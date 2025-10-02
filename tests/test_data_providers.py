import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from stockstui.data_providers.portfolio import PortfolioManager
from stockstui.data_providers import market_provider



class TestMarketProviderEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling in the market_provider."""

    def setUp(self):
        """Reset internal caches before each test."""
        market_provider._price_cache.clear()
        market_provider._info_cache.clear()
        market_provider._news_cache.clear()

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_historical_data_handles_error(self, mock_yf_ticker):
        """Test that get_historical_data returns an empty DataFrame on yfinance error."""
        mock_yf_ticker.return_value.history.side_effect = Exception("yfinance broke")
        mock_yf_ticker.return_value.info = {'currency': 'USD'}
        
        df = market_provider.get_historical_data("AAPL", "1mo")
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)
        self.assertEqual(df.attrs.get('error'), 'Data Error')

    
