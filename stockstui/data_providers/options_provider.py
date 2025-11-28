"""
Options data provider for fetching stock options chains using yfinance.
"""
import logging
import time
import yfinance as yf


# Cache for options data with TTL
_options_cache = {}
_expirations_cache = {}
OPTIONS_CACHE_TTL = 600  # 10 minutes in seconds


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still valid based on TTL."""
    if not cache_entry:
        return False
    return (time.time() - cache_entry.get('timestamp', 0)) < OPTIONS_CACHE_TTL


def clear_options_cache(ticker: str | None = None):
    """
    Clear the options cache. If ticker is provided, only clear that ticker's cache.
    
    Args:
        ticker: Optional ticker symbol to clear specific cache, or None to clear all
    """
    global _options_cache, _expirations_cache
    
    if ticker:
        ticker_upper = ticker.upper()
        # Clear expirations (exact match)
        _expirations_cache.pop(ticker_upper, None)
        
        # Clear options chains (prefix match)
        keys_to_remove = [k for k in _options_cache.keys() if k.startswith(ticker_upper)]
        for k in keys_to_remove:
            _options_cache.pop(k, None)
    else:
        _options_cache.clear()
        _expirations_cache.clear()


def get_available_expirations(ticker_symbol: str, use_cache: bool = True) -> tuple[str, ...] | None:
    """
    Fetches available expiration dates for a ticker's options.
    
    Args:
        ticker_symbol: The stock ticker symbol (e.g., "AAPL")
        use_cache: Whether to use cached data if available
    
    Returns:
        Tuple of expiration date strings (YYYY-MM-DD format), or None on error
    """
    ticker_upper = ticker_symbol.upper()
    cache_key = ticker_upper
    
    # Check cache first
    if use_cache and cache_key in _expirations_cache:
        cache_entry = _expirations_cache[cache_key]
        if _is_cache_valid(cache_entry):
            logging.debug(f"Using cached expirations for {ticker_upper}")
            return cache_entry.get('data')
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = ticker.options
        
        if expirations:
            # Cache the result
            _expirations_cache[cache_key] = {
                'data': expirations,
                'timestamp': time.time()
            }
            return expirations
        return None
    except Exception as e:
        logging.error(f"Error fetching expirations for {ticker_symbol}: {e}")
        return None


import datetime
from stockstui.utils import black_scholes


def _calculate_greeks_for_chain(chain_df, underlying_price, expiration_date, flag):
    """
    Helper to calculate Greeks for a DataFrame of options.
    
    Args:
        chain_df: DataFrame containing option data
        underlying_price: Current price of underlying asset
        expiration_date: Expiration date string (YYYY-MM-DD)
        flag: 'c' for Call, 'p' for Put
    """
    if chain_df is None or chain_df.empty or not underlying_price:
        return chain_df

    # Constants for calculation
    RISK_FREE_RATE = 0.045  # 4.5% approximation
    
    # Calculate time to expiration in years
    try:
        exp_dt = datetime.datetime.strptime(expiration_date, '%Y-%m-%d')
        now = datetime.datetime.now()
        # Add end of day time (16:00) to expiration for better precision
        exp_dt = exp_dt.replace(hour=16, minute=0, second=0)
        
        diff = exp_dt - now
        days_to_exp = diff.total_seconds() / (24 * 3600)
        T = days_to_exp / 365.0
    except Exception:
        T = 0

    # Initialize Greek columns
    greeks_list = []
    
    for _, row in chain_df.iterrows():
        strike = row.get('strike', 0)
        iv = row.get('impliedVolatility', 0)
        
        # Calculate Greeks
        greeks = black_scholes.calculate_greeks(
            flag=flag,
            S=underlying_price,
            K=strike,
            T=T,
            r=RISK_FREE_RATE,
            sigma=iv
        )
        greeks_list.append(greeks)
    
    # Add columns to DataFrame
    if greeks_list:
        import pandas as pd
        greeks_df = pd.DataFrame(greeks_list)
        # Concatenate original df with greeks
        # Reset index to ensure alignment
        chain_df = chain_df.reset_index(drop=True)
        chain_df = pd.concat([chain_df, greeks_df], axis=1)
        
    return chain_df


def get_options_chain(ticker_symbol: str, expiration_date: str | None = None, use_cache: bool = True):
    """
    Fetches the options chain for a ticker and expiration date.
    
    Args:
        ticker_symbol: The stock ticker symbol (e.g., "AAPL")
        expiration_date: Specific expiration date (YYYY-MM-DD), or None for nearest
        use_cache: Whether to use cached data if available
    
    Returns:
        Dictionary with 'calls', 'puts', and 'underlying' keys, or None on error.
        calls and puts are pandas DataFrames.
    """
    ticker_upper = ticker_symbol.upper()
    cache_key = f"{ticker_upper}_{expiration_date or 'nearest'}"
    
    # Check cache first
    if use_cache and cache_key in _options_cache:
        cache_entry = _options_cache[cache_key]
        if _is_cache_valid(cache_entry):
            logging.debug(f"Using cached options chain for {cache_key}")
            return cache_entry.get('data')
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        options_chain = ticker.option_chain(date=expiration_date)
        
        # Get underlying price
        underlying = options_chain.underlying or {}
        underlying_price = underlying.get('regularMarketPrice')
        
        # If expiration_date is None (nearest), we need to know what it is for Greek calc
        # But yfinance option_chain(date=None) returns the nearest, 
        # however we might not know exactly which date that is without checking ticker.options[0]
        # For now, if date is missing, Greeks might be slightly off if we don't know T.
        # But usually the UI passes a specific date.
        
        calc_date = expiration_date
        if not calc_date:
             # Try to guess or fetch expirations if not provided (though usually it is)
             # For MVP, if no date provided, skip Greeks or use 0
             pass

        calls_df = options_chain.calls
        puts_df = options_chain.puts
        
        if calc_date and underlying_price:
            calls_df = _calculate_greeks_for_chain(calls_df, underlying_price, calc_date, 'c')
            puts_df = _calculate_greeks_for_chain(puts_df, underlying_price, calc_date, 'p')

        result = {
            'calls': calls_df,
            'puts': puts_df,
            'underlying': options_chain.underlying,
            'expiration': calc_date  # Store the date used
        }
        
        # Cache the result
        _options_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        
        return result
    except ValueError as e:
        # Specific error for invalid expiration date
        logging.error(f"Invalid expiration date for {ticker_symbol}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error fetching options chain for {ticker_symbol}: {e}")
        return None
