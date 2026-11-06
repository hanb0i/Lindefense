"""Damage categories and HitSpec: what one hit does to an enemy (neutral defaults: multipliers 1, everything else 0)."""
from lindefense.jenum import JEnum


class DamageType(JEnum):
    SHARP = ("Sharp",)
    BLUNT = ("Blunt",)
    KINETIC = ("Kinetic",)
    ENERGY = ("Energy",)
    EXPLOSIVE = ("Explosive",)
    SONIC = ("Sonic",)
    MAGIC = ("Magic",)
    GRAVITY = ("Gravity",)
    TRUE = ("True",)   # internal: ignores resistances, immunities, armour and marks

    def _init(self, label):
        self.label = label

    def is_blunt_like(self) -> bool:
        return self is DamageType.BLUNT or self is DamageType.KINETIC


class HitSpec:
    def __init__(self, damage: float = 1.0, type_=None):
        self.damage = float(damage)
        self.type = DamageType.ENERGY if type_ is None else type_
        self.armor_pierce = 0.0
        self.ignores_resistance = False
        # situational damage
        self.mult_vs_boss = 1.0
        self.flat_vs_boss = 0.0
        self.mult_vs_fortified = 1.0
        self.flat_vs_fortified = 0.0
        self.flat_vs_lead = 0.0
        self.mult_vs_lead = 1.0
        self.flat_vs_ceramic = 0.0
        self.mult_vs_ceramic = 1.0
        self.mult_vs_sorting_and_lists = 1.0
        self.mult_vs_high_hp = 1.0
        # legacy additive percent bonuses
        self.bonus_vs_boss = 0.0
        self.bonus_vs_fortified = 0.0
        self.bonus_vs_non_fortified = 0.0
        self.bonus_vs_complex = 0.0
        self.bonus_vs_fast = 0.0
        self.bonus_vs_splitters = 0.0
        self.pct_max_hp = 0.0
        self.pct_cap = 60.0
        # control effects
        self.slow_fraction = 0.0
        self.slow_duration = 0.0
        self.stun_duration = 0.0
        self.boss_stun_duration = 0.0
        self.knockback = 0.0
        self.boss_knockback = 0.0
        self.knockback_vs_fast = 0.0
        self.knockback_vs_lead = 0.0
        self.uncapped_knockback = False
        self.armor_break = 0.0
        self.armor_break_duration = 0.0
        self.mark_bonus = 0.0
        self.mark_flat = 0.0
        self.mark_duration = 0.0
        self.disrupt_duration = 0.0
        self.dot_dps = 0.0
        self.dot_duration = 0.0
        self.strips_fortified = False
        self.strips_camo_regrow = False

    def copy(self) -> "HitSpec":
        h = HitSpec.__new__(HitSpec)
        h.__dict__.update(self.__dict__)
        return h
