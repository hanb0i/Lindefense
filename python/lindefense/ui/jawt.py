"""Java AWT / Java2D emulation on Skia: colours, fonts, strokes, shapes, paints, images and Graphics2D.

The UI layer was written against Java2D; this module reproduces the subset it uses with the same semantics (y-down
user space, Java angle conventions for arcs, SrcOver alpha composites, device-space clips) so the transpiled UI code
renders the same pictures. Everything draws through Skia, so it is anti-aliased at any resolution.
"""
import math
import os

import skia

# ====================================================================== colours
class Color:
    __slots__ = ("_argb",)

    def __init__(self, *a):
        n = len(a)
        if n == 1:
            v = a[0]
            self._argb = 0xFF000000 | (int(v) & 0xFFFFFF)
        elif n == 2:   # (rgba, hasAlpha)
            v = int(a[0]) & 0xFFFFFFFF
            self._argb = v if a[1] else (0xFF000000 | (v & 0xFFFFFF))
        elif n in (3, 4):
            t0 = type(a[0])
            if t0 is int and type(a[1]) is int and type(a[2]) is int and (n == 3 or type(a[3]) is int):
                r, g, b = a[0], a[1], a[2]
                al = a[3] if n == 4 else 255
                if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255 and 0 <= al <= 255):
                    raise ValueError("Color parameter outside of expected range: %r" % (a,))
                self._argb = (al << 24) | (r << 16) | (g << 8) | b
                return
            if any(isinstance(x, float) for x in a):
                vals = [int(max(0.0, min(1.0, float(x))) * 255 + 0.5) for x in a]
            else:
                vals = [int(x) for x in a]
                for x in vals:
                    if x < 0 or x > 255:
                        raise ValueError("Color parameter outside of expected range: %r" % (a,))
            r, g, b = vals[0], vals[1], vals[2]
            al = vals[3] if n == 4 else 255
            self._argb = (al << 24) | (r << 16) | (g << 8) | b
        else:
            raise TypeError("Color%r" % (a,))

    @staticmethod
    def _of(argb):
        c = Color.__new__(Color)
        c._argb = argb & 0xFFFFFFFF
        return c

    def get_red(self):
        return (self._argb >> 16) & 255

    def get_green(self):
        return (self._argb >> 8) & 255

    def get_blue(self):
        return self._argb & 255

    def get_alpha(self):
        return (self._argb >> 24) & 255

    def get_rgb(self):
        v = self._argb
        return v - (1 << 32) if v & 0x80000000 else v

    def skia(self):
        return self._argb

    def brighter(self):
        r, g, b, a = self.get_red(), self.get_green(), self.get_blue(), self.get_alpha()
        i = int(1.0 / (1.0 - 0.7))
        if r == 0 and g == 0 and b == 0:
            return Color(i, i, i, a)
        if 0 < r < i:
            r = i
        if 0 < g < i:
            g = i
        if 0 < b < i:
            b = i
        return Color(min(int(r / 0.7), 255), min(int(g / 0.7), 255), min(int(b / 0.7), 255), a)

    def darker(self):
        return Color(max(int(self.get_red() * 0.7), 0), max(int(self.get_green() * 0.7), 0), max(int(self.get_blue() * 0.7), 0), self.get_alpha())

    def get_rgb_color_components(self, arr=None):
        return [self.get_red() / 255.0, self.get_green() / 255.0, self.get_blue() / 255.0]

    def get_rgb_components(self, arr=None):
        return [self.get_red() / 255.0, self.get_green() / 255.0, self.get_blue() / 255.0, self.get_alpha() / 255.0]

    @staticmethod
    def get_hsb_color(h, s, b):
        return Color._of(0xFF000000 | (Color.hsb_to_rgb(h, s, b) & 0xFFFFFF))

    @staticmethod
    def hsb_to_rgb(hue, saturation, brightness):
        r = g = b = 0
        if saturation == 0:
            r = g = b = int(brightness * 255.0 + 0.5)
        else:
            h = (hue - math.floor(hue)) * 6.0
            f = h - math.floor(h)
            p = brightness * (1.0 - saturation)
            q = brightness * (1.0 - saturation * f)
            t = brightness * (1.0 - (saturation * (1.0 - f)))
            hi = int(h)
            if hi == 0:
                r, g, b = brightness, t, p
            elif hi == 1:
                r, g, b = q, brightness, p
            elif hi == 2:
                r, g, b = p, brightness, t
            elif hi == 3:
                r, g, b = p, q, brightness
            elif hi == 4:
                r, g, b = t, p, brightness
            else:
                r, g, b = brightness, p, q
            r, g, b = int(r * 255.0 + 0.5), int(g * 255.0 + 0.5), int(b * 255.0 + 0.5)
        return 0xFF000000 | (r << 16) | (g << 8) | b

    @staticmethod
    def rgb_to_hsb(r, g, b, arr=None):
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        brightness = cmax / 255.0
        saturation = (cmax - cmin) / float(cmax) if cmax != 0 else 0.0
        if saturation == 0:
            hue = 0.0
        else:
            redc = (cmax - r) / float(cmax - cmin)
            greenc = (cmax - g) / float(cmax - cmin)
            bluec = (cmax - b) / float(cmax - cmin)
            if r == cmax:
                hue = bluec - greenc
            elif g == cmax:
                hue = 2.0 + redc - bluec
            else:
                hue = 4.0 + greenc - redc
            hue = hue / 6.0
            if hue < 0:
                hue = hue + 1.0
        return [hue, saturation, brightness]

    def __eq__(self, o):
        return isinstance(o, Color) and o._argb == self._argb

    def __ne__(self, o):
        return not self.__eq__(o)

    def __hash__(self):
        return self._argb

    def equals(self, o):
        return self.__eq__(o)

    def hash_code(self):
        return self.get_rgb()

    def __repr__(self):
        return "java.awt.Color[r=%d,g=%d,b=%d]" % (self.get_red(), self.get_green(), self.get_blue())


for _n, _v in (("WHITE", 0xFFFFFF), ("BLACK", 0x000000), ("RED", 0xFF0000), ("GREEN", 0x00FF00), ("BLUE", 0x0000FF),
               ("YELLOW", 0xFFFF00), ("CYAN", 0x00FFFF), ("MAGENTA", 0xFF00FF), ("ORANGE", 0xFFC800), ("PINK", 0xFFAFAF),
               ("GRAY", 0x808080), ("LIGHT_GRAY", 0xC0C0C0), ("DARK_GRAY", 0x404040)):
    setattr(Color, _n, Color(_v))
    setattr(Color, _n.lower(), Color(_v))
Color.lightGray = Color.LIGHT_GRAY
Color.darkGray = Color.DARK_GRAY
Color.light_gray = Color.LIGHT_GRAY
Color.dark_gray = Color.DARK_GRAY


# ====================================================================== geometry
class Point2D:
    pass


class Point2DDouble(Point2D):
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = float(x), float(y)

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def set_location(self, x, y=None):
        if y is None:
            x, y = x.get_x(), x.get_y()
        self.x, self.y = float(x), float(y)

    def distance(self, x, y=None):
        if y is None:
            x, y = x.get_x(), x.get_y()
        return math.hypot(self.x - x, self.y - y)


Point2D.Double = Point2DDouble
Point2D.Float = Point2DDouble


class Dimension:
    def __init__(self, w=0, h=0):
        if isinstance(w, Dimension):
            w, h = w.width, w.height
        self.width, self.height = int(w), int(h)

    def get_width(self):
        return float(self.width)

    def get_height(self):
        return float(self.height)

    def get_size(self):
        return Dimension(self.width, self.height)

    def __eq__(self, o):
        return isinstance(o, Dimension) and (o.width, o.height) == (self.width, self.height)

    def __repr__(self):
        return "java.awt.Dimension[width=%d,height=%d]" % (self.width, self.height)


class Point:
    def __init__(self, x=0, y=0):
        self.x, self.y = int(x), int(y)

    def get_x(self):
        return float(self.x)

    def get_y(self):
        return float(self.y)


class Insets:
    def __init__(self, top, left, bottom, right):
        self.top, self.left, self.bottom, self.right = top, left, bottom, right


