package lindefense.tools;

import java.util.ArrayList;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Headless balance probe: a competent, scripted "near-optimal" bot plays the campaign on every map.
 *
 * <p>What it does: follows a wave-gated build plan (cheap early defence, Perplexity income early, camo detection
 * before the first camo waves, boss damage before boss waves), respects the one-copy hero rule, sets sensible
 * targeting, fires every ability when it matters (the two point-targeted ones at the densest spot of the track) and
 * spends overflow cash on the cheapest upgrade / the least-represented tower.</p>
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

    /** Plan step: "the copy-th tower of {@code type} must be at least {@code tier}, once the wave reaches {@code minWave}". */
    private static final class Step {
        final TowerType type; final int copy, tier, minWave;
        Step(TowerType type, int copy, int tier, int minWave) { this.type = type; this.copy = copy; this.tier = tier; this.minWave = minWave; }
    }

    /** Near-optimal plan: concentrates on the best damage per dollar (DeepSeek, Brad, Qwen) plus Perplexity income. */
    private static final List<Step> PLAN = new ArrayList<>();
    /** Broad plan used to check that every tower earns its place in a mixed build. */
    private static final List<Step> MIXED = new ArrayList<>();
    private static List<Step> cur = PLAN;
    private static void s(TowerType t, int copy, int tier, int minWave) { cur.add(new Step(t, copy, tier, minWave)); }

    static {
        TowerType GEM = TowerType.GEMINI, CLA = TowerType.CLAUDE, GPT = TowerType.GPT, DS = TowerType.DEEPSEEK, COP = TowerType.COPILOT,
            PER = TowerType.PERPLEXITY, COH = TowerType.COHERE, BRAD = TowerType.LOBBER_LUIS, ZET = TowerType.ZETHOS,
            BRN = TowerType.BLITZ_ARNAV, ROH = TowerType.CHILLSTIN, RON = TowerType.BOOM_SAM, SHA = TowerType.SUNNY_JOE, OWN = TowerType.NIK_SCOPE,
            QWEN = TowerType.QWEN, KIMI = TowerType.KIMI, MM = TowerType.MINIMAX, SUNO = TowerType.SUNO, GLM = TowerType.GLM,
            GROK = TowerType.GROK, SORA = TowerType.SORA, MIS = TowerType.MISTRAL, LLA = TowerType.LLAMA, DAL = TowerType.DALLE;
        // efficient: cheap early defence, Perplexity (camo vision + income), then the DeepSeek / Brad / Qwen core
        cur = PLAN;
        s(GEM, 0, 0, 1); s(CLA, 0, 0, 1); s(GEM, 0, 1, 1); s(CLA, 0, 1, 1); s(PER, 0, 0, 1);
        s(GPT, 0, 0, 1); s(GPT, 0, 1, 1); s(PER, 0, 1, 1); s(DS, 0, 0, 1); s(DS, 0, 1, 1);
        s(COH, 0, 1, 1); s(PER, 0, 2, 1); s(PER, 0, 3, 1);          // +$250 per round
        s(DS, 0, 2, 1); s(DS, 0, 3, 1); s(DS, 1, 0, 1); s(DS, 1, 1, 1); s(DS, 1, 2, 1); s(DS, 1, 3, 1);
        s(PER, 1, 3, 1); s(DS, 2, 3, 1); s(PER, 2, 3, 14); s(QWEN, 0, 2, 1); s(PER, 3, 3, 22);   // research income pays back in ~12 rounds
        s(BRAD, 0, 0, 28);   // the hero is a big Hero Store purchase: only once the core is up
        s(DS, 3, 3, 1); s(QWEN, 0, 3, 1); s(DS, 4, 3, 1); s(COH, 0, 3, 1); s(GEM, 0, 3, 1); s(GPT, 0, 3, 1);
        // mixed: every tower type, used by the "every tower contributes" test
        cur = MIXED;
        s(GEM, 0, 0, 1); s(CLA, 0, 0, 1); s(PER, 0, 0, 1);
        s(GEM, 0, 1, 1); s(CLA, 0, 1, 1); s(GPT, 0, 0, 1); s(PER, 0, 1, 1);
        s(GPT, 0, 1, 1); s(DS, 0, 0, 1); s(DS, 0, 1, 1);
        s(PER, 0, 2, 1); s(PER, 0, 3, 1);
        s(COH, 0, 1, 1); s(GEM, 0, 2, 1); s(CLA, 0, 2, 1);
        s(COH, 0, 2, 1); s(GPT, 0, 2, 1); s(DS, 0, 2, 1);
        s(COH, 0, 3, 1); s(DS, 0, 3, 1); s(GEM, 0, 3, 1);
        s(ZET, 0, 2, 1); s(CLA, 0, 3, 1); s(GPT, 0, 3, 1); s(ZET, 0, 4, 1);
        s(BRAD, 0, 0, 1); s(SHA, 0, 0, 1); s(ROH, 0, 0, 1); s(BRN, 0, 0, 1); s(OWN, 0, 0, 1); s(RON, 0, 0, 1);
        s(QWEN, 0, 2, 1); s(QWEN, 0, 3, 1);
        s(KIMI, 0, 1, 1); s(MM, 0, 1, 1); s(SUNO, 0, 2, 1); s(GLM, 0, 2, 1);
        s(KIMI, 0, 3, 1); s(MM, 0, 3, 1); s(SUNO, 0, 3, 1); s(GLM, 0, 3, 1);
        s(GROK, 0, 3, 1); s(SORA, 0, 3, 1); s(MIS, 0, 3, 1); s(LLA, 0, 3, 1); s(DAL, 0, 3, 1); s(COP, 0, 3, 1);
        cur = PLAN;
    }

    /** Overflow buy order once the plan is exhausted or gated: types are bought in this rotation. */
    private static final TowerType[] OVERFLOW_EFFICIENT = {
        TowerType.DEEPSEEK, TowerType.QWEN, TowerType.COHERE,
        TowerType.GLM, TowerType.SORA, TowerType.GROK, TowerType.LLAMA,        // control and boss-burst tools
    };
    private static final TowerType[] OVERFLOW_MIXED = {
        TowerType.DEEPSEEK, TowerType.COHERE, TowerType.QWEN, TowerType.KIMI, TowerType.MINIMAX, TowerType.GEMINI, TowerType.GPT,
        TowerType.CLAUDE, TowerType.SUNO, TowerType.GLM, TowerType.MISTRAL, TowerType.LLAMA, TowerType.GROK, TowerType.SORA,
    };

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
                System.out.printf("[%s] %-22s seed %-5d %-7s completed %3d lives %3d cash %7.0f earned %7.0f towers %2d maxed %2d%n",
                    botDifficulty().label, r.map, seed0 + k, r.state, r.completed, r.lives, r.cash, r.earned, r.towers, r.maxed);
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
        mixed = mixed || random;                  // a casual human also builds a broad roster
        plan = mixed ? MIXED : PLAN;
        String open = System.getProperty("bot.open");
        if (open != null && !mixed) {
            List<Step> pl = new ArrayList<>();
            for (String tok : open.split(",")) { String[] f = tok.split(":"); pl.add(new Step(TowerType.valueOf(f[0]), Integer.parseInt(f[1]), Integer.parseInt(f[2]), 1)); }
            pl.addAll(PLAN);
            plan = pl;
        }
        Game g = new Game(MapCatalog.create(mapIdx), seed, diff);
        livesAtWaveStart = livesPrevWave = g.getLives(); trackedWave = 0;
        GameMap map = g.getMap();
        List<Vec> samples = new ArrayList<>();
        for (Path r : map.getRoutes()) for (double d = 0; d < r.getTotalLength(); d += 20) samples.add(r.positionAt(d));
        List<Vec> spots = new ArrayList<>();
        for (int x = 30; x < GameMap.WIDTH; x += 15) for (int y = 30; y < GameMap.HEIGHT; y += 15) {
            Vec p = new Vec(x, y);
            if (map.isBuildable(p, 20)) spots.add(p);
        }
        int ticks = 0, lastReport = 0;
        java.util.Map<Integer, Double> snap = null;
        int maxTicks = 60 * 60 * Integer.getInteger("bot.maxMinutes", 90);
        while (g.getState() == Game.State.PLAYING && ticks < maxTicks) {
            if (ticks % 15 == 0) manage(g, spots, samples, maxTowers, random);
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

    // ------------------------------------------------------------------ per-decision logic

    private static int livesAtWaveStart = 100, livesPrevWave = 100, trackedWave = 0;

    private static void manage(Game g, List<Vec> spots, List<Vec> samples, int maxTowers, boolean random) {
        if (g.getWave() != trackedWave) {          // lives lost over the last two waves = "under pressure"
            trackedWave = g.getWave();
            livesPrevWave = livesAtWaveStart;
            livesAtWaveStart = g.getLives();
        }
        if (!random) { useAbilities(g); setTargeting(g); }     // a casual player rarely micro-manages
        purchase(g, spots, samples, maxTowers, random);
    }
    private static List<Step> plan = PLAN;

    private static List<Tower> mine(Game g) { return g.getTowerManager().getPlayerTowers(); }

    private static Tower nth(Game g, TowerType type, int copy) {
        int i = 0;
        for (Tower t : mine(g)) if (t.getType() == type) { if (i == copy) return t; i++; }
        return null;
    }

    private static int count(Game g, TowerType type) {
        int n = 0;
        for (Tower t : mine(g)) if (t.getType() == type) n++;
        return n;
    }

    /** True if the wave (1-based) contains camo enemies or a Lockheed Martin. */
    private static boolean camoWave(int wave) {
        if (wave < 1 || wave > WaveData.WAVE_COUNT) return false;
        WaveDef d = WaveData.get(wave);
        for (SpawnGroup gr : d.groups) if (gr.modifiers.contains(Modifier.CAMO) || gr.type.hasInnateCamo()) return true;
        return false;
    }

    private static boolean hasDetection(Game g) {
        for (Tower t : mine(g)) {
            if (t.getType() == TowerType.PERPLEXITY && t.getTier() >= 1) return true;   // U1: every tower can target all camo
            if (t.getType() == TowerType.GROK) return true;
        }
        return false;
    }

    private static boolean difficultyHardMode(Game g) { return g.getDifficulty().ordinal() >= Difficulty.ON2.ordinal(); }

    private static void purchase(Game g, List<Vec> spots, List<Vec> samples, int maxTowers, boolean random) {
        int wave = Math.max(1, g.getWave());
        int towers = mine(g).size();
        // camo safety net: detection must exist before the next camo wave
        for (int w = wave; w <= wave + 2 && !random; w++) {          // (a casual player does not plan for camo)
            if (camoWave(w) && !hasDetection(g)) {
                Tower per = nth(g, TowerType.PERPLEXITY, 0);
                if (per == null) { if (towers < maxTowers && tryBuy(g, TowerType.PERPLEXITY, spots, samples, random)) return; if (g.getCash() < price(TowerType.PERPLEXITY)) return; }
                else if (per.canUpgrade() && g.upgradeTower(per)) return;
                else if (per.canUpgrade() && g.getCash() < per.nextUpgrade().cost) return;
                break;
            }
        }
        boolean pressure = livesPrevWave - g.getLives() >= 2;
        if (pressure && attackers(g) < 5 + wave / 4 && towers < maxTowers) {
            // leaking: stop investing in economy and add cheap firepower
            TowerType pick = null; int best = Integer.MAX_VALUE;
            for (TowerType tt : new TowerType[] { TowerType.GEMINI, TowerType.CLAUDE, TowerType.GPT, TowerType.COHERE }) {
                int c = count(g, tt); if (c < best) { best = c; pick = tt; }
            }
            if (g.getCash() >= price(pick)) { if (tryBuy(g, pick, spots, samples, random)) return; }
        }
        for (Step st : plan) {
            if (st.minWave > wave) continue;
            if (pressure && st.type == TowerType.PERPLEXITY && st.tier >= 2) continue;
            if (random && st.type == TowerType.PERPLEXITY) continue;
            if (maxTowers < 40 && st.type == TowerType.PERPLEXITY && st.copy >= 1) continue;   // slots are scarce: one research tower only
            Tower t = nth(g, st.type, st.copy);
            if (t == null) {
                if (st.type.isHero() && (count(g, st.type) > 0 || g.isHeroDeployed(st.type))) continue;   // once per match
                if (st.copy > count(g, st.type)) continue;                      // copies are bought in order
                if (towers >= maxTowers) continue;                              // handicap: upgrades only
                if (!tryBuy(g, st.type, spots, samples, random)) { if (g.getCash() < price(g, st.type)) return; continue; }
                return;
            }
            if (t.getTier() >= st.tier) continue;
            if (g.upgradeTower(t)) return;
            if (DUMP && g.getCash() > 2500 && g.getTick() % 600 == 0) System.out.println("      BLOCKED w" + wave + " on " + st.type + " copy " + st.copy + " tier " + st.tier + " cash " + g.getCash() + " cost " + t.nextUpgrade().cost);
            return;                                                             // save up for this upgrade
        }
        overflow(g, spots, samples, maxTowers, random);
    }

    private static int attackers(Game g) {
        int n = 0;
        for (Tower t : mine(g)) if (t.getType() != TowerType.PERPLEXITY) n++;
        return n;
    }

    /** Cash needed to get the type onto the map: Hero Store unlock price for a locked hero, else the base cost. */
    private static int price(TowerType t) { return TowerCatalog.get(t).baseCost; }
    private static int price(Game g, TowerType t) { return t.isHero() && !g.isHeroUnlocked(t) ? TowerCatalog.get(t).unlockCost : price(t); }

    private static boolean tryBuy(Game g, TowerType type, List<Vec> spots, List<Vec> samples, boolean random) {
        if (g.getCash() < price(g, type)) return false;
        if (type.isHero() && g.isHeroDeployed(type)) return false;
        if (type.isHero() && !g.isHeroUnlocked(type) && !g.purchaseHero(type)) return false;   // Hero Store first
        Vec p = bestSpot(g, type, spots, samples, random);
        if (p == null) return false;
        Tower t = g.placeTower(type, p);
        if (DUMP && t != null) System.out.printf("      buy w%d %s cash %.0f%n", g.getWave(), type, g.getCash());
        return t != null;
    }

    /** Spend leftover cash: cheapest upgrade first, otherwise another tower from the rotation (least-represented first). */
    private static void overflow(Game g, List<Vec> spots, List<Vec> samples, int maxTowers, boolean random) {
        Tower up = null;
        for (Tower t : mine(g)) if (t.canUpgrade() && (up == null || t.nextUpgrade().cost < up.nextUpgrade().cost)) up = t;
        TowerType buy = null;
        if (mine(g).size() < maxTowers) {
            double bestRatio = Double.MAX_VALUE;
            for (TowerType tt : plan == MIXED ? OVERFLOW_MIXED : OVERFLOW_EFFICIENT) {
                if (plan != MIXED && isControlTool(tt) && mine(g).size() < 30) continue;   // with a small roster, raw damage first
                double ratio = count(g, tt) / weight(tt);
                if (ratio < bestRatio) { bestRatio = ratio; buy = tt; }
            }
        }
        if (up != null && (buy == null || up.nextUpgrade().cost <= price(buy) * 2.2)) { g.upgradeTower(up); return; }
        if (buy != null) tryBuy(g, buy, spots, samples, random);
        else if (up != null) g.upgradeTower(up);
    }

    private static boolean isControlTool(TowerType t) {
        return t == TowerType.GLM || t == TowerType.SORA || t == TowerType.GROK || t == TowerType.LLAMA;
    }

    /** Overflow weights: how many copies of a type per copy of a weight-1 type. DeepSeek (map-wide, x2 vs bosses) is the best late value per dollar. */
    private static double weight(TowerType t) {
        switch (t) {
            case DEEPSEEK: return plan == MIXED ? 2 : 8;
            case QWEN: return plan == MIXED ? 1 : 2;
            default: return 1;
        }
    }

    // ------------------------------------------------------------------ targeting & abilities

    private static void setTargeting(Game g) {
        boolean boss = false, ddt = false;
        for (Enemy e : g.getEnemyManager().getEnemies()) {
            if (e.isBoss() && !e.isStored()) boss = true;
            if (e.getType() == EnemyType.LOCKHEED_MARTIN) ddt = true;
        }
        for (Tower t : mine(g)) {
            Targeting want = Targeting.FIRST;
            switch (t.getType()) {
                case DEEPSEEK: case COHERE: case NIK_SCOPE: want = Targeting.STRONGEST; break;
                case GROK: if (t.canUseDensestCluster()) want = Targeting.DENSEST_CLUSTER; break;
                default: if (boss) want = Targeting.STRONGEST; break;       // focus bosses while one is on the track
            }
            if (ddt && want != Targeting.DENSEST_CLUSTER) want = Targeting.FIRST;       // the fast DDT runs ahead of the pack: First catches it
            if (t.getTargeting() != want) t.setTargeting(want);
        }
    }

    /** Densest spot on the track: the enemy position with the most other enemies within 110 px (bosses weigh more). */
    private static Vec densestSpot(Game g, int[] outCount) {
        List<Enemy> es = g.getEnemyManager().getEnemies();
        Vec best = null; int bestN = 0;
        for (Enemy a : es) {
            if (a.isStored()) continue;
            int n = 0;
            for (Enemy b : es) if (!b.isStored() && a.getPosition().distSq(b.getPosition()) <= 110 * 110) n += b.isBoss() ? 6 : 1;
            if (n > bestN) { bestN = n; best = a.getPosition(); }
        }
        if (outCount != null) outCount[0] = bestN;
        return best;
    }

    private static void useAbilities(Game g) {
        int alive = 0; boolean boss = false; boolean leakRisk = false; Enemy leadBoss = null;
        for (Enemy e : g.getEnemyManager().getEnemies()) {
            if (e.isStored()) continue;
            alive++;
            if (e.isBoss()) { boss = true; leadBoss = e; }
            if (e.getRemainingDistance() < 0.25 * e.getRoute().getTotalLength() && e.getType().lives >= 2) leakRisk = true;
        }
        if (alive == 0) return;
        boolean danger = boss || alive >= 18 || leakRisk;
        for (Tower t : new ArrayList<>(g.getTowerManager().getTowers())) {
            if (t.isTemporary() || !t.isAbilityReady()) continue;
            switch (t.getType()) {
                case PERPLEXITY:
                    if (g.getRoundPopValue() * 0.2 >= 800) g.activateAbility(t);
                    continue;
                case DEEPSEEK:
                    if (alive >= 6) g.activateAbility(t);
                    continue;
                case SORA:
                    if (leakRisk) g.activateAbility(t);
                    continue;
                default: break;
            }
            if (!danger) continue;
            if (t.getAbility().needsTarget) {
                int[] n = new int[1];
                Vec spot = leadBoss != null && t.getType() == TowerType.MISTRAL ? leadBoss.getPosition() : densestSpot(g, n);
                if (spot != null && (boss || n[0] >= 8)) g.activateAbility(t, spot);
            } else {
                g.activateAbility(t);
            }
        }
    }

    // ------------------------------------------------------------------ placement

    private static Vec bestSpot(Game g, TowerType type, List<Vec> spots, List<Vec> samples, boolean random) {
        double range = TowerCatalog.get(type).baseStats.range;
        if (random) {
            // casual human: a random buildable spot that is at least within range of the track
            for (int tries = 0; tries < 200; tries++) {
                Vec p = spots.get(g.getRng().nextInt(spots.size()));
                if (!g.getTowerManager().canPlace(type, p)) continue;
                int cover = 0;
                for (Vec s : samples) if (s.distSq(p) <= range * range) cover++;
                if (cover >= 3) return p;
            }
            return null;
        }
        boolean mapWide = range >= 1000;
        double aura = TowerCatalog.get(type).baseStats.auraRange;
        // diminishing returns: track already covered by other towers is worth less (spreads towers over every lane)
        double[] weight = new double[samples.size()];
        for (int k = 0; k < weight.length; k++) {
            double cov = 0;
            for (Tower t : mine(g)) {
                double r = t.getStats().range;
                if (r < 1000 && t.getPosition().distSq(samples.get(k)) <= r * r) cov += 1 + t.getTier();
            }
            weight[k] = 1.0 / (1.0 + 0.5 * cov);
        }
        Vec best = null; double bestScore = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < spots.size(); i += 2) {
            Vec p = spots.get(i);
            if (!g.getTowerManager().canPlace(type, p)) continue;
            double score = 0;
            if (mapWide) {
                // a map-wide sniper wants a spot that is useless for everyone else
                for (Vec s : samples) if (s.distSq(p) <= 170 * 170) score -= 1;
            } else {
                for (int k = 0; k < weight.length; k++) if (samples.get(k).distSq(p) <= range * range) score += weight[k];
            }
            if (aura > 0 && !mapWide) {
                for (Tower t : mine(g)) if (t.getPosition().dist(p) <= aura) score += 15;
            } else if (!mapWide) {
                for (Tower t : mine(g)) if (t.getStats().auraRange > 0 && t.getPosition().dist(p) <= t.getStats().auraRange) score += 10;
            }
            if (score > bestScore) { bestScore = score; best = p; }
        }
        return best;
    }
}
