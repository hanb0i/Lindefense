"""Long-term progression (sim/records.py) and its screens: per-map records and medals, career totals, run history,
achievements, corrupt-file tolerance, exclusion rules, the end-of-run report and RETRY, the RECORDS screen, the map
cards' medals, the remembered difficulty and the catalog's owned / locked heroes. Nothing here writes the real save
folder: records are in memory or in pytest's tmp_path."""
import json
import os

import pytest
import skia

from kit import buildable_near, force_place, kill_outright, new_game, spawn_at, ticks
from lindefense import prefs
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim import records as R
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.misc import HeroCollection
from lindefense.sim.records import FileStorage, Records, RunSession, RunSummary
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state

NAMES = [m.get_name() for m in maps.create_all()]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    monkeypatch.delenv("LINDEFENSE_DIFFICULTY", raising=False)
    monkeypatch.delenv("LINDEFENSE_SEED", raising=False)
    prefs._nodes.clear()
    Records._shared = None
    Difficulty.set_selected(None)
    yield
    prefs._nodes.clear()
    Records._shared = None
    Difficulty.set_selected(None)


def run(**kw):
    base = dict(map_name=NAMES[0], map_index=0, difficulty="O1", seed=12345, result=R.DEFEAT, wave=10, waves_cleared=9,
                kills=500, leaks=3, lives=0, max_lives=100, time=600.0, play_time=300.0, cash_earned=4000)
    base.update(kw)
    return RunSummary(**base)


def win(**kw):
    kw.setdefault("result", R.VICTORY)
    kw.setdefault("wave", 100)
    kw.setdefault("waves_cleared", 100)
    kw.setdefault("lives", 80)
    kw.setdefault("leaks", 5)
    kw.setdefault("time", 4000.0)
    return run(**kw)


def paint(node, w=800, h=500):
    surf = skia.Surface.MakeRasterN32Premul(w, h)
    reset_canvas_state(surf.getCanvas())
    g = Graphics2D(surf.getCanvas())
    g.scale(w / 1600.0, h / 1000.0)
    node.paint(g)
    return surf


def labels(node, out=None):
    """Every text label under a scene-graph node."""
    out = [] if out is None else out
    if hasattr(node, "get_element_count"):
        for i in range(node.get_element_count()):
            labels(node.get_element(i), out)
    elif hasattr(node, "get_label"):
        out.append(node.get_label())
    return out


def center(b):
    return b.get_x() + b.get_w() / 2, b.get_y() + b.get_h() / 2


# ---------------------------------------------------------------- map records, medals, career, history
def test_map_records_best_wave_medals_fastest(check):
    r = Records.in_memory()
    rep = r.record(run(wave=30))
    check(rep.counted and not rep.new_bests, "a first run counts but breaks no record (bests %s)" % rep.new_bests)
    check(r.best_wave(NAMES[0], "O1") == 30 and r.best_wave(NAMES[0]) == 30, "best wave 30")
    rep = r.record(run(wave=25))
    check(r.best_wave(NAMES[0], "O1") == 30 and not rep.new_bests, "a worse run keeps the best wave")
    rep = r.record(run(wave=57))
    check(r.best_wave(NAMES[0], "O1") == 57 and [k for k, _ in rep.new_bests] == ["best_wave"], "W57 is a new best")
    check(rep.before["best_wave"] == 30 and rep.after["best_wave"] == 57, "the report has the before / after record")
    check(r.medals(NAMES[0]) == {"O1": False, "ON": False, "ON2": False, "ONN": False}, "no medals before a win")
    rep = r.record(win(difficulty="ON", time=5000.0, lives=70))
    check(r.medals(NAMES[0]) == {"O1": False, "ON": True, "ON2": False, "ONN": False}, "a win on O(N) lights only that medal")
    check(("first_win", "FIRST CLEAR") in rep.new_bests, "first win on the mode is reported")
    rep = r.record(win(difficulty="ON", time=4500.0, lives=60))
    m = r.map_record(NAMES[0], Difficulty.ON)
    check(m["fastest"] == 4500.0 and m["best_lives"] == 70 and m["victories"] == 2 and m["runs"] == 2,
          "fastest win and best lives tracked separately (%s)" % m)
    check([k for k, _ in rep.new_bests] == ["fastest"], "a faster win is a new best (got %s)" % rep.new_bests)
    rep = r.record(win(difficulty="ON", time=9000.0, lives=95))
    check(r.map_record(NAMES[0], "ON")["fastest"] == 4500.0 and [k for k, _ in rep.new_bests] == ["best_lives"],
          "a slow win keeps the fastest time but can set most lives")
    check(r.best_wave(NAMES[1]) == 0 and r.medals(NAMES[1])["ON"] is False, "records are kept per map name")
    c = r.career()
    check(c["runs"] == 6 and c["victories"] == 3 and c["defeats"] == 3, "career runs / wins / defeats (%s)" % c)
    check(c["waves_cleared"] == 3 * 9 + 3 * 100 and c["enemies_killed"] == 6 * 500, "career waves and kills")
    check(c["best_wave"] == 100 and c["play_time"] == 6 * 300.0, "career best wave and play time")


