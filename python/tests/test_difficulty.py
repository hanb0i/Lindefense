"""Difficulty Growth modes (port of DifficultyTests.java)."""
import math
import os

import pytest

from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy.boss import Boss
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.javacompat import jround
from lindefense.jenum import EnumSet
from lindefense.map import maps
from lindefense.sim import difficulty as diffmod
from lindefense.sim.difficulty import Curve, Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.wave import waves

D = Difficulty
DT = Game.DT


def _game(d, m):
    return Game(maps.create(m), 42, d)


def _to_wave(g, wave):
    while g.get_wave() < wave:
        g.get_wave_manager().start_next_wave()
        if g.get_wave() < wave:
            g.get_wave_manager().end_wave()


def _kill(g, e):
    g.get_combat().apply_hit_simple(e, HitSpec(1e12, DamageType.TRUE), None, 1, 0)
    g.get_enemy_manager().update(0)


def _sig(d):
    return ";".join("%s|%d|%s|%r|%r|%r" % (s.type, s.count, sorted(m.ordinal for m in s.modifiers), s.interval, s.start_delay, s.route)
                    for s in d.groups)


def _find_spot(g, target):
    r = 0.0
    while r <= 300:
        for a in range(24):
            p = Vec(target.x + math.cos(a * math.pi / 12) * r, target.y + math.sin(a * math.pi / 12) * r)
            if g.get_tower_manager().can_place(T.GPT, p):
                return p
        r += 10
    return None


def test_o1_is_identical(check):
    check(D.O1.is_base(), "O1 is the base mode")
    for d in waves.all_waves():
        check(D.O1.shape(d, 42) is d, "O1 returns the very same wave object, wave %d" % d.number)
        check(D.O1.shape(d, 7) is d, "O1 ignores the seed")
    g = _game(D.O1, 0)
    check(g.get_cash() == Game.START_CASH and g.get_lives() == Game.START_LIVES, "O1 start cash / lives unchanged")
    check(g.get_global_damage_multiplier() == 1.0, "O1 tower damage x1")
    check(D.default_mode() is D.O1 or os.environ.get(diffmod.PROPERTY) is not None, "default mode is O1 without the override")
    dflt = Game(maps.create(0), 42)
    check(dflt.get_difficulty() is D.default_mode(), "two-arg constructor uses the default mode")
    if dflt.get_difficulty() is not D.O1:
        return
    for w in (1, 10, 40, 41, 60, 80, 99, 100):
        a = _game(D.O1, 1)
        _to_wave(a, w)
        check(a.get_wave_hp_scale() == waves.hp_scale(w), "O1 hp scale wave %d" % w)
        check(a.get_reward_scale() == waves.reward_scale(w), "O1 reward scale wave %d" % w)
        e = a.get_enemy_manager().spawn(EnemyType.QUICK_SORT, None, 0, 0)
        check(e.get_max_hp() == max(1, jround(EnemyType.QUICK_SORT.base_hp * waves.hp_scale(w))), "O1 enemy HP wave %d" % w)
    for wave in (3, 10, 20, 50, 70):
        a = _game(D.O1, 0)
        a.set_global_enemy_speed_multiplier(0)
        _to_wave(a, wave - 1)
        a.get_wave_manager().end_wave()
        a.start_next_wave()
        want = waves.get(wave)
        check(a.get_wave_manager().get_current_def() is want, "O1 wave %d uses the table definition" % wave)
        check(a.get_wave_manager().get_remaining_to_spawn() == want.total_spawns(), "O1 wave %d spawn total" % wave)
    b = _game(D.O1, 0)
    _to_wave(b, 30)
    c0 = b.get_cash()
    b.on_wave_completed(30, waves.get(30))
    check(b.get_cash() - c0 == waves.wave_bonus(30), "O1 wave bonus unchanged")


