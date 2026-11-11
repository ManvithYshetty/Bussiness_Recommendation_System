"""
06 — Recommendation Module (src/recommend.py)
Implements content-based personalization, taste-profile extraction,
multi-criteria weighted ranking (stars, sentiment, category match, distance),
cold-start fallback, and explainable recommendations.
"""

import os
import sys
from collections import Counter
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def get_user_preferred_categories(db, user_id: Optional[str], min_stars: float = 4.0) -> Counter:
    """
    Derive user's taste profile from their positive review history (stars >= min_stars).
    Returns a Counter of category frequencies (e.g. {'Italian': 4, 'Pizza': 3, 'Cafes': 1}).
    If user_id is None, invalid, or has no reviews, returns an empty Counter (cold start).
    """
    if not user_id:
        return Counter()

    reviews = list(db.reviews.find({"user_id": user_id, "stars": {"$gte": min_stars}}))
    if not reviews:
        return Counter()

    business_ids = [r["business_id"] for r in reviews if "business_id" in r]
    businesses = list(db.businesses.find({"_id": {"$in": business_ids}}, {"categories": 1}))

    categories = []
    for b in businesses:
        categories.extend(b.get("categories", []))

    return Counter(categories)


def category_match_boost(business_categories: List[str], user_category_counts: Counter) -> float:
    """
    Compute overlap ratio between candidate business categories and user preferences.
    Returns a normalized float between 0.0 and 1.0.
    """
    if not user_category_counts or not business_categories:
        return 0.0

    overlap = sum(user_category_counts.get(cat, 0) for cat in business_categories)
    max_possible = sum(user_category_counts.values())
    return (overlap / max_possible) if max_possible > 0 else 0.0


def compute_final_score(
    business: Dict[str, Any],
    distance_m: float,
    user_category_counts: Counter,
    weights: Optional[Dict[str, float]] = None,
    max_distance_norm_m: float = 5000.0
) -> float:
    """
    Compute unified recommendation score combining:
      1. Star rating (normalized 0..1)
      2. VADER sentiment score (avgSentiment normalized from [-1, 1] to [0, 1])
      3. Category match boost (0..1)
      4. Distance proximity (closer = higher score, normalized 0..1)
    
    Includes automatic weight redistribution for cold-start users (no review history).
    """
    if not user_category_counts:
        # Cold start fallback: redistribute category weight to stars and sentiment
        effective_weights = {"stars": 0.45, "sentiment": 0.45, "category": 0.0, "distance": 0.10}
    else:
        effective_weights = weights or {"stars": 0.30, "sentiment": 0.30, "category": 0.30, "distance": 0.10}

    # Normalize star rating: 0..5 -> 0..1
    stars = float(business.get("stars", 0.0))
    star_norm = max(0.0, min(stars / 5.0, 1.0))

    # Normalize VADER sentiment: -1..1 -> 0..1
    raw_sentiment = business.get("avgSentiment")
    if raw_sentiment is None:
        raw_sentiment = 0.0
    sentiment_norm = max(0.0, min((float(raw_sentiment) + 1.0) / 2.0, 1.0))

    # Category match boost: 0..1
    cat_norm = category_match_boost(business.get("categories", []), user_category_counts)

    # Normalized distance proximity: 0..1 (closer is higher)
    dist_norm = max(0.0, 1.0 - min(float(distance_m) / max_distance_norm_m, 1.0))

    final_score = (
        effective_weights["stars"] * star_norm +
        effective_weights["sentiment"] * sentiment_norm +
        effective_weights["category"] * cat_norm +
        effective_weights["distance"] * dist_norm
    )

    return round(float(final_score), 4)


def explain_recommendation(
    business: Dict[str, Any],
    distance_m: float,
    user_category_counts: Counter
) -> str:
    """
    Generate an explainable, human-readable reason string justifying
    why this business is recommended to the user.
    """
    reasons = []

    # Proximity reason
    if distance_m < 1000:
        reasons.append(f"{int(distance_m)}m away")
    else:
        reasons.append(f"{distance_m / 1000.0:.1f}km away")

    # Star rating
    stars = business.get("stars", 0.0)
    reasons.append(f"{stars} stars")

    # Sentiment reason
    avg_sentiment = business.get("avgSentiment", 0.0) or 0.0
    if avg_sentiment >= 0.7:
        reasons.append("rave customer reviews")
    elif avg_sentiment >= 0.3:
        reasons.append("mostly positive reviews")
    elif avg_sentiment < 0.0:
        reasons.append("mixed customer reviews")

    # Personalization match reason
    matched = [c for c in business.get("categories", []) if c in user_category_counts]
    if matched:
        top_matched = sorted(matched, key=lambda c: user_category_counts[c], reverse=True)[0]
        reasons.append(f"matches your love for {top_matched}")
    elif not user_category_counts:
        reasons.append("popular nearby choice (cold-start)")

    return " | ".join(reasons)
