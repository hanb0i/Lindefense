package lindefense.ui;

import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.GradientPaint;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.MultipleGradientPaint;
import java.awt.RadialGradientPaint;
import java.awt.RenderingHints;
import java.awt.Shape;
import java.awt.geom.AffineTransform;
import java.awt.geom.Arc2D;
import java.awt.geom.Area;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;
import java.awt.geom.Path2D;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.awt.geom.RoundRectangle2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import lindefense.map.AbandonedDataCenter;
import lindefense.map.GameMap;
import lindefense.map.HallucinationCanyon;
import lindefense.map.LegacyMonolith;
import lindefense.map.NeuralNetwork;
import lindefense.map.Obstacle;
import lindefense.map.Path;
import lindefense.map.SiliconCircuit;
import lindefense.map.SiliconValley;
import lindefense.map.SingularityCore;
import lindefense.sim.Vec;
import lindefense.ui.sprites.Thick;

/**
 * Detailed, futuristic map art (background, set dressing, track) as one ACM {@link GObject}.
 *
 * <p>The art is hundreds of Java2D shapes, so it is painted <b>once</b> into a bitmap at the resolution the object is
 * actually shown at (canvas scale x HiDPI scale) and every frame only blits that bitmap. The bitmap is re-rendered when
 * the window is resized and shared through a small cache, so the map-select thumbnails and the playfield cost nothing
 * per frame. Everything is deterministic (seeded per map) and only reads the map's static geometry: routes, obstacles,
 * pads, nodes. Set dressing is placed only where it keeps clear of the track and obstacles so it never hides gameplay.
 *
 * <p>{@link Pulses} is the small live layer: glowing data packets streaming along each route.
 */
public final class MapArt extends GObject {
    private static final long serialVersionUID = 1L;
    private static final double W = GameMap.WIDTH, H = GameMap.HEIGHT, HW = GameMap.TRACK_HALF_WIDTH;
    private static final double MAX_SCALE = 2.5;

    /** LRU of rendered bitmaps keyed by map name and pixel scale. */
    private static final Map<String, BufferedImage> CACHE = new LinkedHashMap<String, BufferedImage>(8, 0.75f, true) {
        private static final long serialVersionUID = 1L;
        @Override protected boolean removeEldestEntry(Map.Entry<String, BufferedImage> e) { return size() > 6; }
    };

    private final GameMap map;
    private final double dw, dh;
    private transient BufferedImage img;
    private double imgScale = -1;

    /** Full-size map art at the world origin. */
    public MapArt(GameMap map) { this(map, 0, 0, W, H); }

    /** Map art scaled into a {@code dw x dh} box at (x, y) (thumbnails). */
    public MapArt(GameMap map, double x, double y, double dw, double dh) {
        this.map = map; this.dw = dw; this.dh = dh;
        setLocation(x, y);
    }

