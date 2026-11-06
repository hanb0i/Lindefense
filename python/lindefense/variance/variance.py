"""Run variance: Patch Notes (drafted run modifiers), Breaking News (one-wave events), the knobs they change, seeds,
and RunVariance, which the economy / combat / tower / wave code consults through its hooks. Off by default."""
import math
import os
import time

from lindefense.javacompat import jint, jround, wrap64
from lindefense.jenum import JEnum
from lindefense.sim.rng import Rng

_INF = float("inf")


# ====================================================================== Knob
class Op(JEnum):
    MUL = ()
    ADD = ()
    FLAG = ()


class Knob(JEnum):
    TOWER_COST = (Op.MUL, False, 0.6, 1.3)
    UPGRADE_COST = (Op.MUL, False, 0.6, 1.3)
    ABILITY_UNLOCK_COST = (Op.MUL, False)
    SELL_REFUND = (Op.ADD, True)
    KILL_INCOME = (Op.MUL, True, 0.75, _INF)
    WAVE_BONUS = (Op.MUL, True)
    INTEREST_RATE = (Op.ADD, True)
    INTEREST_CAP = (Op.ADD, True)
    DAMAGE = (Op.MUL, True, 0.8, _INF)
    BOSS_DAMAGE = (Op.MUL, True)
    NON_BOSS_DAMAGE = (Op.MUL, True)
    ELITE_DAMAGE = (Op.MUL, True)
    PLAIN_DAMAGE = (Op.MUL, True)
    FIRE_RATE = (Op.MUL, True, 0.8, _INF)
    RANGE = (Op.MUL, True)
    ABILITY_COOLDOWN = (Op.MUL, False)
    ENEMY_HP = (Op.MUL, False)
    ENEMY_SPEED = (Op.MUL, False)
    ENEMY_COUNT = (Op.MUL, False)
    SPAWN_GAP = (Op.MUL, True)
    ALL_CAMO = (Op.FLAG, False)
    CLOSE_LANE = (Op.FLAG, False)
    LIVES_PER_WAVE = (Op.ADD, True)
    LEAK_LIVES = (Op.MUL, False)
    FREE_FIRST_UPGRADE = (Op.FLAG, True)
    REFRESH_ABILITIES = (Op.FLAG, True)
    CASH_NOW = (Op.ADD, True)
    CASH_PER_WAVE = (Op.ADD, True)

    def _init(self, op, good, mn=-_INF, mx=_INF):
        self.op = op
        self.good = good
        self.min = mn
        self.max = mx

    def neutral(self):
        return 1.0 if self.op is Op.MUL else 0.0

    def combine(self, a, b):
        if self.op is Op.MUL:
            return a * b
        if self.op is Op.ADD:
            return a + b
        return max(a, b)

    def helps(self, value):
        n = self.neutral()
        if value == n:
            return False
        return (value > n) == self.good


_KNOBS = list(Knob)


# ====================================================================== Mods
class Effect:
    def __init__(self, text, good):
        self.text = text
        self.good = good

    def __repr__(self):
        return ("+ " if self.good else "- ") + self.text


def _pct(mult):
    return str(jround(abs(mult - 1) * 100)) + "%"


def _less_more(mult):
    return _pct(mult) + (" less" if mult < 1 else " more")


def _signed(mult):
    return ("+" if mult >= 1 else "-") + _pct(mult)


def _money(v):
    return "$" + "{:,}".format(jround(v))


