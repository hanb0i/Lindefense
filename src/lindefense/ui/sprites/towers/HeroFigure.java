package lindefense.ui.sprites.towers;

import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RadialGradientPaint;
import java.awt.RenderingHints;
import java.awt.Shape;
import java.awt.geom.Arc2D;
import java.awt.geom.Area;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;
import java.awt.geom.Path2D;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.awt.geom.RoundRectangle2D;

/**
 * The chibi hero figure every Hero Store hero is drawn from: a big round head with large glossy eyes, blush and a
 * small mouth on a short body with puffed sleeves, little legs and sneakers, wrapped in a glowing sticker outline.
 *
 * <p>It is one custom ACM {@link GObject} painted with Java2D rather than a compound of outlined polygons: at sprite
 * size (head radius ~11 px) the engine's shared 2.2 px ink outline would swallow the eyes, hair and glasses, so the
 * figure uses one bold silhouette outline and hairline inner lines instead. A {@link Look} carries the likeness
 * (skin, hair colour and style, iris, expression, outfit colours) and two {@link Extra} hooks let each hero paint
 * its own clothing print and headgear at the right depth.</p>
 */
public final class HeroFigure {
    private HeroFigure() { }

    /** Hairstyles across the roster. */
    public enum Hair {
        /** Big dark curls all over, curls falling on the forehead. */
        CURLY_BIG,
        /** Curly volume on top, short faded sides. */
        CURLY_TOP,
        /** Lighter, looser shaggy curls. */
        CURLY_LOOSE,
        /** Straight hair with a full fringe (the roster's most common cut). */
        STRAIGHT_FRINGE,
        /** Short spiked hair. */
        SPIKY,
        /** Long hair falling past the shoulders. */
        LONG,
        /** Short hair mostly hidden under headgear. */
        UNDER_HAT
    }

    /** Mouth shapes. */
    public enum Mouth { NEUTRAL, SMILE, GRIN }

    /** Paints extra details; coordinates are world px centred on the tower. */
    public interface Extra { void paint(Graphics2D g, double r, Head h); }

    /** Everything that makes one hero's figure look like their reference portrait. */
    public static final class Look {
        Color skin, hair, shirt, pants = new Color(0x2e3344), shoes = new Color(0xe9e6f5), iris = new Color(0x3a2418);
        Color glow = new Color(0x5fe8ff);
        Hair style = Hair.STRAIGHT_FRINGE;
        Mouth mouth = Mouth.SMILE;
        Extra onShirt, onHead;

        public Look skin(int v) { skin = new Color(v); return this; }
        public Look hair(int v, Hair s) { hair = new Color(v); style = s; return this; }
        public Look shirt(int v) { shirt = new Color(v); return this; }
        public Look pants(int v) { pants = new Color(v); return this; }
        public Look shoes(int v) { shoes = new Color(v); return this; }
        public Look iris(int v) { iris = new Color(v); return this; }
        public Look glow(Color c) { glow = c; return this; }
        public Look mouth(Mouth m) { mouth = m; return this; }
        /** Print / details on the shirt (painted after the torso, before the head). */
        public Look onShirt(Extra e) { onShirt = e; return this; }
        /** Accessories over the face and hair (glasses, hats, goggles). */
        public Look onHead(Extra e) { onHead = e; return this; }
    }

    /** Head geometry, so accessories line up with the face. */
    public static final class Head {
        public final double cy, rad;
        Head(double cy, double rad) { this.cy = cy; this.rad = rad; }
        /** Eye centre x offset (use +/-). */
        public double eyeX() { return rad * 0.37; }
        /** Eye centre y. */
        public double eyeY() { return cy + rad * 0.17; }
    }

    static final Color INK = Art.INK;
    private static final Color BLUSH = new Color(0xff6f92);

    /** Adds the figure to a hero's art and returns its head geometry. */
    public static Head draw(TowerArt a, double r, Look l) {
        Figure f = new Figure(r, l);
        a.add(f);
        return f.head;
    }

    // ================================================================================================ the object
    static final class Figure extends GObject {
        private static final long serialVersionUID = 1L;
        private final double r;
        private final Look l;
        final Head head;

