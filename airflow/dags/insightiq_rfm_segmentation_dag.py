"""
Computes per-customer RFM (Recency, Frequency, Monetary) scores and
quintile-based segment labels from fact_orders + dim_date, writing the
result to customer_rfm_segments.

Dataset quirk worth knowing up front: every customer_key in this
Olist-derived warehouse has exactly one order — customer_id here is
effectively an order-scoped identifier, not a persistent shopper ID
carried across repeat purchases — so distinct order count has zero
variance and can't drive the frequency dimension at all. Frequency is
computed from total item_count per customer instead (see
build_rfm_segments() and score_frequency()), which does vary, but is
heavily right-skewed (~90% of customers bought exactly one item), which
is itself worth reading score_frequency()'s docstring for before
assuming a plain pd.qcut quintile would work here.
"""

import pandas as pd
from sqlalchemy import text

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


def score_frequency(total_items: pd.Series) -> pd.Series:
    """
    Score total items purchased per customer into a 1-5 "frequency"
    score, 5 = best.

    Tried plain pd.qcut() first and rejected it: total_items is heavily
    right-skewed in this dataset (~90% of customers bought exactly one
    item), so the 25th/50th/75th percentiles are all 1 and qcut can't
    form 5 real bins. Also tried rank-based quintile binning
    (pd.qcut(total_items.rank(method="first"), 5, ...), which breaks
    ties by row order to force 5 equal-COUNT bins) and rejected that
    too after checking what it actually produced: 5 perfectly balanced
    bins, but scores 1 through 4 were indistinguishable from each other
    (every customer in all four had total_items == 1) — it was
    fabricating differentiation from arbitrary tie order, not reflecting
    anything real about the customer.

    Uses a direct value-based score instead: total_items capped at 5
    (1 item -> score 1, 2 -> 2, 3 -> 3, 4 -> 4, 5+ -> 5). Not a
    statistical quintile, but honest about what the data actually shows
    — and this is standard practice for frequency counts in RFM
    analysis generally, since order/item counts are usually small,
    skewed integers rather than a smooth continuous distribution.
    """
    return total_items.clip(upper=5).astype(int)


def label_segment(r: int, f: int, m: int) -> str:
    """
    Standard 11-segment RFM labeling (Champions / Loyal Customers /
    Potential Loyalists / New Customers / Promising / Needs Attention /
    About to Sleep / At Risk / Can't Lose Them / Hibernating / Lost)
    plus two dataset-specific additions (Big Ticket Shoppers / Lapsed
    Big Spenders, see below), checked as an if/elif chain from most to
    least specific/valuable so a customer matching multiple conditions
    gets the more meaningful label. Scores are 1-5 (5 = best).

    Querying customer_rfm_segments confirmed the "Other" fallback was
    firing for 51,095 of 98,666 customers (~52%) before the two extra
    rules below were added. Grouping those rows by (r, f, m) showed the
    gap wasn't the broad r=f=m=3 middle ground one might guess — it was
    overwhelmingly (93% of "Other") f<=2 combined with m>=3, spread
    ~evenly across *all* r values. That combination makes sense given
    this dataset's frequency quirk (see module docstring and
    score_frequency()): frequency here is item count capped at 5 and
    heavily skewed toward 1, so it's effectively independent of spend —
    a customer can easily buy a single, expensive item. None of the 11
    standard rules were written to catch "low item count, high spend"
    at every recency level, since standard RFM assumes frequency and
    monetary are correlated. The remaining ~0.4% of "Other" (scattered
    across dozens of rare (r,f,m) cells, each a handful of customers)
    is left as genuine fallback rather than chased with more rules.
    """
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 4 and m >= 3:
        return "Loyal Customers"
    if r >= 4 and 2 <= f < 4 and m >= 2:
        return "Potential Loyalists"
    if r >= 4 and f <= 2 and m <= 2:
        return "New Customers"
    if r == 3 and f <= 2 and m <= 3:
        return "Promising"
    if r == 3 and f == 3 and m == 3:
        return "Needs Attention"
    if r == 2 and f <= 2 and m <= 2:
        return "About to Sleep"
    if r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 1 and f >= 4 and m >= 4:
        return "Can't Lose Them"
    # As specified, Hibernating (r==1, f<=2, m<=2) and Lost (r==1, f<=2,
    # m<=2) were identical conditions, making Lost unreachable dead code
    # behind Hibernating. Kept them as a specific-first pair instead:
    # Lost is the strictly worse case (bottom of every dimension) and is
    # checked before the broader Hibernating, matching the "more
    # specific first" ordering principle used throughout this chain.
    if r == 1 and f <= 1 and m <= 1:
        return "Lost"
    if r == 1 and f <= 2 and m <= 2:
        return "Hibernating"
    # Dataset-specific: low item count (f<=2) but moderate-to-high spend
    # (m>=3) isn't covered by any standard rule above at any recency
    # level (see docstring). Split by recency so the two labels stay
    # actionable: recent big-ticket buyers are a nurture/upsell target,
    # lapsed ones are a win-back target.
    if r >= 3 and f <= 2 and m >= 3:
        return "Big Ticket Shoppers"
    if r <= 2 and f <= 2 and m >= 3:
        return "Lapsed Big Spenders"
    return "Other"


