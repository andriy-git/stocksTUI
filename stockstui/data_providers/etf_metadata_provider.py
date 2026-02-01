"""
ETF Metadata Provider

Fetches ETF metadata (TER, replication, fund size, etc.) from various sources.
Designed with clean abstractions for easy extension.

Supported sources:
- Vanguard PRIIPs KID PDFs (EU, IE* ISINs)
- yfinance API (US ETFs, fallback for others)

To add a new provider:
1. Create a class inheriting from BaseFetcher
2. Implement can_handle() and fetch()
3. Add instance to FETCHERS list

Optional dependency:
- pypdf: Required for PDF parsing. Install with `pip install pypdf`
"""

import logging
import re
import tempfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

import requests


# =============================================================================
# Data Model
# =============================================================================


@dataclass
class ETFMetadata:
    """ETF metadata extracted from various sources."""

    isin: str
    ticker: str | None = None
    name: str | None = None
    ter: float | None = None  # Total Expense Ratio (0.25 = 0.25%)
    ongoing_charges: float | None = None
    replication: str | None = None  # Physical, Synthetic
    distribution: str | None = None  # Accumulating, Distributing
    fund_size_mln: float | None = None
    fund_currency: str | None = None
    fund_family: str | None = None  # Vanguard, iShares, etc.
    inception_date: str | None = None
    risk_level: int | None = None  # 1-7 SRRI scale (EU only)
    source_url: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Include stock-specific fields if present
        if hasattr(self, "_stock_info"):
            d.update(self._stock_info)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ETFMetadata":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# Abstract Base Fetcher
# =============================================================================


class BaseFetcher(ABC):
    """Abstract base class for ETF metadata fetchers."""

    @abstractmethod
    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        """Check if this fetcher can handle the given ISIN/ticker."""
        pass

    @abstractmethod
    def fetch(self, isin: str | None, ticker: str | None) -> ETFMetadata | None:
        """Fetch metadata. Returns None on failure."""
        pass


# =============================================================================
# PDF Parsing Mixin
# =============================================================================


