# 09 — Viva & Report Notes

## 1. One-Line Project Description
"YelpNoSQL filters the Yelp Open Dataset by user location using MongoDB's geospatial indexing, enriches results with sentiment scores computed from review text, and re-ranks them using content-based personalization — combining all three into one query pipeline rather than three separate features."

## 2. What's Unique About This Project (not the dataset itself)
The Yelp dataset is a standard, widely-used public dataset — it is NOT the source of uniqueness. The uniqueness is:
1. Combining geospatial filtering + sentiment scoring + personalized recommendation into a single pipeline where each stage's output feeds the next.
2. Being explicit and correct about which stages **reduce** the dataset (only geo-filtering) versus which stages **enrich/rank** it (sentiment, recommendation) — most basic projects conflate these.
3. Explainable recommendations (a short reason string per result), rather than a bare ranked list.
4. Explicit cold-start handling for new users with no history.
5. Category-agnostic design — demoed across 2+ business categories (e.g., restaurants and cafes), not hardcoded to one type.

## 3. Concepts Learned / Applied — Mapping Table
| NoSQL Concept | Where applied in this project |
|---|---|
| Document modeling (embed vs reference) | Business attributes/categories embedded; reviews referenced via `business_id` |
| Geospatial indexing | `2dsphere` index + `$near`/`$geoNear` for nearby business search |
| Aggregation pipeline | Computing `avgSentiment` per business via `$group`/`$avg`; `$geoNear` aggregation stage |
| Schema flexibility / polymorphic documents | Different business types (restaurant, cafe, gym) coexist in one collection with different attribute sets |
| Unstructured data handling | Review text stored and processed for sentiment, not just numeric fields |
| Indexing & performance | `.explain()` comparison of query plans with/without `2dsphere` index |
| CAP theorem (conceptual, report-only) | Discuss MongoDB's availability/flexibility trade-offs vs strict relational consistency |

## 4. "Why Not SQL?" — Ready Answer
"A relational schema would need a rigid businesses table with many nullable columns to handle varying attributes across business types, or a separate EAV-style attributes table requiring extra joins. Geospatial 'find nearby' queries would need an extension like PostGIS, which isn't part of core SQL. MongoDB gives us native geospatial indexing and lets each business document carry only the attributes relevant to its type — no schema migrations needed when adding a new business category."

## 5. Anticipated Viva Questions & Answers
**Q: Is this just a restaurant recommender?**
A: No — Yelp's dataset covers any local business (cafes, bars, gyms, salons). The system's logic is category-agnostic; we demo it across at least two categories to prove this.

**Q: What if a user has no review history?**
A: Cold-start fallback — the category-match component of the score contributes zero, and ranking falls back to star rating, sentiment, and distance only.

**Q: Does geo-search/sentiment/recommendation each filter the data?**
A: No — only geo-filtering reduces the candidate set. Sentiment scoring enriches existing documents with a precomputed field. Recommendation logic re-ranks the same filtered set; it doesn't remove anything.

**Q: Why VADER instead of a deep learning sentiment model?**
A: VADER requires no training data or GPU, performs well on short informal review-style text, and fits the project's timeline — a reasonable, justifiable engineering trade-off for a mini project.

**Q: Why content-based filtering and not collaborative filtering?**
A: Collaborative filtering needs a large, dense user-item ratings matrix to avoid sparsity issues, and its recommendations are harder to explain. Content-based filtering is simpler to implement, explainable, and works even with a filtered (smaller) dataset.

**Q: How do you prove the index actually helps?**
A: `.explain("executionStats")` run with and without the `2dsphere` index — shows `COLLSCAN` (slow, full scan) vs `IXSCAN`/`GEO_NEAR` (fast, indexed) execution plans, with measurable `executionTimeMillis` difference.

## 6. Report Structure Suggestion
1. Introduction & Problem Statement
2. Dataset Description (Yelp Open Dataset, filtering approach)
3. Why NoSQL / Why MongoDB (comparison table from `00-overview.md`)
4. System Architecture (diagram from `00-overview.md`)
5. Schema Design (embed vs reference justification from `03-database-schema.md`)
6. Implementation — Geospatial Module
7. Implementation — Sentiment Module
8. Implementation — Recommendation Module
9. Combined Pipeline & Explainability
10. Index Performance Evaluation (`.explain()` screenshots, before/after)
11. Results & Demo Screenshots (across 2+ categories)
12. Concepts Learned (mapping table from section 3 above)
13. Limitations & Future Work (mention: no live ingestion, no distributed cluster demo, content-based only)
14. Conclusion

## 7. Limitations to Proactively Mention (shows maturity, avoids "gotcha" questions)
- Sentiment analysis runs as a batch job, not real-time on new reviews.
- Recommendation is content-based only — no collaborative filtering.
- Single-node MongoDB — no sharding/replica set demonstrated (CAP theorem discussed conceptually only).
- Dataset filtered to one city/category subset — not the full Yelp dataset, for practical scope reasons.
