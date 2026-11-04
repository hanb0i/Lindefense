package lindefense.tower.behavior;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.HitSpec;
import lindefense.combat.Projectile;
import lindefense.effects.Mine;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;

/** Shared projectile impact handlers and placement helpers for the Hero Store heroes. */
final class HeroShots {
    private HeroShots() { }

    /**
     * A bolt that homes on its target until the first hit, then keeps flying in a straight line, damaging each enemy
     * it passes through once until its pierce is spent (Spear Hanbo, Blitz Arnav).
     */
    static final Projectile.ImpactHandler STRAIGHT_PIERCE = (game, p, e) -> {
        game.getCombat().projectileHit(p, e, 1);
        if (p.consumePierce()) p.kill(); else p.retarget(null);
    };

    /**
     * Plants one device (mine or trap) on the track inside the tower's range, keeping clear of the devices already
     * planted, and returns it. Returns null when there is no free spot. Devices are placed on the centre line of a
     * route, so they always sit where enemies actually walk.
     */
    static Mine plant(Game game, Tower t, HitSpec hit, double spacing, String kind) {
        double range = t.effectiveRange(game);
        Vec tp = t.getPosition();
        List<Mine> existing = game.getEffects().minesOf(t, kind);
        Vec best = null;
        double bestScore = -1;
        List<Path> routes = game.getMap().getRoutes();
        for (int ri = 0; ri < routes.size(); ri++) {
            Path r = routes.get(ri);
            for (double d = 0; d <= r.getTotalLength(); d += 16) {
                Vec q = r.positionAt(d);
                if (q.dist(tp) > range) continue;
                double nearest = Double.MAX_VALUE;
                for (Mine m : existing) nearest = Math.min(nearest, m.position.dist(q));
                if (nearest < spacing) continue;
                // prefer spots further along the track (enemies meet them sooner after passing the hero)
                double score = nearest == Double.MAX_VALUE ? 1e6 : nearest;
                if (score > bestScore) { bestScore = score; best = q; }
            }
        }
        if (best == null) return null;
        Mine m = new Mine(t, best, hit);
        m.kind = kind;
        m.rgb = t.getType().primaryRgb;
        return m;
    }

    /** Every enemy on the map that is alive and on the track (for map-wide time effects). */
    static List<lindefense.enemy.Enemy> allOnTrack(Game game) {
        List<lindefense.enemy.Enemy> out = new ArrayList<>();
        for (lindefense.enemy.Enemy e : game.getEnemyManager().getEnemies()) {
            if (e.isAlive() && !e.isStored()) out.add(e);
        }
        return out;
    }
}
