# 05 — Sentiment Scoring Module (`src/sentiment.py`)

## 1. Purpose
Convert review text into a numeric quality signal that's richer than just the star rating — a business can have 4 stars overall but recent reviews might mention declining service, which sentiment analysis over the actual text can surface.

This runs as an **offline batch job**, not live per-request — sentiment doesn't need to be recalculated every time a user searches.

## 2. Tool Choice: VADER
VADER (Valence Aware Dictionary and sEntiment Reasoner) is chosen because:
- No training required (unlike a custom ML model) — fits a mini project timeline
- Works well on short, informal text (review-style writing), which is exactly what Yelp reviews look like
- Fast — can process tens of thousands of reviews in seconds, no GPU needed

```python
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()
score = analyzer.polarity_scores("Best slice in the city!")["compound"]
# compound score ranges from -1 (very negative) to +1 (very positive)
```

## 3. Batch Job Steps
1. Query all reviews where `sentiment_score` is `null`.
2. For each review, compute `analyzer.polarity_scores(text)["compound"]`.
3. Update the review document with the computed score:
```python
db.reviews.update_one(
    {"_id": review["_id"]},
    {"$set": {"sentiment_score": score}}
)
```
   For performance on larger batches, use `bulk_write` with `UpdateOne` operations instead of one `update_one` call per review.

4. After all reviews are scored, compute the **average sentiment per business** using an aggregation pipeline:
```python
pipeline = [
    {"$group": {"_id": "$business_id", "avgSentiment": {"$avg": "$sentiment_score"}}}
]
results = db.reviews.aggregate(pipeline)

for r in results:
    db.businesses.update_one(
        {"_id": r["_id"]},
        {"$set": {"avgSentiment": r["avgSentiment"]}}
    )
```

## 4. Optional Enhancement: Recency-Weighted Sentiment
Instead of a plain average, weight recent reviews more heavily so a business's score reflects its *current* quality, not its history:
```python
import math
from datetime import datetime

def recency_weight(review_date, half_life_days=180):
    age_days = (datetime.now() - review_date).days
    return math.exp(-age_days / half_life_days)
```
Then compute a weighted average instead of a plain `$avg` in the aggregation (can be done in Python after fetching, or via `$multiply`/`$sum` stages in the pipeline). Mention this in the report as a demonstration of understanding real-world recommendation system design — most basic projects skip this.

## 5. Testing This Module
1. Manually check a few clearly positive/negative reviews against their computed scores (sanity check the numbers make sense).
2. Confirm every review in the filtered dataset ends up with a non-null `sentiment_score` after the batch job runs.
3. Confirm every business ends up with a non-null `avgSentiment` after the aggregation step.
4. Spot-check: a business with mostly 5-star reviews should have `avgSentiment` clearly positive (typically > 0.3), and vice versa for low-starred businesses — if wildly inconsistent, check for text-cleaning issues (Phase 1).

## 6. Output of This Module
Every business document now has a populated `avgSentiment` field, ready to be used as a ranking input in Phase 5/6.
