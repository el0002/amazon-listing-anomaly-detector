-- Brand-label sample allocation (D26): 100 titles split across categories in proportion to
-- kept rows, largest remainder, ties to the lower category_id. Same as allocate_proportional
-- in src/brand.py. Run after sql/quality_rules.sql (needs its kept view).

CREATE OR REPLACE VIEW label_sample_allocation AS
WITH c AS (
    SELECT category_id, count(*) AS kept_rows FROM kept GROUP BY category_id
),
e AS (
    SELECT *, 100.0 * kept_rows / sum(kept_rows) OVER () AS exact FROM c
),
f AS (
    SELECT *, floor(exact)::INTEGER AS floor_quota, exact - floor(exact) AS remainder FROM e
),
r AS (
    SELECT *, row_number() OVER (ORDER BY remainder DESC, category_id) AS remainder_rank,
           100 - sum(floor_quota) OVER () AS leftover
    FROM f
)
SELECT category_id, kept_rows, floor_quota + (remainder_rank <= leftover)::INTEGER AS quota
FROM r;

SELECT * FROM label_sample_allocation ORDER BY category_id;
