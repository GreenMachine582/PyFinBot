"""Logging through greentechhub-fastapi's register_logging (v0.15): the app's
JSON log lines are tagged with the service and version, and uvicorn's own
loggers go through the same root handler (uvicorn=True)."""
import json
import logging

from greentechhub_core.logging import JSONFormatter

from pyfinbot import version


def test_log_lines_carry_service_and_version():
    import pyfinbot.pyfinbot  # noqa: F401

    formatters = [h.formatter for h in logging.getLogger().handlers if isinstance(h.formatter, JSONFormatter)]
    assert formatters
    record = logging.LogRecord("pyfinbot.test", logging.INFO, __file__, 1, "hello", None, None)
    line = json.loads(formatters[0].format(record))
    assert line["service"] == "pyfinbot"
    assert line["version"] == version.VERSION
    assert line["message"] == "hello"


def test_uvicorn_loggers_propagate_to_the_json_root():
    import pyfinbot.pyfinbot  # noqa: F401

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        assert log.propagate and not log.handlers, name
