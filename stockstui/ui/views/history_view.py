from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Input, RadioButton, Switch, Static, DataTable
from textual.app import ComposeResult, on
from textual.dom import NoMatches
from rich.text import Text

from stockstui.ui.suggesters import TickerSuggester
from stockstui.ui.widgets.history_chart import HistoryChart
from stockstui.ui.widgets.vim_radio_set import VimRadioSet
from stockstui.presentation import formatter


class HistoryView(Vertical):
    """A view for displaying historical stock data, allowing selection of tickers and time ranges."""

    def compose(self) -> ComposeResult:
        """Creates the layout for the historical data view."""
        # Prepare data for the ticker suggester (all unique tickers from user's lists)
        all_tickers_data = [s for lst in self.app.config.lists.values() for s in lst]
        suggester_data = [
            (s["ticker"], s.get("note") or s.get("alias", s["ticker"]))
            for s in all_tickers_data
        ]
        unique_suggester_data = list(
            {t[0]: t for t in suggester_data}.values()
        )  # Deduplicate by ticker
        suggester = TickerSuggester(unique_suggester_data, case_sensitive=False)

        # Horizontal container for ticker input
        with Horizontal(classes="history_controls"):
            yield Input(
                placeholder="Enter a ticker...",
                suggester=suggester,
                id="history-ticker-input",
                value=self.app.history_ticker
                or "",  # Pre-fill with last selected ticker
            )
        # Horizontal container for range selection and view toggle
        with Horizontal(classes="history_controls"):
            yield VimRadioSet(
                RadioButton("1D"),
                RadioButton("5D"),
                RadioButton("1M", value=True),
                RadioButton("6M"),
                RadioButton("YTD"),
                RadioButton("1Y"),
                RadioButton("5Y"),
                RadioButton("All"),
                id="history-range-select",  # Radio buttons for selecting historical period
            )
            yield Switch(
                id="history-view-toggle"
            )  # Toggle between table and chart view
        # Container to display the historical data (table or chart)
        yield Container(id="history-display-container")

    def on_mount(self) -> None:
        """
        Called when the HistoryView is mounted.
        Applies any CLI overrides and triggers initial data rendering.
        """
        # --- Apply CLI Overrides ---
        if self.app.cli_overrides:
            # If --chart was passed, enable the chart view toggle
            if self.app.cli_overrides.get("chart"):
                self.query_one("#history-view-toggle", Switch).value = True

            # If --period was passed, select the corresponding radio button
            if period_arg := self.app.cli_overrides.get("period"):
                period_map = {
                    "1d": "1D",
                    "5d": "5D",
                    "1mo": "1M",
                    "6mo": "6M",
                    "ytd": "YTD",
                    "1y": "1Y",
                    "5y": "5Y",
                    "max": "All",
                }
                target_label = period_map.get(period_arg)
                if target_label:
                    radio_set = self.query_one("#history-range-select", VimRadioSet)
                    for button in radio_set.query(RadioButton):
                        button.value = str(button.label) == target_label

        # Trigger data fetch if a ticker is already set (either from CLI or app state)
        if self.app.history_ticker:
            self.call_after_refresh(self._request_historical_data)
        else:
            self.call_after_refresh(self._render_historical_data)

    async def _render_historical_data(self):
        """
        Renders the appropriate view (table or chart) in the history tab.
        It uses the `_last_historical_data` from the app state.
        """
        try:
            display_container = self.query_one("#history-display-container")
            await display_container.remove_children()  # Clear previous content

            last_data = self.app._last_historical_data
            if last_data is None:
                await display_container.mount(
                    Static(
                        "Enter a ticker symbol to view its historical data.",
                        id="info-message",
                    )
                )
                return

            if last_data.empty:
                # Check for a specific error message from the data provider
                error_type = last_data.attrs.get("error")
                ticker = last_data.attrs.get("symbol", "the selected ticker")

                error_text = Text()
                if error_type == "Invalid Ticker":
                    error_text = Text.assemble(
                        ("Error: ", "bold red"), f"Invalid ticker symbol '{ticker}'."
                    )
                elif error_type == "Network Error":
                    error_text = Text.assemble(
                        ("Network Error: ", "bold red"),
                        f"Could not retrieve data for '{ticker}'.",
                    )
                elif error_type == "Data Error":
                    error_text = Text.assemble(
                        ("Data Error: ", "bold red"),
                        f"Could not process data for '{ticker}'.",
                    )
                else:  # Generic error for other cases (e.g., no data in range)
                    error_text = Text(
                        f"No historical data found for '{ticker}' in the selected range."
                    )

                await display_container.mount(Static(error_text))
                return

            view_toggle = self.query_one("#history-view-toggle", Switch)
            if view_toggle.value:
                # Display as a chart
                chart_widget = HistoryChart(last_data, period=self.app._history_period)
                await display_container.mount(chart_widget)
            else:
                # Display as a table
                table = formatter.format_historical_data_as_table(last_data)
                await display_container.mount(table)
                self.app._apply_history_table_sort()
        except NoMatches:
            pass

    def _request_historical_data(self):
        """
        Initiates the fetching of historical data based on the selected ticker
        and time range. Dispatches a worker to perform the actual data fetch.
        """
        if not self.app.history_ticker:
            return
        try:
            radio_set = self.query_one("#history-range-select", VimRadioSet)
            if radio_set.pressed_button:
                period_map = {
                    "1D": "1d",
                    "5D": "5d",
                    "1M": "1mo",
                    "6M": "6mo",
                    "YTD": "ytd",
                    "1Y": "1y",
                    "5Y": "5y",
                    "All": "max",
                }
                button_label = str(radio_set.pressed_button.label)
                period = period_map.get(button_label)
                if period:
                    self.app._history_period = period
                    # Use a 5-minute interval for the 1D period, otherwise default to daily.
                    interval = "5m" if button_label == "1D" else "1d"

                    display_container = self.query_one("#history-display-container")
                    display_container.loading = True  # Show loading indicator
                    self.app.fetch_historical_data(
                        self.app.history_ticker, period, interval
                    )
        except NoMatches:
            pass

    def _parse_ticker_from_input(self, value: str) -> str:
        """Extracts the ticker symbol from a suggestion string ('TICKER - Desc') or raw input."""
        if " - " in value:
            return value.strip().split(" - ")[0].upper()
        return value.strip().upper()

    @on(Input.Submitted, "#history-ticker-input")
    def on_history_ticker_submitted(self, event: Input.Submitted):
        """Handles submission of the ticker input, triggering data fetch."""
        if event.value:
            self.app.history_ticker = self._parse_ticker_from_input(event.value)
            self._request_historical_data()

    @on(VimRadioSet.Changed, "#history-range-select")
    def on_history_range_changed(self, event: VimRadioSet.Changed):
        """Handles changes in the historical data range selection, triggering data fetch."""
        self._request_historical_data()

    @on(Switch.Changed, "#history-view-toggle")
    async def on_history_view_toggled(self, event: Switch.Changed):
        """Handles toggling between table and chart view for historical data."""
        await self._render_historical_data()

    @on(DataTable.HeaderSelected, "#history-table")
    def on_history_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle header clicks to sort the history table."""
        self.app._set_and_apply_history_sort(str(event.column_key.value), "click")
