"""
Ticker Metadata Provider

Fetches metadata for stocks and ETFs from various sources.

Supported sources:
- Vanguard PRIIPs KID PDFs (EU ETFs with IE* ISINs)
- yfinance API (US ETFs, stocks, fallback)

To add a new provider:
1. Create a class inheriting from BaseFetcher
2. Implement can_handle() and fetch()
3. Add instance to FETCHERS list

Optional dependency:
- pypdf: Required for EU ETF PDF parsing (optional)
"""

import logging
import re
import tempfile
from abc import ABC, abstractmethod

import requests


# =============================================================================
# Data Model
# =============================================================================


class TickerMetadata:
    """Metadata for stocks and ETFs."""

    def __init__(
        self,
        ticker: str,
        name: str | None = None,
        isin: str | None = None,
        currency: str | None = None,
        source_url: str | None = None,
        # ETF fields
        ter: float | None = None,
        risk_level: int | None = None,
        distribution: str | None = None,
        replication: str | None = None,
        fund_family: str | None = None,
        # Stock fields
        sector: str | None = None,
        industry: str | None = None,
        country: str | None = None,
        market_cap: str | None = None,
        pe_ratio: str | None = None,
        dividend_yield: str | None = None,
        quote_type: str | None = None,
    ):
        self.ticker = ticker
        self.name = name
        self.isin = isin
        self.currency = currency
        self.source_url = source_url
        # ETF
        self.ter = ter
        self.risk_level = risk_level
        self.distribution = distribution
        self.replication = replication
        self.fund_family = fund_family
        # Stock
        self.sector = sector
        self.industry = industry
        self.country = country
        self.market_cap = market_cap
        self.pe_ratio = pe_ratio
        self.dividend_yield = dividend_yield
        self.quote_type = quote_type

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "TickerMetadata":
        return cls(
            **{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames}
        )


# =============================================================================
# Abstract Base Fetcher
# =============================================================================


class BaseFetcher(ABC):
    """Abstract base class for metadata fetchers."""

    @abstractmethod
    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        """Check if this fetcher can handle the given ISIN/ticker."""
        pass

    @abstractmethod
    def fetch(self, isin: str | None, ticker: str | None) -> TickerMetadata | None:
        """Fetch metadata. Returns None on failure."""
        pass


# =============================================================================
# Vanguard Fetcher (EU PRIIPs KID PDFs)
# =============================================================================


class VanguardFetcher(BaseFetcher):
    """
    Fetches metadata from Vanguard PRIIPs KID documents.

    URL: https://fund-docs.vanguard.com/{isin}_priipskid_en.pdf
    Supports: Irish ISINs (IE prefix)
    """

    BASE_URL = "https://fund-docs.vanguard.com"

    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        return bool(isin and isin.upper().startswith("IE"))

    def fetch(self, isin: str | None, ticker: str | None) -> TickerMetadata | None:
        if not isin:
            return None

        url = f"{self.BASE_URL}/{isin.lower()}_priipskid_en.pdf"
        pdf_content = self._download_pdf(url)
        if not pdf_content:
            return None

        text = self._extract_text(pdf_content)
        if not text:
            return None

        return self._parse(text, isin, ticker, url)

    def _download_pdf(self, url: str, timeout: int = 15) -> bytes | None:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200 and response.content[:4] == b"%PDF":
                return response.content
        except requests.RequestException as e:
            logging.debug(f"PDF download error: {url} ({e})")

    def _extract_text(self, pdf_content: bytes) -> str | None:
        try:
            from pypdf import PdfReader
        except ImportError:
            logging.warning("pypdf not installed")
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(pdf_content)
                tmp.flush()
                reader = PdfReader(tmp.name)
                return "\n".join(page.extract_text() for page in reader.pages)
        except Exception as e:
            logging.debug(f"PDF parsing error: {e}")

    def _parse(
        self, text: str, isin: str, ticker: str | None, source_url: str
    ) -> TickerMetadata | None:
        metadata = TickerMetadata(
            ticker=ticker or isin,
            isin=isin,
            source_url=source_url,
            fund_family="Vanguard",
        )

        # Fund name
        if match := re.search(
            r"Key Information Document\s*\n\s*(.+?)(?:\n|UCITS)", text, re.IGNORECASE
        ):
            metadata.name = match.group(1).strip()

        # TER
        for pattern in [
            r"Management fees and other[^%]*?(\d+[.,]\d+)\s*%",
            r"Ongoing (?:Charges?|costs?)[:\s]*(\d+[.,]\d+)\s*%",
        ]:
            if match := re.search(pattern, text, re.IGNORECASE):
                try:
                    metadata.ter = float(match.group(1).replace(",", "."))
                    break
                except ValueError:
                    pass

        # Risk level (1-7)
        if match := re.search(r"classified[^0-9]*(\d)\s*out of 7", text, re.IGNORECASE):
            try:
                risk = int(match.group(1))
                if 1 <= risk <= 7:
                    metadata.risk_level = risk
            except ValueError:
                pass

        # Distribution & Replication
        if re.search(r"\baccumulating\b", text, re.IGNORECASE):
            metadata.distribution = "Accumulating"
        elif re.search(r"\bdistributing\b", text, re.IGNORECASE):
            metadata.distribution = "Distributing"

        if re.search(r"\bphysical\b", text, re.IGNORECASE):
            metadata.replication = "Physical"
        elif re.search(r"\bsynthetic\b", text, re.IGNORECASE):
            metadata.replication = "Synthetic"

        return metadata if metadata.ter is not None else None


