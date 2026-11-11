"""The title screen's animated logo (the beta 4.0 wordmark and emblem effects over the flat 4.1 layout) and the shared
cyberpunk backdrop of the menu screens (ui/backdrop.py). Screens are built and painted offscreen; nothing opens a
window."""
import random

import numpy as np
import pytest
import skia

from lindefense import prefs
from lindefense.ui import backdrop as bd
from lindefense.ui.acm import GLabel
from lindefense.ui.backdrop import Backdrop
from lindefense.ui.campaign_screen import CampaignScreen
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.graphics_settings import GraphicsSettings
from lindefense.ui.jawt import Graphics2D, reset_canvas_state
from lindefense.ui.map_select_screen import MapSelectScreen
from lindefense.ui.menu_screen import MenuScreen

Q = GraphicsSettings.Quality


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    GraphicsSettings.set_instance(GraphicsSettings.in_memory())
    yield
    DisplaySettings.set_instance(None)
    GraphicsSettings.set_instance(None)
    prefs._nodes.clear()


class _App:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _reduced_motion(on):
    DisplaySettings.get().reduced_motion = on


def _paint(obj, scale=1.0, w=1600, h=1000):
    surf = skia.Surface.MakeRasterN32Premul(int(w * scale), int(h * scale))
    cv = surf.getCanvas()
    cv.clear(0xff000000)
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.scale(scale, scale)
    obj.paint(g)
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray()[:, :, :3].copy()   # BGR rows


def _run(m, seconds, dt=1 / 30.0):
    """Frames of the title screen; returns what the logo did: glitch bursts, slices, shimmers, flickering letters."""
    seen = {"chroma": 0, "slices": 0, "shimmer": 0, "flicker": 0, "glow": set(), "pads": set()}
    t = 0.0
    while t < seconds:
        m.frame(dt)
        t += dt
        seen["chroma"] += m.chroma_m.is_visible() and m.chroma_c.is_visible()
        seen["slices"] += any(s.is_visible() for s in m.slices)
        seen["shimmer"] += m.shimmer.is_visible()
        seen["flicker"] += any(p.get_fill_color().get_alpha() < 255 for p in m.main.polys)
        seen["glow"].add(m.glow[0].polys[0].get_fill_color().get_alpha())
        seen["pads"].add(tuple(p.get_fill_color().get_rgb() for p in m.emblem.pads))
    return seen


