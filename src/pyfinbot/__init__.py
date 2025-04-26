from __future__ import annotations

import logging
import os

from . import utils, version
from .tools import database
from .tools.database import DatabaseError, DatabaseNotFoundError, SchemaFileNotFoundError, SchemaApplicationError


_logger = logging.getLogger(__name__)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

env: utils.Env | None = None


def loadEnv(config_path: str = "", **kwargs) -> utils.Env:
    """Load the env and config for the project."""
    global env
    kwargs = {
        "project_name": version.PROJECT_NAME,
        "project_name_text": version.PROJECT_NAME_TEXT,
        "version": version.VERSION,
        **kwargs,
    }
    env = utils.Env(config_path, **kwargs)
    return env
