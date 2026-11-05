package lindefense.enemy;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import lindefense.audio.AudioManager;
import lindefense.audio.Sfx;
import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.sim.PromptInjection;
import lindefense.sim.Vec;
import lindefense.sim.WindowLink;
import lindefense.tower.Tower;

/**
 * Palantir's signature ability for each of its three phases, on top of its phase armour / speed and Predictive
 * Surveillance (which stay in {@link Boss}). One instance belongs to each Palantir.
 *
 * <ol>
 *   <li><b>Panopticon</b> (phase 1, Surveillance Shell): a surveillance beam {@link #PANOPTICON_RANGE} px long rotates
 *       around Palantir once every {@link #PANOPTICON_PERIOD} s. Every player tower it sweeps is <i>blinded</i> (cannot
 *       attack or use its ability) for {@link #PANOPTICON_BLIND} s. Counter: Perplexity's Predictive Analysis (U2)
 *       radius, the same one that blocks Predictive Surveillance.</li>
 *   <li><b>Prompt Broadcast</b> (phase 2, Predictive Core): {@link #BROADCAST_FIRST} s after the phase starts and then
 *       every {@link #BROADCAST_INTERVAL} s Palantir broadcasts a prompt injection that hijacks the
 *       {@link #broadcastTargets highest-investment} towers that are not immune (see {@link PromptInjection}). On entering
 *       the phase it also projects {@link #DECOYS} holographic decoy Palantirs ({@link EnemyType#PALANTIR_HOLOGRAM},
 *       {@link #DECOY_HP_FRACTION} of its max HP each) that every tower targets first, except the towers immune to
 *       prompt injection, which see through them.</li>
 *   <li><b>System Takeover</b> (phase 3, Exposed Core): on entering the phase a <i>kill switch</i> restarts the full
 *       cooldown of every unlocked tower ability once (towers immune to prompt injection resist it; a warning is shown at
 *       {@link #KILL_SWITCH_WARNING} HP), the existing Lockheed escorts launch, and Palantir grabs the game window
 *       (renewed every {@link #REGRAB_INTERVAL} s). While the window stays below
 *       {@link WindowLink#SEAL_THRESHOLD} of its pre-takeover size Palantir is <b>sealed</b>: it takes
 *       {@link #SEAL_DAMAGE_MULT} damage and regenerates {@link #SEAL_REGEN_PER_SEC} of its max HP per second (never above
 *       {@link #SEAL_REGEN_CAP}). Dragging the window back breaks the seal. With window effects off, or in any headless
 *       run, the window is never grabbed and Palantir is never sealed.</li>
 * </ol>
 */
public final class PalantirProtocols {
    /** Ability name of each phase. */
    public static final String[] ABILITY_NAMES = { "Panopticon", "Prompt Broadcast", "System Takeover" };

    // ---- phase 1: Panopticon
    /** Length of the rotating surveillance beam (px). */
    public static final double PANOPTICON_RANGE = 380;
    /** Seconds for one full turn of the beam. */
    public static final double PANOPTICON_PERIOD = 10.0;
    /** Half the beam's angular width (radians); the tower's own footprint is added on top. */
    public static final double PANOPTICON_HALF_WIDTH = Math.toRadians(8);
    /** Seconds a swept tower stays blinded. */
    public static final double PANOPTICON_BLIND = 2.0;
    /** Seconds after Palantir arrives before the beam switches on. */
    public static final double PANOPTICON_DELAY = 3.0;

    // ---- phase 2: Prompt Broadcast
    /** Seconds from the start of phase 2 to the first broadcast. */
    public static final double BROADCAST_FIRST = 3.0;
    /** Seconds between broadcasts. */
    public static final double BROADCAST_INTERVAL = 12.0;
    /** Seconds a broadcast hijack lasts. */
    public static final double BROADCAST_HIJACK = 3.0;
    /** Towers hijacked per broadcast: this many, +1 per {@link #BROADCAST_TOWERS_PER_EXTRA} player towers, at most {@link #BROADCAST_MAX_TARGETS}. */
    public static final int BROADCAST_TARGETS = 3;
    public static final int BROADCAST_TOWERS_PER_EXTRA = 30;
    public static final int BROADCAST_MAX_TARGETS = 6;
    /** Holographic decoys projected when phase 2 starts. */
    public static final int DECOYS = 2;
    /** Each decoy's HP as a fraction of Palantir's max HP. */
    public static final double DECOY_HP_FRACTION = 0.02;
    /** Track distance between Palantir and each decoy (one ahead, one behind). */
    public static final double DECOY_SPACING = 90;

    // ---- phase 3: System Takeover
    /** HP fraction (in phase 2) at which the kill-switch warning is shown. */
    public static final double KILL_SWITCH_WARNING = 0.42;
    /** Damage multiplier while sealed. */
    public static final double SEAL_DAMAGE_MULT = 0.3;
    /** Regeneration while sealed, as a fraction of max HP per second. */
    public static final double SEAL_REGEN_PER_SEC = 0.005;
    /** Sealed regeneration never lifts Palantir above this HP fraction (its phase-3 threshold). */
    public static final double SEAL_REGEN_CAP = 0.35;
    /** Seconds between window-grab renewals while the takeover runs. */
    public static final double REGRAB_INTERVAL = 30.0;

