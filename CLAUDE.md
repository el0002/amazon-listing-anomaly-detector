# CLAUDE.md

## Project
Amazon Listing Anomaly Detector: a portfolio project that audits data quality and flags suspicious Amazon listings (possible counterfeits, inflated discounts, copycat relistings) in a 1.4M-row dataset. Built for a Data Analyst application at a brand-protection analytics company. Owner: Adri.

The core story of this project is **AI-assisted analysis with human validation**. Every piece of AI-generated logic must be checked, and mistakes must be documented, not hidden.

## Dataset
- Source: Kaggle `asaniczka/amazon-products-dataset-2023-1-4m-products` (scraped Sep 2023), downloaded with `kagglehub`.
- Expected files: `amazon_products.csv` (asin, title, imgUrl, productURL, stars, reviews, price, listPrice, category_id, isBestSeller, boughtInLastMonth) and `amazon_categories.csv` (id, category_name). Confirm the real schema before relying on it.
- No seller or brand column: brand is derived from titles.
- Confirmed: 1,426,337 products and 248 categories; columns match the list above (version 17, files dated 2024-02-17).
- Zero values, per the dataset description (decision D5 in `reports/decisions.md`): `stars = 0` means no ratings found; `reviews = 0` means no reviews found; `price = 0` means price unavailable; `listPrice` is the original price before discount, and `listPrice = 0` means no discount (price is the selling price).
- `boughtInLastMonth` is Amazon's own estimate of units sold in the past month, bucketed (0, 50, 100…, 100000); treat each value as the bottom of its bucket (D7).
- Time context (D7): scraped Sep 2023, so sales reflect Aug–Sep 2023. Back-to-school season and Labor Day (Sep 4, 2023) deals fall inside that window; Prime Day (mid-July 2023) and Prime Big Deal Days (Oct 10–11, 2023) fall outside it. Seasonal demand or deals can look like anomalies, which is one reason to benchmark within category.
- `reviews = 0` comes per category: 170 of 248 categories have 0 reviews on every rated listing. Don't treat review counts as comparable across categories.
- Single snapshot: anomalies are relative to category, not over time.
- Raw data lives in `data/raw/` and is never committed or modified.

## Stack
- Python (pandas, rapidfuzz) for rules and matching, in `src/`.
- DuckDB for SQL, querying CSV/parquet directly. Queries live in `sql/` as `.sql` files.
- Jupyter in `notebooks/` for exploration only; reusable logic goes in `src/`.
- Looker Studio for the dashboard, fed only by small summary CSVs in `outputs/`.

## Workstreams
1. **Data quality audit**: one named rule per check (zero price, zero listPrice, price > listPrice, duplicate ASIN, missing title, stars without reviews, unknown category_id). Report rows failed and % per rule in `reports/data_quality.md`. Rejected rows are saved, not dropped silently.
2. **Brand extraction**: derive brand from title. Measure accuracy against `labels/brand_labels.csv` (100 hand-labeled titles) before and after every change.
3. **Anomaly signals**, benchmarked within each category: price far below category median; discount far above category norm; near-duplicate titles under different ASINs; high boughtInLastMonth with very few reviews.
4. **Validation**: precision measured on a hand-checked sample of 50 flagged listings.

## Working rules
- **Log AI decisions.** Whenever you write non-trivial logic (a cleaning rule, threshold, regex, join, or matching method), add an entry to `reports/ai_validation_log.md` using the table format there. State what you assumed and how it can be checked.
- **Log human decisions.** When Adri decides a judgment call, record it in `reports/decisions.md` (question, options, decision, why, where applied). Add new judgment calls to its "Open questions" table with the evidence, and move them up once decided. Small defaults you choose without asking also go in, marked "AI default".
- **`reports/my_analysis.md` is Adri's own analysis.** When Adri replies in the session with their own analysis or definitions, add them to that file in Adri's words (dated), and fix any reference line they contradict. Don't add your own analysis there.
- **Read `reports/decisions.md` before writing any logic.** Decisions there override the plan in this file where they differ (e.g. which quality rules reject rows: D9).
- **End of session:** update the Status section below, then commit.
- **Show your checks.** After any transformation, print row counts before and after. When SQL and Python compute the same figure, reconcile them and report any difference.
- **Flag uncertainty instead of guessing.** If a threshold, definition, or schema detail is a judgment call, propose options with trade-offs and ask me. Don't pick silently.
- **Never fabricate results.** Numbers in reports and the README must come from code that was actually run. Never fill in hand labels or precision checks yourself; those are mine to do. Prepare the samples for me.
- **Don't edit `labels/`** except to create sample files for me to label.
- **Performance:** the data is ~1.4M rows. Use DuckDB for aggregates. Run fuzzy matching within categories, and on a sample first.
- **Commits:** small, frequent, conventional messages (`feat:`, `fix:`, `docs:`, `chore:`). Commit at the end of each work session.
- **Writing style for reports and README:** plain, specific, numbers first, explain the "why." No hype words.

## Timeline (3 days)
- Day 1: setup, download, profiling, quality rules (Python + SQL), `data_quality.md`.
- Day 2: brand extraction and accuracy, category baselines, anomaly signals.
- Day 3: precision check, summary exports, dashboard, README, `findings.md`.
If time runs short, cut near-duplicate titles first.

## Status
*Last updated: 2026-10-11, end of setup session (Day 0).*

**Done**
- Scaffold, venv (Python 3.11.9, pinned `requirements.txt`), git repo.
- Data downloaded with kagglehub (no login needed) and copied to `data/raw/`. `src/load.py` loads both files with explicit dtypes; profiled and reconciled against DuckDB (8 of 8 counts match).
- Decisions D1–D15 recorded in `reports/decisions.md`; no open questions.
- Title override for B00758A9CE in `overrides/title_overrides.csv`, confirmed by Adri (D13).
- `reports/ai_validation_log.md`: 3 entries (1 real caught AI error, #2).

**Next: Day 1**
1. `src/download.py`: kagglehub download + copy to `data/raw/`, so a fresh clone can get the data (only done by hand so far).
2. `src/quality_rules.py`: implement rules with the severities in D9; apply `overrides/title_overrides.csv` first; save rejected rows with the rule name to `outputs/`.
3. Same rules as SQL in `sql/`, run with DuckDB; reconcile counts with Python.
4. Write `reports/data_quality.md` (rows and % per rule, rejected vs counted, reconciliation).
5. Log the AI decisions in `ai_validation_log.md`; update this Status; commit.

Expected counts from profiling (re-check, don't copy): price > listPrice 451; zero price 32,772; zero listPrice 1,080,503; stars without reviews 999,480; missing title 1 before override, 0 after; duplicate ASIN 0; unknown category 0.

## Definition of done
- Fresh clone + `pip install -r requirements.txt` runs the pipeline end to end.
- README reports quality-rule failures, brand accuracy (before/after), and flag precision as numbers.
- `ai_validation_log.md` has at least 3 real caught errors.
