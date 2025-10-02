import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from stockstui.main import StocksTUI
from tests.test_utils import TEST_APP_ROOT
from stockstui.config_manager import ConfigManager

class TestAppStartup(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.user_config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_test_app(self, cli_overrides=None):
        app = StocksTUI(cli_overrides=cli_overrides or {})
        mock_dirs = patch('stockstui.config_manager.PlatformDirs').start()
        mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
        app.config = ConfigManager(app_root=TEST_APP_ROOT.parent)
        app._load_and_register_themes()
        
        # Initialize session lists if provided - convert strings to dict format
        if cli_overrides and 'session_list' in cli_overrides:
            for list_name, tickers in cli_overrides['session_list'].items():
                app.config.lists[list_name] = [{"ticker": ticker} for ticker in tickers]
        
        patch.stopall()
        return app

    async def test_startup_with_news_ticker_override(self):
        app = self._setup_test_app(cli_overrides={'news': 'AAPL'})
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.get_active_category(), 'news')
            self.assertEqual(app.news_ticker, 'AAPL')

    async def test_startup_with_history_ticker_and_period_override(self):
        app = self._setup_test_app(cli_overrides={'history': 'TSLA', 'period': '5y', 'chart': True})
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.get_active_category(), 'history')
            self.assertEqual(app.history_ticker, 'TSLA')
            chart_switch = app.query_one("#history-view-toggle")
            self.assertTrue(chart_switch.value)

    async def test_startup_with_tab_override(self):
        app = self._setup_test_app(cli_overrides={'tab': 'crypto'})
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.get_active_category(), 'crypto')

    async def test_startup_with_session_list(self):
        app = self._setup_test_app(cli_overrides={
            'session_list': {'tempsession': ['GM', 'F']},
            'tab': 'tempsession'
        })
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.get_active_category(), 'tempsession')
            self.assertTrue(any(t['category'] == 'tempsession' for t in app.tab_map))