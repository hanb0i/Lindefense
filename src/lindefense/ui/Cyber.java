package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.GraphicsEnvironment;
import java.awt.RenderingHints;
import java.awt.Shape;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;
import java.awt.geom.Path2D;
import java.awt.geom.Rectangle2D;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * Cyberpunk UI toolkit: palette, font fallback chains, number formatting, Java2D
 * quality hints and a handful of custom ACM objects that paint with real strokes
 * (chamfered glow frames, progress bars, rings, vector icons, glitch text).
 * Every object is built once and mutated per frame (setters only change fields).
 */
public final class Cyber {
    private Cyber() { }

    // ------------------------------------------------------------------ palette
    public static final Color CYAN = new Color(0x00f0ff);
    public static final Color MAGENTA = new Color(0xff2bd6);
    public static final Color YELLOW = new Color(0xffe94a);
    public static final Color RED = new Color(0xff3b4e);
    public static final Color GREEN = new Color(0x3bff8a);
    public static final Color INK = new Color(0x05070f);
    /** Dark-glass panel fill (translucent near-black navy). */
    public static final Color GLASS = new Color(8, 13, 30, 226);
    public static final Color GLASS_DEEP = new Color(4, 7, 18, 236);
    public static final Color TEXT = new Color(0xe4f8ff);
    public static final Color MUTED = new Color(0x8aa0bd);
    public static final Color DIM = new Color(0x5a6d88);
    public static final Color LINE = new Color(0x1d3a55);

    public static Color alpha(Color c, int a) { return new Color(c.getRed(), c.getGreen(), c.getBlue(), Math.max(0, Math.min(255, a))); }

    public static Color lerp(Color a, Color b, double f) {
        f = Math.max(0, Math.min(1, f));
        return new Color(
            (int) Math.round(a.getRed() + (b.getRed() - a.getRed()) * f),
            (int) Math.round(a.getGreen() + (b.getGreen() - a.getGreen()) * f),
            (int) Math.round(a.getBlue() + (b.getBlue() - a.getBlue()) * f),
            (int) Math.round(a.getAlpha() + (b.getAlpha() - a.getAlpha()) * f));
    }

    /** Green (full) to yellow to red (empty). */
    public static Color hpColor(double f) {
        return f > 0.5 ? lerp(YELLOW, GREEN, (f - 0.5) * 2) : lerp(RED, YELLOW, f * 2);
    }

    /** Sets a GLabel colour only when it changed (avoids needless repaint requests). */
    public static void setColor(GLabel l, Color c) { if (!c.equals(l.getColor())) l.setColor(c); }

    public static void setText(GLabel l, String s) { if (!s.equals(l.getLabel())) l.setLabel(s); }

    // ------------------------------------------------------------------ fonts
    // Bundled SIL OFL fonts (assets/fonts): Rajdhani (techno display), Barlow (UI sans), IBM Plex Mono (numbers / readouts).
    // Loaded once with Font.createFont + registerFont from a path relative to the working dir / class output dir, or the
    // classpath; any missing file falls back to the matching logical font. All UI text goes through display/mono/body.
    private static final Map<String, Font> FONTS = new HashMap<>();
    private static final Map<String, Font> FILES = new HashMap<>();
    private static boolean loaded;

    public static final String VALORAX_FILE = "Valorax.otf";

    public static final String[] FONT_FILES = {
        "Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf", "Rajdhani-Bold.ttf",
        "Barlow-Regular.ttf", "Barlow-Medium.ttf", "Barlow-SemiBold.ttf", "Barlow-Bold.ttf",
        "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "IBMPlexMono-SemiBold.ttf", "IBMPlexMono-Bold.ttf",
        VALORAX_FILE };

    /**
     * Valorax (Makna Studio): the wide angular gaming face used for headings, buttons, tabs, names and tags. It is a
     * personal-use font, so the file is bundled locally and git-ignored; when it is absent everything falls back to
     * Rajdhani. It is uppercase-only (lowercase draws as small caps) and about 1.6x as wide as Rajdhani, so sizes are
     * scaled by {@link #VALORAX_SCALE} to keep existing layouts, with a floor so small text stays legible.
     */
    private static final double VALORAX_SCALE = 0.8;
    private static final int VALORAX_MIN = 11;
    private static final double MONO_SCALE = 0.9;

