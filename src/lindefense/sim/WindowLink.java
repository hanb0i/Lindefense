package lindefense.sim;

import lindefense.enemy.Boss;

/**
 * The simulation's only view of the real game window, for Palantir's fourth-wall break (phase 3, System Takeover).
 * The simulation never touches a window: Palantir asks for a grab ({@link #requestGrab}) and the windowed UI, if it
 * performs one, reports how large the window is compared with its size before the takeover
 * ({@link #setFraction}, 1.0 = untouched). Headless runs, tests, the bot and the scripted demo never report anything,
 * so the fraction stays 1.0 and Palantir is never sealed there.
 *
 * <p>Seal rule: while Palantir's takeover is active and the reported fraction is below {@link #SEAL_THRESHOLD},
 * Palantir is <b>sealed</b> (see {@link lindefense.enemy.PalantirProtocols}). The player breaks the seal by dragging the
 * window back to at least that size.</p>
 */
public final class WindowLink {
    /** Palantir is sealed while the window is smaller than this fraction of its pre-takeover size. */
    public static final double SEAL_THRESHOLD = 0.85;

    private double fraction = 1.0;
    private int grabRequests;
    private Boss owner;

    /**
     * Reported by the UI: the window's size relative to its pre-takeover size (the smaller of the width and height
     * ratios). Values are clamped to [0.05, 4]; NaN is ignored.
     */
    public void setFraction(double f) {
        if (Double.isNaN(f)) return;
        fraction = Math.max(0.05, Math.min(4, f));
    }

    /** The last reported window fraction (1.0 unless a windowed UI shrank the window). */
    public double getFraction() { return fraction; }

    /** Palantir starts (or renews) its takeover and asks the UI to grab the window. */
    public void requestGrab(Boss by) {
        owner = by;
        grabRequests++;
    }

    /** Returns and clears the number of grab requests since the last call (the UI polls this every frame). */
    public int consumeGrabRequests() {
        int n = grabRequests;
        grabRequests = 0;
        return n;
    }

    /** Grab requests not yet consumed by a UI. */
    public int pendingGrabRequests() { return grabRequests; }

    /** True while the Palantir that started a takeover is still alive on the track. */
    public boolean isTakeoverActive() { return owner != null && owner.isAlive() && !owner.hasLeaked(); }

    /** True when Palantir should be sealed now: an active takeover and a window below {@link #SEAL_THRESHOLD}. */
    public boolean isSealing() { return isTakeoverActive() && fraction < SEAL_THRESHOLD; }
}
