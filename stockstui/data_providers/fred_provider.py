import requests
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple

BASE_URL = "https://api.stlouisfed.org/fred"
_series_cache: Dict[str, Any] = {}
_info_cache: Dict[str, Any] = {}
CACHE_DURATION_SECONDS = 300  # 5 minutes

# ASSUMPTION: 3000 observations covers 10+ years of daily data (~2520 trading days)
# and plenty for weekly (520), monthly (120), or quarterly (40).
OBSERVATION_LIMIT = 3000

def get_series_observations(series_id: str, api_key: str, limit: int = OBSERVATION_LIMIT) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches observations for a specific FRED series.
    Returns observations in descending order (newest first).
    """
    if not api_key:
        logging.error("FRED API key is missing.")
        return None

    series_id = series_id.upper()
    now = datetime.now(timezone.utc)

    # Note: We omit limit from cache key for simplicity under the assumption 
    # that we always request the same "10-year" optimized amount for a given series.
    if series_id in _series_cache:
        timestamp, data = _series_cache[series_id]
        if (now - timestamp).total_seconds() < CACHE_DURATION_SECONDS:
            # If cache has enough data, return it
            if len(data) >= limit:
                return data

    try:
        url = f"{BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",  # Get latest data first
            "limit": limit
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


def detect_frequency(observations: List[Dict[str, Any]]) -> str:
    """
    Infer frequency from observation dates.

    Returns:
        'M' for monthly, 'Q' for quarterly, 'D' for daily, 'A' for annual
    """
    if len(observations) < 2:
        return "M"  # Default to monthly

    try:
        # Parse the first few dates to determine frequency
        dates = []
        for obs in observations[:10]:  # Look at first 10 observations
            date_obj = datetime.strptime(obs["date"], "%Y-%m-%d")
            dates.append(date_obj)

        if len(dates) < 2:
            return "M"

        # Calculate differences between consecutive dates
        diffs = []
        for i in range(1, len(dates)):
            diff = abs((dates[i] - dates[i-1]).days)
            diffs.append(diff)

        # Calculate average difference
        avg_diff = sum(diffs) / len(diffs)

        # Classify based on average difference
        if avg_diff < 2:  # Less than 2 days - daily
            return "D"
        elif avg_diff < 15:  # Less than 15 days - weekly
            return "W"
        elif avg_diff < 45:  # Less than 45 days - monthly
            return "M"
        elif avg_diff < 135:  # Less than 135 days - quarterly
            return "Q"
        else:  # More than 135 days - annual
            return "A"
    except Exception:
        # Default to monthly for ambiguous cases
        return "M"

def compute_enhanced_metrics(
    observations: List[Dict[str, Any]],
    frequency: str = "M",
    short_months: int = 12,
    long_months: int = 24,
    z_lookback_years: int = 10,
) -> Dict[str, Any]:
    """
    Compute advanced metrics from observation data.

    Args:
        observations: List of observations in descending order (newest first)
        frequency: 'M' for monthly, 'Q' for quarterly
        short_months: Lookback for short rolling window (default 12)
        long_months: Lookback for long rolling window (default 24)
        z_lookback_years: Years of data for z-score calculation (default 10)

    Returns:
        Dict with: yoy_pct, roll_12, roll_24, z_10y, hist_min_10y, hist_max_10y, pct_of_range
    """
    metrics: Dict[str, Any] = {
        "yoy_pct": None,
        "roll_12": None,
        "roll_24": None,
        "z_10y": None,
        "hist_min_10y": None,
        "hist_max_10y": None,
        "pct_of_range": None,
    }

    if not observations:
        return metrics

    # Extract numeric values, converting '.' (FRED's N/A) to NaN
    values = []
    for obs in observations:
        val_str = obs["value"]
        if val_str == ".":
            values.append(np.nan)
        else:
            try:
                values.append(float(val_str))
            except (ValueError, TypeError):
                values.append(np.nan)

    # Check if we have valid data
    if not values or all(np.isnan(v) for v in values):
        return metrics

    current = values[0]
    values_arr = np.array(values)

    # Determine period counts based on frequency
    if frequency == "Q":
        short_periods = max(1, short_months // 3)  # 4 quarters for 12 months
        long_periods = max(2, long_months // 3)    # 8 quarters for 24 months
        z_periods = z_lookback_years * 4            # Quarters in lookback
    elif frequency == "A":
        short_periods = 1
        long_periods = 2
        z_periods = z_lookback_years
    elif frequency == "W":
        # Weekly data
        short_periods = 52 # 1 year
        long_periods = 104 # 2 years
        z_periods = z_lookback_years * 52
    elif frequency == "D":
        # Daily data (approx 260 trading days)
        short_periods = 260 # 1 year
        long_periods = 520 # 2 years
        z_periods = z_lookback_years * 260
    else:  # Monthly or default
        short_periods = short_months
        long_periods = long_months
        z_periods = z_lookback_years * 12

    # YoY percent change: (current - value_1y_ago) / value_1y_ago * 100
    if len(values_arr) > short_periods:
        yoy_val = values_arr[short_periods]
        if not np.isnan(yoy_val) and yoy_val != 0:
            metrics["yoy_pct"] = ((current - yoy_val) / abs(yoy_val)) * 100

    # Rolling 12 (short) average
    if len(values_arr) >= short_periods:
        valid_values = values_arr[:short_periods][~np.isnan(values_arr[:short_periods])]
        if len(valid_values) > 0:
            metrics["roll_12"] = float(np.mean(valid_values))

    # Rolling 24 (long) average
    if len(values_arr) >= long_periods:
        valid_values = values_arr[:long_periods][~np.isnan(values_arr[:long_periods])]
        if len(valid_values) > 0:
            metrics["roll_24"] = float(np.mean(valid_values))

    # Z-score using 10-year lookback mean and std
    lookback_end = min(len(values_arr), z_periods)
    if lookback_end >= 4:  # Need at least 4 observations for meaningful stats
        lookback_values = values_arr[:lookback_end]
        valid_lookback = lookback_values[~np.isnan(lookback_values)]
        if len(valid_lookback) >= 4:
            lookback_mean = np.mean(valid_lookback)
            lookback_std = np.std(valid_lookback)
            if lookback_std != 0:
                metrics["z_10y"] = (current - lookback_mean) / lookback_std

    # Historical min/max for 10-year range
    if lookback_end >= 4:
        valid_lookback = values_arr[:lookback_end][~np.isnan(values_arr[:lookback_end])]
        if len(valid_lookback) >= 4:
            metrics["hist_min_10y"] = float(np.min(valid_lookback))
            metrics["hist_max_10y"] = float(np.max(valid_lookback))

            # Calculate % of range: (current - min) / (max - min) * 100
            hist_range = metrics["hist_max_10y"] - metrics["hist_min_10y"]
            if hist_range != 0:
                metrics["pct_of_range"] = ((current - metrics["hist_min_10y"]) / hist_range) * 100

    return metrics


def get_series_info(series_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetches metadata for a specific FRED series.
    Returns info dict with title, units, frequency, seasonal_adjustment, etc.
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
    Calculates comprehensive summary statistics for a FRED series.

    Returns dict with:
        - Basic info: id, title, current, date, units
        - Enhanced metrics: yoy_pct, roll_12, roll_24, z_10y, hist_min_10y, hist_max_10y, pct_of_range
        - Metadata: frequency, seasonal_adj
    """
    # Initialize with default structure
    summary: Dict[str, Any] = {
        "id": series_id,
        "title": series_id,
        "current": "N/A",
        "date": "N/A",
        "units": "",
        "units_short": "",
        "frequency": "M",
        "seasonal_adj": "",
        # Enhanced metrics
        "yoy_pct": None,
        "roll_12": None,
        "roll_24": None,
        "z_10y": None,
        "hist_min_10y": None,
        "hist_max_10y": None,
        "pct_of_range": None,
        # Legacy fields
        "change_1p": "N/A", # 1 period change (vs prev)
        "change_1y": "N/A",
        "change_5y": "N/A"
    }

    info = get_series_info(series_id, api_key)
    
    # Calculate tailored limit based on frequency to optimize data fetching
    # We want ~10 years of data plus a small buffer (11 years)
    tailored_limit = 132 # Default fallback (Monthly)
    
    if info:
        summary["title"] = info.get("title", series_id)
        summary["units"] = info.get("units") or ""
        summary["units_short"] = info.get("units_short") or ""

        # Parse frequency from info (FRED uses codes like 'Monthly', 'Quarterly', etc.)
        freq_str = info.get("frequency", "").lower()
        if "quarterly" in freq_str:
            summary["frequency"] = "Q"
            tailored_limit = 4 * 11
        elif "annual" in freq_str:
            summary["frequency"] = "A"
            tailored_limit = 15
        elif "daily" in freq_str:
            summary["frequency"] = "D"
            tailored_limit = 260 * 11 # ~2860
        elif "weekly" in freq_str:
            summary["frequency"] = "W"
            tailored_limit = 52 * 11 # ~572
        else:
            summary["frequency"] = "M"
            tailored_limit = 12 * 11 # 132

        # Seasonal adjustment status
        sa_str = info.get("seasonal_adjustment_short") or info.get("seasonal_adjustment") or ""
        if "seasonally adjusted" in sa_str.lower():
            summary["seasonal_adj"] = "SA"

    # Now fetch observations with optimized limit
    obs_list = get_series_observations(series_id, api_key, limit=tailored_limit)

    if not obs_list:
        return summary

    try:
        # Detect frequency from observations if not determined from metadata
        detected_freq = detect_frequency(obs_list)
        if summary["frequency"] == "M":  # Use detected if metadata wasn't definitive
            summary["frequency"] = detected_freq

        # Get current value and date (Obs List is desc, newest first)
        current_obs = obs_list[0]
        if current_obs["value"] != ".":
            summary["current"] = float(current_obs["value"])
            summary["date"] = current_obs["date"]
        else:
            summary["current"] = "N/A"
            summary["date"] = current_obs["date"]

        # Previous (1 period)
        if len(obs_list) > 1 and summary["current"] != "N/A":
            prev_obs = obs_list[1]
            try:
                prev_val = float(prev_obs["value"]) if prev_obs["value"] != "." else 0
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
        current_date_obj = datetime.strptime(current_obs["date"], "%Y-%m-%d")
        target_1y = current_date_obj.replace(year=current_date_obj.year - 1)
        obs_1y = find_closest_past(target_1y)
        if obs_1y and summary["current"] != "N/A":
            try:
                val_1y = float(obs_1y["value"]) if obs_1y["value"] != "." else 0
                summary["change_1y"] = summary["current"] - val_1y
            except (ValueError, TypeError):
                pass

        # 5 Year Ago
        target_5y = current_date_obj.replace(year=current_date_obj.year - 5)
        obs_5y = find_closest_past(target_5y)
        if obs_5y and summary["current"] != "N/A":
            try:
                val_5y = float(obs_5y["value"]) if obs_5y["value"] != "." else 0
                summary["change_5y"] = summary["current"] - val_5y
            except (ValueError, TypeError):
                pass

        # Compute enhanced metrics
        enhanced = compute_enhanced_metrics(
            obs_list,
            frequency=summary["frequency"],
            short_months=12,
            long_months=24,
            z_lookback_years=10
        )
        summary.update(enhanced)

        return summary
    except Exception as e:
        logging.error(f"Error calculating summary for {series_id}: {e}")
        return summary
