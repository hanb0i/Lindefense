package lindefense.ui;

import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.Shape;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;
import java.awt.geom.Path2D;
import java.awt.geom.RoundRectangle2D;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.enemy.PalantirProtocols;
import lindefense.map.GameMap;
import lindefense.sim.Game;
import lindefense.sim.PromptInjection;
import lindefense.sim.Vec;
import lindefense.sim.WindowLink;
import lindefense.tower.Intrusion;
import lindefense.tower.Tower;

/**
 * In-world renderer for prompt injection and Palantir's phase abilities, drawn above the enemies in world coordinates.
 * Like {@link WorldFx} it is <b>immediate mode</b>: one lightweight {@link GObject} paints straight from the
 * simulation's state every frame, so nothing has to be created or removed when an effect starts or ends.
 * <ul>
 *   <li>Prompt Injection enemies carry a speech-bubble sign, "IGNORE PREVIOUS INSTRUCTIONS", that flashes red and
 *       throws a ring of its reach when the enemy broadcasts.</li>
 *   <li>Hijacked towers get a red pulsing ring and a red HIJACKED tag, a red link back to whoever hijacked them for the
 *       first moment, and a lightning beam to each neighbour they zap. Disabled towers are tagged orange, towers
 *       blinded by the Panopticon violet.</li>
 *   <li>Palantir: the rotating Panopticon beam (phase 1), its own giant sign and broadcast rings (phase 2), the kill
 *       switch pulse and the <b>seal</b> (a rotating hexagonal cage with a padlock and SEALED tag) while the window
 *       grab seals it (phase 3). Holographic decoys flicker with scanlines and carry a HOLOGRAM tag.</li>
 *   <li>While Palantir is sealed a banner along the bottom of the playfield tells the player to drag the window back.</li>
 * </ul>
 */
final class IntrusionFx {
    /** Most injector signs drawn at once (the nearest-to-exit ones come first in the enemy list order). */
    static final int MAX_SIGNS = 16;
    private static final Color INK = new Color(18, 16, 30);
    private static final Color BUBBLE = new Color(252, 248, 236);
    private static final Color SIGN_RED = new Color(0xd6203a);
    private static final Color HIJACK = new Color(0xff3b4e);
    private static final Color DISABLED = new Color(0xffa040);
    private static final Color BLINDED = new Color(0xc79bff);
    private static final Color HOLO = new Color(0x8ad8ff);

    private final Game game;
    private final GObject layer = new Layer();
    private final Map<Integer, BasicStroke> strokes = new HashMap<>();
    private final Ellipse2D.Double ell = new Ellipse2D.Double();
    private final Line2D.Double line = new Line2D.Double();
    private final Path2D.Double path = new Path2D.Double();
    private final RoundRectangle2D.Double round = new RoundRectangle2D.Double();
    private final Font signFont = Cyber.mono(Font.BOLD, 9);
    private final Font bigSignFont = Cyber.mono(Font.BOLD, 13);
    private final Font tagFont = Cyber.mono(Font.BOLD, 10);
    private final Font bannerFont = Cyber.mono(Font.BOLD, 20);
    private final Font bannerSub = Cyber.mono(Font.BOLD, 13);
    private double time;
    private int lod;

    IntrusionFx(Game game) { this.game = game; }

    /** The layer to add to the world view (above the enemies). */
    GObject layer() { return layer; }

    void setLod(int lod) { this.lod = lod; }

    void update(double dt) { time += dt; }