        // The silhouette and every body part are the same every frame, so they are built once here instead of
        // being unioned on each paint (an Area union per frame per hero showed up clearly in the render benchmark).
        private final Shape[] legs = new Shape[2], shoes = new Shape[2], sleeves = new Shape[2], hands = new Shape[2], ears = new Shape[2];
        private final Shape torso, face;
        private final Area hairBack, hairFront, silhouette;

        Figure(double r, Look l) {
            this.r = r; this.l = l;
            this.head = new Head(-r * 0.33, r * 0.56);
            double R = head.rad, hy = head.cy;
            for (int i = 0; i < 2; i++) {
                int s = i == 0 ? -1 : 1;
                legs[i] = new RoundRectangle2D.Double(s * r * 0.15 - r * 0.09, r * 0.6, r * 0.18, r * 0.32, r * 0.08, r * 0.08);
                shoes[i] = new Ellipse2D.Double(s * r * 0.18 - r * 0.15, r * 0.86, r * 0.3, r * 0.16);
                sleeves[i] = new Ellipse2D.Double(s * r * 0.39 - r * 0.14, r * 0.14, r * 0.28, r * 0.38);
                hands[i] = new Ellipse2D.Double(s * r * 0.45 - r * 0.09, r * 0.5, r * 0.18, r * 0.18);
                ears[i] = new Ellipse2D.Double(s * R * 0.97 - R * 0.15, hy, R * 0.3, R * 0.3);
            }
            Path2D.Double t = new Path2D.Double();
            t.moveTo(-r * 0.24, r * 0.1);
            t.lineTo(r * 0.24, r * 0.1);
            t.quadTo(r * 0.34, r * 0.13, r * 0.35, r * 0.25);
            t.lineTo(r * 0.37, r * 0.68);
            t.quadTo(r * 0.37, r * 0.77, r * 0.28, r * 0.77);
            t.lineTo(-r * 0.28, r * 0.77);
            t.quadTo(-r * 0.37, r * 0.77, -r * 0.37, r * 0.68);
            t.lineTo(-r * 0.35, r * 0.25);
            t.quadTo(-r * 0.34, r * 0.13, -r * 0.24, r * 0.1);
            t.closePath();
            torso = t;
            face = new Ellipse2D.Double(-R, hy - R * 0.95, 2 * R, 1.9 * R);
            hairBack = hairBack(R, hy);
            hairFront = hairFront(R, hy);
            Area sil = new Area(torso);
            for (int i = 0; i < 2; i++) {
                sil.add(new Area(legs[i])); sil.add(new Area(shoes[i])); sil.add(new Area(sleeves[i]));
                sil.add(new Area(hands[i])); sil.add(new Area(ears[i]));
            }
            sil.add(new Area(face));
            sil.add(hairBack);
            sil.add(hairFront);
            silhouette = sil;
        }

        @Override public GRectangle getBounds() { return new GRectangle(getX() - r * 1.5, getY() - r * 1.6, r * 3, r * 3); }

        @Override public void paint(Graphics g0) {
            Graphics2D g = (Graphics2D) g0.create();
            try {
                g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
                g.translate(getX(), getY());
                paintFigure(g);
            } finally {
                g.dispose();
            }
        }

