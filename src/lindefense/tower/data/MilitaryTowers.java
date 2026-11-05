package lindefense.tower.data;

import java.util.Arrays;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.tower.AttackKind;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.data.TowerBuilder.AbilityBuilder;

/**
 * Spec 3.3 MILITARY: DeepSeek, Copilot. Owner: agent B1.
 * Parameters: DeepSeek U2 {@code streakStep, streakMax, defaultStrongest}; Copilot U2 {@code droneInterval,
 * droneDamage, droneSplash}, U3 {@code globalMilitaryRate, globalMilitaryDamage}.
 */
public final class MilitaryTowers {
    private MilitaryTowers() { }

    public static List<TowerDef> all() { return Arrays.asList(deepseek(), copilot()); }

    static TowerDef deepseek() {
        return TowerBuilder.of(TowerType.DEEPSEEK, "Railgun Engineer", 600)
            .description("Map-wide instant-hit sniper that ignores line-of-sight blockers. Volleys, a recursive damage lock and a final-form slayer of sorting algorithms. No camo detection.")
            .tiers("DeepSeek V4 Flash", "DeepSeek V4.1 Flash", "DeepSeek R1", "DeepSeek V4 Pro")
            .attack(AttackKind.INSTANT, DamageType.ENERGY, TowerStats.UNLIMITED_RANGE, 1.6, 2, 1)
            .base(s -> { s.ignoresLos = true; })
            .injectionImmune("Chain-of-thought reasoning: it thinks the injected prompt through and catches the trick.")
            .upgrade(850, "Parallel Processing", "3 shots per volley, pierce 3.",
                s -> { s.projectilesPerShot = 3; s.pierce = 3; })
            .upgrade(900, "Recursive Lock", "Default targeting becomes Strongest. Each consecutive hit on the same target adds +1 damage (max +6); the bonus resets when the target changes.",
                s -> { s.set("defaultStrongest", 1).set("streakStep", 1).set("streakMax", 6); s.stackCap = 6; s.stackStep = 1; })
            .upgrade(1500, "Advanced Computation", "Damage 6; x3 vs all Sorting Algorithm enemies and Linked Lists; x2 vs bosses.",
                s -> { s.hit.damage = 6; s.hit.multVsSortingAndLists = 3; s.hit.multVsBoss = 2; })
            .ability(AbilityBuilder.of("R1 Deep Reasoning Strike", 25, "Instantly destroys the 25 strongest non-boss enemies (no children; each parent's cash is paid once) and strikes every boss for 15% of its max HP (Palantir 5%).")
                .p("count", 25).p("bossDamagePct", 0.15).p("palantirDamagePct", 0.05))
            .build();
    }

    static TowerDef copilot() {
        return TowerBuilder.of(TowerType.COPILOT, "Autonomous Engineer", 350)
            .description("Code fragments with a tether that speeds up nearby towers. Later launches explosive drones and powers every Military tower on the map. No camo detection.")
            .tiers("Copilot", "Copilot Pro", "Microsoft 365 Copilot", "GitHub Copilot Enterprise")
            .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 150, 1.0, 1, 1)
            .base(s -> { s.auraRange = 150; s.auraRate = 0.10; s.auraInjectionImmunity = true; })
            .injectionImmune("Security Copilot: its firewall also shields every tower in its tether radius.")
            .upgrade(350, "Hotfix", "Tether bonus becomes +20% attack speed and +1 pierce.",
                s -> { s.auraRate = 0.20; s.auraPierce = 1; })
            .upgrade(600, "Task Scheduler", "Every 8 s launches an explosive drone at the densest cluster (damage 6, splash 70).",
                s -> { s.set("droneInterval", 8).set("droneDamage", 6).set("droneSplash", 70); })
            .upgrade(1000, "Enterprise Network", "All MILITARY towers anywhere on the map get +15% attack speed and +1 damage; the local tether becomes +30% speed and +2 pierce.",
                s -> { s.set("globalMilitaryRate", 0.15).set("globalMilitaryDamage", 1); s.auraRate = 0.30; s.auraPierce = 2; })
            .ability(AbilityBuilder.of("Enterprise Auto-Refactor", 45, "EVERY tower on the map attacks x3 faster for 20 s. Stacks with other speed boosts and ignores the tower-buff cap.")
                .p("duration", 20).p("rateMult", 3).p("allTowers", 1))
            .build();
    }
}
