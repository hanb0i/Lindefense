"""Reverse mode catalogs: the attacker's units and exploits, and the defender profiles (one per Difficulty mode)."""
from lindefense.javacompat import jint, jround
from lindefense.jenum import JEnum
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.sim.difficulty import Difficulty


class AttackUnit(JEnum):
    PRIMITIVE = (EnemyType.PRIMITIVE_VARIABLE, 10, 0, "Cheap filler. Floods weak defences.")
    STATIC = (EnemyType.STATIC_ARRAY, 22, 0, "Splits into a Primitive Variable.")
    DYNAMIC = (EnemyType.DYNAMIC_ARRAY, 38, 0, "Fast; splits into a Static Array.")
    SINGLY = (EnemyType.SINGLY_LINKED_LIST, 34, 60, "Very fast, takes 2 integrity.")
    DOUBLY = (EnemyType.DOUBLY_LINKED_LIST, 42, 60, "Very fast, speeds up when hit.")
    BUBBLE = (EnemyType.BUBBLE_SORT, 30, 60, "Swaps places with the unit ahead.")
    SELECTION = (EnemyType.SELECTION_SORT, 38, 100, "Jumps to the front of its group.")
    INSERTION = (EnemyType.INSERTION_SORT, 38, 100, "Leapfrogs the unit ahead.")
    SHELL = (EnemyType.SHELL_SORT, 42, 100, "Gap-jumps forward; takes 3 integrity.")
    MERGE = (EnemyType.MERGE_SORT, 72, 150, "Ceramic; splits into two Merge Runs.")
    QUICK = (EnemyType.QUICK_SORT, 72, 150, "Ceramic and fast; splits in two.")
    COUNTING = (EnemyType.COUNTING_SORT, 60, 150, "Releases four Primitive Variables.")
    HEAP = (EnemyType.HEAP_SORT, 65, 200, "Lead-type; shields the units behind it.")
    RADIX = (EnemyType.RADIX_SORT, 75, 200, "Armoured digit phases; takes 6 integrity.")
    BUCKET = (EnemyType.BUCKET_SORT, 68, 200, "Carries weaker units past the towers.")
    TIMSORT = (EnemyType.TIMSORT, 140, 250, "Fast hybrid; splits into Merge + Insertion.")
    # the bosses keep their beta 3.0 health here (the last column: base HP in this mode, instead of the campaign's buffed
    # base HP) and carry their signature abilities, which the price includes
    MOAB = (EnemyType.BELLARMINE_COLLEGE_PREP, 1400, 260, "MOAB-class boss: {hp} HP, a Crest Shield at half health, 30 integrity.", 1300)
    BFB = (EnemyType.SW_RESOURCE_CONSULTANT, 5200, 340, "BFB-class boss: {hp} HP, outsources Quick Sorts, releases 3 MOABs, 60 integrity.", 7500)
    DDT = (EnemyType.LOCKHEED_MARTIN, 3000, 440, "DDT-class: {hp} HP, camo, lead, afterburner bursts, 50 integrity.", 850)
    ZOMG = (EnemyType.THREE_COM, 16000, 560, "ZOMG-class: {hp} HP, a network hub that shields nearby units, 100 integrity.", 8000)
    BAD = (EnemyType.PALANTIR, 30000, 680, "The BAD: {hp} HP, phases, jams towers, 100 integrity.", 50000)

    def _init(self, type_, price, unlock_at, blurb, base_hp=None):
        self.type = type_
        self.price = price
        self.unlock_at = float(unlock_at)
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
            return 90.0
        if m is Modifier.CAMO:
            return 180.0
        if m is Modifier.INJECTION:
            return 360.0
        return 240.0

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
        p = float(self.price)
        if mods is not None and self.accepts_modifiers():
            for m in mods:
                p *= AttackUnit.modifier_factor(m)
        return jint(jround(p))


class AttackAbility(JEnum):
    OVERCLOCK = ("Overclock", 300, 40, 6, 120, "All units on the track move 50% faster for 6 s.")
    HOTFIX = ("Hotfix", 600, 45, 0, 180, "Every unit on the track heals to full health.")
    ZERO_DAY = ("Zero-Day", 900, 60, 6, 240, "Jams the AI's 3 most expensive towers for 6 s.")

    def _init(self, display_name, cost, cooldown, duration, unlock_at, description):
        self.display_name = display_name
        self.cost = cost
        self.cooldown = float(cooldown)
        self.duration = float(duration)
        self.unlock_at = float(unlock_at)
        self.description = description


OVERCLOCK_SPEED = 1.5
ZERO_DAY_TARGETS = 3


def _fmt(v):
    s = "%.2f" % v
    while s.endswith("0"):
        s = s[:-1]
    return s[:-1] if s.endswith(".") else s


class DefenderProfile(JEnum):
    NOVICE = (Difficulty.O1, "Novice", "Builds casually: random placement, no ability micro, reacts to camo only after it gets through. 0.9x funding.",
              0.9, 1.0, True, False, False, 1.0, 0, 0, 0.90, 1.10, 1.10, 80)
    COMPETENT = (Difficulty.ON, "Competent", "Efficient build, smart placement and ability micro, but it reacts to camo only once it sees some.",
                 1.0, 0.5, False, False, False, 1.0, 0, 0, 1.00, 1.00, 1.00, 100)
    EXPERT = (Difficulty.ON2, "Expert", "Builds detection the moment you can buy camo, saves greedily for $15,000 ability unlocks. 1.3x funding.",
              1.3, 0.25, False, True, True, 1.0, 8, 0, 1.10, 0.95, 0.95, 125)
    SUPERINTELLIGENCE = (Difficulty.ONN, "Superintelligence", "Expert play without the greed (unlocks only on a wide tower base), 1.6x funding. Breaking it takes a real plan.",
                         1.6, 0.25, False, True, True, 1.0, 12, 4, 1.20, 0.90, 0.90, 150)

    def _init(self, level, display_name, description, income, think_interval, casual, anticipates_camo, unlocks_abilities,
              start_cash, unlock_min_towers, unlock_towers_per, tower_damage, unit_hp, attacker_income, integrity):
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

    def rules_line(self):
        return ("AI towers x" + _fmt(self.tower_damage) + " damage, AI integrity " + str(self.integrity) + ". Your units x"
                + _fmt(self.unit_hp) + " health, your compute income x" + _fmt(self.attacker_income) + ".")

    @staticmethod
    def of(d):
        for p in DefenderProfile:
            if p.level is d:
                return p
        return DefenderProfile.COMPETENT
