package lindefense.tower.behavior;

import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.tower.BuffStat;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Tanimbus. A flying command drone that never attacks. At base and Enhanced Drone it locks onto the single
 * strongest tower in range (most invested) and speeds that one up; Tactical Network (U2) drops the lock and buffs
 * everything in range through the normal data-driven aura; Battlefield Command (U3) also rallies every tower on the
 * map on a timer. Buffs use the engine's aura / timed-buff system, so they obey the global stacking caps.
 */
public final class TanimbusBehavior extends TowerBehavior {
    private static final String RALLY = "rallyTimer";

    /** The supported tower when Tanimbus is still locking onto one, else null. */
    public static Tower supported(Game game, Tower t) {
        if (t.getStats().p("singleTarget", 0) <= 0) return null;
        double range = t.getStats().auraRange;
        Tower best = null;
        double bestScore = -1;
        for (Tower o : game.getTowerManager().getTowers()) {
            if (o == t || o.isTemporary() || !o.isAlive()) continue;
            if (o.getPosition().dist(t.getPosition()) > range) continue;
            double score = o.getInvestedCost();
            if (score > bestScore) { bestScore = score; best = o; }
        }
        return best;
    }

    @Override public void auraContribution(Game game, Tower src, Tower dst) {
        TowerStats s = src.getStats();
        if (s.p("singleTarget", 0) <= 0) { super.auraContribution(game, src, dst); return; }
        // locked mode: only the strongest tower in range is sped up
        if (dst != supported(game, src)) return;
        dst.addAuraBuff(BuffStat.RATE, src.getType(), s.p("buffRate"));
    }

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        double interval = s.p("rallyInterval", 0);
        if (interval <= 0 || !t.periodic(RALLY, interval, dt)) return;
        double rate = s.p("rallyRate"), duration = s.p("rallyDuration");
        for (Tower o : game.getTowerManager().getTowers()) {
            if (!o.isAlive() || o.isTemporary()) continue;
            o.addTimedBuff(BuffStat.RATE, t.getType(), rate, duration);
        }
        game.getCombat().emit(VisualEvent.text(t.getPosition(), "BATTLEFIELD COMMAND", t.getType().primaryRgb));
    }
}