class Shape:
    """Base of every Java2D shape: subclasses build a Skia path in user space."""

    def path(self):
        raise NotImplementedError

    def get_bounds2_d(self):
        r = self.path().computeTightBounds()
        return Rectangle2DDouble(r.left(), r.top(), r.width(), r.height())

    get_bounds2d = get_bounds2_d

    def get_bounds(self):
        r = self.path().computeTightBounds()
        x0, y0 = math.floor(r.left()), math.floor(r.top())
        return Rectangle(x0, y0, math.ceil(r.right()) - x0, math.ceil(r.bottom()) - y0)

    def contains(self, x, y=None, w=None, h=None):
        if y is None:
            x, y = x.get_x(), x.get_y()
        if w is not None:
            p = self.path()
            return p.contains(x, y) and p.contains(x + w, y) and p.contains(x, y + h) and p.contains(x + w, y + h)
        return self.path().contains(float(x), float(y))

    def intersects(self, x, y=None, w=None, h=None):
        if y is None:
            r = x
            x, y, w, h = r.get_x(), r.get_y(), r.get_width(), r.get_height()
        b = self.path().computeTightBounds()
        return b.intersects(skia.Rect.MakeXYWH(x, y, w, h))


class RectangularShape(Shape):
    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_min_x(self):
        return self.x

    def get_min_y(self):
        return self.y

    def get_max_x(self):
        return self.x + self.width

    def get_max_y(self):
        return self.y + self.height

    def get_center_x(self):
        return self.x + self.width / 2.0

    def get_center_y(self):
        return self.y + self.height / 2.0

    def is_empty(self):
        return self.width <= 0 or self.height <= 0

    def set_frame(self, x, y=None, w=None, h=None):
        if y is None:
            r = x
            x, y, w, h = r.get_x(), r.get_y(), r.get_width(), r.get_height()
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)

    def set_frame_from_center(self, cx, cy, x, y):
        hw, hh = abs(x - cx), abs(y - cy)
        self.set_frame(cx - hw, cy - hh, 2 * hw, 2 * hh)

    def get_frame(self):
        return Rectangle2DDouble(self.x, self.y, self.width, self.height)

    def get_bounds2_d(self):
        return Rectangle2DDouble(self.x, self.y, self.width, self.height)

    get_bounds2d = get_bounds2_d


class Rectangle2DDouble(RectangularShape):
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)

    def set_rect(self, x, y=None, w=None, h=None):
        self.set_frame(x, y, w, h)

    def path(self):
        p = skia.Path()
        p.addRect(skia.Rect.MakeXYWH(self.x, self.y, self.width, self.height))
        return p

    def contains(self, x, y=None, w=None, h=None):
        if y is None:
            x, y = x.get_x(), x.get_y()
        if w is not None:
            return (self.width > 0 and self.height > 0 and w > 0 and h > 0 and x >= self.x and y >= self.y
                    and x + w <= self.x + self.width and y + h <= self.y + self.height)
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def intersects(self, x, y=None, w=None, h=None):
        if y is None:
            r = x
            x, y, w, h = r.get_x(), r.get_y(), r.get_width(), r.get_height()
        return w > 0 and h > 0 and self.width > 0 and self.height > 0 and x < self.x + self.width and x + w > self.x and y < self.y + self.height and y + h > self.y

    def create_union(self, r):
        x0, y0 = min(self.x, r.get_x()), min(self.y, r.get_y())
        x1, y1 = max(self.get_max_x(), r.get_max_x()), max(self.get_max_y(), r.get_max_y())
        return Rectangle2DDouble(x0, y0, x1 - x0, y1 - y0)

    def __repr__(self):
        return "Rectangle2D.Double[x=%s,y=%s,w=%s,h=%s]" % (self.x, self.y, self.width, self.height)


class Rectangle2D:
    Double = Rectangle2DDouble
    Float = Rectangle2DDouble


class Rectangle(Shape):
    """java.awt.Rectangle (integer)."""

    def __init__(self, x=0, y=0, w=None, h=None):
        if isinstance(x, Rectangle):
            x, y, w, h = x.x, x.y, x.width, x.height
        elif isinstance(x, Dimension):
            x, y, w, h = 0, 0, x.width, x.height
        elif w is None:
            x, y, w, h = 0, 0, x, y
        self.x, self.y, self.width, self.height = int(x), int(y), int(w), int(h)

    def path(self):
        p = skia.Path()
        p.addRect(skia.Rect.MakeXYWH(self.x, self.y, self.width, self.height))
        return p

    def get_x(self):
        return float(self.x)

    def get_y(self):
        return float(self.y)

    def get_width(self):
        return float(self.width)

    def get_height(self):
        return float(self.height)

    def get_center_x(self):
        return self.x + self.width / 2.0

    def get_center_y(self):
        return self.y + self.height / 2.0

    def get_max_x(self):
        return float(self.x + self.width)

    def get_max_y(self):
        return float(self.y + self.height)

    def get_size(self):
        return Dimension(self.width, self.height)

    def get_location(self):
        return Point(self.x, self.y)

    def get_bounds(self):
        return Rectangle(self)

    def set_bounds(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self.x, self.y, self.width, self.height = int(x), int(y), int(w), int(h)

    def set_location(self, x, y):
        self.x, self.y = int(x), int(y)

    def set_size(self, w, h):
        self.width, self.height = int(w), int(h)

    def contains(self, x, y=None, w=None, h=None):
        if isinstance(x, Rectangle):
            r = x
            return self.contains(r.x, r.y, r.width, r.height)
        if y is None:
            x, y = x.x, x.y
        if w is not None:
            return (w >= 0 and h >= 0 and self.width >= 0 and self.height >= 0 and x >= self.x and y >= self.y
                    and x + w <= self.x + self.width and y + h <= self.y + self.height)
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def intersects(self, r):
        return r.x < self.x + self.width and r.x + r.width > self.x and r.y < self.y + self.height and r.y + r.height > self.y

    def __eq__(self, o):
        return isinstance(o, Rectangle) and (o.x, o.y, o.width, o.height) == (self.x, self.y, self.width, self.height)

    def equals(self, o):
        return self.__eq__(o)

    def __hash__(self):
        return hash((self.x, self.y, self.width, self.height))

    def __repr__(self):
        return "java.awt.Rectangle[x=%d,y=%d,width=%d,height=%d]" % (self.x, self.y, self.width, self.height)


class Ellipse2DDouble(RectangularShape):
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)

    def path(self):
        p = skia.Path()
        p.addOval(skia.Rect.MakeXYWH(self.x, self.y, self.width, self.height))
        return p

    def contains(self, x, y=None, w=None, h=None):
        if y is None:
            x, y = x.get_x(), x.get_y()
        if w is not None:
            return Shape.contains(self, x, y, w, h)
        if self.width <= 0 or self.height <= 0:
            return False
        nx = (x - self.x) / self.width - 0.5
        ny = (y - self.y) / self.height - 0.5
        return nx * nx + ny * ny < 0.25


class Ellipse2D:
    Double = Ellipse2DDouble
    Float = Ellipse2DDouble


class RoundRectangle2DDouble(RectangularShape):
    def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0, aw=0.0, ah=0.0):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)
        self.arcwidth, self.archeight = float(aw), float(ah)

    def set_round_rect(self, x, y, w, h, aw, ah):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)
        self.arcwidth, self.archeight = float(aw), float(ah)

    def path(self):
        p = skia.Path()
        rx = min(abs(self.arcwidth), abs(self.width)) / 2.0
        ry = min(abs(self.archeight), abs(self.height)) / 2.0
        p.addRoundRect(skia.Rect.MakeXYWH(self.x, self.y, self.width, self.height), rx, ry)
        return p


class RoundRectangle2D:
    Double = RoundRectangle2DDouble
    Float = RoundRectangle2DDouble


class Line2DDouble(Shape):
    __slots__ = ("x1", "y1", "x2", "y2")

    def __init__(self, x1=0.0, y1=0.0, x2=0.0, y2=0.0):
        if isinstance(x1, Point2D):
            p1, p2 = x1, y1
            x1, y1, x2, y2 = p1.get_x(), p1.get_y(), p2.get_x(), p2.get_y()
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)

    def set_line(self, x1, y1=None, x2=None, y2=None):
        if y1 is None:
            ln = x1
            x1, y1, x2, y2 = ln.x1, ln.y1, ln.x2, ln.y2
        elif x2 is None:
            p1, p2 = x1, y1
            x1, y1, x2, y2 = p1.get_x(), p1.get_y(), p2.get_x(), p2.get_y()
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)

    def get_x1(self):
        return self.x1

    def get_y1(self):
        return self.y1

    def get_x2(self):
        return self.x2

    def get_y2(self):
        return self.y2

    def path(self):
        p = skia.Path()
        p.moveTo(self.x1, self.y1)
        p.lineTo(self.x2, self.y2)
        return p


class Line2D:
    Double = Line2DDouble
    Float = Line2DDouble