def test_multipliers_applied(check):
    for d in (D.ON, D.ON2, D.ONN):
        w = 60
        g = _game(d, 0)
        _to_wave(g, w)
        base = _game(D.O1, 0)
        _to_wave(base, w)
        hp_m = d.hp_multiplier(w)
        check(abs(g.get_wave_hp_scale() - waves.hp_scale(w) * hp_m) < 1e-9, "%s hp scale = base x %s" % (d, hp_m))
        check(hp_m > 1, "%s hp multiplier > 1" % d)
        e = g.get_enemy_manager().spawn(EnemyType.QUICK_SORT, None, 0, 0)
        eb = base.get_enemy_manager().spawn(EnemyType.QUICK_SORT, None, 0, 0)
        check(e.get_max_hp() == max(1, jround(EnemyType.QUICK_SORT.base_hp * waves.hp_scale(w) * hp_m)), "%s enemy max HP scaled" % d)
        check(e.get_max_hp() > eb.get_max_hp(), "%s enemy has more HP than O1" % d)
        check(abs(g.get_wave_hp_scale(EnemyType.PALANTIR) - waves.hp_scale(w) * d.palantir_hp()) < 1e-9, "%s Palantir HP multiplier" % d)
        g.get_enemy_manager().update(0)
        c0 = g.get_cash()
        _kill(g, e)
        want_reward = jround(EnemyType.QUICK_SORT.reward * waves.reward_scale(w) * d.income)
        check(g.get_cash() - c0 == want_reward, "%s kill reward: got %s want %s" % (d, g.get_cash() - c0, want_reward))
        check(d.income < 1, "%s income reduced" % d)
        c1 = g.get_cash()
        g.on_wave_completed(w, waves.get(w))
        check(g.get_cash() - c1 == jround(waves.wave_bonus(w) * d.income), "%s wave bonus scaled" % d)
        p = Vec(400, 250)
        spot, spot_b = _find_spot(g, p), _find_spot(base, p)
        t = g.get_tower_manager().place(T.GPT, spot or p)
        tb = base.get_tower_manager().place(T.GPT, spot_b or p)
        if t is not None and tb is not None:
            check(abs(t.damage_multiplier(g) / tb.damage_multiplier(base) - d.tower_damage) < 1e-9, "%s tower damage multiplier" % d)
        else:
            check(False, "%s could not place test towers" % d)
        check(d.tower_damage < 1, "%s tower damage reduced" % d)
    ds = list(D)
    for a, b in zip(ds, ds[1:]):
        check(b.hp_multiplier(100) > a.hp_multiplier(100), "%s HP at wave 100 above %s" % (b, a))
        check(b.tower_damage < a.tower_damage, "%s tower damage below %s" % (b, a))
        check(b.income < a.income, "%s income below %s" % (b, a))
        check(b.count_multiplier(100) > a.count_multiplier(100), "%s count above %s" % (b, a))
        check(b.elite_chance(100) >= a.elite_chance(100), "%s elites at least %s" % (b, a))
    for d in ds:
        if d.curve is Curve.FLAT:
            check(d.growth(50) == 0, "%s flat" % d)
            continue
        check(abs(d.growth(100) - 1) < 1e-9, "%s growth is 1 at wave 100" % d)
        check(d.growth(10) < d.growth(50) < d.growth(90), "%s growth is increasing" % d)
    check(abs(D.ON.growth(50) - 0.5) < 1e-9, "O(N) is linear")
    check(abs(D.ON2.growth(50) - 0.25) < 1e-9, "O(N^2) is quadratic")
    check(D.ONN.growth(50) == D.ON2.growth(50), "O(N^N) ramps on the same quadratic curve")
    check(D.parse("O(N^2)") is D.ON2 and D.parse("onn") is D.ONN and D.parse("O1") is D.O1 and D.parse("O(N²)") is D.ON2
          and D.parse("zzz") is None, "difficulty parsing")


