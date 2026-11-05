package lindefense.variance;

import java.util.ArrayList;
import java.util.List;
import lindefense.tower.Shop;

/**
 * A set of {@link Knob} values: what one patch note or one news event changes. Unset knobs are neutral (multipliers 1,
 * additions 0), so {@link #NONE} changes nothing. The run combines the active card and event sets with
 * {@link #combine}. {@link #effects(int)} turns the numbers into readable lines, each marked good or bad for the player:
 * card and ticker text are generated from the same numbers the game applies.
 */
public final class Mods {
    /** Changes nothing. Never modify it. */
    public static final Mods NONE = new Mods();

    /** One readable line of a card or event, and whether it helps the player. */
    public static final class Effect {
        /** Readable text, e.g. "Towers fire 20% faster". */
        public final String text;
        /** True for an upside, false for a downside. */
        public final boolean good;

        Effect(String text, boolean good) { this.text = text; this.good = good; }

        @Override public String toString() { return (good ? "+ " : "- ") + text; }
    }

    private final double[] v = new double[Knob.values().length];

    private Mods() {
        for (Knob k : Knob.values()) v[k.ordinal()] = k.neutral();
    }

    /** A fresh, neutral set to fill with {@link #set} / {@link #flag} (table definitions only). */
    public static Mods of() { return new Mods(); }

    /** Sets a knob (definition time only) and returns this set. */
    public Mods set(Knob k, double value) {
        if (this == NONE) throw new IllegalStateException("Mods.NONE is immutable");
        v[k.ordinal()] = value;
        return this;
    }

    /** Turns a flag knob on and returns this set. */
    public Mods flag(Knob k) { return set(k, 1); }

    /** The knob's value (its neutral value if unset). */
    public double get(Knob k) { return v[k.ordinal()]; }

    /** True if the knob differs from neutral. */
    public boolean has(Knob k) { return v[k.ordinal()] != k.neutral(); }

    /** True if nothing is changed. */
    public boolean isNeutral() {
        for (Knob k : Knob.values()) if (has(k)) return false;
        return true;
    }

    /** A new set with both sets applied (multipliers multiply, additions add, flags or). */
    public Mods combine(Mods o) {
        Mods m = new Mods();
        for (Knob k : Knob.values()) m.v[k.ordinal()] = k.combine(v[k.ordinal()], o.v[k.ordinal()]);
        return m;
    }

    /** A copy with every knob held inside its {@link Knob#min} / {@link Knob#max} bounds (the run's combined set). */
    public Mods clamped() {
        Mods m = new Mods();
        for (Knob k : Knob.values()) m.v[k.ordinal()] = Math.max(k.min, Math.min(k.max, v[k.ordinal()]));
        return m;
    }

    /**
     * One-off credits this set grants when taken just before {@code wave} starts:
     * {@code CASH_NOW + CASH_PER_WAVE x (waves already played)}.
     */
    public int cashFor(int wave) { return (int) Math.round(get(Knob.CASH_NOW) + get(Knob.CASH_PER_WAVE) * Math.max(0, wave - 1)); }

    // ------------------------------------------------------------------ text
    /** The upsides only. */
    public List<Effect> upsides(int wave) { return filter(wave, true); }

    /** The downsides only. */
    public List<Effect> downsides(int wave) { return filter(wave, false); }

    private List<Effect> filter(int wave, boolean good) {
        List<Effect> out = new ArrayList<>();
        for (Effect e : effects(wave)) if (e.good == good) out.add(e);
        return out;
    }

