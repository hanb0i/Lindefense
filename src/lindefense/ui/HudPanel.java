package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import acm.graphics.GRect;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import lindefense.sim.Game;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;

/**
 * Top HUD (stat chips, speed / pause controls, Start Wave), bottom status strip (map name, event text,
 * next-wave preview) and the notification toast (wave start / boss glitch banners, wave-complete toast).
 * Everything is built once; {@link #update(double)} only mutates labels, colours and positions.
 */
public final class HudPanel extends GCompound {
    private static final long serialVersionUID = 1L;

    private static final Font CHIP_LABEL = Cyber.mono(Font.BOLD, 9);
    private static final Font CHIP_VALUE = Cyber.mono(Font.BOLD, 16);
    private static final double CHIP_Y = 5, CHIP_H = 38;

    /** A stat chip: icon, micro-label and value inside a small chamfered frame. */
    private static final class Chip extends GCompound {
        private static final long serialVersionUID = 1L;
        final Cyber.Chamfer frame;
        final Cyber.Icon icon;
        final GLabel micro, value;
        final double width;
        Color accent;

        Chip(double x, double w, Cyber.Kind kind, String label, Color accent) {
            this.width = w; this.accent = accent;
            frame = new Cyber.Chamfer(0, 0, w, CHIP_H, 8).scan(false).fill(new Color(7, 12, 28, 235)).border(Cyber.alpha(accent, 150));
            add(frame);
            icon = new Cyber.Icon(kind, 16, accent);
            icon.setLocation(9, (CHIP_H - 16) / 2);
            add(icon);
            micro = Ui.label(Cyber.spaced(label), 32, 14, CHIP_LABEL, Cyber.alpha(accent, 190));
            add(micro);
            value = Ui.label("", 32, 32, CHIP_VALUE, Cyber.TEXT);
            add(value);
            setLocation(x, CHIP_Y);
        }

        void set(String v, Color c) {
            Cyber.setText(value, v);
            Cyber.setColor(value, c);
        }
    }

    private final GameScreen screen;
    private final Game game;
    private final List<UIButton> buttons = new ArrayList<>();
    private final Chip cashChip, livesChip, waveChip, enemyChip;
    private final Cyber.Bar waveBar;
    private final UIButton pauseBtn, s1, s2, s3, startBtn, autoBtn, menuBtn, heroBtn;
    private final Cyber.Chamfer speedFrame;

    // bottom strip
    private final GLabel mapMicro, mapName, eventLabel, noteLabel, nextMicro, nextLine;
    private final Cyber.Chamfer bossTag;
    private final GLabel bossTagLabel;

    // toast
    private final GCompound toast = new GCompound();
    private final Cyber.Chamfer toastFrame;
    private final GRect toastStripe;
    private final GLabel toastMicro;
    private final Cyber.GlitchText toastText;
    private final GRect[] toastSlices = new GRect[3];
    private String toastShown = "";
    private double toastAge, toastFade;
    private boolean toastLive;
    private boolean toastSpecial;
    private Color toastColor = Cyber.CYAN;
    private double toastW;

    private String bannerText; private Color bannerColor; private double bannerTime;
    /** Reverse mode: the attacker controller and the chips that replace Start Wave / Auto / Heroes (null otherwise). */
    private final lindefense.ai.ReverseMatch rev;
    private Chip timerChip, aiChip;
    private int lastLives = -1;
    private double lifeFlash, time;
    private final java.util.Random rnd = new java.util.Random(11);

