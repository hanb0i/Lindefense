package lindefense.tower;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.behavior.Behaviors;
import lindefense.tower.behavior.TowerBehavior;

/**
 * A placed tower. Holds position, progression tier, targeting choice, the buff book (aura-granted and timed
 * buffs obeying the spec's stacking rules), ability cooldown and per-tower memory (named counters, the
 * consecutive-hit streak and free-form state for its behaviour). Attack execution is delegated to
 * {@link lindefense.combat.Combat}; special mechanics live in the tower's {@link TowerBehavior}.
 */
public class Tower {
    private static int nextId = 1;
    private static final int STAT_COUNT = BuffStat.values().length;
    private static final int TYPE_COUNT = TowerType.values().length;

    /** A timed buff granted by an ability. */
    private static final class TimedBuff {
        final BuffStat stat; final TowerType source; final double value; double remaining;
        TimedBuff(BuffStat stat, TowerType source, double value, double remaining) {
            this.stat = stat; this.source = source; this.value = value; this.remaining = remaining;
        }
    }

    /** A timed multiplier a tower applies to ITSELF (Caffeine Rush, Scale Factor Overclock). Not capped. */
    private static final class SelfBuff {
        final String key; final double rateMult, projectileSpeedMult; double remaining;
        SelfBuff(String key, double r, double p, double t) { this.key = key; rateMult = r; projectileSpeedMult = p; remaining = t; }
    }

    /** A timed multiplicative buff from a map event (Silicon Circuit pads / short-circuits). Outside the tower-buff caps. */
    private static final class MapBuff {
        final double rateMult, dmgMult, rangeMult; double remaining;
        MapBuff(double r, double d, double g, double t) { rateMult = r; dmgMult = d; rangeMult = g; remaining = t; }
    }

    private final int id;
    private final TowerDef def;
    private final Vec position;
    private int tier;
    private TowerStats stats;
    private Targeting targeting = Targeting.FIRST;
    private boolean alive = true;
    private final boolean temporary;
    private double lifetime;
    private final Tower owner;
    private final TowerBehavior behavior;

    private double attackCooldown;
    private double abilityCooldown;
    /** True once the player has bought this tower's ability ({@link TowerCatalog#ABILITY_UNLOCK_COST}). */
    private boolean abilityUnlocked;
    private double surveilledRemaining;

    // buff book
    private final double[][] auraBuffs = new double[STAT_COUNT][TYPE_COUNT];
    private final List<TimedBuff> timedBuffs = new ArrayList<>();
    private final List<SelfBuff> selfBuffs = new ArrayList<>();
    private final List<MapBuff> mapBuffs = new ArrayList<>();
    private boolean grantedDetection, surveillanceImmune;

    // per-tower memory
    private final Map<String, Double> counters = new HashMap<>();
    private final Map<String, Object> state = new HashMap<>();
    private int streakTargetId = -1;
    private int streakCount;

    // bookkeeping
    private double damageDealt;
    private int kills;
    private Enemy lastTarget;
    private double lastFireTime = -10;

    public Tower(TowerDef def, Vec position, int tier, boolean temporary, double lifetime, Tower owner) {
        this.id = nextId++;
        this.def = def;
        this.position = position;
        this.tier = tier;
        this.stats = def.statsForTier(tier);
        this.temporary = temporary;
        this.lifetime = lifetime;
        this.owner = owner;
        this.behavior = Behaviors.of(def.type);
        this.targeting = def.defaultTargeting;
        // Abilities that need no unlock (Zethos) are usable from placement and start at 50% cooldown (spec 3.0).
        // Shop-tower abilities stay locked until bought at max tier; buying one makes it ready at once.
        boolean usable = def.ability != null && !TowerCatalog.abilityNeedsUnlock(def.type);
        this.abilityCooldown = usable ? def.ability.cooldown * 0.5 : 0;
    }

    public Tower(TowerDef def, Vec position) { this(def, position, 0, false, 0, null); }

