"""Group B2: Magic (DALL-E, Sora, Suno) and Support (Grok, Perplexity) towers."""
from kit import DT, buildable_near, force_place, hit_for, kill_outright, mods, new_game, run_seconds, spawn_at, tower_near_track
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.projectile import HitContext
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.javacompat import jround
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType
from lindefense.wave import waves

BASE = [(TowerType.DALLE, 170.0, 0.9, 1.0, 3, DamageType.MAGIC, AttackKind.PROJECTILE),
        (TowerType.SORA, 160.0, 1.0, 1.0, 2, DamageType.MAGIC, AttackKind.PROJECTILE),
        (TowerType.SUNO, 160.0, 0.8, 1.0, 4, DamageType.SONIC, AttackKind.PROJECTILE),
        (TowerType.GROK, 170.0, 1.1, 2.0, 1, DamageType.EXPLOSIVE, AttackKind.PROJECTILE),
        (TowerType.PERPLEXITY, 180.0, 2.0, 1.0, 1, DamageType.MAGIC, AttackKind.CUSTOM)]


def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _at(g, t, d):
    return spawn_at(g, t, None, 0, d)


def _near(a, b):
    return abs(a - b) < 1e-9


def _scaled(g, t, d, hp_scale, ms=None):
    e = g.get_enemy_manager().spawn_scaled(t, ms, 0, d, hp_scale, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _big(g, t, ms, d):
    return _scaled(g, t, d, 500, ms)


def _track_dist_within(g, frm, lo, hi):
    r = g.get_map().get_routes()[0]
    d = 0.0
    while d < r.get_total_length():
        x = r.position_at(d).dist(frm)
        if lo <= x <= hi:
            return d
        d += 5
    raise RuntimeError("no track point in range")


def test_base_stats_match_spec(check):
    for t, rng, interval, dmg, pierce, dt, kind in BASE:
        s = catalog.get(t).base_stats
        check(_near(s.range, rng), "%s range" % t)
        check(abs(s.interval() - interval) < 1e-9, "%s interval" % t)
        check(_near(s.hit.damage, dmg), "%s damage" % t)
        check(s.pierce == pierce, "%s pierce" % t)
        check(s.hit.type is dt, "%s damage type" % t)
        check(s.kind is kind, "%s attack kind" % t)
    d = catalog.get(TowerType.DALLE).base_stats
    check(d.p("zoneInterval") == 6 and d.p("zoneRadius") == 35 and d.p("zoneDuration") == 4 and d.p("zoneTick") == 0.5
          and d.p("zoneDamage") == 1, "DALL-E paint zone")
    s = catalog.get(TowerType.SORA).base_stats
    check(s.field_radius == 150 and _near(s.aura_enemy_slow, 0.35), "Sora slow field")
    gs = catalog.get(TowerType.GROK).base_stats
    check(gs.splash_radius == 35 and gs.sees_camo, "Grok splash 35, built-in camo detection")
    p = catalog.get(TowerType.PERPLEXITY).base_stats
    check(p.sees_camo and p.aura_range == 180 and p.aura_detection and p.income_per_wave == 40, "Perplexity base")


def test_upgrade_stats_match_spec(check):
    s = catalog.get(TowerType.DALLE).stats_for_tier(1)
    check(s.p("creatureInterval") == 5 and s.p("creatureCount") == 2 and s.p("creatureDamage") == 2 and s.p("creaturePierce") == 5, "DALL-E U1")
    s = catalog.get(TowerType.DALLE).stats_for_tier(2)
    check(s.p("zoneRadius") == 70 and s.p("zoneArmorCrack") == 1, "DALL-E U2")
    s = catalog.get(TowerType.DALLE).stats_for_tier(3)
    check(s.p("zoneInterval") == 3 and s.p("creatureCount") == 4 and s.pierce == 6, "DALL-E U3")
    s = catalog.get(TowerType.SORA).stats_for_tier(1)
    check(_near(s.projectile_speed, 900) and abs(s.interval() - 0.7) < 1e-9 and _near(s.aura_enemy_slow, 0.55), "Sora U1")
    s = catalog.get(TowerType.SORA).stats_for_tier(2)
    check(s.p("rewindInterval") == 8 and s.p("rewindKnockback") == 120, "Sora U2")
    s = catalog.get(TowerType.SORA).stats_for_tier(3)
    check(s.p("loopZones") == 2 and s.p("loopRadius") == 60 and s.p("loopTickDamage") == 2 and s.p("loopTick") == 0.4
          and s.p("loopSlow") == 0.6, "Sora U3")
    s = catalog.get(TowerType.SUNO).stats_for_tier(1)
    check(s.p("bassInterval") == 3 and s.p("bassDamage") == 2 and s.p("bassRadius") == 140, "Suno U1")
    s = catalog.get(TowerType.SUNO).stats_for_tier(2)
    check(s.p("chordEvery") == 4 and s.p("chordDamage") == 6 and s.p("chordPierce") == 10, "Suno U2")
    s = catalog.get(TowerType.SUNO).stats_for_tier(3)
    check(abs(s.interval() - 0.4) < 1e-9 and s.p("symphonyInterval") == 1 and s.p("symphonyCount") == 2
          and s.p("symphonyRadius") == 50 and s.p("symphonyDamage") == 3, "Suno U3")
    s = catalog.get(TowerType.GROK).stats_for_tier(1)
    check(s.hit.dot_dps == 1 and s.hit.dot_duration == 4 and s.p("burnSpreadRadius") == 40, "Grok U1")
    s = catalog.get(TowerType.GROK).stats_for_tier(2)
    check(s.has("allowDensest") and s.p("volleyInterval") == 5 and s.p("volleyMissiles") == 6 and s.p("volleyDamage") == 3, "Grok U2")
    s = catalog.get(TowerType.GROK).stats_for_tier(3)
    check(abs(s.interval() - 0.6) < 1e-9 and s.p("chaosSplit") == 4 and s.p("chaosHeavyMoabMult") == 3, "Grok U3")
    check(catalog.get(TowerType.PERPLEXITY).stats_for_tier(1).has("revealAllCamo"), "Perplexity U1")
    s = catalog.get(TowerType.PERPLEXITY).stats_for_tier(2)
    check(_near(s.field_mark_pct, 0.20) and _near(s.aura_range_bonus, 0.15) and s.aura_surveillance_immunity, "Perplexity U2")
    check(catalog.get(TowerType.PERPLEXITY).stats_for_tier(3).income_per_wave == 250, "Perplexity U3")
    for row in BASE:
        check(catalog.get(row[0]).ability is not None and catalog.ability_needs_unlock(row[0]), "%s ability locked" % row[0])


def test_base_attacks_damage_enemies(check):
    for row in BASE:
        type_ = row[0]
        g = _frozen()
        t = tower_near_track(g, type_, 0, 400)
        if type_ is TowerType.PERPLEXITY:
            e = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO), 0, 400)
        else:
            e = _at(g, EnemyType.QUICK_SORT, 400)
        run_seconds(g, 5)
        check(t.get_damage_dealt() > 0 and e.get_hp() < e.get_max_hp(), "%s base attack damages an enemy" % type_)


