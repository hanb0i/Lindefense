"""In-match safety and controls: confirmations (pause-menu MAIN MENU, window close, hero DISMISS), gameplay keys blocked
behind overlays, auto-pause when the window loses focus (not when Palantir's System Takeover moves it), the tactical
pause (P) that keeps the map usable, Esc's cancel / deselect / menu order, and the Tab / Shift+T / O / Shift+1-9
hotkeys. The real GameScreen is driven offscreen with key and mouse events; the app's window events go through
LindefenseApp._handle. Nothing opens a visible window."""
import json
import os
import subprocess
import sys
import tempfile
import time

import pygame
import pytest

from kit import buildable_near, force_place, new_game, spawn_at
from lindefense import prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.app import LindefenseApp, _WindowAdapter
from lindefense.enemy.types import EnemyType
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import Faction, TowerType as T
from lindefense.ui.acm import GCompound, GLabel
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.jawt import KeyEvent
from lindefense.ui.menu_screen import MenuScreen
from lindefense.ui.shop_layout import ShopLayout
from lindefense.ui.window_grab import Rect

AUTOMATION = ("LINDEFENSE_HIDDEN", "LINDEFENSE_DEMO", "LINDEFENSE_SMOKE")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    for k in AUTOMATION:
        monkeypatch.delenv(k, raising=False)
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


class _App:
    """The parts of LindefenseApp the game screen calls (records them)."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a: self.calls.append(name)


def _key(code, shift=False):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 1 if shift else 0, code, KeyEvent.CHAR_UNDEFINED)


def _press(s, code, shift=False):
    s.key_pressed(_key(code, shift))


def _click(s, b, right=False):
    s.mouse_pressed(b.get_x() + b.get_w() / 2, b.get_y() + b.get_h() / 2, right)


def _click_world(s, p, right=False):
    lx, ly = s.world_to_logical(p)
    s.mouse_pressed(lx, ly, right)


def _overlay_button(s, text):
    for b in s.overlay_buttons:
        if b.get_text() == text:
            return b
    return None


def _texts(c):
    out = []
    for i in range(c.get_element_count()):
        e = c.get_element(i)
        if isinstance(e, GLabel):
            out.append(e.get_label())
        elif isinstance(e, GCompound):
            out.extend(_texts(e))
    return out


def _match(cash=1_000_000, app=None):
    g = new_game(0)
    g.add_cash(cash, None)
    s = GameScreen(app if app is not None else _App(), g)
    s.frame(0.02)
    return g, s


def _bare_app():
    """A LindefenseApp without a window: enough for _handle's window / key events."""
    app = LindefenseApp.__new__(LindefenseApp)
    app.running = True
    app.sdl = app.win_ptr = None
    app.game_screen = app.menu = app.map_select = None
    app.window_grab = None
    app._init_match_safety()
    app._has_input_focus = lambda: False
    return app


def _ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


def _key_ev(k, mod=0, uni=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=uni)


# ---------------------------------------------------------------- 1. confirmations
def test_pause_menu_confirmations(check):
    g, s = _match()
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150))   # something to keep: leaving saves the run
    app = s.app
    _click(s, s.hud.menu_btn)
    check(s.is_menu_open() and g.is_paused(), "MENU button opens the pause menu")
    _click(s, _overlay_button(s, "MAIN MENU"))
    check(s.get_pending_confirm() == 3 and "show_menu" not in app.calls, "MAIN MENU asks first (nothing left yet)")
    check("Leave for the main menu? Your run is saved: CONTINUE it there." in _texts(s.overlay), "the MAIN MENU question shows")
    _click(s, _overlay_button(s, "NO"))
    check(s.get_pending_confirm() == 0 and s.is_menu_open() and not app.calls, "NO returns to the pause menu")
    _click(s, _overlay_button(s, "MAIN MENU"))
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_pending_confirm() == 0 and s.is_menu_open() and not app.calls, "Esc on a confirmation = NO (menu stays)")
    _click(s, _overlay_button(s, "MAIN MENU"))
    _click(s, _overlay_button(s, "YES"))
    check(app.calls == ["show_menu"], "YES leaves for the main menu (%s)" % app.calls)
    for label, code, call in (("RESTART", 1, "restart_level"), ("QUIT LEVEL", 2, "quit_level"), ("MAIN MENU", 3, "show_menu")):
        g, s = _match()
        s.open_menu()
        _click(s, _overlay_button(s, label))
        check(s.get_pending_confirm() == code and not s.app.calls, "%s asks first" % label)
        _press(s, KeyEvent.VK_ENTER)
        check(s.app.calls == [call], "Enter answers YES on %s (%s)" % (label, s.app.calls))
    g, s = _match()
    s.open_menu()
    _press(s, KeyEvent.VK_ENTER)
    check(s.is_menu_open() and not s.app.calls, "Enter without a confirmation does nothing")