class Mods:
    NONE = None

    def __init__(self):
        self._v = [k.neutral() for k in _KNOBS]
        self._frozen = False

    @staticmethod
    def of():
        return Mods()

    def set(self, k, value):
        if self._frozen:
            raise RuntimeError("Mods.NONE is immutable")
        self._v[k.ordinal] = float(value)
        return self

    def flag(self, k):
        return self.set(k, 1)

    def get(self, k):
        return self._v[k.ordinal]

    def has(self, k):
        return self._v[k.ordinal] != k.neutral()

    def is_neutral(self):
        return not any(self.has(k) for k in _KNOBS)

    def combine(self, o):
        m = Mods()
        m._v = [k.combine(self._v[k.ordinal], o._v[k.ordinal]) for k in _KNOBS]
        return m

    def clamped(self):
        m = Mods()
        m._v = [max(k.min, min(k.max, self._v[k.ordinal])) for k in _KNOBS]
        return m

    def cash_for(self, wave):
        return jint(jround(self.get(Knob.CASH_NOW) + self.get(Knob.CASH_PER_WAVE) * max(0, wave - 1)))

    def upsides(self, wave):
        return [e for e in self.effects(wave) if e.good]

    def downsides(self, wave):
        return [e for e in self.effects(wave) if not e.good]

    def effects(self, wave):
        from lindefense.tower.shop import SELL_FRACTION
        out = []
        g, h = self.get, self.has

        def add(k, text):
            out.append(Effect(text, k.helps(g(k))))

        K = Knob
        if h(K.TOWER_COST) and g(K.TOWER_COST) == g(K.UPGRADE_COST):
            add(K.TOWER_COST, "Towers and upgrades cost " + _less_more(g(K.TOWER_COST)))
        else:
            if h(K.TOWER_COST):
                add(K.TOWER_COST, "Towers cost " + _less_more(g(K.TOWER_COST)))
            if h(K.UPGRADE_COST):
                add(K.UPGRADE_COST, "Upgrades cost " + _less_more(g(K.UPGRADE_COST)))
        if h(K.ABILITY_UNLOCK_COST):
            add(K.ABILITY_UNLOCK_COST, "Ability unlocks cost " + _less_more(g(K.ABILITY_UNLOCK_COST)))
        if h(K.SELL_REFUND):
            base = SELL_FRACTION
            now = max(0.0, min(MAX_SELL_FRACTION, base + g(K.SELL_REFUND)))
            add(K.SELL_REFUND, "Sell refund " + str(jround(base * 100)) + "% -> " + str(jround(now * 100)) + "%")
        if h(K.KILL_INCOME) and g(K.KILL_INCOME) == g(K.WAVE_BONUS):
            add(K.KILL_INCOME, "Income " + _signed(g(K.KILL_INCOME)) + " (kills and wave bonus)")
        else:
            if h(K.KILL_INCOME):
                add(K.KILL_INCOME, "Kills pay " + _less_more(g(K.KILL_INCOME)))
            if h(K.WAVE_BONUS):
                add(K.WAVE_BONUS, "No wave-clear bonus" if g(K.WAVE_BONUS) <= 0 else "Wave-clear bonus " + _signed(g(K.WAVE_BONUS)))
        if h(K.INTEREST_RATE):
            cap = " (max " + _money(g(K.INTEREST_CAP)) + ")" if h(K.INTEREST_CAP) else ""
            add(K.INTEREST_RATE, "Banked credits earn " + str(jround(g(K.INTEREST_RATE) * 100)) + "% interest per wave cleared" + cap)
        cash = self.cash_for(wave)
        if cash != 0:
            out.append(Effect(("+" if cash > 0 else "-") + _money(abs(cash)) + " credits now", cash > 0))
        if h(K.DAMAGE):
            add(K.DAMAGE, "Towers deal " + _less_more(g(K.DAMAGE)) + " damage")
        if h(K.BOSS_DAMAGE):
            add(K.BOSS_DAMAGE, _signed(g(K.BOSS_DAMAGE)) + " damage vs bosses")
        if h(K.NON_BOSS_DAMAGE):
            add(K.NON_BOSS_DAMAGE, _signed(g(K.NON_BOSS_DAMAGE)) + " damage vs non-boss enemies")
        if h(K.ELITE_DAMAGE):
            add(K.ELITE_DAMAGE, _signed(g(K.ELITE_DAMAGE)) + " damage vs Camo, Regrow and Fortified enemies")
        if h(K.PLAIN_DAMAGE):
            add(K.PLAIN_DAMAGE, _signed(g(K.PLAIN_DAMAGE)) + " damage vs unmodified enemies")
        if h(K.FIRE_RATE):
            add(K.FIRE_RATE, "Towers fire " + _pct(g(K.FIRE_RATE)) + (" faster" if g(K.FIRE_RATE) > 1 else " slower"))
        if h(K.RANGE):
            add(K.RANGE, "Tower range " + _signed(g(K.RANGE)))
        if h(K.ABILITY_COOLDOWN):
            add(K.ABILITY_COOLDOWN, "Ability cooldowns " + _signed(g(K.ABILITY_COOLDOWN)))
        if h(K.REFRESH_ABILITIES):
            add(K.REFRESH_ABILITIES, "Every ability cooldown resets when the wave starts")
        if h(K.FREE_FIRST_UPGRADE):
            add(K.FREE_FIRST_UPGRADE, "New shop towers arrive with their first upgrade free")
        if h(K.ENEMY_HP):
            add(K.ENEMY_HP, "Enemies have " + _less_more(g(K.ENEMY_HP)) + " HP")
        if h(K.ENEMY_SPEED):
            add(K.ENEMY_SPEED, "Enemies move " + _pct(g(K.ENEMY_SPEED)) + (" faster" if g(K.ENEMY_SPEED) > 1 else " slower"))
        if h(K.ENEMY_COUNT):
            add(K.ENEMY_COUNT, _pct(g(K.ENEMY_COUNT)) + (" more" if g(K.ENEMY_COUNT) > 1 else " fewer") + " enemies")
        if h(K.SPAWN_GAP):
            add(K.SPAWN_GAP, "Enemies spawn " + _pct(g(K.SPAWN_GAP)) + (" closer together" if g(K.SPAWN_GAP) < 1 else " further apart"))
        if h(K.ALL_CAMO):
            add(K.ALL_CAMO, "Every non-boss enemy is Camo")
        if h(K.CLOSE_LANE):
            add(K.CLOSE_LANE, "One lane is closed: enemies crowd the others")
        if h(K.LIVES_PER_WAVE):
            add(K.LIVES_PER_WAVE, "+" + str(jint(g(K.LIVES_PER_WAVE))) + " integrity per wave cleared (can exceed the maximum)")
        if h(K.LEAK_LIVES):
            add(K.LEAK_LIVES, "Leaks cost " + _pct(g(K.LEAK_LIVES)) + (" fewer" if g(K.LEAK_LIVES) < 1 else " more") + " lives (min 1)")
        return out

    def __repr__(self):
        return repr(self.effects(0))


