package lindefense.tools;

import acm.graphics.GCanvas;
import java.awt.Graphics2D;
import java.awt.Window;
import java.awt.event.KeyEvent;
import java.awt.event.MouseEvent;
import java.awt.image.BufferedImage;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import javax.swing.SwingUtilities;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Faction;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.ui.GameScreen;
import lindefense.ui.LindefenseProgram;
import lindefense.ui.ScaledLayer;
import lindefense.ui.Ui;

/**
 * Render soak: opens the real game window and drives the REAL rendering path
 * (screens, WorldView, SidePanel, every enemy / boss / tower / projectile
 * sprite and effect) as fast as possible, collecting every exception, including
 * ones thrown on the Swing event thread during repaint. For every map it visits
 * the menu, How-to-Play and map select, places all towers, upgrades them
 * through every tier, fires abilities (and Palantir's Predictive Surveillance),
 * plays waves 1-100 plus extra spawns of every enemy type with every modifier,
 * toggles the shop, selects / sells / retargets towers, pauses, resizes the
 * window, and finishes on the victory and defeat screens.
 *
 * <p>Usage: {@code ./build.sh && java -XX:-OmitStackTraceInFastThrow -cp build:lib/acm.jar lindefense.tools.RenderSoak [maps] [framesPerWave] [difficulty]}
 * where {@code maps} is e.g. {@code 0123} (default all) and {@code difficulty} is O1, ON, ON2 or ONN (default: rotate
 * through all four so every difficulty is played at least once when 4 maps run). Exits 0 when clean,
 * 1 when any exception was seen. Full traces go to {@code build/render-soak-<maps>.log}.</p>
 */
public final class RenderSoak {
    private RenderSoak() { }

    private static final Map<String, int[]> SEEN = new LinkedHashMap<>();
    private static final Map<String, String> FIRST = new LinkedHashMap<>();
    private static PrintWriter log;
    private static LindefenseProgram app;
    private static BufferedImage buffer;
    private static final Random RNG = new Random(7);
    private static int paints;
    /** Peak number of live zones / walkers / drones / hazards seen per kind (proves the new effects were exercised). */
    private static final Map<String, Integer> PEAK = new java.util.TreeMap<>();
    private static int abilitiesFired, targetedFired;

    public static void main(String[] args) throws Exception {
        String maps = args.length > 0 ? args[0] : "0123";
        int framesPerWave = args.length > 1 ? Integer.parseInt(args[1]) : 220;
        String diffArg = args.length > 2 ? args[2] : "rotate";
        String logName = "build/render-soak-" + maps + ".log";
        log = new PrintWriter(new FileWriter(logName), true);
        Thread.setDefaultUncaughtExceptionHandler((th, e) -> record("uncaught[" + th.getName() + "]", e));
        app = new LindefenseProgram();
        Thread starter = new Thread(() -> app.start(new String[0]), "acm-start");
        starter.start();
        long deadline = System.currentTimeMillis() + 20000;
        while ((app.getGCanvas() == null || app.getRoot().getElementCount() == 0) && System.currentTimeMillis() < deadline) Thread.sleep(50);
        Thread.sleep(500);
        // self-test: an exception thrown on the EDT outside our wrappers must be captured
        SwingUtilities.invokeLater(() -> { throw new IllegalStateException("render-soak selftest"); });
        Thread.sleep(300);
        boolean captured = SEEN.keySet().removeIf(k -> k.contains("selftest"));
        System.out.println(captured ? "PASS self-test: EDT exceptions are captured" : "FAIL self-test: EDT exception was not captured");
        if (!captured) System.exit(2);
        long t0 = System.currentTimeMillis();
        int mapsRun = 0;
        for (char c : maps.toCharArray()) {
            int m = c - '0';
            if (m < 0 || m >= MapCatalog.MAP_COUNT) continue;
            lindefense.sim.Difficulty[] all = lindefense.sim.Difficulty.values();
            lindefense.sim.Difficulty diff = "rotate".equals(diffArg) ? all[mapsRun++ % all.length] : lindefense.sim.Difficulty.valueOf(diffArg);
            lindefense.sim.Difficulty.setSelected(diff);
            System.out.println("== map " + m + " difficulty " + diff);
            soakMap(m, framesPerWave);
            System.out.println("   done map " + m + " (" + (System.currentTimeMillis() - t0) / 1000 + "s, " + paints + " paints, " + SEEN.size() + " distinct errors so far)");
        }
        Thread.sleep(300); // let pending EDT repaints run
        System.out.println();
        System.out.println("================ RENDER SOAK SUMMARY ================");
        if (SEEN.isEmpty()) System.out.println("CLEAN: no exceptions (" + paints + " offscreen paints)");
        for (Map.Entry<String, int[]> en : SEEN.entrySet()) {
            System.out.println("x" + en.getValue()[0] + "  " + en.getKey().replace("\n", "\n      "));
        }
        System.out.println("Abilities fired: " + abilitiesFired + " (targeted: " + targetedFired + ")");
        System.out.println("Effects exercised (peak live count): " + PEAK);
        System.out.println("Distinct errors: " + SEEN.size() + "   (full traces: " + logName + ")");
        log.close();
        System.exit(SEEN.isEmpty() ? 0 : 1);
    }

