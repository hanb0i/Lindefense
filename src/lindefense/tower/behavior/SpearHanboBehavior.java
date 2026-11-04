package lindefense.tower.behavior;

import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.Projectile;
import lindefense.sim.Game;
import lindefense.tower.Tower;

/**
 * Spear Hanbo. His spears fly straight through a line of enemies instead of homing from one to the next. Returning
 * Spear (U2) turns them around when they reach the end of their throw so they rake the line a second time on the way
 * home: the spear's hit list is cleared on the turn, so the return leg can hit the same enemies again but a single
 * leg still never hits one twice.
 */
public final class SpearHanboBehavior extends TowerBehavior {
    /** {@link Projectile#handlerMark} value meaning "already flying home". */
    private static final int RETURNING = 1;

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        c.onImpact = HeroShots.STRAIGHT_PIERCE;
    }

    @Override public void update(Game game, Tower t, double dt) {
        if (t.getStats().p("returns", 0) <= 0) return;
        double range = t.effectiveRange(game);
        List<Projectile> live = game.getCombat().getProjectiles();
        for (int i = 0, n = live.size(); i < n; i++) {
            Projectile p = live.get(i);
            if (p.getSource() != t || p.handlerMark == RETURNING || !p.isAlive()) continue;
            if (p.getPosition().dist(t.getPosition()) < range) continue;
            p.handlerMark = RETURNING;
            p.restorePierce(t.getStats().pierce);
            p.getHitIds().clear();          // a fresh leg: the same enemies may be struck once more
            p.aimTowards(t.getPosition());
        }
    }
}
