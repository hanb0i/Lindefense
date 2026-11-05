package lindefense.ui;

import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.AlphaComposite;
import java.awt.Color;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RadialGradientPaint;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lindefense.combat.Projectile;
import lindefense.map.GameMap;
import lindefense.sim.Game;
import lindefense.sim.Vec;

/**
 * HIGH-quality cosmetic layer (see {@link GraphicsSettings.Quality#glow}): soft light halos under live projectiles and
 * short light flashes on explosions and big abilities. Drawn in world coordinates by {@link WorldView}, under the
 * projectile sprites.
 *
 * <p>It stays cheap by stamping one small pre-rendered radial-gradient sprite per colour (cached) instead of painting
 * gradients every frame, by capping the number of halos, and by switching off as soon as big fights lower the level of
 * detail.</p>
 */
final class GlowLayer extends GObject {
    private static final long serialVersionUID = 1L;
    /** Side of the cached glow sprite in pixels (it is scaled to each halo's size). */
    private static final int SPRITE = 64;
    /** Most projectile halos drawn per frame. */
    static final int MAX_HALOS = 96;
    /** Halo radius around a projectile, world px. */
    private static final double HALO_RADIUS = 15;
    private static final Map<Integer, BufferedImage> SPRITES = new HashMap<>();

    /** One explosion / ability flash. */
    private static final class Flash {
        final double x, y, radius, life;
        final int rgb;
        double age;
        Flash(double x, double y, double radius, double life, int rgb) { this.x = x; this.y = y; this.radius = radius; this.life = life; this.rgb = rgb; }
    }

    private final Game game;
    private final List<Flash> flashes = new ArrayList<>();
    private final AffineTransform at = new AffineTransform();
    private int lod;

    GlowLayer(Game game) { this.game = game; }

    /** Level of detail from the world view: halos only at full detail, flashes up to level 1. */
    void setLod(int lod) { this.lod = lod; }

    /** Adds a light flash of the given world radius and colour (explosions, abilities). */
    void flash(Vec at, double radius, int rgb) {
        if (at == null || !GraphicsSettings.get().quality().glow || lod >= 2 || flashes.size() >= 40) return;
        flashes.add(new Flash(at.x, at.y, Math.min(260, Math.max(24, radius * 1.4)), 0.28, rgb));
    }

    /** Ages the flashes. */
    void update(double dt) {
        for (int i = flashes.size() - 1; i >= 0; i--) {
            Flash f = flashes.get(i);
            f.age += dt;
            if (f.age >= f.life) flashes.remove(i);
        }
    }

    /** Live flashes (tests). */
    int flashCount() { return flashes.size(); }

    @Override public GRectangle getBounds() { return new GRectangle(0, 0, GameMap.WIDTH, GameMap.HEIGHT); }

    @Override public void paint(Graphics g) {
        if (!GraphicsSettings.get().quality().glow) return;
        Graphics2D g2 = (Graphics2D) g.create();
        try {
            if (lod == 0) {
                List<Projectile> live = game.getCombat().getProjectiles();
                int drawn = 0;
                for (int i = 0, n = live.size(); i < n && drawn < MAX_HALOS; i++) {
                    Projectile p = live.get(i);
                    if (!p.isAlive()) continue;
                    Vec q = p.getPosition();
                    stamp(g2, q.x, q.y, HALO_RADIUS, p.getShot().rgb, 0.55f);
                    drawn++;
                }
            }
            for (Flash f : flashes) {
                float k = (float) (1 - f.age / f.life);
                stamp(g2, f.x, f.y, f.radius * (0.7 + 0.3 * (1 - k)), f.rgb, 0.65f * k);
            }
        } finally {
            g2.dispose();
        }
    }

    private void stamp(Graphics2D g2, double x, double y, double r, int rgb, float alpha) {
        if (alpha <= 0.01f) return;
        g2.setComposite(AlphaComposite.SrcOver.derive(Math.min(1f, alpha)));
        at.setToTranslation(x - r, y - r);
        at.scale(2 * r / SPRITE, 2 * r / SPRITE);
        g2.drawImage(sprite(rgb), at, null);
    }

    /** The cached radial glow sprite for a colour: bright core fading to transparent. */
    static synchronized BufferedImage sprite(int rgb) {
        Integer key = rgb & 0xffffff;
        BufferedImage b = SPRITES.get(key);
        if (b != null) return b;
        b = new BufferedImage(SPRITE, SPRITE, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = b.createGraphics();
        try {
            Color c = new Color(key);
            Color core = new Color(Math.min(255, c.getRed() + 70), Math.min(255, c.getGreen() + 70), Math.min(255, c.getBlue() + 70), 200);
            g.setPaint(new RadialGradientPaint(SPRITE / 2f, SPRITE / 2f, SPRITE / 2f, new float[] { 0f, 0.35f, 1f },
                new Color[] { core, new Color(c.getRed(), c.getGreen(), c.getBlue(), 90), new Color(c.getRed(), c.getGreen(), c.getBlue(), 0) }));
            g.fillRect(0, 0, SPRITE, SPRITE);
        } finally {
            g.dispose();
        }
        SPRITES.put(key, b);
        return b;
    }
}
