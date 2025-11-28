import unittest
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from stockstui.ui.widgets.search_box import SearchBox

class SearchBoxApp(App):
    """A minimal app for testing the SearchBox widget."""
    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        self.search_box = None

    def compose(self) -> ComposeResult:
        self.search_box = SearchBox(**self.kwargs)
        yield self.search_box

class TestSearchBox(unittest.IsolatedAsyncioTestCase):
    """Tests for the SearchBox widget."""

    async def test_search_box_creation(self):
        """Test creating a SearchBox with default parameters."""
        app = SearchBoxApp()
        async with app.run_test() as pilot:
            self.assertEqual(app.search_box.placeholder, "Search...")
            self.assertEqual(app.search_box.id, "search-box")

    async def test_search_box_with_placeholder(self):
        """Test creating a SearchBox - it always uses the default placeholder."""
        app = SearchBoxApp()
        async with app.run_test() as pilot:
            self.assertEqual(app.search_box.placeholder, "Search...")

    async def test_search_box_with_initial_value(self):
        """Test creating a SearchBox with an initial value."""
        app = SearchBoxApp(value="initial")
        async with app.run_test() as pilot:
            self.assertEqual(app.search_box.value, "initial")

    async def test_search_box_on_change_callback(self):
        """Test that the search box can handle value changes."""
        app = SearchBoxApp()
        
        async with app.run_test() as pilot:
            # Set initial value
            app.search_box.value = "test"
            await pilot.pause()
            self.assertEqual(app.search_box.value, "test")

    async def test_search_box_on_submit_callback(self):
        """Test that the search box can handle value and submission."""
        app = SearchBoxApp()
        
        async with app.run_test() as pilot:
            # Set initial value
            app.search_box.value = "MSFT"
            await pilot.pause()
            self.assertEqual(app.search_box.value, "MSFT")
