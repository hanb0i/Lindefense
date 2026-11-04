package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.effects.Barrage;
import lindefense.effects.Drone;
import lindefense.effects.Effects;
import lindefense.effects.NodeHazard;
import lindefense.effects.TrackWalker;
import lindefense.effects.TrackZone;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AttackKind;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.behavior.KimiBehavior;
import lindefense.wave.WaveData;

/** Headless tests for the reusable simulation primitives (zones, walkers, drones, barrages, node hazards, enemy operations, counters, income). */
public final class EnginePrimitiveTests {
    private EnginePrimitiveTests() { }

    public static void runAll() {
        run("engine.trackZone", EnginePrimitiveTests::trackZone);
        run("engine.trackWalker", EnginePrimitiveTests::trackWalker);
        run("engine.drone", EnginePrimitiveTests::drone);
        run("engine.barrage", EnginePrimitiveTests::barrage);
        run("engine.nodeHazard", EnginePrimitiveTests::nodeHazard);
        run("engine.enemyReverse", EnginePrimitiveTests::enemyReverse);
        run("engine.enemyRewindHold", EnginePrimitiveTests::enemyRewindHold);
        run("engine.enemyDestroyStrip", EnginePrimitiveTests::enemyDestroyStrip);
        run("engine.palantirShield", EnginePrimitiveTests::palantirShield);
        run("engine.counters", EnginePrimitiveTests::counters);
        run("engine.roundIncome", EnginePrimitiveTests::roundIncome);
        run("engine.scheduleAndOwnerCleanup", EnginePrimitiveTests::scheduleAndOwnerCleanup);
    }

    private static Game frozen() { Game g = newGame(0); g.setGlobalEnemySpeedMultiplier(0); return g; }
    /** A tower placed in a far corner so it never attacks the scene (owner of effects under test). */
    private static Tower farTower(Game g, TowerType type) { return forcePlace(g, type, buildableNear(g, new Vec(1130, 860), 150), 0); }
    private static Path route(Game g) { return g.getMap().getRoutes().get(0); }
    private static Enemy at(Game g, EnemyType t, double d) { return spawnAt(g, t, null, 0, d); }

