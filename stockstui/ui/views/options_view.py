from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Input, Select, Static, DataTable, Label, Button, ContentSwitcher
from textual.app import ComposeResult, on
from textual.dom import NoMatches
from rich.text import Text
from textual.binding import Binding

from stockstui.ui.suggesters import TickerSuggester
from stockstui.ui.position_modal import PositionModal
from stockstui.ui.widgets.oi_chart import OIChart


class OptionsView(Vertical):
    """A view for displaying stock options chains, allowing selection of tickers and expiration dates."""

    BINDINGS = [
        Binding("p", "manage_position", "Position", show=True),
        Binding("c", "toggle_chart", "Toggle Chart", show=True),
        Binding("[", "prev_expiration", "Prev Exp", show=True),
        Binding("]", "next_expiration", "Next Exp", show=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expirations = []

    def compose(self) -> ComposeResult:
        """Creates the layout for the options view."""
        # Prepare data for the ticker suggester (all unique tickers from user's lists)
        all_tickers_data = [s for lst in self.app.config.lists.values() for s in lst]
        suggester_data = [(s['ticker'], s.get('note') or s.get('alias', s['ticker'])) for s in all_tickers_data]
        unique_suggester_data = list({t[0]: t for t in suggester_data}.values())  # Deduplicate by ticker
        suggester = TickerSuggester(unique_suggester_data, case_sensitive=False)
        
        # Horizontal container for ticker input and expiration selector
        with Horizontal(classes="options_controls"):
            yield Input(
                placeholder="Enter a ticker...",
                suggester=suggester,
                id="options-ticker-input",
                value=self.app.options_ticker or ""  # Pre-fill with last selected ticker
            )
            yield Select(
                options=[("Select expiration", "")],
                id="options-expiration-select",
                allow_blank=False,
                prompt="Expiration"
            )
            yield Button("Chart", id="options-view-toggle", variant="primary")
        
        # Container to display the options chain
        with Container(id="options-display-container"):
            yield Static("Enter a ticker symbol to view its options chain.", id="options-info-message")

    def on_mount(self) -> None:
        """
        Called when the OptionsView is mounted.
        Triggers initial data rendering if ticker is already set.
        """
        # Trigger expiration fetch if a ticker is already set
        if self.app.options_ticker:
            self.call_after_refresh(self._request_expirations)
        
        # Disable expiration selector until expirations are loaded
        try:
            self.query_one("#options-expiration-select", Select).disabled = True
        except NoMatches:
            pass

    async def _render_options_data(self):
        """
        Renders the options chain data (calls and puts tables) in the display container.
        Uses the `_last_options_data` from the app state.
        """
        try:
            display_container = self.query_one("#options-display-container")
            await display_container.remove_children()  # Clear previous content

            last_data = self.app._last_options_data
            if last_data is None:
                await display_container.mount(Static("Enter a ticker symbol and select an expiration date.", id="options-info-message"))
                return
            
            # Check for errors
            if last_data.get('error'):
                error_text = Text.assemble(
                    ("Error: ", "bold red"),
                    last_data.get('error', 'Unknown error occurred.')
                )
                await display_container.mount(Static(error_text))
                return
            
            calls_df = last_data.get('calls')
            puts_df = last_data.get('puts')
            underlying_data = last_data.get('underlying', {})
            
            if calls_df is None or puts_df is None or (calls_df.empty and puts_df.empty):
                await display_container.mount(Static(f"No options data found for {self.app.options_ticker}.", id="options-info-message"))
                return

            # Get underlying price for ITM/OTM calculations
            underlying_price = underlying_data.get('regularMarketPrice', 0)
            
            # Calculate days to expiration
            from datetime import datetime
            try:
                expiration_str = last_data.get('expiration', '')
                exp_date = datetime.strptime(expiration_str, '%Y-%m-%d')
                days_to_exp = (exp_date - datetime.now()).days
            except:
                days_to_exp = None
            
            # Create info header
            info_text = f"Underlying: ${underlying_price:.2f}"
            if days_to_exp is not None:
                info_text += f"  |  Days to Expiration: {days_to_exp}"
            info_header = Static(info_text, classes="options-info-header")
            await display_container.mount(info_header)
            
            # Get theme colors
            success_color = self.app.theme_variables.get("success", "green")
            error_color = self.app.theme_variables.get("error", "red")
            muted_color = self.app.theme_variables.get("text-muted", "dim")
            accent_color = self.app.theme_variables.get("accent", "blue")
            
            # Create ContentSwitcher for Table/Chart views
            switcher = ContentSwitcher(initial="options-tables-view", id="options-content-switcher")
            
            # --- TABLE VIEW ---
            # Create horizontal container for tables
            tables_container = Horizontal(classes="options-tables-container", id="options-tables-view")
            
            # Helper to create table
            def create_table(df, table_id, label_text, is_call):
                section = Vertical(classes="options-table-section")
                label = Label(label_text, classes="options-table-header")
                table = DataTable(id=table_id, zebra_stripes=True)
                table.cursor_type = "row"
                
                if df.empty:
                    return section, label, table

                table.add_columns(
                    "Strike", "Last", "Bid", "Ask", "Chg %", 
                    "Vol", "OI", "IV",
                    "Δ", "Γ", "Θ", "ν",
                    "Pos", "P/L" # New columns
                )
                
                for _, row in df.iterrows():
                    strike = row.get('strike', 0)
                    contract_symbol = row.get('contractSymbol')
                    
                    # Position check
                    position = self.app.option_positions.get(contract_symbol)
                    has_position = position is not None
                    
                    is_itm = False
                    if is_call:
                        is_itm = strike < underlying_price if underlying_price else False
                    else:
                        is_itm = strike > underlying_price if underlying_price else False
                    
                    # Format strike
                    strike_text = Text(f"${strike:.2f}")
                    if is_itm:
                        strike_text.stylize(f"bold {success_color}")
                    
                    # Position styling
                    row_style = None
                    if has_position:
                        strike_text.stylize(f"bold {accent_color} reverse")
                    
                    last_price = row.get('lastPrice', 0)
                    last_text = f"${last_price:.2f}"
                    bid = f"${row.get('bid', 0):.2f}"
                    ask = f"${row.get('ask', 0):.2f}"
                    
                    # % Change
                    pct_change_val = row.get('percentChange', 0)
                    pct_change_text = Text(f"{pct_change_val:.1f}%")
                    if pct_change_val > 0:
                        pct_change_text.stylize(success_color)
                    elif pct_change_val < 0:
                        pct_change_text.stylize(error_color)
                    else:
                        pct_change_text.stylize(muted_color)
            
                    # Handle NaN values for volume and openInterest
                    import math
                    volume_val = row.get('volume', 0)
                    oi_val = row.get('openInterest', 0)
                    
                    volume = f"{int(volume_val):,}" if not (isinstance(volume_val, float) and math.isnan(volume_val)) else "—"
                    open_interest = f"{int(oi_val):,}" if not (isinstance(oi_val, float) and math.isnan(oi_val)) else "—"
                    iv = f"{row.get('impliedVolatility', 0):.2%}"
                    
                    # Greeks
                    delta = f"{row.get('delta', 0):.2f}"
                    gamma = f"{row.get('gamma', 0):.3f}"
                    theta = f"{row.get('theta', 0):.3f}"
                    vega = f"{row.get('vega', 0):.3f}"
                    
                    # Position Data
                    pos_text = ""
                    pl_text = Text("")
                    if has_position:
                        qty = position.get('quantity', 0)
                        avg_cost = position.get('avg_cost', 0)
                        pos_text = f"{qty:g}"
                        
                        # Calculate P/L
                        # P/L = (Current Price - Avg Cost) * Qty * 100
                        current_val = last_price
                        pl_val = (current_val - avg_cost) * qty * 100
                        pl_text = Text(f"${pl_val:,.0f}")
                        if pl_val > 0:
                            pl_text.stylize(success_color)
                        elif pl_val < 0:
                            pl_text.stylize(error_color)
                            
                    table.add_row(
                        strike_text, last_text, bid, ask, pct_change_text, 
                        volume, open_interest, iv,
                        delta, gamma, theta, vega,
                        pos_text, pl_text,
                        key=contract_symbol # Store symbol as row key
                    )
                
                return section, label, table

            # --- TABLE VIEW ---
            tables_container = Horizontal(id="options-tables-view")
            
            # Create calls and puts tables
            calls_section, calls_label, calls_table = create_table(calls_df, "options-calls-table", "Calls", True)
            puts_section, puts_label, puts_table = create_table(puts_df, "options-puts-table", "Puts", False)
            
            # --- CHART VIEW ---
            chart_container = Container(id="options-chart-view")
            chart = OIChart(calls_df, puts_df, underlying_price, ticker=self.app.options_ticker)
            
            # Mount switcher to display_container FIRST (top of hierarchy)
            await display_container.mount(switcher)
            
            # Now mount children to switcher (tables_container and chart_container)
            await switcher.mount(tables_container)
            await switcher.mount(chart_container)
            
            # Now mount sections to tables_container
            await tables_container.mount(calls_section)
            await tables_container.mount(puts_section)
            
            # Now mount widgets to sections
            await calls_section.mount(calls_label, calls_table)
            await puts_section.mount(puts_label, puts_table)
            
            # Mount chart to chart_container
            await chart_container.mount(chart)

        except NoMatches:
            pass

    def action_toggle_chart(self):
        """Toggles between the table view and the chart view."""
        try:
            switcher = self.query_one("#options-content-switcher", ContentSwitcher)
            if switcher.current == "options-tables-view":
                switcher.current = "options-chart-view"
            else:
                switcher.current = "options-tables-view"
        except NoMatches:
            pass

    def update_expirations(self, expirations: list[str]):
        """Updates the expiration selector with new dates."""
        self.expirations = expirations
        try:
            select = self.query_one("#options-expiration-select", Select)
            if expirations:
                options = [(exp, exp) for exp in expirations]
                select.set_options(options)
                select.disabled = False
                if options:
                    select.value = options[0][1]
            else:
                select.set_options([("No options available", "")])
                select.disabled = True
        except NoMatches:
            pass

    def action_prev_expiration(self):
        """Selects the previous expiration date."""
        try:
            select = self.query_one("#options-expiration-select", Select)
            if not self.expirations or select.disabled:
                return
            
            current_value = select.value
            
            if not current_value or current_value not in self.expirations:
                return
                
            idx = self.expirations.index(current_value)
            if idx > 0:
                select.value = self.expirations[idx - 1]
        except NoMatches:
            pass

    def action_next_expiration(self):
        """Selects the next expiration date."""
        try:
            select = self.query_one("#options-expiration-select", Select)
            if not self.expirations or select.disabled:
                return
            
            current_value = select.value
            
            if not current_value or current_value not in self.expirations:
                return
                
            idx = self.expirations.index(current_value)
            if idx < len(self.expirations) - 1:
                select.value = self.expirations[idx + 1]
        except NoMatches:
            pass

    @on(Button.Pressed, "#options-view-toggle")
    def on_toggle_chart_pressed(self):
        self.action_toggle_chart()

    def action_manage_position(self):
        """Opens modal to manage position for the selected option."""
        # Determine which table has focus
        focused = self.app.focused
        if not focused or not isinstance(focused, DataTable):
            return
            
        if focused.id not in ["options-calls-table", "options-puts-table"]:
            return
            
        # Get selected row
        row_key = focused.coordinate_to_cell_key(focused.cursor_coordinate).row_key
        if not row_key:
            return
            
        contract_symbol = row_key.value
        if not contract_symbol:
            return

        # Get current position if exists
        current_pos = self.app.option_positions.get(contract_symbol)
        
        def handle_position_result(result: tuple[float, float] | None):
            if result is None:
                return
            
            qty, cost = result
            if qty == 0:
                self.app.remove_option_position(contract_symbol)
            else:
                self.app.add_option_position(contract_symbol, self.app.options_ticker, qty, cost)
            
            # Refresh view to show new position
            self.call_after_refresh(self._render_options_data)

        self.app.push_screen(PositionModal(contract_symbol, current_pos), handle_position_result)

    def _request_expirations(self):
        """Requests available expiration dates for the current ticker."""
        if not self.app.options_ticker:
            return
        
        # Disable expiration selector while loading
        try:
            self.query_one("#options-expiration-select", Select).disabled = True
        except NoMatches:
            pass
        
        self.app.fetch_options_expirations(self.app.options_ticker)

    def _request_options_chain(self):
        """Requests the options chain for the current ticker and selected expiration."""
        if not self.app.options_ticker:
            return
        
        try:
            expiration_select = self.query_one("#options-expiration-select", Select)
            if expiration_select.value and expiration_select.value != "":
                display_container = self.query_one("#options-display-container")
                display_container.loading = True
                self.app.fetch_options_chain(self.app.options_ticker, expiration_select.value)
        except NoMatches:
            pass

    def _parse_ticker_from_input(self, value: str) -> str:
        """Extracts the ticker symbol from a suggestion string ('TICKER - Desc') or raw input."""
        if ' - ' in value:
            return value.strip().split(' - ')[0].upper()
        return value.strip().upper()

    @on(Input.Submitted, '#options-ticker-input')
    def on_options_ticker_submitted(self, event: Input.Submitted):
        """Handles submission of the ticker input, triggering expiration fetch."""
        if event.value:
            self.app.options_ticker = self._parse_ticker_from_input(event.value)
            self._request_expirations()

    @on(Select.Changed, '#options-expiration-select')
    def on_expiration_changed(self, event: Select.Changed):
        """Handles changes in the expiration selector, triggering options chain fetch."""
        if event.value and event.value != "":
            self._request_options_chain()
