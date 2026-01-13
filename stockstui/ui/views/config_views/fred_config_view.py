from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Button, DataTable, Input, Label
from textual.app import ComposeResult, on
from textual.dom import NoMatches
from textual.binding import Binding
from textual import work
from rich.text import Text
import logging

from stockstui.ui.modals import AddFredSeriesModal
from stockstui.ui.edit_fred_series_modal import EditFredSeriesModal


class FredConfigView(ScrollableContainer):
    """A view for configuring FRED integration settings."""

    BINDINGS = [
        Binding("j, down", "focus_next", "Next", show=False),
        Binding("k, up", "focus_previous", "Previous", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Creates the layout for the FRED configuration view."""
        # Top section for API Key
        yield Label("FRED Settings", classes="config-header")
        with Horizontal(classes="config-option-horizontal"):
            yield Label("API Key:", classes="config-label")
            yield Input(id="fred-api-key-input", password=True, placeholder="Enter FRED API Key")
            yield Button("Save", id="save-fred-api-key")

        # Series management section (modeled after ticker management)
        yield Label("Series Management", classes="config-header-small")
        yield DataTable(id="fred-series-table", zebra_stripes=True)
        with Vertical(id="fred-series-buttons"):
            yield Button("Add Series", id="add-fred-series")
            yield Button("Edit Series", id="edit-fred-series")
            yield Button("Remove Series", id="remove-fred-series", variant="error")
            yield Button("Move Up", id="move-fred-series-up")
            yield Button("Move Down", id="move-fred-series-down")

    def on_mount(self) -> None:
        """Called when the view is mounted."""
        table = self.query_one("#fred-series-table", DataTable)
        table.add_columns("Series ID", "Alias", "Description")
        self.repopulate_settings()
        self.repopulate_series_table()

    def repopulate_settings(self):
        """Populate generic settings."""
        settings = self.app.config.settings.get("fred_settings", {})
        self.query_one("#fred-api-key-input", Input).value = settings.get("api_key", "")

    def repopulate_series_table(self):
        """Populate the series DataTable with descriptions (cached or from API)."""
        table = self.query_one("#fred-series-table", DataTable)
        table.clear()
        
        settings = self.app.config.settings.get("fred_settings", {})
        series_list = settings.get("series_list", [])
        aliases = settings.get("series_aliases", {})
        cached_descriptions = settings.get("series_descriptions", {})
        api_key = settings.get("api_key", "")
        
        muted_color = self.app.theme_variables.get("text-muted", "dim")
        
        # Track which series need fetching
        missing_descriptions = []
        
        for series_id in series_list:
            alias = aliases.get(series_id, "")
            alias_text = Text(alias if alias else "—", style=muted_color if not alias else "")
            
            cached_desc = cached_descriptions.get(series_id)
            if cached_desc:
                desc_text = Text(cached_desc)
            else:
                desc_text = Text("Loading...", style=muted_color)
                missing_descriptions.append(series_id)
            
            table.add_row(series_id, alias_text, desc_text, key=series_id)
        
        # Only fetch missing descriptions
        if missing_descriptions and api_key:
            table.loading = True
            self._fetch_descriptions(missing_descriptions, api_key)

    @work(exclusive=True, thread=True)
    def _fetch_descriptions(self, series_list: list, api_key: str):
        """Fetch descriptions for series from FRED API and cache them directly."""
        from stockstui.data_providers import fred_provider
        
        logging.info(f"FRED: Fetching descriptions for {series_list}")
        descriptions = {}
        for series_id in series_list:
            info = fred_provider.get_series_info(series_id, api_key)
            logging.info(f"FRED: Got info for {series_id}: {info}")
            if info:
                descriptions[series_id] = info.get("title", series_id)
            else:
                descriptions[series_id] = series_id
        
        logging.info(f"FRED: Descriptions fetched: {descriptions}")
        
        # Save directly to settings (thread-safe since we're just updating a dict)
        try:
            fred_settings = self.app.config.settings.get("fred_settings", {})
            if "series_descriptions" not in fred_settings:
                fred_settings["series_descriptions"] = {}
            fred_settings["series_descriptions"].update(descriptions)
            self.app.config.settings["fred_settings"] = fred_settings
            self.app.config.save_settings()
            logging.info("FRED: Descriptions saved to settings.json")
        except Exception as e:
            logging.error(f"FRED: Failed to save descriptions: {e}")
        
        # Post a message to refresh the table on the main thread
        self.app.call_from_thread(self._refresh_table_with_cache)

    def _refresh_table_with_cache(self):
        """Refresh the table with cached descriptions."""
        logging.info("FRED: _refresh_table_with_cache called")
        try:
            table = self.query_one("#fred-series-table", DataTable)
            table.loading = False
            
            # Guard: ensure table has 3 columns (Series ID, Alias, Description)
            if len(table.columns) < 3:
                logging.info("FRED: Table not fully initialized, skipping refresh")
                return
            
            # Read from cache
            fred_settings = self.app.config.settings.get("fred_settings", {})
            cached_descriptions = fred_settings.get("series_descriptions", {})
            
            # Use columns.values() to safely get the third column key
            column_list = list(table.columns.values())
            desc_column_key = column_list[2].key
            
            for series_id, title in cached_descriptions.items():
                try:
                    table.update_cell(series_id, desc_column_key, title)
                    logging.info(f"FRED: Updated cell for {series_id}")
                except Exception as e:
                    logging.error(f"FRED: Failed to update cell for {series_id}: {e}")
        except NoMatches:
            logging.info("FRED: Table not found, likely view was replaced")

    def on_key(self, event) -> None:
        """Handle keyboard navigation for FRED configuration view."""
        buttons = list(self.query("#fred-series-buttons Button"))
        # Also include the save button at the top
        buttons.insert(0, self.query_one("#save-fred-api-key", Button))
        
        if not buttons:
            return

        # If 'i' is pressed and we aren't already focused on a button, focus the first one.
        if event.key == "i" and self.app.focused not in buttons:
            buttons[0].focus()
            event.stop()
            return

        # Handle cycling through buttons with j, k, up, down
        if self.app.focused in buttons:
            idx = buttons.index(self.app.focused)
            if event.key in ("k", "up"):
                buttons[(idx - 1) % len(buttons)].focus()
                event.stop()
            elif event.key in ("j", "down"):
                buttons[(idx + 1) % len(buttons)].focus()
                event.stop()

    @on(Button.Pressed, "#save-fred-api-key")
    def on_save_api_key(self):
        """Saves the API Key."""
        key = self.query_one("#fred-api-key-input", Input).value.strip()
        fred_settings = self.app.config.settings.get("fred_settings", {})
        fred_settings["api_key"] = key
        
        if "series_list" not in fred_settings:
            fred_settings["series_list"] = ["GDP", "CPIAUCSL", "UNRATE"]

        self.app.config.settings["fred_settings"] = fred_settings
        self.app.config.save_settings()
        self.app.notify("FRED API Key saved.")

    @on(Button.Pressed, "#add-fred-series")
    def on_add_series(self):
        """Adds a new series using a modal."""
        def on_close(result):
            if result:
                # AddTickerModal returns (ticker, alias, note, tags)
                # We only need ticker (as series_id) and alias
                series_id, alias, _, _ = result
                series_id = series_id.upper()
                
                fred_settings = self.app.config.settings.get("fred_settings", {})
                current_list = fred_settings.get("series_list", [])
                
                if series_id in current_list:
                    self.app.notify("Series already in list.", severity="warning")
                    return
                
                current_list.append(series_id)
                fred_settings["series_list"] = current_list
                
                if alias and alias != series_id:
                    if "series_aliases" not in fred_settings:
                        fred_settings["series_aliases"] = {}
                    fred_settings["series_aliases"][series_id] = alias
                
                self.app.config.settings["fred_settings"] = fred_settings
                self.app.config.save_settings()
                self.repopulate_series_table()
                self.app.notify(f"Added series {series_id}")
        
        # Use dedicated AddFredSeriesModal for appropriate context/placeholders
        self.app.push_screen(AddFredSeriesModal(), on_close)

    @on(DataTable.RowSelected, "#fred-series-table")
    def on_row_selected(self):
        """Trigger editing when a row is selected with Enter."""
        self.on_edit_series()

    @on(Button.Pressed, "#edit-fred-series")
    def on_edit_series(self):
        """Edits the selected series alias."""
        table = self.query_one("#fred-series-table", DataTable)
        if table.cursor_row < 0:
            self.app.notify("Select a series to edit.", severity="warning")
            return
        
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if not row_key:
            return
        
        series_id = row_key.value
        settings = self.app.config.settings.get("fred_settings", {})
        aliases = settings.get("series_aliases", {})
        current_alias = aliases.get(series_id, "")
        
        def handle_edit(new_alias: str | None):
            if new_alias is None:
                return
            
            fred_settings = self.app.config.settings.get("fred_settings", {})
            if "series_aliases" not in fred_settings:
                fred_settings["series_aliases"] = {}
            
            if new_alias:
                fred_settings["series_aliases"][series_id] = new_alias
            else:
                if series_id in fred_settings["series_aliases"]:
                    del fred_settings["series_aliases"][series_id]
            
            self.app.config.settings["fred_settings"] = fred_settings
            self.app.config.save_settings()
            self.repopulate_series_table()
            self.app.notify(f"Updated alias for {series_id}")
        
        self.app.push_screen(EditFredSeriesModal(series_id, current_alias), handle_edit)

    @on(Button.Pressed, "#remove-fred-series")
    def on_remove_series(self):
        """Removes the selected series."""
        table = self.query_one("#fred-series-table", DataTable)
        if table.cursor_row < 0:
            self.app.notify("Select a series to remove.", severity="warning")
            return
        
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if not row_key:
            return
        
        series_id = row_key.value
        fred_settings = self.app.config.settings.get("fred_settings", {})
        current_list = fred_settings.get("series_list", [])
        
        if series_id in current_list:
            current_list.remove(series_id)
            fred_settings["series_list"] = current_list
            
            # Also remove alias if exists
            if "series_aliases" in fred_settings and series_id in fred_settings["series_aliases"]:
                del fred_settings["series_aliases"][series_id]
            
            self.app.config.settings["fred_settings"] = fred_settings
            self.app.config.save_settings()
            self.repopulate_series_table()
            self.app.notify(f"Removed series {series_id}")

    @on(Button.Pressed, "#move-fred-series-up")
    def on_move_series_up(self):
        """Moves the selected series up."""
        table = self.query_one("#fred-series-table", DataTable)
        idx = table.cursor_row
        if idx <= 0:
            return
        
        fred_settings = self.app.config.settings.get("fred_settings", {})
        series_list = fred_settings.get("series_list", [])
        
        if idx < len(series_list):
            series_list.insert(idx - 1, series_list.pop(idx))
            fred_settings["series_list"] = series_list
            self.app.config.settings["fred_settings"] = fred_settings
            self.app.config.save_settings()
            self.repopulate_series_table()
            self.call_later(table.move_cursor, row=idx - 1)

    @on(Button.Pressed, "#move-fred-series-down")
    def on_move_series_down(self):
        """Moves the selected series down."""
        table = self.query_one("#fred-series-table", DataTable)
        idx = table.cursor_row
        
        fred_settings = self.app.config.settings.get("fred_settings", {})
        series_list = fred_settings.get("series_list", [])
        
        if 0 <= idx < len(series_list) - 1:
            series_list.insert(idx + 1, series_list.pop(idx))
            fred_settings["series_list"] = series_list
            self.app.config.settings["fred_settings"] = fred_settings
            self.app.config.save_settings()
            self.repopulate_series_table()
            self.call_later(table.move_cursor, row=idx + 1)
