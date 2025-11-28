import unittest
import pandas as pd
from rich.text import Text
from textual.app import App

from stockstui.presentation import formatter

class TestFormatter(unittest.IsolatedAsyncioTestCase):
    """Unit tests for data formatting functions."""

    async def test_format_historical_data_as_table(self):
        """Test formatting historical data into a DataTable."""
        # Daily data
        dates_daily = pd.to_datetime(['2025-01-01', '2025-01-02'])
        df_daily = pd.DataFrame({
            'Open': [100.0, 101.0], 'High': [105.0, 106.0],
            'Low': [99.0, 100.0], 'Close': [102.0, 103.0],
            'Volume': [1000, 2000]
        }, index=dates_daily)
        
        # We need an active app context for DataTable to measure columns
        app = App()
        async with app.run_test():
            table_daily = formatter.format_historical_data_as_table(df_daily)
            self.assertEqual(str(table_daily.columns['Date'].label), "Date")
            
            # Intraday data
            dates_intraday = pd.to_datetime(['2025-01-01 10:00', '2025-01-01 11:00'])
            df_intraday = pd.DataFrame({
                'Open': [100.0, 101.0], 'High': [105.0, 106.0],
                'Low': [99.0, 100.0], 'Close': [102.0, 103.0],
                'Volume': [1000, 2000]
            }, index=dates_intraday)
            
            table_intraday = formatter.format_historical_data_as_table(df_intraday)
            self.assertEqual(str(table_intraday.columns['Date'].label), "Timestamp")

    def test_format_price_data_for_table(self):
        """Test the formatting of price data, including change calculation and aliasing."""
        sample_data = [{
            'symbol': 'AAPL', 'description': 'Apple Inc.', 'price': 155.25,
            'previous_close': 150.00, 'day_low': 154.0, 'day_high': 156.0,
            'fifty_two_week_low': 120.0, 'fifty_two_week_high': 180.0
        }]
        old_prices = {'AAPL': 155.00} # Price went up
        alias_map = {'AAPL': 'My Apple Stock'}
        
        result = formatter.format_price_data_for_table(sample_data, old_prices, alias_map)
        
        self.assertEqual(len(result), 1)
        row = result[0]
        
        # Assert on dictionary keys
        self.assertEqual(row['Description'], 'My Apple Stock') # Alias should be used
        self.assertEqual(row['Price'], 155.25)
        self.assertAlmostEqual(row['Change'], 5.25)
        self.assertAlmostEqual(row['% Change'], 5.25 / 150.0)
        self.assertEqual(row["Day's Range"], '$154.00 - $156.00')
        self.assertEqual(row["52-Wk Range"], '$120.00 - $180.00')
        self.assertEqual(row['Ticker'], 'AAPL')
        self.assertEqual(row['_change_direction'], 'up') # Price increased vs old_prices

    def test_format_price_data_direction_down(self):
        """Test that change direction is 'down' when price decreases."""
        sample_data = [{'symbol': 'TSLA', 'price': 800.0}]
        old_prices = {'TSLA': 801.0}
        
        row = formatter.format_price_data_for_table(sample_data, old_prices, {})[0]
        self.assertEqual(row['_change_direction'], 'down')

    def test_format_price_data_direction_none(self):
        """Test that change direction is None when price is unchanged or old price is missing."""
        sample_data = [{'symbol': 'GOOG', 'price': 2800.0}]
        
        # No old price
        row_no_old = formatter.format_price_data_for_table(sample_data, {}, {})[0]
        self.assertIsNone(row_no_old['_change_direction'])

        # Same old price
        old_prices_same = {'GOOG': 2800.0}
        row_same = formatter.format_price_data_for_table(sample_data, old_prices_same, {})[0]
        self.assertIsNone(row_same['_change_direction'])

    def test_format_news_for_display(self):
        """Test formatting of news data into a markdown string."""
        sample_news = [{
            'source_ticker': 'NVDA', 'title': 'Big News!', 'link': 'http://example.com',
            'publisher': 'A Publisher', 'publish_time': '2025-08-19 12:00 UTC',
            'summary': 'A summary of the news.'
        }]
        
        markdown, urls = formatter.format_news_for_display(sample_news)
        
        self.assertIn("Source: **`NVDA`**", markdown)
        self.assertIn("**[Big News!](http://example.com)**", markdown)
        self.assertIn("By A Publisher at 2025-08-19 12:00 UTC", markdown)
        self.assertIn("A summary of the news.", markdown)
        self.assertEqual(urls, ['http://example.com'])
        
    def test_format_empty_news(self):
        """Test formatting for an empty news list."""
        markdown, urls = formatter.format_news_for_display([])
        self.assertIsInstance(markdown, Text)
        self.assertIn("No news found", markdown.plain)
        self.assertEqual(urls, [])

    def test_format_market_status(self):
        """Test the formatting of market status into a user-friendly string and styling info."""
        status_dict = {'calendar': 'NYSE', 'status': 'open', 'holiday': None, 'next_close': None}
        result = formatter.format_market_status(status_dict)
        text, text_parts = result
        self.assertIsInstance(text, str)
        self.assertIn('NYSE', text)
        self.assertIsInstance(text_parts, list)
        
        status_dict_holiday = {'calendar': 'NYSE', 'status': 'closed', 'holiday': 'Christmas', 'next_open': None, 'reason': 'holiday'}
        result_holiday = formatter.format_market_status(status_dict_holiday)
        self.assertIsNotNone(result_holiday)

        # Test invalid input
        self.assertIsNone(formatter.format_market_status(None))
        self.assertIsNone(formatter.format_market_status("not a dict"))

    def test_format_debug_tables(self):
        """Test formatting for various debug data tables."""
        # Ticker debug
        ticker_data = [{'symbol': 'A', 'is_valid': True, 'description': 'Desc', 'latency': 0.1}]
        rows_ticker = formatter.format_ticker_debug_data_for_table(ticker_data)
        self.assertEqual(rows_ticker[0], ('A', True, 'Desc', 0.1))
        
        # List debug
        list_data = [{'list_name': 'L1', 'ticker_count': 10, 'latency': 0.5}]
        rows_list = formatter.format_list_debug_data_for_table(list_data)
        self.assertEqual(rows_list[0], ('L1', 10, 0.5))
        
        # Cache test
        cache_data = [{'list_name': 'C1', 'ticker_count': 5, 'latency': 0.2}]
        rows_cache = formatter.format_cache_test_data_for_table(cache_data)
        self.assertEqual(rows_cache[0], ('C1', 5, 0.2))

    def test_format_info_comparison(self):
        """Test comparing fast and slow info dictionaries."""
        fast = {'a': 1, 'b': 2}
        slow = {'a': 1, 'b': 3, 'c': 4}
        
        rows = formatter.format_info_comparison(fast, slow)
        
        # Expect 3 rows: a (match), b (mismatch), c (missing in fast)
        self.assertEqual(len(rows), 3)
        
        # Check 'a' - match
        row_a = next(r for r in rows if r[0] == 'a')
        self.assertEqual(row_a, ('a', '1', '1', False))
        
        # Check 'b' - mismatch
        row_b = next(r for r in rows if r[0] == 'b')
        self.assertEqual(row_b, ('b', '2', '3', True))
        
        # Check 'c' - missing in fast
        row_c = next(r for r in rows if r[0] == 'c')
        self.assertEqual(row_c, ('c', 'N/A', '4', False))
        
        # Test error case
        rows_err = formatter.format_info_comparison({}, {})
        self.assertEqual(rows_err[0][0], "Error")

    def test_escape(self):
        """Test escaping special characters for Rich markdown."""
        text = "Hello [World] *"
        escaped = formatter.escape(text)
        self.assertEqual(escaped, r"Hello \[World\] \*")

if __name__ == '__main__':
    unittest.main()
