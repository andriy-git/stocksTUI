"""
Unit tests for the ticker metadata provider.
"""

import unittest
from unittest.mock import MagicMock, patch

from stockstui.data_providers.ticker_info_provider import (
    FETCHERS,
    BaseFetcher,
    TickerMetadata,
    VanguardFetcher,
    YFinanceFetcher,
    get_etf_metadata,
    is_supported_isin,
    register_fetcher,
)
from stockstui.ui.etf_info_modal import extract_isin_from_note


class TestISINExtraction(unittest.TestCase):
    """Tests for ISIN extraction from note fields."""

    def test_extract_isin_from_parentheses(self):
        note = "Vanguard LifeStrategy 60% (IE00BMVB5P51) - 40%"
        self.assertEqual(extract_isin_from_note(note), "IE00BMVB5P51")

    def test_extract_isin_german(self):
        note = "Xetra-Gold ETC (DE000A0S9GB0) - 16.5%"
        self.assertEqual(extract_isin_from_note(note), "DE000A0S9GB0")

    def test_extract_isin_none(self):
        self.assertIsNone(extract_isin_from_note(None))
        self.assertIsNone(extract_isin_from_note(""))
        self.assertIsNone(extract_isin_from_note("No ISIN here"))


class TestISINSupportDetection(unittest.TestCase):
    """Tests for ISIN support detection."""

    def test_irish_isin_supported(self):
        self.assertTrue(is_supported_isin("IE00BK5BQT80"))
        self.assertTrue(is_supported_isin("ie00bk5bqt80"))

    def test_empty_none_not_supported(self):
        self.assertFalse(is_supported_isin(""))
        self.assertFalse(is_supported_isin(None))


class TestTickerMetadata(unittest.TestCase):
    """Tests for TickerMetadata class."""

    def test_to_dict_excludes_none(self):
        metadata = TickerMetadata(ticker="AAPL", name="Apple", ter=None, sector="Tech")
        d = metadata.to_dict()
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["sector"], "Tech")
        self.assertNotIn("ter", d)

    def test_from_dict(self):
        d = {"ticker": "AAPL", "name": "Apple", "sector": "Tech"}
        metadata = TickerMetadata.from_dict(d)
        self.assertEqual(metadata.ticker, "AAPL")
        self.assertEqual(metadata.sector, "Tech")


class TestVanguardFetcher(unittest.TestCase):
    """Tests for Vanguard PDF fetcher."""

    def setUp(self):
        self.fetcher = VanguardFetcher()

    def test_can_handle_irish_isin(self):
        self.assertTrue(self.fetcher.can_handle("IE00BK5BQT80", None))
        self.assertFalse(self.fetcher.can_handle("DE000A0S9GB0", None))
        self.assertFalse(self.fetcher.can_handle(None, "VOO"))

    @patch.object(VanguardFetcher, "_download_pdf")
    @patch.object(VanguardFetcher, "_extract_text")
    def test_fetch_success(self, mock_extract, mock_download):
        mock_download.return_value = b"%PDF"
        mock_extract.return_value = """
        Key Information Document
        Vanguard FTSE All-World UCITS ETF
        Management fees and other 0.19% of the value
        classified this Fund as 4 out of 7
        accumulating physical
        """

        metadata = self.fetcher.fetch("IE00BK5BQT80", "VWCE.DE")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.19)
        self.assertEqual(metadata.risk_level, 4)
        self.assertEqual(metadata.distribution, "Accumulating")
        self.assertEqual(metadata.replication, "Physical")

    @patch.object(VanguardFetcher, "_download_pdf")
    def test_fetch_download_failure(self, mock_download):
        mock_download.return_value = None
        self.assertIsNone(self.fetcher.fetch("IE00BK5BQT80", None))


