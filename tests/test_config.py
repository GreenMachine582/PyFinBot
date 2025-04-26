import logging
import unittest
from configparser import ConfigParser, DuplicateOptionError
from os import path as os_path
from unittest.mock import patch, mock_open

from src.pyfinbot.utils import joinPath
from src.pyfinbot.utils.config import Config, checkConfigPath
from src.pyfinbot.utils.env import Env

_logger = logging.getLogger(__name__)

TESTS_DIR = os_path.dirname(os_path.abspath(__file__))

CONFIG_CONTENT = """
[default]
Test: False
[Section1]
param1: 10
param2: 'value'
"""

DUPLICATE_OPTION_CONFIG_CONTENT = """
[Section1]
param1 = value1
param1 = value2  # Duplicate option, should raise an error
"""


class TestConfig(unittest.TestCase):

    def setUp(self):
        # Prepare necessary paths and values for tests
        self.valid_config_path = os_path.abspath(TESTS_DIR + '/test_data/pyfinbot.conf')
        self.invalid_config_path = os_path.abspath('/invalid/path/to/config.conf')

    @patch('os.path.exists', return_value=True)
    def test_check_valid_config_path(self, mock_exists):
        """Test the check for a valid config file path."""
        self.assertTrue(checkConfigPath(self.valid_config_path))
        mock_exists.assert_called_once_with(self.valid_config_path)

    @patch('os.path.exists', return_value=False)
    def test_check_invalid_config_path(self, mock_exists):
        """Test the check for an invalid config file path raises an error."""
        with self.assertRaises(FileExistsError):
            checkConfigPath(self.invalid_config_path)
        mock_exists.assert_called_once_with(self.invalid_config_path)

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    @patch('os.path.exists', return_value=True)
    def test_load_config(self, mock_exists, mock_file):
        """Test loading of a valid config file."""
        config = Config(self.valid_config_path)
        self.assertIsInstance(config, Config)
        self.assertEqual(config.get('default'), {'Test': False})
        self.assertEqual(config['Section1']['param1'], 10)
        self.assertEqual(config['Section1']['param2'], "value")
        self.assertEqual(str(config), "{'default': {'Test': False}, 'Section1': {'param1': 10, 'param2': 'value'}}")
        self.assertEqual(repr(config), "Config({'default': {'Test': False}, 'Section1': {'param1': 10, 'param2': 'value'}})")

    @patch('builtins.open', new_callable=mock_open, read_data=DUPLICATE_OPTION_CONFIG_CONTENT)
    @patch('os.path.exists', return_value=True)
    @patch('src.pyfinbot.utils.config._logger')
    def test_load_config_duplicate_option_error(self, mock_logger, mock_exists, mock_file):
        """Test handling of DuplicateOptionError in config loading."""
        with self.assertRaises(DuplicateOptionError):
            config = Config(config_path="dummy_path")
        mock_logger.error.assert_called_once()
        self.assertIn("Duplicate Option Error occurred", mock_logger.error.call_args[0][0])

    @patch('os.path.exists', return_value=False)
    def test_load_missing_config(self, mock_exists):
        """Test handling of a missing config file."""
        with self.assertRaises(FileExistsError):
            Config(self.invalid_config_path)

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    @patch('src.pyfinbot.utils.config._logger')
    def test_save_config(self, mock_logger, mock_file):
        """Test saving the current configuration attributes back to the config file."""
        config = Config(self.valid_config_path)
        config['default'] = {'Test': True}
        config['Section1'] = {'param1': 10, 'param2': 'value'}

        config.saveConfig()
        mock_logger.info.assert_called_once_with(f"Config saved to '{self.valid_config_path}'")
        config_path = os_path.join(config.config_dir, config.filename)

        mock_file.assert_called_with(config_path, 'w')
        handle = mock_file()

        # Verify the written content
        written_content = ''.join(call[0][0] for call in handle.write.call_args_list)
        self.assertIn('[default]\n', written_content)
        self.assertIn('test = True\n', written_content)
        self.assertIn('[Section1]\n', written_content)
        self.assertIn('param1 = 10\n', written_content)
        self.assertIn('param2 = value\n', written_content)

        config.filename = ''
        config.saveConfig()
        config_path = joinPath(os_path.abspath(TESTS_DIR + '/test_data'), config.DEFAULT_PROFILE_NAME, ext=config.CONFIG_EXT)
        mock_logger.info.assert_any_call(f"Config saved to '{config_path}'")

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    def test_load_section(self, mock_file):
        """Test loading a specific section from a config file."""
        config = Config(self.valid_config_path)
        parser = ConfigParser()
        parser.read_string(CONFIG_CONTENT)
        section_data = config.loadSection(self.valid_config_path, parser, 'Section1')
        self.assertEqual(section_data, {'param1': 10, 'param2': 'value'})

        config = Config(self.valid_config_path)
        config.loadConfig(sections='Section1')
        self.assertEqual(section_data, {'param1': 10, 'param2': 'value'})

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    @patch('src.pyfinbot.utils.config._logger')
    def test_load_nonexistent_section(self, mock_logger, mock_file):
        """Test loading a nonexistent section from a config file."""
        config = Config('')
        self.assertFalse(config.config_path)
        parser = ConfigParser()
        parser.read_string(CONFIG_CONTENT)
        section_data = config.loadSection(self.valid_config_path, parser, 'Test Test')
        self.assertEqual(section_data, {})
        mock_logger.error.assert_called_once_with(f"Section 'Test Test' not found in '{self.valid_config_path}'")

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    @patch('os.path.exists', return_value=True)
    def test_load_config_with_env(self, mock_exists, mock_file):
        """Test loading of a valid config file with Env."""
        config = Env(self.valid_config_path, project_name="test").config
        self.assertIsInstance(config, Config)
        self.assertEqual(config.filename, 'pyfinbot.conf')
        self.assertEqual(repr(config), "test.Config({'default': {'Test': False}, 'Section1': {'param1': 10, 'param2': 'value'}})")
        config.env.project_name_text = "Test"
        self.assertEqual(repr(config), "Test.Config({'default': {'Test': False}, 'Section1': {'param1': 10, 'param2': 'value'}})")

    def test_config_with_env(self):
        """Test config with Env."""
        config = Env('', project_name="test").config
        self.assertIsInstance(config, Config)
        self.assertEqual(config.filename, 'test')


