package lindefense.tools;

import acm.graphics.GCanvas;
import acm.graphics.GCompound;
import acm.graphics.GObject;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import javax.imageio.ImageIO;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;
import lindefense.ui.GameScreen;
import lindefense.ui.ScaledLayer;
import lindefense.ui.Ui;

/**
 * Reusable performance benchmark for "big fights": a headless simulation benchmark and an offscreen
 * rendering benchmark that drives the real UI ({@link GameScreen}, {@link lindefense.ui.WorldView}, the real
 * sprites) inside a real {@link GCanvas} and paints it into a {@link BufferedImage}, exactly like the demo
 * driver's snapshots. Nothing is ever shown on screen and nothing is screen-captured; the JVM runs with
 * {@code java.awt.headless=true} unless told otherwise.
 *
 * <h3>Scenarios</h3>
 * <ul>
 *   <li><b>sim</b>: on every map, a dense roster of maxed towers (all 20 types, cycled; heroes once) plays the
 *       late waves {@code perf.from..perf.to} for real (leaks never end the run). Abilities fire every second.
 *       Reports ms per {@link Game#step} (mean / p50 / p95 / p99 / max), enemy / projectile / effect counts,
 *       visual events per tick, bytes allocated per tick and GC activity, plus an outcome fingerprint
 *       (kills, leaks, cash, per-tower damage) that must be identical for identical code paths.</li>
 *   <li><b>siege</b> (part of sim): a real late wave plus a crowd kept at N enemies on every map, the worst case for
 *       targeting, collisions, splash, chains and statuses.</li>
 *   <li><b>render</b>: one map, the same dense maxed roster, and a crowd of exactly N enemies (mixed types and
 *       modifiers, a third of them killable so deaths and splits happen) kept topped up while the towers fire.
 *       Each frame runs {@code GameScreen.frame(1/60)} (one sim step plus the UI sync) and then paints the whole
 *       canvas. Reports update ms, paint ms and total ms per frame (mean / p95 / max), the number of live
 *       GObjects in the scene graph and bytes allocated per frame.</li>
 * </ul>
 *
 * <h3>Usage</h3>
 * <pre>
 *   java -cp build:lib/acm.jar lindefense.tools.PerfBench [sim|render|all]
 *   scripts/perfbench.sh [sim|render|all]           (builds first; PERF_JFR=1 adds a JFR recording + hot methods)
 * </pre>
 * Options (system properties): {@code perf.maps=0,1,2,3}, {@code perf.from=90}, {@code perf.to=100},
 * {@code perf.waveSeconds=30} (sim seconds per wave), {@code perf.towers=72} (roster size), {@code perf.seed=1234},
 * {@code perf.siege=400} (siege crowd size, 0 = skip), {@code perf.siegeWave=96}, {@code perf.siegeSeconds=20}, {@code perf.siegeHp=8},
 * {@code lindefense.difficulty=O1|ON|ON2|ONN}, {@code perf.enemies=150,300,600} (render crowd sizes),
 * {@code perf.frames=240}, {@code perf.renderMap=0}, {@code perf.size=1600x1000} (canvas pixels),
 * {@code perf.clock=cpu|wall} (default cpu: benchmark-thread CPU time, robust on a busy machine),
 * {@code perf.snap=<dir>} (PNG of the last frame of each render case), {@code perf.breakdown=true} (per-layer and
 * per-sprite-class paint cost of the final scene), {@code perf.warmup=true}.
 */
public final class PerfBench {
    private PerfBench() { }

