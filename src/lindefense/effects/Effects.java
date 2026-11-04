package lindefense.effects;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;

/**
 * Owns the reusable simulation primitives that tower behaviours spawn: {@link TrackZone}, {@link TrackWalker},
 * {@link Drone}, {@link NodeHazard}, barrages and delayed tasks. Ticked once per simulation step by
 * {@link Game#step}; everything is removed automatically when it expires or its owner tower is sold.
 * The renderer can read the live lists through the {@code get*} accessors.
 */
public final class Effects {
    private final Game game;
    private final List<TrackZone> zones = new ArrayList<>();
    private final List<TrackWalker> walkers = new ArrayList<>();
    private final List<Drone> drones = new ArrayList<>();
    private final List<NodeHazard> hazards = new ArrayList<>();
    private final List<Mine> mines = new ArrayList<>();
    private final List<Task> tasks = new ArrayList<>();

    private static final class Task {
        double delay; final Runnable action;
        Task(double delay, Runnable action) { this.delay = delay; this.action = action; }
    }

    public Effects(Game game) { this.game = game; }

    // ---------------- registration ----------------
    public TrackZone addZone(TrackZone z) { zones.add(z); return z; }
    public TrackWalker addWalker(TrackWalker w) { walkers.add(w); return w; }
    public Drone addDrone(Drone d) { drones.add(d); return d; }
    public NodeHazard addHazard(NodeHazard h) { hazards.add(h); return h; }
    public Mine addMine(Mine m) { mines.add(m); return m; }

    /** Runs {@code action} after {@code delay} game seconds (0 = on the next tick). */
    public void schedule(double delay, Runnable action) { tasks.add(new Task(delay, action)); }

    /** Fires a barrage: aim is resolved now, shells land {@code stagger} seconds apart. Returns the aim point or null. */
    public Vec fire(Barrage b) {
        Vec aim = b.resolveAim(game);
        if (aim == null) return null;
        final Vec target = aim;
        for (int i = 0; i < b.count; i++) {
            if (i == 0 && b.stagger <= 0) { b.land(game, target); continue; }
            schedule(i * b.stagger, () -> b.land(game, target));
        }
        return aim;
    }

    // ---------------- queries ----------------
    public List<TrackZone> getZones() { return Collections.unmodifiableList(zones); }
    public List<TrackWalker> getWalkers() { return Collections.unmodifiableList(walkers); }
    public List<Drone> getDrones() { return Collections.unmodifiableList(drones); }
    public List<NodeHazard> getHazards() { return Collections.unmodifiableList(hazards); }
    public List<Mine> getMines() { return Collections.unmodifiableList(mines); }

    /** Live mines / traps belonging to a tower (Cami-Mine, Trapper Che cap their field size with this). */
    public List<Mine> minesOf(Tower owner, String kind) {
        List<Mine> l = new ArrayList<>();
        for (Mine m : mines) if (m.owner == owner && m.isAlive() && (kind == null || kind.equals(m.kind))) l.add(m);
        return l;
    }

    /** Live drones belonging to a tower. */
    public List<Drone> dronesOf(Tower owner, String kind) {
        List<Drone> l = new ArrayList<>();
        for (Drone d : drones) if (d.owner == owner && d.isAlive() && (kind == null || kind.equals(d.kind))) l.add(d);
        return l;
    }
    public List<TrackZone> zonesOf(Tower owner, String kind) {
        List<TrackZone> l = new ArrayList<>();
        for (TrackZone z : zones) if (z.owner == owner && z.isAlive() && (kind == null || kind.equals(z.kind))) l.add(z);
        return l;
    }

    /** Removes everything a sold tower created. */
    public void removeOwnedBy(Tower owner) {
        for (TrackZone z : zones) if (z.owner == owner) z.kill();
        for (TrackWalker w : walkers) if (w.owner == owner) w.kill();
        for (Drone d : drones) if (d.owner == owner) d.kill();
        for (NodeHazard h : hazards) if (h.owner == owner) h.kill();
        for (Mine m : mines) if (m.owner == owner) m.kill();
    }

    public void clear() { zones.clear(); walkers.clear(); drones.clear(); hazards.clear(); mines.clear(); tasks.clear(); }

    // ---------------- track helpers ----------------
    /** A point on a route: the route, its index in the map's route list, the distance along it and the position. */
    public static final class TrackPoint {
        public final Path route; public final int routeIndex; public final double distance; public final Vec position;
        TrackPoint(Path route, int routeIndex, double distance, Vec position) {
            this.route = route; this.routeIndex = routeIndex; this.distance = distance; this.position = position;
        }
    }

    /** The point on any route nearest to {@code p} (for snapping player-chosen ability targets onto the track). */
    public TrackPoint nearestTrackPoint(Vec p) {
        TrackPoint best = null;
        double bestD = Double.MAX_VALUE;
        List<Path> routes = game.getMap().getRoutes();
        for (int i = 0; i < routes.size(); i++) {
            Path r = routes.get(i);
            double d = r.nearestDistanceAlong(p);
            Vec q = r.positionAt(d);
            double dist = q.dist(p);
            if (dist < bestD) { bestD = dist; best = new TrackPoint(r, i, d, q); }
        }
        return best;
    }

    /**
     * Track bends (interior waypoints) of every route within {@code range} of {@code from}, as track points.
     * Used for "nearest track bend in range" (Mistral Hurricane).
     */
    public List<TrackPoint> bendsInRange(Vec from, double range) {
        List<TrackPoint> out = new ArrayList<>();
        List<Path> routes = game.getMap().getRoutes();
        for (int i = 0; i < routes.size(); i++) {
            Path r = routes.get(i);
            List<Vec> wp = r.getWaypoints();
            for (int k = 1; k + 1 < wp.size(); k++) {
                if (wp.get(k).dist(from) <= range) out.add(new TrackPoint(r, i, r.nearestDistanceAlong(wp.get(k)), wp.get(k)));
            }
        }
        out.sort((a, b) -> Double.compare(a.position.distSq(from), b.position.distSq(from)));
        return out;
    }

    // ---------------- tick ----------------
    public void update(double dt) {
        for (int i = 0; i < tasks.size(); i++) {
            Task t = tasks.get(i);
            t.delay -= dt;
            if (t.delay <= 0) { tasks.remove(i--); t.action.run(); }
        }
        for (int i = 0; i < zones.size(); i++) zones.get(i).update(game, dt);
        for (int i = 0; i < hazards.size(); i++) hazards.get(i).update(game, dt);
        for (int i = 0; i < mines.size(); i++) mines.get(i).update(game, dt);
        for (int i = 0; i < walkers.size(); i++) walkers.get(i).update(game, dt);
        for (int i = 0; i < drones.size(); i++) drones.get(i).update(game, dt);
        zones.removeIf(z -> !z.isAlive());
        hazards.removeIf(h -> !h.isAlive());
        mines.removeIf(m -> !m.isAlive());
        walkers.removeIf(w -> !w.isAlive());
        drones.removeIf(d -> !d.isAlive());
    }
}
