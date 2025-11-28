from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual import on

from stockstui.common import NotEmpty
from stockstui.utils import parse_tags, format_tags


class QuickEditTickerModal(ModalScreen[tuple[str, str] | None]):
    """A modal dialog for quickly editing a single ticker field."""
    
    def __init__(self, ticker: str, category: str, ticker_data: dict) -> None:
        """
        Args:
            ticker: The ticker symbol being edited.
            category: The category/list the ticker belongs to.
            ticker_data: Dictionary containing current ticker data (alias, note, tags).
        """
        super().__init__()
        self.ticker = ticker
        self.category = category
        self.ticker_data = ticker_data
        
    def compose(self) -> ComposeResult:
        """Creates the layout for the quick edit modal."""
        with Vertical(id="dialog"):
            yield Label(f"Quick Edit: {self.ticker}")
            yield Label("Select field to edit:", classes="field-label")
            yield Select(
                options=[
                    ("Alias", "alias"),
                    ("Note", "note"),
                    ("Tags", "tags")
                ],
                id="field-select",
                value="alias"
            )
            yield Label("Value:", classes="field-label")
            yield Input(
                value=self.ticker_data.get('alias', self.ticker),
                id="value-input",
                validators=[NotEmpty()]
            )
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")
    
    def on_mount(self) -> None:
        """Sets focus to the select field when the modal is mounted."""
        self.query_one("#value-input").focus()
    
    @on(Select.Changed, "#field-select")
    def on_field_changed(self, event: Select.Changed) -> None:
        """Updates the input field when the dropdown selection changes."""
        field = event.value
        value_input = self.query_one("#value-input", Input)
        
        if field == "alias":
            value_input.value = self.ticker_data.get('alias', self.ticker)
        elif field == "note":
            note = self.ticker_data.get('note', '')
            value_input.value = note if note else ''
        elif field == "tags":
            tags = self.ticker_data.get('tags', '')
            value_input.value = tags if tags else ''
        
        # Remove NotEmpty validator for note and tags, but keep it for alias
        if field == "alias":
            value_input.validators = [NotEmpty()]
        else:
            value_input.validators = []
        
        # Focus the input after changing value
        value_input.focus()
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with field update or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        
        if event.button.id == "save":
            field_select = self.query_one("#field-select", Select)
            value_input = self.query_one("#value-input", Input)
            
            field = field_select.value
            value = value_input.value.strip()
            
            # Validate alias is not empty
            if field == "alias" and not value:
                return
            
            # Format tags if that's what we're editing
            if field == "tags":
                value = format_tags(parse_tags(value))
            
            self.dismiss((field, value))
