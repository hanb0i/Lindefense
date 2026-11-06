"""Shop-tower ability unlocks, and consistency regressions (global damage multiplier, no duplicate enemies, grid)."""
import math

from kit import mods, new_game, run_seconds, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.effects.effects import Barrage, Drone, NodeHazard, TrackWalker, TrackZone
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import AttackKind, TowerType


def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _unlocked(check, g, t, d):
    tw = tower_near_track(g, t, len(catalog.get(t).upgrades), d)
    g.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(tw), "%s ability unlocks" % t)
    return tw


def _tank(g, ms, d, hp):
    e = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, ms, 0, d, hp, 1.0)
    g.get_enemy_manager().update(0)
    return e


def test_unlock_rules(check):
    price = catalog.ABILITY_UNLOCK_COST
    check(price == 15_000, "ability unlock costs $15,000")
    for t in TowerType.shop_towers():
        check(catalog.get(t).ability is not None and catalog.ability_needs_unlock(t), "%s locked ability" % t)
    for h in TowerType.heroes():
        check(catalog.get(h).ability is None, "%s is passive" % h)
    g = _frozen()
    c = tower_near_track(g, TowerType.CLAUDE, 0, 450)
    check(c.is_ability_locked() and c.get_ability() is None and c.get_ability_def() is not None, "fresh ability locked")
    check(not c.is_ability_ready() and not g.activate_ability(c), "a locked ability cannot fire")
    g.add_cash(100_000, None)
    before = g.get_cash()
    check(not c.can_unlock_ability() and not g.unlock_ability(c) and g.get_cash() == before, "needs every upgrade first")
    while c.can_upgrade():
        check(g.upgrade_tower(c), "upgrade Claude")
    check(c.can_unlock_ability(), "a maxed tower can unlock its ability")
    g.spend_cash(g.get_cash() - (price - 1))
    check(not g.unlock_ability(c) and c.is_ability_locked() and g.get_cash() == price - 1, "fails below $15,000")
    inv = c.get_invested_cost()
    g.add_cash(1, None)
    check(g.unlock_ability(c) and g.get_cash() == 0, "unlock charges exactly $15,000")
    check(not c.is_ability_locked() and c.is_ability_ready(), "unlocked ability is ready at once")
    check(c.get_invested_cost() == inv + price and shop.sell_value(c) == int(math.floor(c.get_invested_cost() * shop.SELL_FRACTION)), "counts toward sell value")
    g.add_cash(price, None)
    check(not g.unlock_ability(c) and g.get_cash() == price, "cannot be bought twice")
    zg = _frozen()
    z = tower_near_track(zg, TowerType.ZETHOS, 0, 450)
    check(z.is_ability_locked() and not zg.activate_ability(z), "Zethos locked at placement")
    zg.add_cash(100_000, None)
    for _ in range(catalog.ZETHOS_UPGRADES - 1):
        zg.upgrade_tower(z)
    check(not z.can_unlock_ability() and not zg.unlock_ability(z), "Zethos needs all four upgrades")
    check(zg.upgrade_tower(z) and z.is_maxed(), "fourth upgrade maxes it")
    zc = zg.get_cash()
    check(zg.unlock_ability(z) and zg.get_cash() == zc - price and zg.activate_ability(z), "Zethos unlock + fire")
    admin = _frozen()
    admin.set_admin(False, True, False)
    a = tower_near_track(admin, TowerType.GLM, 3, 450)
    check(admin.unlock_ability(a) and a.is_ability_ready(), "admin money unlocks for free")


def test_unlocked_mechanics(check):
    g = _frozen()
    r = g.get_map().get_routes()[0]
    claude = _unlocked(check, g, TowerType.CLAUDE, 300)
    opus = claude.get_ability()
    reach, rng = opus.p("radius"), claude.effective_range(g)
    d_in = d_out = -1.0
    d = 0.0
    while d < r.get_total_length():
        dist = r.position_at(d).dist(claude.get_position())
        if d_in < 0 and rng + 30 < dist < reach - 60:
            d_in = d
        if dist > reach + 60:
            d_out = d
        d += 5
    check(d_in >= 0 and d_out >= 0, "test spots exist")
    reached = spawn_at(g, EnemyType.HEAP_SORT, None, 0, d_in)
    beyond = spawn_at(g, EnemyType.HEAP_SORT, None, 0, d_out)
    boss = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, d_in + 10)
    check(g.activate_ability(claude), "Opus Time-Lock fires")
    check(reached.is_frozen() and not beyond.is_frozen(), "Time-Lock reach")
    check(abs(boss.status_magnitude(StatusKind.SLOW) - opus.p("bossSlow")) < 1e-6, "exact boss slow")
    g = _frozen()
    ds = _unlocked(check, g, TowerType.DEEPSEEK, 450)
    count = int(ds.get_ability().p("count"))
    for i in range(count + 5):
        spawn_at(g, EnemyType.TIMSORT, None, 0, 200 + i * 15)
    boss = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 650)
    bhp = boss.get_hp()
    check(g.activate_ability(ds), "R1 fires")
    left = sum(1 for e in g.get_enemy_manager().get_enemies() if e.is_alive() and not e.is_boss())
    check(left == 5, "R1 destroys the strongest (left %d)" % left)
    pct = ds.get_ability().p("bossDamagePct")
    check(bhp - boss.get_max_hp() * pct * 1.01 <= boss.get_hp() <= bhp - boss.get_max_hp() * pct * 0.9, "R1 boss strike")
    g = _frozen()
    cop = _unlocked(check, g, TowerType.COPILOT, 300)
    gpt = tower_near_track(g, TowerType.GPT, 0, 700)
    check(g.activate_ability(cop) and abs(gpt.self_rate_mult() - cop.get_ability().p("rateMult")) < 1e-9, "Auto-Refactor uncapped")
    g = _frozen()
    dalle = _unlocked(check, g, TowerType.DALLE, 450)
    t1 = _tank(g, None, 450, 500)
    hp = t1.get_hp()
    check(g.activate_ability(dalle, g.get_map().get_routes()[0].position_at(450)), "Outpainting fires")
    run_seconds(g, 1.2)
    check(t1.get_hp() < hp, "Outpainting zone burns")
    g = _frozen()
    suno = _unlocked(check, g, TowerType.SUNO, 450)
    t2 = _tank(g, None, 450, 5000)
    hp = t2.get_hp()
    exp = suno.get_ability().p("baseDamage") + suno.get_ability().p("damagePerSpeed") * t2.speed_multiplier()
    check(g.activate_ability(suno) and hp - t2.get_hp() >= exp * 0.99, "Bass Drop base + per-speed damage")
    g = _frozen()
    kimi = _unlocked(check, g, TowerType.KIMI, 450)
    for _ in range(1200):
        kimi.add_kill()
    fort = _tank(g, mods(Modifier.FORTIFIED), 450, 5000)
    hp = fort.get_hp()
    check(g.activate_ability(kimi) and hp - fort.get_hp() >= 12 * kimi.get_ability().p("damagePerStack") * 0.99, "Context Burst through Fortified")


