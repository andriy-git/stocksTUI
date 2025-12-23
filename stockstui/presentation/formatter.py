from typing import Union
from rich.text import Text
import pandas as pd
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable

def format_price_data_for_table(data: list[dict], old_prices: dict, alias_map: dict[str, str]) -> list[tuple]:
    """
    Formats raw price data for display in the main DataTable.

    This function calculates derived values like change and change percentage,
    determines the direction of price change for UI flashing, and formats
    numerical data into strings. It prioritizes user-defined aliases for the
    description column.

    Args:
        data: A list of dictionaries, where each dict is from the market provider.
        old_prices: A dict mapping tickers to their previously known prices.
        alias_map: A dict mapping tickers to their user-defined aliases.

    Returns:
        A list of tuples, where each tuple represents a row for the DataTable.
    """
    rows = []
    for item in data:
        symbol = item.get('symbol', 'N/A')
        # Prioritize the user-defined alias, fall back to the long name from the provider.
        description = alias_map.get(symbol, item.get('description', 'N/A'))
        price = item.get('price')
        previous_close = item.get('previous_close')
        
        change, change_percent, change_direction = None, None, None
        if price is not None and previous_close is not None and previous_close != 0:
            change = price - previous_close
            change_percent = change / previous_close

        # Determine change direction for flashing based on the *old* price
        old_price = old_prices.get(symbol)
        if old_price is not None and price is not None:
            if round(price, 2) > round(old_price, 2):
                change_direction = 'up'
            elif round(price, 2) < round(old_price, 2):
                change_direction = 'down'

        day_low = item.get('day_low')
        day_high = item.get('day_high')
        day_range_str = f"${day_low:,.2f} - ${day_high:,.2f}" if day_low is not None and day_high is not None else "N/A"

        fifty_two_week_low = item.get('fifty_two_week_low')
        fifty_two_week_high = item.get('fifty_two_week_high')
        fifty_two_week_range_str = f"${fifty_two_week_low:,.2f} - ${fifty_two_week_high:,.2f}" if fifty_two_week_low is not None and fifty_two_week_high is not None else "N/A"

        volume = item.get('volume')
        volume_str = f"{volume:,}" if volume is not None else "N/A"

        open_price = item.get('open')
        open_str = f"${open_price:,.2f}" if open_price is not None else "N/A"

        prev_close_str = f"${previous_close:,.2f}" if previous_close is not None else "N/A"

        all_time_high = item.get('all_time_high')
        pct_off_ath = None
        if price is not None and all_time_high is not None and all_time_high != 0:
            pct_off_ath = (price / all_time_high) - 1

        # Return a dictionary so columns can be selected dynamically
        rows.append({
            "Description": description,
            "Price": price, 
            "Change": change,
            "% Change": change_percent,
            "Day's Range": day_range_str,
            "52-Wk Range": fifty_two_week_range_str,
            "Ticker": symbol,
            "Volume": volume_str,
            "Open": open_str,
            "Prev Close": prev_close_str,
            "PE Ratio": f"{item.get('pe_ratio', 0):.2f}" if item.get('pe_ratio') else "N/A",
            "Market Cap": f"{item.get('market_cap', 0):,}" if item.get('market_cap') else "N/A",
            "Div Yield": f"{item.get('dividend_yield', 0):.2f}%" if item.get('dividend_yield') else "N/A",
            "EPS": f"{item.get('eps', 0):.2f}" if item.get('eps') else "N/A",
            "Beta": f"{item.get('beta', 0):.2f}" if item.get('beta') else "N/A",
            "All Time High": all_time_high,
            "% Off ATH": pct_off_ath,
            "_change_direction": change_direction, # Internal use
            "_raw_price": price, # For sorting if needed, though Price is used for display
            "_raw_change": change,
            "_raw_change_percent": change_percent
        })
    return rows

