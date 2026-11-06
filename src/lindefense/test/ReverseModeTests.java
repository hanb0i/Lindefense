package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.EnumSet;
import java.util.List;
import lindefense.ai.AttackAbility;
import lindefense.ai.AttackUnit;
import lindefense.ai.AttackerBot;
import lindefense.ai.DefenderAI;
import lindefense.ai.DefenderProfile;
import lindefense.ai.ReverseMatch;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.MapCatalog;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;

/**
 * Reverse mode ("Adversarial Training", {@link ReverseMatch}): the attacker economy (start credits, growing income,
 * SCALE COMPUTE, leak bonus), unit / modifier / exploit unlock gating, the uplink (prices, queue, handshake, spawn
 * spacing, lanes, normal enemy mechanics), the exploits, the defender AI spending legally (placement, hero cap, one copy
 * per hero, in-memory Hero Store, ability unlocks only on maxed towers), the win and loss conditions (breach, training
 * run timer, overtime, Palantir not ending the match), restart, the shared {@link DefenderAI} still driving the balance
 * bot, and whole matches: a scripted attacker beats the easiest AI while a do-nothing attacker loses.
 */
public final class ReverseModeTests {
    private ReverseModeTests() { }

    /** Runs every reverse-mode test group. */
    public static void runAll() {
        run("reverse.economy", ReverseModeTests::economy);
        run("reverse.difficultyRules", ReverseModeTests::difficultyRules);
        run("reverse.unlockGating", ReverseModeTests::unlockGating);
        run("reverse.spawning", ReverseModeTests::spawning);
        run("reverse.exploits", ReverseModeTests::exploits);
        run("reverse.defenderPlaysLegally", ReverseModeTests::defenderPlaysLegally);
        run("reverse.winAndLoss", ReverseModeTests::winAndLoss);
        run("reverse.wholeMatches", ReverseModeTests::wholeMatches);
        run("reverse.sharedDefenderAI", ReverseModeTests::sharedDefenderAI);
        run("reverse.uiRouting", ReverseModeTests::uiRouting);
    }

    private static Game reverse(int map, Difficulty d) { return ReverseMatch.create(map, 42, d); }

    /** Runs the match for the given game seconds (stops early if it ends). */
    private static void advance(Game g, double seconds) {
        int n = (int) Math.round(seconds / Game.DT);
        for (int i = 0; i < n && g.getState() == Game.State.PLAYING; i++) { g.step(Game.DT); g.getEvents().clear(); }
    }

    // ------------------------------------------------------------------ economy

