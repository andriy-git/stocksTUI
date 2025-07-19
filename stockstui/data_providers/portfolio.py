"""Portfolio management module for organizing stocks into different portfolios."""

import datetime
import logging
from typing import Dict, List, Set, Optional
import uuid


class PortfolioManager:
    """Manages portfolio operations including CRUD and stock management."""
    
    def __init__(self, config_manager):
        """
        Initialize the portfolio manager.
        
        Args:
            config_manager: The ConfigManager instance for loading/saving portfolios
        """
        self.config = config_manager
        self._ensure_default_portfolio()
    
    def _ensure_default_portfolio(self):
        """Ensure the default portfolio exists."""
        if 'portfolios' not in self.config.portfolios:
            self.config.portfolios['portfolios'] = {}
        
        if 'default' not in self.config.portfolios['portfolios']:
            now = datetime.datetime.now().isoformat() + 'Z'
            self.config.portfolios['portfolios']['default'] = {
                'name': 'Default Portfolio',
                'description': 'Main portfolio containing all stocks',
                'tickers': [],
                'created': now,
                'modified': now
            }
            self.config.save_portfolios()
    
    def get_all_portfolios(self) -> Dict[str, Dict]:
        """
        Get all portfolios.
        
        Returns:
            Dictionary of portfolio_id -> portfolio data
        """
        return self.config.portfolios.get('portfolios', {})
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Dict]:
        """
        Get a specific portfolio by ID.
        
        Args:
            portfolio_id: The portfolio identifier
            
        Returns:
            Portfolio data or None if not found
        """
        return self.config.portfolios.get('portfolios', {}).get(portfolio_id)
    
    def create_portfolio(self, name: str, description: str = "") -> str:
        """
        Create a new portfolio.
        
        Args:
            name: Portfolio name
            description: Portfolio description
            
        Returns:
            The ID of the created portfolio
        """
        # Generate a unique ID
        portfolio_id = str(uuid.uuid4())[:8]
        while portfolio_id in self.config.portfolios.get('portfolios', {}):
            portfolio_id = str(uuid.uuid4())[:8]
        
        now = datetime.datetime.now().isoformat() + 'Z'
        self.config.portfolios['portfolios'][portfolio_id] = {
            'name': name,
            'description': description,
            'tickers': [],
            'created': now,
            'modified': now
        }
        
        self.config.save_portfolios()
        logging.info(f"Created portfolio '{name}' with ID {portfolio_id}")
        return portfolio_id
    
    def update_portfolio(self, portfolio_id: str, name: str, description: str):
        """
        Update portfolio details.
        
        Args:
            portfolio_id: The portfolio identifier
            name: New portfolio name
            description: New portfolio description
        """
        if portfolio_id not in self.config.portfolios.get('portfolios', {}):
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        portfolio = self.config.portfolios['portfolios'][portfolio_id]
        portfolio['name'] = name
        portfolio['description'] = description
        portfolio['modified'] = datetime.datetime.now().isoformat() + 'Z'
        
        self.config.save_portfolios()
        logging.info(f"Updated portfolio {portfolio_id}")
    
    def delete_portfolio(self, portfolio_id: str):
        """
        Delete a portfolio.
        
        Args:
            portfolio_id: The portfolio identifier
            
        Raises:
            ValueError: If trying to delete the default portfolio
        """
        if portfolio_id == 'default':
            raise ValueError("Cannot delete the default portfolio")
        
        if portfolio_id in self.config.portfolios.get('portfolios', {}):
            del self.config.portfolios['portfolios'][portfolio_id]
            self.config.save_portfolios()
            logging.info(f"Deleted portfolio {portfolio_id}")
    
    def add_ticker_to_portfolio(self, portfolio_id: str, ticker: str):
        """
        Add a ticker to a portfolio.
        
        Args:
            portfolio_id: The portfolio identifier
            ticker: The stock ticker symbol
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        ticker = ticker.upper()
        if ticker not in portfolio['tickers']:
            portfolio['tickers'].append(ticker)
            portfolio['modified'] = datetime.datetime.now().isoformat() + 'Z'
            self.config.save_portfolios()
            logging.info(f"Added {ticker} to portfolio {portfolio_id}")
    
    def remove_ticker_from_portfolio(self, portfolio_id: str, ticker: str):
        """
        Remove a ticker from a portfolio.
        
        Args:
            portfolio_id: The portfolio identifier
            ticker: The stock ticker symbol
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        ticker = ticker.upper()
        if ticker in portfolio['tickers']:
            portfolio['tickers'].remove(ticker)
            portfolio['modified'] = datetime.datetime.now().isoformat() + 'Z'
            self.config.save_portfolios()
            logging.info(f"Removed {ticker} from portfolio {portfolio_id}")
    
    def get_tickers_for_portfolio(self, portfolio_id: str) -> List[str]:
        """
        Get all tickers in a specific portfolio.
        
        Args:
            portfolio_id: The portfolio identifier
            
        Returns:
            List of ticker symbols
        """
        portfolio = self.get_portfolio(portfolio_id)
        return portfolio['tickers'] if portfolio else []
    
    def get_all_tickers(self) -> Set[str]:
        """
        Get all unique tickers across all portfolios.
        
        Returns:
            Set of all unique ticker symbols
        """
        all_tickers = set()
        for portfolio in self.config.portfolios.get('portfolios', {}).values():
            all_tickers.update(portfolio.get('tickers', []))
        return all_tickers
    
    def get_portfolios_containing_ticker(self, ticker: str) -> List[tuple[str, str]]:
        """
        Find all portfolios that contain a specific ticker.
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            List of tuples (portfolio_id, portfolio_name)
        """
        ticker = ticker.upper()
        portfolios = []
        
        for pid, portfolio in self.config.portfolios.get('portfolios', {}).items():
            if ticker in portfolio.get('tickers', []):
                portfolios.append((pid, portfolio['name']))
        
        return portfolios
    
    def add_ticker_to_all_portfolios(self, ticker: str):
        """
        Add a ticker to all portfolios.
        
        Args:
            ticker: The stock ticker symbol
        """
        ticker = ticker.upper()
        for portfolio_id in self.config.portfolios.get('portfolios', {}):
            self.add_ticker_to_portfolio(portfolio_id, ticker)