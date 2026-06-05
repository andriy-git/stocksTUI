import unittest
from stockstui.presentation.formatter import get_currency_symbol, CURRENCY_SYMBOLS


class TestCurrencyFormatting(unittest.TestCase):
    """Verifies that currency codes are mapped correctly to symbols."""

    def test_known_currencies(self):
        """Test standard currency code lookups."""
        for code, expected_sym in CURRENCY_SYMBOLS.items():
            self.assertEqual(get_currency_symbol(code), expected_sym)
            self.assertEqual(get_currency_symbol(code.lower()), expected_sym)

    def test_default_fallback(self):
        """Test fallback when currency is None or unknown."""
        self.assertEqual(get_currency_symbol(None), "$")
        self.assertEqual(get_currency_symbol("XYZ"), "$")
        self.assertEqual(get_currency_symbol(""), "$")
