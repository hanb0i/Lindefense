package lindefense.tower.behavior;

import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Mine;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Trapper Che. Plants mechanical traps that snap shut on the first enemy to step in: normal enemies are held in
 * place for {@code holdDuration}, bosses are far too heavy to hold but still take the damage. Electric Cage (U2)
 * keeps shocking whatever is held; Master Trapper (U3) adds a guaranteed parting burst.
 */
public final class TrapperCheBehavior extends TowerBehavior {
    private static final double SPACING = 52;

    @Override public boolean attack(Game game, Tower t) {
        TowerStats s = t.getStats();
        if (game.getEffects().minesOf(t, "trap").size() >= s.pi("maxTraps")) return false;
        HitSpec hit = s.hit.copy();
        Mine m = HeroShots.plant(game, t, hit, SPACING, "trap");
        if (m == null) return false;
        m.blastRadius = s.p("trapRadius");
        m.triggerRadius = s.p("trapTrigger");
        m.holdDuration = s.p("holdDuration");
        m.tetherDps = s.p("tetherDps", 0);
        double secondary = s.p("secondaryChance", 0);
        if (secondary > 0) {
            m.secondaryChance = secondary;
            m.secondaryRadius = m.blastRadius * 1.3;
            m.secondaryHit = new HitSpec(s.p("secondaryDamage"), s.hit.type);
        }
        game.getEffects().addMine(m);
        game.getCombat().emit(VisualEvent.text(m.position, "trap set", t.getType().primaryRgb));
        t.onAttacked(game);   // setting a trap spends the attack timer
        return true;
    }
}
