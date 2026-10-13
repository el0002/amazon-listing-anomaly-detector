-- Data quality rules in DuckDB SQL: the same rules as src/quality_rules.py.
-- Paths are relative to the project root. Run from the root with the DuckDB CLI
-- (duckdb < sql/quality_rules.sql) or with `python -m src.reconcile_quality`.
-- Decisions: D5, D9, D16-D18, D20, D21, D23 in reports/decisions.md.

-- Explicit types; only empty fields are NULL, so text like "NULL" stays text (as in src/load.py).
CREATE OR REPLACE VIEW products_raw AS
SELECT * FROM read_csv('data/raw/amazon_products.csv', header = true, nullstr = '', columns = {
    'asin': 'VARCHAR', 'title': 'VARCHAR', 'imgUrl': 'VARCHAR', 'productURL': 'VARCHAR',
    'stars': 'DOUBLE', 'reviews': 'BIGINT', 'price': 'DOUBLE', 'listPrice': 'DOUBLE',
    'category_id': 'BIGINT', 'isBestSeller': 'BOOLEAN', 'boughtInLastMonth': 'BIGINT'});

CREATE OR REPLACE VIEW categories AS
SELECT * FROM read_csv('data/raw/amazon_categories.csv', header = true, nullstr = '',
                       columns = {'id': 'BIGINT', 'category_name': 'VARCHAR'});

-- An override applies only if Adri confirmed it (D18), its ASIN is in the data, and its raw_title
-- is similar to the data's title: normalized Levenshtein similarity >= 95 after lowercasing and
-- collapsing whitespace (D21, D23). DuckDB's levenshtein counts bytes, so the score is computed
-- on byte lengths; for non-ASCII titles it can be lower than Python's character-based score.
CREATE OR REPLACE VIEW override_status AS
WITH o AS (
    SELECT * FROM read_csv('overrides/title_overrides.csv', header = true, all_varchar = true)
),
d AS (
    SELECT asin, any_value(title) AS title FROM products_raw GROUP BY asin
),
n AS (
    SELECT o.asin, o.raw_title, d.title AS data_title, o.corrected_title, o.confirmed_by,
           d.asin IS NOT NULL AS in_data,
           lower(trim(regexp_replace(coalesce(o.raw_title, ''), '\s+', ' ', 'g'))) AS a,
           lower(trim(regexp_replace(coalesce(d.title, ''), '\s+', ' ', 'g'))) AS b
    FROM o LEFT JOIN d USING (asin)
),
s AS (
    SELECT *, CASE WHEN NOT in_data THEN NULL
                   WHEN greatest(strlen(a), strlen(b)) = 0 THEN 100.0
                   ELSE 100 * (1 - levenshtein(a, b) / greatest(strlen(a), strlen(b))) END AS score
    FROM n
)
SELECT asin, raw_title, data_title, round(score, 1) AS similarity,
       CASE WHEN coalesce(trim(confirmed_by), '') = '' THEN 'unconfirmed'
            WHEN NOT in_data THEN 'asin_not_in_data'
            WHEN score < 95 THEN 'title_differs'
            ELSE 'applied' END AS status,
       corrected_title
FROM s;

CREATE OR REPLACE VIEW products AS
SELECT p.* REPLACE (coalesce(o.corrected_title, p.title) AS title)
FROM products_raw p
LEFT JOIN (SELECT asin, corrected_title FROM override_status WHERE status = 'applied') o USING (asin);

-- One row per listing, one boolean per rule. Every rule sees all rows (D20).
CREATE OR REPLACE VIEW rule_flags AS
WITH t AS (
    SELECT *, regexp_replace(title, '^\s+|\s+$', '', 'g') AS title_trim,
           count(*) OVER (PARTITION BY asin) AS asin_count
    FROM products
)
SELECT
    asin,
    -- D1/D16: empty, "NULL", no letter or digit in any script, or 1 character.
    coalesce(title_trim IS NULL
             OR upper(title_trim) = 'NULL'
             OR NOT regexp_matches(title_trim, '[\pL\pN]')
             OR length(title_trim) <= 1, true)                     AS missing_title,
    coalesce(listPrice > 0 AND price > listPrice, false)           AS price_above_list_price,
    asin_count > 1                                                  AS duplicate_asin,
    category_id IS NULL OR category_id NOT IN (SELECT id FROM categories) AS unknown_category_id,
    coalesce(price = 0, false)                                      AS zero_price,
    coalesce(listPrice = 0, false)                                  AS zero_list_price,
    coalesce(stars > 0 AND reviews = 0, false)                      AS stars_without_reviews
FROM t;

CREATE OR REPLACE VIEW rejected AS
SELECT asin,
       concat_ws(';',
           CASE WHEN missing_title THEN 'missing_title' END,
           CASE WHEN price_above_list_price THEN 'price_above_list_price' END,
           CASE WHEN duplicate_asin THEN 'duplicate_asin' END,
           CASE WHEN unknown_category_id THEN 'unknown_category_id' END) AS rejected_by
FROM rule_flags
WHERE missing_title OR price_above_list_price OR duplicate_asin OR unknown_category_id;

-- Rows no rule rejects: the same rows as clean_products() in src/quality_rules.py.
CREATE OR REPLACE VIEW kept AS
SELECT p.* FROM products p ANTI JOIN rejected r USING (asin);

-- Rows failed and % of all raw rows per rule, plus how many of them are kept.
CREATE OR REPLACE VIEW rule_counts AS
WITH f AS (
    SELECT r.*, (missing_title OR price_above_list_price OR duplicate_asin OR unknown_category_id) AS is_rejected
    FROM rule_flags r
),
long AS (
    UNPIVOT f ON missing_title, price_above_list_price, duplicate_asin, unknown_category_id,
                 zero_price, zero_list_price, stars_without_reviews
    INTO NAME rule VALUE failed
)
SELECT rule,
       CASE WHEN rule IN ('missing_title', 'price_above_list_price', 'duplicate_asin', 'unknown_category_id')
            THEN 'reject' ELSE 'count' END                          AS action,
       count(*) FILTER (failed)                                     AS rows_failed,
       round(100.0 * count(*) FILTER (failed) / count(*), 4)        AS pct_of_rows,
       count(*) FILTER (failed AND NOT is_rejected)                 AS rows_failed_in_kept
FROM long
GROUP BY rule;

SELECT * FROM rule_counts ORDER BY action DESC, rule;
