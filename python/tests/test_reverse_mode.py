"""Reverse mode ("Adversarial Training"): port of ReverseModeTests.java. uiRouting (needs the in-game screen) is ported
with the pygame UI."""
import pytest

from kit import kill_outright, spawn_at
from lindefense.ai import reverse_match as RM
from lindefense.ai.defender_ai import Action
from lindefense.ai.reverse_match import AttackerBot, ReverseMatch, Style
from lindefense.ai.units import OVERCLOCK_SPEED, ZERO_DAY_TARGETS, AttackAbility, AttackUnit, DefenderProfile
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


def _reverse(m, d):
    return ReverseMatch.create(m, 42, d)


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


# ---------------------------------------------------------------- economy
def test_economy(check):
    g = _reverse(0, Difficulty.ON)
    r = g.get_reverse()
    check(g.is_reverse() and r is not None and r.get_game() is g, "reverse game carries its controller")
    check(g.get_difficulty() is Difficulty.O1, "the game itself runs with base rules")
    check(r.get_profile() is DefenderProfile.COMPETENT and r.get_level() is Difficulty.ON, "O(N) picks the Competent AI")
    check(r.get_credits() == RM.START_CREDITS, "attacker starts with %d credits" % RM.START_CREDITS)
    check(g.get_cash() == Game.START_CASH and g.get_lives() == Game.START_LIVES, "defender starts with the normal cash and integrity")
    i0 = r.income_rate()
    check(abs(i0 - 12) < 1e-9, "income starts at 12/s, got %s" % i0)
    _advance(g, 60)
    expected = RM.START_CREDITS + 12 * 60 + 5 * 60 + 0.5 * 60 / 3.0
    check(abs(r.get_credits() - expected) < 3, "one minute of income: about %d, got %d" % (expected, r.get_credits()))
    check(r.income_rate() > i0 + 9, "income grows over the match (%s/s)" % r.income_rate())
    check(r.get_defender_funding() > 0 and g.get_total_cash_earned() > Game.START_CASH, "the defender is funded over time")
    check(abs(r.defender_funding_rate() - r.base_income() * RM.FUND_RATIO * DefenderProfile.COMPETENT.income) < 1e-9, "funding follows the curve")
    for mins, want in ((5, 12 + 50 + 12.5), (10, 12 + 100 + 50), (15, 12 + 150 + 112.5)):
        h = _reverse(0, Difficulty.ON)
        h.get_reverse().update(0)
        _advance_controller(h, mins * 60)
        check(abs(h.get_reverse().base_income() - want) < 0.6, "base income at %d:00 is %s, got %s" % (mins, want, h.get_reverse().base_income()))
    c = _reverse(0, Difficulty.ON)
    rc = c.get_reverse()
    check(rc.compute_price() == RM.COMPUTE_BASE_PRICE, "first SCALE COMPUTE costs %d" % RM.COMPUTE_BASE_PRICE)
    check(rc.compute_problem() is not None and not rc.scale_compute(), "cannot scale compute without the credits")
    _advance(c, 10)
    before, inc = rc.get_credits(), rc.income_rate()
    check(rc.scale_compute(), "SCALE COMPUTE once affordable")
    check(abs(rc.get_credits() - (before - 300)) < 1e-6 and abs(rc.income_rate() - inc - RM.COMPUTE_STEP) < 1e-9, "costs 300 and adds 4/s")
    check(rc.compute_price() == jround(300 * RM.COMPUTE_PRICE_GROWTH), "second purchase costs more")
    rc.set_unlimited_credits(True)
    for _ in range(20):
        rc.scale_compute()
    check(rc.get_compute_level() == RM.COMPUTE_MAX and rc.compute_problem() == "Fully scaled", "SCALE COMPUTE stops at the max")
    l = _reverse(0, Difficulty.ON)
    rl = l.get_reverse()
    e = spawn_at(l, EnemyType.SHELL_SORT, None, 0, 10)
    c0 = rl.get_credits()
    l.lose_lives(3, e)
    check(abs(rl.get_credits() - c0 - 3 * RM.LEAK_BONUS_PER_LIFE) < 1e-9 and rl.get_lives_taken() == 3 and rl.get_leaks() == 1,
          "a 3-integrity leak pays 24 credits")
    check(l.get_lives() == Game.START_LIVES - 3, "and costs the defender 3 integrity")
    check(l.get_reward_scale() == RM.KILL_REWARD_SCALE, "reverse mode pays the listed kill rewards (%s)" % l.get_reward_scale())
    check(_reverse(0, Difficulty.ON).get_reward_scale() != Game(maps.create(0), 1).get_reward_scale(), "the normal game still triples them")
    prev = 0.0
    for d in Difficulty:
        p = DefenderProfile.of(d)
        check(p.level is d and p.income > prev, "%s -> %s funds more than the level below" % (d, p))
        prev = p.income
    for d in Difficulty:
        check(_reverse(0, d).get_cash() == Game.START_CASH * DefenderProfile.of(d).start_cash, "%s starts the AI with its profile's cash" % d)
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
        prev = p
        tag = " [%s]" % d
        g = _reverse(0, d)
        r = g.get_reverse()
        check(g.get_lives() == p.integrity and g.get_max_lives() == p.integrity, "the AI starts with its integrity" + tag)
        check(abs(g.get_global_damage_multiplier() - p.tower_damage) < 1e-9, "the AI's towers deal the mode's damage" + tag)
        check(abs(r.income_rate() - 12 * p.attacker_income) < 1e-9, "compute income starts scaled" + tag)
        c0 = r.get_credits()
        dummy = g.get_enemy_manager().spawn_scaled(EnemyType.PRIMITIVE_VARIABLE, None, 0, 0, 1, 1)
        r.on_leak(5, dummy)
        check(abs(r.get_credits() - c0 - RM.LEAK_BONUS_PER_LIFE * 5 * p.attacker_income) < 1e-9, "leak bounties scale with income" + tag)
        s = _reverse(0, d)
        rs = s.get_reverse()
        rs.set_unlimited_credits(True)
        for _ in range(int(AttackUnit.HEAP.unlock_at / DT) + 1):
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
    g = _reverse(0, Difficulty.ON)
    r = g.get_reverse()
    r.set_unlimited_credits(True)
    for u in AttackUnit:
        check(u.price > 0, "%s has a price" % u)
        check(r.is_unlocked(u) == (u.unlock_at <= 0), "%s unlock state at 0:00" % u)
        if u.unlock_at > 0:
            check(r.send_problem(u, None, 1).startswith("Unlocks at"), "%s refuses to send while locked" % u)
            check(r.send(u, None, 1, -1) == 0, "%s sends nothing while locked" % u)
    max_regular = max(u.price for u in AttackUnit if not u.is_boss())
    for u in AttackUnit:
        if u.is_boss():
            check(u.price > 5 * max_regular, "%s costs far more than any regular unit" % u)
    A = AttackUnit
    check(A.MOAB.price < A.DDT.price < A.BFB.price < A.ZOMG.price < A.BAD.price, "boss prices rise MOAB < DDT < BFB < ZOMG < BAD")
    check(A.of(EnemyType.MERGE_RUN) is None and A.of(EnemyType.QUICK_PARTITION) is None, "split children cannot be bought")
    species = sum(1 for t in EnemyType if t.is_spawnable_species() and A.of(t) is not None)
    check(species == len(list(AttackUnit)) and species == 21, "all 16 species and 5 bosses are buyable, got %d" % species)
    last_regular = max(u.unlock_at for u in AttackUnit if not u.is_boss())
    for u in AttackUnit:
        if u.is_boss():
            check(u.unlock_at >= last_regular, "%s unlocks after the regular units" % u)
        check(u.unlock_at <= A.BAD.unlock_at and u.unlock_at < RM.DURATION, "%s unlocks before Palantir and the run end" % u)
    all_m = EnumSet.all_of(Modifier)
    check(not r.effective_modifiers(A.STATIC, all_m) and r.price(A.STATIC, all_m, 1) == A.STATIC.price, "locked modifiers cost nothing")
    _advance_controller(g, 90)
    check(r.is_unlocked(Modifier.REGROW) and not r.is_unlocked(Modifier.CAMO) and not r.is_unlocked(Modifier.FORTIFIED), "Regrow unlocks at 1:30")
    check(r.is_unlocked(A.SINGLY) and not r.is_unlocked(A.SELECTION), "1:30: linked lists open, the 2:00 tier still locked")
    _advance_controller(g, 150)
    check(r.is_unlocked(Modifier.CAMO) and r.is_unlocked(Modifier.FORTIFIED), "Camo and Fortified unlock by 4:00")
    check(r.price(A.STATIC, all_m, 1) == jround(A.STATIC.price * 1.3 * 1.5 * 2), "surcharges multiply")
    check(r.price(A.QUICK, EnumSet.of(Modifier.CAMO), 5) == 5 * jround(A.QUICK.price * 1.5), "price of a batch is per unit x count")
    check(not r.effective_modifiers(A.BAD, all_m) and A.BAD.price_with(all_m) == A.BAD.price, "Palantir carries no modifiers")
    check(not r.is_unlocked(A.MOAB) and r.is_unlocked(A.HEAP), "4:00: sorters open, bosses not")
    _advance_controller(g, 60)
    check(r.is_unlocked(A.MOAB) and not r.is_unlocked(A.BFB), "the MOAB unlocks at 5:00, the BFB later")
    h = _reverse(0, Difficulty.ON)
    h.get_reverse().set_unlimited_credits(True)
    for a in AttackAbility:
        check(h.get_reverse().ability_problem(a).startswith("Unlocks at"), "%s is locked at 0:00" % a)
    z = _reverse(0, Difficulty.ON)
    _advance_controller(z, RM.DURATION)
    zr = z.get_reverse()
    check(zr.is_uplink_closed() and zr.send_problem(A.PRIMITIVE, None, 1) is not None and zr.send(A.PRIMITIVE, None, 1, -1) == 0,
          "nothing can be sent once the training run is over")
    check(zr.get_epochs_done() == RM.EPOCHS, "all epochs counted")


