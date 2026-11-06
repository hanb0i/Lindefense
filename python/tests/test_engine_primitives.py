"""Reusable simulation primitives: zones, walkers, drones, barrages, node hazards, enemy operations, counters, income."""
from kit import DT, buildable_near, force_place, mods, new_game, run_seconds, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.effects.effects import Barrage, Drone, NodeHazard, TrackWalker, TrackZone
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.javacompat import jround
from lindefense.sim.vec import Vec
from lindefense.tower.behavior.support_titans import KimiBehavior
from lindefense.tower.tower_type import AttackKind, TowerType
from lindefense.wave import waves


def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _far_tower(g, t):
    return force_place(g, t, buildable_near(g, Vec(1130, 860), 150), 0)


def _route(g):
    return g.get_map().get_routes()[0]


def _at(g, t, d):
    return spawn_at(g, t, None, 0, d)


def test_track_zone(check):
    g = _frozen()
    c = _route(g).position_at(400)
    inside = _at(g, EnemyType.TIMSORT, 400)
    out = _at(g, EnemyType.TIMSORT, 600)
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 405)
    z = TrackZone(c, 35, None)
    z.duration = 2
    z.tick_interval = 0.5
    z.tick_hit = HitSpec(1, DamageType.MAGIC)
    z.speed_cap = 0.25
    z.armor_crack = True
    g.get_effects().add_zone(z)
    run_seconds(g, 1.1)
    check(inside.get_hp() == inside.get_max_hp() - 2, "tick damage every 0.5 s, hp %s" % inside.get_hp())
    check(out.get_hp() == out.get_max_hp(), "enemies outside the radius are untouched")
    check(abs(inside.get_slow_fraction() - 0.75) < 1e-9 and abs(inside.current_speed(1) - inside.nominal_speed() * 0.25) < 1e-6, "speed cap")
    check(inside.is_armor_cracked(), "zone applies ARMOR CRACK to non-bosses")
    check(not boss.is_armor_cracked(), "zone does not crack bosses by default")
    check(abs(boss.get_slow_fraction() - 0.25) < 1e-9, "boss gets 1/3 of the zone slow")
    run_seconds(g, 1.2)
    check(not g.get_effects().get_zones(), "zone expires after its duration")
    inside.tick_statuses(1)
    check(not inside.has_status(StatusKind.SLOW), "slow and crack end shortly after the zone")
    g2 = _frozen()
    owner = _far_tower(g2, TowerType.MISTRAL)
    b2 = _at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 400)
    n2 = _at(g2, EnemyType.TIMSORT, 400)
    pz = TrackZone(_route(g2).position_at(400), 40, owner)
    pz.permanent = True
    pz.bosses_only = True
    pz.tick_interval = 0.3
    pz.tick_hit = HitSpec(10, DamageType.MAGIC)
    pz.kind = "tempest"
    g2.get_effects().add_zone(pz)
    run_seconds(g2, 20)
    check(b2.get_hp() < b2.get_max_hp() and n2.get_hp() == n2.get_max_hp(), "bosses-only zone hits airships only")
    check(len(g2.get_effects().zones_of(owner, "tempest")) == 1, "permanent zone outlives any duration")
    g2.sell_tower(owner)
    g2.run(2)
    check(not g2.get_effects().get_zones(), "zone disappears when its owner is sold")


