from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"

with DAG(
    dag_id="insightiq_category_deep_dive",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["insightiq", "dynamic-mapping"],
    default_args={"on_failure_callback": notify_failure},
) as dag:

    def get_top_categories():
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        rows = hook.get_records(
            "SELECT category FROM category_summary ORDER BY order_count DESC LIMIT 5;"
        )
        return [r[0] for r in rows]

    def analyze_category(category: str):
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        result = hook.get_first("""
            SELECT
                COUNT(*) as orders,
                ROUND(AVG(f.price)::numeric, 2) as avg_price,
                ROUND(STDDEV(f.price)::numeric, 2) as price_stddev
            FROM fact_orders f
            JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category = %s;
        """, parameters=(category,))
        print(f"{category}: orders={result[0]}, avg_price={result[1]}, stddev={result[2]}")
        return {"category": category, "orders": result[0], "avg_price": float(result[1])}

    get_categories = PythonOperator(
        task_id="get_top_categories",
        python_callable=get_top_categories,
    )

    analyze = PythonOperator.partial(
        task_id="analyze_category",
        python_callable=analyze_category,
    ).expand(op_args=get_categories.output.map(lambda c: [c]))
