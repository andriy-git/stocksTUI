import unittest
import logging
from unittest.mock import MagicMock

from stockstui.log_handler import TextualHandler

class TestLogHandler(unittest.TestCase):
    """Unit tests for the Textual log handler."""

    def test_log_emit_sends_notification(self):
        """Test that emitting log records calls the app's notify method."""
        mock_app = MagicMock()
        mock_app.notify = MagicMock()

        handler = TextualHandler(app=mock_app)
        handler.setFormatter(logging.Formatter('%(message)s'))

        # Create a logger and add our handler
        logger = logging.getLogger('test_logger')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # Test different log levels
        logger.info("Informational message.")
        mock_app.call_from_thread.assert_called_with(
            mock_app.notify,
            "Informational message.",
            title="Info",
            severity="information",
            timeout=8
        )

        logger.warning("A warning message.")
        mock_app.call_from_thread.assert_called_with(
            mock_app.notify,
            "A warning message.",
            title="Warning",
            severity="warning",
            timeout=8
        )

        logger.error("An error message.")
        mock_app.call_from_thread.assert_called_with(
            mock_app.notify,
            "An error message.",
            title="Error",
            severity="error",
            timeout=8
        )

        # Prevent logs from propagating to the root logger in the test runner
        logger.removeHandler(handler)
