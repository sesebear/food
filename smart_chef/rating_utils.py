# rating_utils.py
# Smart Chef – Agent 2: Recipe Critic
# Multi-agent rating system with RAG and function calling
# Pairs with app.py (Smart Chef Shiny app)

# Agent 2 receives a generated recipe from Agent 1, rates it on three dimensions
# (Ease of Preparation, Completeness, Nutritional Balance), and returns a
# structured JSON rating displayed as a visual card.
#
# RAG: Searches data/food_data.json (USDA Foundation Foods) for nutritional
#      guidelines used to evaluate the Nutritional Balance category.
# Function Calling: Uses nutrition_query.py to look up real USDA nutrition data
#      for the recipe's ingredients.

# 0. Setup #################################

## 0.1 Imports ############################

import json
import os
import re
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

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_CHAT_URL = "https://ollama.com/api/chat"

# 1. RAG – Nutrition Knowledge Base #################################

# Load the USDA Foundation Foods data once at import time.
# This serves as our embedded knowledge base for nutritional guidelines.
_FOOD_DATA_PATH = script_dir / "data" / "food_data.json"
_FOOD_DB: list[dict] = []

# Nutrient IDs we care about for rating
_NUTRIENT_MAP = {
    1008: "calories",
    1003: "protein",
    1005: "carbohydrate",
    1004: "fat",
    1079: "fiber",
}


def _load_food_db() -> list[dict]:
    """Load and index the USDA Foundation Foods for keyword search."""
    global _FOOD_DB
    if _FOOD_DB:
        return _FOOD_DB
    if not _FOOD_DATA_PATH.exists():
        return []
    with open(_FOOD_DATA_PATH, "r") as f:
        raw = json.load(f)
    foods = raw.get("FoundationFoods", [])
    for item in foods:
        nutrients = {}
        for n in item.get("foodNutrients", []):
            nid = n.get("nutrient", {}).get("id")
            if nid in _NUTRIENT_MAP:
                nutrients[_NUTRIENT_MAP[nid]] = n.get("amount")
        _FOOD_DB.append({
            "description": item.get("description", ""),
            "category": item.get("foodCategory", {}).get("description", ""),
            "nutrients": nutrients,
        })
    return _FOOD_DB


def search_food_data(keyword: str, max_results: int = 5) -> list[dict]:
    """
    RAG retrieval: keyword search over the USDA Foundation Foods knowledge base.
    Returns matching foods with their nutritional profiles for the rating agent.

    Parameters
    ----------
    keyword : str
        Search term (e.g. 'chicken', 'rice', 'broccoli').
    max_results : int
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Matching foods with description, category, and nutrient breakdown.
    """
    db = _load_food_db()
    if not db:
        return []
    kw = keyword.lower().strip()
    matches = [f for f in db if kw in f["description"].lower()]
    return matches[:max_results]


def retrieve_nutrition_context(ingredients: list[str]) -> str:
    """
    RAG step: retrieve nutritional reference data for the recipe's ingredients
    from the local food_data.json knowledge base. Returns a formatted text
    block the rating agent uses to evaluate Nutritional Balance.
    """
    print("\n" + "=" * 60)
    print("📚 RAG RETRIEVAL — Searching USDA Foundation Foods knowledge base")
    print(f"   Knowledge base: data/food_data.json ({len(_load_food_db())} foods indexed)")
    print(f"   Query ingredients: {ingredients[:8]}")
    print("-" * 60)

    lines = ["NUTRITIONAL REFERENCE DATA (from USDA Foundation Foods knowledge base):"]
    for ing in ingredients[:8]:
        results = search_food_data(ing, max_results=2)
        if results:
            print(f"   🔍 Search '{ing}' → {len(results)} match(es):")
            for r in results:
                n = r["nutrients"]
                line = (
                    f"- {r['description']} ({r['category']}): "
                    f"{n.get('calories', '?')} kcal, "
                    f"{n.get('protein', '?')}g protein, "
                    f"{n.get('carbohydrate', '?')}g carbs, "
                    f"{n.get('fat', '?')}g fat, "
                    f"{n.get('fiber', '?')}g fiber"
                )
                print(f"      {line}")
                lines.append(line)
        else:
            print(f"   🔍 Search '{ing}' → no matches in knowledge base")
            lines.append(f"- {ing}: no reference data found in knowledge base")

    print("=" * 60 + "\n")
    return "\n".join(lines)


