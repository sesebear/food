# validate.py
# Test Dataset Validator — City Congestion Tracker
# Loads each test CSV, checks schema and expected patterns, and prints results.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import os
import pandas as pd # for data manipulation

## 0.2 Paths #################################

# Resolve test_data directory relative to this script
DIR = os.path.dirname(__file__) or "."

TESTS = {
    "test1_all_zones_7days.csv":    {"min_rows": 10, "required_cols": ["location_id", "name", "zone", "road_type", "timestamp", "congestion_level", "speed_mph", "volume", "delay_minutes"]},
    "test2_downtown_rush_hour.csv": {"min_rows": 10, "required_cols": ["location_id", "name", "zone", "road_type", "timestamp", "congestion_level", "speed_mph", "volume", "delay_minutes"]},
    "test3_weekend_vs_weekday.csv": {"min_rows": 10, "required_cols": ["location_id", "name", "zone", "road_type", "day_type", "timestamp", "congestion_level", "speed_mph", "volume", "delay_minutes"]},
}

# 1. VALIDATION HELPERS ###################################

def check_schema(df, required_cols, name):
    """Verify all required columns are present."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"  ❌ Missing columns: {missing}")
        return False
    print(f"  ✅ Schema OK — {len(df.columns)} columns, {len(df)} rows")
    return True


def check_ranges(df, name):
    """Verify congestion_level is 0-100, speed > 0, volume > 0."""
    ok = True
    if (df["congestion_level"] < 0).any() or (df["congestion_level"] > 100).any():
        print(f"  ❌ congestion_level out of 0–100 range")
        ok = False
    if (df["speed_mph"] <= 0).any():
        print(f"  ❌ speed_mph has non-positive values")
        ok = False
    if (df["volume"] <= 0).any():
        print(f"  ❌ volume has non-positive values")
        ok = False
    if ok:
        print(f"  ✅ Value ranges OK — congestion [{df['congestion_level'].min()}–{df['congestion_level'].max()}], speed [{df['speed_mph'].min()}–{df['speed_mph'].max()}]")
    return ok


def check_test1_patterns(df):
    """Test 1: Downtown should have higher avg congestion than Industrial."""
    zone_avg = df.groupby("zone")["congestion_level"].mean()
    zones_present = set(df["zone"].unique())
    expected_zones = {"Downtown", "Midtown", "Waterfront", "Uptown", "Industrial"}
    if not expected_zones.issubset(zones_present):
        print(f"  ❌ Expected 5 zones, found: {zones_present}")
        return False
    if zone_avg["Downtown"] > zone_avg["Industrial"]:
        print(f"  ✅ Pattern OK — Downtown avg ({zone_avg['Downtown']:.0f}) > Industrial avg ({zone_avg['Industrial']:.0f})")
        return True
    print(f"  ⚠️  Unexpected: Downtown ({zone_avg['Downtown']:.0f}) ≤ Industrial ({zone_avg['Industrial']:.0f})")
    return False


def check_test2_patterns(df):
    """Test 2: All rows should be Downtown, with congestion ≥ 60."""
    zones = df["zone"].unique()
    if list(zones) != ["Downtown"]:
        print(f"  ❌ Expected only Downtown, found: {list(zones)}")
        return False
    high_pct = (df["congestion_level"] >= 60).mean() * 100
    print(f"  ✅ Pattern OK — 100% Downtown, {high_pct:.0f}% of readings ≥ 60 (rush hour)")
    return True


def check_test3_patterns(df):
    """Test 3: Weekday congestion should be higher than weekend on average."""
    if "day_type" not in df.columns:
        print(f"  ❌ Missing day_type column")
        return False
    avg = df.groupby("day_type")["congestion_level"].mean()
    if avg["weekday"] > avg["weekend"]:
        print(f"  ✅ Pattern OK — weekday avg ({avg['weekday']:.0f}) > weekend avg ({avg['weekend']:.0f})")
        return True
    print(f"  ⚠️  Unexpected: weekday ({avg['weekday']:.0f}) ≤ weekend ({avg['weekend']:.0f})")
    return False


# 2. RUN VALIDATION ###################################

PATTERN_CHECKS = {
    "test1_all_zones_7days.csv":    check_test1_patterns,
    "test2_downtown_rush_hour.csv": check_test2_patterns,
    "test3_weekend_vs_weekday.csv": check_test3_patterns,
}

if __name__ == "__main__":
    passed, total = 0, 0

    for filename, spec in TESTS.items():
        path = os.path.join(DIR, filename)
        print(f"\n{'─' * 50}")
        print(f"📄 {filename}")
        print(f"{'─' * 50}")

        if not os.path.exists(path):
            print(f"  ❌ File not found: {path}")
            total += 1
            continue

        df = pd.read_csv(path)
        total += 3  # schema + ranges + pattern

        if check_schema(df, spec["required_cols"], filename):
            passed += 1
        if check_ranges(df, filename):
            passed += 1
        if PATTERN_CHECKS[filename](df):
            passed += 1

    print(f"\n{'═' * 50}")
    print(f"Results: {passed}/{total} checks passed")
    print(f"{'═' * 50}")