    private static void trackZone() {
        Game g = frozen();
        Vec c = route(g).positionAt(400);
        Enemy in = at(g, EnemyType.TIMSORT, 400), out = at(g, EnemyType.TIMSORT, 600);
        Enemy boss = at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 405);
        TrackZone z = new TrackZone(c, 35, null);
        z.duration = 2; z.tickInterval = 0.5; z.tickHit = new HitSpec(1, DamageType.MAGIC);
        z.speedCap = 0.25; z.armorCrack = true;
        g.getEffects().addZone(z);
        runSeconds(g, 1.1);
        check(in.getHp() == in.getMaxHp() - 2, "tick damage every 0.5 s (2 ticks in 1.1 s), hp " + in.getHp());
        check(out.getHp() == out.getMaxHp(), "enemies outside the radius are untouched");
        check(Math.abs(in.getSlowFraction() - 0.75) < 1e-9 && Math.abs(in.currentSpeed(1) - in.nominalSpeed() * 0.25) < 1e-6, "speed cap 25% = 75% slow");
        check(in.isArmorCracked(), "zone applies ARMOR CRACK to non-bosses");
        check(!boss.isArmorCracked(), "zone does not crack bosses by default");
        check(Math.abs(boss.getSlowFraction() - 0.25) < 1e-9, "boss gets 1/3 of the zone slow (0.75 / 3)");
        runSeconds(g, 1.2);
        check(g.getEffects().getZones().isEmpty(), "zone expires after its duration");
        in.tickStatuses(1);
        check(!in.hasStatus(StatusEffect.Kind.SLOW), "slow and crack end shortly after the zone");
        // bosses-only + permanent zone bound to its owner
        Game g2 = frozen();
        Tower owner = farTower(g2, TowerType.MISTRAL);
        Enemy b2 = at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 400), n2 = at(g2, EnemyType.TIMSORT, 400);
        TrackZone pz = new TrackZone(route(g2).positionAt(400), 40, owner);
        pz.permanent = true; pz.bossesOnly = true; pz.tickInterval = 0.3; pz.tickHit = new HitSpec(10, DamageType.MAGIC); pz.kind = "tempest";
        g2.getEffects().addZone(pz);
        runSeconds(g2, 20);
        check(b2.getHp() < b2.getMaxHp() && n2.getHp() == n2.getMaxHp(), "bosses-only zone hits airships only");
        check(g2.getEffects().zonesOf(owner, "tempest").size() == 1, "permanent zone outlives any duration");
        g2.sellTower(owner);
        g2.run(2);
        check(g2.getEffects().getZones().isEmpty(), "zone disappears when its owner is sold");
    }

    private static void trackWalker() {
        Game g = frozen();
        Path r = route(g);
        Tower owner = farTower(g, TowerType.LLAMA);
        Enemy a = at(g, EnemyType.TIMSORT, 450);
        TrackWalker w = new TrackWalker(r, 300, 600, 150, owner, new HitSpec(2, DamageType.ENERGY));
        w.pierce = 1;
        g.getEffects().addWalker(w);
        runSeconds(g, 1.5);
        check(a.getHp() == a.getMaxHp() - 2, "walker contact damage 2, hp " + a.getHp());
        check(!w.isAlive() && g.getEffects().getWalkers().isEmpty(), "walker with pierce 1 expires after one enemy");
        check(owner.getDamageDealt() >= 2, "walker damage is credited to its owner");
        // pierce counts distinct enemies; per-enemy cooldown permits re-hits
        Game g2 = frozen();
        Enemy e1 = at(g2, EnemyType.TIMSORT, 500), e2 = at(g2, EnemyType.TIMSORT, 505), e3 = at(g2, EnemyType.TIMSORT, 510);
        TrackWalker w2 = new TrackWalker(route(g2), 700, 300, 100, null, new HitSpec(1, DamageType.ENERGY));
        w2.pierce = 2;
        g2.getEffects().addWalker(w2);
        runSeconds(g2, 4.5);
        int hit = 0; for (Enemy e : Arrays.asList(e1, e2, e3)) if (e.getHp() < e.getMaxHp()) hit++;
        check(hit == 2 && w2.getDistinctHits() == 2, "pierce 2 hits exactly two enemies, hit " + hit);
        check(w2.distance == 300 || !w2.isAlive(), "backward walker travels toward the entrance");
        Game g3 = frozen();
        Enemy slow = at(g3, EnemyType.TIMSORT, 500);
        TrackWalker w3 = new TrackWalker(route(g3), 500, 600, 1, null, new HitSpec(1, DamageType.ENERGY));
        w3.pierce = 99; w3.perEnemyCooldown = 0.5; w3.lifetime = 2.05;
        g3.getEffects().addWalker(w3);
        g3.run(3 * 60);
        check(slow.getMaxHp() - slow.getHp() >= 3 && slow.getMaxHp() - slow.getHp() <= 5, "per-enemy hit cooldown re-hits every 0.5 s: " + (slow.getMaxHp() - slow.getHp()));
        check(!w3.isAlive(), "walker lifetime ends it");
        // boss alternative spec
        Game g4 = frozen();
        Enemy boss = at(g4, EnemyType.BELLARMINE_COLLEGE_PREP, 500);
        Enemy norm = at(g4, EnemyType.TIMSORT, 500);
        TrackWalker w4 = new TrackWalker(route(g4), 500, 500, 0, null, new HitSpec(15, DamageType.ENERGY));
        w4.bossHit = new HitSpec(60, DamageType.ENERGY); w4.bossHit.bossKnockback = 50; w4.bossHit.uncappedKnockback = true; w4.pierce = 5;
        g4.getEffects().addWalker(w4);
        g4.run(2);
        check(norm.getMaxHp() - norm.getHp() == 10 /* timsort hp 10 dies? */ || !norm.isAlive(), "normal enemies take the normal spec");
        check(boss.getDistance() == 450 && boss.getHp() < boss.getMaxHp() - 40, "bosses take the boss spec (60 dmg x0.75 armour, 50 px knockback)");
    }

    private static void drone() {
        Game g = frozen();
        Tower owner = towerNearTrack(g, TowerType.CLAUDE, 0, 300); // Claude's Sharp shots cannot hurt Lead-type enemies
        Enemy e = at(g, EnemyType.HEAP_SORT, 300);
        TowerStats ds = Drone.statsFor(AttackKind.INSTANT, 400, 0.2, 1, DamageType.ENERGY, 1, 0);
        Drone d = Drone.orbit(owner, ds, 40, 0);
        d.lifetime = 1.0; d.kind = "buddy";
        g.getEffects().addDrone(d);
        Vec p0 = d.getPosition();
        runSeconds(g, 0.5);
        check(d.getPosition().dist(owner.getPosition()) > 39 && d.getPosition().dist(owner.getPosition()) < 41, "orbit drone stays on its circle");
        check(d.getPosition().dist(p0) > 1, "orbit drone moves");
        check(e.getHp() <= e.getMaxHp() - 2, "drone fires on its own interval (damage " + (e.getMaxHp() - e.getHp()) + ")");
        check(owner.getDamageDealt() > 0, "drone damage credited to the owner");
        runSeconds(g, 0.7);
        check(!d.isAlive() && g.getEffects().getDrones().isEmpty(), "drone lifetime ends it");
        // detection: camo hit only with detection
        Game g2 = frozen();
        Tower o2 = towerNearTrack(g2, TowerType.CLAUDE, 0, 300);
        Enemy camo = spawnAt(g2, EnemyType.HEAP_SORT, EnumSet.of(Modifier.CAMO), 0, 300);
        Drone blind = Drone.orbit(o2, Drone.statsFor(AttackKind.INSTANT, 400, 0.2, 1, DamageType.ENERGY, 1, 0), 30, 0);
        g2.getEffects().addDrone(blind);
        runSeconds(g2, 1);
        check(camo.getHp() == camo.getMaxHp(), "drone without detection ignores Camo");
        blind.detection = true;
        runSeconds(g2, 1);
        check(camo.getHp() < camo.getMaxHp(), "drone with its own detection hits Camo");
        // patrol drone walks its route segment anywhere; projectile drone
        Game g3 = frozen();
        Tower o3 = towerNearTrack(g3, TowerType.CLAUDE, 0, 300);
        TowerStats ps = Drone.statsFor(AttackKind.PROJECTILE, 150, 1.2, 2, DamageType.ENERGY, 4, 500);
        Drone pd = Drone.patrol(o3, ps, route(g3), 700, 800, 100);
        g3.getEffects().addDrone(pd);
        Enemy target = at(g3, EnemyType.HEAP_SORT, 750);
        runSeconds(g3, 1.5);
        check(pd.getPosition().dist(route(g3).positionAt(700)) < 200 && pd.getPosition().dist(route(g3).positionAt(700)) > 0, "patrol drone moves along its segment");
        runSeconds(g3, 3);
        check(target.getHp() < target.getMaxHp(), "patrolling projectile drone shoots enemies near it");
        // mirror owner uses owner's stats
        Game g4 = frozen();
        Tower o4 = farTower(g4, TowerType.MINIMAX);
        Drone clone = Drone.orbit(o4, null, 30, 0);
        clone.mirrorOwner = true;
        g4.getEffects().addDrone(clone);
        check(clone.effectiveStats() == o4.getStats(), "mirror drone copies the owner's current stats");
        g4.sellTower(o4);
        g4.run(2);
        check(g4.getEffects().getDrones().isEmpty(), "drones disappear with their owner");
    }

    private static void barrage() {
        Game g = frozen();
        Tower src = farTower(g, TowerType.KAIJU_KAI);
        List<Enemy> cluster = new ArrayList<>();
        for (int i = 0; i < 4; i++) cluster.add(at(g, EnemyType.TIMSORT, 500 + i * 12));
        Enemy lone = at(g, EnemyType.TIMSORT, 800);
        HitSpec h = new HitSpec(2, DamageType.EXPLOSIVE);
        Barrage b = new Barrage(src, h, 3, 50);
        b.aim = Barrage.Aim.DENSEST; b.stagger = 0.2;
        Vec aim = g.getEffects().fire(b);
        check(aim != null && aim.dist(cluster.get(0).getPosition()) < 60, "barrage aims at the densest cluster");
        runSeconds(g, 0.1);
        int landed1 = cluster.get(1).getMaxHp() > cluster.get(1).getHp() ? 1 : 0;
        runSeconds(g, 1.0);
        check(cluster.get(1).getHp() == cluster.get(1).getMaxHp() - 6, "3 shells x 2 damage land on the cluster (splash), hp lost " + (cluster.get(1).getMaxHp() - cluster.get(1).getHp()));
        check(landed1 == 1, "first shell lands immediately, others staggered");
        check(lone.getHp() == lone.getMaxHp(), "the lone enemy is not hit");
        // boss preferred
        Game g2 = frozen();
        Tower s2 = farTower(g2, TowerType.KAIJU_KAI);
        for (int i = 0; i < 4; i++) at(g2, EnemyType.TIMSORT, 500 + i * 12);
        Enemy boss = at(g2, EnemyType.BELLARMINE_COLLEGE_PREP, 900);
        HitSpec bh = new HitSpec(25, DamageType.EXPLOSIVE); bh.multVsBoss = 3;
        Barrage b2 = new Barrage(s2, bh, 5, 90);
        b2.aim = Barrage.Aim.BOSS_ELSE_DENSEST; b2.stagger = 0.05;
        Vec aim2 = g2.getEffects().fire(b2);
        check(aim2.dist(boss.getPosition()) < 1, "BOSS_ELSE_DENSEST aims at the boss when present");
        runSeconds(g2, 1);
        double expected = 5 * 25 * 3 * (1 - EnemyType.BELLARMINE_COLLEGE_PREP.getArmor());
        check(Math.abs((boss.getMaxHp() - boss.getHp()) - expected) < 1e-6, "5 shells x25 x3 vs MOAB with armour = " + expected + ", got " + (boss.getMaxHp() - boss.getHp()));
        // explosive barrage cannot pop camo without detection
        Game g3 = frozen();
        Tower s3 = farTower(g3, TowerType.GPT);
        Enemy camo = spawnAt(g3, EnemyType.TIMSORT, EnumSet.of(Modifier.CAMO), 0, 500);
        Barrage b3 = new Barrage(s3, new HitSpec(5, DamageType.EXPLOSIVE), 1, 50);
        b3.aim = Barrage.Aim.POINT; b3.point = camo.getPosition(); b3.stagger = 0;
        g3.getEffects().fire(b3);
        g3.run(2);
        check(camo.getHp() == camo.getMaxHp(), "explosive barrage cannot damage Camo without detection");
        Barrage b4 = new Barrage(s3, new HitSpec(5, DamageType.EXPLOSIVE), 1, 50);
        b4.aim = Barrage.Aim.POINT; b4.point = camo.getPosition(); b4.stagger = 0; b4.detection = true;
        g3.getEffects().fire(b4);
        g3.run(2);
        check(camo.getHp() == camo.getMaxHp() - 5, "with detection the barrage pops camo");
        check(g3.getEffects().fire(new Barrage(s3, new HitSpec(1, DamageType.ENERGY), 1, 10)) != null, "(densest aim with enemies present returns a point)");
        Game empty = frozen();
        check(empty.getEffects().fire(new Barrage(null, new HitSpec(1, DamageType.ENERGY), 1, 10)) == null, "no target, no barrage");
    }

    private static void nodeHazard() {
        Game g = frozen();
        Path r = route(g);
        Vec a = r.positionAt(400), b = r.positionAt(400);
        Enemy on = at(g, EnemyType.TIMSORT, 400), off = at(g, EnemyType.TIMSORT, 700);
        Vec n1 = on.getPosition().add(new Vec(-30, -30)), n2 = on.getPosition().add(new Vec(30, 30));
        NodeHazard h = NodeHazard.line(null, n1, n2, new HitSpec(2, DamageType.GRAVITY), 0.3);
        g.getEffects().addHazard(h);
        check(a.dist(b) == 0 && h.distanceToLinks(on.getPosition()) < 1, "enemy sits on the laser link");
        runSeconds(g, 1.0);
        double lost = on.getMaxHp() - on.getHp();
        check(lost >= 6 && lost <= 8, "link damages at most once per 0.3 s (~4 hits of 2): " + lost);
        check(off.getHp() == off.getMaxHp(), "enemies away from the link are untouched");
        // polygon slow
        Game g2 = frozen();
        Enemy inside = at(g2, EnemyType.TIMSORT, 400);
        Vec c = inside.getPosition();
        List<Vec> poly = Arrays.asList(c.add(new Vec(-60, -60)), c.add(new Vec(60, -60)), c.add(new Vec(60, 60)), c.add(new Vec(-60, 60)));
        Enemy outside = at(g2, EnemyType.TIMSORT, 900);
        NodeHazard net = NodeHazard.network(null, poly, new HitSpec(5, DamageType.GRAVITY), 0.3, 0.3);
        g2.getEffects().addHazard(net);
        check(NodeHazard.polygonContains(poly, c) && !NodeHazard.polygonContains(poly, c.add(new Vec(100, 0))), "point-in-polygon test");
        g2.run(10);
        check(Math.abs(inside.getSlowFraction() - 0.3) < 1e-9 && outside.getSlowFraction() == 0, "grid region slows enemies inside it");
        check(net.links.size() == 4 && net.nodes.size() == 4, "4 nodes form a closed grid of 4 links");
    }

    private static void enemyReverse() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(1);
        Tower src = farTower(g, TowerType.COHERE);
        Enemy rev = at(g, EnemyType.QUICK_SORT, 500);
        Enemy victim = at(g, EnemyType.TIMSORT, 480);
        Enemy farAway = at(g, EnemyType.TIMSORT, 900);
        rev.startReverse(2, 3, src);
        double before = rev.getDistance();
        runSeconds(g, 1.0);
        check(rev.getDistance() < before - 20, "reversed enemy walks backwards, d=" + rev.getDistance());
        check(victim.getHp() < victim.getMaxHp(), "reversed enemy damages those it touches");
        check(farAway.getHp() == farAway.getMaxHp(), "...and only those");
        check(src.getDamageDealt() > 0, "contact damage is credited to the override's tower");
        runSeconds(g, 1.5);
        double mid = rev.getDistance();
        runSeconds(g, 1.0);
        check(rev.getDistance() > mid, "enemy resumes normal movement after the reversal ends");
        Enemy atStart = at(g, EnemyType.QUICK_SORT, 2);
        atStart.startReverse(3, 0, null);
        runSeconds(g, 1);
        check(atStart.getDistance() >= 0, "reverse never leaves the start of the path");
    }

    private static void enemyRewindHold() {
        Game g = frozen();
        Enemy e = at(g, EnemyType.QUICK_SORT, 600);
        double px = e.rewind(3);
        check(Math.abs(px - e.nominalSpeed() * 3) < 1e-6 && Math.abs(e.getDistance() - (600 - px)) < 1e-6, "rewind 3 s = 3 s of own travel distance");
        Enemy fast = at(g, EnemyType.SINGLY_LINKED_LIST, 600);
        fast.rewind(1);
        check(600 - fast.getDistance() > e.nominalSpeed(), "faster enemies rewind further");
        Enemy near = at(g, EnemyType.QUICK_SORT, 5);
        near.rewind(10);
        check(near.getDistance() == 0, "rewind clamps at the path start");
        Enemy boss = at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 600);
        boss.rewind(1);
        check(Math.abs(600 - boss.getDistance() - boss.nominalSpeed()) < 1e-6, "bosses rewind by 1 s of their own travel");
        // hold / pull
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(1);
        Enemy h = at(g2, EnemyType.QUICK_SORT, 500);
        check(h.hold(2, 560, 100), "hold accepted");
        runSeconds(g2, 1.0);
        check(Math.abs(h.getDistance() - 560) < 1e-6 && h.currentSpeed(1) == 0, "held enemy is pulled to the vortex and stops");
        runSeconds(g2, 1.2);
        check(!h.isHeld(), "hold ends");
        double d = h.getDistance();
        runSeconds(g2, 0.5);
        check(h.getDistance() > d, "released enemy moves again");
        Enemy pal = at(g2, EnemyType.PALANTIR, 400);
        check(!pal.hold(2, 450, 100), "control-immune Palantir cannot be held");
    }

    private static void enemyDestroyStrip() {
        Game g = frozen();
        Tower t = farTower(g, TowerType.COHERE);
        double c0 = g.getCash();
        Enemy parent = at(g, EnemyType.STATIC_ARRAY, 500);
        g.getEnemyManager().destroyWithoutChildren(parent, t);
        g.getEnemyManager().update(0);
        check(!parent.isAlive() && g.getEnemyManager().countOfType(EnemyType.PRIMITIVE_VARIABLE) == 0, "destroyed without children");
        double pay = Math.round(EnemyType.STATIC_ARRAY.reward * g.getRewardScale());
        check(g.getCash() == c0 + pay, "parent's cash is paid once");
        check(t.getKills() == 1, "kill credited to the tower");
        g.getEnemyManager().destroyWithoutChildren(parent, t);
        check(g.getCash() == c0 + pay, "no double payment");
        Enemy tim = at(g, EnemyType.TIMSORT, 500);
        g.getEnemyManager().destroyWithoutChildren(tim, null);
        g.getEnemyManager().update(0);
        check(g.getEnemyManager().countOfType(EnemyType.MERGE_SORT) == 0 && g.getEnemyManager().countOfType(EnemyType.INSERTION_SORT) == 0, "TimSort's children never spawn");
        // strip camo/regrow
        Enemy cr = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO, Modifier.REGROW), 0, 500);
        check(cr.stripCamoRegrow() && !cr.isCamo() && !cr.isRegrow(), "Camo and Regrow permanently removed from non-bosses");
        Enemy ddt = at(g, EnemyType.LOCKHEED_MARTIN, 500);
        check(!ddt.stripCamoRegrow() && ddt.isCamo(), "bosses keep Camo");
        // strip fortified
        Enemy f = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 500);
        double mx = f.getMaxHp();
        check(f.stripFortified() && !f.isFortified() && f.getMaxHp() == mx / 2 && f.getHp() <= f.getMaxHp(), "Fortified removed, HP back to normal");
    }

    private static void palantirShield() {
        Game g = frozen();
        Boss pal = (Boss) at(g, EnemyType.PALANTIR, 500);
        check(pal.isControlImmune() && Math.abs(pal.effectiveArmor() - 0.60) < 1e-9, "phase 1 shield: control immune, armour 60%");
        pal.disablePhaseShield(10);
        check(!pal.isControlImmune() && pal.effectiveArmor() == 0 && pal.isPhaseShieldDown(), "shield off: no immunity, no armour");
        check(pal.applyStatus(StatusEffect.Kind.SLOW, 0.5, 2), "controls land while the shield is down");
        runSeconds(g, 10.5);
        check(pal.isControlImmune() && Math.abs(pal.effectiveArmor() - 0.60) < 1e-9, "shield returns after 10 s");
        Boss moab = (Boss) at(g, EnemyType.BELLARMINE_COLLEGE_PREP, 500);
        moab.disablePhaseShield(10);
        check(!moab.isPhaseShieldDown() && Math.abs(moab.effectiveArmor() - 0.25) < 1e-9, "other bosses are unaffected");
    }

    private static void counters() {
        Game g = frozen();
        Tower t = towerNearTrack(g, TowerType.KIMI, 1, 300);
        check(t.counter("x") == 0 && t.addCounter("x", 2) == 2 && t.counter("x") == 2, "named counters");
        check(t.registerStreak(7) == 0 && t.registerStreak(7) == 1 && t.registerStreak(7) == 2, "streak counts consecutive hits on one target");
        check(t.registerStreak(8) == 0 && t.registerStreak(7) == 0, "switching targets resets the streak");
        int ticks = 0;
        while (!t.periodic("p", 0.5, Game.DT)) ticks++;
        check(ticks >= 28 && ticks <= 30, "periodic fires after the interval: " + ticks);
        for (int i = 0; i < 99; i++) t.addKill();
        check(KimiBehavior.memoryStacks(t) == 0, "99 pops = no memory bonus yet");
        t.addKill();
        check(KimiBehavior.memoryStacks(t) == 1, "100 pops = +1");
        for (int i = 0; i < 2000; i++) t.addKill();
        check(KimiBehavior.memoryStacks(t) == 5, "memory capped at +5 at U1");
        Enemy e = at(g, EnemyType.PRIMITIVE_VARIABLE, 500);
        Tower k2 = towerNearTrack(g, TowerType.KIMI, 0, 500);
        int kills = k2.getKills();
        g.getCombat().applyHit(e, new HitSpec(100, DamageType.MAGIC), k2, 1, 0);
        g.getEnemyManager().update(0);
        check(k2.getKills() == kills + 1, "pops are counted on the tower that landed the final blow");
    }

    private static void roundIncome() {
        Game g = newGame(0);
        Tower p = towerNearTrack(g, TowerType.PERPLEXITY, 0, 300);
        double c = g.getCash();
        g.onWaveCompleted(1, WaveData.get(1));
        check(Math.abs(g.getCash() - (c + WaveData.waveBonus(1) + 40)) < 1e-9, "Perplexity pays +$40 at the end of a round");
        g.upgradeTower(p); g.upgradeTower(p);
        check(p.getStats().incomePerWave == 40, "U1/U2 keep $40");
        g.upgradeTower(p);
        c = g.getCash();
        g.onWaveCompleted(2, WaveData.get(2));
        check(Math.abs(g.getCash() - (c + WaveData.waveBonus(2) + 250)) < 1e-9, "Perplexity U3 pays +$250");
    }

    private static void scheduleAndOwnerCleanup() {
        Game g = frozen();
        int[] ran = { 0 };
        g.getEffects().schedule(0.5, () -> ran[0]++);
        runSeconds(g, 0.4);
        check(ran[0] == 0, "scheduled task waits");
        runSeconds(g, 0.2);
        check(ran[0] == 1, "scheduled task runs once");
        runSeconds(g, 1);
        check(ran[0] == 1, "...and only once");
        Effects.TrackPoint snap = g.getEffects().nearestTrackPoint(route(g).positionAt(400).add(new Vec(0, 30)));
        check(snap != null && snap.position.dist(route(g).positionAt(snap.distance)) < 1e-6 && snap.routeIndex >= 0, "nearest track point snaps onto a route");
        Tower t = towerNearTrack(g, TowerType.MISTRAL, 0, 300);
        List<Effects.TrackPoint> bends = g.getEffects().bendsInRange(t.getPosition(), 1500);
        check(!bends.isEmpty() && bends.get(0).position.distSq(t.getPosition()) <= bends.get(bends.size() - 1).position.distSq(t.getPosition()), "bends are listed nearest first");
    }
}
