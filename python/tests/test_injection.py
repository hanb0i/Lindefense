"""Prompt injection and Palantir's phase abilities (port of InjectionTests.java). No window is ever touched: the
window-grab geometry is tested through its pure helpers."""
import math

from kit import DT, buildable_near, force_place, kill_outright, new_game, run_seconds, spawn_at
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.enemy.boss import PalantirProtocols
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType, Modifier, StatusKind
from lindefense.jenum import EnumSet
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.misc import WindowLink
from lindefense.sim.prompt_injection import PromptInjection as PI
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower import Intrusion
from lindefense.tower.tower_type import Targeting, TowerType as T
from lindefense.ui import intrusion_text as IT
from lindefense.ui import window_grab as WG
from lindefense.ui.window_grab import Rect
from lindefense.wave import waves

IMMUNE = (T.CLAUDE, T.COPILOT, T.DEEPSEEK, T.PERPLEXITY, T.MR_LINDEMANN)
PP = PalantirProtocols


# ---------------------------------------------------------------- helpers
def _frozen():
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    g.set_hero_limit(2 ** 31 - 1)
    return g


def _track(g, d):
    return g.get_map().get_routes()[0].position_at(d)


def _place(g, t, target, tier):
    return force_place(g, t, buildable_near(g, target, 160), tier)


def _spot_at_distance(g, center, dmin, dmax, type_):
    best, best_d = None, float("inf")
    for x in range(25, 1180, 5):
        for y in range(25, 880, 5):
            p = Vec(x, y)
            d = p.dist(center)
            if d < dmin or d > dmax or not g.get_map().is_buildable(p, 20):
                continue
            why = g.get_tower_manager().placement_problem(type_, p)
            if why is not None and why != "Not enough cash":
                continue
            if d < best_d:
                best_d, best = d, p
    return best


def _injector(g, t, d):
    e = g.get_enemy_manager().spawn_scaled(t, EnumSet.of(Modifier.INJECTION), 0, d, 1e5, 1.0)
    g.get_enemy_manager().update(0)
    return e


def _palantir(g, d):
    return spawn_at(g, EnemyType.PALANTIR, None, 0, d)


def _hp_to(g, pal, fraction):
    """Drops Palantir to exactly fraction of its max HP (straight to the hull: the Swarm Uplink of the escorts that each
    phase launches would otherwise soften the blow) and lets one tick run the phase change."""
    dmg = pal.get_hp() - pal.get_max_hp() * fraction
    if dmg > 0:
        Enemy.take_damage(pal, dmg, g.get_time())
    g.run(1)


def _clear_escorts(g, pal):
    """Removes the escort bosses Palantir launched (and their uplink) so damage numbers can be checked exactly."""
    for e in list(g.get_enemy_manager().get_enemies()):
        if e.is_boss() and e is not pal:
            g.get_enemy_manager().destroy_without_children(e, None)
    g.run(1)


# ---------------------------------------------------------------- immunity data
def test_immunity_is_data_driven(check):
    immune = []
    for t in T:
        if catalog.get(t) is None or not t.is_purchasable():
            continue
        if catalog.is_injection_immune(t):
            immune.append(t)
        for i in range(len(catalog.get(t).upgrades) + 1):
            check(catalog.get(t).stats_for_tier(i).injection_immune == catalog.is_injection_immune(t), "%s immunity same at tier %d" % (t, i))
        check(catalog.grants_injection_firewall(t) == (t is T.COPILOT), "%s firewall grant" % t)
    check(len(immune) == len(IMMUNE), "exactly five tower types are immune, got %r" % immune)
    for t in IMMUNE:
        check(t in immune, "%s is immune to prompt injection" % t)
        why = catalog.injection_immunity_reason(t)
        check(why is not None and len(why) > 10, "%s says why it is immune" % t)
    check(catalog.injection_immunity_reason(T.GPT) is None, "GPT has no immunity reason")
    check(T.MR_LINDEMANN in immune and T.LOBBER_LUIS not in immune, "the CS-teacher hero is immune, other heroes are not")
    check(IT.type_line(T.CLAUDE).startswith(IT.IMMUNE), "the panel / catalog line reads IMMUNE TO PROMPT INJECTION")
    check(IT.type_line(T.GPT) is None, "no immunity line for GPT")


def test_modifier_not_inherited(check):
    g = _frozen()
    tim = _injector(g, EnemyType.TIMSORT, 300)
    check(tim.has(Modifier.INJECTION), "the injector carries the modifier")
    kill_outright(g, tim)
    kids = 0
    for e in g.get_enemy_manager().get_enemies():
        kids += 1
        check(not e.has(Modifier.INJECTION), "children never inherit Prompt Injection (%s)" % e.get_type())
    check(kids == 2, "the TimSort still splits (%d)" % kids)
    for w in range(1, waves.INJECTION_FIRST_WAVE):
        for s in Difficulty.ONN.shape(waves.get(w), 42).groups:
            check(Modifier.INJECTION not in s.modifiers, "no elite rolls Prompt Injection on wave %d" % w)


