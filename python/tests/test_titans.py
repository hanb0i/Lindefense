"""Group B3: Experimental Titans (Qwen, Llama, Mistral, Cohere, GLM, Kimi, MiniMax)."""
import pytest

from kit import DT, buildable_near, force_place, mods, new_game, run_seconds, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.visual_event import VisualEvent
from lindefense.effects.effects import Drone, NodeHazard
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.jenum import EnumSet
from lindefense.javacompat import jround
from lindefense.map import maps
from lindefense.sim.game import State
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.behavior.support_titans import KimiBehavior
from lindefense.tower.tower_type import AttackKind, TowerType

T = TowerType
BASE = [(T.QWEN, 190.0, 1.0, 2.0, 4, DamageType.ENERGY, AttackKind.PROJECTILE),
        (T.LLAMA, 170.0, 2.0, 2.0, 6, DamageType.KINETIC, AttackKind.CUSTOM),
        (T.MISTRAL, 170.0, 0.7, 1.0, 3, DamageType.KINETIC, AttackKind.PROJECTILE),
        (T.COHERE, 230.0, 1.5, 3.0, 1, DamageType.EXPLOSIVE, AttackKind.PROJECTILE),
        (T.GLM, 170.0, 1.0, 1.0, 2, DamageType.GRAVITY, AttackKind.PROJECTILE),
        (T.KIMI, 180.0, 0.9, 1.0, 2, DamageType.MAGIC, AttackKind.PROJECTILE),
        (T.MINIMAX, 170.0, 0.5, 1.0, 1, DamageType.ENERGY, AttackKind.PROJECTILE)]
CAMO = mods(Modifier.CAMO)


def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _at(g, t, d):
    return spawn_at(g, t, None, 0, d)


def _near(a, b):
    return abs(a - b) < 1e-9


