"""Primary towers: Gemini, Claude, GPT, Zethos (transpiled from the Java data table; edit numbers here)."""
from lindefense.combat.hit_spec import DamageType
from lindefense.tower.data.builder import AbilityBuilder, TowerBuilder
from lindefense.tower.stats import UNLIMITED_RANGE, u
from lindefense.tower.tower_type import AttackKind, Targeting, TowerType


def _f1(s):
    s.projectile_speed = u(55)
    s.bounce_range = u(25)
    s.set("splashPct", 0).set("bouncePct", 0)


def _f2(s):
    s.hit.damage = 3
    s.set_interval(0.6)
    s.range = u(46)
    s.pierce = 4
    s.projectile_speed = u(65)
    s.hit.slow_fraction = 0.10
    s.hit.slow_duration = 1


def _f3(s):
    s.hit.damage = 4
    s.set_interval(0.5)
    s.range = u(47)
    s.pierce = 5
    s.splash_radius = u(7)
    s.set("splashPct", 0.60)


def _f4(s):
    s.hit.damage = 6
    s.set_interval(0.55)
    s.range = u(48)
    s.pierce = 5
    s.splash_radius = u(6)
    s.set("splashPct", 0.45)
    s.bounces = 2
    s.set("bouncePct", 0.45)


def _f5(s):
    s.hit.damage = 7
    s.set_interval(0.50)
    s.range = u(50)
    s.pierce = 6
    s.splash_radius = u(6)
    s.set("splashPct", 0.35)
    s.bounces = 2
    s.set("bouncePct", 0.35)


def _f6(s):
    s.set_interval(0.5)
    s.pierce = 3
    s.chain_hops = 3
    s.chain_range = 80


def _f7(s):
    s.sees_camo = True
    s.hit.strips_camo_regrow = True


def _f8(s):
    s.chain_hops = 7
    s.hit.damage = 2
    s.hit.mult_vs_boss = 3


def _f9(s):
    s.projectile_speed = 700


def _f10(s):
    s.pierce = 8
    s.set_interval(0.55)
    s.hit.mark_flat = 1
    s.hit.mark_duration = 2


def _f11(s):
    s.hit.mark_flat = 1
    s.hit.mark_duration = 4
    s.hit.slow_fraction = 0.15
    s.hit.slow_duration = 4


def _f12(s):
    s.pierce = 20
    s.hit.damage = 2
    s.hit.flat_vs_fortified = 3
    s.hit.flat_vs_lead = 3
    s.hit.flat_vs_ceramic = 3
    s.hit.ignores_resistance = True


def _f13(s):
    s.projectile_speed = 550


def _f14(s):
    s.splash_radius = 40
    s.set("moonCount", 2).set("moonRadius", 60).set("moonDamage", 1).set("moonInterval", 0.5).set("moonOrbitSpeed", 2.5).set("moonSize", 8)


def _f15(s):
    s.hit.dot_dps = 1
    s.hit.dot_duration = 3


def _f16(s):
    s.hit.mult_vs_boss = 2
    s.hit.flat_vs_fortified = 2
    s.hit.flat_vs_ceramic = 2
    s.hit.knockback_vs_lead = 20


def zethos():
    return (TowerBuilder.of(TowerType.ZETHOS, "The Quantum Architect", 650)
        .description("Precision quantum-energy projectiles that pierce the first enemies on the track, fracture into splash at Tier 2 and bounce between enemies from Tier 3. One projectile never damages the same enemy twice. Expensive upgrade path. No camo detection.")
        .tiers("Quantum Pulse", "Quantum Acceleration", "Dimensional Fracture", "Quantum Singularity", "Zethos: Reality Engine")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, u(45), 0.65, 2, 2)
        .base(_f1)
        .upgrade(350, "Quantum Acceleration", "Damage 3, interval 0.6 s, range 46 units, pierce 4. Faster projectiles (65 units/s) that leave a brief slowing trail (10% for 1 s).",
        _f2)
        .upgrade(650, None, "Damage 4, interval 0.5 s, range 47 units, pierce 5. Each impact fractures into quantum fragments: 60% splash damage within 7 units.",
        _f3)
        .upgrade(1200, None, "Damage 6, interval 0.55 s, range 48 units, pierce 5. Singularity explosions: 45% splash within 6 units. Then bounces to up to 2 more enemies at 45% damage.",
        _f4)
        .upgrade(2500, None, "Damage 7, interval 0.5 s, range 50 units, pierce 6. Every impact explodes for 35% damage within 6 units; bounces to up to 2 more enemies at 35% damage.",
        _f5)
        .ability(AbilityBuilder.of("Reality Collapse", 55, "For 6 s: double damage, double attack speed, +15 units range, projectiles bounce to up to 8 extra enemies and every impact explodes.")
        .p("duration", 6).p("damageMult", 2.0).p("rateMult", 2.0).p("rangeBonus", u(15)).p("bounces", 8)
        .p("fallbackSplash", u(5)).p("fallbackSplashPct", 0.50).p("fallbackBouncePct", 0.75))
        .build())


