package lindefense.ui.sprites.towers;

import acm.graphics.GCanvas;
import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GObject;
import acm.graphics.GRect;
import acm.program.GraphicsProgram;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import javax.swing.Timer;
import lindefense.combat.VisualEvent;
import lindefense.sim.Vec;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.ui.TowerSprite;
import lindefense.ui.sprites.Animated;

/**
 * Visual self-check for the tower art. Run with {@code -Dgallery.page=towers}
 * (default) for a grid of every tower at all five tiers drawn through real
 * {@link TowerSprite}s, or {@code -Dgallery.page=fx} for an aiming / recoil
 * demo, every projectile in flight at tier 0 and tier 4, shop icons and
 * looping BEAM / CHAIN / HIT / EXPLOSION effects.
 */
@SuppressWarnings({ "serial", "this-escape" })
public class TowerGallery extends GraphicsProgram {
    private static final long serialVersionUID = 1L;
    private static final Color BG = new Color(0x3f8f4f);
    private static final Color BG2 = new Color(0x4a9c5a);
    private static final Font F = lindefense.ui.Ui.body(Font.BOLD, 12);
    private static final Font FS = lindefense.ui.Ui.body(Font.PLAIN, 10);

    private final List<TowerSprite> sprites = new ArrayList<>();
    private final List<Tower> towers = new ArrayList<>();
    private final List<TowerArt> aimers = new ArrayList<>();
    private final List<ProjectileSprite> shots = new ArrayList<>();
    private final List<double[]> shotPaths = new ArrayList<>();
    private final List<Animated> fx = new ArrayList<>();
    private GCompound fxLayer;
    private double clock, lastFire, lastFx;
    private boolean fxPage;

    @Override public void init() {
        fxPage = "fx".equals(System.getProperty("gallery.page", "towers"));
        setSize(1500, 1060);
        setTitle("Lindefense tower gallery - " + (fxPage ? "projectiles & effects" : "towers x tiers"));
    }

    @Override public void run() {
        GCanvas canvas = getGCanvas();
        canvas.setBackground(BG);
        canvas.setAutoRepaintFlag(false);
        if (fxPage) buildFx(); else buildTowers();
        canvas.repaint();
        Timer timer = new Timer(33, e -> tick(0.033));
        timer.start();
    }

    private void label(String s, double x, double y, Font f) {
        GLabel l = new GLabel(s, x, y);
        l.setFont(f);
        l.setColor(Color.WHITE);
        add(l);
    }

    private void buildTowers() {
        TowerType[] all = TowerType.values();
        int rows = (all.length + 1) / 2;
        double cellW = 112, cellH = 92, labelW = 150, top = 40;
        for (int block = 0; block < 2; block++) {
            double bx = block * (labelW + 5 * cellW + 30);
            for (int t = 0; t < 5; t++) label("Tier " + t, bx + labelW + t * cellW + 30, 22, F);
            for (int i = 0; i < rows; i++) {
                int idx = block * rows + i;
                if (idx >= all.length) break;
                TowerType type = all[idx];
                double cy = top + i * cellH + cellH / 2;
                GRect band = new GRect(bx, top + i * cellH, labelW + 5 * cellW, cellH);
                band.setFilled(true); band.setFillColor(i % 2 == 0 ? BG : BG2); band.setColor(i % 2 == 0 ? BG : BG2);
                add(band);
                label(type.displayName, bx + 8, cy + 4, F);
                TowerDef def = TowerCatalog.get(type);
                for (int t = 0; t < 5; t++) {
                    double cx = bx + labelW + t * cellW + cellW / 2;
                    Tower tower = new Tower(def, new Vec(cx, cy - 6), t, false, 0, null);
                    TowerSprite s = new TowerSprite(tower);
                    add(s);
                    sprites.add(s);
                    towers.add(tower);
                }
            }
        }
    }

