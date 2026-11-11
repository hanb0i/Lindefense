"""The guided tutorial (ui/tutorial_script.py, ui/tutorial_guide.py, wave/tutorial_waves.py): its own seven waves, the
step logic headless, every step's spotlight target and card at 1600x1000 and after resizes, a full run-through by real
inputs on a windowless app, SKIP / RESUME, the one-off contextual tips, the wave / AUTO gating, REDUCED MOTION, and that
nothing is saved or recorded. Normal games keep the campaign's waves (the bit-exact simtrace fingerprint covers the rest).
"""
import pytest

from kit import buildable_near, force_place, hit_for, new_game, spawn_at
from lindefense.combat.hit_spec import DamageType
from lindefense import prefs, savegame
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.jenum import EnumSet
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.misc import HeroCollection
from lindefense.sim.records import Records
from lindefense.sim.run_setup import DailyRecords, RunOptions
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui import intel
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.jawt import KeyEvent
from lindefense.ui.tutorial_guide import TutorialGuide
from lindefense.ui.tutorial_script import CHAPTERS, TutorialScript, create_game, is_tutorial_game
from lindefense.wave import tutorial_waves, waves

DT = Game.DT


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


# ---------------------------------------------------------------- helpers
class FakeUI:
    """The view state TutorialScript reads, without a screen."""

    def __init__(self, game):
        self.game = game
        self.placing = None
        self.selected = None
        self.store = False
        self.hero_store_selection = T.heroes()[0]

    def get_placing(self):
        return self.placing

    def get_selected_tower(self):
        return self.selected

    def is_hero_store_open(self):
        return self.store

    def get_side_panel(self):
        return None

    def is_tactically_paused(self):
        return self.game.is_paused()

    def is_menu_open(self):
        return False

    def begin_placing(self, t):
        self.placing = t


def _run(g, ts, seconds, until=None):
    for _ in range(int(seconds / DT)):
        if until is not None and until():
            return True
        g.step(DT)
        g.get_events().clear()
        ts.update(DT)
    return until is not None and until()


def _app():
    """A LindefenseApp without a window: the real screens, records and autosave on a ScaledLayer root."""
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


def _key(app, code):
    app.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, code, KeyEvent.CHAR_UNDEFINED))


def _click(app, r):
    """A left click at the centre of logical rect r, sent through the window's pixel space (as the real window does)."""
    root = app.root
    px = root.off_x + (r[0] + r[2] / 2.0) * root.get_scale()
    py = root.off_y + (r[1] + r[3] / 2.0) * root.get_scale()
    lx, ly = root.to_logical_x(px), root.to_logical_y(py)
    app.mouse_moved(lx, ly)
    app.mouse_pressed(lx, ly, False)


def _rect(b):
    return (b.get_x(), b.get_y(), b.get_w(), b.get_h())


def _overlap(a, b, pad=0.0):
    return a[0] < b[0] + b[2] + pad and b[0] < a[0] + a[2] + pad and a[1] < b[1] + b[3] + pad and b[1] < a[1] + a[3] + pad


def _inside(r, w=1600, h=1000):
    return r[0] >= -0.5 and r[1] >= -0.5 and r[0] + r[2] <= w + 0.5 and r[1] + r[3] <= h + 0.5


def _button(guide, text):
    return next((b for b in guide.get_buttons() if b.get_text() == text), None)


SIZES = ((1600, 1000), (1280, 720), (2560, 1440), (1000, 1000), (1920, 1080))


