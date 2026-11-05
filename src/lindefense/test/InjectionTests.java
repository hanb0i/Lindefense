package lindefense.test;

import static lindefense.test.TestKit.check;
import static lindefense.test.TestKit.forcePlace;
import static lindefense.test.TestKit.newGame;
import static lindefense.test.TestKit.run;
import static lindefense.test.TestKit.runSeconds;
import static lindefense.test.TestKit.spawnAt;

import java.awt.Dimension;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.PalantirProtocols;
import lindefense.enemy.StatusEffect;
import lindefense.map.Path;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.sim.PromptInjection;
import lindefense.sim.Vec;
import lindefense.sim.WindowLink;
import lindefense.tower.Intrusion;
import lindefense.tower.Targeting;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.ui.WindowGrab;
import lindefense.wave.InjectionSchedule;
import lindefense.wave.SpawnGroup;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Prompt injection and Palantir's phase abilities: the INJECTION modifier and its wave schedule, hijacked towers and
 * their zaps, immunity (each immune tower and the Copilot firewall), bounded disable chains, Panopticon, Prompt
 * Broadcast, the holographic decoys, the kill switch and the window seal, which the simulation sees only as the window
 * fraction the UI reports. No window is ever touched: the window-grab geometry is tested through its pure helpers.
 */
public final class InjectionTests {
    private InjectionTests() { }

    private static final TowerType[] IMMUNE = { TowerType.CLAUDE, TowerType.COPILOT, TowerType.DEEPSEEK, TowerType.PERPLEXITY, TowerType.MR_LINDEMANN };

    /** Runs every prompt-injection / Palantir-ability / window-seal test (registered in {@link HeadlessTests}). */
    public static void runAll() {
        run("inj.immunityIsDataDriven", InjectionTests::immunityIsDataDriven);
        run("inj.modifierNotInherited", InjectionTests::modifierNotInherited);
        run("inj.injectorHijacksNearest", InjectionTests::injectorHijacksNearest);
        run("inj.hijackedTowerZapsNeighbours", InjectionTests::hijackedTowerZapsNeighbours);
        run("inj.eachImmuneTowerResists", InjectionTests::eachImmuneTowerResists);
        run("inj.copilotFirewall", InjectionTests::copilotFirewall);
        run("inj.boundedChainsNoLockout", InjectionTests::boundedChainsNoLockout);
        run("inj.counterplay", InjectionTests::counterplay);
        run("inj.waveSchedule", InjectionTests::waveSchedule);
        run("inj.palantirPanopticon", InjectionTests::palantirPanopticon);
        run("inj.palantirPromptBroadcast", InjectionTests::palantirPromptBroadcast);
        run("inj.palantirDecoys", InjectionTests::palantirDecoys);
        run("inj.palantirKillSwitch", InjectionTests::palantirKillSwitch);
        run("inj.windowSeal", InjectionTests::windowSeal);
        run("inj.windowSealNeverInHeadless", InjectionTests::windowSealNeverInHeadless);
        run("inj.windowGrabGeometry", InjectionTests::windowGrabGeometry);
    }

    // ------------------------------------------------------------------ helpers
    private static Game frozen() {
        Game g = newGame(0);
        g.setGlobalEnemySpeedMultiplier(0);
        g.setHeroLimit(Integer.MAX_VALUE);
        return g;
    }

    private static Vec track(Game g, double d) { return g.getMap().getRoutes().get(0).positionAt(d); }

    /** A buildable spot for a tower near {@code target} (excluding spots overlapping existing towers). */
    private static Tower place(Game g, TowerType t, Vec target, int tier) {
        return forcePlace(g, t, TestKit.buildableNear(g, target, 160), tier);
    }

    /** The buildable spot nearest {@code center} whose distance from it lies in [dmin, dmax], or null. */
    private static Vec spotAtDistance(Game g, Vec center, double dmin, double dmax, TowerType type) {
        Vec best = null;
        double bestD = Double.MAX_VALUE;
        for (int x = 25; x < 1180; x += 5) for (int y = 25; y < 880; y += 5) {
            Vec p = new Vec(x, y);
            double d = p.dist(center);
            if (d < dmin || d > dmax || !g.getMap().isBuildable(p, 20)) continue;
            String why = g.getTowerManager().placementProblem(type, p);
            if (why != null && !"Not enough cash".equals(why)) continue;
            if (d < bestD) { bestD = d; best = p; }
        }
        return best;
    }

    /** An injector too tough for the test towers to kill (so it keeps broadcasting). */
    private static Enemy injector(Game g, EnemyType t, double d) {
        Enemy e = g.getEnemyManager().spawnScaled(t, EnumSet.of(Modifier.INJECTION), 0, d, 1e5, 1.0);
        g.getEnemyManager().update(0);
        return e;
    }

    /** A Palantir on route 0 at {@code d}, already announced. */
    private static Boss palantir(Game g, double d) { return (Boss) spawnAt(g, EnemyType.PALANTIR, null, 0, d); }

    /** Deals TRUE damage until Palantir sits at {@code fraction} of its max HP, then runs one step. */
    private static void hpTo(Game g, Boss pal, double fraction) {
        double dmg = pal.getHp() - pal.getMaxHp() * fraction;
        if (dmg > 0) g.getCombat().applyHit(pal, new HitSpec(dmg, DamageType.TRUE), null, 1, 0);
        g.run(1);
    }

