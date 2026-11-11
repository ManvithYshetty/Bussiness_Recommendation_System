"""
02 — Data Preparation Module (src/prepare_data.py)
Filters raw Yelp Open Dataset (or generates sample demonstration data)
into clean, manageable, GeoJSON-compliant JSON files for MongoDB ingestion.
"""

import os
import json
import argparse
from typing import Set, Dict, Any, List

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
FILTERED_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "filtered")


def normalize_attributes(attrs: Any) -> Dict[str, Any]:
    """Recursively clean Yelp stringified booleans and nested dictionaries."""
    if not isinstance(attrs, dict):
        return {}
    clean_attrs = {}
    for k, v in attrs.items():
        if isinstance(v, str):
            if v.lower() == "true":
                clean_attrs[k] = True
            elif v.lower() == "false":
                clean_attrs[k] = False
            elif v.lower() == "none":
                clean_attrs[k] = None
            elif v.startswith("{") and v.endswith("}"):
                # Sometimes nested dicts are stored as string literals
                try:
                    # Replace single quotes with double quotes for JSON parsing
                    fixed_json = v.replace("'", '"').replace("True", "true").replace("False", "false")
                    clean_attrs[k] = json.loads(fixed_json)
                except Exception:
                    clean_attrs[k] = v
            else:
                clean_attrs[k] = v
        else:
            clean_attrs[k] = v
    return clean_attrs