    private static final com.sun.management.ThreadMXBean THREADS =
        (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
    /**
     * Clock for all timings: {@code cpu} (default) = CPU time of the benchmark thread, which other processes on a busy
     * machine do not inflate (GC work on other threads is excluded); {@code wall} = elapsed time.
     */
    private static final boolean CPU_CLOCK = !"wall".equals(System.getProperty("perf.clock", "cpu"));

    /** Bytes allocated by the calling thread so far (Java 11 compatible; 0 if the JVM cannot report it). */
    static long allocBytes() {
        return THREADS.isThreadAllocatedMemorySupported() ? THREADS.getThreadAllocatedBytes(Thread.currentThread().getId()) : 0L;
    }

    /** Current time in ns on the selected clock. */
    static long now() { return CPU_CLOCK ? THREADS.getCurrentThreadCpuTime() : System.nanoTime(); }

    public static void main(String[] args) throws Exception {
        if (System.getProperty("java.awt.headless") == null) System.setProperty("java.awt.headless", "true");
        String mode = args.length > 0 ? args[0] : "all";
        Difficulty diff = Difficulty.defaultMode();
        System.out.println("PerfBench  mode=" + mode + "  difficulty=" + diff.label + "  java=" + System.getProperty("java.version")
            + "  cpus=" + Runtime.getRuntime().availableProcessors() + "  heap=" + (Runtime.getRuntime().maxMemory() >> 20) + "MB"
            + "  clock=" + (CPU_CLOCK ? "thread-cpu" : "wall") + "  load=" + String.format("%.1f", ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage()));
        if (Boolean.parseBoolean(System.getProperty("perf.warmup", "true"))) warmUp(diff, mode);
        if (mode.equals("sim") || mode.equals("all")) simBench(diff);
        if (mode.equals("render") || mode.equals("all")) renderBench(diff);
    }

    // ------------------------------------------------------------------ scenario setup

    /**
     * Places up to {@code count} maxed towers on buildable spots closest to the track (44 px lattice, at most
     * 170 px from a route), cycling through all 20 purchasable types; heroes are placed once.
     */
    static int placeDenseRoster(Game g, int count) {
        g.addCash(50_000_000, null);
        GameMap map = g.getMap();
        List<double[]> spots = new ArrayList<>();
        for (int x = 30; x < GameMap.WIDTH - 20; x += 44) {
            for (int y = 30; y < GameMap.HEIGHT - 20; y += 44) {
                Vec p = new Vec(x, y);
                double best = Double.MAX_VALUE;
                for (Path r : map.getRoutes()) best = Math.min(best, r.distanceToPoint(p));
                if (best <= 170) spots.add(new double[] { best, x, y });
            }
        }
        spots.sort((a, b) -> a[0] != b[0] ? Double.compare(a[0], b[0]) : a[1] != b[1] ? Double.compare(a[1], b[1]) : Double.compare(a[2], b[2]));
        g.setHeroLimit(Integer.MAX_VALUE);   // benchmark: the whole roster at once
        g.setHeroCollection(lindefense.sim.HeroCollection.inMemory()); for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);   // tools never touch saved unlocks
        TowerType[] all = TowerType.purchasable();
        int placed = 0, typeIdx = 0;
        for (double[] s : spots) {
            if (placed >= count) break;
            Vec p = new Vec(s[1], s[2]);
            for (int tries = 0; tries < all.length; tries++) {
                TowerType t = all[(typeIdx + tries) % all.length];
                if (g.getTowerManager().placementProblem(t, p) != null) continue;
                Tower tw = g.placeTower(t, p);
                if (tw == null) continue;
                while (g.upgradeTower(tw)) { /* max out */ }
                g.unlockAbility(tw);   // and buy its ability, so ability effects are part of the benchmark
                placed++;
                typeIdx = (typeIdx + tries + 1) % all.length;
                break;
            }
        }
        return placed;
    }

    /** Builds a game on {@code mapIdx} with the dense roster and fast-forwards to just before wave {@code from}. */
    static Game lateGame(int mapIdx, Difficulty diff, int towers, int from) {
        Game g = new Game(MapCatalog.create(mapIdx), Long.getLong("perf.seed", 1234L), diff);
        g.setInvincible(true);
        placeDenseRoster(g, towers);
        for (int k = 1; k < from; k++) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
        return g;
    }

    /** Fires every ready ability (targeted ones at a fixed point on route 0), like the stress test. */
    static void fireAbilities(Game g) {
        for (Tower t : new ArrayList<>(g.getTowerManager().getTowers())) {
            if (!t.isAbilityReady() || t.isTemporary()) continue;
            if (t.getAbility().needsTarget) g.activateAbility(t, g.getMap().getRoutes().get(0).positionAt(400));
            else g.activateAbility(t);
        }
    }

