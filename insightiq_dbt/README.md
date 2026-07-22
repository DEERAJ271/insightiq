# insightiq_dbt

In-warehouse transformation layer: dbt reads directly from the Postgres
tables the Python ETL pipeline (`etl/`) already loaded, builds marts on
top of them, tracks history on a table nothing else in this project
preserves history for, and declares two exposures showing what consumes
those marts downstream. Run and tested from its own Airflow DAG
(`insightiq_dbt_pipeline` — see `airflow/README.md`), and directly from
the CLI for local development.

## Structure

- **`models/staging/stg_fact_orders.sql`** — thin pass-through over the
  `fact_orders` source, the standard staging-layer convention (one
  staging model per source table) even though this project only has one
  fact table to stage.
- **`models/marts/`** — three marts, each a `select` over a `source()`/
  `ref()` with no heavy transformation of its own (the real
  transformation — cleaning, joining, scoring — already happened in
  `etl/transform.py` and the Airflow RFM DAG; these marts expose that
  warehouse state through dbt's lineage/testing/docs layer rather than
  recomputing it):
  - `mart_category_performance` — order count, avg price/freight/review
    score per product category.
  - `mart_customer_segments` — RFM segments as produced by
    `insightiq_rfm_segmentation_dag.py`, exposed unchanged.
  - `mart_delivery_performance` — per-state SLA breach count/percentage.
  - `schema.yml` in this directory documents columns and carries the
    `not_null`/`unique`/`accepted_values` tests below.
- **`snapshots/customer_rfm_snapshot.sql`** — see "Snapshots" below.
- **`models/exposures.yml`** — see "Exposures" below.
- **`analyses/customer_rfm_snapshot_history.sql`** — a `dbt compile`-only
  sample query (not a model — dbt analyses aren't materialized) showing
  how to query the snapshot's history: customers whose `segment_label`
  or `monetary` has changed across snapshot runs.
- **`tests/assert_mart_delivery_performance_breach_percentage_range.sql`**
  — singular test asserting `breach_percentage` stays in `[0, 100]`.

## Snapshots

Every other table in this project is overwritten on each load —
`if_exists="replace"` in the Python/pandas ETL, or `TRUNCATE` + re-insert
in `insightiq_rfm_segmentation_dag.py` — so there's no history to query
anywhere else in the codebase. `snapshots/customer_rfm_snapshot.sql` is
the one exception: a dbt snapshot (SCD Type 2) over
`customer_rfm_segments`, adding `dbt_valid_from`/`dbt_valid_to` columns
so a changed row is versioned (old version closed out, new version
opened) instead of overwritten.

Strategy is `check` (not `timestamp`) with `check_cols: [segment_label,
monetary]`, because `customer_rfm_segments` has no `updated_at` column to
key a timestamp strategy off of — it's a full truncate + append every
run. `check` compares the listed columns directly on each `dbt snapshot`
run and versions the row whenever either changes.

```bash
dbt snapshot   # writes to the snapshots.customer_rfm_snapshot target_schema
```

Verified live: first run inserted all 98,666 rows; a second run with no
underlying data change correctly no-op'd (`INSERT 0 0`).

## Exposures

`models/exposures.yml` declares two downstream consumers of the three
marts, both owned by the same person (`Deeraj`,
`deerajdeepa16@gmail.com`):

- **`streamlit_dashboard`** (`type: application`, `maturity: high`) —
  `app/streamlit_app.py`, built and running today.
- **`power_bi_dashboard`** (`type: dashboard`, `maturity: low`) — the
  Power BI report `streamlit_app.py`'s dashboard tab is meant to embed
  (see its commented-out `st.components.v1.iframe` call); not yet built,
  no `.pbix` file exists in this repo yet.

Both show up as downstream nodes off all three marts in `dbt docs`'
lineage graph (confirmed via `target/manifest.json`'s `child_map`).

## Linting

SQL is linted with [sqlfluff](https://sqlfluff.com/), dbt-aware (it
mocks `ref()`/`source()`/`config()` even without a project-specific
templater config):

```bash
sqlfluff lint models/ --dialect postgres
```

Also runnable via `make lint` from the repo root (which also runs
`ruff` over the rest of the Python codebase) — see the root `Makefile`.
A local, gitignored `.sqlfluff` (`templater = dbt`) exists on some dev
machines for full dbt-context-aware linting, but isn't required — the
command above works standalone against a fresh clone.

## Running locally

```bash
cd insightiq_dbt
dbt run                              # build the staging model + 3 marts
dbt test                             # 9 data tests across sources/models/snapshots
dbt snapshot                         # version customer_rfm_segments (see "Snapshots")
dbt docs generate && dbt docs serve  # browsable lineage graph, http://localhost:8080
```

Or from the repo root: `make dbt-run` (runs `dbt run` + `dbt test`) or
`make test` (Python `pytest tests/` + `dbt test`).

## Two profiles, same project

`profiles.yml` (project default, `host: localhost`) is for running `dbt`
from the Mac terminal. `profiles_docker/profiles.yml` is identical
except `host: host.docker.internal`, used by
`insightiq_dbt_pipeline_dag.py`'s `--profiles-dir` when running `dbt`
from inside the Airflow containers, where `localhost` would otherwise
resolve to the container itself rather than the host's Postgres. Both
point at the same warehouse (`insightiq`, port `5544`) — only the host
differs.

## Numbers

4 models (1 staging + 3 marts) · 9 data tests · 1 snapshot · 2 exposures
· 1 analysis · 7 sources.
