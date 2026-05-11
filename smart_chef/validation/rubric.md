# Smart Chef Validation – Rubric

The validator (`validator.py`) scores every recipe report on **7 recipe-specific dimensions** using a deliberate **mix of measurement types**: 3 deterministic Python checks, 1 grounded RAG comparison, and 2 AI-graded judgments delivered in a single LLM call. The composite `overall_score` is the equally-weighted average of all 7 dimensions, normalized to a 0–100 scale.

This rubric is the deliverable for the HOMEWORK3 "Documentation → Validation Criteria Table" requirement.

---

## Validation Criteria Table

| # | Dimension | Type | Scale / Computation | Benchmark | Source of truth |
|---|---|---|---|---|---|
| 1 | `dish_name_match` | Boolean (deterministic) | Token-overlap ratio between recipe H2 title and requested dish name (stopwords removed). 1 if `overlap ≥ 0.6`. | `1` (true) | User-selected dish name |
| 2 | `ingredient_faithfulness` | Numeric % | % of user-supplied ingredients explicitly mentioned in the recipe markdown (case-insensitive, crude stemming). | `≥ 80 %` | User's ingredient list |
| 3 | `technique_specificity` | Count 0–5 | Number of `### Instructions` steps containing a numeric **time** AND/OR **temperature** (regex match). Capped at 5. | `≥ 3` | Recipe text |
| 4 | `food_safety` | Boolean (AI-graded) | Validator LLM (gpt-oss:20b-cloud) checks for missing safety steps (internal temps, cross-contamination, raw-egg risk, produce washing). | `1` (true) | LLM judgment |
| 5 | `nutritional_honesty` | 1–5 scale (grounded) | Normalized RMSE between live USDA macro estimate and USDA RAG estimate for the ingredient list. Lower RMSE → higher score. | `≥ 4.0` | USDA FoodData Central + `data/food_data.json` |
| 6 | `reproducibility` | 0–1 composite | Per step: mean of (has-number, has-unit, has-action-verb). Averaged over all instruction steps. | `≥ 0.80` | Recipe text |
| 7 | `cultural_plausibility` | 1–7 Likert (AI-graded) | Same LLM call as #4; rates coherence of ingredients + technique against the named cuisine for the requested dish. | mean `≥ 5.0` per prompt cohort | LLM judgment |

**Composite:** Each dimension is normalized to `[0, 1]` (see `validator.py:_normalize`), averaged with equal weights (`1/7` each in `DIMENSION_WEIGHTS`), then scaled to `0–100`.

---

## How this differs from the LAB Likert scales

The reference LAB (`09_text_analysis/LAB_ai_quality_control.md`) uses six **generic 1–5 Likert scales** scored by a single LLM call: `accuracy`, `formality`, `faithfulness`, `clarity`, `succinctness`, `relevance`. All six are *opinion-typed* (the model rates subjective text properties) and all use the same scale.

This validator deliberately departs from that design in four ways:

1. **Recipe-specific dimensions, not generic prose dimensions.** `dish_name_match`, `technique_specificity`, `food_safety`, and `nutritional_honesty` are concepts that only make sense for *recipes*. They wouldn't translate to validating, say, a news report. Generic Likerts can't catch a fluent recipe that omits cooking poultry to safe temperature; `food_safety` can.

2. **Mixed measurement types.** Three dimensions (1, 2, 3, 6) are **fully deterministic** Python regex / set-operation checks, which means re-running the validator on the same recipe always produces the same score. Two (4, 7) are AI-graded. One (5) is **grounded** in a real-world reference dataset (USDA). This mix reduces LLM-judge variance and gives reviewers measurements they can audit by hand.

3. **Non-uniform scales.** We use a boolean (1), a percentage (2), a 0–5 count (3), a boolean (4), a 1–5 score (5), a 0–1 composite (6), and a **1–7 Likert** (7). Heterogeneous scales prevent the validator from collapsing into one-dimensional "how good does this look?" and give each dimension space to vary.

4. **One LLM call covers two AI-graded items.** The LAB makes one call per Likert; our validator bundles `food_safety` + `cultural_plausibility` into a single Ollama call (see `_VALIDATOR_PROMPT_TEMPLATE` in `validator.py`). This cuts API cost roughly in half for the AI-graded portion.

---

## Why these weights

All 7 dimensions are weighted equally (`1/7` each) in the composite. We chose equal weights for HW3 to keep the analysis defensible: any unequal scheme would need its own justification (and probably a separate sensitivity analysis). Reviewers who disagree can edit `DIMENSION_WEIGHTS` in `validator.py` and re-run `run_validation.py --rebuild` → `analyze.py` without touching anything else.
