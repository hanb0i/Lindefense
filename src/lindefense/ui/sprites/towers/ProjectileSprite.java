package lindefense.ui.sprites.towers;

import acm.graphics.GCompound;
import acm.graphics.GOval;
import acm.graphics.GPolygon;
import java.awt.Color;
import java.util.ArrayList;
import java.util.List;
import lindefense.combat.Projectile;
import lindefense.sim.Vec;
import lindefense.ui.sprites.Animated;

/**
 * Cartoon projectile. Each sprite is one of a small set of {@link Style}s
 * (lance, token, shell, ...) built once from at most ~6 ACM objects; afterwards
 * {@link #sync} only moves and rotates it. Parts authored pointing +x turn
 * with the velocity; "spinner" parts tumble continuously; a glow may pulse.
 */
@SuppressWarnings({ "serial", "this-escape" })
public class ProjectileSprite extends GCompound implements Animated {
    private static final long serialVersionUID = 1L;

    /** Visual families; {@link ProjectileSprites} picks one per tower type. */
    public enum Style { LANCE, TOKEN, SLUG, SNIPPET, PAINT, NOTE, BOLT, PIN, BLADE, WAD, GALE, ORB, ROUND, BOOK, SHELL, SPARK, PULSE, DOT,
        /** Hero Store and Zethos families. */
        COMMAND, VOLLEY, CRYO, METEOR, DATA, DRONE, QUANTUM,
        /** Mr. Lindemann: a black hole of Java code (dark core, accretion ring, orbiting code fragments). */
        SINGULARITY }

    private final List<GPolygon> oriented = new ArrayList<>(4);
    private final List<GPolygon> spinners = new ArrayList<>(3);
    private GOval pulseRing;
    private GPolygon flicker;
    private Color flickerColor;
    private double spinSpeed;
    private double heading;
    private double t;
    private double baseRadius;
    private boolean alive = true;

    /**
     * Builds a projectile sprite.
     *
     * @param style visual family
     * @param tier  source tower tier (0-4) used to scale the design up
     * @param size  logical projectile radius from {@link Projectile#getSize()}
     * @param c     main colour
     * @param c2    accent colour
     */
    public ProjectileSprite(Style style, int tier, double size, Color c, Color c2) {
        tier = Math.max(0, Math.min(4, tier));
        double k = (size / 6.0) * (1 + 0.12 * tier);
        baseRadius = size * (1 + 0.12 * tier);
        build(style, tier, k, c, c2);
    }

    private GPolygon part(double[] xy, Color fill) {
        GPolygon ink = Art.rawPoly(Art.expand(xy, Art.OUT * 0.8), Art.INK, Art.INK);
        add(ink);
        oriented.add(ink);
        GPolygon p = Art.rawPoly(xy, fill, Art.shade(fill, 0.75));
        add(p);
        oriented.add(p);
        return p;
    }

    private GPolygon plainPart(double[] xy, Color fill) {
        GPolygon p = Art.rawPoly(xy, fill, fill);
        add(p);
        oriented.add(p);
        return p;
    }

    private GPolygon spinPart(double[] xy, Color fill, boolean outline) {
        if (outline) {
            GPolygon ink = Art.rawPoly(Art.expand(xy, Art.OUT * 0.8), Art.INK, Art.INK);
            add(ink);
            spinners.add(ink);
        }
        GPolygon p = Art.rawPoly(xy, fill, outline ? Art.shade(fill, 0.75) : fill);
        add(p);
        spinners.add(p);
        return p;
    }

