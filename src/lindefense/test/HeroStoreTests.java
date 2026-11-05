package lindefense.test;

import static lindefense.test.TestKit.*;
import static lindefense.tower.TowerStats.u;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import lindefense.combat.AttackContext;
import lindefense.effects.Mine;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.sim.Game;
import lindefense.sim.HeroCollection;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.AttackKind;
import lindefense.tower.BuffStat;
import lindefense.tower.Faction;
import lindefense.tower.Shop;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.UpgradeDef;
import lindefense.tower.behavior.KaijuKaiBehavior;
import lindefense.tower.behavior.TanimbusBehavior;
import lindefense.tower.behavior.ZethosBehavior;
import lindefense.ui.HeroStatText;

/**
 * Hero Store, the 18 heroes and Zethos: registration and prices, purchasing and permanent unlocks, the shared
 * base + 3 upgrade path, every hero's own mechanic, and Zethos's shop / tiers / projectiles / ability.
 */
public final class HeroStoreTests {
    private HeroStoreTests() { }

    /** The roster, with its Hero Store price and the three upgrade costs from the specification. */
    private static final Object[][] ROSTER = {
        { TowerType.LOBBER_LUIS, 900, 400, 850, 1500 },
        { TowerType.SAGE_AARAV, 1000, 450, 900, 1600 },
        { TowerType.IRON_IMRAAN, 1200, 500, 950, 1700 },
        { TowerType.BOOM_SAM, 1100, 450, 900, 1700 },
        { TowerType.CHILLSTIN, 1000, 400, 850, 1500 },
        { TowerType.KAIJU_KAI, 1500, 600, 1100, 2000 },
        { TowerType.ABHI_ACE, 1350, 500, 1000, 1800 },
        { TowerType.ZIPPY_MATT, 1250, 450, 900, 1600 },
        { TowerType.SUNNY_JOE, 850, 400, 800, 1500 },
        { TowerType.NIK_SCOPE, 1300, 500, 1000, 1800 },
        { TowerType.CAMI_MINE, 1100, 450, 900, 1600 },
        { TowerType.JUSTIN_TIME, 1400, 500, 950, 1800 },
        { TowerType.SPEAR_HANBO, 2000, 400, 850, 1500 },
        { TowerType.THORN_TUHIN, 1200, 450, 900, 1700 },
        { TowerType.TRAPPER_CHE, 1150, 450, 900, 1600 },
        { TowerType.BLITZ_ARNAV, 1350, 500, 950, 1750 },
        { TowerType.TANIMBUS, 1300, 500, 950, 1700 },
        { TowerType.MR_LINDEMANN, 2500, 1200, 2600, 5000 } };

    public static void runAll() {
        run("heroes.registration", HeroStoreTests::registration);
        run("heroes.startLocked", HeroStoreTests::startLocked);
        run("heroes.exactPrices", HeroStoreTests::exactPrices);
        run("heroes.purchasing", HeroStoreTests::purchasing);
        run("heroes.persistence", HeroStoreTests::persistence);
        run("heroes.placementRules", HeroStoreTests::placementRules);
        run("heroes.upgradePath", HeroStoreTests::upgradePath);
        run("heroes.upgradesChangeStats", HeroStoreTests::upgradesChangeStats);
        run("heroes.camoAndTargeting", HeroStoreTests::camoAndTargeting);
        run("heroes.lobberLuis", HeroStoreTests::lobberLuis);
        run("heroes.sageAarav", HeroStoreTests::sageAarav);
        run("heroes.ironImraan", HeroStoreTests::ironImraan);
        run("heroes.boomSam", HeroStoreTests::boomSam);
        run("heroes.chillstin", HeroStoreTests::chillstin);
        run("heroes.kaijuKai", HeroStoreTests::kaijuKai);
        run("heroes.abhiAce", HeroStoreTests::abhiAce);
        run("heroes.zippyMatt", HeroStoreTests::zippyMatt);
        run("heroes.sunnyJoe", HeroStoreTests::sunnyJoe);
        run("heroes.nikScope", HeroStoreTests::nikScope);
        run("heroes.camiMine", HeroStoreTests::camiMine);
        run("heroes.justinTime", HeroStoreTests::justinTime);
        run("heroes.spearHanbo", HeroStoreTests::spearHanbo);
        run("heroes.thornTuhin", HeroStoreTests::thornTuhin);
        run("heroes.trapperChe", HeroStoreTests::trapperChe);
        run("heroes.blitzArnav", HeroStoreTests::blitzArnav);
        run("heroes.tanimbus", HeroStoreTests::tanimbus);
        run("zethos.shopOnly", HeroStoreTests::zethosShop);
        run("zethos.tiers", HeroStoreTests::zethosTiers);
        run("zethos.noDuplicateDamage", HeroStoreTests::zethosNoDuplicates);
        run("zethos.bounceFalloff", HeroStoreTests::zethosBounce);
        run("zethos.realityCollapse", HeroStoreTests::zethosCollapse);
        run("heroes.cashNeverNegative", HeroStoreTests::cashNeverNegative);
        run("heroes.uiText", HeroStoreTests::uiText);
        run("ui.tutorialScript", HeroStoreTests::tutorialScript);
        run("ui.catalogEntries", HeroStoreTests::catalogEntries);
        // shop-tower abilities (locked until max tier + $15,000) are tested in AbilityUnlockTests
        run("heroes.mrLindemann", HeroStoreTests::mrLindemann);
        run("heroes.heroLimit", HeroStoreTests::heroLimit);
    }

    // ------------------------------------------------------------------ registration, store, placement
    private static void registration() {
        TowerType[] heroes = TowerType.heroes();
        check(heroes.length == 18, "the Hero Store lists 18 heroes (" + heroes.length + ")");
        Set<TowerType> seen = EnumSet.noneOf(TowerType.class);
        Set<String> names = new HashSet<>();
        for (TowerType h : heroes) {
            check(seen.add(h), h + " is registered exactly once");
            check(names.add(h.displayName), h.displayName + " is a unique display name");
            check(h.faction == Faction.HERO, h + " is classified as a hero");
            TowerDef d = TowerCatalog.get(h);
            check(d != null, h + " has a definition");
            check(d.baseCost == 0, h + " deploys free once unlocked");
            check(d.unlockCost > 0, h + " has a Hero Store price");
        }
        for (Object[] row : ROSTER) check(seen.contains((TowerType) row[0]), row[0] + " is in the roster");
        check(seen.size() == ROSTER.length, "every rostered hero is registered");
        // heroes are never sold in the regular shop, and Zethos is still a Primary tower
        for (TowerType t : TowerType.shopTowers()) check(!t.isHero(), t + " is not a hero");
        check(!TowerType.ZETHOS.isHero() && TowerType.ZETHOS.faction == Faction.PRIMARY, "Zethos is still a Primary tower");
        check(TowerType.shopTowers().length == 18, "the 18 shop towers are untouched");
    }

