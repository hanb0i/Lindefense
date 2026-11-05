package lindefense.enemy;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.VisualEvent;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;

/**
 * Owns every live enemy. Handles spawning, movement, status upkeep, the
 * special mechanics that need neighbour information (swaps, jumps, shields,
 * buckets), leaks, deaths, rewards and splitting. Additions during iteration go
 * through a pending list so no ConcurrentModificationException can occur.
 *
 * <h3>Precise mechanic rules</h3>
 * <ul>
 *   <li>Bubble Sort: every 3 s, swaps distance with the nearest enemy ahead within 45 px on its route.</li>
 *   <li>Selection Sort: every 2.5 s, if any enemy is ahead within 140 px, jumps 6 px in front of the furthest one.</li>
 *   <li>Insertion Sort: every 2 s, leapfrogs 6 px past the nearest enemy ahead within 70 px.</li>
 *   <li>Shell Sort: every 3 s, jumps forward by its current gap (140, 70, 35, then 18 px forever).</li>
 *   <li>Heap Sort: enemies on its route from 90 px behind it up to its position take 50% damage (not itself).</li>
 *   <li>Bucket Sort: every 1 s stores non-boss enemies of base HP &le; 5 within 30 px (max 6). Stored enemies are
 *       off the track until the bucket dies (released at its position, keeping their HP) or leaks (they leak too).</li>
 *   <li>Disrupted enemies perform none of the above; their timers keep running.</li>
 *   <li>Splitting: children spawn at the parent's distance (staggered 6 px behind each other), on the parent's route,
 *       with the parent's HP/speed scale. Camo and Regrow are inherited; Fortified is inherited only from bosses.</li>
 *   <li>Rewards: each entity pays its own reward exactly once, when its own body is destroyed. Leaks pay nothing.
 *       Rewards are multiplied by {@link lindefense.wave.WaveData#rewardScale(int)}.</li>
 * </ul>
 *
 * <h3>Performance</h3>
 * The live list is an {@link EnemyList} with a spatial {@link EnemyGrid} over it ({@link #getGrid()}), used by every
 * proximity query. The neighbour mechanics above work on per-route lists sorted by distance (rebuilt once per tick
 * into reused arrays); while no mechanic has moved an enemy since that sort, each mechanic looks only at the slice of
 * its route within its reach (binary search) instead of the whole route, visiting the same enemies in the same order.
 */
public class EnemyManager {
    private final Game game;
    private static final Comparator<Enemy> BY_DISTANCE = Comparator.comparingDouble(Enemy::getDistance);
    private static final List<Enemy> NO_ENEMIES = java.util.Collections.emptyList();

    private final EnemyList enemies = new EnemyList();
    private final EnemyGrid grid = new EnemyGrid(enemies);
    private final List<Enemy> pending = new ArrayList<>();
    /** Per-route enemy lists sorted by distance: routeKeys[i] is the route (by identity) of routeLists[i]. */
    private final List<Path> routeKeys = new ArrayList<>(4);
    private final List<ArrayList<Enemy>> routeLists = new ArrayList<>(4);
    /** True while every route list is still sorted by the enemies' current distances (no mechanic moved anyone yet). */
    private boolean routesSorted;
    private final List<Enemy> scratch = new ArrayList<>();
    private int totalKilled;
    private int totalLeaked;
    private int totalSpawned;

    public EnemyManager(Game game) { this.game = game; }

    /** Active (on-track, alive) enemies. Do not modify. */
    public List<Enemy> getEnemies() { return enemies; }
    /** Spatial grid over {@link #getEnemies()} for proximity queries (always current; see {@link EnemyGrid}). */
    public EnemyGrid getGrid() { return grid; }
    public int getTotalKilled() { return totalKilled; }
    public int getTotalLeaked() { return totalLeaked; }
    public int getTotalSpawned() { return totalSpawned; }
    public boolean isEmpty() { return enemies.isEmpty() && pending.isEmpty(); }
    public int getAliveCount() {
        int n = enemies.size() + pending.size();
        for (Enemy e : enemies) n += e.getStoredEnemies().size();
        return n;
    }

    /** Spawns an enemy of the given type at the start of a route (routeIndex &lt; 0 = random). */
    public Enemy spawn(EnemyType type, EnumSet<Modifier> mods, int routeIndex, double distance) {
        return spawnScaled(type, mods, routeIndex, distance, game.getWaveHpScale(type), game.getWaveSpeedScale());   // DIFFICULTY HOOK: type-aware HP
    }

