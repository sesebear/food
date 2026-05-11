# smart-chef-validation

Validation system for HOMEWORK3. Scores Smart Chef's AI-generated recipe reports on 7 recipe-specific dimensions (a mix of deterministic checks, RAG-grounded comparisons, and AI-graded judgments) and runs a statistical experiment to compare three Agent-1 prompt variants.

## Tech stack

| Layer       | Technology |
|-------------|------------|
| Language    | Python 3.10+ |
| HTTP        | `requests` |
| Env         | `python-dotenv`, `.env` |
| Stats       | `scipy`, `pingouin`, `statsmodels` |
| Plotting    | `matplotlib` |
| Data        | `pandas`, JSONL, CSV |
| AI provider | Ollama Cloud (`gpt-oss:20b-cloud`) |
| Reference   | USDA FoodData Central (live API + local `data/food_data.json`) |

## Installation

Assumes a fresh environment from the repo root.

1. **Prerequisites**: Python 3.10+, an Ollama Cloud account, a USDA FoodData Central API key.
2. **Install deps** (in addition to `smart_chef/requirements.txt`):
   ```bash
   pip install -r smart_chef/validation/requirements.txt
   ```
3. **API keys** in `smart_chef/.env`:
   ```
   OLLAMA_API_KEY=your_ollama_key
   FDC_API_KEY=your_usda_key
   ```
   The validation scripts read the same `.env` as the Shiny app — no new keys required.

## Usage

From the repo root, run the three scripts in order:

```bash
# 1. Generate 30 recipes (5 ingredient sets × 3 prompts × 2 reps)
python smart_chef/validation/generate_reports.py

# 2. Score every recipe on the 7 dimensions
python smart_chef/validation/run_validation.py

# 3. Run the statistical analysis + save plots
python smart_chef/validation/analyze.py
```

Smoke-test (6 reports, ~1 min) before the full run:

```bash
python smart_chef/validation/generate_reports.py --max-reports 6
python smart_chef/validation/run_validation.py --limit 6
python smart_chef/validation/analyze.py
```

Both `generate_reports.py` and `run_validation.py` are idempotent. Re-running `generate_reports.py --resume` skips cells already in `data/reports.jsonl`; `run_validation.py` skips reports already scored in `data/scores.csv` (use `--rebuild` to redo from scratch).

## Project structure

```
smart_chef/validation/
├── README.md                  ← this file (System Design + Usage)
├── rubric.md                  ← Validation Criteria Table (7 dimensions)
├── requirements.txt           ← Stats + plotting deps
├── prompts.py                 ← Prompt A (baseline), B (minimalist), C (structured + safety)
├── generate_reports.py        ← Build the corpus (30 recipes by default)
├── validator.py               ← 7-dimension scorer; reuses RAG + USDA helpers
├── run_validation.py          ← Score every recipe → data/scores.csv (idempotent)
├── analyze.py                 ← Bartlett → ANOVA → t-tests → regression → plots
├── data/
│   ├── ingredient_sets.json   ← 5 stratified inputs (protein+grain, vegetarian, seafood, dessert, weeknight)
│   ├── reports.jsonl          ← Generated recipes (append-only)
│   └── scores.csv             ← Per-recipe scores (tidy long form)
└── outputs/
    ├── anova_table.txt        ← Bartlett + omnibus ANOVA + pairwise + per-dimension
    ├── regression_summary.txt ← OLS: overall_score ~ prompt + ingredient_set
    ├── boxplot_overall.png    ← Overall score by prompt
    └── per_dimension_bar.png  ← Mean per dimension, grouped by prompt
```

## System Design

The validation system wraps Smart Chef's existing Agent 1 (recipe generator) with a new offline pipeline:

