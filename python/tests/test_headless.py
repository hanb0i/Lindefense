"""Section-16 checklist of the headless game (port of HeadlessTests)."""
import pytest
import math

from kit import (DT, buildable_near, force_place, hit, hit_for, kill_outright, mods, new_game, run_seconds,
                 spawn_at, ticks)
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy.boss import Boss
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.javacompat import jround
from lindefense.map import maps
from lindefense.map.game_map import WIDTH, HEIGHT, TRACK_HALF_WIDTH
from lindefense.map.maps import AbandonedDataCenter, HallucinationCanyon, LegacyMonolith, NeuralNetwork, SiliconCircuit, SingularityCore
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.misc import AdminMode
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import Targeting, TowerType
from lindefense.wave import waves


def _same_mods(e, gr):
    m = set(e.get_modifiers())
    if e.get_type().has_innate_camo() and Modifier.CAMO not in gr.modifiers:
        m.discard(Modifier.CAMO)
    return m == set(gr.modifiers)


def test_catalog_integrity(check):
    p = TowerType.purchasable()
    check(len(p) == 36, "36 placeable units, got %d" % len(p))
    check(len(TowerType.heroes()) == 18 and len(TowerType.shop_towers()) == 18, "18 heroes, 18 shop towers")
    heroes = 0
    for t in p:
        d = catalog.get(t)
        check(d is not None, "def for %s" % t)
        ups = catalog.ZETHOS_UPGRADES if t is TowerType.ZETHOS else catalog.STANDARD_UPGRADES
        check(len(d.upgrades) == ups, "%s has exactly %d upgrades" % (t, ups))
        if catalog.has_active_ability(t):
            check(d.ability is not None and d.ability.cooldown > 0, "%s has ability with cooldown" % t)
        else:
            check(d.ability is None, "%s has no special ability" % t)
        check(d.base_cost > 0 and d.unlock_cost > 0 if t.is_hero() else d.base_cost > 0 and d.unlock_cost == 0, "%s costs" % t)
        for i in range(ups + 1):
            check(d.stats_for_tier(i) is not None, "%s tier %d stats" % (t, i))
        for i in range(ups):
            check(d.upgrades[i].name == d.tier_labels[i + 1], "%s upgrade name is the tier label" % t)
        if t.is_hero():
            heroes += 1
        check(len(d.tier_labels) == ups + 1, "%s tier labels" % t)
        check(bool(d.subtitle), "%s has a nickname subtitle" % t)
    check(heroes == 18, "18 heroes")
    species = sum(1 for e in EnemyType if e.is_spawnable_species() and not e.is_boss())
    check(species == 16, "16 standard enemy species, got %d" % species)
    check(sum(1 for e in EnemyType if e.is_boss()) == 5, "5 bosses")


def test_purchase_upgrade_sell(check):
    g = new_game(0)
    p = buildable_near(g, Vec(400, 250), 200)
    cash0 = g.get_cash()
    t = g.place_tower(TowerType.GPT, p)
    check(t is not None, "placed GPT")
    check(g.get_cash() == cash0 - 500, "cash deducted 500, cash=%s" % g.get_cash())
    check(t.get_tier() == 0, "tier 0")
    g.add_cash(5000, None)
    c = g.get_cash()
    gpt_def = catalog.get(TowerType.GPT)
    check(g.upgrade_tower(t) and t.get_tier() == 1 and g.get_cash() == c - gpt_def.upgrades[0].cost, "upgrade 1 cost")
    check(t.get_tier_label() == "GPT-6 Luna", "tier label is the model name")
    check(g.upgrade_tower(t) and t.get_tier() == 2, "upgrade 2")
    check(g.upgrade_tower(t) and t.get_tier() == 3 and t.is_maxed(), "upgrade 3 (maxed)")
    check(not g.upgrade_tower(t) and t.get_tier() == 3, "no 4th upgrade")
    invested = 500 + sum(u.cost for u in gpt_def.upgrades)
    check(t.get_invested_cost() == invested, "invested %d" % invested)
    expected = int(math.floor(invested * 0.7))
    check(shop.sell_value(t) == expected, "sell value 70%")
    before = g.get_cash()
    refund = g.sell_tower(t)
    check(refund == expected and g.get_cash() == before + expected, "refund applied")
    check(not g.get_tower_manager().get_towers(), "tower removed")
    g2 = new_game(0)
    check(g2.place_tower(TowerType.KAIJU_KAI, p) is None, "a locked hero cannot be placed")
    check(not g2.purchase_hero(TowerType.KAIJU_KAI), "cannot afford Kaiju Kai's unlock at start")
    check(g2.get_cash() == Game.START_CASH, "cash unchanged after failed purchase")
    g3 = new_game(0)
    g3.set_hero_limit(2147483647)
    g3.add_cash(1_000_000, None)
    for i, type_ in enumerate(TowerType.purchasable()):
        q = Vec(80 + (i % 10) * 100, 60 + (i // 10) * 60)
        b = buildable_near(g3, q, 150)
        if type_.is_hero():
            check(g3.place_tower(type_, b) is None, "%s locked: cannot be placed" % type_)
            check(g3.purchase_hero(type_) and not g3.purchase_hero(type_), "%s bought once" % type_)
        tt = g3.place_tower(type_, b)
        check(tt is not None, "place %s" % type_)
        if tt is None:
            continue
        ups = len(catalog.get(type_).upgrades)
        for k in range(ups):
            check(g3.upgrade_tower(tt), "%s upgrade %d" % (type_, k + 1))
        check(not g3.upgrade_tower(tt), "%s no upgrade past tier %d" % (type_, ups))
        check(tt.get_invested_cost() == catalog.get(type_).total_cost(), "%s invested matches" % type_)
        check(tt.get_stats() is not None and tt.is_maxed(), "%s T3 stats" % type_)


def test_placement_rules(check):
    g = new_game(0)
    g.add_cash(10000, None)
    r = g.get_map().get_routes()[0]
    tm = g.get_tower_manager()
    check(tm.placement_problem(TowerType.GPT, r.position_at(300)) is not None, "cannot build on track")
    check(tm.placement_problem(TowerType.GPT, Vec(-50, 100)) is not None, "cannot build outside")
    check(tm.placement_problem(TowerType.GPT, Vec(980, 60)) is not None, "cannot build on obstacle (CPU chip)")
    ok = buildable_near(g, Vec(400, 250), 200)
    t = g.place_tower(TowerType.GPT, ok)
    check(t is not None, "valid placement")
    check(tm.placement_problem(TowerType.CLAUDE, ok.add(Vec(10, 0))) is not None, "cannot overlap")
    check(tm.tower_at(ok) is t, "towerAt finds tower")
    g4 = new_game(3)
    check(not g4.get_map().is_buildable(Vec(20, 20), 20), "outside arena not buildable")
    check(not g4.get_map().is_buildable(Vec(600, 450), 20), "vortex not buildable")


def test_rewards_and_no_duplicate_kills(check):
    g = new_game(0)
    c0 = g.get_cash()
    sa = spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 100)
    kill_outright(g, sa)
    rs = g.get_reward_scale()
    check(g.get_cash() == c0 + jround(3 * rs), "Static Array reward 3 x %s" % rs)
    check(not sa.is_alive(), "dead")
    live = g.get_enemy_manager().get_enemies()
    check(len(live) == 1 and live[0].get_type() is EnemyType.PRIMITIVE_VARIABLE, "child primitive spawned")
    child = live[0]
    check(abs(child.get_distance() - 100) < 1, "child at parent position")
    c1 = g.get_cash()
    g.get_combat().apply_hit_simple(sa, HitSpec(100, DamageType.TRUE), None, 1, 0)
    g.get_enemy_manager().kill(sa)
    g.get_enemy_manager().update(0)
    check(g.get_cash() == c1, "no duplicate reward for re-killing")
    kill_outright(g, child)
    check(g.get_cash() == c1 + jround(2 * rs), "child reward")
    c2 = g.get_cash()
    leaker = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, g.get_map().get_routes()[0].get_total_length() - 1)
    g.run(5)
    check(leaker.has_leaked() and g.get_cash() == c2, "leaked enemy pays nothing")
    check(waves.reward_scale(90) < waves.reward_scale(10) and waves.reward_scale(90) < waves.reward_scale(70), "reward scale tapers off")


