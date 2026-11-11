"""SETTINGS > DISPLAY / ACCESSIBILITY: full screen (F11, Cmd+Ctrl+F, the FULLSCREEN chip), the remembered window geometry,
REDUCED MOTION, COLOUR-BLIND SAFE and the FPS counter. Settings go through injectable stores (MemoryStore / a prefs node
in a temporary folder); screens are built and painted offscreen; the full-screen probe runs a hidden window in a
subprocess on the real video driver (SDL only flags a hidden window as full screen: nothing is ever shown)."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile

import pygame
import pytest
import skia

from kit import buildable_near, force_place, new_game, spawn_at
from lindefense.enemy.types import EnemyType
from lindefense import prefs
from lindefense.app import LindefenseApp, _WindowAdapter
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui import display_settings as DS
from lindefense.ui import window_effects
from lindefense.ui.cyber import Cyber
from lindefense.ui.display_settings import DisplaySettings, MemoryStore, WindowMemory, place_on_displays
from lindefense.ui.fps_counter import FpsCounter
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.glow_layer import GlowLayer
from lindefense.ui.graphics_settings import GraphicsSettings
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state
from lindefense.ui.menu_screen import MenuScreen
from lindefense.ui.screen_shake import ScreenShake
from lindefense.ui.sprites.effect import Effect
from lindefense.ui.ui import Ui

ENV = ("LINDEFENSE_SHOW_FPS", "LINDEFENSE_REDUCED_MOTION", "LINDEFENSE_COLOURBLIND")


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    for k in ENV + ("LINDEFENSE_HIDDEN", "LINDEFENSE_DEMO", "LINDEFENSE_SMOKE"):
        monkeypatch.delenv(k, raising=False)
    prefs._nodes.clear()
    old_gs = GraphicsSettings.instance
    gs = GraphicsSettings.in_memory()
    gs.f_quality = GraphicsSettings.Quality.HIGH   # shake / glow / vignette on, so turning them off is visible
    GraphicsSettings.set_instance(gs)
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    window_effects._on = None
    yield
    GraphicsSettings.set_instance(old_gs)
    DisplaySettings.set_instance(None)
    window_effects._on = None
    prefs._nodes.clear()


def _settings(**on):
    s = DisplaySettings.in_memory()
    for k, v in on.items():
        setattr(s, k, v)
    DisplaySettings.set_instance(s)
    return s


class _App:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a: self.calls.append(name)


def _center(b):
    return b.get_x() + b.get_width() / 2, b.get_y() + b.get_height() / 2


def _paint(node, w=1600, h=1000):
    surf = skia.Surface.MakeRasterN32Premul(w, h)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    cv.clear(0xFF05070F)
    node.paint(Graphics2D(cv))
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray()


# ---------------------------------------------------------------- persistence
def test_settings_persist_through_injectable_stores(check, tmp_path, monkeypatch):
    store = MemoryStore()
    s = DisplaySettings(store)
    check(not (s.fullscreen or s.show_fps or s.reduced_motion or s.colour_blind), "everything is off by default")
    s.set_fullscreen(True)
    check(s.toggle_show_fps() and s.toggle_reduced_motion() and s.toggle_colour_blind(), "toggles report the new state")
    check(store.data == {"fullscreen": True, "showFps": True, "reducedMotion": True, "colourBlind": True},
          "one boolean key each in the store (%s)" % store.data)
    t = DisplaySettings(store)
    check(t.fullscreen and t.show_fps and t.reduced_motion and t.colour_blind, "a new instance loads them back")
    t.toggle_colour_blind()
    check(DisplaySettings(store).colour_blind is False and DisplaySettings(store).reduced_motion, "switching one off saves only it")

    # a real prefs node: its own JSON file, and older save folders (no node, junk values) load the defaults
    node = prefs.node(DisplaySettings.PREFS_NODE)
    p = DisplaySettings(node)
    p.set_reduced_motion(True)
    path = tmp_path / "display.json"
    check(path.exists() and json.loads(path.read_text()) == {"reducedMotion": True}, "saved in the new 'display' node")
    prefs._nodes.clear()
    check(DisplaySettings(prefs.node("display")).reduced_motion, "and read back from disk")
    (tmp_path / "display.json").write_text(json.dumps({"reducedMotion": "yes", "showFps": 1, "unknown": [1]}))
    prefs._nodes.clear()
    j = DisplaySettings(prefs.node("display"))
    check(not j.reduced_motion and not j.show_fps, "non-boolean values fall back to the defaults")
    prefs._nodes.clear()
    (tmp_path / "display.json").unlink()
    (tmp_path / "settings.json").write_text(json.dumps({"windowEffects": False}))
    old = DisplaySettings(prefs.node("display"))
    check(not (old.fullscreen or old.show_fps or old.reduced_motion or old.colour_blind),
          "a save folder from before these settings loads with them off")
    check(json.loads((tmp_path / "settings.json").read_text()) == {"windowEffects": False}, "other nodes untouched")

    # env overrides apply for one run without being saved
    monkeypatch.setenv("LINDEFENSE_REDUCED_MOTION", "1")
    monkeypatch.setenv("LINDEFENSE_COLOURBLIND", "off")
    store = MemoryStore({"colourBlind": True})
    e = DisplaySettings(store)
    check(e.reduced_motion and not e.colour_blind and store.data == {"colourBlind": True}, "env overrides are not saved")

    # the shared instance of a headless run never writes the save folder
    monkeypatch.delenv("LINDEFENSE_REDUCED_MOTION")
    DisplaySettings.set_instance(None)
    before = sorted(os.listdir(tmp_path))
    DisplaySettings.get().toggle_show_fps()
    check(isinstance(DisplaySettings.get().store, MemoryStore) and sorted(os.listdir(tmp_path)) == before,
          "headless runs keep the settings in memory")


def test_window_memory_store(check, tmp_path):
    m = WindowMemory.in_memory()
    check(m.load() is None, "nothing saved yet")
    check(m.save(10, 20, 1200, 750, False), "first save writes")
    check(not m.save(10, 20, 1200, 750, False), "an unchanged geometry is not written again")
    check(m.load() == {"x": 10, "y": 20, "w": 1200, "h": 750, "maximized": False}, "round trip (%s)" % m.load())
    m.save(-1700, 40, 1000, 640, True)
    check(m.load()["x"] == -1700 and m.load()["maximized"], "negative coordinates (a display left of the main one)")
    for junk in (None, 5, "x", {"x": 1, "y": 2, "w": 3}, {"x": 1.5, "y": 2, "w": 300, "h": 200},
                 {"x": 1, "y": 2, "w": 0, "h": 200}, {"x": True, "y": 2, "w": 300, "h": 200}):
        check(WindowMemory.in_memory({"geometry": junk}).load() is None, "unusable geometry ignored: %r" % (junk,))
    p = WindowMemory.persistent()
    p.save(5, 6, 900, 600, False)
    check(json.loads((tmp_path / "window.json").read_text())["geometry"]["w"] == 900, "saved in the new 'window' node")


# ---------------------------------------------------------------- window geometry clamping
def test_saved_window_geometry_is_clamped_onto_a_display(check):
    main = (0, 25, 1728, 1080)            # usable area under a 25 pt menu bar
    left = (-1920, 0, 1920, 1050)         # a second monitor left of the main one
    mn = (640, 420)
    check(place_on_displays((100, 120, 1200, 760), [main], mn) == (100, 120, 1200, 760), "a window on screen stays put")
    check(place_on_displays((1000, 600, 1200, 760), [main], mn) == (528, 345, 1200, 760), "pulled back inside the right / bottom edge")
    check(place_on_displays((-50, 0, 1200, 760), [main], mn) == (0, 53, 1200, 760), "left edge, and room for the title bar")
    gone = place_on_displays((3000, 200, 1200, 760), [main], mn)
    check(gone == (264, 25 + 28 + (1080 - 28 - 760) // 2, 1200, 760), "on a disconnected monitor: centred on the main display (%s)" % (gone,))
    check(place_on_displays((-1500, 100, 1200, 760), [main, left], mn) == (-1500, 100, 1200, 760), "still on the second monitor: stays there")
    check(place_on_displays((-1500, 100, 1200, 760), [main], mn)[0] >= 0, "second monitor unplugged: back on the main one")
    big = place_on_displays((0, 0, 4000, 3000), [main], mn)
    check(big == (0, 53, 1728, 1052), "too big for the display: shrunk to it (%s)" % (big,))
    tiny = place_on_displays((50, 50, 1000, 700), [(0, 0, 600, 400)], mn)
    check(tiny == (0, 0, 640, 420), "never below the minimum size (%s)" % (tiny,))
    check(place_on_displays((0, 0, 800, 500), [], mn) is None, "no display known: no placement")
    for rect in ((100, 120, 1200, 760), (5000, -4000, 900, 600), (-30000, 30000, 700, 500), (1700, 1100, 800, 500)):
        for displays in ([main], [main, left], [left, main]):
            x, y, w, h = place_on_displays(rect, displays, mn)
            check(any(d[0] <= x and x + w <= d[0] + d[2] and d[1] <= y and y + h <= d[1] + d[3] for d in displays),
                  "%s on %s lands fully on a display: %s" % (rect, displays, (x, y, w, h)))

    # the app restores through the same clamp
    app = LindefenseApp.__new__(LindefenseApp)
    app.window_memory = WindowMemory.in_memory({"geometry": {"x": 9000, "y": 9000, "w": 1100, "h": 700, "maximized": True}})
    app._display_bounds = lambda usable=True: [main]
    check(app._restored_geometry() == (314, 25 + 28 + (1080 - 28 - 700) // 2, 1100, 700, True),
          "app: a window last seen on a missing monitor comes back on the main display, still maximised (%s)" % (app._restored_geometry(),))
    app.window_memory = WindowMemory.in_memory()
    check(app._restored_geometry() is None, "first launch: default size")


# ---------------------------------------------------------------- reduced motion
def test_reduced_motion_turns_off_shake_bursts_and_flashes(check):
    for rm in (False, True):
        _settings(reduced_motion=rm)
        tag = "reduced motion" if rm else "normal"
        sh = ScreenShake()
        sh.kick(0.6)
        sh.update(0.02)
        moved = abs(sh.offset_x()) + abs(sh.offset_y())
        check((sh.trauma() == 0 and moved == 0) if rm else (sh.trauma() > 0 and moved > 0),
              "%s: screen shake trauma %.2f, offset %.2f" % (tag, sh.trauma(), moved))
        gl = GlowLayer(new_game(0))
        gl.flash(Vec(300, 300), 120, 0xff8800)
        check(gl.flash_count() == (0 if rm else 1), "%s: explosion light flash count %d" % (tag, gl.flash_count()))
        e = Effect(0, 0, 1.0)
        e.ring(0, 0, 5, 50, Cyber.YELLOW, 0, 0.3, True)
        e.ring(0, 0, 5, 50, Cyber.YELLOW, 0, 0.3, False)
        a_disc, a_ring = e.rings[0].c.get_alpha(), e.rings[1].c.get_alpha()
        check(a_ring == 255 and (a_disc < 100 if rm else a_disc == 255), "%s: flash disc alpha %d, plain ring %d" % (tag, a_disc, a_ring))

    # the main menu: the wordmark's letter-by-letter reveal is its only motion, and reduced motion skips it
    for rm in (False, True):
        _settings(reduced_motion=rm)
        m = MenuScreen(_App())
        m.frame(0.016)
        intro = m.intro_done
        shown = sum(1 for i in range(m.main.get_letter_count()) if m.main.letters[i].is_visible())
        for _ in range(int(3 / 0.05)):
            m.frame(0.05)
        done = m.intro_done and all(m.main.letters[i].is_visible() for i in range(m.main.get_letter_count()))
        if rm:
            check(intro and shown == m.main.get_letter_count(), "reduced motion menu: the logo is shown at once (%s, %d letters)" % (intro, shown))
        else:
            check(not intro and shown < m.main.get_letter_count() and done, "normal menu: the letters appear one by one, then all stay")

    # in a match: no HUD toast glitch slices, no screen shake from lost lives, a steady boss alert
    for rm in (False, True):
        _settings(reduced_motion=rm)
        g = new_game(0)
        s = GameScreen(_App(), g)
        s.frame(0.02)
        s.hud.flash_banner("WAVE 1 INCOMING", Cyber.CYAN, 2)
        s.hud.update(0.02)
        check((s.hud.toast.get_y() == 168) is rm, "%s: the toast %s (y %.1f)" % ("reduced" if rm else "normal", "appears in place" if rm else "slides in", s.hud.toast.get_y()))
        g.lose_lives(5, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
        s.frame(0.02)
        check((s.world.shake.trauma() == 0) is rm, "%s: losing lives shakes the screen = %s" % ("reduced" if rm else "normal", s.world.shake.trauma() > 0))

    check(DS.calm(0.13, 1.0) == 1.0 and DS.reduced_motion(), "calm(): the steady value with reduced motion")
    _settings(reduced_motion=False)
    check(DS.calm(0.13, 1.0) == 0.13, "calm(): the live value otherwise")


def _fold(g, h):
    pk = struct.Struct("<d").pack
    h.update(pk(g.get_time()) + pk(float(g.get_cash())) + pk(float(g.get_lives())) + pk(float(g.get_wave())))
    for e in g.get_enemy_manager().get_enemies():
        p = e.get_position()
        h.update(e.get_type().name.encode() + pk(p.x) + pk(p.y) + pk(e.get_hp()) + pk(e.get_distance()))   # ids are global counters
    for t in g.get_tower_manager().get_towers():
        h.update(b"t%d" % t.get_tier() + pk(float(t.get_damage_dealt())) + pk(float(t.get_kills())))
    for q in g.get_combat().get_projectiles():
        h.update(pk(q.get_position().x) + pk(q.get_position().y))


def _ui_run(**on):
    """A match driven through the real GameScreen (world view, effects, HUD) for 12 s of game time at 3x."""
    _settings(**on)
    g = new_game(2, 1234)
    for p in (Vec(380, 300), Vec(700, 420), Vec(520, 600)):
        force_place(g, T.GPT, buildable_near(g, p, 160), 2)
    s = GameScreen(_App(), g)
    g.set_speed(3)
    g.start_next_wave()
    h = hashlib.blake2b(digest_size=16)
    for i in range(240):
        s.frame(1 / 60.0)
        _fold(g, h)
        if i % 40 == 0:
            s.mouse_moved(400 + i, 300)
    for _ in range(25):
        s.victory_fireworks(0.2)   # the one UI effect that draws from the game's RNG
    return h.hexdigest(), [g.get_rng().next() for _ in range(4)], g.get_enemy_manager().get_total_killed()


def test_display_settings_never_change_the_simulation(check):
    base = _ui_run()
    check(base[2] > 0, "the run destroys enemies (explosions, flashes, shake requests): %d" % base[2])
    for on in ({"reduced_motion": True}, {"colour_blind": True}, {"show_fps": True},
               {"reduced_motion": True, "colour_blind": True, "show_fps": True, "fullscreen": True}):
        r = _ui_run(**on)
        check(r[0] == base[0], "%s: identical game state every frame" % on)
        check(r[1] == base[1], "%s: the game's RNG is in the same place (victory fireworks draw the same numbers)" % on)
    _settings(reduced_motion=True)
    g = new_game(0)
    s = GameScreen(_App(), g)
    g.drain_events()
    for _ in range(10):
        s.victory_fireworks(0.2)
    check(len(g.drain_events()) == 0, "reduced motion: no victory firework explosions")


# ---------------------------------------------------------------- colour-blind safe
def test_colour_blind_palette_swaps_the_red_green_cues(check):
    _settings(colour_blind=False)
    check(Cyber.good() is Cyber.GREEN and Cyber.bad() is Cyber.RED and Cyber.cant_afford() is Cyber.RED, "default palette")
    full, empty = Cyber.hp_color(1.0), Cyber.hp_color(0.0)
    check(full.get_rgb() == Cyber.GREEN.get_rgb() and empty.get_rgb() == Cyber.RED.get_rgb(), "HP bars: green to red")
    _settings(colour_blind=True)
    check(Cyber.good() is Cyber.CB_GOOD and Cyber.bad() is Cyber.CB_BAD and Cyber.cant_afford() is Cyber.CB_SHORT, "colour-blind palette")
    full, empty = Cyber.hp_color(1.0), Cyber.hp_color(0.0)
    check(full.get_rgb() == Cyber.CB_GOOD.get_rgb() and empty.get_rgb() == Cyber.CB_BAD.get_rgb(), "HP bars: azure to vermillion")

    g = new_game(0)
    g.spend_cash(g.get_cash() - 100)   # too poor for anything
    s = GameScreen(_App(), g)
    s.frame(0.02)
    side = s.get_side_panel()
    prices = {c.price.get_color().get_rgb() for c in side.cards}
    check(prices == {Cyber.CB_SHORT.get_rgb()}, "unaffordable shop prices are pink, not red")
    check(all(not c.button.is_enabled() for c in side.cards), "and the cards are disabled (a non-colour cue)")
    s.begin_placing(T.GPT)
    s.mouse_moved(*s.world_to_logical(g.get_map().get_routes()[0].position_at(200)))   # on the track: invalid
    s.frame(0.02)
    wv = s.world
    check(wv.ghost_x1.is_visible() and wv.ghost_x1.get_color().get_rgb() == Cyber.CB_BAD.get_rgb(),
          "invalid placement: vermillion ghost with an X")
    check(wv.ghost_plate.is_visible(), "and the problem in words")


# ---------------------------------------------------------------- SETTINGS panel
class _FullscreenApp(_App):
    def __init__(self):
        super().__init__()
        self.full = False

    def toggle_fullscreen(self):
        self.full = not self.full
        DisplaySettings.get().fullscreen = self.full
        self.calls.append("toggle_fullscreen")
        return self.full


def test_settings_panel_rows_work_by_click(check):
    app = _FullscreenApp()
    m = MenuScreen(app)
    m.skip_intro()
    m.toggle_settings()
    m.frame(0.05)
    ds = DisplaySettings.get()
    gs = GraphicsSettings.get()

    chips = [m.quality_chip, m.fps_chip, m.fullscreen_chip, m.fps_counter_chip, m.motion_chip, m.colour_chip, m.window_chip]
    rects = [(c.get_x(), c.get_y(), c.get_width(), c.get_height()) for c in chips]
    panel = (300, 40, 1000, 920)
    for c, r in zip(chips, rects):
        check(panel[0] < r[0] and r[0] + r[2] < panel[0] + panel[2] and panel[1] < r[1] and r[1] + r[3] < panel[1] + panel[3],
              "%s inside the panel %s" % (c.get_text(), r))
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            overlap = a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
            check(not overlap, "%s and %s do not overlap" % (chips[i].get_text(), chips[j].get_text()))

    q0 = gs.quality()
    m.mouse_pressed(*_center(m.quality_chip))
    check(gs.quality() is q0.next() and m.quality_chip.get_text().endswith(gs.quality().label.upper()), "QUALITY cycles")
    f0 = gs.get_max_fps()
    m.mouse_pressed(*_center(m.fps_chip))
    check(gs.get_max_fps() != f0 and m.fps_chip.get_text() == "MAX FPS: %d" % gs.get_max_fps(), "MAX FPS cycles")
    m.mouse_pressed(*_center(m.fullscreen_chip))
    check(app.calls.count("toggle_fullscreen") == 1 and m.fullscreen_chip.get_text() == "FULLSCREEN: ON",
          "FULLSCREEN switches the real window through the app (%s)" % m.fullscreen_chip.get_text())
    for chip, attr, label in ((m.fps_counter_chip, "show_fps", "FPS COUNTER"), (m.motion_chip, "reduced_motion", "REDUCED MOTION"),
                              (m.colour_chip, "colour_blind", "COLOUR-BLIND SAFE")):
        m.mouse_pressed(*_center(chip))
        check(getattr(ds, attr) and chip.get_text() == label + ": ON" and chip.is_selected(), "%s on by click" % label)
        m.mouse_pressed(*_center(chip))
        check(not getattr(ds, attr) and chip.get_text() == label + ": OFF", "%s off again" % label)
    we = window_effects.is_enabled()
    m.mouse_pressed(*_center(m.window_chip))
    check(window_effects.is_enabled() is (not we), "WINDOW EFFECTS toggles")
    m.mouse_pressed(*_center(m.window_chip))

    # F11 (or the system's control) changes full screen while the panel is open: the chip follows
    app.toggle_fullscreen()
    m.frame(0.05)
    check(m.fullscreen_chip.get_text() == "FULLSCREEN: OFF", "the FULLSCREEN chip follows the window")

    # hint lines explain the hovered chip
    default = m.access_hint.get_label()
    m.mouse_moved(*_center(m.motion_chip))
    check(m.access_hint.get_label().startswith("Reduced motion") and m.access_hint.get_label() != default, "hover explains REDUCED MOTION")
    m.mouse_moved(*_center(m.fullscreen_chip))
    check("F11" in m.display_hint.get_label() and m.access_hint.get_label() == default, "hover explains FULLSCREEN")
    m.mouse_moved(10, 10)
    check(m.display_hint.get_label().startswith(gs.quality().label), "away from the chips: the quality preset")

    # every row still fits the layout and paints
    hint_w = max(Ui.label(t, 0, 0, Cyber.body(0, 14), Ui.TEXT).get_width() for _, _, t in m.settings_hint_rows())
    check(hint_w <= 920, "every hint line fits the panel (widest %.0f px)" % hint_w)
    close = next(b for b in m.buttons if b.get_parent() is m.settings and b.text.get_label() == "CLOSE")
    check(close.get_y() > m.f_disable_admin.get_y() + m.f_disable_admin.get_height(), "CLOSE sits below the admin rows")
    px = _paint(m)
    check(px.shape == (1000, 1600, 4) and px[:, :, :3].max() > 0, "the panel paints offscreen")
    m.mouse_pressed(*_center(close))
    check(not m.settings_shown, "CLOSE closes SETTINGS")
    check(ds.store.data.get("showFps") is False and ds.store.data.get("reducedMotion") is False, "chips saved through the store")

    # the CONTROLS text mentions the hotkey
    texts = [m.help.get_element(i).get_label() for i in range(m.help.get_element_count()) if hasattr(m.help.get_element(i), "get_label")]
    check(any("F11" in t for t in texts), "main-menu HELP > CONTROLS mentions F11")


def test_fullscreen_hotkeys_reach_the_app_everywhere(check):
    app = LindefenseApp.__new__(LindefenseApp)
    app.running = True
    app.sdl = app.win_ptr = None
    app.game_screen = app.map_select = None
    app.menu = MenuScreen(app)
    app.window_grab = None
    app._init_match_safety()
    toggled = []
    app.toggle_fullscreen = lambda: toggled.append(1)
    app.menu.skip_intro()
    app.menu.toggle_settings()   # typing the admin code: F11 / Cmd+Ctrl+F must not type into it
    for key, mod in ((pygame.K_F11, 0), (pygame.K_f, pygame.KMOD_LMETA | pygame.KMOD_LCTRL)):
        app._handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode="f" if key == pygame.K_f else ""))
    check(len(toggled) == 2 and app.menu.code_input.length() == 0, "F11 and Cmd+Ctrl+F toggle full screen on the menu")
    app._handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, mod=pygame.KMOD_LMETA, unicode="f"))
    app._handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode="f"))
    check(len(toggled) == 2, "Cmd+F and plain F do not")
    app.menu.toggle_settings()
    g = new_game(0)
    app.game_screen = GameScreen(app, g)
    app.game_screen.frame(0.02)
    app._handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, mod=0, unicode=""))
    check(len(toggled) == 3, "F11 in a match")
    app.game_screen.toggle_help()
    app._handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, mod=0, unicode=""))
    check(len(toggled) == 4, "F11 behind the HELP overlay")
    labels = []
    for i in range(app.game_screen.overlay.get_element_count()):
        e = app.game_screen.overlay.get_element(i)
        if hasattr(e, "get_label"):
            labels.append(e.get_label())
    check("F11" in labels and any("full screen" in l for l in labels), "the in-game HELP lists F11")

    # the window adapter never moves a full-screen window
    class _Win:
        position, size = (100, 100), (1200, 760)
    app.window = _Win()
    app.is_fullscreen = lambda: True
    from lindefense.ui.window_grab import Rect
    ad = _WindowAdapter(app)
    ad.set_bounds(Rect(300, 300, 700, 500))
    check(app.window.size == (1200, 760) and ad.is_maximized_or_full_screen() and ad.is_full_screen(),
          "set_bounds leaves a full-screen window alone")


def test_window_grab_is_blocked_in_full_screen(check):
    from lindefense.ui.window_grab import Rect, WindowGrab

    class Win:
        def __init__(self):
            self.b = Rect(100, 100, 1200, 760)
            self.full = False
            self.sets = 0

        def get_bounds(self):
            return self.b.copy()

        def set_bounds(self, r):
            self.sets += 1
            self.b = r.copy()

        def is_showing(self):
            return True

        def is_maximized_or_full_screen(self):
            return self.full

        def is_full_screen(self):
            return self.full

        def min_size(self):
            return (640, 420)

        def usable_screen(self):
            return Rect(0, 25, 1728, 1080)

    class Owner:
        def is_alive(self):
            return True

        def has_leaked(self):
            return False

    w = Win()
    w.full = True
    grab = WindowGrab(w)
    g = new_game(0)
    g.get_window_link().request_grab(Owner())
    grab.frame(0.1, g)
    check(w.sets == 0 and grab.get_grabs() == 0 and not grab.is_holding(), "full screen: Palantir cannot grab the window")
    check("full screen" in (g.get_banner() or ""), "a banner says why (%s)" % g.get_banner())
    w.full = False
    g.get_window_link().request_grab(Owner())
    grab.frame(0.1, g)
    sets = w.sets
    check(grab.is_holding() and sets > 0, "windowed: the grab starts animating")
    w.full = True    # the player goes full screen mid-animation
    for _ in range(20):
        grab.frame(0.1, g)
    check(w.sets == sets, "no further bounds changes once the window is full screen")


def test_fps_counter(check):
    c = FpsCounter()
    for _ in range(40):
        c.tick(1 / 50.0)
    check(c.text == "50 FPS", "averages real frame times (%s)" % c.text)
    from lindefense.ui.scaled_layer import ScaledLayer
    layer = ScaledLayer()
    layer.fit(800, 600)   # letterboxed: the readout stays in the layout's corner
    surf = skia.Surface.MakeRasterN32Premul(800, 600)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    cv.clear(0xFF000000)
    c.paint(Graphics2D(cv), layer)
    px = surf.makeImageSnapshot().toarray()
    ys, xs = (px[:, :, :3].max(axis=2) > 40).nonzero()
    s = layer.get_scale()
    check(len(xs) > 0 and xs.min() > layer.off_x + (Ui.W - 120) * s and ys.min() > layer.off_y + (Ui.H - 30) * s
          and ys.max() < layer.off_y + Ui.H * s + 1, "drawn small, in the bottom-right corner of the layout")


# ---------------------------------------------------------------- real hidden window
_PROBE = r"""
import ctypes, json, pygame
from lindefense.app import LindefenseApp, _WindowAdapter
from lindefense.ui.display_settings import DisplaySettings, WindowMemory
from lindefense.ui.jawt import Color
from lindefense.ui.window_grab import Rect, WindowGrab

