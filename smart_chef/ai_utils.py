# ai_utils.py
# Smart Chef – Ollama AI helpers for recipe generation and reporting

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
    Generates a technical recipe using professional naming conventions.
    Focuses on step-by-step execution.
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return None, "OLLAMA_API_KEY not set."

    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"

    prompt = f"""
    You are a professional executive chef. Provide a technical, clear recipe for: "{recipe_name if recipe_name else 'a dish using ' + ing_str}".
    
    NAMING RULE: Do not force the ingredient names into the recipe title. Use professional culinary names (e.g., 'Pommes Frites' instead of 'Potato Fries').
    
    User Ingredients: {ing_str}.
    Context: {recipe_description if recipe_description else 'Focus on high-quality execution.'}

    FORMATTING RULES:
    1. ## [Culinary Recipe Name]
    2. ### Ingredients: Precise quantities and prep states (e.g., 'diced', 'minced').
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
    Uses 'Culinary Identity' logic to force professional naming and 
    broad semantic expansion (e.g., Potato -> Pommes Frites).
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        return [], "OLLAMA_API_KEY not set."

    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"
    n = min(max(3, max_recipes), 10)

    prompt = f"""
    You are a culinary expert. Generate {n} recipe ideas based on: {ing_str}.
    
    CRITICAL NAMING CONSTRAINTS:
    1. NEVER use the literal ingredient names in the title unless it is part of a formal dish name (e.g., 'Potato Salad' is okay, but 'Potato with Beef' is FORBIDDEN).
    2. USE ESTABLISHED CULINARY TITLES: If the recipe is for fried potatoes, call it 'Pommes Frites' or 'French Fries'. If it's a potato pancake, call it a 'Latke' or 'Rösti'. 
    3. SEMANTIC EXPANSION: Identify what these ingredients *become* when processed by a chef. Think of derived forms, classic mother sauces, and international variations.
    4. MAIN INGREDIENT FOCUS: Ensure the provided ingredients are the primary architectural component of the dish, not a garnish.

    Return ONLY valid JSON:
    {{
        "recipes": [
            {{
                "recipe_name": "Official Culinary Title", 
                "calories": 0, 
                "protein": 0, 
                "carbohydrate": 0, 
                "fat": 0, 
                "recipe_description": "Technical one-sentence summary."
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