def _drive(app, check, resize=False, speed_key=KeyEvent.VK_3, max_frames=60 * 60 * 6):
    """Plays the tutorial to the end with real inputs (clicks on the spotlit widgets, P / SPACE / speed keys), checking
    every step's spotlight and card. With resize the window size changes at every step. Returns the guide."""
    gs = app.get_game_screen()
    g = gs.get_game()
    guide = gs.tutorial
    sc = guide.get_script()
    app.frame(1 / 60.0)
    _key(app, speed_key)
    seen = []
    frames = 0
    while not sc.is_finished() and frames < max_frames:
        step = sc.current()
        if step.key not in seen:
            seen.append(step.key)
            if resize:
                app.px_w, app.px_h = SIZES[len(seen) % len(SIZES)]
            app.frame(1 / 60.0)
            _check_step(app, guide, check, step)
        acted = _act(app, guide, sc, g)
        for _ in range(1 if acted else 4):
            app.frame(1 / 60.0)
            frames += 1
    check(sc.is_finished() and sc.is_completed(), "the run-through reaches the end (stopped at %s)" % sc.current().key)
    order = [s.key for s in sc.steps]
    check([order.index(k) for k in seen] == sorted(order.index(k) for k in seen) and len(seen) >= len(order) - 2,
          "steps visited in order, none skipped but those already done: %s" % seen)
    return guide


def _check_step(app, guide, check, step):
    sc = guide.get_script()
    name = step.key
    check(guide.is_shown(), "%s: the guide is shown" % name)
    card = guide.get_card_rect()
    check(card is not None and _inside(card), "%s: the card is on screen (%s)" % (name, card))
    target = sc.target()
    tr = guide.get_target_rect()
    if target is not None:
        check(tr is not None, "%s: target %s resolves to a widget" % (name, target))
    if tr is not None:
        check(_inside(tr, 1600, 1004), "%s: target %s on screen (%s)" % (name, target, tr))
        check(not _overlap(card, tr, 2), "%s: the card %s never covers its target %s" % (name, card, tr))
        root = app.root
        s, ox, oy = root.get_scale(), root.off_x, root.off_y
        phys = (ox + tr[0] * s, oy + tr[1] * s, tr[2] * s, tr[3] * s)
        check(_inside(phys, root.canvas_w, root.canvas_h + 4 * s),
              "%s: target inside the %dx%d window (%s)" % (name, root.canvas_w, root.canvas_h, phys))
    tip = guide.get_tip_rect()
    if tip is not None:
        check(not _overlap(tip, card) and (tr is None or not _overlap(tip, tr)), "%s: a tip keeps clear of the card and target" % name)
    if step.kind == step.INFO:
        check(_button(guide, "NEXT") is not None, "%s: info cards have NEXT" % name)
    check(_button(guide, "SKIP TUTORIAL") is not None, "%s: SKIP TUTORIAL is always there" % name)


def _act(app, guide, sc, g):
    gs = app.get_game_screen()
    step = sc.current()
    if step.kind == step.INFO:
        b = _button(guide, "NEXT")
        if b is not None:
            _click(app, _rect(b))
            return True
        return False
    if step.kind == step.WATCH:
        return False
    t = sc.target()
    if t is None:
        return False
    if t[0] == "pause":
        _key(app, KeyEvent.VK_P)
        return True
    if t[0] == "start":
        if g.get_wave_manager().can_start_next_wave():
            _key(app, KeyEvent.VK_SPACE)
            return True
        return False
    if t[0] == "upgrade":
        _click(app, _rect(gs.side.upgrade_btn))
        return True
    if t[0] == "targeting":
        _click(app, _rect(next(b for b in gs.side.info_buttons if b.get_text() == ">")))
        return True
    r = guide.resolve(t)
    if r is None:
        return False
    _click(app, r)
    return True


