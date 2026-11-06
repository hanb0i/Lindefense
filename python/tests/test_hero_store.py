"""Hero Store, the 18 heroes and Zethos: prices, purchasing, persistence, upgrades, every hero's own mechanic."""
import math

from kit import DT, buildable_near, hit_for, mods, new_game, run_seconds, tower_near_track
from lindefense.combat.hit_spec import DamageType
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.map import maps
from lindefense.sim.game import Game
from lindefense.sim.misc import HeroCollection
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.behavior.heroes import HOLE, KaijuKaiBehavior, MrLindemannBehavior, TanimbusBehavior
from lindefense.tower.behavior.primary import ZethosBehavior
from lindefense.tower.manager import MAX_HEROES_PER_GAME
from lindefense.tower.stats import u
from lindefense.tower.tower_type import AttackKind, BuffStat, Faction, Targeting, TowerType

T = TowerType
ROSTER = [(T.LOBBER_LUIS, 1250, 400, 850, 1500), (T.SAGE_AARAV, 1400, 450, 900, 1600), (T.IRON_IMRAAN, 1650, 500, 950, 1700),
          (T.BOOM_SAM, 1500, 450, 900, 1700), (T.CHILLSTIN, 1400, 400, 850, 1500), (T.KAIJU_KAI, 2000, 600, 1100, 2000),
          (T.ABHI_ACE, 1800, 500, 1000, 1800), (T.ZIPPY_MATT, 1700, 450, 900, 1600), (T.SUNNY_JOE, 1150, 400, 800, 1500),
          (T.NIK_SCOPE, 1750, 500, 1000, 1800), (T.CAMI_MINE, 1500, 450, 900, 1600), (T.JUSTIN_TIME, 1900, 500, 950, 1800),
          (T.SPEAR_HANBO, 2700, 400, 850, 1500), (T.THORN_TUHIN, 1650, 450, 900, 1700), (T.TRAPPER_CHE, 1550, 450, 900, 1600),
          (T.BLITZ_ARNAV, 1800, 500, 950, 1750), (T.TANIMBUS, 1750, 500, 950, 1700), (T.MR_LINDEMANN, 3400, 1200, 2600, 5000)]


# ------------------------------------------------------------------ helpers
def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _near(a, b):
    return abs(a - b) < 1e-6


def _tank(g, dist):
    e = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0, dist, 500, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _taken(e):
    return e.get_max_hp() - e.get_hp()


def _leak(g, n):
    i = 0
    while i < n and g.get_lives() > 1:
        e = g.get_enemy_manager().spawn_scaled(EnemyType.PRIMITIVE_VARIABLE, None, 0, 0, 1, 1.0)
        g.get_enemy_manager().update(0)
        g.lose_lives(1, e)
        e.mark_dead()
        i += 1


def _has_projectiles(g):
    g.get_combat().update_projectiles(0)
    return bool(g.get_combat().get_projectiles())


def _one_shot(check, g, t):
    check(g.get_combat().attack(t), "%s fires" % t.get_type())
    i = 0
    while i < 600 and _has_projectiles(g):
        g.get_combat().update_projectiles(DT)
        g.get_events().clear()
        i += 1


def _hero(g, t, track_dist, tier=0):
    return tower_near_track(g, t, tier, track_dist)


# ------------------------------------------------------------------ registration, store, placement
def test_registration(check):
    heroes = TowerType.heroes()
    check(len(heroes) == 18, "the Hero Store lists 18 heroes")
    seen, names = set(), set()
    for h in heroes:
        check(h not in seen, "%s registered once" % h)
        seen.add(h)
        check(h.display_name not in names, "%s unique display name" % h)
        names.add(h.display_name)
        check(h.faction is Faction.HERO, "%s is classified as a hero" % h)
        d = catalog.get(h)
        check(d is not None and d.base_cost > 0 and d.unlock_cost > 0, "%s has deploy and Hero Store prices" % h)
    for row in ROSTER:
        check(row[0] in seen, "%s is in the roster" % row[0])
    check(len(seen) == len(ROSTER), "every rostered hero is registered")
    for t in TowerType.shop_towers():
        check(not t.is_hero(), "%s is not a hero" % t)
    check(not T.ZETHOS.is_hero() and T.ZETHOS.faction is Faction.PRIMARY, "Zethos is still a Primary tower")
    check(len(TowerType.shop_towers()) == 18, "the 18 shop towers are untouched")


def test_start_locked(check):
    g = new_game(0)
    for h in TowerType.heroes():
        check(not g.is_hero_unlocked(h), "%s starts locked" % h)
        check(g.get_tower_manager().hero_problem(h) is not None, "%s cannot be placed while locked" % h)
        check(g.place_tower(h, buildable_near(g, Vec(400, 300), 200)) is None, "%s placement refused while locked" % h)