def _scaled(g, t, d, hp, ms=None):
    e = g.get_enemy_manager().spawn_scaled(t, ms, 0, d, hp, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _camo_at(g, t, d, hp):
    return _scaled(g, t, d, hp, CAMO)


def _shoot(g, t):
    g.get_combat().attack(t)
    for _ in range(60):
        g.get_combat().update_projectiles(DT)


def _at_point(g, t, ms, p, hp):
    tp = g.get_effects().nearest_track_point(p)
    e = g.get_enemy_manager().spawn_scaled(t, ms, tp.route_index, tp.distance, hp, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _run_pinned(g, seconds, *es):
    d = [e.get_distance() for e in es]
    for _ in range(jround(seconds / DT)):
        for e, x in zip(es, d):
            e.set_distance(x)
        g.step(DT)


def _count_zones(g, kind):
    return sum(1 for z in g.get_effects().get_zones() if z.is_alive() and z.kind == kind)


def _beams(g):
    return sum(1 for ev in g.get_events() if ev.kind == VisualEvent.BEAM)


def test_base_stats_match_spec(check):
    for t, rng, interval, dmg, pierce, dt, kind in BASE:
        s = catalog.get(t).base_stats
        check(_near(s.range, rng) and abs(s.interval() - interval) < 1e-9 and _near(s.hit.damage, dmg)
              and s.pierce == pierce and s.hit.type is dt and s.kind is kind, "%s base stats" % t)
    check(_near(catalog.get(T.QWEN).base_stats.projectile_speed, 500), "Qwen disc speed 500")
    l = catalog.get(T.LLAMA).base_stats
    check(l.p("chargeSegment") == 150 and l.p("chargeCount") == 1, "Llama charge")
    check(catalog.get(T.MISTRAL).base_stats.hit.knockback_vs_fast == 15, "Mistral knockback on fast")
    check(catalog.get(T.COHERE).base_stats.splash_radius == 60, "Cohere splash 60")
    check(_near(catalog.get(T.GLM).base_stats.hit.slow_fraction, 0.10), "GLM slows 10%")
    k = catalog.get(T.KIMI).base_stats
    check(k.p("streakMax") == 3 and _near(k.hit.mult_vs_fortified, 0.5), "Kimi base")
    m = catalog.get(T.MINIMAX).base_stats
    check(m.bounces == 3 and _near(m.p("bounceSpeedGain"), 0.10), "MiniMax base")


def test_upgrade_stats_match_spec(check):
    def s(t, i):
        return catalog.get(t).stats_for_tier(i)
    check(s(T.QWEN, 1).pierce == 8 and s(T.QWEN, 1).projectiles_per_shot == 3, "Qwen U1")
    check(s(T.QWEN, 2).p("droneCount") == 2 and s(T.QWEN, 2).p("droneInterval") == 1.2, "Qwen U2")
    check(s(T.QWEN, 3).hit.damage == 4 and s(T.QWEN, 3).hit.mult_vs_high_hp == 3, "Qwen U3")
    check(s(T.LLAMA, 1).p("chargeCount") == 3, "Llama U1")
    check(s(T.LLAMA, 2).sees_camo and s(T.LLAMA, 2).pierce == 12, "Llama U2")
    x = s(T.LLAMA, 3)
    check(x.p("shockInterval") == 4 and x.p("shockDamage") == 8 and x.p("shockKnockback") == 40 and x.p("shockBossMult") == 2, "Llama U3")
    x = s(T.MISTRAL, 1)
    check(x.p("gustInterval") == 3 and x.p("gustFast") == 60 and x.p("gustOther") == 25, "Mistral U1")
    x = s(T.MISTRAL, 2)
    check(x.p("tornadoInterval") == 8 and x.p("tornadoDuration") == 5 and x.p("tornadoTick") == 0.3 and x.p("tornadoDamage") == 1, "Mistral U2")
    x = s(T.MISTRAL, 3)
    check(x.p("vortexRadius") == 70 and x.p("vortexTick") == 0.3 and x.p("vortexDamage") == 2 and x.p("vortexSlow") == 0.3
          and x.p("vortexBossMult") == 2, "Mistral U3")
    x = s(T.COHERE, 1)
    check(x.p("shrapnelCount") == 8 and x.p("shrapnelDamage") == 1 and x.p("shrapnelPierce") == 2, "Cohere U1")
    x = s(T.COHERE, 2)
    check(x.hit.armor_break > 0 and x.hit.armor_break_duration == 5 and _near(x.hit.mark_bonus, 0.5) and x.hit.mark_duration == 5, "Cohere U2")
    x = s(T.COHERE, 3)
    check(x.hit.damage == 10 and x.splash_radius == 90 and abs(x.interval() - 1.1) < 1e-9 and x.hit.mult_vs_boss == 3, "Cohere U3")
    check(s(T.GLM, 1).p("nodes") == 2 and s(T.GLM, 1).p("lineDamage") == 2 and s(T.GLM, 1).p("lineCooldown") == 0.3, "GLM U1")
    check(s(T.GLM, 2).p("nodes") == 4 and s(T.GLM, 2).p("gridSlow") == 0.30, "GLM U2")
    check(s(T.GLM, 3).p("nodes") == 6 and s(T.GLM, 3).p("lineDamage") == 5 and s(T.GLM, 3).p("lineFortifiedMult") == 2, "GLM U3")
    check(s(T.KIMI, 1).p("memoryPer") == 100 and s(T.KIMI, 1).p("memoryCap") == 5, "Kimi U1")
    check(s(T.KIMI, 2).p("streakMax") == 8 and s(T.KIMI, 2).p("pierceBonusPerStack") == 1, "Kimi U2")
    x = s(T.KIMI, 3)
    check(x.p("memoryCap") == 12 and x.p("burstEvery") == 10 and x.p("burstDamage") == 15 and x.p("burstSplash") == 70, "Kimi U3")
    check(s(T.MINIMAX, 1).bounces == 6 and s(T.MINIMAX, 1).p("cloneCount") == 1, "MiniMax U1")
    check(s(T.MINIMAX, 2).clones == 2, "MiniMax U2")
    x = s(T.MINIMAX, 3)
    check(x.p("cloneCount") == 3 and x.p("barrageInterval") == 6 and x.p("barrageCount") == 20, "MiniMax U3")
    for row in BASE:
        check(catalog.get(row[0]).ability is not None and catalog.ability_needs_unlock(row[0]), "%s ability locked" % row[0])


def test_base_attacks_damage_enemies(check):
    for row in BASE:
        g = _frozen()
        t = tower_near_track(g, row[0], 0, 400)
        e = _at(g, EnemyType.QUICK_SORT, 400)
        run_seconds(g, 5)
        check(t.get_damage_dealt() > 0 and e.get_hp() < e.get_max_hp(), "%s base attack damages an enemy" % row[0])


def test_qwen(check):
    g = _frozen()
    q = tower_near_track(g, T.QWEN, 1, 400)
    _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 30)
    g.get_combat().attack(q)
    g.get_combat().update_projectiles(0)
    check(len(g.get_combat().get_projectiles()) == 3, "U1 fires 3 discs per attack")
    g2 = _frozen()
    q3 = tower_near_track(g2, T.QWEN, 3, 400)
    small = _scaled(g2, EnemyType.STATIC_ARRAY, 400, 30)
    big = _scaled(g2, EnemyType.MERGE_SORT, 410, 30)
    check(_near(g2.get_combat().apply_hit_simple(small, q3.get_stats().hit, q3, 1, 0), 4), "damage 4 vs small enemies")
    check(_near(g2.get_combat().apply_hit_simple(big, q3.get_stats().hit, q3, 1, 0), 12), "x3 vs base HP >= 5")


def test_llama(check):
    g = _frozen()
    l = tower_near_track(g, T.LLAMA, 0, 450)
    check(not g.get_combat().attack(l), "no charge without an enemy in range")
    e = _scaled(g, EnemyType.HEAP_SORT, 450, 5)
    check(g.get_combat().attack(l), "a llama charges")
    ws = g.get_effects().get_walkers()
    check(len(ws) == 1 and ws[0].route is e.get_route(), "one llama on the enemy's route")
    run_seconds(g, 2.5)
    check(e.get_hp() < e.get_max_hp() and l.get_damage_dealt() >= 2, "the llama's contact damages the enemy")
    g2 = _frozen()
    l1 = tower_near_track(g2, T.LLAMA, 1, 450)
    _scaled(g2, EnemyType.HEAP_SORT, 450, 5)
    g2.get_combat().attack(l1)
    check(len(g2.get_effects().get_walkers()) == 3, "U1 sends 3 charging creatures")
    g3 = _frozen()
    l2 = tower_near_track(g3, T.LLAMA, 2, 450)
    spawn_at(g3, EnemyType.HEAP_SORT, CAMO, 0, 450)
    check(l2.can_see_camo() and g3.get_combat().attack(l2), "U2 sees camo and charges at it")
    w = g3.get_effects().get_walkers()[0]
    check(w.pierce == 12 and w.detection, "U2 spectral creatures")
    g4 = _frozen()
    lb = tower_near_track(g4, T.LLAMA, 0, 450)
    grp = [spawn_at(g4, EnemyType.HEAP_SORT, None, 0, 400 + i * 12) for i in range(8)]
    g4.get_combat().attack(lb)
    g4.run(3 * 60)
    n = sum(1 for x in grp if x.get_hp() < x.get_max_hp() or not x.is_alive())
    check(6 <= n <= 7, "base llama pierce 6: %d" % n)


def test_mistral(check):
    g = _frozen()
    m = tower_near_track(g, T.MISTRAL, 0, 400)
    fast = _scaled(g, EnemyType.SINGLY_LINKED_LIST, 500, 20)
    shell = _scaled(g, EnemyType.SHELL_SORT, 520, 20)
    slow = _scaled(g, EnemyType.MERGE_SORT, 540, 20)
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 560)
    h = m.get_stats().hit
    for e in (fast, shell, slow, boss):
        g.get_combat().apply_hit_simple(e, h, m, 1, 0)
    check(fast.get_distance() == 485, "Linked Lists knocked back 15 px")
    check(shell.get_distance() == 505, "2.0x speed enemies knocked back")
    check(slow.get_distance() == 540, "slow enemies not knocked back")
    check(boss.get_distance() == 560, "bosses immune")


