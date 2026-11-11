"""Lindefense Art (ported from src/lindefense/ui/sprites/towers/Art.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class Art:
    """Cartoon drawing helpers shared by every tower, projectile and effect sprite.

The ACM library has no stroke width, so the thin dark outline of the
cartoon look is produced by drawing an "ink" copy of each shape that is
#OUT logical pixels larger, then the coloured fill on top. Helpers
that take a GCompound add both pieces to it and return the fill
object so callers can mutate it later.

Every shape is a Flat primitive: transparent parts are never
rasterized, decorative helpers (#gloss, #sparkle,
#shadow) are tagged lindefense.ui.sprites.Thick#DETAIL_DECOR,
ink underlays drop their one-pixel outline (half a pixel of border) at that
tier and every other shape drops its outline at
lindefense.ui.sprites.Thick#DETAIL_FINE, so crowded screens paint
fewer shapes (see lindefense.ui.sprites.Thick#setLevel)."""
    def __init__(self):
        pass
    @staticmethod
    def rgb(v):
        """Opaque colour from a 0xRRGGBB int."""
        return Color(v)
    @staticmethod
    def _alpha_0(c, a):
        """Copy of c with the given alpha (0-255)."""
        if type(a) is int:
            return Color._with_alpha(c, a)
        return Color(c.get_red(), c.get_green(), c.get_blue(), max(0, min(255, a)))
    @staticmethod
    def _alpha_1(v, a):
        """Colour with alpha from a 0xRRGGBB int."""
        return Art.alpha(Color(v), a)
    @staticmethod
    def alpha(*a):
        if len(a) == 2:
            if isinstance(a[0], Color) and (isinstance(a[1], int) and not isinstance(a[1], bool)):
                return Art._alpha_0(*a)
            return Art._alpha_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    @staticmethod
    def shade(c, k):
        """Shades a colour: k < 1 darkens multiplicatively, k > 1
lightens toward white by k - 1."""
        key = (c._argb, k)
        r = _SHADES.get(key)
        if r is None:
            r = Art._shade(c, k)
            if len(_SHADES) >= 4096:
                _SHADES.clear()
            _SHADES[key] = r
        return r
    @staticmethod
    def _shade(c, k):
        if k <= 1:
            return Color(Art.clamp((c.get_red() * k)), Art.clamp((c.get_green() * k)), Art.clamp((c.get_blue() * k)), c.get_alpha())
        t = _j.dmin(1, (k - 1))
        return Color(Art.clamp((c.get_red() + ((255 - c.get_red()) * t))), Art.clamp((c.get_green() + ((255 - c.get_green()) * t))), Art.clamp((c.get_blue() + ((255 - c.get_blue()) * t))), c.get_alpha())
    @staticmethod
    def mix(a, b, t):
        """Linear mix of two colours."""
        t = _j.dmax(0, _j.dmin(1, t))
        return Color(Art.clamp((a.get_red() + ((b.get_red() - a.get_red()) * t))), Art.clamp((a.get_green() + ((b.get_green() - a.get_green()) * t))), Art.clamp((a.get_blue() + ((b.get_blue() - a.get_blue()) * t))), Art.clamp((a.get_alpha() + ((b.get_alpha() - a.get_alpha()) * t))))
    @staticmethod
    def clamp(v):
        return max(0, min(255, _j.jround(v)))
    @staticmethod
    def disc(g, cx, cy, rad, fill):
        """Adds an outlined filled circle centred at (cx, cy); returns the fill oval."""
        return Art.ellipse(g, cx, cy, rad, rad, fill)
    @staticmethod
    def ellipse(g, cx, cy, rx, ry, fill):
        """Adds an outlined filled ellipse; returns the fill oval."""
        ink = Flat.Oval(((cx - rx) - Art.OUT), ((cy - ry) - Art.OUT), (2 * (rx + Art.OUT)), (2 * (ry + Art.OUT)))
        ink.set_filled(True)
        ink.set_fill_color(Art.INK)
        ink.set_color(Art.INK)
        ink.set_outline_detail(Thick.DETAIL_DECOR)
        g.add(ink)
        o = Flat.Oval((cx - rx), (cy - ry), (2 * rx), (2 * ry))
        o.set_outline_detail(Thick.DETAIL_FINE)
        o.set_filled(True)
        o.set_fill_color(fill)
        o.set_color(Art.shade(fill, 0.75))
        g.add(o)
        return o
    @staticmethod
    def box(g, x, y, w, h, fill):
        """Adds an outlined filled rectangle; returns the fill rect."""
        ink = Flat.Rect((x - Art.OUT), (y - Art.OUT), (w + (2 * Art.OUT)), (h + (2 * Art.OUT)))
        ink.set_filled(True)
        ink.set_fill_color(Art.INK)
        ink.set_color(Art.INK)
        ink.set_outline_detail(Thick.DETAIL_DECOR)
        g.add(ink)
        r = Flat.Rect(x, y, w, h)
        r.set_outline_detail(Thick.DETAIL_FINE)
        r.set_filled(True)
        r.set_fill_color(fill)
        r.set_color(Art.shade(fill, 0.75))
        g.add(r)
        return r
    @staticmethod
    def poly(g, xy, fill):
        """Adds an outlined filled polygon from flat {x0,y0,x1,y1,...}; returns the fill polygon."""
        g.add(Art.raw_poly(Art.expand(xy, Art.OUT), Art.INK, Art.INK))
        p = Art.raw_poly(xy, fill, Art.shade(fill, 0.75))
        g.add(p)
        return p
    @staticmethod
    def plain(g, xy, fill):
        """Adds an un-outlined polygon (for glows, glosses, shadows)."""
        p = Art.raw_poly(xy, fill, fill)
        g.add(p)
        return p
    @staticmethod
    def raw_poly(xy, fill, outline):
        """Builds a filled polygon whose origin is (0,0) so it can be rotated about that pivot."""
        p = Flat.Poly()
        p.set_outline_detail((Thick.DETAIL_DECOR if ((Art.INK == fill) and (Art.INK == outline)) else Thick.DETAIL_FINE))
        i = 0
        while (i + 1) < len(xy):
            p.add_vertex(xy[i], xy[(i + 1)])
            i += 2
        p.set_filled(True)
        p.set_fill_color(fill)
        p.set_color(outline)
        return p
    @staticmethod
    def gloss(g, cx, cy, rx, ry):
        """Big glossy highlight: a soft white ellipse."""
        o = Flat.Oval((cx - rx), (cy - ry), (2 * rx), (2 * ry))
        o.set_detail(Thick.DETAIL_DECOR)
        o.set_filled(True)
        o.set_fill_color(Art.alpha(Color.WHITE, 120))
        o.set_color(Art.alpha(Color.WHITE, 0))
        g.add(o)
        return o
    @staticmethod
    def sparkle(g, cx, cy, s):
        """Small four-point white sparkle."""
        p = Flat.detail(Art.raw_poly(Art.star(cx, cy, s, (s * 0.3), 4, 0), Art.alpha(Color.WHITE, 230), Art.alpha(Color.WHITE, 0)), Thick.DETAIL_DECOR)
        g.add(p)
        return p
    @staticmethod
    def shadow(g, cx, cy, rx, ry):
        """Soft semi-transparent ground shadow."""
        o = Flat.Oval((cx - rx), (cy - ry), (2 * rx), (2 * ry))
        o.set_detail(Thick.DETAIL_DECOR)
        o.set_filled(True)
        o.set_fill_color(Art.alpha(0x08061a, 70))
        o.set_color(Art.alpha(0x08061a, 0))
        g.add(o)
        return o
    @staticmethod
    def glow(g, cx, cy, rad, c, a):
        """Soft glow disc without outline."""
        o = Flat.Oval((cx - rad), (cy - rad), (2 * rad), (2 * rad))
        o.set_filled(True)
        o.set_fill_color(Art.alpha(c, a))
        o.set_color(Art.alpha(c, 0))
        g.add(o)
        return o
    @staticmethod
    def body(g, cx, cy, rad, fill):
        """Two-tone cartoon body: outline, dark tone, lighter tone offset to the
upper-left, and a glossy highlight. Returns the light-tone oval."""
        Art.ellipse(g, cx, cy, rad, rad, Art.shade(fill, 0.78))
        light = Flat.Oval(((cx - (rad * 0.86)) - (rad * 0.1)), ((cy - (rad * 0.86)) - (rad * 0.1)), (rad * 1.72), (rad * 1.72))
        light.set_outline_detail(Thick.DETAIL_FINE)
        light.set_filled(True)
        light.set_fill_color(fill)
        light.set_color(fill)
        g.add(light)
        Art.gloss(g, (cx - (rad * 0.38)), (cy - (rad * 0.42)), (rad * 0.32), (rad * 0.2))
        return light
    @staticmethod
    def body_box(g, x, y, w, h, fill):
        """Two-tone rectangular body with gloss. Returns the light rect."""
        Art.box(g, x, y, w, h, Art.shade(fill, 0.78))
        light = Flat.Rect(x, y, (w * 0.85), (h * 0.85))
        light.set_outline_detail(Thick.DETAIL_FINE)
        light.set_filled(True)
        light.set_fill_color(fill)
        light.set_color(fill)
        g.add(light)
        Art.gloss(g, (x + (w * 0.28)), (y + (h * 0.22)), (w * 0.18), (h * 0.1))
        return light
    @staticmethod
    def circle(cx, cy, rad, n):
        """Circle approximated by n vertices."""
        return Art.regular(cx, cy, rad, n, 0)
    @staticmethod
    def regular(cx, cy, rad, n, rot_deg):
        """Regular polygon; rotDeg rotates it (0 puts a vertex at the top)."""
        v = ([0.0] * (n * 2))
        for i in range(n):
            a = (math.radians((rot_deg - 90)) + (((i * 2) * math.pi) / n))
            v[(2 * i)] = (cx + (math.cos(a) * rad))
            v[((2 * i) + 1)] = (cy + (math.sin(a) * rad))
        return v
    @staticmethod
    def star(cx, cy, ro, ri, n, rot_deg):
        """Star with n points."""
        v = ([0.0] * (n * 4))
        for i in range(2 * n):
            a = (math.radians((rot_deg - 90)) + ((i * math.pi) / n))
            rad = (ro if (_j.imod(i, 2) == 0) else ri)
            v[(2 * i)] = (cx + (math.cos(a) * rad))
            v[((2 * i) + 1)] = (cy + (math.sin(a) * rad))
        return v
    @staticmethod
    def ring(cx, cy, ro, ri, n):
        """Ring (annulus) with a real hole: the outer loop followed by the inner
loop, which the even-odd fill rule of fillPolygon leaves empty."""
        outer = Art.circle(cx, cy, ro, n)
        inner = Art.circle(cx, cy, ri, n)
        return Art.join(outer, inner)
    @staticmethod
    def gear_ring(cx, cy, ro, rs, ri, n):
        """Spiky ring: star outline outside, round hole inside."""
        return Art.join(Art.star(cx, cy, ro, rs, n, 0), Art.circle(cx, cy, ri, (n * 2)))
    @staticmethod
    def join(outer, inner):
        no = _j.idiv(len(outer), 2)
        ni = _j.idiv(len(inner), 2)
        v = ([0.0] * ((((no + 1) + ni) + 1) * 2))
        k = 0
        for i in range(no):
            v[((k := k + 1) - 1)] = outer[(2 * i)]
            v[((k := k + 1) - 1)] = outer[((2 * i) + 1)]
        v[((k := k + 1) - 1)] = outer[0]
        v[((k := k + 1) - 1)] = outer[1]
        for i in range(ni + 1):
            j = _j.imod((ni - i), ni)
            v[((k := k + 1) - 1)] = inner[(2 * j)]
            v[((k := k + 1) - 1)] = inner[((2 * j) + 1)]
        return v
    @staticmethod
    def rect(x, y, w, h):
        """Axis-aligned rectangle vertices."""
        return [x, y, (x + w), y, (x + w), (y + h), x, (y + h)]
    @staticmethod
    def bar(x0, y0, x1, y1, hw):
        """Capsule / rounded bar from (x0,y0) to (x1,y1) with half-width hw."""
        dx = (x1 - x0)
        dy = (y1 - y0)
        len_ = math.hypot(dx, dy)
        if len_ < 1e-6:
            dx = 1.0
            dy = 0.0
            len_ = 1.0
        base = math.atan2((dy / len_), (dx / len_))
        seg = 6
        v = ([0.0] * ((seg + 1) * 4))
        k = 0
        for i in range(seg + 1):
            a = ((base - (math.pi / 2)) + ((i * math.pi) / seg))
            v[((k := k + 1) - 1)] = (x1 + (math.cos(a) * hw))
            v[((k := k + 1) - 1)] = (y1 + (math.sin(a) * hw))
        for i in range(seg + 1):
            a = ((base + (math.pi / 2)) + ((i * math.pi) / seg))
            v[((k := k + 1) - 1)] = (x0 + (math.cos(a) * hw))
            v[((k := k + 1) - 1)] = (y0 + (math.sin(a) * hw))
        return v
    @staticmethod
    def wedge(x0, x1, hw, cy):
        """Isosceles arrow / wedge pointing along +x: base at x0 of half-width hw, tip at x1."""
        return [x0, (cy - hw), x1, cy, x0, (cy + hw)]
    @staticmethod
    def bolt(x0, x1, amp, th):
        """Lightning zigzag along +x from x0 to x1 with amplitude amp and thickness th."""
        m = ((x0 + x1) / 2)
        q = ((x0 + m) / 2)
        q3 = ((m + x1) / 2)
        return [x0, 0, q, (-amp), (m - (th * 0.5)), ((-amp) * 0.2), q3, (-amp), x1, 0, (q3 - th), (amp * 0.1), (m + (th * 0.5)), (amp * 0.9), (q - th), (amp * 0.3)]
    @staticmethod
    def shift(xy, dx, dy):
        """Translates vertices."""
        v = list(xy)
        i = 0
        while (i + 1) < len(v):
            v[i] += dx
            v[(i + 1)] += dy
            i += 2
        return v
    @staticmethod
    def spin(xy, deg):
        """Rotates vertices about (0,0) by degrees (screen-space, clockwise positive)."""
        a = math.radians(deg)
        c = math.cos(a)
        s = math.sin(a)
        v = ([0.0] * len(xy))
        i = 0
        while (i + 1) < len(xy):
            v[i] = ((xy[i] * c) - (xy[(i + 1)] * s))
            v[(i + 1)] = ((xy[i] * s) + (xy[(i + 1)] * c))
            i += 2
        return v
    @staticmethod
    def scaled(xy, k):
        """Scales vertices about (0,0)."""
        v = ([0.0] * len(xy))
        for i in range(len(xy)):
            v[i] = (xy[i] * k)
        return v
    @staticmethod
    def mirror(xy):
        """Mirrors vertices horizontally about x = 0."""
        v = list(xy)
        i = 0
        while (i + 1) < len(v):
            v[i] = (-v[i])
            i += 2
        return v
    @staticmethod
    def expand(xy, by):
        """Expands a polygon away from its centroid by by pixels (approximate outline)."""
        n = _j.idiv(len(xy), 2)
        cx = 0.0
        cy = 0.0
        for i in range(n):
            cx += xy[(2 * i)]
            cy += xy[((2 * i) + 1)]
        cx = (cx / n)
        cy = (cy / n)
        v = ([0.0] * len(xy))
        for i in range(n):
            dx = (xy[(2 * i)] - cx)
            dy = (xy[((2 * i) + 1)] - cy)
            d = math.hypot(dx, dy)
            k = (0 if (d < 1e-6) else ((d + (by * 1.15)) / d))
            v[(2 * i)] = (cx + (dx * k))
            v[((2 * i) + 1)] = (cy + (dy * k))
        return v


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.thick import Thick  # noqa: E402
from lindefense.ui.sprites.towers.flat import Flat  # noqa: E402

Art.INK = Color(0x1d1430)
Art.OUT = 1.5
Art.GOLD = Color(0xffd34d)
Art.GOLD_DARK = Color(0xd29a12)
Art.GOLD_LIGHT = Color(0xfff1a8)
Art.SLATE = Color(0x3a4256)
Art.SLATE_LIGHT = Color(0x5a647c)
Art.METAL = Color(0x6f7a90)
Art.METAL_LIGHT = Color(0xb8c2d6)

_SHADES = {}   # (argb, k) -> Art.shade result
