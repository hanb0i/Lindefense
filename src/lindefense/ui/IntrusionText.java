package lindefense.ui;

import lindefense.tower.Intrusion;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;

/**
 * Player-facing text for prompt injection, shared by the side panel and the catalog so both say the same thing:
 * a placed tower's live state (hijacked / disabled / blinded), and whether a tower type is immune and why.
 */
public final class IntrusionText {
    /** The headline every immune tower shows. */
    public static final String IMMUNE = "IMMUNE TO PROMPT INJECTION";

    private IntrusionText() { }

    /**
     * The side-panel line for a placed tower: its current intrusion if it is offline, otherwise its immunity (own or
     * from a Copilot firewall), or null if it has neither.
     */
    public static String towerLine(Tower t) {
        Intrusion in = t.getIntrusion();
        int s = (int) Math.ceil(in.getRemaining());
        if (in.isHijacked()) return "HIJACKED " + s + "s: it obeys an injected prompt and fires on your towers";
        if (in.isDisabled()) return "DISABLED " + s + "s: zapped by a hijacked neighbour";
        if (in.isBlinded()) return "BLINDED " + s + "s: swept by Palantir's Panopticon";
        if (t.getStats().injectionImmune) return IMMUNE + "  //  " + t.getStats().injectionImmuneReason;
        if (in.isFirewalled()) return IMMUNE + "  //  protected by a Copilot firewall";
        return null;
    }

    /** True if {@link #towerLine} describes a problem (the tower is offline) rather than a protection. */
    public static boolean isWarning(Tower t) { return t.isOffline(); }

    /** Immunity line for a tower type (shop preview, catalog), or null if the type can be hijacked. */
    public static String typeLine(TowerType type) {
        String why = TowerCatalog.injectionImmunityReason(type);
        return why == null ? null : IMMUNE + "  //  " + why;
    }

    /** Extra line for a type whose aura shields other towers (Copilot's firewall), or null. */
    public static String firewallLine(TowerType type) {
        return TowerCatalog.grantsInjectionFirewall(type)
            ? "Firewall: every tower inside its tether radius is immune to prompt injection too." : null;
    }

    /** One line for a type that can be hijacked (catalog), pointing at the counters. */
    public static String vulnerableLine() {
        return "Can be hijacked by Prompt Injection enemies (wave 30+) and Palantir. A Copilot firewall nearby protects it.";
    }

    /** Info-panel line for an enemy carrying the Prompt Injection sign, or null. */
    public static String enemyLine(lindefense.enemy.Enemy e) {
        if (!e.has(lindefense.enemy.Modifier.INJECTION)) return null;
        return "Holds an \"" + lindefense.sim.PromptInjection.SIGN + "\" sign: every " + (int) lindefense.sim.PromptInjection.INTERVAL
            + " s it hijacks the " + lindefense.sim.PromptInjection.MAX_TARGETS + " nearest towers within " + (int) lindefense.sim.PromptInjection.RADIUS
            + " px for " + (int) lindefense.sim.PromptInjection.HIJACK_TIME + " s. Stun or Disrupt it to stop the broadcast.";
    }

    /** Short key of the tower's intrusion state, so a panel can rebuild when it changes. */
    public static String stateKey(Tower t) {
        Intrusion in = t.getIntrusion();
        return in.isHijacked() ? "H" : in.isDisabled() ? "D" : in.isBlinded() ? "B" : in.isFirewalled() ? "F" : "-";
    }
}
