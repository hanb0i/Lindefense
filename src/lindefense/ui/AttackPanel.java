package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import java.awt.Color;
import java.awt.Font;
import java.awt.event.KeyEvent;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.function.Supplier;
import lindefense.ai.AttackAbility;
import lindefense.ai.AttackUnit;
import lindefense.ai.ReverseMatch;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.ui.sprites.EnemySprite;
import lindefense.ui.sprites.SpriteFactory;

/**
 * Reverse mode's right-hand panel (it replaces the tower shop while the player is the attacker): compute credits with
 * the SCALE COMPUTE investment, the 21 unit cards (enemy art, price, unlock time; click to send), modifier toggles,
 * send quantity and lane, the three exploits with cooldowns, the uplink queue, and a context box that shows the hovered
 * unit, a selected tower (read-only: the AI controls it), a selected enemy, or else the defender AI's activity feed.
 * Built once; per frame only colours, enabled states and labels change, and the context box is rebuilt only when what
 * it shows changes.
 */
public final class AttackPanel extends GCompound {
    private static final long serialVersionUID = 1L;

    private static final double X0 = Ui.PANEL_X, PAD = 8, INNER = Ui.PANEL_W - 2 * PAD;
    private static final int COLS = 3;
    private static final double GAP = 5, CARD_Y = 150, CARD_H = 62;
    private static final double CARD_W = (INNER - (COLS - 1) * GAP) / COLS;
    private static final double MODS_Y = CARD_Y + 7 * (CARD_H + GAP) + 4;   // under the 7 card rows
    /** Modifier toggles sit two per row (Regrow / Camo, Fortified / Prompt Injection). */
    private static final int MOD_ROWS = (Modifier.values().length + 1) / 2;
    private static final double MOD_H = 30, MOD_ROW = MOD_H + 4;
    private static final double SEND_Y = MODS_Y + MOD_ROWS * MOD_ROW + 4, EXPLOIT_Y = SEND_Y + 38, UPLINK_Y = EXPLOIT_Y + 58, INFO_Y = UPLINK_Y + 20;
    private static final int[] QUANTITIES = { 1, 5, 10, 25 };
    private static final Font F_MICRO = Cyber.mono(Font.BOLD, 9);
    private static final Font F_VAL = Cyber.mono(Font.BOLD, 14);
    private static final Font F_TXT = Cyber.body(Font.PLAIN, 12);

    /** In-game help for reverse mode: keys. */
    static final String[][] HELP_KEYS = { { "CLICK", "send the unit on a card" }, { "SPACE", "repeat the last send" }, { "X", "cycle send quantity" },
        { "L", "cycle lane" }, { "C", "scale compute (+4 credits/s)" }, { "Q  W  E", "Overclock / Hotfix / Zero-Day" }, { "1  2  3", "game speed" },
        { "P", "pause / resume" }, { "ESC", "pause menu" }, { "M", "music on / off" }, { "N", "sound on / off" }, { "H", "toggle this help" } };
    /** In-game help for reverse mode: rules. */
    static final String[][] HELP_NOTES = {
        { "adversarial training", "Roles reversed: you send the enemies, an AI builds and upgrades the towers. Drop its integrity to 0 before the 15:00 training run ends. Units already sent get up to 1:00 of overtime." },
        { "compute", "Credits grow every second and faster as the run goes on. SCALE COMPUTE adds income; every integrity point a leak takes pays 8 credits. Units unlock over time, bosses last." },
        { "modifiers & exploits", "Camo needs detection, Regrow heals, Fortified doubles HP. Overclock speeds your units up, Hotfix heals them, Zero-Day jams the AI's three priciest towers." },
        { "the defender", "The Difficulty Growth mode picks the AI (Novice to Superintelligence) and the rules: harder modes give its towers more damage and integrity, your units less health and income." } };

    /** One unit card. */
    private static final class Card {
        final AttackUnit unit; final UIButton button; final GLabel name, price; final Cyber.Chamfer veil;
        Card(AttackUnit unit, UIButton button, GLabel name, GLabel price, Cyber.Chamfer veil) {
            this.unit = unit; this.button = button; this.name = name; this.price = price; this.veil = veil;
        }
    }

    private final GameScreen screen;
    private final Game game;
    private final ReverseMatch match;
    private final List<UIButton> buttons = new ArrayList<>();
    private final List<Card> cards = new ArrayList<>();
    private final UIButton helpBtn, computeBtn, laneBtn;
    private final UIButton[] modBtns = new UIButton[Modifier.values().length];
    private final UIButton[] qtyBtns = new UIButton[QUANTITIES.length];
    private final UIButton[] exploitBtns = new UIButton[AttackAbility.values().length];
    private final Cyber.Bar[] exploitBars = new Cyber.Bar[AttackAbility.values().length];
    private final GLabel[] exploitMeta = new GLabel[AttackAbility.values().length];
    private final GLabel credits, income, uplink, hint;
    private final Cyber.Bar queueBar;
    private final GCompound info = new GCompound();
    private final List<UIButton> infoButtons = new ArrayList<>();
    private final List<Runnable> dyn = new ArrayList<>();
    private Cyber.Bar enemyBar;
    private final EnumSet<Modifier> mods = EnumSet.noneOf(Modifier.class);
    private int qtyIndex = 1;
    private int lane = -1;
    private AttackUnit lastSent;
    private Card hovered;
    private String builtKey = "";
    private double refresh, hintTime;

