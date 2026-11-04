package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import acm.graphics.GLine;
import acm.graphics.GObject;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import lindefense.combat.HitSpec;
import lindefense.enemy.Enemy;
import lindefense.enemy.Modifier;
import lindefense.sim.Game;
import lindefense.tower.AbilityDef;
import lindefense.tower.AttackKind;
import lindefense.tower.Faction;
import lindefense.tower.Shop;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.UpgradeDef;
import lindefense.tower.behavior.KimiBehavior;

/**
 * Right-hand panel: the tower shop (faction tabs or an ALL view showing every buildable tower grouped by faction) and
 * the context info panel (selected tower with stat grid / upgrade path / targeting / ability / sell, shop tower preview,
 * enemy inspector). The info panel starts right below whichever card grid is shown, so faction view has no dead gap.
 * Shop cells show live affordability; a floating tooltip explains the hovered cell. The info section is rebuilt only when
 * the selection (or something that changes its buttons) changes; live numbers are refreshed by mutating labels.
 * Upgrade pips and labels are derived from {@code TowerDef.upgrades} / {@code tierLabels}, never hardcoded.
 */
public final class SidePanel extends GCompound {
    private static final long serialVersionUID = 1L;

    private static final Font F_MICRO = Cyber.mono(Font.BOLD, 9);
    private static final Font F_VAL = Cyber.mono(Font.BOLD, 15);
    private static final Font F_NAME = Cyber.display(Font.BOLD, 26);
    private static final Font F_SEC = Cyber.display(Font.BOLD, 16);
    private static final Font F_TXT = Cyber.body(Font.PLAIN, 12);
    private static final Font F_TXT_S = Cyber.body(Font.PLAIN, 11);

    /** One rendered shop cell. */
    private static final class Card {
        final ShopLayout.Cell cell; final UIButton button; final GLabel price; final GLabel name; final GObject icon;
        GCompound badge;   // "PLACED" tag on a hero that already stands on the map
        Card(ShopLayout.Cell cell, UIButton button, GLabel price, GLabel name, GObject icon) {
            this.cell = cell; this.button = button; this.price = price; this.name = name; this.icon = icon;
        }
    }

    private final GameScreen screen;
    private final Game game;
    private final List<UIButton> tabButtons = new ArrayList<>();
    private final UIButton allButton;
    private final UIButton helpBtn;
    private boolean compactShop;
    private static final double BRIEF_H = 96;
    private final List<Card> cards = new ArrayList<>();
    private final List<UIButton> infoButtons = new ArrayList<>();
    private final List<Runnable> dyn = new ArrayList<>();
    private final GCompound cardLayer = new GCompound();
    private final GCompound info = new GCompound();
    private final Cyber.Chamfer infoFrame;
    private double infoY = 320;

    // floating shop tooltip
    private final GCompound tip = new GCompound();
    private final Cyber.Chamfer tipFrame;
    private final GLabel tipTitle, tipSub, tipStatus;

    private Faction tab = Faction.PRIMARY;
    private boolean allMode;
    private double refresh;
    private String builtKey = "";
    private Cyber.Bar abilityBar;
    private GLabel abilityText;
    private Cyber.Bar enemyBar;

    public SidePanel(GameScreen screen) {
        this.screen = screen;
        this.game = screen.getGame();
        add(new Cyber.Chamfer(Ui.PANEL_X, -2, Ui.PANEL_W + 2, Ui.H + 4, 0).fill(new Color(5, 9, 22)).border(Cyber.alpha(Cyber.CYAN, 130)).lineWidth(2));
        add(Ui.rect(Ui.PANEL_X + 2, 0, 3, 90, Cyber.MAGENTA, Cyber.MAGENTA));
        add(Ui.label(Cyber.spaced("armory"), Ui.PANEL_X + 18, 27, Cyber.display(Font.BOLD, 22), Cyber.TEXT));
        helpBtn = new UIButton(Ui.PANEL_X + Ui.PANEL_W - 8 - 92, 8, 92, 26, "? HELP  [H]", Cyber.mono(Font.BOLD, 11), screen::toggleHelp);
        helpBtn.setAccent(Cyber.MAGENTA);
        add(helpBtn);

        double x = Ui.PANEL_X + 8;
        double tabW = 60;
        for (Faction f : ShopLayout.shopFactions()) {
            UIButton b = new UIButton(x, 40, tabW, 30, f.label.toUpperCase(), Cyber.displayCompact(Font.BOLD, 12), () -> setTab(f));
            b.setAccent(Ui.c(f.rgb));
            tabButtons.add(b);
            add(b);
            x += tabW + 3;
        }
        allButton = new UIButton(x, 40, Ui.PANEL_X + Ui.PANEL_W - 8 - x, 30, "ALL", Cyber.display(Font.BOLD, 14), this::toggleAll);
        allButton.setAccent(Cyber.YELLOW);
        add(allButton);
        add(cardLayer);

        infoFrame = new Cyber.Chamfer(Ui.PANEL_X + 8, infoY, Ui.PANEL_W - 16, Ui.H - infoY - 8, 14).fill(new Color(7, 12, 28, 235)).border(Cyber.alpha(Cyber.CYAN, 150)).glow(0.5).ticks(true);
        add(infoFrame);
        add(info);

        tipFrame = new Cyber.Chamfer(0, 0, 280, 78, 10).fill(new Color(5, 9, 22, 245)).border(Cyber.CYAN).glow(0.8).scan(false);
        tip.add(tipFrame);
        tipTitle = Ui.label("", 14, 28, Cyber.display(Font.BOLD, 20), Cyber.TEXT);
        tipSub = Ui.label("", 14, 47, F_TXT, Cyber.MUTED);
        tipStatus = Ui.label("", 14, 67, Cyber.mono(Font.BOLD, 11), Cyber.CYAN);
        tip.add(tipTitle); tip.add(tipSub); tip.add(tipStatus);
        tip.setVisible(false);
        add(tip);
        setTab(Faction.PRIMARY);
    }