def test_history_keeps_the_last_50_runs_newest_first(check):
    st = R.MemoryStorage()
    r = Records.with_storage(st)
    for i in range(60):
        r.record(run(seed=1000 + i, wave=i + 1, notes=["OPEN_SOURCE"], notes_on=True, tags=["daily"] if i == 59 else []))
    h = r.history()
    check(len(h) == R.HISTORY_MAX == 50, "history capped at 50 (%d)" % len(h))
    check(h[0]["seed"] == 1059 and h[-1]["seed"] == 1010, "newest first, oldest dropped")
    e = h[0]
    check(e["map"] == NAMES[0] and e["difficulty"] == "O1" and e["result"] == R.DEFEAT and e["wave"] == 60, "entry fields")
    check(e["seed_code"] and e["notes"] == ["OPEN_SOURCE"] and e["tags"] == ["daily"] and e["notes_on"], "seed code, notes, tags")
    check(st.saves == 60, "exactly one write per run (%d)" % st.saves)
    check(Records.with_storage(st).history() == h, "history survives a reload")


def test_exclusion_rules(check):
    st = R.MemoryStorage()
    r = Records.with_storage(st)
    for kw, why in ((dict(tutorial=True), "tutorial"), (dict(admin=True), "admin")):
        rep = r.record(win(**kw))
        check(not rep.counted and rep.excluded == why and not rep.unlocked, "%s run excluded" % why)
    check(st.saves == 0 and r.career()["runs"] == 0 and not r.history() and not r.unlocked(), "tutorial / admin change nothing")
    rep = r.record(win(reverse=True, reverse_level="ON2"))
    check(rep.excluded == "reverse" and [a.id for a in rep.unlocked] == ["reverse_ON2"], "reverse win: only its reverse achievement (%s)" % [a.id for a in rep.unlocked])
    check(r.career()["runs"] == 0 and not r.history() and r.best_wave(NAMES[0]) == 0, "reverse matches never touch map records / career / history")
    saves = st.saves
    r.record(run(result=R.ABANDONED, wave=0, waves_cleared=0))
    check(st.saves == saves, "quitting before wave 1 with nothing bought does not even write")
    rep = r.record(run(result=R.ABANDONED, wave=0, waves_cleared=0, heroes_bought=["CHILLSTIN"]))
    check(not rep.counted and r.career()["runs"] == 0 and not r.history(), "quitting before wave 1 is not a run")
    check("CHILLSTIN" in r.heroes_bought(), "... but its Hero Store purchase still counts")
    rep = r.record(run(result=R.ABANDONED, wave=12))
    c = r.career()
    check(rep.counted and c["abandoned"] == 1 and r.history()[0]["result"] == R.ABANDONED and r.best_wave(NAMES[0]) == 12,
          "a run quit mid-way is recorded as abandoned at its wave")