def format_historical_data_as_table(data):
    """
    Formats a pandas DataFrame of historical data into a Textual DataTable.

    It intelligently formats the date/time column based on whether the data is
    daily or intraday. All other numerical data is formatted as currency or a
    comma-separated number.

    Args:
        data: A pandas DataFrame containing historical OHLCV data.

    Returns:
        A Textual DataTable widget ready for display.
    """
    table = NavigableDataTable(zebra_stripes=True, id="history-table")

    # Check if the data is intraday by seeing if all timestamps are at midnight.
    # If not, it's intraday data.
    is_intraday = not (data.index.normalize() == data.index).all()

    if is_intraday:
        table.add_column("Timestamp", key="Date")
        date_format = '%Y-%m-%d %H:%M:%S'
    else:
        table.add_column("Date", key="Date")
        date_format = '%Y-%m-%d'

    table.add_column("Open", key="Open")
    table.add_column("High", key="High")
    table.add_column("Low", key="Low")
    table.add_column("Close", key="Close")
    table.add_column("Volume", key="Volume")
    
    for index, row in data.iterrows():
        table.add_row(
            index.strftime(date_format),
            f"${row['Open']:,.2f}",
            f"${row['High']:,.2f}",
            f"${row['Low']:,.2f}",
            f"${row['Close']:,.2f}",
            f"{row['Volume']:,}"
        )
    return table


def format_ticker_debug_data_for_table(data: list[dict]) -> list[tuple]:
    """Formats individual ticker debug results into a list of tuples for a table."""
    rows = []
    for item in data:
        rows.append((
            item.get('symbol', 'N/A'),
            item.get('is_valid', False),
            item.get('description', 'N/A'),
            item.get('latency', 0.0)
        ))
    return rows

def format_list_debug_data_for_table(data: list[dict]) -> list[tuple]:
    """Formats list-based batch debug results into a list of tuples for a table."""
    rows = []
    for item in data:
        rows.append((
            item.get('list_name', 'N/A'),
            item.get('ticker_count', 0),
            item.get('latency', 0.0)
        ))
    return rows

def format_cache_test_data_for_table(data: list[dict]) -> list[tuple]:
    """Formats cache performance test results into a list of tuples for a table."""
    rows = []
    for item in data:
        rows.append((
            item.get('list_name', 'N/A'),
            item.get('ticker_count', 0),
            item.get('latency', 0.0)
        ))
    return rows

def format_info_comparison(fast_info: dict, slow_info: dict) -> list[tuple[str, str, str, bool]]:
    """
    Compares 'fast_info' and full 'info' from yfinance and formats for a table.

    This is a debugging tool to see the difference in data provided by the two
    different yfinance methods.

    Args:
        fast_info: The dictionary from yfinance's `fast_info`.
        slow_info: The dictionary from yfinance's `info`.

    Returns:
        A list of tuples, each containing a key, the two values, and a mismatch flag.
    """
    if not slow_info:
        return [("Error", "Could not retrieve data.", "Ticker may be invalid.", False)]
        
    # Find the union of all keys from both dictionaries
    all_keys = sorted(list(set(fast_info.keys()) | set(slow_info.keys())))
    
    rows = []
    for key in all_keys:
        val_fast = fast_info.get(key, "N/A")
        val_slow = slow_info.get(key, "N/A")
        
        # Flag a mismatch only if both values exist but are different
        is_mismatch = (val_fast != "N/A" and val_slow != "N/A" and val_fast != val_slow)
        
        rows.append((key, str(val_fast), str(val_slow), is_mismatch))
        
    return rows

def escape(text: str) -> str:
    """Escapes characters that have special meaning in Rich-flavored Markdown."""
    return text.replace('[', r'\[').replace(']', r'\]').replace('*', r'\*')

def format_news_for_display(news: list[dict]) -> tuple[Union[str, Text], list[str]]:
    """
    Formats a list of news items into a Markdown string for display.
    If multiple tickers are present, it indicates the source for each article.

    Args:
        news: A list of news item dictionaries from the market provider.

    Returns:
        A tuple containing the formatted Markdown string (or a Rich Text object)
        and a list of the URLs from the news items.
    """
    if not news:
        return (Text.from_markup("[dim]No news found for this ticker.[/dim]"), [])
    
    text = ""
    urls = []
    for item in news:
        source_ticker = item.get('source_ticker')
        if source_ticker:
            text += f"Source: **`{source_ticker}`**\n"
        
        title_raw = item.get('title', 'N/A')
        title = escape(title_raw)
        link = item.get('link', '#')

        publisher_raw = item.get('publisher', 'N/A')
        publisher = escape(publisher_raw)

        publish_time_raw = item.get('publish_time', 'N/A')
        publish_time = escape(publish_time_raw)

        summary_raw = item.get('summary', 'N/A')
        summary = escape(summary_raw)

        if title_raw != 'N/A':
            text += f"**[{title}]({link})**\n\n"
            urls.append(link)
        else:
            text += f"**[dim]{title}[/dim]**\n\n"
        
        publisher_display = publisher if publisher_raw != 'N/A' else f"[dim]{publisher}[/dim]"
        time_display = publish_time if publish_time_raw != 'N/A' else f"[dim]{publish_time}[/dim]"
        text += f"By {publisher_display} at {time_display}\n\n"

        if summary_raw != 'N/A':
            text += f"**Summary:**\n{summary}\n\n"
        else:
            text += f"**Summary:**\n[dim]{summary}[/dim]\n\n"

        text += "---\n"
        
    return (text, urls)