    public Faction getTab() { return tab; }
    public boolean isAllMode() { return allMode; }

    /** Shows one faction (exits ALL mode). */
    public void setTab(Faction f) {
        tab = f;
        allMode = false;
        rebuildCards();
    }

    /** Switches between the single-faction view and the all-towers view. */
    public void toggleAll() {
        allMode = !allMode;
        rebuildCards();
    }

    // ------------------------------------------------------------------ shop cards
    private void rebuildCards() {
        for (int i = 0; i < tabButtons.size(); i++) tabButtons.get(i).setSelected(!allMode && ShopLayout.shopFactions().get(i) == tab);
        allButton.setSelected(allMode);
        cardLayer.removeAll();
        cards.clear();
        List<ShopLayout.Cell> cells = layoutCells();
        for (ShopLayout.Cell c : cells) {
            TowerType t = c.type;
            TowerDef d = TowerCatalog.get(t);
            UIButton b = new UIButton(c.x, c.y, c.w, c.h, "", () -> screen.beginPlacing(t));
            b.setAccent(Cyber.lerp(Ui.c(t.primaryRgb), Cyber.CYAN, 0.35));
            cardLayer.add(b);
            GObject icon; GLabel name; GLabel price;
            if (allMode) {
                if (c.firstOfFaction) {
                    cardLayer.add(Ui.label(t.faction.label.toUpperCase(), ShopLayout.CARDS_X + 5, c.y + c.h / 2 + 4, Cyber.mono(Font.BOLD, 9), Ui.c(t.faction.rgb)));
                    cardLayer.add(Ui.rect(ShopLayout.CARDS_X, c.y + 2, 2, c.h - 4, Ui.c(t.faction.rgb), Ui.c(t.faction.rgb)));
                }
                String label = shortLabel(t);
                if (c.h >= 64) {
                    // roomy cell: icon on top, centred name and price below
                    double isz = Math.min(c.h - 40, 46);
                    icon = shopIcon(t, c.x + (c.w - isz) / 2, c.y + 6, isz);
                    Font nf = fitFont(label, Cyber.display(Font.BOLD, 17), c.w - 10, 10);
                    name = Ui.label(label, 0, c.y + c.h - 22, nf, Cyber.TEXT);
                    name.setLocation(c.x + (c.w - name.getWidth()) / 2, c.y + c.h - 22);
                    price = Ui.label(Ui.money(d.baseCost), 0, c.y + c.h - 7, Cyber.mono(Font.BOLD, 14), Cyber.YELLOW);
                    price.setLocation(c.x + (c.w - price.getWidth()) / 2, c.y + c.h - 7);
                } else {
                    double isz = c.h - 14;
                    icon = shopIcon(t, c.x + 6, c.y + 7, isz);
                    double tx = c.x + isz + 12;
                    Font nf = fitFont(label, Cyber.display(Font.BOLD, 16), c.x + c.w - 4 - tx, 9);
                    name = Ui.label(label, tx, c.y + c.h / 2 - 2, nf, Cyber.TEXT);
                    price = Ui.label(Ui.money(d.baseCost), tx, c.y + c.h - 8, Cyber.mono(Font.BOLD, 14), Cyber.YELLOW);
                }
            } else {
                double isz = Math.min(c.h - 20, 76);
                icon = shopIcon(t, c.x + 10, c.y + (c.h - isz) / 2, isz);
                double tx = c.x + isz + 22;
                boolean big = c.h >= 100;
                int ns = big ? 22 : 19, ps = big ? 19 : 16;
                double blockH = ns + 2 + 14 + ps + 4;
                double top = c.y + (c.h - blockH) / 2;
                Font nf = fitFont(t.displayName, Cyber.display(Font.BOLD, ns), c.x + c.w - 6 - tx, 12);
                name = Ui.label(t.displayName, tx, top + ns, nf, Cyber.TEXT);
                Font sf = fitFont(d.subtitle, Cyber.body(Font.PLAIN, 12), c.x + c.w - 6 - tx, 9);
                cardLayer.add(Ui.label(d.subtitle, tx, top + ns + 16, sf, Cyber.MUTED));
                price = Ui.label(Ui.money(d.baseCost), tx, top + blockH - 2, Cyber.mono(Font.BOLD, ps), Cyber.YELLOW);
            }
            cardLayer.add(icon); cardLayer.add(name); cardLayer.add(price);
            Card card = new Card(c, b, price, name, icon);
            if (t.isHero()) {
                GCompound badge = new GCompound();
                GLabel bl = Ui.label("PLACED", 0, 0, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW);
                double bw = bl.getWidth() + 16;
                badge.add(new Cyber.Chamfer(0, 0, bw, 18, 5).scan(false).fill(new Color(20, 16, 4, 235)).border(Cyber.YELLOW));
                bl.setLocation(8, 13);
                badge.add(bl);
                badge.setLocation(c.x + c.w - bw - 4, c.y + 4);
                badge.setVisible(false);
                cardLayer.add(badge);
                card.badge = badge;
            }
            cards.add(card);
        }
        infoY = ShopLayout.bottom(cells) + 10;
        refreshAffordability();
        builtKey = "";
    }

