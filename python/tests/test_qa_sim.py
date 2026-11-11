"""Cross-feature regressions found by the integration QA pass (simulation, persistence, determinism): records with
Freeplay continuations and saved runs, save-format compatibility, boss abilities against tower mechanics, deep
Freeplay. Every test writes only to temp folders."""
import os

import pytest

from lindefense import prefs
from lindefense.sim import records as R
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.misc import AdminMode, HeroCollection
from lindefense.sim.records import Records, RunSession, RunSummary


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path / "prefs"))
    prefs._nodes.clear()
    Records._shared = None
    shared = HeroCollection._shared
    HeroCollection._shared = None
    AdminMode._unlocked, AdminMode._options = None, {}
    yield
    prefs._nodes.clear()
    Records._shared = None
    HeroCollection._shared = shared
    AdminMode._unlocked, AdminMode._options = None, {}


def _summary(**kw):
    base = dict(map_name="The Silicon Circuit", map_index=0, difficulty="O1", seed=5, result=R.VICTORY, wave=100,
                waves_cleared=100, kills=2500, play_time=1000.0)
    base.update(kw)
    return RunSummary(**base)


# ====================================================================== records x freeplay x save
def test_freeplay_live_achievements_count_only_what_happened_since_the_victory(check):
    """The campaign victory is already in the career totals: a Freeplay continuation's live check (toasts) must add
    only the kills / waves since then, like Records.extend does at the end, or career achievements pop early."""
    recs = Records.in_memory({"career": {"enemies_killed": 97000, "waves_cleared": 800}})
    won = _summary()
    recs.record(won)
    check(recs.career()["enemies_killed"] == 99500 and not recs.is_unlocked("kills_100k"), "the win is folded in")
    later = _summary(result=R.ABANDONED, wave=102, waves_cleared=101, kills=2510, play_time=1100.0)
    live = [a.id for a in recs.pending_live(later, (), won)]
    check("kills_100k" not in live, "no 100k-kills toast at 99,510 career kills (%s)" % live)
    s = RunSession(recs, None)       # the session of the won run, reopened by CONTINUE - FREEPLAY
    s._recorded = won
    s.summary = lambda result=None: later
    toasts = [a.id for a in s.tick(1.0)]
    check("kills_100k" not in toasts, "the reopened session's toasts use the baseline (%s)" % toasts)
    much_later = _summary(result=R.ABANDONED, wave=130, waves_cleared=129, kills=3000)
    check("kills_100k" in [a.id for a in recs.pending_live(much_later, (), won)], "the toast comes once it is earned")
    rep = recs.extend(won, much_later)
    check(recs.is_unlocked("kills_100k") and recs.career()["enemies_killed"] == 100000,
          "and the end of freeplay agrees (%s)" % recs.career()["enemies_killed"])
    check(rep.counted, "the extension is counted")


def test_heroes_bought_during_freeplay_count_for_the_roster(check):
    recs = Records.in_memory()
    won = _summary(heroes_bought=["SPEAR_HANBO"])
    recs.record(won)
    later = _summary(result=R.ABANDONED, wave=104, waves_cleared=103, kills=2600, heroes_bought=["SPEAR_HANBO", "MR_LINDEMANN"])
    recs.extend(won, later)
    check(recs.heroes_bought() == {"SPEAR_HANBO", "MR_LINDEMANN"}, "a hero bought in freeplay is recorded (%s)" % recs.heroes_bought())


