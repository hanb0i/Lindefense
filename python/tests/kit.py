"""Shared builders for the headless tests (port of the Java TestKit): games, towers, enemies, hits."""
import math

from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.jenum import EnumSet
from lindefense.map import maps
from lindefense.sim.game import Game, State
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower_type import TowerType

DT = Game.DT


def new_game(map_idx=0, seed=42):
    return Game(maps.create(map_idx), seed)


def mods(*ms):
    return EnumSet(ms)


def buildable_near(g, target, radius):
    """A buildable point within radius of target (spiral search, like the Java kit)."""
    r = 0.0
    while r <= radius:
        for a in range(24):
            ang = a * math.pi / 12
            p = Vec(target.x + math.cos(ang) * r, target.y + math.sin(ang) * r)
            if g.get_map().is_buildable(p, 20):
                prob = g.get_tower_manager().placement_problem(TowerType.GPT, p)
                if prob is None or prob == "Not enough cash":
                    return p
        r += 10
    raise RuntimeError("No buildable point near %r" % (target,))


def force_place(g, type_, p, tier=0):
    """Places a tower with unlimited cash and buys tier upgrades (heroes unlocked first, in memory)."""
    g.add_cash(1_000_000, None)
    if type_.is_hero():
        g.get_hero_collection().unlock(type_)
    t = g.get_tower_manager().place(type_, p)
    if t is None:
        raise RuntimeError("Could not place %s at %r: %s" % (type_, p, g.get_tower_manager().placement_problem(type_, p)))
    for _ in range(tier):
        g.get_tower_manager().upgrade(t)
    return t


def tower_near_track(g, type_, tier, track_distance):
    r = g.get_map().get_routes()[0]
    p = buildable_near(g, r.position_at(track_distance).add(Vec(0, -70)), 120)
    return force_place(g, type_, p, tier)


def spawn_at(g, type_, ms, route, dist):
    """Spawns an enemy and flushes it into the active list without moving anything."""
    e = g.get_enemy_manager().spawn(type_, ms, route, dist)
    g.get_enemy_manager().update(0)
    return e


def kill_outright(g, e):
    g.get_combat().apply_hit_simple(e, HitSpec(1e9, DamageType.TRUE), None, 1, 0)
    g.get_enemy_manager().update(0)


def run_seconds(g, seconds):
    g.run(int(math.floor(seconds / DT + 0.5)))


def hit(dmg, type_):
    return HitSpec(dmg, type_)


def hit_for(g, e, dmg, type_):
    return g.get_combat().apply_hit_simple(e, HitSpec(dmg, type_), None, 1, 0)


def ticks(seconds):
    """(int) (seconds / Game.DT), Java truncation."""
    return int(seconds / DT)
