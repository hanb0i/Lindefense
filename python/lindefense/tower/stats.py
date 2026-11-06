"""Tower definitions: per-tier stats, upgrades, abilities and the immutable TowerDef."""
from lindefense.javacompat import jround
from lindefense.combat.hit_spec import HitSpec
from lindefense.tower.tower_type import AttackKind, Targeting

UNLIMITED_RANGE = 2000.0
MAP_UNIT = 4.0


def u(map_units: float) -> float:
    """Map units to world pixels (Hero Store / Zethos spec distances)."""
    return map_units * MAP_UNIT


def to_units(px: float) -> float:
    return px / MAP_UNIT


class TowerStats:
    UNLIMITED_RANGE = UNLIMITED_RANGE
    MAP_UNIT = MAP_UNIT

    def __init__(self):
        self.kind = AttackKind.PROJECTILE
        self.hit = HitSpec()
        self.range = 150.0
        self.rate = 1.0
        self.pierce = 1
        self.projectile_speed = 450.0
        self.splash_radius = 0.0
        self.chain_hops = 0
        self.chain_range = 80.0
        self.bounces = 0
        self.bounce_range = 90.0
        self.clones = 0
        self.projectiles_per_shot = 1
        self.targets = 1
        self.stack_cap = 0
        self.stack_step = 1.0
        self.sees_camo = False
        self.ignores_los = False
        # aura given to other towers
        self.aura_range = 0.0
        self.aura_rate = 0.0
        self.aura_damage = 0.0
        self.aura_pierce = 0
        self.aura_range_bonus = 0.0
        self.aura_detection = False
        self.aura_surveillance_immunity = False
        self.aura_injection_immunity = False
        # prompt injection
        self.injection_immune = False
        self.injection_immune_reason = None
        # enemy field around the tower
        self.field_radius = 0.0
        self.aura_enemy_slow = 0.0
        self.field_mark_flat = 0.0
        self.field_mark_pct = 0.0
        self.field_affects_bosses = True
        self.income_per_wave = 0.0
        self.summon_interval = 0.0
        self.summon_count = 0
        self._params = {}

    # ---- named parameters
    def p(self, key: str, dflt=None) -> float:
        v = self._params.get(key)
        if v is None:
            if dflt is None:
                raise ValueError("Missing tower parameter '" + key + "'")
            return dflt
        return v

    def pi(self, key: str, dflt=None) -> int:
        v = self._params.get(key)
        if v is None:
            if dflt is None:
                raise ValueError("Missing tower parameter '" + key + "'")
            return dflt
        return jround(v)

    def has(self, key: str) -> bool:
        v = self._params.get(key)
        return v is not None and v != 0

    def set(self, key: str, value: float) -> "TowerStats":
        self._params[key] = float(value)
        return self

    def params(self):
        return self._params

    def set_interval(self, seconds: float) -> "TowerStats":
        self.rate = 1.0 / seconds
        return self

    def interval(self) -> float:
        return 1.0 / self.rate

    def copy(self) -> "TowerStats":
        s = TowerStats.__new__(TowerStats)
        s.__dict__.update(self.__dict__)
        s.hit = self.hit.copy()
        s._params = dict(self._params)
        return s

    def is_support_only(self) -> bool:
        return self.kind is AttackKind.NONE

    def has_unlimited_range(self) -> bool:
        return self.range >= UNLIMITED_RANGE


class UpgradeDef:
    def __init__(self, name: str, cost: int, description: str, apply):
        self.name = name
        self.cost = cost
        self.description = description
        self.apply = apply


class AbilityDef:
    def __init__(self, name, description, cooldown, needs_target, params):
        self.name = name
        self.description = description
        self.cooldown = float(cooldown)
        self.needs_target = needs_target
        self._params = {k: float(v) for k, v in params.items()}

    def p(self, key, dflt=None):
        v = self._params.get(key)
        if v is None:
            if dflt is None:
                raise ValueError("Ability " + self.name + " has no parameter '" + key + "'")
            return dflt
        return v

    def has(self, key) -> bool:
        return key in self._params

    def params(self):
        return dict(self._params)


class TowerDef:
    def __init__(self, type_, subtitle, description, base_cost, radius, base_stats, upgrades, ability, tier_labels,
                 unlock_cost=0, default_targeting=None):
        if len(tier_labels) != len(upgrades) + 1:
            raise ValueError(str(type_) + " must have " + str(len(upgrades) + 1) + " tier labels")
        if type_.is_hero() and unlock_cost <= 0:
            raise ValueError(str(type_) + ": heroes need a Hero Store price")
        self.type = type_
        self.subtitle = subtitle
        self.description = description
        self.base_cost = base_cost
        self.radius = float(radius)
        self.base_stats = base_stats
        self.upgrades = tuple(upgrades)
        self.ability = ability
        self.tier_labels = tuple(tier_labels)
        self.unlock_cost = unlock_cost
        self.default_targeting = Targeting.FIRST if default_targeting is None else default_targeting

    def stats_for_tier(self, tier: int) -> TowerStats:
        s = self.base_stats.copy()
        for i in range(min(tier, len(self.upgrades))):
            self.upgrades[i].apply(s)
        return s

    def total_cost_for_tier(self, tier: int) -> int:
        c = self.base_cost
        for i in range(min(tier, len(self.upgrades))):
            c += self.upgrades[i].cost
        return c

    def total_cost(self) -> int:
        return self.total_cost_for_tier(len(self.upgrades))
