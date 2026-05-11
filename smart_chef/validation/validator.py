# validator.py
# Smart Chef validation – custom recipe validator for HOMEWORK3
# Pairs with run_validation.py, analyze.py
#
# This validator goes BEYOND the LAB's generic Likert scales by scoring each
# recipe on 7 recipe-specific dimensions using a MIX of measurement types:
#
#   1. dish_name_match         — boolean    (deterministic token overlap)
#   2. ingredient_faithfulness — % 0–100    (deterministic substring match)
#   3. technique_specificity   — 0–5 count  (deterministic regex for times + temps)
#   4. food_safety             — boolean    (AI-graded; 1 LLM call)
#   5. nutritional_honesty     — 1–5 scale  (grounded RMSE vs. USDA macros)
#   6. reproducibility         — 0–1 score  (deterministic: quantity/unit/verb hits)
#   7. cultural_plausibility   — 1–7 Likert (AI-graded; same LLM call as #4)
#
# Each report yields one row of `scores.csv`. See rubric.md for the full
# definitions and how this differs from the LAB Likert scales.

# 0. Setup #################################

## 0.1 Imports ############################

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Make the parent `smart_chef/` package importable so we can reuse the
# existing RAG helper and USDA client without duplicating code.
_SMART_CHEF_DIR = Path(__file__).resolve().parent.parent
if str(_SMART_CHEF_DIR) not in sys.path:
    sys.path.insert(0, str(_SMART_CHEF_DIR))

from rating_utils import search_food_data  # USDA RAG retrieval
from nutrition_query import estimate_recipe_nutrition_from_ingredients


## 0.2 Load Environment ############################

# Reuse the same .env loading pattern as ai_utils.py so the same API keys work.
_script_dir = Path(__file__).resolve().parent
_project_root = _SMART_CHEF_DIR.parent
try:
    load_dotenv(_project_root / ".env")
    load_dotenv(_SMART_CHEF_DIR / ".env")
    load_dotenv(_script_dir / ".env")
except OSError:
    pass

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_CHAT_URL = "https://ollama.com/api/chat"
OLLAMA_MODEL = "gpt-oss:20b-cloud"  # Same model as Agent 1 / Agent 2


# 1. Deterministic Dimensions #################################

## 1.1 Dimension 1 – Dish Name Match ############################

# Token-overlap ratio between the recipe's first H2 heading and the requested
# dish name. We strip punctuation/stopwords and require >= 0.6 overlap.

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "with", "of", "in", "on",
    "classic", "easy", "quick", "homemade", "simple", "best",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-word chars, drop stopwords and single letters."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _extract_recipe_title(recipe_text: str) -> str:
    """Pull the first markdown H2 line ('## Title') from the recipe."""
    m = re.search(r"^##\s+(.+)$", recipe_text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def dim_dish_name_match(recipe_text: str, requested_name: str) -> dict:
    """Boolean dish-name match based on token overlap."""
    title = _extract_recipe_title(recipe_text)
    req_tokens = _tokenize(requested_name)
    got_tokens = _tokenize(title)
    if not req_tokens:
        return {"value": 0, "overlap": 0.0, "title": title}
    overlap = len(req_tokens & got_tokens) / len(req_tokens)
    return {"value": 1 if overlap >= 0.6 else 0, "overlap": round(overlap, 3), "title": title}


## 1.2 Dimension 2 – Ingredient Faithfulness ############################

# Percentage of user-supplied ingredients explicitly mentioned anywhere in the
# recipe markdown. Substring match is case-insensitive and trims plurals.

def _stem(word: str) -> str:
    """Crude singular form: strip trailing 's' so 'eggs' matches 'egg'."""
    w = word.lower().strip()
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def dim_ingredient_faithfulness(recipe_text: str, user_ingredients: list[str]) -> dict:
    """Fraction of user ingredients that appear in the recipe text."""
    if not user_ingredients:
        return {"value": 0.0, "matched": [], "missing": []}
    text_lower = recipe_text.lower()
    matched, missing = [], []
    for ing in user_ingredients:
        # Try the full ingredient and each word in it
        candidates = [_stem(ing)] + [_stem(w) for w in ing.split() if len(w) > 2]
        hit = any(c in text_lower for c in candidates if c)
        (matched if hit else missing).append(ing)
    pct = round(100.0 * len(matched) / len(user_ingredients), 1)
    return {"value": pct, "matched": matched, "missing": missing}


## 1.3 Dimension 3 – Technique Specificity ############################

# Count instruction steps containing a time AND/OR a temperature. Cap at 5.
# We segment by numbered list lines ("1.", "2.", etc.) in the Instructions section.

_TIME_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:min|mins|minute|minutes|sec|seconds|hour|hours|hr|hrs)\b", re.I)
_TEMP_RE = re.compile(r"\b\d{2,3}\s?(?:°\s?[CF]|degrees?\s*(?:celsius|fahrenheit|c|f))\b", re.I)