    // ------------------------------------------------------------------ error capture
    static synchronized void record(String where, Throwable e) {
        Throwable root = e;
        while ((root instanceof java.lang.reflect.InvocationTargetException) && root.getCause() != null) root = root.getCause();
        StringBuilder key = new StringBuilder(root.getClass().getName());
        String msg = root.getMessage();
        if (msg != null) key.append(": ").append(msg.replaceAll("[0-9.\\-]+", "#"));
        StackTraceElement[] st = root.getStackTrace();
        for (int i = 0; i < Math.min(5, st.length); i++) key.append("\n  at ").append(st[i]);
        String k = key.toString();
        int[] n = SEEN.computeIfAbsent(k, x -> new int[1]);
        n[0]++;
        if (n[0] == 1) {
            StringWriter sw = new StringWriter();
            root.printStackTrace(new PrintWriter(sw));
            FIRST.put(k, sw.toString());
            log.println("---- [" + where + "] " + sw);
            if (!k.contains("selftest")) System.out.println("   NEW ERROR [" + where + "] " + k.split("\n")[0] + " | " + (st.length > 0 ? st[0] : ""));
        }
    }

    interface Action { void run() throws Exception; }

    /** Runs an action on the EDT, recording (not propagating) any exception. */
    static void edt(String where, Action a) {
        try {
            SwingUtilities.invokeAndWait(() -> {
                try { a.run(); } catch (Throwable t) { record(where, t); }
            });
        } catch (Exception e) {
            record(where, e);
        }
    }

    /** Paints the whole canvas offscreen through the real paint path. */
    static void paint() {
        GCanvas c = app.getGCanvas();
        int w = Math.max(1, c.getWidth()), h = Math.max(1, c.getHeight());
        if (buffer == null || buffer.getWidth() != w || buffer.getHeight() != h) buffer = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        Graphics2D g2 = buffer.createGraphics();
        try { c.paint(g2); paints++; } finally { g2.dispose(); }
    }

    // ------------------------------------------------------------------ input helpers
    static MouseEvent pixelEvent(double lx, double ly) {
        ScaledLayer root = app.getRoot();
        GCanvas c = app.getGCanvas();
        int px = (int) Math.round(lx * root.getScale() + (c.getWidth() - Ui.W * root.getScale()) / 2);
        int py = (int) Math.round(ly * root.getScale() + (c.getHeight() - Ui.H * root.getScale()) / 2);
        return new MouseEvent(c, MouseEvent.MOUSE_PRESSED, System.currentTimeMillis(), 0, px, py, 1, false, MouseEvent.BUTTON1);
    }

    static void click(double lx, double ly) {
        MouseEvent ev = pixelEvent(lx, ly);
        app.mouseMoved(ev);
        app.mousePressed(ev);
    }

    static void key(int code) {
        app.keyPressed(new KeyEvent(app.getGCanvas(), KeyEvent.KEY_PRESSED, System.currentTimeMillis(), 0, code, KeyEvent.CHAR_UNDEFINED));
    }

