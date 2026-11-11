"""
07 — Combined Pipeline Module (src/pipeline.py)
Unified pipeline chaining:
  Stage 1: Geospatial filter ($geoNear using 2dsphere index)
  Stage 2: Sentiment enrichment (reads precomputed avgSentiment)
  Stage 3: Personalized re-ranking (content-based scoring)
  Stage 4: Explainability annotation (natural language reason generation)
"""

import os
import sys
import time
import argparse
from typing import List, Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import get_db
from src.geo_search import find_nearby_with_distance
from src.recommend import (
    get_user_preferred_categories,
    compute_final_score,
    explain_recommendation,
)


def recommend_businesses(
    db,
    lng: float,
    lat: float,
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    max_distance_m: int = 3000,
    min_stars: Optional[float] = None,
    top_n: int = 10,
    weights: Optional[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Execute the unified 4-stage recommendation pipeline:
      1. Candidate generation: Geo-filter businesses within max_distance_m
      2. Sentiment enrichment: avgSentiment is already embedded in businesses collection
      3. Personalization: Re-rank candidates based on user review profile and weights
      4. Explanation: Attach natural-language justification for each top recommendation
    
    Returns a list of top_n recommended businesses with 'final_score', 'distance_m', and 'explanation'.
    """
    # Stage 1: Geospatial Candidate Retrieval (with computed distance)
    candidates = find_nearby_with_distance(
        db,
        lng=lng,
        lat=lat,
        max_distance_m=max_distance_m,
        category=category,
        min_stars=min_stars,
        limit=100
    )

    if not candidates:
        return []

    # Derive user taste profile (empty Counter for guest / cold-start)
    user_category_counts = get_user_preferred_categories(db, user_id)

    # Stage 2 + 3 + 4: Score, Re-rank, and Explain
    scored_results = []
    for biz in candidates:
        distance_m = biz.get("distance_m", 0.0)
        final_score = compute_final_score(
            business=biz,
            distance_m=distance_m,
            user_category_counts=user_category_counts,
            weights=weights,
            max_distance_norm_m=float(max_distance_m)
        )
        explanation = explain_recommendation(biz, distance_m, user_category_counts)

        # Create enriched result copy
        item = dict(biz)
        item["final_score"] = final_score
        item["explanation"] = explanation
        scored_results.append(item)

    # Re-rank strictly by final_score descending
    scored_results.sort(key=lambda x: x["final_score"], reverse=True)

    return scored_results[:top_n]


def main():
    parser = argparse.ArgumentParser(description="Run the end-to-end recommendation pipeline.")
    parser.add_argument("--lng", type=float, default=-75.1652, help="User longitude (default: Center City)")
    parser.add_argument("--lat", type=float, default=39.9526, help="User latitude (default: Center City)")
    parser.add_argument("--user-id", type=str, default="usr_alex_italian_fan", help="User ID or 'cold-start'")
    parser.add_argument("--category", type=str, default=None, help="Optional category filter")
    parser.add_argument("--radius", type=int, default=3000, help="Search radius in meters")
    parser.add_argument("--top-n", type=int, default=5, help="Number of recommendations to return")
    args = parser.parse_args()

    db = get_db()
    user_id = None if args.user_id in ["cold-start", "guest", "none", "None"] else args.user_id

    print(f"\n==================================================")
    print(f" YelpNoSQL: End-to-End Recommendation Pipeline")
    print(f"==================================================")
    print(f" User       : {user_id or 'Cold Start (Guest User)'}")
    print(f" Location   : [{args.lng}, {args.lat}]")
    print(f" Radius     : {args.radius} meters")
    print(f" Category   : {args.category or 'All Categories'}")
    print(f"--------------------------------------------------")

    start_time = time.perf_counter()
    recommendations = recommend_businesses(
        db,
        lng=args.lng,
        lat=args.lat,
        user_id=user_id,
        category=args.category,
        max_distance_m=args.radius,
        top_n=args.top_n
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    print(f" Pipeline execution completed in {elapsed_ms:.2f} ms")
    print(f" Top {len(recommendations)} Recommendations:\n")

    for rank, rec in enumerate(recommendations, 1):
        name = rec.get("name")
        stars = rec.get("stars")
        sentiment = rec.get("avgSentiment")
        score = rec.get("final_score")
        dist = rec.get("distance_m", 0.0)
        expl = rec.get("explanation")
        cats = ", ".join(rec.get("categories", []))

        print(f" #{rank}: {name}")
        print(f"     Score: {score:.4f} | Stars: {stars} stars | Sentiment: {sentiment} | Distance: {dist:.0f}m")
        print(f"     Categories : {cats}")
        print(f"     Explanation: {expl}\n")


if __name__ == "__main__":
    main()
