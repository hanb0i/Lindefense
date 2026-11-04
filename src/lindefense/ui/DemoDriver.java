package lindefense.ui;

import acm.graphics.GCanvas;
import java.awt.Window;
import java.awt.event.MouseEvent;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;
import javax.swing.SwingUtilities;
import lindefense.enemy.EnemyType;
import lindefense.tower.Faction;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Optional scripted walkthrough used for automated UI verification. Enabled
 * with {@code -Dlindefense.demo=<output dir>}; it drives the real screens
 * through the program's own mouse handlers (pixel coordinates mapped through
 * the scaled layer), resizes the window, verifies click-to-place lands on the
 * cursor at each size, writes PNG snapshots of the canvas, and exits.
 * Not used in normal play.
 */
final class DemoDriver {
    private final LindefenseProgram app;
    private final File out;
    private final List<double[]> steps = new ArrayList<>(); // {time, index}
    private double t;
    private int next;
    private final List<String> results = new ArrayList<>();

    DemoDriver(LindefenseProgram app, String dir) {
        this.app = app;
        this.out = new File(dir);
        out.mkdirs();
        // index -> time (seconds) of each scripted step
        double[] times = new double[41];
        double[][] sched = { { 0, 2.6 }, { 1, 2.8 }, { 2, 3.8 }, { 3, 4.0 }, { 4, 10.0 }, { 5, 11.5 }, { 6, 13.0 }, { 7, 13.5 }, { 8, 15.0 }, { 9, 15.5 },
            { 10, 17.0 }, { 11, 19.5 }, { 12, 28.0 }, { 13, 10.2 }, { 14, 10.4 }, { 15, 0.5 }, { 16, 1.6 }, { 17, 1.9 }, { 18, 2.2 }, { 19, 2.5 },
            { 20, 10.5 }, { 21, 10.7 }, { 22, 10.9 }, { 23, 11.1 }, { 24, 11.3 }, { 25, 19.7 }, { 26, 20.0 }, { 27, 20.1 }, { 28, 20.4 }, { 29, 20.7 },
            { 30, 20.8 }, { 31, 23.4 }, { 32, 23.6 }, { 33, 23.7 }, { 34, 25.8 }, { 35, 11.35 },
            { 36, 26.0 }, { 37, 26.2 }, { 38, 26.5 }, { 39, 26.9 }, { 40, 27.3 } };
        for (double[] sc : sched) times[(int) sc[0]] = sc[1];
        for (int i = 0; i < times.length; i++) steps.add(new double[] { times[i], i });
        steps.sort((a, b) -> Double.compare(a[0], b[0]));
    }

    void frame(double dt) {
        t += dt;
        while (next < steps.size() && t >= steps.get(next)[0]) {
            int idx = (int) steps.get(next)[1];
            next++;
            try { run(idx); } catch (Exception e) { results.add("FAIL step " + idx + ": " + e); e.printStackTrace(); }
        }
    }

