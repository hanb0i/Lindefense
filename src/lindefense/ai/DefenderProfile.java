package lindefense.ai;

import lindefense.sim.Difficulty;

/**
 * How strong reverse mode's defender AI is, chosen with the Difficulty Growth picker: each Big-O mode maps to one
 * profile. The profile scales the AI's funding and how smart it plays: casual or optimised tower placement, whether
 * it plans for camo before it sees any, whether it micro-manages abilities and targeting, whether it saves for the
 * $15,000 ability unlocks, and how often it thinks.
 */
public enum DefenderProfile {
    /** O(1): a casual builder. Random placement, no ability or targeting micro, reacts to camo only after seeing it, 0.9x funding. */
    NOVICE(Difficulty.O1, "Novice", "Builds casually: random placement, no ability micro, reacts to camo only after it gets through. 0.9x funding.",
        0.9, 1.0, true, false, false, 1.0, 0, 0),
    /** O(N): the balance bot's efficient build with full micro, but it only reacts to camo once it sees some. */
    COMPETENT(Difficulty.ON, "Competent", "Efficient build, smart placement and ability micro, but it reacts to camo only once it sees some.",
        1.0, 0.5, false, false, false, 1.0, 0, 0),
    /** O(N^2): anticipates camo as soon as you can buy it, greedily saves for ability unlocks, 1.55x funding. */
    EXPERT(Difficulty.ON2, "Expert", "Builds detection the moment you can buy camo, saves greedily for $15,000 ability unlocks. 1.55x funding.",
        1.55, 0.25, false, true, true, 1.0, 8, 0),
    /** O(N^N): expert play without the greed (each unlock needs a wider tower base), 2x funding, double starting cash. */
    SUPERINTELLIGENCE(Difficulty.ONN, "Superintelligence", "Expert play without the greed (unlocks only on a wide tower base), 2x funding, double starting cash. Breaking it takes a real plan.",
        2.0, 0.25, false, true, true, 2.0, 12, 4);

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

    DefenderProfile(Difficulty level, String displayName, String description, double income, double thinkInterval,
                    boolean casual, boolean anticipatesCamo, boolean unlocksAbilities, double startCash, int unlockMinTowers, int unlockTowersPer) {
        this.level = level; this.displayName = displayName; this.description = description; this.income = income;
        this.thinkInterval = thinkInterval; this.casual = casual; this.anticipatesCamo = anticipatesCamo;
        this.unlocksAbilities = unlocksAbilities; this.startCash = startCash;
        this.unlockMinTowers = unlockMinTowers; this.unlockTowersPer = unlockTowersPer;
    }

    /** The profile for a Difficulty Growth mode. */
    public static DefenderProfile of(Difficulty d) {
        for (DefenderProfile p : values()) if (p.level == d) return p;
        return COMPETENT;
    }
}