# ---------------------------------------------------------------- storage
def test_corrupt_and_partial_files_are_tolerated(check, tmp_path):
    path = str(tmp_path / "records.json")
    with open(path, "w") as f:
        f.write("{not json")
    fs = FileStorage(path)
    r = Records.with_storage(fs)
    check(r.career()["runs"] == 0, "a corrupt file loads as empty records")
    check(fs.recovered is not None and os.path.exists(fs.recovered) and open(fs.recovered).read() == "{not json",
          "the corrupt file is kept aside, untouched")
    r.record(run(wave=40))
    with open(path) as f:
        check(json.load(f)["career"]["runs"] == 1, "the next run writes a fresh, valid file")
    r.record(run(wave=41))
    with open(path + ".bak") as f:
        check(json.load(f)["career"]["runs"] == 1, "each save keeps the previous file as .bak")
    with open(path, "w") as f:
        f.write("[1, 2")
    r2 = Records.with_storage(FileStorage(path))
    check(r2.career()["runs"] == 1 and r2.best_wave(NAMES[0]) == 40, "a corrupt file falls back to the .bak")
    with open(path, "w") as f:
        json.dump({"maps": [1], "career": {"runs": "x", "victories": 3}, "history": [5, {"map": "M"}],
                   "achievements": {"first_win": "2026-01-01"}, "heroes_bought": "no"}, f)
    r3 = Records.with_storage(FileStorage(path))
    check(r3.career()["runs"] == 0 and r3.career()["victories"] == 3, "bad fields reset, good ones kept")
    check(len(r3.history()) == 1 and r3.is_unlocked("first_win") and r3.heroes_bought() == set(), "partial document cleaned")
    r3.record(win())
    check(Records.with_storage(FileStorage(path)).career()["victories"] == 4, "and it keeps working")


def test_persistent_records_live_in_the_prefs_folder(check, tmp_path):
    r = Records.persistent()
    r.record(run(wave=7))
    check(os.path.exists(str(tmp_path / "lindefense_records.json")), "saved as lindefense_records.json in LINDEFENSE_PREFS_DIR")


# ---------------------------------------------------------------- achievements
def test_achievement_table(check):
    a = R.achievements()
    ids = [x.id for x in a]
    check(20 <= len(a) <= 30 and len(set(ids)) == len(ids), "20-30 unique achievements (%d)" % len(a))
    check(all(x.title and x.description and x.mode in ("campaign", "reverse") for x in a), "every entry is complete")
    for n in NAMES:
        check(any(x.id == "win_" + R._slug(n) for x in a), "a win achievement for " + n)
    bosses = [e for e in EnemyType if e.is_boss()]
    check(all(R.achievement("boss_" + e.name.lower()) is not None for e in bosses), "one per boss incl. Palantir")
    check(sum(1 for x in a if x.mode == "reverse") == len(Difficulty.values()), "one reverse achievement per AI level")
    banned = ("boss", "palantir", "phase", "complete", "destroyed", "blocked", "surveillance")
    check(not [x.title for x in a if any(b in x.title.lower() for b in banned)], "titles do not trip the HUD toast's warning colours")


