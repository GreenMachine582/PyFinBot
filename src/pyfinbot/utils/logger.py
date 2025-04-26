
import logging
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from os import listdir, makedirs, path, remove as os_remove

_logger = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def _validateLogLevel(log_level: str):
    """Validate log level."""
    if log_level.lower() not in ["debug", "info", "warning", "error", "critical"]:
        raise ValueError(f"Invalid log level: {log_level}")


def _buildLogDirectory(logs_dir: str = "", add_file_handler: bool = True):
    """Build log directory if not exists."""
    if not add_file_handler:
        return
    if not logs_dir:
        raise ValueError("No log directory specified.")
    makedirs(logs_dir, exist_ok=True)


class LoggerHandler:
    DEFAULT_CONFIG = {
        "ext": "log",
        "log_level": "INFO",
        "add_console_handler": True,
        "add_file_handler": False,
        "add_instance": True,
        "add_time_stamp": True,
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "age_limit": 60 * 60 * 24 * 7  # 7 days
    }

    def __init__(self, logs_dir: str = "", **kwargs):
        self.logs_dir = logs_dir

        self.config = {**self.DEFAULT_CONFIG, **kwargs}

        # Validate config
        ext = self.config["ext"]
        self.config["ext"] = ext.strip(".")
        _validateLogLevel(self.config["log_level"])

        # Build log directory and logger
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _buildLogDirectory(self.logs_dir, self.config["add_file_handler"])

        # Clean old logs if applicable
        if self.logs_dir:
            self.cleanLogs()

        self.logger = self._buildLogger()

    def _getLogFileName(self, level: str) -> str:
        """Constructs the filename of the log file."""
        names = [self.config.get("project_name", "project")]
        if self.config["add_instance"] and self.config.get("instance"):
            names.append(self.config.get("instance"))
        names.append(level)
        if self.config["add_time_stamp"]:
            names.append(self.timestamp)
        names = filter(lambda x: x, names)
        return f"{'_'.join(names)}.{self.config['ext']}"

    def _buildLogger(self):
        """Build the logger by creating and attaching handlers."""
        log_formatter = logging.Formatter("%(asctime)s <%(levelname)s> %(message)s  \t(%(name)s.%(funcName)s)")
        # logger = logging.getLogger(self.project_name if self.project_name else __name__)
        logger = logging.getLogger()  # Root logger
        logger.handlers = []
        logger.setLevel(logging.DEBUG)

        # File loggers
        if self.logs_dir and self.config["add_file_handler"]:
            max_bytes, backup_count = self.config["max_bytes"], self.config["backup_count"]
            for level in ['debug', 'info', 'warning']:
                file_path = path.abspath(f"{self.logs_dir}/" + self._getLogFileName(level))
                file_handler = RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backup_count)
                file_handler.setLevel(getattr(logging, level.upper()))
                file_handler.setFormatter(log_formatter)
                logger.addHandler(file_handler)

        # Console logger
        if self.config["add_console_handler"]:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, self.config["log_level"].upper()))
            console_handler.setFormatter(log_formatter)
            logger.addHandler(console_handler)

        return logger

    def cleanLogs(self):
        """Remove old log files (clean cache)"""
        now = time.time()
        age_limit = self.config["age_limit"]

        for filename in listdir(self.logs_dir):
            file_path = path.abspath(f"{self.logs_dir}/" + filename)
            if not path.isfile(file_path) or not filename.endswith(self.config["ext"]):
                continue  # Not expected log file or ext
            creation_time = path.getctime(file_path)
            if now - creation_time < age_limit:
                continue  # Not aged enough
            # Remove aged files
            try:
                os_remove(file_path)
                _logger.debug(f"Deleted old log file: {filename}")
            except PermissionError:
                _logger.warning(f"Failed to delete old log file due to permissions: {filename}")

    def getLogger(self):
        return self.logger

    def close(self):
        """Shut down the logger and close all handlers."""
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)
        _logger.debug("Logger closed successfully.")
