"""Load the raw Amazon products and categories CSVs from data/raw/ with explicit dtypes."""

from pathlib import Path

import pandas as pd


def load_products(path: Path | None = None) -> pd.DataFrame:
    """Load amazon_products.csv with explicit dtypes."""
    raise NotImplementedError


def load_categories(path: Path | None = None) -> pd.DataFrame:
    """Load amazon_categories.csv with explicit dtypes."""
    raise NotImplementedError
