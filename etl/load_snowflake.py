"""
Load cleaned DataFrames into Snowflake — a parallel loader to etl/load.py,
targeting a second warehouse alongside (not instead of) Postgres.

STATUS: UNTESTED against a live Snowflake account. No SNOWFLAKE_* credentials
are configured in this environment, so nothing in this module has been run
against a real connection. It's written to match the documented
snowflake-sqlalchemy API (see https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy),
but the first real run against an actual account should be treated as the
real test of this integration pattern, not a formality — in particular,
watch for:
  - Snowflake's case-sensitivity rules: unquoted identifiers are folded to
    UPPERCASE, so table/column names created by pandas.to_sql() may not
    match what you expect when queried back from a Snowflake client that
    quotes identifiers differently.
  - The connecting role needs CREATE TABLE (for if_exists="replace") or
    INSERT (for if_exists="append") privileges on SNOWFLAKE_SCHEMA.
  - to_sql()'s default INSERT-per-row behavior is slow for large frames;
    a real integration should consider pandas.io.sql's `method="multi"`
    or Snowflake's own write_pandas() bulk-load helper instead, once this
    is validated against real data volumes.

Reads connection details from these env vars (see .env.example):
    SNOWFLAKE_ACCOUNT    e.g. "xy12345.us-east-1" (required)
    SNOWFLAKE_USER       (required)
    SNOWFLAKE_PASSWORD   (required)
    SNOWFLAKE_WAREHOUSE  (required)
    SNOWFLAKE_DATABASE   (required)
    SNOWFLAKE_SCHEMA     (required)
    SNOWFLAKE_ROLE       (optional)
"""
import os
import pandas as pd
from sqlalchemy import create_engine
from snowflake.sqlalchemy import URL
from dotenv import load_dotenv

load_dotenv()

_REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Snowflake loading requires all of "
            f"{', '.join(_REQUIRED_ENV_VARS)} in .env (SNOWFLAKE_ROLE is optional)."
        )
    return value


def get_engine():
    """Build a Snowflake SQLAlchemy engine from SNOWFLAKE_* env vars.

    Uses snowflake.sqlalchemy.URL() rather than hand-building a connection
    string — it applies the escaping/encoding rules the Snowflake dialect
    expects for account, user, and password.
    """
    return create_engine(URL(
        account=_require_env("SNOWFLAKE_ACCOUNT"),
        user=_require_env("SNOWFLAKE_USER"),
        password=_require_env("SNOWFLAKE_PASSWORD"),
        warehouse=_require_env("SNOWFLAKE_WAREHOUSE"),
        database=_require_env("SNOWFLAKE_DATABASE"),
        schema=_require_env("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    ))


def load_table(df: pd.DataFrame, table_name: str, if_exists: str = "append") -> None:
    engine = get_engine()
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    print(f"Loaded {len(df)} rows into Snowflake table {table_name}")
