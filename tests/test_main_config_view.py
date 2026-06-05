import unittest
from unittest.mock import MagicMock
from textual.app import App

from stockstui.ui.views.config_view import ConfigContainer


class MainConfigTestApp(App):
    """App wrapper for testing MainConfigView."""

    def __init__(self):
        super().__init__()
        self.config = MagicMock()
        self.config.settings = {
            "fred_settings": {"api_key": ""},
            "hidden_tabs": [],
        }
        self.config.get_setting.return_value = []
        self.theme_variables = {"text-muted": "dim"}
        self.cli_overrides = {}

    def compose(self):
        yield ConfigContainer()


class TestMainConfigView(unittest.IsolatedAsyncioTestCase):
    """Test suite for MainConfigView."""

    async def test_button_navigation(self):
        """Test buttons navigate to correct configuration screens."""
        app = MainConfigTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            container = app.query_one(ConfigContainer)

            # Initially we should be on main
            self.assertEqual(container.query_one("ContentSwitcher").current, "main")

            # Click "General Settings" button
            await pilot.click("#goto-general")
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "general")

            # Go back
            container.action_go_back()
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "main")

            # Click "Watchlists" button
            await pilot.click("#goto-lists")
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "lists")

            # Go back
            container.action_go_back()
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "main")

            # Click "FRED Settings" button
            await pilot.click("#goto-fred")
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "fred")
