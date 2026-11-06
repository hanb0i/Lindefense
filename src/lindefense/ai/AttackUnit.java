package lindefense.ai;

import java.util.EnumSet;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;

/**
 * Reverse mode's spawn catalog: every enemy the attacker can buy, with its price in compute credits and the match
 * time at which it unlocks. Prices scale with strength (health including split children, lives taken on a leak,
 * speed and resistances); the unlock order follows the campaign's debut order, compressed into the
 * {@link ReverseMatch#DURATION} training run. The five bosses unlock last.
 *
 * <p>Modifier surcharges ({@link #modifierFactor}): Regrow x1.3, Camo x1.5, Fortified x2 (double HP), multiplied
 * together. Palantir carries no modifiers.</p>
 */
public enum AttackUnit {
    PRIMITIVE(EnemyType.PRIMITIVE_VARIABLE, 10, 0, "Cheap filler. Floods weak defences."),
    STATIC(EnemyType.STATIC_ARRAY, 22, 0, "Splits into a Primitive Variable."),
    DYNAMIC(EnemyType.DYNAMIC_ARRAY, 38, 0, "Fast; splits into a Static Array."),
    SINGLY(EnemyType.SINGLY_LINKED_LIST, 34, 60, "Very fast, takes 2 integrity."),
    DOUBLY(EnemyType.DOUBLY_LINKED_LIST, 42, 60, "Very fast, speeds up when hit."),
    BUBBLE(EnemyType.BUBBLE_SORT, 30, 60, "Swaps places with the unit ahead."),
    SELECTION(EnemyType.SELECTION_SORT, 38, 100, "Jumps to the front of its group."),
    INSERTION(EnemyType.INSERTION_SORT, 38, 100, "Leapfrogs the unit ahead."),
    SHELL(EnemyType.SHELL_SORT, 42, 100, "Gap-jumps forward; takes 3 integrity."),
    MERGE(EnemyType.MERGE_SORT, 72, 150, "Ceramic; splits into two Merge Runs."),
    QUICK(EnemyType.QUICK_SORT, 72, 150, "Ceramic and fast; splits in two."),
    COUNTING(EnemyType.COUNTING_SORT, 60, 150, "Releases four Primitive Variables."),
    HEAP(EnemyType.HEAP_SORT, 65, 200, "Lead-type; shields the units behind it."),
    RADIX(EnemyType.RADIX_SORT, 75, 200, "Armoured digit phases; takes 6 integrity."),
    BUCKET(EnemyType.BUCKET_SORT, 68, 200, "Carries weaker units past the towers."),
    TIMSORT(EnemyType.TIMSORT, 140, 250, "Fast hybrid; splits into Merge + Insertion."),
    MOAB(EnemyType.BELLARMINE_COLLEGE_PREP, 1200, 260, "MOAB-class boss: 1,500 HP, 30 integrity."),
    BFB(EnemyType.SW_RESOURCE_CONSULTANT, 4800, 340, "BFB-class boss: releases 3 MOABs, 60 integrity."),
    DDT(EnemyType.LOCKHEED_MARTIN, 2700, 440, "DDT-class: camo, lead, very fast, 50 integrity."),
    ZOMG(EnemyType.THREE_COM, 15000, 560, "ZOMG-class: releases 3 BFBs, 100 integrity."),
    BAD(EnemyType.PALANTIR, 30000, 680, "The BAD: 50,000 HP, phases, jams towers, 100 integrity.");

    /** The enemy this card spawns. */
    public final EnemyType type;
    /** Base price in compute credits (no modifiers). */
    public final int price;
    /** Match time (seconds) at which the unit becomes available. */
    public final double unlockAt;
    /** One-line role description for the spawn panel. */
    public final String blurb;

    AttackUnit(EnemyType type, int price, double unlockAt, String blurb) {
        this.type = type; this.price = price; this.unlockAt = unlockAt; this.blurb = blurb;
    }

    /** True for the five boss classes. */
    public boolean isBoss() { return type.isBoss(); }

    /** Whether this unit may carry modifiers (everything but Palantir). */
    public boolean acceptsModifiers() { return type != EnemyType.PALANTIR; }

    /** The catalog entry for an enemy type, or null if it cannot be bought (split children). */
    public static AttackUnit of(EnemyType t) {
        for (AttackUnit u : values()) if (u.type == t) return u;
        return null;
    }

    /**
     * Match time (seconds) at which a modifier becomes available: Regrow 1:30, Camo 3:00, Fortified 4:00, Prompt
     * Injection 6:00 (injectors hijack the AI's towers that are not immune, exactly as in the campaign).
     */
    public static double modifierUnlockAt(Modifier m) {
        switch (m) {
            case REGROW: return 90;
            case CAMO: return 180;
            case INJECTION: return 360;
            default: return 240;
        }
    }

    /** Price multiplier of one modifier: Regrow x1.3, Camo x1.5, Fortified x2, Prompt Injection x1.6. */
    public static double modifierFactor(Modifier m) {
        switch (m) {
            case REGROW: return 1.3;
            case CAMO: return 1.5;
            case INJECTION: return 1.6;
            default: return 2.0;
        }
    }

    /** Price of one unit of this type with the given modifiers (ignored on Palantir), rounded to whole credits. */
    public int priceWith(EnumSet<Modifier> mods) {
        double p = price;
        if (mods != null && acceptsModifiers()) for (Modifier m : mods) p *= modifierFactor(m);
        return (int) Math.round(p);
    }
}
