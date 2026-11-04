package lindefense.tower.behavior;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Barrage;
import lindefense.enemy.Enemy;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Kaiju Kai. At base he roars (the data-driven splash attack). From Atomic Breath (U1) the attack becomes a
 * sustained beam: aiming locks on a target, then every {@code beamTick} seconds the beam burns every enemy along
 * its line until {@code beamDuration} is spent. Cataclysmic Kaiju (U3) adds a periodic atomic blast on the densest
 * crowd, independent of the beam.
 */
public final class KaijuKaiBehavior extends TowerBehavior {
    private static final String BEAM_LEFT = "beamLeft", BEAM_TICK = "beamTick", BLAST = "blastTimer";
    private static final String BEAM_DIR_X = "beamDirX", BEAM_DIR_Y = "beamDirY";

    private static boolean hasBeam(TowerStats s) { return s.p("beamDuration", 0) > 0; }

    @Override public boolean attack(Game game, Tower t) {
        TowerStats s = t.getStats();
        if (!hasBeam(s)) return game.getCombat().genericAttack(t);
        List<Enemy> targets = game.getCombat().acquireTargets(t, 1);
        if (targets.isEmpty()) return false;
        Vec dir = targets.get(0).getPosition().sub(t.getPosition()).normalized();
        t.setCounter(BEAM_DIR_X, dir.x);
        t.setCounter(BEAM_DIR_Y, dir.y);
        t.setCounter(BEAM_LEFT, s.p("beamDuration"));
        t.setCounter(BEAM_TICK, 0);
        t.setLastTarget(targets.get(0));
        t.onAttacked(game);   // spends the attack timer; without it the beam would restart every tick
        return true;
    }

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double left = t.counter(BEAM_LEFT);
        if (left > 0) {
            t.setCounter(BEAM_LEFT, Math.max(0, left - dt));
            double tick = s.p("beamTick", 0.25);
            if (t.periodic(BEAM_TICK, tick, dt)) burn(game, t, s);
        }
        double blastInterval = s.p("blastInterval", 0);
        if (blastInterval > 0 && t.periodic(BLAST, blastInterval, dt)) {
            HitSpec blast = new HitSpec(s.p("blastDamage"), s.hit.type);
            Barrage b = new Barrage(t, blast, 1, s.p("blastRadius"));
            b.aim = Barrage.Aim.BOSS_ELSE_DENSEST;
            b.rgb = t.getType().primaryRgb;
            Vec at = game.getEffects().fire(b);
            if (at != null) game.getCombat().emit(VisualEvent.ability(at, s.p("blastRadius"), t.getType().primaryRgb));
        }
    }

    /** One beam tick: a line from the hero out to its range, damaging everything it touches once. */
    private void burn(Game game, Tower t, TowerStats s) {
        Vec dir = new Vec(t.counter(BEAM_DIR_X), t.counter(BEAM_DIR_Y));
        if (dir.length() < 0.5) return;
        double range = t.effectiveRange(game);
        Vec origin = t.getPosition();
        Vec end = origin.add(dir.normalized().scale(range));
        double width = s.p("beamWidth", 24);
        HitSpec hit = s.hit.copy();
        hit.damage = s.p("beamDamage");
        List<Enemy> onLine = new ArrayList<>();
        for (Enemy e : game.getEnemyManager().getEnemies()) {
            if (!e.isAlive() || e.isStored() || !e.isTargetableBy(t.canSeeCamo())) continue;
            if (Path.pointSegmentDistance(e.getPosition(), origin, end) <= width + e.getRadius()) onLine.add(e);
        }
        for (Enemy e : onLine) game.getCombat().applyHit(e, hit, t, game.getGlobalDamageMultiplier(), 0);
        game.getCombat().emit(VisualEvent.beam(origin, end, t.getType().primaryRgb));
    }

    /** True while the atomic beam is firing (the renderer draws the breath). */
    public static boolean isBeaming(Tower t) { return t.counter(BEAM_LEFT) > 0; }
}
