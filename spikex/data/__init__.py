import os
import shutil
from io import open as _open
from pathlib import Path

_HERE_PATH = Path(os.path.dirname(__file__))


def open(filename, mode="r", folder=None):
    path = _HERE_PATH
    if folder is not None:
        path = path.joinpath(folder)
        if not path.exists():
            if mode.startswith("r"):
                raise FileNotFoundError(path)
            path.mkdir()
    return _open(path.joinpath(filename), mode)


def contains(filename, folder=None):
    path = _HERE_PATH
    if folder is not None:
        path = path.joinpath(folder)
        if not path.exists():
            return False
    return path.joinpath(filename).exists()


def delete(filename):
    if not contains(filename):
        return
    path = _HERE_PATH.joinpath(filename)
    shutil.rmtree(path)
    return True


def get(filename, default=None):
    if not contains(filename):
        return default
    return force_get(filename)


def force_get(filename):
    return _HERE_PATH.joinpath(filename)
