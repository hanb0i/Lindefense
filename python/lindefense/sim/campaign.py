"""Campaign mode: 15 curated levels across the seven maps, each a short or long slice of the 100-wave progression,
with towers unlocked level by level, and the player's saved progress (completed levels, best stars, unlocked towers).

A level is static data. Its wave list is a deterministic selection of base waves (wave/waves.py): local wave i plays
base wave bases[i], with that base wave's enemies and the base wave's HP / speed / reward scaling and end-of-wave
bonus, so a level late in the path brings the late enemy types, mechanics and bosses. Its numbers are one BALANCE
entry: a small starting budget (at most CASH_CAP, the finale FINALE_CASH_CAP) and integrity (nothing carries over),
and an enemy health multiplier on top of the base waves' HP scaling that rises from the level's first wave to its last,
so a fresh build can hold the first waves and the pressure grows as the level's income grows the build (above 100% in
the early levels, whose waves are easy in CLASSIC), plus the campaign-only boss leak cap. Stars by integrity left
(STAR_PERCENT). No Patch Notes or Breaking News, Difficulty Growth O(1), no Freeplay. A level is won when its last wave
is cleared; the finale when Palantir dies.

Game.set_campaign() attaches a CampaignRun (level id, allowed towers, wave list: plain picklable data) to a fresh
Game; everything the simulation asks of the campaign goes through that object, and a Game without one (classic,
tutorial, reverse mode) is untouched. CampaignProgress is the saved progress (prefs node "lindefense/campaign"),
in memory for tests."""
from lindefense import prefs
from lindefense.enemy.types import EnemyType, Mechanic, Modifier
from lindefense.tower.tower_type import TowerType
from lindefense.wave import waves as _waves
from lindefense.wave.waves import WaveDef

T = TowerType
STARTER = (T.GEMINI, T.CLAUDE, T.GPT)
NODE = "lindefense/campaign"
CAMPAIGN_DIFFICULTY_ID = "O1"

INJECTION_NOTE = ("Prompt Injection: an enemy holding an IGNORE PREVIOUS INSTRUCTIONS sign hijacks nearby towers "
                  "(Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann are immune).")


class CampaignWave(WaveDef):
    """One wave of a level: local number (1..N), the base wave it plays (`base`, which also sets its HP / speed /
    reward scaling and its bonus), and that base wave's spawn groups (shared, never copied)."""

    def __init__(self, number, base, note, groups):
        WaveDef.__init__(self, number, note, list(groups))
        self.base = base