    public HudPanel(GameScreen screen) {
        this.screen = screen;
        this.game = screen.getGame();

        // ---- top bar backdrop
        add(Ui.rect(0, 0, Ui.WORLD_W, Ui.TOP_H, new Color(5, 9, 22), new Color(5, 9, 22)));
        for (int y = 2; y < Ui.TOP_H; y += 3) { GLine l = new GLine(0, y + 0.5, Ui.WORLD_W, y + 0.5); l.setColor(new Color(0, 0, 0, 60)); add(l); }
        GLine edge = new GLine(0, Ui.TOP_H - 0.5, Ui.WORLD_W, Ui.TOP_H - 0.5);
        edge.setColor(Cyber.alpha(Cyber.CYAN, 150));
        add(edge);
        GLine edge2 = new GLine(0, Ui.TOP_H + 0.5, 220, Ui.TOP_H + 0.5);
        edge2.setColor(Cyber.alpha(Cyber.MAGENTA, 170));
        add(edge2);

        cashChip = new Chip(8, 124, Cyber.Kind.CASH, "credits", Cyber.YELLOW);
        livesChip = new Chip(138, 104, Cyber.Kind.HEART, "integrity", Cyber.RED);
        waveChip = new Chip(248, 124, Cyber.Kind.WAVE, "wave", Cyber.CYAN);
        enemyChip = new Chip(378, 198, Cyber.Kind.ENEMY, "hostiles", Cyber.MAGENTA);
        for (Chip c : new Chip[] { cashChip, livesChip, waveChip, enemyChip }) add(c);
        waveBar = new Cyber.Bar(34, CHIP_H - 5, 124 - 34 - 8, 2, 0).colors(Cyber.CYAN, new Color(255, 255, 255, 30), null);
        waveChip.add(waveBar);

        double cx = 586;
        pauseBtn = btn(cx, 6, 38, 36, "", () -> screen.togglePause());
        pauseBtn.setIcon(Cyber.Kind.PAUSE);
        cx += 46;
        speedFrame = new Cyber.Chamfer(cx, 6, 3 * 38 + 4, 36, 8).scan(false).fill(new Color(7, 12, 28, 235)).border(Cyber.alpha(Cyber.CYAN, 120));
        add(speedFrame);
        s1 = seg(cx + 2, "1x", 1);
        s2 = seg(cx + 2 + 38, "2x", 2);
        s3 = seg(cx + 2 + 76, "3x", 3);
        cx += 3 * 38 + 4 + 10;
        startBtn = btn(cx, 6, 176, 36, "START WAVE 1", () -> screen.startWave());
        startBtn.setPrimary(true);
        startBtn.setIcon(Cyber.Kind.PLAY);
        cx += 176 + 8;
        autoBtn = btn(cx, 6, 78, 36, "AUTO", () -> screen.toggleAuto());
        autoBtn.setIcon(Cyber.Kind.AUTO);
        autoBtn.setAccent(Cyber.MAGENTA);
        cx += 78 + 6;
        menuBtn = btn(cx, 6, 72, 36, "MENU", () -> screen.openMenu());
        menuBtn.setIcon(Cyber.Kind.MENU);
        cx += 72 + 6;
        heroBtn = btn(cx, 6, Ui.WORLD_W - 6 - cx, 36, "HEROES", () -> screen.toggleHeroStore());
        heroBtn.setAccent(Cyber.YELLOW);

        // ---- bottom strip
        add(Ui.rect(0, Ui.BOTTOM_Y, Ui.WORLD_W, Ui.H - Ui.BOTTOM_Y, new Color(5, 9, 22), new Color(5, 9, 22)));
        for (int y = Ui.BOTTOM_Y + 2; y < Ui.H; y += 3) { GLine l = new GLine(0, y + 0.5, Ui.WORLD_W, y + 0.5); l.setColor(new Color(0, 0, 0, 60)); add(l); }
        GLine bedge = new GLine(0, Ui.BOTTOM_Y + 0.5, Ui.WORLD_W, Ui.BOTTOM_Y + 0.5);
        bedge.setColor(Cyber.alpha(Cyber.CYAN, 150));
        add(bedge);
        GLine bedge2 = new GLine(Ui.WORLD_W - 220, Ui.BOTTOM_Y - 0.5, Ui.WORLD_W, Ui.BOTTOM_Y - 0.5);
        bedge2.setColor(Cyber.alpha(Cyber.MAGENTA, 170));
        add(bedge2);
        double by = Ui.BOTTOM_Y;
        mapMicro = Ui.label(Cyber.spaced("sector") + "   //   MODE " + DifficultySelector.display(game.getDifficulty(), CHIP_LABEL), 18, by + 18, CHIP_LABEL, Cyber.alpha(Cyber.CYAN, 200));   // DIFFICULTY HOOK: mode in HUD
        mapName = Ui.label(game.getMap().getName().toUpperCase(), 18, by + 40, Cyber.display(Font.BOLD, 20), Cyber.TEXT);
        add(mapMicro); add(mapName);
        eventLabel = Ui.label("", 0, by + 22, Cyber.mono(Font.BOLD, 13), Cyber.MAGENTA);
        noteLabel = Ui.label("", 0, by + 41, Cyber.body(Font.PLAIN, 13), Cyber.MUTED);
        add(eventLabel); add(noteLabel);
        nextMicro = Ui.label("", 0, by + 18, CHIP_LABEL, Cyber.alpha(Cyber.CYAN, 200));
        nextLine = Ui.label("", 0, by + 40, Cyber.display(Font.BOLD, 17), Cyber.TEXT);
        add(nextMicro); add(nextLine);
        bossTag = new Cyber.Chamfer(0, by + 26, 60, 18, 5).scan(false).fill(Cyber.alpha(Cyber.RED, 50)).border(Cyber.RED);
        bossTagLabel = Ui.label("BOSS", 0, by + 39, Cyber.mono(Font.BOLD, 11), Cyber.RED);
        bossTag.setVisible(false); bossTagLabel.setVisible(false);
        add(bossTag); add(bossTagLabel);

        // ---- toast
        toastFrame = new Cyber.Chamfer(0, 0, 400, 56, 12).scan(true).fill(new Color(6, 10, 24, 238)).glow(1).lineWidth(1.8);
        toast.add(toastFrame);
        toastStripe = Ui.rect(0, 0, 5, 56, Cyber.CYAN, Cyber.CYAN);
        toast.add(toastStripe);
        toastMicro = Ui.label("", 22, 17, Cyber.mono(Font.BOLD, 10), Cyber.CYAN);
        toast.add(toastMicro);
        toastText = new Cyber.GlitchText("", Cyber.display(Font.BOLD, 26), Cyber.TEXT);
        toastText.setLocation(22, 44);
        toast.add(toastText);
        for (int i = 0; i < toastSlices.length; i++) {
            toastSlices[i] = Ui.rect(0, 0, 10, 2, Cyber.CYAN, Cyber.CYAN);
            toastSlices[i].setVisible(false);
            toast.add(toastSlices[i]);
        }
        toast.setVisible(false);
        add(toast);
        rev = game.getReverse();
        if (rev != null) buildReverse();   // REVERSE HOOK
    }