class Arc2DDouble(RectangularShape):
    OPEN, CHORD, PIE = 0, 1, 2

    def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0, start=0.0, extent=0.0, type_=0):
        if isinstance(x, int) and y == 0.0 and w == 0.0 and h == 0.0 and start == 0.0 and extent == 0.0 and type_ == 0 and x in (0, 1, 2):
            self.x = self.y = self.width = self.height = self.start = self.extent = 0.0
            self.type = x
            return
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)
        self.start, self.extent, self.type = float(start), float(extent), int(type_)

    def set_arc(self, x, y, w, h, start, extent, type_):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)
        self.start, self.extent, self.type = float(start), float(extent), int(type_)

    def set_angle_start(self, a):
        self.start = float(a)

    def set_angle_extent(self, a):
        self.extent = float(a)

    def get_angle_start(self):
        return self.start

    def get_angle_extent(self):
        return self.extent

    def path(self):
        p = skia.Path()
        r = skia.Rect.MakeXYWH(self.x, self.y, self.width, self.height)
        ext = self.extent
        if abs(ext) >= 360:
            if self.type == Arc2D.PIE or self.type == Arc2D.CHORD:
                p.addOval(r)
                return p
            p.addArc(r, -self.start, -359.999)
            return p
        if self.type == Arc2D.PIE:
            p.moveTo(r.centerX(), r.centerY())
            p.arcTo(r, -self.start, -ext, False)
            p.close()
        else:
            p.arcTo(r, -self.start, -ext, True)
            if self.type == Arc2D.CHORD:
                p.close()
        return p


class Arc2D:
    OPEN, CHORD, PIE = 0, 1, 2
    Double = Arc2DDouble
    Float = Arc2DDouble


class QuadCurve2DDouble(Shape):
    def __init__(self, x1=0.0, y1=0.0, cx=0.0, cy=0.0, x2=0.0, y2=0.0):
        self.set_curve(x1, y1, cx, cy, x2, y2)

    def set_curve(self, x1, y1, cx, cy, x2, y2):
        self.x1, self.y1, self.ctrlx, self.ctrly, self.x2, self.y2 = map(float, (x1, y1, cx, cy, x2, y2))

    def path(self):
        p = skia.Path()
        p.moveTo(self.x1, self.y1)
        p.quadTo(self.ctrlx, self.ctrly, self.x2, self.y2)
        return p


class QuadCurve2D:
    Double = QuadCurve2DDouble
    Float = QuadCurve2DDouble


class CubicCurve2DDouble(Shape):
    def __init__(self, x1=0.0, y1=0.0, c1x=0.0, c1y=0.0, c2x=0.0, c2y=0.0, x2=0.0, y2=0.0):
        self.set_curve(x1, y1, c1x, c1y, c2x, c2y, x2, y2)

    def set_curve(self, x1, y1, c1x, c1y, c2x, c2y, x2, y2):
        self.c = tuple(map(float, (x1, y1, c1x, c1y, c2x, c2y, x2, y2)))

    def path(self):
        c = self.c
        p = skia.Path()
        p.moveTo(c[0], c[1])
        p.cubicTo(c[2], c[3], c[4], c[5], c[6], c[7])
        return p


class CubicCurve2D:
    Double = CubicCurve2DDouble
    Float = CubicCurve2DDouble


class Path2DDouble(Shape):
    WIND_EVEN_ODD, WIND_NON_ZERO = 0, 1

    def __init__(self, rule=None, *_):
        self._p = skia.Path()
        if isinstance(rule, Shape):
            self._p = skia.Path(rule.path())
        elif rule == 0:
            self._p.setFillType(skia.PathFillType.kEvenOdd)

    def move_to(self, x, y):
        self._p.moveTo(float(x), float(y))

    def line_to(self, x, y):
        self._p.lineTo(float(x), float(y))

    def quad_to(self, cx, cy, x, y):
        self._p.quadTo(float(cx), float(cy), float(x), float(y))

    def curve_to(self, c1x, c1y, c2x, c2y, x, y):
        self._p.cubicTo(float(c1x), float(c1y), float(c2x), float(c2y), float(x), float(y))

    def close_path(self):
        self._p.close()

    def reset(self):
        ft = self._p.getFillType()
        self._p.reset()
        self._p.setFillType(ft)

    def append(self, s, connect):
        sp = s.path() if isinstance(s, Shape) else s
        if connect and self._p.countVerbs() > 0:
            self._p.addPath(sp, skia.Path.AddPathMode.kExtend_AddPathMode)
        else:
            self._p.addPath(sp)

    def set_winding_rule(self, rule):
        self._p.setFillType(skia.PathFillType.kEvenOdd if rule == 0 else skia.PathFillType.kWinding)

    def get_current_point(self):
        n = self._p.countPoints()
        if n == 0:
            return None
        pt = self._p.getPoint(n - 1)
        return Point2DDouble(pt.x(), pt.y())

    def transform(self, at):
        self._p.transform(at.m)

    def create_transformed_shape(self, at):
        q = Path2DDouble()
        self._p.transform(at.m, q._p)
        return q

    def path(self):
        return self._p

    def clone(self):
        return Path2DDouble(self)


class Path2D:
    WIND_EVEN_ODD, WIND_NON_ZERO = 0, 1
    Double = Path2DDouble
    Float = Path2DDouble


GeneralPath = Path2DDouble


class Polygon(Shape):
    def __init__(self, xs=None, ys=None, n=None):
        self.xpoints = list(xs[:n]) if xs is not None else []
        self.ypoints = list(ys[:n]) if ys is not None else []
        self.npoints = len(self.xpoints)

    def add_point(self, x, y):
        self.xpoints.append(int(x))
        self.ypoints.append(int(y))
        self.npoints += 1

    def reset(self):
        self.xpoints, self.ypoints, self.npoints = [], [], 0

    def path(self):
        p = skia.Path()
        if self.npoints:
            p.moveTo(self.xpoints[0], self.ypoints[0])
            for i in range(1, self.npoints):
                p.lineTo(self.xpoints[i], self.ypoints[i])
            p.close()
        return p


class PathShape(Shape):
    """A Shape around an existing Skia path."""
    __slots__ = ("_p",)

    def __init__(self, p):
        self._p = p

    def path(self):
        return self._p


class Area(Shape):
    def __init__(self, s=None):
        self._p = skia.Path(s.path()) if s is not None else skia.Path()
        if s is not None:
            self._p = self._norm(self._p)

    @staticmethod
    def _norm(p):
        q = skia.Simplify(p)
        return q if q is not None else p

    def _op(self, s, op):
        r = skia.Op(self._p, s.path(), op)
        if r is not None:
            self._p = r

    def add(self, s):
        self._op(s, skia.PathOp.kUnion_PathOp)

    def subtract(self, s):
        self._op(s, skia.PathOp.kDifference_PathOp)

    def intersect(self, s):
        self._op(s, skia.PathOp.kIntersect_PathOp)

    def exclusive_or(self, s):
        self._op(s, skia.PathOp.kXOR_PathOp)

    def is_empty(self):
        return self._p.isEmpty()

    def reset(self):
        self._p = skia.Path()

    def transform(self, at):
        self._p.transform(at.m)

    def create_transformed_area(self, at):
        a = Area()
        self._p.transform(at.m, a._p)
        return a

    def path(self):
        return self._p