def test_play_time_survives_save_and_continue(check, tmp_path):
    """RunSession's play time travels with the saved Game, so a run continued later (or recorded when its save is
    replaced) keeps the time played before the save; Freeplay's extension then adds the right amount."""
    from lindefense import savegame
    from lindefense.map import maps
    from lindefense.sim.game import Game
    recs = Records.in_memory()
    g = Game(maps.create(0), 77, Difficulty.O1)
    g.start_next_wave()
    s = RunSession(recs, g)
    for _ in range(600):
        s.tick(0.5, True)
    check(abs(s.play_time - 300.0) < 1e-6, "300 s played")
    slot = savegame.SaveSlot(str(tmp_path / "slot.bin"))
    slot.save(g)
    s.cancel()
    h = slot.load()
    s2 = RunSession(recs, h)
    check(abs(s2.play_time - 300.0) < 1e-6, "the continued session starts at the saved play time (%s)" % s2.play_time)
    s2.tick(20.0, True)
    s2.finish()
    check(abs(recs.career()["play_time"] - 320.0) < 1e-6, "career play time counts both sessions (%s)" % recs.career()["play_time"])
    g3 = Game.fresh_copy(h)
    check(RunSession(recs, g3).play_time == 0.0, "a new run (RESTART) starts from zero")
    # Freeplay: the campaign victory was recorded at 320 s; 40 s of freeplay before a save, 10 s after it
    fp = Game(maps.create(0), 78, Difficulty.O1)
    fp.start_next_wave()
    s3 = RunSession(recs, fp)
    s3.tick(320.0, True)
    s3.finish()                                   # the "victory" (abandoned here; the baseline is what matters)
    before = recs.career()["play_time"]
    s3.reopen()
    s3.tick(40.0, True)
    slot.save(fp)
    s3.cancel()
    s4 = RunSession(recs, slot.load())
    s4.tick(10.0, True)
    s4.finish()
    check(abs(recs.career()["play_time"] - before - 50.0) < 1e-6,
          "the freeplay extension adds the time before and after the save (%s)" % (recs.career()["play_time"] - before))


# ====================================================================== save format compatibility
def _header(data):
    import json
    from lindefense import savegame
    nl = data.index(b"\n", len(savegame.MAGIC))
    return json.loads(data[len(savegame.MAGIC):nl]), nl


def _boss_game():
    from lindefense.tools.perf_bench import PerfBench
    g = PerfBench.late_game(0, Difficulty.ON, 6, 40)
    g.start_next_wave()          # wave 40: Bellarmine College Prep and its Crest Shield
    g.run(60 * 8)
    return g


def test_saves_from_builds_with_other_simulation_classes_are_refused(check, monkeypatch):
    """Pickle restores fields as saved whatever the class looks like now: a save written before the balance /
    challenge merge (same version label, format 1) loaded, then died on the first step (Game has no
    _challenge_damage). Format 1 is refused, and the header's class fingerprints refuse any save whose classes
    changed since, instead of loading it into the new code."""
    import json
    from lindefense import savegame
    from lindefense.enemy.boss import Boss
    from lindefense.sim.game import Game
    g = _boss_game()
    check(any(isinstance(e, Boss) for e in g.get_enemy_manager().get_enemies()), "a boss is on the track")
    data = savegame.encode(g)
    header, nl = _header(data)
    check(savegame.FORMAT >= 2 and header["format"] == savegame.FORMAT, "format 2 or later")
    names = header["classes"]
    check("lindefense.sim.game:Game" in names and "lindefense.enemy.boss:Boss" in names
          and "lindefense.enemy.boss_abilities:CrestShield" in names, "the header fingerprints the saved classes")
    _, h = savegame.decode(data)
    check(h.get_wave() == 40, "an unchanged build loads its own save")

    def refused(blob, why):
        with pytest.raises(savegame.SaveError) as e:
            savegame.validate(blob)
        check(True, why)
        return str(e.value)

    old = dict(header, format=1)
    old.pop("classes")
    refused(savegame.MAGIC + json.dumps(old).encode() + data[nl:], "a format 1 save (no fingerprints) is refused")
    tampered = dict(header, classes=dict(names, **{"lindefense.enemy.boss:Boss": "0" * 24}))
    msg = refused(savegame.MAGIC + json.dumps(tampered).encode() + data[nl:], "a changed class is refused")
    check("Boss" in msg, "the error names the class (%s)" % msg)
    gone = dict(header, classes=dict(names, **{"lindefense.enemy.boss:NoSuchBoss": "0" * 24}))
    refused(savegame.MAGIC + json.dumps(gone).encode() + data[nl:], "a class that no longer exists is refused")
    # the real thing: a simulation class gains a method / field after the run was saved
    monkeypatch.setattr(Game, "_qa_new_rule", lambda self: 1.0, raising=False)
    savegame._CLASS_HASHES.clear()
    try:
        refused(data, "a save made before Game changed is refused")
    finally:
        monkeypatch.undo()
        savegame._CLASS_HASHES.clear()
    check(savegame.validate(data) is not None, "and accepted again once the code matches")


