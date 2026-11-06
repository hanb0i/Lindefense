"""Group B1: Primary (Gemini, Claude, GPT) and Military (DeepSeek, Copilot) towers."""
import math

from kit import DT, buildable_near, force_place, mods, new_game, run_seconds, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.javacompat import jround
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.behavior.primary import GptBehavior
from lindefense.tower.stats import UNLIMITED_RANGE
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType

BASE = [(TowerType.GEMINI, 180.0, 0.8, 1.0, 1, DamageType.ENERGY, AttackKind.INSTANT),
        (TowerType.CLAUDE, 190.0, 0.7, 1.0, 2, DamageType.SHARP, AttackKind.PROJECTILE),
        (TowerType.GPT, 180.0, 0.9, 1.0, 3, DamageType.ENERGY, AttackKind.PROJECTILE),
        (TowerType.DEEPSEEK, UNLIMITED_RANGE, 1.6, 2.0, 1, DamageType.ENERGY, AttackKind.INSTANT),
        (TowerType.COPILOT, 150.0, 1.0, 1.0, 1, DamageType.ENERGY, AttackKind.PROJECTILE)]


def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _at(g, t, d):
    return spawn_at(g, t, None, 0, d)


def _scaled(g, t, d, hp_scale):
    e = g.get_enemy_manager().spawn_scaled(t, None, 0, d, hp_scale, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _near(a, b):
    return abs(a - b) < 1e-9


def test_base_stats_match_spec(check):
    for t, rng, interval, dmg, pierce, dt, kind in BASE:
        s = catalog.get(t).base_stats
        check(_near(s.range, rng), "%s range" % t)
        check(abs(s.interval() - interval) < 1e-9, "%s interval" % t)
        check(_near(s.hit.damage, dmg), "%s damage" % t)
        check(s.pierce == pierce, "%s pierce" % t)
        check(s.hit.type is dt, "%s damage type" % t)
        check(s.kind is kind, "%s attack kind" % t)
    check(_near(catalog.get(TowerType.CLAUDE).base_stats.projectile_speed, 700), "Claude projectile speed 700")
    check(_near(catalog.get(TowerType.GPT).base_stats.projectile_speed, 550), "GPT projectile speed 550")
    check(catalog.get(TowerType.DEEPSEEK).base_stats.ignores_los, "DeepSeek ignores line of sight")
    cop = catalog.get(TowerType.COPILOT).base_stats
    check(cop.aura_range == 150 and _near(cop.aura_rate, 0.10), "Copilot tether 150 px / +10%")


def test_upgrade_stats_match_spec(check):
    s = catalog.get(TowerType.GEMINI).stats_for_tier(1)
    check(abs(s.interval() - 0.5) < 1e-9 and s.pierce == 3 and s.chain_hops == 3 and s.chain_range == 80, "Gemini U1")
    s = catalog.get(TowerType.GEMINI).stats_for_tier(3)
    check(s.chain_hops + 1 == 8 and s.hit.damage == 2 and s.hit.mult_vs_boss == 3 and s.sees_camo and s.hit.strips_camo_regrow, "Gemini U3")
    s = catalog.get(TowerType.CLAUDE).stats_for_tier(1)
    check(s.pierce == 8 and abs(s.interval() - 0.55) < 1e-9, "Claude U1")
    s = catalog.get(TowerType.CLAUDE).stats_for_tier(2)
    check(s.hit.mark_flat == 1 and s.hit.mark_duration == 4 and _near(s.hit.slow_fraction, 0.15), "Claude U2: Context Snare")
    s = catalog.get(TowerType.CLAUDE).stats_for_tier(3)
    check(s.pierce == 20 and s.hit.damage == 2 and s.hit.flat_vs_fortified == 3 and s.hit.flat_vs_lead == 3
          and s.hit.flat_vs_ceramic == 3 and s.hit.ignores_resistance, "Claude U3")
    s = catalog.get(TowerType.GPT).stats_for_tier(1)
    check(s.splash_radius == 40 and s.p("moonCount") == 2 and s.p("moonRadius") == 60 and s.p("moonDamage") == 1
          and s.p("moonInterval") == 0.5, "GPT U1: splash 40 + moons")
    s = catalog.get(TowerType.GPT).stats_for_tier(2)
    check(s.hit.dot_dps == 1 and s.hit.dot_duration == 3, "GPT U2: burn")
    s = catalog.get(TowerType.GPT).stats_for_tier(3)
    check(s.hit.mult_vs_boss == 2 and s.hit.flat_vs_fortified == 2 and s.hit.flat_vs_ceramic == 2 and s.hit.knockback_vs_lead == 20, "GPT U3")
    s = catalog.get(TowerType.DEEPSEEK).stats_for_tier(1)
    check(s.projectiles_per_shot == 3 and s.pierce == 3, "DeepSeek U1")
    s = catalog.get(TowerType.DEEPSEEK).stats_for_tier(3)
    check(s.hit.damage == 6 and s.hit.mult_vs_sorting_and_lists == 3 and s.hit.mult_vs_boss == 2, "DeepSeek U3")
    s = catalog.get(TowerType.COPILOT).stats_for_tier(1)
    check(_near(s.aura_rate, 0.20) and s.aura_pierce == 1, "Copilot U1")
    s = catalog.get(TowerType.COPILOT).stats_for_tier(2)
    check(s.p("droneInterval") == 8 and s.p("droneDamage") == 6 and s.p("droneSplash") == 70, "Copilot U2 drone numbers")
    s = catalog.get(TowerType.COPILOT).stats_for_tier(3)
    check(_near(s.p("globalMilitaryRate"), 0.15) and s.p("globalMilitaryDamage") == 1 and _near(s.aura_rate, 0.30)
          and s.aura_pierce == 2, "Copilot U3 numbers")
    for row in BASE:
        check(catalog.get(row[0]).ability is not None and catalog.ability_needs_unlock(row[0]), "%s ability locked behind unlock" % row[0])


def test_base_attacks_damage_enemies(check):
    for row in BASE:
        type_ = row[0]
        g = _frozen()
        if type_ is TowerType.DEEPSEEK:
            t = force_place(g, type_, buildable_near(g, Vec(1130, 860), 150), 0)
        else:
            t = tower_near_track(g, type_, 0, 400)
        e = _at(g, EnemyType.QUICK_SORT, 400)
        run_seconds(g, 4)
        check(t.get_damage_dealt() > 0 and e.get_hp() < e.get_max_hp(), "%s base attack damages an enemy" % type_)
    g = _frozen()
    ds = force_place(g, TowerType.DEEPSEEK, buildable_near(g, Vec(1130, 860), 150), 0)
    far = _at(g, EnemyType.QUICK_SORT, 100)
    check(ds.get_position().dist(far.get_position()) > 600 and len(g.get_combat().acquire_targets(ds, 1)) == 1, "DeepSeek targets anywhere")


def test_gemini(check):
    g = _frozen()
    gem = tower_near_track(g, TowerType.GEMINI, 1, 450)
    grp = [_at(g, EnemyType.DYNAMIC_ARRAY, 440 + i * 12) for i in range(6)]
    g.get_combat().attack(gem)
    n = sum(1 for e in grp if not e.is_alive() or e.get_hp() < e.get_max_hp())
    check(n >= 4, "U1 beam pierces then ricochets (%d hit)" % n)
    g2 = _frozen()
    g3 = tower_near_track(g2, TowerType.GEMINI, 2, 450)
    c = spawn_at(g2, EnemyType.HEAP_SORT, mods(Modifier.CAMO, Modifier.REGROW), 0, 450)
    check(g3.can_see_camo() and g2.get_combat().acquire_targets(g3, 1)[0] is c, "U2 sees camo")
    run_seconds(g2, 1)
    check(not c.is_camo() and not c.is_regrow(), "U2 hits permanently remove Camo and Regrow")
    g4 = _frozen()
    g5 = tower_near_track(g4, TowerType.GEMINI, 3, 450)
    chain = [_at(g4, EnemyType.HEAP_SORT, 360 + i * 20 + (i % 2)) for i in range(12)]
    g4.get_combat().attack(g5)
    n = sum(1 for e in chain if e.get_hp() < e.get_max_hp())
    check(n >= 8, "U3 hits at least 8 enemies in one attack (%d)" % n)


def test_claude(check):
    g = _frozen()
    tower_near_track(g, TowerType.CLAUDE, 0, 450)
    heap = _at(g, EnemyType.HEAP_SORT, 450)
    run_seconds(g, 4)
    check(heap.get_hp() == heap.get_max_hp(), "Claude's Sharp needles cannot damage Lead-type Heap Sort")
    g2 = _frozen()
    c3 = tower_near_track(g2, TowerType.CLAUDE, 3, 450)
    h2 = _at(g2, EnemyType.HEAP_SORT, 450)
    run_seconds(g2, 2)
    check(h2.get_hp() < h2.get_max_hp() or not h2.is_alive(), "Claude U3 can damage Lead")
    m = _at(g2, EnemyType.MERGE_SORT, 460)
    d = g2.get_combat().apply_hit_simple(m, c3.get_stats().hit, c3, 1, 0)
    check(_near(d, 5), "U3 damage 2 + 3 vs Ceramic = 5, got %s" % d)
    g3 = _frozen()
    c2 = tower_near_track(g3, TowerType.CLAUDE, 2, 450)
    s = _at(g3, EnemyType.QUICK_SORT, 450)
    g3.get_combat().apply_hit_simple(s, c2.get_stats().hit, c2, 1, 0)
    check(_near(s.get_marked_flat(), 1) and _near(s.get_slow_fraction(), 0.15), "Context Snare: mark +1 and slow 15%")


def test_gpt(check):
    g = _frozen()
    tower_near_track(g, TowerType.GPT, 2, 450)
    e = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 450)
    run_seconds(g, 2)
    check(e.has_status(StatusKind.DOT), "U2 hits BURN")
    check(e.status_magnitude(StatusKind.DOT) == 1, "burn 1 dmg/s, never stacks")
    g2 = _frozen()
    t3 = tower_near_track(g2, TowerType.GPT, 3, 450)
    lead = _at(g2, EnemyType.HEAP_SORT, 450)
    before = lead.get_distance()
    g2.get_combat().apply_hit_simple(lead, t3.get_stats().hit, t3, 1, 0)
    check(lead.get_distance() == before - 20, "U3: 20 px knockback vs Lead-type")
    m = _at(g2, EnemyType.MERGE_SORT, 500)
    check(_near(g2.get_combat().apply_hit_simple(m, t3.get_stats().hit, t3, 1, 0), 3), "U3: +2 vs Ceramic-type")
    boss = _at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 600)
    check(_near(g2.get_combat().apply_hit_simple(boss, t3.get_stats().hit, t3, 1, 0), 2 * 0.75), "U3: x2 vs MOAB-class")