    // ---------------- identity ----------------
    public int getId() { return id; }
    public TowerDef getDef() { return def; }
    public TowerType getType() { return def.type; }
    public Vec getPosition() { return position; }
    public int getTier() { return tier; }
    public int getMaxTier() { return def.upgrades.length; }
    /** True when every upgrade is bought (heroes, which have none, always are). */
    public boolean isSuperclass() { return tier >= def.upgrades.length; }
    public boolean isMaxed() { return tier >= def.upgrades.length; }
    public TowerStats getStats() { return stats; }
    public TowerBehavior getBehavior() { return behavior; }
    public Targeting getTargeting() { return targeting; }
    /** Sets the targeting mode; DENSEST_CLUSTER is ignored unless the tower's behaviour allows it. */
    public void setTargeting(Targeting t) {
        if (t == Targeting.DENSEST_CLUSTER && !canUseDensestCluster()) return;
        targeting = t;
    }
    /** True if this tower may select Densest Cluster targeting (Grok U2+). */
    public boolean canUseDensestCluster() { return behavior.allowsDensestCluster(this); }
    /** Steps through the targeting modes this tower may use (First, Last, Strongest, Weakest, Closest, [Densest]). */
    public void cycleTargeting(int dir) {
        Targeting[] all = Targeting.values();
        Targeting t = targeting;
        for (int i = 0; i < all.length; i++) {
            t = all[(t.ordinal() + (dir >= 0 ? 1 : all.length - 1)) % all.length];
            if (t != Targeting.DENSEST_CLUSTER || canUseDensestCluster()) { targeting = t; return; }
        }
    }
    public boolean isAlive() { return alive; }
    public void markRemoved() { alive = false; }
    public boolean isTemporary() { return temporary; }
    public double getLifetime() { return lifetime; }
    public Tower getOwner() { return owner; }
    public String getTierLabel() { return def.tierLabels[Math.min(tier, def.tierLabels.length - 1)]; }
    public double getRadius() { return def.radius; }
    public double getDamageDealt() { return damageDealt; }
    public int getKills() { return kills; }
    public void addDamageDealt(double d) { damageDealt += d; }
    public void addKill() { kills++; }
    public Enemy getLastTarget() { return lastTarget; }
    public void setLastTarget(Enemy e) { lastTarget = e; }
    public double getLastFireTime() { return lastFireTime; }
    public void setLastFireTime(double t) { lastFireTime = t; }

    // ---------------- economy ----------------
    /** Total cash spent on this tower (base + purchased upgrades). */
    public int getInvestedCost() { return def.totalCostForTier(tier) + (abilityUnlocked ? TowerCatalog.ABILITY_UNLOCK_COST : 0); }
    public boolean canUpgrade() { return tier < def.upgrades.length; }
    public UpgradeDef nextUpgrade() { return canUpgrade() ? def.upgrades[tier] : null; }

    /** Applies the next upgrade (cash handling is done by the Shop / TowerManager). */
    public void applyUpgrade(Game game) {
        if (!canUpgrade()) return;
        tier++;
        stats = def.statsForTier(tier);
        behavior.onUpgraded(game, this);
    }

    // ---------------- buff book ----------------
    /**
     * Aura-style buff from a source tower type; recomputed from scratch every aura refresh. The highest value
     * from the same source type wins (no stacking); different types add, up to the stat's cap.
     */
    public void addAuraBuff(BuffStat stat, TowerType source, double value) {
        double[] row = auraBuffs[stat.ordinal()];
        if (value > row[source.ordinal()]) row[source.ordinal()] = value;
    }

    /** Timed buff from an ability. Same (stat, source, value) refreshes its duration. */
    public void addTimedBuff(BuffStat stat, TowerType source, double value, double duration) {
        for (TimedBuff b : timedBuffs) {
            if (b.stat == stat && b.source == source && b.value == value) { b.remaining = Math.max(b.remaining, duration); return; }
        }
        timedBuffs.add(new TimedBuff(stat, source, value, duration));
    }