def build_rfm_segments(**context):
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    df = pd.read_sql(
        """
        SELECT f.customer_key, f.order_id, f.item_count, f.price,
               d.full_date AS order_date
        FROM fact_orders f
        JOIN dim_date d ON f.order_date_key = d.date_key
        WHERE f.customer_key IS NOT NULL;
    """,
        engine,
    )
    df["order_date"] = pd.to_datetime(df["order_date"])

    # Historical data, so "recency" is relative to the most recent order
    # in the dataset, not to today's date.
    max_order_date = df["order_date"].max()

    rfm = (
        df.groupby("customer_key")
        .agg(
            last_order_date=("order_date", "max"),
            # Distinct order count has zero variance in this dataset (every
            # customer has exactly one order) — total items purchased is
            # used as the frequency signal instead, since it actually varies.
            frequency=("item_count", "sum"),
            monetary=("price", "sum"),
        )
        .reset_index()
    )
    rfm["recency_days"] = (max_order_date - rfm["last_order_date"]).dt.days

    rfm["r_score"] = score_quintile(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = score_frequency(rfm["frequency"])
    rfm["m_score"] = score_quintile(rfm["monetary"], higher_is_better=True)

    rfm["rfm_segment"] = (
        rfm["r_score"].astype(str)
        + rfm["f_score"].astype(str)
        + rfm["m_score"].astype(str)
    )
    rfm["segment_label"] = rfm.apply(
        lambda row: label_segment(row["r_score"], row["f_score"], row["m_score"]),
        axis=1,
    )

    result = rfm[
        [
            "customer_key",
            "recency_days",
            "frequency",
            "monetary",
            "r_score",
            "f_score",
            "m_score",
            "rfm_segment",
            "segment_label",
        ]
    ].copy()
    result["monetary"] = result["monetary"].round(2)

    # TRUNCATE + append instead of to_sql(if_exists="replace"): "replace"
    # does a DROP TABLE, which fails once mart_customer_segments (a dbt
    # view) depends on this table. TRUNCATE clears the rows without
    # dropping the table, so the dependent view stays valid.
    with engine.begin() as conn:
        table_exists = (
            conn.execute(
                text("SELECT to_regclass('public.customer_rfm_segments')")
            ).scalar()
            is not None
        )
        if table_exists:
            conn.execute(text("TRUNCATE TABLE customer_rfm_segments"))
    result.to_sql("customer_rfm_segments", engine, if_exists="append", index=False)

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
`segment_label`), truncating and re-inserting rather than dropping the
table so `mart_customer_segments` (a dbt view over this table) doesn't
break. Runs on a weekly schedule (`@weekly`).

- **Recency**: days since each customer's most recent order, relative
  to the most recent order date in the whole dataset (this is
  historical data, not a live feed, so "today" wouldn't mean anything).
- **Frequency**: total items purchased per customer (`SUM(item_count)`),
  **not** distinct order count — every `customer_key` in this
  Olist-derived warehouse has exactly one order (`customer_id` here is
  effectively order-scoped, not a persistent shopper ID), so order
  count has zero variance and can't differentiate anyone. Total items
  purchased does vary and is used instead.
- **Monetary**: total price spent per customer.

Recency and monetary are scored into 1-5 quintiles via `pd.qcut` (5 =
best, `score_quintile()`). Frequency uses a different scorer,
`score_frequency()`: total items is heavily right-skewed (~90% of
customers bought exactly one item), so plain quintile binning can't
form 5 real bins, and rank-based tie-breaking was tried and rejected
after checking its actual output — it produced 5 evenly-sized bins, but
4 of the 5 were indistinguishable (all exactly 1 item), fabricating
differentiation from arbitrary row order rather than reflecting
anything real. Frequency is scored directly instead: total items
capped at 5 (1 item -> score 1, ..., 5+ items -> score 5) — see that
function's docstring.

The three scores combine into an `rfm_segment` string like `"555"` or
`"311"`, then map to a human-readable `segment_label` via the standard
11-segment RFM scheme (Champions, Loyal Customers, Potential Loyalists,
New Customers, Promising, Needs Attention, About to Sleep, At Risk,
Can't Lose Them, Hibernating, Lost) plus two segments added specifically
for this dataset (Big Ticket Shoppers, Lapsed Big Spenders) to cover a
large, systematic gap the 11 standard rules left behind: low item count
(f<=2) combined with moderate-to-high spend (m>=3), which is common here
because frequency (item count, capped at 5 and skewed toward 1) is
largely independent of monetary value. Before adding those two rules,
"Other" absorbed ~52% of all customers; an `"Other"` catch-all remains
for the small residue (~0.4%) of rare `(r, f, m)` combinations none of
the 13 rules cover — see `label_segment()`'s docstring for the query
and breakdown that led to this. RFM labeling conventions vary across
sources, so exact thresholds are one reasonable convention, not an
authoritative standard.
""",
) as dag:

    build_segments = PythonOperator(
        task_id="build_rfm_segments",
        python_callable=build_rfm_segments,
    )
