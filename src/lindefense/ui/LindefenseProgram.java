package lindefense.ui;

import acm.graphics.GCanvas;
import acm.program.GraphicsProgram;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.GraphicsEnvironment;
import java.awt.Rectangle;
import java.awt.Window;
import java.awt.event.ComponentAdapter;
import java.awt.event.ComponentEvent;
import java.awt.event.KeyEvent;
import java.awt.event.MouseEvent;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;
import javax.swing.Timer;
import lindefense.map.MapCatalog;
import lindefense.sim.Game;

/**
 * The ACM GraphicsProgram that hosts Lindefense. Everything is drawn inside one
 * {@link ScaledLayer} laid out in a fixed 1600x1000 logical space, so the game
 * fills any window size (the window is resizable; the layer re-fits on every
 * resize and mouse coordinates are mapped back into logical space).
 *
 * <p>The simulation is advanced from a Swing timer on the event-dispatch thread,
 * which is also where ACM delivers mouse and key events, so no locking is needed.</p>
 *
 * <h3>Frame loop</h3>
 * The timer fires about every {@value #FRAME_MS} ms (so at most ~60 frames per second are produced) and coalesces:
 * if a frame is still being painted when the next tick is due, ticks are merged instead of queuing up, and the
 * mouse and key events waiting on the event thread are handled between frames. Each frame advances the simulation in
 * fixed {@link lindefense.sim.Game#DT} steps (capped per frame by {@link GameScreen#MAX_SIM_STEPS_PER_FRAME}),
 * updates the views and requests one repaint; Swing merges repaint requests, so each frame is painted once.
 */
public class LindefenseProgram extends GraphicsProgram {
    private static final long serialVersionUID = 1L;
    private static final int FRAME_MS = 16;

    private final ScaledLayer root = new ScaledLayer();
    private MenuScreen menu;
    private MapSelectScreen mapSelect;
    private CatalogScreen catalog;
    private GameScreen gameScreen;
    private long lastNanos;
    private Timer timer;
    private DemoDriver demo;

    @Override public void init() {
        Rectangle b = GraphicsEnvironment.getLocalGraphicsEnvironment().getMaximumWindowBounds();
        int w = (int) Math.min(1600, b.width * 0.92);
        int h = (int) Math.min(1000 + 28, b.height * 0.92);
        // keep the 1.6 aspect ratio of the logical layout
        if (w / 1.6 > h) w = (int) (h * 1.6); else h = (int) (w / 1.6) + 28;
        setSize(w, h);
        setTitle("Lindefense - The Last Line of Code");
        setBackground(Ui.BG);
    }

    /**
     * Canvas settings shared by the game and the offscreen benchmark ({@code tools.PerfBench}):
     * <ul>
     *   <li>auto-repaint off: the frame loop repaints once per frame instead of on every GObject mutation;</li>
     *   <li>native arcs on: {@code GOval} / {@code GArc} are painted with Java2D's curve-based arcs instead of ACM's
     *       fallback {@code ArcRenderer}, which converts every oval into an integer polygon of about
     *       {@code 2 * PI * diameter} vertices (190 for a 30 px enemy, 600+ for a range ring) that then has to be
     *       anti-aliased and stroked vertex by vertex. Profiling showed that fallback alone was about 70% of frame time
     *       in large fights.</li>
     * </ul>
     */
    public static void configureCanvas(GCanvas canvas) {
        canvas.setAutoRepaintFlag(false);
        canvas.setNativeArcFlag(true);
    }

