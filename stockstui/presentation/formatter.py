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

        rows.append((
            description,
            price,
            change,
            change_percent,
            day_range_str,
            fifty_two_week_range_str,
            symbol,
            change_direction
        ))
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

def format_market_status(market_status: dict | None) -> tuple | None:
    """Extracts and returns the core components from the market status dictionary."""
    if not isinstance(market_status, dict):
        return None

    calendar = market_status.get('calendar', 'Market')
    status = market_status.get('status', 'closed')
    holiday = market_status.get('holiday')

    return (calendar, status, holiday)