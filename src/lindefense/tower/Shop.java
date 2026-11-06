package lindefense.tower;

import lindefense.sim.Game;

/**
 * Pricing helpers: purchase price, next-upgrade price, sell refunds (70%) and shop availability rules. Heroes carry
 * two prices: a one-time Hero Store unlock ({@link #unlockPriceOf}) and a per-match deploy cost ({@link #priceOf},
 * the same field shop towers use for their placement price); dismissing a hero refunds 70% of its deploy cost and
 * any upgrades bought, same as selling a tower, but its one-time Hero Store unlock is never refunded.
 */
public final class Shop {
    public static final double SELL_FRACTION = 0.70;

    private Shop() { }

    public static int priceOf(TowerType type) { return TowerCatalog.get(type).baseCost; }

    public static int upgradeCost(Tower t) {
        UpgradeDef u = t.nextUpgrade();
        return u == null ? 0 : u.cost;
    }

    /** Refund for selling: 70% of base cost plus all purchased upgrades, rounded down. */
    public static int sellValue(Tower t) {
        return (int) Math.floor(t.getInvestedCost() * SELL_FRACTION);
    }

    // ---- PATCH NOTES / BREAKING NEWS: prices in a match (list prices x the run's modifiers; identical when variance is off)
    /** Price of placing {@code type} in this match. */
    public static int priceOf(Game game, TowerType type) { return game.getVariance().towerPrice(priceOf(type)); }

    /** Price of {@code t}'s next upgrade in this match (0 if maxed). */
    public static int upgradeCost(Game game, Tower t) { return upgradePrice(game, t.nextUpgrade()); }

    /** Price of buying upgrade {@code u} in this match (0 for null). */
    public static int upgradePrice(Game game, UpgradeDef u) { return u == null ? 0 : game.getVariance().upgradePrice(u.cost); }

    /** Price of unlocking a maxed tower's ability in this match. */
    public static int abilityUnlockCost(Game game) { return game.getVariance().abilityUnlockPrice(TowerCatalog.ABILITY_UNLOCK_COST); }

    /** Sell refund fraction in this match (70% unless a patch note or event changes it). */
    public static double sellFraction(Game game) { return game.getVariance().sellFraction(SELL_FRACTION); }

    /** Refund for selling in this match: the refund fraction of what was actually paid (discounts and free upgrades excluded). */
    public static int sellValue(Game game, Tower t) {
        int paid = Math.max(0, t.getInvestedCost() - game.getVariance().unpaidOn(t));
        return (int) Math.floor(paid * sellFraction(game));
    }

    /** Hero Store price that permanently unlocks a hero (0 for shop towers). */
    public static int unlockPriceOf(TowerType type) { return TowerCatalog.get(type).unlockCost; }

    /**
     * Position-independent reason the tower type cannot be placed right now, or null if it can: heroes must be
     * unlocked and are deployed once per match; everything else needs the cash. The UI uses this to grey out cards.
     */
    public static String unavailableReason(Game game, TowerType type) {
        String hero = game.getTowerManager().heroProblem(type);
        if (hero != null) return hero;
        if (game.getCash() < priceOf(game, type)) return "Not enough cash";
        return null;
    }
}
