from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="hello_world",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["test"],
    doc_md="""
### hello_world

Smoke-test DAG confirming the Airflow setup itself works — two
`BashOperator` tasks that just echo text, with no dependency on Postgres,
`etl/`, or any other project code. Triggered manually (`schedule=None`).
Not part of the InsightIQ pipeline; kept around as a baseline sanity check.
""",
) as dag:
    task1 = BashOperator(
        task_id="say_hello",
        bash_command="echo 'Hello from Airflow'",
    )

    task2 = BashOperator(
        task_id="say_goodbye",
        bash_command="echo 'InsightIQ Airflow setup confirmed working'",
    )

    task1 >> task2
