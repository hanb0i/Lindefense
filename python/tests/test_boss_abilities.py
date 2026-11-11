"""The enemy buff: the late-wave HP curve, the corporate bosses' signature abilities (Crest Shield, Outsourcing, Network
Hub, Afterburner) and Palantir's harder final fight (difficulty-scaled HP, longer control immunity, more Surveillance,
twin Panopticon beams, stronger holograms, escort squadrons and the Swarm Uplink), plus their visuals and texts."""
import pytest

from kit import DT, buildable_near, force_place, kill_outright, mods, new_game, run_seconds, spawn_at
from lindefense.ai.units import AttackUnit
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy import boss_abilities as BA
from lindefense.enemy.boss import Boss, PalantirProtocols as PP
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType as E, Modifier, StatusKind
from lindefense.javacompat import jround
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty as D
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui.jawt import BufferedImage
from lindefense.wave import waves

OLD_BASE_HP = {E.BELLARMINE_COLLEGE_PREP: 1500, E.SW_RESOURCE_CONSULTANT: 7500, E.THREE_COM: 8000, E.LOCKHEED_MARTIN: 1000,
               E.PALANTIR: 50000}


def _frozen(m=1):
    g = new_game(m)
    g.set_global_enemy_speed_multiplier(0)
    return g


def _true(g, e, amount):
    return g.get_combat().apply_hit_simple(e, HitSpec(amount, DamageType.TRUE), None, 1, 0)


def _texts(g):
    return [ev.text for ev in g.get_events() if ev.text]


# ---------------------------------------------------------------- the wave curve
def test_hp_curve_leaves_the_early_game_alone_and_ramps_late(check):
    for w in range(1, 21):
        check(waves.hp_scale(w) == 1.0 and waves.speed_scale(w) == 1.0, "waves 1-20 unchanged (wave %d)" % w)
    for w in range(1, 120):
        check(waves.hp_scale(w + 1) >= waves.hp_scale(w) and waves.speed_scale(w + 1) >= waves.speed_scale(w), "curves never fall (wave %d)" % w)
    old = {40: 1.0, 60: 1.0, 80: 1.1, 100: 1.3}
    for w, o in old.items():
        check(waves.hp_scale(w) > o * 1.1, "wave %d enemies are clearly beefier than before (%.2f vs %.2f)" % (w, waves.hp_scale(w), o))
    check(waves.hp_scale(100) >= 1.8, "wave 100 enemies have at least 1.8x HP (%.2f)" % waves.hp_scale(100))
    check(waves.speed_scale(60) == 1.0 and 1.0 < waves.speed_scale(80) < waves.speed_scale(100) <= 1.4, "a modest late speed ramp")
    check(waves.hp_scale(120) > waves.hp_scale(100), "the curve keeps growing past wave 100 (endless play)")
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    e = g.get_enemy_manager().spawn(E.HEAP_SORT, None, 0, 0)
    check(e.get_max_hp() == 8, "a wave-1 Heap Sort still has 8 HP")


# ---------------------------------------------------------------- boss stats
def test_bosses_are_much_tougher(check):
    for t, old in OLD_BASE_HP.items():
        check(t.base_hp > old, "%s base HP raised (%d -> %d)" % (t, old, t.base_hp))
    debut = {E.BELLARMINE_COLLEGE_PREP: 40, E.SW_RESOURCE_CONSULTANT: 60, E.THREE_COM: 80, E.LOCKHEED_MARTIN: 90}
    old_scale = {40: 1.0, 60: 1.0, 80: 1.1, 90: 1.2}
    for t, w in debut.items():
        before = OLD_BASE_HP[t] * old_scale[w]
        now = t.base_hp * waves.hp_scale(w) * (1 + (BA.CrestShield.SHIELD if t is E.BELLARMINE_COLLEGE_PREP else 0))
        check(now >= 1.5 * before, "%s at its debut wave %d: %d effective HP, was %d" % (t, w, now, before))
        check(BA.ability_class(t) is not None, "%s has a signature ability" % t)
    check(BA.ability_class(E.PALANTIR) is None and BA.create(E.QUICK_SORT) is None, "Palantir uses its protocols; plain enemies have none")
    pal_now = E.PALANTIR.base_hp * waves.hp_scale(100)
    check(pal_now >= 2 * OLD_BASE_HP[E.PALANTIR] * 1.3, "Palantir at wave 100 has at least twice its old HP (%d)" % pal_now)