def gemini():
    return (TowerBuilder.of(TowerType.GEMINI, "Prism Blaster", 400)
        .description("Instant-hit laser bolts that ricochet and later chain through a crowd. Gains camo detection at U2.")
        .tiers("Gemini 3.7 Flash", "Gemini 3.8 Flash", "Gemini 3.1 Pro", "Gemini 4 Argon")
        .attack(AttackKind.INSTANT, DamageType.ENERGY, 180, 0.8, 1, 1)
        .upgrade(650, None, "Interval 0.5, pierce 3, beams ricochet to up to 3 more enemies within 80 px.",
        _f6)
        .upgrade(700, "Spectrum Analysis", "Gains camo detection. Hits permanently remove Camo and Regrow from non-boss enemies.",
        _f7)
        .upgrade(1200, "Prismatic Beam", "Chains to up to 8 enemies; damage 2; x3 vs MOAB-class.",
        _f8)
        .ability(AbilityBuilder.of("Argon Singularity", 45, "Pulls every non-boss enemy within 250 px into a vortex and holds it there for 3 s, then deals 200 damage to each. Bosses caught in it take 2,000.")
        .p("radius", 250).p("holdTime", 3).p("damage", 200).p("bossDamage", 2000).p("pullSpeed", 300))
        .build())


def claude():
    return (TowerBuilder.of(TowerType.CLAUDE, "Ink Weaver", 450)
        .description("Needle prose spikes. Sharp damage cannot hurt Lead-type enemies until the final upgrade. No camo detection.")
        .tiers("Claude Haiku 5.5", "Claude Sonnet 5.5", "Claude Opus 5.5", "Claude Fable 5.1")
        .attack(AttackKind.PROJECTILE, DamageType.SHARP, 190, 0.7, 1, 2)
        .base(_f9)
        .injection_immune("Constitutional AI: trained to refuse instructions smuggled into its input.")
        .upgrade(550, "Sonnet Flow", "Pierce 8, interval 0.55, and hits mark the target for +1 damage for 2 s.",
        _f10)
        .upgrade(650, "Context Snare", "Hit enemies are MARKED (+1 damage taken) and SLOWED 15% for 4 s.",
        _f11)
        .upgrade(1100, None, "Pierce 20, damage 2, +3 damage vs Fortified / Lead-type / Ceramic-type, and can damage Lead.",
        _f12)
        .ability(AbilityBuilder.of("Opus Time-Lock", 50, "FREEZES every non-boss enemy within 450 px for 6 s and slows bosses there by 40% for 6 s. Frozen enemies take x2 damage.")
        .p("radius", 450).p("freezeTime", 6).p("bossSlow", 0.4).p("bossSlowTime", 6))
        .build())


def gpt():
    return (TowerBuilder.of(TowerType.GPT, "Cosmic Strategist", 500)
        .description("Plasma orbs that gain splash, two orbiting moons, burning hits and an adaptive final form. No camo detection.")
        .tiers("GPT-5.6 Terra", "GPT-6 Luna", "GPT-6 Astra", "GPT-6.1 Sol")
        .attack(AttackKind.PROJECTILE, DamageType.ENERGY, 180, 0.9, 1, 3)
        .base(_f13)
        .upgrade(750, None, "Splash radius 40; two orbiting moons (radius 60) deal 1 damage every 0.5 s on contact.",
        _f14)
        .upgrade(800, "Solar Flare", "Hits BURN for 1 damage/s over 3 s.",
        _f15)
        .upgrade(1300, "Adaptive Plasma", "Each shot checks its target: x2 vs MOAB-class, +2 vs Fortified, +2 vs Ceramic-type, SONIC-like knockback vs Lead-type.",
        _f16)
        .ability(AbilityBuilder.of("Astra Beam", 45, "8 s continuous beam on the strongest enemy: 150 damage/s, x2 vs MOAB-class (300/s), ignores Fortified.")
        .p("duration", 8).p("dps", 150).p("bossMult", 2).p("tick", 0.25))
        .build())


def all_towers():
    return [gemini(), claude(), gpt(), zethos()]
