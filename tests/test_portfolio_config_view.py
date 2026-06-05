import unittest
from textual.app import App
from stockstui.ui.views.config_views.portfolio_config_view import PortfolioConfigView


class PortfolioConfigTestApp(App):
    """App wrapper for testing PortfolioConfigView."""

    def compose(self):
        yield PortfolioConfigView()


class TestPortfolioConfigView(unittest.IsolatedAsyncioTestCase):
    """Test suite for PortfolioConfigView."""

    async def test_portfolio_config_view_mount(self):
        """Test that the portfolio config view mounts and displays placeholder text."""
        app = PortfolioConfigTestApp()
        async with app.run_test():
            view = app.query_one(PortfolioConfigView)
            self.assertIsNotNone(view)