class TestYFinanceFetcher(unittest.TestCase):
    """Tests for yfinance fetcher."""

    def setUp(self):
        self.fetcher = YFinanceFetcher()

    def test_can_handle(self):
        self.assertTrue(self.fetcher.can_handle(None, "VOO"))
        self.assertTrue(self.fetcher.can_handle(None, "AAPL"))
        self.assertFalse(self.fetcher.can_handle(None, None))

    @patch("yfinance.Ticker")
    def test_fetch_etf(self, mock_ticker):
        mock_ticker.return_value.info = {
            "quoteType": "ETF",
            "longName": "Vanguard S&P 500 ETF",
            "netExpenseRatio": 0.03,
            "fundFamily": "Vanguard",
            "currency": "USD",
        }

        metadata = self.fetcher.fetch(None, "VOO")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.03)
        self.assertEqual(metadata.fund_family, "Vanguard")
        self.assertIsNone(metadata.sector)

    @patch("yfinance.Ticker")
    def test_fetch_stock(self, mock_ticker):
        mock_ticker.return_value.info = {
            "quoteType": "EQUITY",
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3000000000000,
            "trailingPE": 30.5,
            "trailingAnnualDividendYield": 0.005,
            "currency": "USD",
        }

        metadata = self.fetcher.fetch(None, "AAPL")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.sector, "Technology")
        self.assertEqual(metadata.market_cap, "$3.00T")
        self.assertEqual(metadata.pe_ratio, "30.50")
        self.assertEqual(metadata.dividend_yield, "0.50%")
        self.assertIsNone(metadata.ter)

    @patch("yfinance.Ticker")
    def test_fetch_no_name_returns_none(self, mock_ticker):
        mock_ticker.return_value.info = {"quoteType": "EQUITY"}
        self.assertIsNone(self.fetcher.fetch(None, "XXX"))

    @patch("yfinance.Ticker")
    def test_fetch_handles_exception(self, mock_ticker):
        mock_ticker.side_effect = Exception("Network error")
        self.assertIsNone(self.fetcher.fetch(None, "VOO"))


class TestFetcherRegistry(unittest.TestCase):
    """Tests for fetcher registration."""

    def test_default_fetchers(self):
        self.assertTrue(any(isinstance(f, VanguardFetcher) for f in FETCHERS))
        self.assertTrue(any(isinstance(f, YFinanceFetcher) for f in FETCHERS))

    def test_register_fetcher(self):
        class DummyFetcher(BaseFetcher):
            def can_handle(self, isin, ticker):
                return False

            def fetch(self, isin, ticker):
                return None

        original_count = len(FETCHERS)
        dummy = DummyFetcher()
        register_fetcher(dummy)

        self.assertEqual(len(FETCHERS), original_count + 1)
        FETCHERS.remove(dummy)  # Cleanup


class TestGetTickerMetadata(unittest.TestCase):
    """Tests for main API function."""

    def test_empty_inputs(self):
        self.assertIsNone(get_etf_metadata(isin=None, ticker=None))

    def test_cache_hit(self):
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = {
            "ticker": "VWCE.DE",
            "name": "Vanguard ETF",
            "ter": 0.19,
        }

        metadata = get_etf_metadata(isin="IE00BK5BQT80", db_manager=mock_db)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.19)
        mock_db.get_etf_metadata.assert_called_once()

    @patch.object(VanguardFetcher, "fetch")
    def test_cache_miss_saves(self, mock_fetch):
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = None
        mock_fetch.return_value = TickerMetadata(ticker="VWCE.DE", ter=0.19)

        get_etf_metadata(isin="IE00BK5BQT80", ticker="VWCE.DE", db_manager=mock_db)

        mock_db.save_etf_metadata.assert_called_once()

    @patch.object(VanguardFetcher, "fetch")
    def test_skip_cache(self, mock_fetch):
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = {"ticker": "X", "ter": 0.1}
        mock_fetch.return_value = TickerMetadata(ticker="VWCE.DE", ter=0.20)

        metadata = get_etf_metadata(
            isin="IE00BK5BQT80", db_manager=mock_db, skip_cache=True
        )

        mock_fetch.assert_called_once()
        self.assertEqual(metadata.ter, 0.20)


if __name__ == "__main__":
    unittest.main()
