# generate_reports.py
# Smart Chef validation – generate the experimental corpus of AI recipes
# Pairs with prompts.py, run_validation.py
#
# Loops the experiment grid: 5 ingredient sets x 3 prompt variants x 2 reps
# = 30 recipes. Each result is appended as one JSON line to
# `validation/data/reports.jsonl` so the file is resumable and append-only.
#
# Usage (from repo root):
#   python smart_chef/validation/generate_reports.py
#   python smart_chef/validation/generate_reports.py --max-reports 6   # smoke test
#   python smart_chef/validation/generate_reports.py --resume          # skip done cells

# 0. Setup #################################

## 0.1 Imports ############################

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Make smart_chef/ importable
_SMART_CHEF_DIR = Path(__file__).resolve().parent.parent
if str(_SMART_CHEF_DIR) not in sys.path:
    sys.path.insert(0, str(_SMART_CHEF_DIR))

from validation.prompts import build_prompt, PROMPT_IDS


## 0.2 Load Environment ############################

_script_dir = Path(__file__).resolve().parent
_project_root = _SMART_CHEF_DIR.parent
try:
    load_dotenv(_project_root / ".env")
    load_dotenv(_SMART_CHEF_DIR / ".env")
    load_dotenv(_script_dir / ".env")
except OSError:
    pass

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_CHAT_URL = "https://ollama.com/api/chat"
OLLAMA_MODEL = "gpt-oss:20b-cloud"


## 0.3 Paths ############################

DATA_DIR = _script_dir / "data"
SETS_PATH = DATA_DIR / "ingredient_sets.json"
REPORTS_PATH = DATA_DIR / "reports.jsonl"


# 1. Ollama Call #################################


def call_ollama(prompt: str, api_key: str) -> tuple[str | None, str | None]:
    """One Ollama Cloud chat call. Same pattern as ai_utils._call_ollama."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_CHAT_URL, headers=headers, json=body, timeout=180)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", ""), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


# 2. Experiment Plan #################################


def load_ingredient_sets() -> list[dict]:
    """Read the 5 stratified ingredient sets from data/ingredient_sets.json."""
    with open(SETS_PATH, "r") as f:
        return json.load(f)["ingredient_sets"]


def build_plan(sets: list[dict], reps: int) -> list[dict]:
    """Materialize the full set × prompt × rep grid."""
    plan = []
    for s in sets:
        for pid in PROMPT_IDS:
            for r in range(1, reps + 1):
                plan.append({
                    "ingredient_set_id": s["id"],
                    "stratum":           s["stratum"],
                    "dish_name":         s["dish_name"],
                    "ingredients":       s["ingredients"],
                    "prompt_id":         pid,
                    "run":               r,
                })
    return plan


def already_done(path: Path) -> set[tuple[str, str, int]]:
    """Read existing reports.jsonl and return the set of done (set, prompt, run) cells."""
    if not path.exists():
        return set()
    done = set()
    with open(path, "r") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((rec.get("ingredient_set_id"), rec.get("prompt_id"), rec.get("run")))
    return done


# 3. Main #################################


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Smart Chef validation reports.")
    p.add_argument("--reps", type=int, default=2, help="Repetitions per (set, prompt) cell. Default 2.")
    p.add_argument("--max-reports", type=int, default=None,
                   help="Hard cap on number of reports generated this run (smoke-test mode).")
    p.add_argument("--resume", action="store_true",
                   help="Skip (set, prompt, run) cells that already exist in reports.jsonl.")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds between calls (rate-limit guard).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 70)
    print("📋 Smart Chef – Generate validation reports")
    print(f"   Model:    {OLLAMA_MODEL}")
    print(f"   Reports:  {REPORTS_PATH}")
    print(f"   Reps:     {args.reps}")
    print(f"   Max:      {args.max_reports if args.max_reports else 'no cap'}")
    print(f"   Resume:   {args.resume}")
    print("=" * 70)

    if not OLLAMA_API_KEY:
        print("❌ OLLAMA_API_KEY not set in .env. Aborting.")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sets = load_ingredient_sets()
    plan = build_plan(sets, args.reps)
    print(f"📦 Plan: {len(sets)} ingredient sets × {len(PROMPT_IDS)} prompts × "
          f"{args.reps} reps = {len(plan)} reports")

    done = already_done(REPORTS_PATH) if args.resume else set()
    if done:
        print(f"   ↪ Resume: {len(done)} cells already in reports.jsonl, will skip those.")

    n_written = 0
    n_failed = 0
    with open(REPORTS_PATH, "a") as out_f:
        for cell in tqdm(plan, desc="generating"):
            key = (cell["ingredient_set_id"], cell["prompt_id"], cell["run"])
            if key in done:
                continue
            if args.max_reports is not None and n_written >= args.max_reports:
                print(f"   ⛔ Hit --max-reports={args.max_reports}, stopping early.")
                break

            prompt = build_prompt(
                prompt_id=cell["prompt_id"],
                dish_name=cell["dish_name"],
                ingredients=cell["ingredients"],
            )
            text, err = call_ollama(prompt, OLLAMA_API_KEY)
            if err or not text:
                tqdm.write(f"   ❌ {cell['ingredient_set_id']}/{cell['prompt_id']}/run{cell['run']}: {err}")
                n_failed += 1
                continue

            record = {
                **cell,
                "model":        OLLAMA_MODEL,
                "recipe_text":  text,
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()
            n_written += 1
            time.sleep(max(0.0, args.sleep))

    print("=" * 70)
    print("📊 Generation summary")
    print(f"   ✅ Wrote   : {n_written} new reports")
    print(f"   ❌ Failed  : {n_failed}")
    print(f"   📄 Path    : {REPORTS_PATH}")
    print("=" * 70)
    return 0 if n_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
