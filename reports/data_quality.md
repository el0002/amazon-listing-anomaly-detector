# Data Quality Audit

*Run 2026-10-12 on `amazon_products.csv` (Kaggle version 17, the latest on that date; 1,426,337 rows) and `amazon_categories.csv` (248 rows). Every number below comes from `python -m src.quality_rules` and `python -m src.reconcile_quality`.*

## Summary

- **453 rows rejected (0.03%), 1,425,884 kept.** 451 have a price above their list price; 2 have no usable title. Kept + rejected = 1,426,337, the raw row count.
- **Three rules count rows but keep them**, because the zeros are meaningful values, not errors (D5): `zero_list_price` 1,080,503 (75.8%, no discount), `stars_without_reviews` 999,480 (70.1%), `zero_price` 32,772 (2.3%, price unavailable).
- **No duplicate ASINs and no unknown category IDs.**
- **SQL (DuckDB) and Python agree exactly**: 7 of 7 rule counts, the same 453 rejected ASINs with the same reasons, and the same status for all 3 title overrides.
- **3 missing titles were recovered** from Amazon by ASIN and confirmed by Adri (D13, D22), so those listings are kept.

## Rules

Each rule runs on all raw rows, after title overrides are applied, so a row can fail more than one rule and the counts don't depend on rule order (D20). % is out of all 1,426,337 raw rows.

| Rule | Fails when | Action | Why | Decision |
|------|-----------|--------|-----|----------|
| `missing_title` | Title is empty, the text "NULL", has no letter or digit in any script, or is 1 character long, after title overrides | Reject | No title means no product to analyze and no brand to extract. Each case is looked up by ASIN first; it is rejected only if no title is found | D1, D9, D16-D18, D21-D23 |
| `price_above_list_price` | `listPrice > 0` and `price > listPrice` | Reject | List price is the price before discount, so a higher selling price breaks the definition. `listPrice = 0` means no discount and is excluded; without that condition the rule would catch 1,048,231 rows | D5, D9 |
| `duplicate_asin` | ASIN appears more than once (every copy marked) | Reject | ASIN is the listing key | D9, D20 |
| `unknown_category_id` | `category_id` not in `amazon_categories.csv`, or null | Reject | Signals are benchmarked within category; a listing without one can't be benchmarked | D9 |
| `zero_price` | `price = 0` | Count, keep | Price unavailable. Kept, but left out of price and discount signals | D5, D9 |
| `zero_list_price` | `listPrice = 0` | Count, keep | A real "no discount" value | D5, D9 |
| `stars_without_reviews` | `stars > 0` and `reviews = 0` | Count, keep | Coverage note: review counts are missing for whole categories, not for scattered listings | D5, D9 |

## Rule results

| Rule | Action | Rows failed | % of rows | Of which kept |
|------|--------|------------:|----------:|--------------:|
| `missing_title` | Reject | 2 | 0.0001% | 0 |
| `price_above_list_price` | Reject | 451 | 0.0316% | 0 |
| `duplicate_asin` | Reject | 0 | 0% | 0 |
| `unknown_category_id` | Reject | 0 | 0% | 0 |
| `zero_price` | Count | 32,772 | 2.2976% | 32,771 |
| `zero_list_price` | Count | 1,080,503 | 75.7537% | 1,080,502 |
| `stars_without_reviews` | Count | 999,480 | 70.0732% | 999,133 |

"Of which kept" differs from "rows failed" for the counted rules because some rejected rows also fail them: 1 rejected row has a zero price, 1 has a zero list price, and 347 have stars without reviews.

**Against the Day 0 profile**: `price_above_list_price`, `zero_price`, `zero_list_price`, `stars_without_reviews`, `duplicate_asin` and `unknown_category_id` match exactly. `missing_title` was expected to be 1 before the override and 0 after. It is now **5 before overrides and 2 after**: D16 widened the definition beyond the text "NULL", and 3 of the 5 titles were recovered (details below).

### Missing titles

5 titles fail the rule before overrides. Each was looked up on amazon.com by ASIN (D9):

| ASIN | Raw title | Category | Lookup result | Outcome |
|------|-----------|----------|---------------|---------|
| B00758A9CE | NULL | Car Care | Recovered; confirmed by Adri (D13) | **Kept**, override applied |
| B00IKIEKS2 | - | Abrasive & Finishing Products | Recovered: "Osborn 54036 Plater's Fine Solid Wood Block Wire Scratch Brush"; page still shows the 2023 image; confirmed by Adri (D22) | **Kept**, override applied |
| B01HEJ3V9G | 0 | Puzzles | Recovered: Tenyo 500-piece "Alice in Wonderland" stained-art puzzle; page still shows the 2023 image; confirmed by Adri (D22) | **Kept**, override applied |
| B08FM4JTW2 | 3 | PC Games & Accessories | Amazon's own title is also "3" (brand MOOD.SC); the product is a pair of brass drawer pulls | Rejected (D17) |
| B09314JYMX | T | Xbox Series X & S Consoles, Games & Accessories | Page returns 404; no Wayback Machine snapshot. The 2023 image shows a USB-C cable | Rejected: no title found (D9) |

