"""Global tower rules (spec 3.0): units, damage types, statuses, buffs, targeting, camo, factions, heroes, costs."""
import math

from kit import buildable_near, force_place, hit_for, mods, new_game, spawn_at, tower_near_track
from lindefense.combat import clusters
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import BuffStat, Faction, Targeting, TowerType


def _frozen(g, t, dist):
    return spawn_at(g, t, None, 0, dist)


def test_units(check):
    check(Enemy.BASE_SPEED == 60.0, "1.0x speed is 60 px/s")
    g = new_game(0)
    e = _frozen(g, EnemyType.PRIMITIVE_VARIABLE, 100)
    g.run(60)
    check(abs(e.get_distance() - 160) < 1.0, "a 1.0x enemy moves 60 px in one second, d=%s" % e.get_distance())
    check(catalog.get(TowerType.DEEPSEEK).base_stats.has_unlimited_range(), "DeepSeek range is the entire map")
    check(catalog.get(TowerType.DEEPSEEK).base_stats.range > math.hypot(1200, 900), "unlimited range exceeds the map diagonal")


def test_damage_types(check):
    g = new_game(1)
    g.set_global_enemy_speed_multiplier(0)
    heap = _frozen(g, EnemyType.HEAP_SORT, 300)
    check(hit_for(g, heap, 3, DamageType.SHARP) == 0, "SHARP cannot damage Lead-type")
    for t in (DamageType.BLUNT, DamageType.KINETIC, DamageType.ENERGY, DamageType.EXPLOSIVE, DamageType.MAGIC, DamageType.GRAVITY):
        check(hit_for(g, _frozen(g, EnemyType.HEAP_SORT, 300), 1, t) == 1, "%s can damage Lead-type" % t)
    for t in (DamageType.BLUNT, DamageType.KINETIC, DamageType.SONIC):
        check(hit_for(g, _frozen(g, EnemyType.MERGE_SORT, 300), 2, t) == 4, "%s deals x2 to a Ceramic-type layer" % t)
    for t in (DamageType.SHARP, DamageType.ENERGY, DamageType.EXPLOSIVE, DamageType.MAGIC, DamageType.GRAVITY):
        check(hit_for(g, _frozen(g, EnemyType.MERGE_SORT, 300), 2, t) == 2, "%s has no Ceramic bonus" % t)
    check(hit_for(g, _frozen(g, EnemyType.MERGE_RUN, 300), 1, DamageType.BLUNT) == 1, "Merge Run is not Ceramic-type")
    ddt = _frozen(g, EnemyType.LOCKHEED_MARTIN, 300)
    check(hit_for(g, ddt, 10, DamageType.MAGIC) > 0, "MAGIC hurts the Lead-type DDT")
    check(hit_for(g, ddt, 10, DamageType.SHARP) == 0, "SHARP cannot hurt the Lead-type DDT")
    lead = _frozen(g, EnemyType.HEAP_SORT, 500)
    hit_for(g, lead, 1, DamageType.SONIC)
    check(abs(lead.get_distance() - 480) < 1e-6, "SONIC knocks Lead-type back 20 px")
    non_lead = _frozen(g, EnemyType.QUICK_SORT, 500)
    hit_for(g, non_lead, 1, DamageType.SONIC)
    check(non_lead.get_distance() == 500, "SONIC does not knock back non-Lead enemies")
    grav = HitSpec(1, DamageType.GRAVITY)
    grav.slow_fraction = 0.10
    grav.slow_duration = 2
    gz = _frozen(g, EnemyType.QUICK_SORT, 300)
    g.get_combat().apply_hit_simple(gz, grav, None, 1, 0)
    check(abs(gz.get_slow_fraction() - 0.10) < 1e-9, "GRAVITY hit applies its slow")
    gpt = tower_near_track(g, TowerType.GPT, 0, 300)
    grok = force_place(g, TowerType.GROK, buildable_near(g, gpt.get_position().add(Vec(60, 0)), 100), 0)
    camo = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.CAMO), 0, 300)
    boom = HitSpec(2, DamageType.EXPLOSIVE)
    cb = g.get_combat()
    check(cb.apply_hit_simple(camo, boom, gpt, 1, 0) == 0, "EXPLOSIVE cannot damage Camo without detection")
    check(cb.apply_hit_simple(camo, boom, grok, 1, 0) == 2, "EXPLOSIVE damages Camo when the source has detection")
    camo.apply_status(StatusKind.REVEALED, 1, 5)
    check(cb.apply_hit_simple(camo, boom, gpt, 1, 0) == 2, "a revealed Camo enemy can be damaged by explosions")
    g2 = new_game(0)
    g2.set_global_enemy_speed_multiplier(0)
    a = _frozen(g2, EnemyType.QUICK_SORT, 400)
    _frozen(g2, EnemyType.QUICK_SORT, 420)
    far = _frozen(g2, EnemyType.QUICK_SORT, 900)
    n = g2.get_combat().area_hit(a.get_position(), 60, boom, None, 1, 99, None)
    check(n == 2 and far.get_hp() == far.get_max_hp(), "splash hits everything inside the radius only (%d)" % n)


