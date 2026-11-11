"""The scene graph's paint fast paths must draw exactly what the plain ACM / Java2D sequences draw.

Sprites are thousands of acm shapes painted every frame, so the shims take shortcuts: GPolygon keeps its Skia path
until the shape changes, filled shapes paint through one Graphics2D call instead of "set_color; fill; set_color;
draw", and the colour helpers work on packed ARGB. Each test paints or computes both ways and compares pixels or
values, including the colour the Graphics is left with (later siblings without a colour of their own inherit it).
"""
import random

import numpy as np
import skia

from lindefense.ui import acm
from lindefense.ui import jrt as _j
from lindefense.ui.jawt import BasicStroke, Color, Graphics2D, PathShape, Polygon, reset_canvas_state
from lindefense.ui.sprites.art import Art
from lindefense.ui.sprites.thick import Thick
from lindefense.ui.sprites.towers.art import Art as TowerArt
from lindefense.ui.sprites.towers.flat import Flat

W, H = 160, 120


def _render(paint):
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cv.clear(0xFF101820)
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.scale(1.7, 1.7)   # fractional device scale, as on a resized Retina window
    g.set_color(Color(10, 200, 30))
    out = paint(g)
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray(), out, g.color._argb


def _reference_paint(o, g):
    """What the shapes painted before the fast paths (acm 1.99 semantics)."""
    if isinstance(o, acm.GPolygon):
        p = skia.Path()
        p.moveTo(o._x + o._vx[0], o._y + o._vy[0])
        for i in range(1, len(o._vx)):
            p.lineTo(o._x + o._vx[i], o._y + o._vy[i])
        p.close()
        s = PathShape(p)
        if o._filled:
            g.set_color(o.get_fill_color())
            g.fill(s)
            g.set_color(o.get_color())
        g.draw(s)
    elif isinstance(o, acm.GOval):
        if o._filled:
            g.set_color(o.get_fill_color())
            g.fill_oval(o._x, o._y, o._w, o._h)
            g.set_color(o.get_color())
        g.draw_oval(o._x, o._y, o._w, o._h)
    else:
        if o._filled:
            g.set_color(o.get_fill_color())
            g.fill_rect(o._x, o._y, o._w, o._h)
            g.set_color(o.get_color())
        g.draw_rect(o._x, o._y, o._w, o._h)


def _shapes():
    rnd = random.Random(4)
    out = []
    for i in range(36):
        kind = i % 3
        if kind == 0:
            o = acm.GPolygon()
            for k in range(3 + i % 5):
                o.add_vertex(rnd.uniform(-20, 20), rnd.uniform(-20, 20))
            o.set_location(rnd.uniform(10, 80), rnd.uniform(10, 60))
        elif kind == 1:
            o = acm.GOval(rnd.uniform(0, 60), rnd.uniform(0, 40), rnd.uniform(0, 30), rnd.uniform(0, 30))
        else:
            o = acm.GRect(rnd.uniform(0, 60), rnd.uniform(0, 40), rnd.choice([0.0, rnd.uniform(0, 30)]), rnd.uniform(0, 30))
        o.set_filled(i % 4 != 0)
        if i % 5:
            o.set_color(Color(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), rnd.choice([0, 128, 255])))
        if i % 3:
            o.set_fill_color(Color(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), rnd.choice([0, 90, 255])))
        out.append(o)
    return out


def test_acm_shapes_paint_like_the_reference(check):
    for i, o in enumerate(_shapes()):
        a, _, ca = _render(lambda g: o.paint(g))
        b, _, cb = _render(lambda g: _reference_paint(o, g))
        check(np.array_equal(a, b), "shape %d (%s) paints the same pixels" % (i, type(o).__name__))
        check(ca == cb, "shape %d leaves the Graphics colour %08x, reference %08x" % (i, ca, cb))
    # with a translucent composite and a thick stroke too
    for i, o in enumerate(_shapes()[:12]):
        def setup(g, paint):
            from lindefense.ui.jawt import AlphaComposite
            g.set_composite(AlphaComposite.get_instance(AlphaComposite.SRC_OVER, 0.6))
            g.set_stroke(BasicStroke(2.5))
            paint(g)
        a, _, _ = _render(lambda g: setup(g, o.paint))
        b, _, _ = _render(lambda g: setup(g, lambda gg: _reference_paint(o, gg)))
        check(np.array_equal(a, b), "shape %d paints the same under alpha 0.6 and a 2.5px stroke" % i)


