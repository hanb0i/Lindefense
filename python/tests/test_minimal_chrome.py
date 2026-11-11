"""The minimal UI chrome: flat panels with one thin border, flat buttons with distinct hover / selected / pressed / primary /
disabled states, labels that fit their buttons, no decorative "// micro" labels, and a title screen without the old busy
props or blinking text. Screens are built and painted offscreen; nothing opens a window."""
import skia
import pytest

from kit import buildable_near, force_place, kill_outright, new_game, run_seconds, spawn_at
from lindefense import prefs
from lindefense.enemy.types import EnemyType
from lindefense.sim.game import Game, State
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui.acm import GCompound, GLabel, GLine
from lindefense.ui.backdrop import Backdrop
from lindefense.ui.catalog_screen import CatalogScreen
from lindefense.ui.cyber import Cyber
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.jawt import Color, Font, Graphics2D, reset_canvas_state
from lindefense.ui.map_select_screen import MapSelectScreen
from lindefense.ui.menu_screen import MenuScreen
from lindefense.ui.neon_button import NeonButton
from lindefense.ui.stats_screen import StatsScreen
from lindefense.ui.ui_button import UIButton
from lindefense.wave import waves


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


class _App:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _walk(node, out):
    out.append(node)
    if isinstance(node, GCompound):
        for o in node:
            _walk(o, out)
    return out


def _placed(node, ox=0.0, out=None):
    """(object, absolute x) for every object under node (compounds offset their children)."""
    out = [] if out is None else out
    out.append((node, ox + node.get_x()))
    if isinstance(node, GCompound):
        for o in node:
            _placed(o, ox + node.get_x(), out)
    return out


def _labels(node):
    return [o.get_label() for o in _walk(node, []) if isinstance(o, GLabel) and o.is_visible()]


def _pixels(obj, w=200, h=120):
    surf = skia.Surface.MakeRasterN32Premul(w, h)
    surf.getCanvas().clear(0xff000000)
    reset_canvas_state(surf.getCanvas())
    obj.paint(Graphics2D(surf.getCanvas()))
    return surf.makeImageSnapshot().toarray()   # BGRA rows


def test_panels_are_flat_with_one_thin_border(check):
    for gone in ("scan", "glow", "ticks"):
        check(not hasattr(Cyber.Chamfer, gone), "Chamfer.%s() is gone (no scanlines, glow halos or corner ticks)" % gone)
    check(not hasattr(Cyber, "GlitchText"), "no glitch text helper")
    p = Cyber.Chamfer(40, 30, 120, 60, 26).fill(Color(20, 40, 60)).border(Color(200, 0, 0))
    px = _pixels(p)
    check(tuple(px[60, 100][:3]) == (20, 40, 60), "flat fill inside (got %s)" % (px[60, 100][:3],))
    check(px[30, 100][0] > 150 and tuple(px[31, 100][:3]) == (20, 40, 60), "one 1 px border along the top edge (%s, %s)" % (px[30, 100][:3], px[31, 100][:3]))
    check(px[27, 100][:3].max() == 0 and px[60, 36][:3].max() == 0, "nothing painted outside the border (no halo)")
    check(px[34, 44][:3].max() > 0 and px[31, 41][:3].max() == 0, "a small corner cut (capped: a 26 px cut would leave (44, 34) empty)")


def test_button_states_are_distinct(check):
    def look(**state):
        b = UIButton(0, 0, 160, 40, "PLAY", lambda: None)
        b.set_accent(Cyber.CYAN)
        b.set_primary(state.get("primary", False))
        b.set_enabled(state.get("enabled", True))
        b.set_selected(state.get("selected", False))
        b.set_hover(state.get("hover", False))
        if state.get("pressed"):
            b.click()
        for _ in range(30):
            b.animate(1 / 30.0)
        if state.get("pressed"):
            b.press_t = 1.0
            b.apply()
        f, e, t = b.frame.f_fill, b.frame.f_border, b.text.get_color()
        return (None if f is None else f.get_rgb(), None if e is None else e.get_rgb(), t.get_rgb())
    states = {"idle": {}, "hover": {"hover": True}, "selected": {"selected": True}, "pressed": {"pressed": True},
              "primary": {"primary": True}, "disabled": {"enabled": False}}
    looks = {k: look(**v) for k, v in states.items()}
    check(len(set(looks.values())) == len(looks), "every state looks different (%s)" % looks)
    check(not hasattr(UIButton, "set_pulse"), "no breathing glow on buttons")
    m = NeonButton(0, 0, 200, 50, "QUIT", Cyber.display(Font.BOLD, 20), Cyber.CYAN, None)
    check(isinstance(m, UIButton) and m.frame.cut == UIButton.CUT, "menu buttons are the shared flat button (same frame and cut)")


def _won_game():
    g = new_game(0, 42)
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 3)
    wm = g.get_wave_manager()
    for _ in range(waves.WAVE_COUNT - 1):
        wm.start_next_wave()
        wm.end_wave()
    wm.start_next_wave()
    kill_outright(g, spawn_at(g, EnemyType.PALANTIR, None, 0, 60))
    run_seconds(g, Game.VICTORY_SEQUENCE_TIME + 0.2)
    assert g.get_state() is State.VICTORY
    return g


