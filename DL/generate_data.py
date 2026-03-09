# generate_data.py
# Synthetic Congestion Data Generator & Supabase Seeder
# City Congestion Tracker — DL Challenge 2026
#
# Generates realistic synthetic congestion data for 20 intersections
# across 5 city zones over the past 14 days and seeds it into Supabase.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import os
import random
import math
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

## 0.2 Load Environment #################################

if os.path.exists(".env"): load_dotenv()
else: print("⚠️  .env file not found — copy .env.example to .env and fill in values.")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# 1. DEFINE LOCATIONS ###################################

# 20 intersections spread across 5 city zones
LOCATIONS = [
    {"name": "Main St & 1st Ave",       "zone": "Downtown",    "road_type": "arterial",   "latitude": 40.7128, "longitude": -74.0060},
    {"name": "Broadway & 5th Ave",       "zone": "Downtown",    "road_type": "arterial",   "latitude": 40.7138, "longitude": -74.0050},
    {"name": "Center Blvd & Park Rd",    "zone": "Downtown",    "road_type": "collector",  "latitude": 40.7148, "longitude": -74.0070},
    {"name": "Market St & 3rd Ave",      "zone": "Downtown",    "road_type": "arterial",   "latitude": 40.7118, "longitude": -74.0045},
    {"name": "Oak Dr & Elm St",          "zone": "Midtown",     "road_type": "collector",  "latitude": 40.7200, "longitude": -73.9950},
    {"name": "Pine Rd & Maple Ave",      "zone": "Midtown",     "road_type": "local",      "latitude": 40.7210, "longitude": -73.9940},
    {"name": "Cedar Ln & Birch Blvd",    "zone": "Midtown",     "road_type": "arterial",   "latitude": 40.7220, "longitude": -73.9960},
    {"name": "Walnut St & Cherry Dr",    "zone": "Midtown",     "road_type": "collector",  "latitude": 40.7190, "longitude": -73.9970},
    {"name": "River Rd & Lake Ave",      "zone": "Waterfront",  "road_type": "arterial",   "latitude": 40.7050, "longitude": -74.0120},
    {"name": "Harbor Blvd & Dock St",    "zone": "Waterfront",  "road_type": "collector",  "latitude": 40.7040, "longitude": -74.0130},
    {"name": "Marina Dr & Pier Ln",      "zone": "Waterfront",  "road_type": "local",      "latitude": 40.7060, "longitude": -74.0110},
    {"name": "Bay St & Tide Ave",        "zone": "Waterfront",  "road_type": "arterial",   "latitude": 40.7045, "longitude": -74.0140},
    {"name": "University Ave & College Rd", "zone": "Uptown",   "road_type": "arterial",   "latitude": 40.7300, "longitude": -73.9850},
    {"name": "Campus Dr & Scholar Ln",   "zone": "Uptown",      "road_type": "local",      "latitude": 40.7310, "longitude": -73.9840},
    {"name": "Library St & Research Blvd","zone": "Uptown",      "road_type": "collector",  "latitude": 40.7320, "longitude": -73.9860},
    {"name": "Academy Rd & Dean Ave",    "zone": "Uptown",      "road_type": "local",      "latitude": 40.7290, "longitude": -73.9870},
    {"name": "Industrial Pkwy & Factory Rd","zone": "Industrial","road_type": "arterial",   "latitude": 40.6950, "longitude": -74.0200},
    {"name": "Warehouse Blvd & Rail St", "zone": "Industrial",  "road_type": "collector",  "latitude": 40.6940, "longitude": -74.0210},
    {"name": "Commerce Dr & Trade Ave",  "zone": "Industrial",  "road_type": "arterial",   "latitude": 40.6960, "longitude": -74.0190},
    {"name": "Freight Ln & Cargo Blvd",  "zone": "Industrial",  "road_type": "local",      "latitude": 40.6945, "longitude": -74.0220},
]

# Zone-specific congestion profiles (base level during peak, off-peak multiplier)
ZONE_PROFILES = {
    "Downtown":   {"base_peak": 75, "off_peak_mult": 0.45, "weekend_mult": 0.55},
    "Midtown":    {"base_peak": 65, "off_peak_mult": 0.50, "weekend_mult": 0.60},
    "Waterfront": {"base_peak": 50, "off_peak_mult": 0.40, "weekend_mult": 0.70},
    "Uptown":     {"base_peak": 55, "off_peak_mult": 0.55, "weekend_mult": 0.50},
    "Industrial": {"base_peak": 60, "off_peak_mult": 0.30, "weekend_mult": 0.25},
}

# Road type multipliers (arterials are more congested)
ROAD_MULT = {"arterial": 1.15, "collector": 1.0, "local": 0.80}

# 2. CONGESTION MODEL ###################################

def compute_congestion(zone, road_type, hour, is_weekend):
    """Calculate a realistic congestion level (0-100) based on time patterns."""
    profile = ZONE_PROFILES[zone]
    base = profile["base_peak"]

    # Time-of-day curve: two peaks (morning 7-9, evening 5-7), low overnight
    if 7 <= hour <= 9:
        time_factor = 1.0
    elif 16 <= hour <= 18:
        time_factor = 0.95
    elif 10 <= hour <= 15:
        time_factor = 0.65
    elif 19 <= hour <= 21:
        time_factor = 0.55
    else:
        time_factor = profile["off_peak_mult"]

    # Weekend adjustment
    if is_weekend:
        time_factor *= profile["weekend_mult"]

    # Road type adjustment
    road_factor = ROAD_MULT.get(road_type, 1.0)

    level = base * time_factor * road_factor
    # Add realistic noise
    noise = random.gauss(0, 8)
    level = max(0, min(100, int(level + noise)))
    return level


