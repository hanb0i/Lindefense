package lindefense.ui;

import acm.graphics.GLabel;
import acm.graphics.GOval;
import acm.graphics.GRect;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;

/** Shared UI constants and small helpers (fonts, colours, text wrapping). */
public final class Ui {
    private Ui() { }

    /** Logical canvas size; everything is laid out in these units and scaled to fit. */
    public static final int W = 1600;
    public static final int H = 1000;
    public static final int TOP_H = 48;
    public static final int WORLD_X = 0;
    public static final int WORLD_Y = 48;
    public static final int WORLD_W = 1200;
    public static final int WORLD_H = 900;
    public static final int BOTTOM_Y = 948;
    public static final int PANEL_X = 1200;
    public static final int PANEL_W = 400;

    public static final Font F_TITLE = Cyber.display(Font.BOLD, 64);
    public static final Font F_H1 = Cyber.display(Font.BOLD, 28);
    public static final Font F_H2 = Cyber.display(Font.BOLD, 20);
    public static final Font F_BODY = Cyber.body(Font.PLAIN, 14);
    public static final Font F_BOLD = Cyber.body(Font.BOLD, 14);
    public static final Font F_SMALL = Cyber.body(Font.PLAIN, 12);
    public static final Font F_TINY = Cyber.mono(Font.BOLD, 10);

    public static final Color BG = Cyber.INK;
    public static final Color PANEL = new Color(0x080d1e);
    public static final Color PANEL_LIGHT = new Color(0x122038);
    public static final Color TEXT = Cyber.TEXT;
    public static final Color MUTED = Cyber.MUTED;
    public static final Color ACCENT = Cyber.CYAN;
    public static final Color GOLD = Cyber.YELLOW;
    public static final Color GREEN = Cyber.GREEN;
    public static final Color RED = Cyber.RED;

    /** All UI fonts come from these three helpers (bundled OFL fonts, logical-font fallback). */
    public static Font display(int style, int size) { return Cyber.display(style, size); }
    public static Font mono(int style, int size) { return Cyber.mono(style, size); }
    public static Font body(int style, int size) { return Cyber.body(style, size); }

    public static Color c(int rgb) { return new Color(rgb); }
    public static Color c(int rgb, int alpha) { return new Color((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, alpha); }
    public static Color withAlpha(Color col, int alpha) { return new Color(col.getRed(), col.getGreen(), col.getBlue(), alpha); }

    public static GLabel label(String text, double x, double y, Font f, Color col) {
        GLabel l = new Cyber.Text(text, x, y);
        l.setFont(f);
        l.setColor(col);
        return l;
    }

    public static GRect rect(double x, double y, double w, double h, Color fill, Color outline) {
        GRect r = new GRect(x, y, w, h);
        if (fill != null) { r.setFilled(true); r.setFillColor(fill); }
        r.setColor(outline != null ? outline : (fill != null ? fill : TEXT));
        return r;
    }

    public static GOval oval(double x, double y, double w, double h, Color fill, Color outline) {
        GOval o = new GOval(x, y, w, h);
        if (fill != null) { o.setFilled(true); o.setFillColor(fill); }
        o.setColor(outline != null ? outline : (fill != null ? fill : TEXT));
        return o;
    }

    /** Greedy word wrap using GLabel measurement. */
    public static List<String> wrap(String text, Font f, double maxWidth) {
        List<String> lines = new ArrayList<>();
        if (text == null) return lines;
        GLabel probe = new Cyber.Text("");
        probe.setFont(f);
        StringBuilder cur = new StringBuilder();
        for (String word : text.split(" ")) {
            String trial = cur.length() == 0 ? word : cur + " " + word;
            probe.setLabel(trial);
            if (probe.getWidth() > maxWidth && cur.length() > 0) {
                lines.add(cur.toString());
                cur = new StringBuilder(word);
            } else {
                cur = new StringBuilder(trial);
            }
        }
        if (cur.length() > 0) lines.add(cur.toString());
        return lines;
    }

    public static String money(double v) { return Cyber.money(v); }

    public static String fmt(double v) {
        if (Math.abs(v - Math.rint(v)) < 1e-9) return String.valueOf((long) Math.rint(v));
        // up to two decimals, trailing zeros trimmed (0.85 s and 0.25 s intervals must not round to 0.9 / 0.3)
        String s = String.format(java.util.Locale.ROOT, "%.2f", v);
        while (s.endsWith("0")) s = s.substring(0, s.length() - 1);
        return s.endsWith(".") ? s.substring(0, s.length() - 1) : s;
    }

    /**
     * Unit count of a wave after the difficulty has shaped it ({@code game.getDifficulty().shape(...)}, exactly what the
     * wave manager spawns), not the base O(1) count. Used by the bottom strip's next-wave preview.
     */
    public static int shapedUnits(lindefense.sim.Game game, int wave) {
        return game.getVariance().shapeWave(game.getDifficulty().shape(lindefense.wave.WaveData.get(wave), game.getSeed())).totalSpawns();   // + PATCH NOTES / NEWS
    }
}
