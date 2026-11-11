"""Reverse mode catalogs: the attacker's units, roles, exploits and doctrines, and the defender profiles (one per
Difficulty mode)."""
from lindefense.javacompat import jint, jround
from lindefense.jenum import JEnum
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.sim.difficulty import Difficulty
from lindefense.tower.tower_type import TowerType


class Role(JEnum):
    """What a unit is for. The defender AI adapts against the role you spend the most on (it builds the role's counter
    tower), and the unit cards show an EDGE while the AI has no answer to a role and COUNTERED after it adapted."""
    SWARM = ("Swarm", "swarm", TowerType.GEMINI, 2, 4, "chain lightning",
             (TowerType.GEMINI, TowerType.GPT, TowerType.SUNO, TowerType.DALLE))
    SPEED = ("Speed", "fast units", TowerType.CLAUDE, 2, 4, "slowing pierce",
             (TowerType.CLAUDE, TowerType.SORA, TowerType.GLM, TowerType.MISTRAL))
    ARMOUR = ("Armour", "armoured units", TowerType.COHERE, 2, 3, "armour breaker",
              (TowerType.COHERE, TowerType.QWEN, TowerType.DEEPSEEK))
    BOSS = ("Boss", "bosses", TowerType.DEEPSEEK, 2, 4, "railgun",
            (TowerType.DEEPSEEK, TowerType.NIK_SCOPE, TowerType.MR_LINDEMANN))
    CAMO = ("Camo", "camo", TowerType.PERPLEXITY, 1, 1, "camo detection", ())

    def _init(self, label, plural, counter, counter_tier, counter_cap, counter_what, answers):
        self.label = label
        self.plural = plural              # "the AI adapts against your <plural>"
        self.counter = counter            # the tower the AI builds when it adapts against this role
        self.counter_tier = counter_tier  # ... upgraded to this tier
        self.counter_cap = counter_cap    # ... never more copies than this
        self.counter_what = counter_what  # what the counter does, for the feed
        self.answers = answers            # the AI towers that answer this role (none built: the cards show an EDGE)