def test_lives_loss_on_leak(check):
    g = new_game(1)
    ln = g.get_map().get_routes()[0].get_total_length()
    spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, ln - 2)
    g.run(10)
    check(g.get_lives() == 99, "primitive costs 1 life, lives=%d" % g.get_lives())
    spawn_at(g, EnemyType.TIMSORT, None, 0, ln - 2)
    g.run(10)
    check(g.get_lives() == 99 - 8, "TimSort costs 8 lives")
    spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, ln - 2)
    g.run(20)
    check(g.get_lives() == 91 - 30, "MOAB costs 30 lives")
    check(not g.get_enemy_manager().get_enemies(), "leaked enemies removed")


def test_targeting_priorities(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    r = g.get_map().get_routes()[0]
    t = force_place(g, TowerType.GPT, buildable_near(g, r.position_at(400).add(Vec(0, -60)), 80), 1)
    a = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 330)
    b = spawn_at(g, EnemyType.MERGE_SORT, None, 0, 400)
    c = spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 470)
    cb = g.get_combat()
    t.set_targeting(Targeting.FIRST)
    check(cb.acquire_targets(t, 1)[0] is c, "FIRST = closest to exit")
    t.set_targeting(Targeting.LAST)
    check(cb.acquire_targets(t, 1)[0] is a, "LAST = closest to entrance")
    t.set_targeting(Targeting.STRONGEST)
    check(cb.acquire_targets(t, 1)[0] is b, "STRONGEST = most HP")
    t.set_targeting(Targeting.WEAKEST)
    check(cb.acquire_targets(t, 1)[0] is a, "WEAKEST = least HP")
    t.set_targeting(Targeting.CLOSEST)
    check(cb.acquire_targets(t, 1)[0] is b, "CLOSEST = nearest to tower")
    check(len(cb.acquire_targets(t, 3)) == 3, "multi-target returns 3")
    spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 1500)
    check(len(cb.acquire_targets(t, 10)) == 3, "out-of-range excluded")


def test_camo_detection(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    r = g.get_map().get_routes()[0]
    p = buildable_near(g, r.position_at(400).add(Vec(0, -60)), 80)
    gpt = force_place(g, TowerType.GPT, p, 0)
    camo = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, mods(Modifier.CAMO), 0, 400)
    cb = g.get_combat()
    check(not cb.acquire_targets(gpt, 1), "GPT cannot target camo")
    g.run(60)
    check(camo.get_hp() == camo.get_max_hp(), "camo not damaged by GPT")
    perp = force_place(g, TowerType.PERPLEXITY, buildable_near(g, p.add(Vec(60, 0)), 100), 0)
    check(cb.acquire_targets(perp, 1), "Perplexity targets camo")
    g.get_tower_manager().recompute_auras()
    check(gpt.can_see_camo(), "GPT gains detection from Perplexity aura")
    check(cb.acquire_targets(gpt, 1), "GPT can now target camo")
    g.sell_tower(perp)
    check(not gpt.can_see_camo(), "detection lost after selling Perplexity")
    camo.apply_status(StatusKind.REVEALED, 1, 5)
    check(cb.acquire_targets(gpt, 1), "revealed camo is targetable")
    ddt = spawn_at(g, EnemyType.LOCKHEED_MARTIN, None, 0, 100)
    check(ddt.is_camo(), "Lockheed innate camo")
    g2 = new_game(0)
    g2.set_global_enemy_speed_multiplier(0)
    gpt2 = force_place(g2, TowerType.GPT, p, 0)
    spawn_at(g2, EnemyType.PRIMITIVE_VARIABLE, mods(Modifier.CAMO), 0, 400)
    plain = spawn_at(g2, EnemyType.STATIC_ARRAY, None, 0, 420)
    g2.run(120)
    check(plain.get_hp() < plain.get_max_hp() or not plain.is_alive(), "plain enemy hit while camo ignored")
    check(gpt2.get_damage_dealt() > 0, "tower dealt damage")


def test_fortified_and_regrow(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    f = spawn_at(g, EnemyType.HEAP_SORT, mods(Modifier.FORTIFIED), 0, 100)
    check(f.get_max_hp() == 16, "fortified heap has 16 HP")
    n = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 100)
    check(n.get_max_hp() == 8, "normal heap 8 HP")
    r = spawn_at(g, EnemyType.MERGE_SORT, mods(Modifier.REGROW), 0, 100)
    g.get_combat().apply_hit_simple(r, HitSpec(3, DamageType.TRUE), None, 1, 0)
    check(r.get_hp() == 3, "regrow enemy damaged to 3")
    g.run(ticks(Enemy.REGROW_INTERVAL) + 2)
    check(r.get_hp() == 4, "regrow restored 1 HP after interval, hp=%s" % r.get_hp())
    g.run(int(Enemy.REGROW_INTERVAL / DT * 5))
    check(r.get_hp() == 6, "regrow caps at max")
    ff = spawn_at(g, EnemyType.QUICK_SORT, mods(Modifier.FORTIFIED), 0, 100)
    check(ff.get_max_hp() == 14, "fortified quick 14")
    check(ff.strip_fortified() and not ff.is_fortified() and ff.get_hp() <= 7, "strip fortified halves")
    heap = spawn_at(g, EnemyType.HEAP_SORT, None, 0, 100)
    check(g.get_combat().apply_hit_simple(heap, HitSpec(3, DamageType.SHARP), None, 1, 0) == 0, "heap immune to Sharp")
    lead = HitSpec(3, DamageType.SHARP)
    lead.ignores_resistance = True
    check(g.get_combat().apply_hit_simple(heap, lead, None, 1, 0) == 3, "Sharp that can damage Lead hurts heap")
    moab = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 100)
    d1 = g.get_combat().apply_hit_simple(moab, HitSpec(100, DamageType.ENERGY), None, 1, 0)
    check(abs(d1 - 75) < 0.01, "MOAB armour 25%%: got %s" % d1)
    ap = HitSpec(100, DamageType.ENERGY)
    ap.armor_pierce = 1
    check(abs(g.get_combat().apply_hit_simple(moab, ap, None, 1, 0) - 100) < 0.01, "armour piercing ignores armour")
    bfb = spawn_at(g, EnemyType.SW_RESOURCE_CONSULTANT, None, 0, 100)
    weak = g.get_combat().apply_hit_simple(bfb, HitSpec(2, DamageType.ENERGY), None, 1, 0)
    check(abs(weak - 2 * 0.6 * 0.5) < 0.01, "BFB halves weak hits, got %s" % weak)