# ---------------------------------------------------------------- MOAB: Crest Shield
def test_crest_shield(check):
    g = _frozen()
    b = spawn_at(g, E.BELLARMINE_COLLEGE_PREP, None, 0, 400)
    ab = b.get_ability()
    check(isinstance(ab, BA.CrestShield) and not ab.is_up() and not ab.is_used(), "a fresh MOAB has its shield in reserve")
    mx = b.get_max_hp()
    _true(g, b, mx * 0.3)
    check(abs(b.get_hp() - mx * 0.7) < 1e-6 and not ab.is_used(), "above half health damage goes to the hull")
    _true(g, b, mx * 0.3)
    shield = mx * BA.CrestShield.SHIELD
    check(abs(b.get_hp() - mx * BA.CrestShield.TRIGGER) < 1e-6, "the shield snaps up at half health (hp %s)" % b.get_hp())
    check(ab.is_up() and abs(ab.get_shield() - (shield - mx * 0.1)) < 1e-6, "the rest of the hit lands on the shield")
    hp = b.get_hp()
    pct = HitSpec(0, DamageType.TRUE)
    pct.pct_max_hp, pct.pct_cap = 0.05, 1e9
    g.get_combat().apply_hit_simple(b, pct, None, 1, 0)
    check(b.get_hp() == hp and abs(ab.get_shield() - (shield - mx * 0.15)) < 1e-6, "%-max-HP damage is soaked too")
    g.step(DT)
    texts = _texts(g)
    check("CREST SHIELD" in texts, "a floating CREST SHIELD text (%s)" % texts)
    check(g.get_banner() is not None and "CREST SHIELD" in g.get_banner(), "and a banner the first time (%s)" % g.get_banner())
    check(b.get_ability_status().startswith("CREST SHIELD"), "the dock line shows the shield (%s)" % b.get_ability_status())
    dealt = _true(g, b, ab.get_shield() + 100)
    check(not ab.is_up() and abs(b.get_hp() - (hp - 100)) < 1e-6, "a hit that breaks the shield carries over (hp %s)" % b.get_hp())
    check(abs(dealt - (mx * (BA.CrestShield.SHIELD - 0.15) + 100)) < 1e-6, "soaked damage still counts as dealt (%s)" % dealt)
    g.get_events().clear()
    g.step(DT)
    check("SHIELD BROKEN" in _texts(g) and b.get_ability_status() == "SHIELD BROKEN", "the break is shown")
    b.heal(mx)
    _true(g, b, mx * 0.8)
    check(not ab.is_up() and abs(b.get_hp() - mx * 0.2) < 1e-6, "the shield comes only once")
    b2 = spawn_at(g, E.BELLARMINE_COLLEGE_PREP, None, 0, 600)
    _true(g, b2, b2.get_max_hp() * 10)
    g.get_enemy_manager().update(0)
    check(not b2.is_alive(), "a blow bigger than hull + shield still kills")


# ---------------------------------------------------------------- BFB: Outsourcing
def test_outsourcing(check):
    O = BA.Outsourcing
    g = _frozen()
    b = spawn_at(g, E.SW_RESOURCE_CONSULTANT, mods(Modifier.CAMO, Modifier.FORTIFIED), 0, 500)
    em = g.get_enemy_manager()
    run_seconds(g, O.FIRST - 0.1)
    check(em.count_of_type(O.CONTRACTOR) == 0 and b.get_ability().get_spawned() == 0, "no contractors before %s s" % O.FIRST)
    run_seconds(g, 0.2)
    cs = [e for e in em.get_enemies() if e.get_type() is O.CONTRACTOR]
    check(len(cs) == O.COUNT, "%d contractors after %s s (%d)" % (O.COUNT, O.FIRST, len(cs)))
    for c in cs:
        check(c.is_camo() and not c.is_fortified(), "contractors inherit Camo but not Fortified")
        check(c.get_hp_scale() == b.get_hp_scale() and abs(c.get_distance() - b.get_distance()) <= O.SPACING * O.COUNT,
              "contractors have the boss's HP scale and drop on its spot")
    check("OUTSOURCED x%d" % O.COUNT in _texts(g) or b.get_ability().get_fired() == 1, "the drop is announced")
    run_seconds(g, O.INTERVAL)
    check(em.count_of_type(O.CONTRACTOR) == 2 * O.COUNT, "and again every %s s" % O.INTERVAL)
    check(b.get_ability_status().startswith("OUTSOURCING IN"), "the dock shows the countdown (%s)" % b.get_ability_status())
    cash = g.get_cash()
    c = cs[0]
    kill_outright(g, c)
    check(g.get_cash() == cash + jround(O.CONTRACTOR.reward * g.get_reward_scale()), "a contractor pays its normal bounty")
    # deterministic: two identical games drop identical contractors
    sig = []
    for _ in range(2):
        h = _frozen()
        x = spawn_at(h, E.SW_RESOURCE_CONSULTANT, None, 0, 500)
        run_seconds(h, O.FIRST + 2 * O.INTERVAL + 0.5)
        sig.append(sorted(round(e.get_distance(), 6) for e in h.get_enemy_manager().get_enemies() if e is not x))
    check(sig[0] == sig[1] and len(sig[0]) == 3 * O.COUNT, "outsourcing is deterministic")


