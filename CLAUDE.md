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
*Last updated: 2026-10-12, end of Day 1.*

**Done**
- Day 0: scaffold, venv (Python 3.11.9, pinned `requirements.txt`), git repo; `src/load.py` with explicit dtypes, profiled and reconciled against DuckDB (8 of 8 counts match).
- `src/download.py`: kagglehub download of the latest version (D19; latest = version 17 on 2026-10-12), copied to `data/raw/`; stops on a header change, warns on a row-count change. Tested on `data/raw/` and an empty folder; the network download itself is untested (kagglehub used its cache).
- `src/quality_rules.py`: 7 rules on all raw rows (D20), after title overrides (D18, D21, D23: confirmed + similarity >= 95). **453 rejected** (451 `price_above_list_price`, 2 `missing_title`), **1,425,884 kept**. Counted, kept: `zero_price` 32,772, `zero_list_price` 1,080,503, `stars_without_reviews` 999,480. Outputs: `outputs/rejected_rows.csv`, `quality_rule_counts.csv`, `overrides_needing_confirmation.csv` (empty). `clean_products()` returns the kept rows.
- `sql/quality_rules.sql` + `src/reconcile_quality.py`: SQL matches Python on 7 of 7 rule counts, the exact 453 rejected ASINs, and 3 of 3 override statuses (`outputs/quality_reconciliation.csv`).
- Missing titles widened by D16 (5 found): 3 recovered from Amazon and confirmed (B00758A9CE D13; B00IKIEKS2, B01HEJ3V9G D22); B08FM4JTW2 rejected (D17); B09314JYMX rejected (404, no archive).
- `reports/data_quality.md` written. Decisions D1-D24; no open questions.
- `reports/ai_validation_log.md`: 8 entries; real caught errors in #2, #6, #7, #8 (the Day 1 ones were caught by AI self-review, not by Adri).

- Committed to the project repo (`main`, no remote yet). `outputs/` files are committed, `rejected_rows.csv` included (D24).

**Next: Day 2**
1. Brand extraction (`src/brand.py`): measure accuracy on `labels/brand_labels.csv` before and after every change. 16 titles contain U+FFFD and may lose their brand.
2. Category baselines on the kept rows (`clean_products()`); leave `zero_price` rows out of price and discount signals (D9).
3. Anomaly signals in `src/anomalies.py`: low price vs category median; discount far above norm (D6, D14, D15: z-score among discounted listings, tiers z > 3 and 2 < z <= 3); near-duplicate titles (cut first if short on time); high sales with few reviews (D11, with a column marking whether the category has review data).
4. Open AI default to confirm with Adri: D15 skips categories with fewer than 30 discounted listings.
5. Log AI decisions; update this Status; commit.

Expected counts from Day 0 profiling, taken on all rows; re-check them on the kept rows, don't copy: 345,106 discounted listings across 247 categories (D14); 3,291 high-tier discount listings in the 236 categories with 30+ discounted listings (D15); 37,702 high-sales/few-reviews candidates, 32,099 in categories with no review data (D11).

## Definition of done
- Fresh clone + `pip install -r requirements.txt` runs the pipeline end to end.
- README reports quality-rule failures, brand accuracy (before/after), and flag precision as numbers.
- `ai_validation_log.md` has at least 3 real caught errors.
