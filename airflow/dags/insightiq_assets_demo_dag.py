"""
Demonstrates Airflow 3.x's Asset feature (the rename of Airflow 2's
Datasets) as a second, differently-architected way to chain DAGs, next to
the `TriggerDagRunOperator` call `insightiq_real_etl` already uses to kick
off `insightiq_data_validation`.

An Asset is a URI-based identifier for a piece of data — here
`postgres://host.docker.internal:5544/insightiq/public/fact_orders` (see
`dags/utils/assets.py`, shared between this file and
`insightiq_real_etl_dag.py` so both reference the same object; built via
the postgres provider's `create_asset()` helper rather than a bare
`Asset(uri=...)`, since its AIP-60 URI sanitizer requires a full
host:port/database/schema/table path). A task declares it as an `outlet`
to mean "I produce/update
this asset when I succeed" (see `transform_task` in
`insightiq_real_etl_dag.py`); a DAG declares it in `schedule=[...]` to mean
"run me whenever any of these assets is updated." Neither side names the
other DAG anywhere.

TriggerDagRunOperator vs. Asset scheduling — the actual architectural
difference this module exists to show:

  * TriggerDagRunOperator (`insightiq_real_etl` -> `insightiq_data_validation`)
    is an explicit, point-to-point call. The producer DAG's code contains
    the consumer's `dag_id` literally — it knows exactly who it's calling,
    the same way a function call knows its callee. Adding a second
    consumer means editing the producer DAG to add a second
    TriggerDagRunOperator; removing a consumer means finding and deleting
    that operator from the producer's file.

  * Asset scheduling (`insightiq_real_etl`'s `transform_task` -> this
    DAG's `insightiq_post_load_asset_consumer`) is decoupled/pub-sub.
    `transform_task` only knows it produces `FACT_ORDERS_LOADED` — it has
    no idea this DAG exists, or how many other DAGs (if any) are also
    scheduled on that same asset. Adding a third, fourth, fifth consumer
    means writing new DAGs with that asset in their `schedule=[...]`;
    `insightiq_real_etl` never changes. The tradeoff is indirection: to
    find every consumer of an asset you have to search for who schedules
    on it (or use the Airflow UI's Assets view), rather than reading a
    linear list of trigger calls in the producer's own file.

Both mechanisms coexist in this project on purpose, not as a
migrate-away-from-the-old-way exercise: TriggerDagRunOperator is the right
tool when a producer needs to know its consumer ran (e.g.
`wait_for_completion=True` to block on the result), while Asset scheduling
is the right tool when a producer just needs to publish "this data
changed" and doesn't care who's listening.
"""

import sys

sys.path.insert(0, "/opt/insightiq")

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

from dags.utils.alerting import notify_failure
from dags.utils.assets import FACT_ORDERS_LOADED


def report_asset_triggered(**context):
    """
    Runs automatically whenever FACT_ORDERS_LOADED is updated — i.e.
    whenever insightiq_real_etl's transform_task succeeds — with no fixed
    cron schedule and no explicit call from that DAG naming this one.
    `triggering_asset_events` (available in the task context on an
    asset-scheduled run) carries which asset event(s) caused this DagRun,
    which is printed here mainly to make that decoupling concrete rather
    than just asserted in the docstring above.
    """
    events = context.get("triggering_asset_events")
    print(f"Triggered by asset event(s): {events}")
    print(
        "insightiq_post_load_asset_consumer running: fact_orders was just "
        "reloaded by insightiq_real_etl's transform_task."
    )


with DAG(
    dag_id="insightiq_post_load_asset_consumer",
    start_date=datetime(2026, 1, 1),
    # Asset-scheduled, not cron- or manually-triggered: a new DagRun is
    # created automatically each time FACT_ORDERS_LOADED is updated (i.e.
    # each time insightiq_real_etl's transform_task succeeds), with no
    # fixed cadence of its own.
    schedule=[FACT_ORDERS_LOADED],
    catchup=False,
    tags=["insightiq", "assets-demo"],
    default_args={"on_failure_callback": notify_failure},
    doc_md="""
### insightiq_post_load_asset_consumer

Lightweight DAG scheduled on the `FACT_ORDERS_LOADED` asset
(`postgres://host.docker.internal:5544/insightiq/public/fact_orders`)
rather than a fixed cron expression or a manual trigger — a new DagRun is
created automatically each time
`insightiq_real_etl`'s `transform_task` succeeds (see that task's
`outlets=[FACT_ORDERS_LOADED]`), with no explicit call from that DAG naming
this one.

See the module docstring in `insightiq_assets_demo_dag.py` for the full
contrast with the `TriggerDagRunOperator` call `insightiq_real_etl` already
uses to chain into `insightiq_data_validation`: that mechanism is an
explicit, point-to-point call (the producer's code names the consumer's
`dag_id`); asset scheduling is decoupled pub-sub (the producer only
declares what it produces, and has no idea this DAG — or any other
consumer of the same asset — exists).
""",
) as dag:

    report = PythonOperator(
        task_id="report_asset_triggered",
        python_callable=report_asset_triggered,
    )
