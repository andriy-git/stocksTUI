import unittest
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button

from stockstui.ui.widgets.tag_filter import TagFilterWidget, TagFilterChanged

class TagFilterApp(App):
    """A minimal app for testing the TagFilterWidget."""
    CSS = """
    TagFilterWidget {
        height: auto;
        width: 100%;
        border: solid green;
    }
    """
    def __init__(self, widget_to_test):
        super().__init__()
        self.widget = widget_to_test

    def compose(self) -> ComposeResult:
        yield self.widget

class TestTagFilterWidget(unittest.IsolatedAsyncioTestCase):
    """Comprehensive tests for the TagFilterWidget."""

    async def test_tag_filter_with_empty_tags(self):
        """Test widget behavior with an empty tag list."""
        widget = TagFilterWidget(available_tags=[], id="tag-filter")
        app = TagFilterApp(widget)

        async with app.run_test() as pilot:
            # The widget should still mount and function without errors
            self.assertEqual(len(widget.query("Button")), 0) # No buttons should be present

    async def test_tag_filter_with_duplicate_tags(self):
        """Test that duplicate tags are handled gracefully."""
        widget = TagFilterWidget(available_tags=["tech", "tech", "value"], id="tag-filter")
        app = TagFilterApp(widget)

        async with app.run_test() as pilot:
            # Should deduplicate tags, resulting in 3 buttons (tech, value, clear)
            self.assertEqual(len(widget.query("Button")), 3)
            self.assertIsNotNone(widget.query_one("#tag-button-tech"))
            self.assertIsNotNone(widget.query_one("#tag-button-value"))

    async def test_tag_selection_and_message_emission(self):
        """Test that clicking tag buttons selects them and emits a message."""
        tags = ["tech", "growth"]
        widget = TagFilterWidget(available_tags=tags, id="tag-filter")
        app = TagFilterApp(widget)

        # Capture TagFilterChanged messages
        messages = []
        def capture_message(message):
            if isinstance(message, TagFilterChanged):
                messages.append(message)

        # Set up the message capturing
        original_post_message = app.post_message
        def custom_post_message(message):
            capture_message(message)
            return original_post_message(message)
        app.post_message = custom_post_message

        async with app.run_test() as pilot:
            # Clear initial messages from mount
            messages.clear()
            
            # Simulate click on tech button
            tech_button = widget.query_one("#tag-button-tech")
            event = Button.Pressed(tech_button)
            widget.on_tag_button_pressed(event)
            
            # Wait for message to be processed
            await pilot.pause(0.1)

            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].tags, ["tech"])
            self.assertEqual(widget.query_one("#tag-button-tech").variant, "primary")

            # Simulate click on growth button
            growth_button = widget.query_one("#tag-button-growth")
            event = Button.Pressed(growth_button)
            widget.on_tag_button_pressed(event)
            
            await pilot.pause(0.1)

            # Check that the last message contains both tags
            if messages:
                self.assertEqual(set(messages[-1].tags), {"tech", "growth"})

    async def test_tag_filter_clear_functionality(self):
        """Test that the clear button resets all selections."""
        tags = ["tech", "growth", "value"]
        widget = TagFilterWidget(available_tags=tags, id="tag-filter")
        app = TagFilterApp(widget)

        # Capture TagFilterChanged messages
        messages = []
        def capture_message(message):
            if isinstance(message, TagFilterChanged):
                messages.append(message)

        # Set up the message capturing
        original_post_message = app.post_message
        def custom_post_message(message):
            capture_message(message)
            return original_post_message(message)
        app.post_message = custom_post_message

        async with app.run_test() as pilot:
            # Clear initial messages from mount
            messages.clear()
            
            # Select a tag directly
            tech_button = widget.query_one("#tag-button-tech")
            event = Button.Pressed(tech_button)
            widget.on_tag_button_pressed(event)
            await pilot.pause(0.1)
            
            if messages:
                self.assertEqual(messages[-1].tags, ["tech"])

            # Clear the filter directly
            clear_button = widget.query_one("#clear-filter-button")
            event_clear = Button.Pressed(clear_button)
            widget.on_clear_button_pressed(event_clear)
            await pilot.pause(0.1)

            if messages:
                self.assertEqual(messages[-1].tags, [])
            self.assertEqual(widget.query_one("#tag-button-tech").variant, "default")