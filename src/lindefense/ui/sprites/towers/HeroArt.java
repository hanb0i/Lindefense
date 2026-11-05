package lindefense.ui.sprites.towers;

import acm.graphics.GCompound;
import java.awt.Color;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;
import lindefense.tower.TowerType;
import lindefense.ui.sprites.towers.HeroFigure.Hair;
import lindefense.ui.sprites.towers.HeroFigure.Look;
import lindefense.ui.sprites.towers.HeroFigure.Mouth;

/**
 * Body art for every Hero Store hero: the shared chibi {@link HeroFigure} wearing that hero's own face and outfit,
 * plus the gear that makes their role readable at a glance (a mortar, a healing staff, gauntlets, dynamite, frost
 * shards, kaiju spines, jet wings, a sniper rifle, mines, a clock, a spear, vines, traps, a rifle, a drone, and Mr.
 * Lindemann's floating black hole of Java code).
 *
 * <p>{@code tier} is the hero's game tier 0-3, so all four progression levels look different: the gear grows,
 * gains emitters and finally lights up with the hero's colour at the maxed tier.</p>
 */
@SuppressWarnings({ "serial", "this-escape" })
public final class HeroArt extends TowerArt {
    private static final long serialVersionUID = 1L;

    /** @see TowerArt#TowerArt(TowerType, int, double) */
    public HeroArt(TowerType type, int tier, double r) { super(type, tier, r); }

    /** The hero's portrait: skin, hair, outfit and expression, from the roster reference art. */
    private static Look look(TowerType t) {
        switch (t) {
            case LOBBER_LUIS: return new Look().skin(0xf0c8a4).hair(0xf2c94c, Hair.SPIKY).shirt(0x2b3a6c).pants(0x3a4158).mouth(Mouth.GRIN);
            case SAGE_AARAV: return new Look().skin(0xd9a074).hair(0x1c1410, Hair.STRAIGHT_FRINGE).shirt(0xf3f2ef).pants(0xcfd6e2).mouth(Mouth.SMILE);
            case IRON_IMRAAN: return new Look().skin(0xc98d62).hair(0x17110e, Hair.STRAIGHT_FRINGE).shirt(0x27324a).pants(0x2a3140).mouth(Mouth.NEUTRAL);
            case BOOM_SAM: return new Look().skin(0xe8bb92).hair(0x1a1512, Hair.STRAIGHT_FRINGE).shirt(0xcfd3da).pants(0x3a4050).mouth(Mouth.GRIN);
            case CHILLSTIN: return new Look().skin(0xe3b68e).hair(0x1a1512, Hair.STRAIGHT_FRINGE).shirt(0x6b6f3a).pants(0x3a4050).mouth(Mouth.SMILE);
            case KAIJU_KAI: return new Look().skin(0xdfae84).hair(0x15110e, Hair.STRAIGHT_FRINGE).shirt(0x1f3350).pants(0x2a3346).mouth(Mouth.GRIN);
            case ABHI_ACE: return new Look().skin(0xa8714a).hair(0x12100f, Hair.SPIKY).shirt(0x2f55b8).pants(0x2a3550).mouth(Mouth.GRIN);
            case ZIPPY_MATT: return new Look().skin(0xe8bb92).hair(0x1c1512, Hair.CURLY_LOOSE).shirt(0xd8dbe2).pants(0x39405a).mouth(Mouth.SMILE);
            case SUNNY_JOE: return new Look().skin(0xe0b48c).hair(0x17110e, Hair.STRAIGHT_FRINGE).shirt(0x9aa1ad).pants(0x3a4050).mouth(Mouth.SMILE);
            case NIK_SCOPE: return new Look().skin(0xefc6a2).hair(0x7a4a2a, Hair.LONG).shirt(0x23262e).pants(0x2a2e38).mouth(Mouth.SMILE);
            case CAMI_MINE: return new Look().skin(0xeec19c).hair(0x8a5a36, Hair.STRAIGHT_FRINGE).shirt(0x27324a).pants(0x333a4c).mouth(Mouth.SMILE);
            case JUSTIN_TIME: return new Look().skin(0xd8a97e).hair(0x14100e, Hair.CURLY_BIG).shirt(0xf2f3f6).pants(0x343c52).mouth(Mouth.GRIN);
            case SPEAR_HANBO: return new Look().skin(0xe6bd95).hair(0x16120f, Hair.STRAIGHT_FRINGE).shirt(0xf2f3f6).pants(0x343c52).mouth(Mouth.GRIN);
            case THORN_TUHIN: return new Look().skin(0xcf9a6e).hair(0x16120f, Hair.STRAIGHT_FRINGE).shirt(0x24404a).pants(0x2c3a44).mouth(Mouth.SMILE);
            case TRAPPER_CHE: return new Look().skin(0xe8bb92).hair(0x16120f, Hair.STRAIGHT_FRINGE).shirt(0x2b3550).pants(0x333a4c).mouth(Mouth.SMILE)
                .onHead(HeroArt::glasses);
            case BLITZ_ARNAV: return new Look().skin(0xa8714a).hair(0x12100f, Hair.STRAIGHT_FRINGE).shirt(0x27324a).pants(0x2a3140).mouth(Mouth.GRIN);
            case TANIMBUS: return new Look().skin(0xa8714a).hair(0x14100e, Hair.CURLY_BIG).shirt(0xe8a0a8).pants(0x3a3550).mouth(Mouth.GRIN);
            // Mr. Lindemann: fair skin, bald with a grey side trim, rectangular glasses, teacher's blue button-down
            case MR_LINDEMANN: return new Look().skin(0xf6d6c0).hair(0xb9b4ae, Hair.BALD).shirt(0x9fbfe6).pants(0x2f3445).mouth(Mouth.SMILE)
                .onShirt(HeroArt::collar).onHead(HeroArt::squareGlasses);
            default: return new Look().skin(0xe8bb92).hair(0x17110e, Hair.STRAIGHT_FRINGE).shirt(0x3a4158).mouth(Mouth.SMILE);
        }
    }

