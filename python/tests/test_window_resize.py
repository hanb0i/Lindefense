"""Window resizing on the real video driver (the rest of the suite runs on SDL's dummy driver, which has no OpenGL).

Regression: pygame-ce makes its own GL context current whenever an opengl Window is resized. The app used to render
with a second context of its own, so after the first resize every frame was drawn into a context that was no longer
current and the window went blank. Also covers the live-resize event watch that keeps the game drawing while the
player drags a window edge.
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

_SCRIPT = r"""
import ctypes, json, sys
import numpy as np, pygame, skia
from lindefense.app import LindefenseApp
from lindefense.ui.jawt import Color

app = LindefenseApp()
out = {"gpu": app.gr is not None}
sdl = app.sdl
sdl.SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

def red_square(g):
    g.set_color(Color(255, 0, 0))
    g.fill_rect(0, 0, 100, 100)
app.root.paint = red_square   # paint() draws only this: a 100x100 square at the canvas origin

shots = []
if app.gr is not None:
    real_swap = sdl.SDL_GL_SwapWindow
    def swap(win):   # read the frame back just before it is presented
        shots.append(app.surface.makeImageSnapshot().toarray())
        return real_swap(win)
    sdl.SDL_GL_SwapWindow = swap

def red_fraction():
    shots.clear()
    app.paint()
    if not shots:
        return None
    reg = shots[-1][4:96, 4:96, :3].reshape(-1, 3).astype(int)
    return float((np.abs(reg - (255, 0, 0)).sum(1) < 60).mean())

def pump():
    for ev in pygame.event.get():
        app._handle(ev)

out["before"] = red_fraction()
for w, h in ((800, 500), (1100, 700), (700, 900)):
    sdl.SDL_SetWindowSize(app.win_ptr, w, h)
    pump()
    out["after_%dx%d" % (w, h)] = red_fraction()
    out["px_%dx%d" % (w, h)] = [app.px_w, app.px_h]

ticks = []
app._tick = lambda: ticks.append(1)
app._install_live_resize()
app._pumping = True           # as if blocked inside pygame.event.get() during a drag
sdl.SDL_SetWindowSize(app.win_ptr, 900, 600)
out["live_ticks"] = len(ticks)
out["live_px"] = [app.px_w, app.px_h]
app._pumping = False          # resizes the game makes itself must not re-enter the frame loop
sdl.SDL_SetWindowSize(app.win_ptr, 1000, 650)
out["idle_ticks"] = len(ticks) - out["live_ticks"]
pump()
app._remove_live_resize()
print("RESULT " + json.dumps(out))
"""


def _run_probe():
    env = dict(os.environ)
    env.pop("SDL_VIDEODRIVER", None)   # conftest selects the dummy driver; this test needs the real one
    env.update(LINDEFENSE_HIDDEN="1", LINDEFENSE_NOSOUND="1", SDL_AUDIODRIVER="dummy")
    root = os.path.join(os.path.dirname(__file__), "..")
    with tempfile.TemporaryDirectory() as prefs:
        env["LINDEFENSE_PREFS_DIR"] = prefs
        try:
            p = subprocess.run([sys.executable, "-W", "ignore", "-c", _SCRIPT], cwd=root, env=env,
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            pytest.fail("window resize probe timed out")
    lines = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not lines:
        if "No available video device" in p.stderr or "video system not initialized" in p.stderr:
            pytest.skip("no video device")
        pytest.fail("probe failed:\n" + p.stdout[-2000:] + p.stderr[-4000:])
    return json.loads(lines[-1][len("RESULT "):])


def test_window_resize(check):
    r = _run_probe()
    if r["gpu"]:
        check(r["before"] is not None and r["before"] > 0.95, "frame drawn before any resize: %s" % r["before"])
        for size in ("800x500", "1100x700", "700x900"):
            f = r["after_" + size]
            check(f is not None and f > 0.95, "frame drawn after resizing to %s: red fraction %s" % (size, f))
    for size, (w, h) in (("800x500", (800, 500)), ("1100x700", (1100, 700)), ("700x900", (700, 900))):
        px = r["px_" + size]
        check(px[0] >= w and px[1] >= h and abs(px[0] / float(w) - px[1] / float(h)) < 0.01,
              "canvas follows the window at %s: %s" % (size, px))
    check(r["live_ticks"] >= 1, "a resize during a live drag redraws the frame (ticks %d)" % r["live_ticks"])
    check(r["live_px"][0] >= 900 and r["live_px"][1] >= 600, "the live redraw uses the new size: %s" % r["live_px"])
    check(r["idle_ticks"] == 0, "resizes made outside event pumping don't re-enter the frame loop (%d)" % r["idle_ticks"])