    // ------------------------------------------------------------------ reverse mode ("Adversarial Training")
    /** The attacker's HUD: compute credits, the AI's integrity, the epoch, the training-run timer and the AI's cash. */
    private void buildReverse() {
        Cyber.setText(cashChip.micro, Cyber.spaced("compute"));
        Cyber.setText(livesChip.micro, Cyber.spaced("ai integrity"));
        Cyber.setText(waveChip.micro, Cyber.spaced("epoch"));
        startBtn.setVisible(false);
        autoBtn.setVisible(false);
        heroBtn.setVisible(false);
        double tx = startBtn.getX(), tw = autoBtn.getX() + autoBtn.getW() - tx;
        timerChip = new Chip(tx, tw, Cyber.Kind.FAST, "training run", Cyber.MAGENTA);
        add(timerChip);
        aiChip = new Chip(heroBtn.getX(), heroBtn.getW(), Cyber.Kind.CASH, "ai cash", Cyber.YELLOW);
        aiChip.icon.setVisible(false);
        aiChip.micro.setLocation(9, aiChip.micro.getY());
        aiChip.value.setLocation(9, aiChip.value.getY());
        add(aiChip);
        Cyber.setText(mapMicro, Cyber.spaced("sector") + "   //   ADVERSARIAL TRAINING   //   AI " + DifficultySelector.display(rev.getLevel(), CHIP_LABEL)
            + " " + rev.getProfile().displayName.toUpperCase());
        bossTag.setVisible(false);
        bossTagLabel.setVisible(false);
    }

