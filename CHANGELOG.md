# Change Log
## [0.1.0-b11] UNDETERMINED

### Added
-   `feat(fred)`: Add FRED data provider with caching and API integration
-   `feat(fred)`: Add FRED UI view with summary dashboard and edit modal
-   `feat(fred)`: Add FRED configuration view for managing API key and series
-   `feat(fred)`: Integrate FRED view into main application navigation and config
-   `feat(fred)`: Add enhanced FRED metrics (rolling averages, z-scores, historical ranges)
-   `feat(fred)`: Add FRED API debug testing in Debug view
-   `feat(fred)`: Add FRED data output support in CLI mode (-o fred)
-   `feat(fred)`: Add FRED series browser opening functionality (o key) and Enter key editing
-   `feat(fred)`: Add dedicated AddFredSeriesModal and increase observation limits
-   `feat(cli)`: Add support for tag filtering in CLI mode via `--tags`
-   `feat(ui)`: Hide "Portfolios" button from Main Settings to focus on core features
-   `feat(ui)`: Implement dynamic theme-aware colors for charts and CLI headers (replace hardcoded colors)
-   `feat(ui)`: Add Enter key action handling for DataTable selections across views
-   `feat(ui)`: Add keyboard navigation improvements (i, j, k, h, l) to config and debug views
-   `feat(ui)`: Add row selection handling for ticker editing in lists config view
-   `feat(cli)`: Fix CLI output to properly handle cases when only FRED is requested
-   `test(fred)`: Add integration and UI tests for FRED functionality
-   `docs(man)`: Add comprehensive documentation for FRED functionality in --man
-   `docs(man)`: Add documentation for -o fred and --fred command line options
-   `docs(man)`: Add documentation for FRED data table columns in --man
-   `docs(man)`: Add documentation for Options data table columns in --man

### Changed
-   `chore(build)`: Update dev dependencies installation in workflow
-   `chore(build)`: Add mypy configuration with appropriate ignore settings
-   `chore(build)`: Update CI workflow to use .[dev] dependencies and simplify ruff checks

### Build
-   `build(deps)`: Add dev dependencies (ruff, mypy, coverage) to pyproject.toml
-   `build(ci)`: Simplify ruff checks to basic error detection in CI workflow

## [0.1.0-b10] 2025-12-24

### Added
-   `feat(market_provider)`: Add All Time High field to fetched data
-   `feat(ui)`: Add All Time High and % Off ATH columns to price tables with configurable visibility
-   `feat(market_provider)`: Add exchange code mapping for SNP, DJI, CBOE, and NIM to NYSE calendar
-   `feat(ui)`: Add keyboard navigation (j/k, h/l, arrow keys) to config views and debug view

### Changed
-   `chore(themes)`: Fix formatting and newline in themes.json

### Test
-   `test(open_mode)`: Update test to include Yahoo Finance option in open mode
-   `test(market_provider)`: Add exchange mapping tests and cache cleanup

## [0.1.0-b9] 2025-11-29

### Changed
-   `chore(deps)`: Migrated from Textual 3.5.0 to 5.3.0 to fix Python 3.12 compatibility issues
-   `chore(deps)`: Updated requirements.txt to align with pyproject.toml Textual version

## [0.1.0-b8] 2025-11-28

### Added
-   `feat(options)`: Added comprehensive options chain functionality with expiration date selection and call/put tables
-   `feat(options)`: Implemented options Greeks calculation (Delta, Gamma, Theta, Vega) using Black-Scholes model
-   `feat(options)`: Added option position tracking with quantity and average cost management
-   `feat(options)`: Created interactive Open Interest bar chart visualization for calls and puts
-   `feat(ui)`: Introduced 'Open Mode' allowing users to quickly navigate from price tables to news, history, or options views using `o`, `n`, `h` keys
-   `feat(ui)`: Added quick edit modal for ticker aliases, notes, and tags accessible with `e` key in price tables
-   `feat(ui)`: Added position management modal for options with quantity and cost tracking
-   `feat(ui)`: Implemented toggle between table and chart views in options view
-   `feat(ui)`: Added keyboard shortcuts for navigating expiration dates (`[` and `]`) in options view
-   `feat(ui)`: Created new 'options' tab in main application with dedicated UI components
-   `feat(data)`: Added options data provider with caching mechanism and yfinance integration
-   `feat(db)`: Added option_positions table to SQLite database with CRUD operations
-   `feat(core)`: Added Black-Scholes options pricing model implementation for Greeks calculation
-   `feat(core)`: Added new OptionsDataUpdated and OptionsExpirationsUpdated message types
-   `feat(ui)`: Added OIChart widget for visualizing open interest by strike price
-   `feat(test)`: Added comprehensive test coverage for options functionality including provider, UI, and position management

