# 03 — Database Schema & Ingestion

## 1. Collections Overview
| Collection | Purpose | Approx size (after filtering) |
|---|---|---|
| `businesses` | One document per business, embeds attributes | Hundreds–low thousands |
| `reviews` | One document per review, referenced to business + user | Tens of thousands |
| `users` | One document per user, lightweight profile + history summary | Hundreds–low thousands |

## 2. Embed vs Reference Decisions (important for the report)
| Data | Decision | Reasoning |
|---|---|---|
| Business attributes (WiFi, parking, etc.) | **Embed** inside `businesses` document | Small, fixed-per-business, always queried together with the business — no reason to normalize into a separate collection |
| Reviews | **Reference** via `business_id` in a separate `reviews` collection | Unbounded growth (a popular business could have thousands of reviews) — embedding would blow past MongoDB's 16MB document size limit and make the business document slow to load |
| Categories | **Embed** as an array field inside `businesses` | Small, fixed list per business, queried directly (`$in`, exact match) — no need for a separate categories collection |
| User's review history | **Reference** (derive by querying `reviews` where `user_id` matches) | Avoids duplicating review data inside the user document; keeps user documents small |

## 3. `businesses` Collection Schema
```json
{
  "_id": "biz_001",
  "name": "Joe's Pizza",
  "city": "Philadelphia",
  "location": {
    "type": "Point",
    "coordinates": [-75.1652, 39.9526]
  },
  "address": "123 Main St",
  "categories": ["Restaurants", "Pizza", "Italian"],
  "attributes": {
    "WiFi": "free",
    "OutdoorSeating": true,
    "RestaurantsPriceRange2": 2
  },
  "stars": 4.2,
  "review_count": 312,
  "avgSentiment": 0.0
}
```
Note: `avgSentiment` starts at `0.0` (or null) at ingest time — it gets populated in Phase 4 (sentiment module) after reviews are processed.

## 4. `reviews` Collection Schema
```json
{
  "_id": "rev_001",
  "business_id": "biz_001",
  "user_id": "usr_045",
  "stars": 5,
  "text": "Best slice in the city, friendly staff, quick service.",
  "date": "2024-03-12",
  "sentiment_score": null
}
```
`sentiment_score` starts as `null`, populated by the Phase 4 batch job.

## 5. `users` Collection Schema
```json
{
  "_id": "usr_045",
  "name": "Alex R.",
  "review_count": 27,
  "average_stars": 4.1
}
```
Keep this minimal — the recommendation module derives "categories this user likes" dynamically by joining against their reviews at query time (or precomputing it as a maintained field — see 06-recommendation-module.md for the trade-off).

## 6. Required Indexes
```js
// Geospatial index — required for $near / $geoNear queries
db.businesses.createIndex({ location: "2dsphere" })

// Category filtering — speeds up category-based queries
db.businesses.createIndex({ categories: 1 })

// Review lookups by business (for sentiment aggregation and pipeline joins)
db.reviews.createIndex({ business_id: 1 })

// Review lookups by user (for personalization)
db.reviews.createIndex({ user_id: 1 })

// Optional: text index for keyword search on review text
db.reviews.createIndex({ text: "text" })
```

## 7. Ingestion Script Outline (`src/ingest.py`)
1. Connect to MongoDB using `db.py` helper and `.env` config.
2. Load `business_filtered.json`, transform each row into the schema above (build the GeoJSON `location` field).
3. Bulk insert into `businesses` using `insert_many` (batch in chunks of ~1000 to avoid memory spikes).
4. Repeat for `review_filtered.json` → `reviews` and `user_filtered.json` → `users`.
5. Create all indexes listed in section 6 AFTER bulk insert (faster than indexing during insert).
6. Print collection counts at the end as a sanity check (`db.businesses.count_documents({})`, etc.)

## 8. Index Performance Demonstration (for report/viva)
Run the same geo-query with and without the `2dsphere` index (drop index temporarily, re-run, compare via `.explain("executionStats")`):
- Without index: `COLLSCAN` (full collection scan), higher `executionTimeMillis`
- With index: `IXSCAN` (index scan / `GEO_NEAR` stage), significantly lower `executionTimeMillis`

Capture both `.explain()` outputs as screenshots for the report — this is a very concrete, gradable artifact showing you understand *why* indexing matters, not just that you created one.
