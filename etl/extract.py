"""
Extract raw CSV files into pandas DataFrames.

TODO (good first Claude Code task): point this at the actual dataset files
you drop into data/raw/ and add schema validation (column presence, dtypes).
"""
import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_csv(filename: str) -> pd.DataFrame:
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download the dataset into data/raw/ first."
        )
    return pd.read_csv(path)


def extract_all() -> dict[str, pd.DataFrame]:
    """
    Returns a dict of raw DataFrames keyed by logical name.
    Adjust filenames to match whatever dataset you're using.
    """
    return {
        "orders": load_csv("olist_orders_dataset.csv"),
        "customers": load_csv("olist_customers_dataset.csv"),
        "order_items": load_csv("olist_order_items_dataset.csv"),
        "products": load_csv("olist_products_dataset.csv"),
        "sellers": load_csv("olist_sellers_dataset.csv"),
        "payments": load_csv("olist_order_payments_dataset.csv"),
        "reviews": load_csv("olist_order_reviews_dataset.csv"),
        "category_translation": load_csv("product_category_name_translation.csv"),
    }


if __name__ == "__main__":
    data = extract_all()
    for name, df in data.items():
        print(f"{name}: {df.shape[0]} rows, {df.shape[1]} cols")
