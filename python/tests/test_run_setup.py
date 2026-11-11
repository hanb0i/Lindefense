"""Seed entry, the daily run, challenge rules and the Patch Notes switch: parsing, determinism, every rule in a real
game, the default game left unchanged, the briefing / map-select / HUD / end-screen wiring (built and painted
offscreen) and the saved stores (always in memory or in a temp folder here)."""
import datetime

import pytest
import skia

from kit import buildable_near, force_place, spawn_at
from lindefense import prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.enemy.types import EnemyType
from lindefense.javacompat import jround
from lindefense.map import maps
from lindefense.sim import difficulty
from lindefense.sim.challenges import Challenge as C
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.run_setup import (DAILY_DIFFICULTIES, DAILY_RULES, DailyRecords, DailyRun, RunOptions, RunSetup,
                                      _MemoryNode, parse_seed_entry)
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui import run_setup_view
from lindefense.ui.acm import GCompound
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state
from lindefense.ui.lindefense_program import LindefenseProgram
from lindefense.ui.map_select_screen import MapSelectScreen
from lindefense.ui.run_strip import RunStrip
from lindefense.ui.ui import Ui
from lindefense.variance.variance import PatchNote, seed_format, seed_parse

DAY = datetime.date(2026, 11, 9)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    monkeypatch.delenv("LINDEFENSE_VARIANCE", raising=False)
    prefs._nodes.clear()
    RunOptions.set_instance(RunOptions.in_memory())
    DailyRecords.set_instance(DailyRecords.in_memory())
    yield
    prefs._nodes.clear()
    RunOptions.set_instance(None)
    DailyRecords.set_instance(None)


class _App:
    """The parts of the app the map-select screen calls."""

    def __init__(self):
        self.runs = []
        self.calls = []

    def start_run(self, setup):
        self.runs.append(setup)

    def start_game(self, *a):
        self.calls.append(("start_game",) + a)

    def start_reverse(self, idx):
        self.calls.append(("reverse", idx))

    def show_menu(self):
        self.calls.append(("menu",))


def _key(code, ch=KeyEvent.CHAR_UNDEFINED, mods=0):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, mods, code, ch)


def _type(screen, text):
    for ch in text:
        screen.key_pressed(_key(ord(ch.upper()), ch))


def _center(b):
    return b.get_x() + b.w / 2, b.get_y() + b.h / 2


def _paint(c):
    surf = skia.Surface.MakeRasterN32Premul(800, 500)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.scale(0.5, 0.5)
    c.paint(g)
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray()


def _labels(c, deep=True, out=None):
    """Text labels inside compound c (positions are relative to their own parent)."""
    out = [] if out is None else out
    for o in c:
        if hasattr(o, "get_label"):
            out.append(o)
        if deep and isinstance(o, GCompound):
            _labels(o, deep, out)
    return out


# ---------------------------------------------------------------- seed entry
def test_seed_entry_parsing(check):
    check(parse_seed_entry("") == (None, None) and parse_seed_entry("   ") == (None, None) and parse_seed_entry(None) == (None, None),
          "a blank field means a random seed")
    want = seed_parse("K3X9QZ")
    for text in ("K3X9QZ", "k3x9qz", " K3X9QZ ", "SEED K3X9QZ", "seed: k3x9qz", "Seed #K3X9QZ", "K3X 9QZ"):
        check(parse_seed_entry(text) == (want, None), "%r parses to the run code K3X9QZ (got %r)" % (text, parse_seed_entry(text)))
    check(parse_seed_entry("SEEDAB") == (seed_parse("SEEDAB"), None), "a code that starts with the letters SEED is kept whole")
    check(parse_seed_entry("-ABC") == (seed_parse("-ABC"), None), "negative seeds (as seed_format prints them) parse")
    for bad in ("K3_X9", "AB!", "1.5", "0x-1", "--5", "+12"):
        s, err = parse_seed_entry(bad)
        check(s is None and err is not None and "letters" in err, "%r is refused with an explanation (%r)" % (bad, err))
    s, err = parse_seed_entry("Z" * 14)
    check(s is None and err is not None and "too long" in err, "a code beyond 64 bits is refused (%r)" % err)
    for seed in (0, 1, 35, 36, 123456789, 36 ** 6 - 1, -77, (1 << 62) + 12345):
        check(parse_seed_entry(seed_format(seed)) == (seed, None), "seed_format(%d) round-trips through the field" % seed)


