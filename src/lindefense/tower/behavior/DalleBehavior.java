package lindefense.tower.behavior;

import java.util.ArrayList;
import java.util.List;
import lindefense.combat.HitSpec;
import lindefense.combat.VisualEvent;
import lindefense.effects.Effects;
import lindefense.effects.TrackWalker;
import lindefense.effects.TrackZone;
import lindefense.enemy.Enemy;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * DALL-E (spec 3.4 #9). The sketch arrows (pierce 3, 6 at U3) are the data-driven base attack. This class adds:
 * <ul>
 *   <li><b>Paint zones</b> (base): every {@code zoneInterval} s a TrackZone (kind "paint", radius {@code zoneRadius},
 *       {@code zoneDuration} s, {@code zoneDamage} every {@code zoneTick} s) is painted on the track within range, centred on
 *       the most advanced enemy in range (else the most advanced track point in range).</li>
 *   <li><b>U2 Masterpiece Explosion</b>: zones apply ARMOR CRACK to non-bosses. "Downgrading armored enemies into weaker
 *       forms" is defined as: every non-boss FORTIFIED enemy inside a cracking paint zone is permanently stripped of
 *       Fortified (Enemy.stripFortified: back to its normal max HP, current HP capped). Lead-type bodies cannot be
 *       "downgraded" further, so they receive the ARMOR CRACK only (which removes their Sharp immunity); a Radix Sort in an
 *       armoured phase therefore becomes Sharp-vulnerable while inside the zone.</li>
 *   <li><b>U1/U3 Living Illustration</b>: every {@code creatureInterval} s, {@code creatureCount} creatures (TrackWalkers,
 *       kind "creature") start at the most advanced track point in range and walk BACKWARD (toward the entrance).</li>
 *   <li><b>Outpainting Expansion</b> (player-targeted): a "outpaint" TrackZone with a speed cap on the snapped track point.</li>
 * </ul>
 */
public final class DalleBehavior extends TowerBehavior {
    /** Geometry sampling step (px) used to find the stretch of track inside a tower's range. */
    static final double SAMPLE_STEP = 8;

    /** A sampled point on a route. */
    static final class Spot {
        final Path route; final double dist; final Vec pos;
        Spot(Path route, double dist, Vec pos) { this.route = route; this.dist = dist; this.pos = pos; }
    }

    /** All sampled track points within {@code range} of the tower (every route, ordered along each route). */
    static List<Spot> trackSpotsInRange(Game game, Tower t, double range) {
        List<Spot> out = new ArrayList<>();
        for (Path r : game.getMap().getRoutes()) {
            double len = r.getTotalLength();
            for (double d = 0; d <= len; d += SAMPLE_STEP) {
                Vec p = r.positionAt(d);
                if (p.dist(t.getPosition()) <= range) out.add(new Spot(r, d, p));
            }
        }
        return out;
    }

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        if (t.periodic("paint", s.p("zoneInterval"), dt)) paintZone(game, t, s);
        if (s.has("creatureInterval") && t.periodic("creatures", s.p("creatureInterval"), dt)) spawnCreatures(game, t, s);
        if (s.has("zoneArmorCrack")) downgradeArmored(game, t);
    }

    private void paintZone(Game game, Tower t, TowerStats s) {
        double range = t.effectiveRange(game);
        Enemy lead = null;
        for (Enemy e : enemiesWithin(game, t.getPosition(), range)) {
            if (lead == null || e.getRemainingDistance() < lead.getRemainingDistance()) lead = e;
        }
        Vec at = null;
        if (lead != null) at = lead.getPosition();
        else {
            Spot best = null;
            for (Spot sp : trackSpotsInRange(game, t, range)) {
                if (best == null || sp.route.getTotalLength() - sp.dist < best.route.getTotalLength() - best.dist) best = sp;
            }
            if (best != null) at = best.pos;
        }
        if (at == null) return;
        TrackZone z = new TrackZone(at, s.p("zoneRadius"), t);
        z.duration = s.p("zoneDuration");
        z.tickInterval = s.p("zoneTick");
        z.tickHit = new HitSpec(s.p("zoneDamage"), s.hit.type);
        z.armorCrack = s.has("zoneArmorCrack");
        z.kind = "paint";
        z.rgb = t.getType().primaryRgb;
        game.getEffects().addZone(z);
        game.getCombat().emit(VisualEvent.ability(at, z.radius, z.rgb));
    }

    private void spawnCreatures(Game game, Tower t, TowerStats s) {
        List<Spot> spots = trackSpotsInRange(game, t, t.effectiveRange(game));
        if (spots.isEmpty()) return;
        // per route, the most advanced in-range track point is where the creatures enter
        List<Spot> starts = new ArrayList<>();
        for (Spot sp : spots) {
            Spot cur = null;
            for (Spot o : starts) if (o.route == sp.route) cur = o;
            if (cur == null) starts.add(sp);
            else if (sp.dist > cur.dist) starts.set(starts.indexOf(cur), sp);
        }
        int n = s.pi("creatureCount");
        HitSpec hit = new HitSpec(s.p("creatureDamage"), s.hit.type);
        for (int i = 0; i < n; i++) {
            Spot st = starts.get(i % starts.size());
            double start = Math.min(st.route.getTotalLength(), st.dist + (i / starts.size()) * s.p("creatureSpacing"));
            TrackWalker w = new TrackWalker(st.route, start, 0, s.p("creatureSpeed"), t, hit);
            w.pierce = s.pi("creaturePierce");
            w.detection = t.canSeeCamo();
            w.kind = "creature";
            w.rgb = t.getType().primaryRgb;
            game.getEffects().addWalker(w);
        }
        game.getCombat().emit(VisualEvent.ability(starts.get(0).pos, t.getRadius(), t.getType().primaryRgb));
    }

    /** U2: non-boss Fortified enemies standing in a cracking paint zone lose Fortified. */
    private void downgradeArmored(Game game, Tower t) {
        List<TrackZone> zones = game.getEffects().zonesOf(t, "paint");
        if (zones.isEmpty()) return;
        List<Enemy> pool = new ArrayList<>();
        for (TrackZone z : zones) {
            if (!z.armorCrack) continue;
            game.getEnemyManager().getGrid().near(z.center.x, z.center.y, z.radius, pool);
            for (Enemy e : pool) {
                if (!e.isAlive() || e.isStored() || e.isBoss() || !e.isFortified() || !z.contains(e)) continue;
                e.stripFortified();
                game.getCombat().emit(VisualEvent.text(e.getPosition(), "Downgraded", t.getType().primaryRgb));
            }
        }
    }

    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        if (target == null) return false;
        AbilityDef a = t.getAbility();
        Effects.TrackPoint tp = game.getEffects().nearestTrackPoint(target);
        if (tp == null) return false;
        TrackZone z = new TrackZone(tp.position, a.p("radius"), t);
        z.duration = a.p("duration");
        z.speedCap = a.p("speedCap");
        if (a.has("damage")) {   // the unlocked canvas also burns everything standing in it
            z.tickInterval = a.p("tick");
            z.tickHit = new HitSpec(a.p("damage"), lindefense.combat.DamageType.MAGIC);
        }
        z.kind = "outpaint";
        z.rgb = t.getType().secondaryRgb;
        game.getEffects().addZone(z);
        game.getCombat().emit(VisualEvent.ability(tp.position, z.radius, z.rgb));
        return true;
    }
}
