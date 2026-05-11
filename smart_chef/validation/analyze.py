# analyze.py
# Smart Chef validation – statistical analysis for HOMEWORK3
# Pairs with run_validation.py
#
# Pipeline (matches HW3 doc rubric: "Statistical Analysis"):
#   1. Descriptives             — mean/std per prompt + per dimension
#   2. Bartlett's test          — homogeneity of variance
#   3. ANOVA (one-way / Welch)  — overall_score ~ prompt_id
#   4. Pairwise t-tests         — Holm-corrected A/B/C
#   5. Per-dimension ANOVAs     — which dimensions differ?
#   6. OLS regression           — overall_score ~ prompt_id + C(ingredient_set_id)
#   7. Plots                    — boxplot + per-dimension grouped bar chart
#
# Usage (from repo root):
#   python smart_chef/validation/analyze.py

# 0. Setup #################################

## 0.1 Imports ############################

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend so we can save PNGs in any env
import matplotlib.pyplot as plt
import pandas as pd
import pingouin as pg
import statsmodels.formula.api as smf
from scipy.stats import bartlett


## 0.2 Paths ############################

_script_dir = Path(__file__).resolve().parent
DATA_DIR = _script_dir / "data"
OUT_DIR = _script_dir / "outputs"
SCORES_PATH = DATA_DIR / "scores.csv"

DIMENSION_COLS = [
    "dish_name_match",
    "ingredient_faithfulness",
    "technique_specificity",
    "food_safety",
    "nutritional_honesty",
    "reproducibility",
    "cultural_plausibility",
]


# 1. Helpers #################################


def banner(title: str) -> None:
    """Print a heavy rule line + title."""
    print("\n" + "=" * 70)
    print(f"📊 {title}")
    print("=" * 70)


def write_text(path: Path, text: str) -> None:
    """Write a file and echo its path so we have an audit trail."""
    path.write_text(text)
    print(f"   💾 wrote {path}")


# 2. Analysis Steps #################################


def step_descriptives(scores: pd.DataFrame) -> str:
    """Mean ± SD by prompt for overall + per dimension. Returns a text block."""
    banner("Step 1 — Descriptive statistics")
    cols = ["overall_score"] + DIMENSION_COLS

    summary = scores.groupby("prompt_id")[cols].agg(["mean", "std"]).round(2)
    print(summary)

    overall_mean = scores["overall_score"].mean()
    text = []
    text.append("DESCRIPTIVES — mean ± std by prompt (and overall)\n")
    text.append(summary.to_string())
    text.append(f"\n\nOverall mean across all prompts: {overall_mean:.2f}\n")
    return "\n".join(text)


def step_bartlett(scores: pd.DataFrame) -> tuple[float, float, bool]:
    """Bartlett's test for equal variance of overall_score across prompts."""
    banner("Step 2 — Bartlett's test for homogeneity of variance")
    groups = [scores.query(f'prompt_id == "{p}"')["overall_score"]
              for p in sorted(scores["prompt_id"].unique())]
    stat, pval = bartlett(*groups)
    var_equal = bool(pval >= 0.05)
    print(f"   stat = {stat:.4f}, p = {pval:.4f}")
    print(f"   Equal variances assumption: "
          f"{'✅ keep' if var_equal else '❌ reject — use Welch ANOVA'}")
    return float(stat), float(pval), var_equal


def step_anova(scores: pd.DataFrame, var_equal: bool) -> pd.DataFrame:
    """One-way ANOVA (or Welch's) on overall_score ~ prompt_id."""
    banner("Step 3 — Omnibus ANOVA on overall_score")
    if var_equal:
        res = pg.anova(dv="overall_score", between="prompt_id", data=scores, detailed=True)
        print("   (Standard one-way ANOVA, equal variances assumed)")
    else:
        res = pg.welch_anova(dv="overall_score", between="prompt_id", data=scores)
        print("   (Welch's ANOVA, unequal variances)")
    print(res.to_string(index=False))
    return res


