import unittest
from unittest.mock import MagicMock, patch
from textual.app import App
from textual.widgets import DataTable
from stockstui.ui.views.fred_view import FredView, FredDataTable

class FredViewTestApp(App):
    """App for testing FredView with mocked config."""
    def __init__(self):
        super().__init__()
        self.config = MagicMock()
        self.config.settings = {
            "fred_settings": {
                "api_key": "fake_key",
                "series_list": ["TEST1"],
                "series_aliases": {"TEST1": "Test Alias"}
            }
        }
        self.theme_variables = {
            "success": "green",
            "error": "red",
            "warning": "yellow",
            "text-muted": "dim"
        }
        # Fake notify
        self.notify = MagicMock()

    def compose(self):
        yield FredView()

class TestFredView(unittest.IsolatedAsyncioTestCase):
    
    @patch('stockstui.data_providers.fred_provider.get_series_summary')
    async def test_populate_table(self, mock_summary):
        """Test that _populate_table correctly renders data."""
        # Mock background worker return value to avoid network call errors
        mock_summary.return_value = {"id": "TEST1"} 

        app = FredViewTestApp()
        async with app.run_test() as pilot:
            view = app.query_one(FredView)
            
            # Prepare sample summaries
            summaries = [{
                "id": "TEST1",
                "title": "Test Series 1",
                "current": 105.0,
                "yoy_pct": 5.0,
                "roll_12": 102.0,
                "roll_24": 100.0,
                "z_10y": 1.5,
                "hist_min_10y": 90.0,
                "hist_max_10y": 110.0,
                "pct_of_range": 75.0,
                "date": "2023-01-01",
                "frequency": "M",
                "units_short": "Index"
            }]
            
            # Manually call _populate_table (bypassing threaded load)
            view._populate_table(summaries)
            await pilot.pause()
            
            table = app.query_one(FredDataTable)
            self.assertEqual(table.row_count, 1)
            
            # Check row data - verify alias was used
            row = table.get_row("TEST1")
            self.assertEqual(str(row[0]), "Test Alias") # Alias from config
            self.assertEqual(str(row[1]), "105.00")
            
            # Verify styling is applied (rudimentary check logic ran without error)

    @patch('stockstui.data_providers.fred_provider.get_series_summary')
    @patch('webbrowser.open')
    async def test_action_open_series(self, mock_browser, mock_summary):
        """Test action_open_series opens browser."""
        # Mock background worker
        mock_summary.return_value = {"id": "TEST1"}

        app = FredViewTestApp()
        async with app.run_test() as pilot:
            view = app.query_one(FredView)
            table = app.query_one(FredDataTable)
            
            # Populate
            view._populate_table([{"id": "TEST1", "current": 100}])
            await pilot.pause()
            
            # Select the row
            table.focus()
            table.cursor_coordinate = (0, 0)
            
            # Trigger action
            view.action_open_series()
            await pilot.pause()
            
            mock_browser.assert_called_with("https://fred.stlouisfed.org/series/TEST1")

    @patch('stockstui.data_providers.fred_provider.get_series_summary')
    async def test_action_edit_series(self, mock_summary):
        """Test action_edit_series pushes modal."""
        mock_summary.return_value = {"id": "TEST1"}
        
        app = FredViewTestApp()
        
        # Mock push_screen on the app instance
        # We can't mock app.push_screen easily because App overrides it?
        # Instead, verify push_screen behavior or mock it on the instance before run?
        # Textual apps are tricky. Let's rely on checking the screen stack?
        # But isolated test case might not support screen stack inspection easily if modal is pushed?
        
        # Strategy: Mock app.push_screen AFTER init but before acting
        # We'll use a wrapper or patch object
        
        async with app.run_test() as pilot:
            view = app.query_one(FredView)
            table = app.query_one(FredDataTable)
            
            # Populate
            view._populate_table([{"id": "TEST1", "current": 100}])
            await pilot.pause()
            
            table.focus()
            table.cursor_coordinate = (0, 0)
            
            # Mock push_screen
            app.push_screen = MagicMock()
            
            view.action_edit_series()
            await pilot.pause()
            
            app.push_screen.assert_called_once()
            args, _ = app.push_screen.call_args
            modal = args[0]
            self.assertEqual(modal.series_id, "TEST1")