    @Override public void run() {
        GCanvas canvas = getGCanvas();
        canvas.setBackground(Ui.BG);
        configureCanvas(canvas);
        Window win = SwingUtilities.getWindowAncestor(canvas);
        if (win instanceof JFrame) {
            JFrame f = (JFrame) win;
            f.setResizable(true);
            f.setMinimumSize(new Dimension(640, 420));
            installIcon(f);
        }
        add(root);
        root.fit(canvas.getWidth(), canvas.getHeight());
        canvas.addComponentListener(new ComponentAdapter() {
            @Override public void componentResized(ComponentEvent e) {
                root.fit(canvas.getWidth(), canvas.getHeight());
                canvas.repaint();
            }
        });
        addMouseListeners();
        addKeyListeners();
        lindefense.audio.AudioManager.install();   // AUDIO HOOK: preload SFX / open output on a background thread
        showMenu();
        String demoDir = System.getProperty("lindefense.demo");
        if (demoDir != null) demo = new DemoDriver(this, demoDir);
        lastNanos = System.nanoTime();
        timer = new Timer(FRAME_MS, e -> frame());
        timer.setCoalesce(true);
        timer.start();
    }

    private void frame() {
        long now = System.nanoTime();
        double dt = Math.min(0.1, (now - lastNanos) / 1e9);
        lastNanos = now;
        GCanvas canvas = getGCanvas();
        if (canvas.getWidth() > 0 && (Math.abs(root.getScale() - Math.min(canvas.getWidth() / (double) Ui.W, canvas.getHeight() / (double) Ui.H)) > 1e-6)) {
            root.fit(canvas.getWidth(), canvas.getHeight());
        }
        if (gameScreen != null) gameScreen.frame(dt);
        else if (catalog != null) catalog.frame(dt);
        else if (menu != null && menu.isVisible()) menu.frame(dt);
        else if (mapSelect != null) mapSelect.frame(dt);
        if (demo != null) demo.frame(dt);
        canvas.repaint();
    }

    // ------------------------------------------------------------------ screens
    private void clearScreens() {
        root.removeAll();
        gameScreen = null;
        catalog = null;
    }

    public void showMenu() {
        clearScreens();
        menu = new MenuScreen(this);
        root.add(menu);
        lindefense.audio.AudioManager.menuMusic();   // AUDIO HOOK
        getGCanvas().repaint();
    }

    public void showMapSelect() {
        clearScreens();
        menu = null;
        mapSelect = new MapSelectScreen(this);
        root.add(mapSelect);
        lindefense.audio.AudioManager.menuMusic();   // AUDIO HOOK
        getGCanvas().repaint();
    }

    public void startGame(int mapIndex) {
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
        Game g = new Game(MapCatalog.create(mapIndex), System.nanoTime(), lindefense.sim.Difficulty.getSelected());   // DIFFICULTY HOOK
        g.setHeroCollection(lindefense.sim.HeroCollection.persistent());   // Hero Store unlocks persist across sessions
        g.setAdmin(lindefense.sim.AdminMode.isOn(lindefense.sim.AdminMode.Option.UNLOCK_HEROES),   // SETTINGS > ADMIN CODE checklist
            lindefense.sim.AdminMode.isOn(lindefense.sim.AdminMode.Option.INFINITE_MONEY),
            lindefense.sim.AdminMode.isOn(lindefense.sim.AdminMode.Option.INFINITE_HEALTH));
        startGame(g);
    }

    /**
     * TUTORIAL (main menu): a guided match on the first map at the default difficulty. It uses an in-memory hero
     * collection, so practice unlocks never touch the saved Hero Store progress.
     */
    public void startTutorial() {
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
        Game g = new Game(MapCatalog.create(0), System.nanoTime(), lindefense.sim.Difficulty.O1);
        startGame(g, true);
    }

    /** CATALOG (main menu): every enemy, tower and hero. */
    public void showCatalog() {
        clearScreens();
        menu = null;
        mapSelect = null;
        catalog = new CatalogScreen(this);
        root.add(catalog);
        getGCanvas().repaint();
    }

    /** RESTART: throws the running level away and starts a fresh game on the same map and difficulty. */
    public void restartLevel() {
        if (gameScreen == null) return;
        startGame(Game.freshCopy(gameScreen.getGame()));
    }

    /** QUIT LEVEL: abandons the running level and returns to the map / difficulty select screen. */
    public void quitLevel() { showMapSelect(); }

