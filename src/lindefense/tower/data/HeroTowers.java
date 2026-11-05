package lindefense.tower.data;

import static lindefense.tower.TowerStats.u;

import java.util.Arrays;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.tower.AttackKind;
import lindefense.tower.Targeting;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;

/**
 * HERO STORE: the 18 heroes. A hero is bought once in the Hero Store ({@code unlockCost}, a permanent unlock saved
 * between sessions), then deployed free, once per match, and upgraded in-match like any tower: base + exactly three
 * purchasable upgrades, so every hero has four progression levels.
 *
 * <p>Distances are written in the specification's map units with {@link lindefense.tower.TowerStats#u} (1 unit =
 * {@value lindefense.tower.TowerStats#MAP_UNIT} px); intervals are seconds between attacks and damage is raw HP.
 * Every mechanic number lives here as a named parameter ({@code s.set("name", v)}, read with {@code stats.p("name")}),
 * never as a literal in behaviour code, so the whole roster can be retuned from this one file.</p>
 *
 * <p>The roles are deliberately spread: artillery (Lobber Luis, Boom Sam), healing (Sage Aarav), melee control
 * (Iron Imraan), ice and time control (Chillstin, Justin Time), a beam monster (Kaiju Kai), flyers (Abhi-Ace,
 * Tanimbus), chain lightning (Zippy Matt), economy (Sunny Joe), sniping (Nik-Scope), traps and mines (Cami-Mine,
 * Trapper Che), piercing spears (Spear Hanbo), poison (Thorn Tuhin) and suppressing fire (Blitz Arnav).
 * Mr. Lindemann, the teacher, is the strongest hero (black holes of Java code plus a map-wide space warp) and the
 * priciest; Spear Hanbo is the second strongest.</p>
 */
public final class HeroTowers {
    private HeroTowers() { }

    public static List<TowerDef> all() {
        return Arrays.asList(lobberLuis(), sageAarav(), ironImraan(), boomSam(), chillstin(), kaijuKai(), abhiAce(),
            zippyMatt(), sunnyJoe(), nikScope(), camiMine(), justinTime(), spearHanbo(), thornTuhin(), trapperChe(),
            blitzArnav(), tanimbus(), mrLindemann());
    }

