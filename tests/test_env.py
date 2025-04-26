import unittest
import gc
from os import path as os_path
from unittest.mock import MagicMock, patch

from src.pyfinbot.utils.env import Env


class TestEnv(unittest.TestCase):

    def setUp(self):
        self.config_path = "path/to/config"
        self.default_kwargs = {
            "project_name": "TestProject",
            "project_name_text": "Test Project",
            "version": "1.0.0",
            "instance": "test_instance",
            "project_dir": "path/to/project",
        }

    @patch("src.pyfinbot.utils.env.os_path.exists")
    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.LoggerHandler")
    def test_init_creates_logger_and_config(self, mock_logger_handler, mock_config, mock_exist_path):
        """Test that Env initializes with a config and logger correctly."""
        def config_get_side_effect(key, default={}):
            """Simulate log config."""
            if key == "logs":
                return {"no_logs": False, "max_bytes": 1024 * 1024, "backup_count": 3}
            return default

        # Set the side_effect for the config.get() method
        mock_config.return_value.get.side_effect = config_get_side_effect

        env = Env(self.config_path, logs_dir="path/to/logs", **self.default_kwargs)
        mock_config.assert_called_once_with(self.config_path, env=env, project_name="TestProject",
                                            project_name_text="Test Project", version="1.0.0",
                                            instance="test_instance", project_dir='path/to/project')
        mock_logger_handler.assert_called_once_with("path/to/logs", project_name="TestProject",
                                                    instance="test_instance", no_logs=False, max_bytes=1024 * 1024,
                                                    backup_count=3)

    @patch("src.pyfinbot.utils.env.os_path.exists")
    @patch("src.pyfinbot.utils.env.Config")
    def test_call_updates_attributes(self, mock_config, mock_exist_path):
        """Test that calling the Env instance dynamically updates its attributes."""

        env = Env(self.config_path, **self.default_kwargs)
        env(project_name="UpdatedProject", version="2.0.0")

        with patch("src.pyfinbot.utils.env._logger.warning") as mock_warning:
            env(unexpected_key="unexpected_value")
            mock_warning.assert_called_once_with("Unexpected key, got: unexpected_key")

        self.assertEqual(env.project_name, "UpdatedProject")
        self.assertEqual(env.version, "2.0.0")

    @patch("src.pyfinbot.utils.env.os_path.exists")
    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.LoggerHandler")
    def test_init_no_logger_if_no_logs(self, mock_logger_handler, mock_config, mock_exist_path):
        """Test that the logger is not initialized if `no_logs` is set to True."""
        def config_get_side_effect(key, default={}):
            """Simulate log config."""
            if key == "logs":
                return {"no_logs": True}
            return default

        # Set the side_effect for the config.get() method
        mock_config.return_value.get.side_effect = config_get_side_effect

        env = Env(self.config_path, **self.default_kwargs)

        mock_logger_handler.assert_not_called()

    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.os_path.exists", return_value=True)
    def test_project_dir_validation(self, mock_exist_path, mock_config):
        """Test that the project directory validation works correctly."""
        env = Env(self.config_path, **self.default_kwargs)

        self.assertEqual(env.project_dir, os_path.abspath("path/to/project"))
        mock_exist_path.assert_called_once_with(os_path.abspath("path/to/project"))

        env(project_dir="")
        self.assertEqual(env.project_dir, env.PROJECT_DIR)

    @patch("src.pyfinbot.utils.env.os_path.exists", return_value=False)
    def test_invalid_project_dir_validation(self, mock_exist_path):
        """Test that the project directory validation works correctly."""
        with self.assertRaises(FileExistsError):
            env = Env(self.config_path, **self.default_kwargs)

    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.os_path.exists", return_value=True)
    def test_env_str_and_repr(self, mock_exist_path, mock_config):
        """Test that the Env's __str__ and __repr__ methods return expected values."""
        env = Env(self.config_path, **self.default_kwargs)
        expected_str = "Env(project='Test Project', version='1.0.0')"
        self.assertEqual(str(env), expected_str)
        self.assertEqual(repr(env), expected_str)

    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.os_path.exists", return_value=True)
    def test_env_equality(self, mock_exist_path, mock_config):
        """Test that the equality and inequality checks for Env instances work."""
        env1 = Env(self.config_path, **self.default_kwargs)
        env2 = Env(self.config_path, **self.default_kwargs)

        self.assertEqual(env1, env1)
        self.assertNotEqual(env1, env2)

    @patch("src.pyfinbot.utils.env.Config")
    def test_env_hash(self, mock_config):
        """Test that the same Env object returns the same hash."""
        env_instance1 = Env(self.config_path, project_name="test_project_1", version="1.0.0")
        env_instance2 = Env(self.config_path, project_name="test_project_2", version="1.0.1")
        self.assertEqual(hash(env_instance1), hash(env_instance1), "Hashes of the same object should be equal")
        self.assertNotEqual(hash(env_instance1), hash(env_instance2), "Hashes of different objects should not be equal")


class TestEnvDatabase(unittest.TestCase):

    @patch("src.pyfinbot.utils.env.Config")
    @patch("src.pyfinbot.utils.env.os_path.exists", return_value=True)
    def setUp(self, mock_exist_path, mock_config):
        self.env = Env(config_path="dummy_path")

    @patch('src.pyfinbot.utils.env._logger')
    def test_env_cleanup_on_deletion(self, mock_logger):
        # Mock a database connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        self.env.conn = mock_conn
        self.env.cur = mock_cur
        del self.env
        gc.collect()  # Force garbage collection

        # Ensure cursor and connection are closed
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('src.pyfinbot.utils.env._logger')
    def test_env_cleanup_handles_exceptions(self, mock_logger):
        """Env database exceptions should be handled correctly when closing."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        mock_conn.close.side_effect = Exception("Connection close error")
        mock_cur.close.side_effect = Exception("Cursor close error")

        self.env.conn = mock_conn
        self.env.cur = mock_cur
        del self.env
        gc.collect()  # Force garbage collection

        # Ensure exceptions during close are logged
        mock_logger.error.assert_any_call("Failed to close cursor: Cursor close error")
        mock_logger.error.assert_any_call("Failed to close connection: Connection close error")


if __name__ == "__main__":
    unittest.main()