# =============================================================================
# yfinance Fetcher
# =============================================================================


class YFinanceFetcher(BaseFetcher):
    """
    Fetches metadata from yfinance API.
    Works for US ETFs, stocks, and as fallback for other securities.
    """

    def can_handle(self, isin: str | None, ticker: str | None) -> bool:
        return bool(ticker)

    def fetch(self, isin: str | None, ticker: str | None) -> TickerMetadata | None:
        if not ticker:
            return None

        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info
            quote_type = info.get("quoteType", "").upper()
            name = info.get("longName") or info.get("shortName")

            if not name:
                return None

            metadata = TickerMetadata(
                ticker=ticker,
                name=name,
                isin=isin,
                currency=info.get("currency"),
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
                quote_type=quote_type,
            )

            if quote_type == "ETF":
                # ETF-specific fields
                expense_ratio = info.get("netExpenseRatio")
                if expense_ratio is not None:
                    metadata.ter = round(expense_ratio, 4)
                metadata.fund_family = info.get("fundFamily")
                if info.get("dividendYield"):
                    metadata.distribution = "Distributing"
            else:
                # Stock-specific fields
                metadata.sector = info.get("sector")
                metadata.industry = info.get("industry")
                metadata.country = info.get("country")

                # Format market cap
                mc = info.get("marketCap")
                if mc:
                    if mc >= 1e12:
                        metadata.market_cap = f"${mc / 1e12:.2f}T"
                    elif mc >= 1e9:
                        metadata.market_cap = f"${mc / 1e9:.2f}B"
                    elif mc >= 1e6:
                        metadata.market_cap = f"${mc / 1e6:.2f}M"

                # P/E ratio
                pe = info.get("trailingPE")
                if pe:
                    metadata.pe_ratio = f"{pe:.2f}"

                # Dividend yield
                div = info.get("trailingAnnualDividendYield")
                if div:
                    metadata.dividend_yield = f"{div * 100:.2f}%"

            return metadata

        except Exception as e:
            logging.debug(f"yfinance fetch error for {ticker}: {e}")


# =============================================================================
# Registry & Public API
# =============================================================================

FETCHERS: list[BaseFetcher] = [
    VanguardFetcher(),
    YFinanceFetcher(),
]


def register_fetcher(fetcher: BaseFetcher, priority: int = -1) -> None:
    """Register a new fetcher at given priority (-1 = end)."""
    if priority < 0:
        FETCHERS.append(fetcher)
    else:
        FETCHERS.insert(priority, fetcher)


def get_etf_metadata(
    isin: str | None = None,
    ticker: str | None = None,
    db_manager=None,
    skip_cache: bool = False,
) -> TickerMetadata | None:
    """
    Fetch metadata for the given ISIN or ticker.

    Args:
        isin: ISIN (for EU ETFs)
        ticker: Ticker symbol
        db_manager: Optional DbManager for caching (30 days)
        skip_cache: Bypass cache if True

    Returns:
        TickerMetadata or None
    """
    if not isin and not ticker:
        return None

    if isin:
        isin = isin.upper().strip()
    if ticker:
        ticker = ticker.upper().strip()

    cache_key = isin or ticker

    # Check cache
    if db_manager and not skip_cache:
        if cached := db_manager.get_etf_metadata(cache_key):
            logging.debug(f"Cache hit for {cache_key}")
            return TickerMetadata.from_dict(cached)

    # Try fetchers
    result = None
    for fetcher in FETCHERS:
        if fetcher.can_handle(isin, ticker):
            try:
                result = fetcher.fetch(isin, ticker)
                if result:
                    logging.info(
                        f"Fetched {cache_key} via {fetcher.__class__.__name__}"
                    )
                    break
            except Exception as e:
                logging.warning(f"{fetcher.__class__.__name__} failed: {e}")

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