        private void paintFigure(Graphics2D g) {
            double R = head.rad, hy = head.cy;
            // sticker silhouette: a coloured glow, then one bold ink border
            for (int k = 3; k >= 1; k--) {
                g.setStroke(round(r * (0.1 + 0.11 * k)));
                g.setColor(Art.alpha(l.glow, 34 + (3 - k) * 26));
                g.draw(silhouette);
            }
            g.setStroke(round(r * 0.15));
            g.setColor(INK);
            g.draw(silhouette);
            g.fill(silhouette);

            // body
            Color pantsHi = Art.shade(l.pants, 1.15);
            for (int i = 0; i < 2; i++) {
                fill(g, legs[i], l.pants);
                fill(g, new Rectangle2D.Double(legs[i].getBounds2D().getX() + r * 0.03, r * 0.62, r * 0.04, r * 0.22), pantsHi);
            }
            for (int i = 0; i < 2; i++) {
                fill(g, shoes[i], l.shoes);
                fill(g, new Rectangle2D.Double(shoes[i].getBounds2D().getX() + r * 0.03, r * 0.97, r * 0.24, r * 0.03), Art.shade(l.shoes, 0.78));
                line(g, shoes[i], r * 0.03);
            }
            for (int i = 0; i < 2; i++) { fill(g, hands[i], l.skin); line(g, hands[i], r * 0.03); }
            Color sleeve = Art.shade(l.shirt, 0.93);
            for (int i = 0; i < 2; i++) { fill(g, sleeves[i], sleeve); line(g, sleeves[i], r * 0.03); }
            fill(g, torso, l.shirt);
            Shape oldClip = g.getClip();
            g.clip(torso);
            fill(g, new Rectangle2D.Double(r * 0.16, 0, r * 0.3, r), Art.alpha(Color.BLACK, 30));
            g.setClip(oldClip);
            line(g, torso, r * 0.03);
            fill(g, new Ellipse2D.Double(-r * 0.1, r * 0.04, r * 0.2, r * 0.14), Art.shade(l.skin, 0.82));
            if (l.onShirt != null) l.onShirt.paint(g, r, head);

            // head
            fill(g, hairBack, Art.shade(l.hair, 0.82));
            for (int i = 0; i < 2; i++) { fill(g, ears[i], l.skin); fill(g, insetEllipse(ears[i], 0.45), Art.shade(l.skin, 0.85)); }
            fill(g, face, l.skin);
            g.setPaint(new RadialGradientPaint(new Point2D.Double(-R * 0.35, hy - R * 0.3), (float) (R * 1.2),
                new float[] { 0f, 1f }, new Color[] { Art.alpha(Color.WHITE, 40), Art.alpha(Color.WHITE, 0) }));
            g.fill(face);
            line(g, face, r * 0.03);
            paintFace(g, R, hy);
            paintHair(g, hairFront, R, hy);
            if (l.onHead != null) l.onHead.paint(g, r, head);
        }

        private void paintFace(Graphics2D g, double R, double hy) {
            double ey = head.eyeY(), rx = R * 0.2, ry = R * 0.26;
            for (int s = -1; s <= 1; s += 2) {
                double ex = s * head.eyeX();
                g.setPaint(new RadialGradientPaint(new Point2D.Double(s * R * 0.62, hy + R * 0.47), (float) (R * 0.2),
                    new float[] { 0f, 1f }, new Color[] { Art.alpha(BLUSH, 150), Art.alpha(BLUSH, 0) }));
                g.fill(new Ellipse2D.Double(s * R * 0.62 - R * 0.2, hy + R * 0.27, R * 0.4, R * 0.4));
                Ellipse2D eye = new Ellipse2D.Double(ex - rx, ey - ry, 2 * rx, 2 * ry);
                fill(g, eye, Art.shade(l.iris, 0.55));
                Shape clip = g.getClip();
                g.clip(eye);
                g.setPaint(new RadialGradientPaint(new Point2D.Double(ex, ey + ry * 0.7), (float) (ry * 1.1),
                    new float[] { 0f, 1f }, new Color[] { Art.shade(l.iris, 1.6), Art.alpha(Art.shade(l.iris, 1.1), 0) }));
                g.fill(eye);
                g.setClip(clip);
                fill(g, new Ellipse2D.Double(ex - rx * 0.62, ey - ry * 0.72, rx * 0.85, ry * 0.62), Color.WHITE);
                fill(g, new Ellipse2D.Double(ex + rx * 0.2, ey + ry * 0.25, rx * 0.4, ry * 0.3), Art.alpha(Color.WHITE, 220));
                g.setColor(INK);
                g.setStroke(round(R * 0.08));
                g.draw(new Arc2D.Double(ex - rx * 1.1, ey - ry * 1.02, rx * 2.2, ry * 2.1, 25, 130, Arc2D.OPEN));
                g.draw(new Line2D.Double(ex + s * rx * 0.95, ey - ry * 0.55, ex + s * rx * 1.35, ey - ry * 0.8));
                g.setColor(Art.shade(l.hair, 0.75));
                g.setStroke(round(R * 0.06));
                g.draw(new Line2D.Double(ex - rx * 0.8, ey - ry * 1.5, ex + rx * 0.8, ey - ry * 1.58));
            }
            fill(g, new Ellipse2D.Double(-R * 0.035, hy + R * 0.42, R * 0.07, R * 0.05), Art.shade(l.skin, 0.75));
            double my = hy + R * 0.6;
            g.setStroke(round(R * 0.05));
            switch (l.mouth) {
                case NEUTRAL:
                    g.setColor(new Color(0x6b2e2e));
                    g.draw(new Line2D.Double(-R * 0.09, my, R * 0.09, my));
                    break;
                case GRIN: {
                    Shape m = new Arc2D.Double(-R * 0.2, my - R * 0.18, R * 0.4, R * 0.36, 180, 180, Arc2D.CHORD);
                    fill(g, m, new Color(0x7a1f2c));
                    Shape clip = g.getClip();
                    g.clip(m);
                    fill(g, new Rectangle2D.Double(-R * 0.2, my - R * 0.02, R * 0.4, R * 0.07), Color.WHITE);
                    fill(g, new Ellipse2D.Double(-R * 0.1, my + R * 0.08, R * 0.2, R * 0.14), new Color(0xff8295));
                    g.setClip(clip);
                    g.setColor(INK);
                    g.setStroke(round(R * 0.035));
                    g.draw(m);
                    break;
                }
                case SMILE:
                default: {
                    Shape m = new Arc2D.Double(-R * 0.12, my - R * 0.1, R * 0.24, R * 0.2, 180, 180, Arc2D.CHORD);
                    fill(g, m, new Color(0x7a1f2c));
                    g.setColor(INK);
                    g.setStroke(round(R * 0.03));
                    g.draw(m);
                    break;
                }
            }
        }

