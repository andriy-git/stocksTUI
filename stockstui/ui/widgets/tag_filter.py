from textual.message import Message
from textual.containers import Horizontal, Container, Vertical
from textual.widgets import Button, Label, Static
from textual.widget import Widget
from textual.app import ComposeResult
from textual import on
from textual.dom import NoMatches
from rich.text import Text

class TagFilterWidget(Widget):
    """A widget for filtering by tags using clickable buttons."""
    
    def __init__(self, available_tags: list[str] = None, **kwargs) -> None:
        """
        Args:
            available_tags: List of available tags to create filter buttons for.
        """
        super().__init__(**kwargs)
        self.available_tags = sorted(list(set(available_tags or [])))
        self.selected_tags = set()
    
    def compose(self) -> ComposeResult:
        """Creates the layout for the tag filter widget."""
        if self.available_tags:
            with Horizontal(id="tag-filter-controls"):
                yield Static("Filter by:", classes="tag-filter-label")
                # Container for the tag buttons that will allow wrapping
                with Container(classes="tag-buttons-container"):
                    for tag in self.available_tags:
                        yield Button(tag, id=f"tag-button-{tag}", classes="tag-button")
                yield Button("Clear", id="clear-filter-button", variant="default")
        yield Label("Filter status", id="filter-status")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Post message to ensure parent has initial state (no filter)
        self.post_message(TagFilterChanged(list(self.selected_tags)))
    
    @on(Button.Pressed, ".tag-button")
    def on_tag_button_pressed(self, event: Button.Pressed) -> None:
        """Handles clicks on individual tag buttons."""
        tag = event.button.id.replace("tag-button-", "")
        
        if tag in self.selected_tags:
            self.selected_tags.remove(tag)
            event.button.variant = "default"
        else:
            self.selected_tags.add(tag)
            event.button.variant = "primary"
            
        self.post_message(TagFilterChanged(list(self.selected_tags)))

    @on(Button.Pressed, "#clear-filter-button")
    def on_clear_button_pressed(self, event: Button.Pressed) -> None:
        """Handles clicks on the 'Clear' button."""
        self.selected_tags.clear()
        
        # Reset all tag buttons to their default appearance
        for button in self.query(".tag-button"):
            button.variant = "default"
            
        self.post_message(TagFilterChanged([]))

    def update_filter_status(self, filtered_count: int = None, total_count: int = None) -> None:
        """Updates the filter status display."""
        try:
            status_label = self.query_one("#filter-status", Label)
            if self.selected_tags and filtered_count is not None and total_count is not None:
                if filtered_count != total_count:
                    status_text = f"Showing {filtered_count} of {total_count}"
                    status_label.update(Text(status_text, style="dim"))
                else:
                    status_label.update("")
            else:
                status_label.update("")
        except NoMatches:
            pass

class TagFilterChanged(Message):
    """Message posted when tag filter changes."""
    def __init__(self, tags: list[str]) -> None:
        super().__init__()
        self.tags = tags