def test_sora(check):
    g = _frozen()
    s = tower_near_track(g, TowerType.SORA, 0, 400)
    inside = _at(g, EnemyType.HEAP_SORT, 400)
    out = _at(g, EnemyType.HEAP_SORT, 900)
    g.run(10)
    check(_near(inside.get_slow_fraction(), 0.35), "enemies inside the field are slowed 35%")
    check(out.get_slow_fraction() == 0, "enemies outside the field are not slowed")
    g.upgrade_tower(s)
    g.run(10)
    check(_near(inside.get_slow_fraction(), 0.55), "U1 field slow is 55%")


def test_suno(check):
    g = _frozen()
    s = tower_near_track(g, TowerType.SUNO, 0, 400)
    heap = _scaled(g, EnemyType.HEAP_SORT, 400, 20)
    ceramic = _scaled(g, EnemyType.MERGE_SORT, 250, 20)
    d0 = heap.get_distance()
    run_seconds(g, 2)
    check(heap.get_distance() < d0, "sonic hits knock Lead-type enemies back")
    check(s.get_damage_dealt() > 0, "Suno damages Lead-type enemies")
    dm = g.get_combat().apply_hit_simple(ceramic, s.get_stats().hit, s, 1, 0)
    check(_near(dm, 2), "sonic hits deal x2 to Ceramic-type, got %s" % dm)