# ====================================================================== transforms
class AffineTransform:
    __slots__ = ("m",)

    def __init__(self, *a):
        if not a:
            self.m = skia.Matrix()
        elif len(a) == 1:
            src = a[0]
            self.m = mcopy(src.m) if isinstance(src, AffineTransform) else src
        elif len(a) == 6:   # m00, m10, m01, m11, m02, m12
            m00, m10, m01, m11, m02, m12 = map(float, a)
            self.m = skia.Matrix.MakeAll(m00, m01, m02, m10, m11, m12, 0, 0, 1)
        else:
            raise TypeError("AffineTransform%r" % (a,))

    @staticmethod
    def get_translate_instance(x, y):
        return AffineTransform(skia.Matrix.Translate(x, y))

    @staticmethod
    def get_rotate_instance(theta, x=None, y=None):
        m = skia.Matrix.RotateRad(theta) if x is None else skia.Matrix.RotateDeg(math.degrees(theta), skia.Point(x, y))
        return AffineTransform(m)

    @staticmethod
    def get_scale_instance(sx, sy):
        return AffineTransform(skia.Matrix.Scale(sx, sy))

    def translate(self, x, y):
        self.m.preTranslate(float(x), float(y))

    def rotate(self, theta, x=None, y=None):
        if x is None:
            self.m.preRotate(math.degrees(theta))
        else:
            self.m.preRotate(math.degrees(theta), float(x), float(y))

    def scale(self, sx, sy):
        self.m.preScale(float(sx), float(sy))

    def shear(self, shx, shy):
        self.m.preSkew(float(shx), float(shy))

    def concatenate(self, at):
        self.m.preConcat(at.m)

    def pre_concatenate(self, at):
        self.m.postConcat(at.m)

    def set_to_identity(self):
        self.m.reset()

    def set_to_translation(self, x, y):
        self.m.setTranslate(float(x), float(y))

    def set_to_rotation(self, theta, x=None, y=None):
        if x is None:
            self.m.setRotate(math.degrees(theta))
        else:
            self.m.setRotate(math.degrees(theta), float(x), float(y))

    def set_to_scale(self, sx, sy):
        self.m.setScale(float(sx), float(sy))

    def set_transform(self, at):
        self.m = mcopy(at.m)

    def get_scale_x(self):
        return self.m.getScaleX()

    def get_scale_y(self):
        return self.m.getScaleY()

    def get_translate_x(self):
        return self.m.getTranslateX()

    def get_translate_y(self):
        return self.m.getTranslateY()

    def get_shear_x(self):
        return self.m.getSkewX()

    def get_shear_y(self):
        return self.m.getSkewY()

    def get_determinant(self):
        m = self.m
        return m.getScaleX() * m.getScaleY() - m.getSkewX() * m.getSkewY()

    def is_identity(self):
        return self.m.isIdentity()

    def get_matrix(self, arr):
        m = self.m
        vals = [m.getScaleX(), m.getSkewY(), m.getSkewX(), m.getScaleY(), m.getTranslateX(), m.getTranslateY()]
        for i in range(min(len(arr), 6)):
            arr[i] = vals[i]

    def transform(self, src, dst=None):
        p = self.m.mapXY(src.get_x(), src.get_y())
        if dst is None:
            return Point2DDouble(p.x(), p.y())
        dst.set_location(p.x(), p.y())
        return dst

    def inverse_transform(self, src, dst=None):
        inv = skia.Matrix()
        self.m.invert(inv)
        p = inv.mapXY(src.get_x(), src.get_y())
        if dst is None:
            return Point2DDouble(p.x(), p.y())
        dst.set_location(p.x(), p.y())
        return dst

    def create_transformed_shape(self, s):
        q = skia.Path()
        s.path().transform(self.m, q)
        return PathShape(q)

    def clone(self):
        return AffineTransform(mcopy(self.m))


# ====================================================================== strokes
class BasicStroke:
    CAP_BUTT, CAP_ROUND, CAP_SQUARE = 0, 1, 2
    JOIN_MITER, JOIN_ROUND, JOIN_BEVEL = 0, 1, 2
    _CAPS = (skia.Paint.kButt_Cap, skia.Paint.kRound_Cap, skia.Paint.kSquare_Cap)
    _JOINS = (skia.Paint.kMiter_Join, skia.Paint.kRound_Join, skia.Paint.kBevel_Join)

    def __init__(self, width=1.0, cap=2, join=0, miterlimit=10.0, dash=None, dash_phase=0.0):
        self.width = float(width)
        self.cap, self.join, self.miterlimit = cap, join, float(miterlimit)
        self.dash = list(dash) if dash else None
        self.dash_phase = float(dash_phase)
        self._effect = None
        self._skp = None
        if self.dash:
            d = [float(x) for x in self.dash]
            if len(d) % 2:
                d = d + d
            d = [max(x, 1e-3) for x in d]
            self._effect = skia.DashPathEffect.Make(d, self.dash_phase)

    def get_line_width(self):
        return self.width

    def get_end_cap(self):
        return self.cap

    def get_line_join(self):
        return self.join

    def get_dash_array(self):
        return self.dash

    def get_dash_phase(self):
        return self.dash_phase

    def get_miter_limit(self):
        return self.miterlimit

    def apply(self, paint):
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(self.width)
        paint.setStrokeCap(self._CAPS[self.cap])
        paint.setStrokeJoin(self._JOINS[self.join])
        paint.setStrokeMiter(self.miterlimit)
        if self._effect is not None:
            paint.setPathEffect(self._effect)

    def skpaint(self):
        """The cached Skia paint configured for this stroke (colour / blend are set per draw)."""
        p = self._skp
        if p is None:
            p = skia.Paint(AntiAlias=True)
            self.apply(p)
            self._skp = p
        return p

    def create_stroked_shape(self, s):
        paint = skia.Paint(AntiAlias=True)
        self.apply(paint)
        out = skia.Path()
        paint.getFillPath(s.path(), out)
        return PathShape(out)

    def __eq__(self, o):
        return (isinstance(o, BasicStroke) and o.width == self.width and o.cap == self.cap and o.join == self.join
                and o.dash == self.dash and o.dash_phase == self.dash_phase)

    def __hash__(self):
        return hash((self.width, self.cap, self.join))


Stroke = BasicStroke
_DEFAULT_STROKE = BasicStroke(1.0)


# ====================================================================== paints
class _Paint:
    def shader(self, alpha):
        raise NotImplementedError


def _colors_with_alpha(colors, alpha):
    out = []
    for c in colors:
        a = c.get_alpha()
        if alpha < 1.0:
            a = int(a * alpha + 0.5)
        out.append((a << 24) | (c._argb & 0xFFFFFF))
    return out


class GradientPaint(_Paint):
    def __init__(self, x1, y1, c1, x2, y2=None, c2=None, cyclic=False):
        if isinstance(x1, Point2D):   # (p1, c1, p2, c2[, cyclic])
            p1, col1, p2, col2 = x1, y1, c1, x2
            cyclic = bool(y2) if y2 is not None else False
            x1, y1, x2, y2, c1, c2 = p1.get_x(), p1.get_y(), p2.get_x(), p2.get_y(), col1, col2
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)
        self.c1, self.c2, self.cyclic = c1, c2, cyclic

    def get_color1(self):
        return self.c1

    def get_color2(self):
        return self.c2

    def shader(self, alpha):
        mode = skia.TileMode.kMirror if self.cyclic else skia.TileMode.kClamp
        return skia.GradientShader.MakeLinear([skia.Point(self.x1, self.y1), skia.Point(self.x2, self.y2)],
                                              _colors_with_alpha((self.c1, self.c2), alpha), None, mode)


class MultipleGradientPaint(_Paint):
    class CycleMethod:
        NO_CYCLE, REFLECT, REPEAT = 0, 1, 2

    _TILE = (skia.TileMode.kClamp, skia.TileMode.kMirror, skia.TileMode.kRepeat)


class LinearGradientPaint(MultipleGradientPaint):
    def __init__(self, x1, y1, x2=None, y2=None, fractions=None, colors=None, cycle=0, *rest):
        if isinstance(x1, Point2D):   # (start, end, fractions, colors[, cycle])
            start, end, fr, cols = x1, y1, x2, y2
            cyc = fractions if fractions is not None else 0
            x1, y1, x2, y2 = start.get_x(), start.get_y(), end.get_x(), end.get_y()
            fractions, colors, cycle = fr, cols, cyc
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)
        self.fractions = [float(f) for f in fractions]
        self.colors = list(colors)
        self.cycle = cycle if isinstance(cycle, int) else 0

    def shader(self, alpha):
        return skia.GradientShader.MakeLinear([skia.Point(self.x1, self.y1), skia.Point(self.x2, self.y2)],
                                              _colors_with_alpha(self.colors, alpha), self.fractions, self._TILE[self.cycle])


class RadialGradientPaint(MultipleGradientPaint):
    def __init__(self, *a):
        # (cx, cy, r, fractions, colors[, cycle]) | (center, r, fractions, colors[, cycle])
        # | (cx, cy, r, fx, fy, fractions, colors, cycle) | (center, r, focus, fractions, colors, cycle)
        a = list(a)
        if isinstance(a[0], Point2D):
            c = a.pop(0)
            a = [c.get_x(), c.get_y()] + a
            if len(a) >= 4 and isinstance(a[3], Point2D):
                f = a.pop(3)
                a[3:3] = [f.get_x(), f.get_y()]
        self.cx, self.cy, self.r = float(a[0]), float(a[1]), float(a[2])
        rest = a[3:]
        self.fx, self.fy = self.cx, self.cy
        if rest and not isinstance(rest[0], (list, tuple)):
            self.fx, self.fy = float(rest[0]), float(rest[1])
            rest = rest[2:]
        self.fractions = [float(f) for f in rest[0]]
        self.colors = list(rest[1])
        self.cycle = rest[2] if len(rest) > 2 and isinstance(rest[2], int) else 0

    def shader(self, alpha):
        cols = _colors_with_alpha(self.colors, alpha)
        r = max(self.r, 1e-4)
        if self.fx == self.cx and self.fy == self.cy:
            return skia.GradientShader.MakeRadial(skia.Point(self.cx, self.cy), r, cols, self.fractions, self._TILE[self.cycle])
        return skia.GradientShader.MakeTwoPointConical(skia.Point(self.fx, self.fy), 0, skia.Point(self.cx, self.cy), r, cols,
                                                       self.fractions, self._TILE[self.cycle])


