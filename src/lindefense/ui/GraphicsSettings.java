package lindefense.ui;

import java.awt.RenderingHints;
import java.util.prefs.Preferences;

/**
 * The persisted graphics settings: a {@link Quality} preset and a frame-rate cap ({@link #getMaxFps()}), saved with
 * {@link Preferences} in the node {@value #PREFS_NODE}. Persistence failures are ignored (the settings still work in
 * memory). Tests, tools and the scripted demo use an in-memory instance ({@link #inMemory()}), so they never read or
 * write the player's preferences; {@code -Dlindefense.quality=LOW|MEDIUM|HIGH} and {@code -Dlindefense.fps=30|60|120}
 * override the saved values for one run.
 *
 * <p>Everything the renderer needs to know about quality is a field of the preset, so the drawing code asks
 * {@code GraphicsSettings.get().quality()} instead of comparing preset names.</p>
 */
public final class GraphicsSettings {
    /** Preference node of the graphics settings. */
    public static final String PREFS_NODE = "lindefense/graphics";
    static final String KEY_QUALITY = "quality";
    static final String KEY_FPS = "maxFps";
    /** Frame-rate caps offered in SETTINGS (the timer delay is {@code 1000 / fps} ms). */
    public static final int[] FPS_CHOICES = { 30, 60, 120 };
    /** Frame-rate cap when nothing is saved (the rate the game was tuned at). */
    public static final int DEFAULT_FPS = 60;

    /**
     * A graphics preset. Bitmap caches (map backgrounds, icons) are rendered at the screen's real pixel density up to
     * the preset's cap; the level of detail of big fights never drops below {@link #minLod}; the cosmetic extras
     * (vignette and scanlines, screen shake, projectile glow) are only drawn when the preset enables them.
     */
    public enum Quality {
        /** Fastest: bitmaps at most 1.5x, always at least the first detail reduction, no extras. */
        LOW("Low", 1.5, 2, 1, false, false, false),
        /** The look the game shipped with: crisp bitmaps on most screens, automatic detail, no extras. */
        MEDIUM("Medium", 2.5, 3, 0, false, false, false),
        /** Sharpest: bitmaps up to 4x (5K / 6K screens), vignette, screen shake and glow. */
        HIGH("High", 4.0, 4, 0, true, true, true);

        /** Label shown in SETTINGS. */
        public final String label;
        /** Highest pixel scale (relative to the 1200 x 900 world) a map background bitmap is rendered at. */
        public final double mapMaxScale;
        /** Highest supersampling factor (relative to logical size) of cached tower icons. */
        public final int iconMaxScale;
        /** Lowest level of detail used in big fights (0 = full detail; see {@code WorldView}). */
        public final int minLod;
        /** Draw the cyberpunk vignette + scanline overlay over the battlefield. */
        public final boolean vignette;
        /** Shake the battlefield on boss hits, big explosions and lost lives. */
        public final boolean screenShake;
        /** Soft glow halos on projectiles and explosions. */
        public final boolean glow;

        Quality(String label, double mapMaxScale, int iconMaxScale, int minLod, boolean vignette, boolean screenShake, boolean glow) {
            this.label = label; this.mapMaxScale = mapMaxScale; this.iconMaxScale = iconMaxScale; this.minLod = minLod;
            this.vignette = vignette; this.screenShake = screenShake; this.glow = glow;
        }

        /**
         * Pixel scale of a map-background bitmap that must cover {@code devicePxPerWorldPx} device pixels per world
         * pixel: the screen's real density (Retina / HiDPI and window size included), rounded up to 1/8 steps so window
         * resizes reuse bitmaps, at least 1/8 and at most {@link #mapMaxScale}.
         */
        public double mapScale(double devicePxPerWorldPx) {
            return Math.min(mapMaxScale, Math.max(0.125, Math.ceil(devicePxPerWorldPx * 8 - 1e-9) / 8.0));
        }

        /** Supersampling factor of a cached icon drawn at device scale {@code dev}: a whole factor from 2 to {@link #iconMaxScale}. */
        public int iconScale(double dev) {
            return Math.max(2, Math.min(iconMaxScale, (int) Math.ceil(dev - 1e-6)));
        }

