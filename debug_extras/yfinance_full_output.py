import yfinance as yf

# --- Configuration for Table Formatting ---
# Define column widths: [Info Key, Batch Fast, Ind. Fast, Batch Slow, Ind. Slow]
COL_WIDTHS = [28, 18, 18, 18, 18]
# Define column alignments: 'l' for left, 'r' for right
COL_ALIGNMENTS = ['l', 'r', 'r', 'r', 'r']
HEADERS = ["Info Key", "Batch Fast", "Ind. Fast", "Batch Slow", "Ind. Slow"]

def format_row(items: list, widths: list[int], alignments: list[str]) -> str:
    """
    Formats a list of items into a single string of fixed-width columns,
    handling alignment, truncation, and data types.
    """
    formatted_items = []
    for i, item in enumerate(items):
        # 1. Convert item to a display-friendly string
        if item is None:
            s = ""
        elif isinstance(item, float):
            s = f"{item:.4f}"  # Format floats to 4 decimal places
        else:
            s = str(item)

        # 2. Truncate if the string is too long for the column
        if len(s) > widths[i]:
            s = s[:widths[i] - 3] + "..."
        
        # 3. Align the string within its column width
        if alignments[i] == 'r':
            formatted_items.append(s.rjust(widths[i]))
        else:
            formatted_items.append(s.ljust(widths[i]))
            
    return " ".join(formatted_items)

def compare_ticker_info(tickers_to_test: list[str]):
    """
    Compares 'fast_info' and full 'info' data from batch vs. individual
    yfinance requests, printing a clean, fixed-width table.
    """
    if not tickers_to_test:
        print("No tickers provided to test.")
        return

    print("Preparing batch ticker object...")
    try:
        batch_tickers = yf.Tickers(" ".join(tickers_to_test))
        print("Batch object created.\n")
    except Exception as e:
        print(f"Failed to create batch Tickers object: {e}")
        return

    for ticker in tickers_to_test:
        print("-" * sum(COL_WIDTHS) + "-" * (len(COL_WIDTHS) - 1))
        print(f"Ticker: {ticker}")
        print("-" * sum(COL_WIDTHS) + "-" * (len(COL_WIDTHS) - 1))
        
        try:
            # Fetch all four data dictionaries
            batch_fast_info = batch_tickers.tickers[ticker].fast_info
            batch_slow_info = batch_tickers.tickers[ticker].info
            individual_ticker = yf.Ticker(ticker)
            individual_fast_info = individual_ticker.fast_info
            individual_slow_info = individual_ticker.info

            # Combine all unique keys
            all_keys = sorted(list(
                set(batch_fast_info.keys()) | set(individual_fast_info.keys()) |
                set(batch_slow_info.keys()) | set(individual_slow_info.keys())
            ))
            
            # Print table header
            print(format_row(HEADERS, COL_WIDTHS, COL_ALIGNMENTS))
            print("=" * sum(COL_WIDTHS) + "=" * (len(COL_WIDTHS) - 1))

            # Process and print each row
            for key in all_keys:
                row_data = [
                    key,
                    batch_fast_info.get(key),
                    individual_fast_info.get(key),
                    batch_slow_info.get(key),
                    individual_slow_info.get(key)
                ]
                print(format_row(row_data, COL_WIDTHS, COL_ALIGNMENTS))

            print("\n")

        except Exception as e:
            print(f"Could not process ticker {ticker}: {e}\n")

if __name__ == "__main__":
    tickers = ["^VIX", "GC=F", "^FTW5000", "BTC-USD"]
    compare_ticker_info(tickers)