# 2. Function Calling – Tool Definition #################################

def get_ingredient_nutrition(ingredient: str) -> dict:
    """
    Function calling tool: look up USDA nutrition data for a single ingredient
    via the USDA FoodData Central API.

    Parameters
    ----------
    ingredient : str
        The ingredient to look up (e.g. 'chicken breast').

    Returns
    -------
    dict
        Nutrition data with calories, protein, carbohydrate, fat, or an error message.
    """
    from nutrition_query import get_nutrition_for_food
    nut, err = get_nutrition_for_food(ingredient)
    if err:
        return {"ingredient": ingredient, "error": err}
    return {"ingredient": ingredient, **nut}


# Tool metadata for the LLM (Ollama function calling format)
tool_get_ingredient_nutrition = {
    "type": "function",
    "function": {
        "name": "get_ingredient_nutrition",
        "description": (
            "Look up USDA nutrition data (calories, protein, carbohydrate, fat) "
            "for a single food ingredient via the FoodData Central API"
        ),
        "parameters": {
            "type": "object",
            "required": ["ingredient"],
            "properties": {
                "ingredient": {
                    "type": "string",
                    "description": "The food ingredient to look up (e.g. 'chicken breast', 'rice')",
                }
            },
        },
    },
}


# 3. Agent 2 – Recipe Critic #################################


