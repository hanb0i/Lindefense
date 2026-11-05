package lindefense.tower.data;

import java.util.Arrays;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.tower.AttackKind;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;
import lindefense.tower.data.TowerBuilder.AbilityBuilder;

/**
 * Spec 3.5 SUPPORT: Grok, Perplexity. Owner: agent B2.
 * Parameters: Grok U1 {@code burnSpreadRadius, burnSpreads}, U2 {@code volleyInterval, volleyMissiles,
 * volleyDamage, allowDensest}, U3 {@code chaosCluster, chaosSplit, chaosHeavyMoabMult, chaosSplitRange (unspecified: fragment search radius, 80 px)}; Perplexity {@code
 * pulseInterval, pulseDamage, revealAllCamo}.
 */
public final class SupportTowers {
    private SupportTowers() { }

    public static List<TowerDef> all() { return Arrays.asList(grok(), perplexity()); }

    static TowerDef grok() {
        return TowerBuilder.of(TowerType.GROK, "Chaos Generator", 650)
            .description("Thermal micro-missiles with splash that can hit Lead-type enemies; later burns, densest-cluster volleys and a chaos cycle of missile types. Built-in camo detection.")
            .tiers("Grok 4.5", "Grok 4.6", "Grok 4.20 Reasoning", "Grok 4.7")
            .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, 170, 1.1, 2, 1)
            .base(s -> { s.splashRadius = 35; s.seesCamo = true; })
            .upgrade(600, "Ratio", "Hits BURN for 1 damage/s over 4 s, and the burn spreads once to enemies within 40 px.",
                s -> { s.hit.dotDps = 1; s.hit.dotDuration = 4; s.set("burnSpreadRadius", 40).set("burnSpreads", 1); })
            .upgrade(950, "Paradox Trap", "Unlocks Densest Cluster targeting; every 5 s fires a 6-missile volley (damage 3 each) at the densest cluster.",
                s -> { s.set("allowDensest", 1).set("volleyInterval", 5).set("volleyMissiles", 6).set("volleyDamage", 3); })
            .upgrade(1600, "Chaos Mode", "Interval 0.6; missiles cycle between incendiary (burn), cluster (splits into 4) and heavy (x3 vs MOAB-class).",
                s -> { s.interval(0.6); s.set("chaosCycle", 3).set("chaosSplit", 4).set("chaosHeavyMoabMult", 3).set("chaosSplitRange", 80); })
            .ability(AbilityBuilder.of("Real-Time Override", 40, "EVERY tower on the map deals +400% damage to MOAB-class enemies for 20 s.")
                .p("radius", 5000).p("duration", 20).p("bossDamagePct", 4.0))
            .build();
    }

    static TowerDef perplexity() {
        return TowerBuilder.of(TowerType.PERPLEXITY, "Intelligence Scanner", 450)
            .description("Sonar that grants nearby towers camo detection and pings Camo enemies; later reveals all camo map-wide, marks enemies and boosts range. Earns cash every round.")
            .tiers("Sonar", "Sonar Pro", "Sonar Reasoning Pro", "Sonar Deep Research")
            .attack(AttackKind.CUSTOM, DamageType.MAGIC, 180, 2.0, 1, 1)
            .base(s -> { s.seesCamo = true; s.auraRange = 180; s.auraDetection = true; s.incomePerWave = 40; s.set("pulseDamage", 1); })
            .upgrade(450, "Target Identification", "All Camo enemies on the map can be targeted by every tower while this tower exists.",
                s -> { s.set("revealAllCamo", 1); })
            .upgrade(750, "Predictive Analysis", "Enemies in range are MARKED (+20% damage taken); towers in range get +15% range. Towers within this radius are immune to Predictive Surveillance.",
                s -> { s.fieldMarkPct = 0.20; s.auraRangeBonus = 0.15; s.auraSurveillanceImmunity = true; })
            .upgrade(1250, null, "End-of-round bonus becomes +$250.",
                s -> { s.incomePerWave = 250; })
            .ability(AbilityBuilder.of("Deep Research Scrape", 60, "Instantly gain cash equal to 100% of the current round's pop value so far (max $15,000).")
                .p("popValuePct", 1.0).p("maxCash", 15000))
            .build();
    }
}
