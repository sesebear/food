# Smart Chef

Shiny app that finds recipes and nutrition data from ingredients you have. Uses USDA FoodData Central for nutrition lookup and Ollama for AI-generated recipes and reports.

## Tech stack

| Layer      | Technology                    |
|-----------|-------------------------------|
| Language  | Python 3.10+                  |
| Web UI    | Shiny for Python              |
| API       | USDA FoodData Central         |
| AI        | Ollama Cloud                  |
| Env       | python-dotenv, `.env`         |

## Installation

Assumes a fresh environment.

1. **Prerequisites**: Python 3.10+, pip.
2. **Clone** (or navigate to project):
   ```bash
   cd smart_chef
   ```
3. **Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment**: Copy `.env.example` to `.env` and set:
   - `FDC_API_KEY` – required for nutrition (get key at [USDA API key signup](https://fdc.nal.usda.gov/api-key-signup))
   - `OLLAMA_API_KEY` – required for recipe generation (get key at [Ollama signup](ollama.com))

## Usage

Run the Shiny app:

```bash
shiny run app.py
```

Then open the URL shown (e.g. `http://127.0.0.1:8000`). Enter ingredients in the sidebar (comma-separated), click **Find recipes** for nutrition data, and **Generate AI recipe** for an Ollama-generated recipe.

**Test nutrition_query.py** (USDA FoodData Central):

```bash
python nutrition_query.py
```

Requires FDC_API_KEY and OLLAMA_API_KEY in .env.

## Project structure

| File             | Purpose                                  |
|------------------|------------------------------------------|
| `app.py`         | Main Shiny app (UI + server)             |
| `nutrition_query.py` | USDA FoodData Central API client      |
| `api_utils.py`   | Recipe fetch and table helpers           |
| `ai_utils.py`    | Ollama recipe and report generation      |
| `styles.css`     | Custom UI styles                         |
| `requirements.txt` | Python dependencies                   |