    static int effectCount(Game g) {
        return g.getEffects().getZones().size() + g.getEffects().getWalkers().size()
            + g.getEffects().getDrones().size() + g.getEffects().getHazards().size();
    }

    private static void warmUp(Difficulty diff, String mode) {
        long t0 = System.nanoTime();
        Game g = lateGame(0, diff, Integer.getInteger("perf.towers", 72), 70);
        g.startNextWave();
        for (int i = 0; i < 1800 && g.getWaveManager().isWaveActive(); i++) {
            g.step(Game.DT);
            if (i % 60 == 0) fireAbilities(g);
            g.getEvents().clear();
        }
        if (mode.equals("render") || mode.equals("all")) {
            RenderRig rig = new RenderRig(lateGame(1, diff, 30, 95), 1200, 750);
            spawnCrowd(rig.game, 120, 0);
            for (int i = 0; i < 90; i++) { rig.screen.frame(1 / 60.0); rig.paint(); }
        }
        System.out.printf("warm-up done in %.1f s%n%n", (System.nanoTime() - t0) / 1e9);
    }

    // ------------------------------------------------------------------ sim benchmark

    private static final String SIM_HEADER = String.format("%-26s %6s %8s %7s %7s %7s %7s | %5s %5s %5s %5s %6s | %8s %6s | %s",
        "map", "ticks", "mean ms", "p50", "p95", "p99", "max", "enAvg", "enMax", "prMax", "fxMax", "ev/t", "KB/tick", "GCs", "fingerprint");

    /** Per-tick timing and load counters for one simulation run. */
    static final class SimRun {
        final Game g;
        final Stats st = new Stats();
        long enemySum, events;
        int enemyMax, projMax, fxMax;
        final long gc0 = gcCount();
        final long alloc0 = allocBytes();

        SimRun(Game g) { this.g = g; }

        /** One measured tick: abilities every second, then {@link Game#step}. */
        void tick(int tick) {
            long t0 = now();
            if (tick % 60 == 0) fireAbilities(g);
            g.step(Game.DT);
            st.add((now() - t0) / 1e6);
            int en = g.getEnemyManager().getEnemies().size();
            enemySum += en;
            enemyMax = Math.max(enemyMax, en);
            projMax = Math.max(projMax, g.getCombat().getProjectiles().size());
            fxMax = Math.max(fxMax, effectCount(g));
            events += g.getEvents().size();
            g.getEvents().clear();
        }

        String row() {
            long bytes = allocBytes() - alloc0;
            return String.format("%-26s %6d %8.3f %7.3f %7.3f %7.3f %7.2f | %5d %5d %5d %5d %6.1f | %8.1f %6d | %s",
                g.getMap().getName(), st.n, st.mean(), st.pct(50), st.pct(95), st.pct(99), st.max(),
                enemySum / Math.max(1, st.n), enemyMax, projMax, fxMax, events / (double) Math.max(1, st.n),
                bytes / 1024.0 / Math.max(1, st.n), gcCount() - gc0, fingerprint(g));
        }
    }

    private static void simBench(Difficulty diff) {
        int[] maps = intList(System.getProperty("perf.maps", "0,1,2,3"));
        int from = Integer.getInteger("perf.from", 90), to = Integer.getInteger("perf.to", 100);
        int waveTicks = (int) Math.round(Double.parseDouble(System.getProperty("perf.waveSeconds", "30")) / Game.DT);
        int towers = Integer.getInteger("perf.towers", 72);
        if (to >= from) {
            System.out.println("== SIM waves: waves " + from + "-" + to + ", up to " + (waveTicks * Game.DT) + " s each, dense maxed roster of " + towers
                + " towers, difficulty " + diff.label + " ==");
            System.out.println(SIM_HEADER);
            Stats all = new Stats();
            for (int m : maps) {
                SimRun run = new SimRun(lateGame(m, diff, towers, from));
                Game g = run.g;
                for (int wave = from; wave <= to; wave++) {
                    g.getWaveManager().endWave();
                    g.getEnemyManager().clear();
                    g.startNextWave();
                    for (int tick = 0; tick < waveTicks && g.getWaveManager().isWaveActive(); tick++) run.tick(tick);
                }
                all.addAll(run.st);
                System.out.println(run.row());
            }
            System.out.println(String.format("%-26s %6d %8.3f %7.3f %7.3f %7.3f %7.2f", "ALL MAPS", all.n, all.mean(), all.pct(50), all.pct(95), all.pct(99), all.max()));
            System.out.println();
        }
        siegeBench(diff, maps, towers);
    }