### Changed
-   `refactor(ui)`: Updated HistoryChart widget to gracefully handle missing 'Close' column by falling back to 'Open' or first numeric column
-   `refactor(data)`: Enhanced market status provider to handle different HolidayCalendar API versions
-   `refactor(ui)`: Updated NewsView component to include required Markdown component classes for proper styling
-   `refactor(ui)`: Modified main application to support options view integration with proper data flow and category handling
-   `refactor(core)`: Improved error handling in options data fetching with better error messaging
-   `refactor(test)`: Updated format_historical_data_as_table to include app context for proper DataTable measurement
-   `refactor(ui)`: Added Enter key binding to Tabs component for focusing primary view widgets

### Fixed
-   `fix(data)`: Fixed holiday detection in market status provider for different pandas_market_calendars API versions
-   `fix(ui)`: Fixed HistoryChart rendering when data contains only a single point to avoid division by zero errors
-   `fix(ui)`: Improved handling of NaN values in historical data for chart rendering
-   `fix(ui)`: Fixed escape sequence handling in formatter module for special markdown characters

### Test
-   `test(formatter)`: Added tests for historical data formatting with both daily and intraday data
-   `test(formatter)`: Added tests for debug table formatting functions and info comparison utilities
-   `test(formatter)`: Added tests for escaping special characters in markdown text
-   `test(history-chart)`: Updated tests to reflect graceful handling of missing 'Close' column in data
-   `test(black-scholes)`: Added comprehensive test coverage for Black-Scholes Greeks calculations
-   `test(options-provider)`: Added test suite for options provider functionality
-   `test(options-view)`: Added test coverage for options view components
-   `test(position-manager)`: Added tests for option position management features

## [0.1.0-b7] 2025-11-23

### Added
-   `feat(data)`: Added new financial metrics to data providers including volume, open price, PE ratio, market cap, dividend yield, EPS, and beta
-   `feat(ui)`: Implemented dynamic column management system allowing users to show/hide specific data columns in price tables
-   `feat(ui)`: Added column visibility toggles and reordering functionality in the Lists config view
-   `feat(ui)`: Enhanced general config view with improved layout and tab visibility management using ListView
-   `feat(core)`: Added automatic merging of new default settings for backward compatibility when config is updated
-   `feat(ui)`: Implemented cursor position preservation across columns during data refreshes in price tables
-   `feat(ui)`: Enabled sorting on all available columns, not just a predefined set

### Changed
-   `refactor(data)`: Modified data formatting to use dictionary-based rows instead of tuples for more flexible column management
-   `refactor(ui)`: Updated styling for config views to use horizontal layouts with consistent labeling
-   `refactor(core)`: Improved data fetching to include additional metrics like volume, PE ratio, market cap, and dividend yield
-   `refactor(ui)`: Changed tab visibility management to use Switch widgets in a ListView instead of checkboxes

### Fixed
-   `fix(ui)`: Correctly preserve both row and column cursor position during data refresh operations
-   `fix(ui)`: Fixed tab refresh logic to use proper repopulation methods instead of manual DOM manipulation

## [0.1.0-b6] 2025-11-09

### Added
-   `feat(ux)`: Persist last active view within the Configs screen.
-   `feat(ux)`: Add detailed real-time market status display with local timezone support, closure reasons, and next open/close times.

### Fixed
-   `fix(core)`: Prevent crash on shutdown by handling logging race condition.
-   `fix(cache)`: Correct cache expiry logic to prevent using stale `previous_close` values.
-   `fix(ux)`: Hidden tabs are now properly excluded from symbol listings, tag filtering, and alias mapping throughout the application.

### Test
-   `test(suite)`: Added a comprehensive test suite covering the application's core logic, data providers, database, and UI components.
-   `test(ci)`: Implemented a GitHub Actions CI workflow to run tests, linting, and type checking automatically.
-   `test(runner)`: Added a `run_tests.sh` script for convenient local test execution with coverage reporting.
-   `test(cache)`: Add unit test to verify cache invalidation across market sessions.

