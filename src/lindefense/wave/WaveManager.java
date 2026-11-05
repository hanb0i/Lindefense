package lindefense.wave;

import java.util.ArrayList;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.sim.Game;

/**
 * Schedules the 100-wave campaign: starts waves on request, spawns each group's
 * enemies at their intervals, and reports completion once everything spawned
 * (including children) has been destroyed or leaked. The next wave never starts
 * automatically while the current one is still running unless auto-start is
 * enabled by the player, and even then only after the wave is cleared.
 */
public class WaveManager {
    private final Game game;
    private int currentWave;              // 0 = none started yet
    private boolean waveActive;
    private double waveTime;
    private final List<int[]> progress = new ArrayList<>(); // per group: spawned count
    private final List<Double> nextSpawnAt = new ArrayList<>();
    private WaveDef current;
    private boolean autoStart;
    private double prepTimer;
    public static final double PREP_TIME = 8.0;

    public WaveManager(Game game) { this.game = game; }

    public int getCurrentWave() { return currentWave; }
    public boolean isWaveActive() { return waveActive; }
    public WaveDef getCurrentDef() { return current; }
    public boolean isAutoStart() { return autoStart; }
    public void setAutoStart(boolean a) { autoStart = a; prepTimer = PREP_TIME; }
    public double getPrepTimer() { return prepTimer; }
    public double getWaveTime() { return waveTime; }
    public boolean isCampaignComplete() { return currentWave >= WaveData.WAVE_COUNT && !waveActive; }

    /** Remaining enemies to spawn in the current wave. */
    public int getRemainingToSpawn() {
        if (!waveActive || current == null) return 0;
        int n = 0;
        for (int i = 0; i < current.groups.size(); i++) n += current.groups.get(i).count - progress.get(i)[0];
        return n;
    }

    /** True if the next wave may start (PATCH NOTES: also opens a due draft and is false until it is picked). */
    public boolean canStartNextWave() {
        return !waveActive && currentWave < WaveData.WAVE_COUNT && game.getVariance().readyFor(currentWave + 1);
    }

    /** Starts the next wave. Returns false if a wave is active or the campaign is over. */
    public boolean startNextWave() {
        if (!canStartNextWave()) return false;
        currentWave++;
        current = game.getDifficulty().shape(WaveData.get(currentWave), game.getSeed());   // DIFFICULTY HOOK
        current = game.getVariance().shapeWave(current);   // PATCH NOTES / BREAKING NEWS: counts, spawn gaps, Camo
        waveActive = true;
        waveTime = 0;
        progress.clear();
        nextSpawnAt.clear();
        for (SpawnGroup g : current.groups) {
            progress.add(new int[] { 0 });
            nextSpawnAt.add(g.startDelay);
        }
        game.onWaveStarted(currentWave, current);
        return true;
    }

    public void update(double dt) {
        if (!waveActive) {
            if (autoStart && canStartNextWave() && currentWave > 0) {
                prepTimer -= dt;
                if (prepTimer <= 0) { prepTimer = PREP_TIME; startNextWave(); }
            }
            return;
        }
        waveTime += dt;
        boolean allSpawned = true;
        for (int i = 0; i < current.groups.size(); i++) {
            SpawnGroup g = current.groups.get(i);
            int[] p = progress.get(i);
            while (p[0] < g.count && waveTime >= nextSpawnAt.get(i)) {
                Enemy e = game.getEnemyManager().spawn(g.type, g.modifiers, g.route, 0);
                if (e != null) p[0]++;
                nextSpawnAt.set(i, nextSpawnAt.get(i) + Math.max(0.05, g.interval));
            }
            if (p[0] < g.count) allSpawned = false;
        }
        if (allSpawned && game.getEnemyManager().getAliveCount() == 0 && game.getCombat().getProjectiles().isEmpty()) {
            waveActive = false;
            prepTimer = PREP_TIME;
            game.onWaveCompleted(currentWave, current);
        }
    }

    /** Forces the current wave to end (used when the campaign ends on Palantir's defeat). */
    public void endWave() { waveActive = false; }
}
