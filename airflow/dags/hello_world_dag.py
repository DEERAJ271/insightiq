from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="hello_world",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["test"],
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