def test_shaping_is_deterministic(check):
    for d in (D.ON, D.ON2, D.ONN):
        any_seed_differs = False
        elites_seen = 0
        for base in waves.all_waves():
            a, b = d.shape(base, 42), d.shape(base, 42)
            check(_sig(a) == _sig(b), "%s wave %d deterministic for the same seed" % (d, base.number))
            if _sig(a) != _sig(d.shape(base, 43)):
                any_seed_differs = True
            base_nb = sum(s.count for s in base.groups if not s.type.is_boss())
            new_nb = sum(s.count for s in a.groups if not s.type.is_boss())
            check(new_nb >= base_nb, "%s wave %d never has fewer non-boss enemies" % (d, base.number))
            cm = d.count_multiplier(base.number)
            if any(not bg.type.is_boss() for bg in base.groups):
                check(new_nb <= math.ceil(base_nb * cm) + len(base.groups) + 1, "%s wave %d count within rounding" % (d, base.number))
            for s in a.groups:
                if s.type.is_boss():
                    continue
                if not any(bg.type is s.type and bg.modifiers == s.modifiers for bg in base.groups):
                    elites_seen += s.count
                check(s.count >= 1 and s.interval > 0 and s.start_delay >= 0, "%s wave %d sane group values" % (d, base.number))
            check(a.contains(EnemyType.PALANTIR) == base.contains(EnemyType.PALANTIR), "%s Palantir presence wave %d" % (d, base.number))
        check(any_seed_differs, "%s output depends on the seed" % d)
        if d is D.ON:
            check(d.elite_chance(100) == 0, "O(N) has no elites")
        else:
            check(elites_seen > 0, "%s produces elite groups (%d)" % (d, elites_seen))
    w90 = D.ONN.shape(waves.get(90), 42)
    elite_has_more = any(bg.type is s.type and len(s.modifiers) > len(bg.modifiers)
                         for s in w90.groups if not s.type.is_boss() for bg in waves.get(90).groups)
    check(elite_has_more, "O(N^N) wave 90 elites have extra modifiers")
    a, b = _game(D.ON2, 0), _game(D.ON2, 0)
    _to_wave(a, 49)
    _to_wave(b, 49)
    a.get_wave_manager().end_wave()
    b.get_wave_manager().end_wave()
    a.start_next_wave()
    b.start_next_wave()
    check(_sig(a.get_wave_manager().get_current_def()) == _sig(b.get_wave_manager().get_current_def()), "same seed -> same live wave plan")
    check(a.get_wave_manager().get_remaining_to_spawn() == a.get_wave_manager().get_current_def().total_spawns(), "live spawn total")


def test_bosses_and_tuning(check):
    for d in D:
        for base in waves.all_waves():
            shaped = d.shape(base, 42)
            b0 = sum(s.count for s in base.groups if s.type.is_boss())
            b1 = sum(s.count for s in shaped.groups if s.type.is_boss())
            if b0 != b1:
                check(False, "%s wave %d changed its boss count %d -> %d" % (d, base.number, b0, b1))
                break
    g = _game(D.ONN, 0)
    g.set_global_enemy_speed_multiplier(0)
    _to_wave(g, 45)
    moab = g.get_enemy_manager().spawn(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 0)
    g.get_enemy_manager().update(0)
    check(isinstance(moab, Boss), "a MOAB is a Boss instance")
    qs = g.get_enemy_manager().count_of_type(EnemyType.QUICK_SORT)
    hp_scale = moab.get_hp_scale()
    _kill(g, moab)
    g.get_enemy_manager().update(0)
    check(g.get_enemy_manager().count_of_type(EnemyType.QUICK_SORT) == qs + 4, "a MOAB splits into 4 Quick Sorts on O(N^N)")
    for e in g.get_enemy_manager().get_enemies():
        if e.get_type() is EnemyType.QUICK_SORT:
            check(e.get_hp_scale() == hp_scale, "children inherit the parent's HP scale")
            break
    f = _game(D.ONN, 1)
    f.set_global_enemy_speed_multiplier(0)
    bfb = f.get_enemy_manager().spawn(EnemyType.SW_RESOURCE_CONSULTANT, EnumSet.of(Modifier.FORTIFIED), 0, 0)
    f.get_enemy_manager().update(0)
    _kill(f, bfb)
    f.get_enemy_manager().update(0)
    check(f.get_enemy_manager().count_of_type(EnemyType.BELLARMINE_COLLEGE_PREP) == 3, "BFB splits into 3 MOABs on O(N^N)")
    for e in f.get_enemy_manager().get_enemies():
        if e.get_type() is EnemyType.BELLARMINE_COLLEGE_PREP:
            check(e.is_fortified(), "Fortified inherited by boss children")
    n, m, l = D.ONN, D.ON2, D.ON
    check(n.curve is Curve.QUADRATIC and n.hp_base == 1.25 and n.hp_final == 3.10 and n.count_base == 1.25 and n.count_final == 2.40
          and n.tower_damage == 0.84 and n.income == 0.56 and n.elite_base == 0.03 and n.elite_final == 0.80 and n.elite_mods == 2
          and n.promote_chance == 0.50 and n.start_cash_mult == 1 and n.start_lives_mult == 1,
          "O(N^N) uses exactly the previous O(N^2) numbers")
    check([d.palantir_hp() for d in D] == [1.0, 1.15, 1.3, 2.0], "Palantir HP x1 / 1.15 / 1.3 / 2 by mode, on top of the wave curve")
    check(l.hp_final < m.hp_final < n.hp_final and l.count_final < m.count_final < n.count_final, "O(N^2) HP and count in between")
    check(l.tower_damage > m.tower_damage > n.tower_damage and l.income > m.income > n.income, "O(N^2) damage and income in between")
    check(0 < m.elite_final < n.elite_final and m.promote_chance < n.promote_chance, "O(N^2) has fewer, gentler elites")