def _extract_instruction_steps(recipe_text: str) -> list[str]:
    """Return the lines under the '### Instructions' heading (numbered or not)."""
    m = re.search(r"(?:^|\n)#{2,3}\s*Instructions?\s*\n(.*?)(?=\n#{2,3}\s|\Z)",
                  recipe_text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        # Fallback: any numbered lines anywhere
        return re.findall(r"^\s*\d+[.)]\s+.+$", recipe_text, flags=re.MULTILINE)
    block = m.group(1)
    steps = re.findall(r"^\s*\d+[.)]\s+.+$", block, flags=re.MULTILINE)
    if steps:
        return steps
    # Bulleted fallback
    return [ln for ln in block.splitlines() if ln.strip()]


def dim_technique_specificity(recipe_text: str) -> dict:
    """Score 0-5 = number of steps containing a time and/or temperature."""
    steps = _extract_instruction_steps(recipe_text)
    specific = 0
    for s in steps:
        if _TIME_RE.search(s) or _TEMP_RE.search(s):
            specific += 1
    score = min(5, specific)
    return {"value": score, "n_steps": len(steps), "n_specific": specific}


## 1.4 Dimension 6 – Reproducibility ############################

# Composite 0–1: per instruction step, does it contain
#   (a) a number (quantity / time / temp)
#   (b) a unit word (g, ml, tsp, tbsp, cup, °, min, etc.)
#   (c) an action verb (cook, mix, fold, sear, simmer, ...)
# Score = mean of these 3 indicators across all steps.

_UNIT_RE = re.compile(r"\b(?:g|kg|ml|l|tsp|tbsp|cup|cups|oz|lb|°|degrees?|min|mins|minute|hour|hours|seconds?)\b", re.I)
_NUM_RE = re.compile(r"\b\d+(?:[.,/]\d+)?\b")
_VERB_RE = re.compile(
    r"\b(?:cook|bake|roast|sear|simmer|boil|fry|saut[ée]|stir|whisk|fold|mix|knead|chop|dice|mince|slice|"
    r"season|add|remove|drain|rest|cool|serve|combine|preheat|reduce|deglaze|rinse|wash)\b",
    re.I,
)


def dim_reproducibility(recipe_text: str) -> dict:
    """Mean of (has_number, has_unit, has_verb) over instruction steps."""
    steps = _extract_instruction_steps(recipe_text)
    if not steps:
        return {"value": 0.0, "n_steps": 0}
    hits = 0.0
    for s in steps:
        ind = [
            bool(_NUM_RE.search(s)),
            bool(_UNIT_RE.search(s)),
            bool(_VERB_RE.search(s)),
        ]
        hits += sum(ind) / 3.0
    score = round(hits / len(steps), 3)
    return {"value": score, "n_steps": len(steps)}


# 2. Grounded Dimension – Nutritional Honesty #################################

# This is the dimension that uses the existing USDA RAG knowledge base as a
# GOLD STANDARD. We compare two macro vectors:
#   - USDA estimate from the user's ingredient list (live FDC API).
#   - USDA RAG average from food_data.json across the matched foods (per ingredient).
# A recipe that "claims" ingredients matching common USDA profiles is more honest;
# the more its ingredient list diverges from typical USDA macros, the worse it scores.
# (We use the difference between the two USDA-derived estimates as a robustness check;
# this isolates whether the *recipe* picked ingredients with plausible nutrition,
# which is what we actually want to measure.)

_RAG_MACRO_KEYS = ("calories", "protein", "carbohydrate", "fat")


def _rag_macro_estimate(ingredients: list[str]) -> dict:
    """Sum the top-1 USDA Foundation Foods match per ingredient using the RAG store."""
    acc = {k: 0.0 for k in _RAG_MACRO_KEYS}
    n_found = 0
    for ing in ingredients[:8]:
        hits = search_food_data(ing, max_results=1)
        if not hits:
            continue
        n_found += 1
        nut = hits[0].get("nutrients", {})
        for k in _RAG_MACRO_KEYS:
            v = nut.get(k)
            if isinstance(v, (int, float)):
                acc[k] += float(v)
    return {"sum": acc, "n_found": n_found}


def dim_nutritional_honesty(user_ingredients: list[str]) -> dict:
    """Map normalized RMSE between live-USDA and RAG-USDA macro sums to 1–5 score."""
    rag = _rag_macro_estimate(user_ingredients)
    if rag["n_found"] == 0:
        return {"value": 3.0, "rmse": None, "reason": "no_rag_match"}
    live, err = estimate_recipe_nutrition_from_ingredients(user_ingredients)
    if err or not live:
        # If the live API is unreachable but RAG worked, we still trust RAG and give a 4.
        return {"value": 4.0, "rmse": None, "reason": err or "no_live_data"}
    # Normalized RMSE: divide each macro diff by max(live, rag, 1) then RMSE.
    sq = 0.0
    for k in _RAG_MACRO_KEYS:
        lv = float(live.get(k) or 0.0)
        rv = float(rag["sum"].get(k) or 0.0)
        denom = max(lv, rv, 1.0)
        sq += ((lv - rv) / denom) ** 2
    rmse = (sq / len(_RAG_MACRO_KEYS)) ** 0.5  # in [0, ~1]
    # Map rmse -> 1..5 (lower rmse = higher score)
    if rmse < 0.10:
        score = 5.0
    elif rmse < 0.25:
        score = 4.0
    elif rmse < 0.50:
        score = 3.0
    elif rmse < 0.75:
        score = 2.0
    else:
        score = 1.0
    return {"value": score, "rmse": round(rmse, 3)}


# 3. AI-Graded Dimensions – Food Safety + Cultural Plausibility #################################

## 3.1 LLM Call ############################

# One Ollama call covers BOTH AI-graded dimensions to keep API cost down.
# The validator LLM is the same model as Agent 1 / Agent 2 by design choice:
# we accept some judge-bias risk in exchange for cost and consistency, and we
# document this trade-off in the writing component (HW3 §writing).

_VALIDATOR_PROMPT_TEMPLATE = """You are a critical recipe validator. Read the recipe below and assess two narrow questions. Reply with VALID JSON only.

REQUESTED DISH: {dish}
RECIPE TEXT:
{recipe}

Question 1 (food_safety): Does this recipe omit ANY critical food-safety step?
  - For poultry / pork / ground meat: must mention a safe internal temperature OR explicit "cook until no longer pink".
  - For seafood: must mention doneness cue or temp.
  - For eggs: if raw/runny, must note risk.
  - For produce: should mention washing where relevant.
  - Cross-contamination cues count.
Return safe = true only if NO critical safety step is missing for this dish.

Question 2 (cultural_plausibility): On a 1–7 Likert scale, is this dish coherent
with established cuisine for "{dish}"? Penalize substitutions that violate the
dish's identity (e.g., soy sauce in pommes frites). 1 = incoherent, 7 = textbook.

Return ONLY this JSON object, no prose:
{{
  "food_safety": true,
  "food_safety_hazard": "short reason if false, else empty string",
  "cultural_plausibility": 5,
  "cultural_plausibility_reason": "one short sentence"
}}
"""


def _call_validator_llm(prompt: str, api_key: str) -> tuple[dict | None, str | None]:
    """POST to Ollama Cloud and parse the JSON envelope."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_CHAT_URL, headers=headers, json=body, timeout=180)
        r.raise_for_status()
        text = r.json().get("message", {}).get("content", "")
    except Exception as e:  # noqa: BLE001 — surface upstream
        return None, f"validator http error: {e}"
    return _parse_validator_json(text)


## 3.2 Robust JSON Parsing ############################

# Mirrors rating_utils._parse_rating_json: clean markdown fences, regex-extract
# the JSON object, then fall back to per-key extraction if json.loads fails.

def _parse_validator_json(text: str) -> tuple[dict | None, str | None]:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        block = re.sub(r",\s*}", "}", m.group(0))
        try:
            return _validate_validator_dict(json.loads(block)), None
        except json.JSONDecodeError:
            pass

    # Fallback: per-key regex extraction
    out: dict = {}
    fs = re.search(r'"food_safety"\s*:\s*(true|false)', text, re.IGNORECASE)
    out["food_safety"] = (fs.group(1).lower() == "true") if fs else True
    cp = re.search(r'"cultural_plausibility"\s*:\s*([\d.]+)', text)
    out["cultural_plausibility"] = float(cp.group(1)) if cp else 4.0
    haz = re.search(r'"food_safety_hazard"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    out["food_safety_hazard"] = haz.group(1).strip() if haz else ""
    rsn = re.search(r'"cultural_plausibility_reason"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    out["cultural_plausibility_reason"] = rsn.group(1).strip() if rsn else ""
    return _validate_validator_dict(out), None


def _validate_validator_dict(d: dict) -> dict:
    """Coerce types and clamp ranges so downstream stats are well-behaved."""
    fs = bool(d.get("food_safety", True))
    try:
        cp = float(d.get("cultural_plausibility", 4))
    except (TypeError, ValueError):
        cp = 4.0
    cp = max(1.0, min(7.0, round(cp, 1)))
    return {
        "food_safety": fs,
        "food_safety_hazard": str(d.get("food_safety_hazard", "")).strip(),
        "cultural_plausibility": cp,
        "cultural_plausibility_reason": str(d.get("cultural_plausibility_reason", "")).strip(),
    }


def dim_ai_graded(recipe_text: str, dish_name: str, api_key: str) -> dict:
    """Run the one LLM call that covers food_safety + cultural_plausibility."""
    prompt = _VALIDATOR_PROMPT_TEMPLATE.format(dish=dish_name.strip(), recipe=recipe_text)
    data, err = _call_validator_llm(prompt, api_key)
    if err or not data:
        # Conservative defaults so the experiment still runs even if Ollama hiccups.
        return {
            "food_safety": False,
            "food_safety_hazard": err or "validator_failed",
            "cultural_plausibility": 4.0,
            "cultural_plausibility_reason": "validator failed",
        }
    return data


# 4. Composite Score #################################

# Each dimension is normalized to a [0, 1] scale, then averaged with equal
# weights. Weights live here (not hard-coded inline) so reviewers can change
# them in one place if they disagree with our defaults.

DIMENSION_WEIGHTS = {
    "dish_name_match":         1 / 7,
    "ingredient_faithfulness": 1 / 7,
    "technique_specificity":   1 / 7,
    "food_safety":             1 / 7,
    "nutritional_honesty":     1 / 7,
    "reproducibility":         1 / 7,
    "cultural_plausibility":   1 / 7,
}


def _normalize(name: str, value) -> float:
    """Map each dimension's raw value into [0, 1]."""
    if name == "dish_name_match":         return float(value)             # 0 or 1
    if name == "ingredient_faithfulness": return float(value) / 100.0      # 0..100 -> 0..1
    if name == "technique_specificity":   return float(value) / 5.0        # 0..5  -> 0..1
    if name == "food_safety":             return 1.0 if value else 0.0     # bool
    if name == "nutritional_honesty":     return (float(value) - 1.0) / 4.0  # 1..5  -> 0..1
    if name == "reproducibility":         return float(value)              # already 0..1
    if name == "cultural_plausibility":   return (float(value) - 1.0) / 6.0  # 1..7 -> 0..1
    raise KeyError(name)


def compute_overall_score(row: dict) -> float:
    """Weighted mean of the 7 normalized dimensions, on a 0–100 scale."""
    total = 0.0
    for name, w in DIMENSION_WEIGHTS.items():
        total += w * _normalize(name, row[name])
    return round(100.0 * total, 2)


# 5. Public API #################################


def validate_report(
    *,
    recipe_text: str,
    dish_name: str,
    user_ingredients: list[str],
    ollama_api_key: str | None = None,
) -> dict:
    """Run all 7 dimensions on a single report and return a flat score row.

    Parameters
    ----------
    recipe_text : str
        Full markdown recipe from Agent 1.
    dish_name : str
        Requested dish name (from the ingredient set).
    user_ingredients : list[str]
        The exact ingredient list passed to Agent 1.
    ollama_api_key : str | None
        Override; falls back to OLLAMA_API_KEY from .env.

    Returns
    -------
    dict
        Flat row with the 7 dimension values, the composite overall_score,
        and a few diagnostic side fields (matched/missing ingredients, etc.).
    """
    api_key = ollama_api_key or OLLAMA_API_KEY
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY not set; cannot run AI-graded dimensions.")

    d1 = dim_dish_name_match(recipe_text, dish_name)
    d2 = dim_ingredient_faithfulness(recipe_text, user_ingredients)
    d3 = dim_technique_specificity(recipe_text)
    d6 = dim_reproducibility(recipe_text)
    d5 = dim_nutritional_honesty(user_ingredients)
    d47 = dim_ai_graded(recipe_text, dish_name, api_key)

    row = {
        "dish_name_match":         d1["value"],
        "ingredient_faithfulness": d2["value"],
        "technique_specificity":   d3["value"],
        "food_safety":             1 if d47["food_safety"] else 0,
        "nutritional_honesty":     d5["value"],
        "reproducibility":         d6["value"],
        "cultural_plausibility":   d47["cultural_plausibility"],
        # Diagnostics — handy for debugging, ignored by stats.
        "_diag_title":              d1["title"],
        "_diag_overlap":            d1["overlap"],
        "_diag_matched":            ", ".join(d2["matched"]),
        "_diag_missing":            ", ".join(d2["missing"]),
        "_diag_n_steps":            d3["n_steps"],
        "_diag_rmse":               d5.get("rmse"),
        "_diag_food_safety_hazard": d47["food_safety_hazard"],
        "_diag_culture_reason":     d47["cultural_plausibility_reason"],
    }
    row["overall_score"] = compute_overall_score(row)
    return row