def test_exact_prices(check):
    for t, unlock, u1, u2, u3 in ROSTER:
        d = catalog.get(t)
        check(d.unlock_cost == unlock, "%s unlocks for $%d" % (t, unlock))
        check(shop.unlock_price_of(t) == unlock, "%s store price matches the catalog" % t)
        check(len(d.upgrades) == 3, "%s has exactly 3 upgrades" % t)
        for i, c in enumerate((u1, u2, u3)):
            check(d.upgrades[i].cost == c, "%s upgrade %d costs $%d" % (t, i + 1, c))


def test_purchasing(check):
    t = T.SUNNY_JOE
    price = shop.unlock_price_of(t)
    poor = new_game(0)
    poor.add_cash(price - poor.get_cash() - 1, None)
    check(not poor.purchase_hero(t), "a dollar short is refused")
    check(not poor.is_hero_unlocked(t) and poor.get_cash() == price - 1, "a refused purchase spends nothing")
    rich = new_game(0)
    rich.add_cash(price, None)
    before = rich.get_cash()
    check(rich.purchase_hero(t), "affordable hero is bought")
    check(rich.is_hero_unlocked(t), "the purchase unlocks it")
    check(_near(rich.get_cash(), before - price), "the exact price is deducted")
    check(not rich.purchase_hero(t), "buying twice is refused")
    check(rich.get_tower_manager().hero_problem(t) is None, "an unlocked hero may be deployed")
    check(not rich.get_tower_manager().get_player_towers(), "buying a hero never places it")


def test_persistence(check):
    saved = set()

    class Store:
        def load(self):
            return set(saved)

        def save(self, unlocked):
            saved.clear()
            saved.update(unlocked)

    c = HeroCollection.with_storage(Store())
    c.unlock(T.KAIJU_KAI)
    check(T.KAIJU_KAI in saved, "unlocking writes through to storage")
    reloaded = HeroCollection.with_storage(Store())
    check(reloaded.is_unlocked(T.KAIJU_KAI), "the unlock survives a reload")
    check(not reloaded.is_unlocked(T.SUNNY_JOE), "other heroes stay locked")


def test_placement_rules(check):
    g = new_game(0)
    t = T.CHILLSTIN
    g.get_hero_collection().unlock(t)
    first = g.place_tower(t, buildable_near(g, Vec(400, 300), 200))
    check(first is not None, "an unlocked hero deploys")
    check(_near(g.get_cash(), Game.START_CASH - catalog.get(t).base_cost), "deploying charges its deploy cost")
    check(g.get_tower_manager().hero_problem(t) is not None, "the same hero cannot be deployed twice")
    check(g.place_tower(t, buildable_near(g, Vec(800, 500), 200)) is None, "a second copy is refused")
    g.get_hero_collection().unlock(T.SUNNY_JOE)
    check(g.place_tower(T.SUNNY_JOE, buildable_near(g, Vec(800, 500), 200)) is not None, "a different hero still deploys")


def test_upgrade_path(check):
    for t in TowerType.heroes():
        d = catalog.get(t)
        check(len(d.upgrades) == 3 and len(d.tier_labels) == 4, "%s has 3 upgrades and 4 levels" % t)
        check(len(set(d.tier_labels)) == 4, "%s tier labels unique" % t)
        for up in d.upgrades:
            check(up.cost > 0 and up.description is not None and len(up.description) > 10, "%s upgrade '%s'" % (t, up.name))
        g = new_game(0)
        g.get_hero_collection().unlock(t)
        g.add_cash(50_000, None)
        h = g.place_tower(t, buildable_near(g, Vec(400, 300), 250))
        check(h is not None, "%s deploys" % t)
        for i in range(3):
            check(h.get_tier() == i, "%s is at tier %d" % (t, i))
            check(h.next_upgrade() is d.upgrades[i], "%s offers upgrade %d next" % (t, i + 1))
            before = g.get_cash()
            check(g.upgrade_tower(h), "%s buys upgrade %d" % (t, i + 1))
            check(_near(g.get_cash(), before - d.upgrades[i].cost), "%s upgrade %d charges its cost" % (t, i + 1))
        check(h.get_tier() == 3 and h.is_maxed() and not h.can_upgrade(), "%s reaches max tier 3" % t)
        check(h.next_upgrade() is None, "%s offers nothing beyond tier 3" % t)
        check(not g.upgrade_tower(h), "%s refuses a fourth upgrade" % t)
        after = g.get_cash()
        check(not g.upgrade_tower(h) and _near(g.get_cash(), after), "%s a refused upgrade spends nothing" % t)


