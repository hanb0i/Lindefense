"""Reverse mode, "Adversarial Training": the player attacks with compute credits and a DefenderAI defends for a
15-minute training run. Also the scripted AttackerBot used by tests, probes and the demo."""
import math
from collections import deque

from lindefense.ai.defender_ai import Action, DefenderAI, Options, Plan
from lindefense.ai.units import AttackAbility, AttackUnit, DefenderProfile, OVERCLOCK_SPEED, ZERO_DAY_TARGETS
from lindefense.enemy.types import Modifier
from lindefense.javacompat import jint, jpow, jround
from lindefense.jenum import EnumSet, JEnum
from lindefense.sim.difficulty import Difficulty

EPOCH_SECONDS = 60.0
EPOCHS = 15
DURATION = EPOCH_SECONDS * EPOCHS
OVERTIME = 60.0
START_CREDITS = 250
LEAK_BONUS_PER_LIFE = 8
HANDSHAKE = 15.0
SPAWN_GAP = 0.15
MAX_QUEUE = 150
COMPUTE_STEP = 4
COMPUTE_BASE_PRICE = 300
COMPUTE_PRICE_GROWTH = 1.28
COMPUTE_MAX = 8
PRESSURE_WINDOW = 20.0
CAMO_MEMORY = 30.0
FEED_SIZE = 40
TRACK_REFERENCE = 1800.0
TRACK_BONUS_MAX = 3.0
TRACK_EXP = 0.25
SPEED_EXP = 0.75
FUND_RATIO = 1.0
KILL_REWARD_SCALE = 1.0


class FeedEntry:
    def __init__(self, time, text, rgb, action, tower):
        self.time, self.text, self.rgb, self.action, self.tower = time, text, rgb, action, tower


class _Pending:
    __slots__ = ("unit", "mods", "route")

    def __init__(self, unit, mods, route):
        self.unit, self.mods, self.route = unit, mods, route


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


