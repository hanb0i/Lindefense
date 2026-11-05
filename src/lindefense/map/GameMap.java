package lindefense.map;

import java.util.ArrayList;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;

/**
 * Base class for all maps. A map owns its routes (ordered waypoint lists),
 * obstacles, buildable-area rules and any unique map mechanics. Mechanics are
 * applied through the hook methods below, which the {@link Game} calls every
 * tick / wave; subclasses override only what they need.
 *
 * All coordinates are in "world" pixels inside a {@link #WIDTH} x {@link #HEIGHT}
 * field; the renderer translates them onto the canvas.
 */
public abstract class GameMap {
    public static final int WIDTH = 1200;
    public static final int HEIGHT = 900;

    /** Half-width of the walkable track; towers may not be placed inside it. */
    public static final double TRACK_HALF_WIDTH = 22;

    protected final List<Path> routes = new ArrayList<>();
    protected final List<Obstacle> obstacles = new ArrayList<>();
    protected final List<Decoration> decorations = new ArrayList<>();

    private final String name;
    private final String difficulty;
    private final String description;

    protected GameMap(String name, String difficulty, String description) {
        this.name = name;
        this.difficulty = difficulty;
        this.description = description;
    }

    public String getName() { return name; }
    public String getDifficulty() { return difficulty; }
    public String getDescription() { return description; }
    public List<Path> getRoutes() { return routes; }
    public List<Obstacle> getObstacles() { return obstacles; }
    public List<Decoration> getDecorations() { return decorations; }

    /** Background colour as packed RGB. */
    public abstract int getBackgroundRgb();
    /** Track colour as packed RGB. */
    public abstract int getTrackRgb();

    /** Short description of the map mechanics for the UI. */
    public abstract String getMechanicSummary();

    // ------------------------------------------------------------------
    // Placement rules
    // ------------------------------------------------------------------

    /** Minimum distance from a tower centre to the track centre line. */
    public double minTrackClearance(double towerRadius) {
        return TRACK_HALF_WIDTH + towerRadius * 0.6;
    }

    /** True if the point is inside the map's buildable region (ignoring other towers). */
    public boolean isBuildable(Vec p, double towerRadius) {
        if (p.x < towerRadius || p.y < towerRadius || p.x > WIDTH - towerRadius || p.y > HEIGHT - towerRadius) return false;
        for (Path r : routes) {
            if (r.distanceToPoint(p) < minTrackClearance(towerRadius)) return false;
        }
        for (Obstacle o : obstacles) {
            if (o.contains(p, towerRadius * 0.7)) return false;
        }
        return isInsideArena(p);
    }

    /** Maps with a non-rectangular arena override this. */
    protected boolean isInsideArena(Vec p) { return true; }

    /** Line-of-sight test between a tower and an enemy position. */
    public boolean hasLineOfSight(Vec from, Vec to) {
        for (Obstacle o : obstacles) {
            if (o.blocksLineOfSight && o.intersectsSegment(from, to)) return false;
        }
        return true;
    }

    // ------------------------------------------------------------------
    // Mechanic hooks (default: no effect)
    // ------------------------------------------------------------------

    /** Called every simulation tick while the game is running. */
    public void update(Game game, double dt) { }

    /** Called when a wave begins. */
    public void onWaveStart(Game game, int wave) { }

    /** Called after an enemy has been moved this tick (for position-triggered mechanics). */
    public void onEnemyMoved(Game game, Enemy e) { }

    /** Extra speed multiplier for an enemy from map mechanics. */
    public double enemySpeedMultiplier(Enemy e) { return 1.0; }

    /** Extra range multiplier for a tower from map mechanics. {@code t} is null for the placement preview. */
    public double towerRangeMultiplier(Game game, Tower t) { return 1.0; }

    /** Extra attack-rate multiplier for a tower from map mechanics. */
    public double towerRateMultiplier(Game game, Tower t) { return 1.0; }

    /** Extra damage multiplier for a tower from map mechanics. */
    public double towerDamageMultiplier(Game game, Tower t) { return 1.0; }

    /** Active map-event banner text, or null. */
    public String getEventText() { return null; }

    /** Resets transient mechanic state when a new game starts on this map. */
    public void reset() { }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /** Random route index for spawning (BREAKING NEWS: a Server Outage closes one lane for the wave). */
    public int pickRoute(Game game) {
        int closed = game.getVariance().closedRoute(routes.size());
        if (closed < 0) return game.getRng().nextInt(routes.size());
        int r = game.getRng().nextInt(routes.size() - 1);
        return r >= closed ? r + 1 : r;
    }

    protected void addDecoration(Decoration d) { decorations.add(d); }

    /** Simple decorative shape description consumed by the renderer. */
    public static final class Decoration {
        public enum Kind { RECT, OVAL, LABEL, LINE }
        public final Kind kind;
        public final double x, y, w, h;
        public final int rgb;
        public final String text;
        public final boolean filled;

        public Decoration(Kind kind, double x, double y, double w, double h, int rgb, String text, boolean filled) {
            this.kind = kind; this.x = x; this.y = y; this.w = w; this.h = h;
            this.rgb = rgb; this.text = text; this.filled = filled;
        }

        public static Decoration rect(double x, double y, double w, double h, int rgb) {
            return new Decoration(Kind.RECT, x, y, w, h, rgb, null, true);
        }
        public static Decoration frame(double x, double y, double w, double h, int rgb) {
            return new Decoration(Kind.RECT, x, y, w, h, rgb, null, false);
        }
        public static Decoration oval(double x, double y, double w, double h, int rgb, boolean filled) {
            return new Decoration(Kind.OVAL, x, y, w, h, rgb, null, filled);
        }
        public static Decoration label(double x, double y, String text, int rgb) {
            return new Decoration(Kind.LABEL, x, y, 0, 0, rgb, text, false);
        }
        public static Decoration line(double x1, double y1, double x2, double y2, int rgb) {
            return new Decoration(Kind.LINE, x1, y1, x2 - x1, y2 - y1, rgb, null, false);
        }
    }
}
