package lindefense.enemy;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.tower.Tower;

/**
 * Boss enemies: corporate MOAB-class entities with large health bars.
 *
 * <p>Palantir (BAD) has three defensive phases driven by HP thresholds and the
 * signature <b>Predictive Surveillance</b> ability:</p>
 * <ol>
 *   <li>Every {@code SURVEILLANCE_INTERVAL[phase]} seconds Palantir begins a
 *       {@link #TELEGRAPH_TIME}-second analysis; the towers it has chosen (the
 *       N highest-investment towers) are marked with a reticle.</li>
 *   <li>When the telegraph ends, marked towers that are not immune become
 *       <i>Surveilled</i> for {@link #SURVEIL_DURATION} s: -50% attack speed,
 *       -30% range, abilities locked.</li>
 *   <li>Counters: Perplexity (Sonar Reasoning Pro, U2) makes towers in its radius immune;
 *       upgrading, or selling and re-placing a tower also clears it.</li>
 * </ol>
 * <p>Each phase also has a signature ability (Panopticon, Prompt Broadcast, System Takeover), implemented in
 * {@link PalantirProtocols}.</p>
 */
public class Boss extends Enemy {
    public static final double TELEGRAPH_TIME = 3.0;
    public static final double SURVEIL_DURATION = 8.0;
    private static final double[] SURVEILLANCE_INTERVAL = { 30, 20, 14 };
    private static final int[] SURVEILLANCE_TARGETS = { 2, 3, 4 };
    private static final double[] PALANTIR_ARMOR = { 0.60, 0.35, 0.10 };
    private static final double[] PALANTIR_SPEED = { 1.0, 1.3, 1.7 };
    private static final String[] PALANTIR_PHASE_NAMES = { "Surveillance Shell", "Predictive Core", "Exposed Core" };

    private int phase;
    private double surveillanceTimer = SURVEILLANCE_INTERVAL[0];
    private double telegraphRemaining;
    private final List<Tower> markedTowers = new ArrayList<>();
    private boolean entranceAnnounced;
    private int pendingPhaseEvent = -1;
    private double shieldOffRemaining;
    /** Palantir's per-phase signature abilities (null for every other boss). */
    private final PalantirProtocols protocols;

    public Boss(EnemyType type, EnumSet<Modifier> modifiers, Path route, int routeIndex, double distance,
                double hpScale, double speedScale) {
        super(type, modifiers, route, routeIndex, distance, hpScale, speedScale);
        protocols = type == EnemyType.PALANTIR ? new PalantirProtocols() : null;
    }

    /** Palantir's phase abilities (Panopticon, Prompt Broadcast, System Takeover); null for other bosses. */
    public PalantirProtocols getProtocols() { return protocols; }

    /** True while Palantir is sealed by its System Takeover window grab (reduced damage, regeneration). */
    public boolean isSealed() { return protocols != null && protocols.isSealed(); }

    /** While sealed, Palantir takes only {@link PalantirProtocols#SEAL_DAMAGE_MULT} of every hit. */
    @Override public double takeDamage(double amount, double now) {
        return super.takeDamage(isSealed() ? amount * PalantirProtocols.SEAL_DAMAGE_MULT : amount, now);
    }

    public boolean isPalantir() { return getType() == EnemyType.PALANTIR; }
    public int getPhase() { return phase; }
    public int getPhaseCount() { return isPalantir() ? 3 : 1; }
    public String getPhaseName() { return isPalantir() ? PALANTIR_PHASE_NAMES[phase] : getType().getBossClass().label; }
    public boolean isTelegraphing() { return telegraphRemaining > 0; }
    public double getTelegraphRemaining() { return telegraphRemaining; }
    public double getSurveillanceTimer() { return surveillanceTimer; }
    public List<Tower> getMarkedTowers() { return markedTowers; }

    /** Phase 1 Palantir shrugs off slows, stuns and knockback (unless its phase shield is down). */
    @Override public boolean isControlImmune() { return isPalantir() && phase == 0 && shieldOffRemaining <= 0; }

