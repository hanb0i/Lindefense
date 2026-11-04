package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import acm.graphics.GPolygon;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Vec;

/**
 * Map selection: a 4-column grid of cards (as many rows as
 * {@link MapCatalog#MAP_COUNT} needs) with a miniature track preview, name,
 * colour-coded difficulty badge, description and mechanic summary, styled to
 * match the cyberpunk title card. All geometry is in logical coordinates so
 * hit-testing stays correct at any window size.
 */
public final class MapSelectScreen extends GCompound {
    private static final long serialVersionUID = 1L;
    private static final int COLS = 4;

    private final List<NeonButton> buttons = new ArrayList<>();
    private final List<UIButton> chips = new ArrayList<>();
    private AudioToggle[] audioToggles;
    private final LogoEmblem mark;
    private double t;
    private final DifficultySelector difficulty;   // DIFFICULTY HOOK

    public MapSelectScreen(LindefenseProgram app) {
        add(Ui.rect(0, 0, Ui.W, Ui.H, MenuScreen.BG, MenuScreen.BG));
        for (int y = 0; y < Ui.H; y += 4) { GLine l = new GLine(0, y, Ui.W, y); l.setColor(Ui.withAlpha(Color.BLACK, 40)); add(l); }
        GLabel title = Ui.label("SELECT A MAP", 0, 0, MenuScreen.menuFont(Font.BOLD, 34), MenuScreen.CYAN);
        title.setLocation((Ui.W - title.getWidth()) / 2 + 30, 64);
        add(title);
        mark = new LogoEmblem(52);
        mark.setLocation((Ui.W - title.getWidth()) / 2 - 18, 52);
        add(mark);
        LogoWordmark small = new LogoWordmark(22, new Color(0xeafcff), MenuScreen.CYAN, true);
        small.setLocation(Ui.W - 190, 46);
        add(small);
        GLabel sub = Ui.label(spaced("SEVEN BATTLEFIELDS  -  BEGINNER TO EXPERT  -  PICK YOURS"), 0, 0, MenuScreen.menuFont(Font.PLAIN, 12), Ui.withAlpha(MenuScreen.MAGENTA, 200));
        sub.setLocation((Ui.W - sub.getWidth()) / 2, 88);
        add(sub);

        List<GameMap> maps = MapCatalog.createAll();
        int n = maps.size();
        int rows = Math.max(1, (n + COLS - 1) / COLS);
        // DIFFICULTY HOOK: mode picker under the subtitle; map cards start lower to make room
        difficulty = new DifficultySelector(25, 104, Ui.W - 50);
        add(difficulty);
        double top = 104 + DifficultySelector.HEIGHT + 40, bottom = Ui.H - 28, gap = 18;
        double cardW = (Ui.W - 50 - gap * (COLS - 1)) / COLS;
        double cardH = Math.min(rows == 1 ? 540 : 520, (bottom - top - gap * (rows - 1)) / rows);   // capped: no big empty gap under the text
        top += Math.max(0, ((bottom - top - gap * (rows - 1)) / rows - cardH) * 0.35 * rows);   // sit slightly above centre when the cards are capped
        for (int i = 0; i < n; i++) {
            GameMap m = maps.get(i);
            int col = i % COLS, row = i / COLS;
            buildCard(app, m, i, 25 + col * (cardW + gap), top + row * (cardH + gap), cardW, cardH);
        }
        NeonButton back = new NeonButton(25, 28, 130, 42, "BACK", MenuScreen.menuFont(Font.BOLD, 18), MenuScreen.CYAN, app::showMenu);
        buttons.add(back);
        add(back);
        // AUDIO: Sound / Music toggles beside BACK
        audioToggles = AudioToggle.pair(168, 28, 118, 42, 8, "SOUND", "MUSIC", chips);
        for (UIButton c : chips) add(c);
    }

    /**
     * Logical centre of a map card's DEPLOY button, for tools that click through the real UI (the demo driver). Mirrors the
     * layout in the constructor.
     */
    public static double[] deployCenter(int idx) {
        int n = lindefense.map.MapCatalog.MAP_COUNT, rows = Math.max(1, (n + COLS - 1) / COLS);
        double top = 104 + DifficultySelector.HEIGHT + 40, bottom = Ui.H - 28, gap = 18;
        double cardW = (Ui.W - 50 - gap * (COLS - 1)) / COLS;
        double full = (bottom - top - gap * (rows - 1)) / rows;
        double cardH = Math.min(rows == 1 ? 540 : 520, full);
        top += Math.max(0, (full - cardH) * 0.35 * rows);
        boolean compact = cardH < 520;
        double y = top + (idx / COLS) * (cardH + gap), x = 25 + (idx % COLS) * (cardW + gap);
        double by = y + cardH - (compact ? 54 : 70), bh = compact ? 40 : 50;
        return new double[] { x + cardW / 2, by + bh / 2 };
    }

