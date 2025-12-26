import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

BASE_URL = "https://api.stlouisfed.org/fred"
_series_cache: Dict[str, Any] = {}
_info_cache: Dict[str, Any] = {}
CACHE_DURATION_SECONDS = 300  # 5 minutes

def get_series_observations(series_id: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches observations for a specific FRED series.
    """
    if not api_key:
        logging.error("FRED API key is missing.")
        return None
    
    series_id = series_id.upper()
    now = datetime.now(timezone.utc)
    
    if series_id in _series_cache:
        timestamp, data = _series_cache[series_id]
        if (now - timestamp).total_seconds() < CACHE_DURATION_SECONDS:
            return data

    try:
        url = f"{BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc", # Get latest data first
            "limit": 100 # Limit to last 100 observations to keep it light but cover 5+ years (if not daily)
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        observations = data.get("observations", [])
        _series_cache[series_id] = (now, observations)
        return observations
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching FRED series {series_id}: {e}")
        return None

def get_series_info(series_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetches metadata for a specific FRED series.
    """
    if not api_key:
        return None
        
    if series_id in _info_cache:
        return _info_cache[series_id]

    try:
        url = f"{BASE_URL}/series"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        series_list = data.get("seriess", [])
        if series_list:
            _info_cache[series_id] = series_list[0]
            return series_list[0]
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching FRED series info {series_id}: {e}")
        return None

def search_series(search_text: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Searches for FRED series by text.
    """
    if not api_key:
        logging.error("FRED API key is missing.")
        return []

    try:
        url = f"{BASE_URL}/series/search"
        params = {
            "search_text": search_text,
            "api_key": api_key,
            "file_type": "json",
            "limit": 20
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("seriess", [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error searching FRED series '{search_text}': {e}")
        return []

def get_series_summary(series_id: str, api_key: str) -> Dict[str, Any]:
    """
    Calculates summary statistics for a series (Current, Change, YoY, 5Y).
    """
    # Initialize with default structure
    summary = {
        "id": series_id,
        "title": series_id,
        "current": "N/A",
        "date": "N/A",
        "units": "",
        "change_1p": "N/A", # 1 period change (vs prev)
        "change_1y": "N/A",
        "change_5y": "N/A"
    }

    obs_list = get_series_observations(series_id, api_key)
    info = get_series_info(series_id, api_key)
    
    if info:
        summary["title"] = info.get("title", series_id)
        summary["units"] = info.get("units_short") or info.get("units") or ""

    if not obs_list:
        return summary

    try:
        # Obs List is desc (newest first)
        current_obs = obs_list[0]
        summary["current"] = float(current_obs["value"]) if current_obs["value"] != "." else "N/A"
        summary["date"] = current_obs["date"]
        current_date_obj = datetime.strptime(current_obs["date"], "%Y-%m-%d")

        # Previous (1 period)
        if len(obs_list) > 1:
            prev_obs = obs_list[1]
            try:
                prev_val = float(prev_obs["value"])
                if isinstance(summary["current"], float):
                    summary["change_1p"] = summary["current"] - prev_val
            except (ValueError, TypeError):
                pass

        # Helper to find closest date (looking back)
        def find_closest_past(target_date):
            for obs in obs_list:
                try:
                    d = datetime.strptime(obs["date"], "%Y-%m-%d")
                    # allowed slack: within 30 days for 1Y/5Y comparison?
                    # Actually, for macro data, we usually just want the observation "about 1 year ago"
                    # Simple approach: minimize absolute difference in days
                    if abs((d - target_date).days) < 45: # Close enough match (monthly data usually)
                         return obs
                except ValueError: continue
            return None

        # 1 Year Ago
        target_1y = current_date_obj.replace(year=current_date_obj.year - 1)
        obs_1y = find_closest_past(target_1y)
        if obs_1y:
            try:
                val_1y = float(obs_1y["value"])
                if isinstance(summary["current"], float):
                    summary["change_1y"] = summary["current"] - val_1y
            except (ValueError, TypeError): pass

        # 5 Years Ago
        target_5y = current_date_obj.replace(year=current_date_obj.year - 5)
        obs_5y = find_closest_past(target_5y)
        if obs_5y:
             try:
                val_5y = float(obs_5y["value"])
                if isinstance(summary["current"], float):
                    summary["change_5y"] = summary["current"] - val_5y
             except (ValueError, TypeError): pass

    except (ValueError, IndexError) as e:
        logging.error(f"Error calculating summary for {series_id}: {e}")

    return summary
