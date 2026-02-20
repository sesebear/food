# api_utils.py
# FDA Food Adverse Event API – fetch helpers for Shiny app
# Pairs with 02_productivity/shiny_app (FDA Food Event Shiny app)
# Tim Fraser

# Helper functions for calling the openFDA Food Event API.
# Used by app.py to run queries on user request with consistent error handling.

import requests

BASE_URL = "https://api.fda.gov/food/event.json"


def fetch_fda_events(search: str, sort: str, limit: int, api_key: str | None) -> tuple[dict | None, str | None]:
    """
    Query the openFDA Food Adverse Event Reports API.

    Parameters
    ----------
    search : str
        Search filter, e.g. "Cosmetics" (will be used as products.industry_name:<value>).
    sort : str
        Sort order, e.g. "date_created:desc".
    limit : int
        Max records to return (1–1000).
    api_key : str | None
        Optional API key for higher rate limits.

    Returns
    -------
    tuple[dict | None, str | None]
        (response_json, error_message). On success, response_json has "meta" and "results";
        error_message is None. On failure, response_json is None and error_message is set.
    """
    if not search or not search.strip():
        return None, "Please enter an industry name (e.g. Cosmetics)."

    search_clean = search.strip()
    # Build API search expression for product industry name.
    search_expr = f'products.industry_name:"{search_clean}"'

    params = {
        "search": search_expr,
        "sort": sort,
        "limit": min(max(1, limit), 1000),
    }
    if api_key and api_key.strip():
        params["api_key"] = api_key.strip()

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return None, "Request timed out. Check your network and try again."
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            return None, f"HTTP error: {e.response.status_code} – {e.response.reason}"
        return None, "An HTTP error occurred."
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {e}"

    try:
        data = response.json()
    except ValueError:
        return None, "Invalid JSON in API response."

    # API can return {"error": {...}} for bad queries.
    if "error" in data:
        msg = data["error"].get("message", "Unknown API error.")
        return None, msg

    return data, None
