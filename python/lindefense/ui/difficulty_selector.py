"""Lindefense DifficultySelector (ported from src/lindefense/ui/DifficultySelector.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.sim.difficulty import Difficulty
from lindefense.ui.cyber import Cyber


class DifficultySelector(GCompound):
    """"Difficulty Growth" picker on the map-select screen: four cyberpunk chamfered cards (O(1), O(N), O(N<sup>2</sup>),
O(N<sup>N</sup>)), the selected one lit with a glow and a solid accent rail, plus a one-line description of the selected
mode. Exponents are drawn as a small raised label next to the base instead of relying on tiny superscript glyphs.
Selection is stored in Difficulty#setSelected; hit-testing uses logical coordinates."""
    def __init__(self, x, y, width):
        self.bx = 0.0
        self.by = 0.0
        self.bw = 0.0
        self.bh = 0.0
        self.gap = 0.0
        self.desc = None
        GCompound.__init__(self)
        self.boxes = ([None] * len(Difficulty.values()))
        self.subs = ([None] * len(Difficulty.values()))
        self.names = ([None] * len(Difficulty.values()))
        self.hover = (-1)
        ds = Difficulty.values()
        self.gap = 12.0
        self.bw = ((width - (self.gap * (len(ds) - 1))) / len(ds))
        self.bh = DifficultySelector.HEIGHT
        self.bx = x
        self.by = y
        for i in range(len(ds)):
            px = (self.bx + (i * (self.bw + self.gap)))
            c = Cyber.Chamfer(px, self.by, self.bw, self.bh, 12).scan(False)
            self.boxes[i] = c
            self.add(c)
            n = DifficultySelector.math_label(ds[i], DifficultySelector.NAME_FONT, DifficultySelector.SUP_FONT, DifficultySelector.COLORS[i])
            n.set_location((px + ((self.bw - DifficultySelector.label_width(n)) / 2)), (self.by + 28))
            self.names[i] = n
            self.add(n)
            s = Ui.label(_j.replace_all(ds[i].subtitle, ' \\(.*', '').upper(), 0, 0, DifficultySelector.SUB_FONT, Ui.MUTED)
            s.set_location((px + ((self.bw - s.get_width()) / 2)), (self.by + 47))
            self.subs[i] = s
            self.add(s)
        self.desc = Ui.label('', (self.bx + 4), ((self.by + self.bh) + 22), DifficultySelector.DESC_FONT, Ui.TEXT)
        self.add(self.desc)
        self.refresh()
    @staticmethod
    def label_width(c):
        """Width of a label built by #mathLabel (its rightmost child's right edge)."""
        w = 0.0
        i = 0
        while i < c.get_element_count():
            w = _j.dmax(w, (c.get_element(i).get_x() + c.get_element(i).get_width()))
            i += 1
        return w
    @staticmethod
    def math_label(d, base, sup, col):
        """"O(N" + small raised exponent + ")" as separate labels. The exponent comes from the ASCII form ("O(N^2)", "O(N^N)"),
so it is drawn with the UI font at ~60% size, lifted by a third of the base height. Children are laid out from x = 0
with the baseline at y = 0."""
        g = GCompound()
        ascii = d.ascii_label
        caret = _j.index_of(ascii, '^')
        if caret < 0:
            g.add(Ui.label(ascii, 0, 0, base, col))
            return g
        head = Ui.label(ascii[0:caret], 0, 0, base, col)
        g.add(head)
        close = _j.index_of(ascii, ')', caret)
        exp = ascii[(caret + 1):(len(ascii) if (close < 0) else close)]
        up = Ui.label(exp, (head.get_width() + 1), ((-base.get_size()) * 0.38), sup, col)
        g.add(up)
        if close >= 0:
            g.add(Ui.label(ascii[close:], ((up.get_x() + up.get_width()) + 1), 0, base, col))
        return g
    @staticmethod
    def _display_0(d, f):
        """Label usable anywhere with the given UI font (HUD, result screens): Unicode superscript only where it is legible."""
        if _j.index_of(d.label, 'ᴺ') >= 0:
            return d.ascii_label
        return d.label if (f.can_display_up_to(d.label) == (-1)) else d.ascii_label
    @staticmethod
    def _display_1(d):
        """Label usable anywhere with the default UI font."""
        return DifficultySelector.display(d, Ui.F_BOLD)
    @staticmethod
    def display(*a):
        if len(a) == 1:
            return DifficultySelector._display_1(*a)
        elif len(a) == 2:
            return DifficultySelector._display_0(*a)
        raise TypeError('no overload for %d args' % len(a))
    def refresh(self):
        sel = Difficulty.get_selected()
        ds = Difficulty.values()
        for i in range(len(ds)):
            on = (ds[i] is sel)
            hv = (i == self.hover)
            self.boxes[i].fill((Cyber.alpha(DifficultySelector.COLORS[i], 55) if on else Color(8, 14, 32, (235 if hv else 215)))).border((DifficultySelector.COLORS[i] if on else Cyber.alpha(DifficultySelector.COLORS[i], (210 if hv else 120)))).glow((1.0 if on else (0.4 if hv else 0))).line_width((2.4 if on else 1.4)).ticks(on)
            Cyber.set_color(self.subs[i], (Cyber.TEXT if on else Ui.MUTED))
        self.desc.set_label(_j.cat(DifficultySelector.display(sel), '   ', sel.subtitle, '  -  ', sel.description))
        self.desc.set_color(DifficultySelector.COLORS[sel.ordinal])
    def index_at(self, lx, ly):
        ox = self.get_x()
        oy = self.get_y()
        ds = Difficulty.values()
        for i in range(len(ds)):
            px = ((self.bx + (i * (self.bw + self.gap))) + ox)
            if (((lx >= px) and (lx <= (px + self.bw))) and (ly >= (self.by + oy))) and (ly <= ((self.by + self.bh) + oy)):
                return i
        return -1
    def mouse_moved(self, lx, ly):
        """Hover highlight; returns whether the cursor is over a card."""
        h = self.index_at(lx, ly)
        if h != self.hover:
            self.hover = h
            self.refresh()
        return h >= 0
    def mouse_pressed(self, lx, ly):
        """Handles a click in logical coordinates; returns true if it hit a card."""
        i = self.index_at(lx, ly)
        if i < 0:
            return False
        Difficulty.set_selected(Difficulty.values()[i])
        self.refresh()
        return True


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ui import Ui  # noqa: E402

DifficultySelector.serial_version_uid = 1
DifficultySelector.NAME_FONT = Cyber.display(Font.BOLD, 24)
DifficultySelector.SUP_FONT = Cyber.display(Font.BOLD, 14)
DifficultySelector.SUB_FONT = Cyber.body(Font.PLAIN, 12)
DifficultySelector.DESC_FONT = Cyber.body(Font.PLAIN, 14)
DifficultySelector.COLORS = [Color(0x3bff8a), Color(0x35e0ff), Color(0xff8c3b), Color(0xff3bd0)]
DifficultySelector.HEIGHT = 58.0
