"""
Great Expectations-based validation for fact_orders.

Uses GX's lightweight ephemeral-context + Batch.validate() API rather than
a full GX project (no persisted `great_expectations/` directory, Datasource
YAML, or Checkpoint config on disk) — the closest equivalent, in the
great_expectations 1.18.2 pinned in requirements.txt, to the old
`PandasDataset`/`ge.from_pandas()` shortcut, which was removed from the
library well before this version.
"""

import pandas as pd
import great_expectations as gx
import great_expectations.expectations as gxe

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from dags.utils.alerting import notify_failure

CONN_ID = "insightiq_postgres"


def run_ge_expectations(**context):
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    engine = hook.get_sqlalchemy_engine()
    df = pd.read_sql(
        "SELECT customer_key, product_key, review_score, price, item_count "
        "FROM fact_orders;",
        engine,
    )

    gx_context = gx.get_context(mode="ephemeral")
    data_source = gx_context.data_sources.add_pandas(name="insightiq_postgres_pandas")
    data_asset = data_source.add_dataframe_asset(name="fact_orders_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe(
        "fact_orders_batch"
    )
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        (
            "customer_key not null",
            gxe.ExpectColumnValuesToNotBeNull(column="customer_key"),
        ),
        (
            "product_key not null",
            gxe.ExpectColumnValuesToNotBeNull(column="product_key"),
        ),
        # mostly=0.95: some legitimate nulls exist in review_score (unreviewed
        # orders); nulls are excluded from this check entirely, mostly just
        # tolerates a small fraction of bad non-null values as noise rather
        # than data corruption.
        (
            "review_score between 1-5 (mostly 95%)",
            gxe.ExpectColumnValuesToBeBetween(
                column="review_score", min_value=1, max_value=5, mostly=0.95
            ),
        ),
        (
            "price >= 0",
            gxe.ExpectColumnValuesToBeBetween(
                column="price", min_value=0, max_value=None
            ),
        ),
        (
            "item_count >= 1",
            gxe.ExpectColumnValuesToBeBetween(
                column="item_count", min_value=1, max_value=None
            ),
        ),
    ]

    print("=== Great Expectations validation: fact_orders ===")
    failures = []
    for label, expectation in expectations:
        result = batch.validate(expectation)
        status = "PASS" if result.success else "FAIL"
        unexpected = result.result.get("unexpected_count", 0)
        total = result.result.get("element_count", len(df))
        print(f"[{status}] {label} — {unexpected}/{total} unexpected")
        if not result.success:
            failures.append(label)
    print("===================================================")

    if failures:
        raise ValueError(f"Great Expectations validation failed: {failures}")


with DAG(
    dag_id="insightiq_ge_validation",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["insightiq", "validation", "great-expectations"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_ge_validation

A formal, expectation-suite-based alternative to the hand-written SQL
checks in `insightiq_data_validation`, covering an overlapping but not
identical set of rules against `fact_orders`: `customer_key` and
`product_key` must not be null, `review_score` must fall within 1-5 for
at least 95% of non-null values, `price` must be >= 0, and `item_count`
must be >= 1. Triggered manually (`schedule=None`).

Reads `fact_orders` via `PostgresHook.get_sqlalchemy_engine()` + pandas,
then validates it with Great Expectations' lightweight ephemeral-context
`Batch.validate()` API — no persisted GX project directory, Datasource
YAML, or Checkpoint config, just an in-memory `EphemeralDataContext`
wrapping the DataFrame for the duration of the task. This is the closest
equivalent, in the `great_expectations` 1.18.2 pinned in
`requirements.txt`, to the older `PandasDataset` shortcut, which no
longer exists in this version of the library.

Prints a PASS/FAIL line per expectation with the unexpected/total count,
then raises if any expectation failed — every expectation here is a hard
gate, unlike `insightiq_data_validation`'s freight-outlier check, which
only warns.
""",
) as dag:

    validate = PythonOperator(
        task_id="run_ge_expectations",
        python_callable=run_ge_expectations,
    )
