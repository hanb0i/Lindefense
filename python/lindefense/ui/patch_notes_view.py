"""Lindefense PatchNotesView (ported from src/lindefense/ui/PatchNotesView.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.variance import variance
from lindefense.variance.variance import PatchNote
from lindefense.variance.variance import RunVariance


class PatchNotesView:
    """Drawing for the run-variance features: the "Patch Notes" draft overlay (three cards, pick one), the card chips used
on the end screen, and the hover cards for chips and news. Stateless builders; GameScreen owns the overlay
and RunStrip the in-game strip."""
    def __init__(self):
        pass
    @staticmethod
    def accent(c):
        """Card colour by theme."""
        _sw1 = c
        if _sw1 is PatchNote.Category.ECONOMY:
            return Cyber.YELLOW
        elif _sw1 is PatchNote.Category.CONTROL:
            return Cyber.MAGENTA
        elif _sw1 is PatchNote.Category.SURVIVAL:
            return Cyber.GREEN
        else:
            return Cyber.CYAN
    @staticmethod
    def seed_text(game):
        """"SEED K3X9QZ"."""
        return _j.cat('SEED ', variance.seed_format(game.get_seed()))
    @staticmethod
    def build_draft(overlay, buttons, game, on_pick):
        """Builds the draft overlay over the playfield: title, the three offered cards (each fully clickable, plus a SHIP IT
button) and a footer with the active cards, seed and draft number. Returns the title label."""
        v = game.get_variance()
        offer = v.get_offer()
        wave = v.get_offer_wave()
        overlay.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)))
        cx = (Ui.WORLD_X + (Ui.WORLD_W / 2.0))
        pw = 1140.0
        ph = 624.0
        px = (cx - (pw / 2))
        py = (Ui.WORLD_Y + ((Ui.WORLD_H - ph) / 2))
        overlay.add(Cyber.Chamfer(px, py, pw, ph, 6))
        micro = _j.cat('Version 1.', (len(v.get_active()) + 1), '  ·  ', ('Launch build' if (wave <= 1) else _j.cat('Pre-wave ', wave, ' hotfix')))
        PatchNotesView.centered(overlay, micro, cx, (py + 44), Cyber.body(Font.PLAIN, 14), Cyber.MUTED)
        title = Ui.label('PATCH NOTES', 0, 0, Cyber.display(Font.BOLD, 46), Cyber.TEXT)
        title.set_location((cx - (title.get_width() / 2)), (py + 96))
        overlay.add(title)
        PatchNotesView.centered(overlay, 'Ship one change. It lasts the rest of the run, and every card has an upside and a downside.', cx, (py + 128), Cyber.body(Font.PLAIN, 16), Cyber.MUTED)
        cw = 344.0
        ch = 388.0
        gap = 24.0
        x0 = (cx - (((len(offer) * cw) + ((len(offer) - 1) * gap)) / 2))
        y0 = (py + 156)
        for i in range(len(offer)):
            index = i
            PatchNotesView.card(overlay, buttons, offer[i], i, wave, (x0 + (i * (cw + gap))), y0, cw, ch, _j.Fn(lambda index=index: on_pick(index)))
        fy = ((py + ph) - 26)
        act = _j.StringBuilder()
        for p in v.get_active():
            act.append(('' if (act.length() == 0) else '  +  ')).append(p.chip)
        left = Ui.label(('No patches yet' if (act.length() == 0) else _j.cat('Active: ', act)), (px + 30), fy, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
        sz = 13
        hint_w = Ui.label(PatchNotesView.HINT, 0, 0, Cyber.body(Font.PLAIN, 13), Cyber.DIM).get_width()
        limit = _j.dmin((pw * 0.42), (((pw - hint_w) / 2) - 46))
        while (left.get_width() > limit) and (sz > 7):
            left.set_font(Cyber.body(Font.PLAIN, sz))
            sz -= 1
        if left.get_width() > limit:
            left.set_label(_j.cat('Active: ', len(v.get_active()), ' patches'))
            left.set_font(Cyber.body(Font.PLAIN, 13))
        overlay.add(left)
        PatchNotesView.centered(overlay, PatchNotesView.HINT, cx, fy, Cyber.body(Font.PLAIN, 13), Cyber.DIM)
        right = Ui.label(_j.cat(PatchNotesView.seed_text(game), '   ·   Draft ', v.get_draft_number(), (_j.cat(' of ', len(RunVariance.DRAFT_WAVES)) if (v.get_draft_number() <= len(RunVariance.DRAFT_WAVES)) else '  ·  Freeplay')), 0, fy, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
        right.set_location((((px + pw) - 30) - right.get_width()), fy)
        overlay.add(right)
        return title
    @staticmethod
    def card(overlay, buttons, p, index, wave, x, y, w, h, pick):
        """One offered card: theme colour, key badge, title, flavour, upsides, downsides and a SHIP IT button."""
        acc = PatchNotesView.accent(p.category)
        overlay.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.SURFACE_2))
        key = Ui.label(_j.s((index + 1)), 0, 0, Cyber.mono(Font.BOLD, 14), Cyber.INK)
        overlay.add(Cyber.Chamfer((x + 18), (y + 22), 24, 24, 3).fill(acc).border(None))
        key.set_location(((x + 18) + ((24 - key.get_width()) / 2)), (y + 39))
        overlay.add(key)
        theme = Ui.label(PatchNotesView.sentence(p.category.name), 0, (y + 39), Cyber.body(Font.BOLD, 13), acc)
        theme.set_location((((x + w) - 18) - theme.get_width()), (y + 39))
        overlay.add(theme)
        tw = (w - 36)
        yy = (y + 80)
        tf = Cyber.display(Font.BOLD, 26)
        tl = Ui.wrap(p.title.upper(), tf, tw)
        if len(tl) > 2:
            tf = Cyber.display(Font.BOLD, 21)
            tl = Ui.wrap(p.title.upper(), tf, tw)
        for l in tl:
            overlay.add(Ui.label(l, (x + 18), yy, tf, Cyber.TEXT))
            yy += (tf.get_size() + 4)
        yy += 2
        for l in Ui.wrap(p.flavor, Cyber.body(Font.PLAIN, 14), tw):
            overlay.add(Ui.label(l, (x + 18), yy, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
            yy += 18
        yy += 6
        overlay.add(Ui.rect((x + 18), yy, tw, 1, Cyber.EDGE, Cyber.EDGE))
        yy += 22
        yy = PatchNotesView.effects(overlay, 'Upside', p.upsides(wave), Cyber.good(), (x + 18), yy, tw)
        yy += 8
        PatchNotesView.effects(overlay, 'Downside', p.downsides(wave), Cyber.bad(), (x + 18), yy, tw)
        area = UIButton(x, y, w, h, '', Cyber.mono(Font.BOLD, 1), pick)
        area.set_flat(True)
        area.set_accent(acc)
        overlay.add(area)
        _j_add(buttons, area)
        ship = UIButton((x + 18), ((y + h) - 58), (w - 36), 42, _j.cat('SHIP IT  [', (index + 1), ']'), Cyber.display(Font.BOLD, 18), pick)
        ship.set_accent(acc)
        overlay.add(ship)
        _j_add(buttons, ship)
        area.animate(0)
        ship.animate(0)
    @staticmethod
    def effects(into, head, lines, col, x, y, w):
        """An "Upside" block of bullet lines; returns the y below it."""
        into.add(Ui.label(head, x, y, Cyber.body(Font.PLAIN, 13), Cyber.alpha(col, 230)))
        y += 22
        f = Cyber.body(Font.BOLD, 15)
        for e in lines:
            first = True
            for l in Ui.wrap(e.text, f, (w - 20)):
                if first:
                    into.add(Ui.label(('+' if e.good else '-'), (x + 2), y, Cyber.mono(Font.BOLD, 15), col))
                into.add(Ui.label(l, (x + 20), y, f, Cyber.TEXT))
                first = False
                y += 20
            y += 3
        return y
    @staticmethod
    def chip_width(text, f):
        """Width of a chip for text in f."""
        probe = Ui.label(text, 0, 0, f, Color.WHITE)
        return probe.get_width() + 18
    @staticmethod
    def chip(into, p, x, y, h, f):
        """One chip (chamfered tag with a theme-coloured border), top-left at (x, y); returns its width."""
        acc = PatchNotesView.accent(p.category)
        w = PatchNotesView.chip_width(p.chip, f)
        into.add(Cyber.Chamfer(x, y, w, h, 3).fill(Cyber.SURFACE_2))
        into.add(Ui.rect((x + 1), (y + 1), 2, (h - 2), acc, acc))
        l = Ui.label(p.chip, (x + 10), ((y + (h / 2)) + (f.get_size() * 0.36)), f, Cyber.TEXT)
        into.add(l)
        return w
    @staticmethod
    def chip_rows(into, notes, cx, y, max_w):
        """Centred rows of chips for the given cards (end screen), wrapping at maxW; returns the y below the last
