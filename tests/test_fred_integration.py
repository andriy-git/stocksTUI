import unittest
from unittest.mock import MagicMock, patch, call
from stockstui.data_providers.fred_provider import get_series_summary, BASE_URL


class TestFredIntegration(unittest.TestCase):
    @patch("stockstui.data_providers.fred_provider.requests.get")
    def test_get_series_summary(self, mock_get):
        # Mock Observations Response
        mock_response_obs = MagicMock()
        mock_response_obs.status_code = 200
        mock_response_obs.json.return_value = {
            "observations": [
                {"date": "2023-01-01", "value": "105.0"},  # Current
                {"date": "2022-12-01", "value": "104.0"},  # Prev
                # Gap
                {"date": "2022-01-01", "value": "100.0"},  # 1Y Ago
                # Gap
                {"date": "2018-01-01", "value": "90.0"},  # 5Y Ago
            ]
        }

        # Mock Info Response
        mock_response_info = MagicMock()
        mock_response_info.status_code = 200
        mock_response_info.json.return_value = {
            "seriess": [{"title": "Test Series", "units": "Index"}]
        }

        # Side effect to return different responses based on URL
        def side_effect(url, params, timeout):
            if "series/observations" in url:
                return mock_response_obs
            elif "series" in url:
                return mock_response_info
            return MagicMock()

        mock_get.side_effect = side_effect

        summary = get_series_summary("TEST", "fake_key")

        # Verify API calls were made correctly
        self.assertEqual(mock_get.call_count, 2)
        # Check that calls were made to the right endpoints (params may include additional fields)
        calls_made = [str(call) for call in mock_get.call_args_list]
        self.assertTrue(any("series/observations" in str(call) for call in calls_made))
        self.assertTrue(any("/series'" in str(call) and "observations" not in str(call) for call in calls_made))

        # Verify summary data
        self.assertEqual(summary["current"], 105.0)
        self.assertEqual(summary["change_1p"], 1.0)  # 105 - 104
        self.assertEqual(summary["change_1y"], 5.0)  # 105 - 100
        self.assertEqual(summary["change_5y"], 15.0)  # 105 - 90
        self.assertEqual(summary["title"], "Test Series")
        self.assertEqual(summary["units"], "Index")
        self.assertIn("id", summary)
        self.assertEqual(summary["id"], "TEST")

    @patch("stockstui.data_providers.fred_provider.requests.get")
    def test_get_series_summary_nans(self, mock_get):
        # Mock Observations Response with dots (Fred's N/A)
        mock_response_obs = MagicMock()
        mock_response_obs.status_code = 200
        mock_response_obs.json.return_value = {
            "observations": [
                {"date": "2023-01-01", "value": "."},  # Invalid
            ]
        }

        mock_response_info = MagicMock()
        mock_response_info.status_code = 200
        mock_response_info.json.return_value = {"seriess": []}

        mock_get.side_effect = (
            lambda url, params, timeout: mock_response_obs
            if "series/observations" in url
            else mock_response_info
        )

        summary = get_series_summary("TEST_NAN", "fake_key")
        self.assertEqual(summary["current"], "N/A")
        
        # Verify API was still called
        self.assertEqual(mock_get.call_count, 2)
        # When data is N/A, change values are also 'N/A' strings
        self.assertEqual(summary["change_1p"], "N/A")
        self.assertEqual(summary["change_1y"], "N/A")
        self.assertEqual(summary["change_5y"], "N/A")

    @patch("stockstui.data_providers.fred_provider.requests.get")
    def test_get_series_summary_missing_api_key(self, mock_get):
        """Test behavior when API key is missing."""
        # The function returns a dict with N/A values when API key is missing
        summary = get_series_summary("TEST", None)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["current"], "N/A")
        
    @patch("stockstui.data_providers.fred_provider.get_series_observations")
    def test_get_series_summary_request_exception(self, mock_obs):
        """Test behavior when request fails."""
        mock_obs.return_value = None  # Simulate failed fetch
        
        # The function handles exceptions and returns dict with N/A values
        summary = get_series_summary("TEST", "fake_key")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["current"], "N/A")
