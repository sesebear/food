# Smart Chef

Shiny for Python app that generates recipes from ingredients you have on hand, then rates each recipe with a visual scorecard. Uses a multi-agent workflow: Agent 1 (Ollama) generates the recipe, Agent 2 rates it on three dimensions using RAG and function calling. USDA FoodData Central provides nutrition data.

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Web UI | Shiny for Python |
| API | USDA FoodData Central (nutrition data) |
| AI | Ollama Cloud (recipe generation + rating) |
| RAG Data | `data/food_data.json` (365 USDA Foundation Foods) |
| Env | python-dotenv, `.env` |

## Installation

Assumes a fresh environment.

1. **Prerequisites**: Python 3.10+, pip.
2. **Install dependencies**:

```bash
cd smart_chef
pip install -r requirements.txt
```

3. **API keys**: Create a `.env` file in the `smart_chef` folder:

```
FDC_API_KEY=your_usda_key_here
OLLAMA_API_KEY=your_ollama_key_here
```

- USDA key: https://fdc.nal.usda.gov/api-key-signup
- Ollama key: https://ollama.com

## Usage

Run the app from the `smart_chef` directory:

```bash
shiny run app.py
```

Open the URL shown in the terminal (e.g. `http://127.0.0.1:8000`).

### Navigating the app

1. **Enter ingredients** in the text box (comma- or semicolon-separated, e.g. `chicken, rice, broccoli, olive oil`).
2. Click **Find recipes** — the app generates recipe ideas via Ollama and enriches them with USDA nutrition data. Results appear in a table with calories, protein, carbs, and fat per recipe.
3. Click **Generate Recipe** on any row — this triggers the two-agent pipeline:
   - **Agent 1** generates a full recipe with ingredients, step-by-step instructions, and chef's notes.
   - **Agent 2** rates the recipe and displays a **rating card** to the right of the recipe with an overall score and category breakdowns.
4. The **rating card** shows scores (1.0–5.0) for Ease of Preparation, Completeness, and Nutritional Balance, plus a short AI-generated summary explaining the scores.
5. Click **Download Recipe** to save the recipe as a `.md` file.
6. Click **← Back to recipes** to return to the table and try another recipe.

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
│  3 categories using     │
│  RAG + function calling │
└────────┬────────────────┘
         │  structured rating (JSON)
         ▼
┌─────────────────────────┐
│  RATING CARD UI         │
│  Visual scorecard with  │
│  overall + category bars│
│  + AI summary           │
└─────────────────────────┘
```

### Agent 1: Recipe Chef

Generates a professional recipe for the exact dish the user selected. Uses the user's available ingredients and the recipe name from the table to produce formatted markdown with ingredients, instructions, and chef's notes.

### Agent 2: Recipe Critic

Evaluates the generated recipe across three categories (1.0–5.0 scale):

| Category | What It Measures |
|----------|-----------------|
| **Ease of Preparation** | How simple the recipe is for a home cook — steps, techniques, cook time |
| **Completeness** | How comprehensive the instructions are — quantities, times, temperatures |
| **Nutritional Balance** | How balanced the meal is across macros, informed by USDA reference data |

The overall score is the average of the three categories. A short AI-generated summary explains the reasoning behind the scores.

## RAG Integration

Agent 2 uses Retrieval-Augmented Generation to evaluate nutritional balance. The file `data/food_data.json` contains 365 USDA Foundation Foods with detailed nutritional profiles across 19 food categories. Before rating, the system searches this knowledge base for each of the user's ingredients and retrieves reference nutritional data (calories, protein, carbs, fat, fiber). This context is injected into Agent 2's prompt so it can compare the recipe's nutritional profile against real USDA reference values.

## Function Calling

Agent 2 uses `get_ingredient_nutrition` to gather structured nutrition data before rating:

| Tool | Purpose | Parameters | Returns |
|------|---------|------------|---------|
| `get_ingredient_nutrition` | Queries the USDA FoodData Central API for real-time nutrition data on a single ingredient | `ingredient` (str) | `{ingredient, calories, protein, carbohydrate, fat}` |

The tool is defined with Ollama-compatible metadata in `rating_utils.py` and is called programmatically during the Agent 2 workflow. For each of the user's ingredients, the tool queries the USDA API and the results are included in the rating prompt as structured context.

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
