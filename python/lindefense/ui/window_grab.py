"""Palantir's fourth-wall break (phase 3, System Takeover): shrinks the real game window to SHRINK of its size, drifts
it a little, and reports the window's size back to the simulation every frame. Dragging it back above
WindowLink.SEAL_THRESHOLD breaks the seal; the window is restored when Palantir dies or the match ends.

Safety: only ever sets the window's bounds (never full screen / maximised), never below MIN_W x MIN_H, always clamped
inside the visible screen, animated over ANIM_SECONDS, stops at once if the player resizes, and is inert in headless
runs, tests and the scripted demo. The geometry is pure static helpers so it is tested headlessly.

The window is reached through an adapter with: get_bounds() -> Rect, set_bounds(Rect), is_showing(),
is_maximized_or_full_screen(), min_size() -> (w, h), usable_screen() -> Rect.
"""
import math
import os

from lindefense.ui import window_effects

SHRINK = 0.72
DRIFT_X, DRIFT_Y = 0.04, 0.03
ANIM_SECONDS = 1.5
MIN_W, MIN_H = 640, 420


def _round(x):
    return int(math.floor(x + 0.5))


class Rect:
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x, y, width, height):
        self.x, self.y, self.width, self.height = int(x), int(y), int(width), int(height)

    @property
    def center_x(self):
        return self.x + self.width / 2.0

    @property
    def center_y(self):
        return self.y + self.height / 2.0

    @property
    def size(self):
        return (self.width, self.height)

    def contains(self, r):
        return (r.x >= self.x and r.y >= self.y and r.x + r.width <= self.x + self.width
                and r.y + r.height <= self.y + self.height)

    def copy(self):
        return Rect(self.x, self.y, self.width, self.height)

    def __eq__(self, o):
        return isinstance(o, Rect) and (self.x, self.y, self.width, self.height) == (o.x, o.y, o.width, o.height)

    def __repr__(self):
        return "Rect(%d, %d, %d, %d)" % (self.x, self.y, self.width, self.height)


def is_headless():
    return os.environ.get("SDL_VIDEODRIVER") == "dummy" or bool(os.environ.get("LINDEFENSE_HEADLESS"))


def environment_allows():
    """False in headless runs, the scripted demo and with LINDEFENSE_WINDOWFX=false."""
    if is_headless():
        return False
    if os.environ.get("LINDEFENSE_DEMO"):
        return False
    return os.environ.get(window_effects.ENV, "").lower() != "false"


# ---------------------------------------------------------------- pure geometry
def plan(current, baseline, screen, min_size, drift_sign):
    w, h = _round(baseline.width * SHRINK), _round(baseline.height * SHRINK)
    cx = current.center_x + drift_sign * screen.width * DRIFT_X
    cy = current.center_y + drift_sign * screen.height * DRIFT_Y
    return clamp_to_screen(Rect(_round(cx - w / 2.0), _round(cy - h / 2.0), w, h), screen, min_size)


def clamp_to_screen(r, screen, min_size):
    mw, mh = min_size
    w = min(max(r.width, mw), max(mw, screen.width))
    h = min(max(r.height, mh), max(mh, screen.height))
    x = max(screen.x, min(r.x, screen.x + screen.width - w))
    y = max(screen.y, min(r.y, screen.y + screen.height - h))
    return Rect(x, y, w, h)


def fraction(current, baseline):
    """current / baseline are (w, h); the smaller of the two ratios, 1.0 without a baseline."""
    if baseline is None or baseline[0] <= 0 or baseline[1] <= 0:
        return 1.0
    return min(current[0] / float(baseline[0]), current[1] / float(baseline[1]))


def lerp(a, b, t):
    return Rect(_round(a.x + (b.x - a.x) * t), _round(a.y + (b.y - a.y) * t),
                _round(a.width + (b.width - a.width) * t), _round(a.height + (b.height - a.height) * t))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- controller
