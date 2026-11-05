package lindefense.variance;

/**
 * Every number a patch note ({@link PatchNote}) or a news event ({@link BreakingNews}) can change, relative to the
 * base game. A knob says how values combine ({@link Op}) and which direction helps the player ({@link #good}), so card
 * text and the upside / downside split are generated from the numbers instead of being written twice.
 */
public enum Knob {
    // ---- economy
    /** Price of placing a shop tower (multiplier; stacked cards stay within 0.6 - 1.3). */
    TOWER_COST(Op.MUL, false, 0.6, 1.3),
    /** Price of every upgrade (multiplier; stacked cards stay within 0.6 - 1.3). */
    UPGRADE_COST(Op.MUL, false, 0.6, 1.3),
    /** Price of unlocking a maxed tower's ability (multiplier). */
    ABILITY_UNLOCK_COST(Op.MUL, false),
    /** Added to the sell refund fraction ({@code Shop.SELL_FRACTION}, 70%). */
    SELL_REFUND(Op.ADD, true),
    /** Kill rewards (multiplier; stacked cards never drop it below 0.75). */
    KILL_INCOME(Op.MUL, true, 0.75, Double.POSITIVE_INFINITY),
    /** End-of-wave bonus (multiplier). */
    WAVE_BONUS(Op.MUL, true),
    /** Interest paid on banked credits when a wave is cleared (fraction). */
    INTEREST_RATE(Op.ADD, true),
    /** Most interest paid per wave (credits). */
    INTEREST_CAP(Op.ADD, true),
    // ---- combat
    /** All tower damage (multiplier; stacked cards never drop it below 0.8). */
    DAMAGE(Op.MUL, true, 0.8, Double.POSITIVE_INFINITY),
    /** Damage against MOAB-class bosses (multiplier). */
    BOSS_DAMAGE(Op.MUL, true),
    /** Damage against everything that is not a boss (multiplier). */
    NON_BOSS_DAMAGE(Op.MUL, true),
    /** Damage against enemies with a Camo, Regrow or Fortified modifier (multiplier). */
    ELITE_DAMAGE(Op.MUL, true),
    /** Damage against enemies without modifiers (multiplier). */
    PLAIN_DAMAGE(Op.MUL, true),
    /** Tower attack rate (multiplier; stacked effects never drop it below 0.8). */
    FIRE_RATE(Op.MUL, true, 0.8, Double.POSITIVE_INFINITY),
    /** Tower range (multiplier). */
    RANGE(Op.MUL, true),
    /** Length of ability cooldowns (multiplier). */
    ABILITY_COOLDOWN(Op.MUL, false),
    // ---- enemies and waves
    /** Enemy HP (multiplier, applied at spawn). */
    ENEMY_HP(Op.MUL, false),
    /** Enemy speed (multiplier, applied at spawn). */
    ENEMY_SPEED(Op.MUL, false),
    /** Enemies per non-boss spawn group (multiplier). */
    ENEMY_COUNT(Op.MUL, false),
    /** Time between spawns in a group (multiplier; lower = denser waves). */
    SPAWN_GAP(Op.MUL, true),
    /** Every non-boss enemy of the wave gets Camo (flag). */
    ALL_CAMO(Op.FLAG, false),
    /** One lane of a multi-lane map is closed for the wave (flag). */
    CLOSE_LANE(Op.FLAG, false),
    // ---- integrity
    /** Integrity gained per wave cleared (may exceed the starting maximum). */
    LIVES_PER_WAVE(Op.ADD, true),
    /** Lives a leak costs (multiplier, rounded, never below 1). */
    LEAK_LIVES(Op.MUL, false),
    // ---- perks and one-offs
    /** Every newly placed shop tower gets its first upgrade free (flag). */
    FREE_FIRST_UPGRADE(Op.FLAG, true),
    /** Every ability cooldown is refreshed when the wave starts (flag). */
    REFRESH_ABILITIES(Op.FLAG, true),
    /** Credits granted once, when the card is picked or the news breaks. */
    CASH_NOW(Op.ADD, true),
    /** Extra one-off credits per wave already played (so a late pick is worth as much as an early one). */
    CASH_PER_WAVE(Op.ADD, true);

    /** How two values of the knob combine. */
    public enum Op {
        /** Multiplied together; neutral value 1. */
        MUL,
        /** Added; neutral value 0. */
        ADD,
        /** Either sets it; neutral value 0 (off), set = 1. */
        FLAG
    }

    /** How values combine and the neutral value. */
    public final Op op;
    /** True if a higher value (or a set flag) helps the player. */
    public final boolean good;
    /**
     * Bounds for the run's combined value (all cards plus the news): stacking several cards on one knob can never push
     * it past them, so no combination is run-ending on its own. A single card always stays inside them.
     */
    public final double min, max;

    Knob(Op op, boolean higherIsGood) { this(op, higherIsGood, Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY); }

    Knob(Op op, boolean higherIsGood, double min, double max) {
        this.op = op;
        this.good = higherIsGood;
        this.min = min;
        this.max = max;
    }

    /** The value that changes nothing (1 for multipliers, 0 otherwise). */
    public double neutral() { return op == Op.MUL ? 1 : 0; }

    /** Combines two values of this knob. */
    double combine(double a, double b) {
        switch (op) {
            case MUL: return a * b;
            case ADD: return a + b;
            default: return Math.max(a, b);
        }
    }

    /** True if {@code value} helps the player (false for a neutral value). */
    public boolean helps(double value) {
        if (value == neutral()) return false;
        return (value > neutral()) == good;
    }
}