# ---------------------------------------------------------------- the tutorial's own waves
def test_tutorial_waves_and_normal_games(check):
    g = create_game()
    wm = g.get_wave_manager()
    check(is_tutorial_game(g) and wm.wave_count() == 7 == tutorial_waves.COUNT == len(CHAPTERS), "seven waves, one per chapter")
    check(g.get_difficulty() is Difficulty.O1 and not g.get_variance().is_enabled() and g.is_seed_fixed(),
          "O(1), no Patch Notes, a fixed seed")
    check(g.get_hero_collection() is not HeroCollection.persistent(), "an in-memory Hero Store")
    check(waves.count_for(g) == 7 and waves.exists(g, 7) and not waves.exists(g, 8), "waves 1-7 exist, 8 does not")
    check(waves.for_game(g, 7).contains_boss() and not waves.for_game(g, 1).contains_boss(), "wave 7 is the boss wave")
    check(all(gr.route in (tutorial_waves.LANE_A, tutorial_waves.LANE_B) for w in wm.get_wave_list() for gr in w.groups),
          "every group has a fixed lane (no random route picks)")
    check(intel.preview(g).number == 1 and intel.preview(g).total == 8, "the next-wave preview reads the tutorial's waves")
    boss = None
    for n in range(1, 8):
        check(g.start_next_wave(), "wave %d starts" % n)
        for _ in range(int(400 / DT)):
            g.step(DT)
            g.get_events().clear()
            boss = boss or next(iter(g.get_active_bosses()), None)
            if not wm.is_wave_active():
                break
    check(g.get_wave() == 7 and not wm.can_start_next_wave() and intel.preview(g) is None, "no wave 8")
    check(g.get_state() is State.PLAYING, "the last tutorial wave never triggers the campaign victory")
    check(boss is not None and boss.get_max_hp() == pytest.approx(EnemyType.BELLARMINE_COLLEGE_PREP.base_hp * tutorial_waves.BOSS_HP_SCALE),
          "the small boss has %.0f%% of a campaign MOAB's health" % (100 * tutorial_waves.BOSS_HP_SCALE))
    r = Game.fresh_copy(g)
    check(r.get_wave_manager().get_wave_list() is wm.get_wave_list() and r.get_seed() == g.get_seed(),
          "RESTART keeps the tutorial's waves and seed")
    n = new_game(0)
    nwm = n.get_wave_manager()
    check(nwm.get_wave_list() is None and nwm.wave_count() == waves.WAVE_COUNT and waves.count_for(n) == 100,
          "a normal game plays the 100-wave campaign")
    check(all(waves.for_game(n, k) is waves.get(k) for k in (1, 40, 100)) and waves.exists(n, 100) and not waves.exists(n, 101),
          "normal games read the campaign waves exactly as before")
    check(waves.SpawnGroup.hp_scale is None and all(gr.hp_scale is None for w in waves.all_waves() for gr in w.groups),
          "no campaign group scales health")


