package lindefense.tower.behavior;

import java.util.Comparator;
import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.BuffStat;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Per-tower-type behaviour: every hook is a no-op (or the data-driven default) so a subclass only overrides what
 * its tower's special mechanics need. One subclass per tower lives in this package ({@code <Name>Behavior})
 * and is registered in {@link Behaviors}. Behaviours are stateless singletons: keep per-tower memory in
 * {@link Tower#counter(String)}, {@link Tower#state()} or {@link Tower#registerStreak(int)}, and read every number
 * from {@code t.getStats().p("name")} (never hardcode literals).
 *
 * <p>Call order per simulation step for a tower: {@link #update}, then (if its attack timer is ready)
 * {@link #attack} which by default runs the data-driven attack: targets are chosen, {@link #modifyAttack} may
 * adjust the {@link AttackContext}, the attack is fired, then {@link #onFire}. Every hit credited to the tower
 * goes through {@link #beforeHit} and {@link #onHit}; kills through {@link #onKill}.</p>
 */
public abstract class TowerBehavior {

    // ---------------- lifecycle ----------------
    /** The tower was just placed (also called for temporary towers). */
    public void onPlaced(Game game, Tower t) { }

    /** An upgrade was just bought; {@code t.getStats()} already reflects the new tier. */
    public void onUpgraded(Game game, Tower t) { }

    /** The tower was sold. Zones/drones/walkers it created are removed automatically by the engine. */
    public void onRemoved(Game game, Tower t) { }

    /** Every simulation step (even with no target): periodic effects, timers, upkeep of drones/zones. */
    public void update(Game game, Tower t, double dt) { }

    // ---------------- attacking ----------------
    /**
     * Performs the tower's attack when its timer is ready; return true if it fired. The default runs the
     * data-driven attack for the tower's AttackKind. Override for {@code AttackKind.CUSTOM} towers (Llama, Perplexity).
     */
    public boolean attack(Game game, Tower t) { return game.getCombat().genericAttack(t); }

    /** Called before a generic attack is fired; adjust damage, pierce, shot count, tag, or set {@code c.cancel}. */
    public void modifyAttack(Game game, Tower t, AttackContext c) { }

    /** Called after a generic attack was fired. */
    public void onFire(Game game, Tower t, AttackContext c) { }

    /** Called before the damage maths of a hit credited to this tower (edit {@code c.extra}, {@code c.editHit()}, {@code c.finalMult}). */
    public void beforeHit(Game game, Tower t, HitContext c) { }

    /** Called after a hit credited to this tower; {@code c.dealt} is the HP removed and {@code c.immune} whether it was blocked. */
    public void onHit(Game game, Tower t, HitContext c) { }

    /** Called when an enemy last damaged by this tower is destroyed (kill credit, pop counting). */
    public void onKill(Game game, Tower t, Enemy e) { }

    /**
     * Cash paid at the end of a round. The default pays the stats' {@code incomePerWave}
     * (Perplexity's +$40 / +$250 needs no override).
     */
    public double onRoundEnd(Game game, Tower t) { return t.getStats().incomePerWave; }

    // ---------------- abilities ----------------
    /**
     * Executes the tower's active ability. {@code target} is the player-chosen map point for abilities with
     * {@code AbilityDef.needsTarget}, otherwise null. Return false to refuse (no cooldown is spent).
     */
    public boolean activateAbility(Game game, Tower t, Vec target) { return false; }

    // ---------------- auras / targeting ----------------
    /**
     * Applies this (source) tower's aura to one other tower. Called by the engine for every ordered pair whenever
     * auras are recomputed (about 10 times a second). The default implements the data-driven aura: everything
     * within {@code auraRange} gets the stats' attack speed, flat damage, pierce, range, detection and
     * Surveillance immunity. Override and call {@code super} to add faction-wide or conditional aura effects.
     */
    public void auraContribution(Game game, Tower src, Tower dst) {
        TowerStats s = src.getStats();
        if (s.auraRange <= 0 || dst == src) return;
        if (dst.getPosition().dist(src.getPosition()) > s.auraRange) return;
        grantAura(src, dst);
    }

    /** Applies the stats' aura values from {@code src} to {@code dst} with no distance check. */
    protected static void grantAura(Tower src, Tower dst) {
        TowerStats s = src.getStats();
        if (s.auraRate > 0) dst.addAuraBuff(BuffStat.RATE, src.getType(), s.auraRate);
        if (s.auraDamage > 0) dst.addAuraBuff(BuffStat.DAMAGE_FLAT, src.getType(), s.auraDamage);
        if (s.auraPierce > 0) dst.addAuraBuff(BuffStat.PIERCE_FLAT, src.getType(), s.auraPierce);
        if (s.auraRangeBonus > 0) dst.addAuraBuff(BuffStat.RANGE, src.getType(), s.auraRangeBonus);
        if (s.auraDetection) dst.grantDetection();
        if (s.auraSurveillanceImmunity) dst.grantSurveillanceImmunity();
        if (s.auraInjectionImmunity) dst.grantInjectionFirewall();
    }

    /** Flat range added before range multipliers (Zethos Reality Collapse +15 map units). */
    public double flatRangeBonus(Tower t) { return 0; }

    /** Whether the tower may select Densest Cluster targeting (Grok U2+). */
    public boolean allowsDensestCluster(Tower t) { return false; }

    /** Optional ordering applied before the player's targeting priority (Student+AI: camo and Regrow first). */
    public Comparator<Enemy> priorityComparator(Tower t) { return null; }

    // ---------------- helpers for subclasses ----------------
    /** Alive, on-track enemies whose centre is within {@code radius} of {@code p} (any camo status). */
    protected static java.util.List<Enemy> enemiesWithin(Game game, Vec p, double radius) {
        java.util.List<Enemy> out = new java.util.ArrayList<>();
        // spatial grid: candidates come back in list order, so results match a full scan exactly
        java.util.List<Enemy> pool = game.getEnemyManager().getGrid().near(p.x, p.y, radius, new java.util.ArrayList<>());
        for (Enemy e : pool) {
            if (e.isAlive() && !e.isStored() && e.getPosition().dist(p) <= radius) out.add(e);
        }
        return out;
    }

    /** Ability stand-in for mechanics not implemented yet: shows a label and spends the cooldown. */
    protected static boolean stubAbility(Game game, Tower t) {
        game.getCombat().emit(VisualEvent.text(t.getPosition(), t.getAbility().name + " (stub)", t.getType().primaryRgb));
        return true;
    }
}