def test_title_logo_animates_like_beta_4_0(check):
    m = MenuScreen(_App())
    check(m.intro_bar.is_visible() and not any(m.main.letters[i].is_visible() for i in range(m.main.get_letter_count())),
          "the boot-up starts dark, with the intro light bar")
    m.frame(0.4)
    shown = sum(m.main.letters[i].is_visible() for i in range(m.main.get_letter_count()))
    check(0 < shown < m.main.get_letter_count(), "the letters build in one after another (%d shown at 0.4 s)" % shown)
    check(all(g.letters[i].is_visible() == m.main.letters[i].is_visible() for g in m.glow for i in range(len(g.letters))),
          "the glow stack builds in with the letters")
    seen = _run(m, 16)
    check(m.intro_done and not m.intro_bar.is_visible(), "the intro ends and its light bar goes away")
    check(len(m.glow) == 3 and m.main.outline is not None, "three glow copies behind a cyan-outlined wordmark")
    check(seen["chroma"] > 0 and seen["slices"] > 0, "chromatic glitch bursts with slices happen (%s)" % seen)
    check(seen["shimmer"] > 0, "a shimmer sweeps across the wordmark")
    check(seen["flicker"] > 0, "single letters flicker now and then")
    check(len(seen["glow"]) > 3, "the glow stack breathes (%d alphas)" % len(seen["glow"]))
    check(len(seen["pads"]) > 1, "the emblem's circuit pads light up in turn")
    check(not m.chroma_m.is_visible() or m.glitch_left > 0, "glitch copies only show during a burst")
    band = [o for o in m if isinstance(o, bd.Scanlines)]
    check(len(band) == 1 and band[0].get_y() <= MenuScreen.LOGO_Y - 60 and band[0].get_y() + band[0].h >= MenuScreen.LOGO_Y + 60
          and band[0].get_y() + band[0].h < m.subtitle.get_y() - m.subtitle.get_height(),
          "scanlines stripe the wordmark only (not the subtitle or the buttons)")
    _reduced_motion(True)   # hold the backdrop still so the two paints differ by the shimmer only
    m.glitch_left = m.flicker_left = m.shimmer_left = 0.0
    m.chroma_m.set_visible(False)
    m.chroma_c.set_visible(False)
    for s in m.slices:
        s.set_visible(False)
    m.shimmer.set_visible(False)
    plain = _paint(m, 0.5)
    m.shimmer.set_location(800, MenuScreen.LOGO_Y)
    m.shimmer.set_visible(True)
    lit = _paint(m, 0.5)
    rows = np.nonzero((lit != plain).any(axis=(1, 2)))[0] * 2   # logical y of the changed rows
    half = MenuScreen.LOGO_H * 1.16 / 2
    check(len(rows) > 0 and rows.min() >= MenuScreen.LOGO_Y - half - 2 and rows.max() <= MenuScreen.LOGO_Y + half + 2,
          "the shimmer lights the logo only, never a bar over the backdrop (rows %s..%s)" % (rows.min() if len(rows) else None, rows.max() if len(rows) else None))
    m.shimmer.set_visible(False)
    _reduced_motion(False)
    m.toggle_help()
    m.glitch_left = m.flicker_left = m.shimmer_left = 0.0
    m.chroma_m.set_visible(False)
    m.shimmer.set_visible(False)
    seen = _run(m, 12)
    check(seen["chroma"] == 0 and seen["shimmer"] == 0 and seen["flicker"] == 0,
          "with a pop-up open the title starts no glitch, shimmer or flicker (%s)" % seen)


def test_reduced_motion_title_is_calm(check):
    _reduced_motion(True)
    m = MenuScreen(_App())
    m.frame(0.016)
    check(m.intro_done and all(m.main.letters[i].is_visible() for i in range(m.main.get_letter_count())),
          "reduced motion: the whole wordmark shows at once")
    seen = _run(m, 16)
    check(seen["chroma"] == 0 and seen["slices"] == 0 and seen["shimmer"] == 0 and seen["flicker"] == 0,
          "reduced motion: no glitch bursts, slices, shimmer or flicker (%s)" % seen)
    check(len(seen["pads"]) == 1, "reduced motion: the emblem's pads hold still")
    check(not m.intro_bar.is_visible(), "reduced motion: no intro light bar")
    _reduced_motion(False)


def test_menu_screens_share_one_backdrop(check):
    bd._CACHE.clear()
    screens = [("menu", MenuScreen(_App())), ("map select", MapSelectScreen(_App())), ("campaign", CampaignScreen(_App()))]
    for name, s in screens:
        check(isinstance(getattr(s, "backdrop", None), Backdrop) and list(s)[0] is s.backdrop,
              "%s: the shared backdrop, painted first" % name)
        s.frame(0.05)
        _paint(s, 0.5)
    imgs = {id(s.backdrop.img) for _n, s in screens}
    check(len(imgs) == 1 and len(bd._CACHE) == 1, "one static bitmap, shared by every menu screen (%d, %d)" % (len(imgs), len(bd._CACHE)))
    img = screens[0][1].backdrop.img
    check(img.get_width() == 800, "rendered at the pixel scale it is shown at (%d px wide at 0.5x)" % img.get_width())
    _paint(screens[0][1], 0.5)
    check(screens[0][1].backdrop.img is img, "repainting reuses the bitmap")