def _screens():
    """(name, root) for every screen the chrome restyle covers, built offscreen."""
    out = []
    m = MenuScreen(_App())
    m.skip_intro()
    out.append(("menu", m))
    s = MenuScreen(_App())
    s.toggle_settings()
    out.append(("settings", s.settings))
    h = MenuScreen(_App())
    h.toggle_help()
    out.append(("help", h.help))
    out.append(("catalog", CatalogScreen(None)))
    out.append(("records", StatsScreen(None)))
    ms = MapSelectScreen(_App())
    out.append(("map select", ms))
    b = MapSelectScreen(_App())
    b.open_briefing(1)
    out.append(("briefing", b.briefing))
    r = MapSelectScreen(_App())
    r.open_reverse_briefing(1)
    out.append(("reverse briefing", r.briefing))
    d = MapSelectScreen(_App())
    d.open_daily_briefing()
    out.append(("daily briefing", d.briefing))
    g = new_game(1, 7)
    t = force_place(g, T.CLAUDE, buildable_near(g, Vec(700, 250), 200), 2)
    gs = GameScreen(_App(), g)
    gs.select_tower(t)
    gs.frame(0.02)
    out.append(("game", gs))
    p = GameScreen(_App(), new_game(1, 7))
    p.open_menu()
    p.frame(0.02)
    out.append(("pause menu", p))
    c = GameScreen(_App(), new_game(1, 7))
    c.open_menu()
    c.set_confirm(GameScreen.Confirm.QUIT)
    c.frame(0.02)
    out.append(("confirm", c))
    hs = GameScreen(_App(), new_game(1, 7))
    hs.toggle_hero_store()
    hs.frame(0.02)
    out.append(("hero store", hs))
    v = GameScreen(_App(), _won_game())
    v.frame(0.02)
    out.append(("epilogue", v.overlay))
    v.skip_epilogue()
    v.frame(0.02)
    out.append(("victory", v.overlay))
    v.set_end_page(1)
    out.append(("report", v.overlay))
    dg = new_game(2, 5)
    dg.get_variance().enable()
    ds = GameScreen(_App(), dg)
    ds.frame(0.05)
    out.append(("patch notes", ds.overlay))
    return out


def test_labels_fit_and_no_decorative_micro_labels(check):
    for name, root in _screens():
        objs = _walk(root, [])
        bad = [t for t in _labels(root) if t.startswith("//") or any(d in t for d in ("SYS.ONLINE", "THREAT LVL", "SECTOR //"))]
        check(not bad, "%s: no decorative micro labels (%s)" % (name, bad))
        for b in objs:
            if isinstance(b, UIButton) and b.is_visible() and b.get_text():
                tw = b.text.get_width() + (21 if b.has_icon else 0)
                check(tw <= b.w - 8, "%s: %r fits its %d px button (%.0f px)" % (name, b.get_text(), b.w, tw))
        for o, x in _placed(root):
            if isinstance(o, GLabel) and o.is_visible() and o.get_label():
                check(-1 <= x and x + o.get_width() <= 1601,
                      "%s: %r stays inside the 1600 px layout (x %.0f .. %.0f)" % (name, o.get_label(), x, x + o.get_width()))


def test_title_screen_keeps_its_chrome_quiet(check):
    """The beta 4.0 title effects are back (see test_title_backdrop.py), over one shared backdrop object; the
    old busy props stay gone and no text blinks."""
    m = MenuScreen(_App())
    m.skip_intro()
    top = list(m)
    lines = [o for o in top if isinstance(o, GLine)]
    check(not lines, "no full-screen scanlines, perspective grid or bracket lines (%d lines)" % len(lines))
    backdrops = [o for o in top if isinstance(o, Backdrop)]
    check(len(backdrops) == 1 and top[0] is backdrops[0], "the backdrop is one object, painted first")
    def shown(node, out):
        if node.is_visible():
            out.append(node)
            if isinstance(node, GCompound):
                for o in node:
                    shown(o, out)
        return out
    n = len(shown(m, []))
    check(n < 300, "the title screen shows ~250 objects (the logo's glow stack included), not the old rain / skyline / "
                   "grid (~1000): %d" % n)
    for name in ("rain_cols", "grid_rows", "windows", "sys_label", "threat_label", "ticker_label", "scan_bar", "sun_glow"):
        check(not hasattr(m, name), "no %s on the title screen" % name)
    for _ in range(10):
        m.frame(0.05)   # buttons settle into their resting look
    before = [o.get_color() for o in _walk(m, []) if isinstance(o, GLabel)]
    for _ in range(40):
        m.frame(0.05)
    after = [o.get_color() for o in _walk(m, []) if isinstance(o, GLabel)]
    check(before == after, "after the intro no text on the title screen blinks or pulses (only the logo and backdrop move)")