# ---------------------------------------------------------------- ZOMG: Network Hub
def test_network_hub(check):
    H = BA.NetworkHub
    g = _frozen()
    z = spawn_at(g, E.THREE_COM, None, 0, 700)
    zp = z.get_position()
    near = far = None
    r = g.get_map().get_routes()[0]
    d = 0.0
    while d < r.get_total_length():
        p = r.position_at(d)
        if near is None and p.dist(zp) < H.RADIUS * 0.6 and abs(d - 700) > 20:
            near = d
        if far is None and p.dist(zp) > H.RADIUS * 1.5:
            far = d
        d += 10
    a = spawn_at(g, E.TIMSORT, None, 0, near)
    b = spawn_at(g, E.TIMSORT, None, 0, far)
    a.set_distance(near)
    g.step(DT)
    check(a in z.get_ability().get_linked() and b not in z.get_ability().get_linked(), "the hub links only enemies within %d px" % H.RADIUS)
    da = g.get_combat().apply_hit_simple(a, HitSpec(4, DamageType.ENERGY), None, 1, 0)
    db = g.get_combat().apply_hit_simple(b, HitSpec(4, DamageType.ENERGY), None, 1, 0)
    check(abs(da - db * 0.5) < 1e-9 and db > 0, "a linked enemy takes half damage (%s vs %s)" % (da, db))
    _true(g, z, z.get_max_hp() * 0.5)
    hp = z.get_hp()
    run_seconds(g, 2)
    gain = z.get_hp() - hp
    check(abs(gain - H.REGEN * z.get_max_hp() * 2) < z.get_max_hp() * 0.002, "3Com repairs %.1f%%/s (+%d)" % (H.REGEN * 100, gain))
    check("linked" in z.get_ability_status().lower() or "LINKED" in z.get_ability_status(), "the dock shows the links (%s)" % z.get_ability_status())
    kill_outright(g, z)
    g.step(DT)
    g.step(DT)
    db2 = g.get_combat().apply_hit_simple(a, HitSpec(4, DamageType.ENERGY), None, 1, 0)
    check(abs(db2 - db) < 1e-9, "the shield drops with the hub")


# ---------------------------------------------------------------- DDT: Afterburner
def test_afterburner(check):
    A = BA.Afterburner
    g = _frozen()
    d = spawn_at(g, E.LOCKHEED_MARTIN, None, 0, 300)
    base = d.nominal_speed()
    run_seconds(g, A.FIRST - 0.1)
    check(not d.get_ability().is_burning() and d.nominal_speed() == base, "cruising before the first burn")
    run_seconds(g, 0.2)
    check(d.get_ability().is_burning() and abs(d.nominal_speed() - base * A.BOOST) < 1e-9, "afterburner: x%s speed" % A.BOOST)
    check(d.get_ability_status() == "AFTERBURNER!", "the dock shows it (%s)" % d.get_ability_status())
    run_seconds(g, A.DURATION)
    check(not d.get_ability().is_burning() and d.nominal_speed() == base, "it burns for %s s" % A.DURATION)
    run_seconds(g, A.INTERVAL - A.DURATION)
    check(d.get_ability().is_burning() and d.get_ability().get_fired() == 2, "and lights up again every %s s" % A.INTERVAL)
    m = new_game(1)
    x = spawn_at(m, E.LOCKHEED_MARTIN, None, 0, 100)
    y = spawn_at(m, E.LOCKHEED_MARTIN, None, 0, 100)
    y._ability = None
    run_seconds(m, A.FIRST + A.DURATION + 0.1)
    check(x.get_distance() > y.get_distance() + 0.9 * (A.BOOST - 1) * A.DURATION * y.nominal_speed(), "the burn really covers ground")