        private void paintHair(Graphics2D g, Area front, double R, double hy) {
            if (l.style == Hair.CURLY_TOP) {
                for (int s = -1; s <= 1; s += 2) {
                    Path2D.Double fade = new Path2D.Double();
                    fade.moveTo(s * R * 0.99, hy + R * 0.1);
                    fade.lineTo(s * R * 0.97, hy - R * 0.4);
                    fade.lineTo(s * R * 0.62, hy - R * 0.6);
                    fade.lineTo(s * R * 0.7, hy - R * 0.25);
                    fade.lineTo(s * R * 0.86, hy + R * 0.08);
                    fade.closePath();
                    fill(g, fade, Art.alpha(l.hair, 120));
                }
            }
            fill(g, front, l.hair);
            if (l.style == Hair.UNDER_HAT) return;
            g.setColor(Art.alpha(Art.shade(l.hair, 1.45), 170));
            Shape clip = g.getClip();
            g.clip(front);
            if (l.style == Hair.STRAIGHT_FRINGE || l.style == Hair.LONG) {
                g.setStroke(round(R * 0.09));
                g.draw(new Arc2D.Double(-R * 0.75, hy - R * 0.98, R * 1.3, R * 0.9, 110, 55, Arc2D.OPEN));
                g.setStroke(round(R * 0.035));
                g.setColor(Art.alpha(Art.shade(l.hair, 1.6), 110));
                for (int i = -2; i <= 2; i++) g.draw(new Line2D.Double(i * R * 0.22, hy - R * 0.9, i * R * 0.3, hy - R * 0.25));
            } else if (l.style == Hair.SPIKY) {
                g.setStroke(round(R * 0.05));
                for (int i = -2; i <= 2; i++) g.draw(new Line2D.Double(i * R * 0.26, hy - R * 0.5, i * R * 0.34, hy - R * 1.0));
            } else {
                g.setStroke(round(R * 0.05));
                for (double[] c : curlCentres(R, hy)) {
                    g.draw(new Arc2D.Double(c[0] - c[2] * 0.65, c[1] - c[2] * 0.65, c[2] * 1.3, c[2] * 1.3, 70, 120, Arc2D.OPEN));
                }
            }
            g.setClip(clip);
            g.setColor(Art.shade(l.hair, 0.45));
            g.setStroke(round(R * 0.035));
            g.draw(front);
        }

