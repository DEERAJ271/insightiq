"""
Orchestrates extract -> transform -> load.

Run with: python etl/run_pipeline.py [--mode full|incremental]
"""
import argparse
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


def _max_order_date_key(engine) -> int | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT MAX(order_date_key) FROM fact_orders")).scalar()


def _upsert_dim(engine, cleaned_df, id_col, key_col, table_name):
    """Insert only the rows in cleaned_df not already present in table_name
    (matched on id_col), assigning new surrogate keys after the current
    MAX(key_col). Returns an (id_col, key_col) DataFrame covering every row
    in cleaned_df — existing rows plus any newly inserted ones — for use
    as the join table when building fact rows.
    """
    existing = pd.read_sql(f"SELECT {id_col}, {key_col} FROM {table_name}", engine)

    new_rows = (
        cleaned_df[~cleaned_df[id_col].isin(existing[id_col])]
        .drop_duplicates(subset=id_col)
        .reset_index(drop=True)
    )

    if new_rows.empty:
        print(f"No new rows for {table_name}")
        return existing[[id_col, key_col]]

    start = (existing[key_col].max() if not existing.empty else 0) + 1
    new_rows = new_rows.copy()
    new_rows.insert(0, key_col, range(start, start + len(new_rows)))
    load_table(new_rows, table_name, if_exists="append")

    return pd.concat(
        [existing[[id_col, key_col]], new_rows[[id_col, key_col]]],
        ignore_index=True,
    )


def _upsert_dim_date(engine, needed_dates: pd.Series) -> None:
    needed_dates = needed_dates.dropna()
    if needed_dates.empty:
        print("No dates to add to dim_date")
        return

    candidate = build_dim_date(needed_dates.min(), needed_dates.max())
    existing_keys = pd.read_sql("SELECT date_key FROM dim_date", engine)["date_key"]
    new_dates = candidate[~candidate["date_key"].isin(existing_keys)]

    if new_dates.empty:
        print("No new rows for dim_date")
        return
    load_table(new_dates, "dim_date", if_exists="append")


def run_full():
    """Truncate every table and reload it from the source CSVs."""
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

    fact = build_fact_orders(orders, raw["order_items"], dim_customer, dim_product, dim_seller, raw["reviews"])

    print("Loading...")
    load_table(dim_date,     "dim_date",     if_exists="append")
    load_table(dim_customer, "dim_customer", if_exists="append")
    load_table(dim_seller,   "dim_seller",   if_exists="append")
    load_table(dim_product,  "dim_product",  if_exists="append")
    load_table(fact,         "fact_orders",  if_exists="append")

    print(f"Pipeline complete. Loaded {len(fact)} fact_orders row(s).")
    return len(fact)


def run_incremental():
    """High-water-mark load: only orders newer than the current
    MAX(order_date_key) in fact_orders are extracted, transformed, and
    inserted. Dim tables are never truncated — dim_customer, dim_seller,
    and dim_product only gain rows for genuinely new natural keys
    (customer_id/seller_id/product_id not already in the warehouse), and
    dim_date only gains rows for dates the new orders actually need.
    """
    engine = get_engine()

    hwm = _max_order_date_key(engine)
    print(f"High-water mark (MAX order_date_key in fact_orders): {hwm}")

    print("Extracting...")
    raw = extract_all()

    print("Transforming...")
    orders = clean_orders(raw["orders"])
    order_date_key = (
        orders["order_purchase_timestamp"]
        .dt.strftime("%Y%m%d")
        .where(orders["order_purchase_timestamp"].notna(), other=None)
        .astype("Int64")
    )

    new_orders = orders[order_date_key > hwm] if hwm is not None else orders
    print(f"{len(new_orders)} new order(s) found beyond the high-water mark.")

    if new_orders.empty:
        print("No new orders to load. Incremental run complete.")
        return 0

    new_order_ids = set(new_orders["order_id"])
    order_items = raw["order_items"][raw["order_items"]["order_id"].isin(new_order_ids)]

    orders_without_items = new_order_ids - set(order_items["order_id"])
    if orders_without_items:
        print(
            f"{len(orders_without_items)} of {len(new_order_ids)} new order(s) have no "
            f"order_items rows and will be dropped by build_fact_orders' inner join "
            f"(same rule run_full() applies): {sorted(orders_without_items)[:5]}"
            f"{'...' if len(orders_without_items) > 5 else ''}"
        )

    dim_customer_clean = clean_customers(raw["customers"])
    dim_seller_clean   = clean_sellers(raw["sellers"])
    dim_product_clean  = clean_products(raw["products"], raw["category_translation"])

    new_customer_ids = set(new_orders["customer_id"])
    new_seller_ids    = set(order_items["seller_id"])
    new_product_ids   = set(order_items["product_id"])

    print("Loading new dimension rows (if any)...")
    dim_customer = _upsert_dim(
        engine, dim_customer_clean[dim_customer_clean["customer_id"].isin(new_customer_ids)],
        "customer_id", "customer_key", "dim_customer",
    )
    dim_seller = _upsert_dim(
        engine, dim_seller_clean[dim_seller_clean["seller_id"].isin(new_seller_ids)],
        "seller_id", "seller_key", "dim_seller",
    )
    dim_product = _upsert_dim(
        engine, dim_product_clean[dim_product_clean["product_id"].isin(new_product_ids)],
        "product_id", "product_key", "dim_product",
    )

    all_dates = pd.concat([
        new_orders["order_purchase_timestamp"],
        new_orders["order_delivered_customer_date"],
        new_orders["order_estimated_delivery_date"],
    ])
    _upsert_dim_date(engine, all_dates)

    fact = build_fact_orders(new_orders, order_items, dim_customer, dim_product, dim_seller, raw["reviews"])

    print("Loading new fact_orders rows...")
    load_table(fact, "fact_orders", if_exists="append")

    print(f"Incremental run complete. Inserted {len(fact)} new fact_orders row(s).")
    return len(fact)


def main():
    parser = argparse.ArgumentParser(description="Run the InsightIQ ETL pipeline.")
    parser.add_argument(
        "--mode", choices=["full", "incremental"], default="full",
        help="full: truncate and reload every table (default). "
             "incremental: high-water-mark load of only new orders.",
    )
    args = parser.parse_args()

    if args.mode == "incremental":
        run_incremental()
    else:
        run_full()


if __name__ == "__main__":
    main()
