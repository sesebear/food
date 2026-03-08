# Codebook — City Congestion Tracker

Data dictionary for the two Supabase tables used by the congestion tracking pipeline.

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
