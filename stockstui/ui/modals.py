from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual import on

# FIX: Changed 'from common import ...' to an absolute import from the package root.
from stockstui.common import NotEmpty
from stockstui.utils import slugify, parse_tags, format_tags

class ConfirmDeleteModal(ModalScreen[bool]):
    """A modal dialog for confirming a deletion, optionally requiring text input for confirmation."""
    def __init__(self, item_name: str, prompt: str, require_typing: bool = False) -> None:
        """
        Args:
            item_name: The name of the item being deleted (used for confirmation typing).
            prompt: The message displayed to the user.
            require_typing: If True, the user must type `item_name` to enable the delete button.
        """
        super().__init__()
        self.item_name = item_name
        self.prompt_text = prompt
        self.require_typing = require_typing

    def compose(self) -> ComposeResult:
        """Creates the layout for the confirmation modal."""
        with Vertical(id="dialog"):
            yield Label(self.prompt_text)
            if self.require_typing:
                yield Input(placeholder=self.item_name, id="confirmation_input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Delete", variant="error", id="delete", disabled=self.require_typing)
                yield Button("Cancel", id="cancel")

    @on(Input.Changed, "#confirmation_input")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Enables/disables the delete button based on confirmation input."""
        self.query_one("#delete", Button).disabled = event.value != self.item_name

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismisses the modal, returning True if delete was pressed, False otherwise."""
        self.dismiss(event.button.id == "delete")

class EditListModal(ModalScreen[str | None]):
    """A modal dialog for editing the name of an existing list."""
    def __init__(self, current_name: str) -> None:
        """
        Args:
            current_name: The current name of the list being edited.
        """
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        """Creates the layout for the edit list modal."""
        with Vertical(id="dialog"):
            yield Label("Enter new list name:")
            yield Input(value=self.current_name, id="list-name-input", validators=[NotEmpty()])
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Sets focus to the input field when the modal is mounted."""
        self.query_one(Input).focus()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with the new name or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        input_widget = self.query_one(Input)
        if event.button.id == "save" and input_widget.validate(input_widget.value).is_valid:
            self.dismiss(slugify(input_widget.value))

class AddListModal(ModalScreen[str | None]):
    """A modal dialog for adding a new list."""
    def compose(self) -> ComposeResult:
        """Creates the layout for the add list modal."""
        with Vertical(id="dialog"):
            yield Label("Enter new list name (e.g., 'crypto'):")
            yield Input(placeholder="List Name", id="list-name-input", validators=[NotEmpty()])
            with Horizontal(id="dialog-buttons"):
                yield Button("Add", variant="primary", id="add")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Sets focus to the input field when the modal is mounted."""
        self.query_one(Input).focus()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with the new name or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        input_widget = self.query_one(Input)
        if event.button.id == "add" and input_widget.validate(input_widget.value).is_valid:
            self.dismiss(slugify(input_widget.value))

