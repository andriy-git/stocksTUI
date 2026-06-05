import unittest
from unittest.mock import MagicMock
import logging
from stockstui.log_handler import TextualHandler


class TestTextualHandlerSuppression(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock()
        self.app.config = MagicMock()
        self.app.config.get_setting = MagicMock()
        self.handler = TextualHandler(self.app)
        self.record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test Msg",
            args=(),
            exc_info=None,
        )

    def test_logs_not_suppressed_by_default(self):
        # Default behavior (False or missing setting) -> should notify
        self.app.config.get_setting.return_value = False
        self.handler.emit(self.record)
        # Note: emit calls app.call_from_thread(self.app.notify, ...)
        self.app.call_from_thread.assert_called()

    def test_logs_suppressed_when_enabled(self):
        # Setting True -> should NOT notify
        self.app.config.get_setting.return_value = True
        self.handler.emit(self.record)
        self.app.call_from_thread.assert_not_called()
