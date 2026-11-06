"""Tiny persistent key-value store (replaces java.util.prefs): one JSON file per node in the user's app-data folder.
Best effort: any I/O failure falls back to in-memory behaviour."""
import json
import os
import sys


def _base_dir() -> str:
    override = os.environ.get("LINDEFENSE_PREFS_DIR")
    if override:
        return override
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Lindefense")
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Lindefense")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "lindefense")


class Node:
    def __init__(self, name: str):
        self._path = os.path.join(_base_dir(), name.replace("/", "_") + ".json")
        self._data = {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self._data = d
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_bool(self, key, default=False):
        v = self._data.get(key, default)
        return bool(v) if isinstance(v, (bool, int)) else default

    def get_int(self, key, default=0):
        v = self._data.get(key, default)
        return v if isinstance(v, int) and not isinstance(v, bool) else default

    def put(self, key, value):
        self._data[key] = value
        self.flush()

    def flush(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=1)
            os.replace(tmp, self._path)
        except OSError:
            pass


_nodes = {}


def node(name: str) -> Node:
    n = _nodes.get(name)
    if n is None:
        n = Node(name)
        _nodes[name] = n
    return n