def test_splitter_children(check):
    E = EnemyType
    cases = [(E.STATIC_ARRAY, [E.PRIMITIVE_VARIABLE], [1]), (E.DYNAMIC_ARRAY, [E.STATIC_ARRAY], [1]),
             (E.MERGE_SORT, [E.MERGE_RUN], [2]), (E.QUICK_SORT, [E.QUICK_PARTITION], [2]),
             (E.COUNTING_SORT, [E.PRIMITIVE_VARIABLE], [4]), (E.TIMSORT, [E.MERGE_SORT, E.INSERTION_SORT], [1, 1])]
    for parent, types, counts in cases:
        g = new_game(0)
        g.set_global_enemy_speed_multiplier(0)
        e = spawn_at(g, parent, mods(Modifier.CAMO, Modifier.REGROW, Modifier.FORTIFIED), 0, 300)
        kill_outright(g, e)
        for ty, cnt in zip(types, counts):
            n = g.get_enemy_manager().count_of_type(ty)
            check(n == cnt, "%s -> %d x %s, got %d" % (parent, cnt, ty, n))
        total = sum(counts)
        check(len(g.get_enemy_manager().get_enemies()) == total, "%s total children %d" % (parent, total))
        for ch in g.get_enemy_manager().get_enemies():
            check(ch.get_max_hp() == ch.get_type().base_hp, "%s child HP = base" % parent)
            check(ch.is_camo() and ch.is_regrow() and not ch.is_fortified(), "%s child inherits camo+regrow, not fortified" % parent)
            check(abs(ch.get_distance() - 300) <= 6 * total, "%s child near parent position" % parent)
    check(E.MERGE_RUN.base_hp == 2 and E.QUICK_PARTITION.base_hp == 3, "Merge Run 2 HP, Quick Partition 3 HP")
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    spawn_at(g, E.TIMSORT, None, 0, 300)
    guard = 0
    while g.get_enemy_manager().get_enemies() and guard < 50:
        guard += 1
        for e in list(g.get_enemy_manager().get_enemies()):
            g.get_combat().apply_hit_simple(e, HitSpec(1e9, DamageType.TRUE), None, 1, 0)
        g.get_enemy_manager().update(0)
    check(guard < 50, "TimSort chain terminates")
    check(g.get_enemy_manager().get_total_killed() == 5, "TimSort chain = 5 kills, got %d" % g.get_enemy_manager().get_total_killed())


def test_boss_children(check):
    E = EnemyType
    for parent, child, cnt in [(E.BELLARMINE_COLLEGE_PREP, E.QUICK_SORT, 4), (E.SW_RESOURCE_CONSULTANT, E.BELLARMINE_COLLEGE_PREP, 3),
                               (E.THREE_COM, E.SW_RESOURCE_CONSULTANT, 3), (E.LOCKHEED_MARTIN, E.QUICK_SORT, 4)]:
        g = new_game(1)
        g.set_global_enemy_speed_multiplier(0)
        b = spawn_at(g, parent, mods(Modifier.FORTIFIED), 0, 500)
        check(isinstance(b, Boss), "%s is a Boss" % parent)
        cash = g.get_cash()
        kill_outright(g, b)
        n = g.get_enemy_manager().count_of_type(child)
        check(n == cnt, "%s releases %d %s, got %d" % (parent, cnt, child, n))
        check(g.get_cash() == cash + jround(parent.reward * g.get_reward_scale()), "%s reward paid once" % parent)
        for ch in g.get_enemy_manager().get_enemies():
            check(ch.is_fortified(), "%s children inherit Fortified from boss" % parent)
            if parent is E.LOCKHEED_MARTIN:
                check(ch.is_camo(), "Lockheed children camo")
    g = new_game(1)
    g.set_global_enemy_speed_multiplier(0)
    pal = spawn_at(g, E.PALANTIR, None, 0, 500)
    kill_outright(g, pal)
    check(not g.get_enemy_manager().get_enemies(), "Palantir releases no children (victory)")
    check(g.is_victory_sequence_active(), "victory sequence started")


def test_enemy_mechanics(check):
    E = EnemyType
    g = new_game(1)
    g.set_global_enemy_speed_multiplier(0)
    dll = spawn_at(g, E.DOUBLY_LINKED_LIST, None, 0, 100)
    s0 = dll.current_speed(1)
    g.get_combat().apply_hit_simple(dll, HitSpec(1, DamageType.TRUE), None, 1, 0)
    check(dll.current_speed(1) > s0, "DLL faster after damage")
    shell = spawn_at(g, E.SHELL_SORT, None, 0, 100)
    g.run(ticks(3.1))
    check(abs(shell.get_distance() - 240) < 1, "Shell jumped 140 px, d=%s" % shell.get_distance())
    g2 = new_game(1)
    g2.set_global_enemy_speed_multiplier(0)
    heap = spawn_at(g2, E.HEAP_SORT, None, 0, 400)
    behind = spawn_at(g2, E.MERGE_SORT, None, 0, 350)
    ahead = spawn_at(g2, E.MERGE_SORT, None, 0, 450)
    g2.run(2)
    dB = g2.get_combat().apply_hit_simple(behind, HitSpec(2, DamageType.ENERGY), None, 1, 0)
    dA = g2.get_combat().apply_hit_simple(ahead, HitSpec(2, DamageType.ENERGY), None, 1, 0)
    check(dB == 1 and dA == 2, "heap shields enemy behind (1) not ahead (2): %s,%s" % (dB, dA))
    heap.apply_status(StatusKind.DISRUPTED, 1, 5)
    g2.run(3)
    check(g2.get_combat().apply_hit_simple(behind, HitSpec(2, DamageType.ENERGY), None, 1, 0) == 2, "disrupted heap does not shield")
    g3 = new_game(1)
    g3.set_global_enemy_speed_multiplier(0)
    bucket = spawn_at(g3, E.BUCKET_SORT, None, 0, 400)
    small = spawn_at(g3, E.PRIMITIVE_VARIABLE, None, 0, 410)
    big = spawn_at(g3, E.MERGE_SORT, None, 0, 405)
    g3.run(ticks(1.1))
    check(small.is_stored() and small in bucket.get_stored_enemies(), "bucket stored primitive")
    check(not big.is_stored(), "bucket ignores base HP > 5")
    check(small not in g3.get_enemy_manager().get_enemies(), "stored enemy off the track")
    gp = force_place(g3, TowerType.GPT, buildable_near(g3, g3.get_map().get_routes()[0].position_at(400).add(Vec(0, 70)), 100), 0)
    check(len(g3.get_combat().acquire_targets(gp, 10)) == 2, "stored enemy untargetable")
    kill_outright(g3, bucket)
    check(not small.is_stored() and small in g3.get_enemy_manager().get_enemies(), "bucket released stored enemy")
    g4 = new_game(1)
    ln = g4.get_map().get_routes()[0].get_total_length()
    g4.set_global_enemy_speed_multiplier(0)
    bk = spawn_at(g4, E.BUCKET_SORT, None, 0, ln - 100)
    spawn_at(g4, E.PRIMITIVE_VARIABLE, None, 0, ln - 95)
    g4.run(ticks(1.1))
    check(len(bk.get_stored_enemies()) == 1, "stored before leak")
    g4.set_global_enemy_speed_multiplier(1)
    g4.run(600)
    check(g4.get_lives() == 100 - 5 - 1, "bucket leak costs 5 + 1 lives, lives=%d" % g4.get_lives())
    g5 = new_game(1)
    rdx = spawn_at(g5, E.RADIX_SORT, None, 0, 100)
    cb = g5.get_combat()
    check(rdx.radix_phase() == 0 and not rdx.is_lead_type(), "radix phase 0 not Lead-type")
    check(cb.apply_hit_simple(rdx, HitSpec(2, DamageType.SHARP), None, 1, 0) == 2, "radix phase 0 takes Sharp")
    check(rdx.radix_phase() == 1 and rdx.is_lead_type(), "radix phase 1 armoured")
    check(cb.apply_hit_simple(rdx, HitSpec(2, DamageType.SHARP), None, 1, 0) == 0, "radix phase 1 immune to Sharp")
    check(cb.apply_hit_simple(rdx, HitSpec(1, DamageType.ENERGY), None, 1, 0) == 1, "radix armoured phase takes Energy")
    cb.apply_hit_simple(rdx, HitSpec(2, DamageType.TRUE), None, 1, 0)
    check(rdx.radix_phase() == 2 and rdx.is_lead_type(), "radix phase 2 still armoured")
    cb.apply_hit_simple(rdx, HitSpec(1, DamageType.TRUE), None, 1, 0)
    check(rdx.radix_phase() == 3 and cb.apply_hit_simple(rdx, HitSpec(1, DamageType.EXPLOSIVE), None, 1, 0) == 1, "radix phase 3 takes Explosive")
    g6 = new_game(1)
    g6.set_global_enemy_speed_multiplier(0)
    bub = spawn_at(g6, E.BUBBLE_SORT, None, 0, 300)
    front = spawn_at(g6, E.PRIMITIVE_VARIABLE, None, 0, 330)
    g6.run(ticks(3.1))
    check(abs(bub.get_distance() - 330) < 1 and abs(front.get_distance() - 300) < 1, "bubble swapped positions")
    g7 = new_game(1)
    g7.set_global_enemy_speed_multiplier(0)
    sel = spawn_at(g7, E.SELECTION_SORT, None, 0, 300)
    spawn_at(g7, E.PRIMITIVE_VARIABLE, None, 0, 350)
    spawn_at(g7, E.PRIMITIVE_VARIABLE, None, 0, 420)
    g7.run(ticks(2.6))
    check(abs(sel.get_distance() - 426) < 1, "selection jumped to group front, d=%s" % sel.get_distance())
    g8 = new_game(1)
    g8.set_global_enemy_speed_multiplier(0)
    ins = spawn_at(g8, E.INSERTION_SORT, None, 0, 300)
    spawn_at(g8, E.PRIMITIVE_VARIABLE, None, 0, 340)
    spawn_at(g8, E.PRIMITIVE_VARIABLE, None, 0, 420)
    g8.run(ticks(2.1))
    check(abs(ins.get_distance() - 346) < 1, "insertion leapfrogged nearest, d=%s" % ins.get_distance())
    s = spawn_at(g8, E.PRIMITIVE_VARIABLE, None, 0, 100)
    s.apply_status(StatusKind.SLOW, 0.5, 2)
    check(abs(s.current_speed(1) - Enemy.BASE_SPEED * 0.5) < 0.01, "slow halves speed")
    s.apply_status(StatusKind.STUN, 1, 1)
    check(s.current_speed(1) == 0, "stun stops movement")
    before = s.get_distance()
    s.shift_distance(-30)
    check(s.get_distance() == before - 30 and s.get_position().dist(s.get_route().position_at(before - 30)) < 0.01, "knockback moves along path")
    kb = spawn_at(g8, E.MERGE_SORT, None, 0, 500)
    pushed = sum(kb.apply_knockback(10, g8.get_time()) for _ in range(50))
    cap = E.MERGE_SORT.speed * Enemy.BASE_SPEED * Enemy.KNOCKBACK_BUDGET
    check(abs(pushed - cap) < 1e-6 and abs(kb.get_distance() - (500 - cap)) < 1e-6, "knockback capped per second at %s (got %s)" % (cap, pushed))
    g8.run(61)
    check(kb.apply_knockback(10, g8.get_time()) == 10, "knockback budget refreshes after a second")


