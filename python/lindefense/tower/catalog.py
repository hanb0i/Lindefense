"""Central tower registry built from the per-faction data files (lazily, on first use)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.stats import TowerDef
from lindefense.tower.tower_type import AttackKind, TowerType

STANDARD_UPGRADES = 3
ZETHOS_UPGRADES = 4
ABILITY_UNLOCK_COST = 15_000

_DEFS = {}


def _ensure():
    if _DEFS:
        return
    from lindefense.tower.data import heroes, primary, military, magic, support, titans
    from lindefense.tower.data.builder import TowerBuilder
    for module in (heroes, primary, military, magic, support, titans):
        for d in module.all_towers():
            _DEFS[d.type] = _without_ability(d) if d.type.is_hero() else d
    noop = lambda s: None
    _DEFS[TowerType.DALLE_SPRITE] = (TowerBuilder.of(TowerType.DALLE_SPRITE, "Illustrated creature", 0)
                                     .description("Internal. DALL-E creatures are track walkers now, not towers.")
                                     .tiers("Sprite", "Sprite", "Sprite", "Sprite")
                                     .attack(AttackKind.NONE, DamageType.MAGIC, 100, 1.0, 1, 1)
                                     .upgrade(0, None, "None.", noop)
                                     .upgrade(0, None, "None.", noop)
                                     .upgrade(0, None, "None.", noop)
                                     .build())


def _without_ability(d):
    return TowerDef(d.type, d.subtitle, d.description, d.base_cost, d.radius, d.base_stats, d.upgrades, None,
                    d.tier_labels, d.unlock_cost, d.default_targeting)


def get(type_):
    _ensure()
    return _DEFS.get(type_)


def all_defs():
    _ensure()
    return {t: _DEFS[t] for t in TowerType if t in _DEFS}


def has_active_ability(type_) -> bool:
    d = get(type_)
    return not type_.is_hero() and d is not None and d.ability is not None


def ability_needs_unlock(type_) -> bool:
    return not type_.is_hero()


def is_injection_immune(type_) -> bool:
    d = get(type_)
    return d is not None and d.base_stats.injection_immune


def injection_immunity_reason(type_):
    return get(type_).base_stats.injection_immune_reason if is_injection_immune(type_) else None


def grants_injection_firewall(type_) -> bool:
    d = get(type_)
    return d is not None and d.base_stats.aura_injection_immunity
