from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
from textual.containers import Vertical, Horizontal, Grid
from textual.app import ComposeResult
from textual import on
from textual.validation import Number

class PositionModal(ModalScreen[tuple[float, float] | None]):
    """A modal dialog for adding or editing an option position."""
    
    def __init__(self, symbol: str, current_position: dict | None = None) -> None:
        """
        Args:
            symbol: The option symbol being edited.
            current_position: Dictionary containing current position data (quantity, avg_cost).
        """
        super().__init__()
        self.symbol = symbol
        self.current_position = current_position or {}
        
    def compose(self) -> ComposeResult:
        """Creates the layout for the position modal."""
        with Vertical(id="dialog"):
            yield Label(f"Edit Position: {self.symbol}", classes="modal-header")
            
            with Grid(classes="input-grid"):
                yield Label("Quantity:", classes="field-label")
                yield Input(
                    value=str(self.current_position.get('quantity', '')),
                    placeholder="e.g. 1, -1",
                    id="quantity-input",
                    validators=[Number(minimum=None, maximum=None)]
                )
                
                yield Label("Avg Cost:", classes="field-label")
                yield Input(
                    value=str(self.current_position.get('avg_cost', '')),
                    placeholder="e.g. 1.50",
                    id="cost-input",
                    validators=[Number(minimum=0.0)]
                )
            
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                if self.current_position:
                    yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", id="cancel")
    
    def on_mount(self) -> None:
        """Sets focus to the quantity field when the modal is mounted."""
        self.query_one("#quantity-input").focus()
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
            
        if event.button.id == "delete":
            # Return a special signal for deletion, e.g., quantity=0
            self.dismiss((0.0, 0.0))
            return
        
        if event.button.id == "save":
            qty_input = self.query_one("#quantity-input", Input)
            cost_input = self.query_one("#cost-input", Input)
            
            # Validate
            if not qty_input.is_valid or not cost_input.is_valid:
                return
                
            try:
                qty = float(qty_input.value)
                cost = float(cost_input.value) if cost_input.value else 0.0
                self.dismiss((qty, cost))
            except ValueError:
                pass