def test_cohere(check):
    g = _frozen()
    c = tower_near_track(g, T.COHERE, 0, 400)
    a = _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 20)
    b = _scaled(g, EnemyType.DYNAMIC_ARRAY, 430, 20)
    far = _scaled(g, EnemyType.DYNAMIC_ARRAY, 900, 20)
    g.get_combat().attack(c)
    for _ in range(80):
        g.get_combat().update_projectiles(DT)
    check(a.get_hp() < a.get_max_hp() and b.get_hp() < b.get_max_hp() and far.get_hp() == far.get_max_hp(), "splash hits the group only")
    camo = spawn_at(g, EnemyType.QUICK_SORT, CAMO, 0, 410)
    check(g.get_combat().apply_hit_simple(camo, c.get_stats().hit, c, 1, 0) == 0, "Cohere cannot pop Camo")
    g2 = _frozen()
    c2 = tower_near_track(g2, T.COHERE, 2, 400)
    e = _scaled(g2, EnemyType.HEAP_SORT, 400, 20)
    g2.get_combat().apply_hit_simple(e, c2.get_stats().hit, c2, 1, 0)
    check(e.is_armor_cracked() and _near(e.get_marked_bonus(), 0.5), "U2 crack + mark")
    e.tick_statuses(5.1)
    check(not e.is_armor_cracked() and e.get_marked_bonus() == 0, "...for 5 s")
    c3 = force_place(g2, T.COHERE, buildable_near(g2, Vec(1100, 840), 100), 3)
    boss = _at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 700)
    check(_near(g2.get_combat().apply_hit_simple(boss, c3.get_stats().hit, c3, 1, 0), 10 * 3 * 0.75), "U3 x3 vs MOAB")


def test_glm(check):
    g = _frozen()
    t = tower_near_track(g, T.GLM, 0, 400)
    e = _scaled(g, EnemyType.HEAP_SORT, 400, 20)
    g.get_combat().apply_hit_simple(e, t.get_stats().hit, t, 1, 0)
    check(_near(e.get_slow_fraction(), 0.10), "GRAVITY pebble slows 10%")


def test_kimi(check):
    g = _frozen()
    k = tower_near_track(g, T.KIMI, 0, 400)
    e = _scaled(g, EnemyType.BELLARMINE_COLLEGE_PREP, 400, 100)
    for i, exp in enumerate((1, 2, 3, 4, 4, 4)):
        hp = e.get_hp()
        _shoot(g, k)
        check(_near((hp - e.get_hp()) / 0.75, exp), "consecutive hit %d deals %d" % (i + 1, exp))
    k1 = force_place(g, T.KIMI, buildable_near(g, Vec(1100, 840), 100), 1)
    check(KimiBehavior.memory_stacks(k1) == 0, "no memory at start")
    for _ in range(250):
        k1.add_kill()
    check(KimiBehavior.memory_stacks(k1) == 2, "250 pops = +2")
    g2 = _frozen()
    k2 = tower_near_track(g2, T.KIMI, 1, 400)
    for _ in range(300):
        k2.add_kill()
    boss = _scaled(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 400, 100)
    hp = boss.get_hp()
    _shoot(g2, k2)
    check(_near((hp - boss.get_hp()) / 0.75, 4), "memory +3 adds to the first shot")
    fortified = g2.get_enemy_manager().spawn_scaled(EnemyType.QUICK_SORT, mods(Modifier.FORTIFIED), 0, 395, 20, 1)
    g2.get_enemy_manager().update(0)
    check(_near(g2.get_combat().apply_hit_simple(fortified, k2.get_stats().hit, k2, 1, 0), 0.5), "x0.5 vs Fortified")
    g3 = _frozen()
    k3 = tower_near_track(g3, T.KIMI, 2, 400)
    _scaled(g3, EnemyType.BELLARMINE_COLLEGE_PREP, 400, 100)
    _shoot(g3, k3)
    _shoot(g3, k3)
    _shoot(g3, k3)
    g3.get_combat().attack(k3)
    g3.get_combat().update_projectiles(0)
    ps = g3.get_combat().get_projectiles()
    check(ps and ps[-1].get_shot().pierce == k3.get_stats().pierce + 3, "U2: +1 pierce per stack")


