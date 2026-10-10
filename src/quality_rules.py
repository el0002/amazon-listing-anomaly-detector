"""Named data quality rules. Each rule returns a boolean mask of rows that fail it.

Rules: zero price, zero listPrice, price > listPrice, duplicate ASIN, missing title,
stars without reviews, unknown category_id. Failing rows are saved, never dropped silently.
"""

import pandas as pd


def zero_price(products: pd.DataFrame) -> pd.Series:
    """Rows where price == 0."""
    raise NotImplementedError


def zero_list_price(products: pd.DataFrame) -> pd.Series:
    """Rows where listPrice == 0."""
    raise NotImplementedError


def price_above_list_price(products: pd.DataFrame) -> pd.Series:
    """Rows where price > listPrice (and listPrice is set)."""
    raise NotImplementedError


def duplicate_asin(products: pd.DataFrame) -> pd.Series:
    """Rows whose ASIN appears more than once."""
    raise NotImplementedError


def missing_title(products: pd.DataFrame) -> pd.Series:
    """Rows with a null or blank title."""
    raise NotImplementedError


def stars_without_reviews(products: pd.DataFrame) -> pd.Series:
    """Rows with a star rating but zero reviews."""
    raise NotImplementedError


def unknown_category_id(products: pd.DataFrame, categories: pd.DataFrame) -> pd.Series:
    """Rows whose category_id is not in the categories table."""
    raise NotImplementedError


def run_all_rules(products: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    """Run every rule and return a summary of rows failed and % per rule."""
    raise NotImplementedError
