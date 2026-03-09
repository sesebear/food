# Codebook — City Congestion Tracker

Data dictionary for the Supabase tables, test datasets, and pipeline files in this project.

---

## Pipeline Files

| File               | Purpose                                                                                     |
|--------------------|---------------------------------------------------------------------------------------------|
| `schema.sql`       | SQL DDL to create the `locations` and `congestion_readings` tables in Supabase (with indexes and RLS policies). Run once in the Supabase SQL Editor. |
| `generate_data.py` | Generates synthetic congestion data for 20 locations over 14 days and seeds it into Supabase. Also supports `--csv` to export to `test_data/`. |
| `api.py`           | FastAPI REST API. Connects to Supabase, exposes filtered query endpoints (`/locations`, `/congestion`, `/congestion/stats`), and a `/summary` endpoint that sends aggregated data to Ollama for AI analysis. |
| `app.py`           | Shiny for Python dashboard. Fetches data from the API, renders an interactive deck.gl map, Plotly charts (bar, heatmap, line), metric cards, and an AI Insights panel. Sidebar provides zone, severity, time range, road type, and hour range filters. |
| `requirements.txt` | Python dependencies — pin-free for latest compatibility. Install with `pip install -r requirements.txt`. |
| `.env.example`     | Template for environment variables: `SUPABASE_URL`, `SUPABASE_KEY`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `API_HOST`, `API_PORT`. |

---

## Table: `locations`

Represents monitored intersections, road segments, or zones in the city.

| Column      | Type             | Description                                                        |
|-------------|------------------|--------------------------------------------------------------------|
| `id`        | `SERIAL` (PK)   | Auto-incrementing unique identifier for the location               |
| `name`      | `TEXT`           | Human-readable intersection or segment name (e.g. "Main St & 1st Ave") |
| `zone`      | `TEXT`           | City zone grouping: Downtown, Midtown, Waterfront, Uptown, Industrial |
| `road_type` | `TEXT`           | Road classification: `arterial`, `collector`, or `local`           |
| `latitude`  | `DOUBLE PRECISION` | GPS latitude (WGS 84)                                           |
| `longitude` | `DOUBLE PRECISION` | GPS longitude (WGS 84)                                          |

**Row count:** 20 locations (4 per zone)

---

## Table: `congestion_readings`

Time-series congestion measurements recorded at each location.

| Column             | Type                  | Description                                                                 |
|--------------------|-----------------------|-----------------------------------------------------------------------------|
| `id`               | `SERIAL` (PK)        | Auto-incrementing unique identifier for the reading                         |
| `location_id`      | `INTEGER` (FK → `locations.id`) | Which location this reading belongs to                          |
| `timestamp`        | `TIMESTAMPTZ`        | When the measurement was recorded (UTC, ISO 8601)                           |
| `congestion_level` | `INTEGER` (0–100)    | Composite congestion score: 0 = free-flow, 100 = gridlock                   |
| `speed_mph`        | `DOUBLE PRECISION`   | Average observed speed at the location (miles per hour)                      |
| `volume`           | `INTEGER`            | Vehicle count observed in the measurement interval (vehicles per 30 min)     |
| `delay_minutes`    | `DOUBLE PRECISION`   | Estimated additional travel delay compared to free-flow (minutes)            |

**Row count:** ~13,440 readings (20 locations × 672 intervals over 14 days at 30-min spacing)

---

## Congestion Level Interpretation

| Range   | Label      | Description                          |
|---------|------------|--------------------------------------|
| 0–30    | Low        | Free-flow or light traffic           |
| 30–60   | Moderate   | Noticeable slowdowns                 |
| 60–80   | High       | Significant delays, slow movement    |
| 80–100  | Severe     | Near-gridlock, major delays          |

---

## Data Generation

All data is **synthetic**, produced by `generate_data.py`. The congestion model uses:

- **Zone profiles** — each zone has a different base congestion level and weekend multiplier
- **Time-of-day curves** — morning rush (7–9 AM), evening rush (4–6 PM), with lower overnight values
- **Road-type multipliers** — arterials are ~15% more congested than collectors; locals are ~20% less
- **Gaussian noise** — ±8 points of random variation per reading for realism

Speed, volume, and delay are derived from the congestion level using simple scaling functions.

---

## Test Datasets (`test_data/`)

Three CSV files provide representative subsets of the full database for offline review, grading, and reproducibility.

### test1_all_zones_7days.csv

| Column             | Type      | Description                                          |
|--------------------|-----------|------------------------------------------------------|
| `location_id`      | INTEGER   | FK to `locations.id`                                 |
| `name`             | TEXT      | Intersection name                                    |
| `zone`             | TEXT      | City zone                                            |
| `road_type`        | TEXT      | Road classification                                  |
| `timestamp`        | TIMESTAMPTZ | When the reading was recorded (ISO 8601, UTC)      |
| `congestion_level` | INTEGER   | 0–100 congestion score                               |
| `speed_mph`        | FLOAT     | Average speed (mph)                                  |
| `volume`           | INTEGER   | Vehicles per interval                                |
| `delay_minutes`    | FLOAT     | Additional travel delay (minutes)                    |

**Rows:** 16 — samples from all 5 zones at morning rush, midday, evening rush, and overnight.

### test2_downtown_rush_hour.csv

Same columns as test1. **Rows:** 16 — 4 Downtown locations at 30-min intervals during the 7:00–9:00 AM weekday rush.

### test3_weekend_vs_weekday.csv

Same columns as test1, plus:

| Column     | Type | Description                            |
|------------|------|----------------------------------------|
| `day_type` | TEXT | `weekday` or `weekend` label           |

**Rows:** 16 — paired weekday/weekend readings for 4 locations across 4 zones to highlight temporal patterns.