# ---------------------------------------------------------------- hijack
def test_injector_hijacks_nearest(check):
    g = _frozen()
    at = _track(g, 450)
    a = _place(g, T.GPT, at.add(Vec(0, -60)), 0)
    b = _place(g, T.GEMINI, at.add(Vec(50, 60)), 0)
    c = _place(g, T.SORA, at.add(Vec(-60, 70)), 0)
    far = force_place(g, T.GROK, _spot_at_distance(g, at, PI.RADIUS + 60, 900, T.GROK), 0)
    inj = _injector(g, EnemyType.HEAP_SORT, 450)
    in_reach = [t for t in (a, b, c) if t.get_position().dist(inj.get_position()) <= PI.RADIUS]
    in_reach.sort(key=lambda t: t.get_position().dist_sq(inj.get_position()))
    check(len(in_reach) >= 2, "at least two towers in reach (%d)" % len(in_reach))
    check(far.get_position().dist(inj.get_position()) > PI.RADIUS, "the far tower is out of reach")
    g.run(1)
    check(g.get_injection().get_broadcasts() == 1, "the injector broadcasts as soon as a tower is in reach")
    hijacked = sum(1 for t in (a, b, c) if t.is_hijacked())
    n = min(PI.MAX_TARGETS, len(in_reach))
    check(hijacked == n, "a broadcast hijacks the %d nearest towers (%d)" % (PI.MAX_TARGETS, hijacked))
    for i in range(n):
        check(in_reach[i].is_hijacked(), "near tower %d is hijacked" % i)
        check(in_reach[i].get_intrusion().get_hijacker() is inj, "the hijacker is remembered for the beam")
    check(not far.is_hijacked() and not far.is_offline(), "a tower out of reach is untouched")
    check(abs(in_reach[0].get_intrusion().get_remaining() - (PI.HIJACK_TIME - DT)) < 1e-6, "a hijack lasts %s s" % PI.HIJACK_TIME)
    check(not in_reach[0].is_ability_ready() or in_reach[0].get_ability() is None, "a hijacked tower cannot use an ability")
    run_seconds(g, PI.INTERVAL - 0.5)
    check(g.get_injection().get_broadcasts() == 1, "no second broadcast before the interval")
    run_seconds(g, 1.0)
    check(g.get_injection().get_broadcasts() == 2, "the injector broadcasts again after the interval")


def test_hijacked_tower_zaps_neighbours(check):
    g = _frozen()
    at = _track(g, 500)
    a = _place(g, T.GPT, at.add(Vec(0, -70)), 1)
    b = _place(g, T.GEMINI, a.get_position().add(Vec(55, 0)), 1)
    check(a.get_position().dist(b.get_position()) <= PI.ZAP_RANGE, "the neighbour is within zap range")
    dummy = g.get_enemy_manager().spawn_scaled(EnemyType.HEAP_SORT, None, 0, 500, 1e6, 1.0)
    g.get_enemy_manager().update(0)
    source = object()
    check(g.get_injection().hijack(a, source, PI.HIJACK_TIME), "hijack accepted")
    a_dmg = a.get_damage_dealt()
    run_seconds(g, PI.FIRST_ZAP - 0.1)
    check(not b.is_offline(), "no zap before FIRST_ZAP")
    run_seconds(g, 0.2)
    check(b.get_intrusion().is_disabled() and b.get_intrusion().get_disabled_by() is a, "the hijacked tower zaps its neighbour")
    check(not b.is_hijacked(), "a zapped neighbour is disabled, never hijacked")
    check(a.get_intrusion().get_last_victim() is b, "the zap beam knows its victim")
    b_dmg = b.get_damage_dealt()
    run_seconds(g, PI.DISABLE_TIME - 0.3)
    check(b.get_damage_dealt() == b_dmg, "a disabled tower does not attack")
    run_seconds(g, PI.HIJACK_TIME - (PI.FIRST_ZAP + 0.1 + PI.DISABLE_TIME - 0.3) - 0.1)
    check(a.is_hijacked() and a.get_damage_dealt() == a_dmg, "a hijacked tower never attacks enemies")
    run_seconds(g, 0.2)
    check(not a.is_offline() and a.get_intrusion().is_patched(), "the hijack ends and the tower is patched")
    check(g.get_injection().get_zaps() == PI.ZAPS_PER_HIJACK, "%d zaps per hijack (%d)" % (PI.ZAPS_PER_HIJACK, g.get_injection().get_zaps()))
    check(not g.get_injection().hijack(a, source, 3), "a patched tower cannot be hijacked again at once")
    run_seconds(g, 1.5)
    check(a.get_damage_dealt() > a_dmg, "the freed tower attacks enemies again")
    check(dummy.is_alive(), "the dummy is still there")


