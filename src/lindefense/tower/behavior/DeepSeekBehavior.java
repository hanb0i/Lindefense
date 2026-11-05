package lindefense.tower.behavior;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * DeepSeek (spec 3.3 #7). Map-wide instant sniper (unlimited range, ignores line of sight), 3-shot volleys with
 * pierce 3 (U1) and the V4 Pro multipliers (U3) are data-driven. Recursive Lock (consecutive-hit bonus, default
 * Strongest targeting) and the Deep Reasoning Strike are implemented here.
 */
public final class DeepSeekBehavior extends TowerBehavior {
    @Override public void onUpgraded(Game game, Tower t) {
        if (t.getStats().has("defaultStrongest") && t.counter("strongestApplied") == 0) {
            t.setCounter("strongestApplied", 1);
            t.setTargeting(Targeting.STRONGEST);
        }
    }

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        if (!s.has("streakMax") || c.primary == null) return;
        int streak = t.registerStreak(c.primary.getId());
        c.extraDamage += Math.min(s.p("streakMax"), streak * s.p("streakStep"));
    }

    /**
     * R1 Deep Reasoning Strike: destroys the {@code count} strongest non-boss enemies outright (no children; each
     * parent's cash is paid once) and, if the ability has {@code bossDamagePct}, strikes every boss for that fraction
     * of its max HP ({@code palantirDamagePct} for Palantir) as TRUE damage. Fails only if there is nothing to hit.
     */
    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        AbilityDef a = t.getAbility();
        int count = (int) a.p("count", 1);
        List<Enemy> pool = new ArrayList<>();
        List<Enemy> bosses = new ArrayList<>();
        for (Enemy e : game.getEnemyManager().getEnemies()) {
            if (!e.isAlive() || e.isStored()) continue;
            if (e.isBoss()) bosses.add(e); else pool.add(e);
        }
        double bossPct = a.p("bossDamagePct", 0);
        if (pool.isEmpty() && (bossPct <= 0 || bosses.isEmpty())) return false;
        pool.sort((x, y) -> Double.compare(y.getHp(), x.getHp()));
        for (int i = 0; i < Math.min(count, pool.size()); i++) {
            Enemy e = pool.get(i);
            game.getCombat().emit(VisualEvent.beam(t.getPosition(), e.getPosition(), t.getType().primaryRgb));
            game.getEnemyManager().destroyWithoutChildren(e, t);
        }
        if (bossPct > 0) {
            for (Enemy b : bosses) {
                double pct = b.getType() == EnemyType.PALANTIR ? a.p("palantirDamagePct", bossPct) : bossPct;
                game.getCombat().emit(VisualEvent.beam(t.getPosition(), b.getPosition(), t.getType().primaryRgb));
                game.getCombat().applyHit(b, new HitSpec(b.getMaxHp() * pct, DamageType.TRUE), t, 1, 0);
            }
        }
        return true;
    }
}
