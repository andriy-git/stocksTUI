import unittest
import tempfile
from pathlib import Path
from stockstui.database.db_manager import DbManager


class TestOptionPositions(unittest.TestCase):
    """Test suite for option position database operations."""

    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_db.name)
        self.db = DbManager(self.db_path)

    def tearDown(self):
        """Close database and clean up temporary file."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_save_position(self):
        """Test saving a new position."""
        symbol = "SPY251128C00600000"
        ticker = "SPY"
        quantity = 5.0
        avg_cost = 1.50
        
        self.db.save_option_position(symbol, ticker, quantity, avg_cost)
        
        position = self.db.get_option_position(symbol)
        
        self.assertIsNotNone(position)
        self.assertEqual(position['symbol'], symbol)
        self.assertEqual(position['ticker'], ticker)
        self.assertEqual(position['quantity'], quantity)
        self.assertEqual(position['avg_cost'], avg_cost)

    def test_update_position(self):
        """Test updating an existing position."""
        symbol = "SPY251128C00600000"
        
        # Initial save
        self.db.save_option_position(symbol, "SPY", 5.0, 1.50)
        
        # Update
        self.db.save_option_position(symbol, "SPY", 10.0, 1.75)
        
        position = self.db.get_option_position(symbol)
        
        self.assertEqual(position['quantity'], 10.0)
        self.assertEqual(position['avg_cost'], 1.75)

    def test_get_nonexistent_position(self):
        """Test retrieving a position that doesn't exist."""
        position = self.db.get_option_position("NONEXISTENT")
        self.assertIsNone(position)

    def test_delete_position(self):
        """Test deleting a position."""
        symbol = "SPY251128C00600000"
        
        # Save then delete
        self.db.save_option_position(symbol, "SPY", 5.0, 1.50)
        self.assertIsNotNone(self.db.get_option_position(symbol))
        
        self.db.delete_option_position(symbol)
        self.assertIsNone(self.db.get_option_position(symbol))

    def test_delete_nonexistent_position(self):
        """Test deleting a position that doesn't exist (should not error)."""
        # Should not raise an error
        self.db.delete_option_position("NONEXISTENT")

    def test_get_all_positions_empty(self):
        """Test getting all positions when none exist."""
        positions = self.db.get_all_option_positions()
        self.assertEqual(positions, {})

    def test_get_all_positions(self):
        """Test getting all positions."""
        # Save multiple positions
        positions_data = [
            ("SPY251128C00600000", "SPY", 5.0, 1.50),
            ("AAPL251205C00200000", "AAPL", 2.0, 3.25),
            ("TSLA251212P00250000", "TSLA", -1.0, 5.00),
        ]
        
        for symbol, ticker, qty, cost in positions_data:
            self.db.save_option_position(symbol, ticker, qty, cost)
        
        all_positions = self.db.get_all_option_positions()
        
        self.assertEqual(len(all_positions), 3)
        self.assertIn("SPY251128C00600000", all_positions)
        self.assertIn("AAPL251205C00200000", all_positions)
        self.assertIn("TSLA251212P00250000", all_positions)
        
        # Verify data integrity
        spy_pos = all_positions["SPY251128C00600000"]
        self.assertEqual(spy_pos['quantity'], 5.0)
        self.assertEqual(spy_pos['avg_cost'], 1.50)

    def test_save_position_with_zero_cost(self):
        """Test saving a position with zero cost."""
        symbol = "FREE_OPTION"
        self.db.save_option_position(symbol, "TEST", 1.0, 0.0)
        
        position = self.db.get_option_position(symbol)
        self.assertEqual(position['avg_cost'], 0.0)

    def test_save_position_negative_quantity(self):
        """Test saving a position with negative quantity (short position)."""
        symbol = "SHORT_PUT"
        self.db.save_option_position(symbol, "SPY", -5.0, 2.00)
        
        position = self.db.get_option_position(symbol)
        self.assertEqual(position['quantity'], -5.0)

    def test_save_position_with_fractional_quantity(self):
        """Test saving a position with fractional quantity."""
        symbol = "FRACTIONAL"
        self.db.save_option_position(symbol, "SPY", 2.5, 1.00)
        
        position = self.db.get_option_position(symbol)
        self.assertEqual(position['quantity'], 2.5)

    def test_multiple_operations(self):
        """Test a sequence of operations."""
        symbol1 = "POS1"
        symbol2 = "POS2"
        
        # Add
        self.db.save_option_position(symbol1, "SPY", 5.0, 1.50)
        self.assertEqual(len(self.db.get_all_option_positions()), 1)
        
        # Add another
        self.db.save_option_position(symbol2, "AAPL", 3.0, 2.00)
        self.assertEqual(len(self.db.get_all_option_positions()), 2)
        
        # Update first
        self.db.save_option_position(symbol1, "SPY", 10.0, 1.75)
        self.assertEqual(len(self.db.get_all_option_positions()), 2)
        self.assertEqual(self.db.get_option_position(symbol1)['quantity'], 10.0)
        
        # Delete first
        self.db.delete_option_position(symbol1)
        self.assertEqual(len(self.db.get_all_option_positions()), 1)
        self.assertIn(symbol2, self.db.get_all_option_positions())
        
        # Delete second
        self.db.delete_option_position(symbol2)
        self.assertEqual(len(self.db.get_all_option_positions()), 0)


if __name__ == '__main__':
    unittest.main()
