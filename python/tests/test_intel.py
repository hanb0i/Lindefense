"""Player intel: next-wave preview (types, counts, modifiers after difficulty / Patch Notes shaping), threat warnings,
upgrade stat deltas against the real upgraded tower, the damage readout, and that none of it touches the simulation."""
import hashlib
import struct

import pytest
import skia

from kit import buildable_near, force_place, new_game
from lindefense import prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType as E, Modifier
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower import Tower
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui import intel
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.hero_stat_text import HeroStatText
from lindefense.ui.intel import Threat
from lindefense.ui.jawt import Graphics2D, reset_canvas_state
from lindefense.ui.next_wave_panel import EnemyIconImage
from lindefense.ui.side_panel import SidePanel
from lindefense.ui.ui import Ui
from lindefense.variance.variance import BreakingNews, PatchNote, Picker
from lindefense.wave import waves


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


def _game(diff=Difficulty.O1, map_idx=0, seed=42):
    return Game(maps.create(map_idx), seed, diff)


def _at(g, n):
    """Pretend the waves before n are done (the next wave is n)."""
    g.get_wave_manager()._current_wave = n - 1


def _counts(d):
    """{type: count} and {modifier: count} of a WaveDef, innate camo counted as camo."""
    by_type, by_mod = {}, {}
    for gr in d.groups:
        by_type[gr.type] = by_type.get(gr.type, 0) + gr.count
        mods = set(gr.modifiers)
        if gr.type.has_innate_camo():
            mods.add(Modifier.CAMO)
        for m in mods:
            by_mod[m] = by_mod.get(m, 0) + gr.count
    return by_type, by_mod


def _matches(check, pv, d, what):
    by_type, by_mod = _counts(d)
    check(pv.total == d.total_spawns(), "%s: total %d == %d" % (what, pv.total, d.total_spawns()))
    check({g.type: g.count for g in pv.groups} == by_type, "%s: per-type counts %s" % (what, [g.key() for g in pv.groups]))
    check(pv.modifiers == by_mod, "%s: modifier counts %s == %s" % (what, pv.modifiers, by_mod))


# ---------------------------------------------------------------- preview contents
def test_preview_known_waves(check):
    g = _game()
    p1 = intel.preview(g)
    check(p1.number == 1 and p1.total == 10 and p1.count_of(E.PRIMITIVE_VARIABLE) == 10 and len(p1.groups) == 1,
          "wave 1: 10 Primitive Variables (%s)" % [x.key() for x in p1.groups])
    check(not p1.forecast and not p1.modifiers and not p1.bosses, "wave 1: exact, no modifiers, no boss")
    p24 = intel.preview(g, 24)
    check(p24.count_of(E.PRIMITIVE_VARIABLE) == 20 and p24.count_of(E.STATIC_ARRAY) == 12, "wave 24 types and counts")
    check(p24.modifier_count(Modifier.CAMO) == 32 and p24.modifiers.keys() == {Modifier.CAMO}, "wave 24: 32 camo")
    p40 = intel.preview(g, 40)
    check(p40.total == 19 and p40.groups[0].type is E.BELLARMINE_COLLEGE_PREP and p40.groups[0].count == 1,
          "wave 40: the MOAB is listed first (%s)" % [x.key() for x in p40.groups])
    check(p40.count_of(E.QUICK_SORT) == 8 and p40.count_of(E.SHELL_SORT) == 10, "wave 40 escort")
    p90 = intel.preview(g, 90)
    check([x.type for x in p90.bosses] == [E.LOCKHEED_MARTIN, E.BELLARMINE_COLLEGE_PREP], "wave 90: the DDT heads the bosses")
    check(p90.modifier_count(Modifier.CAMO) == 42, "wave 90: 40 camo lists + 2 innately camo DDTs (%d)" % p90.modifier_count(Modifier.CAMO))
    check(sum(x.count for x in p90.lead) == 2, "wave 90: the DDTs are Lead-type")
    p30 = intel.preview(g, 30)
    check(p30.modifier_count(Modifier.INJECTION) == 1 and p30.modifier_count(Modifier.REGROW) == 10, "wave 30: one Prompt Injection carrier, 10 regrow")
    p31 = intel.preview(g, 31)
    check([x.type for x in p31.lead] == [E.RADIX_SORT], "wave 31: Radix Sort counts as Lead-type")
    check(p31.groups[0].type is E.DYNAMIC_ARRAY, "normal groups are listed biggest first")
    check(intel.preview(g, waves.WAVE_COUNT + 1) is None and intel.preview(g, 0) is None, "no preview past the last wave")
    for n in range(1, waves.WAVE_COUNT + 1):
        _matches(check, intel.preview(g, n), waves.get(n), "O(1) wave %d" % n)


