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
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import lindefense.combat.Projectile;
import lindefense.combat.VisualEvent;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.effects.Effects;
import lindefense.map.AbandonedDataCenter;
import lindefense.map.GameMap;
import lindefense.map.HallucinationCanyon;
import lindefense.map.LegacyMonolith;
import lindefense.map.Path;
import lindefense.map.SiliconCircuit;
import lindefense.sim.Game;
import lindefense.sim.Vec;
import lindefense.tower.AbilityDef;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;
import lindefense.ui.sprites.Animated;
import lindefense.ui.sprites.EnemySprite;
import lindefense.ui.sprites.SpriteFactory;
import lindefense.ui.sprites.Thick;
import lindefense.ui.sprites.towers.ProjectileSprite;
import lindefense.ui.sprites.towers.ProjectileSprites;

/**
 * Renders the playfield: map background and track, towers, enemies (via the
 * sprite package), projectiles, transient effects, boss health bars, Palantir's
 * surveillance telegraph and the placement ghost / range circle. All children
 * live in world coordinates (1200x900); the compound sits at the world origin
 * inside the scaled root.
 *
 * <h3>Big fights</h3>
 * <ul>
 *   <li><b>Level of detail</b>: the number of sprites on screen picks a level (see {@link #LOD_DECOR_LOAD}) that is
 *       applied while this view paints ({@link Thick#setLevel}): decorative and then fine sprite details are skipped,
 *       enemy HP bars are drawn simplified.</li>
 *   <li><b>Effect caps</b>: at most {@link #MAX_EFFECTS} legacy and {@link #MAX_EFFECTS} animated effects at full
 *       detail, fewer at higher levels of detail ({@link #effectCap()}); extra visual events are dropped.</li>
 *   <li><b>Effect pool</b>: the simple flash / ring / text effects are pooled. A finished one is hidden and stays in
 *       the effect layer for reuse, so a busy frame neither allocates new GObjects for them nor pays ACM's linear
 *       {@code remove} for each one that expires.</li>
 * </ul>
 */
public final class WorldView extends GCompound {
    private static final long serialVersionUID = 1L;
    private static final int MAX_EFFECTS = 160;

    /**
     * Level of detail for crowded screens (see {@link Thick#setLevel}). The "load" is the number of enemy sprites plus
     * half the tower sprites; at {@link #LOD_DECOR_LOAD} decorative parts (shadows, gloss, cracks, overlay accents) are
     * skipped, at {@link #LOD_FINE_LOAD} also the small features (eyes, thin outlines). Each tier switches back off only
     * when the load falls 20% below its threshold, so a crowd hovering at a threshold does not flicker.
     * {@code -Dlindefense.lod=0|1|2} pins the level (comparisons, screenshots).
     */
    static final int LOD_DECOR_LOAD = 60, LOD_FINE_LOAD = 150;
    private static final int LOD_FORCED = Integer.getInteger("lindefense.lod", -1);
    private int lod;

    private final GameScreen screen;
    private final Game game;
    private final GameMap map;

    private final GCompound background = new GCompound();
    private final GCompound mapFx = new GCompound();
    private final GCompound towerLayer = new GCompound();
    private final GCompound enemyLayer = new GCompound();
    private final GCompound hpLayer = new GCompound();
    private final GCompound projectileLayer = new GCompound();
    private final GCompound effectLayer = new GCompound();
    private final GCompound overlay = new GCompound();
    private final WorldFx fx;
    /** Prompt-injection signs, hijack beams, Palantir's phase abilities and the window-seal banner. */
    private final IntrusionFx intrusionFx;

    private final Map<Tower, TowerSprite> towerSprites = new HashMap<>();
    private final Map<Enemy, EnemySprite> enemySprites = new HashMap<>();
    private final Map<Enemy, Cyber.Bar> hpBars = new HashMap<>();
    private final Map<Projectile, ProjectileSprite> projectileSprites = new HashMap<>();
    private final List<Effect> effects = new ArrayList<>();
    private final List<Animated> animated = new ArrayList<>();
    private final List<GObject> telegraphLines = new ArrayList<>();

    private Cyber.Ring rangeCircle, ghost, ghostRange;
    private GLine ghostX1, ghostX2;
    private Cyber.Ring reticleRadius, reticleDot;
    private GLine reticleH, reticleV, reticleLink;
    private Nameplate reticlePlate;
    private Nameplate ghostPlate, hoverPlate, selectPlate;
    private double viewScale = 1, viewDock;
    private final List<GOval> padFill = new ArrayList<>();
    private GRect ventRect;
    private GRect stormRect;
    private final List<GObject> shortFx = new ArrayList<>();
    private double time;
    private MapArt.Pulses pulses;
    /** Graphics-quality extras (HIGH preset): projectile halos / explosion flashes and camera shake (the vignette is baked into MapArt). */
    private final GlowLayer glow;
    private final ScreenShake shake = new ScreenShake();
    private int lastLives = -1;
    /** Abandoned Data Center: one list of track-section polygons per hazard, lit while it warns or is active. */
    private final List<List<GPolygon>> hazardFx = new ArrayList<>();

