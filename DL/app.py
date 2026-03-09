# app.py
# Shiny Python Dashboard — City Congestion Tracker
# City Congestion Tracker — DL Challenge 2026
#
# A beautiful, modern dashboard that connects to the FastAPI REST API
# to display congestion data and generate AI-powered summaries via Ollama.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import html as html_mod
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

## 0.2 Load Environment #################################

if os.path.exists(".env"): load_dotenv()

API_BASE = f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"

## 0.3 Custom CSS #################################

CUSTOM_CSS = """
<style>
:root {
    --bg-primary: #f8fafc;
    --bg-secondary: #ffffff;
    --bg-card: #ffffff;
    --bg-card-hover: #f1f5f9;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --accent-blue: #7c9cf5;
    --accent-cyan: #67d4e2;
    --accent-green: #6ee7b7;
    --accent-amber: #fcd34d;
    --accent-red: #fca5a5;
    --accent-purple: #b4a0f4;
    --border-color: #e2e8f0;
    --shadow: 0 4px 24px rgba(0,0,0,0.06);
    --radius: 16px;
}

body {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    margin: 0; padding: 0;
}

.main-header {
    background: #ffffff;
    border-bottom: 1px solid var(--border-color);
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.main-header h1 {
    margin: 0; font-size: 1.6rem; font-weight: 700;
    background: linear-gradient(135deg, #7c9cf5, #67d4e2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
}
.main-header .subtitle {
    color: var(--text-secondary); font-size: 0.85rem; margin-top: 2px;
}

.content-wrapper {
    display: flex;
    min-height: calc(100vh - 80px);
}

.sidebar-panel {
    width: 280px;
    min-width: 280px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
}
.sidebar-panel label {
    color: var(--text-secondary) !important;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 4px;
}
.sidebar-panel textarea {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    font-size: 0.88rem !important;
    width: 100% !important;
    resize: vertical !important;
    font-family: 'Inter', sans-serif !important;
    line-height: 1.5 !important;
    transition: border-color 0.2s;
}
.sidebar-panel textarea:focus {
    border-color: var(--accent-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(124,156,245,0.2) !important;
}
.sidebar-panel select, .sidebar-panel input[type="date"], .sidebar-panel input[type="text"] {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    font-size: 0.88rem !important;
    width: 100% !important;
    transition: border-color 0.2s;
}
.sidebar-panel select:focus, .sidebar-panel input:focus {
    border-color: var(--accent-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(124,156,245,0.2) !important;
}

.main-panel {
    flex: 1;
    padding: 24px 28px;
    overflow-y: auto;
    background: var(--bg-primary);
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 20px;
    transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow);
    background: var(--bg-card-hover);
}
.metric-label {
    color: var(--text-secondary);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}
.metric-value {
    font-size: 2rem;
    font-weight: 800;
    margin: 6px 0 2px;
    letter-spacing: -0.03em;
}
.metric-sub {
    color: var(--text-secondary);
    font-size: 0.8rem;
}
.metric-blue .metric-value { color: #6889db; }
.metric-amber .metric-value { color: #e5a832; }
.metric-red .metric-value { color: #e87777; }
.metric-green .metric-value { color: #4dbf8a; }

.chart-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
}
.chart-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 20px;
    overflow: hidden;
}
.chart-card-full {
    grid-column: 1 / -1;
}
.chart-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 12px;
    color: var(--text-primary);
}

.ai-card {
    background: linear-gradient(135deg, #faf5ff 0%, #f0f5ff 50%, #f5faff 100%);
    border: 1px solid #d8ccf0;
    border-radius: var(--radius);
    padding: 24px;
    margin-top: 0;
}
.ai-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px;
}
.ai-header h3 {
    margin: 0; font-size: 1.05rem; font-weight: 700;
    color: #7c6db0;
}
.ai-badge {
    background: rgba(124,109,176,0.1);
    color: #7c6db0;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.ai-body {
    color: var(--text-primary);
    line-height: 1.7;
    font-size: 0.9rem;
}
.ai-body p { margin-bottom: 10px; }
.ai-body strong { color: #4d8ea8; }
.ai-body h1, .ai-body h2, .ai-body h3, .ai-body h4 {
    color: #5a7abf; font-size: 1rem; margin: 14px 0 6px;
}
.ai-body ul, .ai-body ol { padding-left: 20px; }
.ai-body li { margin-bottom: 4px; }
.ai-body code {
    background: rgba(124,156,245,0.1);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
}

.btn-ai {
    background: linear-gradient(135deg, #b4a0f4, #7c9cf5) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 20px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    cursor: pointer !important;
    width: 100% !important;
    transition: opacity 0.2s, transform 0.15s !important;
    letter-spacing: 0.01em;
}
.btn-ai:hover {
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
}

.btn-refresh {
    background: var(--bg-secondary) !important;
    color: #5a7abf !important;
    border: 1px solid #a8bce6 !important;
    border-radius: 10px !important;
    padding: 10px 18px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    cursor: pointer !important;
    width: 100% !important;
    transition: background 0.2s !important;
}
.btn-refresh:hover {
    background: #f0f4ff !important;
}

.section-label {
    color: var(--text-secondary);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    margin: 0 0 10px;
    padding-top: 6px;
    border-top: 1px solid var(--border-color);
}

.loading-shimmer {
    color: var(--text-secondary);
    font-style: italic;
}

.zone-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}

.map-section {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 0;
    margin-bottom: 24px;
    overflow: hidden;
    position: relative;
}
.map-section iframe {
    width: 100% !important;
    height: 620px !important;
    border: none;
    display: block;
    border-radius: 0 0 var(--radius) var(--radius);
}
.map-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    margin-bottom: 0;
    flex-wrap: wrap;
    gap: 10px;
}
.map-legend {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-secondary);
    font-size: 0.78rem;
    font-weight: 500;
}
.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}

/* Slider theme */
.sidebar-panel .irs--shiny .irs-bar { background: var(--accent-blue); border-color: var(--accent-blue); }
.sidebar-panel .irs--shiny .irs-handle { background: var(--accent-blue); border-color: var(--accent-blue); }
.sidebar-panel .irs--shiny .irs-line { background: var(--bg-primary); border-color: var(--border-color); }
.sidebar-panel .irs--shiny .irs-single { background: var(--accent-blue); color: white; border-radius: 6px; }
.sidebar-panel .irs--shiny .irs-min, .sidebar-panel .irs--shiny .irs-max { color: var(--text-secondary); background: transparent; }
.sidebar-panel .irs--shiny .irs-grid-text { color: var(--text-secondary); }

/* Plotly overrides */
.js-plotly-plot .plotly .modebar { right: 5px !important; }
.js-plotly-plot .plotly .modebar-btn path { fill: var(--text-secondary) !important; }
</style>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
"""