    /** Trapper Che's round glasses. */
    private static void glasses(java.awt.Graphics2D g, double r, HeroFigure.Head h) {
        double R = h.rad, ey = h.eyeY();
        g.setStroke(HeroFigure.round(R * 0.08));
        for (int s = -1; s <= 1; s += 2) {
            double cx = s * h.eyeX();
            Ellipse2D lens = new Ellipse2D.Double(cx - R * 0.29, ey - R * 0.27, R * 0.58, R * 0.54);
            HeroFigure.fill(g, lens, new Color(190, 228, 255, 44));
            g.setColor(HeroFigure.INK);
            g.draw(lens);
            g.draw(new Line2D.Double(cx + s * R * 0.29, ey - R * 0.06, cx + s * R * 0.6, ey - R * 0.12));
        }
        g.setColor(HeroFigure.INK);
        g.draw(new Line2D.Double(-R * 0.09, ey - R * 0.04, R * 0.09, ey - R * 0.04));
    }

    /** Mr. Lindemann's rectangular glasses. */
    private static void squareGlasses(java.awt.Graphics2D g, double r, HeroFigure.Head h) {
        double R = h.rad, ey = h.eyeY();
        g.setStroke(HeroFigure.round(R * 0.08));
        for (int s = -1; s <= 1; s += 2) {
            double cx = s * h.eyeX();
            java.awt.geom.RoundRectangle2D lens = new java.awt.geom.RoundRectangle2D.Double(cx - R * 0.31, ey - R * 0.24, R * 0.62, R * 0.46, R * 0.12, R * 0.12);
            HeroFigure.fill(g, lens, new Color(200, 230, 255, 50));
            g.setColor(HeroFigure.INK);
            g.draw(lens);
            g.draw(new Line2D.Double(cx + s * R * 0.31, ey - R * 0.08, cx + s * R * 0.62, ey - R * 0.14));
        }
        g.setColor(HeroFigure.INK);
        g.draw(new Line2D.Double(-R * 0.06, ey - R * 0.06, R * 0.06, ey - R * 0.06));
    }

    /** A white collar with a dark tie (Mr. Lindemann's teaching outfit). */
    private static void collar(java.awt.Graphics2D g, double r, HeroFigure.Head h) {
        java.awt.geom.Path2D.Double c = new java.awt.geom.Path2D.Double();
        c.moveTo(-r * 0.2, r * 0.05); c.lineTo(0, r * 0.2); c.lineTo(r * 0.2, r * 0.05); c.lineTo(r * 0.12, r * 0.02); c.lineTo(0, r * 0.12); c.lineTo(-r * 0.12, r * 0.02);
        c.closePath();
        HeroFigure.fill(g, c, new Color(0xf4f6fa));
        java.awt.geom.Path2D.Double tie = new java.awt.geom.Path2D.Double();
        tie.moveTo(-r * 0.04, r * 0.14); tie.lineTo(r * 0.04, r * 0.14); tie.lineTo(r * 0.06, r * 0.42); tie.lineTo(0, r * 0.5); tie.lineTo(-r * 0.06, r * 0.42);
        tie.closePath();
        HeroFigure.fill(g, tie, new Color(0x3a1d78));
    }

    @Override protected void build() {
        boolean maxed = tier >= 3;
        // every hero glows a little brighter as it is upgraded; the maxed tier gets a real aura
        pulsingGlow(0, 0, r * (0.95 + 0.07 * tier), pri, 16 + 7 * tier, 14, 1.0 + 0.2 * tier);
        if (maxed) pulsingGlow(0, 0, r * 1.35, pri, 30, 24, 1.4);
        // the aiming weapon and the pack go behind the character, so the face is never covered when the
        // turret idles pointing up the screen
        gearBehind();
        gearFront();
        HeroFigure.draw(this, r, look(type));
        if (maxed) sparkle(-r * 0.62, -r * 0.78, r * 0.11);
        sparkle(r * 0.58, -r * 0.8, r * 0.09);
    }

