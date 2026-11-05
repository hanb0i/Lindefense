package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GObject;
import acm.graphics.GRectangle;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.util.ArrayList;
import java.util.List;
import lindefense.sim.Game;
import lindefense.variance.BreakingNews;
import lindefense.variance.PatchNote;
import lindefense.variance.RunVariance;

/**
 * Slim strip under the top HUD bar, shown only while run variance is on: the run's patch version and one chip per
 * active patch note on the left (hover for the full card), the "Breaking News" ticker on the right (hover for details),
 * or the run seed when the feed is quiet. A new headline also flashes the HUD banner once the draft overlay is gone.
 * The playfield shrinks by {@link #height()} (like the boss dock) so the strip never covers the map.
 */
final class RunStrip extends GCompound {
    private static final long serialVersionUID = 1L;
    /** Strip height while variance is on. */
    static final double H = 26;
    private static final Font CHIP_FONT = Cyber.mono(Font.BOLD, 10);
    private static final Font TICK_FONT = Cyber.mono(Font.BOLD, 12);
    private static final double TAG_W = 92, NEWS_TAG_W = 88, NEWS_MIN_X = 640;

    private final GameScreen screen;
    private final Game game;
    private final GCompound chips = new GCompound();
    private final GLabel versionLabel;
    private final Cyber.Chamfer newsTag;
    private final GLabel newsTagLabel, quietLabel;
    private final Ticker ticker = new Ticker();
    private final GCompound tip = new GCompound();
    private final List<double[]> chipBoxes = new ArrayList<>();
    private String chipsKey = "";
    private String tipKey = "";
    private BreakingNews shownNews;
    private int shownNewsWave;
    private double newsX = NEWS_MIN_X;
    private double announceWait = -1, flash, time;

    RunStrip(GameScreen screen) {
        this.screen = screen;
        this.game = screen.getGame();
        double y = Ui.WORLD_Y;
        add(Ui.rect(0, y, Ui.WORLD_W, H, new Color(4, 8, 20, 245), new Color(4, 8, 20, 245)));
        add(Ui.rect(0, y + H - 1, Ui.WORLD_W, 1, Cyber.alpha(Cyber.CYAN, 110), Cyber.alpha(Cyber.CYAN, 110)));
        add(Ui.rect(0, y + H - 1, 160, 1, Cyber.alpha(Cyber.MAGENTA, 170), Cyber.alpha(Cyber.MAGENTA, 170)));
        add(new Cyber.Chamfer(6, y + 4, TAG_W, 18, 5).scan(false).fill(Cyber.alpha(Cyber.CYAN, 28)).border(Cyber.alpha(Cyber.CYAN, 170)));
        versionLabel = Ui.label("", 0, y + 17, CHIP_FONT, Cyber.CYAN);
        add(versionLabel);
        add(chips);
        newsTag = new Cyber.Chamfer(0, y + 4, NEWS_TAG_W, 18, 5).scan(false).fill(Cyber.RED).border(Cyber.lerp(Cyber.RED, Color.WHITE, 0.4));
        newsTagLabel = Ui.label("BREAKING", 0, y + 17, CHIP_FONT, Color.WHITE);
        add(newsTag); add(newsTagLabel);
        add(ticker);
        quietLabel = Ui.label("", 0, y + 17, CHIP_FONT, Cyber.DIM);
        add(quietLabel);
        tip.setVisible(false);
        add(tip);
        setVisible(false);
    }

    /** Height the playfield gives up for the strip (0 while variance is off). */
    double height() { return game.getVariance().isEnabled() ? H : 0; }

    void update(double dt) {
        RunVariance v = game.getVariance();
        boolean on = v.isEnabled();
        if (isVisible() != on) setVisible(on);
        if (!on) return;
        time += dt;
        String key = v.getVersion() + v.getActive();
        if (!key.equals(chipsKey)) { chipsKey = key; rebuildChips(v); }
        updateNews(v, dt);
        updateTip(v);
    }

    // ------------------------------------------------------------------ chips
    private void rebuildChips(RunVariance v) {
        chips.removeAll();
        chipBoxes.clear();
        double y = Ui.WORLD_Y;
        Cyber.setText(versionLabel, "PATCH " + v.getVersion());
        versionLabel.setLocation(6 + (TAG_W - versionLabel.getWidth()) / 2, y + 17);
        double x = 6 + TAG_W + 8;
        if (v.getActive().isEmpty()) {
            chips.add(Ui.label("NO PATCH NOTES YET", x, y + 17, CHIP_FONT, Cyber.DIM));
            x += 130;
        }
        for (PatchNote p : v.getActive()) {
            double w = PatchNotesView.chip(chips, p, x, y + 4, 18, CHIP_FONT);
            chipBoxes.add(new double[] { x, w });
            x += w + 6;
        }
        newsX = Math.max(NEWS_MIN_X, x + 14);
    }

