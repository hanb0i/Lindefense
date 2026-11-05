package lindefense.tower.behavior;

import java.util.List;
import lindefense.combat.AttackContext;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.combat.Projectile;
import lindefense.combat.VisualEvent;
import lindefense.effects.Effects;
import lindefense.effects.TrackZone;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyGrid;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Mr. Lindemann, the strongest hero. Every number comes from his stats in {@code HeroTowers.mrLindemann()}.
 * <ul>
 *   <li><b>Black hole of Java code</b> (attack): the shot blasts everything in its splash radius, then opens a
 *       singularity ({@link TrackZone} kind {@value #HOLE}) on the nearest track point: {@code holeRadius},
 *       {@code holeDuration} s, crushing {@code holeDps} per second (gravity) and slowing by {@code holeSlow}. At most
 *       {@code maxHoles} are open at once (extra shots still blast).</li>
 *   <li><b>Garbage Collector</b> (U2, {@code gcThreshold}): a non-boss enemy inside one of his singularities whose HP
 *       falls below that fraction of its max is deleted outright (no children).</li>
 *   <li><b>Space warp</b>: every {@code warpInterval} seconds (counted while enemies are on the map) every enemy on the
 *       map, bosses included, is sent {@code warpSeconds} seconds of its own travel back along the track.</li>
 * </ul>
 */
public final class MrLindemannBehavior extends TowerBehavior {
    /** Zone kind of his singularities (the renderer draws them as swirling black holes of code). */
    public static final String HOLE = "blackhole";
    private static final String WARP = "warpTimer";

    /** Blast, then a singularity on the track under the impact. */
    private static final Projectile.ImpactHandler SINGULARITY = (game, p, e) -> {
        Projectile.Shot sh = p.getShot();
        Tower t = sh.source;
        game.getCombat().areaHit(p.getPosition(), sh.splash, sh.hit, t, sh.damageMult, sh.extraDamage, 999, null, sh.detection, sh.buffed, p);
        game.getCombat().emit(VisualEvent.explosion(p.getPosition(), sh.splash, t.getType().secondaryRgb));
        p.kill();
        openSingularity(game, t, p.getPosition());
    };

    private static void openSingularity(Game game, Tower t, Vec at) {
        TowerStats s = t.getStats();
        if (game.getEffects().zonesOf(t, HOLE).size() >= s.pi("maxHoles", 3)) return;
        Effects.TrackPoint tp = game.getEffects().nearestTrackPoint(at);
        if (tp == null || tp.position.dist(at) > s.p("holeRadius") * 2) return;
        double tick = 0.25;
        TrackZone z = new TrackZone(tp.position, s.p("holeRadius"), t);
        z.kind = HOLE;
        z.duration = s.p("holeDuration");
        z.tickInterval = tick;
        z.tickHit = new HitSpec(s.p("holeDps") * tick, DamageType.GRAVITY);
        z.slow = s.p("holeSlow", 0);
        z.detection = t.canSeeCamo();
        z.rgb = t.getType().primaryRgb;
        game.getEffects().addZone(z);
    }

    @Override public void modifyAttack(Game game, Tower t, AttackContext c) {
        c.onImpact = SINGULARITY;
    }

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double gc = s.p("gcThreshold", 0);
        if (gc > 0) garbageCollect(game, t, gc);
        // space warp: the timer runs while there is something to warp, and fires as soon as it is due
        double interval = s.p("warpInterval", 0);
        if (interval <= 0) return;
        double timer = Math.min(interval, t.counter(WARP) + dt);
        t.setCounter(WARP, timer);
        if (timer < interval) return;
        List<Enemy> all = HeroShots.allOnTrack(game);
        if (all.isEmpty()) return;
        t.setCounter(WARP, 0);
        warp(game, t, all, s.p("warpSeconds"));
    }

    /** Seconds until the next space warp (0 = due, waiting for enemies). */
    public static double warpRemaining(Tower t) {
        return Math.max(0, t.getStats().p("warpInterval", 0) - t.counter(WARP));
    }

    private static void warp(Game game, Tower t, List<Enemy> all, double seconds) {
        for (Enemy e : all) {
            if (!e.isAlive() || e.isStored()) continue;
            e.rewind(seconds);
            game.getCombat().emit(VisualEvent.hit(e.getPosition(), t.getType().secondaryRgb));
        }
        game.getCombat().emit(VisualEvent.ability(t.getPosition(), 320, t.getType().primaryRgb));
        game.getCombat().emit(VisualEvent.text(t.getPosition(), "SPACE WARP  -" + (int) Math.round(seconds) + "s", t.getType().primaryRgb));
    }

    /** U2: deletes weakened non-boss enemies standing inside any of his singularities. */
    private static void garbageCollect(Game game, Tower t, double threshold) {
        List<TrackZone> holes = game.getEffects().zonesOf(t, HOLE);
        for (int i = 0, n = holes.size(); i < n; i++) {
            TrackZone z = holes.get(i);
            EnemyGrid.Scan scan = game.getEnemyManager().getGrid().scan(z.center.x, z.center.y, z.radius);
            try {
                for (Enemy e = scan.next(); e != null; e = scan.next()) {
                    if (!e.isAlive() || e.isStored() || e.isBoss() || !z.contains(e)) continue;
                    if (e.getHp() > e.getMaxHp() * threshold) continue;
                    if (e.isCamo() && !e.isRevealed() && !t.canSeeCamo()) continue;
                    game.getCombat().emit(VisualEvent.text(e.getPosition(), "null", t.getType().primaryRgb));
                    game.getEnemyManager().destroyWithoutChildren(e, t);
                }
            } finally {
                scan.close();
            }
        }
    }
}
