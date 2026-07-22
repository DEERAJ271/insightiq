"""
Starter tests — expand as etl/transform.py fills in.
"""

import pandas as pd
from etl.transform import build_dim_date


def test_build_dim_date_row_count():
    dim_date = build_dim_date(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-10"))
    assert len(dim_date) == 10


def test_build_dim_date_weekend_flag():
    dim_date = build_dim_date(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-07"))
    saturday = dim_date[dim_date["full_date"] == "2024-01-06"]
    assert bool(saturday["is_weekend"].iloc[0]) is True
