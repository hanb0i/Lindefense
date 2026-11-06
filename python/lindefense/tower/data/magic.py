"""Magic towers: DALL-E, Sora, Suno (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.set("zoneInterval", 6).set("zoneRadius", 35).set("zoneDuration", 4).set("zoneTick", 0.5).set("zoneDamage", 1)


def _f2(s):
    s.set("creatureInterval", 5).set("creatureCount", 2).set("creatureDamage", 2).set("creaturePierce", 5).set("creatureSpeed", 90).set("creatureSpacing", 24)


def _f3(s):
    s.set("zoneRadius", 70).set("zoneArmorCrack", 1)


def _f4(s):
    s.set("zoneInterval", 3).set("creatureCount", 4)
    s.pierce = 6


def _f5(s):
    s.field_radius = 150
    s.aura_enemy_slow = 0.35


def _f6(s):
    s.projectile_speed *= 2
    s.set_interval(0.7)
    s.aura_enemy_slow = 0.55


def _f7(s):
    s.set("rewindInterval", 8).set("rewindKnockback", 120)


def _f8(s):
    s.set("loopZones", 2).set("loopRadius", 60).set("loopTickDamage", 2).set("loopTick", 0.4).set("loopSlow", 0.6)


def _f9(s):
    s.set("bassInterval", 3).set("bassDamage", 2).set("bassRadius", 140)


def _f10(s):
    s.set("chordEvery", 4).set("chordDamage", 6).set("chordPierce", 10)


def _f11(s):
    s.set_interval(0.4)
    s.set("symphonyInterval", 1).set("symphonyCount", 2).set("symphonyRadius", 50).set("symphonyDamage", 3)


def dalle():
    return (TowerBuilder.of(TowerType.DALLE, "Sketch Summoner", 550)
        .description("Sketch arrows, plus paint zones on the track that damage enemies; later illustrated creatures that walk the track backward. No camo detection.")
        .tiers("DALL·E 2", "DALL·E 3", "DALL·E 3 HD", "DALL·E 3 API")
        .attack(AttackKind.PROJECTILE, DamageType.MAGIC, 170, 0.9, 1, 3)
        .base(_f1)
        .upgrade(500, "Living Illustration", "Every 5 s, 2 illustrated creatures walk backward along the track (contact damage 2, pierce 5 each).",
        _f2)
        .upgrade(850, "Masterpiece Explosion", "Paint zones grow to radius 70 and apply ARMOR CRACK to non-boss enemies inside, downgrading armored enemies into weaker forms.",
        _f3)
        .upgrade(1400, "Infinite Canvas", "Zones every 3 s, 4 creatures per wave, arrow pierce 6.",
        _f4)
        .ability(AbilityBuilder.of("Outpainting Expansion", 45, "Paints a 10 s \"extra track\" zone (130 px) on the selected track segment: enemies inside crawl at 35% speed (bosses resist part of it) and take 60 magic damage every 0.5 s.")
        .target().p("duration", 10).p("speedCap", 0.35).p("radius", 130).p("tick", 0.5).p("damage", 60))
        .build())


def sora():
    return (TowerBuilder.of(TowerType.SORA, "Time Director", 700)
        .description("Film-frame projectiles and a slowing field around the tower; later rewinds enemies and places time-loop zones. No camo detection.")
        .tiers("Sora", "Sora Turbo", "Sora 2", "Sora 2 Pro")
        .attack(AttackKind.PROJECTILE, DamageType.MAGIC, 160, 1.0, 1, 2)
        .base(_f5)
        .upgrade(650, "Fast Forward", "Projectile speed x2, interval 0.7, slow becomes 55%.",
        _f6)
        .upgrade(1000, "Scene Rewind", "Every 8 s, KNOCKBACK 120 px on all non-boss enemies in range.",
        _f7)
        .upgrade(1800, "Time Loop", "Places 2 loop zones (radius 60) on the track in range; enemies inside take 2 damage every 0.4 s and are SLOWED 60%.",
        _f8)
        .ability(AbilityBuilder.of("Cinematic Rewind", 60, "Every non-boss enemy on screen is thrown back along the track by 6 s of its own travel distance; bosses by 2 s.")
        .p("rewindSeconds", 6).p("bossRewindSeconds", 2))
        .build())


def suno():
    return (TowerBuilder.of(TowerType.SUNO, "Sonic Composer", 500)
        .description("Rhythmic sound projectiles (x2 vs Ceramic, knock Lead-type back); later bass-drop shockwaves, chords and random sonic explosions. No camo detection.")
        .tiers("Suno v5", "Suno v6-Mini", "Suno v6", "Suno v6-Wild")
        .attack(AttackKind.PROJECTILE, DamageType.SONIC, 160, 0.8, 1, 4)
        .upgrade(500, "Bass Drop", "Every 3 s, a shockwave deals 2 damage to all enemies within 140 px.",
        _f9)
        .upgrade(800, "Chord Strike", "Every 4th attack is a chord (damage 6, pierce 10).",
        _f10)
        .upgrade(1350, "Uncontrolled Symphony", "Interval 0.4; every 1 s, 2 random sonic explosions (radius 50, damage 3) on enemies in range.",
        _f11)
        .ability(AbilityBuilder.of("Symphonic Bass Drop", 45, "Every enemy on screen takes 100 + 150 x its speed multiplier damage (bosses capped at 1,500).")
        .p("baseDamage", 100).p("damagePerSpeed", 150).p("bossCap", 1500))
        .build())


def all_towers():
    return [dalle(), sora(), suno()]
