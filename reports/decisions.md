# Decision Log

Judgment calls made during the project: what the question was, what options were on the table, who decided, and why. `ai_validation_log.md` records how AI-written logic was checked; this file records the human decisions that steer it.

"Decided by" is **Adri** for human decisions, or **AI default** for small choices the AI made without asking, listed here so they can be reviewed and overruled.

## Decisions

| # | Date | Question | Options considered | Decision | Decided by | Why | Where applied |
|---|------|----------|--------------------|----------|------------|-----|---------------|
| D1 | 2026-10-10 | A title is the literal text "NULL" (1 row, ASIN B00758A9CE). Is it a missing title? | (a) Keep as text; (b) treat as missing and reject | (b) Treat as missing; the row is rejected | Adri | No title means no product to analyze and no brand to extract | `missing_title` rule in `src/quality_rules.py` (Day 1). Row goes to the rejected-rows file, not silently dropped |
| D2 | 2026-10-10 | Pin package versions in `requirements.txt`? | (a) Unpinned; (b) pin the versions that installed and were tested | (b) Pin | Adri | A fresh clone must reproduce the same results | `requirements.txt` (Python 3.11.9) |
| D3 | 2026-10-10 | How to put the Kaggle CSVs in `data/raw/` | (a) Symlink; (b) copy | (b) Copy | AI default | Windows symlinks need admin or Developer Mode | `data/raw/` (not committed) |
| D4 | 2026-10-10 | Where the project's git repo lives | (a) Use the existing repo at the home folder; (b) new repo in the project folder | (b) New repo | AI default | The home folder is itself a git repo; the project needs its own history to publish | Project root |

## Open questions

| # | Raised | Question | Options | Evidence so far | Status |
|---|--------|----------|---------|-----------------|--------|
| Q1 | 2026-10-10 | What does `reviews = 0` with `stars > 0` mean (999,480 rows, 70.1%)? | (a) Real: rated but no written review; (b) Not collected: review count missing for those rows; (c) Mixed | Zeros come per category, all or nothing: 170 of 248 categories have `reviews = 0` for every rated listing, 36 have no zeros, 42 are mixed. Rating shape is the same with and without reviews (avg stars 4.41 vs 4.40; whole-number ratings 12.1% vs 13.0%). 6,965 of 8,520 best sellers have 0 reviews | Open: Adri to decide |
| Q2 | 2026-10-10 | Is `boughtInLastMonth` a lower bound ("50+ bought")? | (a) Lower bound; (b) Exact count | Only 30 distinct values: 0, 50, 100…1000, 2000…10000, 20000…100000 | Open |
| Q3 | 2026-10-10 | How to define "discount" when 75.8% of rows have `listPrice = 0` | (a) Discount only where `listPrice > 0`; (b) also track the share of each category that shows a list price | 1,080,503 rows with `listPrice = 0` | Open (needed by Day 2) |
