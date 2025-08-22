import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from stockstui.data_providers import market_provider

class TestMarketProvider(unittest.TestCase):
    """
    Unit tests for the market_provider module.
    """

    def setUp(self):
        """Reset the internal caches before each test."""
        market_provider._price_cache.clear()
        market_provider._info_cache.clear()
        market_provider._news_cache.clear()

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_fetches_uncached(self, mock_yf_tickers):
        """Test that data is fetched for tickers not present in the cache."""
        mock_ticker_obj = MagicMock()
        mock_ticker_obj.info = {
            'currency': 'USD', 'longName': 'Apple Inc.', 'exchange': 'NMS',
            'regularMarketPreviousClose': 150.0
        }
        mock_ticker_obj.fast_info = {'lastPrice': 155.0}
        mock_yf_tickers.return_value.tickers = {'AAPL': mock_ticker_obj}
        
        data = market_provider.get_market_price_data(['AAPL'])
        self.assertEqual(data[0]['symbol'], 'AAPL')

    @patch('stockstui.data_providers.market_provider.get_market_status')
    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_uses_cache(self, mock_yf_tickers, mock_market_status):
        """Test that fresh, cached data is used instead of making an API call."""
        now = datetime.now(timezone.utc)
        market_provider._price_cache['GOOG'] = {
            'expiry': now + timedelta(hours=1),
            'data': {'symbol': 'GOOG', 'price': 2800.0}
        }
        mock_market_status.return_value = {'is_open': False}
        market_provider.get_market_price_data(['GOOG'])
        mock_yf_tickers.assert_not_called()

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_fetch_slow_data_handles_exception(self, mock_yf_tickers):
        """Test graceful failure when fetching slow data fails."""
        mock_yf_tickers.return_value.tickers.__getitem__.side_effect = Exception("API Error")
        market_provider._fetch_and_cache_slow_data(['FAIL'])
        self.assertEqual(market_provider._price_cache['FAIL']['data']['description'], "Data Unavailable")

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_ticker_info_handles_exception(self, mock_yf_ticker):
        """Test graceful failure when get_ticker_info fails."""
        mock_yf_ticker.return_value.info = {}
        self.assertIsNone(market_provider.get_ticker_info('BAD'))
        mock_yf_ticker.side_effect = Exception("API Error")
        self.assertIsNone(market_provider.get_ticker_info('ERROR'))

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_news_for_invalid_ticker(self, mock_yf_ticker):
        """Test that get_news returns None for an invalid ticker."""
        mock_yf_ticker.return_value.info = {}
        self.assertIsNone(market_provider.get_news_data('INVALID'))
        
    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_news_data_handles_malformed_items(self, mock_yf_ticker):
        """Test that news parsing is resilient to missing data fields."""
        mock_yf_ticker.return_value.info = {'currency': 'USD'}
        # This item is missing 'summary', 'provider', and 'canonicalUrl'
        mock_yf_ticker.return_value.news = [{
            'content': { 'title': 'Test News', 'pubDate': '2025-08-19T12:00:00.000Z' }
        }]
        
        # The call should not raise an exception
        news = market_provider.get_news_data('AAPL')
        
        self.assertEqual(len(news), 1)
        item = news[0]
        self.assertEqual(item['title'], 'Test News')
        self.assertEqual(item['summary'], 'N/A')
        self.assertEqual(item['publisher'], 'N/A')
        self.assertEqual(item['link'], '#')