# ====================================================================== Palantir's escorts x the victory sequence x records
def test_nothing_leaks_after_palantir_falls(check):
    """Palantir's death stuns everything for the victory sequence, but bosses ignored that stun: its escort squadron
    (Fortified MOABs launched from the entrance) kept flying for 5 s with no tower firing and leaked, costing 90
    lives and the run's Zero Leaks / Most Lives records after the campaign was already won. Escorts now freeze too,
    and nothing that still reaches the exit during the sequence (a late child, a contractor) costs lives or counts."""
    from kit import kill_outright, new_game, ticks
    from lindefense.enemy.types import EnemyType
    from lindefense.sim.game import Game, State
    g = new_game(0)
    for _ in range(1, 100):
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    g.start_next_wave()
    g.run(ticks(9))
    p = g.get_palantir()
    p.take_damage(p.get_max_hp() * 0.31, g.get_time())
    g.run(2)
    escorts = p.get_protocols().get_escorts()
    check(len(escorts) == 3 and p.get_phase() == 1, "phase 2 launched the escort squadron (%d)" % len(escorts))
    r = g.get_map().get_routes()[p.get_route_index()]
    for e in escorts:
        e.set_distance(r.get_total_length() - 150)     # the squadron has flown most of the route
    kill_outright(g, p)
    check(g.is_campaign_won() and g.is_victory_sequence_active(), "the victory sequence runs")
    at = [e.get_distance() for e in escorts]
    late = g.get_enemy_manager().spawn(EnemyType.SINGLY_LINKED_LIST, None, p.get_route_index(), r.get_total_length() - 40)
    g.run(ticks(Game.VICTORY_SEQUENCE_TIME) + 5)
    check(g.get_state() is State.VICTORY, "won")
    check(g.get_last_completed_wave() == 100, "wave 100 counts as cleared once Palantir is down (records, daily best, "
          "end screen; was %d)" % g.get_last_completed_wave())
    check([e.get_distance() for e in escorts] == at, "the escorts froze where they were")
    check(g.get_lives() == 100 and g.get_enemy_manager().get_total_leaked() == 0,
          "no lives lost, no leak counted (lives %d, leaks %d)" % (g.get_lives(), g.get_enemy_manager().get_total_leaked()))
    check(not late.is_alive() and not late.has_leaked(), "an enemy reaching the exit after the win just leaves")
    check(g.continue_freeplay() and not g.is_campaign_won(), "freeplay resumes normal play")
    e = g.get_enemy_manager().spawn(EnemyType.SINGLY_LINKED_LIST, None, 0, g.get_map().get_routes()[0].get_total_length() - 5)
    g.run(30)
    check(e.has_leaked() and g.get_lives() < 100, "in freeplay leaks cost lives again")


# ====================================================================== deep Freeplay numbers and Patch Notes on screen
def test_huge_health_figures_stay_short_and_true(check):
    """Freeplay health grows x1.06 a wave without bound (1e27 by wave 1000): the boss dock printed
    "15663193082331290000B" over its neighbours' bars and the side panel a saturated 64-bit 9,223,372,036,854,775,807."""
    from lindefense.ui.cyber import Cyber
    check(Cyber.abbrev(38.3e9) == "38B" and Cyber.abbrev(1.26e12) == "1.3T" and Cyber.abbrev(640) == "640", "short forms")
    check(Cyber.abbrev(1.5663e28) == "1.6e28" and Cyber.abbrev(1.13e132) == "1.1e132", "scientific past 999T")
    check(Cyber.amount(38295480666) == "38,295,480,666" and Cyber.amount(0.2) == "1", "full figures while they fit")
    check(Cyber.amount(1.98e28) == "2e28", "abbreviated, not saturated, beyond (%s)" % Cyber.amount(1.98e28))


