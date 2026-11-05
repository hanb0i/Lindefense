package lindefense.ui;

import java.awt.Dimension;
import java.awt.Frame;
import java.awt.GraphicsConfiguration;
import java.awt.GraphicsEnvironment;
import java.awt.Insets;
import java.awt.Rectangle;
import java.awt.Toolkit;
import java.awt.Window;
import lindefense.sim.Game;
import lindefense.sim.WindowLink;

/**
 * Palantir's fourth-wall break (phase 3, System Takeover): when the simulation asks for a grab
 * ({@link WindowLink#requestGrab}) this smoothly shrinks the real game window to {@link #SHRINK} of its size before
 * the takeover and drifts it a little, then reports the window's size back to the simulation every frame
 * ({@link Game#setWindowFraction}). While the window stays below {@link WindowLink#SEAL_THRESHOLD} of its old size
 * Palantir is sealed; the player breaks the seal by dragging the window bigger. When Palantir dies, the match ends or
 * the player leaves the game screen, the window is given back its old size.
 *
 * <h3>Safety</h3>
 * <ul>
 *   <li>Only ever calls {@link Window#setBounds}: never full screen, never maximised, never below the window's minimum
 *       size ({@value #MIN_W}x{@value #MIN_H}), always clamped inside the visible bounds of the window's screen.</li>
 *   <li>Animates over {@value #ANIM_SECONDS} s of real time and stops at once if the player starts resizing.</li>
 *   <li>Does nothing when the window is maximised, minimised or full screen, when SETTINGS > WINDOW EFFECTS is off, and in
 *       headless runs, tests and the scripted demo ({@link #create} returns an inert instance there).</li>
 * </ul>
 * The geometry is in pure static helpers ({@link #plan}, {@link #fraction}, {@link #clampToScreen}) so it can be
 * tested headlessly without a window.
 */
public final class WindowGrab {
    /** Target size as a fraction of the window's size before the takeover. */
    public static final double SHRINK = 0.72;
    /** Drift of the grabbed window, as a fraction of the screen size (x, y). */
    public static final double DRIFT_X = 0.04, DRIFT_Y = 0.03;
    /** Seconds (real time) the shrink and the release take. */
    public static final double ANIM_SECONDS = 1.5;
    /** The game's minimum window size (also set on the frame by {@code LindefenseProgram}). */
    public static final int MIN_W = 640, MIN_H = 420;

    private final Window window;
    private Game game;
    private Rectangle baseline;
    private Rectangle from, to, lastSet;
    private double anim = -1;
    private boolean holding, releasing;
    private int driftSign = 1;
    private int grabs;

    private WindowGrab(Window window) { this.window = window; }

    /**
     * The controller for the game window, or an inert one (it never touches any window) when {@code w} is null, the
     * run is headless, or this is the scripted demo ({@code demo} true or {@code -Dlindefense.demo} set).
     */
    public static WindowGrab create(Window w, boolean demo) {
        return new WindowGrab(w != null && !demo && environmentAllows() ? w : null);
    }

    /** False in headless runs, the scripted demo and with {@code -Dlindefense.windowfx=false}. */
    public static boolean environmentAllows() {
        if (GraphicsEnvironment.isHeadless()) return false;
        if (System.getProperty("lindefense.demo") != null) return false;
        return !"false".equalsIgnoreCase(System.getProperty(WindowEffects.PROPERTY));
    }

    /** True if this instance may ever move or resize a window. */
    public boolean isActive() { return window != null; }
    /** True while it holds the window (between a grab and the end of the release). */
    public boolean isHolding() { return holding; }
    /** Grabs performed so far. */
    public int getGrabs() { return grabs; }

    // ------------------------------------------------------------------ per frame (event thread)
    /** Called once per frame with the running match (or null off the game screen) and the real frame time. */
    public void frame(double dt, Game g) {
        if (window == null) return;
        if (g != game) {   // a new match, or the game screen was left
            if (holding) startRelease();
            game = g;
        }
        if (g == null) { step(dt); return; }
        WindowLink link = g.getWindowLink();
        int requests = link.consumeGrabRequests();
        boolean active = link.isTakeoverActive() && g.getState() == Game.State.PLAYING;
        if (!WindowEffects.isEnabled()) {
            if (holding) startRelease();
            step(dt);
            g.setWindowFraction(1.0);
            return;
        }
        if (active && requests > 0) grab(g);
        if (holding && !releasing && !active) startRelease();
        step(dt);
        g.setWindowFraction(holding && !releasing && baseline != null ? fraction(window.getSize(), baseline.getSize()) : 1.0);
    }

    private void grab(Game g) {
        if (!window.isShowing()) return;
        if (isMaximizedOrFullScreen()) {
            g.setBanner("PALANTIR REACHED FOR YOUR WINDOW  -  blocked: it is maximized", 0x7fd8a8, 3);
            return;
        }
        Rectangle cur = window.getBounds();
        if (!holding || releasing) baseline = new Rectangle(cur);
        Rectangle target = plan(cur, baseline, usableScreen(), minSize(), driftSign);
        driftSign = -driftSign;
        holding = true;
        releasing = false;
        grabs++;
        if (target.width < cur.width - 2 || target.height < cur.height - 2) {
            animate(cur, target);
            g.setBanner("PALANTIR HAS TAKEN YOUR WINDOW  -  drag it back to break the seal", 0xff4d4d, 4);
        }
    }

