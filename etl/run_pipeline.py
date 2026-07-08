"""
Orchestrates extract -> transform -> load.

Run with: python etl/run_pipeline.py
"""
import pandas as pd
from sqlalchemy import text
from etl.extract import extract_all
from etl.transform import (
    clean_orders, clean_products, clean_customers, clean_sellers,
    build_dim_date, build_fact_orders,
)
from etl.load import load_table, get_engine


def _assign_key(df, key_col):
    """Add a sequential surrogate key column starting at 1."""
    df = df.copy()
    df.insert(0, key_col, range(1, len(df) + 1))
    return df


def _truncate_all(engine):
    # Fact table first to satisfy FK constraints, then dims.
    with engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE fact_orders, dim_customer, dim_seller, dim_product, dim_date"
            " RESTART IDENTITY CASCADE"
        ))
        conn.execute(text("COMMIT"))


def main():
    print("Truncating existing data...")
    _truncate_all(get_engine())

    print("Extracting...")
    raw = extract_all()

    print("Transforming...")
    orders = clean_orders(raw["orders"])

    dim_customer = _assign_key(clean_customers(raw["customers"]), "customer_key")
    dim_seller   = _assign_key(clean_sellers(raw["sellers"]),     "seller_key")
    dim_product  = _assign_key(clean_products(raw["products"], raw["category_translation"]), "product_key")
    all_dates = pd.concat([
        orders["order_purchase_timestamp"],
        orders["order_delivered_customer_date"],
        orders["order_estimated_delivery_date"],
    ])
    dim_date = build_dim_date(all_dates.min(), all_dates.max())

    fact = build_fact_orders(orders, raw["order_items"], dim_customer, dim_product, dim_seller)

    print("Loading...")
    load_table(dim_date,     "dim_date",     if_exists="append")
    load_table(dim_customer, "dim_customer", if_exists="append")
    load_table(dim_seller,   "dim_seller",   if_exists="append")
    load_table(dim_product,  "dim_product",  if_exists="append")
    load_table(fact,         "fact_orders",  if_exists="append")

    print("Pipeline complete.")


if __name__ == "__main__":
    main()
