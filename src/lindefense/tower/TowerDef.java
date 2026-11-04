package lindefense.tower;

/**
 * Immutable definition of one tower: identity, base cost, base stats, its upgrade path and an ability. Standard towers
 * and Hero Store heroes have {@link TowerCatalog#STANDARD_UPGRADES} upgrades; Zethos has four. Heroes are unlocked in
 * the Hero Store for {@link #unlockCost}; deploying an unlocked hero is free ({@link #baseCost} 0), but its three
 * upgrades are bought with match cash like any tower's.
 */
public class TowerDef {
    public final TowerType type;
    /** The spec's nickname, shown under the family name ("Prism Blaster"). */
    public final String subtitle;
    public final String description;
    public final int baseCost;
    public final TowerStats baseStats;
    public final UpgradeDef[] upgrades;
    public final AbilityDef ability;
    /** Label for each progression state (base + one per upgrade): model names or tier names. */
    public final String[] tierLabels;
    /** Placement footprint radius. */
    public final double radius;
    /** Hero Store unlock price (heroes only; 0 for shop towers). */
    public final int unlockCost;
    /** Targeting priority a freshly placed tower starts with. */
    public final Targeting defaultTargeting;

    public TowerDef(TowerType type, String subtitle, String description, int baseCost, double radius,
                    TowerStats baseStats, UpgradeDef[] upgrades, AbilityDef ability, String[] tierLabels) {
        this(type, subtitle, description, baseCost, radius, baseStats, upgrades, ability, tierLabels, 0, Targeting.FIRST);
    }

    public TowerDef(TowerType type, String subtitle, String description, int baseCost, double radius,
                    TowerStats baseStats, UpgradeDef[] upgrades, AbilityDef ability, String[] tierLabels,
                    int unlockCost, Targeting defaultTargeting) {
        if (tierLabels.length != upgrades.length + 1) throw new IllegalArgumentException(type + " must have " + (upgrades.length + 1) + " tier labels");
        if (type.isHero() && unlockCost <= 0) throw new IllegalArgumentException(type + ": heroes need a Hero Store price");
        this.type = type; this.subtitle = subtitle; this.description = description; this.baseCost = baseCost;
        this.radius = radius; this.baseStats = baseStats; this.upgrades = upgrades; this.ability = ability;
        this.tierLabels = tierLabels; this.unlockCost = unlockCost;
        this.defaultTargeting = defaultTargeting == null ? Targeting.FIRST : defaultTargeting;
    }

    /** Computes the cumulative stats for a tier (0 = base .. upgrades.length = fully upgraded). */
    public TowerStats statsForTier(int tier) {
        TowerStats s = baseStats.copy();
        for (int i = 0; i < tier && i < upgrades.length; i++) upgrades[i].apply.accept(s);
        return s;
    }

    /** Total cost of base purchase plus the first {@code tier} upgrades. */
    public int totalCostForTier(int tier) {
        int c = baseCost;
        for (int i = 0; i < tier && i < upgrades.length; i++) c += upgrades[i].cost;
        return c;
    }

    /** Total cost of the fully upgraded tower (the spec's "Total"). */
    public int totalCost() { return totalCostForTier(upgrades.length); }
}
