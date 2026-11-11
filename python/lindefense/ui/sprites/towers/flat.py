"""Lindefense Flat (ported from src/lindefense/ui/sprites/towers/Flat.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class Flat:
    """The plain ACM shapes used by tower, projectile and attack-effect art (Art): an GOval,
GRect and GPolygon that paint exactly like the ACM originals (fill, then the default one-pixel
outline) but skip work that cannot change a pixel or that the current level of detail drops:

  a fully transparent fill or outline is not drawn at all (glows, gloss, shadows and effect bars use
      transparent outlines; each skipped outline is one anti-aliased rasterization saved per frame);
  a shape with a #setDetail detail tier is skipped while the world view paints at that
      Thick#level() level of detail or above (decorative shadow, gloss, sparkles, glows);
  a shape with an #setOutlineDetail outline tier keeps its fill but drops the one-pixel outline at that
      level (in very large fights).

The tiers are Thick#DETAIL_DECOR and Thick#DETAIL_FINE, shared with the enemy sprites."""
    class Detailed:
        """A shape with level-of-detail tiers."""
        def set_detail(self, tier):
            """Tier at which the whole shape is skipped (0 = always drawn)."""
            raise NotImplementedError
        def set_outline_detail(self, tier):
            """Tier at which only the outline is dropped (0 = always drawn)."""
            raise NotImplementedError
    class Oval(GOval, Detailed):
        """GOval with transparent-part skipping and detail tiers."""
        def __init__(self, x, y, w, h):
            self.detail = 0
            self.outline_detail = 0
            GOval.__init__(self, x, y, w, h)
        def set_detail(self, tier):
            self.detail = tier
        def set_outline_detail(self, tier):
            self.outline_detail = tier
        def paint(self, g):
            d = self.detail
            if d != 0 and d <= Thick.f_level:
                return
            lc = self._color if self._color is not None else Color.BLACK
            fc = (self._fill_color if self._fill_color is not None else lc) if self._filled else None
            fill = fc is not None and (fc._argb >> 24) != 0
            od = self.outline_detail
            line = (lc._argb >> 24) != 0 and not (od != 0 and od <= Thick.f_level)
            if fill and line:
                g._fill_draw_oval(self._x, self._y, self._w, self._h, fc, lc)
            elif fill:
                g._fill_oval_c(self._x, self._y, self._w, self._h, fc)
            elif line:
                g._draw_oval_c(self._x, self._y, self._w, self._h, lc)
    class Rect(GRect, Detailed):
        """GRect with transparent-part skipping and detail tiers."""
        def __init__(self, x, y, w, h):
            self.detail = 0
            self.outline_detail = 0
            GRect.__init__(self, x, y, w, h)
        def set_detail(self, tier):
            self.detail = tier
        def set_outline_detail(self, tier):
            self.outline_detail = tier
        def paint(self, g):
            d = self.detail
            if d != 0 and d <= Thick.f_level:
                return
            lc = self._color if self._color is not None else Color.BLACK
            fc = (self._fill_color if self._fill_color is not None else lc) if self._filled else None
            fill = fc is not None and (fc._argb >> 24) != 0
            od = self.outline_detail
            line = (lc._argb >> 24) != 0 and not (od != 0 and od <= Thick.f_level)
            if fill and line:
                g._fill_draw_rect(self._x, self._y, self._w, self._h, fc, lc)
            elif fill:
                g._fill_rect_c(self._x, self._y, self._w, self._h, fc)
            elif line:
                g._draw_rect_c(self._x, self._y, self._w, self._h, lc)
    class Poly(GPolygon, Detailed):
        """GPolygon with transparent-part skipping and detail tiers."""
        def __init__(self):
            self.detail = 0
            self.outline_detail = 0
            GPolygon.__init__(self)
        def set_detail(self, tier):
            self.detail = tier
        def set_outline_detail(self, tier):
            self.outline_detail = tier
        def paint(self, g):
            d = self.detail
            if d != 0 and d <= Thick.f_level:
                return
            if not self._vx:
                return
            pc = self._cached()
            lc = self._color if self._color is not None else Color.BLACK
            fc = (self._fill_color if self._fill_color is not None else lc) if self._filled else None
            fill = fc is not None and (fc._argb >> 24) != 0
            od = self.outline_detail
            line = (lc._argb >> 24) != 0 and not (od != 0 and od <= Thick.f_level)
            if fill and line:
                g._fill_draw_path(pc[3]._p, fc, lc)
            elif fill:
                g._fill_path_c(pc[3]._p, fc)
            elif line:
                g._draw_path_c(pc[3]._p, lc)
    def __init__(self):
        pass
    @staticmethod
    def skipped(tier):
        return (tier != 0) and (tier <= Thick.level())
    @staticmethod
    def visible(c):
        return (c is None) or (c.get_alpha() != 0)
    @staticmethod
    def detail(g, tier):
        """Tags any shape that supports it (other GObjects are left alone); returns it for chaining."""
        if isinstance(g, Flat.Detailed):
            g.set_detail(tier)
        return g


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.thick import Thick  # noqa: E402

Flat.Oval.serial_version_uid = 1
Flat.Rect.serial_version_uid = 1
Flat.Poly.serial_version_uid = 1

from lindefense.ui import acm as _acm  # noqa: E402
for _c in (Flat.Oval, Flat.Rect, Flat.Poly):
    _acm.pure_paint(_c)
    for _m in ("set_detail", "set_outline_detail"):
        setattr(_c, _m, _acm.touching(_c.__dict__[_m]))
