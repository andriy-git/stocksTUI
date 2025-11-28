import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Only load data into memory if it's less than a day old.
CACHE_LOAD_DURATION_SECONDS = 86400  # 24 hours

# Prune any data from the database file that is older than 7 days.
# This keeps the database file size manageable over time.
CACHE_PRUNE_EXPIRY_SECONDS = 604800  # 7 days

# Ticker info (exchange, name) changes very rarely. Cache it for a long time.
INFO_CACHE_EXPIRY_SECONDS = 86400 * 30  # 30 days

class DbManager:
    """
    Manages the persistent SQLite database for caching application data, primarily
    stock prices and ticker metadata, to enable faster startups and reduce API calls.
    """
    def __init__(self, db_path: Path):
        """
        Initializes the DbManager and establishes a connection to the database.

        Args:
            db_path: The file path for the SQLite database.
        """
        self.db_path = db_path
        self.conn = None
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(
                self.db_path,
                isolation_level=None,
                check_same_thread=False
            )
            self._create_tables()
            self._prune_expired_entries()
        except sqlite3.Error as e:
            logging.error(f"Database connection failed for '{self.db_path}': {e}")

    def _create_tables(self):
        """Creates the necessary tables in the database if they don't already exist."""
        if not self.conn:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticker_info (
                    ticker TEXT PRIMARY KEY,
                    exchange TEXT,
                    short_name TEXT,
                    long_name TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS option_positions (
                    symbol TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    avg_cost REAL,
                    timestamp REAL NOT NULL
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to create database tables: {e}")
            self.conn.rollback()

    def _prune_expired_entries(self):
        """Removes entries from the persistent cache that are older than their prune expiry date."""
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            price_prune_ts = datetime.now(timezone.utc).timestamp() - CACHE_PRUNE_EXPIRY_SECONDS
            cursor.execute("DELETE FROM price_cache WHERE timestamp < ?", (price_prune_ts,))
            if cursor.rowcount > 0:
                logging.info(f"Pruned {cursor.rowcount} expired entries from the price cache.")

            info_prune_ts = datetime.now(timezone.utc).timestamp() - INFO_CACHE_EXPIRY_SECONDS
            cursor.execute("DELETE FROM ticker_info WHERE timestamp < ?", (info_prune_ts,))
            if cursor.rowcount > 0:
                logging.info(f"Pruned {cursor.rowcount} expired entries from the info cache.")

            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to prune expired cache entries: {e}")
            self.conn.rollback()

    def load_price_cache_from_db(self) -> dict:
        """Loads the price cache from the database, filtering for entries fresh enough to use."""
        if not self.conn: return {}
        loaded_data = {}
        try:
            cursor = self.conn.cursor()
            load_after_ts = datetime.now(timezone.utc).timestamp() - CACHE_LOAD_DURATION_SECONDS
            cursor.execute("SELECT ticker, data, timestamp FROM price_cache WHERE timestamp >= ?", (load_after_ts,))
            rows = cursor.fetchall()
            for ticker, data_json, timestamp_float in rows:
                try:
                    # FIX: Load data into the standardized dictionary format, not a tuple.
                    # The expiry is calculated from the stored timestamp.
                    expiry_dt = datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
                    data_dict = json.loads(data_json)
                    loaded_data[ticker] = {'expiry': expiry_dt, 'data': data_dict}
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logging.warning(f"Failed to decode or parse price data for '{ticker}' from DB.")
        except sqlite3.Error as e:
            logging.error(f"Failed to load price cache from database: {e}")
        logging.info(f"Loaded {len(loaded_data)} fresh items from the persistent price cache.")
        return loaded_data

    def load_info_cache_from_db(self) -> dict:
        """Loads the ticker info cache (exchange, name) from the database."""
        if not self.conn: return {}
        loaded_data = {}
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT ticker, exchange, short_name, long_name FROM ticker_info")
            rows = cursor.fetchall()
            for ticker, exchange, short_name, long_name in rows:
                loaded_data[ticker] = {
                    "exchange": exchange, "shortName": short_name, "longName": long_name
                }
        except sqlite3.Error as e:
            logging.error(f"Failed to load info cache from database: {e}")
        logging.info(f"Loaded {len(loaded_data)} items from the persistent info cache.")
        return loaded_data

    def save_price_cache_to_db(self, cache_data: dict):
        """Saves the in-memory price cache to the database."""
        if not self.conn or not cache_data: return
        items_to_save = []
        for ticker, cache_entry in cache_data.items():
            try:
                # FIX: Unpack the new standardized dictionary format for saving.
                data_dict = cache_entry.get('data', {})
                expiry_dt = cache_entry.get('expiry')
                if data_dict and expiry_dt:
                    items_to_save.append((ticker, json.dumps(data_dict), expiry_dt.timestamp()))
            except (TypeError, ValueError, AttributeError):
                logging.warning(f"Could not serialize price data for '{ticker}' to save.")
        if not items_to_save: return
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            cursor.executemany("INSERT OR REPLACE INTO price_cache (ticker, data, timestamp) VALUES (?, ?, ?)", items_to_save)
            self.conn.commit()
            logging.info(f"Saved/Updated {len(items_to_save)} items in the persistent price cache.")
        except sqlite3.Error as e:
            logging.error(f"Failed to save price cache to database: {e}")
            self.conn.rollback()

    def save_info_cache_to_db(self, cache_data: dict):
        """Saves the in-memory info cache to the database."""
        if not self.conn or not cache_data: return
        items_to_save = []
        now_ts = datetime.now(timezone.utc).timestamp()
        for ticker, data in cache_data.items():
            items_to_save.append((
                ticker, data.get("exchange"), data.get("shortName"), data.get("longName"), now_ts
            ))
        if not items_to_save: return
        try:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            cursor.executemany("INSERT OR REPLACE INTO ticker_info (ticker, exchange, short_name, long_name, timestamp) VALUES (?, ?, ?, ?, ?)", items_to_save)
            self.conn.commit()
            logging.info(f"Saved/Updated {len(items_to_save)} items in the persistent info cache.")
        except sqlite3.Error as e:
            logging.error(f"Failed to save info cache to database: {e}")
            self.conn.rollback()

    # --- Option Positions Methods ---

    def save_option_position(self, symbol: str, ticker: str, quantity: float, avg_cost: float):
        """Saves or updates an option position."""
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now(timezone.utc).timestamp()
            cursor.execute("""
                INSERT OR REPLACE INTO option_positions (symbol, ticker, quantity, avg_cost, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, ticker, quantity, avg_cost, timestamp))
            self.conn.commit()
            logging.info(f"Saved option position: {symbol}")
        except sqlite3.Error as e:
            logging.error(f"Failed to save option position {symbol}: {e}")

    def get_option_position(self, symbol: str) -> dict | None:
        """Retrieves a specific option position."""
        if not self.conn: return None
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT symbol, ticker, quantity, avg_cost FROM option_positions WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if row:
                return {
                    'symbol': row[0],
                    'ticker': row[1],
                    'quantity': row[2],
                    'avg_cost': row[3]
                }
            return None
        except sqlite3.Error as e:
            logging.error(f"Failed to get option position {symbol}: {e}")
            return None

    def delete_option_position(self, symbol: str):
        """Deletes an option position."""
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM option_positions WHERE symbol = ?", (symbol,))
            self.conn.commit()
            logging.info(f"Deleted option position: {symbol}")
        except sqlite3.Error as e:
            logging.error(f"Failed to delete option position {symbol}: {e}")

    def get_all_option_positions(self) -> dict:
        """Retrieves all option positions, keyed by symbol."""
        if not self.conn: return {}
        positions = {}
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT symbol, ticker, quantity, avg_cost FROM option_positions")
            rows = cursor.fetchall()
            for row in rows:
                positions[row[0]] = {
                    'symbol': row[0],
                    'ticker': row[1],
                    'quantity': row[2],
                    'avg_cost': row[3]
                }
            return positions
        except sqlite3.Error as e:
            logging.error(f"Failed to get all option positions: {e}")
            return {}

    def close(self):
        """Closes the database connection if it's open."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")