"""Military towers: DeepSeek, Copilot (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.ignores_los = True


def _f2(s):
    s.projectiles_per_shot = 3
    s.pierce = 3


def _f3(s):
    s.set("defaultStrongest", 1).set("streakStep", 1).set("streakMax", 6)
    s.stack_cap = 6
    s.stack_step = 1


def _f4(s):
    s.hit.damage = 6
    s.hit.mult_vs_sorting_and_lists = 3
    s.hit.mult_vs_boss = 2


def _f5(s):
    s.aura_range = 150
    s.aura_rate = 0.10
    s.aura_injection_immunity = True


def _f6(s):
    s.aura_rate = 0.20
    s.aura_pierce = 1


def _f7(s):
    s.set("droneInterval", 8).set("droneDamage", 6).set("droneSplash", 70)


def _f8(s):
    s.set("globalMilitaryRate", 0.15).set("globalMilitaryDamage", 1)
    s.aura_rate = 0.30
    s.aura_pierce = 2


def deepseek():
    return (TowerBuilder.of(TowerType.DEEPSEEK, "Railgun Engineer", 600)
        .description("Map-wide instant-hit sniper that ignores line-of-sight blockers. Volleys, a recursive damage lock and a final-form slayer of sorting algorithms. No camo detection.")
        .tiers("DeepSeek V4 Flash", "DeepSeek V4.1 Flash", "DeepSeek R1", "DeepSeek V4 Pro")
        .attack(AttackKind.INSTANT, DamageType.ENERGY, UNLIMITED_RANGE, 1.6, 2, 1)
        .base(_f1)
        .injection_immune("Chain-of-thought reasoning: it thinks the injected prompt through and catches the trick.")
        .upgrade(850, "Parallel Processing", "3 shots per volley, pierce 3.",
        _f2)
        .upgrade(900, "Recursive Lock", "Default targeting becomes Strongest. Each consecutive hit on the same target adds +1 damage (max +6); the bonus resets when the target changes.",
        _f3)
        .upgrade(1500, "Advanced Computation", "Damage 6; x3 vs all Sorting Algorithm enemies and Linked Lists; x2 vs bosses.",
        _f4)
        .ability(AbilityBuilder.of("R1 Deep Reasoning Strike", 45, "Instantly destroys the 10 strongest non-boss enemies (no children; each parent's cash is paid once) and strikes every boss for 6% of its max HP (Palantir 2.5%).")
        .p("count", 10).p("bossDamagePct", 0.06).p("palantirDamagePct", 0.025))
        .build())


def copilot():
    return (TowerBuilder.of(TowerType.COPILOT, "Autonomous Engineer", 350)
        .description("Code fragments with a tether that speeds up nearby towers. Later launches explosive drones and powers every Military tower on the map. No camo detection.")
        .tiers("Copilot", "Copilot Pro", "Microsoft 365 Copilot", "GitHub Copilot Enterprise")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 150, 1.0, 1, 1)
        .base(_f5)
        .injection_immune("Security Copilot: its firewall also shields every tower in its tether radius.")
        .upgrade(350, "Hotfix", "Tether bonus becomes +20% attack speed and +1 pierce.",
        _f6)
        .upgrade(600, "Task Scheduler", "Every 8 s launches an explosive drone at the densest cluster (damage 6, splash 70).",
        _f7)
        .upgrade(1000, "Enterprise Network", "All MILITARY towers anywhere on the map get +15% attack speed and +1 damage; the local tether becomes +30% speed and +2 pierce.",
        _f8)
        .ability(AbilityBuilder.of("Enterprise Auto-Refactor", 60, "EVERY tower on the map attacks x2 faster for 10 s. Stacks with other speed boosts and ignores the tower-buff cap.")
        .p("duration", 10).p("rateMult", 2).p("allTowers", 1))
        .build())


def all_towers():
    return [deepseek(), copilot()]