def test_lead_ceramic_flags(check):
    g = new_game(1)
    g.set_global_enemy_speed_multiplier(0)
    check(_frozen(g, EnemyType.HEAP_SORT, 100).is_lead_type(), "Heap Sort is Lead-type")
    check(_frozen(g, EnemyType.LOCKHEED_MARTIN, 100).is_lead_type(), "Lockheed Martin is Lead-type")
    radix = _frozen(g, EnemyType.RADIX_SORT, 100)
    check(not radix.is_lead_type(), "Radix Sort is plain while above 6 layers")
    hit_for(g, radix, 2, DamageType.TRUE)
    check(radix.is_lead_type(), "Radix Sort armoured phase is Lead-type")
    for t in (EnemyType.MERGE_SORT, EnemyType.QUICK_SORT, EnemyType.TIMSORT):
        check(_frozen(g, t, 100).is_ceramic_type(), "%s outer layer is Ceramic-type" % t)
    for t in (EnemyType.MERGE_RUN, EnemyType.QUICK_PARTITION, EnemyType.HEAP_SORT, EnemyType.STATIC_ARRAY):
        check(not _frozen(g, t, 100).is_ceramic_type(), "%s is not Ceramic-type" % t)
    bosses = 0
    for t in EnemyType:
        if t.is_boss():
            bosses += 1
            check(_frozen(g, t, 100).is_moab_class(), "%s is MOAB-class" % t)
    check(bosses == 5, "MOAB-class is exactly the 5 bosses")
    check(not _frozen(g, EnemyType.TIMSORT, 100).is_moab_class(), "ordinary enemies are not MOAB-class")