    static void resize(int w, int h) {
        Window win = SwingUtilities.getWindowAncestor(app.getGCanvas());
        win.setSize(w, h);
        win.validate();
    }

    static final int[][] SIZES = { { 640, 420 }, { 900, 600 }, { 2400, 1400 }, { 700, 1300 }, { 2400, 480 }, { 1600, 1028 } };

    // ------------------------------------------------------------------ the soak
    static void soakMap(int m, int framesPerWave) throws Exception {
        // menu + how-to-play + map select
        edt("menu", () -> { app.showMenu(); paint(); });
        for (int i = 0; i < 20; i++) edt("menu frame", () -> { menuFrames(0.05); paint(); });
        edt("menu help", () -> { click(Ui.W / 2.0, 604); paint(); });
        for (int i = 0; i < 10; i++) edt("help frame", () -> { menuFrames(0.05); paint(); });
        edt("menu help close", () -> { click(Ui.W / 2.0, 846); paint(); key(KeyEvent.VK_ENTER); paint(); });
        edt("menu tiny", () -> { app.getRoot().fit(3, 2); paint(); app.getRoot().fit(app.getGCanvas().getWidth(), app.getGCanvas().getHeight()); });
        edt("menu play", () -> { click(Ui.W / 2.0, 528); paint(); });
        for (int i = 0; i < 10; i++) edt("mapselect frame", () -> { menuFrames(0.05); app.mouseMoved(pixelEvent(100 + RNG.nextInt(1400), 100 + RNG.nextInt(800))); paint(); });
        edt("deploy", () -> {
            double[] dc = lindefense.ui.MapSelectScreen.deployCenter(m);
            click(dc[0], dc[1]);   // opens the mission briefing popup
            paint();
            double[] bc = lindefense.ui.MapSelectScreen.briefingDeployCenter();
            click(bc[0], bc[1]);   // the briefing's DEPLOY starts the match
            if (app.getGame() == null || app.getGame().getMap().getName() == null) app.startGame(m);
            paint();
        });
        final Game[] gh = new Game[1];
        edt("game setup", () -> {
            if (app.getGame() == null) app.startGame(m);
            Game g = app.getGame();
            gh[0] = g;
            g.setInvincible(true);
            g.addCash(1e7, null);
            placeAll(g);
            paint();
        });
        Game g = gh[0];
        List<Tower> keepTier0 = new ArrayList<>();
        edt("tier0 snapshot", () -> { keepTier0.addAll(g.getTowerManager().getPlayerTowers().subList(0, Math.min(5, g.getTowerManager().getPlayerTowers().size()))); });

        boolean extrasSpawned = false;
        for (int wave = 1; wave <= 100 && g.getState() == Game.State.PLAYING; wave++) {
            final int wv = wave;
            edt("start wave", () -> {
                if (!g.getWaveManager().canStartNextWave()) { g.getEnemyManager().clear(); g.getCombat().clear(); g.getWaveManager().endWave(); }
                if (wv == 1) key(KeyEvent.VK_SPACE); else g.startNextWave();
                g.getWaveManager().setAutoStart(wv % 2 == 0);
                app.getGameScreen().setSpeed(3);
                g.addCash(1e6, null);
                // upgrade progressively so every tier gets rendered for a while
                int targetTier = Math.min(3, wv / 6);   // 3 upgrades per tower
                for (Tower t : new ArrayList<>(g.getTowerManager().getPlayerTowers())) {
                    if (keepTier0.contains(t) && wv < 60) continue;
                    while (t.getTier() < targetTier && t.canUpgrade()) {
                        app.getGameScreen().selectTower(t);
                        if (RNG.nextBoolean()) app.getGameScreen().upgradeSelected(); else if (!g.upgradeTower(t)) break;
                    }
                    // maxed shop towers buy their $15,000 ability (U on a maxed tower, or the side-panel button path)
                    if (t.canUnlockAbility()) {
                        app.getGameScreen().selectTower(t);
                        if (RNG.nextBoolean()) app.getGameScreen().upgradeSelected(); else app.getGameScreen().unlockAbilitySelected();
                    }
                }
            });
            if (!extrasSpawned && wave == 35) {
                extrasSpawned = true;
                edt("spawn all types", () -> spawnAllTypes(g));
            }
            int frames = 0;
            while (frames < framesPerWave) {
                final int fr = frames;
                edt("game frame", () -> {
                    GameScreen gs = app.getGameScreen();
                    if (gs == null) return;
                    gs.frame(0.1);
                    interact(g, gs, fr, wv);
                    sampleEffects(g);
                    paint();
                });
                frames++;
                if (!g.getWaveManager().isWaveActive() && frames > 3) break;
                if (g.getState() != Game.State.PLAYING) break;
            }
            if (wave % 5 == 0) {
                int[] sz = SIZES[(wave / 5) % SIZES.length];
                edt("resize", () -> resize(sz[0], sz[1]));
                Thread.sleep(120);
                edt("after resize", () -> { app.getGameScreen().frame(0.05); paint(); });
            }
            if (wave % 10 == 0) System.out.println("   wave " + wave + " t=" + String.format("%.0f", g.getTime()) + " enemies=" + g.getEnemyManager().getEnemies().size()
                + " towers=" + g.getTowerManager().getTowers().size() + " errors=" + SEEN.size());
        }
        // Palantir finale: make sure it is on the field and dies
        edt("palantir ensure", () -> {
            if (g.getPalantir() == null && g.getState() == Game.State.PLAYING) {
                g.getEnemyManager().spawn(EnemyType.PALANTIR, null, 0, 300);
            }
        });
        for (int i = 0; i < 600 && g.getState() == Game.State.PLAYING; i++) {
            final int fi = i;
            edt("palantir frame", () -> {
                GameScreen gs = app.getGameScreen();
                gs.frame(0.1);
                Boss p = g.getPalantir();
                if (p != null && p.isAlive()) {
                    if (fi % 40 == 0 && !p.isTelegraphing()) p.beginSurveillance(g);
                    if (fi > 300) g.getEnemyManager().kill(p);
                }
                interact(g, gs, fi, 100);
                paint();
            });
        }
        edt("victory", () -> { app.getGameScreen().frame(0.1); paint(); });
        System.out.println("   final state " + g.getState() + " wave " + g.getWave());

        // defeat screen on a fresh game
        edt("defeat setup", () -> {
            app.startGame(m);
            Game d = app.getGame();
            d.startNextWave();
            Enemy e = d.getEnemyManager().spawn(EnemyType.values()[0], null, 0, 10);
            d.loseLives(10_000, e);
        });
        for (int i = 0; i < 60; i++) edt("defeat frame", () -> { app.getGameScreen().frame(0.1); paint(); });
        System.out.println("   defeat screen state " + app.getGame().getState());
        edt("defeat play again", () -> { click(Ui.WORLD_X + Ui.WORLD_W / 2.0 - 100, Ui.WORLD_Y + Ui.WORLD_H / 2.0 + 82); paint(); });
        for (int i = 0; i < 5; i++) edt("mapselect frame", () -> { menuFrames(0.05); paint(); });
        edt("esc to menu", () -> { key(KeyEvent.VK_ESCAPE); paint(); });
    }

