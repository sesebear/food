# app.py
# FDA Food Adverse Event Shiny App – main application
# Pairs with LAB_cursor_shiny_app.md, implements 01_query_api/my_good_query.py
# Tim Fraser

# Shiny for Python app that runs the openFDA Food Event API query on user request.
# Includes Query tab (inputs, Run Query, results) and About tab per Shiny best practices.

# 0. Setup #################################

## 0.1 Imports ############################

from pathlib import Path

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from api_utils import fetch_fda_events

## 0.2 Optional .env for API key ############################

# Load API key from .env in app directory if present (optional; higher rate limit with key).
try:
    from dotenv import load_dotenv
    import os
    _env_path = Path(__file__).resolve().with_name(".env.example")
    load_dotenv(dotenv_path=_env_path)
    _api_key_default = os.getenv("API_KEY") or ""
except Exception:
    _api_key_default = ""

# 1. UI #################################

# Sidebar: query parameters and Run Query button.
def make_sidebar():
    return ui.sidebar(
        ui.input_text(
            "industry",
            "Industry name",
            value="Cosmetics",
            placeholder="e.g. Cosmetics, Dietary Supplements",
        ),
        ui.input_numeric(
            "limit",
            "Max records (1–1000)",
            value=20,
            min=1,
            max=1000,
        ),
        ui.input_select(
            "sort",
            "Sort by date",
            choices={
                "date_created:desc": "Newest first",
                "date_created:asc": "Oldest first",
            },
            selected="date_created:desc",
        ),
        ui.input_password(
            "api_key",
            "API key (optional)",
            value=_api_key_default,
            placeholder="Leave blank to use .env or no key",
        ),
        ui.input_action_button("run_query", "Run query", class_="btn-primary"),
        title="Query parameters",
        open="desktop",
    )


# Query tab: run button, filters, summary, table.
def make_query_tab():
    return ui.nav_panel(
        "Query",
        ui.div(
            # Prominent run area: same action as sidebar button.
            ui.div(
                ui.h4("Run API query", class_="mt-0"),
                ui.p(
                    "Set parameters in the sidebar (industry, limit, sort), then click below to fetch data from the openFDA API.",
                    class_="text-muted small",
                ),
                ui.input_action_button("run_query_main", "Run query", class_="btn-primary btn-lg"),
                class_="card card-body mb-3 bg-light",
            ),
            ui.output_ui("result_summary"),
            # Filters: only meaningful after data is loaded (handled in server).
            ui.div(
                ui.h5("Filter results", class_="mt-3 mb-2"),
                ui.div(
                    ui.input_text(
                        "filter_text",
                        "Search in outcomes, reactions, products",
                        placeholder="e.g. NAUSEA, Rash, Visited",
                    ),
                    ui.input_text(
                        "filter_date",
                        "Filter by date (YYYYMMDD or partial, e.g. 2024)",
                        placeholder="e.g. 2024 or 202401",
                    ),
                    class_="row",
                ),
                class_="mb-2",
                id="filter_panel",
            ),
            ui.output_ui("filter_summary"),
            ui.output_data_frame("result_table"),
            class_="mt-3",
        ),
    )


# About tab: app description and data source (per Shiny documentation pattern).
def make_about_tab():
    return ui.nav_panel(
        "About",
        ui.div(
            ui.h2("FDA Food Adverse Event Explorer", class_="mb-3"),
            ui.p(
                "This app runs a query against the openFDA Food Adverse Event Reports API "
                "and displays results in a table. Use the sidebar to set the industry name, "
                "record limit, and sort order, then click **Run query** to fetch data."
            ),
            ui.h4("Data source", class_="mt-4"),
            ui.p(
                ui.a(
                    "openFDA Food Event API",
                    href="https://open.fda.gov/apis/food/event/",
                    target="_blank",
                ),
                " – public data on adverse event reports related to FDA-regulated foods."
            ),
            ui.h4("Parameters", class_="mt-4"),
            ui.tags.ul(
                ui.tags.li("Industry name: filters by product industry (e.g. Cosmetics)."),
                ui.tags.li("Max records: number of events to return (1–1000)."),
                ui.tags.li("Sort: by report date (newest or oldest first)."),
                ui.tags.li("API key: optional; increases rate limit if set in .env or here."),
            ),
            ui.p(
                "Built for the DSAI productivity lab. Implements ",
                ui.code("my_good_query.py"),
                " from the Query API lab.",
                class_="mt-3 text-muted small",
            ),
        ),
    )