def test_minimax(check):
    g = _frozen()
    m = tower_near_track(g, T.MINIMAX, 0, 400)
    es = [_scaled(g, EnemyType.HEAP_SORT, d, 20) for d in (400, 480, 560)]
    g.get_combat().attack(m)
    speed0 = m.get_stats().projectile_speed
    p = None
    for _ in range(200):
        if p is not None and p.get_bounces_left() != m.get_stats().bounces:
            break
        g.get_combat().update_projectiles(DT)
        if g.get_combat().get_projectiles():
            p = g.get_combat().get_projectiles()[0]
    check(p is not None and p.get_bounces_left() == m.get_stats().bounces - 1, "the packet bounced once")
    check(p is not None and abs(p.get_velocity().length() - speed0 * 1.1) < 1e-6, "+10% speed per bounce")
    for _ in range(400):
        g.get_combat().update_projectiles(DT)
    check(sum(1 for e in es if e.get_hp() < e.get_max_hp()) == 3, "one packet bounced across all three")
    g2 = _frozen()
    m2 = tower_near_track(g2, T.MINIMAX, 2, 400)
    for d in (400, 430, 460):
        _scaled(g2, EnemyType.HEAP_SORT, d, 20)
    g2.get_combat().attack(m2)
    mx = 0
    for _ in range(100):
        g2.get_combat().update_projectiles(DT)
        mx = max(mx, len(g2.get_combat().get_projectiles()))
    check(mx >= 2, "U2 packet splits into 2 (peak %d)" % mx)


def test_qwen_drone_formation(check):
    g1 = _frozen()
    q1 = tower_near_track(g1, T.QWEN, 1, 400)
    g1.run(120)
    check(not g1.get_effects().drones_of(q1, "qwen"), "no drones before U2")
    g = _frozen()
    q = tower_near_track(g, T.QWEN, 2, 400)
    g.run(120)
    ds = g.get_effects().drones_of(q, "qwen")
    check(len(ds) == 2, "U2 keeps 2 patrol drones")
    for d in ds:
        check(d.mode is Drone.PATROL and not d.mirror_owner, "drones patrol with their own stats")
        check(d.get_position().dist(q.get_position()) > q.get_stats().range, "drones patrol other segments")
        st = d.stats
        check(_near(st.interval(), 1.2) and _near(st.hit.damage, 2) and st.pierce == 8 and st.projectiles_per_shot == 3
              and _near(st.range, 190) and st.hit.type is DamageType.ENERGY and _near(st.projectile_speed, 500), "drone stats")
    check(ds[0].get_position().dist(ds[1].get_position()) > 20, "drones cover different segments")
    victim = _at_point(g, EnemyType.DYNAMIC_ARRAY, None, ds[0].get_position(), 300)
    check(victim.get_position().dist(q.get_position()) > q.get_stats().range, "victim outside tower range")
    g.run(180)
    check(victim.get_hp() < victim.get_max_hp() and q.get_damage_dealt() > 0, "drone discs damage and credit Qwen")
    g.get_tower_manager().upgrade(q)
    g.run(10)
    ds = g.get_effects().drones_of(q, "qwen")
    check(len(ds) == 2 and ds[0].stats.hit.damage == 4 and ds[0].stats.hit.mult_vs_high_hp == 3, "U3 drones copy new stats")
    check(_near(ds[0].stats.interval(), 1.2), "...at interval 1.2")
    g.sell_tower(q)
    g.run(5)
    check(not g.get_effects().get_drones(), "selling Qwen removes its drones")


def test_qwen_u3_fortified_boss(check):
    g = _frozen()
    q = tower_near_track(g, T.QWEN, 3, 400)
    plain = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 900)
    fort = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, mods(Modifier.FORTIFIED), 0, 1000)
    a = g.get_combat().apply_hit_simple(plain, q.get_stats().hit, q, 1, 0)
    b = g.get_combat().apply_hit_simple(fort, q.get_stats().hit, q, 1, 0)
    check(a > 0 and _near(b / a, 1.0), "x3 applies to plain and Fortified MOAB alike")
    check(_near(a, 4 * 3 * 0.75), "U3: 4 x3 vs MOAB after armour")


