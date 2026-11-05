package lindefense.tower;

import java.util.LinkedHashMap;
import java.util.Map;
import lindefense.combat.HitSpec;

/**
 * Complete numeric description of a tower at one progression tier. The data table defines the base tier; each
 * upgrade mutates a copy, so the four tiers (base + 3 upgrades) are cumulative. Core combat numbers are typed
 * fields; every tower-specific mechanic number lives in the named-parameter map ({@link #p(String)}), so
 * behaviours never contain literals. Distances are px (1:1 with the 1200x900 world), times are seconds.
 */
public class TowerStats {
    /** Range used for "entire map" (DeepSeek); larger than the map diagonal (1500 px). */
    public static final double UNLIMITED_RANGE = 2000;

    /**
     * World pixels per "map unit", the distance unit of the Hero Store / Zethos specification (ranges, radii and
     * projectile speeds in map units and map units per second). 4 px keeps those characters' ranges (40-80 units =
     * 160-320 px) in the same band as the rest of the roster (150-260 px).
     */
    public static final double MAP_UNIT = 4.0;

    /** Converts map units to world pixels. */
    public static double u(double mapUnits) { return mapUnits * MAP_UNIT; }

    /** Converts world pixels to map units (for display). */
    public static double toUnits(double px) { return px / MAP_UNIT; }

    public AttackKind kind = AttackKind.PROJECTILE;
    public HitSpec hit = new HitSpec();
    public double range = 150;
    /** Attacks per second (= 1 / interval). */
    public double rate = 1.0;
    /** Enemies one attack can hit (projectile pierce, beam pass-through). For splash shots: enemies the blast hits (1 = unlimited). */
    public int pierce = 1;
    public double projectileSpeed = 450;
    /** Splash radius in px (0 = none). */
    public double splashRadius = 0;
    /** Extra chain hops after the first hit (CHAIN, or INSTANT ricochet) and their reach. */
    public int chainHops = 0;
    public double chainRange = 80;
    /** Projectile bounce count (MiniMax) and reach. */
    public int bounces = 0;
    public double bounceRange = 90;
    /** Total pieces a projectile splits into on its first hit (MiniMax U2: 2). */
    public int clones = 0;
    /** Projectiles fired per target per attack (fan). */
    public int projectilesPerShot = 1;
    /** Distinct simultaneous targets per attack. */
    public int targets = 1;
    /** Display only: consecutive-hit bonus cap and step (DeepSeek R1, Kimi). Mechanics read params. */
    public int stackCap = 0;
    public double stackStep = 1;

    public boolean seesCamo = false;
    /** Ignores line-of-sight blockers (Student+AI notes, DeepSeek). */
    public boolean ignoresLos = false;

    // ---- aura given to OTHER towers within auraRange (each source tower type counts once per stat) ----
    public double auraRange = 0;
    /** Attack-speed fraction (0.10 = +10%). */
    public double auraRate = 0;
    /** Flat damage added to each attack (+1). */
    public double auraDamage = 0;
    /** Pierce added (+1). */
    public int auraPierce = 0;
    /** Range fraction (0.15 = +15%). */
    public double auraRangeBonus = 0;
    /** Towers in the aura gain camo detection. */
    public boolean auraDetection = false;
    /** Towers in the aura are immune to Predictive Surveillance. */
    public boolean auraSurveillanceImmunity = false;
    /** Towers in the aura resist prompt injection (Copilot's firewall). */
    public boolean auraInjectionImmunity = false;

    // ---- prompt injection (see lindefense.sim.PromptInjection) ----
    /** The tower is smart enough in cybersecurity to ignore injected instructions: it can never be hijacked or disabled. */
    public boolean injectionImmune = false;
    /** Why it is immune, shown in the info panel and catalog ("Constitutional AI ..."); null when not immune. */
    public String injectionImmuneReason = null;

    // ---- enemy field around the tower (Sora slow, Brad discipline, Perplexity analysis) ----
    /** Field radius; 0 = use the tower's range. */
    public double fieldRadius = 0;
    /** Slow applied to enemies in the field (refreshed every few ticks). */
    public double auraEnemySlow = 0;
    /** Flat / percent mark applied to enemies in the field. */
    public double fieldMarkFlat = 0;
    public double fieldMarkPct = 0;
    /** Whether bosses are affected by the field's mark/slow (Brad's field spares bosses). */
    public boolean fieldAffectsBosses = true;

    /** Cash paid at the end of every wave (Perplexity). */
    public double incomePerWave = 0;
    /** Display only: periodic summon (kept for the info panel). */
    public double summonInterval = 0;
    public int summonCount = 0;

    private final Map<String, Double> params = new LinkedHashMap<>();

    // ---------------- named parameters ----------------
    /** Mechanic parameter; throws if the data table never defined it (typos fail loudly). */
    public double p(String key) {
        Double v = params.get(key);
        if (v == null) throw new IllegalArgumentException("Missing tower parameter '" + key + "'");
        return v;
    }
    /** Mechanic parameter with a default for "not unlocked yet". */
    public double p(String key, double dflt) { Double v = params.get(key); return v == null ? dflt : v; }
    public int pi(String key) { return (int) Math.round(p(key)); }
    public int pi(String key, int dflt) { Double v = params.get(key); return v == null ? dflt : (int) Math.round(v); }
    public boolean has(String key) { Double v = params.get(key); return v != null && v != 0; }
    public TowerStats set(String key, double value) { params.put(key, value); return this; }
    public Map<String, Double> params() { return params; }

    /** Sets the attack interval in seconds (rate = 1 / interval). */
    public TowerStats interval(double seconds) { this.rate = 1.0 / seconds; return this; }
    /** Attack interval in seconds. */
    public double interval() { return 1.0 / rate; }

    public TowerStats copy() {
        TowerStats s = new TowerStats();
        s.kind = kind; s.hit = hit.copy(); s.range = range; s.rate = rate; s.pierce = pierce;
        s.projectileSpeed = projectileSpeed; s.splashRadius = splashRadius; s.chainHops = chainHops;
        s.chainRange = chainRange; s.bounces = bounces; s.bounceRange = bounceRange; s.clones = clones;
        s.projectilesPerShot = projectilesPerShot; s.targets = targets; s.stackCap = stackCap; s.stackStep = stackStep;
        s.seesCamo = seesCamo; s.ignoresLos = ignoresLos;
        s.auraRange = auraRange; s.auraRate = auraRate; s.auraDamage = auraDamage; s.auraPierce = auraPierce;
        s.auraRangeBonus = auraRangeBonus; s.auraDetection = auraDetection; s.auraSurveillanceImmunity = auraSurveillanceImmunity;
        s.auraInjectionImmunity = auraInjectionImmunity; s.injectionImmune = injectionImmune; s.injectionImmuneReason = injectionImmuneReason;
        s.fieldRadius = fieldRadius; s.auraEnemySlow = auraEnemySlow; s.fieldMarkFlat = fieldMarkFlat;
        s.fieldMarkPct = fieldMarkPct; s.fieldAffectsBosses = fieldAffectsBosses;
        s.incomePerWave = incomePerWave; s.summonInterval = summonInterval; s.summonCount = summonCount;
        s.params.putAll(params);
        return s;
    }

    public boolean isSupportOnly() { return kind == AttackKind.NONE; }
    public boolean hasUnlimitedRange() { return range >= UNLIMITED_RANGE; }
}