def test_projectile_collision(check):
    E = EnemyType
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    r = g.get_map().get_routes()[0]
    p = buildable_near(g, r.position_at(400).add(Vec(0, -70)), 80)
    claude = force_place(g, TowerType.CLAUDE, p, 0)
    far = spawn_at(g, E.MERGE_SORT, None, 0, 1500)
    near = spawn_at(g, E.MERGE_SORT, None, 0, 400)
    g.run(90)
    check(near.get_hp() < near.get_max_hp(), "projectile hit the in-range enemy")
    check(far.get_hp() == far.get_max_hp(), "out-of-range enemy untouched")
    check(claude.get_damage_dealt() > 0, "damage attributed to tower")
    g2 = new_game(0)
    g2.set_global_enemy_speed_multiplier(0)
    kai = force_place(g2, TowerType.KAIJU_KAI, p, 0)
    group = [spawn_at(g2, E.HEAP_SORT, None, 0, 400 + i * 15) for i in range(4)]
    g2.run(120)
    hit_n = sum(1 for e in group if e.get_hp() < e.get_max_hp() or not e.is_alive())
    check(hit_n >= 3, "splash hit several enemies (%d)" % hit_n)
    check(kai.get_damage_dealt() > 0, "Kaiju dealt damage")
    g3 = new_game(0)
    g3.set_global_enemy_speed_multiplier(0)
    force_place(g3, TowerType.GEMINI, p, 1)
    g3e = [spawn_at(g3, E.HEAP_SORT, None, 0, 400 + i * 40) for i in range(4)]
    g3.run(60)
    chained = sum(1 for e in g3e if e.get_hp() < e.get_max_hp())
    check(chained >= 3, "chain hit several enemies (%d)" % chained)
    g4 = new_game(0)
    g4.set_global_enemy_speed_multiplier(0)
    force_place(g4, TowerType.SUNO, p, 0)
    force_place(g4, TowerType.COHERE, buildable_near(g4, p.add(Vec(70, 0)), 100), 0)
    e4 = spawn_at(g4, E.HEAP_SORT, None, 0, 400)
    g4.run(70)
    check(e4.get_hp() < e4.get_max_hp(), "pulse/beam damaged enemy")
    g5 = new_game(0)
    g5.set_global_enemy_speed_multiplier(0)
    force_place(g5, TowerType.MINIMAX, p, 0)
    g5e = [spawn_at(g5, E.HEAP_SORT, None, 0, 400 + i * 30) for i in range(3)]
    g5.run(120)
    bounced = sum(1 for e in g5e if e.get_hp() < e.get_max_hp())
    check(bounced >= 2, "bounce hit several enemies (%d)" % bounced)


def test_wave_compositions(check):
    E = EnemyType
    all_w = waves.all_waves()
    check(len(all_w) == 100, "100 waves")
    for i, w in enumerate(all_w):
        check(w.number == i + 1, "wave numbering %d" % (i + 1))
        check(w.groups and w.total_spawns() > 0, "wave %d has spawns" % w.number)
        for gr in w.groups:
            check(gr.count > 0 and gr.interval >= 0 and gr.start_delay >= 0, "wave %d group sane" % w.number)
    check(len(all_w[0].groups) == 1 and all_w[0].groups[0].type is E.PRIMITIVE_VARIABLE, "wave 1 primitives only")
    check(all_w[19].contains(E.BUBBLE_SORT), "wave 20 Bubble Sort")
    check(not any(gr.type.ordinal >= E.BUBBLE_SORT.ordinal for i in range(19) for gr in all_w[i].groups), "no sorters before wave 20")
    check(all_w[39].count_of(E.BELLARMINE_COLLEGE_PREP) == 1, "wave 40 first MOAB")
    check(not any(all_w[i].contains_boss() for i in range(39)), "no boss before wave 40")
    check(all_w[59].count_of(E.SW_RESOURCE_CONSULTANT) == 1, "wave 60 BFB")
    check(all_w[79].count_of(E.THREE_COM) == 1, "wave 80 ZOMG")
    check(all_w[89].contains(E.LOCKHEED_MARTIN), "wave 90 DDT")
    check(not any(all_w[i].contains(E.LOCKHEED_MARTIN) for i in range(89)), "no DDT before 90")
    check(all_w[99].count_of(E.PALANTIR) == 1, "wave 100 Palantir")
    for i in range(99):
        check(not all_w[i].contains(E.PALANTIR), "no Palantir before 100")
    camo = any(Modifier.CAMO in gr.modifiers for i in range(20, 39) for gr in all_w[i].groups)
    fort = any(Modifier.FORTIFIED in gr.modifiers for i in range(20, 39) for gr in all_w[i].groups)
    check(camo and fort, "camo & fortified introduced in 21-39")
    for i in range(90, 99):
        check(len(all_w[i].groups) >= 2, "wave %d fully specified" % (i + 1))
    for t in EnemyType:
        if not t.is_spawnable_species():
            continue
        check(any(w.contains(t) for w in all_w), "%s appears in the campaign" % t)


