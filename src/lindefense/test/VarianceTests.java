package lindefense.test;

import static lindefense.test.TestKit.*;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;
import lindefense.combat.DamageType;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Shop;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.variance.BreakingNews;
import lindefense.variance.Knob;
import lindefense.variance.Mods;
import lindefense.variance.PatchNote;
import lindefense.variance.RunSeed;
import lindefense.variance.RunVariance;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Run variance: "Patch Notes" (drafted run modifiers) and "Breaking News" (one-wave events). Checks that every card's
 * upside and downside, and every event, really changes the game by its stated number (each knob is probed through the
 * real economy / combat / tower / wave code against a baseline game), the draft schedule (waves 1, 20, 40, 60, 80; the
 * next wave is blocked until a pick), the news rate and one-wave lifetime, determinism from the seed (independent of
 * the combat RNG), refunds of what was actually paid, seed codes, and the off switch (the default: every hook neutral).
 */
public final class VarianceTests {
    private VarianceTests() { }

    /** Knobs some probe verified against the real game (every knob a card or event uses must end up here). */
    private static final Set<Knob> probed = EnumSet.noneOf(Knob.class);

    /** Runs every run-variance test group. */
    public static void runAll() {
        run("variance.offByDefault", VarianceTests::offByDefault);
        run("variance.offSwitch", VarianceTests::offSwitch);
        run("variance.cardTable", VarianceTests::cardTable);
        run("variance.cardEffectsApply", VarianceTests::cardEffectsApply);
        run("variance.newsEffectsApply", VarianceTests::newsEffectsApply);
        run("variance.everyKnobProbed", VarianceTests::everyKnobProbed);
        run("variance.draftSchedule", VarianceTests::draftSchedule);
        run("variance.autoPickers", VarianceTests::autoPickers);
        run("variance.newsRate", VarianceTests::newsRate);
        run("variance.newsLifetime", VarianceTests::newsLifetime);
        run("variance.determinism", VarianceTests::determinism);
        run("variance.refundsWhatWasPaid", VarianceTests::refundsWhatWasPaid);
        run("variance.seedsAndRestart", VarianceTests::seedsAndRestart);
    }

    // ------------------------------------------------------------------ helpers
    /** A game past wave 1 with variance on, no card taken and no draft pending (wave 2 is next). */
    private static Game clean(int map) {
        Game g = new Game(MapCatalog.create(map), 42, Difficulty.O1);
        check(g.startNextWave(), "variance-off game starts wave 1 at once");
        finish(g);
        g.getVariance().enable();
        return g;
    }

    /** Ends the running wave instantly through the normal completion hook (bonus, variance bookkeeping). */
    private static void finish(Game g) {
        g.getEnemyManager().clear();
        g.getWaveManager().endWave();
        g.onWaveCompleted(g.getWave(), g.getWaveManager().getCurrentDef());
    }

    /** Starts and instantly completes the next wave; false if it could not start. */
    private static boolean playThrough(Game g) {
        if (!g.startNextWave()) return false;
        finish(g);
        return true;
    }

    private static int round5(int list, double mult) { return mult == 1 ? list : (int) (Math.round(list * mult / 5.0) * 5); }

