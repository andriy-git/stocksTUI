import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import datetime
from datetime import timezone, timedelta
import pandas as pd
from stockstui.data_providers import market_provider

class TestMarketProviderCoverage(unittest.TestCase):
    """Comprehensive tests for market_provider.py."""

    def setUp(self):
        """Reset caches before each test."""
        market_provider._price_cache.clear()
        market_provider._info_cache.clear()
        market_provider._news_cache.clear()
        market_provider._market_calendars.clear()

    def test_cache_population_and_retrieval(self):
        """Test populating and retrieving cache states."""
        price_data = {'AAPL': {'data': 'foo'}}
        info_data = {'AAPL': {'exchange': 'NYSE'}}
        
        market_provider.populate_price_cache(price_data)
        market_provider.populate_info_cache(info_data)
        
        self.assertEqual(market_provider.get_price_cache_state(), price_data)
        self.assertEqual(market_provider.get_info_cache_state(), info_data)
        
        self.assertTrue(market_provider.is_cached('AAPL'))
        self.assertEqual(market_provider.get_cached_price('AAPL'), 'foo')
        self.assertIsNone(market_provider.get_cached_price('GOOG'))

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_uncached(self, mock_tickers):
        """Test fetching data for uncached tickers."""
        # Setup mocks
        mock_ticker_obj = MagicMock()
        mock_tickers.return_value.tickers = {'AAPL': mock_ticker_obj}
        
        # Mock slow info
        mock_ticker_obj.info = {
            'currency': 'USD', 'exchange': 'NYSE', 'shortName': 'Apple', 
            'longName': 'Apple Inc.', 'currentPrice': 150.0
        }
        # Mock fast info
        mock_ticker_obj.fast_info = {'lastPrice': 150.0}
        
        # Mock market status to be open so it fetches fast data
        with patch('stockstui.data_providers.market_provider.get_market_status') as mock_status:
            mock_status.return_value = {'is_open': True}
            
            data = market_provider.get_market_price_data(['AAPL'])
            
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['symbol'], 'AAPL')
            self.assertEqual(data[0]['price'], 150.0)
            
            # Verify cache was updated
            self.assertTrue(market_provider.is_cached('AAPL'))

    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_get_market_price_data_cached_fresh(self, mock_tickers):
        """Test that fresh cached data prevents new fetches."""
        # Populate cache with fresh data
        future = datetime.datetime.now(timezone.utc) + timedelta(hours=1)
        market_provider._price_cache['AAPL'] = {
            'expiry': future,
            'data': {'symbol': 'AAPL', 'price': 100.0}
        }
        
        # Mock market status closed so no fast data fetch
        with patch('stockstui.data_providers.market_provider.get_market_status') as mock_status:
            mock_status.return_value = {'is_open': False}
            
            data = market_provider.get_market_price_data(['AAPL'])
            
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['price'], 100.0)
            mock_tickers.assert_not_called()

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_ticker_info(self, mock_ticker):
        """Test fetching ticker info."""
        mock_instance = mock_ticker.return_value
        mock_instance.info = {'currency': 'USD', 'exchange': 'NYSE', 'shortName': 'Apple'}
        
        info = market_provider.get_ticker_info('AAPL')
        self.assertEqual(info['exchange'], 'NYSE')
        self.assertIn('AAPL', market_provider._info_cache)
        
        # Test cached return
        info_cached = market_provider.get_ticker_info('AAPL')
        self.assertEqual(info_cached, info)

    def test_get_market_status_unknown_calendar(self):
        """Test market status for unknown calendar."""
        status = market_provider.get_market_status('UNKNOWN_CAL')
        self.assertEqual(status['status'], 'unknown')
        self.assertTrue(status['is_open'])

    @patch('stockstui.data_providers.market_provider.mcal')
    def test_get_market_status_open(self, mock_mcal):
        """Test market status when market is open."""
        if mock_mcal is None: self.skipTest("pandas_market_calendars not installed")
        
        mock_cal = MagicMock()
        mock_mcal.get_calendar.return_value = mock_cal
        
        # Mock schedule
        now = pd.Timestamp.now(tz=timezone.utc)
        mock_cal.tz = timezone.utc
        
        # Create a schedule where now is between open and close
        schedule_df = pd.DataFrame({
            'market_open': [now - timedelta(hours=1)],
            'market_close': [now + timedelta(hours=6)],
            'premarket_open': [now - timedelta(hours=2)],
            'premarket_close': [now - timedelta(hours=1)],
            'postmarket_open': [now + timedelta(hours=6)],
            'postmarket_close': [now + timedelta(hours=10)]
        }, index=[now.floor('D')])
        
        mock_cal.schedule.return_value = schedule_df
        
        status = market_provider.get_market_status('NYSE')
        self.assertEqual(status['status'], 'open')
        self.assertTrue(status['is_open'])

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_news_data(self, mock_ticker):
        """Test fetching news data."""
        mock_instance = mock_ticker.return_value
        mock_instance.news = [{
            'content': {
                'title': 'News Title',
                'pubDate': '2025-01-01T12:00:00Z',
                'provider': {'displayName': 'Publisher'}
            }
        }]
        # Need info to proceed
        with patch('stockstui.data_providers.market_provider.get_ticker_info') as mock_info:
            mock_info.return_value = {'exchange': 'NYSE'}
            
            news = market_provider.get_news_data('AAPL')
            self.assertEqual(len(news), 1)
            self.assertEqual(news[0]['title'], 'News Title')
            self.assertEqual(news[0]['publisher'], 'Publisher')
            
            # Verify cache
            self.assertIn('AAPL', market_provider._news_cache)

    def test_run_debug_tests(self):
        """Test debug helper functions."""
        # Cache test
        market_provider._price_cache['AAPL'] = {'data': {'price': 100}}
        results = market_provider.run_cache_test({'List1': ['AAPL']})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['list_name'], 'List1')
        
        # Ticker debug test
        with patch('stockstui.data_providers.market_provider.yf.Ticker') as mock_ticker:
            mock_ticker.return_value.info = {'currency': 'USD', 'longName': 'Apple'}
            results = market_provider.run_ticker_debug_test(['AAPL'])
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]['is_valid'])

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    def test_get_ticker_info_comparison(self, mock_ticker):
        """Test comparing fast and slow info."""
        mock_instance = mock_ticker.return_value
        mock_instance.fast_info = {'price': 100}
        mock_instance.info = {'currentPrice': 100}
        
        comp = market_provider.get_ticker_info_comparison('AAPL')
        self.assertEqual(comp['fast'], {'price': 100})
        self.assertEqual(comp['slow'], {'currentPrice': 100})

if __name__ == '__main__':
    unittest.main()