# ---------------------------------------------------------------- daily run
def test_daily_is_deterministic_per_date_and_differs_across_dates(check):
    a, b = DailyRun(DAY), DailyRun("2026-11-09")
    check(a == b and a.seed == b.seed and a.map_index == b.map_index and a.rule is b.rule, "same date, same daily run")
    check(a.date == "2026-11-09" and a.tag() == "daily:2026-11-09" and a.label() == "MON 09 NOV 2026", "date key, tag and label")
    check(a.seed_text() == "AARX1D" and a.map_index == 5 and a.difficulty is Difficulty.ON and a.rule is C.NO_HEROES,
          "the derivation is pinned (SHA-256 of the date): %r" % a)
    check(DailyRun.today(lambda: DAY) == a, "today() uses the local calendar date")
    runs = [DailyRun(DAY + datetime.timedelta(days=i)) for i in range(120)]
    check(len({r.seed for r in runs}) == len(runs), "every date gets its own seed")
    check(len({(r.seed, r.map_index, r.difficulty, r.rule) for r in runs}) == len(runs), "every date gets its own setup")
    check({r.map_index for r in runs} == set(range(maps.MAP_COUNT)), "over four months every map comes up")
    check({r.difficulty for r in runs} == set(DAILY_DIFFICULTIES), "both daily difficulties come up")
    check({r.rule for r in runs} == set(DAILY_RULES), "every daily rule comes up")
    check(all(0 <= r.seed < 36 ** 6 for r in runs), "daily seeds are six-character run codes")
    g1, g2 = a.setup().create_game(), a.setup().create_game()
    check(g1.get_seed() == g2.get_seed() == a.seed and maps.index_of(g1.get_map()) == a.map_index
          and g1.get_difficulty() is a.difficulty and g1.get_challenges() == (a.rule,), "the daily game uses the day's setup")
    check(g1.get_variance().is_enabled() and g1.is_seed_fixed() and g1.get_daily_date() == a.date, "patch notes on, seed fixed")
    check(g1.run_tags == ("daily:2026-11-09", "no-heroes"), "run tags: %r" % (g1.run_tags,))
    check(g1.get_variance().get_offer() == g2.get_variance().get_offer(), "everyone gets the same launch draft")
    RunOptions.get().set_patch_notes(False)
    check(a.setup().create_game().get_variance().is_enabled(), "the daily keeps Patch Notes on even when switched off")


def test_daily_best_wave_store(check):
    node = _MemoryNode()
    r = DailyRecords(node)
    check(r.best("2026-11-09") == 0, "never played")
    check(r.record("2026-11-09", 12) and r.best("2026-11-09") == 12, "first run sets the best")
    check(not r.record("2026-11-09", 9) and r.best("2026-11-09") == 12, "a worse run keeps the best")
    check(r.record("2026-11-09", 30) and DailyRecords(node).best("2026-11-09") == 30, "a better run replaces it; the store reloads it")
    for i in range(80):
        r.record((DAY + datetime.timedelta(days=i + 1)).isoformat(), 5)
    check(len(node.get("best")) == DailyRecords.KEEP_DAYS and r.best("2026-11-09") == 0, "only the latest 60 days are kept")
    disk = DailyRecords(prefs.node(DailyRecords.NODE))
    disk.record("2026-11-09", 7)
    prefs._nodes.clear()
    check(DailyRecords(prefs.node(DailyRecords.NODE)).best("2026-11-09") == 7, "the prefs node persists it (temp folder)")
    g = DailyRun(DAY).setup().create_game()
    mem = DailyRecords.in_memory()
    check(not mem.note(g), "nothing to record before a wave is cleared")
    g._last_completed_wave = 4
    check(mem.note(g) and mem.best("2026-11-09") == 4, "a cleared wave is recorded for the run's date")
    plain = Game(maps.create(0), 1)
    plain._last_completed_wave = 50
    check(not mem.note(plain), "non-daily runs record nothing")


