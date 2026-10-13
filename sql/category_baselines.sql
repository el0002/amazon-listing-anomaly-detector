-- Per-category baselines: the same as category_baselines in src/anomalies.py.
-- Run after sql/quality_rules.sql (needs its kept view).
-- Decisions: D6 (discount), D9 (price = 0 left out), D11 (review data), D14 (discounted only), D29 (30+),
-- D31 (log-price median and MAD), D32 (99th percentile of boughtInLastMonth).

-- D6: discount when listPrice > 0, 0 when listPrice = 0, NULL when price = 0.
CREATE OR REPLACE VIEW kept_discount AS
SELECT *,
       CASE WHEN price = 0 THEN NULL
            WHEN listPrice > 0 THEN (listPrice - price) / listPrice
            ELSE 0 END AS discount,
       ln(CASE WHEN price > 0 THEN price END) AS log_price
FROM kept;

CREATE OR REPLACE VIEW category_baselines AS
SELECT category_id,
       count(*)                                               AS kept_rows,
       count(*) FILTER (price > 0)                            AS priced_rows,
       median(price) FILTER (price > 0)                       AS median_price,
       median(log_price)                                      AS log_price_median,
       mad(log_price)                                         AS log_price_mad,
       count(*) FILTER (discount > 0)                         AS discounted_rows,
       avg(discount) FILTER (discount > 0)                    AS discount_mean,
       stddev_samp(discount) FILTER (discount > 0)            AS discount_std,
       quantile_cont(boughtInLastMonth, 0.99)                 AS bought_p99,
       coalesce(bool_or(reviews > 0), false)                  AS has_review_data,
       count(*) FILTER (discount > 0) >= 30                   AS discount_eligible
FROM kept_discount
GROUP BY category_id;

SELECT * FROM category_baselines ORDER BY category_id;