    /** Builds the panel for the screen's reverse-mode game (it must have a {@link ReverseMatch}). */
    public AttackPanel(GameScreen screen) {
        this.screen = screen;
        this.game = screen.getGame();
        this.match = game.getReverse();
        add(new Cyber.Chamfer(X0, -2, Ui.PANEL_W + 2, Ui.H + 4, 0).fill(new Color(9, 5, 20)).border(Cyber.alpha(Cyber.MAGENTA, 140)).lineWidth(2));
        add(Ui.rect(X0 + 2, 0, 3, 90, Cyber.CYAN, Cyber.CYAN));
        add(Ui.label(Cyber.spaced("uplink"), X0 + 18, 27, Cyber.display(Font.BOLD, 22), Cyber.TEXT));
        add(Ui.label(Cyber.spaced("// adversarial training"), X0 + 104, 26, F_MICRO, Cyber.alpha(Cyber.MAGENTA, 220)));
        helpBtn = button(X0 + Ui.PANEL_W - 8 - 92, 8, 92, 26, "? HELP  [H]", Cyber.mono(Font.BOLD, 11), screen::toggleHelp);
        helpBtn.setAccent(Cyber.MAGENTA);

        // ---- credits + SCALE COMPUTE
        add(new Cyber.Chamfer(X0 + PAD, 38, INNER, 70, 10).scan(false).fill(new Color(14, 10, 30, 235)).border(Cyber.alpha(Cyber.YELLOW, 150)));
        add(Ui.label(Cyber.spaced("compute credits"), X0 + 20, 54, F_MICRO, Cyber.alpha(Cyber.YELLOW, 210)));
        credits = Ui.label("", X0 + 20, 82, Cyber.mono(Font.BOLD, 26), Cyber.YELLOW);
        add(credits);
        income = Ui.label("", 0, 82, Cyber.mono(Font.BOLD, 14), Cyber.GREEN);
        add(income);
        GLabel track = Ui.label(trackText(), X0 + 20, 100, F_MICRO, Cyber.MUTED);
        add(track);
        computeBtn = button(X0 + PAD, 112, INNER, 30, "", Cyber.display(Font.BOLD, 15), this::scaleCompute);
        computeBtn.setAccent(Cyber.YELLOW);

        // ---- unit cards (catalog order: unlock order, bosses last)
        AttackUnit[] units = AttackUnit.values();
        for (int i = 0; i < units.length; i++) {
            double x = X0 + PAD + (i % COLS) * (CARD_W + GAP), y = CARD_Y + (i / COLS) * (CARD_H + GAP);
            cards.add(card(units[i], x, y));
        }

        // ---- modifiers
        Modifier[] ms = Modifier.values();
        double mw = (INNER - GAP) / 2;
        for (int i = 0; i < ms.length; i++) {
            Modifier m = ms[i];
            UIButton b = button(X0 + PAD + (i % 2) * (mw + GAP), MODS_Y + (i / 2) * MOD_ROW, mw, MOD_H, "", Cyber.display(Font.BOLD, 13), () -> toggleMod(m));
            b.setAccent(m == Modifier.CAMO ? Cyber.lerp(Cyber.CYAN, Color.WHITE, 0.2) : m == Modifier.REGROW ? Cyber.GREEN
                : m == Modifier.INJECTION ? Cyber.MAGENTA : Cyber.YELLOW);
            modBtns[i] = b;
        }
        // ---- quantity + lane
        add(Ui.label(Cyber.spaced("send"), X0 + 14, SEND_Y + 21, F_MICRO, Cyber.alpha(Cyber.CYAN, 200)));
        double qx = X0 + 52;
        for (int i = 0; i < QUANTITIES.length; i++) {
            final int k = i;
            UIButton b = button(qx + i * 44, SEND_Y, 42, 32, "x" + QUANTITIES[i], Cyber.mono(Font.BOLD, 13), () -> { qtyIndex = k; });
            b.setFlat(true);
            qtyBtns[i] = b;
        }
        double lx = qx + QUANTITIES.length * 44 + 8;
        laneBtn = button(lx, SEND_Y, X0 + PAD + INNER - lx, 32, "", Cyber.display(Font.BOLD, 14), this::cycleLane);
        laneBtn.setAccent(Cyber.CYAN);
        laneBtn.setEnabled(game.getMap().getRoutes().size() > 1);

        // ---- exploits
        AttackAbility[] as = AttackAbility.values();
        double ew = (INNER - 2 * GAP) / 3;
        for (int i = 0; i < as.length; i++) {
            AttackAbility a = as[i];
            double ex = X0 + PAD + i * (ew + GAP);
            UIButton b = button(ex, EXPLOIT_Y, ew, 34, a.displayName.toUpperCase(), Cyber.display(Font.BOLD, 15), () -> useExploit(a));
            b.setAccent(Cyber.MAGENTA);
            exploitBtns[i] = b;
            exploitBars[i] = new Cyber.Bar(ex + 2, EXPLOIT_Y + 37, ew - 4, 3, 0).colors(Cyber.MAGENTA, new Color(255, 255, 255, 28), null);
            add(exploitBars[i]);
            exploitMeta[i] = Ui.label("", ex + 2, EXPLOIT_Y + 52, F_MICRO, Cyber.MUTED);
            add(exploitMeta[i]);
        }
        // ---- uplink queue + hint line
        uplink = Ui.label("", X0 + 14, UPLINK_Y + 8, F_MICRO, Cyber.alpha(Cyber.CYAN, 210));
        add(uplink);
        queueBar = new Cyber.Bar(X0 + 150, UPLINK_Y + 1, 110, 6, 0).colors(Cyber.CYAN, new Color(255, 255, 255, 26), null);
        add(queueBar);
        hint = Ui.label("", X0 + 270, UPLINK_Y + 8, F_MICRO, Cyber.GREEN);
        add(hint);
        add(new Cyber.Chamfer(X0 + PAD, INFO_Y, INNER, Ui.H - INFO_Y - 8, 14).fill(new Color(12, 8, 28, 235)).border(Cyber.alpha(Cyber.MAGENTA, 150)).glow(0.4).ticks(true));
        add(info);
        refreshStatic();
    }

