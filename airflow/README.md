# Airflow Orchestration Layer

Local Apache Airflow 3.3.0 via Docker Compose (CeleryExecutor, Redis,
Postgres-backed metadata db), running alongside InsightIQ's own Postgres
warehouse and the n8n automation layer (see `n8n/README.md`). 10 DAGs, each
demonstrating a distinct orchestration pattern rather than all doing the
same kind of work.

## Setup

```bash
cd airflow
docker compose up -d   # airflow-init runs first automatically, then all services
```

Or from the repo root: `make airflow-up`, which also starts the
project's own Postgres container (`docker start insightiq-pg`) first —
the warehouse most of these DAGs read from, separate from the Compose
stack's own internal metadata Postgres. See the root `Makefile`
(`make help` for the full target list).

DAG files under `dags/` are covered by the repo-root pre-commit hooks
(`black` + `ruff --fix`, `.pre-commit-config.yaml`) — same formatting/lint
rules as the rest of the Python codebase, no Airflow-specific exemption.

UI: `http://localhost:8080`, default login `airflow` / `airflow`
(`_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` in
`docker-compose.yaml`, both overridable via `airflow/.env`).

**Every DAG is paused on first load** —
`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'` is set explicitly in
`docker-compose.yaml` — so a fresh DAG will not run on its schedule, and
`airflow dags trigger` on a paused DAG just queues a run that never
executes, until it's unpaused in the UI or via
`docker compose exec airflow-scheduler airflow dags unpause <dag_id>`.

Before any DAG that talks to the project's own Postgres warehouse
(anything using `PostgresHook` or `etl.*`) will actually run, set up the
`insightiq_postgres` Connection — see below.

## DAGs

### 1. `hello_world` — proof of concept

Two `BashOperator` tasks (`say_hello` >> `say_goodbye`) that just echo
text. No dependency on Postgres or project code. `schedule=None`, tagged
`["test"]`. Confirmed the Docker Compose stack itself worked before any
real pipeline was built on top of it.

### 2. `insightiq_data_validation` — parallel validation with XCom

Four independent `PythonOperator` checks against `fact_orders` —
`check_null_foreign_keys`, `check_duplicate_orders`,
`check_review_score_range`, `check_freight_outliers` — expressed as a
task list (`[check_null_fk, check_dupes, check_reviews, check_freight]`)
with no explicit `>>` chaining, so all four run in parallel rather than
sequentially. Each pushes its result count to XCom for downstream
inspection. Runs `@daily`, and (as of the `insightiq_real_etl` chaining
work below) is also triggered on demand after every successful ETL run.
`on_failure_callback=notify_failure` generates a plain-English alert via
Ollama on any check failure.

### 3. `insightiq_category_summary` — pandas transformation

Pulls `fact_orders` joined to `dim_product` via
`PostgresHook.get_sqlalchemy_engine()`, aggregates with a pandas
`groupby` (order count, avg price, avg freight, avg review score per
category), and writes the result back with
`to_sql("category_summary", if_exists="replace")`. Runs `@weekly`.
Aggregate columns are wrapped in `pd.to_numeric(errors="coerce")` before
`.round()` — added after a real incident where an object-dtype column
raised a `TypeError` on `.round()`.

### 4. `insightiq_category_deep_dive` — dynamic task mapping

`get_top_categories` queries the top 5 categories by order count and
returns them as a list; `analyze_category` is expanded once per category
via `PythonOperator.partial(...).expand(op_args=get_categories.output.map(...))`,
so the number of mapped task instances is determined at runtime from the
query result rather than hardcoded. `schedule=None`, tagged
`["insightiq", "dynamic-mapping"]`.

### 5. `insightiq_sensor_demo` — sensor / reschedule mode