class AttackUnit(JEnum):
    PRIMITIVE = (EnemyType.PRIMITIVE_VARIABLE, 10, 0, Role.SWARM, "Cheap filler. Floods weak defences.")
    STATIC = (EnemyType.STATIC_ARRAY, 22, 0, Role.SWARM, "Splits into a Primitive Variable.")
    DYNAMIC = (EnemyType.DYNAMIC_ARRAY, 38, 0, Role.SPEED, "Fast; splits into a Static Array.")
    SINGLY = (EnemyType.SINGLY_LINKED_LIST, 34, 0, Role.SPEED, "Very fast, takes 2 integrity.")
    DOUBLY = (EnemyType.DOUBLY_LINKED_LIST, 42, 30, Role.SPEED, "Very fast, speeds up when hit.")
    BUBBLE = (EnemyType.BUBBLE_SORT, 30, 0, Role.SWARM, "Swaps places with the unit ahead.")
    SELECTION = (EnemyType.SELECTION_SORT, 38, 30, Role.SPEED, "Jumps to the front of its group.")
    INSERTION = (EnemyType.INSERTION_SORT, 38, 30, Role.SPEED, "Leapfrogs the unit ahead.")
    SHELL = (EnemyType.SHELL_SORT, 42, 30, Role.SPEED, "Gap-jumps forward; takes 3 integrity.")
    MERGE = (EnemyType.MERGE_SORT, 72, 60, Role.ARMOUR, "Ceramic; splits into two Merge Runs.")
    QUICK = (EnemyType.QUICK_SORT, 72, 60, Role.ARMOUR, "Ceramic and fast; splits in two.")
    COUNTING = (EnemyType.COUNTING_SORT, 60, 60, Role.SWARM, "Releases four Primitive Variables.")
    HEAP = (EnemyType.HEAP_SORT, 65, 90, Role.ARMOUR, "Lead-type; shields the units behind it.")
    RADIX = (EnemyType.RADIX_SORT, 75, 90, Role.ARMOUR, "Armoured digit phases; takes 6 integrity.")
    BUCKET = (EnemyType.BUCKET_SORT, 68, 90, Role.SWARM, "Carries weaker units past the towers.")
    TIMSORT = (EnemyType.TIMSORT, 140, 120, Role.SPEED, "Fast hybrid; splits into Merge + Insertion.")
    # the bosses keep their beta 3.0 health here (the last column: base HP in this mode, instead of the campaign's buffed
    # base HP) and carry their signature abilities, which the price includes
    MOAB = (EnemyType.BELLARMINE_COLLEGE_PREP, 1400, 150, Role.BOSS, "MOAB-class boss: {hp} HP, a Crest Shield at half health, 30 integrity.", 1300)
    BFB = (EnemyType.SW_RESOURCE_CONSULTANT, 5200, 210, Role.BOSS, "BFB-class boss: {hp} HP, outsources Quick Sorts, releases 3 MOABs, 60 integrity.", 7500)
    DDT = (EnemyType.LOCKHEED_MARTIN, 4000, 300, Role.BOSS, "DDT-class: {hp} HP, camo, lead, afterburner bursts, 50 integrity.", 850)
    ZOMG = (EnemyType.THREE_COM, 16000, 360, Role.BOSS, "ZOMG-class: {hp} HP, a network hub that shields nearby units, 100 integrity.", 8000)
    BAD = (EnemyType.PALANTIR, 30000, 420, Role.BOSS, "The BAD: {hp} HP, phases, jams towers, 100 integrity.", 50000)

    def _init(self, type_, price, unlock_at, role, blurb, base_hp=None):
        self.type = type_
        self.price = price
        self.unlock_at = float(unlock_at)
        self.role = role
        self._base_hp = base_hp
        self.blurb = blurb.format(hp="{:,}".format(self.base_hp()))   # {hp}: the unit's base HP, so the card never goes stale

    def base_hp(self):
        """The unit's health before the match scaling (its own reverse-mode base HP, else the campaign's)."""
        return self.type.base_hp if self._base_hp is None else self._base_hp

    def hp_factor(self):
        return self.base_hp() / float(self.type.base_hp)

    def is_boss(self):
        return self.type.is_boss()

    def accepts_modifiers(self):
        return self.type is not EnemyType.PALANTIR

    @staticmethod
    def of(t):
        for u in AttackUnit:
            if u.type is t:
                return u
        return None

    @staticmethod
    def modifier_unlock_at(m):
        if m is Modifier.REGROW:
            return 30.0
        if m is Modifier.CAMO:
            return 60.0
        if m is Modifier.INJECTION:
            return 180.0
        return 90.0

    @staticmethod
    def modifier_factor(m):
        if m is Modifier.REGROW:
            return 1.3
        if m is Modifier.CAMO:
            return 1.5
        if m is Modifier.INJECTION:
            return 1.6
        return 2.0

    def price_with(self, mods):
        """The list price with the modifiers' surcharges (before the doctrine's discounts: ReverseMatch.price)."""
        return jint(jround(self.raw_price(mods)))

    def raw_price(self, mods):
        p = float(self.price)
        if mods is not None and self.accepts_modifiers():
            for m in mods:
                p *= AttackUnit.modifier_factor(m)
        return p


class AttackAbility(JEnum):
    OVERCLOCK = ("Overclock", 100, 25, 6, 0, "All units on the track move 50% faster for 6 s.")
    HOTFIX = ("Hotfix", 350, 40, 0, 45, "Every unit on the track heals to full health.")
    ZERO_DAY = ("Zero-Day", 600, 50, 6, 90, "Jams the AI's 3 most expensive towers for 6 s.")

    def _init(self, display_name, cost, cooldown, duration, unlock_at, description):
        self.display_name = display_name
        self.cost = cost
        self.cooldown = float(cooldown)
        self.duration = float(duration)
        self.unlock_at = float(unlock_at)
        self.description = description


OVERCLOCK_SPEED = 1.5
ZERO_DAY_TARGETS = 3