def test_polygon_cache_follows_every_change(check):
    p = acm.GPolygon()
    for x, y in ((0, 0), (30, 0), (30, 20)):
        p.add_vertex(x, y)
    p.set_location(10, 10)
    p.set_filled(True)

    def same_as_fresh(what):
        a, _, _ = _render(lambda g: p.paint(g))
        b, _, _ = _render(lambda g: _reference_paint(p, g))
        poly = p.get_polygon()
        check(poly.xpoints == [p._x + v for v in p._vx] and poly.ypoints == [p._y + v for v in p._vy],
              "get_polygon() is current after %s" % what)
        check(np.array_equal(a, b), "painted polygon is current after %s" % what)

    same_as_fresh("creation")
    p.add_vertex(0, 25)
    same_as_fresh("add_vertex")
    p.set_location(40, 30)
    same_as_fresh("set_location")
    p.move(-5, 3)
    same_as_fresh("move")
    p.rotate(33)
    same_as_fresh("rotate")
    p.scale(1.3, 0.7)
    same_as_fresh("scale")
    p.recenter()
    same_as_fresh("recenter")
    p.add_polar_edge(12, 45)
    same_as_fresh("add_polar_edge")
    check(p.get_polygon() is p.get_polygon(), "an unchanged polygon reuses its cached Polygon")
    jp = Polygon([0, 10, 10], [0, 0, 10], 3)
    first = jp.path()
    check(jp.path() is first, "java.awt.Polygon reuses its path")
    jp.add_point(0, 10)
    check(jp.path() is not first and jp.path().countPoints() == 4, "add_point rebuilds the path")


def test_sprite_shapes_paint_like_their_java_logic(check):
    """Flat.* and Thick.* paint() were restated in fewer calls; compare with their original logic."""
    def flat_ref(o, g):
        if Flat.skipped(o.detail):
            return
        fill = o.is_filled() and Flat.visible(o.get_fill_color())
        line = Flat.visible(o.get_color()) and not Flat.skipped(o.outline_detail)
        if fill and line:
            _reference_paint(o, g)
            return
        if not fill and not line:
            return
        if isinstance(o, acm.GPolygon):
            p = o.get_polygon()
            g.set_color(o.get_fill_color() if fill else o.get_color())
            (g.fill_polygon if fill else g.draw_polygon)(p.xpoints, p.ypoints, p.npoints)
            return
        r = o.get_awt_bounds()
        g.set_color(o.get_fill_color() if fill else o.get_color())
        if isinstance(o, acm.GOval):
            (g.fill_oval if fill else g.draw_oval)(r.x, r.y, r.width, r.height)
        else:
            (g.fill_rect if fill else g.draw_rect)(r.x, r.y, r.width, r.height)

    def thick_fill_only_ref(o, g):
        if Thick.skipped(o.detail):
            return
        if o.is_filled() and Thick.visible(o.get_fill_color()):
            g.set_color(o.get_fill_color())
            if isinstance(o, acm.GPolygon):
                p = o.get_polygon()
                g.fill_polygon(p.xpoints, p.ypoints, p.npoints)
            elif isinstance(o, acm.GOval):
                g.fill_oval(o._x, o._y, o._w, o._h)
            else:
                g.fill_rect(o._x, o._y, o._w, o._h)

    rnd = random.Random(9)
    old_level = Thick.set_level(0)
    try:
        for level in (0, 1, 2):
            Thick.set_level(level)
            for i in range(30):
                k = i % 3
                for fam in ("flat", "thick"):
                    if k == 0:
                        o = (Flat.Poly() if fam == "flat" else Thick.Poly())
                        for _ in range(4):
                            o.add_vertex(rnd.uniform(0, 40), rnd.uniform(0, 40))
                    elif k == 1:
                        o = (Flat.Oval if fam == "flat" else Thick.Oval)(rnd.uniform(0, 50), rnd.uniform(0, 30), 20, 14)
                    else:
                        o = (Flat.Rect if fam == "flat" else Thick.Rect)(rnd.uniform(0, 50), rnd.uniform(0, 30), 22, 9)
                    o.set_filled(i % 4 != 1)
                    o.set_color(Color(200, 40, 90, (0, 255, 120)[i % 3]))
                    o.set_fill_color(Color(30, 90, 200, (255, 0, 200, 255)[i % 4]))
                    o.set_detail((0, 1, 2)[i % 3])
                    o.set_outline_detail((0, 0, 1, 2)[i % 4])
                    if fam == "thick":
                        o.set_line_width(0)   # the fill-only branch this patch rewrote
                        ref = thick_fill_only_ref
                    else:
                        ref = flat_ref
                    a, _, ca = _render(lambda g: o.paint(g))
                    b, _, cb = _render(lambda g: ref(o, g))
                    check(np.array_equal(a, b), "%s %s #%d at level %d paints the same" % (fam, type(o).__name__, i, level))
                    check(ca == cb, "%s %s #%d at level %d leaves the same colour" % (fam, type(o).__name__, i, level))
    finally:
        Thick.set_level(old_level)


