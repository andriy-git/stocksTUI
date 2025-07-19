from textual.containers import Vertical, Horizontal
from textual.widgets import (Button, Checkbox, DataTable, Input, Label,
                             ListView, Select, Switch, ListItem)
from textual.app import ComposeResult, on
from textual.dom import NoMatches
from textual.validation import Number
from rich.text import Text

from stockstui.ui.modals import (ConfirmDeleteModal, EditListModal, AddListModal,
                                 AddTickerModal, EditTickerModal)
from stockstui.utils import extract_cell_text, slugify
from stockstui.common import NotEmpty

class ConfigView(Vertical):
    """A view for configuring application settings, symbol lists, and tab visibility."""

    def compose(self) -> ComposeResult:
        """Creates the layout for the configuration view."""
        # Top section for general settings and tab visibility
        with Horizontal(id="top-config-container"):
            # Left side for general application settings
            with Vertical(id="general-settings-container"):
                yield Label("General Settings", classes="config-header")
                with Vertical(classes="config-option-stacked"):
                    yield Label("Default Tab:"); yield Select([], id="default-tab-select", allow_blank=True)
                with Vertical(classes="config-option-stacked"):
                    yield Label("Theme:"); yield Select([], id="theme-select", allow_blank=True)
                with Vertical(classes="config-option-stacked"):
                    yield Label("Market Status Calendar:")
                    yield Select([
                        # Americas
                        ("NYSE (US)", "NYSE"),
                        ("TSX (Toronto)", "TSX"),
                        ("BMF (Brazil)", "BMF"),
                        # Europe
                        ("LSE (London)", "LSE"),
                        ("EUREX (Europe)", "EUREX"),
                        ("SIX (Swiss)", "SIX"),
                        ("OSE (Oslo)", "OSE"),
                        # Asia/Pacific
                        ("JPX (Japan)", "JPX"),
                        ("HKEX (Hong Kong)", "HKEX"),
                        ("SSE (Shanghai)", "SSE"),
                        ("ASX (Australia)", "ASX"),
                        ("BSE (Bombay)", "BSE"),
                        ("TASE (Tel Aviv)", "TASE"),
                        # Futures
                        ("CME (Chicago)", "CME"),
                        ("CME Equity Futures", "CME_Equity"),
                        ("CME Bond Futures", "CME_Bond"),
                        ("CME Agriculture Futures", "CME_Agriculture"),
                        ("CME Crypto Futures", "CME_Crypto"),
                        ("CFE (CBOE Futures)", "CFE"),
                        ("ICE Futures", "ICE"),
                        # Bonds
                        ("SIFMA US Bonds", "SIFMAUS"),
                        ("SIFMA UK Bonds", "SIFMAUK"),
                        ("SIFMA JP Bonds", "SIFMAJP"),
                    ], id="market-calendar-select")
                with Vertical(classes="config-option-stacked"):
                    yield Label("Auto Refresh:"); yield Switch(id="auto-refresh-switch")
                with Vertical(classes="config-option-stacked"):
                    yield Label("Refresh Interval (s):")
                    with Horizontal():
                        yield Input(id="refresh-interval-input", validators=[NotEmpty(), Number()]); yield Button("Update", id="update-refresh-interval")
            # Right side for managing which tabs are visible
            with Vertical(id="visibility-settings-container"):
                yield Label("Visible Tabs", classes="config-header"); yield Vertical(id="visible-tabs-container")
        
        # Bottom section for managing symbol lists and their contents
        yield Label("Symbol List Management", classes="config-header")
        with Horizontal(id="list-management-container"):
            # Left side for the list of symbol lists (e.g., Watchlist, Tech)
            with Vertical(id="list-view-container"):
                yield ListView(id="symbol-list-view")
                with Vertical(id="list-buttons"):
                    yield Button("Add List", id="add_list"); yield Button("Rename List", id="rename_list"); yield Button("Delete List", id="delete_list", variant="error"); yield Button("Move Up", id="move_list_up"); yield Button("Move Down", id="move_list_down")
            # Right side for the table of tickers within the selected list
            with Vertical(id="ticker-view-container"):
                yield DataTable(id="ticker-table", zebra_stripes=True)
                with Vertical(id="ticker-buttons-container"):
                    yield Button("Add Ticker", id="add_ticker"); yield Button("Edit Ticker", id="edit_ticker"); yield Button("Remove Ticker", id="delete_ticker", variant="error"); yield Button("Move Ticker Up", id="move_ticker_up"); yield Button("Move Ticker Down", id="move_ticker_down")

    def on_mount(self) -> None:
        """Called when the ConfigView is mounted. Sets up initial static state."""
        # Add columns to the ticker DataTable
        self.query_one("#ticker-table", DataTable).add_columns("Ticker", "Alias", "Note", "Tags")
        # Note: The main App class is responsible for populating dynamic values from config.

    def _update_list_highlight(self) -> None:
        """Applies a specific CSS class to the currently active list item in the ListView."""
        try:
            list_view = self.query_one("#symbol-list-view", ListView)
            active_category = self.app.active_list_category
            for item in list_view.children:
                if isinstance(item, ListItem):
                    item.remove_class("active-list-item")
                    if item.name == active_category:
                        item.add_class("active-list-item")
        except NoMatches:
            pass

    def _populate_ticker_table(self):
        """
        Populates the ticker DataTable with symbols from the currently active list.
        Applies theme-based styling to the 'Note' and 'Tags' columns.
        """
        table = self.query_one("#ticker-table", DataTable)
        table.clear()
        if self.app.active_list_category:
            muted_color = self.app.theme_variables.get("text-muted", "dim")
            # Get the tickers for the active category.
            list_data = self.app.config.lists.get(self.app.active_list_category, [])
            for item in list_data:
                ticker = item['ticker']
                alias = item.get('alias', ticker) # Use ticker as alias if not specified
                note_raw = item.get('note') or 'N/A'
                note_text = Text(note_raw, style=muted_color if note_raw == 'N/A' else "")
                tags_raw = item.get('tags') or 'N/A'
                tags_text = Text(tags_raw, style=muted_color if tags_raw == 'N/A' else "")
                table.add_row(ticker, alias, note_text, tags_text, key=ticker) # Use ticker as row key

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected):
        """Handles selection of a list from the symbol list ListView."""
        self.app.active_list_category = event.item.name
        self._populate_ticker_table()
        self._update_list_highlight()

    @on(Button.Pressed, "#update-refresh-interval")
    def on_update_refresh_button_pressed(self):
        """Handles the 'Update' button press for the refresh interval setting."""
        input_widget = self.query_one("#refresh-interval-input", Input)
        validation_result = input_widget.validate(input_widget.value)

        if validation_result.is_valid:
            self.app.config.settings['refresh_interval'] = float(input_widget.value)
            self.app.config.save_settings()
            self.app._manage_refresh_timer()
            self.app.notify("Refresh interval updated.")
        else:
            if validation_result.failures:
                error_message = ". ".join(f.description for f in validation_result.failures)
                self.app.notify(error_message, severity="error", timeout=5)
            else:
                self.app.notify("Invalid interval value.", severity="error")


    @on(Switch.Changed, "#auto-refresh-switch")
    def on_switch_changed(self, event: Switch.Changed):
        """Handles changes to the 'Auto Refresh' switch."""
        self.app.config.settings['auto_refresh'] = event.value
        self.app.config.save_settings()
        self.app._manage_refresh_timer()

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed):
        """Handles changes to Select widgets (Default Tab, Theme, Market Calendar)."""
        if event.value is Select.BLANK: return
        
        if event.select.id == "default-tab-select":
            self.app.config.settings['default_tab_category'] = str(event.value)
        elif event.select.id == "theme-select":
            theme_name = str(event.value)
            self.app.app.theme = self.app.config.settings['theme'] = theme_name
            self.app._update_theme_variables(theme_name)
        elif event.select.id == "market-calendar-select":
            self.app.config.settings['market_calendar'] = str(event.value)
            self.app.action_refresh(force=True) # Refresh data when market calendar changes
        self.app.config.save_settings()

    @on(Checkbox.Changed)
    async def on_tab_visibility_toggled(self, event: Checkbox.Changed):
        """Handles changes to tab visibility checkboxes."""
        hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
        category = event.checkbox.name
        if event.value:
            # If checkbox is checked (visible), remove from hidden list
            if category in hidden_tabs: hidden_tabs.remove(category)
        else:
            # If checkbox is unchecked (hidden), add to hidden list
            if category not in hidden_tabs: hidden_tabs.append(category)
        self.app.config.settings['hidden_tabs'] = hidden_tabs
        self.app.config.save_settings()
        await self.app._rebuild_app('configs') # Rebuild app to reflect tab changes

    @on(Button.Pressed, "#add_list")
    def on_add_list_pressed(self):
        """Handles the 'Add List' button press, opening a modal for new list name."""
        async def on_close(new_name: str | None):
            if new_name and new_name not in self.app.config.lists:
                self.app.config.lists[new_name] = []
                self.app.config.save_lists()
                await self.app._rebuild_app('configs') # Rebuild app to show new list tab
                self.app.notify(f"List '{new_name}' added.")
        self.app.push_screen(AddListModal(), on_close)

    @on(Button.Pressed, "#add_ticker")
    def on_add_ticker_pressed(self):
        """Handles the 'Add Ticker' button press, opening a modal for new ticker details."""
        category = self.app.active_list_category
        if not category:
            self.app.notify("Select a list first.", severity="warning")
            return

        def on_close(result: tuple[str, str, str, str] | None):
            if result:
                ticker, alias, note, tags = result
                # Check for duplicate tickers in the current list
                if any(t['ticker'].upper() == ticker.upper() for t in self.app.config.lists[category]):
                    self.app.notify(f"Ticker '{ticker}' already exists in this list.", severity="error")
                    return
                self.app.config.lists[category].append({"ticker": ticker, "alias": alias, "note": note, "tags": tags})
                self.app.config.save_lists()
                self._populate_ticker_table()
                self.app.notify(f"Ticker '{ticker}' added.")
        self.app.push_screen(AddTickerModal(), on_close)

    @on(Button.Pressed, "#delete_list")
    def on_delete_list_pressed(self):
        """Handles the 'Delete List' button press, opening a confirmation modal."""
        category = self.app.active_list_category
        if not category:
            self.app.notify("Select a list to delete.", severity="warning")
            return
        prompt = (f"This will permanently delete the list '{category}'.\n\n"
                  f"To confirm, please type '{category}' in the box below.")
        self.app.push_screen(ConfirmDeleteModal(category, prompt, require_typing=True), self.on_delete_list_confirmed)

    async def on_delete_list_confirmed(self, confirmed: bool):
        """Callback for the delete list confirmation modal."""
        if confirmed:
            category = self.app.active_list_category
            settings_updated = False

            # If the deleted list was the default tab, reset default tab to 'all'
            if self.app.config.get_setting("default_tab_category") == category:
                self.app.config.settings["default_tab_category"] = "all"
                settings_updated = True
            
            # If the deleted list was hidden, remove it from hidden tabs
            hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
            if category in hidden_tabs:
                hidden_tabs.remove(category)
                self.app.config.settings['hidden_tabs'] = hidden_tabs
                settings_updated = True

            if settings_updated:
                self.app.config.save_settings()

            del self.app.config.lists[category]
            self.app.active_list_category = None
            self.app.config.save_lists()
            await self.app._rebuild_app('configs') # Rebuild app to remove deleted list tab
            self.app.notify(f"List '{category}' deleted.")

    @on(Button.Pressed, "#rename_list")
    def on_rename_list_pressed(self):
        """Handles the 'Rename List' button press, opening a modal for new name."""
        category = self.app.active_list_category
        if not category:
            self.app.notify("Select a list to rename.", severity="warning")
            return
        async def on_close(new_name: str | None):
            if new_name and new_name != category and new_name not in self.app.config.lists:
                settings_updated = False
                
                # Rename the list in the lists.json data
                self.app.config.lists = { (new_name if k == category else k): v for k, v in self.app.config.lists.items() }
                
                # Update app state if the renamed list was active
                if self.app.active_list_category == category:
                    self.app.active_list_category = new_name

                # Check and update default_tab_category if it referred to the old name
                if self.app.config.get_setting("default_tab_category") == category:
                    self.app.config.settings["default_tab_category"] = new_name
                    settings_updated = True
                
                # Check and update hidden_tabs if it referred to the old name
                hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
                if category in hidden_tabs:
                    hidden_tabs = [new_name if tab == category else tab for tab in hidden_tabs]
                    self.app.config.settings['hidden_tabs'] = hidden_tabs
                    settings_updated = True
                
                # Save settings if anything changed
                if settings_updated:
                    self.app.config.save_settings()

                self.app.config.save_lists()
                await self.app._rebuild_app('configs') # Rebuild app to reflect renamed list tab
                self.app.notify(f"List '{category}' renamed to '{new_name}'.")
        self.app.push_screen(EditListModal(category), on_close)

    @on(Button.Pressed, "#edit_ticker")
    def on_edit_ticker_pressed(self):
        """Handles the 'Edit Ticker' button press, opening a modal to edit ticker details."""
        table = self.query_one("#ticker-table", DataTable)
        if not self.app.active_list_category or table.cursor_row < 0:
            self.app.notify("Select a ticker to edit.", severity="warning")
            return
        
        # Get original ticker details from the table
        original_ticker = extract_cell_text(table.get_cell_at((table.cursor_row, 0)))
        original_alias = extract_cell_text(table.get_cell_at((table.cursor_row, 1)))
        original_note = extract_cell_text(table.get_cell_at((table.cursor_row, 2)))
        original_tags = extract_cell_text(table.get_cell_at((table.cursor_row, 3)))

        def on_close(result: tuple[str, str, str, str] | None):
            if result:
                new_ticker, new_alias, new_note, new_tags = result
                # Check for duplicate tickers (excluding the original ticker being edited)
                is_duplicate = any(item['ticker'].upper() == new_ticker.upper() for item in self.app.config.lists[self.app.active_list_category] if item['ticker'].upper() != original_ticker.upper())
                if is_duplicate:
                    self.app.notify(f"Ticker '{new_ticker}' already exists in this list.", severity="error")
                    return
                # Find and update the ticker in the config
                for item in self.app.config.lists[self.app.active_list_category]:
                    if item['ticker'].upper() == original_ticker.upper():
                        item['ticker'] = new_ticker
                        item['alias'] = new_alias
                        item['note'] = new_note
                        item['tags'] = new_tags
                        break
                self.app.config.save_lists()
                self._populate_ticker_table()
                self.app.notify(f"Ticker '{original_ticker}' updated.")
        # Handle backward compatibility for tags
        display_tags = original_tags if original_tags != 'N/A' else ""
        self.app.push_screen(EditTickerModal(original_ticker, original_alias, original_note, display_tags), on_close)

    @on(Button.Pressed, "#delete_ticker")
    def on_delete_ticker_pressed(self):
        """Handles the 'Remove Ticker' button press, opening a confirmation modal."""
        table = self.query_one("#ticker-table", DataTable)
        if not self.app.active_list_category or table.cursor_row < 0:
            self.app.notify("Select a ticker to delete.", severity="warning")
            return
        ticker = extract_cell_text(table.get_cell_at((table.cursor_row, 0)))
        def on_close(confirmed: bool):
            if confirmed:
                # Filter out the deleted ticker from the list
                self.app.config.lists[self.app.active_list_category] = [item for item in self.app.config.lists[self.app.active_list_category] if item['ticker'].upper() != ticker.upper()]
                self.app.config.save_lists()
                self._populate_ticker_table()
                self.app.notify(f"Ticker '{ticker}' removed.")
        self.app.push_screen(ConfirmDeleteModal(ticker, f"Delete ticker '{ticker}'?"), on_close)

    @on(Button.Pressed, "#move_list_up")
    async def on_move_list_up_pressed(self):
        """Moves the selected list up in the order."""
        category = self.app.active_list_category
        if not category: return
        keys = list(self.app.config.lists.keys())
        idx = keys.index(category)
        if idx > 0:
            keys.insert(idx - 1, keys.pop(idx)) # Move item up by re-inserting
            self.app.config.lists = {k: self.app.config.lists[k] for k in keys} # Reconstruct dict to preserve order
            self.app.config.save_lists()
            await self.app._rebuild_app('configs') # Rebuild app to reflect new list order
            self.query_one(ListView).index = idx - 1 # Maintain selection

    @on(Button.Pressed, "#move_list_down")
    async def on_move_list_down_pressed(self):
        """Moves the selected list down in the order."""
        category = self.app.active_list_category
        if not category: return
        keys = list(self.app.config.lists.keys())
        idx = keys.index(category)
        if 0 <= idx < len(keys) - 1:
            keys.insert(idx + 1, keys.pop(idx)) # Move item down by re-inserting
            self.app.config.lists = {k: self.app.config.lists[k] for k in keys} # Reconstruct dict to preserve order
            self.app.config.save_lists()
            await self.app._rebuild_app('configs') # Rebuild app to reflect new list order
            self.query_one(ListView).index = idx + 1 # Maintain selection

    @on(Button.Pressed, "#move_ticker_up")
    def on_move_ticker_up_pressed(self):
        """Moves the selected ticker up within its list."""
        table = self.query_one("#ticker-table", DataTable)
        idx = table.cursor_row
        if self.app.active_list_category and idx > 0:
            ticker_list = self.app.config.lists[self.app.active_list_category]
            ticker_list.insert(idx - 1, ticker_list.pop(idx)) # Move item up
            self.app.config.save_lists()
            self._populate_ticker_table()
            self.call_later(table.move_cursor, row=idx - 1) # Maintain cursor position

    @on(Button.Pressed, "#move_ticker_down")
    def on_move_ticker_down_pressed(self):
        """Moves the selected ticker down within its list."""
        table = self.query_one("#ticker-table", DataTable)
        idx = table.cursor_row
        if self.app.active_list_category and 0 <= idx < len(self.app.config.lists[self.app.active_list_category]) - 1:
            ticker_list = self.app.config.lists[self.app.active_list_category]
            ticker_list.insert(idx + 1, ticker_list.pop(idx)) # Move item down
            self.app.config.save_lists()
            self._populate_ticker_table()
            self.call_later(table.move_cursor, row=idx + 1) # Maintain cursor position
