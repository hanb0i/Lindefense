package lindefense.tower.data;

import static lindefense.tower.TowerStats.u;

import java.util.Arrays;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.tower.AttackKind;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;
import lindefense.tower.data.TowerBuilder.AbilityBuilder;

/**
 * Spec 3.2 PRIMARY: Gemini, Claude, GPT, plus Zethos (the Quantum Architect: four upgrades, distances in map units via
 * {@link lindefense.tower.TowerStats#u}). Zethos parameters: {@code splashPct} (splash damage fraction per impact),
 * {@code bouncePct} (bounce-hit damage fraction); Reality Collapse {@code duration, damageMult, rateMult, rangeBonus,
 * bounces} and, for tiers that have no explosion / bounce yet, {@code fallbackSplash, fallbackSplashPct,
 * fallbackBouncePct}. Unspecified by the spec: the projectile speed after Quantum Acceleration (65 units/s) and the
 * bounce reach (25 units). Zethos is tuned to about TWICE the best of Gemini, Claude and GPT at the same tier (damage
 * 2 / 3 / 4 / 6 / 7, intervals and ranges near theirs, splash and bounces trimmed): measured as crowd damage per second
 * and single-target damage per second, averaged, about 1.9x-2.2x at tiers 0-3 and 2.5x for the extra fifth tier.
 * Parameters: GPT {@code moonCount, moonRadius, moonDamage, moonInterval} plus the unspecified {@code moonOrbitSpeed} (rad/s) and
 * {@code moonSize} (contact radius px); Astra Beam {@code duration, dps, bossMult, tick}, GPT U3 knockback is the hit's
 * {@code knockbackVsLead}; Gemini U2 strip flag is the hit's {@code stripsCamoRegrow}.
 */
public final class PrimaryTowers {
    private PrimaryTowers() { }

    public static List<TowerDef> all() { return Arrays.asList(gemini(), claude(), gpt(), zethos()); }

    static TowerDef zethos() {
        return TowerBuilder.of(TowerType.ZETHOS, "The Quantum Architect", 650)
            .description("Precision quantum-energy projectiles that pierce the first enemies on the track, fracture into splash at Tier 2 and bounce between enemies from Tier 3. One projectile never damages the same enemy twice. Expensive upgrade path. No camo detection.")
            .tiers("Quantum Pulse", "Quantum Acceleration", "Dimensional Fracture", "Quantum Singularity", "Zethos: Reality Engine")
            .attack(AttackKind.PROJECTILE, DamageType.ENERGY, u(45), 0.65, 2, 2)
            .base(s -> { s.projectileSpeed = u(55); s.bounceRange = u(25); s.set("splashPct", 0).set("bouncePct", 0); })
            .upgrade(350, null, "Damage 3, interval 0.6 s, range 46 units, pierce 4. Faster projectiles (65 units/s) with a brighter energy trail.",
                s -> { s.hit.damage = 3; s.interval(0.6); s.range = u(46); s.pierce = 4; s.projectileSpeed = u(65); })
            .upgrade(650, null, "Damage 4, interval 0.5 s, range 47 units, pierce 5. Each impact fractures into quantum fragments: 60% splash damage within 7 units.",
                s -> { s.hit.damage = 4; s.interval(0.5); s.range = u(47); s.pierce = 5; s.splashRadius = u(7); s.set("splashPct", 0.60); })
            .upgrade(1200, null, "Damage 6, interval 0.55 s, range 48 units, pierce 5. Singularity explosions: 45% splash within 6 units. Then bounces to up to 2 more enemies at 45% damage.",
                s -> { s.hit.damage = 6; s.interval(0.55); s.range = u(48); s.pierce = 5; s.splashRadius = u(6); s.set("splashPct", 0.45);
                    s.bounces = 2; s.set("bouncePct", 0.45); })
            .upgrade(2500, null, "Damage 7, interval 0.5 s, range 50 units, pierce 6. Every impact explodes for 35% damage within 6 units; bounces to up to 2 more enemies at 35% damage.",
                s -> { s.hit.damage = 7; s.interval(0.50); s.range = u(50); s.pierce = 6; s.splashRadius = u(6); s.set("splashPct", 0.35);
                    s.bounces = 2; s.set("bouncePct", 0.35); })
            .ability(AbilityBuilder.of("Reality Collapse", 55, "For 6 s: double damage, double attack speed, +15 units range, projectiles bounce to up to 8 extra enemies and every impact explodes.")
                .p("duration", 6).p("damageMult", 2.0).p("rateMult", 2.0).p("rangeBonus", u(15)).p("bounces", 8)
                .p("fallbackSplash", u(5)).p("fallbackSplashPct", 0.50).p("fallbackBouncePct", 0.75))
            .build();
    }

