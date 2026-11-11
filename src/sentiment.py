"""
05 — Sentiment Scoring Module (src/sentiment.py)
Performs offline batch sentiment scoring of review text using VADER NLP
and aggregates average sentiment scores onto business documents in MongoDB.
"""

import os
import sys
import argparse
from typing import Dict, Any, Optional
from datetime import datetime
import math

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pymongo import UpdateOne
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from src.db import get_db

# Initialize VADER Sentiment Analyzer singleton
_analyzer = None


def get_sentiment_analyzer() -> SentimentIntensityAnalyzer:
    """Return a singleton SentimentIntensityAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def score_text(text: str) -> float:
    """
    Compute VADER compound sentiment score for a given text.
    Returns a float between -1.0 (extremely negative) and +1.0 (extremely positive).
    """
    if not text or not isinstance(text, str):
        return 0.0
    analyzer = get_sentiment_analyzer()
    scores = analyzer.polarity_scores(text)
    return round(float(scores.get("compound", 0.0)), 4)


def compute_recency_weight(date_str: Optional[str], half_life_days: float = 180.0) -> float:
    """
    Optional enhancement: compute exponential decay weight based on review age.
    Recent reviews carry more weight.
    """
    if not date_str:
        return 1.0
    try:
        review_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
        age_days = max(0, (datetime.now() - review_date).days)
        return math.exp(-age_days / half_life_days)
    except Exception:
        return 1.0


def score_reviews_batch(db, batch_size: int = 1000) -> int:
    """
    Find reviews where sentiment_score is null (or score all if force is specified),
    compute compound score with VADER, and bulk update MongoDB.
    """
    query = {"sentiment_score": None}
    total_reviews = db.reviews.count_documents(query)
    print(f"[sentiment] Found {total_reviews} reviews to score.")

    if total_reviews == 0:
        return 0

    cursor = db.reviews.find(query)
    operations = []
    updated_count = 0

    for review in cursor:
        text = review.get("text", "")
        compound = score_text(text)
        operations.append(
            UpdateOne(
                {"_id": review["_id"]},
                {"$set": {"sentiment_score": compound}}
            )
        )

        if len(operations) >= batch_size:
            res = db.reviews.bulk_write(operations)
            updated_count += res.modified_count
            print(f"[sentiment] Scored & updated {updated_count}/{total_reviews} reviews...")
            operations = []

    if operations:
        res = db.reviews.bulk_write(operations)
        updated_count += res.modified_count

    print(f"[sentiment] Completed review scoring: {updated_count} reviews updated.")
    return updated_count


def aggregate_business_sentiments(db) -> int:
    """
    Run MongoDB aggregation pipeline to compute average sentiment per business,
    then update avgSentiment on businesses collection.
    """
    print("[sentiment] Aggregating average sentiment scores per business...")
    pipeline = [
        {"$match": {"sentiment_score": {"$ne": None}}},
        {
            "$group": {
                "_id": "$business_id",
                "avgSentiment": {"$avg": "$sentiment_score"},
                "scored_reviews": {"$sum": 1}
            }
        }
    ]

    aggregates = list(db.reviews.aggregate(pipeline))
    print(f"[sentiment] Computed sentiment aggregates for {len(aggregates)} businesses.")

    if not aggregates:
        print("[sentiment] No sentiment scores available to aggregate.")
        return 0

    operations = []
    for agg in aggregates:
        biz_id = agg["_id"]
        avg_sentiment = round(float(agg["avgSentiment"]), 4)
        operations.append(
            UpdateOne(
                {"_id": biz_id},
                {
                    "$set": {
                        "avgSentiment": avg_sentiment,
                        "sentimentReviewCount": agg["scored_reviews"]
                    }
                }
            )
        )

    if operations:
        res = db.businesses.bulk_write(operations)
        print(f"[sentiment] Updated {res.modified_count} businesses with avgSentiment.")
        return res.modified_count
    return 0


def run_sentiment_pipeline(force: bool = False):
    """Run full sentiment scoring and aggregation workflow."""
    db = get_db()

    if force:
        print("[sentiment] Force flag enabled: resetting all sentiment_score fields to null.")
        db.reviews.update_many({}, {"$set": {"sentiment_score": None}})

    score_reviews_batch(db)
    aggregate_business_sentiments(db)

    # Sanity verification
    sample_biz = list(db.businesses.find({}, {"name": 1, "stars": 1, "avgSentiment": 1}).limit(5))
    print("\n[sentiment] --- Sample Business Sentiment Scores ---")
    for b in sample_biz:
        print(f"  {b.get('name')}: stars={b.get('stars')}, avgSentiment={b.get('avgSentiment')}")
    print("[sentiment] Sentiment processing finished successfully.\n")


def main():
    parser = argparse.ArgumentParser(description="Run VADER sentiment analysis batch job.")
    parser.add_argument("--force", action="store_true", help="Re-score all reviews even if sentiment_score exists")
    args = parser.parse_args()

    run_sentiment_pipeline(force=args.force)


if __name__ == "__main__":
    main()