    @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), dw, dh); }

    @Override public void paint(Graphics g) {
        Graphics2D g2 = (Graphics2D) g.create();
        try {
            AffineTransform t = g2.getTransform();
            double dev = Math.sqrt(Math.abs(t.getDeterminant()));
            double s = Math.min(MAX_SCALE, Math.max(0.125, Math.ceil(dev * dw / W * 8) / 8.0));
            if (img == null || s != imgScale) { img = bitmap(map, s); imgScale = s; }
            g2.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            AffineTransform at = new AffineTransform();
            at.translate(getX(), getY());
            at.scale(dw / img.getWidth(), dh / img.getHeight());
            g2.drawImage(img, at, null);
        } finally {
            g2.dispose();
        }
    }

    private static BufferedImage bitmap(GameMap map, double s) {
        String key = map.getName() + "@" + s;
        BufferedImage b = CACHE.get(key);
        if (b != null) return b;
        b = new BufferedImage((int) Math.ceil(W * s), (int) Math.ceil(H * s), BufferedImage.TYPE_INT_RGB);
        Graphics2D g = b.createGraphics();
        try {
            Cyber.quality(g);
            g.scale(s, s);
            g.clip(new Rectangle2D.Double(0, 0, W, H));
            render(g, map);
        } finally {
            g.dispose();
        }
        CACHE.put(key, b);
        return b;
    }

    /** Paints the full map art in world coordinates. */
    public static void render(Graphics2D g, GameMap map) {
        if (map instanceof SiliconCircuit) new Silicon((SiliconCircuit) map, g).draw();
        else if (map instanceof LegacyMonolith) new Monolith((LegacyMonolith) map, g).draw();
        else if (map instanceof HallucinationCanyon) new Canyon((HallucinationCanyon) map, g).draw();
        else if (map instanceof SingularityCore) new Singularity((SingularityCore) map, g).draw();
        else if (map instanceof SiliconValley) new Valley((SiliconValley) map, g).draw();
        else if (map instanceof NeuralNetwork) new Neural((NeuralNetwork) map, g).draw();
        else if (map instanceof AbandonedDataCenter) new Graveyard((AbandonedDataCenter) map, g).draw();
        else new Painter(map, g, c(map.getBackgroundRgb()), c(0x00f0ff), c(map.getTrackRgb())).drawGeneric();
    }

    // ==================================================================================================== shared painter
    private static class Painter {
        final GameMap map;
        final Graphics2D g;
        final Color bg, accent, track;
        final Random rnd;

        Painter(GameMap map, Graphics2D g, Color bg, Color accent, Color track) {
            this.map = map; this.g = g; this.bg = bg; this.accent = accent; this.track = track;
            this.rnd = new Random(map.getName().hashCode());
        }

        void drawGeneric() {
            fill(new Rectangle2D.Double(0, 0, W, H), bg);
            grid(25, 100, accent, 12, 26);
            vignette(120);
            track(0.55, accent);
            hudFrame(accent, "SECTOR");
            scanlines(10);
        }

        // ---------------------------------------------------------------- primitives
        void fill(Shape s, Color c) { g.setColor(c); g.fill(s); }
        void draw(Shape s, Color c, double w) { g.setStroke(round(w)); g.setColor(c); g.draw(s); }

        /** Stroke with a soft glow: a few wide translucent passes under the core line. */
        void glow(Shape s, Color c, double w, double spread) {
            for (int i = 3; i >= 1; i--) draw(s, alpha(c, (int) (c.getAlpha() * (0.09 + 0.05 * (3 - i)))), w + spread * i);
            draw(s, c, w);
        }

        void text(String s, double x, double y, Font f, Color c) {
            g.setFont(f); g.setColor(c);
            g.drawString(s, (float) x, (float) y);
        }

        /**
         * A legible map label: bright display-font text on a dark, outlined plate, centred on (cx, cy) and kept inside the
         * world. Every functional label (building, pad, hub, portal, hazard) goes through this so it reads over any art.
         */
        void tag(String s, double cx, double cy, Color c) { tag(s, cx, cy, c, true); }

        /** A tag whose right edge sits at {@code rx} (for labels that must stay clear of something to their right). */
        void tagRight(String s, double rx, double cy, Color c) {
            tag(s, rx - textWidth(s.toUpperCase(), Cyber.display(Font.BOLD, 14)) - 14, cy, c, false);
        }

        void tag(String s, double cx, double cy, Color c, boolean centered) {
            Font f = Cyber.display(Font.BOLD, 14);
            String u = s.toUpperCase();
            double tw = textWidth(u, f), pw = tw + 14, ph = 18;
            double x = centered ? cx - pw / 2 : cx;
            x = Math.max(4, Math.min(W - pw - 4, x));
            double y = Math.max(4, Math.min(H - ph - 4, cy - ph / 2));
            RoundRectangle2D.Double plate = new RoundRectangle2D.Double(x, y, pw, ph, 6, 6);
            fill(plate, new Color(3, 6, 16, 225));
            draw(plate, alpha(c, 190), 1);
            text(u, x + 7, y + ph / 2 + g.getFontMetrics().getAscent() / 2.0 - 1, f, Cyber.lerp(c, Color.WHITE, 0.35));
        }

        void textCentered(String s, double cx, double y, Font f, Color c) {
            g.setFont(f);
            FontMetrics fm = g.getFontMetrics();
            text(s, cx - fm.stringWidth(s) / 2.0, y, f, c);
        }

        double textWidth(String s, Font f) { g.setFont(f); return g.getFontMetrics().stringWidth(s); }

        /** True if a disc of radius r at (x, y) keeps clear of every track, obstacle and the world edge. */
        boolean clear(double x, double y, double r) {
            if (x < r + 4 || y < r + 4 || x > W - r - 4 || y > H - r - 4) return false;
            Vec p = new Vec(x, y);
            for (Path route : map.getRoutes()) if (route.distanceToPoint(p) < HW + r + 7) return false;
            for (Obstacle o : map.getObstacles()) if (o.contains(p, r + 6)) return false;
            return extraClear(x, y, r);
        }

        /** Per-map exclusions (pads, hubs, arena). */
        boolean extraClear(double x, double y, double r) { return true; }

        // ---------------------------------------------------------------- backgrounds
        void grid(double minor, double major, Color c, int aMinor, int aMajor) {
            Path2D.Double mi = new Path2D.Double(), ma = new Path2D.Double();
            for (double x = 0; x <= W; x += minor) (x % major == 0 ? ma : mi).append(new Line2D.Double(x, 0, x, H), false);
            for (double y = 0; y <= H; y += minor) (y % major == 0 ? ma : mi).append(new Line2D.Double(0, y, W, y), false);
            draw(mi, alpha(c, aMinor), 1);
            draw(ma, alpha(c, aMajor), 1);
            Path2D.Double cross = new Path2D.Double();
            for (double x = major; x < W; x += major) {
                for (double y = major; y < H; y += major) {
                    cross.append(new Line2D.Double(x - 4, y, x + 4, y), false);
                    cross.append(new Line2D.Double(x, y - 4, x, y + 4), false);
                }
            }
            draw(cross, alpha(c, aMajor * 2), 1.2);
        }

        void dotGrid(double step, Color c, double r) {
            Path2D.Double p = new Path2D.Double();
            for (double y = step / 2; y < H; y += step) for (double x = step / 2; x < W; x += step) p.append(new Ellipse2D.Double(x - r, y - r, 2 * r, 2 * r), false);
            fill(p, c);
        }

        void hexGrid(double r, Color c, double w) {
            Path2D.Double p = new Path2D.Double();
            double hx = Math.sqrt(3) * r, vy = 1.5 * r;
            int row = 0;
            for (double y = 0; y < H + r; y += vy, row++) {
                for (double x = (row % 2) * hx / 2; x < W + hx; x += hx) p.append(hexagon(x, y, r, 30), false);
            }
            draw(p, c, w);
        }

        void glowBlob(double cx, double cy, double r, Color c) {
            g.setPaint(new RadialGradientPaint(new Point2D.Double(cx, cy), (float) r, new float[] { 0f, 1f }, new Color[] { c, alpha(c, 0) }));
            g.fill(new Ellipse2D.Double(cx - r, cy - r, 2 * r, 2 * r));
        }

        void vignette(int a) {
            g.setPaint(new RadialGradientPaint(new Point2D.Double(W / 2, H / 2), (float) (Math.hypot(W, H) / 2),
                new float[] { 0f, 0.55f, 1f }, new Color[] { new Color(0, 0, 0, 0), new Color(0, 0, 0, a / 4), new Color(0, 0, 0, a) }));
            g.fill(new Rectangle2D.Double(0, 0, W, H));
        }

        void scanlines(int a) {
            Path2D.Double p = new Path2D.Double();
            for (double y = 1; y < H; y += 3) p.append(new Rectangle2D.Double(0, y, W, 1), false);
            fill(p, new Color(0, 0, 0, a));
        }

        void stars(Shape region, int n, Color tint) {
            Shape old = g.getClip();
            if (region != null) g.clip(region);
            Rectangle2D b = region != null ? region.getBounds2D() : new Rectangle2D.Double(0, 0, W, H);
            for (int i = 0; i < n; i++) {
                double x = b.getX() + rnd.nextDouble() * b.getWidth(), y = b.getY() + rnd.nextDouble() * b.getHeight();
                double r = rnd.nextDouble() < 0.08 ? 1.6 : 0.5 + rnd.nextDouble() * 0.8;
                Color c = Cyber.lerp(Color.WHITE, tint, rnd.nextDouble() * 0.7);
                if (r > 1.4) glowBlob(x, y, 6, alpha(c, 60));
                fill(new Ellipse2D.Double(x - r, y - r, 2 * r, 2 * r), alpha(c, 90 + rnd.nextInt(150)));
            }
            g.setClip(old);
        }

        /** Corner brackets, ruler ticks and coordinate labels around the world edge. */
        void hudFrame(Color c, String tag) {
            Path2D.Double br = new Path2D.Double();
            double m = 6, L = 34;
            double[][] corners = { { m, m, 1, 1 }, { W - m, m, -1, 1 }, { m, H - m, 1, -1 }, { W - m, H - m, -1, -1 } };
            for (double[] k : corners) {
                br.moveTo(k[0] + k[2] * L, k[1]);
                br.lineTo(k[0], k[1]);
                br.lineTo(k[0], k[1] + k[3] * L);
            }
            glow(br, alpha(c, 170), 2, 2);
            Path2D.Double ticks = new Path2D.Double();
            for (double x = 50; x < W; x += 50) {
                double len = x % 100 == 0 ? 7 : 3.5;
                ticks.append(new Line2D.Double(x, 0, x, len), false);
                ticks.append(new Line2D.Double(x, H, x, H - len), false);
            }
            for (double y = 50; y < H; y += 50) {
                double len = y % 100 == 0 ? 7 : 3.5;
                ticks.append(new Line2D.Double(0, y, len, y), false);
                ticks.append(new Line2D.Double(W, y, W - len, y), false);
            }
            draw(ticks, alpha(c, 90), 1);
            if (tag != null) tag(tag, 14, H - 20, c, false);
        }

        // ---------------------------------------------------------------- track
        Path2D routePath(Path r) {
            Path2D.Double p = new Path2D.Double();
            List<Vec> w = r.getWaypoints();
            p.moveTo(w.get(0).x, w.get(0).y);
            for (int i = 1; i < w.size(); i++) p.lineTo(w.get(i).x, w.get(i).y);
            return p;
        }

        Area trackArea(double halfWidth) {
            BasicStroke st = new BasicStroke((float) (2 * halfWidth), BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND);
            Area a = new Area();
            for (Path r : map.getRoutes()) a.add(new Area(st.createStrokedShape(routePath(r))));
            return a;
        }

        /**
         * The track as a lit conduit: outer glow and drop shadow, a dark body tinted with the track colour, cross ribs,
         * inner lane lines, a dashed centre line, direction chevrons and crisp neon edges. {@code darken} is how far the
         * body is pulled towards black (0 = pure track colour).
         */
        void track(double darken, Color glowCol) {
            Area body = trackArea(HW);
            // glow + shadow
            for (int i = 4; i >= 1; i--) draw(body, alpha(glowCol, 10 + (4 - i) * 6), i * 5);
            g.translate(0, 3);
            draw(body, new Color(0, 0, 0, 140), 5);
            g.translate(0, -3);
            Color base = Cyber.lerp(track, Color.BLACK, darken);
            fill(body, base);
            Shape old = g.getClip();
            g.clip(body);
            // lighter inner band
            fill(trackArea(HW - 7), Cyber.lerp(base, track, 0.16));
            // cross ribs
            g.setColor(alpha(Cyber.lerp(track, Color.WHITE, 0.2), 42));
            g.setStroke(new BasicStroke((float) (2 * HW), BasicStroke.CAP_BUTT, BasicStroke.JOIN_MITER, 10f, new float[] { 1.6f, 9f }, 0f));
            for (Path r : map.getRoutes()) g.draw(routePath(r));
            // inner lane lines
            draw(trackArea(HW - 6), alpha(track, 80), 1);
            // centre line
            g.setColor(alpha(Cyber.lerp(track, Color.WHITE, 0.55), 95));
            g.setStroke(new BasicStroke(1.4f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 12f, 9f }, 0f));
            for (Path r : map.getRoutes()) g.draw(routePath(r));
            // direction chevrons
            Color chev = alpha(Cyber.lerp(track, Color.WHITE, 0.45), 120);
            for (Path r : map.getRoutes()) {
                for (double d = 55; d < r.getTotalLength() - 30; d += 95) {
                    Vec p = r.positionAt(d), dir = r.directionAt(d), n = new Vec(-dir.y, dir.x);
                    Path2D.Double cv = new Path2D.Double();
                    for (int k = 0; k < 2; k++) {
                        double o = k * 7 - 3;
                        cv.moveTo(p.x + dir.x * (o - 5) + n.x * 9, p.y + dir.y * (o - 5) + n.y * 9);
                        cv.lineTo(p.x + dir.x * (o + 1), p.y + dir.y * (o + 1));
                        cv.lineTo(p.x + dir.x * (o - 5) - n.x * 9, p.y + dir.y * (o - 5) - n.y * 9);
                    }
                    draw(cv, chev, 1.8);
                }
            }
            g.setClip(old);
            // neon edges
            glow(body, alpha(Cyber.lerp(track, Color.WHITE, 0.15), 235), 1.8, 2.2);
            // bend studs just outside the corners
            for (Path r : map.getRoutes()) {
                List<Vec> w = r.getWaypoints();
                for (int i = 1; i + 1 < w.size(); i++) {
                    Vec a = w.get(i - 1), b = w.get(i), cc = w.get(i + 1);
                    Vec d1 = b.sub(a).normalized(), d2 = cc.sub(b).normalized();
                    if (Math.abs(d1.x * d2.y - d1.y * d2.x) < 0.5) continue; // gentle bends (spirals) get no stud
                    Vec out = d1.sub(d2).normalized();
                    double sx = b.x + out.x * (HW + 9), sy = b.y + out.y * (HW + 9);
                    fill(new Ellipse2D.Double(sx - 3, sy - 3, 6, 6), alpha(track, 200));
                    draw(new Ellipse2D.Double(sx - 6, sy - 6, 12, 12), alpha(track, 90), 1);
                }
            }
        }

        // ---------------------------------------------------------------- props
        /** Random orthogonal / 45-degree circuit traces that keep clear of the track and obstacles, ending in vias. */
        void circuit(int count, Color line, Color shadow, Color viaRing, Color viaHole) {
            int made = 0;
            for (int tries = 0; made < count && tries < count * 40; tries++) {
                double x = Math.round(rnd.nextDouble() * W / 10) * 10, y = Math.round(rnd.nextDouble() * H / 10) * 10;
                if (!clear(x, y, 6)) continue;
                Path2D.Double tr = new Path2D.Double();
                tr.moveTo(x, y);
                double cx = x, cy = y, total = 0;
                int dir = rnd.nextInt(4) * 2;
                int segs = 2 + rnd.nextInt(3);
                for (int k = 0; k < segs; k++) {
                    double dx = Math.round(Math.cos(dir * Math.PI / 4)), dy = Math.round(Math.sin(dir * Math.PI / 4));
                    double want = 30 + rnd.nextInt(9) * 14, run = 0;
                    while (run < want && clear(cx + dx * 4, cy + dy * 4, 5)) { cx += dx * 4; cy += dy * 4; run += 4; }
                    if (run > 0) { tr.lineTo(cx, cy); total += run; }
                    if (run < want) break;
                    dir = (dir + (rnd.nextBoolean() ? 1 : 7)) % 8;
                }
                if (total < 40) continue;
                double w = rnd.nextDouble() < 0.2 ? 3 : rnd.nextDouble() < 0.5 ? 2 : 1.2;
                if (shadow != null) draw(tr, shadow, w + 2);
                draw(tr, line, w);
                for (double[] v : new double[][] { { x, y }, { cx, cy } }) {
                    fill(new Ellipse2D.Double(v[0] - 3.4, v[1] - 3.4, 6.8, 6.8), viaRing);
                    fill(new Ellipse2D.Double(v[0] - 1.5, v[1] - 1.5, 3, 3), viaHole);
                }
                made++;
            }
        }

        /** The stretch of a route between two distances, sampled every 4 px. */
        Path2D subPath(Path r, double from, double to) {
            Path2D.Double p = new Path2D.Double();
            Vec a = r.positionAt(from);
            p.moveTo(a.x, a.y);
            for (Vec w : r.getWaypoints()) {   // keep only real corners between the ends
                double d = r.nearestDistanceAlong(w);
                if (d > from + 0.5 && d < to - 0.5) p.lineTo(w.x, w.y);
            }
            Vec b = r.positionAt(to);
            p.lineTo(b.x, b.y);
            return p;
        }

        /** Top-down little autonomous car. */
        void car(double cx, double cy, double angDeg, Color body) {
            AffineTransform old = g.getTransform();
            g.translate(cx, cy);
            g.rotate(Math.toRadians(angDeg));
            fill(new RoundRectangle2D.Double(-11, -6, 22, 12, 6, 6), new Color(0, 0, 0, 110));
            fill(new RoundRectangle2D.Double(-10, -5.5, 20, 11, 6, 6), body);
            fill(new RoundRectangle2D.Double(-4, -4.2, 9, 8.4, 3, 3), new Color(0x0c1626));
            fill(new RoundRectangle2D.Double(-3, -3.4, 4, 6.8, 2, 2), new Color(120, 200, 255, 120));
            fill(new Rectangle2D.Double(8.5, -4.5, 1.6, 2.4), new Color(0xeaffff));
            fill(new Rectangle2D.Double(8.5, 2.1, 1.6, 2.4), new Color(0xeaffff));
            fill(new Rectangle2D.Double(-10, -4.5, 1.4, 2.4), Cyber.RED);
            fill(new Rectangle2D.Double(-10, 2.1, 1.4, 2.4), Cyber.RED);
            fill(new Ellipse2D.Double(-1.5, -1.5, 3, 3), Cyber.CYAN);   // roof sensor
            g.setTransform(old);
        }

        /** Floating holographic ad panel. */
        void holo(double x, double y, double w0, double h, Color c1, Color c2, String l1, String l2) {
            double w = Math.max(w0, textWidth(l1.toUpperCase(), Cyber.display(Font.BOLD, 14)) + 22);
            glowBlob(x + w / 2, y + h / 2, w * 0.8, alpha(c1, 40));
            g.setPaint(new GradientPaint((float) x, (float) y, alpha(c1, 110), (float) (x + w), (float) (y + h), alpha(c2, 90)));
            g.fill(new Rectangle2D.Double(x, y, w, h));
            Path2D.Double lines = new Path2D.Double();
            for (double yy = y + 2; yy < y + h; yy += 3) lines.append(new Line2D.Double(x, yy, x + w, yy), false);
            draw(lines, new Color(255, 255, 255, 22), 1);
            glow(new Rectangle2D.Double(x, y, w, h), alpha(c1, 220), 1.2, 2);
            textCentered(l1.toUpperCase(), x + w / 2, y + h / 2 + 4, Cyber.display(Font.BOLD, 14), new Color(255, 255, 255, 240));
            // projector beam to the ground
            Path2D.Double beam = new Path2D.Double();
            beam.moveTo(x + w * 0.4, y + h); beam.lineTo(x + w * 0.6, y + h); beam.lineTo(x + w / 2 + 2, y + h + 14); beam.lineTo(x + w / 2 - 2, y + h + 14); beam.closePath();
            fill(beam, alpha(c1, 60));
        }

        /** Small robotic arm (top-down) at (x, y). */
        void robotArm(double x, double y, double ang, Color accentC) {
            fill(new Ellipse2D.Double(x - 9, y - 9, 18, 18), c(0x2a3140));
            draw(new Ellipse2D.Double(x - 9, y - 9, 18, 18), alpha(accentC, 180), 1.2);
            double a1 = Math.toRadians(ang), a2 = a1 + Math.toRadians(70);
            double ex = x + Math.cos(a1) * 22, ey = y + Math.sin(a1) * 22, hx = ex + Math.cos(a2) * 17, hy = ey + Math.sin(a2) * 17;
            draw(new Line2D.Double(x, y, ex, ey), c(0x0a0d12), 8);
            draw(new Line2D.Double(x, y, ex, ey), c(0xe08a2e), 5.5);
            draw(new Line2D.Double(ex, ey, hx, hy), c(0x0a0d12), 6);
            draw(new Line2D.Double(ex, ey, hx, hy), c(0xf0a040), 4);
            fill(new Ellipse2D.Double(ex - 4, ey - 4, 8, 8), c(0x3a4250));
            fill(new Ellipse2D.Double(x - 3.5, y - 3.5, 7, 7), alpha(accentC, 230));
            double ga = a2 + Math.PI / 2;
            draw(new Line2D.Double(hx + Math.cos(ga) * 5, hy + Math.sin(ga) * 5, hx - Math.cos(ga) * 5, hy - Math.sin(ga) * 5), c(0xc0c8d0), 2.4);
            glowBlob(hx, hy, 8, alpha(accentC, 90));
        }

        void hudTag(String s, double x, double y, Color c) {
            tag(s, x, y + 9, c, false);
        }

        void fan(double cx, double cy, double r, Color c) {
            fill(new Ellipse2D.Double(cx - r, cy - r, 2 * r, 2 * r), new Color(6, 8, 12));
            draw(new Ellipse2D.Double(cx - r, cy - r, 2 * r, 2 * r), alpha(c, 150), 1.6);
            Path2D.Double blades = new Path2D.Double();
            for (int i = 0; i < 7; i++) {
                double a0 = i * Math.PI * 2 / 7;
                blades.moveTo(cx + Math.cos(a0) * r * 0.28, cy + Math.sin(a0) * r * 0.28);
                blades.quadTo(cx + Math.cos(a0 + 0.5) * r * 0.75, cy + Math.sin(a0 + 0.5) * r * 0.75,
                    cx + Math.cos(a0 + 0.95) * r * 0.86, cy + Math.sin(a0 + 0.95) * r * 0.86);
            }
            draw(blades, alpha(c, 110), 3.2);
            Path2D.Double grill = new Path2D.Double();
            for (double rr = r * 0.45; rr < r; rr += r * 0.18) grill.append(new Ellipse2D.Double(cx - rr, cy - rr, 2 * rr, 2 * rr), false);
            grill.append(new Line2D.Double(cx - r, cy, cx + r, cy), false);
            grill.append(new Line2D.Double(cx, cy - r, cx, cy + r), false);
            draw(grill, alpha(Color.WHITE, 40), 0.8);
            fill(new Ellipse2D.Double(cx - r * 0.26, cy - r * 0.26, r * 0.52, r * 0.52), new Color(0x2a3140));
            draw(new Ellipse2D.Double(cx - r * 0.26, cy - r * 0.26, r * 0.52, r * 0.52), alpha(c, 200), 1.2);
        }
    }

    // ==================================================================================================== 1. Silicon
    private static final class Silicon extends Painter {
        final SiliconCircuit sc;
        final Color gold = c(0xd4a62a), mask = c(0x2e6a45), silk = new Color(220, 236, 226, 150);

        Silicon(SiliconCircuit sc, Graphics2D g) { super(sc, g, c(0x0d2c1a), c(0x3bff8a), c(0xd4a62a)); this.sc = sc; }

        @Override boolean extraClear(double x, double y, double r) {
            for (Vec p : sc.getPads()) if (p.dist(new Vec(x, y)) < 50 + r) return false;
            return true;
        }

        void draw() {
            g.setPaint(new GradientPaint(0, 0, c(0x123a23), (float) W, (float) H, c(0x0a2214)));
            g.fill(new Rectangle2D.Double(0, 0, W, H));
            // solder-mask weave + faint grid
            dotGrid(20, alpha(c(0x3bff8a), 16), 0.9);
            grid(50, 200, accent, 7, 16);
            glowBlob(600, 470, 520, new Color(60, 255, 140, 18));
            traces();
            components();
            mountingHoles();
            silkscreen();
            vignette(130);
            for (Obstacle o : map.getObstacles()) chip(o);
            for (Vec p : sc.getPads()) pad(p);
            track(0.38, gold);
            hudFrame(accent, "PCB // LX-MAINBOARD");
            scanlines(9);
        }

        /** Random orthogonal / 45-degree copper traces under the solder mask, ending in vias. */
        void traces() {
            int made = 0;
            for (int tries = 0; made < 110 && tries < 4000; tries++) {
                double x = Math.round(rnd.nextDouble() * W / 10) * 10, y = Math.round(rnd.nextDouble() * H / 10) * 10;
                if (!clear(x, y, 6)) continue;
                Path2D.Double tr = new Path2D.Double();
                tr.moveTo(x, y);
                double cx = x, cy = y, total = 0;
                int dir = rnd.nextInt(4) * 2; // start orthogonal
                int segs = 2 + rnd.nextInt(3);
                for (int s = 0; s < segs; s++) {
                    double dx = Math.round(Math.cos(dir * Math.PI / 4)), dy = Math.round(Math.sin(dir * Math.PI / 4));
                    double want = 30 + rnd.nextInt(9) * 14, run = 0;
                    while (run < want && clear(cx + dx * 4, cy + dy * 4, 5)) { cx += dx * 4; cy += dy * 4; run += 4; }
                    if (run > 0) { tr.lineTo(cx, cy); total += run; }
                    if (run < want) break;
                    dir = (dir + (rnd.nextBoolean() ? 1 : 7)) % 8;
                }
                if (total < 40) continue;
                double w = rnd.nextDouble() < 0.2 ? 3.4 : rnd.nextDouble() < 0.5 ? 2.2 : 1.4;
                draw(tr, alpha(c(0x081a10), 160), w + 2);
                draw(tr, alpha(Cyber.lerp(mask, accent, 0.15), 200), w);
                via(x, y);
                via(cx, cy);
                made++;
            }
        }

        void via(double x, double y) {
            fill(new Ellipse2D.Double(x - 3.6, y - 3.6, 7.2, 7.2), c(0xb89a4a));
            fill(new Ellipse2D.Double(x - 1.6, y - 1.6, 3.2, 3.2), c(0x06120b));
        }

        void components() {
            String[] pre = { "R", "C", "L", "D", "Q" };
            int made = 0;
            for (int tries = 0; made < 46 && tries < 3000; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                boolean ic = made % 6 == 5;
                boolean vert = rnd.nextBoolean();
                double w = ic ? 24 : 11, h = ic ? 14 : 5;
                if (vert) { double t = w; w = h; h = t; }
                if (!clear(x, y, Math.max(w, h) / 2 + 4)) continue;
                double x0 = x - w / 2, y0 = y - h / 2;
                if (ic) {
                    Path2D.Double pins = new Path2D.Double();
                    int n = 4;
                    for (int i = 0; i < n; i++) {
                        double f = (i + 0.5) / n;
                        if (!vert) {
                            pins.append(new Rectangle2D.Double(x0 + f * w - 1, y0 - 3, 2, 3), false);
                            pins.append(new Rectangle2D.Double(x0 + f * w - 1, y0 + h, 2, 3), false);
                        } else {
                            pins.append(new Rectangle2D.Double(x0 - 3, y0 + f * h - 1, 3, 2), false);
                            pins.append(new Rectangle2D.Double(x0 + w, y0 + f * h - 1, 3, 2), false);
                        }
                    }
                    fill(pins, c(0xc7ccd3));
                    fill(new Rectangle2D.Double(x0, y0, w, h), c(0x15181d));
                    draw(new Rectangle2D.Double(x0, y0, w, h), c(0x3a4250), 0.8);
                    fill(new Ellipse2D.Double(x0 + 2, y0 + 2, 2.4, 2.4), c(0x606a78));
                } else {
                    boolean cap = rnd.nextBoolean();
                    fill(new Rectangle2D.Double(x0, y0, w, h), cap ? c(0x9c7a4c) : c(0x1a1a1c));
                    double cw = 2.4;
                    Color end = c(0xd8dce2);
                    if (!vert) { fill(new Rectangle2D.Double(x0, y0, cw, h), end); fill(new Rectangle2D.Double(x0 + w - cw, y0, cw, h), end); }
                    else { fill(new Rectangle2D.Double(x0, y0, w, cw), end); fill(new Rectangle2D.Double(x0, y0 + h - cw, w, cw), end); }
                }
                made++;
            }
        }

        void mountingHoles() {
            double[][] holes = { { 26, 26 }, { 1174, 26 }, { 26, 874 }, { 1174, 874 }, { 600, 26 } };
            for (double[] h : holes) {
                if (!clear(h[0], h[1], 10)) continue;
                fill(new Ellipse2D.Double(h[0] - 11, h[1] - 11, 22, 22), c(0xb89a4a));
                fill(new Ellipse2D.Double(h[0] - 6, h[1] - 6, 12, 12), c(0x050a07));
                draw(new Ellipse2D.Double(h[0] - 14, h[1] - 14, 28, 28), alpha(silk, 90), 0.8);
            }
        }

        void silkscreen() {
            tag("LX-MAINBOARD // REV 4B", 600, 470, Cyber.lerp(silk, c(0x7fd8a8), 0.4));
            for (Path r : map.getRoutes()) {
                Vec s = r.getStart();
                tag(r.getName(), s.x + 34, s.y - HW - 18, gold, false);
            }
        }

        void chip(Obstacle o) {
            String l = o.label == null ? "" : o.label;
            if (l.equals("RAM")) { dimm(o); return; }
            if (l.equals("I/O")) { connector(o); return; }
            double x = o.x, y = o.y, w = o.w, h = o.h, in = 6;
            Path2D.Double pins = new Path2D.Double();
            for (double px = x + in + 3; px < x + w - in - 2; px += 7) {
                pins.append(new Rectangle2D.Double(px, y, 3, in), false);
                pins.append(new Rectangle2D.Double(px, y + h - in, 3, in), false);
            }
            for (double py = y + in + 3; py < y + h - in - 2; py += 7) {
                pins.append(new Rectangle2D.Double(x, py, in, 3), false);
                pins.append(new Rectangle2D.Double(x + w - in, py, in, 3), false);
            }
            fill(pins, c(0xc9ced6));
            Rectangle2D.Double body = new Rectangle2D.Double(x + in, y + in, w - 2 * in, h - 2 * in);
            glowBlob(x + w / 2, y + h / 2, w * 0.7, new Color(0, 240, 255, 26));
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x2a2f37), (float) x, (float) (y + h), c(0x0f1115)));
            g.fill(body);
            draw(body, c(0x4c5562), 1);
            Rectangle2D.Double die = new Rectangle2D.Double(x + 18, y + 13, w - 36, h - 26);
            g.setPaint(new GradientPaint((float) die.x, (float) die.y, c(0x1b2a3a), (float) (die.x + die.width), (float) (die.y + die.height), c(0x0b1420)));
            g.fill(die);
            Path2D.Double cells = new Path2D.Double();
            for (double cx = die.x + 4; cx < die.x + die.width - 3; cx += 6) cells.append(new Line2D.Double(cx, die.y + 2, cx, die.y + die.height - 2), false);
            draw(cells, new Color(0, 240, 255, 26), 1);
            draw(die, new Color(0, 240, 255, 150), 1);
            fill(new Ellipse2D.Double(x + in + 3, y + in + 3, 4, 4), c(0x8a929a));
            textCentered(l, x + w / 2, die.y + die.height / 2 + 2, Cyber.display(Font.BOLD, 15), c(0xd9f6ff));
        }

        void dimm(Obstacle o) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            RoundRectangle2D.Double board = new RoundRectangle2D.Double(x, y, w, h, 6, 6);
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x1b5c34), (float) x, (float) (y + h), c(0x0f3a20)));
            g.fill(board);
            draw(board, c(0x8a929a), 1);
            Path2D.Double fingers = new Path2D.Double();
            for (double fx = x + 6; fx < x + w - 6; fx += 5) {
                if (Math.abs(fx - (x + w * 0.42)) < 4) continue; // key notch
                fingers.append(new Rectangle2D.Double(fx, y + h - 11, 3, 9), false);
            }
            fill(fingers, gold);
            fill(new Rectangle2D.Double(x + w * 0.42 - 2, y + h - 12, 4, 12), c(0x0b2616));
            for (int i = 0; i < 4; i++) {
                double cx = x + 8 + i * (w - 16) / 4.0;
                Rectangle2D.Double chip = new Rectangle2D.Double(cx + 2, y + 10, (w - 16) / 4.0 - 4, h - 30);
                fill(chip, c(0x121418));
                draw(chip, c(0x3a4250), 0.8);
                fill(new Rectangle2D.Double(chip.x + 3, chip.y + 3, chip.width - 6, 2), new Color(0, 240, 255, 60));
            }
            text("RAM", x + 8, y + h - 15, Cyber.display(Font.BOLD, 14), c(0xe6eef6));
        }

        void connector(Obstacle o) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            RoundRectangle2D.Double shell = new RoundRectangle2D.Double(x, y, w, h, 10, 10);
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x9aa3ad), (float) x, (float) (y + h), c(0x3a4048)));
            g.fill(shell);
            draw(shell, c(0xd8dee6), 1);
            RoundRectangle2D.Double slot = new RoundRectangle2D.Double(x + 10, y + 12, w - 20, h - 24, 6, 6);
            fill(slot, c(0x0a0c10));
            Path2D.Double pins = new Path2D.Double();
            for (int row = 0; row < 2; row++) for (double px = x + 18; px < x + w - 16; px += 9) pins.append(new Rectangle2D.Double(px, y + 18 + row * 12, 4, 5), false);
            fill(pins, gold);
            for (int i = 0; i < 3; i++) fill(new Ellipse2D.Double(x + w - 14 - i * 8, y + 4, 4, 4), i == 0 ? Cyber.GREEN : new Color(0x2a3a30));
            text("I/O", x + 10, y + 10, Cyber.display(Font.BOLD, 14), c(0x10141a));
        }

        void pad(Vec p) {
            double r = 42;
            glowBlob(p.x, p.y, 70, new Color(127, 216, 168, 34));
            g.setPaint(new RadialGradientPaint(new Point2D.Double(p.x - 10, p.y - 12), (float) r,
                new float[] { 0f, 0.7f, 1f }, new Color[] { c(0xc89a52), c(0x8a5c2a), c(0x4a3016) }));
            g.fill(new Ellipse2D.Double(p.x - r, p.y - r, 2 * r, 2 * r));
            // thermal relief gaps
            g.setColor(c(0x0d2c1a));
            g.setStroke(new BasicStroke(6f));
            for (int i = 0; i < 4; i++) {
                double a = Math.PI / 4 + i * Math.PI / 2;
                g.draw(new Line2D.Double(p.x + Math.cos(a) * (r - 13), p.y + Math.sin(a) * (r - 13), p.x + Math.cos(a) * (r + 1), p.y + Math.sin(a) * (r + 1)));
            }
            fill(new Ellipse2D.Double(p.x - 26, p.y - 26, 52, 52), c(0x1d4a32));
            draw(new Ellipse2D.Double(p.x - 26, p.y - 26, 52, 52), alpha(c(0x7fd8a8), 200), 1.2);
            draw(new Ellipse2D.Double(p.x - 16, p.y - 16, 32, 32), alpha(c(0x7fd8a8), 110), 1);
            Path2D.Double ticks = new Path2D.Double();
            for (int i = 0; i < 24; i++) {
                double a = i * Math.PI / 12, r0 = r + 4, r1 = r + (i % 3 == 0 ? 10 : 7);
                ticks.append(new Line2D.Double(p.x + Math.cos(a) * r0, p.y + Math.sin(a) * r0, p.x + Math.cos(a) * r1, p.y + Math.sin(a) * r1), false);
            }
            draw(ticks, alpha(c(0x7fd8a8), 150), 1.2);
            glow(new Ellipse2D.Double(p.x - r, p.y - r, 2 * r, 2 * r), alpha(c(0x7fd8a8), 220), 1.6, 2);
            // "+" polarity mark
            Path2D.Double plus = new Path2D.Double();
            plus.append(new Line2D.Double(p.x - 6, p.y, p.x + 6, p.y), false);
            plus.append(new Line2D.Double(p.x, p.y - 6, p.x, p.y + 6), false);
            draw(plus, alpha(c(0x7fd8a8), 200), 2);
            tag("CAPACITOR PAD", p.x, p.y + r + 24, c(0x7fd8a8));
        }
    }

    // ==================================================================================================== 2. Monolith
    private static final class Monolith extends Painter {
        final LegacyMonolith lm;
        final Color steel = c(0x6f7a8c), amber = c(0xffb43b);

        Monolith(LegacyMonolith lm, Graphics2D g) { super(lm, g, c(0x161a22), c(0x5aa8ff), c(0x4f6f8f)); this.lm = lm; }

        void draw() {
            fill(new Rectangle2D.Double(0, 0, W, H), bg);
            double[][] floors = lm.getFloors();
            List<double[]> bands = new ArrayList<>();
            bands.add(new double[] { 0, floors[0][0] });
            for (double[] f : floors) bands.add(f);
            bands.add(new double[] { floors[floors.length - 1][1], H });
            for (double[] b : bands) {
                g.setPaint(new GradientPaint(0, (float) b[0], c(0x1d2330), 0, (float) b[1], c(0x10131a)));
                g.fill(new Rectangle2D.Double(0, b[0], W, b[1] - b[0]));
            }
            // panel seams
            Path2D.Double seams = new Path2D.Double();
            for (double x = 200; x < W; x += 200) seams.append(new Line2D.Double(x, 0, x, H), false);
            draw(seams, new Color(0, 0, 0, 120), 2);
            g.translate(1.5, 0);
            draw(seams, new Color(255, 255, 255, 14), 1);
            g.translate(-1.5, 0);
            perforation();
            glowBlob(600, 450, 600, new Color(90, 168, 255, 16));
            rails();
            for (double[] f : floors) divider(f[0]);
            divider(floors[floors.length - 1][1]);
            header();
            footerVents();
            cables();
            double[][] fans = { { 190, 258 }, { 600, 258 }, { 1010, 258 }, { 190, 468 }, { 600, 468 }, { 1010, 468 }, { 190, 678 }, { 600, 678 }, { 1010, 678 }, { 600, 160 } };
            for (double[] f : fans) if (clear(f[0], f[1], 22)) fan(f[0], f[1], 22, accent);
            vignette(140);
            int n = 0;
            for (Obstacle o : map.getObstacles()) blade(o, n++);
            for (int i = 0; i < floors.length; i++) tagRight("FLOOR " + (i + 1) + " // " + (i < 2 ? "COLD AISLE" : "HOT AISLE"), 1086, floors[i][0] + 15, i < 2 ? accent : amber);
            track(0.45, accent);
            hudFrame(accent, "RACK-07 // LEGACY CLUSTER");
            scanlines(12);
        }

        void perforation() {
            Path2D.Double holes = new Path2D.Double(), lit = new Path2D.Double();
            int row = 0;
            for (double y = 8; y < H; y += 11, row++) {
                for (double x = (row % 2) * 5.5 + 40; x < W - 36; x += 11) {
                    if (!clear(x, y, 2)) continue;
                    holes.append(new Ellipse2D.Double(x - 1.6, y - 1.6, 3.2, 3.2), false);
                    lit.append(new Ellipse2D.Double(x - 1.6, y + 0.4, 3.2, 1.6), false);
                }
            }
            fill(holes, new Color(0, 0, 0, 150));
            fill(lit, new Color(120, 160, 220, 18));
        }

        void rails() {
            for (double x0 : new double[] { 4, W - 30 }) {
                Rectangle2D.Double rail = new Rectangle2D.Double(x0, 0, 26, H);
                g.setPaint(new GradientPaint((float) x0, 0, c(0x3a4250), (float) (x0 + 26), 0, c(0x1a1f28)));
                g.fill(rail);
                draw(new Line2D.Double(x0 + 0.5, 0, x0 + 0.5, H), new Color(255, 255, 255, 40), 1);
                Path2D.Double sq = new Path2D.Double();
                int u = 1;
                for (double y = 12; y < H - 6; y += 22, u++) {
                    sq.append(new Rectangle2D.Double(x0 + 10, y, 6, 6), false);
                }
                fill(sq, c(0x07090d));
            }
        }

        void divider(double y) {
            Rectangle2D.Double band = new Rectangle2D.Double(30, y - 5, W - 60, 10);
            fill(band, c(0x0c0e12));
            Shape old = g.getClip();
            g.clip(band);
            Path2D.Double stripes = new Path2D.Double();
            for (double x = 20; x < W; x += 16) {
                stripes.moveTo(x, y + 5); stripes.lineTo(x + 8, y - 5); stripes.lineTo(x + 14, y - 5); stripes.lineTo(x + 6, y + 5); stripes.closePath();
            }
            fill(stripes, alpha(c(0xc9a227), 70));
            g.setClip(old);
            draw(new Line2D.Double(30, y - 5, W - 30, y - 5), alpha(accent, 80), 1);
            draw(new Line2D.Double(30, y + 5, W - 30, y + 5), new Color(0, 0, 0, 160), 1);
        }

        void header() {
            tag("LEGACY MONOLITH // RACK 07 // 42U", 130, 30, accent, false);
            for (int i = 0; i < 18; i++) {
                double x = 660 + i * 12;
                Color led = i % 7 == 3 ? amber : i % 5 == 0 ? Cyber.RED : Cyber.GREEN;
                glowBlob(x + 2, 26, 6, alpha(led, 60));
                fill(new Rectangle2D.Double(x, 24, 5, 3), led);
            }
            tag("PWR A+B OK", 900, 30, Cyber.GREEN, false);
        }

        void footerVents() {
            Path2D.Double slots = new Path2D.Double();
            for (double x = 140; x < W - 60; x += 14) slots.append(new RoundRectangle2D.Double(x, 864, 8, 24, 4, 4), false);
            fill(slots, c(0x06070a));
            draw(slots, new Color(255, 255, 255, 18), 0.8);
        }

        void cables() {
            // power / data cable bundles that sag across the open strip of each floor
            double[] ys = { 160, 370, 580 };
            Color[] cols = { c(0x2b6cff), c(0xff8a2b), c(0x2bd67b), c(0x8a5cff) };
            for (double y : ys) {
                for (int k = 0; k < 4; k++) {
                    double x0 = 110 + k * 4, x1 = 290 - k * 3;
                    Path2D.Double cab = new Path2D.Double();
                    cab.moveTo(x0, y - 8 + k * 2);
                    cab.curveTo(x0 + 50, y + 10 + k * 3, x1 - 50, y + 10 + k * 3, x1, y - 6 + k * 2);
                    if (!clear(x0, y - 8 + k * 2, 3) || !clear(x1, y - 6 + k * 2, 3) || !clear((x0 + x1) / 2, y + 6 + k * 2, 3)) continue;
                    draw(cab, new Color(0, 0, 0, 150), 4.2);
                    draw(cab, alpha(cols[k], 150), 2.4);
                }
            }
        }

        void blade(Obstacle o, int idx) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            glowBlob(x + w / 2, y + h / 2, w * 0.65, new Color(90, 168, 255, 22));
            g.translate(0, 4);
            fill(new RoundRectangle2D.Double(x, y, w, h, 6, 6), new Color(0, 0, 0, 120));
            g.translate(0, -4);
            RoundRectangle2D.Double body = new RoundRectangle2D.Double(x, y, w, h, 6, 6);
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x3a4252), (float) x, (float) (y + h), c(0x1c2029)));
            g.fill(body);
            draw(body, steel, 1.2);
            // handle
            RoundRectangle2D.Double handle = new RoundRectangle2D.Double(x + 6, y + 8, 10, h - 16, 4, 4);
            fill(handle, c(0x0f1218));
            Path2D.Double grip = new Path2D.Double();
            for (double gy = y + 14; gy < y + h - 12; gy += 5) grip.append(new Line2D.Double(x + 8, gy, x + 14, gy), false);
            draw(grip, alpha(steel, 150), 1);
            // drive bays
            Random r = new Random(idx * 31L + 7);
            for (int i = 0; i < 6; i++) {
                double bx = x + 24 + i * 18;
                RoundRectangle2D.Double bay = new RoundRectangle2D.Double(bx, y + 9, 14, h - 34, 2, 2);
                fill(bay, c(0x12151c));
                draw(bay, c(0x4a5466), 0.8);
                Path2D.Double vent = new Path2D.Double();
                for (double vy = y + 14; vy < y + h - 32; vy += 4) vent.append(new Line2D.Double(bx + 3, vy, bx + 11, vy), false);
                draw(vent, new Color(255, 255, 255, 22), 0.8);
                Color led = r.nextDouble() < 0.18 ? amber : Cyber.GREEN;
                glowBlob(bx + 7, y + h - 29, 5, alpha(led, 90));
                fill(new Ellipse2D.Double(bx + 5.5, y + h - 30.5, 3, 3), led);
            }
            // LCD
            RoundRectangle2D.Double lcd = new RoundRectangle2D.Double(x + 136, y + 10, 52, 22, 3, 3);
            fill(lcd, c(0x061420));
            draw(lcd, alpha(accent, 170), 1);
            int load = 40 + r.nextInt(58);
            text(load + "%", x + 142, y + 24, Cyber.display(Font.BOLD, 14), load > 85 ? amber : Cyber.CYAN);
            fill(new Rectangle2D.Double(x + 140, y + 27, 44 * load / 100.0, 3), alpha(load > 85 ? amber : Cyber.CYAN, 190));
            // grill
            Shape old = g.getClip();
            Rectangle2D.Double gr = new Rectangle2D.Double(x + 136, y + 36, 52, h - 46);
            g.clip(gr);
            Path2D.Double slots = new Path2D.Double();
            for (double sx = gr.x - gr.height; sx < gr.x + gr.width; sx += 5) slots.append(new Line2D.Double(sx, gr.y + gr.height, sx + gr.height, gr.y), false);
            fill(gr, c(0x0c0f14));
            draw(slots, alpha(steel, 90), 1.4);
            g.setClip(old);
            draw(gr, alpha(steel, 140), 0.8);
            // status strip and label
            fill(new Rectangle2D.Double(x + 24, y + h - 18, 106, 2), alpha(accent, 140));
            fill(new Ellipse2D.Double(x + w - 22, y + 8 - 0.5, 8, 8), c(0x5ce07a));
            glowBlob(x + w - 18, y + 12, 8, new Color(92, 224, 122, 90));
            text(o.label, x + 24, y + h - 5, Cyber.display(Font.BOLD, 14), c(0xe2eaf6));
        }
    }

    // ==================================================================================================== 3. Canyon
    private static final class Canyon extends Painter {
        final HallucinationCanyon hc;
        final Color violet = c(0xb48cff), pink = c(0xff8cf0), pale = c(0xe0c8ff);

        Canyon(HallucinationCanyon hc, Graphics2D g) { super(hc, g, c(0x1b1430), c(0xb48cff), c(0x8f7fcf)); this.hc = hc; }

        @Override boolean extraClear(double x, double y, double r) {
            Vec p = new Vec(x, y);
            if (p.dist(hc.getCenter()) < 70 + r) return false;
            for (HallucinationCanyon.BridgeNode n : hc.getNodes()) if (p.dist(n.pos) < 40 + r) return false;
            return true;
        }

        void draw() {
            g.setPaint(new RadialGradientPaint(new Point2D.Double(600, 450), 760f, new float[] { 0f, 0.6f, 1f },
                new Color[] { c(0x2a1d4c), c(0x1b1430), c(0x0e0a1c) }));
            g.fill(new Rectangle2D.Double(0, 0, W, H));
            hexGrid(24, alpha(violet, 16), 1);
            glowBlob(300, 200, 360, new Color(255, 140, 240, 22));
            glowBlob(920, 720, 380, new Color(120, 90, 255, 26));
            network();
            for (Obstacle o : map.getObstacles()) chasm(o);
            vignette(150);
            track(0.5, violet);
            for (HallucinationCanyon.BridgeNode n : hc.getNodes()) node(n);
            hub(hc.getCenter());
            hudFrame(violet, "NEURAL FIELD // LAYER 12 OF 96");
            scanlines(10);
        }

        void network() {
            List<Vec> ns = new ArrayList<>();
            for (int tries = 0; ns.size() < 60 && tries < 3000; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (clear(x, y, 9)) ns.add(new Vec(x, y));
            }
            Path2D.Double links = new Path2D.Double();
            for (int i = 0; i < ns.size(); i++) {
                Vec a = ns.get(i);
                int best1 = -1, best2 = -1;
                double d1 = 1e9, d2 = 1e9;
                for (int j = 0; j < ns.size(); j++) {
                    if (j == i) continue;
                    double d = a.dist(ns.get(j));
                    if (d < d1) { d2 = d1; best2 = best1; d1 = d; best1 = j; } else if (d < d2) { d2 = d; best2 = j; }
                }
                for (int b : new int[] { best1, best2 }) {
                    if (b < 0 || a.dist(ns.get(b)) > 230) continue;
                    Vec v = ns.get(b);
                    double mx = (a.x + v.x) / 2 + (rnd.nextDouble() - 0.5) * 40, my = (a.y + v.y) / 2 + (rnd.nextDouble() - 0.5) * 40;
                    links.moveTo(a.x, a.y);
                    links.quadTo(mx, my, v.x, v.y);
                }
            }
            draw(links, alpha(violet, 30), 3);
            draw(links, alpha(pale, 55), 0.9);
            for (Vec n : ns) {
                double r = 2 + rnd.nextDouble() * 2.5;
                Color c = rnd.nextDouble() < 0.25 ? pink : violet;
                glowBlob(n.x, n.y, r * 5, alpha(c, 70));
                fill(new Ellipse2D.Double(n.x - r, n.y - r, 2 * r, 2 * r), Cyber.lerp(c, Color.WHITE, 0.5));
                draw(new Ellipse2D.Double(n.x - r - 3, n.y - r - 3, 2 * r + 6, 2 * r + 6), alpha(c, 110), 0.8);
            }
        }

        void chasm(Obstacle o) {
            Rectangle2D.Double r = new Rectangle2D.Double(o.x, o.y, o.w, o.h);
            Path2D.Double jag = new Path2D.Double();
            double step = 12;
            boolean first = true;
            double[][] edges = { { o.x, o.y, o.x + o.w, o.y }, { o.x + o.w, o.y, o.x + o.w, o.y + o.h }, { o.x + o.w, o.y + o.h, o.x, o.y + o.h }, { o.x, o.y + o.h, o.x, o.y } };
            for (double[] e : edges) {
                double len = Math.hypot(e[2] - e[0], e[3] - e[1]);
                double nx = (e[3] - e[1]) / len, ny = -(e[2] - e[0]) / len; // outward normal (clockwise rect)
                for (double t = 0; t < len; t += step) {
                    double j = (rnd.nextDouble() - 0.3) * 3.5;
                    double px = e[0] + (e[2] - e[0]) * t / len + nx * j, py = e[1] + (e[3] - e[1]) * t / len + ny * j;
                    if (first) { jag.moveTo(px, py); first = false; } else jag.lineTo(px, py);
                }
            }
            jag.closePath();
            g.setPaint(new RadialGradientPaint(new Point2D.Double(r.getCenterX(), r.getCenterY()), (float) (Math.max(o.w, o.h) * 0.7),
                new float[] { 0f, 1f }, new Color[] { c(0x020106), c(0x0e0820) }));
            g.fill(jag);
            Shape old = g.getClip();
            g.clip(jag);
            stars(r, (int) (o.w * o.h / 900), violet);
            // perspective "depth" grid falling into the void
            Path2D.Double depth = new Path2D.Double();
            double cx = r.getCenterX(), cy = r.getCenterY();
            for (int i = 0; i <= 8; i++) {
                double fx = o.x + o.w * i / 8.0;
                depth.append(new Line2D.Double(fx, o.y, cx + (fx - cx) * 0.25, cy), false);
                depth.append(new Line2D.Double(fx, o.y + o.h, cx + (fx - cx) * 0.25, cy), false);
            }
            for (double k = 0.85; k > 0.3; k -= 0.18) depth.append(new Rectangle2D.Double(cx - o.w * k / 2, cy - o.h * k / 2, o.w * k, o.h * k), false);
            draw(depth, alpha(violet, 26), 1);
            // inner shadow
            for (int i = 0; i < 6; i++) draw(r, new Color(0, 0, 0, 60 - i * 9), 4 + i * 4);
            g.setClip(old);
            glow(jag, alpha(pink, 200), 1.4, 2.4);
            draw(jag, alpha(violet, 120), 4);
            // glitch bars across the rim
            for (int i = 0; i < 5; i++) {
                boolean top = rnd.nextBoolean();
                double bw = 18 + rnd.nextDouble() * 50, bx = o.x + rnd.nextDouble() * Math.max(1, o.w - bw);
                double by = (top ? o.y : o.y + o.h) + (rnd.nextDouble() - 0.5) * 8;
                fill(new Rectangle2D.Double(bx, by, bw, 1.5 + rnd.nextDouble() * 2), alpha(rnd.nextBoolean() ? pink : Cyber.CYAN, 110));
            }
            tag(o.w < 140 ? "VOID" : "NULL REGION", o.x + (o.w < 140 ? o.w / 2 : 10), o.y + 18, pink, o.w < 140);
        }

        void node(HallucinationCanyon.BridgeNode n) {
            Vec p = n.pos;
            fill(hexagon(p.x, p.y, 31, 0), alpha(violet, 34));
            glow(hexagon(p.x, p.y, 31, 0), alpha(violet, 230), 1.6, 2.4);
            draw(hexagon(p.x, p.y, 36, 0), alpha(pale, 70), 0.8);
            g.setColor(alpha(pale, 150));
            g.setStroke(new BasicStroke(1.2f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 5f, 4f }, 0f));
            g.draw(new Ellipse2D.Double(p.x - 19, p.y - 19, 38, 38));
            for (int i = 0; i < 6; i++) {
                double a = Math.toRadians(i * 60);
                fill(new Ellipse2D.Double(p.x + Math.cos(a) * 31 - 2.2, p.y + Math.sin(a) * 31 - 2.2, 4.4, 4.4), pale);
            }
        }

        void hub(Vec c) {
            glowBlob(c.x, c.y, 120, new Color(180, 140, 255, 60));
            fill(new Ellipse2D.Double(c.x - 40, c.y - 40, 80, 80), alpha(c(0x5a3fa0), 110));
            for (int i = 0; i < 3; i++) {
                double r = 48 + i * 11;
                g.setColor(alpha(i == 1 ? pink : pale, 170 - i * 40));
                g.setStroke(new BasicStroke(i == 0 ? 2f : 1.2f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f,
                    i == 0 ? new float[] { 22f, 6f } : i == 1 ? new float[] { 3f, 5f } : new float[] { 40f, 12f, 6f, 12f }, i * 7f));
                g.draw(new Ellipse2D.Double(c.x - r, c.y - r, 2 * r, 2 * r));
            }
            Path2D.Double spokes = new Path2D.Double();
            for (int i = 0; i < 16; i++) {
                double a = i * Math.PI / 8;
                spokes.append(new Line2D.Double(c.x + Math.cos(a) * 42, c.y + Math.sin(a) * 42, c.x + Math.cos(a) * (i % 2 == 0 ? 54 : 48), c.y + Math.sin(a) * (i % 2 == 0 ? 54 : 48)), false);
            }
            draw(spokes, alpha(pale, 170), 1.2);
            glow(new Ellipse2D.Double(c.x - 40, c.y - 40, 80, 80), alpha(pale, 230), 1.6, 3);
            fill(hexagon(c.x, c.y, 9, 30), alpha(pale, 200));
            tag("ATTENTION HUB", c.x, c.y - 84, pale);
        }
    }

    // ==================================================================================================== 4. Singularity
    private static final class Singularity extends Painter {
        final SingularityCore sc;
        final Color violet = c(0xb090ff), magenta = c(0xff4bd8), hot = c(0xffc46a);
        final double R = SingularityCore.ARENA_RADIUS;

        Singularity(SingularityCore sc, Graphics2D g) { super(sc, g, c(0x07050e), c(0x8a6cff), c(0x7a5fe0)); this.sc = sc; }

        @Override boolean extraClear(double x, double y, double r) {
            double d = new Vec(x, y).dist(sc.getCenter());
            return d <= R - 24 - r && d >= 76 + r;
        }

        void draw() {
            Vec c = sc.getCenter();
            fill(new Rectangle2D.Double(0, 0, W, H), bg);
            glowBlob(150, 140, 360, new Color(255, 75, 216, 30));
            glowBlob(1080, 780, 380, new Color(60, 120, 255, 30));
            glowBlob(1100, 120, 260, new Color(140, 90, 255, 26));
            stars(null, 520, violet);
            Ellipse2D.Double arena = new Ellipse2D.Double(c.x - R, c.y - R, 2 * R, 2 * R);
            g.setPaint(new RadialGradientPaint(new Point2D.Double(c.x, c.y), (float) R,
                new float[] { 0f, 0.18f, 0.45f, 0.9f, 1f },
                new Color[] { c(0x4a1f80), c(0x22123f), c(0x150c2b), c(0x1a1030), c(0x2a1850) }, MultipleGradientPaint.CycleMethod.NO_CYCLE));
            g.fill(arena);
            Shape old = g.getClip();
            g.clip(arena);
            polarGrid(c);
            accretionSwirl(c);
            g.setClip(old);
            rim(c);
            vignette(110);
            track(0.5, violet);
            for (Path r : map.getRoutes()) portal(r.getStart(), r.getName());
            horizon(c);
            hudFrame(violet, "SINGULARITY CORE // GRAVITY WELL ACTIVE");
            scanlines(10);
        }

        void polarGrid(Vec c) {
            Path2D.Double rings = new Path2D.Double(), spokes = new Path2D.Double(), major = new Path2D.Double();
            for (double r = 40; r < R; r += 40) rings.append(new Ellipse2D.Double(c.x - r, c.y - r, 2 * r, 2 * r), false);
            for (int i = 0; i < 48; i++) {
                double a = i * Math.PI / 24;
                (i % 6 == 0 ? major : spokes).append(new Line2D.Double(c.x + Math.cos(a) * 60, c.y + Math.sin(a) * 60, c.x + Math.cos(a) * R, c.y + Math.sin(a) * R), false);
            }
            draw(rings, alpha(violet, 26), 1);
            draw(spokes, alpha(violet, 14), 1);
            draw(major, alpha(violet, 40), 1);
            Font f = Cyber.mono(Font.PLAIN, 7);
        }

        void accretionSwirl(Vec c) {
            // faint logarithmic spiral arms being dragged into the core
            for (int arm = 0; arm < 6; arm++) {
                Path2D.Double sp = new Path2D.Double();
                double a0 = arm * Math.PI / 3;
                boolean first = true;
                for (double t = 0; t <= 1; t += 0.01) {
                    double r = 60 + (R - 70) * t, a = a0 + t * 4.2;
                    double x = c.x + Math.cos(a) * r, y = c.y + Math.sin(a) * r;
                    if (first) { sp.moveTo(x, y); first = false; } else sp.lineTo(x, y);
                }
                draw(sp, alpha(arm % 2 == 0 ? magenta : violet, 22), 14);
                draw(sp, alpha(arm % 2 == 0 ? magenta : violet, 45), 1.2);
            }
            glowBlob(c.x, c.y, 200, new Color(255, 196, 106, 40));
        }

        void rim(Vec c) {
            Ellipse2D.Double outer = new Ellipse2D.Double(c.x - R, c.y - R, 2 * R, 2 * R);
            draw(outer, c(0x1b1236), 18);
            g.setColor(alpha(violet, 150));
            g.setStroke(new BasicStroke(6f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 30f, 8f, 4f, 8f }, 0f));
            g.draw(outer);
            Path2D.Double ticks = new Path2D.Double();
            for (int i = 0; i < 120; i++) {
                double a = i * Math.PI / 60, r0 = R + 10, r1 = R + (i % 5 == 0 ? 20 : 14);
                ticks.append(new Line2D.Double(c.x + Math.cos(a) * r0, c.y + Math.sin(a) * r0, c.x + Math.cos(a) * r1, c.y + Math.sin(a) * r1), false);
            }
            draw(ticks, alpha(violet, 120), 1);
            glow(new Ellipse2D.Double(c.x - R - 9, c.y - R - 9, 2 * R + 18, 2 * R + 18), alpha(violet, 200), 1.4, 2.5);
            glow(new Ellipse2D.Double(c.x - R + 9, c.y - R + 9, 2 * R - 18, 2 * R - 18), alpha(magenta, 120), 1, 2);
        }

        void portal(Vec p, String name) {
            glowBlob(p.x, p.y, 70, new Color(176, 144, 255, 70));
            fill(hexagon(p.x, p.y, 32, 0), alpha(c(0x4020a0), 90));
            glow(hexagon(p.x, p.y, 32, 0), alpha(c(0xc0a0ff), 230), 2, 2.6);
            for (int i = 0; i < 3; i++) {
                Arc2D.Double arc = new Arc2D.Double(p.x - 40, p.y - 40, 80, 80, i * 120 + 15, 80, Arc2D.OPEN);
                glow(arc, alpha(magenta, 200), 2, 2);
            }
            double ang = Math.atan2(p.y - 450, p.x - 600);
            double lx = p.x + Math.cos(ang) * 0 + (Math.abs(Math.cos(ang)) > 0.5 ? 0 : 44), ly = p.y + (Math.abs(Math.cos(ang)) > 0.5 ? (Math.cos(ang) > 0 ? -48 : 56) : 4);
            tag(name, lx + (Math.abs(Math.cos(ang)) > 0.5 ? 0 : 30), ly - 4, c(0xc0a0ff));
        }

        void horizon(Vec c) {
            // lensing halo, photon ring, event horizon
            g.setPaint(new RadialGradientPaint(new Point2D.Double(c.x, c.y), 96f, new float[] { 0f, 0.45f, 0.55f, 0.75f, 1f },
                new Color[] { new Color(0, 0, 0, 255), new Color(0, 0, 0, 255), new Color(255, 196, 106, 200), new Color(255, 75, 216, 90), new Color(120, 60, 255, 0) }));
            g.fill(new Ellipse2D.Double(c.x - 96, c.y - 96, 192, 192));
            glow(new Ellipse2D.Double(c.x - 45, c.y - 45, 90, 90), alpha(c(0xffe6c0), 230), 1.6, 3);
            g.setColor(alpha(hot, 170));
            g.setStroke(new BasicStroke(3f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10f, new float[] { 26f, 14f }, 0f));
            g.draw(new Ellipse2D.Double(c.x - 56, c.y - 56, 112, 112));
            g.setColor(alpha(magenta, 140));
            g.setStroke(new BasicStroke(1.4f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10f, new float[] { 4f, 6f }, 0f));
            g.draw(new Ellipse2D.Double(c.x - 70, c.y - 70, 140, 140));
            fill(new Ellipse2D.Double(c.x - 30, c.y - 30, 60, 60), Color.BLACK);
            tag("EVENT HORIZON", c.x, c.y + 94, hot);
        }
    }

    // ==================================================================================================== 5. Silicon Valley
    private static final class Valley extends Painter {
        final SiliconValley sv;
        final Color cyan = c(0x5fd4ff), magenta = c(0xff4bd8), glass = c(0x9fdcff), lime = c(0x7dffb0);

        Valley(SiliconValley sv, Graphics2D g) { super(sv, g, c(0x0b1424), c(0x5fd4ff), c(0x3fb8ff)); this.sv = sv; }

        void draw() {
            g.setPaint(new GradientPaint(0, 0, c(0x101d36), 0, (float) H, c(0x070c18)));
            g.fill(new Rectangle2D.Double(0, 0, W, H));
            // campus paving: fine grid with brighter block lines, glowing circuit inlays
            grid(20, 100, cyan, 9, 22);
            glowBlob(250, 650, 420, new Color(255, 75, 216, 22));
            glowBlob(950, 300, 460, new Color(95, 212, 255, 24));
            circuit(70, alpha(cyan, 70), new Color(0, 0, 0, 90), alpha(cyan, 160), c(0x07101e));
            plazas();
            planters();
            parkedCars();
            vignette(130);
            lamps();
            track(0.72, cyan);
            laneMarks();
            for (Obstacle o : map.getObstacles()) building(o);
            for (double[] b : sv.getSkybridges()) skybridge(b);
            holos();
            arms();
            hudFrame(cyan, "INNOVATION DISTRICT // CAMPUS 01");
            scanlines(9);
        }

        void plazas() {
            int made = 0;
            for (int tries = 0; made < 7 && tries < 600; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H, r = 34 + rnd.nextDouble() * 16;
                if (!clear(x, y, r)) continue;
                fill(hexagon(x, y, r, 30), new Color(20, 40, 70, 120));
                draw(hexagon(x, y, r, 30), alpha(cyan, 70), 1);
                draw(hexagon(x, y, r * 0.62, 30), alpha(cyan, 40), 1);
                fill(new Ellipse2D.Double(x - 3, y - 3, 6, 6), alpha(cyan, 160));
                made++;
            }
        }

        void planters() {
            int made = 0;
            for (int tries = 0; made < 18 && tries < 900; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (!clear(x, y, 12)) continue;
                fill(new Ellipse2D.Double(x - 11, y - 11, 22, 22), c(0x0e1a24));
                draw(new Ellipse2D.Double(x - 11, y - 11, 22, 22), alpha(lime, 150), 1.2);
                glowBlob(x, y, 16, new Color(80, 255, 160, 40));
                for (int k = 0; k < 5; k++) {
                    double a = rnd.nextDouble() * Math.PI * 2, d = rnd.nextDouble() * 4;
                    fill(new Ellipse2D.Double(x + Math.cos(a) * d - 5, y + Math.sin(a) * d - 5, 10, 10), alpha(Cyber.lerp(c(0x1f8a52), lime, rnd.nextDouble() * 0.5), 210));
                }
                made++;
            }
        }

        void parkedCars() {
            Color[] cols = { c(0xe8eef6), c(0x2b6cff), c(0xff4bd8), c(0x1d2230), c(0xffd84a) };
            int made = 0;
            for (int tries = 0; made < 9 && tries < 600; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (!clear(x, y, 13)) continue;
                car(x, y, rnd.nextInt(4) * 90, cols[rnd.nextInt(cols.length)]);
                made++;
            }
        }

        void lamps() {
            Path r = map.getRoutes().get(0);
            boolean side = false;
            for (double d = 60; d < r.getTotalLength(); d += 110, side = !side) {
                Vec p = r.positionAt(d), dir = r.directionAt(d);
                double s = side ? 1 : -1, off = HW + 10;
                double x = p.x - dir.y * off * s, y = p.y + dir.x * off * s;
                Vec q = new Vec(x, y);
                if (r.distanceToPoint(q) < HW + 6 || x < 6 || y < 6 || x > W - 6 || y > H - 6) continue;
                boolean blocked = false;
                for (Obstacle o : map.getObstacles()) if (o.contains(q, 2)) blocked = true;
                if (blocked) continue;
                glowBlob(x, y, 26, new Color(160, 230, 255, 46));
                fill(new Ellipse2D.Double(x - 3, y - 3, 6, 6), c(0x1a2436));
                fill(new Ellipse2D.Double(x - 1.6, y - 1.6, 3.2, 3.2), new Color(0xeaffff));
            }
        }

        void laneMarks() {
            // zebra crossing near the entry and a "SLOW - AV ZONE" stencil near the exit
            Path r = map.getRoutes().get(0);
            for (double d : new double[] { 140, r.getTotalLength() - 150 }) {
                Vec p = r.positionAt(d), dir = r.directionAt(d), n = new Vec(-dir.y, dir.x);
                Path2D.Double z = new Path2D.Double();
                for (int i = -3; i <= 3; i++) {
                    double ox = n.x * i * 6, oy = n.y * i * 6;
                    z.append(new Line2D.Double(p.x + ox - dir.x * 7, p.y + oy - dir.y * 7, p.x + ox + dir.x * 7, p.y + oy + dir.y * 7), false);
                }
                draw(z, new Color(255, 255, 255, 70), 3);
            }
        }

        void building(Obstacle o) {
            String l = o.label == null ? "" : o.label;
            double x = o.x, y = o.y, w = o.w, h = o.h, ex = 6, ey = 8;
            glowBlob(x + w / 2, y + h / 2, Math.max(w, h) * 0.75, alpha(cyan, 20));
            // walls seen below / right of the roof (oblique height), with lit window rows
            Path2D.Double wall = new Path2D.Double();
            wall.moveTo(x, y + h); wall.lineTo(x + w, y + h); wall.lineTo(x + w, y);
            wall.lineTo(x + w + ex, y + ey); wall.lineTo(x + w + ex, y + h + ey); wall.lineTo(x + ex, y + h + ey); wall.closePath();
            fill(wall, c(0x0c1424));
            Path2D.Double win = new Path2D.Double();
            for (double wx = x + ex + 3; wx < x + w + ex - 3; wx += 6) if (rnd.nextDouble() < 0.7) win.append(new Rectangle2D.Double(wx, y + h + 2, 3, ey - 4), false);
            for (double wy = y + ey + 3; wy < y + h + ey - 3; wy += 6) if (rnd.nextDouble() < 0.7) win.append(new Rectangle2D.Double(x + w + 2, wy, ex - 3, 3), false);
            fill(win, alpha(rnd.nextBoolean() ? cyan : c(0xffe6a8), 150));
            // roof
            Rectangle2D.Double roof = new Rectangle2D.Double(x, y, w, h);
            Color r0 = c(0x1c2a42), r1 = c(0x111a2c);
            if (l.contains("HQ")) { r0 = c(0x24395c); r1 = c(0x14223a); }
            if (l.contains("SERVER") || l.contains("DATA")) { r0 = c(0x1a2230); r1 = c(0x0f141e); }
            g.setPaint(new GradientPaint((float) x, (float) y, r0, (float) (x + w), (float) (y + h), r1));
            g.fill(roof);
            Shape old = g.getClip();
            g.clip(roof);
            if (l.contains("HQ")) hq(x, y, w, h);
            else if (l.contains("SERVER") || l.contains("DATA")) serverRoof(x, y, w, h);
            else if (l.contains("LAB")) lab(x, y, w, h, l.contains("ROBOTICS"));
            else if (l.contains("DEPOT") || l.contains("CHARGING")) parking(x, y, w, h);
            else if (l.contains("HOLO")) billboard(x, y, w, h);
            g.setClip(old);
            glow(roof, alpha(cyan, 200), 1.4, 2);
            draw(new Line2D.Double(x, y, x + w, y), new Color(255, 255, 255, 70), 1);
            if (!l.contains("HOLO")) {
                tag(l, x + 5, y + 15, cyan, false);
            }
        }

        void hq(double x, double y, double w, double h) {
            // glass curtain wall reflections and stepped setbacks
            Path2D.Double refl = new Path2D.Double();
            for (double k = -h; k < w; k += 18) refl.append(new Line2D.Double(x + k, y + h, x + k + h, y), false);
            draw(refl, new Color(160, 220, 255, 22), 6);
            Rectangle2D.Double t1 = new Rectangle2D.Double(x + 12, y + 20, w - 24, h - 30), t2 = new Rectangle2D.Double(x + 26, y + 32, w - 52, h - 54);
            fill(t1, new Color(40, 70, 110, 120));
            draw(t1, alpha(glass, 120), 1);
            fill(t2, new Color(60, 100, 150, 120));
            draw(t2, alpha(glass, 160), 1);
            double cx = x + w / 2, cy = y + 32 + (h - 54) / 2, rr = Math.min(t2.width, t2.height) * 0.36;
            draw(new Ellipse2D.Double(cx - rr, cy - rr, 2 * rr, 2 * rr), alpha(Cyber.YELLOW, 200), 1.6);
            textCentered("H", cx, cy + rr * 0.42, Cyber.display(Font.BOLD, (int) Math.max(8, rr * 1.2)), alpha(Cyber.YELLOW, 220));
            glowBlob(x + w - 14, y + 26, 10, alpha(Cyber.RED, 160));
            fill(new Ellipse2D.Double(x + w - 16, y + 24, 4, 4), Cyber.RED);
        }

        void serverRoof(double x, double y, double w, double h) {
            for (double fx = x + 22; fx < x + w - 14; fx += 32) {
                for (double fy = y + 28; fy < y + h - 12; fy += 32) fan(fx, fy, 12, cyan);
            }
            fill(new Rectangle2D.Double(x, y + h - 5, w, 3), alpha(Cyber.GREEN, 140));
        }

        void lab(double x, double y, double w, double h, boolean robotics) {
            // solar strip + glass dome
            Path2D.Double solar = new Path2D.Double();
            for (double sx = x + 6; sx < x + w * 0.45; sx += 11) solar.append(new Rectangle2D.Double(sx, y + 20, 9, h - 28), false);
            fill(solar, c(0x16264a));
            draw(solar, alpha(glass, 90), 0.8);
            double cx = x + w * 0.72, cy = y + h * 0.55, rr = Math.min(w * 0.24, h * 0.36);
            g.setPaint(new RadialGradientPaint(new Point2D.Double(cx - rr * 0.3, cy - rr * 0.3), (float) rr,
                new float[] { 0f, 1f }, new Color[] { new Color(200, 240, 255, 200), new Color(40, 110, 190, 150) }));
            g.fill(new Ellipse2D.Double(cx - rr, cy - rr, 2 * rr, 2 * rr));
            Path2D.Double ribs = new Path2D.Double();
            for (int i = 0; i < 6; i++) ribs.append(new Line2D.Double(cx, cy, cx + Math.cos(i * Math.PI / 3) * rr, cy + Math.sin(i * Math.PI / 3) * rr), false);
            ribs.append(new Ellipse2D.Double(cx - rr * 0.55, cy - rr * 0.55, rr * 1.1, rr * 1.1), false);
            draw(ribs, new Color(255, 255, 255, 80), 1);
            draw(new Ellipse2D.Double(cx - rr, cy - rr, 2 * rr, 2 * rr), alpha(glass, 230), 1.4);
            if (robotics) robotArm(x + w * 0.5, y + h * 0.3, 20, magenta);
        }

        void parking(double x, double y, double w, double h) {
            boolean vert = h > w;
            Path2D.Double bays = new Path2D.Double();
            Color[] cols = { c(0xe8eef6), c(0x2b6cff), c(0xff4bd8), c(0x3a3f4a), c(0xffd84a) };
            if (vert) {
                for (double by = y + 20; by < y + h - 4; by += 26) {
                    bays.append(new Line2D.Double(x + 4, by, x + w - 4, by), false);
                    if (rnd.nextDouble() < 0.75) car(x + w / 2, by + 13, 0, cols[rnd.nextInt(cols.length)]);
                }
            } else {
                for (double bx = x + 6; bx < x + w - 4; bx += 26) {
                    bays.append(new Line2D.Double(bx, y + 20, bx, y + h - 4), false);
                    if (rnd.nextDouble() < 0.7 && bx + 26 < x + w) car(bx + 13, y + h / 2 + 8, 90, cols[rnd.nextInt(cols.length)]);
                }
            }
            draw(bays, new Color(255, 255, 255, 90), 1);
            // charging posts
            for (int i = 0; i < 3; i++) {
                double px = vert ? x + 6 : x + 16 + i * (w - 30) / 2.0, py = vert ? y + 32 + i * (h - 50) / 2.0 : y + 22;
                glowBlob(px, py, 7, new Color(60, 255, 140, 120));
                fill(new Rectangle2D.Double(px - 2, py - 2, 4, 4), Cyber.GREEN);
            }
        }

        void billboard(double x, double y, double w, double h) {
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x3a0f60), (float) (x + w), (float) y, c(0x0f3a66)));
            g.fill(new Rectangle2D.Double(x, y, w, h));
            Path2D.Double lines = new Path2D.Double();
            for (double yy = y + 2; yy < y + h; yy += 3) lines.append(new Line2D.Double(x, yy, x + w, yy), false);
            draw(lines, new Color(255, 255, 255, 20), 1);
            textCentered("SCALE IS", x + w / 2, y + h * 0.36, Cyber.display(Font.BOLD, 15), new Color(255, 255, 255, 240));
            textCentered("ALL YOU NEED", x + w / 2, y + h * 0.62, Cyber.display(Font.BOLD, 15), new Color(255, 255, 255, 240));
            textCentered("NOW SHIPPING", x + w / 2, y + h * 0.88, Cyber.mono(Font.BOLD, 11), Cyber.lerp(cyan, Color.WHITE, 0.4));
            glowBlob(x + w / 2, y + h / 2, w * 0.5, alpha(magenta, 40));
        }

        void skybridge(double[] b) {
            double x = b[0], y = b[1], w = b[2], h = b[3];
            g.translate(5, 7);
            fill(new Rectangle2D.Double(x, y, w, h), new Color(0, 0, 0, 70));
            g.translate(-5, -7);
            Rectangle2D.Double glassR = new Rectangle2D.Double(x, y, w, h);
            g.setPaint(new GradientPaint((float) x, (float) y, new Color(170, 225, 255, 70), (float) x, (float) (y + h), new Color(80, 150, 220, 40)));
            g.fill(glassR);
            Path2D.Double mull = new Path2D.Double();
            boolean horiz = w > h;
            if (horiz) for (double mx = x + 10; mx < x + w; mx += 10) mull.append(new Line2D.Double(mx, y, mx, y + h), false);
            else for (double my = y + 10; my < y + h; my += 10) mull.append(new Line2D.Double(x, my, x + w, my), false);
            draw(mull, new Color(200, 240, 255, 60), 1);
            draw(glassR, alpha(glass, 200), 1.6);
            draw(horiz ? new Line2D.Double(x, y + 2, x + w, y + 2) : new Line2D.Double(x + 2, y, x + 2, y + h), new Color(255, 255, 255, 110), 1);
        }

        void holos() {
            String[] ads = { "AGI SOON", "50% OFF", "HIRE AN AI", "GPU CLOUD" };
            List<Rectangle2D> used = new ArrayList<>();
            int made = 0;
            for (int tries = 0; made < ads.length && tries < 1500; tries++) {
                double w = Math.max(64, textWidth(ads[made], Cyber.display(Font.BOLD, 14)) + 22), h = 30;
                double x = rnd.nextDouble() * (W - w), y = rnd.nextDouble() * (H - h - 16);
                if (!clear(x + w / 2, y + h / 2, w / 2 + 8)) continue;
                Rectangle2D box = new Rectangle2D.Double(x - 24, y - 24, w + 48, h + 56);
                boolean hit = false;
                for (Rectangle2D u : used) if (u.intersects(box)) { hit = true; break; }
                if (hit) continue;
                used.add(box);
                holo(x, y, w, h, made % 2 == 0 ? magenta : cyan, made % 2 == 0 ? cyan : magenta, ads[made], null);
                made++;
            }
        }

        void arms() {
            int made = 0;
            for (int tries = 0; made < 3 && tries < 600; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (!clear(x, y, 34)) continue;
                robotArm(x, y, rnd.nextInt(360), cyan);
                made++;
            }
        }
    }

    // ==================================================================================================== 6. Neural Network
    private static final class Neural extends Painter {
        final NeuralNetwork nn;
        final Color cyan = c(0x38e8ff), magenta = c(0xff4bd8), violet = c(0x8a5cff);

        Neural(NeuralNetwork nn, Graphics2D g) { super(nn, g, c(0x060818), c(0x38e8ff), c(0x38e8ff)); this.nn = nn; }

        @Override boolean extraClear(double x, double y, double r) {
            Vec p = new Vec(x, y);
            for (Vec v : nn.getNeurons()) if (p.dist(v) < 52 + r) return false;
            return true;
        }

        void draw() {
            g.setPaint(new RadialGradientPaint(new Point2D.Double(600, 450), 780f, new float[] { 0f, 0.6f, 1f },
                new Color[] { c(0x0e1430), c(0x070a1c), c(0x020309) }));
            g.fill(new Rectangle2D.Double(0, 0, W, H));
            glowBlob(220, 450, 380, new Color(56, 232, 255, 26));
            glowBlob(760, 200, 360, new Color(255, 75, 216, 22));
            glowBlob(860, 760, 380, new Color(138, 92, 255, 30));
            hexGrid(30, alpha(violet, 14), 1);
            binaryRain();
            weights();
            platforms();
            fragments();
            vignette(150);
            track(0.58, cyan);
            for (int i = 0; i < nn.getNeurons().size(); i++) neuron(nn.getNeurons().get(i), i);
            ports();
            hudFrame(cyan, "INSIDE THE MACHINE // FORWARD PASS");
            scanlines(10);
        }

        void binaryRain() {
            Font f = Cyber.mono(Font.PLAIN, 10);
            g.setFont(f);
            for (double x = 12; x < W; x += 26) {
                if (rnd.nextDouble() < 0.35) continue;
                double y0 = rnd.nextDouble() * H;
                int len = 6 + rnd.nextInt(16);
                for (int k = 0; k < len; k++) {
                    double y = y0 - k * 12;
                    if (y < 0) break;
                    int a = (int) (150 * (1 - k / (double) len));
                    g.setColor(k == 0 ? new Color(220, 255, 255, 170) : alpha(rnd.nextDouble() < 0.15 ? magenta : cyan, Math.max(14, a / 2)));
                    g.drawString(rnd.nextBoolean() ? "1" : "0", (float) x, (float) y);
                }
            }
        }

        /** Faint fully-connected weights between consecutive layers: the network diagram behind the pathways. */
        void weights() {
            Vec[][] layers = { { NeuralNetwork.IN_A, NeuralNetwork.IN_B }, { NeuralNetwork.J1, NeuralNetwork.J2 },
                { NeuralNetwork.H1, NeuralNetwork.H2, NeuralNetwork.H3 }, { NeuralNetwork.H4, NeuralNetwork.H5 }, { NeuralNetwork.OUT } };
            // a few "ghost" neurons per layer, off the playable paths
            for (int li = 0; li + 1 < layers.length; li++) {
                for (Vec a : layers[li]) {
                    for (Vec b : layers[li + 1]) {
                        g.setPaint(new GradientPaint((float) a.x, (float) a.y, alpha(cyan, 40), (float) b.x, (float) b.y, alpha(magenta, 40)));
                        g.setStroke(round(1.2));
                        g.draw(new Line2D.Double(a.x, a.y, b.x, b.y));
                    }
                }
            }
            double[] xs = { 240, 480, 780, 990 };
            for (double x : xs) {
                for (int k = 0; k < 3; k++) {
                    double y = 60 + rnd.nextDouble() * 780;
                    if (!clear(x, y, 10)) continue;
                    glowBlob(x, y, 22, alpha(violet, 70));
                    fill(new Ellipse2D.Double(x - 6, y - 6, 12, 12), c(0x1a1440));
                    draw(new Ellipse2D.Double(x - 6, y - 6, 12, 12), alpha(violet, 200), 1.2);
                    for (Vec v : nn.getNeurons()) {
                        if (Math.abs(v.x - x) < 1 || Math.abs(v.x - x) > 320) continue;
                        draw(new Line2D.Double(x, y, v.x, v.y), alpha(violet, 18), 1);
                    }
                }
            }
        }

        void platforms() {
            int made = 0;
            for (int tries = 0; made < 12 && tries < 1200; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H, r = 22 + rnd.nextDouble() * 10;
                if (!clear(x, y, r)) continue;
                g.translate(0, 5);
                fill(hexagon(x, y, r, 30), new Color(0, 0, 0, 120));
                g.translate(0, -5);
                g.setPaint(new GradientPaint((float) x, (float) (y - r), new Color(40, 50, 110, 200), (float) x, (float) (y + r), new Color(18, 20, 50, 200)));
                g.fill(hexagon(x, y, r, 30));
                glow(hexagon(x, y, r, 30), alpha(made % 3 == 0 ? magenta : cyan, 190), 1.2, 2);
                draw(hexagon(x, y, r * 0.6, 30), alpha(cyan, 60), 1);
                Path2D.Double spokes = new Path2D.Double();
                for (int i = 0; i < 6; i++) {
                    double a = Math.toRadians(30 + i * 60);
                    spokes.append(new Line2D.Double(x + Math.cos(a) * r * 0.6, y + Math.sin(a) * r * 0.6, x + Math.cos(a) * r, y + Math.sin(a) * r), false);
                }
                draw(spokes, alpha(cyan, 50), 1);
                made++;
            }
        }

        void fragments() {
            String[] bits = { "[0.42]", "w=1.7", "relu", "dL/dw", "bias +0.3", "0x3F", "softmax", "[ ]", "epoch 812", "lr 3e-4", "grad", "{ }" };
            Font f = Cyber.mono(Font.BOLD, 11);
            List<Rectangle2D> used = new ArrayList<>();
            int made = 0;
            for (int tries = 0; made < 20 && tries < 1500; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                boolean box = rnd.nextDouble() < 0.4;
                String s = bits[rnd.nextInt(bits.length)];
                double tw = box ? 10 : textWidth(s, f);
                if (!clear(x + tw / 2, y - 3, tw / 2 + 10)) continue;
                Rectangle2D r = new Rectangle2D.Double(x - 14, y - 26, tw + 28, 40);
                boolean hit = false;
                for (Rectangle2D u : used) if (u.intersects(r)) { hit = true; break; }
                if (hit) continue;
                used.add(r);
                Color c = rnd.nextBoolean() ? cyan : magenta;
                if (box) {
                    AffineTransform old = g.getTransform();
                    g.rotate(rnd.nextDouble() * Math.PI, x + 5, y - 5);
                    draw(new Rectangle2D.Double(x, y - 10, 10, 10), alpha(c, 140), 1.2);
                    fill(new Rectangle2D.Double(x + 3, y - 7, 4, 4), alpha(c, 110));
                    g.setTransform(old);
                } else {
                    fill(new RoundRectangle2D.Double(x - 5, y - 13, tw + 10, 18, 5, 5), new Color(3, 6, 16, 215));
                    draw(new RoundRectangle2D.Double(x - 5, y - 13, tw + 10, 18, 5, 5), alpha(c, 140), 1);
                    text(s, x, y, f, Cyber.lerp(c, Color.WHITE, 0.45));
                }
                made++;
            }
        }

        void neuron(Vec p, int i) {
            boolean out = p == NeuralNetwork.OUT;
            double r = out ? 44 : 36;
            Color core = out ? c(0xffd84a) : magenta;
            glowBlob(p.x, p.y, r * 2.6, alpha(core, 60));
            // dendrites
            Path2D.Double den = new Path2D.Double();
            for (int k = 0; k < 14; k++) {
                double a = k * Math.PI * 2 / 14 + i;
                double r0 = r + 2, r1 = r + 9 + (k % 3) * 5;
                den.moveTo(p.x + Math.cos(a) * r0, p.y + Math.sin(a) * r0);
                den.quadTo(p.x + Math.cos(a + 0.12) * (r0 + r1) / 2, p.y + Math.sin(a + 0.12) * (r0 + r1) / 2, p.x + Math.cos(a + 0.2) * r1, p.y + Math.sin(a + 0.2) * r1);
            }
            draw(den, alpha(Cyber.lerp(core, Color.WHITE, 0.3), 150), 1.4);
            g.setPaint(new RadialGradientPaint(new Point2D.Double(p.x, p.y), (float) r, new float[] { 0f, 0.35f, 0.8f, 1f },
                new Color[] { new Color(255, 255, 255, 230), alpha(core, 200), alpha(Cyber.lerp(core, violet, 0.6), 120), alpha(violet, 40) }));
            g.fill(new Ellipse2D.Double(p.x - r, p.y - r, 2 * r, 2 * r));
            glow(new Ellipse2D.Double(p.x - r, p.y - r, 2 * r, 2 * r), alpha(cyan, 230), 1.8, 2.5);
            g.setColor(alpha(Color.WHITE, 140));
            g.setStroke(new BasicStroke(1.2f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 6f, 5f }, i * 3f));
            g.draw(new Ellipse2D.Double(p.x - r * 0.68, p.y - r * 0.68, r * 1.36, r * 1.36));
            String[] names = { "J1", "J2", "H1", "H2", "H3", "H4", "H5", "OUT" };
            String n = i < names.length ? names[i] : "N";
            tag(n, p.x, p.y - r - 14, cyan);
        }

        void ports() {
            for (Vec p : new Vec[] { NeuralNetwork.IN_A, NeuralNetwork.IN_B, NeuralNetwork.EXIT }) {
                boolean in = p.x < W / 2;
                Color c = in ? Cyber.GREEN : Cyber.RED;
                glowBlob(p.x, p.y, 70, alpha(c, 50));
                g.setColor(alpha(c, 200));
                g.setStroke(round(3));
                g.draw(new Arc2D.Double(p.x - 40, p.y - 40, 80, 80, in ? -70 : 110, 140, Arc2D.OPEN));
                tag(in ? (p.y < H / 2 ? "INPUT A" : "INPUT B") : "OUTPUT", in ? p.x + 62 : p.x - 66, p.y - 52, c);
            }
        }
    }

    // ==================================================================================================== 7. Abandoned Data Center
    /** Flickering light spots per map name (filled while the art renders, read by {@link Pulses}). */
    private static final Map<String, List<double[]>> FLICKER = new java.util.HashMap<>();

    private static final class Graveyard extends Painter {
        final AbandonedDataCenter dc;
        final Color amber = c(0xffb43b), cold = c(0x7fd6ff), dead = c(0x2a2e33);
        final List<double[]> lights = new ArrayList<>();

        Graveyard(AbandonedDataCenter dc, Graphics2D g) { super(dc, g, c(0x0b0d10), c(0xffb43b), c(0x9aa4b0)); this.dc = dc; }

        void draw() {
            fill(new Rectangle2D.Double(0, 0, W, H), bg);
            floorTiles();
            cables();
            glowBlob(600, 120, 260, new Color(127, 214, 255, 30));
            glowBlob(210, 470, 200, new Color(255, 180, 59, 22));
            glowBlob(990, 450, 220, new Color(127, 214, 255, 22));
            glowBlob(600, 820, 220, new Color(255, 80, 60, 18));
            debris();
            vignette(175);
            track(0.62, amber);
            for (int i = 0; i < dc.getHazards().size(); i++) hazardMarks(dc.getHazards().get(i), false);
            for (Obstacle o : map.getObstacles()) {
                String l = o.label == null ? "" : o.label;
                if (l.startsWith("COOLING")) coolingPlant(o);
                else if (l.startsWith("UPS")) ups(o);
                else rack(o);
            }
            props();
            for (int i = 0; i < dc.getHazards().size(); i++) hazardMarks(dc.getHazards().get(i), true);
            hudFrame(amber, "SERVER GRAVEYARD // SECTOR 7 // POWER 12%");
            scanlines(14);
            synchronized (FLICKER) { FLICKER.put(map.getName(), lights); }
        }

        void floorTiles() {
            Path2D.Double seams = new Path2D.Double();
            for (double x = 0; x <= W; x += 40) seams.append(new Line2D.Double(x, 0, x, H), false);
            for (double y = 0; y <= H; y += 40) seams.append(new Line2D.Double(0, y, W, y), false);
            Path2D.Double holes = new Path2D.Double();
            for (double tx = 0; tx < W; tx += 40) {
                for (double ty = 0; ty < H; ty += 40) {
                    double v = rnd.nextDouble();
                    if (v < 0.12) {   // perforated airflow tile
                        for (double hx = tx + 6; hx < tx + 36; hx += 6) for (double hy = ty + 6; hy < ty + 36; hy += 6) holes.append(new Ellipse2D.Double(hx - 1.2, hy - 1.2, 2.4, 2.4), false);
                    } else if (v < 0.3) {
                        fill(new Rectangle2D.Double(tx + 1, ty + 1, 38, 38), new Color(255, 255, 255, 6 + rnd.nextInt(8)));
                    } else if (v < 0.36) {
                        fill(new Rectangle2D.Double(tx + 1, ty + 1, 38, 38), new Color(0, 0, 0, 60));   // grime
                    }
                }
            }
            fill(holes, new Color(0, 0, 0, 160));
            draw(seams, new Color(0, 0, 0, 170), 2);
            g.translate(1, 1);
            draw(seams, new Color(255, 255, 255, 10), 1);
            g.translate(-1, -1);
            // a few lifted / missing tiles showing the cable void
            int made = 0;
            for (int tries = 0; made < 5 && tries < 400; tries++) {
                double tx = Math.floor(rnd.nextDouble() * W / 40) * 40, ty = Math.floor(rnd.nextDouble() * H / 40) * 40;
                if (!clear(tx + 20, ty + 20, 22)) continue;
                fill(new Rectangle2D.Double(tx + 2, ty + 2, 36, 36), c(0x030405));
                for (int k = 0; k < 3; k++) draw(new Line2D.Double(tx + 4, ty + 8 + k * 11, tx + 36, ty + 12 + k * 9), new Color[] { c(0x5a1a1a), c(0x1a3a5a), c(0x5a5a1a) }[k], 3);
                AffineTransform old = g.getTransform();
                g.rotate(Math.toRadians(12 + rnd.nextInt(20)), tx + 40, ty + 20);
                fill(new Rectangle2D.Double(tx + 30, ty + 6, 36, 36), c(0x1c2025));
                draw(new Rectangle2D.Double(tx + 30, ty + 6, 36, 36), c(0x3a3f46), 1);
                g.setTransform(old);
                made++;
            }
        }

        void cables() {
            Color[] sheath = { c(0x8a2a2a), c(0x2a4a8a), c(0x8a7a2a), c(0x3a3f46), c(0x2a6a3a) };
            for (int i = 0; i < 18; i++) {
                double x0 = rnd.nextDouble() * W, y0 = rnd.nextDouble() * H;
                double x1 = x0 + (rnd.nextDouble() - 0.5) * 360, y1 = y0 + (rnd.nextDouble() - 0.5) * 360;
                Path2D.Double cab = new Path2D.Double();
                cab.moveTo(x0, y0);
                cab.curveTo(x0 + (rnd.nextDouble() - 0.5) * 240, y0 + (rnd.nextDouble() - 0.5) * 240, x1 + (rnd.nextDouble() - 0.5) * 240, y1 + (rnd.nextDouble() - 0.5) * 240, x1, y1);
                double w = 2.5 + rnd.nextDouble() * 3;
                Color sc = sheath[rnd.nextInt(sheath.length)];
                draw(cab, new Color(0, 0, 0, 150), w + 2.5);
                draw(cab, sc, w);
                draw(cab, alpha(Cyber.lerp(sc, Color.WHITE, 0.4), 60), w * 0.3);
                if (rnd.nextDouble() < 0.45 && clear(x1, y1, 6)) frayed(x1, y1);
            }
        }

        void frayed(double x, double y) {
            Path2D.Double wires = new Path2D.Double();
            for (int k = 0; k < 5; k++) {
                double a = rnd.nextDouble() * Math.PI * 2;
                wires.append(new Line2D.Double(x, y, x + Math.cos(a) * (5 + rnd.nextDouble() * 5), y + Math.sin(a) * (5 + rnd.nextDouble() * 5)), false);
            }
            draw(wires, c(0xd08a4a), 1.2);
            spark(x, y, 9);
        }

        void spark(double x, double y, double r) {
            glowBlob(x, y, r * 2.4, new Color(255, 230, 140, 90));
            Path2D.Double rays = new Path2D.Double();
            for (int k = 0; k < 7; k++) {
                double a = rnd.nextDouble() * Math.PI * 2, l = r * (0.5 + rnd.nextDouble() * 0.7);
                rays.append(new Line2D.Double(x, y, x + Math.cos(a) * l, y + Math.sin(a) * l), false);
            }
            draw(rays, new Color(255, 245, 200, 220), 1);
            fill(new Ellipse2D.Double(x - 1.6, y - 1.6, 3.2, 3.2), Color.WHITE);
            lights.add(new double[] { x, y, 1, 0xffe08a });
        }

        void debris() {
            int made = 0;
            for (int tries = 0; made < 26 && tries < 1500; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (!clear(x, y, 5)) continue;
                AffineTransform old = g.getTransform();
                g.rotate(rnd.nextDouble() * Math.PI, x, y);
                double w = 4 + rnd.nextDouble() * 9, h = 2 + rnd.nextDouble() * 4;
                fill(new Rectangle2D.Double(x - w / 2, y - h / 2, w, h), rnd.nextBoolean() ? c(0x3a3f46) : c(0x1e3a22));
                g.setTransform(old);
                made++;
            }
        }

        /** {@code labels == false} draws the striped zone under the props; {@code true} draws its warning tag on top of them. */
        void hazardMarks(AbandonedDataCenter.Hazard hz, boolean labels) {
            Path r = map.getRoutes().get(0);
            Path2D zone = subPath(r, hz.from, hz.to);
            Shape band = new Area(new BasicStroke((float) (2 * HW + 10), BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND).createStrokedShape(zone));
            Color hc = c(hz.rgb);
            if (labels) { hazardLabel(hz, r, hc); return; }
            draw(band, new Color(0, 0, 0, 200), 4);
            g.setColor(alpha(Cyber.YELLOW, 220));
            g.setStroke(new BasicStroke(4f, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10f, new float[] { 7f, 7f }, 0f));
            g.draw(band);
            Shape old = g.getClip();
            g.clip(trackArea(HW));
            fill(band, alpha(hc, 22));
            g.setClip(old);
        }

        void hazardLabel(AbandonedDataCenter.Hazard hz, Path r, Color hc) {
            // tag on the side of the zone, with a warning triangle
            Vec mid = r.positionAt((hz.from + hz.to) / 2), dir = r.directionAt((hz.from + hz.to) / 2);
            double side = 1;
            Vec tagAt = new Vec(mid.x - dir.y * (HW + 28) * side, mid.y + dir.x * (HW + 28) * side);
            boolean blocked = false;
            for (Obstacle o : map.getObstacles()) if (o.contains(tagAt, 14)) blocked = true;
            if (blocked) tagAt = new Vec(mid.x + dir.y * (HW + 28), mid.y - dir.x * (HW + 28));
            Path2D.Double tri = new Path2D.Double();
            tri.moveTo(tagAt.x, tagAt.y - 11); tri.lineTo(tagAt.x + 11, tagAt.y + 8); tri.lineTo(tagAt.x - 11, tagAt.y + 8); tri.closePath();
            fill(tri, alpha(Cyber.YELLOW, 230));
            draw(tri, new Color(0, 0, 0, 220), 1.4);
            textCentered("!", tagAt.x, tagAt.y + 6, Cyber.mono(Font.BOLD, 12), Color.BLACK);
            tag(hz.kind, tagAt.x, tagAt.y + 24, hc);
            lights.add(new double[] { tagAt.x, tagAt.y - 2, 2, Cyber.YELLOW.getRGB() & 0xffffff });
        }

        void rack(Obstacle o) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            g.translate(4, 6);
            fill(new Rectangle2D.Double(x, y, w, h), new Color(0, 0, 0, 140));
            g.translate(-4, -6);
            Rectangle2D.Double body = new Rectangle2D.Double(x, y, w, h);
            g.setPaint(new GradientPaint((float) x, (float) y, c(0x23272d), (float) (x + w), (float) y, c(0x121417)));
            g.fill(body);
            draw(body, c(0x4a5058), 1.4);
            Path2D.Double units = new Path2D.Double();
            for (double uy = y + 6; uy < y + h - 4; uy += 9) units.append(new Line2D.Double(x + 5, uy, x + w - 5, uy), false);
            draw(units, new Color(0, 0, 0, 180), 1.2);
            for (double uy = y + 8; uy < y + h - 6; uy += 9) {
                double v = rnd.nextDouble();
                Color led = v < 0.62 ? dead : v < 0.78 ? Cyber.RED : v < 0.92 ? amber : Cyber.GREEN;
                fill(new Rectangle2D.Double(x + w - 10, uy, 3, 3), led);
                if (led != dead) { glowBlob(x + w - 8.5, uy + 1.5, 5, alpha(led, 90)); if (rnd.nextDouble() < 0.35) lights.add(new double[] { x + w - 8.5, uy + 1.5, 0, led.getRGB() & 0xffffff }); }
            }
            // cracked panel and a door hanging open
            Path2D.Double crack = new Path2D.Double();
            double cx = x + w * 0.3, cy = y + h * (0.3 + rnd.nextDouble() * 0.4);
            crack.moveTo(cx, cy); crack.lineTo(cx + 8, cy + 6); crack.lineTo(cx + 5, cy + 14); crack.lineTo(cx + 13, cy + 20);
            draw(crack, new Color(200, 210, 220, 90), 1);
            if (rnd.nextBoolean()) {
                AffineTransform old = g.getTransform();
                g.rotate(Math.toRadians(-14), x, y + h * 0.5);
                fill(new Rectangle2D.Double(x - 4, y + h * 0.5, 6, h * 0.42), c(0x2c3036));
                g.setTransform(old);
            }
        }

        void coolingPlant(Obstacle o) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            glowBlob(x + w / 2, y + h / 2, w * 0.9, new Color(127, 214, 255, 40));
            Rectangle2D.Double body = new Rectangle2D.Double(x, y, w, h);
            fill(body, c(0x1a1f25));
            // hazard-striped border
            Shape old = g.getClip();
            Area border = new Area(body);
            border.subtract(new Area(new Rectangle2D.Double(x + 8, y + 8, w - 16, h - 16)));
            g.clip(border);
            fill(body, new Color(0x1a1a1a));
            Path2D.Double stripes = new Path2D.Double();
            for (double k = -h; k < w + h; k += 16) { stripes.moveTo(x + k, y); stripes.lineTo(x + k + 8, y); stripes.lineTo(x + k + 8 - h, y + h); stripes.lineTo(x + k - h, y + h); stripes.closePath(); }
            fill(stripes, alpha(Cyber.YELLOW, 150));
            g.setClip(old);
            // pipes
            Color pipe = c(0x5a6a7a);
            for (double py : new double[] { y + 30, y + h - 30 }) {
                draw(new Line2D.Double(x + 12, py, x + w - 12, py), new Color(0, 0, 0, 160), 11);
                draw(new Line2D.Double(x + 12, py, x + w - 12, py), pipe, 8);
                draw(new Line2D.Double(x + 12, py - 2, x + w - 12, py - 2), new Color(255, 255, 255, 50), 2);
                for (double jx = x + 30; jx < x + w - 20; jx += 44) fill(new Rectangle2D.Double(jx, py - 6, 5, 12), c(0x3a4550));
            }
            // two big turbines
            fan(x + w / 2, y + h * 0.36, 44, cold);
            fan(x + w / 2, y + h * 0.7, 30, cold);
            // frost
            g.setPaint(new RadialGradientPaint(new Point2D.Double(x + 24, y + h - 24), (float) (w * 0.5), new float[] { 0f, 1f },
                new Color[] { new Color(200, 240, 255, 90), new Color(200, 240, 255, 0) }));
            g.fill(body);
            draw(body, c(0x5a6470), 1.6);
            fill(new Rectangle2D.Double(x + 14, y + 12, w - 28, 14), new Color(0, 0, 0, 200));
            tag("COOLING PLANT // OFFLINE", x + w / 2, y + 19, amber);
            lights.add(new double[] { x + w - 16, y + 19, 2, amber.getRGB() & 0xffffff });
        }

        void ups(Obstacle o) {
            double x = o.x, y = o.y, w = o.w, h = o.h;
            fill(new Rectangle2D.Double(x, y, w, h), c(0x15181c));
            draw(new Rectangle2D.Double(x, y, w, h), c(0x4a5058), 1.4);
            for (int i = 0; i < 4; i++) {
                double cx = x + 6 + i * (w - 12) / 4.0, cw = (w - 12) / 4.0 - 6;
                RoundRectangle2D.Double cab = new RoundRectangle2D.Double(cx, y + 8, cw, h - 16, 4, 4);
                fill(cab, c(0x23282e));
                draw(cab, c(0x3a4048), 1);
                fill(new Rectangle2D.Double(cx + 4, y + 14, cw - 8, 10), new Color(20, 6, 6));
                text(i == 2 ? "FAULT" : "LOW", cx + 5, y + 23, Cyber.mono(Font.BOLD, 10), Cyber.RED);
                for (double by = y + 32; by < y + h - 14; by += 6) fill(new Rectangle2D.Double(cx + 4, by, (cw - 8) * (i == 2 ? 0.15 : 0.3), 3), alpha(Cyber.RED, 160));
                lights.add(new double[] { cx + cw / 2, y + 19, 1, Cyber.RED.getRGB() & 0xffffff });
            }
            tag("UPS BANK", x + 2, y + h + 14, amber, false);
        }

        void props() {
            int monitors = 0, beacons = 0, fans = 0, chassis = 0;
            for (int tries = 0; tries < 2500 && (monitors < 8 || beacons < 7 || fans < 3 || chassis < 4); tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (monitors < 8 && clear(x, y, 16)) { monitor(x, y); monitors++; continue; }
                if (beacons < 7 && clear(x, y, 8)) { beacon(x, y); beacons++; continue; }
                if (fans < 3 && clear(x, y, 26)) { fan(x, y, 22, amber); fans++; continue; }
                if (chassis < 4 && clear(x, y, 20)) { toppled(x, y); chassis++; }
            }
            int sparks = 0;
            for (int tries = 0; sparks < 6 && tries < 800; tries++) {
                double x = rnd.nextDouble() * W, y = rnd.nextDouble() * H;
                if (clear(x, y, 8)) { spark(x, y, 8 + rnd.nextDouble() * 5); sparks++; }
            }
        }

        void monitor(double x, double y) {
            AffineTransform old = g.getTransform();
            g.rotate(Math.toRadians(rnd.nextInt(50) - 25), x, y);
            fill(new RoundRectangle2D.Double(x - 14, y - 10, 28, 20, 3, 3), c(0x202428));
            draw(new RoundRectangle2D.Double(x - 14, y - 10, 28, 20, 3, 3), c(0x4a5058), 1);
            boolean on = rnd.nextDouble() < 0.55;
            Color scr = rnd.nextBoolean() ? c(0x3bff8a) : cold;
            Rectangle2D.Double screen = new Rectangle2D.Double(x - 11, y - 7.5, 22, 14);
            fill(screen, on ? alpha(scr, 70) : c(0x0a0c0e));
            if (on) {
                Path2D.Double txt = new Path2D.Double();
                for (int k = 0; k < 4; k++) txt.append(new Line2D.Double(x - 9, y - 5 + k * 3.4, x - 9 + 6 + rnd.nextDouble() * 12, y - 5 + k * 3.4), false);
                draw(txt, alpha(scr, 200), 1);
                lights.add(new double[] { x, y, 0, scr.getRGB() & 0xffffff });
            }
            Path2D.Double crack = new Path2D.Double();
            crack.moveTo(x + 2, y - 7); crack.lineTo(x - 2, y - 1); crack.lineTo(x + 4, y + 2); crack.lineTo(x + 1, y + 7);
            crack.moveTo(x - 2, y - 1); crack.lineTo(x - 9, y + 1);
            draw(crack, new Color(255, 255, 255, 140), 0.8);
            fill(new Rectangle2D.Double(x - 4, y + 10, 8, 3), c(0x2a2e33));
            fill(new RoundRectangle2D.Double(x - 12, y + 15, 24, 6, 2, 2), c(0x1a1d21));
            g.setTransform(old);
        }

        void beacon(double x, double y) {
            glowBlob(x, y, 22, alpha(amber, 70));
            fill(new Ellipse2D.Double(x - 5, y - 5, 10, 10), c(0x2a2420));
            fill(new Ellipse2D.Double(x - 3.2, y - 3.2, 6.4, 6.4), amber);
            fill(new Ellipse2D.Double(x - 1.4, y - 2.4, 2.4, 2), new Color(255, 255, 255, 200));
            lights.add(new double[] { x, y, 2, amber.getRGB() & 0xffffff });
        }

        void toppled(double x, double y) {
            AffineTransform old = g.getTransform();
            g.rotate(Math.toRadians(rnd.nextInt(360)), x, y);
            fill(new Rectangle2D.Double(x - 16, y - 7, 32, 14), new Color(0, 0, 0, 120));
            fill(new Rectangle2D.Double(x - 17, y - 9, 32, 14), c(0x2a2f36));
            draw(new Rectangle2D.Double(x - 17, y - 9, 32, 14), c(0x4a5058), 1);
            for (int k = 0; k < 4; k++) fill(new Rectangle2D.Double(x - 14 + k * 7, y - 6, 5, 8), c(0x16191d));
            fill(new Rectangle2D.Double(x + 10, y - 6, 2, 2), rnd.nextBoolean() ? Cyber.RED : dead);
            g.setTransform(old);
        }
    }

    // ==================================================================================================== live layer
    /**
     * Glowing data packets streaming along every route (one cheap custom ACM object). Skipped when the world view is
     * painting at a reduced level of detail.
     */
    public static final class Pulses extends GObject {
        private static final long serialVersionUID = 1L;
        private final GameMap map;
        private final Color col;
        private double time;

        public Pulses(GameMap map) {
            this.map = map;
            this.col = Cyber.lerp(c(map.getTrackRgb()), Color.WHITE, 0.6);
        }

        public void setTime(double t) { time = t; }

        @Override public GRectangle getBounds() { return new GRectangle(0, 0, W, H); }

        @Override public void paint(Graphics g) {
            if (Thick.level() >= Thick.DETAIL_DECOR) return;
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                g2.setComposite(AlphaComposite.SrcOver);
                g2.setStroke(new BasicStroke(3f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                int ri = 0;
                for (Path r : map.getRoutes()) {
                    double len = r.getTotalLength();
                    int n = Math.max(3, (int) (len / 420));
                    for (int k = 0; k < n; k++) {
                        double d = ((time * 150 + k * len / n + ri * 97) % len + len) % len;
                        if (d < 24) continue;
                        Vec p = r.positionAt(d), q = r.positionAt(d - 26);
                        g2.setPaint(new GradientPaint((float) q.x, (float) q.y, alpha(col, 0), (float) p.x, (float) p.y, alpha(col, 170)));
                        g2.draw(new Line2D.Double(q.x, q.y, p.x, p.y));
                        g2.setColor(alpha(col, 70));
                        g2.fill(new Ellipse2D.Double(p.x - 6, p.y - 6, 12, 12));
                        g2.setColor(Color.WHITE);
                        g2.fill(new Ellipse2D.Double(p.x - 2.2, p.y - 2.2, 4.4, 4.4));
                    }
                    ri++;
                }
                if (map instanceof NeuralNetwork) neuronPulse(g2);
                if (map instanceof AbandonedDataCenter) { flicker(g2); hazardFx(g2, (AbandonedDataCenter) map); }
            } finally {
                g2.dispose();
            }
        }

        /** Neurons breathe: an expanding ring and a brightening core, out of phase per neuron. */
        private void neuronPulse(Graphics2D g2) {
            List<Vec> ns = ((NeuralNetwork) map).getNeurons();
            for (int i = 0; i < ns.size(); i++) {
                Vec p = ns.get(i);
                double ph = (time * 0.8 + i * 0.37) % 1.0;
                double rr = 38 + ph * 34;
                g2.setStroke(new BasicStroke(2f));
                g2.setColor(alpha(c(0xff4bd8), (int) (150 * (1 - ph))));
                g2.draw(new Ellipse2D.Double(p.x - rr, p.y - rr, 2 * rr, 2 * rr));
                int a = (int) (60 + 50 * Math.sin(time * 3 + i));
                g2.setColor(new Color(255, 255, 255, Math.max(0, a)));
                g2.fill(new Ellipse2D.Double(p.x - 10, p.y - 10, 20, 20));
            }
        }

        /** Dying lights: monitors flicker, warning beacons blink, sparks crackle. */
        private void flicker(Graphics2D g2) {
            List<double[]> ls;
            synchronized (FLICKER) { ls = FLICKER.get(map.getName()); }
            if (ls == null) return;
            for (int i = 0; i < ls.size(); i++) {
                double[] l = ls.get(i);
                int kind = (int) l[2];
                double n = Math.sin(time * (7 + i % 5) + i * 1.7) + Math.sin(time * 13.3 + i);
                int a;
                if (kind == 2) a = ((int) (time * 2 + i * 0.3)) % 2 == 0 ? 120 : 0;   // beacon blink
                else if (kind == 1) a = n > 1.2 ? 200 : 0;                             // spark crackle
                else a = n > 0.6 ? 90 : n > -1.4 ? 40 : 0;                              // monitor flicker
                if (a <= 0) continue;
                double rr = kind == 2 ? 16 : kind == 1 ? 10 : 12;
                Color c = new Color((int) l[3]);
                g2.setPaint(new RadialGradientPaint(new Point2D.Double(l[0], l[1]), (float) rr, new float[] { 0f, 1f }, new Color[] { alpha(c, a), alpha(c, 0) }));
                g2.fill(new Ellipse2D.Double(l[0] - rr, l[1] - rr, 2 * rr, 2 * rr));
            }
        }

        /** Particles over the active hazard section: sparks, coolant mist or air streaks. */
        private void hazardFx(Graphics2D g2, AbandonedDataCenter dc) {
            int idx = dc.getActiveHazard();
            if (idx < 0) return;
            AbandonedDataCenter.Hazard h = dc.getHazards().get(idx);
            Path r = map.getRoutes().get(0);
            Color c = new Color(h.rgb);
            Random rr = new Random((long) (time * 20));
            for (int k = 0; k < 22; k++) {
                double d = h.from + rr.nextDouble() * (h.to - h.from);
                Vec p = r.positionAt(d), dir = r.directionAt(d);
                double off = (rr.nextDouble() - 0.5) * 2 * HW;
                double x = p.x - dir.y * off, y = p.y + dir.x * off;
                if (h.kind.equals("SPARKS")) {
                    double a = rr.nextDouble() * Math.PI * 2, l = 4 + rr.nextDouble() * 8;
                    g2.setColor(alpha(Color.WHITE, 220));
                    g2.setStroke(new BasicStroke(1.2f));
                    g2.draw(new Line2D.Double(x, y, x + Math.cos(a) * l, y + Math.sin(a) * l));
                    g2.setColor(alpha(c, 120));
                    g2.fill(new Ellipse2D.Double(x - 4, y - 4, 8, 8));
                } else if (h.kind.equals("COOLANT")) {
                    double s = 6 + rr.nextDouble() * 12;
                    g2.setColor(alpha(c, 60));
                    g2.fill(new Ellipse2D.Double(x - s / 2, y - s / 2, s, s));
                    g2.setColor(alpha(Color.WHITE, 120));
                    g2.fill(new Ellipse2D.Double(x - 1, y - 1, 2, 2));
                } else {
                    double l = 10 + rr.nextDouble() * 14;
                    g2.setColor(alpha(c, 130));
                    g2.setStroke(new BasicStroke(1.4f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                    g2.draw(new Line2D.Double(x, y, x - dir.x * l, y - dir.y * l));
                }
            }
        }
    }

    // ==================================================================================================== helpers
    private static Color c(int rgb) { return new Color(rgb); }
    private static Color alpha(Color c, int a) { return Cyber.alpha(c, a); }
    private static BasicStroke round(double w) { return new BasicStroke((float) w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND); }

    private static Path2D hexagon(double cx, double cy, double r, double rotDeg) {
        Path2D.Double p = new Path2D.Double();
        for (int i = 0; i < 6; i++) {
            double a = Math.toRadians(rotDeg + i * 60);
            if (i == 0) p.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); else p.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
        }
        p.closePath();
        return p;
    }
}