def test_window_close_asks_during_a_match(check, monkeypatch):
    app = _bare_app()
    app._handle(_ev(pygame.WINDOWCLOSE))
    check(not app.running, "closing outside a match quits at once")

    app = _bare_app()
    g, s = _match(app=app)
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150))   # something to keep: quitting saves the run
    app.game_screen = s
    app._handle(_ev(pygame.WINDOWCLOSE))
    app._handle(_ev(pygame.QUIT))       # one click on the close button sends both
    check(app.running, "closing during a match does not quit")
    check(s.is_menu_open() and g.is_paused() and s.get_pending_confirm() == 4, "the QUIT GAME? confirmation shows")
    check("Quit Lindefense? Your run is saved: CONTINUE it next time." in _texts(s.overlay), "with the run-is-saved question")
    _click(s, _overlay_button(s, "NO"))
    check(app.running and s.is_menu_open() and s.get_pending_confirm() == 0, "NO keeps the run (pause menu)")
    app._handle(_key_ev(pygame.K_ESCAPE, uni="\x1b"))
    check(not s.is_menu_open() and not g.is_paused(), "Esc then resumes the match")
    app._last_close_request -= 10
    app._handle(_ev(pygame.QUIT))       # Cmd+Q
    check(app.running and s.get_pending_confirm() == 4, "Cmd+Q asks too")
    app._last_close_request -= 10
    app._handle(_ev(pygame.WINDOWCLOSE))
    check(not app.running, "a second close request while the confirmation shows quits")

    app = _bare_app()
    g, s = _match(app=app)
    app.game_screen = s
    app._handle(_ev(pygame.WINDOWCLOSE))
    _click(s, _overlay_button(s, "YES"))
    check(not app.running, "YES quits")

    app = _bare_app()
    g, s = _match(app=app)
    app.game_screen = s
    app._handle(_ev(pygame.WINDOWCLOSE))
    app._handle(_key_ev(pygame.K_RETURN, uni="\r"))
    check(not app.running, "Enter on the confirmation quits")

    app = _bare_app()
    g, s = _match(app=app)
    app.game_screen = s
    s.toggle_pause()
    app._handle(_ev(pygame.WINDOWCLOSE))
    check(app.running and s.get_pending_confirm() == 4, "asks during the tactical pause too")
    _press(s, KeyEvent.VK_ESCAPE)
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.is_tactically_paused() and not s.is_menu_open(), "NO + Esc lands back in the tactical pause")

    app = _bare_app()
    g, s = _match(app=app)
    app.game_screen = s
    g.lose_lives(Game.START_LIVES, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(400):
        if g.get_state() is not State.PLAYING:
            break
        s.frame(Game.DT)
    s.frame(0.02)
    check(g.get_state() is State.DEFEAT, "match lost")
    app._handle(_ev(pygame.WINDOWCLOSE))
    check(not app.running, "closing on the end screen quits at once")

    for var in AUTOMATION:
        monkeypatch.setenv(var, "1")
        app = _bare_app()
        g, s = _match(app=app)
        app.game_screen = s
        app._handle(_ev(pygame.WINDOWCLOSE))
        check(not app.running and not s.is_menu_open(), "%s runs quit at once" % var)
        monkeypatch.delenv(var)


def test_hero_dismiss_confirmation(check):
    g, s = _match()
    hero = force_place(g, T.SUNNY_JOE, buildable_near(g, Vec(700, 250), 150))
    gpt = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150))
    _click_world(s, hero.get_position())
    s.frame(0.02)
    check(s.get_selected_tower() is hero, "hero selected by clicking it")
    cash = g.get_cash()
    _press(s, KeyEvent.VK_S)
    check(s.get_pending_dismiss() is hero and hero.is_alive() and g.get_cash() == cash, "S on a hero asks first")
    check(_overlay_button(s, "DISMISS") is not None and _overlay_button(s, "KEEP") is not None, "DISMISS / KEEP buttons")
    check(any("cannot be deployed again this match" in t for t in _texts(s.overlay)), "explains the hero is used up")
    _press(s, KeyEvent.VK_U)
    _press(s, KeyEvent.VK_S)
    check(hero.get_tier() == 0 and hero.is_alive(), "gameplay keys do nothing behind the confirmation")
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_pending_dismiss() is None and hero.is_alive() and s.get_selected_tower() is hero, "Esc keeps the hero")
    _press(s, KeyEvent.VK_S)
    _click(s, _overlay_button(s, "KEEP"))
    check(s.get_pending_dismiss() is None and hero.is_alive(), "KEEP keeps the hero")
    s.frame(0.02)
    side_btn = [b for b in s.get_side_panel().info_buttons if b.get_text().startswith("DISMISS")]
    check(len(side_btn) == 1, "side panel shows a DISMISS button")
    _click(s, side_btn[0])
    check(s.get_pending_dismiss() is hero and hero.is_alive(), "the side panel's DISMISS asks too")
    _click_world(s, gpt.get_position())
    check(s.get_selected_tower() is hero, "map clicks are blocked behind the confirmation")
    _click(s, _overlay_button(s, "DISMISS"))
    check(not hero.is_alive() and g.get_cash() > cash and s.get_selected_tower() is None, "DISMISS sells the hero")
    check(g.get_tower_manager().hero_problem(T.SUNNY_JOE) is not None, "and it cannot be redeployed this match")
    check(s.get_pending_dismiss() is None and len(s.overlay_buttons) == 0, "the confirmation is gone")
    hero2 = force_place(g, T.NIK_SCOPE, buildable_near(g, Vec(560, 480), 150))
    s.select_tower(hero2)
    _press(s, KeyEvent.VK_S)
    _press(s, KeyEvent.VK_ENTER)
    check(not hero2.is_alive(), "Enter confirms DISMISS")
    hero3 = force_place(g, T.LOBBER_LUIS, buildable_near(g, Vec(820, 660), 150))
    s.select_tower(hero3)
    _press(s, KeyEvent.VK_S)
    g.get_tower_manager().sell(hero3)      # the hero disappears some other way while the dialog is up
    s.frame(0.02)
    check(s.get_pending_dismiss() is None and len(s.overlay_buttons) == 0, "the confirmation closes if the hero is gone")
    s.select_tower(gpt)
    _press(s, KeyEvent.VK_S)
    check(not gpt.is_alive() and s.get_pending_dismiss() is None, "ordinary towers still sell at once")


