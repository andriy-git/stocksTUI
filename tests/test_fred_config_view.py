import unittest
from textual.app import App
from textual.widgets import DataTable, Input, Button, Switch
from unittest.mock import MagicMock, AsyncMock, patch

from stockstui.ui.views.config_views.fred_config_view import FredConfigView
from stockstui.ui.modals import AddFredSeriesModal


class FredConfigTestApp(App):
    """App for testing FredConfigView."""

    def __init__(self):
        super().__init__()
        self.config = MagicMock()
        self.config.get_setting.return_value = []
        self.config.settings = {
            "hidden_tabs": [],
            "fred_settings": {
                "api_key": "fake_key",
                "series_list": ["TEST1", "TEST2"],
                "series_aliases": {"TEST1": "Alias1"},
                "series_descriptions": {},
            }
        }
        self.theme_variables = {"text-muted": "dim"}
        self.notify = MagicMock()
        self._rebuild_app = AsyncMock()

    def compose(self):
        yield FredConfigView()


class TestFredConfigView(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patcher = patch("stockstui.ui.views.config_views.fred_config_view.FredConfigView._fetch_descriptions")
        self.mock_fetch = self.patcher.start()

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_initial_population(self):
        """Test table populates on mount."""
        app = FredConfigTestApp()
        async with app.run_test():
            table = app.query_one(DataTable)
            self.assertEqual(table.row_count, 2)

            # Check row 1
            row1 = table.get_row("TEST1")
            self.assertEqual(row1[0], "TEST1")
            self.assertIn("Alias1", str(row1[1]))

    async def test_save_api_key(self):
        """Test saving API key."""
        app = FredConfigTestApp()
        # Increase size to ensure visibility
        async with app.run_test(size=(120, 40)) as pilot:
            inp = app.query_one("#fred-api-key-input", Input)

            # Change value
            inp.value = "new_key"

            # Use programmatic press to avoid OutOfBounds issues with scrolling/layout in test env
            app.query_one("#save-fred-api-key", Button).press()
            await pilot.pause()

            # Check config updated
            settings = app.config.settings["fred_settings"]
            self.assertEqual(settings["api_key"], "new_key")
            app.config.save_settings.assert_called()

    async def test_remove_series(self):
        """Test removing a series."""
        app = FredConfigTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            table = app.query_one(DataTable)

            # Select row 0 (TEST1)
            table.focus()
            table.cursor_coordinate = (0, 0)

            app.query_one("#remove-fred-series", Button).press()
            await pilot.pause()

            # Verify removed from settings
            settings = app.config.settings["fred_settings"]
            self.assertNotIn("TEST1", settings["series_list"])
            self.assertNotIn("TEST1", settings["series_aliases"])

            # Verify table updated
            self.assertEqual(table.row_count, 1)

    async def test_move_series_down(self):
        """Test moving series down."""
        app = FredConfigTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            table = app.query_one(DataTable)

            # List is [TEST1, TEST2]
            # Select TEST1 (index 0)
            table.focus()
            table.cursor_coordinate = (0, 0)

            app.query_one("#move-fred-series-down", Button).press()
            await pilot.pause()

            # New list should be [TEST2, TEST1]
            settings = app.config.settings["fred_settings"]
            self.assertEqual(settings["series_list"], ["TEST2", "TEST1"])

    async def test_add_series_flow(self):
        """Test adding a series via modal callback simulation."""
        app = FredConfigTestApp()

        # Mock push_screen to capture callback
        app.push_screen = MagicMock()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#add-fred-series", Button).press()
            await pilot.pause()

            # Verify push_screen called with AddFredSeriesModal
            app.push_screen.assert_called_once()
            args, _ = app.push_screen.call_args
            self.assertIsInstance(args[0], AddFredSeriesModal)
            callback = args[1]

            # Simulate modal returning ("NEW", "New Alias", "Note", "Tags")
            # (Note: AddTickerModal/AddFredSeriesModal return tuple)
            callback(("NEW_SERIES", "New Alias", "", ""))
            await pilot.pause()

            # Verify config updated
            settings = app.config.settings["fred_settings"]
            self.assertIn("NEW_SERIES", settings["series_list"])
            self.assertEqual(settings["series_aliases"]["NEW_SERIES"], "New Alias")

    async def test_toggle_fred_visibility(self):
        """Test toggling FRED tab visibility."""
        app = FredConfigTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            switch = app.query_one("#fred-visibility-switch", Switch)
            self.assertTrue(switch.value)

            # Programmatically change switch to False
            switch.value = False
            await pilot.pause()

            # Verify hidden_tabs updated to include 'fred'
            self.assertIn("fred", app.config.settings["hidden_tabs"])
            app._rebuild_app.assert_called_once_with("configs", config_sub_view="fred")

            # Toggle back to True
            switch.value = True
            await pilot.pause()

            # Verify 'fred' removed from hidden_tabs
            self.assertNotIn("fred", app.config.settings["hidden_tabs"])
