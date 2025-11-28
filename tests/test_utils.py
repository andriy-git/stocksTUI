import unittest
from unittest.mock import MagicMock
from pathlib import Path
import asyncio
import threading

from rich.text import Text

from stockstui.main import StocksTUI
from stockstui.utils import slugify, extract_cell_text, parse_tags, format_tags, match_tags

# Define the root path of the application package.
TEST_APP_ROOT = Path(__file__).resolve().parent.parent / "stockstui"


async def create_test_app() -> StocksTUI:
    """
    Creates a fully mocked, composed instance of the StocksTUI app for testing.
    """
    app = create_mocked_app()
    
    app._loop = asyncio.get_running_loop()
    app._thread_id = threading.get_ident()
    
    with app._context():
        screen = app.get_default_screen()
        app.install_screen(screen, "_default")
        await app.push_screen("_default")
        
    app.mount()
    await app.workers.wait_for_complete()
    await asyncio.sleep(0.01)
    app.push_screen = MagicMock()
    
    return app

def create_mocked_app() -> StocksTUI:
    """
    Creates a StocksTUI app with mocks but does NOT mount it.
    Suitable for use with app.run_test().
    """
    app = StocksTUI()

    # Replace core components with mocks
    app.config = MagicMock()
    app.db_manager = MagicMock()
    app.portfolio_manager = MagicMock()
    app.notify = MagicMock()
    app.bell = MagicMock()
    app.fetch_prices = MagicMock()
    app.fetch_news = MagicMock()
    app.fetch_historical_data = MagicMock()
    
    # Test theme expectations: use gruvbox_soft_dark (as requested)
    def get_setting_side_effect(key, default=None):
        if key == "theme":
            return "gruvbox_soft_dark"
        if key == "market_calendar":
            return "NYSE"
        return default
        
    app.config.get_setting.side_effect = get_setting_side_effect
    app.config.lists = {"stocks": [], "crypto": [], "news": [], "debug": []}

    # Register a dummy theme to satisfy app requirements
    from textual.theme import Theme
    app.register_theme(Theme(
        name="gruvbox_soft_dark",
        primary="#d79921",
        secondary="#458588",
        background="#282828",
        surface="#3c3836",
        error="#cc241d",
        warning="#d65d0e",
        success="#98971a",
        accent="#b16286",
        dark=True,
        variables={
            "price": "cyan",
            "latency-high": "red",
            "latency-medium": "yellow",
            "latency-low": "blue",
            "text-muted": "#808080",
            "status-open": "green",
            "status-pre": "yellow",
            "status-post": "yellow",
            "status-closed": "red",
            "button-foreground": "white",
            "scrollbar": "black",
            "scrollbar-hover": "#808080",
        }
    ))
    # Mock _available_theme_names to include our dummy theme so on_mount doesn't try to reload
    app._available_theme_names = ["gruvbox_soft_dark"]
    
    # Updated tab map to match actual app structure
    app.tab_map = [
        {'name': 'All', 'category': 'all'},
        {'name': 'Stocks', 'category': 'stocks'},
        {'name': 'Crypto', 'category': 'crypto'},
        {'name': 'News', 'category': 'news'},
        {'name': 'Debug', 'category': 'debug'},
        {'name': 'History', 'category': 'history'},
        {'name': 'Configs', 'category': 'configs'}
    ]
    # Do not mock _rebuild_app so that tabs are actually created
    # app._rebuild_app = MagicMock()
    
    return app


class TestUtils(unittest.TestCase):
    """Unit tests for utility functions."""

    def test_slugify(self):
        self.assertEqual(slugify("My List Name"), "my_list_name")

    def test_extract_cell_text(self):
        self.assertEqual(extract_cell_text(Text("Rich Text")), "Rich Text")
    
    def test_parse_tags(self):
        self.assertEqual(parse_tags("tech, growth, value"), ["tech", "growth", "value"])

    def test_format_tags(self):
        self.assertEqual(format_tags(["tech", "growth"]), "tech, growth")
        
    def test_match_tags(self):
        item_tags = ["tech", "growth"]
        self.assertTrue(match_tags(item_tags, ["growth"]))
        self.assertFalse(match_tags(item_tags, ["value"]))