def step_pairwise(scores: pd.DataFrame) -> pd.DataFrame:
    """Pairwise t-tests with Holm correction between prompts."""
    banner("Step 4 — Pairwise t-tests (Holm-corrected)")
    res = pg.pairwise_tests(
        data=scores,
        dv="overall_score",
        between="prompt_id",
        padjust="holm",
        effsize="cohen",
    )
    print(res.to_string(index=False))
    return res


def _get_pingouin_col(df: pd.DataFrame, *names: str) -> float:
    """Return the first matching column's first value as float; NaN if none match.

    Pingouin renamed columns between versions (e.g. 'p-unc' -> 'p_unc'),
    so we accept either form.
    """
    for n in names:
        if n in df.columns:
            try:
                return float(df[n].values[0])
            except (TypeError, ValueError):
                return float("nan")
    return float("nan")


def step_per_dimension(scores: pd.DataFrame) -> pd.DataFrame:
    """Run one ANOVA per dimension; collect F and p side-by-side."""
    banner("Step 5 — Per-dimension ANOVAs")
    rows = []
    for dim in DIMENSION_COLS:
        if scores[dim].nunique() <= 1:
            rows.append({"dimension": dim, "F": float("nan"), "p_unc": float("nan"),
                         "note": "constant — no variance"})
            continue
        # Check within-group variance: Welch's ANOVA needs >0 variance in every group.
        within_var_ok = all(
            scores.query(f'prompt_id == "{p}"')[dim].nunique() > 1
            for p in scores["prompt_id"].unique()
        )
        try:
            if within_var_ok:
                res = pg.welch_anova(dv=dim, between="prompt_id", data=scores)
            else:
                # Fall back to standard ANOVA when at least one group has no variance.
                res = pg.anova(dv=dim, between="prompt_id", data=scores, detailed=True)
            f_val = _get_pingouin_col(res, "F")
            p_val = _get_pingouin_col(res, "p-unc", "p_unc")
            rows.append({
                "dimension": dim,
                "F": round(f_val, 4) if pd.notna(f_val) else float("nan"),
                "p_unc": round(p_val, 4) if pd.notna(p_val) else float("nan"),
                "note": "" if within_var_ok else "fallback: standard ANOVA (one group has no variance)",
            })
        except Exception as e:  # noqa: BLE001
            rows.append({"dimension": dim, "F": float("nan"), "p_unc": float("nan"),
                         "note": f"error: {e}"})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    return df


def step_regression(scores: pd.DataFrame) -> str:
    """OLS: overall_score ~ C(prompt_id) + C(ingredient_set_id)."""
    banner("Step 6 — OLS regression with ingredient-set control")
    # Drop ingredient_set_id from formula if there's only one level (e.g., smoke run)
    has_multi_set = scores["ingredient_set_id"].nunique() > 1
    formula = "overall_score ~ C(prompt_id)"
    if has_multi_set:
        formula += " + C(ingredient_set_id)"
    else:
        print("   (only 1 ingredient set — dropping that term)")
    model = smf.ols(formula, data=scores).fit()
    summary = model.summary().as_text()
    print(summary)
    return summary


# 3. Plots #################################


def plot_boxplot(scores: pd.DataFrame, out_path: Path) -> None:
    """Boxplot of overall_score by prompt."""
    fig, ax = plt.subplots(figsize=(7, 5))
    prompts = sorted(scores["prompt_id"].unique())
    data = [scores.query(f'prompt_id == "{p}"')["overall_score"].values for p in prompts]
    ax.boxplot(data, tick_labels=[f"Prompt {p}" for p in prompts], showmeans=True)
    ax.set_ylabel("Overall validation score (0–100)")
    ax.set_title("Overall validation score by prompt")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"   🎨 wrote {out_path}")