    /**
     * Siege: the worst case for "a bunch of stuff at once". Wave {@code perf.siegeWave} (default 96) runs for real while
     * a crowd is kept at {@code perf.siege} enemies (default 400; mixed types and modifiers, HP x{@code perf.siegeHp}
     * of the wave's scale, spread along every route), so hundreds of enemies, projectiles, splits and effects are alive
     * every tick. {@code perf.siegeSeconds} (default 20) of game time per map.
     */
    private static void siegeBench(Difficulty diff, int[] maps, int towers) {
        int crowd = Integer.getInteger("perf.siege", 400);
        if (crowd <= 0) return;
        int wave = Integer.getInteger("perf.siegeWave", 96);
        int ticks = (int) Math.round(Double.parseDouble(System.getProperty("perf.siegeSeconds", "20")) / Game.DT);
        double hpMult = Double.parseDouble(System.getProperty("perf.siegeHp", "8"));
        System.out.println("== SIM siege: wave " + wave + " + a crowd kept at " + crowd + " enemies (HP x" + hpMult + "), " + (ticks * Game.DT)
            + " s per map, " + towers + " maxed towers, difficulty " + diff.label + " ==");
        System.out.println(SIM_HEADER);
        Stats all = new Stats();
        for (int m : maps) {
            Game g = lateGame(m, diff, towers, wave);
            g.startNextWave();
            SimRun run = new SimRun(g);
            int salt = 0;
            for (int tick = 0; tick < ticks; tick++) {
                if (tick % 30 == 0) {
                    int alive = g.getEnemyManager().getEnemies().size();
                    if (alive < crowd) { siegeCrowd(g, crowd - alive, salt, hpMult); salt += crowd - alive; }
                }
                run.tick(tick);
            }
            all.addAll(run.st);
            System.out.println(run.row());
        }
        System.out.println(String.format("%-26s %6d %8.3f %7.3f %7.3f %7.3f %7.2f", "ALL MAPS", all.n, all.mean(), all.pct(50), all.pct(95), all.pct(99), all.max()));
        System.out.println();
    }

    /** Siege reinforcements: deterministic mix of types / modifiers, spread over the first 70% of every route. */
    static void siegeCrowd(Game g, int n, int salt, double hpMult) {
        List<Path> routes = g.getMap().getRoutes();
        for (int i = 0; i < n; i++) {
            int k = i + salt;
            EnemyType t = CROWD[k % CROWD.length];
            EnumSet<Modifier> mods = EnumSet.noneOf(Modifier.class);
            if (k % 5 == 1) mods.add(Modifier.CAMO);
            if (k % 7 == 2) mods.add(Modifier.REGROW);
            if (k % 6 == 3) mods.add(Modifier.FORTIFIED);
            int route = k % routes.size();
            Path r = routes.get(route);
            double d = r.getTotalLength() * 0.7 * ((k * 0.6180339887) % 1.0);
            g.getEnemyManager().spawnScaled(t, mods, route, d, g.getWaveHpScale(t) * hpMult, g.getWaveSpeedScale());
        }
    }

    /** Outcome fingerprint: identical simulation paths give identical values. */
    static String fingerprint(Game g) {
        long h = 0xcbf29ce484222325L;
        long[] vals = { g.getEnemyManager().getTotalKilled(), g.getEnemyManager().getTotalLeaked(), g.getEnemyManager().getTotalSpawned(),
            Double.doubleToLongBits(g.getCash()), g.getLives(), g.getTick() };
        for (long v : vals) { h ^= v; h *= 0x100000001b3L; }
        for (Tower t : g.getTowerManager().getTowers()) {
            h ^= Double.doubleToLongBits(t.getDamageDealt()); h *= 0x100000001b3L;
            h ^= t.getKills(); h *= 0x100000001b3L;
        }
        return String.format("k%d/l%d %016x", g.getEnemyManager().getTotalKilled(), g.getEnemyManager().getTotalLeaked(), h);
    }

