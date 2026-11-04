package lindefense.tower.behavior;

import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Iron Imraan. Hydraulic Smash (U2) turns every {@code smashEvery}-th punch into a ground slam around the hero;
 * Iron Colossus (U3) widens it and briefly stuns the normal enemies it catches (bosses are immune, as always).
 */
public final class IronImraanBehavior extends TowerBehavior {
    private static final String PUNCHES = "punches";

    @Override public void onFire(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        int every = s.pi("smashEvery", 0);
        if (every <= 0) return;
        if (t.addCounter(PUNCHES, 1) % every != 0) return;
        HitSpec smash = new HitSpec(s.p("smashDamage"), s.hit.type);
        smash.knockback = s.hit.knockback;
        double radius = s.p("smashRadius");
        List<HitContext> hits = game.getCombat().areaHits(t.getPosition(), radius, smash, t,
            game.getGlobalDamageMultiplier(), 0, null, null, t.canSeeCamo(), false, null);
        double stun = s.p("smashStun", 0);
        if (stun > 0) {
            for (HitContext h : hits) {
                Enemy e = h.target;
                if (e != null && e.isAlive() && !e.isBoss()) e.applyStatus(StatusEffect.Kind.STUN, 1, stun);
            }
        }
        game.getCombat().emit(VisualEvent.explosion(t.getPosition(), radius, t.getType().primaryRgb));
    }
}
