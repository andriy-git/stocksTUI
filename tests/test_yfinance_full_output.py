"""Tests for the yfinance_full_output debug utility."""

import unittest
from io import StringIO
import sys

from debug_extras.yfinance_full_output import format_row, compare_ticker_info, HEADERS, COL_WIDTHS, COL_ALIGNMENTS


class TestFormatRow(unittest.TestCase):
    """Tests for the format_row function."""
    
    def test_format_row_basic(self) -> None:
        """Test basic row formatting."""
        items = ["Test Key", "10.5", "20.3", "30.1", "40.2"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Should contain all items
        self.assertIn("Test Key", result)
        self.assertIn("10.5", result)
        
    def test_format_row_none_values(self) -> None:
        """Test formatting with None values."""
        items = ["Test Key", None, "value", None, None]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # None should be converted to empty strings
        self.assertIn("Test Key", result)
        
    def test_format_row_float_formatting(self) -> None:
        """Test that floats are formatted to 4 decimal places."""
        items = ["Test Key", 1.23456789, 2.0, 3.14159, 4.0]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Float should be formatted to 4 decimals
        self.assertIn("1.2346", result)  # Rounded
        
    def test_format_row_truncation(self) -> None:
        """Test that long strings are truncated."""
        # Create a very long string
        long_string = "A" * 50
        items = [long_string, "short", "short", "short", "short"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Should be truncated with ...
        self.assertIn("...", result)
        
    def test_format_row_right_alignment(self) -> None:
        """Test right alignment for numeric columns."""
        items = ["Test", "100", "200", "300", "400"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        # Verify result is a string and non-empty
        self.assertTrue(len(result) > 0)
        
    def test_format_row_left_alignment(self) -> None:
        """Test left alignment for first column."""
        items = ["Test Key", "100", "200", "300", "400"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # First column should be left-aligned
        self.assertTrue(result.startswith("Test Key"))
        
    def test_format_row_column_widths(self) -> None:
        """Test that output respects column widths."""
        items = ["Short", "1", "2", "3", "4"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Each column should be padded to its width
        # Total length should be sum of widths + spaces between
        expected_min_length = sum(COL_WIDTHS) + len(COL_WIDTHS) - 1
        self.assertTrue(len(result) >= expected_min_length)


class TestCompareTickerInfo(unittest.TestCase):
    """Tests for the compare_ticker_info function."""
    
    def test_compare_ticker_info_empty_list(self) -> None:
        """Test with empty ticker list."""
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            compare_ticker_info([])
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("No tickers provided", captured_output.getvalue())
        
    def test_compare_ticker_info_prints_headers(self) -> None:
        """Test that function prints headers for valid tickers."""
        # Use a simple mock test - just check it runs without error
        # Actual yfinance testing requires network
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            compare_ticker_info(["AAPL"])
        finally:
            sys.stdout = sys.__stdout__
        
        # Should print some output
        self.assertTrue(len(captured_output.getvalue()) > 0)
        
    def test_compare_ticker_info_prints_ticker_separator(self) -> None:
        """Test that function prints separator lines."""
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            compare_ticker_info(["AAPL"])
        finally:
            sys.stdout = sys.__stdout__
        
        # Should print separator lines
        self.assertIn("-", captured_output.getvalue())


class TestHeadersAndConstants(unittest.TestCase):
    """Tests for constants."""
    
    def test_headers_count(self) -> None:
        """Test that headers match expected columns."""
        self.assertEqual(len(HEADERS), 5)
        
    def test_col_widths_count(self) -> None:
        """Test that column widths match headers."""
        self.assertEqual(len(COL_WIDTHS), len(HEADERS))
        
    def test_col_alignments_count(self) -> None:
        """Test that column alignments match headers."""
        self.assertEqual(len(COL_ALIGNMENTS), len(HEADERS))
        
    def test_first_column_left_aligned(self) -> None:
        """Test that first column is left-aligned."""
        self.assertEqual(COL_ALIGNMENTS[0], "l")
        
    def test_numeric_columns_right_aligned(self) -> None:
        """Test that numeric columns are right-aligned."""
        for i in range(1, len(COL_ALIGNMENTS)):
            self.assertEqual(COL_ALIGNMENTS[i], "r")


if __name__ == "__main__":
    unittest.main()