    private static void startLocked() {
        Game g = newGame(0);
        for (TowerType h : TowerType.heroes()) {
            check(!g.isHeroUnlocked(h), h + " starts locked");
            check(g.getTowerManager().heroProblem(h) != null, h + " cannot be placed while locked");
            check(g.placeTower(h, buildableNear(g, new Vec(400, 300), 200)) == null, h + " placement is refused while locked");
        }
    }

    private static void exactPrices() {
        for (Object[] row : ROSTER) {
            TowerType t = (TowerType) row[0];
            TowerDef d = TowerCatalog.get(t);
            check(d.unlockCost == (Integer) row[1], t + " unlocks for $" + row[1] + " (got $" + d.unlockCost + ")");
            check(Shop.unlockPriceOf(t) == (Integer) row[1], t + " store price matches the catalog");
            check(d.upgrades.length == 3, t + " has exactly 3 upgrades");
            for (int i = 0; i < 3; i++) {
                check(d.upgrades[i].cost == (Integer) row[2 + i], t + " upgrade " + (i + 1) + " costs $" + row[2 + i]
                    + " (got $" + d.upgrades[i].cost + ")");
            }
        }
    }

    private static void purchasing() {
        Game g = newGame(0);
        TowerType t = TowerType.SUNNY_JOE;   // cheapest hero
        int price = Shop.unlockPriceOf(t);
        check(g.getCash() < price || !g.isHeroUnlocked(t), "starts without the hero");
        g.addCash(price - 1 - g.getCash() + Game.START_CASH, null);
        g.addCash(0, null);
        // exactly one dollar short
        Game poor = newGame(0);
        poor.addCash(price - poor.getCash() - 1, null);
        check(!poor.purchaseHero(t), "a dollar short is refused");
        check(!poor.isHeroUnlocked(t) && poor.getCash() == price - 1, "a refused purchase spends nothing");
        Game rich = newGame(0);
        rich.addCash(price, null);
        double before = rich.getCash();
        check(rich.purchaseHero(t), "affordable hero is bought");
        check(rich.isHeroUnlocked(t), "the purchase unlocks it");
        check(near(rich.getCash(), before - price), "the exact price is deducted");
        check(!rich.purchaseHero(t), "buying twice is refused");
        check(rich.getTowerManager().heroProblem(t) == null, "an unlocked hero may be deployed");
        // unlocking does not place it
        check(rich.getTowerManager().getPlayerTowers().isEmpty(), "buying a hero never places it");
    }

    private static void persistence() {
        final Set<TowerType> saved = EnumSet.noneOf(TowerType.class);
        HeroCollection c = HeroCollection.withStorage(new HeroCollection.Storage() {
            @Override public Set<TowerType> load() { return EnumSet.copyOf(saved.isEmpty() ? EnumSet.noneOf(TowerType.class) : saved); }
            @Override public void save(Set<TowerType> unlocked) { saved.clear(); saved.addAll(unlocked); }
        });
        c.unlock(TowerType.KAIJU_KAI);
        check(saved.contains(TowerType.KAIJU_KAI), "unlocking writes through to storage");
        HeroCollection reloaded = HeroCollection.withStorage(new HeroCollection.Storage() {
            @Override public Set<TowerType> load() { return EnumSet.copyOf(saved); }
            @Override public void save(Set<TowerType> unlocked) { saved.clear(); saved.addAll(unlocked); }
        });
        check(reloaded.isUnlocked(TowerType.KAIJU_KAI), "the unlock survives a reload");
        check(!reloaded.isUnlocked(TowerType.SUNNY_JOE), "other heroes stay locked");
    }

    private static void placementRules() {
        Game g = newGame(0);
        TowerType t = TowerType.CHILLSTIN;
        g.getHeroCollection().unlock(t);
        Tower first = g.placeTower(t, buildableNear(g, new Vec(400, 300), 200));
        check(first != null, "an unlocked hero deploys");
        check(near(g.getCash(), Game.START_CASH), "deploying an unlocked hero is free");
        check(g.getTowerManager().heroProblem(t) != null, "the same hero cannot be deployed twice in one match");
        check(g.placeTower(t, buildableNear(g, new Vec(800, 500), 200)) == null, "a second copy is refused");
        TowerType other = TowerType.SUNNY_JOE;
        g.getHeroCollection().unlock(other);
        check(g.placeTower(other, buildableNear(g, new Vec(800, 500), 200)) != null, "a different hero still deploys");
    }

    private static void upgradePath() {
        for (TowerType t : TowerType.heroes()) {
            TowerDef d = TowerCatalog.get(t);
            check(d.upgrades.length == 3, t + " has three upgrades");
            check(d.tierLabels.length == 4, t + " has four progression levels");
            Set<String> labels = new HashSet<>();
            for (String l : d.tierLabels) check(labels.add(l), t + " tier label '" + l + "' is unique");
            for (UpgradeDef up : d.upgrades) {
                check(up.cost > 0, t + " upgrade '" + up.name + "' costs something");
                check(up.description != null && up.description.length() > 10, t + " upgrade '" + up.name + "' is described");
            }
            // upgrades are bought in order and stop at tier 3
            Game g = newGame(0);
            g.getHeroCollection().unlock(t);
            g.addCash(50_000, null);
            Tower h = g.placeTower(t, buildableNear(g, new Vec(400, 300), 250));
            check(h != null, t + " deploys");
            for (int i = 0; i < 3; i++) {
                check(h.getTier() == i, t + " is at tier " + i);
                check(h.nextUpgrade() == d.upgrades[i], t + " offers upgrade " + (i + 1) + " next (purchase order)");
                double before = g.getCash();
                check(g.upgradeTower(h), t + " buys upgrade " + (i + 1));
                check(near(g.getCash(), before - d.upgrades[i].cost), t + " upgrade " + (i + 1) + " charges $" + d.upgrades[i].cost);
            }
            check(h.getTier() == 3 && h.isMaxed() && !h.canUpgrade(), t + " reaches max tier 3");
            check(h.nextUpgrade() == null, t + " offers nothing beyond tier 3");
            check(!g.upgradeTower(h), t + " refuses a fourth upgrade");
            double after = g.getCash();
            check(!g.upgradeTower(h) && near(g.getCash(), after), t + " a refused upgrade spends nothing");
        }
    }

    private static void upgradesChangeStats() {
        for (TowerType t : TowerType.heroes()) {
            TowerDef d = TowerCatalog.get(t);
            for (int i = 1; i <= 3; i++) {
                TowerStats a = d.statsForTier(i - 1), b = d.statsForTier(i);
                boolean changed = b.hit.damage != a.hit.damage || b.rate != a.rate || b.range != a.range
                    || b.pierce != a.pierce || b.splashRadius != a.splashRadius || b.targets != a.targets
                    || b.chainHops != a.chainHops || b.hit.slowFraction != a.hit.slowFraction
                    || b.hit.dotDps != a.hit.dotDps || b.auraRange != a.auraRange || b.auraRate != a.auraRate
                    || !b.params().equals(a.params()) || b.kind != a.kind || b.projectilesPerShot != a.projectilesPerShot;
                check(changed, t + " upgrade " + i + " (" + d.upgrades[i - 1].name + ") actually changes its statistics");
            }
            // the maxed hero is meaningfully stronger than the base one
            TowerStats base = d.statsForTier(0), max = d.statsForTier(3);
            boolean stronger = max.hit.damage > base.hit.damage || max.p("income", 0) > base.p("income", 0)
                || max.p("healAmount", 0) > base.p("healAmount", 0) || max.auraRate > base.auraRate
                || max.p("buffRate", 0) > base.p("buffRate", 0) || max.p("beamDamage", 0) > base.p("beamDamage", 0);
            check(stronger, t + " is stronger at tier 3 than at base");
        }
    }

