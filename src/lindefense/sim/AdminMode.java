package lindefense.sim;

/**
 * Admin mode, unlocked by typing the admin code in SETTINGS on the main menu. Entering the code reveals a checklist
 * of cheats that can be switched on and off independently:
 *
 * <ul>
 *   <li>{@link Option#UNLOCK_HEROES}: every Hero Store hero counts as unlocked (the saved collection is never touched,
 *       so switching this off restores exactly what the player really bought).</li>
 *   <li>{@link Option#INFINITE_MONEY}: nothing costs anything, so every tower, hero upgrade and placement is free.</li>
 *   <li>{@link Option#INFINITE_HEALTH}: leaks never reduce integrity below 1, so a run cannot be lost.</li>
 * </ul>
 *
 * <p>Whether the code has been entered, and which options are ticked, are remembered between sessions with
 * {@code java.util.prefs} (node {@code lindefense/admin}). Only the windowed game applies them
 * ({@link Game#setAdmin}); tests, tools and the tutorial never do.</p>
 */
public final class AdminMode {
    private AdminMode() { }

    /** One switchable cheat. */
    public enum Option {
        UNLOCK_HEROES("Unlock all heroes", "Every Hero Store hero is available to deploy. Your real purchases are left untouched."),
        INFINITE_MONEY("Infinite money", "Credits never run out, so every tower, hero and upgrade is free."),
        INFINITE_HEALTH("Infinite health", "Leaks can never take your last integrity, so the run cannot be lost.");

        public final String label, description;
        Option(String label, String description) { this.label = label; this.description = description; }
        String key() { return "opt." + name(); }
    }

    /** The admin code (case-insensitive, surrounding spaces ignored). */
    static final String CODE = "lindeveloper";

    private static final String PREFS_NODE = "lindefense/admin";
    private static final String UNLOCKED_KEY = "unlocked";
    private static Boolean unlocked;
    private static final java.util.EnumMap<Option, Boolean> OPTIONS = new java.util.EnumMap<>(Option.class);

    private static java.util.prefs.Preferences prefs() { return java.util.prefs.Preferences.userRoot().node(PREFS_NODE); }

    /** True once the admin code has been entered (the checklist is then shown in SETTINGS). */
    public static synchronized boolean isUnlocked() {
        if (unlocked == null) {
            boolean v = false;
            try { v = prefs().getBoolean(UNLOCKED_KEY, false); } catch (RuntimeException ignored) { }
            unlocked = v;
        }
        return unlocked;
    }

    /** True if {@code code} is the admin code. */
    public static boolean matches(String code) { return code != null && code.trim().equalsIgnoreCase(CODE); }

    /** Unlocks the checklist if the code is right; returns whether it was accepted. */
    public static synchronized boolean tryCode(String code) {
        if (!matches(code)) return false;
        unlocked = true;
        try { prefs().putBoolean(UNLOCKED_KEY, true); } catch (RuntimeException ignored) { }
        return true;
    }

    /** Whether one cheat is switched on (always false until the code has been entered). */
    public static synchronized boolean isOn(Option o) {
        if (!isUnlocked()) return false;
        Boolean v = OPTIONS.get(o);
        if (v == null) {
            boolean b = false;
            try { b = prefs().getBoolean(o.key(), false); } catch (RuntimeException ignored) { }
            OPTIONS.put(o, b);
            return b;
        }
        return v;
    }

    /** Switches one cheat on or off. */
    public static synchronized void set(Option o, boolean on) {
        OPTIONS.put(o, on);
        try { prefs().putBoolean(o.key(), on); } catch (RuntimeException ignored) { }
    }

    /** Flips one cheat and returns its new state. */
    public static synchronized boolean toggle(Option o) {
        boolean v = !isOn(o);
        set(o, v);
        return v;
    }

    /** True if any cheat is currently on. */
    public static boolean anyOn() {
        for (Option o : Option.values()) if (isOn(o)) return true;
        return false;
    }

    /** Switches every cheat off and locks the checklist again (the code must be re-entered). */
    public static synchronized void disableAll() {
        for (Option o : Option.values()) set(o, false);
        unlocked = false;
        try { prefs().putBoolean(UNLOCKED_KEY, false); } catch (RuntimeException ignored) { }
    }
}
