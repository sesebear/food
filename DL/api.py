# api.py
# FastAPI REST API for the City Congestion Tracker
# City Congestion Tracker — DL Challenge 2026
#
# Serves congestion data from Supabase with filters for location,
# time range, and severity. Also provides an AI summary endpoint
# that calls Ollama to generate plain-language insights.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import requests
import pandas as pd

## 0.2 Load Environment #################################

if os.path.exists(".env"): load_dotenv()
else: print("⚠️  .env not found — copy .env.example to .env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "smollm2:1.7b")

## 0.3 Initialize App & Client #################################

app = FastAPI(
    title="City Congestion Tracker API",
    description="REST API serving congestion data from Supabase with AI-powered summaries via Ollama.",
    version="1.0.0",
)

# Allow CORS for the Shiny dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


# 1. HELPER FUNCTIONS ###################################

def require_db():
    """Raise an error if the database client is not configured."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured. Set SUPABASE_URL and SUPABASE_KEY.")


# 2. ENDPOINTS ###################################

## 2.1 Health Check #################################

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "database": db is not None}


## 2.2 Locations #################################

@app.get("/locations")
def get_locations(zone: Optional[str] = None, road_type: Optional[str] = None):
    """Retrieve all monitored locations, optionally filtered by zone or road type."""
    require_db()
    query = db.table("locations").select("*")
    if zone: query = query.eq("zone", zone)
    if road_type: query = query.eq("road_type", road_type)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


## 2.3 Congestion Readings #################################

@app.get("/congestion")
def get_congestion(
    location_id: Optional[int] = None,
    zone: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    min_level: Optional[int] = Query(None, ge=0, le=100),
    max_level: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(500, ge=1, le=5000),
    order: str = Query("desc", regex="^(asc|desc)$"),
):
    """
    Retrieve congestion readings with filters.

    Parameters:
        location_id: Filter by a specific location
        zone: Filter by zone name (requires join — uses location_id lookup)
        start_time: ISO timestamp lower bound
        end_time: ISO timestamp upper bound
        min_level: Minimum congestion level (0-100)
        max_level: Maximum congestion level (0-100)
        limit: Max rows returned (default 500)
        order: Sort by timestamp 'asc' or 'desc'
    """
    require_db()

    # If filtering by zone, first get location IDs in that zone
    loc_ids = None
    if zone:
        loc_result = db.table("locations").select("id").eq("zone", zone).execute()
        loc_ids = [r["id"] for r in loc_result.data]
        if not loc_ids:
            return {"data": [], "count": 0}

    query = db.table("congestion_readings").select("*")

    if location_id: query = query.eq("location_id", location_id)
    if loc_ids: query = query.in_("location_id", loc_ids)
    if start_time: query = query.gte("timestamp", start_time)
    if end_time: query = query.lte("timestamp", end_time)
    if min_level is not None: query = query.gte("congestion_level", min_level)
    if max_level is not None: query = query.lte("congestion_level", max_level)

    query = query.order("timestamp", desc=(order == "desc")).limit(limit)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


## 2.4 Current Congestion (Latest per Location) #################################

@app.get("/congestion/current")
def get_current_congestion():
    """Get the most recent reading for every location."""
    require_db()

    # Fetch locations and latest readings
    locations = db.table("locations").select("*").execute().data
    output = []

    for loc in locations:
        reading = (
            db.table("congestion_readings")
            .select("*")
            .eq("location_id", loc["id"])
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if reading.data:
            output.append({**loc, "latest_reading": reading.data[0]})

    return {"data": output, "count": len(output)}


## 2.5 Aggregated Statistics #################################

@app.get("/congestion/stats")
def get_congestion_stats(
    zone: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """
    Return aggregated congestion statistics.
    Uses pandas for server-side aggregation.
    """
    require_db()

    # Fetch readings (use the congestion endpoint logic)
    loc_ids = None
    if zone:
        loc_result = db.table("locations").select("id").eq("zone", zone).execute()
        loc_ids = [r["id"] for r in loc_result.data]

    query = db.table("congestion_readings").select("*")
    if loc_ids: query = query.in_("location_id", loc_ids)
    if start_time: query = query.gte("timestamp", start_time)
    if end_time: query = query.lte("timestamp", end_time)

    result = query.order("timestamp", desc=True).limit(5000).execute()
    if not result.data:
        return {"stats": {}, "message": "No data found for the given filters."}

    df = pd.DataFrame(result.data)
    df["congestion_level"] = pd.to_numeric(df["congestion_level"])
    df["speed_mph"] = pd.to_numeric(df["speed_mph"])
    df["delay_minutes"] = pd.to_numeric(df["delay_minutes"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour

    # Overall stats
    stats = {
        "avg_congestion": round(df["congestion_level"].mean(), 1),
        "max_congestion": int(df["congestion_level"].max()),
        "min_congestion": int(df["congestion_level"].min()),
        "avg_speed_mph": round(df["speed_mph"].mean(), 1),
        "avg_delay_min": round(df["delay_minutes"].mean(), 1),
        "total_readings": len(df),
    }

    # Per-location averages (top 5 worst)
    loc_avg = (df.groupby("location_id")["congestion_level"]
               .mean().sort_values(ascending=False).head(5))
    stats["worst_locations"] = [
        {"location_id": int(lid), "avg_congestion": round(val, 1)}
        for lid, val in loc_avg.items()
    ]

    # Hourly pattern
    hourly = (df.groupby("hour")["congestion_level"]
              .mean().sort_index())
    stats["hourly_pattern"] = [
        {"hour": int(h), "avg_congestion": round(v, 1)}
        for h, v in hourly.items()
    ]

    return {"stats": stats}


## 2.6 AI Summary (Ollama) #################################

@app.get("/summary")
def get_ai_summary(
    zone: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    question: str = Query(
        "Summarize current congestion conditions and provide actionable recommendations.",
        description="The question to ask the AI about the congestion data."
    ),
):
    """
    Generate an AI-powered narrative summary of congestion data.
    Fetches stats from the database, sends them to Ollama, and returns a natural-language summary.
    """
    require_db()

    # Gather statistics to send to the AI
    stats_response = get_congestion_stats(zone=zone, start_time=start_time, end_time=end_time)
    stats = stats_response.get("stats", {})

    if not stats:
        return {"summary": "No congestion data available for the selected filters.", "stats": {}}

    # Resolve location names for the worst locations
    worst_locs = stats.get("worst_locations", [])
    for wl in worst_locs:
        loc = db.table("locations").select("name, zone").eq("id", wl["location_id"]).execute()
        if loc.data:
            wl["name"] = loc.data[0]["name"]
            wl["zone"] = loc.data[0]["zone"]

    # Build the prompt for Ollama
    data_context = json.dumps(stats, indent=2)
    zone_label = zone if zone else "all zones"

    system_prompt = (
        "You are a transportation analyst AI for a city congestion monitoring system. "
        "You provide concise, actionable summaries of traffic congestion data. "
        "Use specific numbers from the data. Be direct and practical. "
        "Format your response with clear sections using markdown."
    )

    user_prompt = (
        f"Here is the congestion data summary for {zone_label}:\n\n"
        f"```json\n{data_context}\n```\n\n"
        f"User question: {question}\n\n"
        "Provide a clear, actionable summary. Include:\n"
        "1. Current overall status (good/moderate/severe)\n"
        "2. The worst affected areas with specific congestion levels\n"
        "3. Time-of-day patterns (peak hours)\n"
        "4. Specific recommendations for commuters\n"
        "Keep it under 200 words."
    )

    # Call Ollama
    try:
        ollama_url = f"{OLLAMA_HOST}/api/chat"
        body = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        resp = requests.post(ollama_url, json=body, timeout=120)
        resp.raise_for_status()
        ai_text = resp.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        ai_text = (
            "⚠️ Could not connect to Ollama. Make sure it is running at "
            f"{OLLAMA_HOST}. You can start it with: `ollama serve`"
        )
    except Exception as e:
        ai_text = f"⚠️ AI summary unavailable: {str(e)}"

    return {"summary": ai_text, "stats": stats, "model": OLLAMA_MODEL}


# 3. RUN ###################################

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    print(f"🚀 Starting API at http://{host}:{port}")
    print(f"📖 Docs at http://{host}:{port}/docs")
    uvicorn.run("api:app", host=host, port=port, reload=True)