    /** Gear drawn behind the figure (packs, wings, drones, big weapons resting on the back). */
    private void gearBehind() {
        switch (type) {
            case LOBBER_LUIS: {
                // shell rack on the back, one more shell per tier
                for (int i = 0; i <= tier; i++) {
                    double x = -r * 0.5 + i * r * 0.26;
                    poly(Art.rect(x, r * 0.1, r * 0.16, r * 0.3), Art.METAL);
                    plain(Art.circle(x + r * 0.08, r * 0.1, r * 0.08, 8), pri);
                }
                break;
            }
            case ABHI_ACE: {
                // jet wings: longer and swept back with every tier
                double span = r * (0.85 + 0.18 * tier);
                for (int s = -1; s <= 1; s += 2) {
                    poly(new double[] { s * r * 0.3, -r * 0.1, s * span, r * 0.05, s * span * 0.9, r * 0.3, s * r * 0.3, r * 0.25 }, sec);
                    plain(Art.rect(s * span * 0.6 - r * 0.07, r * 0.06, r * 0.14, r * 0.12), pri);
                }
                // engine flames
                for (int s = -1; s <= 1; s += 2) {
                    plain(new double[] { s * span * 0.78, r * 0.12, s * span * 1.05, r * 0.2, s * span * 0.78, r * 0.28 },
                        Art.alpha(0xffd166, 220));
                }
                break;
            }
            case MR_LINDEMANN: {
                // a black hole of Java code hovering over his shoulder: the accretion ring widens and more code
                // fragments orbit with every tier; the maxed tier gets a second, counter-rotating ring
                double cx = r * 0.62, cy = -r * 0.62, hole = r * (0.26 + 0.04 * tier);
                poly(Art.ring(cx, cy, hole * 1.9, hole * 1.35, 20), Art.alpha(pri, 200));
                plain(Art.ring(cx, cy, hole * 1.4, hole * 1.15, 18), Art.alpha(sec, 230));
                poly(Art.circle(cx, cy, hole, 16), new Color(0x07040f));
                plain(Art.circle(cx - hole * 0.25, cy - hole * 0.25, hole * 0.22, 8), Art.alpha(sec.brighter(), 160));
                int bits = 2 + tier;
                for (int i = 0; i < bits; i++) {
                    double a = i * Math.PI * 2 / bits;
                    double bx = cx + Math.cos(a) * hole * 2.2, by = cy + Math.sin(a) * hole * 1.6;
                    spinningPoly(new double[] { -r * 0.07, -r * 0.03, r * 0.07, -r * 0.03, r * 0.07, r * 0.03, -r * 0.07, r * 0.03 },
                        bx, by, i % 2 == 0 ? pri : Art.alpha(Color.WHITE, 220), 120 + 60 * tier);
                }
                if (tier >= 3) poly(Art.ring(cx, cy, hole * 2.5, hole * 2.3, 24), Art.alpha(pri, 120));
                break;
            }
            case TANIMBUS: {
                // quad rotor ring above and behind, blades spin
                for (int i = 0; i < 4; i++) {
                    double a = Math.PI / 4 + i * Math.PI / 2;
                    double x = Math.cos(a) * r * 0.78, y = Math.sin(a) * r * 0.5 - r * 0.15;
                    poly(Art.ring(x, y, r * 0.2, r * 0.15, 12), Art.METAL);
                    spinningPoly(new double[] { -r * 0.2, -r * 0.02, r * 0.2, -r * 0.02, r * 0.2, r * 0.02, -r * 0.2, r * 0.02 },
                        x, y, Art.alpha(sec, 190), 900 + 200 * tier);
                }
                break;
            }
            case KAIJU_KAI: {
                // dorsal spines: taller and more numerous with each tier
                int n = 3 + tier;
                for (int i = 0; i < n; i++) {
                    double x = -r * 0.42 + i * (r * 0.84 / Math.max(1, n - 1));
                    double h = r * (0.3 + 0.09 * tier) * (1 - Math.abs(i - (n - 1) / 2.0) / (n + 1.0));
                    poly(new double[] { x - r * 0.08, r * 0.05, x, r * 0.05 - h, x + r * 0.08, r * 0.05 }, pri);
                }
                // tail
                poly(Art.bar(r * 0.3, r * 0.6, r * 0.95, r * 0.42, r * 0.09), Art.shade(pri, 0.8));
                poly(new double[] { r * 0.9, r * 0.33, r * 1.15, r * 0.42, r * 0.9, r * 0.52 }, pri);
                break;
            }
            case SUNNY_JOE: {
                // cash briefcase that grows into stacked bundles
                box(-r * 0.68, r * 0.3, r * 0.34, r * 0.26, new Color(0x6b4a2a));
                plain(Art.rect(-r * 0.6, r * 0.3, r * 0.18, r * 0.05), Art.GOLD);
                for (int i = 0; i <= tier; i++) {
                    double y = r * 0.22 - i * r * 0.1;
                    plain(Art.rect(r * 0.38, y, r * 0.3, r * 0.08), new Color(0x3fa96b));
                    plain(Art.rect(r * 0.46, y + r * 0.02, r * 0.14, r * 0.04), Art.GOLD_LIGHT);
                }
                break;
            }
            case THORN_TUHIN: {
                // vines creeping up behind him, one more coil per tier
                for (int i = 0; i <= tier; i++) {
                    double s = i % 2 == 0 ? -1 : 1;
                    double x = s * r * (0.5 + 0.12 * i);
                    poly(Art.bar(x, r * 0.75, x + s * r * 0.08, -r * 0.1 - i * r * 0.08, r * 0.045), new Color(0x2f7d3a));
                    plain(Art.circle(x + s * r * 0.1, -r * 0.12 - i * r * 0.08, r * 0.09, 8), pri);
                }
                break;
            }
            default: break;
        }
    }