@pytest.mark.parametrize("diff", [Difficulty.ON, Difficulty.ON2, Difficulty.ONN])
def test_preview_matches_shaped_waves(check, diff):
    """After difficulty shaping (elites, promotions, extra units) the preview lists exactly what the wave manager starts."""
    for n in (1, 14, 24, 28, 39, 40, 56, 74, 90, 99, 100):
        g = _game(diff, seed=1234 + n)
        _at(g, n)
        pv = intel.preview(g)
        check(g.get_wave_manager().start_next_wave(), "%s wave %d starts" % (diff, n))
        _matches(check, pv, g.get_wave_manager().get_current_def(), "%s wave %d" % (diff, n))
        check(not pv.forecast, "%s wave %d: exact" % (diff, n))
    g = _game(diff)
    check(intel.preview(g, 74).total > waves.get(74).total_spawns(), "%s adds enemies" % diff)


def test_preview_with_patch_notes_and_news(check):
    """Breaking News already rolled for the next wave is in the preview (and named); while the wave before is still
    running the next wave is a forecast; once that wave ends the preview matches what starts."""
    g = _game(Difficulty.ON)
    _at(g, 50)
    g.get_variance().enable(Picker.FIRST)
    g.get_variance().force_news(BreakingNews.HYPE_CYCLE, -1)
    pv = intel.preview(g)
    check(pv.news is BreakingNews.HYPE_CYCLE and not pv.forecast, "the next wave names its Breaking News")
    check(pv.total > g.get_difficulty().shape(waves.get(50), g.get_seed()).total_spawns(), "Hype Cycle adds enemies")
    g.get_wave_manager().start_next_wave()
    _matches(check, pv, g.get_wave_manager().get_current_def(), "Hype Cycle wave 50")

    g = _game(Difficulty.ON)
    _at(g, 49)
    g.get_variance().enable(Picker.FIRST)
    g.get_variance().force_news(BreakingNews.VIRAL_MEME, -1)
    pv = intel.preview(g)
    check(pv.modifier_count(Modifier.CAMO) == pv.total - sum(x.count for x in pv.bosses), "Viral Meme: every non-boss is camo")
    g.get_wave_manager().start_next_wave()
    _matches(check, pv, g.get_wave_manager().get_current_def(), "Viral Meme wave 49")
    nxt = intel.preview(g)
    check(nxt.number == 50 and nxt.forecast and nxt.news is None, "while wave 49 runs, wave 50 is a forecast")
    check(nxt.modifier_count(Modifier.CAMO) < nxt.total - len(nxt.bosses), "the forecast ignores wave 49's Viral Meme")
    v = g.get_variance()
    v.on_wave_completed(49)       # wave 50's news is rolled here (as when the game completes wave 49)
    g.get_wave_manager().end_wave()
    exact = intel.preview(g)
    check(not exact.forecast, "after the wave ends the preview is exact")
    g.get_wave_manager().start_next_wave()
    _matches(check, exact, g.get_wave_manager().get_current_def(), "wave 50 after its news roll")

    off = _game()
    _at(off, 12)
    off.get_wave_manager().start_next_wave()
    check(not intel.preview(off).forecast, "Patch Notes off: the next wave is never a forecast")