# ---------------------------------------------------------------- step logic, headless
def test_step_logic_headless(check):
    g = create_game()
    ui = FakeUI(g)
    ts = TutorialScript(g, ui)
    tm = g.get_tower_manager()
    check(ts.current().key == "welcome" and ts.current().kind == "info" and ts.target() == ("chips",), "starts on the welcome card")
    ts.update(DT)
    check(ts.index() == 0 and not ts.allows_wave_start() and not ts.allows_auto(), "info cards wait for NEXT; waves wait")
    ts.next()
    check(ts.current().key == "build" and ts.target() == ("card", T.CLAUDE), "build: CLAUDE in the shop")
    ui.placing = T.CLAUDE
    spot = ts.target()
    check(spot[0] == "spot" and spot[1] is not None and tm.placement_problem(T.CLAUDE, spot[1]) is None,
          "while placing, the target is a free spot by the track")
    check(g.place_tower(T.CLAUDE, spot[1]) is not None, "placed at the suggested spot")
    ts.update(DT)
    check(ts.current().key == "start1" and ui.placing is None, "placing a tower moves on (and drops the placement mode)")
    check(ts.allows_wave_start(), "now START is allowed")
    check(g.start_next_wave(), "wave 1")
    ts.update(DT)
    check(ts.current().key == "watch1", "watch the first wave")
    check(_run(g, ts, 120, lambda: ts.current().key != "watch1"), "the watch card ends with wave 1")
    check(ts.current().key == "select" and ts.target()[0] == "tower", "select: points at the tower")
    claude = tm.get_player_towers()[0]
    ui.selected = claude
    ts.update(DT)
    check(ts.current().key == "upgrade" and ts.target() == ("upgrade",), "upgrade: points at UPGRADE")
    check(g.get_cash() >= claude.get_def().upgrades[0].cost, "the step can always be afforded")
    ui.selected = None
    check(ts.target() == ("tower", claude), "deselected: back to the tower")
    ui.selected = claude
    check(g.upgrade_tower(claude), "upgraded")
    ts.update(DT)
    check(ts.current().key == "targeting" and ts.target() == ("targeting",), "targeting")
    claude.cycle_targeting(1)
    ts.update(DT)
    check(ts.current().key == "start2", "changing targeting moves on")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "preview3" and ts.target() == ("preview",), "the next-wave preview")
    ts.next()
    check(_run(g, ts, 120, lambda: g.get_wave_manager().can_start_next_wave()), "wave 2 ends")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "lead" and intel.lead_blocked(g) and "SHARP VS LEAD" in ts.text(), "Lead: the warning is explained")
    check(any(t.kind == intel.Threat.LEAD for t in intel.threats(g, intel.preview(g))), "and the preview really warns")
    ts.next()
    check(ts.current().key == "lead_fix" and ts.target() == ("card", T.GPT), "build GPT")
    ui.placing = T.CLAUDE
    check(ts.target() == ("card", T.GPT), "placing another Sharp tower does not count: still GPT")
    ui.placing = T.GPT
    p = ts.target()[1]
    g.place_tower(T.GPT, p)
    ts.update(DT)
    check(ts.current().key == "start4" and not intel.lead_blocked(g), "an Energy tower answers Lead")
    check(_run(g, ts, 120, lambda: g.get_wave_manager().can_start_next_wave()), "wave 3 ends")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "camo" and "NO CAMO DETECTION" in ts.text(), "Camo: the warning is explained")
    ts.next()
    check(ts.current().key == "camo_fix" and ts.target() == ("card", T.GROK), "build Grok")
    ui.placing = T.GROK
    g.place_tower(T.GROK, ts.target()[1])
    ts.update(DT)
    check(ts.current().key == "start5" and intel.camo_covered(g), "a detector answers Camo")
    check(_run(g, ts, 120, lambda: g.get_wave_manager().can_start_next_wave()), "wave 4 ends")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "start6" and not g.get_wave_manager().can_start_next_wave() and "still running" in ts.text(),
          "wave 6 waits for wave 5")
    check(_run(g, ts, 120, lambda: g.get_wave_manager().can_start_next_wave()), "wave 5 ends")
    check(ts.allows_wave_start(), "then START 6 is allowed")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "pause" and ts.target() == ("pause",), "pause")
    g.set_paused(True)
    ts.update(DT)
    check(ts.current().key == "pause_build" and not ts.allows_wave_start(), "build while paused")
    ui.placing = T.GPT
    spot = ts.target()[1]
    lane_b = g.get_map().get_routes()[tutorial_waves.LANE_B]
    check(lane_b.distance_to_point(spot) < 120, "the suggested spot is by the LOWER trace")
    g.place_tower(T.GPT, spot)
    ts.update(DT)
    check(ts.current().key == "resume", "resume")
    g.set_paused(False)
    ts.update(DT)
    check(ts.current().key == "heroes" and g.get_cash() >= 1500, "heroes: the Hero Store step is funded")
    ui.store = True
    ts.update(DT)
    check(ts.current().key == "buy_hero" and ts.target() == ("buy",), "buy a hero")
    ui.hero_store_selection = T.MR_LINDEMANN
    ts.update(DT)
    check(g.get_cash() >= 3400, "picking a pricier hero tops the credits up for it")
    check(g.purchase_hero(T.SUNNY_JOE), "bought")
    ts.update(DT)
    check(ts.current().key == "deploy_hero" and ts.target() == ("deploy",), "deploy it")
    ui.store = False
    check(ts.target() == ("heroes",), "store closed: back to HEROES")
    ui.placing = T.SUNNY_JOE
    hs = ts.target()
    check(hs[0] == "spot" and hs[1] is not None, "a spot for the hero")
    g.place_tower(T.SUNNY_JOE, hs[1])
    ui.selected = None
    ts.update(DT)
    check(ts.current().key == "spend" and ts.target()[0] == "tower", "spend: points at the cheapest upgrade")
    t = ts.target()[1]
    ui.selected = t
    check(ts.target() == ("upgrade",), "selected: UPGRADE")
    g.upgrade_tower(t)
    ts.update(DT)
    check(ts.current().key == "boss_preview" and any(th.kind == intel.Threat.BOSS for th in intel.threats(g, intel.preview(g))),
          "the boss is flagged in the preview")
    ts.next()
    check(ts.current().key == "start7", "start the boss wave")
    check(_run(g, ts, 120, lambda: g.get_wave_manager().can_start_next_wave()), "wave 6 ends")
    g.start_next_wave()
    ts.update(DT)
    check(ts.current().key == "boss_wait", "waiting for the boss")
    check(_run(g, ts, 30, lambda: ts.current().key != "boss_wait"), "the boss arrives")
    check(ts.current().key == "dock" and ts.target() == ("dock",) and g.is_paused(), "the boss dock, paused to read")
    ts.next()
    check(ts.current().key == "boss_fight" and not g.is_paused(), "NEXT resumes")
    check(_run(g, ts, 300, lambda: ts.is_finished()), "the boss wave ends the tutorial")
    check(ts.is_completed() and not ts.is_skipped() and ts.allows_wave_start() and ts.allows_auto(), "completed")
    check(ts.target() is None, "nothing to point at any more")


