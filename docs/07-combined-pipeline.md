# 07 — Combined Pipeline (`src/pipeline.py`)

## 1. Purpose
This is the module that ties Phases 3–5 together into the single end-to-end function the frontend actually calls. This is also the piece that answers "how do you combine geo + sentiment + recommendation into one system" in viva — each stage's output feeds the next stage's input.

## 2. Pipeline Stages Recap
| Stage | Module | Effect on dataset |
|---|---|---|
| 1. Geo-filter | `geo_search.py` | **Reduces** — narrows thousands of businesses to a nearby candidate pool |
| 2. Sentiment enrichment | Already precomputed in `businesses.avgSentiment` (Phase 4) | **Enriches** — no reduction, just reads existing data |
| 3. Recommendation ranking | `recommend.py` | **Re-ranks** — no reduction, reorders based on user history |
| 4. Explanation | `recommend.py` | **Annotates** — attaches a human-readable reason per result |

## 3. Main Pipeline Function
```python
from src.geo_search import find_nearby_with_distance
from src.recommend import get_user_preferred_categories, compute_final_score, explain_recommendation

def recommend_businesses(db, lng, lat, user_id=None, category=None, max_distance_m=3000, top_n=10):
    # Stage 1: Geo-filter (with distance returned per result)
    candidates = find_nearby_with_distance(db, lng, lat, max_distance_m, category)

    # Stage 2: Sentiment already embedded on each business document (avgSentiment)
    # — nothing to compute here, just read business["avgSentiment"]

    # Determine user's preferences (empty dict if cold-start / no user_id)
    user_category_counts = get_user_preferred_categories(db, user_id) if user_id else {}

    # Stage 3 + 4: Score and explain each candidate
    results = []
    for business in candidates:
        distance_m = business.get("distance_m", 0)
        score = compute_final_score(business, distance_m, user_category_counts)
        reason = explain_recommendation(business, distance_m, user_category_counts)
        results.append({**business, "final_score": score, "explanation": reason})

    # Sort by final_score descending, return top N
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:top_n]
```

## 4. Why This Counts as "One System" (for viva)
- It is a **single function call** from the frontend's perspective — the caller doesn't need to know three techniques are involved internally.
- Each stage's output is the next stage's input: geo-filter's candidate list → sentiment field already attached to those same documents → recommendation re-ranks those same documents → explanation is generated from the same final data.
- No stage operates on the full, unfiltered dataset except Stage 1 — this is what makes it efficient (you don't run sentiment analysis or personalization scoring against every business in the database, only the nearby, relevant few).

## 5. Testing This Module
1. Call with a known `user_id` that has category history + valid coordinates — confirm results are geographically near, sorted sensibly, and explanations reference the matched category.
2. Call with `user_id=None` — confirm it still returns a sensible ranked list (cold-start path).
3. Call with a `category` filter and without — confirm both paths work.
4. Time the full pipeline call — this becomes a useful "performance" data point for the report (e.g., "end-to-end recommendation returned in X ms for a candidate pool of Y businesses").

## 6. Output of This Module
A ranked, explained list of top-N business dicts — this is exactly what `app.py` (Phase 7 frontend) needs to render directly.
