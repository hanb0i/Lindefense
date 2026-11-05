package lindefense.sim;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import lindefense.audio.AudioManager;
import lindefense.audio.Sfx;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.tower.Intrusion;
import lindefense.tower.Tower;

/**
 * Prompt injection: the satire of real AI prompt-injection attacks. Owned by {@link Game} and updated once per step
 * before the towers act.
 *
 * <h3>Injector enemies ({@link Modifier#INJECTION})</h3>
 * An enemy carrying the "IGNORE PREVIOUS INSTRUCTIONS" sign broadcasts its prompt as soon as any player tower is
 * within {@link #RADIUS} px, then again every {@link #INTERVAL} s while towers stay in reach. Each broadcast hijacks
 * the {@link #MAX_TARGETS} nearest towers that are not immune for {@link #HIJACK_TIME} s. Stunned, frozen or
 * Disrupted injectors cannot broadcast. Immune towers in reach show "BLOCKED".
 *
 * <h3>Hijacked towers</h3>
 * A hijacked tower stops attacking enemies and fires on its neighbours instead: {@link #FIRST_ZAP} s after the hijack
 * and then every {@link #ZAP_INTERVAL} s ({@link #ZAPS_PER_HIJACK} zaps in all) it zaps the nearest other tower within
 * {@link #ZAP_RANGE} px that can be compromised, disabling it for {@link #DISABLE_TIME} s. Towers have no health, so
 * "damage" is downtime. Chains are bounded: a disabled tower never becomes hijacked, and every intrusion is followed by
 * {@link Intrusion#GRACE} s of patch time ({@link Intrusion}), so one injector can take at most
 * {@code MAX_TARGETS * (1 + ZAPS_PER_HIJACK)} towers offline per broadcast and no tower is ever locked out twice in a row.
 *
 * <h3>Immunity</h3>
 * Towers "smart enough in cybersecurity" carry the data flag {@code TowerStats.injectionImmune}: Claude
 * (Constitutional AI), Copilot (Security Copilot), DeepSeek (reasoning catches the trick), Perplexity (source
 * verification) and the hero Mr. Lindemann (the CS teacher). Copilot's firewall aura additionally protects every tower
 * in its tether radius. See {@link Tower#isInjectionImmune()}.
 *
 * <h3>Palantir</h3>
 * {@link #hijackStrongest} is Palantir's Prompt Broadcast (phase 2), and {@link #registerDecoy} tracks its holographic
 * decoys, which every tower that is not immune to prompt injection targets first while they exist
 * ({@link #tauntComparator()}; the immune towers see through the holograms).
 */
public final class PromptInjection {
    /** The text on the sign. */
    public static final String SIGN = "IGNORE PREVIOUS INSTRUCTIONS";
    /** Reach of an injector's broadcast (px from the enemy's centre to the tower's centre). */
    public static final double RADIUS = 150;
    /** Seconds between two broadcasts of the same injector. */
    public static final double INTERVAL = 9.0;
    /** Towers one injector broadcast hijacks (the nearest eligible ones). */
    public static final int MAX_TARGETS = 2;
    /** Seconds a hijack lasts. */
    public static final double HIJACK_TIME = 3.0;
    /** How far a hijacked tower can reach a neighbour (px). */
    public static final double ZAP_RANGE = 170;
    /** Seconds from the hijack to the first zap. */
    public static final double FIRST_ZAP = 0.5;
    /** Seconds between zaps of one hijacked tower. */
    public static final double ZAP_INTERVAL = 1.25;
    /** Zaps one hijacked tower fires during its hijack. */
    public static final int ZAPS_PER_HIJACK = 2;
    /** Seconds a zapped neighbour stays disabled. */
    public static final double DISABLE_TIME = 1.5;
    /** Most "BLOCKED" labels one broadcast shows over immune towers. */
    private static final int MAX_BLOCK_LABELS = 2;
    private static final int PRUNE_TICKS = 60;

