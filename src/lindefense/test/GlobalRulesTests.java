package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import lindefense.combat.Clusters;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.BuffStat;
import lindefense.tower.Faction;
import lindefense.tower.Shop;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerType;

/** Tests for the global tower rules (spec 3.0): units, damage types, statuses, buffs, targeting, camo, factions, heroes, costs. */
public final class GlobalRulesTests {
    private GlobalRulesTests() { }

    public static void runAll() {
        run("rules.units", GlobalRulesTests::units);
        run("rules.damageTypes", GlobalRulesTests::damageTypes);
        run("rules.leadCeramicFlags", GlobalRulesTests::leadCeramicFlags);
        run("rules.statuses", GlobalRulesTests::statuses);
        run("rules.armorCrack", GlobalRulesTests::armorCrack);
        run("rules.knockback", GlobalRulesTests::knockback);
        run("rules.buffStacking", GlobalRulesTests::buffStacking);
        run("rules.targeting", GlobalRulesTests::targeting);
        run("rules.camoDetection", GlobalRulesTests::camoDetection);
        run("rules.factions", GlobalRulesTests::factions);
        run("rules.heroUniqueness", GlobalRulesTests::heroUniqueness);
        run("rules.costTable", GlobalRulesTests::costTable);
        run("rules.tierNames", GlobalRulesTests::tierNames);
    }

    private static Enemy frozenEnemy(Game g, EnemyType t, double dist) { return spawnAt(g, t, null, 0, dist); }

    private static void units() {
        check(Enemy.BASE_SPEED == 60.0, "1.0x speed is 60 px/s");
        Game g = newGame(0);
        Enemy e = frozenEnemy(g, EnemyType.PRIMITIVE_VARIABLE, 100);
        g.run(60);
        check(Math.abs(e.getDistance() - 160) < 1.0, "a 1.0x enemy moves 60 px in one second, d=" + e.getDistance());
        check(TowerCatalog.get(TowerType.DEEPSEEK).baseStats.hasUnlimitedRange(), "DeepSeek range is the entire map");
        check(TowerCatalog.get(TowerType.DEEPSEEK).baseStats.range > Math.hypot(1200, 900), "unlimited range exceeds the map diagonal");
    }

