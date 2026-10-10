"""Anomaly signals benchmarked within each category.

Signals: price far below category median, discount far above category norm,
near-duplicate titles under different ASINs, high boughtInLastMonth with very few reviews.
"""

import pandas as pd


def category_baselines(products: pd.DataFrame) -> pd.DataFrame:
    """Per-category price and discount statistics used as benchmarks."""
    raise NotImplementedError


def flag_low_price(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.Series:
    """Listings priced far below their category median."""
    raise NotImplementedError


def flag_high_discount(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.Series:
    """Listings with a discount far above their category norm."""
    raise NotImplementedError


def flag_near_duplicate_titles(products: pd.DataFrame) -> pd.DataFrame:
    """Pairs of near-identical titles under different ASINs, matched within category."""
    raise NotImplementedError


def flag_sales_review_mismatch(products: pd.DataFrame) -> pd.Series:
    """Listings with high boughtInLastMonth but very few reviews."""
    raise NotImplementedError


def sample_for_precision_check(flags: pd.DataFrame, n: int = 50, seed: int = 0) -> pd.DataFrame:
    """Random sample of flagged listings for hand checking."""
    raise NotImplementedError