    static void sampleEffects(Game g) {
        Map<String, Integer> now = new LinkedHashMap<>();
        for (lindefense.effects.TrackZone z : g.getEffects().getZones()) now.merge("zone:" + z.kind, 1, Integer::sum);
        for (lindefense.effects.TrackWalker w : g.getEffects().getWalkers()) now.merge("walker:" + w.kind, 1, Integer::sum);
        for (lindefense.effects.Drone d : g.getEffects().getDrones()) now.merge("drone:" + d.kind, 1, Integer::sum);
        for (lindefense.effects.NodeHazard h : g.getEffects().getHazards()) now.merge("hazard:" + h.kind, 1, Integer::sum);
        for (Map.Entry<String, Integer> e : now.entrySet()) PEAK.merge(e.getKey(), e.getValue(), Math::max);
    }

    /** A point on a route (preferably under a live enemy) for abilities that need a target point. */
    static Vec trackPoint(Game g) {
        List<Enemy> es = g.getEnemyManager().getEnemies();
        Vec from = es.isEmpty() ? g.getMap().getRoutes().get(0).positionAt(300 + RNG.nextInt(400)) : es.get(RNG.nextInt(es.size())).getPosition();
        lindefense.effects.Effects.TrackPoint tp = g.getEffects().nearestTrackPoint(from);
        return tp == null ? from : tp.position;
    }

