import yfinance as yf
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import time
import pandas as pd

# In-memory cache for storing fetched market data to reduce API calls.
_price_cache = {}
_news_cache = {}
_info_cache = {}
_market_calendars = {}

# Duration for which cached news is considered fresh.
NEWS_CACHE_DURATION_SECONDS = 300  # 5 minutes

try:
    import pandas_market_calendars as mcal
except ImportError:
    mcal = None


def _get_calendar(exchange_name: str):
    """
    Retrieves a market calendar, translating exchange codes from yfinance to pandas_market_calendars names.

    Some yfinance tickers (like ^GSPC, ^DJI) report non-standard exchange names ('SNP', 'DJI').
    This function normalizes them to valid pandas_market_calendars calendars (e.g., 'NYSE').
    Caches retrieved calendars for performance.
    """
    if exchange_name in _market_calendars:
        return _market_calendars[exchange_name]
    # MAPPING: yfinance exchange codes -> pandas_market_calendars calendar names
    exchange_map = {
        "NMS": "NYSE",
        "NYQ": "NYSE",
        "NYS": "NYSE",
        "GDAX": "CME_Crypto",
        "SNP": "NYSE",
        "DJI": "NYSE",
        "CBOE": "NYSE",
        "NIM": "NYSE",
    }
    calendar_name = exchange_map.get(exchange_name, exchange_name)
    if mcal is None:
        return None
    try:
        calendar = mcal.get_calendar(calendar_name)
        _market_calendars[exchange_name] = calendar
        return calendar
    except Exception as e:
        logging.debug(f"Failed to get calendar for {calendar_name}: {e}")
        return None


def _calculate_info_expiry(exchange_name: str) -> datetime:
    now = datetime.now(timezone.utc)
    cal = _get_calendar(exchange_name)
    if cal is None:
        return now + timedelta(hours=1)
    try:
        schedule = cal.schedule(
            start_date=now.date(), end_date=now.date() + timedelta(days=7)
        )
        if not schedule.empty:
            future_opens = schedule.market_open[schedule.market_open > now]
            if not future_opens.empty:
                # ASSUMPTION: The 'previous_close' value updates shortly after market open.
                # We add a 5-minute buffer to ensure the API has refreshed before we re-fetch.
                return future_opens.iloc[0].to_pydatetime() + timedelta(minutes=5)
    except Exception as e:
        logging.debug(f"Failed to calculate info expiry for {exchange_name}: {e}")
        pass
    return now + timedelta(hours=1)


def populate_price_cache(initial_data: dict):
    global _price_cache
    _price_cache.update(initial_data)
    logging.info(f"In-memory price cache populated with {len(initial_data)} items.")


def populate_info_cache(initial_data: dict):
    global _info_cache
    _info_cache.update(initial_data)
    logging.info(f"In-memory info cache populated with {len(initial_data)} items.")


def get_price_cache_state() -> dict:
    return _price_cache


def get_info_cache_state() -> dict:
    return _info_cache


def get_market_price_data(
    tickers: list[str], force_refresh: bool = False
) -> list[dict]:
    seen = set()
    valid_tickers = [
        t.upper()
        for t in tickers
        if t and t.upper() not in seen and not seen.add(t.upper())
    ]
    if not valid_tickers:
        return []

    now = datetime.now(timezone.utc)

    # PERF: Batch market-status lookups by exchange.
    # Previously this called get_market_status() once per ticker, which rebuilt
    # a Pandas schedule DataFrame each time. Now we call it once per unique
    # exchange and reuse the result for all tickers on that exchange.
    _exchange_open_status: dict[str, bool] = {}

    slow_data_to_fetch, fast_data_to_fetch = [], []
    for ticker in valid_tickers:
        if (
            force_refresh
            or ticker not in _price_cache
            or now >= _price_cache[ticker].get("expiry", now)
        ):
            slow_data_to_fetch.append(ticker)

        info = _info_cache.get(ticker, {})
        exchange = info.get("exchange", "NYSE")
        if exchange not in _exchange_open_status:
            _exchange_open_status[exchange] = bool(
                get_market_status(exchange).get("is_open")
            )
        if _exchange_open_status[exchange]:
            fast_data_to_fetch.append(ticker)

    if slow_data_to_fetch:
        _fetch_and_cache_slow_data(slow_data_to_fetch)

    live_prices = _fetch_fast_data(fast_data_to_fetch) if fast_data_to_fetch else {}

    # Merge live price updates back into the cache to maintain a single source of truth.
    # This prevents data loss when switching tabs mid-session.
    if live_prices:
        for ticker, fast_data_update in live_prices.items():
            if ticker in _price_cache and "data" in _price_cache[ticker]:
                # Filter out None values to prevent overwriting valid cached data (fallback)
                valid_updates = {k: v for k, v in fast_data_update.items() if v is not None}
                _price_cache[ticker]["data"].update(valid_updates)

    # Now that the cache is updated, construct the final list from it.
    final_data = []
    for ticker in valid_tickers:
        if ticker in _price_cache:
            final_data.append(_price_cache[ticker].get("data", {}))

    return final_data


