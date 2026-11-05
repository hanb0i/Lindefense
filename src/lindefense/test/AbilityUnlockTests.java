package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.EnumSet;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.tower.AbilityDef;
import lindefense.tower.Shop;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;

/**
 * Shop-tower abilities: every shop tower has an overpowered ability that is locked until the tower has every upgrade
 * and the player pays {@link TowerCatalog#ABILITY_UNLOCK_COST}; Zethos's ability needs no unlock; heroes have none.
 * Also checks the mechanics the unlocked versions added (map-wide Time-Lock, multi-target R1 strike, uncapped
 * Auto-Refactor, burning Outpainting, Bass Drop base damage, Context Burst through Fortified).
 * Every ability firing after its unlock is covered by {@code HeadlessTests.abilities}.
 */
public final class AbilityUnlockTests {
    private AbilityUnlockTests() { }

    public static void runAll() {
        run("abilities.unlockRules", AbilityUnlockTests::unlockRules);
        run("abilities.unlockedMechanics", AbilityUnlockTests::unlockedMechanics);
    }

    private static Game frozen() { Game g = newGame(0); g.setGlobalEnemySpeedMultiplier(0); return g; }

    /** A max-tier tower near the track with its ability bought (cash added first). */
    private static Tower unlocked(Game g, TowerType type, double trackDistance) {
        Tower t = towerNearTrack(g, type, TowerCatalog.get(type).upgrades.length, trackDistance);
        g.addCash(TowerCatalog.ABILITY_UNLOCK_COST, null);
        check(g.unlockAbility(t), type + " ability unlocks");
        return t;
    }

    /** An unarmoured, slow-to-kill enemy (HP = base x hpScale). */
    private static Enemy tank(Game g, EnumSet<Modifier> mods, double dist, double hpScale) {
        Enemy e = g.getEnemyManager().spawnScaled(EnemyType.DYNAMIC_ARRAY, mods, 0, dist, hpScale, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }

    private static void unlockRules() {
        int price = TowerCatalog.ABILITY_UNLOCK_COST;
        check(price == 15_000, "ability unlock costs $15,000");
        for (TowerType t : TowerType.shopTowers()) {
            check(TowerCatalog.get(t).ability != null, t + " has an ability");
            check(TowerCatalog.abilityNeedsUnlock(t), t + " ability must be unlocked");
        }
        for (TowerType h : TowerType.heroes()) check(TowerCatalog.get(h).ability == null, h + " is passive (no ability)");

        Game g = frozen();
        Tower c = towerNearTrack(g, TowerType.CLAUDE, 0, 450);
        check(c.isAbilityLocked() && c.getAbility() == null && c.getAbilityDef() != null, "a fresh shop tower's ability is locked");
        check(!c.isAbilityReady() && !g.activateAbility(c), "a locked ability cannot fire");
        g.addCash(100_000, null);
        double before = g.getCash();
        check(!c.canUnlockAbility() && !g.unlockAbility(c) && g.getCash() == before, "the unlock needs every upgrade first (no charge)");
        while (c.canUpgrade()) check(g.upgradeTower(c), "upgrade Claude");
        check(c.canUnlockAbility(), "a maxed tower can unlock its ability");
        g.spendCash(g.getCash() - (price - 1));
        check(!g.unlockAbility(c) && c.isAbilityLocked() && g.getCash() == price - 1, "the unlock fails below $15,000 (no charge)");
        int investedBefore = c.getInvestedCost();
        g.addCash(1, null);
        check(g.unlockAbility(c), "the unlock succeeds with exactly $15,000");
        check(g.getCash() == 0, "the unlock charges exactly $15,000 (cash " + g.getCash() + ")");
        check(!c.isAbilityLocked() && c.getAbility() != null && c.isAbilityReady(), "an unlocked ability is ready at once");
        check(c.getInvestedCost() == investedBefore + price && Shop.sellValue(c) == (int) Math.floor(c.getInvestedCost() * Shop.SELL_FRACTION),
            "the unlock counts toward the tower's sell value");
        g.addCash(price, null);
        check(!g.unlockAbility(c) && g.getCash() == price, "an ability cannot be bought twice");

        // Zethos: Reality Collapse is locked like every shop tower's ability, until all FOUR upgrades are bought
        Game zg = frozen();
        Tower z = towerNearTrack(zg, TowerType.ZETHOS, 0, 450);
        check(z.isAbilityLocked() && z.getAbility() == null && !zg.activateAbility(z), "Zethos's Reality Collapse is locked at placement");
        zg.addCash(100_000, null);
        for (int i = 0; i < TowerCatalog.ZETHOS_UPGRADES - 1; i++) check(zg.upgradeTower(z), "upgrade Zethos");
        check(!z.isMaxed() && !z.canUnlockAbility() && !zg.unlockAbility(z), "Zethos cannot unlock after only three upgrades");
        check(zg.upgradeTower(z) && z.isMaxed() && z.getTier() == TowerCatalog.ZETHOS_UPGRADES, "Zethos's fourth upgrade maxes it");
        double zCash = zg.getCash();
        check(zg.unlockAbility(z) && zg.getCash() == zCash - price, "Zethos unlocks Reality Collapse for $15,000 after the fourth upgrade");
        check(!z.isAbilityLocked() && z.isAbilityReady() && zg.activateAbility(z), "Zethos's unlocked Reality Collapse fires at once");

        Game admin = frozen();
        admin.setAdmin(false, true, false);
        Tower a = towerNearTrack(admin, TowerType.GLM, 3, 450);
        check(admin.unlockAbility(a) && a.isAbilityReady(), "admin infinite money unlocks abilities for free");
    }

    private static void unlockedMechanics() {
        // Opus Time-Lock reaches past Claude's own range up to its ability radius, and slows bosses there by the stated amount
        Game g = frozen();
        Path r = g.getMap().getRoutes().get(0);
        Tower claude = unlocked(g, TowerType.CLAUDE, 300);
        AbilityDef opus = claude.getAbility();
        double reach = opus.p("radius"), range = claude.effectiveRange(g);
        double dIn = -1, dOut = -1;
        for (double d = 0; d < r.getTotalLength(); d += 5) {
            double dist = r.positionAt(d).dist(claude.getPosition());
            if (dIn < 0 && dist > range + 30 && dist < reach - 60) dIn = d;
            if (dist > reach + 60) dOut = d;
        }
        check(dIn >= 0 && dOut >= 0, "test spots inside and outside Opus Time-Lock's reach exist");
        Enemy reached = spawnAt(g, EnemyType.HEAP_SORT, null, 0, dIn);
        Enemy beyond = spawnAt(g, EnemyType.HEAP_SORT, null, 0, dOut);
        Enemy boss = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, dIn + 10);
        check(g.activateAbility(claude), "Opus Time-Lock fires");
        check(reached.isFrozen(), "Opus Time-Lock freezes an enemy outside Claude's range but within " + (int) reach + " px");
        check(!beyond.isFrozen(), "Opus Time-Lock does not reach past " + (int) reach + " px");
        check(Math.abs(boss.statusMagnitude(StatusEffect.Kind.SLOW) - opus.p("bossSlow")) < 1e-6,
            "Opus Time-Lock slows bosses by " + Math.round(opus.p("bossSlow") * 100) + "% (got " + boss.statusMagnitude(StatusEffect.Kind.SLOW) + ")");

        // R1 Deep Reasoning Strike destroys the N strongest non-bosses and strikes bosses for a share of their max HP
        g = frozen();
        Tower ds = unlocked(g, TowerType.DEEPSEEK, 450);
        AbilityDef r1 = ds.getAbility();
        int count = (int) r1.p("count");
        for (int i = 0; i < count + 5; i++) spawnAt(g, EnemyType.TIMSORT, null, 0, 200 + i * 15);
        boss = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 650);
        double bossHp = boss.getHp();
        check(g.activateAbility(ds), "R1 Deep Reasoning Strike fires");
        int left = 0;
        for (Enemy e : g.getEnemyManager().getEnemies()) if (e.isAlive() && !e.isBoss()) left++;
        check(left == 5, "R1 destroys the " + count + " strongest of " + (count + 5) + " non-boss enemies (left " + left + ")");
        double pct = r1.p("bossDamagePct");
        check(boss.getHp() <= bossHp - boss.getMaxHp() * pct * 0.9 && boss.getHp() >= bossHp - boss.getMaxHp() * pct * 1.01,
            "R1 strikes bosses for " + Math.round(pct * 100) + "% of max HP (" + bossHp + " -> " + boss.getHp() + ")");