    private UIButton button(double x, double y, double w, double h, String text, Font f, Runnable r) {
        UIButton b = new UIButton(x, y, w, h, text, f, r);
        add(b);
        buttons.add(b);
        return b;
    }

    private String trackText() {
        double b = match.getTrackBonus(), s = match.getTrackSpeed();
        int lanes = game.getMap().getRoutes().size();
        String l = lanes + (lanes == 1 ? " LANE" : " LANES");
        if (b <= 1 && s <= 1) return l + "  //  STANDARD TRACK";
        return l + "  //  LONG TRACK: UNITS x" + Ui.fmt(Math.round(s * 100) / 100.0) + " SPEED, COMPUTE x" + Ui.fmt(Math.round(b * 100) / 100.0);
    }

    /** A unit card: click target first, the enemy's own art, short name and price over it, a veil while locked. */
    private Card card(AttackUnit u, double x, double y) {
        UIButton b = button(x, y, CARD_W, CARD_H, "", Cyber.mono(Font.BOLD, 1), () -> send(u));
        b.setAccent(u.isBoss() ? Cyber.RED : u.type.isSortingAlgorithm() ? Cyber.MAGENTA : Cyber.CYAN);
        double box = 46;
        acm.graphics.GImage icon = enemyIcon(u.type, box);
        icon.setLocation(x + 3, y + (CARD_H - box) / 2);
        add(icon);
        String label = shortName(u.type);
        GLabel name = Ui.label(label, x + 50, y + 26, fit(label, Cyber.display(Font.BOLD, 15), CARD_W - 54, 9), Cyber.TEXT);
        add(name);
        GLabel price = Ui.label("", x + 50, y + 46, Cyber.mono(Font.BOLD, 12), Cyber.YELLOW);
        add(price);
        Cyber.Chamfer veil = new Cyber.Chamfer(x + 1, y + 1, CARD_W - 2, CARD_H - 2, 8).scan(false).fill(new Color(6, 4, 16, 165)).border(null);
        add(veil);
        return new Card(u, b, name, price, veil);
    }

    /**
     * The enemy's own sprite, painted once into a clipped square image (2x supersampled): boss sprites carry name banners
     * wider than a card, so drawing them live would spill over the neighbouring cards and the playfield.
     */
    static acm.graphics.GImage enemyIcon(EnemyType t, double box) {
        int px = (int) Math.round(box * 2);
        java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(px, px, java.awt.image.BufferedImage.TYPE_INT_ARGB);
        java.awt.Graphics2D g2 = img.createGraphics();
        try {
            Cyber.quality(g2);
            Path p = new Path("icon", -1, 0, 1, 0);
            Enemy model = t.isBoss() ? new Boss(t, EnumSet.noneOf(Modifier.class), p, 0, 0, 1.0, 1.0) : new Enemy(t, EnumSet.noneOf(Modifier.class), p, 0, 0, 1.0, 1.0);
            EnemySprite sprite = SpriteFactory.create(model);
            sprite.sync(model, 0.4);
            double scale = 2 * Math.min(1.6, box / (t.radius * (t.isBoss() ? 2.0 : 2.2)));
            g2.translate(px / 2.0, px / 2.0);
            g2.scale(scale, scale);
            g2.translate(1, 0);   // the model stands at (-1, 0) on its little path
            sprite.paint(g2);
        } finally {
            g2.dispose();
        }
        acm.graphics.GImage gi = new acm.graphics.GImage(img);
        gi.setSize(box, box);
        return gi;
    }

