"""Lindefense Cyber (ported from src/lindefense/ui/Cyber.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.jenum import JEnum


class Cyber:
    """Cyberpunk UI toolkit: palette, font fallback chains, number formatting, Java2D
quality hints and a handful of custom ACM objects that paint with real strokes
(flat chamfered panels, progress bars, rings, vector icons, a background grid).
Every object is built once and mutated per frame (setters only change fields)."""
    class Chamfer(GObject):
        """Flat panel: one fill and one thin border around a rectangle with small cut top-left / bottom-right corners
(the cut is capped at Cyber.CUT, so every panel, card and button shares the same quiet silhouette)."""
        def __init__(self, x, y, w, h, cut):
            GObject.__init__(self)
            self.f_fill = Cyber.SURFACE
            self.f_border = Cyber.EDGE
            self.line_w = 1.0
            self.f_alpha = 1.0
            self.w = w
            self.h = h
            self.cut = cut
            self.set_location(x, y)
        def fill(self, c):
            self.f_fill = c
            return self
        def border(self, c):
            self.f_border = c
            return self
        def line_width(self, lw):
            self.line_w = lw
            return self
        def alpha(self, a):
            self.f_alpha = a
            return self
        def size(self, nw, nh):
            self.w = nw
            self.h = nh
            return self
        def get_w(self):
            return self.w
        def get_h(self):
            return self.h
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint(self, g):
            if self.f_alpha <= 0.004:
                return
            g2 = g.create()
            try:
                Cyber.quality(g2)
                if self.f_alpha < 1.0:
                    g2.set_composite(AlphaComposite.SrcOver.derive(self.f_alpha))
                in_ = (self.line_w / 2)
                p = Cyber.chamfer((self.get_x() + in_), (self.get_y() + in_), (self.w - self.line_w), (self.h - self.line_w), _j.dmin(self.cut, Cyber.CUT))
                if (self.f_fill is not None) and (self.f_fill.get_alpha() > 0):
                    g2.set_color(self.f_fill)
                    g2.fill(p)
                if (self.f_border is not None) and (self.f_border.get_alpha() > 0):
                    g2.set_stroke(Cyber.stroke(self.line_w))
                    g2.set_color(self.f_border)
                    g2.draw(p)
            finally:
                g2.dispose()
    class Grid(GObject):
        """Faint background grid drawn as one path (a full-screen grid is a single fill): 1 px lines every step px."""
        def __init__(self, x, y, w, h, step, color):
            GObject.__init__(self)
            self.w = w
            self.h = h
            self.color = color
            p = Path2D.Double()
            gx = 0.0
            while gx <= w:
                p.append(Rectangle2D.Double(gx, 0, 1, h), False)
                gx += step
            gy = 0.0
            while gy <= h:
                p.append(Rectangle2D.Double(0, gy, w, 1), False)
                gy += step
            self.path = p
            self.set_location(x, y)
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint(self, g):
            g2 = g.create()
            try:
                g2.translate(self.get_x(), self.get_y())
                g2.set_color(self.color)
                g2.fill(self.path)
            finally:
                g2.dispose()
    class Light(GObject):
        """A soft, static pool of light: a radial gradient from color at (cx, cy) to transparent at radius r, stretched
