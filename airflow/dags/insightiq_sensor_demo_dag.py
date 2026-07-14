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