    public WorldView(GameScreen screen) {
        this.screen = screen;
        this.game = screen.getGame();
        this.map = game.getMap();
        setLocation(0, 0);
        fx = new WorldFx(game);
        intrusionFx = new IntrusionFx(game);
        buildBackground();
        add(background);
        add(mapFx);
        add(fx.ground());
        add(towerLayer);
        add(enemyLayer);
        add(fx.top());
        add(hpLayer);
        glow = new GlowLayer(game);
        add(glow);
        add(projectileLayer);
        add(effectLayer);
        add(intrusionFx.layer());
        add(overlay);
        buildOverlay();
    }

    // ------------------------------------------------------------------ static map
    private void buildBackground() {
        // detailed futuristic art (background, set dressing, track), pre-rendered once into a bitmap
        background.add(new MapArt(map));
        pulses = new MapArt.Pulses(map);
        mapFx.add(pulses);
        for (Path r : map.getRoutes()) {
            List<Vec> w = r.getWaypoints();
            addMarker(r.getStart(), w.get(1).sub(w.get(0)).normalized(), Cyber.GREEN, "IN");
            addMarker(r.getEnd(), w.get(w.size() - 1).sub(w.get(w.size() - 2)).normalized(), Cyber.RED, "OUT");
        }
        if (map instanceof SiliconCircuit) {
            for (Vec p : ((SiliconCircuit) map).getPads()) {
                GOval f = Ui.oval(p.x - 36, p.y - 36, 72, 72, Ui.c(0x7fd8a8, 40), Ui.c(0x7fd8a8, 0));
                padFill.add(f);
                mapFx.add(f);
            }
        }
        if (map instanceof LegacyMonolith) {
            ventRect = Ui.rect(0, 0, GameMap.WIDTH, 10, Ui.c(0xff6a00, 45), Ui.c(0xff6a00, 120));
            ventRect.setVisible(false);
            mapFx.add(ventRect);
        }
        if (map instanceof AbandonedDataCenter) {
            Path r = map.getRoutes().get(0);
            for (AbandonedDataCenter.Hazard h : ((AbandonedDataCenter) map).getHazards()) {
                List<GPolygon> polys = new ArrayList<>();
                Vec prev = r.positionAt(h.from);
                for (double d = h.from + 24; ; d += 24) {
                    Vec next = r.positionAt(Math.min(d, h.to));
                    if (next.dist(prev) > 0.5) {
                        GPolygon p = segment(prev, next, GameMap.TRACK_HALF_WIDTH + 2, Ui.c(h.rgb, 0));
                        p.setVisible(false);
                        mapFx.add(p);
                        polys.add(p);
                    }
                    prev = next;
                    if (d >= h.to) break;
                }
                hazardFx.add(polys);
            }
        }
        if (map instanceof HallucinationCanyon) {
            stormRect = Ui.rect(0, 0, GameMap.WIDTH, GameMap.HEIGHT, Ui.c(0xff8cf0, 35), Ui.c(0xff8cf0, 0));
            stormRect.setVisible(false);
            mapFx.add(stormRect);
        }
    }

    /** Track entry / exit marker: a ringed chevron inset from the world edge so it is never clipped. */
    private void addMarker(Vec at, Vec dir, Color col, String text) {
        double m = 26;
        double px = Math.max(m, Math.min(GameMap.WIDTH - m, at.x)), py = Math.max(m, Math.min(GameMap.HEIGHT - m, at.y));
        Cyber.Ring ring = new Cyber.Ring(px - 15, py - 15, 30, 30, Cyber.alpha(col, 70), Cyber.alpha(col, 235));
        ring.setLineWidth(2);
        background.add(ring);
        Vec n = new Vec(-dir.y, dir.x);
        GPolygon chev = new GPolygon();
        chev.addVertex(px + dir.x * 8, py + dir.y * 8);
        chev.addVertex(px - dir.x * 1 + n.x * 8, py - dir.y * 1 + n.y * 8);
        chev.addVertex(px - dir.x * 1 + n.x * 4, py - dir.y * 1 + n.y * 4);
        chev.addVertex(px + dir.x * 3, py + dir.y * 3);
        chev.addVertex(px - dir.x * 1 - n.x * 4, py - dir.y * 1 - n.y * 4);
        chev.addVertex(px - dir.x * 1 - n.x * 8, py - dir.y * 1 - n.y * 8);
        chev.setFilled(true); chev.setFillColor(col); chev.setColor(col);
        background.add(chev);
        GLabel l = Ui.label(text, 0, 0, Cyber.mono(Font.BOLD, 11), col);
        double ly = py + 31 < GameMap.HEIGHT - 4 ? py + 31 : py - 21;
        l.setLocation(px - l.getWidth() / 2, ly);
        background.add(l);
    }

