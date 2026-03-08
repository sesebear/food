# City Congestion Tracker

An AI-powered congestion monitoring pipeline for a city transportation authority. Stores synthetic congestion data in Supabase, serves it through a FastAPI REST API, visualizes it in a Shiny for Python dashboard, and generates plain-language insights with Ollama.

---

## System Architecture

```
Supabase (PostgreSQL)  →  FastAPI REST API  →  Shiny Dashboard  →  Ollama AI
       ↑                        ↑                    ↑                 ↑
  Data storage            Data access layer     User interface    AI summaries
```

The pipeline flows left to right:

1. **Supabase** stores two tables — `locations` (20 intersections across 5 zones) and `congestion_readings` (~13 K time-series records over 14 days).
2. **FastAPI** exposes filtered reads (by zone, time window, severity) and an `/summary` endpoint that aggregates data and forwards it to Ollama.
3. **Shiny for Python** renders an interactive dark-themed dashboard with metric cards, plotly charts, and a sidebar for filters and AI questions.
4. **Ollama** receives a compact JSON summary of the queried data and returns a short, actionable narrative.

---

## Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Database    | Supabase (PostgreSQL)             |
| API         | FastAPI + Uvicorn                 |
| Dashboard   | Shiny for Python, Plotly, shinywidgets |
| AI          | Ollama (llama3.2:3b or any model) |
| Data gen    | Python (pandas, random, math)     |
| Environment | python-dotenv, `.env`             |

---

## Project Structure

```
DL/
├── README.md            # This file
├── codebook.md          # Data dictionary for both tables
├── schema.sql           # SQL to create tables in Supabase
├── generate_data.py     # Synthetic data generator + Supabase seeder
├── api.py               # FastAPI REST API
├── app.py               # Shiny Python dashboard
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variable template
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
   OLLAMA_MODEL=llama3.2:3b
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
   ollama serve           # start the Ollama server
   ollama pull llama3.2:3b  # download the model
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
shiny run app.py
```
The dashboard opens at `http://127.0.0.1:8000` (Shiny default) or the port shown in the terminal.

### Dashboard Controls

- **Zone** — filter all views to a single city zone
- **Severity** — filter by congestion level range
- **Time Range** — select 24 hours, 3 days, 7 days, or 14 days
- **Refresh Data** — re-fetch from the API
- **AI Question** — pick a template or type a custom question, then click **Generate AI Summary**

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

## Test Executions

### Test 1 — Default view (all zones, last 7 days)

1. Start the API (`python api.py`) and dashboard (`shiny run app.py`).
2. Open the dashboard in a browser.
3. **Expected**: Four metric cards display (avg congestion, peak, avg speed, avg delay). The zone bar chart shows all 5 zones. The hourly chart shows a clear morning/evening rush pattern. The timeline shows 7 days of data with per-zone lines.

### Test 2 — Zone filter + severity filter

1. Select **Downtown** from the Zone dropdown.
2. Select **High (60–80)** from the Severity dropdown.
3. **Expected**: Metrics update to show only high-severity Downtown readings. Charts narrow to Downtown data only. Congestion averages are higher (60–80 range).

### Test 3 — AI summary generation

1. Set filters to **All Zones**, **Last 7 Days**.
2. Select the question: *"Which intersections are currently showing the highest congestion?"*
3. Click **Generate AI Summary**.
4. **Expected**: After a few seconds, the AI Insights panel at the bottom fills with a narrative mentioning specific intersection names, congestion levels, and zones. The summary includes actionable recommendations.

---

## Data

All data is synthetic, generated by `generate_data.py`. See `codebook.md` for the full data dictionary.

- **20 locations** across 5 city zones (Downtown, Midtown, Waterfront, Uptown, Industrial)
- **~13,440 readings** at 30-minute intervals over 14 days
- Congestion patterns follow realistic time-of-day curves with morning/evening rush hours
- Zone and road-type profiles create differentiated patterns (Downtown is busiest; Industrial is quiet on weekends)

To regenerate or export CSV files:
```bash
python generate_data.py           # seed Supabase
python generate_data.py --csv     # export to CSV files instead
```