class TexturePaint(_Paint):
    def __init__(self, img, anchor):
        self.img, self.anchor = img, anchor

    def shader(self, alpha):
        m = skia.Matrix.Translate(self.anchor.get_x(), self.anchor.get_y())
        m.preScale(self.anchor.get_width() / max(1, self.img.get_width()), self.anchor.get_height() / max(1, self.img.get_height()))
        return self.img.snapshot().makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat, skia.SamplingOptions(skia.FilterMode.kLinear), m)


# ====================================================================== composites / hints
class AlphaComposite:
    CLEAR, SRC, SRC_OVER, DST_OVER, SRC_IN, DST_IN, SRC_OUT, DST_OUT, DST, SRC_ATOP, DST_ATOP, XOR = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    _MODES = {1: skia.BlendMode.kClear, 2: skia.BlendMode.kSrc, 3: skia.BlendMode.kSrcOver, 4: skia.BlendMode.kDstOver,
              5: skia.BlendMode.kSrcIn, 6: skia.BlendMode.kDstIn, 7: skia.BlendMode.kSrcOut, 8: skia.BlendMode.kDstOut,
              9: skia.BlendMode.kDst, 10: skia.BlendMode.kSrcATop, 11: skia.BlendMode.kDstATop, 12: skia.BlendMode.kXor}

    def __init__(self, rule, alpha=1.0):
        self.rule, self.alpha = rule, max(0.0, min(1.0, float(alpha)))
        self.mode = self._MODES[rule]

    @staticmethod
    def get_instance(rule, alpha=1.0):
        return AlphaComposite(rule, alpha)

    def derive(self, x):
        """derive(float alpha) keeps the rule; derive(int rule) keeps the alpha (Java overloads)."""
        if isinstance(x, float):
            return AlphaComposite(self.rule, x)
        return AlphaComposite(int(x), self.alpha)

    def get_alpha(self):
        return self.alpha

    def get_rule(self):
        return self.rule

    def __eq__(self, o):
        return isinstance(o, AlphaComposite) and o.rule == self.rule and o.alpha == self.alpha

    def __hash__(self):
        return hash((self.rule, self.alpha))


AlphaComposite.Clear = AlphaComposite(1)
AlphaComposite.Src = AlphaComposite(2)
AlphaComposite.SrcOver = AlphaComposite(3)
AlphaComposite.DstOver = AlphaComposite(4)
AlphaComposite.SrcIn = AlphaComposite(5)
AlphaComposite.DstIn = AlphaComposite(6)
AlphaComposite.SrcOut = AlphaComposite(7)
AlphaComposite.DstOut = AlphaComposite(8)
AlphaComposite.SrcAtop = AlphaComposite(10)
AlphaComposite.Xor = AlphaComposite(12)
Composite = AlphaComposite


class RenderingHints:
    KEY_ANTIALIASING = "aa"
    VALUE_ANTIALIAS_ON = "aa_on"
    VALUE_ANTIALIAS_OFF = "aa_off"
    VALUE_ANTIALIAS_DEFAULT = "aa_default"
    KEY_TEXT_ANTIALIASING = "taa"
    VALUE_TEXT_ANTIALIAS_ON = "taa_on"
    VALUE_TEXT_ANTIALIAS_OFF = "taa_off"
    VALUE_TEXT_ANTIALIAS_DEFAULT = "taa_default"
    KEY_RENDERING = "render"
    VALUE_RENDER_QUALITY = "render_q"
    VALUE_RENDER_SPEED = "render_s"
    VALUE_RENDER_DEFAULT = "render_d"
    KEY_STROKE_CONTROL = "stroke"
    VALUE_STROKE_PURE = "stroke_pure"
    VALUE_STROKE_NORMALIZE = "stroke_norm"
    VALUE_STROKE_DEFAULT = "stroke_d"
    KEY_FRACTIONALMETRICS = "fm"
    VALUE_FRACTIONALMETRICS_ON = "fm_on"
    VALUE_FRACTIONALMETRICS_OFF = "fm_off"
    KEY_INTERPOLATION = "interp"
    VALUE_INTERPOLATION_BILINEAR = "interp_bilinear"
    VALUE_INTERPOLATION_BICUBIC = "interp_bicubic"
    VALUE_INTERPOLATION_NEAREST_NEIGHBOR = "interp_nn"
    KEY_COLOR_RENDERING = "color"
    VALUE_COLOR_RENDER_QUALITY = "color_q"
    VALUE_COLOR_RENDER_SPEED = "color_s"
    KEY_ALPHA_INTERPOLATION = "ai"
    VALUE_ALPHA_INTERPOLATION_QUALITY = "ai_q"
    VALUE_ALPHA_INTERPOLATION_SPEED = "ai_s"
    KEY_DITHERING = "dither"
    VALUE_DITHER_ENABLE = "dither_on"
    VALUE_DITHER_DISABLE = "dither_off"


# ====================================================================== fonts
FONT_DIR_CANDIDATES = []


def _find_assets():
    here = os.path.dirname(os.path.abspath(__file__))
    for up in range(1, 6):
        d = os.path.join(here, *([".."] * up), "assets")
        if os.path.isdir(os.path.join(d, "fonts")):
            return os.path.normpath(d)
    return os.path.join(os.getcwd(), "assets")


ASSETS_DIR = os.environ.get("LINDEFENSE_ASSETS") or _find_assets()

_TYPEFACES = {}
_FALLBACK_CACHE = {}
_MGR = skia.FontMgr.RefDefault() if hasattr(skia.FontMgr, "RefDefault") else skia.FontMgr()


def _typeface_for_file(path):
    tf = _TYPEFACES.get(path)
    if tf is None:
        tf = skia.Typeface.MakeFromFile(path)
        _TYPEFACES[path] = tf
    return tf


def _logical_typeface(name, style):
    key = (name, style)
    tf = _TYPEFACES.get(key)
    if tf is None:
        fam = {"SansSerif": "Helvetica Neue", "Dialog": "Helvetica Neue", "DialogInput": "Menlo", "Monospaced": "Menlo",
               "Serif": "Times New Roman"}.get(name, name)
        fs = skia.FontStyle.Bold() if style & 1 else skia.FontStyle.Normal()
        if style & 2:
            fs = skia.FontStyle.BoldItalic() if style & 1 else skia.FontStyle.Italic()
        tf = skia.Typeface(fam, fs) or skia.Typeface("Helvetica", fs)
        _TYPEFACES[key] = tf
    return tf


class Font:
    PLAIN, BOLD, ITALIC = 0, 1, 2
    TRUETYPE_FONT = 0
    SANS_SERIF, SERIF, MONOSPACED, DIALOG, DIALOG_INPUT = "SansSerif", "Serif", "Monospaced", "Dialog", "DialogInput"

    def __init__(self, name="Dialog", style=0, size=12, _tf=None, _file=None):
        self.name = name
        self.style = int(style)
        self.size2d = float(size)
        self.size = int(size)
        self._file = _file
        self._tf = _tf if _tf is not None else _logical_typeface(name, self.style)
        self._sk = None
        self._metrics = None

    @staticmethod
    def create_font(fmt, src):
        path = src if isinstance(src, str) else getattr(src, "name", None) or getattr(src, "path", None)
        tf = _typeface_for_file(path) if path else None
        if tf is None:
            raise IOError("cannot load font %r" % (src,))
        fam = tf.getFamilyName() if hasattr(tf, "getFamilyName") else os.path.basename(path)
        return Font(fam, 0, 1, _tf=tf, _file=path)

    def derive_font(self, a, b=None):
        if b is not None:   # (style, size)
            return Font(self.name, a, b, _tf=self._tf, _file=self._file)
        if isinstance(a, float):
            return Font(self.name, self.style, a, _tf=self._tf, _file=self._file)
        return Font(self.name, a, self.size2d, _tf=self._tf, _file=self._file)

    def get_size(self):
        return self.size

    def get_size2_d(self):
        return self.size2d

    get_size2d = get_size2_d

    def get_style(self):
        return self.style

    def is_bold(self):
        return bool(self.style & 1)

    def is_italic(self):
        return bool(self.style & 2)

    def get_name(self):
        return self.name

    def get_family(self):
        return self.name

    def get_font_name(self):
        return self.name

    def skfont(self):
        f = self._sk
        if f is None:
            f = skia.Font(self._tf, self.size2d)
            f.setSubpixel(True)
            f.setEdging(skia.Font.Edging.kAntiAlias)
            f.setHinting(skia.FontHinting.kNone)
            f.setLinearMetrics(True)
            if self._file is None and self.style & 1 and not self._tf.isBold():
                f.setEmbolden(True)
            self._sk = f
        return f

    def can_display_up_to(self, s):
        f = self.skfont()
        for i, ch in enumerate(s):
            if f.unicharToGlyph(ord(ch)) == 0:
                return i
        return -1

    def can_display(self, ch):
        return self.skfont().unicharToGlyph(ord(ch) if isinstance(ch, str) else ch) != 0

    def get_string_bounds(self, s, frc=None):
        fm = font_metrics(self)
        return Rectangle2DDouble(0, -fm.ascent_f, fm.string_width_f(s), fm.ascent_f + fm.descent_f + fm.leading_f)

    def get_line_metrics(self, s, frc=None):
        return font_metrics(self)

    def __eq__(self, o):
        return isinstance(o, Font) and o._tf is self._tf and o.size2d == self.size2d and o.style == self.style

    def __hash__(self):
        return hash((id(self._tf), self.size2d, self.style))

    def __repr__(self):
        return "java.awt.Font[family=%s,style=%d,size=%s]" % (self.name, self.style, self.size)


