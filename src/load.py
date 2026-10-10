"""Load the raw Amazon products and categories CSVs from data/raw/ with explicit dtypes.

Run `python -m src.load` to print a profile of both files.
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Nullable pandas dtypes so missing values stay missing instead of coercing ints to float.
PRODUCT_DTYPES = {
    "asin": "string",
    "title": "string",
    "imgUrl": "string",
    "productURL": "string",
    "stars": "Float64",
    "reviews": "Int64",
    "price": "Float64",
    "listPrice": "Float64",
    "category_id": "Int64",
    "isBestSeller": "boolean",
    "boughtInLastMonth": "Int64",
}

CATEGORY_DTYPES = {
    "id": "Int64",
    "category_name": "string",
}

# Only an empty field counts as missing. pandas' default NA list also includes strings
# like "NA", "None" and "null", which could be real title text.
READ_OPTS = {"keep_default_na": False, "na_values": [""]}


def _read(path: Path, dtypes: dict[str, str]) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    if header != list(dtypes):
        raise ValueError(f"{path.name}: expected columns {list(dtypes)}, got {header}")
    return pd.read_csv(path, dtype=dtypes, **READ_OPTS)


def load_products(path: Path | None = None) -> pd.DataFrame:
    """Load amazon_products.csv with explicit dtypes."""
    return _read(path or RAW_DIR / "amazon_products.csv", PRODUCT_DTYPES)


def load_categories(path: Path | None = None) -> pd.DataFrame:
    """Load amazon_categories.csv with explicit dtypes."""
    return _read(path or RAW_DIR / "amazon_categories.csv", CATEGORY_DTYPES)


def profile(df: pd.DataFrame, name: str) -> None:
    """Print row count, columns, dtypes, head and describe for a frame."""
    with pd.option_context("display.width", 200, "display.max_columns", None,
                           "display.max_colwidth", 40):
        print(f"\n===== {name}: {len(df):,} rows x {df.shape[1]} cols =====")
        print(df.columns)
        print(df.dtypes)
        print(df.head())
        print(df.describe(include="all").T)


if __name__ == "__main__":
    profile(load_products(), "amazon_products.csv")
    profile(load_categories(), "amazon_categories.csv")