# ---------------------------------------------------------------- 2. keys behind overlays
def _state(g, s, t):
    return (t.get_tier(), t.is_alive(), t.get_targeting(), g.get_cash(), g.get_wave(), g.get_speed(),
            g.get_wave_manager().is_auto_start(), s.get_side_panel().is_all_mode(), s.get_placing(),
            s.get_selected_tower(), len(g.get_tower_manager().get_towers()))


GAMEPLAY_KEYS = [(KeyEvent.VK_U, False), (KeyEvent.VK_S, False), (KeyEvent.VK_A, False), (KeyEvent.VK_T, False),
                 (KeyEvent.VK_T, True), (KeyEvent.VK_SPACE, False), (KeyEvent.VK_2, False), (KeyEvent.VK_3, False),
                 (KeyEvent.VK_B, False), (KeyEvent.VK_TAB, False), (KeyEvent.VK_TAB, True), (KeyEvent.VK_O, False),
                 (KeyEvent.VK_1, True), (KeyEvent.VK_4, True)]


def test_gameplay_keys_blocked_behind_overlays(check):
    def setup():
        g, s = _match()
        t = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 3)
        g.unlock_ability(t)
        force_place(g, T.CLAUDE, buildable_near(g, Vec(800, 600), 150))
        s.select_tower(t)
        s.frame(0.02)
        return g, s, t

    def esc_menu(s, t):
        _press(s, KeyEvent.VK_ESCAPE)      # deselects
        _press(s, KeyEvent.VK_ESCAPE)      # opens the menu
        s.select_tower(t)                  # a tower selected behind the menu must still be safe
        return t

    def dismiss(s, t):
        hero = force_place(s.get_game(), T.SUNNY_JOE, buildable_near(s.get_game(), Vec(700, 250), 150))
        s.select_tower(hero)
        _press(s, KeyEvent.VK_S)
        return hero

    openers = {
        "pause menu (Esc)": esc_menu,
        "pause menu (MENU button)": lambda s, t: _click(s, s.hud.menu_btn),
        "help": lambda s, t: _press(s, KeyEvent.VK_H),
        "hero store": lambda s, t: _press(s, KeyEvent.VK_K),
        "restart confirmation": lambda s, t: s.open_menu() or s.set_confirm(GameScreen.Confirm.RESTART),
        "help over the tactical pause": lambda s, t: _press(s, KeyEvent.VK_P) or _press(s, KeyEvent.VK_H),
        "dismiss confirmation": dismiss,
    }
    for name, open_ in openers.items():
        g, s, t = setup()
        t = open_(s, t) or t
        s.frame(0.02)
        check(s.get_selected_tower() is t, "%s: a tower is selected behind it" % name)
        check(s.gameplay_keys_blocked(), "%s: overlay counts as covering the map" % name)
        sel = s.get_selected_tower()
        before = _state(g, s, t)
        cooldown = t.get_ability_cooldown_remaining()
        for k, shift in GAMEPLAY_KEYS:
            _press(s, k, shift)
        check(_state(g, s, t) == before, "%s: U/S/A/T/Space/1-3/B/Tab/O/Shift+N did nothing (%s -> %s)"
              % (name, before, _state(g, s, t)))
        check(t.get_ability_cooldown_remaining() == cooldown and s.get_targeting_tower() is None, "%s: A did not fire" % name)
        check(s.get_selected_tower() is sel, "%s: selection unchanged" % name)

    # Esc / P / H / K keep working with the overlays up
    g, s, t = setup()
    s.open_menu()
    _press(s, KeyEvent.VK_H)
    check(s.help_shown, "H opens help over the pause menu")
    _press(s, KeyEvent.VK_ESCAPE)
    check(not s.help_shown and s.is_menu_open(), "Esc closes help back to the menu")
    _press(s, KeyEvent.VK_P)
    check(not s.is_menu_open() and not g.is_paused(), "P resumes from the pause menu")
    _press(s, KeyEvent.VK_K)
    check(s.is_hero_store_open(), "K opens the Hero Store")
    _press(s, KeyEvent.VK_P)
    check(s.is_hero_store_open() and s.is_tactically_paused(), "P pauses under the Hero Store")
    _press(s, KeyEvent.VK_K)
    check(not s.is_hero_store_open() and s.is_tactically_paused(), "K closes the Hero Store, still paused")
    _press(s, KeyEvent.VK_P)

    # the end screen
    g, s, t = setup()
    g.lose_lives(Game.START_LIVES, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(400):
        if g.get_state() is not State.PLAYING:
            break
        s.frame(Game.DT)
    s.frame(0.02)
    before = _state(g, s, t)
    for k, shift in GAMEPLAY_KEYS:
        _press(s, k, shift)
    check(g.get_state() is State.DEFEAT and _state(g, s, t) == before, "gameplay keys do nothing on the end screen")

    # the patch-notes draft: digits (shifted or not) pick a card, nothing else acts
    g = new_game(0, 7)
    g.get_variance().enable()
    g.add_cash(5000, None)
    s = GameScreen(_App(), g)
    s.frame(0.02)
    check(s.is_draft_open(), "launch draft open")
    offer = list(g.get_variance().get_offer())
    for k, shift in [(KeyEvent.VK_SPACE, False), (KeyEvent.VK_O, False), (KeyEvent.VK_B, False), (KeyEvent.VK_TAB, False)]:
        _press(s, k, shift)
    check(g.get_wave() == 0 and not g.get_wave_manager().is_auto_start() and not s.get_side_panel().is_all_mode(),
          "draft: gameplay keys blocked")
    _press(s, KeyEvent.VK_2, True)
    act = g.get_variance().get_active()
    check(len(act) == 1 and act[0] is offer[1] and s.get_placing() is None, "draft: Shift+2 still ships card 2")

    # reverse mode keeps its own keys, which also wait behind overlays
    g = ReverseMatch.create(0, 42, Difficulty.ON)
    r = g.get_reverse()
    s = GameScreen(_App(), g)
    s.frame(0.02)
    from lindefense.ai.units import AttackUnit
    from lindefense.ui.attack_panel import AttackPanel
    c = AttackPanel.card_center(AttackUnit.PRIMITIVE.ordinal)
    s.mouse_pressed(c[0], c[1], False)
    q = r.get_queued()
    _press(s, KeyEvent.VK_H)
    _press(s, KeyEvent.VK_SPACE)
    check(r.get_queued() == q, "reverse: SPACE waits behind help")
    _press(s, KeyEvent.VK_H)
    _press(s, KeyEvent.VK_P)
    _press(s, KeyEvent.VK_SPACE)
    check(s.is_tactically_paused() and r.get_queued() > q, "reverse: SPACE sends during the tactical pause")
    _press(s, KeyEvent.VK_P)
    _press(s, KeyEvent.VK_SPACE)
    check(not g.is_paused() and r.get_queued() > q + 5, "reverse: SPACE sends while running")


# ---------------------------------------------------------------- 3. auto-pause
def test_auto_pause_on_focus_loss(check, monkeypatch):
    app = _bare_app()
    g, s = _match(app=app)
    app.game_screen = s
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    check(s.is_menu_open() and g.is_paused(), "focus lost: the pause menu opens")
    s.resume_game()
    app._handle(_ev(pygame.WINDOWMINIMIZED))
    check(s.is_menu_open(), "minimised: the pause menu opens")
    s.resume_game()
    app._has_input_focus = lambda: True
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    check(not g.is_paused(), "a focus loss already undone (the window has focus again) is ignored")
    app._has_input_focus = lambda: False
    s.toggle_pause()
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    check(s.is_tactically_paused() and not s.is_menu_open(), "already (tactically) paused: left alone")
    s.toggle_pause()

    # the game moving its own window (Palantir's System Takeover goes through _WindowAdapter.set_bounds)
    class _Win:
        position, size = (100, 100), (1200, 760)
    app.window = _Win()
    _WindowAdapter(app).set_bounds(Rect(140, 120, 860, 540))
    check(app.window.size == (860, 540), "adapter moved the (fake) window")
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    app._check_deferred_focus()
    check(not g.is_paused(), "a focus loss while the game moves its window does not pause")
    app._handle(_ev(pygame.WINDOWFOCUSGAINED))
    app._self_moved_at -= 5
    app._check_deferred_focus()
    check(not g.is_paused(), "focus came back: nothing to do once the move settles")
    _WindowAdapter(app).set_bounds(Rect(150, 130, 860, 540))
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    app._check_deferred_focus()
    check(not g.is_paused(), "deferred while the move is recent")
    app._self_moved_at -= 5
    app._check_deferred_focus()
    check(s.is_menu_open(), "still unfocused after the move settled: pauses")
    s.resume_game()

    for var in AUTOMATION:
        monkeypatch.setenv(var, "1")
        app._handle(_ev(pygame.WINDOWFOCUSLOST))
        app._handle(_ev(pygame.WINDOWMINIMIZED))
        check(not g.is_paused(), "%s runs never auto-pause" % var)
        monkeypatch.delenv(var)

    s.open_menu()
    s.set_confirm(GameScreen.Confirm.QUIT)
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    check(s.get_pending_confirm() == 2, "an open confirmation is left alone")
    s.resume_game()
    g.lose_lives(Game.START_LIVES, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(400):
        if g.get_state() is not State.PLAYING:
            break
        s.frame(Game.DT)
    app._handle(_ev(pygame.WINDOWFOCUSLOST))
    check(g.get_state() is State.DEFEAT and not s.is_menu_open(), "a finished match is not paused")
    app.game_screen = None
    app._handle(_ev(pygame.WINDOWFOCUSLOST))   # menu screens: nothing to pause
    check(app.running, "out of a match nothing happens")


_GRAB_SCRIPT = r"""
import json, time, pygame
from lindefense.app import LindefenseApp, _WindowAdapter
from lindefense.ui.window_grab import WindowGrab

app = LindefenseApp()
app._is_automation = lambda: False          # a hidden window, but act like a player's run
_WindowAdapter.is_showing = lambda self: True   # the grab skips hidden windows; this one is hidden on purpose
app.show_menu()
app.start_game(0)
gs = app.get_game_screen()
g = app.get_game()
app.window_grab = WindowGrab(_WindowAdapter(app))
out = {"start": list(app.window.size), "events": {}, "paused": False, "menu": False, "min": list(app.window.size)}

class Owner:
    alive = True
    def is_alive(self): return self.alive
    def has_leaked(self): return False
owner = Owner()
g.get_window_link().request_grab(owner)

def run(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        for ev in pygame.event.get():
            name = pygame.event.event_name(ev.type)
            out["events"][name] = out["events"].get(name, 0) + 1
            app._handle(ev)
        app._check_deferred_focus()
        app.frame(1 / 60.0)
        out["paused"] = out["paused"] or g.is_paused()
        out["menu"] = out["menu"] or gs.is_menu_open()
        w, h = app.window.size
        out["min"] = [min(out["min"][0], w), min(out["min"][1], h)]
        time.sleep(1 / 120.0)

run(2.0)                                   # the grab: ~1.5 s of animated set_bounds calls
out["grabs"] = app.window_grab.get_grabs()
out["grabbed"] = list(app.window.size)
owner.alive = False                        # Palantir gone: the window is given back
run(2.6)                                   # release animation + the focus grace period
out["after"] = list(app.window.size)
app._self_moved_at -= 10
app._handle(pygame.event.Event(pygame.WINDOWFOCUSLOST))   # control: a real focus loss on this unfocused window
out["control"] = gs.is_menu_open()
print("RESULT " + json.dumps(out))
"""


def test_palantir_window_grab_does_not_auto_pause(check):
    """System Takeover really moves and resizes a (hidden) window through the app's window adapter while the app handles
    every window event it produces; the match must keep running. A real focus loss afterwards still pauses."""
    env = dict(os.environ)
    env.pop("SDL_VIDEODRIVER", None)   # conftest selects the dummy driver; this needs the real one (window stays hidden)
    env.update(LINDEFENSE_HIDDEN="1", LINDEFENSE_NOSOUND="1", SDL_AUDIODRIVER="dummy", LINDEFENSE_VARIANCE="off")
    root = os.path.join(os.path.dirname(__file__), "..")
    with tempfile.TemporaryDirectory() as d:
        env["LINDEFENSE_PREFS_DIR"] = d
        try:
            p = subprocess.run([sys.executable, "-W", "ignore", "-c", _GRAB_SCRIPT], cwd=root, env=env,
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            pytest.fail("window grab probe timed out")
    lines = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not lines:
        if "No available video device" in p.stderr or "video system not initialized" in p.stderr:
            pytest.skip("no video device")
        pytest.fail("probe failed:\n" + p.stdout[-2000:] + p.stderr[-4000:])
    r = json.loads(lines[-1][len("RESULT "):])
    check(r["grabs"] == 1, "Palantir grabbed the window once (%s)" % r["grabs"])
    check(r["min"][0] < r["start"][0] * 0.9 and r["min"][1] < r["start"][1] * 0.9,
          "the window really shrank: %s -> %s" % (r["start"], r["min"]))
    check(r["after"][0] >= r["start"][0] - 2 and r["after"][1] >= r["start"][1] - 2,
          "and was given back: %s" % r["after"])
    check(not r["paused"] and not r["menu"], "the takeover never paused the match (events %s)" % r["events"])
    check(r["control"], "a real focus loss afterwards does pause")


# ---------------------------------------------------------------- 4. tactical pause and Esc
def test_tactical_pause_keeps_the_map_usable(check):
    g, s = _match(cash=5000)
    _click(s, s.hud.pause_btn)
    check(s.is_tactically_paused() and not s.is_menu_open(), "HUD pause button: tactical pause, no menu")
    texts = _texts(s.overlay)
    check("PAUSED" in texts and "Press P to resume" in texts and s.pause_banner is not None, "PAUSED banner shows")
    check(len(s.overlay_buttons) == 0, "the banner has no buttons (map clicks go through)")
    _press(s, KeyEvent.VK_P)
    check(not g.is_paused() and s.pause_banner is None, "P resumes and the banner goes")
    _press(s, KeyEvent.VK_P)
    tick = g.get_tick()
    side = s.get_side_panel()
    card = next(c for c in side.cards if c.cell.type is T.GPT)
    _click(s, card.button)
    check(s.get_placing() is T.GPT, "shop card arms placement while paused")
    p = buildable_near(g, Vec(380, 300), 150)
    cash = g.get_cash()
    _click_world(s, p)
    towers = g.get_tower_manager().get_player_towers()
    check(len(towers) == 1 and g.get_cash() < cash, "placed at once while paused")
    t = towers[0]
    s.mouse_pressed(600, 500, True)
    _click_world(s, t.get_position())
    check(s.get_selected_tower() is t, "selected by clicking it while paused")
    _press(s, KeyEvent.VK_U)
    check(t.get_tier() == 1, "U upgrades while paused")
    tg = t.get_targeting()
    _press(s, KeyEvent.VK_T)
    check(t.get_targeting() is not tg, "T retargets while paused")
    _press(s, KeyEvent.VK_T, True)
    check(t.get_targeting() is tg, "Shift+T steps back")
    _press(s, KeyEvent.VK_SPACE)
    check(g.get_wave() == 1, "Space starts the wave while paused")
    for _ in range(20):
        s.frame(0.05)
    check(g.get_tick() == tick and s.is_tactically_paused(), "nothing stepped meanwhile")
    cash = g.get_cash()
    _press(s, KeyEvent.VK_S)
    check(not t.is_alive() and g.get_cash() > cash, "S sells while paused")

    # Esc: placement -> selection -> menu -> back to the tactical pause
    t2 = force_place(g, T.GPT, buildable_near(g, Vec(800, 600), 150))
    s.select_tower(t2)
    s.begin_placing(T.GPT)
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_placing() is None and not s.is_menu_open(), "Esc cancels the placement first")
    s.select_tower(t2)
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_selected_tower() is None and not s.is_menu_open(), "then deselects")
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.is_menu_open(), "then opens the pause menu")
    check(any(x.startswith("P to resume, Esc stays paused") for x in _texts(s.overlay)), "menu hint explains Esc")
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.is_tactically_paused(), "Esc closes the menu back into the tactical pause")
    _click(s, s.hud.menu_btn)
    _click(s, _overlay_button(s, "RESUME"))
    check(not g.is_paused() and not s.is_menu_open(), "RESUME runs the game")
    _press(s, KeyEvent.VK_P)
    _press(s, KeyEvent.VK_2)
    check(not g.is_paused() and g.get_speed() == 2, "a speed key resumes at that speed (like the HUD buttons)")


