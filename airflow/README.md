# Airflow Orchestration Layer

Local Apache Airflow 3.3.0 via Docker Compose (CeleryExecutor, Redis,
Postgres-backed metadata db), running alongside InsightIQ's own Postgres
warehouse and the n8n automation layer (see `n8n/README.md`). 6 DAGs, each
demonstrating a distinct orchestration pattern rather than all doing the
same kind of work.

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
silently fails to load in the UI.

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

- `great-expectations` is pinned in `requirements.txt` but not actually
  used by any DAG yet — validation today is hand-rolled SQL checks in
  `insightiq_data_validation`, not Great Expectations expectation suites.
  A GE-based validation DAG is a planned follow-up, not a built feature.
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
