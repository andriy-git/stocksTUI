import unittest
from unittest.mock import MagicMock, patch
import tempfile
import json
from pathlib import Path

from stockstui.data_providers.portfolio import PortfolioManager
from stockstui.config_manager import ConfigManager

class TestPortfolioManagerAdditional(unittest.TestCase):
    """Additional tests for the PortfolioManager."""

    def setUp(self):
        """Set up a mock ConfigManager for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        
        # Create a minimal config structure
        self.user_config_dir = self.tmp_path / "user_config"
        self.user_config_dir.mkdir()
        
        self.app_root = self.tmp_path / "app"
        self.app_root.mkdir()
        default_dir = self.app_root / "default_configs"
        default_dir.mkdir()
        
        # Write default portfolio config
        default_portfolios = {"portfolios": {"default": {"tickers": []}}}
        (default_dir / "portfolios.json").write_text(json.dumps(default_portfolios))
        
        # Create a real config manager for more realistic testing
        with patch('platformdirs.PlatformDirs') as mock_dirs:
            mock_dirs.return_value.user_config_dir = str(self.user_config_dir)
            self.config_manager = ConfigManager(app_root=self.app_root)
        
        self.pm = PortfolioManager(self.config_manager)

    def tearDown(self):
        """Clean up temporary directory."""
        self.tmpdir.cleanup()

    def test_create_portfolio_with_special_characters(self):
        """Test creating portfolios with special characters in name."""
        portfolio_id = self.pm.create_portfolio("Tech & Science", "Portfolio with special chars")
        self.assertIn(portfolio_id, self.config_manager.portfolios["portfolios"])
        
        portfolio = self.config_manager.portfolios["portfolios"][portfolio_id]
        self.assertEqual(portfolio["name"], "Tech & Science")
        self.assertEqual(portfolio["description"], "Portfolio with special chars")

    def test_add_duplicate_ticker_prevention(self):
        """Test that adding duplicate tickers is properly prevented."""
        # Add a ticker
        self.pm.add_ticker_to_portfolio("default", "AAPL")
        initial_count = len(self.config_manager.portfolios["portfolios"]["default"]["tickers"])
        
        # Try to add the same ticker again
        self.pm.add_ticker_to_portfolio("default", "AAPL")
        final_count = len(self.config_manager.portfolios["portfolios"]["default"]["tickers"])
        
        # Count should be the same
        self.assertEqual(initial_count, final_count)
        
        # Verify ticker appears only once
        tickers = self.config_manager.portfolios["portfolios"]["default"]["tickers"]
        self.assertEqual(tickers.count("AAPL"), 1)

    def test_remove_nonexistent_ticker(self):
        """Test removing a ticker that doesn't exist (should not error)."""
        initial_count = len(self.config_manager.portfolios["portfolios"]["default"]["tickers"])
        
        # Try to remove a ticker that doesn't exist
        self.pm.remove_ticker_from_portfolio("default", "NONEXISTENT")
        
        # Count should be the same
        final_count = len(self.config_manager.portfolios["portfolios"]["default"]["tickers"])
        self.assertEqual(initial_count, final_count)

    def test_get_portfolios_containing_nonexistent_ticker(self):
        """Test getting portfolios for a ticker that doesn't exist."""
        portfolios = self.pm.get_portfolios_containing_ticker("NONEXISTENT")
        self.assertEqual(portfolios, [])

    def test_portfolio_id_generation_uniqueness(self):
        """Test that generated portfolio IDs are unique."""
        ids = set()
        for i in range(10):
            portfolio_id = self.pm.create_portfolio(f"Portfolio {i}", f"Description {i}")
            self.assertNotIn(portfolio_id, ids)
            ids.add(portfolio_id)