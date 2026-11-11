# 02 — Data Preparation

## 1. Goal
The raw Yelp dataset is too large to use as-is for a mini project (`review.json` alone is several GB with 7M+ records). This phase filters it down to a manageable, demo-friendly subset while keeping it realistic.

## 2. Filtering Strategy
1. **Pick one city** with a good volume of businesses (check value counts first — don't assume, verify from the data). Philadelphia, Tampa, and New Orleans are commonly dense in the Yelp dataset.
2. **Pick 1–2 categories** to focus on, e.g. `Restaurants` as primary, and one secondary category (e.g. `Cafes` or `Bars`) to prove the system is category-agnostic.
3. Keep only businesses matching city + category filter.
4. Keep only reviews whose `business_id` is in the filtered business set.
5. Keep only users whose `user_id` appears in the filtered review set.

## 3. Processing Steps (`src/prepare_data.py`, run once, offline)
1. Load `business.json` line-by-line (it's newline-delimited JSON, not a single JSON array) using `pandas.read_json(..., lines=True)` or manual line iteration for memory efficiency.
2. Filter on `city` and `categories` (categories is a comma-separated string in raw Yelp data — split and check membership).
3. Extract and validate `latitude` / `longitude` — drop rows with nulls (a small number typically exist).
4. Save filtered businesses to `data/filtered/business_filtered.json`.
5. Stream `review.json` line-by-line, keep only rows where `business_id` is in the filtered business ID set (use a Python `set` for O(1) lookup — do not do this with a list, review.json is too large).
6. Save filtered reviews to `data/filtered/review_filtered.json`.
7. Stream `user.json`, keep only rows where `user_id` is in the filtered review's user ID set.
8. Save filtered users to `data/filtered/user_filtered.json`.

## 4. Expected Field Cleanup
| Field | Cleanup needed |
|---|---|
| `categories` (business) | Split comma-separated string into an array, e.g. `"Restaurants, Italian, Pizza"` → `["Restaurants", "Italian", "Pizza"]` |
| `attributes` (business) | Yelp stores this as a nested dict, sometimes with stringified booleans (`"True"` as a string) — normalize to real booleans/nested objects |
| `latitude` / `longitude` | Convert to GeoJSON: `{"type": "Point", "coordinates": [longitude, latitude]}` — note GeoJSON order is `[lng, lat]`, NOT `[lat, lng]`, this is a common bug source |
| `date` (review) | Ensure parsed as an ISO date string or Python `datetime` for later time-decay/recency logic |
| `stars` | Keep as float, no change needed |

## 5. Sanity Checks Before Moving to Phase 2
- [ ] Filtered `business_filtered.json` has a reasonable size (aim for hundreds to a few thousand businesses, not tens of thousands)
- [ ] Every business has valid, non-null `latitude`/`longitude`
- [ ] At least 2 distinct categories are represented (for the category-agnostic demo)
- [ ] Filtered `review_filtered.json` only contains reviews referencing existing filtered businesses
- [ ] Spot-check a few review texts manually — confirm they read like real sentences (encoding issues are common with Yelp's raw text, e.g. stray unicode escapes)

## 6. Output of This Phase
Three clean, small, ready-to-ingest JSON files in `data/filtered/`:
- `business_filtered.json`
- `review_filtered.json`
- `user_filtered.json`

These feed directly into `src/ingest.py` in Phase 2.
