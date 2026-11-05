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
 * colour-coded difficulty badge and lane count, styled to match the cyberpunk
 * title card. A card's DEPLOY button opens a mission briefing popup (large
 * preview, description, map mechanics, chosen Difficulty Growth mode) whose own
 * DEPLOY starts the match; BACK or Esc closes it. All geometry is in logical
 * coordinates so hit-testing stays correct at any window size.
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
    private final LindefenseProgram app;
    private final List<GameMap> maps;

    // ---- mission briefing popup (opened by a card's DEPLOY)
    /** Popup panel geometry (logical), shared with {@link #briefingDeployCenter()}. */
    private static final double BRIEF_W = 1100, BRIEF_H = 640;
    private static final double BRIEF_X = (Ui.W - BRIEF_W) / 2, BRIEF_Y = (Ui.H - BRIEF_H) / 2;
    private static final double BRIEF_PAD = 34, BRIEF_ART_W = 600, BRIEF_BUTTON_H = 54;
    /** The open popup, or null while closed. */
    private GCompound briefing;
    private final List<NeonButton> briefingButtons = new ArrayList<>();
    private int briefingMap = -1;

    public MapSelectScreen(LindefenseProgram app) {
        this.app = app;
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

        maps = MapCatalog.createAll();
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
        NeonButton play = new NeonButton(x + 16, buttonY, w - 32, buttonH, "DEPLOY", MenuScreen.menuFont(Font.BOLD, compact ? 17 : 20), dc, () -> openBriefing(idx));
        buttons.add(play);
        add(play);
    }

    // ------------------------------------------------------------------ mission briefing popup
    /** Logical centre of the briefing popup's DEPLOY button (for tools that click through the real UI). */
    public static double[] briefingDeployCenter() {
        double[] r = briefingDeployRect();
        return new double[] { r[0] + r[2] / 2, r[1] + r[3] / 2 };
    }

    /** {x, y, w, h} of the popup's DEPLOY button; BACK sits to its left. */
    private static double[] briefingDeployRect() {
        double rx = BRIEF_X + BRIEF_PAD + BRIEF_ART_W + 36, rw = BRIEF_X + BRIEF_W - BRIEF_PAD - rx;
        double by = BRIEF_Y + BRIEF_H - BRIEF_PAD - BRIEF_BUTTON_H;
        return new double[] { rx + 166, by, rw - 166, BRIEF_BUTTON_H };
    }

    /** True while the mission briefing popup is showing. */
    public boolean isBriefingOpen() { return briefing != null; }

    /** Index of the map in the open briefing, or -1. */
    public int getBriefingMap() { return briefingMap; }

    /** Opens the mission briefing for map {@code idx} (a card's DEPLOY button). */
    public void openBriefing(int idx) {
        closeBriefing();
        GameMap m = maps.get(idx);
        Color dc = difficultyColor(m.getDifficulty());
        briefingMap = idx;
        briefing = new GCompound();
        // dim everything behind the popup; the popup is modal
        briefing.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)));
        double px = BRIEF_X, py = BRIEF_Y, pw = BRIEF_W, ph = BRIEF_H;
        briefing.add(new Cyber.Chamfer(px, py, pw, ph, 26).fill(new Color(6, 10, 24, 244)).border(dc).glow(1.1).lineWidth(2).ticks(true));
        briefing.add(Ui.rect(px + 24, py + 12, 140, 3, MenuScreen.MAGENTA, MenuScreen.MAGENTA));
        briefing.add(Ui.label(Cyber.spaced("// mission briefing  -  sector " + (idx + 1) + " of " + maps.size()), px + BRIEF_PAD, py + 40, Cyber.mono(Font.BOLD, 12), Ui.withAlpha(MenuScreen.MAGENTA, 230)));

        // left: large preview with entry (green) and exit (red) markers
        double ax = px + BRIEF_PAD, ay = py + 60, aw = BRIEF_ART_W, ah = aw * GameMap.HEIGHT / GameMap.WIDTH, s = aw / GameMap.WIDTH;
        briefing.add(new MapArt(m, ax, ay, aw, ah));
        briefing.add(Ui.rect(ax, ay, aw, ah, null, Ui.withAlpha(dc, 170)));
        for (Path r : m.getRoutes()) {
            briefing.add(Ui.oval(ax + r.getStart().x * s - 5, ay + r.getStart().y * s - 5, 10, 10, Ui.GREEN, Ui.GREEN));
            briefing.add(Ui.oval(ax + r.getEnd().x * s - 5, ay + r.getEnd().y * s - 5, 10, 10, Ui.RED, Ui.RED));
        }
        double ly = ay + ah + 30;
        Font legendF = Cyber.mono(Font.BOLD, 12);
        briefing.add(Ui.oval(ax, ly - 9, 10, 10, Ui.GREEN, Ui.GREEN));
        GLabel entry = Ui.label("ENTRY", ax + 16, ly, legendF, Ui.TEXT);
        briefing.add(entry);
        double ex = ax + 16 + entry.getWidth() + 22;
        briefing.add(Ui.oval(ex, ly - 9, 10, 10, Ui.RED, Ui.RED));
        briefing.add(Ui.label("EXIT", ex + 16, ly, legendF, Ui.TEXT));

        // right: name, badge, description, mechanics, difficulty growth mode
        double rx = ax + aw + 36, rw = px + pw - BRIEF_PAD - rx, ty = py + 92;
        Font nameF = MenuScreen.menuFont(Font.BOLD, 30);
        for (String line : Ui.wrap(m.getName().toUpperCase(), nameF, rw)) { briefing.add(Ui.label(line, rx, ty, nameF, Ui.TEXT)); ty += 34; }
        ty += 2;
        String badge = m.getDifficulty().toUpperCase() + "  /  " + m.getRoutes().size() + (m.getRoutes().size() == 1 ? " LANE" : " LANES");
        GLabel bl = Ui.label(badge, rx + 8, ty, Cyber.display(Font.BOLD, 16), dc);
        briefing.add(Ui.rect(rx, ty - 15, bl.getWidth() + 16, 22, Ui.withAlpha(dc, 35), Ui.withAlpha(dc, 160)));
        briefing.add(bl);
        ty += 40;
        ty = briefingSection("BRIEFING", m.getDescription(), MenuScreen.CYAN, rx, ty, rw);
        ty = briefingSection("MAP MECHANICS", m.getMechanicSummary(), MenuScreen.YELLOW, rx, ty, rw);
        lindefense.sim.Difficulty d = lindefense.sim.Difficulty.getSelected();
        briefingSection("DIFFICULTY GROWTH", DifficultySelector.display(d, Cyber.body(Font.PLAIN, 16)) + "  -  " + d.subtitle, MenuScreen.MAGENTA, rx, ty, rw);

        double[] dep = briefingDeployRect();
        NeonButton back = new NeonButton(rx, dep[1], 150, dep[3], "BACK", MenuScreen.menuFont(Font.BOLD, 18), MenuScreen.CYAN, this::closeBriefing);
        NeonButton go = new NeonButton(dep[0], dep[1], dep[2], dep[3], "DEPLOY", MenuScreen.menuFont(Font.BOLD, 22), dc, () -> app.startGame(idx));
        briefingButtons.add(back);
        briefingButtons.add(go);
        briefing.add(back);
        briefing.add(go);
        add(briefing);
    }

    /** One heading + wrapped paragraph in the briefing's right column; returns the y for the next section. */
    private double briefingSection(String heading, String text, Color col, double x, double y, double w) {
        briefing.add(Ui.label(Cyber.spaced(heading), x, y, Cyber.mono(Font.BOLD, 12), Ui.withAlpha(col, 235)));
        y += 24;
        Font f = Cyber.body(Font.PLAIN, 16);
        for (String line : Ui.wrap(text, f, w)) { briefing.add(Ui.label(line, x, y, f, Ui.TEXT)); y += 22; }
        return y + 18;
    }

    /** Closes the mission briefing popup (BACK, Esc); does nothing if it is not open. */
    public void closeBriefing() {
        if (briefing == null) return;
        remove(briefing);
        briefing = null;
        briefingButtons.clear();
        briefingMap = -1;
    }

    /** Esc closes the briefing popup, or goes back to the main menu; Enter deploys from an open briefing. */
    public void keyPressed(java.awt.event.KeyEvent e) {
        int k = e.getKeyCode();
        if (k == java.awt.event.KeyEvent.VK_ESCAPE) {
            if (briefing != null) { lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_CLICK); closeBriefing(); }   // AUDIO HOOK
            else app.showMenu();
        } else if (k == java.awt.event.KeyEvent.VK_ENTER && briefing != null) {
            int idx = briefingMap;
            lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
            app.startGame(idx);
        }
    }

    private static GPolygon cut(double x, double y, double w, double h, double c) {
        GPolygon p = new GPolygon();
        p.addVertex(x + c, y); p.addVertex(x + w, y); p.addVertex(x + w, y + h - c);
        p.addVertex(x + w - c, y + h); p.addVertex(x, y + h); p.addVertex(x, y + c);
        return p;
    }

    public void mousePressed(double lx, double ly) {
        if (briefing != null) {   // the briefing popup is modal: only its own buttons respond
            for (NeonButton b : new ArrayList<>(briefingButtons)) if (b.hit(lx, ly)) { b.click(); return; }
            return;
        }
        for (UIButton c : chips) if (c.hit(lx, ly)) { c.click(); return; }
        if (difficulty.mousePressed(lx, ly)) { lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_CLICK); return; }   // DIFFICULTY HOOK / AUDIO HOOK
        for (NeonButton b : buttons) if (b.hit(lx, ly)) { b.click(); return; }
    }

    public void mouseMoved(double lx, double ly) {
        if (briefing != null) {
            for (NeonButton b : briefingButtons) b.setHover(b.hit(lx, ly));
            for (NeonButton b : buttons) b.setHover(false);
            for (UIButton c : chips) c.setHover(false);
            return;
        }
        difficulty.mouseMoved(lx, ly);
        for (NeonButton b : buttons) b.setHover(b.hit(lx, ly));
        for (UIButton c : chips) c.setHover(c.hit(lx, ly));
    }

    public void frame(double dt) {
        t += dt;
        mark.animate(t);
        for (NeonButton b : buttons) b.animate(dt);
        for (NeonButton b : briefingButtons) b.animate(dt);
        AudioToggle.syncAll(audioToggles);
        for (UIButton c : chips) c.animate(dt);
    }
}