def test_grok(check):
    g = _frozen()
    grok = tower_near_track(g, TowerType.GROK, 0, 400)
    check(grok.can_see_camo(), "Grok sees camo")
    camo = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO), 0, 400)
    run_seconds(g, 3)
    check(camo.get_hp() < camo.get_max_hp(), "Grok's explosive missiles pop Camo")
    g2 = _frozen()
    g1 = tower_near_track(g2, TowerType.GROK, 1, 400)
    a = _scaled(g2, EnemyType.DYNAMIC_ARRAY, 400, 20)
    b = _scaled(g2, EnemyType.DYNAMIC_ARRAY, 420, 20)
    g2.get_combat().attack(g1)
    run_seconds(g2, 0.01)
    for _ in range(40):
        g2.get_combat().update_projectiles(DT)
    check(a.get_hp() < a.get_max_hp() and b.get_hp() < b.get_max_hp(), "splash 35 hits both neighbours")
    check(a.has_status(StatusKind.DOT) and _near(a.status_magnitude(StatusKind.DOT), 1), "U1 hits BURN 1/s")
    a.tick_statuses(4.1)
    check(not a.has_status(StatusKind.DOT), "burn lasts 4 s")
    u0 = force_place(g2, TowerType.GROK, buildable_near(g2, Vec(1100, 840), 100), 0)
    u0.set_targeting(Targeting.DENSEST_CLUSTER)
    check(u0.get_targeting() is not Targeting.DENSEST_CLUSTER, "base Grok cannot select Densest Cluster")
    u2 = force_place(g2, TowerType.GROK, buildable_near(g2, Vec(900, 840), 100), 2)
    u2.set_targeting(Targeting.DENSEST_CLUSTER)
    check(u2.get_targeting() is Targeting.DENSEST_CLUSTER, "Grok U2 can select Densest Cluster")


def test_perplexity(check):
    g = _frozen()
    tower_near_track(g, TowerType.PERPLEXITY, 0, 400)
    camo = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO), 0, 400)
    plain = _at(g, EnemyType.QUICK_SORT, 410)
    run_seconds(g, 0.1)
    check(camo.get_hp() == camo.get_max_hp() - 1, "radar pulse: 1 damage to Camo enemies")
    run_seconds(g, 2.0)
    check(camo.get_hp() == camo.get_max_hp() - 2, "...repeating every 2 s")
    check(plain.get_hp() == plain.get_max_hp(), "the pulse ignores non-Camo enemies")
    g2 = _frozen()
    p2 = tower_near_track(g2, TowerType.PERPLEXITY, 2, 400)
    gpt = force_place(g2, TowerType.GPT, buildable_near(g2, p2.get_position().add(Vec(60, 0)), 80), 0)
    marked = _at(g2, EnemyType.HEAP_SORT, 400)
    g2.get_tower_manager().recompute_auras()
    g2.run(10)
    check(_near(marked.get_marked_bonus(), 0.20), "enemies in range are MARKED +20%")
    check(_near(gpt.effective_range(None), gpt.get_stats().range * 1.15), "towers in range get +15% range")
    check(gpt.is_surveillance_immune(), "towers in range are immune to Predictive Surveillance")
    dmg = g2.get_combat().apply_hit_simple(marked, HitSpec(2, DamageType.ENERGY), None, 1, 0)
    check(_near(dmg, 2 * 1.2), "marked enemies take +20%% from all sources, got %s" % dmg)
    g4 = new_game(0)
    e = spawn_at(g4, EnemyType.STATIC_ARRAY, None, 0, 300)
    kill_outright(g4, e)
    check(g4.get_round_pop_value() == jround(EnemyType.STATIC_ARRAY.reward * g4.get_reward_scale()), "pops add to the round pop value")


