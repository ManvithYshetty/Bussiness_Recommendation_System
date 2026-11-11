# YelpNoSQL: Location-Aware Business Recommendation System Using MongoDB

## 1. Project Summary
YelpNoSQL is a MongoDB-based system that recommends local businesses (restaurants, cafes, pubs, etc.) to a user based on three combined signals:

1. **Geospatial filtering** — narrows the full dataset down to businesses near the user's location.
2. **Sentiment-based quality scoring** — enriches each nearby business with a quality signal derived from review text (not just star ratings).
3. **Personalized recommendation logic** — re-ranks the filtered, enriched list based on the user's past preferences (or falls back to popularity for new users).

This is a college mini project for a **NoSQL Database** subject. The goal is not just to build a working app, but to clearly demonstrate NoSQL concepts (document modeling, geospatial indexing, aggregation pipelines, schema flexibility) that would be awkward or expensive to implement in a relational database.

## 2. Dataset
- **Source**: Yelp Open Dataset (official site or Kaggle mirror `yelp-dataset/yelp-dataset`)
- **Files used**: `business.json`, `review.json`, `user.json` (checkin.json optional, not core to MVP)
- **Scope**: Filtered to ONE city and 1–2 broad categories (e.g., Restaurants, plus one secondary category like Cafes or Pubs to demonstrate category-agnostic design) to keep the project manageable within a mini-project timeline.
- **Note on terminology**: Yelp calls every listed place a "business" — this includes restaurants, cafes, gyms, salons, etc. Our system is category-agnostic by design; the demo focuses on restaurants but is not hardcoded to them.

## 3. Why MongoDB / Why NoSQL
| Requirement | Relational (SQL) pain point | MongoDB advantage |
|---|---|---|
| Variable business attributes (WiFi, parking, delivery — different per category) | Needs many nullable columns or extra join tables (EAV pattern) | Store as a flexible embedded sub-document; no schema migration needed |
| Geospatial "find nearby" queries | Needs extensions (e.g., PostGIS) not native to core SQL | Native `2dsphere` index + `$near` / `$geoNear` operators |
| Unstructured review text for sentiment analysis | Text fields are supported but there's no natural way to enrich/aggregate them without extra pipelines | Store text directly on the document; use aggregation pipeline to compute/join enrichments |
| Rapid schema evolution across business types (gym vs restaurant vs salon) | Rigid schema, ALTER TABLE required | Polymorphic documents in the same collection |

This comparison should appear in the final report as the core "why NoSQL" justification.

## 4. High-Level Architecture

```
                 ┌────────────────────┐
 Raw Yelp JSON → │  Filtering/Cleaning │ → Filtered JSON (city + categories)
                 └────────────────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │   MongoDB Ingest    │ → businesses / reviews / users collections
                 └────────────────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │  Sentiment Batch    │ → adds sentiment_score (per review)
                 │      Job            │    and avgSentiment (per business)
                 └────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────┐
       │        Combined Query Pipeline         │
       │  1. Geo-filter ($geoNear + category)   │
       │  2. Enrich (join avgSentiment, stars)  │
       │  3. Re-rank (personalization boost)    │
       │  4. Explain (why this was recommended) │
       └───────────────────────────────────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │  Streamlit Frontend │ → search bar, filters, ranked results
                 └────────────────────┘
```

## 5. Project Phases (map to docs in this folder)
| Phase | Doc | What it covers |
|---|---|---|
| 0 | 01-setup.md | Environment, MongoDB, Python deps |
| 1 | 02-data-preparation.md | Filtering & cleaning raw Yelp JSON |
| 2 | 03-database-schema.md | Collections, embed vs reference, indexes |
| 3 | 04-geospatial-module.md | `$geoNear` queries |
| 4 | 05-sentiment-module.md | Sentiment scoring batch job |
| 5 | 06-recommendation-module.md | Content-based scoring + cold start |
| 6 | 07-combined-pipeline.md | How the three stages chain together |
| 7 | 08-frontend.md | Streamlit UI |
| 8 | 09-viva-and-report-notes.md | Talking points, uniqueness, concepts learned |

## 6. Non-Goals (explicitly out of scope for this mini project)
- No collaborative filtering (matrix factorization / ML-based CF) — content-based only, to keep it explainable and fast to build.
- No real-time review ingestion — sentiment scoring runs as a batch job, not live per new review.
- No distributed MongoDB cluster / sharding demo — single-node MongoDB is sufficient; CAP theorem trade-offs are discussed conceptually in the report only.
- No authentication/user accounts system — a mock/sample user ID is used to demonstrate personalization.

## 7. Success Criteria (what "done" looks like)
1. MongoDB populated with filtered Yelp data across 2 categories, correct indexes created.
2. Geo-search returns correct nearby results, verifiably faster with the `2dsphere` index than without (measurable via `.explain()`).
3. Every business has a computed `avgSentiment` field.
4. Recommendation endpoint returns a ranked list with an explanation string per result.
5. Streamlit app demonstrates the full flow live, across at least 2 business categories.
6. Report contains schema design justification, index performance comparison, and concepts-learned mapping.
