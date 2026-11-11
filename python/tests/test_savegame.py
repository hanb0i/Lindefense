"""Save & Continue (lindefense.savegame): a run saved at a wave boundary (or mid-wave), loaded and played on is
bit-identical to the same run played straight through; bad saves are reported once and deleted; the app autosaves at
wave boundaries and on quit, never saves tutorial / reverse runs, deletes the save on game over and on a new run.

Fidelity is checked with a per-step state digest (the shared simtrace fold plus RNG / scheduled-task / Patch Notes
state) compared tick by tick between the uninterrupted run and every continuation. Every test uses temp folders."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib

import pytest

from lindefense import prefs, savegame, version
from lindefense.ai.defender_ai import DefenderAI, Options, Plan, Step
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.misc import AdminMode, HeroCollection
from lindefense.tower.tower_type import TowerType
from lindefense.variance.variance import Picker

TESTS = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(autouse=True)
def _temp_prefs(tmp_path, monkeypatch):
    """Every test here writes only to its own temp folder (prefs nodes, Hero Store, the save slot)."""
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path / "prefs"))
    prefs._nodes.clear()
    shared = HeroCollection._shared
    HeroCollection._shared = None
    AdminMode._unlocked, AdminMode._options = None, {}
    yield
    prefs._nodes.clear()
    HeroCollection._shared = shared
    AdminMode._unlocked, AdminMode._options = None, {}


# ====================================================================== a deterministic player and a state digest
_pack = struct.Struct("<d").pack


def digest(g):
    """The simtrace fold for one step, plus the RNG, scheduled tasks and Patch Notes / Breaking News state."""
    h = hashlib.blake2b(digest_size=12)
    u = h.update
    u(_pack(g.get_time()))
    u(_pack(float(g.get_cash())))
    u(_pack(float(g.get_lives())))
    u(_pack(float(g.get_wave())))
    for e in g.get_enemy_manager().get_enemies():
        p = e.get_position()
        u(b"e%d%s" % (e.get_id(), e.get_type().name.encode()))
        u(_pack(p.x)); u(_pack(p.y)); u(_pack(e.get_hp())); u(_pack(e.get_distance())); u(_pack(e.get_slow_fraction()))
        u(b"A" if e.is_alive() else b"D")
    for t in g.get_tower_manager().get_towers():
        p = t.get_position()
        u(b"t%d%d%s" % (t.get_id(), t.get_tier(), t.get_targeting().name.encode()))
        u(_pack(p.x)); u(_pack(p.y)); u(_pack(float(t.get_damage_dealt()))); u(_pack(float(t.get_kills())))
        if t.get_ability() is not None:
            u(_pack(float(t.get_ability_cooldown_remaining())))
    for q in g.get_combat().get_projectiles():
        p = q.get_position()
        u(_pack(p.x)); u(_pack(p.y))
    fx = g.get_effects()
    u(b"fx%d.%d.%d.%d.%d.%d" % (len(fx.get_zones()), len(fx.get_walkers()), len(fx.get_drones()), len(fx.get_hazards()),
                                len(fx.get_mines()), len(fx._tasks)))
    u(b"rng%d" % g.get_rng()._random._seed)
    v = g.get_variance()
    u(repr((v.get_active(), v.get_news(), v.get_news_lane(), v.is_draft_pending(), g.get_banner())).encode())
    return h.digest()


HEROES = (TowerType.LOBBER_LUIS, TowerType.BOOM_SAM, TowerType.CHILLSTIN)   # their attacks schedule delayed blasts
AI_MEMORY = ("_tracked_wave", "_lives_at_wave_start", "_lives_prev_wave")


def new_run(map_idx, seed, difficulty, picker):
    g = Game(maps.create(map_idx), seed, difficulty)
    for h in HEROES:
        g.get_hero_collection().unlock(h)
    g.get_variance().enable(picker)
    return g


def new_player(g, memory=None):
    """The DefenderAI as the player: buys, upgrades, deploys the three heroes, unlocks and fires abilities. Its only
    memory outside the game (lives seen at recent wave starts) is carried across a save like a human's."""
    o = Options()
    o.plan = Plan.EFFICIENT
    o.opening = [Step(TowerType.GEMINI, 0, 0, 1)] + [Step(h, 0, i % 2, 2 + i) for i, h in enumerate(HEROES)]
    o.unlock_abilities = True
    ai = DefenderAI(g, o)
    if memory is not None:
        for f, v in zip(AI_MEMORY, memory):
            setattr(ai, f, v)
    return ai