by sy vertically, filling the w x h rectangle at its location (one draw call)."""
        def __init__(self, x, y, w, h, cx, cy, r, sy, color):
            GObject.__init__(self)
            self.w = w
            self.h = h
            self.cx = cx
            self.cy = cy
            self.r = r
            self.sy = sy
            self.color = color
            self.set_location(x, y)
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint(self, g):
            g2 = g.create()
            try:
                g2.translate(self.cx, self.cy)
                g2.scale(1.0, self.sy)
                g2.set_paint(RadialGradientPaint(Point2D.Double(0, 0), self.r, [0.0, 1.0], [self.color, Cyber.alpha(self.color, 0)]))
                g2.fill(Rectangle2D.Double((self.get_x() - self.cx), ((self.get_y() - self.cy) / self.sy), self.w, (self.h / self.sy)))
            finally:
                g2.dispose()
    class Ring(GObject):
        """Ellipse with fill and a crisp outline of arbitrary width (optionally dashed)."""
        def __init__(self, x, y, w, h, fill, line):
            self.w = 0.0
            self.h = 0.0
            self.fill = None
            self.line = None
            self.dashed = False
            self.dash_phase = 0.0
            GObject.__init__(self)
            self.line_w = 1.6
            self.w = w
            self.h = h
            self.fill = fill
            self.line = line
            self.set_location(x, y)
        def set(self, cx, cy, r):
            self.h = (2 * r)
            self.w = self.h
            self.set_location((cx - r), (cy - r))
        def set_fill(self, c):
            self.fill = c
        def set_line(self, c):
            self.line = c
        def set_line_width(self, lw):
            self.line_w = lw
        def set_dashed(self, d):
            self.dashed = d
        def set_phase(self, p):
            self.dash_phase = p
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint(self, g):
            g2 = g.create()
            try:
                Cyber.quality(g2)
                e = Ellipse2D.Double((self.get_x() + (self.line_w / 2)), (self.get_y() + (self.line_w / 2)), (self.w - self.line_w), (self.h - self.line_w))
                if self.fill is not None:
                    g2.set_color(self.fill)
                    g2.fill(e)
                if self.line is not None:
                    g2.set_stroke((BasicStroke(self.line_w, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [10.0, 7.0], self.dash_phase) if self.dashed else Cyber.stroke(self.line_w)))
                    g2.set_color(self.line)
                    g2.draw(e)
            finally:
                g2.dispose()
    class Bar(GObject):
        """Progress bar with dark backing, outline, optional chamfered ends, trailing "recent damage" chunk and notches."""
        def __init__(self, x, y, w, h, cut):
            self.w = 0.0
            self.h = 0.0
            self.cut = 0.0
            self.hold_timer = 0.0
            self.use_trail = False
            GObject.__init__(self)
            self.value = 1.0
            self.f_trail = 1.0
            self.fill = Cyber.GREEN
            self.back = Color(0, 0, 0, 190)
            self.outline = Color(0, 0, 0, 230)
            self.trail_color = Color(255, 255, 255, 200)
            self.f_notches = ([0.0] * 0)
            self.line_w = 1.0
            self.w = w
            self.h = h
            self.cut = cut
            self.set_location(x, y)
        def colors(self, fill, back, outline):
            self.fill = fill
            self.back = back
            self.outline = outline
            return self
        def trail(self, t, c):
            self.use_trail = t
            if c is not None:
                self.trail_color = c
            return self
        def notches(self, n):
            self.f_notches = n
            return self
        def line_width(self, lw):
            self.line_w = lw
            return self
        def set_fill(self, c):
            self.fill = c
        def set_value(self, v):
            v = _j.dmax(0, _j.dmin(1, v))
            if v < (self.value - 1e-9):
                self.hold_timer = 0.45
            self.value = v
            if (not self.use_trail) or (v > self.f_trail):
                self.f_trail = v
        def get_value(self):
            return self.value
        def set_size(self, nw, nh):
            self.w = nw
            self.h = nh
        def step(self, dt):
            """Eases the trailing chunk toward the live value."""
            if (not self.use_trail) or (self.f_trail <= self.value):
                return
            if self.hold_timer > 0:
                self.hold_timer -= dt
                return
            self.f_trail = _j.dmax(self.value, (self.f_trail - (dt * _j.dmax(0.25, ((self.f_trail - self.value) * 2.0)))))
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint_simple(self, g2, lod):
            """Reduced bar for crowded screens (the world view's level of detail, see
lindefense.ui.sprites.Thick#setLevel): backing and value only, plus the outline at level 1. Two or
three fills instead of six plus a clip; plain enemy HP bars only (no chamfer, trail or notches)."""
            old = g2.get_color()
            x = self.get_x()
            y = self.get_y()
            g2.set_color(self.back)
            g2.fill(Rectangle2D.Double(x, y, self.w, self.h))
            fw = ((self.w - (2 * self.line_w)) * self.value)
            if fw > 0.3:
                g2.set_color(self.fill)
                g2.fill(Rectangle2D.Double((x + self.line_w), y, fw, self.h))
            if (lod < 2) and (self.outline is not None):
                os_ = g2.get_stroke()
                g2.set_stroke(Cyber.stroke(_j.dmax(1, self.line_w)))
                g2.set_color(self.outline)
                g2.draw(Rectangle2D.Double((x + 0.5), (y + 0.5), (self.w - 1), (self.h - 1)))
                g2.set_stroke(os_)
            g2.set_color(old)
        def paint(self, g):
            lod = Thick.level()
            if (((lod > 0) and (self.cut <= 0)) and (not self.use_trail)) and (len(self.f_notches) == 0):
                self.paint_simple(g, lod)
                return
            g2 = g.create()
            try:
                Cyber.quality(g2)
                x = self.get_x()
                y = self.get_y()
                shape = (Cyber.chamfer(x, y, self.w, self.h, self.cut) if (self.cut > 0) else Rectangle2D.Double(x, y, self.w, self.h))
                g2.set_color(self.back)
                g2.fill(shape)
                old = g2.get_clip()
                g2.clip(shape)
                inner = self.line_w
                fw = ((self.w - (2 * inner)) * self.value)
                if self.use_trail and (self.f_trail > self.value):
                    g2.set_color(self.trail_color)
                    g2.fill(Rectangle2D.Double(((x + inner) + fw), y, ((self.w - (2 * inner)) * (self.f_trail - self.value)), self.h))
                if fw > 0.3:
                    g2.set_color(self.fill)
                    g2.fill(Rectangle2D.Double((x + inner), y, fw, self.h))
                    g2.set_color(Color(255, 255, 255, 62))
                    g2.fill(Rectangle2D.Double((x + inner), y, fw, _j.dmax(1, (self.h * 0.38))))
                    g2.set_color(Color(0, 0, 0, 55))
                    g2.fill(Rectangle2D.Double((x + inner), (y + (self.h * 0.72)), fw, (self.h * 0.28)))
                g2.set_color(Color(0, 0, 0, 200))
                for n in self.f_notches:
                    g2.fill(Rectangle2D.Double((((x + inner) + ((self.w - (2 * inner)) * n)) - 1), y, 2, self.h))
                g2.set_clip(old)
                if self.outline is not None:
                    g2.set_stroke(Cyber.stroke(_j.dmax(1, self.line_w)))
                    g2.set_color(self.outline)
                    g2.draw((Cyber.chamfer((x + 0.5), (y + 0.5), (self.w - 1), (self.h - 1), self.cut) if (self.cut > 0) else Rectangle2D.Double((x + 0.5), (y + 0.5), (self.w - 1), (self.h - 1))))
            finally:
                g2.dispose()
    class Text(GLabel):
        """GLabel whose width / ascent are measured with a fractional-metrics, anti-aliased FontRenderContext and which draws with
the same context at sub-pixel positions, so centring, right-alignment and fitting match what is painted at any scale."""
        def _init_0(self, s):
            GLabel.__init__(self, s)
            pass
        def _init_1(self, s, x, y):
            GLabel.__init__(self, s, x, y)
            pass
        def __init__(self, *a):
            if len(a) == 1:
                return self._init_0(*a)
            elif len(a) == 3:
                return self._init_1(*a)
            raise TypeError('no overload for %d args' % len(a))
        def get_width(self):
            return self.get_font().get_string_bounds(self.get_label(), Cyber.Text.FRC).get_width()
        def get_ascent(self):
            return self.get_font().get_line_metrics('Ag', Cyber.Text.FRC).get_ascent()
        def get_descent(self):
            return self.get_font().get_line_metrics('Ag', Cyber.Text.FRC).get_descent()
        def get_height(self):
            return self.get_ascent() + self.get_descent()
        def get_bounds(self):
            return GRectangle(self.get_x(), (self.get_y() - self.get_ascent()), self.get_width(), self.get_height())
        def paint(self, g):
            g2 = g.create()
            try:
                Cyber.quality(g2)
                g2.set_font(self.get_font())
                g2.set_color(self.get_color())
                g2.draw_string(self.get_label(), self.get_x(), self.get_y())
            finally:
                g2.dispose()
    class Kind(JEnum):
        """Vector glyphs for HUD chips and buttons."""
        PLAY = ()
        PAUSE = ()
        CASH = ()
        HEART = ()
        WAVE = ()
        ENEMY = ()
        AUTO = ()
        MENU = ()
        FAST = ()
        CHECK = ()
        SKULL = ()
        SPEAKER = ()
        NOTE = ()
    class Icon(GObject):
        """A small flat vector icon, size x size, drawn at its location (top-left)."""
        def __init__(self, kind, size, color):
            self.kind = None
            self.size = 0.0
            self.color = None
            self.struck = False
            GObject.__init__(self)
            self.kind = kind
            self.size = size
            self.color = color
        def set_kind(self, k):
            self.kind = k
        def set_struck(self, s):
            """Draws a diagonal strike-through (used by the Sound / Music "off" state)."""
            self.struck = s
        def set_icon_color(self, c):
            self.color = c
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.size, self.size)
        def paint(self, g):
            g2 = g.create()
            try:
                Cyber.quality(g2)
                g2.translate(self.get_x(), self.get_y())
                g2.scale((self.size / 16.0), (self.size / 16.0))
                g2.set_color(self.color)
                g2.set_stroke(BasicStroke(1.7, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                _sw1 = self.kind
                if _sw1 is Cyber.Kind.PLAY:
                    p = Path2D.Double()
                    p.move_to(3.5, 2)
                    p.line_to(13.5, 8)
                    p.line_to(3.5, 14)
                    p.close_path()
                    g2.fill(p)
                    pass  # break
                elif _sw1 is Cyber.Kind.PAUSE:
                    g2.fill(Rectangle2D.Double(3.5, 2.5, 3.2, 11))
                    g2.fill(Rectangle2D.Double(9.3, 2.5, 3.2, 11))
                elif _sw1 is Cyber.Kind.FAST:
                    p = Path2D.Double()
                    p.move_to(1.5, 3)
                    p.line_to(8, 8)
                    p.line_to(1.5, 13)
                    p.close_path()
                    p.move_to(8, 3)
                    p.line_to(14.5, 8)
                    p.line_to(8, 13)
                    p.close_path()
                    g2.fill(p)
                    pass  # break
                elif _sw1 is Cyber.Kind.CASH:
                    hex = Path2D.Double()
                    hex.move_to(8, 1)
                    hex.line_to(14, 4.5)
                    hex.line_to(14, 11.5)
                    hex.line_to(8, 15)
                    hex.line_to(2, 11.5)
                    hex.line_to(2, 4.5)
                    hex.close_path()
                    g2.draw(hex)
                    g2.fill(Rectangle2D.Double(7.2, 4.2, 1.6, 7.6))
                    g2.draw(Line2D.Double(5.6, 6.2, 10.4, 6.2))
                    g2.draw(Line2D.Double(5.6, 9.8, 10.4, 9.8))
                    pass  # break
                elif _sw1 is Cyber.Kind.HEART:
                    p = Path2D.Double()
                    p.move_to(8, 14.2)
                    p.curve_to(1.5, 9.6, 0.6, 6.4, 2.2, 4.0)
                    p.curve_to(4.0, 1.6, 7.0, 2.6, 8, 5.0)
                    p.curve_to(9.0, 2.6, 12.0, 1.6, 13.8, 4.0)
                    p.curve_to(15.4, 6.4, 14.5, 9.6, 8, 14.2)
                    p.close_path()
                    g2.fill(p)
                    pass  # break
                elif _sw1 is Cyber.Kind.WAVE:
                    p = Path2D.Double()
                    p.move_to(1, 8)
                    p.curve_to(3, 1, 5, 1, 7, 8)
                    p.curve_to(9, 15, 11, 15, 15, 8)
                    g2.draw(p)
                    pass  # break
                elif _sw1 is Cyber.Kind.ENEMY:
                    d = Path2D.Double()
                    d.move_to(8, 1.2)
                    d.line_to(14.8, 8)
                    d.line_to(8, 14.8)
                    d.line_to(1.2, 8)
                    d.close_path()
                    g2.draw(d)
                    g2.fill(Ellipse2D.Double(5.8, 5.8, 4.4, 4.4))
                    pass  # break
                elif _sw1 is Cyber.Kind.AUTO:
                    g2.draw(Arc2D.Double(2.2, 2.2, 11.6, 11.6, 40, 270, Arc2D.OPEN))
                    a = Path2D.Double()
                    a.move_to(13.6, 1.5)
                    a.line_to(13.6, 6.6)
                    a.line_to(8.8, 5.2)
                    a.close_path()
                    g2.fill(a)
                    pass  # break
                elif _sw1 is Cyber.Kind.MENU:
                    for i in range(3):
                        g2.fill(Rectangle2D.Double(2.5, (3 + (i * 4.2)), 11, 1.8))
                elif _sw1 is Cyber.Kind.CHECK:
                    p = Path2D.Double()
                    p.move_to(2.5, 8.5)
                    p.line_to(6.5, 12.5)
                    p.line_to(13.5, 3.5)
                    g2.draw(p)
                    pass  # break
                elif _sw1 is Cyber.Kind.SKULL:
                    g2.draw(Ellipse2D.Double(2.5, 1.5, 11, 9.5))
                    g2.fill(Ellipse2D.Double(5, 5, 2.2, 2.6))
                    g2.fill(Ellipse2D.Double(8.8, 5, 2.2, 2.6))
                    g2.draw(Line2D.Double(6, 14, 10, 14))
                elif _sw1 is Cyber.Kind.SPEAKER:
                    p = Path2D.Double()
                    p.move_to(1.5, 5.8)
                    p.line_to(4.6, 5.8)
                    p.line_to(8.2, 2.6)
                    p.line_to(8.2, 13.4)
                    p.line_to(4.6, 10.2)
                    p.line_to(1.5, 10.2)
                    p.close_path()
                    g2.fill(p)
                    g2.draw(Arc2D.Double(6.2, 4.6, 5.0, 6.8, (-60), 120, Arc2D.OPEN))
                    g2.draw(Arc2D.Double(5.4, 2.4, 8.6, 11.2, (-55), 110, Arc2D.OPEN))
                    pass  # break
                elif _sw1 is Cyber.Kind.NOTE:
                    g2.fill(Ellipse2D.Double(2.6, 10.0, 4.8, 3.8))
                    g2.fill(Ellipse2D.Double(9.2, 8.6, 4.8, 3.8))
                    g2.draw(Line2D.Double(7.2, 11.4, 7.2, 2.8))
                    g2.draw(Line2D.Double(13.8, 10.0, 13.8, 2.0))
                    g2.draw(Line2D.Double(7.2, 2.8, 13.8, 2.0))
                else:
                    pass
                if self.struck:
                    g2.set_stroke(BasicStroke(3.4, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                    g2.set_color(Color(0x0a1020))
                    g2.draw(Line2D.Double(2.6, 1.6, 14.2, 14.4))
                    g2.set_stroke(BasicStroke(1.8, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                    g2.set_color(Cyber.RED)
                    g2.draw(Line2D.Double(2.6, 1.6, 14.2, 14.4))
            finally:
                g2.dispose()
    def __init__(self):
        pass
    @staticmethod
    def alpha(c, a):
        return Color(c.get_red(), c.get_green(), c.get_blue(), max(0, min(255, a)))
    @staticmethod
    def lerp(a, b, f):
        f = _j.dmax(0, _j.dmin(1, f))
        return Color(_j.to_int(_j.jround((a.get_red() + ((b.get_red() - a.get_red()) * f)))), _j.to_int(_j.jround((a.get_green() + ((b.get_green() - a.get_green()) * f)))), _j.to_int(_j.jround((a.get_blue() + ((b.get_blue() - a.get_blue()) * f)))), _j.to_int(_j.jround((a.get_alpha() + ((b.get_alpha() - a.get_alpha()) * f)))))
    @staticmethod
    def hp_color(f):
        """Green (full) to yellow to red (empty). With COLOUR-BLIND SAFE on: azure down to 75 %, yellow from 50 % to 25 %,
vermillion at 0 (short blends, so the bar never sits in the grey halfway between azure and yellow)."""
        if display_settings.colour_blind():
            return Cyber.lerp(Cyber.YELLOW, Cyber.CB_GOOD, ((f - 0.5) * 4)) if (f > 0.5) else Cyber.lerp(Cyber.CB_BAD, Cyber.YELLOW, (f * 4))
        return Cyber.lerp(Cyber.YELLOW, Cyber.GREEN, ((f - 0.5) * 2)) if (f > 0.5) else Cyber.lerp(Cyber.RED, Cyber.YELLOW, (f * 2))
    @staticmethod
    def good():
        """Colour of a good / OK signal (healthy, affordable, buffed): green, or blue with COLOUR-BLIND SAFE on."""
        return Cyber.CB_GOOD if display_settings.colour_blind() else Cyber.GREEN
    @staticmethod
    def bad():
        """Colour of a bad / warning signal (low HP, unaffordable, debuffed, invalid): red, or orange with COLOUR-BLIND
SAFE on (red and green look alike with deuteranopia and protanopia; azure and vermillion stay apart)."""
        return Cyber.CB_BAD if display_settings.colour_blind() else Cyber.RED
    @staticmethod
    def cant_afford():
        """Colour of a price you cannot pay yet (next to the yellow of one you can): red, or pink with COLOUR-BLIND SAFE."""
        return Cyber.CB_SHORT if display_settings.colour_blind() else Cyber.RED
    @staticmethod
    def set_color(l, c):
        """Sets a GLabel colour only when it changed (avoids needless repaint requests)."""
        if not (c == l.get_color()):
            l.set_color(c)
    @staticmethod
    def set_text(l, s):
        if not (s == l.get_label()):
            l.set_label(s)
    @staticmethod
    def load_fonts():
        if Cyber.loaded:
            return
        Cyber.loaded = True
        dirs = _j.ArrayList()
        _j_add(dirs, Assets.file('assets/fonts'))
        _j_add(dirs, _j.File('assets/fonts'))
        _j_add(dirs, _j.File(_j.get_property('user.dir', '.'), 'assets/fonts'))
        _j_add(dirs, _j.File('../assets/fonts'))
        try:
            code = _j.File(Cyber)
            root = (code.get_parent_file() if code.is_directory() else (None if (code.get_parent_file() is None) else code.get_parent_file().get_parent_file()))
            if root is not None:
                _j_add(dirs, _j.File(root, 'assets/fonts'))
        except Exception as ignored:
            pass
        for name in Cyber.FONT_FILES:
            f = None
            for d in dirs:
                file = _j.File(d, name)
                if not file.is_file():
                    continue
                in_ = FileInputStream(file)
                try:
                    f = Font.create_font(Font.TRUETYPE_FONT, in_)
                    break
                except Exception as ignored:
                    pass
            if f is None:
                in_ = Cyber
                try:
                    if in_ is not None:
                        f = Font.create_font(Font.TRUETYPE_FONT, in_)
                except Exception as ignored:
                    pass
            if f is not None:
                _j_put(Cyber.FILES, name, f)
                try:
                    GraphicsEnvironment.get_local_graphics_environment().register_font(f)
                except Exception as ignored:
                    pass
    @staticmethod
    def display(style, size):
        """Display font (headings, buttons, tabs, names, tags): see #DISPLAY_FACE."""
        return Cyber.display_font('V', style, size, 1.0, Cyber.VALORAX_MIN)
    @staticmethod
    def display_compact(style, size):
        """Compact display font for tight spots (tab strips, small chips): the same face at a smaller scale and a lower
size floor than #display."""
        return Cyber.display_font('C', style, size, 0.94, 9)
    @staticmethod
    def display_font(kind, style, size, compact, floor):
        key = _j.cat(kind, Cyber.DISPLAY_FACE, style, '/', size)
        f = Cyber.FONTS.get(key)
        if f is not None:
            return f
        Cyber.load_fonts()
        if (Cyber.DISPLAY_FACE == 'valorax') and (Cyber.FILES.get(Cyber.VALORAX_FILE) is not None):
            f = Cyber.FILES.get(Cyber.VALORAX_FILE).derive_font(float(_j.dmax((9 if (kind == 'C') else Cyber.VALORAX_MIN), (_j.jround(((size * (0.75 if (kind == 'C') else Cyber.VALORAX_SCALE)) * 2)) / 2.0))))
        elif Cyber.DISPLAY_FACE == 'mono':
            base = Cyber.FILES.get(('IBMPlexMono-Bold.ttf' if ((style & Font.BOLD) != 0) else 'IBMPlexMono-Medium.ttf'))
            f = (base.derive_font(float(_j.dmax(floor, (_j.jround((((size * Cyber.MONO_SCALE) * compact) * 2)) / 2.0)))) if (base is not None) else Font(Font.MONOSPACED, style, max(floor, _j.to_int(_j.jround(((size * Cyber.MONO_SCALE) * compact))))))
        else:
            f = Cyber.font('D', 'Rajdhani-Medium.ttf', 'Rajdhani-Bold.ttf', Font.SANS_SERIF, style, size)
        _j_put(Cyber.FONTS, key, f)
        return f
    @staticmethod
    def mono(style, size):
        """Monospace font for numbers and data readouts: IBM Plex Mono."""
        return Cyber.font('M', 'IBMPlexMono-Medium.ttf', 'IBMPlexMono-Bold.ttf', Font.MONOSPACED, style, size)
    @staticmethod
    def body(style, size):
        """Clean sans font for paragraph text: Barlow."""
        return Cyber.font('B', 'Barlow-Regular.ttf', 'Barlow-SemiBold.ttf', Font.SANS_SERIF, style, size)
    @staticmethod
    def font(kind, plain, bold, fallback, style, size):
        key = _j.cat(kind, style, '/', size)
        f = Cyber.FONTS.get(key)
        if f is None:
            Cyber.load_fonts()
            base = Cyber.FILES.get((bold if ((style & Font.BOLD) != 0) else plain))
            f = (base.derive_font(float(size)) if (base is not None) else Font(fallback, style, size))
            _j_put(Cyber.FONTS, key, f)
        return f
    @staticmethod
    def commas(v):
        return _j.format('%,d', v)
    @staticmethod
    def amount(v):
        """A health / damage figure in full ("38,295,480,666", rounded up), or abbrev()'d once it would not fit a
        panel line (Freeplay's deepest waves; a 64-bit long saturates at 9.2e18)."""
        return Cyber.commas(_j.to_long(float(math.ceil(v)))) if v < 1e15 else Cyber.abbrev(v)
    @staticmethod
    def money(v):
        return _j.cat('$', Cyber.commas(_j.to_long(float(math.floor(v)))))
    @staticmethod
    def abbrev(v):
        """4.2e15 / 3.1T / 1.2M / 845K / 9.5K / 640 (rounds up so a living boss never shows 0). Deep Freeplay health
        reaches 1e130: past 999T it is shown in scientific notation instead of an ever longer number."""
        if v >= 999.5e12:
            return _j.format('%.2g', v).replace('e+', 'e')
        v = float(math.ceil(_j.dmax(0, v)))
        a = v
        suf = ''
        if a >= 1e12:
            a = (a / 1e12)
            suf = 'T'
        elif a >= 1e9:
            a = (a / 1e9)
            suf = 'B'
        elif a >= 1e6:
            a = (a / 1e6)
            suf = 'M'
        elif a >= 1e3:
            a = (a / 1e3)
            suf = 'K'
        if len(suf) == 0:
            return _j.s(_j.to_long(a))
        return _j.format('%.1f%s', a, suf) if (a < 10) else _j.format('%.0f%s', a, suf)
    @staticmethod
    def spaced(s):
        """Upper-case readout text (the bundled mono / display faces are already wide and tracked enough)."""
        return s.upper()
    @staticmethod
    def quality(g2):
        """Applies the shared Java2D quality hints. The root layer sets them once per frame and every child Graphics
inherits them, so when they are already in effect this returns after a few cheap reads instead of re-setting
seven hints for every custom-painted object."""
        if ((((((g2.get_rendering_hint(RenderingHints.KEY_RENDERING) == RenderingHints.VALUE_RENDER_QUALITY) and (g2.get_rendering_hint(RenderingHints.KEY_ANTIALIASING) == RenderingHints.VALUE_ANTIALIAS_ON)) and (g2.get_rendering_hint(RenderingHints.KEY_TEXT_ANTIALIASING) == RenderingHints.VALUE_TEXT_ANTIALIAS_ON)) and (g2.get_rendering_hint(RenderingHints.KEY_STROKE_CONTROL) == RenderingHints.VALUE_STROKE_PURE)) and (g2.get_rendering_hint(RenderingHints.KEY_FRACTIONALMETRICS) == RenderingHints.VALUE_FRACTIONALMETRICS_ON)) and (g2.get_rendering_hint(RenderingHints.KEY_INTERPOLATION) == RenderingHints.VALUE_INTERPOLATION_BILINEAR)) and (g2.get_rendering_hint(RenderingHints.KEY_COLOR_RENDERING) == RenderingHints.VALUE_COLOR_RENDER_QUALITY):
            return
        g2.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
        g2.set_rendering_hint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON)
        g2.set_rendering_hint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY)
        g2.set_rendering_hint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE)
        g2.set_rendering_hint(RenderingHints.KEY_FRACTIONALMETRICS, RenderingHints.VALUE_FRACTIONALMETRICS_ON)
        g2.set_rendering_hint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR)
        g2.set_rendering_hint(RenderingHints.KEY_COLOR_RENDERING, RenderingHints.VALUE_COLOR_RENDER_QUALITY)
    @staticmethod
    def stroke(w):
        return BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
    @staticmethod
    def chamfer(x, y, w, h, c):
        """Rectangle with chamfered top-left and bottom-right corners (the title-card button silhouette)."""
        c = _j.dmax(0, _j.dmin(c, (_j.dmin(w, h) / 2)))
        p = Path2D.Double()
        p.move_to((x + c), y)
        p.line_to((x + w), y)
        p.line_to((x + w), ((y + h) - c))
        p.line_to(((x + w) - c), (y + h))
        p.line_to(x, (y + h))
        p.line_to(x, (y + c))
        p.close_path()
        return p


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.assets import Assets  # noqa: E402
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402

