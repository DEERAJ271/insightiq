from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import pandas as pd

CONN_ID = "insightiq_postgres"

with DAG(
    dag_id="insightiq_category_summary",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    tags=["insightiq", "transformation"],
    doc_md="""
### insightiq_category_summary

Rebuilds the `category_summary` table (order count, average price, average
freight, average review score per product category) by aggregating
`fact_orders` joined to `dim_product` and writing the result back to
Postgres via `to_sql(..., if_exists="replace")`. Runs on a weekly schedule
(`@weekly`).

Aggregate columns are coerced with `pd.to_numeric(errors="coerce")` before
rounding as a defensive cast against non-numeric/NULL-tainted values
reaching `.round()`.
""",
) as dag:

    def build_category_summary():
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        engine = hook.get_sqlalchemy_engine()

        df = pd.read_sql("""
            SELECT p.category, f.price, f.freight_value, f.review_score
            FROM fact_orders f
            JOIN dim_product p ON f.product_key = p.product_key
        """, engine)
        print(df.dtypes)

        summary = df.groupby("category").agg(
            order_count=("price", "count"),
            avg_price=("price", "mean"),
            avg_freight=("freight_value", "mean"),
            avg_review_score=("review_score", "mean"),
        ).reset_index()

        summary["avg_price"] = pd.to_numeric(summary["avg_price"], errors="coerce").round(2)
        summary["avg_freight"] = pd.to_numeric(summary["avg_freight"], errors="coerce").round(2)
        summary["avg_review_score"] = pd.to_numeric(summary["avg_review_score"], errors="coerce").round(2)

        summary.to_sql(
            "category_summary",
            engine,
            if_exists="replace",
            index=False,
        )
        print(f"Wrote {len(summary)} category summary rows")
        return len(summary)

    build_summary = PythonOperator(
        task_id="build_category_summary",
        python_callable=build_category_summary,
    )