# saved on a monitor that is no longer connected
mem = WindowMemory.in_memory({"geometry": {"x": 60000, "y": -40000, "w": 1000, "h": 640, "maximized": False}})
app = LindefenseApp(window_memory=mem)
sdl = app.sdl
sdl.SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
sdl.SDL_SetWindowPosition.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
out = {"gpu": app.gr is not None, "displays": app._display_bounds(), "pos": list(app.window.position),
       "size": list(app.window.size)}

def red_square(g):
    g.set_color(Color(255, 0, 0))
    g.fill_rect(0, 0, 100, 100)
real_paint = app.root.paint
app.root.paint = red_square
shots = []
if app.gr is not None:
    real_swap = sdl.SDL_GL_SwapWindow
    def swap(win):
        shots.append(app.surface.makeImageSnapshot().toarray())
        return real_swap(win)
    sdl.SDL_GL_SwapWindow = swap

def red_fraction():
    import numpy as np
    shots.clear()
    app.paint()
    if not shots:
        return None
    reg = shots[-1][4:96, 4:96, :3].reshape(-1, 3).astype(int)
    return float((np.abs(reg - (255, 0, 0)).sum(1) < 60).mean())

def pump():
    for ev in pygame.event.get():
        app._handle(ev)

def key(k, mod=0, uni=""):
    app._handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=uni))
    pump()

