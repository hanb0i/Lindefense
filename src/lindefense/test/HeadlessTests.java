package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.map.GameMap;
import lindefense.map.HallucinationCanyon;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.map.SingularityCore;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Shop;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Headless verification of the section-16 checklist against the real game
 * logic. Run with {@code java -cp build lindefense.test.HeadlessTests}.
 * Exits with status 1 if any check fails.
 */
public final class HeadlessTests {
    public static void main(String[] args) {
        run("catalogIntegrity", HeadlessTests::catalogIntegrity);
        run("purchaseUpgradeSell", HeadlessTests::purchaseUpgradeSell);
        run("placementRules", HeadlessTests::placementRules);
        run("rewardsAndNoDuplicateKills", HeadlessTests::rewardsAndNoDuplicateKills);
        run("livesLossOnLeak", HeadlessTests::livesLossOnLeak);
        run("targetingPriorities", HeadlessTests::targetingPriorities);
        run("camoDetection", HeadlessTests::camoDetection);
        run("fortifiedAndRegrow", HeadlessTests::fortifiedAndRegrow);
        run("splitterChildren", HeadlessTests::splitterChildren);
        run("bossChildren", HeadlessTests::bossChildren);
        run("enemyMechanics", HeadlessTests::enemyMechanics);
        run("projectileCollision", HeadlessTests::projectileCollision);
        run("waveCompositions", HeadlessTests::waveCompositions);
        run("waveSpawningMatchesData", HeadlessTests::waveSpawningMatchesData);
        run("palantirPhasesAndSurveillance", HeadlessTests::palantirPhasesAndSurveillance);
        run("abilityCooldowns", HeadlessTests::abilityCooldowns);
        run("mapsTraversable", HeadlessTests::mapsTraversable);
        run("mapMechanics", HeadlessTests::mapMechanics);
        run("adminMode", HeadlessTests::adminMode);
        run("newMaps", HeadlessTests::newMaps);
        run("winAndLose", HeadlessTests::winAndLose);
        run("shopLayout", HeadlessTests::shopLayout);
        run("stressLateWaves", HeadlessTests::stressLateWaves);
        run("stressMaxedRoster", HeadlessTests::stressMaxedRoster);

        GlobalRulesTests.runAll();
        EnginePrimitiveTests.runAll();
        HeroPrimaryMilitaryTests.runAll();
        MagicSupportTests.runAll();
        HeroStoreTests.runAll();
        AbilityUnlockTests.runAll();
        GraphicsTests.runAll();
        TitanTests.runAll();
        InjectionTests.runAll();   // PROMPT INJECTION + Palantir phase abilities + window seal
        BalanceTests.runAll();
        ConsistencyTests.runAll();
        VarianceTests.runAll();   // PATCH NOTES / BREAKING NEWS / run seeds
        ReverseModeTests.runAll();   // REVERSE MODE: Adversarial Training (attacker economy, uplink, defender AI)

        run("restartResetsLevel", HeadlessTests::restartResetsLevel);
        run("assetNamesMatchExactly", () -> { for (String f : AssetTests.run()) check(false, f); check(AssetTests.checkCount() > 40, "asset suite ran (" + AssetTests.checkCount() + " checks)"); });
        // DIFFICULTY HOOK: Difficulty Growth suite (see DifficultyTests)
        run("difficultyGrowth", () -> { for (String f : DifficultyTests.run()) check(false, f); check(DifficultyTests.checkCount() > 100, "difficulty suite ran (" + DifficultyTests.checkCount() + " checks)"); });

        // AUDIO: sound / music system suite (headless, never opens a device)
        run("audioSystem", () -> { for (String f : AudioTests.run()) check(false, f); check(AudioTests.checkCount() > 30, "audio suite ran (" + AudioTests.checkCount() + " checks)"); });
        VolumeTests.runAll();   // AUDIO: volume levels and the Slider component

        System.out.println();
        System.out.println("Passed: " + passed() + "  Failed: " + failed());
        for (String f : failures()) System.out.println("  FAIL " + f);
        System.exit(failed() == 0 ? 0 : 1);
    }

    /** RESTART builds a fresh game on the same map and difficulty (wave, cash, lives, towers, enemies all reset). */
    private static void restartResetsLevel() {
        for (int map = 0; map < lindefense.map.MapCatalog.MAP_COUNT; map++) {
            for (lindefense.sim.Difficulty d : lindefense.sim.Difficulty.values()) {
                Game g = new Game(MapCatalog.create(map), 7, d);
                g.addCash(4000, null);
                g.placeTower(TowerType.GPT, buildableNear(g, new Vec(400, 250), 300));
                g.startNextWave();
                g.run(600);
                g.loseLives(3, g.getEnemyManager().getEnemies().isEmpty() ? g.getEnemyManager().spawn(lindefense.enemy.EnemyType.STATIC_ARRAY, null, 0, 10) : g.getEnemyManager().getEnemies().get(0));
                Game f = Game.freshCopy(g);
                String tag = " (map " + map + ", " + d + ")";
                check(f != g && f.getMap() != g.getMap(), "fresh game has its own map instance" + tag);
                check(f.getMap().getName().equals(g.getMap().getName()) && f.getDifficulty() == g.getDifficulty(), "same map and difficulty" + tag);
                check(f.getWave() == 0 && f.getLastCompletedWave() == 0 && f.getTick() == 0, "wave and clock reset" + tag);
                check(f.getCash() == d.startCash(Game.START_CASH) && f.getLives() == d.startLives(Game.START_LIVES), "cash and lives reset" + tag);
                check(f.getTowerManager().getTowers().isEmpty() && f.getEnemyManager().getEnemies().isEmpty() && f.getState() == Game.State.PLAYING && !f.isPaused(), "no towers, enemies or pause carried over" + tag);
            }
        }
    }

    private static Game newGame(int mapIdx) { return new Game(MapCatalog.create(mapIdx), 42); }

    /** Modifier equality ignoring innate camo (Lockheed Martin is always camo). */
    private static boolean sameMods(Enemy e, SpawnGroup gr) {
        EnumSet<Modifier> m = EnumSet.copyOf(e.getModifiers());
        if (e.getType().hasInnateCamo() && !gr.modifiers.contains(Modifier.CAMO)) m.remove(Modifier.CAMO);
        return m.equals(gr.modifiers);
    }

    // ------------------------------------------------------------------ tests
    private static void catalogIntegrity() {
        TowerType[] p = TowerType.purchasable();
        check(p.length == 36, "36 placeable units (18 heroes + 18 shop towers), got " + p.length);
        check(TowerType.heroes().length == 18 && TowerType.shopTowers().length == 18, "18 Hero Store heroes, 18 shop towers");
        int heroes = 0;
        for (TowerType t : p) {
            TowerDef d = TowerCatalog.get(t);
            check(d != null, "def for " + t);
            int ups = t == TowerType.ZETHOS ? TowerCatalog.ZETHOS_UPGRADES : TowerCatalog.STANDARD_UPGRADES;
            check(d.upgrades.length == ups, t + " has exactly " + ups + " upgrades");
            if (TowerCatalog.hasActiveAbility(t)) check(d.ability != null && d.ability.cooldown > 0, t + " has ability with cooldown");
            else check(d.ability == null, t + " (original shop tower) has no special ability");
            check(t.isHero() ? d.baseCost == 0 && d.unlockCost > 0 : d.baseCost > 0 && d.unlockCost == 0, t + " has cost (heroes: unlock price, free deploy)");
            for (int i = 0; i <= ups; i++) check(d.statsForTier(i) != null, t + " tier " + i + " stats");
            for (int i = 0; i < ups; i++) check(d.upgrades[i].name.equals(d.tierLabels[i + 1]), t + " upgrade name is the tier label");
            if (t.isHero()) heroes++;
            check(d.tierLabels.length == ups + 1, t + " " + (ups + 1) + " tier labels");
            check(d.subtitle != null && !d.subtitle.isEmpty(), t + " has a nickname subtitle");
        }
        check(heroes == 18, "18 heroes");
        int species = 0;
        for (EnemyType e : EnemyType.values()) if (e.isSpawnableSpecies() && !e.isBoss()) species++;
        check(species == 16, "16 standard enemy species, got " + species);
        int bosses = 0;
        for (EnemyType e : EnemyType.values()) if (e.isBoss()) bosses++;
        check(bosses == 5, "5 bosses");
    }