def test_esc_cancels_aim_before_anything_else(check):
    g, s = _match()
    t = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 3)
    g.unlock_ability(t)
    s.select_tower(t)
    s.frame(0.02)
    _press(s, KeyEvent.VK_A)
    if s.get_targeting_tower() is None:   # GPT's ability may not need a target: arm one by hand
        s.targeting_tower = t
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_targeting_tower() is None and s.get_selected_tower() is t and not s.is_menu_open(), "Esc drops the aim only")
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.get_selected_tower() is None and not s.is_menu_open(), "then the selection")
    _press(s, KeyEvent.VK_ESCAPE)
    check(s.is_menu_open(), "then the menu")
    _press(s, KeyEvent.VK_ESCAPE)
    check(not s.is_menu_open() and not g.is_paused(), "and Esc closes it (running before: running again)")


def test_paused_actions_are_deterministic(check):
    """Placing, upgrading and retargeting during the tactical pause must give exactly the same match as doing the same
    things between two steps without pausing."""
    def run(g, n):
        for _ in range(n):
            g.step(Game.DT)
            g.get_events().clear()

    a = new_game(0, 99)
    s = GameScreen(_App(), a)
    s.frame(0.0)
    a.start_next_wave()
    run(a, 240)
    _press(s, KeyEvent.VK_P)
    tick = a.get_tick()
    card = next(c for c in s.get_side_panel().cards if c.cell.type is T.GPT)
    _click(s, card.button)
    _click_world(s, buildable_near(a, Vec(380, 300), 150))
    ta = a.get_tower_manager().get_player_towers()[0]
    s.select_tower(ta)
    _press(s, KeyEvent.VK_T)
    for _ in range(10):
        s.frame(0.05)
    check(a.get_tick() == tick, "paused: no steps")
    _press(s, KeyEvent.VK_P)
    run(a, 900)

    b = new_game(0, 99)
    b.start_next_wave()
    run(b, 240)
    tb = b.place_tower(T.GPT, ta.get_position())
    tb.cycle_targeting(1)
    run(b, 900)

    def sig(g):
        em = g.get_enemy_manager()
        return (g.get_tick(), g.get_cash(), g.get_lives(), em.get_total_killed(), em.get_alive_count(),
                [(round(e.get_position().x, 6), round(e.get_position().y, 6), e.get_hp()) for e in em.get_enemies()],
                [(t.get_kills(), t.get_tier(), t.get_targeting()) for t in g.get_tower_manager().get_towers()])
    check(sig(a) == sig(b), "same match either way:\n%s\n%s" % (sig(a), sig(b)))
    check(a.get_enemy_manager().get_total_killed() > 0, "the tower did fight")


