package lindefense.tower.behavior;

import lindefense.enemy.Enemy;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Tower;

/**
 * Claude (spec 3.2 #5). Sharp spikes, pierce, Context Snare (flat mark + slow) and the final upgrade's flat
 * bonuses / Lead damage are data-driven. Opus Time-Lock is implemented here.
 */
public final class ClaudeBehavior extends TowerBehavior {
    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        AbilityDef a = t.getAbility();
        double range = a.has("radius") ? a.p("radius") : t.effectiveRange(game);   // radius: the unlocked ability reaches the whole map
        for (Enemy e : enemiesWithin(game, t.getPosition(), range)) {
            if (e.isBoss()) e.applyExactSlow(a.p("bossSlow"), a.p("bossSlowTime"));   // the stated boss slow, not divided by 3
            else e.applyStatus(StatusEffect.Kind.FREEZE, 1, a.p("freezeTime"));
        }
        return true;
    }
}