    // ------------------------------------------------------------------ immunity data
    private static void immunityIsDataDriven() {
        List<TowerType> immune = new ArrayList<>();
        for (TowerType t : TowerType.values()) {
            if (TowerCatalog.get(t) == null || !t.isPurchasable()) continue;
            if (TowerCatalog.isInjectionImmune(t)) immune.add(t);
            for (int i = 0; i <= TowerCatalog.get(t).upgrades.length; i++)
                check(TowerCatalog.get(t).statsForTier(i).injectionImmune == TowerCatalog.isInjectionImmune(t), t + " immunity is the same at tier " + i);
            check(TowerCatalog.grantsInjectionFirewall(t) == (t == TowerType.COPILOT), t + (t == TowerType.COPILOT ? " grants" : " does not grant") + " the injection firewall");
        }
        check(immune.size() == IMMUNE.length, "exactly five tower types are immune to prompt injection, got " + immune);
        for (TowerType t : IMMUNE) {
            check(immune.contains(t), t + " is immune to prompt injection");
            String why = TowerCatalog.injectionImmunityReason(t);
            check(why != null && why.length() > 10, t + " says why it is immune");
        }
        check(TowerCatalog.injectionImmunityReason(TowerType.GPT) == null, "GPT has no immunity reason");
        check(immune.contains(TowerType.MR_LINDEMANN) && !immune.contains(TowerType.LOBBER_LUIS), "the CS-teacher hero is immune, other heroes are not");
        check(lindefense.ui.IntrusionText.typeLine(TowerType.CLAUDE).startsWith(lindefense.ui.IntrusionText.IMMUNE), "the panel / catalog line reads IMMUNE TO PROMPT INJECTION");
        check(lindefense.ui.IntrusionText.typeLine(TowerType.GPT) == null, "no immunity line for GPT");
    }

    private static void modifierNotInherited() {
        Game g = frozen();
        Enemy tim = injector(g, EnemyType.TIMSORT, 300);
        check(tim.has(Modifier.INJECTION), "the injector carries the modifier");
        TestKit.killOutright(g, tim);
        int kids = 0;
        for (Enemy e : g.getEnemyManager().getEnemies()) { kids++; check(!e.has(Modifier.INJECTION), "children never inherit Prompt Injection (" + e.getType() + ")"); }
        check(kids == 2, "the TimSort still splits (" + kids + ")");
        // elites never roll it: the O(N^N) shaping of a pre-injection wave has none
        for (int w = 1; w < InjectionSchedule.FIRST_WAVE; w++) {
            for (SpawnGroup s : Difficulty.ONN.shape(WaveData.get(w), 42).groups) check(!s.modifiers.contains(Modifier.INJECTION), "no elite rolls Prompt Injection on wave " + w);
        }
    }

    // ------------------------------------------------------------------ hijack
    private static void injectorHijacksNearest() {
        Game g = frozen();
        Vec at = track(g, 450);
        Tower a = place(g, TowerType.GPT, at.add(new Vec(0, -60)), 0);
        Tower b = place(g, TowerType.GEMINI, at.add(new Vec(50, 60)), 0);
        Tower c = place(g, TowerType.SORA, at.add(new Vec(-60, 70)), 0);
        Tower far = forcePlace(g, TowerType.GROK, spotAtDistance(g, at, PromptInjection.RADIUS + 60, 900, TowerType.GROK), 0);
        Enemy inj = injector(g, EnemyType.HEAP_SORT, 450);
        List<Tower> inReach = new ArrayList<>();
        for (Tower t : new Tower[] { a, b, c }) if (t.getPosition().dist(inj.getPosition()) <= PromptInjection.RADIUS) inReach.add(t);
        inReach.sort((x, y) -> Double.compare(x.getPosition().distSq(inj.getPosition()), y.getPosition().distSq(inj.getPosition())));
        check(inReach.size() >= 2, "at least two towers stand in reach of the injector (" + inReach.size() + ")");
        check(far.getPosition().dist(inj.getPosition()) > PromptInjection.RADIUS, "the far tower is out of reach");
        g.run(1);
        check(g.getInjection().getBroadcasts() == 1, "the injector broadcasts as soon as a tower is in reach");
        int hijacked = 0;
        for (Tower t : new Tower[] { a, b, c }) if (t.isHijacked()) hijacked++;
        check(hijacked == Math.min(PromptInjection.MAX_TARGETS, inReach.size()), "a broadcast hijacks the " + PromptInjection.MAX_TARGETS + " nearest towers (" + hijacked + ")");
        for (int i = 0; i < Math.min(PromptInjection.MAX_TARGETS, inReach.size()); i++) {
            check(inReach.get(i).isHijacked(), "near tower " + i + " is hijacked");
            check(inReach.get(i).getIntrusion().getHijacker() == inj, "the hijacker is remembered for the beam");
        }
        check(!far.isHijacked() && !far.isOffline(), "a tower out of reach is untouched");
        check(Math.abs(inReach.get(0).getIntrusion().getRemaining() - (PromptInjection.HIJACK_TIME - Game.DT)) < 1e-6, "a hijack lasts " + PromptInjection.HIJACK_TIME + " s");
        check(!inReach.get(0).isAbilityReady() || inReach.get(0).getAbility() == null, "a hijacked tower cannot use an ability");
        // the next broadcast waits for the interval
        runSeconds(g, PromptInjection.INTERVAL - 0.5);
        check(g.getInjection().getBroadcasts() == 1, "no second broadcast before " + PromptInjection.INTERVAL + " s");
        runSeconds(g, 1.0);
        check(g.getInjection().getBroadcasts() == 2, "the injector broadcasts again after the interval");
    }

