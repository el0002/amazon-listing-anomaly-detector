# AI Validation Log

Every AI-generated piece of logic, how it was checked, and what was wrong.

| # | Date | AI task | What it produced | How it was checked | What was wrong | Fix and result |
|---|------|---------|------------------|--------------------|----------------|----------------|
| 1 | 2026-10-10 | Loader dtypes and NA handling (`src/load.py`) | Explicit nullable dtypes; only empty fields read as missing (`keep_default_na=False`), so strings like "NA"/"None"/"NULL" stay as text. Header checked against the expected column list. | Counted NA-like title strings in the raw CSV with DuckDB (all columns read as text): 1 row. Reconciled 8 profile counts (rows, zero price, zero listPrice, price > listPrice, duplicate ASIN, missing title, stars without reviews, unknown category) between DuckDB and the pandas loader: all 8 match. | Not an error yet, but the choice changes a result: ASIN B00758A9CE has title "NULL". pandas defaults would count it as a missing title; this loader counts 0 missing titles. | Open: the `missing_title` rule should decide whether "NULL" counts as missing (decision pending from Adri). Loader keeps raw text either way. |