def flags():
    return sdl.SDL_GetWindowFlags(app.win_ptr)

def centre():
    w, h = app.window.size
    return list(app._logical((w / 2.0, h / 2.0)))

pump()
out["before"] = red_fraction()
key(pygame.K_F11)
out["f11"] = {"full": app.is_fullscreen(), "flag": bool(flags() & 0x1), "hidden": bool(flags() & 0x8),
              "setting": DisplaySettings.get().fullscreen, "red": red_fraction(), "centre": centre()}

# Palantir's System Takeover while full screen
app.root.paint = real_paint
app.show_menu()
app.start_game(0)
g = app.get_game()
_WindowAdapter.is_showing = lambda self: True
app.window_grab = WindowGrab(_WindowAdapter(app))
class Owner:
    def is_alive(self): return True
    def has_leaked(self): return False
g.get_window_link().request_grab(Owner())
size0, pos0 = list(app.window.size), list(app.window.position)
for _ in range(30):
    app.frame(1 / 30.0)
    pump()
out["grab"] = {"grabs": app.window_grab.get_grabs(), "banner": g.get_banner(), "same": list(app.window.size) == size0
               and list(app.window.position) == pos0}
_WindowAdapter(app).set_bounds(Rect(10, 60, 700, 500))
out["grab"]["set_bounds_refused"] = list(app.window.size) == size0
app.window_grab = None
app.root.paint = red_square

