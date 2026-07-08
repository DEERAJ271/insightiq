"""
Translates a natural-language question into a SQL query against the
InsightIQ warehouse, using Claude, then executes it read-only.

TODO (good Claude Code task): add a validation step that rejects
non-SELECT statements before execution, and a retry loop that feeds the
error back to Claude if the generated SQL fails.
"""
import os
import pandas as pd
from anthropic import Anthropic
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
DATABASE_URL = os.getenv("DATABASE_URL")

SCHEMA_SUMMARY = """
Tables:
fact_orders(order_key, order_id, customer_key, product_key, seller_key,
    order_date_key, delivered_date_key, estimated_date_key, order_status,
    item_count, price, freight_value, payment_type, payment_installments, review_score)
dim_customer(customer_key, customer_id, city, state, country)
dim_product(product_key, product_id, category, weight_g, length_cm, height_cm, width_cm)
dim_seller(seller_key, seller_id, city, state)
dim_date(date_key, full_date, year, quarter, month, day, day_of_week, is_weekend)
"""

SYSTEM_PROMPT = f"""You are a SQL generator for a Postgres data warehouse.
Schema:
{SCHEMA_SUMMARY}

Rules:
- Only generate SELECT statements.
- Return ONLY the SQL query, no explanation, no markdown fences.
- Join through the dimension tables using their surrogate keys.
"""


def generate_sql(question: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text.strip()


def run_query(sql: str) -> pd.DataFrame:
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed.")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def answer_numeric_question(question: str) -> tuple[str, pd.DataFrame]:
    sql = generate_sql(question)
    return sql, run_query(sql)


if __name__ == "__main__":
    # Temporary: hardcoded queries from sql/analytical_queries.sql to validate
    # run_query() and the DB connection without calling the Anthropic API.

    TESTS = {
        "AOV by product category (Q2)": """
SELECT p.category, ROUND(AVG(f.price), 2) AS avg_order_value, COUNT(*) AS n_orders
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY avg_order_value DESC
""".strip(),

        "SLA breach rate by state (Q3)": """
SELECT c.state,
       ROUND(100.0 * SUM(CASE WHEN f.delivered_date_key > f.estimated_date_key THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS sla_breach_pct
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.state
ORDER BY sla_breach_pct DESC
""".strip(),

        "Repeat customer rate (Q4)": """
SELECT
    COUNT(*) FILTER (WHERE order_count > 1) AS repeat_customers,
    COUNT(*) AS total_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE order_count > 1) / COUNT(*), 2) AS repeat_rate_pct
FROM (
    SELECT customer_key, COUNT(DISTINCT order_id) AS order_count
    FROM fact_orders
    GROUP BY customer_key
) t
""".strip(),
    }

    for label, sql in TESTS.items():
        print(f"{'='*60}")
        print(f"TEST: {label}")
        print(f"SQL:\n{sql}\n")
        df = run_query(sql)
        print(df.to_string(index=False))
        print()

    # Verify non-SELECT rejection
    print(f"{'='*60}")
    print("TEST: non-SELECT rejection")
    try:
        run_query("DROP TABLE fact_orders")
        print("FAIL — should have raised ValueError")
    except ValueError as e:
        print(f"PASS — correctly rejected: {e}")
