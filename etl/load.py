"""
Load cleaned DataFrames into Postgres.

TODO (good Claude Code task): add upsert logic (ON CONFLICT DO UPDATE) so
re-running the pipeline is idempotent, instead of the naive replace below.
"""
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/insightiq")


def get_engine():
    return create_engine(DATABASE_URL)


def load_table(df: pd.DataFrame, table_name: str, if_exists: str = "append") -> None:
    engine = get_engine()
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    print(f"Loaded {len(df)} rows into {table_name}")