key(pygame.K_f, pygame.KMOD_LMETA | pygame.KMOD_LCTRL, "f")
out["cmdctrlf"] = {"full": app.is_fullscreen(), "flag": bool(flags() & 0x1), "setting": DisplaySettings.get().fullscreen,
                   "red": red_fraction()}

# a wide window, like a 16:10 or 21:9 full screen: drawing and click mapping follow the letterbox
app._self_moved_at -= 10
sdl.SDL_SetWindowSize(app.win_ptr, 1400, 600)
pump()
lx, ly = app._logical((app.root.off_x / app.dpr, app.root.off_y / app.dpr))
out["wide"] = {"red": red_fraction(), "centre": centre(), "origin": [lx, ly], "off_x": app.root.off_x}

# a move / resize by the player is remembered (in the injected memory) and saved
sdl.SDL_SetWindowPosition(app.win_ptr, 120, 140)
sdl.SDL_SetWindowSize(app.win_ptr, 900, 600)
pump()
app._flush_geometry(True)
out["saved"] = mem.load()
key(pygame.K_F11)
sdl.SDL_SetWindowSize(app.win_ptr, 1000, 700)   # SDL keeps this for later while full screen
pump()
app._flush_geometry(True)
out["saved_full"] = mem.load()
key(pygame.K_F11)
out["end_full"] = app.is_fullscreen()
print("RESULT " + json.dumps(out))
"""


def test_fullscreen_and_window_memory_in_a_hidden_window(check):
    env = dict(os.environ)
    env.pop("SDL_VIDEODRIVER", None)   # conftest selects the dummy driver; this needs the real one (the window stays hidden)
    env.update(LINDEFENSE_HIDDEN="1", LINDEFENSE_NOSOUND="1", SDL_AUDIODRIVER="dummy", LINDEFENSE_VARIANCE="off")
    root = os.path.join(os.path.dirname(__file__), "..")
    with tempfile.TemporaryDirectory() as d:
        env["LINDEFENSE_PREFS_DIR"] = d
        try:
            p = subprocess.run([sys.executable, "-W", "ignore", "-c", _PROBE], cwd=root, env=env,
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            pytest.fail("full-screen probe timed out")
        saved_files = sorted(os.listdir(d))
    lines = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not lines:
        if "No available video device" in p.stderr or "video system not initialized" in p.stderr:
            pytest.skip("no video device")
        pytest.fail("probe failed:\n" + p.stdout[-2000:] + p.stderr[-4000:])
    r = json.loads(lines[-1][len("RESULT "):])
    dx, dy, dw, dh = r["displays"][0]
    x, y = r["pos"]
    check(r["size"] == [1000, 640] and dx <= x and x + 1000 <= dx + dw and dy <= y and y + 640 <= dy + dh,
          "a window saved on a disconnected monitor opens on the main display: %s at %s on %s" % (r["size"], r["pos"], r["displays"]))
    good = (lambda f: f is not None and f > 0.95) if r["gpu"] else (lambda f: True)
    check(good(r["before"]), "frame drawn before (%s)" % r["before"])
    f = r["f11"]
    check(f["full"] and f["flag"] and f["setting"], "F11: full screen (%s)" % f)
    check(f["hidden"], "the hidden test window stays hidden")
    check(good(f["red"]) and abs(f["centre"][0] - 800) < 1 and abs(f["centre"][1] - 500) < 1,
          "full screen: still drawing, clicks still map (%s)" % f)
    gr = r["grab"]
    check(gr["grabs"] == 0 and gr["same"] and "full screen" in (gr["banner"] or ""),
          "Palantir's grab is blocked in full screen: %s" % gr)
    check(gr["set_bounds_refused"], "the window adapter refuses to move a full-screen window")
    c = r["cmdctrlf"]
    check(not c["full"] and not c["flag"] and not c["setting"] and good(c["red"]), "Cmd+Ctrl+F leaves full screen (%s)" % c)
    w = r["wide"]
    check(good(w["red"]) and w["off_x"] > 1, "a wide window letterboxes and still draws (%s)" % w)
    check(abs(w["centre"][0] - 800) < 1 and abs(w["centre"][1] - 500) < 1 and abs(w["origin"][0]) < 1 and abs(w["origin"][1]) < 1,
          "clicks map through the letterbox: centre %s, layout corner %s" % (w["centre"], w["origin"]))
    check(r["saved"] == {"x": 120, "y": 140, "w": 900, "h": 600, "maximized": False}, "the player's window is remembered (%s)" % r["saved"])
    check(r["saved_full"] == r["saved"], "nothing is remembered while full screen (%s)" % r["saved_full"])
    check(not r["end_full"], "F11 again: windowed")
    check("display.json" not in saved_files and "window.json" not in saved_files,
          "a hidden (automation) run never saves full screen or the window (%s)" % saved_files)


_LAUNCH_PROBE = r"""
import json, pygame
from lindefense import prefs
from lindefense.app import LindefenseApp
LindefenseApp._is_automation = staticmethod(lambda: False)   # behave like a player's run (the window itself stays hidden)
prefs.node("display").put("fullscreen", True)
prefs.node("window").put("geometry", {"x": 200, "y": 150, "w": 1100, "h": 700, "maximized": False})
app = LindefenseApp()
flags = lambda: app.sdl.SDL_GetWindowFlags(app.win_ptr)
out = {"full": app.is_fullscreen(), "flag": bool(flags() & 0x1), "hidden": bool(flags() & 0x8)}
app.toggle_fullscreen()
for ev in pygame.event.get():
    app._handle(ev)
