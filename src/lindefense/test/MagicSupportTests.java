package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.HitSpec;
import lindefense.combat.Projectile;
import lindefense.effects.TrackWalker;
import lindefense.effects.TrackZone;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AttackKind;
import lindefense.tower.BuffStat;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;

/**
 * Group B2 tests: Magic (DALL-E, Sora, Suno) and Support (Grok, Perplexity). Agents extend this class as the
 * special mechanics are implemented; every {@code // TODO(B2)} in the behaviours should gain a test here.
 */
public final class MagicSupportTests {
    private MagicSupportTests() { }

    /** type, range, interval, damage, pierce, damage type, kind. */
    private static final Object[][] BASE = {
        { TowerType.DALLE, 170.0, 0.9, 1.0, 3, DamageType.MAGIC, AttackKind.PROJECTILE },
        { TowerType.SORA, 160.0, 1.0, 1.0, 2, DamageType.MAGIC, AttackKind.PROJECTILE },
        { TowerType.SUNO, 160.0, 0.8, 1.0, 4, DamageType.SONIC, AttackKind.PROJECTILE },
        { TowerType.GROK, 170.0, 1.1, 2.0, 1, DamageType.EXPLOSIVE, AttackKind.PROJECTILE },
        { TowerType.PERPLEXITY, 180.0, 2.0, 1.0, 1, DamageType.MAGIC, AttackKind.CUSTOM },
    };

    public static void runAll() {
        run("b2.baseStatsMatchSpec", MagicSupportTests::baseStatsMatchSpec);
        run("b2.upgradeStatsMatchSpec", MagicSupportTests::upgradeStatsMatchSpec);
        run("b2.baseAttacksDamageEnemies", MagicSupportTests::baseAttacksDamageEnemies);
        run("b2.sora", MagicSupportTests::sora);
        run("b2.suno", MagicSupportTests::suno);
        run("b2.grok", MagicSupportTests::grok);
        run("b2.perplexity", MagicSupportTests::perplexity);
        run("b2.dalle.paintZones", MagicSupportTests::dallePaintZones);
        run("b2.dalle.creatures", MagicSupportTests::dalleCreatures);
        run("b2.dalle.armorCrackDowngrade", MagicSupportTests::dalleArmorCrack);
        run("b2.sora.sceneRewind", MagicSupportTests::soraSceneRewind);
        run("b2.sora.timeLoop", MagicSupportTests::soraTimeLoop);
        run("b2.suno.bassDrop", MagicSupportTests::sunoBassDrop);
        run("b2.suno.chordStrike", MagicSupportTests::sunoChord);
        run("b2.suno.symphony", MagicSupportTests::sunoSymphony);
        run("b2.grok.burnSpread", MagicSupportTests::grokBurnSpread);
        run("b2.grok.paradoxVolley", MagicSupportTests::grokVolley);
        run("b2.grok.chaosMode", MagicSupportTests::grokChaos);
        run("b2.perplexity.detectionAndReveal", MagicSupportTests::perplexityDetection);
        run("b2.perplexity.roundIncome", MagicSupportTests::perplexityIncome);
    }

    private static Game frozen() { Game g = newGame(0); g.setGlobalEnemySpeedMultiplier(0); return g; }
    private static Enemy at(Game g, EnemyType t, double d) { return spawnAt(g, t, null, 0, d); }
    private static boolean near(double a, double b) { return Math.abs(a - b) < 1e-9; }

    private static void baseStatsMatchSpec() {
        for (Object[] r : BASE) {
            TowerType t = (TowerType) r[0];
            TowerStats s = TowerCatalog.get(t).baseStats;
            check(near(s.range, (Double) r[1]), t + " range " + s.range);
            check(Math.abs(s.interval() - (Double) r[2]) < 1e-9, t + " interval " + s.interval());
            check(near(s.hit.damage, (Double) r[3]), t + " damage " + s.hit.damage);
            check(s.pierce == (Integer) r[4], t + " pierce " + s.pierce);
            check(s.hit.type == r[5], t + " damage type " + s.hit.type);
            check(s.kind == r[6], t + " attack kind " + s.kind);
        }
        TowerStats d = TowerCatalog.get(TowerType.DALLE).baseStats;
        check(d.p("zoneInterval") == 6 && d.p("zoneRadius") == 35 && d.p("zoneDuration") == 4 && d.p("zoneTick") == 0.5 && d.p("zoneDamage") == 1, "DALL-E paint zone: every 6 s, radius 35, 4 s, 1 dmg / 0.5 s");
        TowerStats s = TowerCatalog.get(TowerType.SORA).baseStats;
        check(s.fieldRadius == 150 && near(s.auraEnemySlow, 0.35), "Sora slow field radius 150, 35%");
        TowerStats g = TowerCatalog.get(TowerType.GROK).baseStats;
        check(g.splashRadius == 35 && g.seesCamo, "Grok splash 35, built-in camo detection");
        TowerStats p = TowerCatalog.get(TowerType.PERPLEXITY).baseStats;
        check(p.seesCamo && p.auraRange == 180 && p.auraDetection && p.incomePerWave == 40, "Perplexity: detection aura 180, +$40 per round");
    }

