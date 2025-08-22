import unittest
import pandas as pd
from unittest.mock import MagicMock
import tempfile
from pathlib import Path

from textual.widgets import DataTable, Static
from stockstui.ui.views.history_view import HistoryView
from stockstui.ui.widgets.history_chart import HistoryChart
from stockstui.main import StocksTUI
from tests.test_utils import TEST_APP_ROOT
from stockstui.config_manager import ConfigManager

class TestHistoryView(unittest.IsolatedAsyncioTestCase):
    """Isolated unit tests for the HistoryView widget."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.user_config_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_app_with_data(self, data):
        """Creates a real app instance with a temporary config and pre-loaded data."""
        app = StocksTUI()
        with unittest.mock.patch('stockstui.config_manager.PlatformDirs') as mock_dirs:
            mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
            app.config = ConfigManager(app_root=TEST_APP_ROOT.parent)
        app._load_and_register_themes()
        app._last_historical_data = data
        app._history_period = "1mo"
        return app

    async def test_renders_table_view_correctly(self):
        # FIX: Use a realistic DataFrame with all required OHLCV columns.
        dates = pd.to_datetime(['2025-08-18', '2025-08-19'])
        data = pd.DataFrame({
            'Open': [100.0, 101.5], 'High': [102.0, 103.0], 'Low': [99.5, 100.8],
            'Close': [101.0, 102.2], 'Volume': [1000000, 1200000]
        }, index=dates)
        app = self._setup_app_with_data(data)
        
        async with app.run_test() as pilot:
            history_view = HistoryView()
            await pilot.app.mount(history_view)
            await history_view._render_historical_data()
            await pilot.pause()
            
            table = history_view.query_one(DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(len(history_view.query(HistoryChart)), 0)

    async def test_renders_chart_view_when_toggled(self):
        dates = pd.to_datetime(['2025-08-18', '2025-08-19'])
        data = pd.DataFrame({'Close': [102, 103]}, index=dates)
        app = self._setup_app_with_data(data)
        
        async with app.run_test() as pilot:
            history_view = HistoryView()
            await pilot.app.mount(history_view)
            history_view.query_one("#history-view-toggle").value = True
            await history_view._render_historical_data()
            await pilot.pause()

            self.assertIsInstance(history_view.query_one(HistoryChart), HistoryChart)
            self.assertEqual(len(history_view.query(DataTable)), 0)

    async def test_renders_error_message_for_empty_data(self):
        empty_df = pd.DataFrame()
        empty_df.attrs = {'error': 'Invalid Ticker', 'symbol': 'BAD'}
        app = self._setup_app_with_data(empty_df)
        
        async with app.run_test() as pilot:
            history_view = HistoryView()
            await pilot.app.mount(history_view)
            await history_view._render_historical_data()
            await pilot.pause()

            message = history_view.query_one("#history-display-container > Static")
            self.assertIn("Invalid ticker", str(message.render()))