# 1. PLOTLY THEME ###################################

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#64748b", family="Inter, sans-serif", size=12),
    margin=dict(l=40, r=20, t=10, b=40),
    xaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0"),
    yaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#64748b")),
    hoverlabel=dict(bgcolor="#ffffff", font_color="#1e293b", bordercolor="#e2e8f0"),
)

CONGESTION_COLORS = ["#6ee7b7", "#67e8f9", "#93c5fd", "#fcd34d", "#fca5a5"]

ZONE_COLORS = {
    "Downtown": "#f9a8a8",
    "Midtown": "#fcd686",
    "Waterfront": "#7dd3e8",
    "Uptown": "#7ee8ba",
    "Industrial": "#b8a4f0",
}

# 2. UI LAYOUT ###################################

app_ui = ui.page_fluid(
    ui.HTML(CUSTOM_CSS),

    # Header
    ui.HTML("""
    <div class="main-header">
        <div>
            <h1>🚦 City Congestion Tracker</h1>
            <div class="subtitle">Real-time congestion monitoring · AI-powered insights</div>
        </div>
        <div></div>
    </div>
    """),

    # Main content: sidebar + panel
    ui.HTML('<div class="content-wrapper">'),

    # --- Sidebar ---
    ui.HTML('<div class="sidebar-panel">'),

    ui.HTML('<div class="section-label">Filters</div>'),
    ui.input_select("zone", "Zone", choices=["All Zones", "Downtown", "Midtown", "Waterfront", "Uptown", "Industrial"], selected="All Zones"),
    ui.input_select("severity", "Severity", choices=["All Levels", "Low (0–30)", "Moderate (30–60)", "High (60–80)", "Severe (80–100)"], selected="All Levels"),
    ui.input_select("time_range", "Time Range", choices=["Last 24 Hours", "Last 3 Days", "Last 7 Days", "Last 14 Days"], selected="Last 7 Days"),
    ui.input_select("road_type_filter", "Road Type", choices=["All Roads", "Arterial", "Collector", "Local"], selected="All Roads"),
    ui.input_action_button("refresh", "↻  Refresh Data", class_="btn-refresh"),

    ui.HTML('<div class="section-label" style="margin-top:10px;">Hour Range</div>'),
    ui.input_slider("hour_range", "Hours of Day", min=0, max=23, value=(0, 23), step=1, post="h"),

    ui.HTML('<div class="section-label" style="margin-top:10px;">AI Analysis</div>'),
    ui.input_text_area("ai_question_text", "Ask the AI", placeholder="e.g. Which areas have the worst congestion right now? What time should I avoid Downtown?", rows=4),
    ui.input_action_button("ask_ai", "✦  Generate AI Summary", class_="btn-ai"),

    ui.HTML('</div>'),  # end sidebar

    # --- Main Panel ---
    ui.HTML('<div class="main-panel">'),

    # Metric Cards
    ui.output_ui("metric_cards"),

    # Map (full width, prominent)
    ui.HTML('<div class="map-section">'),
    ui.HTML("""<div class="map-header">
        <div class="chart-title" style="margin-bottom:0;">Live Congestion Map</div>
        <div class="map-legend">
            <span class="legend-item"><span class="legend-dot" style="background:#6ee7b7;"></span>Low 0–30</span>
            <span class="legend-item"><span class="legend-dot" style="background:#67e8f9;"></span>Moderate 30–60</span>
            <span class="legend-item"><span class="legend-dot" style="background:#fcd34d;"></span>High 60–80</span>
            <span class="legend-item"><span class="legend-dot" style="background:#fca5a5;"></span>Severe 80–100</span>
        </div>
    </div>"""),
    ui.output_ui("congestion_map"),
    ui.HTML('</div>'),

    # Chart Grid (zone + hourly side by side, then timeline)
    ui.HTML('<div class="chart-grid">'),
    ui.HTML('<div class="chart-card">'),
    ui.HTML('<div class="chart-title">Congestion by Zone</div>'),
    output_widget("zone_chart"),
    ui.HTML('</div>'),

    ui.HTML('<div class="chart-card">'),
    ui.HTML('<div class="chart-title">Congestion Heatmap · Hour × Day</div>'),
    output_widget("hourly_chart"),
    ui.HTML('</div>'),

    ui.HTML('<div class="chart-card chart-card-full">'),
    ui.HTML('<div class="chart-title">Congestion by Hour · Per Zone</div>'),
    output_widget("timeline_chart"),
    ui.HTML('</div>'),
    ui.HTML('</div>'),  # end chart-grid

    # AI Insights
    ui.output_ui("ai_panel"),

    ui.HTML('</div>'),  # end main-panel
    ui.HTML('</div>'),  # end content-wrapper
)