def test_deepseek(check):
    g = _frozen()
    t = force_place(g, TowerType.DEEPSEEK, buildable_near(g, Vec(1130, 860), 150), 2)
    check(t.get_targeting() is Targeting.STRONGEST, "R1 makes Strongest the default targeting")
    boss = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 600)
    deltas = []
    for _ in range(10):
        hp = boss.get_hp()
        g.get_combat().attack(t)
        deltas.append(hp - boss.get_hp())
    for i in range(10):
        expect = 3 * (2 + min(6, i)) * 0.75
        check(abs(deltas[i] - expect) < 1e-6, "volley %d damage %s got %s" % (i, expect, deltas[i]))
    other = _scaled(g, EnemyType.MERGE_SORT, 300, 50)
    t.set_targeting(Targeting.WEAKEST)
    hp = other.get_hp()
    g.get_combat().attack(t)
    check(other.get_hp() < hp, "attacks the new target")
    g.get_enemy_manager().destroy_without_children(other, None)
    g.get_enemy_manager().update(0)
    t.set_targeting(Targeting.STRONGEST)
    hp = boss.get_hp()
    g.get_combat().attack(t)
    check(abs((hp - boss.get_hp()) - 3 * 2 * 0.75) < 1e-6, "streak reset after switching targets")
    t3 = force_place(g, TowerType.DEEPSEEK, buildable_near(g, Vec(1000, 860), 150), 3)
    bub = _scaled(g, EnemyType.BUBBLE_SORT, 800, 20)
    ll = _scaled(g, EnemyType.SINGLY_LINKED_LIST, 820, 20)
    arr = _scaled(g, EnemyType.DYNAMIC_ARRAY, 840, 20)
    cb = g.get_combat()
    check(_near(cb.apply_hit_simple(bub, t3.get_stats().hit, t3, 1, 0), 18), "U3 x3 vs sorting algorithms")
    check(_near(cb.apply_hit_simple(ll, t3.get_stats().hit, t3, 1, 0), 18), "U3 x3 vs linked lists")
    check(_near(cb.apply_hit_simple(arr, t3.get_stats().hit, t3, 1, 0), 6), "no bonus vs ordinary enemies")
    bh = _at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 900)
    check(_near(cb.apply_hit_simple(bh, t3.get_stats().hit, t3, 1, 0), 6 * 2 * 0.75), "U3 x2 vs bosses")


