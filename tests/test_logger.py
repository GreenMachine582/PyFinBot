
import os
import time
import unittest
from datetime import datetime
from os import path as os_path
from unittest.mock import patch, MagicMock

from src.pyfinbot.utils.logger import LoggerHandler, _validateLogLevel, _buildLogDirectory


class TestLoggerHandler(unittest.TestCase):

    def setUp(self):
        self.config = {
            "log_level": "info",
            "add_console_handler": False,
            "add_file_handler": False,
            "max_bytes": 1024 * 1024,  # 1MB
            "backup_count": 3,
            "age_limit": 60 * 60 * 24 * 7,  # 7 days
            "add_time_stamp": True,
            "add_instance": True,
            "ext": "log",
            "project_name": "test_project",
            "instance": "dev"
        }
        self.logs_dir = os_path.abspath("./tmp/logs")
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def test_validateLogLevel_valid_level(self):
        """Test that valid log levels do not raise an error."""
        for level in ["debug", "info", "WARNING", "error", "critical"]:
            _validateLogLevel(level)

    def test_validateLogLevel_invalid_level(self):
        """Test that invalid log levels raise a ValueError."""
        with self.assertRaises(ValueError):
            _validateLogLevel("invalid_level")

    @patch("src.pyfinbot.utils.logger.makedirs")
    def test_buildLogDirectory(self, mock_makedirs):
        """Test creating a log directory."""
        _buildLogDirectory(logs_dir=self.logs_dir, add_file_handler=True)
        mock_makedirs.assert_called_once_with(self.logs_dir, exist_ok=True)

    @patch("src.pyfinbot.utils.logger.makedirs")
    def test_buildLogDirectory_no_file_handler(self, mock_makedirs):
        """Test without adding a file handler, the directory should not be created."""
        _buildLogDirectory(logs_dir=self.logs_dir, add_file_handler=False)
        mock_makedirs.assert_not_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    def test_buildLogDirectory_no_logs_dir(self, mock_makedirs):
        """Test required logs dir when building directory."""
        # Make dirs is mocked incase failure
        with self.assertRaises(ValueError):
            _buildLogDirectory("", add_file_handler=True)

    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    def test_getLogFileName(self, mock_listdir):
        """Test that log file names are generated correctly."""
        logger_handler = LoggerHandler(self.logs_dir, **self.config)
        log_file_name = logger_handler._getLogFileName("info")
        self.assertIn("test_project", log_file_name)
        self.assertIn("info", log_file_name)
        self.assertIn(self.timestamp, log_file_name)
        self.assertTrue(log_file_name.endswith(".log"))

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.path.getctime")
    @patch("src.pyfinbot.utils.logger.path.isfile", return_value=True)
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["old_logfile.log"])
    @patch("src.pyfinbot.utils.logger.RotatingFileHandler")
    @patch("src.pyfinbot.utils.logger._logger")
    @patch("src.pyfinbot.utils.logger.os_remove")
    def test_cleanLogs_remove_old_log(self, mock_remove, mock_logger, mock_file_handler, mock_listdir, mock_isfile,
                                        mock_getctime, mock_makedirs):
        mock_getctime.return_value = time.time() - (60 * 60 * 24 * 8)  # 8 days ago
        logger_handler = LoggerHandler(self.logs_dir, add_file_handler=True)
        mock_remove.assert_called_once_with(os.path.abspath(f"{self.logs_dir}/old_logfile.log"))
        mock_logger.debug.assert_called_once_with("Deleted old log file: old_logfile.log")

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.path.getctime")
    @patch("src.pyfinbot.utils.logger.path.isfile", return_value=True)
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["old_logfile.log"])
    @patch("src.pyfinbot.utils.logger.RotatingFileHandler")
    @patch("src.pyfinbot.utils.logger._logger")
    @patch("src.pyfinbot.utils.logger.os_remove", side_effect=PermissionError)
    def test_cleanLogs_unable_to_remove_old_log(self, mock_remove, mock_logger, mock_file_handler, mock_listdir, mock_isfile,
                                        mock_getctime, mock_makedirs):
        mock_getctime.return_value = time.time() - (60 * 60 * 24 * 8)  # 8 days ago
        logger_handler = LoggerHandler(self.logs_dir, add_file_handler=True)
        mock_logger.warning.assert_called_once_with("Failed to delete old log file due to permissions: old_logfile.log")
        mock_remove.assert_called_once_with(os.path.abspath(f"{self.logs_dir}/old_logfile.log"))

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.path.getctime", return_value=time.time())
    @patch("src.pyfinbot.utils.logger.path.isfile", return_value=True)
    @patch("src.pyfinbot.utils.logger.RotatingFileHandler")
    @patch("src.pyfinbot.utils.logger.os_remove")
    def test_cleanLogs_no_old_files(self, mock_remove, mock_file_handler, mock_isfile, mock_getctime, mock_listdir, mock_makedirs):
        """Test that recent log files are not removed."""
        logger = LoggerHandler(self.logs_dir, add_file_handler=True)
        mock_remove.assert_not_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.logging.StreamHandler")
    @patch("src.pyfinbot.utils.logger.logging.getLogger")
    def test_logger_with_console_handler(self, mock_get_logger, mock_stream_handler, mock_listdir, mock_makedirs):
        """Test creating a console handler."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = LoggerHandler(self.logs_dir, add_console_handler=True)

        # Ensure the StreamHandler was added
        mock_stream_handler.assert_called_once()
        mock_logger_instance.addHandler.assert_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.logging.StreamHandler")
    @patch("src.pyfinbot.utils.logger.logging.getLogger")
    def test_logger_without_console_handler(self, mock_get_logger, mock_stream_handler, mock_listdir, mock_makedirs):
        """Test that no console handler is created."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = LoggerHandler(self.logs_dir, add_console_handler=False)

        # Ensure the StreamHandler was not added
        mock_stream_handler.assert_not_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.RotatingFileHandler")
    @patch("src.pyfinbot.utils.logger.logging.getLogger")
    def test_logger_with_file_handler(self, mock_get_logger, mock_rotating_file_handler, mock_listdir, mock_makedirs):
        """Test creating a file handler."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = LoggerHandler(self.logs_dir, add_file_handler=True)

        # Ensure the RotatingFileHandler was added
        mock_rotating_file_handler.assert_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.RotatingFileHandler")
    @patch("src.pyfinbot.utils.logger.logging.getLogger")
    def test_logger_without_file_handler(self, mock_get_logger, mock_rotating_file_handler, mock_listdir, mock_makedirs):
        """Test that no file handler is created."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = LoggerHandler(self.logs_dir, add_file_handler=False)

        # Ensure the RotatingFileHandler was not added
        mock_rotating_file_handler.assert_not_called()

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=[])
    def test_getLogger(self, mock_listdir, mock_makedirs):
        """Test get logger method."""
        logger = LoggerHandler(self.logs_dir)
        self.assertEqual(logger.getLogger(), logger.logger)

    @patch("src.pyfinbot.utils.logger.makedirs")
    @patch("src.pyfinbot.utils.logger.listdir", return_value=["test.log"])
    @patch("src.pyfinbot.utils.logger.logging.StreamHandler")
    @patch("src.pyfinbot.utils.logger.logging.getLogger")
    def test_logger_close(self, mock_get_logger, mock_stream_handler, mock_listdir, mock_makedirs):
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = LoggerHandler(self.logs_dir, add_console_handler=True)

        # Verify that the logger added the console handler
        add_handler_calls = [call for call in mock_logger_instance.mock_calls if call[0] == 'addHandler']
        self.assertGreater(len(add_handler_calls), 0, "No handlers were added to the logger")

        mock_handler_1 = MagicMock()
        mock_handler_2 = MagicMock()
        logger.logger.handlers = [mock_handler_1, mock_handler_2]
        logger.close()

        mock_handler_1.close.assert_called_once()
        mock_handler_2.close.assert_called_once()
        mock_logger_instance.removeHandler.assert_any_call(mock_handler_1)
        mock_logger_instance.removeHandler.assert_any_call(mock_handler_2)


if __name__ == '__main__':
    unittest.main()
