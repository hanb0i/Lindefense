package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import java.awt.Color;
import java.awt.Font;
import java.util.ArrayList;
import java.util.List;
import java.util.function.IntConsumer;
import lindefense.sim.Game;
import lindefense.variance.BreakingNews;
import lindefense.variance.Mods;
import lindefense.variance.PatchNote;
import lindefense.variance.RunSeed;
import lindefense.variance.RunVariance;

/**
 * Drawing for the run-variance features: the "Patch Notes" draft overlay (three cards, pick one), the card chips used
 * on the end screen, and the hover cards for chips and news. Stateless builders; {@link GameScreen} owns the overlay
 * and {@link RunStrip} the in-game strip.
 */
final class PatchNotesView {
    private PatchNotesView() { }

    /** Card colour by theme. */
    static Color accent(PatchNote.Category c) {
        switch (c) {
            case ECONOMY: return Cyber.YELLOW;
            case CONTROL: return Cyber.MAGENTA;
            case SURVIVAL: return Cyber.GREEN;
            default: return Cyber.CYAN;
        }
    }

    /** "SEED K3X9QZ". */
    static String seedText(Game game) { return "SEED " + RunSeed.format(game.getSeed()); }

    // ------------------------------------------------------------------ draft overlay
    /**
     * Builds the draft overlay over the playfield: title, the three offered cards (each fully clickable, plus a SHIP IT
     * button) and a footer with the active cards, seed and draft number. Returns the title for the glitch animation.
     */
    static Cyber.GlitchText buildDraft(GCompound overlay, List<UIButton> buttons, Game game, IntConsumer onPick) {
        RunVariance v = game.getVariance();
        List<PatchNote> offer = v.getOffer();
        int wave = v.getOfferWave();
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)));
        double cx = Ui.WORLD_X + Ui.WORLD_W / 2.0;
        double pw = 1140, ph = 624, px = cx - pw / 2, py = Ui.WORLD_Y + (Ui.WORLD_H - ph) / 2;
        overlay.add(new Cyber.Chamfer(px, py, pw, ph, 26).fill(new Color(6, 10, 24, 240)).border(Cyber.CYAN).glow(1.1).lineWidth(2).ticks(true));
        overlay.add(Ui.rect(px + 24, py + 12, 140, 3, Cyber.MAGENTA, Cyber.MAGENTA));
        String micro = "// patch notes v1." + (v.getActive().size() + 1) + "  //  " + (wave <= 1 ? "launch build" : "pre-wave " + wave + " hotfix");
        centered(overlay, Cyber.spaced(micro), cx, py + 42, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.MAGENTA, 235));
        Cyber.GlitchText title = new Cyber.GlitchText("PATCH NOTES", Cyber.display(Font.BOLD, 58), Cyber.lerp(Cyber.CYAN, Color.WHITE, 0.3));
        title.setLocation(cx - title.textWidth() / 2, py + 102);
        overlay.add(title);
        title.burst(0.5);
        centered(overlay, "Ship one change. It lasts the rest of the run, and every card has an upside and a downside.",
            cx, py + 132, Cyber.body(Font.PLAIN, 16), Cyber.MUTED);

        double cw = 344, ch = 388, gap = 24;
        double x0 = cx - (offer.size() * cw + (offer.size() - 1) * gap) / 2, y0 = py + 156;
        for (int i = 0; i < offer.size(); i++) {
            final int index = i;
            card(overlay, buttons, offer.get(i), i, wave, x0 + i * (cw + gap), y0, cw, ch, () -> onPick.accept(index));
        }

        // footer: active cards (left), key hint (centre), seed and draft number (right)
        double fy = py + ph - 26;
        StringBuilder act = new StringBuilder();
        for (PatchNote p : v.getActive()) act.append(act.length() == 0 ? "" : "  +  ").append(p.chip);
        GLabel left = Ui.label(act.length() == 0 ? "NO PATCHES YET" : "ACTIVE  " + act, px + 30, fy, Cyber.mono(Font.BOLD, 11), Cyber.alpha(Cyber.CYAN, 200));
        for (int sz = 11; left.getWidth() > pw * 0.42 && sz > 7; sz--) left.setFont(Cyber.mono(Font.BOLD, sz));
        overlay.add(left);
        centered(overlay, "PRESS 1 / 2 / 3 OR CLICK A CARD", cx, fy, Cyber.mono(Font.BOLD, 11), Cyber.MUTED);
        GLabel right = Ui.label(seedText(game) + "   //   DRAFT " + v.getDraftNumber() + " OF " + RunVariance.DRAFT_WAVES.length, 0, fy,
            Cyber.mono(Font.BOLD, 11), Cyber.alpha(Cyber.MAGENTA, 220));
        right.setLocation(px + pw - 30 - right.getWidth(), fy);
        overlay.add(right);
        return title;
    }

    /** One offered card: theme colour, key badge, title, flavour, upsides, downsides and a SHIP IT button. */
    private static void card(GCompound overlay, List<UIButton> buttons, PatchNote p, int index, int wave,
                             double x, double y, double w, double h, Runnable pick) {
        Color acc = accent(p.category);
        overlay.add(new Cyber.Chamfer(x, y, w, h, 16).fill(new Color(8, 13, 30, 232)).border(Cyber.alpha(acc, 225)).glow(0.6).lineWidth(1.8).ticks(true));
        overlay.add(Ui.rect(x + 18, y + 10, 70, 3, acc, acc));
        // key badge + theme
        GLabel key = Ui.label(String.valueOf(index + 1), 0, 0, Cyber.mono(Font.BOLD, 14), Cyber.INK);
        overlay.add(new Cyber.Chamfer(x + 18, y + 22, 26, 24, 6).scan(false).fill(acc).border(Cyber.lerp(acc, Color.WHITE, 0.4)));
        key.setLocation(x + 18 + (26 - key.getWidth()) / 2, y + 39);
        overlay.add(key);
        GLabel theme = Ui.label(Cyber.spaced(p.category.name()), 0, y + 39, Cyber.mono(Font.BOLD, 10), Cyber.alpha(acc, 230));
        theme.setLocation(x + w - 18 - theme.getWidth(), y + 39);
        overlay.add(theme);
        // title (up to two lines), flavour
        double tw = w - 36, yy = y + 80;
        Font tf = Cyber.display(Font.BOLD, 26);
        List<String> tl = Ui.wrap(p.title.toUpperCase(), tf, tw);
        if (tl.size() > 2) { tf = Cyber.display(Font.BOLD, 21); tl = Ui.wrap(p.title.toUpperCase(), tf, tw); }
        for (String l : tl) { overlay.add(Ui.label(l, x + 18, yy, tf, Cyber.lerp(acc, Color.WHITE, 0.55))); yy += tf.getSize() + 4; }
        yy += 2;
        for (String l : Ui.wrap(p.flavor, Cyber.body(Font.PLAIN, 14), tw)) { overlay.add(Ui.label(l, x + 18, yy, Cyber.body(Font.PLAIN, 14), Cyber.MUTED)); yy += 18; }
        yy += 6;
        overlay.add(Ui.rect(x + 18, yy, tw, 1, Cyber.alpha(acc, 90), Cyber.alpha(acc, 90)));
        yy += 22;
        yy = effects(overlay, "upside", p.upsides(wave), Cyber.GREEN, x + 18, yy, tw);
        yy += 8;
        effects(overlay, "downside", p.downsides(wave), Cyber.RED, x + 18, yy, tw);
        // the whole card is the click target (a flat button over the art lights it on hover), plus an explicit button
        UIButton area = new UIButton(x, y, w, h, "", Cyber.mono(Font.BOLD, 1), pick);
        area.setFlat(true);
        area.setAccent(acc);
        overlay.add(area);
        buttons.add(area);
        UIButton ship = new UIButton(x + 18, y + h - 58, w - 36, 42, "SHIP IT  [" + (index + 1) + "]", Cyber.display(Font.BOLD, 18), pick);
        ship.setAccent(acc);
        ship.setPrimary(true);
        overlay.add(ship);
        buttons.add(ship);
        area.animate(0);   // apply the flat / primary styles now, not one frame later (no dark flash over the card)
        ship.animate(0);
    }

    /** A "// upside" block of bullet lines; returns the y below it. */
    private static double effects(GCompound into, String head, List<Mods.Effect> lines, Color col, double x, double y, double w) {
        into.add(Ui.label(Cyber.spaced("// " + head), x, y, Cyber.mono(Font.BOLD, 10), Cyber.alpha(col, 230)));
        y += 22;
        Font f = Cyber.body(Font.BOLD, 15);
        for (Mods.Effect e : lines) {
            boolean first = true;
            for (String l : Ui.wrap(e.text, f, w - 20)) {
                if (first) into.add(Ui.label(e.good ? "+" : "-", x + 2, y, Cyber.mono(Font.BOLD, 15), col));
                into.add(Ui.label(l, x + 20, y, f, Cyber.TEXT));
                first = false;
                y += 20;
            }
            y += 3;
        }
        return y;
    }

    // ------------------------------------------------------------------ chips
    /** Width of a chip for {@code text} in {@code f}. */
    static double chipWidth(String text, Font f) {
        GLabel probe = Ui.label(text, 0, 0, f, Color.WHITE);
        return probe.getWidth() + 18;
    }

    /** One chip (chamfered tag with a theme-coloured border), top-left at (x, y); returns its width. */
    static double chip(GCompound into, PatchNote p, double x, double y, double h, Font f) {
        Color acc = accent(p.category);
        double w = chipWidth(p.chip, f);
        into.add(new Cyber.Chamfer(x, y, w, h, 5).scan(false).fill(new Color(10, 16, 34, 235)).border(Cyber.alpha(acc, 210)));
        into.add(Ui.rect(x + 1.5, y + 3, 2, h - 6, acc, acc));
        GLabel l = Ui.label(p.chip, x + 10, y + h / 2 + f.getSize() * 0.36, f, Cyber.lerp(acc, Color.WHITE, 0.45));
        into.add(l);
        return w;
    }

    /**
     * Centred rows of chips for the given cards (end screen), wrapping at {@code maxW}; returns the y below the last
     * row (or {@code y} when there are none).
     */
    static double chipRows(GCompound into, List<PatchNote> notes, double cx, double y, double maxW) {
        if (notes.isEmpty()) return y;
        Font f = Cyber.mono(Font.BOLD, 11);
        double h = 22, gap = 8;
        List<List<PatchNote>> rows = new ArrayList<>();
        List<PatchNote> row = new ArrayList<>();
        double rw = 0;
        for (PatchNote p : notes) {
            double w = chipWidth(p.chip, f);
            if (!row.isEmpty() && rw + gap + w > maxW) { rows.add(row); row = new ArrayList<>(); rw = 0; }
            rw += (row.isEmpty() ? 0 : gap) + w;
            row.add(p);
        }
        rows.add(row);
        for (List<PatchNote> r : rows) {
            double total = -gap;
            for (PatchNote p : r) total += gap + chipWidth(p.chip, f);
            double x = cx - total / 2;
            for (PatchNote p : r) x += chip(into, p, x, y, h, f) + gap;
            y += h + 6;
        }
        return y;
    }

    // ------------------------------------------------------------------ hover cards
    /** Hover card for an active patch note: title, theme, flavour, upsides and downsides. Top-left at (0, 0). */
    static GCompound noteCard(PatchNote p, int pickedBefore) {
        Color acc = accent(p.category);
        List<String[]> lines = new ArrayList<>();
        for (Mods.Effect e : p.upsides(pickedBefore)) lines.add(new String[] { "+", e.text });
        for (Mods.Effect e : p.downsides(pickedBefore)) lines.add(new String[] { "-", e.text });
        return hoverCard(p.title.toUpperCase(), Cyber.spaced(p.category.name() + "  //  shipped before wave " + pickedBefore), p.flavor, lines, acc);
    }

    /** Hover card for a news event. */
    static GCompound newsCard(BreakingNews n, int wave, boolean live) {
        List<String[]> lines = new ArrayList<>();
        for (Mods.Effect e : n.mods().effects(wave)) lines.add(new String[] { e.good ? "+" : "-", e.text });
        String when = live ? "live now  //  ends when wave " + wave + " is cleared" : "breaks on wave " + wave + "  //  lasts that wave";
        return hoverCard("BREAKING: " + n.title.toUpperCase(), Cyber.spaced(when), n.flavor, lines, Cyber.RED);
    }

    private static GCompound hoverCard(String title, String micro, String flavor, List<String[]> lines, Color acc) {
        GCompound c = new GCompound();
        double w = 360, x = 14, tw = w - 28;
        List<GLabel> parts = new ArrayList<>();
        double y = 28;
        parts.add(Ui.label(title, x, y, fit(title, Cyber.display(Font.BOLD, 18), tw), Cyber.lerp(acc, Color.WHITE, 0.5)));
        y += 17;
        parts.add(Ui.label(micro, x, y, Cyber.mono(Font.BOLD, 9), Cyber.alpha(acc, 220)));
        y += 19;
        for (String l : Ui.wrap(flavor, Cyber.body(Font.PLAIN, 13), tw)) { parts.add(Ui.label(l, x, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)); y += 16; }
        y += 6;
        Font f = Cyber.body(Font.BOLD, 13);
        for (String[] l : lines) {
            Color col = l[0].equals("+") ? Cyber.GREEN : Cyber.RED;
            boolean first = true;
            for (String part : Ui.wrap(l[1], f, tw - 16)) {
                if (first) parts.add(Ui.label(l[0], x, y, Cyber.mono(Font.BOLD, 13), col));
                parts.add(Ui.label(part, x + 16, y, f, Cyber.TEXT));
                first = false;
                y += 17;
            }
        }
        double h = y + 4;
        c.add(new Cyber.Chamfer(0, 0, w, h, 10).scan(false).fill(new Color(5, 9, 22, 248)).border(acc).glow(0.7).lineWidth(1.6));
        c.add(Ui.rect(0, 6, 4, h - 12, acc, acc));
        for (GLabel l : parts) c.add(l);
        return c;
    }

    private static Font fit(String text, Font f, double w) {
        Font cur = f;
        for (int sz = f.getSize(); sz > 10 && Ui.label(text, 0, 0, cur, Color.WHITE).getWidth() > w; sz--) cur = Cyber.display(Font.BOLD, sz - 1);
        return cur;
    }

    /** Places a label centred on {@code cx} at baseline {@code y}. */
    private static void centered(GCompound into, String text, double cx, double y, Font f, Color col) {
        GLabel l = Ui.label(text, 0, y, f, col);
        l.setLocation(cx - l.getWidth() / 2, y);
        into.add(l);
    }
}