def test_dalle_paint_zones(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.DALLE, 0, 400)
    e = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), 400)
    run_seconds(g, 5.9)
    check(not g.get_effects().zones_of(t, "paint"), "no paint zone before the 6 s interval")
    run_seconds(g, 0.2)
    zs = g.get_effects().zones_of(t, "paint")
    check(len(zs) == 1, "one paint zone after 6 s, got %d" % len(zs))
    z = zs[0]
    check(_near(z.radius, 35) and _near(z.tick_interval, 0.5) and _near(z.tick_hit.damage, 1) and not z.armor_crack, "base zone")
    check(z.center.dist(e.get_position()) < 1e-6, "the zone is painted under the lead enemy in range")
    check(3.5 < z.get_remaining() <= 4, "zone lasts 4 s")
    run_seconds(g, 4.2)
    check(not z.is_alive(), "zone expires after 4 s")
    lost = e.get_max_hp() - e.get_hp()
    check(7 <= lost <= 8, "zone dealt 1 damage every 0.5 s for 4 s, lost %s" % lost)
    check(not g.get_effects().zones_of(t, "paint"), "no second zone before 12 s")
    g3 = _frozen()
    t3 = tower_near_track(g3, TowerType.DALLE, 3, 400)
    run_seconds(g3, 3.05)
    check(len(g3.get_effects().zones_of(t3, "paint")) == 1, "U3 paints a zone after 3 s")
    run_seconds(g3, 3.0)
    check(len(g3.get_effects().zones_of(t3, "paint")) == 2, "...and another 3 s later")
    check(t3.get_stats().pierce == 6, "U3 arrow pierce 6")
    g3.sell_tower(t3)
    check(not g3.get_effects().zones_of(t3, "paint"), "selling DALL-E removes its zones")


def test_dalle_creatures(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.DALLE, 1, 400)
    e = _big(g, EnemyType.DYNAMIC_ARRAY, None, 150)
    run_seconds(g, 4.9)
    check(not g.get_effects().get_walkers(), "no creatures before the 5 s interval")
    run_seconds(g, 0.2)
    ws = list(g.get_effects().get_walkers())
    check(len(ws) == 2, "U1: 2 creatures per cycle, got %d" % len(ws))
    for w in ws:
        check(not w.is_forward() and w.end_distance == 0, "creatures walk BACKWARD toward the entrance")
        check(w.pierce == 5 and _near(w.hit.damage, 2) and w.kind == "creature", "creature contact damage 2, pierce 5")
        check(_near(w.speed, t.get_stats().p("creatureSpeed")), "creature speed from the data table")
    run_seconds(g, 7)
    check(_near(e.get_max_hp() - e.get_hp(), 4), "each creature hits the enemy once for 2")
    g3 = _frozen()
    tower_near_track(g3, TowerType.DALLE, 3, 400)
    run_seconds(g3, 5.05)
    n = sum(1 for w in g3.get_effects().get_walkers() if w.kind == "creature")
    check(n == 4, "U3: 4 creatures per wave, got %d" % n)