    private static void purchaseUpgradeSell() {
        Game g = newGame(0);
        Vec p = buildableNear(g, new Vec(400, 250), 200);
        double cash0 = g.getCash();
        Tower t = g.placeTower(TowerType.GPT, p);
        check(t != null, "placed GPT");
        check(g.getCash() == cash0 - 500, "cash deducted 500, cash=" + g.getCash());
        check(t.getTier() == 0, "tier 0");
        g.addCash(5000, null);
        double c = g.getCash();
        TowerDef gptDef = TowerCatalog.get(TowerType.GPT);
        check(g.upgradeTower(t) && t.getTier() == 1 && g.getCash() == c - gptDef.upgrades[0].cost, "upgrade 1 costs " + gptDef.upgrades[0].cost);
        check(t.getTierLabel().equals("GPT-6 Luna"), "tier label is the model name");
        check(g.upgradeTower(t) && t.getTier() == 2, "upgrade 2");
        check(g.upgradeTower(t) && t.getTier() == 3 && t.isMaxed(), "upgrade 3 (maxed)");
        check(!g.upgradeTower(t) && t.getTier() == 3, "no 4th upgrade");
        int invested = 500 + gptDef.upgrades[0].cost + gptDef.upgrades[1].cost + gptDef.upgrades[2].cost;
        check(t.getInvestedCost() == invested, "invested " + invested);
        int expectedRefund = (int) Math.floor(invested * 0.7);
        check(Shop.sellValue(t) == expectedRefund, "sell value 70%");
        double before = g.getCash();
        int refund = g.sellTower(t);
        check(refund == expectedRefund && g.getCash() == before + expectedRefund, "refund applied");
        check(g.getTowerManager().getTowers().isEmpty(), "tower removed");
        // Not enough cash
        Game g2 = newGame(0);
        check(g2.placeTower(TowerType.KAIJU_KAI, p) == null, "a locked hero cannot be placed");
        check(!g2.purchaseHero(TowerType.KAIJU_KAI), "cannot afford Kaiju Kai's $1,500 unlock at start");
        check(g2.getCash() == Game.START_CASH, "cash unchanged after failed purchase");
        // Every tower can be placed and upgraded through its whole path (and never past it); heroes after unlocking
        Game g3 = newGame(0);
        g3.setHeroLimit(Integer.MAX_VALUE);   // every unit in one game; the 3-hero cap is tested in heroes.heroLimit
        g3.addCash(1_000_000, null);
        int i = 0;
        for (TowerType type : TowerType.purchasable()) {
            Vec q = new Vec(80 + (i % 10) * 100, 60 + (i / 10) * 60);
            i++;
            Vec b = buildableNear(g3, q, 150);
            if (type.isHero()) {
                check(g3.placeTower(type, b) == null, type + " locked: cannot be placed");
                check(g3.purchaseHero(type) && !g3.purchaseHero(type), type + " bought once (no duplicate purchase)");
            }
            Tower tt = g3.placeTower(type, b);
            check(tt != null, "place " + type);
            if (tt == null) continue;
            int ups = TowerCatalog.get(type).upgrades.length;
            for (int k = 0; k < ups; k++) check(g3.upgradeTower(tt), type + " upgrade " + (k + 1));
            check(!g3.upgradeTower(tt), type + " no upgrade past tier " + ups);
            check(tt.getInvestedCost() == TowerCatalog.get(type).totalCost(), type + " invested matches");
            check(tt.getStats() != null && tt.isMaxed(), type + " T3 stats");
        }
    }

    private static void placementRules() {
        Game g = newGame(0);
        g.addCash(10000, null);
        Path r = g.getMap().getRoutes().get(0);
        Vec onTrack = r.positionAt(300);
        check(g.getTowerManager().placementProblem(TowerType.GPT, onTrack) != null, "cannot build on track");
        check(g.getTowerManager().placementProblem(TowerType.GPT, new Vec(-50, 100)) != null, "cannot build outside");
        check(g.getTowerManager().placementProblem(TowerType.GPT, new Vec(980, 60)) != null, "cannot build on obstacle (CPU chip)");
        Vec ok = buildableNear(g, new Vec(400, 250), 200);
        Tower t = g.placeTower(TowerType.GPT, ok);
        check(t != null, "valid placement");
        check(g.getTowerManager().placementProblem(TowerType.CLAUDE, ok.add(new Vec(10, 0))) != null, "cannot overlap");
        check(g.getTowerManager().towerAt(ok) == t, "towerAt finds tower");
        // Singularity arena
        Game g4 = newGame(3);
        check(!g4.getMap().isBuildable(new Vec(20, 20), 20), "outside arena not buildable");
        check(!g4.getMap().isBuildable(new Vec(600, 450), 20), "vortex not buildable");
    }

