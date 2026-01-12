from textual.app import ComposeResult, on
from textual.containers import Vertical
from textual.widgets import Label, DataTable
from textual.dom import NoMatches
from textual.binding import Binding
from textual import work
from rich.text import Text
import webbrowser

from stockstui.data_providers import fred_provider
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable
from stockstui.ui.edit_fred_series_modal import EditFredSeriesModal

class FredDataTable(NavigableDataTable):
    """Specific DataTable for FRED view with overridden bindings."""
    
    BINDINGS = [
        # Override 'e' - use 'screen.' prefix won't work. Instead define action here.
        Binding("e", "edit_series", "Edit Alias"),
        Binding("o", "open_series", "Open (Browser)"),
        Binding("backspace", "app.back_or_dismiss", "Back", show=False),
    ]
    
    def action_edit_series(self):
        """Bubble edit_series action to parent FredView."""
        # Find the parent FredView and call its action
        for ancestor in self.ancestors:
            if hasattr(ancestor, 'action_edit_series'):
                ancestor.action_edit_series()
                return

    def action_open_series(self):
        """Bubble open_series action to parent FredView."""
        # Find the parent FredView and call its action
        for ancestor in self.ancestors:
            if hasattr(ancestor, 'action_open_series'):
                ancestor.action_open_series()
                return