    private GPolygon segment(Vec a, Vec b, double hw, Color col) {
        Vec d = b.sub(a).normalized();
        Vec n = new Vec(-d.y * hw, d.x * hw);
        GPolygon p = new GPolygon();
        p.addVertex(a.x + n.x, a.y + n.y);
        p.addVertex(b.x + n.x, b.y + n.y);
        p.addVertex(b.x - n.x, b.y - n.y);
        p.addVertex(a.x - n.x, a.y - n.y);
        p.setFilled(true); p.setFillColor(col); p.setColor(col);
        return p;
    }

    private void buildOverlay() {
        rangeCircle = new Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.CYAN, 22), Cyber.alpha(Cyber.CYAN, 215));
        rangeCircle.setVisible(false);
        overlay.add(rangeCircle);
        ghostRange = new Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.CYAN, 22), Cyber.alpha(Cyber.CYAN, 215));
        ghostRange.setVisible(false);
        overlay.add(ghostRange);
        ghost = new Cyber.Ring(0, 0, 40, 40, Cyber.alpha(Cyber.CYAN, 90), Cyber.CYAN);
        ghost.setLineWidth(2.2);
        ghost.setVisible(false);
        overlay.add(ghost);
        ghostX1 = new GLine(0, 0, 1, 1); ghostX2 = new GLine(0, 0, 1, 1);
        ghostX1.setColor(Cyber.RED); ghostX2.setColor(Cyber.RED);
        ghostX1.setVisible(false); ghostX2.setVisible(false);
        overlay.add(ghostX1); overlay.add(ghostX2);
        reticleRadius = new Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.YELLOW, 28), Cyber.alpha(Cyber.YELLOW, 235));
        reticleRadius.setLineWidth(2.4); reticleRadius.setDashed(true); reticleRadius.setVisible(false);
        reticleDot = new Cyber.Ring(0, 0, 10, 10, null, Cyber.YELLOW);
        reticleDot.setLineWidth(2.6); reticleDot.setVisible(false);
        reticleH = new GLine(0, 0, 1, 1); reticleV = new GLine(0, 0, 1, 1); reticleLink = new GLine(0, 0, 1, 1);
        reticleH.setColor(Cyber.YELLOW); reticleV.setColor(Cyber.YELLOW); reticleLink.setColor(Cyber.alpha(Cyber.YELLOW, 120));

        reticleH.setVisible(false); reticleV.setVisible(false); reticleLink.setVisible(false);
        reticlePlate = new Nameplate();
        overlay.add(reticleRadius); overlay.add(reticleLink); overlay.add(reticleDot); overlay.add(reticleH); overlay.add(reticleV);
        hoverPlate = new Nameplate();
        selectPlate = new Nameplate();
        ghostPlate = new Nameplate();
        overlay.add(hoverPlate); overlay.add(selectPlate); overlay.add(ghostPlate); overlay.add(reticlePlate);
    }

    // ------------------------------------------------------------------ per frame
    public void update(double dt) {
        time += dt;
        syncTowers(dt);
        syncEnemies(dt);
        updateLod();
        fx.setLod(lod);
        fx.update(dt);
        glow.setLod(lod);
        glow.update(dt);
        shake.update(dt);
        int lives = game.getLives();
        if (lastLives >= 0 && lives < lastLives) shake.kick(0.3);   // a leak jolts the camera
        lastLives = lives;
        intrusionFx.setLod(lod);
        intrusionFx.update(dt);
        syncProjectiles();
        consumeEvents();
        stepEffects(dt);
        syncMapFx();
        syncOverlay();
    }

    private void syncTowers(double dt) {
        List<Tower> marked = null;
        Boss pal = game.getPalantir();
        if (pal != null && pal.isAlive() && pal.isTelegraphing()) marked = pal.getMarkedTowers();
        for (Tower t : game.getTowerManager().getTowers()) {
            TowerSprite s = towerSprites.get(t);
            if (s == null) { s = new TowerSprite(t); towerSprites.put(t, s); towerLayer.add(s); }
            s.sync(game, dt, marked != null && marked.contains(t));
        }
        Iterator<Map.Entry<Tower, TowerSprite>> it = towerSprites.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<Tower, TowerSprite> en = it.next();
            if (!en.getKey().isAlive()) { towerLayer.remove(en.getValue()); it.remove(); }
        }
        // telegraph lines
        for (GObject o : telegraphLines) overlay.remove(o);
        telegraphLines.clear();
        if (marked != null) {
            for (Tower t : marked) {
                GLine l = new GLine(pal.getPosition().x, pal.getPosition().y, t.getPosition().x, t.getPosition().y);
                l.setColor(Ui.c(0xff3030, (int) (120 + 100 * Math.abs(Math.sin(time * 10)))));
                overlay.add(l);
                telegraphLines.add(l);
            }
        }
    }

    private void syncEnemies(double dt) {
        List<Enemy> enemies = game.getEnemyManager().getEnemies();
        for (Enemy e : enemies) {
            EnemySprite s = enemySprites.get(e);
            if (s == null) {
                s = SpriteFactory.create(e);
                enemySprites.put(e, s);
                enemyLayer.add(s);
            }
            s.sync(e, time);
            s.step(dt);
            syncHpBar(e);
        }
        Iterator<Map.Entry<Enemy, EnemySprite>> it = enemySprites.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<Enemy, EnemySprite> en = it.next();
            Enemy e = en.getKey();
            if (!e.isAlive() || e.isStored()) {
                enemyLayer.remove(en.getValue());
                it.remove();
                Cyber.Bar bar = hpBars.remove(e);
                if (bar != null) hpLayer.remove(bar);
                if (!e.isAlive() && !e.hasLeaked() && animated.size() < effectCap()) {
                    Animated fx = e.getType().hasChildren() ? SpriteFactory.createSplitEffect(e) : SpriteFactory.createDeathEffect(e);
                    if (fx instanceof GObject) { effectLayer.add((GObject) fx); animated.add(fx); }
                }
            }
        }
    }

    /** Compact HP bar centred just above a damaged, non-boss enemy; created lazily, mutated every frame. */
    private void syncHpBar(Enemy e) {
        boolean show = !e.isBoss() && e.isAlive() && e.getHp() < e.getMaxHp() - 1e-9;
        Cyber.Bar bar = hpBars.get(e);
        if (!show) {
            if (bar != null) bar.setVisible(false);
            return;
        }
        double r = e.getRadius();
        double w = Math.max(16, Math.min(48, r * 2.0 + 4));
        double h = r > 14 ? 5 : 4;
        if (bar == null) {
            bar = new Cyber.Bar(0, 0, w, h, 0).colors(Cyber.GREEN, new Color(4, 6, 14, 215), new Color(0, 0, 0, 235));
            hpLayer.add(bar);
            hpBars.put(e, bar);
        }
        double f = e.getHpFraction();
        bar.setSize(w, h);
        double bx = e.getPosition().x - w / 2, by = e.getPosition().y - r - h - 6;
        if (bx != bar.getX() || by != bar.getY()) bar.setLocation(bx, by);
        if (f != bar.getValue()) { bar.setValue(f); bar.setFill(Cyber.hpColor(f)); }
        if (!bar.isVisible()) bar.setVisible(true);
    }

    private void syncProjectiles() {
        double now = game.getTime();
        for (Projectile p : game.getCombat().getProjectiles()) {
            ProjectileSprite s = projectileSprites.get(p);
            if (s == null) {
                s = ProjectileSprites.create(p);
                projectileSprites.put(p, s);
                projectileLayer.add(s);
            }
            s.sync(p, now);
        }
        Iterator<Map.Entry<Projectile, ProjectileSprite>> it = projectileSprites.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<Projectile, ProjectileSprite> en = it.next();
            if (!en.getKey().isAlive()) { projectileLayer.remove(en.getValue()); it.remove(); }
        }
    }

    /** Picks the level of detail for this frame from the number of sprites on screen (with hysteresis). */
    private void updateLod() {
        if (LOD_FORCED >= 0) { lod = LOD_FORCED; return; }
        int load = enemySprites.size() + towerSprites.size() / 2;
        int want = load >= LOD_FINE_LOAD ? 2 : load >= LOD_DECOR_LOAD ? 1 : 0;
        if (want > lod) lod = want;
        else if (lod == 2 && load < LOD_FINE_LOAD * 0.8) lod = load >= LOD_DECOR_LOAD ? 1 : 0;
        else if (lod == 1 && load < LOD_DECOR_LOAD * 0.8) lod = 0;
        lod = Math.max(lod, GraphicsSettings.get().quality().minLod);   // LOW never draws full detail
    }

    /** Current level of detail (0 = full detail). */
    public int getLod() { return lod; }

    /** Effect cap for the current level of detail (applies separately to legacy and animated effects). */
    private int effectCap() { return lod == 0 ? MAX_EFFECTS : lod == 1 ? MAX_EFFECTS * 5 / 8 : MAX_EFFECTS * 3 / 8; }

    /** A transient effect built from a VisualEvent (pooled together with its GObject). */
    private static final class Effect {
        GObject obj; VisualEvent ev; double t; Color base;
        Effect set(GObject o, VisualEvent e, Color b) { obj = o; ev = e; base = b; t = 0; return this; }
    }

    // pools of finished legacy effects: their GObjects stay (hidden) in the effect layer for reuse
    private final ArrayDeque<Effect> effectPool = new ArrayDeque<>();
    private final ArrayDeque<GOval> ovalPool = new ArrayDeque<>();
    private final ArrayDeque<GLine> linePool = new ArrayDeque<>();
    private final ArrayDeque<GLabel> labelPool = new ArrayDeque<>();

    private Effect effect(GObject o, VisualEvent ev, Color base) {
        Effect e = effectPool.isEmpty() ? new Effect() : effectPool.pop();
        return e.set(o, ev, base);
    }

    /** A pooled (or new) oval in the effect layer, configured like {@link Ui#oval}. */
    private GOval pooledOval(double x, double y, double w, double h, Color fill, Color outline) {
        GOval o = ovalPool.poll();
        if (o == null) { o = Ui.oval(x, y, w, h, fill, outline); effectLayer.add(o); return o; }
        o.setBounds(x, y, w, h);
        o.setFilled(fill != null);
        if (fill != null) o.setFillColor(fill);
        o.setColor(outline != null ? outline : (fill != null ? fill : Ui.TEXT));
        o.setVisible(true);
        return o;
    }

    private GLine pooledLine(Vec a, Vec b, Color col) {
        GLine l = linePool.poll();
        if (l == null) { l = new GLine(a.x, a.y, b.x, b.y); effectLayer.add(l); }
        else { l.setStartPoint(a.x, a.y); l.setEndPoint(b.x, b.y); l.setVisible(true); }
        l.setColor(col);
        return l;
    }

    private GLabel pooledLabel(String text, Font f, Color col) {
        GLabel l = labelPool.poll();
        if (l == null) { l = Ui.label(text, 0, 0, f, col); effectLayer.add(l); return l; }
        l.setLabel(text);
        l.setFont(f);
        l.setColor(col);
        l.setVisible(true);
        return l;
    }

    /** Hides a finished legacy effect and returns it and its object to the pools. */
    private void recycle(Effect e) {
        e.obj.setVisible(false);
        if (e.obj instanceof GOval) ovalPool.push((GOval) e.obj);
        else if (e.obj instanceof GLine) linePool.push((GLine) e.obj);
        else if (e.obj instanceof GLabel) labelPool.push((GLabel) e.obj);
        else effectLayer.remove(e.obj);
        e.obj = null; e.ev = null;
        effectPool.push(e);
    }

    private void consumeEvents() {
        int cap = effectCap();
        for (VisualEvent ev : game.drainEvents()) {
            lindefense.audio.AudioManager.event(ev);   // AUDIO HOOK
            // graphics-quality extras: light flashes and camera shake (both no-ops below the HIGH preset)
            if (ev.kind == VisualEvent.Kind.EXPLOSION || ev.kind == VisualEvent.Kind.ABILITY) {
                glow.flash(ev.a, ev.radius, ev.rgb);
                if (ev.radius >= 70) shake.kick(ev.kind == VisualEvent.Kind.EXPLOSION ? 0.12 : 0.08);
            } else if (ev.kind == VisualEvent.Kind.PHASE) {
                shake.kick(0.5);
            }
            if (effects.size() >= cap && ev.kind != VisualEvent.Kind.PHASE && ev.kind != VisualEvent.Kind.BANNER) continue;
            if (ev.kind == VisualEvent.Kind.BEAM || ev.kind == VisualEvent.Kind.CHAIN
                    || ev.kind == VisualEvent.Kind.HIT || ev.kind == VisualEvent.Kind.EXPLOSION) {
                if (animated.size() >= cap) continue;
                Animated fx = ProjectileSprites.createAttackEffect(ev);
                if (fx != null) {
                    effectLayer.add((GObject) fx);
                    animated.add(fx);
                    continue;
                }
            }
            if (ev.kind == VisualEvent.Kind.ABILITY) fx.onAbilityEvent(ev);
            Color col = Ui.c(ev.rgb);
            GObject o = null;
            switch (ev.kind) {
                case BEAM: case CHAIN: o = pooledLine(ev.a, ev.b, col); break;
                case HIT: o = pooledOval(ev.a.x - ev.radius, ev.a.y - ev.radius, ev.radius * 2, ev.radius * 2, Ui.withAlpha(col, 200), null); break;
                case EXPLOSION: case ABILITY: case TELEPORT: case DEATH: case SPLIT: case PHASE:
                    o = pooledOval(ev.a.x - 4, ev.a.y - 4, 8, 8, ev.kind == VisualEvent.Kind.EXPLOSION ? Ui.withAlpha(col, 90) : null, col);
                    break;
                case TEXT: {
                    GLabel l = pooledLabel(ev.text, Cyber.mono(Font.BOLD, 13), col);
                    l.setLocation(ev.a.x - l.getWidth() / 2, ev.a.y);
                    o = l;
                    break;
                }
                case BANNER: screen.flashBanner(ev.text, col, ev.duration); break;
                default: break;
            }
            if (ev.kind == VisualEvent.Kind.PHASE) {
                GLabel l = pooledLabel(ev.text, Cyber.display(Font.BOLD, 36), col);
                l.setLocation(Math.max(8, Math.min(GameMap.WIDTH - l.getWidth() - 8, ev.a.x - l.getWidth() / 2)), Math.max(l.getHeight() + 4, ev.a.y - 60));
                effects.add(effect(l, VisualEvent.text(ev.a, ev.text, ev.rgb), col));
            }
            if (o != null) effects.add(effect(o, ev, col));
        }
    }

    private void stepEffects(double dt) {
        for (int i = effects.size() - 1; i >= 0; i--) {
            Effect e = effects.get(i);
            e.t += dt;
            double f = Math.min(1, e.t / e.ev.duration);
            if (f >= 1) {
                int last = effects.size() - 1;
                effects.set(i, effects.get(last));
                effects.remove(last);
                recycle(e);
                continue;
            }
            int alpha = (int) (255 * (1 - f));
            switch (e.ev.kind) {
                case EXPLOSION: case ABILITY: case TELEPORT: case DEATH: case SPLIT: case PHASE: {
                    double r = e.ev.radius * (e.ev.kind == VisualEvent.Kind.ABILITY ? (0.2 + 0.8 * f) : (0.3 + 0.7 * f));
                    GOval ov = (GOval) e.obj;
                    ov.setBounds(e.ev.a.x - r, e.ev.a.y - r, 2 * r, 2 * r);
                    ov.setColor(Ui.withAlpha(e.base, alpha));
                    if (ov.isFilled()) ov.setFillColor(Ui.withAlpha(e.base, alpha / 3));
                    break;
                }
                case TEXT: e.obj.move(0, -30 * dt); e.obj.setColor(Ui.withAlpha(e.base, alpha)); break;
                default: e.obj.setColor(Ui.withAlpha(e.base, alpha)); break;
            }
        }
        for (int i = animated.size() - 1; i >= 0; i--) {
            Animated a = animated.get(i);
            if (!a.step(dt)) { effectLayer.remove((GObject) a); animated.remove(i); }
        }
    }

    private void syncMapFx() {
        pulses.setTime(time);
        if (map instanceof SiliconCircuit) {
            SiliconCircuit sc = (SiliconCircuit) map;
            for (int i = 0; i < padFill.size(); i++) {
                double c = sc.getPadCharge(i);
                padFill.get(i).setFillColor(Ui.c(0x7fd8a8, (int) (20 + 120 * c)));
            }
            int lane = sc.getShortedLane();
            for (GObject o : shortFx) mapFx.remove(o);
            shortFx.clear();
            if (lane >= 0) {
                Path r = map.getRoutes().get(lane);
                List<Vec> w = r.getWaypoints();
                for (int i = 0; i + 1 < w.size(); i++) {
                    GPolygon p = segment(w.get(i), w.get(i + 1), GameMap.TRACK_HALF_WIDTH, Ui.c(0xffffff, (int) (90 + 90 * Math.abs(Math.sin(time * 30)))));
                    mapFx.add(p);
                    shortFx.add(p);
                }
            }
        }
        if (ventRect != null) {
            LegacyMonolith lm = (LegacyMonolith) map;
            int f = lm.getVentedFloor();
            ventRect.setVisible(f >= 0);
            if (f >= 0) {
                double[] band = lm.getFloors()[f];
                ventRect.setBounds(0, band[0], GameMap.WIDTH, band[1] - band[0]);
                ventRect.setFillColor(Ui.c(0xff6a00, (int) (35 + 25 * Math.sin(time * 4))));
            }
        }
        if (!hazardFx.isEmpty()) {
            AbandonedDataCenter dc = (AbandonedDataCenter) map;
            int active = dc.getActiveHazard(), warned = dc.getWarnedHazard();
            for (int i = 0; i < hazardFx.size(); i++) {
                boolean on = i == active || i == warned;
                Color col = null;
                if (i == active) col = Ui.c(dc.getHazards().get(i).rgb, (int) (70 + 45 * Math.sin(time * 9)));
                else if (i == warned) col = Ui.c(0xffd23b, ((int) (time * 8)) % 2 == 0 ? 120 : 30);
                for (GPolygon p : hazardFx.get(i)) {
                    p.setVisible(on);
                    if (col != null) { p.setFillColor(col); p.setColor(col); }
                }
            }
        }
        if (stormRect != null) {
            HallucinationCanyon hc = (HallucinationCanyon) map;
            stormRect.setVisible(hc.isStormActive());
            if (hc.isStormActive()) stormRect.setFillColor(Ui.c(0xff8cf0, (int) (25 + 25 * Math.abs(Math.sin(time * 6)))));
        }
    }

    private void syncOverlay() {
        Tower sel = screen.getSelectedTower();
        TowerType placing = screen.getPlacing();
        Vec mouse = screen.getMouseWorld();
        Tower hover = null;
        if (placing != null && mouse != null && insideWorld(mouse)) {
            double r = TowerCatalog.get(placing).statsForTier(0).range * map.towerRangeMultiplier(game, null) * game.getGlobalRangeMultiplier();
            String problem = game.getTowerManager().placementProblem(placing, mouse);
            boolean ok = problem == null;
            Color col = ok ? Cyber.CYAN : Cyber.RED;
            ghostRange.set(mouse.x, mouse.y, r);
            ghostRange.setFill(Cyber.alpha(col, ok ? 20 : 30)); ghostRange.setLine(Cyber.alpha(col, ok ? 215 : 235));
            ghostRange.setDashed(!ok); ghostRange.setPhase(time * 14);
            ghostRange.setVisible(true);
            double tr = TowerCatalog.get(placing).radius;
            ghost.set(mouse.x, mouse.y, tr);
            ghost.setFill(Cyber.alpha(col, ok ? 85 : 110)); ghost.setLine(col);
            ghost.setVisible(true);
            ghostX1.setVisible(!ok); ghostX2.setVisible(!ok);
            if (!ok) {
                double k = tr * 0.55;
                ghostX1.setStartPoint(mouse.x - k, mouse.y - k); ghostX1.setEndPoint(mouse.x + k, mouse.y + k);
                ghostX2.setStartPoint(mouse.x - k, mouse.y + k); ghostX2.setEndPoint(mouse.x + k, mouse.y - k);
            }
            ghostPlate.set(ok ? placing.displayName : problem, ok ? Ui.money(lindefense.tower.Shop.priceOf(game, placing)) : null, col);
            placePlate(ghostPlate, mouse, tr);
            ghostPlate.setVisible(true);
            rangeCircle.setVisible(false);
        } else {
            ghostRange.setVisible(false); ghost.setVisible(false); ghostPlate.setVisible(false);
            ghostX1.setVisible(false); ghostX2.setVisible(false);
            if (sel != null && sel.isAlive()) {
                rangeCircle.set(sel.getPosition().x, sel.getPosition().y, sel.effectiveRange(game));
                rangeCircle.setVisible(true);
            } else {
                rangeCircle.setVisible(false);
            }
            if (mouse != null && insideWorld(mouse)) hover = game.getTowerManager().towerAt(mouse);
        }
        syncReticle(mouse);
        // nameplates: tower under the cursor and the selected tower
        Tower selShow = sel != null && sel.isAlive() && placing == null ? sel : null;
        showPlate(selectPlate, selShow);
        showPlate(hoverPlate, hover != null && hover != selShow ? hover : null);
    }

    /**
     * Targeting-mode reticle: snaps to the spot the sim will use (the nearest track bend within the ability's snap range
     * if it has one, otherwise the nearest point on the track) and previews the effect radius.
     */
    private void syncReticle(Vec mouse) {
        Tower caster = screen.getTargetingTower();
        boolean on = caster != null && caster.isAlive() && caster.getAbility() != null && mouse != null && insideWorld(mouse);
        reticleRadius.setVisible(on); reticleDot.setVisible(on); reticleH.setVisible(on); reticleV.setVisible(on);
        reticleLink.setVisible(on); reticlePlate.setVisible(on);
        if (!on) return;
        AbilityDef a = caster.getAbility();
        Vec at = null;
        boolean bend = false;
        if (a.has("snapRange")) {
            List<Effects.TrackPoint> bends = game.getEffects().bendsInRange(mouse, a.p("snapRange"));
            if (!bends.isEmpty()) { at = bends.get(0).position; bend = true; }
        }
        if (at == null) {
            Effects.TrackPoint tp = game.getEffects().nearestTrackPoint(mouse);
            if (tp != null) at = tp.position;
        }
        if (at == null) { reticleRadius.setVisible(false); reticleDot.setVisible(false); reticleH.setVisible(false); reticleV.setVisible(false); reticleLink.setVisible(false); reticlePlate.setVisible(false); return; }
        Color col = Ui.c(caster.getType().primaryRgb);
        col = Cyber.lerp(col, Cyber.YELLOW, 0.5);
        double r = a.p("radius", 60);
        reticleRadius.set(at.x, at.y, r);
        reticleRadius.setFill(Cyber.alpha(col, 30)); reticleRadius.setLine(Cyber.alpha(col, 240));
        reticleRadius.setPhase(time * 18);
        double pr = 11 + 2 * Math.sin(time * 8);
        reticleDot.set(at.x, at.y, pr); reticleDot.setLine(col);
        double k = pr + 8;
        reticleH.setStartPoint(at.x - k, at.y); reticleH.setEndPoint(at.x + k, at.y);
        reticleV.setStartPoint(at.x, at.y - k); reticleV.setEndPoint(at.x, at.y + k);
        reticleH.setColor(col); reticleV.setColor(col);
        reticleLink.setStartPoint(mouse.x, mouse.y); reticleLink.setEndPoint(at.x, at.y);
        reticlePlate.set(a.name, bend ? "snaps to track bend" : "on the track", col);
        placePlate(reticlePlate, at, Math.max(r, pr));
    }

    private void showPlate(Nameplate p, Tower t) {
        if (t == null) { p.setVisible(false); return; }
        TowerType ty = t.getType();
        p.set(ty.displayName, t.getTierLabel(), Cyber.lerp(Ui.c(ty.primaryRgb), Color.WHITE, 0.35));
        placePlate(p, t.getPosition(), t.getRadius());
        p.setVisible(true);
    }

    /** Puts a plate above (or below, near the top edge) a circle, clamped inside the world. */
    private void placePlate(Nameplate p, Vec c, double r) {
        double w = p.getPlateWidth();
        double x = Math.max(4, Math.min(GameMap.WIDTH - w - 4, c.x - w / 2));
        double y = c.y - r - Nameplate.HEIGHT - 12;
        if (y < 4) y = c.y + r + 12;
        y = Math.min(y, GameMap.HEIGHT - Nameplate.HEIGHT - 4);
        p.place(x, y);
    }

    /** Reserves {@code dock} logical px under the HUD for the boss dock by shrinking the playfield uniformly. */
    public void setDock(double dock) {
        viewDock = Math.max(0, Math.min(170, dock));   // boss dock + the PATCH NOTES strip
        viewScale = (Ui.WORLD_H - viewDock) / Ui.WORLD_H;
    }

    /** Inverse of {@link #toWorld}: the logical point {x, y} where world point {@code w} is drawn (boss dock / strip aware). */
    public double[] toLogical(Vec w) {
        double offX = (Ui.WORLD_W - GameMap.WIDTH * viewScale) / 2;
        return new double[] { Ui.WORLD_X + offX + w.x * viewScale, Ui.WORLD_Y + viewDock + w.y * viewScale };
    }

    /** Maps a logical point (screen layout space) into world coordinates, or null outside the playfield. */
    public Vec toWorld(double lx, double ly) {
        double offX = (Ui.WORLD_W - GameMap.WIDTH * viewScale) / 2;
        Vec p = new Vec((lx - Ui.WORLD_X - offX) / viewScale, (ly - Ui.WORLD_Y - viewDock) / viewScale);
        return insideWorld(p) ? p : null;
    }

    @Override public void paint(Graphics g) {
        Graphics2D g2 = (Graphics2D) g.create();
        try {
            Cyber.quality(g2);
            double offX = (Ui.WORLD_W - GameMap.WIDTH * viewScale) / 2;
            g2.translate(Ui.WORLD_X + offX, Ui.WORLD_Y + viewDock);
            g2.translate(shake.offsetX(), shake.offsetY());   // HIGH preset camera shake (drawing only)
            g2.scale(viewScale, viewScale);
            g2.clipRect(0, 0, GameMap.WIDTH, GameMap.HEIGHT);
            int prevLod = Thick.setLevel(lod);
            try {
                super.paint(g2);
            } finally {
                Thick.setLevel(prevLod);
            }
        } finally {
            g2.dispose();
        }
    }

    public static boolean insideWorld(Vec p) {
        return p.x >= 0 && p.y >= 0 && p.x <= GameMap.WIDTH && p.y <= GameMap.HEIGHT;
    }

    /** Enemy under a world point, or null. */
    public Enemy pickEnemy(Vec p) {
        Enemy best = null;
        double bestD = Double.MAX_VALUE;
        for (Enemy e : game.getEnemyManager().getEnemies()) {
            double d = e.getPosition().dist(p);
            if (d <= e.getRadius() + 6 && d < bestD) { bestD = d; best = e; }
        }
        return best;
    }
}
