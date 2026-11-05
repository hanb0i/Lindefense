package lindefense.ai;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BooleanSupplier;
import java.util.function.IntSupplier;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.GameMap;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Shop;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * A scripted tower-defense player that a running {@link Game} consults every few game-seconds. It is the decision
 * logic of the balance bot ({@code tools.AutoPlayer}) and the defender of reverse mode ({@link ReverseMatch}).
 *
 * <p>One {@link #manage()} pass: fires abilities when they matter (point-targeted ones at the densest spot of the
 * track), sets sensible targeting, then spends cash. Spending follows a wave-gated build plan (cheap early defence,
 * Perplexity, camo detection before camo arrives, a DeepSeek / Qwen core for bosses), respects the Hero Store rules
 * (unlock first, one copy per hero, the per-game hero cap), adds cheap firepower while leaking, and puts overflow cash
 * into the cheapest upgrade or the least-represented tower of a rotation. Optionally it buys the $15,000 ability unlock
 * of maxed towers ({@link Options#unlockAbilities}).</p>
 *
 * <p>Everything goes through the public {@link Game} actions (placeTower, upgradeTower, purchaseHero, unlockAbility,
 * activateAbility), so the AI is bound by exactly the rules a human player is. No UI dependency: runs headless.</p>
 */
public class DefenderAI {

    /** Plan step: "the copy-th tower of {@code type} must be at least {@code tier}, once the wave reaches {@code minWave}". */
    public static final class Step {
        /** Tower type of the step. */
        public final TowerType type;
        /** 0-based copy, target tier and the earliest wave the step may be worked on. */
        public final int copy, tier, minWave;
        /** A plan step (copy and tier are 0-based; minWave is the earliest wave the step may be worked on). */
        public Step(TowerType type, int copy, int tier, int minWave) { this.type = type; this.copy = copy; this.tier = tier; this.minWave = minWave; }
    }

    /** Build plan presets. */
    public enum Plan {
        /** Near-optimal: best damage per dollar (DeepSeek, Lobber Luis, Qwen) plus Perplexity income. */
        EFFICIENT,
        /** Every tower type: a broad roster (also what a casual human builds). */
        MIXED,
        /** Reverse mode: the efficient core plus three heroes (Spear Hanbo, Mr. Lindemann, Lobber Luis). */
        REVERSE
    }

    /** What the AI just did (for the reverse-mode feed). */
    public enum Action { BUILD, UPGRADE, HERO_UNLOCK, HERO_DEPLOY, ABILITY_UNLOCK, ABILITY_CAST }

    /** Receives every action the AI takes. */
    public interface Listener {
        /** Called after a successful action; {@code text} is a short human-readable line ("built Claude Haiku 5.5"). */
        void onAction(Action action, Tower tower, String text);
    }

    /** Tunable behaviour. The defaults are the near-optimal balance bot. */
    public static final class Options {
        /** Which build plan to follow. */
        public Plan plan = Plan.EFFICIENT;
        /** Steps worked on before the plan (AutoPlayer {@code -Dbot.open}); only used with {@link Plan#EFFICIENT}. */
        public List<Step> opening;
        /** Tower cap: beyond it the AI only upgrades. */
        public int maxTowers = 999;
        /** Casual human: random spots that touch the track, broad roster, no ability / targeting micro, no camo planning. */
        public boolean randomPlacement;
        /** Buy the $15,000 ability of maxed shop towers (saves up for it once it has a core). */
        public boolean unlockAbilities;
        /** Towers needed before the first ability unlock. */
        public int unlockMinTowers = 8;
        /** Extra towers needed for each further unlock (0 = greedy: unlock whenever a maxed tower is available). */
        public int unlockTowersPer;
        /** Equivalent wave used for plan gating; null = the game's own wave counter. */
        public IntSupplier waveSource;
        /** True when camo is expected soon; null = look ahead in the campaign's wave table (two waves). Setting it also
         *  arms the camo safety net of a {@link #randomPlacement} player. */
        public BooleanSupplier camoAlarm;
        /** "Under pressure" = 2+ lives lost within this many game seconds; 0 = over the last two waves. */
        public double pressureWindow;
        /** Debug prints (AutoPlayer {@code -Dbot.dump}). */
        public boolean verbose;
    }

    private static final List<Step> EFFICIENT_PLAN = new ArrayList<>();
    private static final List<Step> MIXED_PLAN = new ArrayList<>();
    private static final List<Step> REVERSE_PLAN = new ArrayList<>();
    private static List<Step> cur;
    private static void s(TowerType t, int copy, int tier, int minWave) { cur.add(new Step(t, copy, tier, minWave)); }

    static {
        TowerType GEM = TowerType.GEMINI, CLA = TowerType.CLAUDE, GPT = TowerType.GPT, DS = TowerType.DEEPSEEK, COP = TowerType.COPILOT,
            PER = TowerType.PERPLEXITY, COH = TowerType.COHERE, BRAD = TowerType.LOBBER_LUIS, ZET = TowerType.ZETHOS,
            BRN = TowerType.BLITZ_ARNAV, ROH = TowerType.CHILLSTIN, RON = TowerType.BOOM_SAM, SHA = TowerType.SUNNY_JOE, OWN = TowerType.NIK_SCOPE,
            QWEN = TowerType.QWEN, KIMI = TowerType.KIMI, MM = TowerType.MINIMAX, SUNO = TowerType.SUNO, GLM = TowerType.GLM,
            GROK = TowerType.GROK, SORA = TowerType.SORA, MIS = TowerType.MISTRAL, LLA = TowerType.LLAMA, DAL = TowerType.DALLE,
            HANBO = TowerType.SPEAR_HANBO, LIND = TowerType.MR_LINDEMANN;
        // efficient: cheap early defence, Perplexity (camo vision + income), then the DeepSeek / Brad / Qwen core
        cur = EFFICIENT_PLAN;
        s(GEM, 0, 0, 1); s(CLA, 0, 0, 1); s(GEM, 0, 1, 1); s(CLA, 0, 1, 1); s(PER, 0, 0, 1);
        s(GPT, 0, 0, 1); s(GPT, 0, 1, 1); s(PER, 0, 1, 1); s(DS, 0, 0, 1); s(DS, 0, 1, 1);
        s(COH, 0, 1, 1); s(PER, 0, 2, 1); s(PER, 0, 3, 1);          // +$250 per round
        s(DS, 0, 2, 1); s(DS, 0, 3, 1); s(DS, 1, 0, 1); s(DS, 1, 1, 1); s(DS, 1, 2, 1); s(DS, 1, 3, 1);
        s(PER, 1, 3, 1); s(DS, 2, 3, 1); s(PER, 2, 3, 14); s(QWEN, 0, 2, 1); s(PER, 3, 3, 22);   // research income pays back in ~12 rounds
        s(BRAD, 0, 0, 28);   // the hero is a big Hero Store purchase: only once the core is up
        s(DS, 3, 3, 1); s(QWEN, 0, 3, 1); s(DS, 4, 3, 1); s(COH, 0, 3, 1); s(GEM, 0, 3, 1); s(GPT, 0, 3, 1);
        // mixed: every tower type, used by the "every tower contributes" test
        cur = MIXED_PLAN;
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
        // reverse mode: a 15-minute match with no wave bonuses, so no research economy; camo detection (Perplexity U1)
        // comes from the camo alarm, so a reactive AI only builds it once it has seen camo. Heroes come in as soon as the
        // core can carry them.
        cur = REVERSE_PLAN;
        s(GEM, 0, 0, 1); s(CLA, 0, 0, 1); s(GEM, 0, 1, 1); s(CLA, 0, 1, 1); s(GPT, 0, 0, 1); s(GPT, 0, 1, 1);
        s(DS, 0, 0, 1); s(DS, 0, 1, 1); s(HANBO, 0, 0, 1); s(COH, 0, 1, 1); s(DS, 0, 2, 1); s(HANBO, 0, 1, 1); s(DS, 0, 3, 1);
        s(DS, 1, 0, 1); s(DS, 1, 1, 1); s(LIND, 0, 0, 1); s(DS, 1, 2, 1); s(DS, 1, 3, 1); s(HANBO, 0, 2, 1); s(LIND, 0, 1, 1);
        s(QWEN, 0, 2, 1); s(DS, 2, 3, 1); s(LIND, 0, 2, 1); s(BRAD, 0, 0, 1); s(HANBO, 0, 3, 1);
        s(DS, 3, 3, 1); s(QWEN, 0, 3, 1); s(BRAD, 0, 2, 1); s(LIND, 0, 3, 1); s(COH, 0, 3, 1); s(DS, 4, 3, 1);
        s(GEM, 0, 3, 1); s(GPT, 0, 3, 1); s(BRAD, 0, 3, 1);
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
    /** Ability unlocks in order of value (map-wide boss deletion first). */
    private static final TowerType[] UNLOCK_ORDER = {
        TowerType.DEEPSEEK, TowerType.QWEN, TowerType.COHERE, TowerType.GPT, TowerType.GEMINI, TowerType.CLAUDE, TowerType.SORA,
        TowerType.GLM, TowerType.GROK, TowerType.LLAMA, TowerType.KIMI, TowerType.MINIMAX, TowerType.SUNO, TowerType.MISTRAL,
        TowerType.DALLE, TowerType.COPILOT, TowerType.PERPLEXITY,
    };

    private final Game g;
    private final Options o;
    private final List<Step> plan;
    private final boolean mixed;
    private final List<Vec> spots = new ArrayList<>();
    private final List<Vec> samples = new ArrayList<>();
    private Listener listener;
    private int livesAtWaveStart, livesPrevWave, trackedWave;
    /** (time, lives) samples for the time-window pressure test. */
    private final List<double[]> livesHistory = new ArrayList<>();
    private int actions;

    /** An AI that plays {@code game} with the given options (null = the near-optimal defaults). */
    public DefenderAI(Game game, Options options) {
        this.g = game;
        this.o = options == null ? new Options() : options;
        this.mixed = o.plan == Plan.MIXED;
        if (mixed) plan = MIXED_PLAN;
        else if (o.plan == Plan.REVERSE) plan = REVERSE_PLAN;
        else if (o.opening != null) { plan = new ArrayList<>(o.opening); plan.addAll(EFFICIENT_PLAN); }
        else plan = EFFICIENT_PLAN;
        livesAtWaveStart = livesPrevWave = game.getLives();
        trackedWave = 0;
        GameMap map = game.getMap();
        for (Path r : map.getRoutes()) for (double d = 0; d < r.getTotalLength(); d += 20) samples.add(r.positionAt(d));
        for (int x = 30; x < GameMap.WIDTH; x += 15) for (int y = 30; y < GameMap.HEIGHT; y += 15) {
            Vec p = new Vec(x, y);
            if (map.isBuildable(p, 20)) spots.add(p);
        }
    }

    /** Receives every action from now on (null to stop). */
    public void setListener(Listener l) { listener = l; }
    /** The options this AI was built with. */
    public Options getOptions() { return o; }
    /** Number of successful actions so far (builds, upgrades, hero purchases, unlocks, ability casts). */
    public int getActionCount() { return actions; }
    /** The build plan being followed (read-only view). */
    public List<Step> getPlan() { return java.util.Collections.unmodifiableList(plan); }

    // ------------------------------------------------------------------ one decision pass

    /** One decision pass: abilities and targeting (unless casual), then spending. Call every ~0.25-1 game seconds. */
    public void manage() {
        if (g.getState() != Game.State.PLAYING) return;
        if (g.getWave() != trackedWave) {          // lives lost over the last two waves = "under pressure"
            trackedWave = g.getWave();
            livesPrevWave = livesAtWaveStart;
            livesAtWaveStart = g.getLives();
        }
        if (o.pressureWindow > 0) {
            livesHistory.add(new double[] { g.getTime(), g.getLives() });
            while (livesHistory.size() > 1 && livesHistory.get(1)[0] <= g.getTime() - o.pressureWindow) livesHistory.remove(0);
        }
        if (!o.randomPlacement) { useAbilities(); setTargeting(); }     // a casual player rarely micro-manages
        purchase();
    }

    private int wave() { return o.waveSource != null ? o.waveSource.getAsInt() : g.getWave(); }

    private boolean underPressure() {
        if (o.pressureWindow > 0) return !livesHistory.isEmpty() && livesHistory.get(0)[1] - g.getLives() >= 2;
        return livesPrevWave - g.getLives() >= 2;
    }

    /** True if camo is expected within two waves (or the configured alarm says so). */
    private boolean camoExpected(int wave) {
        if (o.camoAlarm != null) return o.camoAlarm.getAsBoolean();
        for (int w = wave; w <= wave + 2; w++) if (camoWave(w)) return true;
        return false;
    }

    private List<Tower> mine() { return g.getTowerManager().getPlayerTowers(); }

    private Tower nth(TowerType type, int copy) {
        int i = 0;
        for (Tower t : mine()) if (t.getType() == type) { if (i == copy) return t; i++; }
        return null;
    }

    private int count(TowerType type) {
        int n = 0;
        for (Tower t : mine()) if (t.getType() == type) n++;
        return n;
    }

    /** True if the wave (1-based) contains camo enemies or a Lockheed Martin. */
    private static boolean camoWave(int wave) {
        if (wave < 1 || wave > WaveData.WAVE_COUNT) return false;
        WaveDef d = WaveData.get(wave);
        for (SpawnGroup gr : d.groups) if (gr.modifiers.contains(Modifier.CAMO) || gr.type.hasInnateCamo()) return true;
        return false;
    }

    /** True if some tower lets the defence hit camo across the map (Perplexity U1, or a Grok). */
    public boolean hasDetection() {
        for (Tower t : mine()) {
            if (t.getType() == TowerType.PERPLEXITY && t.getTier() >= 1) return true;   // U1: every tower can target all camo
            if (t.getType() == TowerType.GROK) return true;
        }
        return false;
    }

    private void purchase() {
        boolean random = o.randomPlacement;
        int wave = Math.max(1, wave());
        int towers = mine().size();
        // camo safety net: detection must exist before camo arrives (a casual player does not plan for camo, but does
        // react to an explicit alarm: reverse mode raises it once camo has been seen on the track)
        if ((!random || o.camoAlarm != null) && !hasDetection() && camoExpected(wave)) {
            Tower per = nth(TowerType.PERPLEXITY, 0);
            if (per == null) { if (towers < o.maxTowers && tryBuy(TowerType.PERPLEXITY)) return; if (g.getCash() < price(TowerType.PERPLEXITY)) return; }
            else if (per.canUpgrade() && upgrade(per)) return;
            else if (per.canUpgrade() && g.getCash() < Shop.upgradeCost(g, per)) return;
        }
        boolean pressure = underPressure();
        if (pressure && attackers() < 5 + wave / 4 && towers < o.maxTowers) {
            // leaking: stop investing in economy and add cheap firepower
            TowerType pick = null; int best = Integer.MAX_VALUE;
            for (TowerType tt : new TowerType[] { TowerType.GEMINI, TowerType.CLAUDE, TowerType.GPT, TowerType.COHERE }) {
                int c = count(tt); if (c < best) { best = c; pick = tt; }
            }
            if (g.getCash() >= price(pick)) { if (tryBuy(pick)) return; }
        }
        for (Step st : plan) {
            if (st.minWave > wave) continue;
            if (pressure && st.type == TowerType.PERPLEXITY && st.tier >= 2) continue;
            if (random && st.type == TowerType.PERPLEXITY) continue;
            if (o.maxTowers < 40 && st.type == TowerType.PERPLEXITY && st.copy >= 1) continue;   // slots are scarce: one research tower only
            Tower t = nth(st.type, st.copy);
            if (t == null) {
                if (st.type.isHero() && (count(st.type) > 0 || g.isHeroDeployed(st.type))) continue;   // once per match
                if (st.type.isHero() && g.getTowerManager().heroProblem(st.type) != null && g.isHeroUnlocked(st.type)) continue;   // hero cap reached
                if (st.copy > count(st.type)) continue;                      // copies are bought in order
                if (towers >= o.maxTowers) continue;                         // handicap: upgrades only
                if (!tryBuy(st.type)) { if (g.getCash() < price(st.type)) return; continue; }
                return;
            }
            if (t.getTier() >= st.tier) continue;
            if (upgrade(t)) return;
            if (o.verbose && g.getCash() > 2500 && g.getTick() % 600 == 0) System.out.println("      BLOCKED w" + wave + " on " + st.type + " copy " + st.copy + " tier " + st.tier + " cash " + g.getCash() + " cost " + t.nextUpgrade().cost);
            return;                                                             // save up for this upgrade
        }
        if (o.unlockAbilities && !pressure && tryAbilityUnlock()) return;
        overflow();
    }

    private int attackers() {
        int n = 0;
        for (Tower t : mine()) if (t.getType() != TowerType.PERPLEXITY) n++;
        return n;
    }

    /** Cash needed to get the type onto the map: Hero Store unlock price for a locked hero, else this match's price (PATCH NOTES can change it). */
    private int price(TowerType t) { return t.isHero() && !g.isHeroUnlocked(t) ? TowerCatalog.get(t).unlockCost : Shop.priceOf(g, t); }

    private boolean upgrade(Tower t) {
        if (!g.upgradeTower(t)) return false;
        report(Action.UPGRADE, t, "upgraded " + t.getType().displayName + " to " + t.getTierLabel());
        return true;
    }

    private boolean tryBuy(TowerType type) {
        if (g.getCash() < price(type)) return false;
        if (type.isHero() && g.isHeroDeployed(type)) return false;
        if (type.isHero() && !g.isHeroUnlocked(type)) {   // Hero Store first, but never past the per-game hero cap
            if (g.getTowerManager().heroesDeployedThisMatch() >= g.getHeroLimit()) return false;
            if (!g.purchaseHero(type)) return false;
            report(Action.HERO_UNLOCK, null, "unlocked hero " + type.displayName + " in the Hero Store");
        }
        Vec p = bestSpot(type);
        if (p == null) return false;
        Tower t = g.placeTower(type, p);
        if (o.verbose && t != null) System.out.printf("      buy w%d %s cash %.0f%n", g.getWave(), type, g.getCash());
        if (t != null) report(type.isHero() ? Action.HERO_DEPLOY : Action.BUILD, t, (type.isHero() ? "deployed hero " + type.displayName : "built " + t.getTierLabel()));
        return t != null;
    }

    /**
     * Saves for and buys a $15,000 ability unlock once a core is up ({@link Options#unlockMinTowers} towers, plus
     * {@link Options#unlockTowersPer} per unlock already bought): the first maxed tower in
     * {@link #UNLOCK_ORDER}. Returns true while it is saving or just bought (nothing else is bought this pass).
     */
    private boolean tryAbilityUnlock() {
        int unlocked = 0;
        for (Tower t : mine()) if (TowerCatalog.abilityNeedsUnlock(t.getType()) && !t.isAbilityLocked()) unlocked++;
        if (mine().size() < o.unlockMinTowers + o.unlockTowersPer * unlocked) return false;
        Tower pick = null;
        for (TowerType tt : UNLOCK_ORDER) {
            for (Tower t : mine()) if (t.getType() == tt && t.canUnlockAbility()) { pick = t; break; }
            if (pick != null) break;
        }
        if (pick == null) return false;
        if (g.getCash() < TowerCatalog.ABILITY_UNLOCK_COST) return true;   // save up
        if (!g.unlockAbility(pick)) return false;
        report(Action.ABILITY_UNLOCK, pick, "unlocked " + pick.getAbilityDef().name);
        return true;
    }

    /** Spend leftover cash: cheapest upgrade first, otherwise another tower from the rotation (least-represented first). */
    private void overflow() {
        Tower up = null;
        for (Tower t : mine()) if (t.canUpgrade() && (up == null || Shop.upgradeCost(g, t) < Shop.upgradeCost(g, up))) up = t;
        TowerType buy = null;
        if (mine().size() < o.maxTowers) {
            double bestRatio = Double.MAX_VALUE;
            for (TowerType tt : mixed ? OVERFLOW_MIXED : OVERFLOW_EFFICIENT) {
                if (!mixed && isControlTool(tt) && mine().size() < 30) continue;   // with a small roster, raw damage first
                double ratio = count(tt) / weight(tt);
                if (ratio < bestRatio) { bestRatio = ratio; buy = tt; }
            }
        }
        if (up != null && (buy == null || Shop.upgradeCost(g, up) <= price(buy) * 2.2)) { upgrade(up); return; }
        if (buy != null) tryBuy(buy);
        else if (up != null) upgrade(up);
    }

    private static boolean isControlTool(TowerType t) {
        return t == TowerType.GLM || t == TowerType.SORA || t == TowerType.GROK || t == TowerType.LLAMA;
    }

    /** Overflow weights: how many copies of a type per copy of a weight-1 type. DeepSeek (map-wide, x2 vs bosses) is the best late value per dollar. */
    private double weight(TowerType t) {
        switch (t) {
            case DEEPSEEK: return mixed ? 2 : 8;
            case QWEN: return mixed ? 1 : 2;
            default: return 1;
        }
    }

    // ------------------------------------------------------------------ targeting & abilities

    private void setTargeting() {
        boolean boss = false, ddt = false;
        for (Enemy e : g.getEnemyManager().getEnemies()) {
            if (e.isBoss() && !e.isStored()) boss = true;
            if (e.getType() == EnemyType.LOCKHEED_MARTIN) ddt = true;
        }
        for (Tower t : mine()) {
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
    private Vec densestSpot(int[] outCount) {
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

    private void useAbilities() {
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
                    if (g.getRoundPopValue() * 0.2 >= 800) cast(t, null);
                    continue;
                case DEEPSEEK:
                    if (alive >= 6) cast(t, null);
                    continue;
                case SORA:
                    if (leakRisk) cast(t, null);
                    continue;
                default: break;
            }
            if (!danger) continue;
            if (t.getAbility().needsTarget) {
                int[] n = new int[1];
                Vec spot = leadBoss != null && t.getType() == TowerType.MISTRAL ? leadBoss.getPosition() : densestSpot(n);
                if (spot != null && (boss || n[0] >= 8)) cast(t, spot);
            } else {
                cast(t, null);
            }
        }
    }

    private void cast(Tower t, Vec spot) {
        String name = t.getAbility().name;
        boolean ok = spot == null ? g.activateAbility(t) : g.activateAbility(t, spot);
        if (ok) report(Action.ABILITY_CAST, t, "cast " + name);
    }

    private void report(Action a, Tower t, String text) {
        actions++;
        if (listener != null) listener.onAction(a, t, text);
    }

    // ------------------------------------------------------------------ placement

    private Vec bestSpot(TowerType type) {
        double range = TowerCatalog.get(type).baseStats.range;
        if (o.randomPlacement) {
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
            for (Tower t : mine()) {
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
                for (Tower t : mine()) if (t.getPosition().dist(p) <= aura) score += 15;
            } else if (!mapWide) {
                for (Tower t : mine()) if (t.getStats().auraRange > 0 && t.getPosition().dist(p) <= t.getStats().auraRange) score += 10;
            }
            if (score > bestScore) { bestScore = score; best = p; }
        }
        return best;
    }
}