    private void startGame(Game game) { startGame(game, false); }

    private void startGame(Game game, boolean tutorial) {
        clearScreens();
        menu = null;
        mapSelect = null;
        gameScreen = new GameScreen(this, game, tutorial);
        root.add(gameScreen);
        getGCanvas().requestFocusInWindow();
        getGCanvas().repaint();
    }

    /** Renders the emblem to an image and uses it as the window / dock icon (best effort). */
    private void installIcon(JFrame f) {
        try {
            int n = 128;
            java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(n, n, java.awt.image.BufferedImage.TYPE_INT_ARGB);
            java.awt.Graphics2D g2 = img.createGraphics();
            Cyber.quality(g2);
            g2.translate(n / 2.0, n / 2.0);
            LogoEmblem e = new LogoEmblem(n * 0.9);
            e.animate(0.4);
            e.paint(g2);
            g2.dispose();
            f.setIconImage(img);
            if (java.awt.Taskbar.isTaskbarSupported() && java.awt.Taskbar.getTaskbar().isSupported(java.awt.Taskbar.Feature.ICON_IMAGE)) {
                java.awt.Taskbar.getTaskbar().setIconImage(img);
            }
        } catch (Exception | Error ignored) {
            // icons are cosmetic; never fail startup over them
        }
    }

    public void quit() {
        if (timer != null) timer.stop();
        exit();
    }

    // ------------------------------------------------------------------ input
    @Override public void mousePressed(MouseEvent e) {
        getGCanvas().requestFocusInWindow();
        double lx = root.toLogicalX(e.getX()), ly = root.toLogicalY(e.getY());
        boolean right = SwingUtilities.isRightMouseButton(e) || e.isControlDown();
        if (gameScreen != null) gameScreen.mousePressed(lx, ly, right);
        else if (catalog != null) catalog.mousePressed(lx, ly);
        else if (mapSelect != null) mapSelect.mousePressed(lx, ly);
        else if (menu != null) menu.mousePressed(lx, ly);
        getGCanvas().repaint();
    }

    @Override public void mouseMoved(MouseEvent e) {
        double lx = root.toLogicalX(e.getX()), ly = root.toLogicalY(e.getY());
        if (gameScreen != null) gameScreen.mouseMoved(lx, ly);
        else if (catalog != null) catalog.mouseMoved(lx, ly);
        else if (mapSelect != null) mapSelect.mouseMoved(lx, ly);
        else if (menu != null) menu.mouseMoved(lx, ly);
    }

    @Override public void mouseDragged(MouseEvent e) { mouseMoved(e); }

    @Override public void keyPressed(KeyEvent e) {
        // SETTINGS text entry gets every key first (so typing M or N doesn't toggle the audio)
        if (gameScreen == null && catalog == null && menu != null && menu.isTyping()) { menu.keyPressed(e); return; }
        // AUDIO HOOK: M toggles music, N toggles sound, on every screen
        lindefense.audio.AudioManager am = lindefense.audio.AudioManager.get();
        if (am != null && (e.getKeyCode() == KeyEvent.VK_M || e.getKeyCode() == KeyEvent.VK_N)) {
            if (e.getKeyCode() == KeyEvent.VK_M) am.toggleMusic(); else am.toggleSound();
            return;
        }
        if (gameScreen != null) gameScreen.keyPressed(e);
        else if (catalog != null) catalog.keyPressed(e);
        else if (e.getKeyCode() == KeyEvent.VK_ESCAPE && mapSelect != null) showMenu();
        else if (menu != null) menu.skipIntro();
    }

    /** Exposed for tests / tooling. */
    public ScaledLayer getRoot() { return root; }
    public GameScreen getGameScreen() { return gameScreen; }
    public CatalogScreen getCatalog() { return catalog; }
    public Game getGame() { return gameScreen == null ? null : gameScreen.getGame(); }
    public Color getBackgroundColor() { return Ui.BG; }
}
