# Change Log
## [Unreleased]

### Added
-   `feat(ux)`: Persist last active view within the Configs screen.
-   `feat(ux)`: Add detailed real-time market status display with local timezone support, closure reasons, and next open/close times.

### Fixed
-   `fix(core)`: Prevent crash on shutdown by handling logging race condition.
-   `fix(cache)`: Correct cache expiry logic to prevent using stale `previous_close` values.

### Test
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
