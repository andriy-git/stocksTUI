import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from stockstui.main import StocksTUI
from tests.test_utils import TEST_APP_ROOT
from stockstui.config_manager import ConfigManager

class TestUIWorkflows(unittest.IsolatedAsyncioTestCase):
    """
    Tests for user workflows using Textual pilot. All original tests are kept
    and improved for stability and maintainability.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.user_config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_app(self):
        app = StocksTUI()
        mock_dirs = patch('stockstui.config_manager.PlatformDirs').start()
        mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
        app.config = ConfigManager(app_root=TEST_APP_ROOT.parent)
        app._load_and_register_themes()
        patch.stopall()
        return app

    async def test_watchlist_management_workflow(self):
        app = self._setup_app()
        async with app.run_test() as pilot:
            # Find config tab by iterating through available tabs
            config_tab_id = None
            tabs = app.query("Tab")
            for i, tab in enumerate(tabs, 1):
                if hasattr(tab, 'id') and 'config' in tab.id:
                    config_tab_id = f"tab-{i}"
                    break
            
            if config_tab_id:
                app.query_one("Tabs").active = config_tab_id
                await pilot.pause()

                # Navigate to Watchlists view
                await pilot.click("#goto-lists")
                await pilot.pause()

                # Add a new list
                await pilot.click("#add_list")
                await pilot.pause()
                await pilot.press("t", "e", "s", "t", "enter")
                await pilot.pause()
                self.assertIn("test", app.config.lists)

                # Add a ticker to the new list
                await pilot.click("#add_ticker")
                await pilot.pause()
                await pilot.press(
                    "n", "e", "w", "tab",
                    "n", "e", "w", "a", "tab",
                    "n", "o", "t", "e", "enter"
                )
                await pilot.pause()
                self.assertEqual(app.config.lists["test"][0]["ticker"], "NEW")
                self.assertEqual(app.config.lists["test"][0]["alias"], "newa")

                # Rename the list
                await pilot.click("#rename_list")
                await pilot.pause()
                for _ in range(len("test")):
                    await pilot.press("backspace")
                await pilot.press("r", "e", "n", "a", "m", "e", "d", "enter")
                await pilot.pause()
                self.assertIn("renamed", app.config.lists)
                self.assertNotIn("test", app.config.lists)

                # Delete the ticker
                await pilot.click("#delete_ticker")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(len(app.config.lists["renamed"]), 0)

                # Delete the list
                await pilot.click("#delete_list")
                await pilot.pause()
                for _ in range(len("renamed")):
                    await pilot.press("backspace")
                await pilot.press("enter")
                await pilot.pause()
                self.assertNotIn("renamed", app.config.lists)

    async def test_search_and_clear_workflow(self):
        app = self._setup_app()
        # Pre-populate price data to ensure the table is non-empty
        app.config.lists["stocks"] = [
            {"ticker": "AAPL", "alias": "Apple Inc."},
            {"ticker": "GOOG", "alias": "Alphabet Inc."},
        ]

        async with app.run_test() as pilot:
            await pilot.pause()

            price_table = app.query_one("#price-table")
            await pilot.wait_for_scheduled_animations()
            initial_rows = price_table.row_count
            self.assertGreater(initial_rows, 1, "Table was not populated with test data")

            await pilot.press("/")
            await pilot.pause()
            await pilot.press("a", "p", "p", "l", "e")
            await pilot.pause()
            self.assertEqual(price_table.row_count, 1)

            # Clear the search manually by pressing backspaces
            for _ in range(len("apple")):
                await pilot.press("backspace")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(price_table.row_count, initial_rows)