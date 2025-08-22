import unittest
from unittest.mock import MagicMock, patch

from textual.app import App
from textual.widgets import DataTable, Select, Markdown
from textual.theme import Theme
from textual import on

from stockstui.common import TickerDebugDataUpdated
from stockstui.ui.views.debug_view import DebugView
from stockstui.ui.views.news_view import NewsView
from stockstui.ui.views.config_view import ConfigContainer
from stockstui.ui.views.config_views.general_config_view import GeneralConfigView
from stockstui.ui.views.config_views.lists_config_view import ListsConfigView
from stockstui.presentation import formatter

class ViewsTestApp(App):
    """A minimal app for testing individual views."""
    def __init__(self, view_to_test):
        super().__init__()
        self.view_to_test = view_to_test
        # Mock necessary app attributes that views might access
        self.config = MagicMock()
        self.config.lists.values.return_value = []
        self.config.get_setting.return_value = "default_theme"
        self.config.themes = { "default_theme": {"palette": {}} }
        self.config.settings = {'theme': 'default_theme', 'auto_refresh': False}
        self.cli_overrides = {}
        self.news_ticker = None
        self._news_content_for_ticker = None
        self._last_news_content = None
        self.fetch_news = MagicMock()
        self.theme_variables = {}
        self.active_list_category = "stocks"
        self.market_status_timer = None
        self.fetch_market_status = MagicMock()
        self._rebuild_app = MagicMock()
        self._manage_price_refresh_timer = MagicMock()

    def on_mount(self):
        # Correctly register a valid Theme object before mounting.
        default_theme = Theme( name="default_theme", primary="blue", dark=True)
        self.register_theme(default_theme)
        self.mount(self.view_to_test)

    def run_ticker_debug_test(self, symbols):
        """Mock method for testing."""
        pass

    @on(TickerDebugDataUpdated)
    async def on_ticker_debug_data_updated(self, message: TickerDebugDataUpdated):
        """This handler is a simplified version of the one in the main app."""
        try:
            view = self.query_one(DebugView)
            dt = view.query_one("#debug-table", DataTable)
            dt.loading = False
            dt.clear()
            rows = formatter.format_ticker_debug_data_for_table(message.data)
            for row in rows:
                dt.add_row(*row)
        except Exception:
            pass

class TestDebugView(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the DebugView."""

    async def test_debug_view_populates_table(self):
        """Test that the view correctly populates its table on message."""
        view = DebugView()
        app = ViewsTestApp(view)
        
        async with app.run_test() as pilot:
            await pilot.click("#debug-test-tickers")
            await pilot.pause()
            
            message = TickerDebugDataUpdated(
                data=[{"symbol": "AAPL", "is_valid": True, "description": "Apple", "latency": 0.5}],
                total_time=0.5
            )
            app.post_message(message)
            await pilot.pause()

            table = view.query_one(DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(str(table.get_cell_at((0, 0))), "AAPL")

class TestNewsView(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the NewsView."""

    async def test_news_view_fetches_on_submit(self):
        """Test that submitting the input triggers a news fetch."""
        view = NewsView()
        app = ViewsTestApp(view)
        async with app.run_test() as pilot:
            input_widget = view.query_one("#news-ticker-input")
            input_widget.value = "TSLA"
            view.on_news_ticker_submitted(input_widget.Submitted(input_widget, "TSLA"))
            await pilot.pause()
            app.fetch_news.assert_called_once_with("TSLA")

    @patch('webbrowser.open')
    async def test_news_view_link_navigation(self, mock_webbrowser_open):
        """Test cycling through and opening links in the news view."""
        view = NewsView()
        app = ViewsTestApp(view)
        async with app.run_test() as pilot:
            markdown_content = (
                "**[Title 1](link1)**\n\n---\n**[Title 2](link2)**\n\n---\n"
            )
            urls = ["link1", "link2"]
            view.update_content(markdown_content, urls)
            await pilot.pause()
            
            # Cycle forward
            await pilot.press("tab")
            self.assertEqual(view._current_link_index, 0)
            await pilot.press("tab")
            self.assertEqual(view._current_link_index, 1)
            await pilot.press("tab") # Wraps around
            self.assertEqual(view._current_link_index, 0)

            # Cycle backward
            await pilot.press("shift+tab") # Wraps around
            self.assertEqual(view._current_link_index, 1)

            # Open link
            await pilot.press("enter")
            mock_webbrowser_open.assert_called_once_with("link2")

class TestConfigContainer(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the main ConfigContainer."""
    
    async def test_config_container_navigation(self):
        """Test the view switching and history logic."""
        container = ConfigContainer()
        app = ViewsTestApp(container)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "main")

            container.show_lists()
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "lists")
            
            container.action_go_back()
            await pilot.pause()
            self.assertEqual(container.query_one("ContentSwitcher").current, "main")

class TestListsConfigView(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the ListsConfigView."""

    async def test_repopulate_lists_and_tickers(self):
        """Test that the list and ticker tables populate from app config."""
        view = ListsConfigView()
        app = ViewsTestApp(view)
        
        app.config.lists = {
            "stocks": [{"ticker": "AAPL", "alias": "Apple"}],
            "crypto": [{"ticker": "BTC-USD", "alias": "Bitcoin"}]
        }
        app.active_list_category = "stocks"

        async with app.run_test() as pilot:
            await pilot.pause()

            list_view = view.query_one("#symbol-list-view")
            self.assertEqual(list_view.index, 0)
            self.assertEqual(len(list_view.children), 2)

            ticker_table = view.query_one("#ticker-table")
            self.assertEqual(ticker_table.row_count, 1)
            self.assertEqual(str(ticker_table.get_cell_at((0, 0))), "AAPL")