from datetime import datetime
from dateutil.tz import gettz

def format_market_status(market_status: dict | None) -> tuple | None:
    """Formats the detailed market status dictionary into a user-friendly string."""
    if not isinstance(market_status, dict):
        return None

    calendar = market_status.get('calendar', 'Market')
    status_code = market_status.get('status', 'closed')
    reason_code = market_status.get('reason')
    holiday = market_status.get('holiday')
    next_open = market_status.get('next_open')
    next_close = market_status.get('next_close')
    is_open = market_status.get('is_open', False)
    
    # Default to system's local timezone if gettz() returns None
    local_tz = gettz() or datetime.now().astimezone().tzinfo

    # 1. Exchange
    text = f"{calendar}: "
    
    # 2. Main Status (Open vs Closed) + Reason (Pre/Post/Weekend/Holiday)
    # The display logic constructs a 3-part status:
    #   [Main Status] [Reason] [Next Event]
    #
    # logic:
    # - Main Status: Explicitly "Open" or "Closed".
    # - Reason: Provides context for the "Closed" state (e.g., Pre-Market, Weekend).
    #           We treat Pre/Post market as "Closed" for the main status color (Red)
    #           but highlight the reason (Yellow) to distinguish it from a hard close.
    
    # Define Styles
    status_map = {
        "open": "status-open",
        "pre": "status-pre",
        "post": "status-post",
        "closed": "status-closed",
        "unknown": "text-muted",
    }
    
    # Determine Primary Display "Open" or "Closed"
    if status_code == 'open':
        main_status = "Open"
        style_var = status_map['open']
        reason_display = "" # No reason needed for standard open state
    elif status_code == 'pre':
        main_status = "Closed"
        style_var = status_map['closed'] 
        # Highlight Pre-Market activity distinct from the main closed status
        reason_display = "(Pre-Market)"
    elif status_code == 'post':
        main_status = "Closed"
        style_var = status_map['closed']
        # Highlight Post-Market activity distinct from the main closed status
        reason_display = "(Post Market)"
    else: # closed or unknown
        main_status = "Closed"
        style_var = status_map['closed']
        reason_display = ""
        if reason_code == 'weekend':
            reason_display = "(Weekend)"
        elif reason_code == 'holiday':
            holiday_str = holiday[:15] + '...' if holiday and len(holiday) > 15 else (holiday or "Holiday")
            reason_display = f"(Holiday: {holiday_str})"
    
    text_parts = [(f"{main_status} ", style_var)]
    
    if reason_display:
        # Style the reason. 
        # Use specific status color for Pre/Post reasons to make them visually distinct.
        reason_style = "text-muted"
        if status_code == 'pre': reason_style = status_map['pre']
        elif status_code == 'post': reason_style = status_map['post']
        
        text_parts.append((f"{reason_display} ", reason_style))
        
    # 3. Next Event
    # Displays when the current state ends or the next trading session begins.
    next_event_str = ""
    if is_open:
        # ASSUMPTION: 'is_open' is True only for REGULAR trading hours.
        # If open, relevant info is when it closes today.
        if next_close:
            close_local = next_close.astimezone(local_tz)
            next_event_str = f"(Closes {close_local:%H:%M})"
            
    else:
        # If closed (including Pre/Post), the most relevant info is the next Open time.
        if next_open:
            open_local = next_open.astimezone(local_tz)
            # Logic: If next open is today, omit the date. Otherwise include Day abbreviation.
            now = datetime.now(local_tz)
            if open_local.date() == now.date():
                 next_event_str = f"(Opens {open_local:%H:%M})"
            else:
                 next_event_str = f"(Opens {open_local:%a %H:%M})"
    
    if next_event_str:
        text_parts.append((next_event_str, "text-muted"))

    return (text, text_parts)