package lindefense.ui;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.EnumSet;
import javax.imageio.ImageIO;
import lindefense.combat.DamageType;
import lindefense.combat.HitSpec;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.MapCatalog;
import lindefense.map.Path;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.test.TestKit;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Developer tool: paints the prompt-injection and Palantir phase-ability visuals offscreen into PNGs for review,
 * without opening a window (and so without ever touching a real window: the window grab is shown through the
 * simulated window fraction only). {@code java -Djava.awt.headless=true -Dlindefense.nosound=true -cp build:lib/acm.jar
 * lindefense.ui.InjectionSnapshots <dir>}.
 */
public final class InjectionSnapshots {
    private InjectionSnapshots() { }

    private static void snap(acm.graphics.GCompound c, File dir, String name) throws Exception {
        BufferedImage img = new BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        Cyber.quality(g);
        c.paint(g);
        g.dispose();
        ImageIO.write(img, "png", new File(dir, name + ".png"));
        System.out.println("  " + name + ".png");
    }

    private static void run(Game g, GameScreen s, double seconds) {
        int n = (int) Math.round(seconds / Game.DT);
        for (int i = 0; i < n; i++) s.frame(Game.DT);   // the screen advances the game by one fixed step per frame
    }

    /** Places a fully upgraded tower near a track point offset by (dx, dy). */
    private static Tower near(Game g, TowerType t, double dist, double dx, double dy, int tier) {
        Path r = g.getMap().getRoutes().get(0);
        Vec p = TestKit.buildableNear(g, r.positionAt(dist).add(new Vec(dx, dy)), 140);
        return TestKit.forcePlace(g, t, p, tier);
    }