        private double[][] curlCentres(double R, double hy) {
            switch (l.style) {
                case CURLY_BIG:
                    return new double[][] { { -R * 0.72, hy - R * 0.45, R * 0.3 }, { R * 0.72, hy - R * 0.45, R * 0.3 },
                        { -R * 0.38, hy - R * 0.62, R * 0.32 }, { R * 0.38, hy - R * 0.62, R * 0.32 }, { 0, hy - R * 0.7, R * 0.32 },
                        { -R * 0.2, hy - R * 0.36, R * 0.21 }, { R * 0.24, hy - R * 0.38, R * 0.2 }, { -R * 0.55, hy - R * 0.3, R * 0.18 },
                        { -R * 0.55, hy - R * 0.95, R * 0.34 }, { R * 0.55, hy - R * 0.95, R * 0.34 }, { 0, hy - R * 1.08, R * 0.36 },
                        { -R * 0.92, hy - R * 0.7, R * 0.3 }, { R * 0.92, hy - R * 0.7, R * 0.3 } };
                case CURLY_LOOSE:
                    return new double[][] { { -R * 0.76, hy - R * 0.42, R * 0.27 }, { R * 0.76, hy - R * 0.42, R * 0.27 },
                        { -R * 0.42, hy - R * 0.62, R * 0.3 }, { R * 0.42, hy - R * 0.62, R * 0.3 }, { 0, hy - R * 0.7, R * 0.31 },
                        { -R * 0.12, hy - R * 0.4, R * 0.21 }, { R * 0.32, hy - R * 0.37, R * 0.18 },
                        { -R * 0.55, hy - R * 0.92, R * 0.32 }, { R * 0.55, hy - R * 0.92, R * 0.32 }, { 0, hy - R * 1.04, R * 0.33 },
                        { -R * 0.95, hy - R * 0.62, R * 0.27 }, { R * 0.95, hy - R * 0.62, R * 0.27 } };
                case CURLY_TOP:
                    return new double[][] { { -R * 0.48, hy - R * 0.6, R * 0.29 }, { R * 0.48, hy - R * 0.6, R * 0.29 }, { 0, hy - R * 0.7, R * 0.33 },
                        { -R * 0.18, hy - R * 0.42, R * 0.2 }, { R * 0.2, hy - R * 0.44, R * 0.18 },
                        { -R * 0.3, hy - R * 1.02, R * 0.36 }, { R * 0.3, hy - R * 1.02, R * 0.36 },
                        { -R * 0.66, hy - R * 0.82, R * 0.3 }, { R * 0.66, hy - R * 0.82, R * 0.3 } };
                default:
                    return new double[0][];
            }
        }

        private Area hairBack(double R, double hy) {
            switch (l.style) {
                case CURLY_BIG:
                    return circles(new double[][] { { -R * 0.98, hy - R * 0.08, R * 0.3 }, { R * 0.98, hy - R * 0.08, R * 0.3 },
                        { -R * 0.88, hy - R * 0.55, R * 0.38 }, { R * 0.88, hy - R * 0.55, R * 0.38 },
                        { -R * 0.45, hy - R * 0.92, R * 0.42 }, { R * 0.45, hy - R * 0.92, R * 0.42 }, { 0, hy - R * 1.0, R * 0.44 } });
                case CURLY_LOOSE:
                    return circles(new double[][] { { -R * 1.0, hy - R * 0.02, R * 0.27 }, { R * 1.0, hy - R * 0.02, R * 0.27 },
                        { -R * 0.9, hy - R * 0.5, R * 0.34 }, { R * 0.9, hy - R * 0.5, R * 0.34 },
                        { -R * 0.5, hy - R * 0.88, R * 0.38 }, { R * 0.5, hy - R * 0.88, R * 0.38 }, { 0, hy - R * 0.98, R * 0.4 } });
                case CURLY_TOP:
                    return circles(new double[][] { { -R * 0.62, hy - R * 0.8, R * 0.36 }, { R * 0.62, hy - R * 0.8, R * 0.36 },
                        { -R * 0.22, hy - R * 1.02, R * 0.38 }, { R * 0.22, hy - R * 1.02, R * 0.38 } });
                case LONG: {
                    Area a = new Area(new Ellipse2D.Double(-R * 1.12, hy - R * 1.1, R * 2.24, R * 1.9));
                    a.add(new Area(new RoundRectangle2D.Double(-R * 1.12, hy - R * 0.2, R * 0.5, R * 1.7, R * 0.4, R * 0.4)));
                    a.add(new Area(new RoundRectangle2D.Double(R * 0.62, hy - R * 0.2, R * 0.5, R * 1.7, R * 0.4, R * 0.4)));
                    return a;
                }
                case SPIKY: {
                    Area a = new Area(new Ellipse2D.Double(-R * 1.06, hy - R * 1.0, R * 2.12, R * 1.8));
                    Path2D.Double sp = new Path2D.Double();
                    for (int i = -3; i <= 3; i++) {
                        double x = i * R * 0.3;
                        sp.moveTo(x - R * 0.2, hy - R * 0.6);
                        sp.lineTo(x + (i < 0 ? -R * 0.14 : R * 0.14), hy - R * 1.45);
                        sp.lineTo(x + R * 0.2, hy - R * 0.6);
                        sp.closePath();
                    }
                    a.add(new Area(sp));
                    return a;
                }
                case STRAIGHT_FRINGE:
                    return new Area(new Ellipse2D.Double(-R * 1.08, hy - R * 1.1, R * 2.16, R * 1.9));
                case UNDER_HAT:
                default:
                    return new Area(new Ellipse2D.Double(-R * 1.03, hy - R * 0.9, R * 2.06, R * 1.6));
            }
        }