    /** Per-frame reverse-mode chips and bottom strip (the AI's latest action, the next unlock). */
    private void updateReverse() {
        cashChip.set(rev.hasUnlimitedCredits() ? "ADMIN \u221e" : compactMoney(rev.getCredits()), Cyber.YELLOW);
        waveChip.set(rev.getEpoch() + " / " + lindefense.ai.ReverseMatch.EPOCHS, Cyber.TEXT);
        waveBar.setValue(Math.min(1, rev.getElapsed() / lindefense.ai.ReverseMatch.DURATION));
        int alive = game.getEnemyManager().getAliveCount(), queued = rev.getQueued();
        enemyChip.set(alive + " / " + (alive + queued), alive + queued > 0 ? Cyber.TEXT : Cyber.MUTED);
        boolean closing = !rev.isUplinkClosed() && rev.getTimeLeft() <= 60;
        double pulse = closing ? 0.5 + 0.5 * Math.sin(time * 6) : 0;
        if (rev.isUplinkClosed()) timerChip.set("OVERTIME  " + lindefense.ai.ReverseMatch.clock(rev.getOvertimeLeft()), Cyber.YELLOW);
        else timerChip.set(lindefense.ai.ReverseMatch.clock(rev.getTimeLeft()) + "  LEFT", closing ? Cyber.lerp(Cyber.MAGENTA, Color.WHITE, pulse * 0.5) : Cyber.TEXT);
        timerChip.frame.glow(closing ? 0.3 + 0.6 * pulse : 0);
        aiChip.set(compactMoney(game.getCash()), Cyber.YELLOW);
        // bottom strip: map event / the AI's last action in the centre, the next unlock on the right
        double cxEvent = Ui.WORLD_W / 2.0;
        String ev = game.getMap().getEventText();
        Cyber.setText(eventLabel, ev == null ? "" : ev);
        eventLabel.setLocation(cxEvent - eventLabel.getWidth() / 2, eventLabel.getY());
        lindefense.ai.ReverseMatch.FeedEntry last = rev.getLastAiAction();
        Cyber.setText(noteLabel, last == null ? "THE DEFENDER AI IS ONLINE" : last.text.toUpperCase());
        Cyber.setColor(noteLabel, last == null ? Cyber.MUTED : Cyber.lerp(Ui.c(last.rgb), Cyber.TEXT, 0.25));
        noteLabel.setLocation(cxEvent - noteLabel.getWidth() / 2, ev == null || ev.isEmpty() ? Ui.BOTTOM_Y + 32 : Ui.BOTTOM_Y + 41);
        double next = Double.MAX_VALUE;
        List<String> names = new ArrayList<>();
        double now = rev.getElapsed();
        for (lindefense.ai.AttackUnit u : lindefense.ai.AttackUnit.values()) if (u.unlockAt > now) next = Math.min(next, u.unlockAt);
        for (lindefense.enemy.Modifier m : lindefense.enemy.Modifier.values()) if (lindefense.ai.AttackUnit.modifierUnlockAt(m) > now) next = Math.min(next, lindefense.ai.AttackUnit.modifierUnlockAt(m));
        for (lindefense.ai.AttackUnit u : lindefense.ai.AttackUnit.values()) if (u.unlockAt == next) names.add(u.type.displayName);
        for (lindefense.enemy.Modifier m : lindefense.enemy.Modifier.values()) if (lindefense.ai.AttackUnit.modifierUnlockAt(m) == next) names.add(m.label);
        String micro, line;
        if (next == Double.MAX_VALUE) { micro = "uplink"; line = rev.isUplinkClosed() ? "closed" : "everything unlocked"; }
        else { micro = "next unlock // " + lindefense.ai.ReverseMatch.clock(next); line = names.get(0) + (names.size() > 1 ? "  +" + (names.size() - 1) : ""); }
        Cyber.setText(nextMicro, Cyber.spaced(micro));
        Cyber.setText(nextLine, line);
        double right = Ui.WORLD_W - 18;
        nextLine.setLocation(right - nextLine.getWidth(), nextLine.getY());
        nextMicro.setLocation(right - nextMicro.getWidth(), nextMicro.getY());
    }

    private UIButton btn(double x, double y, double w, double h, String text, Runnable r) {
        UIButton b = new UIButton(x, y, w, h, text, Cyber.display(Font.BOLD, 16), r);
        buttons.add(b);
        add(b);
        return b;
    }

    private UIButton seg(double x, String text, int speed) {
        UIButton b = new UIButton(x, 8, 38, 32, text, Cyber.mono(Font.BOLD, 14), () -> screen.setSpeed(speed));
        b.setFlat(true);
        buttons.add(b);
        add(b);
        return b;
    }

    public List<UIButton> getButtons() { return buttons; }

    public void flashBanner(String text, Color col, double seconds) {
        bannerText = text; bannerColor = col; bannerTime = seconds;
    }