    /**
     * Every change as a readable line. Pairs that move together read as one line ("Towers and upgrades cost 15% less",
     * "Income +20%"). {@code wave} prices the one-off credits.
     */
    public List<Effect> effects(int wave) {
        List<Effect> out = new ArrayList<>();
        // economy
        if (has(Knob.TOWER_COST) && get(Knob.TOWER_COST) == get(Knob.UPGRADE_COST)) {
            add(out, Knob.TOWER_COST, "Towers and upgrades cost " + lessMore(get(Knob.TOWER_COST)));
        } else {
            if (has(Knob.TOWER_COST)) add(out, Knob.TOWER_COST, "Towers cost " + lessMore(get(Knob.TOWER_COST)));
            if (has(Knob.UPGRADE_COST)) add(out, Knob.UPGRADE_COST, "Upgrades cost " + lessMore(get(Knob.UPGRADE_COST)));
        }
        if (has(Knob.ABILITY_UNLOCK_COST)) add(out, Knob.ABILITY_UNLOCK_COST, "Ability unlocks cost " + lessMore(get(Knob.ABILITY_UNLOCK_COST)));
        if (has(Knob.SELL_REFUND)) {
            double base = Shop.SELL_FRACTION, now = Math.max(0, Math.min(RunVariance.MAX_SELL_FRACTION, base + get(Knob.SELL_REFUND)));
            add(out, Knob.SELL_REFUND, "Sell refund " + Math.round(base * 100) + "% -> " + Math.round(now * 100) + "%");
        }
        if (has(Knob.KILL_INCOME) && get(Knob.KILL_INCOME) == get(Knob.WAVE_BONUS)) {
            add(out, Knob.KILL_INCOME, "Income " + signed(get(Knob.KILL_INCOME)) + " (kills and wave bonus)");
        } else {
            if (has(Knob.KILL_INCOME)) add(out, Knob.KILL_INCOME, "Kills pay " + lessMore(get(Knob.KILL_INCOME)));
            if (has(Knob.WAVE_BONUS)) add(out, Knob.WAVE_BONUS, get(Knob.WAVE_BONUS) <= 0 ? "No wave-clear bonus" : "Wave-clear bonus " + signed(get(Knob.WAVE_BONUS)));
        }
        if (has(Knob.INTEREST_RATE)) {
            String cap = has(Knob.INTEREST_CAP) ? " (max " + money(get(Knob.INTEREST_CAP)) + ")" : "";
            add(out, Knob.INTEREST_RATE, "Banked credits earn " + Math.round(get(Knob.INTEREST_RATE) * 100) + "% interest per wave cleared" + cap);
        }
        int cash = cashFor(wave);
        if (cash != 0) out.add(new Effect((cash > 0 ? "+" : "-") + money(Math.abs(cash)) + " credits now", cash > 0));
        // combat
        if (has(Knob.DAMAGE)) add(out, Knob.DAMAGE, "Towers deal " + lessMore(get(Knob.DAMAGE)) + " damage");
        if (has(Knob.BOSS_DAMAGE)) add(out, Knob.BOSS_DAMAGE, signed(get(Knob.BOSS_DAMAGE)) + " damage vs bosses");
        if (has(Knob.NON_BOSS_DAMAGE)) add(out, Knob.NON_BOSS_DAMAGE, signed(get(Knob.NON_BOSS_DAMAGE)) + " damage vs non-boss enemies");
        if (has(Knob.ELITE_DAMAGE)) add(out, Knob.ELITE_DAMAGE, signed(get(Knob.ELITE_DAMAGE)) + " damage vs Camo, Regrow and Fortified enemies");
        if (has(Knob.PLAIN_DAMAGE)) add(out, Knob.PLAIN_DAMAGE, signed(get(Knob.PLAIN_DAMAGE)) + " damage vs unmodified enemies");
        if (has(Knob.FIRE_RATE)) add(out, Knob.FIRE_RATE, "Towers fire " + pct(get(Knob.FIRE_RATE)) + (get(Knob.FIRE_RATE) > 1 ? " faster" : " slower"));
        if (has(Knob.RANGE)) add(out, Knob.RANGE, "Tower range " + signed(get(Knob.RANGE)));
        if (has(Knob.ABILITY_COOLDOWN)) add(out, Knob.ABILITY_COOLDOWN, "Ability cooldowns " + signed(get(Knob.ABILITY_COOLDOWN)));
        if (has(Knob.REFRESH_ABILITIES)) add(out, Knob.REFRESH_ABILITIES, "Every ability cooldown resets when the wave starts");
        if (has(Knob.FREE_FIRST_UPGRADE)) add(out, Knob.FREE_FIRST_UPGRADE, "New shop towers arrive with their first upgrade free");
        // enemies
        if (has(Knob.ENEMY_HP)) add(out, Knob.ENEMY_HP, "Enemies have " + lessMore(get(Knob.ENEMY_HP)) + " HP");
        if (has(Knob.ENEMY_SPEED)) add(out, Knob.ENEMY_SPEED, "Enemies move " + pct(get(Knob.ENEMY_SPEED)) + (get(Knob.ENEMY_SPEED) > 1 ? " faster" : " slower"));
        if (has(Knob.ENEMY_COUNT)) add(out, Knob.ENEMY_COUNT, pct(get(Knob.ENEMY_COUNT)) + (get(Knob.ENEMY_COUNT) > 1 ? " more" : " fewer") + " enemies");
        if (has(Knob.SPAWN_GAP)) add(out, Knob.SPAWN_GAP, "Enemies spawn " + pct(get(Knob.SPAWN_GAP)) + (get(Knob.SPAWN_GAP) < 1 ? " closer together" : " further apart"));
        if (has(Knob.ALL_CAMO)) add(out, Knob.ALL_CAMO, "Every non-boss enemy is Camo");
        if (has(Knob.CLOSE_LANE)) add(out, Knob.CLOSE_LANE, "One lane is closed: enemies crowd the others");
        // integrity
        if (has(Knob.LIVES_PER_WAVE)) add(out, Knob.LIVES_PER_WAVE, "+" + (int) get(Knob.LIVES_PER_WAVE) + " integrity per wave cleared (can exceed the maximum)");
        if (has(Knob.LEAK_LIVES)) add(out, Knob.LEAK_LIVES, "Leaks cost " + pct(get(Knob.LEAK_LIVES)) + (get(Knob.LEAK_LIVES) < 1 ? " fewer" : " more") + " lives (min 1)");
        return out;
    }

    private void add(List<Effect> out, Knob k, String text) { out.add(new Effect(text, k.helps(get(k)))); }

    /** "15%" for 0.85 or 1.15. */
    static String pct(double mult) { return Math.round(Math.abs(mult - 1) * 100) + "%"; }

    /** "15% less" / "15% more". */
    private static String lessMore(double mult) { return pct(mult) + (mult < 1 ? " less" : " more"); }

    /** "+40%" / "-15%". */
    private static String signed(double mult) { return (mult >= 1 ? "+" : "-") + pct(mult); }

    private static String money(double v) { return "$" + String.format("%,d", Math.round(v)); }

    @Override public String toString() { return effects(0).toString(); }
}
