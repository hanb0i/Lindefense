"""Headless balance probe: the scripted near-optimal DefenderAI plays the campaign on every map.

Usage: python -m lindefense.tools.auto_player [maxWave] [mapIdx] [verbose]
       python -m lindefense.tools.auto_player campaign [level ...]   (campaign levels: the bot may only build the
       level's unlocked towers, heroes only once the Hero Store is open; BOT_SEED / BOT_SEEDS pick the seeds)
Environment: BOT_DIFFICULTY=O1|ON|ON2|ONN, BOT_SEED=N, BOT_SEEDS=K, BOT_MAX_MINUTES=N, BOT_MAX_TOWERS=N,
BOT_RANDOM=true, BOT_VARIANCE=random|first, BOT_OPEN=TYPE:copy:tier,..., BOT_DUMP=true, BOT_DUMP_WAVE=N,
BOT_REPORT_EVERY=N, BOT_FREEPLAY=true (after winning, continue into Freeplay until lives run out or maxWave; pass a
maxWave above 100, e.g. 200), BOT_ABILITIES=MIN:PER (buy $15,000 ability unlocks like a player: the first once MIN
towers stand, then one more per PER further towers; ABILITY_POLICY is the calibrated default when the value is just
"true").
"""
import os
import sys

from lindefense.ai.defender_ai import DefenderAI, Options, Plan, Step
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.tower.tower_type import TowerType
from lindefense.ui import jrt as _j
from lindefense.variance.variance import Picker


def _env(name, default=None):
    v = os.environ.get(name)
    return default if v is None or v == "" else v