def test_track_walker(check):
    g = _frozen()
    owner = _far_tower(g, TowerType.LLAMA)
    a = _at(g, EnemyType.TIMSORT, 450)
    w = TrackWalker(_route(g), 300, 600, 150, owner, HitSpec(2, DamageType.ENERGY))
    w.pierce = 1
    g.get_effects().add_walker(w)
    run_seconds(g, 1.5)
    check(a.get_hp() == a.get_max_hp() - 2, "walker contact damage 2")
    check(not w.is_alive() and not g.get_effects().get_walkers(), "walker with pierce 1 expires after one enemy")
    check(owner.get_damage_dealt() >= 2, "walker damage is credited to its owner")
    g2 = _frozen()
    es = [_at(g2, EnemyType.TIMSORT, d) for d in (500, 505, 510)]
    w2 = TrackWalker(_route(g2), 700, 300, 100, None, HitSpec(1, DamageType.ENERGY))
    w2.pierce = 2
    g2.get_effects().add_walker(w2)
    run_seconds(g2, 4.5)
    n = sum(1 for e in es if e.get_hp() < e.get_max_hp())
    check(n == 2 and w2.get_distinct_hits() == 2, "pierce 2 hits exactly two enemies, hit %d" % n)
    check(w2.distance == 300 or not w2.is_alive(), "backward walker travels toward the entrance")
    g3 = _frozen()
    slow = _at(g3, EnemyType.TIMSORT, 500)
    w3 = TrackWalker(_route(g3), 500, 600, 1, None, HitSpec(1, DamageType.ENERGY))
    w3.pierce = 99
    w3.per_enemy_cooldown = 0.5
    w3.lifetime = 2.05
    g3.get_effects().add_walker(w3)
    g3.run(3 * 60)
    lost = slow.get_max_hp() - slow.get_hp()
    check(3 <= lost <= 5, "per-enemy hit cooldown re-hits every 0.5 s: %s" % lost)
    check(not w3.is_alive(), "walker lifetime ends it")
    g4 = _frozen()
    boss = _at(g4, EnemyType.BELLARMINE_COLLEGE_PREP, 500)
    norm = _at(g4, EnemyType.TIMSORT, 500)
    w4 = TrackWalker(_route(g4), 500, 500, 0, None, HitSpec(15, DamageType.ENERGY))
    w4.boss_hit = HitSpec(60, DamageType.ENERGY)
    w4.boss_hit.boss_knockback = 50
    w4.boss_hit.uncapped_knockback = True
    w4.pierce = 5
    g4.get_effects().add_walker(w4)
    g4.run(2)
    check(norm.get_max_hp() - norm.get_hp() == 10 or not norm.is_alive(), "normal enemies take the normal spec")
    check(boss.get_distance() == 450 and boss.get_hp() < boss.get_max_hp() - 40, "bosses take the boss spec")


def test_drone(check):
    g = _frozen()
    owner = tower_near_track(g, TowerType.CLAUDE, 0, 300)
    e = _at(g, EnemyType.HEAP_SORT, 300)
    ds = Drone.stats_for(AttackKind.INSTANT, 400, 0.2, 1, DamageType.ENERGY, 1, 0)
    d = Drone.orbit(owner, ds, 40, 0)
    d.lifetime = 1.0
    d.kind = "buddy"
    g.get_effects().add_drone(d)
    p0 = d.get_position()
    run_seconds(g, 0.5)
    check(39 < d.get_position().dist(owner.get_position()) < 41, "orbit drone stays on its circle")
    check(d.get_position().dist(p0) > 1, "orbit drone moves")
    check(e.get_hp() <= e.get_max_hp() - 2, "drone fires on its own interval")
    check(owner.get_damage_dealt() > 0, "drone damage credited to the owner")
    run_seconds(g, 0.7)
    check(not d.is_alive() and not g.get_effects().get_drones(), "drone lifetime ends it")
    g2 = _frozen()
    o2 = tower_near_track(g2, TowerType.CLAUDE, 0, 300)
    camo = spawn_at(g2, EnemyType.HEAP_SORT, mods(Modifier.CAMO), 0, 300)
    blind = Drone.orbit(o2, Drone.stats_for(AttackKind.INSTANT, 400, 0.2, 1, DamageType.ENERGY, 1, 0), 30, 0)
    g2.get_effects().add_drone(blind)
    run_seconds(g2, 1)
    check(camo.get_hp() == camo.get_max_hp(), "drone without detection ignores Camo")
    blind.detection = True
    run_seconds(g2, 1)
    check(camo.get_hp() < camo.get_max_hp(), "drone with its own detection hits Camo")
    g3 = _frozen()
    o3 = tower_near_track(g3, TowerType.CLAUDE, 0, 300)
    ps = Drone.stats_for(AttackKind.PROJECTILE, 150, 1.2, 2, DamageType.ENERGY, 4, 500)
    pd = Drone.patrol(o3, ps, _route(g3), 700, 800, 100)
    g3.get_effects().add_drone(pd)
    target = _at(g3, EnemyType.HEAP_SORT, 750)
    run_seconds(g3, 1.5)
    dd = pd.get_position().dist(_route(g3).position_at(700))
    check(0 < dd < 200, "patrol drone moves along its segment")
    run_seconds(g3, 3)
    check(target.get_hp() < target.get_max_hp(), "patrolling projectile drone shoots enemies near it")
    g4 = _frozen()
    o4 = _far_tower(g4, TowerType.MINIMAX)
    clone = Drone.orbit(o4, None, 30, 0)
    clone.mirror_owner = True
    g4.get_effects().add_drone(clone)
    check(clone.effective_stats() is o4.get_stats(), "mirror drone copies the owner's current stats")
    g4.sell_tower(o4)
    g4.run(2)
    check(not g4.get_effects().get_drones(), "drones disappear with their owner")