# ---------------------------------------------------------------- warnings
def _kinds(g, n):
    return {t.kind for t in intel.threats(g, intel.preview(g, n))}


def test_threat_warnings(check):
    g = new_game(0)
    check(_kinds(g, 23) == set(), "wave 23: no warnings")
    check(_kinds(g, 24) == {Threat.CAMO}, "wave 24, no towers: camo warning")
    gpt = force_place(g, T.GPT, buildable_near(g, Vec(380, 300), 150))
    check(_kinds(g, 24) == {Threat.CAMO}, "GPT cannot see camo")
    gem = force_place(g, T.GEMINI, buildable_near(g, Vec(700, 600), 150), 1)
    check(_kinds(g, 24) == {Threat.CAMO}, "Gemini tier 1 cannot see camo")
    g.get_tower_manager().upgrade(gem)
    check(Threat.CAMO not in _kinds(g, 24), "Gemini tier 2 sees camo: no warning")
    g.get_tower_manager().sell(gem)
    g.get_tower_manager().sell(gpt)
    force_place(g, T.PERPLEXITY, buildable_near(g, Vec(700, 600), 150))
    check(Threat.CAMO not in _kinds(g, 24), "Perplexity: no camo warning")

    g = new_game(0)
    check(_kinds(g, 28) == set(), "wave 28, no towers: no Lead warning (there is no damage at all to judge)")
    claude = force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150))
    check(_kinds(g, 28) == {Threat.LEAD}, "wave 28 (Heap Sort), Claude only: Sharp vs Lead")
    check(_kinds(g, 27) == set(), "wave 27 (no Lead-type): no warning")
    check(Threat.LEAD in _kinds(g, 31), "wave 31 (Radix Sort): Sharp vs Lead")
    hanbo = force_place(g, T.SPEAR_HANBO, buildable_near(g, Vec(700, 600), 150))
    check(Threat.LEAD in _kinds(g, 28), "two Sharp towers: still warned")
    g.get_tower_manager().sell(hanbo)
    for _ in range(3):
        g.get_tower_manager().upgrade(claude)
    check(claude.get_tier() == 3 and Threat.LEAD not in _kinds(g, 28), "Claude's final upgrade damages Lead: no warning")
    g.get_tower_manager().sell(claude)
    force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150))
    force_place(g, T.SUNO, buildable_near(g, Vec(700, 600), 150))
    check(Threat.LEAD not in _kinds(g, 28), "a Sonic tower beside Claude: no warning")

    g = new_game(0)
    check(_kinds(g, 39) == {Threat.CAMO}, "wave 39: camo but no boss")
    th = intel.threats(g, intel.preview(g, 40))
    boss = [t for t in th if t.kind is Threat.BOSS]
    check(len(boss) == 1 and "BELLARMINE COLLEGE PREP" in boss[0].chip, "wave 40: boss warning names the boss (%s)" % th)
    force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150))
    th = intel.threats(g, intel.preview(g, 90))
    check({t.kind for t in th} == {Threat.BOSS, Threat.CAMO, Threat.LEAD}, "wave 90 with Claude: boss, camo and Lead (%s)" % th)
    check("LOCKHEED MARTIN" in th[0].chip and "+1" in th[0].chip, "wave 90 boss chip: the DDT plus one more boss type")
    check(intel.threats(g, None) == [], "no preview, no warnings")


# ---------------------------------------------------------------- upgrade deltas
def _fmt_actual(g, t, label):
    s = t.get_stats()
    ty = t.get_type()
    if label == "DMG":
        return Ui.fmt(s.hit.damage * t.damage_multiplier(g))
    if label == "INTERVAL":
        return Ui.fmt(1.0 / max(0.01, t.effective_rate(g))) + "s"
    if label == "RANGE":
        return HeroStatText.range(ty, t.effective_range(g))
    if label == "PIERCE":
        return str(t.effective_pierce())
    if label in ("CHAIN", "MODE"):
        return SidePanel.mode_text(s)
    if label == "TARGETS":
        return str(s.targets)
    if label == "SHOTS":
        return str(s.projectiles_per_shot)
    if label == "SPLASH":
        return HeroStatText.range(ty, s.splash_radius)
    if label == "TYPE":
        return s.hit.type.label.upper()
    if label == "CAMO":
        return "YES" if t.can_see_camo() else "NO"
    raise AssertionError(label)


