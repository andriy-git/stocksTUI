import argparse
from importlib import metadata

try:
    # Read the version dynamically from the package metadata. This is the
    # standard way to get the version of an installed package.
    APP_VERSION = metadata.version("stocksTUI")
except metadata.PackageNotFoundError:
    # Fallback for development environments where the package is not
    # installed in the traditional sense.
    APP_VERSION = "0.0.0-dev"

class SessionListAction(argparse.Action):
    """
    Custom argparse action to parse session list arguments.
    It handles input like 'NAME=TICKER1,TICKER2' and converts it into a
    dictionary that the application can use to create temporary watchlists.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        # Initialize the dictionary if it doesn't exist
        session_lists = getattr(namespace, self.dest, None) or {}
        for value in values:
            if '=' not in value:
                raise argparse.ArgumentError(self, f"Argument must be in format NAME=TICKER1,TICKER2,... Got: {value}")
            name, tickers_str = value.split('=', 1)
            tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
            if not tickers:
                 raise argparse.ArgumentError(self, f"List '{name}' must contain at least one ticker.")
            # Store with a standardized key format
            session_lists[name.lower().replace("_", " ")] = tickers
        setattr(namespace, self.dest, session_lists)

def create_arg_parser() -> argparse.ArgumentParser:
    """Creates and returns the command-line argument parser for the application."""
    parser = argparse.ArgumentParser(
        description="stocksTUI: A Terminal User Interface for monitoring stock data.",
        formatter_class=argparse.RawTextHelpFormatter,
        # Let our custom --man flag handle detailed help
        add_help=False
    )

    # --- Standard Arguments ---
    parser.add_argument(
        '-h', '--help',
        action='help',
        default=argparse.SUPPRESS,
        help='Show this help message and exit.'
    )
    parser.add_argument(
        '--man',
        action='store_true',
        help="Show the full user manual and exit."
    )
    parser.add_argument(
        '-v', '-V', '--version',
        action='version',
        version=f'%(prog)s {APP_VERSION}'
    )

    # --- View Selection Group (for TUI mode) ---
    view_group = parser.add_mutually_exclusive_group()
    view_group.add_argument(
        '--tab',
        type=str,
        metavar='LIST_NAME',
        help="Start on a specific watchlist tab (e.g., stocks, crypto)."
    )
    view_group.add_argument(
        '-H', '--history',
        nargs='?',
        const=True,
        default=None,
        metavar='TICKER',
        help="Start on the History tab. Optionally provide a ticker."
    )
    view_group.add_argument(
        '-N', '--news',
        nargs='?',
        const=True,
        default=None,
        metavar='TICKER(S)',
        help="Start on the News tab. Optionally provide one or more\ncomma-separated tickers (e.g., \"AAPL,MSFT\")."
    )
    view_group.add_argument(
        '-O', '--options',
        nargs='?',
        const=True,
        default=None,
        metavar='TICKER',
        help="Start on the Options tab. Optionally provide a ticker."
    )
    view_group.add_argument(
        '--debug',
        action='store_true',
        help="Start on the Debug tab."
    )
    view_group.add_argument(
        '--configs',
        action='store_true',
        help="Start on the Configs tab."
    )
    
    # --- Other Options ---
    parser.add_argument(
        '-o', '--output',
        nargs='?',
        const='all',
        default=None,
        metavar='LISTS',
        help="""Output data directly to the terminal without launching the TUI.
Optionally specify a comma-separated list of watchlists to show.
If no list is specified, all tickers are shown."""
    )
    parser.add_argument(
        '--session-list',
        nargs='+',
        action=SessionListAction,
        metavar='NAME=TICKERS',
        help="""Create a temporary watchlist for this session only.
Format: LIST_NAME=TICKER1,TICKER2,...
Example: --session-list stocks=AAPL,MSFT crypto=BTC-USD
Can be specified multiple times."""
    )

    history_group = parser.add_argument_group('History View Options')
    history_group.add_argument(
        '--period',
        choices=['1d', '5d', '1mo', '6mo', 'ytd', '1y', '5y', 'max'],
        help="Set the time period for the history view."
    )
    history_group.add_argument(
        '-c', '--chart',
        action='store_true',
        help="Show chart by default in the history view."
    )

    return parser