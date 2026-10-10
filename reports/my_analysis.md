# My Analysis (Adri)

My own exploration of the dataset. The reference section at the top holds facts from profiling code that was actually run (2026-10-10), with column meanings as I defined them. Everything below "My notes" is my own analysis, written by me or transcribed from what I said in the working session.

---

## Reference: data dictionary

**`amazon_products.csv`**: 1,426,337 rows, one per ASIN (no duplicate ASINs, no nulls in any column).

| Column | Type | Meaning | Observed | Watch out for |
|--------|------|---------|----------|---------------|
| `asin` | text | Amazon product ID | 1,426,337 distinct | Unique, safe as a key |
| `title` | text | Listing title | 1,385,431 distinct; 40,906 rows repeat a title used by another ASIN | 1 title is the text "NULL" (to be rejected, D1). 16 lines contain the U+FFFD replacement character (garbled text) |
| `imgUrl` | text | Main image URL | 1,372,162 distinct; 54,175 rows reuse another ASIN's image | Shared images may point to copycats or to variants of one product |
| `productURL` | text | `amazon.com/dp/<asin>` | 1,426,337 distinct | Built from the ASIN; adds no information |
| `stars` | decimal | Average star rating, 0–5 | Median 4.4; 131,023 rows are 0 | `0` = no ratings found (D5). All 131,023 also have 0 reviews |
| `reviews` | integer | Review count | 1,130,503 rows (79.3%) are 0; max 346,563 | `0` = no reviews found (D5). 999,480 rows have stars but 0 reviews; zeros cluster by category (170 of 248 categories have 0 on every rated listing) |
| `price` | decimal | Selling price, USD | Median 19.95; max 19,731.81; 32,772 rows are 0 | `0` = price unavailable (D5). 32,723 of the zero-price rows also have `listPrice = 0` |
| `listPrice` | decimal | Original price before discount, USD | 1,080,503 rows (75.8%) are 0; max 999.99 | `0` = no discount was given; the price is the price (D5). 451 rows have price > listPrice |
| `category_id` | integer | Joins to `amazon_categories.id` | 248 distinct; all match a category | IDs run 1–270 with gaps |
| `isBestSeller` | true/false | Best Seller badge | 8,520 true | |
| `boughtInLastMonth` | integer | Amazon's estimate of units sold in the past month ("N+ bought") | Only 30 distinct values: 0, 50, 100…1000, 2000…10000, 20000…100000 | An estimate, not an exact count: each value is the bottom of a bucket (D7). Reflects Aug–Sep 2023 |

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

*2026-10-10*

- A rating with no reviews could mean the customer gave stars but no written review. (Later settled by the dataset description, below.)
- No title = no product = no insights. Listings with no title get removed.
- From the dataset description: 0 stars means no ratings found, 0 reviews means no reviews found, 0 price means the price is unavailable. List price is the original price before the discount.
- A list price of 0 just means no discount was given, meaning the price is the price.
- `boughtInLastMonth` is part of the dataset. It is an estimate, since it refers to products sold in the last month, provided by Amazon.
- The data is from September 2023, so we have to consider the buying climate at the time and the deals in both August and September 2023.

### Questions I want to answer

### What I found

### Things that don't look right

*2026-10-10*

- Price above the list price: remove, since it breaks the logic (list price is the price before the discount).
- Missing title: use the ASIN to find the product title. If there's no ASIN or title, remove the product, since we have no idea what it is.

*2026-10-11*

- Checked the 2023 image for B00758A9CE: it is a brush, so the recovered title is right.

### Ideas for anomaly signals

*2026-10-10*

- Products that don't have a discount still mean something.

*2026-10-11*

- For "discount far above the category norm", don't include the 0% discounts, only the ones above 0. It's fair that way.