def test_statuses(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    e = _frozen(g, EnemyType.QUICK_SORT, 300)
    e.apply_status(StatusKind.SLOW, 0.3, 5)
    e.apply_status(StatusKind.SLOW, 0.5, 1)
    e.apply_status(StatusKind.SLOW, 0.2, 5)
    check(abs(e.get_slow_fraction() - 0.5) < 1e-9, "strongest slow applies")
    e.tick_statuses(2)
    check(abs(e.get_slow_fraction() - 0.3) < 1e-9, "next strongest takes over")
    boss = _frozen(g, EnemyType.BELLARMINE_COLLEGE_PREP, 300)
    boss.apply_status(StatusKind.SLOW, 0.6, 5)
    check(abs(boss.get_slow_fraction() - 0.2) < 1e-9, "bosses receive 1/3 of a slow")
    pal = _frozen(g, EnemyType.PALANTIR, 300)
    pal.apply_status(StatusKind.SLOW, 0.6, 5)
    check(pal.get_slow_fraction() == 0, "Palantir phase 1 ignores slows")
    check(e.apply_status(StatusKind.STUN, 1, 1) and e.is_stunned(), "stun stops a normal enemy")
    check(not boss.apply_status(StatusKind.STUN, 1, 1) and not boss.is_stunned(), "bosses are immune to stun")
    check(not boss.apply_status(StatusKind.FREEZE, 1, 1) and not boss.is_frozen(), "bosses are immune to freeze")
    check(boss.apply_status(StatusKind.STUN, 1, 1, True) and boss.is_stunned(), "a tower can explicitly stun bosses")
    f = _frozen(g, EnemyType.HEAP_SORT, 300)
    f.apply_status(StatusKind.FREEZE, 1, 2)
    check(f.is_stunned() and f.current_speed(1) == 0, "freeze stops movement")
    plain = _frozen(g, EnemyType.HEAP_SORT, 300)
    check(hit_for(g, f, 2, DamageType.ENERGY) == 4, "frozen enemies take x2 damage")
    check(hit_for(g, plain, 2, DamageType.ENERGY) == 2, "unfrozen control takes normal damage")
    m = _frozen(g, EnemyType.HEAP_SORT, 300)
    m.apply_status(StatusKind.MARKED, 0.2, 5)
    m.apply_status(StatusKind.MARKED, 0.5, 5)
    m.apply_status(StatusKind.MARKED_FLAT, 1, 5)
    m.apply_status(StatusKind.MARKED_FLAT, 2, 5)
    check(abs(m.get_marked_bonus() - 0.5) < 1e-9 and m.get_marked_flat() == 2, "strongest marks apply")
    d = hit_for(g, m, 2, DamageType.ENERGY)
    check(abs(d - (2 * 1.5 + 2)) < 1e-9, "damage with +50%% and +2 marks = 5, got %s" % d)
    burn = _frozen(g, EnemyType.HEAP_SORT, 300)
    burn.apply_burn(1, 3, None)
    burn.tick_statuses(1)
    burn.apply_burn(2, 3, None)
    check(burn.status_magnitude(StatusKind.DOT) == 2, "burn keeps the strongest dps")
    dot = burn.tick_statuses(1)
    check(abs(dot - 2) < 1e-9, "one second of burn = 2 damage, got %s" % dot)
    burn.tick_statuses(2.5)
    check(not burn.has_status(StatusKind.DOT), "burn expires 3 s after the refresh")
    lead = _frozen(g, EnemyType.HEAP_SORT, 300)
    lead.apply_status(StatusKind.MARKED_FLAT, 5, 5)
    check(hit_for(g, lead, 2, DamageType.SHARP) == 0, "marks never add damage to a blocked hit")


def test_armor_crack(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    heap = _frozen(g, EnemyType.HEAP_SORT, 300)
    heap.apply_status(StatusKind.ARMOR_CRACK, 1, 5)
    check(hit_for(g, heap, 2, DamageType.SHARP) == 2, "ARMOR CRACK removes Lead immunity")
    fort = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.FORTIFIED), 0, 300)
    fc = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.FORTIFIED), 0, 300)
    fc.apply_status(StatusKind.ARMOR_CRACK, 1, 5)
    a, b = hit_for(g, fort, 1, DamageType.ENERGY), hit_for(g, fc, 1, DamageType.ENERGY)
    check(a == 1 and b == 2, "ARMOR CRACK doubles damage vs Fortified: %s vs %s" % (a, b))
    fc.tick_statuses(6)
    check(not fc.is_armor_cracked(), "ARMOR CRACK lasts only its duration")