    public Enemy spawnScaled(EnemyType type, EnumSet<Modifier> mods, int routeIndex, double distance,
                             double hpScale, double speedScale) {
        List<Path> routes = game.getMap().getRoutes();
        int idx = routeIndex < 0 || routeIndex >= routes.size() ? game.getMap().pickRoute(game) : routeIndex;
        Path route = routes.get(idx);
        Enemy e = type.isBoss()
            ? new Boss(type, mods, route, idx, distance, hpScale, speedScale)
            : new Enemy(type, mods, route, idx, distance, hpScale, speedScale);
        e.setSpawnTime(game.getTime());
        pending.add(e);
        totalSpawned++;
        return e;
    }

    public void clear() { enemies.clear(); pending.clear(); for (ArrayList<Enemy> l : routeLists) l.clear(); }

    // ------------------------------------------------------------------

    public void update(double dt) {
        flushPending();
        double now = game.getTime();
        // 1. statuses, DOT, regrow, boss logic
        for (int i = 0; i < enemies.size(); i++) {
            Enemy e = enemies.get(i);
            double dot = e.tickStatuses(dt);
            if (dot > 0) {
                double dealt = e.takeDamage(dot, now);
                Object ds = e.getDotSource();
                if (ds instanceof Tower) { e.setLastHitBy(ds); ((Tower) ds).addDamageDealt(dealt); }
            }
            if (e instanceof Boss) ((Boss) e).updateBoss(game, dt);
        }
        // 2. movement + leaks
        for (int i = 0; i < enemies.size(); i++) {
            Enemy e = enemies.get(i);
            if (!e.isAlive()) continue;
            double ext = game.getMap().enemySpeedMultiplier(e) * game.getGlobalEnemySpeedMultiplier();
            boolean reached = e.advance(dt, ext);
            if (reached) {
                leak(e);
            } else {
                game.getMap().onEnemyMoved(game, e);
            }
        }
        // 2b. reversed enemies (Cohere Command Override) damage whatever they touch
        for (int i = 0; i < enemies.size(); i++) {
            Enemy e = enemies.get(i);
            if (e.isAlive() && e.isReversed() && !e.isStored()) reverseContact(e, dt);
        }
        // 3. neighbour-based mechanics
        rebuildRouteIndex();
        for (int i = 0; i < enemies.size(); i++) {
            Enemy e = enemies.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            if (e.getType().mechanic != Mechanic.NONE && e.getType().mechanic != Mechanic.PALANTIR) runMechanic(e, dt);
        }
        // 4. deaths
        for (int i = 0; i < enemies.size(); i++) {
            Enemy e = enemies.get(i);
            if (e.isAlive() && e.getHp() <= 0) kill(e);
        }
        // 5. sweep
        for (int i = enemies.size() - 1; i >= 0; i--) {
            Enemy e = enemies.get(i);
            if (!e.isAlive() || e.isStored()) {
                int last = enemies.size() - 1;
                enemies.set(i, enemies.get(last));
                enemies.remove(last);
            }
        }
        flushPending();
    }

    /** Contact damage of a reversed enemy: its dps (TRUE damage, credited to the override's source) to every other enemy touching it. */
    private void reverseContact(Enemy r, double dt) {
        double dmg = r.getReverseDps() * dt;
        if (dmg <= 0) return;
        Object src = r.getReverseSource();
        List<Enemy> near = grid.near(r.getPosition().x, r.getPosition().y, r.getRadius(), scratch);
        for (int j = 0; j < near.size(); j++) {
            Enemy o = near.get(j);
            if (o == r || !o.isAlive() || o.isStored()) continue;
            if (o.getPosition().distSq(r.getPosition()) > (r.getRadius() + o.getRadius()) * (r.getRadius() + o.getRadius())) continue;
            double dealt = o.takeDamage(dmg, game.getTime());
            if (src instanceof Tower) { o.setLastHitBy(src); ((Tower) src).addDamageDealt(dealt); }
        }
    }

    private void flushPending() {
        if (!pending.isEmpty()) { enemies.addAll(pending); pending.clear(); }
    }

    private void rebuildRouteIndex() {
        for (int i = 0; i < routeLists.size(); i++) routeLists.get(i).clear();
        for (int i = 0, n = enemies.size(); i < n; i++) {
            Enemy e = enemies.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            routeList(e.getRoute(), true).add(e);
        }
        for (int i = 0; i < routeLists.size(); i++) routeLists.get(i).sort(BY_DISTANCE);
        routesSorted = true;
    }

    /** The list for a route (matched by identity, as the HashMap key was); created on demand if {@code create}. */
    private ArrayList<Enemy> routeList(Path route, boolean create) {
        for (int i = 0; i < routeKeys.size(); i++) if (routeKeys.get(i) == route) return routeLists.get(i);
        if (!create) return null;
        ArrayList<Enemy> l = new ArrayList<>();
        routeKeys.add(route);
        routeLists.add(l);
        return l;
    }

