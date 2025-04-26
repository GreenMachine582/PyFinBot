from __future__ import annotations

import logging
import configparser
from configparser import ConfigParser as _ConfigParser
from os import path
from typing import Any

from .. import utils
from ..version import PROJECT_NAME


_logger = logging.getLogger(__name__)

UTILS_DIR = path.dirname(path.abspath(__file__))
SRC_DIR = path.dirname(UTILS_DIR)  # Get source directory


def checkConfigPath(config_path: str) -> bool:
    """Check for valid config path."""
    if not config_path or not path.exists(config_path):
        raise FileExistsError(f"Invalid config path was given, got: {config_path}")
    return True


class Config:

    CONFIG_EXT = "conf"
    DEFAULT_PROFILE_NAME = "profile_1"
    PROJECT_CONFIG_PATH: str = path.abspath(f"{SRC_DIR}/{PROJECT_NAME}.{CONFIG_EXT}")

    def __init__(self, config_path: str, sections: str | list = "", env: utils.Env = None, **kwargs):
        if config_path:
            config_path = path.abspath(config_path)
            checkConfigPath(config_path)  # Validate the passed config path

        self.env: utils.Env = env
        self.config_path: str = config_path
        self.config_dir: str = '' if not config_path else path.dirname(config_path)
        self.filename: str = ''

        self._sections: list[str] = []
        self._config: dict[str: Any] = {}

        # Split given config path into dir and name
        split_path = self._splitPathIntoDirAndName(config_path)
        if split_path:  # Updated detected dir and name
            self.config_dir, self.filename = split_path
        if not self.filename and self.env:
            self.filename = self.env.project_name

        # Load and set config attributes
        # Load base config first
        self.loadConfig(self.PROJECT_CONFIG_PATH)

        if self.config_path:  # Load desired config and overwrite base config
            self.loadConfig(sections=sections)

        # Add environment paths
        self.addEnvPaths()

    def __str__(self) -> str:
        return str(self._config)

    def __repr__(self) -> str:
        prefix = ""
        if self.env:
            prefix = (self.env.project_name_text or self.env.project_name or '')
        return f"{prefix}{'.' if prefix else ''}Config({str(self)})"

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = value

    def get(self, key: str, fallback={}):
        return self._config.get(key, fallback)

    def _splitPathIntoDirAndName(self, config_path: str) -> tuple[str, str] | False:
        """Split path into directory and filename."""
        if not config_path and not isinstance(config_path, str):
            return False
        if not config_path.endswith('.' + self.CONFIG_EXT):
            return False
        return path.split(config_path)

    def loadConfig(self, config_path: str = '', sections: str | list = '') -> dict | None:
        """Load config attributes from config file."""
        config_: dict = {}

        config_path = config_path or self.config_path

        # Read config file
        parser = _ConfigParser()
        parser.optionxform = str
        try:
            parser.read(config_path)
        except configparser.DuplicateOptionError as e:
            _logger.error(f"Duplicate Option Error occurred; {e}")
            raise e

        # Sections need to be a list or false
        if sections and isinstance(sections, str):
            sections = [sections]
        elif not sections or not isinstance(sections, list):
            sections = False

        if not sections:  # Default to get all attributes from config file
            sections = parser.sections()

        # Load each section
        for section_name in sections:
            config_[section_name] = config_.get(section_name, {})  # Merge sections with same name
            config_[section_name].update(self.loadSection(config_path, parser, section_name))

        self.setConfig(config_)
        return config_

    def loadSection(self, config_path: str, parser: _ConfigParser, section_name: str) -> dict:
        """Get section attributes from config file."""
        section_config = {}
        if parser.has_section(section_name):
            section_config = {}
            for key, value in parser.items(section_name):
                try:
                    section_config[key] = eval(value)
                except (SyntaxError, NameError):
                    section_config[key] = value
            self._sections.append(section_name)
        else:
            _logger.error(f"Section '{section_name}' not found in '{config_path}'")
        return section_config

    def addEnvPaths(self):
        """Add environment paths to system."""
        if hasattr(self, "env_paths"):
            for env_name, env_path in getattr(self, "env_paths").items():
                utils.addEnvPath(env_path, env_name=env_name)
            _logger.info("Environment paths have been added")

    def unloadConfig(self):
        """Remove configs and sections from Config."""
        self._config = {}
        self._sections = []

    def setConfig(self, config: dict[str: dict]):
        """Add section attributes to Config with dict values."""
        for key, value in config.items():
            if key not in self._config:
                self._config[key] = value
                continue
            self._config[key].update(value)

    def saveConfig(self, config_dir: str = "", filename: str = ""):
        """Save the current configuration attributes back to the config file."""
        # Create a new config parser object
        parser = _ConfigParser()

        config_dir = config_dir or self.config_dir
        filename = filename or self.filename or self.DEFAULT_PROFILE_NAME

        # For each attribute in the object, if it's a dictionary, add it as a section
        for key, value in self._config.items():
            parser.add_section(key)
            for sub_key, sub_value in value.items():
                parser.set(key, sub_key, str(sub_value))

        # Write the configuration back to the file
        config_path = utils.joinPath(config_dir, filename, ext=self.CONFIG_EXT)
        with open(config_path, 'w') as config_file:
            parser.write(config_file)

        _logger.info(f"Config saved to '{config_path}'")