def test_upgrades_change_stats(check):
    for t in TowerType.heroes():
        d = catalog.get(t)
        for i in range(1, 4):
            a, b = d.stats_for_tier(i - 1), d.stats_for_tier(i)
            changed = (b.hit.damage != a.hit.damage or b.rate != a.rate or b.range != a.range or b.pierce != a.pierce
                       or b.splash_radius != a.splash_radius or b.targets != a.targets or b.chain_hops != a.chain_hops
                       or b.hit.slow_fraction != a.hit.slow_fraction or b.hit.dot_dps != a.hit.dot_dps
                       or b.aura_range != a.aura_range or b.aura_rate != a.aura_rate or b.params() != a.params()
                       or b.kind is not a.kind or b.projectiles_per_shot != a.projectiles_per_shot)
            check(changed, "%s upgrade %d actually changes its statistics" % (t, i))
        base, mx = d.stats_for_tier(0), d.stats_for_tier(3)
        stronger = (mx.hit.damage > base.hit.damage or mx.p("income", 0.0) > base.p("income", 0.0)
                    or mx.p("healAmount", 0.0) > base.p("healAmount", 0.0) or mx.aura_rate > base.aura_rate
                    or mx.p("buffRate", 0.0) > base.p("buffRate", 0.0) or mx.p("beamDamage", 0.0) > base.p("beamDamage", 0.0))
        check(stronger, "%s is stronger at tier 3 than at base" % t)


def test_camo_and_targeting(check):
    check(catalog.get(T.NIK_SCOPE).base_stats.sees_camo, "Nik-Scope sees camo from the start")
    check(catalog.get(T.NIK_SCOPE).default_targeting is Targeting.STRONGEST, "Nik-Scope opens on Strongest")
    for t in TowerType.heroes():
        if t is not T.NIK_SCOPE:
            check(not catalog.get(t).base_stats.sees_camo, "%s has no built-in camo detection" % t)
    g = _frozen()
    h = _hero(g, T.CHILLSTIN, 500)
    camo = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, mods(Modifier.CAMO), 0, 500, 500, 1.0)
    g.get_enemy_manager().update(0)
    check(not g.get_combat().acquire_targets(h, 1), "camo is invisible to a hero without detection")
    sniper = _hero(g, T.NIK_SCOPE, 520)
    check(g.get_combat().acquire_targets(sniper, 1), "Nik-Scope sees the same camo enemy")
    check(camo.is_alive(), "the camo enemy is still alive")


# ------------------------------------------------------------------ per-hero mechanics
def test_lobber_luis(check):
    s = catalog.get(T.LOBBER_LUIS).stats_for_tier(2)
    check(s.pi("clusterBombs") == 3 and s.p("clusterDamage") == 25, "Cluster Bombs: 3 bomblets x 25 damage")
    g = _frozen()
    h = _hero(g, T.LOBBER_LUIS, 500, 2)
    for i in range(10):
        _tank(g, 460 + i * 14)
    _one_shot(check, g, h)
    run_seconds(g, 0.6)
    hurt = sum(1 for e in g.get_enemy_manager().get_enemies() if _taken(e) > 0)
    check(hurt >= 4, "the cluster spreads damage over the crowd (%d)" % hurt)
    g2 = _frozen()
    h2 = _hero(g2, T.LOBBER_LUIS, 500, 3)
    plain = orbital = -1
    for shot in range(1, 6):
        e = _tank(g2, 500)
        _one_shot(check, g2, h2)
        if shot == 1:
            plain = _taken(e)
        if shot == 5:
            orbital = _taken(e)
        e.mark_dead()
    check(orbital > plain * 1.5, "every 5th shot is an orbital strike (%s -> %s)" % (plain, orbital))


def test_sage_aarav(check):
    check(catalog.get(T.SAGE_AARAV).base_stats.kind is AttackKind.NONE, "Sage Aarav never attacks")
    g = _frozen()
    _hero(g, T.SAGE_AARAV, 500)
    _leak(g, 20)
    before = g.get_lives()
    check(before < g.get_max_lives(), "integrity was lost")
    run_seconds(g, 5.2)
    check(g.get_lives() == before + 6, "restores 6 integrity every 5 s")
    run_seconds(g, 60)
    check(g.get_lives() == g.get_max_lives(), "healing stops at the starting maximum")
    g2 = _frozen()
    _hero(g2, T.SAGE_AARAV, 500, 3)
    _leak(g2, g2.get_max_lives() - 10)
    check(g2.get_lives() == 10, "integrity down to 10")
    run_seconds(g2, 0.2)
    emergency = g2.get_lives()
    check(emergency >= 10 + int(math.ceil(g2.get_max_lives() * 0.20)), "emergency restoration pays 20%% of maximum (%d)" % emergency)
    _leak(g2, emergency - 5)
    run_seconds(g2, 0.2)
    check(g2.get_lives() <= 6, "the emergency restoration only happens once per match")


def test_iron_imraan(check):
    s = catalog.get(T.IRON_IMRAAN).base_stats
    check(s.hit.knockback > 0 and s.hit.boss_knockback == 0, "punches shove normal enemies, never bosses")
    check(_near(s.range, u(20)), "a very short 20-unit reach")
    g = _frozen()
    h = _hero(g, T.IRON_IMRAAN, 500)
    e = _tank(g, 500)
    d0 = e.get_distance()
    _one_shot(check, g, h)
    check(e.get_distance() < d0, "the enemy is knocked back down the track")
    g2 = _frozen()
    h2 = _hero(g2, T.IRON_IMRAAN, 500, 3)
    far = _tank(g2, 500 + u(18))
    for _ in range(3):
        _tank(g2, 500)
        _one_shot(check, g2, h2)
    check(_taken(far) > 0, "the shockwave reaches past the punch")