row (or y when there are none)."""
        if len(notes) == 0:
            return y
        f = Cyber.mono(Font.BOLD, 11)
        h = 22.0
        gap = 8.0
        rows = _j.ArrayList()
        row = _j.ArrayList()
        rw = 0.0
        for p in notes:
            w = PatchNotesView.chip_width(p.chip, f)
            if (not (len(row) == 0)) and (((rw + gap) + w) > max_w):
                _j_add(rows, row)
                row = _j.ArrayList()
                rw = 0.0
            rw += ((0 if (len(row) == 0) else gap) + w)
            _j_add(row, p)
        _j_add(rows, row)
        for r in rows:
            total = (-gap)
            for p in r:
                total += (gap + PatchNotesView.chip_width(p.chip, f))
            x = (cx - (total / 2))
            for p in r:
                x += (PatchNotesView.chip(into, p, x, y, h, f) + gap)
            y += (h + 6)
        return y
    @staticmethod
    def note_card(p, picked_before):
        """Hover card for an active patch note: title, theme, flavour, upsides and downsides. Top-left at (0, 0)."""
        acc = PatchNotesView.accent(p.category)
        lines = _j.ArrayList()
        for e in p.upsides(picked_before):
            _j_add(lines, ['+', e.text])
        for e in p.downsides(picked_before):
            _j_add(lines, ['-', e.text])
        return PatchNotesView.hover_card(p.title.upper(), _j.cat(PatchNotesView.sentence(p.category.name), '  ·  shipped before wave ', picked_before), p.flavor, lines, acc)
    @staticmethod
    def news_card(n, wave, live):
        """Hover card for a news event."""
        lines = _j.ArrayList()
        for e in n.mods().effects(wave):
            _j_add(lines, [('+' if e.good else '-'), e.text])
        when = (_j.cat('Live now  ·  ends when wave ', wave, ' is cleared') if live else _j.cat('Breaks on wave ', wave, '  ·  lasts that wave'))
        return PatchNotesView.hover_card(_j.cat('BREAKING: ', n.title.upper()), when, n.flavor, lines, Cyber.RED)
    @staticmethod
    def hover_card(title, micro, flavor, lines, acc):
        c = GCompound()
        w = 360.0
        x = 14.0
        tw = (w - 28)
        parts = _j.ArrayList()
        y = 28.0
        _j_add(parts, Ui.label(title, x, y, PatchNotesView.fit(title, Cyber.display(Font.BOLD, 18), tw), Cyber.TEXT))
        y += 18
        _j_add(parts, Ui.label(micro, x, y, Cyber.body(Font.PLAIN, 12), Cyber.lerp(acc, Cyber.MUTED, 0.35)))
        y += 20
        for l in Ui.wrap(flavor, Cyber.body(Font.PLAIN, 13), tw):
            _j_add(parts, Ui.label(l, x, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
            y += 16
        y += 6
        f = Cyber.body(Font.BOLD, 13)
        for l in lines:
            col = (Cyber.good() if (l[0] == '+') else Cyber.bad())
            first = True
            for part in Ui.wrap(l[1], f, (tw - 16)):
                if first:
                    _j_add(parts, Ui.label(l[0], x, y, Cyber.mono(Font.BOLD, 13), col))
                _j_add(parts, Ui.label(part, (x + 16), y, f, Cyber.TEXT))
                first = False
                y += 17
        h = (y + 4)
        c.add(Cyber.Chamfer(0, 0, w, h, 4).fill(Color(9, 14, 28, 250)).border(Cyber.EDGE_HI))
        c.add(Ui.rect(1, 1, 3, (h - 2), acc, acc))
        for l in parts:
            c.add(l)
        return c
    @staticmethod
    def sentence(name):
        """ECONOMY -> Economy."""
        return name[0:1].upper() + name[1:].lower()
    @staticmethod
    def fit(text, f, w):
        cur = f
        sz = f.get_size()
        while (sz > 10) and (Ui.label(text, 0, 0, cur, Color.WHITE).get_width() > w):
            cur = Cyber.display(Font.BOLD, (sz - 1))
            sz -= 1
        return cur
    @staticmethod
    def centered(into, text, cx, y, f, col):
        """Places a label centred on cx at baseline y."""
        l = Ui.label(text, 0, y, f, col)
        l.set_location((cx - (l.get_width() / 2)), y)
        into.add(l)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

PatchNotesView.HINT = 'Press 1, 2 or 3, or click a card'