    /** Cells for the current mode; the shop is larger when nothing is selected and compacts to leave room for the info panel. */
    private List<ShopLayout.Cell> layoutCells() {
        double avail = Ui.H - 8 - BRIEF_H - 12 - ShopLayout.CARDS_Y;
        if (allMode) {
            double h = ShopLayout.ALL_ROW_H;
            if (!compactShop) h = Math.max(h, Math.min(84, (avail - 4 * ShopLayout.ALL_GROUP_GAP) / 7 - ShopLayout.ALL_ROW_GAP));
            return ShopLayout.allCells(h);
        }
        double h = ShopLayout.CARD_H;
        if (!compactShop) {
            int n = 0;
            for (TowerType t : TowerType.shopTowers()) if (t.faction == tab) n++;
            int rows = Math.max(1, (n + 1) / 2);
            h = Math.max(h, Math.min(140, (avail - ShopLayout.CARD_GAP) / rows - ShopLayout.CARD_GAP));
        }
        return ShopLayout.factionCells(tab, h);
    }

    /** Compact label for the dense ALL grid (full name is shown in the tooltip and info panel). */
    private static String shortLabel(TowerType t) {
        return t.displayName;
    }

    /** Shop icon: the tower's tier-0 art in a size x size box with top-left (x, y). */
    private static GObject shopIcon(TowerType t, double x, double y, double size) {
        ShopIcon icon = new ShopIcon(t, size);
        icon.setLocation(x + size / 2, y + size / 2);
        return icon;
    }

    /** Tower art icon with a translucent overlay that dims it when the tower is unaffordable. */
    private static final class ShopIcon extends GCompound {
        private static final long serialVersionUID = 1L;
        private final Cyber.Ring dim;

        ShopIcon(TowerType t, double size) {
            add(lindefense.ui.sprites.towers.TowerIcons.create(t, 0, size), 0, 0);
            double r = size * 0.62;
            dim = new Cyber.Ring(-r, -r, 2 * r, 2 * r, new Color(5, 9, 22, 170), null);
            dim.setVisible(false);
            add(dim);
        }

        void setDimmed(boolean d) { dim.setVisible(d); }
    }

    /** Shrinks a font (never truncates) until the text fits maxWidth, down to minSize. */
    private static Font fitFont(String text, Font f, double maxWidth, int minSize) {
        GLabel probe = new Cyber.Text(text);
        Font cur = f;
        probe.setFont(cur);
        while (probe.getWidth() > maxWidth && cur.getSize() > minSize) {
            cur = cur.deriveFont((float) (cur.getSize() - 1));
            probe.setFont(cur);
        }
        return cur;
    }

    public List<UIButton> getButtons() {
        List<UIButton> all = new ArrayList<>(tabButtons);
        all.add(allButton);
        all.add(helpBtn);
        for (Card c : cards) all.add(c.button);
        all.addAll(infoButtons);
        return all;
    }

    public void requestRebuild() { builtKey = ""; }

    private void refreshAffordability() {
        double cash = game.getCash();
        for (Card c : cards) {
            boolean placed = c.cell.type.isHero() && game.getTowerManager().heroPlaced(c.cell.type);
            boolean ok = ShopLayout.affordable(cash, c.cell.type) && !placed;
            if (c.badge != null && c.badge.isVisible() != placed) c.badge.setVisible(placed);
            c.button.setSelected(screen.getPlacing() == c.cell.type);
            c.button.setEnabled(ok);
            Cyber.setColor(c.price, ok ? Cyber.YELLOW : placed ? Cyber.DIM : Cyber.RED);
            Cyber.setColor(c.name, ok ? Cyber.TEXT : new Color(0x6f819b));
            if (c.icon instanceof ShopIcon) ((ShopIcon) c.icon).setDimmed(!ok);
        }
    }

    // ------------------------------------------------------------------ frame update
    public void update(double dt) {
        refresh -= dt;
        refreshAffordability();
        boolean wantCompact = screen.getSelectedTower() != null || screen.getPlacing() != null || screen.getSelectedEnemy() != null;
        if (wantCompact != compactShop) { compactShop = wantCompact; rebuildCards(); }
        updateTooltip();
        String key = selectionKey();
        boolean rebuilt = false;
        if (!key.equals(builtKey)) {
            builtKey = key;
            rebuildInfo();
            rebuilt = true;
        }
        if (rebuilt) { refresh = 0.25; screen.refreshHover(); }
        else if (refresh <= 0) {
            refresh = 0.25;
            for (Runnable r : dyn) r.run();
        }
        Tower t = screen.getSelectedTower();
        if (abilityBar != null && t != null && t.getAbility() != null) {
            abilityBar.setValue(1 - t.getAbilityCooldownFraction());
            boolean ready = t.isAbilityReady();
            abilityBar.setFill(ready ? Cyber.MAGENTA : Cyber.lerp(Cyber.DIM, Cyber.MAGENTA, 1 - t.getAbilityCooldownFraction()));
            String s = ready ? "READY  [A]" : t.isSurveilled() ? "OFFLINE" : String.format("%.0fs / %ds", Math.ceil(t.getAbilityCooldownRemaining()), (int) t.getAbility().cooldown);
            Cyber.setText(abilityText, s);
            abilityText.setLocation(Ui.PANEL_X + Ui.PANEL_W - 22 - abilityText.getWidth(), abilityText.getY());
            Cyber.setColor(abilityText, ready ? Cyber.MAGENTA : Cyber.MUTED);
        }
        if (enemyBar != null && screen.getSelectedEnemy() != null) {
            enemyBar.setValue(screen.getSelectedEnemy().getHpFraction());
            enemyBar.setFill(Cyber.hpColor(screen.getSelectedEnemy().getHpFraction()));
        }
    }