    private static void hijackedTowerZapsNeighbours() {
        Game g = frozen();
        Vec at = track(g, 500);
        Tower a = place(g, TowerType.GPT, at.add(new Vec(0, -70)), 1);
        Tower b = place(g, TowerType.GEMINI, a.getPosition().add(new Vec(55, 0)), 1);
        check(a.getPosition().dist(b.getPosition()) <= PromptInjection.ZAP_RANGE, "the neighbour is within zap range");
        Enemy dummy = g.getEnemyManager().spawnScaled(EnemyType.HEAP_SORT, null, 0, 500, 1e6, 1.0);
        g.getEnemyManager().update(0);
        Object source = new Object();
        check(g.getInjection().hijack(a, source, PromptInjection.HIJACK_TIME), "hijack accepted");
        double aDmg = a.getDamageDealt();
        runSeconds(g, PromptInjection.FIRST_ZAP - 0.1);
        check(!b.isOffline(), "no zap before " + PromptInjection.FIRST_ZAP + " s");
        runSeconds(g, 0.2);
        check(b.getIntrusion().isDisabled() && b.getIntrusion().getDisabledBy() == a, "the hijacked tower zaps and disables its neighbour");
        check(!b.isHijacked(), "a zapped neighbour is disabled, never hijacked (chains stay one hop)");
        check(a.getIntrusion().getLastVictim() == b, "the zap beam knows its victim");
        double bDmg = b.getDamageDealt();
        runSeconds(g, PromptInjection.DISABLE_TIME - 0.3);
        check(b.getDamageDealt() == bDmg, "a disabled tower does not attack");
        runSeconds(g, PromptInjection.HIJACK_TIME - (PromptInjection.FIRST_ZAP + 0.1 + PromptInjection.DISABLE_TIME - 0.3) - 0.1);
        check(a.isHijacked() && a.getDamageDealt() == aDmg, "a hijacked tower never attacks enemies (enemy in range all along)");
        runSeconds(g, 0.2);
        check(!a.isOffline() && a.getIntrusion().isPatched(), "the hijack ends and the tower is patched");
        check(g.getInjection().getZaps() == PromptInjection.ZAPS_PER_HIJACK, PromptInjection.ZAPS_PER_HIJACK + " zaps per hijack (" + g.getInjection().getZaps() + ")");
        check(!g.getInjection().hijack(a, source, 3), "a patched tower cannot be hijacked again at once");
        runSeconds(g, 1.5);
        check(a.getDamageDealt() > aDmg, "the freed tower attacks enemies again");
        check(dummy.isAlive(), "the dummy is still there");
    }

    private static void eachImmuneTowerResists() {
        for (TowerType type : IMMUNE) {
            Game g = frozen();
            Vec at = track(g, 450);
            Tower t = place(g, type, at.add(new Vec(0, -60)), 0);
            check(t.isInjectionImmune(), type + " reports immunity");
            Tower victim = place(g, TowerType.GPT, t.getPosition().add(new Vec(0, -60)), 0);
            for (int i = 0; i < 3; i++) injector(g, EnemyType.HEAP_SORT, 420 + i * 30);
            boolean everOffline = false;
            for (int i = 0; i < (int) (20 / Game.DT); i++) {
                g.step(Game.DT);
                if (t.isOffline()) everOffline = true;
            }
            check(!everOffline, type + " is never hijacked, disabled or blinded by injectors");
            check(g.getInjection().getBlocks() > 0, type + " shows BLOCKED when an injector tries");
            check(!g.getInjection().hijack(t, new Object(), 3), type + " refuses a direct hijack");
            // a hijacked neighbour cannot disable it either
            Game g2 = frozen();
            Tower t2 = place(g2, type, track(g2, 450).add(new Vec(0, -60)), 0);
            // the zapper must stand outside Copilot's firewall (which would protect it) but within zap range
            Vec hp = type == TowerType.COPILOT
                ? spotAtDistance(g2, t2.getPosition(), t2.getStats().auraRange + 5, PromptInjection.ZAP_RANGE - 2, TowerType.GPT)
                : TestKit.buildableNear(g2, t2.getPosition().add(new Vec(55, 0)), 80);
            check(hp != null, "a spot for the zapper beside " + type);
            if (hp == null) continue;
            Tower h = forcePlace(g2, TowerType.GPT, hp, 0);
            g2.getTowerManager().recomputeAuras();
            check(g2.getInjection().hijack(h, new Object(), PromptInjection.HIJACK_TIME), "hijack the neighbour of " + type);
            runSeconds(g2, PromptInjection.HIJACK_TIME + 0.2);
            check(!t2.isOffline() && t2.getIntrusion().getTotalOfflineTime() == 0, "a hijacked neighbour's zaps never disable " + type);
            check(victim.isAlive(), "the GPT beside " + type + " exists");
        }
    }

    private static void copilotFirewall() {
        Game g = frozen();
        Vec at = track(g, 450);
        Tower cop = place(g, TowerType.COPILOT, at.add(new Vec(0, -60)), 0);
        Tower inside = forcePlace(g, TowerType.GPT, TestKit.buildableNear(g, cop.getPosition().add(new Vec(60, 0)), 50), 0);
        Tower outside = place(g, TowerType.GEMINI, at.add(new Vec(0, 300)), 0);
        g.getTowerManager().recomputeAuras();
        double range = cop.getStats().auraRange;
        check(inside.getPosition().dist(cop.getPosition()) <= range, "the GPT stands in the Copilot tether");
        check(outside.getPosition().dist(cop.getPosition()) > range, "the Gemini stands outside it");
        check(inside.isInjectionImmune() && inside.getIntrusion().isFirewalled(), "the firewall makes a tower in the tether immune");
        check(!outside.isInjectionImmune(), "a tower outside the tether is not protected");
        check(!g.getInjection().hijack(inside, new Object(), 3), "a firewalled tower refuses a hijack");
        check(g.getInjection().hijack(outside, new Object(), 3), "an unprotected tower can be hijacked");
        check(lindefense.ui.IntrusionText.towerLine(outside).startsWith("HIJACKED"), "the panel shows HIJACKED");
        check(lindefense.ui.IntrusionText.towerLine(inside).contains("Copilot firewall"), "the panel credits the Copilot firewall");
        check(lindefense.ui.IntrusionText.towerLine(cop).startsWith(lindefense.ui.IntrusionText.IMMUNE), "the panel shows Copilot's own immunity");
        // injectors walking past the firewalled GPT never take it offline
        injector(g, EnemyType.HEAP_SORT, 450);
        boolean off = false;
        for (int i = 0; i < (int) (12 / Game.DT); i++) { g.step(Game.DT); if (inside.isOffline()) off = true; }
        check(!off, "the firewalled GPT never goes offline");
        // selling the Copilot drops the firewall
        g.sellTower(cop);
        g.getTowerManager().recomputeAuras();
        check(!inside.isInjectionImmune(), "the firewall is gone once the Copilot is sold");
    }

