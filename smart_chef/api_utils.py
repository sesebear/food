# api_utils.py
# Smart Chef – API and data helpers for Shiny app
# Pairs with 04_deployment/smart_chef (Smart Chef Shiny app)
#
# AI (Ollama) generates recipes. USDA FoodData Central provides nutrition only.

from nutrition_query import estimate_recipe_nutrition_from_ingredients

# Inappropriate or poisonous ingredients – no recipes generated, user notified
_INAPPROPRIATE_TERMS = frozenset({
    "paper", "plastic", "metal", "wood", "rocks", "glass", "dirt", "sand",
    "bleach", "poison", "posion", "chemicals", "soap", "glue", "paint", "gasoline",
    "detergent", "ammonia", "lighter fluid", "antifreeze", "rat poison",
    "cyanide", "arsenic", "lead", "mercury", "pesticide", "herbicide",
})


def _validate_ingredients(ingredients: list[str]) -> tuple[list[str] | None, str | None]:
    """
    Check for inappropriate or poisonous ingredients.
    Returns (inappropriate_list, error_message) if any found, else (None, None).
    Uses whole-word matching to avoid blocking valid foods (e.g. bleached flour).
    """
    found = []
    for ing in ingredients:
        lower = ing.lower().strip()
        if not lower:
            continue
        words = set(lower.split())
        if lower in _INAPPROPRIATE_TERMS:
            found.append(ing)
        elif any(term in words for term in _INAPPROPRIATE_TERMS):
            found.append(ing)
    if found:
        unique = list(dict.fromkeys(found))
        msg = (
            "No recipes can be generated. One or more ingredients are inappropriate or dangerous: "
            f"{', '.join(unique)}. Please enter only safe, edible food ingredients."
        )
        return unique, msg
    return None, None


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
    Get recipes using AI (Ollama); nutrition facts from USDA only.

    AI generates recipe ideas. USDA FoodData Central provides nutrition
    (calories, protein, carbs, fat) for each recipe.

    Returns
    -------
    tuple[list[dict], str | None, str]
        (recipes, error_message, source). source is always "ollama".
    """
    if not ingredients_text or not ingredients_text.strip():
        return [], "Please enter at least one ingredient.", ""

    raw = ingredients_text.replace(";", ",").split(",")
    ingredients = [s.strip() for s in raw if s.strip()]
    if not ingredients:
        return [], "Please enter at least one ingredient.", ""

    # Block inappropriate or poisonous ingredients – no recipes, notify user
    bad, err = _validate_ingredients(ingredients)
    if bad is not None:
        return [], err, ""

    # AI generates recipes; USDA provides nutrition only
    gen = _get_ollama_recipes()
    recipes, err = gen(
        ingredients,
        ollama_api_key=ollama_api_key,
        max_recipes=min(max_results_per_search, 10),
    )
    if err:
        return [], err, ""
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
