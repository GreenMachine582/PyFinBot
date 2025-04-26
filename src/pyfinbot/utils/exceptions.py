import logging
import traceback

_logger = logging.getLogger(__name__)

__all__ = ["logExceptionHelper", "PyFinBotException"]


def logExceptionHelper(message: str, level: str = "debug", exception=Exception):
    """Log message at designated level and raise exception."""
    if level in ["", "ignore"]:  # Ignore
        return

    # Validate logger level
    if level not in ["debug", "warning", "error", "raise"]:
        raise ValueError(f"The parameter level must be either 'debug', 'warning', 'error' or 'raise', got: '{level}'")

    getattr(_logger, level)(message)  # Log message
    if level == 'raise':  # Log and raise exception
        _logger.exception(message)
        raise exception(message)


class PyFinBotException(Exception):
    def __init__(self, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.message = message

        # Capture the stack trace when the exception is instantiated
        self.stack = traceback.format_stack()[:-1]

        self.log_exception()

    def __str__(self) -> str:
        return f"{type(self).__name__}('{self.message or 'Unknown Error!'}')"

    def log_exception(self):
        """Log the exception message and its associated stack trace."""
        ignore_lines_with = {'PyCharm', '<frozen importlib._bootstrap>', '<frozen importlib._bootstrap_external>'}
        filtered_stack = filter(lambda x: all(ignore not in x for ignore in ignore_lines_with), self.stack)

        # Log the stack trace and exception
        trace_str = ''.join(filtered_stack)
        _logger.error(trace_str)
        _logger.error(self)
