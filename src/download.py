"""Download the Kaggle dataset with kagglehub and copy the CSVs into data/raw/.

Run `python -m src.download` from the project root. No Kaggle login is needed.
It fetches the latest dataset version (D19). Version 17 was profiled on 2026-10-10; if a newer
version has different row counts, the script warns so the reports can be re-checked.
"""

import argparse
import shutil
from pathlib import Path

import duckdb
import kagglehub
import pandas as pd

from src.load import CATEGORY_DTYPES, PRODUCT_DTYPES, RAW_DIR

DATASET = "asaniczka/amazon-products-dataset-2023-1-4m-products"

# File name -> (expected columns, data rows in version 17, the version profiled on 2026-10-10).
EXPECTED = {
    "amazon_products.csv": (list(PRODUCT_DTYPES), 1_426_337),
    "amazon_categories.csv": (list(CATEGORY_DTYPES), 248),
}


def copy_files(src_dir: Path, dest_dir: Path, force: bool = False) -> None:
    """Copy the expected CSVs from src_dir to dest_dir, skipping same-size copies unless force."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED:
        src, dest = src_dir / name, dest_dir / name
        if not src.exists():
            raise FileNotFoundError(f"{name} not found in the download at {src_dir}")
        if dest.exists() and dest.stat().st_size == src.stat().st_size and not force:
            print(f"skip   {name}: already in {dest_dir} with the same size")
            continue
        shutil.copy2(src, dest)
        print(f"copied {name}: {src.stat().st_size:,} bytes")


def check_files(dest_dir: Path) -> None:
    """Fail if a CSV's header differs; warn if its row count differs from version 17."""
    con = duckdb.connect()
    for name, (columns, rows) in EXPECTED.items():
        path = dest_dir / name
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if header != columns:
            raise ValueError(f"{name}: expected columns {columns}, got {header}")
        n = con.execute("SELECT count(*) FROM read_csv(?, all_varchar = true)", [str(path)]).fetchone()[0]
        if n != rows:
            print(f"WARNING {name}: {n:,} rows, but version 17 had {rows:,}. "
                  "Reports were built on version 17; re-run the pipeline and re-check them.")
        else:
            print(f"ok     {name}: {n:,} rows, columns match")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=RAW_DIR, help="target folder (default data/raw/)")
    parser.add_argument("--force", action="store_true", help="copy even if a same-size file exists")
    args = parser.parse_args()

    src_dir = Path(kagglehub.dataset_download(DATASET))
    print(f"kagglehub path: {src_dir} (dataset version {src_dir.name})")
    copy_files(src_dir, args.dest, args.force)
    check_files(args.dest)


if __name__ == "__main__":
    main()
