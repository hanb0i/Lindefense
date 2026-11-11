"""Reverse mode ("Adversarial Training"): economy, rounds and objectives, sudden-death overtime, doctrines, the AI's
adaptations, matchup intel, unlocks, the uplink, exploits, win / loss and whole matches (ported from
ReverseModeTests.java, then revamped for the 8-round match). The screens are covered at the end of this file."""
import pytest

from kit import kill_outright, spawn_at
from lindefense import prefs
from lindefense.ai import reverse_match as RM
from lindefense.ai import units
from lindefense.ai.defender_ai import Action, DefenderAI, Options
from lindefense.ai.reverse_match import AttackerBot, ReverseMatch, Style
from lindefense.ai.units import (OVERCLOCK_SPEED, ZERO_DAY_TARGETS, AttackAbility, AttackUnit, DefenderProfile, Doctrine,
                                 Role)
from lindefense.enemy.boss import Boss
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.javacompat import jround
from lindefense.jenum import EnumSet
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.tools import auto_player
from lindefense.tower import catalog
from lindefense.tower.manager import MAX_HEROES_PER_GAME
from lindefense.tower.tower_type import TowerType as T

DT = Game.DT


@pytest.fixture(autouse=True)
def _session_doctrine():
    """The briefing's doctrine pick is session state: every test starts and ends on the default."""
    units.select_doctrine(Doctrine.default())
    yield
    units.select_doctrine(Doctrine.default())


def _reverse(m, d, doctrine=None):
    return ReverseMatch.create(m, 42, d, doctrine)


def _advance(g, seconds):
    n = jround(seconds / DT)
    i = 0
    while i < n and g.get_state() is State.PLAYING:
        g.step(DT)
        g.get_events().clear()
        i += 1


def _advance_controller(g, seconds):
    g.set_paused(False)
    r = g.get_reverse()
    for _ in range(jround(seconds / 0.5)):
        r.update(0.5)


def _leak(g, lives):
    """The AI loses `lives` integrity to a leak (a unit placed at the end of the track)."""
    e = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    g.lose_lives(lives, e)
    kill_outright(g, e)   # off the track again: it must not walk on and leak a second time


