from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult, on
from textual.containers import Vertical
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from stockstui.ui.views.config_view import ConfigContainer


class MainConfigView(Static):
    """The main hub screen for the configuration tab."""

    def compose(self) -> ComposeResult:
        """Creates the layout for the main config view."""
        with Vertical(classes="vertical-center"):
            yield Button("General Settings", id="goto-general", variant="primary", classes="config-hub-button")
            yield Static(classes="spacer")
            yield Button("Watchlists", id="goto-lists", variant="primary", classes="config-hub-button")
            yield Static(classes="spacer")
            yield Button("Portfolios", id="goto-portfolios", variant="primary", classes="config-hub-button")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses to navigate to different config views."""
        container: "ConfigContainer" = self.query_ancestor("ConfigContainer")
        if event.button.id == "goto-general":
            container.show_general()
        elif event.button.id == "goto-lists":
            container.show_lists()
        elif event.button.id == "goto-portfolios":
            container.show_portfolios()