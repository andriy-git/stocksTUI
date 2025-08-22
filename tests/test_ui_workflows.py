import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import asyncio

from stockstui.main import StocksTUI
from tests.test_utils import TEST_APP_ROOT
from stockstui.config_manager import ConfigManager

class TestUIWorkflows(unittest.IsolatedAsyncioTestCase):
    """Tests for common user interaction workflows using Textual's headless pilot."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.user_config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_app(self) -> StocksTUI:
        """Helper to create a test app with a real but temporary config."""
        app = StocksTUI()
        with unittest.mock.patch('stockstui.config_manager.PlatformDirs') as mock_dirs:
            mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
            app.config = ConfigManager(app_root=TEST_APP_ROOT.parent)
        
        # Ensure all tabs are visible for workflow tests to prevent StopIteration.
        app.config.settings['hidden_tabs'] = []
        
        app._load_and_register_themes()
        return app

    async def wait_for_modal_dismissal(self, pilot, modal_type_name="Modal", max_attempts=20):
        """Wait for modal to be dismissed by checking if it's still in the screen stack."""
        for _ in range(max_attempts):
            # Check if any screen in the stack is a modal
            modal_still_present = any(
                modal_type_name in type(screen).__name__ 
                for screen in pilot.app.screen_stack
            )
            
            if not modal_still_present:
                return True
            await asyncio.sleep(0.1)
        return False

    async def test_full_lists_config_workflow(self):
        """
        A comprehensive test of the ListsConfigView, covering adding, renaming,
        moving, and deleting both lists and the tickers within them.
        """
        app = self._setup_app()
        app.config.save_lists = MagicMock()

        async with app.run_test() as pilot:
            # 1. Navigate to the Config -> Lists screen
            await pilot.pause()
            config_tab = next(tab for tab in pilot.app.query("Tab") if "Configs" in str(tab.label))
            app.query_one("Tabs").active = config_tab.id
            await pilot.pause()
            await pilot.click("#goto-lists")
            await pilot.pause()

            # 2. Add two new lists
            await pilot.click("#add_list")
            await pilot.pause()
            await pilot.press("l", "i", "s", "t", "_", "b", "enter")
            
            # Wait for modal to be dismissed
            modal_dismissed = await self.wait_for_modal_dismissal(pilot, "AddListModal")
            self.assertTrue(modal_dismissed, "Modal was not dismissed in time")
            
            # Wait a bit more for UI to update
            await pilot.pause()
            
            await pilot.click("#add_list")
            await pilot.pause()
            await pilot.press("l", "i", "s", "t", "_", "a", "enter")
            
            # Wait for modal to be dismissed again
            modal_dismissed = await self.wait_for_modal_dismissal(pilot, "AddListModal")
            self.assertTrue(modal_dismissed, "Modal was not dismissed in time")
            
            await pilot.pause()

            self.assertIn("list_b", app.config.lists)
            self.assertIn("list_a", app.config.lists)

            # 3. Rename a list (list_a should be selected by default)
            await pilot.click("#rename_list")
            await pilot.pause()
            for _ in "list_a": await pilot.press("backspace")
            await pilot.press("renamed", "_", "list", "enter")
            
            # Wait for modal to be dismissed
            modal_dismissed = await self.wait_for_modal_dismissal(pilot, "RenameListModal")
            self.assertTrue(modal_dismissed, "Modal was not dismissed in time")
            
            await pilot.pause()
            self.assertIn("renamed_list", app.config.lists)
            self.assertNotIn("list_a", app.config.lists)

            # 4. Move 'renamed_list' down (it's currently selected)
            list_view = app.query_one("#symbol-list-view")
            self.assertEqual(list_view.children[list_view.index].name, "renamed_list")
            await pilot.click("#move_list_down")
            await pilot.pause()
            await pilot.pause()
            keys = list(app.config.lists.keys())
            self.assertTrue(keys.index("list_b") < keys.index("renamed_list"))
            
            # 5. Add tickers to the currently selected list ('renamed_list')
            await pilot.click("#add_ticker"); await pilot.pause()
            await pilot.press("TICK1", "tab", "alias1", "enter"); await pilot.pause()
            await pilot.click("#add_ticker"); await pilot.pause()
            await pilot.press("TICK2", "tab", "alias2", "enter"); await pilot.pause()
            self.assertEqual(len(app.config.lists["renamed_list"]), 2)

            # 6. Edit a ticker (TICK2 is selected as it was added last)
            await pilot.click("#edit_ticker"); await pilot.pause()
            await pilot.press("tab", *"_EDITED"); await pilot.click("#save"); await pilot.pause()
            self.assertEqual(app.config.lists["renamed_list"][1]["alias"], "alias2_EDITED")

            # 7. Move a ticker up
            ticker_table = app.query_one("#ticker-table")
            self.assertEqual(ticker_table.cursor_row, 1) # TICK2 is at index 1
            await pilot.click("#move_ticker_up"); await pilot.pause()
            self.assertEqual(app.config.lists["renamed_list"][0]["ticker"], "TICK2")
            
            # 8. Delete a ticker (TICK2 is now at index 0 and selected)
            await pilot.click("#delete_ticker"); await pilot.pause()
            await pilot.press("enter"); await pilot.pause()
            self.assertEqual(len(app.config.lists["renamed_list"]), 1)
            
            # 9. Delete a list
            await pilot.click("#delete_list"); await pilot.pause()
            await pilot.press("r", "e", "n", "a", "m", "e", "d", "_", "l", "i", "s", "t", "enter")
            
            # Wait for modal to be dismissed
            modal_dismissed = await self.wait_for_modal_dismissal(pilot, "DeleteListModal")
            self.assertTrue(modal_dismissed, "Modal was not dismissed in time")
            
            await pilot.pause()
            self.assertNotIn("renamed_list", app.config.lists)

    async def test_search_and_clear_workflow(self):
        """Test searching in a price table and clearing the search."""
        app = self._setup_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            price_table = app.query_one("#price-table")
            initial_rows = price_table.row_count
            self.assertGreater(initial_rows, 1)

            await pilot.press("/")
            await pilot.pause()
            await pilot.press("a", "p", "p", "l", "e")
            await pilot.pause()
            self.assertEqual(price_table.row_count, 1)
            
            for _ in "apple": await pilot.press("backspace")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(price_table.row_count, initial_rows)

    @patch('stockstui.main.StocksTUI.run_ticker_debug_test')
    @patch('stockstui.main.StocksTUI.run_list_debug_test')
    @patch('stockstui.main.StocksTUI.run_cache_test')
    async def test_debug_view_workflow(self, mock_cache_test, mock_list_test, mock_ticker_test):
        """Test that clicking debug buttons calls the correct app methods."""
        app = self._setup_app()
        app.run_ticker_debug_test = mock_ticker_test
        app.run_list_debug_test = mock_list_test
        app.run_cache_test = mock_cache_test

        async with app.run_test() as pilot:
            await pilot.pause()
            debug_tab = next(tab for tab in pilot.app.query("Tab") if "Debug" in str(tab.label))
            app.query_one("Tabs").active = debug_tab.id
            await pilot.pause()

            buttons = app.query("Button")
            for button in buttons: button.disabled = False
            
            await pilot.click("#debug-test-tickers"); await pilot.pause()
            mock_ticker_test.assert_called_once()
            for button in buttons: button.disabled = False

            await pilot.click("#debug-test-lists"); await pilot.pause()
            mock_list_test.assert_called_once()
            for button in buttons: button.disabled = False

            await pilot.click("#debug-test-cache"); await pilot.pause()
            mock_cache_test.assert_called_once()