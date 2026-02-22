# ai_utils.py
# Smart Chef – Ollama AI helpers for recipe generation and reporting
# Pairs with 04_deployment/smart_chef (Smart Chef Shiny app)

import json
import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env from smart_chef or project root
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
try:
    load_dotenv(project_root / ".env")
    load_dotenv(script_dir / ".env")
except OSError:
    pass  # .env may be missing or unreadable

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_CHAT_URL = "https://ollama.com/api/chat"


def generate_recipe_from_ingredients(
    ingredients: list[str],
    ollama_api_key: str | None = None,
    recipe_name: str | None = None,
    recipe_description: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Generates a recipe for the EXACT dish the user selected from the table.
    The output must match the selected row's recipe name.
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return None, "OLLAMA_API_KEY not set."

    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"

    if recipe_name and recipe_name.strip():
        dish_instruction = f"""
CRITICAL – USER SELECTED THIS SPECIFIC DISH:
The user clicked "Generate Recipe" for this exact row: "{recipe_name.strip()}"
{f'Additional context: {recipe_description.strip()}' if recipe_description and recipe_description.strip() else ''}

You MUST generate a recipe for THIS EXACT DISH and no other.
- Your recipe title MUST match or closely reflect: "{recipe_name.strip()}"
- Do NOT substitute a different dish (e.g., if selected dish is "Chicken with gravy", do NOT generate "Chicken Fried Rice" or "Stir-fry")
- The ingredients and instructions must be appropriate for this specific dish"""
    else:
        dish_instruction = f"Create a practical recipe using these ingredients: {ing_str}."

    prompt = f"""
You are a professional executive chef. The user selected a recipe from a table and wants instructions for that specific dish.

{dish_instruction}

User's available ingredients: {ing_str}

FORMATTING RULES:
1. ## [Recipe Name] – must match the selected dish above
2. ### Ingredients: Precise quantities and prep states (e.g., 'diced', 'minced'). Use only ingredients that belong in this dish.
3. ### Instructions: Numbered, technical steps focusing on heat control, technique, and timing.
4. ### Chef's Notes: 2-3 brief tips on technical finesse or storage.

TONE: Professional and direct. Bold key instructions.
"""
    return _call_ollama(prompt, api_key)

def generate_recipes_with_nutrition(
    ingredients: list[str],
    ollama_api_key: str | None = None,
    max_recipes: int = 8,
) -> tuple[list[dict], str | None]:
    """
    Generates recipe ideas using professional naming, main-ingredient logic,
    and transformation thinking. Used when USDA returns no foods.
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return [], "OLLAMA_API_KEY not set."

    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"
    n = min(max(3, max_recipes), 10)

    prompt = f"""
You are a culinary expert. Generate {n} recipe ideas based on: {ing_str}.

SUBSET RULE: Recipes may use a subset of the ingredients. Not every recipe needs all ingredients—e.g., if the user has "chicken, rice, broccoli, garlic," one recipe might use only chicken and garlic, another only rice and broccoli. Each recipe should use ingredients that genuinely belong in that dish.

PROFESSIONAL NAMING RULE:
Use standard culinary titles from established cuisine. Search your knowledge for real dishes—e.g., Pommes Frites, Dauphinoise, Latkes, Rösti, Gnocchi—rather than constructing generic names like "Potato with oil" or "Fried potato strips."

MAIN INGREDIENT LOGIC:
The provided ingredients must be the STAR of the dish, not a side or garnish. If the user has "potato," prefer "Classic French Fries" or "Potato Gratin" over "Beef Stew with Potatoes"—because potato is central to the former. Rank recipes where the ingredient is the primary architectural component higher.

TRANSFORMATION COMMAND:
Think like a chef: "What can I make with this?"—not like a search engine: "What contains this word?" Consider what the ingredient *becomes* through technique: potato → fries, gnocchi, latkes, dauphinoise; flour → pasta, flatbread, batter; egg → frittata, custard, meringue.

Return ONLY valid JSON:
{{
    "recipes": [
        {{
            "recipe_name": "Standard Culinary Title",
            "calories": 0,
            "protein": 0,
            "carbohydrate": 0,
            "fat": 0,
            "recipe_description": "One-sentence technical summary."
        }}
    ]
}}
"""
    text, err = _call_ollama(prompt, api_key)
    if err or not text:
        return [], err or "No response from AI."

    return _parse_ollama_recipes_json(text)

def generate_nutrition_report(
    ingredients: list[str],
    recipes_summary: str,
    ollama_api_key: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Objective macro-analysis of the suggested meal options.
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return None, "OLLAMA_API_KEY not set."

    prompt = f"""
    Analyze the nutritional density of these ingredients: {", ".join(ingredients)} 
    found in these recipes: {recipes_summary}.

    TASK:
    - ## Summary: Overall nutritional balance.
    - ## Macros: Best options for protein and calorie efficiency.
    - ## Recommendations: 1-2 technical cooking adjustments to optimize health.

    STYLE: Objective, data-driven, and professional.
    """
    return _call_ollama(prompt, api_key)

def _parse_ollama_recipes_json(text: str) -> tuple[list[dict], str | None]:
    import re
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], "JSON Parse Error."

    recipes_raw = data.get("recipes") or []
    if isinstance(recipes_raw, dict):
        recipes_raw = [recipes_raw]
    
    result = []
    for i, r in enumerate(recipes_raw):
        if not isinstance(r, dict): continue
        result.append({
            "recipe_id": f"ollama-{i}",
            "recipe_name": str(r.get("recipe_name", "Recipe")).strip(),
            "recipe_description": str(r.get("recipe_description", "")).strip(),
            "calories": _safe_float(r.get("calories")),
            "protein_g": _safe_float(r.get("protein")),
            "carbs_g": _safe_float(r.get("carbohydrate")),
            "fat_g": _safe_float(r.get("fat")),
            "ingredients": [],
            "recipe_image": None,
        })
    return result, None

def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None

def _call_ollama(prompt: str, api_key: str) -> tuple[str | None, str | None]:
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
        return result.get("message", {}).get("content", ""), None
    except Exception as e:
        return None, str(e)