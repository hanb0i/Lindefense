package lindefense.tower.behavior;

import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Zippy Matt. The engine's chain already refuses to strike the same enemy twice in one arc; Electric Overload (U2)
 * adds the damage falloff down the chain (each hop deals {@code chainFalloff} of the previous one) and Hyperdrive
 * (U3) ends every {@code burstEvery}-th arc with a lightning explosion.
 */
public final class ZippyMattBehavior extends TowerBehavior {
    private static final String HOP = "hop", ARCS = "arcs";

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        t.setCounter(HOP, 0);
        int every = t.getStats().pi("burstEvery", 0);
        if (every > 0 && (t.counter(ARCS) + 1) % every == 0) c.tag = "burst";
    }

    @Override public void beforeHit(Game game, Tower t, HitContext c) {
        double falloff = t.getStats().p("chainFalloff", 1.0);
        if (falloff >= 1.0 || !c.fromAttack) return;
        int hop = (int) t.counter(HOP);
        c.finalMult *= Math.pow(falloff, hop);
        t.setCounter(HOP, hop + 1);
    }

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        t.addCounter(ARCS, 1);
        if (!"burst".equals(c.tag) || c.primary == null) return;
        TowerStats s = t.getStats();
        Vec at = c.primary.getPosition();
        HitSpec burst = new HitSpec(s.p("burstDamage"), s.hit.type);
        double radius = s.p("burstRadius");
        game.getCombat().areaHit(at, radius, burst, t, game.getGlobalDamageMultiplier(), 9999, null);
        game.getCombat().emit(VisualEvent.explosion(at, radius, t.getType().primaryRgb));
    }
}