    /** The weapon the hero aims, plus held props and emitters (drawn behind the figure). */
    private void gearFront() {
        switch (type) {
            case LOBBER_LUIS: mortar(); break;
            case SAGE_AARAV: staff(); break;
            case IRON_IMRAAN: gauntlets(); break;
            case BOOM_SAM: dynamite(); break;
            case CHILLSTIN: frost(); break;
            case KAIJU_KAI: kaiju(); break;
            case ABHI_ACE: missilePod(); break;
            case ZIPPY_MATT: lightning(); break;
            case SUNNY_JOE: coins(); break;
            case NIK_SCOPE: rifle(); break;
            case CAMI_MINE: mines(); break;
            case JUSTIN_TIME: clock(); break;
            case SPEAR_HANBO: spear(); break;
            case THORN_TUHIN: thorns(); break;
            case TRAPPER_CHE: traps(); break;
            case BLITZ_ARNAV: carbine(); break;
            case TANIMBUS: commandPod(); break;
            default: break;
        }
    }

    /**
     * A hero's weapon, authored pointing +x like any {@link Turret} but pushed {@code out} further from the body so
     * it still reads behind the character: the figure is drawn over the turret, so anything inside its silhouette
     * (about {@code r}) would be invisible.
     */
    private final class Gear {
        private final Turret tu = turret();
        private final double dx;
        Gear(double out) { this.dx = out; }
        acm.graphics.GPolygon poly(double[] xy, Color c) { return tu.poly(Art.shift(xy, dx, 0), c); }
        acm.graphics.GPolygon plain(double[] xy, Color c) { return tu.plain(Art.shift(xy, dx, 0), c); }
        void flash(double[] xy, Color c) { tu.setFlash(tu.plain(Art.shift(xy, dx, 0), c)); }
        void spinner(double[] xy, double cx, double cy, Color c, double degPerSec) {
            tu.spinner(xy, cx + dx, cy, c);
            tu.setSpinSpeed(degPerSec);
        }
    }

    // ---------------------------------------------------------------- per-hero gear
    /** Lobber Luis: a stubby mortar that widens and gains a cluster rack and orbital fins. */
    private void mortar() {
        Gear tu = new Gear(r * 0.55);
        double len = r * (0.55 + 0.1 * tier), hw = r * (0.17 + 0.03 * tier);
        tu.poly(Art.rect(r * 0.1, -hw, len, hw * 2), new Color(0x4a4f58));
        tu.poly(Art.rect(r * 0.1 + len - r * 0.06, -hw * 1.3, r * 0.16, hw * 2.6), pri);
        tu.plain(Art.circle(r * 0.1 + len + r * 0.04, 0, hw * 0.8, 10), Art.alpha(0xffd166, 220));
        if (tier >= 2) {   // cluster rack: three bomblets clipped under the barrel
            for (int i = 0; i < 3; i++) tu.plain(Art.circle(r * 0.3 + i * r * 0.14, hw * 1.5, r * 0.06, 8), sec);
        }
        if (tier >= 3) {   // orbital fins
            tu.poly(new double[] { r * 0.2, -hw * 1.1, r * 0.1, -hw * 2.1, r * 0.4, -hw * 1.9, r * 0.45, -hw * 1.1 }, Art.GOLD);
            tu.poly(new double[] { r * 0.2, hw * 1.1, r * 0.1, hw * 2.1, r * 0.4, hw * 1.9, r * 0.45, hw * 1.1 }, Art.GOLD);
        }
        tu.flash(Art.star(r * 0.1 + len + r * 0.3, 0, r * 0.34, r * 0.12, 7, 0), Art.alpha(0xffd166, 240));
    }

    /** Sage Aarav: a healing staff whose crystal grows and finally crowns itself in gold. */
    private void staff() {
        Gear tu = new Gear(r * 0.25);
        double len = r * 0.95;
        tu.poly(Art.rect(-r * 0.05, -r * 0.045, len, r * 0.09), new Color(0xc9a46a));
        tu.poly(Art.ring(len, 0, r * (0.16 + 0.03 * tier), r * (0.09 + 0.02 * tier), 12), tier >= 3 ? Art.GOLD : pri);
        tu.plain(Art.circle(len, 0, r * (0.08 + 0.02 * tier), 10), Color.WHITE);
        tu.flash(Art.star(len, 0, r * 0.34, r * 0.12, 6, 0), Art.alpha(0xffe9a8, 230));
        // healing motes orbiting the hero, one more per tier
        for (int i = 0; i <= tier; i++) {
            GCompound m = orbitingOrb(0, 0, r * 0.95, r * 0.07, i * Math.PI * 2 / (tier + 1), 1.1, pri);
            Art.plain(m, Art.rect(-r * 0.05, -r * 0.015, r * 0.1, r * 0.03), Color.WHITE);
            Art.plain(m, Art.rect(-r * 0.015, -r * 0.05, r * 0.03, r * 0.1), Color.WHITE);
        }
        if (tier >= 3) crown(0, -r * 1.02, r * 0.2, 7);
    }

