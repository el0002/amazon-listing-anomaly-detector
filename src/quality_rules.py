"""Named data quality rules. Each rule returns a boolean mask of rows that fail it.

Rules: zero price, zero listPrice, price > listPrice, duplicate ASIN, missing title,
stars without reviews, unknown category_id. Failing rows are saved, never dropped silently.

Which rules reject rows and which only count them follows decisions D9, D16-D18, D21-D23 in
reports/decisions.md. Every rule runs on all raw rows, after title overrides
are applied, so counts don't depend on rule order (D20).

Run `python -m src.quality_rules` to apply the rules and write the outputs.
"""

from pathlib import Path

import pandas as pd
from rapidfuzz.distance import Levenshtein

from src.load import load_categories, load_products

ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = ROOT / "overrides" / "title_overrides.csv"
OUTPUT_DIR = ROOT / "outputs"

# An override's raw_title must score at least this against the data's title to apply (D23).
OVERRIDE_MIN_SIMILARITY = 95


def load_title_overrides(path: Path = OVERRIDES_PATH) -> pd.DataFrame:
    """Load the title override file, keeping text like "NULL" and "-" as text."""
    return pd.read_csv(path, dtype="string", keep_default_na=False)


def _normalize_title(title) -> str:
    """Lowercase and collapse whitespace, as in sql/quality_rules.sql."""
    return "" if pd.isna(title) else " ".join(str(title).split()).lower()


def title_similarity(a, b) -> float:
    """Normalized Levenshtein similarity, 0-100, of two titles after _normalize_title (D23)."""
    return 100 * Levenshtein.normalized_similarity(_normalize_title(a), _normalize_title(b))


