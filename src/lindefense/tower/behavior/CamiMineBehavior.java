package lindefense.tower.behavior;

import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Mine;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Cami-Mine. Her attack timer plants a proximity mine on the track inside her range instead of shooting: it arms,
 * waits for an enemy and detonates once. The field is capped at {@code maxMines}, and because each mine fires once
 * and never blocks movement, a lane can always be walked through.
 */
public final class CamiMineBehavior extends TowerBehavior {
    /** Minimum gap between two planted mines, so a field covers a stretch instead of stacking on one spot. */
    private static final double SPACING = 46;

    @Override public boolean attack(Game game, Tower t) {
        TowerStats s = t.getStats();
        if (game.getEffects().minesOf(t, "mine").size() >= s.pi("maxMines")) return false;
        HitSpec hit = s.hit.copy();
        Mine m = HeroShots.plant(game, t, hit, SPACING, "mine");
        if (m == null) return false;
        m.blastRadius = s.p("mineRadius");
        m.triggerRadius = s.p("mineTrigger");
        m.armTime = s.p("mineArm");
        double secondary = s.p("secondaryChance", 0);
        if (secondary > 0) {
            m.secondaryChance = secondary;
            m.secondaryRadius = m.blastRadius;
            HitSpec sec = new HitSpec(s.p("secondaryDamage"), s.hit.type);
            m.secondaryHit = sec;
        }
        game.getEffects().addMine(m);
        game.getCombat().emit(VisualEvent.text(m.position, "mine set", t.getType().primaryRgb));
        t.onAttacked(game);   // planting spends the attack timer
        return true;
    }
}