    private void buildFx() {
        // aim / recoil demo
        label("Aim + recoil demo (TowerArt.aim / setFiring)", 20, 22, F);
        TowerType[] demo = { TowerType.CLAUDE, TowerType.KAIJU_KAI, TowerType.DEEPSEEK, TowerType.KIMI, TowerType.COHERE, TowerType.GEMINI, TowerType.LLAMA, TowerType.ZETHOS };
        int[] demoTier = { 2, 4, 3, 1, 4, 2, 3, 4 };
        for (int i = 0; i < demo.length; i++) {
            TowerArt a = TowerArtFactory.create(demo[i], demoTier[i], 20);
            a.setLocation(70 + i * 110, 85);
            add(a);
            aimers.add(a);
        }
        // projectiles
        label("Projectiles: tier 0 row, tier 4 row (one per tower type)", 20, 160, F);
        TowerType[] all = TowerType.values();
        for (int t = 0; t < 2; t++) {
            int tier = t == 0 ? 0 : 4;
            for (int i = 0; i < all.length; i++) {
                TowerType type = all[i];
                TowerDef def = TowerCatalog.get(type);
                TowerStats st = def.statsForTier(tier);
                double size = st.splashRadius > 0 ? 8 : (st.hit.damage >= 5 ? 7 : 5);
                ProjectileSprite p = ProjectileSprites.create(type, tier, st, size, type.primaryRgb);
                add(p);
                shots.add(p);
                shotPaths.add(new double[] { 50 + i * 66, 200 + t * 70, i * 0.4 });
                if (t == 0) {
                    GLabel l = new GLabel(type.displayName.length() > 9 ? type.displayName.substring(0, 9) : type.displayName, 50 + i * 66 - 20, 330);
                    l.setFont(FS); l.setColor(Color.WHITE); add(l);
                }
            }
        }
        // icons
        label("TowerIcons.create(type, tier, 56) for game tiers 0 and 3", 20, 370, F);
        for (int t = 0; t < 2; t++) {
            for (int i = 0; i < all.length; i++) {
                double cx = 50 + i * 66, cy = 410 + t * 70;
                GRect box = new GRect(cx - 28, cy - 28, 56, 56);
                box.setColor(new Color(0xffffff));
                add(box);
                GCompound icon = TowerIcons.create(all[i], t == 0 ? 0 : 3, 56);
                add(icon, cx, cy);
            }
        }
        // effects
        label("Attack effects: BEAM, CHAIN, HIT, EXPLOSION (looping)", 20, 540, F);
        fxLayer = new GCompound();
        add(fxLayer);
    }

    private void spawnFx() {
        int[] cols = { 0xe88a4a, 0x4f7cff, 0x20b2aa, 0xffd700, 0xff5fa2, 0x19e6ff };
        int c = cols[(int) (clock * 7) % cols.length];
        addFx(VisualEvent.beam(new Vec(60, 620), new Vec(260, 580), c));
        addFx(VisualEvent.chain(new Vec(320, 620), new Vec(470, 585), cols[(int) (clock * 3) % cols.length]));
        addFx(VisualEvent.hit(new Vec(560, 600), c));
        addFx(VisualEvent.explosion(new Vec(700, 600), 45, c));
        addFx(VisualEvent.explosion(new Vec(850, 600), 90, 0xffd700));
        addFx(new VisualEvent(VisualEvent.Kind.BEAM, new Vec(960, 640), new Vec(1200, 560), 4, 0x3d3fa8, null, 0.3));
    }

    private void addFx(VisualEvent ev) {
        Animated a = ProjectileSprites.createAttackEffect(ev);
        if (a instanceof GObject) { fxLayer.add((GObject) a); fx.add(a); }
    }

    private boolean shotTaken;

    /** Writes the canvas to the PNG named by -Dgallery.shot once the scene has settled. */
    private void maybeSnapshot() {
        String path = System.getProperty("gallery.shot");
        if (path == null || shotTaken || clock < Double.parseDouble(System.getProperty("gallery.shotAt", "2.5"))) return;
        shotTaken = true;
        try {
            GCanvas canvas = getGCanvas();
            java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(
                Math.max(1, canvas.getWidth()), Math.max(1, canvas.getHeight()), java.awt.image.BufferedImage.TYPE_INT_RGB);
            java.awt.Graphics2D g = img.createGraphics();
            g.setRenderingHint(java.awt.RenderingHints.KEY_ANTIALIASING, java.awt.RenderingHints.VALUE_ANTIALIAS_ON);
            canvas.paint(g);
            g.dispose();
            javax.imageio.ImageIO.write(img, "png", new java.io.File(path));
            System.out.println("snapshot written: " + path);
        } catch (Exception ex) {
            System.out.println("snapshot failed: " + ex);
        }
    }

    private void tick(double dt) {
        clock += dt;
        maybeSnapshot();
        if (!fxPage) {
            if (clock - lastFire > 1.6) {
                lastFire = clock;
                for (Tower t : towers) t.setLastFireTime(clock);
            }
            for (TowerSprite s : sprites) s.sync(null, dt, false);
        } else {
            double ang = clock * 1.3;
            double since = (clock - lastFire);
            if (since > 0.9) { lastFire = clock; since = 0; }
            for (TowerArt a : aimers) { a.aim(ang); a.setFiring(since); a.animate(clock, dt); }
            for (int i = 0; i < shots.size(); i++) {
                double[] p = shotPaths.get(i);
                double a = clock * 1.5 + p[2];
                double x = p[0] + Math.cos(a) * 16, y = p[1] + Math.sin(a) * 16;
                shots.get(i).place(x, y, -Math.sin(a), Math.cos(a), clock);
                shots.get(i).step(dt);
            }
            if (clock - lastFx > 0.75) { lastFx = clock; spawnFx(); }
            for (int i = fx.size() - 1; i >= 0; i--) {
                if (!fx.get(i).step(dt)) { fxLayer.remove((GObject) fx.get(i)); fx.remove(i); }
            }
        }
        getGCanvas().repaint();
    }

    /** Entry point. */
    public static void main(String[] args) {
        new TowerGallery().start(args);
    }
}
