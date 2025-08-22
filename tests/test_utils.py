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
    app.config.get_setting.return_value = "gruvbox_soft_dark"
    app.config.lists = {"stocks": [], "crypto": []}

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
    
    # Updated tab map to match actual app structure
    app.tab_map = [
        {"category": "stocks"},
        {"category": "crypto"},
        {"category": "news"},
        {"category": "history"},
        {"category": "configs"},
    ]
    
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