def apply_title_overrides(products: pd.DataFrame, overrides: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return products with override titles applied, plus a report of every override's status.

    An override applies only if `confirmed_by` is filled in (D18), its ASIN is in the data, and
    its `raw_title` scores at least OVERRIDE_MIN_SIMILARITY against the data's title (D21, D23).
    Status is one of: applied, unconfirmed, title_differs, asin_not_in_data. Anything not applied
    needs Adri's (re-)confirmation; the row then goes through the rules with its own title.
    """
    current = products.drop_duplicates("asin").set_index("asin")["title"]
    report = []
    for row in overrides.itertuples():
        in_data = row.asin in current.index
        data_title = current[row.asin] if in_data else pd.NA
        score = title_similarity(row.raw_title, data_title) if in_data else None
        if row.confirmed_by.strip() == "":
            status = "unconfirmed"
        elif not in_data:
            status = "asin_not_in_data"
        elif score < OVERRIDE_MIN_SIMILARITY:
            status = "title_differs"
        else:
            status = "applied"
        report.append({"asin": row.asin, "raw_title": row.raw_title, "data_title": data_title,
                       "similarity": None if score is None else round(score, 1), "status": status, "corrected_title": row.corrected_title})
    report = pd.DataFrame(report, columns=["asin", "raw_title", "data_title", "similarity", "status", "corrected_title"])
    applied = report[report["status"] == "applied"]
    out = products.copy()
    new_titles = out["asin"].map(applied.set_index("asin")["corrected_title"])
    out["title"] = new_titles.fillna(out["title"]).astype("string")
    return out, report


def zero_price(products: pd.DataFrame) -> pd.Series:
    """Rows where price == 0 (price unavailable, D5)."""
    return products["price"] == 0


def zero_list_price(products: pd.DataFrame) -> pd.Series:
    """Rows where listPrice == 0 (no discount, D5)."""
    return products["listPrice"] == 0


def price_above_list_price(products: pd.DataFrame) -> pd.Series:
    """Rows where price > listPrice and listPrice is set (> 0; 0 means no discount, D5)."""
    return (products["listPrice"] > 0) & (products["price"] > products["listPrice"])


def duplicate_asin(products: pd.DataFrame) -> pd.Series:
    """Rows whose ASIN appears more than once (every copy is marked, D20)."""
    return products["asin"].duplicated(keep=False)


def missing_title(products: pd.DataFrame) -> pd.Series:
    """Rows whose title is missing per D1/D16: null, blank, the text "NULL",
    no letters or digits in any script, or 1 character long."""
    title = products["title"].str.strip()
    # [^\W_] is a letter or digit in any script.
    no_alnum = ~title.str.contains(r"[^\W_]", regex=True)
    return (title.isna() | (title.str.upper() == "NULL") | no_alnum | (title.str.len() <= 1)).fillna(True)


def stars_without_reviews(products: pd.DataFrame) -> pd.Series:
    """Rows with a star rating but zero reviews."""
    return (products["stars"] > 0) & (products["reviews"] == 0)


def unknown_category_id(products: pd.DataFrame, categories: pd.DataFrame) -> pd.Series:
    """Rows whose category_id is not in the categories table (null counts as unknown)."""
    return ~products["category_id"].isin(categories["id"]).fillna(False)


# Rule name -> (function, action, description). "reject" removes the row; "count" keeps it.
# Functions take (products, categories).
RULES = {
    "missing_title": (lambda p, c: missing_title(p), "reject",
                      "Title empty, \"NULL\", no letters or digits, or 1 character, after confirmed overrides (D1, D16-D18)"),
    "price_above_list_price": (lambda p, c: price_above_list_price(p), "reject", "price > listPrice where listPrice > 0 (D9)"),
    "duplicate_asin": (lambda p, c: duplicate_asin(p), "reject", "ASIN appears more than once (D9)"),
    "unknown_category_id": (unknown_category_id, "reject", "category_id not in amazon_categories.csv (D9)"),
    "zero_price": (lambda p, c: zero_price(p), "count", "price = 0: price unavailable (D5, D9)"),
    "zero_list_price": (lambda p, c: zero_list_price(p), "count", "listPrice = 0: no discount (D5, D9)"),
    "stars_without_reviews": (lambda p, c: stars_without_reviews(p), "count", "stars > 0 and reviews = 0 (D5, D9)"),
}
REJECT_RULES = [name for name, (_, action, _) in RULES.items() if action == "reject"]


def rule_masks(products: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per rule, True where the row fails it."""
    return pd.DataFrame({name: fn(products, categories).astype(bool) for name, (fn, _, _) in RULES.items()})


def run_all_rules(products: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    """Run every rule and return a summary of rows failed and % per rule."""
    masks = rule_masks(products, categories)
    rejected = masks[REJECT_RULES].any(axis=1)
    return pd.DataFrame({
        "rule": list(RULES),
        "action": [RULES[n][1] for n in RULES],
        "rows_failed": [int(masks[n].sum()) for n in RULES],
        "pct_of_rows": [round(100 * masks[n].mean(), 4) for n in RULES],
        "rows_failed_in_kept": [int((masks[n] & ~rejected).sum()) for n in RULES],
        "description": [RULES[n][2] for n in RULES],
    })


def split_rejected(products: pd.DataFrame, categories: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (kept, rejected). Rejected rows carry a `rejected_by` column naming every rejecting rule they fail."""
    masks = rule_masks(products, categories)[REJECT_RULES]
    is_rejected = masks.any(axis=1)
    failed = masks[is_rejected]
    rejected_by = pd.Series([";".join(failed.columns[row]) for row in failed.to_numpy()],
                            index=failed.index, dtype="string")
    rejected = products[is_rejected].assign(rejected_by=rejected_by)
    return products[~is_rejected], rejected


def clean_products() -> pd.DataFrame:
    """Load the raw data, apply title overrides (D18, D21), and return the rows no rule rejects."""
    products, _ = apply_title_overrides(load_products(), load_title_overrides())
    kept, _ = split_rejected(products, load_categories())
    return kept


def main() -> None:
    raw, categories = load_products(), load_categories()
    print(f"raw rows: {len(raw):,}; categories: {len(categories):,}")

    products, override_report = apply_title_overrides(raw, load_title_overrides())
    print("title overrides by status:", override_report["status"].value_counts().to_dict())
    print(override_report[["asin", "raw_title", "data_title", "similarity", "status"]].to_string(index=False))
    needs_confirmation = override_report[override_report["status"] != "applied"]
    print(f"rows after overrides: {len(products):,}")

    summary = run_all_rules(products, categories)
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(summary.drop(columns="description").to_string(index=False))

    kept, rejected = split_rejected(products, categories)
    print(f"rejected: {len(rejected):,}; kept: {len(kept):,}; "
          f"kept + rejected = {len(kept) + len(rejected):,} (raw {len(raw):,})")
    print(rejected["rejected_by"].value_counts().to_string())

    OUTPUT_DIR.mkdir(exist_ok=True)
    rejected.to_csv(OUTPUT_DIR / "rejected_rows.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "quality_rule_counts.csv", index=False)
    needs_confirmation.to_csv(OUTPUT_DIR / "overrides_needing_confirmation.csv", index=False)
    print(f"wrote rejected_rows.csv, quality_rule_counts.csv and overrides_needing_confirmation.csv "
          f"({len(needs_confirmation)} rows) to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
