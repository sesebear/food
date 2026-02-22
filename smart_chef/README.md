# Smart Chef

Shiny app that finds recipes and nutrition data from ingredients you have. AI (Ollama) generates recipes; USDA FoodData Central provides nutrition facts only.

## Tech stack

| Layer      | Technology                    |
|-----------|-------------------------------|
| Language  | Python 3.10+                  |
| Web UI    | Shiny for Python              |
| API       | USDA FoodData Central (nutrition only) |
| AI        | Ollama Cloud                  |
| Env       | python-dotenv, `.env`         |

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
4. Click **Generate Recipe** on a row to see full instructions.
5. Use **Download Recipe** to save the recipe as markdown.

Requires `FDC_API_KEY` and `OLLAMA_API_KEY` in `.env`.

## Project structure

| File             | Purpose                                  |
|------------------|------------------------------------------|
| `app.py`         | Main Shiny app (UI + server)             |
| `nutrition_query.py` | USDA FoodData Central API client      |
| `api_utils.py`   | Recipe fetch and table helpers           |
| `ai_utils.py`    | Ollama recipe and report generation      |
| `styles.css`     | Custom UI styles                         |
| `requirements.txt` | Python dependencies                   |