1. **Generation** (`generate_reports.py`): For every cell in the 5 × 3 × 2 experimental grid, calls Ollama Cloud (`gpt-oss:20b-cloud`) with one of the three prompt variants from `prompts.py`. Each response is appended as one JSON line to `data/reports.jsonl`.
2. **Validation** (`run_validation.py` + `validator.py`): Each recipe gets scored on 7 dimensions. Deterministic dimensions (`dish_name_match`, `ingredient_faithfulness`, `technique_specificity`, `reproducibility`) run as Python regex/set-ops on the recipe markdown. `nutritional_honesty` compares live USDA macros with the USDA RAG estimate (reusing `smart_chef/rating_utils.py:search_food_data` and `nutrition_query.estimate_recipe_nutrition_from_ingredients`). `food_safety` and `cultural_plausibility` are obtained in **one** LLM call per recipe to control API cost.
3. **Analysis** (`analyze.py`): Runs Bartlett's test → Welch ANOVA (or standard) on `overall_score` by `prompt_id` → Holm-corrected pairwise t-tests → per-dimension ANOVAs → an OLS regression that controls for `ingredient_set_id` (handles the fact that the same ingredient sets are reused across prompts). Saves text outputs and PNG plots.

See [`rubric.md`](rubric.md) for the full dimension specs and how this design departs from the LAB Likert validator.

## Experimental Design

| Factor | Levels | Notes |
|---|---|---|
| Prompt (manipulated) | A — Baseline (current production prompt) <br> B — Minimalist (`Write a recipe for X using Y.`) <br> C — Structured + Safety (forces metric quantities, time + temperature per step, dedicated safety section) | Generator prompt is the only thing that changes across cells. |
| Ingredient set (blocking) | 5 stratified inputs (protein+grain, vegetarian, seafood, dessert, weeknight) | Same dish_name + ingredient list used across all 3 prompts. |
| Repetitions | 2 | Captures LLM stochasticity at the same temperature. |
| Total reports | **30** (n=10 per prompt) | Adequate power for ANOVA / pairwise t-tests on a single-factor design. |
| Generator model | `gpt-oss:20b-cloud` (Ollama Cloud) | Same as Smart Chef's Agent 1. |
| Validator model | `gpt-oss:20b-cloud` (Ollama Cloud) | Same model judges all three prompts — fair comparison; documented as a judge-bias risk in the writing component. |

## Statistical Analysis

We test three nested hypotheses with the same dataset:

1. **Omnibus**: does prompt choice matter at all?
   - H0: μ(A) = μ(B) = μ(C) on `overall_score`.
   - Test: one-way ANOVA (or Welch's if Bartlett's p < 0.05). Reports F, η², p.

2. **Pairwise**: *which* prompts differ?
   - Holm-corrected t-tests A↔B, A↔C, B↔C. Reports Cohen's *d*.

3. **Per-dimension**: *where* does the difference live?
   - One ANOVA per dimension. Identifies whether Prompt C beats A specifically on technique_specificity / reproducibility / food_safety (our hypothesis) or on something else.

4. **Regression** (handles non-independence): the same ingredient sets recur across prompts, so observations within an ingredient set are correlated. The OLS model `overall_score ~ C(prompt_id) + C(ingredient_set_id)` controls for ingredient-set difficulty; the coefficients on `prompt_id` are the cleanest estimate of the prompt effect.

All outputs land in `outputs/` and the printed console log captures the same numbers.

## Technical Details

- **API keys**: `OLLAMA_API_KEY` (required), `FDC_API_KEY` (required for `nutritional_honesty`). Loaded from `smart_chef/.env` via the same pattern as `ai_utils.py`.
- **Endpoint**: `https://ollama.com/api/chat` — same as the Shiny app.
- **No app modifications**: Nothing in `app.py`, `ai_utils.py`, `rating_utils.py`, or `nutrition_query.py` is changed. The validator *imports* from `rating_utils` and `nutrition_query` to reuse the RAG store.
- **Reproducibility**: `data/reports.jsonl` and `data/scores.csv` are deterministic given the same prompts and ingredient sets (modulo LLM stochasticity, which is exactly what the `run` dimension captures).

## Where things live for HOMEWORK3 deliverables

| HW3 component | File(s) |
|---|---|
| 📝 Writing component (your own words) | Authored in your `.docx`; cite this README + `rubric.md` for the design |
| 🔗 Git links | `validator.py`, `rubric.md`, `data/scores.csv`, `outputs/anova_table.txt`, `outputs/regression_summary.txt`, `data/reports.jsonl` |
| 📸 Screenshots (4–5) | Terminal output of `run_validation.py`; a recipe + score row; rendered `rubric.md` table; `outputs/boxplot_overall.png`; `outputs/per_dimension_bar.png` |
| 📚 Documentation | This README (System Design, Experimental Design, Statistical Analysis, Technical Details, Usage) + [`rubric.md`](rubric.md) |