def test_llama_mythical_stampede(check):
    g = _frozen()
    l = tower_near_track(g, T.LLAMA, 3, 400)
    n1 = _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 100)
    n2 = _scaled(g, EnemyType.DYNAMIC_ARRAY, 360, 100)
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 440)
    far = _scaled(g, EnemyType.DYNAMIC_ARRAY, 900, 100)
    mult = l.damage_multiplier(g)
    l.get_behavior().update(g, l, 3.9)
    check(n1.get_hp() == n1.get_max_hp(), "no shockwave before 4 s")
    l.get_behavior().update(g, l, 0.2)
    check(_near(n1.get_max_hp() - n1.get_hp(), 8 * mult), "shockwave deals 8")
    check(_near(n1.get_distance(), 360) and _near(n2.get_distance(), 320), "KNOCKBACK 40 px")
    check(_near(boss.get_max_hp() - boss.get_hp(), 8 * 2 * mult * 0.75), "x2 vs MOAB")
    check(boss.get_distance() == 440, "bosses not knocked back")
    check(far.get_hp() == far.get_max_hp() and far.get_distance() == 900, "out of range untouched")
    l.get_behavior().update(g, l, 4.0)
    check(_near(n1.get_distance(), 320), "uncapped second push")
    g2 = _frozen()
    l2 = tower_near_track(g2, T.LLAMA, 2, 400)
    e = _scaled(g2, EnemyType.DYNAMIC_ARRAY, 400, 100)
    l2.get_behavior().update(g2, l2, 10)
    check(e.get_hp() == e.get_max_hp(), "U2 has no shockwave")
    g3 = _frozen()
    tower_near_track(g3, T.LLAMA, 3, 400)
    e3 = _camo_at(g3, EnemyType.DYNAMIC_ARRAY, 400, 100)
    run_seconds(g3, 4.1)
    check(e3.get_distance() <= 360 + 1e-9, "the shockwave fires from the sim loop")


def test_llama_camo_respected(check):
    g = _frozen()
    l = tower_near_track(g, T.LLAMA, 0, 450)
    seen = _scaled(g, EnemyType.DYNAMIC_ARRAY, 440, 50)
    camo = _camo_at(g, EnemyType.DYNAMIC_ARRAY, 460, 50)
    g.get_combat().attack(l)
    run_seconds(g, 0.5)
    check(seen.get_hp() < seen.get_max_hp() and camo.get_hp() == camo.get_max_hp(), "base creatures cannot hurt Camo")
    g2 = _frozen()
    l2 = tower_near_track(g2, T.LLAMA, 2, 450)
    camo2 = _camo_at(g2, EnemyType.DYNAMIC_ARRAY, 460, 50)
    g2.get_combat().attack(l2)
    run_seconds(g2, 0.5)
    check(camo2.get_hp() < camo2.get_max_hp(), "Illusion Pack creatures hit Camo")


def test_mistral_gust(check):
    g = _frozen()
    m = tower_near_track(g, T.MISTRAL, 1, 400)
    fast = _scaled(g, EnemyType.SINGLY_LINKED_LIST, 450, 50)
    other = _scaled(g, EnemyType.MERGE_SORT, 360, 50)
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 420)
    far = _scaled(g, EnemyType.DYNAMIC_ARRAY, 800, 50)
    m.get_behavior().update(g, m, 2.9)
    check(fast.get_distance() == 450, "no gust before 3 s")
    m.get_behavior().update(g, m, 0.2)
    check(_near(fast.get_distance(), 390), "fast enemies back 60 px")
    check(_near(other.get_distance(), 335), "other enemies back 25 px")
    check(boss.get_distance() == 420 and far.get_distance() == 800, "bosses / out of range untouched")
    g0 = _frozen()
    m0 = tower_near_track(g0, T.MISTRAL, 0, 400)
    e0 = _scaled(g0, EnemyType.DYNAMIC_ARRAY, 400, 50)
    m0.get_behavior().update(g0, m0, 9)
    check(e0.get_distance() == 400, "base Mistral has no gust")


def test_mistral_cyclone(check):
    g = _frozen()
    m = tower_near_track(g, T.MISTRAL, 2, 400)
    m.get_behavior().update(g, m, 8.1)
    check(_count_zones(g, "tornado") == 0, "no enemy: no tornado")
    decoy = _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 1000)
    victim = _camo_at(g, EnemyType.DYNAMIC_ARRAY, 400, 1000)
    m.get_behavior().update(g, m, 0.01)
    check(_count_zones(g, "tornado") == 1, "a tornado appears on the first enemy")
    z = g.get_effects().zones_of(m, "tornado")[0]
    check(_near(z.radius, 45) and _near(z.duration, 5) and _near(z.tick_interval, 0.3) and not z.permanent, "tornado 5 s")
    check(z.center.dist(decoy.get_position()) < 1e-6, "centred on the enemy")
    hp = victim.get_hp()
    _run_pinned(g, 5.2, victim, decoy)
    dealt = hp - victim.get_hp()
    check(15 <= dealt <= 17, "1 damage every 0.3 s for 5 s: %s" % dealt)
    g1 = _frozen()
    m1 = tower_near_track(g1, T.MISTRAL, 1, 400)
    _scaled(g1, EnemyType.DYNAMIC_ARRAY, 400, 1000)
    m1.get_behavior().update(g1, m1, 20)
    check(_count_zones(g1, "tornado") == 0, "U1 has no tornado")


