# Smart Chef

Shiny app that finds recipes and nutrition data from ingredients you have. Uses a **multi-agent workflow**: Agent 1 (Ollama) generates recipes, then Agent 2 rates them on five dimensions and displays a visual rating card. USDA FoodData Central provides nutrition facts.

## Multi-Agent Architecture

```
User clicks "Generate Recipe"
        │
        ▼
┌─────────────────────────┐
│  AGENT 1: Recipe Chef   │
│  Generates a full recipe │
│  for the selected dish   │
└────────┬────────────────┘
         │  recipe text
         ▼
┌─────────────────────────┐
│  AGENT 2: Recipe Critic │
│  Rates the recipe on    │
│  5 categories using     │
│  RAG + function calling │
└────────┬────────────────┘
         │  structured rating (JSON)
         ▼
┌─────────────────────────┐
│  RATING CARD UI         │
│  Visual scorecard with  │
│  overall + category bars│
└─────────────────────────┘
```

### Agent 1: Recipe Chef

Generates a professional recipe for the exact dish the user selected. Uses the user's available ingredients and the recipe name from the table to produce formatted markdown with ingredients, instructions, and chef's notes.

### Agent 2: Recipe Critic

Evaluates the generated recipe across five categories (1.0–5.0 scale):

| Category | What It Measures |
|----------|-----------------|
| **Ingredient Utilization** | How well the recipe uses the ingredients the user said they had |
| **Ease of Preparation** | How simple the recipe is for a home cook |
| **Completeness** | How comprehensive the instructions are (quantities, times, temps) |
| **Nutritional Balance** | How balanced the meal is across macros, informed by USDA data |
| **Creativity** | How inventive or interesting the recipe is |

## RAG Integration

Agent 2 uses **Retrieval-Augmented Generation** to evaluate nutritional balance. The file `data/food_data.json` contains 365 USDA Foundation Foods with detailed nutritional profiles across 19 food categories. Before rating, the system searches this knowledge base for each of the user's ingredients and retrieves reference nutritional data (calories, protein, carbs, fat, fiber). This context is injected into Agent 2's prompt so it can compare the recipe's nutritional profile against real USDA reference values.

## Function Calling

Agent 2 uses two function calling tools to gather structured data before rating:

| Tool | Purpose | Parameters | Returns |
|------|---------|------------|---------|
| `get_ingredient_nutrition` | Queries the USDA FoodData Central API for real-time nutrition data on a single ingredient | `ingredient` (str) | `{ingredient, calories, protein, carbohydrate, fat}` |
| `check_ingredient_utilization` | Compares the recipe's ingredients against the user's stated ingredients | `recipe_ingredients` (list), `user_ingredients` (list) | `{used, unused, extra, utilization_pct}` |

Both tools are defined with Ollama-compatible metadata in `rating_utils.py` and are called programmatically during the Agent 2 workflow — their outputs are included in the rating prompt as structured context.

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Web UI | Shiny for Python |
| API | USDA FoodData Central (nutrition data) |
| AI | Ollama Cloud (recipe generation + rating) |
| RAG Data | `data/food_data.json` (365 USDA Foundation Foods) |
| Env | python-dotenv, `.env` |

## Usage Instructions

### 1. Install dependencies

```bash
cd smart_chef
pip install -r requirements.txt
```

### 2. Set up API keys

Create a `.env` file in the `smart_chef` folder:

```
FDC_API_KEY=your_usda_key_here
OLLAMA_API_KEY=your_ollama_key_here
```

- USDA key: https://fdc.nal.usda.gov/api-key-signup
- Ollama key: https://ollama.com

### 3. Run the app

```bash
shiny run app.py
```

### 4. Use the app

1. Open the URL shown (e.g. `http://127.0.0.1:8000`).
2. Enter ingredients (comma- or semicolon-separated).
3. Click **Find recipes**.
4. Click **Generate Recipe** on a row — Agent 1 generates the recipe, then Agent 2 rates it.
5. View the **rating card** below the recipe with scores across all five categories.
6. Use **Download Recipe** to save the recipe as markdown.

Requires `FDC_API_KEY` and `OLLAMA_API_KEY` in `.env`.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Main Shiny app (UI + server), multi-agent orchestration |
| `ai_utils.py` | Agent 1: Ollama recipe generation |
| `rating_utils.py` | Agent 2: Recipe rating with RAG and function calling |
| `nutrition_query.py` | USDA FoodData Central API for nutrition lookups |
| `api_utils.py` | Recipe fetch and table helpers |
| `data/food_data.json` | RAG knowledge base — 365 USDA Foundation Foods |
| `styles.css` | Custom UI styles including rating card |
| `requirements.txt` | Python dependencies |
