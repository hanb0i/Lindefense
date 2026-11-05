package lindefense.ui;

import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RadialGradientPaint;
import java.awt.geom.Rectangle2D;

/**
 * HIGH-quality cosmetic (see {@link GraphicsSettings.Quality#vignette}): darkened corners and faint CRT scanlines for
 * the cyberpunk monitor look. It is painted ONCE into the cached map-background bitmap ({@link MapArt}), not over every
 * frame: blending a full-screen translucent layer each frame cost about 14 ms in the render benchmark, baking it into
 * the static backdrop costs nothing per frame. Units and effects are drawn on top of it.
 */
final class VignetteOverlay {
    /** Spacing of the scanlines in world px. */
    static final int SCANLINE_STEP = 4;

    private VignetteOverlay() { }

    /** Paints the vignette and scanlines over a {@code w x h} area in the current (world) coordinates. */
    static void paint(Graphics2D g, double w, double h) {
        float cx = (float) (w / 2), cy = (float) (h / 2);
        g.setPaint(new RadialGradientPaint(cx, cy, (float) Math.hypot(cx, cy), new float[] { 0f, 0.62f, 1f },
            new Color[] { new Color(0, 0, 0, 0), new Color(2, 4, 12, 30), new Color(2, 4, 12, 150) }));
        g.fill(new Rectangle2D.Double(0, 0, w, h));
        g.setColor(new Color(0, 0, 0, 18));
        for (int y = 0; y < h; y += SCANLINE_STEP) g.fill(new Rectangle2D.Double(0, y, w, 1));
    }
}
