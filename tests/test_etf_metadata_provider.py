"""
Unit tests for the ETF metadata provider.

Tests cover:
- ISIN support detection
- ETFMetadata dataclass serialization
- ISIN extraction from note fields
- Graceful failure handling
- Fetcher implementations (mocked)
- Database caching
"""

import unittest
from unittest.mock import MagicMock, patch

from stockstui.data_providers.etf_metadata_provider import (
    FETCHERS,
    BaseFetcher,
    ETFMetadata,
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
        """ISIN in parentheses should be extracted."""
        note = "Vanguard LifeStrategy 60% (IE00BMVB5P51) - 40%"
        self.assertEqual(extract_isin_from_note(note), "IE00BMVB5P51")

    def test_extract_isin_german(self):
        """German ISIN should be extracted."""
        note = "Xetra-Gold ETC (DE000A0S9GB0) - 16.5%"
        self.assertEqual(extract_isin_from_note(note), "DE000A0S9GB0")

    def test_extract_isin_no_parentheses(self):
        """ISIN without parentheses should be extracted."""
        note = "Some ETF IE00BG0SKF03 with info"
        self.assertEqual(extract_isin_from_note(note), "IE00BG0SKF03")

    def test_extract_isin_none_input(self):
        """None input should return None."""
        self.assertIsNone(extract_isin_from_note(None))

    def test_extract_isin_empty_string(self):
        """Empty string should return None."""
        self.assertIsNone(extract_isin_from_note(""))

    def test_extract_isin_no_isin_present(self):
        """Note without ISIN should return None."""
        self.assertIsNone(extract_isin_from_note("Just a regular note"))


class TestISINSupportDetection(unittest.TestCase):
    """Tests for ISIN support detection."""

    def test_irish_isin_supported(self):
        """Irish ISINs (IE prefix) should be supported."""
        self.assertTrue(is_supported_isin("IE00BK5BQT80"))

    def test_irish_isin_lowercase(self):
        """Lowercase Irish ISINs should be supported."""
        self.assertTrue(is_supported_isin("ie00bk5bqt80"))

    def test_us_isin_supported(self):
        """US ISINs should be supported (via yfinance)."""
        self.assertTrue(is_supported_isin("US9229083632"))

    def test_empty_isin(self):
        """Empty ISIN should not be supported."""
        self.assertFalse(is_supported_isin(""))

    def test_none_isin(self):
        """None ISIN should not be supported."""
        self.assertFalse(is_supported_isin(None))


class TestETFMetadataDataclass(unittest.TestCase):
    """Tests for ETFMetadata dataclass."""

    def test_to_dict(self):
        """to_dict should return all fields."""
        metadata = ETFMetadata(
            isin="IE00BK5BQT80",
            ticker="VWCE.DE",
            ter=0.19,
            risk_level=4,
            distribution="Accumulating",
            fund_family="Vanguard",
        )
        d = metadata.to_dict()
        self.assertEqual(d["isin"], "IE00BK5BQT80")
        self.assertEqual(d["ticker"], "VWCE.DE")
        self.assertEqual(d["ter"], 0.19)
        self.assertEqual(d["risk_level"], 4)

    def test_from_dict(self):
        """from_dict should restore metadata."""
        d = {
            "isin": "IE00BK5BQT80",
            "ticker": "VWCE.DE",
            "ter": 0.19,
            "risk_level": 4,
            "distribution": "Accumulating",
            "fund_family": "Vanguard",
        }
        metadata = ETFMetadata.from_dict(d)
        self.assertEqual(metadata.isin, "IE00BK5BQT80")
        self.assertEqual(metadata.ter, 0.19)
        self.assertEqual(metadata.risk_level, 4)

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict should ignore unknown fields."""
        d = {
            "isin": "IE00BK5BQT80",
            "unknown_field": "should be ignored",
        }
        metadata = ETFMetadata.from_dict(d)
        self.assertEqual(metadata.isin, "IE00BK5BQT80")


class TestVanguardFetcher(unittest.TestCase):
    """Tests for Vanguard PDF fetcher."""

    def setUp(self):
        self.fetcher = VanguardFetcher()

    def test_can_handle_irish_isin(self):
        """Should handle Irish ISINs."""
        self.assertTrue(self.fetcher.can_handle("IE00BK5BQT80", None))

    def test_cannot_handle_german_isin(self):
        """Should not handle German ISINs."""
        self.assertFalse(self.fetcher.can_handle("DE000A0S9GB0", None))

    def test_cannot_handle_none(self):
        """Should not handle None ISIN."""
        self.assertFalse(self.fetcher.can_handle(None, "VWCE.DE"))

    def test_build_url(self):
        """URL should be built correctly."""
        url = self.fetcher._build_url("IE00BK5BQT80")
        self.assertEqual(
            url, "https://fund-docs.vanguard.com/ie00bk5bqt80_priipskid_en.pdf"
        )

    @patch.object(VanguardFetcher, "_download_pdf")
    @patch.object(VanguardFetcher, "_extract_text_from_pdf")
    def test_fetch_success(self, mock_extract, mock_download):
        """Successful fetch should return metadata."""
        mock_download.return_value = b"%PDF-1.4 fake pdf content"
        mock_extract.return_value = """
        Key Information Document
        Vanguard FTSE All-World UCITS ETF
        Management fees and other 0.19% of the value
        We have classified this Fund as 4 out of 7, which is a medium risk class.
        accumulating
        physical
        """

        metadata = self.fetcher.fetch("IE00BK5BQT80", "VWCE.DE")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.19)
        self.assertEqual(metadata.risk_level, 4)
        self.assertEqual(metadata.distribution, "Accumulating")
        self.assertEqual(metadata.replication, "Physical")

    @patch.object(VanguardFetcher, "_download_pdf")
    def test_fetch_download_failure(self, mock_download):
        """Failed download should return None."""
        mock_download.return_value = None
        metadata = self.fetcher.fetch("IE00BK5BQT80", "VWCE.DE")
        self.assertIsNone(metadata)


class TestYFinanceFetcher(unittest.TestCase):
    """Tests for yfinance fetcher."""

    def test_can_handle_any_ticker(self):
        """Should handle any ticker."""
        fetcher = YFinanceFetcher(etf_only=True)
        self.assertTrue(fetcher.can_handle(None, "VOO"))

    def test_can_handle_us_isin(self):
        """Should handle US ISINs."""
        fetcher = YFinanceFetcher(etf_only=True)
        self.assertTrue(fetcher.can_handle("US9229083632", None))

    @patch("yfinance.Ticker")
    def test_fetch_etf_success(self, mock_ticker):
        """Successfully fetch US ETF metadata."""
        mock_ticker.return_value.info = {
            "quoteType": "ETF",
            "netExpenseRatio": 0.03,
            "longName": "Vanguard S&P 500 ETF",
            "fundFamily": "Vanguard",
            "currency": "USD",
        }

        fetcher = YFinanceFetcher(etf_only=True)
        metadata = fetcher.fetch(None, "VOO")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.03)
        self.assertEqual(metadata.fund_family, "Vanguard")

    @patch("yfinance.Ticker")
    def test_fetch_etf_only_rejects_equity(self, mock_ticker):
        """etf_only=True should reject non-ETFs."""
        mock_ticker.return_value.info = {
            "quoteType": "EQUITY",
            "longName": "Apple Inc.",
        }

        fetcher = YFinanceFetcher(etf_only=True)
        metadata = fetcher.fetch(None, "AAPL")

        self.assertIsNone(metadata)

    @patch("yfinance.Ticker")
    def test_fetch_allows_non_etf(self, mock_ticker):
        """etf_only=False should accept non-ETFs."""
        mock_ticker.return_value.info = {
            "quoteType": "EQUITY",
            "longName": "Xetra-Gold",
            "currency": "EUR",
        }

        fetcher = YFinanceFetcher(etf_only=False)
        metadata = fetcher.fetch(None, "4GLD.DE")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "Xetra-Gold")

    @patch("yfinance.Ticker")
    def test_fetch_partial_data(self, mock_ticker):
        """Should return partial data when TER unavailable."""
        mock_ticker.return_value.info = {
            "quoteType": "ETF",
            "longName": "Some ETF",
            # No netExpenseRatio
        }

        fetcher = YFinanceFetcher(etf_only=True)
        metadata = fetcher.fetch(None, "SOME")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "Some ETF")
        self.assertIsNone(metadata.ter)

    @patch("yfinance.Ticker")
    def test_fetch_handles_exception(self, mock_ticker):
        """Exceptions should be handled gracefully."""
        mock_ticker.side_effect = Exception("Network error")

        fetcher = YFinanceFetcher(etf_only=True)
        metadata = fetcher.fetch(None, "VOO")

        self.assertIsNone(metadata)


class TestFetcherRegistry(unittest.TestCase):
    """Tests for fetcher registration."""

    def test_default_fetchers_registered(self):
        """Default fetchers should be registered."""
        self.assertTrue(len(FETCHERS) >= 2)
        self.assertTrue(any(isinstance(f, VanguardFetcher) for f in FETCHERS))
        self.assertTrue(any(isinstance(f, YFinanceFetcher) for f in FETCHERS))

    def test_register_fetcher_append(self):
        """register_fetcher should append by default."""

        class DummyFetcher(BaseFetcher):
            def can_handle(self, isin, ticker):
                return False

            def fetch(self, isin, ticker):
                return None

        original_count = len(FETCHERS)
        dummy = DummyFetcher()
        register_fetcher(dummy)

        self.assertEqual(len(FETCHERS), original_count + 1)
        self.assertIs(FETCHERS[-1], dummy)

        # Cleanup
        FETCHERS.remove(dummy)


class TestGetETFMetadata(unittest.TestCase):
    """Tests for the main get_etf_metadata function."""

    def test_empty_inputs_return_none(self):
        """Empty ISIN and ticker should return None."""
        self.assertIsNone(get_etf_metadata(isin=None, ticker=None))
        self.assertIsNone(get_etf_metadata(isin="", ticker=""))

    def test_cache_hit_returns_cached_data(self):
        """Cache hit should return cached data without fetching."""
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = {
            "isin": "IE00BK5BQT80",
            "ticker": "VWCE.DE",
            "ter": 0.19,
        }

        metadata = get_etf_metadata(
            isin="IE00BK5BQT80", ticker="VWCE.DE", db_manager=mock_db
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.ter, 0.19)
        mock_db.get_etf_metadata.assert_called_once()

    @patch.object(VanguardFetcher, "fetch")
    def test_cache_miss_fetches_and_saves(self, mock_fetch):
        """Cache miss should fetch and save to cache."""
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = None
        mock_fetch.return_value = ETFMetadata(
            isin="IE00BK5BQT80", ticker="VWCE.DE", ter=0.19
        )

        metadata = get_etf_metadata(
            isin="IE00BK5BQT80", ticker="VWCE.DE", db_manager=mock_db
        )

        self.assertIsNotNone(metadata)
        mock_db.save_etf_metadata.assert_called_once()

    @patch.object(VanguardFetcher, "fetch")
    def test_skip_cache_bypasses_cache(self, mock_fetch):
        """skip_cache=True should bypass cache."""
        mock_db = MagicMock()
        mock_db.get_etf_metadata.return_value = {"isin": "IE00BK5BQT80", "ter": 0.19}
        mock_fetch.return_value = ETFMetadata(
            isin="IE00BK5BQT80", ticker="VWCE.DE", ter=0.20
        )

        metadata = get_etf_metadata(
            isin="IE00BK5BQT80", ticker="VWCE.DE", db_manager=mock_db, skip_cache=True
        )

        # Should fetch fresh data, not use cached
        mock_fetch.assert_called_once()
        self.assertEqual(metadata.ter, 0.20)


if __name__ == "__main__":
    unittest.main()
