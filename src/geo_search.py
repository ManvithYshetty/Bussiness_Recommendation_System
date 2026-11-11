"""
04 — Geospatial Search Module (src/geo_search.py)
Performs location-aware business searches using MongoDB's 2dsphere index,
supporting both $near queries and $geoNear aggregation pipelines with computed distances.
"""

import os
import sys
import argparse
from typing import List, Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import get_db

# Default Philadelphia Center City Coordinates: [longitude, latitude]
DEFAULT_CENTER_CITY_LNG = -75.1652
DEFAULT_CENTER_CITY_LAT = 39.9526


def find_nearby_businesses(
    db,
    lng: float,
    lat: float,
    max_distance_m: int = 3000,
    category: Optional[str] = None,
    min_stars: Optional[float] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Query MongoDB using the $near operator on businesses.location.
    NOTE: GeoJSON coordinates order is strictly [longitude, latitude].
    Requires a '2dsphere' index on businesses.location.
    """
    query: Dict[str, Any] = {
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [float(lng), float(lat)]
                },
                "$maxDistance": int(max_distance_m)
            }
        }
    }

    if category:
        query["categories"] = category

    if min_stars is not None:
        query["stars"] = {"$gte": float(min_stars)}

    cursor = db.businesses.find(query).limit(limit)
    return list(cursor)


def find_nearby_with_distance(
    db,
    lng: float,
    lat: float,
    max_distance_m: int = 3000,
    category: Optional[str] = None,
    min_stars: Optional[float] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Query MongoDB using the $geoNear aggregation stage to return businesses
    along with their exact computed distance in meters ('distance_m').
    IMPORTANT: $geoNear MUST be the first stage in an aggregation pipeline!
    """
    match_query: Dict[str, Any] = {}
    if category:
        match_query["categories"] = category
    if min_stars is not None:
        match_query["stars"] = {"$gte": float(min_stars)}

    pipeline = [
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [float(lng), float(lat)]
                },
                "distanceField": "distance_m",
                "maxDistance": int(max_distance_m),
                "spherical": True,
                "query": match_query
            }
        },
        {"$limit": limit}
    ]

    results = list(db.businesses.aggregate(pipeline))
    return results


def main():
    parser = argparse.ArgumentParser(description="Test geospatial search queries in MongoDB.")
    parser.add_argument("--lng", type=float, default=DEFAULT_CENTER_CITY_LNG, help="Longitude (default: -75.1652)")
    parser.add_argument("--lat", type=float, default=DEFAULT_CENTER_CITY_LAT, help="Latitude (default: 39.9526)")
    parser.add_argument("--radius", type=int, default=2500, help="Search radius in meters (default: 2500)")
    parser.add_argument("--category", type=str, default=None, help="Optional category filter (e.g. Italian, Cafes)")
    parser.add_argument("--min-stars", type=float, default=None, help="Minimum star rating")
    args = parser.parse_args()

    db = get_db()
    print(f"[geo_search] Searching near [{args.lng}, {args.lat}] with radius={args.radius}m, category={args.category}...")

    results = find_nearby_with_distance(
        db,
        lng=args.lng,
        lat=args.lat,
        max_distance_m=args.radius,
        category=args.category,
        min_stars=args.min_stars
    )

    print(f"[geo_search] Found {len(results)} businesses within {args.radius}m:\n")
    for idx, b in enumerate(results, 1):
        dist = b.get("distance_m", 0.0)
        coords = b.get("location", {}).get("coordinates", [])
        print(f"  {idx}. {b.get('name')} ({dist:.0f}m away)")
        print(f"     Stars: {b.get('stars')} stars | avgSentiment: {b.get('avgSentiment')} | Categories: {b.get('categories')}")
        print(f"     Coordinates: {coords}")


if __name__ == "__main__":
    main()
