"""
Real ETL pipeline: extract olist CSVs, transform into the star schema, load
into Postgres, validate, and summarize the run.

DataFrames never cross an XCom boundary — XCom is metadata-DB-backed and not
meant to carry pandas DataFrames of any real size. extract_task only reports
row counts (for an early sanity signal); transform_task re-extracts (cheap,
since the source is local CSVs) and performs transform+load in one task,
since the cleaned DataFrames it builds never need to leave that task.
"""
import sys
sys.path.insert(0, "/opt/insightiq")

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import requests

from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"

FK_CHECKS = [
    ("customer_key", "dim_customer"),
    ("product_key", "dim_product"),
    ("seller_key", "dim_seller"),
]

LOADED_TABLES = ["dim_date", "dim_customer", "dim_seller", "dim_product", "fact_orders"]


def extract_task(**context):
    from etl.extract import extract_all

    raw = extract_all()
    counts = {name: len(df) for name, df in raw.items()}
    for name, count in counts.items():
        print(f"{name}: {count} rows")
    return counts


def transform_task(**context):
    import pandas as pd
    from etl.extract import extract_all
    from etl.transform import (
        clean_orders, clean_products, clean_customers, clean_sellers,
        build_dim_date, build_fact_orders,
    )
    from etl.load import load_table, get_engine
    from etl.run_pipeline import _assign_key, _truncate_all

    print("Re-extracting (extract_task's DataFrames don't survive XCom)...")
    raw = extract_all()

    print("Transforming...")
    orders = clean_orders(raw["orders"])
    dim_customer = _assign_key(clean_customers(raw["customers"]), "customer_key")
    dim_seller = _assign_key(clean_sellers(raw["sellers"]), "seller_key")
    dim_product = _assign_key(
        clean_products(raw["products"], raw["category_translation"]), "product_key"
    )
    all_dates = pd.concat([
        orders["order_purchase_timestamp"],
        orders["order_delivered_customer_date"],
        orders["order_estimated_delivery_date"],
    ])
    dim_date = build_dim_date(all_dates.min(), all_dates.max())
    fact = build_fact_orders(
        orders, raw["order_items"], dim_customer, dim_product, dim_seller, raw["reviews"]
    )

    print("Loading...")
    engine = get_engine()
    _truncate_all(engine)
    load_table(dim_date, "dim_date")
    load_table(dim_customer, "dim_customer")
    load_table(dim_seller, "dim_seller")
    load_table(dim_product, "dim_product")
    load_table(fact, "fact_orders")

    loaded_counts = {
        "dim_date": len(dim_date),
        "dim_customer": len(dim_customer),
        "dim_seller": len(dim_seller),
        "dim_product": len(dim_product),
        "fact_orders": len(fact),
    }
    print(f"Loaded counts: {loaded_counts}")
    return loaded_counts


def validate_task(**context):
    hook = PostgresHook(postgres_conn_id=CONN_ID)

    for table in LOADED_TABLES:
        count = hook.get_first(f"SELECT COUNT(*) FROM {table};")[0]
        print(f"{table}: {count} rows")
        if count == 0:
            raise ValueError(f"{table} has 0 rows after load")

    for col, dim_table in FK_CHECKS:
        result = hook.get_first(f"""
            SELECT COUNT(*) FROM fact_orders f
            LEFT JOIN {dim_table} d ON f.{col} = d.{col}
            WHERE f.{col} IS NOT NULL AND d.{col} IS NULL;
        """)
        count = result[0]
        print(f"Orphaned {col} -> {dim_table}: {count}")
        if count > 0:
            raise ValueError(f"Found {count} orphaned {col} reference(s) to {dim_table}")


def summary_task(**context):
    ti = context["ti"]
    raw_counts = ti.xcom_pull(task_ids="extract_task")
    loaded_counts = ti.xcom_pull(task_ids="transform_task")

    prompt = (
        f"An Airflow ETL pipeline just ran. Raw extracted row counts: {raw_counts}. "
        f"Rows loaded into the warehouse: {loaded_counts}. "
        f"Write a 2-3 sentence plain-English summary of this pipeline run for "
        f"a data analyst, noting anything that looks off (e.g. large drops "
        f"between extracted and loaded row counts)."
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

    print(f"=== ETL RUN SUMMARY ===\n{summary}\n=======================")
    return summary


with DAG(
    dag_id="insightiq_real_etl",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["insightiq", "etl", "real-pipeline"],
    default_args={"on_failure_callback": notify_failure},
) as dag:

    extract = PythonOperator(task_id="extract_task", python_callable=extract_task)
    transform = PythonOperator(task_id="transform_task", python_callable=transform_task)
    validate = PythonOperator(task_id="validate_task", python_callable=validate_task)
    summary = PythonOperator(task_id="summary_task", python_callable=summary_task)

    extract >> transform >> validate >> summary