# ---------------------------------------------------------------- uplink
def test_spawning(check):
    A = AttackUnit
    g = _reverse(0, Difficulty.ON)
    r = g.get_reverse()
    c0 = r.get_credits()
    n = r.send(A.STATIC, None, 5, 0)
    check(n == 5 and r.get_queued() == 5 and r.get_units_bought() == 5, "5 Static Arrays queued")
    check(abs(r.get_credits() - (c0 - 5 * A.STATIC.price)) < 1e-9 and r.get_credits_spent() == 5 * A.STATIC.price, "paid 5 x price")
    affordable = int(r.get_credits() / A.DYNAMIC.price)
    check(r.send(A.DYNAMIC, None, 100, -1) == affordable and r.get_credits() < A.DYNAMIC.price, "a big order buys what the credits allow")
    _advance_controller(g, 1.0)
    check(g.get_enemy_manager().get_total_spawned() == 0, "nothing leaves the uplink during the handshake")
    s = _reverse(0, Difficulty.ON)
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
    b = _reverse(0, Difficulty.ON)
    rb = b.get_reverse()
    rb.set_unlimited_credits(True)
    _advance_controller(b, 300)
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
    check(rb.get_queued() == RM.MAX_QUEUE and added == RM.MAX_QUEUE - waiting, "the queue holds at most MAX_QUEUE")
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
    g = _reverse(0, Difficulty.ON)
    r = g.get_reverse()
    _advance(g, 245)
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
    c = _reverse(0, Difficulty.ON)
    rc = c.get_reverse()
    _advance_controller(c, 240)
    spawn_at(c, EnemyType.PRIMITIVE_VARIABLE, None, 0, 50)
    before = rc.get_credits()
    check(rc.use_ability(AttackAbility.OVERCLOCK) and abs(rc.get_credits() - (before - AttackAbility.OVERCLOCK.cost)) < 1e-9, "Overclock costs credits")


