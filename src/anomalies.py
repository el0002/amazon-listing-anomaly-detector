"""Anomaly signals benchmarked within each category.

Signals: price far below category median, discount far above category norm,
near-duplicate titles under different ASINs, high boughtInLastMonth with very few reviews.
Thresholds follow reports/decisions.md: D6, D9, D11, D14, D15, D29, D31, D32, D33.

Each flag_* function returns one row per flagged listing: asin, category_id, signal, tier, score.
"""

import numpy as np
import pandas as pd

from src.quality_rules import _normalize_title

# A category needs at least this many discounted listings for the discount signal (D15, D29).
MIN_DISCOUNTED_LISTINGS = 30
# Discount z-score tiers among discounted listings: high z > 3, medium 2 < z <= 3 (D15).
DISCOUNT_Z_HIGH, DISCOUNT_Z_MEDIUM = 3.0, 2.0
# Robust z-score of log price below this is "far below the category median" (D31).
LOW_PRICE_Z = -3.0
# 1.4826 x MAD estimates the standard deviation for normal data (D31, AI default).
MAD_SCALE = 1.4826
# boughtInLastMonth at or above this category percentile counts as high sales (D32).
SALES_PERCENTILE = 0.99

FLAG_COLUMNS = ["asin", "category_id", "signal", "tier", "score"]


def discount(products: pd.DataFrame) -> pd.Series:
    """Discount as a share of list price (D6): (listPrice - price) / listPrice when listPrice > 0,
    0 when listPrice = 0 (no discount, D5), missing when price = 0 (price unavailable, D9)."""
    price, list_price = products["price"].astype("float64"), products["listPrice"].astype("float64")
    d = ((list_price - price) / list_price).where(list_price > 0, 0.0)
    return d.where(price > 0)


def category_baselines(products: pd.DataFrame) -> pd.DataFrame:
    """Per-category price, discount and sales statistics used as benchmarks, one row per category_id.

    Takes kept rows (clean_products()). Price stats use price > 0 only (D9); discount mean and
    std use discounted listings only (discount > 0, D14), std with ddof=1 as in DuckDB's stddev.
    Log-price median and MAD feed the low-price signal (D31); bought_p99 the sales signal (D32).
    """
    df = pd.DataFrame({
        "category_id": products["category_id"],
        "price": products["price"].astype("float64").where(products["price"] > 0),
        "discount": discount(products),
        "has_reviews": products["reviews"] > 0,
        "bought": products["boughtInLastMonth"].astype("float64"),
    })
    df["discounted"] = df["discount"].where(df["discount"] > 0)
    df["log_price"] = np.log(df["price"])
    g = df.groupby("category_id")
    log_median = g["log_price"].median()
    df["log_abs_dev"] = (df["log_price"] - df["category_id"].map(log_median)).abs()
    out = pd.DataFrame({
        "kept_rows": g.size(),
        "priced_rows": g["price"].count(),
        "median_price": g["price"].median(),
        "log_price_median": log_median,
        "log_price_mad": df.groupby("category_id")["log_abs_dev"].median(),
        "discounted_rows": g["discounted"].count(),
        "discount_mean": g["discounted"].mean(),
        "discount_std": g["discounted"].std(ddof=1),
        "bought_p99": g["bought"].quantile(SALES_PERCENTILE),
        "has_review_data": g["has_reviews"].any().astype(bool),
    })
    out["discount_eligible"] = out["discounted_rows"] >= MIN_DISCOUNTED_LISTINGS
    return out.reset_index()


def _per_row(products: pd.DataFrame, baselines: pd.DataFrame, column: str) -> pd.Series:
    """The category baseline `column` aligned to each listing."""
    return products["category_id"].map(baselines.set_index("category_id")[column])


def _flags(products: pd.DataFrame, mask: pd.Series, signal: str, tier, score: pd.Series) -> pd.DataFrame:
    """Flag rows for the listings where mask is True."""
    mask = mask.fillna(False).astype(bool)
    out = pd.DataFrame({"asin": products["asin"], "category_id": products["category_id"],
                        "signal": signal, "tier": tier, "score": score})
    return out[mask].reset_index(drop=True)


def low_price_z(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.Series:
    """Robust z-score of log price within category (D31); missing for price = 0 or a category with MAD 0."""
    price = products["price"].astype("float64").where(products["price"] > 0)
    scale = MAD_SCALE * _per_row(products, baselines, "log_price_mad")
    return (np.log(price) - _per_row(products, baselines, "log_price_median")) / scale.where(scale > 0)


def flag_low_price(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """Listings priced far below their category median: robust z of log price < -3 (D31)."""
    z = low_price_z(products, baselines)
    return _flags(products, z < LOW_PRICE_Z, "low_price", "high", z)


def discount_z(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.Series:
    """z-score of discount among discounted listings in categories with 30+ of them (D14, D15, D29)."""
    d = discount(products)
    eligible = _per_row(products, baselines, "discount_eligible").eq(True)
    z = (d - _per_row(products, baselines, "discount_mean")) / _per_row(products, baselines, "discount_std")
    return z.where((d > 0) & eligible)


def flag_high_discount(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """Listings with a discount far above their category norm: high z > 3, medium 2 < z <= 3 (D15)."""
    z = discount_z(products, baselines)
    tier = pd.Series(np.where(z > DISCOUNT_Z_HIGH, "high", "medium"), index=z.index)
    return _flags(products, z > DISCOUNT_Z_MEDIUM, "high_discount", tier, z)


def flag_sales_review_mismatch(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """Listings with boughtInLastMonth at or above the category's 99th percentile (and > 0) and
    reviews = 0 (D11, D32). Carries has_review_data for the category (D11)."""
    bought = products["boughtInLastMonth"].astype("float64")
    hit = (bought >= _per_row(products, baselines, "bought_p99")) & (bought > 0) & (products["reviews"] == 0)
    out = _flags(products, hit, "sales_review_mismatch", "high", bought)
    out["has_review_data"] = _per_row(out, baselines, "has_review_data").astype(bool)
    return out


def flag_near_duplicate_titles(products: pd.DataFrame) -> pd.DataFrame:
    """Listings whose title, lowercased with whitespace collapsed, is shared by another ASIN in the
    same category (D33). Score is the number of ASINs sharing that title in the category."""
    title = products["title"].map(_normalize_title)
    group_size = title.groupby([products["category_id"], title]).transform("size")
    return _flags(products, group_size >= 2, "near_duplicate_title", "high", group_size.astype("float64"))


def all_flags(products: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """Flags from every signal, one row per (listing, signal)."""
    return pd.concat([flag_low_price(products, baselines), flag_high_discount(products, baselines),
                      flag_near_duplicate_titles(products), flag_sales_review_mismatch(products, baselines)],
                     ignore_index=True)


def sample_for_precision_check(flags: pd.DataFrame, n: int = 50, seed: int = 0) -> pd.DataFrame:
    """Random sample of flagged listings for hand checking."""
    raise NotImplementedError