def test_steps_adapt_and_never_get_stuck(check):
    """Goals already met are skipped; selling everything sends the player back to the shop; cash is topped up."""
    g = create_game()
    ui = FakeUI(g)
    ts = TutorialScript(g, ui)
    ts.next()
    g.add_cash(5000, None)
    g.place_tower(T.GPT, buildable_near(g, Vec(380, 300), 150))   # an Energy tower from the start
    g.place_tower(T.GROK, buildable_near(g, Vec(700, 300), 150))   # and a detector
    ts.update(DT)
    check(ts.current().key == "start1", "any tower completes the build step")
    keys = [s.key for s in ts.steps]
    ts.f_index = keys.index("lead")
    ts.enter()
    check("covered" in ts.text(), "Lead: covered when a tower already deals another damage type (%s)" % ts.text())
    ts.next()
    check(ts.current().key == "start4", "the Lead build step is skipped when not needed")
    ts.f_index = keys.index("camo")
    ts.enter()
    check("covered" in ts.text(), "Camo: covered when a tower already sees camo")
    ts.next()
    check(ts.current().key == "start5", "the detector step is skipped when not needed")
    ts.f_index = keys.index("upgrade")
    ts.enter()
    for t in list(g.get_tower_manager().get_player_towers()):
        g.sell_tower(t)
    g.get_tower_manager().update(0)
    ts.update(DT)
    check(ts.target()[0] in ("card", "tab", "expand") and "no towers" in ts.text(), "no towers left: back to the shop (%s)" % (ts.target(),))
    g2 = create_game()
    ts2 = TutorialScript(g2, FakeUI(g2))
    ts2.next()
    g2.spend_cash(g2.get_cash())
    ts2.update(DT)
    check(g2.get_cash() >= 450 and ts2.grant_paid(), "broke on the build step: topped up to a Claude")
    ts3 = TutorialScript(create_game(), None)
    check(ts3.target() == ("chips",) and ts3.selected() is None and not ts3.store_open(), "works without a view")


