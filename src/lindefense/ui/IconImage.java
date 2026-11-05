package lindefense.ui;

import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.util.HashMap;
import java.util.Map;
import lindefense.tower.TowerType;
import lindefense.ui.sprites.towers.TowerIcons;

/**
 * A tower icon pre-rendered into a bitmap and cached per (type, game tier, size, pixel scale), centred on its location.
 * The live art is a compound of dozens of shapes; dozens of ability-bar slots painting those every frame cost
 * milliseconds, a cached bitmap costs almost nothing.
 *
 * <p>The bitmap is rendered at the density it is actually drawn at: the logical size times the canvas scale (window
 * size and Retina / HiDPI included), rounded up to a whole factor and capped by the graphics preset
 * ({@link GraphicsSettings.Quality#iconMaxScale}). It is drawn through an affine transform at fractional positions, so
 * icons stay sharp on large high-density windows and do not shimmer when the window is resized.</p>
 */
final class IconImage extends GObject {
    private static final long serialVersionUID = 1L;
    private static final Map<String, BufferedImage> CACHE = new HashMap<>();
    private final TowerType type;
    private final int tier;
    private final double size;
    private transient BufferedImage img;
    private int imgScale;

    IconImage(TowerType type, int tier, double size) {
        this.type = type; this.tier = tier; this.size = size;
    }

    private static synchronized BufferedImage bitmap(TowerType type, int tier, double size, int ss) {
        String key = type + ":" + tier + ":" + size + ":" + ss;
        BufferedImage b = CACHE.get(key);
        if (b == null) {
            int px = (int) Math.ceil(size * ss);
            b = new BufferedImage(px, px, BufferedImage.TYPE_INT_ARGB);
            Graphics2D g = b.createGraphics();
            try {
                Cyber.quality(g);
                g.translate(px / 2.0, px / 2.0);
                g.scale(ss, ss);
                TowerIcons.create(type, tier, size).paint(g);
            } finally {
                g.dispose();
            }
            CACHE.put(key, b);
        }
        return b;
    }

    @Override public GRectangle getBounds() { return new GRectangle(getX() - size / 2, getY() - size / 2, size, size); }

    @Override public void paint(Graphics g) {
        Graphics2D g2 = (Graphics2D) g.create();
        try {
            GraphicsSettings.Quality q = GraphicsSettings.get().quality();
            int ss = q.iconScale(Math.sqrt(Math.abs(g2.getTransform().getDeterminant())));
            if (img == null || ss != imgScale) { img = bitmap(type, tier, size, ss); imgScale = ss; }
            g2.setRenderingHint(RenderingHints.KEY_INTERPOLATION, q.interpolation());
            AffineTransform at = new AffineTransform();
            at.translate(getX() - size / 2, getY() - size / 2);
            at.scale(size / img.getWidth(), size / img.getHeight());
            g2.drawImage(img, at, null);
        } finally {
            g2.dispose();
        }
    }
}
