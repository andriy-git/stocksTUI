import unittest
import asyncio
from unittest.mock import MagicMock

from tests.test_utils import create_test_app
from stockstui.ui.widgets.search_box import SearchBox
from stockstui.ui.views.config_view import ConfigContainer

# Import the real exception Textual raises when a query finds nothing.
try:
    # Textual 0.30+ locations
    from textual.css.query import NoMatches
except Exception:  # pragma: no cover - fallback for other versions
    # Very old fallback (kept to be resilient)
    from textual.css.query import QueryError as NoMatches


class TestAppRefreshActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = await create_test_app()

    def test_action_refresh_smart(self):
        self.app.get_active_category = MagicMock(return_value="stocks")
        self.app.config.lists = {"stocks": [{"ticker": "AAPL"}, {"ticker": "TSLA"}]}
        self.app._filter_symbols_by_tags = MagicMock(side_effect=lambda c, s: s)

        self.app.action_refresh(force=False)
        self.app.fetch_prices.assert_called_once_with(
            ["AAPL", "TSLA"], force=False, category="stocks"
        )

    def test_action_refresh_force(self):
        self.app.get_active_category = MagicMock(return_value="crypto")
        self.app.config.lists = {"crypto": [{"ticker": "BTC-USD"}]}
        self.app._filter_symbols_by_tags = MagicMock(side_effect=lambda c, s: s)

        self.app.action_refresh(force=True)
        self.app.fetch_prices.assert_called_once_with(
            ["BTC-USD"], force=True, category="crypto"
        )

    def test_action_refresh_with_tag_filter(self):
        self.app.get_active_category = MagicMock(return_value="stocks")
        self.app.config.lists = {"stocks": [{"ticker": "AAPL"}, {"ticker": "TSLA"}]}
        self.app._filter_symbols_by_tags = MagicMock(return_value=["TSLA"])

        self.app.action_refresh(force=False)
        self.app.fetch_prices.assert_called_once_with(
            ["TSLA"], force=False, category="stocks"
        )

    def test_action_refresh_all_category(self):
        self.app.get_active_category = MagicMock(return_value="all")
        self.app.config.lists = {
            "stocks": [{"ticker": "AAPL"}, {"ticker": "TSLA"}],
            "indices": [{"ticker": "TSLA"}, {"ticker": "^GSPC"}],
        }
        self.app._filter_symbols_by_tags = MagicMock(side_effect=lambda c, s: s)

        self.app.action_refresh(force=False)
        expected_symbols = ["AAPL", "TSLA", "^GSPC"]
        self.app.fetch_prices.assert_called_once_with(
            expected_symbols, force=False, category="all"
        )


class TestAppSortActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = await create_test_app()

    def test_action_enter_sort_mode(self):
        """Entering sort mode should set _sort_mode and update the status label."""
        self.app.get_active_category = MagicMock(return_value="stocks")

        # Mock the status label that gets updated
        mock_label = MagicMock()
        self.app.query_one = MagicMock(return_value=mock_label)

        self.app.action_enter_sort_mode()

        # Check that sort mode is enabled and status label was updated
        self.assertTrue(self.app._sort_mode)
        mock_label.update.assert_called_once_with(
            "SORT BY: \[d]escription, \[p]rice, \[c]hange, p\[e]rcent, \[t]icker, \[u]ndo, \[ESC]ape"
        )

    def test_action_enter_sort_mode_on_invalid_tab(self):
        self.app.get_active_category = MagicMock(return_value="news")
        self.app.action_enter_sort_mode()
        # Expecting a bell or some form of feedback on invalid context.
        self.app.bell.assert_called_once()


class TestAppNavigationActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = await create_test_app()

    def test_action_back_or_dismiss_clears_sort_mode(self):
        # This test keeps behavior validation local and simple.
        self.app._sort_mode = True
        self.app.get_active_category = MagicMock(return_value="stocks")
        self.app.action_back_or_dismiss()
        self.assertFalse(self.app._sort_mode)

    def test_action_back_or_dismiss_removes_search_box(self):
        """When a SearchBox is present, dismiss should remove it."""
        # Provide a fake mounted SearchBox the app can 'find' and remove.
        mock_search_box = MagicMock(spec=SearchBox)
        self.app.query_one = MagicMock(return_value=mock_search_box)

        self.app.action_back_or_dismiss()

        # We don't rely on Textual's async remove semantics in tests; just assert it's invoked.
        mock_search_box.remove.assert_called_once()

    def test_action_back_or_dismiss_navigates_config_view(self):
        """If no SearchBox is mounted and the current view is Configs, delegate to go_back."""
        self.app.get_active_category = MagicMock(return_value="configs")

        mock_container = MagicMock(spec=ConfigContainer)
        mock_container.action_go_back.return_value = True

        # First call: looking for SearchBox -> raise the *real* NoMatches
        # Second call: looking for ConfigContainer -> return the container
        self.app.query_one = MagicMock(side_effect=[NoMatches("no SearchBox"), mock_container])

        self.app.action_back_or_dismiss()

        mock_container.action_go_back.assert_called_once()


class TestAppFilterActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = await create_test_app()
        self.app.get_active_category = MagicMock(return_value="stocks")

    def test_action_toggle_tag_filter_with_no_tags(self):
        # Provide a TagFilter-like object with no tags available.
        mock_tag_filter = MagicMock()
        mock_tag_filter.available_tags = []
        mock_tag_filter.display = False
        self.app.query_one = MagicMock(return_value=mock_tag_filter)

        self.app.action_toggle_tag_filter()

        self.app.notify.assert_called_once_with(
            "No tags available for this list.", severity="information"
        )
        self.app.bell.assert_called_once()
        self.assertFalse(mock_tag_filter.display)
