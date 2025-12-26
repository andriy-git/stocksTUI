from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult, on

class EditFredSeriesModal(ModalScreen[str | None]):
    """A modal dialog for setting an alias for a FRED series."""

    def __init__(self, series_id: str, current_alias: str) -> None:
        super().__init__()
        self.series_id = series_id
        self.current_alias = current_alias

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Edit Alias: {self.series_id}", classes="modal-header")
            yield Label("Alias:", classes="field-label")
            yield Input(
                value=self.current_alias,
                id="alias-input",
                placeholder="Enter alias (leave empty to reset)"
            )
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")
    
    def on_mount(self) -> None:
        self.query_one("#alias-input").focus()

    @on(Input.Submitted, "#alias-input")
    def on_input_submitted(self):
        self.query_one("#save", Button).press()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "save":
            value = self.query_one("#alias-input", Input).value.strip()
            self.dismiss(value)