class Level:
    """One campaign level (static). index is 1-based; bases are the base waves its waves play, strictly increasing."""

    def __init__(self, id_, title, flavour, map_index, bases, reward=(), heroes=False, abilities=False):
        self.id = id_
        self.title = title
        self.flavour = flavour
        self.map_index = map_index
        self.bases = tuple(bases)
        self.reward = tuple(reward)          # shop towers unlocked by the first completion
        self.reward_heroes = heroes          # the first completion opens the Hero Store
        self.reward_abilities = abilities    # ... or the $15,000 ability unlocks
        self.index = 0                       # set by _register
        self._waves = None

    def __repr__(self):
        return "Level(%d %s)" % (self.index, self.id)

    def wave_count(self):
        return len(self.bases)

    # ---- the level's numbers (BALANCE)
    def balance(self):
        return BALANCE[self.id]

    @property
    def start_cash(self):
        return BALANCE[self.id].cash

    @property
    def start_lives(self):
        return BALANCE[self.id].lives

    def hp_text(self):
        """The enemy health multiplier as the briefing shows it: '100%', '20%' or '20-45%'."""
        a, b = self.hp_range()
        pa, pb = int(a * 100 + 0.5), int(b * 100 + 0.5)   # half up: 4.5% shows as 5%
        return "%d%%" % pa if pa == pb else "%d-%d%%" % (pa, pb)

    def hp_range(self):
        """(first wave, last wave) enemy health multiplier of the level, on top of the base waves' own scaling."""
        b = BALANCE[self.id]
        return b.hp, b.hp_end

    def boss_leak(self):
        """The most integrity one leaking corporate boss costs in this level (Palantir excepted), or None (no cap)."""
        return BALANCE[self.id].boss_leak

    def star_lives(self):
        """(integrity left needed for 3 stars, for 2 stars) in this level."""
        return star_lives(self.start_lives)

    def is_finale(self):
        return self is LEVELS[-1]

    def waves(self):
        """The level's waves (CampaignWave, local numbers 1..N), built once and shared."""
        if self._waves is None:
            out = []
            explained = False
            for i, b in enumerate(self.bases):
                base = _waves.get(b)
                note = base.note
                injects = any(Modifier.INJECTION in gr.modifiers for gr in base.groups)
                if injects and not explained:
                    explained = True
                    if note is None or "IGNORE PREVIOUS INSTRUCTIONS" not in note:
                        note = INJECTION_NOTE if note is None else note + " " + INJECTION_NOTE
                out.append(CampaignWave(i + 1, b, note, base.groups))
            self._waves = tuple(out)
        return self._waves

    def boss_waves(self):
        return [w for w in self.waves() if w.contains_boss()]

    def threats(self):
        """What the level throws at you: {"camo", "lead", "fortified", "regrow", "injection": enemies with it,
        "bosses": [(local wave, boss type)]}."""
        out = {"camo": 0, "lead": 0, "fortified": 0, "regrow": 0, "injection": 0, "bosses": []}
        for w in self.waves():
            for gr in w.groups:
                t, m = gr.type, gr.modifiers
                if Modifier.CAMO in m or t.has_innate_camo():
                    out["camo"] += gr.count
                if t.is_lead_body() or t.mechanic is Mechanic.RADIX_PHASES:
                    out["lead"] += gr.count
                if Modifier.FORTIFIED in m:
                    out["fortified"] += gr.count
                if Modifier.REGROW in m:
                    out["regrow"] += gr.count
                if Modifier.INJECTION in m:
                    out["injection"] += gr.count
                if t.is_boss():
                    out["bosses"].append((w.number, t))
        return out

    def kind(self):
        """SKIRMISH (12 waves or fewer), BATTLE, or SIEGE (20 or more)."""
        n = self.wave_count()
        return "SKIRMISH" if n <= 12 else ("SIEGE" if n >= 20 else "BATTLE")

    def map_name(self):
        from lindefense.map import maps
        return maps.create(self.map_index).get_name()

    # ---- what the player has when playing this level (everything earned by the levels before it)
    def towers(self):
        """Shop towers available in this level, in TowerType order."""
        have = set(STARTER)
        for lv in LEVELS[:self.index - 1]:
            have.update(lv.reward)
        return tuple(t for t in TowerType.shop_towers() if t in have)

    def heroes_allowed(self):
        return any(lv.reward_heroes for lv in LEVELS[:self.index - 1])

    def abilities_allowed(self):
        return any(lv.reward_abilities for lv in LEVELS[:self.index - 1])

    def reward_text(self):
        """'Perplexity', 'Copilot + Hero Store', 'GLM + $15,000 abilities', or '' for the finale."""
        parts = []
        if self.reward:
            parts.append(", ".join(t.display_name for t in self.reward))
        if self.reward_heroes:
            parts.append("Hero Store")
        if self.reward_abilities:
            parts.append("$15,000 abilities")
        return " + ".join(parts)


def _span(a, b, n):
    """n base waves spread evenly over a..b (both included), strictly increasing."""
    if n == 1:
        return (b,)
    out = []
    for i in range(n):
        out.append(a + int(round(i * (b - a) / float(n - 1))))
    return tuple(out)


def _register(levels):
    for i, lv in enumerate(levels):
        lv.index = i + 1
    return tuple(levels)