def _close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def _check_upgrades(check, g, t, what):
    while t.can_upgrade():
        tier = t.get_tier()
        nxt = intel.next_stats(t)
        dm = t.damage_multiplier(g)
        want_dmg = nxt.hit.damage * dm
        want_range, want_rate, want_camo = intel.next_range(g, t), intel.next_rate(g, t), intel.next_sees_camo(t)
        rows, gained = intel.upgrade_deltas(g, t)
        for r in rows:
            check(r.now == _fmt_actual(g, t, r.label), "%s T%d %s 'now' %s" % (what, tier, r.label, r.now))
        check(g.get_tower_manager().upgrade(t), "%s T%d upgrades" % (what, tier))
        check(_close(t.get_stats().hit.damage * t.damage_multiplier(g), want_dmg), "%s T%d->%d damage" % (what, tier, tier + 1))
        check(_close(t.effective_range(g), want_range), "%s T%d->%d range %.6f == %.6f" % (what, tier, tier + 1, want_range, t.effective_range(g)))
        check(_close(t.effective_rate(g), want_rate), "%s T%d->%d rate %.6f == %.6f" % (what, tier, tier + 1, want_rate, t.effective_rate(g)))
        check(t.can_see_camo() == want_camo, "%s T%d->%d camo detection" % (what, tier, tier + 1))
        for r in rows:
            check(r.next == _fmt_actual(g, t, r.label), "%s T%d->%d %s: preview %s, real %s" % (what, tier, tier + 1, r.label, r.next, _fmt_actual(g, t, r.label)))
        fx = set(SidePanel.effects_text(t.get_stats(), False).split("  •  ")) | set(SidePanel.support_text(t.get_stats(), False).split("  •  "))
        check(all(e in fx for e in gained), "%s T%d->%d gained effects %s exist after the upgrade" % (what, tier, tier + 1, gained))
    check(intel.upgrade_deltas(g, t) == ([], []) and intel.next_stats(t) is None, "%s at max tier: nothing to preview" % what)


def test_upgrade_deltas_match_real_upgrade(check):
    """For every shop tower and hero (Zethos has four upgrades): the previewed numbers equal the tower's real numbers
    after buying the upgrade, on a plain game and on one with Patch Notes, an O(N) difficulty and buffing neighbours."""
    types = list(T.shop_towers()) + list(T.heroes())
    check(T.ZETHOS in types and len(catalog.get(T.ZETHOS).upgrades) == 4, "Zethos (4 upgrades) is covered")
    for ty in types:
        g = new_game(0)
        g.set_hero_limit(99)
        t = force_place(g, ty, buildable_near(g, Vec(560, 480), 200))
        _check_upgrades(check, g, t, ty.name)
    buffers = [x for x in T.shop_towers() + list(T.heroes())
               if catalog.get(x).base_stats.aura_rate > 0 or catalog.get(x).base_stats.aura_range_bonus > 0]
    check(len(buffers) > 0, "some tower buffs its neighbours (%s)" % buffers)
    buffed = []
    for ty in (T.CLAUDE, T.GPT, T.GEMINI, T.ZETHOS, T.LLAMA, T.SPEAR_HANBO, T.NIK_SCOPE):
        g = _game(Difficulty.ON)
        g.set_hero_limit(99)
        g.get_variance().enable(Picker.FIRST)
        g.get_variance().grant(PatchNote.CONTEXT_WINDOW)
        g.get_variance().grant(PatchNote.QUANTIZATION)
        t = force_place(g, ty, buildable_near(g, Vec(560, 480), 200))
        for b in buffers[:2]:
            force_place(g, b, buildable_near(g, t.get_position(), 120), 3)
        buffed.append(t.get_aura_rate_bonus() > 0 or t.buff_total_uncapped(intel.BuffStat.RANGE) > 0)
        _check_upgrades(check, g, t, "buffed " + ty.name)
    check(any(buffed), "the buffed setups really buff (%s)" % buffed)