def filter_businesses(
    raw_path: str,
    output_path: str,
    target_city: str = "Philadelphia",
    target_categories: List[str] = None
) -> Set[str]:
    """
    Stream business.json, filter by city and categories, format GeoJSON location,
    and save to business_filtered.json. Returns a set of kept business_ids.
    """
    if target_categories is None:
        target_categories = ["Restaurants", "Cafes", "Bars"]

    target_cats_lower = [c.lower() for c in target_categories]
    target_city_lower = target_city.lower()
    kept_biz_ids = set()

    print(f"[prepare_data] Filtering businesses for city='{target_city}' and categories={target_categories}...")

    with open(raw_path, "r", encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        count_total = 0
        count_kept = 0
        for line in in_f:
            count_total += 1
            if not line.strip():
                continue
            biz = json.loads(line)

            # Check city
            city = biz.get("city", "")
            if not city or city.strip().lower() != target_city_lower:
                continue

            # Check categories
            cats_raw = biz.get("categories")
            if not cats_raw or not isinstance(cats_raw, str):
                continue
            cat_list = [c.strip() for c in cats_raw.split(",") if c.strip()]
            
            # Check if any target category is in cat_list
            has_matching_cat = any(
                any(t in c.lower() for t in target_cats_lower)
                for c in cat_list
            )
            if not has_matching_cat:
                continue

            # Validate coordinates
            lat = biz.get("latitude")
            lng = biz.get("longitude")
            if lat is None or lng is None:
                continue
            try:
                lat = float(lat)
                lng = float(lng)
            except (ValueError, TypeError):
                continue

            # GeoJSON Point: [longitude, latitude]
            geojson_location = {
                "type": "Point",
                "coordinates": [lng, lat]
            }

            clean_biz = {
                "_id": biz.get("business_id"),
                "name": biz.get("name"),
                "city": biz.get("city"),
                "state": biz.get("state"),
                "postal_code": biz.get("postal_code"),
                "address": biz.get("address"),
                "location": geojson_location,
                "categories": cat_list,
                "attributes": normalize_attributes(biz.get("attributes")),
                "stars": float(biz.get("stars", 0.0)),
                "review_count": int(biz.get("review_count", 0)),
                "is_open": int(biz.get("is_open", 1)),
                "avgSentiment": 0.0  # Initial placeholder to be populated in Phase 4
            }

            out_f.write(json.dumps(clean_biz) + "\n")
            kept_biz_ids.add(clean_biz["_id"])
            count_kept += 1

    print(f"[prepare_data] Processed {count_total} raw businesses -> Kept {count_kept} businesses in '{target_city}'.")
    return kept_biz_ids


def filter_reviews(raw_path: str, output_path: str, kept_biz_ids: Set[str]) -> Set[str]:
    """
    Stream review.json, keeping only reviews for businesses in kept_biz_ids.
    Returns a set of kept user_ids.
    """
    print(f"[prepare_data] Streaming reviews for {len(kept_biz_ids)} businesses...")
    kept_user_ids = set()

    with open(raw_path, "r", encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        count_total = 0
        count_kept = 0
        for line in in_f:
            count_total += 1
            if count_total % 200000 == 0:
                print(f"[prepare_data] Scanned {count_total} reviews... (Kept: {count_kept})")
            if not line.strip():
                continue
            rev = json.loads(line)

            biz_id = rev.get("business_id")
            if biz_id not in kept_biz_ids:
                continue

            user_id = rev.get("user_id")
            clean_rev = {
                "_id": rev.get("review_id"),
                "business_id": biz_id,
                "user_id": user_id,
                "stars": float(rev.get("stars", 0.0)),
                "text": rev.get("text", "").strip(),
                "date": rev.get("date"),
                "sentiment_score": None  # Initial placeholder populated by Phase 4
            }

            out_f.write(json.dumps(clean_rev) + "\n")
            if user_id:
                kept_user_ids.add(user_id)
            count_kept += 1

    print(f"[prepare_data] Processed {count_total} raw reviews -> Kept {count_kept} reviews.")
    return kept_user_ids


def filter_users(raw_path: str, output_path: str, kept_user_ids: Set[str]) -> int:
    """
    Stream user.json, keeping only users who wrote at least one kept review.
    """
    print(f"[prepare_data] Streaming users for {len(kept_user_ids)} active reviewers...")

    with open(raw_path, "r", encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        count_total = 0
        count_kept = 0
        for line in in_f:
            count_total += 1
            if count_total % 200000 == 0:
                print(f"[prepare_data] Scanned {count_total} users... (Kept: {count_kept})")
            if not line.strip():
                continue
            usr = json.loads(line)

            uid = usr.get("user_id")
            if uid not in kept_user_ids:
                continue

            clean_usr = {
                "_id": uid,
                "name": usr.get("name", "User"),
                "review_count": int(usr.get("review_count", 0)),
                "average_stars": float(usr.get("average_stars", 0.0)),
                "yelping_since": usr.get("yelping_since")
            }

            out_f.write(json.dumps(clean_usr) + "\n")
            count_kept += 1

    print(f"[prepare_data] Processed {count_total} raw users -> Kept {count_kept} users.")
    return count_kept


def generate_sample_dataset():
    """
    Generates a realistic Philadelphia demonstration dataset when raw Yelp JSON files
    are not yet downloaded, so the user can test the full pipeline and UI immediately.
    """
    os.makedirs(FILTERED_DATA_DIR, exist_ok=True)
    print("[prepare_data] Generating realistic Philadelphia sample dataset...")

    sample_businesses = [
        {
            "_id": "biz_phi_001",
            "name": "Reading Terminal Market Bakes",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19107",
            "address": "51 N 12th St",
            "location": {"type": "Point", "coordinates": [-75.1593, 39.9533]},
            "categories": ["Cafes", "Bakeries", "Breakfast & Brunch"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 1},
            "stars": 4.7,
            "review_count": 520,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_002",
            "name": "Center City Trattoria & Pizza",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19102",
            "address": "1520 Locust St",
            "location": {"type": "Point", "coordinates": [-75.1668, 39.9489]},
            "categories": ["Restaurants", "Italian", "Pizza"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.5,
            "review_count": 340,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_003",
            "name": "Old City Espresso Bar",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19106",
            "address": "218 Market St",
            "location": {"type": "Point", "coordinates": [-75.1438, 39.9502]},
            "categories": ["Cafes", "Coffee & Tea"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 1},
            "stars": 4.6,
            "review_count": 210,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_004",
            "name": "Rittenhouse Steakhouse & Grill",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19103",
            "address": "1801 Chestnut St",
            "location": {"type": "Point", "coordinates": [-75.1709, 39.9517]},
            "categories": ["Restaurants", "Steakhouses", "American"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 3},
            "stars": 4.3,
            "review_count": 415,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_005",
            "name": "South Street Tacos & Cantina",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19147",
            "address": "520 South St",
            "location": {"type": "Point", "coordinates": [-75.1517, 39.9416]},
            "categories": ["Restaurants", "Mexican", "Bars"],
            "attributes": {"WiFi": "no", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.4,
            "review_count": 185,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_006",
            "name": "University City Artisan Coffee",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19104",
            "address": "3600 Chestnut St",
            "location": {"type": "Point", "coordinates": [-75.1950, 39.9545]},
            "categories": ["Cafes", "Coffee & Tea", "Breakfast & Brunch"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 1},
            "stars": 4.8,
            "review_count": 290,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_007",
            "name": "Bella Vista Pizzeria",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19147",
            "address": "900 S 9th St",
            "location": {"type": "Point", "coordinates": [-75.1580, 39.9378]},
            "categories": ["Restaurants", "Italian", "Pizza"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 2},
            "stars": 4.2,
            "review_count": 175,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_008",
            "name": "Chinatown Dim Sum House",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19107",
            "address": "1015 Arch St",
            "location": {"type": "Point", "coordinates": [-75.1565, 39.9538]},
            "categories": ["Restaurants", "Chinese", "Dim Sum"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 2},
            "stars": 4.6,
            "review_count": 390,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_009",
            "name": "Fishtown Craft Beer & Burger",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19125",
            "address": "1240 Frankford Ave",
            "location": {"type": "Point", "coordinates": [-75.1325, 39.9721]},
            "categories": ["Bars", "American", "Burgers"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.5,
            "review_count": 480,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_010",
            "name": "Passyunk Italian Bistro & Wine Bar",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19148",
            "address": "1610 E Passyunk Ave",
            "location": {"type": "Point", "coordinates": [-75.1610, 39.9290]},
            "categories": ["Restaurants", "Italian", "Wine Bars"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 3},
            "stars": 4.8,
            "review_count": 610,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_011",
            "name": "Northern Liberties Vegan Kitchen",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19123",
            "address": "700 N 2nd St",
            "location": {"type": "Point", "coordinates": [-75.1415, 39.9648]},
            "categories": ["Restaurants", "Vegan", "Salad"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.4,
            "review_count": 230,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_012",
            "name": "Fairmount Brunch & Creperie",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19130",
            "address": "2200 Fairmount Ave",
            "location": {"type": "Point", "coordinates": [-75.1740, 39.9675]},
            "categories": ["Cafes", "Breakfast & Brunch", "French"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.3,
            "review_count": 310,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_013",
            "name": "Queen Village Sushi & Sake",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19147",
            "address": "740 S 4th St",
            "location": {"type": "Point", "coordinates": [-75.1495, 39.9385]},
            "categories": ["Restaurants", "Japanese", "Sushi Bars"],
            "attributes": {"WiFi": "no", "OutdoorSeating": False, "RestaurantsPriceRange2": 3},
            "stars": 4.7,
            "review_count": 350,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_014",
            "name": "West Philly Global Cafe",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19104",
            "address": "4505 Baltimore Ave",
            "location": {"type": "Point", "coordinates": [-75.2110, 39.9530]},
            "categories": ["Cafes", "Coffee & Tea", "Breakfast & Brunch"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 1},
            "stars": 4.6,
            "review_count": 275,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_015",
            "name": "Center City Cocktail Lounge",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19102",
            "address": "1420 Sansom St",
            "location": {"type": "Point", "coordinates": [-75.1650, 39.9505]},
            "categories": ["Bars", "Cocktail Bars", "Nightlife"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 3},
            "stars": 4.5,
            "review_count": 420,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_016",
            "name": "Manayunk Riverside Brewpub",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19127",
            "address": "4120 Main St",
            "location": {"type": "Point", "coordinates": [-75.2250, 40.0260]},
            "categories": ["Bars", "Breweries", "American"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.1,
            "review_count": 380,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_017",
            "name": "Graduate Hospital Gastropub",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19146",
            "address": "2101 South St",
            "location": {"type": "Point", "coordinates": [-75.1765, 39.9435]},
            "categories": ["Restaurants", "Gastropubs", "American"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 2},
            "stars": 4.3,
            "review_count": 290,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_018",
            "name": "University Ramen & Noodles",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19104",
            "address": "3710 Spruce St",
            "location": {"type": "Point", "coordinates": [-75.1985, 39.9540]},
            "categories": ["Restaurants", "Japanese", "Noodles"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 2},
            "stars": 4.4,
            "review_count": 320,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_019",
            "name": "Washington Square Italian Osteria",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19106",
            "address": "210 W Washington Sq",
            "location": {"type": "Point", "coordinates": [-75.1520, 39.9470]},
            "categories": ["Restaurants", "Italian", "Seafood"],
            "attributes": {"WiFi": "free", "OutdoorSeating": True, "RestaurantsPriceRange2": 3},
            "stars": 4.7,
            "review_count": 510,
            "is_open": 1,
            "avgSentiment": 0.0
        },
        {
            "_id": "biz_phi_020",
            "name": "Midtown Diner & Bakery",
            "city": "Philadelphia",
            "state": "PA",
            "postal_code": "19107",
            "address": "1200 Chestnut St",
            "location": {"type": "Point", "coordinates": [-75.1605, 39.9495]},
            "categories": ["Restaurants", "Diners", "Bakeries"],
            "attributes": {"WiFi": "free", "OutdoorSeating": False, "RestaurantsPriceRange2": 1},
            "stars": 3.8,
            "review_count": 160,
            "is_open": 1,
            "avgSentiment": 0.0
        }
    ]

    sample_reviews = [
        {
            "_id": "rev_001",
            "business_id": "biz_phi_002",
            "user_id": "usr_alex_italian_fan",
            "stars": 5.0,
            "text": "Absolute best authentic thin-crust pizza in Philadelphia! The pasta is fresh and the staff treated us like family.",
            "date": "2024-02-15",
            "sentiment_score": None
        },
        {
            "_id": "rev_002",
            "business_id": "biz_phi_007",
            "user_id": "usr_alex_italian_fan",
            "stars": 4.5,
            "text": "Classic Italian pizza in Bella Vista. Garlic knots are to die for and fast delivery!",
            "date": "2024-03-01",
            "sentiment_score": None
        },
        {
            "_id": "rev_003",
            "business_id": "biz_phi_010",
            "user_id": "usr_alex_italian_fan",
            "stars": 5.0,
            "text": "Exquisite handmade gnocchi and superb wine pairing. True Italian hospitality in East Passyunk!",
            "date": "2024-03-14",
            "sentiment_score": None
        },
        {
            "_id": "rev_004",
            "business_id": "biz_phi_019",
            "user_id": "usr_alex_italian_fan",
            "stars": 5.0,
            "text": "Sensational seafood risotto and tiramisu overlooking Washington Square. Outstanding dining experience.",
            "date": "2024-03-20",
            "sentiment_score": None
        },
        {
            "_id": "rev_005",
            "business_id": "biz_phi_003",
            "user_id": "usr_sam_cafe_lover",
            "stars": 5.0,
            "text": "My favorite morning study cafe in Old City. Wonderful pour-over coffee, quiet ambient vibe, and lightning fast wifi.",
            "date": "2024-03-10",
            "sentiment_score": None
        },
        {
            "_id": "rev_006",
            "business_id": "biz_phi_006",
            "user_id": "usr_sam_cafe_lover",
            "stars": 5.0,
            "text": "Stunning artisan coffee near campus. Excellent cold brew and delicious fresh pastries.",
            "date": "2024-03-22",
            "sentiment_score": None
        },
        {
            "_id": "rev_007",
            "business_id": "biz_phi_001",
            "user_id": "usr_sam_cafe_lover",
            "stars": 4.0,
            "text": "Great breakfast pastries and fresh bread! Very bustling and fun atmosphere inside Reading Terminal.",
            "date": "2024-03-25",
            "sentiment_score": None
        },
        {
            "_id": "rev_008",
            "business_id": "biz_phi_012",
            "user_id": "usr_sam_cafe_lover",
            "stars": 4.5,
            "text": "Delightful French crepes and artisan latte. Cozy brunch spot with sunny outdoor seating in Fairmount.",
            "date": "2024-03-28",
            "sentiment_score": None
        },
        {
            "_id": "rev_009",
            "business_id": "biz_phi_014",
            "user_id": "usr_sam_cafe_lover",
            "stars": 5.0,
            "text": "Incredible specialty coffee beans and serene garden seating. Love West Philly community vibes.",
            "date": "2024-03-29",
            "sentiment_score": None
        },
        {
            "_id": "rev_010",
            "business_id": "biz_phi_004",
            "user_id": "usr_foodie_general",
            "stars": 4.0,
            "text": "Prime cut ribeye cooked to perfection. A bit pricey but worth it for a celebratory evening dinner.",
            "date": "2024-02-28",
            "sentiment_score": None
        },
        {
            "_id": "rev_011",
            "business_id": "biz_phi_005",
            "user_id": "usr_foodie_general",
            "stars": 4.5,
            "text": "Flavorful street tacos, delicious homemade guacamole, and a fantastic craft cocktail selection.",
            "date": "2024-03-05",
            "sentiment_score": None
        },
        {
            "_id": "rev_012",
            "business_id": "biz_phi_008",
            "user_id": "usr_foodie_general",
            "stars": 5.0,
            "text": "Exceptional soup dumplings and steamed buns. Super fast service and authentically delicious flavors.",
            "date": "2024-03-18",
            "sentiment_score": None
        },
        {
            "_id": "rev_013",
            "business_id": "biz_phi_009",
            "user_id": "usr_foodie_general",
            "stars": 4.5,
            "text": "Juicy smash burgers and an incredible rotating local IPA draft list in Fishtown. Great music!",
            "date": "2024-03-21",
            "sentiment_score": None
        },
        {
            "_id": "rev_014",
            "business_id": "biz_phi_013",
            "user_id": "usr_foodie_general",
            "stars": 5.0,
            "text": "Freshest sashimi in Philly! Beautiful presentation, warm hospitality, and delightful seasonal sake flights.",
            "date": "2024-03-27",
            "sentiment_score": None
        },
        {
            "_id": "rev_015",
            "business_id": "biz_phi_015",
            "user_id": "usr_nightlife_bar_hopper",
            "stars": 4.5,
            "text": "Craft cocktails are art pieces here. Sophisticated speakeasy atmosphere with skilled mixologists.",
            "date": "2024-03-12",
            "sentiment_score": None
        },
        {
            "_id": "rev_016",
            "business_id": "biz_phi_009",
            "user_id": "usr_nightlife_bar_hopper",
            "stars": 4.5,
            "text": "Lively bar with great outdoor patio and huge draft selection. Top spot for Fishtown nights.",
            "date": "2024-03-16",
            "sentiment_score": None
        },
        {
            "_id": "rev_017",
            "business_id": "biz_phi_016",
            "user_id": "usr_nightlife_bar_hopper",
            "stars": 4.0,
            "text": "Nice brewery patio right next to the river. Good beers, though service was slightly slow on Saturday.",
            "date": "2024-03-23",
            "sentiment_score": None
        },
        {
            "_id": "rev_018",
            "business_id": "biz_phi_011",
            "user_id": "usr_plant_based_eats",
            "stars": 5.0,
            "text": "100% plant-based perfection! The vegan truffle mac and crispy oyster mushroom salad blew my mind.",
            "date": "2024-03-15",
            "sentiment_score": None
        },
        {
            "_id": "rev_019",
            "business_id": "biz_phi_001",
            "user_id": "usr_plant_based_eats",
            "stars": 4.0,
            "text": "Found some really nice vegan baked pastries and fresh smoothies here. Very crowded on weekends.",
            "date": "2024-03-19",
            "sentiment_score": None
        },
        {
            "_id": "rev_020",
            "business_id": "biz_phi_020",
            "user_id": "usr_plant_based_eats",
            "stars": 2.5,
            "text": "Very limited healthy options and the service was inattentive and sluggish. Coffee tasted burnt.",
            "date": "2024-03-24",
            "sentiment_score": None
        },
        {
            "_id": "rev_021",
            "business_id": "biz_phi_020",
            "user_id": "usr_foodie_general",
            "stars": 3.0,
            "text": "Standard greasy spoon diner food. Pancakes were fine but eggs were cold by the time they arrived.",
            "date": "2024-03-26",
            "sentiment_score": None
        },
        {
            "_id": "rev_022",
            "business_id": "biz_phi_018",
            "user_id": "usr_foodie_general",
            "stars": 4.5,
            "text": "Rich tonkotsu broth, perfectly springy noodles, and melt-in-your-mouth chashu pork.",
            "date": "2024-03-28",
            "sentiment_score": None
        }
    ]

    sample_users = [
        {
            "_id": "usr_alex_italian_fan",
            "name": "Alex R. (Italian & Pizza Lover)",
            "review_count": 28,
            "average_stars": 4.8,
            "yelping_since": "2021-04-12"
        },
        {
            "_id": "usr_sam_cafe_lover",
            "name": "Sam K. (Cafe & Bakery Enthusiast)",
            "review_count": 35,
            "average_stars": 4.6,
            "yelping_since": "2020-08-19"
        },
        {
            "_id": "usr_nightlife_bar_hopper",
            "name": "Jordan P. (Nightlife & Craft Beer Fan)",
            "review_count": 41,
            "average_stars": 4.3,
            "yelping_since": "2020-02-10"
        },
        {
            "_id": "usr_plant_based_eats",
            "name": "Morgan L. (Vegan & Healthy Eater)",
            "review_count": 22,
            "average_stars": 4.2,
            "yelping_since": "2022-06-15"
        },
        {
            "_id": "usr_foodie_general",
            "name": "Taylor M. (Eclectic Foodie)",
            "review_count": 52,
            "average_stars": 4.4,
            "yelping_since": "2019-01-05"
        }
    ]

    # Save to data/filtered/
    biz_out = os.path.join(FILTERED_DATA_DIR, "business_filtered.json")
    rev_out = os.path.join(FILTERED_DATA_DIR, "review_filtered.json")
    usr_out = os.path.join(FILTERED_DATA_DIR, "user_filtered.json")

    with open(biz_out, "w", encoding="utf-8") as f:
        for b in sample_businesses:
            f.write(json.dumps(b) + "\n")

    with open(rev_out, "w", encoding="utf-8") as f:
        for r in sample_reviews:
            f.write(json.dumps(r) + "\n")

    with open(usr_out, "w", encoding="utf-8") as f:
        for u in sample_users:
            f.write(json.dumps(u) + "\n")

    print(f"[prepare_data] Generated sample files in {FILTERED_DATA_DIR}:")
    print(f"  - {len(sample_businesses)} businesses -> {biz_out}")
    print(f"  - {len(sample_reviews)} reviews -> {rev_out}")
    print(f"  - {len(sample_users)} users -> {usr_out}")


def main():
    parser = argparse.ArgumentParser(description="Filter Yelp raw dataset or generate demonstration subset.")
    parser.add_argument("--city", default="Philadelphia", help="City name to filter (default: Philadelphia)")
    parser.add_argument("--sample", action="store_true", help="Generate realistic demonstration subset without raw files")
    args = parser.parse_args()

    biz_raw = os.path.join(RAW_DATA_DIR, "business.json")
    rev_raw = os.path.join(RAW_DATA_DIR, "review.json")
    usr_raw = os.path.join(RAW_DATA_DIR, "user.json")

    if args.sample or not os.path.exists(biz_raw):
        if not os.path.exists(biz_raw):
            print(f"[prepare_data] Raw files not found in {RAW_DATA_DIR}. Defaulting to demonstration sample dataset.")
        generate_sample_dataset()
        return

    os.makedirs(FILTERED_DATA_DIR, exist_ok=True)
    biz_out = os.path.join(FILTERED_DATA_DIR, "business_filtered.json")
    rev_out = os.path.join(FILTERED_DATA_DIR, "review_filtered.json")
    usr_out = os.path.join(FILTERED_DATA_DIR, "user_filtered.json")

    kept_biz_ids = filter_businesses(biz_raw, biz_out, target_city=args.city)
    kept_user_ids = filter_reviews(rev_raw, rev_out, kept_biz_ids)
    filter_users(usr_raw, usr_out, kept_user_ids)
    print("[prepare_data] Data preparation complete!")


if __name__ == "__main__":
    main()
