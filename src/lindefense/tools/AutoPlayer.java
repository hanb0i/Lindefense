package lindefense.tools;

import java.util.ArrayList;
import java.util.List;
import lindefense.ai.DefenderAI;
import lindefense.enemy.Enemy;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Headless balance probe: a competent, scripted "near-optimal" bot plays the campaign on every map.
 *
 * <p>What it does: follows a wave-gated build plan (cheap early defence, Perplexity income early, camo detection
 * before the first camo waves, boss damage before boss waves), respects the one-copy hero rule, sets sensible
 * targeting, fires every ability when it matters (the two point-targeted ones at the densest spot of the track) and
 * spends overflow cash on the cheapest upgrade / the least-represented tower. The decisions live in
 * {@link lindefense.ai.DefenderAI} (shared with the reverse-mode defender); this class runs whole campaigns with it.</p>
 *
 * <p>Handicaps: {@code -Dbot.maxTowers=N} caps the tower count (upgrades only beyond it); {@code -Dbot.random=true}
 * places towers on random spots that merely touch the track (a casual human).</p>
 *
 * <p>Usage: {@code java -cp build lindefense.tools.AutoPlayer [maxWave] [mapIdx] [verbose]} with
 * {@code -Dbot.difficulty=O1|ON|ON2|ONN}, {@code -Dbot.seed=N}, {@code -Dbot.seeds=K} (runs seeds N..N+K-1 and prints one
 * line per run), {@code -Dbot.maxMinutes=N}.</p>
 */
public final class AutoPlayer {
    private static final boolean DUMP = Boolean.getBoolean("bot.dump");
    /** PATCH NOTES: {@code -Dbot.variance=random|first} plays with run variance on (default off, as in every tool). */
    private static final lindefense.variance.RunVariance.Picker VARIANCE = variancePicker(System.getProperty("bot.variance"));

    private static lindefense.variance.RunVariance.Picker variancePicker(String s) {
        if (s == null || s.isEmpty() || s.equalsIgnoreCase("false") || s.equalsIgnoreCase("off")) return null;
        return s.equalsIgnoreCase("first") ? lindefense.variance.RunVariance.Picker.FIRST : lindefense.variance.RunVariance.Picker.RANDOM;
    }

    /** " notes A,B,C news N" for a run with variance on, else empty. */
    private static String varianceSummary(Game g) {
        if (g == null || !g.getVariance().isEnabled()) return "";
        StringBuilder sb = new StringBuilder("  notes ");
        String sep = "";
        for (lindefense.variance.PatchNote p : g.getVariance().getActive()) { sb.append(sep).append(p.name()); sep = ","; }
        return sb.append("  news ").append(g.getVariance().getNewsLog().size()).toString();
    }
    private static int DUMP_WAVE = Integer.getInteger("bot.dumpWave", -1);

    private AutoPlayer() { }

    /** Outcome of one run. */
    public static final class Result {
        public Game.State state;
        public int completed, lives, towers, maxed;
        public double cash, earned;
        public String map;
        public Game game;
        public boolean won() { return state == Game.State.VICTORY; }
    }