# ---------------------------------------------------------------- the defender AI
@pytest.mark.slow
def test_defender_plays_legally(check):
    for d in (Difficulty.O1, Difficulty.ON2):
        g = _reverse(0 if d is Difficulty.O1 else 2, d)
        r = g.get_reverse()
        bot = AttackerBot(r, Style.PASSIVE if d is Difficulty.O1 else Style.SPAM)
        min_cash = float("inf")
        i = 0
        while i < int(600 / DT) and g.get_state() is State.PLAYING:
            bot.tick(DT)
            g.step(DT)
            g.get_events().clear()
            min_cash = min(min_cash, g.get_cash())
            i += 1
        tag = " [%s]" % r.get_profile()
        ts = g.get_tower_manager().get_player_towers()
        check(g.get_state() is State.PLAYING, "the AI survives ten minutes" + tag)
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
        spent = Game.START_CASH + g.get_total_cash_earned() - g.get_cash()
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
    g.lose_lives(Game.START_LIVES, e)
    _advance(g, 3)
    check(g.get_state() is State.DEFEAT and g.get_reverse().attacker_won() and not g.get_reverse().defender_held(), "integrity 0 = attacker wins")
    p = _reverse(0, Difficulty.ON)
    _advance(p, RM.DURATION - 1)
    check(p.get_state() is State.PLAYING and not p.get_reverse().is_uplink_closed(), "still running a second before the end")
    _advance(p, 2)
    check(p.get_state() is State.VICTORY and p.get_reverse().defender_held() and not p.get_reverse().attacker_won(), "the defender holds")
    check(p.get_reverse().get_elapsed() < RM.DURATION + 1, "no overtime with an empty track")
    o = _reverse(1, Difficulty.O1)
    ro = o.get_reverse()
    _advance(o, RM.DURATION - 3)
    ro.set_unlimited_credits(True)
    ro.send(AttackUnit.BAD, None, 1, -1)
    _advance(o, 6)
    check(ro.is_uplink_closed() and o.get_state() is State.PLAYING, "overtime while Palantir walks")
    _advance(o, RM.OVERTIME + 2)
    check(o.get_state() is not State.PLAYING, "overtime is capped")
    check(ro.get_elapsed() <= RM.DURATION + RM.OVERTIME + 2.5, "ended by " + RM.clock(ro.get_elapsed()))
    k = _reverse(0, Difficulty.ON)
    pal = spawn_at(k, EnemyType.PALANTIR, None, 0, 100)
    kill_outright(k, pal)
    _advance(k, 6)
    check(k.get_state() is State.PLAYING and not k.is_victory_sequence_active(), "killing the attacker's Palantir does not end the match")
    q = _reverse(0, Difficulty.ON)
    qe = spawn_at(q, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    q.lose_lives(Game.START_LIVES, qe)
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


# ---------------------------------------------------------------- whole matches
@pytest.mark.slow
def test_whole_matches(check):
    for m in (0, 1, 5):
        win = AttackerBot.play(m, 42, Difficulty.O1, Style.REASONABLE)
        check(win.attacker_won and win.time < RM.DURATION, "a scripted attacker beats the Novice AI on map %d (%r)" % (m, win))
        idle = AttackerBot.play(m, 42, Difficulty.O1, Style.PASSIVE)
        check(not idle.attacker_won and idle.defender_lives == DefenderProfile.NOVICE.integrity and idle.time >= RM.DURATION,
              "a do-nothing attacker loses on map %d (%r)" % (m, idle))
    spam = AttackerBot.play(0, 42, Difficulty.ON, Style.SPAM)
    check(not spam.attacker_won, "flooding Primitive Variables does not beat the Competent AI (%r)" % spam)
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
