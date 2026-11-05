package lindefense.test;

import static lindefense.test.TestKit.*;

import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.util.prefs.Preferences;
import lindefense.map.MapCatalog;
import lindefense.ui.GraphicsSettings;
import lindefense.ui.GraphicsSettings.Quality;
import lindefense.ui.MapArt;

/**
 * Graphics settings: the quality presets' resolution rules (map backgrounds and icons follow the screen's real pixel
 * density up to the preset's cap), frame-rate choices, persistence without touching the player's preferences, and the
 * map-background cache staying inside its pixel budget even at 5K / 6K densities.
 */
public final class GraphicsTests {
    private GraphicsTests() { }

    public static void runAll() {
        run("graphics.presets", GraphicsTests::presets);
        run("graphics.settings", GraphicsTests::settings);
        run("graphics.mapCacheBudget", GraphicsTests::mapCacheBudget);
    }

    private static void presets() {
        check(Quality.HIGH.mapScale(1.0) == 1.0 && Quality.MEDIUM.mapScale(1.0) == 1.0, "a 1:1 map bitmap at every preset");
        check(Quality.HIGH.mapScale(3.2) == 3.25, "HIGH follows a 5K density (3.2 -> 3.25), got " + Quality.HIGH.mapScale(3.2));
        check(Quality.MEDIUM.mapScale(3.2) == 2.5 && Quality.LOW.mapScale(3.2) == 1.5, "MEDIUM / LOW cap the map bitmap at 2.5x / 1.5x");
        check(Quality.HIGH.mapScale(9) == 4.0, "HIGH caps at 4x");
        check(Quality.HIGH.mapScale(0.01) == 0.125, "tiny thumbnails never drop below 1/8 scale");
        check(Quality.HIGH.mapScale(2.0) == 2.0 && Quality.HIGH.mapScale(2.01) == 2.125, "map scale rounds up to 1/8 steps");
        check(Quality.HIGH.iconScale(1.0) == 2 && Quality.HIGH.iconScale(3.1) == 4 && Quality.MEDIUM.iconScale(3.1) == 3 && Quality.LOW.iconScale(3.1) == 2,
            "icons supersample at the device density (min 2x, capped per preset)");
        check(Quality.HIGH.interpolation() == RenderingHints.VALUE_INTERPOLATION_BILINEAR
            && Quality.LOW.interpolation() == RenderingHints.VALUE_INTERPOLATION_BILINEAR, "bilinear scaling everywhere (bitmaps are drawn at about 1:1)");
        check(Quality.LOW.minLod >= 1 && Quality.MEDIUM.minLod == 0 && Quality.HIGH.minLod == 0, "LOW always trims detail; MEDIUM / HIGH use automatic detail");
        check(Quality.HIGH.vignette && Quality.HIGH.screenShake && Quality.HIGH.glow && !Quality.MEDIUM.glow && !Quality.LOW.screenShake,
            "the cosmetic extras are HIGH only");
        check(Quality.LOW.next() == Quality.MEDIUM && Quality.HIGH.next() == Quality.LOW, "presets cycle LOW -> MEDIUM -> HIGH -> LOW");
        check(Quality.parse("high") == Quality.HIGH && Quality.parse(" Low ") == Quality.LOW && Quality.parse("ultra") == null, "preset names parse");
    }

    private static void settings() {
        GraphicsSettings mem = GraphicsSettings.inMemory();
        check(mem.quality() == Quality.HIGH && mem.getMaxFps() == 60, "defaults: HIGH quality, 60 fps");
        check(mem.frameDelayMs() == 16, "60 fps = a 16 ms frame timer");
        mem.setMaxFps(100);
        check(mem.getMaxFps() == 120 && mem.frameDelayMs() == 8, "a requested rate snaps to the nearest choice (100 -> 120)");
        check(mem.nextFps() == 30, "frame-rate choices cycle 30 -> 60 -> 120 -> 30");
        mem.setQuality(null);
        check(mem.quality() == Quality.HIGH, "a null preset is ignored");

        // persistence round trip in a throwaway node, never the player's lindefense/graphics node
        String path = "lindefense-test/graphics-" + System.nanoTime();
        try {
            Preferences node = Preferences.userRoot().node(path);
            GraphicsSettings a = new GraphicsSettings(node);
            a.setQuality(Quality.LOW);
            a.setMaxFps(120);
            GraphicsSettings b = new GraphicsSettings(node);
            check(b.quality() == Quality.LOW && b.getMaxFps() == 120, "quality and frame rate persist");
            node.removeNode();
        } catch (Exception e) {
            check(false, "graphics prefs round trip failed: " + e);
        }
    }

    private static void mapCacheBudget() {
        GraphicsSettings saved = GraphicsSettings.get();
        GraphicsSettings.setInstance(GraphicsSettings.inMemory());   // HIGH
        try {
            // paint four different maps at a 5K-class density into a tiny target: each bitmap is ~15 M px
            BufferedImage target = new BufferedImage(8, 8, BufferedImage.TYPE_INT_RGB);
            for (int m = 0; m < 4; m++) {
                Graphics2D g = target.createGraphics();
                g.scale(3.4, 3.4);
                new MapArt(MapCatalog.create(m)).paint(g);
                g.dispose();
                check(MapArt.cachedPixels() <= MapArt.CACHE_PIXEL_BUDGET, "map bitmap cache within its pixel budget after map " + m
                    + " (" + MapArt.cachedPixels() + " px)");
            }
        } finally {
            GraphicsSettings.setInstance(saved);
        }
    }
}
