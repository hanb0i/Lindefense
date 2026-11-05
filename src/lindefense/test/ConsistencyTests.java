package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.List;
import java.util.function.ToDoubleFunction;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.effects.Barrage;
import lindefense.effects.Drone;
import lindefense.effects.NodeHazard;
import lindefense.effects.TrackWalker;
import lindefense.effects.TrackZone;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AttackKind;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Phase C2b regressions: the difficulty's global tower-damage multiplier reaches every damage source (track zones,
 * walkers, node hazards, drones, barrages, as it does direct hits), and the enemy list never holds an enemy twice.
 */
public final class ConsistencyTests {
    private ConsistencyTests() { }

    public static void runAll() {
        run("c2b.globalDamageMultiplierEverywhere", ConsistencyTests::globalDamageMultiplierEverywhere);
        run("c2b.noDuplicateEnemiesAfterCarrierDies", ConsistencyTests::noDuplicateEnemiesAfterCarrierDies);
        run("c2b.gridHelpersMatchFullScan", ConsistencyTests::gridHelpersMatchFullScan);
    }

    private static Game frozen(Difficulty d) {
        Game g = new Game(MapCatalog.create(0), 42, d);
        g.setGlobalEnemySpeedMultiplier(0);
        return g;
    }

    private static double lost(Enemy e) { return e.getMaxHp() - e.getHp(); }

    /** Runs {@code scenario} on O(1) and O(N^N) and checks the damage ratio equals the difficulty's multiplier. */
    private static void ratio(String what, ToDoubleFunction<Game> scenario) {
        double base = scenario.applyAsDouble(frozen(Difficulty.O1));
        double hard = scenario.applyAsDouble(frozen(Difficulty.ONN));
        check(base > 0, what + ": deals damage at O(1) (" + base + ")");
        check(Math.abs(hard - base * Difficulty.ONN.towerDamage) < 1e-9 * Math.max(1, base),
            what + ": O(N^N) damage " + hard + " = O(1) damage " + base + " x " + Difficulty.ONN.towerDamage);
    }

    private static void globalDamageMultiplierEverywhere() {
        check(Difficulty.ONN.towerDamage == 0.84, "O(N^N) tower damage is x0.84");
        // reference: a direct tower hit
        ratio("direct hit", g -> {
            Tower t = towerNearTrack(g, TowerType.GPT, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            g.getCombat().applyHit(e, new HitSpec(4, DamageType.TRUE), t, t.damageMultiplier(g), 0);
            return lost(e);
        });
        ratio("track zone tick", g -> {
            Tower t = towerNearTrack(g, TowerType.GPT, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            TrackZone z = new TrackZone(e.getPosition(), 40, t);
            z.duration = 5; z.tickInterval = 0.5; z.tickHit = new HitSpec(2, DamageType.TRUE);
            g.getEffects().addZone(z);
            runSeconds(g, 1.2);
            return lost(e);
        });
        ratio("track walker", g -> {
            Tower t = towerNearTrack(g, TowerType.GPT, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            Path r = g.getMap().getRoutes().get(0);
            g.getEffects().addWalker(new TrackWalker(r, 290, 320, 100, t, new HitSpec(4, DamageType.TRUE)));
            runSeconds(g, 0.6);
            return lost(e);
        });
        ratio("node hazard (GLM line)", g -> {
            Tower t = towerNearTrack(g, TowerType.GLM, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            Vec p = e.getPosition();
            g.getEffects().addHazard(NodeHazard.line(t, p.add(new Vec(-30, -30)), p.add(new Vec(30, 30)), new HitSpec(4, DamageType.TRUE), 10));
            runSeconds(g, 0.3);
            return lost(e);
        });
        ratio("drone", g -> {
            Tower t = towerNearTrack(g, TowerType.GPT, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            Drone d = Drone.orbit(t, Drone.statsFor(AttackKind.INSTANT, 600, 5, 4, DamageType.TRUE, 1, 0), 30, 0);
            g.getEffects().addDrone(d);
            runSeconds(g, 0.3);
            return lost(e);
        });
        ratio("barrage", g -> {
            Tower t = towerNearTrack(g, TowerType.GPT, 0, 300);
            Enemy e = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 300);
            Barrage b = new Barrage(t, new HitSpec(4, DamageType.TRUE), 1, 60);
            b.stagger = 0;
            g.getEffects().fire(b);
            return lost(e);
        });
    }

    private static void noDuplicateEnemiesAfterCarrierDies() {
        Game g = frozen(Difficulty.O1);
        Enemy carrier = spawnAt(g, EnemyType.BUCKET_SORT, null, 0, 300);
        Enemy small = spawnAt(g, EnemyType.values()[0], null, 0, 310);
        // find a stored candidate: any non-boss with baseHp <= 5 that is not a carrier
        for (EnemyType t : EnemyType.values()) {
            if (!t.isBoss() && t.baseHp <= 5 && t != EnemyType.BUCKET_SORT) { small = spawnAt(g, t, null, 0, 310); break; }
        }
        // the carrier stores the small enemy in its step 3 and is killed (hp <= 0) in step 4 of the same tick
        carrier.takeDamage(carrier.getHp() + 1, 0);
        g.getEnemyManager().update(0);
        List<Enemy> seen = new ArrayList<>();
        for (Enemy e : g.getEnemyManager().getEnemies()) {
            check(!seen.contains(e), "enemy " + e.getId() + " appears once in the live list");
            seen.add(e);
        }
        for (int i = 0; i < 3; i++) g.getEnemyManager().update(0.016);
        seen.clear();
        for (Enemy e : g.getEnemyManager().getEnemies()) {
            check(!seen.contains(e), "enemy " + e.getId() + " still appears once");
            seen.add(e);
        }
    }

    private static void gridHelpersMatchFullScan() {
        // the behaviours' radius queries (grid backed) return exactly what a scan of the whole list would
        Game g = frozen(Difficulty.O1);
        for (int i = 0; i < 60; i++) spawnAt(g, EnemyType.HEAP_SORT, null, i % g.getMap().getRoutes().size(), 40 + i * 17);
        Vec p = g.getMap().getRoutes().get(0).positionAt(400);
        for (double r : new double[] { 30, 90, 200, 700 }) {
            List<Enemy> want = new ArrayList<>();
            for (Enemy e : g.getEnemyManager().getEnemies()) if (e.isAlive() && !e.isStored() && e.getPosition().dist(p) <= r) want.add(e);
            List<Enemy> got = new ArrayList<>();
            for (Enemy e : g.getEnemyManager().getGrid().near(p.x, p.y, r, new ArrayList<>())) if (e.isAlive() && !e.isStored() && e.getPosition().dist(p) <= r) got.add(e);
            check(want.equals(got), "grid query radius " + r + " equals the full scan (" + got.size() + " of " + want.size() + ")");
        }
    }
}