    /** Card label: the display name, minus the trailing "Sort" family word where space is tight. */
    private static String shortName(EnemyType t) {
        switch (t) {
            case BELLARMINE_COLLEGE_PREP: return "Bellarmine";
            case SW_RESOURCE_CONSULTANT: return "SW Consultant";
            case LOCKHEED_MARTIN: return "Lockheed";
            case SINGLY_LINKED_LIST: return "Singly List";
            case DOUBLY_LINKED_LIST: return "Doubly List";
            case PRIMITIVE_VARIABLE: return "Primitive";
            default: return t.displayName;
        }
    }

    private static Font fit(String text, Font f, double maxWidth, int minSize) {
        GLabel probe = new Cyber.Text(text);
        Font cur = f;
        probe.setFont(cur);
        while (probe.getWidth() > maxWidth && cur.getSize() > minSize) {
            cur = cur.deriveFont((float) (cur.getSize() - 1));
            probe.setFont(cur);
        }
        return cur;
    }

    /** Logical centre of the card of {@code AttackUnit.values()[index]} (for tools and tests that click through the UI). */
    public static double[] cardCenter(int index) {
        return new double[] { X0 + PAD + (index % COLS) * (CARD_W + GAP) + CARD_W / 2, CARD_Y + (index / COLS) * (CARD_H + GAP) + CARD_H / 2 };
    }

    /** Every clickable button of the panel (for hit-testing and hover). */
    public List<UIButton> getButtons() {
        List<UIButton> all = new ArrayList<>(buttons);
        all.addAll(infoButtons);
        return all;
    }

    /** Forces the context box to rebuild on the next frame. */
    public void requestRebuild() { builtKey = ""; }

    // ------------------------------------------------------------------ actions

    private int quantity() { return QUANTITIES[qtyIndex]; }