class PDFFetcherMixin:
    """Mixin providing PDF download and text extraction capabilities."""

    def _download_pdf(self, url: str, timeout: int = 15) -> bytes | None:
        """Download PDF from URL. Returns bytes or None on failure."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                if response.content[:4] == b"%PDF":
                    return response.content
            logging.debug(f"PDF download failed: {url} (status={response.status_code})")
        except requests.RequestException as e:
            logging.debug(f"PDF download error: {url} ({e})")
        return None

    def _extract_text_from_pdf(self, pdf_content: bytes) -> str | None:
        """Extract text from PDF bytes. Returns None if pypdf not installed."""
        try:
            from pypdf import PdfReader
        except ImportError:
            logging.warning("pypdf not installed. Install with: pip install pypdf")
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(pdf_content)
                tmp.flush()
                reader = PdfReader(tmp.name)
                return "\n".join(page.extract_text() for page in reader.pages)
        except Exception as e:
            logging.debug(f"PDF parsing error: {e}")
            return None


# =============================================================================
# Vanguard Fetcher (EU PRIIPs KID PDFs)
# =============================================================================


class VanguardFetcher(BaseFetcher, PDFFetcherMixin):
    """
    Fetches metadata from Vanguard PRIIPs KID documents.

    URL: https://fund-docs.vanguard.com/{isin}_priipskid_en.pdf
    Supports: Irish ISINs (IE prefix)
    """

    BASE_URL = "https://fund-docs.vanguard.com"

    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        return bool(isin and isin.upper().startswith("IE"))

    def _build_url(self, isin: str, lang: str = "en") -> str:
        return f"{self.BASE_URL}/{isin.lower()}_priipskid_{lang}.pdf"

    def fetch(self, isin: str | None, ticker: str | None) -> ETFMetadata | None:
        if not isin:
            return None

        url = self._build_url(isin)
        pdf_content = self._download_pdf(url)
        if not pdf_content:
            return None

        text = self._extract_text_from_pdf(pdf_content)
        if not text:
            return None

        return self._parse_kid_text(text, isin, ticker, url)

    def _parse_kid_text(
        self, text: str, isin: str, ticker: str | None, source_url: str
    ) -> ETFMetadata | None:
        """Parse Vanguard KID PDF text."""
        metadata = ETFMetadata(
            isin=isin, ticker=ticker, source_url=source_url, fund_family="Vanguard"
        )

        # Fund name
        if match := re.search(
            r"Key Information Document\s*\n\s*(.+?)(?:\n|UCITS)", text, re.IGNORECASE
        ):
            metadata.name = match.group(1).strip()

        # TER
        ter_patterns = [
            r"Management fees and other[^%]*?(\d+[.,]\d+)\s*%",
            r"Ongoing (?:Charges?|costs?)[:\s]*(\d+[.,]\d+)\s*%",
            r"(\d+[.,]\d+)\s*%\s*of the value of your investment p\.?a",
        ]
        for pattern in ter_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                try:
                    metadata.ter = float(match.group(1).replace(",", "."))
                    break
                except ValueError:
                    pass

        # Risk level (1-7 SRRI)
        risk_patterns = [
            r"classified[^0-9]*(\d)\s*out of 7",
            r"(\d)\s*out of 7[,\s]*which is",
        ]
        for pattern in risk_patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                try:
                    risk = int(match.group(1))
                    if 1 <= risk <= 7:
                        metadata.risk_level = risk
                        break
                except ValueError:
                    pass

        # Distribution
        if re.search(r"\baccumulating\b", text, re.IGNORECASE):
            metadata.distribution = "Accumulating"
        elif re.search(r"\bdistributing\b", text, re.IGNORECASE):
            metadata.distribution = "Distributing"

        # Replication
        if re.search(r"\bphysical\b", text, re.IGNORECASE):
            metadata.replication = "Physical"
        elif re.search(r"\bsynthetic\b", text, re.IGNORECASE):
            metadata.replication = "Synthetic"

        return metadata if metadata.ter is not None else None


# =============================================================================
# yfinance Fetcher (US ETFs + Fallback)
# =============================================================================


class YFinanceFetcher(BaseFetcher):
    """
    Fetches metadata from yfinance API.

    Supports: US ETFs (primary), any ticker (fallback)
    No PDF parsing required.
    """

    def __init__(self, etf_only: bool = True):
        """
        Args:
            etf_only: If True, only fetch for securities with quoteType=ETF
        """
        self.etf_only = etf_only

    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        # Can handle any ticker, or US ISINs
        if ticker:
            return True
        return bool(isin and isin.upper().startswith("US"))

    def fetch(self, isin: str | None, ticker: str | None) -> ETFMetadata | None:
        if not ticker:
            return None

        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info

            # Check quote type
            quote_type = info.get("quoteType", "").upper()
            if self.etf_only and quote_type != "ETF":
                logging.debug(f"{ticker} is not an ETF (quoteType={quote_type})")
                return None

            # Build metadata
            expense_ratio = info.get("netExpenseRatio")
            ter = round(expense_ratio, 4) if expense_ratio is not None else None

            metadata = ETFMetadata(
                isin=isin or ticker,
                ticker=ticker,
                name=info.get("longName") or info.get("shortName"),
                ter=ter,
                fund_family=info.get("fundFamily"),
                fund_currency=info.get("currency"),
                distribution="Distributing" if info.get("dividendYield") else None,
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
            )

            # Return if we have at least a name
            return metadata if metadata.name else None

        except Exception as e:
            logging.debug(f"yfinance fetch error for {ticker}: {e}")
            return None


# =============================================================================
# Stock Info Fetcher
# =============================================================================


class StockInfoFetcher(BaseFetcher):
    """
    Fetches stock metadata from yfinance API.

    Provides: sector, industry, market cap, P/E ratio, dividend yield.
    """

    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        return bool(ticker)

    def fetch(self, isin: str | None, ticker: str | None) -> ETFMetadata | None:
        if not ticker:
            return None

        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info
            quote_type = info.get("quoteType", "").upper()

            # Skip ETFs - they're handled by other fetchers
            if quote_type == "ETF":
                return None

            name = info.get("longName") or info.get("shortName")
            if not name:
                return None

            # Format market cap
            market_cap = info.get("marketCap")
            if market_cap:
                if market_cap >= 1e12:
                    market_cap_str = f"${market_cap / 1e12:.2f}T"
                elif market_cap >= 1e9:
                    market_cap_str = f"${market_cap / 1e9:.2f}B"
                elif market_cap >= 1e6:
                    market_cap_str = f"${market_cap / 1e6:.2f}M"
                else:
                    market_cap_str = f"${market_cap:,.0f}"
            else:
                market_cap_str = None

            # Format P/E ratio
            pe = info.get("trailingPE")
            pe_str = f"{pe:.2f}" if pe else None

            # Format dividend yield (use trailing, it's a proper decimal)
            div_yield = info.get("trailingAnnualDividendYield")
            div_str = f"{div_yield * 100:.2f}%" if div_yield else None

            # Use ETFMetadata with stock-specific fields in a dict
            # We'll store extra fields that the modal can display
            metadata = ETFMetadata(
                isin=isin or ticker,
                ticker=ticker,
                name=name,
                fund_currency=info.get("currency"),
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
            )

            # Add stock-specific fields as attributes (modal will read from dict)
            metadata._stock_info = {
                "quote_type": quote_type,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "country": info.get("country"),
                "market_cap": market_cap_str,
                "pe_ratio": pe_str,
                "dividend_yield": div_str,
            }

            return metadata

        except Exception as e:
            logging.debug(f"Stock info fetch error for {ticker}: {e}")
            return None


# =============================================================================
# Fetcher Registry
# =============================================================================

# Order matters: more specific fetchers first
FETCHERS: list[BaseFetcher] = [
    VanguardFetcher(),  # EU Vanguard (IE ISINs)
    YFinanceFetcher(etf_only=True),  # US ETFs
    StockInfoFetcher(),  # Stocks
    YFinanceFetcher(etf_only=False),  # Fallback for ETCs, etc.
]


def register_fetcher(fetcher: BaseFetcher, priority: int = -1) -> None:
    """
    Register a new fetcher.

    Args:
        fetcher: Fetcher instance
        priority: Index to insert at (-1 = append at end)
    """
    if priority < 0:
        FETCHERS.append(fetcher)
    else:
        FETCHERS.insert(priority, fetcher)


# =============================================================================
# Public API
# =============================================================================


def get_etf_metadata(
    isin: str | None = None,
    ticker: str | None = None,
    db_manager=None,
    skip_cache: bool = False,
) -> ETFMetadata | None:
    """
    Fetch ETF metadata for the given ISIN or ticker.

    Tries registered fetchers in order until one succeeds.
    Results are cached for 30 days if db_manager is provided.

    Args:
        isin: ISIN (required for EU ETFs)
        ticker: Ticker symbol (required for US ETFs)
        db_manager: Optional DbManager for caching
        skip_cache: Bypass cache if True

    Returns:
        ETFMetadata or None
    """
    if not isin and not ticker:
        return None

    # Normalize
    if isin:
        isin = isin.upper().strip()
    if ticker:
        ticker = ticker.upper().strip()

    cache_key = isin or ticker

    # Check cache
    if db_manager and not skip_cache:
        if cached := db_manager.get_etf_metadata(cache_key):
            logging.debug(f"ETF metadata cache hit for {cache_key}")
            return ETFMetadata.from_dict(cached)

    # Try fetchers in order
    result = None
    for fetcher in FETCHERS:
        if fetcher.can_handle(isin, ticker):
            try:
                result = fetcher.fetch(isin, ticker)
                if result:
                    logging.info(
                        f"ETF metadata for {cache_key} via {fetcher.__class__.__name__}"
                    )
                    break
            except Exception as e:
                logging.warning(f"Fetcher {fetcher.__class__.__name__} failed: {e}")

    # Cache result
    if result and db_manager:
        db_manager.save_etf_metadata(cache_key, ticker, result.to_dict())

    return result


def is_supported_isin(isin: str | None) -> bool:
    """Check if any fetcher can handle this ISIN."""
    if not isin:
        return False
    isin = isin.upper().strip()
    return any(f.can_handle(isin, None) for f in FETCHERS)
