"""Lindefense Thick (ported from src/lindefense/ui/sprites/Thick.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class Thick:
    """ACM primitives that paint with a configurable, round-joined outline width
(and anti-aliasing) instead of the fixed one-pixel stroke. The cartoon art
direction wants a thick dark outline on every shape; these are the only
primitives the sprites use.

Paint cost
Every visible shape is an anti-aliased rasterization (two when it has an outline), and in a big fight there are
thousands per frame, so these primitives avoid work that cannot change a pixel:

  an outline of width 0 or with a fully transparent colour is not stroked (the fill is drawn alone, exactly as
      ACM would draw it); a fully transparent fill is not filled;
  anti-aliasing is switched on only if the Graphics2D does not already have it (the game's root layer
      sets all quality hints once per frame), instead of re-setting the hint for every shape;
  level of detail: each shape has a Outlined#setDetail detail level (0 = essential). While
      #level() is at or above a shape's level the shape is skipped at paint time. The world view raises the
      level when many enemies are on screen; sprites tag gloss, shadows, eyes, cracks and similar small parts. Skipping
      at paint time leaves visibility, z-order and every sprite's own logic untouched. A shape can also have an
      Outlined#setOutlineDetail outline detail tier at which it keeps its fill but drops its outline."""
    class Outlined:
        """A shape whose outline width can be set."""
        def set_line_width(self, w):
            """Sets the outline width in logical px (0 hides the outline)."""
            raise NotImplementedError
        def get_line_width(self):
            """Current outline width, or negative if never set."""
            raise NotImplementedError
        def set_detail(self, detail):
            """Sets the level-of-detail tier of this shape (0 = always drawn, see Thick#setLevel)."""
            raise NotImplementedError
        def get_detail(self):
            """The level-of-detail tier of this shape."""
            raise NotImplementedError
        def set_outline_detail(self, detail):
            """Sets the tier at which only the outline is dropped (the fill is still drawn); 0 = never."""
            raise NotImplementedError
    class Oval(GOval, Outlined):
        """Oval with a thick outline."""
        def __init__(self, x, y, w, h):
            self.detail = 0
            self.outline_detail = 0
            self.s = None
            GOval.__init__(self, x, y, w, h)
            self.width = (-1)
        def set_line_width(self, w):
            self.width = w
            self.s = Thick.stroke(w)
        def get_line_width(self):
            return self.width
        def set_detail(self, d):
            self.detail = d
        def get_detail(self):
            return self.detail
        def set_outline_detail(self, d):
            self.outline_detail = d
        def paint(self, g):
            lvl = Thick.f_level
            d = self.detail
            if d != 0 and d <= lvl:
                return
            lc = self._color if self._color is not None else Color.BLACK
            od = self.outline_detail
            if self.width == 0 or (lc._argb >> 24) == 0 or (od != 0 and od <= lvl):
                if self._filled:
                    fc = self._fill_color if self._fill_color is not None else lc
                    if (fc._argb >> 24) != 0:
                        Thick.aa(g)
                        g._fill_oval_c(self._x, self._y, self._w, self._h, fc)
                return
            st = self.s
            if st is None:
                st = self.s = Thick.stroke((1 if (self.width < 0) else self.width))
            old = g.stroke
            if g.hints.get(RenderingHints.KEY_ANTIALIASING) != RenderingHints.VALUE_ANTIALIAS_ON:
                g.hints[RenderingHints.KEY_ANTIALIASING] = RenderingHints.VALUE_ANTIALIAS_ON
            g.stroke = st
            if self._filled:
                g._fill_draw_oval(self._x, self._y, self._w, self._h,
                                  self._fill_color if self._fill_color is not None else lc, lc)
            else:
                g.draw_oval(self._x, self._y, self._w, self._h)
            g.stroke = old
    class Rect(GRect, Outlined):
        """Rectangle with a thick outline."""
        def __init__(self, x, y, w, h):
            self.detail = 0
            self.outline_detail = 0
            self.s = None
            GRect.__init__(self, x, y, w, h)
            self.width = (-1)
        def set_line_width(self, w):
            self.width = w
            self.s = Thick.stroke(w)
        def get_line_width(self):
            return self.width
        def set_detail(self, d):
            self.detail = d
        def get_detail(self):
            return self.detail
        def set_outline_detail(self, d):
            self.outline_detail = d
        def paint(self, g):
            lvl = Thick.f_level
            d = self.detail
            if d != 0 and d <= lvl:
                return
            lc = self._color if self._color is not None else Color.BLACK
            od = self.outline_detail
            if self.width == 0 or (lc._argb >> 24) == 0 or (od != 0 and od <= lvl):
                if self._filled:
                    fc = self._fill_color if self._fill_color is not None else lc
                    if (fc._argb >> 24) != 0:
                        Thick.aa(g)
                        g._fill_rect_c(self._x, self._y, self._w, self._h, fc)
                return
            st = self.s
            if st is None:
                st = self.s = Thick.stroke((1 if (self.width < 0) else self.width))
            old = g.stroke
            if g.hints.get(RenderingHints.KEY_ANTIALIASING) != RenderingHints.VALUE_ANTIALIAS_ON:
                g.hints[RenderingHints.KEY_ANTIALIASING] = RenderingHints.VALUE_ANTIALIAS_ON
            g.stroke = st
            if self._filled:
                g._fill_draw_rect(self._x, self._y, self._w, self._h,
                                  self._fill_color if self._fill_color is not None else lc, lc)
            else:
                g.draw_rect(self._x, self._y, self._w, self._h)
            g.stroke = old
    class Poly(GPolygon, Outlined):
        """Polygon with a thick outline."""
        def __init__(self):
            self.detail = 0
            self.outline_detail = 0
            self.s = None
            GPolygon.__init__(self)
            self.width = (-1)
        def set_line_width(self, w):
            self.width = w
            self.s = Thick.stroke(w)
        def get_line_width(self):
            return self.width
        def set_detail(self, d):
            self.detail = d
        def get_detail(self):
            return self.detail
        def set_outline_detail(self, d):
            self.outline_detail = d
        def paint(self, g):
            lvl = Thick.f_level
            d = self.detail
            if d != 0 and d <= lvl:
                return
            lc = self._color if self._color is not None else Color.BLACK
            od = self.outline_detail
            if self.width == 0 or (lc._argb >> 24) == 0 or (od != 0 and od <= lvl):
                if self._filled:
                    fc = self._fill_color if self._fill_color is not None else lc
                    if (fc._argb >> 24) != 0:
                        if not self._vx:
                            return
                        Thick.aa(g)
                        g._fill_path_c(self._cached()[3]._p, fc)
                return
            st = self.s
            if st is None:
                st = self.s = Thick.stroke((1 if (self.width < 0) else self.width))
            old = g.stroke
            if g.hints.get(RenderingHints.KEY_ANTIALIASING) != RenderingHints.VALUE_ANTIALIAS_ON:
                g.hints[RenderingHints.KEY_ANTIALIASING] = RenderingHints.VALUE_ANTIALIAS_ON
            if self._vx:
                g.stroke = st
                path = self._cached()[3]
                if self._filled:
                    g._fill_draw_path(path._p, self._fill_color if self._fill_color is not None else lc, lc)
                else:
                    g.draw(path)
                g.stroke = old
    class Arc(GArc, Outlined):
        """Arc with a thick outline."""
        def __init__(self, x, y, w, h, start, sweep):
            self.detail = 0
            self.outline_detail = 0
            self.s = None
            GArc.__init__(self, x, y, w, h, start, sweep)
            self.width = (-1)
        def set_line_width(self, w):
            self.width = w
            self.s = Thick.stroke(w)
        def get_line_width(self):
            return self.width
        def set_detail(self, d):
            self.detail = d
        def get_detail(self):
            return self.detail
        def set_outline_detail(self, d):
            self.outline_detail = d
        def paint(self, g):
            if Thick.skipped(self.detail):
                return
            if (not Thick.strokes(self.width, self.get_color())) or Thick.skipped(self.outline_detail):
                if self.is_filled() and Thick.visible(self.get_fill_color()):
                    Thick.aa(g)
                    r = self.get_awt_bounds()
                    g.set_color(self.get_fill_color())
                    g.fill_arc(r.x, r.y, r.width, r.height, GMath.round(self.get_start_angle()), GMath.round(self.get_sweep_angle()))
                return
            if self.s is None:
                self.s = Thick.stroke((1 if (self.width < 0) else self.width))
            old = Thick.begin(g, self.s)
            super(Thick.Arc, self).paint(g)
            g.set_stroke(old)
    class Line(GLine, Outlined):
        """Line with a thick stroke."""
        def __init__(self, x0, y0, x1, y1):
            self.detail = 0
            self.outline_detail = 0
            self.s = None
            GLine.__init__(self, x0, y0, x1, y1)
            self.width = (-1)
        def set_line_width(self, w):
            self.width = w
            self.s = Thick.stroke(w)
        def get_line_width(self):
            return self.width
        def set_detail(self, d):
            self.detail = d
        def get_detail(self):
            return self.detail
        def set_outline_detail(self, d):
            self.outline_detail = d
        def paint(self, g):
            if (Thick.skipped(self.detail) or Thick.skipped(self.outline_detail)) or (not Thick.strokes(self.width, self.get_color())):
                return
            if self.s is None:
                self.s = Thick.stroke((1 if (self.width < 0) else self.width))
            old = Thick.begin(g, self.s)
            super(Thick.Line, self).paint(g)
            g.set_stroke(old)
    def __init__(self):
        pass
    @staticmethod
    def set_level(lod):
        """Sets the level of detail for subsequent paints and returns the previous one (restore it when done).
Shapes whose detail level is non-zero and at most lod are skipped."""
        old = Thick.f_level
        Thick.f_level = lod
        return old
    @staticmethod
    def level():
        """The level of detail currently being painted."""
        return Thick.f_level
    @staticmethod
    def stroke(w):
        return BasicStroke(_j.dmax(0.1, w), BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
    @staticmethod
    def begin(g, s):
        g2 = g
        old = g2.get_stroke()
        if g2.get_rendering_hint(RenderingHints.KEY_ANTIALIASING) != RenderingHints.VALUE_ANTIALIAS_ON:
            g2.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
        g2.set_stroke(s)
        return old
    @staticmethod
    def skipped(detail):
        """True if a shape of this detail tier is skipped at the current level."""
        return (detail != 0) and (detail <= Thick.f_level)
    @staticmethod
    def strokes(width, c):
        """True if an outline of this width and colour would change pixels."""
        return (width != 0) and ((c is None) or (c.get_alpha() != 0))
    @staticmethod
    def visible(c):
        return (c is None) or (c.get_alpha() != 0)
    @staticmethod
    def aa(g):
        """Turns anti-aliasing on for a fill-only paint if the context does not have it yet."""
        g2 = g
        if g2.get_rendering_hint(RenderingHints.KEY_ANTIALIASING) != RenderingHints.VALUE_ANTIALIAS_ON:
            g2.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)


Thick.NORMAL = 2.2
Thick.BOSS = 3.4
Thick.DETAIL = 1.4
Thick.LINE = 1.8
Thick.DETAIL_DECOR = 1
Thick.DETAIL_FINE = 2
Thick.f_level = 0
Thick.Oval.serial_version_uid = 1
Thick.Rect.serial_version_uid = 1
Thick.Poly.serial_version_uid = 1
Thick.Arc.serial_version_uid = 1
Thick.Line.serial_version_uid = 1

from lindefense.ui import acm as _acm  # noqa: E402
_acm.PaintCache.add_global(Thick.level)
for _c in (Thick.Oval, Thick.Rect, Thick.Poly, Thick.Arc, Thick.Line):
    _acm.pure_paint(_c)
    for _m in ("set_line_width", "set_detail", "set_outline_detail"):
        setattr(_c, _m, _acm.touching(_c.__dict__[_m]))
