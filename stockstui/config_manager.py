import json
from pathlib import Path
import logging
import os
import time
from platformdirs import PlatformDirs

# Use platformdirs to determine the correct user directories.
# This ensures we respect OS conventions (e.g., ~/.config vs ~/Library/Application Support)
# The "appauthor" argument is optional but good practice.
APP_NAME = "stockstui"
APP_AUTHOR = "andriy-git"
dirs = PlatformDirs(APP_NAME, APP_AUTHOR)

class ConfigManager:
    """
    Manages loading, saving, and accessing application configuration files.
    It uses platformdirs to store files in OS-appropriate locations.
    - Config files (`.json`) go in the user_config_dir.
    - Cache files (`.db`) go in the user_cache_dir.
    """
    def __init__(self, app_root: Path):
        """
        Initializes the ConfigManager.
        Args:
            app_root: The root path of the application package.
        """
        # Define user-specific and default configuration directories
        self.user_config_dir = Path(dirs.user_config_dir)
        self.user_cache_dir = Path(dirs.user_cache_dir)
        self.default_dir = app_root / "default_configs"

        # Ensure directories exist
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        self.user_cache_dir.mkdir(parents=True, exist_ok=True)

        # The database path now correctly uses the cache directory.
        self.db_path = self.user_cache_dir / "app_cache.db"

        self.settings: dict = self._load_or_create('settings.json')
        
        # Merge defaults for new keys to ensure backward compatibility
        try:
            default_settings_path = self.default_dir / 'settings.json'
            if default_settings_path.exists():
                with open(default_settings_path, 'r') as f:
                    default_settings = json.load(f)
                    updated = False
                    for k, v in default_settings.items():
                        if k not in self.settings:
                            self.settings[k] = v
                            updated = True
                        elif k == "column_settings" and isinstance(v, list) and isinstance(self.settings[k], list):
                            # Special handling for column_settings to merge new columns
                            existing_keys = {col.get("key") for col in self.settings[k] if isinstance(col, dict)}
                            for default_col in v:
                                if isinstance(default_col, dict) and default_col.get("key") not in existing_keys:
                                    self.settings[k].append(default_col)
                                    updated = True
                    if updated:
                        self.save_settings()
        except Exception as e:
            logging.error(f"Failed to merge default settings: {e}")

        self.lists: dict = self._load_or_create('lists.json')
        self.themes: dict = self._load_or_create('themes.json')
        self.portfolios: dict = self._load_or_create('portfolios.json')
        
        # Migrate existing stocks to default portfolio on first run
        self._migrate_stocks_to_default_portfolio()

    def _load_or_create(self, filename: str) -> dict:
        """
        Loads a JSON configuration file from the user's config directory.
        If the file is missing or corrupted, it's restored from the default config.
        """
        user_path = self.user_config_dir / filename
        default_path = self.default_dir / filename

        data = None
        if user_path.exists():
            try:
                with open(user_path, 'r') as f:
                    if os.fstat(f.fileno()).st_size == 0:
                        raise json.JSONDecodeError("File is empty.", "", 0)
                    data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"User config '{user_path}' is corrupted: {e}. Restoring from default.")
                try:
                    backup_path = user_path.with_suffix(user_path.suffix + '.bak')
                    os.replace(user_path, backup_path)
                    logging.info(f"Corrupted file backed up to '{backup_path.name}'.")
                except OSError as backup_err:
                    logging.error(f"Could not back up corrupted file '{user_path}': {backup_err}")
                data = None

        if data is None:
            if not default_path.exists():
                logging.critical(f"Default config '{default_path}' is missing! Cannot create user config.")
                return {}
            try:
                with open(default_path, 'r') as f_default:
                    default_data = json.load(f_default)
                self._atomic_save(filename, default_data)
                logging.info(f"Created/Restored user config '{user_path}' from default.")
                return default_data
            except (IOError, json.JSONDecodeError) as e:
                logging.error(f"Failed to create user config from '{default_path}': {e}")
                return {}

        return data

    def _atomic_save(self, filename: str, data: dict):
        """
        Safely saves a dictionary to a JSON file using an atomic operation.
        """
        user_path = self.user_config_dir / filename
        temp_path = user_path.with_suffix(user_path.suffix + '.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=4)
            os.replace(temp_path, user_path)
        except IOError as e:
            logging.error(f"Could not save to '{filename}': {e}")
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def save_settings(self):
        self._atomic_save('settings.json', self.settings)

    def save_lists(self):
        self._atomic_save('lists.json', self.lists)
    
    def save_portfolios(self):
        self._atomic_save('portfolios.json', self.portfolios)
    
    def _migrate_stocks_to_default_portfolio(self):
        """Migrate existing stocks from lists to default portfolio if needed."""
        if 'portfolios' not in self.portfolios:
            return
        
        # Check if migration was already done by looking for a migration flag
        if self.portfolios.get('settings', {}).get('migration_completed'):
            return
            
        default_portfolio = self.portfolios['portfolios'].get('default', {})
        
        # Only migrate if default portfolio is empty
        if not default_portfolio.get('tickers'):
            # Get all tickers from the 'stocks' list
            stocks_list = self.lists.get('stocks', [])
            if stocks_list:
                tickers = [item['ticker'] for item in stocks_list if 'ticker' in item]
                if tickers:
                    import datetime
                    now = datetime.datetime.now().isoformat() + 'Z'
                    default_portfolio['tickers'] = tickers
                    default_portfolio['created'] = now
                    default_portfolio['modified'] = now
                    self.portfolios['portfolios']['default'] = default_portfolio
                    logging.info(f"Migrated {len(tickers)} stocks to default portfolio")
        
        # Set migration flag to prevent future migrations
        if 'settings' not in self.portfolios:
            self.portfolios['settings'] = {}
        self.portfolios['settings']['migration_completed'] = True
        self.save_portfolios()