# ---------------------------------------------------------------- economy
def test_economy(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    check(g.is_reverse() and r is not None and r.get_game() is g, "reverse game carries its controller")
    check(g.get_difficulty() is Difficulty.O1, "the game itself runs with base rules")
    check(r.get_profile() is DefenderProfile.COMPETENT and r.get_level() is Difficulty.ON, "O(N) picks the Competent AI")
    check(_reverse(0, Difficulty.ON).get_reverse().get_doctrine() is Doctrine.default() is Doctrine.RUSH, "Rush is the default doctrine")
    for d in Doctrine:
        check(_reverse(0, Difficulty.ON, d).get_reverse().get_credits() == d.start_credits,
              "%s starts with %d credits" % (d, d.start_credits))
    check(Doctrine.RUSH.start_credits > Doctrine.SWARM.start_credits > Doctrine.HEIST.start_credits >= 400,
          "a fast start: every doctrine starts with at least 400 compute, Rush the most")
    check(g.get_lives() == DefenderProfile.COMPETENT.integrity, "the defender starts with its integrity")
    check(g.get_cash() == Game.START_CASH * DefenderProfile.COMPETENT.start_cash, "and its opening budget")
    i0 = r.income_rate()
    check(abs(i0 - RM.INCOME_BASE) < 1e-9, "income starts at %s/s, got %s" % (RM.INCOME_BASE, i0))
    check(i0 >= 30, "a fast start: at least 30 compute per second from 0:00")
    _advance(g, 60)
    expected = Doctrine.SWARM.start_credits + 60 * (RM.INCOME_BASE + RM.INCOME_LINEAR / 2 + RM.INCOME_SQUARE / 3)
    check(abs(r.get_credits() - expected) < 3, "one minute of income: about %d, got %d" % (expected, r.get_credits()))
    check(r.income_rate() > i0 + 10, "income grows over the match (%s/s)" % r.income_rate())
    check(r.get_defender_funding() > 0 and g.get_total_cash_earned() > Game.START_CASH, "the defender is funded over time")
    check(abs(r.defender_funding_rate() - r.base_income() * RM.FUND_RATIO * DefenderProfile.COMPETENT.income) < 1e-9, "funding follows the curve")
    for mins, want in ((3, 30 + 36 + 13.5), (8, 30 + 96 + 96), (9, 30 + 96 + 96)):
        h = _reverse(0, Difficulty.ON, Doctrine.SWARM)
        h.get_reverse().update(0)
        _advance_controller(h, mins * 60)
        check(abs(h.get_reverse().base_income() - want) < 0.6, "base income at %d:00 is %s, got %s" % (mins, want, h.get_reverse().base_income()))
    rush = _reverse(0, Difficulty.ON, Doctrine.RUSH).get_reverse()
    check(abs(rush.income_rate() - RM.INCOME_BASE * Doctrine.RUSH.income) < 1e-9, "Rush earns 10%% less (%s)" % rush.income_rate())
    c = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    rc = c.get_reverse()
    check(rc.compute_price() == RM.COMPUTE_BASE_PRICE, "first SCALE COMPUTE costs %d" % RM.COMPUTE_BASE_PRICE)
    before, inc = rc.get_credits(), rc.income_rate()
    check(rc.scale_compute(), "SCALE COMPUTE affordable from the first second")
    check(abs(rc.get_credits() - (before - RM.COMPUTE_BASE_PRICE)) < 1e-6 and abs(rc.income_rate() - inc - RM.COMPUTE_STEP) < 1e-9,
          "costs %d and adds %d/s" % (RM.COMPUTE_BASE_PRICE, RM.COMPUTE_STEP))
    check(rc.compute_price() == jround(RM.COMPUTE_BASE_PRICE * RM.COMPUTE_PRICE_GROWTH), "second purchase costs more")
    rc.set_unlimited_credits(True)
    for _ in range(20):
        rc.scale_compute()
    check(rc.get_compute_level() == rc.compute_max() == RM.COMPUTE_MAX and rc.compute_problem() == "Fully scaled", "SCALE COMPUTE stops at the max")
    l = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    rl = l.get_reverse()
    e = spawn_at(l, EnemyType.SHELL_SORT, None, 0, 10)
    c0 = rl.get_credits()
    l.lose_lives(3, e)
    check(abs(rl.get_credits() - c0 - 3 * RM.LEAK_BONUS_PER_LIFE) < 1e-9 and rl.get_lives_taken() == 3 and rl.get_leaks() == 1,
          "a 3-integrity leak pays 24 credits")
    check(l.get_lives() == DefenderProfile.COMPETENT.integrity - 3, "and costs the defender 3 integrity")
    check(l.get_reward_scale() == RM.KILL_REWARD_SCALE, "reverse mode pays the listed kill rewards (%s)" % l.get_reward_scale())
    check(_reverse(0, Difficulty.ON).get_reward_scale() != Game(maps.create(0), 1).get_reward_scale(), "the normal game still triples them")
    prev = 0.0
    for d in Difficulty:
        p = DefenderProfile.of(d)
        check(p.level is d and p.income > prev, "%s -> %s funds more than the level below" % (d, p))
        prev = p.income
    for d in Difficulty:
        check(_reverse(0, d).get_cash() == Game.START_CASH * DefenderProfile.of(d).start_cash, "%s starts the AI with its profile's cash" % d)
        check(DefenderProfile.of(d).start_cash > 1, "%s: the AI opens with more than the normal $650 (a defence from 0:00)" % d)
    check(RM.track_bonus(maps.create(0)) == 1 and RM.track_bonus(maps.create(1)) > 1.2, "long tracks pay a compute bonus")
    check(RM.track_speed(maps.create(0)) == 1 and RM.track_speed(maps.create(1)) > 2, "units cross long tracks faster")


def test_difficulty_rules(check):
    n = DefenderProfile.COMPETENT
    check(n.tower_damage == 1 and n.unit_hp == 1 and n.attacker_income == 1 and n.integrity == Game.START_LIVES, "O(N) is the neutral baseline")
    prev = None
    for d in Difficulty:
        p = DefenderProfile.of(d)
        if prev is not None:
            check(p.tower_damage > prev.tower_damage, "%s: towers hit harder" % d)
            check(p.integrity > prev.integrity, "%s: more integrity" % d)
            check(p.unit_hp < prev.unit_hp, "%s: frailer units" % d)
            check(p.attacker_income < prev.attacker_income, "%s: less income" % d)
            check(p.adapt_interval < prev.adapt_interval, "%s: adapts faster" % d)
        prev = p
        tag = " [%s]" % d
        g = _reverse(0, d, Doctrine.SWARM)
        r = g.get_reverse()
        check(g.get_lives() == p.integrity and g.get_max_lives() == p.integrity, "the AI starts with its integrity" + tag)
        check(abs(g.get_global_damage_multiplier() - p.tower_damage) < 1e-9, "the AI's towers deal the mode's damage" + tag)
        check(abs(r.income_rate() - RM.INCOME_BASE * p.attacker_income) < 1e-9, "compute income starts scaled" + tag)
        c0 = r.get_credits()
        dummy = g.get_enemy_manager().spawn_scaled(EnemyType.PRIMITIVE_VARIABLE, None, 0, 0, 1, 1)
        r.on_leak(5, dummy)
        check(abs(r.get_credits() - c0 - RM.LEAK_BONUS_PER_LIFE * 5 * p.attacker_income) < 1e-9, "leak bounties scale with income" + tag)
        s = _reverse(0, d, Doctrine.RUSH)
        rs = s.get_reverse()
        rs.set_unlimited_credits(True)
        for _ in range(int(rs.unlock_at(AttackUnit.HEAP) / DT) + 1):
            rs.update(DT)
        check(rs.send(AttackUnit.HEAP, None, 1, 0) == 1, "a Heap Sort is sent" + tag)
        for _ in range(int(2 * RM.SPAWN_GAP / DT) + 1):
            rs.update(DT)
        s.get_enemy_manager().update(0)
        heap = None
        for e in s.get_enemy_manager().get_enemies():
            if e.get_type() is EnemyType.HEAP_SORT:
                heap = e
        want = max(1, jround(EnemyType.HEAP_SORT.base_hp * s.get_wave_hp_scale(EnemyType.HEAP_SORT) * p.unit_hp))
        check(heap is not None and heap.get_max_hp() == want, "units enter with the mode's health" + tag)
        s.lose_lives(10, heap)
        s.restore_lives(1000)
        check(s.get_lives() == p.integrity, "healing stops at the mode's integrity" + tag)


# ---------------------------------------------------------------- unlocks
def test_unlock_gating(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    r.set_unlimited_credits(True)
    A = AttackUnit
    open_now = [u for u in AttackUnit if r.is_unlocked(u)]
    check(len(open_now) >= 5 and A.SINGLY in open_now and A.BUBBLE in open_now,
          "a fast start: fast and 2-integrity units from 0:00 (%s)" % open_now)
    for u in AttackUnit:
        check(u.price > 0, "%s has a price" % u)
        check(r.is_unlocked(u) == (u.unlock_at <= 0), "%s unlock state at 0:00" % u)
        if u.unlock_at > 0:
            check(r.send_problem(u, None, 1).startswith("Unlocks at"), "%s refuses to send while locked" % u)
            check(r.send(u, None, 1, -1) == 0, "%s sends nothing while locked" % u)
        check(u.unlock_at <= A.BAD.unlock_at and u.unlock_at < RM.DURATION, "%s unlocks before Palantir and the run end" % u)
    max_regular = max(u.price for u in AttackUnit if not u.is_boss())
    for u in AttackUnit:
        if u.is_boss():
            check(u.price > 5 * max_regular, "%s costs far more than any regular unit" % u)
    check(A.MOAB.price < A.DDT.price < A.BFB.price < A.ZOMG.price < A.BAD.price, "boss prices rise MOAB < DDT < BFB < ZOMG < BAD")
    check(A.of(EnemyType.MERGE_RUN) is None and A.of(EnemyType.QUICK_PARTITION) is None, "split children cannot be bought")
    species = sum(1 for t in EnemyType if t.is_spawnable_species() and A.of(t) is not None)
    check(species == len(list(AttackUnit)) and species == 21, "all 16 species and 5 bosses are buyable, got %d" % species)
    last_regular = max(u.unlock_at for u in AttackUnit if not u.is_boss())
    for u in AttackUnit:
        if u.is_boss():
            check(u.unlock_at >= last_regular, "%s unlocks after the regular units" % u)
    check(A.MOAB.unlock_at <= 180 and A.BAD.unlock_at <= 7 * 60, "the schedule is compressed: MOAB by 3:00, Palantir by 7:00")
    all_m = EnumSet.all_of(Modifier)
    check(not r.effective_modifiers(A.STATIC, all_m) and r.price(A.STATIC, all_m, 1) == r.price(A.STATIC, None, 1), "locked modifiers cost nothing")
    _advance_controller(g, 30)
    check(r.is_unlocked(Modifier.REGROW) and not r.is_unlocked(Modifier.CAMO), "Regrow unlocks at 0:30")
    check(r.is_unlocked(A.SHELL) and not r.is_unlocked(A.MERGE), "0:30: the sorts open, the 1:00 tier still locked")
    _advance_controller(g, 60)
    check(r.is_unlocked(Modifier.CAMO) and r.is_unlocked(Modifier.FORTIFIED), "Camo and Fortified unlock by 1:30")
    k = Doctrine.SWARM.unit_cost
    check(r.price(A.STATIC, all_m - {Modifier.INJECTION}, 1) == jround(A.STATIC.price * 1.3 * 1.5 * 2 * k), "surcharges multiply")
    check(r.price(A.QUICK, EnumSet.of(Modifier.CAMO), 5) == 5 * jround(A.QUICK.price * 1.5 * k), "price of a batch is per unit x count")
    check(not r.effective_modifiers(A.BAD, all_m) and A.BAD.price_with(all_m) == A.BAD.price, "Palantir carries no modifiers")
    check(not r.is_unlocked(A.MOAB) and r.is_unlocked(A.HEAP), "1:30: sorters open, bosses not")
    _advance_controller(g, A.MOAB.unlock_at - 90)
    check(r.is_unlocked(A.MOAB) and not r.is_unlocked(A.BFB), "the MOAB unlocks at %s, the BFB later" % RM.clock(A.MOAB.unlock_at))
    h = _reverse(0, Difficulty.ON)
    hr = h.get_reverse()
    hr.set_unlimited_credits(True)
    check(hr.is_unlocked(AttackAbility.OVERCLOCK) and "No units" in hr.ability_problem(AttackAbility.OVERCLOCK),
          "Overclock, the cheap exploit, is open from 0:00 (it needs units on the track)")
    for a in (AttackAbility.HOTFIX, AttackAbility.ZERO_DAY):
        check(hr.ability_problem(a).startswith("Unlocks at") and a.unlock_at <= 90, "%s is locked at 0:00, open by 1:30" % a)
    t, names = hr.next_unlock()
    check(t == 30 and "Doubly Linked List" in names and "Regrow" in names, "next unlock: 0:30 (%s %s)" % (t, names))
    z = _reverse(0, Difficulty.ON)
    _advance_controller(z, RM.DURATION)
    zr = z.get_reverse()
    check(zr.is_uplink_closed() and zr.send_problem(A.PRIMITIVE, None, 1) is not None and zr.send(A.PRIMITIVE, None, 1, -1) == 0,
          "nothing can be sent once the training run is over")
    check(zr.get_rounds_done() == RM.ROUNDS and zr.next_unlock() == (None, []), "all rounds counted, everything unlocked")


# ---------------------------------------------------------------- uplink
def test_spawning(check):
    A = AttackUnit
    g = _reverse(0, Difficulty.ON, Doctrine.RUSH)
    r = g.get_reverse()
    c0 = r.get_credits()
    n = r.send(A.STATIC, None, 5, 0)
    check(n == 5 and r.get_queued() == 5 and r.get_units_bought() == 5, "5 Static Arrays queued")
    check(abs(r.get_credits() - (c0 - 5 * A.STATIC.price)) < 1e-9 and r.get_credits_spent() == 5 * A.STATIC.price, "paid 5 x price")
    affordable = int(r.get_credits() / A.DYNAMIC.price)
    check(r.send(A.DYNAMIC, None, 100, -1) == affordable and r.get_credits() < A.DYNAMIC.price, "a big order buys what the credits allow")
    _advance_controller(g, 1.0)
    check(g.get_enemy_manager().get_total_spawned() == 0, "nothing leaves the uplink during the handshake")
    check(RM.HANDSHAKE <= 5, "a short handshake (%s s)" % RM.HANDSHAKE)
    s = _reverse(0, Difficulty.ON, Doctrine.RUSH)
    rs = s.get_reverse()
    rs.send(A.STATIC, EnumSet.of(Modifier.CAMO), 4, 1)
    for _ in range(int(RM.HANDSHAKE / DT) + 1):
        rs.update(DT)
    s.get_enemy_manager().update(0)
    es = s.get_enemy_manager().get_enemies()
    check(len(es) == 1, "the first unit spawns when the handshake ends (%d)" % len(es))
    rs.update(RM.SPAWN_GAP / 2)
    s.get_enemy_manager().update(0)
    check(len(s.get_enemy_manager().get_enemies()) == 1, "the next one waits for the spawn gap")
    for _ in range(4):
        rs.update(RM.SPAWN_GAP)
    s.get_enemy_manager().update(0)
    check(len(s.get_enemy_manager().get_enemies()) == 4 and rs.get_queued() == 0 and rs.get_units_spawned() == 4, "all 4 spawned")
    for e in s.get_enemy_manager().get_enemies():
        check(e.get_type() is EnemyType.STATIC_ARRAY and e.get_route_index() == 1, "on the chosen lane")
        check(e.get_distance() < 20, "entered at the start of the track (%s)" % e.get_distance())
        check(not e.is_camo(), "a locked modifier was not applied")
    first = s.get_enemy_manager().get_enemies()[0]
    earned0 = s.get_total_cash_earned()
    kill_outright(s, first)
    check(s.get_enemy_manager().count_of_type(EnemyType.PRIMITIVE_VARIABLE) == 1, "sent units split like campaign enemies")
    check(abs(s.get_total_cash_earned() - earned0 - EnemyType.STATIC_ARRAY.reward * RM.KILL_REWARD_SCALE) < 1e-9, "listed reward paid")
    b = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    rb = b.get_reverse()
    rb.set_unlimited_credits(True)
    _advance_controller(b, A.MOAB.unlock_at)
    rb.send(A.MOAB, EnumSet.of(Modifier.FORTIFIED, Modifier.CAMO), 1, -1)
    rb.send(A.QUICK, EnumSet.of(Modifier.REGROW), 2, -1)
    for _ in range(40):
        rb.update(DT)
    b.get_enemy_manager().update(0)
    boss = None
    regrow = 0
    for e in b.get_enemy_manager().get_enemies():
        if e.is_boss():
            boss = e
        if e.is_regrow():
            regrow += 1
    check(isinstance(boss, Boss) and boss.is_fortified() and boss.is_camo(), "a Fortified Camo MOAB is a real boss")
    check(boss is not None and boss.get_max_hp() == 2 * A.MOAB.base_hp(), "Fortified doubles its (reverse-mode) HP")
    check(A.MOAB.base_hp() < EnemyType.BELLARMINE_COLLEGE_PREP.base_hp and boss.get_ability() is not None,
          "reverse-mode bosses keep their old health but bring their signature ability")
    check(regrow == 2, "Regrow applied to the Quick Sorts")
    waiting = rb.get_queued()
    added = rb.send(A.PRIMITIVE, None, 1000, -1)
    check(rb.get_queued() == rb.max_queue() == Doctrine.SWARM.max_queue and added == rb.max_queue() - waiting,
          "the queue holds at most the doctrine's limit (%d)" % rb.max_queue())
    check(rb.send_problem(A.PRIMITIVE, None, 1) == "Uplink queue full", "a full queue refuses more")
    p = _reverse(0, Difficulty.ON)
    p.get_reverse().send(A.DYNAMIC, None, 1000, -1)
    check(p.get_reverse().send_problem(A.DYNAMIC, None, 1) == "Not enough credits", "out of credits")
    lm = _reverse(1, Difficulty.ON)
    lm.get_reverse().send(A.PRIMITIVE, None, 1, -1)
    for _ in range(int(RM.HANDSHAKE / DT) + 2):
        lm.get_reverse().update(DT)
    lm.get_enemy_manager().update(0)
    fast = lm.get_enemy_manager().get_enemies()[0]
    check(abs(fast.get_speed_scale() - lm.get_reverse().get_track_speed()) < 1e-9 and fast.get_speed_scale() > 2, "track speed-up")


# ---------------------------------------------------------------- exploits
def test_exploits(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    _advance(g, 95)
    r.set_unlimited_credits(True)
    prob = r.ability_problem(AttackAbility.OVERCLOCK)
    check(prob is not None and "No units" in prob, "Overclock needs units on the track")
    e = spawn_at(g, EnemyType.MERGE_SORT, None, 0, 50)
    m0 = g.get_global_enemy_speed_multiplier()
    check(r.use_ability(AttackAbility.OVERCLOCK), "Overclock fires")
    check(abs(g.get_global_enemy_speed_multiplier() - m0 * OVERCLOCK_SPEED) < 1e-9, "Overclock: units +50% speed")
    check(r.cooldown_left(AttackAbility.OVERCLOCK) == AttackAbility.OVERCLOCK.cooldown
          and r.ability_problem(AttackAbility.OVERCLOCK).startswith("Recharging"), "then it recharges")
    for _ in range(int(AttackAbility.OVERCLOCK.duration / DT) + 2):
        r.update(DT)
    check(abs(g.get_global_enemy_speed_multiplier() - m0) < 1e-9, "the speed boost ends after 6 s")
    e.take_damage(3, g.get_time())
    hp_before = e.get_hp()
    check(r.use_ability(AttackAbility.HOTFIX) and e.get_hp() == e.get_max_hp() and hp_before < e.get_max_hp(), "Hotfix heals units to full")
    ts = g.get_tower_manager().get_player_towers()
    check(bool(ts), "the AI has towers to jam")
    check(r.use_ability(AttackAbility.ZERO_DAY), "Zero-Day fires")
    jammed = sum(1 for t in ts if t.is_surveilled())
    check(1 <= jammed <= ZERO_DAY_TARGETS, "Zero-Day jams up to 3 towers, got %d" % jammed)
    top = None
    for t in ts:
        if top is None or t.get_invested_cost() > top.get_invested_cost():
            top = t
    check(top is not None and (top.is_surveilled() or top.is_surveillance_immune()), "the most expensive tower is among them")
    check(r.get_uses(AttackAbility.ZERO_DAY) == 1 and r.get_uses(AttackAbility.HOTFIX) == 1, "uses counted")
    for d in Doctrine:
        c = _reverse(0, Difficulty.ON, d)
        rc = c.get_reverse()
        spawn_at(c, EnemyType.PRIMITIVE_VARIABLE, None, 0, 50)
        before = rc.get_credits()
        cost = rc.ability_cost(AttackAbility.OVERCLOCK)
        check(rc.use_ability(AttackAbility.OVERCLOCK) and abs(rc.get_credits() - (before - cost)) < 1e-9,
              "%s: Overclock at 0:00 costs %d" % (d, cost))
        check(abs(rc.cooldown_left(AttackAbility.OVERCLOCK) - AttackAbility.OVERCLOCK.cooldown * d.exploit_cooldown) < 1e-9,
              "%s: its cooldown follows the doctrine" % d)
    check(AttackAbility.OVERCLOCK.cost <= 150, "an early, cheap exploit (%d)" % AttackAbility.OVERCLOCK.cost)


# ---------------------------------------------------------------- rounds, objectives, overtime
def test_rounds_and_objectives(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    check(RM.ROUNDS * RM.ROUND_SECONDS == RM.DURATION and 8 * 60 <= RM.DURATION <= 10 * 60, "a short match: %s" % RM.clock(RM.DURATION))
    goals = [r.round_goal(i) for i in range(RM.ROUNDS)]
    check(goals == [4, 5, 6, 8, 10, 12, 14, 16], "O(N) round objectives escalate %s" % goals)
    check(r.get_round() == 1 and r.get_round_index() == 0 and abs(r.round_time_left() - 60) < 1e-9, "round 1 of 8 at 0:00")
    reward = r.objective_reward()
    check(reward == jround(RM.OBJECTIVE_SECONDS * r.income_rate()), "the objective pays %d s of income (%d)" % (RM.OBJECTIVE_SECONDS, reward))
    _leak(g, 3)
    check(r.round_taken() == 3 and not r.objective_met(), "3 of 4: not yet")
    c0 = r.get_credits()
    _leak(g, 2)
    check(r.objective_met() and r.round_taken() == 5, "5 of 4: objective met")
    check(abs(r.get_credits() - c0 - 2 * RM.LEAK_BONUS_PER_LIFE - r.get_objective_bonus()) < 1e-6 and r.get_objective_bonus() > 0,
          "the bonus is paid at once (%d)" % r.get_objective_bonus())
    check(g.get_banner() is not None and "OBJECTIVE COMPLETE" in g.get_banner(), "and announced (%s)" % g.get_banner())
    bonus = r.get_objective_bonus()
    _leak(g, 10)
    check(r.get_objective_bonus() == bonus, "an objective pays once per round")
    _advance_controller(g, 60)
    check(r.get_round() == 2 and r.get_rounds_done() == 1 and r.round_taken() == 0, "round 2 starts from zero")
    check(any("Round 1 won" in f.text for f in r.get_feed()) and any("Round 2: take 5" in f.text for f in r.get_feed()),
          "the feed reports the round and the next objective")
    hist = r.get_round_history()
    check(hist[0] == (15, 4, True) and hist[1] == (0, 5, False) and len(hist) == 2, "round history %s" % hist)
    check(r.get_objectives_met() == 1, "one objective met")
    k = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    kr = k.get_reverse()
    _leak(k, 99)
    _leak(k, 30)
    check(kr.round_taken() == 100 and kr.get_lives_taken() == 100, "overkill is not counted (%d)" % kr.round_taken())
    h = _reverse(0, Difficulty.ON, Doctrine.HEIST)
    hr = h.get_reverse()
    check(hr.objective_reward() == jround(RM.OBJECTIVE_SECONDS * hr.income_rate() * Doctrine.HEIST.objective_pay), "Heist objectives pay 50% more")
    e = spawn_at(h, EnemyType.SHELL_SORT, None, 0, 10)
    c0 = hr.get_credits()
    h.lose_lives(3, e)
    check(abs(hr.get_credits() - c0 - 3 * RM.LEAK_BONUS_PER_LIFE * Doctrine.HEIST.leak_pay) < 1e-9, "Heist leaks pay double")
    x = _reverse(0, Difficulty.ONN)
    check([x.get_reverse().round_goal(i) for i in range(2)] == [8, 10], "goals scale with the AI's integrity")


def test_overtime(check):
    held = _reverse(0, Difficulty.ON)
    r = held.get_reverse()
    _advance_controller(held, RM.DURATION - 1)
    check(held.get_state() is State.PLAYING and not r.is_uplink_closed() and r.is_final_round(), "the final round runs to 8:00")
    _advance(held, 2)
    check(held.get_state() is State.VICTORY and not r.is_overtime(), "an AI above the line holds at 8:00 (no overtime)")
    o = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    ro = o.get_reverse()
    check(ro.overtime_line() == 25, "the overtime line is 25% of the integrity")
    _advance_controller(o, RM.DURATION - 30)
    _leak(o, 75)
    check(any("critical" in f.text.lower() for f in ro.get_feed()), "the feed warns when the AI is critical")
    ro.set_unlimited_credits(True)
    check(ro.use_ability(AttackAbility.ZERO_DAY), "a Zero-Day at 7:30")
    inc = ro.income_rate()
    _advance_controller(o, 30.5)
    check(ro.is_overtime() and not ro.is_uplink_closed() and o.get_state() is State.PLAYING, "AI at 25 at 8:00: sudden-death overtime")
    check(ro.get_round() == RM.ROUNDS + 1 and ro.round_goal() == 0, "the overtime is the ninth slot, without an objective")
    check(ro.income_rate() > 1.8 * inc, "overtime doubles the income (%s vs %s)" % (ro.income_rate(), inc))
    check(ro.cooldown_left(AttackAbility.ZERO_DAY) == 0, "and recharges every exploit")
    check(ro.send(AttackUnit.PRIMITIVE, None, 1, -1) == 1, "the uplink stays open")
    check(any("SUDDEN-DEATH" in (f.text.upper()) for f in ro.get_feed()) and "OVERTIME" in (o.get_banner() or ""), "announced")
    _advance_controller(o, RM.OVERTIME)
    check(ro.is_uplink_closed(), "it closes after %s" % RM.clock(RM.OVERTIME))
    _advance(o, RM.DRAIN + 2)
    check(o.get_state() is State.VICTORY and ro.get_elapsed() <= RM.DURATION + RM.OVERTIME + RM.DRAIN + 1,
          "the AI held the overtime; the match ends by %s" % RM.clock(ro.get_elapsed()))
    w = _reverse(0, Difficulty.ON)
    rw = w.get_reverse()
    _advance_controller(w, RM.DURATION - 5)
    _leak(w, 80)
    _advance_controller(w, 10)
    check(rw.is_overtime(), "overtime again")
    _leak(w, 20)
    _advance(w, 3)
    check(w.get_state() is State.DEFEAT and rw.attacker_won(), "a breach in overtime wins")
    t, sub, kind = __import__("lindefense.ui.attack_panel", fromlist=["AttackPanel"]).AttackPanel.end_texts(w)
    check(kind == "win" and "overtime" in sub, sub)


# ---------------------------------------------------------------- doctrines
def test_doctrines(check):
    A = AttackUnit
    ds = list(Doctrine)
    check([d.display_name for d in ds] == ["Rush", "Swarm", "Heist"], "three doctrines")
    for d in ds:
        check(len(d.perks) == 3 and d.drawback and d.tagline, "%s has three perks, a drawback and a tagline" % d)
    rush = _reverse(0, Difficulty.ON, Doctrine.RUSH).get_reverse()
    swarm = _reverse(0, Difficulty.ON, Doctrine.SWARM).get_reverse()
    heist = _reverse(0, Difficulty.ON, Doctrine.HEIST).get_reverse()
    check(rush.unlock_at(A.MOAB) == A.MOAB.unlock_at - 30 and rush.unlock_at(A.SHELL) == A.SHELL.unlock_at, "Rush: bosses 30 s earlier")
    check(rush.ability_cost(AttackAbility.ZERO_DAY) < swarm.ability_cost(AttackAbility.ZERO_DAY)
          and rush.ability_cooldown(AttackAbility.ZERO_DAY) < swarm.ability_cooldown(AttackAbility.ZERO_DAY), "Rush: cheaper, faster exploits")
    check(swarm.price(A.STATIC, None, 1) == jround(A.STATIC.price * 0.75) and swarm.price(A.MOAB, None, 1) == jround(A.MOAB.price * 1.1),
          "Swarm: regular units 25% cheaper, bosses 10% dearer")
    check(swarm.unit_hp_scale(EnemyType.STATIC_ARRAY) == 1.25 * rush.unit_hp_scale(EnemyType.STATIC_ARRAY)
          and swarm.unit_hp_scale(EnemyType.BELLARMINE_COLLEGE_PREP) == rush.unit_hp_scale(EnemyType.BELLARMINE_COLLEGE_PREP),
          "Swarm: regular units +25% health, bosses unchanged")
    check(Doctrine.SWARM.spawn_gap < Doctrine.RUSH.spawn_gap and swarm.max_queue() > rush.max_queue(), "Swarm: a faster, deeper uplink")
    check(heist.compute_price() < rush.compute_price() and heist.compute_max() > rush.compute_max(), "Heist: cheaper, deeper SCALE COMPUTE")
    check(heist.leak_pay(10) == 2 * rush.leak_pay(10), "Heist: leaks pay double")
    g = ReverseMatch.create(2, 5, Difficulty.ON2, Doctrine.HEIST)
    g2 = ReverseMatch.restart(g)
    check(g2.get_reverse().get_doctrine() is Doctrine.HEIST and g2.get_reverse().get_profile() is DefenderProfile.EXPERT,
          "RETRY keeps the doctrine and the AI")
    check(units.selected_doctrine() is Doctrine.RUSH, "the briefing pre-selects Rush")
    units.select_doctrine(Doctrine.SWARM)
    check(units.selected_doctrine() is Doctrine.SWARM, "and remembers the pick for the session")


# ---------------------------------------------------------------- the AI adapts; matchup intel
def test_ai_adapts(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    r.set_unlimited_credits(True)
    check(g.get_reverse().get_ai().get_options().counter is not None, "the reverse AI takes counter orders")
    check(DefenderAI(Game(maps.create(0), 1), Options()).get_options().counter is None, "the campaign / balance AI does not")
    t = 0.0
    while t < RM.ADAPT_START + 1:
        if int(t * 2) % 4 == 0:
            r.send(AttackUnit.PRIMITIVE, None, 5, -1)
        _advance(g, 0.5)
        t += 0.5
    ads = r.get_adaptations()
    check(len(ads) >= 1 and ads[0].role is Role.SWARM and ads[0].tower is T.GEMINI, "a swarm of Primitives: the AI adapts with Gemini (%s)"
          % [(a.role, a.tower) for a in ads])
    check(any(f.text.startswith("AI adapts") for f in r.get_feed()), "announced in the feed")
    g.add_cash(6000, None)
    _advance(g, 20)
    a = ads[0]
    check(a.done_at > 0 and sum(1 for x in g.get_tower_manager().get_player_towers() if x.get_type() is T.GEMINI and x.get_tier() >= a.tier) >= a.copies,
          "and builds it (%d Gemini at tier %d)" % (a.copies, a.tier))
    check(r.role_status(Role.SWARM) == "countered" and r.unit_status(AttackUnit.PRIMITIVE) == "countered", "the swarm cards read COUNTERED")
    check(r.edge_reason(AttackUnit.STATIC).startswith("COUNTERED") and "Gemini" in r.edge_reason(AttackUnit.STATIC), r.edge_reason(AttackUnit.STATIC))
    b = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    br = b.get_reverse()
    for x in b.get_tower_manager().get_player_towers():
        check(x.get_type() is not T.DEEPSEEK, "no railgun yet")
    spawn_at(b, EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 20)
    _advance(b, 0.5)
    ba = br.get_adaptation()
    check(ba is not None and ba.role is Role.BOSS and ba.tower is T.DEEPSEEK, "a boss on the track: the AI rushes a DeepSeek")
    x = _reverse(0, Difficulty.ON2, Doctrine.SWARM)
    xr = x.get_reverse()
    _advance_controller(x, AttackUnit.MOAB.unlock_at - RM.BOSS_NOTICE + 1)
    check(any(a.role is Role.BOSS for a in xr.get_adaptations()) or
          any(t.get_type() is T.DEEPSEEK for t in x.get_tower_manager().get_player_towers()),
          "the Expert braces for bosses before the MOAB unlocks")


def test_matchup_intel(check):
    g = _reverse(0, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    check(all(r.role_status(x) == "edge" for x in Role), "0:00, no towers: every role has an edge")
    _advance(g, 1)
    check(any(t.get_type() is T.GEMINI for t in g.get_tower_manager().get_player_towers()), "the AI opens with Gemini")
    check(r.role_status(Role.SWARM) is None and r.unit_status(AttackUnit.PRIMITIVE) is None, "Gemini answers the swarm")
    check(r.role_status(Role.BOSS) == "edge" and r.unit_status(AttackUnit.MOAB) == "edge", "no DeepSeek: bosses have an edge")
    check(r.edge_reason(AttackUnit.MOAB) == "EDGE: no railgun (DeepSeek) yet.", r.edge_reason(AttackUnit.MOAB))
    check(r.role_status(Role.CAMO) == "edge" and r.unit_status(AttackUnit.DDT) == "edge", "blind AI: the DDT (innate camo) has an edge")
    check(r.unit_status(AttackUnit.PRIMITIVE, EnumSet.of(Modifier.CAMO)) is None, "camo before it unlocks changes nothing")
    _advance_controller(g, 60)
    if r.role_status(Role.CAMO) == "edge":
        check(r.unit_status(AttackUnit.PRIMITIVE, EnumSet.of(Modifier.CAMO)) == "edge"
              and "camo" in r.edge_reason(AttackUnit.PRIMITIVE, EnumSet.of(Modifier.CAMO)), "a camo Primitive against a blind AI")
    two = _reverse(0, Difficulty.ON)
    two.get_reverse().update(0)
    _advance(two, 20)
    tr = two.get_reverse()
    cover = tr.lane_cover()
    check(len(cover) == 2 and tr.weakest_lane() in (0, 1) and cover[tr.weakest_lane()] == min(cover), "two lanes, the weakest found (%s)" % (cover,))
    check(all(tr.lane_label(i) in ("OPEN", "EVEN", "HEAVY") for i in range(2)) and tr.lane_label(5) is None, "lane labels")
    one = _reverse(1, Difficulty.ON).get_reverse()
    check(one.lane_cover() == () and one.weakest_lane() == -1 and one.lane_label(0) is None, "one lane: no lane intel")


# ---------------------------------------------------------------- the defender AI
@pytest.mark.slow
def test_defender_plays_legally(check):
    for d in (Difficulty.O1, Difficulty.ON2):
        g = _reverse(0 if d is Difficulty.O1 else 2, d)
        r = g.get_reverse()
        bot = AttackerBot(r, Style.PASSIVE if d is Difficulty.O1 else Style.SPAM)
        min_cash = float("inf")
        i = 0
        while i < int((RM.DURATION - 5) / DT) and g.get_state() is State.PLAYING:
            bot.tick(DT)
            g.step(DT)
            g.get_events().clear()
            min_cash = min(min_cash, g.get_cash())
            i += 1
        tag = " [%s]" % r.get_profile()
        ts = g.get_tower_manager().get_player_towers()
        check(g.get_state() is State.PLAYING, "the AI survives the training run" + tag)
        check(len(ts) >= 8, "the AI built a defence (%d towers)%s" % (len(ts), tag))
        check(r.get_ai().get_action_count() > len(ts), "and upgraded it" + tag)
        check(min_cash >= 0, "never spent money it did not have" + tag)
        upgraded = heroes = 0
        hero_types = set()
        invested = 0.0
        for t in ts:
            if t.get_tier() > 0:
                upgraded += 1
            if t.get_type().is_hero():
                heroes += 1
                check(t.get_type() not in hero_types, "one copy of %s%s" % (t.get_type(), tag))
                hero_types.add(t.get_type())
                check(g.is_hero_unlocked(t.get_type()), "%s was unlocked in the Hero Store first%s" % (t.get_type(), tag))
            check(g.get_map().is_buildable(t.get_position(), t.get_radius()), "%s stands on buildable ground%s" % (t.get_type(), tag))
            for o in ts:
                if o is not t:
                    check(o.get_position().dist(t.get_position()) >= o.get_radius() + t.get_radius() - 1e-6, "%s does not overlap%s" % (t.get_type(), tag))
            if not t.is_ability_locked() and catalog.ability_needs_unlock(t.get_type()):
                check(t.is_maxed(), "%s had its ability unlocked only at max tier%s" % (t.get_type(), tag))
            invested += t.get_invested_cost()
            if t.get_type().is_hero():
                invested += catalog.get(t.get_type()).unlock_cost
        check(upgraded >= 4, "upgraded several towers (%d)%s" % (upgraded, tag))
        check(heroes <= g.get_hero_limit() and g.get_tower_manager().heroes_deployed_this_match() <= len(T.heroes()), "hero cap respected" + tag)
        check(g.get_hero_limit() == MAX_HEROES_PER_GAME, "the normal hero cap" + tag)
        spent = Game.START_CASH + g.get_total_cash_earned() - g.get_cash()   # the opening budget counts as earned
        check(abs(invested - spent) < 2, "every dollar it spent is in its towers (%d vs %d)%s" % (invested, spent, tag))
        check(r.get_last_ai_action() is not None and r.get_last_ai_action().text.startswith("AI "), "the feed reports the AI's actions" + tag)
        if d is Difficulty.ON2:
            check(heroes >= 2, "the Expert deploys heroes (%d)" % heroes)
    x = _reverse(0, Difficulty.ON2)
    AttackerBot.play(x, Style.PASSIVE)
    unlocks = 0
    for t in x.get_tower_manager().get_player_towers():
        if catalog.ability_needs_unlock(t.get_type()) and not t.is_ability_locked():
            unlocks += 1
            check(t.is_maxed(), "%s maxed before its unlock" % t.get_type())
    check(unlocks >= 1, "the Expert unlocked abilities (%d)" % unlocks)
    feed = x.get_reverse().get_feed()
    unlock_feed = sum(1 for fe in feed if fe.action is Action.ABILITY_UNLOCK)
    check(unlock_feed >= 1 or len(feed) == RM.FEED_SIZE, "unlocks show in the feed")
    n = _reverse(0, Difficulty.ON)
    check(not n.get_hero_collection().is_unlocked(T.MR_LINDEMANN) and not n.get_hero_collection().unlocked(), "the AI starts with no heroes")


# ---------------------------------------------------------------- win / loss
def test_win_and_loss(check):
    g = _reverse(0, Difficulty.ON)
    e = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    g.lose_lives(g.get_max_lives(), e)
    _advance(g, 3)
    check(g.get_state() is State.DEFEAT and g.get_reverse().attacker_won() and not g.get_reverse().defender_held(), "integrity 0 = attacker wins")
    p = _reverse(0, Difficulty.ON)
    _advance(p, RM.DURATION - 1)
    check(p.get_state() is State.PLAYING and not p.get_reverse().is_uplink_closed(), "still running a second before the end")
    _advance(p, 2)
    check(p.get_state() is State.VICTORY and p.get_reverse().defender_held() and not p.get_reverse().attacker_won(), "the defender holds")
    check(p.get_reverse().get_elapsed() < RM.DURATION + 1, "no drain with an empty track")
    o = _reverse(1, Difficulty.O1)
    ro = o.get_reverse()
    _advance(o, RM.DURATION - 3)
    ro.set_unlimited_credits(True)
    ro.send(AttackUnit.BAD, None, 1, -1)
    _advance(o, 6)
    check(ro.is_uplink_closed() and o.get_state() is State.PLAYING, "the drain runs while Palantir walks")
    _advance(o, RM.DRAIN + 2)
    check(o.get_state() is not State.PLAYING, "the drain is capped")
    check(ro.get_elapsed() <= RM.DURATION + RM.DRAIN + 2.5, "ended by " + RM.clock(ro.get_elapsed()))
    k = _reverse(0, Difficulty.ON)
    pal = spawn_at(k, EnemyType.PALANTIR, None, 0, 100)
    kill_outright(k, pal)
    _advance(k, 6)
    check(k.get_state() is State.PLAYING and not k.is_victory_sequence_active(), "killing the attacker's Palantir does not end the match")
    q = _reverse(0, Difficulty.ON)
    qe = spawn_at(q, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    q.lose_lives(q.get_max_lives(), qe)
    q.declare_defender_victory("x")
    _advance(q, 3)
    check(q.get_state() is State.DEFEAT, "a breach beats the timer on the same tick")
    r0 = _reverse(2, Difficulty.ON2)
    r0.get_reverse().set_unlimited_credits(True)
    _advance(r0, 30)
    r1 = ReverseMatch.restart(r0)
    check(r1 is not r0 and r1.is_reverse() and r1.get_reverse().get_profile() is DefenderProfile.EXPERT
          and r1.get_map().get_name() == r0.get_map().get_name(), "restart: same map and AI")
    check(r1.get_reverse().get_elapsed() == 0 and r1.get_reverse().has_unlimited_credits() and not r1.get_tower_manager().get_towers(),
          "restart: fresh clock and board, admin credits kept")
    normal = Game(maps.create(0), 5)
    check(not normal.is_reverse() and normal.get_reverse() is None, "the normal game has no reverse controller")


def test_determinism(check):
    """Same map, seed, level and doctrine: the same match, step for step (the AI, the bot and the adaptations)."""
    outs = []
    for _ in range(2):
        g = ReverseMatch.create(3, 99, Difficulty.ON, Doctrine.SWARM)
        bot = AttackerBot(g.get_reverse(), Style.REASONABLE)
        for _ in range(int(100 / DT)):
            bot.tick(DT)
            g.step(DT)
            g.get_events().clear()
        r = g.get_reverse()
        outs.append((g.get_lives(), round(g.get_cash(), 6), round(r.get_credits(), 6), r.get_units_bought(),
                     [(a.role.name, a.tower.name, a.since) for a in r.get_adaptations()],
                     [(t.get_type().name, t.get_tier(), t.get_position().x, t.get_position().y) for t in g.get_tower_manager().get_towers()]))
    check(outs[0] == outs[1], "two runs agree")


# ---------------------------------------------------------------- whole matches
@pytest.mark.slow
def test_whole_matches(check):
    for m in (0, 1, 5):
        win = AttackerBot.play(m, 42, Difficulty.O1, Style.REASONABLE)
        check(win.attacker_won and win.time < RM.DURATION, "a scripted attacker beats the Novice AI on map %d (%r)" % (m, win))
        idle = AttackerBot.play(m, 42, Difficulty.O1, Style.PASSIVE)
        check(not idle.attacker_won and idle.defender_lives == DefenderProfile.NOVICE.integrity and idle.time >= RM.DURATION,
              "a do-nothing attacker loses on map %d (%r)" % (m, idle))
    for d in Doctrine:
        spam = AttackerBot.play(0, 42, Difficulty.ON, Style.SPAM, doctrine=d)
        check(not spam.attacker_won, "flooding Primitive Variables does not beat the Competent AI with %s (%r)" % (d, spam))
        ok = AttackerBot.play(0, 42, Difficulty.ON, Style.REASONABLE, doctrine=d)
        check(ok.attacker_won, "every doctrine can beat the Competent AI (%s: %r)" % (d, ok))
    hard = AttackerBot.play(1, 42, Difficulty.ONN, Style.REASONABLE)
    easy = AttackerBot.play(1, 42, Difficulty.O1, Style.REASONABLE)
    check(not hard.attacker_won or hard.time > easy.time, "the Superintelligence lasts longer (%r vs %r)" % (hard, easy))
    check(hard.defender_earned > easy.defender_earned, "and is funded better")


@pytest.mark.slow
def test_shared_defender_ai(check):
    res = auto_player.run(0, 1234, Difficulty.O1, 12, 999, False, False)
    check(res.completed == 12 and res.lives == Game.START_LIVES, "AutoPlayer clears 12 waves flawlessly (%d, lives %d)" % (res.completed, res.lives))
    check(res.towers >= 4, "and builds a defence (%d towers)" % res.towers)
    mixed = auto_player.run(0, 1234, Difficulty.O1, 40, 999, False, False, True)
    n = len(mixed.game.get_hero_collection().unlocked())
    check(n <= mixed.game.get_hero_limit(), "the mixed plan buys at most the hero cap (%d)" % n)


# ---------------------------------------------------------------- screens
@pytest.fixture
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


def _labels(c, out=None):
    out = [] if out is None else out
    for o in c:
        if hasattr(o, "get_label"):
            out.append(o)
        if hasattr(o, "_contents"):
            _labels(o, out)
    return out


def test_attack_panel_round_box_and_tags(check, _prefs_dir):
    from lindefense.ui.attack_panel import AttackPanel
    from lindefense.ui.cyber import Cyber
    from lindefense.ui.game_screen import GameScreen
    g = ReverseMatch.create(0, 42, Difficulty.ON, Doctrine.SWARM)
    r = g.get_reverse()
    s = GameScreen(None, g)
    s.frame(0.02)
    ap = s.attack
    texts = [l.get_label() for l in _labels(ap)]
    check("SWARM DOCTRINE" in texts, "the panel names the doctrine")
    check(ap.round_label.get_label() == "Round 1 / 8" and ap.round_clock.get_label() == "1:00", "round 1, 1:00 left")
    check(ap.objective.get_label().startswith("Breach 4 this round for +") and ap.objective_count.get_label() == "0 / 4", ap.objective.get_label())
    check(len(ap.round_bars) == RM.ROUNDS and ap.ot_bar.get_value() == 0, "a round track of 8 and an unlit overtime slot")
    cards = {c.unit: c for c in ap.cards}
    check(cards[AttackUnit.SINGLY].tag.get_label() == "EDGE", "0:00: no slows yet, the Singly List card shows EDGE")
    check(cards[AttackUnit.MOAB].tag.get_label() == "", "a locked card shows no tag")
    check(cards[AttackUnit.SINGLY].tag.get_color() == Cyber.good(), "EDGE in the good colour")
    _leak(g, 4)
    s.frame(0.02)
    check(ap.objective.get_label() == "Objective complete: round won" and ap.round_bars[0].get_value() == 1, "objective met: the slot fills")
    r._adaptations.append(RM.Adaptation(Role.SPEED, T.CLAUDE, 1, 2, 0.0))
    r._adaptations[-1].done_at = r.get_elapsed()
    s.frame(0.02)
    check(cards[AttackUnit.SINGLY].tag.get_label() == "COUNTERED" and cards[AttackUnit.SINGLY].tag.get_color() == Cyber.bad(),
          "after the AI's counter: COUNTERED in the bad colour")
    for c in ap.cards:
        check(c.price.get_x() + c.price.get_width() <= c.button.get_x() + c.button.w - 2, "%s: the price fits its card" % c.unit)
        check(c.name.get_x() + c.name.get_width() <= c.button.get_x() + c.button.w, "%s: the name fits its card" % c.unit)
    r.set_unlimited_credits(True)
    ap.qty_index = 3
    r._elapsed = 400.0
    s.frame(0.02)
    for c in ap.cards:
        check(c.price.get_x() + c.price.get_width() <= c.button.get_x() + c.button.w - 2,
              "%s: %r fits its card" % (c.unit, c.price.get_label()))
    lane = ap.lane_text()
    check(lane.startswith("ALL"), "the lane button starts on ALL (%s)" % lane)
    ap.cycle_lane()
    check(ap.lane_text().startswith("LANE 1"), ap.lane_text())
    check(AttackPanel.INFO_Y + 150 < 1000 and AttackPanel.CARD_Y > AttackPanel.ROUND_Y + AttackPanel.ROUND_H, "the round box sits above the cards")


def test_hud_breach_meter_and_round(check, _prefs_dir):
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui import display_settings
    g = ReverseMatch.create(0, 42, Difficulty.ON, Doctrine.RUSH)
    s = GameScreen(None, g)
    s.frame(0.02)
    hud = s.hud
    check(hud.wave_chip.value.get_label() == "R1 / 8", "the wave chip shows the round (%s)" % hud.wave_chip.value.get_label())
    check(hud.breach_bar is not None and hud.breach_bar.get_value() == 1, "the breach meter starts full")
    _leak(g, 40)
    s.frame(0.02)
    check(abs(hud.breach_bar.get_value() - 0.6) < 1e-9, "and drains with the AI's integrity (%s)" % hud.breach_bar.get_value())
    r = g.get_reverse()
    r._elapsed = RM.DURATION - 30
    r._rounds_done = RM.ROUNDS - 1
    st = display_settings.DisplaySettings.get()
    old = st.reduced_motion
    try:
        st.reduced_motion = True
        cols = set()
        for k in range(6):
            hud.time += 0.13
            hud.update_reverse()
            cols.add(str(hud.timer_chip.value.get_color()))
        check(len(cols) == 1, "REDUCED MOTION: the final-round timer does not pulse (%s)" % cols)
    finally:
        st.reduced_motion = old


def test_end_screen_summary(check, _prefs_dir):
    from lindefense.ui.attack_panel import AttackPanel
    from lindefense.ui.game_screen import GameScreen
    g = ReverseMatch.create(0, 42, Difficulty.ON, Doctrine.HEIST)
    s = GameScreen(None, g)
    s.frame(0.02)
    _leak(g, 5)
    g.get_reverse().update(60.0)
    _leak(g, g.get_lives())
    for _ in range(200):
        if g.get_state() is not State.PLAYING:
            break
        g.step(DT)
    s.frame(0.02)
    s.frame(0.02)
    check(g.get_state() is State.DEFEAT, "breached")
    texts = [l.get_label() for l in _labels(s.overlay)]
    check("BREACH" in texts, "the end panel says BREACH")
    check(any("Heist doctrine" in t for t in texts), "and names the doctrine")
    check("R1" in texts and "R8" in texts and "-5" in texts, "the round strip shows each round's breach (%s)" % [t for t in texts if t.startswith(("R", "-"))])
    stats = AttackPanel.end_stats(g)
    check([x[0] for x in stats] == ["integrity taken", "objectives", "units sent", "match time"], "four summary chips")
    check(stats[0][1] == "100 / 100" and stats[1][1] == "2 / 8", "integrity and objectives (%s)" % stats)
    t, sub, kind = AttackPanel.end_texts(g)
    check(t == "BREACH" and kind == "win" and "Heist" in sub, sub)
    for o in _labels(s.overlay):
        if o.is_visible() and o.get_label():
            check(o.get_x() >= 0 and o.get_x() + o.get_width() <= 1600, "%r stays inside the layout" % o.get_label())


def test_briefing_doctrine_picker(check, _prefs_dir):
    from lindefense.ui.jawt import KeyEvent
    from lindefense.ui.map_select_screen import MapSelectScreen

    class _App:
        def __init__(self):
            self.calls = []

        def start_reverse(self, idx):
            self.calls.append(("reverse", idx, units.selected_doctrine()))

        def start_run(self, setup):
            self.calls.append(("run",))

        def show_menu(self):
            self.calls.append(("menu",))

    app = _App()
    m = MapSelectScreen(app)
    m.open_reverse_briefing(1)
    p = m.doctrine_picker
    check(p is not None and len(p.buttons()) == 3, "the reverse briefing shows three doctrine cards")
    check([b.is_selected() for b in p.buttons()] == [True, False, False], "Rush is selected")
    b = p.buttons()[1]
    m.mouse_pressed(b.get_x() + b.w / 2, b.get_y() + b.h / 2)
    check(units.selected_doctrine() is Doctrine.SWARM and [x.is_selected() for x in p.buttons()] == [False, True, False], "a click picks Swarm")
    m.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_3, "3"))
    check(units.selected_doctrine() is Doctrine.HEIST, "key 3 picks Heist")
    texts = [l.get_label() for l in _labels(m.briefing)]
    for d in Doctrine:
        check(d.display_name.upper() in texts and all(("+  " + x) in texts for x in d.perks) and ("-  " + d.drawback) in texts,
              "%s card lists its perks and its cost" % d)
    for o in _labels(p):
        check(o.get_x() + o.get_width() <= MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_W - MapSelectScreen.BRIEF_PAD + 1,
              "%r stays inside the briefing" % o.get_label())
    for btn in p.buttons():
        check(btn.get_y() + btn.h < MapSelectScreen.briefing_deploy_rect()[1], "the cards end above the ATTACK row")
    m.key_pressed(KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_ENTER, "\r"))
    check(app.calls == [("reverse", 1, Doctrine.HEIST)], "Enter attacks with the picked doctrine (%s)" % app.calls)
    m.open_briefing(1)
    check(m.doctrine_picker is None, "the defend briefing has no doctrine cards")


def test_app_starts_the_picked_doctrine(check, monkeypatch, _prefs_dir):
    from lindefense.app import LindefenseApp
    from lindefense.ui.scaled_layer import ScaledLayer
    monkeypatch.setattr(LindefenseApp, "_settle_heap", staticmethod(lambda: None))
    app = LindefenseApp.__new__(LindefenseApp)
    app.root = ScaledLayer()
    app.menu = app.map_select = app.game_screen = None
    app.demo = app.window_grab = app.autosave = None
    app._errors = {}
    app.running = True
    app.px_w, app.px_h = 1600, 1000
    units.select_doctrine(Doctrine.SWARM)
    app.start_reverse(0)
    g = app.get_game()
    check(g.is_reverse() and g.get_reverse().get_doctrine() is Doctrine.SWARM, "ATTACK starts a Swarm match")
    app.restart_level()
    check(app.get_game() is not g and app.get_game().get_reverse().get_doctrine() is Doctrine.SWARM, "RETRY keeps it")
