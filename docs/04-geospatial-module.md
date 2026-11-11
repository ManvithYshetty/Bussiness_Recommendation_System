z# 04 — Geospatial Search Module (`src/geo_search.py`)

## 1. Purpose
Given a user's coordinates (and optionally a category + radius), return the set of nearby candidate businesses. This is Stage 1 of the pipeline — the only stage that actually reduces the dataset size.

## 2. Core Query
```python
def find_nearby_businesses(db, lng, lat, max_distance_m=3000, category=None, limit=50):
    query = {
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": max_distance_m
            }
        }
    }
    if category:
        query["categories"] = category

    return list(db.businesses.find(query).limit(limit))
```

Notes:
- `$near` requires the `2dsphere` index created in Phase 2 — without it, the query will error out, not just run slowly. This is a good point to mention in viva: MongoDB enforces the index requirement for `$near`.
- Coordinates are `[longitude, latitude]` order — a very common bug if someone mixes it up. Add a code comment reminding of this.
- `$maxDistance` is in **meters** when using GeoJSON points (as opposed to legacy coordinate pairs which use radians) — confirm this in the report as a technical detail.

## 3. Alternative: `$geoNear` via Aggregation Pipeline
Useful when you also want the **computed distance** returned (not just filtering, but the actual distance value per result — needed later for the ranking formula in Phase 5):
```python
def find_nearby_with_distance(db, lng, lat, max_distance_m=3000, category=None, limit=50):
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lng, lat]},
                "distanceField": "distance_m",
                "maxDistance": max_distance_m,
                "spherical": True,
                "query": {"categories": category} if category else {}
            }
        },
        {"$limit": limit}
    ]
    return list(db.businesses.aggregate(pipeline))
```
This is the version to actually use in the combined pipeline (Phase 6), since `distance_m` is needed for the final scoring formula. `$geoNear` must be the FIRST stage of the aggregation pipeline — this is a MongoDB requirement worth noting in the report.

## 4. Testing This Module
1. Pick a known business's coordinates from the filtered dataset, search from a point ~1km away, confirm it's returned.
2. Search from a point >max_distance away, confirm it's NOT returned.
3. Test the `category` filter narrows results correctly.
4. Run `.explain("executionStats")` on both query forms to confirm `IXSCAN`/`GEO_NEAR` stage usage (ties into the index performance demonstration from Phase 2).

## 5. Output of This Module
A list of business documents (or business + distance pairs, if using `$geoNear`), which becomes the candidate pool passed into Phase 4 (sentiment enrichment — already precomputed, just read) and Phase 5 (recommendation ranking).
