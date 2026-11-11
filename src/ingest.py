"""
03 — MongoDB Ingestion and Indexing Module (src/ingest.py)
Loads filtered Yelp datasets into MongoDB and creates required indexes
including the crucial 2dsphere index for location-aware queries.
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pymongo import ASCENDING, TEXT, GEOSPHERE
from src.db import get_db

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "filtered")


def load_json_lines(file_path: str) -> List[Dict[str, Any]]:
    """Load JSON-lines formatted file into a list of dictionaries."""
    records = []
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                records.append(json.loads(line_str))
    return records


def ingest_data(data_dir: str = DATA_DIR, drop_existing: bool = True):
    """
    Ingest businesses, reviews, and users into MongoDB and build indexes.
    """
    db = get_db()
    print(f"[ingest] Connected to database '{db.name}'.")

    if drop_existing:
        print("[ingest] Dropping existing collections ('businesses', 'reviews', 'users')...")
        db.businesses.drop()
        db.reviews.drop()
        db.users.drop()

    biz_file = os.path.join(data_dir, "business_filtered.json")
    rev_file = os.path.join(data_dir, "review_filtered.json")
    usr_file = os.path.join(data_dir, "user_filtered.json")

    # Ingest Businesses
    businesses = load_json_lines(biz_file)
    if businesses:
        db.businesses.insert_many(businesses)
        print(f"[ingest] Inserted {len(businesses)} documents into 'businesses'.")
    else:
        print("[ingest] Warning: No business documents found to insert.")

    # Ingest Reviews
    reviews = load_json_lines(rev_file)
    if reviews:
        db.reviews.insert_many(reviews)
        print(f"[ingest] Inserted {len(reviews)} documents into 'reviews'.")
    else:
        print("[ingest] Warning: No review documents found to insert.")

    # Ingest Users
    users = load_json_lines(usr_file)
    if users:
        db.users.insert_many(users)
        print(f"[ingest] Inserted {len(users)} documents into 'users'.")
    else:
        print("[ingest] Warning: No user documents found to insert.")

    # Create Indexes
    print("[ingest] Creating indexes...")
    # Geospatial index — required for $near / $geoNear queries
    idx_geo = db.businesses.create_index([("location", GEOSPHERE)], name="idx_businesses_location_2dsphere")
    print(f"  - Created {idx_geo} on businesses.location")

    # Category filtering index
    idx_cat = db.businesses.create_index([("categories", ASCENDING)], name="idx_businesses_categories")
    print(f"  - Created {idx_cat} on businesses.categories")

    # Review lookup indexes
    idx_rev_biz = db.reviews.create_index([("business_id", ASCENDING)], name="idx_reviews_business_id")
    print(f"  - Created {idx_rev_biz} on reviews.business_id")

    idx_rev_usr = db.reviews.create_index([("user_id", ASCENDING)], name="idx_reviews_user_id")
    print(f"  - Created {idx_rev_usr} on reviews.user_id")

    # Text index for review keywords
    idx_rev_text = db.reviews.create_index([("text", TEXT)], name="idx_reviews_text_search")
    print(f"  - Created {idx_rev_text} on reviews.text")

    # Verification summary
    print("\n[ingest] --- Ingestion Summary ---")
    print(f"  Businesses count : {db.businesses.count_documents({})}")
    print(f"  Reviews count    : {db.reviews.count_documents({})}")
    print(f"  Users count      : {db.users.count_documents({})}")

    print("\n[ingest] --- Active Indexes ---")
    for col_name in ["businesses", "reviews", "users"]:
        col = db[col_name]
        index_names = [idx["name"] for idx in col.list_indexes()]
        print(f"  {col_name}: {index_names}")

    print("[ingest] Ingestion and indexing completed successfully!\n")


def main():
    parser = argparse.ArgumentParser(description="Ingest filtered Yelp data into MongoDB.")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Path to directory containing filtered JSON files")
    parser.add_argument("--no-drop", action="store_true", help="Do not drop existing collections before ingesting")
    args = parser.parse_args()

    ingest_data(data_dir=args.data_dir, drop_existing=not args.no_drop)


if __name__ == "__main__":
    main()