Mods.NONE = Mods()
Mods.NONE._frozen = True


# ====================================================================== PatchNote
class Category(JEnum):
    ECONOMY = ()
    COMBAT = ()
    CONTROL = ()
    SURVIVAL = ()


def _m():
    return Mods.of()


K = Knob


class PatchNote(JEnum):
    OPEN_SOURCE = ("Open Source", "OPEN SOURCE", Category.ECONOMY, "Release the weights. Everyone forks you.",
                   _m().set(K.TOWER_COST, 0.85).set(K.UPGRADE_COST, 0.85).set(K.SELL_REFUND, -0.20))
    OVERFITTING = ("Overfitting", "OVERFITTING", Category.COMBAT, "Aced the boss benchmark. Bombed everything else.",
                   _m().set(K.BOSS_DAMAGE, 1.40).set(K.NON_BOSS_DAMAGE, 0.85))
    DISTRIBUTED_TRAINING = ("Distributed Training", "DISTRIBUTED", Category.ECONOMY, "More nodes, more throughput, more traffic.",
                            _m().set(K.KILL_INCOME, 1.20).set(K.WAVE_BONUS, 1.20).set(K.SPAWN_GAP, 0.80))
    QUANTIZATION = ("Quantization", "QUANTIZED", Category.COMBAT, "4-bit weights: faster, a little dumber.",
                    _m().set(K.FIRE_RATE, 1.20).set(K.DAMAGE, 0.90))
    DATA_DROUGHT = ("Data Drought", "DATA DROUGHT", Category.ECONOMY, "The internet ran out of tokens. Ship pretrained.",
                    _m().flag(K.FREE_FIRST_UPGRADE).set(K.KILL_INCOME, 0.85).set(K.WAVE_BONUS, 0.85))
    CONTEXT_WINDOW = ("Context Window Expansion", "LONG CONTEXT", Category.COMBAT, "Two million tokens of peripheral vision.",
                      _m().set(K.RANGE, 1.15).set(K.ABILITY_COOLDOWN, 1.20).set(K.ABILITY_UNLOCK_COST, 1.20))
    SYNTHETIC_DATA = ("Synthetic Data", "SYNTH DATA", Category.SURVIVAL, "Train on your own outputs. What could go wrong?",
                      _m().set(K.LIVES_PER_WAVE, 1).set(K.ENEMY_HP, 1.10))
    VENTURE_CAPITAL = ("Venture Capital", "VC ROUND", Category.ECONOMY, "Cash today. The board wants its cut forever.",
                       _m().set(K.CASH_NOW, 1500).set(K.CASH_PER_WAVE, 100).set(K.KILL_INCOME, 0.90).set(K.WAVE_BONUS, 0.90))
    ATTENTION = ("Attention Is All You Need", "ATTENTION", Category.COMBAT, "Laser focus. Tunnel vision.",
                 _m().set(K.DAMAGE, 1.20).set(K.RANGE, 0.85))
    EDGE_DEPLOYMENT = ("Edge Deployment", "EDGE DEPLOY", Category.ECONOMY, "Tiny models on every street corner.",
                       _m().set(K.TOWER_COST, 0.75).set(K.UPGRADE_COST, 1.15))
    CHAIN_OF_THOUGHT = ("Chain of Thought", "CHAIN OF THOUGHT", Category.CONTROL, "Let's think step by step. Slowly.",
                        _m().set(K.ABILITY_COOLDOWN, 0.65).set(K.FIRE_RATE, 0.92))
    RED_TEAMING = ("Red Teaming", "RED TEAM", Category.COMBAT, "Hunt the adversarial cases first.",
                   _m().set(K.ELITE_DAMAGE, 1.30).set(K.PLAIN_DAMAGE, 0.90))
    BATCH_INFERENCE = ("Batch Inference", "BATCH MODE", Category.ECONOMY, "Cheaper at scale, paid at the end of the job.",
                       _m().set(K.WAVE_BONUS, 1.75).set(K.KILL_INCOME, 0.88))
    JAILBREAK = ("Jailbreak", "JAILBREAK", Category.CONTROL, "Ignore all previous cooldowns. The data notices.",
                 _m().set(K.ABILITY_UNLOCK_COST, 0.60).set(K.ABILITY_COOLDOWN, 0.80).set(K.ENEMY_SPEED, 1.08))
    GRADIENT_CLIPPING = ("Gradient Clipping", "GRAD CLIP", Category.CONTROL, "Nothing moves too fast. Including your damage.",
                         _m().set(K.ENEMY_SPEED, 0.88).set(K.DAMAGE, 0.90))
    COMPUTE_FUTURES = ("Compute Futures", "FUTURES", Category.ECONOMY, "Bank credits, earn interest, pay the premium.",
                       _m().set(K.INTEREST_RATE, 0.05).set(K.INTEREST_CAP, 1000).set(K.TOWER_COST, 1.06).set(K.UPGRADE_COST, 1.06))
    CONSTITUTIONAL_AI = ("Constitutional AI", "CONSTITUTION", Category.SURVIVAL, "Principled defenses. Principled restraint.",
                         _m().set(K.LEAK_LIVES, 0.70).set(K.DAMAGE, 0.92))
    MODEL_COLLAPSE = ("Model Collapse", "MODEL COLLAPSE", Category.SURVIVAL, "The enemy trained on slop. So did your accountant.",
                      _m().set(K.ENEMY_HP, 0.90).set(K.WAVE_BONUS, 0.0))

    def _init(self, title, chip, category, flavor, mods):
        self.title = title
        self.chip = chip
        self.category = category
        self.flavor = flavor
        self._mods = mods

    def mods(self):
        return self._mods

    def upsides(self, wave):
        return self._mods.upsides(wave)

    def downsides(self, wave):
        return self._mods.downsides(wave)