def test_mistral_hurricane(check):
    g = _frozen()
    b = g.get_map().get_routes()[0].get_waypoints()[1]
    m = force_place(g, T.MISTRAL, buildable_near(g, b.add(Vec(0, -60)), 80), 3)
    check(m.get_position().dist(b) <= m.get_stats().range, "a bend is in range")
    run_seconds(g, 1)
    check(_count_zones(g, "vortex") == 1, "U3 creates one vortex")
    z = g.get_effects().zones_of(m, "vortex")[0]
    check(z.permanent and _near(z.radius, 70) and _near(z.tick_interval, 0.3), "vortex params")
    check(any(w.dist(z.center) < 1e-6 for w in g.get_map().get_routes()[0].get_waypoints()), "the vortex sits on a bend")
    e = _at_point(g, EnemyType.DYNAMIC_ARRAY, CAMO, z.center, 300)
    boss = _at_point(g, EnemyType.BELLARMINE_COLLEGE_PREP, CAMO, z.center, 1)
    hp, bhp = e.get_hp(), boss.get_hp()
    _run_pinned(g, 3, e, boss)
    dealt, bdealt = hp - e.get_hp(), bhp - boss.get_hp()
    check(18 <= dealt <= 22, "2 damage every 0.3 s: %s" % dealt)
    check(_near(bdealt / dealt, 2 * 0.75), "x2 vs MOAB after armour")
    check(_near(e.get_slow_fraction(), 0.30) and _near(boss.get_slow_fraction(), 0.10), "slows")
    run_seconds(g, 20)
    check(_count_zones(g, "vortex") == 1, "permanent, never duplicated")
    g.sell_tower(m)
    run_seconds(g, 0.2)
    check(_count_zones(g, "vortex") == 0, "selling removes the vortex")


def test_cohere_fragmentation(check):
    g = _frozen()
    c = tower_near_track(g, T.COHERE, 1, 400)
    target = _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 300)
    ring = []
    for i in range(1, 7):
        ring.append(_scaled(g, EnemyType.DYNAMIC_ARRAY, 400 + i * 15, 300))
        ring.append(_scaled(g, EnemyType.DYNAMIC_ARRAY, 400 - i * 15, 300))
    g.get_events().clear()
    g.get_combat().attack(c)
    for _ in range(90):
        g.get_combat().update_projectiles(DT)
    check(_beams(g) == 8, "one burst of 8 shrapnel per shell: %d" % _beams(g))
    shell = 3 * 0.75
    check(sum(1 for e in ring if e.get_max_hp() - e.get_hp() > shell + 1e-6) > 0, "shrapnel damages around the impact")
    check(max(e.get_max_hp() - e.get_hp() for e in ring) >= shell + 0.75 - 1e-6, "shrapnel damage 1 on top")
    check(target.get_hp() < target.get_max_hp(), "the struck enemy is hit")
    g0 = _frozen()
    c0 = tower_near_track(g0, T.COHERE, 0, 400)
    _scaled(g0, EnemyType.DYNAMIC_ARRAY, 400, 300)
    g0.get_events().clear()
    g0.get_combat().attack(c0)
    for _ in range(90):
        g0.get_combat().update_projectiles(DT)
    check(_beams(g0) == 0, "base Cohere has no shrapnel")


def test_glm_node_network(check):
    g = _frozen()
    t = tower_near_track(g, T.GLM, 0, 400)
    run_seconds(g, 1)
    check(not g.get_effects().get_hazards(), "no nodes at base")
    g.get_tower_manager().upgrade(t)
    check(len(g.get_effects().get_hazards()) == 1, "U1 places a network")
    h = g.get_effects().get_hazards()[0]
    check(len(h.nodes) == 2 and len(h.links) == 1 and h.region is None, "2 nodes joined by one line")
    for n in h.nodes:
        check(n.dist(t.get_position()) <= t.get_stats().range + 40, "nodes within range")
    mid = Vec.lerp(h.nodes[0], h.nodes[1], 0.5)
    e = _at_point(g, EnemyType.DYNAMIC_ARRAY, CAMO, mid, 300)
    hp = e.get_hp()
    run_seconds(g, 0.25)
    check(_near(hp - e.get_hp(), 2), "crossing the line takes 2")
    run_seconds(g, 0.75)
    check(6 <= hp - e.get_hp() <= 10, "at most once every 0.3 s")
    g.get_tower_manager().upgrade(t)
    alive = [x for x in g.get_effects().get_hazards() if x.is_alive()]
    check(len(alive) == 1, "U2 replaces the network")
    h2 = g.get_effects().get_hazards()[-1]
    check(len(h2.nodes) == 4 and h2.region is not None and _near(h2.region_slow, 0.30), "U2 grid")
    g.get_tower_manager().upgrade(t)
    g.run(1)
    check(len([x for x in g.get_effects().get_hazards() if x.is_alive()]) == 1, "U3 replaces the network")
    h3 = g.get_effects().get_hazards()[-1]
    check(len(h3.nodes) == 6 and _near(h3.line_hit.damage, 5) and _near(h3.line_hit.mult_vs_fortified, 2), "U3 grid")
    check(len(h3.links) > len(h3.nodes), "interior links")
    g.sell_tower(t)
    g.run(5)
    check(not [x for x in g.get_effects().get_hazards() if x.is_alive()], "selling removes the nodes")


