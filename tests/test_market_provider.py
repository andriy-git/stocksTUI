import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from stockstui.data_providers import market_provider

class TestMarketProvider(unittest.TestCase):
    """
    Unit tests for the market_provider module.
    Uses patching to mock the yfinance API, allowing tests to run without
    making actual network requests.
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
        
        # FIX: Configure the mock to simulate the `tickers['TICKER']` access pattern.
        mock_yf_tickers.return_value.tickers = {'AAPL': mock_ticker_obj}
        
        data = market_provider.get_market_price_data(['AAPL'])
        
        mock_yf_tickers.assert_called_with("AAPL")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['symbol'], 'AAPL')
        self.assertEqual(data[0]['price'], 155.0)
        self.assertIn('AAPL', market_provider._price_cache)

    @patch('stockstui.data_providers.market_provider.get_market_status')
    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_uses_cache(self, mock_yf_tickers, mock_market_status):
        """Test that fresh, cached data is used instead of making an API call."""
        
        now = datetime.now(timezone.utc)
        market_provider._price_cache['GOOG'] = {
            'expiry': now + timedelta(hours=1),
            'data': {'symbol': 'GOOG', 'price': 2800.0}
        }
        
        # Simulate market closed so only the slow cache is checked.
        mock_market_status.return_value = {'is_open': False}
        data = market_provider.get_market_price_data(['GOOG'])
        
        # yfinance should NOT have been called for slow data.
        mock_yf_tickers.assert_not_called()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['price'], 2800.0)

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_fetches_expired(self, mock_yf_tickers):
        """Test that expired cached data triggers a new API call."""

        now = datetime.now(timezone.utc)
        market_provider._price_cache['MSFT'] = {
            'expiry': now - timedelta(minutes=1),
            'data': {'symbol': 'MSFT', 'price': 300.0}
        }

        mock_ticker_obj = MagicMock()
        mock_ticker_obj.info = {'currency': 'USD', 'longName': 'Microsoft'}
        mock_ticker_obj.fast_info = {'lastPrice': 305.0}
        mock_yf_tickers.return_value.tickers = {'MSFT': mock_ticker_obj}
        
        data = market_provider.get_market_price_data(['MSFT'])
        
        mock_yf_tickers.assert_called_with("MSFT")
        self.assertEqual(data[0]['price'], 305.0)

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_force_refresh(self, mock_yf_tickers):
        """Test that force_refresh=True ignores a fresh cache entry."""

        now = datetime.now(timezone.utc)
        market_provider._price_cache['TSLA'] = {
            'expiry': now + timedelta(hours=1),
            'data': {'symbol': 'TSLA', 'price': 800.0}
        }
        
        mock_ticker_obj = MagicMock()
        mock_ticker_obj.info = {'currency': 'USD', 'longName': 'Tesla'}
        mock_ticker_obj.fast_info = {'lastPrice': 810.0}
        mock_yf_tickers.return_value.tickers = {'TSLA': mock_ticker_obj}

        data = market_provider.get_market_price_data(['TSLA'], force_refresh=True)

        mock_yf_tickers.assert_called_with("TSLA")
        self.assertEqual(data[0]['price'], 810.0)
        
    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_news_data(self, mock_yf_ticker):
        """Test fetching and processing of news data."""
        mock_yf_ticker.return_value.news = [{
            'content': {
                'title': 'Test News',
                'summary': 'A summary.',
                'provider': {'displayName': 'Test Provider'},
                'canonicalUrl': {'url': 'http://news.com'},
                'pubDate': '2025-08-19T12:00:00.000Z'
            }
        }]
        
        mock_yf_ticker.return_value.info = {'currency': 'USD'}
        
        news = market_provider.get_news_data('AAPL')
        
        self.assertEqual(len(news), 1)
        item = news[0]
        self.assertEqual(item['title'], 'Test News')
        self.assertEqual(item['publisher'], 'Test Provider')
        self.assertIn('AAPL', market_provider._news_cache)
