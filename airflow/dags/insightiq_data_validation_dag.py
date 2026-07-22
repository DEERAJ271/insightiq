from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"

with DAG(
    dag_id="insightiq_data_validation",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["insightiq", "validation"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_data_validation

Runs 4 independent data-quality checks against `fact_orders`: NULL
`customer_key` foreign keys, duplicate order-product rows, review scores
outside the valid 1-5 range, and freight-value outliers (>3x price). Runs
on a daily schedule (`@daily`), and is also triggered automatically as an
independent DagRun by `insightiq_real_etl`'s final task after each
successful ETL run — so validation always runs after fresh data lands, not
just once a day.

Kept as its own DAG (rather than folded into the ETL DAG) so it stays
independently schedulable and testable, and can gain its own checks or
cadence without touching the ETL pipeline.
""",
) as dag:

    def check_null_foreign_keys(**context):
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        result = hook.get_first(
            "SELECT COUNT(*) FROM fact_orders WHERE customer_key IS NULL;"
        )
        count = result[0]
        print(f"NULL customer_key count: {count}")
        context["ti"].xcom_push(key="null_fk_count", value=count)
        if count > 0:
            raise ValueError(f"Found {count} orders with NULL customer_key")

    def check_duplicate_orders(**context):
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        result = hook.get_first(
            """
            SELECT COUNT(*) FROM (
                SELECT order_id, product_key, COUNT(*) as c
                FROM fact_orders
                GROUP BY order_id, product_key
                HAVING COUNT(*) > 1
            ) dupes;
        """
        )
        count = result[0]
        print(f"Duplicate order-product rows: {count}")
        context["ti"].xcom_push(key="duplicate_count", value=count)
        if count > 0:
            raise ValueError(f"Found {count} duplicate order-product rows")

    def check_review_score_range(**context):
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        result = hook.get_first(
            """
            SELECT COUNT(*) FROM fact_orders
            WHERE review_score IS NOT NULL
            AND (review_score < 1 OR review_score > 5);
        """
        )
        count = result[0]
        print(f"Out-of-range review scores: {count}")
        if count > 0:
            raise ValueError(f"Found {count} review scores outside 1-5")

    def check_freight_outliers(**context):
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        result = hook.get_first(
            """
            SELECT COUNT(*) FROM fact_orders
            WHERE freight_value > price * 3;
        """
        )
        count = result[0]
        print(f"Freight value outliers (>3x price): {count}")
        context["ti"].xcom_push(key="freight_outlier_count", value=count)

    check_null_fk = PythonOperator(
        task_id="check_null_foreign_keys",
        python_callable=check_null_foreign_keys,
    )
    check_dupes = PythonOperator(
        task_id="check_duplicate_orders",
        python_callable=check_duplicate_orders,
    )
    check_reviews = PythonOperator(
        task_id="check_review_score_range",
        python_callable=check_review_score_range,
    )
    check_freight = PythonOperator(
        task_id="check_freight_outliers",
        python_callable=check_freight_outliers,
    )

    [check_null_fk, check_dupes, check_reviews, check_freight]
