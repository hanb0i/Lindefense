package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.EnumSet;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Game;
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
            check(TowerCatalog.abilityNeedsUnlock(t) == (t != TowerType.ZETHOS), t + (t == TowerType.ZETHOS ? " ability is free from placement" : " ability must be unlocked"));
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

        Tower z = towerNearTrack(frozen(), TowerType.ZETHOS, 0, 450);
        check(!z.isAbilityLocked() && z.getAbility() != null && Math.abs(z.getAbilityCooldownRemaining() - z.getAbility().cooldown * 0.5) < 1e-9,
            "Zethos's ability is usable from placement at 50% cooldown");

        Game admin = frozen();
        admin.setAdmin(false, true, false);
        Tower a = towerNearTrack(admin, TowerType.GLM, 3, 450);
        check(admin.unlockAbility(a) && a.isAbilityReady(), "admin infinite money unlocks abilities for free");
    }

    private static void unlockedMechanics() {
        // Opus Time-Lock reaches the whole map and slows bosses by the stated 60%
        Game g = frozen();
        Path r = g.getMap().getRoutes().get(0);
        Tower claude = unlocked(g, TowerType.CLAUDE, 300);
        Enemy far = spawnAt(g, EnemyType.HEAP_SORT, null, 0, r.getTotalLength() - 40);
        Enemy boss = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, r.getTotalLength() - 80);
        check(far.getPosition().dist(claude.getPosition()) > claude.effectiveRange(g), "test enemy starts outside Claude's normal range");
        check(g.activateAbility(claude), "Opus Time-Lock fires");
        check(far.isFrozen(), "Opus Time-Lock freezes an enemy far outside Claude's range");
        check(Math.abs(boss.statusMagnitude(StatusEffect.Kind.SLOW) - 0.6) < 1e-6, "Opus Time-Lock slows bosses by 60% (got " + boss.statusMagnitude(StatusEffect.Kind.SLOW) + ")");

        // R1 Deep Reasoning Strike destroys the 25 strongest non-bosses and strikes bosses for 15% max HP
        g = frozen();
        Tower ds = unlocked(g, TowerType.DEEPSEEK, 450);
        for (int i = 0; i < 30; i++) spawnAt(g, EnemyType.TIMSORT, null, 0, 200 + i * 15);
        boss = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 650);
        double bossHp = boss.getHp();
        check(g.activateAbility(ds), "R1 Deep Reasoning Strike fires");
        int left = 0;
        for (Enemy e : g.getEnemyManager().getEnemies()) if (e.isAlive() && !e.isBoss()) left++;
        check(left == 5, "R1 destroys the 25 strongest of 30 non-boss enemies (left " + left + ")");
        check(boss.getHp() <= bossHp - boss.getMaxHp() * 0.14, "R1 strikes bosses for 15% of max HP (" + bossHp + " -> " + boss.getHp() + ")");

        // Enterprise Auto-Refactor: every tower, x3, past the +100% buff cap
        g = frozen();
        Tower copilot = unlocked(g, TowerType.COPILOT, 300);
        Tower gpt = towerNearTrack(g, TowerType.GPT, 0, 700);
        check(g.activateAbility(copilot), "Enterprise Auto-Refactor fires");
        check(Math.abs(gpt.selfRateMult() - 3) < 1e-9, "Auto-Refactor speeds up a non-Military tower x3 (got x" + gpt.selfRateMult() + ")");

        // Outpainting Expansion now burns enemies standing in it
        g = frozen();
        r = g.getMap().getRoutes().get(0);
        Tower dalle = unlocked(g, TowerType.DALLE, 450);
        Enemy t1 = tank(g, null, 450, 500);
        double hp = t1.getHp();
        check(g.activateAbility(dalle, r.positionAt(450)), "Outpainting Expansion fires");
        runSeconds(g, 1.2);
        check(t1.getHp() < hp, "Outpainting's zone damages enemies inside it (" + hp + " -> " + t1.getHp() + ")");

        // Symphonic Bass Drop: 300 base + 400 x speed multiplier
        g = frozen();
        Tower suno = unlocked(g, TowerType.SUNO, 450);
        Enemy t2 = tank(g, null, 450, 5000);
        hp = t2.getHp();
        check(g.activateAbility(suno), "Symphonic Bass Drop fires");
        check(hp - t2.getHp() >= 300 + 400 * t2.speedMultiplier() * 0.99, "Bass Drop deals 300 + 400 x speed (" + (hp - t2.getHp()) + ")");

        // Infinite Context Burst goes through Fortified
        g = frozen();
        Tower kimi = unlocked(g, TowerType.KIMI, 450);
        for (int i = 0; i < 1200; i++) kimi.addKill();
        Enemy fort = tank(g, EnumSet.of(Modifier.FORTIFIED), 450, 5000);
        hp = fort.getHp();
        check(g.activateAbility(kimi), "Infinite Context Burst fires");
        check(hp - fort.getHp() >= 12 * 300 * 0.99, "Context Burst hits a Fortified enemy for 12 stacks x 300 (" + (hp - fort.getHp()) + ")");
    }
}
