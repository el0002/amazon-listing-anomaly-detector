"""Derive brand from listing titles and measure accuracy against labels/brand_labels.csv.

The label sample is drawn per D26 (proportional to category size, from kept rows). `true_brand` is the
brand on the listing's Amazon page as Adri checked it (D35); `NO_BRAND` means none was found, and a blank
means not labeled yet (D27). Rows tagged DIFF_PRODUCT, LISTING_UNAVAILABLE or ASIN_INVALID are left out of
accuracy and counted separately (D36).

Run `python -m src.brand sample` to write the label sample for Adri (refuses to overwrite labels), and
`python -m src.brand score` to print accuracy and the misses (D30: rules may be tuned on these labels).
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from src.load import load_categories

ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = ROOT / "labels" / "brand_labels.csv"
LABEL_SAMPLE_SIZE = 100
LABEL_SAMPLE_SEED = 0
NO_BRAND = "NO_BRAND"
# A letter in any script (not a digit or underscore).
_HAS_LETTER = re.compile(r"[^\W\d_]")
# Tags Adri added after checking the live page; these rows have no page brand to score against (D36).
EXCLUDED_TAGS = ["DIFF_PRODUCT", "LISTING_UNAVAILABLE", "ASIN_INVALID"]


def extract_brand(title: str) -> str | None:
    """Return the brand implied by a listing title, or None if it can't be determined.

    v1: the first whitespace-separated word that contains a letter, so a leading year or count
    ("2022 HP 14\" Laptop") is skipped. v0 was the first word; v0 -> v1 is 36 -> 37 of 86 (D30).
    """
    if pd.isna(title):
        return None
    words = [w for w in str(title).split() if _HAS_LETTER.search(w)]
    return words[0] if words else None


def add_brand_column(products: pd.DataFrame) -> pd.DataFrame:
    """Return products with a derived `brand` column."""
    return products.assign(brand=products["title"].map(extract_brand).astype("string"))


def normalize_brand(brand) -> str:
    """Lowercase and drop everything but letters and digits in any script (D28)."""
    return "" if pd.isna(brand) else re.sub(r"[\W_]+", "", str(brand).lower())


def load_labels(path: Path = LABELS_PATH) -> pd.DataFrame:
    """Read the label file as UTF-8, keeping text like "NULL" as text. Stops on a non-UTF-8 byte
    instead of guessing the encoding."""
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        line = raw[:e.start].count(b"\n") + 1
        raise ValueError(f"{path.name} line {line}: byte {raw[e.start]:#x} is not UTF-8; re-save the file as UTF-8") from e
    return pd.read_csv(path, dtype="string", keep_default_na=False, encoding="utf-8")


def score_brands(labels: pd.DataFrame) -> pd.DataFrame:
    """Labels with `predicted`, a per-row `outcome` (correct, wrong, missed, invented, no_brand_ok,
    excluded or unlabeled; D27, D36) and `label_in_title` (the normalized label occurs in the
    normalized title: the most a title-only extractor can get, D35)."""
    out = labels.copy()
    out["predicted"] = out["title"].map(extract_brand).astype("string")
    truth = out["true_brand"].fillna("").str.strip()
    pred_norm, truth_norm = out["predicted"].map(normalize_brand), truth.map(normalize_brand)
    no_brand = truth.str.upper() == NO_BRAND
    out["outcome"] = "wrong"
    out.loc[pred_norm == truth_norm, "outcome"] = "correct"
    out.loc[~no_brand & (pred_norm == ""), "outcome"] = "missed"
    out.loc[no_brand & (pred_norm != ""), "outcome"] = "invented"
    out.loc[no_brand & (pred_norm == ""), "outcome"] = "no_brand_ok"
    out.loc[truth.str.upper().isin(EXCLUDED_TAGS), "outcome"] = "excluded"
    out.loc[truth == "", "outcome"] = "unlabeled"
    title_norm = out["title"].map(normalize_brand)
    out["label_in_title"] = [t != "" and t in x for x, t in zip(title_norm, truth_norm)]
    return out


def brand_accuracy(labels: pd.DataFrame) -> dict:
    """Accuracy over labels that name a brand, the invented-brand count on NO_BRAND labels (D27),
    rows left out per tag (D36), and how many brand labels appear in their title (ceiling, D35)."""
    scored = score_brands(labels)
    outcome = scored["outcome"]
    branded = outcome.isin(["correct", "wrong", "missed"])
    no_brand = outcome.isin(["invented", "no_brand_ok"])
    correct = int((outcome == "correct").sum())
    return {
        "labeled": int((outcome != "unlabeled").sum()),
        "unlabeled": int((outcome == "unlabeled").sum()),
        "branded": int(branded.sum()),
        "correct": correct,
        "accuracy": correct / branded.sum() if branded.any() else float("nan"),
        "no_brand": int(no_brand.sum()),
        "invented": int((outcome == "invented").sum()),
        "excluded": {tag: int((labels["true_brand"].str.strip().str.upper() == tag).sum()) for tag in EXCLUDED_TAGS},
        "label_in_title": int((branded & scored["label_in_title"]).sum()),
    }


def allocate_proportional(counts: pd.Series, n: int) -> pd.Series:
    """Split n slots across the index of `counts` in proportion to the counts (largest remainder).

    Each key gets floor(n * share); the slots left over go to the largest remainders, ties to the
    lower key (D26). Returns an int Series on the same index that sums to n.
    """
    exact = counts * n / counts.sum()
    quota = exact.astype(int)
    remainder = (exact - quota).rename("remainder").to_frame()
    remainder["key"] = remainder.index
    leftover = n - int(quota.sum())
    top = remainder.sort_values(["remainder", "key"], ascending=[False, True]).index[:leftover]
    quota[top] += 1
    return quota


def sample_for_labeling(products: pd.DataFrame, categories: pd.DataFrame,
                        n: int = LABEL_SAMPLE_SIZE, seed: int = LABEL_SAMPLE_SEED) -> pd.DataFrame:
    """Draw n titles for hand labeling, allocated by category share of `products` (D26).

    Returns asin, title, a blank true_brand, category_id and category_name.
    """
    quota = allocate_proportional(products["category_id"].value_counts().sort_index(), n)
    quota = quota[quota > 0]
    parts = [products[products["category_id"] == cat].sample(n=int(k), random_state=seed)
             for cat, k in quota.items()]
    sample = pd.concat(parts)[["asin", "title", "category_id"]]
    sample.insert(2, "true_brand", pd.Series("", index=sample.index, dtype="string"))
    names = categories.set_index("id")["category_name"]
    sample["category_name"] = sample["category_id"].map(names)
    return sample.reset_index(drop=True)


def write_label_sample(path: Path = LABELS_PATH) -> pd.DataFrame:
    """Write the label sample to `path` unless it already holds labels. Returns the sample."""
    from src.quality_rules import clean_products

    if path.exists():
        existing = pd.read_csv(path, dtype="string", keep_default_na=False)
        if "true_brand" in existing and (existing["true_brand"].str.strip() != "").any():
            raise FileExistsError(f"{path} already has labels; not overwriting")
    kept = clean_products()
    sample = sample_for_labeling(kept, load_categories())
    print(f"kept rows: {len(kept):,} in {kept['category_id'].nunique()} categories; "
          f"sample: {len(sample)} rows in {sample['category_id'].nunique()} categories; "
          f"duplicate ASINs in sample: {sample['asin'].duplicated().sum()}")
    sample.to_csv(path, index=False)
    print(f"wrote {path}")
    return sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["sample", "score"])
    args = parser.parse_args()
    # Titles include characters the Windows console code page can't print.
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "sample":
        write_label_sample()
    else:
        labels = load_labels()
        print(brand_accuracy(labels))
        scored = score_brands(labels)
        misses = scored[~scored["outcome"].isin(["correct", "no_brand_ok", "excluded", "unlabeled"])]
        with pd.option_context("display.width", 200, "display.max_colwidth", 70):
            print(misses[["asin", "true_brand", "predicted", "outcome", "label_in_title", "title"]].to_string(index=False))


if __name__ == "__main__":
    main()
