"""Experimental Titans (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.projectile_speed = 500


def _f2(s):
    s.pierce = 8
    s.projectiles_per_shot = 3


def _f3(s):
    s.set("droneCount", 2).set("droneInterval", 1.2).set("droneSegment", 180).set("droneSpeed", 70)


def _f4(s):
    s.hit.damage = 4
    s.hit.mult_vs_high_hp = 3


def _f5(s):
    s.set("chargeSegment", 150).set("chargeCount", 1).set("chargeSpeed", 260)


def _f6(s):
    s.set("chargeCount", 3)


def _f7(s):
    s.sees_camo = True
    s.pierce = 12


def _f8(s):
    s.set("shockInterval", 4).set("shockDamage", 8).set("shockKnockback", 40).set("shockBossMult", 2)


def _f9(s):
    s.hit.knockback_vs_fast = 15


def _f10(s):
    s.set("gustInterval", 3).set("gustFast", 60).set("gustOther", 25)


def _f11(s):
    s.set("tornadoInterval", 8).set("tornadoDuration", 5).set("tornadoTick", 0.3).set("tornadoDamage", 1).set("tornadoRadius", 45)


def _f12(s):
    s.set("vortexRadius", 70).set("vortexTick", 0.3).set("vortexDamage", 2).set("vortexSlow", 0.3).set("vortexBossMult", 2)


def _f13(s):
    s.splash_radius = 60
    s.projectile_speed = 350


def _f14(s):
    s.set("shrapnelCount", 8).set("shrapnelDamage", 1).set("shrapnelPierce", 2).set("shrapnelRange", 110).set("shrapnelWidth", 5)


def _f15(s):
    s.hit.armor_break = 1
    s.hit.armor_break_duration = 5
    s.hit.mark_bonus = 0.5
    s.hit.mark_duration = 5


def _f16(s):
    s.hit.damage = 10
    s.splash_radius = 90
    s.set_interval(1.1)
    s.hit.mult_vs_boss = 3


def _f17(s):
    s.hit.slow_fraction = 0.10
    s.hit.slow_duration = 1.5


def _f18(s):
    s.set("nodes", 2).set("lineDamage", 2).set("lineCooldown", 0.3).set("nodeSpread", 30)


def _f19(s):
    s.set("nodes", 4).set("gridSlow", 0.30)


def _f20(s):
    s.set("nodes", 6).set("lineDamage", 5).set("lineFortifiedMult", 2)


def _f21(s):
    s.hit.mult_vs_fortified = 0.5
    s.set("streakStep", 1).set("streakMax", 3)
    s.stack_cap = 3
    s.stack_step = 1


def _f22(s):
    s.set("memoryPer", 100).set("memoryCap", 5)


def _f23(s):
    s.set("streakMax", 8).set("pierceBonusPerStack", 1)
    s.stack_cap = 8


def _f24(s):
    s.set("memoryCap", 12).set("burstEvery", 10).set("burstDamage", 15).set("burstSplash", 70)


def _f25(s):
    s.bounces = 3
    s.bounce_range = 100
    s.set("bounceSpeedGain", 0.10)


def _f26(s):
    s.bounces = 6
    s.set("cloneCount", 1).set("cloneOrbit", 36)


def _f27(s):
    s.clones = 2


def _f28(s):
    s.set("cloneCount", 3).set("barrageInterval", 6).set("barrageCount", 20)


def qwen():
    return (TowerBuilder.of(TowerType.QWEN, "Modular Drone Factory", 750)
        .description("Multi-threaded energy discs; later patrolling drones and a screen-wide burst that strips Fortified from airships. No camo detection.")
        .tiers("Qwen3.8 Flash", "Qwen3.6 Max", "Qwen3.7 Plus", "Qwen3.8 Max")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 190, 1.0, 2, 4)
        .base(_f1)
        .upgrade(1100, None, "Pierce 8, 3 discs per attack.",
        _f2)
        .upgrade(1200, "Drone Formation", "2 drones patrol other track segments anywhere on the map (interval 1.2, same disc stats).",
        _f3)
        .upgrade(2000, "Sovereign Processing", "Damage 4; x3 vs enemies with max HP of 5 or more and vs Fortified MOAB-class.",
        _f4)
        .ability(AbilityBuilder.of("Cosmic Sovereign Burst", 60, "Screen-wide wave deals 400 damage to every enemy, bosses included, and removes Fortified from all airships except Palantir (Palantir loses its current phase shield for 10 s).")
        .p("damage", 400).p("palantirShieldOff", 10))
        .build())


def llama():
    return (TowerBuilder.of(TowerType.LLAMA, "Primal Swarm", 700)
        .description("Every 2 s llamas charge along a track segment in range; later spectral packs that see camo and a mythical stampede shockwave.")
        .tiers("Llama 4 Scout", "Llama 4 Maverick", "Muse Glimmer", "Muse Wonder")
        .attack(AttackKind.CUSTOM, DamageType.KINETIC, 170, 2.0, 2, 6)
        .base(_f5)
        .upgrade(1000, "Pack Mentality", "3 charging creatures per cycle.",
        _f6)
        .upgrade(1100, "Illusion Pack", "Spectral creatures gain camo detection, pierce 12.",
        _f7)
        .upgrade(1900, "Mythical Stampede", "Every 4 s, a kinetic shockwave across the full range (damage 8, KNOCKBACK 40 px, x2 vs MOAB-class).",
        _f8)
        .ability(AbilityBuilder.of("Open Titan Stampede", 60, "A herd runs from exit to entrance along every route, dealing 200 damage to every enemy it touches. Bosses take 1,500 and are knocked back 120 px.")
        .p("damage", 200).p("bossDamage", 1500).p("bossKnockback", 120).p("herdSpeed", 500))
        .build())


def mistral():
    return (TowerBuilder.of(TowerType.MISTRAL, "Windblade Turbine", 650)
        .description("Spinning wind blades that knock fast enemies back; later gusts, a tornado and a permanent hurricane vortex. No camo detection.")
        .tiers("Ministral 3 8B", "Ministral 3 14B", "Mistral Small 4", "Mistral Large 4")
        .attack(AttackKind.PROJECTILE, DamageType.KINETIC, 170, 0.7, 1, 3)
        .base(_f9)
        .upgrade(650, "Gust", "Every 3 s, knocks back fast enemies 60 px and other non-boss enemies 25 px.",
        _f10)
        .upgrade(1050, "Cyclone", "Every 8 s, a tornado sits on the track for 5 s, dealing 1 damage every 0.3 s.",
        _f11)
        .upgrade(1750, "Hurricane", "A permanent vortex (radius 70) at the nearest track bend in range: 2 damage every 0.3 s, SLOW 30%, x2 vs MOAB-class.",
        _f12)
        .ability(AbilityBuilder.of("Stratosphere Tempest", 50, "For 10 s, a super-hurricane (150 px) on a player-chosen bend deals 60 damage every 0.5 s to airships and pushes MOAB-class enemies back 120 px.")
        .target().p("duration", 10).p("tick", 0.5).p("damage", 60).p("bossKnockback", 120).p("radius", 150).p("snapRange", 300))
        .build())


def cohere():
    return (TowerBuilder.of(TowerType.COHERE, "Command Commander", 800)
        .description("Heavy artillery shells; later fragmentation, armour cracking, a supreme-command cannon and an override that turns enemies against each other. No camo detection.")
        .tiers("Command R7B", "Command R+", "Command A", "Command A+")
        .attack(AttackKind.PROJECTILE, DamageType.EXPLOSIVE, 230, 1.5, 3, 1)
        .base(_f13)
        .upgrade(800, "Fragmentation", "Impact releases 8 shrapnel (damage 1, pierce 2 each).",
        _f14)
        .upgrade(1300, "Formation Breaker", "Hits apply ARMOR CRACK and +50% damage taken for 5 s.",
        _f15)
        .upgrade(2200, "Supreme Command", "Damage 10, splash 90, interval 1.1, x3 vs MOAB-class.",
        _f16)
        .ability(AbilityBuilder.of("Command Override", 60, "The 12 nearest non-boss enemies (Bellarmine College Prep MOAB allowed; BFB, ZOMG, DDT and BAD excluded) reverse direction for 8 s and deal 100 damage/s to enemies they touch, then resume normally.")
        .p("count", 12).p("duration", 8).p("contactDps", 100))
        .build())


def glm():
    return (TowerBuilder.of(TowerType.GLM, "Gravity Manipulator", 600)
        .description("Grid projectiles that slow; later laser-linked nodes on the track, a slowing matrix web and saturation grid. No camo detection.")
        .tiers("GLM 5.1", "GLM 5.2", "GLM 5.3 Flash", "GLM 5.3")
        .attack(AttackKind.PROJECTILE, DamageType.GRAVITY, 170, 1.0, 1, 2)
        .base(_f17)
        .upgrade(550, "Gravity Well", "Places 2 nodes on the track in range, linked by a laser line; enemies crossing it take 2 damage (each enemy at most every 0.3 s).",
        _f18)
        .upgrade(900, "Matrix Web", "4 nodes forming a grid; enemies inside are SLOWED 30%.",
        _f19)
        .upgrade(1500, "Grid Saturation", "6 nodes, line damage 5, x2 vs Fortified.",
        _f20)
        .ability(AbilityBuilder.of("Matrix Overload", 60, "STUNS every non-boss enemy on the track for 5 s; bosses for 1.5 s.")
        .p("stun", 5).p("bossStun", 1.5))
        .build())


def kimi():
    return (TowerBuilder.of(TowerType.KIMI, "Dimensional Assassin", 700)
        .description("Crystalline shards that hit harder on the same target and remember every pop; later a long context chain and crystal bursts. All damage x0.5 vs Fortified. No camo detection.")
        .tiers("Kimi K2.5", "Kimi K2.6", "Kimi K3", "Kimi K3.1 Pro")
        .attack(AttackKind.PROJECTILE, DamageType.MAGIC, 180, 0.9, 1, 2)
        .base(_f21)
        .upgrade(700, "Memory Storage", "+1 permanent damage per 100 enemies this tower has popped this game (max +5). The memory counter is shown in the info panel.",
        _f22)
        .upgrade(1150, "Context Chain", "Consecutive-hit max becomes +8, and +1 pierce per stack.",
        _f23)
        .upgrade(1950, "Infinite Context", "Memory cap becomes +12; every 10th attack fires a crystal burst (damage 15, splash 70).",
        _f24)
        .ability(AbilityBuilder.of("Infinite Context Burst", 60, "Every enemy on screen, Fortified included, takes damage = memory stacks x 80 (960 at the 12-stack cap). Bosses take half.")
        .p("damagePerStack", 80).p("bossFraction", 0.5).p("hitsFortified", 1))
        .build())


def minimax():
    return (TowerBuilder.of(TowerType.MINIMAX, "Clone Generator", 650)
        .description("Data packets that bounce between enemies, gaining speed each bounce; later clones, splitting packets and synchronized barrages. No camo detection.")
        .tiers("MiniMax M2.5", "MiniMax M2.7", "MiniMax M3", "MiniMax M3.1 Flash")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 170, 0.5, 1, 1)
        .base(_f25)
        .upgrade(1050, None, "A clone copies the base attack; bounces become 6.",
        _f26)
        .upgrade(1050, "Mass Replication", "Each packet splits into 2 on its first hit.",
        _f27)
        .upgrade(1800, "Infinite Multiplication", "3 clones; every 6 s, a synchronized barrage of 20 packets.",
        _f28)
        .ability(AbilityBuilder.of("Scale Factor Overclock", 50, "Bounce count x3 and fire rate x2.5 for 10 s.")
        .p("duration", 10).p("bounceMult", 3).p("rateMult", 2.5))
        .build())


def all_towers():
    return [qwen(), llama(), mistral(), cohere(), glm(), kimi(), minimax()]
