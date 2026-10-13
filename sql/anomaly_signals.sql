-- Anomaly signals: the same as the flag_* functions in src/anomalies.py.
-- Run after sql/quality_rules.sql and sql/category_baselines.sql.
-- One row per flagged listing and signal. Decisions: D11, D14, D15, D29, D31, D32, D33.

CREATE OR REPLACE VIEW signal_flags AS
WITH s AS (
    SELECT k.asin, k.category_id, k.discount, k.log_price, k.boughtInLastMonth, k.reviews,
           b.log_price_median, b.log_price_mad, b.discount_mean, b.discount_std, b.discount_eligible,
           b.bought_p99, b.has_review_data
    FROM kept_discount k JOIN category_baselines b USING (category_id)
),
low_price AS (
    -- D31: robust z of log price < -3; price = 0 (log_price NULL) and MAD = 0 get no score.
    SELECT asin, category_id, (log_price - log_price_median) / (1.4826 * log_price_mad) AS z
    FROM s WHERE log_price IS NOT NULL AND log_price_mad > 0
),
near_duplicate AS (
    -- D33: same title within category after lowercasing and collapsing whitespace (as in
    -- override_status in sql/quality_rules.sql); score = ASINs sharing it.
    SELECT asin, category_id,
           count(*) OVER (PARTITION BY category_id, lower(trim(regexp_replace(title, '\s+', ' ', 'g')))) AS group_size
    FROM kept
),
high_discount AS (
    -- D14, D15, D29: z among discounted listings, categories with 30+ of them.
    SELECT asin, category_id, (discount - discount_mean) / discount_std AS z
    FROM s WHERE discount > 0 AND discount_eligible
)
SELECT asin, category_id, 'low_price' AS signal, 'high' AS tier, z AS score, NULL::BOOLEAN AS has_review_data
FROM low_price WHERE z < -3
UNION ALL
SELECT asin, category_id, 'high_discount', CASE WHEN z > 3 THEN 'high' ELSE 'medium' END, z, NULL
FROM high_discount WHERE z > 2
UNION ALL
SELECT asin, category_id, 'near_duplicate_title', 'high', group_size::DOUBLE, NULL
FROM near_duplicate WHERE group_size >= 2
UNION ALL
-- D32, D11: bought at or above the category's 99th percentile, bought > 0, reviews = 0.
SELECT asin, category_id, 'sales_review_mismatch', 'high', boughtInLastMonth::DOUBLE, has_review_data
FROM s WHERE boughtInLastMonth >= bought_p99 AND boughtInLastMonth > 0 AND reviews = 0;

SELECT signal, tier, count(*) AS listings FROM signal_flags GROUP BY ALL ORDER BY ALL;