A `PythonSensor` (`wait_for_fact_orders`) polls `fact_orders`'s row count
against a threshold every `poke_interval=10s`, `timeout=120s`, running in
`mode="reschedule"` rather than the default `mode="poke"` — the sensor
releases its worker slot between checks instead of occupying one for its
entire wait, which matters because a poke-mode sensor can starve unrelated
DAGs of worker capacity in a deployment with a limited worker pool.
`ROW_COUNT_THRESHOLD` defaults low (1000, well under the real ~102k-row
table) so the DAG passes immediately in normal runs; the module docstring
documents temporarily raising it to force a few real poll cycles for a
demo walkthrough.

### 6. `insightiq_real_etl` — real pipeline + DAG-to-DAG triggering

The primary pipeline, and the first DAG to call the project's actual
`etl/` package instead of reimplementing that logic inline:
`extract_task` >> `transform_task` >> `validate_task` >> `summary_task` >>
`trigger_validation`.

- `extract_task` returns only row counts via XCom — XCom is metadata-DB
  backed and not meant to carry pandas DataFrames of any real size.
- `transform_task` re-extracts locally (cheap; the source is local CSVs)
  and performs transform + load in one task, since the cleaned DataFrames
  it builds never need to leave that task.
- `validate_task` checks row counts and referential integrity via
  `PostgresHook`.
- `summary_task` produces an LLM-generated (Ollama) plain-English run
  summary from the extract/load XCom counts.
- `trigger_validation` is a `TriggerDagRunOperator` that fires
  `insightiq_data_validation` as its own independent DagRun — fire and
  forget, not `wait_for_completion`, so `insightiq_real_etl` succeeds once
  validation has been *triggered*, not once it has *passed*.

`extract_task` and `transform_task` both carry
`execution_timeout=timedelta(minutes=15)` as a safety net against a
runaway task (e.g. a hung DB connection) blocking a worker indefinitely.

### 7. `insightiq_ge_validation` — Great Expectations expectation suite

A formal, expectation-suite-based counterpart to
`insightiq_data_validation`'s hand-written SQL checks, over an
overlapping but not identical rule set: `customer_key`/`product_key`
not null, `review_score` in 1-5 for at least 95% of non-null values
(`mostly=0.95`, tolerant of legitimately unreviewed orders), `price >= 0`,
and `item_count >= 1`. Triggered manually (`schedule=None`).

Reads `fact_orders` via `PostgresHook.get_sqlalchemy_engine()` + pandas,
then validates the DataFrame with Great Expectations' ephemeral-context
`Batch.validate()` API (`gx.get_context(mode="ephemeral")` → `add_pandas()`
→ `add_dataframe_asset()` → `add_batch_definition_whole_dataframe()` →
`batch.validate(expectation)`) — no persisted GX project directory,
Datasource YAML, or Checkpoint config. This is a deliberate substitution:
the classic `PandasDataset`/`ge.from_pandas()` shortcut no longer exists
in `great_expectations` 1.18.2, the version actually installed despite
the `>=0.18` floor in `requirements.txt`. Prints a `[PASS]`/`[FAIL]` line
per expectation with the unexpected/total count, and raises if any
expectation fails — every expectation here is a hard gate, unlike
`insightiq_data_validation`'s freight-outlier check, which only warns.

### 8. `insightiq_rfm_segmentation` — customer segmentation

Computes per-customer Recency/Frequency/Monetary scores from
`fact_orders` + `dim_date` and writes `customer_rfm_segments`. Runs
`@weekly`.

- **Recency**: days since each customer's last order, relative to the
  most recent order date in the dataset (historical data, not a live
  feed).
- **Frequency**: total items purchased (`SUM(item_count)`) — **not**
  distinct order count, which has zero variance in this dataset (every
  `customer_key` here has exactly one order; `customer_id` is
  effectively order-scoped, not a persistent shopper ID). Scored via a
  direct capped value (1 item → 1, ..., 5+ items → 5) rather than
  `pd.qcut`, after verifying that both plain quintile binning (fails
  outright — the data is ~90% single-item orders, so the 25th/50th/75th
  percentiles are all 1) and rank-based quintile binning (technically
  produces 5 balanced bins, but 4 of them turn out to be
  indistinguishable, fabricating differentiation from arbitrary tie
  order) were the wrong tool for this specific skew.