    private static void damageTypes() {
        Game g = newGame(1);
        g.setGlobalEnemySpeedMultiplier(0);
        // SHARP vs Lead
        Enemy heap = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        check(hitFor(g, heap, 3, DamageType.SHARP) == 0, "SHARP cannot damage Lead-type");
        for (DamageType t : new DamageType[] { DamageType.BLUNT, DamageType.KINETIC, DamageType.ENERGY, DamageType.EXPLOSIVE, DamageType.MAGIC, DamageType.GRAVITY }) {
            Enemy h = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
            check(hitFor(g, h, 1, t) == 1, t + " can damage Lead-type");
        }
        // BLUNT / KINETIC / SONIC x2 vs Ceramic only
        for (DamageType t : new DamageType[] { DamageType.BLUNT, DamageType.KINETIC, DamageType.SONIC }) {
            Enemy m = frozenEnemy(g, EnemyType.MERGE_SORT, 300);
            check(hitFor(g, m, 2, t) == 4, t + " deals x2 to a Ceramic-type layer");
        }
        for (DamageType t : new DamageType[] { DamageType.SHARP, DamageType.ENERGY, DamageType.EXPLOSIVE, DamageType.MAGIC, DamageType.GRAVITY }) {
            Enemy m = frozenEnemy(g, EnemyType.MERGE_SORT, 300);
            check(hitFor(g, m, 2, t) == 2, t + " has no Ceramic bonus");
        }
        Enemy run = frozenEnemy(g, EnemyType.MERGE_RUN, 300);
        check(hitFor(g, run, 1, DamageType.BLUNT) == 1, "Merge Run is not Ceramic-type");
        // MAGIC / ENERGY hurt everything including a Lead-type boss
        Enemy ddt = frozenEnemy(g, EnemyType.LOCKHEED_MARTIN, 300);
        check(hitFor(g, ddt, 10, DamageType.MAGIC) > 0, "MAGIC hurts the Lead-type DDT");
        check(hitFor(g, ddt, 10, DamageType.SHARP) == 0, "SHARP cannot hurt the Lead-type DDT");
        // SONIC knocks Lead-type back 20 px
        Enemy lead = frozenEnemy(g, EnemyType.HEAP_SORT, 500);
        hitFor(g, lead, 1, DamageType.SONIC);
        check(Math.abs(lead.getDistance() - 480) < 1e-6, "SONIC knocks Lead-type back 20 px, d=" + lead.getDistance());
        Enemy nonLead = frozenEnemy(g, EnemyType.QUICK_SORT, 500);
        hitFor(g, nonLead, 1, DamageType.SONIC);
        check(nonLead.getDistance() == 500, "SONIC does not knock back non-Lead enemies");
        // GRAVITY slows on hit
        HitSpec grav = new HitSpec(1, DamageType.GRAVITY); grav.slowFraction = 0.10; grav.slowDuration = 2;
        Enemy gz = frozenEnemy(g, EnemyType.QUICK_SORT, 300);
        g.getCombat().applyHit(gz, grav, null, 1, 0);
        check(Math.abs(gz.getSlowFraction() - 0.10) < 1e-9, "GRAVITY hit applies its slow");
        // EXPLOSIVE cannot pop Camo without detection
        Tower gpt = towerNearTrack(g, TowerType.GPT, 0, 300);
        Tower grok = forcePlace(g, TowerType.GROK, buildableNear(g, gpt.getPosition().add(new Vec(60, 0)), 100), 0);
        Enemy camo = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.CAMO), 0, 300);
        HitSpec boom = new HitSpec(2, DamageType.EXPLOSIVE);
        check(g.getCombat().applyHit(camo, boom, gpt, 1, 0) == 0, "EXPLOSIVE cannot damage Camo without detection");
        check(g.getCombat().applyHit(camo, boom, grok, 1, 0) == 2, "EXPLOSIVE damages Camo when the source has detection");
        camo.applyStatus(StatusEffect.Kind.REVEALED, 1, 5);
        check(g.getCombat().applyHit(camo, boom, gpt, 1, 0) == 2, "a revealed Camo enemy can be damaged by explosions");
        // splash damage: explosions hit several enemies
        Game g2 = newGame(0);
        g2.setGlobalEnemySpeedMultiplier(0);
        Enemy a = frozenEnemy(g2, EnemyType.QUICK_SORT, 400), b = frozenEnemy(g2, EnemyType.QUICK_SORT, 420), far = frozenEnemy(g2, EnemyType.QUICK_SORT, 900);
        int hit = g2.getCombat().areaHit(a.getPosition(), 60, boom, null, 1, 99, null);
        check(hit == 2 && far.getHp() == far.getMaxHp(), "splash hits everything inside the radius only (" + hit + ")");
    }

    private static void leadCeramicFlags() {
        Game g = newGame(1);
        g.setGlobalEnemySpeedMultiplier(0);
        check(frozenEnemy(g, EnemyType.HEAP_SORT, 100).isLeadType(), "Heap Sort is Lead-type");
        check(frozenEnemy(g, EnemyType.LOCKHEED_MARTIN, 100).isLeadType(), "Lockheed Martin keeps its immunity as Lead-type");
        Enemy radix = frozenEnemy(g, EnemyType.RADIX_SORT, 100);
        check(!radix.isLeadType(), "Radix Sort is plain while above 6 layers");
        hitFor(g, radix, 2, DamageType.TRUE);
        check(radix.isLeadType(), "Radix Sort armoured phase (6 layers or fewer) is Lead-type");
        for (EnemyType t : new EnemyType[] { EnemyType.MERGE_SORT, EnemyType.QUICK_SORT, EnemyType.TIMSORT }) check(frozenEnemy(g, t, 100).isCeramicType(), t + " outer layer is Ceramic-type");
        for (EnemyType t : new EnemyType[] { EnemyType.MERGE_RUN, EnemyType.QUICK_PARTITION, EnemyType.HEAP_SORT, EnemyType.STATIC_ARRAY }) check(!frozenEnemy(g, t, 100).isCeramicType(), t + " is not Ceramic-type");
        int bosses = 0;
        for (EnemyType t : EnemyType.values()) if (t.isBoss()) { bosses++; check(frozenEnemy(g, t, 100).isMoabClass(), t + " is MOAB-class"); }
        check(bosses == 5, "MOAB-class is exactly the 5 bosses");
        check(!frozenEnemy(g, EnemyType.TIMSORT, 100).isMoabClass(), "ordinary enemies are not MOAB-class");
    }

    private static void statuses() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        // SLOW: strongest applies, no stacking
        Enemy e = frozenEnemy(g, EnemyType.QUICK_SORT, 300);
        e.applyStatus(StatusEffect.Kind.SLOW, 0.3, 5);
        e.applyStatus(StatusEffect.Kind.SLOW, 0.5, 1);
        e.applyStatus(StatusEffect.Kind.SLOW, 0.2, 5);
        check(Math.abs(e.getSlowFraction() - 0.5) < 1e-9, "strongest slow applies (not the sum 1.0)");
        e.tickStatuses(2);
        check(Math.abs(e.getSlowFraction() - 0.3) < 1e-9, "when the strongest slow expires the next strongest takes over");
        // Boss gets 1/3 of any slow
        Enemy boss = frozenEnemy(g, EnemyType.BELLARMINE_COLLEGE_PREP, 300);
        boss.applyStatus(StatusEffect.Kind.SLOW, 0.6, 5);
        check(Math.abs(boss.getSlowFraction() - 0.2) < 1e-9, "bosses receive 1/3 of a slow");
        Enemy pal = frozenEnemy(g, EnemyType.PALANTIR, 300);
        pal.applyStatus(StatusEffect.Kind.SLOW, 0.6, 5);
        check(pal.getSlowFraction() == 0, "Palantir phase 1 ignores slows");
        // STUN / FREEZE: bosses immune unless overridden
        check(e.applyStatus(StatusEffect.Kind.STUN, 1, 1) && e.isStunned(), "stun stops a normal enemy");
        check(!boss.applyStatus(StatusEffect.Kind.STUN, 1, 1) && !boss.isStunned(), "bosses are immune to stun");
        check(!boss.applyStatus(StatusEffect.Kind.FREEZE, 1, 1) && !boss.isFrozen(), "bosses are immune to freeze");
        check(boss.applyStatus(StatusEffect.Kind.STUN, 1, 1, true) && boss.isStunned(), "a tower can explicitly stun bosses");
        Enemy f = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        f.applyStatus(StatusEffect.Kind.FREEZE, 1, 2);
        check(f.isStunned() && f.currentSpeed(1) == 0, "freeze stops movement");
        Enemy plain = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        check(hitFor(g, f, 2, DamageType.ENERGY) == 4, "frozen enemies take x2 damage");
        check(hitFor(g, plain, 2, DamageType.ENERGY) == 2, "unfrozen control takes normal damage");
        // MARKED: flat and percent, strongest of each
        Enemy m = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        m.applyStatus(StatusEffect.Kind.MARKED, 0.2, 5); m.applyStatus(StatusEffect.Kind.MARKED, 0.5, 5);
        m.applyStatus(StatusEffect.Kind.MARKED_FLAT, 1, 5); m.applyStatus(StatusEffect.Kind.MARKED_FLAT, 2, 5);
        check(Math.abs(m.getMarkedBonus() - 0.5) < 1e-9 && m.getMarkedFlat() == 2, "strongest percent mark and strongest flat mark apply");
        double d = hitFor(g, m, 2, DamageType.ENERGY);
        check(Math.abs(d - (2 * 1.5 + 2)) < 1e-9, "damage with +50% and +2 marks = 5, got " + d);
        // DoT refreshes, does not stack
        Enemy burn = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        burn.applyBurn(1, 3, null);
        burn.tickStatuses(1);
        burn.applyBurn(2, 3, null);
        check(burn.statusMagnitude(StatusEffect.Kind.DOT) == 2, "burn keeps the strongest dps, not the sum");
        double dot = burn.tickStatuses(1);
        check(Math.abs(dot - 2) < 1e-9, "one second of burn = 2 damage (no stacking), got " + dot);
        burn.tickStatuses(2.5);
        check(!burn.hasStatus(StatusEffect.Kind.DOT), "burn expires 3 s after the refresh");
        // flat mark does not apply to immune hits
        Enemy lead = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        lead.applyStatus(StatusEffect.Kind.MARKED_FLAT, 5, 5);
        check(hitFor(g, lead, 2, DamageType.SHARP) == 0, "marks never add damage to a blocked hit");
    }

    private static void armorCrack() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Enemy heap = frozenEnemy(g, EnemyType.HEAP_SORT, 300);
        heap.applyStatus(StatusEffect.Kind.ARMOR_CRACK, 1, 5);
        check(hitFor(g, heap, 2, DamageType.SHARP) == 2, "ARMOR CRACK removes Lead immunity");
        Enemy fort = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 300);
        Enemy fortCracked = spawnAt(g, EnemyType.QUICK_SORT, EnumSet.of(Modifier.FORTIFIED), 0, 300);
        fortCracked.applyStatus(StatusEffect.Kind.ARMOR_CRACK, 1, 5);
        double a = hitFor(g, fort, 1, DamageType.ENERGY), b = hitFor(g, fortCracked, 1, DamageType.ENERGY);
        check(a == 1 && b == 2, "ARMOR CRACK doubles damage vs Fortified (HP bonus ignored): " + a + " vs " + b);
        fortCracked.tickStatuses(6);
        check(!fortCracked.isArmorCracked(), "ARMOR CRACK lasts only its duration");
    }

    private static void knockback() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Path r = g.getMap().getRoutes().get(0);
        Enemy e = frozenEnemy(g, EnemyType.QUICK_SORT, 600);
        HitSpec kb = new HitSpec(0, DamageType.TRUE); kb.knockback = 10;
        g.getCombat().applyHit(e, kb, null, 1, 0);
        check(Math.abs(e.getDistance() - 590) < 1e-6 && e.getPosition().dist(r.positionAt(590)) < 1e-6, "knockback moves the enemy back along the waypoint path");
        Enemy start = frozenEnemy(g, EnemyType.QUICK_SORT, 5);
        start.applyKnockbackUncapped(500);
        check(start.getDistance() == 0 && start.getPosition().dist(r.positionAt(0)) < 1e-6, "knockback never goes before the path start");
        Enemy boss = frozenEnemy(g, EnemyType.BELLARMINE_COLLEGE_PREP, 600);
        g.getCombat().applyHit(boss, kb, null, 1, 0);
        check(boss.getDistance() == 600, "bosses are immune to knockback unless stated");
        HitSpec kbBoss = new HitSpec(0, DamageType.TRUE); kbBoss.knockback = 10; kbBoss.bossKnockback = 10; kbBoss.uncappedKnockback = true;
        g.getCombat().applyHit(boss, kbBoss, null, 1, 0);
        check(boss.getDistance() == 590, "a tower can knock bosses back explicitly");
        Enemy pal = frozenEnemy(g, EnemyType.PALANTIR, 600);
        g.getCombat().applyHit(pal, kbBoss, null, 1, 0);
        check(pal.getDistance() == 600, "Palantir phase 1 ignores knockback");
        // anti soft-lock budget still protects against stacked pushers
        Enemy ms = frozenEnemy(g, EnemyType.MERGE_SORT, 700);
        double pushed = 0;
        for (int i = 0; i < 40; i++) pushed += ms.applyKnockback(10, g.getTime());
        check(pushed <= EnemyType.MERGE_SORT.speed * Enemy.BASE_SPEED * Enemy.KNOCKBACK_BUDGET + 1e-6, "knockback budget caps stacked pushes (" + pushed + ")");
    }

    private static void buffStacking() {
        Game g = newGame(0);
        Tower gpt = towerNearTrack(g, TowerType.GPT, 0, 300);
        double base = gpt.getStats().rate;
        // same source type: highest wins
        gpt.addAuraBuff(BuffStat.RATE, TowerType.COPILOT, 0.10);
        gpt.addAuraBuff(BuffStat.RATE, TowerType.COPILOT, 0.30);
        check(Math.abs(gpt.buffTotal(BuffStat.RATE) - 0.30) < 1e-9, "same-type buffs do not stack (highest applies)");
        // different types add
        gpt.addAuraBuff(BuffStat.RATE, TowerType.KAIJU_KAI, 0.25);
        check(Math.abs(gpt.buffTotal(BuffStat.RATE) - 0.55) < 1e-9, "different-type buffs add");
        check(Math.abs(gpt.effectiveRate(g) - base * 1.55) < 1e-9, "effective attack speed uses the summed buff");
        // caps
        gpt.addAuraBuff(BuffStat.RATE, TowerType.SUNNY_JOE, 0.9);
        check(gpt.buffTotal(BuffStat.RATE) == 1.0 && Math.abs(gpt.effectiveRate(g) - base * 2) < 1e-9, "attack speed buff capped at +100%");
        gpt.addTimedBuff(BuffStat.PIERCE_FLAT, TowerType.COPILOT, 8, 5);
        gpt.addTimedBuff(BuffStat.PIERCE_FLAT, TowerType.KAIJU_KAI, 6, 5);
        check(gpt.effectivePierce() == gpt.getStats().pierce + 10, "pierce buff capped at +10, got " + gpt.effectivePierce());
        gpt.addAuraBuff(BuffStat.DAMAGE_FLAT, TowerType.COPILOT, 4);
        gpt.addAuraBuff(BuffStat.DAMAGE_FLAT, TowerType.KAIJU_KAI, 3);
        check(gpt.flatDamageBuff() == 5, "flat damage buff capped at +5");
        // timed buffs expire
        Tower t2 = towerNearTrack(g, TowerType.CLAUDE, 0, 500);
        t2.addTimedBuff(BuffStat.RATE, TowerType.COPILOT, 1.0, 2);
        check(t2.buffTotal(BuffStat.RATE) == 1.0, "timed buff active");
        t2.tickTimers(g, 2.1);
        check(t2.buffTotal(BuffStat.RATE) == 0, "timed buff expired");
        // real auras: two Copilots do not stack; Copilot + Shashank's Resource Optimization (another source type) do
        Game g2 = newGame(0);
        Tower target = towerNearTrack(g2, TowerType.GPT, 0, 300);
        Tower c1 = forcePlace(g2, TowerType.COPILOT, buildableNear(g2, target.getPosition().add(new Vec(50, 0)), 80), 0);
        forcePlace(g2, TowerType.COPILOT, buildableNear(g2, target.getPosition().add(new Vec(-50, 0)), 80), 0);
        g2.getTowerManager().recomputeAuras();
        check(Math.abs(target.getAuraRateBonus() - 0.10) < 1e-9, "two Copilots give +10%, not +20%: " + target.getAuraRateBonus());
        // a different source stacks with Copilot: Tanimbus's Tactical Network adds its own +15%
        Tower drone = forcePlace(g2, TowerType.TANIMBUS, buildableNear(g2, target.getPosition().add(new Vec(0, 70)), 100), 2);
        g2.getTowerManager().recomputeAuras();
        check(Math.abs(target.getAuraRateBonus() - 0.25) < 1e-9, "Copilot + Tanimbus add: " + target.getAuraRateBonus());
        g2.sellTower(c1);
        g2.getTowerManager().recomputeAuras();
        check(Math.abs(target.getAuraRateBonus() - 0.25) < 1e-9, "remaining Copilot + Tanimbus still add: " + target.getAuraRateBonus());
        check(drone.isAlive(), "the support drone is still on the field");
    }

    private static void targeting() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Tower grok = towerNearTrack(g, TowerType.GROK, 2, 450);
        Enemy c1 = frozenEnemy(g, EnemyType.QUICK_SORT, 400), c2 = frozenEnemy(g, EnemyType.QUICK_SORT, 410), c3 = frozenEnemy(g, EnemyType.QUICK_SORT, 420);
        Enemy lone = frozenEnemy(g, EnemyType.QUICK_SORT, 500);
        List<Enemy> all = new ArrayList<>(Arrays.asList(c1, c2, c3, lone));
        check(Clusters.density(c2, all) == 2 && Clusters.density(lone, all) == 0, "density = other enemies within 60 px");
        check(Clusters.densest(all, all) == c3, "densest cluster tie goes to First (furthest along)");
        grok.setTargeting(Targeting.FIRST);
        check(g.getCombat().acquireTargets(grok, 1).get(0) == lone, "First targets the lone leader");
        grok.setTargeting(Targeting.DENSEST_CLUSTER);
        check(grok.getTargeting() == Targeting.DENSEST_CLUSTER, "Grok U2 can select Densest Cluster");
        Enemy picked = g.getCombat().acquireTargets(grok, 1).get(0);
        check(picked == c3, "Densest Cluster picks the cluster, ties to First");
        // only Grok U2+ can select it
        Tower gpt = forcePlace(g, TowerType.GPT, buildableNear(g, grok.getPosition().add(new Vec(80, 0)), 100), 3);
        gpt.setTargeting(Targeting.DENSEST_CLUSTER);
        check(gpt.getTargeting() == Targeting.FIRST, "GPT cannot select Densest Cluster");
        Tower grok1 = forcePlace(g, TowerType.GROK, buildableNear(g, grok.getPosition().add(new Vec(-80, 0)), 100), 1);
        grok1.setTargeting(Targeting.DENSEST_CLUSTER);
        check(grok1.getTargeting() != Targeting.DENSEST_CLUSTER, "Grok U1 cannot select Densest Cluster yet");
        // cycling reaches Densest only where allowed
        boolean sawDensest = false;
        for (int i = 0; i < 8; i++) { grok.cycleTargeting(1); if (grok.getTargeting() == Targeting.DENSEST_CLUSTER) sawDensest = true; }
        check(sawDensest, "cycling includes Densest Cluster for Grok U2");
        boolean gptSaw = false;
        for (int i = 0; i < 8; i++) { gpt.cycleTargeting(1); if (gpt.getTargeting() == Targeting.DENSEST_CLUSTER) gptSaw = true; }
        check(!gptSaw, "cycling never offers Densest Cluster to other towers");
    }

    private static void camoDetection() {
        // built-in at base
        EnumSet<TowerType> builtIn = EnumSet.of(TowerType.GROK, TowerType.PERPLEXITY, TowerType.NIK_SCOPE);
        for (TowerType t : TowerType.purchasable()) {
            check(TowerCatalog.get(t).statsForTier(0).seesCamo == builtIn.contains(t), t + " base camo detection");
        }
        // gained at U2
        for (TowerType t : new TowerType[] { TowerType.GEMINI, TowerType.LLAMA }) {
            TowerDef d = TowerCatalog.get(t);
            check(!d.statsForTier(1).seesCamo && d.statsForTier(2).seesCamo && d.statsForTier(3).seesCamo, t + " gains camo detection at U2");
        }
        // Mr. Lindemann sees Camo from Recursion (U1)
        TowerDef ml = TowerCatalog.get(TowerType.MR_LINDEMANN);
        check(!ml.statsForTier(0).seesCamo && ml.statsForTier(1).seesCamo && ml.statsForTier(3).seesCamo, "MR_LINDEMANN gains camo detection at U1");
        // nobody else ever gets it
        for (TowerType t : TowerType.purchasable()) {
            if (builtIn.contains(t) || t == TowerType.GEMINI || t == TowerType.LLAMA || t == TowerType.MR_LINDEMANN) continue;
            TowerDef dd = TowerCatalog.get(t);
            check(!dd.statsForTier(dd.upgrades.length).seesCamo, t + " has no camo detection");
        }
        // Perplexity radius grants detection; U1 grants it map-wide
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        Tower gpt = towerNearTrack(g, TowerType.GPT, 0, 300);
        Tower far = forcePlace(g, TowerType.CLAUDE, buildableNear(g, new Vec(1000, 800), 100), 0);
        Tower perp = forcePlace(g, TowerType.PERPLEXITY, buildableNear(g, gpt.getPosition().add(new Vec(70, 0)), 80), 0);
        g.getTowerManager().recomputeAuras();
        check(gpt.canSeeCamo() && !far.canSeeCamo(), "towers within Perplexity's radius gain detection; far towers do not");
        g.upgradeTower(perp);
        g.getTowerManager().recomputeAuras();
        check(gpt.canSeeCamo() && far.canSeeCamo(), "Perplexity U1 makes every tower able to target Camo map-wide");
        g.sellTower(perp);
        check(!gpt.canSeeCamo() && !far.canSeeCamo(), "detection disappears with Perplexity");
    }

    private static void factions() {
        Object[][] f = {
            { TowerType.KAIJU_KAI, Faction.HERO }, { TowerType.BLITZ_ARNAV, Faction.HERO }, { TowerType.CHILLSTIN, Faction.HERO },
            { TowerType.BOOM_SAM, Faction.HERO }, { TowerType.SUNNY_JOE, Faction.HERO }, { TowerType.NIK_SCOPE, Faction.HERO },
            { TowerType.GEMINI, Faction.PRIMARY }, { TowerType.CLAUDE, Faction.PRIMARY }, { TowerType.GPT, Faction.PRIMARY }, { TowerType.ZETHOS, Faction.PRIMARY },
            { TowerType.DEEPSEEK, Faction.MILITARY }, { TowerType.COPILOT, Faction.MILITARY },
            { TowerType.DALLE, Faction.MAGIC }, { TowerType.SORA, Faction.MAGIC }, { TowerType.SUNO, Faction.MAGIC },
            { TowerType.GROK, Faction.SUPPORT }, { TowerType.PERPLEXITY, Faction.SUPPORT },
            { TowerType.QWEN, Faction.TITAN }, { TowerType.LLAMA, Faction.TITAN }, { TowerType.MISTRAL, Faction.TITAN }, { TowerType.COHERE, Faction.TITAN },
            { TowerType.GLM, Faction.TITAN }, { TowerType.KIMI, Faction.TITAN }, { TowerType.MINIMAX, Faction.TITAN } };
        for (Object[] o : f) check(((TowerType) o[0]).faction == o[1], o[0] + " faction");
    }

    private static void heroUniqueness() {
        Game g = newGame(0);
        g.addCash(100000, null);
        Vec p1 = buildableNear(g, new Vec(300, 300), 100);
        Vec p2 = buildableNear(g, new Vec(600, 300), 100);
        String locked = g.placementProblem(TowerType.KAIJU_KAI, p1);
        check(g.placeTower(TowerType.KAIJU_KAI, p1) == null && locked != null && locked.contains("Hero Store"), "a locked hero cannot be placed: " + locked);
        check(g.purchaseHero(TowerType.KAIJU_KAI), "Kaiju Kai bought in the Hero Store");
        Tower kaiju = g.placeTower(TowerType.KAIJU_KAI, p1);
        check(kaiju != null, "first copy placed");
        check(g.placeTower(TowerType.KAIJU_KAI, p2) == null, "a second copy of the same hero is refused");
        String why = g.placementProblem(TowerType.KAIJU_KAI, p2);
        check(why != null && why.contains("already deployed"), "clear failure reason: " + why);
        check(Shop.unavailableReason(g, TowerType.KAIJU_KAI) != null, "shop reason for the UI");
        check(Shop.unavailableReason(g, TowerType.GPT) == null, "non-heroes are not limited");
        g.purchaseHero(TowerType.BLITZ_ARNAV);
        check(g.placeTower(TowerType.BLITZ_ARNAV, p2) != null, "a different unlocked hero can be placed");
        check(g.placeTower(TowerType.GPT, buildableNear(g, new Vec(300, 600), 100)) != null && g.placeTower(TowerType.GPT, buildableNear(g, new Vec(500, 600), 100)) != null, "multiple copies of a normal tower are allowed");
        g.sellTower(kaiju);
        check(!kaiju.isAlive() && g.placeTower(TowerType.KAIJU_KAI, p1) == null, "a dismissed hero cannot be redeployed in the same match");
    }

    private static void costTable() {
        Object[][] t = {
            { TowerType.GEMINI, 400, 650, 700, 1200, 2950 }, { TowerType.CLAUDE, 450, 550, 650, 1100, 2750 }, { TowerType.GPT, 500, 750, 800, 1300, 3350 },
            { TowerType.DEEPSEEK, 600, 850, 900, 1500, 3850 }, { TowerType.COPILOT, 350, 350, 600, 1000, 2300 },
            { TowerType.DALLE, 550, 500, 850, 1400, 3300 }, { TowerType.SORA, 700, 650, 1000, 1800, 4150 }, { TowerType.SUNO, 500, 500, 800, 1350, 3150 },
            { TowerType.GROK, 650, 600, 950, 1600, 3800 }, { TowerType.PERPLEXITY, 450, 450, 750, 1250, 2900 },
            { TowerType.QWEN, 750, 1100, 1200, 2000, 5050 }, { TowerType.LLAMA, 700, 1000, 1100, 1900, 4700 }, { TowerType.MISTRAL, 650, 650, 1050, 1750, 4100 },
            { TowerType.COHERE, 800, 800, 1300, 2200, 5100 }, { TowerType.GLM, 600, 550, 900, 1500, 3550 }, { TowerType.KIMI, 700, 700, 1150, 1950, 4500 },
            { TowerType.MINIMAX, 650, 1050, 1050, 1800, 4550 } };
        check(t.length == 17, "table lists the 17 standard towers");
        for (Object[] r : t) {
            TowerDef d = TowerCatalog.get((TowerType) r[0]);
            check(d.baseCost == (Integer) r[1], r[0] + " base cost");
            for (int i = 0; i < 3; i++) check(d.upgrades[i].cost == (Integer) r[2 + i], r[0] + " U" + (i + 1) + " cost");
            int sum = d.baseCost + d.upgrades[0].cost + d.upgrades[1].cost + d.upgrades[2].cost;
            check(sum == (Integer) r[5] && d.totalCost() == (Integer) r[5], r[0] + " total $" + r[5] + " (got " + sum + ")");
        }
        // Zethos: four upgrades, $5,350 fully upgraded
        TowerDef z = TowerCatalog.get(TowerType.ZETHOS);
        int[] zc = { 350, 650, 1200, 2500 };
        check(z.baseCost == 650 && z.upgrades.length == 4, "Zethos $650 with four upgrades");
        for (int i = 0; i < 4; i++) check(z.upgrades[i].cost == zc[i], "Zethos tier " + (i + 1) + " cost $" + zc[i]);
        check(z.totalCost() == 5350, "Zethos fully upgraded total $5,350");
    }

    private static void tierNames() {
        String[][] names = {
            { "Quantum Pulse", "Quantum Acceleration", "Dimensional Fracture", "Quantum Singularity", "Zethos: Reality Engine" },
            { "Gemini 3.7 Flash", "Gemini 3.8 Flash", "Gemini 3.1 Pro", "Gemini 4 Argon" },
            { "Claude Haiku 5.5", "Claude Sonnet 5.5", "Claude Opus 5.5", "Claude Fable 5.1" },
            { "GPT-5.6 Terra", "GPT-6 Luna", "GPT-6 Astra", "GPT-6.1 Sol" },
            { "DeepSeek V4 Flash", "DeepSeek V4.1 Flash", "DeepSeek R1", "DeepSeek V4 Pro" },
            { "Qwen3.8 Flash", "Qwen3.6 Max", "Qwen3.7 Plus", "Qwen3.8 Max" },
            { "Llama 4 Scout", "Llama 4 Maverick", "Muse Glimmer", "Muse Wonder" },
            { "MiniMax M2.5", "MiniMax M2.7", "MiniMax M3", "MiniMax M3.1 Flash" } };
        TowerType[] types = { TowerType.ZETHOS, TowerType.GEMINI, TowerType.CLAUDE,
            TowerType.GPT, TowerType.DEEPSEEK, TowerType.QWEN, TowerType.LLAMA, TowerType.MINIMAX };
        for (int i = 0; i < types.length; i++) check(Arrays.equals(TowerCatalog.get(types[i]).tierLabels, names[i]), types[i] + " tier labels " + Arrays.toString(TowerCatalog.get(types[i]).tierLabels));
        // family name is the display name, the nickname is the subtitle
        check(TowerType.GEMINI.displayName.equals("Gemini") && TowerCatalog.get(TowerType.GEMINI).subtitle.equals("Prism Blaster"), "family name + nickname subtitle");
        check(TowerCatalog.get(TowerType.CLAUDE).subtitle.equals("Ink Weaver") && TowerCatalog.get(TowerType.KIMI).subtitle.equals("Dimensional Assassin"), "nickname subtitles");
    }

    /** Boss helper used by other groups. */
    static Boss boss(Game g, EnemyType t, double dist) { return (Boss) spawnAt(g, t, null, 0, dist); }
}
