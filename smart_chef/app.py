# app.py
# Smart Chef – Shiny for Python app
# Pairs with 03_query_ai/process_diagram.md, 04_deployment/smart_chef

# Smart Chef: ingredients → recipes (USDA FoodData Central) → select recipe → AI recipe + report.
# Uses nutrition_query.py for USDA nutrition; Ollama for AI generation and fallback.

# 0. Setup #################################

## 0.1 Imports ############################

from logging import NullHandler
from pathlib import Path

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from ai_utils import generate_recipe_from_ingredients
from api_utils import fetch_recipes_for_ingredients, recipes_to_table_rows
from rating_utils import rate_recipe

## 0.2 Optional .env ############################

try:
    from dotenv import load_dotenv
    import os
    _env_path = Path(__file__).resolve().with_name(".env")
    load_dotenv(dotenv_path=_env_path)
    _ollama_key = os.getenv("OLLAMA_API_KEY") or ""
except Exception:
    _ollama_key = ""

# 1. UI #################################


def make_sidebar():
    """Sidebar: Find recipes and optional API key."""
    return ui.sidebar(
        ui.h5("Actions", class_="mt-2"),
        ui.p("Enter ingredients above, then click ", ui.strong("Find recipes"), ".", class_="text-muted small"),
        ui.input_action_button("run_query", "Find recipes", class_="btn-primary"),
        ui.input_password(
            "ollama_key",
            "Ollama API key (optional)",
            value=_ollama_key,
            placeholder="Leave blank to use .env",
        ),
        title="Smart Chef",
        open="desktop",
    )


def make_recipes_tab():
    """Recipes tab: nutrition table with Generate AI recipe button per row."""
    return ui.nav_panel(
        "Recipes & nutrition",
        ui.div(
            ui.div(
                ui.h4("Recipe nutrition table", class_="mt-0"),
                ui.p(
                    "Recipes from AI; nutrition from USDA FoodData Central. "
                    "Click ",
                    ui.strong("Generate Recipe"),
                    " on a recipe to see details.",
                    class_="text-muted small",
                ),
                ui.output_ui("result_summary"),
                class_="card card-body mb-3 bg-light",
            ),
            ui.output_ui("recipe_table"),
            class_="mt-3",
        ),
    )


def make_about_tab():
    """About tab: app description and data sources."""
    return ui.nav_panel(
        "About",
        ui.div(
            ui.h2("Smart Chef", class_="mb-3"),
            ui.p(
                "Smart Chef helps you discover recipes and nutrition information "
                "from ingredients you have on hand. Uses USDA FoodData Central "
                " for nutrition, and it uses Ollama AI to generate recipes."
            ),
            ui.h4("Data sources", class_="mt-4"),
            ui.tags.ul(
                ui.tags.li(
                    ui.a("USDA FoodData Central", href="https://fdc.nal.usda.gov/", target="_blank"),
                    " – nutrition facts only",
                ),
                ui.tags.li(
                    ui.a("Ollama Cloud", href="https://ollama.com/", target="_blank"),
                    " – AI recipe generation",
                ),
            ),
        ),
    )


# Ingredients input card
def make_ingredients_card():
    """Main ingredients text box and Find recipes button."""
    return ui.div(
        ui.div(
            ui.h4("What ingredients do you have?", class_="mt-0 mb-2"),
            ui.p(
                "Enter ingredients (comma- or semicolon-separated), then click ",
                ui.strong("Find recipes"),
                ".",
                class_="text-muted small mb-2",
            ),
            ui.input_text_area(
                "ingredients_main",
                "Ingredients",
                placeholder="e.g. chicken, rice, broccoli, olive oil, lemon",
                rows=4,
            ),
            ui.input_action_button("run_query_main", "Find recipes", class_="btn-primary mt-2"),
            class_="card card-body mb-4",
        ),
        id="ingredients_card",
    )


