package lindefense.tower.behavior;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.HitContext;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Barrage;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Suno (spec 3.4 #11). Rhythmic sonic projectiles (x2 vs Ceramic, 20 px knockback on Lead) and the faster interval at U3 are
 * data-driven. This class adds U1 Bass Drop (periodic SONIC shockwave around the tower, distance measured to enemy
 * centres), U2 Chord Strike (every {@code chordEvery}-th attack), U3 Uncontrolled Symphony (random sonic explosions on
 * enemies the tower can target in range) and the Symphonic Bass Drop ability (SONIC damage = damagePerSpeed x speed
 * multiplier, bosses capped at bossCap).
 */
public final class SunoBehavior extends TowerBehavior {
    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        if (s.has("bassInterval") && t.periodic("bass", s.p("bassInterval"), dt)) bassDrop(game, t, s);
        if (s.has("symphonyInterval") && t.periodic("symphony", s.p("symphonyInterval"), dt)) symphony(game, t, s);
    }

    private void bassDrop(Game game, Tower t, TowerStats s) {
        double radius = s.p("bassRadius");
        List<Enemy> hit = enemiesWithin(game, t.getPosition(), radius);
        if (hit.isEmpty()) return;
        HitSpec spec = new HitSpec(s.p("bassDamage"), s.hit.type);
        double mult = t.damageMultiplier(game);
        for (Enemy e : hit) {
            HitContext c = new HitContext(e, spec, t);
            c.mult = mult;
            game.getCombat().applyHit(c);
        }
        game.getCombat().emit(VisualEvent.ability(t.getPosition(), radius, t.getType().primaryRgb));
    }

    private void symphony(Game game, Tower t, TowerStats s) {
        List<Enemy> pool = new ArrayList<>();
        for (Enemy e : enemiesWithin(game, t.getPosition(), t.effectiveRange(game))) {
            if (e.isTargetableBy(t.canSeeCamo())) pool.add(e);
        }
        if (pool.isEmpty()) return;
        HitSpec spec = new HitSpec(s.p("symphonyDamage"), s.hit.type);
        for (int i = 0; i < s.pi("symphonyCount"); i++) {
            Enemy target = pool.get(game.getRng().nextInt(pool.size()));
            Barrage b = new Barrage(t, spec, 1, s.p("symphonyRadius"));
            b.aim = Barrage.Aim.POINT;
            b.point = target.getPosition();
            b.rgb = t.getType().secondaryRgb;
            game.getEffects().fire(b);
        }
    }

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        TowerStats s = t.getStats();
        if (!s.has("chordEvery")) return;
        if (((long) t.addCounter("chord", 1)) % s.pi("chordEvery") != 0) return;
        c.editHit().damage = s.p("chordDamage");
        c.pierce += s.pi("chordPierce") - s.pierce; // keep pierce buffs on top of the chord's pierce
        c.tag = "chord";
    }

    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        AbilityDef a = t.getAbility();
        double mult = t.damageMultiplier(game);
        for (Enemy e : new ArrayList<>(game.getEnemyManager().getEnemies())) {
            if (!e.isAlive() || e.isStored()) continue;
            double dmg = a.p("baseDamage", 0) + a.p("damagePerSpeed") * e.speedMultiplier();
            if (e.isBoss()) dmg = Math.min(dmg, a.p("bossCap"));
            HitContext c = new HitContext(e, new HitSpec(dmg, t.getStats().hit.type), t);
            c.mult = mult;
            game.getCombat().applyHit(c);
        }
        game.getCombat().emit(VisualEvent.ability(t.getPosition(), t.getRadius(), t.getType().primaryRgb));
        return true;
    }
}