def test_barrage(check):
    g = _frozen()
    src = _far_tower(g, TowerType.KAIJU_KAI)
    cluster = [_at(g, EnemyType.TIMSORT, 500 + i * 12) for i in range(4)]
    lone = _at(g, EnemyType.TIMSORT, 800)
    b = Barrage(src, HitSpec(2, DamageType.EXPLOSIVE), 3, 50)
    b.aim = Barrage.DENSEST
    b.stagger = 0.2
    aim = g.get_effects().fire(b)
    check(aim is not None and aim.dist(cluster[0].get_position()) < 60, "barrage aims at the densest cluster")
    run_seconds(g, 0.1)
    landed1 = 1 if cluster[1].get_max_hp() > cluster[1].get_hp() else 0
    run_seconds(g, 1.0)
    check(cluster[1].get_hp() == cluster[1].get_max_hp() - 6, "3 shells x 2 damage land on the cluster")
    check(landed1 == 1, "first shell lands immediately, others staggered")
    check(lone.get_hp() == lone.get_max_hp(), "the lone enemy is not hit")
    g2 = _frozen()
    s2 = _far_tower(g2, TowerType.KAIJU_KAI)
    for i in range(4):
        _at(g2, EnemyType.TIMSORT, 500 + i * 12)
    boss = _at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 900)
    bh = HitSpec(25, DamageType.EXPLOSIVE)
    bh.mult_vs_boss = 3
    b2 = Barrage(s2, bh, 5, 90)
    b2.aim = Barrage.BOSS_ELSE_DENSEST
    b2.stagger = 0.05
    aim2 = g2.get_effects().fire(b2)
    check(aim2.dist(boss.get_position()) < 1, "BOSS_ELSE_DENSEST aims at the boss when present")
    run_seconds(g2, 1)
    expected = 5 * 25 * 3 * (1 - EnemyType.BELLARMINE_COLLEGE_PREP.get_armor())
    check(abs((boss.get_max_hp() - boss.get_hp()) - expected) < 1e-6, "5 shells x25 x3 vs MOAB with armour")
    g3 = _frozen()
    s3 = _far_tower(g3, TowerType.GPT)
    camo = spawn_at(g3, EnemyType.TIMSORT, mods(Modifier.CAMO), 0, 500)
    b3 = Barrage(s3, HitSpec(5, DamageType.EXPLOSIVE), 1, 50)
    b3.aim = Barrage.POINT
    b3.point = camo.get_position()
    b3.stagger = 0
    g3.get_effects().fire(b3)
    g3.run(2)
    check(camo.get_hp() == camo.get_max_hp(), "explosive barrage cannot damage Camo without detection")
    b4 = Barrage(s3, HitSpec(5, DamageType.EXPLOSIVE), 1, 50)
    b4.aim = Barrage.POINT
    b4.point = camo.get_position()
    b4.stagger = 0
    b4.detection = True
    g3.get_effects().fire(b4)
    g3.run(2)
    check(camo.get_hp() == camo.get_max_hp() - 5, "with detection the barrage pops camo")
    check(g3.get_effects().fire(Barrage(s3, HitSpec(1, DamageType.ENERGY), 1, 10)) is not None, "densest aim returns a point")
    empty = _frozen()
    check(empty.get_effects().fire(Barrage(None, HitSpec(1, DamageType.ENERGY), 1, 10)) is None, "no target, no barrage")


def test_node_hazard(check):
    g = _frozen()
    on = _at(g, EnemyType.TIMSORT, 400)
    off = _at(g, EnemyType.TIMSORT, 700)
    n1 = on.get_position().add(Vec(-30, -30))
    n2 = on.get_position().add(Vec(30, 30))
    h = NodeHazard.line(None, n1, n2, HitSpec(2, DamageType.GRAVITY), 0.3)
    g.get_effects().add_hazard(h)
    check(h.distance_to_links(on.get_position()) < 1, "enemy sits on the laser link")
    run_seconds(g, 1.0)
    lost = on.get_max_hp() - on.get_hp()
    check(6 <= lost <= 8, "link damages at most once per 0.3 s: %s" % lost)
    check(off.get_hp() == off.get_max_hp(), "enemies away from the link are untouched")
    g2 = _frozen()
    inside = _at(g2, EnemyType.TIMSORT, 400)
    c = inside.get_position()
    poly = [c.add(Vec(-60, -60)), c.add(Vec(60, -60)), c.add(Vec(60, 60)), c.add(Vec(-60, 60))]
    outside = _at(g2, EnemyType.TIMSORT, 900)
    net = NodeHazard.network(None, poly, HitSpec(5, DamageType.GRAVITY), 0.3, 0.3)
    g2.get_effects().add_hazard(net)
    check(NodeHazard.polygon_contains(poly, c) and not NodeHazard.polygon_contains(poly, c.add(Vec(100, 0))), "point-in-polygon test")
    g2.run(10)
    check(abs(inside.get_slow_fraction() - 0.3) < 1e-9 and outside.get_slow_fraction() == 0, "grid region slows enemies inside it")
    check(len(net.links) == 4 and len(net.nodes) == 4, "4 nodes form a closed grid of 4 links")