# ---------------------------------------------------------------- tips
def test_contextual_tips_fire_once(check):
    g = create_game()
    ui = FakeUI(g)
    ts = TutorialScript(g, ui)
    ts.next()
    claude = force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150))
    g.spend_cash(g.get_cash())
    ts.update(DT)
    check(ts.current().key == "start1", "past the build step")
    check(not ts.tips_fired, "no tip yet")
    ui.selected = claude
    ts.update(DT)
    check([t.key for t in ts.tips_fired] == ["selected"], "first tower selected")
    ui.selected = None
    ts.update(DT)
    ui.selected = claude
    ts.update(DT)
    e = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    g.lose_lives(1, e)
    ts.update(DT)
    g.lose_lives(1, e)
    ts.update(DT)
    check([t.key for t in ts.tips_fired].count("leak") == 1, "the first leak, once")
    route = g.get_map().get_routes()[0]
    d = min(range(0, int(route.get_total_length()), 10), key=lambda x: route.position_at(x).dist(claude.get_position()))
    spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, EnumSet([Modifier.CAMO]), 0, d)
    ts.update(DT)
    ts.update(DT)
    check([t.key for t in ts.tips_fired].count("camo") == 1, "a camo enemy slipping past a tower that cannot see it, once")
    g.start_next_wave()
    g.add_cash(3000, None)
    for _ in range(int(14 / DT)):
        ts.update(DT)
    check([t.key for t in ts.tips_fired].count("cash") == 1 and "$" in ts.tips_fired[-1].text, "credits piling up, once")
    boss = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 100)
    ts.update(DT)
    check("boss" not in [t.key for t in ts.tips_fired], "no boss tip before the ability fires")
    hit_for(g, boss, boss.get_max_hp() * 0.6, DamageType.TRUE)
    for _ in range(3):
        g.step(DT)
        ts.update(DT)
    check([t.key for t in ts.tips_fired].count("boss") == 1 and "CREST SHIELD" in ts.tips_fired[-1].text,
          "the first boss ability (%s)" % [t.key for t in ts.tips_fired])
    keys = [t.key for t in ts.tips_fired]
    check(len(keys) == len(set(keys)) == 5, "five tips, each once: %s" % keys)
    q = []
    while True:
        t = ts.pop_tip()
        if t is None:
            break
        q.append(t.key)
    check(q == keys, "the view gets them in order")


def test_selection_tip_is_folded_into_the_selection_steps(check):
    g = create_game()
    ui = FakeUI(g)
    ts = TutorialScript(g, ui)
    keys = [s.key for s in ts.steps]
    t = force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150))
    ts.f_index = keys.index("upgrade")
    ts.enter()
    ui.selected = t
    ts.update(DT)
    check("selected" not in [x.key for x in ts.tips_fired] and "selected" in ts.tips_shown,
          "selecting during the upgrade lesson needs no extra tip")


# ---------------------------------------------------------------- the real app: spotlight, cards, run-through
def test_full_run_through_by_real_inputs(check):
    """Every step at 1600x1000: the spotlight target exists, is on screen and never under the card; then the same run
    with the window resized at every step. Both reach the completion card with the same result (deterministic)."""
    results = []
    for resize in (False, True):
        Records._shared = Records.in_memory()
        app = _app()
        app.start_tutorial()
        guide = _drive(app, check, resize=resize)
        g = app.get_game()
        results.append((round(g.get_time(), 6), g.get_cash(), g.get_lives(), len(g.get_tower_manager().get_player_towers()),
                        [t.key for t in guide.get_script().tips_fired]))
        app.frame(1 / 60.0)
        fr = guide.get_final_rect()
        check(fr is not None and _inside(fr) and guide.get_card_rect() is None, "the completion card replaces the step card")
        labels = [b.get_text() for b in guide.get_buttons()]
        check(labels == ["START CAMPAIGN", "PLAY A MAP", "MAIN MENU"], "the app's campaign is offered first (%s)" % labels)
        from lindefense.sim.campaign import CampaignProgress
        check(CampaignProgress.persistent().boot_camp_done(), "the campaign's BOOT CAMP node is marked done")
        CampaignProgress._shared = None
        check(g.get_state() is State.PLAYING and g.get_lives() > 0, "the match is still on (no campaign victory screen)")
        _click(app, _rect(_button(guide, "MAIN MENU")))
        check(app.get_menu() is not None and app.get_game_screen() is None, "MAIN MENU leaves the tutorial")
        check(Records.persistent().history() == [] and not savegame.slot().exists(), "nothing recorded, nothing saved")
    check(results[0] == results[1], "the tutorial plays the same at any window size: %s vs %s" % (results[0], results[1]))
    check(results[0][2] == Game.START_LIVES, "the guided path loses no lives: %s" % (results[0],))


