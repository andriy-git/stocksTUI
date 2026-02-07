"""
Ticker Info Modal

Displays ticker metadata - ETF info (TER, risk level) or stock info (sector, P/E).
"""

import re

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class TickerInfoModal(ModalScreen[None]):
    """A modal dialog displaying ticker metadata (ETF or stock)."""

    DEFAULT_CSS = """
    TickerInfoModal {
        align: center middle;
    }
    
    TickerInfoModal > Vertical {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    
    TickerInfoModal .modal-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }
    
    TickerInfoModal .info-row {
        height: 1;
        margin-bottom: 0;
    }
    
    TickerInfoModal .info-label {
        width: 20;
        color: $text-muted;
    }
    
    TickerInfoModal .info-value {
        width: 1fr;
        text-style: bold;
    }
    
    TickerInfoModal .info-section {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary;
    }
    
    TickerInfoModal .error-message {
        color: $error;
        text-align: center;
        padding: 1;
    }
    
    TickerInfoModal .loading-message {
        color: $text-muted;
        text-align: center;
        padding: 1;
    }
    
    TickerInfoModal #close-button {
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        ticker: str,
        metadata: dict | None = None,
        error: str | None = None,
    ) -> None:
        super().__init__()
        self.ticker = ticker
        self.metadata = metadata
        self.error = error

    def compose(self) -> ComposeResult:
        """Creates the layout for the info modal."""
        with Vertical(id="dialog"):
            yield Label(f"Info: {self.ticker}", classes="modal-title")

            if self.error:
                yield Static(f"⚠ {self.error}", classes="error-message")
            elif self.metadata:
                yield from self._render_metadata()
            else:
                yield Static("Loading...", classes="loading-message")

            yield Button("Close", variant="primary", id="close-button")

    def _render_metadata(self) -> ComposeResult:
        """Render metadata fields dynamically."""
        m = self.metadata

        # Name
        if m.get("name"):
            with Horizontal(classes="info-row"):
                yield Static("Name:", classes="info-label")
                yield Static(m["name"], classes="info-value")

        # Type-specific fields
        quote_type = m.get("quote_type", "").upper()

        if quote_type == "ETF" or m.get("ter") is not None or m.get("risk_level"):
            # ETF-specific
            yield from self._render_etf_fields(m)
        else:
            # Stock-specific
            yield from self._render_stock_fields(m)

        # Common fields
        if m.get("currency"):
            with Horizontal(classes="info-row"):
                yield Static("Currency:", classes="info-label")
                yield Static(m["currency"], classes="info-value")

    def _render_etf_fields(self, m: dict) -> ComposeResult:
        """Render ETF-specific fields."""
        if m.get("isin"):
            with Horizontal(classes="info-row"):
                yield Static("ISIN:", classes="info-label")
                yield Static(m["isin"], classes="info-value")

        if m.get("fund_family"):
            with Horizontal(classes="info-row"):
                yield Static("Provider:", classes="info-label")
                yield Static(m["fund_family"], classes="info-value")

        yield Static("", classes="info-section")

        # TER
        ter_value = f"{m['ter']}%" if m.get("ter") is not None else "N/A"
        with Horizontal(classes="info-row"):
            yield Static("TER:", classes="info-label")
            yield Static(ter_value, classes="info-value")

        # Risk level (EU only)
        if m.get("risk_level") is not None:
            risk = m["risk_level"]
            risk_labels = {
                1: "Lowest",
                2: "Low",
                3: "Medium-low",
                4: "Medium",
                5: "Medium-high",
                6: "High",
                7: "Highest",
            }
            risk_text = f"{risk}/7 ({risk_labels.get(risk, 'Unknown')} risk)"
            with Horizontal(classes="info-row"):
                yield Static("Risk Level:", classes="info-label")
                yield Static(risk_text, classes="info-value")

        if m.get("distribution"):
            with Horizontal(classes="info-row"):
                yield Static("Distribution:", classes="info-label")
                yield Static(m["distribution"], classes="info-value")

        if m.get("replication"):
            with Horizontal(classes="info-row"):
                yield Static("Replication:", classes="info-label")
                yield Static(m["replication"], classes="info-value")

    def _render_stock_fields(self, m: dict) -> ComposeResult:
        """Render stock-specific fields."""
        if m.get("sector"):
            with Horizontal(classes="info-row"):
                yield Static("Sector:", classes="info-label")
                yield Static(m["sector"], classes="info-value")

        if m.get("industry"):
            with Horizontal(classes="info-row"):
                yield Static("Industry:", classes="info-label")
                yield Static(m["industry"], classes="info-value")

        if m.get("country"):
            with Horizontal(classes="info-row"):
                yield Static("Country:", classes="info-label")
                yield Static(m["country"], classes="info-value")

        yield Static("", classes="info-section")

        if m.get("market_cap"):
            with Horizontal(classes="info-row"):
                yield Static("Market Cap:", classes="info-label")
                yield Static(m["market_cap"], classes="info-value")

        if m.get("pe_ratio"):
            with Horizontal(classes="info-row"):
                yield Static("P/E Ratio:", classes="info-label")
                yield Static(m["pe_ratio"], classes="info-value")

        if m.get("dividend_yield"):
            with Horizontal(classes="info-row"):
                yield Static("Dividend:", classes="info-label")
                yield Static(m["dividend_yield"], classes="info-value")

    def on_mount(self) -> None:
        """Focus the close button when mounted."""
        self.query_one("#close-button", Button).focus()

    @on(Button.Pressed, "#close-button")
    def on_close(self, event: Button.Pressed) -> None:
        """Close the modal."""
        self.dismiss(None)

    def key_escape(self) -> None:
        """Allow escape to close the modal."""
        self.dismiss(None)

    def key_enter(self) -> None:
        """Allow enter to close the modal."""
        self.dismiss(None)


# Alias for backward compatibility
ETFInfoModal = TickerInfoModal


def extract_isin_from_note(note: str | None) -> str | None:
    """
    Extract ISIN from a note field.

    Looks for patterns like:
    - (IE00BK5BQT80)
    - IE00BK5BQT80
    - (DE000A0S9GB0)
    """
    if not note:
        return None

    # ISIN format: 2 letters + 10 alphanumeric chars
    match = re.search(r"\b([A-Z]{2}[A-Z0-9]{10})\b", note)
    if match:
        return match.group(1)
    return None
