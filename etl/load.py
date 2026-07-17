"""
Load cleaned DataFrames into Postgres.

Idempotent re-runs are handled at the pipeline level, not here: run_pipeline.py's
_truncate_all() truncates every table (RESTART IDENTITY CASCADE) before this
module's load_table() appends the freshly transformed data back in.
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
