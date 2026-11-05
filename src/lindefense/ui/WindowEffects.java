package lindefense.ui;

/**
 * SETTINGS > WINDOW EFFECTS: whether Palantir's System Takeover may grab and shrink the real game window (default
 * ON). Remembered between sessions with {@code java.util.prefs} (node {@code lindefense/settings}, like the other
 * settings). Switching it off disables the grab entirely, so Palantir is then never sealed by it.
 * {@code -Dlindefense.windowfx=false} forces it off for one run without touching the saved choice.
 */
public final class WindowEffects {
    /** System property that forces window effects off for one run ({@code -Dlindefense.windowfx=false}). */
    public static final String PROPERTY = "lindefense.windowfx";
    private static final String PREFS_NODE = "lindefense/settings";
    private static final String KEY = "windowEffects";
    private static Boolean on;

    private WindowEffects() { }

    private static java.util.prefs.Preferences prefs() { return java.util.prefs.Preferences.userRoot().node(PREFS_NODE); }

    /** True if the window grab may run (the saved setting, default ON, unless the property forces it off). */
    public static synchronized boolean isEnabled() {
        if ("false".equalsIgnoreCase(System.getProperty(PROPERTY))) return false;
        if (on == null) {
            boolean v = true;
            try { v = prefs().getBoolean(KEY, true); } catch (RuntimeException ignored) { }
            on = v;
        }
        return on;
    }

    /** Saves the setting. */
    public static synchronized void setEnabled(boolean enabled) {
        on = enabled;
        try { prefs().putBoolean(KEY, enabled); } catch (RuntimeException ignored) { }
    }

    /** Flips and saves the setting; returns the new value. */
    public static synchronized boolean toggle() {
        boolean v = !isEnabled();
        setEnabled(v);
        return v;
    }
}
