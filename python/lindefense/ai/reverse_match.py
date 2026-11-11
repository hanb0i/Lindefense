"""Reverse mode, "Adversarial Training": the player attacks with compute credits and a DefenderAI defends for an
8-round training run (with a sudden-death overtime when the AI is nearly broken). Also the scripted AttackerBot used by
tests, probes and the demo.

The match: 8 rounds of 60 s. Each round has an objective (take that many integrity points before the round ends) that
pays a compute bonus. The attacker picks a Doctrine in the briefing (Rush / Swarm / Heist). The defender AI looks at
what you spend on every few seconds and adapts against the role you lean on (it builds that role's counter tower)."""
import math
from collections import deque

from lindefense.ai.defender_ai import Action, DefenderAI, Options, Plan
from lindefense.ai.units import (AttackAbility, AttackUnit, DefenderProfile, Doctrine, OVERCLOCK_SPEED, Role,
                                 ZERO_DAY_TARGETS)
from lindefense.enemy.types import Modifier
from lindefense.javacompat import jint, jpow, jround
from lindefense.jenum import EnumSet, JEnum
from lindefense.sim.difficulty import Difficulty

ROUND_SECONDS = 60.0
ROUNDS = 8
DURATION = ROUND_SECONDS * ROUNDS
OVERTIME = 60.0          # sudden-death overtime: the uplink stays open this much longer
OVERTIME_LINE = 0.25     # ... when the AI's integrity is at or below this share of its maximum at the end of round 8
DRAIN = 45.0             # once the uplink closes, units already sent get up to this long to finish
START_CREDITS = Doctrine.default().start_credits   # each doctrine has its own (Doctrine.start_credits)
LEAK_BONUS_PER_LIFE = 8
HANDSHAKE = 5.0
SPAWN_GAP = 0.15         # seconds between two units leaving the uplink (each doctrine: Doctrine.spawn_gap)
MAX_QUEUE = 150          # units the uplink holds (each doctrine: Doctrine.max_queue)
COMPUTE_STEP = 5
COMPUTE_BASE_PRICE = 300
COMPUTE_PRICE_GROWTH = 1.3
COMPUTE_MAX = 8          # SCALE COMPUTE levels (each doctrine: Doctrine.compute_max)
INCOME_BASE = 30.0       # base income per second at 0:00 ...
INCOME_LINEAR = 12.0     # ... + this per minute ...
INCOME_SQUARE = 1.5      # ... + this per minute squared (on O(N): 30/s at 0:00, 80/s at 3:00, 222/s at 8:00)
OVERTIME_INCOME = 2.0    # the attacker's income multiplier during the overtime (which also recharges every exploit)
GOALS = (0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16)   # round objectives: share of the AI's integrity to take
OBJECTIVE_SECONDS = 8.0    # an objective pays this many seconds of your income
ADAPT_START = 40.0       # the AI's first look at your army
ADAPT_WINDOW = 40.0      # it looks at what you spent over this many seconds ...
ADAPT_SHARE = 0.45       # ... and adapts against a role with at least this share of it ...
ADAPT_MIN_SPEND = 250.0  # ... if you spent at least this much
ADAPT_TIMEOUT = 45.0     # a counter not built by then is dropped
COUNTER_MEMORY = 75.0    # the cards show COUNTERED this long after the counter stands
BOSS_NOTICE = 15.0       # an AI that anticipates builds its railgun this long before the first boss unlocks
PRESSURE_WINDOW = 20.0
CAMO_MEMORY = 30.0
FEED_SIZE = 40
TRACK_REFERENCE = 1800.0
TRACK_BONUS_MAX = 3.0
TRACK_EXP = 0.25
SPEED_EXP = 0.75
FUND_RATIO = 1.0
KILL_REWARD_SCALE = 1.0
INTEL_PERIOD = 0.5
LANE_PERIOD = 1.0

# colours of the match's banners and feed lines
GOLD = 0xffd166
GOOD = 0x3bff8a
VIOLET = 0xb48cff
PINK = 0xff2bd6
RED = 0xff4d4d


class FeedEntry:
    def __init__(self, time, text, rgb, action, tower):
        self.time, self.text, self.rgb, self.action, self.tower = time, text, rgb, action, tower


class _Pending:
    __slots__ = ("unit", "mods", "route")

    def __init__(self, unit, mods, route):
        self.unit, self.mods, self.route = unit, mods, route


class Adaptation:
    """One adaptation of the defender AI: the role it answers and the counter (tower, copies, tier) it builds."""
    __slots__ = ("role", "tower", "copies", "tier", "since", "done_at")

    def __init__(self, role, tower, copies, tier, since):
        self.role, self.tower, self.copies, self.tier, self.since = role, tower, copies, tier, since
        self.done_at = -1.0

    def want(self):
        return self.tower, self.copies, self.tier


def _mean_route(gmap):
    routes = gmap.get_routes()
    return sum(p.get_total_length() for p in routes) / max(1, len(routes))


def track_bonus(gmap):
    return max(1.0, min(TRACK_BONUS_MAX, jpow(_mean_route(gmap) / TRACK_REFERENCE, TRACK_EXP)))


def track_speed(gmap):
    return max(1.0, min(TRACK_BONUS_MAX, jpow(_mean_route(gmap) / TRACK_REFERENCE, SPEED_EXP)))