    // ------------------------------------------------------------------ render benchmark

    /** The real UI stack (GCanvas -> ScaledLayer -> GameScreen) painted offscreen into a BufferedImage. */
    static final class RenderRig {
        final Game game;
        final GCanvas canvas = new GCanvas();
        final ScaledLayer root = new ScaledLayer();
        final GameScreen screen;
        final BufferedImage img;

        RenderRig(Game game, int w, int h) {
            this.game = game;
            canvas.setSize(w, h);
            canvas.setBackground(Ui.BG);
            configureLikeProgram(canvas);
            canvas.add(root);
            root.fit(w, h);
            screen = new GameScreen(null, game);
            root.add(screen);
            img = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        }

        /** Paints the whole canvas exactly like the demo driver's snapshot (GCanvas.paint into a Graphics2D). */
        void paint() {
            Graphics2D g2 = img.createGraphics();
            try { canvas.paint(g2); } finally { g2.dispose(); }
        }

        /** Mean paint time of the current scene over {@code k} paints (no updates in between). */
        double paintMs(int k) {
            long t0 = now();
            for (int i = 0; i < k; i++) paint();
            return (now() - t0) / 1e6 / k;
        }
    }

    /**
     * Applies the same canvas settings as the real program: {@code LindefenseProgram.configureCanvas(GCanvas)} when it
     * exists, otherwise the settings the program used before that hook existed (auto-repaint off). Reflection keeps
     * this benchmark source compilable against older revisions for before/after comparisons.
     */
    static void configureLikeProgram(GCanvas canvas) {
        try {
            Class.forName("lindefense.ui.LindefenseProgram").getMethod("configureCanvas", GCanvas.class).invoke(null, canvas);
        } catch (ReflectiveOperationException e) {
            canvas.setAutoRepaintFlag(false);
        }
    }

    /**
     * Prints what each part of the scene costs to paint: every top-level child of the GameScreen, every layer of the
     * WorldView, and the enemy / tower sprites grouped by class. Cost = full paint minus paint with that part hidden.
     */
    static void breakdown(RenderRig rig) {
        int k = Integer.getInteger("perf.breakdownReps", 24);
        rig.paintMs(3 * k);
        double full = rig.paintMs(k);
        System.out.printf("   breakdown (full paint %.2f ms; each cost = full paint around it minus paint without it):%n", full);
        GCompound world = null;
        List<GObject> leaves = new ArrayList<>();
        for (int i = 0; i < rig.screen.getElementCount(); i++) {
            GObject o = rig.screen.getElement(i);
            if (!(o instanceof GCompound) && o.isVisible()) leaves.add(o);
        }
        System.out.printf("     screen leaves  (%3d objs: backdrop rect, grid, brackets) %6.2f ms%n", leaves.size(), costOfHiding(rig, leaves, k));
        for (int i = 0; i < rig.screen.getElementCount(); i++) {
            GObject o = rig.screen.getElement(i);
            if (o instanceof lindefense.ui.WorldView) world = (GCompound) o;
            if (!(o instanceof GCompound) || !o.isVisible()) continue;
            double cost = costOfHiding(rig, java.util.Collections.singletonList(o), k);
            System.out.printf("     screen[%2d] %-14s %6.2f ms  (%d objs)%n", i, o.getClass().getSimpleName(), cost, countObjects((GCompound) o));
        }
        if (world == null) return;
        for (int i = 0; i < world.getElementCount(); i++) {
            GObject o = world.getElement(i);
            if (!o.isVisible()) continue;
            double cost = costOfHiding(rig, java.util.Collections.singletonList(o), k);
            int objs = o instanceof GCompound ? countObjects((GCompound) o) : 1;
            String first = o instanceof GCompound && ((GCompound) o).getElementCount() > 0 ? ((GCompound) o).getElement(0).getClass().getSimpleName() : "-";
            System.out.printf("     world[%d] (%4d objs, first %-22s) %6.2f ms%n", i, objs, first, cost);
            if (o instanceof GCompound && ((GCompound) o).getElementCount() > 20) byClass(rig, (GCompound) o, full, k);
        }
    }

