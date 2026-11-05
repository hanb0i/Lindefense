package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;
import lindefense.map.Path;
import lindefense.tower.AbilityDef;
import lindefense.tower.AttackKind;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.UpgradeDef;
import lindefense.ui.sprites.EnemySprite;
import lindefense.ui.sprites.SpriteFactory;
import lindefense.ui.sprites.towers.TowerIcons;

/**
 * The Catalog (main menu): every enemy, boss, tower and hero with its sprite and what it does. Four tabs, a list of
 * entries on the left and a detail card on the right. Every number and description is read from the data tables
 * ({@link EnemyType}, {@link TowerCatalog}), so the catalog always matches the game.
 */
public final class CatalogScreen extends GCompound {
    private static final long serialVersionUID = 1L;

    /** Catalog sections. */
    public enum Tab { ENEMIES("ENEMIES"), BOSSES("BOSSES"), TOWERS("TOWERS"), HEROES("HEROES");
        final String label; Tab(String l) { label = l; } }

    private static final double LIST_X = 50, LIST_W = 420, LIST_Y = 168, ROW_H = 36;
    private static final double CARD_X = 500, CARD_Y = 150, CARD_W = 1050, CARD_H = 800;

    private final LindefenseProgram app;
    private final List<UIButton> chrome = new ArrayList<>();
    private final List<UIButton> rows = new ArrayList<>();
    private final GCompound listLayer = new GCompound();
    private final GCompound card = new GCompound();
    private final List<UIButton> tabs = new ArrayList<>();
    private Tab tab = Tab.ENEMIES;
    private int selected;
    private EnemySprite liveSprite;
    private Enemy liveEnemy;
    private double time;