def test_boom_sam(check):
    check(catalog.get(T.BOOM_SAM).stats_for_tier(2).targets == 2, "Double Detonation throws two charges")
    g = _frozen()
    h = _hero(g, T.BOOM_SAM, 500, 1)
    outside = _tank(g, 500 - u(60))
    centre = _tank(g, 500)
    edge = _tank(g, 500 + u(10))
    _one_shot(check, g, h)
    check(_taken(centre) > 0 and _taken(edge) > 0, "the blast damages everything in its radius")
    check(_taken(outside) == 0, "enemies outside the blast are untouched")
    check(_near(_taken(centre), _taken(edge)), "splash deals full damage across the blast")
    g2 = _frozen()
    h2 = _hero(g2, T.BOOM_SAM, 500, 3)
    small = big = -1
    for shot in range(1, 6):
        e = _tank(g2, 500)
        _one_shot(check, g2, h2)
        run_seconds(g2, 0.4)
        if shot == 1:
            small = _taken(e)
        if shot == 5:
            big = _taken(e)
        e.mark_dead()
    check(big > small, "every 5th attack adds the nuclear detonation (%s -> %s)" % (small, big))


def test_chillstin(check):
    g = _frozen()
    h = _hero(g, T.CHILLSTIN, 500)
    e = _tank(g, 500)
    _one_shot(check, g, h)
    check(e.has_status(StatusKind.SLOW), "frost shards slow what they hit")
    g2 = _frozen()
    h2 = _hero(g2, T.CHILLSTIN, 500, 2)
    boss = g2.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 500, 4000, 1.0)
    g2.get_enemy_manager().update(0)
    for _ in range(8):
        _one_shot(check, g2, h2)
    check(not boss.has_status(StatusKind.FREEZE), "a boss is never frozen")
    check(boss.has_status(StatusKind.SLOW), "a boss is slowed instead")
    s3 = catalog.get(T.CHILLSTIN).stats_for_tier(3)
    check(s3.pi("burstEvery") == 6 and _near(s3.p("burstSlow"), 0.60), "Absolute Frost burst")


def test_kaiju_kai(check):
    d = catalog.get(T.KAIJU_KAI)
    check(d.base_stats.kind is AttackKind.PROJECTILE and d.base_stats.splash_radius > 0, "the base roar is a splash attack")
    check(d.stats_for_tier(1).kind is AttackKind.CUSTOM, "Atomic Breath replaces the roar with a beam")
    check(d.stats_for_tier(2).p("beamDamage") == 35, "Titan Awakening raises the beam to 35 per tick")
    g = _frozen()
    h = _hero(g, T.KAIJU_KAI, 500, 1)
    line = [_tank(g, 500 + i * 30) for i in range(4)]
    check(g.get_combat().attack(h), "the beam starts")
    check(KaijuKaiBehavior.is_beaming(h), "the beam is burning")
    run_seconds(g, 1.6)
    burned = sum(1 for e in line if _taken(e) > 0)
    check(burned >= 2, "the beam burns everything along its path (%d)" % burned)
    check(not KaijuKaiBehavior.is_beaming(h), "the beam ends after its duration")
    g2 = _frozen()
    _hero(g2, T.KAIJU_KAI, 500, 3)
    far = _tank(g2, 900)
    run_seconds(g2, 8.3)
    check(_taken(far) > 0, "Cataclysmic Kaiju detonates an atomic blast on the crowd")


def test_abhi_ace(check):
    d = catalog.get(T.ABHI_ACE)
    check(d.base_stats.ignores_los, "Abhi-Ace flies over ground blockers")
    check(d.stats_for_tier(2).targets == 3 and d.stats_for_tier(3).targets == 4, "3 then 4 missiles per attack")
    g = _frozen()
    h = _hero(g, T.ABHI_ACE, 500, 2)
    three = [_tank(g, 480 + i * 40) for i in range(3)]
    _one_shot(check, g, h)
    hurt = sum(1 for e in three if _taken(e) > 0)
    check(hurt >= 2, "Missile Barrage splits across separate targets (%d)" % hurt)
    los = Game(maps.create(1), 7)
    check(los.get_map().has_line_of_sight(Vec(150, 150), Vec(150, 290)), "the monolith map has clear lanes")
    check(not los.get_map().has_line_of_sight(Vec(400, 150), Vec(400, 290)), "and blocked ones")