    private static String spaced(String s) {
        StringBuilder sb = new StringBuilder();
        for (char c : s.toCharArray()) { sb.append(c); sb.append(' '); }
        return sb.toString().trim();
    }

    private static Color difficultyColor(String d) {
        switch (d) {
            case "Beginner": return new Color(0x3bff8a);
            case "Intermediate": return MenuScreen.YELLOW;
            case "Advanced": return new Color(0xff8c3b);
            default: return MenuScreen.MAGENTA;
        }
    }

    private void buildCard(LindefenseProgram app, GameMap m, int idx, double x, double y, double w, double h) {
        Color dc = difficultyColor(m.getDifficulty());
        GPolygon frame = cut(x, y, w, h, 16);
        frame.setFilled(true);
        frame.setFillColor(new Color(0x0a0e1e));
        frame.setColor(Ui.withAlpha(MenuScreen.CYAN, 150));
        add(frame);
        GPolygon inner = cut(x + 4, y + 4, w - 8, h - 8, 13);
        inner.setColor(Ui.withAlpha(dc, 70));
        add(inner);
        // preview thumbnail (uniform scale, centred): takes all the height the name, badge and DEPLOY button leave
        boolean compact = h < 520;
        double ph = h - (compact ? 123 : 139);
        double s = Math.min((w - 24) / GameMap.WIDTH, ph / GameMap.HEIGHT);
        double pw = GameMap.WIDTH * s;
        ph = GameMap.HEIGHT * s;
        double px = x + (w - pw) / 2, py = y + 14;
        add(new MapArt(m, px, py, pw, ph));
        add(Ui.rect(px, py, pw, ph, null, Ui.withAlpha(MenuScreen.CYAN, 90)));
        for (Path r : m.getRoutes()) {
            add(Ui.oval(px + r.getStart().x * s - 3, py + r.getStart().y * s - 3, 6, 6, Ui.GREEN, Ui.GREEN));
            add(Ui.oval(px + r.getEnd().x * s - 3, py + r.getEnd().y * s - 3, 6, 6, Ui.RED, Ui.RED));
        }
        // text block: just the name and the difficulty / lane count badge
        double tx = x + 16, ty = py + ph + 24;
        Font nameF = MenuScreen.menuFont(Font.BOLD, compact ? 19 : 24);
        add(Ui.label(m.getName().toUpperCase(), tx, ty, nameF, Ui.TEXT));
        ty += compact ? 18 : 24;
        // difficulty badge
        String badge = m.getDifficulty().toUpperCase() + "  /  " + m.getRoutes().size() + (m.getRoutes().size() == 1 ? " LANE" : " LANES");
        GLabel bl = Ui.label(badge, tx + 8, ty, Cyber.display(Font.BOLD, compact ? 14 : 16), dc);
        add(Ui.rect(tx, ty - (compact ? 13 : 15), bl.getWidth() + 16, compact ? 19 : 22, Ui.withAlpha(dc, 35), Ui.withAlpha(dc, 160)));
        add(bl);
        double buttonY = y + h - (compact ? 54 : 70);
        double buttonH = compact ? 40 : 50;
        NeonButton play = new NeonButton(x + 16, buttonY, w - 32, buttonH, "DEPLOY", MenuScreen.menuFont(Font.BOLD, compact ? 17 : 20), dc, () -> app.startGame(idx));
        buttons.add(play);
        add(play);
    }

    private static GPolygon cut(double x, double y, double w, double h, double c) {
        GPolygon p = new GPolygon();
        p.addVertex(x + c, y); p.addVertex(x + w, y); p.addVertex(x + w, y + h - c);
        p.addVertex(x + w - c, y + h); p.addVertex(x, y + h); p.addVertex(x, y + c);
        return p;
    }

    public void mousePressed(double lx, double ly) {
        for (UIButton c : chips) if (c.hit(lx, ly)) { c.click(); return; }
        if (difficulty.mousePressed(lx, ly)) { lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_CLICK); return; }   // DIFFICULTY HOOK / AUDIO HOOK
        for (NeonButton b : buttons) if (b.hit(lx, ly)) { b.click(); return; }
    }

    public void mouseMoved(double lx, double ly) {
        difficulty.mouseMoved(lx, ly);
        for (NeonButton b : buttons) b.setHover(b.hit(lx, ly));
        for (UIButton c : chips) c.setHover(c.hit(lx, ly));
    }

    public void frame(double dt) {
        t += dt;
        mark.animate(t);
        for (NeonButton b : buttons) b.animate(dt);
        AudioToggle.syncAll(audioToggles);
        for (UIButton c : chips) c.animate(dt);
    }
}