def _fetch_and_cache_slow_data(tickers: list[str]):
    """
    Fetches full metadata (info + fast_info) for a batch of tickers in parallel.

    PERF: Previously this iterated sequentially, waiting for each HTTP response
    before starting the next. Now each ticker is fetched in its own thread via
    ThreadPoolExecutor, cutting wall-clock time from O(n * latency) to roughly
    O(latency) for typical list sizes.

    Cache writes happen only after all futures complete so the module-level
    dicts (_price_cache, _info_cache) are never touched from multiple threads.

    PERF: _calculate_info_expiry() is also memoised per exchange within the
    batch — the calendar schedule DataFrame is built once per exchange rather
    than once per ticker.
    """
    if not tickers:
        return

    def _fetch_one(ticker: str) -> tuple[str, dict | None, object | None]:
        """Fetch info for a single ticker. Runs inside the thread pool."""
        try:
            tkr = yf.Ticker(ticker)
            return ticker, tkr.info, tkr.fast_info
        except Exception:
            logging.warning(f"Failed to fetch slow data for {ticker}")
            return ticker, None, None

    # Cap threads to avoid hammering yfinance rate-limits on very large lists.
    max_workers = min(len(tickers), 8)
    raw_results: dict[str, tuple[dict | None, object | None]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(future_to_ticker):
            ticker, slow_info, fast_info = future.result()
            raw_results[ticker] = (slow_info, fast_info)

    # PERF: Cache _calculate_info_expiry() per exchange so the Pandas calendar
    # schedule query runs once per exchange per batch instead of once per ticker.
    exchange_expiry_cache: dict[str, datetime] = {}

    # Write to module-level caches sequentially (no concurrent access).
    # Preserve the original ticker order for predictability.
    for ticker in tickers:
        slow_info, fast_info = raw_results.get(ticker, (None, None))
        try:
            if slow_info and slow_info.get("currency"):
                exchange = slow_info.get("exchange", "NYSE")
                _info_cache[ticker] = {
                    "currency": slow_info.get("currency"),
                    "exchange": exchange,
                    "shortName": slow_info.get("shortName"),
                    "longName": slow_info.get("longName"),
                }
                if exchange not in exchange_expiry_cache:
                    exchange_expiry_cache[exchange] = _calculate_info_expiry(exchange)
                _price_cache[ticker] = {
                    "expiry": exchange_expiry_cache[exchange],
                    "data": {
                        "symbol": ticker,
                        "currency": fast_info.get("currency", slow_info.get("currency", "USD")),
                        "description": slow_info.get("longName", ticker),
                        "price": fast_info.get("lastPrice")
                        or slow_info.get("currentPrice"),
                        "previous_close": slow_info.get("regularMarketPreviousClose")
                        or slow_info.get("previousClose")
                        or fast_info.get("previousClose"),
                        "day_low": fast_info.get("dayLow")
                        or slow_info.get("regularMarketDayLow"),
                        "day_high": fast_info.get("dayHigh")
                        or slow_info.get("regularMarketDayHigh"),
                        "volume": fast_info.get("lastVolume")
                        or slow_info.get("volume"),
                        "open": fast_info.get("open") or slow_info.get("open"),
                        "fifty_two_week_low": slow_info.get("fiftyTwoWeekLow"),
                        "fifty_two_week_high": slow_info.get("fiftyTwoWeekHigh"),
                        "pe_ratio": slow_info.get("trailingPE")
                        or slow_info.get("forwardPE"),
                        "market_cap": fast_info.get("marketCap")
                        or slow_info.get("marketCap"),
                        "dividend_yield": slow_info.get("dividendYield")
                        or slow_info.get("trailingAnnualDividendYield"),
                        "eps": slow_info.get("trailingEps")
                        or slow_info.get("forwardEps"),
                        "beta": slow_info.get("beta") or slow_info.get("beta3Year"),
                        "all_time_high": slow_info.get("allTimeHigh"),
                    },
                }
            else:
                # If slow_info is None, it means _fetch_one caught an exception (fetch failed).
                # If slow_info is a dict but has no currency, it's an invalid ticker.
                description = "Data Unavailable" if slow_info is None else "Invalid Ticker"
                _price_cache[ticker] = {
                    "expiry": datetime.now(timezone.utc) + timedelta(days=1),
                    "data": {"symbol": ticker, "description": description},
                }
        except Exception:
            logging.warning(f"Failed to cache slow data for {ticker}")
            _price_cache[ticker] = {
                "expiry": datetime.now(timezone.utc) + timedelta(days=1),
                "data": {"symbol": ticker, "description": "Data Unavailable"},
            }


def _fetch_fast_data(tickers: list[str]) -> dict:
    """
    Fetches live intraday OHLCV data for multiple tickers in a single batch call.

    PERF: Replaces the old approach of creating yf.Tickers() and then accessing
    .fast_info for each ticker sequentially. yf.download() fires a single
    batched HTTP request with its own internal threading (threads=True is the
    default), so all tickers are fetched concurrently inside yfinance itself.

    NOTE: yf.download() returns OHLCV data, not the same field set as fast_info.
    market_cap and currency are intentionally omitted here — they are already
    present in the slow cache and do not need refreshing on every live cycle.
    day_high / day_low are derived as the intraday max/min across all 1-minute
    bars returned for the current session.
    """
    if not tickers:
        return {}

    live_prices: dict[str, dict] = {}
    try:
        # period="1d" with interval="1m" gives today's intraday bars.
        # auto_adjust=False returns raw (unadjusted) prices, consistent with
        # what fast_info.lastPrice returns.
        # multi_level_index=True always returns a MultiIndex (metric, ticker)
        # even for a single ticker, which keeps the extraction logic uniform.
        df = yf.download(
            tickers,
            period="1d",
            interval="1m",
            threads=True,
            progress=False,
            auto_adjust=False,
            multi_level_index=True,
        )

        if df is None or df.empty:
            return {}

        for ticker in tickers:
            try:
                close_series = df["Close"][ticker].dropna()
                if close_series.empty:
                    # Market closed or no intraday data for this ticker today.
                    continue

                high_series = df["High"][ticker].dropna()
                low_series = df["Low"][ticker].dropna()
                open_series = df["Open"][ticker].dropna()
                vol_series = df["Volume"][ticker].dropna()

                live_prices[ticker] = {
                    # Last 1-minute close is the most recent trade price.
                    "price": float(close_series.iloc[-1]),
                    # Intraday high/low span all bars in the current session.
                    "day_high": float(high_series.max()) if not high_series.empty else None,
                    "day_low": float(low_series.min()) if not low_series.empty else None,
                    # First bar's open is the session open price.
                    "open": float(open_series.iloc[0]) if not open_series.empty else None,
                    # Sum of all intraday bar volumes equals total day volume.
                    "volume": int(vol_series.sum()) if not vol_series.empty else None,
                    # market_cap and currency omitted intentionally — see docstring.
                }
            except (KeyError, IndexError, ValueError, TypeError) as e:
                logging.warning(
                    f"Failed to extract fast data for {ticker} from batch download: {e}"
                )

    except Exception as e:
        logging.warning(f"Batch fast-data download failed: {e}")

    return live_prices


def get_ticker_info(ticker: str) -> dict | None:
    if ticker in _info_cache:
        return _info_cache[ticker]
    try:
        info = yf.Ticker(ticker).info
        if not info or not info.get("currency"):
            _info_cache[ticker] = {}
            return None
        _info_cache[ticker] = {
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "shortName": info.get("shortName"),
            "longName": info.get("longName"),
        }
        return _info_cache[ticker]
    except Exception:
        _info_cache[ticker] = {}
        return None


def get_market_status(calendar_name="NYSE") -> dict:
    """
    Determines the current market status and finds the next open/close times.

    This function is enhanced to provide not just the current state but also
    future transition times, which enables the main application to schedule
    the next status poll intelligently.

    Returns:
        A dictionary containing the status, next open/close times, and other details.
    """
    if calendar_name == "GDAX":
        calendar_name = "CME_Crypto"
    cal = _get_calendar(calendar_name)
    if not cal:
        return {"status": "unknown", "is_open": True, "calendar": calendar_name}

    try:
        now = pd.Timestamp.now(tz=cal.tz)
        schedule = cal.schedule(
            start_date=now.date() - pd.Timedelta(days=1),
            end_date=now.date() + pd.Timedelta(days=7),
        )

        result = {
            "status": "closed",
            "is_open": False,
            "calendar": calendar_name,
            "next_open": None,
            "next_close": None,
            "reason": None,
            "holiday": None,
            "premarket_open": None,
            "premarket_close": None,
            "postmarket_open": None,
            "postmarket_close": None,
        }

        if not schedule.empty:
            future_opens = schedule.market_open[schedule.market_open > now]
            if not future_opens.empty:
                result["next_open"] = future_opens.iloc[0].to_pydatetime()

            future_closes = schedule.market_close[schedule.market_close > now]
            if not future_closes.empty:
                result["next_close"] = future_closes.iloc[0].to_pydatetime()

        today_schedule = schedule[schedule.index.date == now.date()]
        if not today_schedule.empty:
            row = today_schedule.iloc[0]
            market_open, market_close = row.market_open, row.market_close

            # WORKAROUND: The installed pandas_market_calendars version lacks `extended_hours` support.
            # We manually calculate extended hours based on NYSE standards:
            #   - Pre-market: 5.5 hours before market_open (e.g., 4:00 AM if open is 9:30 AM).
            #   - Post-market: 4 hours after market_close (e.g., 8:00 PM for a 4:00 PM close).
            # These offsets are relative, so they automatically adjust for early-close days.

            pre_open = market_open - pd.Timedelta(hours=5.5)
            # Pre-close is market_open

            # Post-open is market_close
            post_close = market_close + pd.Timedelta(hours=4)

            result["premarket_open"] = pre_open
            result["premarket_close"] = market_open
            result["postmarket_open"] = market_close
            result["postmarket_close"] = post_close

            if market_open <= now < market_close:
                result["status"] = "open"
                result["is_open"] = True
            elif pre_open <= now < market_open:
                result["status"] = "pre"
            elif market_close <= now < post_close:
                result["status"] = "post"
        else:
            if now.weekday() >= 5:
                result["reason"] = "weekend"
            else:
                holidays_obj = cal.holidays()
                today_date = pd.Timestamp(now.date())
                if hasattr(holidays_obj, "holidays"):
                    holiday_list = (
                        holidays_obj.holidays()
                        if callable(holidays_obj.holidays)
                        else holidays_obj.holidays
                    )
                    if today_date in holiday_list:
                        result["reason"] = "holiday"
                        if hasattr(holiday_list, "loc"):
                            result["holiday"] = holiday_list.loc[today_date]

        return result
    except Exception as e:
        logging.error(f"Error getting market status for {calendar_name}: {e}")
        return {"status": "unknown", "is_open": True, "calendar": calendar_name}


def get_historical_data(ticker: str, period: str, interval: str = "1d"):
    df = pd.DataFrame()
    df.attrs["symbol"] = ticker.upper()
    try:
        info = get_ticker_info(ticker)
        if not info:
            df.attrs["error"] = "Invalid Ticker"
            return df
        data = yf.Ticker(ticker).history(period=period, interval=interval)
        if not data.empty:
            data.attrs["symbol"] = ticker.upper()
            data.attrs["currency"] = info.get("currency")
        return data
    except Exception as e:
        # HACK: yfinance sometimes raises errors for valid tickers with no data in range.
        # Log the actual error for debugging, but return an empty dataframe.
        logging.error(f"yfinance error fetching history for {ticker} ({period}): {e}")
        df.attrs["error"] = "Data Error"
        return df


def get_news_for_tickers(tickers: list[str]) -> list[dict] | None:
    all_news, seen_urls = [], set()
    for ticker in tickers:
        news_items = get_news_data(ticker)
        if news_items:
            for item in news_items:
                if (link := item.get("link")) and link not in seen_urls:
                    all_news.append(item)
                    seen_urls.add(link)
    if not all_news:
        return None if len(tickers) > 0 else []
    all_news.sort(key=lambda x: x["publish_datetime_utc"], reverse=True)
    return all_news


def get_news_data(ticker: str) -> list[dict] | None:
    if not ticker:
        return []
    normalized_ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    if normalized_ticker in _news_cache:
        timestamp, cached_data = _news_cache[normalized_ticker]
        if (now - timestamp).total_seconds() < NEWS_CACHE_DURATION_SECONDS:
            return cached_data
    info = get_ticker_info(ticker)
    if not info:
        return None
    raw_news = yf.Ticker(normalized_ticker).news
    if not raw_news:
        return []
    processed_news = []
    for item in raw_news:
        content = item.get("content", {})
        if not content:
            continue
        publish_time_utc = None
        publish_time_str = "N/A"
        if pub_date_str := content.get("pubDate"):
            try:
                publish_time_utc = datetime.fromisoformat(
                    pub_date_str.replace("Z", "+00:00")
                )
                publish_time_str = publish_time_utc.astimezone().strftime(
                    "%Y-%m-%d %H:%M %Z"
                )
            except (ValueError, TypeError):
                publish_time_str = pub_date_str
        processed_news.append(
            {
                "source_ticker": normalized_ticker,
                "title": content.get("title", "N/A"),
                "summary": content.get("summary", "N/A"),
                "publisher": content.get("provider", {}).get("displayName", "N/A"),
                "link": content.get("canonicalUrl", {}).get("url", "#"),
                "publish_time": publish_time_str,
                "publish_datetime_utc": publish_time_utc,
            }
        )
    _news_cache[normalized_ticker] = (datetime.now(timezone.utc), processed_news)
    return processed_news


def get_ticker_info_comparison(ticker: str) -> dict:
    try:
        ticker_obj = yf.Ticker(ticker)
        fast_info, slow_info = ticker_obj.fast_info, ticker_obj.info
        if not slow_info:
            return {"fast": {}, "slow": {}}
        return {"fast": fast_info, "slow": slow_info}
    except Exception:
        return {"fast": {}, "slow": {}}


def run_ticker_debug_test(tickers: list[str]) -> list[dict]:
    """
    Tests a list of tickers for validity and measures API response latency for each.
    """
    results = []
    # FIX: Iterate and fetch tickers individually to measure individual latency.
    for symbol in tickers:
        start_time = time.perf_counter()
        try:
            # Let yfinance manage its own session.
            info = yf.Ticker(symbol).info
            is_valid = info and info.get("currency") is not None
        except Exception:
            info, is_valid = {}, False
        latency = time.perf_counter() - start_time
        description = (
            info.get("longName", "N/A") if is_valid else "Could not retrieve data."
        )
        results.append(
            {
                "symbol": symbol,
                "is_valid": is_valid,
                "description": description,
                "latency": latency,
            }
        )

    results.sort(key=lambda x: x["latency"], reverse=True)
    return results


def run_list_debug_test(lists: dict[str, list[str]]):
    """
    Measures the time it takes to fetch data for entire lists of tickers.
    This is a true network test.
    """
    results = []
    for list_name, tickers in lists.items():
        if not tickers:
            results.append({"list_name": list_name, "latency": 0.0, "ticker_count": 0})
            continue

        start_time = time.perf_counter()
        # FIX: Use force_refresh=True to guarantee a network call. No session needed.
        get_market_price_data(tickers, force_refresh=True)
        latency = time.perf_counter() - start_time

        results.append(
            {"list_name": list_name, "latency": latency, "ticker_count": len(tickers)}
        )
    results.sort(key=lambda x: x["latency"], reverse=True)
    return results


def run_cache_test(lists: dict[str, list[str]]) -> list[dict]:
    """
    Tests the performance of reading pre-cached data for lists of tickers.
    This test relies on the cache being populated by normal app usage and
    does not trigger network calls itself.
    """
    results = []
    for list_name, tickers in lists.items():
        start_time = time.perf_counter()
        _ = [get_cached_price(ticker) for ticker in tickers]
        latency = time.perf_counter() - start_time
        results.append(
            {"list_name": list_name, "latency": latency, "ticker_count": len(tickers)}
        )

    results.sort(key=lambda x: x["latency"], reverse=True)
    return results


def is_cached(ticker: str) -> bool:
    return ticker.upper() in _price_cache


def get_cached_price(ticker: str) -> dict | None:
    entry = _price_cache.get(ticker.upper())
    return entry.get("data") if entry else None