def test_each_immune_tower_resists(check):
    for type_ in IMMUNE:
        g = _frozen()
        at = _track(g, 450)
        t = _place(g, type_, at.add(Vec(0, -60)), 0)
        check(t.is_injection_immune(), "%s reports immunity" % type_)
        victim = _place(g, T.GPT, t.get_position().add(Vec(0, -60)), 0)
        for i in range(3):
            _injector(g, EnemyType.HEAP_SORT, 420 + i * 30)
        ever_offline = False
        for _ in range(int(20 / DT)):
            g.step(DT)
            if t.is_offline():
                ever_offline = True
        check(not ever_offline, "%s is never hijacked, disabled or blinded" % type_)
        check(g.get_injection().get_blocks() > 0, "%s shows BLOCKED when an injector tries" % type_)
        check(not g.get_injection().hijack(t, object(), 3), "%s refuses a direct hijack" % type_)
        g2 = _frozen()
        t2 = _place(g2, type_, _track(g2, 450).add(Vec(0, -60)), 0)
        if type_ is T.COPILOT:
            hp = _spot_at_distance(g2, t2.get_position(), t2.get_stats().aura_range + 5, PI.ZAP_RANGE - 2, T.GPT)
        else:
            hp = buildable_near(g2, t2.get_position().add(Vec(55, 0)), 80)
        check(hp is not None, "a spot for the zapper beside %s" % type_)
        if hp is None:
            continue
        h = force_place(g2, T.GPT, hp, 0)
        g2.get_tower_manager().recompute_auras()
        check(g2.get_injection().hijack(h, object(), PI.HIJACK_TIME), "hijack the neighbour of %s" % type_)
        run_seconds(g2, PI.HIJACK_TIME + 0.2)
        check(not t2.is_offline() and t2.get_intrusion().get_total_offline_time() == 0, "zaps never disable %s" % type_)
        check(victim.is_alive(), "the GPT beside %s exists" % type_)


def test_copilot_firewall(check):
    g = _frozen()
    at = _track(g, 450)
    cop = _place(g, T.COPILOT, at.add(Vec(0, -60)), 0)
    inside = force_place(g, T.GPT, buildable_near(g, cop.get_position().add(Vec(60, 0)), 50), 0)
    outside = _place(g, T.GEMINI, at.add(Vec(0, 300)), 0)
    g.get_tower_manager().recompute_auras()
    rng = cop.get_stats().aura_range
    check(inside.get_position().dist(cop.get_position()) <= rng, "the GPT stands in the Copilot tether")
    check(outside.get_position().dist(cop.get_position()) > rng, "the Gemini stands outside it")
    check(inside.is_injection_immune() and inside.get_intrusion().is_firewalled(), "the firewall makes a tower in the tether immune")
    check(not outside.is_injection_immune(), "a tower outside the tether is not protected")
    check(not g.get_injection().hijack(inside, object(), 3), "a firewalled tower refuses a hijack")
    check(g.get_injection().hijack(outside, object(), 3), "an unprotected tower can be hijacked")
    check(IT.tower_line(outside).startswith("HIJACKED"), "the panel shows HIJACKED")
    check("Copilot firewall" in IT.tower_line(inside), "the panel credits the Copilot firewall")
    check(IT.tower_line(cop).startswith(IT.IMMUNE), "the panel shows Copilot's own immunity")
    _injector(g, EnemyType.HEAP_SORT, 450)
    off = False
    for _ in range(int(12 / DT)):
        g.step(DT)
        if inside.is_offline():
            off = True
    check(not off, "the firewalled GPT never goes offline")
    g.sell_tower(cop)
    g.get_tower_manager().recompute_auras()
    check(not inside.is_injection_immune(), "the firewall is gone once the Copilot is sold")


