import os
import unittest
from stockstui.data_providers import market_provider

class TestLiveApiIntegration(unittest.TestCase):
    """
    A suite of tests that make real network calls to the yfinance API.
    
    These tests are designed to be run infrequently (e.g., in CI) to validate
    our assumptions about the API's response structure. They do NOT test for
    specific price values, only for the presence and types of expected data fields.
    """

    def setUp(self):
        """Clear the provider's caches to ensure a real network call is made."""
        market_provider._price_cache.clear()
        market_provider._info_cache.clear()

    def test_get_market_price_data_structure(self):
        """
        Fetches live data for a common ticker (AAPL) and verifies the structure
        of the returned dictionary.
        """
        # We test with a well-known, highly available ticker.
        tickers = ['AAPL']
        
        # Act
        data = market_provider.get_market_price_data(tickers, force_refresh=True)
        
        # Assert
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        
        item = data[0]
        self.assertIsInstance(item, dict)
        
        # Check for key presence and correct types
        self.assertEqual(item['symbol'], 'AAPL')
        self.assertIn('description', item)
        self.assertIsInstance(item['description'], str)
        self.assertIn('price', item)
        self.assertIsInstance(item['price'], (float, int))
        self.assertIn('previous_close', item)
        self.assertIsInstance(item['previous_close'], (float, int))

    def test_get_historical_data_structure(self):
        """
        Fetches live historical data and verifies the resulting DataFrame structure.
        """
        # Act
        df = market_provider.get_historical_data('MSFT', period='5d')
        
        # Assert
        import pandas as pd
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        
        # Check for expected columns
        expected_columns = {'Open', 'High', 'Low', 'Close', 'Volume'}
        self.assertTrue(expected_columns.issubset(df.columns))
        
        # Check the symbol attribute
        self.assertEqual(df.attrs.get('symbol'), 'MSFT')

if __name__ == '__main__':
    unittest.main()