    private double clock;
    private double beamAngle = -Math.PI / 2;
    private int blinds;
    private double broadcastTimer = -1;
    private int broadcasts, broadcastHijacks;
    private double lastBroadcastAge = 99;
    private List<Tower> lastBroadcastTargets = Collections.emptyList();
    private final List<Enemy> decoys = new ArrayList<>(DECOYS);
    private boolean killSwitchWarned, killSwitchUsed;
    private int killSwitchResets;
    private double killSwitchAge = 99;
    private double regrabTimer;
    private boolean sealed;
    private double sealedTime;
    private double healedWhileSealed;

    // ------------------------------------------------------------------ hooks from Boss
    /** Called by {@link Boss#updateBoss} when Palantir enters {@code phase} (0-based). */
    void onPhase(Game game, Boss b, int phase) {
        if (phase == 1) {
            broadcastTimer = BROADCAST_FIRST;
            spawnDecoys(game, b);
        } else if (phase == 2) {
            killSwitch(game, b);
            game.getWindowLink().requestGrab(b);
            regrabTimer = REGRAB_INTERVAL;
        }
    }

    /** Per-tick logic, called by {@link Boss#updateBoss} for a live Palantir. */
    void update(Game game, Boss b, double dt) {
        clock += dt;
        lastBroadcastAge += dt;
        killSwitchAge += dt;
        switch (b.getPhase()) {
            case 0: panopticon(game, b, dt); break;
            case 1: promptBroadcast(game, b, dt); break;
            default: systemTakeover(game, b, dt); break;
        }
    }

    // ------------------------------------------------------------------ phase 1
    private void panopticon(Game game, Boss b, double dt) {
        if (clock < PANOPTICON_DELAY) return;
        beamAngle = wrap(beamAngle + 2 * Math.PI / PANOPTICON_PERIOD * dt);
        Vec o = b.getPosition();
        for (Tower t : game.getTowerManager().getTowers()) {
            if (!t.isAlive() || t.isTemporary() || t.isSurveillanceImmune()) continue;
            if (!t.getIntrusion().canBeCompromised() || !inBeam(o, beamAngle, t)) continue;
            if (t.getIntrusion().blind(PANOPTICON_BLIND)) blinds++;   // the world view tags it BLINDED
        }
    }

    /** True if the beam from {@code origin} at {@code angle} covers the tower (range, width and the tower's footprint). */
    public static boolean inBeam(Vec origin, double angle, Tower t) {
        double dx = t.getPosition().x - origin.x, dy = t.getPosition().y - origin.y;
        double d = Math.sqrt(dx * dx + dy * dy);
        if (d > PANOPTICON_RANGE + t.getRadius()) return false;
        if (d < 1) return true;
        double diff = Math.abs(wrap(Math.atan2(dy, dx) - angle));
        return diff <= PANOPTICON_HALF_WIDTH + Math.atan2(t.getRadius(), d);
    }

    private static double wrap(double a) {
        while (a > Math.PI) a -= 2 * Math.PI;
        while (a < -Math.PI) a += 2 * Math.PI;
        return a;
    }

    // ------------------------------------------------------------------ phase 2
    private void promptBroadcast(Game game, Boss b, double dt) {
        if (!killSwitchWarned && b.getHpFraction() < KILL_SWITCH_WARNING) {
            killSwitchWarned = true;
            game.setBanner("KILL SWITCH ARMING: fire your abilities before Palantir drops to 35%", 0xffb020, 3.5);
        }
        if (broadcastTimer < 0) broadcastTimer = BROADCAST_FIRST;   // phase 2 entered without the hook (tests)
        broadcastTimer -= dt;
        if (broadcastTimer > 0) return;
        broadcastTimer = BROADCAST_INTERVAL;
        broadcast(game, b);
    }

    /** Fires one Prompt Broadcast now; returns the towers it hijacked. */
    public List<Tower> broadcast(Game game, Boss b) {
        int n = broadcastTargets(game);
        List<Tower> hit = game.getInjection().hijackStrongest(b, n, BROADCAST_HIJACK);
        broadcasts++;
        broadcastHijacks += hit.size();
        lastBroadcastTargets = hit;
        lastBroadcastAge = 0;
        AudioManager.sfx(Sfx.PALANTIR_WARNING);   // AUDIO HOOK
        if (hit.isEmpty()) game.setBanner("PROMPT BROADCAST blocked: your towers ignore it", 0x7fd8a8, 2.5);
        else game.setBanner("PROMPT BROADCAST: \"" + PromptInjection.SIGN + "\"  -  " + hit.size() + " tower(s) hijacked", 0xff4d4d, 3);
        return hit;
    }

