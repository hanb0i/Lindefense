"""Tower spec section 3.7 balance targets (port of BalanceTests.java)."""
import pytest

from kit import DT, force_place, new_game
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.map.game_map import GameMap
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower_type import TowerType as T
from lindefense.wave import waves

DUEL_MAP = 1


def _top(t):
    return len(catalog.get(t).upgrades)


def _best_spot(g, type_):
    rng = min(catalog.get(type_).base_stats.range, 400)
    r = g.get_map().get_routes()[0]
    g.add_cash(1_000_000, None)
    for h in T.heroes():
        g.get_hero_collection().unlock(h)
    samples = []
    d = 0.0
    while d < r.get_total_length():
        samples.append(r.position_at(d))
        d += 20
    best, best_n = None, -1
    r2 = rng * rng
    for x in range(30, GameMap.WIDTH, 15):
        for y in range(30, GameMap.HEIGHT, 15):
            p = Vec(x, y)
            if not g.get_map().is_buildable(p, 20) or g.get_tower_manager().placement_problem(type_, p) is not None:
                continue
            n = sum(1 for s in samples if s.dist_sq(p) <= r2)
            if n > best_n:
                best_n, best = n, p
    return best


def duel(type_, boss, hp_scale=1.0):
    """Fraction of the boss's HP left after it has walked the route past one fully upgraded tower (0 = killed)."""
    g = new_game(DUEL_MAP)
    g.set_invincible(True)
    route = g.get_map().get_routes()[0]
    t = force_place(g, type_, _best_spot(g, type_), _top(type_))
    e = g.get_enemy_manager().spawn_scaled(boss, None, 0, 0, hp_scale, 1.0)
    g.get_enemy_manager().update(0)
    time = 0.0
    while time < 400 and e.is_alive() and not e.has_leaked() and e.get_distance() < route.get_total_length() - 1:
        if t.get_ability() is not None and t.is_ability_ready():
            if t.get_ability().needs_target:
                g.activate_ability(t, e.get_position())
            else:
                g.activate_ability(t)
        g.step(DT)
        g.get_events().clear()
        time += DT
    return e.get_hp() / e.get_max_hp() if e.is_alive() else 0.0


def crowd_dps(type_):
    g = new_game(DUEL_MAP)
    g.set_invincible(True)
    t = force_place(g, type_, _best_spot(g, type_), _top(type_))
    secs, every, acc, time = 60.0, 0.25, 0.0, 0.0
    while time < secs:
        acc += DT
        if acc >= every:
            acc -= every
            g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0, 0, 3000, 1.0)
        g.step(DT)
        g.get_events().clear()
        time += DT
    return t.get_damage_dealt() / secs


def _pct(f):
    return "%s%%" % (round(f * 1000) / 10.0)


def test_hp_never_decreases(check):
    for w in range(1, waves.WAVE_COUNT):
        check(waves.hp_scale(w + 1) >= waves.hp_scale(w), "HP scale never decreases (wave %d)" % w)
    check(waves.hp_scale(100) > waves.hp_scale(80) > waves.hp_scale(60), "HP grows after wave 60 and again after wave 80")
    pal = EnemyType.PALANTIR.base_hp
    for t in EnemyType:
        if t.is_boss() and t is not EnemyType.PALANTIR:
            check(pal > 2 * t.base_hp * waves.hp_scale(100) * 2, "Palantir clearly outweighs a Fortified %s" % t)


@pytest.mark.slow
def test_heroes_cannot_solo_late_bfb(check):
    bfb_left, crowd = {}, {}
    parts = []
    for h in T.heroes():
        moab = duel(h, EnemyType.BELLARMINE_COLLEGE_PREP, waves.hp_scale(40))
        bfb = duel(h, EnemyType.SW_RESOURCE_CONSULTANT, waves.hp_scale(99))
        dps = crowd_dps(h)
        bfb_left[h], crowd[h] = bfb, dps
        parts.append("%s=%s/%s/%d" % (h, _pct(moab), _pct(bfb), round(dps)))
        check(bfb > 0, "%s alone must not defeat a wave-99 BFB (HP left %s)" % (h, _pct(bfb)))
    print("      hero solo, HP left: MOAB(w40) / BFB(w99) / crowd dps: " + " ".join(parts))
    ml, sh = T.MR_LINDEMANN, T.SPEAR_HANBO
    for h in T.heroes():
        if h is ml:
            continue
        check(bfb_left[ml] < bfb_left[h] and crowd[ml] > crowd[h], "Mr. Lindemann is stronger than %s" % h)
        if h is sh:
            continue
        check(bfb_left[sh] < bfb_left[h] and crowd[sh] > crowd[h], "Spear Hanbo is stronger than %s" % h)


@pytest.mark.slow
def test_no_solo_bfb(check):
    for wave in (1, 60, 99):
        scale = 1.0 if wave == 1 else waves.hp_scale(wave)
        label = "base" if wave == 1 else "wave %d" % wave
        parts = []
        for tt in T.purchasable():
            if tt.is_hero():
                continue
            left = duel(tt, EnemyType.SW_RESOURCE_CONSULTANT, scale)
            parts.append("%s=%s" % (tt, _pct(left)))
            check(left > 0, "%s fully upgraded must not solo a BFB (%s)" % (tt, label))
        if wave in (1, 60):
            print("      solo BFB hp left (%s): %s" % (label, " ".join(parts)))