# Recipe detail page — side-by-side: recipe (left) + rating card (right)
def make_recipe_detail_ui():
    """Detail view: recipe on the left, rating card pinned to the right."""
    return ui.div(
        ui.input_action_button("back_to_table", "← Back to recipes", class_="btn btn-outline-secondary mb-3"),
        ui.div(
            # Left column: recipe content + download
            ui.div(
                ui.div(
                    ui.output_ui("ai_recipe_output"),
                    ui.output_ui("download_recipe_ui"),
                    class_="card card-body",
                ),
                class_="detail-recipe-col",
            ),
            # Right column: rating card (sticky)
            ui.div(
                ui.output_ui("rating_card_output"),
                class_="detail-rating-col",
            ),
            class_="detail-split-layout",
        ),
        id="recipe_detail_view",
    )


def _make_stars_html(score: float) -> ui.Tag:
    """Render filled / half / empty stars for a score out of 5."""
    full = int(score)
    half = 1 if (score - full) >= 0.3 else 0
    empty = 5 - full - half
    stars = "★" * full + ("½" if half else "") + "☆" * empty
    return ui.span(stars, class_="rating-stars")


def _score_color(score: float) -> str:
    """Return a CSS color class name for the given score."""
    if score >= 4.0:
        return "rating-green"
    if score >= 3.0:
        return "rating-yellow"
    return "rating-red"


def _make_bar(label: str, score: float) -> ui.Tag:
    """One category row: label, progress bar, score number."""
    pct = max(0, min(100, score / 5.0 * 100))
    color = _score_color(score)
    return ui.div(
        ui.div(
            ui.span(label, class_="rating-bar-label"),
            ui.div(
                ui.div(class_=f"rating-bar-fill {color}", style=f"width:{pct}%"),
                class_="rating-bar-track",
            ),
            ui.span(f"{score}", class_="rating-bar-score"),
            class_="rating-bar-row",
        ),
        class_="mb-2",
    )


def make_rating_card(rating: dict) -> ui.Tag:
    """Build the visual rating card from Agent 2's structured rating."""
    overall = rating.get("overall_score", 0)
    summary = rating.get("summary")
    categories = [
        ("Ease of Preparation", rating.get("ease_of_preparation", 0)),
        ("Completeness", rating.get("completeness", 0)),
        ("Nutritional Balance", rating.get("nutritional_balance", 0)),
    ]

    summary_section = (
        ui.div(
            ui.hr(class_="rating-divider"),
            ui.p(summary, class_="rating-summary-text"),
            class_="rating-summary",
        )
        if summary
        else ui.span()
    )

    return ui.div(
        ui.h5("Recipe Rating", class_="rating-card-title"),
        ui.div(
            ui.div(
                ui.div(f"{overall}", class_="rating-overall-number"),
                _make_stars_html(overall),
                ui.div("Overall Score", class_="rating-overall-label"),
                class_="rating-overall-section",
            ),
            ui.div(
                *[_make_bar(label, score) for label, score in categories],
                class_="rating-categories-section",
            ),
            class_="rating-card-body",
        ),
        summary_section,
        class_="card card-body rating-card",
    )


# Full page layout
app_ui = ui.page_fluid(
    ui.include_css("styles.css"),
    ui.tags.head(
        ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
        ui.tags.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap",
        ),
    ),
    make_sidebar(),
    ui.div(
        ui.output_ui("ingredients_section"),
        ui.output_ui("main_content"),
        id="main_container",
    ),
    title="Smart Chef",
)

# 2. Server #################################