# Wave counts: 10 18 12 24 8 21 14 30 10 16 25 12 28 9 22 (skirmishes and sieges alternate, no two neighbours equal).
# Rewards: one shop tower per level (two after level 7), the Hero Store after level 6, the $15,000 ability unlocks
# after level 10 and Zethos last, so the finale has all 18 towers. See DESIGN.md / tests/test_campaign.py.
LEVELS = _register([
    Level("hello_world", "Hello, World",
          "A trickle of Primitive Variables probes the Circuit. Three models stand between them and the core.",
          0, _span(1, 12, 10), reward=(T.PERPLEXITY,)),
    Level("garbage_collection", "Garbage Collection",
          "The old data center is full of arrays that refuse to die. Clear them out before they regrow.",
          6, _span(4, 21, 18), reward=(T.MISTRAL,)),
    Level("legacy_code", "Legacy Code",
          "The sorting algorithms arrive, some already invisible. Perplexity sees what the others cannot.",
          1, _span(18, 29, 12), reward=(T.DEEPSEEK,)),
    Level("campus_tour", "Campus Tour",
          "A long road through Silicon Valley, and Bellarmine College Prep is enrolling at the far end.",
          4, _span(17, 40, 24), reward=(T.SUNO,)),
    Level("hallucinations", "Hallucinations",
          "Camo splitters and the first MOAB packs, on a map that teleports half of them. Short and sharp.",
          2, (41, 43, 45, 46, 47, 49, 50, 52), reward=(T.QWEN,)),
    Level("backpropagation", "Backpropagation",
          "Fortified MOABs push through every hidden layer. Strip their armour before it reaches the output.",
          5, _span(36, 56, 21), reward=(T.COPILOT,), heroes=True),
    Level("outsourced", "Outsourced",
          "The SW Resource Consultant has signed a contract on the Circuit. It brings contractors.",
          0, _span(47, 60, 14), reward=(T.COHERE, T.DALLE)),
    Level("technical_debt", "Technical Debt",
          "Thirty waves of interest payments: MOABs, BFBs and armour walls, all due at once.",
          6, _span(41, 70, 30), reward=(T.GROK,)),
    Level("event_horizon", "Event Horizon",
          "Four portals, one vortex. The core collapses on the fiftieth wave of the war. Hold on.",
          3, _span(48, 66, 10), reward=(T.SORA,)),
    Level("network_effect", "Network Effect",
          "3Com wires the Monolith into one hub. Everything near it shrugs off half your damage.",
          1, _span(65, 80, 16), reward=(T.GLM,), abilities=True),
    Level("mass_hallucination", "Mass Hallucination",
          "The canyon fills with camo regrow speedsters and fortified BFBs. A long night.",
          2, tuple(b for b in range(58, 84) if b != 80), reward=(T.LLAMA,)),
    Level("stealth_mode", "Stealth Mode",
          "Lockheed Martin flies in camo and Lead armour. Detection is not optional any more.",
          4, _span(79, 90, 12), reward=(T.KIMI,)),
    Level("deep_learning", "Deep Learning",
          "Every corporate boss the network has met, layer after layer. The longest siege of the war.",
          5, _span(67, 94, 28), reward=(T.MINIMAX,)),
    Level("singularity", "Singularity",
          "Nine waves of DDTs and fortified BFBs falling into the vortex. The last rehearsal.",
          3, (90, 91, 92, 93, 94, 95, 96, 97, 99), reward=(T.ZETHOS,)),
    Level("last_line_of_code", "The Last Line of Code",
          "Palantir sees everything and is coming for the Circuit. Every model you have earned, one final time.",
          0, _span(79, 100, 22)),
])

_BY_ID = {lv.id: lv for lv in LEVELS}