# ---------------------------------------------------------------- 5. hotkeys
def test_tab_cycles_through_placed_towers(check):
    g, s = _match()
    _press(s, KeyEvent.VK_TAB)
    check(s.get_selected_tower() is None, "Tab with no towers selects nothing")
    ts = [force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150)),
          force_place(g, T.CLAUDE, buildable_near(g, Vec(800, 600), 150)),
          force_place(g, T.SUNNY_JOE, buildable_near(g, Vec(700, 250), 150))]
    got = []
    for _ in range(4):
        _press(s, KeyEvent.VK_TAB)
        got.append(s.get_selected_tower())
    check(got == [ts[0], ts[1], ts[2], ts[0]], "Tab: placement order, wrapping")
    _press(s, KeyEvent.VK_TAB, True)
    check(s.get_selected_tower() is ts[2], "Shift+Tab goes back (wraps)")
    _press(s, KeyEvent.VK_TAB, True)
    check(s.get_selected_tower() is ts[1], "Shift+Tab again")
    s.select_tower(None)
    _press(s, KeyEvent.VK_TAB, True)
    check(s.get_selected_tower() is ts[2], "Shift+Tab from nothing selects the last tower")
    s.begin_placing(T.GPT)
    _press(s, KeyEvent.VK_TAB)
    check(s.get_placing() is None and s.get_selected_tower() is ts[0], "Tab drops a pending placement and selects")
    g.get_tower_manager().sell(ts[0])
    s.frame(0.02)
    _press(s, KeyEvent.VK_TAB)
    check(s.get_selected_tower() is ts[1], "sold towers drop out of the cycle")


