import unittest
import pandas as pd
from textual.app import App, ComposeResult

from stockstui.ui.widgets.history_chart import HistoryChart

class HistoryChartApp(App):
    """A minimal app for testing the HistoryChart widget."""
    def __init__(self, chart_widget):
        super().__init__()
        self.chart = chart_widget

    def compose(self) -> ComposeResult:
        yield self.chart

class TestHistoryChart(unittest.IsolatedAsyncioTestCase):
    """Tests for the HistoryChart widget."""

    async def test_history_chart_with_valid_data(self):
        """Test chart rendering with a typical valid DataFrame."""
        dates = pd.to_datetime(['2025-01-01', '2025-01-02'])
        df = pd.DataFrame({'Close': [100.0, 102.5]}, index=dates)
        chart = HistoryChart(df, "1mo", id="test-chart")
        app = HistoryChartApp(chart)

        async with app.run_test() as pilot:
            await pilot.pause()
            # The chart should render without errors
            self.assertIsNotNone(chart)

    async def test_history_chart_with_empty_data(self):
        """Test chart rendering with an empty DataFrame."""
        chart = HistoryChart(pd.DataFrame(), "1mo", id="test-chart")
        app = HistoryChartApp(chart)

        async with app.run_test() as pilot:
            await pilot.pause()
            # Should render without errors
            self.assertIsNotNone(chart)


    async def test_history_chart_with_missing_close_column(self):
        """Test chart behavior with a missing 'Close' column, which should now fall back gracefully."""
        dates = pd.to_datetime(['2025-01-01'])
        df = pd.DataFrame({'Open': [100.0]}, index=dates)
        chart = HistoryChart(df, "1d", id="test-chart")
        app = HistoryChartApp(chart)

        # The widget should NOT raise a KeyError anymore, it should fall back to 'Open'
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsNotNone(chart)

    async def test_history_chart_with_nan_values(self):
        """Test chart rendering with NaN values in data."""
        dates = pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03'])
        df = pd.DataFrame({'Close': [100.0, float('nan'), 102.0]}, index=dates)
        chart = HistoryChart(df, "1mo", id="test-chart")
        app = HistoryChartApp(chart)

        async with app.run_test() as pilot:
            await pilot.pause()
            # Should render without errors
            self.assertIsNotNone(chart)