def test_copilot(check):
    g = _frozen()
    cop = tower_near_track(g, TowerType.COPILOT, 3, 450)
    ds = force_place(g, TowerType.DEEPSEEK, buildable_near(g, Vec(1130, 860), 150), 0)
    gpt = force_place(g, TowerType.GPT, buildable_near(g, cop.get_position().add(Vec(60, 0)), 80), 0)
    nr = force_place(g, TowerType.COPILOT, buildable_near(g, cop.get_position().add(Vec(-60, 0)), 80), 0)
    g.get_tower_manager().recompute_auras()
    check(_near(ds.get_aura_rate_bonus(), 0.15) and ds.flat_damage_buff() == 1, "Enterprise Network reaches MILITARY towers")
    check(_near(gpt.get_aura_rate_bonus(), 0.30) and gpt.effective_pierce() == gpt.get_stats().pierce + 2 and gpt.flat_damage_buff() == 0, "local tether")
    check(_near(nr.get_aura_rate_bonus(), 0.30), "same source never stacks")
    g2 = _frozen()
    force_place(g2, TowerType.COPILOT, buildable_near(g2, Vec(1130, 860), 150), 2)
    cluster = [_at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 500 + i * 10) for i in range(3)]
    run_seconds(g2, 7.5)
    check(cluster[0].get_hp() == cluster[0].get_max_hp(), "no drone before 8 s")
    run_seconds(g2, 1)
    check(cluster[1].get_hp() == cluster[1].get_max_hp() - 6 * 0.75, "explosive drone hits the cluster at 8 s")
    check(cluster[0].get_hp() < cluster[0].get_max_hp() and cluster[2].get_hp() < cluster[2].get_max_hp(), "splash hits the whole cluster")