    private static void upgradeStatsMatchSpec() {
        TowerStats s;
        s = TowerCatalog.get(TowerType.DALLE).statsForTier(1);
        check(s.p("creatureInterval") == 5 && s.p("creatureCount") == 2 && s.p("creatureDamage") == 2 && s.p("creaturePierce") == 5, "DALL-E U1 creatures");
        s = TowerCatalog.get(TowerType.DALLE).statsForTier(2);
        check(s.p("zoneRadius") == 70 && s.p("zoneArmorCrack") == 1, "DALL-E U2: radius 70 + armor crack");
        s = TowerCatalog.get(TowerType.DALLE).statsForTier(3);
        check(s.p("zoneInterval") == 3 && s.p("creatureCount") == 4 && s.pierce == 6, "DALL-E U3: zones every 3 s, 4 creatures, arrow pierce 6");
        s = TowerCatalog.get(TowerType.SORA).statsForTier(1);
        check(near(s.projectileSpeed, 900) && Math.abs(s.interval() - 0.7) < 1e-9 && near(s.auraEnemySlow, 0.55), "Sora U1: speed x2, interval 0.7, slow 55%");
        s = TowerCatalog.get(TowerType.SORA).statsForTier(2);
        check(s.p("rewindInterval") == 8 && s.p("rewindKnockback") == 120, "Sora U2: knockback 120 px every 8 s");
        s = TowerCatalog.get(TowerType.SORA).statsForTier(3);
        check(s.p("loopZones") == 2 && s.p("loopRadius") == 60 && s.p("loopTickDamage") == 2 && s.p("loopTick") == 0.4 && s.p("loopSlow") == 0.6, "Sora U3 loop zones");
        s = TowerCatalog.get(TowerType.SUNO).statsForTier(1);
        check(s.p("bassInterval") == 3 && s.p("bassDamage") == 2 && s.p("bassRadius") == 140, "Suno U1 bass drop");
        s = TowerCatalog.get(TowerType.SUNO).statsForTier(2);
        check(s.p("chordEvery") == 4 && s.p("chordDamage") == 6 && s.p("chordPierce") == 10, "Suno U2 chord strike");
        s = TowerCatalog.get(TowerType.SUNO).statsForTier(3);
        check(Math.abs(s.interval() - 0.4) < 1e-9 && s.p("symphonyInterval") == 1 && s.p("symphonyCount") == 2 && s.p("symphonyRadius") == 50 && s.p("symphonyDamage") == 3, "Suno U3 symphony");
        s = TowerCatalog.get(TowerType.GROK).statsForTier(1);
        check(s.hit.dotDps == 1 && s.hit.dotDuration == 4 && s.p("burnSpreadRadius") == 40, "Grok U1: burn 1/s for 4 s, spreads within 40 px");
        s = TowerCatalog.get(TowerType.GROK).statsForTier(2);
        check(s.has("allowDensest") && s.p("volleyInterval") == 5 && s.p("volleyMissiles") == 6 && s.p("volleyDamage") == 3, "Grok U2: densest targeting + 6-missile volley every 5 s");
        s = TowerCatalog.get(TowerType.GROK).statsForTier(3);
        check(Math.abs(s.interval() - 0.6) < 1e-9 && s.p("chaosSplit") == 4 && s.p("chaosHeavyMoabMult") == 3, "Grok U3 chaos mode");
        s = TowerCatalog.get(TowerType.PERPLEXITY).statsForTier(1);
        check(s.has("revealAllCamo"), "Perplexity U1: map-wide camo targeting");
        s = TowerCatalog.get(TowerType.PERPLEXITY).statsForTier(2);
        check(near(s.fieldMarkPct, 0.20) && near(s.auraRangeBonus, 0.15) && s.auraSurveillanceImmunity, "Perplexity U2: +20% mark, +15% range, Surveillance immunity");
        s = TowerCatalog.get(TowerType.PERPLEXITY).statsForTier(3);
        check(s.incomePerWave == 250, "Perplexity U3: +$250 per round");
        for (Object[] r : BASE) check(TowerCatalog.get((TowerType) r[0]).ability != null && TowerCatalog.abilityNeedsUnlock((TowerType) r[0]), r[0] + " has an ability locked behind the max-tier unlock");
    }

