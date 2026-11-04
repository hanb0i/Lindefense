package lindefense.tower.behavior;

import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Sage Aarav. Never attacks: on a timer he restores the player's integrity (lives), which is the survival resource
 * leaks take away, never past the difficulty's starting maximum. Divine Restoration (U3) adds a single
 * emergency restoration per match when integrity drops below a quarter.
 */
public final class SageAaravBehavior extends TowerBehavior {
    private static final String TIMER = "healTimer", EMERGENCY = "emergencyUsed";

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double interval = s.p("healInterval");
        if (interval > 0 && t.periodic(TIMER, interval, dt)) {
            int healed = game.restoreLives((int) s.p("healAmount"));
            if (healed > 0) {
                game.getCombat().emit(VisualEvent.text(t.getPosition(), "+" + healed + " integrity", t.getType().primaryRgb));
                game.getCombat().emit(VisualEvent.ability(t.getPosition(), s.fieldRadius, t.getType().primaryRgb));
            }
        }
        double threshold = s.p("emergencyThreshold", 0);
        if (threshold > 0 && t.counter(EMERGENCY) == 0) {
            int max = game.getMaxLives();
            if (game.getLives() > 0 && game.getLives() < max * threshold) {
                t.setCounter(EMERGENCY, 1);
                int healed = game.restoreLives((int) Math.ceil(max * s.p("emergencyRestore")));
                game.getCombat().emit(VisualEvent.text(t.getPosition(), "DIVINE RESTORATION +" + healed, 0xffe9a8));
                game.getCombat().emit(VisualEvent.ability(t.getPosition(), s.fieldRadius * 1.5, 0xffe9a8));
            }
        }
    }
}
