package lindefense.tower;

/**
 * A tower's prompt-injection / takeover state. Towers have no health, so the cyber attacks of the late game take
 * towers <b>offline</b> for a few seconds instead of damaging them:
 * <ul>
 *   <li><b>Hijacked</b> (a Prompt Injection enemy or Palantir's Prompt Broadcast): the tower stops attacking enemies
 *       and instead zaps a neighbouring tower a couple of times, which disables that neighbour.</li>
 *   <li><b>Disabled</b> (zapped by a hijacked neighbour): no attacks, no ability. A disabled tower never becomes
 *       hijacked itself, so a hijack chain is always one hop long.</li>
 *   <li><b>Blinded</b> (swept by Palantir's Panopticon beam): no attacks, no ability.</li>
 * </ul>
 * The three states never overlap: a tower can only be compromised while it is online and not <b>patched</b>, and
 * every intrusion is followed by {@link #GRACE} seconds of patch time in which nothing can take the tower offline
 * again. So no tower can ever be locked out for more than one intrusion in a row. While offline a tower does nothing to
 * enemies (no attack, no periodic strikes, no enemy field, no ability); the buffs its aura gives other towers stay.
 *
 * <p>The rules that decide <i>who</i> gets compromised live in {@link lindefense.sim.PromptInjection} and
 * {@link lindefense.enemy.PalantirProtocols}; this class only keeps the timers and the bookkeeping the renderer
 * needs (who hijacked the tower, whom it zapped last).</p>
 */
public final class Intrusion {
    /** Seconds after any intrusion ends during which the tower cannot be hijacked, disabled or blinded again. */
    public static final double GRACE = 4.0;

    private double hijacked, disabled, blinded, grace;
    private Object hijacker;
    private Tower disabledBy;
    private double zapTimer;
    private int zapsLeft;
    private boolean firewalled;
    private Tower lastVictim;
    private double lastZapAge = 99;
    private double age = 99;
    private double total;

    // ---------------- queries ----------------
    /** True while the tower obeys an injected prompt (it zaps its neighbours instead of attacking). */
    public boolean isHijacked() { return hijacked > 0; }
    /** True while the tower is disabled by a hijacked neighbour's zap. */
    public boolean isDisabled() { return disabled > 0; }
    /** True while the tower is blinded by Palantir's Panopticon beam. */
    public boolean isBlinded() { return blinded > 0; }
    /** True while the tower cannot attack or use its ability (hijacked, disabled or blinded). */
    public boolean isOffline() { return hijacked > 0 || disabled > 0 || blinded > 0; }
    /** True during the patch window after an intrusion (nothing can take the tower offline again yet). */
    public boolean isPatched() { return grace > 0; }
    /** True if the tower is online and not patched, i.e. an intrusion would take effect now. */
    public boolean canBeCompromised() { return !isOffline() && grace <= 0; }
    /** Seconds left on the current intrusion (0 when online). */
    public double getRemaining() { return Math.max(hijacked, Math.max(disabled, blinded)); }
    /** Seconds left in the patch window (0 when not patched). */
    public double getGraceRemaining() { return grace; }
    /** Seconds since the current intrusion started (for animations). */
    public double getAge() { return age; }
    /** The enemy (or Palantir) whose prompt hijacked the tower, or null. */
    public Object getHijacker() { return isHijacked() ? hijacker : null; }
    /** The hijacked tower that disabled this one, or null. */
    public Tower getDisabledBy() { return isDisabled() ? disabledBy : null; }
    /** The tower this hijacked tower zapped most recently (for the beam), or null. */
    public Tower getLastVictim() { return lastVictim; }
    /** Seconds since the last zap (large when it never zapped). */
    public double getLastZapAge() { return lastZapAge; }
    /** Zaps this tower still owes its neighbours during the current hijack. */
    public int getZapsLeft() { return isHijacked() ? zapsLeft : 0; }
    /** Total seconds this tower has spent offline (all intrusions). */
    public double getTotalOfflineTime() { return total; }
    /** True while the tower stands inside a Copilot firewall aura (recomputed with the auras). */
    public boolean isFirewalled() { return firewalled; }

    // ---------------- mutators (used by the injection / Palantir rules) ----------------
    /**
     * Hijacks the tower for {@code seconds}: it will zap a neighbour {@code zaps} times, the first after
     * {@code firstZap} seconds. Returns false (and changes nothing) unless {@link #canBeCompromised()}.
     */
    public boolean hijack(double seconds, Object source, double firstZap, int zaps) {
        if (seconds <= 0 || !canBeCompromised()) return false;
        hijacked = seconds;
        hijacker = source;
        zapTimer = firstZap;
        zapsLeft = zaps;
        lastVictim = null;
        lastZapAge = 99;
        age = 0;
        return true;
    }

    /** Disables the tower for {@code seconds} (zapped by {@code by}). Returns false unless {@link #canBeCompromised()}. */
    public boolean disable(double seconds, Tower by) {
        if (seconds <= 0 || !canBeCompromised()) return false;
        disabled = seconds;
        disabledBy = by;
        age = 0;
        return true;
    }

    /** Blinds the tower for {@code seconds}. Returns false unless {@link #canBeCompromised()}. */
    public boolean blind(double seconds) {
        if (seconds <= 0 || !canBeCompromised()) return false;
        blinded = seconds;
        age = 0;
        return true;
    }

    /**
     * Advances the hijacked tower's zap timer; returns true when a zap is due now (the caller picks the victim and
     * reports it with {@link #recordZap}).
     */
    public boolean zapDue(double dt) {
        if (!isHijacked() || zapsLeft <= 0) return false;
        zapTimer -= dt;
        if (zapTimer > 0) return false;
        zapsLeft--;
        zapTimer = Double.MAX_VALUE;   // the caller sets the next interval through recordZap
        return true;
    }

    /** Records a zap (victim may be null when no neighbour was in reach) and schedules the next one. */
    public void recordZap(Tower victim, double nextIn) {
        if (victim != null) { lastVictim = victim; lastZapAge = 0; }
        zapTimer = nextIn;
    }

    /** Ends every intrusion at once (upgrading or re-placing a tower patches it, like Surveillance). */
    public void clear() {
        boolean was = isOffline();
        hijacked = disabled = blinded = 0;
        if (was) grace = GRACE;
    }

    void setFirewalled(boolean on) { firewalled = on; }

    /** Counts the timers down (game time). An intrusion that just ended starts the patch window. */
    void tick(double dt) {
        age += dt;
        lastZapAge += dt;
        boolean was = isOffline();
        if (was) total += dt;
        if (hijacked > 0) hijacked = Math.max(0, hijacked - dt);
        if (disabled > 0) disabled = Math.max(0, disabled - dt);
        if (blinded > 0) blinded = Math.max(0, blinded - dt);
        if (grace > 0) grace = Math.max(0, grace - dt);
        if (was && !isOffline()) grace = GRACE;
    }
}