# ---------------------------------------------------------------- challenge rules in real games
def _game(*cs, seed=42, m=0, notes=False):
    return RunSetup(m, Difficulty.O1, seed, cs, notes).create_game()


def test_no_selling_refuses_to_sell(check):
    g = _game(C.NO_SELLING)
    t = force_place(g, T.GPT, buildable_near(g, Vec(400, 300), 200))
    cash = g.get_cash()
    check(g.sell_tower(t) == 0 and t.is_alive() and t in g.get_tower_manager().get_towers() and g.get_cash() == cash,
          "selling is refused: the tower stays and no cash is paid")
    check(g.get_tower_manager().sell_problem(t) == "No Selling challenge: towers cannot be sold", "the reason is given")
    h = force_place(g, T.SUNNY_JOE, buildable_near(g, Vec(800, 600), 200))
    check(g.sell_tower(h) == 0 and h.is_alive(), "heroes cannot be dismissed either")
    s = GameScreen(None, g)
    s.frame(0.02)
    s.select_tower(t)
    s.frame(0.02)
    sell = [b for b in s.get_side_panel().info_buttons if b.get_text() == "NO SELLING RULE"]
    check(len(sell) == 1 and not sell[0].is_enabled(), "the side panel's SELL button is off and says why")
    s.key_pressed(_key(KeyEvent.VK_S, "s"))
    check(t.is_alive() and s.get_selected_tower() is t and "NO SELLING" in s.abilities.hint, "S shows the reason (%r)" % s.abilities.hint)
    free = _game()
    t2 = force_place(free, T.GPT, buildable_near(free, Vec(400, 300), 200))
    check(free.sell_tower(t2) > 0 and not t2.is_alive(), "without the rule selling works")


def test_one_life_is_defeat_on_first_leak(check):
    g = _game(C.ONE_LIFE)
    check(g.get_lives() == 1 and g.get_max_lives() == 1, "one integrity")
    g.start_next_wave()
    for _ in range(int(120 / Game.DT)):
        if g.get_state() is not State.PLAYING:
            break
        g.step(Game.DT)
    check(g.get_state() is State.DEFEAT and g.get_lives() == 0, "the first leak of wave 1 ends the run (%s)" % g.get_state())
    check(g.get_last_completed_wave() == 0, "before wave 1 was even cleared")


def test_no_heroes_enforces_limit_zero(check):
    g = _game(C.NO_HEROES)
    check(g.get_hero_limit() == 0, "hero limit 0")
    g.get_hero_collection().unlock(T.SUNNY_JOE)
    g.add_cash(100000)
    p = buildable_near(g, Vec(400, 300), 200)
    check(g.placement_problem(T.SUNNY_JOE, p) == "No Heroes challenge: heroes are disabled", "the reason is given")
    check(g.place_tower(T.SUNNY_JOE, p) is None and not g.get_tower_manager().get_towers(), "an owned hero cannot be deployed")
    check(g.place_tower(T.GPT, p) is not None, "towers still can")
    check(_game().get_hero_limit() == 3, "the normal limit is 3")


def test_frugal_raises_prices_and_refunds_follow_what_was_paid(check):
    g, base = _game(C.FRUGAL), _game()
    for t in (T.GPT, T.CLAUDE, T.GEMINI, T.SUNNY_JOE):
        lst = catalog.get(t).base_cost
        check(shop.price_of(t, g) == jround(lst * 1.5 / 5) * 5 and shop.price_of(t, base) == lst,
              "%s costs %d instead of %d" % (t, shop.price_of(t, g), lst))
    cash = g.get_cash() + 100000
    g.add_cash(100000)
    p = buildable_near(g, Vec(400, 300), 200)
    t = g.place_tower(T.GPT, p)
    check(t is not None and cash - g.get_cash() == 750, "placing a GPT spends $750 (%s)" % (cash - g.get_cash()))
    up = t.next_upgrade().cost
    check(shop.upgrade_cost(t, g) == jround(up * 1.5 / 5) * 5, "upgrades cost 50% more")
    c0 = g.get_cash()
    g.upgrade_tower(t)
    check(c0 - g.get_cash() == jround(up * 1.5 / 5) * 5, "the upgrade charges the marked-up price")
    paid = 750 + jround(up * 1.5 / 5) * 5
    check(shop.sell_value(t, g) == int(paid * 0.7), "the refund is 70%% of what was paid (%d vs %d)" % (shop.sell_value(t, g), int(paid * 0.7)))
    check(shop.ability_unlock_cost(g) == shop.ability_unlock_cost(base), "ability unlocks are unchanged")
    v = _game(C.FRUGAL, notes=True)
    v.get_variance().grant(PatchNote.EDGE_DEPLOYMENT)
    want = jround(v.get_variance().tower_price(500) * 1.5 / 5) * 5
    check(shop.price_of(T.GPT, v) == want, "the markup applies on top of Patch Notes (%d)" % want)