def test_patch_note_chips_fit_the_run_strip(check):
    """Freeplay drafts a Patch Note every 20 waves forever; the strip laid every chip in one row, so by wave ~200 they
    ran under the news feed and past the playfield into the side panel."""
    from kit import new_game
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.run_strip import RunStrip
    from lindefense.ui.ui import Ui
    from lindefense.variance.variance import PatchNote
    g = new_game(0)
    g.get_variance().enable()
    for p in list(PatchNote)[:18]:
        g.get_variance().grant(p)
    s = GameScreen(None, g)
    s.frame(0.05)
    strip = s.strip
    end = max(b[0] + b[1] for b in strip.chip_boxes)
    check(end <= Ui.WORLD_W - RunStrip.QUIET_W, "the chips end before the news feed (%s)" % end)
    shown = len(strip.chip_boxes)
    texts = [strip.chips.get_element(i).get_label() for i in range(strip.chips.get_element_count())
             if hasattr(strip.chips.get_element(i), "get_label")]
    check(0 < shown < 18 and ("+%d" % (18 - shown)) in texts, "the rest are counted (%d shown, %s)" % (shown, texts[-1:]))
    g2 = new_game(0)
    g2.get_variance().enable()
    for p in list(PatchNote)[:5]:
        g2.get_variance().grant(p)
    s2 = GameScreen(None, g2)
    s2.frame(0.05)
    check(len(s2.strip.chip_boxes) == 5, "a campaign's five notes are all shown")


def test_daily_best_ignores_admin_runs(check):
    """The career records exclude admin-mode runs; the daily run's saved best wave counted them."""
    from lindefense.sim.run_setup import DailyRecords, DailyRun
    store = DailyRecords.in_memory()
    d = DailyRun("2026-11-10")
    g = d.setup().create_game(HeroCollection.in_memory(), (False, True, False))
    g._last_completed_wave = 37
    check(not store.note(g) and store.best(d.date) == 0, "an admin daily run records no best")
    h = d.setup().create_game(HeroCollection.in_memory())
    h._last_completed_wave = 12
    check(store.note(h) and store.best(d.date) == 12, "a normal one does")


def test_records_screen_survives_a_damaged_history(check):
    """A records file that parses but holds a mistyped history row ("wave": "abc", "notes": 7, Infinity) crashed the
    RECORDS screen's HISTORY tab; rows are now cleaned on load like the rest of the document."""
    import skia
    from lindefense.ui.jawt import Graphics2D, reset_canvas_state
    from lindefense.ui.stats_screen import StatsScreen, Tab
    inf = float("inf")
    recs = Records.in_memory({
        "history": [{"wave": "abc", "map": None, "difficulty": 5, "seed": "x", "result": 3, "tags": "daily:2026",
                     "notes": 7, "time": "t", "kills": None, "date": 12, "map_index": "z", "notes_on": "yes"},
                    {"wave": inf, "time": -inf, "kills": inf, "seed": 77, "map": "The Silicon Circuit", "difficulty": "O1",
                     "notes": ["OPEN_SOURCE", 3], "tags": ["custom-seed"]}],
        "career": {"play_time": inf, "best_wave": inf, "runs": 2}})
    h = recs.history()
    check("wave" not in h[0] and "seed" not in h[0] and h[0]["notes"] == [] and h[0]["tags"] == [] and h[0]["notes_on"] is False,
          "mistyped fields are dropped (%s)" % h[0])
    check("wave" not in h[1] and h[1]["seed"] == 77 and h[1]["notes"] == ["OPEN_SOURCE"], "infinities too, the rest is kept")
    check(recs.career()["play_time"] == 0 and recs.career()["runs"] == 2, "career numbers must be finite")
    for tab in Tab.values():
        s = StatsScreen(lambda: None, lambda *a: None, recs)
        s.set_tab(tab)
        surf = skia.Surface.MakeRasterN32Premul(400, 250)
        reset_canvas_state(surf.getCanvas())
        g = Graphics2D(surf.getCanvas())
        g.scale(0.25, 0.25)
        s.paint(g)
        check(True, "the %s tab paints" % tab.name)