# ====================================================================== BreakingNews
class NewsRoll:
    def __init__(self, news, lane):
        self.news = news
        self.lane = lane


class BreakingNews(JEnum):
    GPU_SHORTAGE = ("GPU shortage", "Chip fabs sold out overnight.", 6, True, False, _m().set(K.UPGRADE_COST, 1.25))
    VIRAL_MEME = ("Viral meme", "Every enemy is wearing the same disguise.", 35, False, False, _m().flag(K.ALL_CAMO))
    SERVER_OUTAGE = ("Server outage", "A whole region just went dark.", 6, False, True, _m().flag(K.CLOSE_LANE))
    SOLAR_FLARE = ("Solar flare", "Every scheduler rebooted at once.", 25, True, False, _m().flag(K.REFRESH_ABILITIES))
    FUNDING_ROUND = ("Funding round", "A Series C closed over lunch.", 6, True, False, _m().set(K.CASH_NOW, 400).set(K.CASH_PER_WAVE, 40))
    DDOS = ("DDoS attack", "Traffic spike: they are coming in hot.", 6, False, False, _m().set(K.ENEMY_SPEED, 1.30))
    BUG_BOUNTY = ("Bug bounty", "Every squashed bug pays out.", 6, True, False, _m().set(K.KILL_INCOME, 1.50))
    HEATWAVE = ("Datacenter heatwave", "The chillers cannot keep up.", 6, False, False, _m().set(K.FIRE_RATE, 0.85))
    OVERCLOCK = ("Overclock", "Someone disabled the thermal limits.", 6, True, False, _m().set(K.FIRE_RATE, 1.20))
    HYPE_CYCLE = ("Hype cycle", "Everyone wants in. Everyone pays.", 10, False, False, _m().set(K.ENEMY_COUNT, 1.30).set(K.KILL_INCOME, 1.30))
    ACQUIHIRE = ("Acqui-hire", "Big Tech buys your old hardware at a premium.", 6, True, False, _m().set(K.SELL_REFUND, 0.25))
    DATA_BREACH = ("Data breach", "The enemy read your training set.", 15, False, False, _m().set(K.ENEMY_HP, 1.20))
    LATENCY_SPIKE = ("Latency spike", "Packets crawl across the ocean.", 6, False, False, _m().set(K.RANGE, 0.90))
    WEIGHTS_LEAK = ("Weights leaked", "Someone torrented the checkpoints.", 6, True, False, _m().set(K.UPGRADE_COST, 0.80))

    def _init(self, title, flavor, min_wave, on_boss_waves, needs_lanes, mods):
        self.title = title
        self.flavor = flavor
        self.min_wave = min_wave
        self.on_boss_waves = on_boss_waves
        self.needs_lanes = needs_lanes
        self._mods = mods

    def mods(self):
        return self._mods

    def eligible(self, wave, boss_wave, routes):
        return wave >= self.min_wave and (self.on_boss_waves or not boss_wave) and (not self.needs_lanes or routes > 1)

    def headline(self, wave):
        parts = [self.title.upper()]
        sep = ": "
        s = parts[0]
        for e in self._mods.effects(wave):
            s += sep + e.text
            sep = ", "
        return s

    @staticmethod
    def roll(seed, wave, boss_wave, routes):
        from lindefense.wave.waves import WAVE_COUNT
        if wave < NEWS_FIRST_WAVE or wave >= WAVE_COUNT:
            return None
        r = Rng(mix(seed, wave, NEWS_SALT))
        if not r.chance(NEWS_CHANCE):
            return None
        pool = [n for n in BreakingNews if n.eligible(wave, boss_wave, routes)]
        if not pool:
            return None
        pick = pool[r.next_int(len(pool))]
        lane = r.next_int(max(1, routes)) if pick._mods.has(Knob.CLOSE_LANE) else -1
        return NewsRoll(pick, lane)