def test_wave_spawning_matches_data(check):
    for wave in range(1, 101):
        g = new_game(wave % maps.MAP_COUNT)
        g.set_global_enemy_speed_multiplier(0)
        wm = g.get_wave_manager()
        for _ in range(1, wave):
            wm.start_next_wave()
            wm.end_wave()
        check(g.start_next_wave(), "start wave %d" % wave)
        d = wm.get_current_def()
        check(d.number == wave, "current def is wave %d" % wave)
        n_ticks = int((d.duration() + 1.0) / DT)
        em = g.get_enemy_manager()
        for _ in range(n_ticks):
            wm.update(DT)
            em.update(0)
        check(wm.get_remaining_to_spawn() == 0, "wave %d fully spawned" % wave)
        check(em.get_total_spawned() == d.total_spawns(), "wave %d spawned %d got %d" % (wave, d.total_spawns(), em.get_total_spawned()))
        for gr in d.groups:
            n = sum(1 for e in em.get_enemies() if e.get_type() is gr.type and _same_mods(e, gr))
            expected = sum(o.count for o in d.groups if o.type is gr.type and set(o.modifiers) == set(gr.modifiers))
            check(n == expected, "wave %d %s %s count %d got %d" % (wave, gr.type, gr.modifier_label(), expected, n))
        for e in em.get_enemies():
            check(abs(e.get_hp_scale() - waves.hp_scale(wave)) < 1e-9, "wave %d hp scale" % wave)
        if wave == 100:
            check(any(e.get_type() is EnemyType.PALANTIR for e in em.get_enemies()), "Palantir spawned on wave 100")
        check(wm.is_wave_active(), "wave stays active while enemies alive")
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    g.start_next_wave()
    g.run(int(waves.get(1).duration() / DT) + 10)
    check(not g.start_next_wave(), "cannot start wave 2 while wave 1 active")
    for e in list(g.get_enemy_manager().get_enemies()):
        g.get_combat().apply_hit_simple(e, HitSpec(1e9, DamageType.TRUE), None, 1, 0)
    cash = g.get_cash()
    g.run(5)
    check(not g.get_wave_manager().is_wave_active(), "wave 1 complete after kills")
    check(g.get_cash() >= cash + waves.wave_bonus(1), "wave bonus paid")
    check(g.get_last_completed_wave() == 1, "last completed = 1")
    g.run(600)
    check(g.get_wave() == 1, "next wave not auto-started")
    check(g.start_next_wave() and g.get_wave() == 2, "wave 2 starts on request")


def test_palantir_phases_and_surveillance(check):
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    r = g.get_map().get_routes()[0]
    base = r.position_at(500).add(Vec(0, -80))
    cheap = force_place(g, TowerType.QWEN, buildable_near(g, base, 100), 0)
    strong = force_place(g, TowerType.DEEPSEEK, buildable_near(g, base.add(Vec(80, 0)), 100), 3)
    strong2 = force_place(g, TowerType.COHERE, buildable_near(g, base.add(Vec(160, 0)), 100), 3)
    pal = spawn_at(g, EnemyType.PALANTIR, None, 0, 500)
    g.get_enemy_manager().update(0)
    check(pal.get_phase() == 0 and pal.get_phase_count() == 3, "Palantir starts phase 1 of 3")
    check(abs(pal.effective_armor() - 0.60) < 1e-9, "phase 1 armour 60%")
    check(pal.is_control_immune(), "phase 1 control immune")
    pal.apply_status(StatusKind.SLOW, 0.5, 5)
    stun_hit = HitSpec(0, DamageType.TRUE)
    stun_hit.boss_stun_duration = 2
    stun_hit.slow_fraction = 0.5
    stun_hit.slow_duration = 2
    cb = g.get_combat()
    cb.apply_hit_simple(pal, stun_hit, None, 1, 0)
    check(not pal.is_stunned(), "phase 1 ignores stuns")
    cb.apply_hit_simple(pal, HitSpec(pal.get_max_hp() * 0.31, DamageType.TRUE), None, 1, 0)
    g.run(1)
    check(pal.get_phase() == 1, "phase 2 at <70%")
    check(abs(pal.effective_armor() - 0.35) < 1e-9, "phase 2 armour 35%")
    before = len(g.get_enemy_manager().get_enemies())
    cb.apply_hit_simple(pal, HitSpec(pal.get_max_hp() * 0.35, DamageType.TRUE), None, 1, 0)
    g.run(1)
    check(pal.get_phase() == 2, "phase 3 at <35%")
    check(abs(pal.effective_armor() - 0.10) < 1e-9, "phase 3 armour 10%")
    check(g.get_enemy_manager().count_of_type(EnemyType.LOCKHEED_MARTIN) == 2
          and len(g.get_enemy_manager().get_enemies()) == before + 2, "phase 3 launches 2 Lockheed escorts")
    pal.begin_surveillance(g)
    check(pal.is_telegraphing(), "telegraph active")
    check(len(pal.get_marked_towers()) == 3, "phase 3 marks 3 available towers")
    check(strong in pal.get_marked_towers() and strong2 in pal.get_marked_towers(), "marks strongest")
    rate_before = strong.effective_rate(g)
    range_before = strong.effective_range(g)
    g.run(ticks(Boss.TELEGRAPH_TIME) + 2)
    check(not pal.is_telegraphing(), "telegraph ended")
    check(strong.is_surveilled() and strong2.is_surveilled() and cheap.is_surveilled(), "towers surveilled after telegraph")
    check(strong.effective_rate(g) < rate_before * 0.51 and strong.effective_range(g) < range_before * 0.71, "surveillance halves rate, cuts range")
    check(not strong.is_ability_ready(), "ability locked while surveilled")
    g.run(ticks(Boss.SURVEIL_DURATION) + 2)
    check(not strong.is_surveilled(), "surveillance expires")
    check(abs(strong.effective_rate(g) - rate_before) < 1e-9, "rate restored")
    perp = force_place(g, TowerType.PERPLEXITY, buildable_near(g, base.add(Vec(80, 60)), 100), 2)
    g.get_tower_manager().recompute_auras()
    check(strong.is_surveillance_immune(), "DeepSeek immune inside Perplexity U2 radius")
    pal.begin_surveillance(g)
    g.run(ticks(Boss.TELEGRAPH_TIME) + 2)
    check(not strong.is_surveilled(), "immune tower not surveilled")
    g.sell_tower(perp)
    g.get_tower_manager().recompute_auras()
    pal.begin_surveillance(g)
    g.run(ticks(Boss.TELEGRAPH_TIME) + 2)
    check(strong.is_surveilled() and cheap.is_surveilled(), "surveilled again without the Perplexity radius")
    check(g.upgrade_tower(cheap) and not cheap.is_surveilled(), "upgrading clears Surveillance")
    g2 = new_game(0)
    g2.set_global_enemy_speed_multiplier(0)
    t2 = force_place(g2, TowerType.GPT, buildable_near(g2, base, 100), 0)
    p2 = spawn_at(g2, EnemyType.PALANTIR, None, 0, 500)
    g2.run(ticks(31))
    check(t2 in p2.get_marked_towers() or t2.is_surveilled(), "surveillance fires periodically")