class TestValidConfig(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open, read_data=CONFIG_CONTENT)
    @patch('os.path.exists', return_value=True)
    def setUp(self, mock_exists, mock_file):
        # Prepare necessary paths and values for tests
        self.config_path = os_path.abspath(TESTS_DIR + '/non_existent.conf')
        self.config = Config(self.config_path)

    def test_split_path_into_dir_and_name(self):
        """Test splitting a path into directory and filename."""
        directory, filename = self.config._splitPathIntoDirAndName(self.config_path)
        self.assertEqual(directory, os_path.dirname(self.config_path))
        self.assertEqual(filename, os_path.basename(self.config_path))

    def test_split_invalid_path(self):
        """Test handling of an invalid path format."""
        self.assertFalse(self.config._splitPathIntoDirAndName('invalid_config.txt'))
        self.assertFalse(self.config._splitPathIntoDirAndName(''))
        self.assertFalse(self.config._splitPathIntoDirAndName(False))

    def test_unload_config(self):
        """Test removing section attributes from Config."""
        self.config._config = {'default': {'Test': True}, 'Section1': {'param1': 10}}
        self.config._sections = ['default', 'Section1']
        self.config.unloadConfig()
        self.assertFalse(hasattr(self.config, 'default'))
        self.assertFalse(hasattr(self.config, 'Section1'))
        self.assertEqual(self.config._sections, [])

    def test_set_config(self):
        """Test setting configuration attributes."""
        new_config = {'default': {'NewParam': 123}}
        self.config.setConfig(new_config)
        self.assertEqual(self.config.get('default'), {'Test': False, 'NewParam': 123})
        self.assertEqual(str(self.config), "{'default': {'Test': False, 'NewParam': 123}, 'Section1': {'param1': 10, 'param2': 'value'}}")

    @patch('src.pyfinbot.utils.config._logger')
    @patch('src.pyfinbot.utils.addEnvPath')
    def test_add_env_paths_success(self, mock_addEnvPath, mock_logger):
        """Test adding env paths success."""
        self.config.env_paths = {
            "PATH1": "/some/path1",
            "PATH2": "/some/path2",
        }

        self.config.addEnvPaths()

        mock_addEnvPath.assert_any_call("/some/path1", env_name="PATH1")
        mock_addEnvPath.assert_any_call("/some/path2", env_name="PATH2")
        mock_logger.info.assert_called_once_with("Environment paths have been added")

    @patch('src.pyfinbot.utils.config._logger')
    @patch('src.pyfinbot.utils.addEnvPath')
    def test_add_env_paths_no_env_paths(self, mock_addEnvPath, mock_logger):
        """Test adding env paths without env paths."""
        self.assertFalse(hasattr(self.config, "env_paths"))

        self.config.addEnvPaths()

        mock_addEnvPath.assert_not_called()
        mock_logger.info.assert_not_called()

    def test_loadSection_handles_SyntaxError(self):
        """Test loading a section with an invalid eval expression."""
        section_name = "test_section"
        parser = ConfigParser()
        parser.add_section(section_name)

        parser.set(section_name, "key_with_syntax_error", "['invalid_python_code@')")
        result = self.config.loadSection("", parser, section_name)
        self.assertIn("key_with_syntax_error", result)
        self.assertEqual(result["key_with_syntax_error"], "['invalid_python_code@')")