    private void build(Style s, int tier, double k, Color c, Color c2) {
        switch (s) {
            case LANCE: {
                double len = k * (16 + 4 * tier), hw = k * 1.7;
                plainPart(Art.wedge(-len * 0.3, -len * 1.4, hw * 1.6, 0), Art.alpha(c, 90));
                part(new double[] { -len / 2, -hw, len / 2 - hw * 2.5, -hw, len / 2 + hw, 0, len / 2 - hw * 2.5, hw, -len / 2, hw }, tier >= 4 ? Art.GOLD : c);
                plainPart(Art.rect(-len * 0.4, -hw * 0.35, len * 0.75, hw * 0.7), tier >= 3 ? Color.WHITE : c2);
                break;
            }
            case TOKEN: {
                double rad = k * 5.5;
                plainPart(Art.wedge(0, -rad * 3, rad * 0.8, 0), Art.alpha(c, 80));
                part(tier >= 3 ? Art.star(0, 0, rad * 1.2, rad * 0.8, 8, 0) : Art.circle(0, 0, rad, 14), c);
                plainPart(Art.circle(0, 0, rad * 0.45, 10), Color.WHITE);
                plainPart(Art.circle(-rad * 0.35, -rad * 0.4, rad * 0.22, 6), Art.alpha(Color.WHITE, 200));
                break;
            }
            case SLUG: {
                double len = k * 14, hw = k * 2.2;
                plainPart(Art.wedge(-len * 0.2, -len * 1.8, hw * 1.3, 0), Art.alpha(c2, 100));
                part(Art.bar(-len / 2, 0, len / 2, 0, hw), c);
                plainPart(Art.rect(-len * 0.35, -hw * 0.3, len * 0.7, hw * 0.6), tier >= 4 ? Color.WHITE : c2);
                plainPart(Art.circle(len / 2, 0, hw * 1.1, 8), Art.alpha(Color.WHITE, 220));
                break;
            }
            case SNIPPET: {
                double w = k * 11, h = k * 7;
                part(Art.rect(-w / 2, -h / 2, w, h), c2);
                plainPart(Art.rect(-w * 0.38, -h * 0.3, w * 0.12, h * 0.6), c);
                plainPart(Art.rect(w * 0.26, -h * 0.3, w * 0.12, h * 0.6), c);
                plainPart(Art.rect(-w * 0.18, -h * 0.08, w * 0.36, h * 0.16), tier >= 4 ? Art.GOLD : c);
                spinSpeed = 0;
                break;
            }
            case PAINT: {
                double rad = k * 5.5;
                part(Art.circle(0, 0, rad, 14), c);
                plainPart(Art.circle(-rad * 0.3, -rad * 0.35, rad * 0.3, 8), Art.alpha(Color.WHITE, 200));
                spinPart(Art.circle(rad * 1.35, 0, rad * 0.35, 8), Art.shade(c, 1.2), false);
                spinPart(Art.circle(-rad * 0.6, rad * 1.25, rad * 0.28, 8), c2, false);
                spinSpeed = 400;
                break;
            }
            case NOTE: {
                double rad = k * 4.5;
                spinPart(Art.bar(rad * 0.9, 0, rad * 0.9, -rad * 3.2, rad * 0.3), c, true);
                spinPart(new double[] { rad * 0.9, -rad * 3.2, rad * 2.4, -rad * 2.2, rad * 0.9, -rad * 1.8 }, c, true);
                spinPart(Art.regular(0, 0, rad, 10, 0), c, true);
                spinPart(Art.circle(-rad * 0.3, -rad * 0.3, rad * 0.3, 6), Art.alpha(Color.WHITE, 200), false);
                spinSpeed = 240;
                break;
            }
            case BOLT: {
                double len = k * 16, amp = k * 4;
                flicker = part(Art.bolt(-len / 2, len / 2, amp, k * 1.5), c2);
                flickerColor = c2;
                plainPart(Art.scaled(Art.bolt(-len / 2, len / 2, amp, k * 1.5), 0.5), Color.WHITE);
                break;
            }
            case PIN: {
                double len = k * 13, hw = k * 3;
                plainPart(Art.wedge(0, -len * 1.3, hw * 0.6, 0), Art.alpha(c, 90));
                part(Art.wedge(-len / 2, len / 2, hw, 0), c);
                part(Art.circle(-len * 0.3, 0, hw * 0.7, 10), c2);
                break;
            }
            case BLADE: {
                double rad = k * 7;
                spinPart(Art.star(0, 0, rad, rad * 0.45, 3 + tier / 2, 0), c, true);
                spinPart(Art.circle(0, 0, rad * 0.25, 8), c2, false);
                spinSpeed = 900;
                break;
            }
            case WAD: {
                double rad = k * 6;
                double[] v = new double[14];
                double[] bumps = { 1, 0.8, 1.05, 0.85, 1, 0.75, 0.95 };
                for (int i = 0; i < 7; i++) {
                    double a = i * 2 * Math.PI / 7;
                    v[2 * i] = Math.cos(a) * rad * bumps[i];
                    v[2 * i + 1] = Math.sin(a) * rad * bumps[i];
                }
                spinPart(v, c, true);
                spinPart(Art.circle(-rad * 0.3, -rad * 0.3, rad * 0.3, 6), Art.alpha(Color.WHITE, 200), false);
                spinSpeed = 360;
                break;
            }
            case GALE: {
                double rad = k * 8;
                double[] v = new double[28];
                for (int i = 0; i < 7; i++) {
                    double a = -Math.PI * 0.45 + i * Math.PI * 0.9 / 6;
                    v[2 * i] = Math.cos(a) * rad;
                    v[2 * i + 1] = Math.sin(a) * rad;
                }
                for (int i = 0; i < 7; i++) {
                    double a = Math.PI * 0.45 - i * Math.PI * 0.9 / 6;
                    v[14 + 2 * i] = Math.cos(a) * rad * 0.55 + rad * 0.25;
                    v[14 + 2 * i + 1] = Math.sin(a) * rad * 0.55;
                }
                spinPart(v, c2, true);
                spinPart(Art.scaled(v, 0.5), Art.alpha(Color.WHITE, 160), false);
                spinSpeed = 720;
                break;
            }
            case ORB: {
                double rad = k * 5.5;
                plainPart(Art.wedge(0, -rad * 2.5, rad * 0.7, 0), Art.alpha(c, 80));
                part(Art.circle(0, 0, rad, 14), c);
                plainPart(Art.circle(-rad * 0.3, -rad * 0.35, rad * 0.32, 8), Art.alpha(Color.WHITE, 210));
                if (tier >= 2) {
                    spinPart(Art.circle(rad * 1.7, 0, rad * 0.35, 8), c2, false);
                    spinPart(Art.circle(-rad * 1.7, 0, rad * 0.35, 8), c2, false);
                    spinSpeed = 500;
                }
                break;
            }
            case ROUND: {
                double len = k * 18, hw = k * 1.3;
                plainPart(Art.rect(-len * 1.6, -hw * 0.6, len * 1.3, hw * 1.2), Art.alpha(c2, 110));
                part(Art.bar(-len / 2, 0, len / 2, 0, hw), tier >= 4 ? Art.GOLD : c);
                plainPart(Art.rect(-len * 0.3, -hw * 0.3, len * 0.7, hw * 0.6), Color.WHITE);
                break;
            }
            case BOOK: {
                double w = k * 10, h = k * 7.5;
                spinPart(Art.rect(-w / 2, -h / 2, w, h), c, true);
                spinPart(Art.rect(-w / 2, -h / 2, w * 0.2, h), Art.shade(c, 0.7), false);
                spinPart(Art.rect(-w * 0.15, -h * 0.25, w * 0.5, h * 0.12), Color.WHITE, false);
                spinSpeed = 300;
                break;
            }
            case SHELL: {
                double len = k * 15, hw = k * 3.2;
                plainPart(Art.circle(-len * 0.9, 0, hw * 1.2, 8), Art.alpha(0xbbbbbb, 110));
                plainPart(Art.circle(-len * 1.5, hw * 0.3, hw * 0.9, 8), Art.alpha(0xbbbbbb, 70));
                part(new double[] { -len / 2, -hw, len * 0.2, -hw, len / 2, 0, len * 0.2, hw, -len / 2, hw }, Art.rgb(0x2b2b33));
                plainPart(Art.rect(-len * 0.2, -hw * 0.9, len * 0.18, hw * 1.8), Art.GOLD);
                plainPart(new double[] { len * 0.2, -hw * 0.8, len / 2, 0, len * 0.2, hw * 0.8 }, tier >= 4 ? Art.GOLD : Art.rgb(0xff7a00));
                break;
            }
            case PULSE: {
                pulseRing = new Flat.Oval(-k * 6, -k * 6, k * 12, k * 12);
                pulseRing.setColor(Art.alpha(c, 200));
                add(pulseRing);
                plainPart(Art.circle(0, 0, k * 2.5, 8), Art.alpha(c, 200));
                break;
            }
            case SPARK: {
                double rad = k * 6;
                spinPart(Art.star(0, 0, rad, rad * 0.4, 4, 0), c, true);
                spinPart(Art.circle(0, 0, rad * 0.3, 8), Color.WHITE, false);
                spinSpeed = 420;
                break;
            }
            case COMMAND: {   // Brad: a big command-energy sphere wrapped in crackling arcs
                double rad = k * 8;
                plainPart(Art.wedge(0, -rad * 2.6, rad * 0.9, 0), Art.alpha(Art.rgb(0xfff3a0), 90));
                part(Art.circle(0, 0, rad, 16), c);
                plainPart(Art.circle(0, 0, rad * 0.6, 12), Art.rgb(0xfff3a0));
                plainPart(Art.circle(0, 0, rad * 0.3, 10), Color.WHITE);
                spinPart(Art.star(0, 0, rad * 1.5, rad * 0.9, 5, 0), Art.alpha(Art.rgb(0xfff3a0), 150), false);
                spinSpeed = 380;
                break;
            }
            case VOLLEY: {   // Brandon: slim lime tracer bolt
                double len = k * 15, hw = k * 1.2;
                plainPart(Art.rect(-len * 1.5, -hw * 0.5, len * 1.2, hw), Art.alpha(c, 110));
                part(new double[] { -len / 2, -hw, len / 2 - hw, -hw, len / 2 + hw * 2, 0, len / 2 - hw, hw, -len / 2, hw }, c);
                plainPart(Art.rect(-len * 0.35, -hw * 0.35, len * 0.7, hw * 0.7), Color.WHITE);
                break;
            }
            case CRYO: {   // Rohan: tumbling ice crystal with a frost trail
                double rad = k * 6.5;
                plainPart(Art.wedge(0, -rad * 2.4, rad * 0.7, 0), Art.alpha(Art.rgb(0x8fe6ff), 100));
                spinPart(Art.star(0, 0, rad, rad * 0.45, 6, 0), Art.rgb(0x8fe6ff), true);
                spinPart(Art.star(0, 0, rad * 0.55, rad * 0.25, 6, 30), Color.WHITE, false);
                spinSpeed = 260;
                break;
            }
            case METEOR: {   // Ronil: molten rock with a fiery tail
                double rad = k * 7.5;
                plainPart(Art.wedge(0, -rad * 3.2, rad * 1.1, 0), Art.alpha(Art.rgb(0xff5a1f), 120));
                plainPart(Art.wedge(0, -rad * 2.2, rad * 0.7, 0), Art.alpha(Art.rgb(0xffd166), 160));
                double[] v = new double[16];
                double[] bumps = { 1, 0.82, 1.08, 0.9, 1, 0.78, 1.04, 0.86 };
                for (int i = 0; i < 8; i++) { double a = i * Math.PI / 4; v[2 * i] = Math.cos(a) * rad * bumps[i]; v[2 * i + 1] = Math.sin(a) * rad * bumps[i]; }
                spinPart(v, Art.rgb(0x4a3530), true);
                spinPart(Art.circle(rad * 0.2, rad * 0.1, rad * 0.35, 8), Art.rgb(0xffb02e), false);
                spinPart(Art.circle(-rad * 0.35, -rad * 0.3, rad * 0.2, 6), Art.rgb(0xff5a1f), false);
                spinSpeed = 200;
                break;
            }
            case DATA: {   // Shashank: a green data packet trailing bits
                double w = k * 9, h = k * 6;
                plainPart(Art.rect(-w * 1.6, -h * 0.15, w * 0.3, h * 0.3), Art.alpha(c, 160));
                plainPart(Art.rect(-w * 1.15, -h * 0.15, w * 0.3, h * 0.3), Art.alpha(c, 200));
                part(Art.regular(0, 0, w * 0.6, 6, 0), c);
                plainPart(Art.rect(-w * 0.25, -h * 0.25, w * 0.15, h * 0.5), Color.WHITE);
                plainPart(Art.rect(w * 0.05, -h * 0.25, w * 0.15, h * 0.5), Color.WHITE);
                break;
            }
            case DRONE: {   // Owen's drones: short cyan pulse dart
                double len = k * 10, hw = k * 1.6;
                plainPart(Art.wedge(-len * 0.3, -len * 1.4, hw, 0), Art.alpha(Art.rgb(0x5fd6ff), 120));
                part(Art.wedge(-len / 2, len / 2, hw * 1.4, 0), Art.rgb(0x5fd6ff));
                plainPart(Art.circle(len * 0.1, 0, hw * 0.6, 6), Color.WHITE);
                break;
            }
            case QUANTUM: {   // Zethos: a violet-cyan quantum diamond with orbiting probability nodes
                double rad = k * (5.5 + 0.6 * tier);
                plainPart(Art.wedge(0, -rad * (2.4 + 0.5 * tier), rad * 0.75, 0), Art.alpha(c2, 90 + 25 * tier));
                part(new double[] { -rad, 0, 0, -rad * 0.7, rad * 1.3, 0, 0, rad * 0.7 }, c);
                plainPart(new double[] { -rad * 0.4, 0, 0, -rad * 0.3, rad * 0.6, 0, 0, rad * 0.3 }, c2);
                plainPart(Art.circle(0, 0, rad * 0.18, 6), Color.WHITE);
                if (tier >= 2) {
                    spinPart(Art.circle(rad * 1.5, 0, rad * 0.25, 8), c2, false);
                    spinPart(Art.circle(-rad * 1.5, 0, rad * 0.25, 8), tier >= 4 ? Art.GOLD : c, false);
                    spinSpeed = 600;
                }
                break;
            }
            case SINGULARITY: {
                double rad = k * 7;
                plainPart(Art.ring(0, 0, rad * 1.9, rad * 1.25, 18), Art.alpha(c, 170));
                part(Art.circle(0, 0, rad, 14), new Color(0x07040f));
                plainPart(Art.ring(0, 0, rad * 1.25, rad * 1.0, 16), Art.alpha(c2, 230));
                // code fragments ({ } ;) orbiting the core
                spinPart(Art.rect(rad * 2.0, -rad * 0.18, rad * 0.55, rad * 0.36), Color.WHITE, false);
                spinPart(Art.rect(-rad * 2.55, -rad * 0.18, rad * 0.55, rad * 0.36), c, false);
                spinPart(Art.rect(-rad * 0.18, rad * 2.0, rad * 0.36, rad * 0.55), c2, false);
                spinSpeed = 420;
                break;
            }
            case DOT: default: {
                double rad = k * 5.5;
                part(Art.circle(0, 0, rad, 12), c);
                plainPart(Art.circle(-rad * 0.3, -rad * 0.35, rad * 0.3, 8), Art.alpha(Color.WHITE, 200));
                break;
            }
        }
    }

