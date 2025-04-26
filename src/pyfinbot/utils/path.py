from __future__ import annotations

import logging
import os
import re

from .exceptions import logExceptionHelper

_logger = logging.getLogger(__name__)


def formatPath(path: str) -> str:
    """Format path using detected OS separator."""
    if path and isinstance(path, str):
        split_path = re.split("[\\\\|/]", path)
        return os.sep.join(split_path)
    return ""


def checkPath(path: str, *paths, ext: str = '', errors: str = 'ignore', return_exist: bool = True) -> tuple | str:
    """
    Join the paths together, adds an extension if not already included
    in path, then checks if path exists.

    :param path: Main file path, should be a str
    :param paths: Remaining file paths, should be a tuple[str]
    :param ext: File extension, should be a str
    :param errors: Whether to 'ignore', 'warning', 'error' or 'raise' errors, should be str
    :param return_exist: Whether to return the status of the path, should be a bool
    :return: path, exist - tuple[str, bool] | str
    """
    path = joinPath(path, *paths, ext=ext)

    exist = True if os.path.exists(path) else False

    if not exist:
        logExceptionHelper(f"No such file or directory: '{path}'", errors, FileNotFoundError)
    if not return_exist:
        return path
    return path, exist


def existPath(path: str, *paths, ext: str = '', errors: str = 'ignore') -> bool:
    """
    Join the paths together, adds an extension if not already included
    in path, then checks if path exists.

    :param path: Main file path, should be a str
    :param paths: Remaining file paths, should be a tuple[str]
    :param ext: File extension, should be a str
    :param errors: Whether to 'ignore', 'warning' or 'raise' errors, should be str
    :return: exist - bool
    """
    _, exist = checkPath(path, *paths, ext=ext, errors=errors)
    return exist


def joinPath(path: str, *paths, ext: str = '') -> str:
    """
    Join the paths together, adds an extension if not already included
    in path.

    :param path: Main file path, should be a str
    :param paths: Remaining file paths, should be a tuple[str]
    :param ext: File extension, should be a str
    :return: path - str
    """
    path, path_ext = os.path.splitext(os.path.join(path, *filter(lambda x: x and isinstance(x, str), paths)))
    if ext and path_ext != ext:
        path_ext = (ext if ext and '.' in ext else f'.{ext}')
    return os.path.abspath(path + path_ext)


def makePath(path: str, *paths, errors: str = 'ignore') -> str:
    """
    Check if the path exists and creates the path when required.

    :param path: Main file path, should be a str
    :param paths: Remaining file paths, should be a tuple[str]
    :param errors: Whether to 'ignore', 'warning' or 'raise' errors, should be str
    :return: path - str
    """
    path, exist = checkPath(path, *paths, errors=errors)
    if not exist:
        os.makedirs(path)
        _logger.debug(f"Path has been made: '{path}'")
    return path


def listPath(path: str, *paths, ext: str | list | tuple = None, return_file_path: bool = False,
             errors: str = 'ignore') -> tuple:
    """
    Join the paths together, return list of files within directory or
    specific files by extension.

    :param path: Main file path, should be a str
    :param paths: Remaining file paths, should be a tuple[str]
    :param ext: File extension, should be a str | list | tuple
    :param return_file_path: Whether to return file name or file path, should be a bool
    :param errors: Whether to 'ignore', 'warning' or 'raise' errors, should be str
    :return: path, files - tuple[str, list[str]]
    """
    if not ext:
        ext = []
    elif isinstance(ext, str):
        ext = [ext]
    elif not isinstance(ext, (list, tuple)):
        raise TypeError(f"'ext': Expected type 'str', 'list' or 'tuple', got: '{type(ext).__name__}'")

    ext = [_.replace('.', '') for _ in ext]

    files = []
    path, exist = checkPath(path, *paths, errors=errors)
    if not exist:
        return path, files

    for file in os.listdir(path):
        file_ext = os.path.splitext(file)[1].replace('.', '')
        if not ext or file_ext in ext:
            files.append(joinPath(path, file) if return_file_path else file)
    return path, files


def splitPath(path: str, direction: str = 'lr', max_split: int = 1, include_ext: bool = True) -> tuple:
    """
    Splits the path into left and right by direction with split size.

    :param path: Path to a folder or file, should be a str
    :param direction: Whether to split the path from 'lr' or 'rl', should be str
    :param max_split: The splitting size, should be an int
    :param include_ext: Whether to include file extension, should be a bool
    :return: left, right - tuple[str, str]
    """
    sep_path = re.split("[\\\\|/]", path)
    if max_split not in range(1, len(sep_path)):
        raise ValueError(f"'max_split' must be within range of 1 and directory depth, got: {max_split}")

    if direction == 'lr':
        left, right = sep_path[:max_split], sep_path[max_split:]
    elif direction == 'rl':
        left, right = sep_path[:(len(sep_path) - max_split)], sep_path[(len(sep_path) - max_split):]
    else:
        raise ValueError("The parameter direction must be either 'lr' or 'rl'")

    if not include_ext:  # removes the file extension
        right[-1] = os.path.splitext(right[-1])[0]
    return os.sep.join(left), os.sep.join(right)


def addEnvPath(*paths, env_name: str = 'PATH', path_sep: str = ',', errors: str = 'raise') -> None:
    """
    Add paths to environment paths.

    :param paths: Remaining file paths, should be a tuple[str]
    :param env_name: Name of environment path to be added, should be a str
    :param path_sep: Seperator the can split joined str paths, should be a str
    :param errors: Whether to 'ignore', 'warning' or 'raise' errors, should be str
    :return: - None
    """
    if len(paths) == 1:
        if isinstance(paths[0], (list, tuple)):
            paths = paths[0]
        elif isinstance(paths[0], str):
            paths = paths[0].split(path_sep)

    for env_path in paths:
        if env_path and existPath(env_path, errors=errors):
            existing_paths = list(filter(bool, [os.environ.get(env_name)]))
            existing_paths.append(env_path)
            os.environ[env_name] = ';'.join(existing_paths)


def _exclude(exclusions: list) -> list:
    """
    Exclude specific functions and variables from a list of global functions
    and variables.

    :param exclusions: A list of function names to exclude, should be a list
    :return: functions - list
    """
    import types

    # Get all global functions and variables that are not modules or prefixed with _
    functions = [name for name, function in globals().items()
                 if not (name.startswith('_') or isinstance(function, types.ModuleType))]

    # Remove the exclusions from the functions list
    for exclusion in exclusions:
        if exclusion in functions:
            functions.remove(exclusion)

    del types  # Delete types from the current scope (introduced from the import)
    return functions


_exclusions = ["annotations"]
__all__ = _exclude(_exclusions)
