"""Fluent builder used by the per-faction data files (all numbers live in the stat lambdas)."""
from lindefense.tower.stats import AbilityDef, TowerDef, TowerStats, UpgradeDef
from lindefense.tower.tower_type import Targeting


class TowerBuilder:
    def __init__(self, type_, subtitle, cost):
        self._type = type_
        self._subtitle = subtitle
        self._cost = cost
        self._description = ""
        self._tiers = None
        self._base = TowerStats()
        self._upgrades = []
        self._ability = None
        self._radius = 20.0
        self._unlock_cost = 0
        self._targeting = Targeting.FIRST

    @staticmethod
    def of(type_, subtitle, cost):
        return TowerBuilder(type_, subtitle, cost)

    def description(self, d):
        self._description = d
        return self

    def tiers(self, *labels):
        self._tiers = tuple(labels)
        return self

    def unlock_cost(self, cost):
        self._unlock_cost = cost
        return self

    def targeting(self, t):
        self._targeting = t
        return self

    def attack(self, kind, dt, range_, interval, damage, pierce):
        b = self._base
        b.kind = kind
        b.hit.type = dt
        b.range = float(range_)
        b.set_interval(interval)
        b.hit.damage = float(damage)
        b.pierce = pierce
        return self

    def base(self, f):
        f(self._base)
        return self

    def upgrade(self, up_cost, mechanic, desc, f):
        i = len(self._upgrades)
        if self._tiers is None:
            raise RuntimeError(str(self._type) + ": call tiers() before upgrade()")
        if i + 1 >= len(self._tiers):
            raise RuntimeError(str(self._type) + ": more upgrades than tier labels")
        text = desc if not mechanic else mechanic + ": " + desc
        self._upgrades.append(UpgradeDef(self._tiers[i + 1], up_cost, text, f))
        return self

    def ability(self, a):
        self._ability = a.build()
        return self

    def radius(self, r):
        self._radius = float(r)
        return self

    def injection_immune(self, why):
        self._base.injection_immune = True
        self._base.injection_immune_reason = why
        return self

    def build(self):
        return TowerDef(self._type, self._subtitle, self._description, self._cost, self._radius, self._base,
                        self._upgrades, self._ability, self._tiers, self._unlock_cost, self._targeting)


class AbilityBuilder:
    def __init__(self, name, cooldown, desc):
        self._name = name
        self._cooldown = cooldown
        self._desc = desc
        self._needs_target = False
        self._params = {}

    @staticmethod
    def of(name, cooldown, desc):
        return AbilityBuilder(name, cooldown, desc)

    def target(self):
        self._needs_target = True
        return self

    def p(self, key, value):
        self._params[key] = float(value)
        return self

    def build(self):
        return AbilityDef(self._name, self._desc, self._cooldown, self._needs_target, self._params)