    /** Towers one broadcast tries to hijack for the current defence size. */
    public static int broadcastTargets(Game game) {
        int towers = game.getTowerManager().getPlayerTowers().size();
        return Math.min(BROADCAST_MAX_TARGETS, BROADCAST_TARGETS + towers / BROADCAST_TOWERS_PER_EXTRA);
    }

    private void spawnDecoys(Game game, Boss b) {
        double hp = b.getMaxHp() * DECOY_HP_FRACTION;
        double hpScale = hp / EnemyType.PALANTIR_HOLOGRAM.baseHp;
        double len = b.getRoute().getTotalLength();
        for (int i = 0; i < DECOYS; i++) {
            double d = b.getDistance() + (i % 2 == 0 ? DECOY_SPACING : -DECOY_SPACING) * (1 + i / 2);
            d = Math.max(0, Math.min(len - 1, d));
            Enemy e = game.getEnemyManager().spawnScaled(EnemyType.PALANTIR_HOLOGRAM, null, b.getRouteIndex(), d, hpScale, b.getSpeedScale());
            decoys.add(e);
            game.getInjection().registerDecoy(e);
            game.getEvents().add(VisualEvent.teleport(e.getPosition()));
        }
        game.getEvents().add(VisualEvent.phase(b.getPosition(), "HOLOGRAMS", 0x8ad8ff));
    }

    // ------------------------------------------------------------------ phase 3
    private void killSwitch(Game game, Boss b) {
        if (killSwitchUsed) return;
        killSwitchUsed = true;
        int n = 0;
        for (Tower t : game.getTowerManager().getTowers()) {
            if (!t.isAlive() || t.isTemporary() || t.getAbility() == null || t.isInjectionImmune()) continue;
            t.startAbilityCooldown();
            n++;
            game.getEvents().add(VisualEvent.text(t.getPosition(), "KILL SWITCH", 0xffb020));
        }
        killSwitchResets = n;
        killSwitchAge = 0;
        game.setBanner("SYSTEM TAKEOVER: kill switch reset " + n + " abilit" + (n == 1 ? "y" : "ies") + "  -  Palantir reaches for your window", 0xff4d4d, 4);
    }

    private void systemTakeover(Game game, Boss b, double dt) {
        WindowLink link = game.getWindowLink();
        regrabTimer -= dt;
        if (regrabTimer <= 0) {
            regrabTimer = REGRAB_INTERVAL;
            link.requestGrab(b);
        }
        boolean now = link.isSealing();
        if (now != sealed) {
            sealed = now;
            if (now) game.setBanner("PALANTIR IS SEALED: it regenerates and shrugs off damage  -  drag your window back", 0xff4d4d, 4);
            else game.setBanner("SEAL BROKEN: window restored", 0x7fd8a8, 2.5);
        }
        if (!sealed) return;
        sealedTime += dt;
        double cap = SEAL_REGEN_CAP * b.getMaxHp();
        if (b.getHp() < cap) {
            double heal = Math.min(SEAL_REGEN_PER_SEC * b.getMaxHp() * dt, cap - b.getHp());
            b.heal(heal);
            healedWhileSealed += heal;
        }
    }

    // ------------------------------------------------------------------ state for the renderer / tests
    /** True while Palantir is sealed by the window grab (it takes {@link #SEAL_DAMAGE_MULT} damage and regenerates). */
    public boolean isSealed() { return sealed; }
    /** Seconds Palantir has spent sealed. */
    public double getSealedTime() { return sealedTime; }
    /** HP Palantir regenerated while sealed. */
    public double getHealedWhileSealed() { return healedWhileSealed; }
    /** Current angle of the Panopticon beam (radians, screen coordinates). */
    public double getBeamAngle() { return beamAngle; }
    /** True while the Panopticon beam is sweeping (phase 1, after its start-up delay). */
    public boolean isBeamActive(Boss b) { return b.getPhase() == 0 && clock >= PANOPTICON_DELAY; }
    /** Towers blinded by the beam so far. */
    public int getBlinds() { return blinds; }
    /** Prompt Broadcasts fired so far. */
    public int getBroadcasts() { return broadcasts; }
    /** Towers hijacked by Prompt Broadcasts so far. */
    public int getBroadcastHijacks() { return broadcastHijacks; }
    /** Seconds since the last Prompt Broadcast. */
    public double getLastBroadcastAge() { return lastBroadcastAge; }
    /** Towers hijacked by the last Prompt Broadcast. */
    public List<Tower> getLastBroadcastTargets() { return lastBroadcastTargets; }
    /** Seconds until the next Prompt Broadcast (phase 2 only). */
    public double getBroadcastTimer() { return Math.max(0, broadcastTimer); }
    /** The decoys projected in phase 2 (dead ones included). */
    public List<Enemy> getDecoys() { return decoys; }
    /** True once the kill switch fired. */
    public boolean isKillSwitchUsed() { return killSwitchUsed; }
    /** Ability cooldowns the kill switch reset. */
    public int getKillSwitchResets() { return killSwitchResets; }
    /** Seconds since the kill switch fired. */
    public double getKillSwitchAge() { return killSwitchAge; }
}