        private Area hairFront(double R, double hy) {
            switch (l.style) {
                case CURLY_BIG: case CURLY_LOOSE: case CURLY_TOP:
                    return circles(curlCentres(R, hy));
                case SPIKY: {
                    Path2D.Double p = new Path2D.Double();
                    p.moveTo(-R * 1.0, hy + R * 0.1);
                    p.lineTo(-R * 0.95, hy - R * 0.5);
                    for (int i = -3; i <= 3; i++) {
                        double x = i * R * 0.3;
                        p.lineTo(x - R * 0.12, hy - R * 0.62);
                        p.lineTo(x + (i < 0 ? -R * 0.1 : R * 0.1), hy - R * 1.35);
                        p.lineTo(x + R * 0.15, hy - R * 0.55);
                    }
                    p.lineTo(R * 0.95, hy - R * 0.5);
                    p.lineTo(R * 1.0, hy + R * 0.1);
                    p.closePath();
                    return new Area(p);
                }
                case STRAIGHT_FRINGE: case LONG: {
                    Path2D.Double p = new Path2D.Double();
                    int n = 16;
                    for (int i = 0; i <= n; i++) {
                        double t = Math.toRadians(182 + 176.0 * i / n);
                        double x = Math.cos(t) * R * 1.07, y = hy - R * 0.06 + Math.sin(t) * R * 1.03;
                        if (i == 0) p.moveTo(x, y); else p.lineTo(x, y);
                    }
                    double[] fringe = { R * 0.99, hy + R * 0.12, R * 0.66, hy - R * 0.3, R * 0.45, hy - R * 0.12, R * 0.24, hy - R * 0.32,
                        0.02 * R, hy - R * 0.1, -R * 0.24, hy - R * 0.3, -R * 0.46, hy - R * 0.1, -R * 0.68, hy - R * 0.3, -R * 0.99, hy + R * 0.12 };
                    for (int i = 0; i < fringe.length; i += 2) p.lineTo(fringe[i], fringe[i + 1]);
                    p.closePath();
                    return new Area(p);
                }
                case UNDER_HAT:
                default: {
                    Area a = new Area();
                    for (int s = -1; s <= 1; s += 2) {
                        Path2D.Double p = new Path2D.Double();
                        p.moveTo(s * R * 1.01, hy + R * 0.12);
                        p.lineTo(s * R * 0.99, hy - R * 0.5);
                        p.lineTo(s * R * 0.7, hy - R * 0.56);
                        p.lineTo(s * R * 0.84, hy + R * 0.04);
                        p.closePath();
                        a.add(new Area(p));
                    }
                    return a;
                }
            }
        }
    }

    // ================================================================================================ helpers
    /** Round-cap stroke of the given width (hero gear uses it too). */
    public static BasicStroke round(double w) { return new BasicStroke((float) w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND); }

    /** Fills a shape in a flat colour. */
    public static void fill(Graphics2D g, Shape s, Color c) { g.setColor(c); g.fill(s); }

    /** Outlines a shape in the sprite ink colour. */
    public static void line(Graphics2D g, Shape s, double w) {
        g.setColor(INK);
        g.setStroke(round(w));
        g.draw(s);
    }

    private static Area circles(double[][] c) {
        Area a = new Area();
        for (double[] k : c) a.add(new Area(new Ellipse2D.Double(k[0] - k[2], k[1] - k[2], 2 * k[2], 2 * k[2])));
        return a;
    }

    private static Shape insetEllipse(Shape s, double k) {
        Rectangle2D b = s.getBounds2D();
        double w = b.getWidth() * k, h = b.getHeight() * k;
        return new Ellipse2D.Double(b.getCenterX() - w / 2, b.getCenterY() - h / 2, w, h);
    }
}
