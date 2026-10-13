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
- **End of session:** update the Status section below, then propose commit messages for Adri (D25).
- **Show your checks.** After any transformation, print row counts before and after. When SQL and Python compute the same figure, reconcile them and report any difference.
- **Flag uncertainty instead of guessing.** If a threshold, definition, or schema detail is a judgment call, propose options with trade-offs and ask me. Don't pick silently.
- **Never fabricate results.** Numbers in reports and the README must come from code that was actually run. Never fill in hand labels or precision checks yourself; those are mine to do. Prepare the samples for me.
- **Don't edit `labels/`** except to create sample files for me to label.
- **Performance:** the data is ~1.4M rows. Use DuckDB for aggregates. Run fuzzy matching within categories, and on a sample first.
- **Commits are Adri's (D25).** Never run `git commit` or `git push`, and never add a Co-Authored-By trailer. Leave changes uncommitted; at the end of a session, propose small conventional commits (`feat:`, `fix:`, `docs:`, `chore:`) with the files that belong in each, for Adri to review, commit and push. Committing is Adri's human-in-the-loop sign-off on the AI-assisted work.
- **Writing style for reports and README:** plain, specific, numbers first, explain the "why." No hype words.

## Timeline (3 days)
- Day 1: setup, download, profiling, quality rules (Python + SQL), `data_quality.md`.
- Day 2: brand extraction and accuracy, category baselines, anomaly signals.
- Day 3: precision check, summary exports, dashboard, README, `findings.md`.
If time runs short, cut near-duplicate titles first.

## Status
*Last updated: 2026-10-13, end of Day 2.*

**Done: Day 1**
- Day 0: scaffold, venv (Python 3.11.9, pinned `requirements.txt`), git repo; `src/load.py` with explicit dtypes, profiled and reconciled against DuckDB (8 of 8 counts match).
- `src/download.py`: kagglehub download of the latest version (D19; latest = version 17 on 2026-10-12), copied to `data/raw/`; stops on a header change, warns on a row-count change. Tested on `data/raw/` and an empty folder; the network download itself is untested (kagglehub used its cache).
- `src/quality_rules.py`: 7 rules on all raw rows (D20), after title overrides (D18, D21, D23: confirmed + similarity >= 95). **453 rejected** (451 `price_above_list_price`, 2 `missing_title`), **1,425,884 kept**. Counted, kept: `zero_price` 32,772, `zero_list_price` 1,080,503, `stars_without_reviews` 999,480. Outputs: `outputs/rejected_rows.csv`, `quality_rule_counts.csv`, `overrides_needing_confirmation.csv` (empty). `clean_products()` returns the kept rows.
- `sql/quality_rules.sql` + `src/reconcile_quality.py`: SQL matches Python on 7 of 7 rule counts, the exact 453 rejected ASINs, and 3 of 3 override statuses (`outputs/quality_reconciliation.csv`).
- Missing titles widened by D16 (5 found): 3 recovered from Amazon and confirmed (B00758A9CE D13; B00IKIEKS2, B01HEJ3V9G D22); B08FM4JTW2 rejected (D17); B09314JYMX rejected (404, no archive).
- `reports/data_quality.md` written. Decisions D1-D25.
- `reports/ai_validation_log.md`: 8 entries; real caught errors in #2, #6, #7, #8 (the Day 1 ones were caught by AI self-review, not by Adri).

- Committed and pushed to https://github.com/el0002/amazon-listing-anomaly-detector (`main`). `outputs/` files are committed, `rejected_rows.csv` included (D24). All 12 commits were rewritten on 2026-10-12/13 to drop the Claude co-author trailer and to set author and committer to el0002 (`172130004+el0002@users.noreply.github.com`; the old email belongs to a separate GitHub account, gitnadu). Files, dates and messages unchanged. This repo's git identity is set to el0002; from now on Adri commits (D25).

**Done: Day 2** (uncommitted; commits proposed for Adri)
- Decisions D26-D33 (Adri): label sample proportional to category size (D26); accuracy over branded labels only, plus an invented-brand count, with `NO_BRAND` for titles naming no brand (D27); match ignores case, spaces, punctuation (D28); D15's 30-listing minimum confirmed (D29); rules may be tuned on the 100 labels and the "after" figure says so (D30); low price = robust z of log price < -3 (D31); high sales/few reviews = bought >= category p99, > 0, reviews = 0 (D32); near-duplicate = exact title within category (D33). No open questions.
- Decisions D34-D39 (Adri): keep the market-wide scope, no per-brand analysis (D34); `true_brand` is the brand on the Amazon page as Adri checked it, `NO_BRAND` if none (D35, replaces D27's "title brand"); rows tagged `DIFF_PRODUCT`/`LISTING_UNAVAILABLE`/`ASIN_INVALID` are left out and counted (D36); label-file save artefacts fixed by the AI (D37); "Rubie" kept (D38); B0767KQY6V relabeled "Small Parts" (D39). No open questions.
- `src/brand.py`: 100-title sample in 98 categories (allocation matches `sql/label_sample_allocation.sql`). Adri labeled it from Amazon pages: 86 brands, 1 `NO_BRAND`, 13 tagged (10 unavailable, 3 different product). **Brand accuracy: v0 (first word) 36/86 = 41.9% -> v1 (first word with a letter) 37/86 = 43.0%**, tuned on these labels (D30); invented 1 of 1 `NO_BRAND`. Ceiling: only 43 of 86 page brands appear in their title, so a title-only rule cannot exceed 50.0%. v2 (two-word brands learned from the data) was tried and rejected (#16).
- `src/anomalies.py`: category baselines (11 columns) and 4 signals on kept rows. `sql/category_baselines.sql`, `sql/anomaly_signals.sql`, `src/reconcile_anomalies.py`: 248 of 248 categories match on every column; 84,952 = 84,952 flags, 0 differences; mutation tests detected. Flags: high discount 3,291 high + 13,629 medium; low price 2,369; near-duplicate title 49,805; sales/reviews 15,858 (3,798 in categories with review data). 82,866 distinct listings, 2,034 with 2+ signals. `outputs/signal_counts.csv`, `outputs/baseline_reconciliation.csv`. `kept` view moved into `sql/quality_rules.sql` (Day 1 reconciliation re-run: unchanged).
- `reports/ai_validation_log.md`: entries 9-17 (#13: AI's runtime estimate for fuzzy matching was off by ~80x; #14: a Day 0 threshold had been quoted without ever being decided; #15: label checks found the title-vs-page mismatch and two save artefacts; #16: the AI's v2 rule made accuracy worse).

**Next**
1. Optional: more brand rules for the 6 reachable misses (Power Stop, Hot Wheels, Small Parts, Socell, Serene, Rubie), measured after each change. Edit `labels/` as text (UTF-8), not in a spreadsheet, which drops leading zeros.
2. Day 3: precision sample (`sample_for_precision_check`, still a stub; the split across signals and tiers is not decided yet, see D15), summary exports, dashboard, README, `findings.md`.
3. Update this Status; propose commits for Adri (D25).

Counts on kept rows (2026-10-13) vs Day 0 on all rows: discounted listings 345,105 vs 345,106 (B08FM4JTW2 rejected); high-tier discount 3,291 in both. Day 0's 37,702 "high sales/few reviews" used an undecided definition and is superseded by D32 (15,858).

## Definition of done
- Fresh clone + `pip install -r requirements.txt` runs the pipeline end to end.
- README reports quality-rule failures, brand accuracy (before/after), and flag precision as numbers.
- `ai_validation_log.md` has at least 3 real caught errors.