    private void startRelease() {
        if (!holding) return;
        releasing = true;
        Rectangle cur = window.getBounds();
        if (baseline == null || isMaximizedOrFullScreen() || cur.width >= baseline.width && cur.height >= baseline.height) { finish(); return; }
        Rectangle back = new Rectangle(baseline.x, baseline.y, Math.max(cur.width, baseline.width), Math.max(cur.height, baseline.height));
        animate(cur, clampToScreen(back, usableScreen(), minSize()));
    }

    private void finish() {
        holding = false;
        releasing = false;
        baseline = null;
        anim = -1;
        lastSet = null;
    }

    private void animate(Rectangle a, Rectangle b) {
        from = new Rectangle(a);
        to = new Rectangle(b);
        anim = 0;
        lastSet = null;
    }

    private void step(double dt) {
        if (anim < 0) return;
        Rectangle now = window.getBounds();
        if (lastSet != null && (Math.abs(now.width - lastSet.width) > 4 || Math.abs(now.height - lastSet.height) > 4)) {
            anim = -1;   // the player grabbed the window edge: let go at once
            lastSet = null;
            if (releasing) finish();
            return;
        }
        anim = Math.min(1, anim + Math.max(0, dt) / ANIM_SECONDS);
        Rectangle r = lerp(from, to, ease(anim));
        window.setBounds(r);
        lastSet = r;
        if (anim >= 1) {
            anim = -1;
            lastSet = null;
            if (releasing) finish();
        }
    }

    /** Maximised, minimised (iconified) or full screen: the grab leaves such a window alone. */
    private boolean isMaximizedOrFullScreen() {
        if (window instanceof Frame && (((Frame) window).getExtendedState() & (Frame.MAXIMIZED_BOTH | Frame.ICONIFIED)) != 0) return true;
        GraphicsConfiguration gc = window.getGraphicsConfiguration();
        if (gc == null) return false;
        if (gc.getDevice().getFullScreenWindow() == window) return true;
        Rectangle sb = gc.getBounds();
        return window.getWidth() >= sb.width && window.getHeight() >= sb.height;   // native full screen covers the whole display
    }

    private Dimension minSize() {
        Dimension m = window.getMinimumSize();
        return new Dimension(Math.max(MIN_W, m == null ? 0 : m.width), Math.max(MIN_H, m == null ? 0 : m.height));
    }

    /** Visible bounds of the window's screen (minus menu bar / dock / taskbar), falling back to the default screen. */
    private Rectangle usableScreen() {
        GraphicsConfiguration gc = window.getGraphicsConfiguration();
        if (gc != null) {
            Rectangle b = new Rectangle(gc.getBounds());
            try {
                Insets in = Toolkit.getDefaultToolkit().getScreenInsets(gc);
                b = new Rectangle(b.x + in.left, b.y + in.top, b.width - in.left - in.right, b.height - in.top - in.bottom);
            } catch (RuntimeException ignored) { /* keep the full bounds */ }
            return b;
        }
        return GraphicsEnvironment.getLocalGraphicsEnvironment().getMaximumWindowBounds();
    }

    // ------------------------------------------------------------------ pure geometry (tested headlessly)
    /**
     * Where a grab moves the window: {@link #SHRINK} of the pre-takeover size (never below {@code min}, never larger than
     * the screen), centred where the window is now, drifted by {@link #DRIFT_X} / {@link #DRIFT_Y} of the screen in the
     * direction {@code driftSign} (+1 right-down, -1 left-up), and clamped inside {@code screen}.
     */
    public static Rectangle plan(Rectangle current, Rectangle baseline, Rectangle screen, Dimension min, int driftSign) {
        int w = (int) Math.round(baseline.width * SHRINK), h = (int) Math.round(baseline.height * SHRINK);
        double cx = current.getCenterX() + driftSign * screen.width * DRIFT_X;
        double cy = current.getCenterY() + driftSign * screen.height * DRIFT_Y;
        Rectangle r = new Rectangle((int) Math.round(cx - w / 2.0), (int) Math.round(cy - h / 2.0), w, h);
        return clampToScreen(r, screen, min);
    }

    /** {@code r} with its size kept between {@code min} and the screen, moved so it lies inside {@code screen}. */
    public static Rectangle clampToScreen(Rectangle r, Rectangle screen, Dimension min) {
        int w = Math.min(Math.max(r.width, min.width), Math.max(min.width, screen.width));
        int h = Math.min(Math.max(r.height, min.height), Math.max(min.height, screen.height));
        int x = Math.max(screen.x, Math.min(r.x, screen.x + screen.width - w));
        int y = Math.max(screen.y, Math.min(r.y, screen.y + screen.height - h));
        return new Rectangle(x, y, w, h);
    }

    /** The window's size relative to its pre-takeover size: the smaller of the width and height ratios. */
    public static double fraction(Dimension current, Dimension baseline) {
        if (baseline == null || baseline.width <= 0 || baseline.height <= 0) return 1.0;
        return Math.min(current.width / (double) baseline.width, current.height / (double) baseline.height);
    }

    /** Linear interpolation of two rectangles. */
    public static Rectangle lerp(Rectangle a, Rectangle b, double t) {
        return new Rectangle((int) Math.round(a.x + (b.x - a.x) * t), (int) Math.round(a.y + (b.y - a.y) * t),
            (int) Math.round(a.width + (b.width - a.width) * t), (int) Math.round(a.height + (b.height - a.height) * t));
    }

    /** Smooth ease-in-out on [0, 1]. */
    public static double ease(double t) {
        t = Math.max(0, Math.min(1, t));
        return t * t * (3 - 2 * t);
    }
}