def test_upgrade_delta_examples(check):
    g = new_game(0)
    claude = force_place(g, T.CLAUDE, buildable_near(g, Vec(380, 300), 150), 2)
    rows, gained = intel.upgrade_deltas(g, claude)
    texts = [r.text() for r in rows]
    check("DMG 1 -> 2" in texts and "PIERCE 8 -> 20" in texts, "Claude Fable: %s" % texts)
    check("ignores immunities" in gained, "Claude Fable gains 'ignores immunities' (%s)" % gained)
    gem = force_place(g, T.GEMINI, buildable_near(g, Vec(700, 600), 150), 1)
    rows, _ = intel.upgrade_deltas(g, gem)
    camo = [r for r in rows if r.label == "CAMO"]
    check(len(camo) == 1 and camo[0].text() == "CAMO NO -> YES" and camo[0].better is True, "Gemini tier 2 gains camo detection")
    nik = force_place(g, T.NIK_SCOPE, buildable_near(g, Vec(560, 480), 200), 2)
    rows = {r.label: r for r in intel.upgrade_deltas(g, nik)[0]}
    check(rows["INTERVAL"].better is False and rows["DMG"].better is True, "Nik Scope Deadeye: slower (worse) but harder hits")
    check(rows["RANGE"].next.endswith("u"), "hero ranges are in map units")


def test_compact_numbers(check):
    cases = [(0, "0"), (7.9, "7"), (999, "999"), (1000, "1.0k"), (12345, "12.3k"), (99999, "99.9k"), (100000, "100k"),
             (999999, "999k"), (4567890, "4.5M"), (4600000, "4.6M"), (12.3e6, "12.3M"), (987e6, "987M"), (1.5e9, "1.5B"), (-5, "0")]
    for v, want in cases:
        check(intel.compact(v) == want, "compact(%r) = %r (want %r)" % (v, intel.compact(v), want))


# ---------------------------------------------------------------- read-only
def _state(g, ids=True):
    """Hash of the simulation state. ids=False leaves out the global id counters and absolute ids (twin games built
    side by side draw ids from the same counters)."""
    h = hashlib.blake2b(digest_size=16)
    u = h.update
    pk = struct.Struct("<d").pack
    u(b"%d" % g.get_rng()._random._seed)
    u(pk(g.get_cash()))
    u(pk(float(g.get_lives())))
    u(pk(g.get_time()))
    wm = g.get_wave_manager()
    u(repr((wm.get_current_wave(), wm.is_wave_active(), list(wm._progress))).encode())
    for e in g.get_enemy_manager().get_enemies():
        p = e.get_position()
        u(repr((e.get_id() if ids else 0, e.get_type().name)).encode())
        u(pk(p.x) + pk(p.y) + pk(e.get_hp()))
    for t in g.get_tower_manager().get_towers():
        u(repr((t.get_id() if ids else 0, t.get_tier(), t.can_see_camo())).encode())
        u(pk(t.get_damage_dealt()) + pk(t.effective_range(g)) + pk(t.effective_rate(g)))
    v = g.get_variance()
    u(repr((v.get_news(), v.get_news_wave(), v._news_rolled_for, v.get_offer(), v.get_active())).encode())
    if ids:
        u(b"ids%d.%d" % (Enemy._next_id, Tower._next_id))
    return h.hexdigest()


def _setup(g):
    g.set_hero_limit(99)
    for ty, p, tier in ((T.CLAUDE, Vec(380, 300), 1), (T.GPT, Vec(700, 600), 2), (T.ZETHOS, Vec(560, 480), 3)):
        force_place(g, ty, buildable_near(g, p, 200), tier)
    _at(g, 23)
    g.get_variance().enable(Picker.FIRST)