        // Enterprise Auto-Refactor: every tower, past the +100% buff cap
        g = frozen();
        Tower copilot = unlocked(g, TowerType.COPILOT, 300);
        Tower gpt = towerNearTrack(g, TowerType.GPT, 0, 700);
        double mult = copilot.getAbility().p("rateMult");
        check(g.activateAbility(copilot), "Enterprise Auto-Refactor fires");
        check(Math.abs(gpt.selfRateMult() - mult) < 1e-9, "Auto-Refactor speeds up a non-Military tower x" + mult + " (got x" + gpt.selfRateMult() + ")");

        // Outpainting Expansion now burns enemies standing in it
        g = frozen();
        r = g.getMap().getRoutes().get(0);
        Tower dalle = unlocked(g, TowerType.DALLE, 450);
        Enemy t1 = tank(g, null, 450, 500);
        double hp = t1.getHp();
        check(g.activateAbility(dalle, r.positionAt(450)), "Outpainting Expansion fires");
        runSeconds(g, 1.2);
        check(t1.getHp() < hp, "Outpainting's zone damages enemies inside it (" + hp + " -> " + t1.getHp() + ")");

        // Symphonic Bass Drop: base + per-speed damage
        g = frozen();
        Tower suno = unlocked(g, TowerType.SUNO, 450);
        AbilityDef bass = suno.getAbility();
        Enemy t2 = tank(g, null, 450, 5000);
        hp = t2.getHp();
        double expected = bass.p("baseDamage") + bass.p("damagePerSpeed") * t2.speedMultiplier();
        check(g.activateAbility(suno), "Symphonic Bass Drop fires");
        check(hp - t2.getHp() >= expected * 0.99, "Bass Drop deals base + per-speed damage (" + (hp - t2.getHp()) + " of " + expected + ")");

        // Infinite Context Burst goes through Fortified
        g = frozen();
        Tower kimi = unlocked(g, TowerType.KIMI, 450);
        for (int i = 0; i < 1200; i++) kimi.addKill();
        Enemy fort = tank(g, EnumSet.of(Modifier.FORTIFIED), 450, 5000);
        hp = fort.getHp();
        check(g.activateAbility(kimi), "Infinite Context Burst fires");
        double perStack = kimi.getAbility().p("damagePerStack");
        check(hp - fort.getHp() >= 12 * perStack * 0.99, "Context Burst hits a Fortified enemy for 12 stacks x " + (int) perStack + " (" + (hp - fort.getHp()) + ")");
    }
}