    public static void main(String[] args) {
        int maxWaves = args.length > 0 ? Integer.parseInt(args[0]) : 100;
        int only = args.length > 1 ? Integer.parseInt(args[1]) : -1;
        boolean verbose = args.length > 2;
        long seed0 = Long.getLong("bot.seed", 1234L);
        int seeds = Integer.getInteger("bot.seeds", 1);
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            if (only >= 0 && only != m) continue;
            for (int k = 0; k < seeds; k++) {
                Result r = run(m, seed0 + k, botDifficulty(), maxWaves, Integer.getInteger("bot.maxTowers", 999), Boolean.getBoolean("bot.random"), verbose || seeds == 1);
                System.out.printf("[%s] %-22s seed %-5d %-7s completed %3d lives %3d cash %7.0f earned %7.0f towers %2d maxed %2d%s%n",
                    botDifficulty().label, r.map, seed0 + k, r.state, r.completed, r.lives, r.cash, r.earned, r.towers, r.maxed, varianceSummary(r.game));
            }
        }
    }

    /** Difficulty from {@code -Dbot.difficulty=O1|ON|ON2|ONN} (falls back to -Dlindefense.difficulty, then O(1)). */
    private static Difficulty botDifficulty() {
        Difficulty d = Difficulty.parse(System.getProperty("bot.difficulty"));
        return d != null ? d : Difficulty.defaultMode();
    }

    /** Plays one full campaign (or up to {@code maxWaves}) and returns the outcome. */
    public static Result run(int mapIdx, long seed, Difficulty diff, int maxWaves, int maxTowers, boolean random, boolean report) {
        return run(mapIdx, seed, diff, maxWaves, maxTowers, random, report, false);
    }

    /** As above; {@code mixed} selects the broad every-tower build instead of the efficient one. */
    public static Result run(int mapIdx, long seed, Difficulty diff, int maxWaves, int maxTowers, boolean random, boolean report, boolean mixed) {
        DefenderAI.Options opt = new DefenderAI.Options();
        opt.plan = mixed || random ? DefenderAI.Plan.MIXED : DefenderAI.Plan.EFFICIENT;   // a casual human also builds a broad roster
        opt.maxTowers = maxTowers;
        opt.randomPlacement = random;
        opt.verbose = DUMP;
        String open = System.getProperty("bot.open");
        if (open != null) {
            List<DefenderAI.Step> pl = new ArrayList<>();
            for (String tok : open.split(",")) { String[] f = tok.split(":"); pl.add(new DefenderAI.Step(TowerType.valueOf(f[0]), Integer.parseInt(f[1]), Integer.parseInt(f[2]), 1)); }
            opt.opening = pl;
        }
        Game g = new Game(MapCatalog.create(mapIdx), seed, diff);
        if (VARIANCE != null) g.getVariance().enable(VARIANCE);   // PATCH NOTES: the bot answers drafts itself
        DefenderAI ai = new DefenderAI(g, opt);
        GameMap map = g.getMap();
        int ticks = 0, lastReport = 0;
        java.util.Map<Integer, Double> snap = null;
        int maxTicks = 60 * 60 * Integer.getInteger("bot.maxMinutes", 90);
        while (g.getState() == Game.State.PLAYING && ticks < maxTicks) {
            if (ticks % 15 == 0) ai.manage();
            if (g.getWaveManager().canStartNextWave()) {
                if (g.getWave() < maxWaves) g.startNextWave(); else break;
            }
            if (DUMP_WAVE > 0 && g.getWave() == DUMP_WAVE && snap == null) {
                snap = new java.util.HashMap<>();
                for (Tower t : mine(g)) snap.put(t.getId(), t.getDamageDealt());
            }
            if (DUMP_WAVE > 0 && g.getLastCompletedWave() == DUMP_WAVE && snap != null) {
                double tot = 0;
                for (Tower t : mine(g)) { Double b = snap.get(t.getId()); double d = t.getDamageDealt() - (b == null ? 0 : b); tot += d; System.out.printf("      w%d %-22s tier %d dmg %8.0f%n", DUMP_WAVE, t.getType(), t.getTier(), d); }
                System.out.printf("      total %.0f%n", tot);
                snap = null; DUMP_WAVE = -1;
            }
            int livesBefore = g.getLives();
            Enemy nearest = null;
            if (DUMP) for (Enemy e : g.getEnemyManager().getEnemies()) if (nearest == null || e.getRemainingDistance() < nearest.getRemainingDistance()) nearest = e;
            g.step(Game.DT);
            if (DUMP && g.getLives() < livesBefore && nearest != null)
                System.out.printf("      leak w%d -%d lives: %s %s hpScale %.2f%n", g.getWave(), livesBefore - g.getLives(), nearest.getType(), nearest.getModifiers(), nearest.getHpScale());
            g.getEvents().clear();
            ticks++;
            if (report && g.getLastCompletedWave() != lastReport && g.getLastCompletedWave() % Integer.getInteger("bot.reportEvery", 10) == 0) {
                lastReport = g.getLastCompletedWave();
                System.out.printf("    after wave %3d: lives %3d cash %7.0f towers %2d (maxed: %d)%n", lastReport, g.getLives(), g.getCash(),
                    g.getTowerManager().getPlayerTowers().size(), countMaxed(g));
            }
        }
        if (Boolean.getBoolean("bot.dump")) {
            java.util.Map<TowerType, double[]> agg = new java.util.EnumMap<>(TowerType.class);
            for (Tower t : g.getTowerManager().getPlayerTowers()) {
                double[] a = agg.computeIfAbsent(t.getType(), k -> new double[3]);
                a[0] += t.getInvestedCost(); a[1] += t.getDamageDealt(); a[2] += t.getKills();
            }
            for (java.util.Map.Entry<TowerType, double[]> en : agg.entrySet())
                System.out.printf("      SUM %-24s cost %8.0f dmg %10.0f dmg/$ %6.2f kills %6.0f%n", en.getKey(), en.getValue()[0], en.getValue()[1], en.getValue()[1] / en.getValue()[0], en.getValue()[2]);
            System.out.println("      wave " + g.getWave() + " alive " + g.getEnemyManager().getAliveCount());
        }
        Result r = new Result();
        r.state = g.getState(); r.completed = g.getLastCompletedWave(); r.lives = g.getLives(); r.cash = g.getCash();
        r.earned = g.getTotalCashEarned(); r.towers = g.getTowerManager().getPlayerTowers().size(); r.maxed = countMaxed(g);
        r.map = map.getName(); r.game = g;
        return r;
    }

    private static int countMaxed(Game g) {
        int n = 0;
        for (Tower t : g.getTowerManager().getPlayerTowers()) if (t.isMaxed()) n++;
        return n;
    }

    private static List<Tower> mine(Game g) { return g.getTowerManager().getPlayerTowers(); }
}