def test_achievements_from_synthetic_runs(check):
    r = Records.in_memory()
    got = [x.id for x in r.record(win(difficulty="ON2", leaks=0, heroes_deployed=[], max_tier=2)).unlocked]
    for want in ("first_win", "win_" + R._slug(NAMES[0]), "win_ON", "win_ON2", "flawless", "no_heroes", "tier_cap"):
        check(want in got, "%s unlocked by a flawless, hero-less, tier-2 O(N^2) win (got %s)" % (want, got))
    check("win_ONN" not in got and "all_maps" not in got, "harder modes / other maps still locked")
    got = [x.id for x in r.record(win(map_name=NAMES[1], difficulty="O1", leaks=2, heroes_deployed=["MR_LINDEMANN"], max_tier=3)).unlocked]
    check(got == ["win_" + R._slug(NAMES[1]), "lindemann"], "only the new map and Mr. Lindemann (got %s)" % got)
    check(not r.record(win(map_name=NAMES[1])).unlocked, "nothing unlocks twice")
    got = [x.id for x in r.record(run(bosses=["THREE_COM", "PALANTIR"])).unlocked]
    check(got == ["boss_three_com", "boss_palantir"], "boss kills count even in a lost run (%s)" % got)
    for n in NAMES[2:]:
        got = [x.id for x in r.record(win(map_name=n)).unlocked]
    check("all_maps" in got, "winning on the last map unlocks Full Coverage")
    check("wins_10" not in [a for a in r.unlocked()] and r.career()["victories"] == 8, "8 wins so far")
    r.record(win())
    got = [x.id for x in r.record(win()).unlocked]
    check(got == ["waves_1000", "wins_10"], "the 10th win unlocks Production Ready, and its 1,000th wave Long-Running Process (%s)" % got)
    heroes = [h.name for h in T.heroes()]
    r.record(run(heroes_bought=heroes[:10]))
    check(not r.is_unlocked("roster"), "10 of 18 heroes is not the full roster")
    got = [x.id for x in r.record(run(heroes_bought=heroes[10:])).unlocked]
    check("roster" in got, "purchases add up across runs to the full roster (%s)" % got)
    k = Records.in_memory()
    k.record(run(kills=99_990))
    s = run(kills=20)
    check([x.id for x in k.pending_live(s)] == ["kills_100k"], "live check: 99,990 + 20 kills is already 100k")
    check(k.pending_live(s, {"kills_100k"}) == [] and not k.is_unlocked("kills_100k"), "live checks never write")
    check([x.id for x in k.record(s).unlocked] == ["kills_100k"], "it unlocks when the run is recorded")


def test_achievements_from_a_real_game(check):
    """A real (shortened) campaign reaches victory through the wave manager and Palantir's death."""
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    t = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 1)
    for _ in range(1, 100):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    g.start_next_wave()
    g.run(ticks(9))
    pal = g.get_palantir()
    check(pal is not None, "Palantir on wave 100")
    kill_outright(g, pal)
    g.run(ticks(Game.VICTORY_SEQUENCE_TIME) + 5)
    check(g.get_state() is State.VICTORY, "victory")
    check(g.get_boss_kills() == [EnemyType.PALANTIR], "the boss counter saw Palantir (%s)" % g.get_boss_kills())
    s = RunSummary.of(g)
    check(s.result == R.VICTORY and s.wave == 100 and s.map_name == NAMES[0] and s.difficulty == g.get_difficulty().id, "summary")
    check(s.max_tier == 1 and len(s.towers) == 1 and s.towers[0].type == "GPT" and not s.heroes_deployed, "towers in the summary")
    r = Records.in_memory()
    rep = r.record(s)
    got = [a.id for a in rep.unlocked]
    for want in ("first_win", "win_" + R._slug(NAMES[0]), "boss_palantir", "flawless", "no_heroes", "tier_cap"):
        check(want in got, "real win unlocks %s (got %s)" % (want, got))
    check(r.medals(NAMES[0])[g.get_difficulty().id] and r.history()[0]["result"] == R.VICTORY, "medal and history")
    del t