def test_enemy_reverse(check):
    g = new_game(0)
    src = _far_tower(g, TowerType.COHERE)
    rev = _at(g, EnemyType.QUICK_SORT, 500)
    victim = _at(g, EnemyType.TIMSORT, 480)
    far = _at(g, EnemyType.TIMSORT, 900)
    rev.start_reverse(2, 3, src)
    before = rev.get_distance()
    run_seconds(g, 1.0)
    check(rev.get_distance() < before - 20, "reversed enemy walks backwards")
    check(victim.get_hp() < victim.get_max_hp(), "reversed enemy damages those it touches")
    check(far.get_hp() == far.get_max_hp(), "...and only those")
    check(src.get_damage_dealt() > 0, "contact damage is credited to the override's tower")
    run_seconds(g, 1.5)
    mid = rev.get_distance()
    run_seconds(g, 1.0)
    check(rev.get_distance() > mid, "enemy resumes normal movement")
    at_start = _at(g, EnemyType.QUICK_SORT, 2)
    at_start.start_reverse(3, 0, None)
    run_seconds(g, 1)
    check(at_start.get_distance() >= 0, "reverse never leaves the start of the path")


def test_enemy_rewind_hold(check):
    g = _frozen()
    e = _at(g, EnemyType.QUICK_SORT, 600)
    px = e.rewind(3)
    check(abs(px - e.nominal_speed() * 3) < 1e-6 and abs(e.get_distance() - (600 - px)) < 1e-6, "rewind 3 s of own travel")
    fast = _at(g, EnemyType.SINGLY_LINKED_LIST, 600)
    fast.rewind(1)
    check(600 - fast.get_distance() > e.nominal_speed(), "faster enemies rewind further")
    near = _at(g, EnemyType.QUICK_SORT, 5)
    near.rewind(10)
    check(near.get_distance() == 0, "rewind clamps at the path start")
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 600)
    boss.rewind(1)
    check(abs(600 - boss.get_distance() - boss.nominal_speed()) < 1e-6, "bosses rewind by 1 s of their own travel")
    g2 = new_game(0)
    h = _at(g2, EnemyType.QUICK_SORT, 500)
    check(h.hold(2, 560, 100), "hold accepted")
    run_seconds(g2, 1.0)
    check(abs(h.get_distance() - 560) < 1e-6 and h.current_speed(1) == 0, "held enemy is pulled to the vortex")
    run_seconds(g2, 1.2)
    check(not h.is_held(), "hold ends")
    d = h.get_distance()
    run_seconds(g2, 0.5)
    check(h.get_distance() > d, "released enemy moves again")
    pal = _at(g2, EnemyType.PALANTIR, 400)
    check(not pal.hold(2, 450, 100), "control-immune Palantir cannot be held")


def test_enemy_destroy_strip(check):
    g = _frozen()
    t = _far_tower(g, TowerType.COHERE)
    c0 = g.get_cash()
    parent = _at(g, EnemyType.STATIC_ARRAY, 500)
    em = g.get_enemy_manager()
    em.destroy_without_children(parent, t)
    em.update(0)
    check(not parent.is_alive() and em.count_of_type(EnemyType.PRIMITIVE_VARIABLE) == 0, "destroyed without children")
    pay = jround(EnemyType.STATIC_ARRAY.reward * g.get_reward_scale())
    check(g.get_cash() == c0 + pay, "parent's cash is paid once")
    check(t.get_kills() == 1, "kill credited to the tower")
    em.destroy_without_children(parent, t)
    check(g.get_cash() == c0 + pay, "no double payment")
    tim = _at(g, EnemyType.TIMSORT, 500)
    em.destroy_without_children(tim, None)
    em.update(0)
    check(em.count_of_type(EnemyType.MERGE_SORT) == 0 and em.count_of_type(EnemyType.INSERTION_SORT) == 0, "TimSort's children never spawn")
    cr = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO, Modifier.REGROW), 0, 500)
    check(cr.strip_camo_regrow() and not cr.is_camo() and not cr.is_regrow(), "Camo and Regrow removed from non-bosses")
    ddt = _at(g, EnemyType.LOCKHEED_MARTIN, 500)
    check(not ddt.strip_camo_regrow() and ddt.is_camo(), "bosses keep Camo")
    f = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.FORTIFIED), 0, 500)
    mx = f.get_max_hp()
    check(f.strip_fortified() and not f.is_fortified() and f.get_max_hp() == mx / 2 and f.get_hp() <= f.get_max_hp(), "Fortified removed")


