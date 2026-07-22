"""
Runs the insightiq_dbt project (mart_category_performance,
mart_customer_segments, mart_delivery_performance, and their staging
model) inside the Airflow containers: `dbt run` then `dbt test`, followed
by an LLM-generated plain-English summary of the run via Ollama.

Both dbt commands use --profiles-dir insightiq_dbt/profiles_docker
instead of the project's default insightiq_dbt/profiles.yml, since that
default points at host: localhost — correct for running dbt from a Mac
terminal, wrong inside the Airflow containers where "localhost" resolves
to the container itself rather than the host's Postgres (same class of
bug fixed for the etl/ package in insightiq_real_etl_dag.py's
REAL_DB_URL override). profiles_docker/profiles.yml is identical except
for host: host.docker.internal. /opt/insightiq is already bind-mounted
into the containers (see airflow/docker-compose.yaml), so insightiq_dbt/
is visible there without any new volume mount.
"""

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import requests

from dags.utils.alerting import notify_failure

DBT_PROJECT_DIR = "/opt/insightiq/insightiq_dbt"
DBT_PROFILES_DIR = "/opt/insightiq/insightiq_dbt/profiles_docker"
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"


def summary_task(**context):
    ti = context["ti"]
    # BashOperator's default do_xcom_push=True pushes the last line of the
    # command's stdout — for dbt run/test that's always the "Done. PASS=.."
    # summary line, so no separate log file is needed to know what ran and
    # whether it passed.
    run_result = ti.xcom_pull(task_ids="dbt_run_task") or "(no output captured)"
    test_result = ti.xcom_pull(task_ids="dbt_test_task") or "(no output captured)"

    prompt = (
        f"An Airflow DAG just ran `dbt run` followed by `dbt test` for the "
        f"InsightIQ warehouse. dbt run's final summary line: {run_result}. "
        f"dbt test's final summary line: {test_result}. Both commands must "
        f"have exited successfully for this task to run at all. Write a 2-3 "
        f"sentence plain-English summary for a data analyst of what ran and "
        f"whether the tests passed."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=30,
        )
        summary = response.json().get("response", "No summary available")
    except Exception as e:
        summary = f"(Summary generation failed: {e})"

    print(f"=== DBT RUN SUMMARY ===\n{summary}\n=======================")
    return summary


with DAG(
    dag_id="insightiq_dbt_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["insightiq", "dbt"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_dbt_pipeline

Runs the insightiq_dbt project's models and tests from inside Airflow:
`dbt run` builds stg_fact_orders and the three marts
(mart_category_performance, mart_customer_segments,
mart_delivery_performance); `dbt test` then runs their not_null/unique/
accepted_values/custom-range tests; `summary_task` produces an
LLM-generated (Ollama) plain-English summary of the run. Triggered
manually (`schedule=None`).

Both dbt commands pass `--profiles-dir insightiq_dbt/profiles_docker`
(host: host.docker.internal) instead of the project's default
`profiles.yml` (host: localhost, correct only for running dbt from a Mac
terminal outside Docker) — see the module docstring for why.
""",
) as dag:

    dbt_run_task = BashOperator(
        task_id="dbt_run_task",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_test_task = BashOperator(
        task_id="dbt_test_task",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    summary = PythonOperator(task_id="summary_task", python_callable=summary_task)

    dbt_run_task >> dbt_test_task >> summary
