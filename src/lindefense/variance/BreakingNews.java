package lindefense.variance;

import static lindefense.variance.Knob.*;

import java.util.ArrayList;
import java.util.List;
import lindefense.sim.Rng;
import lindefense.wave.WaveData;

/**
 * "Breaking News": one-wave random events. From wave {@link RunVariance#NEWS_FIRST_WAVE} on, each wave has a
 * {@link RunVariance#NEWS_CHANCE} chance of an event, rolled when the previous wave is cleared (so the ticker announces
 * it during the build phase) and active until that wave is cleared. Each event is small on its own: the harsh ones never
 * land on a boss wave ({@link #onBossWaves}), Camo-for-all waits until detection is mandatory anyway, and closing a
 * lane needs a map with more than one.
 */
public enum BreakingNews {
    GPU_SHORTAGE("GPU shortage", "Chip fabs sold out overnight.", 6, true, false,
        Mods.of().set(UPGRADE_COST, 1.25)),
    VIRAL_MEME("Viral meme", "Every enemy is wearing the same disguise.", 35, false, false,
        Mods.of().flag(ALL_CAMO)),
    SERVER_OUTAGE("Server outage", "A whole region just went dark.", 6, false, true,
        Mods.of().flag(CLOSE_LANE)),
    SOLAR_FLARE("Solar flare", "Every scheduler rebooted at once.", 25, true, false,
        Mods.of().flag(REFRESH_ABILITIES)),
    FUNDING_ROUND("Funding round", "A Series C closed over lunch.", 6, true, false,
        Mods.of().set(CASH_NOW, 400).set(CASH_PER_WAVE, 40)),
    DDOS("DDoS attack", "Traffic spike: they are coming in hot.", 6, false, false,
        Mods.of().set(ENEMY_SPEED, 1.30)),
    BUG_BOUNTY("Bug bounty", "Every squashed bug pays out.", 6, true, false,
        Mods.of().set(KILL_INCOME, 1.50)),
    HEATWAVE("Datacenter heatwave", "The chillers cannot keep up.", 6, false, false,
        Mods.of().set(FIRE_RATE, 0.85)),
    OVERCLOCK("Overclock", "Someone disabled the thermal limits.", 6, true, false,
        Mods.of().set(FIRE_RATE, 1.20)),
    HYPE_CYCLE("Hype cycle", "Everyone wants in. Everyone pays.", 10, false, false,
        Mods.of().set(ENEMY_COUNT, 1.30).set(KILL_INCOME, 1.30)),
    ACQUIHIRE("Acqui-hire", "Big Tech buys your old hardware at a premium.", 6, true, false,
        Mods.of().set(SELL_REFUND, 0.25)),
    DATA_BREACH("Data breach", "The enemy read your training set.", 15, false, false,
        Mods.of().set(ENEMY_HP, 1.20)),
    LATENCY_SPIKE("Latency spike", "Packets crawl across the ocean.", 6, false, false,
        Mods.of().set(RANGE, 0.90)),
    WEIGHTS_LEAK("Weights leaked", "Someone torrented the checkpoints.", 6, true, false,
        Mods.of().set(UPGRADE_COST, 0.80));

    /** Headline name. */
    public final String title;
    /** One-line flavour text. */
    public final String flavor;
    /** First wave the event may appear on. */
    public final int minWave;
    /** True if the event may land on a wave with a boss (only harmless or helpful ones). */
    public final boolean onBossWaves;
    /** True if the event needs a map with more than one lane. */
    public final boolean needsLanes;
    private final Mods mods;

    BreakingNews(String title, String flavor, int minWave, boolean onBossWaves, boolean needsLanes, Mods mods) {
        this.title = title; this.flavor = flavor; this.minWave = minWave; this.onBossWaves = onBossWaves; this.needsLanes = needsLanes; this.mods = mods;
    }

    /** What the event changes while it is active (do not modify). */
    public Mods mods() { return mods; }

    /** True if the event may be rolled for this wave. */
    public boolean eligible(int wave, boolean bossWave, int routes) {
        return wave >= minWave && (onBossWaves || !bossWave) && (!needsLanes || routes > 1);
    }

    /** "GPU SHORTAGE: Upgrades cost 25% more" (all effect lines, priced for {@code wave}). */
    public String headline(int wave) {
        StringBuilder sb = new StringBuilder(title.toUpperCase());
        String sep = ": ";
        for (Mods.Effect e : mods.effects(wave)) { sb.append(sep).append(e.text); sep = ", "; }
        return sb.toString();
    }

    /** The outcome of a news roll: the event and, for a lane closure, which lane. */
    public static final class Roll {
        /** The event. */
        public final BreakingNews news;
        /** Closed lane index, or -1. */
        public final int lane;

        Roll(BreakingNews news, int lane) { this.news = news; this.lane = lane; }
    }

    /**
     * Rolls the news for a wave from its own seeded stream ({@code (seed, wave)} only), so a run's events depend on the
     * seed and the map, never on how the fight went. Returns null for a quiet wave.
     */
    public static Roll roll(long seed, int wave, boolean bossWave, int routes) {
        if (wave < RunVariance.NEWS_FIRST_WAVE || wave >= WaveData.WAVE_COUNT) return null;
        Rng r = new Rng(RunVariance.mix(seed, wave, RunVariance.NEWS_SALT));
        if (!r.chance(RunVariance.NEWS_CHANCE)) return null;
        List<BreakingNews> pool = new ArrayList<>();
        for (BreakingNews n : values()) if (n.eligible(wave, bossWave, routes)) pool.add(n);
        if (pool.isEmpty()) return null;
        BreakingNews pick = pool.get(r.nextInt(pool.size()));
        int lane = pick.mods.has(CLOSE_LANE) ? r.nextInt(Math.max(1, routes)) : -1;
        return new Roll(pick, lane);
    }
}