## [0.1.0-b5] 2025-07-22

### Added
-   `feat(config)`: Implemented a multi-window layout for the "Configs" tab, separating General Settings, Watchlists, and Portfolios into distinct views.
-   `feat(ux)`: The `backspace` key can now be used for hierarchical "back" navigation within the nested menus of the Configs tab.
-   `feat(ux)`: Implemented a smart, self-adjusting refresh mechanism for the market status, polling more frequently around market open/close and less frequently during off-hours.
-   `feat(ux)`: The tag filtering widget is now available on all ticker list tabs (e.g., 'crypto', 'indices').
-   `feat(ux)`: The tag filter panel can now be toggled on and off using the `f` key, preserving filter state while hidden.

### Changed
-   `refactor(config)`: Refactored the entire configuration tab to use the Container View Pattern for better organization and scalability.
-   `refactor(ux)`: Decoupled UI filtering from network refreshing, making tag filtering an instantaneous, local operation.

### Fixed
-   `fix(ux)`: The user-defined order of tickers is now correctly preserved during data refreshes, filtering, and in the command-line `--output` mode.
-   `fix(ux)`: Cursor position in the main price table is now preserved across data refreshes and correctly resets only when filters are applied.
-   `fix(core)`: Implemented worker cancellation checks to prevent `RuntimeError` crashes during application shutdown.

### Docs
-   `docs`: README and manual updated

### Feature Merge: Portfolios & Tag Filtering
This release includes a major contribution that introduces two powerful new systems for organizing and viewing assets: **Portfolios** and **Tags**. These features work together to provide a much more flexible and powerful way to manage watchlists.

