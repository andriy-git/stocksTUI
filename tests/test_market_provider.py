import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pandas as pd
import pytz

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
        market_provider._market_calendars.clear()

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

    @patch('stockstui.data_providers.market_provider.datetime')
    @patch('stockstui.data_providers.market_provider.pd.Timestamp.now')
    @patch('stockstui.data_providers.market_provider.mcal.get_calendar')
    @patch('stockstui.data_providers.market_provider.yf.Tickers')
    def test_cache_invalidated_after_market_open(self, mock_yf_tickers, mock_get_calendar, mock_pd_now, mock_dt):
        """
        Test that the price cache is correctly invalidated after a new market session opens.
        This ensures that stale 'previous_close' values are not used.
        """
        # 1. --- Setup a predictable market calendar ---
        mock_calendar = MagicMock()
        schedule = pd.DataFrame({
            'market_open': [
                pd.Timestamp('2025-08-18 09:30:00-0400', tz='America/New_York'),
                pd.Timestamp('2025-08-19 09:30:00-0400', tz='America/New_York')
            ],
            'market_close': [
                pd.Timestamp('2025-08-18 16:00:00-0400', tz='America/New_York'),
                pd.Timestamp('2025-08-19 16:00:00-0400', tz='America/New_York')
            ]
        }, index=pd.to_datetime(['2025-08-18', '2025-08-19']))
        mock_calendar.schedule.return_value = schedule
        mock_calendar.tz = 'America/New_York'
        mock_get_calendar.return_value = mock_calendar

        # 2. --- Simulate Day 1: Initial fetch and cache population ---
        day1_noon_utc = datetime(2025, 8, 18, 16, 0, 0, tzinfo=timezone.utc)
        day1_noon_ny = pd.Timestamp(day1_noon_utc).tz_convert('America/New_York')
        mock_dt.now.return_value = day1_noon_utc
        mock_pd_now.return_value = day1_noon_ny

        mock_ticker_obj1 = MagicMock()
        mock_ticker_obj1.info = {'regularMarketPreviousClose': 100.0, 'currency': 'USD', 'exchange': 'NYSE'}
        mock_ticker_obj1.fast_info = {'lastPrice': 105.0}
        mock_yf_tickers.return_value.tickers = {'AAPL': mock_ticker_obj1}

        market_provider.get_market_price_data(['AAPL'])
        self.assertEqual(mock_yf_tickers.call_count, 2, "Initial fetch should make two API calls (slow and fast).")
        self.assertEqual(market_provider._price_cache['AAPL']['data']['previous_close'], 100.0)

        # 3. --- Simulate Day 2: Time passes, market opens ---
        day2_noon_utc = datetime(2025, 8, 19, 16, 0, 0, tzinfo=timezone.utc)
        day2_noon_ny = pd.Timestamp(day2_noon_utc).tz_convert('America/New_York')
        mock_dt.now.return_value = day2_noon_utc
        mock_pd_now.return_value = day2_noon_ny

        mock_ticker_obj2 = MagicMock()
        mock_ticker_obj2.info = {'regularMarketPreviousClose': 105.0, 'currency': 'USD', 'exchange': 'NYSE'}
        mock_ticker_obj2.fast_info = {'lastPrice': 110.0}
        mock_yf_tickers.return_value.tickers = {'AAPL': mock_ticker_obj2}

        # 4. --- Trigger the function again (no force refresh) ---
        market_provider.get_market_price_data(['AAPL'], force_refresh=False)

        # 5. --- Assert the correct behavior ---
        self.assertEqual(mock_yf_tickers.call_count, 4, "The API was not called again on the new day; the stale cache was used.")
        self.assertEqual(market_provider._price_cache['AAPL']['data']['previous_close'], 105.0)

    def test_unknown_exchange_status(self):
        """Test that unknown exchanges default to appropriate fallback status."""
        unknown_exchange = "UNKNOWN_EXCHANGE"
        status = market_provider.get_market_status(unknown_exchange)
        self.assertEqual(status['calendar'], unknown_exchange)
        # Unknown exchanges default to Open/True in fallback
        self.assertTrue(status['is_open'], "Unknown exchange should default to Open (fallback behavior)")

    @patch('stockstui.data_providers.market_provider.yf.Ticker')
    @patch('stockstui.data_providers.market_provider.pd')
    @patch('stockstui.data_providers.market_provider.mcal')
    def test_gspc_exchange_mapping(self, mock_mcal, mock_pd, mock_ticker):
        """Test correct mapping of SNP/GSPC to NYSE and status check."""
        import logging
        logging.basicConfig(level=logging.ERROR)
        import pandas as real_pd
        
        # Configure mock_pd to use real pandas classes
        mock_pd.Timedelta = real_pd.Timedelta
        mock_pd.DataFrame = real_pd.DataFrame
        
        # Mock Timestamp.now to return 02:00 AM ET (Closed)
        mock_now = real_pd.Timestamp("2025-12-11 02:00:00-05:00")
        
        # We need mock_pd.Timestamp to maintain the Mock structure for .now() patching
        # But allow constructor calls to pass through to real Timestamp
        mock_pd.Timestamp.now.side_effect = lambda tz=None: mock_now.astimezone(tz) if tz else mock_now
        
        mock_instance = mock_ticker.return_value
        mock_instance.info = {'exchange': 'SNP', 'currency': 'USD'}
        mock_pd.Timestamp.side_effect = lambda *args, **kwargs: real_pd.Timestamp(*args, **kwargs)
        
        # Setup mock calendar
        mock_cal = MagicMock()
        mock_cal.tz = pytz.timezone('America/New_York')
        mock_mcal.get_calendar.return_value = mock_cal
        
        # Setup mock schedule with valid data to prevent 'RangeIndex' errors
        # Create a schedule that indicates market is CLOSED at 2 AM
        # But has valid open/close times for the day
        schedule_df = pd.DataFrame({
            'market_open': [pd.Timestamp("2025-12-11 09:30:00-05:00")],
            'market_close': [pd.Timestamp("2025-12-11 16:00:00-05:00")]
        }, index=pd.DatetimeIndex([pd.Timestamp("2025-12-11")]))
        mock_cal.schedule.return_value = schedule_df
        
        info = market_provider.get_ticker_info("^GSPC")
        exchange = info.get('exchange')
        
        status = market_provider.get_market_status(exchange)
        
        # VERIFY MAPPING: Ensure get_calendar was called with 'NYSE', not 'SNP'
        mock_mcal.get_calendar.assert_called_with('NYSE')
        
        self.assertFalse(status['is_open'], f"Exchange {exchange} resulted in is_open=True")
        self.assertEqual(status['status'], 'closed', "Should be closed at 2:00 AM")