def test_gpt_moons(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.GPT, 1, 450)
    t.get_stats().hit.damage = 0
    e = _scaled(g, EnemyType.DYNAMIC_ARRAY, 450, 100)
    d = e.get_position().dist(t.get_position())
    check(abs(d - 60) <= t.get_stats().p("moonSize") + e.get_radius(), "scenario: enemy within a moon's orbit band")
    toward = math.atan2(e.get_position().y - t.get_position().y, e.get_position().x - t.get_position().x)
    hp0 = e.get_hp()
    steps = jround(1.9 / DT)
    for _ in range(steps):
        t.set_counter("moonAngle", toward)
        g.run(1)
    check(_near(hp0 - e.get_hp(), 4), "moon on contact: 4 hits in 1.9 s, got %s" % (hp0 - e.get_hp()))
    check(t.get_stats().p("moonCount") == 2 and t.get_stats().p("moonRadius") == 60, "two moons of orbit radius 60")
    m0, m1 = GptBehavior.moon_position(t, 0), GptBehavior.moon_position(t, 1)
    check(_near(m0.dist(t.get_position()), 60) and _near(m1.dist(t.get_position()), 60) and _near(m0.dist(m1), 120), "moons opposite")
    t.set_counter("moonAngle", 0)
    before = GptBehavior.moon_position(t, 0)
    g.run(30)
    check(GptBehavior.moon_position(t, 0).dist(before) > 1, "the moons orbit")
    g2 = _frozen()
    t2 = tower_near_track(g2, TowerType.GPT, 1, 450)
    t2.get_stats().hit.damage = 0
    e2 = _scaled(g2, EnemyType.DYNAMIC_ARRAY, 450, 100)
    away = math.atan2(e2.get_position().y - t2.get_position().y, e2.get_position().x - t2.get_position().x) + math.pi / 2
    hp2 = e2.get_hp()
    for _ in range(steps):
        t2.set_counter("moonAngle", away)
        g2.run(1)
    check(e2.get_hp() == hp2, "no damage without contact")
    g3 = _frozen()
    t0 = tower_near_track(g3, TowerType.GPT, 0, 450)
    t0.get_stats().hit.damage = 0
    e3 = _scaled(g3, EnemyType.DYNAMIC_ARRAY, 450, 100)
    toward3 = math.atan2(e3.get_position().y - t0.get_position().y, e3.get_position().x - t0.get_position().x)
    for _ in range(steps):
        t0.set_counter("moonAngle", toward3)
        g3.run(1)
    check(GptBehavior.moon_position(t0, 0) is None and e3.get_hp() == e3.get_max_hp(), "moons are an U1 feature")


