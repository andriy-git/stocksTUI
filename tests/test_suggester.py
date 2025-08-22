import unittest

from stockstui.ui.suggesters import TickerSuggester

class TestTickerSuggester(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the TickerSuggester."""

    def setUp(self):
        """Set up a suggester instance for each test."""
        self.sample_items = [
            ('AAPL', 'Apple Inc.'),
            ('GOOGL', 'Alphabet Inc. Class A'),
            ('TSLA', 'Tesla, Inc.')
        ]
        self.suggester = TickerSuggester(self.sample_items)

    async def test_prefix_match_ticker(self):
        suggestion = await self.suggester.get_suggestion("AAP")
        self.assertEqual(suggestion, "L - Apple Inc. - AAPL")

    async def test_substring_match_description(self):
        suggestion = await self.suggester.get_suggestion("abet")
        self.assertEqual(suggestion, "GOOGL - Alphabet Inc. Class A - GOOGL")
        suggestion_lower = await self.suggester.get_suggestion("apple")
        self.assertEqual(suggestion_lower, "AAPL - Apple Inc. - AAPL")

    async def test_no_match(self):
        suggestion = await self.suggester.get_suggestion("XYZ")
        self.assertIsNone(suggestion)

    async def test_empty_input(self):
        suggestion = await self.suggester.get_suggestion("")
        self.assertIsNone(suggestion)
        
    async def test_prefix_has_priority(self):
        items_with_overlap = [('TES', 'Some Other Company'), ('TSLA', 'Tesla, Inc.')]
        suggester_overlap = TickerSuggester(items_with_overlap)
        suggestion = await suggester_overlap.get_suggestion("TES")
        self.assertEqual(suggestion, " - Some Other Company - TES")