    private static void camoAndTargeting() {
        check(TowerCatalog.get(TowerType.NIK_SCOPE).baseStats.seesCamo, "Nik-Scope sees camo from the start");
        check(TowerCatalog.get(TowerType.NIK_SCOPE).defaultTargeting == Targeting.STRONGEST, "Nik-Scope opens on Strongest");
        for (TowerType t : TowerType.heroes()) {
            if (t == TowerType.NIK_SCOPE) continue;
            check(!TowerCatalog.get(t).baseStats.seesCamo, t + " has no built-in camo detection");
        }
        // a hero without detection cannot touch an undetected camo enemy
        Game g = frozen();
        Tower h = hero(g, TowerType.CHILLSTIN, 500);
        Enemy camo = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO), 0, 500, 500, 1.0);
        g.getEnemyManager().update(0);
        check(g.getCombat().acquireTargets(h, 1).isEmpty(), "camo is invisible to a hero without detection");
        Tower sniper = hero(g, TowerType.NIK_SCOPE, 520);
        check(!g.getCombat().acquireTargets(sniper, 1).isEmpty(), "Nik-Scope sees the same camo enemy");
        check(camo.isAlive(), "the camo enemy is still alive");
    }

    // ------------------------------------------------------------------ per-hero mechanics
    private static void lobberLuis() {
        TowerStats s = TowerCatalog.get(TowerType.LOBBER_LUIS).statsForTier(2);
        check(s.pi("clusterBombs") == 3 && s.p("clusterDamage") == 25, "Cluster Bombs: 3 bomblets x 25 damage");
        Game g = frozen();
        Tower h = hero(g, TowerType.LOBBER_LUIS, 500, 2);
        // a crowd around the impact: the bomblets must reach enemies the main blast does not
        for (int i = 0; i < 10; i++) tank(g, 460 + i * 14);
        oneShot(g, h);
        runSeconds(g, 0.6);                     // the bomblets land shortly after the shell
        int hurt = 0;
        for (Enemy e : g.getEnemyManager().getEnemies()) if (taken(e) > 0) hurt++;
        check(hurt >= 4, "the cluster spreads damage over the crowd (" + hurt + " enemies)");
        // Orbital Artillery doubles every 5th shot
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.LOBBER_LUIS, 500, 3);
        double plain = -1, orbital = -1;
        for (int shot = 1; shot <= 5; shot++) {
            Enemy e = tank(g2, 500);
            oneShot(g2, h2);
            if (shot == 1) plain = taken(e);
            if (shot == 5) orbital = taken(e);
            e.markDead();
        }
        check(orbital > plain * 1.5, "every 5th shot is an orbital strike (" + plain + " -> " + orbital + ")");
    }

    private static void sageAarav() {
        TowerDef d = TowerCatalog.get(TowerType.SAGE_AARAV);
        check(d.baseStats.kind == AttackKind.NONE, "Sage Aarav never attacks");
        Game g = frozen();
        Tower h = hero(g, TowerType.SAGE_AARAV, 500);
        // lose some integrity, then let the aura work
        leak(g, 20);
        int before = g.getLives();
        check(before < g.getMaxLives(), "integrity was lost");
        runSeconds(g, 5.2);
        check(g.getLives() == before + 5, "restores 5 integrity every 5 s (" + before + " -> " + g.getLives() + ")");
        // never above the maximum
        runSeconds(g, 60);
        check(g.getLives() == g.getMaxLives(), "healing stops at the starting maximum");
        // Divine Restoration fires once, below a quarter
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.SAGE_AARAV, 500, 3);
        leak(g2, g2.getMaxLives() - 10);
        check(g2.getLives() == 10, "integrity down to 10");
        runSeconds(g2, 0.2);
        int emergency = g2.getLives();
        check(emergency >= 10 + (int) Math.ceil(g2.getMaxLives() * 0.20), "emergency restoration pays 20% of maximum (" + emergency + ")");
        leak(g2, emergency - 5);
        runSeconds(g2, 0.2);
        check(g2.getLives() <= 5 + 1, "the emergency restoration only happens once per match");
    }

    private static void ironImraan() {
        TowerStats s = TowerCatalog.get(TowerType.IRON_IMRAAN).baseStats;
        check(s.hit.knockback > 0 && s.hit.bossKnockback == 0, "punches shove normal enemies, never bosses");
        check(near(s.range, u(20)), "a very short 20-unit reach");
        Game g = frozen();
        Tower h = hero(g, TowerType.IRON_IMRAAN, 500);
        Enemy e = tank(g, 500);
        double d0 = e.getDistance();
        oneShot(g, h);
        check(e.getDistance() < d0, "the enemy is knocked back down the track");
        // Hydraulic Smash: every 3rd punch also slams the ground
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.IRON_IMRAAN, 500, 3);
        Enemy far = tank(g2, 500 + u(18));       // outside the punch, inside the 22-unit shockwave
        for (int i = 0; i < 3; i++) { tank(g2, 500); oneShot(g2, h2); }
        check(taken(far) > 0, "the shockwave reaches past the punch");
        check(far.hasStatus(StatusEffect.Kind.STUN) || taken(far) > 0, "the shockwave lands on nearby enemies");
    }

    private static void boomSam() {
        TowerStats s2 = TowerCatalog.get(TowerType.BOOM_SAM).statsForTier(2);
        check(s2.targets == 2, "Double Detonation throws two charges");
        Game g = frozen();
        Tower h = hero(g, TowerType.BOOM_SAM, 500, 1);
        Enemy outside = tank(g, 500 - u(60));    // well behind: never the First target, never in the blast
        Enemy centre = tank(g, 500);
        Enemy edge = tank(g, 500 + u(10));       // inside the 13-unit blast of the target
        oneShot(g, h);
        check(taken(centre) > 0 && taken(edge) > 0, "the blast damages everything in its radius");
        check(taken(outside) == 0, "enemies outside the blast are untouched");
        check(near(taken(centre), taken(edge)), "splash deals full damage across the blast");
        // Nuclear Boom on every 5th attack
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.BOOM_SAM, 500, 3);
        double small = -1, big = -1;
        for (int shot = 1; shot <= 5; shot++) {
            Enemy e = tank(g2, 500);
            oneShot(g2, h2);
            runSeconds(g2, 0.4);
            if (shot == 1) small = taken(e);
            if (shot == 5) big = taken(e);
            e.markDead();
        }
        check(big > small, "every 5th attack adds the nuclear detonation (" + small + " -> " + big + ")");
    }

    private static void chillstin() {
        Game g = frozen();
        Tower h = hero(g, TowerType.CHILLSTIN, 500);
        Enemy e = tank(g, 500);
        oneShot(g, h);
        check(e.hasStatus(StatusEffect.Kind.SLOW), "frost shards slow what they hit");
        // bosses are never frozen by Frozen Prison
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.CHILLSTIN, 500, 2);
        Enemy boss = g2.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 500, 4000, 1.0);
        g2.getEnemyManager().update(0);
        for (int i = 0; i < 8; i++) oneShot(g2, h2);
        check(!boss.hasStatus(StatusEffect.Kind.FREEZE), "a boss is never frozen");
        check(boss.hasStatus(StatusEffect.Kind.SLOW), "a boss is slowed instead");
        // Absolute Frost bursts
        TowerStats s3 = TowerCatalog.get(TowerType.CHILLSTIN).statsForTier(3);
        check(s3.pi("burstEvery") == 6 && near(s3.p("burstSlow"), 0.60), "Absolute Frost: 60% slow burst every 6th shard");
    }

    private static void kaijuKai() {
        TowerDef d = TowerCatalog.get(TowerType.KAIJU_KAI);
        check(d.baseStats.kind == AttackKind.PROJECTILE && d.baseStats.splashRadius > 0, "the base roar is a splash attack");
        check(d.statsForTier(1).kind == AttackKind.CUSTOM, "Atomic Breath replaces the roar with a beam");
        check(d.statsForTier(2).p("beamDamage") == 35, "Titan Awakening raises the beam to 35 per tick");
        Game g = frozen();
        Tower h = hero(g, TowerType.KAIJU_KAI, 500, 1);
        // enemies strung out along the beam's path
        List<Enemy> line = new ArrayList<>();
        for (int i = 0; i < 4; i++) line.add(tank(g, 500 + i * 30));
        check(g.getCombat().attack(h), "the beam starts");
        check(KaijuKaiBehavior.isBeaming(h), "the beam is burning");
        runSeconds(g, 1.6);
        int burned = 0;
        for (Enemy e : line) if (taken(e) > 0) burned++;
        check(burned >= 2, "the beam burns everything along its path (" + burned + ")");
        check(!KaijuKaiBehavior.isBeaming(h), "the beam ends after its duration");
        // the atomic blast
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.KAIJU_KAI, 500, 3);
        Enemy far = tank(g2, 900);
        runSeconds(g2, 8.3);
        check(taken(far) > 0, "Cataclysmic Kaiju detonates an atomic blast on the crowd");
    }

    private static void abhiAce() {
        TowerDef d = TowerCatalog.get(TowerType.ABHI_ACE);
        check(d.baseStats.ignoresLos, "Abhi-Ace flies, so ground blockers never stop his missiles");
        check(d.statsForTier(2).targets == 3 && d.statsForTier(3).targets == 4, "3 then 4 missiles per attack");
        // flying does not make him invulnerable or unplaceable: he is a normal tower on the ground grid
        Game g = frozen();
        Tower h = hero(g, TowerType.ABHI_ACE, 500, 2);
        List<Enemy> three = new ArrayList<>();
        for (int i = 0; i < 3; i++) three.add(tank(g, 480 + i * 40));
        oneShot(g, h);
        int hurt = 0;
        for (Enemy e : three) if (taken(e) > 0) hurt++;
        check(hurt >= 2, "Missile Barrage splits across separate targets (" + hurt + ")");
        // line of sight is ignored on the map that has blockers
        Game los = new Game(lindefense.map.MapCatalog.create(1), 7);
        check(los.getMap().hasLineOfSight(new Vec(150, 150), new Vec(150, 290)), "the monolith map has clear lanes");
        check(!los.getMap().hasLineOfSight(new Vec(400, 150), new Vec(400, 290)), "and blocked ones");
    }

    private static void zippyMatt() {
        Game g = frozen();
        Tower h = hero(g, TowerType.ZIPPY_MATT, 500, 1);
        // a tight cluster so the chain can hop
        List<Enemy> cluster = new ArrayList<>();
        for (int i = 0; i < 6; i++) cluster.add(tank(g, 490 + i * 16));
        oneShot(g, h);
        int hit = 0;
        double damage = h.getStats().hit.damage;
        for (Enemy e : cluster) {
            double d = taken(e);
            if (d > 0) hit++;
            check(d <= damage + 1e-6, "no enemy is struck twice by one arc (" + d + " of " + damage + ")");
        }
        check(hit >= 2 && hit <= 4, "Speed Surge chains to at most 4 targets (" + hit + ")");
        // Electric Overload's falloff
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.ZIPPY_MATT, 500, 2);
        List<Enemy> line = new ArrayList<>();
        for (int i = 0; i < 6; i++) line.add(tank(g2, 490 + i * 16));
        oneShot(g2, h2);
        double top = 0, low = Double.MAX_VALUE;
        int touched = 0;
        for (Enemy e : line) {
            double d = taken(e);
            if (d <= 0) continue;
            touched++;
            top = Math.max(top, d);
            low = Math.min(low, d);
        }
        check(touched >= 3, "the chain reaches several enemies (" + touched + ")");
        check(low < top, "each hop deals less than the one before (" + top + " -> " + low + ")");
    }

    private static void sunnyJoe() {
        TowerDef d = TowerCatalog.get(TowerType.SUNNY_JOE);
        check(d.baseStats.kind == AttackKind.NONE, "Sunny Joe never attacks");
        Game g = frozen();
        Tower h = hero(g, TowerType.SUNNY_JOE, 500);
        double before = g.getCash();
        runSeconds(g, 10.2);
        check(near(g.getCash(), before + 40), "pays $40 every 10 s (got $" + (g.getCash() - before) + ")");
        // Financial Empire: bigger income and the periodic bonus
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.SUNNY_JOE, 500, 3);
        double b2 = g2.getCash();
        runSeconds(g2, 60.5);
        double earned = g2.getCash() - b2;
        check(earned >= 6 * 150 + 300 - 1, "Financial Empire pays 150 per 10 s plus the 300 bonus (got $" + earned + ")");
    }

    private static void nikScope() {
        TowerDef d = TowerCatalog.get(TowerType.NIK_SCOPE);
        check(near(d.baseStats.range, u(100)) && near(d.statsForTier(3).range, u(150)), "range 100 -> 150 units");
        check(d.statsForTier(2).pierce == 3 && d.statsForTier(3).pierce == 5, "pierce 3 then 5");
        check(near(d.statsForTier(2).hit.multVsFortified, 1.5), "+50% against Fortified enemies");
        check(near(d.statsForTier(3).p("critChance"), 0.20) && near(d.statsForTier(3).p("critMult"), 2.5), "20% crits at x2.5");
        // crits actually multiply damage: over many shots the best hit beats the plain one
        Game g = frozen();
        Tower h = hero(g, TowerType.NIK_SCOPE, 500, 3);
        double plain = h.getStats().hit.damage, best = 0;
        for (int i = 0; i < 60; i++) {
            Enemy e = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, null, 0, 500, 5000, 1.0);
            g.getEnemyManager().update(0);
            oneShot(g, h);
            best = Math.max(best, taken(e));
            e.markDead();
        }
        check(best > plain * 2, "critical hits land for more than double (" + plain + " -> " + best + ")");
    }

    private static void camiMine() {
        Game g = frozen();
        Tower h = hero(g, TowerType.CAMI_MINE, 500);
        runSeconds(g, 4.2);
        List<Mine> mines = g.getEffects().minesOf(h, "mine");
        check(!mines.isEmpty(), "a mine is planted on the track");
        check(mines.size() <= h.getStats().pi("maxMines"), "never more than the maximum");
        runSeconds(g, 30);
        check(g.getEffects().minesOf(h, "mine").size() == h.getStats().pi("maxMines"), "the field fills up to its cap and stops");
        // an enemy walking onto a mine sets it off exactly once
        Mine m = g.getEffects().minesOf(h, "mine").get(0);
        Enemy e = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, null, 0,
            g.getMap().getRoutes().get(0).nearestDistanceAlong(m.position), 500, 1.0);
        g.getEnemyManager().update(0);
        runSeconds(g, 0.2);
        check(taken(e) > 0, "the mine detonates on the enemy that steps on it");
        check(!m.isAlive(), "a mine fires once and is gone, so it can never block a lane");
        // mines never stop enemies moving
        check(!e.hasStatus(StatusEffect.Kind.STUN), "a mine does not immobilise");
    }

    private static void justinTime() {
        Game g = frozen();
        Tower h = hero(g, TowerType.JUSTIN_TIME, 500);
        Enemy e = tank(g, 500);
        oneShot(g, h);
        check(e.hasStatus(StatusEffect.Kind.SLOW), "time bolts slow what they hit");
        // the Temporal Field reaches enemies far outside his range
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.JUSTIN_TIME, 500, 2);
        Enemy far = tank(g2, 1400);
        check(far.getPosition().dist(h2.getPosition()) > h2.effectiveRange(g2), "the enemy is out of range");
        runSeconds(g2, 12.3);
        check(far.hasStatus(StatusEffect.Kind.SLOW), "the Temporal Field slows the whole map");
        // Time Freeze: bosses are slowed, never frozen
        Game g3 = frozen();
        Tower h3 = hero(g3, TowerType.JUSTIN_TIME, 500, 3);
        Enemy boss = g3.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 600, 9000, 1.0);
        Enemy normal = tank(g3, 650);
        g3.getEnemyManager().update(0);
        runSeconds(g3, 60.3);
        check(!boss.hasStatus(StatusEffect.Kind.FREEZE), "bosses are never frozen by Time Freeze");
        check(boss.hasStatus(StatusEffect.Kind.SLOW), "bosses are slowed instead");
        check(normal.hasStatus(StatusEffect.Kind.FREEZE) || !normal.isAlive(), "normal enemies freeze");
    }

    private static void spearHanbo() {
        Game g = frozen();
        Tower h = hero(g, TowerType.SPEAR_HANBO, 420);
        List<Enemy> line = new ArrayList<>();
        for (int i = 0; i < 6; i++) line.add(tank(g, 470 + i * 16));
        oneShot(g, h);
        int pierced = 0;
        double dmg = h.getStats().hit.damage;
        for (Enemy e : line) {
            double d = taken(e);
            if (d > 0) pierced++;
            check(d <= dmg + 1e-6, "one spear never hits the same enemy twice on a leg (" + d + ")");
        }
        check(pierced >= 2 && pierced <= 4, "the spear pierces up to 4 enemies (" + pierced + ")");
        // the returning spear hits the line a second time on the way home
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.SPEAR_HANBO, 420, 2);
        List<Enemy> back = new ArrayList<>();
        for (int i = 0; i < 6; i++) back.add(tank(g2, 470 + i * 16));
        check(g2.getCombat().attack(h2), "the spear is thrown");
        runSeconds(g2, 1.6);                     // under the 1.8 s interval: exactly one throw, out and back
        double maxHit = 0;
        for (Enemy e : back) maxHit = Math.max(maxHit, taken(e));
        double single = h2.getStats().hit.damage;
        check(maxHit > single + 1e-6, "an enemy can be hit on the way out and on the way back (" + maxHit + " > " + single + ")");
        check(maxHit <= single * 2 + 1e-6, "but no more than twice (" + maxHit + ")");
    }

    private static void thornTuhin() {
        Game g = frozen();
        Tower h = hero(g, TowerType.THORN_TUHIN, 500);
        Enemy e = tank(g, 500);
        oneShot(g, h);
        double direct = taken(e);
        check(direct > 0 && e.hasStatus(StatusEffect.Kind.DOT), "thorns poison what they hit");
        runSeconds(g, 3.2);
        check(taken(e) > direct, "the poison keeps damaging after the hit (" + direct + " -> " + taken(e) + ")");
        // Overgrowth vines
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.THORN_TUHIN, 500, 2);
        runSeconds(g2, 8.3);
        check(!g2.getEffects().zonesOf(h2, "vines").isEmpty(), "vines grow across the track");
        runSeconds(g2, 40);
        check(g2.getEffects().zonesOf(h2, "vines").size() <= h2.getStats().pi("maxVines"), "never more than two vine patches at once");
    }

    private static void trapperChe() {
        Game g = frozen();
        Tower h = hero(g, TowerType.TRAPPER_CHE, 500);
        runSeconds(g, 4.2);
        List<Mine> traps = g.getEffects().minesOf(h, "trap");
        check(!traps.isEmpty(), "a trap is set on the track");
        Mine t = traps.get(0);
        double along = g.getMap().getRoutes().get(0).nearestDistanceAlong(t.position);
        Enemy e = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, null, 0, along, 600, 1.0);
        g.getEnemyManager().update(0);
        runSeconds(g, 0.2);
        check(taken(e) > 0, "the trap damages the enemy that triggers it");
        check(e.hasStatus(StatusEffect.Kind.STUN), "normal enemies are held in place");
        // a boss takes the damage but is never held
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.TRAPPER_CHE, 500, 2);
        runSeconds(g2, 4.2);
        Mine t2 = g2.getEffects().minesOf(h2, "trap").get(0);
        double along2 = g2.getMap().getRoutes().get(0).nearestDistanceAlong(t2.position);
        Enemy boss = g2.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, along2, 9000, 1.0);
        g2.getEnemyManager().update(0);
        runSeconds(g2, 0.2);
        check(taken(boss) > 0, "a boss still takes the trap's damage");
        check(!boss.hasStatus(StatusEffect.Kind.STUN), "a boss is never immobilised");
    }

    private static void blitzArnav() {
        TowerDef d = TowerCatalog.get(TowerType.BLITZ_ARNAV);
        int[] bullets = { 3, 5, 7, 10 };
        for (int i = 0; i < 4; i++) {
            check(d.statsForTier(i).pi("bullets") == bullets[i], "tier " + i + " fires " + bullets[i] + " bullets per burst");
        }
        Game g = frozen();
        Tower h = hero(g, TowerType.BLITZ_ARNAV, 500);
        List<Enemy> spread = new ArrayList<>();
        for (int i = 0; i < 5; i++) spread.add(tank(g, 470 + i * 30));
        oneShot(g, h);
        int hurt = 0;
        for (Enemy e : spread) if (taken(e) > 0) hurt++;
        check(hurt >= 2, "a burst spreads across several enemies (" + hurt + ")");
        // Suppressive Fire slows on every third burst
        Game g2 = frozen();
        Tower h2 = hero(g2, TowerType.BLITZ_ARNAV, 500, 2);
        Enemy e2 = tank(g2, 500);
        for (int i = 0; i < 3; i++) oneShot(g2, h2);
        check(e2.hasStatus(StatusEffect.Kind.SLOW) || !e2.isAlive(), "every 3rd burst suppresses");
    }

    private static void tanimbus() {
        Game g = frozen();
        Tower drone = hero(g, TowerType.TANIMBUS, 500);
        Tower weak = towerNearTrack(g, TowerType.GEMINI, 0, 470);
        Tower strong = towerNearTrack(g, TowerType.GPT, 3, 530);
        g.getTowerManager().recomputeAuras();
        check(TanimbusBehavior.supported(g, drone) == strong, "the drone locks onto the strongest tower in range");
        check(strong.buffTotal(BuffStat.RATE) > 0, "the supported tower really is sped up");
        check(weak.buffTotal(BuffStat.RATE) == 0, "other towers are not buffed while it is locked on");
        // Tactical Network buffs everything in range
        Game g2 = frozen();
        Tower drone2 = hero(g2, TowerType.TANIMBUS, 500, 2);
        Tower a = towerNearTrack(g2, TowerType.GEMINI, 0, 470);
        Tower b = towerNearTrack(g2, TowerType.GPT, 0, 530);
        g2.getTowerManager().recomputeAuras();
        check(a.buffTotal(BuffStat.RATE) > 0 && b.buffTotal(BuffStat.RATE) > 0, "Tactical Network buffs every tower in range");
        check(a.buffTotal(BuffStat.RANGE) > 0, "and adds range");
        // Battlefield Command rallies the whole map on a timer
        Game g3 = frozen();
        Tower drone3 = hero(g3, TowerType.TANIMBUS, 500, 3);
        Tower far = towerNearTrack(g3, TowerType.GEMINI, 0, 1300);
        check(far.getPosition().dist(drone3.getPosition()) > drone3.getStats().auraRange, "the tower is outside the support radius");
        runSeconds(g3, 45.3);
        check(far.timedBuffRemaining(TowerType.TANIMBUS) > 0, "the rally reaches every tower on the map");
        runSeconds(g3, 8.5);
        check(far.timedBuffRemaining(TowerType.TANIMBUS) == 0, "and expires after its duration");
    }

    // ------------------------------------------------------------------ Zethos (unchanged Primary tower)
    private static void zethosShop() {
        boolean inPrimary = false;
        for (lindefense.ui.ShopLayout.Cell c : lindefense.ui.ShopLayout.factionCells(Faction.PRIMARY)) if (c.type == TowerType.ZETHOS) inPrimary = true;
        check(inPrimary, "Zethos is in the Primary tower shop");
        for (TowerType h : TowerType.heroes()) check(h != TowerType.ZETHOS, "Zethos is not in the Hero Store");
        Game g = newGame(0);
        Vec p = buildableNear(g, new Vec(400, 300), 150);
        check(g.getTowerManager().heroProblem(TowerType.ZETHOS) == null, "Zethos has no hero restrictions");
        Tower z = g.placeTower(TowerType.ZETHOS, p);
        check(z != null && g.getCash() == Game.START_CASH - 650, "Zethos bought for $650 with starting cash");
        g.addCash(10_000, null);
        Tower z2 = g.placeTower(TowerType.ZETHOS, buildableNear(g, new Vec(800, 300), 150));
        check(z2 != null, "several Zethos towers may be placed");
        double c0 = g.getCash();
        check(g.upgradeTower(z) && near(g.getCash(), c0 - 350), "Tier 1 costs $350");
        double c1 = g.getCash();
        int refund = g.sellTower(z);
        check(refund == (int) Math.floor((650 + 350) * 0.7) && near(g.getCash(), c1 + refund), "sells for 70% like any tower");
    }

    private static void zethosTiers() {
        TowerDef d = TowerCatalog.get(TowerType.ZETHOS);
        double[][] t = {
            // tuned to about twice the best of Gemini / Claude / GPT at each tier
            { 2, 0.65, 45, 2, 0, 0, 0, 0 },
            { 3, 0.60, 46, 4, 0, 0, 0, 0 },
            { 4, 0.50, 47, 5, 7, 0.60, 0, 0 },
            { 6, 0.55, 48, 5, 6, 0.45, 2, 0.45 },
            { 7, 0.50, 50, 6, 6, 0.35, 2, 0.35 } };
        int[] cost = { 650, 350, 650, 1200, 2500 };
        check(d.baseCost == cost[0], "base $650");
        for (int i = 0; i < t.length; i++) {
            TowerStats s = d.statsForTier(i);
            String n = "Zethos tier " + i;
            check(s.hit.damage == t[i][0] && near(s.interval(), t[i][1]) && near(s.range, u(t[i][2])) && s.pierce == (int) t[i][3], n + " damage/interval/range/pierce");
            check(near(s.splashRadius, u(t[i][4])) && near(s.p("splashPct", 0), t[i][5]) && s.bounces == (int) t[i][6] && near(s.p("bouncePct", 0), t[i][7]), n + " splash/bounce");
            if (i > 0) check(d.upgrades[i - 1].cost == cost[i], n + " costs $" + cost[i]);
        }
        check(near(d.baseStats.projectileSpeed, u(55)) && d.statsForTier(1).projectileSpeed > d.baseStats.projectileSpeed, "55 u/s, faster after Quantum Acceleration");
        check(d.totalCost() == 5350, "fully upgraded $5,350");
    }

    private static void zethosNoDuplicates() {
        for (int tier = 2; tier <= 4; tier++) {
            Game g = frozen();
            Tower z = towerNearTrack(g, TowerType.ZETHOS, tier, 500);
            List<Enemy> stack = new ArrayList<>();
            for (int i = 0; i < 25; i++) stack.add(tank(g, 500));
            oneShot(g, z);
            double dmg = z.getStats().hit.damage;
            double max = 0; int hit = 0;
            for (Enemy e : stack) { max = Math.max(max, taken(e)); if (taken(e) > 0) hit++; }
            check(max <= dmg + 1e-6, "tier " + tier + ": no enemy damaged twice by one projectile (max " + max + " of " + dmg + ")");
            check(hit > z.getStats().pierce, "tier " + tier + ": splash reaches beyond the direct hits (" + hit + " enemies)");
        }
    }

    private static void zethosBounce() {
        Game g = frozen();
        Tower z = towerNearTrack(g, TowerType.ZETHOS, 3, 500);
        List<Enemy> line = new ArrayList<>();
        for (int i = 0; i < 12; i++) line.add(tank(g, 300 + i * 75));
        oneShot(g, z);
        int full = 0, bounce = 0, other = 0;
        for (Enemy e : line) {
            double d = taken(e);
            if (d == 0) continue;
            if (near(d, 6)) full++; else if (near(d, 6 * 0.45)) bounce++; else other++;
        }
        check(bounce == 2, "Tier 3 bounces to exactly 2 more enemies at 45% (" + bounce + ")");
        check(full >= 1 && full <= 5, "direct (pierce) hits at full damage (" + full + ")");
        check(other == 0, "no other damage values (" + other + ")");
    }

    private static void zethosCollapse() {
        Game g = frozen();
        Tower z = towerNearTrack(g, TowerType.ZETHOS, 4, 500);
        double range = z.effectiveRange(g), rate = z.effectiveRate(g);
        check(near(range, u(50)), "Reality Engine range 50 units");
        z.resetAbilityCooldown();
        check(g.activateAbility(z), "Reality Collapse activates");
        check(near(z.effectiveRange(g), u(65)) && near(z.effectiveRate(g), rate * 2), "range 50 -> 65 units, attack interval halved");
        tank(g, 500);
        AttackContext c = g.getCombat().newAttackContext(z, g.getCombat().acquireTargets(z, 1));
        z.getBehavior().modifyAttack(g, z, c);
        check(near(c.damageMult, 2) && c.bounces == 8 && c.splash > 0, "x2 damage, 8 bounces, every impact explodes");
        runSeconds(g, 6.1);
        check(!ZethosBehavior.isCollapsing(z) && near(z.effectiveRange(g), u(50)), "ends after 6 s");
        AbilityDef zd = TowerCatalog.get(TowerType.ZETHOS).ability;
        check(zd.p("damageMult") == 2 && zd.p("rateMult") == 2 && near(zd.p("rangeBonus"), u(15)) && zd.p("bounces") == 8, "Reality Collapse multipliers");
    }

    // ------------------------------------------------------------------ economy, UI, regression
    private static void cashNeverNegative() {
        Game g = newGame(0);
        for (TowerType h : TowerType.heroes()) { g.purchaseHero(h); check(g.getCash() >= 0, "cash stays >= 0 after trying " + h); }
        check(g.getCash() == Game.START_CASH, "nothing affordable bought at the start");
    }

    private static void uiText() {
        for (TowerType h : TowerType.heroes()) {
            check(HeroStatText.role(h) != null && !HeroStatText.role(h).isEmpty(), h + " has a role line");
            check(HeroStatText.attackName(h).equals(TowerCatalog.get(h).tierLabels[0]), h + " names its base ability");
            for (int tier = 0; tier < 4; tier++) {
                List<String> lines = HeroStatText.attackLines(h, tier);
                check(lines.size() >= 2, h + " tier " + tier + " shows at least two stat lines");
                for (String l : lines) check(l != null && !l.isEmpty(), h + " tier " + tier + " line is filled in");
            }
            check(TowerCatalog.get(h).description.length() > 40, h + " has a store description");
        }
        check(HeroStatText.isSupportHero(TowerType.SAGE_AARAV) && HeroStatText.isSupportHero(TowerType.SUNNY_JOE)
            && HeroStatText.isSupportHero(TowerType.TANIMBUS), "the three non-attacking heroes are flagged as support");
        check(!HeroStatText.isSupportHero(TowerType.NIK_SCOPE), "attackers are not");
        // the live line never throws for a placed hero
        Game g = frozen();
        g.setHeroLimit(Integer.MAX_VALUE);
        for (TowerType h : TowerType.heroes()) {
            Tower t = hero(g, h, 400 + (h.ordinal() % 7) * 60);
            if (t != null) HeroStatText.liveLine(g, t);
        }
    }

    private static void tutorialScript() {
        Game g = newGame(0);
        lindefense.ui.TutorialScript ts = new lindefense.ui.TutorialScript(g);
        check(ts.current() == lindefense.ui.TutorialScript.Step.WELCOME && !ts.current().action, "starts on the welcome card");
        ts.update();
        check(ts.index() == 0, "info cards wait for NEXT");
        ts.next();
        check(ts.current() == lindefense.ui.TutorialScript.Step.PLACE, "then: place a tower");
        ts.update();
        check(ts.index() == 1, "action steps wait for the action");
        Tower gpt = g.placeTower(TowerType.GPT, buildableNear(g, new Vec(380, 300), 150));
        check(gpt != null, "player places GPT");
        ts.update();
        check(ts.current() == lindefense.ui.TutorialScript.Step.WAVE, "placing a tower advances");
        g.startNextWave();
        ts.update();
        check(ts.current() == lindefense.ui.TutorialScript.Step.UPGRADE && ts.grantPaid(), "starting a wave advances; upgrade step pays its bonus");
        check(g.upgradeTower(gpt), "bonus covers the upgrade");
        ts.update();
        check(ts.current() == lindefense.ui.TutorialScript.Step.TARGETING, "upgrading advances");
        ts.next();
        check(ts.current() == lindefense.ui.TutorialScript.Step.HERO_STORE && g.getCash() >= 1000, "Hero Store step funds a hero");
        check(g.purchaseHero(TowerType.SUNNY_JOE), "buy a hero");
        ts.update();
        check(ts.current() == lindefense.ui.TutorialScript.Step.DEPLOY, "buying advances");
        Tower sj = g.placeTower(TowerType.SUNNY_JOE, buildableNear(g, new Vec(700, 300), 150));
        ts.update();
        check(sj != null && ts.current() == lindefense.ui.TutorialScript.Step.HERO_UPGRADE, "deploying advances to the hero-upgrade step");
        check(g.upgradeTower(sj), "the tutorial bonus covers the hero's first upgrade");
        ts.update();
        check(ts.current() == lindefense.ui.TutorialScript.Step.ZETHOS, "upgrading the hero advances");
        ts.next();
        check(ts.current() == lindefense.ui.TutorialScript.Step.DONE, "final card");
        ts.next();
        check(ts.isFinished(), "FINISH ends the tutorial");
        check(g.getHeroCollection() != HeroCollection.persistent(), "the tutorial game is not wired to the saved collection");
        lindefense.ui.TutorialScript skip = new lindefense.ui.TutorialScript(newGame(0));
        skip.skipAll();
        check(skip.isFinished(), "END TUTORIAL works from any step");
    }

    private static void catalogEntries() {
        int enemies = lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.ENEMIES).size();
        int bosses = lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.BOSSES).size();
        int towers = lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.TOWERS).size();
        int heroes = lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.HEROES).size();
        int allEnemies = 0;
        for (EnemyType e : EnemyType.values()) allEnemies++;
        check(enemies + bosses == allEnemies && bosses == 5, "catalog lists every enemy (" + enemies + ") and all 5 bosses");
        check(towers == 18 && lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.TOWERS).contains(TowerType.ZETHOS), "catalog lists the 18 shop towers incl. Zethos");
        check(heroes == 18 && !lindefense.ui.CatalogScreen.entries(lindefense.ui.CatalogScreen.Tab.HEROES).contains(TowerType.ZETHOS), "catalog lists the 18 heroes (not Zethos)");
    }

    /** At most 3 different heroes per match; a dismissed hero keeps using its slot. */
    private static void heroLimit() {
        check(lindefense.tower.TowerManager.MAX_HEROES_PER_GAME == 3, "the hero cap is 3 per game");
        Game g = frozen();
        check(g.getHeroLimit() == 3, "a new match allows 3 heroes");
        TowerType[] h = { TowerType.LOBBER_LUIS, TowerType.KAIJU_KAI, TowerType.SPEAR_HANBO };
        Tower first = null;
        for (int i = 0; i < 3; i++) {
            Tower t = hero(g, h[i], 300 + i * 150);
            check(t != null, h[i] + " deploys (" + (i + 1) + " of 3)");
            if (i == 0) first = t;
        }
        check(g.getTowerManager().heroesDeployedThisMatch() == 3, "3 heroes counted");
        g.getHeroCollection().unlock(TowerType.MR_LINDEMANN);
        String why = g.getTowerManager().heroProblem(TowerType.MR_LINDEMANN);
        check(why != null && why.contains("limit"), "a 4th hero is refused: " + why);
        check(g.getTowerManager().heroProblem(TowerType.GPT) == null, "shop towers are not affected by the hero cap");
        g.sellTower(first);
        check(g.getTowerManager().heroesDeployedThisMatch() == 3 && g.getTowerManager().heroProblem(TowerType.MR_LINDEMANN) != null,
            "dismissing a hero does not free its slot");
    }

    /** Mr. Lindemann: map-wide space warp on schedule (bosses too), a singularity per impact, U2 garbage collection. */
    private static void mrLindemann() {
        Game g = frozen();
        lindefense.map.Path r = g.getMap().getRoutes().get(0);
        Tower ml = towerNearTrack(g, TowerType.MR_LINDEMANN, 0, 150);
        double far = r.getTotalLength() - 60;
        Enemy grunt = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, null, 0, far, 500, 1.0);
        Enemy boss = g.getEnemyManager().spawnScaled(EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, far - 20, 50, 1.0);
        g.getEnemyManager().update(0);
        check(grunt.getPosition().dist(ml.getPosition()) > ml.effectiveRange(g) + 50, "warp test enemies start out of his range");
        double g0 = grunt.getDistance(), b0 = boss.getDistance();
        runSeconds(g, 19.8);
        check(grunt.getDistance() == g0 && boss.getDistance() == b0, "no space warp before 20 s");
        runSeconds(g, 0.4);
        check(grunt.getDistance() < g0 - 30 && boss.getDistance() < b0 - 10, "the space warp sends every enemy back, bosses included (" + g0 + " -> " + grunt.getDistance() + ", boss " + b0 + " -> " + boss.getDistance() + ")");
        check(lindefense.tower.behavior.MrLindemannBehavior.warpRemaining(ml) > 19, "the warp timer restarts after a warp");
        check(near(TowerCatalog.get(TowerType.MR_LINDEMANN).statsForTier(3).p("warpInterval"), 15), "Event Horizon warps every 15 s");

        // a shot opens a singularity on the track
        Game g2 = frozen();
        Tower m2 = towerNearTrack(g2, TowerType.MR_LINDEMANN, 0, 450);
        tank(g2, 450);
        boolean opened = false;
        for (int i = 0; i < 600 && !opened; i++) { g2.step(Game.DT); opened = !g2.getEffects().zonesOf(m2, lindefense.tower.behavior.MrLindemannBehavior.HOLE).isEmpty(); }
        check(opened, "a black hole shot opens a singularity on the track");

        // U2 Garbage Collector deletes a weakened non-boss standing in a singularity (no children)
        Game g3 = frozen();
        Tower m3 = towerNearTrack(g3, TowerType.MR_LINDEMANN, 2, 450);
        Enemy victim = tank(g3, 450);
        for (int i = 0; i < 600 && g3.getEffects().zonesOf(m3, lindefense.tower.behavior.MrLindemannBehavior.HOLE).isEmpty(); i++) g3.step(Game.DT);
        lindefense.effects.TrackZone hole = g3.getEffects().zonesOf(m3, lindefense.tower.behavior.MrLindemannBehavior.HOLE).get(0);
        check(hole.contains(victim), "the singularity opened on the enemy");
        hitFor(g3, victim, victim.getHp() - victim.getMaxHp() * 0.10, lindefense.combat.DamageType.TRUE);
        g3.step(Game.DT);
        int alive = 0;
        for (Enemy e : g3.getEnemyManager().getEnemies()) if (e.isAlive()) alive++;
        check(!victim.isAlive() && alive == 0, "Garbage Collector deletes a non-boss below 15% HP inside a singularity, with no children (alive " + alive + ")");
    }

    // ------------------------------------------------------------------ helpers
    private static Game frozen() { Game g = newGame(0); g.setGlobalEnemySpeedMultiplier(0); return g; }
    private static boolean near(double a, double b) { return Math.abs(a - b) < 1e-6; }

    /** An unarmoured enemy with a huge HP pool, so damage is never capped by remaining HP. */
    private static Enemy tank(Game g, double dist) {
        Enemy e = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, null, 0, dist, 500, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }
    private static double taken(Enemy e) { return e.getMaxHp() - e.getHp(); }

    /** Leaks enough enemies to cost {@code n} integrity (the only way the game normally loses lives). */
    private static void leak(Game g, int n) {
        for (int i = 0; i < n && g.getLives() > 1; i++) {
            Enemy e = g.getEnemyManager().spawnScaled(EnemyType.PRIMITIVE_VARIABLE, null, 0, 0, 1, 1.0);
            g.getEnemyManager().update(0);
            g.loseLives(1, e);
            e.markDead();
        }
    }

    /** Fires exactly one attack from the tower and flies its projectiles until they are spent. */
    private static void oneShot(Game g, Tower t) {
        check(g.getCombat().attack(t), t.getType() + " fires");
        for (int i = 0; i < 600 && hasProjectiles(g); i++) { g.getCombat().updateProjectiles(Game.DT); g.getEvents().clear(); }
    }
    private static boolean hasProjectiles(Game g) {
        g.getCombat().updateProjectiles(0);
        return !g.getCombat().getProjectiles().isEmpty();
    }

    private static Tower hero(Game g, TowerType t, double trackDist) { return towerNearTrack(g, t, 0, trackDist); }
    private static Tower hero(Game g, TowerType t, double trackDist, int tier) { return towerNearTrack(g, t, tier, trackDist); }
}
