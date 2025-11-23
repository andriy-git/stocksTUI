import unittest
from unittest.mock import MagicMock, patch
from stockstui.presentation import formatter
from stockstui.config_manager import ConfigManager
import json
import tempfile
import shutil
from pathlib import Path
import os

class TestColumns(unittest.TestCase):
    def test_formatter_returns_dict(self):
        data = [{
            'symbol': 'AAPL',
            'description': 'Apple Inc.',
            'price': 150.0,
            'previous_close': 145.0,
            'day_low': 148.0,
            'day_high': 152.0,
            'fifty_two_week_low': 100.0,
            'fifty_two_week_high': 200.0,
            'volume': 1000000,
            'open': 149.0
        }]
        old_prices = {}
        alias_map = {}
        
        rows = formatter.format_price_data_for_table(data, old_prices, alias_map)
        self.assertIsInstance(rows[0], dict)
        self.assertEqual(rows[0]['Ticker'], 'AAPL')
        self.assertEqual(rows[0]['Volume'], '1,000,000')
        self.assertEqual(rows[0]['Open'], '$149.00')
        self.assertEqual(rows[0]['Prev Close'], '$145.00')
        self.assertEqual(rows[0]['Price'], 150.0) # Raw value

    def test_config_manager_merges_defaults(self):
        # Create a temp dir for config
        with tempfile.TemporaryDirectory() as tmpdir:
            app_root = Path(tmpdir)
            default_dir = app_root / "default_configs"
            default_dir.mkdir()
            
            # Create default settings with new key
            default_settings = {
                "theme": "default",
                "new_key": "new_value"
            }
            with open(default_dir / "settings.json", "w") as f:
                json.dump(default_settings, f)
            
            # Create existing user config WITHOUT new key
            user_config_dir = app_root / "config"
            user_config_dir.mkdir()
            user_settings = {"theme": "user_theme"}
            with open(user_config_dir / "settings.json", "w") as f:
                json.dump(user_settings, f)
            
            # Mock platformdirs to point to tmpdir
            with patch("stockstui.config_manager.dirs") as mock_dirs:
                mock_dirs.user_config_dir = str(user_config_dir)
                mock_dirs.user_cache_dir = str(app_root / "cache")
                
                # Initialize ConfigManager
                cm = ConfigManager(app_root)
                
                # Check if merged
                self.assertEqual(cm.settings['theme'], 'user_theme')
                self.assertEqual(cm.settings['new_key'], 'new_value')

if __name__ == '__main__':
    unittest.main()