def _fallback_font(base, ch):
    key = (id(base._tf), base.size2d, ch)
    f = _FALLBACK_CACHE.get(key)
    if f is None:
        tf = None
        try:
            tf = _MGR.matchFamilyStyleCharacter(None, skia.FontStyle(), [], ord(ch))
        except Exception:
            tf = None
        f = skia.Font(tf, base.size2d) if tf is not None else base.skfont()
        f.setSubpixel(True)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        f.setLinearMetrics(True)
        _FALLBACK_CACHE[key] = f
    return f


def _runs(font, s):
    """Splits s into (skfont, text) runs, using a fallback typeface for characters the font lacks."""
    f = font.skfont()
    glyphs = f.textToGlyphs(s)
    if 0 not in glyphs:
        return ((f, s),)
    runs = []
    cur_f, cur = None, []
    for ch, gid in zip(s, glyphs):
        ff = f if gid != 0 or ch in " \t" else _fallback_font(font, ch)
        if ff is not cur_f and cur:
            runs.append((cur_f, "".join(cur)))
            cur = []
        cur_f = ff
        cur.append(ch)
    if cur:
        runs.append((cur_f, "".join(cur)))
    return runs


class FontMetrics:
    def __init__(self, font):
        self.font = font
        m = font.skfont().getMetrics()
        self.ascent_f = -m.fAscent
        self.descent_f = m.fDescent
        self.leading_f = m.fLeading
        # Java rounds the line metrics to whole pixels
        self.ascent = int(math.floor(self.ascent_f + 0.5))
        self.descent = int(math.floor(self.descent_f + 0.5))
        self.leading = int(math.floor(self.leading_f + 0.5))
        self._w = {}

    def get_ascent(self):
        return self.ascent

    def get_descent(self):
        return self.descent

    def get_leading(self):
        return self.leading

    def get_height(self):
        return self.ascent + self.descent + self.leading

    def get_max_ascent(self):
        return self.ascent

    def get_font(self):
        return self.font

    def string_width_f(self, s):
        w = self._w.get(s)
        if w is None:
            w = 0.0
            for f, t in _runs(self.font, s):
                w += f.measureText(t)
            if len(self._w) < 4096:
                self._w[s] = w
        return w

    def string_width(self, s):
        return int(math.floor(self.string_width_f(s) + 0.5))

    def char_width(self, ch):
        return self.string_width(ch if isinstance(ch, str) else chr(ch))

    def get_string_bounds(self, s, g=None):
        return Rectangle2DDouble(0, -self.ascent, self.string_width_f(s), self.get_height())


_FM = {}


def font_metrics(font):
    fm = _FM.get(font)
    if fm is None:
        fm = FontMetrics(font)
        _FM[font] = fm
    return fm


# ====================================================================== images
class Image:
    SCALE_DEFAULT, SCALE_FAST, SCALE_SMOOTH = 1, 2, 4


class BufferedImage(Image):
    TYPE_INT_RGB, TYPE_INT_ARGB, TYPE_INT_ARGB_PRE = 1, 2, 3

    def __init__(self, w, h=None, type_=2, _img=None):
        if _img is not None:
            self._surface = None
            self._snap = _img
            self.width, self.height = _img.width(), _img.height()
            return
        self.width, self.height = max(1, int(w)), max(1, int(h))
        self._surface = skia.Surface.MakeRasterN32Premul(self.width, self.height)
        if type_ == BufferedImage.TYPE_INT_RGB:
            self._surface.getCanvas().clear(0xFF000000)
        self._snap = None

    def get_width(self, obs=None):
        return self.width

    def get_height(self, obs=None):
        return self.height

    def _ensure_surface(self):
        if self._surface is None:
            s = skia.Surface.MakeRasterN32Premul(self.width, self.height)
            s.getCanvas().drawImage(self._snap, 0, 0)
            self._surface = s

    def create_graphics(self):
        self._ensure_surface()
        self._snap = None
        return Graphics2D(self._surface.getCanvas(), owner=self)

    get_graphics = create_graphics

    def _dirty(self):
        self._snap = None

    def snapshot(self):
        if self._snap is None:
            self._snap = self._surface.makeImageSnapshot()
        return self._snap

    def get_rgb(self, x, y):
        img = self.snapshot()
        bm = skia.Bitmap()
        bm.allocPixels(skia.ImageInfo.Make(1, 1, skia.ColorType.kBGRA_8888_ColorType, skia.AlphaType.kUnpremul_AlphaType))
        img.readPixels(bm.info(), bm.getPixels(), bm.rowBytes(), int(x), int(y))
        v = bm.getColor(0, 0)
        return v - (1 << 32) if v & 0x80000000 else v

    def set_rgb(self, x, y, argb):
        self._ensure_surface()
        p = skia.Paint(Color=argb & 0xFFFFFFFF, BlendMode=skia.BlendMode.kSrc)
        self._surface.getCanvas().drawRect(skia.Rect.MakeXYWH(x, y, 1, 1), p)
        self._snap = None

    def get_scaled_instance(self, w, h, hints=0):
        out = BufferedImage(w, h)
        c = out._surface.getCanvas()
        c.drawImageRect(self.snapshot(), skia.Rect.MakeWH(w, h), skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
        return out

    def save_png(self, path):
        self.snapshot().save(path, skia.kPNG)


class ImageIO:
    @staticmethod
    def read(src):
        path = src if isinstance(src, str) else getattr(src, "path", None) or str(src)
        img = skia.Image.open(path)
        return BufferedImage(0, 0, _img=img) if img is not None else None

    @staticmethod
    def write(img, fmt, dst):
        path = dst if isinstance(dst, str) else getattr(dst, "path", None) or str(dst)
        img.save_png(path)
        return True


# ====================================================================== Graphics2D
_IDENTITY = skia.Matrix.I()


def mcopy(m):
    """Copy of a skia.Matrix (skia-python has no copy constructor)."""
    return skia.Matrix.Concat(m, _IDENTITY)
_SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kNone)


class _CanvasState:
    """Per-canvas bookkeeping: which clip is currently applied (clips are pushed with save/restore)."""
    __slots__ = ("canvas", "base", "clip", "mtok", "fc", "fm", "solid")

    def __init__(self, canvas):
        self.canvas = canvas
        self.base = canvas.getSaveCount()
        self.clip = None
        self.mtok = None    # token of the Graphics matrix currently set on the canvas
        self.fc = None      # last colour / blend mode set on this canvas's solid paint
        self.fm = None
        self.solid = skia.Paint(AntiAlias=True)


_STATES = {}
_SOLID = skia.Paint(AntiAlias=True)
_IMG = skia.Paint(AntiAlias=True)


def _state_for(canvas):
    k = id(canvas)
    st = _STATES.get(k)
    if st is None or st.canvas is not canvas:
        st = _CanvasState(canvas)
        _STATES[k] = st
    return st


def reset_canvas_state(canvas):
    """Called at the start of every frame for a canvas: forget the applied clip."""
    st = _state_for(canvas)
    canvas.restoreToCount(st.base)
    st.clip = None
    st.mtok = None