def test_shop_auto_and_targeting_hotkeys(check):
    g, s = _match()
    side = s.get_side_panel()
    cells = ShopLayout.faction_cells(Faction.PRIMARY)
    check([c.cell.type for c in side.cards] == [c.type for c in cells], "hotkey order = the order of the cards shown")
    for i, c in enumerate(cells):
        _press(s, KeyEvent.VK_1 + i, True)
        check(s.get_placing() is c.type, "Shift+%d picks %s (got %s)" % (i + 1, c.type, s.get_placing()))
    s.begin_placing(None)
    _press(s, KeyEvent.VK_1 + len(cells), True)
    check(s.get_placing() is None, "Shift+N past the last card does nothing")
    _press(s, KeyEvent.VK_2)
    check(g.get_speed() == 2 and s.get_placing() is None, "plain 2 is still game speed")
    _press(s, KeyEvent.VK_1)
    _press(s, KeyEvent.VK_B)
    allc = ShopLayout.all_cells()
    check([c.cell.type for c in side.cards] == [c.type for c in allc], "ALL view order matches too")
    _press(s, KeyEvent.VK_9, True)
    check(s.get_placing() is allc[8].type, "Shift+9 in ALL picks the 9th card (%s)" % allc[8].type)
    s.begin_placing(None)
    poor, ps = _match(cash=0)
    poor.spend_cash(poor.get_cash())
    _press(ps, KeyEvent.VK_1, True)
    check(ps.get_placing() is None and "needs" in ps.abilities.hint, "an unaffordable card is refused with a hint")

    check(not g.get_wave_manager().is_auto_start(), "AUTO starts off")
    _press(s, KeyEvent.VK_O)
    check(g.get_wave_manager().is_auto_start() and s.hud.banner_text == "AUTO WAVES ON", "O turns AUTO on (with a toast)")
    _press(s, KeyEvent.VK_O)
    check(not g.get_wave_manager().is_auto_start(), "O turns it off")

    t = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150))
    twin = force_place(g, T.GPT, buildable_near(g, Vec(800, 600), 150))
    start = t.get_targeting()
    s.select_tower(t)
    seen, want = [], []
    for _ in range(3):
        _press(s, KeyEvent.VK_T, True)
        twin.cycle_targeting(-1)
        seen.append(t.get_targeting())
        want.append(twin.get_targeting())
    check(seen == want and seen[0] is not start, "Shift+T cycles backwards (%s)" % seen)
    for _ in range(3):
        _press(s, KeyEvent.VK_T)
    check(t.get_targeting() is start, "T steps forward again to %s" % start)

    rg = ReverseMatch.create(0, 42, Difficulty.ON)
    rs = GameScreen(_App(), rg)
    rs.frame(0.02)
    _press(rs, KeyEvent.VK_1, True)
    _press(rs, KeyEvent.VK_O)
    check(rs.get_placing() is None and not rg.get_wave_manager().is_auto_start(), "reverse mode: no shop / AUTO keys")