def test_sold_towers_bosses_and_purchases_are_counted_purely(check):
    g = new_game(0)
    a = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 2)
    b = force_place(g, T.CLAUDE, buildable_near(g, Vec(800, 600), 150), 0)
    a.add_damage_dealt(5000)
    a.add_kill()
    b.add_damage_dealt(100)
    earned = g.get_total_cash_earned()
    refund = g.sell_tower(a)
    check(refund > 0 and g.get_total_cash_earned() == earned + refund, "selling still pays through add_cash")
    check(g.get_tower_manager().get_sold() == [(a, refund)] and g.get_tower_manager().get_total_refunds() == refund, "sale recorded")
    e = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 50)
    kill_outright(g, e)
    check(g.get_boss_kills() == [EnemyType.BELLARMINE_COLLEGE_PREP], "boss kill counted")
    g.add_cash(5000, None)
    check(g.purchase_hero(T.CHILLSTIN) and g.get_heroes_bought() == [T.CHILLSTIN], "hero purchase counted")
    s = RunSummary.of(g)
    mvp = s.mvp()
    check(mvp[0].type == "GPT" and mvp[0].sold and mvp[0].tier == 2 and mvp[0].damage == 5000 and mvp[0].kills == 1,
          "a sold tower keeps its stats in the MVP table")
    check(mvp[1].type == "CLAUDE" and not mvp[1].sold and s.max_tier == 2, "live towers too")
    check(s.cash_earned == g.get_total_cash_earned() - refund, "credits earned exclude sell refunds")
    check(s.heroes_bought == ["CHILLSTIN"] and s.result == R.ABANDONED, "purchases and result")
    cheat = new_game(0)
    cheat.set_admin(False, True, False)
    check(cheat.purchase_hero(T.SAGE_AARAV), "admin money buys a hero")
    cs = RunSummary.of(cheat)
    check(cs.heroes_bought == [] and cs.admin, "purchases made with admin money never count")


# ---------------------------------------------------------------- end-of-run report, RETRY, abandon on quit
class _App:
    def __init__(self):
        self.calls = []

    def __getattr__(self, n):
        if n.startswith("_"):
            raise AttributeError(n)
        return lambda *a: self.calls.append(n)


def _defeat(g):
    e = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    g.lose_lives(10_000, e)
    for _ in range(400):
        if g.get_state() is not State.PLAYING:
            break
        g.step(Game.DT)


def test_end_screen_report_and_toast(check):
    from lindefense.ui.game_screen import GameScreen
    g = new_game(0)
    g.get_variance().enable()
    g.get_variance().pick(0)
    recs = Records.in_memory()
    s = GameScreen(_App(), g)
    s.set_run_session(RunSession(recs, g))
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 1)
    g.start_next_wave()
    s.frame(0.02)
    e = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 50)
    kill_outright(g, e)
    g._banner_time = 0
    for _ in range(3):
        s.frame(0.6)
    check(s.hud.banner_text is not None and s.hud.banner_text.startswith("ACHIEVEMENT") and "GRADUATED" in s.hud.banner_text,
          "a live achievement shows a HUD toast (%r)" % s.hud.banner_text)
    check(not recs.is_unlocked("boss_bellarmine_college_prep"), "... but nothing is saved before the run ends")
    _defeat(g)
    s.frame(0.02)
    rep = s.get_run_report()
    check(rep is not None and rep.counted and rep.summary.result == R.DEFEAT, "the defeat was recorded")
    check("boss_bellarmine_college_prep" in [a.id for a in rep.unlocked], "the toasted achievement unlocks at run end")
    check(s.end_run() is rep and len(recs.history()) == 1, "recorded once (end_run is idempotent)")
    texts = [b.get_text() for b in s.overlay_buttons]
    check(texts == ["SUMMARY", "REPORT", "RETRY", "REPLAY SEED", "MAP SELECT", "MAIN MENU"], "end buttons %s" % texts)
    check(any("ACHIEVEMENT" in t for t in labels(s.overlay)), "the summary page mentions the unlocked achievement")
    paint(s)
    s.mouse_pressed(*center(s.overlay_buttons[1]), False)
    check(s.end_page == 1, "REPORT tab opens the report page")
    txt = labels(s.overlay)
    check("TOP TOWERS  //  BY DAMAGE" in txt and "GPT" in txt and "GRADUATED" in txt, "MVP table and achievements shown")
    check(any(t.startswith("T1/") for t in txt), "tier column")
    paint(s)
    s.mouse_pressed(*center(s.overlay_buttons[0]), False)
    check(s.end_page == 0, "SUMMARY tab goes back")
    retry = next(b for b in s.overlay_buttons if b.get_text() == "RETRY")
    s.mouse_pressed(*center(retry), False)
    check(s.app.calls[-1] == "restart_level", "RETRY restarts the level (%s)" % s.app.calls)