def test_ability_banner_once_per_wave_and_never_over_palantir(check):
    g = _frozen()
    a = spawn_at(g, E.LOCKHEED_MARTIN, None, 0, 300)
    run_seconds(g, BA.Afterburner.FIRST + 0.1)
    check(g.get_banner() is not None and "AFTERBURNER" in g.get_banner(), "the first afterburner is bannered")
    g.set_banner("x", 0, 0.01)
    run_seconds(g, BA.Afterburner.INTERVAL)
    check(g.get_banner() is None, "the second is not")
    h = _frozen()
    spawn_at(h, E.PALANTIR, None, 0, 900)
    spawn_at(h, E.LOCKHEED_MARTIN, None, 0, 300)
    run_seconds(h, BA.Afterburner.FIRST + 0.1)
    check(h.get_banner() is None or "AFTERBURNER" not in h.get_banner(), "no ability banner over the Palantir fight")


# ---------------------------------------------------------------- Palantir
def _pal(g, d=600):
    return spawn_at(g, E.PALANTIR, None, 0, d)


def _phase_to(g, pal, f):
    pal._hp = pal.get_max_hp() * f
    g.run(1)


def test_palantir_hp_scales_with_difficulty(check):
    hp = {}
    for d in D:
        check(d.hp_multiplier(100, E.PALANTIR) == d.palantir_hp(), "%s Palantir uses its own multiplier" % d)
        hp[d] = d.palantir_hp() / d.tower_damage
    ds = list(D)
    check(D.O1.palantir_hp() == 1.0, "O(1) Palantir multiplier is 1")
    for a, b in zip(ds, ds[1:]):
        check(hp[b] > hp[a] * 1.1, "Palantir's effective HP grows with difficulty (%s %.2f -> %s %.2f)" % (a, hp[a], b, hp[b]))
        check(b.palantir_hp() <= b.hp_multiplier(100), "but never beyond the full ramp (%s)" % b)


def test_palantir_control_immunity_lasts_two_phases(check):
    g = _frozen()
    pal = _pal(g)
    check(pal.is_control_immune(), "phase 1 immune")
    _phase_to(g, pal, 0.6)
    check(pal.get_phase() == 1 and pal.is_control_immune(), "phase 2 now immune as well")
    check(not pal.apply_status(StatusKind.SLOW, 0.6, 3) and pal.apply_knockback(50, g.get_time()) == 0, "no slow or knockback in phase 2")
    _phase_to(g, pal, 0.3)
    check(pal.get_phase() == 2 and not pal.is_control_immune(), "phase 3 can be controlled")
    check(pal.apply_status(StatusKind.SLOW, 0.6, 3), "phase 3 takes slows")


