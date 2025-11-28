import unittest
from textual.validation import ValidationResult
from stockstui.common import (
    PriceDataUpdated, NewsDataUpdated, MarketStatusUpdated,
    HistoricalDataUpdated, TickerInfoComparisonUpdated,
    TickerDebugDataUpdated, ListDebugDataUpdated, CacheTestDataUpdated,
    PortfolioChanged, PortfolioDataUpdated, OptionsDataUpdated,
    OptionsExpirationsUpdated, NotEmpty
)

class TestCommonMessages(unittest.TestCase):
    """Tests for message classes in common.py to ensure full coverage."""

    def test_price_data_updated(self):
        msg = PriceDataUpdated([{'a': 1}], 'stocks')
        self.assertEqual(msg.data, [{'a': 1}])
        self.assertEqual(msg.category, 'stocks')

    def test_news_data_updated(self):
        msg = NewsDataUpdated('AAPL', [{'title': 'foo'}])
        self.assertEqual(msg.tickers_str, 'AAPL')
        self.assertEqual(msg.data, [{'title': 'foo'}])

    def test_market_status_updated(self):
        msg = MarketStatusUpdated({'status': 'open'})
        self.assertEqual(msg.status, {'status': 'open'})

    def test_historical_data_updated(self):
        msg = HistoricalDataUpdated({'df': 'fake'})
        self.assertEqual(msg.data, {'df': 'fake'})

    def test_ticker_info_comparison_updated(self):
        msg = TickerInfoComparisonUpdated({'fast': 1}, {'slow': 2})
        self.assertEqual(msg.fast_info, {'fast': 1})
        self.assertEqual(msg.slow_info, {'slow': 2})

    def test_ticker_debug_data_updated(self):
        msg = TickerDebugDataUpdated([{'d': 1}], 1.5)
        self.assertEqual(msg.data, [{'d': 1}])
        self.assertEqual(msg.total_time, 1.5)

    def test_list_debug_data_updated(self):
        msg = ListDebugDataUpdated([{'d': 1}], 2.5)
        self.assertEqual(msg.data, [{'d': 1}])
        self.assertEqual(msg.total_time, 2.5)

    def test_cache_test_data_updated(self):
        msg = CacheTestDataUpdated([{'d': 1}], 0.5)
        self.assertEqual(msg.data, [{'d': 1}])
        self.assertEqual(msg.total_time, 0.5)

    def test_portfolio_changed(self):
        msg = PortfolioChanged('p1')
        self.assertEqual(msg.portfolio_id, 'p1')

    def test_portfolio_data_updated(self):
        msg = PortfolioDataUpdated('p1', ['AAPL'])
        self.assertEqual(msg.portfolio_id, 'p1')
        self.assertEqual(msg.tickers, ['AAPL'])

    def test_options_data_updated(self):
        msg = OptionsDataUpdated('AAPL', '2025-01-01', 'calls', 'puts', {'u': 1})
        self.assertEqual(msg.ticker, 'AAPL')
        self.assertEqual(msg.expiration, '2025-01-01')
        self.assertEqual(msg.calls_data, 'calls')
        self.assertEqual(msg.puts_data, 'puts')
        self.assertEqual(msg.underlying, {'u': 1})

    def test_options_expirations_updated(self):
        msg = OptionsExpirationsUpdated('AAPL', ('2025-01-01',))
        self.assertEqual(msg.ticker, 'AAPL')
        self.assertEqual(msg.expirations, ('2025-01-01',))

class TestValidators(unittest.TestCase):
    """Tests for validators in common.py."""

    def test_not_empty_validator(self):
        validator = NotEmpty()
        
        # Valid case
        result = validator.validate("valid")
        self.assertTrue(result.is_valid)
        
        # Invalid case (empty)
        result = validator.validate("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.failure_descriptions[0], "This field cannot be empty.")
        
        # Invalid case (whitespace)
        result = validator.validate("   ")
        self.assertFalse(result.is_valid)

if __name__ == '__main__':
    unittest.main()