def server(input: Inputs, output: Outputs, session: Session) -> None:
    recipes_result = reactive.value(None)
    selected_recipe = reactive.value(None)  # When set, show detail view
    ai_recipe_result = reactive.value(None)
    rating_result = reactive.value(None)    # Agent 2 rating

    def _get_ingredients_text() -> str:
        return (input.ingredients_main() or "").strip()

    def _parse_ingredients() -> list[str]:
        text = _get_ingredients_text()
        raw = text.replace(";", ",").split(",")
        return [s.strip() for s in raw if s.strip()]

    @reactive.Effect
    @reactive.event(input.run_query, input.run_query_main)
    def _run_query():
        selected_recipe.set(None)  # Reset detail view when new search
        api_key = (input.ollama_key() or "").strip() or None
        recipes, err, source = fetch_recipes_for_ingredients(
            _get_ingredients_text(),
            max_results_per_search=15,
            ollama_api_key=api_key,
            fdc_api_key=None,  # Uses FDC_API_KEY from .env
        )
        recipes_result.set({"recipes": recipes, "error": err, "source": source})

    @reactive.Effect
    @reactive.event(input.back_to_table)
    def _back():
        selected_recipe.set(None)

    @reactive.Effect
    def _on_recipe_generate():
        rec = recipes_result.get()
        if not rec or rec.get("error"):
            return
        rlist = rec.get("recipes", [])
        for i in range(len(rlist)):
            btn = getattr(input, f"recipe_btn_{i}", None)
            if btn is not None:
                n = btn()  # Create reactive dependency
                if n is not None and n > 0:
                    recipe = rlist[i]
                    selected_recipe.set(recipe)
                    rating_result.set(None)  # Reset while generating
                    ingredients = _parse_ingredients()
                    api_key = (input.ollama_key() or "").strip() or None

                    print("\n" + "=" * 60)
                    print("🍳 MULTI-AGENT WORKFLOW STARTED")
                    print(f"   Selected recipe: {recipe.get('recipe_name', '?')}")
                    print(f"   Ingredients: {', '.join(ingredients)}")
                    print("=" * 60)

                    print("\n🤖 AGENT 1: Recipe Chef — Generating full recipe...")
                    text, err = generate_recipe_from_ingredients(
                        ingredients,
                        ollama_api_key=api_key,
                        recipe_name=recipe.get("recipe_name"),
                        recipe_description=recipe.get("recipe_description"),
                    )
                    ai_recipe_result.set({"text": text, "error": err})

                    if text and not err:
                        print(f"   ✅ Agent 1 complete — recipe generated ({len(text)} chars)")
                        print("\n🤖 AGENT 2: Recipe Critic — Rating the recipe...")
                        rating, rating_err = rate_recipe(
                            recipe_text=text,
                            user_ingredients=ingredients,
                            recipe_name=recipe.get("recipe_name", ""),
                            ollama_api_key=api_key,
                        )
                        rating_result.set({"rating": rating, "error": rating_err})
                        if rating and not rating_err:
                            print(f"   ✅ Agent 2 complete — Overall score: {rating.get('overall_score', '?')}/5.0")
                        else:
                            print(f"   ⚠️ Agent 2 error: {rating_err}")
                        print("\n" + "=" * 60)
                        print("🍳 MULTI-AGENT WORKFLOW COMPLETE")
                        print("=" * 60 + "\n")
                    else:
                        print(f"   ❌ Agent 1 failed: {err}")
                    return

    @render.ui
    def ingredients_section():
        """Show ingredients card on table view; hide when viewing recipe detail (inputs stay in DOM)."""
        card = make_ingredients_card()
        if selected_recipe.get() is not None:
            return ui.div(card, class_="d-none")
        return card

    @render.ui
    def main_content():
        """Show table view or detail view based on selection."""
        if selected_recipe.get() is not None:
            return make_recipe_detail_ui()
        return ui.navset_card_underline(
            make_recipes_tab(),
            make_about_tab(),
            title="Smart Chef",
            id="main_tabs",
        )

    @render.ui
    def result_summary():
        out = recipes_result.get()
        if out is None:
            return ui.p("Click ", ui.strong("Find recipes"), " to search.", class_="text-muted mb-0")
        err = out.get("error")
        if err:
            return ui.p("No results.", class_="text-muted mb-0")
        recipes = out.get("recipes", [])
        n = len(recipes)
        msg = f"Found {n} recipe(s). Nutrition from USDA."
        return ui.div(
            ui.div(
                ui.p(msg, " Click ", ui.strong("Generate Recipe"), " on a recipe to see details."),
                class_="alert alert-success mb-0",
                role="status",
            )
        )

    @render.ui
    def recipe_table():
        """Table of recipes with Generate AI recipe button per row."""
        out = recipes_result.get()
        if out is None:
            return ui.div(ui.p("Run ", ui.strong("Find recipes"), " to see results.", class_="text-muted"), class_="card card-body")
        if out.get("error"):
            return ui.div(
                ui.div(out.get("error"), class_="alert alert-danger mb-0", role="alert"),
                class_="card card-body",
            )
        recipes = out.get("recipes", [])
        if not recipes:
            return ui.div(ui.p("No recipes found.", class_="text-muted"), class_="card card-body")

        # Build table with header
        header = ui.tags.thead(
            ui.tags.tr(
                ui.tags.th("Recipe"),
                ui.tags.th("Calories"),
                ui.tags.th("Protein (g)"),
                ui.tags.th("Carbs (g)"),
                ui.tags.th("Fat (g)"),
                ui.tags.th("Description"),
                ui.tags.th("Action"),
            )
        )
        rows_data = recipes_to_table_rows(recipes)
        body_rows = []
        for i, r in enumerate(rows_data):
            body_rows.append(
                ui.tags.tr(
                    ui.tags.td(r.get("Recipe", "—")),
                    ui.tags.td(r.get("Calories", "—")),
                    ui.tags.td(r.get("Protein (g)", "—")),
                    ui.tags.td(r.get("Carbs (g)", "—")),
                    ui.tags.td(r.get("Fat (g)", "—")),
                    ui.tags.td(r.get("Description", "")[:60] + ("..." if len(r.get("Description", "")) > 60 else "")),
                    ui.tags.td(
                        ui.input_action_button(f"recipe_btn_{i}", "Generate Recipe", class_="btn btn-sm btn-primary")
                    ),
                )
            )
        body = ui.tags.tbody(*body_rows)
        return ui.div(
            ui.tags.table(
                header,
                body,
                class_="table table-striped table-hover",
            ),
            class_="table-responsive",
        )

    @render.ui
    def ai_recipe_output():
        out = ai_recipe_result.get()
        if out is None:
            return ui.p("Generating...", class_="text-muted")
        err = out.get("error")
        if err:
            return ui.div(ui.div(err, class_="alert alert-warning", role="alert"))
        text = out.get("text")
        if not text:
            return ui.p("No recipe generated.", class_="text-muted")
        return ui.div(ui.markdown(text), class_="markdown-recipe")

    @render.download(filename="recipe.md")
    def download_recipe():
        out = ai_recipe_result.get()
        text = (out or {}).get("text") or ""
        yield text

    @render.ui
    def download_recipe_ui():
        out = ai_recipe_result.get()
        if not out or out.get("error") or not out.get("text"):
            return None
        return ui.download_button(
            "download_recipe",
            "Download Recipe",
            class_="btn btn-outline-primary mt-2",
        )

    @render.ui
    def rating_card_output():
        """Render Agent 2's rating card below the recipe."""
        out = rating_result.get()
        if out is None:
            recipe_out = ai_recipe_result.get()
            if recipe_out and recipe_out.get("text") and not recipe_out.get("error"):
                return ui.div(
                    ui.p("Rating recipe...", class_="text-muted"),
                    class_="card card-body mt-3",
                )
            return None
        err = out.get("error")
        if err:
            return ui.div(
                ui.div(f"Rating unavailable: {err}", class_="alert alert-warning mb-0"),
                class_="mt-3",
            )
        rating = out.get("rating")
        if not rating:
            return None
        return make_rating_card(rating)


# 3. App #################################

app = App(app_ui, server)
