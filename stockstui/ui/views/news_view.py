import re
import webbrowser
from typing import Union

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, Markdown
from textual.app import ComposeResult, on

from stockstui.ui.suggesters import TickerSuggester

class NewsView(Vertical):
    """A view for displaying news articles for a selected ticker, with link navigation."""

    # Key bindings specific to the NewsView for navigating and opening links
    BINDINGS = [
        Binding("tab", "cycle_links", "Cycle Links", show=False),
        Binding("shift+tab", "cycle_links_backward", "Cycle Links Backward", show=False),
        Binding("enter", "open_link", "Open Link", show=False),
    ]

    def __init__(self, **kwargs):
        """Initializes the NewsView, setting up internal state for link management."""
        super().__init__(**kwargs)
        self._link_urls: list[str] = [] # Stores URLs extracted from news articles
        self._current_link_index: int = -1 # Index of the currently highlighted link
        self._original_markdown: Union[str, Text] = "" # Stores the original markdown content

    def compose(self) -> ComposeResult:
        """Creates the layout for the news view."""
        all_tickers_data = [s for lst in self.app.config.lists.values() for s in lst]
        suggester_data = [(s['ticker'], s.get('note') or s.get('alias', s['ticker'])) for s in all_tickers_data]
        unique_suggester_data = list({t[0]: t for t in suggester_data}.values())
        suggester = TickerSuggester(unique_suggester_data, case_sensitive=False)

        with Horizontal(classes="news-controls"):
            yield Input(
                placeholder="Enter ticker(s), comma-separated...",
                suggester=suggester,
                id="news-ticker-input",
                value=self.app.news_ticker or ""
            )
        yield Markdown(id="news-output-display")

    def on_mount(self) -> None:
        """Called when the NewsView is mounted. Sets up initial state and fetches news if a ticker is set."""
        markdown_widget = self.query_one(Markdown)
        markdown_widget.can_focus = True
        
        if self.app.news_ticker:
            if self.app._news_content_for_ticker == self.app.news_ticker and self.app._last_news_content:
                self.update_content(*self.app._last_news_content)
            else:
                markdown_widget.update("")
                markdown_widget.loading = True
                self.app.fetch_news(self.app.news_ticker)
            
    def _parse_tickers_from_input(self, value: str) -> str:
        """Cleans and standardizes a comma-separated string of tickers."""
        tickers = [t.strip().upper() for t in value.split(',') if t.strip()]
        return ",".join(tickers)

    def _reset_link_focus(self):
        """Resets the link navigation state, clearing any highlighted links."""
        self._current_link_index = -1
        self._link_urls = []
        self._original_markdown = ""
        
    @on(Input.Submitted, '#news-ticker-input')
    def on_news_ticker_submitted(self, event: Input.Submitted):
        """Handles submission of the ticker input, triggering news fetch."""
        self._reset_link_focus()

        self.app._last_news_content = None
        self.app._news_content_for_ticker = None

        if event.value:
            markdown_widget = self.query_one(Markdown)
            # Standardize the input string before using it.
            tickers_str = self._parse_tickers_from_input(event.value)
            self.app.news_ticker = tickers_str
            markdown_widget.update("")
            markdown_widget.loading = True
            self.app.fetch_news(tickers_str)

    def update_content(self, markdown: Union[str, Text], urls: list[str]) -> None:
        """Receives new news content and associated URLs, then updates the display."""
        markdown_widget = self.query_one(Markdown)
        markdown_widget.loading = False
        self._original_markdown = markdown
        self._link_urls = urls
        self._current_link_index = -1
        markdown_widget.update(markdown)

    def _highlight_current_link(self):
        """
        Re-renders the markdown content with the currently selected link highlighted.
        It prepends a '➤ ' indicator to the link text.
        """
        markdown_widget = self.query_one(Markdown)

        if not isinstance(self._original_markdown, str) or self._current_link_index == -1:
            markdown_widget.update(self._original_markdown)
            return

        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
        link_counter = 0

        def replacer(match):
            nonlocal link_counter
            original_text = match.group(1)
            url = match.group(2)
            clean_text = original_text.replace("➤ ", "")
            
            if link_counter == self._current_link_index:
                replacement = f"[{'➤ ' + clean_text}]({url})"
            else:
                replacement = f"[{clean_text}]({url})"
            
            link_counter += 1
            return replacement

        new_content = link_pattern.sub(replacer, self._original_markdown)
        markdown_widget.update(new_content)

        if self._link_urls and len(self._link_urls) > 1:
            scroll_percentage = (self._current_link_index / (len(self._link_urls) - 1)) * 100
            if markdown_widget.virtual_size.height > markdown_widget.container_size.height:
                max_scroll_y = markdown_widget.virtual_size.height - markdown_widget.container_size.height
                target_y = (scroll_percentage / 100) * max_scroll_y
                markdown_widget.scroll_to(y=target_y, duration=0.2)

    def action_cycle_links(self) -> None:
        """Cycles focus forward through the available links, highlighting the next one."""
        if not self._link_urls:
            return

        if self.query_one(Input).has_focus:
            self.query_one(Markdown).focus()

        self._current_link_index += 1
        if self._current_link_index >= len(self._link_urls):
            self._current_link_index = 0
        
        self._highlight_current_link()

    def action_cycle_links_backward(self) -> None:
        """Cycles focus backward through the available links, highlighting the previous one."""
        if not self._link_urls:
            return

        if self.query_one(Input).has_focus:
            self.query_one(Markdown).focus()

        self._current_link_index -= 1
        if self._current_link_index < 0:
            self._current_link_index = len(self._link_urls) - 1
        
        self._highlight_current_link()

    def action_open_link(self) -> None:
        """Opens the currently focused (highlighted) link in the default web browser."""
        if self._current_link_index == -1 or not self._link_urls:
            return

        try:
            url_to_open = self._link_urls[self._current_link_index]
            self.app.notify(f"Opening {url_to_open}...")
            webbrowser.open(url_to_open)
        except webbrowser.Error:
            self.app.notify("No web browser found. Please configure your system's default browser.", severity="error", timeout=8)
        except IndexError:
            self.app.notify("Internal error: Invalid link index.", severity="error")
        except Exception as e:
            self.app.notify(f"An unexpected error occurred: {e}", severity="error")