- **Monetary**: total price spent, scored via `pd.qcut` same as recency.

`r_score`/`f_score`/`m_score` (1-5, 5=best) combine into an
`rfm_segment` string (e.g. `"555"`) and map to one of the standard
11 RFM segment labels (Champions, Loyal Customers, Potential
Loyalists, New Customers, Promising, Needs Attention, About to Sleep,
At Risk, Can't Lose Them, Hibernating, Lost) plus two labels added
specifically for this dataset — Big Ticket Shoppers and Lapsed Big
Spenders, covering low item count (`f<=2`) combined with
moderate-to-high spend (`m>=3`) at any recency, which the 11 standard
rules didn't catch and which turned out to be the overwhelming majority
(~52% of all customers) of what an `"Other"` catch-all was absorbing.
`"Other"` still exists for the small residue (~0.4%) of rare `(r, f, m)`
combinations none of the 13 rules cover — see `label_segment()`'s
docstring in the DAG file for the query and breakdown behind this, and
the exact thresholds and ordering.

### 9. `insightiq_dbt_pipeline` — dbt run/test from Airflow

`dbt_run_task` >> `dbt_test_task` >> `summary_task`: builds and tests the
`insightiq_dbt` project's staging model and three marts
(`mart_category_performance`, `mart_customer_segments`,
`mart_delivery_performance`) from inside the Airflow containers, then
asks Ollama for a plain-English summary of the run. Triggered manually
(`schedule=None`).

- `dbt_run_task` / `dbt_test_task` are both `BashOperator`s running
  `cd /opt/insightiq/insightiq_dbt && dbt run` (then `dbt test`) with
  `--profiles-dir /opt/insightiq/insightiq_dbt/profiles_docker`.
- `summary_task` doesn't need a separate log file to know what happened:
  `BashOperator`'s default `do_xcom_push=True` pushes the last line of
  each command's stdout, which for `dbt run`/`dbt test` is always their
  own `Done. PASS=.. ERROR=..` summary line. It pulls both via XCom and
  passes them to Ollama.

**Docker-specific dbt profile.** `insightiq_dbt/profiles.yml` (the
project default) points `host` at `localhost` — correct for running
`dbt` from the Mac terminal, wrong from inside a container, where
`localhost` resolves to the container itself rather than the host's
Postgres. Same networking pattern as `insightiq_real_etl_dag.py`'s
`DATABASE_URL` override (see "Container networking" below).
`insightiq_dbt/profiles_docker/profiles.yml` is identical except for
`host: host.docker.internal`, and the DAG points `--profiles-dir` at it
instead.

**Two infrastructure fixes this required**, beyond just adding the
docker-specific profile:

- `--profiles-dir` is a *directory* flag — dbt only ever looks for a file
  literally named `profiles.yml` inside whatever directory it's pointed
  at; there's no way to give it an alternate filename. A naive
  `profiles_docker.yml` sitting directly in `insightiq_dbt/` would never
  be picked up and dbt would silently fall back to a missing/wrong
  profile. The docker profile has to live in its own subdirectory
  (`insightiq_dbt/profiles_docker/profiles.yml`) instead.
- `airflow/requirements.txt` didn't include `dbt-core`/`dbt-postgres` at
  all, so the `dbt` CLI didn't exist in the Airflow image and
  `dbt_run_task` would fail immediately with "command not found."
  Adding those also surfaced a second, pre-existing issue: the file's
  `numpy>=1.26,<2` pin (copied from the main project's
  requirements.txt, where it exists for local torch/macOS compatibility)
  broke the image build outright — `apache/airflow:3.3.0` runs Python
  3.13, numpy 1.26.4 has no wheel for it, and there's no compiler in the
  container to build one from source, while numpy 2.x (already bundled
  in the base image) works fine. The pin was relaxed to `numpy>=1.26`
  for this file only.

Verified end-to-end against the running containers: `dbt_run_task` built
all 4 models, `dbt_test_task` passed all 7 tests, and `summary_task`
returned a real Ollama-generated summary (its first run hit the same
30s Ollama-timeout-on-cold-model-load pattern as
`insightiq_real_etl_dag.py`'s `summary_task` and `notify_failure` — the
task still succeeds via the `try/except` fallback text, it just doesn't
have a real summary that run).

### 10. `insightiq_post_load_asset_consumer` — Asset-based scheduling

Demonstrates Airflow 3.x's Asset feature (the rename of Airflow 2's
Datasets) as a second, differently-architected way to chain DAGs, next to
`insightiq_real_etl` → `insightiq_data_validation`'s `TriggerDagRunOperator`
call above.

