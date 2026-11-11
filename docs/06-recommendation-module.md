# 06 — Recommendation Module (`src/recommend.py`)

## 1. Purpose
Re-rank the geo-filtered, sentiment-enriched candidate list based on a specific user's past preferences. This module does NOT reduce the candidate set — it only reorders it (see `00-overview.md` for why this distinction matters in viva).

## 2. Approach: Content-Based Filtering
Chosen over collaborative filtering because:
- No need for a user-item ratings matrix or matrix factorization — much simpler to build and explain within a mini project timeline
- Naturally explainable ("recommended because you liked Italian food before") — collaborative filtering recommendations are harder to justify to an evaluator in a demo
- Works even with a relatively small/filtered user base, where collaborative filtering would suffer from sparsity

## 3. Step 1 — Derive User's Preferred Categories
```python
def get_user_preferred_categories(db, user_id, min_stars=4):
    reviews = db.reviews.find({"user_id": user_id, "stars": {"$gte": min_stars}})
    business_ids = [r["business_id"] for r in reviews]

    businesses = db.businesses.find({"_id": {"$in": business_ids}})
    categories = []
    for b in businesses:
        categories.extend(b["categories"])

    from collections import Counter
    return Counter(categories)  # e.g. {"Italian": 5, "Cafe": 2}
```

## 4. Step 2 — Category Match Boost
For each candidate business, compute how much its categories overlap with the user's preferred categories:
```python
def category_match_boost(business_categories, user_category_counts):
    if not user_category_counts:
        return 0  # cold start — no history yet
    overlap = sum(user_category_counts.get(cat, 0) for cat in business_categories)
    max_possible = sum(user_category_counts.values())
    return overlap / max_possible if max_possible else 0
```

## 5. Step 3 — Final Weighted Score
```python
def compute_final_score(business, distance_m, user_category_counts, weights=None):
    weights = weights or {"stars": 0.3, "sentiment": 0.3, "category": 0.3, "distance": 0.1}

    normalized_distance = 1 - min(distance_m / 5000, 1)  # closer = higher score, capped at 5km
    category_score = category_match_boost(business["categories"], user_category_counts)

    final_score = (
        weights["stars"] * (business["stars"] / 5) +
        weights["sentiment"] * ((business.get("avgSentiment", 0) + 1) / 2) +  # normalize -1..1 to 0..1
        weights["category"] * category_score +
        weights["distance"] * normalized_distance
    )
    return final_score
```
Note: `avgSentiment` is normalized from its native `-1..1` range to `0..1` so it's on the same scale as the other weighted components — call this out explicitly in the report, it's a subtle but important detail.

## 6. Cold-Start Handling
If a user has no review history (`user_category_counts` is empty):
- `category_match_boost` naturally returns `0` for everyone — meaning ranking falls back to a mix of `stars`, `avgSentiment`, and `distance` only
- Optionally, re-normalize weights when there's no history (e.g., redistribute the `category` weight into `stars`/`sentiment`) so cold-start users still get a meaningful ranking rather than one quietly missing a component
- Explicitly mention this fallback behavior in the report/viva — it's a well-known real-world recommendation system problem, and handling it (even simply) shows depth

## 7. Explainable Output
Alongside the score, generate a short reason string per result:
```python
def explain_recommendation(business, distance_m, user_category_counts):
    reasons = [f"{distance_m/1000:.1f}km away", f"{business['stars']}★"]
    if business.get("avgSentiment", 0) > 0.3:
        reasons.append("mostly positive reviews")
    matched = [c for c in business["categories"] if c in user_category_counts]
    if matched:
        reasons.append(f"matches your interest in {matched[0]}")
    return ", ".join(reasons)
```

## 8. Testing This Module
1. Test with a user who has clear category history (e.g., only rated Italian places highly) — confirm Italian businesses rank higher.
2. Test with a brand-new user ID (no reviews) — confirm cold-start fallback still returns a sensible, non-empty ranked list.
3. Confirm the explanation string reads sensibly for a handful of sample outputs.

## 9. Output of This Module
A ranked list of businesses (with `final_score` and `explanation` attached), ready to be returned by the combined pipeline in Phase 6.