    private static void boundedChainsNoLockout() {
        Game g = frozen();
        Path r = g.getMap().getRoutes().get(0);
        List<Tower> towers = new ArrayList<>();
        TowerType[] types = { TowerType.GPT, TowerType.GEMINI, TowerType.SORA, TowerType.GROK, TowerType.SUNO, TowerType.KIMI, TowerType.GLM, TowerType.MINIMAX, TowerType.COHERE, TowerType.QWEN };
        for (int i = 0; i < types.length; i++) {
            Vec p = r.positionAt(380 + (i / 2) * 45).add(new Vec(0, i % 2 == 0 ? -65 : 65));
            towers.add(place(g, types[i], p, 1));
        }
        injector(g, EnemyType.HEAP_SORT, 390);
        injector(g, EnemyType.HEAP_SORT, 560);
        Map<Tower, Double> run = new HashMap<>(), maxRun = new HashMap<>(), lastEnd = new HashMap<>(), minGap = new HashMap<>();
        for (Tower t : towers) { run.put(t, 0.0); maxRun.put(t, 0.0); minGap.put(t, 1e9); }
        int hijackFromZap = 0;
        double time = 0;
        for (int i = 0; i < (int) (45 / Game.DT); i++) {
            Map<Tower, Boolean> wasDisabled = new HashMap<>();
            for (Tower t : towers) wasDisabled.put(t, t.getIntrusion().isDisabled());
            g.step(Game.DT);
            time += Game.DT;
            for (Tower t : towers) {
                if (wasDisabled.get(t) && t.isHijacked()) hijackFromZap++;
                if (t.isOffline()) {
                    if (run.get(t) == 0 && lastEnd.containsKey(t)) minGap.put(t, Math.min(minGap.get(t), time - lastEnd.get(t)));
                    run.put(t, run.get(t) + Game.DT);
                    maxRun.put(t, Math.max(maxRun.get(t), run.get(t)));
                } else if (run.get(t) > 0) {
                    run.put(t, 0.0);
                    lastEnd.put(t, time);
                }
            }
        }
        double longest = Math.max(PromptInjection.HIJACK_TIME, PromptInjection.DISABLE_TIME) + 2 * Game.DT;
        PromptInjection inj = g.getInjection();
        check(inj.getHijacks() > 0 && inj.getDisables() > 0, "the dense cluster sees hijacks (" + inj.getHijacks() + ") and zaps (" + inj.getDisables() + ")");
        for (Tower t : towers) {
            check(maxRun.get(t) <= longest, t + " never stays offline longer than one intrusion (" + maxRun.get(t) + " s)");
            check(minGap.get(t) >= Intrusion.GRACE - 2 * Game.DT, t + " always gets the patch window between intrusions (" + minGap.get(t) + " s)");
        }
        check(hijackFromZap == 0, "a disabled tower never turns into a hijacked one (chains are one hop)");
        check(inj.getHijacks() <= inj.getBroadcasts() * PromptInjection.MAX_TARGETS, "hijacks per broadcast are capped");
        check(inj.getDisables() <= inj.getHijacks() * PromptInjection.ZAPS_PER_HIJACK, "disables per hijack are capped");
        // the injectors go away: everything is back online and stays online
        for (Enemy e : new ArrayList<>(g.getEnemyManager().getEnemies())) TestKit.killOutright(g, e);
        for (Enemy e : new ArrayList<>(g.getEnemyManager().getEnemies())) TestKit.killOutright(g, e);
        for (Enemy e : new ArrayList<>(g.getEnemyManager().getEnemies())) TestKit.killOutright(g, e);
        runSeconds(g, PromptInjection.HIJACK_TIME + 0.1);
        boolean any = false;
        for (Tower t : towers) if (t.isOffline()) any = true;
        check(!any, "no permanent lockout: every tower is back online once the injectors are gone");
    }

    private static void counterplay() {
        Game g = frozen();
        Vec at = track(g, 450);
        Tower t = place(g, TowerType.GPT, at.add(new Vec(0, -60)), 0);
        Enemy inj = injector(g, EnemyType.HEAP_SORT, 450);
        inj.applyStatus(StatusEffect.Kind.STUN, 1, 2);
        g.run(30);
        check(g.getInjection().getBroadcasts() == 0 && !t.isOffline(), "a stunned injector cannot broadcast");
        inj.clearStatus(StatusEffect.Kind.STUN);
        inj.applyStatus(StatusEffect.Kind.DISRUPTED, 1, 2);
        g.run(30);
        check(g.getInjection().getBroadcasts() == 0, "a Disrupted injector cannot broadcast");
        inj.clearStatus(StatusEffect.Kind.DISRUPTED);
        g.run(1);
        check(t.isHijacked(), "once free it broadcasts and hijacks");
        check(g.upgradeTower(t) && !t.isOffline() && t.getIntrusion().isPatched(), "upgrading a hijacked tower patches it");
    }

    // ------------------------------------------------------------------ waves
    private static int injectors(WaveDef w) {
        int n = 0;
        for (SpawnGroup s : w.groups) if (s.modifiers.contains(Modifier.INJECTION)) n += s.count;
        return n;
    }