def test_knockback(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    r = g.get_map().get_routes()[0]
    e = _frozen(g, EnemyType.QUICK_SORT, 600)
    kb = HitSpec(0, DamageType.TRUE)
    kb.knockback = 10
    g.get_combat().apply_hit_simple(e, kb, None, 1, 0)
    check(abs(e.get_distance() - 590) < 1e-6 and e.get_position().dist(r.position_at(590)) < 1e-6, "knockback moves back along the path")
    start = _frozen(g, EnemyType.QUICK_SORT, 5)
    start.apply_knockback_uncapped(500)
    check(start.get_distance() == 0 and start.get_position().dist(r.position_at(0)) < 1e-6, "knockback never goes before the path start")
    boss = _frozen(g, EnemyType.BELLARMINE_COLLEGE_PREP, 600)
    g.get_combat().apply_hit_simple(boss, kb, None, 1, 0)
    check(boss.get_distance() == 600, "bosses are immune to knockback unless stated")
    kbb = HitSpec(0, DamageType.TRUE)
    kbb.knockback = 10
    kbb.boss_knockback = 10
    kbb.uncapped_knockback = True
    g.get_combat().apply_hit_simple(boss, kbb, None, 1, 0)
    check(boss.get_distance() == 590, "a tower can knock bosses back explicitly")
    pal = _frozen(g, EnemyType.PALANTIR, 600)
    g.get_combat().apply_hit_simple(pal, kbb, None, 1, 0)
    check(pal.get_distance() == 600, "Palantir phase 1 ignores knockback")
    ms = _frozen(g, EnemyType.MERGE_SORT, 700)
    pushed = sum(ms.apply_knockback(10, g.get_time()) for _ in range(40))
    check(pushed <= EnemyType.MERGE_SORT.speed * Enemy.BASE_SPEED * Enemy.KNOCKBACK_BUDGET + 1e-6, "knockback budget caps pushes")


def test_buff_stacking(check):
    g = new_game(0)
    gpt = tower_near_track(g, TowerType.GPT, 0, 300)
    base = gpt.get_stats().rate
    gpt.add_aura_buff(BuffStat.RATE, TowerType.COPILOT, 0.10)
    gpt.add_aura_buff(BuffStat.RATE, TowerType.COPILOT, 0.30)
    check(abs(gpt.buff_total(BuffStat.RATE) - 0.30) < 1e-9, "same-type buffs do not stack")
    gpt.add_aura_buff(BuffStat.RATE, TowerType.KAIJU_KAI, 0.25)
    check(abs(gpt.buff_total(BuffStat.RATE) - 0.55) < 1e-9, "different-type buffs add")
    check(abs(gpt.effective_rate(g) - base * 1.55) < 1e-9, "effective attack speed uses the summed buff")
    gpt.add_aura_buff(BuffStat.RATE, TowerType.SUNNY_JOE, 0.9)
    check(gpt.buff_total(BuffStat.RATE) == 1.0 and abs(gpt.effective_rate(g) - base * 2) < 1e-9, "rate buff capped at +100%")
    gpt.add_timed_buff(BuffStat.PIERCE_FLAT, TowerType.COPILOT, 8, 5)
    gpt.add_timed_buff(BuffStat.PIERCE_FLAT, TowerType.KAIJU_KAI, 6, 5)
    check(gpt.effective_pierce() == gpt.get_stats().pierce + 10, "pierce buff capped at +10")
    gpt.add_aura_buff(BuffStat.DAMAGE_FLAT, TowerType.COPILOT, 4)
    gpt.add_aura_buff(BuffStat.DAMAGE_FLAT, TowerType.KAIJU_KAI, 3)
    check(gpt.flat_damage_buff() == 5, "flat damage buff capped at +5")
    t2 = tower_near_track(g, TowerType.CLAUDE, 0, 500)
    t2.add_timed_buff(BuffStat.RATE, TowerType.COPILOT, 1.0, 2)
    check(t2.buff_total(BuffStat.RATE) == 1.0, "timed buff active")
    t2.tick_timers(g, 2.1)
    check(t2.buff_total(BuffStat.RATE) == 0, "timed buff expired")
    g2 = new_game(0)
    target = tower_near_track(g2, TowerType.GPT, 0, 300)
    c1 = force_place(g2, TowerType.COPILOT, buildable_near(g2, target.get_position().add(Vec(50, 0)), 80), 0)
    force_place(g2, TowerType.COPILOT, buildable_near(g2, target.get_position().add(Vec(-50, 0)), 80), 0)
    g2.get_tower_manager().recompute_auras()
    check(abs(target.get_aura_rate_bonus() - 0.10) < 1e-9, "two Copilots give +10%, not +20%")
    drone = force_place(g2, TowerType.TANIMBUS, buildable_near(g2, target.get_position().add(Vec(0, 70)), 100), 2)
    g2.get_tower_manager().recompute_auras()
    check(abs(target.get_aura_rate_bonus() - 0.25) < 1e-9, "Copilot + Tanimbus add")
    g2.sell_tower(c1)
    g2.get_tower_manager().recompute_auras()
    check(abs(target.get_aura_rate_bonus() - 0.25) < 1e-9, "remaining Copilot + Tanimbus still add")
    check(drone.is_alive(), "the support drone is still on the field")


def test_targeting(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    grok = tower_near_track(g, TowerType.GROK, 2, 450)
    c1, c2, c3 = (_frozen(g, EnemyType.QUICK_SORT, d) for d in (400, 410, 420))
    lone = _frozen(g, EnemyType.QUICK_SORT, 500)
    al = [c1, c2, c3, lone]
    check(clusters.density(c2, al) == 2 and clusters.density(lone, al) == 0, "density = other enemies within 60 px")
    check(clusters.densest(al, al) is c3, "densest cluster tie goes to First")
    grok.set_targeting(Targeting.FIRST)
    check(g.get_combat().acquire_targets(grok, 1)[0] is lone, "First targets the lone leader")
    grok.set_targeting(Targeting.DENSEST_CLUSTER)
    check(grok.get_targeting() is Targeting.DENSEST_CLUSTER, "Grok U2 can select Densest Cluster")
    check(g.get_combat().acquire_targets(grok, 1)[0] is c3, "Densest Cluster picks the cluster, ties to First")
    gpt = force_place(g, TowerType.GPT, buildable_near(g, grok.get_position().add(Vec(80, 0)), 100), 3)
    gpt.set_targeting(Targeting.DENSEST_CLUSTER)
    check(gpt.get_targeting() is Targeting.FIRST, "GPT cannot select Densest Cluster")
    grok1 = force_place(g, TowerType.GROK, buildable_near(g, grok.get_position().add(Vec(-80, 0)), 100), 1)
    grok1.set_targeting(Targeting.DENSEST_CLUSTER)
    check(grok1.get_targeting() is not Targeting.DENSEST_CLUSTER, "Grok U1 cannot select Densest Cluster yet")
    saw = False
    for _ in range(8):
        grok.cycle_targeting(1)
        saw = saw or grok.get_targeting() is Targeting.DENSEST_CLUSTER
    check(saw, "cycling includes Densest Cluster for Grok U2")
    gsaw = False
    for _ in range(8):
        gpt.cycle_targeting(1)
        gsaw = gsaw or gpt.get_targeting() is Targeting.DENSEST_CLUSTER
    check(not gsaw, "cycling never offers Densest Cluster to other towers")


def test_camo_detection(check):
    built_in = {TowerType.GROK, TowerType.PERPLEXITY, TowerType.NIK_SCOPE}
    for t in TowerType.purchasable():
        check(catalog.get(t).stats_for_tier(0).sees_camo == (t in built_in), "%s base camo detection" % t)
    for t in (TowerType.GEMINI, TowerType.LLAMA):
        d = catalog.get(t)
        check(not d.stats_for_tier(1).sees_camo and d.stats_for_tier(2).sees_camo and d.stats_for_tier(3).sees_camo, "%s gains camo at U2" % t)
    ml = catalog.get(TowerType.MR_LINDEMANN)
    check(not ml.stats_for_tier(0).sees_camo and ml.stats_for_tier(1).sees_camo and ml.stats_for_tier(3).sees_camo, "Mr. Lindemann camo at U1")
    for t in TowerType.purchasable():
        if t in built_in or t in (TowerType.GEMINI, TowerType.LLAMA, TowerType.MR_LINDEMANN):
            continue
        dd = catalog.get(t)
        check(not dd.stats_for_tier(len(dd.upgrades)).sees_camo, "%s has no camo detection" % t)
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    gpt = tower_near_track(g, TowerType.GPT, 0, 300)
    far = force_place(g, TowerType.CLAUDE, buildable_near(g, Vec(1000, 800), 100), 0)
    perp = force_place(g, TowerType.PERPLEXITY, buildable_near(g, gpt.get_position().add(Vec(70, 0)), 80), 0)
    g.get_tower_manager().recompute_auras()
    check(gpt.can_see_camo() and not far.can_see_camo(), "radius grants detection; far towers do not")
    g.upgrade_tower(perp)
    g.get_tower_manager().recompute_auras()
    check(gpt.can_see_camo() and far.can_see_camo(), "Perplexity U1 grants detection map-wide")
    g.sell_tower(perp)
    check(not gpt.can_see_camo() and not far.can_see_camo(), "detection disappears with Perplexity")


def test_factions(check):
    T, F = TowerType, Faction
    pairs = [(T.KAIJU_KAI, F.HERO), (T.BLITZ_ARNAV, F.HERO), (T.CHILLSTIN, F.HERO), (T.BOOM_SAM, F.HERO), (T.SUNNY_JOE, F.HERO),
             (T.NIK_SCOPE, F.HERO), (T.GEMINI, F.PRIMARY), (T.CLAUDE, F.PRIMARY), (T.GPT, F.PRIMARY), (T.ZETHOS, F.PRIMARY),
             (T.DEEPSEEK, F.MILITARY), (T.COPILOT, F.MILITARY), (T.DALLE, F.MAGIC), (T.SORA, F.MAGIC), (T.SUNO, F.MAGIC),
             (T.GROK, F.SUPPORT), (T.PERPLEXITY, F.SUPPORT), (T.QWEN, F.TITAN), (T.LLAMA, F.TITAN), (T.MISTRAL, F.TITAN),
             (T.COHERE, F.TITAN), (T.GLM, F.TITAN), (T.KIMI, F.TITAN), (T.MINIMAX, F.TITAN)]
    for t, f in pairs:
        check(t.faction is f, "%s faction" % t)


def test_hero_uniqueness(check):
    g = new_game(0)
    g.add_cash(100000, None)
    p1 = buildable_near(g, Vec(300, 300), 100)
    p2 = buildable_near(g, Vec(600, 300), 100)
    locked = g.placement_problem(TowerType.KAIJU_KAI, p1)
    check(g.place_tower(TowerType.KAIJU_KAI, p1) is None and locked is not None and "Hero Store" in locked, "locked hero refused: %s" % locked)
    check(g.purchase_hero(TowerType.KAIJU_KAI), "Kaiju Kai bought in the Hero Store")
    kaiju = g.place_tower(TowerType.KAIJU_KAI, p1)
    check(kaiju is not None, "first copy placed")
    check(g.place_tower(TowerType.KAIJU_KAI, p2) is None, "a second copy is refused")
    why = g.placement_problem(TowerType.KAIJU_KAI, p2)
    check(why is not None and "already deployed" in why, "clear failure reason: %s" % why)
    check(shop.unavailable_reason(g, TowerType.KAIJU_KAI) is not None, "shop reason for the UI")
    check(shop.unavailable_reason(g, TowerType.GPT) is None, "non-heroes are not limited")
    g.purchase_hero(TowerType.BLITZ_ARNAV)
    check(g.place_tower(TowerType.BLITZ_ARNAV, p2) is not None, "a different unlocked hero can be placed")
    check(g.place_tower(TowerType.GPT, buildable_near(g, Vec(300, 600), 100)) is not None
          and g.place_tower(TowerType.GPT, buildable_near(g, Vec(500, 600), 100)) is not None, "multiple normal towers allowed")
    g.sell_tower(kaiju)
    check(not kaiju.is_alive() and g.place_tower(TowerType.KAIJU_KAI, p1) is None, "a dismissed hero cannot be redeployed")


def test_cost_table(check):
    T = TowerType
    table = [(T.GEMINI, 400, 650, 700, 1200, 2950), (T.CLAUDE, 450, 550, 650, 1100, 2750), (T.GPT, 500, 750, 800, 1300, 3350),
             (T.DEEPSEEK, 600, 850, 900, 1500, 3850), (T.COPILOT, 350, 350, 600, 1000, 2300),
             (T.DALLE, 550, 500, 850, 1400, 3300), (T.SORA, 700, 650, 1000, 1800, 4150), (T.SUNO, 500, 500, 800, 1350, 3150),
             (T.GROK, 650, 600, 950, 1600, 3800), (T.PERPLEXITY, 450, 450, 750, 1250, 2900),
             (T.QWEN, 750, 1100, 1200, 2000, 5050), (T.LLAMA, 700, 1000, 1100, 1900, 4700), (T.MISTRAL, 650, 650, 1050, 1750, 4100),
             (T.COHERE, 800, 800, 1300, 2200, 5100), (T.GLM, 600, 550, 900, 1500, 3550), (T.KIMI, 700, 700, 1150, 1950, 4500),
             (T.MINIMAX, 650, 1050, 1050, 1800, 4550)]
    check(len(table) == 17, "table lists the 17 standard towers")
    for row in table:
        d = catalog.get(row[0])
        check(d.base_cost == row[1], "%s base cost" % row[0])
        for i in range(3):
            check(d.upgrades[i].cost == row[2 + i], "%s U%d cost" % (row[0], i + 1))
        s = d.base_cost + sum(u.cost for u in d.upgrades)
        check(s == row[5] and d.total_cost() == row[5], "%s total $%d (got %d)" % (row[0], row[5], s))
    z = catalog.get(T.ZETHOS)
    zc = (350, 650, 1200, 2500)
    check(z.base_cost == 650 and len(z.upgrades) == 4, "Zethos $650 with four upgrades")
    for i in range(4):
        check(z.upgrades[i].cost == zc[i], "Zethos tier %d cost" % (i + 1))
    check(z.total_cost() == 5350, "Zethos fully upgraded total $5,350")


def test_tier_names(check):
    names = [("Quantum Pulse", "Quantum Acceleration", "Dimensional Fracture", "Quantum Singularity", "Zethos: Reality Engine"),
             ("Gemini 3.7 Flash", "Gemini 3.8 Flash", "Gemini 3.1 Pro", "Gemini 4 Argon"),
             ("Claude Haiku 5.5", "Claude Sonnet 5.5", "Claude Opus 5.5", "Claude Fable 5.1"),
             ("GPT-5.6 Terra", "GPT-6 Luna", "GPT-6 Astra", "GPT-6.1 Sol"),
             ("DeepSeek V4 Flash", "DeepSeek V4.1 Flash", "DeepSeek R1", "DeepSeek V4 Pro"),
             ("Qwen3.8 Flash", "Qwen3.6 Max", "Qwen3.7 Plus", "Qwen3.8 Max"),
             ("Llama 4 Scout", "Llama 4 Maverick", "Muse Glimmer", "Muse Wonder"),
             ("MiniMax M2.5", "MiniMax M2.7", "MiniMax M3", "MiniMax M3.1 Flash")]
    types = (TowerType.ZETHOS, TowerType.GEMINI, TowerType.CLAUDE, TowerType.GPT, TowerType.DEEPSEEK, TowerType.QWEN, TowerType.LLAMA, TowerType.MINIMAX)
    for t, n in zip(types, names):
        check(catalog.get(t).tier_labels == n, "%s tier labels" % t)
    check(TowerType.GEMINI.display_name == "Gemini" and catalog.get(TowerType.GEMINI).subtitle == "Prism Blaster", "family name + subtitle")
    check(catalog.get(TowerType.CLAUDE).subtitle == "Ink Weaver" and catalog.get(TowerType.KIMI).subtitle == "Dimensional Assassin", "nickname subtitles")
