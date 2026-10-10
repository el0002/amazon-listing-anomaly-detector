"""Derive brand from listing titles and measure accuracy against labels/brand_labels.csv."""

import pandas as pd


def extract_brand(title: str) -> str | None:
    """Return the brand implied by a listing title, or None if it can't be determined."""
    raise NotImplementedError


def add_brand_column(products: pd.DataFrame) -> pd.DataFrame:
    """Return products with a derived `brand` column."""
    raise NotImplementedError


def brand_accuracy(labels: pd.DataFrame) -> float:
    """Share of hand-labeled titles where extract_brand matches true_brand."""
    raise NotImplementedError
