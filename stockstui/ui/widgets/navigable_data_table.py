from textual.binding import Binding
from textual.widgets import DataTable

class NavigableDataTable(DataTable):
    """A DataTable with an added binding for 'backspace' to go back."""

    BINDINGS = [
        # This binding allows using backspace to navigate "back" (e.g., focus tabs)
        # when the table is focused, without interfering with Input widgets.
        Binding("backspace", "app.back_or_dismiss", "Back", show=False),
        # This binding allows using 'e' to quickly edit a ticker
        Binding("e", "app.edit_ticker_quick", "Quick Edit", show=False),
    ]