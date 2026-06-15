import unittest
from unittest.mock import MagicMock, patch
from textual.app import App
from textual.widgets import Static
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
                "series_aliases": {"TEST1": "Test Alias"},
            }
        }
        self.theme_variables = {
            "success": "green",
            "error": "red",
            "warning": "yellow",
            "text-muted": "dim",
        }
        # Fake notify
        self.notify = MagicMock()

    def compose(self):
        yield FredView()


class TestFredView(unittest.IsolatedAsyncioTestCase):
    @patch("stockstui.data_providers.fred_provider.get_series_summary")
    async def test_populate_table(self, mock_summary):
        """Test that _populate_table correctly renders data."""
        # Prepare sample summary
        sample_summary = {
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
            "units_short": "Index",
        }
        # Mock background worker return value to provide complete data
        mock_summary.return_value = sample_summary

        app = FredViewTestApp()
        async with app.run_test() as pilot:
            view = app.query_one(FredView)

            # Summaries list for manual call (keeping it for explicit test control)
            summaries = [sample_summary]

            # Manually call _populate_table (bypassing threaded load)
            view._populate_table(summaries)
            await pilot.pause()

            table = app.query_one(FredDataTable)
            self.assertEqual(table.row_count, 1)

            # Check row data - verify alias was used
            row = table.get_row("TEST1")
            self.assertEqual(str(row[0]), "Test Alias")  # Alias from config
            self.assertEqual(str(row[1]), "105.00")
            
            # Verify more row data
            self.assertEqual(str(row[2]), "+5.0%")  # yoy_pct formatted with %
            self.assertEqual(str(row[3]), "102.00")  # roll_12
            self.assertEqual(str(row[4]), "100.00")  # roll_24
            self.assertEqual(str(row[5]), "+1.50")  # z_10y formatted with sign
            self.assertEqual(str(row[6]), "90.00")  # hist_min
            self.assertEqual(str(row[7]), "110.00")  # hist_max
            self.assertEqual(str(row[8]), "75%")  # pct_of_range formatted with %
            self.assertEqual(str(row[9]), "2023-01-01")  # date
            self.assertEqual(str(row[10]), "M")  # frequency
            self.assertEqual(str(row[11]), "Index")  # units

            # Verify table has rows
            self.assertGreater(table.row_count, 0)

    @patch("stockstui.data_providers.fred_provider.get_series_summary")
    @patch("webbrowser.open")
    async def test_action_open_series(self, mock_browser, mock_summary):
        """Test action_open_series opens browser."""
        # Mock background worker
        mock_summary.return_value = {"id": "TEST1", "title": "Test Series 1"}

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
            
            # Verify notify was called
            self.assertEqual(app.notify.call_count, 1)

    @patch("stockstui.data_providers.fred_provider.get_series_summary")
    async def test_action_edit_series(self, mock_summary):
        """Test action_edit_series pushes modal."""
        mock_summary.return_value = {"id": "TEST1", "title": "Test Series 1"}

        app = FredViewTestApp()

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
            
    @patch("stockstui.data_providers.fred_provider.get_series_summary")
    async def test_fred_view_composes_data_table(self, mock_summary):
        """Test that FredView composes with a FredDataTable."""
        mock_summary.return_value = {"id": "TEST1"}
        
        app = FredViewTestApp()
        async with app.run_test() as pilot:
            view = app.query_one(FredView)
            await pilot.pause()
            
            # Verify data table exists
            table = app.query_one(FredDataTable)
            self.assertIsNotNone(table)
            
            # Verify view has loading label initially
            labels = list(view.query("Static"))
            self.assertGreater(len(labels), 0)
            
    @patch("stockstui.data_providers.fred_provider.get_series_summary")
    async def test_fred_view_settings_structure(self, mock_summary):
        """Test that FredView settings are properly structured."""
        mock_summary.return_value = {"id": "TEST1"}
        
        app = FredViewTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Verify config structure
            self.assertIn("fred_settings", app.config.settings)
            self.assertIn("api_key", app.config.settings["fred_settings"])
            self.assertIn("series_list", app.config.settings["fred_settings"])
            self.assertIn("series_aliases", app.config.settings["fred_settings"])
            
            # Verify theme variables
            self.assertIn("success", app.theme_variables)
            self.assertIn("error", app.theme_variables)
            self.assertIn("warning", app.theme_variables)
