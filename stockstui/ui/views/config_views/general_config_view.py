from textual.containers import Vertical, Horizontal
from textual.widgets import (Button, Checkbox, Input, Label,
                             Select, Switch, ListView, ListItem)
from textual.app import ComposeResult, on
from textual.validation import Number
from textual.binding import Binding

from stockstui.common import NotEmpty

class GeneralConfigView(Vertical):
    """A view for configuring general application settings and tab visibility."""

    BINDINGS = [
        Binding("j, down", "focus_next", "Next", show=False),
        Binding("k, up", "focus_previous", "Previous", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Creates the layout for the general configuration view."""
        with Horizontal(id="top-config-container"):
            # Left side for general application settings
            with Vertical(id="general-settings-container"):
                yield Label("General Settings", classes="config-header")
                with Horizontal(classes="config-option-horizontal"):
                    yield Label("Default Tab:", classes="config-label"); yield Select([], id="default-tab-select", allow_blank=True)
                with Horizontal(classes="config-option-horizontal"):
                    yield Label("Theme:", classes="config-label"); yield Select([], id="theme-select", allow_blank=True)
                with Horizontal(classes="config-option-horizontal"):
                    yield Label("Market Status\nCalendar:", classes="config-label")
                    yield Select([
                        ("NYSE (US)", "NYSE"), ("TSX (Toronto)", "TSX"), ("BMF (Brazil)", "BMF"),
                        ("LSE (London)", "LSE"), ("EUREX (Europe)", "EUREX"), ("SIX (Swiss)", "SIX"), ("OSE (Oslo)", "OSE"),
                        ("JPX (Japan)", "JPX"), ("HKEX (Hong Kong)", "HKEX"), ("SSE (Shanghai)", "SSE"), ("ASX (Australia)", "ASX"), ("BSE (Bombay)", "BSE"), ("TASE (Tel Aviv)", "TASE"),
                        ("CME (Chicago)", "CME"), ("CME Equity Futures", "CME_Equity"), ("CME Bond Futures", "CME_Bond"), ("CME Agriculture Futures", "CME_Agriculture"), ("CME Crypto Futures", "CME_Crypto"),
                        ("CFE (CBOE Futures)", "CFE"), ("ICE Futures", "ICE"),
                        ("SIFMA US Bonds", "SIFMAUS"), ("SIFMA UK Bonds", "SIFMAUK"), ("SIFMA JP Bonds", "SIFMAJP"),
                    ], id="market-calendar-select")
                with Horizontal(classes="config-option-horizontal"):
                    yield Label("Auto Refresh:", classes="config-label"); yield Switch(id="auto-refresh-switch")
                with Horizontal(classes="config-option-horizontal"):
                    yield Label("Refresh\nInterval (s):", classes="config-label")
                    yield Input(id="refresh-interval-input", validators=[NotEmpty(), Number()]); yield Button("Update", id="update-refresh-interval")
            # Right side for managing which tabs are visible
            with Vertical(id="visibility-settings-container"):
                yield Label("Visible Tabs", classes="config-header")
                yield ListView(id="visible-tabs-list-view")

    def on_mount(self) -> None:
        """Called when the view is mounted."""
        self.repopulate_visible_tabs()

    def repopulate_visible_tabs(self):
        """Populates the visible tabs list view."""
        view = self.query_one("#visible-tabs-list-view", ListView)
        view.clear()
        
        hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
        
        # Combine static tabs with dynamic lists from config
        # Static tabs: All, History, News
        # Dynamic lists: Stocks, Currencies, etc. (keys in self.app.config.lists)
        
        # Start with "All"
        all_tabs = ["all"]
        
        # Add dynamic lists
        if hasattr(self.app.config, 'lists'):
            all_tabs.extend(list(self.app.config.lists.keys()))
            
        # Add other static tabs
        all_tabs.extend(["history", "news", "options", "debug"])
        
        # Remove duplicates and preserve order (though dict keys are ordered in recent Python)
        seen = set()
        unique_tabs = []
        for t in all_tabs:
            if t not in seen:
                unique_tabs.append(t)
                seen.add(t)
        
        for tab in unique_tabs:
            visible = tab not in hidden_tabs
            item_content = Horizontal(
                Label(tab.replace("_", " ").capitalize(), classes="column-label"),
                Switch(value=visible, classes="tab-switch"),
                classes="column-item-layout"
            )
            item = ListItem(item_content, name=tab)
            view.append(item)

    @on(Button.Pressed, "#update-refresh-interval")
    def on_update_refresh_button_pressed(self):
        """Handles the 'Update' button press for the refresh interval setting."""
        input_widget = self.query_one("#refresh-interval-input", Input)
        validation_result = input_widget.validate(input_widget.value)

        if validation_result.is_valid:
            self.app.config.settings['refresh_interval'] = float(input_widget.value)
            self.app.config.save_settings()
            self.app._manage_price_refresh_timer()
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
        self.app._manage_price_refresh_timer()

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
            if self.app.market_status_timer: self.app.market_status_timer.stop()
            self.app.fetch_market_status(str(event.value))
        self.app.config.save_settings()

    @on(Switch.Changed)
    async def on_tab_visibility_toggled(self, event: Switch.Changed):
        """Handles changes to tab visibility switches."""
        if "tab-switch" not in event.switch.classes:
            return

        key = None
        for ancestor in event.switch.ancestors:
            if isinstance(ancestor, ListItem):
                key = ancestor.name
                break
        
        if not key: return

        hidden_tabs = self.app.config.get_setting("hidden_tabs", [])
        if event.value:
            if key in hidden_tabs: hidden_tabs.remove(key)
        else:
            if key not in hidden_tabs: hidden_tabs.append(key)
            
        self.app.config.settings['hidden_tabs'] = hidden_tabs
        self.app.config.save_settings()
        await self.app._rebuild_app('configs')

    @on(ListView.Selected, "#visible-tabs-list-view")
    def on_tab_selected(self, event: ListView.Selected):
        """Toggle switch on selection."""
        switch = event.item.query_one(Switch)
        switch.value = not switch.value