    private void updateTooltip() {
        double[] m = screen.getMouseLogical();
        Card hover = null;
        for (Card c : cards) if (c.button.hit(m[0], m[1])) { hover = c; break; }
        if (hover == null) { tip.setVisible(false); return; }
        TowerDef d = TowerCatalog.get(hover.cell.type);
        int need = ShopLayout.shortfall(game.getCash(), hover.cell.type);
        tipTitle.setLabel(hover.cell.type.displayName + "   " + Ui.money(d.baseCost));
        Cyber.setText(tipSub, d.subtitle + "  //  " + hover.cell.type.faction.label);
        String block = hover.cell.type.isHero() && game.getTowerManager().heroPlaced(hover.cell.type) ? Shop.unavailableReason(game, hover.cell.type) : null;
        Cyber.setText(tipStatus, block != null ? block.toUpperCase() : need > 0 ? "NEED " + Ui.money(need) + " MORE" : "CLICK, THEN PLACE ON THE MAP");
        Color accent = block != null ? Cyber.YELLOW : need > 0 ? Cyber.RED : Cyber.CYAN;
        Cyber.setColor(tipStatus, accent);
        Cyber.setColor(tipTitle, need > 0 && block == null ? Cyber.lerp(Cyber.TEXT, Cyber.RED, 0.15) : Cyber.TEXT);
        double w = Math.max(240, Math.max(tipTitle.getWidth(), tipSub.getWidth()) + 28);
        tipFrame.size(w, 78).border(accent);
        double y = Math.max(Ui.WORLD_Y + 6, Math.min(hover.cell.y + hover.cell.h / 2 - 39, Ui.BOTTOM_Y - 90));
        tip.setLocation(Ui.PANEL_X - w - 8, y);
        tip.setVisible(true);
    }

    private String selectionKey() {
        Tower t = screen.getSelectedTower();
        String base = "@" + (int) infoY + compactShop + ":";
        if (t != null) return base + "T" + t.getId() + ":" + t.getTier() + ":" + (game.getCash() >= Shop.upgradeCost(t)) + ":" + t.getTargeting() + ":" + t.isAbilityReady() + ":" + t.isSurveilled();
        if (screen.getPlacing() != null) return base + "P" + screen.getPlacing();
        if (screen.getSelectedEnemy() != null) return base + "E" + screen.getSelectedEnemy().getId();
        return base + "none";
    }

    // ------------------------------------------------------------------ info builders
    private double y;
    private final double x0 = Ui.PANEL_X + 22;
    private final double textW = Ui.PANEL_W - 44;

    private GLabel put(String s, double x, double baseline, Font f, Color c) {
        GLabel l = Ui.label(s, x, baseline, f, c);
        info.add(l);
        return l;
    }

    private void para(String s, Font f, Color c, int maxLines) {
        List<String> lines = Ui.wrap(s, f, textW);
        int n = 0;
        for (String l : lines) {
            if (maxLines > 0 && n >= maxLines) break;
            y += f.getSize() + 4;
            put(l, x0, y, f, c);
            n++;
        }
    }

    private void section(String title) {
        y += 12;
        GLabel l = put(Cyber.spaced("// " + title), x0, y + 9, F_MICRO, Cyber.alpha(Cyber.CYAN, 230));
        GLine ln = new GLine(x0 + l.getWidth() + 8, y + 5.5, x0 + textW, y + 5.5);
        ln.setColor(Cyber.alpha(Cyber.CYAN, 70));
        info.add(ln);
        y += 13;
    }

    private UIButton button(double bx, double by, double w, double h, String text, Runnable r) {
        UIButton b = new UIButton(bx, by, w, h, text, Cyber.display(Font.BOLD, 15), r);
        info.add(b);
        infoButtons.add(b);
        return b;
    }

    /** Micro-label over a value; the value is refreshed from the supplier by {@link #update(double)}. */
    private void statCell(double cx, double cy, String label, Supplier<String> val, Color vc) {
        put(Cyber.spaced(label), cx, cy + 9, F_MICRO, Cyber.alpha(Cyber.CYAN, 190));
        GLabel v = put(val.get(), cx, cy + 27, F_VAL, vc);
        dyn.add(() -> Cyber.setText(v, val.get()));
    }

    private void rebuildInfo() {
        info.removeAll();
        infoButtons.clear();
        dyn.clear();
        abilityBar = null; abilityText = null; enemyBar = null;
        boolean brief = !compactShop;
        double top = infoY;
        infoFrame.setLocation(Ui.PANEL_X + 8, top);
        infoFrame.size(Ui.PANEL_W - 16, brief ? BRIEF_H : Ui.H - 8 - top);
        y = top + 6;
        Tower t = screen.getSelectedTower();
        if (t != null && t.isAlive()) buildTowerInfo(t);
        else if (screen.getPlacing() != null) buildShopInfo(screen.getPlacing());
        else {
            Enemy e = screen.getSelectedEnemy();
            if (e != null) buildEnemyInfo(e); else buildHelp();
        }
    }

