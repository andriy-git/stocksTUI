import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from stockstui.database.db_manager import (DbManager, CACHE_LOAD_DURATION_SECONDS,
                                           CACHE_PRUNE_EXPIRY_SECONDS)

class TestDbManager(unittest.TestCase):
    """
    Unit tests for the DbManager class.
    Uses a temporary file for the SQLite database to ensure tests are isolated.
    """

    def setUp(self):
        """Set up a temporary database for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_cache.db"
        self.dbm = DbManager(self.db_path)

    def tearDown(self):
        """Close the connection and clean up the temporary directory."""
        self.dbm.close()
        self.tmpdir.cleanup()

    def test_table_creation(self):
        """Verify that the necessary tables are created on initialization."""
        cursor = self.dbm.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        self.assertIn("price_cache", tables)
        self.assertIn("ticker_info", tables)

    def test_save_and_load_price_cache(self):
        """Test the full cycle of saving and loading the price cache."""
        now = datetime.now(timezone.utc)
        sample_data = {
            "AAPL": {"expiry": now, "data": {"price": 150.0}},
            "GOOG": {"expiry": now, "data": {"price": 2800.0}}
        }
        
        self.dbm.save_price_cache_to_db(sample_data)
        loaded_data = self.dbm.load_price_cache_from_db()

        self.assertEqual(len(loaded_data), 2)
        self.assertIn("AAPL", loaded_data)
        self.assertEqual(loaded_data["AAPL"]["data"]["price"], 150.0)
        # Compare timestamps with a small tolerance for float precision
        self.assertAlmostEqual(loaded_data["AAPL"]["expiry"].timestamp(), now.timestamp(), places=5)

    def test_load_price_cache_filters_stale_data(self):
        """Test that load_price_cache_from_db filters out entries older than CACHE_LOAD_DURATION."""
        stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_LOAD_DURATION_SECONDS + 60)).timestamp()
        fresh_ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).timestamp()

        # Manually insert data with different timestamps
        cursor = self.dbm.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO price_cache (ticker, data, timestamp) VALUES (?, ?, ?)",
                       ("STALE", json.dumps({"price": 10}), stale_ts))
        cursor.execute("INSERT OR REPLACE INTO price_cache (ticker, data, timestamp) VALUES (?, ?, ?)",
                       ("FRESH", json.dumps({"price": 20}), fresh_ts))
        
        loaded_data = self.dbm.load_price_cache_from_db()
        
        self.assertEqual(len(loaded_data), 1)
        self.assertIn("FRESH", loaded_data)
        self.assertNotIn("STALE", loaded_data)
        
    def test_prune_expired_entries(self):
        """Test that _prune_expired_entries removes data older than CACHE_PRUNE_EXPIRY."""
        very_old_ts = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_PRUNE_EXPIRY_SECONDS + 60)).timestamp()
        not_so_old_ts = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

        cursor = self.dbm.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO price_cache (ticker, data, timestamp) VALUES (?, ?, ?)",
                       ("OLD", json.dumps({}), very_old_ts))
        cursor.execute("INSERT OR REPLACE INTO price_cache (ticker, data, timestamp) VALUES (?, ?, ?)",
                       ("NEW", json.dumps({}), not_so_old_ts))
        
        # Pruning happens at initialization, so we create a new instance
        new_dbm = DbManager(self.db_path)
        
        # Check the database content directly
        cursor = new_dbm.conn.cursor()
        cursor.execute("SELECT ticker FROM price_cache")
        remaining_tickers = {row[0] for row in cursor.fetchall()}
        
        self.assertEqual(len(remaining_tickers), 1)
        self.assertIn("NEW", remaining_tickers)
        self.assertNotIn("OLD", remaining_tickers)
        new_dbm.close()

    def test_save_and_load_info_cache(self):
        """Test the full cycle of saving and loading the ticker info cache."""
        sample_data = {
            "TSLA": {"exchange": "NMS", "shortName": "Tesla", "longName": "Tesla, Inc."},
            "NVDA": {"exchange": "NMS", "shortName": "NVIDIA", "longName": "NVIDIA Corporation"}
        }
        
        self.dbm.save_info_cache_to_db(sample_data)
        loaded_data = self.dbm.load_info_cache_from_db()
        
        self.assertEqual(loaded_data, sample_data)

if __name__ == '__main__':
    unittest.main()