    private static void economy() {
        Game g = reverse(0, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        check(g.isReverse() && r != null && r.getGame() == g, "reverse game carries its controller");
        check(g.getDifficulty() == Difficulty.O1, "the game itself runs with base rules (the mode only picks the AI)");
        check(r.getProfile() == DefenderProfile.COMPETENT && r.getLevel() == Difficulty.ON, "O(N) picks the Competent AI");
        check(r.getCredits() == ReverseMatch.START_CREDITS, "attacker starts with " + ReverseMatch.START_CREDITS + " credits");
        check(g.getCash() == Game.START_CASH && g.getLives() == Game.START_LIVES, "defender starts with the normal cash and integrity");
        double i0 = r.incomeRate();
        check(Math.abs(i0 - 12) < 1e-9, "income starts at 12/s, got " + i0);
        // a passive minute: credits = start + integral of the income curve (the AI spends its own cash meanwhile)
        advance(g, 60);
        double expected = ReverseMatch.START_CREDITS + 12 * 60 + 5 * 60 + 0.5 * 60 / 3.0;   // integral of 12 + 10 m + 0.5 m^2 over a minute
        check(Math.abs(r.getCredits() - expected) < 3, "one minute of income: expected about " + (int) expected + ", got " + (int) r.getCredits());
        check(r.incomeRate() > i0 + 9, "income grows over the match (" + r.incomeRate() + "/s after a minute)");
        check(r.getDefenderFunding() > 0 && g.getTotalCashEarned() > Game.START_CASH, "the defender is funded over time");
        check(Math.abs(r.defenderFundingRate() - r.baseIncome() * ReverseMatch.FUND_RATIO * DefenderProfile.COMPETENT.income) < 1e-9, "funding follows the compute curve x the profile");
        // income at 5 / 10 / 15 minutes (the documented curve)
        double[][] pts = { { 5, 12 + 50 + 12.5 }, { 10, 12 + 100 + 50 }, { 15, 12 + 150 + 112.5 } };
        for (double[] p : pts) {
            Game h = reverse(0, Difficulty.ON);
            h.getReverse().update(0);   // no-op on time 0
            advanceController(h, p[0] * 60);
            check(Math.abs(h.getReverse().baseIncome() - p[1]) < 0.6, "base income at " + (int) p[0] + ":00 is " + p[1] + ", got " + h.getReverse().baseIncome());
        }
        // SCALE COMPUTE: +4/s, price grows (COMPUTE_PRICE_GROWTH - 1) x 100% each time, at most 8
        Game c = reverse(0, Difficulty.ON);
        ReverseMatch rc = c.getReverse();
        check(rc.computePrice() == ReverseMatch.COMPUTE_BASE_PRICE, "first SCALE COMPUTE costs " + ReverseMatch.COMPUTE_BASE_PRICE);
        check(rc.computeProblem() != null && !rc.scaleCompute(), "cannot scale compute without the credits (250 < 300)");
        advance(c, 10);
        double before = rc.getCredits(), inc = rc.incomeRate();
        check(rc.scaleCompute(), "SCALE COMPUTE once affordable");
        check(Math.abs(rc.getCredits() - (before - 300)) < 1e-6 && Math.abs(rc.incomeRate() - inc - ReverseMatch.COMPUTE_STEP) < 1e-9, "costs 300 and adds 4 credits/s");
        check(rc.computePrice() == (int) Math.round(300 * ReverseMatch.COMPUTE_PRICE_GROWTH), "second purchase costs " + (int) Math.round((ReverseMatch.COMPUTE_PRICE_GROWTH - 1) * 100) + "% more");
        rc.setUnlimitedCredits(true);
        for (int i = 0; i < 20; i++) rc.scaleCompute();
        check(rc.getComputeLevel() == ReverseMatch.COMPUTE_MAX && "Fully scaled".equals(rc.computeProblem()), "SCALE COMPUTE stops at " + ReverseMatch.COMPUTE_MAX);
        // leak bonus: 8 credits per integrity point
        Game l = reverse(0, Difficulty.ON);
        ReverseMatch rl = l.getReverse();
        Enemy e = spawnAt(l, EnemyType.SHELL_SORT, null, 0, 10);
        double c0 = rl.getCredits();
        l.loseLives(3, e);
        check(Math.abs(rl.getCredits() - c0 - 3 * ReverseMatch.LEAK_BONUS_PER_LIFE) < 1e-9 && rl.getLivesTaken() == 3 && rl.getLeaks() == 1, "a 3-integrity leak pays 24 credits");
        check(l.getLives() == Game.START_LIVES - 3, "and costs the defender 3 integrity");
        // kill bounty: listed reward (not the campaign's x3)
        check(l.getRewardScale() == ReverseMatch.KILL_REWARD_SCALE, "reverse mode pays the listed kill rewards (scale " + l.getRewardScale() + ")");
        check(reverse(0, Difficulty.ON).getRewardScale() != new Game(MapCatalog.create(0), 1).getRewardScale(), "the normal game still triples them");
        // profiles: more funding and starting cash on harder levels
        double prev = 0;
        for (Difficulty d : Difficulty.values()) {
            DefenderProfile p = DefenderProfile.of(d);
            check(p.level == d && p.income > prev, d + " -> " + p + " funds more than the level below");
            prev = p.income;
        }
        for (Difficulty d : Difficulty.values())
            check(reverse(0, d).getCash() == Game.START_CASH * DefenderProfile.of(d).startCash, d + " starts the AI with its profile's cash");
        check(ReverseMatch.trackBonus(MapCatalog.create(0)) == 1 && ReverseMatch.trackBonus(MapCatalog.create(1)) > 1.2, "long tracks pay a compute bonus, short ones none");
        check(ReverseMatch.trackSpeed(MapCatalog.create(0)) == 1 && ReverseMatch.trackSpeed(MapCatalog.create(1)) > 2, "units cross long tracks faster");
    }

    /**
     * The difficulty's match rules: harder modes give the AI's towers more damage and the AI more integrity, and give
     * the attacker frailer units and less income; O(N) is the neutral baseline. Each lever is checked in a live match.
     */
    private static void difficultyRules() {
        DefenderProfile n = DefenderProfile.COMPETENT;
        check(n.towerDamage == 1 && n.unitHp == 1 && n.attackerIncome == 1 && n.integrity == Game.START_LIVES, "O(N) is the neutral baseline");
        DefenderProfile prev = null;
        for (Difficulty d : Difficulty.values()) {
            DefenderProfile p = DefenderProfile.of(d);
            if (prev != null) {
                check(p.towerDamage > prev.towerDamage, d + ": the AI's towers hit harder than on the mode below");
                check(p.integrity > prev.integrity, d + ": the AI has more integrity than on the mode below");
                check(p.unitHp < prev.unitHp, d + ": your units have less health than on the mode below");
                check(p.attackerIncome < prev.attackerIncome, d + ": you earn less than on the mode below");
            }
            prev = p;
            String tag = " [" + d + "]";
            Game g = reverse(0, d);
            ReverseMatch r = g.getReverse();
            check(g.getLives() == p.integrity && g.getMaxLives() == p.integrity, "the AI starts with " + p.integrity + " integrity" + tag);
            check(Math.abs(g.getGlobalDamageMultiplier() - p.towerDamage) < 1e-9, "the AI's towers deal x" + p.towerDamage + " damage" + tag);
            check(Math.abs(r.incomeRate() - 12 * p.attackerIncome) < 1e-9, "compute income starts at 12/s x " + p.attackerIncome + tag + " (" + r.incomeRate() + ")");
            double c0 = r.getCredits();
            Enemy dummy = g.getEnemyManager().spawnScaled(EnemyType.PRIMITIVE_VARIABLE, null, 0, 0, 1, 1);
            r.onLeak(5, dummy);
            check(Math.abs(r.getCredits() - c0 - ReverseMatch.LEAK_BONUS_PER_LIFE * 5 * p.attackerIncome) < 1e-9, "leak bounties scale with income" + tag);
            // a sent Heap Sort enters with the mode's health multiplier
            Game s = reverse(0, d);
            ReverseMatch rs = s.getReverse();
            rs.setUnlimitedCredits(true);
            for (int i = 0; i < (int) (AttackUnit.HEAP.unlockAt / Game.DT) + 1; i++) rs.update(Game.DT);
            check(rs.send(AttackUnit.HEAP, null, 1, 0) == 1, "a Heap Sort is sent" + tag);
            for (int i = 0; i < (int) (2 * ReverseMatch.SPAWN_GAP / Game.DT) + 1; i++) rs.update(Game.DT);
            s.getEnemyManager().update(0);
            Enemy heap = null;
            for (Enemy e : s.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.HEAP_SORT) heap = e;
            check(heap != null && heap.getMaxHp() == Math.max(1, Math.round(EnemyType.HEAP_SORT.baseHp * s.getWaveHpScale(EnemyType.HEAP_SORT) * p.unitHp)),
                "units enter with x" + p.unitHp + " health" + tag + " (" + (heap == null ? "none" : heap.getMaxHp()) + ")");
            // healing never lifts integrity past the mode's maximum
            s.loseLives(10, heap);
            s.restoreLives(1000);
            check(s.getLives() == p.integrity, "healing stops at the mode's integrity" + tag);
        }
    }

    /** Advances only the reverse controller's clock (no AI or towers): for curve checks. */
    private static void advanceController(Game g, double seconds) {
        g.setPaused(false);
        ReverseMatch r = g.getReverse();
        int n = (int) Math.round(seconds / 0.5);
        for (int i = 0; i < n; i++) r.update(0.5);
    }

    // ------------------------------------------------------------------ unlocks

    private static void unlockGating() {
        Game g = reverse(0, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        r.setUnlimitedCredits(true);
        for (AttackUnit u : AttackUnit.values()) {
            check(u.price > 0, u + " has a price");
            check(r.isUnlocked(u) == (u.unlockAt <= 0), u + (u.unlockAt <= 0 ? " is available at 0:00" : " is locked at 0:00"));
            if (u.unlockAt > 0) {
                check(r.sendProblem(u, null, 1).startsWith("Unlocks at"), u + " refuses to send while locked");
                check(r.send(u, null, 1, -1) == 0, u + " sends nothing while locked");
            }
        }
        // prices scale with strength: bosses dearer than any regular unit, each boss class dearer than the previous tier
        int maxRegular = 0;
        for (AttackUnit u : AttackUnit.values()) if (!u.isBoss()) maxRegular = Math.max(maxRegular, u.price);
        for (AttackUnit u : AttackUnit.values()) if (u.isBoss()) check(u.price > 5 * maxRegular, u + " costs far more than any regular unit");
        check(AttackUnit.MOAB.price < AttackUnit.DDT.price && AttackUnit.DDT.price < AttackUnit.BFB.price && AttackUnit.BFB.price < AttackUnit.ZOMG.price && AttackUnit.ZOMG.price < AttackUnit.BAD.price, "boss prices rise MOAB < DDT < BFB < ZOMG < BAD");
        check(AttackUnit.of(EnemyType.MERGE_RUN) == null && AttackUnit.of(EnemyType.QUICK_PARTITION) == null, "split children cannot be bought");
        int species = 0;
        for (EnemyType t : EnemyType.values()) if (t.isSpawnableSpecies() && AttackUnit.of(t) != null) species++;
        check(species == AttackUnit.values().length && species == 21, "all 16 species and 5 bosses are buyable, got " + species);
        // unlock order: all bosses after every regular unit, Palantir last
        double lastRegular = 0;
        for (AttackUnit u : AttackUnit.values()) if (!u.isBoss()) lastRegular = Math.max(lastRegular, u.unlockAt);
        for (AttackUnit u : AttackUnit.values()) if (u.isBoss()) check(u.unlockAt >= lastRegular, u + " unlocks after the regular units");
        for (AttackUnit u : AttackUnit.values()) check(u.unlockAt <= AttackUnit.BAD.unlockAt && u.unlockAt < ReverseMatch.DURATION, u + " unlocks before Palantir and before the run ends");
        // modifiers: locked ones are dropped from the order and the price
        EnumSet<Modifier> all = EnumSet.allOf(Modifier.class);
        check(r.effectiveModifiers(AttackUnit.STATIC, all).isEmpty() && r.price(AttackUnit.STATIC, all, 1) == AttackUnit.STATIC.price, "locked modifiers cost nothing and do nothing");
        advanceController(g, 90);
        check(r.isUnlocked(Modifier.REGROW) && !r.isUnlocked(Modifier.CAMO) && !r.isUnlocked(Modifier.FORTIFIED), "Regrow unlocks at 1:30, before Camo and Fortified");
        check(r.isUnlocked(AttackUnit.SINGLY) && !r.isUnlocked(AttackUnit.SELECTION), "1:30: linked lists open, the 2:00 tier still locked");
        advanceController(g, 150);   // 4:00
        check(r.isUnlocked(Modifier.CAMO) && r.isUnlocked(Modifier.FORTIFIED), "Camo and Fortified unlock by 4:00");
        check(r.price(AttackUnit.STATIC, all, 1) == (int) Math.round(AttackUnit.STATIC.price * 1.3 * 1.5 * 2), "surcharges multiply: x1.3 Regrow, x1.5 Camo, x2 Fortified");
        check(r.price(AttackUnit.QUICK, EnumSet.of(Modifier.CAMO), 5) == 5 * (int) Math.round(AttackUnit.QUICK.price * 1.5), "price of a batch is per unit x count");
        check(r.effectiveModifiers(AttackUnit.BAD, all).isEmpty() && AttackUnit.BAD.priceWith(all) == AttackUnit.BAD.price, "Palantir carries no modifiers");
        check(!r.isUnlocked(AttackUnit.MOAB) && r.isUnlocked(AttackUnit.HEAP), "4:00: the 4:00 sorters are open, bosses are not");
        advanceController(g, 60);   // 5:00
        check(r.isUnlocked(AttackUnit.MOAB) && !r.isUnlocked(AttackUnit.BFB), "the MOAB unlocks at 5:00, the BFB later");
        // exploits are gated too
        Game h = reverse(0, Difficulty.ON);
        h.getReverse().setUnlimitedCredits(true);
        for (AttackAbility a : AttackAbility.values()) check(h.getReverse().abilityProblem(a).startsWith("Unlocks at"), a + " is locked at 0:00");
        // uplink closes at the end of the run
        Game z = reverse(0, Difficulty.ON);
        advanceController(z, ReverseMatch.DURATION);
        check(z.getReverse().isUplinkClosed() && z.getReverse().sendProblem(AttackUnit.PRIMITIVE, null, 1) != null && z.getReverse().send(AttackUnit.PRIMITIVE, null, 1, -1) == 0,
            "nothing can be sent once the training run is over");
        check(z.getReverse().getEpochsDone() == ReverseMatch.EPOCHS, "all " + ReverseMatch.EPOCHS + " epochs counted");
    }

    // ------------------------------------------------------------------ uplink

    private static void spawning() {
        Game g = reverse(0, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        double c0 = r.getCredits();
        int n = r.send(AttackUnit.STATIC, null, 5, 0);
        check(n == 5 && r.getQueued() == 5 && r.getUnitsBought() == 5, "5 Static Arrays queued");
        check(Math.abs(r.getCredits() - (c0 - 5 * AttackUnit.STATIC.price)) < 1e-9 && r.getCreditsSpent() == 5 * AttackUnit.STATIC.price, "paid 5 x " + AttackUnit.STATIC.price);
        int affordable = (int) (r.getCredits() / AttackUnit.DYNAMIC.price);
        check(r.send(AttackUnit.DYNAMIC, null, 100, -1) == affordable && r.getCredits() < AttackUnit.DYNAMIC.price, "a big order buys as many as the credits allow (" + affordable + ")");
        advanceController(g, 1.0);
        check(g.getEnemyManager().getTotalSpawned() == 0, "nothing leaves the uplink during the " + (int) ReverseMatch.HANDSHAKE + " s handshake");
        Game s = reverse(0, Difficulty.ON);
        ReverseMatch rs = s.getReverse();
        rs.send(AttackUnit.STATIC, EnumSet.of(Modifier.CAMO), 4, 1);   // Camo is still locked: ignored
        for (int i = 0; i < (int) (ReverseMatch.HANDSHAKE / Game.DT) + 1; i++) rs.update(Game.DT);
        s.getEnemyManager().update(0);
        List<Enemy> es = s.getEnemyManager().getEnemies();
        check(es.size() == 1, "the first unit spawns when the handshake ends (" + es.size() + ")");
        rs.update(ReverseMatch.SPAWN_GAP / 2); s.getEnemyManager().update(0);
        check(s.getEnemyManager().getEnemies().size() == 1, "the next one waits for the spawn gap");
        for (int i = 0; i < 4; i++) rs.update(ReverseMatch.SPAWN_GAP);
        s.getEnemyManager().update(0);
        check(s.getEnemyManager().getEnemies().size() == 4 && rs.getQueued() == 0 && rs.getUnitsSpawned() == 4, "all 4 spawned one gap apart");
        for (Enemy e : s.getEnemyManager().getEnemies()) {
            check(e.getType() == EnemyType.STATIC_ARRAY && e.getRouteIndex() == 1, "on the chosen lane");
            check(e.getDistance() < 20, "entered at the start of the track (" + e.getDistance() + ")");
            check(!e.isCamo(), "a locked modifier was not applied");
        }
        // normal mechanics: a killed Static Array splits into a Primitive Variable
        Enemy first = s.getEnemyManager().getEnemies().get(0);
        double earned0 = s.getTotalCashEarned();
        killOutright(s, first);
        check(s.getEnemyManager().countOfType(EnemyType.PRIMITIVE_VARIABLE) == 1, "sent units split like campaign enemies");
        check(Math.abs(s.getTotalCashEarned() - earned0 - EnemyType.STATIC_ARRAY.reward * ReverseMatch.KILL_REWARD_SCALE) < 1e-9, "the defender is paid the listed reward for the kill");
        // modifiers, bosses and queue limit
        Game b = reverse(0, Difficulty.ON);
        ReverseMatch rb = b.getReverse();
        rb.setUnlimitedCredits(true);
        advanceController(b, 300);
        rb.send(AttackUnit.MOAB, EnumSet.of(Modifier.FORTIFIED, Modifier.CAMO), 1, -1);
        rb.send(AttackUnit.QUICK, EnumSet.of(Modifier.REGROW), 2, -1);
        for (int i = 0; i < 40; i++) rb.update(Game.DT);
        b.getEnemyManager().update(0);
        Enemy boss = null; int regrow = 0;
        for (Enemy e : b.getEnemyManager().getEnemies()) { if (e.isBoss()) boss = e; if (e.isRegrow()) regrow++; }
        check(boss instanceof Boss && boss.isFortified() && boss.isCamo(), "a Fortified Camo MOAB is a real boss");
        check(boss != null && boss.getMaxHp() == 2 * EnemyType.BELLARMINE_COLLEGE_PREP.baseHp, "Fortified doubles its HP");
        check(regrow == 2, "Regrow applied to the Quick Sorts");
        int waiting = rb.getQueued();
        int added = rb.send(AttackUnit.PRIMITIVE, null, 1000, -1);
        check(rb.getQueued() == ReverseMatch.MAX_QUEUE && added == ReverseMatch.MAX_QUEUE - waiting, "the queue holds at most " + ReverseMatch.MAX_QUEUE);
        check("Uplink queue full".equals(rb.sendProblem(AttackUnit.PRIMITIVE, null, 1)), "a full queue refuses more");
        // not enough credits
        Game p = reverse(0, Difficulty.ON);
        p.getReverse().send(AttackUnit.DYNAMIC, null, 1000, -1);
        check("Not enough credits".equals(p.getReverse().sendProblem(AttackUnit.DYNAMIC, null, 1)), "out of credits");
        // long tracks: units move faster
        Game lm = reverse(1, Difficulty.ON);
        lm.getReverse().send(AttackUnit.PRIMITIVE, null, 1, -1);
        for (int i = 0; i < (int) (ReverseMatch.HANDSHAKE / Game.DT) + 2; i++) lm.getReverse().update(Game.DT);
        lm.getEnemyManager().update(0);
        Enemy fast = lm.getEnemyManager().getEnemies().get(0);
        check(Math.abs(fast.getSpeedScale() - lm.getReverse().getTrackSpeed()) < 1e-9 && fast.getSpeedScale() > 2, "on The Legacy Monolith units get the track speed-up");
    }

    // ------------------------------------------------------------------ exploits

    private static void exploits() {
        Game g = reverse(0, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        advance(g, 245);   // all exploits unlocked; the AI has built a few towers
        r.setUnlimitedCredits(true);
        check(r.abilityProblem(AttackAbility.OVERCLOCK) != null && r.abilityProblem(AttackAbility.OVERCLOCK).contains("No units"), "Overclock needs units on the track");
        Enemy e = spawnAt(g, EnemyType.MERGE_SORT, null, 0, 50);
        double m0 = g.getGlobalEnemySpeedMultiplier();
        check(r.useAbility(AttackAbility.OVERCLOCK), "Overclock fires");
        check(Math.abs(g.getGlobalEnemySpeedMultiplier() - m0 * AttackAbility.OVERCLOCK_SPEED) < 1e-9, "Overclock: units +50% speed");
        check(r.cooldownLeft(AttackAbility.OVERCLOCK) == AttackAbility.OVERCLOCK.cooldown && r.abilityProblem(AttackAbility.OVERCLOCK).startsWith("Recharging"), "then it recharges");
        for (int i = 0; i < (int) (AttackAbility.OVERCLOCK.duration / Game.DT) + 2; i++) r.update(Game.DT);
        check(Math.abs(g.getGlobalEnemySpeedMultiplier() - m0) < 1e-9, "the speed boost ends after 6 s");
        e.takeDamage(3, g.getTime());
        double hpBefore = e.getHp();
        check(r.useAbility(AttackAbility.HOTFIX) && e.getHp() == e.getMaxHp() && hpBefore < e.getMaxHp(), "Hotfix heals units to full");
        List<Tower> ts = g.getTowerManager().getPlayerTowers();
        check(!ts.isEmpty(), "the AI has towers to jam");
        check(r.useAbility(AttackAbility.ZERO_DAY), "Zero-Day fires");
        int jammed = 0;
        for (Tower t : ts) if (t.isSurveilled()) jammed++;
        check(jammed >= 1 && jammed <= AttackAbility.ZERO_DAY_TARGETS, "Zero-Day jams up to 3 towers, got " + jammed);
        Tower top = null;
        for (Tower t : ts) if (top == null || t.getInvestedCost() > top.getInvestedCost()) top = t;
        check(top != null && (top.isSurveilled() || top.isSurveillanceImmune()), "the most expensive tower is among them");
        check(r.getUses(AttackAbility.ZERO_DAY) == 1 && r.getUses(AttackAbility.HOTFIX) == 1, "uses counted");
        // costs are real without unlimited credits
        Game c = reverse(0, Difficulty.ON);
        ReverseMatch rc = c.getReverse();
        advanceController(c, 240);
        spawnAt(c, EnemyType.PRIMITIVE_VARIABLE, null, 0, 50);
        double before = rc.getCredits();
        check(rc.useAbility(AttackAbility.OVERCLOCK) && Math.abs(rc.getCredits() - (before - AttackAbility.OVERCLOCK.cost)) < 1e-9, "Overclock costs " + AttackAbility.OVERCLOCK.cost);
    }

    // ------------------------------------------------------------------ the defender AI

    private static void defenderPlaysLegally() {
        for (Difficulty d : new Difficulty[] { Difficulty.O1, Difficulty.ON2 }) {
            Game g = reverse(d == Difficulty.O1 ? 0 : 2, d);
            ReverseMatch r = g.getReverse();
            // the Expert also faces a Primitive flood (it must keep paying for towers while killing); the Novice builds in peace
            AttackerBot bot = new AttackerBot(r, d == Difficulty.O1 ? AttackerBot.Style.PASSIVE : AttackerBot.Style.SPAM);
            double minCash = Double.MAX_VALUE;
            for (int i = 0; i < (int) (600 / Game.DT) && g.getState() == Game.State.PLAYING; i++) {
                bot.tick(Game.DT);
                g.step(Game.DT);
                g.getEvents().clear();
                minCash = Math.min(minCash, g.getCash());
            }
            String tag = " [" + r.getProfile() + "]";
            List<Tower> ts = g.getTowerManager().getPlayerTowers();
            check(g.getState() == Game.State.PLAYING, "the AI survives ten minutes" + tag);
            check(ts.size() >= 8, "the AI built a defence (" + ts.size() + " towers)" + tag);
            check(r.getAI().getActionCount() > ts.size(), "and upgraded it" + tag);
            check(minCash >= 0, "never spent money it did not have" + tag);
            int upgraded = 0, heroes = 0;
            java.util.EnumSet<TowerType> heroTypes = java.util.EnumSet.noneOf(TowerType.class);
            double invested = 0;
            for (Tower t : ts) {
                if (t.getTier() > 0) upgraded++;
                if (t.getType().isHero()) { heroes++; check(heroTypes.add(t.getType()), "one copy of " + t.getType() + tag); check(g.isHeroUnlocked(t.getType()), t.getType() + " was unlocked in the Hero Store first" + tag); }
                check(g.getMap().isBuildable(t.getPosition(), t.getRadius()), t + " stands on buildable ground" + tag);
                for (Tower o : ts) if (o != t) check(o.getPosition().dist(t.getPosition()) >= o.getRadius() + t.getRadius() - 1e-6, t + " does not overlap " + o + tag);
                if (!t.isAbilityLocked() && TowerCatalog.abilityNeedsUnlock(t.getType())) check(t.isMaxed(), t + " had its ability unlocked only at max tier" + tag);
                invested += t.getInvestedCost();
                if (t.getType().isHero()) invested += TowerCatalog.get(t.getType()).unlockCost;
            }
            check(upgraded >= 4, "upgraded several towers (" + upgraded + ")" + tag);
            check(heroes <= g.getHeroLimit() && g.getTowerManager().heroesDeployedThisMatch() <= TowerType.heroes().length, "hero cap respected (" + heroes + " / " + g.getHeroLimit() + ")" + tag);
            check(g.getHeroLimit() == lindefense.tower.TowerManager.MAX_HEROES_PER_GAME, "the normal cap of " + lindefense.tower.TowerManager.MAX_HEROES_PER_GAME + tag);
            double spent = Game.START_CASH + g.getTotalCashEarned() - g.getCash();
            check(Math.abs(invested - spent) < 2, "every dollar it spent is in its towers, heroes and unlocks (" + (int) invested + " vs " + (int) spent + ")" + tag);
            check(r.getLastAiAction() != null && r.getLastAiAction().text.startsWith("AI "), "the feed reports the AI's actions" + tag);
            if (d == Difficulty.ON2) check(heroes >= 2, "the Expert deploys heroes (" + heroes + ")" + tag);
        }
        // the Expert buys $15,000 ability unlocks once it has a core
        Game x = reverse(0, Difficulty.ON2);
        AttackerBot.play(x, AttackerBot.Style.PASSIVE);
        int unlocks = 0;
        for (Tower t : x.getTowerManager().getPlayerTowers()) if (TowerCatalog.abilityNeedsUnlock(t.getType()) && !t.isAbilityLocked()) { unlocks++; check(t.isMaxed(), t + " maxed before its unlock"); }
        check(unlocks >= 1, "the Expert unlocked abilities (" + unlocks + ")");
        int unlockFeed = 0;
        for (ReverseMatch.FeedEntry fe : x.getReverse().getFeed()) if (fe.action == DefenderAI.Action.ABILITY_UNLOCK) unlockFeed++;
        check(unlockFeed >= 1 || x.getReverse().getFeed().size() == ReverseMatch.FEED_SIZE, "unlocks show in the feed");
        // the Hero Store collection of a reverse match is in memory: the player's saved unlocks are never used or changed
        Game n = reverse(0, Difficulty.ON);
        check(!n.getHeroCollection().isUnlocked(TowerType.MR_LINDEMANN) && n.getHeroCollection().unlocked().isEmpty(), "the AI starts with no heroes unlocked");
    }

    // ------------------------------------------------------------------ win / loss

    private static void winAndLoss() {
        // breach: integrity 0 -> the game's DEFEAT state = attacker wins
        Game g = reverse(0, Difficulty.ON);
        Enemy e = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, 10);
        g.loseLives(Game.START_LIVES, e);
        advance(g, 3);
        check(g.getState() == Game.State.DEFEAT && g.getReverse().attackerWon() && !g.getReverse().defenderHeld(), "integrity 0 = attacker wins");
        // timer: a passive attacker loses when the run ends (nothing on the track, so no overtime)
        Game p = reverse(0, Difficulty.ON);
        advance(p, ReverseMatch.DURATION - 1);
        check(p.getState() == Game.State.PLAYING && !p.getReverse().isUplinkClosed(), "still running a second before the end");
        advance(p, 2);
        check(p.getState() == Game.State.VICTORY && p.getReverse().defenderHeld() && !p.getReverse().attackerWon(), "the defender holds when the run ends");
        check(p.getReverse().getElapsed() < ReverseMatch.DURATION + 1, "no overtime with an empty track");
        // overtime: units already sent keep the match alive, at most OVERTIME seconds
        Game o = reverse(1, Difficulty.O1);
        ReverseMatch ro = o.getReverse();
        advance(o, ReverseMatch.DURATION - 3);
        ro.setUnlimitedCredits(true);
        ro.send(AttackUnit.BAD, null, 1, -1);
        advance(o, 6);
        check(ro.isUplinkClosed() && o.getState() == Game.State.PLAYING, "overtime while Palantir walks");
        advance(o, ReverseMatch.OVERTIME + 2);
        check(o.getState() != Game.State.PLAYING, "overtime is capped at " + (int) ReverseMatch.OVERTIME + " s");
        check(ro.getElapsed() <= ReverseMatch.DURATION + ReverseMatch.OVERTIME + 2.5, "ended by " + ReverseMatch.clock(ro.getElapsed()));
        // Palantir's death is just a kill in reverse mode
        Game k = reverse(0, Difficulty.ON);
        Enemy pal = spawnAt(k, EnemyType.PALANTIR, null, 0, 100);
        killOutright(k, pal);
        advance(k, 6);
        check(k.getState() == Game.State.PLAYING && !k.isVictorySequenceActive(), "killing the attacker's Palantir does not end the match");
        // declareDefenderVictory never overrides a breach in progress
        Game q = reverse(0, Difficulty.ON);
        Enemy qe = spawnAt(q, EnemyType.PRIMITIVE_VARIABLE, null, 0, 10);
        q.loseLives(Game.START_LIVES, qe);
        q.declareDefenderVictory("x");
        advance(q, 3);
        check(q.getState() == Game.State.DEFEAT, "a breach beats the timer on the same tick");
        // restart keeps the map and the defender profile
        Game r0 = reverse(2, Difficulty.ON2);
        r0.getReverse().setUnlimitedCredits(true);
        advance(r0, 30);
        Game r1 = ReverseMatch.restart(r0);
        check(r1 != r0 && r1.isReverse() && r1.getReverse().getProfile() == DefenderProfile.EXPERT && r1.getMap().getName().equals(r0.getMap().getName()), "restart: same map and AI");
        check(r1.getReverse().getElapsed() == 0 && r1.getReverse().hasUnlimitedCredits() && r1.getTowerManager().getTowers().isEmpty(), "restart: fresh clock and board, admin credits kept");
        // the normal game is untouched
        Game normal = new Game(MapCatalog.create(0), 5);
        check(!normal.isReverse() && normal.getReverse() == null, "the normal game has no reverse controller");
    }

    // ------------------------------------------------------------------ whole matches

    private static void wholeMatches() {
        for (int map : new int[] { 0, 1, 5 }) {
            AttackerBot.Outcome win = AttackerBot.play(map, 42, Difficulty.O1, AttackerBot.Style.REASONABLE);
            check(win.attackerWon && win.time < ReverseMatch.DURATION, "a scripted attacker beats the Novice AI on map " + map + " (" + win + ")");
            AttackerBot.Outcome idle = AttackerBot.play(map, 42, Difficulty.O1, AttackerBot.Style.PASSIVE);
            check(!idle.attackerWon && idle.defenderLives == DefenderProfile.NOVICE.integrity && idle.time >= ReverseMatch.DURATION, "a do-nothing attacker loses on map " + map + " (" + idle + ")");
        }
        AttackerBot.Outcome spam = AttackerBot.play(0, 42, Difficulty.ON, AttackerBot.Style.SPAM);
        check(!spam.attackerWon, "flooding Primitive Variables does not beat the Competent AI (" + spam + ")");
        AttackerBot.Outcome hard = AttackerBot.play(1, 42, Difficulty.ONN, AttackerBot.Style.REASONABLE);
        AttackerBot.Outcome easy = AttackerBot.play(1, 42, Difficulty.O1, AttackerBot.Style.REASONABLE);
        check(!hard.attackerWon || hard.time > easy.time, "the Superintelligence lasts longer than the Novice (" + hard + " vs " + easy + ")");
        check(hard.defenderEarned > easy.defenderEarned, "and is funded better");
    }

    private static java.awt.event.KeyEvent key(int code) {
        return new java.awt.event.KeyEvent(new javax.swing.JPanel(), java.awt.event.KeyEvent.KEY_PRESSED, 0, 0, code, java.awt.event.KeyEvent.CHAR_UNDEFINED);
    }

    /**
     * The real in-game screen in reverse mode (painted nowhere): a card click sends the default x5, SPACE repeats, X
     * changes the quantity, locked cards refuse; waves, the shop, the Hero Store and tower actions are off; AI towers can
     * be inspected but not changed; the pause menu still toggles; the end screen speaks for the attacker.
     */
    private static void uiRouting() {
        Game g = reverse(0, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        lindefense.ui.GameScreen s = new lindefense.ui.GameScreen(null, g);
        s.frame(0.02);
        double[] c = lindefense.ui.AttackPanel.cardCenter(AttackUnit.PRIMITIVE.ordinal());
        s.mousePressed(c[0], c[1], false);
        check(r.getQueued() == 5 && r.getUnitsBought() == 5, "clicking the Primitive card sends 5 (" + r.getQueued() + ")");
        s.keyPressed(key(java.awt.event.KeyEvent.VK_SPACE));
        check(r.getQueued() == 10, "SPACE repeats the last send (" + r.getQueued() + ")");
        s.keyPressed(key(java.awt.event.KeyEvent.VK_X));
        s.keyPressed(key(java.awt.event.KeyEvent.VK_SPACE));
        check(r.getQueued() == 20, "X switches to x10 (" + r.getQueued() + ")");
        check(g.getWave() == 0 && !g.getWaveManager().isWaveActive(), "SPACE never starts a campaign wave in reverse mode");
        double[] boss = lindefense.ui.AttackPanel.cardCenter(AttackUnit.MOAB.ordinal());
        s.mousePressed(boss[0], boss[1], false);
        check(r.getQueued() == 20, "a locked card sends nothing");
        s.startWave();
        s.toggleAuto();
        check(g.getWave() == 0 && !g.getWaveManager().isAutoStart(), "Start Wave and Auto are off");
        s.toggleHeroStore();
        check(!s.isHeroStoreOpen(), "the Hero Store stays closed");
        s.beginPlacing(TowerType.GPT);
        check(s.getPlacing() == null, "the player cannot place towers");
        advance(g, 6);
        Tower t = g.getTowerManager().getPlayerTowers().get(0);
        s.mousePressed(t.getPosition().x, t.getPosition().y + lindefense.ui.Ui.WORLD_Y, false);
        check(s.getSelectedTower() == t, "an AI tower can be selected for inspection");
        int tier = t.getTier(); double cash = g.getCash(); lindefense.tower.Targeting tg = t.getTargeting();
        for (int k : new int[] { java.awt.event.KeyEvent.VK_U, java.awt.event.KeyEvent.VK_S, java.awt.event.KeyEvent.VK_T, java.awt.event.KeyEvent.VK_A }) s.keyPressed(key(k));
        s.upgradeSelected(); s.sellSelected(); s.unlockAbilitySelected(); s.cycleTargeting(1);
        check(t.isAlive() && t.getTier() == tier && g.getCash() == cash && t.getTargeting() == tg, "upgrade / sell / targeting / unlock are read-only for the AI's towers");
        s.frame(0.02);
        s.escapePressed();
        check(s.isMenuOpen() && g.isPaused(), "Esc opens the pause menu");
        s.keyPressed(key(java.awt.event.KeyEvent.VK_SPACE));
        check(r.getQueued() <= 20, "attacker keys are inactive while paused");
        s.escapePressed();
        check(!s.isMenuOpen() && !g.isPaused(), "Esc resumes");
        s.keyPressed(key(java.awt.event.KeyEvent.VK_3));
        check(g.getSpeed() == 3, "speed keys still work");
        // the end screen speaks for the attacker
        Enemy e = spawnAt(g, EnemyType.PRIMITIVE_VARIABLE, null, 0, 10);
        g.loseLives(Game.START_LIVES, e);
        for (int i = 0; i < 200 && g.getState() == Game.State.PLAYING; i++) s.frame(Game.DT);
        s.frame(0.02);
        check(g.getState() == Game.State.DEFEAT && r.attackerWon(), "breached");
    }

    /** The balance bot runs on the shared DefenderAI and still clears the opening waves. */
    private static void sharedDefenderAI() {
        lindefense.tools.AutoPlayer.Result res = lindefense.tools.AutoPlayer.run(0, 1234, Difficulty.O1, 12, 999, false, false);
        check(res.completed == 12 && res.lives == Game.START_LIVES, "AutoPlayer (via DefenderAI) clears 12 waves flawlessly (" + res.completed + ", lives " + res.lives + ")");
        check(res.towers >= 4, "and builds a defence (" + res.towers + " towers)");
        // the hero cap: the broad roster never buys more Hero Store unlocks than it can deploy
        lindefense.tools.AutoPlayer.Result mixed = lindefense.tools.AutoPlayer.run(0, 1234, Difficulty.O1, 40, 999, false, false, true);
        check(mixed.game.getHeroCollection().unlocked().size() <= mixed.game.getHeroLimit(), "the mixed plan buys at most " + mixed.game.getHeroLimit() + " heroes ("
            + mixed.game.getHeroCollection().unlocked().size() + ")");
    }
}