    /** Compact 3-line briefing strip anchored at the bottom of the panel (full controls live in the Help overlay). */
    private void buildHelp() {
        put(Cyber.spaced("sector"), x0, y + 16, F_MICRO, Cyber.alpha(Cyber.CYAN, 230));
        GLabel nm = put(game.getMap().getName().toUpperCase(), x0 + 62, y + 18, Cyber.display(Font.BOLD, 18), Cyber.YELLOW);
        GLabel hint = put("[H] HELP", 0, y + 16, F_MICRO, Cyber.DIM);
        hint.setLocation(x0 + textW - hint.getWidth(), y + 16);
        // long map names (Valorax is wide): step the title down until it clears the hint
        double room = hint.getX() - 8 - (x0 + 62);
        for (int sz = 18; nm.getWidth() > room && sz > 8; sz -= 2) nm.setFont(Cyber.displayCompact(Font.BOLD, sz));
        y += 22;
        List<String> lines = Ui.wrap(game.getMap().getMechanicSummary(), F_TXT, textW);
        for (int i = 0; i < Math.min(2, lines.size()); i++) {
            y += 16;
            String l = lines.get(i);
            if (i == 1 && lines.size() > 2) l = fitText(l + " …", F_TXT, textW);
            put(l, x0, y, F_TXT, Cyber.MUTED);
        }
        if (nm.getWidth() < 0) y += 0;
    }

    private static String fitText(String s, Font f, double w) {
        GLabel p = new Cyber.Text(s);
        p.setFont(f);
        String cur = s;
        while (p.getWidth() > w && cur.length() > 2) { cur = cur.substring(0, cur.length() - 2) + "…"; p.setLabel(cur); }
        return cur;
    }

    /** Wrapped, comma-joined list of a stat block's notable effects. */
    private static String effectsText(TowerStats s, boolean includeKind) {
        HitSpec h = s.hit;
        List<String> fx = new ArrayList<>();
        if (includeKind && s.kind != AttackKind.NONE) {
            fx.add(s.kind == AttackKind.PULSE ? "pulse (all in range)" : s.kind == AttackKind.CHAIN ? "chain x" + (s.chainHops + 1)
                : s.kind == AttackKind.INSTANT ? "beam" : (s.splashRadius > 0 ? "splash " + (int) s.splashRadius + "px" : "projectile"));
            fx.add(h.type.label.toLowerCase());
        }
        if (s.targets > 1) fx.add(s.targets + " targets");
        if (s.projectilesPerShot > 1) fx.add(s.projectilesPerShot + " shots");
        if (s.bounces > 0) fx.add(s.bounces + " bounces");
        if (h.slowFraction > 0) fx.add("slow " + (int) (h.slowFraction * 100) + "%");
        if (h.stunDuration > 0) fx.add("stun " + Ui.fmt(h.stunDuration) + "s");
        if (h.knockback > 0) fx.add("knockback " + (int) h.knockback);
        if (h.armorBreak > 0) fx.add("armour break " + (int) (h.armorBreak * 100) + "%");
        if (h.armorPierce > 0) fx.add("armour pierce " + (int) (h.armorPierce * 100) + "%");
        if (h.ignoresResistance) fx.add("ignores immunities");
        if (h.markBonus > 0) fx.add("mark +" + (int) (h.markBonus * 100) + "%");
        if (h.disruptDuration > 0) fx.add("disrupt " + Ui.fmt(h.disruptDuration) + "s");
        if (h.bonusVsBoss > 0) fx.add("+" + (int) (h.bonusVsBoss * 100) + "% vs bosses");
        if (h.bonusVsFortified > 0) fx.add("+" + (int) (h.bonusVsFortified * 100) + "% vs Fortified");
        if (h.bonusVsNonFortified > 0) fx.add("+" + (int) (h.bonusVsNonFortified * 100) + "% vs non-Fortified");
        if (h.bonusVsComplex > 0) fx.add("+" + (int) (h.bonusVsComplex * 100) + "% vs complex");
        if (h.bonusVsFast > 0) fx.add("+" + (int) (h.bonusVsFast * 100) + "% vs fast");
        if (h.bonusVsSplitters > 0) fx.add("+" + (int) (h.bonusVsSplitters * 100) + "% vs splitters");
        if (h.stripsFortified) fx.add("strips Fortified");
        if (h.pctMaxHp > 0) fx.add("+" + (int) (h.pctMaxHp * 100) + "% max HP");
        if (s.stackCap > 0) fx.add("stacks to +" + (int) (s.stackCap * s.stackStep));
        return String.join("  •  ", fx);
    }

    private static String supportText(TowerStats s, boolean sees) {
        List<String> aura = new ArrayList<>();
        if (sees) aura.add("sees camo");
        if (s.auraDetection) aura.add("shares detection");
        if (s.auraRate > 0) aura.add("aura +" + (int) (s.auraRate * 100) + "% speed");
        if (s.auraDamage > 0) aura.add("aura +" + Ui.fmt(s.auraDamage) + " damage");
        if (s.auraRangeBonus > 0) aura.add("aura +" + (int) (s.auraRangeBonus * 100) + "% range");
        if (s.auraSurveillanceImmunity) aura.add("blocks Surveillance");
        if (s.auraEnemySlow > 0) aura.add("wind wall slow " + (int) (s.auraEnemySlow * 100) + "%");
        if (s.incomePerWave > 0) aura.add("+$" + (int) s.incomePerWave + " per wave");
        if (s.summonCount > 0) aura.add("summons " + s.summonCount + " sprite(s) / " + (int) s.summonInterval + "s");
        return String.join("  •  ", aura);
    }

    private static String modeText(TowerStats s) {
        return s.kind == AttackKind.PULSE ? "PULSE" : s.kind == AttackKind.CHAIN ? "x" + (s.chainHops + 1) : String.valueOf(s.pierce);
    }

