# Food – FDA Adverse Event API

Scripts and labs for querying the openFDA Food Adverse Event Reports API. Fetch filtered adverse event reports (e.g. by product industry), sorted by date, for analysis or reporting. Built for systems engineering coursework; usable from the repo as standalone Python.

---

## Tech stack

| Layer     | Technology |
|----------|------------|
| Language | Python 3.10+ |
| HTTP     | `requests` |
| Env      | `python-dotenv`, `.env` for optional API key |
| API      | [ fatsecret Platform REST API](https://platform.fatsecret.com/rest/) |

---

## Installation

Assumes a fresh environment (no prior clone or venv).

1. **Prerequisites**: Python 3.10+, Git.
2. **Clone**:
   ```bash
   git clone <repo-url>
   cd <repo-name>
   ```
3. **Python deps**:
   ```bash
   pip install requests python-dotenv
   ```
4. **Optional – API key**: openFDA allows higher rate limits with a key. In `01_query_api/` create a `.env` file and set `API_KEY=your_openfda_key`. Register at [openFDA API key](https://open.fda.gov/apis/authentication/). The script runs without a key at lower limits.

---

## Usage

From the repo root, run the Food Event query (filter: Cosmetics industry, 20 records, newest first). Output is printed to stdout.

```bash
python 01_query_api/my_good_query.py
```

You get a short summary (total matching, count returned) and a numbered list of records with `report_number`, `date_created`, outcomes, reactions, and product names. See [`my_good_query.py`](my_good_query.py) and [README_my_good_query.md](../02_productivity/README_my_good_query.md) for endpoint details and data structure.

---

See [LAB_your_good_api_query.md](LAB_your_good_api_query.md) for the lab that goes with this script.
