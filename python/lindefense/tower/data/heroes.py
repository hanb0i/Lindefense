"""Hero Store heroes (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.splash_radius = u(12)
    s.projectile_speed = u(40)


def _f2(s):
    s.hit.damage = 45
    s.splash_radius = u(15)
    s.hit.knockback = 10


def _f3(s):
    s.set("clusterBombs", 3).set("clusterDamage", 25).set("clusterSplash", u(7))


def _f4(s):
    s.hit.damage = 100
    s.splash_radius = u(22)
    s.set("orbitalEvery", 5).set("orbitalMult", 2.0)


def _f5(s):
    s.field_radius = u(40)
    s.set("healAmount", 6).set("healInterval", 5)


def _f6(s):
    s.field_radius = u(50)
    s.set("healAmount", 10)
    s.aura_range = s.field_radius
    s.aura_rate = 0.05


def _f7(s):
    s.set("healAmount", 15).set("healInterval", 4)
    s.aura_range = s.field_radius
    s.aura_surveillance_immunity = True


def _f8(s):
    s.set("healAmount", 25).set("emergencyThreshold", 0.25).set("emergencyRestore", 0.20)


def _f9(s):
    s.projectile_speed = u(90)
    s.hit.knockback = 18


def _f10(s):
    s.hit.damage = 55
    s.hit.knockback = 30
    s.hit.slow_fraction = 0.20
    s.hit.slow_duration = 1


def _f11(s):
    s.set("smashEvery", 3).set("smashDamage", 45).set("smashRadius", u(14))


def _f12(s):
    s.hit.damage = 100
    s.set_interval(1.5)
    s.set("smashRadius", u(22)).set("smashStun", 0.6)


def _f13(s):
    s.splash_radius = u(10)
    s.projectile_speed = u(55)


def _f14(s):
    s.hit.damage = 70
    s.splash_radius = u(13)
    s.hit.dot_dps = 2
    s.hit.dot_duration = 2


def _f15(s):
    s.hit.damage = 50
    s.splash_radius = u(9)
    s.targets = 2


def _f16(s):
    s.hit.damage = 110
    s.splash_radius = u(20)
    s.set("nukeEvery", 5).set("nukeDamage", 250).set("nukeRadius", u(24))


def _f17(s):
    s.projectile_speed = u(70)
    s.hit.slow_fraction = 0.25
    s.hit.slow_duration = 2


def _f18(s):
    s.hit.damage = 22
    s.hit.slow_fraction = 0.40
    s.hit.slow_duration = 3
    s.pierce = 2


def _f19(s):
    s.set("freezeEvery", 4).set("freezeChance", 0.25).set("freezeDuration", 2).set("bossSlowPct", 0.15)


def _f20(s):
    s.hit.damage = 40
    s.set_interval(0.9)
    s.set("burstEvery", 6).set("burstRadius", u(15)).set("burstSlow", 0.60).set("burstSlowDuration", 4)


def _f21(s):
    s.splash_radius = u(15)
    s.projectile_speed = u(60)
    s.hit.knockback = 22


def _f22(s):
    s.kind = AttackKind.CUSTOM
    s.range = u(60)
    s.hit.type = DamageType.ENERGY
    s.hit.knockback = 0
    s.set("beamDamage", 20).set("beamDuration", 1.5).set("beamTick", 0.25).set("beamWidth", u(6))


def _f23(s):
    s.set("beamDamage", 35).set("beamDuration", 2.0)


def _f24(s):
    s.set("blastInterval", 8).set("blastDamage", 250).set("blastRadius", u(25))


def _f25(s):
    s.projectile_speed = u(65)
    s.ignores_los = True
    s.splash_radius = u(5)
    s.set("flying", 1)


def _f26(s):
    s.hit.damage = 35
    s.set_interval(1.0)
    s.hit.mark_flat = 1
    s.hit.mark_duration = 2


def _f27(s):
    s.hit.damage = 25
    s.targets = 3


def _f28(s):
    s.hit.damage = 45
    s.targets = 4
    s.set("bombInterval", 10).set("bombDamage", 200).set("bombRadius", u(20))


def _f29(s):
    s.chain_hops = 2
    s.chain_range = u(12)
    s.set("chainFalloff", 1.0)


def _f30(s):
    s.hit.damage = 25
    s.chain_hops = 3
    s.chain_range = u(16)
    s.hit.slow_fraction = 0.15
    s.hit.slow_duration = 1


def _f31(s):
    s.chain_hops = 5
    s.set_interval(1.2)
    s.set("chainFalloff", 0.90)


def _f32(s):
    s.hit.damage = 40
    s.chain_hops = 8
    s.set_interval(0.8)
    s.set("burstEvery", 8).set("burstDamage", 100).set("burstRadius", u(14))


def _f33(s):
    s.set("income", 46).set("incomeInterval", 10)


def _f34(s):
    s.set("income", 65)
    s.aura_range = u(30)
    s.aura_rate = 0.05


def _f35(s):
    s.set("income", 100).set("bonus", 100).set("bonusInterval", 60)


def _f36(s):
    s.set("income", 150).set("bonus", 300)


def _f37(s):
    s.sees_camo = True
    s.hit.armor_pierce = 0.3


def _f38(s):
    s.hit.damage = 150
    s.range = u(120)
    s.set_interval(2.7)
    s.pierce = 2


def _f39(s):
    s.hit.damage = 225
    s.pierce = 3
    s.hit.mult_vs_fortified = 1.5
    s.hit.armor_pierce = 0.6
    s.set_interval(3.2)


def _f40(s):
    s.hit.damage = 400
    s.range = u(150)
    s.pierce = 5
    s.hit.armor_pierce = 1.0
    s.set_interval(4.2)
    s.set("critChance", 0.20).set("critMult", 2.5)
    s.hit.mult_vs_boss = 0.55


def _f41(s):
    s.set("maxMines", 3).set("mineRadius", u(8)).set("mineTrigger", 14).set("mineArm", 0.4)


def _f42(s):
    s.hit.damage = 85
    s.set("maxMines", 5)
    s.hit.mark_flat = 1
    s.hit.mark_duration = 2


def _f43(s):
    s.hit.damage = 120
    s.set("mineRadius", u(12))
    s.hit.slow_fraction = 0.30
    s.hit.slow_duration = 2


def _f44(s):
    s.hit.damage = 200
    s.set("maxMines", 8).set("secondaryChance", 0.20).set("secondaryDamage", 100)


def _f45(s):
    s.projectile_speed = u(60)
    s.hit.slow_fraction = 0.20
    s.hit.slow_duration = 2


def _f46(s):
    s.hit.damage = 30
    s.hit.slow_fraction = 0.35
    s.hit.slow_duration = 3
    s.pierce = 2


def _f47(s):
    s.set("fieldInterval", 12).set("fieldSlow", 0.40).set("fieldDuration", 3).set("fieldBossSlow", 0.15)


def _f48(s):
    s.hit.damage = 50
    s.set("fieldInterval", 10).set("freezeInterval", 60).set("freezeDuration", 3).set("freezeBossSlow", 0.50)


def _f49(s):
    s.projectile_speed = u(80)


def _f50(s):
    s.hit.damage = 55
    s.pierce = 6
    s.hit.mark_flat = 1
    s.hit.mark_duration = 2


def _f51(s):
    s.hit.damage = 70
    s.set("returns", 1)


def _f52(s):
    s.hit.damage = 100
    s.pierce = 10
    s.projectiles_per_shot = 3
    s.set_interval(1.35)
    s.set("spread", 0.24)


def _f53(s):
    s.projectile_speed = u(70)
    s.hit.dot_dps = 5
    s.hit.dot_duration = 3


def _f54(s):
    s.hit.damage = 30
    s.hit.dot_dps = 8
    s.hit.dot_duration = 4
    s.hit.slow_fraction = 0.10
    s.hit.slow_duration = 2


def _f55(s):
    s.set("vineInterval", 8).set("vineDps", 20).set("vineDuration", 4).set("vineRadius", u(16)).set("maxVines", 2)


def _f56(s):
    s.hit.damage = 50
    s.hit.dot_dps = 15
    s.pierce = 5
    s.set("vineDps", 40).set("vineSlow", 0.30)


def _f57(s):
    s.set("maxTraps", 3).set("trapRadius", u(7)).set("trapTrigger", 13).set("holdDuration", 1.5)


def _f58(s):
    s.hit.damage = 40
    s.set("maxTraps", 4).set("holdDuration", 2.0)
    s.hit.mark_flat = 1
    s.hit.mark_duration = 2


def _f59(s):
    s.hit.damage = 60
    s.set("maxTraps", 4).set("holdDuration", 2.5).set("tetherDps", 15)


def _f60(s):
    s.hit.damage = 100
    s.set("maxTraps", 6).set("holdDuration", 3.0).set("secondaryChance", 1.0).set("secondaryDamage", 50)


def _f61(s):
    s.projectile_speed = u(95)
    s.targets = 3
    s.set("bullets", 3)


def _f62(s):
    s.hit.damage = 18
    s.targets = 5
    s.set("bullets", 5)
    s.hit.mark_flat = 1
    s.hit.mark_duration = 1.5


def _f63(s):
    s.hit.damage = 22
    s.targets = 7
    s.set("bullets", 7).set("suppressEvery", 3).set("suppressSlow", 0.20).set("suppressDuration", 2)


def _f64(s):
    s.hit.damage = 30
    s.targets = 10
    s.set_interval(1.0)
    s.set("bullets", 10).set("rocketEvery", 5).set("rocketDamage", 150).set("rocketRadius", u(16))


def _f65(s):
    s.aura_range = u(35)
    s.set("flying", 1).set("singleTarget", 1).set("buffRate", 0.12)


def _f66(s):
    s.aura_range = u(45)
    s.set("buffRate", 0.15)
    s.aura_range_bonus = 0.05


def _f67(s):
    s.set("singleTarget", 0)
    s.aura_rate = 0.15
    s.aura_range_bonus = 0.10


def _f68(s):
    s.aura_rate = 0.25
    s.aura_range_bonus = 0.15
    s.set("buffRate", 0.25).set("rallyInterval", 45).set("rallyRate", 0.30).set("rallyDuration", 8)


def _f69(s):
    s.splash_radius = u(12)
    s.projectile_speed = u(32)
    s.set("holeRadius", u(14)).set("holeDuration", 2).set("holeDps", 30).set("holeSlow", 0.5).set("maxHoles", 2).set("warpInterval", 20).set("warpSeconds", 5)


def _f70(s):
    s.hit.damage = 90
    s.sees_camo = True
    s.set("holeDuration", 3).set("holeDps", 50)


def _f71(s):
    s.set("holeRadius", u(18)).set("maxHoles", 3).set("gcThreshold", 0.15)


def _f72(s):
    s.hit.damage = 200
    s.set_interval(1.4)
    s.set("holeDps", 70).set("warpInterval", 15)


def lobber_luis():
    return (TowerBuilder.of(TowerType.LOBBER_LUIS, "Explosive Artillery", 250)
        .unlock_cost(1250)
        .description("Hero. Lobs an arcing explosive that deals full damage to everything in the blast. Slow, long-ranged and built for dense groups; later splits into cluster bombs and finally calls orbital strikes.")
        .tiers("Lob Shot", "Heavy Payload", "Cluster Bombs", "Orbital Artillery")
        .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(55), 2.5, 34, 1)
        .base(_f1)
        .upgrade(400, "Heavy Payload", "Damage 34 -> 45 and blast radius 12 -> 15 units; a heavier shell that also shoves survivors back.",
        _f2)
        .upgrade(850, None, "The shell splits on impact into 3 bomblets, each dealing 25 damage in 7 units.",
        _f3)
        .upgrade(1500, None, "Damage 45 -> 100, blast radius 15 -> 22 units, and every 5th shot lands as a double-damage orbital strike with a shockwave.",
        _f4)
        .build())


def sage_aarav():
    return (TowerBuilder.of(TowerType.SAGE_AARAV, "Healing and Defensive Support", 300)
        .unlock_cost(1400)
        .description("Hero. Never attacks. A healing aura restores the integrity leaks take away, up to your starting maximum, and later shields nearby towers and performs one emergency restoration per match.")
        .tiers("Healing Aura", "Restorative Energy", "Protective Blessing", "Divine Restoration")
        .attack(AttackKind.NONE, DamageType.ENERGY, u(40), 5.0, 0, 1)
        .base(_f5)
        .upgrade(450, "Restorative Energy", "Restores 10 integrity every 5 s (was 6) and the aura grows 40 -> 50 units; it also lightly speeds up towers it reaches (+5% attack speed).",
        _f6)
        .upgrade(900, None, "Restores 15 integrity every 4 s, and towers in the aura are shielded from Palantir's Predictive Surveillance.",
        _f7)
        .upgrade(1600, None, "Restores 25 integrity every 4 s, and once per match, when integrity falls below 25%, instantly restores 20% of your maximum.",
        _f8)
        .build())


def iron_imraan():
    return (TowerBuilder.of(TowerType.IRON_IMRAAN, "Heavy Defensive Tank", 350)
        .unlock_cost(1650)
        .description("Hero. A very short-range bruiser: every punch knocks normal enemies back down the track (bosses are immune to knockback). Later punches shake the ground with stunning shockwaves.")
        .tiers("Iron Fist", "Reinforced Armor", "Hydraulic Smash", "Iron Colossus")
        .attack(AttackKind.PROJECTILE, DamageType.BLUNT, u(20), 2.0, 46, 1)
        .base(_f9)
        .upgrade(500, "Reinforced Armor", "Damage 46 -> 55, a stronger shove (18 -> 30 px), and the heavier plating staggers what it hits (20% slow for 1 s).",
        _f10)
        .upgrade(950, None, "Every 3rd punch slams the ground for 45 damage in 14 units.",
        _f11)
        .upgrade(1700, None, "Damage 55 -> 100, interval 2 -> 1.5 s, shockwave radius 14 -> 22 units, and the shockwave briefly stuns normal enemies.",
        _f12)
        .build())


def boom_sam():
    return (TowerBuilder.of(TowerType.BOOM_SAM, "Demolition Specialist", 300)
        .unlock_cost(1500)
        .description("Hero. Hurls dynamite into enemy groups for heavy burst damage. Learns to throw two charges at once and finally detonates a nuclear blast every fifth attack.")
        .tiers("Dynamite Toss", "Extra Explosives", "Double Detonation", "Nuclear Boom")
        .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(45), 2.2, 57, 1)
        .base(_f13)
        .upgrade(450, "Extra Explosives", "Damage 57 -> 70, blast radius 10 -> 13 units, and the extra explosive leaves lingering fire (2 damage/s for 2 s).",
        _f14)
        .upgrade(900, None, "Throws two charges per attack at separate targets, each 50 damage in 9 units.",
        _f15)
        .upgrade(1700, None, "Damage 50 -> 110 per charge, blast radius 9 -> 20 units, and every 5th attack adds a 250-damage detonation.",
        _f16)
        .build())


def chillstin():
    return (TowerBuilder.of(TowerType.CHILLSTIN, "Ice and Crowd Control", 300)
        .unlock_cost(1400)
        .description("Hero. Fast frost shards that slow everything they touch. Upgrades deepen the chill into outright freezes and a shattering ice explosion; bosses resist freezing and are only slowed.")
        .tiers("Frost Shards", "Deep Freeze", "Frozen Prison", "Absolute Frost")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, u(45), 1.2, 17, 1)
        .base(_f17)
        .upgrade(400, "Deep Freeze", "Damage 17 -> 22, the slow deepens 25% -> 40% and lasts 2 -> 3 s, and shards now pierce a second enemy.",
        _f18)
        .upgrade(850, None, "Every 4th shard has a 25% chance to freeze a normal enemy for 2 s; bosses cannot be frozen and take a 15% slow instead.",
        _f19)
        .upgrade(1500, None, "Damage 22 -> 40, interval 1.2 -> 0.9 s, and every 6th shard bursts for 15 units, slowing everything hit by 60% for 4 s.",
        _f20)
        .build())


def kaiju_kai():
    return (TowerBuilder.of(TowerType.KAIJU_KAI, "Giant Monster and Area Damage", 400)
        .unlock_cost(2000)
        .description("Hero. A towering monster whose roar blasts and shoves whole groups. From Atomic Breath on it replaces the roar with a sustained energy beam that burns everything along its path, and finally detonates periodic atomic blasts.")
        .tiers("Monster Roar", "Atomic Breath", "Titan Awakening", "Cataclysmic Kaiju")
        .attack(AttackKind.PROJECTILE, DamageType.SONIC, u(50), 2.5, 52, 1)
        .base(_f21)
        .upgrade(600, None, "Replaces the roar with an energy beam: 20 damage per tick for 1.5 s along its whole path, range 50 -> 60 units.",
        _f22)
        .upgrade(1100, None, "Beam damage 20 -> 35 per tick and duration 1.5 -> 2 s.",
        _f23)
        .upgrade(2000, None, "Every 8 s releases an atomic blast dealing 250 damage in 25 units.",
        _f24)
        .build())


def abhi_ace():
    return (TowerBuilder.of(TowerType.ABHI_ACE, "Flying Aerial Striker", 350)
        .unlock_cost(1800)
        .description("Hero. Flies above the battlefield, so its missiles ignore every line-of-sight blocker on the ground. Upgrades turn single missiles into a barrage and finally add a periodic bombing run.")
        .tiers("Aerial Strike", "Jet Boost", "Missile Barrage", "Ace of the Skies")
        .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, u(60), 1.2, 29, 1)
        .base(_f25)
        .upgrade(500, "Jet Boost", "Damage 29 -> 35, interval 1.2 -> 1 s, and the afterburner heat marks the target for +1 damage for 2 s.",
        _f26)
        .upgrade(1000, None, "Fires 3 missiles per attack, each 25 damage, and they may split across separate targets.",
        _f27)
        .upgrade(1800, None, "4 missiles per attack at 45 damage each, plus an aerial bombardment every 10 s dealing 200 damage in 20 units.",
        _f28)
        .build())


def zippy_matt():
    return (TowerBuilder.of(TowerType.ZIPPY_MATT, "Speed and Chain Lightning", 350)
        .unlock_cost(1700)
        .description("Hero. Lightning that leaps from enemy to enemy, never striking the same target twice in one arc. Upgrades add hops and speed until the chain detonates in a lightning burst.")
        .tiers("Lightning Dash", "Speed Surge", "Electric Overload", "Hyperdrive")
        .attack(AttackKind.CHAIN, DamageType.ENERGY, u(45), 1.5, 21, 1)
        .base(_f29)
        .upgrade(450, "Speed Surge", "Damage 21 -> 25, chains to 4 enemies (was 3), reaches 12 -> 16 units between hops, and every hit saps 15% speed for 1 s.",
        _f30)
        .upgrade(900, None, "Chains to 6 enemies and interval 1.5 -> 1.2 s, but each hop deals 90% of the previous hit.",
        _f31)
        .upgrade(1600, None, "Damage 25 -> 40, chains to 9 enemies, interval 1.2 -> 0.8 s, and every 8th attack ends in a 100-damage lightning explosion.",
        _f32)
        .build())


def sunny_joe():
    return (TowerBuilder.of(TowerType.SUNNY_JOE, "Passive Economy Generator", 200)
        .unlock_cost(1150)
        .description("Hero. Never attacks: he runs a side hustle that quietly pays cash straight into your balance on a timer, and later adds a much larger periodic payout.")
        .tiers("Side Hustle", "Smart Investments", "Business Expansion", "Financial Empire")
        .attack(AttackKind.NONE, DamageType.ENERGY, u(30), 10.0, 0, 1)
        .base(_f33)
        .upgrade(400, "Smart Investments", "Income 46 -> 65 every 10 s, and the investments fund a small productivity bonus to nearby towers (+5% attack speed).",
        _f34)
        .upgrade(800, None, "Income 65 -> 100 every 10 s, plus a 100 bonus payout every 60 s.",
        _f35)
        .upgrade(1500, None, "Income 100 -> 150 every 10 s and the bonus payout grows 100 -> 300.",
        _f36)
        .build())


def nik_scope():
    return (TowerBuilder.of(TowerType.NIK_SCOPE, "Long-Range Precision Sniper", 350)
        .unlock_cost(1750)
        .description("Hero. Picks off the strongest enemy from across the map and sees through camo from the start. Upgrades punch through more enemies per shot and finally land critical hits. Devastating against ordinary enemies; a boss's sheer bulk blunts a single precision round, so she still needs a line behind her.")
        .tiers("Precision Shot", "Enhanced Scope", "Armor Piercing", "Deadeye")
        .attack(AttackKind.INSTANT, DamageType.SHARP, u(100), 3.0, 115, 1)
        .base(_f37)
        .targeting(Targeting.STRONGEST)
        .upgrade(500, "Enhanced Scope", "Damage 115 -> 150, range 100 -> 120 units, interval 3 -> 2.7 s, and the sharper scope punches through a second enemy.",
        _f38)
        .upgrade(1000, None, "Damage 150 -> 225, the shot passes through 3 enemies, ignores most armour and deals +50% to Fortified enemies.",
        _f39)
        .upgrade(1800, None, "Damage 225 -> 400, range 120 -> 150 units, pierce 5, full armour piercing and 20% of shots critically hit for 2.5x damage. Lining up the shot takes longer: interval 3.2 -> 4.2 s.",
        _f40)
        .build())


def cami_mine():
    return (TowerBuilder.of(TowerType.CAMI_MINE, "Mine and Trap Specialist", 300)
        .unlock_cost(1500)
        .description("Hero. Plants proximity mines on the track that sit armed until an enemy walks onto them. Each mine fires once, so a field never blocks a lane; upgrades add charges, electrify them and double the blast.")
        .tiers("Proximity Mines", "Extra Charges", "Electrified Mines", "Minefield")
        .attack(AttackKind.CUSTOM, DamageType.EXPLOSIVE, u(45), 4.0, 75, 1)
        .base(_f41)
        .upgrade(450, "Extra Charges", "Carries 5 mines at once (was 3), each deals 75 -> 85 damage, and the trip also marks the target for +1 damage for 2 s.",
        _f42)
        .upgrade(900, None, "Damage 85 -> 120, blast radius 8 -> 12 units, and survivors are slowed 30% for 2 s.",
        _f43)
        .upgrade(1600, None, "Carries 8 mines, damage 120 -> 200, and each blast has a 20% chance of a 100-damage secondary detonation.",
        _f44)
        .build())


def justin_time():
    return (TowerBuilder.of(TowerType.JUSTIN_TIME, "Time Manipulation", 400)
        .unlock_cost(1900)
        .description("Hero. Time bolts drag enemies to a crawl. Later he stalls whole stretches of track with a temporal field and finally stops normal enemies outright; bosses resist, taking only a slow.")
        .tiers("Time Bolt", "Time Dilation", "Temporal Field", "Time Freeze")
        .attack(AttackKind.PROJECTILE, DamageType.MAGIC, u(45), 1.5, 23, 1)
        .base(_f45)
        .upgrade(500, "Time Dilation", "Damage 23 -> 30, the slow deepens 20% -> 35% and lasts 2 -> 3 s, and bolts now pierce a second enemy.",
        _f46)
        .upgrade(950, None, "Every 12 s a temporal field slows every normal enemy on the map by 40% for 3 s; bosses are slowed 15%.",
        _f47)
        .upgrade(1800, None, "Damage 30 -> 50, the field fires every 10 s, and every 60 s time stops: normal enemies freeze for 3 s and bosses are slowed 50%.",
        _f48)
        .build())


def spear_hanbo():
    return (TowerBuilder.of(TowerType.SPEAR_HANBO, "Piercing Projectile Specialist", 500)
        .unlock_cost(2700)
        .description("Hero. The second strongest hero. Throws spears that fly straight through a whole line of enemies. Upgrades sharpen them, make them fly back through the line on the return trip, and finally hurl a fan of five at once.")
        .tiers("Spear Throw", "Sharpened Spear", "Returning Spear", "Spear Master")
        .attack(AttackKind.PROJECTILE, DamageType.SHARP, u(55), 1.7, 46, 5)
        .base(_f49)
        .upgrade(400, "Sharpened Spear", "Damage 46 -> 55, pierces 6 enemies (was 5), and the sharpened edge marks whatever it hits for +1 damage for 2 s.",
        _f50)
        .upgrade(850, None, "Damage 55 -> 70, and the spear flies back to Hanbo, hitting each enemy once more on the way.",
        _f51)
        .upgrade(1500, None, "Throws 3 spears in a fan at 100 damage each, pierce 10, interval 1.7 -> 1.35 s.",
        _f52)
        .build())


def thorn_tuhin():
    return (TowerBuilder.of(TowerType.THORN_TUHIN, "Poison and Damage Over Time", 350)
        .unlock_cost(1650)
        .description("Hero. Thorn volleys that leave enemies bleeding poison long after the hit. From Overgrowth on he also grows thorny vines across the track that keep damaging whatever walks through them.")
        .tiers("Thorn Volley", "Poisoned Thorns", "Overgrowth", "Nature's Wrath")
        .attack(AttackKind.PROJECTILE, DamageType.SHARP, u(45), 1.3, 23, 2)
        .base(_f53)
        .upgrade(450, "Poisoned Thorns", "Damage 23 -> 30, the poison worsens 5 -> 8 per second for 3 -> 4 s, and the toxin now also slows (10% for 2 s).",
        _f54)
        .upgrade(900, None, "Every 8 s grows thorny vines across a stretch of track dealing 20 damage per second for 4 s; two stretches can be alive at once.",
        _f55)
        .upgrade(1700, None, "Damage 30 -> 50, poison 8 -> 15 per second, pierce 2 -> 5, and vines deal 40 damage per second and slow by 30%.",
        _f56)
        .build())


def trapper_che():
    return (TowerBuilder.of(TowerType.TRAPPER_CHE, "Mechanical Crowd Control", 300)
        .unlock_cost(1550)
        .description("Hero. Sets mechanical traps along the track that snap shut and hold normal enemies in place. Bosses are too heavy to be held but still take the damage; upgrades electrify the cage and add a parting shock.")
        .tiers("Capture Trap", "Reinforced Traps", "Electric Cage", "Master Trapper")
        .attack(AttackKind.CUSTOM, DamageType.KINETIC, u(45), 4.0, 29, 1)
        .base(_f57)
        .upgrade(450, "Reinforced Traps", "Damage 29 -> 40, the hold lasts 1.5 -> 2 s, a 4th trap can be set, and trapped enemies are marked for +1 damage for 2 s.",
        _f58)
        .upgrade(900, None, "Damage 40 -> 60, the hold lasts 2.5 s and held enemies take 15 extra damage per second.",
        _f59)
        .upgrade(1600, None, "Up to 6 traps, damage 60 -> 100, the hold lasts 3 s and every trap adds a 50-damage electrical burst.",
        _f60)
        .build())


def blitz_arnav():
    return (TowerBuilder.of(TowerType.BLITZ_ARNAV, "Rapid-Fire Military Specialist", 350)
        .unlock_cost(1800)
        .description("Hero. Fires tight bursts that spread across whatever is in range, so a burst can tag several enemies at once. Upgrades lengthen the magazine until he is firing full auto with rocket support.")
        .tiers("Tactical Burst", "Extended Magazine", "Suppressive Fire", "Full Auto")
        .attack(AttackKind.PROJECTILE, DamageType.KINETIC, u(55), 1.5, 17, 1)
        .base(_f61)
        .upgrade(500, "Extended Magazine", "5 bullets per burst (was 3) at 17 -> 18 damage each, and tracer rounds mark what they hit for +1 damage for 1.5 s.",
        _f62)
        .upgrade(950, None, "7 bullets per burst at 22 damage, and every 3rd burst slows everything it hits by 20% for 2 s.",
        _f63)
        .upgrade(1750, None, "10 bullets per burst at 30 damage, interval 1.5 -> 1 s, and every 5th burst launches a 150-damage rocket.",
        _f64)
        .build())


def tanimbus():
    return (TowerBuilder.of(TowerType.TANIMBUS, "Flying Tower Support", 350)
        .unlock_cost(1750)
        .description("Hero. A command drone that hovers over the battlefield and never attacks. It locks onto the strongest tower nearby and speeds it up, later buffing every tower in range and finally rallying the whole map.")
        .tiers("Command Drone", "Enhanced Drone", "Tactical Network", "Battlefield Command")
        .attack(AttackKind.NONE, DamageType.ENERGY, u(35), 1.0, 0, 1)
        .base(_f65)
        .upgrade(500, "Enhanced Drone", "Attack-speed bonus 12% -> 15% and support radius 35 -> 45 units; towers near the drone also get a touch more range (+5%).",
        _f66)
        .upgrade(950, None, "Buffs every tower in range instead of just the strongest: +15% attack speed and +10% range, with link lines to each one.",
        _f67)
        .upgrade(1700, None, "+25% attack speed and +15% range to the network, and every 45 s every tower on the map gets +30% attack speed for 8 s.",
        _f68)
        .build())


def mr_lindemann():
    return (TowerBuilder.of(TowerType.MR_LINDEMANN, "Space-Warping CS Teacher", 700)
        .unlock_cost(3400)
        .description("Hero. The strongest hero. Fires black holes of Java code that crush everything near the impact and leave a singularity on the track that drags enemies to a crawl. Every 20 s he warps space and sends every enemy on the map, bosses included, back 5 s along the track.")
        .tiers("Hello, World", "Recursion", "Garbage Collector", "Event Horizon")
        .attack(AttackKind.PROJECTILE, DamageType.GRAVITY, u(60), 1.6, 70, 1)
        .base(_f69)
        .injection_immune("The CS teacher: he wrote the lesson on prompt injection, so it never fools him.")
        .upgrade(1200, None, "Damage 70 -> 90; singularities last 2 -> 3 s and crush 30 -> 50 per second; sees Camo.",
        _f70)
        .upgrade(2600, None, "Singularities grow 14 -> 18 units (up to 3 at once) and garbage-collect: a non-boss enemy inside one below 15% HP is deleted outright.",
        _f71)
        .upgrade(5000, None, "Damage 90 -> 200, interval 1.6 -> 1.4 s, singularities crush 70 per second, and space warps every 15 s instead of 20.",
        _f72)
        .build())


def all_towers():
    return [lobber_luis(), sage_aarav(), iron_imraan(), boom_sam(), chillstin(), kaiju_kai(), abhi_ace(), zippy_matt(), sunny_joe(), nik_scope(), cami_mine(), justin_time(), spear_hanbo(), thorn_tuhin(), trapper_che(), blitz_arnav(), tanimbus(), mr_lindemann()]