    private static String modeLabel(TowerStats s) {
        return s.kind == AttackKind.PULSE ? "MODE" : s.kind == AttackKind.CHAIN ? "CHAIN" : "PIERCE";
    }

    private void header(String name, Color nameColor, String badge, Color badgeColor) {
        y += 28;
        GLabel n = put(name, x0, y, F_NAME, nameColor);
        if (badge != null) {
            GLabel b = Ui.label(badge, 0, 0, Cyber.mono(Font.BOLD, 11), badgeColor);
            double bw = b.getWidth() + 18;
            double bx = x0 + textW - bw;
            if (bx < x0 + n.getWidth() + 8) { bx = x0 + n.getWidth() + 8; }
            info.add(new Cyber.Chamfer(bx, y - 17, bw, 20, 5).scan(false).fill(Cyber.alpha(badgeColor, 40)).border(badgeColor));
            b.setLocation(bx + 9, y - 2.5);
            info.add(b);
        }
    }

    private void buildShopInfo(TowerType type) {
        TowerDef d = TowerCatalog.get(type);
        Color tc = Cyber.lerp(Ui.c(type.primaryRgb), Color.WHITE, 0.3);
        header(type.displayName, tc, type.isHero() ? "HERO // DEPLOY" : Ui.money(d.baseCost), Cyber.YELLOW);
        y += 4;
        put(d.subtitle + "  //  " + type.faction.label.toUpperCase(), x0, y + 12, F_TXT, Ui.c(type.faction.rgb));
        y += 14;
        para(d.description, F_TXT, Cyber.TEXT, 0);
        section("stats");
        TowerStats s = d.baseStats;
        if (s.kind != AttackKind.NONE) {
            double yy = y;
            statCell(x0, yy, "damage", () -> Ui.fmt(s.hit.damage), Cyber.TEXT);
            statCell(x0 + 180, yy, "interval", () -> Ui.fmt(s.interval()) + "s", Cyber.TEXT);
            statCell(x0, yy + 34, "range", () -> HeroStatText.range(type, s.range), Cyber.TEXT);
            statCell(x0 + 180, yy + 34, modeLabel(s), () -> modeText(s), Cyber.TEXT);
            y += 68;
            String fx = effectsText(s, true);
            if (!fx.isEmpty()) para(fx, F_TXT_S, Cyber.MUTED, 3);
        } else {
            y += 4;
            put("Support tower - no direct attack", x0, y + 12, F_TXT, Cyber.TEXT);
            y += 14;
        }
        String sup = supportText(s, s.seesCamo);
        if (!sup.isEmpty()) para(sup, F_TXT_S, Cyber.CYAN, 3);
        if (d.upgrades.length > 0) section("upgrade path");
        for (int i = 0; i < d.upgrades.length; i++) {
            UpgradeDef u = d.upgrades[i];
            y += 15;
            put((i + 1) + "  " + u.name, x0, y, Cyber.display(Font.BOLD, 14), Cyber.TEXT);
            GLabel pr = put(Ui.money(u.cost), 0, y, Cyber.mono(Font.BOLD, 12), Cyber.YELLOW);
            pr.setLocation(x0 + textW - pr.getWidth(), y);
        }
        if (d.ability != null) {
            section("ability");
            y += 16;
            put(d.ability.name, x0, y, Cyber.display(Font.BOLD, 15), Cyber.MAGENTA);
            GLabel cd = put((int) d.ability.cooldown + "s cooldown", 0, y, Cyber.mono(Font.BOLD, 11), Cyber.MUTED);
            cd.setLocation(x0 + textW - cd.getWidth(), y);
            para(d.ability.description, F_TXT_S, Cyber.MUTED, 3);
        }
        y += 12;
        para(type.isHero() ? "Click a free spot to deploy (free, once per match). Esc cancels." : "Click a free spot on the map. Right-click or Esc to cancel.", F_TXT_S, Cyber.CYAN, 1);
        button(x0, Math.min(y + 10, Ui.H - 56), 130, 34, "CANCEL", () -> screen.beginPlacing(null)).setAccent(Cyber.RED);
    }

