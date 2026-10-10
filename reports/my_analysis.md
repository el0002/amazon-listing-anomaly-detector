# My Analysis (Adri)

My own exploration of the dataset, written by me. The reference section at the top holds facts from profiling code that was actually run (2026-10-10); everything below "My notes" is mine.

---

## Reference: data dictionary

**`amazon_products.csv`**: 1,426,337 rows, one per ASIN (no duplicate ASINs, no nulls in any column).

| Column | Type | Meaning | Observed | Watch out for |
|--------|------|---------|----------|---------------|
| `asin` | text | Amazon product ID | 1,426,337 distinct | Unique, safe as a key |
| `title` | text | Listing title | 1,385,431 distinct; 40,906 rows repeat a title used by another ASIN | 1 title is the text "NULL" (to be rejected, D1). 16 lines contain the U+FFFD replacement character (garbled text) |
| `imgUrl` | text | Main image URL | 1,372,162 distinct; 54,175 rows reuse another ASIN's image | Shared images may point to copycats or to variants of one product |
| `productURL` | text | `amazon.com/dp/<asin>` | 1,426,337 distinct | Built from the ASIN; adds no information |
| `stars` | decimal | Average star rating, 0–5 | Median 4.4; 131,023 rows are 0 | `0` seems to mean "no rating" (all 131,023 also have 0 reviews) |
| `reviews` | integer | Review count | 1,130,503 rows (79.3%) are 0; max 346,563 | 999,480 rows have stars but 0 reviews. Zeros cluster by category (see Q1 in `decisions.md`) |
| `price` | decimal | Current price, USD | Median 19.95; max 19,731.81; 32,772 rows are 0 | 32,723 of the zero-price rows also have `listPrice = 0` |
| `listPrice` | decimal | "Was" / list price, USD | 1,080,503 rows (75.8%) are 0; max 999.99 | 0 likely means no list price shown. 451 rows have price > listPrice |
| `category_id` | integer | Joins to `amazon_categories.id` | 248 distinct; all match a category | IDs run 1–270 with gaps |
| `isBestSeller` | true/false | Best Seller badge | 8,520 true | |
| `boughtInLastMonth` | integer | "N+ bought in past month" | Only 30 distinct values: 0, 50, 100…1000, 2000…10000, 20000…100000 | A bucket, probably a lower bound (Q2) |

**`amazon_categories.csv`**: 248 rows, `id` and `category_name`. No duplicate names; every category has products.

## Reference: how to query it yourself

From the project root with the venv active (`.venv\Scripts\activate`), in Python or a notebook:

```python
import duckdb
con = duckdb.connect()
con.sql("CREATE VIEW p AS SELECT * FROM 'data/raw/amazon_products.csv'")
con.sql("CREATE VIEW c AS SELECT * FROM 'data/raw/amazon_categories.csv'")

# Example: listings and median price per category
con.sql("""
    SELECT c.category_name, count(*) AS listings, median(p.price) AS median_price
    FROM p JOIN c ON p.category_id = c.id
    GROUP BY 1 ORDER BY listings DESC LIMIT 20
""").df()
```

From a notebook in `notebooks/`, use `'../data/raw/...'` paths instead.

Or load into pandas with the project loader:

```python
from src.load import load_products, load_categories
df, cat = load_products(), load_categories()
```

---

## My notes

### First impressions

### Questions I want to answer

### What I found

### Things that don't look right

### Ideas for anomaly signals
