"""SETTINGS > WINDOW EFFECTS: whether Palantir's System Takeover may grab and shrink the real game window (default ON).
LINDEFENSE_WINDOWFX=false forces it off for one run without touching the saved choice."""
import os

from lindefense import prefs

ENV = "LINDEFENSE_WINDOWFX"
_KEY = "windowEffects"
_on = None


def _node():
    return prefs.node("settings")


def is_enabled():
    global _on
    if os.environ.get(ENV, "").lower() == "false":
        return False
    if _on is None:
        try:
            _on = _node().get_bool(_KEY, True)
        except Exception:
            _on = True
    return _on


def set_enabled(enabled):
    global _on
    _on = bool(enabled)
    try:
        n = _node()
        n.put(_KEY, _on)
        n.flush()
    except Exception:
        pass


def toggle():
    v = not is_enabled()
    set_enabled(v)
    return v


class WindowEffects:
    """Class-style entry points used by the ported UI."""
    PROPERTY = "lindefense.windowfx"
    is_enabled = staticmethod(is_enabled)
    set_enabled = staticmethod(set_enabled)
    toggle = staticmethod(toggle)