def test_dalle_armor_crack_downgrade(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.DALLE, 2, 400)
    fort = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.FORTIFIED), 400)
    heap = _big(g, EnemyType.HEAP_SORT, None, 410)
    boss = g.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 420, 50, 1.0)
    g.get_enemy_manager().update(0)
    check(fort.is_fortified() and hit_for(g, heap, 1, DamageType.SHARP) == 0, "precondition")
    run_seconds(g, 6.1)
    zs = g.get_effects().zones_of(t, "paint")
    check(len(zs) == 1 and _near(zs[0].radius, 70) and zs[0].armor_crack, "U2 zone: radius 70 with armor crack")
    check(not fort.is_fortified(), "Fortified enemies in the zone are downgraded")
    check(heap.is_armor_cracked() and hit_for(g, heap, 1, DamageType.SHARP) > 0, "Lead-type in the zone is cracked")
    check(not boss.is_armor_cracked(), "bosses are not cracked")
    run_seconds(g, 4.5)
    check(not heap.is_armor_cracked(), "crack ends shortly after the zone expires")


def test_sora_scene_rewind(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.SORA, 2, 400)
    inside = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), 400)
    boss = g.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, mods(Modifier.CAMO), 0, 410, 50, 1.0)
    far = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), 900)
    g.get_enemy_manager().update(0)
    run_seconds(g, 7.9)
    check(_near(inside.get_distance(), 400), "no rewind before 8 s")
    run_seconds(g, 0.2)
    check(_near(inside.get_distance(), 280), "Scene Rewind: -120 px, got %s" % inside.get_distance())
    check(_near(boss.get_distance(), 410), "bosses are immune")
    check(_near(far.get_distance(), 900), "enemies out of range are untouched")
    run_seconds(g, 8.0)
    check(_near(inside.get_distance(), 160), "repeats every 8 s")
    check(t.get_stats().has("rewindInterval"), "Scene Rewind runs from the data table")


def test_sora_time_loop(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.SORA, 3, 400)
    run_seconds(g, 0.1)
    zs = g.get_effects().zones_of(t, "loop")
    check(len(zs) == 2, "U3 places 2 loop zones, got %d" % len(zs))
    a, b = zs[0], zs[1]
    for z in zs:
        check(_near(z.radius, 60) and z.permanent and _near(z.slow, 0.6) and _near(z.tick_interval, 0.4) and _near(z.tick_hit.damage, 2), "loop zone")
        check(g.get_map().get_routes()[0].distance_to_point(z.center) < 1e-6 or len(g.get_map().get_routes()) > 1, "loop zone sits on the track")
        check(z.center.dist(t.get_position()) <= t.effective_range(g), "loop zone is inside the tower's range")
    check(a.center.dist(b.center) > a.radius, "the two loops are distinct")
    run_seconds(g, 5)
    check(len(g.get_effects().zones_of(t, "loop")) == 2, "permanent, none duplicated")
    dist = g.get_map().get_routes()[0].nearest_distance_along(a.center)
    e = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), dist)
    check(a.contains(e), "precondition: enemy inside the loop")
    run_seconds(g, 2.0)
    check(_near(e.get_slow_fraction(), 0.6), "enemies in the loop are SLOWED 60%")
    lost = e.get_max_hp() - e.get_hp()
    check(8 <= lost <= 10, "2 damage every 0.4 s, lost %s" % lost)
    g.sell_tower(t)
    check(not g.get_effects().zones_of(t, "loop"), "selling Sora removes the loops")


def test_suno_bass_drop(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.SUNO, 1, 400)
    inside = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), _track_dist_within(g, t.get_position(), 0, 100))
    out = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), _track_dist_within(g, t.get_position(), 200, 260))
    run_seconds(g, 2.9)
    check(inside.get_hp() == inside.get_max_hp(), "no shockwave before 3 s")
    run_seconds(g, 0.2)
    check(_near(inside.get_max_hp() - inside.get_hp(), 2), "Bass Drop deals 2 damage within 140 px")
    check(out.get_hp() == out.get_max_hp(), "enemies beyond 140 px are untouched")
    run_seconds(g, 3.0)
    check(_near(inside.get_max_hp() - inside.get_hp(), 4), "repeats every 3 s")
    g2 = _frozen()
    t2 = tower_near_track(g2, TowerType.SUNO, 1, 400)
    d = _track_dist_within(g2, t2.get_position(), 0, 100)
    heap = g2.get_enemy_manager().spawn_scaled(EnemyType.HEAP_SORT, mods(Modifier.CAMO), 0, d, 500, 1.0)
    g2.get_enemy_manager().update(0)
    run_seconds(g2, 3.05)
    check(_near(heap.get_distance(), d - 20), "sonic shockwave knocks Lead-type back 20 px")


