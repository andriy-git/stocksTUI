from textual.message import Message
from textual.containers import Horizontal, Container, Vertical, VerticalScroll, Grid
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
                # Use VerticalScroll with a Grid inside for proper scrolling
                with VerticalScroll(classes="tag-buttons-scroll"):
                    with Grid(classes="tag-buttons-container"):
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

    def on_key(self, event) -> None:
        """Handle 2D keyboard navigation for tag filter buttons."""
        if not isinstance(self.app.focused, Button):
            return
        
        # Horizontal navigation (sequential)
        if event.key in ("h", "left"):
            self.screen.focus_previous()
            event.stop()
        elif event.key in ("l", "right"):
            self.screen.focus_next()
            event.stop()
        # Vertical navigation (find button in same column position)
        elif event.key in ("j", "down", "k", "up"):
            self._navigate_vertical(direction="down" if event.key in ("j", "down") else "up")
            event.stop()

    def _navigate_vertical(self, direction: str) -> None:
        """Navigate to a button in the row above/below at approximately the same horizontal position."""
        try:
            focused = self.app.focused
            if not focused:
                return
            
            # Get all buttons and their positions
            all_buttons = list(self.query(Button))
            if not all_buttons:
                return
            
            # Group buttons by their y-coordinate (row)
            rows = {}
            for btn in all_buttons:
                y = btn.region.y
                if y not in rows:
                    rows[y] = []
                rows[y].append(btn)
            
            # Sort rows by y-coordinate
            sorted_row_keys = sorted(rows.keys())
            
            # Find which row the focused button is in
            focused_y = focused.region.y
            focused_x = focused.region.x
            
            try:
                current_row_idx = sorted_row_keys.index(focused_y)
            except ValueError:
                return
            
            # Determine target row
            if direction == "down":
                target_row_idx = current_row_idx + 1
            else:  # up
                target_row_idx = current_row_idx - 1
            
            # Wrap around if at edge
            if target_row_idx >= len(sorted_row_keys):
                target_row_idx = 0
            elif target_row_idx < 0:
                target_row_idx = len(sorted_row_keys) - 1
            
            target_row_y = sorted_row_keys[target_row_idx]
            target_row_buttons = rows[target_row_y]
            
            # Find button in target row closest to current x position
            closest_btn = min(target_row_buttons, key=lambda b: abs(b.region.x - focused_x))
            closest_btn.focus()
            
        except Exception:
            # Fallback to sequential navigation if grid logic fails
            if direction == "down":
                self.screen.focus_next()
            else:
                self.screen.focus_previous()

class TagFilterChanged(Message):
    """Message posted when tag filter changes."""
    def __init__(self, tags: list[str]) -> None:
        super().__init__()
        self.tags = tags