def test_preview_never_changes_the_game(check):
    """Previews, warnings, deltas and the HUD / panel / overlay that show them leave the game bit-identical: a twin game
    run with the UI reading it every frame ends in the same state as one run without."""
    a, b = _game(Difficulty.ON2, seed=99), _game(Difficulty.ON2, seed=99)
    for g in (a, b):
        _setup(g)
    check(_state(a, False) == _state(b, False), "twins start equal")
    s = GameScreen(None, a)
    tz = a.get_tower_manager().get_towers()[2]
    s.select_tower(tz)
    before = _state(a)
    for n in (1, 24, 40, 90, 100):
        pv = intel.preview(a, n)
        intel.threats(a, pv)
    for t in a.get_tower_manager().get_towers():
        intel.upgrade_deltas(a, t)
        intel.next_range(a, t)
    s.hud.update(0.02)
    s.side.update(0.02)
    ub = s.side.upgrade_btn
    s.mouse_moved(ub.get_x() + 10, ub.get_y() + 10)
    s.world.sync_overlay()
    s.mouse_moved(1100, Ui.BOTTOM_Y + 25)
    s.hud.update(0.02)
    EnemyIconImage.CACHE.clear()   # paint builds the enemy icons from throwaway Enemy objects
    _paint(s)
    check(len(EnemyIconImage.CACHE) > 0, "the strip painted enemy icons")
    check(_state(a) == before, "reading the intel leaves the state (RNG, ids, variance, towers) unchanged")
    for g in (a, b):
        g.get_wave_manager().start_next_wave()
    for i in range(600):
        a.step(Game.DT)
        b.step(Game.DT)
        if i % 5 == 0:
            s.mouse_moved(1100 if i % 2 else 1300, Ui.BOTTOM_Y + 25)
            s.hud.update(0.05)
            s.side.update(0.3)
            s.world.sync_overlay()
            intel.preview(a)
    check(_state(a, False) == _state(b, False), "after 10 s of wave 24 the twins are identical")
    check(len(a.get_enemy_manager().get_enemies()) > 0, "the twins really fought (enemies on the field)")


# ---------------------------------------------------------------- UI wiring
def _paint(s):
    surf = skia.Surface.MakeRasterN32Premul(800, 500)
    reset_canvas_state(surf.getCanvas())
    g = Graphics2D(surf.getCanvas())
    g.scale(0.5, 0.5)
    s.paint(g)
    reset_canvas_state(surf.getCanvas())


def test_hud_strip_and_card(check):
    g = new_game(0)
    _at(g, 24)
    s = GameScreen(None, g)
    s.frame(0.02)
    nw = s.hud.next_wave
    check(nw.preview is not None and nw.preview.number == 24, "the strip previews wave 24")
    check([t.kind for t in nw.threats] == [Threat.CAMO], "camo warning on the strip")
    check(not nw.is_card_visible(), "card hidden until hovered")
    s.mouse_moved(Ui.WORLD_W - 60, Ui.BOTTOM_Y + 30)
    s.frame(0.02)
    check(nw.is_card_visible(), "hovering the preview opens the card")
    card = nw.card
    check(card.get_y() + card.get_bounds().get_height() <= Ui.BOTTOM_Y and card.get_x() >= 0, "the card sits above the strip, on screen")
    _paint(s)
    s.mouse_moved(600, 400)
    s.frame(0.02)
    check(not nw.is_card_visible(), "moving away closes the card")
    force_place(g, T.GROK, buildable_near(g, Vec(380, 300), 150))
    s.frame(0.02)
    check(nw.threats == [], "building Grok clears the camo warning at once")
    g.get_wave_manager().start_next_wave()
    s.frame(0.02)
    check(nw.preview.number == 25 and "next // wave 25" in nw.label, "while wave 24 runs the strip shows wave 25")
    g.get_wave_manager().end_wave()
    _at(g, waves.WAVE_COUNT)
    check(g.get_wave_manager().start_next_wave(), "the final wave starts")
    s.frame(0.02)
    check(nw.preview is not None and nw.preview.number == waves.WAVE_COUNT and nw.label.startswith("live"),
          "the final wave shows itself while it runs")