The rule keeps real titles that are short or in other scripts: 27 titles have no Latin letters or digits (Chinese, Japanese, or styled Unicode letters) but are real titles, and titles of 2–3 characters are mostly real brands or words ("K2", "Jo", "Bag" x14).

Recovered titles live in `overrides/title_overrides.csv` with their source and evidence (D12). An override applies only if `confirmed_by` is filled in (D18), its ASIN is in the data, and its `raw_title` is similar to the data's title: normalized Levenshtein similarity of 95 or more after lowercasing and collapsing whitespace (D21, D23). This guards against a new dataset version changing a title under an old override. Any override that doesn't apply is listed with its reason in `outputs/overrides_needing_confirmation.csv` for Adri to re-check, and its row goes through the rules with its own title. Today all 3 apply with similarity 100, and the list is empty.

### Price above list price

The 451 rows are spread over 62 categories, but video games dominate: the top five categories are all console game categories (Xbox 360: 62, PlayStation 4: 47, PlayStation 3: 44, Xbox One: 31, Nintendo DS: 28; 212 rows together). The gap is usually small: median $5.69 over list, median ratio 1.24x list. 83 rows are within $1.00 of list (6 within $0.01), 164 are more than $10 over, and 11 are more than $50 over (max ratio 8.8x). All 451 are rejected per D9, whatever the gap size.

## Rejected rows

`outputs/rejected_rows.csv`: 453 rows, all 11 original columns plus `rejected_by`. That column names every rejecting rule the row fails, separated by ";" (D20). No row fails more than one rejecting rule today:

| `rejected_by` | Rows |
|---------------|-----:|
| `price_above_list_price` | 451 |
| `missing_title` | 2 |

Rule counts are in `outputs/quality_rule_counts.csv`. `src.quality_rules.clean_products()` returns the 1,425,884 kept rows for Day 2.

## SQL vs Python reconciliation

The same rules are written twice: pandas in `src/quality_rules.py`, and DuckDB SQL reading the raw CSVs directly in `sql/quality_rules.sql`. `python -m src.reconcile_quality` runs both and compares them (`outputs/quality_reconciliation.csv`).

| Check | Python | SQL | Difference |
|-------|-------:|----:|-----------:|
| Rule counts (rows failed, %, of which kept), 7 rules | - | - | 0 of 7 differ |
| Rejected ASINs | 453 | 453 | 0 only in Python, 0 only in SQL |
| Title overrides: status and similarity | 3 applied | 3 applied | 0 of 3 differ |
| Same ASIN, different `rejected_by` | - | - | 0 |
| Missing titles before overrides | 5 | 5 | 0 |

To check that the comparison can fail, the SQL `missing_title` rule was run once with the 1-character condition removed. That test ran before D22, when Python counted 4 missing titles; the broken SQL returned 1, so a real difference would show up. The override fuzzy match was tested in both engines on 7 made-up cases (exact, unconfirmed, case and spacing change, 1-character typo, changed last word, unknown ASIN, non-ASCII title); Python and SQL gave the same status and score for all 7.

Known spots where the two engines could differ: (1) DuckDB's `levenshtein` counts bytes, not characters, so for a title that mixes 1-byte and multi-byte characters (e.g. "Décor") the SQL similarity can be lower than Python's; all 3 current raw titles are ASCII. (2) Python's `strip()` trims Unicode whitespace, while the SQL regex trims ASCII whitespace only. One title (B07W9JH5WN, 97 characters, ends in the control character U+0085) trims differently. It has letters and digits either way, so no rule result changes.

## Notes and open questions

- **Review counts are missing by category, not at random.** All 131,023 zero-star rows also have 0 reviews. Of the 999,480 rows with stars but no reviews, 783,343 (78%) are in the 170 of 248 categories where every rated listing has 0 reviews. Review counts aren't comparable across categories; this matters for the "high sales, few reviews" signal (D11).
- **Zero price and zero list price overlap**: 32,723 of the 32,772 zero-price rows also have list price 0; 49 have a list price but no selling price.
- **16 titles contain the U+FFFD replacement character** (garbled text in the source). They have readable text around it, so no rule fails them; brand extraction may miss a brand in these 16.
- **B08FM4JTW2 shows a category mismatch**: drawer pulls filed under PC Games & Accessories. It is rejected for its title, but it's an example of miscategorization worth noting in findings.
- No open questions in `reports/decisions.md`.

## How to reproduce

```
python -m src.download            # fetch the latest Kaggle version into data/raw/; warns if row counts differ from version 17
python -m src.quality_rules       # apply rules; write rejected_rows.csv, quality_rule_counts.csv, overrides_needing_confirmation.csv
python -m src.reconcile_quality   # run sql/quality_rules.sql and compare with Python
```
