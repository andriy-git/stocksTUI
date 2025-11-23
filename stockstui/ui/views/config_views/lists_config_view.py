from textual.containers import Vertical, Horizontal
from textual.widgets import (Button, DataTable, Input, Label,
                             ListView, ListItem, Switch)
from textual.app import ComposeResult, on
from textual.dom import NoMatches
from rich.text import Text

from stockstui.ui.modals import (ConfirmDeleteModal, EditListModal, AddListModal,
                                 AddTickerModal, EditTickerModal)
from stockstui.utils import extract_cell_text, slugify

class ListsConfigView(Vertical):
    """A view for managing watchlists and the tickers within them."""

    def compose(self) -> ComposeResult:
        """Creates the layout for the list and ticker management view."""
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
        
        yield Label("Columns", classes="config-header-small")
        with Horizontal(id="columns-management-container"):
            with Vertical(id="columns-list-container"):
                # User requested fixed height of 3 (interpreted as 3 items visible or height: 3)
                # Setting height via CSS or inline styles is better, but here we can use id for CSS.
                # We'll assume CSS will handle the height or we can try to enforce it.
                yield ListView(id="columns-list-view")
                with Horizontal(id="column-buttons"):
                    yield Button("Up", id="move_col_up", classes="small-button")
                    yield Button("Down", id="move_col_down", classes="small-button")

    def on_mount(self) -> None:
        """Called when the view is mounted. Sets up initial static state."""
        self.query_one("#ticker-table", DataTable).add_columns("Ticker", "Alias", "Note", "Tags")
        self.repopulate_lists()
        self.repopulate_columns()

    def repopulate_columns(self):
        view = self.query_one("#columns-list-view", ListView)
        view.clear()
        
        columns = self.app.config.get_setting("column_settings", [])
        
        for col in columns:
            if not isinstance(col, dict): continue
            key = col['key']
            visible = col['visible']
            
            item_content = Horizontal(
                Label(key, classes="column-label"),
                Switch(value=visible, classes="column-switch"),
                classes="column-item-layout"
            )
            
            item = ListItem(item_content, name=key)
            view.append(item)

    def repopulate_lists(self):
        """Populates the list of symbol categories from the app's config."""
        try:
            view = self.query_one("#symbol-list-view", ListView)
            view.clear()
            
            session_lists = self.app.cli_overrides.get('session_list') or {}
            categories = [c for c in self.app.config.lists.keys() if c not in session_lists]

            if not categories:
                self.app.active_list_category = None
                self._populate_ticker_table()
                return

            for category in categories:
                view.append(ListItem(Label(category.replace("_", " ").capitalize()), name=category))

            # FIX: Explicitly set the index after populating. The community confirmed
            # that ListView does not automatically select an index.
            new_index = None
            if self.app.active_list_category:
                try:
                    # Find the index of the currently active category
                    new_index = next(
                        i for i, item in enumerate(view.children) if isinstance(item, ListItem) and item.name == self.app.active_list_category
                    )
                except StopIteration:
                    new_index = None
            
            # If no index is set (either because active_list_category was None or not found), default to 0.
            if new_index is None and view.children:
                new_index = 0

            if new_index is not None:
                view.index = new_index
                # Ensure the app's active category state is synced with the view's new index.
                if view.children and isinstance(view.children[new_index], ListItem):
                    self.app.active_list_category = view.children[new_index].name
            else:
                self.app.active_list_category = None

            self._update_list_highlight()
            self._populate_ticker_table()
        except NoMatches:
            pass

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
            list_data = self.app.config.lists.get(self.app.active_list_category, [])
            for item in list_data:
                ticker = item['ticker']
                alias = item.get('alias', ticker)
                note_raw = item.get('note') or 'N/A'
                note_text = Text(note_raw, style=muted_color if note_raw == 'N/A' else "")
                tags_raw = item.get('tags') or 'N/A'
                tags_text = Text(tags_raw, style=muted_color if tags_raw == 'N/A' else "")
                table.add_row(ticker, alias, note_text, tags_text, key=ticker)

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected):
        """Handles selection of a list from the symbol list ListView or toggling a column."""
        if event.control.id == "symbol-list-view":
            self.app.active_list_category = event.item.name
            self._populate_ticker_table()
            self._update_list_highlight()
        elif event.control.id == "columns-list-view":
            # Toggle the switch inside the selected item
            switch = event.item.query_one(Switch)
            switch.value = not switch.value

    @on(Button.Pressed, "#add_list")
    def on_add_list_pressed(self):
        """Handles the 'Add List' button press, opening a modal for new list name."""
        async def on_close(new_name: str | None):
            if new_name and new_name not in self.app.config.lists:
                self.app.config.lists[new_name] = []
                self.app.config.save_lists()
                await self.app._rebuild_app('configs', config_sub_view='lists')
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

            if self.app.config.get_setting("default_tab_category") == category:
                self.app.config.settings["default_tab_category"] = "all"
                settings_updated = True
            
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
            await self.app._rebuild_app('configs', config_sub_view='lists')
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
                
                self.app.config.lists = { (new_name if k == category else k): v for k, v in self.app.config.lists.items() }
                
                if self.app.active_list_category == category:
                    self.app.active_list_category = new_name

                if self.app.config.get_setting("default_tab_category") == category:
                    self.app.config.settings["default_tab_category"] = new_name
                    settings_updated = True
                
                hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
                if category in hidden_tabs:
                    hidden_tabs = [new_name if tab == category else tab for tab in hidden_tabs]
                    self.app.config.settings['hidden_tabs'] = hidden_tabs
                    settings_updated = True
                
                if settings_updated:
                    self.app.config.save_settings()

                self.app.config.save_lists()
                await self.app._rebuild_app('configs', config_sub_view='lists')
                self.app.notify(f"List '{category}' renamed to '{new_name}'.")
        self.app.push_screen(EditListModal(category), on_close)

    @on(Button.Pressed, "#edit_ticker")
    def on_edit_ticker_pressed(self):
        """Handles the 'Edit Ticker' button press, opening a modal to edit ticker details."""
        table = self.query_one("#ticker-table", DataTable)
        if not self.app.active_list_category or table.cursor_row < 0:
            self.app.notify("Select a ticker to edit.", severity="warning")
            return
        
        original_ticker = extract_cell_text(table.get_cell_at((table.cursor_row, 0)))
        original_alias = extract_cell_text(table.get_cell_at((table.cursor_row, 1)))
        original_note = extract_cell_text(table.get_cell_at((table.cursor_row, 2)))
        original_tags = extract_cell_text(table.get_cell_at((table.cursor_row, 3)))

        def on_close(result: tuple[str, str, str, str] | None):
            if result:
                new_ticker, new_alias, new_note, new_tags = result
                is_duplicate = any(item['ticker'].upper() == new_ticker.upper() for item in self.app.config.lists[self.app.active_list_category] if item['ticker'].upper() != original_ticker.upper())
                if is_duplicate:
                    self.app.notify(f"Ticker '{new_ticker}' already exists in this list.", severity="error")
                    return
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
            keys.insert(idx - 1, keys.pop(idx))
            self.app.config.lists = {k: self.app.config.lists[k] for k in keys}
            self.app.config.save_lists()
            await self.app._rebuild_app('configs', config_sub_view='lists')
            self.query_one(ListView).index = idx - 1

    @on(Button.Pressed, "#move_list_down")
    async def on_move_list_down_pressed(self):
        """Moves the selected list down in the order."""
        category = self.app.active_list_category
        if not category: return
        keys = list(self.app.config.lists.keys())
        idx = keys.index(category)
        if 0 <= idx < len(keys) - 1:
            keys.insert(idx + 1, keys.pop(idx))
            self.app.config.lists = {k: self.app.config.lists[k] for k in keys}
            self.app.config.save_lists()
            await self.app._rebuild_app('configs', config_sub_view='lists')
            self.query_one(ListView).index = idx + 1

    @on(Button.Pressed, "#move_ticker_up")
    def on_move_ticker_up_pressed(self):
        """Moves the selected ticker up within its list."""
        table = self.query_one("#ticker-table", DataTable)
        idx = table.cursor_row
        if self.app.active_list_category and idx > 0:
            ticker_list = self.app.config.lists[self.app.active_list_category]
            ticker_list.insert(idx - 1, ticker_list.pop(idx))
            self.app.config.save_lists()
            self._populate_ticker_table()
            self.call_later(table.move_cursor, row=idx - 1)

    @on(Button.Pressed, "#move_ticker_down")
    def on_move_ticker_down_pressed(self):
        """Moves the selected ticker down within its list."""
        table = self.query_one("#ticker-table", DataTable)
        idx = table.cursor_row
        if self.app.active_list_category and 0 <= idx < len(self.app.config.lists[self.app.active_list_category]) - 1:
            ticker_list = self.app.config.lists[self.app.active_list_category]
            ticker_list.insert(idx + 1, ticker_list.pop(idx))
            self.app.config.save_lists()
            self._populate_ticker_table()
            self.call_later(table.move_cursor, row=idx + 1)

    @on(Switch.Changed)
    def on_column_visibility_changed(self, event: Switch.Changed):
        switch = event.switch
        # Check if this switch belongs to the columns list
        if "column-switch" not in switch.classes:
            return

        key = None
        for ancestor in switch.ancestors:
            if isinstance(ancestor, ListItem):
                key = ancestor.name
                break
        
        if not key: return
            
        columns = self.app.config.get_setting("column_settings", [])
        for col in columns:
            if not isinstance(col, dict): continue
            if col['key'] == key:
                col['visible'] = event.value
                break
        
        self.app.config.settings['column_settings'] = columns
        self.app.config.save_settings()

    def _update_column_highlight(self):
        """Manually applies a highlight class to the currently selected column item."""
        try:
            view = self.query_one("#columns-list-view", ListView)
            if view.index is not None:
                for i, item in enumerate(view.children):
                    if i == view.index:
                        item.add_class("active-column-item")
                    else:
                        item.remove_class("active-column-item")
        except NoMatches:
            pass

    @on(ListView.Highlighted)
    def on_column_highlighted(self, event: ListView.Highlighted):
        if event.control.id == "columns-list-view":
            self._update_column_highlight()

    @on(Button.Pressed, "#move_col_up")
    def on_move_col_up(self):
        view = self.query_one("#columns-list-view", ListView)
        idx = view.index
        if idx is not None and idx > 0:
            columns = self.app.config.get_setting("column_settings", [])
            columns.insert(idx - 1, columns.pop(idx))
            self.app.config.settings['column_settings'] = columns
            self.app.config.save_settings()
            
            self.repopulate_columns()
            view.index = idx - 1
            self._update_column_highlight()

    @on(Button.Pressed, "#move_col_down")
    def on_move_col_down(self):
        view = self.query_one("#columns-list-view", ListView)
        idx = view.index
        columns = self.app.config.get_setting("column_settings", [])
        if idx is not None and idx < len(columns) - 1:
            columns.insert(idx + 1, columns.pop(idx))
            self.app.config.settings['column_settings'] = columns
            self.app.config.save_settings()
            
            self.repopulate_columns()
            view.index = idx + 1
            self._update_column_highlight()

    def on_key(self, event) -> None:
        """Handles key presses for navigating between buttons."""
        if event.key in ("j", "down", "k", "up"):
            focused = self.app.focused
            if isinstance(focused, Button):
                # Determine direction
                direction = 1 if event.key in ("j", "down") else -1
                
                # Find the container of the focused button
                parent = focused.parent
                if parent and parent.id in ("list-buttons", "ticker-buttons-container"):
                    children = [c for c in parent.children if isinstance(c, Button)]
                    if focused in children:
                        idx = children.index(focused)
                        new_idx = (idx + direction) % len(children)
                        children[new_idx].focus()
                        event.stop()
        elif event.key in ("h", "left", "l", "right"):
            focused = self.app.focused
            if isinstance(focused, Button):
                # Determine direction (left/h = -1, right/l = 1)
                direction = 1 if event.key in ("l", "right") else -1
                
                # Find the container of the focused button
                parent = focused.parent
                if parent and parent.id == "column-buttons":
                    children = [c for c in parent.children if isinstance(c, Button)]
                    if focused in children:
                        idx = children.index(focused)
                        new_idx = (idx + direction) % len(children)
                        children[new_idx].focus()
                        event.stop()
