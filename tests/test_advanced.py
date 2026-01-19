import unittest
from hypothesis import given, strategies as st
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from stockstui.presentation import formatter


# Pydantic Model for "Data Reality"
class MarketItem(BaseModel):
    symbol: str = Field(..., min_length=1)
    description: str = "N/A"
    price: Optional[float] = None
    previous_close: Optional[float] = None
    day_low: Optional[float] = None
    day_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    all_time_high: Optional[float] = None


class TestAdvanced(unittest.TestCase):
    """Demonstrating Hypothesis and Pydantic for robust testing."""

    def test_pydantic_validation(self):
        """Verify that Pydantic catches 'data reality' issues."""
        # Valid data
        valid_data = {"symbol": "AAPL", "price": 150.0, "previous_close": 145.0}
        item = MarketItem(**valid_data)
        self.assertEqual(item.symbol, "AAPL")

        # Invalid data (missing symbol)
        with self.assertRaises(ValidationError):
            MarketItem(price=10.0)

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "symbol": st.text(min_size=1, max_size=5).map(lambda s: s.upper()),
                    "price": st.floats(
                        min_value=0.01,
                        max_value=1000000,
                        allow_nan=False,
                        allow_infinity=False,
                    ),
                    "previous_close": st.floats(
                        min_value=0.01,
                        max_value=1000000,
                        allow_nan=False,
                        allow_infinity=False,
                    ),
                }
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_formatter_with_hypothesis(self, data):
        """Use Hypothesis to find edge cases in the formatter."""
        old_prices = {item["symbol"]: item["price"] for item in data}
        alias_map = {}

        # This will run with many different combinations of symbols and prices
        result = formatter.format_price_data_for_table(data, old_prices, alias_map)

        self.assertEqual(len(result), len(data))
        for row in result:
            self.assertIn("Ticker", row)
            self.assertIn("Price", row)
            # Ensure calculations don't crash and produce expected keys
            self.assertIn("Change", row)
            self.assertIn("% Change", row)


if __name__ == "__main__":
    unittest.main()
