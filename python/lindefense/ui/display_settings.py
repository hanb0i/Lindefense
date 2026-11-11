"""SETTINGS > DISPLAY and ACCESSIBILITY: full screen, the FPS counter, reduced motion and the colour-blind-safe palette,
plus the remembered window geometry.

Persistence: two new prefs nodes, both optional. A missing node or key means the default, so save folders written by
older versions load unchanged.
  'display'  fullscreen / showFps / reducedMotion / colourBlind (booleans, all off by default)
  'window'   geometry = {x, y, w, h, maximized}: the last windowed (not full-screen, not maximised) bounds in screen
             points, and whether the window was maximised on top of them

Both classes take an injectable store: anything with get(key, default) and put(key, value), i.e. a prefs.Node or a
MemoryStore. The shared DisplaySettings (DisplaySettings.get()) lives in memory for headless runs and the scripted demo,
so tests never touch the player's save folder; LINDEFENSE_SHOW_FPS / LINDEFENSE_REDUCED_MOTION / LINDEFENSE_COLOURBLIND
= 1 or 0 force a setting for one run without saving it.

Reduced motion and the colour-blind palette are cosmetic only: they change what is drawn, never the simulation. UI code
that draws numbers from the game's RNG (the victory fireworks) keeps drawing exactly the same numbers either way.
"""
import os

from lindefense import prefs