class Graphics2D:
    """java.awt.Graphics2D on a Skia canvas. create() copies the state; state is applied lazily per draw call."""

    def __init__(self, canvas, owner=None, _copy=None):
        self._cv = canvas
        self._st = _state_for(canvas)
        self._owner = owner
        if _copy is None:
            self.m = skia.Matrix()
            self._mtok = None
            self.color = Color.BLACK
            self.paint = None
            self.stroke = _DEFAULT_STROKE
            self.font = None
            self.comp = AlphaComposite.SrcOver
            self.clipdev = None   # device-space skia.Path or None
            self.hints = {}
            self.bg = Color.BLACK
        else:
            self.m = mcopy(_copy.m)
            self._mtok = _copy._mtok   # same matrix value: the canvas need not be updated
            self.color, self.paint, self.stroke, self.font = _copy.color, _copy.paint, _copy.stroke, _copy.font
            self.comp, self.clipdev, self.hints, self.bg = _copy.comp, _copy.clipdev, dict(_copy.hints), _copy.bg

    # ---------------------------------------------------------------- state
    def create(self, x=None, y=None, w=None, h=None):
        g = Graphics2D(self._cv, self._owner, _copy=self)
        if x is not None:
            g.translate(x, y)
            g.clip_rect(0, 0, w, h)
        return g

    def dispose(self):
        pass

    def set_color(self, c):
        if c is not None:
            self.color = c
            self.paint = None

    def get_color(self):
        return self.color

    def set_paint(self, p):
        if p is None:
            return
        if isinstance(p, Color):
            self.color = p
            self.paint = None
        else:
            self.paint = p

    def get_paint(self):
        return self.paint if self.paint is not None else self.color

    def set_stroke(self, s):
        self.stroke = s

    def get_stroke(self):
        return self.stroke

    def set_font(self, f):
        if f is not None:
            self.font = f

    def get_font(self):
        if self.font is None:
            self.font = Font("Dialog", 0, 12)
        return self.font

    def get_font_metrics(self, f=None):
        return font_metrics(f if f is not None else self.get_font())

    def set_composite(self, c):
        self.comp = c

    def get_composite(self):
        return self.comp

    def set_rendering_hint(self, k, v):
        self.hints[k] = v

    def get_rendering_hint(self, k):
        return self.hints.get(k)

    def set_rendering_hints(self, m):
        self.hints.update(m)

    def set_background(self, c):
        self.bg = c

    def get_background(self):
        return self.bg

    def get_device_configuration(self):
        return None

    # ---------------------------------------------------------------- transforms
    def translate(self, x, y):
        self._mtok = None
        self.m.preTranslate(float(x), float(y))

    def rotate(self, theta, x=None, y=None):
        self._mtok = None
        if x is None:
            self.m.preRotate(math.degrees(theta))
        else:
            self.m.preRotate(math.degrees(theta), float(x), float(y))

    def scale(self, sx, sy):
        self._mtok = None
        self.m.preScale(float(sx), float(sy))

    def shear(self, shx, shy):
        self._mtok = None
        self.m.preSkew(float(shx), float(shy))

    def transform(self, at):
        self._mtok = None
        self.m.preConcat(at.m)

    def get_transform(self):
        return AffineTransform(mcopy(self.m))

    def set_transform(self, at):
        self.m = mcopy(at.m)
        self._mtok = None

    # ---------------------------------------------------------------- clip
    def clip(self, s):
        if s is None:
            return
        dev = skia.Path()
        s.path().transform(self.m, dev)
        if self.clipdev is None:
            self.clipdev = dev
        else:
            r = skia.Op(self.clipdev, dev, skia.PathOp.kIntersect_PathOp)
            self.clipdev = r if r is not None else dev

    def clip_rect(self, x, y, w, h):
        self.clip(Rectangle2DDouble(x, y, w, h))

    def set_clip(self, s, y=None, w=None, h=None):
        if y is not None:
            s = Rectangle2DDouble(s, y, w, h)
        if s is None:
            self.clipdev = None
            return
        dev = skia.Path()
        s.path().transform(self.m, dev)
        self.clipdev = dev

    def get_clip(self):
        if self.clipdev is None:
            return None
        inv = skia.Matrix()
        if not self.m.invert(inv):
            return None
        p = skia.Path()
        self.clipdev.transform(inv, p)
        return PathShape(p)

    def get_clip_bounds(self):
        c = self.get_clip()
        return c.get_bounds() if c is not None else None

    def hit_clip(self, x, y, w, h):
        return True

    # ---------------------------------------------------------------- applying state
    def _begin(self):
        cv = self._cv
        st = self._st
        cd = self.clipdev
        if st.clip is not cd:
            cv.restoreToCount(st.base)
            if cd is not None:
                cv.save()
                cv.resetMatrix()
                cv.clipPath(cd, skia.ClipOp.kIntersect, True)
            st.clip = cd
            st.mtok = None
        tok = self._mtok
        if tok is None or st.mtok is not tok:
            if tok is None:
                tok = self._mtok = object()
            cv.setMatrix(self.m)
            st.mtok = tok
        if self._owner is not None:
            self._owner._dirty()
        return cv

    def _fill_paint(self):
        comp = self.comp
        if self.paint is not None:
            return skia.Paint(AntiAlias=True, Shader=self.paint.shader(comp.alpha), BlendMode=comp.mode)
        st = self._st
        p = st.solid
        c = self.color._argb
        a = comp.alpha
        if a < 1.0:
            c = (int(((c >> 24) & 255) * a + 0.5) << 24) | (c & 0xFFFFFF)
        if st.fc != c:
            p.setColor(c)
            st.fc = c
        if st.fm is not comp.mode:
            p.setBlendMode(comp.mode)
            st.fm = comp.mode
        return p

    def _stroke_paint(self):
        comp = self.comp
        base = self.stroke.skpaint()
        if self.paint is not None:
            p = skia.Paint(base)
            p.setShader(self.paint.shader(comp.alpha))
            p.setBlendMode(comp.mode)
            return p
        c = self.color._argb
        a = comp.alpha
        if a < 1.0:
            c = (int(((c >> 24) & 255) * a + 0.5) << 24) | (c & 0xFFFFFF)
        base.setColor(c)
        base.setBlendMode(comp.mode)
        return base

    # ---------------------------------------------------------------- shapes
    def fill(self, s):
        self._begin().drawPath(s.path(), self._fill_paint())

    def draw(self, s):
        self._begin().drawPath(s.path(), self._stroke_paint())

    def fill_rect(self, x, y, w, h):
        if w <= 0 or h <= 0:
            return
        st = self._st
        # fast path: same clip and matrix already on the canvas, solid colour
        if st.clip is self.clipdev and self._mtok is not None and st.mtok is self._mtok and self.paint is None \
                and self._owner is None:
            comp = self.comp
            c = self.color._argb
            if comp.alpha < 1.0:
                c = (int(((c >> 24) & 255) * comp.alpha + 0.5) << 24) | (c & 0xFFFFFF)
            p = st.solid
            if st.fc != c:
                p.setColor(c)
                st.fc = c
            if st.fm is not comp.mode:
                p.setBlendMode(comp.mode)
                st.fm = comp.mode
            self._cv.drawRect(skia.Rect.MakeXYWH(x, y, w, h), p)
            return
        self._begin().drawRect(skia.Rect.MakeXYWH(x, y, w, h), self._fill_paint())

    def clear_rect(self, x, y, w, h):
        p = skia.Paint(Color=self.bg._argb, BlendMode=skia.BlendMode.kSrc)
        self._begin().drawRect(skia.Rect.MakeXYWH(x, y, w, h), p)

    def draw_rect(self, x, y, w, h):
        if w < 0 or h < 0:
            return
        p = self._stroke_paint()
        self._begin().drawRect(skia.Rect.MakeXYWH(x, y, w, h), p)

    def fill_oval(self, x, y, w, h):
        self._begin().drawOval(skia.Rect.MakeXYWH(x, y, w, h), self._fill_paint())

    def draw_oval(self, x, y, w, h):
        self._begin().drawOval(skia.Rect.MakeXYWH(x, y, w, h), self._stroke_paint())

    def fill_round_rect(self, x, y, w, h, aw, ah):
        self._begin().drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), aw / 2.0, ah / 2.0), self._fill_paint())

    def draw_round_rect(self, x, y, w, h, aw, ah):
        self._begin().drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), aw / 2.0, ah / 2.0), self._stroke_paint())

    def fill_arc(self, x, y, w, h, start, extent):
        self.fill(Arc2DDouble(x, y, w, h, start, extent, Arc2D.PIE))

    def draw_arc(self, x, y, w, h, start, extent):
        self.draw(Arc2DDouble(x, y, w, h, start, extent, Arc2D.OPEN))

    def draw_line(self, x1, y1, x2, y2):
        p = self._stroke_paint()
        self._begin().drawLine(x1, y1, x2, y2, p)

    def fill_polygon(self, xs, ys=None, n=None):
        poly = xs if isinstance(xs, Polygon) else Polygon(xs, ys, n)
        self.fill(poly)

    def draw_polygon(self, xs, ys=None, n=None):
        poly = xs if isinstance(xs, Polygon) else Polygon(xs, ys, n)
        self._begin().drawPath(poly.path(), self._stroke_paint())

    def draw_polyline(self, xs, ys, n):
        if n < 2:
            return
        p = skia.Path()
        p.moveTo(xs[0], ys[0])
        for i in range(1, n):
            p.lineTo(xs[i], ys[i])
        self._begin().drawPath(p, self._stroke_paint())

    # ---------------------------------------------------------------- text
    def draw_string(self, s, x, y):
        if not s:
            return
        s = str(s)
        font = self.get_font()
        cv = self._begin()
        p = self._fill_paint()
        runs = _runs(font, s)
        if len(runs) == 1:
            cv.drawString(s, float(x), float(y), runs[0][0], p)
            return
        xx = float(x)
        for f, t in runs:
            cv.drawString(t, xx, float(y), f, p)
            xx += f.measureText(t)

    def draw_chars(self, data, off, n, x, y):
        self.draw_string("".join(data[off:off + n]), x, y)

    # ---------------------------------------------------------------- images
    def draw_image(self, img, *a):
        if img is None:
            return True
        sk = img.snapshot() if isinstance(img, BufferedImage) else img
        cv = None
        if a and isinstance(a[0], AffineTransform):
            at = a[0]
            cv = self._begin()
            m = mcopy(self.m)
            m.preConcat(at.m)
            cv.setMatrix(m)
            self._st.mtok = None
            cv.drawImage(sk, 0, 0, _SAMPLING, self._image_paint())
            return True
        nums = [x for x in a if isinstance(x, (int, float)) and not isinstance(x, bool)]
        bgcolor = next((x for x in a if isinstance(x, Color)), None)
        cv = self._begin()
        if len(nums) >= 8:   # dst x1,y1,x2,y2, src x1,y1,x2,y2
            dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2 = nums[:8]
            cv.drawImageRect(sk, skia.Rect.MakeLTRB(sx1, sy1, sx2, sy2), skia.Rect.MakeLTRB(dx1, dy1, dx2, dy2), _SAMPLING,
                             self._image_paint())
        elif len(nums) >= 4:
            x, y, w, h = nums[:4]
            r = skia.Rect.MakeXYWH(x, y, w, h)
            if bgcolor is not None:
                cv.drawRect(r, skia.Paint(Color=bgcolor._argb))
            cv.drawImageRect(sk, r, _SAMPLING, self._image_paint())
        else:
            x, y = nums[:2]
            cv.drawImage(sk, float(x), float(y), _SAMPLING, self._image_paint())
        return True

    def _image_paint(self):
        p = _IMG
        a = self.comp.alpha
        p.setColor((int(255 * a + 0.5) << 24) | 0xFFFFFF)
        p.setBlendMode(self.comp.mode)
        return p


