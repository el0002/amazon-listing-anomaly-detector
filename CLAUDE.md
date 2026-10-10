# CLAUDE.md

## Project
Amazon Listing Anomaly Detector: a portfolio project that audits data quality and flags suspicious Amazon listings (possible counterfeits, inflated discounts, copycat relistings) in a 1.4M-row dataset. Built for a Data Analyst application at a brand-protection analytics company. Owner: Adri.

The core story of this project is **AI-assisted analysis with human validation**. Every piece of AI-generated logic must be checked, and mistakes must be documented, not hidden.

## Dataset
- Source: Kaggle `asaniczka/amazon-products-dataset-2023-1-4m-products` (scraped Sep 2023), downloaded with `kagglehub`.
- Expected files: `amazon_products.csv` (asin, title, imgUrl, productURL, stars, reviews, price, listPrice, category_id, isBestSeller, boughtInLastMonth) and `amazon_categories.csv` (id, category_name). Confirm the real schema before relying on it.
- No seller or brand column: brand is derived from titles.
- `listPrice = 0` likely means "no list price," not a 100% discount.
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
- **`reports/my_analysis.md` is Adri's own analysis.** Don't edit it unless asked.
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

## Definition of done
- Fresh clone + `pip install -r requirements.txt` runs the pipeline end to end.
- README reports quality-rule failures, brand accuracy (before/after), and flag precision as numbers.
- `ai_validation_log.md` has at least 3 real caught errors.
