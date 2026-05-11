# run_validation.py
# Smart Chef validation – score every generated report
# Pairs with validator.py, generate_reports.py, analyze.py
#
# For every record in `data/reports.jsonl`, runs the 7-dimension validator and
# appends the result to `data/scores.csv`. Idempotent: re-runs skip rows that
# are already scored (matched on prompt_id + ingredient_set_id + run).
#
# Usage (from repo root):
#   python smart_chef/validation/run_validation.py
#   python smart_chef/validation/run_validation.py --rebuild   # ignore existing scores
#   python smart_chef/validation/run_validation.py --limit 6   # smoke-test mode

# 0. Setup #################################

## 0.1 Imports ############################

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Make smart_chef/ importable
_SMART_CHEF_DIR = Path(__file__).resolve().parent.parent
if str(_SMART_CHEF_DIR) not in sys.path:
    sys.path.insert(0, str(_SMART_CHEF_DIR))

from validation.validator import validate_report, OLLAMA_API_KEY


## 0.2 Paths ############################

_script_dir = Path(__file__).resolve().parent
DATA_DIR = _script_dir / "data"
REPORTS_PATH = DATA_DIR / "reports.jsonl"
SCORES_PATH = DATA_DIR / "scores.csv"


# 1. Helpers #################################


def load_reports(path: Path) -> list[dict]:
    """Read the JSONL file into a list of records, skipping malformed lines."""
    if not path.exists():
        return []
    out = []
    with open(path, "r") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def load_existing_scores(path: Path) -> pd.DataFrame:
    """Load previously computed scores, or an empty frame with the right columns."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return pd.DataFrame()


def already_scored_keys(df: pd.DataFrame) -> set[tuple[str, str, int]]:
    """Return the set of (set_id, prompt_id, run) cells already in scores.csv."""
    if df.empty or not {"ingredient_set_id", "prompt_id", "run"}.issubset(df.columns):
        return set()
    return set(zip(
        df["ingredient_set_id"].astype(str),
        df["prompt_id"].astype(str),
        df["run"].astype(int),
    ))


# 2. Main #################################


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score Smart Chef validation reports.")
    p.add_argument("--rebuild", action="store_true",
                   help="Re-score every report (delete existing scores.csv first).")
    p.add_argument("--limit", type=int, default=None,
                   help="Hard cap on how many new reports to score this run.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 70)
    print("📋 Smart Chef – Validate reports (7 dimensions)")
    print(f"   Reports:  {REPORTS_PATH}")
    print(f"   Scores:   {SCORES_PATH}")
    print(f"   Rebuild:  {args.rebuild}")
    print(f"   Limit:    {args.limit if args.limit else 'no cap'}")
    print("=" * 70)

    if not OLLAMA_API_KEY:
        print("❌ OLLAMA_API_KEY not set in .env. Aborting.")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    reports = load_reports(REPORTS_PATH)
    print(f"📦 Loaded {len(reports)} reports from JSONL")
    if not reports:
        print("⚠️ No reports to score. Run generate_reports.py first.")
        return 0

    if args.rebuild and SCORES_PATH.exists():
        SCORES_PATH.unlink()
        print("   🧹 Deleted existing scores.csv (--rebuild).")

    existing = load_existing_scores(SCORES_PATH)
    done = already_scored_keys(existing)
    if done:
        print(f"   ↪ Skipping {len(done)} reports already in scores.csv (use --rebuild to redo).")

    rows: list[dict] = []
    n_scored = 0
    for rec in tqdm(reports, desc="scoring"):
        key = (rec.get("ingredient_set_id"), rec.get("prompt_id"), int(rec.get("run", 0)))
        if key in done:
            continue
        if args.limit is not None and n_scored >= args.limit:
            print(f"   ⛔ Hit --limit={args.limit}, stopping early.")
            break

        try:
            score = validate_report(
                recipe_text=rec["recipe_text"],
                dish_name=rec["dish_name"],
                user_ingredients=rec["ingredients"],
            )
        except Exception as e:  # noqa: BLE001
            tqdm.write(f"   ❌ {key}: {e}")
            continue

        rows.append({
            "ingredient_set_id": rec["ingredient_set_id"],
            "stratum":           rec.get("stratum", ""),
            "prompt_id":         rec["prompt_id"],
            "run":               int(rec["run"]),
            "dish_name":         rec["dish_name"],
            **score,
        })
        n_scored += 1

    # Combine and write
    new_df = pd.DataFrame(rows)
    if not new_df.empty:
        combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        combined = combined.sort_values(["ingredient_set_id", "prompt_id", "run"])
        combined.to_csv(SCORES_PATH, index=False)

    final = load_existing_scores(SCORES_PATH)
    print("=" * 70)
    print("📊 Validation summary")
    print(f"   ✅ Newly scored : {n_scored}")
    print(f"   📦 Total rows   : {len(final)}")
    print(f"   📄 Path         : {SCORES_PATH}")
    if not final.empty:
        print(f"   Shape: {final.shape}")
        cols = ["ingredient_set_id", "prompt_id", "run", "overall_score"]
        print("   Preview:")
        print(final[cols].head(5).to_string(index=False))
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