def test_thick_outlined_shapes_paint_like_their_java_logic(check):
    """Thick.* paint with an outline inlines Thick.begin and the ACM paint; compare with the original sequence,
    including the Graphics state it leaves (colour, stroke restored, anti-aliasing hint on)."""
    from lindefense.ui.jawt import RenderingHints

    def ref(o, g):
        if Thick.skipped(o.detail):
            return
        if (not Thick.strokes(o.get_line_width(), o.get_color())) or Thick.skipped(o.outline_detail):
            if o.is_filled() and Thick.visible(o.get_fill_color()):
                Thick.aa(g)
                g.set_color(o.get_fill_color())
                if isinstance(o, acm.GPolygon):
                    if o.get_vertex_count():
                        p = o.get_polygon()
                        g.fill_polygon(p.xpoints, p.ypoints, p.npoints)
                elif isinstance(o, acm.GOval):
                    g.fill_oval(o._x, o._y, o._w, o._h)
                else:
                    g.fill_rect(o._x, o._y, o._w, o._h)
            return
        w = o.get_line_width()
        old = Thick.begin(g, Thick.stroke(1 if w < 0 else w))
        if not (isinstance(o, acm.GPolygon) and o.get_vertex_count() == 0):
            _reference_paint(o, g)
        g.set_stroke(old)

    rnd = random.Random(21)
    old_level = Thick.set_level(0)
    stroke0 = BasicStroke(1.5)
    try:
        for level in (0, 1, 2):
            Thick.set_level(level)
            for i in range(48):
                k = i % 3
                if k == 0:
                    o = Thick.Poly()
                    for _ in range(0 if i % 16 == 0 else 4):
                        o.add_vertex(rnd.uniform(0, 40), rnd.uniform(0, 40))
                elif k == 1:
                    o = Thick.Oval(rnd.uniform(0, 50), rnd.uniform(0, 30), 20, 14)
                else:
                    o = Thick.Rect(rnd.uniform(0, 50), rnd.uniform(0, 30), 22, 9)
                o.set_filled(i % 4 != 1)
                o.set_color(Color(200, 40, 90, (255, 0, 120)[i % 3]))
                o.set_fill_color(Color(30, 90, 200, (255, 0, 200, 255)[i % 4]))
                o.set_detail((0, 0, 1, 2)[i % 4])
                o.set_outline_detail((0, 0, 0, 1, 2)[i % 5])
                if i % 6 != 5:   # the rest keep the default (never set) width
                    o.set_line_width((2.2, 0.8, 3.4, 1.4, 0)[i % 5])

                def run(paint):
                    def p(g):
                        g.set_stroke(stroke0)
                        g.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, (RenderingHints.VALUE_ANTIALIAS_OFF if i % 2
                                                                               else RenderingHints.VALUE_ANTIALIAS_ON))
                        paint(g)
                        return g.stroke, g.get_rendering_hint(RenderingHints.KEY_ANTIALIASING)
                    return _render(p)
                a, (sa, ha), ca = run(lambda g: o.paint(g))
                b, (sb, hb), cb = run(lambda g: ref(o, g))
                name = "%s #%d at level %d" % (type(o).__name__, i, level)
                check(np.array_equal(a, b), name + " paints the same")
                check(ca == cb, name + " leaves the same colour")
                check(sa is sb, name + " restores the stroke")
                check(ha == hb, name + " leaves the same anti-aliasing hint")
    finally:
        Thick.set_level(old_level)


