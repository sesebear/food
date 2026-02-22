# api_utils.py
# Smart Chef – API and data helpers for Shiny app
# Pairs with 04_deployment/smart_chef (Smart Chef Shiny app)
#
# Uses nutrition_query.py (USDA FoodData Central) for food nutrition.
# Uses Ollama AI for recipe ideas when USDA returns no foods, and to enrich.
# Both API and AI: USDA for nutrition, Ollama for recipe ideas and fallback.

from nutrition_query import (
    search_foods_as_recipes,
    estimate_recipe_nutrition_from_ingredients,
)

# Lazy import to avoid circular dependency
def _get_ollama_recipes():
    from ai_utils import generate_recipes_with_nutrition
    return generate_recipes_with_nutrition


def _enrich_recipe_with_usda_nutrition(
    recipe: dict,
    api_key: str | None,
) -> dict:
    """
    Try to get nutrition from USDA for a recipe (e.g. from Ollama).
    Uses estimate_recipe_nutrition_from_ingredients.
    Returns recipe with updated calories, protein_g, carbs_g, fat_g if found.
    """
    ingredients = recipe.get("ingredients", [])
    name = recipe.get("recipe_name", "")
    ing_list = ingredients if ingredients else [name]
    nut, err = estimate_recipe_nutrition_from_ingredients(ing_list, api_key=api_key)
    if not err and nut:
        recipe["calories"] = nut.get("calories")
        recipe["protein_g"] = nut.get("protein")
        recipe["carbs_g"] = nut.get("carbohydrate")
        recipe["fat_g"] = nut.get("fat")
        recipe["_nutrition_source"] = "usda"
    return recipe


def fetch_recipes_for_ingredients(
    ingredients_text: str,
    max_results_per_search: int = 15,
    ollama_api_key: str | None = None,
    fdc_api_key: str | None = None,
) -> tuple[list[dict], str | None, str]:
    """
    Get recipes/foods with nutrition using USDA FoodData Central and Ollama.

    Tries USDA first for food matches. Falls back to Ollama for recipe ideas,
    then enriches with USDA nutrition when API key is available.

    Parameters
    ----------
    ingredients_text : str
        Comma- or semicolon-separated list of ingredients.
    max_results_per_search : int
        Max items per search.
    ollama_api_key : str | None
        Ollama API key for recipe ideas when USDA has no foods.
    fdc_api_key : str | None
        USDA API key. If None, uses FDC_API_KEY from .env.

    Returns
    -------
    tuple[list[dict], str | None, str]
        (recipes, error_message, source). source is "usda" or "ollama".
    """
    if not ingredients_text or not ingredients_text.strip():
        return [], "Please enter at least one ingredient.", ""

    raw = ingredients_text.replace(";", ",").split(",")
    ingredients = [s.strip() for s in raw if s.strip()]
    if not ingredients:
        return [], "Please enter at least one ingredient.", ""

    # Try USDA first (nutrition_query.py)
    combined = " ".join(ingredients[:5])
    foods, err = search_foods_as_recipes(
        combined,
        api_key=fdc_api_key,
        max_results=max_results_per_search,
    )
    if not err and foods:
        return foods, None, "usda"

    # Try individual ingredient searches for more coverage
    if not err:
        seen_ids = set()
        all_foods = list(foods)
        for f in all_foods:
            rid = f.get("recipe_id")
            if rid:
                seen_ids.add(rid)
        for ing in ingredients[:3]:
            if len(all_foods) >= max_results_per_search * 2:
                break
            more, err2 = search_foods_as_recipes(ing, api_key=fdc_api_key, max_results=10)
            if not err2:
                for f in more:
                    rid = f.get("recipe_id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        all_foods.append(f)
        if all_foods:
            return all_foods, None, "usda"

    # Fall back to Ollama for recipe ideas, enrich with USDA nutrition
    return _ollama_fallback(
        ingredients,
        ollama_api_key,
        err or "No foods found for these ingredients.",
        fdc_api_key=fdc_api_key,
    )


def _ollama_fallback(
    ingredients: list[str],
    ollama_api_key: str | None,
    usda_error: str,
    fdc_api_key: str | None = None,
) -> tuple[list[dict], str | None, str]:
    """
    Fall back to Ollama for recipe ideas when USDA has no foods.
    Enrich each recipe with USDA nutrition when API key is available.
    """
    gen = _get_ollama_recipes()
    recipes, err = gen(ingredients, ollama_api_key=ollama_api_key, max_recipes=8)
    if err:
        return [], f"USDA had no foods ({usda_error}). Ollama fallback: {err}", ""
    for r in recipes:
        _enrich_recipe_with_usda_nutrition(r, fdc_api_key)
    return recipes, None, "ollama"


def _truncate(s: str | None, max_len: int) -> str:
    """Truncate string to max_len, appending '...' if longer."""
    if not s:
        return ""
    return s[:max_len] + ("..." if len(s) > max_len else "")


def recipes_to_table_rows(recipes: list[dict]) -> list[dict]:
    """
    Convert recipe list to table rows for DataGrid display.

    Returns list of dicts with keys: Recipe, Calories, Protein (g), Carbs (g), Fat (g), Description.
    """
    rows = []
    for r in recipes:
        rows.append({
            "Recipe": r.get("recipe_name", "—"),
            "Calories": r.get("calories") if r.get("calories") is not None else "—",
            "Protein (g)": r.get("protein_g") if r.get("protein_g") is not None else "—",
            "Carbs (g)": r.get("carbs_g") if r.get("carbs_g") is not None else "—",
            "Fat (g)": r.get("fat_g") if r.get("fat_g") is not None else "—",
            "Description": _truncate(r.get("recipe_description"), 80),
        })
    return rows
