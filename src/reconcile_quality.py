"""Run sql/quality_rules.sql with DuckDB and reconcile it with the Python rules.

Compares per-rule counts, the exact set of rejected ASINs (with their rejected_by
values), and the status and similarity of every title override, not just totals. Run `python -m src.reconcile_quality` from the project root.
Writes outputs/quality_reconciliation.csv.
"""

import duckdb
import pandas as pd

from src.load import load_categories, load_products
from src.quality_rules import OUTPUT_DIR, ROOT, apply_title_overrides, load_title_overrides, run_all_rules, split_rejected

SQL_PATH = ROOT / "sql" / "quality_rules.sql"


def run_sql(sql: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (rule counts, rejected rows, override status) computed by DuckDB."""
    con = duckdb.connect()
    con.execute(f"SET file_search_path = '{ROOT.as_posix()}'")
    # DuckDB runs every statement in the script and returns the last one's result.
    counts = con.execute(sql or SQL_PATH.read_text(encoding="utf-8")).df()
    rejected = con.execute("SELECT asin, rejected_by FROM rejected").df()
    overrides = con.execute("SELECT asin, similarity, status FROM override_status").df()
    return counts, rejected, overrides


def compare_overrides(py_report: pd.DataFrame, sql_status: pd.DataFrame) -> pd.DataFrame:
    """One row per override with Python and SQL status and similarity side by side."""
    cmp = py_report[["asin", "similarity", "status"]].merge(sql_status, on="asin", how="outer", suffixes=("_py", "_sql"))
    cmp["match"] = (cmp["status_py"] == cmp["status_sql"]) & (
        (cmp["similarity_py"] - cmp["similarity_sql"]).abs().fillna(0) < 0.05)
    return cmp


def main() -> None:
    sql_counts, sql_rejected, sql_overrides = run_sql()

    products, override_report = apply_title_overrides(load_products(), load_title_overrides())
    ov = compare_overrides(override_report, sql_overrides)
    print(ov.to_string(index=False))
    print(f"title overrides matching: {int(ov['match'].sum())} of {len(ov)}")

    categories = load_categories()
    py_counts = run_all_rules(products, categories)
    _, py_rejected = split_rejected(products, categories)

    cols = ["rows_failed", "pct_of_rows", "rows_failed_in_kept"]
    rec = py_counts[["rule", "action", *cols]].merge(
        sql_counts[["rule", "action", *cols]], on="rule", how="outer", suffixes=("_py", "_sql"))
    rec["action_match"] = rec["action_py"] == rec["action_sql"]
    for c in cols:
        rec[f"{c}_diff"] = rec[f"{c}_py"] - rec[f"{c}_sql"]
    rec["match"] = rec["action_match"] & (rec[[f"{c}_diff" for c in cols]].abs() < 1e-9).all(axis=1)
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(rec[["rule", "action_py", "rows_failed_py", "rows_failed_sql", "pct_of_rows_py", "pct_of_rows_sql",
                   "rows_failed_in_kept_py", "rows_failed_in_kept_sql", "match"]].to_string(index=False))
    print(f"rule counts matching: {int(rec['match'].sum())} of {len(rec)}")

    py_set = dict(zip(py_rejected["asin"], py_rejected["rejected_by"]))
    sql_set = dict(zip(sql_rejected["asin"], sql_rejected["rejected_by"]))
    only_py, only_sql = py_set.keys() - sql_set.keys(), sql_set.keys() - py_set.keys()
    reason_diff = {a for a in py_set.keys() & sql_set.keys() if py_set[a] != sql_set[a]}
    print(f"rejected ASINs: python {len(py_set):,}, sql {len(sql_set):,}, in both {len(py_set.keys() & sql_set.keys()):,}; "
          f"only python {len(only_py)}, only sql {len(only_sql)}, same ASIN but different rejected_by {len(reason_diff)}")
    for label, asins in [("only python", only_py), ("only sql", only_sql), ("different rejected_by", reason_diff)]:
        for a in sorted(asins)[:10]:
            print(f"  {label}: {a} py={py_set.get(a)} sql={sql_set.get(a)}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    rec.to_csv(OUTPUT_DIR / "quality_reconciliation.csv", index=False)
    print(f"wrote {OUTPUT_DIR / 'quality_reconciliation.csv'}")


if __name__ == "__main__":
    main()