def test_suno_chord_strike(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.SUNO, 2, 400)
    _big(g, EnemyType.DYNAMIC_ARRAY, None, _track_dist_within(g, t.get_position(), 60, 100))
    for _ in range(8):
        g.get_combat().attack(t)
    g.get_combat().update_projectiles(0)
    chords = normals = 0
    for p in g.get_combat().get_projectiles():
        if p.get_shot().tag == "chord":
            chords += 1
            check(_near(p.get_hit().damage, 6) and p.get_shot().pierce == 10, "chord: damage 6, pierce 10")
        else:
            normals += 1
            check(_near(p.get_hit().damage, 1) and p.get_shot().pierce == 4, "normal note: damage 1, pierce 4")
    check(chords == 2 and normals == 6, "every 4th attack is a chord: got %d/%d" % (chords, normals))
    check(_near(t.get_stats().hit.damage, 1), "the chord does not mutate the tower's stats")
    g0 = _frozen()
    t0 = tower_near_track(g0, TowerType.SUNO, 1, 400)
    _big(g0, EnemyType.DYNAMIC_ARRAY, None, _track_dist_within(g0, t0.get_position(), 60, 100))
    for _ in range(8):
        g0.get_combat().attack(t0)
    g0.get_combat().update_projectiles(0)
    for p in g0.get_combat().get_projectiles():
        check(p.get_shot().tag != "chord", "no chords before U2")


def test_suno_symphony(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.SUNO, 3, 400)
    target = _big(g, EnemyType.DYNAMIC_ARRAY, None, _track_dist_within(g, t.get_position(), 60, 100))
    far = _big(g, EnemyType.DYNAMIC_ARRAY, None, 900)
    t.get_behavior().update(g, t, 0.5)
    g.get_effects().update(1.0)
    check(target.get_hp() == target.get_max_hp(), "no explosions before the 1 s interval")
    t.get_behavior().update(g, t, 0.5)
    g.get_effects().update(1.0)
    check(_near(target.get_max_hp() - target.get_hp(), 6), "2 sonic explosions of 3 damage land on the enemy in range")
    check(far.get_hp() == far.get_max_hp(), "enemies out of range are not targeted")
    g2 = _frozen()
    t2 = tower_near_track(g2, TowerType.SUNO, 3, 400)
    camo = _big(g2, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), _track_dist_within(g2, t2.get_position(), 60, 100))
    t2.get_behavior().update(g2, t2, 1.0)
    g2.get_effects().update(1.0)
    check(camo.get_hp() == camo.get_max_hp(), "explosions only pick enemies the tower can target")
    check(_near(t.get_stats().p("symphonyRadius"), 50), "explosion radius 50")
    check(abs(t.get_stats().interval() - 0.4) < 1e-9, "U3 interval 0.4")


