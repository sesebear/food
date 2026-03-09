# City Congestion Tracker

An AI-powered congestion monitoring pipeline for a city transportation authority. Stores synthetic congestion data in Supabase, serves it through a FastAPI REST API, visualizes it in a Shiny for Python dashboard with an interactive deck.gl map, and generates plain-language insights with Ollama.

---

## System Architecture

```
Supabase (PostgreSQL)  →  FastAPI REST API  →  Shiny Dashboard  →  Ollama AI
       ↑                        ↑                    ↑                 ↑
  Data storage            Data access layer     User interface    AI summaries
```

The pipeline flows left to right:

1. **Supabase** stores two tables — `locations` (20 intersections across 5 zones) and `congestion_readings` (~13 K time-series records over 14 days).
2. **FastAPI** exposes filtered reads (by zone, time window, severity) and a `/summary` endpoint that aggregates data and forwards it to Ollama.
3. **Shiny for Python** renders an interactive light-themed dashboard with a deck.gl map, metric cards, a congestion heatmap, per-zone trend lines, and a sidebar for filters and AI questions.
4. **Ollama** (smollm2:1.7b) receives a compact JSON summary of the queried data and returns a short, actionable narrative.

---

## Tech Stack

| Layer       | Technology                                  |
|-------------|---------------------------------------------|
| Database    | Supabase (PostgreSQL)                       |
| API         | FastAPI + Uvicorn                           |
| Dashboard   | Shiny for Python, Plotly, deck.gl + Maplibre GL JS |
| AI          | Ollama (smollm2:1.7b)                       |
| Data gen    | Python (pandas, random, math)               |
| Environment | python-dotenv, `.env`                       |

---

## Project Structure

```
DL/
├── README.md            # This file
├── codebook.md          # Data dictionary for all tables and test datasets
├── schema.sql           # SQL to create tables in Supabase
├── generate_data.py     # Synthetic data generator + Supabase seeder
├── api.py               # FastAPI REST API
├── app.py               # Shiny Python dashboard
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── test_data/
    ├── validate.py                    # Validates all test datasets (schema + patterns)
    ├── test1_all_zones_7days.csv      # Cross-zone comparison (all 5 zones)
    ├── test2_downtown_rush_hour.csv   # Single-zone rush hour deep dive
    └── test3_weekend_vs_weekday.csv   # Weekday vs weekend temporal patterns
```

---

## Installation

Assumes a fresh environment with Python 3.10+ and Git installed.

1. **Clone and enter the directory**:
   ```bash
   git clone <repo-url>
   cd 05_hackathon/DL
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** — copy the template and fill in your Supabase credentials:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=smollm2:1.7b
   API_HOST=127.0.0.1
   API_PORT=8000
   ```

4. **Create the database schema** — run `schema.sql` in the Supabase SQL Editor (Dashboard → SQL → New Query → paste and run).

5. **Seed the database**:
   ```bash
   python generate_data.py
   ```
   This inserts 20 locations and ~13,440 congestion readings covering the last 14 days.

6. **Install and start Ollama** (if not already running):
   ```bash
   ollama serve              # start the Ollama server
   ollama pull smollm2:1.7b  # download the model
   ```

---

## Usage

Start the API and dashboard in two separate terminals:

**Terminal 1 — API:**
```bash
python api.py
```
The API runs at `http://127.0.0.1:8000`. Interactive docs at `http://127.0.0.1:8000/docs`.

**Terminal 2 — Dashboard:**
```bash
shiny run app.py --port 8001
```
The dashboard opens at `http://127.0.0.1:8001`.

### Dashboard Controls

**Filters (sidebar)**
- **Zone** — filter all views to a single city zone (Downtown, Midtown, Waterfront, Uptown, Industrial)
- **Severity** — filter by congestion level range (Low, Moderate, High, Severe)
- **Time Range** — select Last 24 Hours, 3 Days, 7 Days, or 14 Days
- **Road Type** — filter by Arterial, Collector, or Local roads
- **Refresh Data** — re-fetch all data from the API

**Hour Range (sidebar)**
- **Hours of Day** — a dual-handle range slider (0h–23h) that filters all charts, metrics, the map, and AI summaries to only include readings within the selected hours

**AI Analysis (sidebar)**
- **Ask the AI** — type a custom question about congestion, then click **Generate AI Summary** to get an Ollama-powered narrative in the AI Insights panel

**Main Panel**
- **Metric cards** — Avg Congestion, Peak Congestion, Avg Speed, Avg Delay
- **Live Congestion Map** — interactive deck.gl map with zoom, pan, and hover tooltips showing per-intersection details; color-coded from green (low) to coral (severe)
- **Congestion by Zone** — horizontal bar chart comparing average congestion across zones
- **Congestion Heatmap** — hour-of-day × day-of-week heatmap revealing weekly patterns
- **Congestion by Hour · Per Zone** — line chart showing average congestion per hour for each zone
- **AI Insights** — panel displaying the Ollama-generated summary

---

## API Endpoints

| Method | Path                 | Description                                      |
|--------|----------------------|--------------------------------------------------|
| GET    | `/health`            | Health check — confirms API and database status   |
| GET    | `/locations`         | List all locations; filter by `zone`, `road_type` |
| GET    | `/congestion`        | Readings with filters: `location_id`, `zone`, `start_time`, `end_time`, `min_level`, `max_level`, `limit`, `order` |
| GET    | `/congestion/current`| Latest reading per location                       |
| GET    | `/congestion/stats`  | Aggregated stats: averages, worst locations, hourly pattern |
| GET    | `/summary`           | AI-generated summary via Ollama; accepts `zone`, `start_time`, `end_time`, `question` |