    private void buildTowerInfo(Tower t) {
        TowerDef d = t.getDef();
        TowerType ty = t.getType();
        Color tc = Cyber.lerp(Ui.c(ty.primaryRgb), Color.WHITE, 0.3);
        boolean maxed = !t.canUpgrade();
        boolean hero = ty.isHero();
        String badge = hero ? "HERO" : maxed ? "MAX" : "TIER " + t.getTier() + "/" + t.getMaxTier();
        header(ty.displayName, tc, badge, maxed ? Cyber.YELLOW : Cyber.CYAN);
        y += 4;
        GLabel sub = put(d.subtitle + "  //  ", x0, y + 12, F_TXT, Cyber.MUTED);
        put(t.getTierLabel(), x0 + sub.getWidth(), y + 12, Cyber.body(Font.BOLD, 12), Cyber.CYAN);
        y += 14;

        // ---- stat grid (2 columns)
        section("stats");
        TowerStats base = t.getStats();
        double yy = y;
        if (!base.isSupportOnly()) {
            statCell(x0, yy, "damage", () -> Ui.fmt(t.getStats().hit.damage * t.damageMultiplier(game)), Cyber.TEXT);
            statCell(x0 + 180, yy, "interval", () -> Ui.fmt(1.0 / Math.max(0.01, t.effectiveRate(game))) + "s", Cyber.TEXT);
            statCell(x0, yy + 34, "range", () -> HeroStatText.range(t.getType(), t.effectiveRange(game)), Cyber.TEXT);
            statCell(x0 + 180, yy + 34, modeLabel(base), () -> modeText(t.getStats()), Cyber.TEXT);
            statCell(x0, yy + 68, "kills", () -> Cyber.commas(t.getKills()), Cyber.GREEN);
            if (t.getAbility() != null) statCell(x0 + 180, yy + 68, "ability", () -> t.isAbilityReady() ? "READY" : (int) Math.ceil(t.getAbilityCooldownRemaining()) + "s", Cyber.MAGENTA);
            else statCell(x0 + 180, yy + 68, "invested", () -> Ui.money(t.getInvestedCost()), Cyber.YELLOW);
            y += 102;
        } else {
            statCell(x0, yy, "kills", () -> Cyber.commas(t.getKills()), Cyber.GREEN);
            statCell(x0 + 180, yy, "invested", () -> Ui.money(t.getInvestedCost()), Cyber.YELLOW);
            y += 34;
        }
        String fx = effectsText(base, true);
        if (!fx.isEmpty() && !base.isSupportOnly()) para(fx, F_TXT_S, Cyber.MUTED, 2);
        String sup = supportText(base, t.canSeeCamo());
        if (!sup.isEmpty()) para(sup, F_TXT_S, Cyber.CYAN, 2);
        if (ty == TowerType.KIMI && base.has("memoryPer")) {
            y += 6;
            double my = y;
            statCell(x0, my, "memory", () -> "+" + KimiBehavior.memoryStacks(t) + " dmg  (" + KimiBehavior.memoryStacks(t) + " / " + (int) t.getStats().p("memoryCap") + ")", Cyber.MAGENTA);
            statCell(x0 + 180, my, "next stack", () -> KimiBehavior.memoryStacks(t) >= (int) t.getStats().p("memoryCap") ? "MAX"
                : (t.getKills() % (int) t.getStats().p("memoryPer")) + " / " + (int) t.getStats().p("memoryPer") + " pops", Cyber.TEXT);
            y += 34;
        }
        if (t.getAuraRateBonus() > 0 || t.getAuraDamageBonus() > 0) {
            para("BUFFED " + (t.getAuraRateBonus() > 0 ? "+" + (int) Math.round(t.getAuraRateBonus() * 100) + "% speed" : "") + (t.getAuraRateBonus() > 0 && t.getAuraDamageBonus() > 0 ? ", " : "")
                + (t.getAuraDamageBonus() > 0 ? "+" + Ui.fmt(t.getAuraDamageBonus()) + " damage" : ""), F_TXT_S, Cyber.GREEN, 1);
        }
        if (t.isSurveilled()) {
            y += 4;
            put("SURVEILLED: -50% speed, -30% range", x0, y + 12, Cyber.mono(Font.BOLD, 11), Cyber.RED);
            y += 12;
        }

        String extra = HeroStatText.liveLine(game, t);
        if (extra != null) para(extra, F_TXT_S, Cyber.YELLOW, 2);

        // ---- upgrade path: one pip per upgrade, labels from tierLabels (heroes have none)
        int n = d.upgrades.length;
        if (n > 0) section("upgrade path");
        double gap = 6, pipW = (textW - gap * (n - 1)) / Math.max(1, n);
        for (int i = 0; i < n; i++) {
            boolean owned = i < t.getTier(), next = i == t.getTier();
            Color pc = owned ? Cyber.CYAN : next ? Cyber.YELLOW : Cyber.DIM;
            info.add(new Cyber.Chamfer(x0 + i * (pipW + gap), y, pipW, 9, 3).scan(false)
                .fill(owned ? Cyber.alpha(Cyber.CYAN, 200) : next ? Cyber.alpha(Cyber.YELLOW, 45) : new Color(10, 18, 38, 220))
                .border(owned ? Cyber.CYAN : next ? Cyber.YELLOW : Cyber.alpha(Cyber.DIM, 160)).glow(owned ? 0.6 : 0).lineWidth(1.2));
            String label = d.tierLabels[Math.min(i + 1, d.tierLabels.length - 1)];
            Font lf = fitFont(label, Cyber.body(Font.PLAIN, 11), pipW, 8);
            put(label, x0 + i * (pipW + gap), y + 23, lf, owned ? Cyber.MUTED : next ? Cyber.YELLOW : Cyber.DIM);
        }
        y += 30;
        UpgradeDef u = t.nextUpgrade();
        if (u != null) {
            boolean can = game.getCash() >= u.cost;
            UIButton ub = button(x0, y, textW, 40, "", () -> screen.upgradeSelected());
            ub.setEnabled(can);
            ub.setAccent(Cyber.CYAN);
            put(Cyber.spaced("upgrade [u]"), x0 + 12, y + 14, F_MICRO, can ? Cyber.alpha(Cyber.CYAN, 230) : Cyber.DIM);
            put(u.name, x0 + 12, y + 32, Cyber.display(Font.BOLD, 17), can ? Cyber.TEXT : Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.4));
            GLabel pr = put(Ui.money(u.cost), 0, y + 27, Cyber.mono(Font.BOLD, 16), can ? Cyber.YELLOW : Cyber.RED);
            pr.setLocation(x0 + textW - 12 - pr.getWidth(), y + 27);
            y += 40;
            para(u.description, F_TXT_S, Cyber.MUTED, 3);
        } else if (!hero) {
            y += 4;
            put("MAX TIER  //  " + t.getTierLabel(), x0, y + 14, Cyber.display(Font.BOLD, 16), Cyber.YELLOW);
            y += 16;
        }

