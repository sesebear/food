# prompts.py
# Smart Chef validation – three Agent-1 prompt variants for the HOMEWORK3 experiment
# Pairs with generate_reports.py, validator.py

# We compare three prompt designs head-to-head:
#   PROMPT_A — Baseline (the current production Agent 1 prompt from ai_utils.py)
#   PROMPT_B — Minimalist (strip all formatting rules)
#   PROMPT_C — Structured + Safety (explicit quantities, temperatures, safety section)
#
# Each builder returns a single string prompt for Ollama Cloud. Inputs are the
# *same* across all three variants — only the prompt text changes — so any
# difference in validation scores can be attributed to the prompt, not the data.

# 0. Setup #################################

PROMPT_IDS = ["A", "B", "C"]


# 1. Prompt Builders #################################

## 1.1 Prompt A – Baseline ############################

# This is a verbatim copy of the prompt in
# smart_chef/ai_utils.py:generate_recipe_from_ingredients (lines 42-69).
# We keep it here so the experiment is reproducible even if ai_utils.py is later edited.

def build_prompt_a(dish_name: str, ingredients: list[str]) -> str:
    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"
    name = dish_name.strip()

    dish_instruction = f"""
CRITICAL – USER SELECTED THIS SPECIFIC DISH:
The user clicked "Generate Recipe" for this exact row: "{name}"

You MUST generate a recipe for THIS EXACT DISH and no other.
- Your recipe title MUST match or closely reflect: "{name}"
- Do NOT substitute a different dish (e.g., if selected dish is "Chicken with gravy", do NOT generate "Chicken Fried Rice" or "Stir-fry")
- The ingredients and instructions must be appropriate for this specific dish"""

    return f"""
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


## 1.2 Prompt B – Minimalist ############################

# Deliberately spartan. No formatting guidance, no role, no instructions on
# quantities or safety. Used as the negative control in our experiment.

def build_prompt_b(dish_name: str, ingredients: list[str]) -> str:
    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"
    name = dish_name.strip()
    return f"Write a recipe for {name} using {ing_str}."


## 1.3 Prompt C – Structured + Safety ############################

# Explicit chain-of-thought style: forces metric quantities, mandatory
# temperatures and times, and a dedicated Food Safety section. We hypothesize
# this will outperform Prompt A on technique_specificity, reproducibility,
# and food_safety.

def build_prompt_c(dish_name: str, ingredients: list[str]) -> str:
    ing_str = ", ".join(ingredients) if ingredients else "common pantry items"
    name = dish_name.strip()

    return f"""
You are a meticulous test-kitchen recipe developer. Generate a recipe for "{name}" using these ingredients: {ing_str}.

YOU MUST FOLLOW THIS EXACT STRUCTURE — do not omit any section:

## {name}

### Ingredients
- List every ingredient with a metric weight or volume (e.g., "200 g chicken breast", "240 ml stock").
- Mark prep state ("diced", "minced", "room temperature").
- Only use ingredients that belong in this dish.

### Instructions
Number every step. EVERY step that involves heat MUST include BOTH:
  (a) a time in minutes (e.g., "4 minutes"), AND
  (b) a temperature (e.g., "medium-high heat (~200°C / 400°F)" or "oven at 180°C / 350°F").
Be explicit about technique (sear, deglaze, fold, reduce, rest).

### Food Safety
List 2–3 concrete safety checks specific to this recipe. Examples:
- Internal temperature targets for meat / poultry / fish (use °F or °C).
- Cross-contamination steps (wash cutting boards, rinse produce).
- Storage / cooling guidance (refrigerate within 2 hours, etc.).

### Chef's Notes
2–3 brief tips on technique, storage, or substitutions.

TONE: Direct, technical, no filler. Bold key instructions.
"""


# 2. Dispatcher #################################

# Single entry point used by generate_reports.py so the caller does not
# need to know which prompt builder corresponds to which prompt_id.

_BUILDERS = {
    "A": build_prompt_a,
    "B": build_prompt_b,
    "C": build_prompt_c,
}


def build_prompt(prompt_id: str, dish_name: str, ingredients: list[str]) -> str:
    """Return the Agent-1 prompt for the given variant."""
    if prompt_id not in _BUILDERS:
        raise ValueError(f"Unknown prompt_id: {prompt_id!r}. Use one of {PROMPT_IDS}.")
    return _BUILDERS[prompt_id](dish_name, ingredients)
