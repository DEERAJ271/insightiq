"""
Computes per-customer RFM (Recency, Frequency, Monetary) scores and
quintile-based segment labels from fact_orders + dim_date, writing the
result to customer_rfm_segments.

Dataset quirk worth knowing before reading score_quintile()'s fallback
branch: every customer_key in this Olist-derived warehouse has exactly
one order — customer_id here is effectively an order-scoped identifier,
not a persistent shopper ID carried across repeat purchases — so the
frequency dimension has zero variance and always falls back to a
constant score. See that function's docstring and the DAG's doc_md.
"""
import pandas as pd

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"


def score_quintile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """
    Score a numeric series into 1-5 quintiles via pd.qcut, 5 always
    meaning "best" regardless of whether the underlying metric is
    naturally ascending-is-better (frequency, monetary) or
    descending-is-better (recency, where fewer days since the last
    order is better).

    Falls back to a constant score of 3 (the middle quintile) if the
    series doesn't have enough distinct values for pd.qcut to form 5
    bins — e.g. this dataset's frequency column, where every customer
    has exactly one order and there's nothing to differentiate.
    """
    labels = [1, 2, 3, 4, 5] if higher_is_better else [5, 4, 3, 2, 1]
    try:
        return pd.qcut(series, 5, labels=labels).astype(int)
    except ValueError:
        return pd.Series(3, index=series.index)


def label_segment(r: int, f: int, m: int) -> str:
    """
    Simplified RFM segment labeling. RFM labeling conventions vary
    across sources; this is a reasonable, commonly-seen reduced rule
    set, not an authoritative standard. Scores are 1-5 (5 = best);
    "high" below means >=4, "low" means <=2.

    - Champions       : high R, high F, high M (e.g. "555", "554") —
                        bought recently, often, and spends the most.
    - Loyal Customers : high F, high M, any R — buys often and big
                        regardless of how recently.
    - New Customers   : high R, low F — bought recently but hasn't
                        built up any purchase frequency yet.
    - At Risk         : low R, high F — used to buy often, hasn't
                        been back recently.
    - Lost            : low R, low F, low M — bottom of every
                        dimension.
    - Big Spenders    : high R, high M, but not high F — one big
                        recent purchase, not yet a frequent buyer.
    - Needs Attention : catch-all for everything in the mid-range.
                        Expected to be the largest bucket in most real
                        datasets, since most customers cluster around
                        the middle on at least one dimension — and, in
                        this dataset specifically, the only bucket
                        alongside Big Spenders that's actually reachable,
                        since f_score is always the constant fallback (3)
                        and can never cross the >=4 / <=2 thresholds
                        above.
    """
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if f >= 4 and m >= 4:
        return "Loyal Customers"
    if r >= 4 and f <= 2:
        return "New Customers"
    if r <= 2 and f >= 4:
        return "At Risk"
    if r <= 2 and f <= 2 and m <= 2:
        return "Lost"
    if r >= 4 and m >= 4:
        return "Big Spenders"
    return "Needs Attention"


def build_rfm_segments(**context):
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    df = pd.read_sql("""
        SELECT f.customer_key, f.order_id, f.price, d.full_date AS order_date
        FROM fact_orders f
        JOIN dim_date d ON f.order_date_key = d.date_key
        WHERE f.customer_key IS NOT NULL;
    """, engine)
    df["order_date"] = pd.to_datetime(df["order_date"])

    # Historical data, so "recency" is relative to the most recent order
    # in the dataset, not to today's date.
    max_order_date = df["order_date"].max()

    rfm = df.groupby("customer_key").agg(
        last_order_date=("order_date", "max"),
        frequency=("order_id", "nunique"),
        monetary=("price", "sum"),
    ).reset_index()
    rfm["recency_days"] = (max_order_date - rfm["last_order_date"]).dt.days

    rfm["r_score"] = score_quintile(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = score_quintile(rfm["frequency"], higher_is_better=True)
    rfm["m_score"] = score_quintile(rfm["monetary"], higher_is_better=True)

    rfm["rfm_segment"] = (
        rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
    )
    rfm["segment_label"] = rfm.apply(
        lambda row: label_segment(row["r_score"], row["f_score"], row["m_score"]), axis=1
    )

    result = rfm[[
        "customer_key", "recency_days", "frequency", "monetary",
        "r_score", "f_score", "m_score", "rfm_segment", "segment_label",
    ]].copy()
    result["monetary"] = result["monetary"].round(2)

    result.to_sql("customer_rfm_segments", engine, if_exists="replace", index=False)

    print(f"Wrote {len(result)} customer RFM segment rows")
    print("Segment label distribution:")
    print(result["segment_label"].value_counts().to_string())
    return len(result)


with DAG(
    dag_id="insightiq_rfm_segmentation",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    tags=["insightiq", "segmentation"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_rfm_segmentation

Computes per-customer RFM (Recency, Frequency, Monetary) scores from
`fact_orders` joined to `dim_date`, and writes the result to
`customer_rfm_segments` (`customer_key`, `recency_days`, `frequency`,
`monetary`, `r_score`, `f_score`, `m_score`, `rfm_segment`,
`segment_label`) via `to_sql(..., if_exists="replace")`. Runs on a
weekly schedule (`@weekly`).

- **Recency**: days since each customer's most recent order, relative
  to the most recent order date in the whole dataset (this is
  historical data, not a live feed, so "today" wouldn't mean anything).
- **Frequency**: distinct order count per customer.
- **Monetary**: total price spent per customer.

Each dimension is scored into 1-5 quintiles via `pd.qcut` (5 = best)
and combined into an `rfm_segment` string like `"555"` or `"311"`, then
mapped to a human-readable `segment_label` (Champions, Loyal Customers,
New Customers, At Risk, Lost, Big Spenders, Needs Attention) via a
simplified, documented rule set in `label_segment()` — RFM labeling
conventions vary across sources, so this is a reasonable approximation,
not an authoritative standard.

**Known data quirk:** every `customer_key` in this Olist-derived
warehouse has exactly one order, so the frequency dimension has zero
variance; `pd.qcut` can't form 5 real bins from a constant column, so
`f_score` falls back to a constant middle score (3) for every customer.
In practice, that collapses `segment_label` down to mostly "Needs
Attention" and "Big Spenders" for this specific dataset, since every
label rule that depends on a high or low `f_score` can never fire. The
scoring and labeling logic itself is written generically and would
behave normally against a dataset with real repeat-purchase behavior.
""",
) as dag:

    build_segments = PythonOperator(
        task_id="build_rfm_segments",
        python_callable=build_rfm_segments,
    )