    private static void baseAttacksDamageEnemies() {
        for (Object[] r : BASE) {
            TowerType type = (TowerType) r[0];
            Game g = frozen();
            Tower t = towerNearTrack(g, type, 0, 400);
            // Perplexity's radar only pings Camo enemies
            Enemy e = type == TowerType.PERPLEXITY ? spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO), 0, 400) : at(g, EnemyType.QUICK_SORT, 400);
            runSeconds(g, 5);
            check(t.getDamageDealt() > 0 && e.getHp() < e.getMaxHp(), type + " base attack damages an enemy");
        }
    }

    private static void sora() {
        Game g = frozen();
        Tower s = towerNearTrack(g, TowerType.SORA, 0, 400);
        Enemy in = at(g, EnemyType.HEAP_SORT, 400);
        Enemy out = at(g, EnemyType.HEAP_SORT, 900);
        g.run(10);
        check(near(in.getSlowFraction(), 0.35), "enemies inside the field are slowed 35%");
        check(out.getSlowFraction() == 0, "enemies outside the field are not slowed");
        g.upgradeTower(s);
        g.run(10);
        check(near(in.getSlowFraction(), 0.55), "U1 field slow is 55% (slows do not stack: strongest applies)");
    }

    private static void suno() {
        Game g = frozen();
        Tower s = towerNearTrack(g, TowerType.SUNO, 0, 400);
        Enemy heap = scaled(g, EnemyType.HEAP_SORT, 400, 20);
        Enemy ceramic = scaled(g, EnemyType.MERGE_SORT, 250, 20);
        double d0 = heap.getDistance();
        runSeconds(g, 2);
        check(heap.getDistance() < d0, "sonic hits knock Lead-type enemies back (d " + d0 + " -> " + heap.getDistance() + ")");
        check(s.getDamageDealt() > 0, "Suno damages Lead-type enemies");
        double dm = g.getCombat().applyHit(ceramic, s.getStats().hit, s, 1, 0);
        check(near(dm, 2), "sonic hits deal x2 to Ceramic-type, got " + dm);
    }

    private static Enemy scaled(Game g, EnemyType t, double d, double hpScale) {
        Enemy e = g.getEnemyManager().spawnScaled(t, null, 0, d, hpScale, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }

    private static void grok() {
        Game g = frozen();
        Tower grok = towerNearTrack(g, TowerType.GROK, 0, 400);
        check(grok.canSeeCamo(), "Grok sees camo");
        Enemy camo = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO), 0, 400);
        runSeconds(g, 3);
        check(camo.getHp() < camo.getMaxHp(), "Grok's explosive missiles pop Camo (built-in detection)");
        // splash hits clusters
        Game g2 = frozen();
        Tower g1 = towerNearTrack(g2, TowerType.GROK, 1, 400);
        Enemy a = scaled(g2, EnemyType.DYNAMIC_ARRAY, 400, 20), b = scaled(g2, EnemyType.DYNAMIC_ARRAY, 420, 20);
        g2.getCombat().attack(g1);
        runSeconds(g2, 0.01);
        for (int i = 0; i < 40; i++) g2.getCombat().updateProjectiles(Game.DT);
        check(a.getHp() < a.getMaxHp() && b.getHp() < b.getMaxHp(), "splash 35 hits both neighbours");
        check(a.hasStatus(StatusEffect.Kind.DOT) && near(a.statusMagnitude(StatusEffect.Kind.DOT), 1), "U1 hits BURN 1/s");
        a.tickStatuses(4.1);
        check(!a.hasStatus(StatusEffect.Kind.DOT), "burn lasts 4 s");
        // Densest Cluster unlocks at U2 only
        Tower u0 = forcePlace(g2, TowerType.GROK, buildableNear(g2, new Vec(1100, 840), 100), 0);
        u0.setTargeting(Targeting.DENSEST_CLUSTER);
        check(u0.getTargeting() != Targeting.DENSEST_CLUSTER, "base Grok cannot select Densest Cluster");
        Tower u2 = forcePlace(g2, TowerType.GROK, buildableNear(g2, new Vec(900, 840), 100), 2);
        u2.setTargeting(Targeting.DENSEST_CLUSTER);
        check(u2.getTargeting() == Targeting.DENSEST_CLUSTER, "Grok U2 can select Densest Cluster");
    }

    private static void perplexity() {
        Game g = frozen();
        Tower p = towerNearTrack(g, TowerType.PERPLEXITY, 0, 400);
        Enemy camo = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO), 0, 400);
        Enemy plain = at(g, EnemyType.QUICK_SORT, 410);
        runSeconds(g, 0.1);
        check(camo.getHp() == camo.getMaxHp() - 1, "radar pulse: 1 damage to Camo enemies");
        runSeconds(g, 2.0);
        check(camo.getHp() == camo.getMaxHp() - 2, "...repeating every 2 s");
        check(plain.getHp() == plain.getMaxHp(), "the pulse ignores non-Camo enemies");
        // U2: marks enemies in range, +15% range for towers in range, Surveillance immunity
        Game g2 = frozen();
        Tower p2 = towerNearTrack(g2, TowerType.PERPLEXITY, 2, 400);
        Tower gpt = forcePlace(g2, TowerType.GPT, buildableNear(g2, p2.getPosition().add(new Vec(60, 0)), 80), 0);
        Enemy marked = at(g2, EnemyType.HEAP_SORT, 400);
        g2.getTowerManager().recomputeAuras();
        g2.run(10);
        check(near(marked.getMarkedBonus(), 0.20), "enemies in range are MARKED +20%");
        check(near(gpt.effectiveRange(null), gpt.getStats().range * 1.15), "towers in range get +15% range");
        check(gpt.isSurveillanceImmune(), "towers in range are immune to Predictive Surveillance");
        double dmg = g2.getCombat().applyHit(marked, new HitSpec(2, DamageType.ENERGY), null, 1, 0);
        check(near(dmg, 2 * 1.2), "marked enemies take +20% from all sources, got " + dmg);
        // enemy kills add to the round pop value
        Game g4 = newGame(0);
        Enemy e = spawnAt(g4, EnemyType.STATIC_ARRAY, null, 0, 300);
        killOutright(g4, e);
        check(g4.getRoundPopValue() == Math.round(EnemyType.STATIC_ARRAY.reward * g4.getRewardScale()), "pops add to the round pop value");
    }

    // ------------------------------------------------------------------ B2 mechanics

    private static Enemy big(Game g, EnemyType t, EnumSet<Modifier> mods, double d) {
        Enemy e = g.getEnemyManager().spawnScaled(t, mods, 0, d, 500, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }

    private static void dallePaintZones() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.DALLE, 0, 400);
        // a CAMO enemy cannot be shot by DALL-E (no detection) but paint zones still land on it, isolating the zone damage
        Enemy e = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), 400);
        runSeconds(g, 5.9);
        check(g.getEffects().zonesOf(t, "paint").isEmpty(), "no paint zone before the 6 s interval");
        runSeconds(g, 0.2);
        List<TrackZone> zs = g.getEffects().zonesOf(t, "paint");
        check(zs.size() == 1, "one paint zone after 6 s, got " + zs.size());
        TrackZone z = zs.get(0);
        check(near(z.radius, 35) && near(z.tickInterval, 0.5) && near(z.tickHit.damage, 1) && !z.armorCrack, "base zone: radius 35, 1 dmg / 0.5 s, no crack");
        check(z.center.dist(e.getPosition()) < 1e-6, "the zone is painted on the track under the lead enemy in range");
        check(z.getRemaining() <= 4 && z.getRemaining() > 3.5, "zone lasts 4 s");
        runSeconds(g, 4.2);
        check(!z.isAlive(), "zone expires after 4 s");
        double lost = e.getMaxHp() - e.getHp();
        check(lost >= 7 && lost <= 8, "zone dealt 1 damage every 0.5 s for 4 s (7-8 ticks), lost " + lost);
        check(g.getEffects().zonesOf(t, "paint").isEmpty(), "no second zone before 12 s");
        // U3: zones every 3 s
        Game g3 = frozen();
        Tower t3 = towerNearTrack(g3, TowerType.DALLE, 3, 400);
        runSeconds(g3, 3.05);
        check(g3.getEffects().zonesOf(t3, "paint").size() == 1, "U3 paints a zone after 3 s");
        runSeconds(g3, 3.0);
        check(g3.getEffects().zonesOf(t3, "paint").size() == 2, "...and another 3 s later (both still alive: 4 s duration)");
        check(t3.getStats().pierce == 6, "U3 arrow pierce 6");
        // selling the tower removes its zones
        g3.sellTower(t3);
        check(g3.getEffects().zonesOf(t3, "paint").isEmpty(), "selling DALL-E removes its zones");
    }

    private static void dalleCreatures() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.DALLE, 1, 400);
        // enemy outside the tower's range so only the creatures reach it
        Enemy e = big(g, EnemyType.DYNAMIC_ARRAY, null, 150);
        runSeconds(g, 4.9);
        check(g.getEffects().getWalkers().isEmpty(), "no creatures before the 5 s interval");
        runSeconds(g, 0.2);
        List<TrackWalker> ws = new ArrayList<>(g.getEffects().getWalkers());
        check(ws.size() == 2, "U1: 2 creatures per cycle, got " + ws.size());
        for (TrackWalker w : ws) {
            check(!w.isForward() && w.endDistance == 0, "creatures walk BACKWARD toward the entrance");
            check(w.pierce == 5 && near(w.hit.damage, 2) && "creature".equals(w.kind), "creature contact damage 2, pierce 5");
            check(near(w.speed, t.getStats().p("creatureSpeed")), "creature speed comes from the data table");
        }
        runSeconds(g, 7);
        check(near(e.getMaxHp() - e.getHp(), 4), "each of the 2 creatures hits the enemy once for 2 (lost " + (e.getMaxHp() - e.getHp()) + ")");
        // U3: 4 creatures per wave
        Game g3 = frozen();
        towerNearTrack(g3, TowerType.DALLE, 3, 400);
        runSeconds(g3, 5.05);
        int n = 0;
        for (TrackWalker w : g3.getEffects().getWalkers()) if ("creature".equals(w.kind)) n++;
        check(n == 4, "U3: 4 creatures per wave, got " + n);
    }

    private static void dalleArmorCrack() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.DALLE, 2, 400);
        Enemy fort = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.FORTIFIED), 400);
        Enemy heap = big(g, EnemyType.HEAP_SORT, null, 410);
        Enemy boss = g.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 420, 50, 1.0);
        g.getEnemyManager().update(0);
        check(fort.isFortified() && hitFor(g, heap, 1, DamageType.SHARP) == 0, "precondition: Fortified, and Sharp cannot hurt Heap Sort");
        runSeconds(g, 6.1);
        List<TrackZone> zs = g.getEffects().zonesOf(t, "paint");
        check(zs.size() == 1 && near(zs.get(0).radius, 70) && zs.get(0).armorCrack, "U2 zone: radius 70 with armor crack");
        check(!fort.isFortified(), "armored (Fortified) enemies in the zone are downgraded: Fortified stripped");
        check(heap.isArmorCracked() && hitFor(g, heap, 1, DamageType.SHARP) > 0, "Lead-type in the zone is cracked: Sharp now hurts it");
        check(!boss.isArmorCracked(), "bosses are not cracked");
        runSeconds(g, 4.5);
        check(!heap.isArmorCracked(), "crack ends shortly after the zone expires");
    }

    private static void soraSceneRewind() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.SORA, 2, 400);
        Enemy in = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), 400);
        Enemy boss = g.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, EnumSet.of(Modifier.CAMO), 0, 410, 50, 1.0);
        Enemy far = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), 900);
        g.getEnemyManager().update(0);
        runSeconds(g, 7.9);
        check(near(in.getDistance(), 400), "no rewind before 8 s");
        runSeconds(g, 0.2);
        check(near(in.getDistance(), 280), "Scene Rewind: -120 px for non-boss in range, got " + in.getDistance());
        check(near(boss.getDistance(), 410), "bosses are immune");
        check(near(far.getDistance(), 900), "enemies out of range are untouched");
        runSeconds(g, 8.0);
        check(near(in.getDistance(), 160), "repeats every 8 s");
        check(t.getStats().has("rewindInterval"), "Scene Rewind runs from the data table");
    }

    private static void soraTimeLoop() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.SORA, 3, 400);
        runSeconds(g, 0.1);
        List<TrackZone> zs = g.getEffects().zonesOf(t, "loop");
        check(zs.size() == 2, "U3 places 2 loop zones, got " + zs.size());
        TrackZone a = zs.get(0), b = zs.get(1);
        for (TrackZone z : zs) {
            check(near(z.radius, 60) && z.permanent && near(z.slow, 0.6) && near(z.tickInterval, 0.4) && near(z.tickHit.damage, 2), "loop zone: radius 60, slow 60%, 2 dmg / 0.4 s");
            check(g.getMap().getRoutes().get(0).distanceToPoint(z.center) < 1e-6 || g.getMap().getRoutes().size() > 1, "loop zone sits on the track");
            check(z.center.dist(t.getPosition()) <= t.effectiveRange(g), "loop zone is inside the tower's range");
        }
        check(a.center.dist(b.center) > a.radius, "the two loops are distinct");
        runSeconds(g, 5);
        check(g.getEffects().zonesOf(t, "loop").size() == 2, "permanent while the tower lives (still 2, none duplicated)");
        double dist = g.getMap().getRoutes().get(0).nearestDistanceAlong(a.center);
        Enemy e = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), dist);
        check(a.contains(e), "precondition: enemy inside the loop");
        runSeconds(g, 2.0);
        check(near(e.getSlowFraction(), 0.6), "enemies in the loop are SLOWED 60%: " + e.getSlowFraction());
        double lost = e.getMaxHp() - e.getHp();
        check(lost >= 8 && lost <= 10, "2 damage every 0.4 s (4-5 ticks in 2 s), lost " + lost);
        g.sellTower(t);
        check(g.getEffects().zonesOf(t, "loop").isEmpty(), "selling Sora removes the loops");
    }

    private static double trackDistWithin(Game g, Vec from, double lo, double hi) {
        var r = g.getMap().getRoutes().get(0);
        for (double d = 0; d < r.getTotalLength(); d += 5) {
            double x = r.positionAt(d).dist(from);
            if (x >= lo && x <= hi) return d;
        }
        throw new IllegalStateException("no track point in [" + lo + "," + hi + "]");
    }

    private static void sunoBassDrop() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.SUNO, 1, 400);
        // CAMO enemies cannot be shot by Suno, isolating the shockwave
        Enemy in = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), trackDistWithin(g, t.getPosition(), 0, 100));
        Enemy out = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), trackDistWithin(g, t.getPosition(), 200, 260));
        runSeconds(g, 2.9);
        check(in.getHp() == in.getMaxHp(), "no shockwave before 3 s");
        runSeconds(g, 0.2);
        check(near(in.getMaxHp() - in.getHp(), 2), "Bass Drop deals 2 damage within 140 px, got " + (in.getMaxHp() - in.getHp()));
        check(out.getHp() == out.getMaxHp(), "enemies beyond 140 px are untouched");
        runSeconds(g, 3.0);
        check(near(in.getMaxHp() - in.getHp(), 4), "repeats every 3 s");
        // Lead-type is knocked back 20 px by the SONIC shockwave
        Game g2 = frozen();
        Tower t2 = towerNearTrack(g2, TowerType.SUNO, 1, 400);
        double d = trackDistWithin(g2, t2.getPosition(), 0, 100);
        Enemy heap = g2.getEnemyManager().spawnScaled(EnemyType.HEAP_SORT, EnumSet.of(Modifier.CAMO), 0, d, 500, 1.0);
        g2.getEnemyManager().update(0);
        runSeconds(g2, 3.05);
        check(near(heap.getDistance(), d - 20), "sonic shockwave knocks Lead-type back 20 px, d " + d + " -> " + heap.getDistance());
    }

    private static void sunoChord() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.SUNO, 2, 400);
        big(g, EnemyType.DYNAMIC_ARRAY, null, trackDistWithin(g, t.getPosition(), 60, 100));
        for (int i = 0; i < 8; i++) g.getCombat().attack(t);
        g.getCombat().updateProjectiles(0);
        int chords = 0, normals = 0;
        for (Projectile p : g.getCombat().getProjectiles()) {
            if ("chord".equals(p.getShot().tag)) {
                chords++;
                check(near(p.getHit().damage, 6) && p.getShot().pierce == 10, "chord: damage 6, pierce 10");
            } else {
                normals++;
                check(near(p.getHit().damage, 1) && p.getShot().pierce == 4, "normal note: damage 1, pierce 4");
            }
        }
        check(chords == 2 && normals == 6, "every 4th attack is a chord: 2 of 8, got " + chords + "/" + normals);
        check(near(t.getStats().hit.damage, 1), "the chord does not mutate the tower's stats");
        // before U2 there is no chord
        Game g0 = frozen();
        Tower t0 = towerNearTrack(g0, TowerType.SUNO, 1, 400);
        big(g0, EnemyType.DYNAMIC_ARRAY, null, trackDistWithin(g0, t0.getPosition(), 60, 100));
        for (int i = 0; i < 8; i++) g0.getCombat().attack(t0);
        g0.getCombat().updateProjectiles(0);
        for (Projectile p : g0.getCombat().getProjectiles()) check(!"chord".equals(p.getShot().tag), "no chords before U2");
    }

    private static void sunoSymphony() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.SUNO, 3, 400);
        double d = trackDistWithin(g, t.getPosition(), 60, 100);
        Enemy target = big(g, EnemyType.DYNAMIC_ARRAY, null, d);
        Enemy farAway = big(g, EnemyType.DYNAMIC_ARRAY, null, 900);
        t.getBehavior().update(g, t, 0.5);
        g.getEffects().update(1.0);
        check(target.getHp() == target.getMaxHp(), "no explosions before the 1 s interval");
        t.getBehavior().update(g, t, 0.5);
        g.getEffects().update(1.0);
        check(near(target.getMaxHp() - target.getHp(), 6), "2 sonic explosions of 3 damage land on the enemy in range, got " + (target.getMaxHp() - target.getHp()));
        check(farAway.getHp() == farAway.getMaxHp(), "enemies out of range are not targeted");
        Game g2 = frozen();
        Tower t2 = towerNearTrack(g2, TowerType.SUNO, 3, 400);
        Enemy camo = big(g2, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), trackDistWithin(g2, t2.getPosition(), 60, 100));
        t2.getBehavior().update(g2, t2, 1.0);
        g2.getEffects().update(1.0);
        check(camo.getHp() == camo.getMaxHp(), "explosions only pick enemies the tower can target (not undetected Camo)");
        check(near(t.getStats().p("symphonyRadius"), 50), "explosion radius 50 from the data table");
        check(Math.abs(t.getStats().interval() - 0.4) < 1e-9, "U3 interval 0.4");
    }

    private static void grokBurnSpread() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.GROK, 1, 400);
        double d = 400;
        Enemy a = big(g, EnemyType.DYNAMIC_ARRAY, null, d);
        Enemy b = big(g, EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), d + 38);
        Enemy c = big(g, EnemyType.DYNAMIC_ARRAY, null, d + 60);
        Enemy far2 = big(g, EnemyType.DYNAMIC_ARRAY, null, d + 76);
        check(a.getPosition().dist(b.getPosition()) <= 40 && a.getPosition().dist(c.getPosition()) > 40 && b.getPosition().dist(far2.getPosition()) <= 40
            && a.getPosition().dist(far2.getPosition()) > 40, "precondition: geometry (38 / 60 / 76 px)");
        g.getCombat().applyHit(new HitContext(a, t.getStats().hit, t));
        check(a.hasStatus(StatusEffect.Kind.DOT), "the hit burns its target");
        check(b.hasStatus(StatusEffect.Kind.DOT) && near(b.statusMagnitude(StatusEffect.Kind.DOT), 1), "burn spreads to an enemy within 40 px (even Camo: Grok detects)");
        check(!c.hasStatus(StatusEffect.Kind.DOT), "...but not to one 60 px away");
        check(!far2.hasStatus(StatusEffect.Kind.DOT), "...and the spread burn does not spread again (once only)");
        // no spread before U1
        Game g0 = frozen();
        Tower t0 = towerNearTrack(g0, TowerType.GROK, 0, 400);
        Enemy a0 = big(g0, EnemyType.DYNAMIC_ARRAY, null, 400), b0 = big(g0, EnemyType.DYNAMIC_ARRAY, null, 430);
        g0.getCombat().applyHit(new HitContext(a0, t0.getStats().hit, t0));
        check(!a0.hasStatus(StatusEffect.Kind.DOT) && !b0.hasStatus(StatusEffect.Kind.DOT), "base Grok neither burns nor spreads");
    }

    private static void grokVolley() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.GROK, 2, 400);
        List<Enemy> pack = new ArrayList<>();
        for (int i = 0; i < 5; i++) pack.add(big(g, EnemyType.DYNAMIC_ARRAY, null, 400 + i * 4));
        Enemy lone = big(g, EnemyType.DYNAMIC_ARRAY, null, 280);
        t.getBehavior().update(g, t, 4.9);
        g.getEffects().update(1.0);
        check(pack.get(0).getHp() == pack.get(0).getMaxHp(), "no volley before 5 s");
        t.getBehavior().update(g, t, 0.2);
        g.getEffects().update(1.0);
        for (Enemy e : pack) check(near(e.getMaxHp() - e.getHp(), 18), "6 missiles x 3 damage land on the densest cluster, got " + (e.getMaxHp() - e.getHp()));
        check(lone.getHp() == lone.getMaxHp(), "the lone enemy is not targeted");
        // nothing in range: no volley is wasted and nothing throws
        Game g2 = frozen();
        Tower t2 = towerNearTrack(g2, TowerType.GROK, 2, 400);
        Enemy faraway = big(g2, EnemyType.DYNAMIC_ARRAY, null, 900);
        t2.getBehavior().update(g2, t2, 5.0);
        g2.getEffects().update(1.0);
        check(faraway.getHp() == faraway.getMaxHp(), "no volley with nothing in range");
        check(t.getStats().pi("volleyMissiles") == 6, "volley size from the data table");
    }

    private static void grokChaos() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.GROK, 3, 400);
        Enemy a = big(g, EnemyType.DYNAMIC_ARRAY, null, 400);
        String[] tags = new String[6];
        double[] dots = new double[6];
        double[] boss = new double[6];
        for (int i = 0; i < 6; i++) {
            AttackContext c = g.getCombat().newAttackContext(t, java.util.Collections.singletonList(a));
            t.getBehavior().modifyAttack(g, t, c);
            tags[i] = c.tag; dots[i] = c.hit().dotDps; boss[i] = c.hit().multVsBoss;
        }
        check("incendiary".equals(tags[0]) && "cluster".equals(tags[1]) && "heavy".equals(tags[2]) && "incendiary".equals(tags[3]), "missile types cycle incendiary / cluster / heavy");
        check(dots[0] == 1 && dots[1] == 0 && dots[2] == 0 && dots[3] == 1, "only incendiary missiles burn");
        check(near(boss[2], 3) && near(boss[0], 1) && near(boss[1], 1), "heavy is x3 vs MOAB-class");
        check(near(t.getStats().hit.dotDps, 1) && near(t.getStats().hit.multVsBoss, 1), "the cycle never mutates the tower's base stats");
        // cluster split: 4 fragments toward the nearest other enemies
        Game g2 = frozen();
        Tower t2 = towerNearTrack(g2, TowerType.GROK, 3, 400);
        Enemy hitA = big(g2, EnemyType.DYNAMIC_ARRAY, null, 400);
        Enemy b = big(g2, EnemyType.DYNAMIC_ARRAY, null, 337);
        Vec dir = g2.getMap().getRoutes().get(0).directionAt(400);
        Enemy c = big(g2, EnemyType.DYNAMIC_ARRAY, null, 463);
        check(hitA.getPosition().dist(b.getPosition()) > 50 && hitA.getPosition().dist(b.getPosition()) < 80, "precondition: fragments' targets lie outside the splash");
        t2.setCounter("chaos", 1);
        // fire from the side so the missile does not fly through the neighbours
        AttackContext cc = g2.getCombat().newAttackContext(t2, java.util.Collections.singletonList(hitA));
        t2.getBehavior().modifyAttack(g2, t2, cc);
        g2.getCombat().executeAttack(cc, hitA.getPosition().add(new Vec(-dir.y * 100, dir.x * 100)), true, true);
        int maxFragments = 0;
        for (int i = 0; i < 90; i++) {
            g2.getCombat().updateProjectiles(Game.DT);
            int f = 0;
            for (Projectile p : g2.getCombat().getProjectiles()) if ("fragment".equals(p.getShot().tag)) f++;
            maxFragments = Math.max(maxFragments, f);
        }
        check(maxFragments == 4, "a cluster missile splits into 4 fragments (and fragments do not split), got " + maxFragments);
        check(!hitA.hasStatus(StatusEffect.Kind.DOT), "cluster missiles do not burn");
        check(near(hitA.getMaxHp() - hitA.getHp(), 2), "the cluster missile itself deals its 2 splash damage");
        check(near(b.getMaxHp() - b.getHp(), 4) && near(c.getMaxHp() - c.getHp(), 4), "fragments (2 damage each) hit the neighbours: " + (b.getMaxHp() - b.getHp()) + " / " + (c.getMaxHp() - c.getHp()));
        // heavy against a boss
        Game g3 = frozen();
        Tower t3 = towerNearTrack(g3, TowerType.GROK, 3, 400);
        Enemy bossE = g3.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 400, 50, 1.0);
        g3.getEnemyManager().update(0);
        t3.setCounter("chaos", 2);
        double before = bossE.getHp();
        g3.getCombat().attack(t3);
        for (int i = 0; i < 90; i++) g3.getCombat().updateProjectiles(Game.DT);
        double heavy = before - bossE.getHp();
        Enemy ref = g3.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 420, 50, 1.0);
        g3.getEnemyManager().update(0);
        double normal = g3.getCombat().applyHit(ref, t3.getStats().hit, t3, 1, 0);
        check(heavy > 0 && near(heavy, normal * 3), "heavy missile deals x3 to a boss: " + heavy + " vs " + normal);
    }

    private static void perplexityDetection() {
        Game g = frozen();
        Tower p = towerNearTrack(g, TowerType.PERPLEXITY, 0, 400);
        Tower near180 = forcePlace(g, TowerType.GPT, buildableNear(g, p.getPosition().add(new Vec(100, 0)), 40), 0);
        Tower far180 = forcePlace(g, TowerType.GPT, buildableNear(g, p.getPosition().add(new Vec(-300, 0)), 60), 0);
        check(near180.getPosition().dist(p.getPosition()) <= 180 && far180.getPosition().dist(p.getPosition()) > 180, "precondition: GPT towers inside / outside 180 px");
        check(!near180.getStats().seesCamo, "precondition: GPT has no built-in camo detection");
        g.getTowerManager().recomputeAuras();
        check(near180.canSeeCamo() && !far180.canSeeCamo(), "towers within 180 px gain camo detection; others do not");
        Enemy camo = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO), 0, 400);
        check(camo.isTargetableBy(near180.canSeeCamo()) && !camo.isTargetableBy(far180.canSeeCamo()), "camo targetable only by detecting towers");
        // U1: every tower anywhere can target Camo while this tower exists
        g.upgradeTower(p);
        g.getTowerManager().recomputeAuras();
        check(far180.canSeeCamo(), "U1: all Camo enemies can be targeted by every tower");
        g.sellTower(p);
        g.getTowerManager().recomputeAuras();
        check(!far180.canSeeCamo() && !near180.canSeeCamo(), "...only while the Perplexity exists");
    }

    private static void perplexityIncome() {
        for (int tier = 0; tier <= 3; tier++) {
            Game with = newGame(0), without = newGame(0);
            forcePlace(with, TowerType.PERPLEXITY, buildableNear(with, new Vec(600, 450), 300), tier);
            double c0 = with.getCash(), c1 = without.getCash();
            with.onWaveCompleted(1, lindefense.wave.WaveData.get(1));
            without.onWaveCompleted(1, lindefense.wave.WaveData.get(1));
            double expected = tier < 3 ? 40 : 250;
            check(near((with.getCash() - c0) - (without.getCash() - c1), expected), "tier " + tier + " pays +$" + expected + " at round end, got " + ((with.getCash() - c0) - (without.getCash() - c1)));
        }
    }

    /** Helper kept for B2 extensions. */
    static List<Enemy> cluster(Game g, EnemyType t, double start, int n, double spacing) {
        List<Enemy> l = new ArrayList<>();
        for (int i = 0; i < n; i++) l.add(spawnAt(g, t, null, 0, start + i * spacing));
        return l;
    }
}
