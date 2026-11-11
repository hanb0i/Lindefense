"""Flows that cross the final-beta features: the end screen and HELP before CONTINUE - FREEPLAY, REPLAY SEED from the
RECORDS history (rules, Patch Notes, a chosen seed), RESTART / RETRY in the tutorial next to a saved run, the quit
confirmations' save promise, the tactical-pause hint under No Selling, and REDUCED MOTION / COLOUR-BLIND SAFE on the
newer effects (boss abilities, next-wave warnings, the epilogue, upgrade previews). The real screens are driven through a
windowless LindefenseApp; records and the save slot live in pytest's temporary folder."""
import pytest
import skia

from kit import buildable_near, force_place, kill_outright, new_game, run_seconds, spawn_at
from lindefense import prefs, savegame
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim.challenges import Challenge as C
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.records import Records, RunSummary
from lindefense.sim import records as R
from lindefense.sim.run_setup import DailyRecords, DailyRun, RunOptions, RunSetup
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui import boss_fx as BossFx
from lindefense.ui.cyber import Cyber
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.intrusion_fx import IntrusionFx
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state
from lindefense.ui.next_wave_panel import NextWavePanel
from lindefense.ui.victory_epilogue import VictoryEpilogue
from lindefense.wave import waves


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    for k in ("LINDEFENSE_VARIANCE", "LINDEFENSE_REDUCED_MOTION", "LINDEFENSE_COLOURBLIND"):
        monkeypatch.delenv(k, raising=False)
    prefs._nodes.clear()
    Records._shared = None
    RunOptions.set_instance(RunOptions.in_memory())
    DailyRecords.set_instance(DailyRecords.in_memory())
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    yield
    prefs._nodes.clear()
    Records._shared = None
    RunOptions.set_instance(None)
    DailyRecords.set_instance(None)
    DisplaySettings.set_instance(None)


def _app():
    """A LindefenseApp without a window: the real screen, records and autosave methods on a ScaledLayer root."""
    from lindefense.app import LindefenseApp
    from lindefense.ui.scaled_layer import ScaledLayer
    app = LindefenseApp.__new__(LindefenseApp)
    app.root = ScaledLayer()
    app.menu = app.map_select = app.game_screen = None
    app.demo = app.window_grab = app.autosave = None
    app._errors = {}
    app.running = True
    app.px_w, app.px_h = 1600, 1000
    app._settle_heap = lambda: None
    return app


def _key(code, ch=KeyEvent.CHAR_UNDEFINED):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, code, ch)


def _press(target, code):
    target.key_pressed(_key(code))


def _center(b):
    return b.get_x() + b.get_w() / 2, b.get_y() + b.get_h() / 2


def _button(gs, text):
    return next((b for b in gs.overlay_buttons if b.get_text() == text), None)


def _texts(c):
    out = []
    for o in c:
        if hasattr(o, "get_label"):
            out.append(o.get_label())
        if hasattr(o, "get_element_count") and not hasattr(o, "get_label"):
            out.extend(_texts(o))
    return out


