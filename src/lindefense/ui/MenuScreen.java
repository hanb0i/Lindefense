package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import acm.graphics.GObject;
import acm.graphics.GOval;
import acm.graphics.GPolygon;
import acm.graphics.GRect;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Cyberpunk animated title card. Everything is built once in the constructor
 * (ACM primitives only) and animated by mutating positions/colours in
 * {@link #frame(double)}: neon-glow wordmark with flicker and chromatic-aberration
 * glitch bursts, holographic shimmer, synthwave perspective grid with sun and
 * skyline, low-alpha digital rain, CRT scanlines + scan bar, HUD brackets and
 * blinking readouts, neon buttons, and a 1.3 s boot-up intro that any input skips.
 */
public final class MenuScreen extends GCompound {
    private static final long serialVersionUID = 1L;

    static final Color BG = new Color(0x05070f);
    static final Color CYAN = LogoEmblem.CYAN;
    static final Color MAGENTA = LogoEmblem.MAGENTA;
    static final Color YELLOW = LogoEmblem.YELLOW;
    private static final double INTRO_TIME = 1.3;
    private static final double HORIZON = 612;
    private static final double LOGO_Y = 330;
    private static final int GRID_ROWS = 14;
    private static final int RAIN_COLUMNS = 34;
    private static final int RAIN_LEN = 9;
    private static final String GLYPHS = "01010110ABCDEF{}[]<>->∑#$%&*+=/;:";

    private final Random rnd = new Random(7);
    private final List<NeonButton> buttons = new ArrayList<>();
    private final List<UIButton> chips = new ArrayList<>();
    private AudioToggle[] audioToggles;
    private final GCompound help = new GCompound();
    private boolean helpShown;
    // SETTINGS panel: admin code entry
    private final GCompound settings = new GCompound();
    private boolean settingsShown;
    private final StringBuilder codeInput = new StringBuilder();
    private GLabel codeLabel, adminStatus, codeFeedback;
    private NeonButton disableAdmin;
    private NeonButton[] optionButtons;
    private GLabel[] optionLabels;
    // SETTINGS > AUDIO: on/off chips and volume sliders (hit-tested only while the panel is open)
    private final List<UIButton> settingsChips = new ArrayList<>();
    private AudioToggle[] settingsToggles;
    private Slider[] settingsSliders;
    /** SETTINGS > WINDOW EFFECTS on/off chip (Palantir's window grab). */
    private UIButton windowChip;
    /** SETTINGS > DISPLAY: graphics preset and frame-rate chips, and the line describing the preset. */
    private UIButton qualityChip, fpsChip;
    private GLabel displayHint;
    private double feedbackTime;
    private double t;
    private double introT;
    private boolean introDone;

    // wordmark stack
    private final LogoWordmark[] glow = new LogoWordmark[3];
    private final LogoWordmark chromaM, chromaC, main;
    private final GPolygon shimmer;
    private final GRect introBar;
    private final LogoEmblem emblem;
    private final GLabel subtitle, tagline;
    private int flickerLetter = -1;
    private double flickerTimer = 2.5;
    private double flickerLeft;
    private double glitchTimer = 2.0;
    private double glitchLeft;
    private final GRect[] slices = new GRect[3];
    private double shimmerTimer = 1.0;
    private double shimmerLeft;

    // backdrop
    private final GLine[] gridRows = new GLine[GRID_ROWS];
    private double gridPhase;
    private final List<GCompound> rainCols = new ArrayList<>();
    private final double[] rainSpeed = new double[RAIN_COLUMNS];
    private final List<GRect> windows = new ArrayList<>();
    private final GRect scanBar;
    private final GLabel sysLabel, threatLabel, verLabel, tickerLabel;
    private final GOval sunGlow;

    public MenuScreen(LindefenseProgram app) {
        add(Ui.rect(0, 0, Ui.W, Ui.H, BG, BG));
        buildRain();
        buildSunAndSkyline();
        sunGlow = Ui.oval(800 - 260, HORIZON - 260, 520, 520, Ui.withAlpha(MAGENTA, 25), Ui.withAlpha(MAGENTA, 0));
        add(sunGlow);
        buildGrid();

        // ---- wordmark stack: glow layers, chroma copies, main, shimmer
        double hgt = 112;
        double[] scales = { 1.16, 1.09, 1.035 };
        for (int i = 0; i < 3; i++) {
            glow[i] = new LogoWordmark(hgt * scales[i], Ui.withAlpha(CYAN, 18 + 18 * i), Ui.withAlpha(CYAN, 40 + 30 * i), true);
            glow[i].setLocation(800, LOGO_Y);
            add(glow[i]);
        }
        chromaM = new LogoWordmark(hgt, Ui.withAlpha(MAGENTA, 170), null, true);
        chromaC = new LogoWordmark(hgt, Ui.withAlpha(CYAN, 170), null, true);
        chromaM.setLocation(800, LOGO_Y); chromaC.setLocation(800, LOGO_Y);
        chromaM.setVisible(false); chromaC.setVisible(false);
        add(chromaM); add(chromaC);
        main = new LogoWordmark(hgt, new Color(0xeafcff), CYAN, true);
        main.setLocation(800, LOGO_Y);
        add(main);
        shimmer = new GPolygon();
        shimmer.addVertex(0, -hgt * 0.7); shimmer.addVertex(26, -hgt * 0.7); shimmer.addVertex(-14, hgt * 0.7); shimmer.addVertex(-40, hgt * 0.7);
        shimmer.setFilled(true); shimmer.setFillColor(Ui.withAlpha(Color.WHITE, 70)); shimmer.setColor(Ui.withAlpha(Color.WHITE, 0));
        shimmer.setVisible(false);
        add(shimmer);
        for (int i = 0; i < slices.length; i++) {
            slices[i] = Ui.rect(0, 0, 10, 4, BG, BG);
            slices[i].setVisible(false);
            add(slices[i]);
        }
        introBar = Ui.rect(800 - 560, LOGO_Y - 80, 1120, 6, Ui.withAlpha(Color.WHITE, 160), Ui.withAlpha(CYAN, 0));
        add(introBar);

        emblem = new LogoEmblem(130);
        emblem.setLocation(800, 150);
        add(emblem);

        subtitle = Ui.label(spaced("THE LAST LINE OF CODE"), 0, 0, menuFont(Font.BOLD, 26), CYAN);
        subtitle.setLocation((Ui.W - subtitle.getWidth()) / 2, 428);
        add(subtitle);
        tagline = Ui.label(spaced("DEPLOY. UPGRADE. DEFEND."), 0, 0, menuFont(Font.PLAIN, 14), Ui.withAlpha(MAGENTA, 220));
        tagline.setLocation((Ui.W - tagline.getWidth()) / 2, 456);
        add(tagline);

        // ---- buttons
        Font bf = menuFont(Font.BOLD, 24);
        NeonButton play = new NeonButton(Ui.W / 2.0 - 150, 488, 300, 50, "PLAY", bf, CYAN, app::showMapSelect);
        NeonButton tut = new NeonButton(Ui.W / 2.0 - 150, 546, 300, 50, "TUTORIAL", bf, new Color(0x3bff8a), app::startTutorial);
        NeonButton cat = new NeonButton(Ui.W / 2.0 - 150, 604, 300, 50, "CATALOG", bf, CYAN, app::showCatalog);
        NeonButton how = new NeonButton(Ui.W / 2.0 - 150, 662, 300, 50, "HOW TO PLAY", bf, MAGENTA, this::toggleHelp);
        NeonButton set = new NeonButton(Ui.W / 2.0 - 150, 720, 300, 50, "SETTINGS", bf, new Color(0x9b7bff), this::toggleSettings);
        NeonButton quit = new NeonButton(Ui.W / 2.0 - 150, 778, 300, 50, "QUIT", bf, YELLOW, app::quit);
        for (NeonButton b : new NeonButton[] { play, tut, cat, how, set, quit }) { buttons.add(b); add(b); }
        // AUDIO: Sound / Music toggles under the main buttons
        audioToggles = AudioToggle.pair(Ui.W / 2.0 - 150, 842, 145, 38, 10, "SOUND", "MUSIC", chips);
        for (UIButton c : chips) add(c);

        // ---- CRT overlay, HUD frame, readouts
        for (int y = 0; y < Ui.H; y += 4) {
            GLine l = new GLine(0, y, Ui.W, y);
            l.setColor(Ui.withAlpha(Color.BLACK, 46));
            add(l);
        }
        scanBar = Ui.rect(0, -120, Ui.W, 90, Ui.withAlpha(Color.WHITE, 9), Ui.withAlpha(Color.WHITE, 0));
        add(scanBar);
        buildBrackets();
        Font mono = Cyber.mono(Font.BOLD, 14);
        sysLabel = Ui.label("SYS.ONLINE  •", 44, 52, mono, new Color(0x3bff8a));
        threatLabel = Ui.label("THREAT LVL: PALANTIR", 44, Ui.H - 40, mono, MAGENTA);
        verLabel = Ui.label(lindefense.Version.LABEL, Ui.W - 150, 52, mono, YELLOW);
        tickerLabel = Ui.label("LINDEFENSE // 100 WAVES // 18 TOWERS // 17 HEROES // 7 MAPS", 0, Ui.H - 40, mono, Ui.withAlpha(CYAN, 200));
        tickerLabel.setLocation(Ui.W - 44 - tickerLabel.getWidth(), Ui.H - 40);
        add(sysLabel); add(threatLabel); add(verLabel); add(tickerLabel);
        GLabel foot = Ui.label("JAVA + STANFORD ACM GRAPHICS  •  RESIZE THE WINDOW FREELY", 0, 0, menuFont(Font.PLAIN, 12), Ui.withAlpha(CYAN, 120));
        foot.setLocation((Ui.W - foot.getWidth()) / 2, Ui.H - 14);
        add(foot);

        buildHelp();
        help.setVisible(false);
        add(help);
        buildSettings();
        settings.setVisible(false);
        add(settings);

        // start the intro with every letter hidden
        for (int i = 0; i < main.getLetterCount(); i++) setLetterStackVisible(i, false);
    }

    // ------------------------------------------------------------------ construction helpers
    /** Font fallback chain for small text. */
    static Font menuFont(int style, int size) {
        return Cyber.display(style, size);
    }

    private static String spaced(String s) {
        StringBuilder sb = new StringBuilder();
        for (char c : s.toCharArray()) { sb.append(c); sb.append(' '); }
        return sb.toString().trim();
    }

    private void buildRain() {
        for (int c = 0; c < RAIN_COLUMNS; c++) {
            GCompound col = new GCompound();
            Font f = Cyber.mono(Font.PLAIN, 13);
            for (int k = 0; k < RAIN_LEN; k++) {
                GLabel g = new Cyber.Text(String.valueOf(GLYPHS.charAt(rnd.nextInt(GLYPHS.length()))), 0, k * 16);
                g.setFont(f);
                int a = k == RAIN_LEN - 1 ? 150 : 25 + k * 9;
                g.setColor(Ui.withAlpha(k == RAIN_LEN - 1 ? Color.WHITE : (c % 3 == 0 ? MAGENTA : CYAN), a));
                col.add(g);
            }
            col.setLocation(20 + rnd.nextInt(Ui.W - 40), -rnd.nextInt(Ui.H));
            rainSpeed[c] = 60 + rnd.nextInt(110);
            rainCols.add(col);
            add(col);
        }
    }

    private void buildSunAndSkyline() {
        double r = 150;
        GOval sun = Ui.oval(800 - r, HORIZON - r, 2 * r, 2 * r, new Color(0xff4fc3), Ui.withAlpha(MAGENTA, 0));
        add(sun);
        GOval sunTop = Ui.oval(800 - r * 0.92, HORIZON - r * 0.98, 2 * r * 0.92, r * 1.1, new Color(0xffb347), Ui.withAlpha(YELLOW, 0));
        add(sunTop);
        // retro stripes
        for (int i = 0; i < 7; i++) {
            double y = HORIZON - 8 - i * (14 + i * 3);
            add(Ui.rect(800 - r, y, 2 * r, 3 + i * 0.6, BG, BG));
        }
        // skyline silhouette
        double x = 0;
        int b = 0;
        while (x < Ui.W) {
            double w = 28 + rnd.nextInt(60);
            double h = 30 + rnd.nextInt(b % 5 == 2 ? 190 : 110);
            if (Math.abs(x + w / 2 - 800) < 120) h *= 0.5;
            add(Ui.rect(x, HORIZON - h, w, h, new Color(0x04050c), new Color(0x101430)));
            if (b % 4 == 0) {
                GRect spire = Ui.rect(x + w / 2 - 2, HORIZON - h - 26, 4, 26, new Color(0x0a0c1c), new Color(0x0a0c1c));
                add(spire);
                GOval beacon = Ui.oval(x + w / 2 - 3, HORIZON - h - 30, 6, 6, Ui.withAlpha(MAGENTA, 220), Ui.withAlpha(MAGENTA, 0));
                add(beacon);
            }
            for (int k = 0; k < 2 + rnd.nextInt(3); k++) {
                double wx = x + 6 + rnd.nextInt((int) Math.max(1, w - 14)), wy = HORIZON - h + 8 + rnd.nextInt((int) Math.max(1, h - 20));
                GRect win = Ui.rect(wx, wy, 5, 7, Ui.withAlpha(rnd.nextBoolean() ? YELLOW : CYAN, 180), Ui.withAlpha(YELLOW, 0));
                windows.add(win);
                add(win);
            }
            x += w + 3 + rnd.nextInt(10);
            b++;
        }
        // floor and horizon glow
        add(Ui.rect(0, HORIZON, Ui.W, Ui.H - HORIZON, new Color(0x070616), new Color(0x070616)));
        for (int i = 4; i >= 1; i--) add(Ui.rect(0, HORIZON - i * 2, Ui.W, i * 4, Ui.withAlpha(CYAN, 18 + 10 * (4 - i)), Ui.withAlpha(CYAN, 0)));
        GLine hl = new GLine(0, HORIZON, Ui.W, HORIZON);
        hl.setColor(CYAN);
        add(hl);
    }

    private void buildGrid() {
        for (int k = -14; k <= 14; k++) {
            double bx = 800 + k * 150;
            double tx = 800 + (bx - 800) * 0.03;
            GLine l = new GLine(tx, HORIZON + 2, bx, Ui.H);
            l.setColor(Ui.withAlpha(MAGENTA, 110));
            add(l);
        }
        for (int i = 0; i < GRID_ROWS; i++) {
            gridRows[i] = new GLine(0, HORIZON, Ui.W, HORIZON);
            gridRows[i].setColor(Ui.withAlpha(CYAN, 120));
            add(gridRows[i]);
        }
    }

    private void buildBrackets() {
        double m = 24, len = 60;
        double[][] c = { { m, m, 1, 1 }, { Ui.W - m, m, -1, 1 }, { m, Ui.H - m, 1, -1 }, { Ui.W - m, Ui.H - m, -1, -1 } };
        for (double[] k : c) {
            GLine a = new GLine(k[0], k[1], k[0] + len * k[2], k[1]);
            GLine b = new GLine(k[0], k[1], k[0], k[1] + len * k[3]);
            a.setColor(Ui.withAlpha(CYAN, 200)); b.setColor(Ui.withAlpha(CYAN, 200));
            add(a); add(b);
            GLine a2 = new GLine(k[0] + 4 * k[2], k[1] + 4 * k[3], k[0] + (len - 20) * k[2], k[1] + 4 * k[3]);
            a2.setColor(Ui.withAlpha(MAGENTA, 160));
            add(a2);
        }
        GRect frame = Ui.rect(m + 8, m + 8, Ui.W - 2 * m - 16, Ui.H - 2 * m - 16, null, Ui.withAlpha(CYAN, 35));
        add(frame);
    }

    private void buildHelp() {
        help.add(Ui.rect(Ui.W / 2.0 - 440, 110, 880, 780, Ui.withAlpha(new Color(0x070a16), 245), CYAN));
        help.add(Ui.rect(Ui.W / 2.0 - 434, 116, 868, 768, null, Ui.withAlpha(MAGENTA, 90)));
        double y = 146, x = Ui.W / 2.0 - 410;
        String[][] sections = {
            { "GOAL", "Survive all 100 waves and destroy Palantir, the BAD-class final boss, on Wave 100. You start with $650 and 100 lives." },
            { "BUILDING", "Pick a faction tab (or press B for all towers), click a tower, then click a free spot beside the track. Each tower has three upgrades named after its model lineup (Zethos has four) and several targeting priorities. Once a tower has every upgrade, buy its overpowered ability for $15,000 (U or the side panel); Zethos has Reality Collapse from the start." },
            { "HERO STORE", "Press HEROES (or K) in game. Buy a hero once to unlock it for good: 18 heroes, up to Mr. Lindemann, the strongest. Unlocked heroes deploy free, once per match, at most 3 per game, and level up with three upgrades. New here? Try TUTORIAL; look anything up in CATALOG." },
            { "ECONOMY", "Enemies pay cash when destroyed; every wave pays a bonus. Perplexity earns research income. Selling refunds 70% of everything spent on a tower." },
            { "ENEMIES", "Data structures and sorting algorithms, each with a mechanic: Bubble Sort swaps places, Heap Sort shields allies and is Lead-type (Sharp damage cannot hurt it), Merge/Quick/Counting/TimSort split, Bucket Sort stores weaker enemies, Radix Sort turns Lead-type in its armoured phases, Shell Sort gap-jumps." },
            { "MODIFIERS", "Camo needs detection (Grok, Perplexity and its radius, Gemini / Llama U2). Regrow heals. Fortified has double HP. Prompt Injection hijacks nearby towers; Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann are immune." },
            { "BOSSES", "Bellarmine College Prep (MOAB, wave 40), SW Resource Consultant (BFB, 60), 3Com (ZOMG, 80), Lockheed Martin (DDT, 90) and Palantir (BAD, 100): Predictive Surveillance plus one trick per phase - Panopticon sweep, Prompt Broadcast with decoys, a System Takeover that grabs your window." },
            { "CONTROLS", "Space: next wave.  1/2/3: speed.  P: pause.  Esc: pause menu.  Right-click: cancel.  B: all towers.  U: upgrade / buy ability.  S: sell.  A: ability.  T: targeting.  K: Hero Store.  H: help.  M / N: music / sound." },
        };
        Font hf = menuFont(Font.BOLD, 18), bf = Cyber.body(Font.PLAIN, 14);
        for (String[] s : sections) {
            y += 26;
            help.add(Ui.label(s[0], x, y, hf, CYAN));
            for (String l : Ui.wrap(s[1], bf, 820)) { y += 20; help.add(Ui.label(l, x, y, bf, Ui.TEXT)); }
            y += 6;
        }
        NeonButton close = new NeonButton(Ui.W / 2.0 - 100, 822, 200, 48, "CLOSE", menuFont(Font.BOLD, 20), MAGENTA, this::toggleHelp);
        help.add(close);
        buttons.add(close);
    }

    // ------------------------------------------------------------------ input
    private void toggleHelp() {
        helpShown = !helpShown;
        help.setVisible(helpShown);
    }

    /** Any click or key ends the boot-up intro immediately. */
    public void skipIntro() {
        if (introDone) return;
        introDone = true;
        introBar.setVisible(false);
        for (int i = 0; i < main.getLetterCount(); i++) setLetterStackVisible(i, true);
    }

    public void mousePressed(double lx, double ly) {
        skipIntro();
        if (settingsShown) {   // the settings panel is modal
            if (Slider.pressAny(lx, ly, settingsSliders)) return;   // AUDIO: volume sliders
            for (UIButton c : settingsChips) if (c.hit(lx, ly)) { c.click(); return; }
            for (NeonButton b : buttons) if (b.getParent() == settings && b.isVisible() && b.hit(lx, ly)) { b.click(); return; }
            return;
        }
        if (!helpShown) for (UIButton c : chips) if (c.hit(lx, ly)) { c.click(); return; }
        for (NeonButton b : buttons) if (b.hit(lx, ly) && b.isVisible() && b.getParent() != settings && (b.getParent() != help || helpShown)) { b.click(); return; }
    }

    // ------------------------------------------------------------------ settings / admin code
    private void buildSettings() {
        double w = 720, h = 880, x = (Ui.W - w) / 2, y = 60;
        settings.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.withAlpha(new Color(0x02030a), 170), Ui.withAlpha(new Color(0x02030a), 0)));
        settings.add(new Cyber.Chamfer(x, y, w, h, 18).fill(new Color(7, 10, 22, 248)).border(CYAN).glow(1).ticks(true));
        GLabel title = Ui.label("SETTINGS", 0, 0, menuFont(Font.BOLD, 32), CYAN);
        title.setLocation((Ui.W - title.getWidth()) / 2, y + 52);
        settings.add(title);
        double lx = x + 40, ty = y + 100;
        ty = buildAudioSettings(lx, ty, w - 80);
        ty = buildDisplaySettings(lx, ty, w - 80);
        settings.add(Ui.label("ADMIN CODE", lx, ty, menuFont(Font.BOLD, 20), new Color(0x9b7bff)));
        Font body = Cyber.body(Font.PLAIN, 14);
        for (String l : Ui.wrap("Enter the admin code to unlock the cheat checklist. Each option can be switched on and off on its own and applies to matches started from PLAY.", body, w - 80)) {
            ty += 20;
            settings.add(Ui.label(l, lx, ty, body, Ui.TEXT));
        }
        double by = ty + 22;
        settings.add(new Cyber.Chamfer(lx, by, 380, 48, 8).fill(new Color(2, 4, 12, 240)).border(Ui.withAlpha(CYAN, 200)).scan(false));
        codeLabel = Ui.label("", lx + 16, by + 32, Cyber.mono(Font.BOLD, 20), Cyber.TEXT);
        settings.add(codeLabel);
        NeonButton submit = new NeonButton(lx + 400, by, 200, 48, "ENTER", menuFont(Font.BOLD, 20), new Color(0x3bff8a), this::submitCode);
        settings.add(submit);
        buttons.add(submit);
        adminStatus = Ui.label("", lx, by + 76, Cyber.mono(Font.BOLD, 15), Cyber.DIM);
        settings.add(adminStatus);
        codeFeedback = Ui.label("", lx, by + 96, Cyber.mono(Font.PLAIN, 13), Cyber.RED);
        settings.add(codeFeedback);
        // the checklist: one toggle per cheat, revealed once the code is accepted
        lindefense.sim.AdminMode.Option[] opts = lindefense.sim.AdminMode.Option.values();
        optionButtons = new NeonButton[opts.length];
        optionLabels = new GLabel[opts.length];
        double oy = by + 112;
        for (int i = 0; i < opts.length; i++) {
            final lindefense.sim.AdminMode.Option o = opts[i];
            NeonButton t = new NeonButton(lx, oy, 360, 40, o.label, menuFont(Font.BOLD, 17), new Color(0x3bff8a), () -> toggleOption(o));
            settings.add(t);
            buttons.add(t);
            optionButtons[i] = t;
            GLabel desc = Ui.label(o.description, lx + 374, oy + 25, Cyber.body(Font.PLAIN, 12), Cyber.MUTED);
            settings.add(desc);
            optionLabels[i] = desc;
            oy += 46;
        }
        disableAdmin = new NeonButton(lx, oy + 6, 360, 40, "LOCK ADMIN (CODE AGAIN)", menuFont(Font.BOLD, 15), Cyber.RED, this::disableAdmin);
        settings.add(disableAdmin);
        buttons.add(disableAdmin);
        NeonButton close = new NeonButton((Ui.W - 200) / 2.0, y + h - 62, 200, 46, "CLOSE", menuFont(Font.BOLD, 20), MAGENTA, this::toggleSettings);
        settings.add(close);
        buttons.add(close);
        refreshSettings();
    }

    /** SETTINGS > AUDIO: per channel an on/off chip and a volume slider. Returns the baseline y of the next section. */
    private double buildAudioSettings(double lx, double ty, double cw) {
        settings.add(Ui.label("AUDIO", lx, ty, menuFont(Font.BOLD, 20), CYAN));
        Font body = Cyber.body(Font.PLAIN, 14);
        for (String l : Ui.wrap("Levels are saved. Switching a channel off keeps its level. Outside SETTINGS, M toggles music and N sound.", body, cw)) {
            ty += 20;
            settings.add(Ui.label(l, lx, ty, body, Ui.TEXT));
        }
        double ry = ty + 16, rh = 40, chipW = 200, gap = 12, sx = lx + chipW + gap, sw = cw - chipW - gap;
        settingsToggles = new AudioToggle[] { AudioToggle.sound(lx, ry, chipW, rh, "SOUND"), AudioToggle.music(lx, ry + rh + 10, chipW, rh, "MUSIC") };
        for (AudioToggle a : settingsToggles) { settings.add(a.getButton()); settingsChips.add(a.getButton()); }
        settingsSliders = new Slider[] { AudioToggle.soundVolume(sx, ry, sw, rh, "VOLUME"), AudioToggle.musicVolume(sx, ry + rh + 10, sw, rh, "VOLUME") };
        for (Slider sl : settingsSliders) settings.add(sl);
        double divY = ry + 2 * rh + 10 + 22;
        settings.add(Ui.rect(lx, divY, cw, 1, Ui.withAlpha(CYAN, 70), Ui.withAlpha(CYAN, 0)));
        return divY + 40;
    }

    /**
     * SETTINGS > DISPLAY: one row of chips (graphics quality preset, frame-rate cap, Palantir's window effects) and a
     * line describing the chosen preset. Each chip cycles its value on click. Returns the baseline y of the next section.
     */
    private double buildDisplaySettings(double lx, double ty, double cw) {
        settings.add(Ui.label("DISPLAY", lx, ty, menuFont(Font.BOLD, 20), CYAN));
        double cy = ty + 14, ch = 38, gap = 12, chipW = (cw - 2 * gap) / 3;
        qualityChip = new UIButton(lx, cy, chipW, ch, "", Cyber.mono(Font.BOLD, 13), this::cycleQuality);
        fpsChip = new UIButton(lx + chipW + gap, cy, chipW, ch, "", Cyber.mono(Font.BOLD, 13), this::cycleFps);
        windowChip = new UIButton(lx + 2 * (chipW + gap), cy, chipW, ch, "", Cyber.mono(Font.BOLD, 13), this::toggleWindowEffects);
        for (UIButton b : new UIButton[] { qualityChip, fpsChip, windowChip }) { settings.add(b); settingsChips.add(b); }
        Font body = Cyber.body(Font.PLAIN, 14);
        displayHint = Ui.label("", lx, cy + ch + 24, body, Ui.TEXT);
        settings.add(displayHint);
        settings.add(Ui.label("Window effects: Palantir's final phase grabs and shrinks this window; drag it back to break its seal.",
            lx, cy + ch + 46, Cyber.body(Font.PLAIN, 13), Cyber.MUTED));
        syncWindowChip();
        syncDisplayChips();
        double divY = cy + ch + 66;
        settings.add(Ui.rect(lx, divY, cw, 1, Ui.withAlpha(CYAN, 70), Ui.withAlpha(CYAN, 0)));
        return divY + 40;
    }

    /** QUALITY chip: LOW -> MEDIUM -> HIGH -> LOW; takes effect on the next frame. */
    private void cycleQuality() {
        GraphicsSettings gs = GraphicsSettings.get();
        gs.setQuality(gs.quality().next());
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
        syncDisplayChips();
    }

    /** MAX FPS chip: 30 -> 60 -> 120 -> 30; the frame timer picks it up on its next tick. */
    private void cycleFps() {
        GraphicsSettings gs = GraphicsSettings.get();
        gs.setMaxFps(gs.nextFps());
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
        syncDisplayChips();
    }

    private void syncDisplayChips() {
        GraphicsSettings gs = GraphicsSettings.get();
        GraphicsSettings.Quality q = gs.quality();
        qualityChip.setText("QUALITY: " + q.label.toUpperCase());
        qualityChip.setSelected(q == GraphicsSettings.Quality.HIGH);
        qualityChip.setAccent(q == GraphicsSettings.Quality.HIGH ? CYAN : q == GraphicsSettings.Quality.MEDIUM ? Cyber.YELLOW : Cyber.DIM);
        fpsChip.setText("MAX FPS: " + gs.getMaxFps());
        fpsChip.setSelected(gs.getMaxFps() > GraphicsSettings.DEFAULT_FPS);
        fpsChip.setAccent(gs.getMaxFps() >= GraphicsSettings.DEFAULT_FPS ? CYAN : Cyber.DIM);
        displayHint.setLabel(q == GraphicsSettings.Quality.HIGH ? "High: sharpest on 4K / 5K screens, with glow, vignette and screen shake."
            : q == GraphicsSettings.Quality.MEDIUM ? "Medium: the original look, with automatic detail in big fights."
            : "Low: fastest. Lighter bitmaps and reduced detail everywhere.");
    }

    private void toggleWindowEffects() {
        boolean on = WindowEffects.toggle();
        lindefense.audio.AudioManager.sfx(on ? lindefense.audio.Sfx.UI_SELECT : lindefense.audio.Sfx.UI_CLICK);   // AUDIO HOOK
        syncWindowChip();
    }

    private void syncWindowChip() {
        boolean on = WindowEffects.isEnabled();
        windowChip.setText("WINDOW EFFECTS: " + (on ? "ON" : "OFF"));
        windowChip.setSelected(on);
        windowChip.setAccent(on ? Cyber.MAGENTA : Cyber.DIM);
    }

    private void toggleSettings() {
        settingsShown = !settingsShown;
        if (settingsShown) { helpShown = false; help.setVisible(false); codeInput.setLength(0); codeFeedback.setLabel(""); }
        settings.setVisible(settingsShown);
        refreshSettings();
    }

    private void submitCode() {
        if (lindefense.sim.AdminMode.tryCode(codeInput.toString())) {
            lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
            codeFeedback.setLabel("Code accepted. Pick the cheats you want below.");
            codeFeedback.setColor(Cyber.GREEN);
        } else {
            lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.INVALID);   // AUDIO HOOK
            codeFeedback.setLabel(codeInput.length() == 0 ? "Type the code first." : "Invalid code.");
            codeFeedback.setColor(Cyber.RED);
        }
        codeInput.setLength(0);
        feedbackTime = 4;
        refreshSettings();
    }

    private void toggleOption(lindefense.sim.AdminMode.Option o) {
        boolean on = lindefense.sim.AdminMode.toggle(o);
        lindefense.audio.AudioManager.sfx(on ? lindefense.audio.Sfx.UI_SELECT : lindefense.audio.Sfx.UI_CLICK);   // AUDIO HOOK
        codeFeedback.setLabel(o.label + (on ? ": ON" : ": OFF"));
        codeFeedback.setColor(on ? Cyber.GREEN : Cyber.MUTED);
        feedbackTime = 3;
        refreshSettings();
    }

    private void disableAdmin() {
        lindefense.sim.AdminMode.disableAll();
        codeFeedback.setLabel("Admin cheats off. Enter the code again to re-open the checklist.");
        codeFeedback.setColor(Cyber.MUTED);
        feedbackTime = 4;
        refreshSettings();
    }

    private void refreshSettings() {
        boolean unlocked = lindefense.sim.AdminMode.isUnlocked();
        adminStatus.setLabel(unlocked
            ? (lindefense.sim.AdminMode.anyOn() ? "ADMIN: UNLOCKED  //  CHEATS ACTIVE" : "ADMIN: UNLOCKED  //  NO CHEATS ON")
            : "ADMIN: LOCKED");
        adminStatus.setColor(unlocked ? (lindefense.sim.AdminMode.anyOn() ? Cyber.GREEN : Cyber.YELLOW) : Cyber.DIM);
        lindefense.sim.AdminMode.Option[] opts = lindefense.sim.AdminMode.Option.values();
        for (int i = 0; i < opts.length; i++) {
            boolean on = lindefense.sim.AdminMode.isOn(opts[i]);
            optionButtons[i].setVisible(unlocked);
            optionLabels[i].setVisible(unlocked);
            optionButtons[i].setText((on ? "[X]  " : "[  ]  ") + opts[i].label);
            optionButtons[i].setSelected(on);
        }
        disableAdmin.setVisible(unlocked);
        updateCodeLabel();
    }

    private void updateCodeLabel() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < codeInput.length(); i++) sb.append('*');
        boolean caret = settingsShown && ((int) (t * 2.2)) % 2 == 0;
        if (codeInput.length() == 0 && !caret) codeLabel.setLabel("enter code");
        else codeLabel.setLabel(sb + (caret ? "_" : ""));
        codeLabel.setColor(codeInput.length() == 0 && !caret ? Cyber.DIM : Cyber.TEXT);
    }

    /** True while the settings panel is open and capturing typed text. */
    public boolean isTyping() { return settingsShown; }

    /**
     * Keys on the main menu. Any key ends the intro and Esc closes the HELP panel. While the settings panel is open
     * keys type the code: Enter submits, Backspace deletes, Esc closes.
     */
    public void keyPressed(java.awt.event.KeyEvent e) {
        skipIntro();
        int k = e.getKeyCode();
        if (!settingsShown) {
            if (k == java.awt.event.KeyEvent.VK_ESCAPE && helpShown) toggleHelp();
            return;
        }
        if (k == java.awt.event.KeyEvent.VK_ESCAPE) { toggleSettings(); return; }
        if (k == java.awt.event.KeyEvent.VK_ENTER) { submitCode(); return; }
        if (k == java.awt.event.KeyEvent.VK_BACK_SPACE) { if (codeInput.length() > 0) codeInput.setLength(codeInput.length() - 1); updateCodeLabel(); return; }
        char c = e.getKeyChar();
        if (c != java.awt.event.KeyEvent.CHAR_UNDEFINED && !Character.isISOControl(c) && codeInput.length() < 24) {
            codeInput.append(c);
            updateCodeLabel();
        }
    }

    public void mouseMoved(double lx, double ly) {
        for (NeonButton b : buttons) b.setHover(b.hit(lx, ly));
        for (UIButton c : chips) c.setHover(c.hit(lx, ly));
        for (UIButton c : settingsChips) c.setHover(settingsShown && c.hit(lx, ly));
        if (settingsShown) Slider.hoverAll(lx, ly, settingsSliders);
    }

    /** Mouse drag (logical coordinates): moves a grabbed SETTINGS volume slider. */
    public void mouseDragged(double lx, double ly) { if (settingsShown) Slider.dragAll(lx, ly, settingsSliders); }

    /** Mouse release: ends a SETTINGS volume-slider drag (the level is saved). */
    public void mouseReleased() { Slider.releaseAll(settingsSliders); }

    private void setLetterStackVisible(int i, boolean v) {
        main.setLetterVisible(i, v);
        for (LogoWordmark g : glow) g.setLetterVisible(i, v);
        chromaM.setLetterVisible(i, v);
        chromaC.setLetterVisible(i, v);
    }

    // ------------------------------------------------------------------ animation
    public void frame(double dt) {
        t += dt;
        if (settingsShown) {
            updateCodeLabel();
            if (feedbackTime > 0 && (feedbackTime -= dt) <= 0) codeFeedback.setLabel("");
            AudioToggle.syncAll(settingsToggles);   // AUDIO: SETTINGS chips / sliders follow M / N and the other screens
            for (UIButton c : settingsChips) c.animate(dt);
            Slider.frameAll(dt, settingsSliders);
        }
        animateIntro(dt);
        animateLogo(dt);
        animateBackdrop(dt);
        emblem.animate(t);
        for (NeonButton b : buttons) b.animate(dt);
        AudioToggle.syncAll(audioToggles);
        for (UIButton c : chips) c.animate(dt);
        sysLabel.setVisible(((int) (t * 1.6)) % 2 == 0 || t % 1 > 0.2);
        threatLabel.setColor(((int) (t * 2)) % 2 == 0 ? MAGENTA : Ui.withAlpha(MAGENTA, 120));
        verLabel.setColor(Ui.withAlpha(YELLOW, (int) (170 + 80 * Math.sin(t * 4))));
    }

    private void animateIntro(double dt) {
        if (introDone) return;
        introT += dt;
        int n = main.getLetterCount();
        int shown = (int) Math.min(n, Math.floor(introT / INTRO_TIME * (n + 1)));
        for (int i = 0; i < n; i++) {
            boolean v = i < shown;
            if (i == shown && rnd.nextDouble() < 0.5) v = true; // glitchy pre-flash of the next letter
            setLetterStackVisible(i, v);
        }
        double p = Math.min(1, introT / INTRO_TIME);
        introBar.setLocation(800 - 560, LOGO_Y - 90 + 180 * p);
        introBar.setFillColor(Ui.withAlpha(Color.WHITE, (int) (200 * (1 - p * 0.6))));
        if (introT >= INTRO_TIME + 0.05) skipIntro();
    }

    private void animateLogo(double dt) {
        // glow breathing
        double breathe = 0.5 + 0.5 * Math.sin(t * 1.7);
        for (int i = 0; i < 3; i++) {
            int a = (int) ((14 + 16 * i) * (0.7 + 0.6 * breathe));
            glow[i].setTint(Ui.withAlpha(CYAN, a), Ui.withAlpha(CYAN, a + 25));
        }
        // neon flicker on one letter
        flickerTimer -= dt;
        if (flickerLeft > 0) {
            flickerLeft -= dt;
            boolean dim = rnd.nextDouble() < 0.6;
            main.setLetterTint(flickerLetter, dim ? Ui.withAlpha(new Color(0xeafcff), 70) : new Color(0xeafcff), dim ? Ui.withAlpha(CYAN, 90) : CYAN);
            if (flickerLeft <= 0) { main.setLetterTint(flickerLetter, new Color(0xeafcff), CYAN); flickerLetter = -1; }
        } else if (flickerTimer <= 0 && introDone) {
            flickerTimer = 1.8 + rnd.nextDouble() * 2.5;
            flickerLeft = 0.12 + rnd.nextDouble() * 0.25;
            flickerLetter = rnd.nextInt(main.getLetterCount());
        }
        // chromatic aberration glitch bursts + slice displacement
        glitchTimer -= dt;
        if (glitchLeft > 0) {
            glitchLeft -= dt;
            double dx = 4 + rnd.nextDouble() * 12;
            double dy = rnd.nextDouble() * 4 - 2;
            chromaM.setLocation(800 - dx, LOGO_Y + dy);
            chromaC.setLocation(800 + dx, LOGO_Y - dy);
            chromaM.setVisible(true); chromaC.setVisible(true);
            for (GRect s : slices) {
                s.setVisible(true);
                double y = LOGO_Y - 60 + rnd.nextDouble() * 120;
                s.setBounds(800 - 520 + rnd.nextDouble() * 80, y, 1000 + rnd.nextDouble() * 80, 2 + rnd.nextDouble() * 5);
                s.setFillColor(rnd.nextDouble() < 0.3 ? Ui.withAlpha(CYAN, 120) : BG);
                s.setColor(s.getFillColor());
            }
            if (glitchLeft <= 0) {
                chromaM.setVisible(false); chromaC.setVisible(false);
                for (GRect s : slices) s.setVisible(false);
            }
        } else if (glitchTimer <= 0) {
            glitchTimer = 2.5 + rnd.nextDouble() * 4;
            glitchLeft = 0.14 + rnd.nextDouble() * 0.2;
        }
        // holographic shimmer sweep
        shimmerTimer -= dt;
        if (shimmerLeft > 0) {
            shimmerLeft -= dt;
            double p = 1 - shimmerLeft / 0.8;
            shimmer.setVisible(true);
            shimmer.setLocation(800 - 560 + 1120 * p, LOGO_Y);
            if (shimmerLeft <= 0) shimmer.setVisible(false);
        } else if (shimmerTimer <= 0) {
            shimmerTimer = 3.5 + rnd.nextDouble() * 2;
            shimmerLeft = 0.8;
        }
    }

    private void animateBackdrop(double dt) {
        // scrolling perspective floor
        gridPhase = (gridPhase + dt * 0.45) % 1.0;
        for (int i = 0; i < GRID_ROWS; i++) {
            double p = ((i + gridPhase) / GRID_ROWS);
            double y = HORIZON + (Ui.H - HORIZON) * Math.pow(p, 2.3);
            gridRows[i].setStartPoint(0, y);
            gridRows[i].setEndPoint(Ui.W, y);
            gridRows[i].setColor(Ui.withAlpha(CYAN, (int) (30 + 170 * p)));
        }
        sunGlow.setFillColor(Ui.withAlpha(MAGENTA, (int) (20 + 14 * Math.sin(t * 1.3))));
        // digital rain
        for (int c = 0; c < rainCols.size(); c++) {
            GCompound col = rainCols.get(c);
            col.move(0, rainSpeed[c] * dt);
            if (col.getY() > Ui.H) {
                col.setLocation(20 + rnd.nextInt(Ui.W - 40), -RAIN_LEN * 16 - rnd.nextInt(300));
            }
            if (rnd.nextDouble() < 0.08) {
                GObject g = col.getElement(rnd.nextInt(RAIN_LEN));
                ((GLabel) g).setLabel(String.valueOf(GLYPHS.charAt(rnd.nextInt(GLYPHS.length()))));
            }
        }
        // CRT scan bar
        scanBar.setLocation(0, (t * 70) % (Ui.H + 200) - 150);
        // window twinkle
        if (rnd.nextDouble() < 0.3 && !windows.isEmpty()) {
            GRect w = windows.get(rnd.nextInt(windows.size()));
            w.setFillColor(Ui.withAlpha(rnd.nextBoolean() ? YELLOW : CYAN, 40 + rnd.nextInt(200)));
        }
    }
}
