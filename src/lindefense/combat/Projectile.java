package lindefense.combat;

import java.util.HashSet;
import java.util.Set;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * A travelling projectile. Projectiles home on their target while it is alive (so displayed shots really
 * land), collide with any enemy whose radius they enter, and support pierce, splash, bounce (with a speed gain
 * per bounce) and clone behaviour. Build one from a {@link Shot} and fire it with {@link Combat#fire(Shot)}.
 */
public class Projectile {
    /**
     * Custom collision logic for one shot (hero and Zethos projectiles). When a shot has a handler, the combat engine
     * records the enemy in {@link #getHitIds()} and hands the whole collision to it instead of the generic
     * pierce / splash / bounce code; the handler decides damage, splash, pierce, bounces and when to {@link #kill()}.
     */
    public interface ImpactHandler {
        void impact(Game game, Projectile p, Enemy e);
    }

    /** Mutable description of a shot; every field has a sensible default derived from the tower's stats. */
    public static final class Shot {
        public Tower source;
        /** Stats used for sprites and defaults (the tower's stats, or a companion's own stats). */
        public TowerStats stats;
        public HitSpec hit;
        public Vec start;
        public Enemy target;
        public double damageMult = 1;
        public double extraDamage;
        public int pierce = 1;
        public int bounces;
        public double bounceRange = 90;
        /** Speed multiplier gained per bounce (0.10 = +10%). */
        public double bounceSpeedGain;
        /** Total pieces after the first hit (2 = splits into 2). */
        public int clones;
        public double splash;
        public double speed = 400;
        public boolean detection;
        public int rgb;
        public String tag;
        /** Whether hits receive the source tower's buffed flat damage (companions/drones: false). */
        public boolean buffed = true;
        /** Optional custom collision logic (see {@link ImpactHandler}); null = generic behaviour. */
        public ImpactHandler onImpact;

        /** A shot for a tower with all values taken from its current stats and buffs. */
        public static Shot of(Game game, Tower t, Vec start, Enemy target) {
            Shot s = new Shot();
            TowerStats st = t.getStats();
            s.damageMult = t.damageMultiplier(game);
            s.source = t; s.stats = st; s.hit = st.hit; s.start = start; s.target = target;
            s.pierce = t.effectivePierce(); s.bounces = st.bounces; s.bounceRange = st.bounceRange;
            s.bounceSpeedGain = st.p("bounceSpeedGain", 0);
            s.clones = st.clones; s.splash = st.splashRadius;
            s.speed = st.projectileSpeed * t.projectileSpeedMult();
            s.detection = t.canSeeCamo(); s.rgb = t.getType().primaryRgb;
            return s;
        }
    }

    private Vec pos;
    private Vec vel;
    private Enemy target;
    private final Shot shot;
    private int pierceLeft;
    private int bouncesLeft;
    private boolean canClone;
    private final Set<Integer> hitIds = new HashSet<>(4);
    private double travelled;
    private final double maxTravel;
    private boolean alive = true;
    private double speed;
    /** Seconds spent without moving; a stalled projectile expires (fixes zero-velocity clones never ending a wave). */
    private double stalled;
    private final double size;
    /** Bounces already taken. */
    private int bounced;
    /** Free-form marker for custom impact handlers (Zethos: 1 = the next collision is a bounce hit). */
    public int handlerMark;

    public Projectile(Shot shot) {
        this.shot = shot;
        this.pos = shot.start;
        this.target = shot.target;
        this.speed = shot.speed;
        this.pierceLeft = Math.max(1, shot.pierce);
        this.bouncesLeft = shot.bounces;
        this.canClone = shot.clones > 1;
        this.maxTravel = shot.stats.range * 1.4 + 80;
        this.size = shot.splash > 0 ? 8 : (shot.hit.damage >= 5 ? 7 : 5);
        Vec dir = target.getPosition().sub(pos).normalized();
        if (dir.length() < 0.5) dir = new Vec(1, 0);
        this.vel = dir.scale(speed);
    }

    public Vec getPosition() { return pos; }
    public Vec getVelocity() { return vel; }
    public boolean isAlive() { return alive; }
    /** The credited tower (null never happens for tower shots). */
    public Tower getSource() { return shot.source; }
    public TowerStats getStats() { return shot.stats; }
    public Shot getShot() { return shot; }
    public HitSpec getHit() { return shot.hit; }
    public double getDamageMult() { return shot.damageMult; }
    public int getRgb() { return shot.rgb; }
    public double getSize() { return size; }
    public Set<Integer> getHitIds() { return hitIds; }
    public Enemy getTarget() { return target; }
    public int getBouncesLeft() { return bouncesLeft; }
    public boolean canClone() { return canClone; }
    public void consumeClone() { canClone = false; }
    public boolean hasDetection() { return shot.detection; }
    public void kill() { alive = false; }

    public void retarget(Enemy e) {
        target = e;
        if (e != null) vel = e.getPosition().sub(pos).normalized().scale(speed);
    }

    /** Restarts the travel budget (custom bounce handlers: each bounce gets a full flight). */
    public void resetTravel() { travelled = 0; }

    /** Refills the direct-hit budget (Spear Hanbo's returning spear gets a fresh pierce for the trip home). */
    public void restorePierce(int n) { pierceLeft = Math.max(1, n); }

    /** Drops the homing target and flies straight towards a fixed point (the returning spear's owner). */
    public void aimTowards(Vec at) {
        target = null;
        Vec d = at.sub(pos).normalized();
        if (d.length() < 0.5) d = new Vec(1, 0);
        vel = d.scale(speed);
        travelled = 0;
    }

    /** Number of bounces this projectile has already made. */
    public int getBounced() { return bounced; }
    /** Remaining pierce (direct hits left before the projectile is spent or starts bouncing). */
    public int getPierceLeft() { return pierceLeft; }

    /** Uses up one bounce and applies the speed gain. */
    public void consumeBounce() {
        bouncesLeft--;
        bounced++;
        speed *= 1 + shot.bounceSpeedGain;
    }

    /** Decrements pierce; returns true if the projectile is spent. */
    public boolean consumePierce() {
        pierceLeft--;
        return pierceLeft <= 0;
    }

    /**
     * Moves the projectile; returns false if it expired. The steering maths is done on plain doubles in exactly the
     * order the former {@link Vec} expression used ({@code want.scale(speed / d)}, lerp, {@code normalized().scale(speed)},
     * {@code pos.add(vel.scale(dt))}), so results are bit-identical while only the new position and velocity are
     * allocated.
     */
    public boolean move(double dt) {
        if (!alive) return false;
        if (target != null && target.isAlive() && !target.isStored()) {
            double wx = target.getPosition().x - pos.x, wy = target.getPosition().y - pos.y;
            double d = Math.sqrt(wx * wx + wy * wy);
            if (d > 1) {
                double s = speed / d;
                double dx = wx * s, dy = wy * s;
                double k = Math.min(1, dt * 10);
                double nx = vel.x + (dx - vel.x) * k, ny = vel.y + (dy - vel.y) * k;
                double len = Math.sqrt(nx * nx + ny * ny);
                vel = len < 1e-9 ? new Vec(0 * speed, 0 * speed) : new Vec(nx / len * speed, ny / len * speed);
            }
        } else if (target != null && !target.isAlive()) {
            target = null;
        }
        double sx = vel.x * dt, sy = vel.y * dt;
        pos = new Vec(pos.x + sx, pos.y + sy);
        double stepLen = Math.sqrt(sx * sx + sy * sy);
        travelled += stepLen;
        if (travelled > maxTravel) alive = false;
        // BUGFIX (found via Difficulty calibration): a zero-velocity clone never travels and would stall wave completion forever.
        if (stepLen < 1e-6 && (stalled += dt) > 1.0) alive = false;
        return alive;
    }
}