class FredView(Vertical):
    """View displaying a summary dashboard of configured FRED series."""

    BINDINGS = [
        Binding("i", "focus_table", "Focus Table", show=False),
        # 'e' might be handled by the table when focused, but we keep this as fallback?
        # Actually bindings on the view are useful if focus is on the view container but not the table?
        # But for 'e' to work on a row, table must be focused.
    ]

    def compose(self) -> ComposeResult:
        yield Label("Economic Data Summary", classes="content-header")
        yield FredDataTable(id="fred-summary-table", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialize the view with enhanced column layout."""
        table = self.query_one("#fred-summary-table", FredDataTable)
        # Enhanced columns per recommended layout:
        # Core signal block: Series, Current, YoY %, Roll-12, Roll-24, Z-10Y
        # Context block: 10Y Min, 10Y Max, % Range, Obs Date, Freq
        table.add_columns(
            "Series",     # Title/alias
            "Current",    # Most recent value
            "YoY %",      # Year-over-year percent change
            "Roll-12",    # 12-month rolling average
            "Roll-24",    # 24-month rolling average
            "Z-10Y",      # Z-score (10-year basis)
            "10Y Min",    # 10-year historical minimum
            "10Y Max",    # 10-year historical maximum
            "% Range",    # Position in historical range
            "Obs Date",   # Most recent observation date
            "Freq",       # M/Q (monthly/quarterly)
            "Units",      # Short units from FRED
        )
        self.load_all_series()
        # NOTE: Do NOT call table.focus() here - it steals focus from Tabs.
        # Focus is managed by the App via action_focus_input (i) or action_activate_tab (Enter).

    def action_focus_table(self):
        """Focus the data table."""
        try:
            self.query_one("#fred-summary-table").focus()
        except NoMatches:
            pass

    def action_edit_series(self):
        """Edit the alias of the selected series."""
        try:
            table = self.query_one("#fred-summary-table", FredDataTable)
            if table.cursor_type == "none":
                return

            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if not row_key:
                return
             
            series_id = row_key.value
            
            settings = self.app.config.settings.get("fred_settings", {})
            aliases = settings.get("series_aliases", {})
            current_alias = aliases.get(series_id, "")
            
            def handle_edit(new_alias: str | None):
                if new_alias is None: return 
                
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
                self.load_all_series() 
                self.app.notify(f"Updated alias for {series_id}")
                
            self.app.push_screen(EditFredSeriesModal(series_id, current_alias), handle_edit)
        except NoMatches:
            pass

    def action_open_series(self):
        """Open the selected FRED series in the default web browser."""
        try:
            table = self.query_one("#fred-summary-table", FredDataTable)
            if table.cursor_type == "none" or table.cursor_row < 0:
                return

            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if not row_key:
                return
             
            series_id = row_key.value
            url = f"https://fred.stlouisfed.org/series/{series_id}"
            
            try:
                self.app.notify(f"Opening FRED for {series_id}...")
                webbrowser.open(url)
            except webbrowser.Error:
                self.app.notify("No web browser found. Please configure your system's default browser.", severity="error", timeout=8)
            except Exception as e:
                self.app.notify(f"Failed to open browser: {e}", severity="error")
        except NoMatches:
            pass

    @work(exclusive=True, thread=True)
    def load_all_series(self):
        """Fetch summary data for all configured series."""
        settings = self.app.config.settings.get("fred_settings", {})
        api_key = settings.get("api_key")
        
        if not api_key:
             self.app.call_from_thread(self._show_error)
             return

        series_list = settings.get("series_list", [])
        if not series_list:
            self.app.call_from_thread(self._display_empty)
            return

        self.app.call_from_thread(self._set_loading, True)
        
        summaries = []
        for series_id in series_list:
            # We fetching sequentially for now to be gentle on limited threads/connections
            # Could be parallelized if needed
            s = fred_provider.get_series_summary(series_id, api_key)
            summaries.append(s)

        self.app.call_from_thread(self._populate_table, summaries)

    def _set_loading(self, loading: bool):
        try:
            self.query_one("#fred-summary-table", DataTable).loading = loading
        except NoMatches:
            pass

    def _show_error(self):
        try:
            table = self.query_one("#fred-summary-table", DataTable)
            table.loading = False
            table.clear()
            table.add_row("Error: API Key missing. Go to Configs > FRED Settings.")
        except NoMatches:
            pass

    def _display_empty(self):
        try:
            table = self.query_one("#fred-summary-table", DataTable)
            table.loading = False
            table.clear()
            table.add_row("No series configured. Go to Configs > FRED Settings to add data.")
        except NoMatches:
            pass

    def _populate_table(self, summaries: list):
        try:
            table = self.query_one("#fred-summary-table", DataTable)
            table.loading = False
            table.clear()

            # Get theme colors for styling
            success_color = self.app.theme_variables.get("success", "green")
            error_color = self.app.theme_variables.get("error", "red")
            warning_color = self.app.theme_variables.get("warning", "yellow")
            text_muted = self.app.theme_variables.get("text-muted", "dim")

            settings = self.app.config.settings.get("fred_settings", {})
            aliases = settings.get("series_aliases", {})

            for item in summaries:
                series_id = item.get("id")
                alias = aliases.get(series_id)

                # Format Name/Title
                if alias:
                    name_text = Text(alias)
                else:
                    name_text = Text(item.get("title", series_id))

                # Format Current Value
                current_val = item.get("current")
                if isinstance(current_val, (int, float)):
                    current_text = Text(f"{current_val:,.2f}", justify="right")
                else:
                    current_text = Text(str(current_val), justify="right", style=text_muted)

                # Helper to format percentage values with color
                def format_pct(val, show_sign=True):
                    if val is None:
                        return Text("N/A", justify="right", style=text_muted)
                    color = success_color if val > 0 else (error_color if val < 0 else "")
                    prefix = "+" if val > 0 and show_sign else ""
                    return Text(f"{prefix}{val:.1f}%", style=color, justify="right")

                # Helper to format numeric values
                def format_num(val, decimals=2):
                    if val is None:
                        return Text("N/A", justify="right", style=text_muted)
                    return Text(f"{val:,.{decimals}f}", justify="right")

                # Format Z-score with warning colors for extreme values
                def format_zscore(val):
                    if val is None:
                        return Text("N/A", justify="right", style=text_muted)
                    # Extreme values (|z| > 2) get warning/error color
                    if abs(val) > 2:
                        color = error_color
                    elif abs(val) > 1:
                        color = warning_color
                    else:
                        color = ""
                    prefix = "+" if val > 0 else ""
                    return Text(f"{prefix}{val:.2f}", style=color, justify="right")

                # Format % range with colors for extreme positions
                def format_pct_range(val):
                    if val is None:
                        return Text("N/A", justify="right", style=text_muted)
                    # Near extremes get warning colors
                    if val >= 90:
                        color = warning_color  # Near max
                    elif val <= 10:
                        color = warning_color  # Near min
                    else:
                        color = ""
                    return Text(f"{val:.0f}%", style=color, justify="right")

                # Format date
                date_text = Text(item.get("date", "N/A"), justify="center")

                # Format frequency
                freq_text = Text(item.get("frequency", "M"), justify="center")

                table.add_row(
                    name_text,
                    current_text,
                    format_pct(item.get("yoy_pct")),
                    format_num(item.get("roll_12")),
                    format_num(item.get("roll_24")),
                    format_zscore(item.get("z_10y")),
                    format_num(item.get("hist_min_10y")),
                    format_num(item.get("hist_max_10y")),
                    format_pct_range(item.get("pct_of_range")),
                    date_text,
                    freq_text,
                    Text(item.get("units_short") or item.get("units", ""), justify="left"),
                    key=series_id
                )

            # Set initial cursor position if table is empty cursor-wise
            if table.row_count > 0 and table.cursor_row is None:
                table.cursor_coordinate = (0, 0)
            # NOTE: Do NOT call table.focus() here - it steals focus from Tabs.

        except NoMatches:
            pass
