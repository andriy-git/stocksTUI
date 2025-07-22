from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ContentSwitcher
from textual.dom import NoMatches
from textual.binding import Binding

# Import the new child views from the subdirectory
from .config_views.main_config_view import MainConfigView
from .config_views.general_config_view import GeneralConfigView
from .config_views.lists_config_view import ListsConfigView
from .config_views.portfolio_config_view import PortfolioConfigView


class ConfigContainer(Vertical):
    """A container that manages different configuration views using a ContentSwitcher."""

    # Add a specific binding for 'backspace' to this container.
    # This is not a global binding, so it will only be active when focus
    # is within this container and not captured by a child widget like an Input.
    BINDINGS = [
        Binding("backspace", "go_back", "Back", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # The history stack for navigating "back" with escape or backspace.
        self._history: list[str] = []

    def compose(self) -> ComposeResult:
        """Creates the layout, mounting all child views into a ContentSwitcher."""
        # The ContentSwitcher will manage showing/hiding the different config screens.
        # The `initial` view is the one displayed when the tab is first activated.
        with ContentSwitcher(initial="main"):
            # FIX: Apply a shared class to all child views to make them scrollable.
            yield MainConfigView(id="main", classes="config-view-child")
            yield GeneralConfigView(id="general", classes="config-view-child")
            yield ListsConfigView(id="lists", classes="config-view-child")
            yield PortfolioConfigView(id="portfolios", classes="config-view-child")

    def on_mount(self) -> None:
        """Set focus to the main container and initialize navigation history."""
        self.focus()
        # Initialize the history with the starting view.
        self._history.append(self.query_one(ContentSwitcher).current)

    def _switch_view(self, view_id: str):
        """Switches the view and updates the navigation history."""
        switcher = self.query_one(ContentSwitcher)
        if switcher.current != view_id:
            switcher.current = view_id
            # Only add to history if it's a new view, not a repeat of the last one.
            if not self._history or self._history[-1] != view_id:
                self._history.append(view_id)
        
        try:
            self.query(f"#{view_id}").first().focus()
        except NoMatches:
            pass

    def action_go_back(self) -> bool:
        """
        Goes back to the previous view in the history.
        Returns True if navigation happened, False otherwise.
        """
        if len(self._history) > 1:
            self._history.pop()  # Remove current view from history
            previous_view_id = self._history[-1]  # Get the new top of the stack
            self.query_one(ContentSwitcher).current = previous_view_id
            try:
                self.query(f"#{previous_view_id}").first().focus()
            except NoMatches:
                pass
            return True
        return False
        
    # --- Public API for View Switching ---

    def show_main(self):
        """Switches to the main configuration hub view, resetting history."""
        switcher = self.query_one(ContentSwitcher)
        if switcher.current != "main":
            switcher.current = "main"
        self._history = ["main"]
        try:
            self.query("#main").first().focus()
        except NoMatches:
            pass

    def show_general(self):
        """Switches to the general settings view."""
        self._switch_view("general")

    def show_lists(self):
        """Switches to the watchlist management view."""
        self._switch_view("lists")

    def show_portfolios(self):
        """Switches to the portfolio management view."""
        self._switch_view("portfolios")