def clock(seconds):
    s = jint(math.ceil(max(0.0, seconds)))
    return str(s // 60) + ":" + ("0" if s % 60 < 10 else "") + str(s % 60)


def goal_for(round_index, integrity):
    """The objective of round round_index (0-based): integrity points to take before the round ends."""
    return max(2, jround(integrity * GOALS[min(round_index, ROUNDS - 1)]))


class ReverseMatch:
    ROUND_SECONDS = ROUND_SECONDS
    ROUNDS = ROUNDS
    DURATION = DURATION
    OVERTIME = OVERTIME
    DRAIN = DRAIN
    HANDSHAKE = HANDSHAKE
    clock = staticmethod(clock)

    @staticmethod
    def create(map_or_index, seed, level, doctrine=None):
        from lindefense.map import maps
        from lindefense.sim.game import Game
        gmap = maps.create(map_or_index) if isinstance(map_or_index, int) else map_or_index
        g = Game(gmap, seed, Difficulty.O1)
        g.set_reverse(ReverseMatch(g, DefenderProfile.of(Difficulty.O1 if level is None else level),
                                   Doctrine.default() if doctrine is None else doctrine))
        return g

    @staticmethod
    def restart(old):
        from lindefense.map import maps
        from lindefense.variance.variance import seed_next
        r = old.get_reverse()
        idx = maps.index_of(old.get_map())
        if r is None or idx < 0:
            raise ValueError("not a reverse-mode catalog game")
        g = ReverseMatch.create(idx, seed_next(), r._profile.level, r._doctrine)
        g.get_reverse().set_unlimited_credits(r._unlimited)
        return g

    def __init__(self, game, profile, doctrine=None):
        from lindefense.sim.game import Game
        self._game = game
        self._profile = profile
        self._doctrine = Doctrine.default() if doctrine is None else doctrine
        self._credits = float(self._doctrine.start_credits)
        self._credits_earned = float(self._doctrine.start_credits)
        self._credits_spent = 0.0
        self._defender_funding = 0.0
        self._leak_bonus = 0.0
        self._objective_bonus = 0.0
        self._compute_level = 0
        self._track_bonus = track_bonus(game.get_map())
        self._track_speed = track_speed(game.get_map())
        self._elapsed = 0.0
        self._rounds_done = 0
        self._taken = [0] * (ROUNDS + 1)          # integrity taken per round (the last slot: overtime)
        self._met = [False] * ROUNDS
        self._overtime = False
        self._uplink_closed = False
        self._closed_at = 0.0
        self._critical = False
        self._queue = deque()
        self._spawn_timer = 0.0
        self._cooldowns = {}
        self._uses = {}
        self._overclock_left = 0.0
        self._feed = []
        self._last_ai_action = None
        self._units_bought = self._units_spawned = self._lives_taken = self._leaks = self._bosses_sent = 0
        self._think_timer = 0.0
        self._camo_scan_timer = 0.0
        self._last_camo_seen = -1e9
        self._unlimited = False
        self._sends = deque()                     # (time, role, camo, credits) for the AI's look at your army
        self._adapt_timer = ADAPT_START
        self._adaptation = None
        self._adaptations = []
        self._role_edge = {}
        self._intel_timer = 0.0
        self._lane_cover = []
        self._lane_timer = 0.0
        game.set_starting_lives(profile.integrity)
        self._lives_mark = profile.integrity
        if profile.start_cash > 1:
            game.add_cash(Game.START_CASH * (profile.start_cash - 1), None)
        o = Options()
        o.plan = Plan.REVERSE
        o.random_placement = profile.casual
        o.unlock_abilities = profile.unlocks_abilities
        o.unlock_min_towers = profile.unlock_min_towers
        o.unlock_towers_per = profile.unlock_towers_per
        o.wave_source = self.equivalent_wave
        o.camo_alarm = self._camo_alarm
        o.counter = self._counter_order
        o.pressure_window = PRESSURE_WINDOW
        self._ai = DefenderAI(game, o)
        self._ai.set_listener(self._on_ai_action)
        self._announced = {u for u in AttackUnit if self.unlock_at(u) <= 0}
        self._announced_mods = set()
        self._announced_abilities = {a for a in AttackAbility if a.unlock_at <= 0}
        self._refresh_intel()
        self._refresh_lanes()

    # ---- accessors
    def get_game(self):
        return self._game

    def get_profile(self):
        return self._profile

    def get_level(self):
        return self._profile.level

    def get_doctrine(self):
        return self._doctrine

    def get_ai(self):
        return self._ai

    def get_credits(self):
        from lindefense.sim.game import Game
        return Game.ADMIN_CASH if self._unlimited else self._credits

    def get_credits_earned(self):
        return self._credits_earned

    def get_credits_spent(self):
        return self._credits_spent

    def get_leak_bonus(self):
        return self._leak_bonus

    def get_objective_bonus(self):
        return self._objective_bonus

    def unit_hp_scale(self, type_):
        """The match's health factor (the BAD included: the campaign's per-mode Palantir multiplier is a final-boss
        rule, not a reverse-mode one) times the unit's own factor from the unit table (and the Swarm doctrine's bonus for
        the regular units)."""
        u = AttackUnit.of(type_)
        own = 1.0 if u is None else u.hp_factor() * (1.0 if u.is_boss() else self._doctrine.unit_hp)
        return self._game.get_wave_hp_scale() * self._profile.unit_hp * own

    def get_defender_funding(self):
        return self._defender_funding

    def get_elapsed(self):
        return self._elapsed

    def close_time(self):
        """When the uplink closes: the end of round 8, or of the overtime."""
        return DURATION + (OVERTIME if self._overtime else 0.0)

    def get_time_left(self):
        """Time until the uplink closes."""
        return max(0.0, self.close_time() - self._elapsed)

    def get_overtime_left(self):
        return max(0.0, DURATION + OVERTIME - self._elapsed) if self._overtime else OVERTIME

    def get_drain_left(self):
        """Once the uplink is closed: how long the units already sent may still walk."""
        return max(0.0, self._closed_at + DRAIN - self._elapsed) if self._uplink_closed else DRAIN

    def is_overtime(self):
        return self._overtime

    def get_round_index(self):
        """0-based round (ROUNDS while in the overtime); after the uplink closed, the last round played."""
        return ROUNDS if self._overtime else min(self._rounds_done, ROUNDS - 1)

    def get_round(self):
        """1-based round number for the HUD (ROUNDS + 1 in the overtime)."""
        return self.get_round_index() + 1

    def get_rounds_done(self):
        return self._rounds_done

    def is_final_round(self):
        return not self._overtime and self._rounds_done == ROUNDS - 1

    def round_time_left(self):
        if self._uplink_closed:
            return 0.0
        if self._overtime:
            return self.get_time_left()
        return max(0.0, (self._rounds_done + 1) * ROUND_SECONDS - self._elapsed)

    def round_goal(self, i=None):
        """Objective of round i (0-based; default the current round): integrity to take before it ends. 0 for the
        overtime (no objective: break the AI)."""
        i = self.get_round_index() if i is None else i
        return 0 if i >= ROUNDS else goal_for(i, self._game.get_max_lives())

    def round_taken(self, i=None):
        return self._taken[self.get_round_index() if i is None else i]

    def objective_met(self, i=None):
        i = self.get_round_index() if i is None else i
        return i < ROUNDS and self._met[i]

    def get_objectives_met(self):
        return sum(1 for m in self._met if m)

    def get_round_history(self):
        """[(taken, goal, met)] for every round started so far (the overtime last, with goal 0)."""
        n = ROUNDS + 1 if self._overtime else min(ROUNDS, self._rounds_done + 1)
        return [(self._taken[i], self.round_goal(i), i < ROUNDS and self._met[i]) for i in range(n)]

    def objective_reward(self):
        """What the current objective pays now (OBJECTIVE_SECONDS of income, with the doctrine's multiplier)."""
        return jround(OBJECTIVE_SECONDS * self.income_rate() * self._doctrine.objective_pay)

    def is_uplink_closed(self):
        return self._uplink_closed

    def has_unlimited_credits(self):
        return self._unlimited

    def set_unlimited_credits(self, u):
        self._unlimited = u

    def get_compute_level(self):
        return self._compute_level

    def compute_max(self):
        return self._doctrine.compute_max

    def compute_step(self):
        return COMPUTE_STEP

    def max_queue(self):
        return self._doctrine.max_queue

    def get_units_bought(self):
        return self._units_bought

    def get_units_spawned(self):
        return self._units_spawned

    def get_bosses_sent(self):
        return self._bosses_sent

    def get_lives_taken(self):
        return self._lives_taken

    def get_leaks(self):
        return self._leaks

    def get_queued(self):
        return len(self._queue)

    def get_uses(self, a):
        return self._uses.get(a, 0)

    def get_feed(self):
        return tuple(self._feed)

    def get_last_ai_action(self):
        return self._last_ai_action

    def get_adaptations(self):
        """Every adaptation the AI made, oldest first (the last one may still be under construction)."""
        return tuple(self._adaptations)

    def get_adaptation(self):
        """The counter the AI is building right now, or None."""
        return self._adaptation

    def attacker_won(self):
        from lindefense.sim.game import State
        return self._game.get_state() is State.DEFEAT

    def defender_held(self):
        from lindefense.sim.game import State
        return self._game.get_state() is State.VICTORY

    def income_rate(self):
        r = (self.base_income() * self._track_bonus * self._doctrine.income + COMPUTE_STEP * self._compute_level) * self._profile.attacker_income
        return r * OVERTIME_INCOME if (self._overtime and not self._uplink_closed) else r

    def get_track_bonus(self):
        return self._track_bonus

    def get_track_speed(self):
        return self._track_speed

    def base_income(self):
        m = min(self._elapsed, DURATION) / 60.0
        return INCOME_BASE + INCOME_LINEAR * m + INCOME_SQUARE * m * m

    def defender_funding_rate(self):
        return self.base_income() * FUND_RATIO * self._profile.income

    def kill_reward_scale(self):
        return KILL_REWARD_SCALE

    def equivalent_wave(self):
        return 1 + jint(min(99.0, self._elapsed / DURATION * 99))

    # ---- unlocks
    def unlock_at(self, x):
        """When a unit, modifier or exploit unlocks in this match (the Rush doctrine brings the bosses forward)."""
        if isinstance(x, AttackUnit):
            return max(0.0, x.unlock_at + (self._doctrine.boss_shift if x.is_boss() else 0.0))
        if isinstance(x, AttackAbility):
            return x.unlock_at
        return AttackUnit.modifier_unlock_at(x)

    def is_unlocked(self, x):
        return self._elapsed >= self.unlock_at(x)

    def unlocks_in(self, u):
        return max(0.0, self.unlock_at(u) - self._elapsed)

    def next_unlock(self):
        """(time, [names]) of the next unlock, or (None, []) once everything is open."""
        nxt = None
        for x in list(AttackUnit) + list(Modifier) + list(AttackAbility):
            t = self.unlock_at(x)
            if t > self._elapsed and (nxt is None or t < nxt):
                nxt = t
        if nxt is None:
            return None, []
        names = [u.type.display_name for u in AttackUnit if self.unlock_at(u) == nxt]
        names += [m.label for m in Modifier if self.unlock_at(m) == nxt]
        names += [a.display_name for a in AttackAbility if self.unlock_at(a) == nxt]
        return nxt, names

    def effective_modifiers(self, u, mods):
        m = EnumSet()
        if mods is None or not u.accepts_modifiers():
            return m
        for x in mods:
            if self.is_unlocked(x):
                m.add(x)
        return m

    def unit_price(self, u, mods):
        """One unit's price with its (unlocked) modifiers and the doctrine's discount or surcharge."""
        k = self._doctrine.boss_cost if u.is_boss() else self._doctrine.unit_cost
        return jint(jround(u.raw_price(self.effective_modifiers(u, mods)) * k))

    def price(self, u, mods, count):
        return self.unit_price(u, mods) * max(1, count)

    def ability_cost(self, a):
        return jint(jround(a.cost * self._doctrine.exploit_cost))

    def ability_cooldown(self, a):
        return a.cooldown * self._doctrine.exploit_cooldown

    # ---- intel: what the AI can answer, per role and lane
    def _refresh_intel(self):
        ai = self._ai
        types = {t.get_type() for t in self._game.get_tower_manager().get_player_towers()}
        for r in Role:
            if r is Role.CAMO:
                self._role_edge[r] = not ai.has_detection()
            else:
                self._role_edge[r] = not any(t in types for t in r.answers)

    def role_status(self, role):
        """"countered" while the AI's counter against the role stands (for COUNTER_MEMORY s after it was built),
        "edge" while the AI has no tower that answers the role, else None."""
        for a in reversed(self._adaptations):
            if a.role is role and a.done_at >= 0 and self._elapsed - a.done_at <= COUNTER_MEMORY:
                return "countered"
        return "edge" if self._role_edge.get(role, False) else None

    def unit_status(self, u, mods=None):
        """The card's matchup tag for unit u with the toggled modifiers: camo against a blind AI is an edge."""
        camo = u.type.has_innate_camo() or (mods is not None and Modifier.CAMO in self.effective_modifiers(u, mods))
        if camo and self.role_status(Role.CAMO) == "edge":
            return "edge"
        return self.role_status(u.role)

    def edge_reason(self, u, mods=None):
        """One sentence: why the card shows its tag (None without one)."""
        s = self.unit_status(u, mods)
        camo = u.type.has_innate_camo() or (mods is not None and Modifier.CAMO in self.effective_modifiers(u, mods))
        if s == "edge" and camo and self.role_status(Role.CAMO) == "edge":
            return "EDGE: the AI has no camo detection yet."
        if s == "edge":
            return "EDGE: no " + u.role.counter_what + " (" + u.role.counter.display_name + ") yet."
        if s == "countered":
            return "COUNTERED: " + u.role.counter.display_name + " now answers your " + u.role.plural + "."
        return None

    def _refresh_lanes(self):
        g = self._game
        routes = g.get_map().get_routes()
        if len(routes) < 2:
            self._lane_cover = []
            return
        towers = g.get_tower_manager().get_player_towers()
        out = []
        for p in routes:
            cover = 0.0
            d = 0.0
            while d < p.get_total_length():
                v = p.position_at(d)
                for tw in towers:
                    rng = tw.get_stats().range
                    if rng >= 1000 or tw.get_position().dist_sq(v) <= rng * rng:
                        cover += 1 + tw.get_tier()
                d += 40
            out.append(cover / max(1.0, p.get_total_length()))
        self._lane_cover = out

    def lane_cover(self):
        """Per lane: how much tower coverage the AI has on it (refreshed every second; empty on one-lane maps)."""
        return tuple(self._lane_cover)

    def weakest_lane(self):
        """The lane with the least AI coverage, or -1 (one lane, or all equal)."""
        c = self._lane_cover
        if len(c) < 2:
            return -1
        best = 0
        for i in range(1, len(c)):
            if c[i] < c[best]:
                best = i
        return best

    def lane_label(self, i):
        """"OPEN" for a lane the AI covers clearly less than the busiest one, "HEAVY" for the busiest, else "EVEN"."""
        c = self._lane_cover
        if i < 0 or i >= len(c):
            return None
        lo, hi = min(c), max(c)
        if c[i] == lo and lo < 0.75 * hi:
            return "OPEN"
        if c[i] == hi and hi > 1.25 * max(lo, 1e-9):
            return "HEAVY"
        return "EVEN"

    # ---- attacker actions
    def send_problem(self, u, mods, count):
        from lindefense.sim.game import State
        if self._game.get_state() is not State.PLAYING:
            return "Match over"
        if self._uplink_closed:
            return "Uplink closed"
        if not self.is_unlocked(u):
            return "Unlocks at " + clock(self.unlock_at(u))
        if len(self._queue) >= self.max_queue():
            return "Uplink queue full"
        if not self._unlimited and self._credits < self.price(u, mods, 1):
            return "Not enough credits"
        return None

    def send(self, u, mods, count, route):
        if self.send_problem(u, mods, 1) is not None:
            return 0
        m = self.effective_modifiers(u, mods)
        each = self.unit_price(u, m)
        routes = len(self._game.get_map().get_routes())
        lane = -1 if route >= routes else route
        n = 0
        cap = self.max_queue()
        while n < max(1, count) and len(self._queue) < cap and (self._unlimited or self._credits >= each):
            self._spend(each)
            self._queue.append(_Pending(u, m.copy(), lane))
            n += 1
        self._units_bought += n
        if u.is_boss():
            self._bosses_sent += n
        if n > 0:
            self._sends.append((self._elapsed, u.role, u.type.has_innate_camo() or Modifier.CAMO in m, float(each * n)))
        return n

    def compute_price(self):
        return jint(jround(COMPUTE_BASE_PRICE * jpow(COMPUTE_PRICE_GROWTH, self._compute_level) * self._doctrine.compute_price))

    def compute_problem(self):
        from lindefense.sim.game import State
        if self._game.get_state() is not State.PLAYING:
            return "Match over"
        if self._uplink_closed:
            return "Uplink closed"
        if self._compute_level >= self.compute_max():
            return "Fully scaled"
        if not self._unlimited and self._credits < self.compute_price():
            return "Not enough credits"
        return None

    def scale_compute(self):
        if self.compute_problem() is not None:
            return False
        self._spend(self.compute_price())
        self._compute_level += 1
        self._feed_line("Compute scaled to +" + str(COMPUTE_STEP * self._compute_level) + "/s", GOLD, None, None)
        return True

    def cooldown_left(self, a):
        return self._cooldowns.get(a, 0.0)

    def get_overclock_left(self):
        return self._overclock_left

    def ability_problem(self, a):
        from lindefense.sim.game import State
        g = self._game
        if g.get_state() is not State.PLAYING:
            return "Match over"
        if self._uplink_closed:
            return "Uplink closed"
        if not self.is_unlocked(a):
            return "Unlocks at " + clock(self.unlock_at(a))
        if self.cooldown_left(a) > 0:
            return "Recharging (" + str(jint(math.ceil(self.cooldown_left(a)))) + "s)"
        if not self._unlimited and self._credits < self.ability_cost(a):
            return "Not enough credits"
        if a is not AttackAbility.ZERO_DAY and not g.get_enemy_manager().get_enemies():
            return "No units on the track"
        if a is AttackAbility.ZERO_DAY and not g.get_tower_manager().get_player_towers():
            return "No towers to jam"
        return None

    def use_ability(self, a):
        if self.ability_problem(a) is not None:
            return False
        g = self._game
        self._spend(self.ability_cost(a))
        self._cooldowns[a] = self.ability_cooldown(a)
        self._uses[a] = self.get_uses(a) + 1
        if a is AttackAbility.OVERCLOCK:
            if self._overclock_left <= 0:
                g.set_global_enemy_speed_multiplier(g.get_global_enemy_speed_multiplier() * OVERCLOCK_SPEED)
            self._overclock_left = a.duration
            g.set_banner("OVERCLOCK: UNITS +50% SPEED", PINK, 2)
        elif a is AttackAbility.HOTFIX:
            n = 0
            for e in g.get_enemy_manager().get_enemies():
                if not e.is_alive() or e.get_hp() >= e.get_max_hp():
                    continue
                e.heal(e.get_max_hp())
                g.emit_text(e.get_position(), "+HP", GOOD)
                n += 1
            g.set_banner("HOTFIX: " + str(n) + " UNITS RESTORED", GOOD, 2)
        elif a is AttackAbility.ZERO_DAY:
            ts = list(g.get_tower_manager().get_player_towers())
            ts.sort(key=lambda t: -t.get_invested_cost())
            jammed = tried = 0
            for t in ts:
                if tried >= ZERO_DAY_TARGETS:
                    break
                tried += 1
                if t.is_surveillance_immune():
                    g.emit_text(t.get_position(), "PATCHED", 0x7fd8a8)
                    continue
                t.set_surveilled(a.duration)
                g.emit_text(t.get_position(), "JAMMED", RED)
                jammed += 1
            g.set_banner("ZERO-DAY: " + str(jammed) + " TOWER" + ("" if jammed == 1 else "S") + " JAMMED", RED, 2)
        self._feed_line("Exploit: " + a.display_name, PINK, None, None)
        return True

    def _spend(self, amount):
        if not self._unlimited:
            self._credits -= amount
        self._credits_spent += amount

    def _earn(self, amount):
        self._credits += amount
        self._credits_earned += amount

    # ---- simulation hooks
    def update(self, dt):
        from lindefense.sim.game import State
        g = self._game
        if g.get_state() is not State.PLAYING:
            return
        self._elapsed += dt
        self._lives_mark = g.get_lives()
        if not self._uplink_closed:
            self._earn(self.income_rate() * dt)
            fund = self.defender_funding_rate() * dt
            g.add_cash(fund, None)
            self._defender_funding += fund
        banner = None
        while self._rounds_done < ROUNDS and self._elapsed >= (self._rounds_done + 1) * ROUND_SECONDS:
            banner = self._end_round()
        unlocked = self._announce_unlocks()
        if banner is None and unlocked:
            head = ", ".join(unlocked[:3]) + " +" + str(len(unlocked) - 3) if len(unlocked) > 3 else ", ".join(unlocked)
            g.set_banner("UNLOCKED: " + head.upper(), PINK, 3)
        elif banner is not None:
            text, rgb = banner
            if unlocked:
                text += "  ·  " + str(len(unlocked)) + " UNLOCK" + ("" if len(unlocked) == 1 else "S")
            g.set_banner(text, rgb, 3.5)
        if self._elapsed >= HANDSHAKE:
            self._spawn_timer -= dt
        gap = self._doctrine.spawn_gap
        while self._spawn_timer <= 0 and self._queue and self._elapsed >= HANDSHAKE:
            p = self._queue.popleft()
            e = g.get_enemy_manager().spawn_scaled(p.unit.type, p.mods, p.route, 0, self.unit_hp_scale(p.unit.type),
                                                   g.get_wave_speed_scale() * self._track_speed)
            if e is not None:
                self._units_spawned += 1
            self._spawn_timer += gap
        if not self._queue and self._spawn_timer < 0:
            self._spawn_timer = 0.0
        for a in AttackAbility:
            c = self.cooldown_left(a)
            if c > 0:
                self._cooldowns[a] = max(0.0, c - dt)
        if self._overclock_left > 0:
            self._overclock_left -= dt
            if self._overclock_left <= 0:
                self._overclock_left = 0.0
                g.set_global_enemy_speed_multiplier(g.get_global_enemy_speed_multiplier() / OVERCLOCK_SPEED)
        self._camo_scan_timer -= dt
        if self._camo_scan_timer <= 0:
            self._camo_scan_timer = 0.5
            for e in g.get_enemy_manager().get_enemies():
                if e.is_camo():
                    self._last_camo_seen = self._elapsed
                    break
        if not self._uplink_closed:
            self._adapt(dt)
        self._think_timer -= dt
        if self._think_timer <= 0:
            self._think_timer += self._profile.think_interval
            self._ai.manage()
        self._check_adaptation()
        self._intel_timer -= dt
        if self._intel_timer <= 0:
            self._intel_timer += INTEL_PERIOD
            self._refresh_intel()
        self._lane_timer -= dt
        if self._lane_timer <= 0:
            self._lane_timer += LANE_PERIOD
            self._refresh_lanes()
        if not self._uplink_closed and self._overtime and self._elapsed >= DURATION + OVERTIME:
            self._close_uplink("OVERTIME OVER  -  UPLINK CLOSED")
        if (self._uplink_closed and g.get_state() is State.PLAYING
                and ((not self._queue and g.get_enemy_manager().is_empty()) or self._elapsed >= self._closed_at + DRAIN)):
            self._feed_line("Defender held with " + str(g.get_lives()) + " integrity", 0x7fd8a8, None, None)
            g.declare_defender_victory("THE DEFENDER AI HELD THE LINE")

    def _close_uplink(self, banner):
        self._uplink_closed = True
        self._closed_at = self._elapsed
        self._game.set_banner(banner, GOLD, 3)
        self._feed_line("Uplink closed: units already sent get " + clock(DRAIN) + " to finish", GOLD, None, None)

    def on_leak(self, lives, leaker):
        if lives <= 0:
            return
        g = self._game
        self._leaks += 1
        took = max(0, min(lives, self._lives_mark - g.get_lives()))   # what it really took (no overkill past 0)
        self._lives_mark = g.get_lives()
        self._lives_taken += took
        bonus = self.leak_pay(lives)
        self._earn(bonus)
        self._leak_bonus += bonus
        i = self.get_round_index()
        self._taken[i] += took
        if not self._uplink_closed and i < ROUNDS and not self._met[i] and self._taken[i] >= self.round_goal(i):
            self._met[i] = True
            pay = self.objective_reward()
            self._earn(pay)
            self._objective_bonus += pay
            g.set_banner("OBJECTIVE COMPLETE  +" + str(pay) + " COMPUTE", GOOD, 2.5)
            self._feed_line("Round " + str(i + 1) + " objective complete: +" + str(pay) + " compute", GOOD, None, None)
        if not self._critical and 0 < g.get_lives() <= OVERTIME_LINE * g.get_max_lives():
            self._critical = True
            if not self._uplink_closed and not self._overtime:
                g.set_banner("AI INTEGRITY CRITICAL  -  KEEP IT UNDER " + str(self.overtime_line()) + " FOR OVERTIME", RED, 3)
            self._feed_line("AI integrity critical (" + str(g.get_lives()) + ")", RED, None, None)

    def leak_pay(self, lives):
        """Compute a leak of that many integrity points pays (the mode's income multiplier and the doctrine's)."""
        return LEAK_BONUS_PER_LIFE * lives * self._profile.attacker_income * self._doctrine.leak_pay

    def overtime_line(self):
        """At or below this much integrity at the end of round 8, the match goes to sudden-death overtime."""
        return jint(OVERTIME_LINE * self._game.get_max_lives())

    def _end_round(self):
        """Closes the current round (objective result, the AI's research), then opens the next one, the overtime or
        closes the uplink. Returns (banner text, rgb) for the new round, or None."""
        g = self._game
        i = self._rounds_done
        self._rounds_done += 1
        research = 0.0
        for t in list(g.get_tower_manager().get_towers()):
            research += t.get_behavior().on_round_end(g, t)
        if research > 0:
            g.add_cash(research, None)
        g.add_pop_value(-g.get_round_pop_value())
        tail = "  (AI research +$" + str(jint(research)) + ")" if research > 0 else ""
        if self._met[i]:
            self._feed_line("Round " + str(i + 1) + " won: " + str(self._taken[i]) + " integrity taken" + tail, GOOD, None, None)
        else:
            self._feed_line("Round " + str(i + 1) + " held by the AI (" + str(self._taken[i]) + " / " + str(self.round_goal(i))
                            + ")" + tail, 0x9fb3c8, None, None)
        if self._rounds_done < ROUNDS:
            n = self._rounds_done
            goal = self.round_goal(n)
            self._feed_line("Round " + str(n + 1) + ": take " + str(goal) + " integrity for +" + str(self.objective_reward())
                            + " compute", GOLD, None, None)
            final = n == ROUNDS - 1
            return (("FINAL ROUND" if final else "ROUND " + str(n + 1) + " / " + str(ROUNDS)) + "  -  BREACH " + str(goal),
                    RED if final else GOLD)
        if g.get_lives() <= self.overtime_line():
            self._overtime = True
            self._cooldowns.clear()
            self._feed_line("Sudden-death overtime: the uplink stays open for " + clock(OVERTIME) + ", income x"
                            + ("%g" % OVERTIME_INCOME) + ", exploits recharged", RED, None, None)
            return "SUDDEN-DEATH OVERTIME  -  BREAK IT IN " + clock(OVERTIME), RED
        self._close_uplink("TRAINING RUN OVER  -  UPLINK CLOSED")
        return "TRAINING RUN OVER  -  UPLINK CLOSED", GOLD

    def _announce_unlocks(self):
        names = []
        for u in AttackUnit:
            if u in self._announced or not self.is_unlocked(u):
                continue
            self._announced.add(u)
            names.append(u.type.display_name)
        for m in Modifier:
            if m in self._announced_mods or not self.is_unlocked(m):
                continue
            self._announced_mods.add(m)
            names.append(m.label + " modifier")
        for a in AttackAbility:
            if a in self._announced_abilities or not self.is_unlocked(a):
                continue
            self._announced_abilities.add(a)
            names.append(a.display_name + " exploit")
        if names:
            self._feed_line("Unlocked: " + ", ".join(names), PINK, None, None)
        return names

    # ---- the AI adapts
    def _adapt(self, dt):
        """Every adapt_interval seconds the AI looks at what you spent over the last ADAPT_WINDOW seconds; if one role
        dominates and the AI's counter to it is not standing yet, it builds that counter before its plan."""
        while self._sends and self._sends[0][0] < self._elapsed - ADAPT_WINDOW:
            self._sends.popleft()
        if self._adaptation is not None:
            return
        if self._boss_alarm():
            self._start_adaptation(Role.BOSS, "THE AI BRACES FOR BOSSES: ")
            return
        self._adapt_timer -= dt
        if self._adapt_timer > 0:
            return
        self._adapt_timer = self._profile.adapt_interval
        total = 0.0
        spend = {}
        camo = 0.0
        for _, role, c, amount in self._sends:
            total += amount
            spend[role] = spend.get(role, 0.0) + amount
            if c:
                camo += amount
        if total < ADAPT_MIN_SPEND:
            return
        picks = []
        if camo >= ADAPT_SHARE * total and not self._ai.has_detection():
            picks.append(Role.CAMO)
        for r in Role:
            if r is not Role.CAMO and spend.get(r, 0.0) >= ADAPT_SHARE * total:
                picks.append(r)
        for r in picks:
            if self._start_adaptation(r, "THE AI ADAPTS: "):
                return

    def _boss_alarm(self):
        """The AI has no railgun while a boss is on the track (or, if it anticipates, about to unlock)."""
        ai = self._ai
        if any(t.get_type() is Role.BOSS.counter for t in self._game.get_tower_manager().get_player_towers()):
            return False
        if self._profile.anticipates_camo and self.unlocks_in(AttackUnit.MOAB) <= BOSS_NOTICE:
            return True
        return any(e.is_boss() for e in self._game.get_enemy_manager().get_enemies())

    def _start_adaptation(self, r, head):
        have = sum(1 for t in self._game.get_tower_manager().get_player_towers() if t.get_type() is r.counter)
        copies = min(r.counter_cap, have + 1)
        if r is not Role.CAMO and have >= r.counter_cap:
            return False
        tier = r.counter_tier + (1 if (self._profile.anticipates_camo and r is not Role.CAMO) else 0)
        a = Adaptation(r, r.counter, copies, tier, self._elapsed)
        self._adaptation = a
        self._adaptations.append(a)
        what = r.counter.display_name + " (" + r.counter_what + ")"
        self._game.set_banner(head + r.counter.display_name.upper() + " VS YOUR " + r.plural.upper(), VIOLET, 3)
        self._feed_line("AI adapts: building " + what + " against your " + r.plural, VIOLET, None, None)
        return True

    def _counter_order(self):
        a = self._adaptation
        return None if a is None else a.want()

    def _check_adaptation(self):
        a = self._adaptation
        if a is None:
            return
        done = self._ai.has_detection() if a.role is Role.CAMO else self._ai.counter_ready(a.want())
        if done:
            a.done_at = self._elapsed
            self._adaptation = None
            self._refresh_intel()
            self._feed_line("AI countered your " + a.role.plural + ": " + a.tower.display_name + " online", VIOLET, None, None)
        elif self._elapsed - a.since > ADAPT_TIMEOUT:
            self._adaptation = None
            self._feed_line("AI dropped its counter to your " + a.role.plural + " (no funds)", 0x9fb3c8, None, None)

    def _camo_alarm(self):
        if self._elapsed - self._last_camo_seen <= CAMO_MEMORY:
            return True
        return self._profile.anticipates_camo and (self.is_unlocked(Modifier.CAMO) or self.is_unlocked(AttackUnit.DDT))

    def _on_ai_action(self, a, t, text):
        if a is Action.BUILD:
            rgb = 0x00f0ff
        elif a is Action.UPGRADE:
            rgb = GOOD
        elif a is Action.HERO_UNLOCK or a is Action.HERO_DEPLOY:
            rgb = GOLD
        elif a is Action.ABILITY_UNLOCK:
            rgb = PINK
        else:
            rgb = VIOLET
        e = self._feed_line("AI " + text, rgb, a, t.get_type() if t is not None else None)
        if a is not Action.ABILITY_CAST:
            self._last_ai_action = e
        if a in (Action.HERO_UNLOCK, Action.HERO_DEPLOY, Action.ABILITY_UNLOCK):
            self._game.set_banner(("DEFENDER AI " + text).upper(), rgb, 2.5)

    def _feed_line(self, text, rgb, a, tower):
        e = FeedEntry(self._elapsed, text, rgb, a, tower)
        self._feed.append(e)
        if len(self._feed) > FEED_SIZE:
            del self._feed[0]
        return e


# ====================================================================== AttackerBot
class Style(JEnum):
    PASSIVE = ()
    SPAM = ()
    REASONABLE = ()


DEFAULT_PUSH_SECONDS = 30.0
DEFAULT_BOSS_SHARE = 0.8
BOT_COMPUTE_UNTIL = 150.0   # the reasonable bot scales compute in the first 2:30 ...
BOT_COMPUTE_LEVELS = 4      # ... up to this level
BOT_MIN_PUSH = 300.0
BOT_LAST_CALL = 25.0        # seconds before the uplink closes when it sends whatever it has
BOT_SAVE_SECONDS = 100.0    # ... and saves up for the biggest boss it can afford within this much income
BOT_SWARM_BOSSES = 1.0      # with the Swarm doctrine it spends this share of its usual boss budget on bosses


class Outcome:
    def __init__(self):
        self.attacker_won = False
        self.time = 0.0
        self.defender_lives = self.towers = self.maxed = self.heroes = self.ability_unlocks = 0
        self.credits_spent = self.defender_earned = 0.0
        self.units_sent = 0
        self.objectives = 0
        self.adaptations = 0

    def __repr__(self):
        from lindefense.ui import jrt as _j   # String.format: %.0f rounds half up, like Java
        return _j.format("%s at %s  lives %3d  towers %2d (maxed %2d, heroes %d, abilities %d)  spent %7.0f  AI earned %7.0f  units %5d  objectives %d  adapts %d",
                         "ATTACKER WINS" if self.attacker_won else "DEFENDER HOLDS", clock(self.time), self.defender_lives, self.towers,
                         self.maxed, self.heroes, self.ability_unlocks, self.credits_spent, self.defender_earned, self.units_sent,
                         self.objectives, self.adaptations)


class AttackerBot:
    Style = Style

    def __init__(self, match, style, push_seconds=DEFAULT_PUSH_SECONDS, boss_share=DEFAULT_BOSS_SHARE):
        self._match = match
        self._style = style
        self._push_seconds = push_seconds
        self._boss_share = boss_share
        self._timer = 0.0

    def get_style(self):
        return self._style

    def tick(self, dt):
        from lindefense.sim.game import State
        self._timer -= dt
        if self._timer > 0:
            return
        self._timer = 0.5
        m = self._match
        g = m.get_game()
        if g.get_state() is not State.PLAYING or g.get_lives() <= 0 or m.is_uplink_closed():
            return
        if self._style is Style.SPAM:
            m.send(AttackUnit.PRIMITIVE, None, 10, -1)
        elif self._style is Style.REASONABLE:
            self._reasonable()

    def _reasonable(self):
        m = self._match
        t = m.get_elapsed()
        if t < BOT_COMPUTE_UNTIL and m.get_compute_level() < BOT_COMPUTE_LEVELS and m.compute_problem() is None:
            m.scale_compute()
            return
        self._exploits()
        mods = EnumSet()
        if m.is_unlocked(Modifier.CAMO) and not m.get_ai().has_detection():
            mods.add(Modifier.CAMO)
        if m.is_unlocked(Modifier.REGROW):
            mods.add(Modifier.REGROW)
        if m.is_unlocked(Modifier.FORTIFIED) and t > 0.4 * DURATION:
            mods.add(Modifier.FORTIFIED)
        boss_share = self._boss_share * (BOT_SWARM_BOSSES if m.get_doctrine() is Doctrine.SWARM else 1.0)
        # push every push_seconds of income; once a bigger boss is affordable within BOT_SAVE_SECONDS, save up for it
        threshold = max(BOT_MIN_PUSH, m.income_rate() * self._push_seconds)
        window = min(BOT_SAVE_SECONDS, m.get_time_left() - BOT_LAST_CALL)
        for u in reversed(list(AttackUnit)):
            if u.is_boss() and m.is_unlocked(u):
                p = m.price(u, mods, 1) / boss_share
                if p <= m.get_credits() + m.income_rate() * max(0.0, window):
                    threshold = max(threshold, p)
                    break
        # the last call dumps everything, unless the AI is low enough for the overtime: then it saves for that push
        overtime_coming = not m.is_overtime() and m.get_game().get_lives() <= m.overtime_line()
        last_call = m.get_time_left() < BOT_LAST_CALL and not overtime_coming
        if m.get_credits() < threshold and not last_call:
            return
        lane = m.weakest_lane()
        boss_budget = m.get_credits() * boss_share
        units = list(AttackUnit)
        for u in reversed(units):
            if not u.is_boss() or not m.is_unlocked(u):
                continue
            p = m.price(u, mods, 1)
            n = jint(boss_budget / p)
            if n > 0:
                boss_budget -= p * m.send(u, mods, n, lane)
        for u in reversed(units):
            if m.get_queued() >= m.max_queue():
                break
            if u.is_boss() or not m.is_unlocked(u):
                continue
            n = jint(m.get_credits() / m.price(u, mods, 1))
            if n > 0:
                m.send(u, mods, min(n, 30), lane)

    def _exploits(self):
        m = self._match
        boss = None
        alive = 0
        lead = 0.0
        for e in m.get_game().get_enemy_manager().get_enemies():
            alive += 1
            lead = max(lead, e.get_distance() / e.get_route().get_total_length())
            if e.is_boss() and (boss is None or e.get_max_hp() > boss.get_max_hp()):
                boss = e
        if boss is None:
            if alive >= 12 and lead > 0.3 and m.ability_problem(AttackAbility.OVERCLOCK) is None:
                m.use_ability(AttackAbility.OVERCLOCK)
            return
        progress = boss.get_distance() / boss.get_route().get_total_length()
        if progress > 0.3 and m.ability_problem(AttackAbility.OVERCLOCK) is None:
            m.use_ability(AttackAbility.OVERCLOCK)
        if boss.get_hp_fraction() < 0.5 and m.ability_problem(AttackAbility.HOTFIX) is None:
            m.use_ability(AttackAbility.HOTFIX)
        if progress > 0.15 and m.ability_problem(AttackAbility.ZERO_DAY) is None:
            m.use_ability(AttackAbility.ZERO_DAY)

    @staticmethod
    def play(game_or_map, seed_or_bot=None, level=None, style=None, trace=False, doctrine=None):
        """play(map_index, seed, level, style[, doctrine=...]) or play(game, style_or_bot)."""
        from lindefense.sim.game import Game, State
        if isinstance(game_or_map, int):
            g = ReverseMatch.create(game_or_map, seed_or_bot, level, doctrine)
            bot = AttackerBot(g.get_reverse(), style)
        else:
            g = game_or_map
            bot = seed_or_bot if isinstance(seed_or_bot, AttackerBot) else AttackerBot(g.get_reverse(), seed_or_bot)
        r = g.get_reverse()
        max_ticks = jint((DURATION + OVERTIME + DRAIN + 10) / Game.DT)
        i = 0
        while i < max_ticks and g.get_state() is State.PLAYING:
            bot.tick(Game.DT)
            g.step(Game.DT)
            g.get_events().clear()
            i += 1
        from lindefense.tower import catalog
        o = Outcome()
        o.attacker_won = r.attacker_won()
        o.time = r.get_elapsed()
        o.defender_lives = g.get_lives()
        for t in g.get_tower_manager().get_player_towers():
            o.towers += 1
            if t.is_maxed():
                o.maxed += 1
            if t.get_type().is_hero():
                o.heroes += 1
            if catalog.ability_needs_unlock(t.get_type()) and not t.is_ability_locked():
                o.ability_unlocks += 1
        o.credits_spent = r.get_credits_spent()
        o.defender_earned = g.get_total_cash_earned()
        o.units_sent = r.get_units_bought()
        o.objectives = r.get_objectives_met()
        o.adaptations = len(r.get_adaptations())
        return o