    // ------------------------------------------------------------------ per frame
    public void update(double dt) {
        time += dt;
        int w = game.getWave();
        int alive = game.getEnemyManager().getAliveCount();
        int toSpawn = game.getWaveManager().getRemainingToSpawn();

        cashChip.set(game.hasAdminMoney() ? "ADMIN \u221e" : compactMoney(game.getCash()), Cyber.YELLOW);
        // lives: red pulse when low, flash on loss
        int lv = game.getLives();
        if (lastLives >= 0 && lv < lastLives) lifeFlash = 0.6;
        lastLives = lv;
        lifeFlash = Math.max(0, lifeFlash - dt);
        boolean low = lv <= 25;
        double pulse = low ? 0.5 + 0.5 * Math.sin(time * 7) : 0;
        Color lc = Cyber.lerp(Cyber.RED, Color.WHITE, Math.max(lifeFlash / 0.6 * 0.7, low ? pulse * 0.35 : 0));
        livesChip.set(Cyber.commas(lv), lc);
        livesChip.frame.border(Cyber.alpha(Cyber.RED, (int) (150 + 105 * pulse))).glow(low ? 0.4 + 0.8 * pulse : lifeFlash > 0 ? 1 : 0)
            .fill(low ? new Color(40 + (int) (40 * pulse), 8, 16, 235) : new Color(7, 12, 28, 235));

        waveChip.set(w + " / " + WaveData.WAVE_COUNT, Cyber.TEXT);
        waveBar.setValue(w / (double) WaveData.WAVE_COUNT);
        // hostiles: alive on the field / total still to beat this wave (alive + not yet spawned)
        enemyChip.set(alive + " / " + (alive + toSpawn), alive > 0 || toSpawn > 0 ? Cyber.TEXT : Cyber.MUTED);

        boolean paused = game.isPaused();
        pauseBtn.setSelected(paused);
        pauseBtn.setIcon(paused ? Cyber.Kind.PLAY : Cyber.Kind.PAUSE);
        s1.setSelected(game.getSpeed() == 1 && !paused);
        s2.setSelected(game.getSpeed() == 2 && !paused);
        s3.setSelected(game.getSpeed() == 3 && !paused);
        boolean canStart = game.getWaveManager().canStartNextWave() && game.getState() == Game.State.PLAYING;
        startBtn.setEnabled(canStart);
        startBtn.setPulse(canStart && !game.getWaveManager().isWaveActive() ? 0.35 : 0);
        if (canStart) {
            String t = "START WAVE " + (w + 1);
            if (game.getWaveManager().isAutoStart() && w > 0) t += String.format("  (%.0f)", Math.ceil(game.getWaveManager().getPrepTimer()));
            startBtn.setText(t);
            startBtn.setIcon(Cyber.Kind.PLAY);
        } else {
            startBtn.setText(game.getVariance().isDraftPending() ? "PICK A PATCH" : w >= WaveData.WAVE_COUNT ? "FINAL WAVE" : "WAVE " + w + " LIVE");   // PATCH NOTES
            startBtn.setIcon(null);
        }
        autoBtn.setSelected(game.getWaveManager().isAutoStart());
        heroBtn.setSelected(screen.isHeroStoreOpen());

        if (rev != null) updateReverse(); else updateStrip(w);   // REVERSE HOOK
        updateToast(dt);
    }

    private void updateStrip(int w) {
        double cxEvent = Ui.WORLD_W / 2.0;
        String ev = game.getMap().getEventText();
        WaveDef def = game.getWaveManager().getCurrentDef();
        String note;
        if (game.getWaveManager().isWaveActive() && def != null && def.note != null) note = "WAVE " + def.number + ": " + def.note;
        else note = "";
        Cyber.setText(eventLabel, ev == null ? "" : ev);
        eventLabel.setLocation(cxEvent - eventLabel.getWidth() / 2, eventLabel.getY());
        Cyber.setText(noteLabel, note);
        noteLabel.setLocation(cxEvent - noteLabel.getWidth() / 2, noteLabel.getY());
        if (ev == null || ev.isEmpty()) {
            noteLabel.setLocation(noteLabel.getX(), Ui.BOTTOM_Y + 32);
        } else {
            noteLabel.setLocation(noteLabel.getX(), Ui.BOTTOM_Y + 41);
        }
        // next-wave preview, right aligned
        double right = Ui.WORLD_W - 18;
        boolean boss = false;
        String line, micro;
        if (w < WaveData.WAVE_COUNT && !game.getWaveManager().isWaveActive()) {
            WaveDef next = WaveData.get(w + 1);
            micro = "next // wave " + (w + 1);
            line = Ui.shapedUnits(game, w + 1) + " units";   // after Difficulty Growth shaping
            boss = next.containsBoss();
        } else if (def != null && game.getWaveManager().isWaveActive()) {
            micro = "live // wave " + def.number;
            line = Ui.shapedUnits(game, def.number) + " units";
            boss = def.containsBoss();
        } else { micro = "final"; line = "stand firm"; }
        Cyber.setText(nextMicro, Cyber.spaced(micro));
        Cyber.setText(nextLine, line);
        double lw = nextLine.getWidth();
        nextLine.setLocation(right - lw, nextLine.getY());
        nextMicro.setLocation(right - nextMicro.getWidth(), nextMicro.getY());
        bossTag.setVisible(boss); bossTagLabel.setVisible(boss);
        if (boss) {
            double bx = right - lw - 12 - 54;
            bossTag.setLocation(bx, Ui.BOTTOM_Y + 25);
            bossTag.size(54, 20);
            bossTagLabel.setLocation(bx + (54 - bossTagLabel.getWidth()) / 2, Ui.BOTTOM_Y + 39);
        }
        // pre-wave notes
        if (!game.getWaveManager().isWaveActive() && w < WaveData.WAVE_COUNT) {
            WaveDef next = WaveData.get(w + 1);
            if (next.note != null) {
                Cyber.setText(noteLabel, next.note);
                noteLabel.setLocation(cxEvent - noteLabel.getWidth() / 2, noteLabel.getY());
            }
        }
    }