# 3. SERVER LOGIC ###################################

def server(input, output, session):

    ## 3.1 Reactive Values #################################

    api_data = reactive.Value({"stats": {}, "readings": [], "locations": []})
    ai_summary = reactive.Value("")
    ai_loading = reactive.Value(False)

    ## 3.2 Helpers #################################

    def get_time_range_iso():
        """Convert the time range dropdown to start/end ISO strings."""
        mapping = {
            "Last 24 Hours": 1,
            "Last 3 Days": 3,
            "Last 7 Days": 7,
            "Last 14 Days": 14,
        }
        days = mapping.get(input.time_range(), 7)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return start.isoformat(), end.isoformat()

    def get_severity_range():
        """Convert severity dropdown to min/max level."""
        mapping = {
            "All Levels": (None, None),
            "Low (0–30)": (0, 30),
            "Moderate (30–60)": (30, 60),
            "High (60–80)": (60, 80),
            "Severe (80–100)": (80, 100),
        }
        return mapping.get(input.severity(), (None, None))

    def build_params():
        """Build query params dict from current filter selections."""
        start, end = get_time_range_iso()
        min_lev, max_lev = get_severity_range()
        params = {"start_time": start, "end_time": end, "limit": 5000}
        if input.zone() != "All Zones":
            params["zone"] = input.zone()
        if min_lev is not None:
            params["min_level"] = min_lev
        if max_lev is not None:
            params["max_level"] = max_lev
        return params

    ## 3.3 Fetch Data on Filter Change #################################

    @reactive.effect
    @reactive.event(input.refresh, input.zone, input.severity, input.time_range, input.road_type_filter, ignore_none=False)
    def fetch_data():
        params = build_params()
        try:
            with httpx.Client(timeout=30) as client:
                readings_resp = client.get(f"{API_BASE}/congestion", params=params)
                locs_resp = client.get(f"{API_BASE}/locations")

            readings = readings_resp.json().get("data", []) if readings_resp.status_code == 200 else []
            locations = locs_resp.json().get("data", []) if locs_resp.status_code == 200 else []

            api_data.set({"readings": readings, "locations": locations})
        except Exception as e:
            print(f"API error: {e}")
            api_data.set({"readings": [], "locations": [], "error": str(e)})

    ## 3.3b Hour-Filtered Data (drives all charts and metrics) ############

    @reactive.calc
    def filtered_readings():
        """Filter readings by the selected hour range."""
        data = api_data.get()
        readings = data.get("readings", [])
        if not readings:
            return []
        df = pd.DataFrame(readings)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        h_min, h_max = input.hour_range()
        filtered = df[(df["hour"] >= h_min) & (df["hour"] <= h_max)]
        return filtered.to_dict(orient="records") if not filtered.empty else []

    @reactive.calc
    def filtered_stats():
        """Compute stats from hour-filtered readings."""
        records = filtered_readings()
        if not records:
            return {}
        df = pd.DataFrame(records)
        df["congestion_level"] = pd.to_numeric(df["congestion_level"])
        df["speed_mph"] = pd.to_numeric(df["speed_mph"])
        df["delay_minutes"] = pd.to_numeric(df["delay_minutes"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour

        stats = {
            "avg_congestion": round(df["congestion_level"].mean(), 1),
            "max_congestion": int(df["congestion_level"].max()),
            "min_congestion": int(df["congestion_level"].min()),
            "avg_speed_mph": round(df["speed_mph"].mean(), 1),
            "avg_delay_min": round(df["delay_minutes"].mean(), 1),
            "total_readings": len(df),
        }

        loc_avg = (df.groupby("location_id")["congestion_level"]
                   .mean().sort_values(ascending=False).head(5))
        stats["worst_locations"] = [
            {"location_id": int(lid), "avg_congestion": round(val, 1)}
            for lid, val in loc_avg.items()
        ]

        hourly = df.groupby("hour")["congestion_level"].mean().sort_index()
        stats["hourly_pattern"] = [
            {"hour": int(h), "avg_congestion": round(v, 1)}
            for h, v in hourly.items()
        ]

        return stats

    ## 3.4 AI Summary #################################

    @reactive.effect
    @reactive.event(input.ask_ai)
    def fetch_ai_summary():
        ai_loading.set(True)
        h_min, h_max = input.hour_range()
        hour_label = f"{h_min}:00–{h_max}:00" if (h_min, h_max) != (0, 23) else "all hours"
        question = input.ai_question_text().strip() or "Summarize current congestion conditions and provide actionable recommendations."
        question_with_hours = f"{question} (Only consider data from hours {hour_label}.)"

        # Build stats locally from filtered data so the AI sees the same slice
        stats = filtered_stats()
        if not stats:
            ai_summary.set("No congestion data available for the selected filters and hour range.")
            ai_loading.set(False)
            return

        # Resolve location names for worst locations
        locs = api_data.get().get("locations", [])
        loc_map = {l["id"]: l for l in locs}
        for wl in stats.get("worst_locations", []):
            loc = loc_map.get(wl["location_id"], {})
            wl["name"] = loc.get("name", f"Location {wl['location_id']}")
            wl["zone"] = loc.get("zone", "Unknown")

        params = build_params()
        params.pop("limit", None)
        params.pop("min_level", None)
        params.pop("max_level", None)
        params["question"] = question_with_hours

        try:
            with httpx.Client(timeout=180) as client:
                resp = client.get(f"{API_BASE}/summary", params=params)
            if resp.status_code == 200:
                ai_summary.set(resp.json().get("summary", "No summary returned."))
            else:
                ai_summary.set(f"API error: {resp.status_code}")
        except Exception as e:
            ai_summary.set(f"Could not reach API: {e}")
        finally:
            ai_loading.set(False)

    ## 3.5 Metric Cards #################################

    @render.ui
    def metric_cards():
        data = api_data.get()
        error = data.get("error")
        stats = filtered_stats()

        if error:
            return ui.HTML(f'<div class="metric-card" style="grid-column:1/-1"><div class="metric-label">API CONNECTION ERROR</div><div class="metric-sub" style="color:var(--accent-red)">Could not reach the API at {API_BASE}. Make sure the API is running: <code>python api.py</code></div></div>')

        avg = stats.get("avg_congestion", "—")
        mx = stats.get("max_congestion", "—")
        spd = stats.get("avg_speed_mph", "—")
        dly = stats.get("avg_delay_min", "—")
        total = stats.get("total_readings", 0)

        # Color the avg congestion based on severity
        if isinstance(avg, (int, float)):
            if avg >= 70: color_class = "metric-red"
            elif avg >= 45: color_class = "metric-amber"
            else: color_class = "metric-green"
        else:
            color_class = "metric-blue"

        return ui.HTML(f"""
        <div class="metric-grid">
            <div class="metric-card {color_class}">
                <div class="metric-label">Avg Congestion</div>
                <div class="metric-value">{avg}</div>
                <div class="metric-sub">out of 100 · {total:,} readings</div>
            </div>
            <div class="metric-card metric-red">
                <div class="metric-label">Peak Congestion</div>
                <div class="metric-value">{mx}</div>
                <div class="metric-sub">maximum recorded level</div>
            </div>
            <div class="metric-card metric-blue">
                <div class="metric-label">Avg Speed</div>
                <div class="metric-value">{spd}</div>
                <div class="metric-sub">miles per hour</div>
            </div>
            <div class="metric-card metric-amber">
                <div class="metric-label">Avg Delay</div>
                <div class="metric-value">{dly}</div>
                <div class="metric-sub">minutes per intersection</div>
            </div>
        </div>
        """)

    ## 3.6 Zone Chart #################################

    @render_widget
    def zone_chart():
        data = api_data.get()
        readings = filtered_readings()
        locations = data.get("locations", [])

        if not readings or not locations:
            fig = go.Figure()
            fig.update_layout(**PLOT_LAYOUT, height=300)
            fig.add_annotation(text="No data available", showarrow=False, font=dict(color="#64748b", size=14), xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        df = pd.DataFrame(readings)
        loc_df = pd.DataFrame(locations)

        # Join to get zone names
        merged = df.merge(loc_df[["id", "zone"]], left_on="location_id", right_on="id", how="left")
        zone_avg = (merged.groupby("zone")["congestion_level"]
                    .mean().reset_index()
                    .sort_values("congestion_level", ascending=True))

        colors = [ZONE_COLORS.get(z, "#3b82f6") for z in zone_avg["zone"]]

        fig = go.Figure(go.Bar(
            x=zone_avg["congestion_level"].round(1),
            y=zone_avg["zone"],
            orientation="h",
            marker=dict(color=colors, cornerradius=6),
            text=zone_avg["congestion_level"].round(1),
            textposition="auto",
            textfont=dict(color="#475569", size=13, family="Inter"),
        ))
        layout = {**PLOT_LAYOUT, "yaxis": dict(gridcolor="rgba(0,0,0,0)")}
        fig.update_layout(**layout, height=300)
        fig.update_xaxes(title_text="Avg Congestion Level", range=[0, 100])
        return fig

    ## 3.7 Heatmap (Hour × Day-of-Week) #################################

    @render_widget
    def hourly_chart():
        records = filtered_readings()

        if not records:
            fig = go.Figure()
            fig.update_layout(**PLOT_LAYOUT, height=300)
            fig.add_annotation(text="No data available", showarrow=False, font=dict(color="#64748b", size=14), xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        df["day_name"] = df["timestamp"].dt.day_name()

        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        pivot = (df.groupby(["day_name", "hour"])["congestion_level"]
                 .mean().reset_index()
                 .pivot(index="day_name", columns="hour", values="congestion_level")
                 .reindex(day_order)
                 .fillna(0))

        fig = go.Figure(go.Heatmap(
            z=pivot.values,
            x=[f"{h}:00" for h in pivot.columns],
            y=[d[:3] for d in pivot.index],
            colorscale=[[0, "#d1fae5"], [0.3, "#a7f3d0"], [0.5, "#fef08a"], [0.7, "#fcd34d"], [0.85, "#fdba74"], [1.0, "#fca5a5"]],
            zmin=0, zmax=100,
            hovertemplate="<b>%{y} %{x}</b><br>Avg Congestion: %{z:.1f}<extra></extra>",
            colorbar=dict(
                title=dict(text="Congestion", font=dict(size=11, color="#64748b")),
                tickvals=[0, 25, 50, 75, 100],
                ticktext=["0", "25", "50", "75", "100"],
                len=0.9,
                thickness=12,
                outlinewidth=0,
                tickfont=dict(color="#64748b", size=10),
            ),
        ))

        layout = {
            **PLOT_LAYOUT,
            "yaxis": dict(gridcolor="rgba(0,0,0,0)"),
            "xaxis": dict(side="top", tickfont=dict(size=10, color="#64748b"), dtick=3, gridcolor="rgba(0,0,0,0)"),
        }
        fig.update_layout(**layout, height=300)

        return fig

    ## 3.8 Interactive Congestion Map (deck.gl) #################################

    @render.ui
    def congestion_map():
        data = api_data.get()
        readings = filtered_readings()
        locations = data.get("locations", [])
        road_filter = input.road_type_filter()

        empty_msg = '<div style="height:620px;display:flex;align-items:center;justify-content:center;color:#64748b;font-family:Inter,sans-serif;">No data available</div>'

        if not readings or not locations:
            return ui.HTML(empty_msg)

        df = pd.DataFrame(readings)
        loc_df = pd.DataFrame(locations)
        hour_df = df

        # Average per location at the selected hour
        loc_hour = (hour_df.groupby("location_id")
                    .agg(congestion_level=("congestion_level", "mean"),
                         speed_mph=("speed_mph", "mean"),
                         volume=("volume", "mean"),
                         delay_minutes=("delay_minutes", "mean"))
                    .reset_index())

        merged = loc_hour.merge(loc_df, left_on="location_id", right_on="id", how="left")

        if road_filter != "All Roads":
            merged = merged[merged["road_type"] == road_filter.lower()]

        if merged.empty:
            return ui.HTML(empty_msg.replace("No data available", "No data for these filters"))

        merged["congestion_level"] = merged["congestion_level"].round(1)
        merged["speed_mph"] = merged["speed_mph"].round(1)
        merged["delay_minutes"] = merged["delay_minutes"].round(1)
        merged["volume"] = merged["volume"].round(0).astype(int)

        def severity_label(lvl):
            if lvl >= 80: return "Severe"
            elif lvl >= 60: return "High"
            elif lvl >= 30: return "Moderate"
            return "Low"

        merged["severity"] = merged["congestion_level"].apply(severity_label)

        # Pastel RGBA colors
        def congestion_rgba(lvl):
            if lvl >= 80: return [252, 165, 165, 230]
            elif lvl >= 60: return [252, 211, 77, 220]
            elif lvl >= 30: return [103, 232, 249, 200]
            return [110, 231, 183, 200]

        merged["radius"] = 80 + (merged["congestion_level"] / 100) * 320

        center_lat = float(merged["latitude"].mean())
        center_lon = float(merged["longitude"].mean())

        # Build JSON data for the deck.gl layer
        points = merged[["latitude", "longitude", "name", "zone", "road_type",
                         "congestion_level", "severity", "speed_mph",
                         "volume", "delay_minutes", "radius"]].to_dict(orient="records")
        for pt in points:
            pt["color"] = congestion_rgba(pt["congestion_level"])

        import html as html_mod
        map_data_json = json.dumps(points)

        # Standalone deck.gl HTML (loaded via srcdoc for full interactivity)
        raw_html = (
            '<!DOCTYPE html>'
            '<html><head><meta charset="utf-8">'
            '<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>'
            '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css">'
            '<script src="https://unpkg.com/deck.gl@9.1/dist.min.js"></script>'
            '<style>'
            'body{margin:0;overflow:hidden;background:#f8fafc;}'
            '#map{width:100%;height:100vh;}'
            '.deck-tooltip{'
            'font-family:Inter,-apple-system,sans-serif;'
            'background:#ffffff !important;'
            'color:#1e293b !important;'
            'border:1px solid #e2e8f0 !important;'
            'border-radius:12px !important;'
            'padding:14px 18px !important;'
            'box-shadow:0 8px 30px rgba(0,0,0,0.10) !important;'
            'max-width:300px;pointer-events:none;font-size:13px;line-height:1.5;'
            '}'
            '</style></head><body><div id="map"></div>'
            '<script>'
            'const data = ' + map_data_json + ';'
            'const tooltip = (info) => {'
            '  if (!info.object) return null;'
            '  const d = info.object;'
            '  return {'
            '    html: "<div style=\\"font-family:Inter,sans-serif;\\">"'
            '      + "<div style=\\"font-size:15px;font-weight:700;margin-bottom:3px;\\">" + d.name + "</div>"'
            '      + "<div style=\\"font-size:12px;color:#64748b;margin-bottom:10px;\\">" + d.zone + " · " + d.road_type + "</div>"'
            '      + "<div style=\\"display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12.5px;\\">"'
            '      + "<span style=\\"color:#64748b;\\">Congestion</span>"'
            '      + "<span style=\\"font-weight:600;\\">" + d.congestion_level + "/100 (" + d.severity + ")</span>"'
            '      + "<span style=\\"color:#64748b;\\">Speed</span><span>" + d.speed_mph + " mph</span>"'
            '      + "<span style=\\"color:#64748b;\\">Volume</span><span>" + d.volume + " vehicles</span>"'
            '      + "<span style=\\"color:#64748b;\\">Delay</span><span>" + d.delay_minutes + " min</span>"'
            '      + "</div></div>",'
            '    className: "deck-tooltip"'
            '  };'
            '};'
            'new deck.DeckGL({'
            '  container: "map",'
            '  mapStyle: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",'
            '  initialViewState: {'
            f'    latitude: {center_lat},'
            f'    longitude: {center_lon},'
            '    zoom: 12, pitch: 0, bearing: 0'
            '  },'
            '  controller: {scrollZoom:true, dragPan:true, dragRotate:true, doubleClickZoom:true, touchZoom:true, touchRotate:true, keyboard:true},'
            '  getTooltip: tooltip,'
            '  layers: ['
            '    new deck.ScatterplotLayer({'
            '      id: "congestion",'
            '      data: data,'
            '      getPosition: d => [d.longitude, d.latitude],'
            '      getRadius: d => d.radius,'
            '      getFillColor: d => d.color,'
            '      pickable: true,'
            '      autoHighlight: true,'
            '      highlightColor: [100, 100, 100, 50],'
            '      radiusMinPixels: 8,'
            '      radiusMaxPixels: 45,'
            '      opacity: 0.85,'
            '      stroked: true,'
            '      getLineColor: [148, 163, 184, 80],'
            '      lineWidthMinPixels: 1'
            '    })'
            '  ]'
            '});'
            '</script></body></html>'
        )

        escaped = html_mod.escape(raw_html, quote=True)
        return ui.HTML(
            f'<iframe srcdoc="{escaped}" '
            'style="width:100%;height:620px;border:none;border-radius:0 0 16px 16px;" '
            'sandbox="allow-scripts allow-same-origin" '
            '></iframe>'
        )

    ## 3.9 Timeline Chart #################################

    @render_widget
    def timeline_chart():
        data = api_data.get()
        readings = filtered_readings()
        locations = data.get("locations", [])
        h_min, h_max = input.hour_range()

        if not readings or not locations:
            fig = go.Figure()
            fig.update_layout(**PLOT_LAYOUT, height=320)
            fig.add_annotation(text="No data available", showarrow=False, font=dict(color="#64748b", size=14), xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        df = pd.DataFrame(readings)
        loc_df = pd.DataFrame(locations)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        merged = df.merge(loc_df[["id", "zone"]], left_on="location_id", right_on="id", how="left")

        # Average congestion by hour-of-day per zone
        agg = (merged.groupby(["hour", "zone"])["congestion_level"]
               .mean().reset_index()
               .sort_values("hour"))

        fig = go.Figure()
        for zone in sorted(agg["zone"].unique()):
            zdata = agg[agg["zone"] == zone]
            fig.add_trace(go.Scatter(
                x=zdata["hour"], y=zdata["congestion_level"].round(1),
                mode="lines+markers",
                name=zone,
                line=dict(color=ZONE_COLORS.get(zone, "#7c9cf5"), width=2.5, shape="spline"),
                marker=dict(size=5),
                hovertemplate=f"<b>{zone}</b><br>Hour: %{{x}}:00<br>Congestion: %{{y}}<extra></extra>",
            ))

        layout = {**PLOT_LAYOUT, "legend": dict(orientation="h", y=1.08, x=0.5, xanchor="center")}
        fig.update_layout(**layout, height=320)
        fig.update_xaxes(
            title_text="Hour of Day",
            range=[h_min - 0.3, h_max + 0.3],
            dtick=1,
            tickvals=list(range(h_min, h_max + 1)),
            ticktext=[f"{h}:00" for h in range(h_min, h_max + 1)],
        )
        fig.update_yaxes(title_text="Avg Congestion", range=[0, 100])
        return fig

    ## 3.9 AI Panel #################################

    @render.ui
    def ai_panel():
        summary = ai_summary.get()
        loading = ai_loading.get()

        if loading:
            content = '<div class="loading-shimmer">🤖 Analyzing congestion patterns with AI — this may take a moment...</div>'
        elif summary:
            # Convert basic markdown to HTML for display
            import re
            html = summary
            html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
            html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
            html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
            html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
            html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
            html = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
            html = re.sub(r'</ul>\s*<ul>', '', html)
            html = html.replace('\n\n', '</p><p>').replace('\n', '<br>')
            html = f'<p>{html}</p>'
            content = f'<div class="ai-body">{html}</div>'
        else:
            content = '<div class="ai-body" style="color:var(--text-secondary);">Click <strong>"Generate AI Summary"</strong> in the sidebar to get AI-powered congestion insights using Ollama.</div>'

        return ui.HTML(f"""
        <div class="ai-card">
            <div class="ai-header">
                <h3>✦ AI Insights</h3>
                <span class="ai-badge">Ollama</span>
            </div>
            {content}
        </div>
        """)


# 4. CREATE APP ###################################

app = App(app_ui, server)