    private void run(int idx) {
        GCanvas canvas = app.getGCanvas();
        switch (idx) {
            case 0: snap("01_menu"); break;
            case 1: clickLogical(Ui.W / 2.0, 528); break;              // Play
            case 2: snap("02_mapselect"); break;
            case 3: {
                double[] dc = MapSelectScreen.deployCenter(0);   // Play map 1
                clickLogical(dc[0], dc[1]);
                Game g = app.getGame();
                g.addCash(5000, null);
                g.setHeroCollection(lindefense.sim.HeroCollection.inMemory()); for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);   // tools never touch saved unlocks
                placeViaClick(TowerType.GPT, new Vec(380, 300));
                placeViaClick(TowerType.CLAUDE, new Vec(700, 250));
                placeViaClick(TowerType.PERPLEXITY, new Vec(460, 520));
                placeViaClick(TowerType.LOBBER_LUIS, new Vec(560, 480));
                placeViaClick(TowerType.SUNO, new Vec(820, 660));
                app.getGameScreen().keyPressed(new java.awt.event.KeyEvent(canvas, 0, 0, 0, java.awt.event.KeyEvent.VK_SPACE, ' '));
                app.getGameScreen().setSpeed(3);
                for (int k = 0; k < 12; k++) g.getWaveManager().startNextWave();
                break;
            }
            case 4: {
                for (Tower tw : app.getGame().getTowerManager().getTowers()) if (tw.getType() == TowerType.LOBBER_LUIS) app.getGameScreen().selectTower(tw);
                app.getGameScreen().frame(0.01);
                snap("03_game_default"); app.getGameScreen().setSpeed(1); break; }
            case 5: { resize(900, 600); break; }
            case 6: { snap("04_game_small_900x600"); verifyClick("small"); break; }
            case 7: { resize(2400, 1400); break; }
            case 8: { snap("05_game_large_2400x1400"); verifyClick("large"); break; }
            case 9: {
                resize(1500, 950);
                Game g = app.getGame();
                // jump to the finale: Palantir + a boss escort
                while (g.getWave() < 99) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
                g.getEnemyManager().clear();
                g.startNextWave();
                g.getEnemyManager().spawn(EnemyType.BELLARMINE_COLLEGE_PREP, null, 1, 400);
                g.addCash(20000, null);
                for (Tower tw : new ArrayList<>(g.getTowerManager().getTowers())) for (int u = 0; u < 3; u++) g.upgradeTower(tw);
                g.setSpeed(3);
                break;
            }
            case 10: {
                Game g = app.getGame();
                if (g.getPalantir() != null) g.getPalantir().beginSurveillance(g);
                break;
            }
            case 11: {
                Game g = app.getGame();
                boolean ok = g.getWave() == 100 && g.getPalantir() != null && g.getPalantir().isAlive();
                results.add((ok ? "PASS" : "FAIL") + " finale fights Palantir on wave 100 (wave " + g.getWave() + ", palantir " + (g.getPalantir() != null) + ")");
                snap("06_palantir");
                break;
            }
            case 13: {
                // ALL-towers shop view: toggle via the hotkey path, hover a cell, snapshot, then verify a cell click starts placement
                app.getGameScreen().toggleShopAll();
                // the shop re-lays itself out (compact / roomy cells) a frame after the toggle: let it settle, then take the
                // card button's position from the CURRENT layout right before clicking
                for (int k = 0; k < 4; k++) app.getGameScreen().frame(0.01);
                int lastCell = ShopLayout.allCells().size() - 1;
                TowerType want = ShopLayout.allCells().get(lastCell).type;
                List<UIButton> btns = app.getGameScreen().getSidePanel().getButtons();
                UIButton card = btns.get(ShopLayout.shopFactions().size() + 2 + lastCell);   // tabs, ALL, help, then the cards in cell order
                MouseEvent mv = pixelEvent(card.getX() + 5, card.getY() + 5);
                app.mouseMoved(mv);
                app.getGameScreen().frame(0.01);
                snap("03b_shop_all");
                app.mousePressed(mv);
                boolean ok = app.getGameScreen().getPlacing() == want && app.getGameScreen().getSidePanel().isAllMode();
                results.add((ok ? "PASS" : "FAIL") + " ALL-view cell click starts placement of " + want + " (got " + app.getGameScreen().getPlacing() + ")");
                app.getGameScreen().beginPlacing(null);
                break;
            }
            case 14: { app.getGameScreen().toggleShopAll(); break; }
            case 15: snap("00_menu_intro"); break;
            case 16: { resize(900, 600); break; }
            case 17: { snap("00b_menu_small"); resize(2400, 1400); break; }
            case 18: { snap("00c_menu_large"); resize(1600, 1028); break; }
            case 19: { app.mouseMoved(pixelEvent(Ui.W / 2.0, 528)); break; }
            case 20: {
                // busy late wave: ~100 damaged enemies across all lanes
                Game g = app.getGame();
                EnemyType[] ts = { EnemyType.PRIMITIVE_VARIABLE, EnemyType.STATIC_ARRAY, EnemyType.DYNAMIC_ARRAY, EnemyType.BUBBLE_SORT, EnemyType.MERGE_SORT,
                    EnemyType.QUICK_SORT, EnemyType.HEAP_SORT, EnemyType.SHELL_SORT, EnemyType.TIMSORT, EnemyType.RADIX_SORT };
                int routes = g.getMap().getRoutes().size();
                for (int i = 0; i < 100; i++) {
                    lindefense.enemy.Enemy e = g.getEnemyManager().spawn(ts[i % ts.length], null, i % routes, 40 + i * 9);
                    if (e != null && i % 3 != 0) e.takeDamage(e.getMaxHp() * (0.12 + 0.75 * ((i * 37) % 100) / 100.0), g.getTime());
                }
                break;
            }
            case 21: snap("03c_busy_wave"); break;
            case 22: {
                // placement ghost on the track (invalid)
                app.getGameScreen().beginPlacing(TowerType.CLAUDE);
                Vec wp = app.getGame().getMap().getRoutes().get(0).getWaypoints().get(2);
                app.mouseMoved(pixelEvent(wp.x + Ui.WORLD_X, wp.y + Ui.WORLD_Y));
                app.getGameScreen().frame(0.01);
                snap("03d_placing_invalid");
                break;
            }
            case 23: {
                // placement ghost on a valid spot
                Game g = app.getGame();
                outer:
                for (int yy = 100; yy < 800; yy += 20) for (int xx = 100; xx < 1100; xx += 20) {
                    Vec v = new Vec(xx, yy);
                    if (g.getTowerManager().placementProblem(TowerType.CLAUDE, v) == null) {
                        app.mouseMoved(pixelEvent(v.x + Ui.WORLD_X, v.y + Ui.WORLD_Y));
                        break outer;
                    }
                }
                app.getGameScreen().frame(0.01);
                snap("03e_placing_valid");
                app.getGameScreen().beginPlacing(null);
                app.getGameScreen().selectTower(null);
                app.mouseMoved(pixelEvent(700 + Ui.WORLD_X, 250 + Ui.WORLD_Y));
                break;
            }
            case 24: snap("03f_hover_nameplate"); app.mouseMoved(pixelEvent(5, 5)); break;
            case 25: {
                Game g = app.getGame();
                EnemyType[] bs = { EnemyType.BELLARMINE_COLLEGE_PREP, EnemyType.SW_RESOURCE_CONSULTANT, EnemyType.THREE_COM, EnemyType.LOCKHEED_MARTIN };
                for (int i = 0; i < bs.length; i++) {
                    lindefense.enemy.Enemy e = g.getEnemyManager().spawn(bs[i], null, 0, 250 + i * 160);
                    if (e != null) e.takeDamage(e.getMaxHp() * (0.1 + 0.15 * i), g.getTime());
                }
                if (g.getPalantir() != null) g.getPalantir().takeDamage(g.getPalantir().getMaxHp() * 0.3, g.getTime());
                break;
            }
            case 26: snap("06b_multi_boss"); break;
            case 27: app.getGame().setPaused(true); break;
            case 28: {
                snap("07_paused");
                Game g = app.getGame();
                g.setPaused(false);
                if (g.getPalantir() != null) g.loseLives(Math.max(0, g.getLives() - 18), g.getPalantir());
                break;
            }
            case 29: snap("06c_low_lives"); break;
            case 30: {
                Game g = app.getGame();
                if (g.getPalantir() != null) g.getPalantir().takeDamage(1e12, g.getTime());
                g.setSpeed(3);
                break;
            }
            case 31: {
                boolean ok = app.getGame().getState() == Game.State.VICTORY;
                results.add((ok ? "PASS" : "FAIL") + " victory screen reached (state " + app.getGame().getState() + ")");
                snap("08_victory");
                break;
            }
            case 32: app.startGame(0); break;
            case 33: {
                Game g = app.getGame();
                lindefense.enemy.Enemy e = g.getEnemyManager().spawn(EnemyType.STATIC_ARRAY, null, 0, 100);
                g.loseLives(g.getLives(), e);
                g.setSpeed(3);
                break;
            }
            case 34: snap("09_defeat"); break;
            case 35: {
                GameScreen gs = app.getGameScreen();
                gs.toggleShopAll();
                gs.frame(0.01); gs.frame(0.01);
                snap("03g_shop_all_idle");
                gs.toggleShopAll();
                gs.toggleHelp();
                gs.frame(0.01);
                snap("03h_help_overlay");
                gs.toggleHelp();
                break;
            }
            case 36: menuRestartFlow(); break;
            case 37: resize(900, 600); break;
            case 38: {
                GameScreen gs = app.getGameScreen();
                gs.openMenu(); gs.frame(0.01);
                snap("10d_pause_menu_small");
                resize(2400, 1400);
                break;
            }
            case 39: { snap("10e_pause_menu_large"); resize(1600, 1028); break; }
            case 40: menuQuitFlow(); break;
            case 12: {
                for (String r : results) System.out.println(r);
                System.out.println("DEMO DONE");
                System.exit(0);
                break;
            }
            default: break;
        }
    }

    private void check(boolean ok, String what) { results.add((ok ? "PASS " : "FAIL ") + what); }

    /** MENU -> RESTART -> confirm: a fresh game on the same map and difficulty (wave, cash, lives, towers reset). */
    private void menuRestartFlow() {
        app.startGame(0);
        GameScreen gs = app.getGameScreen();
        Game g0 = app.getGame();
        g0.addCash(3000, null);
        placeViaClick(TowerType.GPT, new Vec(380, 300));
        g0.startNextWave();
        g0.run(300);
        boolean progressed = g0.getWave() > 0 && !g0.getTowerManager().getTowers().isEmpty();
        gs.openMenu();
        gs.frame(0.01);
        check(gs.isMenuOpen() && g0.isPaused(), "MENU button path opens the pause menu and pauses the game");
        snap("10_pause_menu");
        clickLogical(600, 489);                                   // RESTART
        check(gs.getPendingConfirm() == 1 && app.getGame() == g0, "RESTART asks for confirmation first");
        gs.frame(0.01);
        snap("10b_restart_confirm");
        clickLogical(735, 595);                                   // NO
        check(gs.getPendingConfirm() == 0 && app.getGame() == g0 && gs.isMenuOpen(), "NO keeps the current game and returns to the menu");
        clickLogical(600, 489);
        clickLogical(465, 595);                                   // YES
        Game g1 = app.getGame();
        check(progressed && g1 != g0 && g1.getWave() == 0 && g1.getLives() == g1.getDifficulty().startLives(Game.START_LIVES)
            && g1.getCash() == g1.getDifficulty().startCash(Game.START_CASH) && g1.getTowerManager().getTowers().isEmpty()
            && g1.getMap().getName().equals(g0.getMap().getName()) && g1.getDifficulty() == g0.getDifficulty() && !g1.isPaused(),
            "RESTART YES gives a fresh game on the same map and difficulty (wave " + g1.getWave() + ", cash " + (int) g1.getCash() + ", lives " + g1.getLives() + ")");
        check(app.getGameScreen() != gs, "old game screen was replaced");
    }

    /** MENU -> QUIT LEVEL -> confirm: back on the map select screen. */
    private void menuQuitFlow() {
        GameScreen gs = app.getGameScreen();
        gs.openMenu();
        gs.frame(0.01);
        clickLogical(600, 657);                                   // QUIT LEVEL
        check(gs.getPendingConfirm() == 2 && app.getGame() != null, "QUIT LEVEL asks for confirmation first");
        clickLogical(465, 595);                                   // YES
        check(app.getGame() == null && app.getGameScreen() == null, "QUIT LEVEL YES leaves the game (map select shown)");
        snap("10c_quit_to_mapselect");
    }

    private void resize(int w, int h) {
        Window win = SwingUtilities.getWindowAncestor(app.getGCanvas());
        win.setSize(w, h);
        win.validate();
    }

    private MouseEvent pixelEvent(double lx, double ly) {
        ScaledLayer root = app.getRoot();
        int px = (int) Math.round(lx * root.getScale() + (app.getGCanvas().getWidth() - Ui.W * root.getScale()) / 2);
        int py = (int) Math.round(ly * root.getScale() + (app.getGCanvas().getHeight() - Ui.H * root.getScale()) / 2);
        return new MouseEvent(app.getGCanvas(), MouseEvent.MOUSE_PRESSED, System.currentTimeMillis(), 0, px, py, 1, false, MouseEvent.BUTTON1);
    }

    /** Sends a press through the real program mouse handler at the pixel position of a logical point. */
    private void clickLogical(double lx, double ly) {
        MouseEvent ev = pixelEvent(lx, ly);
        app.mouseMoved(ev);
        app.mousePressed(ev);
    }

    private void placeViaClick(TowerType type, Vec world) {
        app.getGameScreen().beginPlacing(type);
        clickLogical(world.x + Ui.WORLD_X, world.y + Ui.WORLD_Y);
        app.getGameScreen().beginPlacing(null);
    }

    private void verifyClick(String label) {
        Game g = app.getGame();
        g.addCash(1000, null);
        Vec target = new Vec(label.equals("small") ? 150 : 320, 60);
        int before = g.getTowerManager().getTowers().size();
        placeViaClick(TowerType.QWEN, target);
        Tower placed = null;
        for (Tower tw : g.getTowerManager().getTowers()) if (tw.getType() == TowerType.QWEN && tw.getPosition().dist(target) < 1.5) placed = tw;
        boolean ok = placed != null && g.getTowerManager().getTowers().size() == before + 1;
        results.add((ok ? "PASS" : "FAIL") + " click-to-place after resize (" + label + ", canvas "
            + app.getGCanvas().getWidth() + "x" + app.getGCanvas().getHeight() + ", scale " + String.format("%.3f", app.getRoot().getScale()) + ")"
            + (placed != null ? " tower at " + placed.getPosition() : " no tower at " + target));
    }

    private void snap(String name) {
        GCanvas canvas = app.getGCanvas();
        int w = Math.max(1, canvas.getWidth()), h = Math.max(1, canvas.getHeight());
        BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        java.awt.Graphics2D g2 = img.createGraphics();
        canvas.paint(g2);
        g2.dispose();
        try {
            ImageIO.write(img, "png", new File(out, name + ".png"));
            results.add("SNAP " + name + " " + w + "x" + h);
        } catch (Exception e) {
            results.add("FAIL snapshot " + name + ": " + e);
        }
    }
}
