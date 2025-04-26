from __future__ import annotations

import json
import logging
import pickle
from os import path as os_path

from .exceptions import logExceptionHelper
from .path import joinPath, checkPath, existPath
from .utils import toJson


_logger = logging.getLogger(__name__)

__all__ = ["load", "save"]


def load(dir_: str, name: str = "", ext: str = "", errors: str = "raise"):
    """
    Load the data with appropriate method. Pickle will deserialise the
    contents of the file and json will load the contents.

    :param dir_: Directory of file, should be a str
    :param name: Name of file, should be a str
    :param ext: File extension, should be a str
    :param errors: Whether to 'ignore', 'warning' or 'raise' errors, should be str
    :return: data - Any
    """
    filename = name
    if not name:
        filename = os_path.splitext(os_path.basename(dir_))[0]

    if not ext:
        ext = os_path.splitext(name or filename)[1]

    if not ext:
        msg = f"The parameters 'name' or 'ext' must include file extension, got: '{name or filename}', '{ext}'"
        logExceptionHelper(msg, errors, ValueError)
        return

    path, exist = checkPath(dir_, name, ext=ext, errors=errors)
    if not exist:
        return None

    if ext[0] == ".":  # Remove . for easier file type checks
        ext = ext[1:]

    data = None
    try:
        if ext == 'json':
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        elif ext in ['txt', 'xml']:
            with open(path, 'r') as file:
                data = file.read()
        else:
            with open(path, 'rb') as file:
                data = pickle.load(file)
        _logger.debug(f"File '{name or filename}' data was loaded")
    except Exception as e:
        _logger.error(f"File is not supported or an error occurred when loading the data.")
        _logger.debug(e)
    return data


def save(dir_: str, name: str, data, indent: int = 4, errors: str = 'raise') -> bool:
    """
    Save the data with appropriate method. Pickle will serialise the
    object, while json will dump the data with indenting to allow users
    to edit and easily view the encoded data.

    :param dir_: Directory of file, should be a str
    :param name: Name of file, should be a str
    :param data: Data to be saved, should be an Any
    :param indent: Data's indentation within the file, should be an int
    :param errors: If 'ignore', suppress errors, should be str
    :return: completed - bool
    """
    path = joinPath(dir_, name)
    ext = os_path.splitext(name)[1]

    if not existPath(dir_, errors=errors):
        return False

    if not ext:
        msg = f"File '{name}' must include file extension in name"
        logExceptionHelper(msg, errors, ValueError)
        return False

    if ext == '.json':
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(data, file, default=toJson, indent=indent)
    elif ext == '.txt':
        with open(path, 'w') as file:
            file.write(str(data))
    if ext in {'.html', '.xml'}:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(data)
    elif isinstance(data, object):
        with open(path, 'wb') as file:
            pickle.dump(data, file, pickle.HIGHEST_PROTOCOL)
    else:
        msg = f"Saving method was not determined, failed to save file, got: {type(data)}"
        logExceptionHelper(msg, errors, FileNotFoundError)
        return False
    _logger.debug(f"File '{name}' was saved")
    return True