def _fz(d):
    g = Game(maps.create(0), 42, d)
    g.set_global_enemy_speed_multiplier(0)
    return g


def test_global_damage_multiplier_everywhere(check):
    check(Difficulty.ONN.tower_damage == 0.84, "O(N^N) tower damage x0.84")

    def ratio(what, fn):
        base, hard = fn(_fz(Difficulty.O1)), fn(_fz(Difficulty.ONN))
        check(base > 0 and abs(hard - base * 0.84) < 1e-9 * max(1, base), "%s: %s vs %s" % (what, hard, base))

    def lost(e):
        return e.get_max_hp() - e.get_hp()

    def direct(g):
        t = tower_near_track(g, TowerType.GPT, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        g.get_combat().apply_hit_simple(e, HitSpec(4, DamageType.TRUE), t, t.damage_multiplier(g), 0)
        return lost(e)

    def zone(g):
        t = tower_near_track(g, TowerType.GPT, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        z = TrackZone(e.get_position(), 40, t)
        z.duration, z.tick_interval, z.tick_hit = 5, 0.5, HitSpec(2, DamageType.TRUE)
        g.get_effects().add_zone(z)
        run_seconds(g, 1.2)
        return lost(e)

    def walker(g):
        t = tower_near_track(g, TowerType.GPT, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        g.get_effects().add_walker(TrackWalker(g.get_map().get_routes()[0], 290, 320, 100, t, HitSpec(4, DamageType.TRUE)))
        run_seconds(g, 0.6)
        return lost(e)

    def node(g):
        t = tower_near_track(g, TowerType.GLM, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        p = e.get_position()
        g.get_effects().add_hazard(NodeHazard.line(t, p.add(Vec(-30, -30)), p.add(Vec(30, 30)), HitSpec(4, DamageType.TRUE), 10))
        run_seconds(g, 0.3)
        return lost(e)

    def drone(g):
        t = tower_near_track(g, TowerType.GPT, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        g.get_effects().add_drone(Drone.orbit(t, Drone.stats_for(AttackKind.INSTANT, 600, 5, 4, DamageType.TRUE, 1, 0), 30, 0))
        run_seconds(g, 0.3)
        return lost(e)

    def barrage(g):
        t = tower_near_track(g, TowerType.GPT, 0, 300)
        e = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 300)
        b = Barrage(t, HitSpec(4, DamageType.TRUE), 1, 60)
        b.stagger = 0
        g.get_effects().fire(b)
        return lost(e)

    for name, fn in (("direct", direct), ("zone", zone), ("walker", walker), ("node", node), ("drone", drone), ("barrage", barrage)):
        ratio(name, fn)


def test_no_duplicate_enemies_after_carrier_dies(check):
    g = _fz(Difficulty.O1)
    carrier = spawn_at(g, EnemyType.BUCKET_SORT, None, 0, 300)
    spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 310)
    carrier.take_damage(carrier.get_hp() + 1, 0)
    g.get_enemy_manager().update(0)
    for _ in range(4):
        es = g.get_enemy_manager().get_enemies()
        check(len({id(e) for e in es}) == len(es), "each enemy appears once")
        g.get_enemy_manager().update(0.016)


def test_grid_helpers_match_full_scan(check):
    g = _fz(Difficulty.O1)
    n_routes = len(g.get_map().get_routes())
    for i in range(60):
        spawn_at(g, EnemyType.HEAP_SORT, None, i % n_routes, 40 + i * 17)
    p = g.get_map().get_routes()[0].position_at(400)
    for r in (30, 90, 200, 700):
        want = [e for e in g.get_enemy_manager().get_enemies() if e.is_alive() and not e.is_stored() and e.get_position().dist(p) <= r]
        got = [e for e in g.get_enemy_manager().get_grid().near(p.x, p.y, r, []) if e.is_alive() and not e.is_stored() and e.get_position().dist(p) <= r]
        check(want == got, "grid query radius %s equals the full scan" % r)
