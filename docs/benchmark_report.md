
# MongoDB Index & Performance Benchmark Summary

### 1. Geospatial Indexing Comparison
| Metric | With `2dsphere` Index | Without `2dsphere` Index |
| :--- | :--- | :--- |
| **Winning Stage** | `GEO_NEAR_2DSPHERE` | **FAILED** (OperationFailure) |
| **Status** | High-performance spatial traversal | Query rejected by engine |
| **Viva Takeaway** | MongoDB *strictly enforces* `2dsphere` index presence for `$near` and `$geoNear`. |

### 2. Category Filter Query (`categories: "Italian"`)
| Metric | With Index (`IXSCAN`) | Without Index (`COLLSCAN`) |
| :--- | :--- | :--- |
| **Plan Stage** | `FETCH` -> `IXSCAN` | `COLLSCAN` |
| **Keys Examined** | 4 | 0 (no index) |
| **Docs Examined** | 4 | 20 (100% of collection) |
| **Speedup Ratio** | Instant index seek | Full table scan |

### 3. Unified Recommendation Pipeline Latency
- **End-to-End Latency**: Avg **11.84 ms** (Min: 7.04 ms, Max: 44.91 ms)
- **Pipeline Stages**: `$geoNear` spatial query -> VADER avgSentiment enrichment -> User taste profile matching -> Score weighting & natural-language explanations.