    /** Holograms first, then whatever ordering the tower uses. */
    private static final Comparator<Enemy> DECOYS_FIRST =
        Comparator.comparingInt((Enemy e) -> e.getType() == EnemyType.PALANTIR_HOLOGRAM ? 0 : 1);

    private final Game game;
    private final Map<Enemy, Double> cooldowns = new IdentityHashMap<>();
    private final List<Enemy> decoys = new ArrayList<>(2);
    private final List<Tower> scratch = new ArrayList<>(), scratchImmune = new ArrayList<>();
    private int ticks;
    private int broadcasts, hijacks, zaps, disables, blocks;
    /** Seconds since each injector last broadcast (for the renderer's flash), keyed like {@link #cooldowns}. */
    private final Map<Enemy, Double> lastBroadcast = new IdentityHashMap<>();

    /** Creates the system for a game. */
    public PromptInjection(Game game) { this.game = game; }

    // ------------------------------------------------------------------ per step
    /** Runs the injectors' broadcasts and the hijacked towers' zaps. Called by {@link Game#step}. */
    public void update(double dt) {
        List<Enemy> es = game.getEnemyManager().getEnemies();
        for (int i = 0, n = es.size(); i < n; i++) {
            Enemy e = es.get(i);
            if (!e.isAlive() || e.isStored() || !e.has(Modifier.INJECTION)) continue;
            Double last = lastBroadcast.get(e);
            if (last != null) lastBroadcast.put(e, last + dt);
            double cd = cooldowns.getOrDefault(e, 0.0) - dt;
            if (cd <= 0) cd = tryBroadcast(e) ? INTERVAL : 0;
            cooldowns.put(e, cd);
        }
        List<Tower> towers = game.getTowerManager().getTowers();
        for (int i = 0; i < towers.size(); i++) {
            Tower t = towers.get(i);
            if (t.isAlive() && t.getIntrusion().zapDue(dt)) zap(t);
        }
        if (++ticks % PRUNE_TICKS == 0) {
            cooldowns.keySet().removeIf(e -> !e.isAlive());
            lastBroadcast.keySet().removeIf(e -> !e.isAlive());
        }
    }

    /** One injector broadcast attempt; true if it fired (some tower, eligible or immune, was in reach). */
    private boolean tryBroadcast(Enemy e) {
        if (e.isStunned() || e.isDisrupted()) return false;
        Vec at = e.getPosition();
        List<Tower> eligible = scratch, immune = scratchImmune;
        eligible.clear();
        immune.clear();
        for (Tower t : game.getTowerManager().getTowers()) {
            if (!t.isAlive() || t.isTemporary() || t.getPosition().exceedsDist(at, RADIUS)) continue;
            if (t.isInjectionImmune()) immune.add(t);
            else if (t.getIntrusion().canBeCompromised()) eligible.add(t);
        }
        if (eligible.isEmpty() && immune.isEmpty()) return false;
        eligible.sort(Comparator.comparingDouble((Tower t) -> t.getPosition().distSq(at)).thenComparingInt(Tower::getId));
        int n = 0;
        for (int i = 0; i < eligible.size() && n < MAX_TARGETS; i++) if (hijack(eligible.get(i), e, HIJACK_TIME)) n++;
        for (int i = 0; i < immune.size() && i < MAX_BLOCK_LABELS; i++) {
            game.getEvents().add(VisualEvent.text(immune.get(i).getPosition(), "BLOCKED", 0x7fd8a8));
            blocks++;
        }
        broadcasts++;
        lastBroadcast.put(e, 0.0);
        if (n > 0) AudioManager.sfx(Sfx.INVALID);   // AUDIO HOOK: the glitchy "access denied" blip (the sign flashes in the view)
        return true;
    }

