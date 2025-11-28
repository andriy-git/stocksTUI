import unittest
from unittest.mock import MagicMock
from stockstui.data_providers.portfolio import PortfolioManager

class TestPortfolioManagerCoverage(unittest.TestCase):
    """Additional coverage tests for PortfolioManager."""

    def setUp(self):
        self.mock_config = MagicMock()
        # Setup initial state
        self.mock_config.portfolios = {
            'portfolios': {
                'default': {'name': 'Default', 'tickers': ['AAPL']},
                'p1': {'name': 'P1', 'tickers': ['GOOG']}
            }
        }
        self.pm = PortfolioManager(self.mock_config)

    def test_update_portfolio(self):
        """Test updating portfolio details."""
        self.pm.update_portfolio('p1', 'New Name', 'New Desc')
        
        p1 = self.mock_config.portfolios['portfolios']['p1']
        self.assertEqual(p1['name'], 'New Name')
        self.assertEqual(p1['description'], 'New Desc')
        self.mock_config.save_portfolios.assert_called()

    def test_update_portfolio_not_found(self):
        """Test updating a non-existent portfolio raises ValueError."""
        with self.assertRaises(ValueError):
            self.pm.update_portfolio('bad_id', 'Name', 'Desc')

    def test_get_portfolio_found(self):
        """Test getting an existing portfolio."""
        p = self.pm.get_portfolio('default')
        self.assertIsNotNone(p)
        self.assertEqual(p['name'], 'Default')

    def test_get_portfolio_not_found(self):
        """Test getting a non-existent portfolio returns None."""
        p = self.pm.get_portfolio('bad_id')
        self.assertIsNone(p)

    def test_get_tickers_for_portfolio(self):
        """Test getting tickers for a portfolio."""
        tickers = self.pm.get_tickers_for_portfolio('default')
        self.assertEqual(tickers, ['AAPL'])
        
        # Non-existent
        self.assertEqual(self.pm.get_tickers_for_portfolio('bad_id'), [])

    def test_get_portfolios_containing_ticker(self):
        """Test finding portfolios containing a ticker."""
        # Add AAPL to p1 too
        self.mock_config.portfolios['portfolios']['p1']['tickers'].append('AAPL')
        
        results = self.pm.get_portfolios_containing_ticker('AAPL')
        # Should be in default and p1
        self.assertEqual(len(results), 2)
        ids = [r[0] for r in results]
        self.assertIn('default', ids)
        self.assertIn('p1', ids)
        
        # Case insensitive check
        results_lower = self.pm.get_portfolios_containing_ticker('aapl')
        self.assertEqual(len(results_lower), 2)

    def test_add_ticker_to_all_portfolios(self):
        """Test adding a ticker to all portfolios."""
        self.pm.add_ticker_to_all_portfolios('MSFT')
        
        self.assertIn('MSFT', self.mock_config.portfolios['portfolios']['default']['tickers'])
        self.assertIn('MSFT', self.mock_config.portfolios['portfolios']['p1']['tickers'])
        self.mock_config.save_portfolios.assert_called()

    def test_add_ticker_to_portfolio_not_found(self):
        """Test adding ticker to non-existent portfolio raises ValueError."""
        with self.assertRaises(ValueError):
            self.pm.add_ticker_to_portfolio('bad_id', 'AAPL')

    def test_remove_ticker_from_portfolio_not_found(self):
        """Test removing ticker from non-existent portfolio raises ValueError."""
        with self.assertRaises(ValueError):
            self.pm.remove_ticker_from_portfolio('bad_id', 'AAPL')

    def test_ensure_default_portfolio_creates_if_missing(self):
        """Test that default portfolio is created if missing."""
        # Setup config with NO portfolios
        empty_config = MagicMock()
        empty_config.portfolios = {} 
        
        pm = PortfolioManager(empty_config)
        
        # Should have created 'portfolios' dict and 'default' entry
        self.assertIn('portfolios', empty_config.portfolios)
        self.assertIn('default', empty_config.portfolios['portfolios'])
        empty_config.save_portfolios.assert_called()

if __name__ == '__main__':
    unittest.main()