    private List<Enemy> routeMates(Enemy e) {
        List<Enemy> l = routeList(e.getRoute(), false);
        return l == null ? NO_ENEMIES : l;
    }

    /**
     * Index of the first route mate a mechanic of {@code e} must look at when its reach behind {@code e} is
     * {@code behind} px: binary search on the distance-sorted route list (with 1 px of slack, the exact test is still
     * applied by the caller), or 0 (scan everything, as before) once any mechanic has moved an enemy this tick.
     */
    private int windowStart(List<Enemy> mates, double fromDistance) {
        if (!routesSorted) return 0;
        int lo = 0, hi = mates.size();
        double key = fromDistance - 1;
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (mates.get(mid).getDistance() < key) lo = mid + 1; else hi = mid;
        }
        return lo;
    }

    /** True if iteration may stop at {@code o}: the list is still sorted and {@code o} is beyond {@code toDistance} (+1 px slack). */
    private boolean pastWindow(Enemy o, double toDistance) {
        return routesSorted && o.getDistance() > toDistance + 1;
    }

    private void runMechanic(Enemy e, double dt) {
        Mechanic m = e.getType().mechanic;
        if (m == Mechanic.HEAP_SHIELD) {
            if (e.isDisrupted()) return;
            List<Enemy> mates = routeMates(e);
            for (int i = windowStart(mates, e.getDistance() - 90); i < mates.size(); i++) {
                Enemy o = mates.get(i);
                if (pastWindow(o, e.getDistance())) break;
                if (o == e) continue;
                double gap = e.getDistance() - o.getDistance();
                if (gap > 0 && gap <= 90) o.setShieldedTick(game.getTick());
            }
            return;
        }
        if (m == Mechanic.ACCELERATE_ON_DAMAGE || m == Mechanic.RADIX_PHASES) return; // handled in Enemy
        e.setMechanicTimer(e.getMechanicTimer() + dt);
        double period = m == Mechanic.BUBBLE_SWAP ? 3.0 : m == Mechanic.SELECTION_FRONT ? 2.5
            : m == Mechanic.INSERTION_LEAPFROG ? 2.0 : m == Mechanic.SHELL_GAP_JUMP ? 3.0 : 1.0;
        if (e.getMechanicTimer() < period) return;
        e.setMechanicTimer(0);
        if (e.isDisrupted() || e.isStunned()) return;
        switch (m) {
            case BUBBLE_SWAP: {
                Enemy ahead = nearestAhead(e, 45);
                if (ahead != null) {
                    routesSorted = false;
                    double d = ahead.getDistance();
                    ahead.setDistance(e.getDistance());
                    e.setDistance(d);
                    game.getEvents().add(VisualEvent.split(e.getPosition(), 14, 0x9be7ff));
                }
                break;
            }
            case SELECTION_FRONT: {
                double best = -1;
                List<Enemy> mates = routeMates(e);
                for (int i = windowStart(mates, e.getDistance()); i < mates.size(); i++) {
                    Enemy o = mates.get(i);
                    if (pastWindow(o, e.getDistance() + 140)) break;
                    double gap = o.getDistance() - e.getDistance();
                    if (o != e && gap > 0 && gap <= 140 && o.getDistance() > best) best = o.getDistance();
                }
                if (best >= 0) { routesSorted = false; e.setDistance(best + 6); game.getEvents().add(VisualEvent.teleport(e.getPosition())); }
                break;
            }
            case INSERTION_LEAPFROG: {
                Enemy ahead = nearestAhead(e, 70);
                if (ahead != null) { routesSorted = false; e.setDistance(ahead.getDistance() + 6); game.getEvents().add(VisualEvent.split(e.getPosition(), 10, 0xffe066)); }
                break;
            }
            case SHELL_GAP_JUMP: {
                double gap = e.currentShellGap();
                Vec from = e.getPosition();
                routesSorted = false;
                e.shiftDistance(gap);
                e.setShellJumpIndex(e.getShellJumpIndex() + 1);
                game.getEvents().add(VisualEvent.chain(from, e.getPosition(), 0xc2b280));
                break;
            }
            case BUCKET_STORE: {
                if (e.getStoredEnemies().size() >= 6) break;
                List<Enemy> mates = routeMates(e);
                for (int i = windowStart(mates, e.getDistance() - 30); i < mates.size(); i++) {
                    Enemy o = mates.get(i);
                    if (pastWindow(o, e.getDistance() + 30)) break;
                    if (o == e || !o.isAlive() || o.isStored() || o.isBoss()) continue;
                    if (o.getType().baseHp > 5 || o.getType().mechanic == Mechanic.BUCKET_STORE) continue;
                    if (Math.abs(o.getDistance() - e.getDistance()) <= 30) {
                        o.setStored(true);
                        e.getStoredEnemies().add(o);
                        game.getEvents().add(VisualEvent.split(o.getPosition(), 12, 0x8ad8ff));
                        if (e.getStoredEnemies().size() >= 6) break;
                    }
                }
                break;
            }
            default: break;
        }
    }

    private Enemy nearestAhead(Enemy e, double maxGap) {
        Enemy best = null;
        double bestGap = maxGap;
        List<Enemy> mates = routeMates(e);
        for (int i = windowStart(mates, e.getDistance()); i < mates.size(); i++) {
            Enemy o = mates.get(i);
            if (pastWindow(o, e.getDistance() + maxGap)) break;
            if (o == e) continue;
            double gap = o.getDistance() - e.getDistance();
            if (gap > 0 && gap <= bestGap) { bestGap = gap; best = o; }
        }
        return best;
    }

    // ------------------------------------------------------------------

    private void leak(Enemy e) {
        if (!e.isAlive()) return;
        int lives = e.getType().lives;
        for (Enemy s : e.getStoredEnemies()) { lives += s.getType().lives; s.markLeaked(); }
        e.markLeaked();
        totalLeaked++;
        game.loseLives(game.getVariance().leakLives(lives), e);   // PATCH NOTES: Constitutional AI
    }

    /** Destroys the enemy's body: pays its reward and releases children / stored enemies. */
    public void kill(Enemy e) { destroy(e, true); }

    /**
     * Instantly destroys an enemy WITHOUT releasing children (DeepSeek Deep Reasoning Strike): the enemy's own
     * reward is paid exactly once, stored bucket contents are released normally, and the kill is credited to
     * {@code credit} (a Tower or null). Does nothing if already dead.
     */
    public void destroyWithoutChildren(Enemy e, Object credit) {
        if (e == null || !e.isAlive()) return;
        if (credit != null) e.setLastHitBy(credit);
        destroy(e, false);
    }

    private void destroy(Enemy e, boolean children) {
        if (!e.isAlive()) return;
        e.markDead();
        totalKilled++;
        Object src = e.getLastHitBy();
        double reward = Math.round(e.getType().reward * game.getRewardScale());
        if (reward > 0) { game.addCash(reward, e.getPosition()); game.addPopValue(reward); }
        game.onEnemyKilled(e);
        if (src instanceof Tower) {
            Tower killer = (Tower) src;
            killer.addKill();
            killer.getBehavior().onKill(game, killer, e);
        }

        EnemyType t = e.getType();
        if (t == EnemyType.PALANTIR) return; // victory sequence; no children
        EnumSet<Modifier> inherited = EnumSet.noneOf(Modifier.class);
        if (e.has(Modifier.CAMO)) inherited.add(Modifier.CAMO);
        if (e.has(Modifier.REGROW)) inherited.add(Modifier.REGROW);
        if (e.has(Modifier.FORTIFIED) && e.isBoss()) inherited.add(Modifier.FORTIFIED);
        int k = 0;
        EnemyType[] ct = t.getChildTypes();
        int[] cc = t.getChildCounts();
        if (children) {
            for (int i = 0; i < ct.length; i++) {
                for (int j = 0; j < cc[i]; j++) {
                    double d = e.getDistance() - 6 * k++;
                    Enemy child = spawnScaled(ct[i], inherited, e.getRouteIndex(), Math.max(0, d), e.getHpScale(), e.getSpeedScale());
                    child.setDrifted(e.hasDrifted());
                }
            }
        }
        if (children && ct.length > 0) game.getEvents().add(VisualEvent.split(e.getPosition(), e.getRadius() * 1.6, 0xffffff));
        else game.getEvents().add(VisualEvent.death(e.getPosition(), e.getRadius(), 0xffffff));
        if (!e.getStoredEnemies().isEmpty()) {
            int i = 0;
            for (Enemy s : e.getStoredEnemies()) {
                s.setStored(false);
                s.teleportTo(e.getRoute(), e.getRouteIndex(), Math.max(0, e.getDistance() - 8 * i++));
                // a carrier stored it this very tick and dies before the sweep removed it: it is still in the list
                if (!enemies.contains(s)) pending.add(s);
            }
            e.getStoredEnemies().clear();
        }
    }

    /** Debug/test helper: counts enemies of a type (active + pending + stored). */
    public int countOfType(EnemyType t) {
        int n = 0;
        for (Enemy e : enemies) { if (e.getType() == t) n++; for (Enemy s : e.getStoredEnemies()) if (s.getType() == t) n++; }
        for (Enemy e : pending) if (e.getType() == t) n++;
        return n;
    }
}