    private static void waveSchedule() {
        int band30 = 0, band50 = 0, band70 = 0, waves30 = 0, waves50 = 0, waves70 = 0;
        for (WaveDef w : WaveData.all()) {
            int n = injectors(w);
            boolean carrier = false;   // a wave of bosses only (95) has nobody to carry the sign
            for (SpawnGroup s : w.groups) if (!s.type.isBoss()) carrier = true;
            check(n == InjectionSchedule.injectors(w.number) || n == 0 && !carrier, "wave " + w.number + " has " + InjectionSchedule.injectors(w.number) + " injectors (" + n + ")");
            if (w.number < InjectionSchedule.FIRST_WAVE) check(n == 0, "no injectors before wave " + InjectionSchedule.FIRST_WAVE + " (wave " + w.number + ")");
            if (w.number == WaveData.WAVE_COUNT) check(n == 0, "wave 100 leaves the injecting to Palantir");
            for (SpawnGroup s : w.groups) {
                if (!s.modifiers.contains(Modifier.INJECTION)) continue;
                check(!s.type.isBoss(), "injectors are never bosses (wave " + w.number + ")");
                boolean sibling = false;
                for (SpawnGroup o : w.groups) if (o != s && o.type == s.type) sibling = true;
                check(sibling, "the injector group was split off an existing group (wave " + w.number + ")");
            }
            if (w.number >= 30 && w.number < 50) { band30 += n; if (n > 0) waves30++; }
            else if (w.number >= 50 && w.number < 70) { band50 += n; if (n > 0) waves50++; }
            else if (w.number >= 70 && w.number < 100) { band70 += n; if (n > 0) waves70++; }
        }
        check(injectors(WaveData.get(InjectionSchedule.FIRST_WAVE)) > 0 && WaveData.get(InjectionSchedule.FIRST_WAVE).note.contains("Prompt Injection"), "wave 30 introduces Prompt Injection in its note");
        // boss debuts get the stage to themselves: the constant matches the waves where a boss class first appears
        java.util.Set<EnemyType> seen = java.util.EnumSet.noneOf(EnemyType.class);
        List<Integer> debuts = new ArrayList<>();
        for (WaveDef w : WaveData.all()) {
            boolean debut = false;
            for (SpawnGroup s : w.groups) if (s.type.isBoss() && s.type != EnemyType.PALANTIR && seen.add(s.type)) debut = true;
            if (debut) { debuts.add(w.number); check(injectors(w) == 0, "no injectors on boss debut wave " + w.number); }
        }
        List<Integer> declared = new ArrayList<>();
        for (int d : InjectionSchedule.BOSS_DEBUTS) declared.add(d);
        check(debuts.equals(declared), "BOSS_DEBUTS lists the boss debut waves " + debuts);
        check(waves30 < waves50 && waves50 < waves70, "injection waves get more frequent (" + waves30 + " / " + waves50 + " / " + waves70 + ")");
        check(band30 < band50 && band50 < band70, "and more numerous (" + band30 + " / " + band50 + " / " + band70 + ")");
        // higher Difficulty Growth: more of them
        int[] total = new int[Difficulty.values().length];
        for (Difficulty d : Difficulty.values()) for (int w = 30; w < 100; w++) total[d.ordinal()] += injectors(d.shape(WaveData.get(w), 42));
        check(total[Difficulty.O1.ordinal()] < total[Difficulty.ON.ordinal()] && total[Difficulty.ON.ordinal()] < total[Difficulty.ON2.ordinal()]
            && total[Difficulty.ON.ordinal()] < total[Difficulty.ONN.ordinal()], "more injectors at higher Difficulty Growth (" + java.util.Arrays.toString(total) + ")");
    }

    // ------------------------------------------------------------------ Palantir
    private static void palantirPanopticon() {
        Game g = frozen();
        Boss pal = palantir(g, 500);
        PalantirProtocols pr = pal.getProtocols();
        check(pr != null, "Palantir has its phase protocols");
        Vec p = pal.getPosition();
        Tower near = place(g, TowerType.GPT, p.add(new Vec(0, -150)), 0);
        Tower far = place(g, TowerType.GEMINI, new Vec(p.x + 520 < 1150 ? p.x + 520 : p.x - 520, p.y), 0);
        check(near.getPosition().dist(p) < PalantirProtocols.PANOPTICON_RANGE, "a tower inside the beam's reach");
        boolean farInReach = far.getPosition().dist(p) <= PalantirProtocols.PANOPTICON_RANGE + far.getRadius();
        runSeconds(g, PalantirProtocols.PANOPTICON_DELAY - 0.2);
        check(!pr.isBeamActive(pal) && pr.getBlinds() == 0, "the beam switches on after " + PalantirProtocols.PANOPTICON_DELAY + " s");
        boolean nearBlinded = false, farBlinded = false;
        double dmgWhileBlind = -1;
        for (int i = 0; i < (int) ((PalantirProtocols.PANOPTICON_PERIOD + 0.5) / Game.DT); i++) {
            double before = near.getDamageDealt();
            boolean wasBlind = near.getIntrusion().isBlinded();
            g.step(Game.DT);
            if (near.getIntrusion().isBlinded()) nearBlinded = true;
            if (far.getIntrusion().isBlinded()) farBlinded = true;
            if (wasBlind && near.getIntrusion().isBlinded()) dmgWhileBlind = Math.max(dmgWhileBlind, near.getDamageDealt() - before);
        }
        check(pr.isBeamActive(pal), "the beam sweeps in phase 1");
        check(nearBlinded, "the beam blinds a tower it sweeps within one turn");
        check(dmgWhileBlind <= 0, "a blinded tower does not attack");
        if (!farInReach) check(!farBlinded, "a tower beyond the beam's reach is never blinded");
        // Perplexity U2 (Predictive Analysis) protects its radius
        Game g2 = frozen();
        Boss pal2 = palantir(g2, 500);
        Tower perp = place(g2, TowerType.PERPLEXITY, pal2.getPosition().add(new Vec(0, -150)), 2);
        Tower guarded = forcePlace(g2, TowerType.GPT, TestKit.buildableNear(g2, perp.getPosition().add(new Vec(60, 0)), 60), 0);
        g2.getTowerManager().recomputeAuras();
        check(guarded.isSurveillanceImmune(), "the GPT stands in the Perplexity U2 radius");
        boolean hit = false;
        for (int i = 0; i < (int) ((PalantirProtocols.PANOPTICON_DELAY + 2 * PalantirProtocols.PANOPTICON_PERIOD) / Game.DT); i++) {
            g2.step(Game.DT);
            if (guarded.isOffline() || perp.isOffline()) hit = true;
        }
        check(!hit, "Perplexity's Predictive Analysis radius blocks the Panopticon");
        check(PalantirProtocols.inBeam(pal2.getPosition(), Math.atan2(guarded.getPosition().y - pal2.getPosition().y, guarded.getPosition().x - pal2.getPosition().x), guarded),
            "inBeam is true for a tower straight down the beam");
        // the beam stops in phase 2
        hpTo(g, pal, 0.69);
        check(pal.getPhase() == 1 && !pr.isBeamActive(pal), "no Panopticon beam in phase 2");
    }