class ReverseMatch:
    EPOCH_SECONDS = EPOCH_SECONDS
    EPOCHS = EPOCHS
    DURATION = DURATION
    OVERTIME = OVERTIME
    MAX_QUEUE = MAX_QUEUE
    HANDSHAKE = HANDSHAKE
    COMPUTE_MAX = COMPUTE_MAX
    clock = staticmethod(clock)

    @staticmethod
    def create(map_or_index, seed, level):
        from lindefense.map import maps
        from lindefense.sim.game import Game
        gmap = maps.create(map_or_index) if isinstance(map_or_index, int) else map_or_index
        g = Game(gmap, seed, Difficulty.O1)
        g.set_reverse(ReverseMatch(g, DefenderProfile.of(Difficulty.O1 if level is None else level)))
        return g

    @staticmethod
    def restart(old):
        from lindefense.map import maps
        from lindefense.variance.variance import seed_next
        r = old.get_reverse()
        idx = maps.index_of(old.get_map())
        if r is None or idx < 0:
            raise ValueError("not a reverse-mode catalog game")
        g = ReverseMatch.create(idx, seed_next(), r._profile.level)
        g.get_reverse().set_unlimited_credits(r._unlimited)
        return g

    def __init__(self, game, profile):
        from lindefense.sim.game import Game
        self._game = game
        self._profile = profile
        self._credits = float(START_CREDITS)
        self._credits_earned = float(START_CREDITS)
        self._credits_spent = 0.0
        self._defender_funding = 0.0
        self._leak_bonus = 0.0
        self._compute_level = 0
        self._track_bonus = track_bonus(game.get_map())
        self._track_speed = track_speed(game.get_map())
        self._elapsed = 0.0
        self._epochs_done = 0
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
        self._uplink_closed = False
        game.set_starting_lives(profile.integrity)
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
        o.pressure_window = PRESSURE_WINDOW
        self._ai = DefenderAI(game, o)
        self._ai.set_listener(self._on_ai_action)
        self._announced = {u for u in AttackUnit if u.unlock_at <= 0}
        self._announced_mods = set()
        self._announced_abilities = set()

    # ---- accessors
    def get_game(self):
        return self._game

    def get_profile(self):
        return self._profile

    def get_level(self):
        return self._profile.level

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

    def unit_hp_scale(self, type_):
        """The match's health factor (the BAD included: the campaign's per-mode Palantir multiplier is a final-boss
        rule, not a reverse-mode one) times the unit's own factor from the unit table."""
        u = AttackUnit.of(type_)
        return self._game.get_wave_hp_scale() * self._profile.unit_hp * (1.0 if u is None else u.hp_factor())

    def get_defender_funding(self):
        return self._defender_funding

    def get_elapsed(self):
        return self._elapsed

    def get_time_left(self):
        return max(0.0, DURATION - self._elapsed)

    def get_overtime_left(self):
        return max(0.0, DURATION + OVERTIME - self._elapsed) if self._uplink_closed else OVERTIME

    def get_epoch(self):
        return min(EPOCHS, self._epochs_done + 1)

    def get_epochs_done(self):
        return self._epochs_done

    def is_uplink_closed(self):
        return self._uplink_closed

    def has_unlimited_credits(self):
        return self._unlimited

    def set_unlimited_credits(self, u):
        self._unlimited = u

    def get_compute_level(self):
        return self._compute_level

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

    def attacker_won(self):
        from lindefense.sim.game import State
        return self._game.get_state() is State.DEFEAT

    def defender_held(self):
        from lindefense.sim.game import State
        return self._game.get_state() is State.VICTORY

    def income_rate(self):
        return (self.base_income() * self._track_bonus + COMPUTE_STEP * self._compute_level) * self._profile.attacker_income

    def get_track_bonus(self):
        return self._track_bonus

    def get_track_speed(self):
        return self._track_speed

    def base_income(self):
        m = min(self._elapsed, DURATION) / 60.0
        return 12 + 10 * m + 0.5 * m * m

    def defender_funding_rate(self):
        return self.base_income() * FUND_RATIO * self._profile.income

    def kill_reward_scale(self):
        return KILL_REWARD_SCALE

    def equivalent_wave(self):
        return 1 + jint(min(99.0, self._elapsed / DURATION * 99))

    # ---- unlocks
    def is_unlocked(self, x):
        if isinstance(x, AttackUnit) or isinstance(x, AttackAbility):
            return self._elapsed >= x.unlock_at
        return self._elapsed >= AttackUnit.modifier_unlock_at(x)

    def unlocks_in(self, u):
        return max(0.0, u.unlock_at - self._elapsed)

    def effective_modifiers(self, u, mods):
        m = EnumSet()
        if mods is None or not u.accepts_modifiers():
            return m
        for x in mods:
            if self.is_unlocked(x):
                m.add(x)
        return m

    def price(self, u, mods, count):
        return u.price_with(self.effective_modifiers(u, mods)) * max(1, count)

    # ---- attacker actions
    def send_problem(self, u, mods, count):
        from lindefense.sim.game import State
        if self._game.get_state() is not State.PLAYING:
            return "Match over"
        if self._uplink_closed:
            return "Uplink closed"
        if not self.is_unlocked(u):
            return "Unlocks at " + clock(u.unlock_at)
        if len(self._queue) >= MAX_QUEUE:
            return "Uplink queue full"
        if not self._unlimited and self._credits < self.price(u, mods, 1):
            return "Not enough credits"
        return None

    def send(self, u, mods, count, route):
        if self.send_problem(u, mods, 1) is not None:
            return 0
        m = self.effective_modifiers(u, mods)
        each = u.price_with(m)
        routes = len(self._game.get_map().get_routes())
        lane = -1 if route >= routes else route
        n = 0
        while n < max(1, count) and len(self._queue) < MAX_QUEUE and (self._unlimited or self._credits >= each):
            self._spend(each)
            self._queue.append(_Pending(u, m.copy(), lane))
            n += 1
        self._units_bought += n
        if u.is_boss():
            self._bosses_sent += n
        return n

    def compute_price(self):
        return jint(jround(COMPUTE_BASE_PRICE * jpow(COMPUTE_PRICE_GROWTH, self._compute_level)))

    def compute_problem(self):
        from lindefense.sim.game import State
        if self._game.get_state() is not State.PLAYING:
            return "Match over"
        if self._uplink_closed:
            return "Uplink closed"
        if self._compute_level >= COMPUTE_MAX:
            return "Fully scaled"
        if not self._unlimited and self._credits < self.compute_price():
            return "Not enough credits"
        return None

    def scale_compute(self):
        if self.compute_problem() is not None:
            return False
        self._spend(self.compute_price())
        self._compute_level += 1
        self._feed_line("Compute scaled to +" + str(COMPUTE_STEP * self._compute_level) + "/s", 0xffd166, None, None)
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
            return "Unlocks at " + clock(a.unlock_at)
        if self.cooldown_left(a) > 0:
            return "Recharging (" + str(jint(math.ceil(self.cooldown_left(a)))) + "s)"
        if not self._unlimited and self._credits < a.cost:
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
        self._spend(a.cost)
        self._cooldowns[a] = a.cooldown
        self._uses[a] = self.get_uses(a) + 1
        if a is AttackAbility.OVERCLOCK:
            if self._overclock_left <= 0:
                g.set_global_enemy_speed_multiplier(g.get_global_enemy_speed_multiplier() * OVERCLOCK_SPEED)
            self._overclock_left = a.duration
            g.set_banner("OVERCLOCK: UNITS +50% SPEED", 0xff2bd6, 2)
        elif a is AttackAbility.HOTFIX:
            n = 0
            for e in g.get_enemy_manager().get_enemies():
                if not e.is_alive() or e.get_hp() >= e.get_max_hp():
                    continue
                e.heal(e.get_max_hp())
                g.emit_text(e.get_position(), "+HP", 0x3bff8a)
                n += 1
            g.set_banner("HOTFIX: " + str(n) + " UNITS RESTORED", 0x3bff8a, 2)
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
                g.emit_text(t.get_position(), "JAMMED", 0xff4d4d)
                jammed += 1
            g.set_banner("ZERO-DAY: " + str(jammed) + " TOWER" + ("" if jammed == 1 else "S") + " JAMMED", 0xff4d4d, 2)
        self._feed_line("Exploit: " + a.display_name, 0xff2bd6, None, None)
        return True

    def _spend(self, amount):
        if not self._unlimited:
            self._credits -= amount
        self._credits_spent += amount

    # ---- simulation hooks
    def update(self, dt):
        from lindefense.sim.game import State
        g = self._game
        if g.get_state() is not State.PLAYING:
            return
        self._elapsed += dt
        if not self._uplink_closed:
            inc = self.income_rate() * dt
            self._credits += inc
            self._credits_earned += inc
            fund = self.defender_funding_rate() * dt
            g.add_cash(fund, None)
            self._defender_funding += fund
        while self._epochs_done < EPOCHS and self._elapsed >= (self._epochs_done + 1) * EPOCH_SECONDS:
            self._end_epoch()
        self._announce_unlocks()
        if self._elapsed >= HANDSHAKE:
            self._spawn_timer -= dt
        while self._spawn_timer <= 0 and self._queue and self._elapsed >= HANDSHAKE:
            p = self._queue.popleft()
            e = g.get_enemy_manager().spawn_scaled(p.unit.type, p.mods, p.route, 0, self.unit_hp_scale(p.unit.type),
                                                   g.get_wave_speed_scale() * self._track_speed)
            if e is not None:
                self._units_spawned += 1
            self._spawn_timer += SPAWN_GAP
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
        self._think_timer -= dt
        if self._think_timer <= 0:
            self._think_timer += self._profile.think_interval
            self._ai.manage()
        if not self._uplink_closed and self._elapsed >= DURATION:
            self._uplink_closed = True
            g.set_banner("TRAINING RUN OVER  -  UPLINK CLOSED", 0xffd166, 3)
            self._feed_line("Uplink closed: overtime for units already sent", 0xffd166, None, None)
        if (self._uplink_closed and g.get_state() is State.PLAYING
                and ((not self._queue and g.get_enemy_manager().is_empty()) or self._elapsed >= DURATION + OVERTIME)):
            self._feed_line("Defender held with " + str(g.get_lives()) + " integrity", 0x7fd8a8, None, None)
            g.declare_defender_victory("THE DEFENDER AI HELD THE LINE")

    def on_leak(self, lives, leaker):
        if lives <= 0:
            return
        self._leaks += 1
        self._lives_taken += lives
        bonus = LEAK_BONUS_PER_LIFE * lives * self._profile.attacker_income
        self._credits += bonus
        self._credits_earned += bonus
        self._leak_bonus += bonus

    def _end_epoch(self):
        g = self._game
        self._epochs_done += 1
        research = 0.0
        for t in list(g.get_tower_manager().get_towers()):
            research += t.get_behavior().on_round_end(g, t)
        if research > 0:
            g.add_cash(research, None)
        g.add_pop_value(-g.get_round_pop_value())
        self._feed_line("Epoch " + str(self._epochs_done) + " / " + str(EPOCHS) + " complete"
                        + ("  (AI research +$" + str(jint(research)) + ")" if research > 0 else ""), 0x9fb3c8, None, None)

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
        if not names:
            return
        head = ", ".join(names[:3]) + " +" + str(len(names) - 3) if len(names) > 3 else ", ".join(names)
        self._game.set_banner("UNLOCKED: " + head.upper(), 0xff2bd6, 3)
        self._feed_line("Unlocked: " + ", ".join(names), 0xff2bd6, None, None)

    def _camo_alarm(self):
        if self._elapsed - self._last_camo_seen <= CAMO_MEMORY:
            return True
        return self._profile.anticipates_camo and (self.is_unlocked(Modifier.CAMO) or self.is_unlocked(AttackUnit.DDT))

    def _on_ai_action(self, a, t, text):
        if a is Action.BUILD:
            rgb = 0x00f0ff
        elif a is Action.UPGRADE:
            rgb = 0x3bff8a
        elif a is Action.HERO_UNLOCK or a is Action.HERO_DEPLOY:
            rgb = 0xffd166
        elif a is Action.ABILITY_UNLOCK:
            rgb = 0xff2bd6
        else:
            rgb = 0xb48cff
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