def test_completion_offers_the_campaign(check):
    calls = []
    app = _app()
    app.show_campaign = lambda: calls.append("campaign")
    app.on_tutorial_complete = lambda: calls.append("done")
    app.start_tutorial()
    gs = app.get_game_screen()
    sc = gs.get_tutorial()
    app.frame(1 / 60.0)
    check(calls == [], "nothing reported while it runs")
    sc.finish(True)
    app.frame(1 / 60.0)
    app.frame(1 / 60.0)
    check(calls == ["done"], "finishing reports to the app once (the campaign's tutorial node)")
    labels = [b.get_text() for b in gs.tutorial.get_buttons()]
    check(labels == ["START CAMPAIGN", "PLAY A MAP", "MAIN MENU"], "with a campaign: START CAMPAIGN first (%s)" % labels)
    _click(app, _rect(_button(gs.tutorial, "START CAMPAIGN")))
    check(calls == ["done", "campaign"], "START CAMPAIGN opens the campaign")
    app2 = _app()
    app2.start_tutorial()
    app2.get_game_screen().get_tutorial().finish(True)
    app2.frame(1 / 60.0)
    _click(app2, _rect(_button(app2.get_game_screen().tutorial, "PLAY A MAP")))
    check(app2.get_map_select() is not None, "PLAY A MAP opens the map select")


def test_skip_and_resume(check):
    app = _app()
    app.start_tutorial()
    gs = app.get_game_screen()
    guide = gs.tutorial
    sc = guide.get_script()
    g = gs.get_game()
    app.frame(1 / 60.0)
    _click(app, _rect(_button(guide, "NEXT")))
    app.frame(1 / 60.0)
    check(sc.current().key == "build", "on the build step")
    _key(app, KeyEvent.VK_SPACE)
    _key(app, KeyEvent.VK_O)
    check(g.get_wave() == 0 and not g.get_wave_manager().is_auto_start(), "SPACE and AUTO wait while a step is pending")
    done = []
    app.on_tutorial_complete = lambda: done.append(1)
    _click(app, _rect(_button(guide, "SKIP TUTORIAL")))
    app.frame(1 / 60.0)
    check(sc.is_finished() and sc.is_skipped() and not sc.is_completed() and not done, "SKIP TUTORIAL ends it (not as completed)")
    labels = [b.get_text() for b in guide.get_buttons()]
    check(labels == ["RESUME TUTORIAL", "START CAMPAIGN", "PLAY A MAP", "MAIN MENU"], "skipped: RESUME TUTORIAL first (%s)" % labels)
    check(guide.get_card_rect() is None and not any(b.is_visible() for b, _, _ in guide.card_buttons),
          "the step card and its buttons are gone")
    _key(app, KeyEvent.VK_SPACE)
    check(g.get_wave() == 1, "after a skip the waves are the player's")
    _click(app, _rect(_button(guide, "RESUME TUTORIAL")))
    app.frame(1 / 60.0)
    check(not sc.is_finished() and sc.current().key == "build" and guide.get_card_rect() is not None,
          "RESUME TUTORIAL returns to the same step")
    sc.skip_all()
    app.frame(1 / 60.0)
    _click(app, _rect(_button(guide, "MAIN MENU")))
    check(app.get_menu() is not None, "MAIN MENU after a skip")


def test_enter_is_next_and_clicks_on_the_card_stay_there(check):
    app = _app()
    app.start_tutorial()
    gs = app.get_game_screen()
    guide = gs.tutorial
    sc = guide.get_script()
    app.frame(1 / 60.0)
    _key(app, KeyEvent.VK_ENTER)
    check(sc.current().key == "build", "Enter = NEXT on an info card")
    _key(app, KeyEvent.VK_ENTER)
    check(sc.current().key == "build", "Enter does not skip an action")
    card = guide.get_card_rect()
    gs.begin_placing(T.CLAUDE)
    gs.game.add_cash(5000, None)
    app.mouse_pressed(card[0] + 30, card[1] + 50, False)
    check(not gs.get_game().get_tower_manager().get_player_towers(), "a click on the card never places a tower under it")