out["after"] = {"full": app.is_fullscreen(), "size": list(app.window.size), "pos": list(app.window.position)}
app._flush_geometry(True)
print("RESULT " + json.dumps(out))
"""


def test_saved_full_screen_and_window_apply_at_launch(check):
    """A player's launch (the automation guard switched off; the window still hidden, so SDL only flags it) restores the
    saved window and re-enters full screen; leaving full screen saves that choice."""
    env = dict(os.environ)
    env.pop("SDL_VIDEODRIVER", None)
    env.update(LINDEFENSE_HIDDEN="1", LINDEFENSE_NOSOUND="1", SDL_AUDIODRIVER="dummy", LINDEFENSE_VARIANCE="off")
    root = os.path.join(os.path.dirname(__file__), "..")
    with tempfile.TemporaryDirectory() as d:
        env["LINDEFENSE_PREFS_DIR"] = d
        try:
            p = subprocess.run([sys.executable, "-W", "ignore", "-c", _LAUNCH_PROBE], cwd=root, env=env,
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            pytest.fail("launch probe timed out")
        files = {f: json.load(open(os.path.join(d, f))) for f in os.listdir(d) if f.endswith(".json")}
    lines = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not lines:
        if "No available video device" in p.stderr or "video system not initialized" in p.stderr:
            pytest.skip("no video device")
        pytest.fail("probe failed:\n" + p.stdout[-2000:] + p.stderr[-4000:])
    r = json.loads(lines[-1][len("RESULT "):])
    check(r["full"] and r["flag"] and r["hidden"], "the saved FULLSCREEN is applied at launch (%s)" % r)
    check(not r["after"]["full"] and r["after"]["size"] == [1100, 700] and r["after"]["pos"] == [200, 150],
          "leaving it returns to the saved window (%s)" % r["after"])
    check(files.get("display.json") == {"fullscreen": False}, "the choice is saved (%s)" % files.get("display.json"))
    check(files.get("window.json", {}).get("geometry") == {"x": 200, "y": 150, "w": 1100, "h": 700, "maximized": False},
          "the window geometry is saved (%s)" % files.get("window.json"))
