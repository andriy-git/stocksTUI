from textual.binding import Binding
from textual.widgets import RadioSet


class VimRadioSet(RadioSet):
    """A RadioSet widget with added Vim-like (h/l, j/k) keybindings for navigation."""

    # Define custom key bindings for Vim-like navigation
    BINDINGS = [
        Binding(
            "down,right,l", "next_button", "Next option", show=False
        ),  # Move to the next radio button
        Binding(
            "enter,space", "toggle_button", "Toggle", show=False
        ),  # Toggle the selected radio button
        Binding(
            "up,left,h", "previous_button", "Previous option", show=False
        ),  # Move to the previous radio button
    ]