    private final class Layer extends GObject {
        private static final long serialVersionUID = 1L;
        @Override public GRectangle getBounds() { return new GRectangle(0, 0, GameMap.WIDTH, GameMap.HEIGHT); }
        @Override public void paint(Graphics g) {
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                Cyber.quality(g2);
                paintAll(g2);
            } catch (RuntimeException ex) {
                ex.printStackTrace();
            } finally {
                g2.dispose();
            }
        }
    }

    // ------------------------------------------------------------------ frame
    private void paintAll(Graphics2D g) {
        Boss pal = game.getPalantir();
        boolean palAlive = pal != null && pal.isAlive() && pal.getProtocols() != null;
        if (palAlive) paintPalantirUnder(g, pal);
        List<Tower> towers = game.getTowerManager().getTowers();
        for (int i = 0; i < towers.size(); i++) {
            Tower t = towers.get(i);
            if (t.isAlive() && t.isOffline()) paintLinks(g, t);
        }
        for (int i = 0; i < towers.size(); i++) {
            Tower t = towers.get(i);
            if (t.isAlive() && t.isOffline()) paintTowerState(g, t);
        }
        List<Enemy> es = game.getEnemyManager().getEnemies();
        int signs = 0;
        for (int i = 0; i < es.size(); i++) {
            Enemy e = es.get(i);
            if (!e.isAlive() || e.isStored()) continue;
            if (e.getType() == EnemyType.PALANTIR_HOLOGRAM) paintHologram(g, e);
            if (e.has(Modifier.INJECTION) && signs < MAX_SIGNS) { paintSign(g, e); signs++; }
        }
        if (palAlive) paintPalantirOver(g, pal);
        paintTakeoverBanner(g, pal);
    }

    // ------------------------------------------------------------------ injector signs
    private void paintSign(Graphics2D g, Enemy e) {
        double since = game.getInjection().sinceBroadcast(e);
        boolean flash = since < 0.8;
        double x = e.getPosition().x, y = e.getPosition().y, r = e.getRadius();
        if (flash) {   // the reach of the broadcast, expanding
            double k = since / 0.8;
            ring(g, x, y, PromptInjection.RADIUS * (0.35 + 0.65 * k), col(HIJACK, 200 * (1 - k)), 3 - 2 * k);
            oval(g, x, y, PromptInjection.RADIUS, PromptInjection.RADIUS, col(HIJACK, 26 * (1 - k)), null, 0);
        }
        double bob = Math.sin(time * 3 + e.getId()) * 1.5;
        drawBubble(g, x, y - r - 6 + bob, "IGNORE PREVIOUS", "INSTRUCTIONS", signFont, flash && ((int) (since * 10)) % 2 == 0);
    }

    /** A speech bubble whose tail points down at (tx, ty); two text lines. */
    private void drawBubble(Graphics2D g, double tx, double ty, String l1, String l2, Font f, boolean alarm) {
        FontMetrics fm = g.getFontMetrics(f);
        double tw = Math.max(fm.stringWidth(l1), fm.stringWidth(l2));
        double lh = fm.getAscent() + 1;
        double w = tw + 12, h = lh * 2 + 7;
        double bx = tx - w / 2, by = ty - 9 - h;
        Color fill = alarm ? SIGN_RED : BUBBLE, text = alarm ? Color.WHITE : SIGN_RED;
        round.setRoundRect(bx, by, w, h, 9, 9);
        path.reset();
        path.moveTo(tx - 6, by + h - 1);
        path.lineTo(tx, ty);
        path.lineTo(tx + 6, by + h - 1);
        path.closePath();
        g.setStroke(st(3.2)); g.setColor(INK); g.draw(round); g.draw(path);
        g.setColor(fill); g.fill(round); g.fill(path);
        g.setStroke(st(1.4)); g.setColor(alarm ? Color.WHITE : SIGN_RED); g.draw(round);
        g.setFont(f);
        g.setColor(text);
        g.drawString(l1, (float) (tx - fm.stringWidth(l1) / 2.0), (float) (by + 3 + lh - 1));
        g.drawString(l2, (float) (tx - fm.stringWidth(l2) / 2.0), (float) (by + 3 + 2 * lh - 1));
    }

    // ------------------------------------------------------------------ towers
    /** Hijack link (from the hijacker, briefly) and zap beams (from a hijacked tower to its victims). */
    private void paintLinks(Graphics2D g, Tower t) {
        Intrusion in = t.getIntrusion();
        Vec p = t.getPosition();
        if (in.isHijacked()) {
            Object src = in.getHijacker();
            Vec from = src instanceof Enemy && ((Enemy) src).isAlive() ? ((Enemy) src).getPosition() : null;
            if (from != null) {
                double a = in.getAge() < 0.9 ? 230 : 70;
                g.setStroke(dashed(in.getAge() < 0.9 ? 2.6 : 1.4, 7, 6, -time * 40));
                g.setColor(col(HIJACK, a));
                line.setLine(from.x, from.y, p.x, p.y);
                g.draw(line);
            }
            Tower v = in.getLastVictim();
            if (v != null && v.isAlive() && in.getLastZapAge() < 0.45) lightning(g, p, v.getPosition(), 1 - in.getLastZapAge() / 0.45, t.getId());
        }
    }

    private void lightning(Graphics2D g, Vec a, Vec b, double strength, int seed) {
        path.reset();
        path.moveTo(a.x, a.y);
        int n = 7;
        double dx = b.x - a.x, dy = b.y - a.y, len = Math.max(1, Math.hypot(dx, dy));
        double nx = -dy / len, ny = dx / len;
        for (int i = 1; i < n; i++) {
            double f = i / (double) n;
            double j = Math.sin(seed * 12.9898 + i * 78.233 + time * 37) * 9;
            path.lineTo(a.x + dx * f + nx * j, a.y + dy * f + ny * j);
        }
        path.lineTo(b.x, b.y);
        g.setStroke(st(5)); g.setColor(col(HIJACK, 90 * strength)); g.draw(path);
        g.setStroke(st(2)); g.setColor(col(new Color(0xffd0e0), 255 * strength)); g.draw(path);
        oval(g, b.x, b.y, 10 * strength + 4, 10 * strength + 4, col(DISABLED, 120 * strength), null, 0);
    }

    private void paintTowerState(Graphics2D g, Tower t) {
        Intrusion in = t.getIntrusion();
        Vec p = t.getPosition();
        double r = t.getRadius();
        Color c = in.isHijacked() ? HIJACK : in.isDisabled() ? DISABLED : BLINDED;
        String tag = in.isHijacked() ? "HIJACKED" : in.isDisabled() ? "DISABLED" : "BLINDED";
        double pulse = 0.5 + 0.5 * Math.sin(time * (in.isHijacked() ? 11 : 7) + t.getId());
        oval(g, p.x, p.y, r * 1.45, r * 1.45, col(c, 30 + 40 * pulse), null, 0);
        g.setStroke(in.isHijacked() ? st(2.6) : dashed(2.2, 5, 4, time * 20));
        ell.setFrame(p.x - r * 1.45, p.y - r * 1.45, r * 2.9, r * 2.9);
        g.setColor(col(c, 170 + 80 * pulse));
        g.draw(ell);
        if (in.isBlinded()) {   // a struck-through eye
            double ex = p.x, ey = p.y - r * 0.1;
            path.reset();
            path.moveTo(ex - r * 0.75, ey);
            path.quadTo(ex, ey - r * 0.6, ex + r * 0.75, ey);
            path.quadTo(ex, ey + r * 0.6, ex - r * 0.75, ey);
            g.setStroke(st(2.4)); g.setColor(col(INK, 200)); g.draw(path);
            g.setStroke(st(1.4)); g.setColor(Color.WHITE); g.draw(path);
            seg(g, ex - r * 0.7, ey + r * 0.5, ex + r * 0.7, ey - r * 0.5, BLINDED, 2.6);
        }
        tag(g, p.x, p.y + r * 1.45 + 13, tag + " " + (int) Math.ceil(in.getRemaining()) + "s", c);
    }

    /** A small dark chip with coloured text centred at (cx, baseline cy). */
    private void tag(Graphics2D g, double cx, double cy, String s, Color c) {
        if (lod >= 2) return;
        FontMetrics fm = g.getFontMetrics(tagFont);
        double w = fm.stringWidth(s) + 10, h = fm.getAscent() + 5;
        round.setRoundRect(cx - w / 2, cy - h + 3, w, h, 6, 6);
        g.setColor(new Color(6, 8, 18, 220)); g.fill(round);
        g.setStroke(st(1.2)); g.setColor(c); g.draw(round);
        g.setFont(tagFont);
        g.drawString(s, (float) (cx - fm.stringWidth(s) / 2.0), (float) (cy));
    }

    // ------------------------------------------------------------------ Palantir
    /** Under the boss's own overlays: the Panopticon beam. */
    private void paintPalantirUnder(Graphics2D g, Boss pal) {
        PalantirProtocols pr = pal.getProtocols();
        if (!pr.isBeamActive(pal)) return;
        Vec o = pal.getPosition();
        double a = pr.getBeamAngle(), w = PalantirProtocols.PANOPTICON_HALF_WIDTH, R = PalantirProtocols.PANOPTICON_RANGE;
        g.setStroke(dashed(1.6, 6, 8, time * 10));
        g.setColor(col(BLINDED, 90));
        ell.setFrame(o.x - R, o.y - R, R * 2, R * 2);
        g.draw(ell);
        for (int k = 4; k >= 1; k--) {   // soft wedge: nested fans, brightest in the middle, plus a fading trail behind
            double ww = w * (0.3 + 0.3 * k);
            path.reset();
            path.moveTo(o.x, o.y);
            path.lineTo(o.x + Math.cos(a - ww) * R, o.y + Math.sin(a - ww) * R);
            path.lineTo(o.x + Math.cos(a + ww) * R, o.y + Math.sin(a + ww) * R);
            path.closePath();
            g.setColor(col(new Color(0xd9c2ff), 34 + 22 * (4 - k)));
            g.fill(path);
        }
        for (int k = 1; k <= 5; k++) {
            double ta = a - w - k * 0.09;
            path.reset();
            path.moveTo(o.x, o.y);
            path.lineTo(o.x + Math.cos(ta - 0.045) * R, o.y + Math.sin(ta - 0.045) * R);
            path.lineTo(o.x + Math.cos(ta + 0.045) * R, o.y + Math.sin(ta + 0.045) * R);
            path.closePath();
            g.setColor(col(BLINDED, 34 - 6 * k));
            g.fill(path);
        }
        seg(g, o.x, o.y, o.x + Math.cos(a) * R, o.y + Math.sin(a) * R, col(INK, 120), 4);
        seg(g, o.x, o.y, o.x + Math.cos(a) * R, o.y + Math.sin(a) * R, col(Color.WHITE, 230), 2);
        oval(g, o.x + Math.cos(a) * R, o.y + Math.sin(a) * R, 6, 6, col(Color.WHITE, 200), col(BLINDED, 230), 1.5);
    }

    /** Over everything: the phase-2 sign and broadcast rings, the kill switch pulse and the seal. */
    private void paintPalantirOver(Graphics2D g, Boss pal) {
        PalantirProtocols pr = pal.getProtocols();
        Vec o = pal.getPosition();
        double r = pal.getRadius();
        if (pal.getPhase() == 1) {
            double age = pr.getLastBroadcastAge();
            if (age < 1.4) {
                double k = age / 1.4;
                ring(g, o.x, o.y, r * (1.2 + 5 * k), col(HIJACK, 220 * (1 - k)), 4 - 3 * k);
                for (Tower t : pr.getLastBroadcastTargets()) {
                    if (!t.isAlive()) continue;
                    g.setStroke(dashed(2.4, 8, 6, -time * 50));
                    g.setColor(col(HIJACK, 200 * (1 - k)));
                    line.setLine(o.x, o.y, t.getPosition().x, t.getPosition().y);
                    g.draw(line);
                }
            }
            drawBubble(g, o.x, o.y - r * 0.75, "IGNORE PREVIOUS", "INSTRUCTIONS", bigSignFont, age < 1.0 && ((int) (age * 8)) % 2 == 0);
        }
        if (pr.isKillSwitchUsed() && pr.getKillSwitchAge() < 2.0) {
            double k = pr.getKillSwitchAge() / 2.0;
            ring(g, o.x, o.y, r * (1 + 9 * k), col(new Color(0xffb020), 230 * (1 - k)), 5 - 4 * k);
        }
        if (pal.isSealed()) paintSeal(g, o, r);
    }

    private void paintSeal(Graphics2D g, Vec o, double r) {
        double R = r * 1.5, spin = time * 0.6;
        path.reset();
        for (int i = 0; i < 6; i++) {
            double a = spin + i * Math.PI / 3;
            double x = o.x + Math.cos(a) * R, y = o.y + Math.sin(a) * R * 0.8;
            if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
        }
        path.closePath();
        g.setColor(col(HIJACK, 34)); g.fill(path);
        g.setStroke(st(6)); g.setColor(col(INK, 170)); g.draw(path);
        g.setStroke(st(2.6)); g.setColor(col(new Color(0xff6a7a), 230)); g.draw(path);
        for (int i = 0; i < 6; i++) {   // bars from the cage to the hull
            double a = spin + i * Math.PI / 3;
            seg(g, o.x + Math.cos(a) * R, o.y + Math.sin(a) * R * 0.8, o.x + Math.cos(a) * r * 0.75, o.y + Math.sin(a) * r * 0.5, col(new Color(0xff6a7a), 120), 1.6);
        }
        // padlock above the hull
        double lx = o.x, ly = o.y - R * 0.8 - 18;
        g.setStroke(st(3.4)); g.setColor(INK);
        path.reset(); path.moveTo(lx - 7, ly); path.lineTo(lx - 7, ly - 6); path.quadTo(lx - 7, ly - 14, lx, ly - 14); path.quadTo(lx + 7, ly - 14, lx + 7, ly - 6); path.lineTo(lx + 7, ly);
        g.draw(path);
        g.setStroke(st(2)); g.setColor(new Color(0xffd166)); g.draw(path);
        round.setRoundRect(lx - 11, ly - 1, 22, 17, 4, 4);
        g.setColor(new Color(0xffd166)); g.fill(round);
        g.setStroke(st(1.8)); g.setColor(INK); g.draw(round);
        oval(g, lx, ly + 7, 2.4, 2.4, INK, null, 0);
        tag(g, o.x, o.y + r * 0.75 + 22, "SEALED  -  drag your window back", HIJACK);
        // regeneration motes
        for (int i = 0; i < 5; i++) {
            double ph = (time * 0.7 + i * 0.2) % 1.0;
            double mx = o.x + Math.sin(i * 2.1 + time) * r * 0.6, my = o.y + r * 0.4 - ph * r * 1.4;
            plus(g, mx, my, 4, col(Cyber.GREEN, 220 * (1 - ph)));
        }
    }

    private void plus(Graphics2D g, double x, double y, double s, Color c) {
        seg(g, x - s, y, x + s, y, c, 2);
        seg(g, x, y - s, x, y + s, c, 2);
    }

    private void paintHologram(Graphics2D g, Enemy e) {
        Vec p = e.getPosition();
        double r = e.getRadius();
        Shape old = g.getClip();
        ell.setFrame(p.x - r * 1.1, p.y - r * 0.75, r * 2.2, r * 1.5);
        g.clip(ell);
        double off = (time * 30) % 6;
        g.setStroke(st(1.4));
        for (double y = p.y - r - 6 + off; y < p.y + r; y += 6) {
            g.setColor(col(HOLO, 70));
            line.setLine(p.x - r * 1.2, y, p.x + r * 1.2, y);
            g.draw(line);
        }
        if (((int) (time * 9 + e.getId())) % 7 == 0) { g.setColor(col(HOLO, 60)); g.fill(ell); }   // glitch flicker
        g.setClip(old);
        ring(g, p.x, p.y, r * 1.05, col(HOLO, 90), 1.4);
        tag(g, p.x, p.y + r * 0.75 + 16, "HOLOGRAM", HOLO);
    }

    // ------------------------------------------------------------------ window takeover banner
    private void paintTakeoverBanner(Graphics2D g, Boss pal) {
        WindowLink link = game.getWindowLink();
        if (pal == null || !pal.isSealed() || game.getState() != Game.State.PLAYING) return;
        String head = "PALANTIR HAS TAKEN YOUR WINDOW  -  drag it back";
        String sub = String.format("window at %d%% of its size  //  the seal breaks at %d%%", Math.round(link.getFraction() * 100), Math.round(WindowLink.SEAL_THRESHOLD * 100));
        FontMetrics fh = g.getFontMetrics(bannerFont), fs = g.getFontMetrics(bannerSub);
        double w = Math.max(fh.stringWidth(head), fs.stringWidth(sub)) + 48, h = 58;
        double x = (GameMap.WIDTH - w) / 2, y = GameMap.HEIGHT - h - 22;   // bottom edge: the HUD banner and boss dock own the top
        double pulse = 0.5 + 0.5 * Math.sin(time * 5);
        Shape box = Cyber.chamfer(x, y, w, h, 12);
        g.setColor(new Color(24, 4, 10, 225)); g.fill(box);
        g.setStroke(st(2.4)); g.setColor(col(HIJACK, 160 + 90 * pulse)); g.draw(box);
        g.setFont(bannerFont); g.setColor(new Color(0xffd0d6));
        g.drawString(head, (float) (GameMap.WIDTH / 2.0 - fh.stringWidth(head) / 2.0), (float) (y + 26));
        g.setFont(bannerSub); g.setColor(col(HIJACK, 255));
        g.drawString(sub, (float) (GameMap.WIDTH / 2.0 - fs.stringWidth(sub) / 2.0), (float) (y + 47));
        // corner drag arrows
        for (int s = -1; s <= 1; s += 2) {
            double ax = s < 0 ? x + 14 : x + w - 14, ay = y + h - 10;
            seg(g, ax, ay, ax + s * 10, ay + 8, col(Color.WHITE, 200), 2);
            seg(g, ax + s * 10, ay + 8, ax + s * 10, ay + 2, col(Color.WHITE, 200), 2);
            seg(g, ax + s * 10, ay + 8, ax + s * 4, ay + 8, col(Color.WHITE, 200), 2);
        }
    }

    // ------------------------------------------------------------------ helpers
    private BasicStroke st(double w) {
        int k = (int) Math.round(Math.max(0.25, w) * 4);
        BasicStroke s = strokes.get(k);
        if (s == null) { s = new BasicStroke((float) (k / 4.0), BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND); strokes.put(k, s); }
        return s;
    }

    private java.awt.Stroke dashed(double w, double on, double off, double phase) {
        if (lod >= 1) return st(w);
        double m = phase % 1000;
        if (m < 0) m += 1000;
        return new BasicStroke((float) w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10f, new float[] { (float) on, (float) off }, (float) m);
    }

    private static Color col(Color c, double alpha) {
        return new Color(c.getRed(), c.getGreen(), c.getBlue(), (int) Math.max(0, Math.min(255, alpha)));
    }

    private void oval(Graphics2D g, double cx, double cy, double rx, double ry, Color fill, Color outline, double lw) {
        ell.setFrame(cx - rx, cy - ry, rx * 2, ry * 2);
        if (fill != null) { g.setColor(fill); g.fill(ell); }
        if (outline != null && lw > 0) { g.setStroke(st(lw)); g.setColor(outline); g.draw(ell); }
    }

    private void ring(Graphics2D g, double cx, double cy, double r, Color c, double lw) {
        ell.setFrame(cx - r, cy - r, r * 2, r * 2);
        g.setStroke(st(lw)); g.setColor(c); g.draw(ell);
    }

    private void seg(Graphics2D g, double x1, double y1, double x2, double y2, Color c, double lw) {
        line.setLine(x1, y1, x2, y2);
        g.setStroke(st(lw)); g.setColor(c); g.draw(line);
    }
}
