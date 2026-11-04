package lindefense.tower.behavior;

import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Barrage;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Abhi-Ace. He flies, so his missiles ignore line of sight (set in the data as {@code ignoresLos}); Ace of the
 * Skies (U3) adds a bombing run every {@code bombInterval} seconds on the densest crowd.
 */
public final class AbhiAceBehavior extends TowerBehavior {
    private static final String BOMB = "bombTimer";

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double interval = s.p("bombInterval", 0);
        if (interval <= 0 || !t.periodic(BOMB, interval, dt)) return;
        HitSpec bomb = new HitSpec(s.p("bombDamage"), s.hit.type);
        Barrage b = new Barrage(t, bomb, 1, s.p("bombRadius"));
        b.aim = Barrage.Aim.DENSEST;
        b.rgb = t.getType().primaryRgb;
        Vec at = game.getEffects().fire(b);
        if (at != null) game.getCombat().emit(VisualEvent.ability(at, s.p("bombRadius"), t.getType().primaryRgb));
    }
}