class WindowGrab:
    def __init__(self, window):
        self._window = window
        self._game = None
        self._baseline = None
        self._from = self._to = self._last_set = None
        self._anim = -1.0
        self._holding = self._releasing = False
        self._drift_sign = 1
        self._grabs = 0

    @staticmethod
    def create(window, demo):
        return WindowGrab(window if window is not None and not demo and environment_allows() else None)

    environment_allows = staticmethod(environment_allows)
    SHRINK, DRIFT_X, DRIFT_Y, ANIM_SECONDS, MIN_W, MIN_H = SHRINK, DRIFT_X, DRIFT_Y, ANIM_SECONDS, MIN_W, MIN_H
    plan = staticmethod(plan)
    clamp_to_screen = staticmethod(clamp_to_screen)
    fraction = staticmethod(fraction)
    lerp = staticmethod(lerp)
    ease = staticmethod(ease)

    def is_active(self):
        return self._window is not None

    def is_holding(self):
        return self._holding

    def get_grabs(self):
        return self._grabs

    def frame(self, dt, g):
        from lindefense.sim.game import State
        if self._window is None:
            return
        if g is not self._game:
            if self._holding:
                self._start_release()
            self._game = g
        if g is None:
            self._step(dt)
            return
        link = g.get_window_link()
        requests = link.consume_grab_requests()
        active = link.is_takeover_active() and g.get_state() is State.PLAYING
        if not window_effects.is_enabled():
            if self._holding:
                self._start_release()
            self._step(dt)
            g.set_window_fraction(1.0)
            return
        if active and requests > 0:
            self._grab(g)
        if self._holding and not self._releasing and not active:
            self._start_release()
        self._step(dt)
        g.set_window_fraction(fraction(self._window.get_bounds().size, self._baseline.size)
                              if self._holding and not self._releasing and self._baseline is not None else 1.0)

    def _min_size(self):
        m = self._window.min_size() or (0, 0)
        return (max(MIN_W, m[0]), max(MIN_H, m[1]))

    def _grab(self, g):
        w = self._window
        if not w.is_showing():
            return
        if w.is_maximized_or_full_screen():
            g.set_banner("PALANTIR REACHED FOR YOUR WINDOW  -  blocked: it is maximized", 0x7fd8a8, 3)
            return
        cur = w.get_bounds()
        if not self._holding or self._releasing:
            self._baseline = cur.copy()
        target = plan(cur, self._baseline, w.usable_screen(), self._min_size(), self._drift_sign)
        self._drift_sign = -self._drift_sign
        self._holding, self._releasing = True, False
        self._grabs += 1
        if target.width < cur.width - 2 or target.height < cur.height - 2:
            self._animate(cur, target)
            g.set_banner("PALANTIR HAS TAKEN YOUR WINDOW  -  drag it back to break the seal", 0xff4d4d, 4)

    def _start_release(self):
        if not self._holding:
            return
        self._releasing = True
        w = self._window
        cur = w.get_bounds()
        b = self._baseline
        if b is None or w.is_maximized_or_full_screen() or (cur.width >= b.width and cur.height >= b.height):
            self._finish()
            return
        back = Rect(b.x, b.y, max(cur.width, b.width), max(cur.height, b.height))
        self._animate(cur, clamp_to_screen(back, w.usable_screen(), self._min_size()))

    def _finish(self):
        self._holding = self._releasing = False
        self._baseline = None
        self._anim = -1.0
        self._last_set = None

    def _animate(self, a, b):
        self._from, self._to = a.copy(), b.copy()
        self._anim = 0.0
        self._last_set = None

    def _step(self, dt):
        if self._anim < 0:
            return
        now = self._window.get_bounds()
        ls = self._last_set
        if ls is not None and (abs(now.width - ls.width) > 4 or abs(now.height - ls.height) > 4):
            self._anim = -1.0
            self._last_set = None
            if self._releasing:
                self._finish()
            return
        self._anim = min(1.0, self._anim + max(0.0, dt) / ANIM_SECONDS)
        r = lerp(self._from, self._to, ease(self._anim))
        self._window.set_bounds(r)
        self._last_set = r
        if self._anim >= 1:
            self._anim = -1.0
            self._last_set = None
            if self._releasing:
                self._finish()