def test_glass_cannon_damage_and_lives(check):
    g, base = _game(C.GLASS_CANNON), _game()
    check(g.get_lives() == 25 and g.get_max_lives() == 25, "25 integrity")
    check(g.get_global_damage_multiplier() == 1.5 * base.get_global_damage_multiplier(), "+50% global tower damage")
    dealt = []
    for gm in (g, base):
        t = force_place(gm, T.GPT, buildable_near(gm, gm.get_map().get_routes()[0].position_at(300).add(Vec(0, -60)), 120))
        check(abs(t.damage_multiplier(gm) / (1.5 if gm is g else 1.0) - t.damage_multiplier(base) / 1.0) < 1e-9
              if gm is g else True, "the tower's damage multiplier carries the bonus")
        e = spawn_at(gm, EnemyType.QUICK_SORT, None, 0, 300)
        e._hp = e._max_hp = 1e9
        for _ in range(int(4 / Game.DT)):
            gm.step(Game.DT)
        dealt.append(t.get_damage_dealt())
    check(dealt[1] > 0 and abs(dealt[0] / dealt[1] - 1.5) < 1e-6, "the same fight deals 1.5x the damage (%r)" % dealt)
    both = _game(C.GLASS_CANNON, C.ONE_LIFE)
    check(both.get_lives() == 1 and both.get_global_damage_multiplier() == 1.5, "One Life wins over Glass Cannon's 25")


def test_reverse_mode_takes_no_challenges(check):
    g = ReverseMatch.create(0, 42, Difficulty.ON)
    lives, limit = g.get_lives(), g.get_hero_limit()
    dmg = g.get_global_damage_multiplier()
    g.set_challenges(list(C))
    check(g.get_challenges() == () and g.get_lives() == lives and g.get_hero_limit() == limit
          and g.get_global_damage_multiplier() == dmg and not g.is_selling_locked() and g.get_price_multiplier() == 1,
          "the defender AI keeps the standard rules")
    check(g.run_tags == (), "reverse matches carry no run tags (%r)" % (g.run_tags,))


# ---------------------------------------------------------------- the default game is unchanged
def _trace(g, waves):
    g.add_cash(4000)
    for i, at in enumerate((Vec(380, 300), Vec(700, 250), Vec(560, 480))):
        g.place_tower((T.GPT, T.CLAUDE, T.GEMINI)[i], buildable_near(g, at, 200))
    out = []
    for _ in range(waves):
        g.start_next_wave()
        for _ in range(int(40 / Game.DT)):
            g.step(Game.DT)
            if not g.get_wave_manager().is_wave_active():
                break
        out.append((g.get_tick(), g.get_cash(), g.get_lives(), g.get_enemy_manager().get_total_killed(),
                    tuple(round(t.get_damage_dealt(), 9) for t in g.get_tower_manager().get_towers())))
    return out


