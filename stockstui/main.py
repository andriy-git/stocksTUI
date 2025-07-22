from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import logging
import time
from typing import Union
import sys
import os
import shutil
import subprocess
import argparse

import yfinance as yf
from rich.console import Console
from rich.table import Table
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.actions import SkipAction
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.theme import Theme
from textual.widgets import (Button, Checkbox, DataTable, Footer,
                             Input, Label, ListView, ListItem,
                             Select, Static, Tab, Tabs, Markdown, Switch, RadioButton, ContentSwitcher)
# FIX: Directly import the CellDoesNotExist exception and Coordinate class.
from textual.widgets.data_table import CellDoesNotExist
from textual.coordinate import Coordinate
from textual.widget import Widget
# FIX: Import get_current_worker from its correct module, textual.worker.
from textual import on, work
from textual.worker import get_current_worker
from rich.text import Text
from rich.style import Style
from textual.color import Color
from platformdirs import PlatformDirs

from stockstui.config_manager import ConfigManager
from stockstui.common import (PriceDataUpdated, NewsDataUpdated,
                              TickerDebugDataUpdated, ListDebugDataUpdated, CacheTestDataUpdated,
                              MarketStatusUpdated, HistoricalDataUpdated, TickerInfoComparisonUpdated,
                              PortfolioChanged, PortfolioDataUpdated)
from stockstui.data_providers.portfolio import PortfolioManager
from stockstui.ui.widgets.search_box import SearchBox
from stockstui.ui.widgets.tag_filter import TagFilterWidget, TagFilterChanged
# Import the new container instead of the old view
from stockstui.ui.views.config_view import ConfigContainer
from stockstui.ui.views.config_views.general_config_view import GeneralConfigView
from stockstui.ui.views.config_views.lists_config_view import ListsConfigView
from stockstui.ui.views.history_view import HistoryView
from stockstui.ui.views.news_view import NewsView
from stockstui.ui.views.debug_view import DebugView
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable
from stockstui.data_providers import market_provider
from stockstui.presentation import formatter
from stockstui.utils import extract_cell_text
from stockstui.database.db_manager import DbManager
from stockstui.parser import create_arg_parser
from stockstui.log_handler import TextualHandler


# A base template for all themes. It defines the required keys and uses
# placeholder variables (e.g., '$blue') that will be substituted with
# concrete colors from a specific theme's palette.
BASE_THEME_STRUCTURE = {
    "dark": False,
    "primary": "$blue",
    "secondary": "$cyan",
    "accent": "$orange",
    "success": "$green",
    "warning": "$yellow",
    "error": "$red",
    "background": "$bg3",
    "surface": "$bg2",
    "panel": "$bg1",
    "foreground": "$fg0",
    "variables": {
        "price": "$cyan",
        "latency-high": "$red",
        "latency-medium": "$yellow",
        "latency-low": "$blue",
        "text-muted": "$fg1",
        "status-open": "$green",
        "status-pre": "$yellow",
        "status-post": "$yellow",
        "status-closed": "$red",
        "button-foreground": "$fg3",
        "scrollbar": "$bg0",
        "scrollbar-hover": "$fg2",
    }
}

def substitute_colors(template: dict, palette: dict) -> dict:
    """
    Recursively substitutes color variables (e.g., '$blue') in a theme
    structure with concrete color values from a palette.
    """
    resolved = {}
    for key, value in template.items():
        if isinstance(value, dict):
            # Recurse for nested dictionaries (like 'variables').
            resolved[key] = substitute_colors(value, palette)
        elif isinstance(value, str) and value.startswith('$'):
            # If the value is a variable, look it up in the palette.
            color_name = value[1:]
            resolved[key] = palette.get(color_name, f"UNDEFINED_{color_name.upper()}")
        else:
            # Otherwise, use the value as is.
            resolved[key] = value
    return resolved

