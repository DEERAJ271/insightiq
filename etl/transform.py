"""
Clean and reshape raw DataFrames into the star schema defined in sql/schema.sql.

TODO (good Claude Code task): add data quality assertions (e.g. no negative
prices, valid state codes) — etl/validate.py currently checks referential
integrity, freight outliers, and review-score range, but not these.
"""

import pandas as pd


def build_dim_date(min_date: pd.Timestamp, max_date: pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(min_date, max_date, freq="D")
    return pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "full_date": dates,
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "day": dates.day,
            "day_of_week": dates.dayofweek,
            "is_weekend": dates.dayofweek >= 5,
        }
    )


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    orders = orders.copy()
    date_cols = [c for c in orders.columns if "date" in c or "timestamp" in c]
    for col in date_cols:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")
    return orders


def clean_products(
    products: pd.DataFrame, category_translation: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Map olist_products_dataset → dim_product columns.

    If category_translation (product_category_name_translation.csv) is supplied,
    Portuguese category names are replaced with their English equivalents before
    mapping to the 'category' column. Products whose Portuguese name has no
    translation entry keep the original Portuguese name rather than becoming NULL.
    """
    df = products.copy()
    df = df.dropna(subset=["product_id"])
    df = df.drop_duplicates(subset=["product_id"])

    if category_translation is not None:
        trans = category_translation.set_index("product_category_name")[
            "product_category_name_english"
        ]
        df["product_category_name"] = (
            df["product_category_name"].map(trans).fillna(df["product_category_name"])
        )

    df = df.rename(
        columns={
            "product_category_name": "category",
            "product_weight_g": "weight_g",
            "product_length_cm": "length_cm",
            "product_height_cm": "height_cm",
            "product_width_cm": "width_cm",
        }
    )
    return df[
        ["product_id", "category", "weight_g", "length_cm", "height_cm", "width_cm"]
    ].reset_index(drop=True)


def clean_customers(customers: pd.DataFrame) -> pd.DataFrame:
    """Map olist_customers_dataset → dim_customer columns.

    customer_id is the FK used in orders, so we deduplicate on it (not
    customer_unique_id, which tracks the same person across multiple orders).
    city/state are title-cased for consistency.
    """
    df = customers.copy()
    df = df.dropna(subset=["customer_id"])
    df = df.drop_duplicates(subset=["customer_id"])
    df = df.rename(
        columns={
            "customer_city": "city",
            "customer_state": "state",
        }
    )
    df["city"] = df["city"].str.title()
    df["country"] = "Brazil"
    return df[["customer_id", "city", "state", "country"]].reset_index(drop=True)


def clean_sellers(sellers: pd.DataFrame) -> pd.DataFrame:
    """Map olist_sellers_dataset → dim_seller columns."""
    df = sellers.copy()
    df = df.dropna(subset=["seller_id"])
    df = df.drop_duplicates(subset=["seller_id"])
    df = df.rename(
        columns={
            "seller_city": "city",
            "seller_state": "state",
        }
    )
    df["city"] = df["city"].str.title()
    return df[["seller_id", "city", "state"]].reset_index(drop=True)


def build_fact_orders(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_seller: pd.DataFrame,
    reviews: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join raw order + item data with dimension surrogate keys → fact_orders.

    orders          : cleaned olist_orders_dataset (from clean_orders)
    order_items     : raw olist_order_items_dataset
    dim_customer    : dim_customer with customer_key column (from DB or serial)
    dim_product     : dim_product with product_key column
    dim_seller      : dim_seller with seller_key column
    reviews         : raw olist_order_reviews_dataset, or None to leave
                      review_score as NULL

    payment_type and payment_installments are not present in these five
    source files; they are left as NaN to be filled by a later enrichment
    step (olist_order_payments dataset). review_score comes from `reviews`
    when supplied; some orders have more than one review submission (e.g.
    resubmitted reviews), so the most recent one per order_id is kept.
    """
    # --- aggregate order_items to one row per (order_id, product_id, seller_id) ---
    # item_count captures how many line-item rows collapsed into this fact row.
    # payment_installments and review_score are order-level (not line-item) fields,
    # so MAX is used to propagate a single non-null value after grouping.
    items = order_items.copy()
    items["price"] = pd.to_numeric(items["price"], errors="coerce")
    items["freight_value"] = pd.to_numeric(items["freight_value"], errors="coerce")

    items_agg = items.groupby(
        ["order_id", "product_id", "seller_id"], as_index=False
    ).agg(
        price=("price", "sum"),
        freight_value=("freight_value", "sum"),
        item_count=("order_item_id", "count"),
    )

    # --- join aggregated items with order-level fields ---
    fact = orders.merge(items_agg, on="order_id", how="inner")

    # --- attach surrogate keys ---
    fact = fact.merge(
        dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left"
    )
    fact = fact.merge(
        dim_product[["product_id", "product_key"]], on="product_id", how="left"
    )
    fact = fact.merge(
        dim_seller[["seller_id", "seller_key"]], on="seller_id", how="left"
    )

    # --- date keys (YYYYMMDD int, NaT → None) ---
    def to_date_key(series: pd.Series) -> pd.Series:
        return (
            series.dt.strftime("%Y%m%d")
            .where(series.notna(), other=None)
            .astype("Int64")
        )

    fact["order_date_key"] = to_date_key(fact["order_purchase_timestamp"])
    fact["delivered_date_key"] = to_date_key(fact["order_delivered_customer_date"])
    fact["estimated_date_key"] = to_date_key(fact["order_estimated_delivery_date"])

    # --- payment fields: placeholder, filled by a later enrichment step ---
    fact["payment_type"] = None
    fact["payment_installments"] = None

    # --- review_score: keep the most recent submission per order_id ---
    # review_score is SMALLINT, and some orders have more than one review
    # submission with genuinely different scores (resubmissions), so we take
    # the latest by review_creation_date (tie-broken by review_answer_timestamp)
    # rather than averaging, which would produce non-integer values.
    if reviews is not None:
        r = reviews.copy()
        r["review_creation_date"] = pd.to_datetime(
            r["review_creation_date"], errors="coerce"
        )
        r["review_answer_timestamp"] = pd.to_datetime(
            r["review_answer_timestamp"], errors="coerce"
        )
        r["review_score"] = pd.to_numeric(r["review_score"], errors="coerce")
        r = r.sort_values(["review_creation_date", "review_answer_timestamp"])
        reviews_latest = r.drop_duplicates(subset="order_id", keep="last")[
            ["order_id", "review_score"]
        ]
        fact = fact.merge(reviews_latest, on="order_id", how="left")
    else:
        fact["review_score"] = None

    return fact[
        [
            "order_id",
            "customer_key",
            "product_key",
            "seller_key",
            "order_date_key",
            "delivered_date_key",
            "estimated_date_key",
            "order_status",
            "item_count",
            "price",
            "freight_value",
            "payment_type",
            "payment_installments",
            "review_score",
        ]
    ].reset_index(drop=True)
