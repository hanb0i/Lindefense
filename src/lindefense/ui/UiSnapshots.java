package lindefense.ui;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import lindefense.map.MapCatalog;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Developer tool: paints real screens (Hero Store, hero / Zethos info panels and combat, tutorial, catalog) offscreen
 * into PNGs for visual review, without opening a window. {@code java -cp build:lib/acm.jar lindefense.ui.UiSnapshots <dir>}.
 */
public final class UiSnapshots {
    private UiSnapshots() { }

    private static void snap(acm.graphics.GCompound c, File dir, String name) throws Exception {
        BufferedImage img = new BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        Cyber.quality(g);
        c.paint(g);
        g.dispose();
        ImageIO.write(img, "png", new File(dir, name + ".png"));
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("lindefense.nosound", "true");
        File dir = new File(args.length > 0 ? args[0] : "snapshots");
        dir.mkdirs();
        Game g = new Game(MapCatalog.create(0), 7L);
        g.setHeroLimit(Integer.MAX_VALUE);   // the review battle fields six heroes at once
        g.addCash(1600, null);
        GameScreen s = new GameScreen(null, g, true);
        s.frame(0.02);
        snap(s, dir, "01_tutorial_start");
        s.toggleHeroStore();
        s.frame(0.02);
        snap(s, dir, "02_hero_store_locked");
        s.buyHero(TowerType.SUNNY_JOE);
        s.frame(0.02);
        snap(s, dir, "03_hero_store_after_buy");
        s.toggleHeroStore();
        // a battle with every hero and a maxed Zethos
        for (TowerType h : TowerType.heroes()) g.getHeroCollection().unlock(h);
        g.addCash(50_000, null);
        Vec[] spots = { new Vec(380, 300), new Vec(700, 250), new Vec(460, 520), new Vec(560, 480), new Vec(820, 660), new Vec(300, 700), new Vec(950, 420) };
        TowerType[] types = { TowerType.LOBBER_LUIS, TowerType.CHILLSTIN, TowerType.KAIJU_KAI, TowerType.NIK_SCOPE, TowerType.ZETHOS, TowerType.BLITZ_ARNAV, TowerType.SAGE_AARAV };
        Tower zethos = null, owen = null;
        for (int i = 0; i < types.length; i++) {
            Vec p = lindefense.test.TestKit.buildableNear(g, spots[i], 200);
            Tower t = g.placeTower(types[i], p);
            if (t == null) { System.out.println("could not place " + types[i] + ": " + g.placementProblem(types[i], p)); continue; }
            while (g.upgradeTower(t)) { /* max */ }
            if (types[i] == TowerType.ZETHOS) zethos = t;
            if (types[i] == TowerType.NIK_SCOPE) owen = t;
        }
        for (int k = 0; k < 12; k++) { g.getWaveManager().startNextWave(); }
        for (int i = 0; i < 60 * 6; i++) { g.step(Game.DT); s.frame(Game.DT); }
        for (Tower t : g.getTowerManager().getPlayerTowers()) { t.resetAbilityCooldown(); g.activateAbility(t); }
        for (int i = 0; i < 40; i++) { g.step(Game.DT); s.frame(Game.DT); }
        snap(s, dir, "04_battle_abilities");
        for (lindefense.map.Path r : g.getMap().getRoutes())
            for (double d = 100; d < r.getTotalLength(); d += 45) g.getEnemyManager().spawnScaled(lindefense.enemy.EnemyType.QUICK_SORT, null, g.getMap().getRoutes().indexOf(r), d, 60, 1.0);
        g.getEnemyManager().spawnScaled(lindefense.enemy.EnemyType.BELLARMINE_COLLEGE_PREP, null, 0, 700, 5, 1.0);
        for (Tower t : g.getTowerManager().getPlayerTowers()) { t.resetAbilityCooldown(); g.activateAbility(t); }
        for (int i = 0; i < 50; i++) { g.step(Game.DT); s.frame(Game.DT); }
        snap(s, dir, "04b_battle_live");
        if (zethos != null) { s.selectTower(zethos); s.frame(0.02); s.frame(0.02); snap(s, dir, "05_zethos_selected"); }
        if (owen != null) { s.selectTower(owen); s.frame(0.02); s.frame(0.02); snap(s, dir, "06_owen_selected"); }
        s.selectTower(null);
        s.beginPlacing(TowerType.ZETHOS);
        s.frame(0.02); s.frame(0.02);
        snap(s, dir, "07_shop_zethos_preview");
        s.beginPlacing(null);
        s.toggleHeroStore(); s.frame(0.02);
        snap(s, dir, "08_hero_store_deployed");
        CatalogScreen c = new CatalogScreen(null);
        c.frame(0.1); snap(c, dir, "09_catalog_enemies");
        c.setTab(CatalogScreen.Tab.BOSSES); c.select(4); c.frame(0.1); snap(c, dir, "10_catalog_boss");
        c.setTab(CatalogScreen.Tab.TOWERS); c.select(3); c.frame(0.1); snap(c, dir, "11_catalog_zethos");
        c.setTab(CatalogScreen.Tab.TOWERS); c.select(0); c.frame(0.1); snap(c, dir, "12_catalog_gemini");
        c.setTab(CatalogScreen.Tab.HEROES); c.select(0); c.frame(0.1); snap(c, dir, "13_catalog_brad");
        System.out.println("snapshots written to " + dir.getAbsolutePath());
        System.exit(0);
    }
}
