"""Lindefense HeroFigure (ported from src/lindefense/ui/sprites/towers/HeroFigure.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.jenum import JEnum
from lindefense.ui.sprites.towers.art import Art


class HeroFigure:
    """The chibi hero figure every Hero Store hero is drawn from: a big round head with large glossy eyes, blush and a
small mouth on a short body with puffed sleeves, little legs and sneakers, wrapped in a glowing sticker outline.

It is one custom ACM GObject painted with Java2D rather than a compound of outlined polygons: at sprite
size (head radius ~11 px) the engine's shared 2.2 px ink outline would swallow the eyes, hair and glasses, so the
figure uses one bold silhouette outline and hairline inner lines instead. A Look carries the likeness
(skin, hair colour and style, iris, expression, outfit colours) and two Extra hooks let each hero paint
its own clothing print and headgear at the right depth."""
    class Hair(JEnum):
        """Hairstyles across the roster."""
        CURLY_BIG = ()
        CURLY_TOP = ()
        CURLY_LOOSE = ()
        STRAIGHT_FRINGE = ()
        SPIKY = ()
        LONG = ()
        UNDER_HAT = ()
        BALD = ()
    class Mouth(JEnum):
        """Mouth shapes."""
        NEUTRAL = ()
        SMILE = ()
        GRIN = ()
    class Extra:
        """Paints extra details; coordinates are world px centred on the tower."""
        def paint(self, g, r, h):
            raise NotImplementedError
    class Look:
        """Everything that makes one hero's figure look like their reference portrait."""
        def __init__(self):
            self.f_skin = None
            self.f_hair = None
            self.f_shirt = None
            self.f_on_shirt = None
            self.f_on_head = None
            self.f_pants = Color(0x2e3344)
            self.f_shoes = Color(0xe9e6f5)
            self.f_iris = Color(0x3a2418)
            self.f_glow = Color(0x5fe8ff)
            self.style = HeroFigure.Hair.STRAIGHT_FRINGE
            self.f_mouth = HeroFigure.Mouth.SMILE
            pass
        def skin(self, v):
            self.f_skin = Color(v)
            return self
        def hair(self, v, s):
            self.f_hair = Color(v)
            self.style = s
            return self
        def shirt(self, v):
            self.f_shirt = Color(v)
            return self
        def pants(self, v):
            self.f_pants = Color(v)
            return self
        def shoes(self, v):
            self.f_shoes = Color(v)
            return self
        def iris(self, v):
            self.f_iris = Color(v)
            return self
        def glow(self, c):
            self.f_glow = c
            return self
        def mouth(self, m):
            self.f_mouth = m
            return self
        def on_shirt(self, e):
            """Print / details on the shirt (painted after the torso, before the head)."""
            self.f_on_shirt = e
            return self
        def on_head(self, e):
            """Accessories over the face and hair (glasses, hats, goggles)."""
            self.f_on_head = e
            return self
    class Head:
        """Head geometry, so accessories line up with the face."""
        def __init__(self, cy, rad):
            self.cy = 0.0
            self.rad = 0.0
            self.cy = cy
            self.rad = rad
        def eye_x(self):
            """Eye centre x offset (use +/-)."""
            return self.rad * 0.37
        def eye_y(self):
            """Eye centre y."""
            return self.cy + (self.rad * 0.17)
    class Figure(GObject):
        def __init__(self, r, l):
            self.r = 0.0
            self.l = None
            self.head = None
            self.torso = None
            self.face = None
            self.f_hair_back = None
            self.f_hair_front = None
            self.silhouette = None
            GObject.__init__(self)
            self.legs = ([None] * 2)
            self.shoes = ([None] * 2)
            self.sleeves = ([None] * 2)
            self.hands = ([None] * 2)
            self.ears = ([None] * 2)
            self.r = r
            self.l = l
            self.head = HeroFigure.Head(((-r) * 0.33), (r * 0.56))
            R = self.head.rad
            hy = self.head.cy
            for i in range(2):
                s = ((-1) if (i == 0) else 1)
                self.legs[i] = RoundRectangle2D.Double((((s * r) * 0.15) - (r * 0.09)), (r * 0.6), (r * 0.18), (r * 0.32), (r * 0.08), (r * 0.08))
                self.shoes[i] = Ellipse2D.Double((((s * r) * 0.18) - (r * 0.15)), (r * 0.86), (r * 0.3), (r * 0.16))
                self.sleeves[i] = Ellipse2D.Double((((s * r) * 0.39) - (r * 0.14)), (r * 0.14), (r * 0.28), (r * 0.38))
                self.hands[i] = Ellipse2D.Double((((s * r) * 0.45) - (r * 0.09)), (r * 0.5), (r * 0.18), (r * 0.18))
                self.ears[i] = Ellipse2D.Double((((s * R) * 0.97) - (R * 0.15)), hy, (R * 0.3), (R * 0.3))
            t = Path2D.Double()
            t.move_to(((-r) * 0.24), (r * 0.1))
            t.line_to((r * 0.24), (r * 0.1))
            t.quad_to((r * 0.34), (r * 0.13), (r * 0.35), (r * 0.25))
            t.line_to((r * 0.37), (r * 0.68))
            t.quad_to((r * 0.37), (r * 0.77), (r * 0.28), (r * 0.77))
            t.line_to(((-r) * 0.28), (r * 0.77))
            t.quad_to(((-r) * 0.37), (r * 0.77), ((-r) * 0.37), (r * 0.68))
            t.line_to(((-r) * 0.35), (r * 0.25))
            t.quad_to(((-r) * 0.34), (r * 0.13), ((-r) * 0.24), (r * 0.1))
            t.close_path()
            self.torso = t
            self.face = Ellipse2D.Double((-R), (hy - (R * 0.95)), (2 * R), (1.9 * R))
            self.f_hair_back = self.hair_back(R, hy)
            self.f_hair_front = self.hair_front(R, hy)
            sil = Area(self.torso)
            for i in range(2):
                sil.add(Area(self.legs[i]))
                sil.add(Area(self.shoes[i]))
                sil.add(Area(self.sleeves[i]))
                sil.add(Area(self.hands[i]))
                sil.add(Area(self.ears[i]))
            sil.add(Area(self.face))
            sil.add(self.f_hair_back)
            sil.add(self.f_hair_front)
            self.silhouette = sil
        def get_bounds(self):
            return GRectangle((self.get_x() - (self.r * 1.5)), (self.get_y() - (self.r * 1.6)), (self.r * 3), (self.r * 3))
        def paint(self, g0):
            g = g0.create()
            try:
                g.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
                g.set_rendering_hint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE)
                g.translate(self.get_x(), self.get_y())
                self.paint_figure(g)
            finally:
                g.dispose()
        def paint_figure(self, g):
            R = self.head.rad
            hy = self.head.cy
            for k in range(3, 0, -1):
                g.set_stroke(HeroFigure.round((self.r * (0.1 + (0.11 * k)))))
                g.set_color(Art.alpha(self.l.f_glow, (34 + ((3 - k) * 26))))
                g.draw(self.silhouette)
            g.set_stroke(HeroFigure.round((self.r * 0.15)))
            g.set_color(HeroFigure.INK)
            g.draw(self.silhouette)
            g.fill(self.silhouette)
            pants_hi = Art.shade(self.l.f_pants, 1.15)
            for i in range(2):
                HeroFigure.fill(g, self.legs[i], self.l.f_pants)
                HeroFigure.fill(g, Rectangle2D.Double((self.legs[i].get_bounds2_d().get_x() + (self.r * 0.03)), (self.r * 0.62), (self.r * 0.04), (self.r * 0.22)), pants_hi)
            for i in range(2):
                HeroFigure.fill(g, self.shoes[i], self.l.f_shoes)
                HeroFigure.fill(g, Rectangle2D.Double((self.shoes[i].get_bounds2_d().get_x() + (self.r * 0.03)), (self.r * 0.97), (self.r * 0.24), (self.r * 0.03)), Art.shade(self.l.f_shoes, 0.78))
                HeroFigure.line(g, self.shoes[i], (self.r * 0.03))
            for i in range(2):
                HeroFigure.fill(g, self.hands[i], self.l.f_skin)
                HeroFigure.line(g, self.hands[i], (self.r * 0.03))
            sleeve = Art.shade(self.l.f_shirt, 0.93)
            for i in range(2):
                HeroFigure.fill(g, self.sleeves[i], sleeve)
                HeroFigure.line(g, self.sleeves[i], (self.r * 0.03))
            HeroFigure.fill(g, self.torso, self.l.f_shirt)
            old_clip = g.get_clip()
            g.clip(self.torso)
            HeroFigure.fill(g, Rectangle2D.Double((self.r * 0.16), 0, (self.r * 0.3), self.r), Art.alpha(Color.BLACK, 30))
            g.set_clip(old_clip)
            HeroFigure.line(g, self.torso, (self.r * 0.03))
            HeroFigure.fill(g, Ellipse2D.Double(((-self.r) * 0.1), (self.r * 0.04), (self.r * 0.2), (self.r * 0.14)), Art.shade(self.l.f_skin, 0.82))
            if self.l.f_on_shirt is not None:
                self.l.f_on_shirt.paint(g, self.r, self.head)
            HeroFigure.fill(g, self.f_hair_back, Art.shade(self.l.f_hair, 0.82))
            for i in range(2):
                HeroFigure.fill(g, self.ears[i], self.l.f_skin)
                HeroFigure.fill(g, HeroFigure.inset_ellipse(self.ears[i], 0.45), Art.shade(self.l.f_skin, 0.85))
            HeroFigure.fill(g, self.face, self.l.f_skin)
            g.set_paint(RadialGradientPaint(Point2D.Double(((-R) * 0.35), (hy - (R * 0.3))), (R * 1.2), [0.0, 1.0], [Art.alpha(Color.WHITE, 40), Art.alpha(Color.WHITE, 0)]))
            g.fill(self.face)
            HeroFigure.line(g, self.face, (self.r * 0.03))
            self.paint_face(g, R, hy)
            self.paint_hair(g, self.f_hair_front, R, hy)
            if self.l.f_on_head is not None:
                self.l.f_on_head.paint(g, self.r, self.head)
        def paint_face(self, g, R, hy):
            ey = self.head.eye_y()
            rx = (R * 0.2)
            ry = (R * 0.26)
            for s in range((-1), 2, 2):
                ex = (s * self.head.eye_x())
                g.set_paint(RadialGradientPaint(Point2D.Double(((s * R) * 0.62), (hy + (R * 0.47))), (R * 0.2), [0.0, 1.0], [Art.alpha(HeroFigure.BLUSH, 150), Art.alpha(HeroFigure.BLUSH, 0)]))
                g.fill(Ellipse2D.Double((((s * R) * 0.62) - (R * 0.2)), (hy + (R * 0.27)), (R * 0.4), (R * 0.4)))
                eye = Ellipse2D.Double((ex - rx), (ey - ry), (2 * rx), (2 * ry))
                HeroFigure.fill(g, eye, Art.shade(self.l.f_iris, 0.55))
                clip = g.get_clip()
                g.clip(eye)
                g.set_paint(RadialGradientPaint(Point2D.Double(ex, (ey + (ry * 0.7))), (ry * 1.1), [0.0, 1.0], [Art.shade(self.l.f_iris, 1.6), Art.alpha(Art.shade(self.l.f_iris, 1.1), 0)]))
                g.fill(eye)
                g.set_clip(clip)
                HeroFigure.fill(g, Ellipse2D.Double((ex - (rx * 0.62)), (ey - (ry * 0.72)), (rx * 0.85), (ry * 0.62)), Color.WHITE)
                HeroFigure.fill(g, Ellipse2D.Double((ex + (rx * 0.2)), (ey + (ry * 0.25)), (rx * 0.4), (ry * 0.3)), Art.alpha(Color.WHITE, 220))
                g.set_color(HeroFigure.INK)
                g.set_stroke(HeroFigure.round((R * 0.08)))
                g.draw(Arc2D.Double((ex - (rx * 1.1)), (ey - (ry * 1.02)), (rx * 2.2), (ry * 2.1), 25, 130, Arc2D.OPEN))
                g.draw(Line2D.Double((ex + ((s * rx) * 0.95)), (ey - (ry * 0.55)), (ex + ((s * rx) * 1.35)), (ey - (ry * 0.8))))
                g.set_color(Art.shade(self.l.f_hair, 0.75))
                g.set_stroke(HeroFigure.round((R * 0.06)))
                g.draw(Line2D.Double((ex - (rx * 0.8)), (ey - (ry * 1.5)), (ex + (rx * 0.8)), (ey - (ry * 1.58))))
            HeroFigure.fill(g, Ellipse2D.Double(((-R) * 0.035), (hy + (R * 0.42)), (R * 0.07), (R * 0.05)), Art.shade(self.l.f_skin, 0.75))
            my = (hy + (R * 0.6))
            g.set_stroke(HeroFigure.round((R * 0.05)))
            _sw1 = self.l.f_mouth
            if _sw1 is HeroFigure.Mouth.NEUTRAL:
                g.set_color(Color(0x6b2e2e))
                g.draw(Line2D.Double(((-R) * 0.09), my, (R * 0.09), my))
            elif _sw1 is HeroFigure.Mouth.GRIN:
                m = Arc2D.Double(((-R) * 0.2), (my - (R * 0.18)), (R * 0.4), (R * 0.36), 180, 180, Arc2D.CHORD)
                HeroFigure.fill(g, m, Color(0x7a1f2c))
                clip = g.get_clip()
                g.clip(m)
                HeroFigure.fill(g, Rectangle2D.Double(((-R) * 0.2), (my - (R * 0.02)), (R * 0.4), (R * 0.07)), Color.WHITE)
                HeroFigure.fill(g, Ellipse2D.Double(((-R) * 0.1), (my + (R * 0.08)), (R * 0.2), (R * 0.14)), Color(0xff8295))
                g.set_clip(clip)
                g.set_color(HeroFigure.INK)
                g.set_stroke(HeroFigure.round((R * 0.035)))
                g.draw(m)
                pass  # break
            elif _sw1 is HeroFigure.Mouth.SMILE:
                m = Arc2D.Double(((-R) * 0.12), (my - (R * 0.1)), (R * 0.24), (R * 0.2), 180, 180, Arc2D.CHORD)
                HeroFigure.fill(g, m, Color(0x7a1f2c))
                g.set_color(HeroFigure.INK)
                g.set_stroke(HeroFigure.round((R * 0.03)))
                g.draw(m)
                pass  # break
        def paint_hair(self, g, front, R, hy):
            if self.l.style is HeroFigure.Hair.BALD:
                HeroFigure.fill(g, front, self.l.f_hair)
                HeroFigure.fill(g, Ellipse2D.Double(((-R) * 0.55), (hy - (R * 0.98)), (R * 0.7), (R * 0.36)), Art.alpha(Color.WHITE, 70))
                HeroFigure.fill(g, Ellipse2D.Double(((-R) * 0.36), (hy - (R * 0.9)), (R * 0.22), (R * 0.12)), Art.alpha(Color.WHITE, 150))
                return
            if self.l.style is HeroFigure.Hair.CURLY_TOP:
                for s in range((-1), 2, 2):
                    fade = Path2D.Double()
                    fade.move_to(((s * R) * 0.99), (hy + (R * 0.1)))
                    fade.line_to(((s * R) * 0.97), (hy - (R * 0.4)))
                    fade.line_to(((s * R) * 0.62), (hy - (R * 0.6)))
                    fade.line_to(((s * R) * 0.7), (hy - (R * 0.25)))
                    fade.line_to(((s * R) * 0.86), (hy + (R * 0.08)))
                    fade.close_path()
                    HeroFigure.fill(g, fade, Art.alpha(self.l.f_hair, 120))
            HeroFigure.fill(g, front, self.l.f_hair)
            if self.l.style is HeroFigure.Hair.UNDER_HAT:
                return
            g.set_color(Art.alpha(Art.shade(self.l.f_hair, 1.45), 170))
            clip = g.get_clip()
            g.clip(front)
            if (self.l.style is HeroFigure.Hair.STRAIGHT_FRINGE) or (self.l.style is HeroFigure.Hair.LONG):
                g.set_stroke(HeroFigure.round((R * 0.09)))
                g.draw(Arc2D.Double(((-R) * 0.75), (hy - (R * 0.98)), (R * 1.3), (R * 0.9), 110, 55, Arc2D.OPEN))
                g.set_stroke(HeroFigure.round((R * 0.035)))
                g.set_color(Art.alpha(Art.shade(self.l.f_hair, 1.6), 110))
                for i in range((-2), 3):
                    g.draw(Line2D.Double(((i * R) * 0.22), (hy - (R * 0.9)), ((i * R) * 0.3), (hy - (R * 0.25))))
            elif self.l.style is HeroFigure.Hair.SPIKY:
                g.set_stroke(HeroFigure.round((R * 0.05)))
                for i in range((-2), 3):
                    g.draw(Line2D.Double(((i * R) * 0.26), (hy - (R * 0.5)), ((i * R) * 0.34), (hy - (R * 1.0))))
            else:
                g.set_stroke(HeroFigure.round((R * 0.05)))
                for c in self.curl_centres(R, hy):
                    g.draw(Arc2D.Double((c[0] - (c[2] * 0.65)), (c[1] - (c[2] * 0.65)), (c[2] * 1.3), (c[2] * 1.3), 70, 120, Arc2D.OPEN))
            g.set_clip(clip)
            g.set_color(Art.shade(self.l.f_hair, 0.45))
            g.set_stroke(HeroFigure.round((R * 0.035)))
            g.draw(front)
        def curl_centres(self, R, hy):
            _sw2 = self.l.style
            if _sw2 is HeroFigure.Hair.CURLY_BIG:
                return [[((-R) * 0.72), (hy - (R * 0.45)), (R * 0.3)], [(R * 0.72), (hy - (R * 0.45)), (R * 0.3)], [((-R) * 0.38), (hy - (R * 0.62)), (R * 0.32)], [(R * 0.38), (hy - (R * 0.62)), (R * 0.32)], [0, (hy - (R * 0.7)), (R * 0.32)], [((-R) * 0.2), (hy - (R * 0.36)), (R * 0.21)], [(R * 0.24), (hy - (R * 0.38)), (R * 0.2)], [((-R) * 0.55), (hy - (R * 0.3)), (R * 0.18)], [((-R) * 0.55), (hy - (R * 0.95)), (R * 0.34)], [(R * 0.55), (hy - (R * 0.95)), (R * 0.34)], [0, (hy - (R * 1.08)), (R * 0.36)], [((-R) * 0.92), (hy - (R * 0.7)), (R * 0.3)], [(R * 0.92), (hy - (R * 0.7)), (R * 0.3)]]
            elif _sw2 is HeroFigure.Hair.CURLY_LOOSE:
                return [[((-R) * 0.76), (hy - (R * 0.42)), (R * 0.27)], [(R * 0.76), (hy - (R * 0.42)), (R * 0.27)], [((-R) * 0.42), (hy - (R * 0.62)), (R * 0.3)], [(R * 0.42), (hy - (R * 0.62)), (R * 0.3)], [0, (hy - (R * 0.7)), (R * 0.31)], [((-R) * 0.12), (hy - (R * 0.4)), (R * 0.21)], [(R * 0.32), (hy - (R * 0.37)), (R * 0.18)], [((-R) * 0.55), (hy - (R * 0.92)), (R * 0.32)], [(R * 0.55), (hy - (R * 0.92)), (R * 0.32)], [0, (hy - (R * 1.04)), (R * 0.33)], [((-R) * 0.95), (hy - (R * 0.62)), (R * 0.27)], [(R * 0.95), (hy - (R * 0.62)), (R * 0.27)]]
            elif _sw2 is HeroFigure.Hair.CURLY_TOP:
                return [[((-R) * 0.48), (hy - (R * 0.6)), (R * 0.29)], [(R * 0.48), (hy - (R * 0.6)), (R * 0.29)], [0, (hy - (R * 0.7)), (R * 0.33)], [((-R) * 0.18), (hy - (R * 0.42)), (R * 0.2)], [(R * 0.2), (hy - (R * 0.44)), (R * 0.18)], [((-R) * 0.3), (hy - (R * 1.02)), (R * 0.36)], [(R * 0.3), (hy - (R * 1.02)), (R * 0.36)], [((-R) * 0.66), (hy - (R * 0.82)), (R * 0.3)], [(R * 0.66), (hy - (R * 0.82)), (R * 0.3)]]
            else:
                return [None] * 0
        def hair_back(self, R, hy):
            _sw3 = self.l.style
            if _sw3 is HeroFigure.Hair.CURLY_BIG:
                return HeroFigure.circles([[((-R) * 0.98), (hy - (R * 0.08)), (R * 0.3)], [(R * 0.98), (hy - (R * 0.08)), (R * 0.3)], [((-R) * 0.88), (hy - (R * 0.55)), (R * 0.38)], [(R * 0.88), (hy - (R * 0.55)), (R * 0.38)], [((-R) * 0.45), (hy - (R * 0.92)), (R * 0.42)], [(R * 0.45), (hy - (R * 0.92)), (R * 0.42)], [0, (hy - (R * 1.0)), (R * 0.44)]])
            elif _sw3 is HeroFigure.Hair.CURLY_LOOSE:
                return HeroFigure.circles([[((-R) * 1.0), (hy - (R * 0.02)), (R * 0.27)], [(R * 1.0), (hy - (R * 0.02)), (R * 0.27)], [((-R) * 0.9), (hy - (R * 0.5)), (R * 0.34)], [(R * 0.9), (hy - (R * 0.5)), (R * 0.34)], [((-R) * 0.5), (hy - (R * 0.88)), (R * 0.38)], [(R * 0.5), (hy - (R * 0.88)), (R * 0.38)], [0, (hy - (R * 0.98)), (R * 0.4)]])
            elif _sw3 is HeroFigure.Hair.CURLY_TOP:
                return HeroFigure.circles([[((-R) * 0.62), (hy - (R * 0.8)), (R * 0.36)], [(R * 0.62), (hy - (R * 0.8)), (R * 0.36)], [((-R) * 0.22), (hy - (R * 1.02)), (R * 0.38)], [(R * 0.22), (hy - (R * 1.02)), (R * 0.38)]])
            elif _sw3 is HeroFigure.Hair.LONG:
                a = Area(Ellipse2D.Double(((-R) * 1.12), (hy - (R * 1.1)), (R * 2.24), (R * 1.9)))
                a.add(Area(RoundRectangle2D.Double(((-R) * 1.12), (hy - (R * 0.2)), (R * 0.5), (R * 1.7), (R * 0.4), (R * 0.4))))
                a.add(Area(RoundRectangle2D.Double((R * 0.62), (hy - (R * 0.2)), (R * 0.5), (R * 1.7), (R * 0.4), (R * 0.4))))
                return a
            elif _sw3 is HeroFigure.Hair.SPIKY:
                a = Area(Ellipse2D.Double(((-R) * 1.06), (hy - (R * 1.0)), (R * 2.12), (R * 1.8)))
                sp = Path2D.Double()
                for i in range((-3), 4):
                    x = ((i * R) * 0.3)
                    sp.move_to((x - (R * 0.2)), (hy - (R * 0.6)))
                    sp.line_to((x + (((-R) * 0.14) if (i < 0) else (R * 0.14))), (hy - (R * 1.45)))
                    sp.line_to((x + (R * 0.2)), (hy - (R * 0.6)))
                    sp.close_path()
                a.add(Area(sp))
                return a
            elif _sw3 is HeroFigure.Hair.STRAIGHT_FRINGE:
                return Area(Ellipse2D.Double(((-R) * 1.08), (hy - (R * 1.1)), (R * 2.16), (R * 1.9)))
            elif _sw3 is HeroFigure.Hair.BALD:
                return Area()
            elif _sw3 is HeroFigure.Hair.UNDER_HAT:
                return Area(Ellipse2D.Double(((-R) * 1.03), (hy - (R * 0.9)), (R * 2.06), (R * 1.6)))
        def hair_front(self, R, hy):
            _sw4 = self.l.style
            if _sw4 is HeroFigure.Hair.CURLY_BIG or _sw4 is HeroFigure.Hair.CURLY_LOOSE or _sw4 is HeroFigure.Hair.CURLY_TOP:
                return HeroFigure.circles(self.curl_centres(R, hy))
            elif _sw4 is HeroFigure.Hair.SPIKY:
                p = Path2D.Double()
                p.move_to(((-R) * 1.0), (hy + (R * 0.1)))
                p.line_to(((-R) * 0.95), (hy - (R * 0.5)))
                for i in range((-3), 4):
                    x = ((i * R) * 0.3)
                    p.line_to((x - (R * 0.12)), (hy - (R * 0.62)))
                    p.line_to((x + (((-R) * 0.1) if (i < 0) else (R * 0.1))), (hy - (R * 1.35)))
                    p.line_to((x + (R * 0.15)), (hy - (R * 0.55)))
                p.line_to((R * 0.95), (hy - (R * 0.5)))
                p.line_to((R * 1.0), (hy + (R * 0.1)))
                p.close_path()
                return Area(p)
            elif _sw4 is HeroFigure.Hair.STRAIGHT_FRINGE or _sw4 is HeroFigure.Hair.LONG:
                p = Path2D.Double()
                n = 16
                for i in range(n + 1):
                    t = math.radians((182 + ((176.0 * i) / n)))
                    x = ((math.cos(t) * R) * 1.07)
                    y = ((hy - (R * 0.06)) + ((math.sin(t) * R) * 1.03))
                    if i == 0:
                        p.move_to(x, y)
                    else:
                        p.line_to(x, y)
                fringe = [(R * 0.99), (hy + (R * 0.12)), (R * 0.66), (hy - (R * 0.3)), (R * 0.45), (hy - (R * 0.12)), (R * 0.24), (hy - (R * 0.32)), (0.02 * R), (hy - (R * 0.1)), ((-R) * 0.24), (hy - (R * 0.3)), ((-R) * 0.46), (hy - (R * 0.1)), ((-R) * 0.68), (hy - (R * 0.3)), ((-R) * 0.99), (hy + (R * 0.12))]
                for i in range(0, len(fringe), 2):
                    p.line_to(fringe[i], fringe[(i + 1)])
                p.close_path()
                return Area(p)
            elif _sw4 is HeroFigure.Hair.BALD:
                a = Area()
                for s in range((-1), 2, 2):
                    p = Path2D.Double()
                    p.move_to(((s * R) * 1.0), (hy + (R * 0.06)))
                    p.line_to(((s * R) * 0.98), (hy - (R * 0.3)))
                    p.line_to(((s * R) * 0.84), (hy - (R * 0.34)))
                    p.line_to(((s * R) * 0.9), (hy + (R * 0.02)))
                    p.close_path()
                    a.add(Area(p))
                return a
            elif _sw4 is HeroFigure.Hair.UNDER_HAT:
                a = Area()
                for s in range((-1), 2, 2):
                    p = Path2D.Double()
                    p.move_to(((s * R) * 1.01), (hy + (R * 0.12)))
                    p.line_to(((s * R) * 0.99), (hy - (R * 0.5)))
                    p.line_to(((s * R) * 0.7), (hy - (R * 0.56)))
                    p.line_to(((s * R) * 0.84), (hy + (R * 0.04)))
                    p.close_path()
                    a.add(Area(p))
                return a
    def __init__(self):
        pass
    @staticmethod
    def draw(a, r, l):
        """Adds the figure to a hero's art and returns its head geometry."""
        f = HeroFigure.Figure(r, l)
        a.add(f)
        return f.head
    @staticmethod
    def round(w):
        """Round-cap stroke of the given width (hero gear uses it too)."""
        return BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
    @staticmethod
    def fill(g, s, c):
        """Fills a shape in a flat colour."""
        g.set_color(c)
        g.fill(s)
    @staticmethod
    def line(g, s, w):
        """Outlines a shape in the sprite ink colour."""
        g.set_color(HeroFigure.INK)
        g.set_stroke(HeroFigure.round(w))
        g.draw(s)
    @staticmethod
    def circles(c):
        a = Area()
        for k in c:
            a.add(Area(Ellipse2D.Double((k[0] - k[2]), (k[1] - k[2]), (2 * k[2]), (2 * k[2]))))
        return a
    @staticmethod
    def inset_ellipse(s, k):
        b = s.get_bounds2_d()
        w = (b.get_width() * k)
        h = (b.get_height() * k)
        return Ellipse2D.Double((b.get_center_x() - (w / 2)), (b.get_center_y() - (h / 2)), w, h)


HeroFigure.INK = Art.INK
HeroFigure.BLUSH = Color(0xff6f92)
HeroFigure.Figure.serial_version_uid = 1

from lindefense.ui import acm as _acm  # noqa: E402
_acm.pure_paint(HeroFigure.Figure, heavy=True)
