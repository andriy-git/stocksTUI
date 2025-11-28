import unittest
import pandas as pd
from stockstui.ui.widgets.oi_chart import OIChart


class TestOIChart(unittest.TestCase):
    """Test suite for Open Interest Chart widget."""

    def setUp(self):
        """Create sample options data for testing."""
        # Sample calls data
        self.calls_df = pd.DataFrame({
            'strike': [580, 590, 600, 610, 620, 630, 640, 650, 660, 670, 680],
            'openInterest': [100, 200, 500, 1000, 2000, 1500, 800, 400, 200, 100, 50],
            'contractSymbol': [f'CALL{s}' for s in range(11)]
        })
        
        # Sample puts data
        self.puts_df = pd.DataFrame({
            'strike': [580, 590, 600, 610, 620, 630, 640, 650, 660, 670, 680],
            'openInterest': [50, 150, 300, 600, 1800, 2500, 1200, 600, 300, 150, 75],
            'contractSymbol': [f'PUT{s}' for s in range(11)]
        })
        
        self.underlying_price = 630.0

    def test_chart_initialization(self):
        """Test that the chart can be initialized."""
        chart = OIChart(self.calls_df, self.puts_df, self.underlying_price)
        self.assertIsNotNone(chart)
        self.assertEqual(chart._underlying_price, self.underlying_price)

    def test_chart_with_empty_calls(self):
        """Test chart with empty calls dataframe."""
        empty_calls = pd.DataFrame(columns=['strike', 'openInterest', 'contractSymbol'])
        chart = OIChart(empty_calls, self.puts_df, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_with_empty_puts(self):
        """Test chart with empty puts dataframe."""
        empty_puts = pd.DataFrame(columns=['strike', 'openInterest', 'contractSymbol'])
        chart = OIChart(self.calls_df, empty_puts, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_with_both_empty(self):
        """Test chart with both empty dataframes."""
        empty_df = pd.DataFrame(columns=['strike', 'openInterest', 'contractSymbol'])
        chart = OIChart(empty_df, empty_df, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_with_single_strike(self):
        """Test chart with only one strike."""
        single_call = pd.DataFrame({
            'strike': [630],
            'openInterest': [1000],
            'contractSymbol': ['CALL']
        })
        single_put = pd.DataFrame({
            'strike': [630],
            'openInterest': [1500],
            'contractSymbol': ['PUT']
        })
        chart = OIChart(single_call, single_put, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_with_wide_strikes(self):
        """Test chart with strikes far from underlying."""
        wide_calls = pd.DataFrame({
            'strike': [100, 200, 300, 900, 1000, 1100],
            'openInterest': [10, 20, 30, 40, 50, 60],
            'contractSymbol': [f'CALL_WIDE{s}' for s in range(6)]
        })
        chart = OIChart(wide_calls, self.puts_df, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_data_integrity(self):
        """Test that chart preserves data integrity."""
        chart = OIChart(self.calls_df, self.puts_df, self.underlying_price)
        
        # Verify internal data is stored
        self.assertTrue(chart._calls_df.equals(self.calls_df))
        self.assertTrue(chart._puts_df.equals(self.puts_df))

    def test_chart_with_zero_oi(self):
        """Test chart with zero open interest."""
        zero_oi_calls = pd.DataFrame({
            'strike': [630],
            'openInterest': [0],
            'contractSymbol': ['CALL']
        })
        chart = OIChart(zero_oi_calls, self.puts_df, self.underlying_price)
        self.assertIsNotNone(chart)

    def test_chart_with_missing_strikes(self):
        """Test chart with gaps in strike prices."""
        gapped_calls = pd.DataFrame({
            'strike': [600, 620, 660, 680],  # Missing 610, 630, 640, 650, 670
            'openInterest': [100, 500, 300, 100],
            'contractSymbol': ['C1', 'C2', 'C3', 'C4']
        })
        chart = OIChart(gapped_calls, self.puts_df, self.underlying_price)
        self.assertIsNotNone(chart)


if __name__ == '__main__':
    unittest.main()