def test_zippy_matt(check):
    g = _frozen()
    h = _hero(g, T.ZIPPY_MATT, 500, 1)
    cluster = [_tank(g, 490 + i * 16) for i in range(6)]
    _one_shot(check, g, h)
    damage = h.get_stats().hit.damage
    n = 0
    for e in cluster:
        d = _taken(e)
        if d > 0:
            n += 1
        check(d <= damage + 1e-6, "no enemy is struck twice by one arc")
    check(2 <= n <= 4, "Speed Surge chains to at most 4 targets (%d)" % n)
    g2 = _frozen()
    h2 = _hero(g2, T.ZIPPY_MATT, 500, 2)
    line = [_tank(g2, 490 + i * 16) for i in range(6)]
    _one_shot(check, g2, h2)
    vals = [_taken(e) for e in line if _taken(e) > 0]
    check(len(vals) >= 3, "the chain reaches several enemies (%d)" % len(vals))
    check(vals and min(vals) < max(vals), "each hop deals less than the one before")


def test_sunny_joe(check):
    check(catalog.get(T.SUNNY_JOE).base_stats.kind is AttackKind.NONE, "Sunny Joe never attacks")
    g = _frozen()
    _hero(g, T.SUNNY_JOE, 500)
    before = g.get_cash()
    run_seconds(g, 10.2)
    check(_near(g.get_cash(), before + 46), "pays $46 every 10 s (got $%s)" % (g.get_cash() - before))
    g2 = _frozen()
    _hero(g2, T.SUNNY_JOE, 500, 3)
    b2 = g2.get_cash()
    run_seconds(g2, 60.5)
    earned = g2.get_cash() - b2
    check(earned >= 6 * 150 + 300 - 1, "Financial Empire pays 150 per 10 s plus the 300 bonus (got $%s)" % earned)


def test_nik_scope(check):
    d = catalog.get(T.NIK_SCOPE)
    check(_near(d.base_stats.range, u(100)) and _near(d.stats_for_tier(3).range, u(150)), "range 100 -> 150 units")
    check(d.stats_for_tier(2).pierce == 3 and d.stats_for_tier(3).pierce == 5, "pierce 3 then 5")
    check(_near(d.stats_for_tier(2).hit.mult_vs_fortified, 1.5), "+50% against Fortified enemies")
    check(_near(d.stats_for_tier(3).p("critChance"), 0.20) and _near(d.stats_for_tier(3).p("critMult"), 2.5), "20% crits at x2.5")
    g = _frozen()
    h = _hero(g, T.NIK_SCOPE, 500, 3)
    plain = h.get_stats().hit.damage
    best = 0.0
    for _ in range(60):
        e = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0, 500, 5000, 1.0)
        g.get_enemy_manager().update(0)
        _one_shot(check, g, h)
        best = max(best, _taken(e))
        e.mark_dead()
    check(best > plain * 2, "critical hits land for more than double (%s -> %s)" % (plain, best))


def test_cami_mine(check):
    g = _frozen()
    h = _hero(g, T.CAMI_MINE, 500)
    run_seconds(g, 4.2)
    ms = g.get_effects().mines_of(h, "mine")
    check(ms, "a mine is planted on the track")
    check(len(ms) <= h.get_stats().pi("maxMines"), "never more than the maximum")
    run_seconds(g, 30)
    check(len(g.get_effects().mines_of(h, "mine")) == h.get_stats().pi("maxMines"), "the field fills up to its cap")
    m = g.get_effects().mines_of(h, "mine")[0]
    e = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0,
                                           g.get_map().get_routes()[0].nearest_distance_along(m.position), 500, 1.0)
    g.get_enemy_manager().update(0)
    run_seconds(g, 0.2)
    check(_taken(e) > 0, "the mine detonates on the enemy that steps on it")
    check(not m.is_alive(), "a mine fires once and is gone")
    check(not e.has_status(StatusKind.STUN), "a mine does not immobilise")


def test_justin_time(check):
    g = _frozen()
    h = _hero(g, T.JUSTIN_TIME, 500)
    e = _tank(g, 500)
    _one_shot(check, g, h)
    check(e.has_status(StatusKind.SLOW), "time bolts slow what they hit")
    g2 = _frozen()
    h2 = _hero(g2, T.JUSTIN_TIME, 500, 2)
    far = _tank(g2, 1400)
    check(far.get_position().dist(h2.get_position()) > h2.effective_range(g2), "the enemy is out of range")
    run_seconds(g2, 12.3)
    check(far.has_status(StatusKind.SLOW), "the Temporal Field slows the whole map")
    g3 = _frozen()
    _hero(g3, T.JUSTIN_TIME, 500, 3)
    boss = g3.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 600, 9000, 1.0)
    normal = _tank(g3, 650)
    g3.get_enemy_manager().update(0)
    run_seconds(g3, 60.3)
    check(not boss.has_status(StatusKind.FREEZE), "bosses are never frozen by Time Freeze")
    check(boss.has_status(StatusKind.SLOW), "bosses are slowed instead")
    check(normal.has_status(StatusKind.FREEZE) or not normal.is_alive(), "normal enemies freeze")