def memory_of(ai):
    return tuple(getattr(ai, f) for f in AI_MEMORY)


def act_and_step(g, ai, last_wave):
    """One tick of play: the player's decisions (a function of the game state only), then one simulation step."""
    if g.get_tick() % 15 == 0:
        ai.manage()
    v = g.get_variance()
    if v.is_draft_pending():
        v.pick(g.get_wave() % len(v.get_offer()))   # the PLAYER picker waits for this click
    if g.get_wave_manager().can_start_next_wave() and g.get_wave() < last_wave:
        g.start_next_wave()
    g.step(Game.DT)
    g.get_events().clear()


def finished(g, last_wave):
    return g.get_state() is not State.PLAYING or (g.get_wave() >= last_wave and not g.get_wave_manager().is_wave_active())


def play_and_snapshot(g, ai, last_wave, take):
    """Plays to the end; take(g) says when to snapshot (before that tick's actions). Returns the per-tick digests
    and the snapshots as (tick, payload, player memory)."""
    trace, snaps = {}, []
    while not finished(g, last_wave):
        if take(g):
            snaps.append((g.get_tick(), savegame.dumps(g), memory_of(ai)))
        act_and_step(g, ai, last_wave)
        trace[g.get_tick()] = digest(g)
    return trace, snaps


def continue_from(g, memory, last_wave, trace, max_steps=None):
    """Plays a loaded game on; returns (steps, ticks whose digest differs from the uninterrupted run)."""
    ai = new_player(g, memory)
    steps, bad = 0, []
    while not finished(g, last_wave) and (max_steps is None or steps < max_steps):
        act_and_step(g, ai, last_wave)
        steps += 1
        if trace.get(g.get_tick()) != digest(g):
            bad.append(g.get_tick())
    return steps, bad


def boundary_and_mid_wave(boundaries, mid_wave):
    taken = set()

    def take(g):
        wm = g.get_wave_manager()
        done = g.get_last_completed_wave()
        if not wm.is_wave_active() and done in boundaries and done not in taken:
            taken.add(done)
            return True
        if wm.is_wave_active() and g.get_wave() == mid_wave and "mid" not in taken and wm.get_wave_time() > 10:
            taken.add("mid")
            return True
        return False
    return take


# ====================================================================== fidelity
@pytest.mark.parametrize("map_idx,diff,picker", [
    (2, Difficulty.O1, Picker.PLAYER), (2, Difficulty.ON2, Picker.RANDOM),
    (6, Difficulty.ON, Picker.RANDOM), (6, Difficulty.ONN, Picker.PLAYER)])
def test_continued_run_is_bit_identical(check, tmp_path, map_idx, diff, picker):
    last = 6
    g = new_run(map_idx, 31 + map_idx, diff, picker)
    trace, snaps = play_and_snapshot(g, new_player(g), last, boundary_and_mid_wave({2, 3, 5}, 6))
    check(len(snaps) == 4, "three wave-boundary snapshots and one mid-wave (got %d)" % len(snaps))
    check(g.get_wave() == last and g.get_state() is State.PLAYING, "the uninterrupted run reached wave %d" % g.get_wave())
    check(len(g._deployed_heroes) == 3, "heroes were deployed (%s)" % sorted(t.name for t in g._deployed_heroes))
    check(len(g.get_variance().get_active()) >= 1, "a Patch Note was shipped")
    end = (g.get_tick(), g.get_cash(), g.get_lives(), g.get_enemy_manager().get_total_killed())
    slot = savegame.SaveSlot(str(tmp_path / "slot.bin"))
    for i, (tick, payload, memory) in enumerate(snaps):
        if i % 2 == 0:   # half of them through the real file path (header, zlib, checksum, atomic write)
            restored = savegame.loads(payload)
            slot.save(restored)
            loaded = slot.load()
        else:
            loaded = savegame.loads(payload)
        check(loaded.get_tick() == tick, "the snapshot holds tick %d (got %d)" % (tick, loaded.get_tick()))
        steps, bad = continue_from(loaded, memory, last, trace)
        check(steps > 0 and not bad, "map %d %s, saved at tick %d: %d of %d continued steps differ (first at %s)"
              % (map_idx, diff.name, tick, len(bad), steps, bad[:1]))
        got = (loaded.get_tick(), loaded.get_cash(), loaded.get_lives(), loaded.get_enemy_manager().get_total_killed())
        check(got == end, "continuation ends exactly where the uninterrupted run did: %s vs %s" % (got, end))