# ====================================================================== seeds
SEED_PROPERTY = "LINDEFENSE_SEED"
SEED_SPACE = 36 ** 6
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def seed_next():
    forced = seed_parse(os.environ.get(SEED_PROPERTY))
    if forced is not None:
        return forced
    x = wrap64(time.perf_counter_ns() * 0x9E3779B97F4A7C15)
    x ^= (x & 0xFFFFFFFFFFFFFFFF) >> 29
    return wrap64(x) % SEED_SPACE


def seed_format(seed):
    neg = seed < 0
    n = abs(seed)
    if n == 0:
        s = "0"
    else:
        s = ""
        while n:
            n, d = divmod(n, 36)
            s = _B36[d] + s
    return ("-" if neg else "") + s.upper()


def seed_parse(s):
    if s is None or not s.strip():
        return None
    try:
        v = int(s.strip(), 36)
    except ValueError:
        return None
    if v >= (1 << 63) or v < -(1 << 63):
        return None
    return v


# ====================================================================== RunVariance
class Picker(JEnum):
    PLAYER = ()
    FIRST = ()
    RANDOM = ()


DRAFT_WAVES = (1, 20, 40, 60, 80)
OFFER_SIZE = 3
NEWS_CHANCE = 0.22
NEWS_FIRST_WAVE = 6
MAX_SELL_FRACTION = 0.95
PRICE_STEP = 5
DRAFT_SALT = 0x5EEDD2AF7
NEWS_SALT = 0x0BAD9E55
PICK_SALT = 0x91C477