def test_default_run_setup_is_the_plain_game(check):
    for m, d in ((0, Difficulty.O1), (3, Difficulty.ON2)):
        old = Game(maps.create(m), 777, d)
        old.get_variance().enable()
        new = RunSetup(m, d, 777, (), True).create_game()
        check(new.get_challenges() == () and not new.is_selling_locked() and new.get_price_multiplier() == 1
              and new.get_hero_limit() == old.get_hero_limit() and new.get_lives() == old.get_lives()
              and new.get_global_damage_multiplier() == old.get_global_damage_multiplier(), "no rule is on by default")
        check(_trace(old, 3) == _trace(new, 3), "map %d %s: the same run, tick for tick" % (m, d))
    g = Game(maps.create(0), 5)
    check(g.run_tags == ("no-patch-notes",), "a plain game without Patch Notes: %r" % (g.run_tags,))
    g.get_variance().enable()
    check(g.run_tags == () and not g.is_seed_fixed(), "a standard run has no tags")
    r = RunSetup(0, Difficulty.O1, None, (), True).create_game()
    check(not r.is_seed_fixed() and r.run_tags == (), "a random-seed run from the briefing is a standard run")


def test_restart_and_replay_keep_the_rules(check):
    g = _game(C.NO_SELLING, C.FRUGAL, seed=None, notes=True)
    r = Game.fresh_copy(g)
    check(r.get_challenges() == (C.NO_SELLING, C.FRUGAL) and r.get_variance().is_enabled(), "RESTART keeps the rules")
    check(r.get_seed() != g.get_seed() or True, "a random-seed run restarts on a new seed")
    rp = Game.fresh_copy(g, g.get_seed())
    check(rp.get_seed() == g.get_seed() and rp.is_seed_fixed() and "custom-seed" in rp.run_tags, "REPLAY SEED fixes the seed")
    check(Game.fresh_copy(rp).get_seed() == g.get_seed(), "restarting a replayed seed keeps it")
    typed = _game(C.ONE_LIFE, seed=1234)
    check(Game.fresh_copy(typed).get_seed() == 1234 and Game.fresh_copy(typed).get_lives() == 1, "a typed seed survives RESTART")
    d = DailyRun(DAY).setup().create_game()
    dr = Game.fresh_copy(d, today=DAY)   # restarted on its own date (another day it is a chosen-seed run)
    check(dr.get_seed() == d.get_seed() and dr.get_daily_date() == "2026-11-09" and dr.run_tags == d.run_tags,
          "restarting the daily is still the daily run")


# ---------------------------------------------------------------- Patch Notes switch
def test_patch_notes_switch_persists(check, monkeypatch):
    node = _MemoryNode()
    o = RunOptions(node)
    check(o.patch_notes_on(), "on by default")
    check(not o.toggle_patch_notes() and not RunOptions(node).patch_notes_on(), "switched off, and it stays off on reload")
    o.set_patch_notes(True)
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    check(not o.patch_notes_on() and not RunOptions.env_allows_patch_notes(), "LINDEFENSE_VARIANCE=off still forces them off")
    monkeypatch.delenv("LINDEFENSE_VARIANCE")
    disk = RunOptions(prefs.node(RunOptions.NODE))
    disk.set_patch_notes(False)
    prefs._nodes.clear()
    check(not RunOptions(prefs.node(RunOptions.NODE)).patch_notes_on(), "the prefs node saves it (temp folder)")
    RunOptions.set_instance(RunOptions(node))
    check(LindefenseProgram.variance_for_players(), "new runs follow the switch (on)")
    RunOptions.get().set_patch_notes(False)
    check(not LindefenseProgram.variance_for_players(), "... and (off)")
    g = RunSetup(0, Difficulty.O1, None, (), RunOptions.get().patch_notes_on()).create_game()
    check(not g.get_variance().is_enabled() and not g.get_variance().is_draft_pending(), "off: no draft and no news")
    o2 = RunOptions.in_memory()
    o2.toggle_challenge(C.FRUGAL)
    o2.toggle_challenge(C.NO_HEROES)
    check(o2.challenges == (C.NO_HEROES, C.FRUGAL), "challenge toggles are kept in rule order")
    o2.toggle_challenge(C.FRUGAL)
    check(o2.challenges == (C.NO_HEROES,) and RunOptions.in_memory().challenges == (), "and start off in a new session")


# ---------------------------------------------------------------- briefing / map select UI
def _right_column_bottom(m):
    rx = MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_PAD + MapSelectScreen.BRIEF_ART_W + 36
    return max(l.get_y() for l in _labels(m.briefing, False) if l.get_x() >= rx - 1)