def test_help_lists_every_key(check):
    g, s = _match()
    _press(s, KeyEvent.VK_H)
    texts = _texts(s.overlay)
    for k in ("SPACE", "O", "1  2  3", "P", "ESC", "B", "SHIFT 1-9", "TAB", "U", "S", "A", "T", "K", "M", "N", "H"):
        check(k in texts, "in-game help lists %s" % k)
    check("select next tower (Shift: previous)" in texts and "cycle targeting (Shift: backwards)" in texts
          and "cancel / deselect, else pause menu" in texts, "help explains Tab, Shift+T and Esc")
    m = MenuScreen(_App())
    controls = " ".join(" ".join(_texts(m.help)).split())
    for k in ("O: auto waves", "Shift+1-9", "Tab / Shift+Tab", "T / Shift+T", "Esc: cancel / deselect, else pause menu",
              "P: pause (you can still build"):
        check(k in controls, "main menu CONTROLS mentions %r" % k)


def test_deploying_a_hero_ends_its_placement(check):
    """A hero deploys once per match: after it is placed by a click the cursor no longer carries it, while an ordinary
    tower keeps placing as long as it is affordable."""
    from kit import buildable_near, new_game
    from lindefense.sim.vec import Vec
    from lindefense.tower.tower_type import TowerType as T
    from lindefense.ui.game_screen import GameScreen
    g = new_game(0)
    g.add_cash(50_000, None)
    s = GameScreen(None, g)
    s.frame(0.02)
    s.placing = T.GPT
    _click_world(s, buildable_near(g, Vec(400, 300), 160))
    check(s.placing is T.GPT and len(g.get_tower_manager().get_towers()) == 1, "a tower keeps placing while affordable")
    hero = next(h for h in T.heroes() if g.hero_purchase_problem(h) is None) if hasattr(g, "hero_purchase_problem") else T.heroes()[0]
    if hasattr(g, "purchase_hero"):
        g.purchase_hero(hero)
    s.placing = hero
    _click_world(s, buildable_near(g, Vec(700, 600), 160))
    placed = [t for t in g.get_tower_manager().get_towers() if t.get_type() is hero]
    check(len(placed) == 1, "the hero was deployed by the click (%s)" % hero)
    check(s.placing is None and s.selected_tower is placed[0] if placed else False, "hero placement ends and the hero is selected")