    /** 1. Explosive artillery: arcing bombs that cluster, then call orbital strikes. */
    static TowerDef lobberLuis() {
        return TowerBuilder.of(TowerType.LOBBER_LUIS, "Explosive Artillery", 0)
            .unlockCost(900)
            .description("Hero. Lobs an arcing explosive that deals full damage to everything in the blast. Slow, long-ranged and built for dense groups; later splits into cluster bombs and finally calls orbital strikes.")
            .tiers("Lob Shot", "Heavy Payload", "Cluster Bombs", "Orbital Artillery")
            .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(55), 2.5, 30, 1)
            .base(s -> { s.splashRadius = u(12); s.projectileSpeed = u(40); })
            .upgrade(400, null, "Damage 30 -> 45 and blast radius 12 -> 15 units; a visibly heavier shell.",
                s -> { s.hit.damage = 45; s.splashRadius = u(15); })
            .upgrade(850, null, "The shell splits on impact into 3 bomblets, each dealing 25 damage in 7 units.",
                s -> { s.set("clusterBombs", 3).set("clusterDamage", 25).set("clusterSplash", u(7)); })
            .upgrade(1500, null, "Damage 45 -> 100, blast radius 15 -> 22 units, and every 5th shot lands as a double-damage orbital strike with a shockwave.",
                s -> { s.hit.damage = 100; s.splashRadius = u(22); s.set("orbitalEvery", 5).set("orbitalMult", 2.0); })
            .build();
    }

    /** 2. Healing support: restores the player's integrity (lives); never attacks. */
    static TowerDef sageAarav() {
        return TowerBuilder.of(TowerType.SAGE_AARAV, "Healing and Defensive Support", 0)
            .unlockCost(1000)
            .description("Hero. Never attacks. A healing aura restores the integrity leaks take away, up to your starting maximum, and later shields nearby towers and performs one emergency restoration per match.")
            .tiers("Healing Aura", "Restorative Energy", "Protective Blessing", "Divine Restoration")
            .attack(AttackKind.NONE, DamageType.ENERGY, u(40), 5.0, 0, 1)
            .base(s -> { s.fieldRadius = u(40); s.set("healAmount", 5).set("healInterval", 5); })
            .upgrade(450, null, "Restores 10 integrity every 5 s (was 5) and the aura grows 40 -> 50 units.",
                s -> { s.fieldRadius = u(50); s.set("healAmount", 10); })
            .upgrade(900, null, "Restores 15 integrity every 4 s, and towers in the aura are shielded from Palantir's Predictive Surveillance.",
                s -> { s.set("healAmount", 15).set("healInterval", 4); s.auraRange = s.fieldRadius; s.auraSurveillanceImmunity = true; })
            .upgrade(1600, null, "Restores 25 integrity every 4 s, and once per match, when integrity falls below 25%, instantly restores 20% of your maximum.",
                s -> { s.set("healAmount", 25).set("emergencyThreshold", 0.25).set("emergencyRestore", 0.20); })
            .build();
    }

    /** 3. Melee tank: short-range punches that shove enemies back down the track. */
    static TowerDef ironImraan() {
        return TowerBuilder.of(TowerType.IRON_IMRAAN, "Heavy Defensive Tank", 0)
            .unlockCost(1200)
            .description("Hero. A very short-range bruiser: every punch knocks normal enemies back down the track (bosses are immune to knockback). Later punches shake the ground with stunning shockwaves.")
            .tiers("Iron Fist", "Reinforced Armor", "Hydraulic Smash", "Iron Colossus")
            .attack(AttackKind.PROJECTILE, DamageType.BLUNT, u(20), 2.0, 40, 1)
            .base(s -> { s.projectileSpeed = u(90); s.hit.knockback = 18; })
            .upgrade(500, null, "Damage 40 -> 55 and a stronger shove (18 -> 30 px).",
                s -> { s.hit.damage = 55; s.hit.knockback = 30; })
            .upgrade(950, null, "Every 3rd punch slams the ground for 45 damage in 14 units.",
                s -> { s.set("smashEvery", 3).set("smashDamage", 45).set("smashRadius", u(14)); })
            .upgrade(1700, null, "Damage 55 -> 100, interval 2 -> 1.5 s, shockwave radius 14 -> 22 units, and the shockwave briefly stuns normal enemies.",
                s -> { s.hit.damage = 100; s.interval(1.5); s.set("smashRadius", u(22)).set("smashStun", 0.6); })
            .build();
    }

    /** 4. Demolition: dynamite, then twin charges, then a nuclear finisher. */
    static TowerDef boomSam() {
        return TowerBuilder.of(TowerType.BOOM_SAM, "Demolition Specialist", 0)
            .unlockCost(1100)
            .description("Hero. Hurls dynamite into enemy groups for heavy burst damage. Learns to throw two charges at once and finally detonates a nuclear blast every fifth attack.")
            .tiers("Dynamite Toss", "Extra Explosives", "Double Detonation", "Nuclear Boom")
            .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(45), 2.2, 50, 1)
            .base(s -> { s.splashRadius = u(10); s.projectileSpeed = u(55); })
            .upgrade(450, null, "Damage 50 -> 70 and blast radius 10 -> 13 units.",
                s -> { s.hit.damage = 70; s.splashRadius = u(13); })
            .upgrade(900, null, "Throws two charges per attack at separate targets, each 50 damage in 9 units.",
                s -> { s.hit.damage = 50; s.splashRadius = u(9); s.targets = 2; })
            .upgrade(1700, null, "Damage 50 -> 110 per charge, blast radius 9 -> 20 units, and every 5th attack adds a 250-damage detonation.",
                s -> { s.hit.damage = 110; s.splashRadius = u(20); s.set("nukeEvery", 5).set("nukeDamage", 250).set("nukeRadius", u(24)); })
            .build();
    }

    /** 5. Ice control: slows, then freezes, then shatters groups. */
    static TowerDef chillstin() {
        return TowerBuilder.of(TowerType.CHILLSTIN, "Ice and Crowd Control", 0)
            .unlockCost(1000)
            .description("Hero. Fast frost shards that slow everything they touch. Upgrades deepen the chill into outright freezes and a shattering ice explosion; bosses resist freezing and are only slowed.")
            .tiers("Frost Shards", "Deep Freeze", "Frozen Prison", "Absolute Frost")
            .attack(AttackKind.PROJECTILE, DamageType.ENERGY, u(45), 1.2, 15, 1)
            .base(s -> { s.projectileSpeed = u(70); s.hit.slowFraction = 0.25; s.hit.slowDuration = 2; })
            .upgrade(400, null, "Damage 15 -> 22 and the slow deepens 25% -> 40% and lasts 2 -> 3 s.",
                s -> { s.hit.damage = 22; s.hit.slowFraction = 0.40; s.hit.slowDuration = 3; })
            .upgrade(850, null, "Every 4th shard has a 25% chance to freeze a normal enemy for 2 s; bosses cannot be frozen and take a 15% slow instead.",
                s -> { s.set("freezeEvery", 4).set("freezeChance", 0.25).set("freezeDuration", 2).set("bossSlowPct", 0.15); })
            .upgrade(1500, null, "Damage 22 -> 40, interval 1.2 -> 0.9 s, and every 6th shard bursts for 15 units, slowing everything hit by 60% for 4 s.",
                s -> { s.hit.damage = 40; s.interval(0.9); s.set("burstEvery", 6).set("burstRadius", u(15)).set("burstSlow", 0.60).set("burstSlowDuration", 4); })
            .build();
    }

    /** 6. Kaiju: a roar that becomes a sweeping atomic beam. */
    static TowerDef kaijuKai() {
        return TowerBuilder.of(TowerType.KAIJU_KAI, "Giant Monster and Area Damage", 0)
            .unlockCost(1500)
            .description("Hero. A towering monster whose roar blasts and shoves whole groups. From Atomic Breath on it replaces the roar with a sustained energy beam that burns everything along its path, and finally detonates periodic atomic blasts.")
            .tiers("Monster Roar", "Atomic Breath", "Titan Awakening", "Cataclysmic Kaiju")
            .attack(AttackKind.PROJECTILE, DamageType.SONIC, u(50), 2.5, 45, 1)
            .base(s -> { s.splashRadius = u(15); s.projectileSpeed = u(60); s.hit.knockback = 22; })
            .upgrade(600, null, "Replaces the roar with an energy beam: 20 damage per tick for 1.5 s along its whole path, range 50 -> 60 units.",
                s -> { s.kind = AttackKind.CUSTOM; s.range = u(60); s.hit.type = DamageType.ENERGY; s.hit.knockback = 0;
                    s.set("beamDamage", 20).set("beamDuration", 1.5).set("beamTick", 0.25).set("beamWidth", u(6)); })
            .upgrade(1100, null, "Beam damage 20 -> 35 per tick and duration 1.5 -> 2 s.",
                s -> { s.set("beamDamage", 35).set("beamDuration", 2.0); })
            .upgrade(2000, null, "Every 8 s releases an atomic blast dealing 250 damage in 25 units.",
                s -> { s.set("blastInterval", 8).set("blastDamage", 250).set("blastRadius", u(25)); })
            .build();
    }

    /** 7. Flying striker: missiles that ignore ground obstacles. */
    static TowerDef abhiAce() {
        return TowerBuilder.of(TowerType.ABHI_ACE, "Flying Aerial Striker", 0)
            .unlockCost(1350)
            .description("Hero. Flies above the battlefield, so its missiles ignore every line-of-sight blocker on the ground. Upgrades turn single missiles into a barrage and finally add a periodic bombing run.")
            .tiers("Aerial Strike", "Jet Boost", "Missile Barrage", "Ace of the Skies")
            .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(60), 1.2, 25, 1)
            .base(s -> { s.projectileSpeed = u(65); s.ignoresLos = true; s.splashRadius = u(5); s.set("flying", 1); })
            .upgrade(500, null, "Damage 25 -> 35 and interval 1.2 -> 1 s; the jet flies visibly faster.",
                s -> { s.hit.damage = 35; s.interval(1.0); })
            .upgrade(1000, null, "Fires 3 missiles per attack, each 25 damage, and they may split across separate targets.",
                s -> { s.hit.damage = 25; s.targets = 3; })
            .upgrade(1800, null, "4 missiles per attack at 45 damage each, plus an aerial bombardment every 10 s dealing 200 damage in 20 units.",
                s -> { s.hit.damage = 45; s.targets = 4; s.set("bombInterval", 10).set("bombDamage", 200).set("bombRadius", u(20)); })
            .build();
    }

    /** 8. Chain lightning: arcs between crowded enemies. */
    static TowerDef zippyMatt() {
        return TowerBuilder.of(TowerType.ZIPPY_MATT, "Speed and Chain Lightning", 0)
            .unlockCost(1250)
            .description("Hero. Lightning that leaps from enemy to enemy, never striking the same target twice in one arc. Upgrades add hops and speed until the chain detonates in a lightning burst.")
            .tiers("Lightning Dash", "Speed Surge", "Electric Overload", "Hyperdrive")
            .attack(AttackKind.CHAIN, DamageType.ENERGY, u(45), 1.5, 18, 1)
            .base(s -> { s.chainHops = 2; s.chainRange = u(12); s.set("chainFalloff", 1.0); })
            .upgrade(450, null, "Damage 18 -> 25, chains to 4 enemies (was 3) and reaches 12 -> 16 units between hops.",
                s -> { s.hit.damage = 25; s.chainHops = 3; s.chainRange = u(16); })
            .upgrade(900, null, "Chains to 6 enemies and interval 1.5 -> 1.2 s, but each hop deals 90% of the previous hit.",
                s -> { s.chainHops = 5; s.interval(1.2); s.set("chainFalloff", 0.90); })
            .upgrade(1600, null, "Damage 25 -> 40, chains to 9 enemies, interval 1.2 -> 0.8 s, and every 8th attack ends in a 100-damage lightning explosion.",
                s -> { s.hit.damage = 40; s.chainHops = 8; s.interval(0.8); s.set("burstEvery", 8).set("burstDamage", 100).set("burstRadius", u(14)); })
            .build();
    }

    /** 9. Economy: pure income, no attack. */
    static TowerDef sunnyJoe() {
        return TowerBuilder.of(TowerType.SUNNY_JOE, "Passive Economy Generator", 0)
            .unlockCost(850)
            .description("Hero. Never attacks: he runs a side hustle that quietly pays cash straight into your balance on a timer, and later adds a much larger periodic payout.")
            .tiers("Side Hustle", "Smart Investments", "Business Expansion", "Financial Empire")
            .attack(AttackKind.NONE, DamageType.ENERGY, u(30), 10.0, 0, 1)
            .base(s -> { s.set("income", 40).set("incomeInterval", 10); })
            .upgrade(400, null, "Income 40 -> 65 every 10 s.",
                s -> { s.set("income", 65); })
            .upgrade(800, null, "Income 65 -> 100 every 10 s, plus a 100 bonus payout every 60 s.",
                s -> { s.set("income", 100).set("bonus", 100).set("bonusInterval", 60); })
            .upgrade(1500, null, "Income 100 -> 150 every 10 s and the bonus payout grows 100 -> 300.",
                s -> { s.set("income", 150).set("bonus", 300); })
            .build();
    }

    /** 10. Sniper: extreme range, camo detection, crits. */
    static TowerDef nikScope() {
        return TowerBuilder.of(TowerType.NIK_SCOPE, "Long-Range Precision Sniper", 0)
            .unlockCost(1300)
            .description("Hero. Picks off the strongest enemy from across the map and sees through camo from the start. Upgrades punch through more enemies per shot and finally land critical hits. Devastating against ordinary enemies; a boss's sheer bulk blunts a single precision round, so she still needs a line behind her.")
            .tiers("Precision Shot", "Enhanced Scope", "Armor Piercing", "Deadeye")
            .attack(AttackKind.INSTANT, DamageType.SHARP, u(100), 3.0, 100, 1)
            .base(s -> { s.seesCamo = true; s.hit.armorPierce = 0.3; })
            .targeting(Targeting.STRONGEST)
            .upgrade(500, null, "Damage 100 -> 150, range 100 -> 120 units and interval 3 -> 2.7 s.",
                s -> { s.hit.damage = 150; s.range = u(120); s.interval(2.7); })
            .upgrade(1000, null, "Damage 150 -> 225, the shot passes through 3 enemies, ignores most armour and deals +50% to Fortified enemies.",
                s -> { s.hit.damage = 225; s.pierce = 3; s.hit.multVsFortified = 1.5; s.hit.armorPierce = 0.6; s.interval(3.2); })
            .upgrade(1800, null, "Damage 225 -> 400, range 120 -> 150 units, pierce 5, full armour piercing and 20% of shots critically hit for 2.5x damage. Lining up the shot takes longer: interval 3.2 -> 4.2 s.",
                s -> { s.hit.damage = 400; s.range = u(150); s.pierce = 5; s.hit.armorPierce = 1.0; s.interval(4.2);
                    s.set("critChance", 0.20).set("critMult", 2.5); s.hit.multVsBoss = 0.55; })
            .build();
    }

    /** 11. Mines: plants a proximity field beside the track. */
    static TowerDef camiMine() {
        return TowerBuilder.of(TowerType.CAMI_MINE, "Mine and Trap Specialist", 0)
            .unlockCost(1100)
            .description("Hero. Plants proximity mines on the track that sit armed until an enemy walks onto them. Each mine fires once, so a field never blocks a lane; upgrades add charges, electrify them and double the blast.")
            .tiers("Proximity Mines", "Extra Charges", "Electrified Mines", "Minefield")
            .attack(AttackKind.CUSTOM, DamageType.EXPLOSIVE, u(45), 4.0, 65, 1)
            .base(s -> { s.set("maxMines", 3).set("mineRadius", u(8)).set("mineTrigger", 14).set("mineArm", 0.4); })
            .upgrade(450, null, "Carries 5 mines at once (was 3) and each deals 65 -> 85 damage.",
                s -> { s.hit.damage = 85; s.set("maxMines", 5); })
            .upgrade(900, null, "Damage 85 -> 120, blast radius 8 -> 12 units, and survivors are slowed 30% for 2 s.",
                s -> { s.hit.damage = 120; s.set("mineRadius", u(12)); s.hit.slowFraction = 0.30; s.hit.slowDuration = 2; })
            .upgrade(1600, null, "Carries 8 mines, damage 120 -> 200, and each blast has a 20% chance of a 100-damage secondary detonation.",
                s -> { s.hit.damage = 200; s.set("maxMines", 8).set("secondaryChance", 0.20).set("secondaryDamage", 100); })
            .build();
    }

    /** 12. Time control: slowing bolts plus periodic time fields. */
    static TowerDef justinTime() {
        return TowerBuilder.of(TowerType.JUSTIN_TIME, "Time Manipulation", 0)
            .unlockCost(1400)
            .description("Hero. Time bolts drag enemies to a crawl. Later he stalls whole stretches of track with a temporal field and finally stops normal enemies outright; bosses resist, taking only a slow.")
            .tiers("Time Bolt", "Time Dilation", "Temporal Field", "Time Freeze")
            .attack(AttackKind.PROJECTILE, DamageType.MAGIC, u(45), 1.5, 20, 1)
            .base(s -> { s.projectileSpeed = u(60); s.hit.slowFraction = 0.20; s.hit.slowDuration = 2; })
            .upgrade(500, null, "Damage 20 -> 30 and the slow deepens 20% -> 35% and lasts 2 -> 3 s.",
                s -> { s.hit.damage = 30; s.hit.slowFraction = 0.35; s.hit.slowDuration = 3; })
            .upgrade(950, null, "Every 12 s a temporal field slows every normal enemy on the map by 40% for 3 s; bosses are slowed 15%.",
                s -> { s.set("fieldInterval", 12).set("fieldSlow", 0.40).set("fieldDuration", 3).set("fieldBossSlow", 0.15); })
            .upgrade(1800, null, "Damage 30 -> 50, the field fires every 10 s, and every 60 s time stops: normal enemies freeze for 3 s and bosses are slowed 50%.",
                s -> { s.hit.damage = 50; s.set("fieldInterval", 10).set("freezeInterval", 60).set("freezeDuration", 3).set("freezeBossSlow", 0.50); })
            .build();
    }

    /** 13. Spears: piercing throws that later return. */
    static TowerDef spearHanbo() {
        return TowerBuilder.of(TowerType.SPEAR_HANBO, "Piercing Projectile Specialist", 0)
            .unlockCost(2000)
            .description("Hero. The second strongest hero. Throws spears that fly straight through a whole line of enemies. Upgrades sharpen them, make them fly back through the line on the return trip, and finally hurl a fan of five at once.")
            .tiers("Spear Throw", "Sharpened Spear", "Returning Spear", "Spear Master")
            .attack(AttackKind.PROJECTILE, DamageType.SHARP, u(55), 1.7, 40, 5)
            .base(s -> { s.projectileSpeed = u(80); })
            .upgrade(400, null, "Damage 40 -> 55 and pierces 6 enemies (was 5).",
                s -> { s.hit.damage = 55; s.pierce = 6; })
            .upgrade(850, null, "Damage 55 -> 70, and the spear flies back to Hanbo, hitting each enemy once more on the way.",
                s -> { s.hit.damage = 70; s.set("returns", 1); })
            .upgrade(1500, null, "Throws 3 spears in a fan at 100 damage each, pierce 10, interval 1.7 -> 1.35 s.",
                s -> { s.hit.damage = 100; s.pierce = 10; s.projectilesPerShot = 3; s.interval(1.35); s.set("spread", 0.24); })
            .build();
    }

    /** 14. Poison: lingering damage plus thorny track hazards. */
    static TowerDef thornTuhin() {
        return TowerBuilder.of(TowerType.THORN_TUHIN, "Poison and Damage Over Time", 0)
            .unlockCost(1200)
            .description("Hero. Thorn volleys that leave enemies bleeding poison long after the hit. From Overgrowth on he also grows thorny vines across the track that keep damaging whatever walks through them.")
            .tiers("Thorn Volley", "Poisoned Thorns", "Overgrowth", "Nature's Wrath")
            .attack(AttackKind.PROJECTILE, DamageType.SHARP, u(45), 1.3, 20, 2)
            .base(s -> { s.projectileSpeed = u(70); s.hit.dotDps = 5; s.hit.dotDuration = 3; })
            .upgrade(450, null, "Damage 20 -> 30 and the poison worsens 5 -> 8 per second for 3 -> 4 s.",
                s -> { s.hit.damage = 30; s.hit.dotDps = 8; s.hit.dotDuration = 4; })
            .upgrade(900, null, "Every 8 s grows thorny vines across a stretch of track dealing 20 damage per second for 4 s; two stretches can be alive at once.",
                s -> { s.set("vineInterval", 8).set("vineDps", 20).set("vineDuration", 4).set("vineRadius", u(16)).set("maxVines", 2); })
            .upgrade(1700, null, "Damage 30 -> 50, poison 8 -> 15 per second, pierce 2 -> 5, and vines deal 40 damage per second and slow by 30%.",
                s -> { s.hit.damage = 50; s.hit.dotDps = 15; s.pierce = 5; s.set("vineDps", 40).set("vineSlow", 0.30); })
            .build();
    }

    /** 15. Traps: mechanical snares that hold enemies still. */
    static TowerDef trapperChe() {
        return TowerBuilder.of(TowerType.TRAPPER_CHE, "Mechanical Crowd Control", 0)
            .unlockCost(1150)
            .description("Hero. Sets mechanical traps along the track that snap shut and hold normal enemies in place. Bosses are too heavy to be held but still take the damage; upgrades electrify the cage and add a parting shock.")
            .tiers("Capture Trap", "Reinforced Traps", "Electric Cage", "Master Trapper")
            .attack(AttackKind.CUSTOM, DamageType.KINETIC, u(45), 4.0, 25, 1)
            .base(s -> { s.set("maxTraps", 3).set("trapRadius", u(7)).set("trapTrigger", 13).set("holdDuration", 1.5); })
            .upgrade(450, null, "Damage 25 -> 40, the hold lasts 1.5 -> 2 s and a 4th trap can be set.",
                s -> { s.hit.damage = 40; s.set("maxTraps", 4).set("holdDuration", 2.0); })
            .upgrade(900, null, "Damage 40 -> 60, the hold lasts 2.5 s and held enemies take 15 extra damage per second.",
                s -> { s.hit.damage = 60; s.set("maxTraps", 4).set("holdDuration", 2.5).set("tetherDps", 15); })
            .upgrade(1600, null, "Up to 6 traps, damage 60 -> 100, the hold lasts 3 s and every trap adds a 50-damage electrical burst.",
                s -> { s.hit.damage = 100; s.set("maxTraps", 6).set("holdDuration", 3.0).set("secondaryChance", 1.0).set("secondaryDamage", 50); })
            .build();
    }

    /** 16. Suppressing fire: multi-bullet bursts. */
    static TowerDef blitzArnav() {
        return TowerBuilder.of(TowerType.BLITZ_ARNAV, "Rapid-Fire Military Specialist", 0)
            .unlockCost(1350)
            .description("Hero. Fires tight bursts that spread across whatever is in range, so a burst can tag several enemies at once. Upgrades lengthen the magazine until he is firing full auto with rocket support.")
            .tiers("Tactical Burst", "Extended Magazine", "Suppressive Fire", "Full Auto")
            .attack(AttackKind.PROJECTILE, DamageType.KINETIC, u(55), 1.5, 15, 1)
            .base(s -> { s.projectileSpeed = u(95); s.targets = 3; s.set("bullets", 3); })
            .upgrade(500, null, "5 bullets per burst (was 3) at 15 -> 18 damage each.",
                s -> { s.hit.damage = 18; s.targets = 5; s.set("bullets", 5); })
            .upgrade(950, null, "7 bullets per burst at 22 damage, and every 3rd burst slows everything it hits by 20% for 2 s.",
                s -> { s.hit.damage = 22; s.targets = 7; s.set("bullets", 7).set("suppressEvery", 3).set("suppressSlow", 0.20).set("suppressDuration", 2); })
            .upgrade(1750, null, "10 bullets per burst at 30 damage, interval 1.5 -> 1 s, and every 5th burst launches a 150-damage rocket.",
                s -> { s.hit.damage = 30; s.targets = 10; s.interval(1.0); s.set("bullets", 10).set("rocketEvery", 5).set("rocketDamage", 150).set("rocketRadius", u(16)); })
            .build();
    }

    /** 17. Flying support drone: buffs the tower network, never attacks. */
    static TowerDef tanimbus() {
        return TowerBuilder.of(TowerType.TANIMBUS, "Flying Tower Support", 0)
            .unlockCost(1300)
            .description("Hero. A command drone that hovers over the battlefield and never attacks. It locks onto the strongest tower nearby and speeds it up, later buffing every tower in range and finally rallying the whole map.")
            .tiers("Command Drone", "Enhanced Drone", "Tactical Network", "Battlefield Command")
            .attack(AttackKind.NONE, DamageType.ENERGY, u(35), 1.0, 0, 1)
            .base(s -> { s.auraRange = u(35); s.set("flying", 1).set("singleTarget", 1).set("buffRate", 0.10); })
            .upgrade(500, null, "Attack-speed bonus 10% -> 15% and support radius 35 -> 45 units.",
                s -> { s.auraRange = u(45); s.set("buffRate", 0.15); })
            .upgrade(950, null, "Buffs every tower in range instead of just the strongest: +15% attack speed and +10% range, with link lines to each one.",
                s -> { s.set("singleTarget", 0); s.auraRate = 0.15; s.auraRangeBonus = 0.10; })
            .upgrade(1700, null, "+25% attack speed and +15% range to the network, and every 45 s every tower on the map gets +30% attack speed for 8 s.",
                s -> { s.auraRate = 0.25; s.auraRangeBonus = 0.15; s.set("buffRate", 0.25)
                    .set("rallyInterval", 45).set("rallyRate", 0.30).set("rallyDuration", 8); })
            .build();
    }

    /**
     * 18. The teacher: Mr. Lindemann, the strongest hero. His shots are black holes of Java code: a gravity blast,
     * then a singularity on the track that drags enemies to a crawl and keeps crushing them. Every
     * {@code warpInterval} seconds he warps space and sends EVERY enemy on the map (bosses included) back
     * {@code warpSeconds} seconds along the track.
     */
    static TowerDef mrLindemann() {
        return TowerBuilder.of(TowerType.MR_LINDEMANN, "Space-Warping CS Teacher", 0)
            .unlockCost(2500)
            .description("Hero. The strongest hero. Fires black holes of Java code that crush everything near the impact and leave a singularity on the track that drags enemies to a crawl. Every 20 s he warps space and sends every enemy on the map, bosses included, back 5 s along the track.")
            .tiers("Hello, World", "Recursion", "Garbage Collector", "Event Horizon")
            .attack(AttackKind.PROJECTILE, DamageType.GRAVITY, u(60), 1.6, 60, 1)
            .base(s -> {
                s.splashRadius = u(12); s.projectileSpeed = u(32);
                s.set("holeRadius", u(14)).set("holeDuration", 2).set("holeDps", 30).set("holeSlow", 0.5).set("maxHoles", 2)
                    .set("warpInterval", 20).set("warpSeconds", 5);
            })
            .upgrade(1200, null, "Damage 60 -> 90; singularities last 2 -> 3 s and crush 30 -> 50 per second; sees Camo.",
                s -> { s.hit.damage = 90; s.seesCamo = true; s.set("holeDuration", 3).set("holeDps", 50); })
            .upgrade(2600, null, "Singularities grow 14 -> 18 units (up to 3 at once) and garbage-collect: a non-boss enemy inside one below 15% HP is deleted outright.",
                s -> { s.set("holeRadius", u(18)).set("maxHoles", 3).set("gcThreshold", 0.15); })
            .upgrade(5000, null, "Damage 90 -> 200, interval 1.6 -> 1.4 s, singularities crush 70 per second, and space warps every 15 s instead of 20.",
                s -> { s.hit.damage = 200; s.interval(1.4); s.set("holeDps", 70).set("warpInterval", 15); })
            .build();
    }
}
