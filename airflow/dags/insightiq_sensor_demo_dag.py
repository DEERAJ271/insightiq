"""
Demonstrates a PythonSensor that waits for fact_orders to reach a row-count
threshold before a downstream task runs.

Sensor modes — "poke" vs "reschedule":
  * poke (the default): the sensor task occupies a worker slot for its
    entire wait, checking the condition every `poke_interval` seconds while
    sleeping in-process between checks. Simple, but that worker slot is
    unusable by any other task the whole time.
  * reschedule: the sensor releases its worker slot between checks. Each
    poke that fails puts the task instance back in the scheduler's queue in
    `up_for_reschedule` state, and it's handed to a worker again after
    `poke_interval` elapses. The wait no longer consumes a worker at all.

In a real deployment with a fixed, limited pool of workers, a long-running
poke-mode sensor can starve unrelated DAGs of capacity — e.g. a handful of
sensors waiting on slow upstream data can silently block everything else
from running until they time out. reschedule mode avoids that by only
occupying a worker for the brief moment it takes to check the condition,
which is why it's used here.
"""
import sys
sys.path.insert(0, "/opt/insightiq")

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.python import PythonSensor
from datetime import datetime
from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"

# Set well below the real fact_orders row count (102,425 as of the last
# real ETL run) so this sensor succeeds by default and the DAG passes on
# its own in future runs. For a portfolio walkthrough demonstrating the
# poke/reschedule polling cycle in the logs and UI, temporarily raise this
# to 200000 and drop timeout below to 40s — that forces the sensor to
# genuinely poll a few times and time out instead of succeeding instantly.
ROW_COUNT_THRESHOLD = 1000


def fact_orders_above_threshold() -> bool:
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    count = hook.get_first("SELECT COUNT(*) FROM fact_orders;")[0]
    print(f"fact_orders row count: {count} (threshold: {ROW_COUNT_THRESHOLD})")
    return count > ROW_COUNT_THRESHOLD


def report_ready(**context):
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    count = hook.get_first("SELECT COUNT(*) FROM fact_orders;")[0]
    print(f"Sensor succeeded — fact_orders has {count} rows, proceeding.")


with DAG(
    dag_id="insightiq_sensor_demo",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["insightiq", "sensor-demo"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_sensor_demo

Demonstrates a `PythonSensor` that waits for `fact_orders` to exceed a row
count threshold before `report_ready` runs. Triggered manually
(`schedule=None`).

Runs in `mode="reschedule"` rather than the default `mode="poke"`, so the
sensor releases its worker slot between checks instead of occupying one for
its entire wait — avoiding a scenario where long-running sensors starve
other DAGs of worker capacity. `ROW_COUNT_THRESHOLD` is set well below the
real `fact_orders` count so this succeeds immediately in normal runs; see
the module docstring for how to temporarily raise it to actually
demonstrate the poll/reschedule cycle.
""",
) as dag:

    wait_for_data = PythonSensor(
        task_id="wait_for_fact_orders",
        python_callable=fact_orders_above_threshold,
        poke_interval=10,
        timeout=120,
        mode="reschedule",
    )

    report = PythonOperator(
        task_id="report_ready",
        python_callable=report_ready,
    )

    wait_for_data >> report
