import unittest
from unittest.mock import MagicMock, patch

from stockstui.data_providers.portfolio import PortfolioManager

class TestPortfolioManager(unittest.TestCase):
    """Unit tests for the PortfolioManager."""

    def setUp(self):
        """Set up a mock ConfigManager for each test."""
        self.mock_config_manager = MagicMock()
        self.mock_config_manager.portfolios = {
            "portfolios": {
                "default": {"name": "Default", "tickers": ["AAPL", "GOOG"]},
                "tech": {"name": "Tech", "tickers": ["MSFT"]}
            }
        }
        
        # Instantiate the PortfolioManager with the mock
        self.pm = PortfolioManager(self.mock_config_manager)

    def test_get_all_portfolios(self):
        """Test retrieving all portfolios."""
        portfolios = self.pm.get_all_portfolios()
        self.assertEqual(len(portfolios), 2)
        self.assertIn("default", portfolios)

    def test_create_portfolio(self):
        """Test creating a new portfolio."""
        new_id = self.pm.create_portfolio("New Portfolio", "A test portfolio")
        
        # Verify the new portfolio exists in the mock data
        self.assertIn(new_id, self.mock_config_manager.portfolios["portfolios"])
        self.assertEqual(self.mock_config_manager.portfolios["portfolios"][new_id]["name"], "New Portfolio")
        
        # Verify that the config was saved
        self.mock_config_manager.save_portfolios.assert_called_once()

    def test_delete_portfolio(self):
        """Test deleting an existing portfolio."""
        self.pm.delete_portfolio("tech")
        self.assertNotIn("tech", self.mock_config_manager.portfolios["portfolios"])
        self.mock_config_manager.save_portfolios.assert_called_once()
        
    def test_delete_default_portfolio_raises_error(self):
        """Test that attempting to delete the default portfolio raises a ValueError."""
        with self.assertRaises(ValueError):
            self.pm.delete_portfolio("default")
            
        # Ensure save was not called
        self.mock_config_manager.save_portfolios.assert_not_called()

    def test_add_ticker_to_portfolio(self):
        """Test adding a new ticker to a portfolio."""
        self.pm.add_ticker_to_portfolio("default", "TSLA")
        self.assertIn("TSLA", self.mock_config_manager.portfolios["portfolios"]["default"]["tickers"])
        self.mock_config_manager.save_portfolios.assert_called_once()

    def test_add_existing_ticker_does_nothing(self):
        """Test that adding a ticker that already exists does not cause duplicates."""
        initial_count = len(self.mock_config_manager.portfolios["portfolios"]["default"]["tickers"])
        self.pm.add_ticker_to_portfolio("default", "AAPL")
        
        # Count should be the same, and save should not have been called
        final_count = len(self.mock_config_manager.portfolios["portfolios"]["default"]["tickers"])
        self.assertEqual(initial_count, final_count)
        self.mock_config_manager.save_portfolios.assert_not_called()
        
    def test_remove_ticker_from_portfolio(self):
        """Test removing a ticker from a portfolio."""
        self.pm.remove_ticker_from_portfolio("default", "AAPL")
        self.assertNotIn("AAPL", self.mock_config_manager.portfolios["portfolios"]["default"]["tickers"])
        self.mock_config_manager.save_portfolios.assert_called_once()

    def test_get_all_tickers(self):
        """Test getting a unique set of all tickers across all portfolios."""
        all_tickers = self.pm.get_all_tickers()
        self.assertEqual(all_tickers, {"AAPL", "GOOG", "MSFT"})

if __name__ == '__main__':
    unittest.main()
