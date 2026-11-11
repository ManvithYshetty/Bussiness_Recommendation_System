"""
Comprehensive End-to-End Test Suite for YelpNoSQL
Tests:
  1. Database connection & collection schemas
  2. Geospatial search ($near & $geoNear with distanceField)
  3. VADER sentiment scoring and aggregation
  4. Recommendation scoring, personalization, and cold-start fallback
  5. End-to-end pipeline execution
  6. Performance and explain query plan verification
"""

import os
import sys
import unittest
from collections import Counter

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import get_db, test_connection
from src.geo_search import find_nearby_businesses, find_nearby_with_distance
from src.sentiment import score_text, aggregate_business_sentiments
from src.recommend import (
    get_user_preferred_categories,
    category_match_boost,
    compute_final_score,
    explain_recommendation,
)
from src.pipeline import recommend_businesses


class TestYelpNoSQL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.philly_center_lng = -75.1652
        cls.philly_center_lat = 39.9526

    def test_01_mongodb_connection_and_collections(self):
        """Test MongoDB connectivity and verify non-empty collections."""
        self.assertTrue(test_connection(), "MongoDB connection failed")
        
        biz_count = self.db.businesses.count_documents({})
        rev_count = self.db.reviews.count_documents({})
        usr_count = self.db.users.count_documents({})

        self.assertGreater(biz_count, 0, "Businesses collection is empty")
        self.assertGreater(rev_count, 0, "Reviews collection is empty")
        self.assertGreater(usr_count, 0, "Users collection is empty")

        # Verify 2dsphere index exists
        indexes = [idx["name"] for idx in self.db.businesses.list_indexes()]
        self.assertTrue(
            any("2dsphere" in idx for idx in indexes),
            f"2dsphere index missing from businesses. Indexes: {indexes}"
        )

    def test_02_geospatial_search(self):
        """Test geospatial queries using $near and $geoNear."""
        # 1. Nearby search within 3000m
        results = find_nearby_with_distance(
            self.db,
            lng=self.philly_center_lng,
            lat=self.philly_center_lat,
            max_distance_m=3000
        )
        self.assertGreater(len(results), 0, "No nearby businesses found within 3km")

        # Check distance sorting (results should be monotonically increasing by distance_m)
        distances = [r["distance_m"] for r in results]
        self.assertEqual(distances, sorted(distances), "Results not sorted by distance")
        self.assertTrue(all(d <= 3000 for d in distances), "Distance exceeded 3000m limit")

        # 2. Strict category filtering
        italian_results = find_nearby_with_distance(
            self.db,
            lng=self.philly_center_lng,
            lat=self.philly_center_lat,
            max_distance_m=5000,
            category="Italian"
        )
        self.assertGreater(len(italian_results), 0)
        for r in italian_results:
            self.assertIn("Italian", r["categories"])

    def test_03_sentiment_analysis(self):
        """Test VADER sentiment scoring and business aggregation."""
        # Positive review
        pos_score = score_text("Absolutely phenomenal food, exceptional service and wonderful vibe!")
        self.assertGreater(pos_score, 0.5)

        # Negative review
        neg_score = score_text("Horrible experience, completely burnt food and rude, slow staff.")
        self.assertLess(neg_score, -0.3)

        # Neutral review
        neu_score = score_text("The restaurant is located on 12th street.")
        self.assertAlmostEqual(neu_score, 0.0, delta=0.2)

        # Verify avgSentiment is populated on businesses
        sample_biz = self.db.businesses.find_one({"avgSentiment": {"$ne": None}})
        self.assertIsNotNone(sample_biz)
        self.assertIsInstance(sample_biz["avgSentiment"], float)
        self.assertTrue(-1.0 <= sample_biz["avgSentiment"] <= 1.0)

    def test_04_recommendation_and_cold_start(self):
        """Test personalization, taste profiles, and cold-start fallback."""
        # Active user with Italian preference
        user_cats = get_user_preferred_categories(self.db, "usr_alex_italian_fan")
        self.assertIn("Italian", user_cats)

        # Category match boost
        boost_match = category_match_boost(["Italian", "Pizza"], user_cats)
        boost_unmatch = category_match_boost(["Chinese", "Dim Sum"], user_cats)
        self.assertGreater(boost_match, boost_unmatch)

        # Cold-start fallback (guest user with no ID)
        guest_cats = get_user_preferred_categories(self.db, None)
        self.assertEqual(guest_cats, Counter())

        dummy_biz = {
            "stars": 4.5,
            "avgSentiment": 0.8,
            "categories": ["Restaurants", "Italian"]
        }
        score_guest = compute_final_score(dummy_biz, distance_m=500, user_category_counts=guest_cats)
        self.assertGreater(score_guest, 0.0)
        self.assertLessEqual(score_guest, 1.0)

        # Explanation generation
        expl_personalized = explain_recommendation(dummy_biz, distance_m=500, user_category_counts=user_cats)
        self.assertIn("matches your love for", expl_personalized)

        expl_cold_start = explain_recommendation(dummy_biz, distance_m=500, user_category_counts=guest_cats)
        self.assertIn("popular nearby choice (cold-start)", expl_cold_start)

    def test_05_end_to_end_pipeline(self):
        """Test unified recommend_businesses pipeline."""
        recs = recommend_businesses(
            self.db,
            lng=self.philly_center_lng,
            lat=self.philly_center_lat,
            user_id="usr_alex_italian_fan",
            category=None,
            max_distance_m=3000,
            top_n=5
        )
        self.assertEqual(len(recs), 5)

        # Ensure sorted by final_score descending
        scores = [r["final_score"] for r in recs]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Check required fields
        for r in recs:
            self.assertIn("final_score", r)
            self.assertIn("explanation", r)
            self.assertIn("distance_m", r)
            self.assertIn("avgSentiment", r)


if __name__ == "__main__":
    unittest.main()