def test_guide_hides_behind_overlays_but_works_in_the_hero_store(check):
    app = _app()
    app.start_tutorial()
    gs = app.get_game_screen()
    guide = gs.tutorial
    app.frame(1 / 60.0)
    check(guide.is_shown(), "shown on the map")
    gs.open_menu()
    app.frame(1 / 60.0)
    check(not guide.is_shown() and guide.get_buttons() == [], "hidden behind the pause menu")
    gs.resume_game()
    gs.toggle_help()
    app.frame(1 / 60.0)
    check(not guide.is_shown(), "hidden behind HELP")
    gs.toggle_help()
    gs.toggle_hero_store()
    app.frame(1 / 60.0)
    check(not guide.is_shown(), "hidden behind the Hero Store outside the hero steps")
    gs.toggle_hero_store()
    sc = guide.get_script()
    sc.f_index = [s.key for s in sc.steps].index("buy_hero")
    sc.enter()
    gs.toggle_hero_store()
    app.frame(1 / 60.0)
    check(guide.is_shown() and sc.target() == ("buy",), "shown over the store on the hero steps")
    card, tr = guide.get_card_rect(), guide.get_target_rect()
    check(tr is not None and card[0] >= 1200 and not _overlap(card, tr), "the card sits beside the store, on the side panel")


def test_reduced_motion_steadies_the_spotlight(check):
    def outline_colours():
        app = _app()
        app.start_tutorial()
        cols = set()
        for _ in range(40):
            app.frame(1 / 30.0)
            cols.add(app.get_game_screen().tutorial.spot.line.get_alpha())
        return cols
    check(len(outline_colours()) > 3, "the spotlight outline breathes")
    DisplaySettings.get().set_reduced_motion(True)
    check(len(outline_colours()) == 1, "REDUCED MOTION: a steady outline")


def test_hud_counts_the_tutorials_waves(check):
    app = _app()
    app.start_tutorial()
    app.frame(1 / 60.0)
    hud = app.get_game_screen().hud
    check(hud.wave_chip.value.get_label() == "0 / 7", "the wave chip counts 7 (%s)" % hud.wave_chip.value.get_label())
    app.start_game(0)
    app.frame(1 / 60.0)
    check(app.get_game_screen().hud.wave_chip.value.get_label() == "0 / 100", "a normal run still counts 100")
    check(app.get_game_screen().get_tutorial() is None, "no tutorial in a normal run")


def test_nothing_saved_or_recorded(check):
    Records._shared = Records.in_memory()
    app = _app()
    app.start_tutorial()
    gs = app.get_game_screen()
    g = gs.get_game()
    g.add_cash(5000, None)
    gs.toggle_hero_store()
    gs.buy_hero(T.SUNNY_JOE)
    check(g.is_hero_unlocked(T.SUNNY_JOE) and not HeroCollection.persistent().is_unlocked(T.SUNNY_JOE),
          "a hero bought in the tutorial is a practice unlock")
    g.start_next_wave()
    for _ in range(120):
        app.frame(1 / 60.0)
    check(not savegame.slot().exists(), "the tutorial is never autosaved")
    gs.open_menu()
    gs.set_confirm(gs.Confirm.RESTART)
    gs.confirm_yes()
    gs2 = app.get_game_screen()
    check(gs2.get_tutorial() is not None and is_tutorial_game(gs2.get_game()) and gs2.get_game().get_wave() == 0,
          "RESTART starts the tutorial again, with its own waves")
    app.show_menu()
    check(Records.persistent().history() == [] and Records.persistent().career()["runs"] == 0, "never recorded")
    check(not savegame.slot().exists(), "never saved")
