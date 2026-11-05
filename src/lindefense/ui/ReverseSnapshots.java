package lindefense.ui;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import lindefense.ai.AttackUnit;
import lindefense.ai.AttackerBot;
import lindefense.ai.ReverseMatch;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.tower.Tower;

/**
 * Developer tool: paints the reverse-mode ("Adversarial Training") screens offscreen into PNGs for visual review,
 * without opening a window: the briefing switch and the attacker briefing, the in-match HUD and spawn panel at several
 * moments (driven by the scripted {@link AttackerBot}), a hovered unit card, a selected AI tower, the help overlay, the
 * pause menu and both end screens. {@code java -Djava.awt.headless=true -cp build:lib/acm.jar lindefense.ui.ReverseSnapshots <dir>}.
 */
public final class ReverseSnapshots {
    private ReverseSnapshots() { }

    private static void snap(acm.graphics.GCompound c, File dir, String name) throws Exception {
        BufferedImage img = new BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        Cyber.quality(g);
        c.paint(g);
        g.dispose();
        ImageIO.write(img, "png", new File(dir, name + ".png"));
        System.out.println("wrote " + new File(dir, name + ".png").getPath());
    }

    /** Runs the match headlessly with the bot for {@code seconds}, then a few rendered frames so the views catch up. */
    private static void play(Game g, GameScreen s, AttackerBot bot, double seconds) {
        int n = (int) (seconds / Game.DT);
        for (int i = 0; i < n && g.getState() == Game.State.PLAYING; i++) { bot.tick(Game.DT); g.step(Game.DT); if (i % 30 == 0) s.frame(0); g.getEvents().clear(); }
        for (int i = 0; i < 20; i++) { bot.tick(Game.DT); s.frame(Game.DT); }
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("lindefense.nosound", "true");
        File dir = new File(args.length > 0 ? args[0] : "snapshots-reverse");
        dir.mkdirs();
        Difficulty.setSelected(Difficulty.ON);

        // map select: the normal briefing with its ATTACK INSTEAD switch, then the attacker briefing
        MapSelectScreen ms = new MapSelectScreen(null);
        ms.frame(0.02);
        ms.openBriefing(4);
        ms.frame(0.05);
        snap(ms, dir, "r01_briefing_with_attack_switch");
        ms.openReverseBriefing(4);
        ms.frame(0.05);
        snap(ms, dir, "r02_reverse_briefing");
        ms.openReverseBriefing(1);
        ms.frame(0.05);
        snap(ms, dir, "r02b_reverse_briefing_long_track");

        // in match: Competent AI on The Silicon Circuit
        Game g = ReverseMatch.create(0, 11, Difficulty.ON);
        ReverseMatch r = g.getReverse();
        GameScreen s = new GameScreen(null, g);
        s.frame(0.02);
        snap(s, dir, "r03_match_start");
        AttackerBot bot = new AttackerBot(r, AttackerBot.Style.REASONABLE);
        play(g, s, bot, 75);
        r.send(AttackUnit.DYNAMIC, null, 6, -1);
        play(g, s, bot, 10);
        snap(s, dir, "r04_match_1m25");
        play(g, s, bot, 240);
        double[] card = { Ui.PANEL_X + 8 + 62, 150 + 5 * 67 + 31 };   // the MOAB card (row 6, column 1)
        s.mouseMoved(card[0], card[1]);
        s.frame(Game.DT); s.frame(Game.DT);
        snap(s, dir, "r05_hover_unit_card");
        s.mouseMoved(600, 500);
        play(g, s, bot, 140);
        snap(s, dir, "r06_match_7m");
        Tower best = null;
        for (Tower t : g.getTowerManager().getPlayerTowers()) if (best == null || t.getInvestedCost() > best.getInvestedCost()) best = t;
        if (best != null) { s.selectTower(best); s.frame(Game.DT); s.frame(Game.DT); snap(s, dir, "r07_ai_tower_selected"); s.selectTower(null); }
        s.toggleHelp(); s.frame(Game.DT);
        snap(s, dir, "r08_help");
        s.toggleHelp();
        s.openMenu(); s.frame(Game.DT);
        snap(s, dir, "r09_pause_menu");
        s.escapePressed(); s.frame(Game.DT);
        play(g, s, bot, 400);
        for (int i = 0; i < 200 && g.getState() == Game.State.PLAYING; i++) { bot.tick(Game.DT); s.frame(Game.DT); }
        snap(s, dir, g.getState() == Game.State.DEFEAT ? "r10_end_breach" : "r10_end_contained");

        // the other end screen: a passive attacker against the Superintelligence on The Neural Network
        Game h = ReverseMatch.create(5, 12, Difficulty.ONN);
        GameScreen hs = new GameScreen(null, h);
        play(h, hs, new AttackerBot(h.getReverse(), AttackerBot.Style.PASSIVE), ReverseMatch.DURATION + 5);
        for (int i = 0; i < 10; i++) hs.frame(Game.DT);
        snap(hs, dir, h.getState() == Game.State.VICTORY ? "r11_end_contained" : "r11_end_other");
        // a breach on the easy AI for the attacker's victory screen
        Game w = ReverseMatch.create(2, 13, Difficulty.O1);
        GameScreen ws = new GameScreen(null, w);
        play(w, ws, new AttackerBot(w.getReverse(), AttackerBot.Style.REASONABLE), ReverseMatch.DURATION);
        for (int i = 0; i < 200 && w.getState() == Game.State.PLAYING; i++) ws.frame(Game.DT);
        for (int i = 0; i < 10; i++) ws.frame(Game.DT);
        snap(ws, dir, w.getState() == Game.State.DEFEAT ? "r12_end_breach" : "r12_end_other");
    }
}
