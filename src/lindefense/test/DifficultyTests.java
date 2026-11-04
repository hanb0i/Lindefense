package lindefense.test;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Headless tests for the "Difficulty Growth" modes. {@link #run()} is called from
 * {@code HeadlessTests}; it returns the list of failure messages (empty = all good).
 */
public final class DifficultyTests {
    private static final List<String> failures = new ArrayList<>();
    private static int checks;
    private static String current = "";

    private DifficultyTests() { }

    /** Number of assertions evaluated by the last {@link #run()}. */
    public static int checkCount() { return checks; }

    private static void check(boolean ok, String msg) {
        checks++;
        if (!ok) failures.add(current + ": " + msg);
    }

    private static void section(String name) { current = name; }

    /** Runs every difficulty test and returns failure messages. */
    public static List<String> run() {
        failures.clear();
        checks = 0;
        try {
            o1IsIdentical();
            multipliersApplied();
            shapingIsDeterministic();
            extraBossesScheduled();
            palantirAndVictory();
            stressLateWavesOnImpossible();
        } catch (Throwable t) {
            failures.add(current + ": exception " + t);
            t.printStackTrace(System.out);
        }
        return failures;
    }

    // ------------------------------------------------------------------ helpers
    private static Game game(Difficulty d, int map) { return new Game(MapCatalog.create(map), 42, d); }

    private static void toWave(Game g, int wave) {
        while (g.getWave() < wave) { g.getWaveManager().startNextWave(); if (g.getWave() < wave) g.getWaveManager().endWave(); }
    }

    private static void kill(Game g, Enemy e) {
        g.getCombat().applyHit(e, new HitSpec(1e12, DamageType.TRUE), null, 1, 0);
        g.getEnemyManager().update(0);
    }

    private static String sig(WaveDef d) {
        StringBuilder sb = new StringBuilder();
        for (SpawnGroup s : d.groups) sb.append(s.type).append('|').append(s.count).append('|').append(s.modifiers).append('|')
            .append(s.interval).append('|').append(s.startDelay).append('|').append(s.route).append(';');
        return sb.toString();
    }

    private static int bodies(WaveDef d) { return d.totalSpawns(); }

    // ------------------------------------------------------------------ tests
    private static void o1IsIdentical() {
        section("O1 regression");
        check(Difficulty.O1.isBase(), "O1 is the base mode");
        for (WaveDef d : WaveData.all()) {
            check(Difficulty.O1.shape(d, 42) == d, "O1 returns the very same wave object, wave " + d.number);
            check(Difficulty.O1.shape(d, 7) == d, "O1 ignores the seed");
        }
        Game g = game(Difficulty.O1, 0);
        check(g.getCash() == Game.START_CASH && g.getLives() == Game.START_LIVES, "O1 start cash / lives unchanged");
        check(g.getGlobalDamageMultiplier() == 1.0, "O1 tower damage x1");
        check(Difficulty.defaultMode() == Difficulty.O1 || System.getProperty(Difficulty.PROPERTY) != null, "default mode is O1 without the property");
        // The default constructor is the O1 game.
        Game def = new Game(MapCatalog.create(0), 42);
        check(def.getDifficulty() == Difficulty.defaultMode(), "two-arg constructor uses the default mode");
        if (def.getDifficulty() != Difficulty.O1) return;   // property overrides below only make sense for the base game
        for (int w : new int[] { 1, 10, 40, 41, 60, 80, 99, 100 }) {
            Game a = game(Difficulty.O1, 1);
            toWave(a, w);
            check(a.getWaveHpScale() == WaveData.hpScale(w), "O1 hp scale wave " + w);
            check(a.getRewardScale() == WaveData.rewardScale(w), "O1 reward scale wave " + w);
            Enemy e = a.getEnemyManager().spawn(EnemyType.QUICK_SORT, null, 0, 0);
            check(e.getMaxHp() == Math.max(1, Math.round(EnemyType.QUICK_SORT.baseHp * WaveData.hpScale(w))), "O1 enemy HP wave " + w);
        }
        // Spawn real waves in O1 and compare against the data table.
        for (int wave : new int[] { 3, 10, 20, 50, 70 }) {
            Game a = game(Difficulty.O1, 0);
            a.setGlobalEnemySpeedMultiplier(0);
            toWave(a, wave - 1);
            a.getWaveManager().endWave();
            a.startNextWave();
            WaveDef want = WaveData.get(wave);
            check(a.getWaveManager().getCurrentDef() == want, "O1 wave " + wave + " uses the table definition");
            check(a.getWaveManager().getRemainingToSpawn() == want.totalSpawns(), "O1 wave " + wave + " spawn total");
        }
        // Income: wave bonus and kill reward identical to the table
        Game b = game(Difficulty.O1, 0);
        toWave(b, 30);
        double c0 = b.getCash();
        b.onWaveCompleted(30, WaveData.get(30));
        check(b.getCash() - c0 == WaveData.waveBonus(30), "O1 wave bonus unchanged");
    }

    private static void multipliersApplied() {
        section("multipliers");
        for (Difficulty d : new Difficulty[] { Difficulty.ON, Difficulty.ON2, Difficulty.ONN }) {
            int w = 60;
            Game g = game(d, 0);
            toWave(g, w);
            Game base = game(Difficulty.O1, 0);
            toWave(base, w);
            double hpM = d.hpMultiplier(w);
            check(Math.abs(g.getWaveHpScale() - WaveData.hpScale(w) * hpM) < 1e-9, d + " hp scale = base x " + hpM);
            check(hpM > 1, d + " hp multiplier > 1");
            Enemy e = g.getEnemyManager().spawn(EnemyType.QUICK_SORT, null, 0, 0);
            Enemy eb = base.getEnemyManager().spawn(EnemyType.QUICK_SORT, null, 0, 0);
            check(e.getMaxHp() == Math.max(1, Math.round(EnemyType.QUICK_SORT.baseHp * WaveData.hpScale(w) * hpM)), d + " enemy max HP scaled");
            check(e.getMaxHp() > eb.getMaxHp(), d + " enemy has more HP than O1");
            // Palantir is damage-compensated, not raw-multiplied
            check(Math.abs(g.getWaveHpScale(EnemyType.PALANTIR) - WaveData.hpScale(w) * d.palantirHp()) < 1e-9, d + " Palantir HP uses its special multiplier");

            // kill reward
            g.getEnemyManager().update(0);
            double c0 = g.getCash();
            kill(g, e);
            double wantReward = Math.round(EnemyType.QUICK_SORT.reward * WaveData.rewardScale(w) * d.income);
            check(g.getCash() - c0 == wantReward, d + " kill reward x" + d.income + ": got " + (g.getCash() - c0) + " want " + wantReward);
            check(d.income < 1, d + " income reduced");

            // wave bonus
            double c1 = g.getCash();
            g.onWaveCompleted(w, WaveData.get(w));
            check(g.getCash() - c1 == Math.round(WaveData.waveBonus(w) * d.income), d + " wave bonus scaled");

            // tower damage
            Vec p = new Vec(400, 250);
            Vec spot = findSpot(g, p), spotB = findSpot(base, p);
            Tower t = g.getTowerManager().place(TowerType.GPT, spot == null ? p : spot);
            Tower tb = base.getTowerManager().place(TowerType.GPT, spotB == null ? p : spotB);
            if (t != null && tb != null) {
                check(Math.abs(t.damageMultiplier(g) / tb.damageMultiplier(base) - d.towerDamage) < 1e-9, d + " tower damage multiplier x" + d.towerDamage);
            } else check(false, d + " could not place test towers");
            check(d.towerDamage < 1, d + " tower damage reduced");
        }
        // monotone difficulty ladder
        Difficulty[] ds = Difficulty.values();
        for (int i = 1; i < ds.length; i++) {
            check(ds[i].hpMultiplier(100) > ds[i - 1].hpMultiplier(100), ds[i] + " HP at wave 100 above " + ds[i - 1]);
            check(ds[i].towerDamage < ds[i - 1].towerDamage, ds[i] + " tower damage below " + ds[i - 1]);
            check(ds[i].income < ds[i - 1].income, ds[i] + " income below " + ds[i - 1]);
            check(ds[i].countMultiplier(100) > ds[i - 1].countMultiplier(100), ds[i] + " count above " + ds[i - 1]);
            check(ds[i].eliteChance(100) >= ds[i - 1].eliteChance(100), ds[i] + " elites at least " + ds[i - 1]);
        }
        // growth curves: shape of the name, normalised to 1 at wave 100
        for (Difficulty d : ds) {
            if (d.curve == Difficulty.Curve.FLAT) { check(d.growth(50) == 0, d + " flat"); continue; }
            check(Math.abs(d.growth(100) - 1) < 1e-9, d + " growth is 1 at wave 100");
            check(d.growth(10) < d.growth(50) && d.growth(50) < d.growth(90), d + " growth is increasing");
        }
        check(Math.abs(Difficulty.ON.growth(50) - 0.5) < 1e-9, "O(N) is linear");
        check(Math.abs(Difficulty.ON2.growth(50) - 0.25) < 1e-9, "O(N^2) is quadratic");
        check(Difficulty.ONN.growth(50) < Difficulty.ON2.growth(50), "O(N^N) back-loaded");
        check(Difficulty.parse("O(N^2)") == Difficulty.ON2 && Difficulty.parse("onn") == Difficulty.ONN && Difficulty.parse("O1") == Difficulty.O1
            && Difficulty.parse("O(N²)") == Difficulty.ON2 && Difficulty.parse("zzz") == null, "difficulty parsing");
    }

    private static Vec findSpot(Game g, Vec target) {
        for (double r = 0; r <= 300; r += 10) {
            for (int a = 0; a < 24; a++) {
                Vec p = new Vec(target.x + Math.cos(a * Math.PI / 12) * r, target.y + Math.sin(a * Math.PI / 12) * r);
                if (g.getTowerManager().canPlace(TowerType.GPT, p)) return p;
            }
        }
        return null;
    }

    private static void shapingIsDeterministic() {
        section("shaping determinism");
        for (Difficulty d : new Difficulty[] { Difficulty.ON, Difficulty.ON2, Difficulty.ONN }) {
            boolean anySeedDiffers = false;
            int elitesSeen = 0;
            for (WaveDef base : WaveData.all()) {
                WaveDef a = d.shape(base, 42), b = d.shape(base, 42);
                check(sig(a).equals(sig(b)), d + " wave " + base.number + " deterministic for the same seed");
                if (!sig(a).equals(sig(d.shape(base, 43)))) anySeedDiffers = true;
                // Bosses already in the wave are never multiplied; non-boss enemies never drop below the base total.
                int baseNonBoss = 0, newNonBoss = 0;
                for (SpawnGroup s : base.groups) if (!s.type.isBoss()) baseNonBoss += s.count;
                for (SpawnGroup s : a.groups) if (!s.type.isBoss()) newNonBoss += s.count;
                check(newNonBoss >= baseNonBoss, d + " wave " + base.number + " never has fewer non-boss enemies");
                double cm = d.countMultiplier(base.number);
                for (SpawnGroup bg : base.groups) {
                    if (bg.type.isBoss()) continue;
                    check(newNonBoss <= Math.ceil(baseNonBoss * cm) + base.groups.size() + 1, d + " wave " + base.number + " count within rounding of x" + cm);
                    break;
                }
                for (SpawnGroup s : a.groups) {
                    if (s.type.isBoss()) continue;
                    // elite groups have strictly more modifiers than some base group of the same (or promoted) lineage
                    boolean isBaseGroup = false;
                    for (SpawnGroup bg : base.groups) if (bg.type == s.type && bg.modifiers.equals(s.modifiers)) isBaseGroup = true;
                    if (!isBaseGroup) elitesSeen += s.count;
                    check(s.count >= 1 && s.interval > 0 && s.startDelay >= 0, d + " wave " + base.number + " sane group values");
                }
                check(a.contains(EnemyType.PALANTIR) == base.contains(EnemyType.PALANTIR), d + " Palantir presence unchanged on wave " + base.number);
            }
            check(anySeedDiffers, d + " output depends on the seed");
            if (d == Difficulty.ON) check(elitesSeen == 0 || elitesSeen > 0, "O(N) elites optional");
            if (d == Difficulty.ON) check(d.eliteChance(100) == 0, "O(N) has no elites");
            else check(elitesSeen > 0, d + " produces elite groups (" + elitesSeen + ")");
        }
        // Elites carry extra modifiers
        WaveDef w90 = Difficulty.ONN.shape(WaveData.get(90), 42);
        boolean eliteHasMore = false;
        for (SpawnGroup s : w90.groups) {
            if (s.type.isBoss()) continue;
            for (SpawnGroup bg : WaveData.get(90).groups) if (bg.type == s.type && s.modifiers.size() > bg.modifiers.size()) eliteHasMore = true;
        }
        check(eliteHasMore, "O(N^N) wave 90 elites have extra modifiers");
        // Same seed in a live game gives the same spawn plan
        Game a = game(Difficulty.ON2, 0), b = game(Difficulty.ON2, 0);
        toWave(a, 49); toWave(b, 49);
        a.getWaveManager().endWave(); b.getWaveManager().endWave();
        a.startNextWave(); b.startNextWave();
        check(sig(a.getWaveManager().getCurrentDef()).equals(sig(b.getWaveManager().getCurrentDef())), "same seed -> same live wave plan");
        check(a.getWaveManager().getRemainingToSpawn() == a.getWaveManager().getCurrentDef().totalSpawns(), "live wave spawn total matches the shaped definition");
    }

    private static void extraBossesScheduled() {
        section("extra bosses");
        check(Difficulty.O1.getExtraBosses().isEmpty() && Difficulty.ON.getExtraBosses().isEmpty() && Difficulty.ON2.getExtraBosses().isEmpty(),
            "only O(N^N) has extra bosses");
        check(Difficulty.ONN.getExtraBosses().size() >= 10, "O(N^N) has a boss schedule");
        for (Difficulty.ExtraBoss b : Difficulty.ONN.getExtraBosses()) {
            WaveDef base = WaveData.get(b.wave), shaped = Difficulty.ONN.shape(base, 42);
            check(b.type.isBoss() && b.type != EnemyType.PALANTIR, "extra boss at wave " + b.wave + " is a non-final boss");
            check(shaped.countOf(b.type) >= base.countOf(b.type) + b.count, "wave " + b.wave + " gained " + b.count + " x " + b.type);
        }
        // a wave with no scheduled boss does not gain any
        WaveDef w26 = Difficulty.ONN.shape(WaveData.get(26), 42);
        check(!w26.containsBoss(), "no bosses on unscheduled wave 26");

        // Live: wave 25 gets one extra MOAB which still splits into 4 Quick Sorts
        Game g = game(Difficulty.ONN, 0);
        g.setGlobalEnemySpeedMultiplier(0);
        toWave(g, 24);
        g.getWaveManager().endWave();
        g.startNextWave();
        for (int i = 0; i < 60 * 40; i++) g.step(Game.DT);
        check(g.getEnemyManager().countOfType(EnemyType.BELLARMINE_COLLEGE_PREP) == 1, "extra MOAB spawned on wave 25, got " + g.getEnemyManager().countOfType(EnemyType.BELLARMINE_COLLEGE_PREP));
        Enemy moab = null;
        for (Enemy e : g.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.BELLARMINE_COLLEGE_PREP) moab = e;
        check(moab instanceof Boss, "extra boss is a Boss instance");
        if (moab != null) {
            int qs = g.getEnemyManager().countOfType(EnemyType.QUICK_SORT);
            double hpScale = moab.getHpScale();
            kill(g, moab);
            g.getEnemyManager().update(0);
            check(g.getEnemyManager().countOfType(EnemyType.QUICK_SORT) == qs + 4, "extra MOAB splits into 4 Quick Sorts");
            check(g.getEnemyManager().countOfType(EnemyType.BELLARMINE_COLLEGE_PREP) == 0, "MOAB removed after the split");
            for (Enemy e : g.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.QUICK_SORT) { check(e.getHpScale() == hpScale, "children inherit the parent's HP scale"); break; }
        }
        // Fortified extra BFB (wave 85) splits into 3 fortified MOAB children
        Game f = game(Difficulty.ONN, 1);
        f.setGlobalEnemySpeedMultiplier(0);
        Enemy bfb = f.getEnemyManager().spawn(EnemyType.SW_RESOURCE_CONSULTANT, EnumSet.of(Modifier.FORTIFIED), 0, 0);
        f.getEnemyManager().update(0);
        kill(f, bfb);
        f.getEnemyManager().update(0);
        check(f.getEnemyManager().countOfType(EnemyType.BELLARMINE_COLLEGE_PREP) == 3, "BFB splits into 3 MOABs on O(N^N)");
        for (Enemy e : f.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.BELLARMINE_COLLEGE_PREP) check(e.isFortified(), "Fortified inherited by boss children");
    }

    private static void palantirAndVictory() {
        section("palantir & victory");
        for (Difficulty d : Difficulty.values()) {
            WaveDef w = d.shape(WaveData.get(100), 42);
            check(w.countOf(EnemyType.PALANTIR) == 1, d + " wave 100 contains exactly one Palantir");
        }
        for (Difficulty d : new Difficulty[] { Difficulty.O1, Difficulty.ON2, Difficulty.ONN }) {
            Game g = game(d, 2);
            g.setGlobalEnemySpeedMultiplier(0);
            toWave(g, 99);
            g.getWaveManager().endWave();
            g.startNextWave();
            check(g.getWave() == 100, d + " reached wave 100");
            g.run(60 * 10);
            Boss pal = g.getPalantir();
            check(pal != null && pal.isAlive(), d + " Palantir spawned");
            if (pal == null) continue;
            double expected = EnemyType.PALANTIR.baseHp * WaveData.hpScale(100) * (d.isBase() ? 1.0 : d.palantirHp());
            check(Math.abs(pal.getMaxHp() - Math.round(expected)) <= 1, d + " Palantir HP " + pal.getMaxHp() + " vs " + expected);
            kill(g, pal);
            check(g.isVictorySequenceActive(), d + " victory sequence starts");
            g.run((int) (Game.VICTORY_SEQUENCE_TIME / Game.DT) + 5);
            check(g.getState() == Game.State.VICTORY, d + " state VICTORY, got " + g.getState());
        }
    }

    private static void stressLateWavesOnImpossible() {
        section("stress O(N^N)");
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            Game g = game(Difficulty.ONN, m);
            g.setInvincible(true);
            g.setGlobalEnemySpeedMultiplier(0.5);
            g.addCash(400_000, null);
            TowerType[] types = { TowerType.KAIJU_KAI, TowerType.DEEPSEEK, TowerType.COHERE, TowerType.GEMINI, TowerType.SORA, TowerType.SUNO };
            int placed = 0;
            for (Path r : g.getMap().getRoutes()) {
                for (double dd = 100; dd < r.getTotalLength() && placed < 12; dd += 220) {
                    Vec base = r.positionAt(dd), dir = r.directionAt(dd);
                    for (int side = -1; side <= 1; side += 2) {
                        Vec p = base.add(new Vec(-dir.y, dir.x).scale(side * 70));
                        TowerType tt = types[placed % types.length];
                        if (g.getTowerManager().canPlace(tt, p)) { Tower t = g.placeTower(tt, p); g.upgradeTower(t); placed++; }
                    }
                }
            }
            toWave(g, 94);
            int peak = 0;
            for (int wave = 95; wave <= 100; wave++) {
                g.getWaveManager().endWave();
                g.getEnemyManager().clear();
                check(g.startNextWave(), "start wave " + wave + " on map " + m);
                int ticks = 0;
                while (g.getWaveManager().isWaveActive() && ticks < 60 * 120 && g.getState() == Game.State.PLAYING) {
                    g.step(Game.DT);
                    if (ticks % 120 == 0) for (Tower t : new ArrayList<>(g.getTowerManager().getTowers())) if (t.isAbilityReady()) g.activateAbility(t);
                    peak = Math.max(peak, g.getEnemyManager().getEnemies().size());
                    g.getEvents().clear();
                    ticks++;
                }
                if (g.getState() != Game.State.PLAYING) break;
            }
            check(peak > 20, "map " + m + " stress produced a real rush (peak " + peak + ")");
            check(g.getState() == Game.State.PLAYING || g.getState() == Game.State.VICTORY, "map " + m + " stress ended in a valid state " + g.getState());
        }
    }
}
