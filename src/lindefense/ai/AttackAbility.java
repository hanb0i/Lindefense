package lindefense.ai;

/**
 * Reverse mode's attacker abilities ("exploits"): bought with compute credits, each on its own cooldown, unlocked
 * over the match like the units.
 * <ul>
 *   <li>{@link #OVERCLOCK}: every unit on the track moves 50% faster for 6 s.</li>
 *   <li>{@link #HOTFIX}: every unit on the track heals to full health.</li>
 *   <li>{@link #ZERO_DAY}: the defender's three most expensive towers are jammed for 6 s (Palantir's surveillance
 *       debuff: -50% attack speed, -30% range, abilities locked). Towers immune to surveillance (Perplexity U2) shrug
 *       it off.</li>
 * </ul>
 */
public enum AttackAbility {
    OVERCLOCK("Overclock", 300, 40, 6, 120, "All units on the track move 50% faster for 6 s."),
    HOTFIX("Hotfix", 600, 45, 0, 180, "Every unit on the track heals to full health."),
    ZERO_DAY("Zero-Day", 900, 60, 6, 240, "Jams the AI's 3 most expensive towers for 6 s.");

    /** Name shown on the button. */
    public final String displayName;
    /** Price in compute credits per use. */
    public final int cost;
    /** Cooldown in game seconds after a use. */
    public final double cooldown;
    /** Effect duration in seconds (0 = instant). */
    public final double duration;
    /** Match time (seconds) at which it becomes available. */
    public final double unlockAt;
    /** One-line description. */
    public final String description;

    /** Speed multiplier while {@link #OVERCLOCK} runs. */
    public static final double OVERCLOCK_SPEED = 1.5;
    /** Towers hit by {@link #ZERO_DAY}. */
    public static final int ZERO_DAY_TARGETS = 3;

    AttackAbility(String displayName, int cost, double cooldown, double duration, double unlockAt, String description) {
        this.displayName = displayName; this.cost = cost; this.cooldown = cooldown; this.duration = duration;
        this.unlockAt = unlockAt; this.description = description;
    }
}