    /**
     * Total buff for a stat (before the cap): the sum over source types of the highest value that type
     * contributes through auras or timed buffs.
     */
    public double buffTotalUncapped(BuffStat stat) {
        double[] row = auraBuffs[stat.ordinal()];
        double sum = 0;
        for (int ti = 0; ti < TYPE_COUNT; ti++) {
            double best = row[ti];
            for (int k = 0, n = timedBuffs.size(); k < n; k++) {   // index loops: these run for every attack, no iterators
                TimedBuff b = timedBuffs.get(k);
                if (b.stat == stat && b.source.ordinal() == ti && b.value > best) best = b.value;
            }
            sum += best;
        }
        return sum;
    }

    /** Total buff for a stat after the spec's caps (+100% attack speed, +5 flat damage). */
    public double buffTotal(BuffStat stat) { return Math.min(stat.cap, buffTotalUncapped(stat)); }

    /** Map-event buff (attack-rate / damage / range multipliers for a duration). Not part of the tower-buff caps. */
    public void addBuff(double rateMult, double dmgMult, double rangeMult, double duration) {
        mapBuffs.add(new MapBuff(rateMult, dmgMult, rangeMult, duration));
    }
    private double mapRate() { double m = 1; for (int i = 0, n = mapBuffs.size(); i < n; i++) m *= mapBuffs.get(i).rateMult; return m; }
    private double mapDamage() { double m = 1; for (int i = 0, n = mapBuffs.size(); i < n; i++) m *= mapBuffs.get(i).dmgMult; return m; }
    private double mapRange() { double m = 1; for (int i = 0, n = mapBuffs.size(); i < n; i++) m *= mapBuffs.get(i).rangeMult; return m; }

    /** Self-applied timed multiplier (ability). Re-adding the same key refreshes it. */
    public void addSelfBuff(String key, double rateMult, double projectileSpeedMult, double duration) {
        selfBuffs.removeIf(b -> b.key.equals(key));
        selfBuffs.add(new SelfBuff(key, rateMult, projectileSpeedMult, duration));
    }
    public boolean hasSelfBuff(String key) {
        for (int i = 0, n = selfBuffs.size(); i < n; i++) if (selfBuffs.get(i).key.equals(key)) return true;
        return false;
    }
    /** Seconds left on a self buff (0 if not active). */
    public double selfBuffRemaining(String key) {
        for (int i = 0, n = selfBuffs.size(); i < n; i++) if (selfBuffs.get(i).key.equals(key)) return selfBuffs.get(i).remaining;
        return 0;
    }
    /** Seconds left on the longest timed buff granted by a source tower type (0 if none). */
    public double timedBuffRemaining(TowerType source) {
        double best = 0;
        for (int i = 0, n = timedBuffs.size(); i < n; i++) if (timedBuffs.get(i).source == source) best = Math.max(best, timedBuffs.get(i).remaining);
        return best;
    }
    /** Product of self rate multipliers (Caffeine Rush x2, Overclock x3). */
    public double selfRateMult() { double m = 1; for (int i = 0, n = selfBuffs.size(); i < n; i++) m *= selfBuffs.get(i).rateMult; return m; }
    public double projectileSpeedMult() { double m = 1; for (int i = 0, n = selfBuffs.size(); i < n; i++) m *= selfBuffs.get(i).projectileSpeedMult; return m; }

    /** Effective pierce: base pierce plus buffed pierce (flat + percent of base), buff part capped at +10. */
    public int effectivePierce() {
        double flat = buffTotalUncapped(BuffStat.PIERCE_FLAT);
        double pct = buffTotalUncapped(BuffStat.PIERCE_PCT);
        double add = Math.min(BuffStat.PIERCE_FLAT.cap, flat + Math.round(stats.pierce * pct));
        return stats.pierce + (int) add;
    }
    /** Flat damage added to every attack by buffs (cap +5). */
    public double flatDamageBuff() { return buffTotal(BuffStat.DAMAGE_FLAT); }
    /** Extra damage fraction vs MOAB-class from buffs. */
    public double bossDamageBuff() { return buffTotal(BuffStat.BOSS_DAMAGE_PCT); }

