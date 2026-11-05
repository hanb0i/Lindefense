package lindefense.tower;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.Vec;

/**
 * Owns placed towers: placement validation, purchase, upgrade, selling,
 * temporary summons, aura recomputation and the per-tick attack loop.
 */
public class TowerManager {
    private static final int AURA_REFRESH_TICKS = 6;
    private static final int FIELD_REFRESH_TICKS = 3;
    private static final double FIELD_STATUS_TIME = 0.3;

    private final Game game;
    private final List<Tower> towers = new ArrayList<>();
    private final List<Tower> pending = new ArrayList<>();
    /** Grid query buffer for {@link #applyEnemyField} (statuses only, nothing re-enters while it is in use). */
    private final List<Enemy> near = new ArrayList<>();
    private int tickCounter;

    public TowerManager(Game game) { this.game = game; }

    public List<Tower> getTowers() { return towers; }

    /** Permanent (player-owned) towers only. */
    public List<Tower> getPlayerTowers() {
        List<Tower> l = new ArrayList<>();
        for (Tower t : towers) if (!t.isTemporary()) l.add(t);
        return l;
    }

    public void clear() { towers.clear(); pending.clear(); }

    // ------------------------------------------------------------------
    // Placement
    // ------------------------------------------------------------------

    /** Returns null if a tower of this type can be placed at p, otherwise the reason it cannot. */
    public String placementProblem(TowerType type, Vec p) {
        TowerDef def = TowerCatalog.get(type);
        String hero = heroProblem(type);
        if (hero != null) return hero;
        if (!game.getMap().isBuildable(p, def.radius)) return "Cannot build here";
        for (Tower t : towers) {
            if (t.isTemporary()) continue;
            if (t.getPosition().dist(p) < t.getRadius() + def.radius) return "Overlaps another tower";
        }
        if (game.getCash() < def.baseCost) return "Not enough cash";
        return null;
    }

    public boolean canPlace(TowerType type, Vec p) { return placementProblem(type, p) == null; }

    /** Most different heroes a player may deploy in one match; a dismissed hero still uses its slot. */
    public static final int MAX_HEROES_PER_GAME = 3;

    /**
     * Hero-only placement rules, independent of position: the hero must be unlocked in the Hero Store, can be
     * deployed once per match (removing it does not give the deployment back), and at most
     * {@link #MAX_HEROES_PER_GAME} different heroes may be deployed per match. Null for shop towers.
     */
    public String heroProblem(TowerType type) {
        if (!type.isHero()) return null;
        if (!game.isHeroUnlocked(type)) return "Unlock " + type.displayName + " in the Hero Store";
        if (game.isHeroDeployed(type) || heroPlaced(type)) return type.displayName + " already deployed this match";
        if (heroesDeployedThisMatch() >= game.getHeroLimit()) return "Hero limit reached (" + game.getHeroLimit() + " per game)";
        return null;
    }

    /** Different heroes deployed so far this match: the ones on the map plus any already dismissed. */
    public int heroesDeployedThisMatch() {
        java.util.EnumSet<TowerType> seen = java.util.EnumSet.noneOf(TowerType.class);
        for (Tower t : towers) if (t.getType().isHero() && !t.isTemporary()) seen.add(t.getType());
        for (Tower t : pending) if (t.getType().isHero() && !t.isTemporary()) seen.add(t.getType());
        for (TowerType h : TowerType.heroes()) if (game.isHeroDeployed(h)) seen.add(h);
        return seen.size();
    }

    /** True if a copy of this hero is currently placed (only one of each hero may exist). */
    public boolean heroPlaced(TowerType type) {
        for (Tower t : towers) if (t.getType() == type && !t.isTemporary()) return true;
        for (Tower t : pending) if (t.getType() == type && !t.isTemporary()) return true;
        return false;
    }

    /** Buys and places a tower. Returns the tower, or null if placement is invalid. */
    public Tower place(TowerType type, Vec p) {
        if (!canPlace(type, p)) return null;
        TowerDef def = TowerCatalog.get(type);
        if (!game.spendCash(def.baseCost)) return null;
        Tower t = new Tower(def, p);
        towers.add(t);
        if (type.isHero()) game.markHeroDeployed(type);
        game.getEvents().add(VisualEvent.ability(p, def.radius * 2, type.primaryRgb));
        recomputeAuras();
        t.getBehavior().onPlaced(game, t);
        return t;
    }

    /** Adds a temporary tower (summon / clone). */
    public Tower addTemporary(TowerType type, int tier, Vec p, double lifetime, Tower owner) {
        Tower t = new Tower(TowerCatalog.get(type), p, tier, true, lifetime, owner);
        pending.add(t);
        game.getEvents().add(VisualEvent.ability(p, 30, type.secondaryRgb));
        return t;
    }

    public boolean canUpgrade(Tower t) {
        return t != null && t.isAlive() && !t.isTemporary() && t.canUpgrade() && game.getCash() >= t.nextUpgrade().cost;
    }

    /** Purchases the next upgrade. Returns false if unaffordable or maxed. */
    public boolean upgrade(Tower t) {
        if (!canUpgrade(t)) return false;
        int cost = t.nextUpgrade().cost;
        if (!game.spendCash(cost)) return false;
        t.applyUpgrade(game);
        t.clearSurveilled();
        game.getEvents().add(VisualEvent.ability(t.getPosition(), 50, t.getType().secondaryRgb));
        recomputeAuras();
        return true;
    }