    /** Iron Imraan: heavy gauntlets that gain plating, pistons and finally a colossus fist. */
    private void gauntlets() {
        Gear tu = new Gear(r * 0.62);
        double size = r * (0.26 + 0.05 * tier);
        tu.poly(Art.rect(r * 0.18, -size, size * 1.5, size * 2), new Color(0x5a6472));
        tu.poly(Art.rect(r * 0.18 + size * 1.2, -size * 1.15, size * 0.5, size * 2.3), Art.METAL_LIGHT);
        for (int i = 0; i < 3; i++) tu.plain(Art.rect(r * 0.24 + i * size * 0.4, -size * 0.75, size * 0.22, size * 1.5), pri);
        if (tier >= 2) {   // hydraulic pistons
            tu.poly(Art.rect(r * 0.05, -size * 0.3, size * 0.5, size * 0.6), new Color(0x2e3440));
            tu.plain(Art.rect(r * 0.12, -size * 0.14, size * 0.4, size * 0.28), sec);
        }
        tu.flash(Art.star(r * 0.18 + size * 2.1, 0, r * 0.3, r * 0.11, 6, 0), Art.alpha(pri, 235));
        // shoulder plates grow with the tier
        for (int s = -1; s <= 1; s += 2) {
            ellipse(s * r * 0.5, r * 0.1, r * (0.16 + 0.03 * tier), r * (0.12 + 0.02 * tier), new Color(0x6a7482));
        }
    }

    /** Boom Sam: dynamite bundles, then a twin charge, then a nuclear cylinder. */
    private void dynamite() {
        Gear tu = new Gear(r * 0.5);
        int sticks = tier >= 2 ? 3 : 2;
        for (int i = 0; i < sticks; i++) {
            double y = (i - (sticks - 1) / 2.0) * r * 0.16;
            tu.poly(Art.rect(r * 0.3, y - r * 0.07, r * 0.34, r * 0.14), new Color(0xc0392b));
            tu.plain(Art.rect(r * 0.3, y - r * 0.03, r * 0.34, r * 0.05), new Color(0xe8745f));
        }
        tu.poly(Art.bar(r * 0.64, 0, r * 0.84, -r * 0.16, r * 0.03), new Color(0x8a6a3a));
        tu.plain(Art.star(r * 0.86, -r * 0.18, r * 0.1, r * 0.04, 6, 0), Art.alpha(0xffd166, 240));
        if (tier >= 3) {   // nuclear canister on the hip
            poly(Art.rect(-r * 0.72, r * 0.26, r * 0.28, r * 0.32), new Color(0x3a4a2e));
            plain(Art.circle(-r * 0.58, r * 0.42, r * 0.1, 10), Art.GOLD);
            plain(Art.circle(-r * 0.58, r * 0.42, r * 0.05, 8), new Color(0x1a1a1a));
        }
        tu.flash(Art.star(r * 1.0, 0, r * 0.36, r * 0.13, 8, 0), Art.alpha(0xffd166, 240));
    }

    /** Chillstin: frost shards that multiply and finally ring him in a freezing halo. */
    private void frost() {
        Gear tu = new Gear(r * 0.3);
        double len = r * 0.72;
        tu.poly(Art.rect(r * 0.1, -r * 0.06, len * 0.7, r * 0.12), new Color(0x7fa8c8));
        tu.poly(new double[] { r * 0.1 + len * 0.7, -r * 0.14, r * 0.1 + len, 0, r * 0.1 + len * 0.7, r * 0.14 }, pri);
        tu.plain(new double[] { r * 0.1 + len * 0.78, -r * 0.06, r * 0.1 + len * 0.94, 0, r * 0.1 + len * 0.78, r * 0.06 }, Color.WHITE);
        tu.flash(Art.star(r * 0.1 + len + r * 0.22, 0, r * 0.3, r * 0.1, 6, 0), Art.alpha(Color.WHITE, 235));
        int shards = 2 + tier;
        for (int i = 0; i < shards; i++) {
            GCompound s = orbitingOrb(0, 0, r * (0.95 + 0.04 * tier), r * 0.07, i * Math.PI * 2 / shards, 1.2, pri);
            Art.plain(s, Art.star(0, 0, r * 0.14, r * 0.05, 6, 0), Art.alpha(Color.WHITE, 220));
        }
        if (tier >= 3) {
            poly(Art.ring(0, 0, r * 1.12, r * 1.03, 20), Art.alpha(pri, 120));
        }
    }

    /** Kaiju Kai: a roaring maw that becomes an atomic breath emitter. */
    private void kaiju() {
        Gear tu = new Gear(r * 0.25);
        if (tier == 0) {   // roar: sonic rings in front
            for (int i = 1; i <= 3; i++) {
                tu.plain(Art.ring(r * (0.3 + i * 0.18), 0, r * (0.1 + i * 0.07), r * (0.06 + i * 0.07), 14), Art.alpha(pri, 190 - i * 40));
            }
        } else {           // breath: a glowing emitter and a widening cone
            tu.poly(Art.rect(r * 0.2, -r * 0.14, r * 0.3, r * 0.28), new Color(0x2a4a35));
            tu.plain(Art.circle(r * 0.5, 0, r * (0.12 + 0.03 * tier), 12), pri);
            tu.plain(Art.circle(r * 0.5, 0, r * (0.06 + 0.02 * tier), 10), Color.WHITE);
            tu.plain(new double[] { r * 0.56, -r * 0.1, r * (1.0 + 0.12 * tier), -r * (0.22 + 0.05 * tier),
                r * (1.0 + 0.12 * tier), r * (0.22 + 0.05 * tier), r * 0.56, r * 0.1 }, Art.alpha(pri, 110));
        }
        tu.flash(Art.star(r * 1.05, 0, r * 0.42, r * 0.15, 8, 0), Art.alpha(Color.WHITE, 230));
        // clawed hands
        for (int s = -1; s <= 1; s += 2) {
            for (int i = -1; i <= 1; i++) {
                plain(new double[] { s * r * 0.46 + i * r * 0.06, r * 0.56, s * r * 0.5 + i * r * 0.06, r * 0.7, s * r * 0.42 + i * r * 0.06, r * 0.62 },
                    Art.METAL_LIGHT);
            }
        }
        if (tier >= 3) pulseWave(pri, 2.0);
    }