    /** Writes the snapshots into {@code args[0]} (default {@code snapshots-injection}). */
    public static void main(String[] args) throws Exception {
        System.setProperty("lindefense.nosound", "true");
        File dir = new File(args.length > 0 ? args[0] : "snapshots-injection");
        dir.mkdirs();

        // ---- 1. injectors hijack towers, hijacked towers zap neighbours
        Game g = new Game(MapCatalog.create(0), 11L);
        g.setInvincible(true);
        g.setGlobalEnemySpeedMultiplier(0);
        GameScreen s = new GameScreen(null, g, false);
        double at = 520;
        Tower gpt = near(g, TowerType.GPT, at, 0, -70, 2);
        Tower gem = near(g, TowerType.GEMINI, at, 70, -80, 2);
        Tower qwen = near(g, TowerType.QWEN, at, -70, -75, 1);
        Tower claude = near(g, TowerType.CLAUDE, at, 20, 75, 2);
        near(g, TowerType.COHERE, at, 150, -40, 1);
        near(g, TowerType.SORA, at, -150, -30, 1);
        Tower ds = near(g, TowerType.DEEPSEEK, at, -40, 120, 1);
        Path r = g.getMap().getRoutes().get(0);
        for (int i = 0; i < 4; i++) {
            Enemy e = g.getEnemyManager().spawn(EnemyType.TIMSORT, EnumSet.of(Modifier.INJECTION), 0, at - 40 + i * 90);
            if (e != null && i == 3) e.takeDamage(e.getMaxHp() * 0.4, 0);
        }
        g.getEnemyManager().spawn(EnemyType.QUICK_SORT, null, 0, at - 160);
        g.getEnemyManager().update(0);
        run(g, s, 0.15);
        snap(s, dir, "inj_01_signs_broadcast");
        run(g, s, 0.45);
        snap(s, dir, "inj_02_hijack_zap");
        Tower hij = null;
        for (Tower t : g.getTowerManager().getTowers()) if (t.isHijacked()) hij = t;
        if (hij != null) { s.selectTower(hij); s.frame(0.02); s.frame(0.02); snap(s, dir, "inj_03_panel_hijacked"); }
        s.selectTower(claude); s.frame(0.02); s.frame(0.02);
        snap(s, dir, "inj_04_panel_claude_immune");
        s.selectTower(ds); s.frame(0.02); s.frame(0.02);
        snap(s, dir, "inj_05_panel_deepseek_immune");
        s.selectTower(null);
        s.beginPlacing(TowerType.PERPLEXITY); s.frame(0.02); s.frame(0.02);
        snap(s, dir, "inj_06_shop_perplexity_immune");
        s.beginPlacing(null);
        // Copilot firewall: a GPT inside the tether radius
        Game g2 = new Game(MapCatalog.create(0), 12L);
        g2.setGlobalEnemySpeedMultiplier(0);
        GameScreen s2 = new GameScreen(null, g2, false);
        Tower cop = near(g2, TowerType.COPILOT, 400, 0, -70, 1);
        Vec gp = TestKit.buildableNear(g2, cop.getPosition().add(new Vec(60, 0)), 80);
        Tower shielded = TestKit.forcePlace(g2, TowerType.GPT, gp, 1);
        g2.getTowerManager().recomputeAuras();
        s2.selectTower(shielded); s2.frame(0.02); s2.frame(0.02);
        snap(s2, dir, "inj_07_panel_copilot_firewall");

        // ---- 2. Palantir phase 1: Panopticon
        Game p = new Game(MapCatalog.create(0), 21L);
        p.setInvincible(true);
        p.setGlobalEnemySpeedMultiplier(0);
        GameScreen ps = new GameScreen(null, p, false);
        double pd = 700;
        Tower[] ring = {
            near(p, TowerType.GPT, pd, 0, -110, 2), near(p, TowerType.GEMINI, pd, 160, -60, 2), near(p, TowerType.QWEN, pd, -170, -40, 1),
            near(p, TowerType.COHERE, pd, 120, 120, 1), near(p, TowerType.CLAUDE, pd, -120, 130, 2), near(p, TowerType.SORA, pd, 250, 40, 1),
            near(p, TowerType.KIMI, pd, -260, 60, 1), near(p, TowerType.DEEPSEEK, pd, 40, 230, 1) };
        Boss pal = (Boss) p.getEnemyManager().spawn(EnemyType.PALANTIR, null, 0, pd);
        p.getEnemyManager().update(0);
        run(p, ps, 4.6);
        snap(ps, dir, "inj_08_palantir_panopticon");
        run(p, ps, 2.2);
        snap(ps, dir, "inj_09_palantir_panopticon_later");
        if (ring[0].isOffline()) { ps.selectTower(ring[0]); ps.frame(0.02); ps.frame(0.02); }

        // ---- 3. phase 2: Prompt Broadcast + decoys
        p.getCombat().applyHit(pal, new HitSpec(pal.getMaxHp() * 0.31, DamageType.TRUE), null, 1, 0);
        run(p, ps, 1.0);
        snap(ps, dir, "inj_10_palantir_decoys");
        run(p, ps, 2.3);
        snap(ps, dir, "inj_11_palantir_prompt_broadcast");

        // ---- 4. phase 3: System Takeover, kill switch, window seal (simulated window fraction only)
        for (Tower t : p.getTowerManager().getTowers()) { if (t.isAbilityLocked() && t.canUnlockAbility()) { p.addCash(20000, null); p.unlockAbility(t); } }
        p.getCombat().applyHit(pal, new HitSpec(pal.getHp() - pal.getMaxHp() * 0.30, DamageType.TRUE), null, 1, 0);
        run(p, ps, 0.4);
        snap(ps, dir, "inj_12_palantir_kill_switch");
        p.setWindowFraction(0.72);   // what the windowed UI would report after the grab
        run(p, ps, 1.5);
        snap(ps, dir, "inj_13_palantir_sealed");
        ps.selectEnemy(pal); ps.frame(0.02); ps.frame(0.02);
        snap(ps, dir, "inj_14_palantir_sealed_selected");
        p.setWindowFraction(0.95);
        run(p, ps, 0.5);
        ps.selectEnemy(null);
        snap(ps, dir, "inj_15_palantir_seal_broken");

        // ---- 5. catalog and settings
        CatalogScreen c = new CatalogScreen(null);
        c.setTab(CatalogScreen.Tab.TOWERS); c.select(indexOf(CatalogScreen.Tab.TOWERS, TowerType.CLAUDE)); c.frame(0.1); snap(c, dir, "inj_16_catalog_claude");
        c.setTab(CatalogScreen.Tab.TOWERS); c.select(indexOf(CatalogScreen.Tab.TOWERS, TowerType.COPILOT)); c.frame(0.1); snap(c, dir, "inj_17_catalog_copilot");
        c.setTab(CatalogScreen.Tab.TOWERS); c.select(indexOf(CatalogScreen.Tab.TOWERS, TowerType.GPT)); c.frame(0.1); snap(c, dir, "inj_18_catalog_gpt");
        c.setTab(CatalogScreen.Tab.HEROES); c.select(indexOf(CatalogScreen.Tab.HEROES, TowerType.MR_LINDEMANN)); c.frame(0.1); snap(c, dir, "inj_19_catalog_lindemann");
        c.setTab(CatalogScreen.Tab.BOSSES); c.select(4); c.frame(0.1); snap(c, dir, "inj_20_catalog_palantir");
        c.setTab(CatalogScreen.Tab.ENEMIES); c.select(CatalogScreen.entries(CatalogScreen.Tab.ENEMIES).indexOf(EnemyType.PALANTIR_HOLOGRAM)); c.frame(0.1); snap(c, dir, "inj_21_catalog_hologram");
        System.out.println("snapshots written to " + dir.getAbsolutePath());
        System.exit(0);
    }

    private static int indexOf(CatalogScreen.Tab tab, Object o) { return Math.max(0, CatalogScreen.entries(tab).indexOf(o)); }
}
