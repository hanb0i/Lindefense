package lindefense.tower.behavior;

import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.effects.Barrage;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.BuffStat;
import lindefense.tower.Faction;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;

/**
 * Copilot (spec 3.3 #8). The local tether (attack speed, pierce) is the data-driven aura; this class adds the
 * map-wide MILITARY bonus (U3), the Task Scheduler drone (U2: a one-shell barrage at the densest cluster) and
 * Enterprise Auto-Refactor.
 */
public final class CopilotBehavior extends TowerBehavior {
    @Override public void auraContribution(Game game, Tower src, Tower dst) {
        super.auraContribution(game, src, dst);
        TowerStats s = src.getStats();
        if (dst != src && dst.getType().faction == Faction.MILITARY && s.has("globalMilitaryRate")) {
            dst.addAuraBuff(BuffStat.RATE, src.getType(), s.p("globalMilitaryRate"));
            dst.addAuraBuff(BuffStat.DAMAGE_FLAT, src.getType(), s.p("globalMilitaryDamage"));
        }
    }

    @Override public void update(Game game, Tower t, double dt) {
        TowerStats s = t.getStats();
        if (!s.has("droneInterval") || !t.periodic("drone", s.p("droneInterval"), dt)) return;
        HitSpec h = new HitSpec(s.p("droneDamage"), DamageType.EXPLOSIVE);
        Barrage b = new Barrage(t, h, 1, s.p("droneSplash"));
        b.aim = Barrage.Aim.DENSEST;
        b.rgb = t.getType().primaryRgb;
        game.getEffects().fire(b);
    }

    /** Self-buff key of Enterprise Auto-Refactor on the towers it speeds up. */
    public static final String AUTO_REFACTOR = "autoRefactor";

    @Override public boolean activateAbility(Game game, Tower t, Vec target) {
        AbilityDef a = t.getAbility();
        boolean all = a.p("allTowers", 0) > 0;
        for (Tower o : game.getTowerManager().getTowers()) {
            if (!all && o.getType().faction != Faction.MILITARY) continue;
            // rateMult: an uncapped self buff (x3 stays x3); rateBonus: the capped tower-buff path
            if (a.has("rateMult")) o.addSelfBuff(AUTO_REFACTOR, a.p("rateMult"), 1, a.p("duration"));
            else o.addTimedBuff(BuffStat.RATE, t.getType(), a.p("rateBonus"), a.p("duration"));
        }
        return true;
    }
}
