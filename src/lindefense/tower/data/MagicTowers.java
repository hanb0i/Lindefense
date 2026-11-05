package lindefense.tower.data;

import java.util.Arrays;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.tower.AttackKind;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;
import lindefense.tower.data.TowerBuilder.AbilityBuilder;

/**
 * Spec 3.4 MAGIC: DALL-E, Sora, Suno. Owner: agent B2.
 * Parameters: DALL-E {@code zoneInterval, zoneRadius, zoneDuration, zoneTick, zoneDamage, zoneArmorCrack,
 * creatureInterval, creatureCount, creatureDamage, creaturePierce, creatureSpeed (unspecified in the spec: 90 px/s),
 * creatureSpacing (px between creatures of one wave)}; Sora {@code rewindInterval, rewindKnockback,
 * loopZones, loopRadius, loopTickDamage, loopTick, loopSlow}; Suno {@code bassInterval, bassDamage, bassRadius,
 * chordEvery, chordDamage, chordPierce, symphonyInterval, symphonyCount, symphonyRadius, symphonyDamage}.
 */
public final class MagicTowers {
    private MagicTowers() { }

    public static List<TowerDef> all() { return Arrays.asList(dalle(), sora(), suno()); }

    static TowerDef dalle() {
        return TowerBuilder.of(TowerType.DALLE, "Sketch Summoner", 550)
            .description("Sketch arrows, plus paint zones on the track that damage enemies; later illustrated creatures that walk the track backward. No camo detection.")
            .tiers("DALL·E 2", "DALL·E 3", "DALL·E 3 HD", "DALL·E 3 API")
            .attack(AttackKind.PROJECTILE, DamageType.MAGIC, 170, 0.9, 1, 3)
            .base(s -> { s.set("zoneInterval", 6).set("zoneRadius", 35).set("zoneDuration", 4).set("zoneTick", 0.5).set("zoneDamage", 1); })
            .upgrade(500, "Living Illustration", "Every 5 s, 2 illustrated creatures walk backward along the track (contact damage 2, pierce 5 each).",
                s -> { s.set("creatureInterval", 5).set("creatureCount", 2).set("creatureDamage", 2).set("creaturePierce", 5)
                    .set("creatureSpeed", 90).set("creatureSpacing", 24); })
            .upgrade(850, "Masterpiece Explosion", "Paint zones grow to radius 70 and apply ARMOR CRACK to non-boss enemies inside, downgrading armored enemies into weaker forms.",
                s -> { s.set("zoneRadius", 70).set("zoneArmorCrack", 1); })
            .upgrade(1400, "Infinite Canvas", "Zones every 3 s, 4 creatures per wave, arrow pierce 6.",
                s -> { s.set("zoneInterval", 3).set("creatureCount", 4); s.pierce = 6; })
            .ability(AbilityBuilder.of("Outpainting Expansion", 25, "Paints a 30 s \"extra track\" zone (180 px) on the selected track segment: enemies inside crawl at 5% speed (bosses resist part of it) and take 120 magic damage every 0.5 s.")
                .target().p("duration", 30).p("speedCap", 0.05).p("radius", 180).p("tick", 0.5).p("damage", 120))
            .build();
    }

    static TowerDef sora() {
        return TowerBuilder.of(TowerType.SORA, "Time Director", 700)
            .description("Film-frame projectiles and a slowing field around the tower; later rewinds enemies and places time-loop zones. No camo detection.")
            .tiers("Sora", "Sora Turbo", "Sora 2", "Sora 2 Pro")
            .attack(AttackKind.PROJECTILE, DamageType.MAGIC, 160, 1.0, 1, 2)
            .base(s -> { s.fieldRadius = 150; s.auraEnemySlow = 0.35; })
            .upgrade(650, "Fast Forward", "Projectile speed x2, interval 0.7, slow becomes 55%.",
                s -> { s.projectileSpeed *= 2; s.interval(0.7); s.auraEnemySlow = 0.55; })
            .upgrade(1000, "Scene Rewind", "Every 8 s, KNOCKBACK 120 px on all non-boss enemies in range.",
                s -> { s.set("rewindInterval", 8).set("rewindKnockback", 120); })
            .upgrade(1800, "Time Loop", "Places 2 loop zones (radius 60) on the track in range; enemies inside take 2 damage every 0.4 s and are SLOWED 60%.",
                s -> { s.set("loopZones", 2).set("loopRadius", 60).set("loopTickDamage", 2).set("loopTick", 0.4).set("loopSlow", 0.6); })
            .ability(AbilityBuilder.of("Cinematic Rewind", 45, "Every non-boss enemy on screen is thrown back along the track by 15 s of its own travel distance; bosses by 6 s.")
                .p("rewindSeconds", 15).p("bossRewindSeconds", 6))
            .build();
    }

    static TowerDef suno() {
        return TowerBuilder.of(TowerType.SUNO, "Sonic Composer", 500)
            .description("Rhythmic sound projectiles (x2 vs Ceramic, knock Lead-type back); later bass-drop shockwaves, chords and random sonic explosions. No camo detection.")
            .tiers("Suno v5", "Suno v6-Mini", "Suno v6", "Suno v6-Wild")
            .attack(AttackKind.PROJECTILE, DamageType.SONIC, 160, 0.8, 1, 4)
            .upgrade(500, "Bass Drop", "Every 3 s, a shockwave deals 2 damage to all enemies within 140 px.",
                s -> { s.set("bassInterval", 3).set("bassDamage", 2).set("bassRadius", 140); })
            .upgrade(800, "Chord Strike", "Every 4th attack is a chord (damage 6, pierce 10).",
                s -> { s.set("chordEvery", 4).set("chordDamage", 6).set("chordPierce", 10); })
            .upgrade(1350, "Uncontrolled Symphony", "Interval 0.4; every 1 s, 2 random sonic explosions (radius 50, damage 3) on enemies in range.",
                s -> { s.interval(0.4); s.set("symphonyInterval", 1).set("symphonyCount", 2).set("symphonyRadius", 50).set("symphonyDamage", 3); })
            .ability(AbilityBuilder.of("Symphonic Bass Drop", 35, "Every enemy on screen takes 300 + 400 x its speed multiplier damage (bosses capped at 6,000).")
                .p("baseDamage", 300).p("damagePerSpeed", 400).p("bossCap", 6000))
            .build();
    }
}