def test_ability_cooldowns(check):
    g = new_game(0)
    p = buildable_near(g, Vec(400, 250), 200)
    st = force_place(g, TowerType.ZETHOS, p, catalog.ZETHOS_UPGRADES)
    check(not st.is_ability_ready() and not g.activate_ability(st), "a maxed Zethos's ability is locked until bought")
    g.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(st) and st.is_ability_ready(), "the bought ability is ready at once")
    check(g.activate_ability(st), "ability activates")
    check(not st.is_ability_ready(), "not ready after use")
    check(abs(st.get_ability_cooldown_remaining() - 55) < 1e-9, "cooldown 55 s")
    check(not g.activate_ability(st), "cannot activate during cooldown")
    check(abs(st.self_rate_mult() - 2.0) < 1e-9, "self buff applied (x2 rate)")
    run_seconds(g, 6.1)
    check(st.self_rate_mult() == 1.0, "buff expired after 6 s")
    run_seconds(g, 49)
    check(st.is_ability_ready(), "ready again after cooldown")
    fast = new_game(0)
    ft = force_place(fast, TowerType.ZETHOS, p, catalog.ZETHOS_UPGRADES)
    fast.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(fast.unlock_ability(ft) and fast.activate_ability(ft), "fast-forward test: ability unlocked and used")
    fast.set_speed(3)
    for _ in range(60 * 19):
        fast.advance(1.0 / 60)
    check(ft.is_ability_ready(), "ability cooldown speeds up with fast-forward")
    i = 0
    for type_ in TowerType.purchasable():
        gg = new_game(0)
        gg.set_global_enemy_speed_multiplier(0)
        r = gg.get_map().get_routes()[0]
        q = buildable_near(gg, r.position_at(500).add(Vec(0, -70)), 120)
        t = force_place(gg, type_, q, len(catalog.get(type_).upgrades))
        if t.is_ability_locked():
            check(not gg.activate_ability(t), "%s locked ability cannot activate" % type_)
            gg.add_cash(catalog.ABILITY_UNLOCK_COST, None)
            check(gg.unlock_ability(t) and t.is_ability_ready(), "%s unlocks its ability at max tier" % type_)
        if t.get_ability() is None:
            check(not gg.activate_ability(t), "%s has no ability to activate" % type_)
            continue
        spawn_at(gg, EnemyType.HEAP_SORT, None, 0, 500)
        spawn_at(gg, EnemyType.MERGE_SORT, mods(Modifier.FORTIFIED), 0, 510)
        t.reset_ability_cooldown()
        if t.get_ability().needs_target:
            check(not gg.activate_ability(t) and t.is_ability_ready(), "%s targeted ability refuses activation without a point" % type_)
        ok = gg.activate_ability(t, r.position_at(500)) if t.get_ability().needs_target else gg.activate_ability(t)
        check(ok, "%s ability activates" % type_)
        check(not t.is_ability_ready() and t.get_ability_cooldown_remaining() > 0, "%s ability on cooldown" % type_)
        gg.run(60)
        i += 1
    check(i == len(TowerType.shop_towers()), "every shop tower's ability tested, got %d" % i)


def test_maps_traversable(check):
    for m in range(maps.MAP_COUNT):
        gmap = maps.create(m)
        check(gmap.get_routes(), "%s has routes" % gmap.get_name())
        for ri, r in enumerate(gmap.get_routes()):
            check(r.get_total_length() > 500, "%s route %d length" % (gmap.get_name(), ri))
            for w in r.get_waypoints():
                check(-1 <= w.x <= WIDTH + 1 and -1 <= w.y <= HEIGHT + 1, "%s waypoint in bounds %r" % (gmap.get_name(), w))
            g = Game(maps.create(m), 7)
            e = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, ri, 0)
            last = -1.0
            n = 0
            monotonic = True
            while e.is_alive() and n < 20000:
                g.step(DT)
                if e.is_alive() and e.get_distance() < last - 1e-6:
                    monotonic = False
                last = e.get_distance()
                n += 1
            check(e.has_leaked(), "%s route %d reaches exit (%d ticks)" % (gmap.get_name(), ri, n))
            check(monotonic, "%s route %d monotonic progress" % (gmap.get_name(), ri))
            check(g.get_lives() == 100 - EnemyType.BELLARMINE_COLLEGE_PREP.lives, "%s leak costs lives" % gmap.get_name())
        buildable = sum(1 for x in range(20, WIDTH, 20) for y in range(20, HEIGHT, 20) if gmap.is_buildable(Vec(x, y), 20))
        check(buildable > 200, "%s has buildable area (%d cells)" % (gmap.get_name(), buildable))
    mono = maps.create(1)
    check(not mono.has_line_of_sight(Vec(400, 150), Vec(400, 290)), "chassis blocks LOS")
    check(mono.has_line_of_sight(Vec(150, 150), Vec(150, 290)), "clear LOS beside chassis")


def test_new_maps(check):
    for m in range(4, maps.MAP_COUNT):
        gmap = maps.create(m)
        for r in gmap.get_routes():
            d = 0.0
            while d <= r.get_total_length():
                p = r.position_at(d)
                for o in gmap.get_obstacles():
                    check(not o.contains(p, TRACK_HALF_WIDTH + 2), "%s: %s clear of the track at %r" % (gmap.get_name(), o.label, p))
                d += 5
    nn = maps.create(5)
    check(len(nn.get_routes()) == 6, "neural network has six routes")
    for r in nn.get_routes():
        s0 = r.get_start()
        check(s0.dist(NeuralNetwork.IN_A) < 1 or s0.dist(NeuralNetwork.IN_B) < 1, "%s starts at an input" % r.get_name())
        check(r.get_end().dist(NeuralNetwork.EXIT) < 1, "%s ends at the exit" % r.get_name())
        check(r.distance_to_point(NeuralNetwork.OUT) < 20, "%s passes through the output neuron" % r.get_name())
    g = new_game(6)
    dc = g.get_map()
    g.set_global_enemy_speed_multiplier(0)
    n = 0
    warned = False
    while dc.get_active_hazard() < 0 and n < 2000:
        g.step(DT)
        n += 1
        if dc.get_warned_hazard() >= 0:
            warned = True
    check(warned, "a hazard warns before it activates")
    a = dc.get_active_hazard()
    check(a >= 0 and abs(n * DT - AbandonedDataCenter.HAZARD_INTERVAL) < 0.2, "a hazard activates after the interval")
    h = dc.get_hazards()[a]
    inside = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, (h.frm + h.to) / 2)
    out = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, h.frm - 60)
    boss = spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, (h.frm + h.to) / 2)
    slow = AbandonedDataCenter.HAZARD_SLOW
    check(abs(dc.enemy_speed_multiplier(inside) - (1 - slow)) < 1e-9, "enemies in the active section are slowed")
    check(dc.enemy_speed_multiplier(out) == 1.0, "enemies outside the section are not slowed")
    check(abs(dc.enemy_speed_multiplier(boss) - (1 - slow / 3)) < 1e-9, "bosses take a third of the hazard slow")
    check(dc.get_event_text() is not None, "an active hazard shows a banner")
    g.run(ticks(AbandonedDataCenter.HAZARD_DURATION) + 2)
    check(dc.get_active_hazard() < 0 and dc.enemy_speed_multiplier(inside) == 1.0, "the hazard switches off")
    prev, repeats = a, 0
    for _ in range(12):
        guard = 0
        while dc.get_active_hazard() < 0 and guard < 2000:
            guard += 1
            g.step(DT)
        now = dc.get_active_hazard()
        if now == prev:
            repeats += 1
        prev = now
        while dc.get_active_hazard() >= 0 and guard < 4000:
            guard += 1
            g.step(DT)
    check(repeats == 0, "the same hazard never fires twice in a row")