    // ------------------------------------------------------------------ news
    private void updateNews(RunVariance v, double dt) {
        BreakingNews n = v.getNews();
        int nw = v.getNewsWave();
        if (n != shownNews || (n != null && nw != shownNewsWave)) {
            shownNews = n;
            shownNewsWave = nw;
            if (n != null) { announceWait = 0; flash = 1.5; }
        }
        double y = Ui.WORLD_Y, right = Ui.WORLD_W - 6;
        boolean has = n != null;
        newsTag.setVisible(has); newsTagLabel.setVisible(has); ticker.setVisible(has);
        quietLabel.setVisible(!has);
        if (!has) {
            Cyber.setText(quietLabel, "NEWS FEED QUIET   //   " + PatchNotesView.seedText(game));
            quietLabel.setLocation(right - quietLabel.getWidth(), y + 17);
            announceWait = -1;
            return;
        }
        boolean live = game.getWaveManager().isWaveActive() && game.getWave() == nw;
        newsTag.setLocation(newsX, y + 4);
        newsTagLabel.setLocation(newsX + (NEWS_TAG_W - newsTagLabel.getWidth()) / 2, y + 17);
        flash = Math.max(0, flash - dt);
        double pulse = flash > 0 ? 0.5 + 0.5 * Math.sin(time * 18) : 0.5 + 0.5 * Math.sin(time * 3);
        newsTag.fill(Cyber.alpha(Cyber.RED, (int) (150 + 105 * pulse))).glow(flash > 0 ? 1 : 0.3 * pulse);
        ticker.set(newsX + NEWS_TAG_W + 8, y + 3, right - (newsX + NEWS_TAG_W + 8), H - 6,
            n.headline(nw) + "   //   " + n.flavor + "   //   " + (live ? "LIVE ON WAVE " + nw : "INCOMING: WAVE " + nw),
            flash > 0 ? Color.WHITE : Cyber.lerp(Cyber.RED, Color.WHITE, 0.55));
        ticker.scroll(dt);
        // announce on the HUD banner once nothing else needs the screen (draft closed, wave banner gone)
        if (announceWait >= 0 && !v.isDraftPending()) {
            announceWait += dt;
            if (game.getBanner() == null || announceWait > 3.0) {
                screen.flashBanner("BREAKING NEWS: " + n.title.toUpperCase(), Cyber.RED, 3.2);
                flash = 1.2;
                announceWait = -1;
            }
        }
    }

    // ------------------------------------------------------------------ hover cards
    private void updateTip(RunVariance v) {
        double[] m = screen.getMouseLogical();
        double y = Ui.WORLD_Y;
        int chip = -1;
        boolean news = false;
        double ax = 0;
        if (m[1] >= y && m[1] <= y + H) {
            for (int i = 0; i < chipBoxes.size(); i++) {
                double[] b = chipBoxes.get(i);
                if (m[0] >= b[0] && m[0] <= b[0] + b[1]) { chip = i; ax = b[0]; }
            }
            if (chip < 0 && v.getNews() != null && m[0] >= newsX) { news = true; ax = newsX; }
        }
        boolean live = game.getWaveManager().isWaveActive() && game.getWave() == v.getNewsWave();
        String key = chip >= 0 ? "C" + chip + "|" + chipsKey : news ? "N" + v.getNews() + "|" + v.getNewsWave() + "|" + live : "";
        if (key.equals(tipKey)) return;
        tipKey = key;
        tip.removeAll();
        if (key.isEmpty()) { tip.setVisible(false); return; }
        GCompound card = chip >= 0 ? PatchNotesView.noteCard(v.getActive().get(chip), v.getPickedBefore(chip))
            : PatchNotesView.newsCard(v.getNews(), v.getNewsWave(), live);
        double w = card.getWidth();
        card.setLocation(Math.max(6, Math.min(Ui.WORLD_W - w - 6, ax)), y + H + 6);
        tip.add(card);
        tip.setVisible(true);
    }

    /** One line of text that scrolls right to left inside a clipped window (static when it fits). */
    private static final class Ticker extends GObject {
        private static final long serialVersionUID = 1L;
        private static final String GAP = "      +      ";
        private static final java.awt.font.FontRenderContext FRC = new java.awt.font.FontRenderContext(null, true, true);
        private String text = "";
        private Color color = Color.WHITE;
        private double w, h, offset, textW, loopW;

        void set(double x, double y, double nw, double nh, String t, Color c) {
            setLocation(x, y);
            w = Math.max(0, nw); h = nh; color = c;
            if (!t.equals(text)) {
                text = t;
                offset = 0;
                textW = TICK_FONT.getStringBounds(text, FRC).getWidth();
                loopW = TICK_FONT.getStringBounds(text + GAP, FRC).getWidth();
            }
        }

        void scroll(double dt) { if (textW > w) offset = (offset + dt * 55) % Math.max(1, loopW); }

        @Override public GRectangle getBounds() { return new GRectangle(getX(), getY(), w, h); }

        @Override public void paint(Graphics g) {
            if (w <= 0 || text.isEmpty()) return;
            Graphics2D g2 = (Graphics2D) g.create();
            try {
                Cyber.quality(g2);
                g2.clip(new java.awt.geom.Rectangle2D.Double(getX(), getY(), w, h));
                g2.setFont(TICK_FONT);
                g2.setColor(color);
                float base = (float) (getY() + h / 2 + TICK_FONT.getSize() * 0.36);
                if (textW <= w) {
                    g2.drawString(text, (float) getX(), base);
                } else {
                    float x = (float) (getX() - offset);
                    g2.drawString(text + GAP, x, base);
                    g2.drawString(text + GAP, (float) (x + loopW), base);
                }
            } finally {
                g2.dispose();
            }
        }
    }
}