def test_palantir_shield(check):
    g = _frozen()
    pal = _at(g, EnemyType.PALANTIR, 500)
    check(pal.is_control_immune() and abs(pal.effective_armor() - 0.60) < 1e-9, "phase 1 shield")
    pal.disable_phase_shield(10)
    check(not pal.is_control_immune() and pal.effective_armor() == 0 and pal.is_phase_shield_down(), "shield off")
    check(pal.apply_status(StatusKind.SLOW, 0.5, 2), "controls land while the shield is down")
    run_seconds(g, 10.5)
    check(pal.is_control_immune() and abs(pal.effective_armor() - 0.60) < 1e-9, "shield returns after 10 s")
    moab = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 500)
    moab.disable_phase_shield(10)
    check(not moab.is_phase_shield_down() and abs(moab.effective_armor() - 0.25) < 1e-9, "other bosses are unaffected")


def test_counters(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.KIMI, 1, 300)
    check(t.counter("x") == 0 and t.add_counter("x", 2) == 2 and t.counter("x") == 2, "named counters")
    check(t.register_streak(7) == 0 and t.register_streak(7) == 1 and t.register_streak(7) == 2, "streak counts consecutive hits")
    check(t.register_streak(8) == 0 and t.register_streak(7) == 0, "switching targets resets the streak")
    n = 0
    while not t.periodic("p", 0.5, DT):
        n += 1
    check(28 <= n <= 30, "periodic fires after the interval: %d" % n)
    for _ in range(99):
        t.add_kill()
    check(KimiBehavior.memory_stacks(t) == 0, "99 pops = no memory bonus yet")
    t.add_kill()
    check(KimiBehavior.memory_stacks(t) == 1, "100 pops = +1")
    for _ in range(2000):
        t.add_kill()
    check(KimiBehavior.memory_stacks(t) == 5, "memory capped at +5 at U1")
    e = _at(g, EnemyType.PRIMITIVE_VARIABLE, 500)
    k2 = tower_near_track(g, TowerType.KIMI, 0, 500)
    kills = k2.get_kills()
    g.get_combat().apply_hit_simple(e, HitSpec(100, DamageType.MAGIC), k2, 1, 0)
    g.get_enemy_manager().update(0)
    check(k2.get_kills() == kills + 1, "pops are counted on the tower that landed the final blow")


def test_round_income(check):
    g = new_game(0)
    p = tower_near_track(g, TowerType.PERPLEXITY, 0, 300)
    c = g.get_cash()
    g.on_wave_completed(1, waves.get(1))
    check(abs(g.get_cash() - (c + waves.wave_bonus(1) + 40)) < 1e-9, "Perplexity pays +$40 at the end of a round")
    g.upgrade_tower(p)
    g.upgrade_tower(p)
    check(p.get_stats().income_per_wave == 40, "U1/U2 keep $40")
    g.upgrade_tower(p)
    c = g.get_cash()
    g.on_wave_completed(2, waves.get(2))
    check(abs(g.get_cash() - (c + waves.wave_bonus(2) + 250)) < 1e-9, "Perplexity U3 pays +$250")


def test_schedule_and_owner_cleanup(check):
    g = _frozen()
    ran = [0]
    g.get_effects().schedule(0.5, lambda: ran.__setitem__(0, ran[0] + 1))
    run_seconds(g, 0.4)
    check(ran[0] == 0, "scheduled task waits")
    run_seconds(g, 0.2)
    check(ran[0] == 1, "scheduled task runs once")
    run_seconds(g, 1)
    check(ran[0] == 1, "...and only once")
    snap = g.get_effects().nearest_track_point(_route(g).position_at(400).add(Vec(0, 30)))
    check(snap is not None and snap.position.dist(_route(g).position_at(snap.distance)) < 1e-6 and snap.route_index >= 0, "snaps onto a route")
    t = tower_near_track(g, TowerType.MISTRAL, 0, 300)
    bends = g.get_effects().bends_in_range(t.get_position(), 1500)
    check(bends and bends[0].position.dist_sq(t.get_position()) <= bends[-1].position.dist_sq(t.get_position()), "bends nearest first")