    /** A hijacked tower's zap: disables the nearest neighbour that can be compromised (none in reach = a wasted zap). */
    private void zap(Tower h) {
        Tower best = null;
        double bestD = ZAP_RANGE * ZAP_RANGE;
        for (Tower o : game.getTowerManager().getTowers()) {
            if (o == h || !o.isAlive() || o.isTemporary() || o.isInjectionImmune() || !o.getIntrusion().canBeCompromised()) continue;
            double d = o.getPosition().distSq(h.getPosition());
            if (d <= bestD) { bestD = d; best = o; }
        }
        if (best != null && best.getIntrusion().disable(DISABLE_TIME, h)) {
            disables++;
            game.getEvents().add(VisualEvent.chain(h.getPosition(), best.getPosition(), 0xff3b6e));
        } else {
            best = null;
        }
        zaps++;
        h.getIntrusion().recordZap(best, ZAP_INTERVAL);
    }

    // ------------------------------------------------------------------ API
    /**
     * Hijacks one tower for {@code seconds} on behalf of {@code source} (an injector enemy or Palantir). Immune,
     * offline and patched towers refuse. Returns true if the tower is now hijacked.
     */
    public boolean hijack(Tower t, Object source, double seconds) {
        if (t == null || !t.isAlive() || t.isTemporary() || t.isInjectionImmune()) return false;
        if (!t.getIntrusion().hijack(seconds, source, FIRST_ZAP, ZAPS_PER_HIJACK)) return false;
        hijacks++;   // the world view tags the tower HIJACKED while it lasts
        return true;
    }

    /**
     * Palantir's Prompt Broadcast: hijacks the {@code n} highest-investment player towers that can be hijacked
     * (immune, offline and patched towers are skipped). Returns the towers hijacked.
     */
    public List<Tower> hijackStrongest(Object source, int n, double seconds) {
        List<Tower> cands = new ArrayList<>();
        for (Tower t : game.getTowerManager().getTowers()) {
            if (t.isAlive() && !t.isTemporary() && !t.isInjectionImmune() && t.getIntrusion().canBeCompromised()) cands.add(t);
        }
        cands.sort(Comparator.comparingDouble((Tower t) -> -t.getInvestedCost()).thenComparingInt(Tower::getId));
        List<Tower> done = new ArrayList<>();
        for (int i = 0; i < cands.size() && done.size() < n; i++) if (hijack(cands.get(i), source, seconds)) done.add(cands.get(i));
        return done;
    }

    /** Registers one of Palantir's holographic decoys: while any is alive, towers that are not immune target decoys first. */
    public void registerDecoy(Enemy e) { if (e != null) decoys.add(e); }

    /** True while a registered decoy is alive on the track. */
    public boolean hasDecoys() {
        if (decoys.isEmpty()) return false;
        for (int i = decoys.size() - 1; i >= 0; i--) if (!decoys.get(i).isAlive()) decoys.remove(i);
        return !decoys.isEmpty();
    }

    /** The live decoys (do not modify). */
    public List<Enemy> getDecoys() { hasDecoys(); return decoys; }

    /** Target priority that puts decoys first while any exist (null otherwise), used by target acquisition. */
    public Comparator<Enemy> tauntComparator() { return hasDecoys() ? DECOYS_FIRST : null; }

    /** Seconds since an injector's last broadcast, or a large number if it never broadcast. */
    public double sinceBroadcast(Enemy e) { Double d = lastBroadcast.get(e); return d == null ? 99 : d; }

    /** Seconds until an injector may broadcast again (0 = ready, waiting for a tower in reach). */
    public double cooldownOf(Enemy e) { return Math.max(0, cooldowns.getOrDefault(e, 0.0)); }

    // ------------------------------------------------------------------ stats (tests, tuning)
    /** Injector broadcasts that fired. */
    public int getBroadcasts() { return broadcasts; }
    /** Towers hijacked (injectors and Palantir). */
    public int getHijacks() { return hijacks; }
    /** Zaps fired by hijacked towers (including ones with no neighbour in reach). */
    public int getZaps() { return zaps; }
    /** Neighbours disabled by zaps. */
    public int getDisables() { return disables; }
    /** "BLOCKED" labels shown over immune towers. */
    public int getBlocks() { return blocks; }
}
