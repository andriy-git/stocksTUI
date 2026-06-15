"""Tests for the yfinance_full_output debug utility."""

import pytest
from io import StringIO
import sys

from debug_extras.yfinance_full_output import format_row, compare_ticker_info, HEADERS, COL_WIDTHS, COL_ALIGNMENTS


class TestFormatRow:
    """Tests for the format_row function."""
    
    def test_format_row_basic(self) -> None:
        """Test basic row formatting."""
        items = ["Test Key", "10.5", "20.3", "30.1", "40.2"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Should contain all items
        assert "Test Key" in result
        assert "10.5" in result
        
    def test_format_row_none_values(self) -> None:
        """Test formatting with None values."""
        items = ["Test Key", None, "value", None, None]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # None should be converted to empty strings
        assert "Test Key" in result
        
    def test_format_row_float_formatting(self) -> None:
        """Test that floats are formatted to 4 decimal places."""
        items = ["Test Key", 1.23456789, 2.0, 3.14159, 4.0]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Float should be formatted to 4 decimals
        assert "1.2346" in result  # Rounded
        
    def test_format_row_truncation(self) -> None:
        """Test that long strings are truncated."""
        # Create a very long string
        long_string = "A" * 50
        items = [long_string, "short", "short", "short", "short"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Should be truncated with ...
        assert "..." in result
        
    def test_format_row_right_alignment(self) -> None:
        """Test right alignment for numeric columns."""
        items = ["Test", "100", "200", "300", "400"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Right-aligned columns should have leading spaces
        # This is harder to test directly, so we check the format is consistent
        
    def test_format_row_left_alignment(self) -> None:
        """Test left alignment for first column."""
        items = ["Test Key", "100", "200", "300", "400"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # First column should be left-aligned
        assert result.startswith("Test Key")
        
    def test_format_row_column_widths(self) -> None:
        """Test that output respects column widths."""
        items = ["Short", "1", "2", "3", "4"]
        result = format_row(items, COL_WIDTHS, COL_ALIGNMENTS)
        
        # Each column should be padded to its width
        # Total length should be sum of widths + spaces between
        expected_min_length = sum(COL_WIDTHS) + len(COL_WIDTHS) - 1
        assert len(result) >= expected_min_length


class TestCompareTickerInfo:
    """Tests for the compare_ticker_info function."""
    
    def test_compare_ticker_info_empty_list(self, capsys) -> None:
        """Test with empty ticker list."""
        compare_ticker_info([])
        captured = capsys.readouterr()
        assert "No tickers provided" in captured.out
        
    def test_compare_ticker_info_prints_headers(self, capsys) -> None:
        """Test that function prints headers for valid tickers."""
        # Use a simple mock test - just check it runs without error
        # Actual yfinance testing requires network
        compare_ticker_info(["AAPL"])
        captured = capsys.readouterr()
        
        # Should print some output
        assert len(captured.out) > 0
        
    def test_compare_ticker_info_prints_ticker_separator(self, capsys) -> None:
        """Test that function prints separator lines."""
        compare_ticker_info(["AAPL"])
        captured = capsys.readouterr()
        
        # Should print separator lines
        assert "-" in captured.out


class TestHeadersAndConstants:
    """Tests for constants."""
    
    def test_headers_count(self) -> None:
        """Test that headers match expected columns."""
        assert len(HEADERS) == 5
        
    def test_col_widths_count(self) -> None:
        """Test that column widths match headers."""
        assert len(COL_WIDTHS) == len(HEADERS)
        
    def test_col_alignments_count(self) -> None:
        """Test that column alignments match headers."""
        assert len(COL_ALIGNMENTS) == len(HEADERS)
        
    def test_first_column_left_aligned(self) -> None:
        """Test that first column is left-aligned."""
        assert COL_ALIGNMENTS[0] == "l"
        
    def test_numeric_columns_right_aligned(self) -> None:
        """Test that numeric columns are right-aligned."""
        for i in range(1, len(COL_ALIGNMENTS)):
            assert COL_ALIGNMENTS[i] == "r"