def test_grok_burn_spread(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.GROK, 1, 400)
    a = _big(g, EnemyType.DYNAMIC_ARRAY, None, 400)
    b = _big(g, EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), 438)
    c = _big(g, EnemyType.DYNAMIC_ARRAY, None, 460)
    far2 = _big(g, EnemyType.DYNAMIC_ARRAY, None, 476)
    check(a.get_position().dist(b.get_position()) <= 40 and a.get_position().dist(c.get_position()) > 40
          and b.get_position().dist(far2.get_position()) <= 40 and a.get_position().dist(far2.get_position()) > 40, "geometry")
    g.get_combat().apply_hit(HitContext(a, t.get_stats().hit, t))
    check(a.has_status(StatusKind.DOT), "the hit burns its target")
    check(b.has_status(StatusKind.DOT) and _near(b.status_magnitude(StatusKind.DOT), 1), "burn spreads within 40 px")
    check(not c.has_status(StatusKind.DOT), "...but not to one 60 px away")
    check(not far2.has_status(StatusKind.DOT), "spread burn does not spread again")
    g0 = _frozen()
    t0 = tower_near_track(g0, TowerType.GROK, 0, 400)
    a0 = _big(g0, EnemyType.DYNAMIC_ARRAY, None, 400)
    b0 = _big(g0, EnemyType.DYNAMIC_ARRAY, None, 430)
    g0.get_combat().apply_hit(HitContext(a0, t0.get_stats().hit, t0))
    check(not a0.has_status(StatusKind.DOT) and not b0.has_status(StatusKind.DOT), "base Grok neither burns nor spreads")


def test_grok_paradox_volley(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.GROK, 2, 400)
    pack = [_big(g, EnemyType.DYNAMIC_ARRAY, None, 400 + i * 4) for i in range(5)]
    lone = _big(g, EnemyType.DYNAMIC_ARRAY, None, 280)
    t.get_behavior().update(g, t, 4.9)
    g.get_effects().update(1.0)
    check(pack[0].get_hp() == pack[0].get_max_hp(), "no volley before 5 s")
    t.get_behavior().update(g, t, 0.2)
    g.get_effects().update(1.0)
    for e in pack:
        check(_near(e.get_max_hp() - e.get_hp(), 18), "6 missiles x 3 damage land on the densest cluster")
    check(lone.get_hp() == lone.get_max_hp(), "the lone enemy is not targeted")
    g2 = _frozen()
    t2 = tower_near_track(g2, TowerType.GROK, 2, 400)
    far = _big(g2, EnemyType.DYNAMIC_ARRAY, None, 900)
    t2.get_behavior().update(g2, t2, 5.0)
    g2.get_effects().update(1.0)
    check(far.get_hp() == far.get_max_hp(), "no volley with nothing in range")
    check(t.get_stats().pi("volleyMissiles") == 6, "volley size from the data table")


