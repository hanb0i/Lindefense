package lindefense.tower.behavior;

import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Justin Time. Temporal Field (U2) stalls every normal enemy on the map on a timer; Time Freeze (U3) speeds the
 * field up and adds a rarer full stop. Bosses are never frozen and never take the full field slow: they get the
 * reduced boss value, consistent with the global boss rules.
 */
public final class JustinTimeBehavior extends TowerBehavior {
    private static final String FIELD = "fieldTimer", FREEZE = "freezeTimer";

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double fieldInterval = s.p("fieldInterval", 0);
        if (fieldInterval > 0 && t.periodic(FIELD, fieldInterval, dt)) {
            double slow = s.p("fieldSlow"), bossSlow = s.p("fieldBossSlow"), duration = s.p("fieldDuration");
            for (Enemy e : HeroShots.allOnTrack(game)) {
                e.applyStatus(StatusEffect.Kind.SLOW, e.isBoss() ? bossSlow : slow, duration);
            }
            game.getCombat().emit(VisualEvent.text(t.getPosition(), "TEMPORAL FIELD", t.getType().primaryRgb));
            game.getCombat().emit(VisualEvent.ability(t.getPosition(), t.effectiveRange(game) * 1.4, t.getType().primaryRgb));
        }
        double freezeInterval = s.p("freezeInterval", 0);
        if (freezeInterval > 0 && t.periodic(FREEZE, freezeInterval, dt)) {
            double duration = s.p("freezeDuration"), bossSlow = s.p("freezeBossSlow");
            for (Enemy e : HeroShots.allOnTrack(game)) {
                if (e.isBoss()) e.applyStatus(StatusEffect.Kind.SLOW, bossSlow, duration);
                else e.applyStatus(StatusEffect.Kind.FREEZE, 1, duration);
            }
            game.getCombat().emit(VisualEvent.text(t.getPosition(), "TIME FREEZE", 0xffffff));
        }
    }
}