@pytest.mark.slow
def test_long_campaigns_continue_bit_identically_on_every_map(check):
    """Every map, 30 waves (bosses at none yet, Prompt Injection from 30, sorters, Breaking News, three drafts),
    snapshots every ~1500 ticks, each continued for 2500 steps."""
    pickers = (Picker.RANDOM, Picker.PLAYER, Picker.FIRST)
    for m in range(maps.MAP_COUNT):
        d = Difficulty.values()[m % 4]
        g = new_run(m, 101 + m, d, pickers[m % 3])
        trace, snaps = play_and_snapshot(g, new_player(g), 30, lambda g: g.get_tick() % 1499 == 1498)
        bad_total = 0
        for tick, payload, memory in snaps:
            steps, bad = continue_from(savegame.loads(payload), memory, 30, trace, 2500)
            bad_total += len(bad)
        check(len(snaps) >= 15 and bad_total == 0, "map %d %s: %d snapshots, %d differing steps"
              % (m, d.name, len(snaps), bad_total))


def test_scheduled_blasts_in_flight_survive_a_save(check):
    """Delayed explosions are closures held by Effects.schedule(); saving while they are pending must replay them."""
    from lindefense.tools.perf_bench import PerfBench

    def drive(g, f):
        if len(g.get_enemy_manager().get_enemies()) < 60:
            PerfBench.spawn_crowd(g, 20, f)
        if f % 60 == 0:
            PerfBench.fire_abilities(g)
        g.step(Game.DT)
        g.get_events().clear()

    g = PerfBench.late_game(0, Difficulty.O1, 24, 95)
    PerfBench.spawn_crowd(g, 80, 0)
    trace, snaps, kinds = {}, [], set()
    for f in range(360):
        tasks = g.get_effects()._tasks
        if tasks and (not snaps or f - snaps[-1][0] > 40):
            snaps.append((f, savegame.dumps(g)))
            kinds.update(t.action.__qualname__ for t in tasks)
        drive(g, f)
        trace[f] = digest(g)
    check(len(snaps) >= 5 and len(kinds) >= 4, "snapshots taken with several kinds of blasts pending (%s)" % sorted(kinds))
    for f0, payload in snaps:
        h = savegame.loads(payload)
        bad = []
        for f in range(f0, 360):
            drive(h, f)
            if trace[f] != digest(h):
                bad.append(f)
        check(not bad, "saved at frame %d: %d of %d steps differ" % (f0, len(bad), 360 - f0))


def _drive_crowd(g, f):
    """Deterministic busy-board driver: keeps ~60 enemies on the track and fires every ability once a second."""
    from lindefense.tools.perf_bench import PerfBench
    if len(g.get_enemy_manager().get_enemies()) < 60:
        PerfBench.spawn_crowd(g, 20, f)
    if f % 60 == 0:
        PerfBench.fire_abilities(g)
    g.step(Game.DT)
    g.get_events().clear()