def test_grok_chaos_mode(check):
    g = _frozen()
    t = tower_near_track(g, TowerType.GROK, 3, 400)
    a = _big(g, EnemyType.DYNAMIC_ARRAY, None, 400)
    tags, dots, boss = [], [], []
    for _ in range(6):
        c = g.get_combat().new_attack_context(t, [a])
        t.get_behavior().modify_attack(g, t, c)
        tags.append(c.tag)
        dots.append(c.hit().dot_dps)
        boss.append(c.hit().mult_vs_boss)
    check(tags[0] == "incendiary" and tags[1] == "cluster" and tags[2] == "heavy" and tags[3] == "incendiary", "missile types cycle")
    check(dots[0] == 1 and dots[1] == 0 and dots[2] == 0 and dots[3] == 1, "only incendiary missiles burn")
    check(_near(boss[2], 3) and _near(boss[0], 1) and _near(boss[1], 1), "heavy is x3 vs MOAB-class")
    check(_near(t.get_stats().hit.dot_dps, 1) and _near(t.get_stats().hit.mult_vs_boss, 1), "the cycle never mutates the base stats")
    g2 = _frozen()
    t2 = tower_near_track(g2, TowerType.GROK, 3, 400)
    hit_a = _big(g2, EnemyType.DYNAMIC_ARRAY, None, 400)
    b = _big(g2, EnemyType.DYNAMIC_ARRAY, None, 337)
    direction = g2.get_map().get_routes()[0].direction_at(400)
    c = _big(g2, EnemyType.DYNAMIC_ARRAY, None, 463)
    check(50 < hit_a.get_position().dist(b.get_position()) < 80, "fragments' targets lie outside the splash")
    t2.set_counter("chaos", 1)
    cc = g2.get_combat().new_attack_context(t2, [hit_a])
    t2.get_behavior().modify_attack(g2, t2, cc)
    g2.get_combat().execute_attack(cc, hit_a.get_position().add(Vec(-direction.y * 100, direction.x * 100)), True, True)
    max_frag = 0
    for _ in range(90):
        g2.get_combat().update_projectiles(DT)
        f = sum(1 for p in g2.get_combat().get_projectiles() if p.get_shot().tag == "fragment")
        max_frag = max(max_frag, f)
    check(max_frag == 4, "a cluster missile splits into 4 fragments, got %d" % max_frag)
    check(not hit_a.has_status(StatusKind.DOT), "cluster missiles do not burn")
    check(_near(hit_a.get_max_hp() - hit_a.get_hp(), 2), "the cluster missile deals its 2 splash damage")
    check(_near(b.get_max_hp() - b.get_hp(), 4) and _near(c.get_max_hp() - c.get_hp(), 4), "fragments hit the neighbours")
    g3 = _frozen()
    t3 = tower_near_track(g3, TowerType.GROK, 3, 400)
    boss_e = g3.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 400, 50, 1.0)
    g3.get_enemy_manager().update(0)
    t3.set_counter("chaos", 2)
    before = boss_e.get_hp()
    g3.get_combat().attack(t3)
    for _ in range(90):
        g3.get_combat().update_projectiles(DT)
    heavy = before - boss_e.get_hp()
    ref = g3.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 420, 50, 1.0)
    g3.get_enemy_manager().update(0)
    normal = g3.get_combat().apply_hit_simple(ref, t3.get_stats().hit, t3, 1, 0)
    check(heavy > 0 and _near(heavy, normal * 3), "heavy missile deals x3 to a boss: %s vs %s" % (heavy, normal))


def test_perplexity_detection_and_reveal(check):
    g = _frozen()
    p = tower_near_track(g, TowerType.PERPLEXITY, 0, 400)
    near180 = force_place(g, TowerType.GPT, buildable_near(g, p.get_position().add(Vec(100, 0)), 40), 0)
    far180 = force_place(g, TowerType.GPT, buildable_near(g, p.get_position().add(Vec(-300, 0)), 60), 0)
    check(near180.get_position().dist(p.get_position()) <= 180 and far180.get_position().dist(p.get_position()) > 180, "precondition")
    check(not near180.get_stats().sees_camo, "GPT has no built-in camo detection")
    g.get_tower_manager().recompute_auras()
    check(near180.can_see_camo() and not far180.can_see_camo(), "towers within 180 px gain camo detection")
    camo = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO), 0, 400)
    check(camo.is_targetable_by(near180.can_see_camo()) and not camo.is_targetable_by(far180.can_see_camo()), "camo targetable only by detecting towers")
    g.upgrade_tower(p)
    g.get_tower_manager().recompute_auras()
    check(far180.can_see_camo(), "U1: every tower can target Camo")
    g.sell_tower(p)
    g.get_tower_manager().recompute_auras()
    check(not far180.can_see_camo() and not near180.can_see_camo(), "...only while the Perplexity exists")


def test_perplexity_round_income(check):
    for tier in range(4):
        with_p, without = new_game(0), new_game(0)
        force_place(with_p, TowerType.PERPLEXITY, buildable_near(with_p, Vec(600, 450), 300), tier)
        c0, c1 = with_p.get_cash(), without.get_cash()
        with_p.on_wave_completed(1, waves.get(1))
        without.on_wave_completed(1, waves.get(1))
        expected = 40 if tier < 3 else 250
        check(_near((with_p.get_cash() - c0) - (without.get_cash() - c1), expected), "tier %d pays +$%d" % (tier, expected))