def test_backdrop_bitmap_scale_is_capped(check):
    bd._CACHE.clear()
    b = Backdrop()
    _paint(b, 4.0, 100, 60)   # a 5K screen: the bitmap stops at MAX_SCALE
    check(b.img.get_width() == int(bd.W * bd.MAX_SCALE), "HIGH: capped at %.1fx (%d px)" % (bd.MAX_SCALE, b.img.get_width()))
    GraphicsSettings.get().set_quality(Q.LOW)
    _paint(b, 4.0, 100, 60)
    check(b.img.get_width() == int(bd.W * Q.LOW.map_max_scale), "LOW: capped at the preset's %.1fx" % Q.LOW.map_max_scale)
    check(len(bd._CACHE) == 1, "only the newest bitmap is kept")


def test_backdrop_motion_settings(check):
    b = Backdrop()
    for q, n in ((Q.LOW, 0), (Q.MEDIUM, 8), (Q.HIGH, 14)):
        GraphicsSettings.get().set_quality(q)
        check(b.live_count() >= n and (q is not Q.LOW or b.live_count() == 0),
              "%s: %d live accents (motes %d)" % (q.name, b.live_count(), n))
    GraphicsSettings.get().set_quality(Q.HIGH)
    check(b.live_count() < 25, "a handful of live accents, not hundreds (%d)" % b.live_count())
    a = _paint(b, 0.5)
    for _ in range(90):
        b.frame(1 / 30.0)
    moved = _paint(b, 0.5)
    check((a != moved).any(), "normal motion: motes drift, the scan light glides")
    _reduced_motion(True)
    still = _paint(b, 0.5)
    for _ in range(90):
        b.frame(1 / 30.0)
    check((still == _paint(b, 0.5)).all(), "reduced motion: the backdrop holds still")
    _reduced_motion(False)
    GraphicsSettings.get().set_quality(Q.LOW)
    low = _paint(b, 0.5)
    for _ in range(90):
        b.frame(1 / 30.0)
    check((low == _paint(b, 0.5)).all(), "LOW quality: only the static bitmap (no live accents)")


def test_backdrop_is_deterministic_and_keeps_its_own_randomness(check):
    state = random.getstate()
    a, b = Backdrop(), Backdrop()
    for _ in range(200):
        a.frame(1 / 30.0)
        b.frame(1 / 30.0)
    check((_paint(a, 0.5) == _paint(b, 0.5)).all(), "two backdrops with the same seed draw the same frames")
    check(random.getstate() == state, "the backdrop never touches Python's shared random numbers")
    check(a.pulse is not None or a.pulse_wait > 0, "data pulses are scheduled")


def _lum(rgb):
    c = np.asarray(rgb, dtype=float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def test_backdrop_keeps_menu_text_readable(check):
    _reduced_motion(True)
    m = MenuScreen(_App())
    m.skip_intro()
    px = _paint(Backdrop())[:, :, ::-1]   # RGB
    bg = _lum(px)
    flat = float(_lum([MenuScreen.BG.get_red(), MenuScreen.BG.get_green(), MenuScreen.BG.get_blue()]))
    labels = [o for o in m if isinstance(o, GLabel) and o.get_label()]
    check(len(labels) >= 4, "subtitle, tagline, version and footer checked")
    for o in labels:
        x, y, w, h = o.get_x(), o.get_y(), o.get_width(), o.get_height()
        box = bg[max(0, int(y - h)):int(y + 4), int(x):int(x + w) + 1]
        c = o.get_color()
        lt = float(_lum([c.get_red(), c.get_green(), c.get_blue()]))
        ratio = (lt + 0.05) / (float(box.max()) + 0.05)
        flat_ratio = (lt + 0.05) / (flat + 0.05)
        check(ratio >= 0.85 * flat_ratio, "%r keeps its contrast over the backdrop (%.1f : 1, flat 4.1 background %.1f : 1)"
              % (o.get_label(), ratio, flat_ratio))
    _reduced_motion(False)