class StocksTUI(App):
    """
    The main application class for the Stocks Terminal User Interface.
    This class orchestrates the entire application, including UI composition,
    state management, data fetching, and event handling.
    """
    # The CSS file is now inside the package, so we need to tell Textual to load it from there
    CSS_PATH = "main.css"
    ENABLE_COMMAND_PALETTE = False
    
    # Define all key bindings for the application.
    # Bindings with 'show=False' are active but not displayed in the footer.
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True, show=True),
        Binding("Z", "quit", "Quit", priority=True, show=False),
        Binding("r", "refresh(False)", "Refresh", show=True),
        Binding("R", "refresh(True)", "Force Refresh", show=True),
        Binding("s", "enter_sort_mode", "Sort", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("f", "toggle_tag_filter", "Filter", show=True),
        Binding("?", "toggle_help", "Toggle Help", show=True),
        Binding("i", "focus_input", "Input", show=False),
        Binding("d", "handle_sort_key('d')", "Sort by Description/Date", show=False),
        Binding("p", "handle_sort_key('p')", "Sort by Price", show=False),
        Binding("c", "handle_sort_key('c')", "Sort by Change/Close", show=False),
        Binding("e", "handle_sort_key('e')", "Sort by % Change", show=False),
        Binding("t", "handle_sort_key('t')", "Sort by Ticker", show=False),
        Binding("u", "handle_sort_key('u')", "Undo Sort", show=False),
        Binding("o", "handle_sort_key('o')", "Sort by Open", show=False),
        Binding("H", "handle_sort_key('H')", "Sort by High", show=False),
        Binding("L", "handle_sort_key('L')", "Sort by Low", show=False),
        Binding("v", "handle_sort_key('v')", "Sort by Volume", show=False),
        Binding("ctrl+c", "copy_text", "Copy", show=False),
        Binding("ctrl+C", "copy_text", "Copy", show=False),
        # FIX: Split the bindings. Escape is high-priority for dismissing things.
        Binding("escape,ctrl+[", "back_or_dismiss", "Dismiss", show=False, priority=True),
        # FIX: Backspace is non-priority, so it's only triggered if a widget
        # (like an Input) doesn't handle it first.
        Binding("backspace", "back_or_dismiss", "Back", show=False),
        Binding("k,up", "move_cursor('up')", "Up", show=False),
        Binding("j,down", "move_cursor('down')", "Down", show=False),
        Binding("h,left", "move_cursor('left')", "Left", show=False),
        Binding("l,right", "move_cursor('right')", "Right", show=False),
    ]

    # Reactive variables trigger UI updates when their values change.
    active_list_category = reactive(None)
    news_ticker = reactive(None)
    history_ticker = reactive(None)
    search_target_table = reactive(None)
    selected_portfolio = reactive("default")
    active_tag_filter = reactive([])

    def __init__(self, cli_overrides: dict | None = None):
        """
        Initializes the application state and loads configurations.

        Args:
            cli_overrides: A dictionary of command-line arguments that override
                           default behavior for the current session.
        """
        super().__init__()
        self.cli_overrides = cli_overrides or {}
        
        # ConfigManager now needs the path to the package root to find default_configs
        self.config = ConfigManager(Path(__file__).resolve().parent)
        self.price_refresh_timer = None
        self.market_status_timer = None
        # This dictionary holds the last known prices to compare against for flashing.
        self._price_comparison_data = {}
        
        # Initialize the database manager for the persistent cache.
        self.db_manager = DbManager(self.config.db_path)
        
        # Initialize the portfolio manager
        self.portfolio_manager = PortfolioManager(self.config)
        
        # --- Pre-populate in-memory caches from persistent DB cache ---
        market_provider.populate_price_cache(self.db_manager.load_price_cache_from_db())
        market_provider.populate_info_cache(self.db_manager.load_info_cache_from_db())
        
        # Internal state management variables
        self._last_refresh_times = {}
        self._available_theme_names = []
        self._processed_themes = {}
        self.theme_variables = {}
        self._original_table_data = []
        self._last_historical_data = None
        self._news_content_for_ticker: str | None = None
        self._last_news_content: tuple[Union[str, Text], list[str]] | None = None
        self._sort_column_key: str | None = None
        self._sort_reverse: bool = False
        self._history_sort_column_key: str | None = None
        self._history_sort_reverse: bool = False
        self._history_period = "1mo"
        self._sort_mode = False
        self._original_status_text = None
        # HACK: Flags to manage cursor restoration on refresh vs. filter changes.
        self._pre_refresh_cursor_key = None
        self._is_filter_refresh = False
        
        # --- Handle CLI Overrides ---
        # If --session-list is used, create temporary lists for this session only.
        # This modifies the in-memory config *before* the UI is built.
        if session_lists := self.cli_overrides.get('session_list'):
            for name, tickers in session_lists.items():
                # Create a simple list structure for the temporary tab.
                self.config.lists[name] = [
                    {"ticker": ticker, "alias": ticker, "note": ""} for ticker in tickers
                ]

        self._setup_dynamic_tabs()

    def compose(self) -> ComposeResult:
        """
        Creates the static layout of the application.
        Widgets are mounted here, but their content is populated later.
        """
        with Vertical(id="app-body"):
            yield Tabs(id="tabs-container")
            with Container(id="app-grid"):
                yield Container(id="output-container")
                # Use the new ConfigContainer instead of the old ConfigView
                yield ConfigContainer(id="config-container")
            with Horizontal(id="status-bar-container"):
                yield Label("Market Status: Unknown", id="market-status")
                yield Label("Last Refresh: Never", id="last-refresh-time")
        yield Footer()

    
    def on_mount(self) -> None:
        """
        Called when the app is first mounted.
        This is where we initialize dynamic content and start background tasks.
        """
        logging.info("Application mounting.")
        
        # Load and set up themes and initial config settings.
        self._load_and_register_themes()
        active_theme = self.config.get_setting("theme", "gruvbox_soft_dark")
        self.app.theme = active_theme
        self._update_theme_variables(active_theme)
        
        # Populate the config view with current settings.
        config_container = self.query_one(ConfigContainer)
        general_view = config_container.query_one(GeneralConfigView)
        general_view.query_one("#theme-select", Select).set_options([(t, t) for t in self._available_theme_names])
        general_view.query_one("#theme-select", Select).value = active_theme
        general_view.query_one("#auto-refresh-switch", Switch).value = self.config.get_setting("auto_refresh", False)
        general_view.query_one("#refresh-interval-input", Input).value = str(self.config.get_setting("refresh_interval", 300.0))
        general_view.query_one("#market-calendar-select", Select).value = self.config.get_setting("market_calendar", "NYSE")

        # --- Determine Start Category and Tickers from CLI Overrides ---
        start_category = None
        if self.cli_overrides:
            if cli_tab := self.cli_overrides.get('tab'):
                start_category = cli_tab
            elif cli_history := self.cli_overrides.get('history'):
                start_category = 'history'
                if isinstance(cli_history, str): self.history_ticker = cli_history
            elif cli_news := self.cli_overrides.get('news'):
                start_category = 'news'
                if isinstance(cli_news, str): self.news_ticker = cli_news
            elif self.cli_overrides.get('debug'):
                start_category = 'debug'
            elif self.cli_overrides.get('configs'):
                start_category = 'configs'
            elif session_lists := self.cli_overrides.get('session_list'):
                # Default to the first session list created if no other view is specified
                start_category = next(iter(session_lists))
        
        if self.cli_overrides.get('period'):
            self._history_period = self.cli_overrides['period']

        # Perform initial setup and start the independent refresh loops.
        self.call_after_refresh(self._rebuild_app, new_active_category=start_category)
        self.call_after_refresh(self._start_refresh_loops)
        
    def on_unmount(self) -> None:
        """
        Clean up background tasks and save all caches to the database on exit.
        """
        # Stop any running timers to prevent tasks from running after exit.
        if self.price_refresh_timer: self.price_refresh_timer.stop()
        if self.market_status_timer: self.market_status_timer.stop()
        
        # Save both price and info caches to the persistent DB.
        self.db_manager.save_price_cache_to_db(market_provider.get_price_cache_state())
        self.db_manager.save_info_cache_to_db(market_provider.get_info_cache_state())
        self.db_manager.close()
        
        self.workers.cancel_all()

    #region UI and App State Management
    def _start_refresh_loops(self) -> None:
        """Kicks off the independent refresh cycles for prices and market status."""
        # Initial price refresh
        self.action_refresh()
        # Start the price auto-refresh timer if configured
        self._manage_price_refresh_timer()
        # Start the smart market status refresh loop
        calendar = self.config.get_setting("market_calendar", "NYSE")
        self.fetch_market_status(calendar)

    def _get_alias_map(self) -> dict[str, str]:
        """Creates a mapping from ticker symbol to its user-defined alias."""
        alias_map = {}
        for list_data in self.config.lists.values():
            for item in list_data:
                ticker = item.get('ticker')
                alias = item.get('alias')
                if ticker and alias:
                    alias_map[ticker] = alias
        return alias_map

    def _get_available_tags_for_category(self, category: str) -> list[str]:
        """Gets all available tags from tickers in the specified category."""
        from stockstui.utils import parse_tags
        
        all_tags = set()
        
        lists_to_check = []
        if category == 'all':
            lists_to_check.extend(self.config.lists.values())
        elif category in self.config.lists:
            lists_to_check.append(self.config.lists[category])

        for list_data in lists_to_check:
            for item in list_data:
                tags_str = item.get('tags', '')
                if tags_str and isinstance(tags_str, str):
                    tags = parse_tags(tags_str)
                    all_tags.update(tags)
        
        return sorted(list(all_tags))

    def _filter_symbols_by_tags(self, category: str, symbols: list[str]) -> list[str]:
        """
        Filters symbols by active tag filter, preserving original order and handling duplicates.
        """
        from stockstui.utils import parse_tags, match_tags
        
        if not self.active_tag_filter:
            return symbols  # No filter applied, return all symbols
        
        # This set tracks tickers we've already added to avoid duplicates in the 'all' view.
        seen_symbols = set()
        ordered_filtered_symbols = []
        
        # Iterate through all configured lists to respect the user-defined order.
        lists_to_check = []
        if category == 'all':
            lists_to_check.extend(self.config.lists.values())
        elif category in self.config.lists:
            lists_to_check.append(self.config.lists.get(category, []))

        # We iterate through the original config lists to get the correct order.
        for list_data in lists_to_check:
            for item in list_data:
                ticker = item.get('ticker')
                # Check if this ticker is in our target list and we haven't already processed it.
                if ticker in symbols and ticker not in seen_symbols:
                    item_tags_str = item.get('tags', '')
                    item_tags = parse_tags(item_tags_str) if item_tags_str else []
                    if match_tags(item_tags, self.active_tag_filter):
                        ordered_filtered_symbols.append(ticker)
                    # Mark as seen to handle duplicates from the 'all' view correctly.
                    seen_symbols.add(ticker)

        logging.info(f"Filtered symbols (ordered): {ordered_filtered_symbols}")
        
        return ordered_filtered_symbols

    def _update_tag_filter_status(self) -> None:
        """Updates the tag filter status display with current counts."""
        try:
            tag_filter = self.query_one("#tag-filter")
            category = self.get_active_category()
            
            if category and category not in ["history", "news", "debug", "configs"]:
                # Get total symbols count
                if category == 'all':
                    total_symbols = list(set(s['ticker'] for lst in self.config.lists.values() for s in lst))
                else:
                    total_symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
                
                # Get filtered symbols count
                filtered_symbols = self._filter_symbols_by_tags(category, total_symbols)
                
                tag_filter.update_filter_status(len(filtered_symbols), len(total_symbols))
        except NoMatches:
            pass

    def _load_and_register_themes(self):
        """
        Loads theme palettes from config, resolves them against the base structure,
        and registers them with Textual so they can be used.
        """
        valid_themes = {}
        for name, theme_data in self.config.themes.items():
            palette = theme_data.get("palette")
            if not palette:
                logging.warning(f"Theme '{name}' has no 'palette' defined. Skipping.")
                continue

            try:
                # Create a resolved theme by substituting palette colors into the base template.
                resolved_theme_dict = copy.deepcopy(BASE_THEME_STRUCTURE)
                resolved_theme_dict = substitute_colors(resolved_theme_dict, palette)
                resolved_theme_dict['dark'] = theme_data.get('dark', False)
                
                # Ensure all color variables were resolved.
                resolved_json = json.dumps(resolved_theme_dict)
                if "UNDEFINED_" in resolved_json:
                    raise ValueError(f"Theme '{name}' is missing one or more required color definitions in its palette.")

                self.register_theme(Theme(name=name, **resolved_theme_dict))
                valid_themes[name] = resolved_theme_dict
            except Exception as e:
                self.notify(f"Theme '{name}' failed to load: {e}", severity="error", timeout=10)
        
        self._processed_themes = valid_themes
        self._available_theme_names = sorted(list(valid_themes.keys()))

    def _update_theme_variables(self, theme_name: str):
        """
        Updates the internal theme variable snapshot for programmatic styling
        (e.g., dynamically coloring rows in a DataTable).
        """
        if theme_name in self._processed_themes:
            theme_dict = self._processed_themes[theme_name]
            self.theme_variables = {
                "primary": theme_dict.get("primary"),
                "secondary": theme_dict.get("secondary"),
                "accent": theme_dict.get("accent"),
                "success": theme_dict.get("success"),
                "warning": theme_dict.get("warning"),
                "error": theme_dict.get("error"),
                "foreground": theme_dict.get("foreground"),
                "background": theme_dict.get("background"),
                "surface": theme_dict.get("surface"),
                **theme_dict.get("variables", {})
            }

    def _setup_dynamic_tabs(self):
        """
        Generates the list of tabs to be displayed based on user configuration
        (i.e., defined lists and hidden tabs).
        """
        self.tab_map = []
        hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
        
        # Get all list categories, including temporary session lists.
        all_list_categories = list(self.config.lists.keys())
        all_possible_categories = ["all"] + all_list_categories + ["history", "news", "debug"]
        
        for category in all_possible_categories:
            if category not in hidden_tabs:
                self.tab_map.append({'name': category.replace("_", " ").capitalize(), 'category': category})
        self.tab_map.append({'name': "Configs", 'category': 'configs'})

    async def _rebuild_app(self, new_active_category: str | None = None):
        """
        Rebuilds dynamic parts of the UI, primarily the tabs and config screen widgets.
        This is called on startup and after any change that affects tabs or lists.
        """
        self._setup_dynamic_tabs()
        tabs_widget = self.query_one(Tabs)
        current_active_cat = new_active_category or self.get_active_category()
        await tabs_widget.clear()
        
        # Recreate the tabs.
        for i, tab_data in enumerate(self.tab_map, start=1):
            await tabs_widget.add_tab(Tab(f"{i}: {tab_data['name']}", id=f"tab-{i}"))
        self._update_tab_bindings()
        
        # Determine which tab should be active after the rebuild.
        try:
            # Prioritize the category passed from the CLI or other logic
            idx_to_activate = next(i for i, t in enumerate(self.tab_map, start=1) if t['category'] == current_active_cat)
        except (StopIteration, NoMatches):
            # Fallback to the user's default configured tab
            default_cat = self.config.get_setting("default_tab_category", "all")
            try:
                idx_to_activate = next(i for i, t in enumerate(self.tab_map, start=1) if t['category'] == default_cat)
            except (StopIteration, NoMatches):
                # Ultimate fallback to the first tab
                idx_to_activate = 1
        
        if tabs_widget.tab_count >= idx_to_activate:
            tabs_widget.active = f"tab-{idx_to_activate}"
        
        # Repopulate the selects and checkboxes in the ConfigContainer.
        config_container = self.query_one(ConfigContainer)
        general_view = config_container.query_one(GeneralConfigView)
        default_tab_select = general_view.query_one("#default-tab-select", Select)
        options = [(t['name'], t['category']) for t in self.tab_map if t['category'] not in ['configs', 'history', 'news', 'debug']]
        default_tab_select.set_options(options)
        
        default_cat_value = self.config.get_setting("default_tab_category", "all")
        
        valid_option_values = [opt[1] for opt in options]
        
        if default_cat_value in valid_option_values:
            default_tab_select.value = default_cat_value
        elif options:
            default_tab_select.value = options[0][1]
        else:
            default_tab_select.clear()
        
        vis_container = general_view.query_one("#visible-tabs-container")
        await vis_container.remove_children()
        all_cats_for_toggle = ["all"] + list(self.config.lists.keys()) + ["history", "news", "debug"]
        hidden = set(self.config.get_setting("hidden_tabs", []))
        for cat in all_cats_for_toggle:
            # Don't show session lists in the "Visible Tabs" config panel
            if self.cli_overrides.get('session_list') and cat in self.cli_overrides['session_list']:
                continue
            checkbox = Checkbox(cat.replace("_", " ").capitalize(), cat not in hidden, name=cat)
            await vis_container.mount(checkbox)
            
        # The ListsConfigView is now responsible for populating its own list.
        self.query_one(ListsConfigView).repopulate_lists()

    def get_active_category(self) -> str | None:
        """Returns the category string (e.g., 'stocks', 'crypto') of the currently active tab."""
        try:
            active_tab_id = self.query_one(Tabs).active
            if active_tab_id:
                # e.g., 'tab-1' -> index 0
                return self.tab_map[int(active_tab_id.split('-')[1]) - 1]['category']
        except (NoMatches, IndexError, ValueError):
            return None
            
    def _update_tab_bindings(self):
        """Binds number keys (1-9, 0) to select the corresponding tab."""
        for i in range(1, 10): self.bind(str(i), f"select_tab({i})", description=f"Tab {i}", show=False)
        self.bind("0", "select_tab(10)", description="Tab 10", show=False)

    def action_select_tab(self, tab_index: int):
        """Action to switch to a tab by its number."""
        try:
            tabs = self.query_one(Tabs)
            if tab_index <= tabs.tab_count:
                tabs.active = f"tab-{tab_index}"
        except NoMatches:
            pass

    def action_copy_text(self) -> None:
        """Copies the currently selected text to the system clipboard."""
        selection = self.screen.get_selected_text()
        if selection is None:
            raise SkipAction()
        self.copy_to_clipboard(selection)

    def _manage_price_refresh_timer(self):
        """Starts or stops the auto-refresh timer for prices based on the user's config."""
        if self.price_refresh_timer:
            self.price_refresh_timer.stop()
        if self.config.get_setting("auto_refresh", False):
            try:
                interval = float(self.config.get_setting("refresh_interval", 300.0))
                # Auto-refresh should always be a "smart" refresh, not a force refresh.
                self.price_refresh_timer = self.set_interval(interval, lambda: self.action_refresh(force=False))
            except (ValueError, TypeError):
                logging.error("Invalid refresh interval.")
    
    def _schedule_next_market_status_refresh(self, status: dict):
        """
        Calculates the next poll interval for the market status and sets a timer.
        This creates a self-adjusting "smart" refresh cycle.
        """
        if self.market_status_timer:
            self.market_status_timer.stop()

        now = datetime.now(timezone.utc)
        next_open = status.get('next_open')
        next_close = status.get('next_close')
        current_status = status.get('status')

        # Default interval: 5 minutes
        interval = 300.0

        if current_status == 'open' and next_close:
            time_to_close = (next_close - now).total_seconds()
            if time_to_close <= 900:  # Within 15 minutes of closing
                interval = 30  # High frequency
            else:
                interval = 300 # Normal open-market frequency
        elif current_status == 'closed' and next_open:
            time_to_open = (next_open - now).total_seconds()
            if 0 < time_to_open <= 900: # Within 15 minutes of opening
                interval = 30 # High frequency
            elif 900 < time_to_open <= 3600 * 2: # Within 2 hours of opening
                interval = 300 # Medium frequency
            else: # Market is closed for a long time
                interval = 3600 # Low frequency (1 hour)

        # Ensure interval is not negative and has a minimum value
        interval = max(interval, 5.0)

        logging.info(f"Market status is '{current_status}'. Scheduling next poll in {interval:.2f} seconds.")

        calendar = self.config.get_setting("market_calendar", "NYSE")
        self.market_status_timer = self.set_timer(
            interval,
            lambda: self.fetch_market_status(calendar)
        )
    
    def action_refresh(self, force: bool = False):
        """
        Refreshes price data for the current view.
        - force: If True, bypasses the smart expiry cache for all symbols.
        """
        category = self.get_active_category()
        if category and category not in ["history", "news", "debug", "configs"]:
            if category == 'all':
                seen = set()
                symbols = [s['ticker'] for lst in self.config.lists.values() for s in lst if s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
            
            logging.info("Applying tag filter")

            # Apply tag filtering
            symbols = self._filter_symbols_by_tags(category, symbols)

            if symbols:
                try:
                    price_table = self.query_one("#price-table", DataTable)
                    if force and price_table.row_count == 0:
                        price_table.loading = True
                except NoMatches:
                    pass
                self.fetch_prices(symbols, force=force, category=category)

    def action_toggle_help(self) -> None:
        """
        Toggles the built-in Textual help screen.
        """
        if self.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()
            
    def action_toggle_tag_filter(self) -> None:
        """Toggles the visibility of the tag filter widget if it has tags."""
        category = self.get_active_category()
        if category and category in ["history", "news", "debug", "configs"]:
            self.bell() # Not applicable in these views
            return

        try:
            tag_filter = self.query_one("#tag-filter", TagFilterWidget)
            # Only allow toggling if there are tags to filter by.
            if not tag_filter.available_tags:
                self.notify("No tags available for this list.", severity="information")
                self.bell()
                return

            tag_filter.display = not tag_filter.display
            if tag_filter.display:
                try:
                    # If there are any filter buttons, focus the first one
                    first_button = tag_filter.query_one(".tag-button", Button)
                    first_button.focus()
                except NoMatches:
                    pass # No tags, nothing to focus
        except NoMatches:
            self.bell() # No tag filter widget on this view

    def action_move_cursor(self, direction: str) -> None:
        """
        Handles unified hjkl/arrow key navigation.
        It prioritizes moving the cursor in the currently focused widget.
        If the widget doesn't support cursor movement, it falls back to scrolling
        the main content area.
        """
        # Priority 1: Main Tabs navigation
        if self.focused and isinstance(self.focused, Tabs):
            if direction == 'left': self.focused.action_previous_tab()
            elif direction == 'right': self.focused.action_next_tab()
            return

        # Priority 2: Generic cursor movement for widgets that support it.
        if self.focused and hasattr(self.focused, f"action_cursor_{direction}"):
            getattr(self.focused, f"action_cursor_{direction}")()
            return

        # Priority 3: Fallback to scrolling the container for up/down
        if direction in ("up", "down"):
            if (scrollable := self._get_active_scrollable_widget()):
                if direction == "up": scrollable.scroll_up(duration=0.5)
                else: scrollable.scroll_down(duration=0.5)

    def _get_primary_view_widget(self) -> Widget | None:
        """
        Gets the primary *focusable* widget for the currently active view.
        This centralizes the logic for finding the main interactive widget for a view.
        """
        category = self.get_active_category()
        target_id = None
        
        if category == 'history':
            target_id = '#history-ticker-input'
        elif category == 'news':
            target_id = '#news-ticker-input'
        elif category == 'configs':
            # In the new config layout, the container itself is the primary target
            target_id = '#config-container'
        elif category == 'debug':
            target_id = '#debug-table'
        elif category and category not in ['history', 'news', 'configs', 'debug']: # Price views
            target_id = '#price-table'

        if target_id:
            try:
                return self.query_one(target_id)
            except NoMatches:
                pass
        return None
    
    def _get_active_scrollable_widget(self) -> Container | None:
        """
        Determines the currently visible main container that should be scrolled
        by the fallback `move_cursor` logic. This is now tied to the primary widget.
        """
        primary_widget = self._get_primary_view_widget()
        if not primary_widget:
            return None

        # Determine the scrollable container based on the primary widget's view
        category = self.get_active_category()
        if category == 'configs':
            return self.query_one("#config-container")
        
        # For all other views, the scrollable area is within #output-container
        output_container = self.query_one('#output-container')
        
        if category == 'news':
            return output_container.query_one('#news-output-display')
        elif category == 'history':
            return output_container.query_one('#history-display-container')
        else: # Default for price, debug, etc.
            return output_container
    #endregion

    #region Data Flow
    async def _display_data_for_category(self, category: str):
        """
        Renders the main content area based on the selected tab's category.
        This method is the router that decides whether to show a price table,
        the history view, the news view, etc.
        """
        output_container = self.query_one("#output-container")
        config_container = self.query_one("#config-container")
        await output_container.remove_children()

        # Toggle visibility between the main output and config screens.
        is_config_tab = category == "configs"
        config_container.display = is_config_tab
        output_container.display = not is_config_tab
        self.query_one("#status-bar-container").display = not is_config_tab
        if is_config_tab:
            # If switching to the config tab, ensure the main hub is shown.
            config_container.show_main()
            return

        if category == 'history':
            await output_container.mount(HistoryView())
        elif category == 'news':
            await output_container.mount(NewsView())
        elif category == 'debug':
            await output_container.mount(DebugView())
        else: # This is a price view for 'all' or a specific list
            # Add tag filter widget for all price views. It's hidden by default and toggled via keybind.
            if category not in ["history", "news", "debug", "configs"]:
                available_tags = self._get_available_tags_for_category(category)
                # The widget is created but initially hidden. It can be toggled with the 'f' key.
                tag_filter = TagFilterWidget(available_tags=available_tags, id="tag-filter")
                tag_filter.display = False # Initially hidden
                await output_container.mount(tag_filter)

            await output_container.mount(NavigableDataTable(id="price-table", zebra_stripes=True))

            price_table = self.query_one("#price-table", NavigableDataTable)
            price_table.add_column("Description", key="Description")
            price_table.add_column("Price", key="Price")
            price_table.add_column("Change", key="Change")
            price_table.add_column("% Change", key="% Change")
            price_table.add_column("Day's Range", key="Day's Range")
            price_table.add_column("52-Wk Range", key="52-Wk Range")
            price_table.add_column("Ticker", key="Ticker")
            
            if category == 'all':
                # Preserve config order for 'all' view
                seen = set()
                symbols = [s['ticker'] for lst in self.config.lists.values() for s in lst if s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
            
            # Apply tag filtering
            symbols = self._filter_symbols_by_tags(category, symbols)
            
            if symbols and not any(market_provider.is_cached(s) for s in symbols):
                price_table.loading = True
                self.fetch_prices(symbols, force=False, category=category)
            elif symbols:
                # We have symbols, try to get cached data
                # Re-order cached data to match the desired symbol order
                data_map = {item['symbol']: item for s in symbols if (item := market_provider.get_cached_price(s))}
                cached_data = [data_map[s] for s in symbols if s in data_map]
                
                if cached_data:
                    alias_map = self._get_alias_map()
                    # Populate comparison data before initial display
                    self._price_comparison_data = {item.get('symbol'): item.get('price') for item in cached_data if item.get('price') is not None}
                    rows = formatter.format_price_data_for_table(cached_data, self._price_comparison_data, alias_map)
                    self._style_and_populate_price_table(price_table, rows)
                    self._apply_price_table_sort()
                else:
                    # We have symbols but no cached data, fetch them
                    price_table.loading = True
                    self.fetch_prices(symbols, force=False, category=category)
            else:
                # No symbols in the list
                price_table.add_row(f"[dim]No symbols in list '{category}'. Add some in the Configs tab.[/dim]")

    @work(exclusive=True, thread=True)
    def fetch_prices(self, symbols: list[str], force: bool, category: str):
        """Worker to fetch market price data in the background."""
        try:
            data = market_provider.get_market_price_data(symbols, force_refresh=force)
            if not get_current_worker().is_cancelled:
                self.post_message(PriceDataUpdated(data, category))
        except Exception as e:
            logging.error(f"Worker fetch_prices failed for category '{category}': {e}")

    @work(exclusive=True, thread=True)
    def fetch_market_status(self, calendar: str):
        """Worker to fetch the current market status."""
        try:
            status = market_provider.get_market_status(calendar)
            if not get_current_worker().is_cancelled:
                self.post_message(MarketStatusUpdated(status))
        except Exception as e:
            logging.error(f"Market status worker failed: {e}")

    @work(exclusive=True, thread=True)
    def fetch_news(self, tickers_str: str):
        """Worker to fetch news data for one or more tickers."""
        try:
            tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
            if not tickers:
                if not get_current_worker().is_cancelled:
                    self.post_message(NewsDataUpdated(tickers_str, []))
                return

            data = market_provider.get_news_for_tickers(tickers)
            if not get_current_worker().is_cancelled:
                self.post_message(NewsDataUpdated(tickers_str, data))
        except Exception as e:
            logging.error(f"Worker fetch_news failed for {tickers_str}: {e}")
            if not get_current_worker().is_cancelled:
                self.post_message(NewsDataUpdated(tickers_str, None))
            
    @work(exclusive=True, thread=True)
    def fetch_historical_data(self, ticker: str, period: str, interval: str = "1d"):
        """Worker to fetch historical price data for a specific ticker."""
        try:
            data = market_provider.get_historical_data(ticker, period, interval)
            if not get_current_worker().is_cancelled:
                self.post_message(HistoricalDataUpdated(data))
        except Exception as e:
            logging.error(f"Worker fetch_historical_data failed for {ticker} over {period} with interval {interval}: {e}")

    @work(exclusive=True, thread=True)
    def run_info_comparison_test(self, ticker: str):
        """Worker to fetch fast vs slow ticker info for the debug tab."""
        data = market_provider.get_ticker_info_comparison(ticker)
        if not get_current_worker().is_cancelled:
            self.post_message(TickerInfoComparisonUpdated(fast_info=data['fast'], slow_info=data['slow']))

    @work(exclusive=True, thread=True)
    def run_ticker_debug_test(self, symbols: list[str]):
        """Worker to run the individual ticker latency test."""
        start_time = time.perf_counter()
        data = market_provider.run_ticker_debug_test(symbols)
        total_time = time.perf_counter() - start_time
        if not get_current_worker().is_cancelled:
            self.post_message(TickerDebugDataUpdated(data, total_time))
        
    @work(exclusive=True, thread=True)
    def run_list_debug_test(self, lists: dict[str, list[str]]):
        """Worker to run the list batch network test."""
        start_time = time.perf_counter()
        data = market_provider.run_list_debug_test(lists)
        total_time = time.perf_counter() - start_time
        if not get_current_worker().is_cancelled:
            self.post_message(ListDebugDataUpdated(data, total_time))

    @work(exclusive=True, thread=True)
    def run_cache_test(self, lists: dict[str, list[str]]):
        """Worker to run the local cache speed test."""
        start_time = time.perf_counter()
        data = market_provider.run_cache_test(lists)
        total_time = time.perf_counter() - start_time
        if not get_current_worker().is_cancelled:
            self.post_message(CacheTestDataUpdated(data, total_time))

    def _style_and_populate_price_table(self, price_table: DataTable, rows: list[tuple]):
        """
        Applies dynamic styling (colors) to the raw data and populates
        the main price table. Also handles flashing cells on price changes.
        """
        price_color = self.theme_variables.get("price", "cyan")
        success_color = self.theme_variables.get("success", "green")
        error_color = self.theme_variables.get("error", "red")
        muted_color = self.theme_variables.get("text-muted", "dim")

        for row_data in rows:
            desc, price, change, change_percent, day_range, week_range, symbol, change_direction = row_data
            
            if desc == 'Invalid Ticker':
                desc_text = Text(desc, style=error_color)
            elif desc == 'N/A':
                desc_text = Text(desc, style=muted_color)
            else:
                desc_text = Text(desc)
            
            price_text = Text(f"${price:,.2f}", style=price_color, justify="right") if price is not None else Text("N/A", style=muted_color, justify="right")
            
            if change is not None and change_percent is not None:
                if change > 0:
                    change_text = Text(f"{change:,.2f}", style=success_color, justify="right")
                    change_percent_text = Text(f"+{change_percent:.2%}", style=success_color, justify="right")
                elif change < 0:
                    change_text = Text(f"{change:,.2f}", style=error_color, justify="right")
                    change_percent_text = Text(f"{change_percent:.2%}", style=error_color, justify="right")
                else:
                    change_text = Text("0.00", justify="right")
                    change_percent_text = Text("0.00%", justify="right")
            else:
                change_text = Text("N/A", style=muted_color, justify="right")
                change_percent_text = Text("N/A", style=muted_color, justify="right")
            
            day_range_text = Text(day_range, style=muted_color if day_range == "N/A" else "", justify="right")
            week_range_text = Text(week_range, style=muted_color if week_range == "N/A" else "", justify="right")
            ticker_text = Text(symbol, style=muted_color)
            price_table.add_row(desc_text, price_text, change_text, change_percent_text, day_range_text, week_range_text, ticker_text, key=symbol)
            
            if change_direction == 'up':
                self.flash_cell(symbol, "Change", "positive")
                self.flash_cell(symbol, "% Change", "positive")
            elif change_direction == 'down':
                self.flash_cell(symbol, "Change", "negative")
                self.flash_cell(symbol, "% Change", "negative")

    @on(PriceDataUpdated)
    async def on_price_data_updated(self, message: PriceDataUpdated):
        """Handles the arrival of new price data from a worker."""
        # FIX: Use the correct `datetime.now()` call after changing the import.
        now_str = f"Last Refresh: {datetime.now():%H:%M:%S}"
        if message.category == 'all':
            for cat in list(self.config.lists.keys()) + ['all']:
                self._last_refresh_times[cat] = now_str
        else:
            self._last_refresh_times[message.category] = now_str
        
        active_category = self.get_active_category()
        is_relevant = (active_category == message.category) or (message.category == 'all' and active_category not in ['history', 'news', 'debug', 'configs'])
        if not is_relevant: return

        try:
            dt = self.query_one("#price-table", DataTable)
            
            # --- START: Cursor Preservation Logic ---
            self._pre_refresh_cursor_key = None
            if not self._is_filter_refresh and dt.row_count > 0 and dt.cursor_row >= 0:
                try:
                    # Use the correct public API to get the row key from the cursor index.
                    coordinate = Coordinate(row=dt.cursor_row, column=0)
                    self._pre_refresh_cursor_key = dt.coordinate_to_cell_key(coordinate).row_key
                except CellDoesNotExist:
                    self._pre_refresh_cursor_key = None
            # --- END: Cursor Preservation Logic ---

            dt.loading = False
            dt.clear()
            
            # --- FIX: Start of order-preserving logic ---
            # 1. Determine the correct, ordered list of symbols that should be on screen.
            if active_category == 'all':
                # For 'all', we iterate through lists in config order to build the base symbol list.
                # Duplicates are implicitly handled by _filter_symbols_by_tags.
                seen = set()
                symbols_on_screen = [s['ticker'] for lst in self.config.lists.values() for s in lst if s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols_on_screen = [s['ticker'] for s in self.config.lists.get(active_category, [])]

            ordered_filtered_symbols = self._filter_symbols_by_tags(active_category, symbols_on_screen)

            # 2. Create a mapping from symbol to its data for efficient lookup.
            data_map = {item['symbol']: item for item in message.data}

            # 3. Build the final data list in the correct order.
            data_for_table = [data_map[symbol] for symbol in ordered_filtered_symbols if symbol in data_map]
            # --- FIX: End of order-preserving logic ---

            if not data_for_table:
                if ordered_filtered_symbols:
                    # We expected data but couldn't fetch it
                    dt.add_row("[dim]Could not fetch data for any symbols in this list.[/dim]")
                elif symbols_on_screen and not ordered_filtered_symbols:
                    # No symbols match the current tag filter
                    dt.add_row("[dim]No symbols match the current tag filter.[/dim]")
                else:
                    # No symbols in the list
                    dt.add_row(f"[dim]No symbols in list '{active_category}'. Add some in the Configs tab.[/dim]")
                return

            alias_map = self._get_alias_map()
            rows = formatter.format_price_data_for_table(data_for_table, self._price_comparison_data, alias_map)
            
            self._style_and_populate_price_table(dt, rows)
            
            # After populating, update the comparison data with the new prices for the next cycle.
            self._price_comparison_data = {
                item['symbol']: item.get('price')
                for item in data_for_table
                if item.get('price') is not None
            }
            
            self._apply_price_table_sort()
            self.query_one("#last-refresh-time").update(now_str)

            # --- START: Cursor Restoration Logic ---
            if self._pre_refresh_cursor_key:
                try:
                    new_row_index = dt.get_row_index(self._pre_refresh_cursor_key)
                    dt.move_cursor(row=new_row_index)
                except KeyError:
                    pass # The previously selected row no longer exists, do nothing.
            
            self._is_filter_refresh = False # Reset the flag after the refresh is complete
            # --- END: Cursor Restoration Logic ---

        except NoMatches: pass
    
    @on(MarketStatusUpdated)
    async def on_market_status_updated(self, message: MarketStatusUpdated):
        """Handles the arrival of new market status data and schedules the next poll."""
        try:
            status_parts = formatter.format_market_status(message.status)
            if not status_parts:
                self.query_one("#market-status").update(Text("Market: Unknown", style="dim"))
                return

            calendar, status, holiday = status_parts
            status_color_map = {"open": self.theme_variables.get("status-open", "green"), "pre": self.theme_variables.get("status-pre", "yellow"), "post": self.theme_variables.get("status-post", "yellow"), "closed": self.theme_variables.get("status-closed", "red")}
            status_text_map = {"open": "Open", "pre": "Pre-Market", "post": "After Hours", "closed": "Closed"}
            status_color = status_color_map.get(status, "dim")
            status_display = status_text_map.get(status, "Unknown")
            
            text = Text.assemble(f"{calendar}: ", (f"{status_display}", status_color))
            if holiday and status == 'closed':
                holiday_display = holiday[:20] + '...' if len(holiday) > 20 else holiday
                text.append(f" ({holiday_display})", style=self.theme_variables.get("text-muted", "dim"))
            
            self.query_one("#market-status").update(text)
            
            # This is the key part of the new feature: schedule the next check.
            self._schedule_next_market_status_refresh(message.status)
        except NoMatches: pass

    @on(HistoricalDataUpdated)
    async def on_historical_data_updated(self, message: HistoricalDataUpdated):
        """Handles arrival of historical data, then tells the history view to render it."""
        try:
            self.query_one("#history-display-container").loading = False
        except NoMatches: return

        self._last_historical_data = message.data
        try:
            history_view = self.query_one(HistoryView)
            await history_view._render_historical_data()
        except NoMatches: pass

    @on(NewsDataUpdated)
    async def on_news_data_updated(self, message: NewsDataUpdated):
        """Handles arrival of news data, then tells the news view to render it."""
        self._news_content_for_ticker = message.tickers_str
        if message.data is None:
            error_markdown = (f"**Error:** Could not retrieve news for '{message.tickers_str}'.\n\n" "This may be due to an invalid symbol or a network connectivity issue.")
            self._last_news_content = (error_markdown, [])
        else:
            self._last_news_content = formatter.format_news_for_display(message.data)
        
        if self.get_active_category() == 'news' and self.news_ticker == message.tickers_str:
            try:
                self.query_one(NewsView).update_content(*self._last_news_content)
            except NoMatches: pass

    @on(TickerInfoComparisonUpdated)
    async def on_ticker_info_comparison_updated(self, message: TickerInfoComparisonUpdated):
        """Handles arrival of the fast/slow info comparison test data."""
        try:
            for button in self.query(".debug-buttons Button"): button.disabled = False
            dt = self.query_one("#debug-table", DataTable); dt.loading = False; dt.clear()
            rows = formatter.format_info_comparison(message.fast_info, message.slow_info)
            muted_color = self.theme_variables.get("text-muted", "dim"); warning_color = self.theme_variables.get("warning", "yellow")
            for key, fast_val, slow_val, is_mismatch in rows:
                fast_text = Text(fast_val, style=warning_color if is_mismatch else (muted_color if fast_val == "N/A" else ""))
                slow_text = Text(slow_val, style=warning_color if is_mismatch else (muted_color if slow_val == "N/A" else ""))
                dt.add_row(key, fast_text, slow_text)
        except NoMatches: pass
    
    @on(TickerDebugDataUpdated)
    async def on_ticker_debug_data_updated(self, message: TickerDebugDataUpdated):
        """Handles arrival of the individual ticker latency test data."""
        try:
            for button in self.query(".debug-buttons Button"): button.disabled = False
            dt = self.query_one("#debug-table", DataTable); dt.loading = False; dt.clear()
            rows = formatter.format_ticker_debug_data_for_table(message.data)
            success_color = self.theme_variables.get("success", "green"); error_color = self.theme_variables.get("error", "red"); lat_high = self.theme_variables.get("latency-high", "red"); lat_med = self.theme_variables.get("latency-medium", "yellow"); lat_low = self.theme_variables.get("latency-low", "blue"); muted_color = self.theme_variables.get("text-muted", "dim")
            for symbol, is_valid, description, latency in rows:
                valid_text = Text("Yes", style=success_color) if is_valid else Text("No", style=f"bold {error_color}")
                if latency > 2.0: latency_style = lat_high
                elif latency > 0.5: latency_style = lat_med
                else: latency_style = lat_low
                latency_text = Text(f"{latency:.3f}s", style=latency_style, justify="right")
                desc_text = Text(description, style=muted_color if not is_valid or description == 'N/A' else "")
                dt.add_row(symbol, valid_text, desc_text, latency_text)
            self.query_one("#last-refresh-time").update(Text.assemble("Test Completed. Total time: ", (f"{message.total_time:.2f}s", f"bold {self.theme_variables.get('warning')}")))
        except NoMatches: pass
            
    @on(ListDebugDataUpdated)
    async def on_list_debug_data_updated(self, message: ListDebugDataUpdated):
        """Handles arrival of the list batch network test data."""
        try:
            for button in self.query(".debug-buttons Button"): button.disabled = False
            dt = self.query_one("#debug-table", DataTable); dt.loading = False; dt.clear()
            rows = formatter.format_list_debug_data_for_table(message.data)
            lat_high = self.theme_variables.get("latency-high", "red"); lat_med = self.theme_variables.get("latency-medium", "yellow"); lat_low = self.theme_variables.get("latency-low", "blue"); muted_color = self.theme_variables.get("text-muted", "dim")
            for list_name, ticker_count, latency in rows:
                if latency > 5.0: latency_style = lat_high
                elif latency > 2.0: latency_style = lat_med
                else: latency_style = lat_low
                latency_text = Text(f"{latency:.3f}s", style=latency_style, justify="right")
                list_name_text = Text(list_name, style=muted_color if list_name == 'N/A' else "")
                dt.add_row(list_name_text, str(ticker_count), latency_text)
            self.query_one("#last-refresh-time").update(Text.assemble("Test Completed. Total time: ", (f"{message.total_time:.2f}s", f"bold {self.theme_variables.get('warning')}")))
        except NoMatches: pass

    @on(CacheTestDataUpdated)
    async def on_cache_test_data_updated(self, message: CacheTestDataUpdated):
        """Handles arrival of the local cache speed test data."""
        try:
            for button in self.query(".debug-buttons Button"): button.disabled = False
            dt = self.query_one("#debug-table", DataTable); dt.loading = False; dt.clear()
            rows = formatter.format_cache_test_data_for_table(message.data)
            price_color = self.theme_variables.get("price", "cyan"); muted_color = self.theme_variables.get("text-muted", "dim")
            for list_name, ticker_count, latency in rows:
                latency_text = Text(f"{latency * 1000:.3f} ms", style=price_color, justify="right")
                list_name_text = Text(list_name, style=muted_color if list_name == 'N/A' else "")
                dt.add_row(list_name_text, str(ticker_count), latency_text)
            self.query_one("#last-refresh-time").update(Text.assemble("Test Completed. Total time: ", (f"{message.total_time * 1000:.2f} ms", f"bold {self.theme_variables.get('price')}")))
        except NoMatches: pass
    
    def _apply_price_table_sort(self) -> None:
        """Applies the current sort order to the price table."""
        if self._sort_column_key is None: return
        try:
            table = self.query_one("#price-table", DataTable)
            def sort_key(row_values: tuple) -> tuple[int, any]:
                column_index = table.get_column_index(self._sort_column_key)
                if column_index >= len(row_values): return (1, 0)
                cell_value = row_values[column_index]
                text_content = extract_cell_text(cell_value)
                if text_content in ("N/A", "Invalid Ticker"): return (1, 0)
                if self._sort_column_key in ("Description", "Ticker"):
                    return (0, text_content.lower())
                cleaned_text = text_content.replace("$", "").replace(",", "").replace("%", "").replace("+", "")
                try: return (0, float(cleaned_text))
                except (ValueError, TypeError): return (1, 0)
            table.sort(key=sort_key, reverse=self._sort_reverse)
        except (NoMatches, KeyError): logging.error(f"Could not find table or column for sort key '{self._sort_column_key}'")
            
    def _apply_history_table_sort(self) -> None:
        """Applies the current sort order to the history table."""
        if self._history_sort_column_key is None: return
        try:
            table = self.query_one("#history-table", DataTable)
            def sort_key(row_values: tuple) -> tuple[int, any]:
                column_index = table.get_column_index(self._history_sort_column_key)
                if column_index >= len(row_values): return (1, 0)
                text_content = extract_cell_text(row_values[column_index])
                if self._history_sort_column_key == "Date":
                    try: return (0, text_content)
                    except (ValueError, TypeError): return (1, "")
                cleaned_text = text_content.replace("$", "").replace(",", "")
                try: return (0, float(cleaned_text))
                except (ValueError, TypeError): return (1, 0)
            table.sort(key=sort_key, reverse=self._history_sort_reverse)
        except (NoMatches, KeyError): logging.error(f"Could not find history table or column for sort key '{self._history_sort_column_key}'")
    
    def flash_cell(self, row_key: str, column_key: str, flash_type: str) -> None:
        """Applies a temporary background color flash to a specific cell in the price table."""
        try:
            dt = self.query_one("#price-table", DataTable)
            current_content = dt.get_cell(row_key, column_key)

            if not isinstance(current_content, Text): return

            flash_color_name = self.theme_variables.get("success") if flash_type == "positive" else self.theme_variables.get("error")
            bg_color = Color.parse(flash_color_name).with_alpha(0.3)
            
            flash_text_color = self.theme_variables.get("background")
            new_style = Style(color=flash_text_color, bgcolor=bg_color.rich_color)
            
            flashed_content = Text(
                current_content.plain,
                style=new_style,
                justify=current_content.justify
            )
            
            dt.update_cell(row_key, column_key, flashed_content, update_width=False)
            
            self.set_timer(0.8, lambda: self.unflash_cell(row_key, column_key, current_content))
        except (KeyError, NoMatches, AttributeError):
            pass

    def unflash_cell(self, row_key: str, column_key: str, original_content: Text) -> None:
        """Restores a cell to its original, non-flashed state."""
        try:
            dt = self.query_one("#price-table", DataTable)
            dt.update_cell(row_key, column_key, original_content, update_width=False)
        # FIX: Catch the correctly imported exception.
        except (KeyError, NoMatches, CellDoesNotExist):
            pass
    #endregion

    #region Event Handlers & Actions
    @on(Tabs.TabActivated)
    async def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        """Handles tab switching. Resets sort state and displays new content."""
        try:
            self.query_one(SearchBox).remove()
            self._original_table_data = [] # Clear the backup data as well.
        except NoMatches:
            pass

        self._sort_column_key = None; self._sort_reverse = False
        self._history_sort_column_key = None; self._history_sort_reverse = False
        
        active_category = self.get_active_category()
        if active_category:
            await self._display_data_for_category(active_category)

        self.action_refresh()

        try:
            status_label = self.query_one("#last-refresh-time")
            if active_category in ['history', 'news', 'debug', 'configs']:
                status_label.update("")
        except NoMatches:
            pass
        
    @on(DataTable.RowSelected, "#price-table")
    def on_main_datatable_row_selected(self, event: DataTable.RowSelected):
        """When a row is selected on the price table, set it as the active ticker for other views."""
        if event.row_key.value:
            self.news_ticker = event.row_key.value
            self.history_ticker = event.row_key.value
            self.notify(f"Selected {self.news_ticker} for news/history tabs.")
    

    @on(DataTable.HeaderSelected, "#price-table")
    def on_price_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handles header clicks to sort the price table."""
        self._set_and_apply_sort(str(event.column_key.value), "click")

    def _set_and_apply_sort(self, column_key_str: str, source: str) -> None:
        """Sets the sort key and direction for the price table and applies it."""
        sortable_columns = {"Description", "Price", "Change", "% Change", "Ticker"}
        if column_key_str not in sortable_columns: return

        if self._sort_column_key == column_key_str:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column_key = column_key_str
            self._sort_reverse = column_key_str not in ("Description", "Ticker")
        self._apply_price_table_sort()
        
    def _set_and_apply_history_sort(self, column_key_str: str, source: str) -> None:
        """Sets the sort key and direction for the history table and applies it."""
        if self._history_sort_column_key == column_key_str:
            self._history_sort_reverse = not self._history_sort_reverse
        else:
            self._history_sort_column_key = column_key_str
            self._history_sort_reverse = column_key_str == "Date"
        self._apply_history_table_sort()

    def action_enter_sort_mode(self) -> None:
        """Enters 'sort mode', displaying available sort keys in the status bar."""
        if self._sort_mode: return
        category = self.get_active_category()
        if category == 'history' or (category and category not in ['news', 'debug', 'configs']):
            self._sort_mode = True
            try:
                status_label = self.query_one("#last-refresh-time", Label)
                self._original_status_text = status_label.renderable
                if category == 'history':
                    status_label.update("SORT BY: \\[d]ate, \\[o]pen, \\[H]igh, \\[L]ow, \\[c]lose, \\[v]olume, \\[ESC]ape")
                else:
                    status_label.update("SORT BY: \\[d]escription, \\[p]rice, \\[c]hange, p\\[e]rcent, \\[t]icker, \\[u]ndo, \\[ESC]ape")
            except NoMatches: self._sort_mode = False
        else:
            self.bell()

    async def _undo_sort(self) -> None:
        """Restores the price table to its original, unsorted order."""
        self._sort_column_key = None
        self._sort_reverse = False
        await self._display_data_for_category(self.get_active_category())

    def action_back_or_dismiss(self) -> None:
        """
        Handles 'back' and 'dismiss' actions in a context-sensitive way.
        This action is bound to 'escape' and 'backspace'.
        """
        # Priority 1: Clear sort mode if active.
        if self._sort_mode:
            self._sort_mode = False
            try:
                status_label = self.query_one("#last-refresh-time", Label)
                if self._original_status_text is not None:
                    status_label.update(self._original_status_text)
            except NoMatches:
                pass
            return

        # Priority 2: Dismiss the search box if it's active.
        try:
            search_box = self.query_one(SearchBox)
            if self._original_table_data:
                self.search_target_table.clear()
                for row_key, row_data in self._original_table_data:
                    self.search_target_table.add_row(*row_data, key=row_key.value)
            search_box.remove()
            return
        except NoMatches:
            pass
        
        # Priority 3: Handle back-navigation within the ConfigContainer.
        if self.get_active_category() == "configs":
            try:
                config_container = self.query_one(ConfigContainer)
                # The container's action returns True if it successfully navigated back.
                if config_container.action_go_back():
                    return  # If it navigated, our work is done.
            except NoMatches:
                pass

        # Fallback: If no other context was handled, focus the main tabs.
        try:
            self.query_one(Tabs).focus()
        except NoMatches:
            pass

    def action_focus_input(self) -> None:
        """Focus the primary input widget of the current view using the new helper method."""
        if (target_widget := self._get_primary_view_widget()):
            target_widget.focus()

    async def action_handle_sort_key(self, key: str) -> None:
        """Handles a key press while in sort mode to apply a specific sort."""
        if not self._sort_mode: return
        target_view = 'history' if self.get_active_category() == 'history' else 'price'
        if key == 'u':
            if target_view == 'price':
                await self._undo_sort()
                self.action_back_or_dismiss()
            return

        column_map = {'d': {'price': 'Description', 'history': 'Date'}, 'p': {'price': 'Price'}, 'c': {'price': 'Change', 'history': 'Close'}, 'e': {'price': '% Change'}, 't': {'price': 'Ticker'}, 'o': {'history': 'Open'}, 'H': {'history': 'High'}, 'L': {'history': 'Low'}, 'v': {'history': 'Volume'},}
        if key not in column_map or target_view not in column_map[key]: return
        
        column_key_str = column_map[key][target_view]
        if target_view == 'history':
            self._set_and_apply_history_sort(column_key_str, f"key '{key}'")
        else:
            self._set_and_apply_sort(column_key_str, f"key '{key}'")
        
        self.action_back_or_dismiss()

    def action_focus_search(self):
        """Activates the search box for the current table view."""
        try:
            self.query_one(SearchBox).focus()
            return
        except NoMatches: pass
        category = self.get_active_category()
        target_id = None
        if category and category not in ['history', 'news', 'configs', 'debug']: target_id = "#price-table"
        elif category == 'debug': target_id = "#debug-table"
        elif category == 'configs':
             # In the new config layout, the target table is in the lists view
            try:
                target_id = "#" + self.query_one(ListsConfigView).query_one(DataTable).id
            except NoMatches:
                target_id = None
        
        if not target_id:
            self.bell(); return
        try:
            table = self.query_one(target_id, DataTable)
            self.search_target_table = table
            self._original_table_data = []
            for row_key, row_data in table.rows.items():
                self._original_table_data.append((row_key, table.get_row(row_key)))
            search_box = SearchBox()
            self.mount(search_box)
            search_box.focus()
        except NoMatches: self.bell()

    @on(Input.Changed, '#search-box')
    def on_search_changed(self, event: Input.Changed):
        """Filters the target table as the user types in the search box."""
        query = event.value
        if not self.search_target_table: return
        from textual.fuzzy import Matcher
        matcher = Matcher(query)
        self.search_target_table.clear()
        if not query:
            for row_key, row_data in self._original_table_data: self.search_target_table.add_row(*row_data, key=row_key.value)
            return
        for row_key, row_data in self._original_table_data:
            searchable_string = " ".join(extract_cell_text(cell) for cell in row_data)
            if matcher.match(searchable_string) > 0: self.search_target_table.add_row(*row_data, key=row_key.value)

    @on(Input.Submitted, '#search-box')
    def on_search_submitted(self, event: Input.Submitted):
        """Removes the search box when the user presses Enter."""
        try: self.query_one(SearchBox).remove()
        except NoMatches: pass
    
    @on(TagFilterChanged)
    def on_tag_filter_changed(self, message: TagFilterChanged) -> None:
        """Handles TagFilterChanged messages from the tag filter widget."""
        logging.info(f"TagFilterChanged message received: {message.tags}")
        self.active_tag_filter = message.tags
        # Set the flag to true so the cursor resets on the upcoming refresh.
        self._is_filter_refresh = True
        # Refresh the current view to apply the new filter.
        # This is now a UI-only operation.
        self._redisplay_price_table()
        # Update filter status after refresh
        self._update_tag_filter_status()
    
    def _redisplay_price_table(self):
        """Re-draws the price table using only data from the in-memory cache.
        
        This method is used for UI-only updates like clearing filters, which should
        be instantaneous and not trigger network requests.
        """
        try:
            dt = self.query_one("#price-table", DataTable)
            active_category = self.get_active_category()
            if not active_category: return

            dt.clear()

            # 1. Get the correctly ordered list of symbols that should be on screen.
            if active_category == 'all':
                seen = set()
                symbols_on_screen = [s['ticker'] for lst in self.config.lists.values() for s in lst if s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols_on_screen = [s['ticker'] for s in self.config.lists.get(active_category, [])]

            ordered_filtered_symbols = self._filter_symbols_by_tags(active_category, symbols_on_screen)

            # 2. Fetch data only from the in-memory cache.
            data_for_table = [market_provider.get_cached_price(s) for s in ordered_filtered_symbols]
            data_for_table = [item for item in data_for_table if item is not None]

            # 3. Render the table.
            if not data_for_table:
                if ordered_filtered_symbols:
                    dt.add_row("[dim]No cached data for symbols in this filter. Press 'r' to refresh.[/dim]")
                else:
                    dt.add_row("[dim]No symbols match the current tag filter.[/dim]")
                return

            alias_map = self._get_alias_map()
            rows = formatter.format_price_data_for_table(data_for_table, self._price_comparison_data, alias_map)
            
            self._style_and_populate_price_table(dt, rows)
            self._apply_price_table_sort()
            
            # Since this is a UI-only refresh, the "Last Refresh" time doesn't change.
            # But we must reset the filter flag.
            self._is_filter_refresh = False

        except NoMatches:
            pass
    #endregion

def show_manual():
    """Displays the help file content using a pager like 'less' if available."""
    help_path = Path(__file__).resolve().parent / "documents" / "help.txt"
    try:
        pager = shutil.which('less')
        if pager:
            subprocess.run([pager, str(help_path)])
        else:
            with open(help_path, 'r') as f:
                print(f.read())
    except FileNotFoundError:
        print(f"Error: Help file not found at {help_path}")
    except Exception as e:
        print(f"An unexpected error occurred while trying to show help: {e}")

def run_cli_output(args: argparse.Namespace):
    """
    Handles fetching and displaying stock data directly to the terminal, bypassing the TUI.
    This function is triggered by the --output flag.
    """
    console = Console()
    app_root = Path(__file__).resolve().parent
    config = ConfigManager(app_root)

    # --- 1. Handle Session Lists ---
    if session_lists := args.session_list:
        for name, tickers in session_lists.items():
            config.lists[name] = [{"ticker": ticker, "alias": ticker, "note": ""} for ticker in tickers]

    # --- 2. Determine and Collect Tickers ---
    target_names = []
    # If -o is used with a value (e.g., 'stocks'), add those to the target list.
    if args.output != 'all':
        target_names.extend([name.strip().lower() for name in args.output.split(',')])
    # Always add session lists to the target if they are provided.
    if args.session_list:
        target_names.extend(args.session_list.keys())

    lists_to_iterate = []
    if not target_names:
        # If no specific or session lists are given, it implies 'all' was intended.
        lists_to_iterate = config.lists.items()
    else:
        # Otherwise, use the collected list of target names (de-duplicated).
        unique_target_names = list(set(target_names))
        lists_to_iterate = [(name, lst) for name, lst in config.lists.items() if name in unique_target_names]
        
    if not lists_to_iterate:
        console.print(f"[bold red]Error:[/] No lists found matching your criteria.")
        return
        
    # FIX: Use an ordered list and a set to preserve order while ensuring uniqueness.
    ordered_tickers = []
    seen_tickers = set()
    alias_map = {}
    for _, list_content in lists_to_iterate:
        for item in list_content:
            ticker = item.get("ticker")
            if ticker and ticker not in seen_tickers:
                ordered_tickers.append(ticker)
                seen_tickers.add(ticker)
                alias_map[ticker] = item.get("alias", ticker)

    if not ordered_tickers:
        console.print("[yellow]No tickers found for the specified lists.[/yellow]")
        return

    # --- 3. Fetch Data using yfinance ---
    with console.status("[bold green]Fetching data...[/]"):
        try:
            ticker_objects = yf.Tickers(" ".join(ordered_tickers))
            all_info = {ticker: ticker_objects.tickers[ticker].info for ticker in ordered_tickers}
        except Exception as e:
            console.print(f"[bold red]Failed to fetch data from API:[/] {e}")
            return

    # --- 4. Format Data for Display ---
    rows = []
    # FIX: Iterate over the ordered list of tickers to build the rows.
    for ticker in ordered_tickers:
        info = all_info.get(ticker)
        if not info or not info.get('currency'):
            rows.append(("Invalid Ticker", None, None, None, "N/A", "N/A", ticker))
            continue

        price = info.get('lastPrice') or info.get('currentPrice') or info.get('regularMarketPrice')
        prev_close = info.get('regularMarketPreviousClose') or info.get('previousClose') or info.get('open')
        change = price - prev_close if price is not None and prev_close is not None else None
        change_percent = (change / prev_close) if change is not None and prev_close != 0 else None
        day_range = f"${info.get('regularMarketDayLow'):,.2f} - ${info.get('regularMarketDayHigh'):,.2f}" if info.get('regularMarketDayLow') and info.get('regularMarketDayHigh') else "N/A"
        wk_range = f"${info.get('fiftyTwoWeekLow'):,.2f} - ${info.get('fiftyTwoWeekHigh'):,.2f}" if info.get('fiftyTwoWeekLow') and info.get('fiftyTwoWeekHigh') else "N/A"
        description = alias_map.get(ticker) or info.get('longName', ticker)
        rows.append((description, price, change, change_percent, day_range, wk_range, ticker))

    # --- 5. Display Data in a Rich Table ---
    table = Table(title="Ticker Overview", show_header=True, header_style="bold magenta")
    table.add_column("Description", style="dim", width=30)
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("% Change", justify="right")
    table.add_column("Day's Range", justify="right")
    table.add_column("52-Wk Range", justify="right")
    table.add_column("Ticker", style="dim")

    for desc, price, change, pct, day_r, wk_r, symbol in rows:
        price_text = f"${price:,.2f}" if price is not None else "N/A"
        style, change_text, pct_text = ("dim", "N/A", "N/A")
        if change is not None and pct is not None:
            if change > 0: style, change_text, pct_text = "green", f"{change:,.2f}", f"+{pct:.2%}"
            elif change < 0: style, change_text, pct_text = "red", f"{change:,.2f}", f"{pct:.2%}"
            else: style, change_text, pct_text = "", "0.00", "0.00%"
        table.add_row(desc, Text(price_text, style="cyan"), Text(change_text, style=style), Text(pct_text, style=style), day_r, wk_r, symbol)

    console.print(table)

def main():
    """The main entry point for the application."""
    dirs = PlatformDirs("stockstui", "andriy-git")
    
    cache_dir = Path(dirs.user_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_file = cache_dir / "stockstui.log"
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s', filename=log_file, filemode='w')
    
    parser = create_arg_parser()
    args = parser.parse_args()

    if args.man:
        show_manual()
        return

    # --- Main Application Router ---
    if args.output:
        # If --output flag is used, run the CLI output and exit.
        run_cli_output(args)
    else:
        # Otherwise, launch the full TUI application.
        app = StocksTUI(cli_overrides=vars(args))
        textual_handler = TextualHandler(app)
        textual_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(message)s')
        textual_handler.setFormatter(formatter)
        logging.getLogger().addHandler(textual_handler)
        app.run()

if __name__ == "__main__":
    main()