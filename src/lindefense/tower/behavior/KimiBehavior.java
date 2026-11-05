package lindefense.tower.behavior;

import lindefense.combat.AttackContext;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.map.GameMap;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Kimi (spec 3.6 #19). Implemented here: the consecutive-hit damage bonus (base, max +3 / +8 at U2) with +1 pierce
 * per stack (U2) and the Memory Storage permanent bonus (U1+: +1 per {@code memoryPer} pops, capped at
 * {@code memoryCap}; pops are {@link Tower#getKills()}). The x0.5 vs Fortified is data-driven. The U3 crystal burst and the
 * Infinite Context Burst ability are implemented here.
 */
public final class KimiBehavior extends TowerBehavior {
    /** Permanent memory bonus damage for the info panel / ability: floor(pops / memoryPer), capped. */
    public static int memoryStacks(Tower t) {
        TowerStats s = t.getStats();
        if (!s.has("memoryPer")) return 0;
        return (int) Math.min(s.p("memoryCap"), Math.floor(t.getKills() / s.p("memoryPer")));
    }

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        if (c.primary == null) return;
        int streak = (int) Math.min(s.p("streakMax"), t.registerStreak(c.primary.getId()) * s.p("streakStep"));
        c.extraDamage += streak + memoryStacks(t);
        c.pierce += (int) (streak * s.p("pierceBonusPerStack", 0));
    }

    /** U3 Infinite Context: every burstEvery-th attack also detonates a crystal burst at the primary target. */
    @Override public void onFire(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        if (!s.has("burstEvery") || c.primary == null) return;
        if (t.addCounter("attacks", 1) < s.p("burstEvery")) return;
        t.setCounter("attacks", 0);
        HitSpec h = new HitSpec(s.p("burstDamage"), DamageType.MAGIC);
        h.multVsFortified = s.hit.multVsFortified; // all Kimi damage is halved vs Fortified
        Vec at = c.primary.getPosition();
        double radius = s.p("burstSplash");
        game.getCombat().areaHit(at, radius, h, t, t.damageMultiplier(game), 9999, null);
        game.getCombat().emit(VisualEvent.explosion(at, radius, t.getType().secondaryRgb));
    }

    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        AbilityDef a = t.getAbility();
        int stacks = memoryStacks(t);
        HitSpec full = new HitSpec(stacks * a.p("damagePerStack"), DamageType.TRUE);
        HitSpec half = new HitSpec(full.damage * a.p("bossFraction"), DamageType.TRUE);
        java.util.List<Enemy> list = game.getEnemyManager().getEnemies();
        for (int i = 0; i < list.size(); i++) {
            Enemy e = list.get(i);
            if (stacks == 0) break;   // no memory yet: the burst fires but has nothing to deal
            if (!e.isAlive() || e.isStored() || (e.isFortified() && a.p("hitsFortified", 0) <= 0)) continue;
            Vec p = e.getPosition();
            if (p.x < 0 || p.y < 0 || p.x > GameMap.WIDTH || p.y > GameMap.HEIGHT) continue;   // on screen only
            game.getCombat().applyHit(e, e.isBoss() ? half : full, t, 1, 0);
        }
        game.getCombat().emit(VisualEvent.banner("INFINITE CONTEXT BURST", t.getType().primaryRgb, 1.2));
        return true;
    }
}