def test_copilot_enterprise_scope(check):
    g = _frozen()
    cop = tower_near_track(g, TowerType.COPILOT, 3, 450)
    far_mil = force_place(g, TowerType.DEEPSEEK, buildable_near(g, Vec(1130, 860), 150), 0)
    far_other = force_place(g, TowerType.GPT, buildable_near(g, Vec(1130, 760), 100), 0)
    ar = cop.get_stats().aura_range
    check(far_mil.get_position().dist(cop.get_position()) > ar and far_other.get_position().dist(cop.get_position()) > ar, "both far")
    g.get_tower_manager().recompute_auras()
    check(_near(far_mil.get_aura_rate_bonus(), 0.15) and far_mil.flat_damage_buff() == 1, "Enterprise Network reaches a far MILITARY tower")
    check(far_other.get_aura_rate_bonus() == 0 and far_other.flat_damage_buff() == 0
          and far_other.effective_pierce() == far_other.get_stats().pierce, "...but not a far non-MILITARY tower")
    hero = force_place(g, TowerType.BLITZ_ARNAV, buildable_near(g, Vec(1130, 660), 100), 0)
    g.get_tower_manager().recompute_auras()
    check(hero.get_aura_rate_bonus() == 0 and hero.flat_damage_buff() == 0, "HERO towers get no Enterprise bonus")
    g2 = _frozen()
    c2 = force_place(g2, TowerType.COPILOT, buildable_near(g2, Vec(600, 700), 100), 2)
    far2 = force_place(g2, TowerType.DEEPSEEK, buildable_near(g2, Vec(1130, 860), 150), 0)
    g2.get_tower_manager().recompute_auras()
    check(c2.get_position().dist(far2.get_position()) > 150 and far2.get_aura_rate_bonus() == 0, "no map-wide bonus before U3")