class Doctrine(JEnum):
    """The attack doctrine picked in the briefing: one opening plan for the whole match, with a perk set and a cost."""
    RUSH = ("Rush", "Hit before the AI is built.", 0xff2bd6,
            ("Start with 1,000 compute", "Exploits recharge 40% faster, cost 25% less", "Bosses unlock 30 s earlier"),
            "Income -10%",
            1000, 0.9, 0.6, 0.75, -30.0, 1.0, 1.0, 1.0, 0.15, 150, 1.0, 1.0, 8, 1.0)
    SWARM = ("Swarm", "Drown the defence in numbers.", 0x00f0ff,
             ("Regular units cost 25% less", "Regular units +25% health", "Uplink twice as fast, queue 250"),
             "Bosses cost 10% more",
             600, 1.0, 1.0, 1.0, 0.0, 0.75, 1.25, 1.1, 0.075, 250, 1.0, 1.0, 8, 1.0)
    HEIST = ("Heist", "Every breach funds the next.", 0xffd166,
             ("Leaks pay 2x compute", "SCALE COMPUTE 35% cheaper, 10 levels", "Round objectives pay 50% more"),
             "Start with 400 compute",
             400, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.15, 150, 2.0, 0.65, 10, 1.5)

    def _init(self, display_name, tagline, rgb, perks, drawback, start_credits, income, exploit_cooldown, exploit_cost,
              boss_shift, unit_cost, unit_hp, boss_cost, spawn_gap, max_queue, leak_pay, compute_price, compute_max,
              objective_pay):
        self.display_name = display_name
        self.tagline = tagline
        self.rgb = rgb
        self.perks = perks
        self.drawback = drawback
        self.start_credits = start_credits
        self.income = float(income)                   # passive income multiplier
        self.exploit_cooldown = float(exploit_cooldown)
        self.exploit_cost = float(exploit_cost)
        self.boss_shift = float(boss_shift)           # seconds added to every boss's unlock time
        self.unit_cost = float(unit_cost)             # price multiplier of the regular units
        self.unit_hp = float(unit_hp)                 # health multiplier of the regular units
        self.boss_cost = float(boss_cost)             # ... of the bosses
        self.spawn_gap = float(spawn_gap)             # seconds between two units leaving the uplink
        self.max_queue = max_queue
        self.leak_pay = float(leak_pay)               # leak bounty multiplier
        self.compute_price = float(compute_price)     # SCALE COMPUTE price multiplier
        self.compute_max = compute_max
        self.objective_pay = float(objective_pay)     # round objective bonus multiplier

    @staticmethod
    def default():
        return Doctrine.RUSH


_selected_doctrine = [Doctrine.RUSH]


def selected_doctrine():
    """The doctrine the reverse briefing has selected (kept for the session, like the Difficulty Growth mode)."""
    return _selected_doctrine[0]


def select_doctrine(d):
    _selected_doctrine[0] = d


def _fmt(v):
    s = "%.2f" % v
    while s.endswith("0"):
        s = s[:-1]
    return s[:-1] if s.endswith(".") else s


class DefenderProfile(JEnum):
    NOVICE = (Difficulty.O1, "Novice", "Builds casually: random placement, no ability micro, slow to adapt, blind to camo until it leaks. 0.9x funding.",
              0.9, 0.5, True, False, False, 7.0, 0, 0, 0.90, 1.10, 1.10, 90, 75.0)
    COMPETENT = (Difficulty.ON, "Competent", "Efficient build and ability micro; adapts to your army every 50 s, but only sees camo once it leaks.",
                 1.0, 0.5, False, False, False, 5.0, 0, 0, 1.00, 1.00, 1.00, 100, 50.0)
    EXPERT = (Difficulty.ON2, "Expert", "Detection the moment you can buy camo, adapts every 35 s, saves for $15,000 ability unlocks. 1.75x funding.",
              1.75, 0.25, False, True, True, 5.5, 8, 0, 1.20, 0.90, 0.95, 150, 35.0)
    SUPERINTELLIGENCE = (Difficulty.ONN, "Superintelligence", "Expert play without the greed, adapts every 25 s, 2x funding. Breaking it takes a real plan.",
                         2.0, 0.25, False, True, True, 6.0, 12, 4, 1.35, 0.85, 0.90, 200, 25.0)

    def _init(self, level, display_name, description, income, think_interval, casual, anticipates_camo, unlocks_abilities,
              start_cash, unlock_min_towers, unlock_towers_per, tower_damage, unit_hp, attacker_income, integrity,
              adapt_interval):
        self.level = level
        self.display_name = display_name
        self.description = description
        self.income = float(income)
        self.think_interval = float(think_interval)
        self.casual = casual
        self.anticipates_camo = anticipates_camo
        self.unlocks_abilities = unlocks_abilities
        self.start_cash = float(start_cash)
        self.unlock_min_towers = unlock_min_towers
        self.unlock_towers_per = unlock_towers_per
        self.tower_damage = float(tower_damage)
        self.unit_hp = float(unit_hp)
        self.attacker_income = float(attacker_income)
        self.integrity = integrity
        self.adapt_interval = float(adapt_interval)   # seconds between two looks at your army (it adapts to the top role)

    def rules_line(self):
        return ("AI towers x" + _fmt(self.tower_damage) + " damage, AI integrity " + str(self.integrity) + ". Your units x"
                + _fmt(self.unit_hp) + " health, your compute income x" + _fmt(self.attacker_income) + ".")

    @staticmethod
    def of(d):
        for p in DefenderProfile:
            if p.level is d:
                return p
        return DefenderProfile.COMPETENT
