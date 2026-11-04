package lindefense.tower.behavior;

import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Blitz Arnav. A burst is {@code bullets} rounds spread over whatever is in range (the data's {@code targets}), so
 * one burst can tag several enemies. Suppressive Fire (U2) slows everything caught by every {@code suppressEvery}-th
 * burst; Full Auto (U3) launches a rocket on every {@code rocketEvery}-th.
 */
public final class BlitzArnavBehavior extends TowerBehavior {
    private static final String BURSTS = "bursts";

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        double next = t.counter(BURSTS) + 1;
        // a burst is one bullet per acquired target; with fewer enemies than bullets the rest double up
        int bullets = s.pi("bullets", s.targets);
        if (!c.targets.isEmpty() && bullets > c.targets.size()) {
            c.shotsPerTarget = Math.max(1, bullets / c.targets.size());
        }
        int suppress = s.pi("suppressEvery", 0);
        if (suppress > 0 && next % suppress == 0) c.tag = "suppress";
        int rocket = s.pi("rocketEvery", 0);
        if (rocket > 0 && next % rocket == 0) c.tag = "rocket";
    }

    @Override public void onHit(Game game, Tower t, HitContext c) {
        if (!"suppress".equals(c.tag) || c.target == null || !c.target.isAlive()) return;
        TowerStats s = t.getStats();
        c.target.applyStatus(StatusEffect.Kind.SLOW, s.p("suppressSlow"), s.p("suppressDuration"));
    }

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        t.addCounter(BURSTS, 1);
        if (!"rocket".equals(c.tag) || c.primary == null) return;
        TowerStats s = t.getStats();
        Vec at = c.primary.getPosition();
        HitSpec rocket = new HitSpec(s.p("rocketDamage"), lindefense.combat.DamageType.EXPLOSIVE);
        double radius = s.p("rocketRadius");
        game.getEffects().schedule(0.2, () -> {
            game.getCombat().areaHit(at, radius, rocket, t, game.getGlobalDamageMultiplier(), 9999, null);
            game.getCombat().emit(VisualEvent.explosion(at, radius, t.getType().primaryRgb));
        });
    }
}