Full interactive docs: `http://127.0.0.1:8000/docs`

---

## Test Datasets

Three CSV files in `test_data/` demonstrate different slices of the system's data. Each can be loaded directly with `pandas.read_csv()` and mirrors the columns returned by the API.

### test1_all_zones_7days.csv

Cross-zone comparison across all 5 city zones (Downtown, Midtown, Waterfront, Uptown, Industrial). Includes readings at morning rush, midday, evening rush, and late-night hours to show how congestion levels differ by zone and time of day. **16 rows, 9 columns.**

Demonstrates: metric cards, zone bar chart, and map all populated; Downtown has the highest congestion.

### test2_downtown_rush_hour.csv

Focused deep dive into the Downtown zone during the 7:00–9:00 AM rush on a single weekday. Covers 4 Downtown locations at 30-min granularity with congestion levels ranging from 62 to 91. **16 rows, 9 columns.**

Demonstrates: filtering by zone + hour range; the heatmap lights up at morning rush hours; arterials (Broadway & 5th Ave) spike higher than collectors (Center Blvd & Park Rd).

### test3_weekend_vs_weekday.csv

Side-by-side weekday vs weekend readings for 4 locations across Downtown, Midtown, Industrial, and Waterfront. Includes a `day_type` column (`weekday` or `weekend`) for easy comparison. **16 rows, 10 columns.**

Demonstrates: the congestion model's weekend drop-off. Industrial goes from ~55 on weekdays to ~10–12 on weekends. Downtown drops from ~80 to ~35–42. This pattern appears in the heatmap (lighter weekend rows) and the AI summary when asked about weekly trends.

### Validating the test datasets

Run the validator from the project root — it checks schema, value ranges, and expected congestion patterns for all 3 files:

```bash
python test_data/validate.py
```

Expected output: `9/9 checks passed`.

### Regenerating or exporting full datasets

```bash
python generate_data.py --csv   # writes test_data/locations.csv and test_data/readings.csv
```

---

## Test Executions

### Test 1 — Default view (all zones, last 7 days, full hour range)

1. Start the API (`python api.py`) and dashboard (`shiny run app.py --port 8001`).
2. Open `http://127.0.0.1:8001` in a browser.
3. Leave all filters at their defaults: **All Zones**, **All Levels**, **Last 7 Days**, **All Roads**, hours **0h–23h**.
4. **Expected**:
   - Four metric cards appear at the top showing Avg Congestion (~40–55), Peak Congestion (near 100), Avg Speed (~25–35 mph), and Avg Delay (~4–8 min).
   - The **Live Congestion Map** displays 20 colored bubbles on a light basemap around lower Manhattan. Bubbles are green (low), cyan (moderate), yellow (high), or coral (severe). Hovering over a bubble shows the intersection name, zone, road type, congestion score, speed, volume, and delay. Scrolling zooms in and out.
   - The **Congestion by Zone** bar chart shows all 5 zones, with Downtown having the highest average.
   - The **Congestion Heatmap** shows a 7-row (Mon–Sun) × 24-column (0:00–23:00) grid with clear morning (7–9 AM) and evening (4–6 PM) hot spots in yellow/coral, and cooler overnight cells in green.
   - The **Congestion by Hour** line chart shows 5 zone lines with peaks during rush hours.

### Test 2 — Hour range filter + zone filter

1. Set **Zone** to **Downtown**.
2. Drag the **Hours of Day** slider to **7h–18h** (daytime only).
3. **Expected**:
   - Metric cards update to reflect only Downtown readings between 7 AM and 6 PM — Avg Congestion is noticeably higher (~55–70) than the default all-zones view.
   - The **map** shows only Downtown intersections (4 bubbles), predominantly yellow/coral.
   - The **heatmap** columns narrow to 7:00–18:00 only, highlighting weekday morning and evening rush.
   - The **Congestion by Hour** chart x-axis shows only 7:00–18:00, with a single Downtown line peaking at morning and evening rush.
   - The **zone bar chart** shows only Downtown.

### Test 3 — AI summary generation

1. Reset filters to **All Zones**, **Last 7 Days**, hours **0h–23h**.
2. In the **Ask the AI** text area, type: *"Which intersections have the worst congestion and what times should commuters avoid?"*
3. Click **Generate AI Summary**.
4. **Expected**:
   - The AI Insights panel displays a loading message, then after a few seconds fills with a narrative from Ollama (smollm2:1.7b).
   - The summary references specific intersection names (e.g., "Main St & 1st Ave"), zones, congestion levels, and peak hours.
   - The response includes actionable recommendations such as which areas or times to avoid.

---

## Data

All data is synthetic, generated by `generate_data.py`. See `codebook.md` for the full data dictionary covering both database tables and all test dataset files.

- **20 locations** across 5 city zones (Downtown, Midtown, Waterfront, Uptown, Industrial)
- **~13,440 readings** at 30-minute intervals over 14 days
- Congestion patterns follow realistic time-of-day curves with morning/evening rush hours
- Zone and road-type profiles create differentiated patterns (Downtown is busiest; Industrial is quiet on weekends)
- **3 test datasets** in `test_data/` provide representative subsets for offline review

```bash
python generate_data.py           # seed Supabase with full dataset
python generate_data.py --csv     # export locations.csv and readings.csv to test_data/
```