    private static void palantirPromptBroadcast() {
        Game g = frozen();
        Boss pal = palantir(g, 500);
        Vec p = pal.getPosition();
        Tower ds = place(g, TowerType.DEEPSEEK, p.add(new Vec(-200, -120)), 3);
        List<Tower> others = new ArrayList<>();
        others.add(place(g, TowerType.GPT, p.add(new Vec(0, -160)), 3));
        others.add(place(g, TowerType.GEMINI, p.add(new Vec(160, -60)), 2));
        others.add(place(g, TowerType.SORA, p.add(new Vec(-160, 60)), 1));
        others.add(place(g, TowerType.GROK, p.add(new Vec(150, 150)), 0));
        others.add(place(g, TowerType.SUNO, p.add(new Vec(-300, 200)), 0));
        hpTo(g, pal, 0.69);
        check(pal.getPhase() == 1, "phase 2 at 69%");
        PalantirProtocols pr = pal.getProtocols();
        runSeconds(g, PalantirProtocols.BROADCAST_FIRST - 0.2);
        check(pr.getBroadcasts() == 0, "the first broadcast waits " + PalantirProtocols.BROADCAST_FIRST + " s");
        runSeconds(g, 0.3);
        check(pr.getBroadcasts() == 1, "Prompt Broadcast fires");
        int n = PalantirProtocols.broadcastTargets(g);
        check(n == PalantirProtocols.BROADCAST_TARGETS, "a small defence gets " + PalantirProtocols.BROADCAST_TARGETS + " targets (" + n + ")");
        List<Tower> sorted = new ArrayList<>(others);
        sorted.sort((a, b) -> Integer.compare(b.getInvestedCost(), a.getInvestedCost()));
        for (int i = 0; i < sorted.size(); i++) {
            Tower t = sorted.get(i);
            if (i < n) check(t.isHijacked() && t.getIntrusion().getHijacker() == pal, "broadcast hijacks the #" + (i + 1) + " investment " + t);
            else check(!t.isHijacked(), "cheaper " + t + " is not hijacked by the broadcast");
        }
        check(!ds.isOffline(), "DeepSeek (immune, the priciest) ignores the broadcast");
        check(pr.getLastBroadcastTargets().size() == n, "the renderer sees the broadcast targets");
        runSeconds(g, PalantirProtocols.BROADCAST_INTERVAL);
        check(pr.getBroadcasts() == 2, "broadcasts repeat every " + PalantirProtocols.BROADCAST_INTERVAL + " s");
        // a big defence gets more targets, capped
        Game big = frozen();
        for (int i = 0; i < 200; i++) {
            Vec v = TestKit.buildableNear(big, new Vec(60 + (i * 73) % 1080, 60 + (i * 41) % 780), 200);
            if (big.getTowerManager().placementProblem(TowerType.GPT, v) == null || "Not enough cash".equals(big.getTowerManager().placementProblem(TowerType.GPT, v))) forcePlace(big, TowerType.GPT, v, 0);
        }
        int towers = big.getTowerManager().getPlayerTowers().size();
        check(PalantirProtocols.broadcastTargets(big) == Math.min(PalantirProtocols.BROADCAST_MAX_TARGETS, PalantirProtocols.BROADCAST_TARGETS + towers / PalantirProtocols.BROADCAST_TOWERS_PER_EXTRA),
            "targets grow with the defence (" + towers + " towers -> " + PalantirProtocols.broadcastTargets(big) + "), at most " + PalantirProtocols.BROADCAST_MAX_TARGETS);
    }

    private static void palantirDecoys() {
        Game g = frozen();
        Boss pal = palantir(g, 500);
        Vec p = pal.getPosition();
        Tower gpt = place(g, TowerType.GPT, p.add(new Vec(0, -70)), 0);
        Tower ds = place(g, TowerType.DEEPSEEK, p.add(new Vec(0, 90)), 0);
        gpt.setTargeting(Targeting.STRONGEST);
        ds.setTargeting(Targeting.STRONGEST);
        check(g.getCombat().acquireTargets(gpt, 1).get(0) == pal, "before phase 2 the GPT targets Palantir");
        int enemiesBefore = g.getEnemyManager().getEnemies().size();
        double cash = g.getCash();
        int lives = g.getLives();
        hpTo(g, pal, 0.69);
        List<Enemy> decoys = new ArrayList<>();
        for (Enemy e : g.getEnemyManager().getEnemies()) if (e.getType() == EnemyType.PALANTIR_HOLOGRAM) decoys.add(e);
        check(decoys.size() == PalantirProtocols.DECOYS, "phase 2 projects " + PalantirProtocols.DECOYS + " holographic decoys (" + decoys.size() + ")");
        check(g.getEnemyManager().getEnemies().size() == enemiesBefore + PalantirProtocols.DECOYS, "nothing else spawns");
        check(pal.getProtocols().getDecoys().size() == PalantirProtocols.DECOYS && g.getInjection().hasDecoys(), "the decoys are tracked");
        for (Enemy d : decoys) {
            check(Math.abs(d.getMaxHp() - Math.round(pal.getMaxHp() * PalantirProtocols.DECOY_HP_FRACTION)) <= 1, "a decoy has " + PalantirProtocols.DECOY_HP_FRACTION * 100 + "% of Palantir's HP (" + d.getMaxHp() + ")");
            check(!d.isBoss() && d.getType().reward == 0 && d.getType().lives == 0, "decoys are not bosses, pay nothing and cost no lives");
            check(Math.abs(d.getDistance() - pal.getDistance()) <= PalantirProtocols.DECOY_SPACING + 1, "decoys fly next to Palantir");
            check(!d.getType().isSpawnableSpecies(), "the hologram is never part of a wave");
        }
        List<Enemy> t = g.getCombat().acquireTargets(gpt, 1);
        check(!t.isEmpty() && t.get(0).getType() == EnemyType.PALANTIR_HOLOGRAM, "decoys draw a non-immune tower's fire (even on Strongest)");
        List<Enemy> td = g.getCombat().acquireTargets(ds, 1);
        check(!td.isEmpty() && td.get(0) == pal, "DeepSeek (immune to prompt injection) sees through the holograms");
        // leak one: no lives lost; kill the other: no cash
        Enemy leak = decoys.get(0);
        leak.setDistance(leak.getRoute().getTotalLength() - 0.5);
        g.setGlobalEnemySpeedMultiplier(1);
        g.run(30);
        g.setGlobalEnemySpeedMultiplier(0);
        check(!leak.isAlive() && g.getLives() == lives, "a leaking hologram costs no lives");
        double before = g.getCash();
        TestKit.killOutright(g, decoys.get(1));
        check(g.getCash() == before && !decoys.get(1).isAlive(), "a destroyed hologram pays nothing");
        check(!g.getInjection().hasDecoys(), "no decoys left");
        check(g.getCombat().acquireTargets(gpt, 1).get(0) == pal, "with the decoys gone the GPT targets Palantir again");
        check(cash <= g.getCash() + 1e-9, "cash never dropped");
    }

