package lindefense.ui;

import java.util.ArrayList;
import java.util.List;
import lindefense.tower.Faction;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerType;

/**
 * Pure-logic layout of the tower shop (no ACM dependency) so it can be unit
 * tested headlessly. Produces cell rectangles in logical coordinates for the
 * single-faction view and for the all-towers view (every shop tower in one
 * compact grid grouped by faction: Primary, Military, Magic, Support, Titans).
 * Heroes are not sold here; they live in the separate Hero Store.
 */
public final class ShopLayout {
    private ShopLayout() { }

    /** One shop cell. */
    public static final class Cell {
        public final TowerType type;
        public final Faction faction;
        public final double x, y, w, h;
        /** True for the first cell of a faction row group (where the header label goes). */
        public final boolean firstOfFaction;

        Cell(TowerType type, double x, double y, double w, double h, boolean firstOfFaction) {
            this.type = type; this.faction = type.faction; this.x = x; this.y = y; this.w = w; this.h = h; this.firstOfFaction = firstOfFaction;
        }

        public boolean contains(double px, double py) { return px >= x && px <= x + w && py >= y && py <= y + h; }
    }

    /** Area available for cards inside the sidebar. */
    public static final double CARDS_X = Ui.PANEL_X + 8;
    public static final double CARDS_Y = 82;
    public static final double CARDS_W = Ui.PANEL_W - 16;
    /** Bottom of the card area for the tallest view (the info panel begins below the cards actually shown). */
    public static final double CARDS_BOTTOM = 492;

    /** Width of the faction header column in the all-towers view. */
    public static final double HEADER_W = 50;
    public static final double ALL_ROW_H = 46;
    public static final double ALL_ROW_GAP = 3;
    public static final double ALL_GROUP_GAP = 6;
    public static final int ALL_MAX_COLS = 3;

    /** Faction-view card size. */
    public static final double CARD_W = 190, CARD_H = 84, CARD_GAP = 4;

    /** Cells for the single-faction view: 2 columns of 190 x 60 cards. */
    public static List<Cell> factionCells(Faction f) { return factionCells(f, CARD_H); }

    /** Faction view with a given card height (the shop grows when nothing is selected). */
    public static List<Cell> factionCells(Faction f, double cardH) {
        List<Cell> cells = new ArrayList<>();
        int i = 0;
        for (TowerType t : TowerType.shopTowers()) {
            if (t.faction != f) continue;
            double cx = CARDS_X + (i % 2) * (CARD_W + CARD_GAP), cy = CARDS_Y + (i / 2) * (cardH + CARD_GAP);
            cells.add(new Cell(t, cx, cy, CARD_W, cardH, i == 0));
            i++;
        }
        return cells;
    }

    /**
     * Cells for the all-towers view: one row group per faction (Titans wrap to
     * three rows), every row using the same three equal columns after a header
     * column. Fits in the card area without scrolling.
     */
    public static List<Cell> allCells() { return allCells(ALL_ROW_H); }

    /** All-towers view with a given cell height. */
    public static List<Cell> allCells(double rowH) {
        List<Cell> cells = new ArrayList<>();
        double y = CARDS_Y;
        double gridX = CARDS_X + HEADER_W;
        double gridW = CARDS_W - HEADER_W;
        double cellW = gridW / ALL_MAX_COLS;
        for (Faction f : shopFactions()) {
            List<TowerType> types = new ArrayList<>();
            for (TowerType t : TowerType.shopTowers()) if (t.faction == f) types.add(t);
            int n = types.size();
            for (int i = 0; i < n; i++) {
                int row = i / ALL_MAX_COLS, col = i % ALL_MAX_COLS;
                double cx = gridX + col * cellW;
                double cy = y + row * (rowH + ALL_ROW_GAP);
                cells.add(new Cell(types.get(i), cx + 1, cy, cellW - 2, rowH, i == 0));
            }
            int rows = (n + ALL_MAX_COLS - 1) / ALL_MAX_COLS;
            y += rows * (rowH + ALL_ROW_GAP) + ALL_GROUP_GAP - ALL_ROW_GAP;
        }
        return cells;
    }

    /** Factions shown as tower-shop tabs (every faction except the Hero Store's heroes). */
    public static List<Faction> shopFactions() {
        List<Faction> l = new ArrayList<>();
        for (Faction f : Faction.values()) if (f != Faction.HERO) l.add(f);
        return l;
    }

    /** Lowest edge of a set of cells (where the info panel may begin, plus a margin). */
    public static double bottom(List<Cell> cells) {
        double b = CARDS_Y;
        for (Cell c : cells) b = Math.max(b, c.y + c.h);
        return b;
    }

    /** Height used by the all-towers grid. */
    public static double allGridHeight() {
        double maxBottom = CARDS_Y;
        for (Cell c : allCells()) maxBottom = Math.max(maxBottom, c.y + c.h);
        return maxBottom - CARDS_Y;
    }

    public static boolean affordable(double cash, TowerType t) { return cash >= TowerCatalog.get(t).baseCost; }

    /** True if the match can pay for the tower at its current price (PATCH NOTES discounts / surcharges included). */
    public static boolean affordable(lindefense.sim.Game game, TowerType t) { return game.getCash() >= lindefense.tower.Shop.priceOf(game, t); }

    /** Cash still missing to buy the tower at its current match price (0 if affordable). */
    public static int shortfall(lindefense.sim.Game game, TowerType t) {
        return (int) Math.max(0, Math.ceil(lindefense.tower.Shop.priceOf(game, t) - game.getCash()));
    }

    /** Cash still missing to buy the tower (0 if affordable). */
    public static int shortfall(double cash, TowerType t) {
        return (int) Math.max(0, Math.ceil(TowerCatalog.get(t).baseCost - cash));
    }

    /** Cell under a logical point, or null. */
    public static Cell cellAt(List<Cell> cells, double px, double py) {
        for (Cell c : cells) if (c.contains(px, py)) return c;
        return null;
    }
}