def _app():
    from lindefense.app import LindefenseApp
    from lindefense.ui.scaled_layer import ScaledLayer
    app = LindefenseApp.__new__(LindefenseApp)
    app.root = ScaledLayer()
    app.menu = app.map_select = app.game_screen = None
    app._settle_heap = lambda: None
    return app


def test_retry_starts_the_same_map_and_difficulty(check):
    Records._shared = Records.in_memory()
    app = _app()
    g = Game(maps.create(3), 777, Difficulty.ON2)
    app.start_game(g)
    gs = app.get_game_screen()
    gs.frame(0.02)
    g.start_next_wave()
    _defeat(g)
    gs.frame(0.02)
    retry = next(b for b in gs.overlay_buttons if b.get_text() == "RETRY")
    gs.mouse_pressed(*center(retry), False)
    n = app.get_game()
    check(n is not None and n is not g, "RETRY started a new game")
    check(n.get_map().get_name() == NAMES[3] and n.get_difficulty() is Difficulty.ON2, "same map and difficulty")
    check(n.get_seed() != 777, "with a new seed")
    h = Records.persistent().history()
    check(len(h) == 1 and h[0]["result"] == R.DEFEAT and h[0]["seed"] == 777, "the lost run was recorded once (%s)" % h)
    n.start_next_wave()
    app.show_map_select()
    from lindefense import savegame
    check(len(Records.persistent().history()) == 1 and savegame.slot().exists(),
          "leaving mid-run saves it for CONTINUE instead of recording it")
    app.show_menu()
    check(len(Records.persistent().history()) == 1, "leaving the map select records nothing")
    app.start_tutorial()
    app.get_game().start_next_wave()
    app.show_menu()
    check(len(Records.persistent().history()) == 1 and savegame.slot().exists(),
          "the tutorial is never recorded and leaves the saved run alone")
    app.replay_run(1, Difficulty.ON, 4242, False)
    h = Records.persistent().history()
    check(len(h) == 2 and h[0]["result"] == R.ABANDONED and h[0]["wave"] == 1 and h[0]["seed"] == n.get_seed(),
          "a new run replacing the saved one records that run as abandoned (%s)" % h[:1])
    r = app.get_game()
    check(r.get_map().get_name() == NAMES[1] and r.get_difficulty() is Difficulty.ON and r.get_seed() == 4242
          and not r.get_variance().is_enabled(), "history REPLAY SEED starts that map / mode / seed")


# ---------------------------------------------------------------- screens
def _sample_records():
    r = Records.in_memory()
    r.record(win(map_name=NAMES[0], difficulty="ON", notes=["OPEN_SOURCE"], notes_on=True))
    r.record(run(map_name=NAMES[2], map_index=2, difficulty="ON2", wave=57, seed=99, tags=["daily"]))
    r.record(win(map_name=NAMES[5], map_index=5, difficulty="O1"))
    return r


