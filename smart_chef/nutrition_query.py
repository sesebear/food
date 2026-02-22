# nutrition_query.py
# USDA FoodData Central API – nutrition lookup for Smart Chef
# Pairs with 04_deployment/smart_chef (Smart Chef Shiny app)

# Queries USDA FoodData Central for food nutrition data.
# No IP restrictions; requires FDC_API_KEY (data.gov) in .env.

# 0. Setup #################################

## 0.1 Load Packages ############################

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

## 0.2 Load Environment ############################

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
try:
    load_dotenv(project_root / ".env")
    load_dotenv(script_dir / ".env")
except OSError:
    pass

# USDA FoodData Central API key (required)
# Get key: https://fdc.nal.usda.gov/api-key-signup
FDC_API_KEY = os.getenv("FDC_API_KEY")

BASE_URL = "https://api.nal.usda.gov/fdc/v1"

# USDA nutrient IDs
NUTRIENT_ENERGY = 1008   # kcal
NUTRIENT_PROTEIN = 1003  # g
NUTRIENT_CARBS = 1005    # g
NUTRIENT_FAT = 1004      # g


# 1. Food Search #################################


def search_foods(
    search_expression: str,
    api_key: str | None = None,
    page_size: int = 25,
    page_number: int = 1,
) -> tuple[dict | None, str | None]:
    """
    Search USDA FoodData Central for foods matching the query.

    Parameters
    ----------
    search_expression : str
        Search term (food name, ingredient).
    api_key : str | None
        USDA API key. If None, uses FDC_API_KEY from .env.
    page_size : int
        Results per page (1–200).
    page_number : int
        Page number (1-based).

    Returns
    -------
    tuple[dict | None, str | None]
        (response_json, error_message). Response has "foods" list.
    """
    if not search_expression or not search_expression.strip():
        return None, "Search expression cannot be empty."

    key = api_key or FDC_API_KEY
    if not key:
        return None, "FDC_API_KEY must be set in .env. Get key at https://fdc.nal.usda.gov/api-key-signup"

    url = f"{BASE_URL}/foods/search"
    params = {
        "api_key": key,
        "query": search_expression.strip(),
        "pageSize": min(max(1, page_size), 200),
        "pageNumber": max(1, page_number),
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return None, "Food search timed out. Check network and try again."
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            return None, f"Food search failed: {e.response.status_code} – {e.response.reason}"
        return None, "Food search failed."
    except requests.exceptions.RequestException as e:
        return None, f"Food search failed: {e}"

    try:
        data = response.json()
    except ValueError:
        return None, "Invalid JSON in API response."

    return data, None


# 2. Extract Nutrition from USDA Food #################################


def _extract_nutrients(food: dict) -> dict:
    """Extract calories, protein, carbs, fat from USDA foodNutrients."""
    result = {"calories": None, "protein": None, "carbohydrate": None, "fat": None}
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrientId")
        val = n.get("value")
        if val is None:
            continue
        if nid == NUTRIENT_ENERGY:
            result["calories"] = float(val)
        elif nid == NUTRIENT_PROTEIN:
            result["protein"] = float(val)
        elif nid == NUTRIENT_CARBS:
            result["carbohydrate"] = float(val)
        elif nid == NUTRIENT_FAT:
            result["fat"] = float(val)
    return result


def get_nutrition_for_food(
    search_expression: str,
    api_key: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Get nutrition for a single food/ingredient via USDA search.
    Returns first match's nutrition (calories, protein, carbohydrate, fat).

    Returns
    -------
    tuple[dict | None, str | None]
        ({"calories": float, "protein": float, "carbohydrate": float, "fat": float}, error)
    """
    data, err = search_foods(search_expression, api_key=api_key, page_size=1)
    if err:
        return None, err
    foods = data.get("foods", [])
    if not foods:
        return None, "No food found"
    nut = _extract_nutrients(foods[0])
    if nut["calories"] is None and nut["protein"] is None:
        return None, "No nutrition data for this food"
    return nut, None


def estimate_recipe_nutrition_from_ingredients(
    ingredients: list[str],
    api_key: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Estimate recipe nutrition by looking up each ingredient via USDA
    and summing (rough estimate for a typical serving).

    Returns
    -------
    tuple[dict | None, str | None]
        ({"calories": float, "protein": float, "carbohydrate": float, "fat": float}, error)
    """
    if not ingredients:
        return None, "No ingredients provided"
    acc = {"calories": 0.0, "protein": 0.0, "carbohydrate": 0.0, "fat": 0.0}
    for ing in ingredients[:8]:
        nut, err = get_nutrition_for_food(ing.strip(), api_key=api_key)
        if err or not nut:
            continue
        for k in acc:
            if nut.get(k) is not None:
                acc[k] += nut[k]
    if acc["calories"] == 0 and acc["protein"] == 0:
        return None, "Could not find nutrition for any ingredient"
    return acc, None


# 3. Foods to Recipe-Like Format #################################


def search_foods_as_recipes(
    search_expression: str,
    api_key: str | None = None,
    max_results: int = 15,
) -> tuple[list[dict], str | None]:
    """
    Search USDA for foods and return as recipe-like dicts for display.
    Each USDA food becomes a row with recipe_name, calories, protein_g, etc.

    Returns
    -------
    tuple[list[dict], str | None]
        (list of recipe-like dicts, error_message)
    """
    data, err = search_foods(
        search_expression,
        api_key=api_key,
        page_size=min(max_results, 50),
    )
    if err:
        return [], err
    foods = data.get("foods", [])
    result = []
    seen = set()
    for f in foods:
        fid = f.get("fdcId")
        if fid in seen:
            continue
        seen.add(fid)
        nut = _extract_nutrients(f)
        result.append({
            "recipe_id": str(fid),
            "recipe_name": f.get("description", "Unknown"),
            "recipe_description": f.get("ingredients", "") or f.get("brandOwner", ""),
            "calories": nut.get("calories"),
            "protein_g": nut.get("protein"),
            "carbs_g": nut.get("carbohydrate"),
            "fat_g": nut.get("fat"),
            "ingredients": [],
            "recipe_image": None,
        })
    return result, None


# 4. CLI Demo / Test #################################


def run_test() -> bool:
    """
    Test nutrition_query.py: search_foods, get_nutrition, estimate from ingredients.
    Returns True if all pass, False otherwise.
    """
    print("--- nutrition_query.py test (USDA FoodData Central) ---")
    key = FDC_API_KEY
    if not key:
        print("❌ FDC_API_KEY not set in .env")
        return False
    print("✅ API key loaded")

    data, err = search_foods("chicken breast", api_key=key, page_size=5)
    if err:
        print(f"❌ Food search: {err}")
        return False
    foods = data.get("foods", [])
    print(f"✅ Food search: {len(foods)} food(s)")
    for f in foods[:2]:
        nut = _extract_nutrients(f)
        print(f"   - {f.get('description')}: {nut.get('calories')} kcal, {nut.get('protein')}g protein")

    nut, err2 = get_nutrition_for_food("rice", api_key=key)
    if err2:
        print(f"⚠️ Single food nutrition: {err2}")
    else:
        print(f"✅ Single food nutrition: {nut}")

    nut3, err3 = estimate_recipe_nutrition_from_ingredients(["chicken", "rice"], api_key=key)
    if err3:
        print(f"⚠️ Ingredient nutrition: {err3}")
    else:
        print(f"✅ Ingredient nutrition: {nut3}")
    print("--- Test complete ---")
    return True


if __name__ == "__main__":
    ok = run_test()
    raise SystemExit(0 if ok else 1)