# ====================================================================== save fidelity with the new content
def _rich_digest(g):
    """test_savegame's per-step digest plus the boss-ability / Palantir-protocol state, challenge flags and Frugal's
    unpaid-cost table."""
    import hashlib
    from test_savegame import digest
    from lindefense.enemy.boss import Boss
    h = hashlib.blake2b(digest(g), digest_size=12)
    for e in g.get_enemy_manager().get_enemies():
        if isinstance(e, Boss):
            for part in (e.get_ability(), e.get_protocols()):
                if part is not None:
                    h.update(repr(sorted((k, v if isinstance(v, (int, float, bool)) else len(v))
                                         for k, v in vars(part).items() if isinstance(v, (int, float, bool, list)))).encode())
            h.update(b"p%d" % e.get_phase())
    h.update(repr((g.get_challenges(), g.run_tags, g.get_hero_limit(), g.get_price_multiplier(), g.is_selling_locked(),
                   g.get_max_lives(), g.is_seed_fixed(), g.is_freeplay(), sorted(g.get_variance()._unpaid.items()),
                   g.get_window_link().get_fraction())).encode())
    return h.digest()


def _continues_identically(check, name, g, drive, frames, take):
    """Plays g for `frames`, snapshotting when take(g, f); every snapshot, loaded, must replay the same steps."""
    from lindefense import savegame
    trace, snaps = {}, []
    for f in range(frames):
        if take(g, f):
            snaps.append((f, savegame.dumps(g)))
        drive(g, f)
        trace[f] = _rich_digest(g)
    for f0, payload in snaps:
        h = savegame.loads(payload)
        bad = [f for f in range(f0, frames) if (drive(h, f), trace[f] != _rich_digest(h))[1]]
        check(not bad, "%s: saved at frame %d, %d of %d steps differ" % (name, f0, len(bad), frames - f0))
    return snaps


def test_runs_with_boss_abilities_continue_bit_identically(check):
    """Crest Shield up, Outsourcing mid-timer, Network Hub linking, Afterburner burning: saved mid-ability, continued."""
    from lindefense.enemy.boss import Boss
    from lindefense.enemy.boss_abilities import Afterburner, CrestShield, NetworkHub, Outsourcing
    from lindefense.enemy.types import EnemyType as E, Modifier
    from lindefense.jenum import EnumSet
    from lindefense.sim.game import Game
    from lindefense.tools.perf_bench import PerfBench
    g = PerfBench.late_game(3, Difficulty.ON2, 12, 95)
    g.start_next_wave()
    for i, t in enumerate((E.BELLARMINE_COLLEGE_PREP, E.SW_RESOURCE_CONSULTANT, E.THREE_COM, E.LOCKHEED_MARTIN)):
        g.get_enemy_manager().spawn_scaled(t, EnumSet([Modifier.FORTIFIED]) if i % 2 == 0 else None, i % 2, 60.0 * i, 40.0, 1.0)
    PerfBench.spawn_crowd(g, 20, 0)

    def bosses(g):
        return [e for e in g.get_enemy_manager().get_enemies() if isinstance(e, Boss) and e.is_alive()]

    def drive(g, f):
        if f % 60 == 0:
            PerfBench.fire_abilities(g)
        if f % 90 == 45:
            for b in bosses(g):
                b.take_damage(b.get_max_hp() * 0.2, g.get_time())
        g.step(Game.DT)
        g.get_events().clear()

    def take(g, f):
        ab = [b.get_ability() for b in bosses(g)]
        return f in (100, 260, 420) or any(isinstance(a, CrestShield) and a.is_up() for a in ab) and f % 97 == 0

    seen = set()

    def watch(g, f):
        for b in bosses(g):
            a = b.get_ability()
            if isinstance(a, CrestShield) and a.is_up():
                seen.add("shield")
            if isinstance(a, Outsourcing) and a.get_spawned():
                seen.add("outsourced")
            if isinstance(a, NetworkHub) and a.get_linked():
                seen.add("hub")
            if isinstance(a, Afterburner) and a.is_burning():
                seen.add("burn")
        drive(g, f)
    snaps = _continues_identically(check, "bosses", g, watch, 600, take)
    check(len(snaps) >= 3 and seen == {"shield", "outsourced", "hub", "burn"}, "every ability was live (%s, %d saves)" % (sorted(seen), len(snaps)))


