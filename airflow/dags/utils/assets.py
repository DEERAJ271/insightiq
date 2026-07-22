"""
Shared Asset definitions (Airflow 3.x's renamed Datasets) — kept in one
place so a producer DAG's outlet and a consumer DAG's schedule reference
the exact same object rather than two separately-constructed Assets that
happen to share a URI (Airflow identifies assets by URI either way, but
importing one shared object avoids two sources of truth drifting apart).
"""

from airflow.providers.postgres.assets.postgres import create_asset

# create_asset() (not the bare Asset(uri=...) constructor) because the
# postgres provider's AIP-60 URI sanitizer requires
# postgres://host:port/database/schema/table — a bare
# "postgres://insightiq/fact_orders" fails to parse (host with no
# database/schema/table). host:port/database match the real connection
# insightiq_real_etl_dag.py uses (host.docker.internal:5544/insightiq).
FACT_ORDERS_LOADED = create_asset(
    host="host.docker.internal",
    port=5544,
    database="insightiq",
    schema="public",
    table="fact_orders",
)
