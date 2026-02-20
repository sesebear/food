# my_good_query.py
# FDA Food Adverse Event API – filtered query for analysis/reporting
# Pairs with LAB_your_good_api_query.md
# Tim Fraser

# Queries openFDA Food Event API for adverse event reports in a date range.
# Returns 10–20 records with key fields for time-series or categorical analysis.

# 0. Setup #################################

## 0.1 Load packages ############################

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

## 0.2 Load API key ###############################

# openFDA accepts api_key as a query parameter (optional but recommended for higher rate limits).
# Load API key from .env in the same directory as this script; add API_KEY=your_key for openFDA.
dotenv_path = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=dotenv_path)

# API key is optional for openFDA (higher rate limit with key). Load if present.
api_key = os.getenv("API_KEY")

# 1. API request #################################

# --- API documentation (for reporting) ---
# API name:   openFDA Food Adverse Event Reports API
# Endpoint:   https://api.fda.gov/food/event.json
# Parameters:
#   api_key  – Optional; increases rate limit (120k/day with key vs 1k/day without).
#   search   – Filter: e.g. products.industry_name:"Cosmetics" (categorical).
#   sort     – Order by date_created descending (newest first).
#   limit    – Max records to return (1–1000; we request 20).
# Expected data:
#   Each result: report_number, date_created, outcomes[], reactions[], consumer{}, products[].
#   products[]: name_brand, industry_name, industry_code, role (SUSPECT/CONCOMITANT).
#   Useful for: time-series (date_created), categorical (industry/product), filtered subsets.

BASE_URL = "https://api.fda.gov/food/event.json"

# Filtered + categorical query: events where product industry is "Cosmetics".
# Returns 20 rows for analysis; sort by date_created descending (time-series order).
params = {
    "search": "products.industry_name:Cosmetics",
    "sort": "date_created:desc",
    "limit": 20,
}
if api_key:
    params["api_key"] = api_key

try:
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
except requests.exceptions.Timeout:
    raise SystemExit("Request timed out. Check network and try again.")
except requests.exceptions.HTTPError as e:
    raise SystemExit(f"HTTP error: {e.response.status_code} – {e.response.reason}")
except requests.exceptions.RequestException as e:
    raise SystemExit(f"Request failed: {e}")

data = response.json()

# 2. Document results #################################

# --- Result summary ---
# Number of records:  len(data["results"])  (expect 10–20 when filter matches enough).
# Key fields per record:
#   report_number   – Unique report ID.
#   date_created    – Report date (YYYYMMDD).
#   outcomes        – List of outcomes (e.g. "Visited a Health Care Provider").
#   reactions       – List of reported reactions (e.g. "NAUSEA", "RASH").
#   consumer        – Dict: age, age_unit, gender (when reported).
#   products        – List of dicts: name_brand, industry_name, industry_code, role.
# Data structure:  JSON object with "meta" (disclaimer, total, skip, limit) and "results" (list of events).

meta = data.get("meta", {})
results = data.get("results", [])
total_available = meta.get("results", {}).get("total", "?")
n_returned = len(results)

print("--- FDA Food Event API – query result ---")
print(f"Total matching records (API): {total_available}")
print(f"Records returned:            {n_returned}")
print("--- Key fields per record: report_number, date_created, outcomes, reactions, consumer, products ---")
print()

for i, event in enumerate(results, start=1):
    report_number = event.get("report_number", "N/A")
    date_created = event.get("date_created", "N/A")
    outcomes = event.get("outcomes", [])
    reactions = event.get("reactions", [])[:3]  # First 3 for brevity
    products = event.get("products", [])
    product_names = [p.get("name_brand", "?") for p in products[:2]]  # First 2 products
    print(f"{i}. Report {report_number} | date_created={date_created} | outcomes={outcomes[:1]} | reactions={reactions} | products={product_names}")

print()
print("--- Full JSON structure (first record keys): ---")
if results:
    print(list(results[0].keys()))
