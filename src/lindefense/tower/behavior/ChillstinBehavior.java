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
 * Chillstin. Frozen Prison (U2) gives every {@code freezeEvery}-th shard a chance to freeze a normal enemy solid
 * (bosses can never be frozen and take a slow instead); Absolute Frost (U3) makes every {@code burstEvery}-th shard
 * burst into a deep-freezing ice explosion.
 */
public final class ChillstinBehavior extends TowerBehavior {
    private static final String SHOTS = "shards";

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        double shots = t.counter(SHOTS) + 1;
        int freezeEvery = s.pi("freezeEvery", 0);
        if (freezeEvery > 0 && shots % freezeEvery == 0) c.tag = "freeze";
        int burstEvery = s.pi("burstEvery", 0);
        if (burstEvery > 0 && shots % burstEvery == 0) c.tag = "burst";
    }

    @Override public void onHit(Game game, Tower t, HitContext c) {
        if (!"freeze".equals(c.tag) || c.target == null || !c.target.isAlive()) return;
        TowerStats s = t.getStats();
        if (c.target.isBoss()) {
            c.target.applyStatus(StatusEffect.Kind.SLOW, s.p("bossSlowPct"), s.hit.slowDuration);
        } else if (game.getRng().chance(s.p("freezeChance"))) {
            c.target.applyStatus(StatusEffect.Kind.FREEZE, 1, s.p("freezeDuration"));
            game.getCombat().emit(VisualEvent.text(c.target.getPosition(), "FROZEN", t.getType().primaryRgb));
        }
    }

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        t.addCounter(SHOTS, 1);
        if (!"burst".equals(c.tag) || c.primary == null) return;
        TowerStats s = t.getStats();
        Vec at = c.primary.getPosition();
        double radius = s.p("burstRadius");
        HitSpec burst = new HitSpec(s.hit.damage, s.hit.type);
        burst.slowFraction = s.p("burstSlow");
        burst.slowDuration = s.p("burstSlowDuration");
        game.getEffects().schedule(0.15, () -> {
            List<HitContext> hits = game.getCombat().areaHits(at, radius, burst, t,
                game.getGlobalDamageMultiplier(), 0, null, null, t.canSeeCamo(), false, null);
            for (HitContext h : hits) {
                Enemy e = h.target;
                if (e != null && e.isAlive() && e.isBoss()) {
                    e.applyStatus(StatusEffect.Kind.SLOW, s.p("bossSlowPct", 0.15), s.p("burstSlowDuration"));
                }
            }
            game.getCombat().emit(VisualEvent.explosion(at, radius, t.getType().primaryRgb));
        });
    }
}