    private static synchronized void loadFonts() {
        if (loaded) return;
        loaded = true;
        java.util.List<java.io.File> dirs = new java.util.ArrayList<>();
        dirs.add(lindefense.Assets.file("assets/fonts"));   // working-directory independent lookup
        dirs.add(new java.io.File("assets/fonts"));
        dirs.add(new java.io.File(System.getProperty("user.dir", "."), "assets/fonts"));
        dirs.add(new java.io.File("../assets/fonts"));
        try {
            java.io.File code = new java.io.File(Cyber.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            java.io.File root = code.isDirectory() ? code.getParentFile() : code.getParentFile() == null ? null : code.getParentFile().getParentFile();
            if (root != null) dirs.add(new java.io.File(root, "assets/fonts"));
        } catch (Exception | Error ignored) {
            // code source unavailable: relative paths only
        }
        for (String name : FONT_FILES) {
            Font f = null;
            for (java.io.File d : dirs) {
                java.io.File file = new java.io.File(d, name);
                if (!file.isFile()) continue;
                try (java.io.InputStream in = new java.io.FileInputStream(file)) {
                    f = Font.createFont(Font.TRUETYPE_FONT, in);
                    break;
                } catch (Exception | Error ignored) {
                    // try the next location
                }
            }
            if (f == null) {
                try (java.io.InputStream in = Cyber.class.getResourceAsStream("/assets/fonts/" + name)) {
                    if (in != null) f = Font.createFont(Font.TRUETYPE_FONT, in);
                } catch (Exception | Error ignored) {
                    // fall through to logical fonts
                }
            }
            if (f != null) {
                FILES.put(name, f);
                try { GraphicsEnvironment.getLocalGraphicsEnvironment().registerFont(f); } catch (RuntimeException | Error ignored) { /* optional */ }
            }
        }
    }

    /**
     * Which face the display role uses: {@code mono} (IBM Plex Mono, default), {@code valorax} (personal-use font, needs
     * assets/fonts/Valorax.otf, falls back to Rajdhani when absent) or {@code rajdhani}. Switch with
     * {@code -Dlindefense.font=...}.
     */
    private static final String DISPLAY_FACE = System.getProperty("lindefense.font", "mono").toLowerCase();

    /** Display font (headings, buttons, tabs, names, tags): see {@link #DISPLAY_FACE}. */
    public static Font display(int style, int size) { return displayFont("V", style, size, 1.0, VALORAX_MIN); }

    /**
     * Compact display font for tight spots (tab strips, small chips): the same face at a smaller scale and a lower
     * size floor than {@link #display}.
     */
    public static Font displayCompact(int style, int size) { return displayFont("C", style, size, 0.94, 9); }

    private static Font displayFont(String kind, int style, int size, double compact, int floor) {
        String key = kind + DISPLAY_FACE + style + "/" + size;
        synchronized (Cyber.class) {
            Font f = FONTS.get(key);
            if (f != null) return f;
            loadFonts();
            if (DISPLAY_FACE.equals("valorax") && FILES.get(VALORAX_FILE) != null) {
                // uppercase-only, ~1.6x as wide as Rajdhani: scaled down to keep layouts
                f = FILES.get(VALORAX_FILE).deriveFont((float) Math.max(kind.equals("C") ? 9 : VALORAX_MIN, Math.round(size * (kind.equals("C") ? 0.75 : VALORAX_SCALE) * 2) / 2.0));
            } else if (DISPLAY_FACE.equals("mono")) {
                // IBM Plex Mono is ~1.4x as wide as Rajdhani: scaled down to keep layouts
                Font base = FILES.get((style & Font.BOLD) != 0 ? "IBMPlexMono-Bold.ttf" : "IBMPlexMono-Medium.ttf");
                f = base != null ? base.deriveFont((float) Math.max(floor, Math.round(size * MONO_SCALE * compact * 2) / 2.0)) : new Font(Font.MONOSPACED, style, Math.max(floor, (int) Math.round(size * MONO_SCALE * compact)));
            } else {
                f = font("D", "Rajdhani-Medium.ttf", "Rajdhani-Bold.ttf", Font.SANS_SERIF, style, size);
            }
            FONTS.put(key, f);
            return f;
        }
    }

    /** Monospace font for numbers and data readouts: IBM Plex Mono. */
    public static Font mono(int style, int size) { return font("M", "IBMPlexMono-Medium.ttf", "IBMPlexMono-Bold.ttf", Font.MONOSPACED, style, size); }
    /** Clean sans font for paragraph text: Barlow. */
    public static Font body(int style, int size) { return font("B", "Barlow-Regular.ttf", "Barlow-SemiBold.ttf", Font.SANS_SERIF, style, size); }

    private static synchronized Font font(String kind, String plain, String bold, String fallback, int style, int size) {
        String key = kind + style + "/" + size;
        Font f = FONTS.get(key);
        if (f == null) {
            loadFonts();
            Font base = FILES.get((style & Font.BOLD) != 0 ? bold : plain);
            f = base != null ? base.deriveFont((float) size) : new Font(fallback, style, size);
            FONTS.put(key, f);
        }
        return f;
    }

    // ------------------------------------------------------------------ number formatting
    public static String commas(long v) { return String.format("%,d", v); }

    public static String money(double v) { return "$" + commas((long) Math.floor(v)); }

    /** 1.2M / 845K / 9.5K / 640 (rounds up so a living boss never shows 0). */
    public static String abbrev(double v) {
        v = Math.ceil(Math.max(0, v));
        double a = v;
        String suf = "";
        if (a >= 1e9) { a /= 1e9; suf = "B"; }
        else if (a >= 1e6) { a /= 1e6; suf = "M"; }
        else if (a >= 1e3) { a /= 1e3; suf = "K"; }
        if (suf.isEmpty()) return String.valueOf((long) a);
        return a < 10 ? String.format("%.1f%s", a, suf) : String.format("%.0f%s", a, suf);
    }

    /** Upper-case readout text (the bundled mono / display faces are already wide and tracked enough). */
    public static String spaced(String s) { return s.toUpperCase(); }

    // ------------------------------------------------------------------ rendering
    /**
     * Applies the shared Java2D quality hints. The root layer sets them once per frame and every child Graphics
     * inherits them, so when they are already in effect this returns after a few cheap reads instead of re-setting
     * seven hints for every custom-painted object.
     */
    public static void quality(Graphics2D g2) {
        if (g2.getRenderingHint(RenderingHints.KEY_RENDERING) == RenderingHints.VALUE_RENDER_QUALITY
                && g2.getRenderingHint(RenderingHints.KEY_ANTIALIASING) == RenderingHints.VALUE_ANTIALIAS_ON
                && g2.getRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING) == RenderingHints.VALUE_TEXT_ANTIALIAS_ON
                && g2.getRenderingHint(RenderingHints.KEY_STROKE_CONTROL) == RenderingHints.VALUE_STROKE_PURE
                && g2.getRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS) == RenderingHints.VALUE_FRACTIONALMETRICS_ON
                && g2.getRenderingHint(RenderingHints.KEY_INTERPOLATION) == RenderingHints.VALUE_INTERPOLATION_BILINEAR
                && g2.getRenderingHint(RenderingHints.KEY_COLOR_RENDERING) == RenderingHints.VALUE_COLOR_RENDER_QUALITY) {
            return;
        }
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g2.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g2.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
        g2.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
        g2.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS, RenderingHints.VALUE_FRACTIONALMETRICS_ON);
        g2.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g2.setRenderingHint(RenderingHints.KEY_COLOR_RENDERING, RenderingHints.VALUE_COLOR_RENDER_QUALITY);
    }

    private static BasicStroke stroke(double w) { return new BasicStroke((float) w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND); }

    /** Rectangle with chamfered top-left and bottom-right corners (the title-card button silhouette). */
    public static Path2D chamfer(double x, double y, double w, double h, double c) {
        c = Math.max(0, Math.min(c, Math.min(w, h) / 2));
        Path2D.Double p = new Path2D.Double();
        p.moveTo(x + c, y);
        p.lineTo(x + w, y);
        p.lineTo(x + w, y + h - c);
        p.lineTo(x + w - c, y + h);
        p.lineTo(x, y + h);
        p.lineTo(x, y + c);
        p.closePath();
        return p;
    }

    // ------------------------------------------------------------------ custom objects
    /** Chamfered dark-glass frame: translucent fill, scanlines, layered glowing border, corner ticks. */
    public static final class Chamfer extends GObject {
        private static final long serialVersionUID = 1L;
        private double w, h, cut;
        private Color fill = GLASS, border = CYAN;
        private double glow;
        private double lineW = 1.4;
        private boolean scan = true;
        private boolean ticks;
        private float alpha = 1f;
        /** The scanline stripes as one path (one fill per frame instead of one per stripe), rebuilt when the frame moves or resizes. */
        private transient Path2D scanPath;
        private double scanX = Double.NaN, scanY, scanW, scanH;
        private static final Color SCANLINE = new Color(0, 0, 0, 52);

        private Path2D scanlines() {
            if (scanPath == null || scanX != getX() || scanY != getY() || scanW != w || scanH != h) {
                Path2D.Double sp = new Path2D.Double();
                for (double yy = getY() + 2; yy < getY() + h; yy += 3) sp.append(new Rectangle2D.Double(getX(), yy, w, 1), false);
                scanPath = sp;
                scanX = getX(); scanY = getY(); scanW = w; scanH = h;
            }
            return scanPath;
        }

        public Chamfer(double x, double y, double w, double h, double cut) {
            this.w = w; this.h = h; this.cut = cut;
            setLocation(x, y);
        }

        public Chamfer fill(Color c) { fill = c; return this; }
        public Chamfer border(Color c) { border = c; return this; }
        public Chamfer glow(double g) { glow = g; return this; }
        public Chamfer lineWidth(double lw) { lineW = lw; return this; }
        public Chamfer scan(boolean s) { scan = s; return this; }
        public Chamfer ticks(boolean t) { ticks = t; return this; }
        public Chamfer alpha(float a) { alpha = a; return this; }
        public Chamfer size(double nw, double nh) { w = nw; h = nh; return this; }
        public double getW() { return w; }
        public double getH() { return h; }

        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), w, h); }

        @Override public void paint(Graphics g) {
            if (alpha <= 0.004f) return;
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                quality(g2);
                if (alpha < 1f) g2.setComposite(AlphaComposite.SrcOver.derive(alpha));
                double in = lineW / 2;
                Path2D p = chamfer(getX() + in, getY() + in, w - lineW, h - lineW, cut);
                if (fill != null && fill.getAlpha() > 0) { g2.setColor(fill); g2.fill(p); }
                if (scan && fill != null) {
                    Shape oldClip = g2.getClip();
                    g2.clip(p);
                    g2.setColor(SCANLINE);
                    g2.fill(scanlines());
                    g2.setClip(oldClip);
                }
                if (border != null) {
                    int ba = border.getAlpha();
                    if (glow > 0.01) {
                        for (int i = 3; i >= 1; i--) {
                            g2.setStroke(stroke(lineW + i * 2.2));
                            g2.setColor(Cyber.alpha(border, (int) (ba * glow * (0.20 - 0.05 * i))));
                            g2.draw(p);
                        }
                    }
                    g2.setStroke(stroke(lineW));
                    g2.setColor(border);
                    g2.draw(p);
                    if (ticks) {
                        // bright corner ticks on the two square corners
                        g2.setStroke(stroke(lineW + 1.2));
                        g2.setColor(lerp(border, Color.WHITE, 0.55));
                        double x0 = getX() + in, y0 = getY() + in, x1 = getX() + w - in, y1 = getY() + h - in, t = Math.min(12, Math.min(w, h) / 3);
                        g2.draw(new Line2D.Double(x1 - t, y0, x1, y0));
                        g2.draw(new Line2D.Double(x1, y0, x1, y0 + t));
                        g2.draw(new Line2D.Double(x0, y1 - t, x0, y1));
                        g2.draw(new Line2D.Double(x0, y1, x0 + t, y1));
                    }
                }
            } finally {
                g2.dispose();
            }
        }
    }

    /** Ellipse with fill and a crisp outline of arbitrary width (optionally dashed). */
    public static final class Ring extends GObject {
        private static final long serialVersionUID = 1L;
        private double w, h;
        private Color fill, line;
        private double lineW = 1.6;
        private boolean dashed;
        private double dashPhase;

        public Ring(double x, double y, double w, double h, Color fill, Color line) {
            this.w = w; this.h = h; this.fill = fill; this.line = line;
            setLocation(x, y);
        }

        public void set(double cx, double cy, double r) { w = h = 2 * r; setLocation(cx - r, cy - r); }
        public void setFill(Color c) { fill = c; }
        public void setLine(Color c) { line = c; }
        public void setLineWidth(double lw) { lineW = lw; }
        public void setDashed(boolean d) { dashed = d; }
        public void setPhase(double p) { dashPhase = p; }

        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), w, h); }

        @Override public void paint(Graphics g) {
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                quality(g2);
                Ellipse2D e = new Ellipse2D.Double(getX() + lineW / 2, getY() + lineW / 2, w - lineW, h - lineW);
                if (fill != null) { g2.setColor(fill); g2.fill(e); }
                if (line != null) {
                    g2.setStroke(dashed
                        ? new BasicStroke((float) lineW, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 10f, 7f }, (float) dashPhase)
                        : stroke(lineW));
                    g2.setColor(line);
                    g2.draw(e);
                }
            } finally {
                g2.dispose();
            }
        }
    }

    /** Progress bar with dark backing, outline, optional chamfered ends, trailing "recent damage" chunk and notches. */
    public static final class Bar extends GObject {
        private static final long serialVersionUID = 1L;
        private double w, h, cut;
        private double value = 1, trail = 1, holdTimer;
        private Color fill = GREEN, back = new Color(0, 0, 0, 190), outline = new Color(0, 0, 0, 230), trailColor = new Color(255, 255, 255, 200);
        private double[] notches = new double[0];
        private boolean useTrail;
        private double lineW = 1;

        public Bar(double x, double y, double w, double h, double cut) {
            this.w = w; this.h = h; this.cut = cut;
            setLocation(x, y);
        }

        public Bar colors(Color fill, Color back, Color outline) { this.fill = fill; this.back = back; this.outline = outline; return this; }
        public Bar trail(boolean t, Color c) { useTrail = t; if (c != null) trailColor = c; return this; }
        public Bar notches(double... n) { notches = n; return this; }
        public Bar lineWidth(double lw) { lineW = lw; return this; }
        public void setFill(Color c) { fill = c; }
        public void setValue(double v) {
            v = Math.max(0, Math.min(1, v));
            if (v < value - 1e-9) holdTimer = 0.45;
            value = v;
            if (!useTrail || v > trail) trail = v;
        }
        public double getValue() { return value; }
        public void setSize(double nw, double nh) { w = nw; h = nh; }

        /** Eases the trailing chunk toward the live value. */
        public void step(double dt) {
            if (!useTrail || trail <= value) return;
            if (holdTimer > 0) { holdTimer -= dt; return; }
            trail = Math.max(value, trail - dt * Math.max(0.25, (trail - value) * 2.0));
        }

        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), w, h); }

        /**
         * Reduced bar for crowded screens (the world view's level of detail, see
         * {@link lindefense.ui.sprites.Thick#setLevel}): backing and value only, plus the outline at level 1. Two or
         * three fills instead of six plus a clip; plain enemy HP bars only (no chamfer, trail or notches).
         */
        private void paintSimple(Graphics2D g2, int lod) {
            Color old = g2.getColor();
            double x = getX(), y = getY();
            g2.setColor(back);
            g2.fill(new Rectangle2D.Double(x, y, w, h));
            double fw = (w - 2 * lineW) * value;
            if (fw > 0.3) {
                g2.setColor(fill);
                g2.fill(new Rectangle2D.Double(x + lineW, y, fw, h));
            }
            if (lod < 2 && outline != null) {
                java.awt.Stroke os = g2.getStroke();
                g2.setStroke(stroke(Math.max(1, lineW)));
                g2.setColor(outline);
                g2.draw(new Rectangle2D.Double(x + 0.5, y + 0.5, w - 1, h - 1));
                g2.setStroke(os);
            }
            g2.setColor(old);
        }

        @Override public void paint(Graphics g) {
            int lod = lindefense.ui.sprites.Thick.level();
            if (lod > 0 && cut <= 0 && !useTrail && notches.length == 0) { paintSimple((Graphics2D) g, lod); return; }
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                quality(g2);
                double x = getX(), y = getY();
                Shape shape = cut > 0 ? chamfer(x, y, w, h, cut) : new Rectangle2D.Double(x, y, w, h);
                g2.setColor(back);
                g2.fill(shape);
                Shape old = g2.getClip();
                g2.clip(shape);
                double inner = lineW;
                double fw = (w - 2 * inner) * value;
                if (useTrail && trail > value) {
                    g2.setColor(trailColor);
                    g2.fill(new Rectangle2D.Double(x + inner + fw, y, (w - 2 * inner) * (trail - value), h));
                }
                if (fw > 0.3) {
                    g2.setColor(fill);
                    g2.fill(new Rectangle2D.Double(x + inner, y, fw, h));
                    g2.setColor(new Color(255, 255, 255, 62));
                    g2.fill(new Rectangle2D.Double(x + inner, y, fw, Math.max(1, h * 0.38)));
                    g2.setColor(new Color(0, 0, 0, 55));
                    g2.fill(new Rectangle2D.Double(x + inner, y + h * 0.72, fw, h * 0.28));
                }
                g2.setColor(new Color(0, 0, 0, 200));
                for (double n : notches) g2.fill(new Rectangle2D.Double(x + inner + (w - 2 * inner) * n - 1, y, 2, h));
                g2.setClip(old);
                if (outline != null) {
                    g2.setStroke(stroke(Math.max(1, lineW)));
                    g2.setColor(outline);
                    g2.draw(cut > 0 ? chamfer(x + 0.5, y + 0.5, w - 1, h - 1, cut) : new Rectangle2D.Double(x + 0.5, y + 0.5, w - 1, h - 1));
                }
            } finally {
                g2.dispose();
            }
        }
    }

    /**
     * GLabel whose width / ascent are measured with a fractional-metrics, anti-aliased FontRenderContext and which draws with
     * the same context at sub-pixel positions, so centring, right-alignment and fitting match what is painted at any scale.
     */
    public static final class Text extends GLabel {
        private static final long serialVersionUID = 1L;
        private static final java.awt.font.FontRenderContext FRC = new java.awt.font.FontRenderContext(null, true, true);

        public Text(String s) { super(s); }
        public Text(String s, double x, double y) { super(s, x, y); }

        @Override public double getWidth() { return getFont().getStringBounds(getLabel(), FRC).getWidth(); }
        @Override public double getAscent() { return getFont().getLineMetrics("Ag", FRC).getAscent(); }
        @Override public double getDescent() { return getFont().getLineMetrics("Ag", FRC).getDescent(); }
        @Override public double getHeight() { return getAscent() + getDescent(); }
        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY() - getAscent(), getWidth(), getHeight()); }

        @Override public void paint(Graphics g) {
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                quality(g2);
                g2.setFont(getFont());
                g2.setColor(getColor());
                g2.drawString(getLabel(), (float) getX(), (float) getY());
            } finally {
                g2.dispose();
            }
        }
    }

    /** Vector glyphs for HUD chips and buttons. */
    public enum Kind { PLAY, PAUSE, CASH, HEART, WAVE, ENEMY, AUTO, MENU, FAST, CHECK, SKULL, SPEAKER, NOTE }

    /** A small flat vector icon, size x size, drawn at its location (top-left). */
    public static class Icon extends GObject {
        private static final long serialVersionUID = 1L;
        private Kind kind;
        private final double size;
        private Color color;

        public Icon(Kind kind, double size, Color color) { this.kind = kind; this.size = size; this.color = color; }

        private boolean struck;

        public void setKind(Kind k) { kind = k; }
        /** Draws a diagonal strike-through (used by the Sound / Music "off" state). */
        public void setStruck(boolean s) { struck = s; }
        public void setIconColor(Color c) { color = c; }

        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), size, size); }

        @Override public void paint(Graphics g) {
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                quality(g2);
                g2.translate(getX(), getY());
                g2.scale(size / 16.0, size / 16.0);
                g2.setColor(color);
                g2.setStroke(new BasicStroke(1.7f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                switch (kind) {
                    case PLAY: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(3.5, 2); p.lineTo(13.5, 8); p.lineTo(3.5, 14); p.closePath();
                        g2.fill(p);
                        break;
                    }
                    case PAUSE:
                        g2.fill(new Rectangle2D.Double(3.5, 2.5, 3.2, 11));
                        g2.fill(new Rectangle2D.Double(9.3, 2.5, 3.2, 11));
                        break;
                    case FAST: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(1.5, 3); p.lineTo(8, 8); p.lineTo(1.5, 13); p.closePath();
                        p.moveTo(8, 3); p.lineTo(14.5, 8); p.lineTo(8, 13); p.closePath();
                        g2.fill(p);
                        break;
                    }
                    case CASH: {
                        Path2D hex = new Path2D.Double();
                        hex.moveTo(8, 1); hex.lineTo(14, 4.5); hex.lineTo(14, 11.5); hex.lineTo(8, 15); hex.lineTo(2, 11.5); hex.lineTo(2, 4.5); hex.closePath();
                        g2.draw(hex);
                        g2.fill(new Rectangle2D.Double(7.2, 4.2, 1.6, 7.6));
                        g2.draw(new Line2D.Double(5.6, 6.2, 10.4, 6.2));
                        g2.draw(new Line2D.Double(5.6, 9.8, 10.4, 9.8));
                        break;
                    }
                    case HEART: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(8, 14.2);
                        p.curveTo(1.5, 9.6, 0.6, 6.4, 2.2, 4.0);
                        p.curveTo(4.0, 1.6, 7.0, 2.6, 8, 5.0);
                        p.curveTo(9.0, 2.6, 12.0, 1.6, 13.8, 4.0);
                        p.curveTo(15.4, 6.4, 14.5, 9.6, 8, 14.2);
                        p.closePath();
                        g2.fill(p);
                        break;
                    }
                    case WAVE: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(1, 8);
                        p.curveTo(3, 1, 5, 1, 7, 8);
                        p.curveTo(9, 15, 11, 15, 15, 8);
                        g2.draw(p);
                        break;
                    }
                    case ENEMY: {
                        Path2D d = new Path2D.Double();
                        d.moveTo(8, 1.2); d.lineTo(14.8, 8); d.lineTo(8, 14.8); d.lineTo(1.2, 8); d.closePath();
                        g2.draw(d);
                        g2.fill(new Ellipse2D.Double(5.8, 5.8, 4.4, 4.4));
                        break;
                    }
                    case AUTO: {
                        g2.draw(new java.awt.geom.Arc2D.Double(2.2, 2.2, 11.6, 11.6, 40, 270, java.awt.geom.Arc2D.OPEN));
                        Path2D a = new Path2D.Double();
                        a.moveTo(13.6, 1.5); a.lineTo(13.6, 6.6); a.lineTo(8.8, 5.2); a.closePath();
                        g2.fill(a);
                        break;
                    }
                    case MENU:
                        for (int i = 0; i < 3; i++) g2.fill(new Rectangle2D.Double(2.5, 3 + i * 4.2, 11, 1.8));
                        break;
                    case CHECK: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(2.5, 8.5); p.lineTo(6.5, 12.5); p.lineTo(13.5, 3.5);
                        g2.draw(p);
                        break;
                    }
                    case SKULL:
                        g2.draw(new Ellipse2D.Double(2.5, 1.5, 11, 9.5));
                        g2.fill(new Ellipse2D.Double(5, 5, 2.2, 2.6));
                        g2.fill(new Ellipse2D.Double(8.8, 5, 2.2, 2.6));
                        g2.draw(new Line2D.Double(6, 14, 10, 14));
                        break;
                    case SPEAKER: {
                        Path2D p = new Path2D.Double();
                        p.moveTo(1.5, 5.8); p.lineTo(4.6, 5.8); p.lineTo(8.2, 2.6); p.lineTo(8.2, 13.4); p.lineTo(4.6, 10.2); p.lineTo(1.5, 10.2); p.closePath();
                        g2.fill(p);
                        g2.draw(new java.awt.geom.Arc2D.Double(6.2, 4.6, 5.0, 6.8, -60, 120, java.awt.geom.Arc2D.OPEN));
                        g2.draw(new java.awt.geom.Arc2D.Double(5.4, 2.4, 8.6, 11.2, -55, 110, java.awt.geom.Arc2D.OPEN));
                        break;
                    }
                    case NOTE:
                        g2.fill(new Ellipse2D.Double(2.6, 10.0, 4.8, 3.8));
                        g2.fill(new Ellipse2D.Double(9.2, 8.6, 4.8, 3.8));
                        g2.draw(new Line2D.Double(7.2, 11.4, 7.2, 2.8));
                        g2.draw(new Line2D.Double(13.8, 10.0, 13.8, 2.0));
                        g2.draw(new Line2D.Double(7.2, 2.8, 13.8, 2.0));
                        break;
                    default: break;
                }
                if (struck) {
                    g2.setStroke(new BasicStroke(3.4f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                    g2.setColor(new Color(0x0a1020));
                    g2.draw(new Line2D.Double(2.6, 1.6, 14.2, 14.4));
                    g2.setStroke(new BasicStroke(1.8f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                    g2.setColor(RED);
                    g2.draw(new Line2D.Double(2.6, 1.6, 14.2, 14.4));
                }
            } finally {
                g2.dispose();
            }
        }
    }

    /**
     * Text with a brief chromatic glitch flourish: magenta and cyan ghost copies jitter around the main
     * label for a short burst, then settle. Use {@link #burst(double)} to trigger it.
     */
    public static final class GlitchText extends GCompound {
        private static final long serialVersionUID = 1L;
        private final GLabel main, ghostA, ghostB;
        private final Random rnd = new Random();
        private double left;
        private double glyphAlpha = 1;
        private Color color = TEXT;

        public GlitchText(String text, Font font, Color color) {
            ghostA = new Text(text); ghostB = new Text(text); main = new Text(text);
            for (GLabel l : new GLabel[] { ghostA, ghostB, main }) { l.setFont(font); add(l); }
            ghostA.setColor(alpha(MAGENTA, 190)); ghostB.setColor(alpha(CYAN, 190));
            ghostA.setVisible(false); ghostB.setVisible(false);
            setColor(color);
        }

        @Override public void setColor(Color c) { color = c; applyAlpha(); }

        public void setAlphaFactor(double a) { glyphAlpha = a; applyAlpha(); }

        private void applyAlpha() {
            main.setColor(alpha(color, (int) (color.getAlpha() * glyphAlpha)));
            ghostA.setColor(alpha(MAGENTA, (int) (190 * glyphAlpha)));
            ghostB.setColor(alpha(CYAN, (int) (190 * glyphAlpha)));
        }

        public void setText(String s) {
            if (s.equals(main.getLabel())) return;
            main.setLabel(s); ghostA.setLabel(s); ghostB.setLabel(s);
        }

        public double textWidth() { return main.getWidth(); }
        public double textAscent() { return main.getAscent(); }

        /** Baseline-left placement of the main label inside this compound's own coordinates (0,0). */
        public void burst(double seconds) { left = seconds; }

        public void animate(double dt) {
            if (left > 0) {
                left -= dt;
                double j = 2 + rnd.nextDouble() * 5;
                ghostA.setLocation(-j, rnd.nextDouble() * 3 - 1.5);
                ghostB.setLocation(j, rnd.nextDouble() * 3 - 1.5);
                main.setLocation(left > 0.05 && rnd.nextDouble() < 0.25 ? rnd.nextDouble() * 6 - 3 : 0, 0);
                ghostA.setVisible(true); ghostB.setVisible(true);
                if (left <= 0) { ghostA.setVisible(false); ghostB.setVisible(false); main.setLocation(0, 0); }
            }
        }
    }
}
