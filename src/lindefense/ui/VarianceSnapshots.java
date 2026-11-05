package lindefense.ui;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import lindefense.map.MapCatalog;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.TowerType;
import lindefense.variance.BreakingNews;
import lindefense.variance.PatchNote;
import lindefense.variance.RunSeed;

/**
 * Developer tool: paints the run-variance screens (patch-notes drafts, the HUD strip with chips and the news ticker,
 * hover cards, pause menu seed, end screen) offscreen into PNGs, without opening a window.
 * {@code java -Djava.awt.headless=true -cp build:lib/acm.jar lindefense.ui.VarianceSnapshots <dir>}.
 */
public final class VarianceSnapshots {
    private VarianceSnapshots() { }

    private static void snap(acm.graphics.GCompound c, File dir, String name) throws Exception {
        BufferedImage img = new BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        Cyber.quality(g);
        c.paint(g);
        g.dispose();
        ImageIO.write(img, "png", new File(dir, name + ".png"));
    }

    private static void frames(GameScreen s, int n) { for (int i = 0; i < n; i++) s.frame(0.05); }

    /** Writes the snapshots into {@code args[0]} (default {@code snapshots}). */
    public static void main(String[] args) throws Exception {
        System.setProperty("lindefense.nosound", "true");
        File dir = new File(args.length > 0 ? args[0] : "snapshots");
        dir.mkdirs();
        Game g = new Game(MapCatalog.create(2), RunSeed.parse("K3X9QZ"), lindefense.sim.Difficulty.ON);
        g.getVariance().enable();
        GameScreen s = new GameScreen(null, g);
        frames(s, 12);
        snap(s, dir, "v01_draft_launch");
        s.mouseMoved(600, 560);   // hover the middle card
        frames(s, 6);
        snap(s, dir, "v01b_draft_hover");
        s.pickPatchNote(1);
        g.getVariance().grant(PatchNote.CONTEXT_WINDOW);
        g.getVariance().grant(PatchNote.SYNTHETIC_DATA);
        g.addCash(6000, null);
        Vec[] spots = { new Vec(380, 300), new Vec(700, 250), new Vec(460, 520), new Vec(820, 660), new Vec(300, 700) };
        TowerType[] types = { TowerType.GPT, TowerType.CLAUDE, TowerType.PERPLEXITY, TowerType.DEEPSEEK, TowerType.GEMINI };
        for (int i = 0; i < spots.length; i++) g.placeTower(types[i], lindefense.test.TestKit.buildableNear(g, spots[i], 200));
        g.getVariance().forceNews(BreakingNews.GPU_SHORTAGE, -1);
        s.mouseMoved(5, 990);
        frames(s, 70);   // let the banner queue fire
        snap(s, dir, "v02_strip_news_prep");
        g.startNextWave();
        for (int i = 0; i < 60 * 5; i++) { g.step(Game.DT); if (i % 3 == 0) s.frame(Game.DT * 3); }
        snap(s, dir, "v03_strip_live_wave");
        s.mouseMoved(112, Ui.WORLD_Y + 12);   // first chip
        frames(s, 2);
        snap(s, dir, "v04_chip_hover");
        s.mouseMoved(760, Ui.WORLD_Y + 12);   // ticker
        frames(s, 2);
        snap(s, dir, "v05_news_hover");
        s.mouseMoved(5, 990);
        // jump to the wave-20 draft
        while (g.getWave() < 19) { g.getWaveManager().startNextWave(); g.getWaveManager().endWave(); }
        g.getEnemyManager().clear();
        g.getWaveManager().canStartNextWave();   // opens the due draft
        frames(s, 12);
        snap(s, dir, "v06_draft_wave20");
        s.pickPatchNote(0);
        frames(s, 4);
        // a boss on the track: the dock opens under the strip
        g.getVariance().forceNews(BreakingNews.SERVER_OUTAGE, 1);
        g.startNextWave();
        g.getEnemyManager().spawn(lindefense.enemy.EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 300);
        for (int i = 0; i < 60 * 3; i++) { g.step(Game.DT); if (i % 3 == 0) s.frame(Game.DT * 3); }
        snap(s, dir, "v07_boss_dock_with_strip");
        s.openMenu();
        frames(s, 3);
        snap(s, dir, "v08_pause_seed");
        s.escapePressed();
        frames(s, 2);
        lindefense.enemy.Enemy e = g.getEnemyManager().spawn(lindefense.enemy.EnemyType.STATIC_ARRAY, null, 0, 100);
        g.loseLives(g.getLives(), e);
        for (int i = 0; i < 60 * 3; i++) g.step(Game.DT);
        frames(s, 12);
        snap(s, dir, "v09_defeat_with_notes");
        // the longest titles and texts in one draft (a seed whose launch offer has them)
        long seed = 0;
        java.util.List<PatchNote> none = new java.util.ArrayList<>();
        while (!(lindefense.variance.RunVariance.offerFor(seed, 1, none).contains(PatchNote.CONTEXT_WINDOW)
            && lindefense.variance.RunVariance.offerFor(seed, 1, none).contains(PatchNote.ATTENTION))) seed++;
        Game lg = new Game(MapCatalog.create(5), seed, lindefense.sim.Difficulty.O1);
        lg.getVariance().enable();
        GameScreen ls = new GameScreen(null, lg);
        frames(ls, 12);
        snap(ls, dir, "v11_draft_long_titles");
        // variance off (tools, tutorial): no strip, full-size playfield
        Game off = new Game(MapCatalog.create(2), 7L);
        GameScreen so = new GameScreen(null, off);
        frames(so, 6);
        snap(so, dir, "v10_variance_off");
        System.out.println("snapshots written to " + dir.getAbsolutePath());
        System.exit(0);
    }
}
