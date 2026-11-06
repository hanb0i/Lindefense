"""Support towers: Grok, Perplexity (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.splash_radius = 35
    s.sees_camo = True


def _f2(s):
    s.hit.dot_dps = 1
    s.hit.dot_duration = 4
    s.set("burnSpreadRadius", 40).set("burnSpreads", 1)


def _f3(s):
    s.set("allowDensest", 1).set("volleyInterval", 5).set("volleyMissiles", 6).set("volleyDamage", 3)


def _f4(s):
    s.set_interval(0.6)
    s.set("chaosCycle", 3).set("chaosSplit", 4).set("chaosHeavyMoabMult", 3).set("chaosSplitRange", 80)


def _f5(s):
    s.sees_camo = True
    s.aura_range = 180
    s.aura_detection = True
    s.income_per_wave = 40
    s.set("pulseDamage", 1)


def _f6(s):
    s.set("revealAllCamo", 1)


def _f7(s):
    s.field_mark_pct = 0.20
    s.aura_range_bonus = 0.15
    s.aura_surveillance_immunity = True


def _f8(s):
    s.income_per_wave = 250
    s.aura_damage = 1


def grok():
    return (TowerBuilder.of(TowerType.GROK, "Chaos Generator", 650)
        .description("Thermal micro-missiles with splash that can hit Lead-type enemies; later burns, densest-cluster volleys and a chaos cycle of missile types. Built-in camo detection.")
        .tiers("Grok 4.5", "Grok 4.6", "Grok 4.20 Reasoning", "Grok 4.7")
        .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, 170, 1.1, 2, 1)
        .base(_f1)
        .upgrade(600, "Ratio", "Hits BURN for 1 damage/s over 4 s, and the burn spreads once to enemies within 40 px.",
        _f2)
        .upgrade(950, "Paradox Trap", "Unlocks Densest Cluster targeting; every 5 s fires a 6-missile volley (damage 3 each) at the densest cluster.",
        _f3)
        .upgrade(1600, "Chaos Mode", "Interval 0.6; missiles cycle between incendiary (burn), cluster (splits into 4) and heavy (x3 vs MOAB-class).",
        _f4)
        .ability(AbilityBuilder.of("Real-Time Override", 50, "Towers within 350 px deal +150% damage to MOAB-class enemies for 12 s.")
        .p("radius", 350).p("duration", 12).p("bossDamagePct", 1.5))
        .build())


def perplexity():
    return (TowerBuilder.of(TowerType.PERPLEXITY, "Intelligence Scanner", 450)
        .description("Sonar that grants nearby towers camo detection and pings Camo enemies; later reveals all camo map-wide, marks enemies and boosts range. Earns cash every round.")
        .tiers("Sonar", "Sonar Pro", "Sonar Reasoning Pro", "Sonar Deep Research")
        .attack(AttackKind.CUSTOM, DamageType.MAGIC, 180, 2.0, 1, 1)
        .base(_f5)
        .injection_immune("Source verification: it checks where an instruction came from before obeying it.")
        .upgrade(450, "Target Identification", "All Camo enemies on the map can be targeted by every tower while this tower exists.",
        _f6)
        .upgrade(750, "Predictive Analysis", "Enemies in range are MARKED (+20% damage taken); towers in range get +15% range. Towers within this radius are immune to Predictive Surveillance.",
        _f7)
        .upgrade(1250, "Knowledge Synthesis", "End-of-round bonus becomes +$250, and towers in its radius gain +1 damage per hit.",
        _f8)
        .ability(AbilityBuilder.of("Deep Research Scrape", 60, "Instantly gain cash equal to 35% of the current round's pop value so far (max $3,000).")
        .p("popValuePct", 0.35).p("maxCash", 3000))
        .build())


def all_towers():
    return [grok(), perplexity()]
