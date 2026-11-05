package lindefense.combat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyGrid;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * The combat engine: target acquisition (including Densest Cluster), attack execution for every
 * {@link lindefense.tower.AttackKind}, projectile movement/collision and the single damage formula
 * ({@link #applyHit(HitContext)}) used by every hit in the game (towers, abilities, summons and map hazards).
 *
 * <p>Every proximity query (targets in range, enemies on a beam, splash, chain / bounce hops, projectile collisions)
 * asks the {@link EnemyGrid} for the few enemies near the point instead of scanning every enemy, then applies the
 * same exact test as before to those candidates, in the same order, so results are unchanged. Range checks use
 * {@link Vec#withinDist} / {@link Vec#exceedsDist} (exactly {@code dist <= r} / {@code dist > r}, without the slow
 * {@code Math.hypot}) and cheap geometric tests run before the boxed hit-id lookups.</p>
 */
public class Combat {
    /** Maximum visual events kept per tick to keep the renderer responsive. */
    private static final int MAX_EVENTS_PER_TICK = 400;
    /** SONIC knockback on Lead-type enemies (spec 3.0). */
    public static final double SONIC_LEAD_KNOCKBACK = 20;
    /** Ceramic multiplier for BLUNT / KINETIC / SONIC (spec 3.0). */
    public static final double CERAMIC_MULT = 2.0;
    /** Damage multiplier against FROZEN enemies (Claude Time-Lock). */
    public static final double FROZEN_MULT = 2.0;
    /** Damage multiplier against Fortified enemies while ARMOR CRACKED (the HP bonus is ignored: x2 damage). */
    public static final double CRACKED_FORTIFIED_MULT = 2.0;

    private static final Comparator<Enemy> FIRST = Comparator.comparingDouble(Enemy::getRemainingDistance);
    private static final Comparator<Enemy> LAST = FIRST.reversed();
    private static final Comparator<Enemy> STRONGEST = Comparator.comparingDouble(Enemy::getHp).reversed().thenComparingDouble(Enemy::getRemainingDistance);
    private static final Comparator<Enemy> WEAKEST = Comparator.comparingDouble(Enemy::getHp).thenComparingDouble(Enemy::getRemainingDistance);

    private final Game game;
    private final List<Projectile> projectiles = new ArrayList<>();
    private final List<Projectile> newProjectiles = new ArrayList<>();
    /** Grid query buffer; only used in stretches that cannot re-enter (no hits are applied while it is in use). */
    private final List<Enemy> near = new ArrayList<>();

    public Combat(Game game) { this.game = game; }

    public List<Projectile> getProjectiles() { return projectiles; }

    // ------------------------------------------------------------------
    // Target acquisition
    // ------------------------------------------------------------------

    /** Returns up to {@code n} valid targets for the tower, ordered by its priority. */
    public List<Enemy> acquireTargets(Tower t, int n) {
        Comparator<Enemy> priority = t.getBehavior().priorityComparator(t);
        // PALANTIR: its holographic decoys draw fire; towers immune to prompt injection see through them
        Comparator<Enemy> taunt = t.isInjectionImmune() ? null : game.getInjection().tauntComparator();
        if (taunt != null) priority = priority == null ? taunt : taunt.thenComparing(priority);
        return acquireTargetsFrom(t.getPosition(), t.effectiveRange(game), t.canSeeCamo(), t.getStats().ignoresLos,
            t.getTargeting(), n, priority);
    }

    /**
     * General target acquisition from any point (towers, drones). {@code priority} (nullable) is applied before the
     * targeting comparator.
     */
    public List<Enemy> acquireTargetsFrom(Vec origin, double range, boolean detection, boolean ignoreLos,
                                          Targeting targeting, int n, Comparator<Enemy> priority) {
        List<Enemy> candidates = new ArrayList<>();
        List<Enemy> pool = game.getEnemyManager().getGrid().near(origin.x, origin.y, range, near);
        for (int i = 0, n2 = pool.size(); i < n2; i++) {
            Enemy e = pool.get(i);
            if (!e.isTargetableBy(detection)) continue;
            if (origin.exceedsDist(e.getPosition(), range + e.getRadius())) continue;
            if (!ignoreLos && !game.getMap().hasLineOfSight(origin, e.getPosition())) continue;
            candidates.add(e);
        }
        if (candidates.isEmpty()) return candidates;
        Comparator<Enemy> cmp;
        if (targeting == Targeting.DENSEST_CLUSTER) {
            Map<Enemy, Integer> dens = new HashMap<>();
            List<Enemy> pop = game.getEnemyManager().getEnemies();
            for (Enemy e : candidates) dens.put(e, Clusters.density(e, pop));
            cmp = Comparator.comparingInt((Enemy e) -> -dens.get(e)).thenComparingDouble(Enemy::getRemainingDistance);
        } else {
            cmp = comparatorFor(targeting, origin);
        }
        if (priority != null) cmp = priority.thenComparing(cmp);
        if (candidates.size() > 1) candidates.sort(cmp);
        if (candidates.size() > n) candidates.subList(n, candidates.size()).clear();
        return candidates;
    }

    /**
     * The ordering used by each targeting priority. DENSEST_CLUSTER needs the whole population and is handled in
     * {@link #acquireTargetsFrom}; here it falls back to First.
     */
    public static Comparator<Enemy> comparatorFor(Targeting targeting, Vec towerPos) {
        switch (targeting) {
            case LAST: return LAST;
            case STRONGEST: return STRONGEST;
            case WEAKEST: return WEAKEST;
            case CLOSEST: return Comparator.comparingDouble((Enemy e) -> e.getPosition().distSq(towerPos));
            case FIRST:
            case DENSEST_CLUSTER:
            default: return FIRST;
        }
    }

    // ------------------------------------------------------------------
    // Attack execution
    // ------------------------------------------------------------------

    /** Performs one attack for the tower (via its behaviour). Returns true if it attacked. */
    public boolean attack(Tower t) { return t.getBehavior().attack(game, t); }

    /** The data-driven base attack for the tower's {@link lindefense.tower.AttackKind}. */
    public boolean genericAttack(Tower t) {
        TowerStats s = t.getStats();
        switch (s.kind) {
            case PULSE: return pulse(t, s);
            case PROJECTILE: case INSTANT: case CHAIN: break;
            default: return false;
        }
        int want = s.kind == lindefense.tower.AttackKind.INSTANT ? Math.max(s.targets, s.projectilesPerShot) : s.targets;
        List<Enemy> targets = acquireTargets(t, Math.max(1, want));
        if (targets.isEmpty()) return false;
        AttackContext c = newAttackContext(t, targets);
        t.getBehavior().modifyAttack(game, t, c);
        if (c.cancel || c.targets.isEmpty()) return false;
        executeAttack(c, t.getPosition(), t.canSeeCamo(), true);
        t.setLastTarget(c.targets.get(0));
        t.getBehavior().onFire(game, t, c);
        t.onAttacked(game);
        return true;
    }

    /** Builds the attack context for a tower from its current stats, buffs and map multipliers. */
    public AttackContext newAttackContext(Tower t, List<Enemy> targets) {
        TowerStats s = t.getStats();
        AttackContext c = new AttackContext(t, s, targets);
        c.damageMult = t.damageMultiplier(game);
        c.pierce = t.effectivePierce();
        c.bounces = s.bounces;
        c.clones = s.clones;
        c.splash = s.splashRadius;
        c.speed = s.projectileSpeed * t.projectileSpeedMult();
        return c;
    }

    /**
     * Fires an attack described by the context from {@code origin}. Used by towers and by companions/drones,
     * which pass their own stats and origin. {@code buffed} controls whether the owner's flat damage buff applies.
     */
    public void executeAttack(AttackContext c, Vec origin, boolean detection, boolean buffed) {
        switch (c.stats.kind) {
            case PROJECTILE: shoot(c, origin, detection, buffed); break;
            case INSTANT: case CHAIN: beam(c, origin, detection, buffed); break;
            default: break;
        }
    }

    private void shoot(AttackContext c, Vec origin, boolean detection, boolean buffed) {
        int shots = c.shotsPerTarget;
        for (Enemy target : c.targets) {
            for (int i = 0; i < shots; i++) {
                Vec start = origin;
                if (shots > 1) {
                    double ang = (i - (shots - 1) / 2.0) * 0.35;
                    Vec d = target.getPosition().sub(start).normalized();
                    Vec perp = new Vec(-d.y, d.x);
                    start = start.add(perp.scale(ang * 20));
                }
                Projectile.Shot sh = new Projectile.Shot();
                sh.source = c.tower; sh.stats = c.stats; sh.hit = c.hit(); sh.start = start; sh.target = target;
                sh.damageMult = c.damageMult; sh.extraDamage = c.extraDamage; sh.pierce = c.pierce;
                sh.bounces = c.bounces; sh.bounceRange = c.stats.bounceRange; sh.bounceSpeedGain = c.stats.p("bounceSpeedGain", 0);
                sh.clones = c.clones; sh.splash = c.splash; sh.speed = c.speed; sh.detection = detection;
                sh.rgb = c.tower.getType().primaryRgb; sh.tag = c.tag; sh.buffed = buffed; sh.onImpact = c.onImpact;
                newProjectiles.add(new Projectile(sh));
            }
        }
    }

    /** Instant beams (INSTANT) and chains (CHAIN). */
    private void beam(AttackContext c, Vec origin, boolean detection, boolean buffed) {
        TowerStats s = c.stats;
        int rgb = c.tower.getType().primaryRgb;
        boolean chainOnly = s.kind == lindefense.tower.AttackKind.CHAIN;
        // INSTANT: one beam per requested target/shot, cycling over the acquired targets; CHAIN: a single chain
        int beams = chainOnly ? 1 : Math.max(Math.max(s.targets, c.shotsPerTarget), c.targets.size());
        Set<Integer> hitAlready = new HashSet<>();
        for (int b = 0; b < beams; b++) {
            Enemy target = c.targets.get(b % c.targets.size());
            if (!target.isAlive()) continue;
            Enemy last = target;
            if (!chainOnly && c.pierce > 1) {
                Vec dir = target.getPosition().sub(origin).normalized();
                double range = s.hasUnlimitedRange() ? TowerStats.UNLIMITED_RANGE : c.tower.effectiveRange(game);
                Vec end = origin.add(dir.scale(range));
                List<Enemy> onLine = new ArrayList<>();
                List<Enemy> pool = game.getEnemyManager().getGrid().box(Math.min(origin.x, end.x) - 4, Math.min(origin.y, end.y) - 4,
                    Math.max(origin.x, end.x) + 4, Math.max(origin.y, end.y) + 4, near);
                for (int i = 0, n = pool.size(); i < n; i++) {
                    Enemy e = pool.get(i);
                    if (!e.isTargetableBy(detection)) continue;
                    if (Path.pointSegmentDistance(e.getPosition(), origin, end) <= e.getRadius() + 4) onLine.add(e);
                }
                onLine.sort(Comparator.comparingDouble(e -> e.getPosition().distSq(origin)));
                int hits = 0;
                for (Enemy e : onLine) {
                    if (hits++ >= c.pierce) break;
                    beamHit(c, e, buffed, detection);
                    hitAlready.add(e.getId());
                }
                emit(VisualEvent.beam(origin, end, rgb));
            } else {
                beamHit(c, target, buffed, detection);
                hitAlready.add(target.getId());
                emit(chainOnly ? VisualEvent.chain(origin, target.getPosition(), rgb) : VisualEvent.beam(origin, target.getPosition(), rgb));
            }
            if (s.chainHops > 0) {
                Enemy cur = last;
                for (int hop = 0; hop < s.chainHops; hop++) {
                    Enemy next = nearestEnemy(cur.getPosition(), s.chainRange, hitAlready, detection);
                    if (next == null) break;
                    emit(VisualEvent.chain(cur.getPosition(), next.getPosition(), c.tower.getType().secondaryRgb));
                    beamHit(c, next, buffed, detection);
                    hitAlready.add(next.getId());
                    cur = next;
                }
            }
        }
    }

    private void beamHit(AttackContext c, Enemy e, boolean buffed, boolean detection) {
        HitContext h = new HitContext(e, c.hit(), c.tower);
        h.mult = c.damageMult; h.extra = c.extraDamage; h.fromAttack = buffed; h.detection = detection; h.tag = c.tag;
        applyHit(h);
    }

    private boolean pulse(Tower t, TowerStats s) {
        double range = t.effectiveRange(game);
        Vec tp = t.getPosition();
        List<Enemy> inRange = new ArrayList<>();
        List<Enemy> pool = game.getEnemyManager().getGrid().near(tp.x, tp.y, range, near);
        for (int i = 0, n = pool.size(); i < n; i++) {
            Enemy e = pool.get(i);
            if (!e.isTargetableBy(t.canSeeCamo())) continue;
            if (tp.withinDist(e.getPosition(), range + e.getRadius())) inRange.add(e);
        }
        if (inRange.isEmpty()) return false;
        inRange.sort(comparatorFor(t.getTargeting(), tp));
        AttackContext c = newAttackContext(t, inRange);
        t.getBehavior().modifyAttack(game, t, c);
        if (c.cancel) return false;
        int n = 0;
        for (Enemy e : c.targets) {
            if (n++ >= c.pierce) break;
            beamHit(c, e, true, t.canSeeCamo());
        }
        emit(VisualEvent.ability(tp, range, t.getType().primaryRgb));
        t.setLastTarget(c.targets.get(0));
        t.getBehavior().onFire(game, t, c);
        t.onAttacked(game);
        return true;
    }

    /** Nearest targetable enemy to a point within radius, excluding ids. */
    public Enemy nearestEnemy(Vec p, double radius, Set<Integer> exclude, boolean seesCamo) {
        Enemy best = null;
        double bestD = radius * radius;
        List<Enemy> pool = game.getEnemyManager().getGrid().near(p.x, p.y, radius, near);
        for (int i = 0, n = pool.size(); i < n; i++) {
            Enemy e = pool.get(i);
            double d = e.getPosition().distSq(p);
            if (!(d <= bestD)) continue;
            if (!e.isTargetableBy(seesCamo)) continue;
            if (exclude != null && exclude.contains(e.getId())) continue;
            bestD = d; best = e;
        }
        return best;
    }

    // ------------------------------------------------------------------
    // Projectiles
    // ------------------------------------------------------------------

    public void addProjectile(Projectile p) { newProjectiles.add(p); }

    /** Fires a projectile described by a {@link Projectile.Shot}. */
    public Projectile fire(Projectile.Shot shot) {
        Projectile p = new Projectile(shot);
        newProjectiles.add(p);
        return p;
    }

    public void updateProjectiles(double dt) {
        if (!newProjectiles.isEmpty()) { projectiles.addAll(newProjectiles); newProjectiles.clear(); }
        EnemyGrid grid = game.getEnemyManager().getGrid();
        for (int i = 0; i < projectiles.size(); i++) {
            Projectile p = projectiles.get(i);
            if (!p.move(dt)) continue;
            boolean sees = p.hasDetection();
            // a hit can knock enemies around (splash knockback, behaviours), so iterate with a self-refreshing scan
            EnemyGrid.Scan scan = grid.scan(p.getPosition().x, p.getPosition().y, p.getSize());
            try {
                for (Enemy e = scan.next(); e != null && p.isAlive(); e = scan.next()) {
                    double r = e.getRadius() + p.getSize();
                    if (!(e.getPosition().distSq(p.getPosition()) <= r * r)) continue;
                    if (!e.isTargetableBy(sees) || p.getHitIds().contains(e.getId())) continue;
                    onProjectileHit(p, e);
                }
            } finally {
                scan.close();
            }
        }
        for (int i = projectiles.size() - 1; i >= 0; i--) {
            if (!projectiles.get(i).isAlive()) {
                int last = projectiles.size() - 1;
                projectiles.set(i, projectiles.get(last));
                projectiles.remove(last);
            }
        }
        if (!newProjectiles.isEmpty()) { projectiles.addAll(newProjectiles); newProjectiles.clear(); }
    }

    private void onProjectileHit(Projectile p, Enemy e) {
        Projectile.Shot sh = p.getShot();
        Tower t = sh.source;
        p.getHitIds().add(e.getId());
        if (sh.onImpact != null) { sh.onImpact.impact(game, p, e); return; }
        if (sh.splash > 0) {
            int cap = sh.pierce > 1 ? sh.pierce : 999;
            areaHit(p.getPosition(), sh.splash, sh.hit, t, sh.damageMult, sh.extraDamage, cap, null, sh.detection, sh.buffed, p);
            emit(VisualEvent.explosion(p.getPosition(), sh.splash, t.getType().primaryRgb));
            p.kill();
            return;
        }
        HitContext h = new HitContext(e, sh.hit, t);
        h.mult = sh.damageMult; h.extra = sh.extraDamage; h.fromAttack = sh.buffed; h.detection = sh.detection;
        h.projectile = p; h.tag = sh.tag;
        applyHit(h);
        emit(VisualEvent.hit(e.getPosition(), t.getType().primaryRgb));
        if (p.canClone()) {
            p.consumeClone();
            Set<Integer> exclude = new HashSet<>(p.getHitIds());
            for (int c = 1; c < sh.clones; c++) {
                Enemy nt = nearestEnemy(e.getPosition(), sh.bounceRange, exclude, sh.detection);
                if (nt == null) break;
                exclude.add(nt.getId());
                Projectile.Shot cs = copyShot(sh);
                cs.start = e.getPosition(); cs.target = nt; cs.clones = 0; cs.rgb = t.getType().secondaryRgb;
                Projectile clone = new Projectile(cs);
                clone.getHitIds().add(e.getId());
                newProjectiles.add(clone);
            }
        }
        if (p.getBouncesLeft() > 0) {
            Enemy next = nearestEnemy(e.getPosition(), sh.bounceRange, p.getHitIds(), sh.detection);
            if (next != null) { p.consumeBounce(); p.retarget(next); return; }
        }
        if (p.consumePierce()) p.kill();
    }

    private static Projectile.Shot copyShot(Projectile.Shot o) {
        Projectile.Shot s = new Projectile.Shot();
        s.source = o.source; s.stats = o.stats; s.hit = o.hit; s.start = o.start; s.target = o.target;
        s.damageMult = o.damageMult; s.extraDamage = o.extraDamage; s.pierce = o.pierce; s.bounces = o.bounces;
        s.bounceRange = o.bounceRange; s.bounceSpeedGain = o.bounceSpeedGain; s.clones = o.clones; s.splash = o.splash;
        s.speed = o.speed; s.detection = o.detection; s.rgb = o.rgb; s.tag = o.tag; s.buffed = o.buffed; s.onImpact = o.onImpact;
        return s;
    }

    /**
     * Applies a projectile's direct hit to one enemy, as the generic code does, with an extra damage scale (bounce
     * falloff). Returns the applied context ({@code dealt}, {@code immune}). Used by custom impact handlers.
     */
    public HitContext projectileHit(Projectile p, Enemy e, double scale) {
        Projectile.Shot sh = p.getShot();
        HitContext h = new HitContext(e, sh.hit, sh.source);
        h.mult = sh.damageMult * scale; h.extra = sh.extraDamage; h.fromAttack = sh.buffed; h.detection = sh.detection;
        h.projectile = p; h.tag = sh.tag;
        applyHit(h);
        emit(VisualEvent.hit(e.getPosition(), sh.rgb));
        return h;
    }

    /**
     * Hits every enemy within {@code radius} of {@code center} (nearest first) that is not in {@code exclude}, and
     * returns the applied contexts. When {@code record} is non-null every enemy touched is added to it, which is how
     * custom projectiles guarantee that one projectile never damages the same enemy twice.
     */
    public List<HitContext> areaHits(Vec center, double radius, HitSpec hit, Tower source, double mult, double extra,
                                     Set<Integer> exclude, Set<Integer> record, boolean detection, boolean fromAttack, Projectile via) {
        List<Enemy> inRange = new ArrayList<>();
        List<Enemy> pool = game.getEnemyManager().getGrid().near(center.x, center.y, radius, near);
        for (int i = 0, n = pool.size(); i < n; i++) {
            Enemy e = pool.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            if (!e.getPosition().withinDist(center, radius + e.getRadius())) continue;
            if (exclude != null && exclude.contains(e.getId())) continue;
            inRange.add(e);
        }
        inRange.sort(Comparator.comparingDouble(e -> e.getPosition().distSq(center)));
        List<HitContext> out = new ArrayList<>(inRange.size());
        for (Enemy e : inRange) {
            if (record != null) record.add(e.getId());
            HitContext h = new HitContext(e, hit, source);
            h.mult = mult; h.extra = extra; h.fromAttack = fromAttack; h.detection = detection; h.projectile = via;
            applyHit(h);
            out.add(h);
        }
        return out;
    }

    // ------------------------------------------------------------------
    // Area hits
    // ------------------------------------------------------------------

    /**
     * Hits every enemy within radius (up to maxTargets, nearest first) with an ability-style hit (no attack buffs).
     * Detection for the EXPLOSIVE-vs-camo rule is the source tower's detection (true when source is null).
     */
    public int areaHit(Vec center, double radius, HitSpec hit, Tower source, double mult, int maxTargets, Set<Integer> exclude) {
        return areaHit(center, radius, hit, source, mult, 0, maxTargets, exclude, source == null || source.canSeeCamo(), false, null);
    }

    /** Full-control area hit; see {@link #areaHit(Vec, double, HitSpec, Tower, double, int, Set)}. */
    public int areaHit(Vec center, double radius, HitSpec hit, Tower source, double mult, double extra, int maxTargets,
                       Set<Integer> exclude, boolean detection, boolean fromAttack, Projectile via) {
        List<Enemy> inRange = new ArrayList<>();
        List<Enemy> pool = game.getEnemyManager().getGrid().near(center.x, center.y, radius, near);
        for (int i = 0, n = pool.size(); i < n; i++) {
            Enemy e = pool.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            if (!e.getPosition().withinDist(center, radius + e.getRadius())) continue;
            if (exclude != null && exclude.contains(e.getId())) continue;
            inRange.add(e);
        }
        inRange.sort(Comparator.comparingDouble(e -> e.getPosition().distSq(center)));
        int n = 0;
        for (Enemy e : inRange) {
            if (n >= maxTargets) break;
            HitContext h = new HitContext(e, hit, source);
            h.mult = mult; h.extra = extra; h.fromAttack = fromAttack; h.detection = detection; h.projectile = via;
            applyHit(h);
            if (!h.immune) n++;
        }
        return n;
    }

    // ------------------------------------------------------------------
    // The damage formula
    // ------------------------------------------------------------------

    /**
     * Legacy entry: applies a hit and returns the HP actually removed. Ability-style (no attack buffs);
     * detection comes from the source tower.
     */
    public double applyHit(Enemy e, HitSpec hit, Tower source, double mult, double extra) {
        HitContext h = new HitContext(e, hit, source);
        h.mult = mult; h.extra = extra;
        return applyHit(h);
    }

    /**
     * Applies a hit and returns the HP actually removed.
     *
     * <pre>
     * base   = hit.damage + extra [+ buffed flat damage if fromAttack] + flat bonuses (boss/Fortified/Lead/Ceramic)
     * raw    = base * mult * (1 + legacy % bonuses) * type & situation multipliers:
     *            BLUNT/KINETIC/SONIC x2 vs Ceramic; hit.multVs* ; x(1+buff) vs MOAB-class ;
     *            x2 vs FROZEN ; x2 vs Fortified while ARMOR CRACKED
     * immune : SHARP vs Lead (unless cracked / hit.ignoresResistance); EXPLOSIVE vs Camo without detection
     * dmg    = raw * (1 - armour * (1 - armorPierce))        (TRUE skips this)
     * dmg   *= 0.5 BFB weak-hit rule, 0.5 Heap shield          (weak-hit skipped for TRUE)
     * dmg    = dmg * (1 + percent mark) + flat mark           (TRUE skips marks)
     * dmg   += min(pctCap, pctMaxHp * maxHp)
     * dmg    = dmg * finalMult + finalFlat
     * </pre>
     * Control effects (slow, stun, knockback, armour crack, marks, burn, disrupt, strips) are then applied unless the
     * hit was blocked by an immunity. Tower behaviours get {@code beforeHit} (before the maths) and {@code onHit}.
     */
    public double applyHit(HitContext c) {
        Enemy e = c.target;
        if (e == null || !e.isAlive() || e.isStored()) return 0;
        Tower src = c.source;
        if (src != null) src.getBehavior().beforeHit(game, src, c);
        HitSpec h = c.hit();
        DamageType type = h.type;
        boolean isTrue = type == DamageType.TRUE;

        // ---- immunities ----
        boolean cracked = e.isArmorCracked();
        boolean immune = false;
        if (!isTrue) {
            if (type == DamageType.SHARP && e.isLeadType() && !cracked && !h.ignoresResistance) immune = true;
            if (type == DamageType.EXPLOSIVE && e.isCamo() && !c.detection && !e.isRevealed()) immune = true;
        }
        c.immune = immune;

        double dmg = 0;
        if (!immune) {
            double base = h.damage + c.extra;
            if (c.fromAttack && src != null) base += src.flatDamageBuff();
            if (e.isBoss()) base += h.flatVsBoss;
            if (e.isFortified()) base += h.flatVsFortified;
            if (e.isLeadType()) base += h.flatVsLead;
            if (e.isCeramicType()) base += h.flatVsCeramic;
            double bonus = 1.0;
            if (e.isBoss()) bonus += h.bonusVsBoss;
            if (e.isFortified()) bonus += h.bonusVsFortified; else bonus += h.bonusVsNonFortified;
            if (e.getType().isComplex()) bonus += h.bonusVsComplex;
            if (e.getType().isFast()) bonus += h.bonusVsFast;
            if (e.getType().hasChildren()) bonus += h.bonusVsSplitters;
            double m = Math.max(0.1, bonus);
            if (!isTrue) {
                if (e.isCeramicType() && (type.isBluntLike() || type == DamageType.SONIC)) m *= CERAMIC_MULT;
                if (e.isCeramicType()) m *= h.multVsCeramic;
                if (e.isLeadType()) m *= h.multVsLead;
                if (e.isFortified()) { m *= h.multVsFortified; if (cracked) m *= CRACKED_FORTIFIED_MULT; }
                if (e.isBoss()) {
                    m *= h.multVsBoss;
                    if (src != null) m *= 1 + src.bossDamageBuff();
                }
                if (e.getType().isSortingAlgorithm() || e.getType().isLinkedList()) m *= h.multVsSortingAndLists;
                if (e.getType().baseHp >= 5) m *= h.multVsHighHp;
                if (e.isFrozen()) m *= FROZEN_MULT;
            }
            dmg = base * c.mult * m;
            if (!isTrue) {
                double armor = e.effectiveArmor() * (1 - h.armorPierce);
                dmg *= (1 - Math.max(0, Math.min(0.95, armor)));
                int weak = e.getType().getWeakHitThreshold();
                if (weak > 0 && h.damage < weak) dmg *= 0.5;
            }
            if (e.isShielded(game.getTick())) dmg *= 0.5;
            if (!isTrue) {
                dmg *= 1 + e.getMarkedBonus();
                if (dmg > 0) dmg += e.getMarkedFlat();
            }
            if (h.pctMaxHp > 0) dmg += Math.min(h.pctCap, h.pctMaxHp * e.getMaxHp());
            dmg = dmg * c.finalMult + c.finalFlat;
            dmg *= game.getVariance().damageAgainst(e);   // PATCH NOTES / BREAKING NEWS damage hook (1 when off)
        }

        double dealt = 0;
        if (!immune && dmg > 0) {
            dealt = e.takeDamage(dmg, game.getTime());
            if (src != null) { e.setLastHitBy(src); src.addDamageDealt(dealt); }
        } else if (immune && src != null && game.getRng().chance(0.05)) {
            emit(VisualEvent.text(e.getPosition(), "Immune", 0xaaaaaa));
        }
        c.dealt = dealt;

        if (!immune) applyEffects(c, e, h, type);
        if (src != null) src.getBehavior().onHit(game, src, c);
        return dealt;
    }

    /** Control effects of a hit (spec 3.0 status rules live in {@code Enemy.applyStatus}). */
    private void applyEffects(HitContext c, Enemy e, HitSpec h, DamageType type) {
        Tower src = c.source;
        if (h.slowFraction > 0) e.applyStatus(StatusEffect.Kind.SLOW, h.slowFraction, h.slowDuration);
        double stun = e.isBoss() ? h.bossStunDuration : h.stunDuration;
        if (stun > 0) e.applyStatus(StatusEffect.Kind.STUN, 1, stun, true);
        double kb = e.isBoss() ? h.bossKnockback : h.knockback;
        if (!e.isBoss()) {
            if (h.knockbackVsFast > 0 && e.isFastForKnockback()) kb += h.knockbackVsFast;
            if (e.isLeadType()) {
                kb += h.knockbackVsLead;
                if (type == DamageType.SONIC) kb += SONIC_LEAD_KNOCKBACK;
            }
        }
        if (kb > 0) {
            if (h.uncappedKnockback) e.applyKnockbackUncapped(kb); else e.applyKnockback(kb, game.getTime());
        }
        if (h.armorBreak > 0 && h.armorBreakDuration > 0) e.applyStatus(StatusEffect.Kind.ARMOR_CRACK, 1, h.armorBreakDuration);
        if (h.markBonus > 0) e.applyStatus(StatusEffect.Kind.MARKED, h.markBonus, h.markDuration);
        if (h.markFlat > 0) e.applyStatus(StatusEffect.Kind.MARKED_FLAT, h.markFlat, h.markDuration);
        if (h.disruptDuration > 0) e.applyStatus(StatusEffect.Kind.DISRUPTED, 1, h.disruptDuration);
        if (h.dotDps > 0) e.applyBurn(h.dotDps, h.dotDuration, src);
        if (h.stripsFortified && !e.isBoss() && e.isFortified()) {
            e.stripFortified();
            emit(VisualEvent.text(e.getPosition(), "Stripped!", 0xd9c6ff));
        }
        if (h.stripsCamoRegrow && e.stripCamoRegrow()) emit(VisualEvent.text(e.getPosition(), "Revealed", 0xb9a8ff));
    }

    /** True damage from map hazards (short circuits, heat). */
    public double applyMapDamage(Enemy e, double amount) {
        if (e == null || !e.isAlive() || e.isStored()) return 0;
        double dealt = e.takeDamage(amount, game.getTime());
        e.setLastHitBy(null);
        emit(VisualEvent.hit(e.getPosition(), 0xffffff));
        return dealt;
    }

    /** Emits a visual event (throttled per tick). */
    public void emit(VisualEvent ev) {
        if (game.getEvents().size() < MAX_EVENTS_PER_TICK) game.getEvents().add(ev);
    }

    public void clear() { projectiles.clear(); newProjectiles.clear(); }
}
