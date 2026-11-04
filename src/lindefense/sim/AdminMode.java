package lindefense.sim;

/**
 * Admin mode, unlocked by typing the admin code in SETTINGS on the main menu. While it is on, every match started from
 * the map select screen gets unlimited credits (nothing costs anything, so every tower can be bought and fully
 * upgraded) and every Hero Store hero counts as unlocked. The switch is remembered between sessions with
 * {@code java.util.prefs} (node {@code lindefense/admin}); turning it off restores normal play and never touches the
 * player's real Hero Store purchases.
 *
 * <p>Only the windowed game applies it ({@link Game#setAdmin}); tests, tools and the tutorial never do.</p>
 */
public final class AdminMode {
    private AdminMode() { }

    /** The admin code (case-insensitive, surrounding spaces ignored). */
    static final String CODE = "lindeveloper";

    private static final String PREFS_NODE = "lindefense/admin";
    private static final String PREFS_KEY = "enabled";
    private static Boolean enabled;

    /** True if admin mode is on. */
    public static synchronized boolean isEnabled() {
        if (enabled == null) {
            boolean v = false;
            try { v = java.util.prefs.Preferences.userRoot().node(PREFS_NODE).getBoolean(PREFS_KEY, false); } catch (RuntimeException ignored) { }
            enabled = v;
        }
        return enabled;
    }

    /** True if {@code code} is the admin code. */
    public static boolean matches(String code) { return code != null && code.trim().equalsIgnoreCase(CODE); }

    /** Turns admin mode on if the code is right; returns whether it was accepted. */
    public static boolean tryCode(String code) {
        if (!matches(code)) return false;
        set(true);
        return true;
    }

    /** Turns admin mode off. */
    public static void disable() { set(false); }

    private static synchronized void set(boolean v) {
        enabled = v;
        try { java.util.prefs.Preferences.userRoot().node(PREFS_NODE).putBoolean(PREFS_KEY, v); } catch (RuntimeException ignored) { }
    }
}