    /** Abhi-Ace: an underslung missile pod that fills up with every tier. */
    private void missilePod() {
        Gear tu = new Gear(r * 0.3);
        tu.poly(Art.rect(r * 0.22, -r * 0.16, r * 0.5, r * 0.32), new Color(0x3a4658));
        int missiles = tier >= 3 ? 4 : tier >= 2 ? 3 : tier >= 1 ? 2 : 1;
        for (int i = 0; i < missiles; i++) {
            double y = (i - (missiles - 1) / 2.0) * r * 0.12;
            tu.poly(Art.rect(r * 0.6, y - r * 0.04, r * 0.26, r * 0.08), Art.METAL_LIGHT);
            tu.plain(new double[] { r * 0.86, y - r * 0.04, r * 0.98, y, r * 0.86, y + r * 0.04 }, pri);
        }
        tu.flash(Art.star(r * 1.1, 0, r * 0.3, r * 0.1, 5, 0), Art.alpha(pri, 235));
        // vapour trail under the jet
        plain(Art.rect(-r * 0.2, r * 0.92, r * 0.4, r * 0.05), Art.alpha(Color.WHITE, 90));
    }

    /** Zippy Matt: crackling tesla prongs and orbiting sparks. */
    private void lightning() {
        Gear tu = new Gear(r * 0.3);
        tu.poly(Art.rect(r * 0.2, -r * 0.05, r * 0.42, r * 0.1), Art.METAL);
        for (int s = -1; s <= 1; s += 2) {
            tu.poly(new double[] { r * 0.62, s * r * 0.04, r * 0.84, s * r * 0.18, r * 0.9, s * r * 0.1, r * 0.68, s * r * 0.0 }, pri);
        }
        tu.plain(Art.bolt(r * 0.3, r * 0.95, r * 0.1, r * 0.035), Art.alpha(Color.WHITE, 230));
        tu.flash(Art.star(r * 1.05, 0, r * 0.32, r * 0.1, 6, 0), Art.alpha(pri, 240));
        int sparks = 1 + tier;
        for (int i = 0; i < sparks; i++) {
            GCompound s = orbitingOrb(0, 0, r * 0.9, r * 0.06, i * Math.PI * 2 / sparks, 3.2, pri);
            Art.plain(s, Art.bolt(-r * 0.1, r * 0.1, r * 0.06, r * 0.025), Art.alpha(Color.WHITE, 230));
        }
        if (tier >= 3) poly(Art.ring(0, 0, r * 1.1, r * 1.02, 18), Art.alpha(pri, 110));
    }

    /** Sunny Joe: coins raining around him, more as the business grows. */
    private void coins() {
        int n = 2 + tier;
        for (int i = 0; i < n; i++) {
            GCompound c = orbitingOrb(0, -r * 0.1, r * (0.85 + 0.05 * tier), r * 0.11, i * Math.PI * 2 / n, 0.9, Art.GOLD);
            Art.plain(c, Art.rect(-r * 0.02, -r * 0.06, r * 0.04, r * 0.12), Art.GOLD_DARK);
        }
        // the phone he runs the hustle on
        poly(Art.rect(r * 0.3, r * 0.3, r * 0.2, r * 0.3), new Color(0x1f2630));
        plain(Art.rect(r * 0.33, r * 0.34, r * 0.14, r * 0.2), Art.alpha(pri, 220));
        if (tier >= 2) plain(Art.rect(r * 0.33, r * 0.34, r * 0.14, r * 0.06), Art.GOLD);
    }

    /** Nik-Scope: a long rifle whose scope and muzzle grow with every tier. */
    private void rifle() {
        Gear tu = new Gear(r * 0.35);
        double len = r * (1.0 + 0.17 * tier);
        tu.poly(Art.rect(-r * 0.2, -r * 0.05, len + r * 0.2, r * 0.1), new Color(0x2a2e38));
        tu.poly(Art.rect(r * 0.05, -r * 0.14, r * 0.3, r * 0.1), new Color(0x4a5260));
        tu.poly(Art.rect(r * 0.12, -r * 0.24, r * (0.26 + 0.05 * tier), r * 0.12), Art.METAL);
        tu.plain(Art.circle(r * 0.12 + r * (0.26 + 0.05 * tier), -r * 0.18, r * 0.05, 8), pri);
        tu.poly(Art.rect(len - r * 0.06, -r * (0.08 + 0.015 * tier), r * 0.18, r * (0.16 + 0.03 * tier)), pri);
        if (tier >= 3) {   // bipod and a laser line
            tu.poly(Art.bar(r * 0.7, r * 0.05, r * 0.86, r * 0.3, r * 0.025), Art.METAL);
            tu.poly(Art.bar(r * 0.7, r * 0.05, r * 0.56, r * 0.3, r * 0.025), Art.METAL);
            tu.plain(Art.rect(len, -r * 0.012, r * 0.9, r * 0.024), Art.alpha(pri, 150));
        }
        tu.flash(Art.star(len + r * 0.3, 0, r * 0.36, r * 0.11, 5, 0), Art.alpha(pri, 240));
    }