    // ------------------------------------------------------------------ toast
    private void updateToast(double dt) {
        if (bannerTime > 0) bannerTime -= dt;
        String gb = game.getBanner();
        String text = null; Color col = null;
        if (bannerTime > 0 && bannerText != null) { text = bannerText; col = bannerColor; }
        else if (gb != null) { text = gb; col = Ui.c(game.getBannerRgb()); }
        if (text != null && (!text.equals(toastShown) || !toastLive)) {
            showToast(text, col);
        } else if (text == null && toastLive) {
            toastLive = false;
        }
        double target = toastLive ? 1 : 0;
        toastFade += (target - toastFade) * Math.min(1, dt * (toastLive ? 14 : 7));
        toastAge += dt;
        if (toastFade < 0.01 && !toastLive) { toast.setVisible(false); return; }
        toast.setVisible(true);
        double slide = (1 - toastFade) * -14;
        toast.setLocation((Ui.WORLD_W - toastW) / 2, 168 + slide);
        float a = (float) Math.max(0, Math.min(1, toastFade));
        toastFrame.alpha(a);
        toastStripe.setFillColor(Cyber.alpha(toastColor, (int) (255 * a)));
        toastStripe.setColor(toastStripe.getFillColor());
        Cyber.setColor(toastMicro, Cyber.alpha(toastColor, (int) (220 * a)));
        toastText.setAlphaFactor(a);
        toastText.animate(dt);
        boolean glitch = toastSpecial && toastAge < 0.45;
        for (GRect s : toastSlices) {
            s.setVisible(glitch);
            if (glitch) {
                s.setBounds(rnd.nextDouble() * (toastW - 120), 6 + rnd.nextDouble() * 44, 40 + rnd.nextDouble() * 120, 1 + rnd.nextDouble() * 3);
                s.setFillColor(Cyber.alpha(rnd.nextBoolean() ? Cyber.CYAN : Cyber.MAGENTA, 150));
                s.setColor(s.getFillColor());
            }
        }
    }

    private void showToast(String text, Color col) {
        toastShown = text;
        toastLive = true;
        toastAge = 0;
        String lower = text.toLowerCase();
        boolean complete = lower.contains("complete");
        boolean boss = lower.contains("boss") || lower.contains("palantir") || lower.contains("entered the track") || lower.contains("surveillance") || lower.contains("phase");
        boolean start = lower.startsWith("wave") && !complete;
        toastSpecial = boss || start;
        toastColor = boss ? (lower.contains("blocked") ? Cyber.GREEN : Cyber.RED) : complete ? Cyber.GREEN : start ? Cyber.CYAN : col;
        if (lower.contains("destroyed")) toastColor = Cyber.YELLOW;
        String micro = complete ? "// wave clear" : boss ? "// warning" : start ? "// incoming" : "// system";
        Cyber.setText(toastMicro, Cyber.spaced(micro));
        toastText.setText(text.toUpperCase());
        toastText.setColor(Cyber.lerp(toastColor, Color.WHITE, 0.55));
        toastW = Math.max(300, toastText.textWidth() + 52);
        toastFrame.size(toastW, 56).border(toastColor);
        toastStripe.setSize(5, 56);
        if (toastSpecial) toastText.burst(0.5);
    }

    /** Cash for the HUD chip: full digits up to $999,999, then compact ($1.25M, $12.5M) so it never overflows the chip. */
    static String compactMoney(double v) {
        if (v < 1_000_000) return Cyber.money(v);
        double m = v / 1_000_000.0;
        return m < 10 ? String.format("$%.2fM", m) : m < 100 ? String.format("$%.1fM", m) : String.format("$%.0fM", m);
    }
}