def test_glm_grid_slow_and_fortified(check):
    g = _frozen()
    tower_near_track(g, T.GLM, 3, 400)
    g.run(30)
    h = g.get_effects().get_hazards()[0]
    check(any(l[0] == 1 and l[1] == 4 for l in h.links), "interior rung present")
    centre = Vec.lerp(h.nodes[1], h.nodes[4], 0.5)
    plain = _at_point(g, EnemyType.DYNAMIC_ARRAY, CAMO, centre, 300)
    fort = _at_point(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO, Modifier.FORTIFIED), centre, 300)
    boss = _at_point(g, EnemyType.BELLARMINE_COLLEGE_PREP, CAMO, centre, 1)
    p0, f0 = plain.get_hp(), fort.get_hp()
    run_seconds(g, 0.05)
    check(p0 - plain.get_hp() >= 5 - 1e-9, "U3 line damage 5")
    check(_near((f0 - fort.get_hp()) / (p0 - plain.get_hp()), 2), "x2 vs Fortified")
    check(_near(plain.get_slow_fraction(), 0.30) and _near(boss.get_slow_fraction(), 0.10), "web slows")
    away = _camo_at(g, EnemyType.DYNAMIC_ARRAY, 1000, 300)
    run_seconds(g, 1)
    check(away.get_hp() == away.get_max_hp() and away.get_slow_fraction() == 0, "outside the web nothing happens")


def test_kimi_crystal_burst(check):
    g = _frozen()
    k = tower_near_track(g, T.KIMI, 3, 400)
    _scaled(g, EnemyType.BELLARMINE_COLLEGE_PREP, 400, 1000)
    n = _camo_at(g, EnemyType.DYNAMIC_ARRAY, 430, 1000)
    f = _scaled(g, EnemyType.DYNAMIC_ARRAY, 410, 1000, mods(Modifier.CAMO, Modifier.FORTIFIED))
    for _ in range(9):
        _shoot(g, k)
    check(n.get_hp() == n.get_max_hp(), "only the burst touches Camo")
    _shoot(g, k)
    mult = k.damage_multiplier(g)
    check(_near(n.get_max_hp() - n.get_hp(), 15 * mult), "10th attack fires a crystal burst")
    check(_near(f.get_max_hp() - f.get_hp(), 15 * 0.5 * mult), "x0.5 vs Fortified")
    after = n.get_hp()
    for _ in range(9):
        _shoot(g, k)
    check(n.get_hp() == after, "no burst on attacks 11-19")
    _shoot(g, k)
    check(_near(after - n.get_hp(), 15 * mult), "again on the 20th")
    outside = _camo_at(g, EnemyType.DYNAMIC_ARRAY, 500, 1000)
    for _ in range(10):
        _shoot(g, k)
    check(outside.get_hp() == outside.get_max_hp(), "burst splash is 70 px")
    g2 = _frozen()
    k2 = tower_near_track(g2, T.KIMI, 2, 400)
    _scaled(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 400, 1000)
    n2 = _camo_at(g2, EnemyType.DYNAMIC_ARRAY, 420, 1000)
    for _ in range(12):
        _shoot(g2, k2)
    check(n2.get_hp() == n2.get_max_hp(), "U2 has no crystal burst")


def test_kimi_memory_and_fortified(check):
    g = _frozen()
    k = tower_near_track(g, T.KIMI, 1, 400)
    e = _scaled(g, EnemyType.DYNAMIC_ARRAY, 400, 1)
    g.get_combat().apply_hit_simple(e, HitSpec(1e9, DamageType.TRUE), k, 1, 0)
    g.get_enemy_manager().update(0)
    check(k.get_kills() == 1, "a pop credited to Kimi counts as memory")
    for _ in range(199):
        k.add_kill()
    check(KimiBehavior.memory_stacks(k) == 2, "200 pops = +2")
    fort = _scaled(g, EnemyType.DYNAMIC_ARRAY, 380, 300, mods(Modifier.FORTIFIED))
    check(_near(g.get_combat().apply_hit_simple(fort, k.get_stats().hit, k, 1, 2), 1.5), "memory damage also x0.5 vs Fortified")
    g0 = _frozen()
    k0 = tower_near_track(g0, T.KIMI, 0, 400)
    for _ in range(1000):
        k0.add_kill()
    check(KimiBehavior.memory_stacks(k0) == 0, "no memory before U1")


def test_minimax_clones(check):
    for tier in range(4):
        g = _frozen()
        m = tower_near_track(g, T.MINIMAX, tier, 400)
        _scaled(g, EnemyType.HEAP_SORT, 400, 100000)
        peak = 0
        for _ in range(4):
            g.step(DT)
            peak = max(peak, len(g.get_combat().get_projectiles()))
        clones = len(g.get_effects().drones_of(m, "clone"))
        expected = 0 if tier == 0 else (1 if tier < 3 else 3)
        check(clones == expected, "tier %d has %d clones" % (tier, expected))
        check(peak == 1 + expected, "tier %d: tower + clones fire together (%d)" % (tier, peak))
        for d in g.get_effects().drones_of(m, "clone"):
            check(d.mode is Drone.ORBIT and d.stats.bounces == m.get_stats().bounces and d.stats.clones == m.get_stats().clones, "clone copies base attack")
            check(_near(d.stats.hit.damage, 1), "clone damage 1")
    g = _frozen()
    m = tower_near_track(g, T.MINIMAX, 1, 400)
    g.run(5)
    check(len(g.get_effects().get_drones()) == 1, "one clone only")
    g.get_tower_manager().upgrade(m)
    g.get_tower_manager().upgrade(m)
    g.run(5)
    check(len(g.get_effects().drones_of(m, "clone")) == 3 and len(g.get_effects().get_drones()) == 3, "U3: 3 clones")
    g.sell_tower(m)
    g.run(3)
    check(not g.get_effects().get_drones(), "selling removes the clones")


