import logging
import threading
from textual.app import App

class TextualHandler(logging.Handler):
    """
    A custom logging handler that forwards records to a Textual app's notification system.
    This allows any module in the application to send user-facing notifications
    using the standard logging library.
    """

    def __init__(self, app: App):
        """
        Initializes the handler.

        Args:
            app: The Textual App instance to which notifications will be sent.
        """
        super().__init__()
        self.app = app

    def emit(self, record: logging.LogRecord):
        """
        Processes a log record and displays it as a notification in the Textual app.
        This method is thread-safe.
        """
        try:
            # Format the message using the handler's formatter
            message = self.format(record)
            
            # Map logging levels to notification severities
            severity = "information"
            if record.levelno >= logging.ERROR:
                severity = "error"
            elif record.levelno >= logging.WARNING:
                severity = "warning"
            
            # FIX: Always use call_from_thread. This is the canonical way to
            # schedule a callback on the main event loop thread from any thread,
            # including the main one. It ensures thread-safety without complex checks.
            try:
                self.app.call_from_thread(
                    self.app.notify,
                    message,
                    title=record.levelname.capitalize(),
                    severity=severity,
                    timeout=8
                )
            except RuntimeError:
                # This can happen if a worker thread tries to log a message
                # after the app has already shut down. It's safe to ignore.
                pass
        except Exception:
            self.handleError(record)