class Balance:
    """One level's numbers. cash / lives: what the level starts with (nothing carries over). hp -> hp_end: the
    campaign's enemy health multiplier on top of the base waves' own HP scaling, on the level's first wave rising
    to its last along HP_RAMP (bosses and Palantir included; kill rewards are not scaled). A low hp lets a fresh, small
    build hold the late waves' enemy types, mechanics and bosses; the rise toward hp_end keeps the level a fight as
    the player's build grows with the level's income, and above 1 (the early levels) enemies are tougher than in
    CLASSIC. boss_leak: the most integrity one corporate boss that gets through costs in this level (its own cost
    otherwise, e.g. 3Com 100), so a single leak hurts without deciding the level; Palantir is never capped (it reaching
    the core ends the finale). None: no cap (levels without bosses)."""
    __slots__ = ("cash", "lives", "hp", "hp_end", "boss_leak")

    def __init__(self, cash, lives, hp=1.0, hp_end=None, boss_leak=None):
        self.cash = cash
        self.lives = lives
        self.hp = float(hp)
        self.hp_end = float(hp if hp_end is None else hp_end)
        self.boss_leak = boss_leak

    def __repr__(self):
        return "Balance(cash=%d, lives=%d, hp=%g, hp_end=%g, boss_leak=%s)" % (self.cash, self.lives, self.hp,
                                                                            self.hp_end, self.boss_leak)


CASH_CAP = 25_000          # starting cash of a regular level (manageable build before wave 1)
FINALE_CASH_CAP = 60_000

# The enemy health multiplier rises from hp to hp_end along t ** HP_RAMP (t: 0 on a level's first wave, 1 on its
# last): a fresh build meets the first waves near hp, and most of the rise comes in the level's second half, so the
# pressure grows as the level's income grows the build instead of deciding the level in its first waves.
HP_RAMP = 2

# Calibrated with the balance bot (tools/auto_player.py campaign, seeds 1234 / 2000 / 2766, checked on six seeds; see
# README / DESIGN.md section 11). The bot plays near-optimally with only the level's towers (abilities from level 11),
# so a player who uses heroes and abilities well does better. Targets for the bot: levels 1-2 won with 60-90% of the
# integrity left, levels 3-9 with 30-70%, levels 10-14 tight (won about two times in three, often under 40%), the
# finale won at most two times in three with Palantir deep along its route. Every level has 100 integrity; boss_leak
# 25 caps what one leaking boss costs (levels 1-3 have no bosses).
BALANCE = {
    "hello_world":        Balance(cash=650, lives=100, hp=1.2, hp_end=4.0),
    "garbage_collection": Balance(cash=750, lives=100, hp=1.3, hp_end=7.0),
    "legacy_code":        Balance(cash=4_000, lives=100, hp=1.4, hp_end=6.0),
    "campus_tour":        Balance(cash=5_000, lives=100, hp=1.45, hp_end=6.0, boss_leak=25),
    "hallucinations":     Balance(cash=8_000, lives=100, hp=0.18, hp_end=0.47, boss_leak=25),
    "backpropagation":    Balance(cash=10_000, lives=100, hp=0.33, hp_end=0.83, boss_leak=25),
    "outsourced":         Balance(cash=12_000, lives=100, hp=0.26, hp_end=0.34, boss_leak=25),
    "technical_debt":     Balance(cash=8_000, lives=100, hp=1.0, hp_end=2.55, boss_leak=25),
    "event_horizon":      Balance(cash=14_000, lives=100, hp=0.15, hp_end=0.46, boss_leak=25),
    "network_effect":     Balance(cash=16_000, lives=100, hp=0.22, hp_end=1.62, boss_leak=25),
    "mass_hallucination": Balance(cash=18_000, lives=100, hp=0.1, hp_end=1.3, boss_leak=25),
    "stealth_mode":       Balance(cash=20_000, lives=100, hp=0.14, hp_end=1.45, boss_leak=25),
    "deep_learning":      Balance(cash=22_000, lives=100, hp=0.1, hp_end=0.77, boss_leak=25),
    "singularity":        Balance(cash=25_000, lives=100, hp=0.042, hp_end=0.24, boss_leak=25),
    "last_line_of_code":  Balance(cash=60_000, lives=100, hp=0.1, hp_end=0.37, boss_leak=25),
}