`insightiq_real_etl`'s `transform_task` declares
`FACT_ORDERS_LOADED` — a URI-based Asset identifier,
`postgres://host.docker.internal:5544/insightiq/public/fact_orders`
(`dags/utils/assets.py`, built via the postgres provider's
`create_asset()` helper rather than a bare `Asset(uri=...)`, since its
AIP-60 URI sanitizer requires a full `host:port/database/schema/table`
path) — as an `outlet`. `insightiq_post_load_asset_consumer` schedules on
that same asset (`schedule=[FACT_ORDERS_LOADED]`) instead of a cron
expression or a manual trigger: a new DagRun is created automatically
every time the asset is updated, i.e. every time `transform_task`
succeeds.

**Architecturally different from `insightiq_real_etl` →
`insightiq_data_validation`**, not just a stylistic alternative:

- `TriggerDagRunOperator` is producer-initiated and point-to-point — the
  ETL DAG's own code names `insightiq_data_validation`'s `dag_id`
  literally. Adding another consumer means editing the producer to add
  another `TriggerDagRunOperator`.
- Asset scheduling is consumer-declared and decoupled — `transform_task`
  only declares what it produces (`outlets=[FACT_ORDERS_LOADED]`) and has
  no knowledge that `insightiq_post_load_asset_consumer` exists at all,
  or that anything else is scheduled on the same asset. Adding another
  consumer means writing a new DAG with that asset in its `schedule=[...]`;
  `insightiq_real_etl` never changes.

Both mechanisms are kept side by side deliberately: `TriggerDagRunOperator`
is the right tool when a producer needs to know its consumer ran (e.g.
`wait_for_completion=True`); Asset scheduling is the right tool when a
producer just needs to publish "this data changed" and doesn't care who,
if anyone, is listening.

**Verified end-to-end against the running containers**, not just parsed:
triggered `insightiq_real_etl` manually, and once `transform_task`
succeeded, Airflow's own scheduler/task log for the resulting
`insightiq_post_load_asset_consumer` run stated explicitly "Triggered by
asset event(s)", including the full event trace — source task
(`transform_task`), source DAG (`insightiq_real_etl`), source run id, and
timestamp — confirming the decoupled trigger actually fired, not just
that the DAG *could* be scheduled that way. `insightiq_post_load_asset_consumer`
is paused by default (per the "every DAG is paused on first load" note
above) since it's a demo DAG, not part of the production chain — unpause
it to see this fire on a real `insightiq_real_etl` run.

## Airflow Connection setup

The DAGs above that use `PostgresHook` (`insightiq_data_validation`,
`insightiq_category_summary`, `insightiq_category_deep_dive`,
`insightiq_sensor_demo`, and `validate_task` in `insightiq_real_etl`) all
reference a connection with `conn_id="insightiq_postgres"`, configured
manually in the Airflow UI (**Admin > Connections**):

| Field         | Value                  |
|---------------|------------------------|
| Connection Id | `insightiq_postgres`   |
| Connection Type | Postgres             |
| Host          | `host.docker.internal` |
| Port          | `5544`                 |
| Schema        | `insightiq`            |
| Login         | `postgres`             |
| Password      | `postgres`             |

This is a separate connection from Airflow's own internal metadata
database (the `postgres` service in `docker-compose.yaml`, database
`airflow`, reachable at `postgres:5432` on the `airflow_default` Docker
network) — `insightiq_postgres` points at the project's actual data
warehouse, which runs outside the Airflow Compose stack entirely.