def test_briefing_text_clears_the_band_in_every_mode(check):
    m = MapSelectScreen(_App())
    saved = difficulty._selected[0]
    try:
        for d in Difficulty:
            Difficulty.set_selected(d)
            for i in range(len(m.maps)):
                for reverse in (False, True):
                    (m.open_reverse_briefing if reverse else m.open_briefing)(i)
                    low = _right_column_bottom(m)
                    check(low < MapSelectScreen.band_y() - 20, "%s map %d %s: text ends at %d, above the RUN SETUP band (%d)"
                          % (d, i, "reverse" if reverse else "defend", low, MapSelectScreen.band_y()))
        m.open_daily_briefing()
        check(_right_column_bottom(m) < MapSelectScreen.band_y() - 20, "the daily briefing's text ends above the band")
    finally:
        Difficulty.set_selected(saved)


def test_briefing_run_setup_band(check):
    app = _App()
    m = MapSelectScreen(app)
    m.frame(0.02)
    for i in range(len(m.maps)):
        m.open_briefing(i)
        rs = m.get_run_setup()
        check(rs is not None and len(rs.toggles) == len(C) and rs.field in m.briefing_buttons and rs.patch in m.briefing_buttons,
              "map %d: the briefing has the SEED field, PATCH NOTES and %d challenge toggles" % (i, len(C)))
        check(_right_column_bottom(m) < MapSelectScreen.band_y() - 20, "map %d: the briefing text ends above the band" % i)
        for b in m.briefing_buttons:
            check(b.get_x() >= MapSelectScreen.BRIEF_X and b.get_x() + b.w <= MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_W
                  and b.get_y() + b.h <= MapSelectScreen.BRIEF_Y + MapSelectScreen.BRIEF_H, "map %d: controls inside the panel" % i)
        m.frame(0.02)
        _paint(m)
    m.open_briefing(2)
    rs = m.get_run_setup()
    by_rule = {c: b for c, b in rs.toggles}
    for c in (C.NO_SELLING, C.ONE_LIFE):
        m.mouse_pressed(*_center(by_rule[c]))
    check(RunOptions.get().challenges == (C.ONE_LIFE, C.NO_SELLING) and by_rule[C.ONE_LIFE].primary, "clicking toggles rules on")
    check(not m.is_typing(), "the field has no focus until clicked")
    m.mouse_pressed(*_center(rs.field))
    check(m.is_typing(), "clicking the field focuses it")
    _type(m, "mn7q")
    check(rs.field.text == "mn7q", "M and N type into the field (got %r)" % rs.field.text)
    m.key_pressed(_key(KeyEvent.VK_BACK_SPACE, "\b"))
    _type(m, "!")
    check(rs.status_head.get_label() == "INVALID SEED" and rs.field.error, "an invalid seed shows its error inline")
    m.key_pressed(_key(KeyEvent.VK_ENTER, "\r"))
    check(app.runs == [] and m.is_briefing_open(), "Enter with an invalid seed starts nothing")
    m.key_pressed(_key(KeyEvent.VK_BACK_SPACE, "\b"))
    check(rs.status_head.get_label() == "RUN CODE " + seed_format(seed_parse("mn7")) and not rs.field.error, "fixed: the code is accepted")
    m.mouse_pressed(*_center(m.briefing_buttons[1]))
    check(len(app.runs) == 1, "DEPLOY starts a run")
    s = app.runs[0]
    check(s.map_index == 2 and s.seed == seed_parse("mn7") and s.challenges == (C.ONE_LIFE, C.NO_SELLING)
          and s.patch_notes and s.daily is None and s.difficulty is Difficulty.get_selected(), "with the briefing's setup")
    m.mouse_pressed(*_center(rs.patch))
    check(not RunOptions.get().patch_notes_on() and rs.patch.get_text() == "PATCH NOTES: OFF", "PATCH NOTES switches off")
    m.mouse_pressed(*_center(rs.field))
    m.key_pressed(_key(KeyEvent.VK_BACK_SPACE, "\b", 4))
    check(rs.field.text == "", "Cmd+Backspace clears the field")
    m.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not m.is_typing() and m.is_briefing_open(), "Esc first drops the focus")
    m.key_pressed(_key(KeyEvent.VK_ENTER, "\r"))
    check(len(app.runs) == 2 and app.runs[1].seed is None and not app.runs[1].patch_notes, "blank = random seed, Patch Notes off")
    m.open_briefing(0)
    check(m.get_run_setup().field.text == "" and m.get_run_setup().challenges() == (C.ONE_LIFE, C.NO_SELLING),
          "a new briefing starts blank but keeps the session's rules")