def test_palantir_surveillance_is_more_aggressive(check):
    check(Boss.SURVEILLANCE_FIRST < 30 and all(a < b for a, b in zip(Boss.SURVEILLANCE_INTERVAL, (30.0, 20.0, 14.0))),
          "Surveillance comes sooner and more often")
    check(all(a > b for a, b in zip(Boss.SURVEILLANCE_TARGETS, (2, 3, 4))) and all(a > b for a, b in zip(Boss.SURVEILLANCE_SHARE, (0.10, 0.15, 0.20))),
          "and marks more towers")
    g = _frozen(0)
    base = g.get_map().get_routes()[0].position_at(500)
    ts = [force_place(g, T.GPT, buildable_near(g, base.add(Vec(-300 + 60 * i, -90 + 180 * (i % 2))), 120), 0) for i in range(10)]
    pal = _pal(g, 500)
    run_seconds(g, Boss.SURVEILLANCE_FIRST + 0.2)
    marked = len(pal.get_marked_towers())
    check(marked == max(Boss.SURVEILLANCE_TARGETS[0], -(-len(ts) * 15 // 100)), "first cast at %ss marks %d towers" % (Boss.SURVEILLANCE_FIRST, marked))


def test_palantir_escorts_and_swarm_uplink(check):
    g = _frozen()
    pal = _pal(g, 900)
    em = g.get_enemy_manager()
    _phase_to(g, pal, 0.69)
    want = {t: n for t, n, _ in PP.ESCORTS[1]}
    for t, n in want.items():
        check(em.count_of_type(t) == n, "phase 2 launches %d %s (%d)" % (n, t, em.count_of_type(t)))
    esc = list(pal.get_protocols().get_escorts())
    check(len(esc) == sum(want.values()) and all(e.is_fortified() for e in esc), "Fortified escorts are tracked")
    check(all(e.get_distance() < 2 * PP.ESCORT_SPACING * len(esc) for e in esc), "they launch from the route entrance")
    g.step(DT)
    check(not pal.get_protocols().get_uplinks(), "no uplink until they catch up")
    for i, e in enumerate(esc):
        e.set_distance(pal.get_distance() - 30 * (i + 1))   # caught up with Palantir
    g.step(DT)
    ups = pal.get_protocols().get_uplinks()
    red = pal.get_protocols().uplink_reduction()
    check(len(ups) == len(esc) and abs(red - min(PP.UPLINK_MAX, PP.UPLINK_PER * len(esc))) < 1e-9, "every escort in range uplinks (%d, -%d%%)" % (len(ups), red * 100))
    dealt = pal.take_damage(1000, g.get_time())
    check(abs(dealt - 1000 * (1 - red)) < 1e-6, "the uplink cuts Palantir's damage taken (%s)" % dealt)
    check(pal.get_ability_status().startswith("SWARM UPLINK"), "the dock shows it (%s)" % pal.get_ability_status())
    for e in esc:
        kill_outright(g, e)
    em.update(0)
    for e in list(em.get_enemies()):
        if e is not pal and not e.get_type().is_hologram():
            g.get_enemy_manager().destroy_without_children(e, None)
    g.step(DT)
    check(not pal.get_protocols().get_uplinks() and abs(pal.take_damage(1000, g.get_time()) - 1000) < 1e-6, "killing the escorts breaks the uplink")
    _phase_to(g, pal, 0.3)
    for t, n, code in PP.ESCORTS[2]:
        check(em.count_of_type(t) >= n, "phase 3 launches %d %s" % (n, t))
    check(em.count_of_type(E.LOCKHEED_MARTIN) >= 1, "a Lockheed Martin escort is still there")
    h = _frozen()
    p2 = _pal(h, 900)
    r = h.get_map().get_routes()[0]
    d = 900.0
    while r.position_at(d).dist(p2.get_position()) < PP.UPLINK_RANGE * 1.5:
        d += 20
    far = spawn_at(h, E.BELLARMINE_COLLEGE_PREP, None, 0, d)
    near = spawn_at(h, E.BELLARMINE_COLLEGE_PREP, None, 0, 860)
    h.step(DT)
    check(not p2.get_protocols().get_uplinks(), "no uplink in phase 1, nor from far away")
    _phase_to(h, p2, 0.69)
    h.step(DT)
    ups = p2.get_protocols().get_uplinks()
    check(far not in ups and near in ups, "any boss within %d px uplinks, one beyond does not" % PP.UPLINK_RANGE)


def test_palantir_twin_panopticon_and_holograms(check):
    g = _frozen()
    pal = _pal(g, 900)
    pr = pal.get_protocols()
    run_seconds(g, PP.PANOPTICON_DELAY + 0.1)
    check(len(pr.beam_angles(pal)) == 1, "one beam in phase 1")
    _phase_to(g, pal, 0.69)
    check(not pr.beam_angles(pal), "no beam in phase 2")
    holos = [e for e in g.get_enemy_manager().get_enemies() if e.get_type().is_hologram()]
    check(len(holos) == PP.DECOYS and PP.DECOYS > 2, "phase 2 projects %d holograms" % PP.DECOYS)
    check(all(abs(h.get_max_hp() - round(pal.get_max_hp() * PP.DECOY_HP_FRACTION)) <= 1 for h in holos) and PP.DECOY_HP_FRACTION > 0.02,
          "stronger holograms (%.0f%% of Palantir each)" % (PP.DECOY_HP_FRACTION * 100))
    kill_outright(g, holos[0])
    run_seconds(g, PP.BROADCAST_FIRST + 0.1)
    alive = [e for e in g.get_enemy_manager().get_enemies() if e.get_type().is_hologram() and e.is_alive()]
    check(len(alive) == PP.DECOYS, "a broadcast re-projects destroyed holograms (%d)" % len(alive))
    _phase_to(g, pal, 0.3)
    check(not pr.beam_angles(pal), "the phase-3 beams warm up first")
    run_seconds(g, PP.PANOPTICON_DELAY + 0.1)
    a = pr.beam_angles(pal)
    import math
    check(len(a) == 2 and abs(abs(a[0] - a[1]) - math.pi) < 1e-9, "twin opposed beams in phase 3 (%s)" % (a,))
    before = pr.get_beam_angle()
    run_seconds(g, 1.0)
    turned = (pr.get_beam_angle() - before) % (2 * math.pi)
    check(abs(turned - 2 * math.pi / PP.PANOPTICON_PERIODS[2]) < 0.05, "and they sweep faster (%.2f rad/s)" % turned)


# ---------------------------------------------------------------- visuals and texts
def _paint(s):
    img = BufferedImage(1600, 1000, BufferedImage.TYPE_INT_ARGB)
    gr = img.create_graphics()
    s.paint(gr)
    gr.dispose()


def test_boss_ability_visuals_render(check, tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    from lindefense.ui.game_screen import GameScreen
    g = Game(maps.create(0), 31)
    g.set_invincible(True)
    g.set_global_enemy_speed_multiplier(0)
    s = GameScreen(None, g, False)
    em = g.get_enemy_manager()
    moab = em.spawn(E.BELLARMINE_COLLEGE_PREP, None, 0, 300)
    em.spawn(E.SW_RESOURCE_CONSULTANT, None, 0, 640)
    em.spawn(E.THREE_COM, None, 0, 1040)
    em.spawn(E.TIMSORT, None, 0, 1000)
    em.spawn(E.LOCKHEED_MARTIN, None, 0, 1400)
    em.update(0)
    moab.take_damage(moab.get_max_hp() * 0.6, 0)
    for _ in range(int(4.2 / DT)):
        s.frame(DT)
    _paint(s)
    lay = [r.phase.get_label() for r in s.dock.rows]
    check(any("NETWORK HUB" in x for x in lay), "the primary dock row shows the boss ability (%s)" % lay)
    p = Game(maps.create(0), 32)
    p.set_invincible(True)
    p.set_global_enemy_speed_multiplier(0)
    ps = GameScreen(None, p, False)
    pal = p.get_enemy_manager().spawn(E.PALANTIR, None, 0, 900)
    p.get_enemy_manager().update(0)
    ps.frame(0.5)
    pal._hp = pal.get_max_hp() * 0.6
    ps.frame(DT)
    for i, e in enumerate(pal.get_protocols().get_escorts()):
        e.set_distance(pal.get_distance() - 40 * (i + 1))   # the squadron has caught up
    for _ in range(int(1.0 / DT)):
        ps.frame(DT)
    _paint(ps)
    check("SWARM UPLINK" in ps.dock.rows[0].phase.get_label(), "Palantir's dock row shows the uplink (%s)" % ps.dock.rows[0].phase.get_label())
    pal._hp = pal.get_max_hp() * 0.3
    for _ in range(int((PP.PANOPTICON_DELAY + 0.5) / DT)):
        ps.frame(DT)
    _paint(ps)
    check(len(pal.get_protocols().beam_angles(pal)) == 2, "the phase-3 twin beams are live while painting")


def test_texts_describe_the_new_bosses(check):
    from lindefense.ui.catalog_screen import CatalogScreen
    for t, word in ((E.BELLARMINE_COLLEGE_PREP, "CREST SHIELD"), (E.SW_RESOURCE_CONSULTANT, "OUTSOURCING"),
                    (E.THREE_COM, "NETWORK HUB"), (E.LOCKHEED_MARTIN, "AFTERBURNER")):
        check(word in t.description, "%s description names its ability" % t)
        check(word.lower() in (CatalogScreen.boss_note(t) or "").lower(), "the catalog explains %s" % word)
    note = CatalogScreen.boss_note(E.PALANTIR)
    for word in ("phases 1 and 2", "Swarm Uplink", "escort", "twin"):
        check(word.lower() in note.lower(), "the Palantir catalog note mentions %r" % word)
    for u in AttackUnit:
        if u.is_boss():
            check("{:,}".format(u.base_hp()) in u.blurb, "the reverse-mode blurb of %s quotes its HP (%s)" % (u, u.blurb))
            check(u.base_hp() <= u.type.base_hp, "%s keeps its beta 3.0 health in reverse mode (%d)" % (u, u.base_hp()))