    private static void palantirKillSwitch() {
        Game g = frozen();
        Boss pal = palantir(g, 500);
        Vec p = pal.getPosition();
        Tower gpt = place(g, TowerType.GPT, p.add(new Vec(-150, -150)), 3);
        Tower ds = place(g, TowerType.DEEPSEEK, p.add(new Vec(150, -150)), 3);
        Tower zet = place(g, TowerType.ZETHOS, p.add(new Vec(-150, 170)), TowerCatalog.ZETHOS_UPGRADES);
        g.addCash(3 * TowerCatalog.ABILITY_UNLOCK_COST, null);
        check(g.unlockAbility(gpt) && g.unlockAbility(ds) && g.unlockAbility(zet), "abilities unlocked");
        Tower locked = place(g, TowerType.GEMINI, p.add(new Vec(170, 170)), 3);
        hpTo(g, pal, 0.69);
        hpTo(g, pal, 0.41);
        check(g.getBanner() != null && g.getBanner().startsWith("KILL SWITCH"), "a warning shows before the kill switch (" + g.getBanner() + ")");
        check(gpt.getAbilityCooldownRemaining() == 0 && ds.getAbilityCooldownRemaining() == 0, "abilities still ready in phase 2");
        int lockheeds = g.getEnemyManager().countOfType(EnemyType.LOCKHEED_MARTIN);
        hpTo(g, pal, 0.34);
        PalantirProtocols pr = pal.getProtocols();
        check(pal.getPhase() == 2 && pr.isKillSwitchUsed(), "System Takeover fires the kill switch");
        check(Math.abs(gpt.getAbilityCooldownRemaining() - gpt.getAbility().cooldown) < 1e-6, "GPT's unlocked ability restarts its full cooldown");
        check(Math.abs(zet.getAbilityCooldownRemaining() - zet.getAbility().cooldown) < 1e-6, "Zethos's unlocked ability restarts its full cooldown");
        check(ds.getAbilityCooldownRemaining() == 0, "DeepSeek (immune) keeps its ability ready");
        check(locked.isAbilityLocked() && locked.getAbilityCooldownRemaining() == 0, "a locked ability is untouched");
        check(pr.getKillSwitchResets() == 2, "two abilities reset (" + pr.getKillSwitchResets() + ")");
        check(g.getEnemyManager().countOfType(EnemyType.LOCKHEED_MARTIN) == lockheeds + 2, "the Lockheed escorts still launch");
        check(g.getWindowLink().consumeGrabRequests() >= 1, "System Takeover asks the UI to grab the window");
        gpt.resetAbilityCooldown();
        runSeconds(g, 2);
        check(gpt.getAbilityCooldownRemaining() == 0 && pr.getKillSwitchResets() == 2, "the kill switch fires only once");
    }

    private static void windowSeal() {
        Game g = frozen();
        Boss pal = palantir(g, 500);
        check(g.getWindowFraction() == 1.0, "the window fraction defaults to 1.0");
        hpTo(g, pal, 0.30);
        WindowLink link = g.getWindowLink();
        check(pal.getPhase() == 2 && link.isTakeoverActive(), "phase 3 starts the takeover");
        check(!pal.isSealed(), "an untouched window (fraction 1.0) never seals Palantir");
        check(Math.abs(pal.takeDamage(100, g.getTime()) - 100) < 1e-9, "full damage while unsealed");
        g.setWindowFraction(WindowLink.SEAL_THRESHOLD);
        g.run(1);
        check(!pal.isSealed(), "exactly " + WindowLink.SEAL_THRESHOLD + " does not seal");
        g.setWindowFraction(0.72);
        g.run(1);
        check(pal.isSealed() && link.isSealing(), "a window below " + WindowLink.SEAL_THRESHOLD + " seals Palantir");
        check(Math.abs(pal.takeDamage(100, g.getTime()) - 100 * PalantirProtocols.SEAL_DAMAGE_MULT) < 1e-9, "sealed Palantir takes " + PalantirProtocols.SEAL_DAMAGE_MULT + "x damage");
        double hp0 = pal.getHp();
        runSeconds(g, 2);
        double gain = pal.getHp() - hp0;
        check(Math.abs(gain - PalantirProtocols.SEAL_REGEN_PER_SEC * pal.getMaxHp() * 2) < pal.getMaxHp() * 0.001, "sealed Palantir regenerates " + PalantirProtocols.SEAL_REGEN_PER_SEC * 100 + "%/s (" + gain + ")");
        runSeconds(g, 60);
        check(pal.getHp() <= pal.getMaxHp() * PalantirProtocols.SEAL_REGEN_CAP + 1e-6 && pal.getHp() >= pal.getMaxHp() * PalantirProtocols.SEAL_REGEN_CAP - 1, "regeneration stops at " + PalantirProtocols.SEAL_REGEN_CAP * 100 + "% (" + pal.getHpFraction() + ")");
        check(pal.getPhase() == 2, "regeneration never reverts the phase");
        g.setWindowFraction(0.9);
        g.run(1);
        check(!pal.isSealed(), "dragging the window back above " + WindowLink.SEAL_THRESHOLD + " breaks the seal");
        check(Math.abs(pal.takeDamage(100, g.getTime()) - 100) < 1e-9, "full damage again");
        g.setWindowFraction(Double.NaN);
        check(g.getWindowFraction() == 0.9, "NaN reports are ignored");
        g.setWindowFraction(-3);
        check(g.getWindowFraction() >= 0.05, "the fraction is clamped");
        g.setWindowFraction(0.5);
        TestKit.killOutright(g, pal);
        check(!link.isTakeoverActive() && !link.isSealing(), "the takeover ends when Palantir dies");
    }

