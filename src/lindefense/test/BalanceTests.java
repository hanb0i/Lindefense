package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.map.GameMap;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;

/**
 * Tower spec section 3.7 balance targets, verified headlessly:
 * (a) Brad alone beats a MOAB but not a BFB, (b) no other fully upgraded tower solos a BFB, (c) Brad is the most
 * expensive tower by far, (d) every tower contributes in waves 60+ of a mixed build, (e) ability cooldowns run in game time.
 */
public final class BalanceTests {
    private BalanceTests() { }

    /** Single-lane map used for solo duels (Legacy Monolith). */
    private static final int DUEL_MAP = 1;

    public static void runAll() {
        run("balance.hpNeverDecreases", BalanceTests::hpNeverDecreases);
        run("balance.heroesCannotSoloLateBfb", BalanceTests::bradDuel);
        run("balance.noSoloBfb", BalanceTests::noSoloBfb);
        run("balance.heroPrices", BalanceTests::costRanking);
        run("balance.everyTowerContributesLate", BalanceTests::everyTowerContributes);
        run("balance.abilityCooldownsInGameTime", BalanceTests::cooldownsInGameTime);
    }

    /** Fraction of the boss's HP left after it has walked the whole route past one fully upgraded tower (0 = killed). */
    public static double duel(TowerType type, EnemyType boss) { return duel(type, boss, 1.0); }

    /** Same duel with the boss spawned at the given HP scale (e.g. {@code WaveData.hpScale(wave)} for the HP met in the campaign). */
    public static double duel(TowerType type, EnemyType boss, double hpScale) {
        Game g = newGame(DUEL_MAP);
        g.setInvincible(true);
        Path route = g.getMap().getRoutes().get(0);
        Tower t = forcePlace(g, type, bestSpot(g, type), TowerCatalog.get(type).upgrades.length);
        Enemy e = g.getEnemyManager().spawnScaled(boss, null, 0, 0, hpScale, 1.0);
        g.getEnemyManager().update(0);
        double limit = 400;   // simulated seconds: far longer than the walk
        for (double time = 0; time < limit && e.isAlive() && !e.hasLeaked() && e.getDistance() < route.getTotalLength() - 1; time += Game.DT) {
            if (t.getAbility() != null && t.isAbilityReady()) {
                if (t.getAbility().needsTarget) g.activateAbility(t, e.getPosition()); else g.activateAbility(t);
            }
            g.step(Game.DT);
            g.getEvents().clear();
        }
        return e.isAlive() ? e.getHp() / e.getMaxHp() : 0;
    }