    /** Cost of each sprite class inside a layer (hides every child of that class at once). */
    private static void byClass(RenderRig rig, GCompound layer, double full, int k) {
        java.util.Map<String, List<GObject>> groups = new java.util.TreeMap<>();
        for (int i = 0; i < layer.getElementCount(); i++) {
            GObject o = layer.getElement(i);
            if (o.isVisible()) groups.computeIfAbsent(o.getClass().getSimpleName(), c -> new ArrayList<>()).add(o);
        }
        if (groups.size() < 2) return;
        for (java.util.Map.Entry<String, List<GObject>> en : groups.entrySet()) {
            double cost = costOfHiding(rig, en.getValue(), k);
            System.out.printf("         %-26s x%-4d %6.2f ms%n", en.getKey(), en.getValue().size(), cost);
        }
    }

    /** Paint cost of a set of objects: mean of the full paints just before and after, minus the paint with them hidden. */
    private static double costOfHiding(RenderRig rig, List<GObject> objs, int k) {
        double before = rig.paintMs(k);
        for (GObject o : objs) o.setVisible(false);
        double without = rig.paintMs(k);
        for (GObject o : objs) o.setVisible(true);
        double after = rig.paintMs(k);
        return (before + after) / 2 - without;
    }

    private static final EnemyType[] CROWD = {
        EnemyType.PRIMITIVE_VARIABLE, EnemyType.STATIC_ARRAY, EnemyType.DYNAMIC_ARRAY, EnemyType.SINGLY_LINKED_LIST,
        EnemyType.DOUBLY_LINKED_LIST, EnemyType.BUBBLE_SORT, EnemyType.SELECTION_SORT, EnemyType.INSERTION_SORT, EnemyType.SHELL_SORT,
        EnemyType.MERGE_SORT, EnemyType.QUICK_SORT, EnemyType.HEAP_SORT, EnemyType.COUNTING_SORT, EnemyType.RADIX_SORT,
        EnemyType.BUCKET_SORT, EnemyType.TIMSORT };

    /** Spawns {@code n} crowd enemies spread along every route (deterministic mix of types, modifiers, HP). */
    static void spawnCrowd(Game g, int n, int salt) {
        List<Path> routes = g.getMap().getRoutes();
        for (int i = 0; i < n; i++) {
            int k = i + salt;
            EnemyType t = CROWD[k % CROWD.length];
            EnumSet<Modifier> mods = EnumSet.noneOf(Modifier.class);
            if (k % 5 == 1) mods.add(Modifier.CAMO);
            if (k % 7 == 2) mods.add(Modifier.REGROW);
            if (k % 6 == 3) mods.add(Modifier.FORTIFIED);
            int route = k % routes.size();
            Path r = routes.get(route);
            double d = (r.getTotalLength() * 0.92) * ((k * 0.6180339887) % 1.0);
            boolean tanky = k % 3 != 0;   // two thirds survive the measurement, one third dies (deaths, splits)
            Enemy e = g.getEnemyManager().spawnScaled(t, mods, route, d, tanky ? 4000 : g.getWaveHpScale(t), g.getWaveSpeedScale());
            if (tanky) e.takeDamage(e.getMaxHp() * (0.1 + 0.8 * ((k * 37) % 100) / 100.0), g.getTime());
        }
    }