def test_bounded_chains_no_lockout(check):
    g = _frozen()
    r = g.get_map().get_routes()[0]
    types = (T.GPT, T.GEMINI, T.SORA, T.GROK, T.SUNO, T.KIMI, T.GLM, T.MINIMAX, T.COHERE, T.QWEN)
    towers = []
    for i, ty in enumerate(types):
        p = r.position_at(380 + (i // 2) * 45).add(Vec(0, -65 if i % 2 == 0 else 65))
        towers.append(_place(g, ty, p, 1))
    _injector(g, EnemyType.HEAP_SORT, 390)
    _injector(g, EnemyType.HEAP_SORT, 560)
    run = {id(t): 0.0 for t in towers}
    max_run = dict(run)
    min_gap = {id(t): 1e9 for t in towers}
    last_end = {}
    hijack_from_zap = 0
    time = 0.0
    for _ in range(int(45 / DT)):
        was = {id(t): t.get_intrusion().is_disabled() for t in towers}
        g.step(DT)
        time += DT
        for t in towers:
            k = id(t)
            if was[k] and t.is_hijacked():
                hijack_from_zap += 1
            if t.is_offline():
                if run[k] == 0 and k in last_end:
                    min_gap[k] = min(min_gap[k], time - last_end[k])
                run[k] += DT
                max_run[k] = max(max_run[k], run[k])
            elif run[k] > 0:
                run[k] = 0.0
                last_end[k] = time
    longest = max(PI.HIJACK_TIME, PI.DISABLE_TIME) + 2 * DT
    inj = g.get_injection()
    check(inj.get_hijacks() > 0 and inj.get_disables() > 0, "hijacks (%d) and zaps (%d)" % (inj.get_hijacks(), inj.get_disables()))
    for t in towers:
        check(max_run[id(t)] <= longest, "%s never offline longer than one intrusion (%s s)" % (t.get_type(), max_run[id(t)]))
        check(min_gap[id(t)] >= Intrusion.GRACE - 2 * DT, "%s always gets the patch window (%s s)" % (t.get_type(), min_gap[id(t)]))
    check(hijack_from_zap == 0, "a disabled tower never turns into a hijacked one")
    check(inj.get_hijacks() <= inj.get_broadcasts() * PI.MAX_TARGETS, "hijacks per broadcast are capped")
    check(inj.get_disables() <= inj.get_hijacks() * PI.ZAPS_PER_HIJACK, "disables per hijack are capped")
    for _ in range(3):
        for e in list(g.get_enemy_manager().get_enemies()):
            kill_outright(g, e)
    run_seconds(g, PI.HIJACK_TIME + 0.1)
    check(not any(t.is_offline() for t in towers), "no permanent lockout once the injectors are gone")


def test_counterplay(check):
    g = _frozen()
    at = _track(g, 450)
    t = _place(g, T.GPT, at.add(Vec(0, -60)), 0)
    inj = _injector(g, EnemyType.HEAP_SORT, 450)
    inj.apply_status(StatusKind.STUN, 1, 2)
    g.run(30)
    check(g.get_injection().get_broadcasts() == 0 and not t.is_offline(), "a stunned injector cannot broadcast")
    inj.clear_status(StatusKind.STUN)
    inj.apply_status(StatusKind.DISRUPTED, 1, 2)
    g.run(30)
    check(g.get_injection().get_broadcasts() == 0, "a Disrupted injector cannot broadcast")
    inj.clear_status(StatusKind.DISRUPTED)
    g.run(1)
    check(t.is_hijacked(), "once free it broadcasts and hijacks")
    check(g.upgrade_tower(t) and not t.is_offline() and t.get_intrusion().is_patched(), "upgrading a hijacked tower patches it")


# ---------------------------------------------------------------- waves
def _injectors(w):
    return sum(s.count for s in w.groups if Modifier.INJECTION in s.modifiers)


def test_wave_schedule(check):
    band = {30: 0, 50: 0, 70: 0}
    nw = {30: 0, 50: 0, 70: 0}
    for w in waves.all_waves():
        n = _injectors(w)
        carrier = any(not s.type.is_boss() for s in w.groups)
        check(n == waves.injectors(w.number) or (n == 0 and not carrier), "wave %d has %d injectors (%d)" % (w.number, waves.injectors(w.number), n))
        if w.number < waves.INJECTION_FIRST_WAVE:
            check(n == 0, "no injectors before wave 30 (wave %d)" % w.number)
        if w.number == waves.WAVE_COUNT:
            check(n == 0, "wave 100 leaves the injecting to Palantir")
        for s in w.groups:
            if Modifier.INJECTION not in s.modifiers:
                continue
            check(not s.type.is_boss(), "injectors are never bosses (wave %d)" % w.number)
            check(any(o is not s and o.type is s.type for o in w.groups), "the injector group was split off (wave %d)" % w.number)
        key = 30 if 30 <= w.number < 50 else 50 if 50 <= w.number < 70 else 70 if 70 <= w.number < 100 else None
        if key is not None:
            band[key] += n
            if n > 0:
                nw[key] += 1
    fw = waves.get(waves.INJECTION_FIRST_WAVE)
    check(_injectors(fw) > 0 and "Prompt Injection" in fw.note, "wave 30 introduces Prompt Injection in its note")
    seen = set()
    debuts = []
    for w in waves.all_waves():
        debut = False
        for s in w.groups:
            if s.type.is_boss() and s.type is not EnemyType.PALANTIR and s.type not in seen:
                seen.add(s.type)
                debut = True
        if debut:
            debuts.append(w.number)
            check(_injectors(w) == 0, "no injectors on boss debut wave %d" % w.number)
    check(debuts == list(waves.BOSS_DEBUTS), "BOSS_DEBUTS lists the boss debut waves %r" % debuts)
    check(nw[30] < nw[50] < nw[70], "injection waves get more frequent %r" % nw)
    check(band[30] < band[50] < band[70], "and more numerous %r" % band)
    total = {d: sum(_injectors(d.shape(waves.get(w), 42)) for w in range(30, 100)) for d in Difficulty}
    D = Difficulty
    check(total[D.O1] < total[D.ON] < total[D.ON2] and total[D.ON] < total[D.ONN], "more injectors at higher growth %r" % total)


# ---------------------------------------------------------------- Palantir
def test_palantir_panopticon(check):
    g = _frozen()
    pal = _palantir(g, 500)
    pr = pal.get_protocols()
    check(pr is not None, "Palantir has its phase protocols")
    p = pal.get_position()
    near = _place(g, T.GPT, p.add(Vec(0, -150)), 0)
    far = _place(g, T.GEMINI, Vec(p.x + 520 if p.x + 520 < 1150 else p.x - 520, p.y), 0)
    check(near.get_position().dist(p) < PP.PANOPTICON_RANGE, "a tower inside the beam's reach")
    far_in_reach = far.get_position().dist(p) <= PP.PANOPTICON_RANGE + far.get_radius()
    run_seconds(g, PP.PANOPTICON_DELAY - 0.2)
    check(not pr.is_beam_active(pal) and pr.get_blinds() == 0, "the beam switches on after the delay")
    near_b = far_b = False
    dmg_blind = -1.0
    for _ in range(int((PP.PANOPTICON_PERIOD + 0.5) / DT)):
        before = near.get_damage_dealt()
        was = near.get_intrusion().is_blinded()
        g.step(DT)
        if near.get_intrusion().is_blinded():
            near_b = True
        if far.get_intrusion().is_blinded():
            far_b = True
        if was and near.get_intrusion().is_blinded():
            dmg_blind = max(dmg_blind, near.get_damage_dealt() - before)
    check(pr.is_beam_active(pal), "the beam sweeps in phase 1")
    check(near_b, "the beam blinds a tower it sweeps within one turn")
    check(dmg_blind <= 0, "a blinded tower does not attack")
    if not far_in_reach:
        check(not far_b, "a tower beyond the beam's reach is never blinded")
    g2 = _frozen()
    pal2 = _palantir(g2, 500)
    perp = _place(g2, T.PERPLEXITY, pal2.get_position().add(Vec(0, -150)), 2)
    guarded = force_place(g2, T.GPT, buildable_near(g2, perp.get_position().add(Vec(60, 0)), 60), 0)
    g2.get_tower_manager().recompute_auras()
    check(guarded.is_surveillance_immune(), "the GPT stands in the Perplexity U2 radius")
    hit = False
    for _ in range(int((PP.PANOPTICON_DELAY + 2 * PP.PANOPTICON_PERIOD) / DT)):
        g2.step(DT)
        if guarded.is_offline() or perp.is_offline():
            hit = True
    check(not hit, "Perplexity's Predictive Analysis radius blocks the Panopticon")
    pp, gp = pal2.get_position(), guarded.get_position()
    check(PP.in_beam(pp, math.atan2(gp.y - pp.y, gp.x - pp.x), guarded), "in_beam is true straight down the beam")
    _hp_to(g, pal, 0.69)
    check(pal.get_phase() == 1 and not pr.is_beam_active(pal), "no Panopticon beam in phase 2")


def test_palantir_prompt_broadcast(check):
    g = _frozen()
    pal = _palantir(g, 500)
    p = pal.get_position()
    ds = _place(g, T.DEEPSEEK, p.add(Vec(-200, -120)), 3)
    others = [_place(g, T.GPT, p.add(Vec(0, -160)), 3), _place(g, T.GEMINI, p.add(Vec(160, -60)), 2),
              _place(g, T.SORA, p.add(Vec(-160, 60)), 1), _place(g, T.GROK, p.add(Vec(150, 150)), 0),
              _place(g, T.SUNO, p.add(Vec(-300, 200)), 0)]
    _hp_to(g, pal, 0.69)
    check(pal.get_phase() == 1, "phase 2 at 69%")
    pr = pal.get_protocols()
    run_seconds(g, PP.BROADCAST_FIRST - 0.2)
    check(pr.get_broadcasts() == 0, "the first broadcast waits")
    run_seconds(g, 0.3)
    check(pr.get_broadcasts() == 1, "Prompt Broadcast fires")
    n = PP.broadcast_targets(g)
    check(n == PP.BROADCAST_TARGETS, "a small defence gets %d targets (%d)" % (PP.BROADCAST_TARGETS, n))
    srt = sorted(others, key=lambda t: -t.get_invested_cost())
    for i, t in enumerate(srt):
        if i < n:
            check(t.is_hijacked() and t.get_intrusion().get_hijacker() is pal, "broadcast hijacks #%d investment %s" % (i + 1, t.get_type()))
        else:
            check(not t.is_hijacked(), "cheaper %s is not hijacked" % t.get_type())
    check(not ds.is_offline(), "DeepSeek ignores the broadcast")
    check(len(pr.get_last_broadcast_targets()) == n, "the renderer sees the broadcast targets")
    run_seconds(g, PP.BROADCAST_INTERVAL)
    check(pr.get_broadcasts() == 2, "broadcasts repeat")
    big = _frozen()
    for i in range(200):
        v = buildable_near(big, Vec(60 + (i * 73) % 1080, 60 + (i * 41) % 780), 200)
        why = big.get_tower_manager().placement_problem(T.GPT, v)
        if why is None or why == "Not enough cash":
            force_place(big, T.GPT, v, 0)
    towers = len(big.get_tower_manager().get_player_towers())
    exp = min(PP.BROADCAST_MAX_TARGETS, PP.BROADCAST_TARGETS + towers // PP.BROADCAST_TOWERS_PER_EXTRA)
    check(PP.broadcast_targets(big) == exp, "targets grow with the defence (%d towers -> %d)" % (towers, PP.broadcast_targets(big)))


def test_palantir_decoys(check):
    g = _frozen()
    pal = _palantir(g, 500)
    p = pal.get_position()
    gpt = _place(g, T.GPT, p.add(Vec(0, -70)), 0)
    ds = _place(g, T.DEEPSEEK, p.add(Vec(0, 90)), 0)
    gpt.set_targeting(Targeting.STRONGEST)
    ds.set_targeting(Targeting.STRONGEST)
    check(g.get_combat().acquire_targets(gpt, 1)[0] is pal, "before phase 2 the GPT targets Palantir")
    before_n = len(g.get_enemy_manager().get_enemies())
    cash = g.get_cash()
    lives = g.get_lives()
    _hp_to(g, pal, 0.69)
    decoys = [e for e in g.get_enemy_manager().get_enemies() if e.get_type() is EnemyType.PALANTIR_HOLOGRAM]
    check(len(decoys) == PP.DECOYS, "phase 2 projects %d decoys (%d)" % (PP.DECOYS, len(decoys)))
    escorts = sum(n for _, n, _ in PP.ESCORTS[1])
    check(len(g.get_enemy_manager().get_enemies()) == before_n + PP.DECOYS + escorts, "nothing but the decoys and the escorts spawns")
    _clear_escorts(g, pal)
    check(len(pal.get_protocols().get_decoys()) == PP.DECOYS and g.get_injection().has_decoys(), "the decoys are tracked")
    for d in decoys:
        check(abs(d.get_max_hp() - round(pal.get_max_hp() * PP.DECOY_HP_FRACTION)) <= 1, "decoy HP fraction (%s)" % d.get_max_hp())
        check(not d.is_boss() and d.get_type().reward == 0 and d.get_type().lives == 0, "decoys pay nothing and cost no lives")
        check(abs(d.get_distance() - pal.get_distance()) <= PP.DECOY_SPACING * (1 + (PP.DECOYS - 1) // 2) + 1, "decoys fly next to Palantir")
        check(not d.get_type().is_spawnable_species(), "the hologram is never part of a wave")
    t = g.get_combat().acquire_targets(gpt, 1)
    check(t and t[0].get_type() is EnemyType.PALANTIR_HOLOGRAM, "decoys draw a non-immune tower's fire")
    td = g.get_combat().acquire_targets(ds, 1)
    check(td and td[0] is pal, "DeepSeek sees through the holograms")
    leak = decoys[0]
    leak.set_distance(leak.get_route().get_total_length() - 0.5)
    g.set_global_enemy_speed_multiplier(1)
    g.run(30)
    g.set_global_enemy_speed_multiplier(0)
    check(not leak.is_alive() and g.get_lives() == lives, "a leaking hologram costs no lives")
    before = g.get_cash()
    for d in decoys[1:]:
        kill_outright(g, d)
    check(g.get_cash() == before and not decoys[1].is_alive(), "a destroyed hologram pays nothing")
    check(not g.get_injection().has_decoys(), "no decoys left")
    check(g.get_combat().acquire_targets(gpt, 1)[0] is pal, "with the decoys gone the GPT targets Palantir again")
    check(cash <= g.get_cash() + 1e-9, "cash never dropped")


def test_palantir_kill_switch(check):
    g = _frozen()
    pal = _palantir(g, 500)
    p = pal.get_position()
    gpt = _place(g, T.GPT, p.add(Vec(-150, -150)), 3)
    ds = _place(g, T.DEEPSEEK, p.add(Vec(150, -150)), 3)
    zet = _place(g, T.ZETHOS, p.add(Vec(-150, 170)), catalog.ZETHOS_UPGRADES)
    g.add_cash(3 * catalog.ABILITY_UNLOCK_COST, None)
    check(g.unlock_ability(gpt) and g.unlock_ability(ds) and g.unlock_ability(zet), "abilities unlocked")
    locked = _place(g, T.GEMINI, p.add(Vec(170, 170)), 3)
    _hp_to(g, pal, 0.69)
    _hp_to(g, pal, 0.41)
    check(g.get_banner() is not None and g.get_banner().startswith("KILL SWITCH"), "a warning shows (%s)" % g.get_banner())
    check(gpt.get_ability_cooldown_remaining() == 0 and ds.get_ability_cooldown_remaining() == 0, "abilities still ready in phase 2")
    lockheeds = g.get_enemy_manager().count_of_type(EnemyType.LOCKHEED_MARTIN)
    _hp_to(g, pal, 0.34)
    pr = pal.get_protocols()
    check(pal.get_phase() == 2 and pr.is_kill_switch_used(), "System Takeover fires the kill switch")
    check(abs(gpt.get_ability_cooldown_remaining() - gpt.get_ability().cooldown) < 1e-6, "GPT's ability restarts its cooldown")
    check(abs(zet.get_ability_cooldown_remaining() - zet.get_ability().cooldown) < 1e-6, "Zethos's ability restarts its cooldown")
    check(ds.get_ability_cooldown_remaining() == 0, "DeepSeek keeps its ability ready")
    check(locked.is_ability_locked() and locked.get_ability_cooldown_remaining() == 0, "a locked ability is untouched")
    check(pr.get_kill_switch_resets() == 2, "two abilities reset (%d)" % pr.get_kill_switch_resets())
    ddt = sum(n for t, n, _ in PP.ESCORTS[2] if t is EnemyType.LOCKHEED_MARTIN)
    check(ddt >= 1 and g.get_enemy_manager().count_of_type(EnemyType.LOCKHEED_MARTIN) == lockheeds + ddt, "the Lockheed escorts still launch")
    check(g.get_window_link().consume_grab_requests() >= 1, "System Takeover asks the UI to grab the window")
    gpt.reset_ability_cooldown()
    run_seconds(g, 2)
    check(gpt.get_ability_cooldown_remaining() == 0 and pr.get_kill_switch_resets() == 2, "the kill switch fires only once")


def test_window_seal(check):
    g = _frozen()
    pal = _palantir(g, 500)
    check(g.get_window_fraction() == 1.0, "the window fraction defaults to 1.0")
    _hp_to(g, pal, 0.30)
    _clear_escorts(g, pal)
    link = g.get_window_link()
    check(pal.get_phase() == 2 and link.is_takeover_active(), "phase 3 starts the takeover")
    check(not pal.is_sealed(), "an untouched window never seals Palantir")
    check(abs(pal.take_damage(100, g.get_time()) - 100) < 1e-9, "full damage while unsealed")
    g.set_window_fraction(WindowLink.SEAL_THRESHOLD)
    g.run(1)
    check(not pal.is_sealed(), "exactly the threshold does not seal")
    g.set_window_fraction(0.72)
    g.run(1)
    check(pal.is_sealed() and link.is_sealing(), "a window below the threshold seals Palantir")
    check(abs(pal.take_damage(100, g.get_time()) - 100 * PP.SEAL_DAMAGE_MULT) < 1e-9, "sealed Palantir takes reduced damage")
    hp0 = pal.get_hp()
    run_seconds(g, 2)
    gain = pal.get_hp() - hp0
    check(abs(gain - PP.SEAL_REGEN_PER_SEC * pal.get_max_hp() * 2) < pal.get_max_hp() * 0.001, "sealed regen (%s)" % gain)
    run_seconds(g, 60)
    check(pal.get_max_hp() * PP.SEAL_REGEN_CAP - 1 <= pal.get_hp() <= pal.get_max_hp() * PP.SEAL_REGEN_CAP + 1e-6,
          "regeneration stops at the cap (%s)" % pal.get_hp_fraction())
    check(pal.get_phase() == 2, "regeneration never reverts the phase")
    g.set_window_fraction(0.9)
    g.run(1)
    check(not pal.is_sealed(), "dragging the window back breaks the seal")
    check(abs(pal.take_damage(100, g.get_time()) - 100) < 1e-9, "full damage again")
    g.set_window_fraction(float("nan"))
    check(g.get_window_fraction() == 0.9, "NaN reports are ignored")
    g.set_window_fraction(-3)
    check(g.get_window_fraction() >= 0.05, "the fraction is clamped")
    g.set_window_fraction(0.5)
    kill_outright(g, pal)
    check(not link.is_takeover_active() and not link.is_sealing(), "the takeover ends when Palantir dies")


def test_window_seal_never_in_headless(check):
    g = _frozen()
    pal = _palantir(g, 500)
    _hp_to(g, pal, 0.30)
    requests = g.get_window_link().consume_grab_requests()
    run_seconds(g, PP.REGRAB_INTERVAL + 1)
    requests += g.get_window_link().consume_grab_requests()
    check(not pal.is_sealed() and pal.get_protocols().get_sealed_time() == 0, "never sealed without a windowed UI")
    check(requests >= 2, "the grab is renewed (%d requests)" % requests)
    inert = WG.WindowGrab.create(None, False)
    check(not inert.is_active(), "no window: the controller is inert")
    check(not WG.WindowGrab.create(None, True).is_active(), "the demo never grabs")
    check(not WG.environment_allows() or not WG.is_headless(), "headless runs never allow the grab")
    g.set_window_fraction(0.95)
    g.get_window_link().request_grab(pal)
    inert.frame(0.1, g)
    check(g.get_window_fraction() == 0.95 and not inert.is_holding(), "an inert controller leaves the simulation alone")


def test_window_grab_geometry(check):
    screen = Rect(0, 25, 1920, 1055)
    mn = (WG.MIN_W, WG.MIN_H)
    base = Rect(220, 60, 1472, 946)
    t = WG.plan(base, base, screen, mn, 1)
    check(t.width == round(base.width * WG.SHRINK) and t.height == round(base.height * WG.SHRINK), "the grab shrinks (%r)" % t)
    check(screen.contains(t), "the grabbed window stays on screen")
    f = WG.fraction(t.size, base.size)
    check(0.70 <= f <= 0.75 and f < WindowLink.SEAL_THRESHOLD, "a fresh grab seals Palantir (%s)" % f)
    dx, dy = t.center_x - base.center_x, t.center_y - base.center_y
    check(abs(dx - screen.width * WG.DRIFT_X) <= 1 and abs(dy - screen.height * WG.DRIFT_Y) <= 1, "the window drifts (%s, %s)" % (dx, dy))
    back = WG.plan(base, base, screen, mn, -1)
    check(back.center_x < base.center_x, "the next grab drifts the other way")
    small = Rect(100, 100, 700, 450)
    ts = WG.plan(small, small, screen, mn, 1)
    check(ts.width == WG.MIN_W and ts.height == WG.MIN_H, "a small window stops at the minimum (%r)" % ts)
    edge = Rect(1700, 900, 1200, 800)
    check(screen.contains(WG.plan(edge, edge, screen, mn, 1)), "a window near the edge is clamped inside")
    huge = WG.clamp_to_screen(Rect(-50, -50, 4000, 3000), screen, mn)
    check(huge.width <= screen.width and huge.height <= screen.height and screen.contains(huge), "never larger than the screen")
    tiny = WG.clamp_to_screen(Rect(10, 30, 100, 100), screen, mn)
    check(tiny.width == WG.MIN_W and tiny.height == WG.MIN_H, "never below the minimum")
    check(WG.fraction((1600, 1000), (1600, 1000)) == 1.0, "untouched window = 1.0")
    check(WG.fraction((2000, 900), (1600, 1000)) == 0.9, "the smaller ratio counts")
    check(WG.fraction((10, 10), None) == 1.0, "no baseline = 1.0")
    check(WG.ease(0) == 0 and WG.ease(1) == 1 and WG.ease(0.5) == 0.5 and WG.ease(2) == 1, "ease-in-out endpoints")
    check(WG.lerp(base, t, 0) == base and WG.lerp(base, t, 1) == t, "lerp endpoints")
    check(1 <= WG.ANIM_SECONDS <= 2, "the grab animates over 1-2 s")