def level(id_or_index):
    """A level by id ("outsourced") or 1-based index; None if there is none."""
    if isinstance(id_or_index, Level):
        return id_or_index
    if isinstance(id_or_index, int) and not isinstance(id_or_index, bool):
        return LEVELS[id_or_index - 1] if 1 <= id_or_index <= len(LEVELS) else None
    return _BY_ID.get(id_or_index)


def finale():
    return LEVELS[-1]


def unlock_level(t):
    """The level whose first completion unlocks shop tower t (None for the starter towers)."""
    for lv in LEVELS:
        if t in lv.reward:
            return lv
    return None


def heroes_level():
    return next(lv for lv in LEVELS if lv.reward_heroes)


def abilities_level():
    return next(lv for lv in LEVELS if lv.reward_abilities)


# Threat -> the shop towers that answer it (campaign tests check every level has one of them unlocked).
def _camo_detectors():
    from lindefense.tower import catalog
    out = []
    for t in TowerType.shop_towers():
        d = catalog.get(t)
        for k in range(len(d.upgrades) + 1):
            st = d.stats_for_tier(k)
            if st.sees_camo or st.aura_detection or st.has("revealAllCamo"):
                out.append(t)
                break
    return tuple(out)


def _lead_breakers():
    from lindefense.combat.hit_spec import DamageType
    from lindefense.tower import catalog
    out = []
    for t in TowerType.shop_towers():
        d = catalog.get(t)
        if d.base_stats.is_support_only():
            continue
        for k in range(len(d.upgrades) + 1):
            h = d.stats_for_tier(k).hit
            if h.type is not DamageType.SHARP or h.ignores_resistance:
                out.append(t)
                break
    return tuple(out)


def _injection_proof():
    from lindefense.tower import catalog
    return tuple(t for t in TowerType.shop_towers()
                 if catalog.is_injection_immune(t) or catalog.grants_injection_firewall(t))


def counters():
    """{threat: shop towers that answer it}: camo detection (any tier), non-Sharp damage for Lead-type enemies,
    injection immunity (or Copilot's firewall), boss killers (DeepSeek's railgun, Cohere's armour break) and, for
    Palantir's Predictive Surveillance, Perplexity (its second upgrade protects nearby towers)."""
    return {"camo": _camo_detectors(), "lead": _lead_breakers(), "injection": _injection_proof(),
            "boss": (T.DEEPSEEK, T.COHERE), "palantir": (T.PERPLEXITY,)}


# Stars for a won level by integrity left, in percent of the level's integrity: 3 stars with at least STAR_PERCENT[0]
# (near-flawless: lose at most 5%), 2 with at least STAR_PERCENT[1], else 1. The briefing shows them in integrity.
STAR_PERCENT = (95, 60)