    private static void renderBench(Difficulty diff) throws Exception {
        int[] sizes = intList(System.getProperty("perf.enemies", "150,300,600"));
        int frames = Integer.getInteger("perf.frames", 240);
        int mapIdx = Integer.getInteger("perf.renderMap", 0);
        int towers = Integer.getInteger("perf.towers", 72);
        String[] wh = System.getProperty("perf.size", "1600x1000").split("x");
        int w = Integer.parseInt(wh[0]), h = Integer.parseInt(wh[1]);
        String snap = System.getProperty("perf.snap");
        System.out.println("== RENDER: real GameScreen in a GCanvas painted offscreen at " + w + "x" + h + ", " + frames + " frames per case, map "
            + mapIdx + ", " + towers + " maxed towers ==");
        System.out.println(String.format("%-7s | %7s %6s %6s | %8s %7s %7s %7s | %8s %7s %7s %7s | %4s %6s | %8s",
            "enemies", "upd p50", "mean", "p95", "paint50", "mean", "p95", "max", "frame50", "mean", "p95", "max", "proj", "GObjs", "KB/frame"));
        for (int n : sizes) {
            Game g = lateGame(mapIdx, diff, towers, 95);
            g.setGlobalEnemySpeedMultiplier(0.25);
            RenderRig rig = new RenderRig(g, w, h);
            spawnCrowd(g, n, 0);
            int salt = n;
            Stats upd = new Stats(), paint = new Stats(), total = new Stats();
            int warm = 30;
            long alloc0 = 0;
            int projSum = 0, objSum = 0, samples = 0;
            for (int f = 0; f < warm + frames; f++) {
                if (f == warm) alloc0 = allocBytes();
                int alive = g.getEnemyManager().getEnemies().size();
                if (alive < n) { spawnCrowd(g, n - alive, salt); salt += n - alive; }
                if (f % 60 == 0) fireAbilities(g);
                long t0 = now();
                rig.screen.frame(1 / 60.0);
                long t1 = now();
                rig.paint();
                long t2 = now();
                if (f < warm) continue;
                upd.add((t1 - t0) / 1e6);
                paint.add((t2 - t1) / 1e6);
                total.add((t2 - t0) / 1e6);
                if (f % 20 == 0) {
                    projSum += g.getCombat().getProjectiles().size();
                    objSum += countObjects(rig.root);
                    samples++;
                }
            }
            long bytes = allocBytes() - alloc0;
            System.out.println(String.format("%-7d | %7.2f %6.2f %6.2f | %8.2f %7.2f %7.2f %7.1f | %8.2f %7.2f %7.2f %7.1f | %4d %6d | %8.1f",
                n, upd.pct(50), upd.mean(), upd.pct(95), paint.pct(50), paint.mean(), paint.pct(95), paint.max(),
                total.pct(50), total.mean(), total.pct(95), total.max(),
                projSum / Math.max(1, samples), objSum / Math.max(1, samples), bytes / 1024.0 / frames));
            if (Boolean.getBoolean("perf.breakdown")) breakdown(rig);
            if (snap != null) {
                File dir = new File(snap);
                dir.mkdirs();
                ImageIO.write(rig.img, "png", new File(dir, "render_" + n + ".png"));
            }
        }
        System.out.println();
    }

    /** Number of visible leaf GObjects under {@code c} (what actually gets painted). */
    static int countObjects(GCompound c) {
        if (!c.isVisible()) return 0;
        int n = 0;
        for (int i = 0; i < c.getElementCount(); i++) {
            GObject o = c.getElement(i);
            if (o instanceof GCompound) n += countObjects((GCompound) o);
            else if (o.isVisible()) n++;
        }
        return n;
    }

    // ------------------------------------------------------------------ helpers

    private static long gcCount() {
        long n = 0;
        for (GarbageCollectorMXBean b : ManagementFactory.getGarbageCollectorMXBeans()) n += Math.max(0, b.getCollectionCount());
        return n;
    }

    private static int[] intList(String s) {
        String[] parts = s.split(",");
        int[] out = new int[parts.length];
        for (int i = 0; i < parts.length; i++) out[i] = Integer.parseInt(parts[i].trim());
        return out;
    }

    /** Sample collector with mean / percentiles / max. */
    static final class Stats {
        private double[] v = new double[1024];
        int n;
        private double sum;
        void add(double x) { if (n == v.length) v = Arrays.copyOf(v, n * 2); v[n++] = x; sum += x; }
        void addAll(Stats o) { for (int i = 0; i < o.n; i++) add(o.v[i]); }
        double mean() { return n == 0 ? 0 : sum / n; }
        double max() { double m = 0; for (int i = 0; i < n; i++) m = Math.max(m, v[i]); return m; }
        double pct(double p) {
            if (n == 0) return 0;
            double[] s = Arrays.copyOf(v, n);
            Arrays.sort(s);
            return s[Math.min(n - 1, (int) Math.ceil(p / 100.0 * n) - 1)];
        }
    }
}
