package lindefense.tower.behavior;

import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Effects;
import lindefense.effects.TrackZone;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Thorn Tuhin. The poison is the attack's own damage-over-time; Overgrowth (U2) additionally grows thorny vines
 * across a stretch of track inside his range every {@code vineInterval} seconds, capped at {@code maxVines} live
 * patches so they expire instead of carpeting the map. Nature's Wrath (U3) makes the vines bite harder and slow.
 */
public final class ThornTuhinBehavior extends TowerBehavior {
    private static final String TIMER = "vineTimer";

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double interval = s.p("vineInterval", 0);
        if (interval <= 0 || !t.periodic(TIMER, interval, dt)) return;
        if (game.getEffects().zonesOf(t, "vines").size() >= s.pi("maxVines", 2)) return;
        Effects.TrackPoint tp = game.getEffects().nearestTrackPoint(t.getPosition());
        if (tp == null || tp.position.dist(t.getPosition()) > t.effectiveRange(game)) return;
        HitSpec bite = new HitSpec(s.p("vineDps") * 0.5, s.hit.type);   // applied twice a second
        TrackZone z = new TrackZone(tp.position, s.p("vineRadius"), t);
        z.kind = "vines";
        z.duration = s.p("vineDuration");
        z.tickInterval = 0.5;
        z.tickHit = bite;
        z.slow = s.p("vineSlow", 0);
        z.rgb = t.getType().primaryRgb;
        game.getEffects().addZone(z);
        game.getCombat().emit(VisualEvent.text(tp.position, "overgrowth", t.getType().primaryRgb));
    }
}