    /** Advance whatever non-game screen is showing via the program's own components. */
    static void menuFrames(double dt) {
        // menu / map select animate from the program timer; call their frame via reflection-free path:
        for (int i = 0; i < app.getRoot().getElementCount(); i++) {
            Object o = app.getRoot().getElement(i);
            if (o instanceof lindefense.ui.MenuScreen) ((lindefense.ui.MenuScreen) o).frame(dt);
            else if (o instanceof lindefense.ui.MapSelectScreen) ((lindefense.ui.MapSelectScreen) o).frame(dt);
        }
    }

    static void placeAll(Game g) {
        g.setHeroLimit(Integer.MAX_VALUE);   // stress: the whole roster at once
        g.setHeroCollection(lindefense.sim.HeroCollection.inMemory()); for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);   // tools never touch saved unlocks
        GameMap map = g.getMap();
        List<Vec> spots = new ArrayList<>();
        for (int x = 30; x < GameMap.WIDTH; x += 13) for (int y = 30; y < GameMap.HEIGHT; y += 13) spots.add(new Vec(x, y));
        java.util.Collections.shuffle(spots, new Random(3));
        // two of each purchasable type (one of each hero)
        for (int round = 0; round < 2; round++) {
            for (TowerType t : TowerType.purchasable()) {
                if (round == 1 && t.isHero()) continue;   // one copy per hero
                double r = TowerCatalog.get(t).radius;
                for (Vec p : spots) {
                    if (map.isBuildable(p, r) && g.getTowerManager().canPlace(t, p)) {
                        // use the real UI path for the first round
                        if (round == 0) {
                            app.getGameScreen().beginPlacing(t);
                            app.getGameScreen().mouseMoved(p.x + Ui.WORLD_X, p.y + Ui.WORLD_Y);
                            app.getGameScreen().getSidePanel().update(0.01);
                            paintQuiet();
                            app.getGameScreen().mousePressed(p.x + Ui.WORLD_X, p.y + Ui.WORLD_Y, false);
                            app.getGameScreen().beginPlacing(null);
                        } else {
                            g.placeTower(t, p);
                        }
                        break;
                    }
                }
            }
        }
    }

    static void paintQuiet() {
        try { paint(); } catch (Throwable t) { record("paint", t); }
    }

    static void spawnAllTypes(Game g) {
        Modifier[] mods = Modifier.values();
        int k = 0;
        int routes = g.getMap().getRoutes().size();
        for (EnemyType t : EnemyType.values()) {
            for (int v = 0; v <= mods.length + 1; v++) {
                EnumSet<Modifier> set = EnumSet.noneOf(Modifier.class);
                if (v < mods.length) set.add(mods[v]);
                else if (v == mods.length) set.addAll(EnumSet.allOf(Modifier.class));
                if (t == EnemyType.PALANTIR) continue; // its death ends the campaign; the finale spawns it
                g.getEnemyManager().spawn(t, set, k++ % routes, RNG.nextInt(200));
            }
        }
    }

    static void interact(Game g, GameScreen gs, int frame, int wave) {
        List<Tower> towers = g.getTowerManager().getTowers();
        switch (frame % 23) {
            case 0: // abilities for everyone; targeted ones are armed through the UI and then cast on a track point
                for (Tower t : new ArrayList<>(towers)) {
                    if (!t.isAbilityReady() || t.getAbility() == null) continue;
                    gs.selectTower(t);
                    if (t.getAbility().needsTarget) {
                        Vec v = trackPoint(g);
                        if (RNG.nextBoolean()) {
                            gs.fireAbility(t);                                     // arms targeting mode
                            gs.mousePressed(v.x + Ui.WORLD_X, v.y + Ui.WORLD_Y, false);   // the click casts it
                            if (!t.isAbilityReady()) targetedFired++;
                            gs.cancelTargeting();
                        } else if (g.activateAbility(t, v)) targetedFired++;
                    } else {
                        gs.abilitySelected();
                    }
                    if (!t.isAbilityReady()) abilitiesFired++;
                }
                break;
            case 2: if (!towers.isEmpty()) { gs.selectTower(towers.get(RNG.nextInt(towers.size()))); gs.cycleTargeting(RNG.nextBoolean() ? 1 : -1); } break;
            case 4: gs.toggleShopAll(); break;
            case 6: gs.getSidePanel().setTab(lindefense.ui.ShopLayout.shopFactions().get(RNG.nextInt(lindefense.ui.ShopLayout.shopFactions().size()))); break;
            case 8: {
                TowerType[] p = TowerType.purchasable();
                gs.beginPlacing(p[RNG.nextInt(p.length)]);
                gs.mouseMoved(RNG.nextInt(1200), Ui.WORLD_Y + RNG.nextInt(900));
                break;
            }
            case 10: gs.beginPlacing(null); gs.mouseMoved(Ui.PANEL_X + RNG.nextInt(Ui.PANEL_W), RNG.nextInt(Ui.H)); break;
            case 12: {
                List<Enemy> es = g.getEnemyManager().getEnemies();
                if (!es.isEmpty()) gs.selectEnemy(es.get(RNG.nextInt(es.size())));
                break;
            }
            case 14: if (wave % 3 == 0) { // sell a random player tower and re-buy it at max tier
                List<Tower> pt = g.getTowerManager().getPlayerTowers();
                if (!pt.isEmpty()) {
                    Tower t = pt.get(RNG.nextInt(pt.size()));
                    TowerType type = t.getType();
                    Vec pos = t.getPosition();
                    gs.selectTower(t);
                    gs.sellSelected();
                    Tower n = g.placeTower(type, pos);
                    if (n != null) while (g.upgradeTower(n)) { /* to max */ }   // heroes are unique: re-buying after the sell is fine
                }
            } break;
            case 16: key(KeyEvent.VK_P); gs.frame(0.05); paintQuiet(); key(KeyEvent.VK_P); break;
            case 18: {
                Boss p = g.getPalantir();
                if (p != null && p.isAlive() && !p.isTelegraphing() && RNG.nextInt(3) == 0) p.beginSurveillance(g);
                break;
            }
            case 20: if (frame % 46 == 20) { app.getRoot().fit(RNG.nextBoolean() ? 2 : 640, RNG.nextBoolean() ? 1 : 400); paintQuiet();
                GCanvas c = app.getGCanvas(); app.getRoot().fit(c.getWidth(), c.getHeight()); } break;
            case 1: case 13: { // click a real side-panel / HUD button through the screen's mouse path
                List<lindefense.ui.UIButton> bs = new ArrayList<>(gs.getSidePanel().getButtons());
                bs.removeIf(b -> { String s = b.getText().toLowerCase(); return s.contains("menu") || s.contains("quit"); });
                if (!bs.isEmpty()) {
                    lindefense.ui.UIButton b = bs.get(RNG.nextInt(bs.size()));
                    gs.mousePressed(b.getX() + b.getW() / 2, b.getY() + b.getH() / 2, false);
                }
                if (frame % 2 == 1) gs.mousePressed(RNG.nextInt(1200), Ui.WORLD_Y + RNG.nextInt(900), RNG.nextInt(4) == 0);
                break;
            }
            case 22: // hover random shop / hud buttons
                gs.mouseMoved(RNG.nextInt(Ui.W), RNG.nextInt(Ui.H));
                key(new int[] { KeyEvent.VK_T, KeyEvent.VK_B, KeyEvent.VK_ESCAPE, KeyEvent.VK_A, KeyEvent.VK_1, KeyEvent.VK_3 }[RNG.nextInt(6)]);
                gs.setSpeed(3);
                break;
            default: break;
        }
    }
}