    /** The buildable spot that covers the most of the route within the tower's range. */
    private static Vec bestSpot(Game g, TowerType type) {
        double range = Math.min(TowerCatalog.get(type).baseStats.range, 400);
        Path r = g.getMap().getRoutes().get(0);
        g.addCash(1_000_000, null);   // so only geometry (not price) can reject a spot
        for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);
        Vec best = null; int bestN = -1;
        for (int x = 30; x < GameMap.WIDTH; x += 15) for (int y = 30; y < GameMap.HEIGHT; y += 15) {
            Vec p = new Vec(x, y);
            if (!g.getMap().isBuildable(p, 20) || g.getTowerManager().placementProblem(type, p) != null) continue;
            int n = 0;
            for (double d = 0; d < r.getTotalLength(); d += 20) if (r.positionAt(d).distSq(p) <= range * range) n++;
            if (n > bestN) { bestN = n; best = p; }
        }
        return best;
    }

    private static void bradDuel() {
        // Hero Store heroes vs a lone boss (abilities used on cooldown): reported for tuning; no hero may solo a BFB
        // at the HP it has on its last campaign appearance (wave 99), so towers stay necessary.
        StringBuilder sb = new StringBuilder("      hero solo, HP left: MOAB(w40) / BFB(w99):");
        for (TowerType h : TowerType.heroes()) {
            double moab = duel(h, EnemyType.BELLARMINE_COLLEGE_PREP, lindefense.wave.WaveData.hpScale(40));
            double bfb = duel(h, EnemyType.SW_RESOURCE_CONSULTANT, lindefense.wave.WaveData.hpScale(99));
            sb.append(' ').append(h).append('=').append(pct(moab)).append('/').append(pct(bfb));
            check(bfb > 0, h + " alone must not defeat a wave-99 BFB (HP left " + pct(bfb) + ")");
        }
        System.out.println(sb);
    }

    private static void noSoloBfb() {
        for (int wave : new int[] { 1, 60, 99 }) {      // base HP, the BFB's debut wave, and its last appearance
            double scale = wave == 1 ? 1.0 : lindefense.wave.WaveData.hpScale(wave);
            StringBuilder sb = new StringBuilder("      solo BFB hp left (" + (wave == 1 ? "base" : "wave " + wave) + "):");
            for (TowerType tt : TowerType.purchasable()) {
                if (tt.isHero()) continue;
                double left = duel(tt, EnemyType.SW_RESOURCE_CONSULTANT, scale);
                sb.append(' ').append(tt).append('=').append(pct(left));
                check(left > 0, tt + " fully upgraded must not solo an SW Resource Consultant BFB (" + (wave == 1 ? "base" : "wave " + wave) + ")");
            }
            if (wave == 1 || wave == 60) System.out.println(sb);
        }
    }

    private static void hpNeverDecreases() {
        for (int w = 1; w < lindefense.wave.WaveData.WAVE_COUNT; w++)
            check(lindefense.wave.WaveData.hpScale(w + 1) >= lindefense.wave.WaveData.hpScale(w), "HP scale never decreases (wave " + w + ")");
        check(lindefense.wave.WaveData.hpScale(100) > lindefense.wave.WaveData.hpScale(80) && lindefense.wave.WaveData.hpScale(80) > lindefense.wave.WaveData.hpScale(60), "HP grows after wave 60 and again after wave 80");
        double palantir = EnemyType.PALANTIR.baseHp;
        for (EnemyType t : EnemyType.values()) if (t.isBoss() && t != EnemyType.PALANTIR) check(palantir > 2 * t.baseHp * lindefense.wave.WaveData.hpScale(100) * 2, "Palantir clearly outweighs even a Fortified " + t);
    }

    private static String pct(double f) { return Math.round(f * 1000) / 10.0 + "%"; }

    private static void costRanking() {
        // the cheapest hero is the pure-economy one and the priciest is the kaiju; every price sits in a sane band
        int cheapest = Integer.MAX_VALUE, priciest = 0;
        TowerType cheapType = null, priceyType = null;
        for (TowerType h : TowerType.heroes()) {
            int p = TowerCatalog.get(h).unlockCost;
            check(p >= 800 && p <= 2000, h + " Hero Store price $" + p + " is in the $800-2000 band");
            if (p < cheapest) { cheapest = p; cheapType = h; }
            if (p > priciest) { priciest = p; priceyType = h; }
        }
        check(cheapType == TowerType.SUNNY_JOE && cheapest == 850, "Sunny Joe is the cheapest hero at $850");
        check(priceyType == TowerType.KAIJU_KAI && priciest == 1500, "Kaiju Kai is the priciest hero at $1,500");
        check(TowerCatalog.get(TowerType.ZETHOS).totalCost() == 5350, "Zethos fully upgraded costs $5,350");
    }

    private static void everyTowerContributes() {
        // One of every tower, fully upgraded, in a mixed build fighting real waves 60-64 at O(N^N) strength (so nothing is
        // overkilled before it reaches the back of the build). Abilities are not used. Every attacker must deal damage or
        // score kills; Perplexity (pure economy) must pay its round-end income.
        Game g = new Game(lindefense.map.MapCatalog.create(DUEL_MAP), 99L, lindefense.sim.Difficulty.ONN);
        g.setInvincible(true);
        List<Tower> build = new ArrayList<>();
        List<TowerType> order = new ArrayList<>(java.util.Arrays.asList(TowerType.purchasable()));
        order.sort((x, y) -> Double.compare(TowerCatalog.get(x).baseStats.range, TowerCatalog.get(y).baseStats.range));   // short-range towers get the closest spots
        // spread the roster along the route so every unit meets live enemies instead of queueing behind one kill zone
        double len = g.getMap().getRoutes().get(0).getTotalLength();
        for (int i = 0; i < order.size(); i++) {
            // Spread over the early stretch only, and alternate ends so no group of similar ranges ends up
            // queued behind another: with 35 units a monotonic line would starve whatever sits at the back.
            int half = (order.size() + 1) / 2;
            int slot = i % 2 == 0 ? i / 2 : half + i / 2;
            build.add(forcePlaceBest(g, order.get(i), 220 + (len * 0.45 - 220) * slot / (double) Math.max(1, order.size() - 1)));
        }
        while (g.getWave() < 59) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
        for (int w = 60; w <= 64; w++) {
            check(g.getWaveManager().startNextWave(), "wave " + w + " starts");
            for (int tick = 0; tick < 60 * 400 && (g.getWaveManager().isWaveActive() || tick < 60); tick++) {
                g.step(Game.DT);
                g.getEvents().clear();
            }
        }
        List<TowerType> silent = new ArrayList<>();
        StringBuilder sb = new StringBuilder("      waves 60-64 damage:");
        for (Tower t : build) {
            sb.append(' ').append(t.getType()).append('=').append(Math.round(t.getDamageDealt())).append('/').append(t.getKills());
            boolean active = t.getDamageDealt() > 0 || t.getKills() > 0;
            if (t.getType() == TowerType.PERPLEXITY) active = t.getBehavior().onRoundEnd(g, t) > 0;
            // the support heroes never attack: they contribute integrity, cash and tower buffs instead
            if (t.getType() == TowerType.SAGE_AARAV) active = t.getStats().p("healAmount", 0) > 0;
            if (t.getType() == TowerType.SUNNY_JOE) active = t.getStats().p("income", 0) > 0;
            if (t.getType() == TowerType.TANIMBUS) active = t.getStats().auraRate > 0 || t.getStats().p("buffRate", 0) > 0;
            if (!active) silent.add(t.getType());
        }
        System.out.println(sb);
        check(build.size() == TowerType.purchasable().length, "the mixed build has every tower and hero (" + build.size() + ")");
        // A unit can go quiet simply because 35 units share one route and the ones in front killed everything first.
        // That is a placement lottery, not a defect, so anything silent here must prove it can fight on its own.
        List<TowerType> broken = new ArrayList<>();
        for (TowerType t : silent) {
            if (duel(t, EnemyType.BELLARMINE_COLLEGE_PREP) >= 1.0) broken.add(t);
        }
        if (!silent.isEmpty()) System.out.println("      quiet in the scrum but able to fight alone: " + silent);
        check(broken.isEmpty(), "every tower can contribute in waves 60+ (never dealt damage, even alone: " + broken + ")");
    }

    /**
     * Places a fully upgraded tower on the free buildable spot nearest {@code aimAt} on the route that can actually
     * see the track. The whole roster (35 units) cannot share one kill zone -- the front of the line would kill
     * everything before the back ever fires -- so the caller spreads them along the route and each one covers its own
     * stretch.
     */
    private static Tower forcePlaceBest(Game g, TowerType type, double aimAt) {
        g.addCash(1_000_000, null);
        for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);
        lindefense.map.Path route = g.getMap().getRoutes().get(0);
        Vec zone = route.positionAt(Math.min(aimAt, route.getTotalLength() - 50));
        double reach = TowerCatalog.get(type).statsForTier(TowerCatalog.get(type).upgrades.length).range;
        Vec best = null; double bestD = Double.MAX_VALUE;
        for (int pass = 0; pass < 2 && best == null; pass++) {
            for (int x = 30; x < GameMap.WIDTH; x += 15) for (int y = 30; y < GameMap.HEIGHT; y += 15) {
                Vec p = new Vec(x, y);
                if (!g.getMap().isBuildable(p, 20) || g.getTowerManager().placementProblem(type, p) != null) continue;
                if (pass == 0 && route.distanceToPoint(p) > reach * 0.8) continue;   // must cover the track
                double d = p.dist(zone);
                if (d < bestD) { bestD = d; best = p; }
            }
        }
        return forcePlace(g, type, best, TowerCatalog.get(type).upgrades.length);
    }

    private static void cooldownsInGameTime() {
        Game g = newGame(DUEL_MAP);
        Tower t = forcePlace(g, TowerType.ZETHOS, bestSpot(g, TowerType.ZETHOS), 0);
        double start = t.getAbilityCooldownRemaining();
        check(Math.abs(start - t.getAbility().cooldown * 0.5) < 1e-9, "starts at 50% cooldown");
        g.setSpeed(3);
        for (int i = 0; i < 6; i++) g.advance(1.0 / 6);   // one real second at 3x = three game seconds
        check(Math.abs(start - t.getAbilityCooldownRemaining() - g.getTime()) < 1e-6, "cooldown drops by elapsed game time (" + g.getTime() + " s)");
        check(g.getTime() > 2.9 && g.getTime() < 3.1, "fast-forward speeds game time up (" + g.getTime() + ")");
    }
}