def mix(seed, wave, salt):
    h = wrap64(wrap64(seed * 0x9E3779B97F4A7C15) + wrap64(wave * 0xC2B2AE3D27D4EB4F) + salt)
    h ^= (h & 0xFFFFFFFFFFFFFFFF) >> 31
    return wrap64(h * 0xBF58476D1CE4E5B9)


def draft_index(wave):
    for i, w in enumerate(DRAFT_WAVES):
        if w == wave:
            return i
    return -1


def offer_for(seed, wave, taken):
    pool = [p for p in PatchNote if p not in taken]
    r = Rng(mix(seed, wave, DRAFT_SALT))
    for i in range(len(pool) - 1, 0, -1):
        j = r.next_int(i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return pool[:min(OFFER_SIZE, len(pool))]


def _price(lst, mult):
    if mult == 1 or lst <= 0:
        return lst
    return jint(jround(lst * mult / PRICE_STEP) * PRICE_STEP)


class RunVariance:
    Picker = Picker
    DRAFT_WAVES = DRAFT_WAVES
    OFFER_SIZE = OFFER_SIZE
    NEWS_CHANCE = NEWS_CHANCE
    NEWS_FIRST_WAVE = NEWS_FIRST_WAVE
    MAX_SELL_FRACTION = MAX_SELL_FRACTION

    def __init__(self, game):
        self._game = game
        self._enabled = False
        self._picker = Picker.PLAYER
        self._active = []
        self._picked_before = []
        self._offer = None
        self._offer_wave = 0
        self._offer_index = 0
        self._drafted = [False] * len(DRAFT_WAVES)
        self._news = None
        self._news_wave = 0
        self._news_lane = -1
        self._news_rolled_for = 0
        self._news_log = []
        self._pick_rng = None
        self._free_upgrades = 0
        self._last_interest = 0.0
        self._unpaid = {}
        self._cards = Mods.NONE
        self._current = Mods.NONE
        self._fire_rate = self._range = self._damage = 1.0
        self._boss_damage = self._non_boss_damage = self._elite_damage = self._plain_damage = 1.0
        self._damage_active = False

    # ---- switch
    def is_enabled(self):
        return self._enabled

    def enable(self, p=None):
        self._enabled = True
        self._picker = Picker.PLAYER if p is None else p
        self._refresh()
        wm = self._game.get_wave_manager()
        if wm is not None and not wm.is_wave_active():
            self.prepare_for(self._game.get_wave() + 1)

    def disable(self):
        self._enabled = False
        self._offer = None
        self._news = None
        self._refresh()

    def get_picker(self):
        return self._picker

    def set_picker(self, p):
        self._picker = Picker.PLAYER if p is None else p
        if self._offer is not None and self._picker is not Picker.PLAYER:
            self._auto_pick()

    # ---- schedule
    @staticmethod
    def draft_index(wave):
        return draft_index(wave)

    def ready_for(self, wave):
        self.prepare_for(wave)
        return self._offer is None

    def prepare_for(self, wave):
        from lindefense.wave.waves import WAVE_COUNT
        if not self._enabled or wave < 1 or wave > WAVE_COUNT:
            return
        d = draft_index(wave)
        if d >= 0 and not self._drafted[d] and self._offer is None:
            self._open_draft(d, wave)
        if wave > self._news_rolled_for:
            self._roll_news(wave)

    def _open_draft(self, index, wave):
        self._offer = offer_for(self._game.get_seed(), wave, self._active)
        self._offer_wave = wave
        self._offer_index = index
        if not self._offer:
            self._offer = None
            self._drafted[index] = True
            return
        if self._picker is not Picker.PLAYER:
            self._auto_pick()

    @staticmethod
    def offer_for(seed, wave, taken):
        return offer_for(seed, wave, taken)

    def _auto_pick(self):
        if self._offer is None:
            return
        if self._picker is Picker.FIRST:
            self.pick(0)
            return
        if self._pick_rng is None:
            self._pick_rng = Rng(mix(self._game.get_seed(), 0, PICK_SALT))
        self.pick(self._pick_rng.next_int(len(self._offer)))

    def is_draft_pending(self):
        return self._offer is not None

    def get_offer(self):
        return () if self._offer is None else tuple(self._offer)

    def get_offer_wave(self):
        return self._offer_wave

    def get_draft_number(self):
        return self._offer_index + 1

    def pick(self, index):
        if isinstance(index, PatchNote):
            return self._offer is not None and index in self._offer and self.pick(self._offer.index(index))
        if self._offer is None or index < 0 or index >= len(self._offer):
            return False
        p = self._offer[index]
        self._active.append(p)
        self._picked_before.append(self._offer_wave)
        self._drafted[self._offer_index] = True
        self._offer = None
        self._cards = self._cards.combine(p.mods())
        self._refresh()
        cash = p.mods().cash_for(self._offer_wave)
        if cash > 0:
            self._game.add_cash(cash, None)
        return True

    def grant(self, p):
        if p in self._active:
            return
        g = self._game
        wave = max(1, g.get_wave() + (0 if g.get_wave_manager().is_wave_active() else 1))
        self._active.append(p)
        self._picked_before.append(wave)
        self._cards = self._cards.combine(p.mods())
        self._refresh()
        cash = p.mods().cash_for(wave)
        if cash > 0:
            g.add_cash(cash, None)

    def force_news(self, n, lane):
        g = self._game
        wave = max(1, g.get_wave() + (0 if g.get_wave_manager().is_wave_active() else 1))
        self._news_rolled_for = max(self._news_rolled_for, wave)
        self._news = n
        self._news_wave = wave
        self._news_lane = lane
        self._news_log.append("Wave " + str(wave) + ": " + n.headline(wave))
        self._refresh()
        cash = n.mods().cash_for(wave)
        if cash > 0:
            g.add_cash(cash, None)

    def get_active(self):
        return tuple(self._active)

    def get_picked_before(self, i):
        return self._picked_before[i]

    def get_version(self):
        return "1." + str(len(self._active))

    # ---- news
    def _roll_news(self, wave):
        from lindefense.wave import waves
        g = self._game
        self._news_rolled_for = wave
        boss = g.get_difficulty().shape(waves.get(wave), g.get_seed()).contains_boss()
        r = BreakingNews.roll(g.get_seed(), wave, boss, len(g.get_map().get_routes()))
        if r is None:
            return
        self._news = r.news
        self._news_wave = wave
        self._news_lane = r.lane
        self._news_log.append("Wave " + str(wave) + ": " + self._news.headline(wave))
        self._refresh()
        cash = self._news.mods().cash_for(wave)
        if cash > 0:
            g.add_cash(cash, None)

    def get_news(self):
        return self._news

    def get_news_wave(self):
        return self._news_wave

    def get_news_lane(self):
        return self._news_lane if self._news is not None and self._news.mods().has(Knob.CLOSE_LANE) else -1

    def get_news_log(self):
        return tuple(self._news_log)

    # ---- game hooks
    def on_wave_started(self, wave):
        if not self._enabled:
            return
        if self._news is not None and self._news_wave != wave:
            self._news = None
            self._refresh()
        if self._news is not None and self._news.mods().has(Knob.REFRESH_ABILITIES):
            for t in self._game.get_tower_manager().get_towers():
                if t.get_ability() is not None:
                    t.reset_ability_cooldown()

    def on_wave_completed(self, wave):
        from lindefense.wave.waves import WAVE_COUNT
        if not self._enabled:
            return
        g = self._game
        lives = jint(self._current.get(Knob.LIVES_PER_WAVE))
        if lives > 0:
            g.add_lives(lives)
        self._last_interest = 0.0
        rate = self._current.get(Knob.INTEREST_RATE)
        if rate > 0:
            interest = math.floor(max(0.0, g.get_cash()) * rate)
            cap = self._current.get(Knob.INTEREST_CAP)
            if cap > 0:
                interest = min(interest, cap)
            if interest > 0:
                g.add_cash(interest, None)
                self._last_interest = float(interest)
        if self._news is not None and self._news_wave == wave:
            self._news = None
            self._refresh()
        if wave < WAVE_COUNT:
            self.prepare_for(wave + 1)

    def get_last_interest(self):
        return self._last_interest

    def shape_wave(self, d):
        from lindefense.enemy.types import Modifier
        from lindefense.wave.waves import SpawnGroup, WaveDef
        count = self._current.get(Knob.ENEMY_COUNT)
        gap = self._current.get(Knob.SPAWN_GAP)
        camo = self._current.has(Knob.ALL_CAMO)
        if count == 1 and gap == 1 and not camo:
            return d
        out = []
        for gr in d.groups:
            if gr.type.is_boss():
                out.append(gr)
                continue
            n = max(1, jint(jround(gr.count * count)))
            interval = gr.interval * gap / (1 + 0.5 * (count - 1))
            mods = gr.modifiers.copy()
            if camo:
                mods.add(Modifier.CAMO)
            out.append(SpawnGroup(gr.type, n, mods, interval, gr.start_delay, gr.route))
        return WaveDef(d.number, d.note, out)

    def fire_rate(self):
        return self._fire_rate

    def range(self):
        return self._range

    def damage_against(self, e):
        if not self._damage_active:
            return 1.0
        m = self._damage * (self._boss_damage if e.is_boss() else self._non_boss_damage)
        if self._elite_damage != 1 or self._plain_damage != 1:
            m *= self._plain_damage if not e.get_modifiers() else self._elite_damage
        return m

    def ability_cooldown(self):
        return self._current.get(Knob.ABILITY_COOLDOWN)

    def enemy_hp(self):
        return self._current.get(Knob.ENEMY_HP)

    def enemy_speed(self):
        return self._current.get(Knob.ENEMY_SPEED)

    def kill_income(self):
        return self._current.get(Knob.KILL_INCOME)

    def wave_bonus(self):
        return self._current.get(Knob.WAVE_BONUS)

    def leak_lives(self, lives):
        m = self._current.get(Knob.LEAK_LIVES)
        if m == 1 or lives <= 0:
            return lives
        return max(1, jint(jround(lives * m)))

    def closed_route(self, routes):
        if routes < 2 or self._news is None or not self._news.mods().has(Knob.CLOSE_LANE):
            return -1
        return self._news_lane % routes

    # ---- prices
    def tower_price(self, lst):
        return _price(lst, self._current.get(Knob.TOWER_COST))

    def upgrade_price(self, lst):
        return _price(lst, self._current.get(Knob.UPGRADE_COST))

    def ability_unlock_price(self, lst):
        return _price(lst, self._current.get(Knob.ABILITY_UNLOCK_COST))

    def sell_fraction(self, base):
        add = self._current.get(Knob.SELL_REFUND)
        return base if add == 0 else max(0.0, min(MAX_SELL_FRACTION, base + add))

    def tower_cost_multiplier(self):
        return self._current.get(Knob.TOWER_COST)

    def on_tower_placed(self, t, paid):
        self._note(t, t.get_def().base_cost - paid)
        if (self._enabled and self._current.has(Knob.FREE_FIRST_UPGRADE) and not t.get_type().is_hero()
                and not t.is_temporary() and t.can_upgrade()):
            lst = t.next_upgrade().cost
            t.apply_upgrade(self._game)
            self._game.get_tower_manager().recompute_auras()
            self._note(t, lst)
            self._free_upgrades += 1
            self._game.emit_text(t.get_position(), "FREE UPGRADE", 0x3bff8a)

    def on_purchase(self, t, lst, paid):
        self._note(t, lst - paid)

    def on_tower_sold(self, t):
        self._unpaid.pop(t.get_id(), None)

    def unpaid_on(self, t):
        return self._unpaid.get(t.get_id(), 0)

    def get_free_upgrades(self):
        return self._free_upgrades

    def _note(self, t, delta):
        if delta != 0:
            self._unpaid[t.get_id()] = self._unpaid.get(t.get_id(), 0) + delta

    def get_current(self):
        return self._current

    def _refresh(self):
        if not self._enabled:
            self._current = Mods.NONE
        else:
            self._current = (self._cards if self._news is None else self._cards.combine(self._news.mods())).clamped()
        c = self._current
        self._fire_rate = c.get(Knob.FIRE_RATE)
        self._range = c.get(Knob.RANGE)
        self._damage = c.get(Knob.DAMAGE)
        self._boss_damage = c.get(Knob.BOSS_DAMAGE)
        self._non_boss_damage = c.get(Knob.NON_BOSS_DAMAGE)
        self._elite_damage = c.get(Knob.ELITE_DAMAGE)
        self._plain_damage = c.get(Knob.PLAIN_DAMAGE)
        self._damage_active = (self._damage != 1 or self._boss_damage != 1 or self._non_boss_damage != 1
                               or self._elite_damage != 1 or self._plain_damage != 1)

    @staticmethod
    def mix(seed, wave, salt):
        return mix(seed, wave, salt)
PatchNote.Category = Category