Graphics = Graphics2D


class GraphicsEnvironment:
    @staticmethod
    def is_headless():
        return os.environ.get("SDL_VIDEODRIVER") == "dummy" or bool(os.environ.get("LINDEFENSE_HEADLESS"))

    @staticmethod
    def get_local_graphics_environment():
        return GraphicsEnvironment()

    def register_font(self, f):
        return True


# ====================================================================== input events (filled in by the pygame host)
class KeyEvent:
    """java.awt.event.KeyEvent with Java virtual-key codes; the app translates pygame key events into these."""
    KEY_PRESSED, KEY_RELEASED, KEY_TYPED = 401, 402, 400
    CHAR_UNDEFINED = "￿"
    VK_ENTER, VK_BACK_SPACE, VK_TAB, VK_SHIFT, VK_CONTROL, VK_ALT, VK_ESCAPE, VK_SPACE = 10, 8, 9, 16, 17, 18, 27, 32
    VK_PAGE_UP, VK_PAGE_DOWN, VK_END, VK_HOME, VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 33, 34, 35, 36, 37, 38, 39, 40
    VK_COMMA, VK_MINUS, VK_PERIOD, VK_SLASH, VK_SEMICOLON, VK_EQUALS = 44, 45, 46, 47, 59, 61
    VK_OPEN_BRACKET, VK_BACK_SLASH, VK_CLOSE_BRACKET, VK_DELETE, VK_BACK_QUOTE, VK_QUOTE, VK_META = 91, 92, 93, 127, 192, 222, 157
    VK_ADD, VK_SUBTRACT, VK_PLUS = 107, 109, 521

    def __init__(self, source=None, id_=401, when=0, modifiers=0, code=0, char=None):
        self.source, self.id, self.when, self.modifiers = source, id_, when, modifiers
        self.code = code
        self.char = char if char is not None else KeyEvent.CHAR_UNDEFINED

    def get_key_code(self):
        return self.code

    def get_key_char(self):
        return self.char

    def get_id(self):
        return self.id

    def get_modifiers(self):
        return self.modifiers

    get_modifiers_ex = get_modifiers

    def is_shift_down(self):
        return bool(self.modifiers & 1)

    def is_control_down(self):
        return bool(self.modifiers & 2)

    def is_meta_down(self):
        return bool(self.modifiers & 4)

    def is_alt_down(self):
        return bool(self.modifiers & 8)

    def consume(self):
        pass


for _i in range(10):
    setattr(KeyEvent, "VK_%d" % _i, 48 + _i)
    setattr(KeyEvent, "VK_NUMPAD%d" % _i, 96 + _i)
for _i in range(26):
    setattr(KeyEvent, "VK_" + chr(65 + _i), 65 + _i)
for _i in range(1, 13):
    setattr(KeyEvent, "VK_F%d" % _i, 111 + _i)


class MouseEvent:
    MOUSE_PRESSED, MOUSE_RELEASED, MOUSE_MOVED, MOUSE_DRAGGED, MOUSE_CLICKED = 501, 502, 503, 506, 500
    BUTTON1, BUTTON2, BUTTON3 = 1, 2, 3

    def __init__(self, source=None, id_=501, when=0, modifiers=0, x=0, y=0, clicks=1, popup=False, button=1):
        self.source, self.id, self.when, self.modifiers = source, id_, when, modifiers
        self.x, self.y, self.clicks, self.button = x, y, clicks, button

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_button(self):
        return self.button

    def get_click_count(self):
        return self.clicks

    def is_control_down(self):
        return bool(self.modifiers & 2)

    def is_shift_down(self):
        return bool(self.modifiers & 1)


class FontRenderContext:
    def __init__(self, *a):
        pass


class Timer:
    """javax.swing.Timer stand-in (the pygame host drives frames itself)."""

    def __init__(self, delay=0, listener=None):
        self.delay, self.listener, self._running = delay, listener, False

    ACTIVE = []

    def start(self):
        self._running = True
        self._next = None
        if self not in Timer.ACTIVE:
            Timer.ACTIVE.append(self)

    def stop(self):
        self._running = False
        if self in Timer.ACTIVE:
            Timer.ACTIVE.remove(self)

    @staticmethod
    def fire_due(now):
        """Runs the listeners of started timers whose delay has elapsed (called by GraphicsProgram's loop)."""
        for t in list(Timer.ACTIVE):
            if t._next is None:
                t._next = now + t.delay / 1000.0
            if now >= t._next and t.listener is not None:
                t._next = now + max(0.001, t.delay / 1000.0)
                t.listener(None)

    def set_delay(self, d):
        self.delay = d

    def get_delay(self):
        return self.delay

    def set_coalesce(self, c):
        pass

    def is_running(self):
        return self._running


class FileInputStream:
    """java.io.FileInputStream stand-in: only carries the path (Font.createFont reads the file itself)."""

    def __init__(self, f):
        self.path = f if isinstance(f, str) else getattr(f, "path", str(f))
        if not os.path.isfile(self.path):
            raise OSError("not found: %s" % self.path)
        self.name = self.path

    def close(self):
        pass

    def read(self, *a):
        with open(self.path, "rb") as fh:
            return fh.read()


InputStream = FileInputStream


from lindefense.ui.jrt import FileWriter, PrintWriter, StringWriter, Preferences  # noqa: E402,F401  (re-exported to the ported UI)