    public CatalogScreen(LindefenseProgram app) {
        this.app = app;
        add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.BG, Ui.BG));
        for (int y = 0; y < Ui.H; y += 40) { acm.graphics.GLine l = new acm.graphics.GLine(0, y + 0.5, Ui.W, y + 0.5); l.setColor(Cyber.alpha(Cyber.CYAN, 12)); add(l); }
        add(Ui.label(Cyber.spaced("// field database"), LIST_X, 50, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.MAGENTA, 230)));
        add(Ui.label("CATALOG", LIST_X, 98, Cyber.display(Font.BOLD, 48), Cyber.TEXT));
        UIButton back = new UIButton(Ui.W - 50 - 180, 52, 180, 46, "BACK  [ESC]", Cyber.display(Font.BOLD, 18), () -> app.showMenu());
        back.setAccent(Cyber.MAGENTA);
        add(back); chrome.add(back);
        double tx = 330;
        for (Tab t : Tab.values()) {
            UIButton b = new UIButton(tx, 58, 150, 40, t.label + " (" + entries(t).size() + ")", Cyber.display(Font.BOLD, 16), () -> setTab(t));
            b.setAccent(t == Tab.HEROES ? Cyber.YELLOW : t == Tab.BOSSES ? Cyber.RED : Cyber.CYAN);
            add(b); chrome.add(b); tabs.add(b);
            tx += 158;
        }
        add(listLayer);
        add(new Cyber.Chamfer(CARD_X, CARD_Y, CARD_W, CARD_H, 22).fill(new Color(6, 10, 24, 240)).border(Cyber.alpha(Cyber.CYAN, 160)).glow(0.6).ticks(true));
        add(card);
        setTab(Tab.ENEMIES);
    }

    /** Entries of a tab, in game order. */
    public static List<Object> entries(Tab t) {
        List<Object> l = new ArrayList<>();
        switch (t) {
            case ENEMIES: for (EnemyType e : EnemyType.values()) if (!e.isBoss()) l.add(e); break;
            case BOSSES: for (EnemyType e : EnemyType.values()) if (e.isBoss()) l.add(e); break;
            case TOWERS: for (TowerType ty : TowerType.shopTowers()) l.add(ty); break;
            case HEROES: for (TowerType ty : TowerType.heroes()) l.add(ty); break;
            default: break;
        }
        return l;
    }

    public Tab getTab() { return tab; }

    public void setTab(Tab t) {
        tab = t;
        selected = 0;
        for (int i = 0; i < tabs.size(); i++) tabs.get(i).setSelected(Tab.values()[i] == t);
        rebuildList();
        rebuildCard();
    }

    public void select(int i) {
        selected = Math.max(0, Math.min(entries(tab).size() - 1, i));
        rebuildList();
        rebuildCard();
    }

    private void rebuildList() {
        listLayer.removeAll();
        rows.clear();
        List<Object> es = entries(tab);
        double rh = Math.min(ROW_H, (Ui.H - 30 - LIST_Y) / Math.max(1, es.size()));
        for (int i = 0; i < es.size(); i++) {
            final int idx = i;
            Object o = es.get(i);
            String name = o instanceof EnemyType ? ((EnemyType) o).displayName : ((TowerType) o).displayName;
            UIButton b = new UIButton(LIST_X, LIST_Y + i * rh, LIST_W, rh - 4, name, Cyber.display(Font.BOLD, 16), () -> select(idx));
            b.setSelected(i == selected);
            if (o instanceof TowerType) b.setAccent(Cyber.lerp(Ui.c(((TowerType) o).primaryRgb), Cyber.CYAN, 0.3));
            else if (((EnemyType) o).isBoss()) b.setAccent(Cyber.RED);
            listLayer.add(b);
            rows.add(b);
        }
    }

    // ------------------------------------------------------------------ detail card
    private double y;
    private static final double TX = CARD_X + 330, TW = CARD_W - 330 - 40;

    private void line(String s, Font f, Color c, double x, double w) {
        for (String l : Ui.wrap(s, f, w)) { y += f.getSize() + 5; card.add(Ui.label(l, x, y, f, c)); }
    }

    private void heading(String s) {
        y += 18;
        card.add(Ui.label(Cyber.spaced("// " + s), TX, y, Cyber.mono(Font.BOLD, 11), Cyber.CYAN));
        y += 2;
    }

    private void rebuildCard() {
        card.removeAll();
        liveSprite = null; liveEnemy = null;
        List<Object> es = entries(tab);
        if (es.isEmpty()) return;
        Object o = es.get(selected);
        y = CARD_Y + 40;
        if (o instanceof EnemyType) enemyCard((EnemyType) o); else towerCard((TowerType) o);
    }

    private void enemyCard(EnemyType t) {
        // live, animated sprite on a tiny loop path
        Path p = new Path("catalog", -1, -1, 1, -1, 1, 1, -1, 1, -1, -1);
        liveEnemy = t.isBoss() ? new Boss(t, EnumSet.noneOf(Modifier.class), p, 0, 0, 1.0, 1.0) : new Enemy(t, EnumSet.noneOf(Modifier.class), p, 0, 0, 1.0, 1.0);
        liveSprite = SpriteFactory.create(liveEnemy);
        GCompound holder = new GCompound();
        holder.add(liveSprite);
        double scale = t.isBoss() ? Math.min(1.1, 42 / Math.max(6, t.radius)) : Math.min(5.0, 95 / Math.max(6, t.radius));
        holder.scale(scale);
        holder.setLocation(CARD_X + 165, CARD_Y + 230);
        card.add(holder);
        card.add(Ui.label(t.displayName, TX, y + 10, Cyber.display(Font.BOLD, 40), t.isBoss() ? Cyber.RED : Cyber.TEXT));
        y += 18;
        String cls = t.isBoss() ? t.getBossClass().label + "-CLASS BOSS" : t.isSortingAlgorithm() ? "SORTING ALGORITHM" : t.isLinkedList() ? "LINKED LIST" : "DATA STRUCTURE";
        y += 16; card.add(Ui.label(cls, TX, y, Cyber.mono(Font.BOLD, 13), t.isBoss() ? Cyber.RED : Cyber.MAGENTA));
        heading("stats");
        statGrid(new String[][] {
            { "health", Cyber.commas(t.baseHp) + (t.isBoss() ? "" : " layers") }, { "speed", Ui.fmt(t.speed) + "x" },
            { "reward", "$" + t.reward }, { "lives cost", String.valueOf(t.lives) },
            { "armour", (int) Math.round(t.getArmor() * 100) + "%" },
            { t.isBoss() ? "class" : "mechanic", t.isBoss() ? t.getBossClass().label : t.mechanic.name().replace('_', ' ').toLowerCase() } });
        heading("what it does");
        line(t.description, Cyber.body(Font.PLAIN, 16), Cyber.TEXT, TX, TW);
        List<String> traits = new ArrayList<>();
        if (t.isLeadBody()) traits.add("Lead-type: Sharp damage cannot hurt it.");
        if (t.isCeramicBody()) traits.add("Ceramic outer layer: Blunt, Kinetic and Sonic damage deal x2.");
        if (t.hasInnateCamo()) traits.add("Always Camo: needs detection to be targeted.");
        if (t.getWeakHitThreshold() > 0) traits.add("Weak hits (under " + t.getWeakHitThreshold() + " damage) are halved.");
        if (t.hasChildren()) {
            StringBuilder sb = new StringBuilder("Releases ");
            EnemyType[] ch = t.getChildTypes(); int[] n = t.getChildCounts();
            for (int i = 0; i < ch.length; i++) { if (i > 0) sb.append(" + "); sb.append(n[i]).append(" x ").append(ch[i].displayName); }
            traits.add(sb.append(" when destroyed.").toString());
        }
        if (t.isFast()) traits.add("Fast: a priority target for rapid-fire towers.");
        String boss = bossNote(t);
        if (boss != null) traits.add(boss);
        if (t.isBoss()) traits.add("Bosses take full damage from every attack; freezes and stuns do not work on them and slows are weaker. Rohan's slows still apply.");
        if (!traits.isEmpty()) { heading("traits"); for (String s : traits) line("•  " + s, Cyber.body(Font.PLAIN, 15), Cyber.MUTED, TX, TW); }
        heading("modifiers it can carry");
        line("Camo (needs detection)  •  Regrow (heals over time)  •  Fortified (double HP)", Cyber.body(Font.PLAIN, 14), Cyber.MUTED, TX, TW);
    }

    /** Campaign notes for each boss (debut wave and special rules). */
    static String bossNote(EnemyType t) {
        switch (t) {
            case BELLARMINE_COLLEGE_PREP: return "Debuts on wave 40 as the first MOAB-class boss.";
            case SW_RESOURCE_CONSULTANT: return "Debuts on wave 60. Low-damage towers struggle: bring heavy hitters (Ronil, Zethos, DeepSeek).";
            case THREE_COM: return "Debuts on wave 80; the largest HP pool before the finale.";
            case LOCKHEED_MARTIN: return "Debuts on wave 90. Camo and very fast: you need detection (Perplexity, Grok, or Gemini / Llama after their second upgrade).";
            case PALANTIR: return "Wave 100 final boss. Armour 60% / 35% / 10% across three phases (faster each phase, Lockheed escorts in phase 3); immune to control in phase 1. "
                + "Predictive Surveillance marks your highest-investment towers for 3 s, then disrupts them for 8 s (-50% speed, -30% range, abilities locked). Towers near Perplexity U2 are immune.";
            default: return null;
        }
    }

    private void statGrid(String[][] cells) {
        double x0 = TX, cw = TW / 3;
        for (int i = 0; i < cells.length; i++) {
            double cx = x0 + (i % 3) * cw, cy = y + 6 + (i / 3) * 46;
            card.add(Ui.label(Cyber.spaced(cells[i][0]), cx, cy + 12, Cyber.mono(Font.BOLD, 10), Cyber.alpha(Cyber.CYAN, 190)));
            card.add(Ui.label(cells[i][1], cx, cy + 34, Cyber.mono(Font.BOLD, 17), Cyber.TEXT));
        }
        y += 6 + ((cells.length + 2) / 3) * 46;
    }

    private void towerCard(TowerType t) {
        TowerDef d = TowerCatalog.get(t);
        TowerStats s = d.baseStats;
        Color accent = Cyber.lerp(Ui.c(t.primaryRgb), Color.WHITE, 0.3);
        GCompound icon = TowerIcons.create(t, 0, 200);
        icon.setLocation(CARD_X + 165, CARD_Y + 170);
        card.add(icon);
        if (d.upgrades.length > 0) {
            GCompound max = TowerIcons.create(t, d.upgrades.length, 150);
            max.setLocation(CARD_X + 165, CARD_Y + 420);
            card.add(max);
            card.add(Ui.label("BASE", CARD_X + 145, CARD_Y + 292, Cyber.mono(Font.BOLD, 12), Cyber.MUTED));
            GLabel ml = Ui.label("MAX: " + d.tierLabels[d.upgrades.length], 0, CARD_Y + 520, Cyber.mono(Font.BOLD, 12), Cyber.YELLOW);
            ml.setLocation(CARD_X + 165 - ml.getWidth() / 2, CARD_Y + 520);
            card.add(ml);
        }
        card.add(Ui.label(t.displayName, TX, y + 10, Cyber.display(Font.BOLD, 40), accent));
        y += 18;
        String price = t.isHero() ? "HERO STORE  " + Ui.money(d.unlockCost) + "  //  deploy free, once per match" : Ui.money(d.baseCost) + "  //  " + t.faction.label.toUpperCase() + "  //  full path " + Ui.money(d.totalCost());
        y += 16; card.add(Ui.label(d.subtitle, TX, y, Cyber.body(Font.BOLD, 15), Cyber.MUTED));
        y += 20; card.add(Ui.label(price, TX, y, Cyber.mono(Font.BOLD, 13), Cyber.YELLOW));
        heading("what it does");
        line(d.description, Cyber.body(Font.PLAIN, 15), Cyber.TEXT, TX, TW);
        heading(HeroStatText.usesUnits(t) ? HeroStatText.attackName(t).toLowerCase() : "base attack");
        if (HeroStatText.usesUnits(t)) {
            for (String l : HeroStatText.attackLines(t)) line(l, Cyber.mono(Font.BOLD, 14), Cyber.TEXT, TX, TW);
        } else {
            String kind = s.kind == AttackKind.PULSE ? "pulse" : s.kind == AttackKind.CHAIN ? "chain" : s.kind == AttackKind.INSTANT ? "beam" : s.kind == AttackKind.CUSTOM ? "special" : s.kind == AttackKind.NONE ? "support" : "projectile";
            line(Ui.fmt(s.hit.damage) + " " + s.hit.type.label.toLowerCase() + " dmg  •  every " + Ui.fmt(s.interval()) + "s  •  range " + (s.hasUnlimitedRange() ? "whole map" : String.valueOf((int) s.range)) + "  •  pierce " + s.pierce + "  •  " + kind
                + (s.splashRadius > 0 ? "  •  splash " + (int) s.splashRadius : "") + (s.seesCamo ? "  •  camo detection" : ""), Cyber.mono(Font.BOLD, 14), Cyber.TEXT, TX, TW);
        }
        if (d.upgrades.length > 0) {
            heading("upgrade path");
            for (int i = 0; i < d.upgrades.length; i++) {
                UpgradeDef u = d.upgrades[i];
                y += 4;
                line((i + 1) + ".  " + u.name + "   " + Ui.money(u.cost), Cyber.display(Font.BOLD, 16), Cyber.YELLOW, TX, TW);
                line(u.description, Cyber.body(Font.PLAIN, 13), Cyber.MUTED, TX + 22, TW - 22);
            }
        }
        AbilityDef a = d.ability;
        heading("active ability");
        if (a == null) line("None: heroes are passive and grow through their upgrades.", Cyber.body(Font.PLAIN, 14), Cyber.MUTED, TX, TW);
        else {
            line(a.name + "   (" + (int) a.cooldown + " s cooldown)", Cyber.display(Font.BOLD, 17), Cyber.MAGENTA, TX, TW);
            if (lindefense.tower.TowerCatalog.abilityNeedsUnlock(d.type)) {
                line("Locked: buy it for " + Ui.money(lindefense.tower.TowerCatalog.ABILITY_UNLOCK_COST) + " once the tower has every upgrade.", Cyber.mono(Font.BOLD, 13), Cyber.YELLOW, TX, TW);
            }
            line(a.description, Cyber.body(Font.PLAIN, 14), Cyber.TEXT, TX, TW);
        }
    }

    // ------------------------------------------------------------------ input / frame
    private List<UIButton> buttons() { List<UIButton> l = new ArrayList<>(chrome); l.addAll(rows); return l; }

    public void mousePressed(double lx, double ly) {
        for (UIButton b : buttons()) if (b.hit(lx, ly) && b.click()) return;
    }

    public void mouseMoved(double lx, double ly) {
        for (UIButton b : buttons()) b.setHover(b.hit(lx, ly));
    }

    /** Up / down step through the list, left / right switch tabs, Esc goes back. */
    public void keyPressed(java.awt.event.KeyEvent e) {
        switch (e.getKeyCode()) {
            case java.awt.event.KeyEvent.VK_ESCAPE: app.showMenu(); break;
            case java.awt.event.KeyEvent.VK_DOWN: select(selected + 1); break;
            case java.awt.event.KeyEvent.VK_UP: select(selected - 1); break;
            case java.awt.event.KeyEvent.VK_RIGHT: setTab(Tab.values()[(tab.ordinal() + 1) % Tab.values().length]); break;
            case java.awt.event.KeyEvent.VK_LEFT: setTab(Tab.values()[(tab.ordinal() + Tab.values().length - 1) % Tab.values().length]); break;
            default: break;
        }
    }

    public void frame(double dt) {
        time += dt;
        for (UIButton b : buttons()) b.animate(dt);
        if (liveSprite != null && liveEnemy != null) {
            liveEnemy.setDistance((time * 0.3) % 1.0);
            liveSprite.sync(liveEnemy, time);
            liveSprite.setLocation(0, 0);
        }
    }
}