def test_strip_layout_fits(check):
    """Every wave, worst case (O(N^N), Sharp-only defence, longest map name): the preview stays right of the map name and
    the note between them; nothing leaves the 1200 px strip."""
    g = _game(Difficulty.ONN, map_idx=2)
    force_place(g, T.CLAUDE, buildable_near(g, Vec(560, 480), 200))
    g.get_variance().enable(Picker.FIRST)
    s = GameScreen(None, g)
    hud = s.hud
    for n in range(1, waves.WAVE_COUNT + 1):
        _at(g, n)
        if n % 7 == 0:
            g.get_variance().force_news(BreakingNews.VIRAL_MEME, -1)
        hud.update(0.02)
        nw = hud.next_wave
        lb = hud.left_block_right()
        check(nw.left >= lb + 100, "wave %d: preview block (x=%.0f) clear of the map name (%.0f)" % (n, nw.left, lb))
        check(nw.right <= Ui.WORLD_W, "wave %d: block inside the strip" % n)
        for l in (hud.note_label, hud.note_label2, hud.event_label):
            if l.get_label():
                check(l.get_x() >= lb and l.get_x() + l.get_width() <= nw.left, "wave %d: %r fits between" % (n, l.get_label()[:30]))


def test_tower_panel_damage_and_deltas(check):
    g = new_game(0)
    t = force_place(g, T.ZETHOS, buildable_near(g, Vec(560, 480), 200), 3)
    t.add_damage_dealt(12345.6)
    s = GameScreen(None, g)
    s.select_tower(t)
    s.frame(0.02)
    side = s.get_side_panel()
    texts = [o.get_label() for o in side.info if hasattr(o, "get_label")]
    check("DMG DEALT" in texts and "12.3k" in texts, "damage dealt readout (%s)" % [x for x in texts if "k" in x][:5])
    check("DMG" in texts and "7" in texts, "Zethos 4th upgrade shows DMG 6 -> 7")
    check(side.upgrade_btn is not None and side.upgrade_hover_tower() is None, "upgrade button built, not hovered")
    ub = side.upgrade_btn
    s.mouse_moved(ub.get_x() + 20, ub.get_y() + 10)
    s.frame(0.02)
    ring = s.world.next_range_circle
    check(side.upgrade_hover_tower() is t and ring.is_visible(), "hovering UPGRADE shows the next-tier range ring")
    check(_close(ring.w / 2, intel.next_range(g, t)) and ring.w > s.world.range_circle.w, "ring radius = next tier's range")
    _paint(s)
    s.mouse_moved(600, 400)
    s.frame(0.02)
    check(not ring.is_visible(), "ring hidden when the button is not hovered")
    g.get_tower_manager().upgrade(t)
    s.frame(0.02)
    check(side.upgrade_btn is None, "max tier: no upgrade button, no preview")
    # the panel stays on screen for every tower and tier with the full shop shown
    side.toggle_all()
    for ty in list(T.shop_towers()) + list(T.heroes()):
        gg = new_game(0)
        gg.set_hero_limit(99)
        tw = force_place(gg, ty, buildable_near(gg, Vec(560, 480), 200))
        ss = GameScreen(None, gg)
        ss.get_side_panel().toggle_all()
        ss.select_tower(tw)
        while True:
            ss.frame(0.02)
            check(ss.get_side_panel().y + 34 <= Ui.H - 8, "%s T%d: panel ends on screen (%.0f)" % (ty.name, tw.get_tier(), ss.get_side_panel().y + 34))
            if not gg.get_tower_manager().upgrade(tw):
                break


def test_reverse_mode_hides_preview(check):
    g = ReverseMatch.create(0, 42, Difficulty.ON)
    s = GameScreen(None, g)
    s.frame(0.02)
    check(not s.hud.next_wave.is_visible(), "the attacker's HUD has no next-wave preview")