class AddTickerModal(ModalScreen[tuple[str, str, str, str] | None]):
    """A modal dialog for adding a new ticker to a list or portfolio."""
    def __init__(self, context: str = "list") -> None:
        """
        Args:
            context: Either "list" or "portfolio" to customize the dialog
        """
        super().__init__()
        self.context = context
    
    def compose(self) -> ComposeResult:
        """Creates the layout for the add ticker modal."""
        with Vertical(id="dialog"):
            if self.context == "portfolio":
                yield Label("Add stock to portfolio:")
                yield Input(placeholder="Ticker (e.g., AAPL)", id="ticker-input", validators=[NotEmpty()])
                yield Input(placeholder="Tags (optional, e.g., tech growth)", id="tags-input")
            else:
                yield Label("Enter new ticker details:")
                yield Input(placeholder="Ticker (e.g., AAPL)", id="ticker-input", validators=[NotEmpty()])
                yield Input(placeholder="Alias (optional, e.g., Apple)", id="alias-input")
                yield Input(placeholder="Note (optional, e.g., Personal reminder)", id="note-input")
                yield Input(placeholder="Tags (optional, e.g., tech growth)", id="tags-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Add", variant="primary", id="add")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Sets focus to the ticker input field when the modal is mounted."""
        self.query_one("#ticker-input").focus()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with ticker details or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        ticker_input = self.query_one("#ticker-input", Input)
        if event.button.id == "add" and ticker_input.validate(ticker_input.value).is_valid:
            ticker = ticker_input.value.strip().upper()
            tags_input = self.query_one("#tags-input", Input).value.strip()
            tags = format_tags(parse_tags(tags_input))
            
            if self.context == "portfolio":
                # For portfolio context, return ticker with tags
                self.dismiss((ticker, "", "", tags))
            else:
                alias = self.query_one("#alias-input", Input).value.strip() or ticker
                note = self.query_one("#note-input", Input).value.strip()
                self.dismiss((ticker, alias, note, tags))

class EditTickerModal(ModalScreen[tuple[str, str, str, str] | None]):
    """A modal dialog for editing an existing ticker's details."""
    def __init__(self, ticker: str, alias: str, note: str, tags: str = "") -> None:
        """
        Args:
            ticker: The current ticker symbol.
            alias: The current alias for the ticker.
            note: The current note for the ticker.
            tags: The current tags for the ticker (comma-separated string).
        """
        super().__init__()
        self.ticker = ticker
        self.alias = alias
        self.note = note
        self.tags = tags

    def compose(self) -> ComposeResult:
        """Creates the layout for the edit ticker modal."""
        with Vertical(id="dialog"):
            yield Label("Edit ticker details:")
            yield Input(value=self.ticker, id="ticker-input", validators=[NotEmpty()])
            yield Input(value=self.alias, id="alias-input")
            yield Input(value=self.note, id="note-input")
            yield Input(value=self.tags, id="tags-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Sets focus to the ticker input field when the modal is mounted."""
        self.query_one("#ticker-input").focus()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with updated ticker details or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        ticker_input = self.query_one("#ticker-input", Input)
        if event.button.id == "save" and ticker_input.validate(ticker_input.value).is_valid:
            ticker = ticker_input.value.strip().upper()
            alias = self.query_one("#alias-input").value.strip() or ticker # Default alias to ticker if empty
            note = self.query_one("#note-input").value.strip()
            tags_input = self.query_one("#tags-input").value.strip()
            tags = format_tags(parse_tags(tags_input))
            self.dismiss((ticker, alias, note, tags))

class CompareInfoModal(ModalScreen[str | None]):
    """A modal dialog to get a ticker symbol for the info comparison debug test."""
    def compose(self) -> ComposeResult:
        """Creates the layout for the compare info modal."""
        with Vertical(id="dialog"):
            yield Label("Enter ticker symbol to compare info:")
            yield Input(placeholder="e.g., AAPL", id="ticker-input", validators=[NotEmpty()])
            with Horizontal(id="dialog-buttons"):
                yield Button("Run Test", variant="primary", id="run")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Sets focus to the input field when the modal is mounted."""
        self.query_one(Input).focus()

    def _submit(self) -> None:
        """Validates the input and dismisses the modal with the uppercase ticker symbol."""
        ticker_input = self.query_one("#ticker-input", Input)
        if ticker_input.validate(ticker_input.value).is_valid:
            self.dismiss(ticker_input.value.strip().upper())
            
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses (Run Test or Cancel)."""
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "run":
            self._submit()

    @on(Input.Submitted, "#ticker-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handles input submission (Enter key), triggering the submit logic."""
        self._submit()

class CreatePortfolioModal(ModalScreen[tuple[str, str] | None]):
    """A modal dialog for creating a new portfolio."""
    def compose(self) -> ComposeResult:
        """Creates the layout for the create portfolio modal."""
        with Vertical(id="dialog"):
            yield Label("Create New Portfolio")
            yield Input(placeholder="Portfolio Name", id="name-input", validators=[NotEmpty()])
            yield Input(placeholder="Description (optional)", id="description-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")
    
    def on_mount(self) -> None:
        """Sets focus to the name input field when the modal is mounted."""
        self.query_one("#name-input").focus()
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with portfolio details or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        name_input = self.query_one("#name-input", Input)
        if event.button.id == "create" and name_input.validate(name_input.value).is_valid:
            name = name_input.value.strip()
            description = self.query_one("#description-input").value.strip()
            self.dismiss((name, description))

class EditPortfolioModal(ModalScreen[tuple[str, str] | None]):
    """A modal dialog for editing an existing portfolio."""
    def __init__(self, current_name: str, current_description: str) -> None:
        """
        Args:
            current_name: The current portfolio name
            current_description: The current portfolio description
        """
        super().__init__()
        self.current_name = current_name
        self.current_description = current_description
    
    def compose(self) -> ComposeResult:
        """Creates the layout for the edit portfolio modal."""
        with Vertical(id="dialog"):
            yield Label("Edit Portfolio")
            yield Input(value=self.current_name, id="name-input", validators=[NotEmpty()])
            yield Input(value=self.current_description, id="description-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")
    
    def on_mount(self) -> None:
        """Sets focus to the name input field when the modal is mounted."""
        self.query_one("#name-input").focus()
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button presses, dismissing the modal with updated details or None."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        name_input = self.query_one("#name-input", Input)
        if event.button.id == "save" and name_input.validate(name_input.value).is_valid:
            name = name_input.value.strip()
            description = self.query_one("#description-input").value.strip()
            self.dismiss((name, description))

class ConfirmAddToAllPortfoliosModal(ModalScreen[bool]):
    """A modal dialog for confirming when adding a stock to all portfolios."""
    def __init__(self, ticker: str, portfolio_count: int) -> None:
        """
        Args:
            ticker: The ticker being added
            portfolio_count: Number of portfolios it will be added to
        """
        super().__init__()
        self.ticker = ticker
        self.portfolio_count = portfolio_count
    
    def compose(self) -> ComposeResult:
        """Creates the layout for the confirmation modal."""
        with Vertical(id="dialog"):
            yield Label(f"Add {self.ticker} to all {self.portfolio_count} portfolios?")
            yield Label("This will add the stock to every portfolio you have created.", classes="dim")
            with Horizontal(id="dialog-buttons"):
                yield Button("Add to All", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")
    
    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismisses the modal, returning True if confirmed, False otherwise."""
        self.dismiss(event.button.id == "confirm")