DEFAULT_PUSH_SECONDS = 75.0
DEFAULT_BOSS_SHARE = 0.8


class Outcome:
    def __init__(self):
        self.attacker_won = False
        self.time = 0.0
        self.defender_lives = self.towers = self.maxed = self.heroes = self.ability_unlocks = 0
        self.credits_spent = self.defender_earned = 0.0
        self.units_sent = 0

    def __repr__(self):
        from lindefense.ui import jrt as _j   # String.format: %.0f rounds half up, like Java
        return _j.format("%s at %s  lives %3d  towers %2d (maxed %2d, heroes %d, abilities %d)  spent %7.0f  AI earned %7.0f  units %5d",
                         "ATTACKER WINS" if self.attacker_won else "DEFENDER HOLDS", clock(self.time), self.defender_lives, self.towers,
                         self.maxed, self.heroes, self.ability_unlocks, self.credits_spent, self.defender_earned, self.units_sent)


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
        if t < 240 and m.get_compute_level() < 4 and m.compute_problem() is None:
            m.scale_compute()
            return
        self._exploits()
        last_call = t > DURATION - 40
        threshold = max(400.0, m.income_rate() * self._push_seconds)
        if m.get_credits() < threshold and not last_call:
            return
        mods = EnumSet()
        if m.is_unlocked(Modifier.CAMO) and not m.get_ai().has_detection():
            mods.add(Modifier.CAMO)
        if m.is_unlocked(Modifier.REGROW):
            mods.add(Modifier.REGROW)
        if m.is_unlocked(Modifier.FORTIFIED) and t > 360:
            mods.add(Modifier.FORTIFIED)
        lane = self._weakest_lane()
        boss_budget = m.get_credits() * self._boss_share
        units = list(AttackUnit)
        for u in reversed(units):
            if not u.is_boss() or not m.is_unlocked(u):
                continue
            p = m.price(u, mods, 1)
            n = jint(boss_budget / p)
            if n > 0:
                boss_budget -= p * m.send(u, mods, n, lane)
        for u in reversed(units):
            if m.get_queued() >= MAX_QUEUE:
                break
            if u.is_boss() or not m.is_unlocked(u):
                continue
            n = jint(m.get_credits() / m.price(u, mods, 1))
            if n > 0:
                m.send(u, mods, min(n, 30), lane)

    def _weakest_lane(self):
        g = self._match.get_game()
        routes = g.get_map().get_routes()
        if len(routes) < 2:
            return -1
        best = -1
        best_cover = 1.7976931348623157e308
        towers = g.get_tower_manager().get_player_towers()
        for r, p in enumerate(routes):
            cover = 0.0
            d = 0.0
            while d < p.get_total_length():
                v = p.position_at(d)
                for tw in towers:
                    rng = tw.get_stats().range
                    if rng >= 1000 or tw.get_position().dist_sq(v) <= rng * rng:
                        cover += 1 + tw.get_tier()
                d += 40
            cover /= max(1.0, p.get_total_length())
            if cover < best_cover:
                best_cover = cover
                best = r
        return best

    def _exploits(self):
        m = self._match
        boss = None
        for e in m.get_game().get_enemy_manager().get_enemies():
            if e.is_boss() and (boss is None or e.get_max_hp() > boss.get_max_hp()):
                boss = e
        if boss is None:
            return
        progress = boss.get_distance() / boss.get_route().get_total_length()
        if progress > 0.3 and m.ability_problem(AttackAbility.OVERCLOCK) is None:
            m.use_ability(AttackAbility.OVERCLOCK)
        if boss.get_hp_fraction() < 0.5 and m.ability_problem(AttackAbility.HOTFIX) is None:
            m.use_ability(AttackAbility.HOTFIX)
        if progress > 0.15 and m.ability_problem(AttackAbility.ZERO_DAY) is None:
            m.use_ability(AttackAbility.ZERO_DAY)

    @staticmethod
    def play(game_or_map, seed_or_bot=None, level=None, style=None, trace=False):
        """play(map_index, seed, level, style) or play(game, style_or_bot)."""
        from lindefense.sim.game import Game, State
        if isinstance(game_or_map, int):
            g = ReverseMatch.create(game_or_map, seed_or_bot, level)
            bot = AttackerBot(g.get_reverse(), style)
        else:
            g = game_or_map
            bot = seed_or_bot if isinstance(seed_or_bot, AttackerBot) else AttackerBot(g.get_reverse(), seed_or_bot)
        r = g.get_reverse()
        max_ticks = jint((DURATION + OVERTIME + 10) / Game.DT)
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
        return o