def test_freeplay_palantir_continues_bit_identically(check):
    """Freeplay wave 125's rebuilt Palantir through its phases (escorts from the entrance, Swarm Uplink, holograms,
    kill switch, window seal, surveillance), saved at several points and continued."""
    from lindefense.enemy.boss import Boss
    from lindefense.sim.game import Game, State
    from lindefense.tools.perf_bench import PerfBench
    from lindefense.variance.variance import Picker
    g = PerfBench.late_game(1, Difficulty.ON, 30, 1)
    g.get_variance().enable(Picker.RANDOM)
    wm = g.get_wave_manager()
    while g.get_wave() < 100:
        wm.start_next_wave()
        wm.end_wave()
    g._last_completed_wave, g._state = 100, State.VICTORY
    check(g.continue_freeplay(), "freeplay")
    while g.get_wave() < 124:
        wm.start_next_wave()
        wm.end_wave()
    g.set_invincible(False)
    g._lives = 10 ** 6
    check(wm.start_next_wave() and wm.get_current_def().contains_boss(), "wave 125 starts")
    seen = set()

    def drive(g, f):
        if f % 60 == 0:
            PerfBench.fire_abilities(g)
        wl = g.get_window_link()
        if wl.consume_grab_requests():
            wl.set_fraction(0.5)
        if f % 300 == 299:
            wl.set_fraction(1.0)
        p = g.get_palantir()
        if p is not None and p.is_alive():
            if f % 150 == 75:
                p.take_damage(p.get_max_hp() * 0.18, g.get_time())
            pr = p.get_protocols()
            seen.update(k for k, v in (("phase%d" % p.get_phase(), True), ("escorts", pr.get_escorts()),
                                       ("uplink", pr.get_uplinks()), ("decoys", pr.get_decoys()), ("sealed", pr.is_sealed()),
                                       ("kill switch", pr.is_kill_switch_used())) if v)
        g.step(Game.DT)
        g.get_events().clear()
    snaps = _continues_identically(check, "freeplay palantir", g, drive, 1500, lambda g, f: f % 300 == 299)
    check({"phase0", "phase1", "phase2", "escorts", "uplink", "decoys", "sealed", "kill switch"} <= seen,
          "the fight went through every phase (%s)" % sorted(seen))
    check(len(snaps) == 5, "five saves")


def test_challenge_and_daily_runs_continue_bit_identically(check):
    """Challenge flags, run tags, the fixed seed, Frugal's unpaid-cost table, the hero limit and lives survive a save,
    and the run continues exactly (a daily run and a run with every rule)."""
    import test_savegame as T
    from lindefense.sim.challenges import Challenge as C
    from lindefense.sim.run_setup import DailyRun, RunSetup
    from lindefense import savegame
    for name, setup in (("daily", DailyRun("2026-11-11").setup()),
                        ("all rules", RunSetup(4, Difficulty.ON2, 4242, tuple(C), True))):
        g = setup.create_game(HeroCollection.in_memory())
        for x in T.HEROES:
            g.get_hero_collection().unlock(x)
        ai = T.new_player(g)
        trace, snaps = {}, []
        while not T.finished(g, 5):
            if g.get_tick() % 700 == 350:
                snaps.append((g.get_tick(), savegame.encode(g), T.memory_of(ai)))
            T.act_and_step(g, ai, 5)
            trace[g.get_tick()] = _rich_digest(g)
        check(len(snaps) >= 3, "%s: saves taken" % name)
        for tick, data, memory in snaps:
            h = savegame.decode(data)[1]
            check((h.get_challenges(), h.run_tags, h.get_daily_date(), h.is_seed_fixed()) ==
                  (g.get_challenges(), g.run_tags, g.get_daily_date(), g.is_seed_fixed()), "%s: the run setup is restored" % name)
            hai = T.new_player(h, memory)
            bad = 0
            while not T.finished(h, 5):
                T.act_and_step(h, hai, 5)
                bad += trace.get(h.get_tick()) != _rich_digest(h)
            check(bad == 0, "%s: saved at tick %d, %d steps differ" % (name, tick, bad))