    /**
     * Qwen's Cosmic Sovereign Burst: Palantir loses its current <b>phase shield</b> for {@code seconds}.
     * The phase shield is its phase armour (60% / 35% / 10%) and phase 1's immunity to slow, stun and
     * knockback; while the shield is down armour is 0 and controls apply normally. No effect on other bosses.
     */
    public void disablePhaseShield(double seconds) {
        if (isPalantir()) shieldOffRemaining = Math.max(shieldOffRemaining, seconds);
    }
    public boolean isPhaseShieldDown() { return shieldOffRemaining > 0; }
    public double getPhaseShieldOffRemaining() { return shieldOffRemaining; }

    @Override protected double baseArmor() {
        if (!isPalantir()) return super.baseArmor();
        return shieldOffRemaining > 0 ? 0 : PALANTIR_ARMOR[phase];
    }

    @Override protected double ownSpeedMultiplier() {
        return super.ownSpeedMultiplier() * (isPalantir() ? PALANTIR_SPEED[phase] : 1.0);
    }

    /** Recomputes the phase from HP; returns the new phase if it changed, else -1. */
    public int updatePhase() {
        if (!isPalantir()) return -1;
        double f = getHpFraction();
        int np = f > 0.70 ? 0 : (f > 0.35 ? 1 : 2);
        if (np > phase) {
            phase = np;
            surveillanceTimer = Math.min(surveillanceTimer, SURVEILLANCE_INTERVAL[phase] * 0.5);
            return phase;
        }
        return -1;
    }

    /** Per-tick boss logic. Called by EnemyManager after statuses tick. */
    public void updateBoss(Game game, double dt) {
        if (!isAlive() || getHp() <= 0) return;
        if (shieldOffRemaining > 0) shieldOffRemaining = Math.max(0, shieldOffRemaining - dt);
        if (!entranceAnnounced) {
            entranceAnnounced = true;
            game.announceBoss(this);
        }
        int newPhase = updatePhase();
        if (newPhase >= 0) {
            pendingPhaseEvent = newPhase;
            game.onPalantirPhase(this, newPhase);
            if (protocols != null) protocols.onPhase(game, this, newPhase);   // PHASE ABILITIES
        }
        if (!isPalantir()) return;
        protocols.update(game, this, dt);   // PHASE ABILITIES: Panopticon / Prompt Broadcast / System Takeover

        if (telegraphRemaining > 0) {
            telegraphRemaining -= dt;
            if (telegraphRemaining <= 0) {
                int applied = 0;
                for (Tower t : markedTowers) {
                    if (t.isAlive() && !t.isSurveillanceImmune()) { t.setSurveilled(SURVEIL_DURATION); applied++; }
                }
                game.onSurveillanceApplied(this, applied, markedTowers.size());
                markedTowers.clear();
            }
            return;
        }
        surveillanceTimer -= dt;
        if (surveillanceTimer <= 0) {
            surveillanceTimer = SURVEILLANCE_INTERVAL[phase];
            beginSurveillance(game);
        }
    }

    /** Starts a Predictive Surveillance telegraph against the strongest towers. */
    public void beginSurveillance(Game game) {
        markedTowers.clear();
        List<Tower> candidates = new ArrayList<>();
        for (Tower t : game.getTowerManager().getTowers()) if (!t.isTemporary()) candidates.add(t);
        candidates.sort(Comparator.comparingDouble((Tower t) -> -t.getInvestedCost()));
        // scale with the size of the defence so the ability stays meaningful against large builds
        int scaled = (int) Math.ceil(candidates.size() * (0.10 + 0.05 * phase));
        int n = Math.min(Math.max(SURVEILLANCE_TARGETS[phase], scaled), candidates.size());
        for (int i = 0; i < n; i++) markedTowers.add(candidates.get(i));
        telegraphRemaining = TELEGRAPH_TIME;
        game.onSurveillanceTelegraph(this, markedTowers);
    }

    /** Consumes a pending phase-transition event (for renderer effects / tests). */
    public int consumePhaseEvent() {
        int p = pendingPhaseEvent;
        pendingPhaseEvent = -1;
        return p;
    }
}
