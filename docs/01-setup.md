# 01 — Environment Setup

## 1. MongoDB
Choose ONE:
- **Local install**: MongoDB Community Server (matches "local dev" simplicity)
- **MongoDB Atlas (free tier, M0)**: easier to demo from any machine, no local install headaches — recommended for a mini project since it also gives a nice dashboard for screenshots in the report

Enable/verify:
- Server is reachable (`mongosh` connects, or Atlas connection string works)
- Note the connection string, e.g. `mongodb://localhost:27017` or `mongodb+srv://<user>:<pass>@cluster.mongodb.net`

## 2. Python Environment
```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows

pip install pymongo pandas vaderSentiment streamlit python-dotenv
```

Package purposes:
- `pymongo` — MongoDB driver
- `pandas` — filtering/cleaning raw JSON before ingest
- `vaderSentiment` — lightweight, no-training-needed sentiment scoring (good fit for a mini project timeline)
- `streamlit` — frontend
- `python-dotenv` — keep MongoDB connection string out of source code

## 3. Project Folder Structure
```
yelpnosql/
├── data/
│   ├── raw/                # original Yelp JSON (not committed — too large)
│   └── filtered/           # output of filtering step
├── src/
│   ├── ingest.py           # load filtered data into MongoDB
│   ├── sentiment.py        # batch sentiment scoring job
│   ├── geo_search.py       # geospatial query functions
│   ├── recommend.py        # recommendation/ranking logic
│   ├── pipeline.py         # chains geo + sentiment + recommend
│   └── db.py                # MongoDB connection helper
├── app.py                  # Streamlit frontend
├── .env                     # MONGO_URI=...
├── requirements.txt
└── docs/                    # this folder
```

## 4. Environment Variables (`.env`)
```
MONGO_URI=mongodb://localhost:27017
DB_NAME=yelpnosql
```

## 5. Dataset Download
- Kaggle: `kaggle datasets download -d yelp-dataset/yelp-dataset`
- Official: https://www.yelp.com/dataset (requires accepting terms, direct `.tar` download)

Place extracted JSON files into `data/raw/`. Expect these files:
- `business.json`
- `review.json`
- `user.json`
- `checkin.json` (optional, not used in MVP)
- `tip.json` (optional, not used in MVP)

## 6. Verification Checklist Before Moving to Phase 1
- [ ] `mongosh` or Atlas connects successfully
- [ ] `python -c "import pymongo, pandas, vaderSentiment, streamlit"` runs with no errors
- [ ] Raw Yelp JSON files present in `data/raw/`
- [ ] `.env` created and loaded correctly by `db.py`