def test_spear_hanbo(check):
    g = _frozen()
    h = _hero(g, T.SPEAR_HANBO, 420)
    line = [_tank(g, 470 + i * 16) for i in range(6)]
    _one_shot(check, g, h)
    dmg = h.get_stats().hit.damage
    pierced = 0
    for e in line:
        d = _taken(e)
        if d > 0:
            pierced += 1
        check(d <= dmg + 1e-6, "one spear never hits the same enemy twice on a leg")
    check(2 <= pierced <= 4, "the spear pierces up to 4 enemies (%d)" % pierced)
    g2 = _frozen()
    h2 = _hero(g2, T.SPEAR_HANBO, 420, 2)
    back = [_tank(g2, 470 + i * 16) for i in range(6)]
    check(g2.get_combat().attack(h2), "the spear is thrown")
    run_seconds(g2, 1.6)
    max_hit = max(_taken(e) for e in back)
    single = h2.get_stats().hit.damage
    check(max_hit > single + 1e-6, "an enemy can be hit on the way out and back (%s > %s)" % (max_hit, single))
    check(max_hit <= single * 2 + 1 + 1e-6, "but no more than twice plus the mark (%s)" % max_hit)


def test_thorn_tuhin(check):
    g = _frozen()
    h = _hero(g, T.THORN_TUHIN, 500)
    e = _tank(g, 500)
    _one_shot(check, g, h)
    direct = _taken(e)
    check(direct > 0 and e.has_status(StatusKind.DOT), "thorns poison what they hit")
    run_seconds(g, 3.2)
    check(_taken(e) > direct, "the poison keeps damaging after the hit")
    g2 = _frozen()
    h2 = _hero(g2, T.THORN_TUHIN, 500, 2)
    run_seconds(g2, 8.3)
    check(g2.get_effects().zones_of(h2, "vines"), "vines grow across the track")
    run_seconds(g2, 40)
    check(len(g2.get_effects().zones_of(h2, "vines")) <= h2.get_stats().pi("maxVines"), "never more than two vine patches")


def test_trapper_che(check):
    g = _frozen()
    h = _hero(g, T.TRAPPER_CHE, 500)
    run_seconds(g, 4.2)
    traps = g.get_effects().mines_of(h, "trap")
    check(traps, "a trap is set on the track")
    t = traps[0]
    along = g.get_map().get_routes()[0].nearest_distance_along(t.position)
    e = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0, along, 600, 1.0)
    g.get_enemy_manager().update(0)
    run_seconds(g, 0.2)
    check(_taken(e) > 0, "the trap damages the enemy that triggers it")
    check(e.has_status(StatusKind.STUN), "normal enemies are held in place")
    g2 = _frozen()
    h2 = _hero(g2, T.TRAPPER_CHE, 500, 2)
    run_seconds(g2, 4.2)
    t2 = g2.get_effects().mines_of(h2, "trap")[0]
    along2 = g2.get_map().get_routes()[0].nearest_distance_along(t2.position)
    boss = g2.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, along2, 9000, 1.0)
    g2.get_enemy_manager().update(0)
    run_seconds(g2, 0.2)
    check(_taken(boss) > 0, "a boss still takes the trap's damage")
    check(not boss.has_status(StatusKind.STUN), "a boss is never immobilised")


def test_blitz_arnav(check):
    d = catalog.get(T.BLITZ_ARNAV)
    for i, b in enumerate((3, 5, 7, 10)):
        check(d.stats_for_tier(i).pi("bullets") == b, "tier %d fires %d bullets per burst" % (i, b))
    g = _frozen()
    h = _hero(g, T.BLITZ_ARNAV, 500)
    spread = [_tank(g, 470 + i * 30) for i in range(5)]
    _one_shot(check, g, h)
    hurt = sum(1 for e in spread if _taken(e) > 0)
    check(hurt >= 2, "a burst spreads across several enemies (%d)" % hurt)
    g2 = _frozen()
    h2 = _hero(g2, T.BLITZ_ARNAV, 500, 2)
    e2 = _tank(g2, 500)
    for _ in range(3):
        _one_shot(check, g2, h2)
    check(e2.has_status(StatusKind.SLOW) or not e2.is_alive(), "every 3rd burst suppresses")


def test_tanimbus(check):
    g = _frozen()
    drone = _hero(g, T.TANIMBUS, 500)
    weak = tower_near_track(g, T.GEMINI, 0, 470)
    strong = tower_near_track(g, T.GPT, 3, 530)
    g.get_tower_manager().recompute_auras()
    check(TanimbusBehavior.supported(g, drone) is strong, "the drone locks onto the strongest tower in range")
    check(strong.buff_total(BuffStat.RATE) > 0, "the supported tower really is sped up")
    check(weak.buff_total(BuffStat.RATE) == 0, "other towers are not buffed while it is locked on")
    g2 = _frozen()
    _hero(g2, T.TANIMBUS, 500, 2)
    a = tower_near_track(g2, T.GEMINI, 0, 470)
    b = tower_near_track(g2, T.GPT, 0, 530)
    g2.get_tower_manager().recompute_auras()
    check(a.buff_total(BuffStat.RATE) > 0 and b.buff_total(BuffStat.RATE) > 0, "Tactical Network buffs every tower in range")
    check(a.buff_total(BuffStat.RANGE) > 0, "and adds range")
    g3 = _frozen()
    drone3 = _hero(g3, T.TANIMBUS, 500, 3)
    far = tower_near_track(g3, T.GEMINI, 0, 1300)
    check(far.get_position().dist(drone3.get_position()) > drone3.get_stats().aura_range, "the tower is outside the support radius")
    run_seconds(g3, 45.3)
    check(far.timed_buff_remaining(T.TANIMBUS) > 0, "the rally reaches every tower on the map")
    run_seconds(g3, 8.5)
    check(far.timed_buff_remaining(T.TANIMBUS) == 0, "and expires after its duration")


