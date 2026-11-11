# 08 — Frontend (`app.py`, Streamlit)

## 1. Purpose
A minimal but functional UI to demo the full pipeline live — this does not need to be visually elaborate, it needs to clearly show the system working end-to-end in front of an evaluator.

## 2. Layout
1. **Header**: Project title "YelpNoSQL: Location-Aware Business Recommendation System"
2. **Sidebar inputs**:
   - Location: either two number inputs (lat/lng) for simplicity, or a dropdown of a few preset demo locations within the filtered city (more reliable for a live demo than relying on GPS/browser geolocation)
   - Category dropdown: populated dynamically from distinct categories in the `businesses` collection (proves category-agnostic design)
   - User ID input/dropdown: a few preset sample user IDs (one with clear history, one "new user" for the cold-start demo)
   - Max distance slider (e.g., 500m–5km)
3. **Main panel — Results**:
   - Ranked list of businesses: name, distance, stars, avgSentiment, and the explanation string
   - Optional: a simple map view (`st.map`) plotting result coordinates

## 3. Skeleton Code
```python
import streamlit as st
from src.db import get_db
from src.pipeline import recommend_businesses

st.set_page_config(page_title="YelpNoSQL", layout="wide")
st.title("YelpNoSQL: Location-Aware Business Recommendation System")

db = get_db()

with st.sidebar:
    st.header("Search")
    demo_locations = {
        "Downtown": (39.9526, -75.1652),
        "University Area": (39.9600, -75.1900),
        # add 1-2 more real coordinates from your filtered dataset
    }
    location_choice = st.selectbox("Location", list(demo_locations.keys()))
    lat, lng = demo_locations[location_choice]

    categories = db.businesses.distinct("categories")
    category = st.selectbox("Category", ["All"] + sorted(categories))

    user_id = st.selectbox("User", ["(new user — cold start)", "usr_045", "usr_102"])
    max_distance_km = st.slider("Max distance (km)", 0.5, 5.0, 3.0)

if st.button("Find Recommendations"):
    resolved_user = None if user_id.startswith("(new") else user_id
    resolved_category = None if category == "All" else category

    results = recommend_businesses(
        db, lng, lat,
        user_id=resolved_user,
        category=resolved_category,
        max_distance_m=int(max_distance_km * 1000)
    )

    for r in results:
        st.subheader(f"{r['name']} — {r['stars']}★")
        st.caption(r["explanation"])
        st.write(f"Categories: {', '.join(r['categories'])}")
        st.divider()
```

## 4. Demo Script (what to actually show live)
1. Run search with an established user ID + Restaurants category → point out ranked results and the explanation referencing their preferred category.
2. Switch to the "new user — cold start" option with the same location → point out results are still sensible (stars/sentiment/distance only), demonstrating the cold-start fallback.
3. Switch the category dropdown to the secondary category (e.g., Cafes) → point out the exact same system works without any code change, proving category-agnostic design.
4. Optionally, briefly show the MongoDB Atlas/Compass dashboard with the `2dsphere` index and a sample document, to visually reinforce the schema design talked about in the report.

## 5. Testing This Module
1. Confirm dropdown category list matches what's actually in the database (not hardcoded).
2. Confirm switching users changes the explanation text/ranking order, not just the same static list.
3. Confirm the app doesn't crash on the cold-start path (most common demo-breaking bug — test this explicitly before presenting).
