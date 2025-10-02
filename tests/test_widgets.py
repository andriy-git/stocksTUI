import unittest
from unittest.mock import MagicMock

from textual.app import App
from textual.containers import VerticalScroll

from stockstui.ui.widgets.tag_filter import TagFilterWidget, TagFilterChanged

class WidgetsTestApp(App):
    """A minimal app for testing widgets."""

    def __init__(self, widget_to_test):
        super().__init__()
        self.widget_to_test = widget_to_test
        self.messages = []

    def compose(self):
        # Mount the widget inside a container to give it a layout
        with VerticalScroll(id="test-container"):
            yield self.widget_to_test

    def on_tag_filter_changed(self, message: TagFilterChanged):
        self.messages.append(message)


class TestTagFilterWidget(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the TagFilterWidget."""

    async def test_tag_selection_and_message_emission(self):
        """Test that clicking tag buttons selects/deselects and emits messages."""
        tags = ["tech", "growth", "value"]
        widget = TagFilterWidget(available_tags=tags, id="tag-filter")
        app = WidgetsTestApp(widget)

        async with app.run_test(size=(120, 40)) as pilot:
            # FIX: Instead of clicking, which is coordinate-based and can be flaky,
            # query for the button and call its press() method directly. This is more robust.
            
            # Toggle the widget's display to make its children queryable
            widget.display = True
            await pilot.pause()

            # Initial state message
            self.assertEqual(len(app.messages), 1)
            self.assertEqual(app.messages[0].tags, [])

            # Select 'tech'
            tech_button = widget.query_one("#tag-button-tech")
            tech_button.press()
            await pilot.pause()
            self.assertEqual(app.messages[-1].tags, ["tech"])

            # Select 'value'
            value_button = widget.query_one("#tag-button-value")
            value_button.press()
            await pilot.pause()
            self.assertEqual(set(app.messages[-1].tags), {"tech", "value"})

            # Deselect 'tech'
            tech_button.press()
            await pilot.pause()
            self.assertEqual(app.messages[-1].tags, ["value"])

            # Clear filter
            clear_button = widget.query_one("#clear-filter-button")
            clear_button.press()
            await pilot.pause()
            self.assertEqual(app.messages[-1].tags, [])