## Container networking

`host.docker.internal` resolves to the host machine from inside the
Airflow containers (Docker Desktop for Mac) and is used in two places:

- The `insightiq_postgres` connection above, reaching the project's
  Postgres warehouse at port `5544` on the host.
- Ollama calls in `summary_task` and `dags/utils/alerting.py`'s
  `notify_failure`, both POSTing to
  `http://host.docker.internal:11434/api/generate`.

A related trap specific to `insightiq_real_etl_dag.py`: `etl.load.get_engine()`
reads `DATABASE_URL` from `.env` at import time, which is
`postgresql://postgres:postgres@localhost:5544/insightiq` — correct when
running the ETL pipeline outside Docker, but wrong inside the Airflow
containers, where `localhost` refers to the container itself, not the
host. `transform_task` works around this by setting
`os.environ["DATABASE_URL"]` to the `host.docker.internal:5544` variant
as its first line, before any `etl.*` module is imported — `python-dotenv`'s
`load_dotenv()` doesn't override an already-set env var, so the explicit
override wins.

The project root is bind-mounted into every Airflow container at
`/opt/insightiq` (see `docker-compose.yaml`'s `x-airflow-common` volumes
and each real DAG's `sys.path.insert(0, "/opt/insightiq")`), which is what
lets DAGs import `etl.*` and `dags.utils.alerting` directly instead of
duplicating that logic.

## Running the DAG integrity tests

```
docker compose exec airflow-worker pytest tests/ -v
```

`tests/test_dag_integrity.py` loads every DAG via `DagBag(dag_folder="dags/")`
and asserts: no import errors, all expected DAG ids are present, every
non-test DAG carries tags, no cycles, `notify_failure` is wired as
`on_failure_callback` where expected, and `insightiq_data_validation` has
its expected task set. These test structure, not business logic — they
catch the class of failure where a DAG file has a typo or bad import and
silently fails to load in the UI. `tests/test_alerting.py` covers
`notify_failure` itself directly (LLM summary on success, fallback
message when Ollama is unreachable or returns a malformed response). 12
tests total, both files, passing as of this writing.

## Why both n8n and Airflow?

n8n came first — a visual, node-based tool that got a working
validation-and-alerting workflow running in an afternoon with no code, and
is genuinely a faster way to prototype a simple linear flow.

Airflow was added deliberately, not to replace n8n, but because it's the
DAG-as-code, retry/scheduling/sensor-native tool that data engineering
roles actually expect familiarity with. Concretely, Airflow gives this
project things n8n's visual canvas doesn't model well: dynamic task
mapping (`insightiq_category_deep_dive`), a real reschedule-mode sensor
(`insightiq_sensor_demo`), DAG-to-DAG triggering
(`insightiq_real_etl` → `insightiq_data_validation`), and DagBag-based
integrity tests runnable in CI. Both layers call the same local Ollama
instance for LLM-generated summaries, so neither duplicates the LLM
integration logic — they differ in orchestration model, not in what they
summarize.

## Known limitations / follow-ups

- `insightiq_ge_validation` and `insightiq_data_validation` check
  overlapping but not identical rules against `fact_orders` and run
  independently of each other — neither triggers the other, and nothing
  reconciles a case where one passes and the other fails.
- `notify_failure` (`dags/utils/alerting.py`) prints an LLM-generated
  alert summary to the failing task's logs. It is not wired to a real
  notification channel (Slack, email, PagerDuty) — a failure is only
  visible to someone actively watching the Airflow UI or logs.
- `trigger_validation` in `insightiq_real_etl` is fire-and-forget
  (`wait_for_completion` not set): the ETL DAG's own success/failure
  status never reflects whether the triggered validation run actually
  passed.
- `insightiq_sensor_demo`'s threshold is deliberately set low so it
  passes instantly in normal runs; it only demonstrates real polling
  behavior when the threshold is temporarily raised per the module
  docstring.
- No CI pipeline runs `tests/test_dag_integrity.py` automatically on
  push — it currently has to be run manually via `docker compose exec`.
