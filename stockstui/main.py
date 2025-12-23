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
import webbrowser

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
from textual.widgets.data_table import CellDoesNotExist
from textual.coordinate import Coordinate
from textual.widget import Widget
from textual import on, work, events
from textual.worker import get_current_worker
from rich.text import Text
from rich.style import Style
from textual.color import Color
from platformdirs import PlatformDirs

from stockstui.config_manager import ConfigManager
from stockstui.common import (PriceDataUpdated, NewsDataUpdated,
                              TickerDebugDataUpdated, ListDebugDataUpdated, CacheTestDataUpdated,
                              MarketStatusUpdated, HistoricalDataUpdated, TickerInfoComparisonUpdated,
                              PortfolioChanged, PortfolioDataUpdated, OptionsDataUpdated, OptionsExpirationsUpdated)
from stockstui.data_providers.portfolio import PortfolioManager
from stockstui.ui.widgets.search_box import SearchBox
from stockstui.ui.widgets.tag_filter import TagFilterWidget, TagFilterChanged
from stockstui.ui.quick_edit_ticker_modal import QuickEditTickerModal
# Import the new container instead of the old view
from stockstui.ui.views.config_view import ConfigContainer
from stockstui.ui.views.config_views.general_config_view import GeneralConfigView
from stockstui.ui.views.config_views.lists_config_view import ListsConfigView
from stockstui.ui.views.history_view import HistoryView
from stockstui.ui.views.news_view import NewsView
from stockstui.ui.views.debug_view import DebugView
from stockstui.ui.views.options_view import OptionsView
from stockstui.ui.widgets.navigable_data_table import NavigableDataTable
from stockstui.data_providers import market_provider
from stockstui.data_providers import options_provider
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
        Binding("o", "enter_open_mode", "Open", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("f", "toggle_tag_filter", "Filter", show=True),
        Binding("?", "toggle_help", "Toggle Help", show=True),
        Binding("i", "focus_input", "Input", show=False),
        Binding("enter", "activate_tab", "Activate Tab", show=False),
        Binding("d", "handle_sort_key('d')", "Sort by Description/Date", show=False),
        Binding("p", "handle_sort_key('p')", "Sort by Price", show=False),
        Binding("c", "handle_sort_key('c')", "Sort by Change/Close", show=False),
        Binding("e", "handle_sort_key('e')", "Sort by % Change", show=False),
        Binding("t", "handle_sort_key('t')", "Sort by Ticker", show=False),
        Binding("u", "handle_sort_key('u')", "Undo Sort", show=False),
        Binding("v", "handle_sort_key('v')", "Sort by Volume", show=False),
        Binding("o", "handle_sort_key('o')", "Sort by Open", show=False),
        Binding("ctrl+c", "copy_text", "Copy", show=False),
        Binding("ctrl+C", "copy_text", "Copy", show=False),
        # FIX: Split the bindings. Escape has its own dedicated action.
        Binding("escape,ctrl+[", "dismiss_or_unfocus", "Dismiss / Unfocus", show=False, priority=True),
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
    options_ticker = reactive(None)
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
        
        # Initialize the last_key attribute. This ensures it always exists.
        self.last_key: events.Key | None = None

        # ConfigManager now needs the path to the package root to find default_configs
        self.config = ConfigManager(Path(__file__).resolve().parent)
        self.price_refresh_timer = None
        self.market_status_timer = None
        self._price_comparison_data = {}
        
        # Initialize the database manager for the persistent cache.
        self.db_manager = DbManager(self.config.db_path)
        
        # Initialize the portfolio manager
        self.portfolio_manager = PortfolioManager(self.config)
        
        market_provider.populate_price_cache(self.db_manager.load_price_cache_from_db())
        market_provider.populate_info_cache(self.db_manager.load_info_cache_from_db())
        
        # Internal state management variables
        self._last_refresh_times = {}
        self._available_theme_names = []
        self._processed_themes = {}
        self.theme_variables = {}
        self._original_table_data = []
        self._last_historical_data = None
        self._last_options_data = None
        self.option_positions = self.db_manager.get_all_option_positions()
        self._news_content_for_ticker: str | None = None
        self._last_news_content: tuple[Union[str, Text], list[str]] | None = None
        self._sort_column_key: str | None = None
        self._sort_reverse: bool = False
        self._history_sort_column_key: str | None = None
        self._history_sort_reverse: bool = False
        self._history_period = "1mo"
        self._sort_mode = False
        self._open_mode = False
        self._original_status_text = None
        self._last_active_category: str | None = None
        self._last_config_sub_view: str | None = None
        self._force_config_sub_view: str | None = None  # Used to temporarily force a config view after operations
        self._pre_refresh_cursor_key = None
        self._pre_refresh_cursor_column = None
        self._is_filter_refresh = False

    def add_option_position(self, symbol: str, ticker: str, quantity: float, avg_cost: float):
        """Adds or updates an option position."""
        self.db_manager.save_option_position(symbol, ticker, quantity, avg_cost)
        self.option_positions[symbol] = {
            'symbol': symbol,
            'ticker': ticker,
            'quantity': quantity,
            'avg_cost': avg_cost
        }
        self.notify(f"Position saved: {symbol}")

    def remove_option_position(self, symbol: str):
        """Removes an option position."""
        self.db_manager.delete_option_position(symbol)
        if symbol in self.option_positions:
            del self.option_positions[symbol]
        self.notify(f"Position removed: {symbol}")
        self._pre_refresh_cursor_key = None
        self._pre_refresh_cursor_column = None
        self._is_filter_refresh = False

        # --- Handle CLI Overrides ---
        if session_lists := self.cli_overrides.get('session_list'):
            for name, tickers in session_lists.items():
                self.config.lists[name] = [
                    {"ticker": ticker, "alias": ticker, "note": ""} for ticker in tickers
                ]

        self._setup_dynamic_tabs()
        
        # Move theme registration to __init__ to prevent race conditions.
        self._load_and_register_themes()

    def compose(self) -> ComposeResult:
        """
        Creates the static layout of the application.
        """
        with Vertical(id="app-body"):
            yield Tabs(id="tabs-container")
            with Container(id="app-grid"):
                yield Container(id="output-container")
                yield ConfigContainer(id="config-container")
            with Horizontal(id="status-bar-container"):
                yield Label("Market Status: Unknown", id="market-status")
                yield Label("Last Refresh: Never", id="last-refresh-time")
        yield Footer()

    
    def on_mount(self) -> None:
        """
        Called when the app is first mounted.
        """
        logging.info("Application mounting.")
        
        # Ensure themes are registered - safety check in case __init__ didn't complete
        if not self._available_theme_names:
            self._load_and_register_themes()
        
        default_theme = "gruvbox_soft_dark"
        active_theme = self.config.get_setting("theme", default_theme)

        # If the theme from settings doesn't exist, fall back to default
        # and notify the user. This prevents crashes from a bad config.
        if active_theme not in self._available_theme_names:
            self.notify(
                f"Theme '{active_theme}' not found. Falling back to default.",
                title="Theme Error",
                severity="warning"
            )
            logging.warning(f"Configured theme '{active_theme}' not found. Falling back to '{default_theme}'.")
            active_theme = default_theme
        
        self.theme = active_theme
        self._update_theme_variables(active_theme)
        
        config_container = self.query_one(ConfigContainer)
        general_view = config_container.query_one(GeneralConfigView)
        general_view.query_one("#theme-select", Select).set_options([(t, t) for t in self._available_theme_names])
        general_view.query_one("#theme-select", Select).value = active_theme
        general_view.query_one("#auto-refresh-switch", Switch).value = self.config.get_setting("auto_refresh", False)
        general_view.query_one("#refresh-interval-input", Input).value = str(self.config.get_setting("refresh_interval", 300.0))
        general_view.query_one("#market-calendar-select", Select).value = self.config.get_setting("market_calendar", "NYSE")

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
            elif cli_options := self.cli_overrides.get('options'):
                start_category = 'options'
                if isinstance(cli_options, str): self.options_ticker = cli_options
            elif self.cli_overrides.get('debug'):
                start_category = 'debug'
            elif self.cli_overrides.get('configs'):
                start_category = 'configs'
            elif session_lists := self.cli_overrides.get('session_list'):
                start_category = next(iter(session_lists))
        
        if self.cli_overrides.get('period'):
            self._history_period = self.cli_overrides['period']

        self.call_after_refresh(self._rebuild_app, new_active_category=start_category)
        self.call_after_refresh(self._start_refresh_loops)
        
    def on_unmount(self) -> None:
        """
        Clean up background tasks and save all caches to the database on exit.
        """
        if self.price_refresh_timer: self.price_refresh_timer.stop()
        if self.market_status_timer: self.market_status_timer.stop()
        
        self.db_manager.save_price_cache_to_db(market_provider.get_price_cache_state())
        self.db_manager.save_info_cache_to_db(market_provider.get_info_cache_state())
        self.db_manager.close()
        
        self.workers.cancel_all()

    #region Event Handlers & Actions
    @on(events.Key)
    async def on_key(self, event: events.Key) -> None:
        """Track the last key pressed for use in contextual actions."""
        # Update the last_key attribute on every key press.
        self.last_key = event
        
        # Contextual handling for Open Mode keys
        # We removed global bindings for these to prevent conflicts (specifically 'h')
        if self._open_mode and event.key in ("n", "h", "y"):
            await self.action_handle_open_key(event.key)
            event.stop()

    def action_dismiss_or_unfocus(self) -> None:
        """
        Dedicated action for the Escape key. It will always unfocus an Input
        widget if one is focused. Otherwise, it will delegate to the standard
        back/dismiss logic. This prevents reliance on stored key state.
        """
        try:
            # If the focused widget is an Input, its primary escape behavior is to unfocus.
            if isinstance(self.focused, Input):
                self.focused.blur()
                return
            
            # If not an Input, perform the regular back/dismiss action.
            self.action_back_or_dismiss()
        except Exception as e:
            # Be forgiving in actions; log errors but don't crash.
            logging.error(f"Error in dismiss_or_unfocus: {e}")

    def action_back_or_dismiss(self) -> None:
        """
        Handles 'back' and 'dismiss' actions, primarily for the 'backspace' key.
        """
        # FIX: Harden this check with getattr as a safeguard, although splitting the
        # bindings makes it much less likely to be needed.
        if isinstance(self.focused, Input):
            last_key = getattr(self, "last_key", None)
            if last_key is not None and getattr(last_key, "key", None) != "escape":
                return

        # Priority 1: Clear sort or open mode if active.
        if self._sort_mode:
            self._sort_mode = False
            self._restore_status_label()
            return
        if self._open_mode:
            self._open_mode = False
            self._restore_status_label()
            return

        # Priority 2: Dismiss the search box if it's active.
        try:
            self.query_one(SearchBox).remove()
            self._original_table_data = []
            return
        except NoMatches:
            pass

        # Priority 3: If inside the config container, try to navigate back to the main config view.
        try:
            config_container = self.query_one(ConfigContainer)
            # The container's action returns True if it successfully navigated back.
            if config_container.action_go_back():
                return
        except NoMatches:
            pass

        # Fallback: If no other context was handled, focus the main tabs.
        try:
            self.query_one(Tabs).focus()
        except NoMatches:
            pass

    def _restore_status_label(self) -> None:
        """Restores the original status label text."""
        try:
            status_label = self.query_one("#last-refresh-time", Label)
            if self._original_status_text is not None:
                status_label.update(self._original_status_text)
        except NoMatches:
            pass

    #endregion

    #region UI and App State Management
    def _start_refresh_loops(self) -> None:
        """Kicks off the independent refresh cycles for prices and market status."""
        self.action_refresh()
        self._manage_price_refresh_timer()

        calendar = self.config.get_setting("market_calendar", "NYSE")
        try:
            initial_status = market_provider.get_market_status(calendar)
            self._update_market_status_display(initial_status)
        except Exception as e:
            logging.error(f"Initial market status fetch failed: {e}")

    def _get_alias_map(self) -> dict[str, str]:
        """Creates a mapping from ticker symbol to its user-defined alias."""
        alias_map = {}
        hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
        for list_name, list_data in self.config.lists.items():
            if list_name not in hidden_tabs:
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
            # Only include non-hidden lists when showing 'all' category
            hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
            for list_name, list_data in self.config.lists.items():
                if list_name not in hidden_tabs:
                    lists_to_check.append(list_data)
        elif category in self.config.lists:
            # If this specific category is hidden, don't include tags from it
            hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
            if category not in hidden_tabs:
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
            return symbols
        
        seen_symbols = set()
        ordered_filtered_symbols = []
        
        lists_to_check = []
        if category == 'all':
            # Only include non-hidden lists when showing 'all' category
            hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
            for list_name, list_data in self.config.lists.items():
                if list_name not in hidden_tabs:
                    lists_to_check.append(list_data)
        elif category in self.config.lists:
            # If this specific category is hidden, don't include it in filtering
            hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
            if category not in hidden_tabs:
                lists_to_check.append(self.config.lists.get(category, []))

        for list_data in lists_to_check:
            for item in list_data:
                ticker = item.get('ticker')
                if ticker in symbols and ticker not in seen_symbols:
                    item_tags_str = item.get('tags', '')
                    item_tags = parse_tags(item_tags_str) if item_tags_str else []
                    if match_tags(item_tags, self.active_tag_filter):
                        ordered_filtered_symbols.append(ticker)
                    seen_symbols.add(ticker)

        logging.info(f"Filtered symbols (ordered): {ordered_filtered_symbols}")
        
        return ordered_filtered_symbols

    def _update_tag_filter_status(self) -> None:
        """Updates the tag filter status display with current counts."""
        try:
            tag_filter = self.query_one("#tag-filter")
            category = self.get_active_category()
            
            if category and category not in ["history", "news", "options", "debug", "configs"]:
                if category == 'all':
                    hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                    total_symbols = list(set(s['ticker'] for list_name, lst in self.config.lists.items() for s in lst if list_name not in hidden_tabs))
                else:
                    # Check if this specific category is hidden
                    hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                    if category not in hidden_tabs:
                        total_symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
                    else:
                        # If category is hidden, no symbols should be available
                        total_symbols = []
                
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
                resolved_theme_dict = copy.deepcopy(BASE_THEME_STRUCTURE)
                resolved_theme_dict = substitute_colors(resolved_theme_dict, palette)
                resolved_theme_dict['dark'] = theme_data.get('dark', False)
                
                resolved_json = json.dumps(resolved_theme_dict)
                if "UNDEFINED_" in resolved_json:
                    raise ValueError(f"Theme '{name}' is missing one or more required color definitions in its palette.")

                self.register_theme(Theme(name=name, **resolved_theme_dict))
                valid_themes[name] = resolved_theme_dict
            except Exception as e:
                # Can't use self.notify here as the app isn't fully mounted yet.
                logging.error(f"Theme '{name}' failed to load: {e}")
        
        self._processed_themes = valid_themes
        self._available_theme_names = sorted(list(valid_themes.keys()))

    def _update_theme_variables(self, theme_name: str):
        """
        Updates the internal theme variable snapshot for programmatic styling.
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
        Generates the list of tabs to be displayed based on user configuration.
        """
        self.tab_map = []
        hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
        
        all_list_categories = list(self.config.lists.keys())
        all_possible_categories = ["all"] + all_list_categories + ["history", "news", "options", "debug"]
        
        for category in all_possible_categories:
            if category not in hidden_tabs:
                self.tab_map.append({'name': category.replace("_", " ").capitalize(), 'category': category})
        self.tab_map.append({'name': "Configs", 'category': 'configs'})

    async def _rebuild_app(self, new_active_category: str | None = None, config_sub_view: str | None = None):
        """
        Rebuilds dynamic parts of the UI, primarily the tabs and config screen widgets.
        """
        self._setup_dynamic_tabs()
        tabs_widget = self.query_one(Tabs)
        current_active_cat = new_active_category or self.get_active_category()
        await tabs_widget.clear()
        
        for i, tab_data in enumerate(self.tab_map, start=1):
            await tabs_widget.add_tab(Tab(f"{i}: {tab_data['name']}", id=f"tab-{i}"))
        self._update_tab_bindings()
        
        try:
            idx_to_activate = next(i for i, t in enumerate(self.tab_map, start=1) if t['category'] == current_active_cat)
        except (StopIteration, NoMatches):
            default_cat = self.config.get_setting("default_tab_category", "all")
            try:
                idx_to_activate = next(i for i, t in enumerate(self.tab_map, start=1) if t['category'] == default_cat)
            except (StopIteration, NoMatches):
                idx_to_activate = 1
        
        if tabs_widget.tab_count >= idx_to_activate:
            tabs_widget.active = f"tab-{idx_to_activate}"

        if current_active_cat == 'configs' and config_sub_view:
            config_container = self.query_one(ConfigContainer)
            view_map = {
                "lists": config_container.show_lists,
                "general": config_container.show_general,
                "portfolios": config_container.show_portfolios,
            }
            show_method = view_map.get(config_sub_view)
            if show_method:
                show_method()
            # Temporarily force this config sub-view after the operation
            self._force_config_sub_view = config_sub_view
        elif current_active_cat == 'configs':
            # If we're going to configs but no sub-view was specified, try to restore the last one
            config_container = self.query_one(ConfigContainer)
            if self._last_config_sub_view:
                view_map = {
                    "lists": config_container.show_lists,
                    "general": config_container.show_general,
                    "portfolios": config_container.show_portfolios,
                }
                show_method = view_map.get(self._last_config_sub_view)
                if show_method:
                    show_method()
        
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
        
        # Refresh visible tabs list
        general_view.repopulate_visible_tabs()
            
        self.query_one(ListsConfigView).repopulate_lists()

    def get_active_category(self) -> str | None:
        """Returns the category string of the currently active tab."""
        try:
            active_tab_id = self.query_one(Tabs).active
            if active_tab_id:
                return self.tab_map[int(active_tab_id.split('-')[1]) - 1]['category']
        except (NoMatches, IndexError, ValueError):
            return None
            
    def _update_tab_bindings(self):
        """Binds number keys to select tabs."""
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
        """Starts or stops the auto-refresh timer for prices based on config."""
        if self.price_refresh_timer:
            self.price_refresh_timer.stop()
            self.price_refresh_timer = None
        if self.config.get_setting("auto_refresh", False):
            try:
                interval = float(self.config.get_setting("refresh_interval", 300.0))
                self.price_refresh_timer = self.set_interval(interval, lambda: self.action_refresh(force=False))
                logging.info(f"Auto-refresh timer started with interval of {interval} seconds.")
            except (ValueError, TypeError):
                logging.error("Invalid refresh interval.")
        else:
            logging.info("Auto-refresh is disabled.")
    
    def _schedule_next_market_status_refresh(self, status: dict):
        """
        Calculates the next poll interval for the market status and sets a timer.
        """
        if self.market_status_timer:
            self.market_status_timer.stop()

        now = datetime.now(timezone.utc)
        next_open = status.get('next_open')
        next_close = status.get('next_close')
        current_status = status.get('status')

        interval = 300.0

        if current_status == 'open' and next_close:
            time_to_close = (next_close - now).total_seconds()
            if time_to_close <= 900:
                interval = 30
            else:
                interval = 300
        elif current_status == 'closed' and next_open:
            time_to_open = (next_open - now).total_seconds()
            if 0 < time_to_open <= 900:
                interval = 30
            elif 900 < time_to_open <= 3600 * 2:
                interval = 300
            else:
                interval = 3600

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
        """
        category = self.get_active_category()
        if category and category not in ["history", "news", "options", "debug", "configs"]:
            if category == 'all':
                seen = set()
                hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                symbols = [s['ticker'] for list_name, lst in self.config.lists.items() for s in lst if list_name not in hidden_tabs and s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
            
            logging.info("Applying tag filter")

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
        if category and category in ["history", "news", "options", "debug", "configs"]:
            self.bell()
            return

        try:
            tag_filter = self.query_one("#tag-filter", TagFilterWidget)
            if not tag_filter.available_tags:
                self.notify("No tags available for this list.", severity="information")
                self.bell()
                return

            tag_filter.display = not tag_filter.display
            if tag_filter.display:
                try:
                    first_button = tag_filter.query_one(".tag-button", Button)
                    first_button.focus()
                except NoMatches:
                    pass
        except NoMatches:
            self.bell()

    def action_move_cursor(self, direction: str) -> None:
        """
        Handles unified hjkl/arrow key navigation.
        """
        if self.focused and (isinstance(self.focused, Tabs) or isinstance(self.focused, Tab)):
            tabs = self.focused if isinstance(self.focused, Tabs) else self.focused.query_ancestor(Tabs)
            if direction == 'left': tabs.action_previous_tab()
            elif direction == 'right': tabs.action_next_tab()
            return

        if self.focused and hasattr(self.focused, f"action_cursor_{direction}"):
            getattr(self.focused, f"action_cursor_{direction}")()
            return

        if direction in ("up", "down"):
            if (scrollable := self._get_active_scrollable_widget()):
                if direction == "up": scrollable.scroll_up(duration=0.5)
                else: scrollable.scroll_down(duration=0.5)

    def _get_primary_view_widget(self) -> Widget | None:
        """
        Gets the primary *focusable* widget for the currently active view.
        """
        category = self.get_active_category()
        target_id = None
        
        if category == 'history':
            target_id = '#history-ticker-input'
        elif category == 'news':
            target_id = '#news-ticker-input'
        elif category == 'options':
            target_id = '#options-ticker-input'
        elif category == 'configs':
            target_id = '#config-container'
        elif category == 'debug':
            target_id = '#debug-table'
        elif category and category not in ['history', 'news', 'configs', 'debug']:
            target_id = '#price-table'

        if target_id:
            try:
                return self.query_one(target_id)
            except NoMatches:
                pass
        return None
    
    def _get_active_scrollable_widget(self) -> Container | None:
        """
        Determines the currently visible main container that should be scrolled.
        """
        primary_widget = self._get_primary_view_widget()
        if not primary_widget:
            return None

        category = self.get_active_category()
        if category == 'configs':
            return self.query_one("#config-container")
        
        output_container = self.query_one('#output-container')
        
        if category == 'news':
            return output_container.query_one('#news-output-display')
        elif category == 'history':
            return output_container.query_one('#history-display-container')
        else:
            return output_container
    
    async def _display_data_for_category(self, category: str):
        """
        Renders the main content area based on the selected tab's category.
        """
        output_container = self.query_one("#output-container")
        config_container = self.query_one("#config-container")
        await output_container.remove_children()

        is_config_tab = category == "configs"
        config_container.display = is_config_tab
        output_container.display = not is_config_tab
        self.query_one("#status-bar-container").display = not is_config_tab
        if is_config_tab:
            # Check if we need to force a specific config view (e.g., after an operation)
            # This is used temporarily to maintain context after operations like adding/deleting lists
            if self._force_config_sub_view:
                # Use the forced config view and then clear the flag so it doesn't persist
                view_map = {
                    "lists": config_container.show_lists,
                    "general": config_container.show_general,
                    "portfolios": config_container.show_portfolios,
                }
                show_method = view_map.get(self._force_config_sub_view)
                if show_method:
                    show_method()
                # Clear the force flag so it doesn't affect subsequent navigation
                self._force_config_sub_view = None
            else:
                # Otherwise, check the current view in the container to preserve user navigation
                current_config_view = config_container.query_one("ContentSwitcher").current
                if current_config_view == "main":
                    config_container.show_main()
                elif current_config_view == "general":
                    config_container.show_general()
                elif current_config_view == "lists":
                    config_container.show_lists()
                elif current_config_view == "portfolios":
                    config_container.show_portfolios()
                else:
                    config_container.show_main()
            return

        if category == 'history':
            await output_container.mount(HistoryView())
        elif category == 'news':
            await output_container.mount(NewsView())
        elif category == 'options':
            await output_container.mount(OptionsView())
        elif category == 'debug':
            await output_container.mount(DebugView())
        else:
            if category not in ["history", "news", "options", "debug", "configs"]:
                available_tags = self._get_available_tags_for_category(category)
                tag_filter = TagFilterWidget(available_tags=available_tags, id="tag-filter")
                tag_filter.display = False
                await output_container.mount(tag_filter)

            await output_container.mount(NavigableDataTable(id="price-table", zebra_stripes=True))

            price_table = self.query_one("#price-table", NavigableDataTable)
            
            column_settings = self.config.get_setting("column_settings", [])
            # Fallback defaults if empty
            if not column_settings:
                column_settings = [
                    {"key": "Ticker", "visible": True},
                    {"key": "Description", "visible": True},
                    {"key": "Price", "visible": True},
                    {"key": "Change", "visible": True},
                    {"key": "% Change", "visible": True},
                    {"key": "Day's Range", "visible": True},
                    {"key": "52-Wk Range", "visible": True},
                ]

            for col in column_settings:
                if not isinstance(col, dict): continue
                if col.get('visible', True):
                    price_table.add_column(col['key'], key=col['key'])
            
            if category == 'all':
                seen = set()
                hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                symbols = [s['ticker'] for list_name, lst in self.config.lists.items() for s in lst if list_name not in hidden_tabs and s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols = [s['ticker'] for s in self.config.lists.get(category, [])]
            
            symbols = self._filter_symbols_by_tags(category, symbols)
            
            if symbols and not any(market_provider.is_cached(s) for s in symbols):
                price_table.loading = True
                self.fetch_prices(symbols, force=False, category=category)
            elif symbols:
                data_map = {item['symbol']: item for s in symbols if (item := market_provider.get_cached_price(s))}
                cached_data = [data_map[s] for s in symbols if s in data_map]
                
                if cached_data:
                    alias_map = self._get_alias_map()
                    self._price_comparison_data = {item.get('symbol'): item.get('price') for item in cached_data if item.get('price') is not None}
                    rows = formatter.format_price_data_for_table(cached_data, self._price_comparison_data, alias_map)
                    self._style_and_populate_price_table(price_table, rows)
                    self._apply_price_table_sort()
                else:
                    price_table.loading = True
                    self.fetch_prices(symbols, force=False, category=category)
            else:
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
    def fetch_options_expirations(self, ticker: str):
        """Worker to fetch available expiration dates for a ticker's options."""
        try:
            expirations = options_provider.get_available_expirations(ticker)
            if not get_current_worker().is_cancelled:
                self.post_message(OptionsExpirationsUpdated(ticker, expirations or ()))
        except Exception as e:
            logging.error(f"Worker fetch_options_expirations failed for {ticker}: {e}")
            if not get_current_worker().is_cancelled:
                self.post_message(OptionsExpirationsUpdated(ticker, ()))

    @work(exclusive=True, thread=True)
    def fetch_options_chain(self, ticker: str, expiration: str):
        """Worker to fetch options chain data for a ticker and expiration date."""
        try:
            options_data = options_provider.get_options_chain(ticker, expiration)
            if not get_current_worker().is_cancelled:
                if options_data:
                    self.post_message(OptionsDataUpdated(
                        ticker, expiration,
                        options_data.get('calls'),
                        options_data.get('puts'),
                        options_data.get('underlying')
                    ))
                else:
                    # Post error
                    self._last_options_data = {'error': f'Could not fetch options data for {ticker}'}
        except Exception as e:
            logging.error(f"Worker fetch_options_chain failed for {ticker} expiring {expiration}: {e}")
            if not get_current_worker().is_cancelled:
                self._last_options_data = {'error': str(e)}

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

    def _style_and_populate_price_table(self, price_table: DataTable, rows: list[dict]):
        """
        Applies dynamic styling and populates the main price table.
        """
        price_color = self.theme_variables.get("price", "cyan")
        success_color = self.theme_variables.get("success", "green")
        error_color = self.theme_variables.get("error", "red")
        muted_color = self.theme_variables.get("text-muted", "dim")

        column_settings = self.config.get_setting("column_settings", [])
        if not column_settings:
             column_settings = [
                {"key": "Ticker", "visible": True},
                {"key": "Description", "visible": True},
                {"key": "Price", "visible": True},
                {"key": "Change", "visible": True},
                {"key": "% Change", "visible": True},
                {"key": "Day's Range", "visible": True},
                {"key": "52-Wk Range", "visible": True},
                {"key": "All Time High", "visible": True},
                {"key": "% Off ATH", "visible": True},
            ]
        
        visible_columns = [c['key'] for c in column_settings if isinstance(c, dict) and c.get('visible', True)]

        for row_data in rows:
            row_values = []
            symbol = row_data.get("Ticker")
            change_direction = row_data.get("_change_direction")
            
            for col_key in visible_columns:
                val = row_data.get(col_key)
                
                if col_key == "Description":
                    if val == 'Invalid Ticker': text = Text(str(val), style=error_color)
                    elif val == 'N/A': text = Text(str(val), style=muted_color)
                    else: text = Text(str(val))
                elif col_key == "Price":
                    raw_price = val
                    text = Text(f"${raw_price:,.2f}", style=price_color, justify="right") if raw_price is not None else Text("N/A", style=muted_color, justify="right")
                elif col_key == "Change":
                    raw_change = val
                    if raw_change is not None:
                        style = success_color if raw_change > 0 else (error_color if raw_change < 0 else "")
                        text = Text(f"{raw_change:,.2f}", style=style, justify="right")
                    else:
                        text = Text("N/A", style=muted_color, justify="right")
                elif col_key == "% Change":
                    raw_pct = val
                    if raw_pct is not None:
                        style = success_color if raw_pct > 0 else (error_color if raw_pct < 0 else "")
                        text = Text(f"{raw_pct:.2%}", style=style, justify="right")
                    else:
                        text = Text("N/A", style=muted_color, justify="right")
                elif col_key == "All Time High":
                    raw_ath = val
                    text = Text(f"${raw_ath:,.2f}", style=price_color, justify="right") if raw_ath is not None else Text("N/A", style=muted_color, justify="right")
                elif col_key == "% Off ATH":
                    raw_pct = val
                    if raw_pct is not None:
                        style = error_color if raw_pct < 0 else (success_color if raw_pct > 0 else "")
                        text = Text(f"{raw_pct:.2%}", style=style, justify="right")
                    else:
                        text = Text("N/A", style=muted_color, justify="right")
                elif col_key in ["Volume", "Open", "Prev Close", "Day's Range", "52-Wk Range"]:
                    text = Text(str(val), style=muted_color if val == "N/A" else "", justify="right")
                elif col_key == "Ticker":
                    text = Text(str(val), style=muted_color)
                else:
                    text = Text(str(val))
                
                row_values.append(text)
            
            price_table.add_row(*row_values, key=symbol)
            
            if change_direction:
                if "Change" in visible_columns:
                    self.flash_cell(symbol, "Change", "positive" if change_direction == 'up' else "negative")
                if "% Change" in visible_columns:
                    self.flash_cell(symbol, "% Change", "positive" if change_direction == 'up' else "negative")

    @on(PriceDataUpdated)
    async def on_price_data_updated(self, message: PriceDataUpdated):
        """Handles the arrival of new price data from a worker."""
        now_str = f"Last Refresh: {datetime.now():%H:%M:%S}"
        if message.category == 'all':
            for cat in list(self.config.lists.keys()) + ['all']:
                self._last_refresh_times[cat] = now_str
        else:
            self._last_refresh_times[message.category] = now_str
        
        active_category = self.get_active_category()
        is_relevant = (active_category == message.category) or (message.category == 'all' and active_category not in ['history', 'news', 'options', 'debug', 'configs'])
        if not is_relevant: return

        try:
            dt = self.query_one("#price-table", DataTable)
            
            self._pre_refresh_cursor_key = None
            self._pre_refresh_cursor_column = None
            if not self._is_filter_refresh and dt.row_count > 0 and dt.cursor_row >= 0:
                try:
                    coordinate = Coordinate(row=dt.cursor_row, column=0)
                    self._pre_refresh_cursor_key = dt.coordinate_to_cell_key(coordinate).row_key
                    self._pre_refresh_cursor_column = dt.cursor_column
                except CellDoesNotExist:
                    self._pre_refresh_cursor_key = None
                    self._pre_refresh_cursor_column = None

            dt.loading = False
            dt.clear()
            
            if active_category == 'all':
                seen = set()
                hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                symbols_on_screen = [s['ticker'] for list_name, lst in self.config.lists.items() for s in lst if list_name not in hidden_tabs and s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols_on_screen = [s['ticker'] for s in self.config.lists.get(active_category, [])]

            ordered_filtered_symbols = self._filter_symbols_by_tags(active_category, symbols_on_screen)

            data_map = {item['symbol']: item for item in message.data}

            data_for_table = [data_map[symbol] for symbol in ordered_filtered_symbols if symbol in data_map]

            if not data_for_table:
                if ordered_filtered_symbols:
                    dt.add_row("[dim]Could not fetch data for any symbols in this list.[/dim]")
                elif symbols_on_screen and not ordered_filtered_symbols:
                    dt.add_row("[dim]No symbols match the current tag filter.[/dim]")
                else:
                    dt.add_row(f"[dim]No symbols in list '{active_category}'. Add some in the Configs tab.[/dim]")
                return

            alias_map = self._get_alias_map()
            rows = formatter.format_price_data_for_table(data_for_table, self._price_comparison_data, alias_map)
            
            self._style_and_populate_price_table(dt, rows)
            
            self._price_comparison_data = {
                item['symbol']: item.get('price')
                for item in data_for_table
                if item.get('price') is not None
            }
            
            self._apply_price_table_sort()
            self.query_one("#last-refresh-time").update(now_str)

            if self._pre_refresh_cursor_key:
                try:
                    new_row_index = dt.get_row_index(self._pre_refresh_cursor_key)
                    if self._pre_refresh_cursor_column is not None:
                        dt.move_cursor(row=new_row_index, column=self._pre_refresh_cursor_column)
                    else:
                        dt.move_cursor(row=new_row_index)
                except KeyError:
                    pass
            
            self._is_filter_refresh = False

        except NoMatches: pass
    
    def _update_market_status_display(self, status_data: dict):
        """
        Formats and displays the market status.
        """
        try:
            format_result = formatter.format_market_status(status_data)
            if not format_result:
                self.query_one("#market-status").update(Text("Market: Unknown", style="dim"))
                return

            base_text, parts = format_result
            
            assembled_text = Text.from_markup(base_text)
            for text, style_var in parts:
                style = self.theme_variables.get(style_var, "")
                assembled_text.append(text, style=style)

            self.query_one("#market-status").update(assembled_text)
            self._schedule_next_market_status_refresh(status_data)
        except NoMatches:
            pass

    @on(MarketStatusUpdated)
    async def on_market_status_updated(self, message: MarketStatusUpdated):
        """Handles the arrival of new market status data from a worker."""
        self._update_market_status_display(message.status)

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

    @on(OptionsExpirationsUpdated)
    async def on_options_expirations_updated(self, message: OptionsExpirationsUpdated):
        """Handles arrival of options expiration dates, populates the expiration selector."""
        if self.get_active_category() != 'options' or self.options_ticker != message.ticker:
            return
        
        try:
            options_view = self.query_one(OptionsView)
            options_view.update_expirations(message.expirations or [])
        except NoMatches:
            pass

    @on(OptionsDataUpdated)
    async def on_options_data_updated(self, message: OptionsDataUpdated):
        """Handles arrival of options chain data, tells the options view to render it."""
        try:
            self.query_one("#options-display-container").loading = False
        except NoMatches:
            return

        self._last_options_data = {
            'ticker': message.ticker,
            'expiration': message.expiration,
            'calls': message.calls_data,
            'puts': message.puts_data,
            'underlying': message.underlying
        }
        
        try:
            options_view = self.query_one(OptionsView)
            await options_view._render_options_data()
        except NoMatches:
            pass

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
        except (KeyError, NoMatches, CellDoesNotExist):
            pass
    
    @on(Tabs.TabActivated)
    async def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        """Handles tab switching. Resets sort state and displays new content."""
        new_category = self.get_active_category()
        if new_category == self._last_active_category:
            return

        try:
            self.query_one(SearchBox).remove()
            self._original_table_data = []
        except NoMatches:
            pass

        self._sort_column_key = None; self._sort_reverse = False
        self._history_sort_column_key = None; self._history_sort_reverse = False
        
        if new_category:
            await self._display_data_for_category(new_category)

        self.action_refresh()

        try:
            status_label = self.query_one("#last-refresh-time")
            if new_category in ['history', 'news', 'options', 'debug', 'configs']:
                status_label.update("")
        except NoMatches:
            pass

        # If we're leaving the configs tab, maintain the sub-view so we return to the same view
        # Only clear the config sub-view when going to completely different UI modes
        if new_category not in ['history', 'news', 'options', 'debug'] and self._last_active_category == 'configs':
            # We're leaving configs, but not going to a special mode like history/news/debug
            # Keep the last config sub-view so we return to it if we come back to configs
            pass
        elif new_category in ['history', 'news', 'debug']:
            # We're going to a different type of view, so clear the config sub-view
            # This ensures that if we later go back to configs, we start from main
            self._last_config_sub_view = None

        self._last_active_category = new_category
        
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
        # We allow sorting on any column that is clicked
        
        if self._sort_column_key == column_key_str:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column_key = column_key_str
            # Default to descending for numeric columns
            numeric_columns = {"Price", "Change", "% Change", "Volume", "Open", "Prev Close"}
            self._sort_reverse = column_key_str in numeric_columns
            
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

    def action_focus_input(self) -> None:
        """Focus the primary input widget of the current view using the new helper method."""
        if (target_widget := self._get_primary_view_widget()):
            target_widget.focus()

    def action_activate_tab(self) -> None:
        """When Enter is pressed on Tabs, focus the primary widget of the active tab."""
        # Only activate if Tabs currently has focus
        if self.focused and isinstance(self.focused, Tabs):
            if (target_widget := self._get_primary_view_widget()):
                target_widget.focus()

    async def action_enter_open_mode(self) -> None:
        """Enters 'open mode', or if already in open mode, opens the ticker in Options."""
        # If already in open mode, treat this as 'open in options'
        if self._open_mode:
            await self.action_handle_open_key('o')
            return
            
        category = self.get_active_category()
        
        # Only activate open mode for price table views
        if category and category not in ['news', 'history', 'options', 'debug', 'configs']:
            try:
                # Check if a row is selected
                price_table = self.query_one("#price-table", NavigableDataTable)
                if price_table.cursor_row >= 0:
                    self._open_mode = True
                    status_label = self.query_one("#last-refresh-time", Label)
                    self._original_status_text = status_label.renderable
                    status_label.update("OPEN IN: \\[n]ews, \\[h]istory, \\[o]ptions, \\[y]ahoo Finance, \\[ESC]ape")
                else:
                    self.bell()
            except NoMatches:
                self.bell()
        else:
            self.bell()

    async def action_handle_open_key(self, key: str) -> None:
        """Handles a key press while in open mode to navigate to a different view."""
        if not self._open_mode: return
        
        try:
            price_table = self.query_one("#price-table", NavigableDataTable)
            if price_table.cursor_row < 0:
                self.action_back_or_dismiss()
                return
                
            # Get the ticker from the row key (same as edit command does)
            coordinate = Coordinate(row=price_table.cursor_row, column=0)
            ticker = price_table.coordinate_to_cell_key(coordinate).row_key.value
            
            if not ticker:
                self.action_back_or_dismiss()
                return
            
            # Find the tab index for the target category
            target_category = None
            if key == 'n':  # News
                target_category = 'news'
                self.news_ticker = ticker
            elif key == 'h':  # History
                target_category = 'history'
                self.history_ticker = ticker
            elif key == 'o':  # Options
                target_category = 'options'
                self.options_ticker = ticker
            elif key == 'y':  # Yahoo Finance
                # Open Yahoo Finance page for the ticker
                yahoo_url = f"https://finance.yahoo.com/quote/{ticker}"
                try:
                    self.notify(f"Opening Yahoo Finance for {ticker}...")
                    webbrowser.open(yahoo_url)
                except webbrowser.Error:
                    self.notify("No web browser found. Please configure your system's default browser.", severity="error", timeout=8)
                except Exception as e:
                    self.notify(f"Failed to open browser: {e}", severity="error")
                # Exit open mode after opening
                self.action_back_or_dismiss()
                return
            
            if target_category:
                # Find the tab ID for this category
                try:
                    idx = next(i for i, t in enumerate(self.tab_map, start=1) if t['category'] == target_category)
                    tabs = self.query_one(Tabs)
                    tabs.active = f"tab-{idx}"
                except (StopIteration, NoMatches):
                    self.notify(f"Tab '{target_category}' not found", severity="error")
            
            # Exit open mode
            self.action_back_or_dismiss()
            
        except (NoMatches, IndexError):
            self.action_back_or_dismiss()

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
    
    def action_edit_ticker_quick(self) -> None:
        """Opens a quick edit modal for the currently selected ticker."""
        # Only allow when not in sort mode
        if self._sort_mode:
            return
        
        category = self.get_active_category()
        # Only work on ticker list tabs, not special views
        if not category or category in ['history', 'news', 'options', 'debug', 'configs']:
            self.bell()
            return
        
        try:
            price_table = self.query_one("#price-table", DataTable)
            if price_table.cursor_row < 0:
                self.notify("Select a ticker to edit.", severity="warning")
                return
            
            # Get the ticker symbol from the row key (not from a column, as column order is configurable)
            coordinate = Coordinate(row=price_table.cursor_row, column=0)
            ticker = price_table.coordinate_to_cell_key(coordinate).row_key.value
            
            # Find the ticker in the config to get current values
            ticker_data = None
            list_names = []
            
            # Check if this is the 'all' category
            if category == 'all':
                hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                for list_name, list_data in self.config.lists.items():
                    if list_name not in hidden_tabs:
                        for item in list_data:
                            if item.get('ticker', '').upper() == ticker.upper():
                                if ticker_data is None:
                                    ticker_data = item.copy()
                                list_names.append(list_name)
                                break
            else:
                # Single list category
                list_data = self.config.lists.get(category, [])
                for item in list_data:
                    if item.get('ticker', '').upper() == ticker.upper():
                        ticker_data = item.copy()
                        list_names.append(category)
                        break
            
            if not ticker_data:
                self.notify(f"Could not find ticker '{ticker}' in configuration.", severity="error")
                return
            
            def on_close(result: tuple[str, str] | None):
                if result:
                    field, value = result
                    
                    # Update the ticker in all relevant lists
                    for list_name in list_names:
                        for item in self.config.lists[list_name]:
                            if item.get('ticker', '').upper() == ticker.upper():
                                item[field] = value
                                break
                    
                    self.config.save_lists()
                    # Refresh the display
                    self.action_refresh(force=False)
                    self.notify(f"Updated {field} for '{ticker}'.")
            
            self.push_screen(QuickEditTickerModal(ticker, category, ticker_data), on_close)
        
        except NoMatches:
            self.bell()
    
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
        """Re-draws the price table using only data from the in-memory cache."""
        try:
            dt = self.query_one("#price-table", DataTable)
            active_category = self.get_active_category()
            if not active_category: return

            dt.clear()

            if active_category == 'all':
                seen = set()
                hidden_tabs = set(self.config.get_setting("hidden_tabs", []))
                symbols_on_screen = [s['ticker'] for list_name, lst in self.config.lists.items() for s in lst if list_name not in hidden_tabs and s['ticker'] not in seen and not seen.add(s['ticker'])]
            else:
                symbols_on_screen = [s['ticker'] for s in self.config.lists.get(active_category, [])]

            ordered_filtered_symbols = self._filter_symbols_by_tags(active_category, symbols_on_screen)

            data_for_table = [market_provider.get_cached_price(s) for s in ordered_filtered_symbols]
            data_for_table = [item for item in data_for_table if item is not None]

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
            
            self._is_filter_refresh = False

        except NoMatches:
            pass

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
    """
    console = Console()
    app_root = Path(__file__).resolve().parent
    config = ConfigManager(app_root)

    if session_lists := args.session_list:
        for name, tickers in session_lists.items():
            config.lists[name] = [{"ticker": ticker, "alias": ticker, "note": ""} for ticker in tickers]

    target_names = []
    if args.output != 'all':
        target_names.extend([name.strip().lower() for name in args.output.split(',')])
    if args.session_list:
        target_names.extend(args.session_list.keys())

    lists_to_iterate = []
    if not target_names:
        lists_to_iterate = config.lists.items()
    else:
        unique_target_names = list(set(target_names))
        lists_to_iterate = [(name, lst) for name, lst in config.lists.items() if name in unique_target_names]
        
    if not lists_to_iterate:
        console.print(f"[bold red]Error:[/] No lists found matching your criteria.")
        return
        
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

    with console.status("[bold green]Fetching data...[/]"):
        try:
            ticker_objects = yf.Tickers(" ".join(ordered_tickers))
            all_info = {ticker: ticker_objects.tickers[ticker].info for ticker in ordered_tickers}
        except Exception as e:
            console.print(f"[bold red]Failed to fetch data from API:[/] {e}")
            return

    rows = []
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

    if args.output:
        run_cli_output(args)
    else:
        app = StocksTUI(cli_overrides=vars(args))
        textual_handler = TextualHandler(app)
        textual_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(message)s')
        textual_handler.setFormatter(formatter)
        logging.getLogger().addHandler(textual_handler)
        app.run()

if __name__ == "__main__":
    main()