def _env_int(name, default):
    try:
        return int(_env(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name):
    return str(_env(name, "")).lower() == "true"


def _ddiv(a, b):
    """Java double division (x / 0.0 is Infinity or NaN, not ZeroDivisionError)."""
    if b != 0:
        return a / b
    return float("nan") if a == 0 or a != a else float("inf") if a > 0 else float("-inf")


def _variance_picker(s):
    if s is None or s == "" or s.lower() in ("false", "off"):
        return None
    return Picker.FIRST if s.lower() == "first" else Picker.RANDOM


class Result:
    def __init__(self):
        self.state = None
        self.completed = self.lives = self.towers = self.maxed = 0
        self.cash = self.earned = 0.0
        self.map = None
        self.game = None

    def won(self):
        return self.state is State.VICTORY


def _variance_summary(g):
    if g is None or not g.get_variance().is_enabled():
        return ""
    return "  notes %s  news %d" % (",".join(p.name for p in g.get_variance().get_active()), len(g.get_variance().get_news_log()))


def bot_difficulty():
    d = Difficulty.parse(os.environ.get("BOT_DIFFICULTY"))
    return d if d is not None else Difficulty.default_mode()


def _count_maxed(g):
    return sum(1 for t in g.get_tower_manager().get_player_towers() if t.is_maxed())


ABILITY_POLICY = (60, 10)


def ability_policy(s):
    """BOT_ABILITIES value -> (min towers, towers per further unlock), or None to never unlock."""
    if s is None or s == "" or s.lower() in ("false", "off", "0"):
        return None
    if ":" in s:
        a, b = s.split(":", 1)
        return int(a), int(b)
    return ABILITY_POLICY


def run(map_idx, seed, diff, max_waves, max_towers=999, random=False, report=False, mixed=False, abilities=None):
    """Plays one campaign (or up to max_waves) and returns the outcome. abilities=(min towers, towers per unlock) lets the
    bot buy ability unlocks (default: BOT_ABILITIES, else never)."""
    dump = _env_bool("BOT_DUMP")
    dump_wave = _env_int("BOT_DUMP_WAVE", -1)
    report_every = _env_int("BOT_REPORT_EVERY", 10)
    opt = Options()
    opt.plan = Plan.MIXED if (mixed or random) else Plan.EFFICIENT
    opt.max_towers = max_towers
    opt.random_placement = random
    opt.verbose = dump
    pol = abilities if abilities is not None else ability_policy(os.environ.get("BOT_ABILITIES"))
    if pol is not None:
        opt.unlock_abilities = True
        opt.boss_focus = True
        opt.unlock_min_towers, opt.unlock_towers_per = pol
    opening = os.environ.get("BOT_OPEN")
    if opening:
        pl = []
        for tok in opening.split(","):
            f = tok.split(":")
            pl.append(Step(TowerType.value_of(f[0]), int(f[1]), int(f[2]), 1))
        opt.opening = pl
    g = Game(maps.create(map_idx), seed, diff)
    picker = _variance_picker(os.environ.get("BOT_VARIANCE"))
    if picker is not None:
        g.get_variance().enable(picker)
    ai = DefenderAI(g, opt)
    ticks = last_report = 0
    snap = None
    max_ticks = 60 * 60 * _env_int("BOT_MAX_MINUTES", 90)
    tm = g.get_tower_manager()
    freeplay = _env_bool("BOT_FREEPLAY")
    while ticks < max_ticks:
        if g.get_state() is not State.PLAYING:
            if freeplay and g.continue_freeplay():
                continue
            break
        if ticks % 15 == 0:
            ai.manage()
        if g.get_wave_manager().can_start_next_wave():
            if g.get_wave() < max_waves:
                g.start_next_wave()
            else:
                break
        if dump_wave > 0 and g.get_wave() == dump_wave and snap is None:
            snap = {t.get_id(): t.get_damage_dealt() for t in tm.get_player_towers()}
        if dump_wave > 0 and g.get_last_completed_wave() == dump_wave and snap is not None:
            tot = 0.0
            for t in tm.get_player_towers():
                d = t.get_damage_dealt() - snap.get(t.get_id(), 0.0)
                tot += d
                print(_j.format("      w%d %-22s tier %d dmg %8.0f", dump_wave, t.get_type(), t.get_tier(), d))
            print(_j.format("      total %.0f", tot))
            snap, dump_wave = None, -1
        lives_before = g.get_lives()
        nearest = None
        if dump:
            for e in g.get_enemy_manager().get_enemies():
                if nearest is None or e.get_remaining_distance() < nearest.get_remaining_distance():
                    nearest = e
        g.step(Game.DT)
        if dump and g.get_lives() < lives_before and nearest is not None:
            print(_j.format("      leak w%d -%d lives: %s %s hpScale %.2f", g.get_wave(), lives_before - g.get_lives(), nearest.get_type(),
                            nearest.get_modifiers(), nearest.get_hp_scale()))
        g.get_events().clear()
        ticks += 1
        lc = g.get_last_completed_wave()
        if report and lc != last_report and lc % report_every == 0:
            last_report = lc
            print(_j.format("    after wave %3d: lives %3d cash %7.0f towers %2d (maxed: %d)",
                            lc, g.get_lives(), g.get_cash(), len(tm.get_player_towers()), _count_maxed(g)))
    if dump:
        agg = {}
        for t in tm.get_player_towers():
            a = agg.setdefault(t.get_type(), [0.0, 0.0, 0.0])
            a[0] += t.get_invested_cost()
            a[1] += t.get_damage_dealt()
            a[2] += t.get_kills()
        for k in sorted(agg, key=lambda k: k.ordinal):
            a = agg[k]
            print(_j.format("      SUM %-24s cost %8.0f dmg %10.0f dmg/$ %6.2f kills %6.0f", k, a[0], a[1], _ddiv(a[1], a[0]), a[2]))
        print("      wave %d alive %d" % (g.get_wave(), g.get_enemy_manager().get_alive_count()))
    r = Result()
    r.state = g.get_state()
    r.completed = g.get_last_completed_wave()
    r.lives = g.get_lives()
    r.cash = g.get_cash()
    r.earned = g.get_total_cash_earned()
    r.towers = len(tm.get_player_towers())
    r.maxed = _count_maxed(g)
    r.map = g.get_map().get_name()
    r.game = g
    return r


def _camo_ahead(g):
    """Campaign levels: camo in the current wave or the next two of the level (the bot's camo look-ahead)."""
    from lindefense.enemy.types import Modifier
    c = g.get_campaign()
    n = g.get_wave()
    for w in range(max(1, n), n + 3):
        if w <= c.wave_count():
            for gr in c.wave(w).groups:
                if Modifier.CAMO in gr.modifiers or gr.type.has_innate_camo():
                    return True
    return False


def campaign_options(g):
    """The balance bot's Options for a campaign Game: the level's towers only (heroes once the Hero Store is open,
    ability unlocks once they are allowed, with the classic ABILITY_POLICY), plan thresholds on the base waves the
    level plays, camo look-ahead over the level's own waves."""
    c = g.get_campaign()
    opt = Options()
    opt.plan = Plan.EFFICIENT
    allowed = set(c.allowed)
    if c.heroes:
        allowed.update(TowerType.heroes())
    opt.allowed = allowed
    opt.wave_source = lambda: c.base_wave(max(1, g.get_wave()))   # before wave 1: the level's first base wave
    opt.camo_alarm = lambda: _camo_ahead(g)
    if c.abilities:   # once the level allows $15,000 ability unlocks, the bot buys them like in the classic calibration
        opt.unlock_abilities = True
        opt.boss_focus = True
        opt.unlock_min_towers, opt.unlock_towers_per = ABILITY_POLICY
    return opt


SETUP_ACTIONS = 600


def setup_phase(ai, limit=SETUP_ACTIONS):
    """Before wave 1 a player spends the starting cash: the bot keeps buying (one action per manage() pass) until it
    stops acting (out of cash, or saving up for its next step). Returns the number of actions."""
    n = 0
    while n < limit:
        before = ai.get_action_count()
        ai.manage()
        if ai.get_action_count() == before:
            break
        n += 1
    return n


def run_level(level, seed, start_cash=None, max_minutes=120, hp=None):
    """Plays one campaign level (Level, id or 1-based index) with the bot and returns a Result (lives, waves cleared,
    game time in result.game.get_time()). start_cash and hp=(first, last wave health multiplier) override the level's
    BALANCE entry (calibration probes only; the level's own values are in sim/campaign.py)."""
    from lindefense.sim import campaign
    g = campaign.new_game(level, seed)
    if start_cash is not None:
        g._cash = float(start_cash)
    if hp is not None:
        g.get_campaign().hp, g.get_campaign().hp_end = float(hp[0]), float(hp[1])
    ai = DefenderAI(g, campaign_options(g))
    setup_phase(ai)
    ticks = 0
    max_ticks = 60 * 60 * max_minutes
    while ticks < max_ticks and g.get_state() is State.PLAYING:
        if ticks % 15 == 0:
            ai.manage()
        if g.get_wave_manager().can_start_next_wave():
            g.start_next_wave()
        g.step(Game.DT)
        g.get_events().clear()
        ticks += 1
    r = Result()
    r.state = g.get_state()
    r.completed = g.get_last_completed_wave()
    r.lives = g.get_lives()
    r.cash = g.get_cash()
    r.earned = g.get_total_cash_earned()
    r.towers = len(g.get_tower_manager().get_player_towers())
    r.maxed = _count_maxed(g)
    r.map = g.get_map().get_name()
    r.game = g
    return r


def campaign_main(args):
    from lindefense.sim import campaign
    seed0 = _env_int("BOT_SEED", 1234)
    seeds = _env_int("BOT_SEEDS", 2)
    pick = [campaign.level(int(a) if a.isdigit() else a) for a in args] or list(campaign.LEVELS)
    for lv in pick:
        for k in range(seeds):
            r = run_level(lv, seed0 + k * 766)
            pal = r.game.get_palantir()
            route = ("  palantir reached %2.0f%% of its route" % (100.0 * pal.get_distance() / pal.get_route().get_total_length())
                     if pal is not None else "")
            print("[campaign] %2d %-22s %-22s waves %2d cash %6d lives %3d hp %.3g-%.3g seed %-5d %-7s cleared %2d "
                  "lives %3d time %5.0fs towers %3d%s" % (lv.index, lv.title, r.map, lv.wave_count(), lv.start_cash,
                                                          lv.start_lives, lv.hp_range()[0], lv.hp_range()[1], seed0 + k * 766,
                                                          r.state, r.completed, r.lives, r.game.get_time(), r.towers, route),
                  flush=True)


class AutoPlayer:
    """Class-style entry points used by the ported UI (demo / tooling)."""
    Result = Result
    run = staticmethod(run)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "campaign":
        campaign_main(args[1:])
        return
    max_waves = int(args[0]) if len(args) > 0 else 100
    only = int(args[1]) if len(args) > 1 else -1
    verbose = len(args) > 2
    seed0 = _env_int("BOT_SEED", 1234)
    seeds = _env_int("BOT_SEEDS", 1)
    d = bot_difficulty()
    for m in range(maps.MAP_COUNT):
        if only >= 0 and only != m:
            continue
        for k in range(seeds):
            r = run(m, seed0 + k, d, max_waves, _env_int("BOT_MAX_TOWERS", 999), _env_bool("BOT_RANDOM"), verbose or seeds == 1)
            print(_j.format("[%s] %-22s seed %-5d %-7s completed %3d lives %3d cash %7.0f earned %7.0f towers %2d maxed %2d%s%s",
                             d.label, r.map, seed0 + k, r.state, r.completed, r.lives, r.cash, r.earned, r.towers, r.maxed,
                             _variance_summary(r.game), ("  freeplay: reached wave %d" % r.game.get_wave()) if r.game.is_freeplay() else ""))


if __name__ == "__main__":
    main()