    static TowerDef gemini() {
        return TowerBuilder.of(TowerType.GEMINI, "Prism Blaster", 400)
            .description("Instant-hit laser bolts that ricochet and later chain through a crowd. Gains camo detection at U2.")
            .tiers("Gemini 3.7 Flash", "Gemini 3.8 Flash", "Gemini 3.1 Pro", "Gemini 4 Argon")
            .attack(AttackKind.INSTANT, DamageType.ENERGY, 180, 0.8, 1, 1)
            .upgrade(650, null, "Interval 0.5, pierce 3, beams ricochet to up to 3 more enemies within 80 px.",
                s -> { s.interval(0.5); s.pierce = 3; s.chainHops = 3; s.chainRange = 80; })
            .upgrade(700, "Spectrum Analysis", "Gains camo detection. Hits permanently remove Camo and Regrow from non-boss enemies.",
                s -> { s.seesCamo = true; s.hit.stripsCamoRegrow = true; })
            .upgrade(1200, "Prismatic Beam", "Chains to up to 8 enemies; damage 2; x3 vs MOAB-class.",
                s -> { s.chainHops = 7; s.hit.damage = 2; s.hit.multVsBoss = 3; })
            .ability(AbilityBuilder.of("Argon Singularity", 30, "Pulls every non-boss enemy within 400 px into a vortex and holds it there for 6 s, then deals 500 damage to each. Bosses caught in it take 5,000.")
                .p("radius", 400).p("holdTime", 6).p("damage", 500).p("bossDamage", 5000).p("pullSpeed", 300))
            .build();
    }

    static TowerDef claude() {
        return TowerBuilder.of(TowerType.CLAUDE, "Ink Weaver", 450)
            .description("Needle prose spikes. Sharp damage cannot hurt Lead-type enemies until the final upgrade. No camo detection.")
            .tiers("Claude Haiku 5.5", "Claude Sonnet 5.5", "Claude Opus 5.5", "Claude Fable 5.1")
            .attack(AttackKind.PROJECTILE, DamageType.SHARP, 190, 0.7, 1, 2)
            .base(s -> { s.projectileSpeed = 700; })
            .upgrade(550, null, "Pierce 8, interval 0.55.",
                s -> { s.pierce = 8; s.interval(0.55); })
            .upgrade(650, "Context Snare", "Hit enemies are MARKED (+1 damage taken) and SLOWED 15% for 4 s.",
                s -> { s.hit.markFlat = 1; s.hit.markDuration = 4; s.hit.slowFraction = 0.15; s.hit.slowDuration = 4; })
            .upgrade(1100, null, "Pierce 20, damage 2, +3 damage vs Fortified / Lead-type / Ceramic-type, and can damage Lead.",
                s -> { s.pierce = 20; s.hit.damage = 2; s.hit.flatVsFortified = 3; s.hit.flatVsLead = 3; s.hit.flatVsCeramic = 3; s.hit.ignoresResistance = true; })
            .ability(AbilityBuilder.of("Opus Time-Lock", 30, "FREEZES every non-boss enemy on the map for 12 s and slows every boss by 60% for 12 s. Frozen enemies take x2 damage.")
                .p("radius", 3000).p("freezeTime", 12).p("bossSlow", 0.6).p("bossSlowTime", 12))
            .build();
    }

    static TowerDef gpt() {
        return TowerBuilder.of(TowerType.GPT, "Cosmic Strategist", 500)
            .description("Plasma orbs that gain splash, two orbiting moons, burning hits and an adaptive final form. No camo detection.")
            .tiers("GPT-5.6 Terra", "GPT-6 Luna", "GPT-6 Astra", "GPT-6.1 Sol")
            .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 180, 0.9, 1, 3)
            .base(s -> { s.projectileSpeed = 550; })
            .upgrade(750, null, "Splash radius 40; two orbiting moons (radius 60) deal 1 damage every 0.5 s on contact.",
                s -> { s.splashRadius = 40; s.set("moonCount", 2).set("moonRadius", 60).set("moonDamage", 1).set("moonInterval", 0.5)
                    .set("moonOrbitSpeed", 2.5).set("moonSize", 8); })
            .upgrade(800, "Solar Flare", "Hits BURN for 1 damage/s over 3 s.",
                s -> { s.hit.dotDps = 1; s.hit.dotDuration = 3; })
            .upgrade(1300, "Adaptive Plasma", "Each shot checks its target: x2 vs MOAB-class, +2 vs Fortified, +2 vs Ceramic-type, SONIC-like knockback vs Lead-type.",
                s -> { s.hit.multVsBoss = 2; s.hit.flatVsFortified = 2; s.hit.flatVsCeramic = 2; s.hit.knockbackVsLead = 20; })
            .ability(AbilityBuilder.of("Astra Beam", 35, "12 s continuous beam on the strongest enemy: 1,500 damage/s, x2 vs MOAB-class (3,000/s), ignores Fortified.")
                .p("duration", 12).p("dps", 1500).p("bossMult", 2).p("tick", 0.25))
            .build();
    }
}