def test_save_loads_in_another_process_with_another_hash_seed(check, tmp_path):
    """No absolute paths, no hash-seed dependence: saves continued in a fresh interpreter (different
    PYTHONHASHSEED, different working directory) match the continuations in this process. One save is a campaign
    at a wave boundary, the other a busy board with delayed blasts (closures) still pending."""
    from lindefense.tools.perf_bench import PerfBench
    g = new_run(1, 77, Difficulty.ON, Picker.RANDOM)
    ai = new_player(g)
    while not (g.get_last_completed_wave() >= 3 and not g.get_wave_manager().is_wave_active()):
        act_and_step(g, ai, 6)
    campaign = str(tmp_path / "campaign.bin")
    savegame.SaveSlot(campaign).save(g)
    memory = memory_of(ai)
    for _ in range(1500):
        act_and_step(g, ai, 6)
    b = PerfBench.late_game(0, Difficulty.O1, 24, 95)
    PerfBench.spawn_crowd(b, 80, 0)
    f0 = 0
    while f0 < 30 or not b.get_effects()._tasks:
        _drive_crowd(b, f0)
        f0 += 1
    busy = str(tmp_path / "busy.bin")
    savegame.SaveSlot(busy).save(b)
    for f in range(f0, f0 + 240):
        _drive_crowd(b, f)
    here = digest(g).hex() + " " + digest(b).hex()
    for path in (campaign, busy):
        data = open(path, "rb").read()
        payload = zlib.decompress(data[data.index(b"\n", len(savegame.MAGIC)) + 1:])
        pkg = os.path.dirname(os.path.dirname(savegame.__file__))
        check(pkg.encode() not in payload and os.getcwd().encode() not in payload and b"/Users/" not in payload,
              "the save holds no absolute paths")
    script = ("import sys; sys.path[:0] = [%r, %r]\n"
              "import test_savegame as T\n"
              "from lindefense import savegame\n"
              "g = savegame.SaveSlot(%r).load()\n"
              "ai = T.new_player(g, %r)\n"
              "for _ in range(1500): T.act_and_step(g, ai, 6)\n"
              "b = savegame.SaveSlot(%r).load()\n"
              "for f in range(%d, %d): T._drive_crowd(b, f)\n"
              "print(T.digest(g).hex(), T.digest(b).hex())\n") % (pkg, TESTS, campaign, memory, busy, f0, f0 + 240)
    env = dict(os.environ, PYTHONHASHSEED="12345", LINDEFENSE_PREFS_DIR=str(tmp_path / "other_prefs"))
    env.pop("PYTHONPATH", None)
    out = subprocess.run([sys.executable, "-c", script], cwd=str(tmp_path), env=env, capture_output=True, text=True,
                         timeout=120)
    check(out.returncode == 0, "the other process loaded the saves: %s" % out.stderr[-800:])
    check(out.stdout.strip() == here, "same states later in both processes (%s vs %s)" % (out.stdout.strip(), here))


def test_restored_run_keeps_shared_data_identity(check, tmp_path):
    """Catalog defs and behaviours come back as the live singletons, strings compared by identity stay interned,
    id()-keyed tables are re-keyed and the global id counters continue."""
    from lindefense.enemy.enemy import Enemy
    from lindefense.tower import catalog
    from lindefense.tower.behavior.registry import behavior_of
    from lindefense.tower.tower import Tower
    from lindefense.tools.perf_bench import PerfBench
    from kit import tower_near_track
    g = PerfBench.late_game(2, Difficulty.ON, 24, 40)
    tower_near_track(g, TowerType.QWEN, 3, 500)   # patrol drones
    PerfBench.spawn_crowd(g, 40, 0)
    g.run(120)
    ids = (Enemy._next_id, Tower._next_id)
    payload = savegame.dumps(g)
    Enemy._next_id, Tower._next_id = 1, 1
    h = savegame.loads(payload)
    check((Enemy._next_id, Tower._next_id) == ids, "the id counters are restored")
    towers = h.get_tower_manager().get_towers()
    check(all(t.get_def() is catalog.get(t.get_type()) for t in towers), "TowerDefs are the catalog's")
    check(all(t.get_behavior() is behavior_of(t.get_type()) for t in towers), "behaviours are the shared ones")
    from lindefense.effects.effects import Drone
    drones = h.get_effects().get_drones()
    check(any(d.mode is Drone.PATROL for d in drones) and all(d.mode is Drone.PATROL or d.mode is Drone.ORBIT
                                                              or d.mode is Drone.STATIC for d in drones),
          "drone modes are the interned constants Drone.update compares by identity (%s)" % [d.mode for d in drones])
    em = h.get_enemy_manager()
    em._rebuild_route_index()
    check(all(len(em._route_mates(e)) > 0 for e in em.get_enemies() if e.is_alive() and not e.is_stored()),
          "the route index (keyed by id(route)) finds every live enemy's lane")
    check(h.get_hero_collection() is not HeroCollection._shared, "an in-memory Hero Store collection travels by value")


def test_persistent_hero_store_is_reattached(check, tmp_path):
    g = Game(maps.create(0), 5)
    g.set_hero_collection(HeroCollection.persistent())
    h = savegame.loads(savegame.dumps(g))
    check(h.get_hero_collection() is HeroCollection.persistent(), "the saved Hero Store collection is the live one")