    /** Cami-Mine: a satchel of mines plus the one she is arming. */
    private void mines() {
        poly(Art.rect(-r * 0.76, r * 0.26, r * 0.32, r * 0.3), new Color(0x4a3a24));
        plain(Art.rect(-r * 0.74, r * 0.33, r * 0.28, r * 0.05), Art.shade(pri, 0.8));
        Gear tu = new Gear(r * 0.5);
        double rad = r * (0.14 + 0.025 * tier);
        tu.poly(Art.circle(r * 0.45, 0, rad, 12), new Color(0x3a4048));
        tu.plain(Art.ring(r * 0.45, 0, rad * 0.75, rad * 0.5, 12), pri);
        tu.plain(Art.circle(r * 0.45, 0, rad * 0.3, 8), Color.WHITE);
        for (int i = 0; i < 3; i++) {   // trigger prongs
            double a = i * Math.PI * 2 / 3 - Math.PI / 2;
            tu.poly(Art.bar(r * 0.45, 0, r * 0.45 + Math.cos(a) * rad * 1.5, Math.sin(a) * rad * 1.5, r * 0.022), Art.METAL_LIGHT);
        }
        tu.flash(Art.star(r * 0.45, 0, rad * 2.2, rad * 0.8, 8, 0), Art.alpha(pri, 230));
        // armed mines already on the belt, one per tier
        for (int i = 0; i <= tier; i++) {
            plain(Art.circle(-r * 0.68 + i * r * 0.15, r * 0.2, r * 0.055, 8), pri);
        }
    }

    /** Justin Time: a pocket watch whose hands spin faster at higher tiers. */
    private void clock() {
        Gear tu = new Gear(r * 0.45);
        tu.poly(Art.rect(r * 0.15, -r * 0.04, r * 0.3, r * 0.08), Art.METAL);
        double rad = r * (0.22 + 0.035 * tier);
        tu.poly(Art.circle(r * 0.62, 0, rad, 16), new Color(0x2a2340));
        tu.poly(Art.ring(r * 0.62, 0, rad, rad * 0.78, 16), tier >= 3 ? Art.GOLD : pri);
        tu.plain(Art.circle(r * 0.62, 0, rad * 0.14, 8), Color.WHITE);
        tu.flash(Art.star(r * 0.62, 0, rad * 2.0, rad * 0.7, 8, 0), Art.alpha(pri, 230));
        // the hands spin in place
        spinningPoly(new double[] { -r * 0.015, -r * 0.015, r * 0.015, -r * 0.015, r * 0.015, r * 0.17, -r * 0.015, r * 0.17 },
            r * 0.62, 0, Color.WHITE, 120 + 90 * tier);
        spinningPoly(new double[] { -r * 0.015, -r * 0.015, r * 0.015, -r * 0.015, r * 0.015, r * 0.1, -r * 0.015, r * 0.1 },
            r * 0.62, 0, Art.alpha(sec, 220), -220 - 120 * tier);
        if (tier >= 2) poly(Art.ring(0, 0, r * 1.08, r * 1.0, 20), Art.alpha(pri, 100));
    }

    /** Spear Hanbo: one spear, then a sharper head, then a trio across his back. */
    private void spear() {
        Gear tu = new Gear(r * 0.2);
        double len = r * (1.0 + 0.1 * tier);
        tu.poly(Art.rect(-r * 0.25, -r * 0.035, len, r * 0.07), new Color(0x8a6a3a));
        tu.poly(new double[] { len - r * 0.25, -r * (0.1 + 0.02 * tier), len + r * 0.2, 0, len - r * 0.25, r * (0.1 + 0.02 * tier) },
            Art.METAL_LIGHT);
        tu.plain(new double[] { len - r * 0.16, -r * 0.04, len + r * 0.1, 0, len - r * 0.16, r * 0.04 }, Color.WHITE);
        tu.poly(Art.rect(len - r * 0.32, -r * 0.07, r * 0.07, r * 0.14), pri);
        if (tier >= 2) {   // return-flight fletching
            tu.poly(new double[] { -r * 0.25, -r * 0.03, -r * 0.42, -r * 0.14, -r * 0.42, r * 0.14, -r * 0.25, r * 0.03 }, sec);
        }
        tu.flash(Art.star(len + r * 0.34, 0, r * 0.3, r * 0.1, 5, 0), Art.alpha(pri, 235));
        if (tier >= 3) {   // two spare spears crossed behind him
            for (int s = -1; s <= 1; s += 2) {
                poly(Art.bar(s * r * 0.2, r * 0.75, s * r * 0.75, -r * 0.5, r * 0.035), new Color(0x8a6a3a));
                plain(new double[] { s * r * 0.68, -r * 0.4, s * r * 0.85, -r * 0.62, s * r * 0.76, -r * 0.34 }, Art.METAL_LIGHT);
            }
        }
    }