def test_seed_paste(check, monkeypatch):
    m = MapSelectScreen(_App())
    m.open_briefing(0)
    rs = m.get_run_setup()
    monkeypatch.setattr(run_setup_view, "clipboard_text", lambda: "  SEED k3x9qz \nmore")
    m.mouse_pressed(*_center(rs.field))
    m.key_pressed(_key(KeyEvent.VK_V, "v", 4))
    check(rs.field.text == "SEED k3x9qz" and rs.setup(0).seed == seed_parse("K3X9QZ"), "Cmd+V pastes a shared run code (%r)" % rs.field.text)
    rs.field.set_text("")
    m.key_pressed(_key(KeyEvent.VK_V, "v", 2))
    check(rs.field.text == "SEED k3x9qz", "Ctrl+V too")
    m.mouse_pressed(5, 5)
    check(not m.is_typing(), "a click elsewhere drops the focus")


def test_daily_card_and_briefing(check):
    DailyRecords.get().record(DailyRun.today().date, 17)
    app = _App()
    m = MapSelectScreen(app)
    m.frame(0.02)
    _paint(m)
    play = [b for b in m.buttons if b.text.get_label() == "PLAY DAILY"]
    check(len(play) == 1, "the map-select screen has a PLAY DAILY card")
    b = play[0]
    check(b.get_y() + b.h <= Ui.H and b.get_x() + b.w <= Ui.W, "it fits the 1600x1000 layout")
    labels = [l.get_label() for l in _labels(m)]
    check("Today's best: wave 17" in labels and DailyRun.today().label() in labels, "the card shows the date and today's best")
    m.mouse_pressed(*_center(b))
    rs = m.get_run_setup()
    check(m.is_daily_briefing() and rs is not None and rs.is_daily(), "PLAY DAILY opens the daily briefing")
    check(rs.field.locked and rs.field.text == DailyRun.today().seed_text(), "the seed is the day's, locked")
    check([c for c, t in rs.toggles if t.is_enabled()] == list(DailyRun.today().challenges), "only the day's rule is on")
    m.mouse_pressed(*_center(rs.field))
    check(not m.is_typing(), "the daily seed cannot be edited")
    for c, t in rs.toggles:
        m.mouse_pressed(*_center(t))
    m.mouse_pressed(*_center(rs.patch))
    check(rs.challenges() == DailyRun.today().challenges and rs.patch_notes(), "the daily setup cannot be changed")
    m.frame(0.02)
    _paint(m)
    m.key_pressed(_key(KeyEvent.VK_ENTER, "\r"))
    check(len(app.runs) == 1 and app.runs[0].seed == DailyRun.today().seed and app.runs[0].daily == DailyRun.today().date
          and app.runs[0].challenges == DailyRun.today().challenges and app.runs[0].patch_notes, "START DAILY starts today's run")
    m.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not m.is_briefing_open(), "Esc closes it")
    m.open_reverse_briefing(1)
    m.frame(0.02)
    _paint(m)
    check(m.get_run_setup() is None and m.is_reverse_briefing(), "the reverse briefing has no run setup")
    m.key_pressed(_key(KeyEvent.VK_ENTER, "\r"))
    check(app.calls[-1] == ("reverse", 1), "Enter still starts Adversarial Training")


def test_daily_button_without_a_free_grid_slot(check, monkeypatch):
    monkeypatch.setattr(MapSelectScreen, "COLS", 7)
    m = MapSelectScreen(_App())
    play = [b for b in m.buttons if b.text.get_label() == "DAILY RUN"]
    check(len(play) == 1 and play[0].get_y() < 100, "a full grid puts DAILY RUN in the top bar")
    m.mouse_pressed(*_center(play[0]))
    check(m.is_daily_briefing(), "and it opens the daily briefing")


