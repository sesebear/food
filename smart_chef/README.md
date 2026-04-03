# Smart Chef

Shiny for Python app that generates recipes from ingredients you have on hand, then rates each recipe with a visual scorecard. Uses a multi-agent workflow: Agent 1 (Ollama) generates the recipe, Agent 2 rates it on three dimensions using RAG and function calling. USDA FoodData Central provides nutrition data.

**Deployed App:** <https://connect.systems-apps.com/content/e8d8ef53-aff2-47b6-b620-27347d50c091>

---

## System Architecture

### Agent Roles

| Agent | Role | Model | Input | Output |
|-------|------|-------|-------|--------|
| **Agent 1: Recipe Chef** | Generates a full professional recipe for the dish the user selected | Ollama Cloud (`gpt-oss:20b-cloud`) | User's ingredients + selected recipe name | Formatted markdown recipe with ingredients, step-by-step instructions, and chef's notes |
| **Agent 2: Recipe Critic** | Evaluates the generated recipe on three dimensions using RAG and function calling | Ollama Cloud (`gpt-oss:20b-cloud`) | Agent 1's recipe text + RAG context + USDA nutrition data | Structured JSON rating (1.0–5.0 per category) with AI-generated summary |

### Workflow

```
User enters ingredients → clicks "Find recipes"
        │
        ▼
┌──────────────────────────────────┐
│  Ollama Cloud generates recipe   │
│  ideas; USDA enriches nutrition  │
└────────┬─────────────────────────┘
         │  recipe table displayed
         ▼
User clicks "Generate Recipe" on a row
        │
        ▼
┌─────────────────────────────────┐
│  AGENT 1: Recipe Chef           │
│  Sends recipe name + ingredients│
│  to Ollama Cloud → returns full │
│  recipe in markdown format      │
└────────┬────────────────────────┘
         │  recipe text (markdown)
         ▼
┌─────────────────────────────────┐
│  AGENT 2: Recipe Critic         │
│  1. RAG: searches food_data.json│
│     for nutritional references  │
│  2. Function calling: queries   │
│     USDA API per ingredient     │
│  3. Sends all context to Ollama │
│     Cloud → returns JSON rating │
└────────┬────────────────────────┘
         │  structured rating (JSON)
         ▼
┌─────────────────────────────────┐
│  RATING CARD UI                 │
│  Visual scorecard: overall score│
│  + category bars + AI summary   │
└─────────────────────────────────┘
```

The two agents run sequentially — Agent 2 cannot start until Agent 1 returns a recipe. This pipeline is orchestrated in `app.py` (lines 300–330).

### Rating Categories

| Category | What It Measures |
|----------|-----------------|
| **Ease of Preparation** | How simple the recipe is for a home cook — steps, techniques, cook time |
| **Completeness** | How comprehensive the instructions are — quantities, times, temperatures |
| **Nutritional Balance** | How balanced the meal is across macros, informed by USDA reference data |

The overall score is the average of the three categories. A short AI-generated summary explains the reasoning behind the scores.

---

## RAG Data Source

**Knowledge base:** `data/food_data.json` — 365 USDA Foundation Foods with detailed nutritional profiles across 19 food categories.