def test_stats_screen_builds_and_replays_a_seed(check):
    from lindefense.ui.stats_screen import StatsScreen
    replays = []
    st = StatsScreen(lambda: replays.append("close"), lambda *a: replays.append(a), _sample_records())
    for t in StatsScreen.Tab.values():
        st.mouse_pressed(*center(st.tabs[t.ordinal]))
        check(st.get_tab() is t, "tab %s opens" % t.label)
        st.frame(0.05)
        paint(st)
    st.set_tab(StatsScreen.Tab.CAREER)
    txt = labels(st)
    check("3" in txt and "2 (67%)" in txt, "career tiles show runs and wins (%s)" % [t for t in txt if "%" in t])
    st.set_tab(StatsScreen.Tab.ACHIEVEMENTS)
    check("HELLO, WORLD" in labels(st), "achievement cards")
    st.set_tab(StatsScreen.Tab.HISTORY)
    check(len(st.replay_buttons) == 3 and all(b.is_enabled() for b in st.replay_buttons), "a REPLAY SEED per history row")
    st.mouse_pressed(*center(st.replay_buttons[1]))
    check(replays == [(2, Difficulty.ON2, 99, False, ())], "REPLAY SEED passes map / difficulty / seed / notes / rules (%s)" % replays)
    st.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ESCAPE, KeyEvent.CHAR_UNDEFINED))
    check(replays[-1] == "close", "Esc closes")
    empty = StatsScreen(None, None, Records.in_memory())
    for t in StatsScreen.Tab.values():
        empty.set_tab(t)
        paint(empty)
    check(True, "an empty record set paints on every tab")


def test_menu_records_button_opens_the_stats_screen(check):
    from lindefense.ui.menu_screen import MenuScreen
    Records._shared = _sample_records()
    m = MenuScreen(_App())
    m.skip_intro()
    rec_btn = next(b for b in m.buttons if b.text.get_label() == "RECORDS")
    play = next(b for b in m.buttons if b.text.get_label() == "PLAY")
    check(play.hit(800, 513), "PLAY did not move")
    m.mouse_pressed(rec_btn.get_x() + 70, rec_btn.get_y() + 25)
    check(m.stats_shown and m.stats is not None, "RECORDS opens the stats screen")
    m.frame(0.05)
    m.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ESCAPE, KeyEvent.CHAR_UNDEFINED))
    check(not m.stats_shown and m.stats is None, "Esc closes it")


def test_map_cards_show_medals_best_wave_and_remember_difficulty(check):
    from lindefense.ui.map_select_screen import MapSelectScreen
    Records._shared = _sample_records()
    Difficulty.set_selected(Difficulty.ON)
    ms = MapSelectScreen(_App())
    marks = {n: [c.f_glow > 0 for c in cs] for n, cs in ms.medal_marks.items()}
    check(marks[NAMES[0]] == [False, True, False, False], "Silicon Circuit: only the O(N) medal lit (%s)" % marks[NAMES[0]])
    check(marks[NAMES[5]] == [True, False, False, False] and not any(marks[NAMES[2]]), "other cards")
    best = {e[1]: e[0].get_label() for e in ms.best_labels}
    check(best[NAMES[0]] == "BEST W100" and best[NAMES[2]] == "BEST  --", "BEST on the selected mode (%s)" % best)
    sel = ms.difficulty
    ms.mouse_pressed(sel.bx + 2 * (sel.bw + sel.gap) + sel.bw / 2, sel.by + sel.bh / 2)
    check(Difficulty.get_selected() is Difficulty.ON2, "clicked O(N^2)")
    best = {e[1]: e[0].get_label() for e in ms.best_labels}
    check(best[NAMES[2]] == "BEST W57" and best[NAMES[0]] == "BEST  --", "BEST follows the selected mode (%s)" % best)
    ms.open_briefing(2)
    txt = labels(ms.briefing)
    check("W57" in txt and "BEST WAVE" in txt, "the briefing shows that map's records for the mode")
    paint(ms)
    Difficulty.set_selected(None)
    check(R.restore_difficulty() is Difficulty.ON2 and Difficulty.get_selected() is Difficulty.ON2, "the last mode is restored at launch")