def test_colour_helpers_match_their_java_formulas(check):
    def mix_ref(a, b, t):
        t = _j.dmax(0, _j.dmin(1, t))
        return Color(_j.to_int(_j.jround(a.get_red() + (b.get_red() - a.get_red()) * t)),
                     _j.to_int(_j.jround(a.get_green() + (b.get_green() - a.get_green()) * t)),
                     _j.to_int(_j.jround(a.get_blue() + (b.get_blue() - a.get_blue()) * t)), a.get_alpha())

    def shade_ref(c, k):
        if k <= 1:
            return Color(TowerArt.clamp(c.get_red() * k), TowerArt.clamp(c.get_green() * k),
                         TowerArt.clamp(c.get_blue() * k), c.get_alpha())
        t = _j.dmin(1, k - 1)
        return Color(TowerArt.clamp(c.get_red() + (255 - c.get_red()) * t),
                     TowerArt.clamp(c.get_green() + (255 - c.get_green()) * t),
                     TowerArt.clamp(c.get_blue() + (255 - c.get_blue()) * t), c.get_alpha())

    rnd = random.Random(2)
    edge = [0, 1, 0.5, -0.0, -1, 2, float("nan"), float("inf"), float("-inf"), 0.49999999999999994, 1 / 3.0]
    bad = []
    for i in range(20000):
        a = Color(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        b = Color(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        t = edge[i % len(edge)] if i % 4 == 0 else rnd.uniform(-0.3, 1.3)
        if Art.mix(a, b, t)._argb != mix_ref(a, b, t)._argb:
            bad.append(("mix", a._argb, b._argb, t))
        al = rnd.randrange(-40, 300)
        expect = Color(a.get_red(), a.get_green(), a.get_blue(), max(0, min(255, al)))._argb
        if Art.alpha(a, al)._argb != expect or TowerArt.alpha(a, al)._argb != expect:
            bad.append(("alpha", a._argb, al))
        k = rnd.choice([0.75, 0.78, 0.5, 1.25, 1.6, 2.5, rnd.uniform(0, 2.2)])
        if TowerArt.shade(a, k)._argb != shade_ref(a, k)._argb:
            bad.append(("shade", a._argb, k))
    check(not bad, "colour helpers differ from the Java formulas: %r" % bad[:5])


def test_math_round_edge_cases(check):
    cases = {0.5: 1, -0.5: 0, 1.5: 2, -1.5: -1, 2.5: 3, -2.5: -2, 0.49999999999999994: 0, -0.49999999999999994: 0,
             254.5: 255, 1e300: (1 << 63) - 1, -1e300: -(1 << 63), float("inf"): (1 << 63) - 1,
             float("-inf"): -(1 << 63), 9.223372036854776e18: (1 << 63) - 1, 7: 7, -7: -7}
    for x, want in cases.items():
        check(_j.jround(x) == want, "Math.round(%r) = %r, got %r" % (x, want, _j.jround(x)))
    check(_j.jround(float("nan")) == 0, "Math.round(NaN) = 0")


def test_gcanvas_has_a_size_and_paints_its_background(check):
    c = acm.GCanvas()
    c.set_size(40, 30)
    c.set_background(Color(255, 0, 0))
    r = acm.GRect(5, 5, 10, 10)
    r.set_filled(True)
    r.set_fill_color(Color(0, 0, 255))
    c.add(r)
    check((c.get_width(), c.get_height()) == (40, 30), "GCanvas.set_size sets its size")
    surf = skia.Surface(40, 30)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    c.paint(Graphics2D(cv))
    img = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    check(tuple(int(v) for v in img[25, 35][:3]) == (255, 0, 0), "background pixel is red: %r" % (tuple(img[25, 35]),))
    check(tuple(int(v) for v in img[10, 10][:3]) == (0, 0, 255), "content pixel is blue: %r" % (tuple(img[10, 10]),))


def test_enemy_retint_sets_each_parts_own_effective_colour(check):
    """EnemySprite.retint computes each distinct base colour once per call; every part must still get exactly
    effective(its own base colour) for every damage / camo / slow / flash state."""
    from lindefense.sim.difficulty import Difficulty
    from lindefense.tools.perf_bench import PerfBench
    g = PerfBench.late_game(1, Difficulty.values()[2], 10, 40)
    rig = PerfBench.RenderRig(g, 400, 250)
    PerfBench.spawn_crowd(g, 60, 0)
    for _ in range(5):
        rig.screen.frame(1 / 60.0)
    rnd = random.Random(3)
    n = bad = 0
    for s in list(rig.screen.world.enemy_sprites.values()):
        for _ in range(6):
            s.dmg = rnd.choice([0.0, 0.03, 0.3, 0.71, 1.0])
            s.decloak = rnd.random()
            camo, rev, slow, flash = (rnd.random() < 0.5 for _ in range(4))
            s.last_tint_key = -1
            s.retint(camo, rev, slow, flash)
            dc = _j.to_int(_j.jround(_j.dmax(0, _j.dmin(1, s.decloak)) * 8)) if camo else 0
            base = (175 if rev else 110) if camo else 255
            alpha = base + _j.to_int(((255 - base) * dc) / 8.0)
            for i, part in enumerate(s.parts):
                full = s.tint_flags[i] == 1
                for src, got in ((s.base_fill[i], getattr(part, "_fill_color", None)), (s.base_line[i], part._color)):
                    if src is not None:
                        n += 1
                        bad += s.effective(src, full, alpha, slow, flash)._argb != got._argb
    check(n > 1000, "colours compared: %d" % n)
    check(bad == 0, "%d of %d part colours differ from effective(base colour)" % (bad, n))
