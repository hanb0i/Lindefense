package lindefense.effects;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import lindefense.combat.HitSpec;
import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;

/**
 * A one-shot proximity device planted beside the track: a mine that detonates (Cami-Mine) or a mechanical trap that
 * snaps shut and holds an enemy (Trapper Che). It arms, waits for an enemy to walk within {@link #triggerRadius},
 * then applies {@link #hit} to everything within {@link #blastRadius} and dies.
 *
 * <p>Devices never block pathfinding: they only read enemy positions and apply hits, so an enemy can always walk
 * through the tile a device sits on. Each device fires once, so a planted field cannot lock a lane forever.</p>
 *
 * <ul>
 *   <li>{@link #holdDuration} immobilises non-boss enemies caught in the blast (a STUN); bosses are never
 *       immobilised but still take the damage, per the global boss rules.</li>
 *   <li>{@link #tetherDps} keeps damaging the enemies it held, for as long as the hold lasts.</li>
 *   <li>{@link #secondaryChance} / {@link #secondaryHit} add a delayed follow-up blast.</li>
 * </ul>
 */
public final class Mine {
    public final Tower owner;
    public final Vec position;
    /** How close an enemy's centre must come to set the device off. */
    public double triggerRadius = 14;
    /** Radius of the blast once it goes off. */
    public double blastRadius = 32;
    /** Applied to every enemy in the blast. */
    public HitSpec hit;
    /** Seconds before the device can trigger (so it cannot detonate on the enemy that is already standing there). */
    public double armTime = 0.35;
    /** Seconds non-boss enemies in the blast are held in place (0 = none). */
    public double holdDuration;
    /** Damage per second dealt to held enemies while the hold lasts (0 = none). */
    public double tetherDps;
    /** Chance of a delayed second blast, and what it does. */
    public double secondaryChance;
    public HitSpec secondaryHit;
    public double secondaryDelay = 0.3;
    public double secondaryRadius = 32;
    /** Source detection for the EXPLOSIVE-vs-camo rule. */
    public boolean detection = true;
    public int rgb = 0xff8a3b;
    /** Free-form label for the renderer and tests ("mine", "trap"). */
    public String kind = "mine";

    private double age;
    private boolean dead;
    private boolean triggered;

    public Mine(Tower owner, Vec position, HitSpec hit) {
        this.owner = owner; this.position = position; this.hit = hit;
        this.detection = owner == null || owner.canSeeCamo();
    }

    public boolean isAlive() { return !dead; }
    public void kill() { dead = true; }
    public boolean isArmed() { return age >= armTime; }
    public boolean hasTriggered() { return triggered; }
    /** 0 while arming, 1 once live (drives the renderer's arming blink). */
    public double getArmFraction() { return armTime <= 0 ? 1 : Math.min(1, age / armTime); }

    void update(Game game, double dt) {
        if (dead) return;
        if (owner != null && !owner.isAlive()) { dead = true; return; }
        age += dt;
        if (age < armTime) return;
        Enemy trigger = null;
        List<Enemy> near = game.getEnemyManager().getGrid().near(position.x, position.y, triggerRadius, new ArrayList<>());
        for (Enemy e : near) {
            if (!e.isAlive() || e.isStored()) continue;
            if (!detection && e.isCamo() && !e.isRevealed()) continue;   // undetected camo never sets a device off
            if (e.getPosition().dist(position) <= triggerRadius + e.getRadius() * 0.5) { trigger = e; break; }
        }
        if (trigger == null) return;
        detonate(game);
    }

    /** Sets the device off now (also used by tests). */
    public void detonate(Game game) {
        if (triggered) return;
        triggered = true;
        dead = true;
        List<lindefense.combat.HitContext> hits = game.getCombat().areaHits(
            position, blastRadius, hit, owner, game.getGlobalDamageMultiplier(), 0, null, null, detection, false, null);
        if (holdDuration > 0 || tetherDps > 0) {
            Set<Integer> held = new HashSet<>();
            for (lindefense.combat.HitContext h : hits) {
                Enemy e = h.target;
                if (e == null || !e.isAlive() || !held.add(e.getId())) continue;
                if (holdDuration > 0 && !e.isBoss()) e.applyStatus(StatusEffect.Kind.STUN, 1, holdDuration);
                if (tetherDps > 0) e.applyBurn(tetherDps, holdDuration > 0 ? holdDuration : 1.0, owner);
            }
        }
        if (secondaryHit != null && secondaryChance > 0 && game.getRng().chance(secondaryChance)) {
            final Vec at = position;
            final HitSpec sec = secondaryHit;
            final double rad = secondaryRadius;
            game.getEffects().schedule(secondaryDelay, () ->
                game.getCombat().areaHit(at, rad, sec, owner, game.getGlobalDamageMultiplier(), 9999, null));
        }
        game.getCombat().emit(lindefense.combat.VisualEvent.explosion(position, blastRadius, rgb));
    }
}