    private static boolean near(double a, double b) { return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)); }

    private static Tower place(Game g, TowerType t) {
        Tower tw = g.placeTower(t, buildableNear(g, new Vec(400, 250), 320));
        check(tw != null, "placed " + t + " (" + g.placementProblem(t, buildableNear(g, new Vec(400, 250), 320)) + ")");
        return tw;
    }

    private static Enemy spawnBig(Game g, EnemyType t, EnumSet<Modifier> mods) {
        Enemy e = g.getEnemyManager().spawnScaled(t, mods, 0, 300, 1000, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }

    // ------------------------------------------------------------------ off switch
    private static void offByDefault() {
        Game g = new Game(MapCatalog.create(0), 42, Difficulty.O1);
        RunVariance v = g.getVariance();
        check(!v.isEnabled() && !v.isDraftPending() && v.getActive().isEmpty(), "a new Game has variance off");
        check(g.getWaveManager().canStartNextWave(), "no draft blocks wave 1");
        check(v.fireRate() == 1 && v.range() == 1 && v.enemyHp() == 1 && v.enemySpeed() == 1 && v.killIncome() == 1 && v.waveBonus() == 1
            && v.abilityCooldown() == 1, "every multiplier hook is exactly 1");
        check(v.leakLives(5) == 5 && v.closedRoute(2) == -1 && v.sellFraction(Shop.SELL_FRACTION) == Shop.SELL_FRACTION, "lives / lanes / refunds neutral");
        for (TowerType t : TowerType.shopTowers()) check(Shop.priceOf(g, t) == Shop.priceOf(t), t + " costs its list price");
        check(Shop.abilityUnlockCost(g) == TowerCatalog.ABILITY_UNLOCK_COST, "ability unlock at list price");
        for (int w = 1; w <= WaveData.WAVE_COUNT; w++) {
            WaveDef d = WaveData.get(w);
            if (v.shapeWave(d) != d) { check(false, "wave " + w + " reshaped while off"); break; }
        }
        Enemy e = spawnBig(g, EnemyType.STATIC_ARRAY, null);
        check(v.damageAgainst(e) == 1, "damage neutral");
        int played = 0;
        while (played < 99 && playThrough(g)) played++;
        check(played == 99, "99 waves play without a draft while off (" + played + ")");
        check(v.getNewsLog().isEmpty() && v.getActive().isEmpty() && !v.isDraftPending(), "99 waves without a draft or news while off");
    }

    private static void offSwitch() {
        Game g = new Game(MapCatalog.create(0), 42, Difficulty.O1);
        g.getVariance().enable();
        check(g.getVariance().isDraftPending() && !g.getWaveManager().canStartNextWave() && !g.startNextWave(), "enabled: the wave-1 draft blocks the wave");
        g.getVariance().grant(PatchNote.QUANTIZATION);
        check(g.getVariance().fireRate() == 1.2, "a granted card applies");
        g.getVariance().disable();
        check(!g.getVariance().isEnabled() && !g.getVariance().isDraftPending() && g.getVariance().fireRate() == 1 && g.getGlobalRateMultiplier() == 1,
            "disable: no draft and every hook neutral again");
        check(g.startNextWave(), "disable: the wave starts");
        // the windowed game's switch: on unless -Dlindefense.variance=off
        String old = System.getProperty("lindefense.variance");
        try {
            System.clearProperty("lindefense.variance");
            check(playerDefault(), "players get variance by default");
            System.setProperty("lindefense.variance", "off");
            check(!playerDefault(), "-Dlindefense.variance=off turns it off for players");
        } finally {
            if (old == null) System.clearProperty("lindefense.variance"); else System.setProperty("lindefense.variance", old);
        }
    }

    /** Mirrors LindefenseProgram.varianceForPlayers (UI class, not loadable headless without AWT). */
    private static boolean playerDefault() {
        String v = System.getProperty("lindefense.variance");
        return v == null || !(v.equalsIgnoreCase("off") || v.equalsIgnoreCase("false"));
    }

    // ------------------------------------------------------------------ tables
    private static void cardTable() {
        check(PatchNote.values().length >= 15 && PatchNote.values().length <= 20, "15-20 patch notes (" + PatchNote.values().length + ")");
        Set<String> titles = new HashSet<>(), chips = new HashSet<>();
        for (PatchNote p : PatchNote.values()) {
            check(titles.add(p.title) && chips.add(p.chip), p + " title and chip are unique");
            check(p.chip.length() <= 16 && p.chip.equals(p.chip.toUpperCase()), p + " chip is short upper case");
            check(!p.flavor.isEmpty(), p + " has flavour text");
            check(!p.upsides(1).isEmpty(), p + " has an upside");
            check(!p.downsides(1).isEmpty(), p + " has a downside");
            for (Mods.Effect e : p.mods().effects(1)) check(!e.text.isEmpty() && !e.text.contains("NaN"), p + " effect text " + e);
            check(!p.mods().has(Knob.ALL_CAMO) && !p.mods().has(Knob.CLOSE_LANE) && !p.mods().has(Knob.REFRESH_ABILITIES), p + " uses run-long knobs only");
        }
        check(BreakingNews.values().length >= 6, "at least six news events");
        for (BreakingNews n : BreakingNews.values()) {
            check(!n.mods().isNeutral() && !n.headline(10).isEmpty(), n + " changes something and has a headline");
            check(n.minWave >= RunVariance.NEWS_FIRST_WAVE, n + " never before wave " + RunVariance.NEWS_FIRST_WAVE);
            // harsh events never land on a boss wave
            boolean harsh = false;
            for (Mods.Effect e : n.mods().effects(10)) if (!e.good) harsh = true;
            if (harsh && n != BreakingNews.GPU_SHORTAGE) check(!n.onBossWaves, n + " (a downside) is kept off boss waves");
        }
        // stacking caps: one card or event always fits inside the bounds; piling several on one knob is held at the bound
        List<String> outside = new ArrayList<>();
        for (PatchNote p : PatchNote.values()) for (Knob k : Knob.values()) if (p.mods().get(k) < k.min || p.mods().get(k) > k.max) outside.add(p + "." + k);
        for (BreakingNews n : BreakingNews.values()) for (Knob k : Knob.values()) if (n.mods().get(k) < k.min || n.mods().get(k) > k.max) outside.add(n + "." + k);
        check(outside.isEmpty(), "every single card and event fits inside the stacking bounds " + outside);
        Game st = clean(0);
        st.getVariance().grant(PatchNote.DATA_DROUGHT);
        st.getVariance().grant(PatchNote.VENTURE_CAPITAL);
        st.getVariance().grant(PatchNote.BATCH_INFERENCE);
        check(near(st.getVariance().killIncome(), Knob.KILL_INCOME.min), "three income cuts stop at x" + Knob.KILL_INCOME.min + " (" + st.getVariance().killIncome() + ")");
        st.getVariance().grant(PatchNote.EDGE_DEPLOYMENT);
        st.getVariance().grant(PatchNote.COMPUTE_FUTURES);
        st.getVariance().forceNews(BreakingNews.GPU_SHORTAGE, -1);
        check(st.getVariance().upgradePrice(1000) == (int) Math.round(1000 * Knob.UPGRADE_COST.max), "stacked upgrade surcharges stop at x" + Knob.UPGRADE_COST.max);
        st.getVariance().grant(PatchNote.QUANTIZATION);
        st.getVariance().grant(PatchNote.GRADIENT_CLIPPING);
        st.getVariance().grant(PatchNote.CONSTITUTIONAL_AI);
        Enemy plain = spawnBig(st, EnemyType.DYNAMIC_ARRAY, null);
        check(near(st.getVariance().damageAgainst(plain), Knob.DAMAGE.min), "stacked damage cuts stop at x" + Knob.DAMAGE.min);
        Mods a = Mods.of().set(Knob.DAMAGE, 1.2).set(Knob.SELL_REFUND, -0.2), b = Mods.of().set(Knob.DAMAGE, 0.5).set(Knob.SELL_REFUND, 0.1).flag(Knob.ALL_CAMO);
        Mods c = a.combine(b);
        check(near(c.get(Knob.DAMAGE), 0.6) && near(c.get(Knob.SELL_REFUND), -0.1) && c.has(Knob.ALL_CAMO) && Mods.NONE.isNeutral(), "mods combine: multiply, add, or");
    }

    // ------------------------------------------------------------------ every card / event really applies
    private static void cardEffectsApply() {
        for (PatchNote p : PatchNote.values()) {
            verify(p.name(), p.mods(), () -> { Game g = clean(0); g.getVariance().grant(p); return g; });
            Game g = clean(0);
            double before = g.getCash();
            g.getVariance().grant(p);
            check(g.getVariance().getActive().contains(p), p + " is active after the grant");
            int cash = p.mods().cashFor(2);
            check(near(g.getCash() - before, cash), p + " pays its one-off credits (" + cash + ")");
            if (cash > 0) probed.add(Knob.CASH_NOW);
            if (cash > 0 && p.mods().has(Knob.CASH_PER_WAVE)) {
                check(p.mods().cashFor(40) > cash, p + " one-off credits grow with the wave");
                probed.add(Knob.CASH_PER_WAVE);
            }
        }
    }

    private static void newsEffectsApply() {
        for (BreakingNews n : BreakingNews.values()) {
            verify(n.name(), n.mods(), () -> { Game g = clean(0); g.getVariance().forceNews(n, 1); return g; });
            Game g = clean(0);
            double before = g.getCash();
            g.getVariance().forceNews(n, 1);
            check(near(g.getCash() - before, n.mods().cashFor(2)), n + " pays its one-off credits");
        }
        // Solar Flare: every ability cooldown resets when its wave starts
        Game g = clean(0);
        g.addCash(100_000, null);
        Tower t = towerNearTrack(g, TowerType.CLAUDE, 3, 400);
        check(g.unlockAbility(t), "Claude ability unlocked");
        spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 300);
        check(g.activateAbility(t) && t.getAbilityCooldownRemaining() > 0, "ability on cooldown");
        g.getVariance().forceNews(BreakingNews.SOLAR_FLARE, -1);
        check(t.getAbilityCooldownRemaining() > 0, "Solar Flare waits for its wave");
        check(g.startNextWave() && t.getAbilityCooldownRemaining() == 0, "Solar Flare resets cooldowns when the wave starts");
        probed.add(Knob.REFRESH_ABILITIES);
        finish(g);
        check(g.getVariance().getNews() == null, "Solar Flare ends with its wave");
    }

    /** Probes every knob {@code m} sets through the real game, comparing a fresh modded game with a fresh baseline. */
    private static void verify(String tag, Mods m, Supplier<Game> modded) {
        Supplier<Game> base = () -> clean(0);
        TowerType gpt = TowerType.GPT;
        if (m.has(Knob.TOWER_COST)) {
            Game g = modded.get();
            int want = round5(TowerCatalog.get(gpt).baseCost, m.get(Knob.TOWER_COST));
            double before = g.getCash();
            check(Shop.priceOf(g, gpt) == want, tag + ": GPT costs " + want + " (got " + Shop.priceOf(g, gpt) + ")");
            place(g, gpt);
            check(near(before - g.getCash(), want), tag + ": placing charges the adjusted price");
            probed.add(Knob.TOWER_COST);
        }
        if (m.has(Knob.UPGRADE_COST)) {
            Game g = modded.get();
            g.addCash(5000, null);
            Tower t = place(g, gpt);
            int list = t.nextUpgrade().cost, want = round5(list, m.get(Knob.UPGRADE_COST));
            double before = g.getCash();
            check(Shop.upgradeCost(g, t) == want && g.upgradeTower(t) && near(before - g.getCash(), want), tag + ": upgrade charges " + want + " for a " + list + " upgrade");
            probed.add(Knob.UPGRADE_COST);
        }
        if (m.has(Knob.ABILITY_UNLOCK_COST)) {
            Game g = modded.get();
            g.addCash(200_000, null);
            Tower t = towerNearTrack(g, TowerType.CLAUDE, 3, 400);
            int want = round5(TowerCatalog.ABILITY_UNLOCK_COST, m.get(Knob.ABILITY_UNLOCK_COST));
            double before = g.getCash();
            check(Shop.abilityUnlockCost(g) == want && g.unlockAbility(t) && near(before - g.getCash(), want), tag + ": ability unlock charges " + want);
            probed.add(Knob.ABILITY_UNLOCK_COST);
        }
        if (m.has(Knob.SELL_REFUND)) {
            Game g = modded.get();
            double frac = Math.max(0, Math.min(RunVariance.MAX_SELL_FRACTION, Shop.SELL_FRACTION + m.get(Knob.SELL_REFUND)));
            int paid = Shop.priceOf(g, gpt);
            Tower t = place(g, gpt);
            int want = (int) Math.floor(paid * frac);
            check(near(Shop.sellFraction(g), frac) && g.sellTower(t) == want, tag + ": selling refunds " + Math.round(frac * 100) + "% of the " + paid + " paid (" + want + ")");
            probed.add(Knob.SELL_REFUND);
        }
        if (m.has(Knob.KILL_INCOME)) {
            Game g = modded.get(), b = base.get();
            check(near(g.getRewardScale(), b.getRewardScale() * m.get(Knob.KILL_INCOME)), tag + ": kill reward scale x" + m.get(Knob.KILL_INCOME));
            Enemy e = spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 300);
            double before = g.getCash();
            g.getEnemyManager().kill(e);
            check(near(g.getCash() - before, Math.round(EnemyType.STATIC_ARRAY.reward * g.getRewardScale())), tag + ": a kill pays the scaled reward");
            probed.add(Knob.KILL_INCOME);
        }
        if (m.has(Knob.WAVE_BONUS)) {
            Game g = modded.get();
            double before = g.getCash();
            check(g.startNextWave(), tag + ": wave 2 starts");
            finish(g);
            long want = Math.round(WaveData.waveBonus(2) * m.get(Knob.WAVE_BONUS));
            check(near(g.getCash() - before, want), tag + ": wave-2 bonus is " + want + " (got " + (g.getCash() - before) + ")");
            probed.add(Knob.WAVE_BONUS);
        }
        if (m.has(Knob.INTEREST_RATE)) {
            for (double bank : new double[] { 8_000, 200_000 }) {
                Game g = modded.get();
                g.addCash(bank - g.getCash(), null);
                check(g.startNextWave(), tag + ": wave 2 starts");
                finish(g);
                double afterBonus = bank + Math.round(WaveData.waveBonus(2) * m.get(Knob.WAVE_BONUS));
                double interest = Math.floor(afterBonus * m.get(Knob.INTEREST_RATE));
                if (m.has(Knob.INTEREST_CAP)) interest = Math.min(interest, m.get(Knob.INTEREST_CAP));
                check(near(g.getCash(), afterBonus + interest) && near(g.getVariance().getLastInterest(), interest), tag + ": interest " + interest + " on " + afterBonus);
            }
            probed.add(Knob.INTEREST_RATE);
            probed.add(Knob.INTEREST_CAP);
        }
        if (m.has(Knob.DAMAGE) || m.has(Knob.BOSS_DAMAGE) || m.has(Knob.NON_BOSS_DAMAGE) || m.has(Knob.ELITE_DAMAGE) || m.has(Knob.PLAIN_DAMAGE)) {
            Object[][] kinds = { { EnemyType.DYNAMIC_ARRAY, null }, { EnemyType.DYNAMIC_ARRAY, EnumSet.of(Modifier.CAMO) },
                { EnemyType.BELLARMINE_COLLEGE_PREP, null }, { EnemyType.BELLARMINE_COLLEGE_PREP, EnumSet.of(Modifier.FORTIFIED) } };
            for (Object[] k : kinds) {
                EnemyType type = (EnemyType) k[0];
                @SuppressWarnings("unchecked") EnumSet<Modifier> mods = (EnumSet<Modifier>) k[1];
                Game g = modded.get(), b = base.get();
                g.setGlobalEnemySpeedMultiplier(0); b.setGlobalEnemySpeedMultiplier(0);
                double dm = hitFor(g, spawnBig(g, type, mods), 100, DamageType.TRUE), db = hitFor(b, spawnBig(b, type, mods), 100, DamageType.TRUE);
                double want = m.get(Knob.DAMAGE) * (type.isBoss() ? m.get(Knob.BOSS_DAMAGE) : m.get(Knob.NON_BOSS_DAMAGE))
                    * (mods == null ? m.get(Knob.PLAIN_DAMAGE) : m.get(Knob.ELITE_DAMAGE));
                check(near(dm, db * want), tag + ": damage vs " + type + (mods == null ? "" : " " + mods) + " x" + want + " (" + dm + " vs " + db + ")");
            }
            for (Knob k : new Knob[] { Knob.DAMAGE, Knob.BOSS_DAMAGE, Knob.NON_BOSS_DAMAGE, Knob.ELITE_DAMAGE, Knob.PLAIN_DAMAGE }) if (m.has(k)) probed.add(k);
        }
        if (m.has(Knob.FIRE_RATE) || m.has(Knob.RANGE)) {
            Game g = modded.get(), b = base.get();
            Tower tg = place(g, gpt), tb = place(b, gpt);
            int tierGap = tg.getTier() - tb.getTier();   // Data Drought would add a free tier; no card combines it with these knobs
            check(tierGap == 0, tag + ": same tier for the rate / range probe");
            if (m.has(Knob.FIRE_RATE)) { check(near(tg.effectiveRate(g), tb.effectiveRate(b) * m.get(Knob.FIRE_RATE)), tag + ": attack rate x" + m.get(Knob.FIRE_RATE)); probed.add(Knob.FIRE_RATE); }
            if (m.has(Knob.RANGE)) { check(near(tg.effectiveRange(g), tb.effectiveRange(b) * m.get(Knob.RANGE)), tag + ": range x" + m.get(Knob.RANGE)); probed.add(Knob.RANGE); }
        }
        if (m.has(Knob.ABILITY_COOLDOWN)) {
            Game g = modded.get();
            g.addCash(200_000, null);
            Tower t = towerNearTrack(g, TowerType.CLAUDE, 3, 400);
            check(g.unlockAbility(t), tag + ": ability unlocked");
            spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 300);
            check(g.activateAbility(t) && near(t.getAbilityCooldownRemaining(), t.getAbility().cooldown * m.get(Knob.ABILITY_COOLDOWN)),
                tag + ": cooldown " + t.getAbilityCooldownRemaining() + " = " + t.getAbility().cooldown + " x " + m.get(Knob.ABILITY_COOLDOWN));
            probed.add(Knob.ABILITY_COOLDOWN);
        }
        if (m.has(Knob.ENEMY_HP)) {
            Game g = modded.get(), b = base.get();
            check(near(g.getWaveHpScale(), b.getWaveHpScale() * m.get(Knob.ENEMY_HP)), tag + ": HP scale x" + m.get(Knob.ENEMY_HP));
            Enemy eg = spawnAt(g, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 300), eb = spawnAt(b, EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 300);
            check(Math.abs(eg.getMaxHp() - eb.getMaxHp() * m.get(Knob.ENEMY_HP)) <= 1, tag + ": spawned enemies get the HP (" + eg.getMaxHp() + " vs " + eb.getMaxHp() + ")");
            probed.add(Knob.ENEMY_HP);
        }
        if (m.has(Knob.ENEMY_SPEED)) {
            Game g = modded.get(), b = base.get();
            check(near(g.getWaveSpeedScale(), b.getWaveSpeedScale() * m.get(Knob.ENEMY_SPEED)), tag + ": speed scale x" + m.get(Knob.ENEMY_SPEED));
            Enemy eg = spawnAt(g, EnemyType.STATIC_ARRAY, null, 0, 10), eb = spawnAt(b, EnemyType.STATIC_ARRAY, null, 0, 10);
            double dg = eg.getDistance(), db = eb.getDistance();
            for (int i = 0; i < 30; i++) { g.getEnemyManager().update(Game.DT); b.getEnemyManager().update(Game.DT); }
            check(near(eg.getDistance() - dg, (eb.getDistance() - db) * m.get(Knob.ENEMY_SPEED)), tag + ": enemies travel x" + m.get(Knob.ENEMY_SPEED) + " as far");
            probed.add(Knob.ENEMY_SPEED);
        }
        if (m.has(Knob.ENEMY_COUNT) || m.has(Knob.SPAWN_GAP) || m.has(Knob.ALL_CAMO)) {
            Game g = modded.get();
            double cm = m.get(Knob.ENEMY_COUNT), gap = m.get(Knob.SPAWN_GAP);
            for (int w : new int[] { 10, 50, 90 }) {
                WaveDef d = WaveData.get(w), s = g.getVariance().shapeWave(d);
                check(s != d && s.groups.size() == d.groups.size() && s.number == w, tag + ": wave " + w + " reshaped into a new definition");
                for (int i = 0; i < d.groups.size(); i++) {
                    SpawnGroup a = d.groups.get(i), z = s.groups.get(i);
                    if (a.type.isBoss()) { check(z == a, tag + ": boss group untouched (wave " + w + ")"); continue; }
                    check(z.count == Math.max(1, (int) Math.round(a.count * cm)), tag + ": count x" + cm + " (wave " + w + ")");
                    check(near(z.interval, a.interval * gap / (1 + 0.5 * (cm - 1))), tag + ": spawn gap (wave " + w + ")");
                    check(z.modifiers.contains(Modifier.CAMO) == (m.has(Knob.ALL_CAMO) || a.modifiers.contains(Modifier.CAMO)), tag + ": camo (wave " + w + ")");
                    check(a.modifiers.equals(WaveData.get(w).groups.get(i).modifiers), tag + ": the campaign data is never modified");
                }
            }
            // the real wave spawns the reshaped groups
            check(g.startNextWave(), tag + ": wave 2 starts");
            WaveDef live = g.getWaveManager().getCurrentDef(), want = g.getVariance().shapeWave(WaveData.get(2));
            check(live.totalSpawns() == want.totalSpawns(), tag + ": the live wave uses the reshaped groups");
            for (Knob k : new Knob[] { Knob.ENEMY_COUNT, Knob.SPAWN_GAP, Knob.ALL_CAMO }) if (m.has(k)) probed.add(k);
        }
        if (m.has(Knob.CLOSE_LANE)) {
            Game g = modded.get(), b = base.get();
            int closed = g.getVariance().closedRoute(g.getMap().getRoutes().size());
            check(closed == 1, tag + ": lane 1 is closed");
            boolean hitClosed = false, sawOther = false;
            for (int i = 0; i < 300; i++) { int r = g.getMap().pickRoute(g); hitClosed |= r == closed; sawOther |= r != closed; }
            check(!hitClosed && sawOther, tag + ": no enemy enters the closed lane");
            Set<Integer> seen = new HashSet<>();
            for (int i = 0; i < 300; i++) seen.add(b.getMap().pickRoute(b));
            check(seen.size() == b.getMap().getRoutes().size(), tag + ": without the outage every lane is used");
            check(g.getVariance().closedRoute(1) == -1, tag + ": a one-lane map never closes its lane");
            probed.add(Knob.CLOSE_LANE);
        }
        if (m.has(Knob.LIVES_PER_WAVE)) {
            Game g = modded.get();
            int before = g.getLives();
            check(before == g.getMaxLives() && g.startNextWave(), tag + ": full integrity, wave 2 starts");
            finish(g);
            check(g.getLives() == before + (int) m.get(Knob.LIVES_PER_WAVE), tag + ": +" + (int) m.get(Knob.LIVES_PER_WAVE) + " integrity per wave, past the maximum (" + g.getLives() + ")");
            int over = g.getLives();
            check(g.restoreLives(5) == 0 && g.getLives() == over, tag + ": healing never lowers integrity that is above the maximum");
            probed.add(Knob.LIVES_PER_WAVE);
        }
        if (m.has(Knob.LEAK_LIVES)) {
            Game g = modded.get();
            Path r = g.getMap().getRoutes().get(0);
            spawnAt(g, EnemyType.HEAP_SORT, null, 0, r.getTotalLength() - 1);
            int before = g.getLives();
            for (int i = 0; i < 120 && g.getLives() == before; i++) g.step(Game.DT);
            int want = Math.max(1, (int) Math.round(EnemyType.HEAP_SORT.lives * m.get(Knob.LEAK_LIVES)));
            check(before - g.getLives() == want, tag + ": a " + EnemyType.HEAP_SORT.lives + "-life leak costs " + want + " (cost " + (before - g.getLives()) + ")");
            check(g.getVariance().leakLives(1) == 1, tag + ": a leak always costs at least 1");
            probed.add(Knob.LEAK_LIVES);
        }
        if (m.has(Knob.FREE_FIRST_UPGRADE)) {
            Game g = modded.get();
            int price = Shop.priceOf(g, gpt);
            double before = g.getCash();
            Tower t = place(g, gpt);
            check(t.getTier() == 1 && near(before - g.getCash(), price), tag + ": a new GPT arrives at tier 1 for its base price");
            check(Shop.sellValue(g, t) == (int) Math.floor(price * Shop.sellFraction(g)), tag + ": the free upgrade is not refunded on sale");
            g.addCash(100_000, null);
            Tower h = g.placeTower(TowerType.LOBBER_LUIS, buildableNear(g, new Vec(800, 600), 320));
            if (h == null) { g.getHeroCollection().unlock(TowerType.LOBBER_LUIS); h = g.placeTower(TowerType.LOBBER_LUIS, buildableNear(g, new Vec(800, 600), 320)); }
            check(h != null && h.getTier() == 0, tag + ": heroes do not get the free upgrade");
            probed.add(Knob.FREE_FIRST_UPGRADE);
        }
    }

    private static void everyKnobProbed() {
        Set<Knob> used = EnumSet.noneOf(Knob.class);
        for (PatchNote p : PatchNote.values()) for (Knob k : Knob.values()) if (p.mods().has(k)) used.add(k);
        for (BreakingNews n : BreakingNews.values()) for (Knob k : Knob.values()) if (n.mods().has(k)) used.add(k);
        for (Knob k : used) check(probed.contains(k), "knob " + k + " is used by a card or event and was probed in the real game");
    }

    // ------------------------------------------------------------------ draft schedule
    private static void draftSchedule() {
        Game g = new Game(MapCatalog.create(0), 42, Difficulty.O1);
        RunVariance v = g.getVariance();
        v.enable();
        int drafts = 0;
        for (int w = 1; w <= 99; w++) {
            boolean due = RunVariance.draftIndex(w) >= 0;
            check(v.isDraftPending() == due, "draft open before wave " + w + " iff it is a draft wave (" + due + ")");
            if (due) {
                check(!g.getWaveManager().canStartNextWave() && !g.startNextWave(), "wave " + w + " waits for the pick");
                List<PatchNote> offer = v.getOffer();
                check(offer.size() == RunVariance.OFFER_SIZE && new HashSet<>(offer).size() == offer.size(), "three different cards on offer before wave " + w);
                for (PatchNote p : offer) check(!v.getActive().contains(p), p + " not offered again once taken");
                check(v.getOfferWave() == w && v.getDraftNumber() == drafts + 1, "draft " + (drafts + 1) + " precedes wave " + w);
                check(!v.pick(7) && v.isDraftPending(), "an out-of-range pick is refused");
                check(v.pick(w % offer.size()), "pick accepted");
                drafts++;
            }
            check(playThrough(g), "wave " + w + " starts after the draft");
        }
        check(drafts == 5 && v.getActive().size() == 5 && new HashSet<>(v.getActive()).size() == 5, "five drafts on waves 1/20/40/60/80, five different cards");
        for (int i = 0; i < 5; i++) check(v.getPickedBefore(i) == RunVariance.DRAFT_WAVES[i], "card " + i + " recorded its draft wave");
        check("1.5".equals(v.getVersion()), "patch version 1.5 after five picks");
        // the draft opens as soon as wave 19 is cleared (the UI shows it before the player presses START)
        Game h = new Game(MapCatalog.create(0), 43, Difficulty.O1);
        h.getVariance().enable(RunVariance.Picker.FIRST);
        h.getVariance().setPicker(RunVariance.Picker.PLAYER);
        for (int w = 1; w <= 18; w++) playThrough(h);
        check(!h.getVariance().isDraftPending() && h.startNextWave(), "wave 19 starts");
        finish(h);
        check(h.getVariance().isDraftPending() && h.getVariance().getOfferWave() == 20, "clearing wave 19 opens the wave-20 draft");
        // auto-start waits too
        h.getWaveManager().setAutoStart(true);
        h.run(60 * 20);
        check(h.getWave() == 19, "auto-start never skips a pending draft");
        h.getVariance().pick(0);
        h.run((int) (60 * (lindefense.wave.WaveManager.PREP_TIME + 1)));
        check(h.getWave() == 20, "auto-start resumes after the pick");
    }

    private static void autoPickers() {
        long seed = 99;
        Game f = new Game(MapCatalog.create(0), seed, Difficulty.O1);
        f.getVariance().enable(RunVariance.Picker.FIRST);
        PatchNote expect = RunVariance.offerFor(seed, 1, new ArrayList<PatchNote>()).get(0);
        check(!f.getVariance().isDraftPending() && f.getVariance().getActive().size() == 1 && f.getVariance().getActive().get(0) == expect,
            "FIRST takes the first offered card at once");
        check(f.startNextWave(), "tools never wait for a draft");
        List<PatchNote> a = randomRun(seed), b = randomRun(seed);
        check(a.equals(b) && a.size() == 5, "RANDOM picks are seeded: " + a);
        Game p = new Game(MapCatalog.create(0), seed, Difficulty.O1);
        p.getVariance().enable();
        check(p.getVariance().isDraftPending(), "PLAYER waits");
        p.getVariance().setPicker(RunVariance.Picker.FIRST);
        check(!p.getVariance().isDraftPending() && p.getVariance().getActive().get(0) == expect, "switching to an automatic picker answers the pending draft");
    }

    private static List<PatchNote> randomRun(long seed) {
        Game g = new Game(MapCatalog.create(0), seed, Difficulty.O1);
        g.getVariance().enable(RunVariance.Picker.RANDOM);
        for (int w = 1; w <= 99; w++) playThrough(g);
        return new ArrayList<>(g.getVariance().getActive());
    }

    // ------------------------------------------------------------------ news
    private static void newsRate() {
        int rolls = 0, hits = 0, early = 0, badLane = 0, unstable = 0;
        EnumSet<BreakingNews> seen = EnumSet.noneOf(BreakingNews.class);
        for (long seed = 0; seed < 400; seed++) {
            for (int w = 1; w <= WaveData.WAVE_COUNT; w++) {
                BreakingNews.Roll r = BreakingNews.roll(seed, w, false, 2);
                if (w < RunVariance.NEWS_FIRST_WAVE || w >= WaveData.WAVE_COUNT) {
                    if (r != null) early++;
                    continue;
                }
                rolls++;
                if (r == null) continue;
                hits++;
                seen.add(r.news);
                if (w < r.news.minWave) early++;
                if (r.news == BreakingNews.SERVER_OUTAGE && (r.lane < 0 || r.lane >= 2)) badLane++;
                BreakingNews.Roll again = BreakingNews.roll(seed, w, false, 2);
                if (again == null || again.news != r.news || again.lane != r.lane) unstable++;
            }
        }
        check(early == 0, "no event before its first wave (" + early + ")");
        check(badLane == 0, "an outage always closes a real lane (" + badLane + ")");
        check(unstable == 0, "a roll is deterministic in (seed, wave) (" + unstable + " differ)");
        double rate = hits / (double) rolls;
        check(Math.abs(rate - RunVariance.NEWS_CHANCE) < 0.01, "news rate " + rate + " ~ " + RunVariance.NEWS_CHANCE + " over " + rolls + " waves");
        check(seen.size() == BreakingNews.values().length, "every event appears (" + seen.size() + ")");
        // boss waves get only the harmless events; one-lane maps never close a lane
        int bossBad = 0, bossNews = 0;
        for (long seed = 0; seed < 300; seed++) {
            BreakingNews.Roll r = BreakingNews.roll(seed, 50, true, 1);
            if (r == null) continue;
            bossNews++;
            if (!r.news.onBossWaves || r.news == BreakingNews.SERVER_OUTAGE) bossBad++;
        }
        check(bossNews > 30 && bossBad == 0, "boss waves on a one-lane map only get harmless events (" + bossBad + " of " + bossNews + " not)");
    }

    private static void newsLifetime() {
        int announced = 0;
        for (long seed = 1; seed <= 4; seed++) {
            Game g = new Game(MapCatalog.create(0), seed, Difficulty.O1);
            RunVariance v = g.getVariance();
            v.enable(RunVariance.Picker.FIRST);
            int bad = 0;
            for (int w = 1; w <= 99; w++) {
                if (!(v.getNews() == null || v.getNewsWave() == w)) bad++;          // before wave w: only its own news is announced
                BreakingNews pre = v.getNews();
                if (!g.startNextWave()) { bad++; break; }
                if (v.getNews() != pre) bad++;                                        // the news stays for its wave
                if (pre != null) announced++;
                finish(g);
                if (!(v.getNews() == null || v.getNewsWave() == w + 1)) bad++;      // after wave w: its news expired
            }
            check(bad == 0, "news is announced before its wave, lasts that wave and expires after it (seed " + seed + ", " + bad + " violations)");
            check(v.getNewsLog().size() == countAnnounced(seed, g), "the log lists every headline (seed " + seed + ")");
        }
        check(announced > 40, "news happened during the runs (" + announced + ")");
        // stale news (a wave ended without completion) is dropped when the next wave starts
        Game g = clean(0);
        g.getVariance().forceNews(BreakingNews.DDOS, -1);
        check(g.startNextWave() && g.getVariance().getNews() == BreakingNews.DDOS, "DDoS live on its wave");
        g.getEnemyManager().clear();
        g.getWaveManager().endWave();
        check(g.startNextWave() && g.getVariance().getNews() == null, "stale news is dropped on the next wave");
    }

    private static int countAnnounced(long seed, Game g) {
        int n = 0;
        for (int w = 1; w <= 99; w++) {
            boolean boss = g.getDifficulty().shape(WaveData.get(w), seed).containsBoss();
            if (BreakingNews.roll(seed, w, boss, g.getMap().getRoutes().size()) != null) n++;
        }
        return n;
    }

    // ------------------------------------------------------------------ determinism
    private static void determinism() {
        String a = transcript(7, 0, false), b = transcript(7, 0, false), noisy = transcript(7, 0, true), other = transcript(8, 0, false);
        check(a.equals(b), "same seed, same picks: same offers, cards and news");
        check(a.equals(noisy), "offers and news do not depend on the combat RNG");
        check(!a.equals(other), "another seed deals another run");
        // a full simulated stretch with variance on is reproducible from the seed
        check(simulate(2024).equals(simulate(2024)), "a simulated run with variance on is reproducible: " + simulate(2024));
    }

    private static String transcript(long seed, int map, boolean noise) {
        Game g = new Game(MapCatalog.create(map), seed, Difficulty.ON2);
        g.getVariance().enable(RunVariance.Picker.RANDOM);
        StringBuilder offers = new StringBuilder();
        for (int w = 1; w <= 99; w++) {
            if (noise) for (int i = 0; i < 137; i++) g.getRng().next();
            playThrough(g);
        }
        for (int i = 0; i < 5; i++) offers.append(RunVariance.offerFor(seed, RunVariance.DRAFT_WAVES[i], g.getVariance().getActive().subList(0, i)));
        return g.getVariance().getActive() + "|" + g.getVariance().getNewsLog() + "|" + offers;
    }

    private static String simulate(long seed) {
        Game g = new Game(MapCatalog.create(0), seed, Difficulty.ON);
        g.getVariance().enable(RunVariance.Picker.RANDOM);
        g.setInvincible(true);
        g.addCash(20_000, null);
        Vec[] spots = { new Vec(380, 300), new Vec(700, 250), new Vec(460, 520), new Vec(820, 660) };
        TowerType[] types = { TowerType.GPT, TowerType.CLAUDE, TowerType.PERPLEXITY, TowerType.DEEPSEEK };
        for (int i = 0; i < spots.length; i++) g.placeTower(types[i], buildableNear(g, spots[i], 200));
        g.getWaveManager().setAutoStart(true);
        g.startNextWave();
        g.run(60 * 240);
        return "wave " + g.getWave() + " cash " + (long) g.getCash() + " lives " + g.getLives() + " killed " + g.getEnemyManager().getTotalKilled()
            + " cards " + g.getVariance().getActive() + " news " + g.getVariance().getNewsLog().size();
    }

    // ------------------------------------------------------------------ refunds
    private static void refundsWhatWasPaid() {
        Game g = clean(0);
        g.addCash(10_000, null);
        Tower t = place(g, TowerType.GPT);
        g.getVariance().forceNews(BreakingNews.GPU_SHORTAGE, -1);
        int surcharge = Shop.upgradeCost(g, t);
        check(surcharge == round5(t.nextUpgrade().cost, 1.25) && g.upgradeTower(t), "GPU shortage: upgrade at +25%");
        int paid = TowerCatalog.get(TowerType.GPT).baseCost + surcharge;
        check(g.getVariance().unpaidOn(t) == t.getInvestedCost() - paid, "the surcharge is recorded");
        check(Shop.sellValue(g, t) == (int) Math.floor(paid * Shop.SELL_FRACTION), "selling refunds 70% of what was paid, surcharge included");
        // Open Source bought after a list-price purchase: the earlier tower still refunds on what it cost
        Game h = clean(0);
        Tower early = place(h, TowerType.GPT);
        h.getVariance().grant(PatchNote.OPEN_SOURCE);
        check(Shop.sellValue(h, early) == (int) Math.floor(TowerCatalog.get(TowerType.GPT).baseCost * (Shop.SELL_FRACTION - 0.20)),
            "Open Source refunds 50% of the list price actually paid before it");
        int refund = h.sellTower(early);
        check(refund > 0 && h.getVariance().unpaidOn(early) == 0, "a sold tower is forgotten");
        // variance off: the old 70% rule exactly
        Game off = new Game(MapCatalog.create(0), 42, Difficulty.O1);
        off.addCash(10_000, null);
        Tower o = place(off, TowerType.GPT);
        off.upgradeTower(o);
        check(Shop.sellValue(off, o) == Shop.sellValue(o), "variance off: the refund is the classic 70% of the invested cost");
    }

    // ------------------------------------------------------------------ seeds
    private static void seedsAndRestart() {
        java.util.Random r = new java.util.Random(5);
        for (int i = 0; i < 200; i++) {
            long s = i == 0 ? Long.MIN_VALUE : i == 1 ? Long.MAX_VALUE : r.nextLong();
            check(Long.valueOf(s).equals(RunSeed.parse(RunSeed.format(s))), "seed code round trip " + s);
        }
        check(RunSeed.format(1234) .equals("YA") && RunSeed.parse(" ya ") == 1234 && RunSeed.parse("not a seed!") == null, "seed codes are base 36");
        String old = System.getProperty(RunSeed.PROPERTY);
        try {
            System.clearProperty(RunSeed.PROPERTY);
            for (int i = 0; i < 50; i++) { long s = RunSeed.next(); check(s >= 0 && s < RunSeed.SPACE && RunSeed.format(s).length() <= 6, "fresh seed is a short code"); }
            System.setProperty(RunSeed.PROPERTY, "K3X9QZ");
            check(RunSeed.next() == RunSeed.parse("K3X9QZ"), "-Dlindefense.seed forces the seed");
        } finally {
            if (old == null) System.clearProperty(RunSeed.PROPERTY); else System.setProperty(RunSeed.PROPERTY, old);
        }
        Game g = new Game(MapCatalog.create(1), 777, Difficulty.ON);
        g.getVariance().enable();
        List<PatchNote> first = g.getVariance().getOffer();
        Game replay = Game.freshCopy(g, g.getSeed());
        check(replay.getSeed() == 777 && replay.getVariance().isEnabled() && replay.getVariance().getOffer().equals(first), "REPLAY SEED deals the same first offer");
        Game restart = Game.freshCopy(g);
        check(restart.getVariance().isEnabled() && restart.getVariance().isDraftPending(), "RESTART keeps variance on (new seed, fresh draft)");
    }
}