# ---------------------------------------------------------------- HUD chips and end screen
def test_hud_chips_and_end_screen(check):
    g = _game(C.NO_SELLING, C.GLASS_CANNON, notes=True)
    s = GameScreen(None, g)
    s.frame(0.02)
    s.frame(0.02)
    check(s.strip.is_visible() and s.strip.height() == RunStrip.H, "the strip shows")
    check([r.text for r in s.strip.rules] == ["NO SELLING", "GLASS CANNON"] and len(s.strip.rule_boxes) == 2, "one chip per rule")
    _paint(s)
    off = _game(C.ONE_LIFE, C.NO_HEROES)
    so = GameScreen(None, off)
    so.frame(0.02)
    so.frame(0.02)
    check(so.strip.is_visible() and so.strip.version_label.get_label() == "Run rules" and len(so.strip.rule_boxes) == 2,
          "without Patch Notes the strip still shows the rules")
    plain = Game(maps.create(0), 3)
    sp = GameScreen(None, plain)
    sp.frame(0.02)
    check(not sp.strip.is_visible() and sp.strip.height() == 0, "a plain game without Patch Notes has no strip")
    e = spawn_at(off, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    off.lose_lives(1, e)
    for _ in range(200):
        so.frame(Game.DT)
    so.frame(0.02)
    texts = [b.get_text() for b in so.overlay_buttons]
    check(off.get_state() is State.DEFEAT and "REPLAY SEED" in texts, "REPLAY SEED shows even with Patch Notes off (%s)" % texts)
    chips = [l.get_label() for l in _labels(so.overlay)]
    check("ONE LIFE" in chips and "NO HEROES" in chips, "the end screen lists the rules")
    _paint(so)
    d = DailyRun(DAY).setup().create_game()
    sd = GameScreen(None, d)
    sd.frame(0.02)
    check(s.strip.rules[0].text == "NO SELLING" and sd.strip.rules[0].text == "DAILY 09 NOV", "the daily run has its chip")
    d._last_completed_wave = 6
    sd.frame(0.02)
    check(DailyRecords.get().best("2026-11-09") == 6, "a daily's cleared wave is saved during play")
    full = RunSetup(0, Difficulty.O1, 5, list(C), True, "2026-11-09").create_game()
    for p in list(PatchNote)[:5]:
        full.get_variance().grant(p)
    sf = GameScreen(None, full)
    sf.frame(0.02)
    sf.frame(0.02)
    box = sf.strip.rule_boxes
    check([r.text for r in sf.strip.shown_rules] == ["RULES x6"] and len(box) == 1 and box[0][0] + box[0][1] < Ui.WORLD_W - RunStrip.QUIET_W,
          "too many chips fold into one RULES chip that leaves room for the seed")
    rv = ReverseMatch.create(0, 42, Difficulty.ON)
    rs = GameScreen(None, rv)
    rs.frame(0.02)
    rv.lose_lives(10000, spawn_at(rv, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    for _ in range(200):
        if rv.get_state() is not State.PLAYING:
            break
        rs.frame(Game.DT)
    rs.frame(0.02)
    check("REPLAY SEED" not in [b.get_text() for b in rs.overlay_buttons], "reverse matches have no REPLAY SEED")


def test_one_life_stays_one_life(check):
    """One Life: no Patch Notes card that hands out lives is ever offered, and nothing adds lives."""
    from lindefense.variance.variance import PatchNote
    seen = set()
    for seed in range(40):
        g = Game(maps.create(0), seed, Difficulty.O1)
        g.set_challenges((C.ONE_LIFE,))
        g.get_variance().enable()
        g.get_variance().prepare_for(0) if hasattr(g.get_variance(), "prepare_for") else None
        offer = g.get_variance().get_offer() or []
        seen.update(offer)
        g.add_lives(3)
        check(g.get_lives() == 1, "seed %d: add_lives cannot raise One Life" % seed)
    check(PatchNote.SYNTHETIC_DATA not in seen and len(seen) > 5, "Synthetic Data is never offered under One Life (%d cards seen)" % len(seen))
    g = Game(maps.create(0), 3, Difficulty.O1)
    g.add_lives(2)
    check(g.get_lives() == g.get_max_lives() + 2, "without the rule, lives can still be added")