    /** Positions the sprite on the projectile and turns it along its velocity. */
    public void sync(Projectile p, double time) {
        if (p == null) return;
        alive = p.isAlive();
        Vec pos = p.getPosition(), v = p.getVelocity();
        place(pos.x, pos.y, v.x, v.y, time);
    }

    /** Manual placement (used by galleries and tests). */
    public void place(double x, double y, double vx, double vy, double time) {
        setLocation(x, y);
        if (Math.abs(vx) + Math.abs(vy) > 1e-6 && !oriented.isEmpty()) {
            double want = Math.atan2(vy, vx);
            double d = want - heading;
            while (d > Math.PI) d -= 2 * Math.PI;
            while (d < -Math.PI) d += 2 * Math.PI;
            if (Math.abs(d) > 1e-4) {
                double deg = -Math.toDegrees(d);
                for (GPolygon q : oriented) q.rotate(deg);
                heading = want;
            }
        }
    }

    /** Advances spin / pulse; returns false once the synced projectile has died. */
    @Override public boolean step(double dt) {
        t += dt;
        if (spinSpeed != 0) {
            double deg = spinSpeed * dt;
            for (GPolygon q : spinners) q.rotate(deg);
        }
        if (pulseRing != null) {
            double ph = (t % 0.5) / 0.5;
            double rad = baseRadius * (0.6 + 1.4 * ph);
            pulseRing.setBounds(-rad, -rad, 2 * rad, 2 * rad);
            pulseRing.setColor(Art.alpha(pulseRing.getColor(), (int) (220 * (1 - ph))));
        }
        if (flicker != null) {
            flicker.setFillColor(((int) (t * 30)) % 2 == 0 ? flickerColor : Art.shade(flickerColor, 1.4));
        }
        return alive;
    }

    /** Marks the sprite finished so the next {@link #step} returns false. */
    public void finish() { alive = false; }
}
