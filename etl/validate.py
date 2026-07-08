"""
Validate referential integrity, uniqueness, and business rules in the warehouse.

Checks:
  1. NULL foreign keys (customer_key, product_key, seller_key)
  2. Orphaned foreign keys — values not present in the corresponding dim table
  3. Duplicate (order_id, product_key) in fact_orders
  4. Duplicate natural keys in dim_customer (customer_id) and dim_product (product_id)
  5. [WARN]  freight_value > price * 3 — suspicious outliers, not dropped
  6. [FAIL]  review_score outside 1–5 (NULLs are allowed)
  7. [FAIL]  delivered_date_key < order_date_key (delivery before purchase)

Run with: python -m etl.validate
"""
import pandas as pd
from sqlalchemy import text
from etl.load import get_engine

SAMPLE_SIZE = 5

FK_CHECKS = [
    ("customer_key", "dim_customer"),
    ("product_key",  "dim_product"),
    ("seller_key",   "dim_seller"),
]


def _read(engine, sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def check_nulls(engine) -> bool:
    """Return True if any NULL FK found."""
    null_cols = ", ".join(
        f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS {col}"
        for col, _ in FK_CHECKS
    )
    row = _read(engine, f"SELECT {null_cols} FROM fact_orders").iloc[0]
    ok = True
    for col, _ in FK_CHECKS:
        count = int(row[col])
        if count:
            print(f"  [FAIL] NULL {col}: {count:,} row(s)")
            sample = _read(
                engine,
                f"SELECT * FROM fact_orders WHERE {col} IS NULL LIMIT {SAMPLE_SIZE}",
            )
            print(sample.to_string(index=False))
            ok = False
        else:
            print(f"  [OK]   NULL {col}: 0")
    return ok


def check_orphans(engine) -> bool:
    """Return True if no orphaned FK found."""
    ok = True
    for col, dim_table in FK_CHECKS:
        dim_key = col  # dim PK has the same name
        sql = f"""
            SELECT f.*
            FROM fact_orders f
            LEFT JOIN {dim_table} d ON f.{col} = d.{dim_key}
            WHERE f.{col} IS NOT NULL
              AND d.{dim_key} IS NULL
        """
        count_sql = f"SELECT COUNT(*) AS n FROM ({sql}) sub"
        count = int(_read(engine, count_sql).iloc[0]["n"])
        if count:
            print(f"  [FAIL] Orphaned {col} → {dim_table}: {count:,} row(s)")
            sample = _read(engine, f"{sql} LIMIT {SAMPLE_SIZE}")
            print(sample.to_string(index=False))
            ok = False
        else:
            print(f"  [OK]   Orphaned {col} → {dim_table}: 0")
    return ok


def check_fact_duplicates(engine) -> bool:
    """Check for duplicate (order_id, product_key) in fact_orders."""
    sql = """
        SELECT order_id, product_key, COUNT(*) AS n
        FROM fact_orders
        GROUP BY order_id, product_key
        HAVING COUNT(*) > 1
    """
    count = int(_read(engine, f"SELECT COUNT(*) AS n FROM ({sql}) sub").iloc[0]["n"])
    if count:
        print(f"  [FAIL] Duplicate (order_id, product_key) in fact_orders: {count:,} group(s)")
        sample = _read(engine, f"{sql} ORDER BY n DESC LIMIT {SAMPLE_SIZE}")
        print(sample.to_string(index=False))
        return False
    print("  [OK]   Duplicate (order_id, product_key) in fact_orders: 0")
    return True


DIM_NATURAL_KEYS = [
    ("dim_customer", "customer_id"),
    ("dim_product",  "product_id"),
]


def check_dim_duplicates(engine) -> bool:
    """Check for duplicate natural keys in dimension tables."""
    ok = True
    for table, key_col in DIM_NATURAL_KEYS:
        sql = f"""
            SELECT {key_col}, COUNT(*) AS n
            FROM {table}
            GROUP BY {key_col}
            HAVING COUNT(*) > 1
        """
        count = int(_read(engine, f"SELECT COUNT(*) AS n FROM ({sql}) sub").iloc[0]["n"])
        if count:
            print(f"  [FAIL] Duplicate {key_col} in {table}: {count:,} value(s)")
            sample = _read(engine, f"{sql} ORDER BY n DESC LIMIT {SAMPLE_SIZE}")
            print(sample.to_string(index=False))
            ok = False
        else:
            print(f"  [OK]   Duplicate {key_col} in {table}: 0")
    return ok


def check_freight_outliers(engine) -> bool:
    """Warn (not fail) when freight_value > price * 3.

    These are suspicious but may be legitimate (bulky/heavy low-value items),
    so they are flagged for review rather than treated as hard errors.
    """
    sql = """
        SELECT order_id, product_key, price, freight_value,
               ROUND(freight_value / NULLIF(price, 0), 2) AS freight_ratio
        FROM fact_orders
        WHERE price > 0
          AND freight_value > price * 3
    """
    count_sql = f"SELECT COUNT(*) AS n FROM ({sql}) sub"
    count = int(_read(engine, count_sql).iloc[0]["n"])
    if count:
        print(f"  [WARN] freight_value > price * 3: {count:,} row(s) (flagged, not failed)")
        sample = _read(engine, f"{sql} ORDER BY freight_ratio DESC LIMIT {SAMPLE_SIZE}")
        print(sample.to_string(index=False))
    else:
        print("  [OK]   freight_value > price * 3: 0")
    return True  # always passes — outliers are warnings only


def check_review_score(engine) -> bool:
    """Fail if any non-NULL review_score falls outside 1–5."""
    sql = """
        SELECT order_id, review_score
        FROM fact_orders
        WHERE review_score IS NOT NULL
          AND review_score NOT BETWEEN 1 AND 5
    """
    count = int(_read(engine, f"SELECT COUNT(*) AS n FROM ({sql}) sub").iloc[0]["n"])
    if count:
        print(f"  [FAIL] review_score outside 1–5: {count:,} row(s)")
        sample = _read(engine, f"{sql} LIMIT {SAMPLE_SIZE}")
        print(sample.to_string(index=False))
        return False
    print("  [OK]   review_score outside 1–5: 0")
    return True


def check_delivery_before_order(engine) -> bool:
    """Fail if delivered_date_key < order_date_key (delivery predates purchase)."""
    sql = """
        SELECT order_id, order_date_key, delivered_date_key
        FROM fact_orders
        WHERE delivered_date_key IS NOT NULL
          AND order_date_key    IS NOT NULL
          AND delivered_date_key < order_date_key
    """
    count = int(_read(engine, f"SELECT COUNT(*) AS n FROM ({sql}) sub").iloc[0]["n"])
    if count:
        print(f"  [FAIL] delivered_date_key < order_date_key: {count:,} row(s)")
        sample = _read(engine, f"{sql} LIMIT {SAMPLE_SIZE}")
        print(sample.to_string(index=False))
        return False
    print("  [OK]   delivered_date_key < order_date_key: 0")
    return True


def main():
    engine = get_engine()

    print("=== NULL foreign-key check ===")
    nulls_ok = check_nulls(engine)

    print("\n=== Orphaned foreign-key check ===")
    orphans_ok = check_orphans(engine)

    print("\n=== Duplicate row check — fact_orders ===")
    fact_dupes_ok = check_fact_duplicates(engine)

    print("\n=== Duplicate natural-key check — dimension tables ===")
    dim_dupes_ok = check_dim_duplicates(engine)

    print("\n=== Business-rule checks ===")
    check_freight_outliers(engine)
    review_ok    = check_review_score(engine)
    delivery_ok  = check_delivery_before_order(engine)

    print()
    if nulls_ok and orphans_ok and fact_dupes_ok and dim_dupes_ok and review_ok and delivery_ok:
        print("All checks passed.")
    else:
        print("Validation FAILED — see details above.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