def _lose(app, g):
    g.lose_lives(10_000, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(600):
        app.frame(1 / 60.0)
        if g.get_state() is not State.PLAYING:
            break
    app.frame(1 / 60.0)


def _won_game(seed=42):
    g = new_game(0, seed)
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


# ---------------------------------------------------------------- end screen -> freeplay
def test_help_from_the_end_screen_does_not_follow_into_freeplay(check):
    """H on the victory screen (or HELP left open as the match ends) used to arm HELP silently; CONTINUE - FREEPLAY then
    opened the match under the HELP overlay."""
    g = _won_game()
    s = GameScreen(_app(), g)
    s.frame(0.02)
    check(s.is_epilogue_open(), "the epilogue plays first")
    _press(s, KeyEvent.VK_H)
    check(s.is_epilogue_open() and not s.help_shown, "H does nothing over the epilogue")
    _press(s, KeyEvent.VK_ESCAPE)
    _press(s, KeyEvent.VK_H)
    check(not s.help_shown and _button(s, "CONTINUE - FREEPLAY") is not None, "H on the victory screen leaves HELP closed")
    s.mouse_pressed(*_center(_button(s, "CONTINUE - FREEPLAY")), False)
    s.frame(0.02)
    check(g.is_freeplay() and not s.help_shown and _button(s, "CLOSE") is None and len(s.overlay_buttons) == 0,
          "freeplay starts on the open map, not under HELP (%s)" % [b.get_text() for b in s.overlay_buttons])
    # HELP open while the final boss dies (it does not pause the game)
    h = new_game(0, 7)
    wm = h.get_wave_manager()
    for _ in range(waves.WAVE_COUNT - 1):
        wm.start_next_wave()
        wm.end_wave()
    wm.start_next_wave()
    s2 = GameScreen(_app(), h)
    s2.frame(0.02)
    s2.toggle_help()
    check(s2.help_shown, "HELP open during wave 100")
    kill_outright(h, spawn_at(h, EnemyType.PALANTIR, None, 0, 60))
    for _ in range(int((Game.VICTORY_SEQUENCE_TIME + 0.5) / 0.05)):
        s2.frame(0.05)
    check(h.get_state() is State.VICTORY, "won")
    s2.skip_epilogue()
    s2.continue_freeplay()
    check(h.is_freeplay() and not s2.help_shown and len(s2.overlay_buttons) == 0, "freeplay opens without the stale HELP")


# ---------------------------------------------------------------- RECORDS history -> REPLAY SEED
def _history_replay(app, row=0):
    app.show_menu()
    m = app.get_menu()
    m.skip_intro()
    m.toggle_stats()
    st = m.stats
    st.set_tab(st.Tab.HISTORY)
    st.mouse_pressed(*_center(st.replay_buttons[row]))
    return app.get_game()


def test_history_replay_brings_back_the_rules_and_keeps_the_seed(check):
    Records._shared = Records.in_memory()
    app = _app()
    app.start_run(RunSetup(2, Difficulty.ON, 4242, (C.ONE_LIFE, C.FRUGAL), True))
    g = app.get_game()
    g.get_variance().pick(0)
    g.start_next_wave()
    _lose(app, g)
    h = Records.persistent().history()
    check(len(h) == 1 and set(h[0]["tags"]) >= {"one-life", "frugal", "custom-seed"} and h[0]["notes_on"],
          "the run is in the history with its rules (%s)" % h[:1])
    RunOptions.get().set_patch_notes(False)   # switched off in a briefing since: the replay still has the run's notes
    r = _history_replay(app)
    check(r is not None and r.get_seed() == 4242 and r.get_map().get_name() == maps.create(2).get_name()
          and r.get_difficulty() is Difficulty.ON, "same map, mode and seed")
    check(r.get_challenges() == (C.ONE_LIFE, C.FRUGAL) and r.get_lives() == 1 and r.get_price_multiplier() == 1.5,
          "the run's challenge rules come back (%s)" % (r.get_challenges(),))
    check(r.get_variance().is_enabled() and r.get_variance().is_draft_pending(), "Patch Notes as the run had them")
    check(r.is_seed_fixed() and "custom-seed" in r.run_tags, "a replayed seed counts as chosen (%s)" % (r.run_tags,))
    gs = app.get_game_screen()
    gs.open_menu()
    gs.set_confirm(GameScreen.Confirm.RESTART)
    gs.confirm_yes()
    n = app.get_game()
    check(n is not r and n.get_seed() == 4242 and n.get_challenges() == (C.ONE_LIFE, C.FRUGAL),
          "RESTART keeps the replayed seed and rules, like REPLAY SEED on the end screen")

    # a daily run replays as a chosen-seed run with the day's rule, not as that day's daily
    Records._shared = Records.in_memory()
    day = DailyRun("2026-11-09")
    app2 = _app()
    app2.start_run(day.setup())
    d = app2.get_game()
    d.get_variance().pick(0)
    d.start_next_wave()
    _lose(app2, d)
    r2 = _history_replay(app2)
    check(r2.get_seed() == day.seed and r2.get_challenges() == day.challenges and r2.get_daily_date() is None
          and "custom-seed" in r2.run_tags, "a daily row replays its seed and rule (%s)" % (r2.run_tags,))


def test_history_replay_honours_the_variance_switch(check, monkeypatch):
    Records._shared = Records.in_memory()
    Records._shared.record(RunSummary(map_name=maps.create(1).get_name(), map_index=1, difficulty="O1", seed=99,
                                      result=R.DEFEAT, wave=5, waves_cleared=4, notes_on=True, tags=["no-heroes"]))
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    r = _history_replay(_app())
    check(r.get_seed() == 99 and not r.get_variance().is_enabled() and r.get_hero_limit() == 0,
          "LINDEFENSE_VARIANCE=off still turns Patch Notes off; the No Heroes rule comes back")


# ---------------------------------------------------------------- tutorial next to a saved run
def test_tutorial_restart_and_retry_stay_in_the_tutorial(check):
    """RESTART (pause menu) and RETRY / REPLAY SEED (end screen) in the tutorial used to start a plain match: the
    player's saved run was recorded as abandoned and deleted, and the 'tutorial' was then recorded and saved."""
    Records._shared = Records.in_memory()
    app = _app()
    app.start_game(1)
    app.get_game().get_variance().pick(0)
    app.get_game().start_next_wave()
    app.show_menu()
    slot = savegame.slot()
    check(slot.exists() and slot.peek().map_index == 1, "a run is saved")
    app.start_tutorial()
    gs = app.get_game_screen()
    gs.open_menu()
    gs.mouse_pressed(*_center(_button(gs, "RESTART")), False)
    _press(gs, KeyEvent.VK_ENTER)
    gs = app.get_game_screen()
    check(gs.get_tutorial() is not None, "RESTART in the tutorial restarts the tutorial")
    check(slot.exists() and slot.peek().map_index == 1 and Records.persistent().history() == [],
          "the saved run is untouched and nothing is recorded")
    for label in ("RETRY", "REPLAY SEED"):
        g = app.get_game()
        g.start_next_wave()
        _lose(app, g)
        gs = app.get_game_screen()
        check("TRAINING RUN  ·  NOT RECORDED" in _texts(gs.overlay), "the tutorial's end screen says it is not recorded")
        gs.mouse_pressed(*_center(_button(gs, label)), False)
        check(app.get_game_screen().get_tutorial() is not None, "%s in the tutorial starts the tutorial again" % label)
    app.show_menu()
    check(slot.exists() and slot.peek().map_index == 1 and Records.persistent().history() == []
          and app.get_menu().continue_button is not None, "CONTINUE still offers the saved run")


# ---------------------------------------------------------------- the quit confirmations' save promise
def test_quit_confirmations_promise_a_save_only_when_one_is_kept(check):
    from lindefense.app import LindefenseApp
    Records._shared = Records.in_memory()
    app = _app()
    for confirm in (GameScreen.Confirm.QUIT, GameScreen.Confirm.MAIN_MENU, GameScreen.Confirm.CLOSE):
        app.start_game(0)
        gs = app.get_game_screen()
        gs.open_menu()
        gs.set_confirm(confirm)
        texts = _texts(gs.overlay)
        check(not any("saved" in t for t in texts), "%s: an untouched match is not kept, so no save is promised (%s)"
              % (confirm.name, [t for t in texts if "?" in t]))
    gs.close_menu()
    force_place(app.get_game(), T.GPT, buildable_near(app.get_game(), Vec(380, 300), 150))
    gs.open_menu()
    gs.set_confirm(GameScreen.Confirm.MAIN_MENU)
    check(any("Your run is saved" in t for t in _texts(gs.overlay)), "a tower built: the run is kept")
    gs.confirm_yes()
    check(savegame.slot().exists() and app.get_menu().continue_button is not None, "and CONTINUE offers it")


def test_tactical_pause_hint_under_no_selling(check):
    g = RunSetup(0, Difficulty.O1, 5, (C.NO_SELLING,), False).create_game()
    s = GameScreen(_app(), g)
    s.toggle_pause()
    hint = [t for t in _texts(s.overlay) if t.startswith("you can still")]
    check(hint == ["you can still build, upgrade and target"], "No Selling: the pause banner does not offer selling (%s)" % hint)
    p = GameScreen(_app(), new_game(0))
    p.toggle_pause()
    check("you can still build, upgrade, sell and target" in _texts(p.overlay), "a standard run still mentions selling")


# ---------------------------------------------------------------- reduced motion / colour-blind safe on the newer effects
def _rm(on):
    s = DisplaySettings.in_memory()
    s.reduced_motion = on
    DisplaySettings.set_instance(s)


def _paint_boss(fx, b, t):
    fx.time = t
    surf = skia.Surface.MakeRasterN32Premul(260, 260)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    cv.clear(0xFF000000)
    g = Graphics2D(cv)
    p = b.get_position()
    g.translate(130 - p.x, 130 - p.y)
    BossFx.paint(fx, g, b)
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray()


def test_reduced_motion_steadies_boss_ability_effects(check):
    g = new_game(0)
    b = spawn_at(g, EnemyType.LOCKHEED_MARTIN, None, 0, 400)
    ab = b.get_ability()
    fx = IntrusionFx(g)
    for on in (False, True):
        _rm(on)
        ab._burn, ab._timer = 0.0, 0.5     # about to light: the warning flicker
        warn = [_paint_boss(fx, b, t) for t in (0.0, 1 / 12.0)]
        ab._burn = 1.0                     # burning: the flame flickers (the speed streaks repeat every 1/3 s)
        flame = [_paint_boss(fx, b, t) for t in (1.0, 4 / 3.0)]
        same_warn = bool((warn[0] == warn[1]).all())
        same_flame = bool((flame[0] == flame[1]).all())
        check(same_warn is on and same_flame is on, "%s: afterburner warning steady %s, flame steady %s"
              % ("reduced motion" if on else "normal", same_warn, same_flame))
        check(warn[0].std() > 0 and flame[0].std() > 0, "the effects still draw")


def test_reduced_motion_steadies_warnings_and_the_epilogue_prompt(check):
    for on in (False, True):
        _rm(on)
        p = NextWavePanel(1180, 950, 900)
        f = Cyber.Chamfer(0, 0, 40, 20, 4)
        p.warn_frames = [(f, Cyber.RED)]
        seen = set()
        for _ in range(12):
            p.animate(0.07, -100, -100)
            seen.add(f.f_border.get_rgb())
        check((len(seen) == 1) is on, "%s: next-wave warning frames %s" % ("steady" if on else "pulse", len(seen)))
        ep = VictoryEpilogue(0, 60, 1200, 880)
        ep.finish()
        alphas = set()
        for _ in range(12):
            ep.update(0.21)
            alphas.add(ep.prompt.get_color().get_alpha())
        check((len(alphas) == 1) is on, "%s: epilogue prompt alphas %s" % ("steady" if on else "blinks", sorted(alphas)))


def test_colour_blind_upgrade_preview_gains(check):
    from lindefense.ui.side_panel import SidePanel
    for cb in (False, True):
        s = DisplaySettings.in_memory()
        s.colour_blind = cb
        DisplaySettings.set_instance(s)
        g = new_game(0)
        g.add_cash(100_000, None)
        gs = GameScreen(_app(), g)
        t = force_place(g, T.DEEPSEEK, buildable_near(g, Vec(380, 300), 150))   # next upgrade: "+ 3 shots"
        gs.select_tower(t)
        gs.frame(0.02)
        gained = [o for o in gs.side.info if hasattr(o, "get_label") and o.get_label().startswith("+ ")]
        want = Cyber.good()
        rgb = lambda c: (c.get_red(), c.get_green(), c.get_blue())
        check(gained and all(rgb(o.get_color()) == rgb(want) for o in gained),
              "%s: the upgrade's gained effects use the good colour (%s)"
              % ("colour-blind" if cb else "normal", [o.get_label() for o in gained]))


# ---------------------------------------------------------------- HUD toasts and hover cards under overlays
def test_achievement_toast_waits_until_the_map_is_uncovered(check):
    """Full Roster is earned in the Hero Store: its toast used to play behind the store panel, out of sight."""
    from lindefense.sim.misc import HeroCollection
    from lindefense.sim.records import RunSession
    g = new_game(0)
    g.set_hero_collection(HeroCollection.in_memory())
    g.add_cash(10_000_000, None)
    s = GameScreen(_app(), g)
    s.set_run_session(RunSession(Records.in_memory(), g))
    s.frame(0.02)
    s.toggle_hero_store()
    for h in T.heroes():
        s.buy_hero(h)
    shown = []
    for _ in range(120):
        s.frame(0.05)
        if s.hud.toast_shown and s.hud.toast_shown.startswith("ACHIEVEMENT"):
            shown.append(s.hud.toast_shown)
    check(s.is_hero_store_open() and not shown and s.toasts and s.toasts[0].id == "roster",
          "Full Roster waits while the Hero Store is open (shown in %d frames)" % len(shown))
    s.toggle_hero_store()
    for _ in range(4):
        s.frame(0.05)
    check(s.hud.toast_shown == "ACHIEVEMENT: FULL ROSTER" and not s.toasts, "then plays on the open map (%s)" % s.hud.toast_shown)


def test_next_wave_card_stays_shut_behind_overlays(check):
    g = new_game(0)
    s = GameScreen(_app(), g)
    s.frame(0.02)
    nw = s.hud.next_wave
    s.mouse_moved(nw.left + 20, nw.top + 20)
    s.frame(0.02)
    check(nw.is_card_visible(), "hovering the preview opens its card")
    s.open_menu()
    s.frame(0.02)
    check(not nw.is_card_visible(), "not under the pause menu")
    s.close_menu()
    s.toggle_pause()
    s.frame(0.02)
    check(nw.is_card_visible(), "the tactical pause leaves it working")


def test_admin_daily_runs_keep_no_daily_best(check):
    """The end screen says an admin-mode run keeps no records; its daily best must not change either."""
    mem = DailyRecords.in_memory()
    day = DailyRun("2026-11-09")
    for admin in (False, True):
        g = day.setup().create_game(None, (False, admin, admin))
        g._last_completed_wave = 7
        check(mem.note(g) is (not admin) and mem.best("2026-11-09") == (0 if admin else 7),
              "%s daily run: best wave %d" % ("admin" if admin else "plain", mem.best("2026-11-09")))
        mem = DailyRecords.in_memory()


def test_end_screen_tabs_show_their_state_at_once(check):
    """The end panel is rebuilt on every SUMMARY / REPORT switch: the tabs must not flash as plain buttons first."""
    g = new_game(0)
    s = GameScreen(_app(), g)
    g.start_next_wave()
    g.lose_lives(10_000, spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(300):
        s.frame(0.05)
        if g.get_state() is not State.PLAYING:
            break
    s.frame(0.02)
    for page in (1, 0):
        _press(s, KeyEvent.VK_TAB)
        tabs = [_button(s, "SUMMARY"), _button(s, "REPORT")]
        check(s.end_page == page and [b.sel_t for b in tabs] == [float(page == 0), float(page == 1)],
              "page %d: tabs settled at once (%s)" % (page, [b.sel_t for b in tabs]))


def test_scripted_demo_keeps_records_and_saves_to_itself(check, tmp_path):
    """LINDEFENSE_DEMO plays whole campaigns: without this its victories, history rows and achievements went into the
    player's records file, and its menus showed the player's CONTINUE."""
    from lindefense.sim.records import MemoryStorage
    from lindefense.ui.demo_driver import DemoDriver
    old = savegame._default
    try:
        app = _app()
        savegame.slot().save(new_game(0))
        app.show_menu()
        check(app.get_menu().continue_button is not None, "the player's run is offered before the demo starts")
        out = tmp_path / "demo"
        DemoDriver(app, str(out))
        check(isinstance(Records.persistent()._storage, MemoryStorage), "the demo's runs are recorded in memory only")
        check(savegame.slot().path().startswith(str(out)) and not savegame.slot().exists(), "its save slot is in its own folder")
        check(app.get_menu().continue_button is None, "its menus do not offer the player's run")
        check(old.exists(), "the player's save is untouched")
    finally:
        savegame._default = old
