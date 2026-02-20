# FDA Food Event Explorer

Shiny for Python app that runs the openFDA Food Adverse Event Reports API on user request. You set parameters (industry, limit, sort), click **Run query** to fetch data, then view and filter results in a table. Implements the query logic from `01_query_api/my_good_query.py`. Built for the DSAI productivity lab.

## Overview

The app lets you:

- **Query the API**: Use the sidebar or the **Run query** button on the Query tab to fetch adverse event reports from the [openFDA Food Event API](https://open.fda.gov/apis/food/event/). Parameters include industry name (e.g. Cosmetics), max records (1–1000), and sort order.
- **View results**: A summary (total matching, returned count) and a table of report number, date, outcomes, reactions, and products.
- **Filter results**: After data is loaded, filter by text (in outcomes, reactions, or products) and by date (e.g. 2024 or 202401) without calling the API again.
- **About**: The About tab describes the data source and parameters.

## Tech stack

| Layer     | Technology        |
|----------|--------------------|
| App      | Shiny for Python   |
| HTTP     | requests           |
| Env      | python-dotenv, .env (optional API key) |
| Data     | pandas (table display) |

## Installation

Assumes a fresh environment (no prior venv).

1. **Prerequisites**: Python 3.10+.
2. **Clone or copy** the repo (or ensure `02_productivity/shiny_app` is on your machine).
3. **Dependencies**:
   ```bash
   cd 02_productivity/shiny_app
   pip install -r requirements.txt
   ```
4. **Optional – API key**: See [API requirements](#api-requirements) below.

## How to run the app

From the app directory:

```bash
cd 02_productivity/shiny_app
shiny run app.py
```

The terminal will print a URL (e.g. `http://127.0.0.1:8000`). Open that URL in a browser.

To use a different port if 8000 is in use:

```bash
shiny run app.py --port 8001
```

Then open http://127.0.0.1:8001.

## API requirements

- **Endpoint**: [openFDA Food Event API](https://open.fda.gov/apis/food/event/) (`https://api.fda.gov/food/event.json`).
- **API key**: Optional. Without a key the API works with a lower rate limit (about 1,000 requests/day). With a key, the limit is much higher (e.g. 120,000/day).
- **Setup**:
  1. Get a key from [openFDA API Key](https://open.fda.gov/apis/authentication/).
  2. Either:
     - Copy `.env.example` to `.env` in `02_productivity/shiny_app` and set `API_KEY=your_key_here`, or
     - Enter the key in the app sidebar under **API key (optional)**.
- No key is required to run or test the app; the key only increases the allowed request rate.

## Usage instructions

1. **Start the app**: Run `shiny run app.py` and open the URL in your browser.
2. **Set parameters** (sidebar): Industry name (e.g. Cosmetics), max records (1–1000), sort (newest or oldest first). Optionally enter an API key.
3. **Run the query**: Click **Run query** in the sidebar or the large **Run query** button on the Query tab. The app fetches data from the API and shows a green summary and a table.
4. **Filter results** (optional): After data loads, use **Search in outcomes, reactions, products** (e.g. NAUSEA, Rash) and **Filter by date** (e.g. 2024) to narrow the table. Filters apply to the current results only; no new API call.
5. **About**: Use the About tab for data source details and parameter descriptions.

## Screenshots

Add your own screenshots below (e.g. Query tab with results, filtered table, About tab) by placing image files in this folder or a `docs/` subfolder and linking them.

| View | Description |
|------|-------------|
| ![Query tab](docs/screenshot-query.png) | Query tab: Run query button, summary, filters, and results table. *(Add `docs/screenshot-query.png`.)* |
| ![About tab](docs/screenshot-about.png) | About tab: data source and parameter info. *(Add `docs/screenshot-about.png`.)* |

If you prefer a single image, add e.g. `screenshot.png` and reference it: `![App in action](screenshot.png)`.

## Project structure

| Item           | Purpose                          |
|----------------|-----------------------------------|
| `app.py`       | Main Shiny app (UI + server)      |
| `api_utils.py` | openFDA API fetch and error handling |
| `requirements.txt` | Python dependencies           |
| `.env.example` | Template for optional `API_KEY`  |