    private static void windowSealNeverInHeadless() {
        // the bot / tests / headless runs never report a fraction: Palantir is never sealed by the grab
        Game g = frozen();
        Boss pal = palantir(g, 500);
        hpTo(g, pal, 0.30);
        int requests = g.getWindowLink().consumeGrabRequests();
        runSeconds(g, PalantirProtocols.REGRAB_INTERVAL + 1);
        requests += g.getWindowLink().consumeGrabRequests();
        check(!pal.isSealed() && pal.getProtocols().getSealedTime() == 0, "never sealed without a windowed UI");
        check(requests >= 2, "the grab is renewed every " + PalantirProtocols.REGRAB_INTERVAL + " s (" + requests + " requests)");
        // an inert grab controller (headless / demo / no window) never reports anything
        WindowGrab inert = WindowGrab.create(null, false);
        check(!inert.isActive(), "no window: the controller is inert");
        check(!WindowGrab.create(null, true).isActive(), "the demo never grabs");
        check(!WindowGrab.environmentAllows() || !java.awt.GraphicsEnvironment.isHeadless(), "headless runs never allow the grab");
        g.setWindowFraction(0.95);
        g.getWindowLink().requestGrab(pal);
        inert.frame(0.1, g);
        check(g.getWindowFraction() == 0.95 && !inert.isHolding(), "an inert controller leaves the simulation alone");
    }

    private static void windowGrabGeometry() {
        Rectangle screen = new Rectangle(0, 25, 1920, 1055);
        Dimension min = new Dimension(WindowGrab.MIN_W, WindowGrab.MIN_H);
        Rectangle base = new Rectangle(220, 60, 1472, 946);
        Rectangle t = WindowGrab.plan(base, base, screen, min, 1);
        check(t.width == (int) Math.round(base.width * WindowGrab.SHRINK) && t.height == (int) Math.round(base.height * WindowGrab.SHRINK), "the grab shrinks to " + WindowGrab.SHRINK + " of the old size (" + t + ")");
        check(screen.contains(t), "the grabbed window stays on screen");
        double f = WindowGrab.fraction(t.getSize(), base.getSize());
        check(f >= 0.70 && f <= 0.75 && f < WindowLink.SEAL_THRESHOLD, "a fresh grab seals Palantir (fraction " + f + ")");
        double dx = t.getCenterX() - base.getCenterX(), dy = t.getCenterY() - base.getCenterY();
        check(Math.abs(dx - screen.width * WindowGrab.DRIFT_X) <= 1 && Math.abs(dy - screen.height * WindowGrab.DRIFT_Y) <= 1, "the window drifts a little (" + dx + ", " + dy + ")");
        Rectangle back = WindowGrab.plan(base, base, screen, min, -1);
        check(back.getCenterX() < base.getCenterX(), "the next grab drifts the other way");
        // never below the minimum size, never larger than the screen, always inside it
        Rectangle small = new Rectangle(100, 100, 700, 450);
        Rectangle ts = WindowGrab.plan(small, small, screen, min, 1);
        check(ts.width == WindowGrab.MIN_W && ts.height == WindowGrab.MIN_H, "a small window stops at the 640x420 minimum (" + ts + ")");
        Rectangle edge = new Rectangle(1700, 900, 1200, 800);
        Rectangle te = WindowGrab.plan(edge, edge, screen, min, 1);
        check(screen.contains(te), "a window near the screen edge is clamped inside (" + te + ")");
        Rectangle huge = WindowGrab.clampToScreen(new Rectangle(-50, -50, 4000, 3000), screen, min);
        check(huge.width <= screen.width && huge.height <= screen.height && screen.contains(huge), "never larger than the screen");
        Rectangle tiny = WindowGrab.clampToScreen(new Rectangle(10, 30, 100, 100), screen, min);
        check(tiny.width == WindowGrab.MIN_W && tiny.height == WindowGrab.MIN_H, "never below the minimum");
        // fraction, animation helpers
        check(WindowGrab.fraction(new Dimension(1600, 1000), new Dimension(1600, 1000)) == 1.0, "untouched window = 1.0");
        check(WindowGrab.fraction(new Dimension(2000, 900), new Dimension(1600, 1000)) == 0.9, "the smaller ratio counts");
        check(WindowGrab.fraction(new Dimension(10, 10), null) == 1.0, "no baseline = 1.0");
        check(WindowGrab.ease(0) == 0 && WindowGrab.ease(1) == 1 && WindowGrab.ease(0.5) == 0.5 && WindowGrab.ease(2) == 1, "ease-in-out endpoints");
        check(WindowGrab.lerp(base, t, 0).equals(base) && WindowGrab.lerp(base, t, 1).equals(t), "lerp endpoints");
        check(WindowGrab.ANIM_SECONDS >= 1 && WindowGrab.ANIM_SECONDS <= 2, "the grab animates over 1-2 s");
    }
}
