package lindefense.ai;

import lindefense.sim.Difficulty;

/**
 * How hard reverse mode is, chosen with the Difficulty Growth picker: each Big-O mode maps to one profile. The profile
 * scales the defender AI's funding and how smart it plays (casual or optimised tower placement, whether it plans for camo
 * before it sees any, whether it micro-manages abilities and targeting, whether it saves for the $15,000 ability
 * unlocks, how often it thinks) and the match itself: the defender's tower damage and integrity, and the attacker's
 * unit health and compute income. The harder the mode, the harder the AI's towers hit, the more integrity it has, and
 * the frailer and poorer the player's side is.
 */
public enum DefenderProfile {
    /** O(1): a casual builder. Random placement, no ability or targeting micro, reacts to camo only after seeing it, 0.9x funding. */
    NOVICE(Difficulty.O1, "Novice", "Builds casually: random placement, no ability micro, reacts to camo only after it gets through. 0.9x funding.",
        0.9, 1.0, true, false, false, 1.0, 0, 0,
        0.90, 1.10, 1.10, 80),
    /** O(N): the balance bot's efficient build with full micro, but it only reacts to camo once it sees some. */
    COMPETENT(Difficulty.ON, "Competent", "Efficient build, smart placement and ability micro, but it reacts to camo only once it sees some.",
        1.0, 0.5, false, false, false, 1.0, 0, 0,
        1.00, 1.00, 1.00, 100),
    /** O(N^2): anticipates camo as soon as you can buy it, greedily saves for ability unlocks, 1.3x funding. */
    EXPERT(Difficulty.ON2, "Expert", "Builds detection the moment you can buy camo, saves greedily for $15,000 ability unlocks. 1.3x funding.",
        1.3, 0.25, false, true, true, 1.0, 8, 0,
        1.10, 0.95, 0.95, 125),
    /** O(N^N): expert play without the greed (each unlock needs a wider tower base), 1.6x funding. */
    SUPERINTELLIGENCE(Difficulty.ONN, "Superintelligence", "Expert play without the greed (unlocks only on a wide tower base), 1.6x funding. Breaking it takes a real plan.",
        1.6, 0.25, false, true, true, 1.0, 12, 4,
        1.20, 0.90, 0.90, 150);

    /** The Difficulty Growth mode that selects this profile. */
    public final Difficulty level;
    /** Name shown in the briefing and HUD. */
    public final String displayName;
    /** One-line description of how it plays. */
    public final String description;
    /** Multiplier on the AI's periodic funding. */
    public final double income;
    /** Game seconds between two decision passes. */
    public final double thinkInterval;
    /** Random placement, broad roster, no micro. */
    public final boolean casual;
    /** Builds camo detection as soon as the attacker can buy camo units. */
    public final boolean anticipatesCamo;
    /** Saves for and buys $15,000 ability unlocks on maxed towers. */
    public final boolean unlocksAbilities;
    /** Multiplier on the normal starting cash. */
    public final double startCash;
    /** Towers it wants before its first ability unlock, and extra towers per further unlock. */
    public final int unlockMinTowers, unlockTowersPer;
    /** Multiplier on all damage the defender's towers deal. */
    public final double towerDamage;
    /** Multiplier on the health of every unit the player sends (children inherit it). */
    public final double unitHp;
    /** Multiplier on the player's compute income (passive, SCALE COMPUTE and leak bounties). */
    public final double attackerIncome;
    /** The defender's starting (and maximum) integrity. */
    public final int integrity;

    DefenderProfile(Difficulty level, String displayName, String description, double income, double thinkInterval,
                    boolean casual, boolean anticipatesCamo, boolean unlocksAbilities, double startCash, int unlockMinTowers, int unlockTowersPer,
                    double towerDamage, double unitHp, double attackerIncome, int integrity) {
        this.level = level; this.displayName = displayName; this.description = description; this.income = income;
        this.thinkInterval = thinkInterval; this.casual = casual; this.anticipatesCamo = anticipatesCamo;
        this.unlocksAbilities = unlocksAbilities; this.startCash = startCash;
        this.unlockMinTowers = unlockMinTowers; this.unlockTowersPer = unlockTowersPer;
        this.towerDamage = towerDamage; this.unitHp = unitHp; this.attackerIncome = attackerIncome; this.integrity = integrity;
    }

    /** The match rules of this mode in one line, for the briefing: "AI towers x1.3 damage, AI integrity 200, ...". */
    public String rulesLine() {
        return "AI towers x" + fmt(towerDamage) + " damage, AI integrity " + integrity + ". Your units x" + fmt(unitHp)
            + " health, your compute income x" + fmt(attackerIncome) + ".";
    }

    private static String fmt(double v) {
        String s = String.format(java.util.Locale.ROOT, "%.2f", v);
        while (s.endsWith("0")) s = s.substring(0, s.length() - 1);
        return s.endsWith(".") ? s.substring(0, s.length() - 1) : s;
    }

    /** The profile for a Difficulty Growth mode. */
    public static DefenderProfile of(Difficulty d) {
        for (DefenderProfile p : values()) if (p.level == d) return p;
        return COMPETENT;
    }
}