A special thanks to contributor **[@klahrich](https://github.com/klahrich)** for their incredible work on designing and implementing this entire feature set.

#### Added
-   **Full-featured Portfolio Management system:**
  -   A new `portfolios.json` config file to define and persist portfolios.
  -   A dedicated `PortfolioManager` to handle all backend logic (CRUD operations).
  -   Automatic migration of existing `stocks` list into a "Default Portfolio" on first run for a seamless user transition.
  -   New modals in the Config screen to create, rename, and delete portfolios.
-   **Comprehensive Tagging and Filtering System:**
  -   Ability to add multiple, space- or comma-separated tags to any ticker in the Config screen.
  -   New `TagFilterWidget` appears at the top of price views, allowing users to filter the visible tickers by clicking one or more tag buttons.
  -   A "Clear" button to quickly remove all active tag filters.
  -   A status label that shows how many tickers are being shown out of the total available (e.g., "Showing 5 of 20").

#### Changed
-   The `Config` view has been significantly updated to support portfolio and tag management.
-   The "Add/Edit Ticker" modals now include a field for "Tags".
-   The `yfinance` dependency requirement was relaxed from `~=` to `>=` to allow for newer patch versions.

## [0.1.0-b4] 2025-07-15

### Added
-   `feat(cli)`: Added `-o/--output` flag to display stock data directly in the terminal without launching the TUI
-   `feat(cli)`: Supported optional watchlist filtering and session lists in CLI output mode

### Fix
-   `fix(ui)`: Prevented crash on duplicate tickers in "all" tab by duplicating ticker lists

### Docs
-   `docs(readme, cli)`: Updated help documentation to include `--output` flag and clarify TUI view options
-   `docs(changelog)`: Updated `CHANGELOG.md` to include recent feature additions

## [0.1.0-b3] 2025-07-14

### Added
-   `feat(cli)`: Added a `--man` flag to display a detailed, man-page-style user guide.
-   `feat(debug)`: Debug test isolation for accurate measurements
-   `feat(ux)`: Smart refresh system (`r` vs `R` keybindings)
-   `feat(news)`: Added support for viewing a combined news feed for multiple tickers, sorted by publication time
-   `feat(cache)`: Implemented persistent SQLite cache (`app_cache.db`) for price/ticker metadata
-   `feat(cache)`: Added market-aware cache expiration to optimize API usage
-   `feat(cli)`: Implemented CLI argument parsing for launching into specific views
-   `feat(logs)`: Added in-app notifications for WARNING/ERROR log messages
-   `feat(logs)`: Added file logger (`stockstui.log`) for debug information

### Changed
-   `refactor(ux)`: Simplified price comparison data handling to update after table population
-   `refactor(ux)`: Improved price change flash by moving direction logic to formatter.py for accurate comparison
-   `refactor(provider)`: Overhauled data fetching pipeline for efficiency
-   `refactor(cli)`: Dynamically load app version from package metadata
-   `refactor(cache)`: Converted caching to timezone-aware UTC datetimes
-   `refactor(config)`: Relocated config/cache files to OS-appropriate directories
-   `refactor(cli)`: Enhanced `--news` to support multiple comma-separated tickers

### Fixed
-   `fix(ui)`: Prevented crash when switching tabs during price cell flash animation
-   `fix(ui)`: Ensured search box is dismissed when switching tabs, preventing it from lingering
-   `fix(ui)`: Fixed invalid state in "Default Tab" dropdown when the configured default tab is deleted
-   `fix(cache)`: Ensured live price updates are saved to session cache, maintaining consistent prices when switching tabs
-   `fix(formatter)`: Restored user-defined aliases in the price table, prioritizing custom names over default descriptions
-   `fix(cache)`: Standardized cache structure to prevent TypeErrors
-   `fix(provider)`: Prioritized `fast_info` for real-time data accuracy
-   `fix(core)`: Improved stability with better DB transaction handling
-   `fix(core)`: Ensured atomic config saves using `os.replace`
-   `fix(ux)`: Guaranteed data refresh on tab switch with accurate timestamps
-   `fix(ui)`: Corrected source ticker styling in multi-news view
-   `fix(news)`: Hardened link-parsing regex against special characters
-   `fix(debug)`: Fixed test button re-enabling after modal cancellation
-   `fix(history)`: Added CLI argument handling for `--chart` and `--period`
-   `fix(css)`: Fixed scrollbar in config visible tabs container
-   `fix(logs)`: Implemented thread-safe logging

### Docs
-   `docs`: README and manual overhaul

## [0.1.0-b2] - 2025-07-11

### Added
-   `feat(ux)`: Added background color flash (green for up, red for down) on 'Change' and '% Change' cells to highlight price updates
-   `feat(ux)`: Improved refresh UX by keeping stale data visible until new data arrives, eliminating loading screen on subsequent refreshes
-   `feat(ux)`: Enhanced readability with inverted text color during price change flashes
-   `feat(ux)`: Refined price comparison to round values, avoiding flashes on minor floating-point fluctuations

### Docs

-   `docs(readme, cli)`: Updated `README.md` to recommend `pipx` installation with setup instructions
-   `docs(readme, cli)`: Added disclaimer in `README.md` and help command requiring tickers in Yahoo Finance format

## [0.1.0-b1] - 2025-07-11

### Added

-   `feat(ui)`: Show specific feedback for invalid tickers and data fetching failures in the history and news views.
-   `feat(news)`: Notify the user when attempting to open an external link.

### Fixed

-   `fix(config)`: Use atomic writes for config files to prevent data loss.
-   `fix(config)`: Eliminate risk of infinite loops during config loading.
-   `fix(config)`: Backup corrupted config files as `.bak` to allow manual recovery.
-   `fix(news)`: Show clear error messages in the Markdown widget for invalid tickers or network issues.
-   `fix(news)`: Provide actionable feedback if no web browser is configured when opening external links.
-   `fix(debug)`: Prevent race conditions by disabling test buttons on start and restoring them on modal cancel.
-   `fix(provider)`: Improve resilience of batch requests by handling individual ticker failures gracefully.
-   `fix(imports)`: Corrected all internal imports to be absolute for package compatibility.

### Changed

-   `refactor(provider)`: Replace broad `except Exception` with targeted exception handling for network, data, and validation errors.
-   `refactor(cli)`: Modernize command-line help display to use `subprocess` for better robustness.

### Docs

-   `docs(readme)`: Revised README for clarity, adding PyPI installation instructions and specific OS requirements.
-   `docs(help)`: Overhaul help text for improved clarity, structure, and readability.

### Build

-   `build(packaging)`: Configured the project for PyPI distribution with a `pyproject.toml` and restructured the source layout.
-   `build(install)`: Reworked `install.sh` to use `pip install -e .` for a standard, editable development setup.

## [0.1.0-beta.0] - 2025-07-08

-   Initial pre-release.
-   Many foundational changes; changelog entries begin from `0.1.0-beta.1`.