def rate_recipe(
    recipe_text: str,
    user_ingredients: list[str],
    recipe_name: str = "",
    ollama_api_key: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Agent 2: Recipe Critic. Takes a generated recipe and the user's ingredient
    list, runs RAG retrieval and function calling, then asks the LLM to produce
    a structured JSON rating across three categories.

    Parameters
    ----------
    recipe_text : str
        The full recipe markdown generated by Agent 1.
    user_ingredients : list[str]
        Ingredients the user said they have.
    recipe_name : str
        Name of the recipe being rated.
    ollama_api_key : str | None
        Ollama API key override.

    Returns
    -------
    tuple[dict | None, str | None]
        (rating_dict, error_message). rating_dict has keys:
        overall_score, ease_of_preparation, completeness,
        nutritional_balance — each a float 1.0-5.0.
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return None, "OLLAMA_API_KEY not set."

    print("\n" + "🤖" * 30)
    print("AGENT 2: RECIPE CRITIC — Rating pipeline started")
    print(f"   Recipe: {recipe_name}")
    print(f"   Ingredients: {', '.join(user_ingredients)}")
    print("🤖" * 30)

    # --- RAG: retrieve nutritional reference data from knowledge base ---
    print("\n📖 Step 1/3: RAG Retrieval")
    rag_context = retrieve_nutrition_context(user_ingredients)

    # --- Function Calling: get USDA nutrition for key ingredients ---
    print("\n" + "=" * 60)
    print("🔧 Step 2/3: FUNCTION CALLING — get_ingredient_nutrition()")
    print(f"   Tool: get_ingredient_nutrition")
    print(f"   Description: Queries USDA FoodData Central API for real-time nutrition")
    print("-" * 60)

    nutrition_reports = []
    for ing in user_ingredients[:4]:
        print(f"   ⚡ Calling get_ingredient_nutrition('{ing}')...")
        report = get_ingredient_nutrition(ing)
        nutrition_reports.append(report)
        if "error" in report:
            print(f"      → Error: {report['error']}")
        else:
            print(f"      → {report.get('calories', '?')} kcal, "
                  f"{report.get('protein', '?')}g protein, "
                  f"{report.get('carbohydrate', '?')}g carbs, "
                  f"{report.get('fat', '?')}g fat")

    print("=" * 60 + "\n")

    nutrition_text = "USDA NUTRITION LOOKUP RESULTS (via function calling):\n"
    for nr in nutrition_reports:
        if "error" in nr:
            nutrition_text += f"- {nr['ingredient']}: {nr['error']}\n"
        else:
            nutrition_text += (
                f"- {nr['ingredient']}: {nr.get('calories', '?')} kcal, "
                f"{nr.get('protein', '?')}g protein, "
                f"{nr.get('carbohydrate', '?')}g carbs, "
                f"{nr.get('fat', '?')}g fat\n"
            )

    print("🧠 Step 3/3: Sending prompt to Ollama Cloud (gpt-oss:20b-cloud)...")

    # --- Build the Agent 2 prompt ---
    prompt = f"""You are a professional recipe critic and food scientist. Rate the following recipe on a scale of 1.0 to 5.0 across three categories.

RECIPE TO RATE:
{recipe_text}

USER'S AVAILABLE INGREDIENTS: {', '.join(user_ingredients)}

{nutrition_text}

{rag_context}

RATING CATEGORIES (rate each 1.0 to 5.0, use one decimal place):

1. **Ease of Preparation**: How simple is this recipe for a home cook? Consider number of steps, required techniques, equipment, and active cook time. High score = straightforward; low score = complex/advanced.

2. **Completeness**: How comprehensive are the recipe instructions? Are quantities precise? Are cooking times and temperatures given? Are steps clear and ordered? High score = thorough; low score = vague.

3. **Nutritional Balance**: Using the USDA nutrition data and the nutritional reference above, how balanced is this meal? Consider protein/carb/fat ratio, presence of fiber, and overall healthfulness. High score = well-balanced; low score = heavily skewed.

Return ONLY valid JSON in this exact format (no other text):
{{
    "ease_of_preparation": 0.0,
    "completeness": 0.0,
    "nutritional_balance": 0.0,
    "overall_score": 0.0,
    "summary": "2-3 sentence explanation of why you gave these scores. Mention specific strengths and weaknesses."
}}

The overall_score should be the average of the three category scores, rounded to one decimal.
The summary should be concise, specific, and reference the data above (e.g. nutritional facts). Do NOT use generic filler.
"""
    return _call_rating_agent(prompt, api_key)


def _call_rating_agent(prompt: str, api_key: str) -> tuple[dict | None, str | None]:
    """Send the rating prompt to Ollama and parse the JSON response."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-oss:20b-cloud",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        response = requests.post(OLLAMA_CHAT_URL, headers=headers, json=body, timeout=120)
        response.raise_for_status()
        result = response.json()
        text = result.get("message", {}).get("content", "")
    except Exception as e:
        return None, f"Rating agent error: {e}"

    return _parse_rating_json(text)


# Rating keys used for validation and scoring
_RATING_KEYS = ["ease_of_preparation", "completeness", "nutritional_balance"]


def _parse_rating_json(text: str) -> tuple[dict | None, str | None]:
    """Extract the JSON rating object from the LLM response.

    Handles common LLM quirks: markdown code fences, trailing commas,
    unescaped quotes inside the summary string, and extra prose around
    the JSON block.
    """
    # --- Attempt 1: clean up and parse JSON normally ---
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        block = m.group(0)
        block = re.sub(r",\s*}", "}", block)
        try:
            data = json.loads(block)
            return _build_rating(data), None
        except json.JSONDecodeError:
            pass

    # --- Attempt 2: regex-extract individual scores ---
    rating = {}
    for k in _RATING_KEYS:
        pat = rf'"{k}"\s*:\s*([\d.]+)'
        sm = re.search(pat, text)
        if sm:
            try:
                rating[k] = round(min(max(float(sm.group(1)), 1.0), 5.0), 1)
            except ValueError:
                rating[k] = 3.0
        else:
            rating[k] = 3.0

    if not any(re.search(rf'"{k}"', text) for k in _RATING_KEYS):
        return None, "Could not parse rating JSON from agent response."

    rating["overall_score"] = round(
        sum(rating[k] for k in _RATING_KEYS) / len(_RATING_KEYS), 1
    )

    sm = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if sm:
        rating["summary"] = sm.group(1).strip() or None
    else:
        sm2 = re.search(r'"summary"\s*:\s*"([\s\S]*?)"\s*}', text)
        rating["summary"] = sm2.group(1).strip() if sm2 else None

    return rating, None


def _build_rating(data: dict) -> dict:
    """Validate parsed JSON into a clean rating dict."""
    rating = {}
    for k in _RATING_KEYS:
        val = data.get(k)
        try:
            val = round(min(max(float(val), 1.0), 5.0), 1)
        except (TypeError, ValueError):
            val = 3.0
        rating[k] = val
    rating["overall_score"] = round(
        sum(rating[k] for k in _RATING_KEYS) / len(_RATING_KEYS), 1
    )
    rating["summary"] = str(data.get("summary", "")).strip() or None
    return rating