def test_catalog_heroes_owned_and_locked(check):
    from lindefense.ui.catalog_screen import CatalogScreen
    hc = HeroCollection.in_memory()
    hc.unlock(T.CHILLSTIN)
    hc.unlock(T.MR_LINDEMANN)
    c = CatalogScreen(None, hc)
    c.set_tab(CatalogScreen.Tab.HEROES)
    txt = labels(c.grid_layer)
    check("2 / 18 UNLOCKED" in txt, "X/18 unlocked line")
    check(txt.count("OWNED") == 2 and txt.count("LOCKED") == 16, "owned / locked badges (%d / %d)" % (txt.count("OWNED"), txt.count("LOCKED")))
    c.select(list(T.heroes()).index(T.MR_LINDEMANN))
    check(any(t.startswith("OWNED") for t in labels(c.card)), "the detail card says owned")
    paint(c)


def test_freeplay_extends_the_recorded_victory(check):
    """A campaign win is recorded when the victory screen shows; CONTINUE - FREEPLAY keeps the same run going, and its
    end updates that run (best wave, history entry, career totals) instead of counting a second run."""
    from lindefense.ui.game_screen import GameScreen
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 1)
    recs = Records.in_memory()
    s = GameScreen(_App(), g)
    s.set_run_session(RunSession(recs, g))
    for _ in range(1, 100):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    g.start_next_wave()
    g.run(ticks(9))
    kill_outright(g, g.get_palantir())
    g.run(ticks(Game.VICTORY_SEQUENCE_TIME) + 5)
    s.frame(0.02)
    check(g.get_state() is State.VICTORY and recs.career()["runs"] == 1 and recs.career()["victories"] == 1,
          "the campaign victory is recorded once (%s)" % recs.career())
    best_before = recs.map_record(NAMES[0], g.get_difficulty())["best_wave"]
    s.continue_freeplay()
    check(g.is_freeplay() and g.get_state() is State.PLAYING and "freeplay" in g.get_tags(), "freeplay continues")
    for _ in range(3):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    s.frame(0.02)
    _defeat(g)
    s.frame(0.02)
    c = recs.career()
    check(g.get_state() is State.VICTORY and c["runs"] == 1 and c["victories"] == 1 and c["defeats"] == 0,
          "freeplay's end does not count a second run (%s)" % c)
    h = recs.history()
    check(len(h) == 1 and h[0]["wave"] > 100 and "freeplay" in h[0]["tags"], "the history entry is updated (%s)" % h[:1])
    after = recs.map_record(NAMES[0], g.get_difficulty())["best_wave"]
    check(after > best_before and after == h[0]["wave"], "the map's best wave includes freeplay (%s -> %s)" % (best_before, after))
    rep = s.get_run_report()
    check(rep is not None and rep.counted and ("best_wave", "BEST WAVE") in rep.new_bests, "the end report shows the new best")


def test_freeplay_saved_and_continued_still_extends_its_victory(check, tmp_path):
    """Freeplay autosaves again; a Freeplay run saved, loaded in a later session and finished extends the campaign
    victory recorded before it instead of counting a second run."""
    from lindefense import savegame
    from lindefense.ui.game_screen import GameScreen
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150), 1)
    recs = Records.in_memory()
    s = GameScreen(_App(), g)
    s.set_run_session(RunSession(recs, g))
    for _ in range(1, 100):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    g.start_next_wave()
    g.run(ticks(9))
    kill_outright(g, g.get_palantir())
    g.run(ticks(Game.VICTORY_SEQUENCE_TIME) + 5)
    s.frame(0.02)
    s.continue_freeplay()
    for _ in range(2):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    slot = savegame.SaveSlot(str(tmp_path / "run_save.bin"))
    slot.save(g)
    s.session.cancel()                       # leaving with the run saved: not recorded now
    g2 = slot.load()
    check(g2.is_freeplay() and getattr(g2, "_records_baseline", None) is not None, "the baseline survives the save")
    s2 = GameScreen(_App(), g2)
    s2.set_run_session(RunSession(recs, g2))
    s2.frame(0.02)
    _defeat(g2)
    s2.frame(0.02)
    c = recs.career()
    check(c["runs"] == 1 and c["victories"] == 1, "one run, one victory (%s)" % c)
    check(len(recs.history()) == 1 and recs.history()[0]["wave"] > 100, "the history entry is extended")