def plot_per_dimension_bar(scores: pd.DataFrame, out_path: Path) -> None:
    """Grouped bar chart: mean per dimension, one bar group per prompt."""
    means = scores.groupby("prompt_id")[DIMENSION_COLS].mean()
    # Normalize each dimension to 0..1 so bars are comparable.
    # (Same normalization the composite uses in validator.py:_normalize.)
    norm = means.copy()
    norm["ingredient_faithfulness"] /= 100.0
    norm["technique_specificity"] /= 5.0
    norm["nutritional_honesty"] = (norm["nutritional_honesty"] - 1) / 4
    norm["cultural_plausibility"] = (norm["cultural_plausibility"] - 1) / 6
    # dish_name_match, food_safety, reproducibility already in 0..1

    fig, ax = plt.subplots(figsize=(11, 5))
    prompts = sorted(norm.index.tolist())
    x = range(len(DIMENSION_COLS))
    width = 0.8 / max(len(prompts), 1)
    for i, p in enumerate(prompts):
        ax.bar([xi + i * width for xi in x], norm.loc[p].values, width=width, label=f"Prompt {p}")
    ax.set_xticks([xi + width * (len(prompts) - 1) / 2 for xi in x])
    ax.set_xticklabels(DIMENSION_COLS, rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Normalized score (0–1)")
    ax.set_title("Per-dimension mean by prompt")
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"   🎨 wrote {out_path}")


# 4. Main #################################


def main() -> int:
    print("=" * 70)
    print("📋 Smart Chef – Statistical analysis of validation scores")
    print(f"   Scores in:  {SCORES_PATH}")
    print(f"   Outputs:    {OUT_DIR}")
    print("=" * 70)

    if not SCORES_PATH.exists():
        print(f"❌ scores.csv not found. Run run_validation.py first.")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scores = pd.read_csv(SCORES_PATH)
    print(f"📦 Loaded {len(scores)} rows × {len(scores.columns)} columns")
    if scores.empty:
        print("⚠️ scores.csv is empty.")
        return 0
    print(f"   Prompts: {sorted(scores['prompt_id'].unique().tolist())}")
    print(f"   Sets:    {sorted(scores['ingredient_set_id'].unique().tolist())}")
    print(f"   n per prompt: {scores.groupby('prompt_id').size().to_dict()}")

    # Run each step and stitch text outputs into one report file
    text_blocks = []
    text_blocks.append(step_descriptives(scores))

    b_stat, b_p, var_equal = step_bartlett(scores)
    text_blocks.append(f"BARTLETT'S TEST\n  statistic={b_stat:.4f}, p={b_p:.4f}, "
                       f"equal_var={var_equal}\n")

    anova_res = step_anova(scores, var_equal)
    text_blocks.append("OMNIBUS ANOVA on overall_score ~ prompt_id\n"
                       + anova_res.to_string(index=False) + "\n")

    pw_res = step_pairwise(scores)
    text_blocks.append("PAIRWISE T-TESTS (Holm-corrected)\n"
                       + pw_res.to_string(index=False) + "\n")

    per_dim = step_per_dimension(scores)
    text_blocks.append("PER-DIMENSION ANOVAS\n"
                       + per_dim.to_string(index=False) + "\n")

    write_text(OUT_DIR / "anova_table.txt", "\n\n".join(text_blocks))

    reg_summary = step_regression(scores)
    write_text(OUT_DIR / "regression_summary.txt", reg_summary)

    # Plots
    banner("Step 7 — Plots")
    plot_boxplot(scores, OUT_DIR / "boxplot_overall.png")
    plot_per_dimension_bar(scores, OUT_DIR / "per_dimension_bar.png")

    # Final summary block
    print("\n" + "=" * 70)
    print("📊 Analysis summary")
    print(f"   📄 anova_table.txt        → {OUT_DIR / 'anova_table.txt'}")
    print(f"   📄 regression_summary.txt → {OUT_DIR / 'regression_summary.txt'}")
    print(f"   🎨 boxplot_overall.png    → {OUT_DIR / 'boxplot_overall.png'}")
    print(f"   🎨 per_dimension_bar.png  → {OUT_DIR / 'per_dimension_bar.png'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