def star_lives(max_lives):
    """(integrity needed for 3 stars, for 2 stars) in a level of max_lives integrity."""
    return tuple(-(-p * max_lives // 100) for p in STAR_PERCENT)   # ceil(p% of max_lives), in integers


def stars_for(lives, max_lives):
    """Stars for a won level by integrity left (STAR_PERCENT): 3 near-flawless, 2 with most of it, else 1."""
    if max_lives <= 0:
        return 1
    three, two = star_lives(max_lives)
    return 3 if lives >= three else (2 if lives >= two else 1)


# ====================================================================== the run a Game carries
class CampaignRun:
    """What a campaign Game knows about its level: the level id, the shop towers it may build, whether the Hero Store
    and the ability unlocks are open, and the wave list. Plain data (picklable: the waves are shared static data that
    savegame writes as references)."""

    def __init__(self, lv):
        self.level_id = lv.id
        self.index = lv.index
        self.allowed = frozenset(lv.towers())
        self.heroes = lv.heroes_allowed()
        self.abilities = lv.abilities_allowed()
        self.waves = lv.waves()
        self.finale = lv.is_finale()
        self.hp, self.hp_end = lv.hp_range()
        self.boss_leak = lv.boss_leak()

    def leak_cost(self, type_, lives):
        """The integrity a leaking enemy of type_ costs in this level: its own cost (lives, children included), but
        a corporate boss at most boss_leak (Palantir never capped)."""
        cap = self.boss_leak
        if cap is not None and lives > cap and type_.is_boss() and type_ is not EnemyType.PALANTIR:
            return cap
        return lives

    def level(self):
        return _BY_ID[self.level_id]

    def wave_count(self):
        return len(self.waves)

    def wave(self, n):
        """The level's wave n (1-based); n past the end gives the last wave (never asked in play)."""
        return self.waves[max(1, min(n, len(self.waves))) - 1]

    def base_wave(self, n):
        """The base wave whose scaling local wave n uses (0 before the first wave)."""
        return 0 if n <= 0 else self.wave(n).base

    def hp_at(self, n):
        """The campaign's enemy health multiplier on local wave n: hp on the first wave, rising to hp_end on the last
        along HP_RAMP (t ** HP_RAMP of the way at fraction t of the level: slow at first, fastest at the end; n <= 1
        gives hp)."""
        last = len(self.waves)
        if self.hp_end == self.hp or n <= 1 or last <= 1:
            return self.hp
        t = (min(n, last) - 1) / float(last - 1)
        return self.hp + (self.hp_end - self.hp) * t ** HP_RAMP

    def is_allowed(self, t):
        if t.is_hero():
            return self.heroes
        return t in self.allowed

    def lock_problem(self, t):
        """Why tower t cannot be built in this level, or None."""
        if self.is_allowed(t):
            return None
        if t.is_hero():
            return "The Hero Store opens after level %d" % heroes_level().index
        lv = unlock_level(t)
        return "%s unlocks after level %d" % (t.display_name, lv.index if lv is not None else self.index)

    def ability_problem(self):
        if self.abilities:
            return None
        return "Ability unlocks open after level %d" % abilities_level().index


def new_game(lv, seed=None, heroes=None, admin=None):
    """A fresh Game for level lv (Level, id or index): its map, O(1), the level's cash, lives and waves, no Patch
    Notes. heroes: the Hero Store collection (default in memory); admin: (heroes, money, health) flags."""
    from lindefense.map import maps
    from lindefense.sim.difficulty import Difficulty
    from lindefense.sim.game import Game
    from lindefense.variance.variance import seed_next
    lv = level(lv)
    g = Game(maps.create(lv.map_index), seed_next() if seed is None else seed, Difficulty.O1)
    if heroes is not None:
        g.set_hero_collection(heroes)
    if admin is not None:
        g.set_admin(*admin)
    g.set_campaign(CampaignRun(lv))
    return g


# ====================================================================== saved progress
class Outcome:
    """What finishing one level changed in the progress (for the end screen)."""

    def __init__(self, level_id, won, stars=0, best=0, first_clear=False, new_best=False, towers=(), heroes=False,
                 abilities=False, campaign_done=False):
        self.level_id = level_id
        self.won = won
        self.stars = stars
        self.best = best
        self.first_clear = first_clear
        self.new_best = new_best
        self.towers = tuple(towers)        # shop towers this result unlocked (first clear only)
        self.heroes = heroes               # the Hero Store opened with it
        self.abilities = abilities         # the ability unlocks opened with it
        self.campaign_done = campaign_done

    def level(self):
        return level(self.level_id)


class _MemoryStorage:
    def __init__(self, data=None):
        self.data = dict(data) if data else {}
        self.saves = 0

    def load(self):
        return dict(self.data)

    def save(self, d):
        self.data = dict(d)
        self.saves += 1


class _PrefsStorage:
    def load(self):
        n = prefs.node(NODE)
        return {"stars": n.get("stars", {}), "unlocked": n.get("unlocked", []), "boot_camp": n.get_bool("boot_camp")}

    def save(self, d):
        n = prefs.node(NODE)
        n.put("stars", d["stars"])
        n.put("unlocked", d["unlocked"])
        n.put("boot_camp", d["boot_camp"])


class CampaignProgress:
    """The player's campaign progress: best stars per completed level and the shop towers unlocked (the starters plus
    the rewards of every completed level, also stored so the save reads on its own). in_memory() never touches disk;
    persistent() is the shared, saved instance (prefs node "lindefense/campaign")."""
    _shared = None

    def __init__(self, storage=None):
        self._storage = storage
        self._stars = {}
        self._boot_camp = False
        d = {}
        if storage is not None:
            try:
                d = storage.load() or {}
            except Exception:
                d = {}
        raw = d.get("stars")
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in _BY_ID and isinstance(v, int) and not isinstance(v, bool) and v > 0:
                    self._stars[k] = min(3, v)
        self._boot_camp = d.get("boot_camp") is True

    @staticmethod
    def in_memory(stars=None, boot_camp=False):
        return CampaignProgress(_MemoryStorage({"stars": dict(stars or {}), "boot_camp": boot_camp}))

    @staticmethod
    def with_storage(storage):
        return CampaignProgress(storage)

    @staticmethod
    def persistent():
        if CampaignProgress._shared is None:
            CampaignProgress._shared = CampaignProgress(_PrefsStorage())
        return CampaignProgress._shared

    # ---- queries
    def is_completed(self, lv):
        return level(lv).id in self._stars

    def best_stars(self, lv):
        return self._stars.get(level(lv).id, 0)

    def stars(self):
        """{level id: best stars} for every completed level."""
        return dict(self._stars)

    def total_stars(self):
        return sum(self._stars.values())

    def completed_count(self):
        return len(self._stars)

    def is_available(self, lv):
        """Level 1 always; any later level once the level before it is completed."""
        lv = level(lv)
        return lv.index == 1 or self.is_completed(LEVELS[lv.index - 2])

    def state(self, lv):
        """"completed", "available" or "locked"."""
        return "completed" if self.is_completed(lv) else ("available" if self.is_available(lv) else "locked")

    def next_level(self):
        """The first level not completed yet (None once the campaign is finished)."""
        for lv in LEVELS:
            if not self.is_completed(lv):
                return lv
        return None

    def unlocked_towers(self):
        have = set(STARTER)
        for lv in LEVELS:
            if self.is_completed(lv):
                have.update(lv.reward)
        return tuple(t for t in TowerType.shop_towers() if t in have)

    def heroes_unlocked(self):
        return self.is_completed(heroes_level())

    def abilities_unlocked(self):
        return self.is_completed(abilities_level())

    def is_finished(self):
        return self.is_completed(finale())

    def boot_camp_done(self):
        """True once the tutorial (the optional BOOT CAMP node) was completed."""
        return self._boot_camp

    def mark_boot_camp(self):
        if not self._boot_camp:
            self._boot_camp = True
            self._save()

    # ---- updates
    def _save(self):
        if self._storage is not None:
            try:
                self._storage.save({"stars": dict(self._stars), "unlocked": [t.name for t in self.unlocked_towers()],
                                    "boot_camp": self._boot_camp})
            except Exception:
                pass

    def record(self, lv, won, lives=0, max_lives=1):
        """Folds one finished attempt at lv into the progress (one save when anything changed) and returns its
        Outcome. A defeat changes nothing."""
        lv = level(lv)
        if not won:
            return Outcome(lv.id, False, 0, self.best_stars(lv))
        stars = stars_for(lives, max_lives)
        first = not self.is_completed(lv)
        old = self.best_stars(lv)
        if stars > old:
            self._stars[lv.id] = stars
            self._save()
        return Outcome(lv.id, True, stars, max(stars, old), first, (not first) and stars > old,
                       lv.reward if first else (), first and lv.reward_heroes, first and lv.reward_abilities,
                       first and lv.is_finale())

    def record_game(self, game):
        """record() for a finished campaign Game (its level, result and lives); None for other games."""
        c = game.get_campaign()
        if c is None:
            return None
        from lindefense.sim.records import RunSummary, VICTORY
        won = RunSummary.result_of(game) == VICTORY
        return self.record(c.level_id, won, game.get_lives(), game.get_max_lives())

    def reset(self):
        self._stars.clear()
        self._boot_camp = False
        self._save()