def test_palantir_and_victory(check):
    for d in D:
        check(d.shape(waves.get(100), 42).count_of(EnemyType.PALANTIR) == 1, "%s wave 100 contains exactly one Palantir" % d)
    for d in (D.O1, D.ON2, D.ONN):
        g = _game(d, 2)
        g.set_global_enemy_speed_multiplier(0)
        _to_wave(g, 99)
        g.get_wave_manager().end_wave()
        g.start_next_wave()
        check(g.get_wave() == 100, "%s reached wave 100" % d)
        g.run(60 * 10)
        pal = g.get_palantir()
        check(pal is not None and pal.is_alive(), "%s Palantir spawned" % d)
        if pal is None:
            continue
        expected = EnemyType.PALANTIR.base_hp * waves.hp_scale(100) * (1.0 if d.is_base() else d.palantir_hp())
        check(abs(pal.get_max_hp() - jround(expected)) <= 1, "%s Palantir HP %s vs %s" % (d, pal.get_max_hp(), expected))
        _kill(g, pal)
        check(g.is_victory_sequence_active(), "%s victory sequence starts" % d)
        g.run(int(Game.VICTORY_SEQUENCE_TIME / DT) + 5)
        check(g.get_state() is State.VICTORY, "%s state VICTORY, got %s" % (d, g.get_state()))


@pytest.mark.slow
def test_stress_late_waves_on_impossible(check):
    types = (T.KAIJU_KAI, T.DEEPSEEK, T.COHERE, T.GEMINI, T.SORA, T.SUNO)
    for m in range(maps.MAP_COUNT):
        g = _game(D.ONN, m)
        g.set_invincible(True)
        g.set_global_enemy_speed_multiplier(0.5)
        g.add_cash(400_000, None)
        placed = 0
        for r in g.get_map().get_routes():
            dd = 100.0
            while dd < r.get_total_length() and placed < 12:
                base, direction = r.position_at(dd), r.direction_at(dd)
                for side in (-1, 1):
                    p = base.add(Vec(-direction.y, direction.x).scale(side * 70))
                    tt = types[placed % len(types)]
                    if g.get_tower_manager().can_place(tt, p):
                        t = g.place_tower(tt, p)
                        g.upgrade_tower(t)
                        placed += 1
                dd += 220
        _to_wave(g, 94)
        peak = 0
        for wave in range(95, 101):
            g.get_wave_manager().end_wave()
            g.get_enemy_manager().clear()
            check(g.start_next_wave(), "start wave %d on map %d" % (wave, m))
            ticks = 0
            while g.get_wave_manager().is_wave_active() and ticks < 60 * 120 and g.get_state() is State.PLAYING:
                g.step(DT)
                if ticks % 120 == 0:
                    for t in list(g.get_tower_manager().get_towers()):
                        if t.is_ability_ready():
                            g.activate_ability(t)
                peak = max(peak, len(g.get_enemy_manager().get_enemies()))
                g.get_events().clear()
                ticks += 1
            if g.get_state() is not State.PLAYING:
                break
        check(peak > 20, "map %d stress produced a real rush (peak %d)" % (m, peak))
        check(g.get_state() in (State.PLAYING, State.VICTORY), "map %d stress ended in a valid state %s" % (m, g.get_state()))
