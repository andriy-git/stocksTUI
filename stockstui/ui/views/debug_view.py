from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Button, Static
from textual.app import ComposeResult, on

from stockstui.ui.modals import CompareInfoModal
# Import the new NavigableDataTable
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable

class DebugView(Vertical):
    """A view for running various debug tests related to data fetching and caching."""

    def compose(self) -> ComposeResult:
        """Creates the layout for the debug view."""
        # Buttons for initiating different debug tests
        with Horizontal(classes="debug-buttons"):
            yield Button("Compare Ticker Info", id="debug-compare-info")
            yield Button("Test Tickers (Latency)", id="debug-test-tickers")
            yield Button("Test Lists (Network)", id="debug-test-lists")
            yield Button("Test Cache (Local Speed)", id="debug-test-cache")
            
        # Container to display the results of the debug tests
        with Container(id="debug-output-container"):
            yield Static("[dim]Run a test to see results.[/dim]", id="info-message")
    
    @on(Button.Pressed, ".debug-buttons Button")
    async def on_debug_button_pressed(self, event: Button.Pressed):
        """
        Handles button presses for the debug tests.
        Clears previous results, disables buttons, and initiates the selected test.
        """
        button_id = event.button.id
        
        for button in self.query(".debug-buttons Button"):
            button.disabled = True
            
        container = self.query_one("#debug-output-container")
        await container.remove_children()
        
        if button_id == "debug-compare-info":
            # Special handling for Compare Ticker Info, which requires a modal input
            async def on_modal_close(ticker: str | None):
                if ticker:
                    # User submitted a ticker. The test will run.
                    await container.mount(NavigableDataTable(id="debug-table"))
                    dt = self.query_one("#debug-table", NavigableDataTable)
                    
                    dt.clear()
                    dt.add_columns("Info Key", "Fast", "Slow")
                    dt.loading = True
                    
                    self.app.run_info_comparison_test(ticker)
                else: 
                    # User cancelled the modal, so re-enable buttons and restore initial state.
                    await container.mount(Static("[dim]Run a test to see results.[/dim]", id="info-message"))
                    for button in self.query(".debug-buttons Button"):
                        button.disabled = False
            
            self.app.push_screen(CompareInfoModal(), on_modal_close)
            
        else:
            # For other tests, directly mount the DataTable and start the test
            await container.mount(NavigableDataTable(id="debug-table"))
            dt = self.query_one("#debug-table", NavigableDataTable)
            
            dt.loading = True
            
            if button_id == "debug-test-tickers":
                dt.add_columns("Symbol", "Valid?", "Description", "Latency")
                dt.add_row("[yellow]Running individual ticker performance test...[/]")
                all_symbols = list(set(s['ticker'] for cat_symbols in self.app.config.lists.values() for s in cat_symbols))
                self.app.run_ticker_debug_test(all_symbols)
            elif button_id == "debug-test-lists":
                dt.add_columns("List Name", "Tickers", "Latency")
                dt.add_row("[yellow]Running list batch network test...[/]")
                lists_to_test = {name: [s['ticker'] for s in tickers] for name, tickers in self.app.config.lists.items()}
                # FIX: Call the correct test function for network latency.
                self.app.run_list_debug_test(lists_to_test)
            elif button_id == "debug-test-cache":
                dt.add_columns("List Name", "Tickers", "Latency (From Cache)")
                dt.add_row("[yellow]Running cache speed test...[/]")
                lists_to_test = {name: [s['ticker'] for s in tickers] for name, tickers in self.app.config.lists.items()}
                self.app.run_cache_test(lists_to_test)