    /** Buys {@link #quantity()} of the unit with the toggled modifiers on the chosen lane. */
    public void send(AttackUnit u) {
        String why = match.sendProblem(u, mods, 1);
        if (why != null) { showHint(u.type.displayName + ": " + why.toLowerCase(), Cyber.RED); lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.INVALID); return; }   // AUDIO HOOK
        int n = match.send(u, mods, quantity(), lane);
        lastSent = u;
        showHint("SENT " + n + " x " + shortName(u.type).toUpperCase(), Cyber.GREEN);
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
    }

    private void scaleCompute() {
        String why = match.computeProblem();
        if (why != null) { showHint("Compute: " + why.toLowerCase(), Cyber.RED); return; }
        match.scaleCompute();
        showHint("COMPUTE +" + ReverseMatch.COMPUTE_STEP + "/s", Cyber.YELLOW);
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.CASH);   // AUDIO HOOK
    }

    private void useExploit(AttackAbility a) {
        String why = match.abilityProblem(a);
        if (why != null) { showHint(a.displayName + ": " + why.toLowerCase(), Cyber.RED); lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.INVALID); return; }   // AUDIO HOOK
        match.useAbility(a);
        showHint(a.displayName.toUpperCase() + "!", Cyber.MAGENTA);
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.ABILITY);   // AUDIO HOOK
    }

    private void toggleMod(Modifier m) {
        if (!match.isUnlocked(m)) { showHint(m.label + " unlocks at " + ReverseMatch.clock(AttackUnit.modifierUnlockAt(m)), Cyber.RED); return; }
        if (!mods.remove(m)) mods.add(m);
    }

    private void cycleLane() {
        int n = game.getMap().getRoutes().size();
        if (n < 2) return;
        lane = lane + 1 >= n ? -1 : lane + 1;
    }

    private void showHint(String s, Color c) {
        Cyber.setText(hint, s.length() > 34 ? s.substring(0, 33) + "…" : s);
        Cyber.setColor(hint, c);
        hintTime = 2.5;
    }

    /** Reverse-mode hotkeys; returns true if the key was handled. */
    public boolean keyPressed(KeyEvent e) {
        switch (e.getKeyCode()) {
            case KeyEvent.VK_SPACE: if (lastSent != null) send(lastSent); else showHint("Click a unit card first", Cyber.MUTED); return true;
            case KeyEvent.VK_X: qtyIndex = (qtyIndex + 1) % QUANTITIES.length; return true;
            case KeyEvent.VK_L: cycleLane(); return true;
            case KeyEvent.VK_C: scaleCompute(); return true;
            case KeyEvent.VK_Q: useExploit(AttackAbility.OVERCLOCK); return true;
            case KeyEvent.VK_W: useExploit(AttackAbility.HOTFIX); return true;
            case KeyEvent.VK_E: useExploit(AttackAbility.ZERO_DAY); return true;
            default: return false;
        }
    }

    // ------------------------------------------------------------------ per frame

    /** Per-frame update: hover, live labels, enabled states, and the context box when its subject changes. */
    public void update(double dt) {
        refresh -= dt;
        if (hintTime > 0) { hintTime -= dt; if (hintTime <= 0) Cyber.setText(hint, ""); }
        double[] m = screen.getMouseLogical();
        Card hv = null;
        for (Card c : cards) if (c.button.hit(m[0], m[1])) { hv = c; break; }
        if (hv != hovered) { hovered = hv; builtKey = ""; }
        refreshStatic();
        String key = contextKey();
        if (!key.equals(builtKey)) { builtKey = key; rebuildInfo(); refresh = 0.25; screen.refreshHover(); }
        else if (refresh <= 0) { refresh = 0.25; for (Runnable r : dyn) r.run(); }
        if (enemyBar != null && screen.getSelectedEnemy() != null) {
            enemyBar.setValue(screen.getSelectedEnemy().getHpFraction());
            enemyBar.setFill(Cyber.hpColor(screen.getSelectedEnemy().getHpFraction()));
        }
    }

    /** Credits, prices, locks, toggles and cooldowns: cheap label / colour mutations every frame. */
    private void refreshStatic() {
        double cr = match.getCredits();
        Cyber.setText(credits, match.hasUnlimitedCredits() ? "ADMIN ∞" : Ui.money(cr));
        Cyber.setText(income, "+" + (int) Math.round(match.incomeRate()) + "/s");
        income.setLocation(X0 + PAD + INNER - 12 - income.getWidth(), 82);
        String cp = match.computeProblem();
        text(computeBtn, match.getComputeLevel() >= ReverseMatch.COMPUTE_MAX ? "COMPUTE FULLY SCALED"
            : "SCALE COMPUTE  +" + ReverseMatch.COMPUTE_STEP + "/s   " + Ui.money(match.computePrice()) + "   [C]");
        computeBtn.setEnabled(cp == null);
        laneBtn.setEnabled(game.getMap().getRoutes().size() > 1 && game.getState() == Game.State.PLAYING);
        boolean open = game.getState() == Game.State.PLAYING && !match.isUplinkClosed();
        for (Card c : cards) {
            boolean unlocked = match.isUnlocked(c.unit);
            int p = match.price(c.unit, mods, 1);
            boolean ok = unlocked && match.sendProblem(c.unit, mods, 1) == null;
            c.veil.setVisible(!unlocked);
            c.button.setEnabled(unlocked && open);
            c.button.setSelected(c.unit == lastSent && unlocked);
            Cyber.setText(c.price, unlocked ? Ui.money(p) + (quantity() > 1 ? "  x" + quantity() : "") : "AT " + ReverseMatch.clock(c.unit.unlockAt));
            Cyber.setColor(c.price, !unlocked ? Cyber.MUTED : ok ? Cyber.YELLOW : Cyber.RED);
            Cyber.setColor(c.name, unlocked ? (c.unit.isBoss() ? Cyber.lerp(Cyber.RED, Color.WHITE, 0.35) : Cyber.TEXT) : Cyber.DIM);
        }
        Modifier[] ms = Modifier.values();
        for (int i = 0; i < ms.length; i++) {
            boolean un = match.isUnlocked(ms[i]);
            modBtns[i].setEnabled(un && open);
            modBtns[i].setSelected(un && mods.contains(ms[i]));
            text(modBtns[i], un ? ms[i].label.toUpperCase() + "  x" + Ui.fmt(AttackUnit.modifierFactor(ms[i])) : ms[i].label.toUpperCase() + "  " + ReverseMatch.clock(AttackUnit.modifierUnlockAt(ms[i])));
        }
        for (int i = 0; i < qtyBtns.length; i++) qtyBtns[i].setSelected(i == qtyIndex);
        int routes = game.getMap().getRoutes().size();
        text(laneBtn, routes < 2 ? "1 LANE" : lane < 0 ? "LANE: ALL  [L]" : "LANE " + (lane + 1) + " / " + routes + "  [L]");
        AttackAbility[] as = AttackAbility.values();
        for (int i = 0; i < as.length; i++) {
            AttackAbility a = as[i];
            boolean un = match.isUnlocked(a);
            double cd = match.cooldownLeft(a);
            String why = match.abilityProblem(a);
            exploitBtns[i].setEnabled(un && cd <= 0 && open);
            exploitBtns[i].setSelected(a == AttackAbility.OVERCLOCK && match.getOverclockLeft() > 0);
            exploitBars[i].setValue(un ? 1 - cd / a.cooldown : 0);
            exploitBars[i].setFill(cd <= 0 && un ? Cyber.MAGENTA : Cyber.DIM);
            String key = "QWE".substring(i, i + 1);
            String meta = !open ? "OFFLINE" : !un ? "UNLOCKS " + ReverseMatch.clock(a.unlockAt) : cd > 0 ? "RECHARGING " + (int) Math.ceil(cd) + "s" : Ui.money(a.cost) + "  [" + key + "]";
            Cyber.setText(exploitMeta[i], meta);
            Cyber.setColor(exploitMeta[i], !un ? Cyber.DIM : cd > 0 ? Cyber.MUTED : why == null ? Cyber.YELLOW : Cyber.RED);
        }
        int q = match.getQueued();
        Cyber.setText(uplink, match.isUplinkClosed() ? "UPLINK CLOSED" : match.getElapsed() < ReverseMatch.HANDSHAKE
            ? "HANDSHAKE " + ReverseMatch.clock(ReverseMatch.HANDSHAKE - match.getElapsed()) : "UPLINK  " + q + " QUEUED");
        queueBar.setValue(q / (double) ReverseMatch.MAX_QUEUE);
    }

    /** Sets a button's text only when it changes (a set re-measures and repaints the label). */
    private static void text(UIButton b, String s) { if (!s.equals(b.getText())) b.setText(s); }

    // ------------------------------------------------------------------ context box

    private String contextKey() {
        Tower t = screen.getSelectedTower();
        if (hovered != null) return "U" + hovered.unit + mods + qtyIndex + match.isUnlocked(hovered.unit);
        if (t != null && t.isAlive()) return "T" + t.getId() + ":" + t.getTier() + ":" + t.isAbilityLocked();
        if (screen.getSelectedEnemy() != null) return "E" + screen.getSelectedEnemy().getId();
        int n = match.getFeed().size();
        ReverseMatch.FeedEntry last = n == 0 ? null : match.getFeed().get(n - 1);
        return "F" + n + ":" + (last == null ? 0 : System.identityHashCode(last));
    }

    private double y;
    private final double tx = X0 + 22, tw = Ui.PANEL_W - 44;

    private GLabel put(String s, double x, double baseline, Font f, Color c) {
        GLabel l = Ui.label(s, x, baseline, f, c);
        info.add(l);
        return l;
    }

    private void section(String title, Color c) {
        y += 10;
        GLabel l = put(Cyber.spaced("// " + title), tx, y + 9, F_MICRO, Cyber.alpha(c, 230));
        GLine ln = new GLine(tx + l.getWidth() + 8, y + 5.5, tx + tw, y + 5.5);
        ln.setColor(Cyber.alpha(c, 70));
        info.add(ln);
        y += 13;
    }

    private void para(String s, Font f, Color c, int maxLines) {
        int n = 0;
        for (String l : Ui.wrap(s, f, tw)) {
            if (maxLines > 0 && n++ >= maxLines) break;
            y += f.getSize() + 4;
            put(l, tx, y, f, c);
        }
    }

    private void statCell(double cx, double cy, String label, Supplier<String> val, Color vc) {
        put(Cyber.spaced(label), cx, cy + 9, F_MICRO, Cyber.alpha(Cyber.CYAN, 190));
        GLabel v = put(val.get(), cx, cy + 26, F_VAL, vc);
        dyn.add(() -> Cyber.setText(v, val.get()));
    }

    private void rebuildInfo() {
        info.removeAll();
        infoButtons.clear();
        dyn.clear();
        enemyBar = null;
        y = INFO_Y + 4;
        Tower t = screen.getSelectedTower();
        if (hovered != null) buildUnitInfo(hovered.unit);
        else if (t != null && t.isAlive()) buildTowerInfo(t);
        else if (screen.getSelectedEnemy() != null) buildEnemyInfo(screen.getSelectedEnemy());
        else buildFeed();
    }

    private void header(String name, Color col, String badge, Color badgeCol) {
        y += 26;
        Font nf = fit(name, Cyber.display(Font.BOLD, 22), tw - 110, 12);
        put(name, tx, y, nf, col);
        if (badge != null) {
            GLabel b = Ui.label(badge, 0, 0, Cyber.mono(Font.BOLD, 10), badgeCol);
            double bw = b.getWidth() + 14, bx = tx + tw - bw;
            info.add(new Cyber.Chamfer(bx, y - 14, bw, 18, 5).scan(false).fill(Cyber.alpha(badgeCol, 40)).border(badgeCol));
            b.setLocation(bx + 7, y - 1);
            info.add(b);
        }
    }

    /** The hovered unit card: what it is, what it costs with the toggled modifiers, what the AI earns if it dies. */
    private void buildUnitInfo(AttackUnit u) {
        EnemyType t = u.type;
        header(t.displayName, u.isBoss() ? Cyber.lerp(Cyber.RED, Color.WHITE, 0.3) : Cyber.TEXT,
            u.isBoss() ? t.getBossClass().label + "-CLASS" : t.isSortingAlgorithm() ? "SORTER" : "DATA", u.isBoss() ? Cyber.RED : Cyber.MAGENTA);
        para(u.blurb, F_TXT, Cyber.MUTED, 2);
        EnumSet<Modifier> eff = match.effectiveModifiers(u, mods);
        // the difficulty scales unit health; whole HP, rounded the way Enemy does
        long hp = Math.max(1, Math.round(t.baseHp * match.unitHpScale(t))) * (eff.contains(Modifier.FORTIFIED) ? 2 : 1);
        y += 6;
        double cw = tw / 3;
        statCell(tx, y, "health", () -> Cyber.commas(hp), Cyber.TEXT);
        statCell(tx + cw, y, "speed", () -> Ui.fmt(Math.round(t.speed * match.getTrackSpeed() * 100) / 100.0) + "x", Cyber.TEXT);
        statCell(tx + 2 * cw, y, "integrity", () -> String.valueOf(t.lives), Cyber.RED);
        y += 38;
        statCell(tx, y, "price", () -> Ui.money(match.price(u, mods, 1)), Cyber.YELLOW);
        statCell(tx + cw, y, "ai bounty", () -> Ui.money(t.reward * ReverseMatch.KILL_REWARD_SCALE), Cyber.GREEN);
        statCell(tx + 2 * cw, y, "leak pays", () -> "+" + t.lives * ReverseMatch.LEAK_BONUS_PER_LIFE, Cyber.CYAN);
        y += 34;
        String m = eff.isEmpty() ? (u.acceptsModifiers() ? "no modifiers (toggle them below the cards)" : "carries no modifiers") : "with " + modsText(eff);
        if (!match.isUnlocked(u)) m = "unlocks at " + ReverseMatch.clock(u.unlockAt) + " (in " + ReverseMatch.clock(match.unlocksIn(u)) + ")";
        para(m, F_TXT, match.isUnlocked(u) ? Cyber.alpha(Cyber.CYAN, 230) : Cyber.YELLOW, 2);
        if (t.hasChildren()) {
            StringBuilder sb = new StringBuilder("Releases ");
            EnemyType[] ch = t.getChildTypes(); int[] n = t.getChildCounts();
            for (int i = 0; i < ch.length; i++) { if (i > 0) sb.append(" + "); sb.append(n[i]).append(" x ").append(ch[i].displayName); }
            para(sb.append(" when destroyed.").toString(), F_TXT, Cyber.MUTED, 2);
        }
    }

    private static String modsText(EnumSet<Modifier> m) {
        List<String> l = new ArrayList<>();
        for (Modifier x : m) l.add(x.label);
        return String.join(" + ", l);
    }

    /** A selected tower, read-only: the AI owns it. */
    private void buildTowerInfo(Tower t) {
        lindefense.tower.TowerDef d = t.getDef();
        header(t.getType().displayName, Cyber.lerp(Ui.c(t.getType().primaryRgb), Color.WHITE, 0.35), "AI  T" + t.getTier() + "/" + t.getMaxTier(), Cyber.CYAN);
        para(t.getTierLabel() + "  //  " + d.subtitle, F_TXT, Cyber.MUTED, 1);
        y += 6;
        double cw = tw / 3;
        statCell(tx, y, "kills", () -> Cyber.commas(t.getKills()), Cyber.TEXT);
        statCell(tx + cw, y, "damage", () -> Cyber.abbrev(t.getDamageDealt()), Cyber.TEXT);
        statCell(tx + 2 * cw, y, "invested", () -> Ui.money(t.getInvestedCost()), Cyber.YELLOW);
        y += 38;
        statCell(tx, y, "targeting", () -> t.getTargeting().label.toUpperCase(), Cyber.CYAN);
        statCell(tx + cw, y, "range", () -> String.valueOf((int) t.effectiveRange(game)), Cyber.TEXT);
        statCell(tx + 2 * cw, y, "status", () -> t.isSurveilled() ? "JAMMED " + (int) Math.ceil(t.getSurveilledRemaining()) + "s" : "ONLINE", t.isSurveilled() ? Cyber.RED : Cyber.GREEN);
        y += 34;
        String ab;
        if (d.ability == null) ab = t.getType().isHero() ? "Hero: passive, no active ability." : "No ability.";
        else if (t.isAbilityLocked()) ab = "Ability " + d.ability.name + ": locked (the AI can buy it for " + Ui.money(TowerCatalog.ABILITY_UNLOCK_COST) + " at max tier).";
        else ab = "Ability " + d.ability.name + ": UNLOCKED. Jam the tower with Zero-Day to lock it.";
        para(ab, F_TXT, t.isAbilityLocked() || d.ability == null ? Cyber.MUTED : Cyber.MAGENTA, 3);
        y += 4;
        para("Read-only: the defender AI controls this tower. Right-click to deselect.", Cyber.body(Font.PLAIN, 11), Cyber.DIM, 2);
    }

    private void buildEnemyInfo(Enemy e) {
        header(e.getType().displayName, e.isBoss() ? Cyber.RED : Cyber.TEXT, "YOURS", Cyber.MAGENTA);
        y += 10;
        enemyBar = new Cyber.Bar(tx, y, tw, 8, 2).colors(Cyber.hpColor(e.getHpFraction()), new Color(255, 255, 255, 30), null);
        enemyBar.setValue(e.getHpFraction());
        info.add(enemyBar);
        y += 14;
        double cw = tw / 3;
        statCell(tx, y, "hp", () -> Cyber.commas((long) Math.ceil(Math.max(0, e.getHp()))) + " / " + Cyber.commas((long) e.getMaxHp()), Cyber.TEXT);
        statCell(tx + 2 * cw, y, "integrity", () -> String.valueOf(e.getType().lives), Cyber.RED);
        y += 38;
        statCell(tx, y, "progress", () -> (int) Math.round(100 * e.getDistance() / e.getRoute().getTotalLength()) + "%", Cyber.CYAN);
        statCell(tx + cw, y, "speed", () -> Ui.fmt(Math.round(e.speedMultiplier() * 100) / 100.0) + "x", Cyber.TEXT);
        statCell(tx + 2 * cw, y, "lane", () -> String.valueOf(e.getRouteIndex() + 1), Cyber.TEXT);
        y += 34;
        para(e.getModifiers().isEmpty() ? "No modifiers." : "Modifiers: " + modsText(e.getModifiers()), F_TXT, Cyber.MUTED, 1);
        para(e.getType().description, F_TXT, Cyber.MUTED, 3);
    }

    /** The defender AI's latest actions and the match's events, newest first. */
    private void buildFeed() {
        y += 6;
        String prof = match.getProfile().displayName.toUpperCase();
        put(Cyber.spaced("// defender ai: " + prof), tx, y + 9, F_MICRO, Cyber.alpha(Cyber.MAGENTA, 230));
        GLabel cash = put("", 0, y + 9, F_MICRO, Cyber.YELLOW);
        dyn.add(() -> { Cyber.setText(cash, "AI CASH " + Ui.money(game.getCash()) + "   TOWERS " + game.getTowerManager().getPlayerTowers().size());
            cash.setLocation(tx + tw - cash.getWidth(), cash.getY()); });
        dyn.get(0).run();
        y += 18;
        List<ReverseMatch.FeedEntry> f = match.getFeed();
        Font ff = Cyber.body(Font.PLAIN, 12);
        int lines = 0;
        for (int i = f.size() - 1; i >= 0 && lines < 10; i--) {
            ReverseMatch.FeedEntry e = f.get(i);
            y += 17;
            put(ReverseMatch.clock(e.time), tx, y, Cyber.mono(Font.BOLD, 10), Cyber.DIM);
            String s = e.text;
            GLabel l = put(s, tx + 40, y, ff, Ui.c(e.rgb));
            while (l.getWidth() > tw - 40 && s.length() > 4) { s = s.substring(0, s.length() - 2); l.setLabel(s + "…"); }
            lines++;
        }
        if (f.isEmpty()) { y += 18; put("The AI is setting up. Click a unit card to send it.", ff, Cyber.MUTED); }
    }

    private void put(String s, Font f, Color c) { put(s, tx, y, f, c); }

    // ------------------------------------------------------------------ end screen texts

    /** Title, micro label, subtitle and accent of the reverse-mode end screen ({title, micro, sub, "win"|"loss"}). */
    static String[] endTexts(Game g) {
        ReverseMatch r = g.getReverse();
        String map = g.getMap().getName(), ai = r.getProfile().displayName;
        if (r.attackerWon()) return new String[] { "BREACH", "// adversary wins",
            "You broke the " + ai + " defender AI on " + map + " in " + ReverseMatch.clock(r.getElapsed()) + ". Its integrity hit zero.", "win" };
        return new String[] { "CONTAINED", "// defender holds",
            "The " + ai + " AI survived the " + ReverseMatch.clock(ReverseMatch.DURATION) + " training run on " + map + " with " + g.getLives() + " integrity left.", "loss" };
    }

    /** The four end-screen stat chips: {label, value, accent}. */
    static String[][] endStats(Game g) {
        ReverseMatch r = g.getReverse();
        return new String[][] {
            { "time", ReverseMatch.clock(r.getElapsed()), "" },
            { "units sent", Cyber.commas(r.getUnitsBought()), "" },
            { "credits spent", Ui.money(r.getCreditsSpent()), "y" },
            { "integrity taken", String.valueOf(Math.max(0, g.getMaxLives() - g.getLives())), "r" } };
    }
}