        /**
         * Image interpolation for scaled bitmaps: bilinear at every preset. Bitmaps are rendered at the screen's density
         * and drawn at about 1:1, where bicubic looks the same but runs Java2D's slow general-transform loop (measured:
         * +24 ms per frame for the map background alone).
         */
        public Object interpolation() { return RenderingHints.VALUE_INTERPOLATION_BILINEAR; }

        /** The next preset in SETTINGS order, wrapping around (LOW -> MEDIUM -> HIGH -> LOW). */
        public Quality next() { return values()[(ordinal() + 1) % values().length]; }

        /** Parses a preset name (case-insensitive); null if it is not one. */
        public static Quality parse(String s) {
            if (s == null) return null;
            for (Quality q : values()) if (q.name().equalsIgnoreCase(s.trim())) return q;
            return null;
        }
    }

    private static GraphicsSettings instance;

    private final Preferences node;
    private Quality quality;
    private int maxFps;

    /** Reads the settings from {@code node} (null = in memory only, all defaults); system properties win. */
    public GraphicsSettings(Preferences node) {
        this.node = node;
        Quality q = Quality.HIGH;
        int fps = DEFAULT_FPS;
        try {
            if (node != null) {
                Quality saved = Quality.parse(node.get(KEY_QUALITY, null));
                if (saved != null) q = saved;
                fps = node.getInt(KEY_FPS, DEFAULT_FPS);
            }
        } catch (RuntimeException ignored) {
            // unreadable preference store: use defaults
        }
        Quality forced = Quality.parse(System.getProperty("lindefense.quality"));
        if (forced != null) q = forced;
        try {
            String f = System.getProperty("lindefense.fps");
            if (f != null) fps = Integer.parseInt(f.trim());
        } catch (NumberFormatException ignored) {
            // keep the saved value
        }
        quality = q;
        maxFps = clampFps(fps);
    }

    /** A settings object that never touches the preference store (tests, tools, the scripted demo). */
    public static GraphicsSettings inMemory() { return new GraphicsSettings(null); }

    /**
     * The settings the game uses. Created on first use: in memory for headless runs and the scripted demo, otherwise
     * backed by the player's preferences.
     */
    public static synchronized GraphicsSettings get() {
        if (instance == null) {
            boolean transientRun = java.awt.GraphicsEnvironment.isHeadless() || System.getProperty("lindefense.demo") != null;
            Preferences p = null;
            if (!transientRun) {
                try { p = Preferences.userRoot().node(PREFS_NODE); } catch (RuntimeException ignored) { p = null; }
            }
            instance = new GraphicsSettings(p);
        }
        return instance;
    }

    /** Replaces the shared instance (tests). */
    public static synchronized void setInstance(GraphicsSettings s) { instance = s; }

    public Quality quality() { return quality; }
    public int getMaxFps() { return maxFps; }
    /** Swing timer delay for the frame-rate cap. */
    public int frameDelayMs() { return Math.max(1, (int) Math.floor(1000.0 / maxFps)); }

    public void setQuality(Quality q) {
        if (q == null) return;
        quality = q;
        save(KEY_QUALITY, q.name());
    }

    /** Sets the frame-rate cap (snapped to the nearest of {@link #FPS_CHOICES}). */
    public void setMaxFps(int fps) {
        maxFps = clampFps(fps);
        if (node != null) {
            try { node.putInt(KEY_FPS, maxFps); } catch (RuntimeException ignored) { /* keep it in memory */ }
        }
    }

    /** The next frame-rate choice in SETTINGS order, wrapping around. */
    public int nextFps() {
        for (int i = 0; i < FPS_CHOICES.length; i++) if (FPS_CHOICES[i] == maxFps) return FPS_CHOICES[(i + 1) % FPS_CHOICES.length];
        return DEFAULT_FPS;
    }

    /** Snaps any requested rate to the nearest offered choice. */
    static int clampFps(int fps) {
        int best = FPS_CHOICES[0];
        for (int c : FPS_CHOICES) if (Math.abs(c - fps) < Math.abs(best - fps)) best = c;
        return best;
    }

    private void save(String key, String value) {
        if (node == null) return;
        try { node.put(key, value); } catch (RuntimeException ignored) { /* keep it in memory */ }
    }
}
