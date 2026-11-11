"""
Database connection module for YelpNoSQL.
Provides MongoDB client and database accessors using environment variables.
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "yelpnosql")

_client = None


def get_client() -> MongoClient:
    """Return a singleton MongoClient instance."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db(db_name: str = None) -> Database:
    """Return MongoDB Database instance."""
    client = get_client()
    return client[db_name or DB_NAME]


def test_connection() -> bool:
    """Verify that MongoDB is reachable and return status."""
    try:
        client = get_client()
        # The ping command is cheap and does not require auth
        client.admin.command("ping")
        print(f"[db.py] Successfully connected to MongoDB at {MONGO_URI}, database: {DB_NAME}")
        return True
    except Exception as e:
        print(f"[db.py] Error connecting to MongoDB: {e}")
        return False


if __name__ == "__main__":
    if test_connection():
        db = get_db()
        print(f"Collections in '{DB_NAME}': {db.list_collection_names()}")