def test_admin_mode(check):
    check(AdminMode.matches("lindeveloper"), "admin code accepted")
    check(AdminMode.matches("  LinDeveloper "), "admin code ignores case and spaces")
    check(not AdminMode.matches("lindeveloper1") and not AdminMode.matches("austin") and not AdminMode.matches("")
          and not AdminMode.matches(None), "wrong codes rejected")
    check(len(list(AdminMode.Option)) == 3, "the checklist offers three cheats")
    normal = new_game(0)
    check(not normal.is_admin() and not normal.is_hero_unlocked(TowerType.CHILLSTIN), "games start with no cheats")
    check(not normal.has_admin_heroes() and not normal.has_admin_money() and not normal.has_admin_health(), "no cheat on by default")
    heroes_only = new_game(0)
    heroes_only.set_admin(True, False, False)
    for h in TowerType.heroes():
        check(heroes_only.is_hero_unlocked(h), "unlock-all opens %s" % h.display_name)
    check(not heroes_only.get_hero_collection().unlocked(), "unlock-all never touches the saved collection")
    check(heroes_only.get_cash() == Game.START_CASH, "unlock-all does not hand out money")
    money_only = new_game(0)
    money_only.set_admin(False, True, False)
    before = money_only.get_cash()
    check(before >= Game.ADMIN_CASH, "infinite money tops credits up")
    check(not money_only.is_hero_unlocked(TowerType.CHILLSTIN), "infinite money alone does not unlock heroes")
    placed = maxed = 0
    for type_ in TowerType.shop_towers():
        t = money_only.place_tower(type_, buildable_near(money_only, Vec(150 + (placed % 8) * 120, 300 + (placed // 8) * 180), 260))
        if t is None:
            continue
        placed += 1
        while money_only.upgrade_tower(t):
            pass
        if not t.can_upgrade():
            maxed += 1
    check(placed >= 10 and maxed == placed, "infinite money buys and fully upgrades every tower (%d/%d)" % (maxed, placed))
    check(money_only.get_cash() == before, "spending never lowers the credits")
    health_only = new_game(0)
    health_only.set_admin(False, False, True)
    for _ in range(Game.START_LIVES + 50):
        e = health_only.get_enemy_manager().spawn_scaled(EnemyType.PRIMITIVE_VARIABLE, None, 0, 0, 1, 1.0)
        health_only.get_enemy_manager().update(0)
        health_only.lose_lives(1, e)
        e.mark_dead()
    check(health_only.get_lives() >= 1 and health_only.get_state() is State.PLAYING, "infinite health never loses the run")
    mortal = new_game(0)
    for _ in range(Game.START_LIVES + 5):
        e = mortal.get_enemy_manager().spawn_scaled(EnemyType.PRIMITIVE_VARIABLE, None, 0, 0, 1, 1.0)
        mortal.get_enemy_manager().update(0)
        mortal.lose_lives(1, e)
        e.mark_dead()
    check(mortal.get_lives() == 0, "without the cheat the same leaks empty the integrity bar")
    all_on = new_game(0)
    all_on.set_admin(True, True, True)
    check(all_on.is_admin() and all_on.has_admin_heroes() and all_on.has_admin_money() and all_on.has_admin_health(), "all three at once")
    restarted = Game.fresh_copy(all_on)
    check(restarted.has_admin_heroes() and restarted.has_admin_money() and restarted.has_admin_health(), "RESTART keeps the checklist")


def test_map_mechanics(check):
    g = new_game(3)
    sc = g.get_map()
    far = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 0)
    near = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 1, g.get_map().get_routes()[1].get_total_length() - 100)
    check(sc.enemy_speed_multiplier(near) > sc.enemy_speed_multiplier(far), "gravity speeds up enemies near core")
    g.set_global_enemy_speed_multiplier(0)
    t = force_place(g, TowerType.ZETHOS, buildable_near(g, Vec(600, 200), 200), catalog.ZETHOS_UPGRADES)
    g.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(t), "Zethos's ability unlocked for the collapse test")
    g.activate_ability(t)
    check(not t.is_ability_ready(), "cooldown started")
    sc.trigger_collapse(g)
    check(t.is_ability_ready(), "collapse resets cooldowns")
    g2 = new_game(2)
    hc = g2.get_map()
    drifted = 0
    for i in range(200):
        gg = Game(maps.create(2), i)
        m = gg.get_map()
        r0 = m.get_routes()[0]
        center_d = r0.nearest_distance_along(m.get_center())
        e = spawn_at(gg, EnemyType.PRIMITIVE_VARIABLE, None, 0, center_d - 25)
        gg.run(60)
        if e.get_route() is not r0 or abs(e.get_distance() - (center_d - 25 + Enemy.BASE_SPEED)) > 30:
            drifted += 1
    check(25 < drifted < 80, "attention drift ~25%% (%d/200)" % drifted)
    g2.set_global_enemy_speed_multiplier(0)
    gpt = force_place(g2, TowerType.GPT, buildable_near(g2, Vec(300, 600), 200), 0)
    g2.run(ticks(HallucinationCanyon.STORM_INTERVAL) + 5)
    check(hc.is_storm_active(), "noise storm started")
    check(abs(gpt.effective_range(g2) - gpt.get_stats().range * 0.5) < 1e-6, "storm halves range")
    force_place(g2, TowerType.COPILOT, buildable_near(g2, gpt.get_position().add(Vec(60, 0)), 100), 0)
    check(abs(gpt.effective_range(g2) - gpt.get_stats().range) < 1e-6, "Logic Specialist counters storm")
    try:
        preview = hc.tower_range_multiplier(g2, None)
        ok = True
    except Exception:
        preview, ok = -1, False
    check(ok and abs(preview - 0.5) < 1e-9, "storm range preview accepts a null tower")
    for m in range(maps.MAP_COUNT):
        gm = new_game(m)
        try:
            gm.get_map().tower_range_multiplier(gm, None)
            ok = True
        except Exception:
            ok = False
        check(ok, "map %d range preview accepts a null tower" % m)
    g3 = new_game(1)
    lm = g3.get_map()
    for _ in range(1, 10):
        g3.get_wave_manager().start_next_wave()
        g3.get_wave_manager().end_wave()
        g3.get_enemy_manager().clear()
    g3.start_next_wave()
    check(lm.get_vented_floor() >= 0, "wave 10 vents a floor")
    g4 = new_game(0)
    g4.set_global_enemy_speed_multiplier(0)
    e4a = spawn_at(g4, EnemyType.HEAP_SORT, None, 0, 300)
    e4b = spawn_at(g4, EnemyType.HEAP_SORT, None, 1, 300)
    g4.run(ticks(SiliconCircuit.SHORT_INTERVAL) + 5)
    check((e4a.get_hp() < 8) != (e4b.get_hp() < 8), "short circuit zapped exactly one lane")


def test_win_and_lose(check):
    g = new_game(0)
    ln = g.get_map().get_routes()[0].get_total_length()
    for _ in range(4):
        spawn_at(g, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, ln - 3)
    g.run(300)
    check(g.get_lives() == 0, "lives hit zero")
    check(g.get_state() is State.DEFEAT, "state DEFEAT, got %s" % g.get_state())
    check(not g.start_next_wave(), "cannot start wave after defeat")
    g2 = new_game(0)
    g2.set_global_enemy_speed_multiplier(0)
    for _ in range(1, 100):
        g2.get_wave_manager().start_next_wave()
        g2.get_wave_manager().end_wave()
    g2.start_next_wave()
    check(g2.get_wave() == 100, "on wave 100")
    g2.run(ticks(9))
    pal = g2.get_palantir()
    check(pal is not None and pal.is_alive(), "Palantir present on wave 100")
    kill_outright(g2, pal)
    check(g2.is_victory_sequence_active(), "victory sequence running")
    check(g2.get_state() is State.PLAYING, "still PLAYING during sequence")
    g2.run(ticks(Game.VICTORY_SEQUENCE_TIME) + 5)
    check(g2.get_state() is State.VICTORY, "state VICTORY, got %s" % g2.get_state())


@pytest.mark.slow
def test_stress_late_waves(check):
    overall = 0
    types = [TowerType.KAIJU_KAI, TowerType.DEEPSEEK, TowerType.COHERE, TowerType.GEMINI, TowerType.SORA, TowerType.SUNO,
             TowerType.GLM, TowerType.PERPLEXITY, TowerType.MINIMAX, TowerType.MISTRAL, TowerType.QWEN, TowerType.KIMI,
             TowerType.GPT, TowerType.CLAUDE, TowerType.LLAMA, TowerType.DALLE, TowerType.GROK, TowerType.COPILOT,
             TowerType.ZETHOS, TowerType.BLITZ_ARNAV, TowerType.CHILLSTIN, TowerType.BOOM_SAM, TowerType.SUNNY_JOE,
             TowerType.NIK_SCOPE, TowerType.LOBBER_LUIS, TowerType.SAGE_AARAV, TowerType.IRON_IMRAAN, TowerType.ABHI_ACE,
             TowerType.ZIPPY_MATT, TowerType.CAMI_MINE, TowerType.JUSTIN_TIME, TowerType.SPEAR_HANBO, TowerType.THORN_TUHIN,
             TowerType.TRAPPER_CHE, TowerType.TANIMBUS]
    for m in range(maps.MAP_COUNT):
        g = new_game(m)
        g.set_invincible(True)
        g.set_global_enemy_speed_multiplier(0.35)
        g.add_cash(500_000, None)
        for h in TowerType.heroes():
            g.get_hero_collection().unlock(h)
        placed = 0
        for r in g.get_map().get_routes():
            d = 100.0
            while d < r.get_total_length() and placed < 14:
                base = r.position_at(d)
                for side in (-1, 1):
                    direction = r.direction_at(d)
                    p = base.add(Vec(-direction.y, direction.x).scale(side * 70))
                    tt = types[placed % len(types)]
                    if g.get_tower_manager().can_place(tt, p):
                        t = g.place_tower(tt, p)
                        g.upgrade_tower(t)
                        placed += 1
                d += 220
        check(placed >= 8, "%s placed defence (%d)" % (g.get_map().get_name(), placed))
        for _ in range(1, 97):
            g.get_wave_manager().start_next_wave()
            g.get_wave_manager().end_wave()
        max_enemies = 0
        for wave in range(97, 101):
            g.get_wave_manager().end_wave()
            g.get_enemy_manager().clear()
            check(g.start_next_wave(), "start wave %d on %s" % (wave, g.get_map().get_name()))
            n = 0
            while g.get_wave_manager().is_wave_active() and n < 60 * 150 and g.get_state() is State.PLAYING:
                g.step(DT)
                if n % 120 == 0:
                    for t in list(g.get_tower_manager().get_towers()):
                        if t.is_ability_ready():
                            g.activate_ability(t)
                max_enemies = max(max_enemies, len(g.get_enemy_manager().get_enemies()))
                g.get_events().clear()
                n += 1
            if g.get_state() is not State.PLAYING:
                break
        overall = max(overall, max_enemies)
        check(g.get_state() in (State.PLAYING, State.VICTORY), "stress game ran to the end")
    check(overall > 50, "stress produced a real rush (peak %d)" % overall)


@pytest.mark.slow
def test_stress_maxed_roster(check):
    for m in range(maps.MAP_COUNT):
        g = new_game(m)
        g.set_hero_limit(2147483647)
        g.set_invincible(True)
        g.set_global_enemy_speed_multiplier(0.35)
        g.add_cash(5_000_000, None)
        for h in TowerType.heroes():
            g.get_hero_collection().unlock(h)
        placed = 0
        roster = TowerType.purchasable()
        done = False
        for r in g.get_map().get_routes():
            d = 80.0
            while d < r.get_total_length() and not done:
                direction = r.direction_at(d)
                for side in (-1, 1):
                    p = r.position_at(d).add(Vec(-direction.y, direction.x).scale(side * 75))
                    if placed >= len(roster):
                        done = True
                        break
                    if g.get_tower_manager().can_place(roster[placed], p):
                        t = g.place_tower(roster[placed], p)
                        while g.upgrade_tower(t):
                            pass
                        placed += 1
                d += 60
            if done:
                break
        check(placed == len(roster), "%s fits the whole roster (%d)" % (g.get_map().get_name(), placed))
        for _ in range(1, 94):
            g.get_wave_manager().start_next_wave()
            g.get_wave_manager().end_wave()
        peak_drones = peak_walkers = 0
        for wave in range(94, 101):
            g.get_wave_manager().end_wave()
            g.get_enemy_manager().clear()
            check(g.start_next_wave(), "start wave %d" % wave)
            n = 0
            while g.get_wave_manager().is_wave_active() and n < 60 * 120 and g.get_state() is State.PLAYING:
                g.step(DT)
                if n % 60 == 0:
                    for t in list(g.get_tower_manager().get_towers()):
                        if not t.is_ability_ready():
                            continue
                        if t.get_ability().needs_target:
                            g.activate_ability(t, g.get_map().get_routes()[0].position_at(400))
                        else:
                            g.activate_ability(t)
                peak_drones = max(peak_drones, len(g.get_effects().get_drones()))
                peak_walkers = max(peak_walkers, len(g.get_effects().get_walkers()))
                g.get_events().clear()
                n += 1
            if g.get_state() is not State.PLAYING:
                break
        check(g.get_state() in (State.PLAYING, State.VICTORY), "maxed roster stress ended in a sane state")
        check(peak_drones > 0 and peak_walkers > 0, "%s primitives were exercised" % g.get_map().get_name())


def test_restart_resets_level(check):
    for m in range(maps.MAP_COUNT):
        for d in Difficulty:
            g = Game(maps.create(m), 7, d)
            g.add_cash(4000, None)
            g.place_tower(TowerType.GPT, buildable_near(g, Vec(400, 250), 300))
            g.start_next_wave()
            g.run(600)
            em = g.get_enemy_manager()
            g.lose_lives(3, em.spawn(EnemyType.STATIC_ARRAY, None, 0, 10) if not em.get_enemies() else em.get_enemies()[0])
            f = Game.fresh_copy(g)
            tag = " (map %d, %s)" % (m, d)
            check(f is not g and f.get_map() is not g.get_map(), "fresh game has its own map instance" + tag)
            check(f.get_map().get_name() == g.get_map().get_name() and f.get_difficulty() is g.get_difficulty(), "same map and difficulty" + tag)
            check(f.get_wave() == 0 and f.get_last_completed_wave() == 0 and f.get_tick() == 0, "wave and clock reset" + tag)
            check(f.get_cash() == d.start_cash(Game.START_CASH) and f.get_lives() == d.start_lives(Game.START_LIVES), "cash and lives reset" + tag)
            check(not f.get_tower_manager().get_towers() and not f.get_enemy_manager().get_enemies()
                  and f.get_state() is State.PLAYING and not f.is_paused(), "nothing carried over" + tag)
