package lindefense.tower.behavior;

import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Sunny Joe. Never attacks: a steady side hustle pays {@code income} into the player's balance every
 * {@code incomeInterval} seconds, and from Business Expansion (U2) a much larger {@code bonus} lands every
 * {@code bonusInterval} seconds on top.
 */
public final class SunnyJoeBehavior extends TowerBehavior {
    private static final String TIMER = "incomeTimer", BONUS = "bonusTimer";

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double interval = s.p("incomeInterval");
        if (interval > 0 && t.periodic(TIMER, interval, dt)) game.addCash(s.p("income"), t.getPosition());
        double bonusInterval = s.p("bonusInterval", 0);
        if (bonusInterval > 0 && t.periodic(BONUS, bonusInterval, dt)) game.addCash(s.p("bonus"), t.getPosition());
    }
}