    public void resetAuraBonuses() {
        for (double[] row : auraBuffs) Arrays.fill(row, 0);
        grantedDetection = false; surveillanceImmune = false;
    }
    public void grantDetection() { grantedDetection = true; }
    public void grantSurveillanceImmunity() { surveillanceImmune = true; }
    public boolean isSurveillanceImmune() { return surveillanceImmune || stats.auraSurveillanceImmunity; }
    /**
     * Camo detection: built-in (stats.seesCamo -- Student+AI, Grok, Perplexity, Gemini U2, Llama U2), granted by a
     * Perplexity aura, or granted map-wide while a Perplexity U1+ exists.
     */
    public boolean canSeeCamo() { return stats.seesCamo || grantedDetection; }
    /**
     * Total attack-rate multiplier on top of the base stats (buffs, self buffs, map, global, surveillance): what
     * {@link #effectiveRate} applies to {@code stats.rate}. Drones that inherit their owner's speed use it.
     */
    public double rateMultiplier(Game game) { return stats.rate <= 0 ? 1 : effectiveRate(game) / stats.rate; }
    /** Attack-speed fraction from buffs (capped at +100%). */
    public double getAuraRateBonus() { return buffTotal(BuffStat.RATE); }
    /** Flat damage from buffs (capped at +5). */
    public double getAuraDamageBonus() { return flatDamageBuff(); }

    public void setSurveilled(double duration) { surveilledRemaining = Math.max(surveilledRemaining, duration); }
    public void clearSurveilled() { surveilledRemaining = 0; }
    public boolean isSurveilled() { return surveilledRemaining > 0; }
    public double getSurveilledRemaining() { return surveilledRemaining; }

    // ---------------- ability ----------------
    /**
     * The ability this tower can use right now, or null. A shop tower's ability is null until it is unlocked
     * ({@link #unlockAbility}), so every ability UI and rule treats a locked ability as absent; use
     * {@link #getAbilityDef()} to show what an unlock would give.
     */
    public AbilityDef getAbility() { return isAbilityLocked() ? null : def.ability; }
    /** The tower's ability definition whether or not it is unlocked (null if it has none). */
    public AbilityDef getAbilityDef() { return def.ability; }
    /** True while this tower has an ability that still has to be bought. */
    public boolean isAbilityLocked() { return def.ability != null && TowerCatalog.abilityNeedsUnlock(def.type) && !abilityUnlocked; }
    /** True if the ability can be bought now: it is locked and every upgrade is owned (cash is checked by the buyer). */
    public boolean canUnlockAbility() { return isAbilityLocked() && isMaxed() && !temporary; }
    /** Unlocks the ability (cash handling is done by {@code TowerManager.unlockAbility}); it is ready immediately. */
    public void unlockAbility() {
        if (!isAbilityLocked()) return;
        abilityUnlocked = true;
        abilityCooldown = 0;
    }
    public boolean isAbilityReady() { return getAbility() != null && abilityCooldown <= 0 && !isSurveilled(); }
    public double getAbilityCooldownRemaining() { return abilityCooldown; }
    public double getAbilityCooldownFraction() { AbilityDef a = getAbility(); return a == null ? 0 : Math.max(0, abilityCooldown / a.cooldown); }
    public void startAbilityCooldown() { AbilityDef a = getAbility(); if (a != null) abilityCooldown = a.cooldown; }
    public void resetAbilityCooldown() { abilityCooldown = 0; }
    public void reduceAbilityCooldown(double fraction) { abilityCooldown *= (1 - fraction); }

    // ---------------- per-tower memory ----------------
    /** Named counter (default 0): pop counts, periodic timers, cycle indices. */
    public double counter(String key) { Double v = counters.get(key); return v == null ? 0 : v; }
    public void setCounter(String key, double v) { counters.put(key, v); }
    public double addCounter(String key, double delta) { double v = counter(key) + delta; counters.put(key, v); return v; }
    public Map<String, Double> counters() { return counters; }
    /** Free-form per-tower state for behaviours (drone handles, zone lists, ...). */
    public Map<String, Object> state() { return state; }

