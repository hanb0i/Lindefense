package lindefense.tower.behavior;

import lindefense.combat.AttackContext;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/** Boom Sam. Nuclear Boom (U3) adds a huge extra detonation on every {@code nukeEvery}-th attack. */
public final class BoomSamBehavior extends TowerBehavior {
    private static final String THROWS = "throws";

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        int every = s.pi("nukeEvery", 0);
        if (every <= 0) return;
        if (t.addCounter(THROWS, 1) % every != 0) return;
        Vec at = c.primary != null ? c.primary.getPosition() : t.getPosition();
        HitSpec nuke = new HitSpec(s.p("nukeDamage"), s.hit.type);
        double radius = s.p("nukeRadius");
        game.getEffects().schedule(0.25, () -> {
            game.getCombat().areaHit(at, radius, nuke, t, game.getGlobalDamageMultiplier(), 9999, null);
            game.getCombat().emit(VisualEvent.explosion(at, radius, 0xffd34d));
            game.getCombat().emit(VisualEvent.ability(at, radius * 1.2, t.getType().primaryRgb));
        });
    }
}