def test_hero_prices(check):
    cheapest, priciest = 2 ** 31, 0
    cheap_t = pricey_t = None
    for h in T.heroes():
        p = catalog.get(h).unlock_cost
        check(1100 <= p <= 3500, "%s Hero Store price $%d is in the $1,100-3,500 band" % (h, p))
        if p < cheapest:
            cheapest, cheap_t = p, h
        if p > priciest:
            priciest, pricey_t = p, h
    check(cheap_t is T.SUNNY_JOE and cheapest == 1150, "Sunny Joe is the cheapest hero at $1,150")
    check(pricey_t is T.MR_LINDEMANN and priciest == 3400, "Mr. Lindemann is the priciest at $3,400")
    check(catalog.get(T.SPEAR_HANBO).unlock_cost == 2700, "Spear Hanbo costs $2,700")
    check(catalog.get(T.ZETHOS).total_cost() == 5350, "Zethos fully upgraded costs $5,350")


def _force_place_best(g, type_, aim_at):
    g.add_cash(1_000_000, None)
    for h in T.heroes():
        g.get_hero_collection().unlock(h)
    route = g.get_map().get_routes()[0]
    zone = route.position_at(min(aim_at, route.get_total_length() - 50))
    reach = catalog.get(type_).stats_for_tier(_top(type_)).range
    best, best_d = None, float("inf")
    for pss in range(2):
        if best is not None:
            break
        for x in range(30, GameMap.WIDTH, 15):
            for y in range(30, GameMap.HEIGHT, 15):
                p = Vec(x, y)
                if not g.get_map().is_buildable(p, 20) or g.get_tower_manager().placement_problem(type_, p) is not None:
                    continue
                if pss == 0 and route.distance_to_point(p) > reach * 0.8:
                    continue
                d = p.dist(zone)
                if d < best_d:
                    best_d, best = d, p
    return force_place(g, type_, best, _top(type_))


@pytest.mark.slow
def test_every_tower_contributes_late(check):
    g = Game(maps.create(DUEL_MAP), 99, Difficulty.ONN)
    g.set_hero_limit(2 ** 31 - 1)
    g.set_invincible(True)
    order = sorted(T.purchasable(), key=lambda x: catalog.get(x).base_stats.range)
    length = g.get_map().get_routes()[0].get_total_length()
    build = []
    half = (len(order) + 1) // 2
    for i, ty in enumerate(order):
        slot = i // 2 if i % 2 == 0 else half + i // 2
        build.append(_force_place_best(g, ty, 220 + (length * 0.45 - 220) * slot / float(max(1, len(order) - 1))))
    while g.get_wave() < 59:
        g.get_wave_manager().start_next_wave()
        g.get_wave_manager().end_wave()
    for w in range(60, 65):
        check(g.get_wave_manager().start_next_wave(), "wave %d starts" % w)
        tick = 0
        while tick < 60 * 400 and (g.get_wave_manager().is_wave_active() or tick < 60):
            g.step(DT)
            g.get_events().clear()
            tick += 1
    silent = []
    parts = []
    for t in build:
        parts.append("%s=%d/%d" % (t.get_type(), round(t.get_damage_dealt()), t.get_kills()))
        active = t.get_damage_dealt() > 0 or t.get_kills() > 0
        ty = t.get_type()
        if ty is T.PERPLEXITY:
            active = t.get_behavior().on_round_end(g, t) > 0
        if ty is T.SAGE_AARAV:
            active = t.get_stats().p("healAmount", 0) > 0
        if ty is T.SUNNY_JOE:
            active = t.get_stats().p("income", 0) > 0
        if ty is T.TANIMBUS:
            active = t.get_stats().aura_rate > 0 or t.get_stats().p("buffRate", 0) > 0
        if not active:
            silent.append(ty)
    print("      waves 60-64 damage: " + " ".join(parts))
    check(len(build) == len(T.purchasable()), "the mixed build has every tower and hero (%d)" % len(build))
    broken = [t for t in silent if duel(t, EnemyType.BELLARMINE_COLLEGE_PREP) >= 1.0]
    if silent:
        print("      quiet in the scrum but able to fight alone: %r" % silent)
    check(not broken, "every tower can contribute in waves 60+ (%r)" % broken)


def test_ability_cooldowns_in_game_time(check):
    g = new_game(DUEL_MAP)
    t = force_place(g, T.ZETHOS, _best_spot(g, T.ZETHOS), catalog.ZETHOS_UPGRADES)
    g.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(t) and g.activate_ability(t), "Zethos's bought ability fires")
    start = t.get_ability_cooldown_remaining()
    check(abs(start - t.get_ability().cooldown) < 1e-9, "a used ability starts its full cooldown")
    g.set_speed(3)
    for _ in range(6):
        g.advance(1.0 / 6)
    check(abs(start - t.get_ability_cooldown_remaining() - g.get_time()) < 1e-6, "cooldown drops by game time (%s s)" % g.get_time())
    check(2.9 < g.get_time() < 3.1, "fast-forward speeds game time up (%s)" % g.get_time())