    /**
     * Buys a fully upgraded shop tower's ability for {@link TowerCatalog#ABILITY_UNLOCK_COST}. Fails (returns false)
     * if the tower is not maxed, has no locked ability, or the player cannot pay.
     */
    public boolean unlockAbility(Tower t) {
        if (t == null || !t.isAlive() || !t.canUnlockAbility()) return false;
        if (!game.spendCash(TowerCatalog.ABILITY_UNLOCK_COST)) return false;
        t.unlockAbility();
        game.getEvents().add(VisualEvent.ability(t.getPosition(), 90, t.getType().primaryRgb));
        game.getEvents().add(VisualEvent.text(t.getPosition(), t.getAbility().name + " UNLOCKED", t.getType().primaryRgb));
        return true;
    }

    /** Sells the tower for 70% of everything spent on it. Returns the refund. */
    public int sell(Tower t) {
        if (t == null || !t.isAlive() || t.isTemporary()) return 0;
        int refund = Shop.sellValue(t);
        t.markRemoved();
        towers.remove(t);
        t.getBehavior().onRemoved(game, t);
        game.getEffects().removeOwnedBy(t);
        game.addCash(refund, t.getPosition());
        game.getEvents().add(VisualEvent.text(t.getPosition(), t.getType().isHero() ? t.getType().displayName + " dismissed" : "+$" + refund, 0xffd166));
        recomputeAuras();
        return refund;
    }

    /** Tower whose footprint contains p, or null. */
    public Tower towerAt(Vec p) {
        Tower best = null;
        double bestD = Double.MAX_VALUE;
        for (Tower t : towers) {
            if (t.isTemporary()) continue;
            double d = t.getPosition().dist(p);
            if (d <= t.getRadius() + 2 && d < bestD) { bestD = d; best = t; }
        }
        return best;
    }

    // ------------------------------------------------------------------
    // Auras
    // ------------------------------------------------------------------

    /**
     * Recomputes every aura-granted bonus from scratch. Each tower's behaviour applies its aura to every other
     * tower ({@link lindefense.tower.behavior.TowerBehavior#auraContribution}); buffs from the same source tower
     * type never stack. A Perplexity with {@code revealAllCamo} (U1+) grants detection to every tower.
     */
    public void recomputeAuras() {
        boolean revealAll = false;
        for (Tower t : towers) {
            t.resetAuraBonuses();
            if (t.getStats().has("revealAllCamo")) revealAll = true;
        }
        for (Tower src : towers) {
            for (Tower dst : towers) {
                if (dst != src) src.getBehavior().auraContribution(game, src, dst);
            }
        }
        if (revealAll) for (Tower t : towers) t.grantDetection();
    }

    // ------------------------------------------------------------------
    // Tick
    // ------------------------------------------------------------------

    public void update(double dt) {
        if (!pending.isEmpty()) { towers.addAll(pending); pending.clear(); }
        if (++tickCounter % AURA_REFRESH_TICKS == 0) recomputeAuras();
        for (int i = 0; i < towers.size(); i++) {
            Tower t = towers.get(i);
            boolean wantsAttack = t.tickTimers(game, dt);
            if (!t.isAlive()) continue;
            t.getBehavior().update(game, t, dt);
            if (tickCounter % FIELD_REFRESH_TICKS == 0) applyEnemyField(t);
            if (wantsAttack) {
                if (!game.getCombat().attack(t)) t.idle();
            }
        }
        for (int i = towers.size() - 1; i >= 0; i--) {
            if (!towers.get(i).isAlive()) towers.remove(i);
        }
        if (!pending.isEmpty()) { towers.addAll(pending); pending.clear(); }
    }

    /** Slow / mark applied to enemies inside a tower's field (Sora, Brad U1, Perplexity U2). */
    private void applyEnemyField(Tower t) {
        TowerStats s = t.getStats();
        if (s.auraEnemySlow <= 0 && s.fieldMarkFlat <= 0 && s.fieldMarkPct <= 0) return;
        double r = s.fieldRadius > 0 ? s.fieldRadius : t.effectiveRange(game);
        List<Enemy> pool = game.getEnemyManager().getGrid().near(t.getPosition().x, t.getPosition().y, r, near);
        for (int i = 0, n = pool.size(); i < n; i++) {
            Enemy e = pool.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            if (e.isBoss() && !s.fieldAffectsBosses) continue;
            if (e.getPosition().exceedsDist(t.getPosition(), r + e.getRadius())) continue;
            if (s.auraEnemySlow > 0) e.applyStatus(StatusEffect.Kind.SLOW, s.auraEnemySlow, FIELD_STATUS_TIME);
            if (s.fieldMarkFlat > 0) e.applyStatus(StatusEffect.Kind.MARKED_FLAT, s.fieldMarkFlat, FIELD_STATUS_TIME);
            if (s.fieldMarkPct > 0) e.applyStatus(StatusEffect.Kind.MARKED, s.fieldMarkPct, FIELD_STATUS_TIME);
        }
    }
}