    /**
     * Periodic timer helper: accumulates {@code dt} under {@code key} and returns true once per
     * {@code interval} seconds (the first time after one full interval).
     */
    public boolean periodic(String key, double interval, double dt) {
        double c = counter(key) + dt;
        if (c >= interval) { counters.put(key, c - interval); return true; }
        counters.put(key, c);
        return false;
    }

    /**
     * Records an attack on a primary target and returns how many consecutive attacks IN A ROW already hit that
     * same target (0 for the first). Switching targets restarts the streak. Callers cap it themselves.
     */
    public int registerStreak(int enemyId) {
        if (enemyId == streakTargetId) { streakCount++; return streakCount - 1; }
        streakTargetId = enemyId;
        streakCount = 1;
        return 0;
    }
    public void resetStreak() { streakTargetId = -1; streakCount = 0; }
    public int getStreakTargetId() { return streakTargetId; }

    // ---------------- effective numbers ----------------
    public double effectiveRange(Game game) {
        double r = (stats.range + behavior.flatRangeBonus(this)) * (1 + buffTotal(BuffStat.RANGE)) * mapRange();
        if (game != null) r *= game.getMap().towerRangeMultiplier(game, this);
        if (isSurveilled()) r *= 0.7;
        return r;
    }

    public double effectiveRate(Game game) {
        double r = stats.rate * (1 + buffTotal(BuffStat.RATE)) * selfRateMult() * mapRate();
        if (game != null) {
            r *= game.getMap().towerRateMultiplier(game, this);
            r *= game.getGlobalRateMultiplier();
        }
        if (isSurveilled()) r *= 0.5;
        return r;
    }

    /** Multiplier from the map and global rules (auras are flat now and handled by {@link #flatDamageBuff()}). */
    public double damageMultiplier(Game game) {
        double m = mapDamage();
        if (game != null) {
            m *= game.getMap().towerDamageMultiplier(game, this);
            m *= game.getGlobalDamageMultiplier();
        }
        return m;
    }

    // ---------------- per tick ----------------
    /** Advances timers (game time, so fast-forward speeds them up). Returns true if this tower wants to attack. */
    public boolean tickTimers(Game game, double dt) {
        if (temporary) {
            lifetime -= dt;
            if (lifetime <= 0) alive = false;
        }
        for (int i = timedBuffs.size() - 1; i >= 0; i--) {
            TimedBuff b = timedBuffs.get(i);
            b.remaining -= dt;
            if (b.remaining <= 0) timedBuffs.remove(i);
        }
        for (int i = mapBuffs.size() - 1; i >= 0; i--) {
            MapBuff b = mapBuffs.get(i);
            b.remaining -= dt;
            if (b.remaining <= 0) mapBuffs.remove(i);
        }
        for (int i = selfBuffs.size() - 1; i >= 0; i--) {
            SelfBuff b = selfBuffs.get(i);
            b.remaining -= dt;
            if (b.remaining <= 0) selfBuffs.remove(i);
        }
        if (abilityCooldown > 0) abilityCooldown = Math.max(0, abilityCooldown - dt);
        if (surveilledRemaining > 0) surveilledRemaining = Math.max(0, surveilledRemaining - dt);
        if (stats.kind == AttackKind.NONE) return false;
        attackCooldown -= dt;
        return attackCooldown <= 0;
    }

    /** Called by Combat after a successful attack. */
    public void onAttacked(Game game) {
        double rate = Math.max(0.05, effectiveRate(game));
        attackCooldown = Math.max(attackCooldown + 1.0 / rate, 1.0 / rate * 0.5);
        if (attackCooldown > 1.0 / rate) attackCooldown = 1.0 / rate;
        lastFireTime = game.getTime();
    }

    /** Called when no target is available (keeps the tower ready). */
    public void idle() { attackCooldown = Math.max(attackCooldown, 0); }

    @Override public String toString() {
        return def.type.displayName + "#" + id + "(T" + tier + ")";
    }
}