def test_a_palantir_hologram_reaching_the_exit_is_not_a_leak(check):
    """Holograms cost no lives, but one that reached the exit still counted as a leak, so a run that never lost a life
    missed Zero Leaks (and its records showed leaks)."""
    from kit import new_game
    from lindefense.enemy.types import EnemyType
    g = new_game(0)
    r = g.get_map().get_routes()[0]
    h = g.get_enemy_manager().spawn_scaled(EnemyType.PALANTIR_HOLOGRAM, None, 0, r.get_total_length() - 3, 1.0, 1.0)
    g.run(60)
    check(not h.is_alive() and g.get_enemy_manager().get_total_leaked() == 0 and g.get_lives() == 100,
          "it just vanishes (leaks %d)" % g.get_enemy_manager().get_total_leaked())
    e = g.get_enemy_manager().spawn(EnemyType.PRIMITIVE_VARIABLE, None, 0, r.get_total_length() - 3)
    g.run(60)
    check(e.has_leaked() and g.get_enemy_manager().get_total_leaked() == 1, "a real enemy still leaks")


def test_daily_retry_and_replay_only_count_as_that_daily_on_its_own_date(check):
    """RETRY / REPLAY SEED from a daily run's end screen kept the "daily:<date>" tag, so a replay played on a later
    date raised that old date's daily best. A replay (or a restart on another day) is a chosen-seed run with the same
    rule; a restart on the same day is still the daily."""
    from lindefense.sim.game import Game
    from lindefense.sim.run_setup import DailyRecords, DailyRun
    d = DailyRun("2026-11-10")
    g = d.setup().create_game(HeroCollection.in_memory())
    check(g.get_daily_date() == "2026-11-10", "a daily run")
    same_day = Game.fresh_copy(g, today="2026-11-10")
    check(same_day.get_daily_date() == "2026-11-10" and same_day.get_seed() == d.seed, "RETRY that day: still the daily")
    later = Game.fresh_copy(g, today="2026-11-11")
    replay = Game.fresh_copy(g, g.get_seed(), today="2026-11-10")
    store = DailyRecords.in_memory()
    for name, x in (("RETRY a day later", later), ("REPLAY SEED", replay)):
        check(x.get_daily_date() is None and "custom-seed" in x.run_tags and x.get_seed() == d.seed and x.is_seed_fixed()
              and x.get_challenges() == d.challenges, "%s: a chosen-seed run with the day's rule (%s)" % (name, x.run_tags))
        x._last_completed_wave = 50
        check(not store.note(x) and store.best(d.date) == 0, "%s: the daily best is untouched" % name)


def test_freeplay_live_check_long_running_process(check):
    """The UI-flow repro: career at 950 waves, a won campaign (100) and freeplay wave 101 toasted Long-Running Process,
    which then stayed locked at 1051."""
    recs = Records.in_memory({"career": {"waves_cleared": 850}})
    won = _summary()
    recs.record(won)
    check(recs.career()["waves_cleared"] == 950 and not recs.is_unlocked("waves_1000"), "950 waves cleared")
    later = _summary(result=R.ABANDONED, wave=102, waves_cleared=101, kills=2600)
    check("waves_1000" not in [a.id for a in recs.pending_live(later, (), won)], "no toast at 951")
    recs.extend(won, later)
    check(recs.career()["waves_cleared"] == 951 and not recs.is_unlocked("waves_1000"), "and none unlocked")