Cyber.CYAN = Color(0x00f0ff)
Cyber.MAGENTA = Color(0xff2bd6)
Cyber.YELLOW = Color(0xffe94a)
Cyber.RED = Color(0xff3b4e)
Cyber.GREEN = Color(0x3bff8a)
# COLOUR-BLIND SAFE palette (checked with deuteranopia / protanopia / tritanopia simulations): azure and vermillion
# stay far apart where green and red merge; violet marks "about to be hit" next to vermillion "hit"; pink marks a price
# you cannot afford next to the yellow of one you can (orange would look like that yellow).
Cyber.CB_GOOD = Color(0x3ea6ff)
Cyber.CB_BAD = Color(0xff6b2b)
Cyber.CB_MARK = Color(0xc28cff)
Cyber.CB_SHORT = Color(0xff5ab4)
Cyber.INK = Color(0x05070f)
Cyber.TEXT = Color(0xe4f8ff)
Cyber.MUTED = Color(0x8aa0bd)
Cyber.DIM = Color(0x5a6d88)
Cyber.LINE = Color(0x1d3a55)
# minimal chrome: flat surfaces, one thin neutral edge, small cuts; colour is kept for meaning (state, signals, accents)
Cyber.SURFACE = Color(9, 14, 28, 244)       # panels and pop-ups
Cyber.SURFACE_2 = Color(14, 21, 40, 236)    # cards and fields inside a panel
Cyber.EDGE = Color(0x23354d)                # the one thin border
Cyber.EDGE_HI = Color(0x3b5573)             # hovered / emphasised border
Cyber.SCRIM = Color(2, 4, 10, 196)          # dims what is behind a pop-up
Cyber.CUT = 6.0                             # largest corner cut of any panel
Cyber.FONTS = _j.HashMap()
Cyber.FILES = _j.HashMap()
Cyber.loaded = False
Cyber.VALORAX_FILE = 'Valorax.otf'
Cyber.FONT_FILES = ['Rajdhani-Medium.ttf', 'Rajdhani-SemiBold.ttf', 'Rajdhani-Bold.ttf', 'Barlow-Regular.ttf', 'Barlow-Medium.ttf', 'Barlow-SemiBold.ttf', 'Barlow-Bold.ttf', 'IBMPlexMono-Regular.ttf', 'IBMPlexMono-Medium.ttf', 'IBMPlexMono-SemiBold.ttf', 'IBMPlexMono-Bold.ttf', Cyber.VALORAX_FILE]
Cyber.VALORAX_SCALE = 0.8
Cyber.VALORAX_MIN = 11
Cyber.MONO_SCALE = 0.9
Cyber.DISPLAY_FACE = _j.get_property('lindefense.font', 'mono').lower()
Cyber.Chamfer.serial_version_uid = 1
Cyber.Ring.serial_version_uid = 1
Cyber.Bar.serial_version_uid = 1
Cyber.Text.serial_version_uid = 1
Cyber.Text.FRC = FontRenderContext(None, True, True)
Cyber.Icon.serial_version_uid = 1
Cyber.Grid.serial_version_uid = 1
Cyber.Light.serial_version_uid = 1