# Full page: sidebar + navset (Query, About).
app_ui = ui.page_fluid(
    make_sidebar(),
    ui.navset_card_underline(
        make_query_tab(),
        make_about_tab(),
        title="FDA Food Adverse Events",
        id="main_tabs",
    ),
    title="FDA Food Event Explorer",
)

# 2. Server #################################


def server(input: Inputs, output: Outputs, session: Session) -> None:
    # Hold last fetch result; set when either Run query button is clicked.
    query_result = reactive.value(None)

    @reactive.Effect
    @reactive.event(input.run_query, input.run_query_main)
    def _run_query():
        # Run on either sidebar or main Run query button.
        data, err = fetch_fda_events(
            search=input.industry(),
            sort=input.sort(),
            limit=int(input.limit()) if input.limit() is not None else 20,
            api_key=input.api_key() or None,
        )
        query_result.set({"data": data, "error": err})

    @render.ui
    def result_summary():
        out = query_result.get()
        if out is None:
            return ui.div(
                ui.p("Click **Run query** to fetch adverse event reports.", class_="text-muted"),
            )
        err = out.get("error")
        if err:
            return ui.div(
                ui.div(err, class_="alert alert-danger", role="alert"),
            )
        data = out.get("data")
        if not data:
            return None
        meta = data.get("meta", {})
        results_info = meta.get("results", {})
        total = results_info.get("total", "?")
        results_list = data.get("results", [])
        n = len(results_list)
        return ui.div(
            ui.div(
                f"Total matching (API): {total}  ·  Returned: {n}",
                class_="alert alert-success mb-0",
                role="status",
            ),
        )

    def _events_to_data_frame(results_list: list) -> pd.DataFrame:
        """Build a DataFrame from API results for display."""
        rows = []
        for event in results_list:
            report_number = event.get("report_number", "N/A")
            date_created = event.get("date_created", "N/A")
            outcomes = event.get("outcomes", [])[:2]
            outcomes_str = ", ".join(outcomes) if outcomes else "—"
            reactions = event.get("reactions", [])[:3]
            reactions_str = ", ".join(reactions) if reactions else "—"
            products = event.get("products", [])
            product_names = [p.get("name_brand", "?") for p in products[:2]]
            products_str = ", ".join(product_names) if product_names else "—"
            rows.append({
                "Report #": report_number,
                "Date": date_created,
                "Outcomes": outcomes_str,
                "Reactions": reactions_str,
                "Products": products_str,
            })
        return pd.DataFrame(rows)

    @reactive.Calc
    def _filtered_df():
        """Full results as DataFrame, with optional text and date filters applied."""
        out = query_result.get()
        if out is None or out.get("error") or not out.get("data"):
            return None
        results_list = out["data"].get("results", [])
        if not results_list:
            return pd.DataFrame()
        df = _events_to_data_frame(results_list)
        text_val = (input.filter_text() or "").strip()
        date_val = (input.filter_date() or "").strip()
        if text_val:
            # Keep rows where search text appears in Outcomes, Reactions, or Products.
            mask = (
                df["Outcomes"].str.contains(text_val, case=False, na=False)
                | df["Reactions"].str.contains(text_val, case=False, na=False)
                | df["Products"].str.contains(text_val, case=False, na=False)
            )
            df = df.loc[mask]
        if date_val:
            # Keep rows where Date contains the date filter (e.g. 2024 or 202401).
            df = df[df["Date"].astype(str).str.contains(date_val, na=False)]
        return df

    @render.ui
    def filter_summary():
        df = _filtered_df()
        if df is None:
            return None
        if len(df) == 0 and query_result.get() and query_result.get().get("data"):
            return ui.div(
                ui.p("No rows match the current filters. Try loosening the search or date.", class_="text-warning"),
            )
        out = query_result.get()
        if not out or not out.get("data"):
            return None
        total = len(out["data"].get("results", []))
        shown = len(df)
        if shown == total and not (input.filter_text() or "").strip() and not (input.filter_date() or "").strip():
            return None
        return ui.div(
            ui.p(f"Showing {shown} of {total} records.", class_="text-muted small mb-1"),
        )

    @render.data_frame
    def result_table():
        df = _filtered_df()
        if df is None:
            return render.DataGrid(pd.DataFrame(), height="200px")
        if df.empty:
            return render.DataGrid(pd.DataFrame(), height="200px")
        return render.DataGrid(df, height="400px")


# 3. App #################################

app = App(app_ui, server)