        // ---- targeting
        if (!base.isSupportOnly()) {
            y += 12;
            put(Cyber.spaced("target [t]"), x0, y + 20, F_MICRO, Cyber.alpha(Cyber.CYAN, 230));
            button(x0 + 86, y, 34, 28, "<", () -> screen.cycleTargeting(-1)).setAccent(Cyber.CYAN);
            String tl = t.getTargeting() == lindefense.tower.Targeting.DENSEST_CLUSTER ? "DENSEST CLUSTER" : t.getTargeting().label.toUpperCase();
            UIButton cur = button(x0 + 124, y, 130, 28, tl, null);
            cur.setSelected(true);
            button(x0 + 258, y, 34, 28, ">", () -> screen.cycleTargeting(1)).setAccent(Cyber.CYAN);
            y += 28;
        }

        // ---- ability
        AbilityDef a = t.getAbility();
        if (a != null) {
            y += 12;
            boolean ready = t.isAbilityReady();
            UIButton ab = button(x0, y, textW, 36, a.name.toUpperCase(), () -> screen.abilitySelected());
            ab.setAccent(Cyber.MAGENTA);
            ab.setEnabled(ready);
            abilityText = put("", x0 + textW - 12, y + 22, Cyber.mono(Font.BOLD, 11), Cyber.MAGENTA);
            abilityBar = new Cyber.Bar(x0 + 6, y + 36 - 7, textW - 12, 3, 0).colors(Cyber.MAGENTA, new Color(255, 255, 255, 28), null);
            info.add(abilityBar);
            y += 36;
            para(a.description, F_TXT_S, Cyber.MUTED, 3);
        }

        // ---- sell / deselect
        y += 12;
        UIButton sell = button(x0, y, 210, 34, hero ? "DISMISS (NO REDEPLOY)" : "SELL  +" + Ui.money(Shop.sellValue(t)), () -> screen.sellSelected());
        sell.setAccent(Cyber.RED);
        UIButton desel = button(x0 + 218, y, textW - 218, 34, "DESELECT", () -> screen.selectTower(null));
        desel.setAccent(Cyber.MUTED);
        if (maxed) y += 0;
    }

    private void buildEnemyInfo(Enemy e) {
        Color nc = e.isBoss() ? Cyber.RED : Cyber.TEXT;
        header(e.getType().displayName, nc, e.isBoss() ? e.getType().getBossClass().label + " BOSS" : "ENEMY", e.isBoss() ? Cyber.RED : Cyber.MAGENTA);
        StringBuilder mods = new StringBuilder();
        for (Modifier m : e.getModifiers()) { if (mods.length() > 0) mods.append(", "); mods.append(m.label); }
        if (mods.length() > 0) { y += 4; put(mods.toString().toUpperCase(), x0, y + 12, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW); y += 14; }
        y += 8;
        enemyBar = new Cyber.Bar(x0, y, textW, 12, 4).colors(Cyber.GREEN, new Color(0, 0, 0, 200), Cyber.alpha(Cyber.CYAN, 120));
        info.add(enemyBar);
        y += 12;
        GLabel hp = put("", x0, y + 18, Cyber.mono(Font.BOLD, 13), Cyber.TEXT);
        dyn.add(() -> Cyber.setText(hp, "HP " + Cyber.commas((long) Math.ceil(e.getHp())) + " / " + Cyber.commas((long) e.getMaxHp()) + (e.isAlive() ? "" : "  (destroyed)")));
        Cyber.setText(hp, "HP " + Cyber.commas((long) Math.ceil(e.getHp())) + " / " + Cyber.commas((long) e.getMaxHp()));
        y += 20;
        section("stats");
        double yy = y;
        statCell(x0, yy, "speed", () -> Ui.fmt(e.getType().speed) + "x", Cyber.TEXT);
        statCell(x0 + 180, yy, "reward", () -> "$" + e.getType().reward, Cyber.YELLOW);
        statCell(x0, yy + 34, "lives cost", () -> String.valueOf(e.getType().lives), Cyber.RED);
        statCell(x0 + 180, yy + 34, "armour", () -> (int) (e.getType().getArmor() * 100) + "%", Cyber.TEXT);
        y += 68;
        if (e.isLeadType()) para("Lead-type: immune to Sharp damage", F_TXT, Cyber.YELLOW, 1);
        if (e.getType().hasChildren()) para("Releases " + e.getType().totalChildren() + " " + e.getType().getChildTypes()[0].displayName + (e.getType().getChildTypes().length > 1 ? " + " + e.getType().getChildTypes()[1].displayName : ""), F_TXT, Cyber.TEXT, 2);
        y += 4;
        para(e.getType().description, F_TXT, Cyber.MUTED, 0);
        if (e.getType().mechanic == lindefense.enemy.Mechanic.RADIX_PHASES) {
            String[] ph = { "plain (layers 8-7)", "Lead-type: armoured phase 1 (layers 6-5)", "Lead-type: armoured phase 2 (layers 4-3)", "Lead-type: armoured phase 3 (layers 2-1)" };
            para("Current phase: " + ph[e.radixPhase()], F_TXT, Cyber.YELLOW, 1);
        }
        if (!e.getStoredEnemies().isEmpty()) para("Storing " + e.getStoredEnemies().size() + " enemies", F_TXT, Cyber.YELLOW, 1);
        y += 14;
        button(x0, y, 130, 32, "DESELECT", () -> screen.selectEnemy(null)).setAccent(Cyber.MUTED);
    }
}