def compute_speed(congestion_level):
    """Derive speed from congestion: high congestion = low speed."""
    max_speed = 45
    speed = max_speed * (1 - congestion_level / 120)
    return round(max(3, speed + random.gauss(0, 2)), 1)


def compute_volume(congestion_level, hour):
    """Derive vehicle volume (vehicles/15min) from congestion and hour."""
    base_volume = 20 + congestion_level * 2.5
    if 7 <= hour <= 9 or 16 <= hour <= 18:
        base_volume *= 1.3
    return max(5, int(base_volume + random.gauss(0, 15)))


def compute_delay(congestion_level):
    """Derive delay in minutes from congestion level."""
    if congestion_level < 20: return round(random.uniform(0, 1), 1)
    elif congestion_level < 50: return round(random.uniform(0.5, 4), 1)
    elif congestion_level < 75: return round(random.uniform(2, 10), 1)
    else: return round(random.uniform(5, 25), 1)


# 3. GENERATE READINGS ###################################

def generate_readings(location_ids, days=14, interval_minutes=30):
    """Generate congestion readings for all locations over N days."""
    readings = []
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    for loc_idx, loc in enumerate(LOCATIONS):
        loc_id = location_ids[loc_idx]
        current = start

        while current <= now:
            hour = current.hour
            is_weekend = current.weekday() >= 5

            congestion = compute_congestion(loc["zone"], loc["road_type"], hour, is_weekend)
            speed = compute_speed(congestion)
            volume = compute_volume(congestion, hour)
            delay = compute_delay(congestion)

            readings.append({
                "location_id": loc_id,
                "timestamp": current.isoformat(),
                "congestion_level": congestion,
                "speed_mph": speed,
                "volume": volume,
                "delay_minutes": delay,
            })

            current += timedelta(minutes=interval_minutes)

    return readings


# 4. SEED SUPABASE ###################################

def seed_supabase():
    """Connect to Supabase and insert all generated data."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return

    print("🔌 Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Clear existing data (readings first due to FK)
    print("🧹 Clearing existing data...")
    client.table("congestion_readings").delete().neq("id", -1).execute()
    client.table("locations").delete().neq("id", -1).execute()

    # Insert locations
    print(f"📍 Inserting {len(LOCATIONS)} locations...")
    loc_result = client.table("locations").insert(LOCATIONS).execute()
    location_ids = [row["id"] for row in loc_result.data]
    print(f"   ✅ Inserted {len(location_ids)} locations")

    # Generate and insert readings in batches
    print("📊 Generating congestion readings (14 days, 30-min intervals)...")
    readings = generate_readings(location_ids, days=14, interval_minutes=30)
    print(f"   Generated {len(readings)} readings")

    batch_size = 500
    for i in range(0, len(readings), batch_size):
        batch = readings[i:i + batch_size]
        client.table("congestion_readings").insert(batch).execute()
        print(f"   📤 Inserted batch {i // batch_size + 1}/{math.ceil(len(readings) / batch_size)}")

    print(f"\n🎉 Done! Seeded {len(location_ids)} locations and {len(readings)} readings.")


# 5. ADD RECENT 24H READINGS ###################################

def seed_recent_24h():
    """Append the last 24 hours of readings at 15-min intervals (no data cleared)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return

    print("🔌 Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get existing location IDs
    loc_result = client.table("locations").select("id").execute()
    location_ids = [row["id"] for row in loc_result.data]
    if not location_ids:
        print("❌ No locations found — run `python generate_data.py` first to seed the full dataset.")
        return

    print(f"📍 Found {len(location_ids)} existing locations")
    print("📊 Generating last-24h readings (15-min intervals)...")
    readings = generate_readings(location_ids, days=1, interval_minutes=15)
    print(f"   Generated {len(readings)} readings")

    batch_size = 500
    for i in range(0, len(readings), batch_size):
        batch = readings[i:i + batch_size]
        client.table("congestion_readings").insert(batch).execute()
        print(f"   📤 Inserted batch {i // batch_size + 1}/{math.ceil(len(readings) / batch_size)}")

    print(f"\n🎉 Done! Appended {len(readings)} recent readings.")


# 6. EXPORT TO CSV (OPTIONAL) ###################################

def export_csv():
    """Export generated data to CSV files in test_data/ for offline review."""
    import pandas as pd

    out_dir = os.path.join(os.path.dirname(__file__) or ".", "test_data")
    os.makedirs(out_dir, exist_ok=True)

    location_ids = list(range(1, len(LOCATIONS) + 1))
    locations_df = pd.DataFrame(LOCATIONS)
    locations_df.insert(0, "id", location_ids)
    loc_path = os.path.join(out_dir, "locations.csv")
    locations_df.to_csv(loc_path, index=False)
    print(f"📁 Exported {loc_path}")

    readings = generate_readings(location_ids, days=14, interval_minutes=30)
    readings_df = pd.DataFrame(readings)
    read_path = os.path.join(out_dir, "readings.csv")
    readings_df.to_csv(read_path, index=False)
    print(f"📁 Exported {read_path} ({len(readings_df)} rows)")


# 6. RUN ###################################

if __name__ == "__main__":
    import sys
    if "--csv" in sys.argv:
        export_csv()
    elif "--recent" in sys.argv:
        seed_recent_24h()
    else:
        seed_supabase()
