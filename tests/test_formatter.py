import unittest
import pandas as pd
from rich.text import Text

from stockstui.presentation import formatter

class TestFormatter(unittest.TestCase):
    """Unit tests for data formatting functions."""

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
        
        # Unpack the tuple for assertions
        desc, price, change, pct, day_r, wk_r, sym, direction = row
        
        self.assertEqual(desc, 'My Apple Stock') # Alias should be used
        self.assertEqual(price, 155.25)
        self.assertAlmostEqual(change, 5.25)
        self.assertAlmostEqual(pct, 5.25 / 150.0)
        self.assertEqual(day_r, '$154.00 - $156.00')
        self.assertEqual(wk_r, '$120.00 - $180.00')
        self.assertEqual(sym, 'AAPL')
        self.assertEqual(direction, 'up') # Price increased vs old_prices

    def test_format_price_data_direction_down(self):
        """Test that change direction is 'down' when price decreases."""
        sample_data = [{'symbol': 'TSLA', 'price': 800.0}]
        old_prices = {'TSLA': 801.0}
        
        row = formatter.format_price_data_for_table(sample_data, old_prices, {})[0]
        self.assertEqual(row[-1], 'down') # Last element is direction

    def test_format_price_data_direction_none(self):
        """Test that change direction is None when price is unchanged or old price is missing."""
        sample_data = [{'symbol': 'GOOG', 'price': 2800.0}]
        
        # No old price
        row_no_old = formatter.format_price_data_for_table(sample_data, {}, {})[0]
        self.assertIsNone(row_no_old[-1])

        # Same old price
        old_prices_same = {'GOOG': 2800.0}
        row_same = formatter.format_price_data_for_table(sample_data, old_prices_same, {})[0]
        self.assertIsNone(row_same[-1])

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
        """Test the extraction of data from the market status dictionary."""
        status_dict = {'calendar': 'NYSE', 'status': 'open', 'holiday': None}
        result = formatter.format_market_status(status_dict)
        self.assertEqual(result, ('NYSE', 'open', None))
        
        status_dict_holiday = {'calendar': 'NYSE', 'status': 'closed', 'holiday': 'Christmas'}
        result_holiday = formatter.format_market_status(status_dict_holiday)
        self.assertEqual(result_holiday, ('NYSE', 'closed', 'Christmas'))

        # Test invalid input
        self.assertIsNone(formatter.format_market_status(None))
        self.assertIsNone(formatter.format_market_status("not a dict"))

if __name__ == '__main__':
    unittest.main()