# ------------------------------------------------------------------ Zethos
def test_zethos_shop(check):
    for h in TowerType.heroes():
        check(h is not T.ZETHOS, "Zethos is not in the Hero Store")
    g = new_game(0)
    p = buildable_near(g, Vec(400, 300), 150)
    check(g.get_tower_manager().hero_problem(T.ZETHOS) is None, "Zethos has no hero restrictions")
    z = g.place_tower(T.ZETHOS, p)
    check(z is not None and g.get_cash() == Game.START_CASH - 650, "Zethos bought for $650 with starting cash")
    g.add_cash(10_000, None)
    check(g.place_tower(T.ZETHOS, buildable_near(g, Vec(800, 300), 150)) is not None, "several Zethos towers may be placed")
    c0 = g.get_cash()
    check(g.upgrade_tower(z) and _near(g.get_cash(), c0 - 350), "Tier 1 costs $350")
    c1 = g.get_cash()
    refund = g.sell_tower(z)
    check(refund == int(math.floor((650 + 350) * 0.7)) and _near(g.get_cash(), c1 + refund), "sells for 70% like any tower")


def test_zethos_tiers(check):
    d = catalog.get(T.ZETHOS)
    table = [(2, 0.65, 45, 2, 0, 0, 0, 0), (3, 0.60, 46, 4, 0, 0, 0, 0), (4, 0.50, 47, 5, 7, 0.60, 0, 0),
             (6, 0.55, 48, 5, 6, 0.45, 2, 0.45), (7, 0.50, 50, 6, 6, 0.35, 2, 0.35)]
    cost = (650, 350, 650, 1200, 2500)
    check(d.base_cost == cost[0], "base $650")
    for i, row in enumerate(table):
        s = d.stats_for_tier(i)
        n = "Zethos tier %d" % i
        check(s.hit.damage == row[0] and _near(s.interval(), row[1]) and _near(s.range, u(row[2])) and s.pierce == row[3], n + " core")
        check(_near(s.splash_radius, u(row[4])) and _near(s.p("splashPct", 0.0), row[5]) and s.bounces == row[6]
              and _near(s.p("bouncePct", 0.0), row[7]), n + " splash/bounce")
        if i > 0:
            check(d.upgrades[i - 1].cost == cost[i], n + " cost")
    check(_near(d.base_stats.projectile_speed, u(55)) and d.stats_for_tier(1).projectile_speed > d.base_stats.projectile_speed, "projectile speed")
    check(d.total_cost() == 5350, "fully upgraded $5,350")


def test_zethos_no_duplicate_damage(check):
    for tier in range(2, 5):
        g = _frozen()
        z = tower_near_track(g, T.ZETHOS, tier, 500)
        stack = [_tank(g, 500) for _ in range(25)]
        _one_shot(check, g, z)
        dmg = z.get_stats().hit.damage
        mx = max(_taken(e) for e in stack)
        n = sum(1 for e in stack if _taken(e) > 0)
        check(mx <= dmg + 1e-6, "tier %d: no enemy damaged twice by one projectile" % tier)
        check(n > z.get_stats().pierce, "tier %d: splash reaches beyond the direct hits (%d)" % (tier, n))


def test_zethos_bounce_falloff(check):
    g = _frozen()
    z = tower_near_track(g, T.ZETHOS, 3, 500)
    line = [_tank(g, 300 + i * 75) for i in range(12)]
    _one_shot(check, g, z)
    full = bounce = other = 0
    for e in line:
        d = _taken(e)
        if d == 0:
            continue
        if _near(d, 6):
            full += 1
        elif _near(d, 6 * 0.45):
            bounce += 1
        else:
            other += 1
    check(bounce == 2, "Tier 3 bounces to exactly 2 more enemies at 45%% (%d)" % bounce)
    check(1 <= full <= 5, "direct hits at full damage (%d)" % full)
    check(other == 0, "no other damage values (%d)" % other)