# ====================================================================== bad saves
def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _with_header(data, **changes):
    nl = data.index(b"\n", len(savegame.MAGIC))
    header = json.loads(data[len(savegame.MAGIC):nl])
    header.update(changes)
    return savegame.MAGIC + json.dumps(header).encode() + data[nl:]


def test_corrupt_or_old_saves_are_reported_once_and_deleted(check, tmp_path):
    g = new_run(0, 9, Difficulty.O1, Picker.FIRST)
    g.get_wave_manager().start_next_wave()
    good = savegame.encode(g)
    nl = good.index(b"\n", len(savegame.MAGIC))
    bad_pickle = zlib.compress(b"\x80\x05not a pickle at all.")
    bad_payload = savegame.MAGIC + json.dumps(dict(json.loads(good[len(savegame.MAGIC):nl]),
                                                   size=len(zlib.decompress(bad_pickle)),
                                                   sha256=hashlib.sha256(zlib.decompress(bad_pickle)).hexdigest())).encode() + b"\n" + bad_pickle
    cases = {
        "garbage": b"\x00\x01garbage",
        "empty": b"",
        "truncated": good[:len(good) // 2],
        "older version": _with_header(good, game_version="2.9 BETA"),
        "older format": _with_header(good, format=savegame.FORMAT - 1),
        "other python": _with_header(good, python="3.9"),
        "flipped byte": good[:-20] + bytes([good[-20] ^ 0xFF]) + good[-19:],
        "bad pickle": bad_payload,
    }
    slot = savegame.slot()
    for name, data in cases.items():
        _write(slot.path(), data)
        info, notice = savegame.menu_entry()
        check(info is None and notice == savegame.LOAD_FAILED_TEXT, "%s: the menu reports it (%r)" % (name, notice))
        check(not os.path.exists(slot.path()), "%s: the save is deleted" % name)
        check(savegame.menu_entry() == (None, None), "%s: reported only once" % name)
    _write(slot.path(), bad_payload)
    with pytest.raises(savegame.SaveError):
        slot.load()
    _write(slot.path(), good)
    info, notice = savegame.menu_entry()
    check(notice is None and info is not None and info.label() == "The Silicon Circuit, O(1), wave 1",
          "a good save is offered (%s)" % (info and info.label()))
    check(json.loads(good[len(savegame.MAGIC):nl])["game_version"] == version.NUMBER + " " + version.STAGE,
          "the header carries the game version")


def test_loading_refuses_foreign_types_and_changed_code(check):
    import pickle
    evil = pickle.dumps({"game": os.system})
    with pytest.raises(savegame.SaveError):
        savegame.loads(evil)
    with pytest.raises(savegame.SaveError):
        savegame._make_function(("nested", "lindefense.effects.effects", "Effects.fire.<locals>.<lambda>", 0, "0" * 24),
                                None, None, None, None)


# ====================================================================== the app: autosave, CONTINUE, game over
class _HeadlessApp:
    """A LindefenseApp without a window: the real screen / autosave methods on a ScaledLayer root."""

    @staticmethod
    def make(monkeypatch):
        from lindefense.app import LindefenseApp
        from lindefense.ui.scaled_layer import ScaledLayer
        monkeypatch.setattr(LindefenseApp, "_settle_heap", staticmethod(lambda: None))
        app = LindefenseApp.__new__(LindefenseApp)
        app.root = ScaledLayer()
        app.menu = app.map_select = app.game_screen = None
        app.demo = app.window_grab = app.autosave = None
        app._errors = {}
        app.running = True
        app.px_w, app.px_h = 1600, 1000
        return app


def _frames(app, n):
    for _ in range(n):
        app.frame(1 / 60.0)


def _play_to_boundary(app, wave):
    from kit import buildable_near
    from lindefense.sim.vec import Vec
    g = app.get_game()
    g.add_cash(5000, None)
    if not g.get_tower_manager().get_towers():
        g.place_tower(TowerType.GEMINI, buildable_near(g, g.get_map().get_routes()[0].position_at(300).add(Vec(0, -60)), 150))
    while not (g.get_last_completed_wave() >= wave and not g.get_wave_manager().is_wave_active()):
        if g.get_wave_manager().can_start_next_wave():
            g.start_next_wave()
        app.frame(0.1)


def test_app_autosaves_continues_and_deletes_on_defeat(check, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    app = _HeadlessApp.make(monkeypatch)
    slot = savegame.slot()
    app.start_game(1)
    g = app.get_game()
    check(not slot.exists(), "a new run starts without a save")
    g.set_speed(3)
    _play_to_boundary(app, 2)
    info = slot.peek()
    check(info is not None and info.wave == 2 and not info.mid_wave, "autosaved when wave 2 was cleared (%s)" % (info and info.label()))
    g.start_next_wave()
    _frames(app, 120)
    tick, cash = g.get_tick(), g.get_cash()
    app.show_menu()
    info = slot.peek()
    check(info is not None and info.mid_wave and info.wave == 3, "quitting mid-wave saves the current state")
    check(app.menu.continue_button is not None, "the menu offers CONTINUE")
    app.continue_run()
    h = app.get_game()
    check(h is not None and h is not g and h.get_tick() == tick and h.get_cash() == cash,
          "CONTINUE restores the run (tick %s cash %s)" % (h and h.get_tick(), h and h.get_cash()))
    check(h.is_paused(), "a mid-wave save opens paused")
    _frames(app, 3)
    world = app.game_screen.world
    check(len(world.tower_sprites) == len(h.get_tower_manager().get_towers()) > 0, "every restored tower has a sprite")
    h.set_paused(False)
    h._lives = 1
    h.set_invincible(False)
    while h._defeat_timer < 0 and h.get_state() is State.PLAYING:
        app.frame(0.1)
    check(not slot.exists(), "the save is deleted as soon as the run is lost")
    app.show_menu()
    check(not slot.exists() and app.menu.continue_button is None, "nothing to continue after a defeat")


def test_app_victory_new_run_tutorial_and_reverse(check, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    app = _HeadlessApp.make(monkeypatch)
    slot = savegame.slot()
    app.start_game(0)
    _play_to_boundary(app, 1)
    check(slot.exists(), "autosaved after wave 1")
    app.start_tutorial()
    check(slot.exists(), "starting the tutorial keeps the saved run")
    _frames(app, 30)
    app.show_menu()
    check(slot.peek().map_index == 0 and slot.peek().wave == 1, "the tutorial never overwrites the save")
    app.start_reverse(1)
    _frames(app, 120)
    app.show_map_select()
    check(slot.peek().map_index == 0, "reverse mode neither saves nor deletes")
    app.continue_run()
    g = app.get_game()
    check(g.get_wave() == 1 and not g.is_paused(), "a boundary save opens unpaused")
    g._victory_timer = 0.2
    _frames(app, 30)
    check(g.get_state() is State.VICTORY and not slot.exists(), "victory deletes the save")
    app.start_game(3)
    _play_to_boundary(app, 1)
    check(slot.peek().map_index == 3, "saved on map 3")
    app.restart_level()
    check(not slot.exists(), "RESTART starts a new run: the save is gone")
    app.show_menu()
    check(not slot.exists(), "a run with nothing played is not saved")


def test_quit_during_palantir_takeover_keeps_the_boundary_save(check, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    app = _HeadlessApp.make(monkeypatch)
    app.start_game(0)
    _play_to_boundary(app, 1)
    g = app.get_game()
    g.start_next_wave()
    _frames(app, 120)

    class _Owner:
        def is_alive(self):
            return True

        def has_leaked(self):
            return False
    g.get_window_link().request_grab(_Owner())
    check(not savegame.mid_wave_safe(g), "a takeover in progress is not saved mid-wave")
    app.show_menu()
    info = savegame.slot().peek()
    check(info.wave == 1 and not info.mid_wave, "the last wave-boundary save is kept (%s)" % info.label())


def test_failed_continue_reports_once(check, monkeypatch):
    app = _HeadlessApp.make(monkeypatch)
    app.show_menu()
    _write(savegame.slot().path(), savegame.MAGIC + b"{}\n")   # appeared after the menu was built
    app.continue_run()
    check(app.get_game() is None and app.menu is not None, "back on the main menu")
    check(app.menu.notice.get_label() == savegame.LOAD_FAILED_TEXT, "the failure is shown")
    check(not savegame.slot().exists(), "the bad save is deleted")
    app.show_menu()
    check(app.menu.notice.get_label() == "", "and not shown again")


def test_save_label_and_quit_confirm_text(check, monkeypatch):
    from lindefense.ui.game_screen import GameScreen
    monkeypatch.setenv("LINDEFENSE_VARIANCE", "off")
    app = _HeadlessApp.make(monkeypatch)
    app.start_game(5)
    gs = app.game_screen
    gs.open_menu()
    gs.set_confirm(GameScreen.Confirm.QUIT)
    texts = [o.get_label() for o in gs.overlay if hasattr(o, "get_label")]
    check(any("Progress will be lost" in t for t in texts) and not any("saved" in t for t in texts),
          "a match nothing happened in yet is not kept, so QUIT LEVEL does not promise a save (%s)" % texts)
    app.get_game().start_next_wave()
    gs.set_confirm(GameScreen.Confirm.QUIT)
    texts = [o.get_label() for o in gs.overlay if hasattr(o, "get_label")]
    check(any("Your run is saved" in t for t in texts), "QUIT LEVEL says the run is kept (%s)" % texts)
    app.start_tutorial()
    gs = app.game_screen
    gs.open_menu()
    gs.set_confirm(GameScreen.Confirm.QUIT)
    texts = [o.get_label() for o in gs.overlay if hasattr(o, "get_label")]
    check(any("Progress will be lost" in t for t in texts), "the tutorial's QUIT LEVEL still warns")


def test_continue_brings_back_the_ui_state(check, monkeypatch):
    """The restored match drives every view: Patch Notes draft overlay, deployed hero (Hero Store), targeting,
    unlocked ability in the ability bar, speed, auto-start."""
    from kit import force_place, buildable_near
    from lindefense.tower.tower_type import Targeting
    app = _HeadlessApp.make(monkeypatch)
    g = Game(maps.create(0), 21, Difficulty.ON)
    g.set_hero_collection(HeroCollection.persistent())
    g.get_variance().enable(Picker.PLAYER)
    r = g.get_map().get_routes()[0]
    hero = force_place(g, TowerType.SPEAR_HANBO, buildable_near(g, r.position_at(250), 150), 1)
    g.mark_hero_deployed(TowerType.SPEAR_HANBO)
    gpt = force_place(g, TowerType.GPT, buildable_near(g, r.position_at(700), 150), 3)
    check(g.get_tower_manager().unlock_ability(gpt), "ability unlocked")
    gpt.set_targeting(Targeting.STRONGEST)
    g.set_speed(2)
    g.get_wave_manager().set_auto_start(True)
    key_before = (g.is_hero_deployed(TowerType.SPEAR_HANBO), g.get_tower_manager().heroes_deployed_this_match(), g.get_cash())
    savegame.slot().save(g)
    app.show_menu()
    check(app.menu.continue_button is not None, "CONTINUE offered")
    app.continue_run()
    _frames(app, 3)
    h = app.get_game()
    gs = app.game_screen
    check(gs.is_draft_open() and h.get_variance().is_draft_pending(), "the pending Patch Notes draft is back on screen")
    check((h.is_hero_deployed(TowerType.SPEAR_HANBO), h.get_tower_manager().heroes_deployed_this_match(), h.get_cash()) == key_before,
          "hero deployment and cash restored")
    towers = {t.get_type(): t for t in h.get_tower_manager().get_towers()}
    check(towers[TowerType.GPT].get_targeting() is Targeting.STRONGEST and towers[TowerType.GPT].get_tier() == 3
          and not towers[TowerType.GPT].is_ability_locked(), "tier, targeting and unlocked ability restored")
    check(towers[TowerType.SPEAR_HANBO].get_tier() == 1, "the hero's level restored")
    check(any(s.tower is towers[TowerType.GPT] for s in gs.abilities.slots), "the ability bar shows the GPT ability")
    check(h.get_speed() == 2 and h.get_wave_manager().is_auto_start(), "speed and auto-start restored")
    gs.pick_patch_note(0)
    _frames(app, 2)
    check(not gs.is_draft_open() and len(h.get_variance().get_active()) == 1, "the draft can be completed after loading")
    gs.toggle_hero_store()
    _frames(app, 2)
    check(gs.is_hero_store_open() and gs.hero_store_state_key()[0:2] != "", "the Hero Store opens on the restored run")
