package lindefense.tower.behavior;

import lindefense.combat.AttackContext;
import lindefense.combat.HitSpec;
import lindefense.combat.Projectile;
import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Lobber Luis. Cluster Bombs (U2) splits the shell on impact into bomblets that blast around the crater a moment
 * later; Orbital Artillery (U3) makes every {@code orbitalEvery}-th shot a double-damage strike with a shockwave.
 */
public final class LobberLuisBehavior extends TowerBehavior {
    private static final String SHOTS = "shots";

    /** Main blast, then {@code clusterBombs} bomblets scattered around the crater. */
    private static final Projectile.ImpactHandler CLUSTER = (game, p, e) -> {
        Projectile.Shot sh = p.getShot();
        TowerStats s = sh.stats;
        game.getCombat().areaHit(p.getPosition(), sh.splash, sh.hit, sh.source, sh.damageMult, sh.extraDamage,
            sh.pierce > 1 ? sh.pierce : 999, null, sh.detection, sh.buffed, p);
        game.getCombat().emit(VisualEvent.explosion(p.getPosition(), sh.splash, sh.rgb));
        p.kill();
        int bombs = s.pi("clusterBombs", 0);
        if (bombs <= 0) return;
        double radius = s.p("clusterSplash"), spread = sh.splash * 0.8;
        HitSpec sub = sh.hit.copy();
        sub.damage = s.p("clusterDamage");
        final Vec at = p.getPosition();
        for (int i = 0; i < bombs; i++) {
            double ang = Math.PI * 2 * i / bombs + 0.4;
            final Vec spot = new Vec(at.x + Math.cos(ang) * spread, at.y + Math.sin(ang) * spread);
            game.getEffects().schedule(0.12 + i * 0.05, () -> {
                game.getCombat().areaHit(spot, radius, sub, sh.source, game.getGlobalDamageMultiplier(), 9999, null);
                game.getCombat().emit(VisualEvent.explosion(spot, radius, sh.source.getType().secondaryRgb));
            });
        }
    };

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        if (s.pi("clusterBombs", 0) > 0) c.onImpact = CLUSTER;
        int every = s.pi("orbitalEvery", 0);
        if (every > 0 && (t.counter(SHOTS) + 1) % every == 0) {
            c.damageMult *= s.p("orbitalMult");
            c.splash *= 1.35;
            c.tag = "orbital";
        }
    }

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        t.addCounter(SHOTS, 1);
        if ("orbital".equals(c.tag) && c.primary != null) {
            game.getCombat().emit(VisualEvent.ability(c.primary.getPosition(), t.getStats().splashRadius * 1.6, t.getType().primaryRgb));
        }
    }
}
