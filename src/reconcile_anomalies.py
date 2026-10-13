"""Reconcile the category baselines and signals in src/anomalies.py with sql/category_baselines.sql
and sql/anomaly_signals.sql.

Compares every baseline column for every category, and the exact set of flagged (listing, signal)
pairs with their tier and score, not just totals. Run `python -m src.reconcile_anomalies`
from the project root. Writes outputs/baseline_reconciliation.csv and outputs/signal_counts.csv.
"""

import duckdb
import numpy as np
import pandas as pd

from src.anomalies import all_flags, category_baselines
from src.quality_rules import OUTPUT_DIR, ROOT, clean_products

SQL_FILES = ["quality_rules.sql", "category_baselines.sql", "anomaly_signals.sql"]
COUNT_COLS = ["kept_rows", "priced_rows", "discounted_rows"]
FLOAT_COLS = ["median_price", "log_price_median", "log_price_mad", "discount_mean", "discount_std", "bought_p99"]
BOOL_COLS = ["has_review_data", "discount_eligible"]


def run_sql() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(category baselines, signal flags) computed by DuckDB."""
    con = duckdb.connect()
    con.execute(f"SET file_search_path = '{ROOT.as_posix()}'")
    for name in SQL_FILES:
        con.execute((ROOT / "sql" / name).read_text(encoding="utf-8"))
    return con.execute("SELECT * FROM category_baselines").df(), con.execute("SELECT * FROM signal_flags").df()


def compare_baselines(py: pd.DataFrame, sql: pd.DataFrame, rel_tol: float = 1e-9) -> pd.DataFrame:
    """One row per category with a match flag per column. Floats match within rel_tol; both null counts as a match."""
    cmp = py.merge(sql, on="category_id", how="outer", suffixes=("_py", "_sql"), indicator=True)
    for c in COUNT_COLS + BOOL_COLS:
        cmp[f"{c}_match"] = cmp[f"{c}_py"].astype("float64") == cmp[f"{c}_sql"].astype("float64")
    for c in FLOAT_COLS:
        a, b = cmp[f"{c}_py"].astype("float64"), cmp[f"{c}_sql"].astype("float64")
        cmp[f"{c}_match"] = np.isclose(a, b, rtol=rel_tol, atol=0) | (a.isna() & b.isna())
    match_cols = [f"{c}_match" for c in COUNT_COLS + FLOAT_COLS + BOOL_COLS]
    cmp["match"] = (cmp["_merge"] == "both") & cmp[match_cols].all(axis=1)
    return cmp


def compare_flags(py: pd.DataFrame, sql: pd.DataFrame, rel_tol: float = 1e-9) -> pd.DataFrame:
    """One row per (asin, signal) flagged by either engine, with tier and score side by side."""
    cmp = py.merge(sql, on=["asin", "signal"], how="outer", suffixes=("_py", "_sql"), indicator=True)
    cmp["tier_match"] = cmp["tier_py"] == cmp["tier_sql"]
    cmp["score_match"] = np.isclose(cmp["score_py"].astype("float64"), cmp["score_sql"].astype("float64"), rtol=rel_tol, atol=0)
    cmp["match"] = (cmp["_merge"] == "both") & cmp["tier_match"] & cmp["score_match"]
    return cmp


def signal_counts(flags: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """Listings and categories flagged per signal and tier, split by whether the category has review data (D11)."""
    f = flags.assign(has_review_data=flags["category_id"].map(baselines.set_index("category_id")["has_review_data"]))
    return (f.groupby(["signal", "tier"])
             .agg(listings=("asin", "size"), categories=("category_id", "nunique"),
                  in_categories_with_review_data=("has_review_data", "sum"))
             .reset_index())


def main() -> None:
    kept = clean_products()
    py = category_baselines(kept)
    sql, sql_flags = run_sql()
    print(f"kept rows: python {len(kept):,}, sql {int(sql['kept_rows'].sum()):,}; "
          f"categories: python {len(py)}, sql {len(sql)}")

    cmp = compare_baselines(py, sql)
    for c in COUNT_COLS + FLOAT_COLS + BOOL_COLS:
        print(f"  {c:<18} categories differing: {int((~cmp[f'{c}_match']).sum())}")
    print(f"categories matching on every column: {int(cmp['match'].sum())} of {len(cmp)}")

    for label, df in [("python", py), ("sql", sql)]:
        print(f"{label}: priced {int(df['priced_rows'].sum()):,}; discounted {int(df['discounted_rows'].sum()):,} "
              f"in {int((df['discounted_rows'] > 0).sum())} categories; eligible (30+) {int(df['discount_eligible'].sum())}; "
              f"with review data {int(df['has_review_data'].sum())}")

    flags = all_flags(kept, py)
    fc = compare_flags(flags, sql_flags)
    print(f"flags: python {len(flags):,}, sql {len(sql_flags):,}; only python {int((fc['_merge'] == 'left_only').sum())}, "
          f"only sql {int((fc['_merge'] == 'right_only').sum())}, tier differs {int((~fc['tier_match'] & (fc['_merge'] == 'both')).sum())}, "
          f"score differs {int((~fc['score_match'] & (fc['_merge'] == 'both')).sum())}; matching {int(fc['match'].sum()):,}")
    for label, row in fc[~fc["match"]].head(10).iterrows():
        print(f"  differs: {row['asin']} {row['signal']} py={row['tier_py']}/{row['score_py']} sql={row['tier_sql']}/{row['score_sql']}")
    s4 = flags[flags["signal"] == "sales_review_mismatch"]
    s4_sql = sql_flags[sql_flags["signal"] == "sales_review_mismatch"].set_index("asin")["has_review_data"]
    print(f"has_review_data differing on sales flags: {int((s4.set_index('asin')['has_review_data'] != s4_sql.reindex(s4['asin'])).sum())}")
    counts = signal_counts(flags, py)
    print(counts.to_string(index=False))
    print(f"distinct listings with any flag: {flags['asin'].nunique():,}; with 2+ signals: "
          f"{int((flags.groupby('asin')['signal'].nunique() >= 2).sum()):,}")
    low = py[py["priced_rows"] > 0]
    print(f"categories with log-price MAD = 0 (no low-price z-scores): {int((low['log_price_mad'] == 0).sum())}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    cmp.drop(columns="_merge").to_csv(OUTPUT_DIR / "baseline_reconciliation.csv", index=False)
    counts.to_csv(OUTPUT_DIR / "signal_counts.csv", index=False)
    print(f"wrote {OUTPUT_DIR / 'baseline_reconciliation.csv'} and {OUTPUT_DIR / 'signal_counts.csv'}")


if __name__ == "__main__":
    main()