def test_minimax_barrage(check):
    g = _frozen()
    m = tower_near_track(g, T.MINIMAX, 3, 400)
    cb = g.get_combat()
    m.get_behavior().update(g, m, 6.0)
    cb.update_projectiles(0)
    check(not cb.get_projectiles(), "no barrage without a target")
    _scaled(g, EnemyType.HEAP_SORT, 400, 100000)
    m.get_behavior().update(g, m, 0.01)
    cb.update_projectiles(0)
    check(len(cb.get_projectiles()) == 20, "a barrage of 20 packets")
    check(cb.get_projectiles()[0].get_bounces_left() == 6, "base packets (6 bounces)")
    for _ in range(600):
        cb.update_projectiles(DT)
    check(not cb.get_projectiles(), "all packets expire")
    m.get_behavior().update(g, m, 5.9)
    cb.update_projectiles(0)
    check(not cb.get_projectiles(), "not before 6 s")
    m.get_behavior().update(g, m, 0.2)
    cb.update_projectiles(0)
    check(len(cb.get_projectiles()) == 20, "fires every 6 s")
    g2 = _frozen()
    m2 = tower_near_track(g2, T.MINIMAX, 3, 400)
    a = _scaled(g2, EnemyType.HEAP_SORT, 380, 100000)
    b = _scaled(g2, EnemyType.HEAP_SORT, 420, 100000)
    m2.get_behavior().update(g2, m2, 6.0)
    g2.get_combat().update_projectiles(0)
    ps = g2.get_combat().get_projectiles()
    check(sum(1 for p in ps if p.get_target() is a) == 10 and sum(1 for p in ps if p.get_target() is b) == 10, "spread over targets")
    g3 = _frozen()
    m3 = tower_near_track(g3, T.MINIMAX, 2, 400)
    _scaled(g3, EnemyType.HEAP_SORT, 400, 100000)
    m3.get_behavior().update(g3, m3, 20)
    g3.get_combat().update_projectiles(0)
    check(not g3.get_combat().get_projectiles(), "U2 has no barrage")


@pytest.mark.slow
def test_stress_titans(check):
    types = [T.QWEN, T.LLAMA, T.MISTRAL, T.COHERE, T.GLM, T.KIMI, T.MINIMAX]
    for mi in range(maps.MAP_COUNT):
        g = new_game(mi)
        g.set_invincible(True)
        g.set_global_enemy_speed_multiplier(0.35)
        g.add_cash(5_000_000, None)
        placed = 0
        done = False
        for r in g.get_map().get_routes():
            d = 80.0
            while d < r.get_total_length() and not done:
                direction = r.direction_at(d)
                for side in (-1, 1):
                    p = r.position_at(d).add(Vec(-direction.y, direction.x).scale(side * 75))
                    if placed >= len(types):
                        done = True
                        break
                    if g.get_tower_manager().can_place(types[placed], p):
                        t = g.place_tower(types[placed], p)
                        while g.upgrade_tower(t):
                            pass
                        placed += 1
                d += 110
            if done:
                break
        check(placed == len(types), "%s fits the 7 titans" % g.get_map().get_name())
        for _ in range(1, 94):
            g.get_wave_manager().start_next_wave()
            g.get_wave_manager().end_wave()
        pk = dict(drones=0, zones=0, walkers=0, hazards=0, proj=0)
        for wave in range(94, 101):
            g.get_wave_manager().end_wave()
            g.get_enemy_manager().clear()
            check(g.start_next_wave(), "start wave %d" % wave)
            n = 0
            while g.get_wave_manager().is_wave_active() and n < 60 * 120 and g.get_state() is State.PLAYING:
                g.step(DT)
                if n % 60 == 0:
                    for t in list(g.get_tower_manager().get_towers()):
                        if t.is_ability_ready():
                            if t.get_ability().needs_target:
                                g.activate_ability(t, g.get_map().get_routes()[0].position_at(400))
                            else:
                                g.activate_ability(t)
                fx = g.get_effects()
                pk["drones"] = max(pk["drones"], len(fx.get_drones()))
                pk["zones"] = max(pk["zones"], len(fx.get_zones()))
                pk["walkers"] = max(pk["walkers"], len(fx.get_walkers()))
                pk["hazards"] = max(pk["hazards"], len(fx.get_hazards()))
                pk["proj"] = max(pk["proj"], len(g.get_combat().get_projectiles()))
                g.get_events().clear()
                n += 1
            if g.get_state() is not State.PLAYING:
                break
        check(g.get_state() in (State.PLAYING, State.VICTORY), "titan stress sane state")
        check(pk["drones"] <= 5 and pk["hazards"] <= 1 and pk["zones"] <= 5 and pk["walkers"] <= 120 and pk["proj"] <= 4000, "bounded: %r" % pk)
        g.get_enemy_manager().clear()
        for _ in range(60 * 40):
            g.get_effects().update(DT)
            g.get_combat().update_projectiles(DT)
        check(not g.get_combat().get_projectiles() and not g.get_effects().get_walkers(), "projectiles and walkers expire")
        check(len(g.get_effects().get_zones()) <= 1 and _count_zones(g, "tornado") == 0 and _count_zones(g, "tempest") == 0, "only the vortex remains")
        check(len(g.get_effects().get_drones()) == 5 and len(g.get_effects().get_hazards()) == 1, "drones / network steady")