class MemoryStore:
    """A prefs node that only lives in memory (tests, tools, automation)."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def put(self, key, value):
        self.data[key] = value


def _read_bool(store, key, default):
    try:
        v = store.get(key, default)
    except Exception:
        return default
    return v if isinstance(v, bool) else default


def _env_bool(name):
    v = os.environ.get(name)
    if v is None:
        return None
    v = v.strip().lower()
    if v in ("1", "true", "on", "yes"):
        return True
    if v in ("0", "false", "off", "no"):
        return False
    return None


def _transient_run():
    """Headless (SDL dummy driver) and scripted-demo runs keep their settings in memory."""
    return (os.environ.get("SDL_VIDEODRIVER") == "dummy" or bool(os.environ.get("LINDEFENSE_HEADLESS"))
            or bool(os.environ.get("LINDEFENSE_DEMO")))


class DisplaySettings:
    PREFS_NODE = "display"
    KEY_FULLSCREEN = "fullscreen"
    KEY_SHOW_FPS = "showFps"
    KEY_REDUCED_MOTION = "reducedMotion"
    KEY_COLOUR_BLIND = "colourBlind"
    ENV = {KEY_SHOW_FPS: "LINDEFENSE_SHOW_FPS", KEY_REDUCED_MOTION: "LINDEFENSE_REDUCED_MOTION",
           KEY_COLOUR_BLIND: "LINDEFENSE_COLOURBLIND"}
    instance = None

    def __init__(self, store=None):
        self.store = store if store is not None else MemoryStore()
        self.fullscreen = _read_bool(self.store, self.KEY_FULLSCREEN, False)
        self.show_fps = _read_bool(self.store, self.KEY_SHOW_FPS, False)
        self.reduced_motion = _read_bool(self.store, self.KEY_REDUCED_MOTION, False)
        self.colour_blind = _read_bool(self.store, self.KEY_COLOUR_BLIND, False)
        for key, attr in ((self.KEY_SHOW_FPS, "show_fps"), (self.KEY_REDUCED_MOTION, "reduced_motion"),
                          (self.KEY_COLOUR_BLIND, "colour_blind")):
            forced = _env_bool(self.ENV[key])
            if forced is not None:
                setattr(self, attr, forced)

    # ---------------------------------------------------------------- shared instance
    @staticmethod
    def in_memory(data=None):
        return DisplaySettings(MemoryStore(data))

    @staticmethod
    def get():
        if DisplaySettings.instance is None:
            store = None
            if not _transient_run():
                try:
                    store = prefs.node(DisplaySettings.PREFS_NODE)
                except Exception:
                    store = None
            DisplaySettings.instance = DisplaySettings(store)
        return DisplaySettings.instance

    @staticmethod
    def set_instance(s):
        """Replaces the shared instance (tests); None makes the next get() load it again."""
        DisplaySettings.instance = s

    # ---------------------------------------------------------------- settings
    def _save(self, key, value):
        try:
            self.store.put(key, bool(value))
        except Exception:
            pass

    def set_fullscreen(self, on):
        self.fullscreen = bool(on)
        self._save(self.KEY_FULLSCREEN, self.fullscreen)

    def set_show_fps(self, on):
        self.show_fps = bool(on)
        self._save(self.KEY_SHOW_FPS, self.show_fps)

    def set_reduced_motion(self, on):
        self.reduced_motion = bool(on)
        self._save(self.KEY_REDUCED_MOTION, self.reduced_motion)

    def set_colour_blind(self, on):
        self.colour_blind = bool(on)
        self._save(self.KEY_COLOUR_BLIND, self.colour_blind)

    def toggle_show_fps(self):
        self.set_show_fps(not self.show_fps)
        return self.show_fps

    def toggle_reduced_motion(self):
        self.set_reduced_motion(not self.reduced_motion)
        return self.reduced_motion

    def toggle_colour_blind(self):
        self.set_colour_blind(not self.colour_blind)
        return self.colour_blind


# ---------------------------------------------------------------- quick queries for the drawing code
def reduced_motion():
    """True when REDUCED MOTION is on: no screen shake, glitch bursts, big flashes or strobes."""
    return DisplaySettings.get().reduced_motion


def colour_blind():
    """True when COLOUR-BLIND SAFE is on: blue / orange instead of green / red for good / bad signals."""
    return DisplaySettings.get().colour_blind


def calm(live, steady):
    """`steady` with REDUCED MOTION on, otherwise `live`: a blinking or pulsing highlight becomes a constant one, so
    the information stays on screen without the strobe."""
    return steady if DisplaySettings.get().reduced_motion else live


# ---------------------------------------------------------------- window geometry
TITLE_BAR = 28   # points kept free above a restored window for its title bar


class WindowMemory:
    """The last windowed geometry of the game window (prefs node 'window')."""
    PREFS_NODE = "window"
    KEY = "geometry"

    def __init__(self, store=None):
        self.store = store if store is not None else MemoryStore()
        self._last = None

    @staticmethod
    def in_memory(data=None):
        return WindowMemory(MemoryStore(data))

    @staticmethod
    def persistent():
        try:
            return WindowMemory(prefs.node(WindowMemory.PREFS_NODE))
        except Exception:
            return WindowMemory.in_memory()

    def load(self):
        """{'x', 'y', 'w', 'h', 'maximized'} or None (nothing saved yet, or unreadable)."""
        try:
            d = self.store.get(self.KEY, None)
        except Exception:
            return None
        if not isinstance(d, dict):
            return None
        out = {}
        for k in ("x", "y", "w", "h"):
            v = d.get(k)
            if not isinstance(v, int) or isinstance(v, bool):
                return None
            out[k] = v
        if out["w"] <= 0 or out["h"] <= 0:
            return None
        out["maximized"] = bool(d.get("maximized", False))
        return out

    def save(self, x, y, w, h, maximized):
        """Stores the geometry; a no-op when nothing changed since the last save (one file write per real change)."""
        g = {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "maximized": bool(maximized)}
        if g == self._last:
            return False
        try:
            self.store.put(self.KEY, g)
        except Exception:
            return False
        self._last = g
        return True


def place_on_displays(rect, displays, min_size, top_margin=TITLE_BAR):
    """Where to put a window saved at rect = (x, y, w, h) given the usable bounds (x, y, w, h) of the displays connected
    now: on the display it overlaps most, moved and shrunk so it fits entirely (with top_margin free above it for the
    title bar), never below min_size. A window that overlaps no display (its monitor was disconnected, the arrangement
    changed) is centred on the first (main) display. None when no display is known."""
    if not displays:
        return None
    x, y, w, h = rect
    best, best_area = None, 0
    for d in displays:
        ix = min(x + w, d[0] + d[2]) - max(x, d[0])
        iy = min(y + h, d[1] + d[3]) - max(y, d[1])
        if ix > 0 and iy > 0 and ix * iy > best_area:
            best, best_area = d, ix * iy
    on_screen = best is not None
    dx, dy, dw, dh = best if on_screen else displays[0]
    mw, mh = min_size
    top = min(top_margin, max(0, dh - mh))
    w = max(mw, min(w, dw))
    h = max(mh, min(h, dh - top))
    if not on_screen:
        x = dx + (dw - w) // 2
        y = dy + top + (dh - top - h) // 2
    x = max(dx, min(x, dx + dw - w))
    y = max(dy + top, min(y, dy + dh - h))
    return int(x), int(y), int(w), int(h)