**Source:** Downloaded from the [USDA FoodData Central](https://fdc.nal.usda.gov/) Foundation Foods dataset. Each food entry includes nutrient amounts for calories, protein, carbohydrate, fat, and fiber.

**How it works:**

1. At import time, `rating_utils.py` loads and indexes all 365 foods from `food_data.json`.
2. When Agent 2 rates a recipe, the `retrieve_nutrition_context()` function performs keyword search over the knowledge base for each of the user's ingredients (up to 8).
3. For each ingredient, the top 2 matching foods are retrieved with their full nutritional profiles.
4. These results are formatted into a text block and injected into Agent 2's prompt as reference data, enabling the model to evaluate Nutritional Balance against real USDA values.

**Search function:** `search_food_data(keyword, max_results=5)` in `rating_utils.py` — performs case-insensitive substring matching on the food description field and returns matching entries with their nutrient breakdowns.

---

## Tool Functions

Agent 2 uses the following tools during its rating pipeline:

| Tool | Purpose | Parameters | Returns |
|------|---------|------------|---------|
| `get_ingredient_nutrition` | Queries the USDA FoodData Central API for real-time nutrition data on a single ingredient | `ingredient` (str) — the food to look up (e.g., "chicken breast") | `{ingredient, calories, protein, carbohydrate, fat}` or `{ingredient, error}` if not found |
| `search_food_data` | RAG retrieval — keyword search over the local USDA Foundation Foods knowledge base | `keyword` (str), `max_results` (int, default 5) | List of matching foods with `{description, category, nutrients}` |
| `retrieve_nutrition_context` | Orchestrates RAG retrieval for all ingredients and formats results into a prompt-ready text block | `ingredients` (list[str]) — user's ingredient list | Formatted string with nutritional reference data for injection into the LLM prompt |
| `search_foods` | Searches USDA FoodData Central API for foods matching a query | `search_expression` (str), `api_key` (str, optional), `page_size` (int), `page_number` (int) | `(response_json, error_message)` — response contains a `foods` list |
| `get_nutrition_for_food` | Gets nutrition for a single food via USDA search (returns first match) | `search_expression` (str), `api_key` (str, optional) | `({calories, protein, carbohydrate, fat}, error_message)` |
| `estimate_recipe_nutrition_from_ingredients` | Estimates total recipe nutrition by summing USDA data for each ingredient | `ingredients` (list[str]), `api_key` (str, optional) | `({calories, protein, carbohydrate, fat}, error_message)` |

The `get_ingredient_nutrition` tool is defined with Ollama-compatible function calling metadata (`tool_get_ingredient_nutrition` in `rating_utils.py`) and is called programmatically for each ingredient during the Agent 2 workflow. The USDA API results are included in the rating prompt as structured context.

---

## Technical Details

### API Keys and Endpoints

| Key | Purpose | Where to get it |
|-----|---------|-----------------|
| `OLLAMA_API_KEY` | Authenticates requests to Ollama Cloud for recipe generation (Agent 1) and rating (Agent 2) | [ollama.com](https://ollama.com) |
| `FDC_API_KEY` | Authenticates requests to USDA FoodData Central for nutrition lookups | [fdc.nal.usda.gov/api-key-signup](https://fdc.nal.usda.gov/api-key-signup) |

| Endpoint | Used by | Purpose |
|----------|---------|---------|
| `https://ollama.com/api/chat` | `ai_utils.py`, `rating_utils.py` | Ollama Cloud chat completions (model: `gpt-oss:20b-cloud`) |
| `https://api.nal.usda.gov/fdc/v1/foods/search` | `nutrition_query.py` | USDA FoodData Central food search and nutrition lookup |

### Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `shiny` | ≥1.0.0 | Web UI framework |
| `requests` | ≥2.28.0 | HTTP client for API calls |
| `python-dotenv` | ≥1.0.0 | Load `.env` files |
| `pandas` | ≥2.0.0 | Data manipulation |

### File Structure

| File | Purpose |
|------|---------|
| `app.py` | Main Shiny app (UI + server), multi-agent orchestration |
| `ai_utils.py` | Agent 1: Ollama Cloud recipe generation |
| `rating_utils.py` | Agent 2: Recipe rating with RAG retrieval and function calling |
| `nutrition_query.py` | USDA FoodData Central API client for nutrition lookups |
| `api_utils.py` | Recipe fetch, ingredient validation, and table helpers |
| `data/food_data.json` | RAG knowledge base — 365 USDA Foundation Foods |
| `styles.css` | Custom UI styles including rating card |
| `requirements.txt` | Python dependencies |
| `.env` | API keys (not committed to git) |

---

## Usage Instructions

### 1. Clone and enter the directory

```bash
git clone https://github.com/sesebear/food.git
cd food/smart_chef
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up API keys

Create a `.env` file in the `smart_chef` folder:

```
FDC_API_KEY=your_usda_key_here
OLLAMA_API_KEY=your_ollama_key_here
```

- **USDA key:** sign up at https://fdc.nal.usda.gov/api-key-signup (free, instant)
- **Ollama key:** sign up at https://ollama.com

### 4. Run the app

```bash
shiny run app.py
```

Open the URL shown in the terminal (e.g., `http://127.0.0.1:8000`).

### 5. Use the app

1. **Enter ingredients** in the text box (comma- or semicolon-separated, e.g., `chicken, rice, broccoli, olive oil`).
2. Click **Find recipes** — the app generates recipe ideas via Ollama and enriches them with USDA nutrition data. Results appear in a table.
3. Click **Generate Recipe** on any row — this triggers the two-agent pipeline. Agent 1 generates the recipe, then Agent 2 rates it.
4. The **rating card** appears to the right of the recipe with scores (1.0–5.0) for Ease of Preparation, Completeness, and Nutritional Balance.
5. Click **Download Recipe** to save as a `.md` file.
6. Click **← Back to recipes** to return to the table.

### 6. (Optional) Deployed version

The app is also deployed on Posit Connect and accessible without local setup:
<https://connect.systems-apps.com/content/035e816b-7940-4f4a-8505-051fc59af618>