    private static void rewardsAndNoDuplicateKills() {
        Game g = newGame(0);
        double c0 = g.getCash();
        Enemy sa = spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 100);
        killOutright(g, sa);
        double rs = g.getRewardScale();   // wave-1 reward multiplier (see WaveData.rewardScale)
        check(g.getCash() == c0 + Math.round(3 * rs), "Static Array reward 3 x " + rs + ", got " + (g.getCash() - c0));
        check(!sa.isAlive(), "dead");
        List<Enemy> live = g.getEnemyManager().getEnemies();
        check(live.size() == 1 && live.get(0).getType() == EnemyType.PRIMITIVE_VARIABLE, "child primitive spawned");
        Enemy child = live.get(0);
        check(Math.abs(child.getDistance() - 100) < 1, "child at parent position");
        double c1 = g.getCash();
        g.getCombat().applyHit(sa, new HitSpec(100, DamageType.TRUE), null, 1, 0);
        g.getEnemyManager().kill(sa);
        g.getEnemyManager().update(0);
        check(g.getCash() == c1, "no duplicate reward for re-killing");
        killOutright(g, child);
        check(g.getCash() == c1 + Math.round(2 * rs), "child reward 2 x " + rs);
        // leak pays nothing
        double c2 = g.getCash();
        Enemy leaker = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, g.getMap().getRoutes().get(0).getTotalLength() - 1);
        g.run(5);
        check(leaker.hasLeaked() && g.getCash() == c2, "leaked enemy pays nothing");
        // reward scaling later
        check(WaveData.rewardScale(90) < WaveData.rewardScale(10) && WaveData.rewardScale(90) < WaveData.rewardScale(70), "reward scale tapers off in the last 20 waves");
    }

    private static void livesLossOnLeak() {
        Game g = newGame(1);
        double len = g.getMap().getRoutes().get(0).getTotalLength();
        spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, len - 2);
        g.run(10);
        check(g.getLives() == 99, "primitive costs 1 life, lives=" + g.getLives());
        spawnAt(g, EnemyType.TIMSORT, null, 0, len - 2);
        g.run(10);
        check(g.getLives() == 99 - 8, "TimSort costs 8 lives, lives=" + g.getLives());
        spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, len - 2);
        g.run(20);
        check(g.getLives() == 91 - 30, "MOAB costs 30 lives, lives=" + g.getLives());
        check(g.getEnemyManager().getEnemies().isEmpty(), "leaked enemies removed");
    }

    private static void targetingPriorities() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Path r = g.getMap().getRoutes().get(0);
        Vec p = buildableNear(g, r.positionAt(400).add(new Vec(0, -60)), 80);
        Tower t = forcePlace(g, TowerType.GPT, p, 1); // range 210
        Enemy a = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, 330);   // last
        Enemy b = spawnAt(g, EnemyType.MERGE_SORT, null, 0, 400);           // strongest, closest
        Enemy c = spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 470);         // first
        t.setTargeting(Targeting.FIRST);
        check(g.getCombat().acquireTargets(t, 1).get(0) == c, "FIRST = closest to exit");
        t.setTargeting(Targeting.LAST);
        check(g.getCombat().acquireTargets(t, 1).get(0) == a, "LAST = closest to entrance");
        t.setTargeting(Targeting.STRONGEST);
        check(g.getCombat().acquireTargets(t, 1).get(0) == b, "STRONGEST = most HP");
        t.setTargeting(Targeting.WEAKEST);
        Enemy w = g.getCombat().acquireTargets(t, 1).get(0);
        check(w == a, "WEAKEST = least HP (" + w + ")");
        t.setTargeting(Targeting.CLOSEST);
        check(g.getCombat().acquireTargets(t, 1).get(0) == b, "CLOSEST = nearest to tower");
        check(g.getCombat().acquireTargets(t, 3).size() == 3, "multi-target returns 3");
        // Out of range enemy is excluded
        spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, 1500);
        check(g.getCombat().acquireTargets(t, 10).size() == 3, "out-of-range excluded");
    }

    private static void camoDetection() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Path r = g.getMap().getRoutes().get(0);
        Vec p = buildableNear(g, r.positionAt(400).add(new Vec(0, -60)), 80);
        Tower gpt = forcePlace(g, TowerType.GPT, p, 0);
        Enemy camo = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, EnumSet.of(Modifier.CAMO), 0, 400);
        check(g.getCombat().acquireTargets(gpt, 1).isEmpty(), "GPT cannot target camo");
        g.run(60);
        check(camo.getHp() == camo.getMaxHp(), "camo not damaged by GPT");
        Vec p2 = buildableNear(g, p.add(new Vec(60, 0)), 100);
        Tower perp = forcePlace(g, TowerType.PERPLEXITY, p2, 0);
        check(!g.getCombat().acquireTargets(perp, 1).isEmpty(), "Perplexity targets camo");
        g.getTowerManager().recomputeAuras();
        check(gpt.canSeeCamo(), "GPT gains detection from Perplexity aura");
        check(!g.getCombat().acquireTargets(gpt, 1).isEmpty(), "GPT can now target camo");
        g.sellTower(perp);
        check(!gpt.canSeeCamo(), "detection lost after selling Perplexity");
        camo.applyStatus(StatusEffect.Kind.REVEALED, 1, 5);
        check(!g.getCombat().acquireTargets(gpt, 1).isEmpty(), "revealed camo is targetable");
        // Lockheed is innately camo
        Enemy ddt = spawnAt(g, EnemyType.LOCKHEED_MARTIN, null, 0, 100);
        check(ddt.isCamo(), "Lockheed innate camo");
        // Projectiles from non-detecting towers pass through camo
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(0);
        Tower gpt2 = forcePlace(g2, TowerType.GPT, p, 0);
        spawnAt(g2, EnemyType.PRIMITIVE_VARIABLE, EnumSet.of(Modifier.CAMO), 0, 400);
        Enemy plain = spawnAt(g2, EnemyType.STATIC_ARRAY, null, 0, 420);
        g2.run(120);
        check(plain.getHp() < plain.getMaxHp() || !plain.isAlive(), "plain enemy hit while camo ignored");
        check(gpt2.getDamageDealt() > 0, "tower dealt damage");
    }

    private static void fortifiedAndRegrow() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Enemy f = spawnAt(g, EnemyType.HEAP_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 100);
        check(f.getMaxHp() == 16, "fortified heap has 16 HP, got " + f.getMaxHp());
        Enemy n = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 100);
        check(n.getMaxHp() == 8, "normal heap 8 HP");
        Enemy r = spawnAt(g, EnemyType.MERGE_SORT, EnumSet.of(Modifier.REGROW), 0, 100);
        g.getCombat().applyHit(r, new HitSpec(3, DamageType.TRUE), null, 1, 0);
        check(r.getHp() == 3, "regrow enemy damaged to 3");
        g.run((int) (Enemy.REGROW_INTERVAL / Game.DT) + 2);
        check(r.getHp() == 4, "regrow restored 1 HP after interval, hp=" + r.getHp());
        g.run((int) (Enemy.REGROW_INTERVAL / Game.DT * 5));
        check(r.getHp() == 6, "regrow caps at max");
        // Fortified strip (Qwen)
        Enemy ff = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 100);
        check(ff.getMaxHp() == 14, "fortified quick 14");
        check(ff.stripFortified() && !ff.isFortified() && ff.getHp() <= 7, "strip fortified halves");
        // Lead-type immunity to Sharp, and the "can damage Lead" flag
        Enemy heap = spawnAt(g, EnemyType.HEAP_SORT, null, 0, 100);
        double dealt = g.getCombat().applyHit(heap, new HitSpec(3, DamageType.SHARP), null, 1, 0);
        check(dealt == 0, "heap (Lead-type) immune to Sharp");
        HitSpec lead = new HitSpec(3, DamageType.SHARP); lead.ignoresResistance = true;
        check(g.getCombat().applyHit(heap, lead, null, 1, 0) == 3, "Sharp that can damage Lead hurts heap");
        // Armour
        Enemy moab = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 100);
        double d1 = g.getCombat().applyHit(moab, new HitSpec(100, DamageType.ENERGY), null, 1, 0);
        check(Math.abs(d1 - 75) < 0.01, "MOAB armour 25%: 100 -> 75, got " + d1);
        HitSpec ap = new HitSpec(100, DamageType.ENERGY); ap.armorPierce = 1;
        check(Math.abs(g.getCombat().applyHit(moab, ap, null, 1, 0) - 100) < 0.01, "armour piercing ignores armour");
        Enemy bfb = spawnAt(g, EnemyType.SW_RESOURCE_CONSULTANT, null, 0, 100);
        double weak = g.getCombat().applyHit(bfb, new HitSpec(2, DamageType.ENERGY), null, 1, 0);
        check(Math.abs(weak - 2 * 0.6 * 0.5) < 0.01, "BFB halves weak hits, got " + weak);
    }

    private static void splitterChildren() {
        Object[][] cases = {
            { EnemyType.STATIC_ARRAY, new EnemyType[] { EnemyType.PRIMITIVE_VARIABLE }, new int[] { 1 } },
            { EnemyType.DYNAMIC_ARRAY, new EnemyType[] { EnemyType.STATIC_ARRAY }, new int[] { 1 } },
            { EnemyType.MERGE_SORT, new EnemyType[] { EnemyType.MERGE_RUN }, new int[] { 2 } },
            { EnemyType.QUICK_SORT, new EnemyType[] { EnemyType.QUICK_PARTITION }, new int[] { 2 } },
            { EnemyType.COUNTING_SORT, new EnemyType[] { EnemyType.PRIMITIVE_VARIABLE }, new int[] { 4 } },
            { EnemyType.TIMSORT, new EnemyType[] { EnemyType.MERGE_SORT, EnemyType.INSERTION_SORT }, new int[] { 1, 1 } },
        };
        for (Object[] c : cases) {
            Game g = newGame(0);
            g.setGlobalEnemySpeedMultiplier(0);
            EnemyType parent = (EnemyType) c[0];
            Enemy e = spawnAt(g, parent, EnumSet.of(Modifier.CAMO, Modifier.REGROW, Modifier.FORTIFIED), 0, 300);
            killOutright(g, e);
            EnemyType[] types = (EnemyType[]) c[1];
            int[] counts = (int[]) c[2];
            for (int i = 0; i < types.length; i++) {
                int n = g.getEnemyManager().countOfType(types[i]);
                check(n == counts[i], parent + " -> " + counts[i] + " x " + types[i] + ", got " + n);
            }
            int total = 0; for (int k : counts) total += k;
            check(g.getEnemyManager().getEnemies().size() == total, parent + " total children " + total);
            for (Enemy ch : g.getEnemyManager().getEnemies()) {
                check(ch.getMaxHp() == ch.getType().baseHp, parent + " child HP = base (" + ch.getType() + " " + ch.getMaxHp() + ")");
                check(ch.isCamo() && ch.isRegrow() && !ch.isFortified(), parent + " child inherits camo+regrow, not fortified");
                check(Math.abs(ch.getDistance() - 300) <= 6 * total, parent + " child near parent position");
            }
        }
        check(EnemyType.MERGE_RUN.baseHp == 2 && EnemyType.QUICK_PARTITION.baseHp == 3, "Merge Run 2 HP, Quick Partition 3 HP");
        // Non-infinite recursion: fully resolve a TimSort chain
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        spawnAt(g, EnemyType.TIMSORT, null, 0, 300);
        int guard = 0;
        while (!g.getEnemyManager().getEnemies().isEmpty() && guard++ < 50) {
            for (Enemy e : new ArrayList<>(g.getEnemyManager().getEnemies())) g.getCombat().applyHit(e, new HitSpec(1e9, DamageType.TRUE), null, 1, 0);
            g.getEnemyManager().update(0);
        }
        check(guard < 50, "TimSort chain terminates");
        check(g.getEnemyManager().getTotalKilled() == 1 + 2 + 2, "TimSort chain = TimSort + Merge + Insertion + 2 Merge Runs = 5 kills, got " + g.getEnemyManager().getTotalKilled());
    }

    private static void bossChildren() {
        Object[][] cases = {
            { EnemyType.BELLARMINE_COLLEGE_PREP, EnemyType.QUICK_SORT, 4 },
            { EnemyType.SW_RESOURCE_CONSULTANT, EnemyType.BELLARMINE_COLLEGE_PREP, 3 },
            { EnemyType.THREE_COM, EnemyType.SW_RESOURCE_CONSULTANT, 3 },
            { EnemyType.LOCKHEED_MARTIN, EnemyType.QUICK_SORT, 4 },
        };
        for (Object[] c : cases) {
            Game g = newGame(1);
            g.setGlobalEnemySpeedMultiplier(0);
            Enemy b = spawnAt(g, (EnemyType) c[0], EnumSet.of(Modifier.FORTIFIED), 0, 500);
            check(b instanceof Boss, c[0] + " is a Boss");
            double cash = g.getCash();
            killOutright(g, b);
            int n = g.getEnemyManager().countOfType((EnemyType) c[1]);
            check(n == (Integer) c[2], c[0] + " releases " + c[2] + " " + c[1] + ", got " + n);
            check(g.getCash() == cash + Math.round(((EnemyType) c[0]).reward * g.getRewardScale()), c[0] + " reward paid once");
            for (Enemy ch : g.getEnemyManager().getEnemies()) {
                check(ch.isFortified(), c[0] + " children inherit Fortified from boss");
                if (c[0] == EnemyType.LOCKHEED_MARTIN) check(ch.isCamo(), "Lockheed children camo");
            }
        }
        Game g = newGame(1);
        g.setGlobalEnemySpeedMultiplier(0);
        Enemy pal = spawnAt(g, EnemyType.PALANTIR, null, 0, 500);
        killOutright(g, pal);
        check(g.getEnemyManager().getEnemies().isEmpty(), "Palantir releases no children (victory)");
        check(g.isVictorySequenceActive(), "victory sequence started");
    }

    private static void enemyMechanics() {
        Game g = newGame(1);
        g.setGlobalEnemySpeedMultiplier(0);
        // DLL accelerates
        Enemy dll = spawnAt(g, EnemyType.DOUBLY_LINKED_LIST, null, 0, 100);
        double s0 = dll.currentSpeed(1);
        g.getCombat().applyHit(dll, new HitSpec(1, DamageType.TRUE), null, 1, 0);
        check(dll.currentSpeed(1) > s0, "DLL faster after damage");
        // Shell jumps
        Enemy shell = spawnAt(g, EnemyType.SHELL_SORT, null, 0, 100);
        g.run((int) (3.1 / Game.DT));
        check(Math.abs(shell.getDistance() - 240) < 1, "Shell jumped 140 px, d=" + shell.getDistance());
        // Heap shield
        Game g2 = newGame(1);
        g2.setGlobalEnemySpeedMultiplier(0);
        Enemy heap = spawnAt(g2, EnemyType.HEAP_SORT, null, 0, 400);
        Enemy behind = spawnAt(g2, EnemyType.MERGE_SORT, null, 0, 350);
        Enemy ahead = spawnAt(g2, EnemyType.MERGE_SORT, null, 0, 450);
        g2.run(2);
        double dB = g2.getCombat().applyHit(behind, new HitSpec(2, DamageType.ENERGY), null, 1, 0);
        double dA = g2.getCombat().applyHit(ahead, new HitSpec(2, DamageType.ENERGY), null, 1, 0);
        check(dB == 1 && dA == 2, "heap shields enemy behind (1) not ahead (2): " + dB + "," + dA);
        heap.applyStatus(StatusEffect.Kind.DISRUPTED, 1, 5);
        g2.run(3);
        check(g2.getCombat().applyHit(behind, new HitSpec(2, DamageType.ENERGY), null, 1, 0) == 2, "disrupted heap does not shield");
        // Bucket stores and releases
        Game g3 = newGame(1);
        g3.setGlobalEnemySpeedMultiplier(0);
        Enemy bucket = spawnAt(g3, EnemyType.BUCKET_SORT, null, 0, 400);
        Enemy small = spawnAt(g3, EnemyType.PRIMITIVE_VARIABLE, null, 0, 410);
        Enemy big = spawnAt(g3, EnemyType.MERGE_SORT, null, 0, 405);
        g3.run((int) (1.1 / Game.DT));
        check(small.isStored() && bucket.getStoredEnemies().contains(small), "bucket stored primitive");
        check(!big.isStored(), "bucket ignores base HP > 5");
        check(!g3.getEnemyManager().getEnemies().contains(small), "stored enemy off the track");
        check(g3.getCombat().acquireTargets(forcePlace(g3, TowerType.GPT, buildableNear(g3, g3.getMap().getRoutes().get(0).positionAt(400).add(new Vec(0, 70)), 100), 0), 10).size() == 2, "stored enemy untargetable");
        killOutright(g3, bucket);
        check(!small.isStored() && g3.getEnemyManager().getEnemies().contains(small), "bucket released stored enemy");
        // Bucket leak costs stored lives too
        Game g4 = newGame(1);
        double len = g4.getMap().getRoutes().get(0).getTotalLength();
        g4.setGlobalEnemySpeedMultiplier(0);
        Enemy bk = spawnAt(g4, EnemyType.BUCKET_SORT, null, 0, len - 100);
        spawnAt(g4, EnemyType.PRIMITIVE_VARIABLE, null, 0, len - 95);
        g4.run((int) (1.1 / Game.DT));
        check(bk.getStoredEnemies().size() == 1, "stored before leak");
        g4.setGlobalEnemySpeedMultiplier(1);
        g4.run(600);
        check(g4.getLives() == 100 - 5 - 1, "bucket leak costs 5 + 1 lives, lives=" + g4.getLives());
        // Radix phases: layers 8-7 plain, then armoured (Lead-type) phases
        Game g5 = newGame(1);
        Enemy rdx = spawnAt(g5, EnemyType.RADIX_SORT, null, 0, 100);
        check(rdx.radixPhase() == 0 && !rdx.isLeadType(), "radix phase 0 at full HP is not Lead-type");
        check(g5.getCombat().applyHit(rdx, new HitSpec(2, DamageType.SHARP), null, 1, 0) == 2, "radix phase 0 takes Sharp");
        check(rdx.radixPhase() == 1 && rdx.isLeadType(), "radix phase 1 is armoured (Lead-type)");
        check(g5.getCombat().applyHit(rdx, new HitSpec(2, DamageType.SHARP), null, 1, 0) == 0, "radix phase 1 immune to Sharp");
        check(g5.getCombat().applyHit(rdx, new HitSpec(1, DamageType.ENERGY), null, 1, 0) == 1, "radix armoured phase takes Energy");
        g5.getCombat().applyHit(rdx, new HitSpec(2, DamageType.TRUE), null, 1, 0);
        check(rdx.radixPhase() == 2 && rdx.isLeadType(), "radix phase 2 still armoured");
        g5.getCombat().applyHit(rdx, new HitSpec(1, DamageType.TRUE), null, 1, 0);
        check(rdx.radixPhase() == 3 && g5.getCombat().applyHit(rdx, new HitSpec(1, DamageType.EXPLOSIVE), null, 1, 0) == 1, "radix phase 3 takes Explosive");
        // Bubble swap, Selection, Insertion
        Game g6 = newGame(1);
        g6.setGlobalEnemySpeedMultiplier(0);
        Enemy bub = spawnAt(g6, EnemyType.BUBBLE_SORT, null, 0, 300);
        Enemy front = spawnAt(g6, EnemyType.PRIMITIVE_VARIABLE, null, 0, 330);
        g6.run((int) (3.1 / Game.DT));
        check(Math.abs(bub.getDistance() - 330) < 1 && Math.abs(front.getDistance() - 300) < 1, "bubble swapped positions");
        Game g7 = newGame(1);
        g7.setGlobalEnemySpeedMultiplier(0);
        Enemy sel = spawnAt(g7, EnemyType.SELECTION_SORT, null, 0, 300);
        spawnAt(g7, EnemyType.PRIMITIVE_VARIABLE, null, 0, 350);
        spawnAt(g7, EnemyType.PRIMITIVE_VARIABLE, null, 0, 420);
        g7.run((int) (2.6 / Game.DT));
        check(Math.abs(sel.getDistance() - 426) < 1, "selection jumped to group front, d=" + sel.getDistance());
        Game g8 = newGame(1);
        g8.setGlobalEnemySpeedMultiplier(0);
        Enemy ins = spawnAt(g8, EnemyType.INSERTION_SORT, null, 0, 300);
        spawnAt(g8, EnemyType.PRIMITIVE_VARIABLE, null, 0, 340);
        spawnAt(g8, EnemyType.PRIMITIVE_VARIABLE, null, 0, 420);
        g8.run((int) (2.1 / Game.DT));
        check(Math.abs(ins.getDistance() - 346) < 1, "insertion leapfrogged nearest, d=" + ins.getDistance());
        // Slow and stun
        Enemy s = spawnAt(g8, EnemyType.PRIMITIVE_VARIABLE, null, 0, 100);
        s.applyStatus(StatusEffect.Kind.SLOW, 0.5, 2);
        check(Math.abs(s.currentSpeed(1) - Enemy.BASE_SPEED * 0.5) < 0.01, "slow halves speed");
        s.applyStatus(StatusEffect.Kind.STUN, 1, 1);
        check(s.currentSpeed(1) == 0, "stun stops movement");
        // knockback keeps progress consistent
        double before = s.getDistance();
        s.shiftDistance(-30);
        check(s.getDistance() == before - 30 && s.getPosition().dist(s.getRoute().positionAt(before - 30)) < 0.01, "knockback moves along path");
        // knockback budget: stacked pushes cannot exceed 40% of unslowed movement per second
        Enemy kb = spawnAt(g8, EnemyType.MERGE_SORT, null, 0, 500);
        double pushed = 0;
        for (int i = 0; i < 50; i++) pushed += kb.applyKnockback(10, g8.getTime());
        double cap = EnemyType.MERGE_SORT.speed * Enemy.BASE_SPEED * Enemy.KNOCKBACK_BUDGET;
        check(Math.abs(pushed - cap) < 1e-6 && Math.abs(kb.getDistance() - (500 - cap)) < 1e-6, "knockback capped per second at " + cap + " (got " + pushed + ")");
        g8.run(61);
        check(kb.applyKnockback(10, g8.getTime()) == 10, "knockback budget refreshes after a second");
    }

    private static void projectileCollision() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Path r = g.getMap().getRoutes().get(0);
        Vec p = buildableNear(g, r.positionAt(400).add(new Vec(0, -70)), 80);
        Tower claude = forcePlace(g, TowerType.CLAUDE, p, 0);
        Enemy far = spawnAt(g, EnemyType.MERGE_SORT, null, 0, 1500);
        Enemy near = spawnAt(g, EnemyType.MERGE_SORT, null, 0, 400);
        g.run(90);
        check(near.getHp() < near.getMaxHp(), "projectile hit the in-range enemy");
        check(far.getHp() == far.getMaxHp(), "out-of-range enemy untouched");
        check(claude.getDamageDealt() > 0, "damage attributed to tower");
        // Splash hits several
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(0);
        Tower brad = forcePlace(g2, TowerType.KAIJU_KAI, p, 0);
        List<Enemy> group = new ArrayList<>();
        for (int i = 0; i < 4; i++) group.add(spawnAt(g2, EnemyType.HEAP_SORT, null, 0, 400 + i * 15));
        g2.run(120);
        int hit = 0; for (Enemy e : group) if (e.getHp() < e.getMaxHp() || !e.isAlive()) hit++;
        check(hit >= 3, "splash hit several enemies (" + hit + ")");
        check(brad.getDamageDealt() > 0, "Brad dealt damage");
        // Chain hits several
        Game g3 = newGame(0);
        g3.setGlobalEnemySpeedMultiplier(0);
        forcePlace(g3, TowerType.GEMINI, p, 1);
        List<Enemy> g3e = new ArrayList<>();
        for (int i = 0; i < 4; i++) g3e.add(spawnAt(g3, EnemyType.HEAP_SORT, null, 0, 400 + i * 40));
        g3.run(60);
        int chained = 0; for (Enemy e : g3e) if (e.getHp() < e.getMaxHp()) chained++;
        check(chained >= 3, "chain hit several enemies (" + chained + ")");
        // Pulse and beam
        Game g4 = newGame(0);
        g4.setGlobalEnemySpeedMultiplier(0);
        forcePlace(g4, TowerType.SUNO, p, 0);
        forcePlace(g4, TowerType.COHERE, buildableNear(g4, p.add(new Vec(70, 0)), 100), 0);
        Enemy e4 = spawnAt(g4, EnemyType.HEAP_SORT, null, 0, 400);
        g4.run(70);
        check(e4.getHp() < e4.getMaxHp(), "pulse/beam damaged enemy");
        // MiniMax bounce
        Game g5 = newGame(0);
        g5.setGlobalEnemySpeedMultiplier(0);
        forcePlace(g5, TowerType.MINIMAX, p, 0);
        List<Enemy> g5e = new ArrayList<>();
        for (int i = 0; i < 3; i++) g5e.add(spawnAt(g5, EnemyType.HEAP_SORT, null, 0, 400 + i * 30));
        g5.run(120);
        int bounced = 0; for (Enemy e : g5e) if (e.getHp() < e.getMaxHp()) bounced++;
        check(bounced >= 2, "bounce hit several enemies (" + bounced + ")");
    }

    private static void waveCompositions() {
        List<WaveDef> all = WaveData.all();
        check(all.size() == 100, "100 waves");
        for (int i = 0; i < all.size(); i++) {
            WaveDef w = all.get(i);
            check(w.number == i + 1, "wave numbering " + (i + 1));
            check(!w.groups.isEmpty() && w.totalSpawns() > 0, "wave " + w.number + " has spawns");
            for (SpawnGroup gr : w.groups) check(gr.count > 0 && gr.interval >= 0 && gr.startDelay >= 0, "wave " + w.number + " group sane");
        }
        check(all.get(0).groups.size() == 1 && all.get(0).groups.get(0).type == EnemyType.PRIMITIVE_VARIABLE, "wave 1 primitives only");
        check(all.get(19).contains(EnemyType.BUBBLE_SORT), "wave 20 Bubble Sort");
        boolean sorterBefore20 = false;
        for (int i = 0; i < 19; i++) for (SpawnGroup gr : all.get(i).groups) if (gr.type.ordinal() >= EnemyType.BUBBLE_SORT.ordinal()) sorterBefore20 = true;
        check(!sorterBefore20, "no sorters before wave 20");
        check(all.get(39).countOf(EnemyType.BELLARMINE_COLLEGE_PREP) == 1, "wave 40 first MOAB");
        boolean moabBefore40 = false;
        for (int i = 0; i < 39; i++) if (all.get(i).containsBoss()) moabBefore40 = true;
        check(!moabBefore40, "no boss before wave 40");
        check(all.get(59).countOf(EnemyType.SW_RESOURCE_CONSULTANT) == 1, "wave 60 BFB");
        check(all.get(79).countOf(EnemyType.THREE_COM) == 1, "wave 80 ZOMG");
        check(all.get(89).contains(EnemyType.LOCKHEED_MARTIN), "wave 90 DDT");
        boolean ddtBefore90 = false;
        for (int i = 0; i < 89; i++) if (all.get(i).contains(EnemyType.LOCKHEED_MARTIN)) ddtBefore90 = true;
        check(!ddtBefore90, "no DDT before 90");
        check(all.get(99).countOf(EnemyType.PALANTIR) == 1, "wave 100 Palantir");
        for (int i = 0; i < 99; i++) check(!all.get(i).contains(EnemyType.PALANTIR), "no Palantir before 100");
        boolean camoIn21to39 = false, fortIn21to39 = false;
        for (int i = 20; i < 39; i++) for (SpawnGroup gr : all.get(i).groups) {
            if (gr.modifiers.contains(Modifier.CAMO)) camoIn21to39 = true;
            if (gr.modifiers.contains(Modifier.FORTIFIED)) fortIn21to39 = true;
        }
        check(camoIn21to39 && fortIn21to39, "camo & fortified introduced in 21-39");
        for (int i = 90; i < 99; i++) check(all.get(i).groups.size() >= 2, "wave " + (i + 1) + " fully specified");
        for (EnemyType t : EnemyType.values()) {
            if (!t.isSpawnableSpecies()) continue;
            boolean used = false;
            for (WaveDef w : all) if (w.contains(t)) used = true;
            check(used, t + " appears in the campaign");
        }
    }

    private static void waveSpawningMatchesData() {
        for (int wave = 1; wave <= 100; wave++) {
            Game g = newGame(wave % MapCatalog.MAP_COUNT);
            g.setGlobalEnemySpeedMultiplier(0);
            // force the wave number
            for (int k = 1; k < wave; k++) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
            check(g.startNextWave(), "start wave " + wave);
            WaveDef def = g.getWaveManager().getCurrentDef();
            check(def.number == wave, "current def is wave " + wave);
            int ticks = (int) ((def.duration() + 1.0) / Game.DT);
            for (int i = 0; i < ticks; i++) {
                g.getWaveManager().update(Game.DT);
                g.getEnemyManager().update(0);
                // neutralise: no deaths, no movement (speed mult 0) -> counts stay exact
            }
            check(g.getWaveManager().getRemainingToSpawn() == 0, "wave " + wave + " fully spawned");
            check(g.getEnemyManager().getTotalSpawned() == def.totalSpawns(), "wave " + wave + " spawned " + def.totalSpawns() + " got " + g.getEnemyManager().getTotalSpawned());
            for (SpawnGroup gr : def.groups) {
                int n = 0;
                for (Enemy e : g.getEnemyManager().getEnemies()) {
                    if (e.getType() == gr.type && sameMods(e, gr)) n++;
                }
                int expected = 0;
                for (SpawnGroup o : def.groups) if (o.type == gr.type && o.modifiers.equals(gr.modifiers)) expected += o.count;
                check(n == expected, "wave " + wave + " " + gr.type + " " + gr.modifierLabel() + " count " + expected + " got " + n);
            }
            for (Enemy e : g.getEnemyManager().getEnemies()) {
                check(Math.abs(e.getHpScale() - WaveData.hpScale(wave)) < 1e-9, "wave " + wave + " hp scale");
            }
            if (wave == 100) {
                boolean pal = false;
                for (Enemy e : g.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.PALANTIR) pal = true;
                check(pal, "Palantir spawned on wave 100");
            }
            check(g.getWaveManager().isWaveActive(), "wave stays active while enemies alive");
        }
        // Wave completes when all dead; next wave does not start by itself
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        g.startNextWave();
        g.run((int) (WaveData.get(1).duration() / Game.DT) + 10);
        check(!g.startNextWave(), "cannot start wave 2 while wave 1 active");
        for (Enemy e : new ArrayList<>(g.getEnemyManager().getEnemies())) g.getCombat().applyHit(e, new HitSpec(1e9, DamageType.TRUE), null, 1, 0);
        double cash = g.getCash();
        g.run(5);
        check(!g.getWaveManager().isWaveActive(), "wave 1 complete after kills");
        check(g.getCash() >= cash + WaveData.waveBonus(1), "wave bonus paid");
        check(g.getLastCompletedWave() == 1, "last completed = 1");
        g.run(600);
        check(g.getWave() == 1, "next wave not auto-started");
        check(g.startNextWave() && g.getWave() == 2, "wave 2 starts on request");
    }

    private static void palantirPhasesAndSurveillance() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Path r = g.getMap().getRoutes().get(0);
        Vec base = r.positionAt(500).add(new Vec(0, -80));
        Tower cheap = forcePlace(g, TowerType.QWEN, buildableNear(g, base, 100), 0);
        Tower strong = forcePlace(g, TowerType.DEEPSEEK, buildableNear(g, base.add(new Vec(80, 0)), 100), 3);
        Tower strong2 = forcePlace(g, TowerType.COHERE, buildableNear(g, base.add(new Vec(160, 0)), 100), 3);
        Boss pal = (Boss) spawnAt(g, EnemyType.PALANTIR, null, 0, 500);
        g.getEnemyManager().update(0);
        check(pal.getPhase() == 0 && pal.getPhaseCount() == 3, "Palantir starts phase 1 of 3");
        check(Math.abs(pal.effectiveArmor() - 0.60) < 1e-9, "phase 1 armour 60%");
        check(pal.isControlImmune(), "phase 1 control immune");
        pal.applyStatus(StatusEffect.Kind.SLOW, 0.5, 5);
        HitSpec stunHit = new HitSpec(0, DamageType.TRUE); stunHit.bossStunDuration = 2; stunHit.slowFraction = 0.5; stunHit.slowDuration = 2;
        g.getCombat().applyHit(pal, stunHit, null, 1, 0);
        check(!pal.isStunned(), "phase 1 ignores stuns");
        // damage to 69%
        g.getCombat().applyHit(pal, new HitSpec(pal.getMaxHp() * 0.31, DamageType.TRUE), null, 1, 0);
        g.run(1);
        check(pal.getPhase() == 1, "phase 2 at <70%");
                check(Math.abs(pal.effectiveArmor() - 0.35) < 1e-9, "phase 2 armour 35%");
        int enemiesBefore = g.getEnemyManager().getEnemies().size();
        g.getCombat().applyHit(pal, new HitSpec(pal.getMaxHp() * 0.35, DamageType.TRUE), null, 1, 0);
        g.run(1);
        check(pal.getPhase() == 2, "phase 3 at <35%");
                check(Math.abs(pal.effectiveArmor() - 0.10) < 1e-9, "phase 3 armour 10%");
        check(g.getEnemyManager().countOfType(EnemyType.LOCKHEED_MARTIN) == 2 && g.getEnemyManager().getEnemies().size() == enemiesBefore + 2, "phase 3 launches 2 Lockheed escorts");
        // Surveillance
        pal.beginSurveillance(g);
        check(pal.isTelegraphing(), "telegraph active");
        check(pal.getMarkedTowers().size() == 3, "phase 3 marks 4 towers capped by 3 available, got " + pal.getMarkedTowers().size());
        check(pal.getMarkedTowers().contains(strong) && pal.getMarkedTowers().contains(strong2), "marks strongest (highest investment)");
        double rateBefore = strong.effectiveRate(g);
        double rangeBefore = strong.effectiveRange(g);
        g.run((int) (Boss.TELEGRAPH_TIME / Game.DT) + 2);
        check(!pal.isTelegraphing(), "telegraph ended");
        check(strong.isSurveilled() && strong2.isSurveilled() && cheap.isSurveilled(), "towers surveilled after telegraph");
        check(strong.effectiveRate(g) < rateBefore * 0.51 && strong.effectiveRange(g) < rangeBefore * 0.71, "surveillance halves rate, cuts range 30%");
        check(!strong.isAbilityReady(), "ability locked while surveilled");
        g.run((int) (Boss.SURVEIL_DURATION / Game.DT) + 2);
        check(!strong.isSurveilled(), "surveillance expires");
        check(Math.abs(strong.effectiveRate(g) - rateBefore) < 1e-9, "rate restored");
        // Counter: Perplexity Sonar Reasoning Pro (U2) radius immunity
        Tower perp = forcePlace(g, TowerType.PERPLEXITY, buildableNear(g, base.add(new Vec(80, 60)), 100), 2);
        g.getTowerManager().recomputeAuras();
        check(strong.isSurveillanceImmune(), "DeepSeek immune inside Perplexity U2 radius");
        pal.beginSurveillance(g);
        g.run((int) (Boss.TELEGRAPH_TIME / Game.DT) + 2);
        check(!strong.isSurveilled(), "immune tower not surveilled");
        // Upgrading a surveilled tower clears the effect
        g.sellTower(perp);
        g.getTowerManager().recomputeAuras();
        pal.beginSurveillance(g);
        g.run((int) (Boss.TELEGRAPH_TIME / Game.DT) + 2);
        check(strong.isSurveilled() && cheap.isSurveilled(), "surveilled again without the Perplexity radius");
        check(g.upgradeTower(cheap) && !cheap.isSurveilled(), "upgrading clears Surveillance");
        // Periodic trigger happens on its own
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(0);
        Tower t2 = forcePlace(g2, TowerType.GPT, buildableNear(g2, base, 100), 0);
        Boss p2 = (Boss) spawnAt(g2, EnemyType.PALANTIR, null, 0, 500);
        g2.run((int) (31 / Game.DT));
        check(p2.getMarkedTowers().contains(t2) || t2.isSurveilled(), "surveillance fires periodically");
    }

    private static void abilityCooldowns() {
        Game g = newGame(0);
        Vec p = buildableNear(g, new Vec(400, 250), 200);
        Tower st = forcePlace(g, TowerType.ZETHOS, p, TowerCatalog.ZETHOS_UPGRADES);
        check(!st.isAbilityReady() && !g.activateAbility(st), "a maxed Zethos's ability is locked until bought");
        g.addCash(TowerCatalog.ABILITY_UNLOCK_COST, null);
        check(g.unlockAbility(st) && st.isAbilityReady(), "the bought ability is ready at once");
        check(g.activateAbility(st), "ability activates");
        check(!st.isAbilityReady(), "not ready after use");
        check(Math.abs(st.getAbilityCooldownRemaining() - 55) < 1e-9, "cooldown 55 s");
        check(!g.activateAbility(st), "cannot activate during cooldown");
        check(Math.abs(st.selfRateMult() - 2.0) < 1e-9, "self buff applied (x2 rate)");
        runSeconds(g, 6.1);
        check(st.selfRateMult() == 1.0, "buff expired after 6 s");
        runSeconds(g, 49);
        check(st.isAbilityReady(), "ready again after cooldown");
        // cooldowns count in game time: 3x speed finishes three times sooner in real seconds
        Game fast = newGame(0);
        Tower ft = forcePlace(fast, TowerType.ZETHOS, p, TowerCatalog.ZETHOS_UPGRADES);
        fast.addCash(TowerCatalog.ABILITY_UNLOCK_COST, null);
        check(fast.unlockAbility(ft) && fast.activateAbility(ft), "fast-forward test: ability unlocked and used");
        fast.setSpeed(3);
        for (int i = 0; i < 60 * 19; i++) fast.advance(1.0 / 60);   // 19 real seconds = 57 game seconds > the 55 s cooldown
        check(ft.isAbilityReady(), "ability cooldown speeds up with fast-forward");
        // every tower's ability can activate (with an enemy present where required)
        int i = 0;
        for (TowerType type : TowerType.purchasable()) {
            Game gg = newGame(0);
            gg.setGlobalEnemySpeedMultiplier(0);
            Path r = gg.getMap().getRoutes().get(0);
            Vec q = buildableNear(gg, r.positionAt(500).add(new Vec(0, -70)), 120);
            Tower t = forcePlace(gg, type, q, TowerCatalog.get(type).upgrades.length);
            if (t.isAbilityLocked()) {   // shop towers: bought at max tier for $15,000, ready at once
                check(!gg.activateAbility(t), type + " locked ability cannot activate");
                gg.addCash(lindefense.tower.TowerCatalog.ABILITY_UNLOCK_COST, null);
                check(gg.unlockAbility(t) && t.isAbilityReady(), type + " unlocks its ability at max tier");
            }
            if (t.getAbility() == null) { check(!gg.activateAbility(t), type + " has no ability to activate"); continue; }
            spawnAt(gg, EnemyType.HEAP_SORT, null, 0, 500);
            spawnAt(gg, EnemyType.MERGE_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 510);
            t.resetAbilityCooldown();
            if (t.getAbility().needsTarget) check(!gg.activateAbility(t) && t.isAbilityReady(), type + " targeted ability refuses activation without a point");
            boolean ok = t.getAbility().needsTarget ? gg.activateAbility(t, r.positionAt(500)) : gg.activateAbility(t);
            check(ok, type + " ability activates");
            check(!t.isAbilityReady() && t.getAbilityCooldownRemaining() > 0, type + " ability on cooldown");
            gg.run(60);
            i++;
        }
        check(i == TowerType.shopTowers().length, "every shop tower's ability tested (17 unlockable + Zethos; heroes are passive), got " + i);
    }

    private static void mapsTraversable() {
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            GameMap map = MapCatalog.create(m);
            check(!map.getRoutes().isEmpty(), map.getName() + " has routes");
            for (int ri = 0; ri < map.getRoutes().size(); ri++) {
                Path r = map.getRoutes().get(ri);
                check(r.getTotalLength() > 500, map.getName() + " route " + ri + " length " + r.getTotalLength());
                for (Vec w : r.getWaypoints()) {
                    check(w.x >= -1 && w.x <= GameMap.WIDTH + 1 && w.y >= -1 && w.y <= GameMap.HEIGHT + 1, map.getName() + " waypoint in bounds " + w);
                }
                Game g = new Game(MapCatalog.create(m), 7);
                // a boss is immune to map hazards (short circuits), so it always reaches the exit
                Enemy e = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, ri, 0);
                double last = -1;
                int ticks = 0;
                boolean monotonic = true;
                while (e.isAlive() && ticks < 20000) {
                    g.step(Game.DT);
                    if (e.isAlive() && e.getDistance() < last - 1e-6) monotonic = false;
                    last = e.getDistance();
                    ticks++;
                }
                check(e.hasLeaked(), map.getName() + " route " + ri + " reaches exit (" + ticks + " ticks)");
                check(monotonic, map.getName() + " route " + ri + " monotonic progress");
                check(g.getLives() == 100 - EnemyType.BELLARMINE_COLLEGE_PREP.lives, map.getName() + " leak costs lives");
            }
            // buildable area exists
            int buildable = 0;
            for (int x = 20; x < GameMap.WIDTH; x += 20) for (int y = 20; y < GameMap.HEIGHT; y += 20) if (map.isBuildable(new Vec(x, y), 20)) buildable++;
            check(buildable > 200, map.getName() + " has buildable area (" + buildable + " cells)");
        }
        // Legacy Monolith line of sight blocked by chassis
        GameMap mono = MapCatalog.create(1);
        check(!mono.hasLineOfSight(new Vec(400, 150), new Vec(400, 290)), "chassis blocks LOS");
        check(mono.hasLineOfSight(new Vec(150, 150), new Vec(150, 290)), "clear LOS beside chassis");
    }

    /** Silicon Valley, The Neural Network and Abandoned Data Center: geometry and the Data Center hazards. */
    private static void newMaps() {
        // buildings never sit on a road, on any of the three maps
        for (int m = 4; m < MapCatalog.MAP_COUNT; m++) {
            GameMap map = MapCatalog.create(m);
            for (Path r : map.getRoutes()) {
                for (double d = 0; d <= r.getTotalLength(); d += 5) {
                    Vec p = r.positionAt(d);
                    for (lindefense.map.Obstacle o : map.getObstacles()) check(!o.contains(p, GameMap.TRACK_HALF_WIDTH + 2), map.getName() + ": " + o.label + " clear of the track at " + p);
                }
            }
        }
        // Neural Network: six routes, each from an input to the single exit through the output neuron
        lindefense.map.NeuralNetwork nn = (lindefense.map.NeuralNetwork) MapCatalog.create(5);
        check(nn.getRoutes().size() == 6, "neural network has six routes");
        for (Path r : nn.getRoutes()) {
            Vec s0 = r.getStart();
            check(s0.dist(lindefense.map.NeuralNetwork.IN_A) < 1 || s0.dist(lindefense.map.NeuralNetwork.IN_B) < 1, r.getName() + " starts at an input");
            check(r.getEnd().dist(lindefense.map.NeuralNetwork.EXIT) < 1, r.getName() + " ends at the exit");
            check(r.distanceToPoint(lindefense.map.NeuralNetwork.OUT) < 20, r.getName() + " passes through the output neuron");
        }
        // Data Center: hazards warn, activate, slow enemies only inside their section, bosses a third as much
        Game g = newGame(6);
        lindefense.map.AbandonedDataCenter dc = (lindefense.map.AbandonedDataCenter) g.getMap();
        g.setGlobalEnemySpeedMultiplier(0);
        int ticks = 0;
        boolean warned = false;
        while (dc.getActiveHazard() < 0 && ticks < 2000) { g.step(Game.DT); ticks++; if (dc.getWarnedHazard() >= 0) warned = true; }
        check(warned, "a hazard warns before it activates");
        int a = dc.getActiveHazard();
        check(a >= 0 && Math.abs(ticks * Game.DT - lindefense.map.AbandonedDataCenter.HAZARD_INTERVAL) < 0.2, "a hazard activates after " + lindefense.map.AbandonedDataCenter.HAZARD_INTERVAL + " s (" + ticks * Game.DT + ")");
        lindefense.map.AbandonedDataCenter.Hazard h = dc.getHazards().get(a);
        Enemy in = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, (h.from + h.to) / 2);
        Enemy out = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, h.from - 60);
        Enemy boss = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, (h.from + h.to) / 2);
        double slow = lindefense.map.AbandonedDataCenter.HAZARD_SLOW;
        check(Math.abs(dc.enemySpeedMultiplier(in) - (1 - slow)) < 1e-9, "enemies in the active section are slowed");
        check(dc.enemySpeedMultiplier(out) == 1.0, "enemies outside the section are not slowed");
        check(Math.abs(dc.enemySpeedMultiplier(boss) - (1 - slow / 3)) < 1e-9, "bosses take a third of the hazard slow");
        check(dc.getEventText() != null, "an active hazard shows a banner");
        g.run((int) (lindefense.map.AbandonedDataCenter.HAZARD_DURATION / Game.DT) + 2);
        check(dc.getActiveHazard() < 0 && dc.enemySpeedMultiplier(in) == 1.0, "the hazard switches off after its duration");
        int prev = a, repeats = 0;
        for (int k = 0; k < 12; k++) {
            int guard = 0;
            while (dc.getActiveHazard() < 0 && guard++ < 2000) g.step(Game.DT);
            int now = dc.getActiveHazard();
            if (now == prev) repeats++;
            prev = now;
            while (dc.getActiveHazard() >= 0 && guard++ < 4000) g.step(Game.DT);
        }
        check(repeats == 0, "the same hazard never fires twice in a row");
    }

    /** SETTINGS > ADMIN CODE: the code check and each cheat on the checklist, applied independently. */
    private static void adminMode() {
        check(lindefense.sim.AdminMode.matches("lindeveloper"), "admin code accepted");
        check(lindefense.sim.AdminMode.matches("  LinDeveloper "), "admin code ignores case and spaces");
        check(!lindefense.sim.AdminMode.matches("lindeveloper1") && !lindefense.sim.AdminMode.matches("austin") && !lindefense.sim.AdminMode.matches("") && !lindefense.sim.AdminMode.matches(null), "wrong codes rejected");
        check(lindefense.sim.AdminMode.Option.values().length == 3, "the checklist offers three cheats");
        Game normal = newGame(0);
        check(!normal.isAdmin() && !normal.isHeroUnlocked(TowerType.CHILLSTIN), "games start with no cheats");
        check(!normal.hasAdminHeroes() && !normal.hasAdminMoney() && !normal.hasAdminHealth(), "no cheat is on by default");

        // 1. unlock all heroes, on its own
        Game heroesOnly = newGame(0);
        heroesOnly.setAdmin(true, false, false);
        for (TowerType h : TowerType.heroes()) check(heroesOnly.isHeroUnlocked(h), "unlock-all opens " + h.displayName);
        check(heroesOnly.getHeroCollection().unlocked().isEmpty(), "unlock-all never touches the saved collection");
        check(heroesOnly.getCash() == Game.START_CASH, "unlock-all does not hand out money");

        // 2. infinite money, on its own
        Game moneyOnly = newGame(0);
        moneyOnly.setAdmin(false, true, false);
        double before = moneyOnly.getCash();
        check(before >= Game.ADMIN_CASH, "infinite money tops credits up");
        check(!moneyOnly.isHeroUnlocked(TowerType.CHILLSTIN), "infinite money alone does not unlock heroes");
        int placed = 0, maxed = 0;
        for (TowerType type : TowerType.shopTowers()) {
            Tower t = moneyOnly.placeTower(type, buildableNear(moneyOnly, new Vec(150 + (placed % 8) * 120, 300 + (placed / 8) * 180), 260));
            if (t == null) continue;
            placed++;
            while (moneyOnly.upgradeTower(t)) { /* every upgrade */ }
            if (!t.canUpgrade()) maxed++;
        }
        check(placed >= 10 && maxed == placed, "infinite money buys and fully upgrades every tower (" + maxed + "/" + placed + ")");
        check(moneyOnly.getCash() == before, "spending never lowers the credits");

        // 3. infinite health, on its own
        Game healthOnly = newGame(0);
        healthOnly.setAdmin(false, false, true);
        for (int i = 0; i < Game.START_LIVES + 50; i++) {
            Enemy e = healthOnly.getEnemyManager().spawnScaled(EnemyType.PRIMITIVE_VARIABLE, null, 0, 0, 1, 1.0);
            healthOnly.getEnemyManager().update(0);
            healthOnly.loseLives(1, e);
            e.markDead();
        }
        check(healthOnly.getLives() >= 1 && healthOnly.getState() == Game.State.PLAYING, "infinite health never loses the run");
        Game mortal = newGame(0);
        for (int i = 0; i < Game.START_LIVES + 5; i++) {
            Enemy e = mortal.getEnemyManager().spawnScaled(EnemyType.PRIMITIVE_VARIABLE, null, 0, 0, 1, 1.0);
            mortal.getEnemyManager().update(0);
            mortal.loseLives(1, e);
            e.markDead();
        }
        check(mortal.getLives() == 0, "without the cheat the same leaks empty the integrity bar");

        // all three together, and RESTART keeps them
        Game all = newGame(0);
        all.setAdmin(true, true, true);
        check(all.isAdmin() && all.hasAdminHeroes() && all.hasAdminMoney() && all.hasAdminHealth(), "all three can be on at once");
        Game restarted = Game.freshCopy(all);
        check(restarted.hasAdminHeroes() && restarted.hasAdminMoney() && restarted.hasAdminHealth(), "RESTART keeps the checklist");
    }

    private static void mapMechanics() {
        // Singularity: gravity and collapse
        Game g = newGame(3);
        SingularityCore sc = (SingularityCore) g.getMap();
        Enemy far = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, 0);
        Enemy near = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 1, g.getMap().getRoutes().get(1).getTotalLength() - 100);
        check(sc.enemySpeedMultiplier(near) > sc.enemySpeedMultiplier(far), "gravity speeds up enemies near core");
        g.setGlobalEnemySpeedMultiplier(0);
        Tower t = forcePlace(g, TowerType.ZETHOS, buildableNear(g, new Vec(600, 200), 200), TowerCatalog.ZETHOS_UPGRADES);
        g.addCash(TowerCatalog.ABILITY_UNLOCK_COST, null);
        check(g.unlockAbility(t), "Zethos's ability unlocked for the collapse test");
        g.activateAbility(t);
        check(!t.isAbilityReady(), "cooldown started");
        sc.triggerCollapse(g);
        check(t.isAbilityReady(), "collapse resets cooldowns");
        // Canyon: drift & storm
        Game g2 = newGame(2);
        HallucinationCanyon hc = (HallucinationCanyon) g2.getMap();
        int drifted = 0;
        for (int i = 0; i < 200; i++) {
            Game gg = new Game(MapCatalog.create(2), i);
            HallucinationCanyon m = (HallucinationCanyon) gg.getMap();
            Path r0 = m.getRoutes().get(0);
            double centerD = r0.nearestDistanceAlong(m.getCenter());
            Enemy e = spawnAt(gg, EnemyType.PRIMITIVE_VARIABLE, null, 0, centerD - 25);
            gg.run(60);
            if (e.getRoute() != r0 || Math.abs(e.getDistance() - (centerD - 25 + Enemy.BASE_SPEED)) > 30) drifted++;
        }
        check(drifted > 25 && drifted < 80, "attention drift ~25% (" + drifted + "/200)");
        g2.setGlobalEnemySpeedMultiplier(0);
        Tower gpt = forcePlace(g2, TowerType.GPT, buildableNear(g2, new Vec(300, 600), 200), 0);
        g2.run((int) (HallucinationCanyon.STORM_INTERVAL / Game.DT) + 5);
        check(hc.isStormActive(), "noise storm started");
        check(Math.abs(gpt.effectiveRange(g2) - gpt.getStats().range * 0.5) < 1e-6, "storm halves range");
        forcePlace(g2, TowerType.COPILOT, buildableNear(g2, gpt.getPosition().add(new Vec(60, 0)), 100), 0);
        check(Math.abs(gpt.effectiveRange(g2) - gpt.getStats().range) < 1e-6, "Logic Specialist counters storm");
        // placement-ghost preview passes a null tower (WorldView.syncOverlay); used to NPE here
        boolean previewOk;
        double previewMult = -1;
        try { previewMult = hc.towerRangeMultiplier(g2, null); previewOk = true; } catch (RuntimeException ex) { previewOk = false; }
        check(previewOk && Math.abs(previewMult - 0.5) < 1e-9, "storm range preview accepts a null tower (got " + previewMult + ")");
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            Game gm = newGame(m);
            boolean ok = true;
            try { gm.getMap().towerRangeMultiplier(gm, null); } catch (RuntimeException ex) { ok = false; }
            check(ok, "map " + m + " range preview accepts a null tower");
        }
        // Monolith: venting
        Game g3 = newGame(1);
        lindefense.map.LegacyMonolith lm = (lindefense.map.LegacyMonolith) g3.getMap();
        for (int k = 1; k < 10; k++) { g3.getWaveManager().startNextWave(); g3.getWaveManager().endWave(); g3.getEnemyManager().clear(); }
        g3.startNextWave();
        check(lm.getVentedFloor() >= 0, "wave 10 vents a floor");
        // Silicon: short circuit happens
        Game g4 = newGame(0);
        g4.setGlobalEnemySpeedMultiplier(0);
        Enemy e4a = spawnAt(g4, EnemyType.HEAP_SORT, null, 0, 300);
        Enemy e4b = spawnAt(g4, EnemyType.HEAP_SORT, null, 1, 300);
        g4.run((int) (lindefense.map.SiliconCircuit.SHORT_INTERVAL / Game.DT) + 5);
        check((e4a.getHp() < 8) ^ (e4b.getHp() < 8), "short circuit zapped exactly one lane");
    }

    private static void winAndLose() {
        // lose
        Game g = newGame(0);
        double len = g.getMap().getRoutes().get(0).getTotalLength();
        for (int i = 0; i < 4; i++) spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, len - 3);
        g.run(300);
        check(g.getLives() == 0, "lives hit zero");
        check(g.getState() == Game.State.DEFEAT, "state DEFEAT, got " + g.getState());
        check(!g.startNextWave(), "cannot start wave after defeat");
        // win
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(0);
        for (int k = 1; k < 100; k++) { g2.getWaveManager().startNextWave(); g2.getWaveManager().endWave(); }
        g2.startNextWave();
        check(g2.getWave() == 100, "on wave 100");
        g2.run((int) (9 / Game.DT));
        Boss pal = g2.getPalantir();
        check(pal != null && pal.isAlive(), "Palantir present on wave 100");
        killOutright(g2, pal);
        check(g2.isVictorySequenceActive(), "victory sequence running");
        check(g2.getState() == Game.State.PLAYING, "still PLAYING during sequence");
        g2.run((int) (Game.VICTORY_SEQUENCE_TIME / Game.DT) + 5);
        check(g2.getState() == Game.State.VICTORY, "state VICTORY, got " + g2.getState());
    }

    private static void shopLayout() {
        List<lindefense.ui.ShopLayout.Cell> all = lindefense.ui.ShopLayout.allCells();
        check(all.size() == 18, "ALL view lists the 18 shop towers (no heroes), got " + all.size());
        // spec order, grouped by faction
        lindefense.tower.Faction[] order = lindefense.tower.Faction.values();
        int fi = 0;
        boolean grouped = true;
        for (lindefense.ui.ShopLayout.Cell c : all) {
            while (fi < order.length && c.faction != order[fi]) fi++;
            if (fi >= order.length) grouped = false;
        }
        check(grouped && all.get(0).faction == lindefense.tower.Faction.PRIMARY && all.get(17).faction == lindefense.tower.Faction.TITAN, "grouped in faction order");
        boolean noHero = true;
        for (lindefense.ui.ShopLayout.Cell c : all) if (c.type.isHero()) noHero = false;
        check(noHero, "heroes never appear in the tower shop");
        int headers = 0;
        for (lindefense.ui.ShopLayout.Cell c : all) if (c.firstOfFaction) headers++;
        check(headers == 5, "five faction headers");
        // fits the sidebar without scrolling, no overlaps, inside panel
        boolean inside = true, overlap = false;
        for (int i = 0; i < all.size(); i++) {
            lindefense.ui.ShopLayout.Cell a = all.get(i);
            if (a.x < lindefense.ui.Ui.PANEL_X || a.x + a.w > lindefense.ui.Ui.PANEL_X + lindefense.ui.Ui.PANEL_W
                || a.y < lindefense.ui.ShopLayout.CARDS_Y || a.y + a.h > lindefense.ui.ShopLayout.CARDS_BOTTOM) inside = false;
            for (int j = i + 1; j < all.size(); j++) {
                lindefense.ui.ShopLayout.Cell b = all.get(j);
                if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlap = true;
            }
        }
        check(inside, "all cells fit inside the sidebar card area (" + lindefense.ui.ShopLayout.allGridHeight() + " px tall)");
        check(!overlap, "no overlapping cells");
        // hit testing picks the right cell
        for (lindefense.ui.ShopLayout.Cell c : all) check(lindefense.ui.ShopLayout.cellAt(all, c.x + c.w / 2, c.y + c.h / 2) == c, "cell hit test " + c.type);
        // faction view
        check(lindefense.ui.ShopLayout.factionCells(lindefense.tower.Faction.TITAN).size() == 7, "Titans tab has 7 cards");
        // affordability flags follow cash
        check(lindefense.ui.ShopLayout.affordable(650, TowerType.GPT) && !lindefense.ui.ShopLayout.affordable(650, TowerType.COHERE), "affordability at $650");
        check(lindefense.ui.ShopLayout.shortfall(650, TowerType.COHERE) == 800 - 650 && lindefense.ui.ShopLayout.shortfall(650, TowerType.GPT) == 0, "shortfall amounts");
        int affordableAtStart = 0;
        for (lindefense.ui.ShopLayout.Cell c : all) if (lindefense.ui.ShopLayout.affordable(Game.START_CASH, c.type)) affordableAtStart++;
        check(affordableAtStart == 13, "13 of 18 shop towers affordable at start, got " + affordableAtStart);
    }

    private static void stressLateWaves() {
        long start = System.currentTimeMillis();
        int overallPeak = 0;
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            Game g = newGame(m);
            g.setInvincible(true);
            g.setGlobalEnemySpeedMultiplier(0.35); // slow enemies so a genuine rush accumulates
            g.addCash(500_000, null);
            // Build a dense late-game defence near the routes
            TowerType[] types = { TowerType.KAIJU_KAI, TowerType.DEEPSEEK, TowerType.COHERE, TowerType.GEMINI, TowerType.SORA,
                TowerType.SUNO, TowerType.GLM, TowerType.PERPLEXITY, TowerType.MINIMAX, TowerType.MISTRAL, TowerType.QWEN, TowerType.KIMI,
                TowerType.GPT, TowerType.CLAUDE, TowerType.LLAMA, TowerType.DALLE, TowerType.GROK, TowerType.COPILOT, TowerType.ZETHOS,
                TowerType.BLITZ_ARNAV, TowerType.CHILLSTIN, TowerType.BOOM_SAM, TowerType.SUNNY_JOE, TowerType.NIK_SCOPE,
                TowerType.LOBBER_LUIS, TowerType.SAGE_AARAV, TowerType.IRON_IMRAAN, TowerType.ABHI_ACE, TowerType.ZIPPY_MATT,
                TowerType.CAMI_MINE, TowerType.JUSTIN_TIME, TowerType.SPEAR_HANBO, TowerType.THORN_TUHIN, TowerType.TRAPPER_CHE,
                TowerType.TANIMBUS };
            for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);
            int placed = 0;
            for (Path r : g.getMap().getRoutes()) {
                for (double d = 100; d < r.getTotalLength() && placed < 14; d += 220) {
                    Vec base = r.positionAt(d);
                    for (int side = -1; side <= 1; side += 2) {
                        Vec dir = r.directionAt(d);
                        Vec perp = new Vec(-dir.y, dir.x).scale(side * 70);
                        Vec p = base.add(perp);
                        TowerType tt = types[placed % types.length];
                        if (g.getTowerManager().canPlace(tt, p)) {
                            Tower t = g.placeTower(tt, p);
                            g.upgradeTower(t); // modest defence so the rush accumulates
                            placed++;
                        }
                    }
                }
            }
            check(placed >= 8, g.getMap().getName() + " placed defence (" + placed + ")");
            for (int k = 1; k < 97; k++) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
            int maxEnemies = 0, maxProjectiles = 0;
            for (int wave = 97; wave <= 100; wave++) {
                g.getWaveManager().endWave();
                g.getEnemyManager().clear();
                check(g.startNextWave(), "start wave " + wave + " on " + g.getMap().getName());
                int ticks = 0;
                while (g.getWaveManager().isWaveActive() && ticks < 60 * 150 && g.getState() == Game.State.PLAYING) {
                    g.step(Game.DT);
                    // use abilities whenever ready
                    if (ticks % 120 == 0) for (Tower t : new ArrayList<>(g.getTowerManager().getTowers())) if (t.isAbilityReady()) g.activateAbility(t);
                    maxEnemies = Math.max(maxEnemies, g.getEnemyManager().getEnemies().size());
                    maxProjectiles = Math.max(maxProjectiles, g.getCombat().getProjectiles().size());
                    g.getEvents().clear();
                    ticks++;
                }
                if (g.getState() != Game.State.PLAYING) break;
            }
            System.out.println("  " + g.getMap().getName() + ": peak enemies " + maxEnemies + ", peak projectiles " + maxProjectiles
                + ", state " + g.getState() + ", lives " + g.getLives() + ", wave " + g.getWave() + ", killed " + g.getEnemyManager().getTotalKilled());
            overallPeak = Math.max(overallPeak, maxEnemies);
            check(g.getState() == Game.State.PLAYING || g.getState() == Game.State.VICTORY, "stress game ran to the end");
        }
        long ms = System.currentTimeMillis() - start;
        System.out.println("  stress time: " + ms + " ms");
        check(overallPeak > 50, "stress produced a real rush (peak " + overallPeak + ")");
        check(true, "stress completed without exceptions");
    }

    /** Every tower and hero fully upgraded, abilities spammed (targeted ones at a track point), late waves: no exceptions, sane state. */
    private static void stressMaxedRoster() {
        long start = System.currentTimeMillis();
        for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
            Game g = newGame(m);
            g.setHeroLimit(Integer.MAX_VALUE);   // the whole roster on one map
            g.setInvincible(true);
            g.setGlobalEnemySpeedMultiplier(0.35);
            g.addCash(5_000_000, null);
            for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);
            int placed = 0;
            TowerType[] all = TowerType.purchasable();
            outer:
            for (Path r : g.getMap().getRoutes()) {
                for (double d = 80; d < r.getTotalLength(); d += 60) {
                    Vec dir = r.directionAt(d);
                    for (int side = -1; side <= 1; side += 2) {
                        Vec p = r.positionAt(d).add(new Vec(-dir.y, dir.x).scale(side * 75));
                        if (placed >= all.length) break outer;
                        if (g.getTowerManager().canPlace(all[placed], p)) {
                            Tower t = g.placeTower(all[placed], p);
                            while (g.upgradeTower(t)) { /* max out */ }
                            placed++;
                        }
                    }
                }
            }
            check(placed == all.length, g.getMap().getName() + " fits the whole roster (" + placed + ")");
            for (int k = 1; k < 94; k++) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
            int peakDrones = 0, peakZones = 0, peakWalkers = 0;
            for (int wave = 94; wave <= 100; wave++) {
                g.getWaveManager().endWave();
                g.getEnemyManager().clear();
                check(g.startNextWave(), "start wave " + wave);
                int ticks = 0;
                while (g.getWaveManager().isWaveActive() && ticks < 60 * 120 && g.getState() == Game.State.PLAYING) {
                    g.step(Game.DT);
                    if (ticks % 60 == 0) {
                        for (Tower t : new ArrayList<>(g.getTowerManager().getTowers())) {
                            if (!t.isAbilityReady()) continue;
                            if (t.getAbility().needsTarget) g.activateAbility(t, g.getMap().getRoutes().get(0).positionAt(400));
                            else g.activateAbility(t);
                        }
                    }
                    peakDrones = Math.max(peakDrones, g.getEffects().getDrones().size());
                    peakZones = Math.max(peakZones, g.getEffects().getZones().size());
                    peakWalkers = Math.max(peakWalkers, g.getEffects().getWalkers().size());
                    g.getEvents().clear();
                    ticks++;
                }
                if (g.getState() != Game.State.PLAYING) break;
            }
            check(g.getState() == Game.State.PLAYING || g.getState() == Game.State.VICTORY, "maxed roster stress ended in a sane state");
            check(peakDrones > 0 && peakWalkers > 0, g.getMap().getName() + " primitives were exercised (drones " + peakDrones + ", walkers " + peakWalkers + ", zones " + peakZones + ")");
            System.out.println("  " + g.getMap().getName() + ": maxed roster, wave " + g.getWave() + ", killed " + g.getEnemyManager().getTotalKilled()
                + ", drones " + peakDrones + ", walkers " + peakWalkers);
        }
        System.out.println("  maxed-roster stress time: " + (System.currentTimeMillis() - start) + " ms");
    }
}