    /** Thorn Tuhin: a thorn launcher wreathed in leaves. */
    private void thorns() {
        Gear tu = new Gear(r * 0.3);
        tu.poly(Art.rect(r * 0.15, -r * 0.08, r * 0.45, r * 0.16), new Color(0x4a3a24));
        for (int i = 0; i < 2 + tier; i++) {
            double y = (i - (1 + tier) / 2.0) * r * 0.1;
            tu.poly(new double[] { r * 0.6, y - r * 0.035, r * 0.88, y, r * 0.6, y + r * 0.035 }, pri);
        }
        tu.plain(new double[] { r * 0.28, -r * 0.2, r * 0.5, -r * 0.1, r * 0.3, -r * 0.03 }, new Color(0x2f7d3a));
        tu.plain(new double[] { r * 0.28, r * 0.2, r * 0.5, r * 0.1, r * 0.3, r * 0.03 }, new Color(0x2f7d3a));
        tu.flash(Art.star(r * 1.0, 0, r * 0.3, r * 0.1, 6, 0), Art.alpha(pri, 235));
        if (tier >= 2) {   // spore motes
            for (int i = 0; i <= tier; i++) orbitingOrb(0, 0, r * 0.95, r * 0.055, i * 2.1, 0.8, Art.alpha(pri, 220));
        }
    }

    /** Trapper Che: a bear-trap launcher and the traps hanging from his belt. */
    private void traps() {
        Gear tu = new Gear(r * 0.42);
        tu.poly(Art.rect(r * 0.18, -r * 0.1, r * 0.34, r * 0.2), new Color(0x3a4048));
        double jaw = r * (0.2 + 0.03 * tier);
        for (int s = -1; s <= 1; s += 2) {
            tu.poly(new double[] { r * 0.52, s * r * 0.04, r * 0.52 + jaw, s * jaw, r * 0.52 + jaw * 1.15, s * jaw * 0.5, r * 0.56, s * r * 0.02 },
                Art.METAL_LIGHT);
            for (int i = 0; i < 3; i++) {
                double t = 0.25 + i * 0.3;
                tu.plain(new double[] { r * 0.52 + jaw * t, s * jaw * t, r * 0.52 + jaw * t + r * 0.03, s * jaw * (t - 0.35),
                    r * 0.52 + jaw * t + r * 0.06, s * jaw * t }, Color.WHITE);
            }
        }
        tu.plain(Art.circle(r * 0.44, 0, r * 0.07, 8), pri);
        tu.flash(Art.star(r * 0.52 + jaw, 0, r * 0.3, r * 0.1, 6, 0), Art.alpha(pri, 235));
        for (int i = 0; i <= tier; i++) {   // spare traps on the belt
            plain(Art.ring(-r * 0.68 + i * r * 0.14, r * 0.3, r * 0.065, r * 0.035, 10), Art.METAL_LIGHT);
        }
        if (tier >= 2) {   // live current between the belt traps
            plain(Art.bolt(-r * 0.68, -r * 0.68 + tier * r * 0.14, r * 0.05, r * 0.02), Art.alpha(pri, 220));
        }
    }

    /** Blitz Arnav: a carbine that gains a longer magazine and finally a rocket tube. */
    private void carbine() {
        Gear tu = new Gear(r * 0.5);
        double len = r * (0.8 + 0.08 * tier);
        tu.poly(Art.rect(-r * 0.12, -r * 0.07, len + r * 0.12, r * 0.14), new Color(0x2e3440));
        tu.poly(Art.rect(r * 0.22, r * 0.05, r * 0.12, r * (0.18 + 0.05 * tier)), pri);   // magazine
        tu.poly(Art.rect(len - r * 0.04, -r * 0.05, r * 0.16, r * 0.1), Art.METAL_LIGHT);
        for (int i = 0; i < Math.min(4, 1 + tier); i++) {   // heat vents
            tu.plain(Art.rect(r * 0.42 + i * r * 0.1, -r * 0.05, r * 0.05, r * 0.1), Art.alpha(sec, 200));
        }
        if (tier >= 3) {   // underslung rocket tube
            tu.poly(Art.rect(r * 0.3, r * 0.1, r * 0.5, r * 0.12), new Color(0x3a4a2e));
            tu.plain(new double[] { r * 0.8, r * 0.1, r * 0.95, r * 0.16, r * 0.8, r * 0.22 }, Art.GOLD);
        }
        tu.flash(Art.star(len + r * 0.28, 0, r * 0.3, r * 0.1, 5, 0), Art.alpha(pri, 240));
    }

    /** Tanimbus: the command pod and its scanning dish. */
    private void commandPod() {
        Gear tu = new Gear(r * 0.45);
        tu.poly(Art.rect(r * 0.2, -r * 0.08, r * 0.28, r * 0.16), Art.METAL);
        tu.poly(new double[] { r * 0.48, -r * (0.2 + 0.03 * tier), r * 0.7, -r * 0.1, r * 0.7, r * 0.1, r * 0.48, r * (0.2 + 0.03 * tier) }, pri);
        tu.plain(Art.circle(r * 0.6, 0, r * 0.06, 8), Color.WHITE);
        tu.flash(Art.star(r * 0.86, 0, r * 0.26, r * 0.09, 4, 0), Art.alpha(sec, 230));
        // holographic command ring under the drone, wider with every tier
        poly(Art.ring(0, r * 0.95, r * (0.4 + 0.1 * tier), r * (0.33 + 0.1 * tier), 20), Art.alpha(pri, 110));
        if (tier >= 2) {
            for (int i = 0; i < 4; i++) {
                double a = i * Math.PI / 2 + Math.PI / 4;
                plain(Art.circle(Math.cos(a) * r * (0.45 + 0.1 * tier), r * 0.95 + Math.sin(a) * r * 0.12, r * 0.045, 8), sec);
            }
        }
        if (tier >= 3) pulseWave(pri, 2.4);
    }
}
