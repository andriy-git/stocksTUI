import unittest
from unittest.mock import MagicMock, AsyncMock
from textual.widgets import Tabs, Label
from textual.coordinate import Coordinate

from tests.test_utils import create_test_app
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable

try:
    from textual.css.query import NoMatches
except Exception:
    from textual.css.query import QueryError as NoMatches


class TestAppOpenMode(unittest.IsolatedAsyncioTestCase):
    """Tests for the 'o' key open mode feature."""

    async def asyncSetUp(self):
        self.app = await create_test_app()
        self.app.get_active_category = MagicMock(return_value="stocks")
        self.app.tab_map = [
            {'name': 'All', 'category': 'all'},
            {'name': 'Stocks', 'category': 'stocks'},
            {'name': 'History', 'category': 'history'},
            {'name': 'News', 'category': 'news'},
            {'name': 'Options', 'category': 'options'},
        ]

    async def test_action_enter_open_mode_activates_mode(self):
        """Entering open mode should set _open_mode and update the status label."""
        # Setup mocks
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = 0  # Valid row selected
        
        mock_status_label = MagicMock(spec=Label)
        mock_status_label.renderable = "Original status"
        
        self.app.query_one = MagicMock(side_effect=[mock_price_table, mock_status_label])
        
        # Execute
        await self.app.action_enter_open_mode()
        
        # Verify
        self.assertTrue(self.app._open_mode)
        mock_status_label.update.assert_called_once_with(
            'OPEN IN: \\[n]ews, \\[h]istory, \\[o]ptions, \\[y]ahoo Finance, \\[ESC]ape'
        )
        self.assertEqual(self.app._original_status_text, "Original status")

    async def test_action_enter_open_mode_no_row_selected(self):
        """Entering open mode with no row selected should ring bell."""
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = -1  # No row selected
        
        self.app.query_one = MagicMock(return_value=mock_price_table)
        
        await self.app.action_enter_open_mode()
        
        self.assertFalse(self.app._open_mode)
        self.app.bell.assert_called_once()

    async def test_action_enter_open_mode_invalid_category(self):
        """Entering open mode from invalid category should ring bell."""
        self.app.get_active_category = MagicMock(return_value="news")
        
        await self.app.action_enter_open_mode()
        
        self.assertFalse(self.app._open_mode)
        self.app.bell.assert_called_once()

    async def test_double_o_opens_in_options(self):
        """Pressing 'o' twice should enter open mode then open in Options."""
        # First press: enter open mode
        self.app._open_mode = False
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = 0
        mock_status_label = MagicMock(spec=Label)
        self.app.query_one = MagicMock(side_effect=[mock_price_table, mock_status_label])
        
        await self.app.action_enter_open_mode()
        self.assertTrue(self.app._open_mode)
        
        # Second press: should open in options
        # Reset query_one for the second call
        mock_price_table2 = MagicMock(spec=NavigableDataTable)
        mock_price_table2.cursor_row = 0
        
        # Mock coordinate_to_cell_key to return the ticker
        mock_cell_key = MagicMock()
        mock_row_key = MagicMock()
        mock_row_key.value = "AAPL"
        mock_cell_key.row_key = mock_row_key
        mock_price_table2.coordinate_to_cell_key.return_value = mock_cell_key
        
        mock_tabs = MagicMock(spec=Tabs)
        
        self.app.query_one = MagicMock(side_effect=[mock_price_table2, mock_tabs])
        self.app.action_back_or_dismiss = MagicMock()  # Mock to prevent actual dismissal logic
        
        await self.app.action_enter_open_mode()
        
        # Verify options ticker was set and tab was activated
        self.assertEqual(self.app.options_ticker, "AAPL")
        self.assertEqual(mock_tabs.active, "tab-5")  # Options is index 5 (1-indexed)

    async def test_handle_open_key_news(self):
        """Pressing 'n' in open mode should open ticker in News."""
        self.app._open_mode = True
        
        # Mock price table with ticker
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = 0
        mock_cell_key = MagicMock()
        mock_row_key = MagicMock()
        mock_row_key.value = "TSLA"
        mock_cell_key.row_key = mock_row_key
        mock_price_table.coordinate_to_cell_key.return_value = mock_cell_key
        
        mock_tabs = MagicMock(spec=Tabs)
        
        self.app.query_one = MagicMock(side_effect=[mock_price_table, mock_tabs])
        self.app.action_back_or_dismiss = MagicMock()
        
        await self.app.action_handle_open_key('n')
        
        self.assertEqual(self.app.news_ticker, "TSLA")
        self.assertEqual(mock_tabs.active, "tab-4")  # News is index 4

    async def test_handle_open_key_history(self):
        """Pressing 'h' in open mode should open ticker in History."""
        self.app._open_mode = True
        
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = 0
        mock_cell_key = MagicMock()
        mock_row_key = MagicMock()
        mock_row_key.value = "GOOGL"
        mock_cell_key.row_key = mock_row_key
        mock_price_table.coordinate_to_cell_key.return_value = mock_cell_key
        
        mock_tabs = MagicMock(spec=Tabs)
        
        self.app.query_one = MagicMock(side_effect=[mock_price_table, mock_tabs])
        self.app.action_back_or_dismiss = MagicMock()
        
        await self.app.action_handle_open_key('h')
        
        self.assertEqual(self.app.history_ticker, "GOOGL")
        self.assertEqual(mock_tabs.active, "tab-3")  # History is index 3

    async def test_handle_open_key_extracts_ticker_correctly(self):
        """Should extract ticker from row_key, not display text."""
        self.app._open_mode = True
        
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = 0
        
        # Simulate a row with alias "Pepsi" but ticker "PEP"
        mock_cell_key = MagicMock()
        mock_row_key = MagicMock()
        mock_row_key.value = "PEP"  # The actual ticker, not "Pepsi"
        mock_cell_key.row_key = mock_row_key
        mock_price_table.coordinate_to_cell_key.return_value = mock_cell_key
        
        mock_tabs = MagicMock(spec=Tabs)
        
        self.app.query_one = MagicMock(side_effect=[mock_price_table, mock_tabs])
        self.app.action_back_or_dismiss = MagicMock()
        
        await self.app.action_handle_open_key('o')
        
        # Should use "PEP" not "Pepsi"
        self.assertEqual(self.app.options_ticker, "PEP")

    async def test_handle_open_key_not_in_open_mode(self):
        """Should do nothing if not in open mode."""
        self.app._open_mode = False
        initial_news_ticker = self.app.news_ticker
        
        await self.app.action_handle_open_key('n')
        
        # Should not have set any ticker
        self.assertEqual(self.app.news_ticker, initial_news_ticker)

    async def test_handle_open_key_no_row_selected(self):
        """Should dismiss if no row selected."""
        self.app._open_mode = True
        
        mock_price_table = MagicMock(spec=NavigableDataTable)
        mock_price_table.cursor_row = -1  # No row
        
        self.app.query_one = MagicMock(return_value=mock_price_table)
        self.app.action_back_or_dismiss = MagicMock()
        
        await self.app.action_handle_open_key('n')
        
        self.app.action_back_or_dismiss.assert_called_once()

    async def test_back_or_dismiss_clears_open_mode(self):
        """Pressing ESC should clear open mode and restore status label."""
        self.app._open_mode = True
        self.app._original_status_text = "Original"
        
        mock_status_label = MagicMock(spec=Label)
        self.app.query_one = MagicMock(return_value=mock_status_label)
        
        self.app.action_back_or_dismiss()
        
        self.assertFalse(self.app._open_mode)
        mock_status_label.update.assert_called_once_with("Original")


if __name__ == '__main__':
    unittest.main()
