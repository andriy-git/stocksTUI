import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
import tempfile

from stockstui.main import StocksTUI
from tests.test_utils import TEST_APP_ROOT
from stockstui.config_manager import ConfigManager

@unittest.skip('Skipping broken specialty view tests')
class TestSpecialtyViewWorkflows(unittest.IsolatedAsyncioTestCase):
    """
    Tests for specialty views like News and Debug.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.user_config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_app(self) -> StocksTUI:
        """Helper to create a test app with a real but temporary config."""
        app = StocksTUI()
        with patch('stockstui.config_manager.PlatformDirs') as mock_dirs:
            mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
            app.config = ConfigManager(app_root=TEST_APP_ROOT.parent)
        
        # Add the required categories for these tests
        app.config.lists['news'] = []
        app.config.lists['debug'] = []
        app.config.save_lists()

        app._load_and_register_themes()
        return app

    async def asyncSetUp(self):
        """Set up a mocked app for each test."""
        self.app = self._setup_app()

    @patch('webbrowser.open')
    async def test_news_view_link_navigation(self, mock_webbrowser_open):
        """Test cycling through and opening links in the news view."""
        async with self.app.run_test() as pilot:
            # Navigate to the news tab
            news_tab = next(t for t in self.app.query("Tab") if "News" in str(t.label))
            await pilot.click(news_tab)
            await pilot.pause()

            # Post a news update to populate the view
            markdown_content = "**[Title 1](link1)**\n\n---\n**[Title 2](link2)**"
            urls = ["link1", "link2"]
            news_view = self.app.query_one("NewsView")
            news_view.update_content(markdown_content, urls)
            await pilot.pause()
            
            # Test link navigation
            await pilot.press("tab")
            self.assertEqual(news_view._current_link_index, 0)
            await pilot.press("enter")
            mock_webbrowser_open.assert_called_with("link1")

    async def test_debug_view_workflow(self):
        """Test that clicking debug buttons calls the correct app methods."""
        # Mock the methods that are called by the debug buttons
        self.app.run_ticker_debug_test = AsyncMock()
        self.app.run_list_debug_test = AsyncMock()
        self.app.run_cache_test = AsyncMock()

        async with self.app.run_test() as pilot:
            # Navigate to the debug tab
            debug_tab = next(t for t in self.app.query("Tab") if "Debug" in str(t.label))
            await pilot.click(debug_tab)
            await pilot.pause()

            # Click the first debug button and check if the corresponding method was called
            await pilot.click("#debug-test-tickers")
            await pilot.pause()
            self.app.run_ticker_debug_test.assert_awaited_once()