def test_zethos_reality_collapse(check):
    g = _frozen()
    z = tower_near_track(g, T.ZETHOS, 4, 500)
    rng, rate = z.effective_range(g), z.effective_rate(g)
    check(_near(rng, u(50)), "Reality Engine range 50 units")
    check(z.is_ability_locked() and not g.activate_ability(z), "Reality Collapse is locked until bought")
    g.add_cash(catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(z), "Reality Collapse unlocks for $15,000")
    check(g.activate_ability(z), "Reality Collapse activates")
    check(_near(z.effective_range(g), u(65)) and _near(z.effective_rate(g), rate * 2), "range 50 -> 65 units, interval halved")
    _tank(g, 500)
    c = g.get_combat().new_attack_context(z, g.get_combat().acquire_targets(z, 1))
    z.get_behavior().modify_attack(g, z, c)
    check(_near(c.damage_mult, 2) and c.bounces == 8 and c.splash > 0, "x2 damage, 8 bounces, every impact explodes")
    run_seconds(g, 6.1)
    check(not ZethosBehavior.is_collapsing(z) and _near(z.effective_range(g), u(50)), "ends after 6 s")
    zd = catalog.get(T.ZETHOS).ability
    check(zd.p("damageMult") == 2 and zd.p("rateMult") == 2 and _near(zd.p("rangeBonus"), u(15)) and zd.p("bounces") == 8, "multipliers")


def test_cash_never_negative(check):
    g = new_game(0)
    for h in TowerType.heroes():
        g.purchase_hero(h)
        check(g.get_cash() >= 0, "cash stays >= 0 after trying %s" % h)
    check(g.get_cash() == Game.START_CASH, "nothing affordable bought at the start")


def test_hero_limit(check):
    check(MAX_HEROES_PER_GAME == 3, "the hero cap is 3 per game")
    g = _frozen()
    check(g.get_hero_limit() == 3, "a new match allows 3 heroes")
    first = None
    for i, h in enumerate((T.LOBBER_LUIS, T.KAIJU_KAI, T.SPEAR_HANBO)):
        t = _hero(g, h, 300 + i * 150)
        check(t is not None, "%s deploys" % h)
        if i == 0:
            first = t
    check(g.get_tower_manager().heroes_deployed_this_match() == 3, "3 heroes counted")
    g.get_hero_collection().unlock(T.MR_LINDEMANN)
    why = g.get_tower_manager().hero_problem(T.MR_LINDEMANN)
    check(why is not None and "limit" in why, "a 4th hero is refused: %s" % why)
    check(g.get_tower_manager().hero_problem(T.GPT) is None, "shop towers are not affected")
    g.sell_tower(first)
    check(g.get_tower_manager().heroes_deployed_this_match() == 3 and g.get_tower_manager().hero_problem(T.MR_LINDEMANN) is not None,
          "dismissing a hero does not free its slot")


def test_mr_lindemann(check):
    g = _frozen()
    r = g.get_map().get_routes()[0]
    ml = tower_near_track(g, T.MR_LINDEMANN, 0, 150)
    far = r.get_total_length() - 60
    grunt = g.get_enemy_manager().spawn_scaled(EnemyType.DYNAMIC_ARRAY, None, 0, far, 500, 1.0)
    boss = g.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, far - 20, 50, 1.0)
    g.get_enemy_manager().update(0)
    check(grunt.get_position().dist(ml.get_position()) > ml.effective_range(g) + 50, "warp test enemies start out of range")
    g0, b0 = grunt.get_distance(), boss.get_distance()
    run_seconds(g, 19.8)
    check(grunt.get_distance() == g0 and boss.get_distance() == b0, "no space warp before 20 s")
    run_seconds(g, 0.4)
    check(grunt.get_distance() < g0 - 30 and boss.get_distance() < b0 - 10, "the space warp sends every enemy back")
    check(MrLindemannBehavior.warp_remaining(ml) > 19, "the warp timer restarts after a warp")
    check(_near(catalog.get(T.MR_LINDEMANN).stats_for_tier(3).p("warpInterval"), 15), "Event Horizon warps every 15 s")
    g2 = _frozen()
    m2 = tower_near_track(g2, T.MR_LINDEMANN, 0, 450)
    _tank(g2, 450)
    opened = False
    for _ in range(600):
        g2.step(DT)
        opened = bool(g2.get_effects().zones_of(m2, HOLE))
        if opened:
            break
    check(opened, "a black hole shot opens a singularity on the track")
    g3 = _frozen()
    m3 = tower_near_track(g3, T.MR_LINDEMANN, 2, 450)
    victim = _tank(g3, 450)
    for _ in range(600):
        if g3.get_effects().zones_of(m3, HOLE):
            break
        g3.step(DT)
    hole = g3.get_effects().zones_of(m3, HOLE)[0]
    check(hole.contains(victim), "the singularity opened on the enemy")
    hit_for(g3, victim, victim.get_hp() - victim.get_max_hp() * 0.10, DamageType.TRUE)
    g3.step(DT)
    alive = sum(1 for e in g3.get_enemy_manager().get_enemies() if e.is_alive())
    check(not victim.is_alive() and alive == 0, "Garbage Collector deletes a weakened non-boss with no children (alive %d)" % alive)
