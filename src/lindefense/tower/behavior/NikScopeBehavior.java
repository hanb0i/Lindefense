package lindefense.tower.behavior;

import lindefense.combat.HitContext;
import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Nik-Scope. Camo detection and armour piercing come from the data; Deadeye (U3) adds the critical hit, rolled per
 * enemy hit so a piercing shot can crit one target and not the next.
 */
public final class NikScopeBehavior extends TowerBehavior {
    @Override public void beforeHit(Game game, Tower t, HitContext c) {
        TowerStats s = t.getStats();
        double chance = s.p("critChance", 0);
        if (chance <= 0 || !c.fromAttack) return;
        if (!game.getRng().chance(chance)) return;
        c.finalMult *= s.p("critMult");
        c.tag = "crit";
    }

    @Override public void onHit(Game game, Tower t, HitContext c) {
        if ("crit".equals(c.tag) && c.target != null) {
            game.getCombat().emit(VisualEvent.text(c.target.getPosition(), "CRIT", t.getType().primaryRgb));
        }
    }
}
