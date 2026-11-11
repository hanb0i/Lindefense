"""The ACM graphics library (acm.graphics) on top of jawt: a retained scene graph of GObjects painted in order.

Painting follows acm.jar 1.99: GObject.paintObject sets the object's colour on the Graphics, calls paint(g) and
restores the colour; GCompound.paint translates a copy of the Graphics by its location and paints its children in
order. Coordinates are kept as doubles (no integer snapping), so everything stays crisp at Retina scale.

Unchanged-part caching (Python only, same pixels): a compound class with _run_cache = True (tower sprites)
records each run of consecutive children that has not changed for a few frames into a Skia picture once and replays
it while it stays unchanged, instead of walking hundreds of shapes in Python every frame. Every mutator calls
_touch(), which stamps the object and its ancestors; a recorded run is replayed only while none of its objects was
touched since the recording and the Graphics state it starts from (colour, stroke, font, composite, hints, level of
detail) is the same. Only objects whose paint depends on nothing but their own mutator-set state are recorded:
GCompounds, the ACM shapes below and the classes registered with pure_paint(). LINDEFENSE_PAINT_CACHE=0 turns it off.
"""
import math
import os

import skia

from lindefense.ui.jawt import (Arc2D, Arc2DDouble, Color, Font, Graphics2D, Rectangle, font_metrics,
                                reset_canvas_state)


# ====================================================================== unchanged-part caching
class PaintCache:
    """Clocks of the unchanged-part cache. frame advances once per painted frame (a child counts as unchanged after
    STABLE_FRAMES frames without a mutation); epoch advances at the first mutation after a run was recorded, so a
    mutation is always stamped later than every recording made before it."""
    enabled = os.environ.get("LINDEFENSE_PAINT_CACHE", "1") != "0"
    STABLE_FRAMES = 3
    frame = 1
    epoch = 1
    recorded = False

    @staticmethod
    def next_frame():
        """Called once per painted frame by whatever paints the scene (the app, GCanvas)."""
        PaintCache.frame += 1

    @staticmethod
    def globals_():
        """Global state that pure paints read besides their own (see add_global)."""
        return None

    @staticmethod
    def add_global(fn):
        """Registers a callable returning global state that pure paints depend on (the sprites' level of detail)."""
        prev = PaintCache.globals_
        PaintCache.globals_ = staticmethod(lambda: (prev(), fn()))


def _touch(o):
    """o (or something inside it) changed: stamp it and its ancestors with the current frame and epoch. The walk stops
    at the first ancestor already stamped with both, whose own ancestors are therefore stamped too."""
    if PaintCache.recorded:
        PaintCache.epoch += 1
        PaintCache.recorded = False
    e = PaintCache.epoch
    f = PaintCache.frame
    while o is not None and (o._me != e or o._mf != f):
        o._me = e
        o._mf = f
        o = o._parent


def touching(fn):
    """Wraps a mutator of a pure_paint class so it stamps its object (see _touch)."""
    def mutator(self, *a, **k):
        r = fn(self, *a, **k)
        _touch(self)
        return r
    mutator.__name__ = fn.__name__
    mutator.__doc__ = fn.__doc__
    return mutator


_PURE_PAINT = set()   # paint functions that depend only on their object's mutator-set state
_HEAVY = set()        # pure classes worth recording on their own (many draw calls each)
_KIND = {}            # class -> 0 (not recordable), 1 (pure shape), 2 (GCompound)


def pure_paint(cls, heavy=False):
    """Registers a GObject class whose paint(g) depends only on its own state (every change of which goes through a
    mutator that calls _touch), the Graphics state it is given and the PaintCache.globals_."""
    _PURE_PAINT.add(cls.__dict__.get("paint", cls.paint))
    if heavy:
        _HEAVY.add(cls)
    _KIND.clear()


def _kind(t):
    k = 0
    if t.paint_object is GObject.paint_object:
        if issubclass(t, GCompound):
            k = 2 if (t.paint is GCompound.paint or t.paint in _PURE_PAINT) else 0
        elif t.paint in _PURE_PAINT:
            k = 1
    _KIND[t] = k
    return k


def _recordable(o):
    """Whether o's whole subtree can be recorded. Only asked for unchanged objects, so a memo stamped with the
    object's (epoch, frame) stamps stays valid until something in the subtree changes."""
    t = type(o)
    k = _KIND.get(t)
    if k is None:
        k = _kind(t)
    if k != 2:
        return k == 1
    m = o._rec
    if m is not None and m[0] == o._me and m[1] == o._mf:
        return m[2]
    r = True
    for c in o._contents:
        if not _recordable(c):
            r = False
            break
    o._rec = (o._me, o._mf, r)
    return r


_CULL = skia.Rect.MakeLTRB(-1e5, -1e5, 1e5, 1e5)


def _gstate(g):
    return (g.color, g.paint, g.stroke, g.font, g.comp, g.bg, PaintCache.globals_())


class _Run:
    """A recorded run of unchanged children: their picture, the Graphics state it was recorded from and the state
    painting them leaves behind."""
    __slots__ = ("kids", "epoch", "pic", "start", "hints", "end", "end_hints")

    def __init__(self, kids, g):
        self.kids = kids
        self.start = _gstate(g)
        self.hints = dict(g.hints)
        rec = skia.PictureRecorder()
        cv = rec.beginRecording(_CULL)
        r = Graphics2D(cv)
        r.color, r.paint, r.stroke, r.font, r.comp, r.bg = g.color, g.paint, g.stroke, g.font, g.comp, g.bg
        r.hints = dict(g.hints)
        for k in kids:
            k.paint_object(r)
        reset_canvas_state(cv)
        self.pic = rec.finishRecordingAsPicture()
        self.end = (r.color, r.paint, r.stroke, r.font, r.comp, r.bg)
        self.end_hints = r.hints
        self.epoch = PaintCache.epoch
        PaintCache.recorded = True

    def valid(self, kids, g):
        mine = self.kids
        if len(mine) != len(kids):
            return False
        e = self.epoch
        for a, b in zip(mine, kids):
            if a is not b or a._me > e:
                return False
        return g.hints == self.hints and _gstate(g) == self.start

    def replay(self, g):
        g._begin().drawPicture(self.pic)
        g.color, g.paint, g.stroke, g.font, g.comp, g.bg = self.end
        if g.hints != self.end_hints:
            g.hints = dict(self.end_hints)


class GPoint:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        if isinstance(x, GPoint):
            x, y = x.x, x.y
        self.x, self.y = float(x), float(y)

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def set_location(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        self.x, self.y = float(x), float(y)

    def translate(self, dx, dy):
        self.x += dx
        self.y += dy

    def __eq__(self, o):
        return isinstance(o, GPoint) and o.x == self.x and o.y == self.y

    def __repr__(self):
        return "(%s, %s)" % (self.x, self.y)


class GDimension:
    __slots__ = ("width", "height")

    def __init__(self, w=0.0, h=0.0):
        self.width, self.height = float(w), float(h)

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height


class GRectangle:
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x=0.0, y=0.0, w=None, h=None):
        if isinstance(x, GRectangle):
            x, y, w, h = x.x, x.y, x.width, x.height
        elif w is None:
            x, y, w, h = 0.0, 0.0, x, y
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_location(self):
        return GPoint(self.x, self.y)

    def get_size(self):
        return GDimension(self.width, self.height)

    def set_bounds(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)

    def set_location(self, x, y):
        self.x, self.y = float(x), float(y)

    def set_size(self, w, h):
        self.width, self.height = float(w), float(h)

    def translate(self, dx, dy):
        self.x += dx
        self.y += dy

    def grow(self, dx, dy):
        self.x -= dx
        self.y -= dy
        self.width += 2 * dx
        self.height += 2 * dy

    def is_empty(self):
        return self.width <= 0 or self.height <= 0

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def intersects(self, r):
        return self.x < r.x + r.width and r.x < self.x + self.width and self.y < r.y + r.height and r.y < self.y + self.height

    def intersection(self, r):
        x1, y1 = max(self.x, r.x), max(self.y, r.y)
        x2, y2 = min(self.x + self.width, r.x + r.width), min(self.y + self.height, r.y + r.height)
        return GRectangle(x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1))

    def union(self, r):
        if self.is_empty():
            return GRectangle(r)
        if r.is_empty():
            return GRectangle(self)
        x1, y1 = min(self.x, r.x), min(self.y, r.y)
        x2, y2 = max(self.x + self.width, r.x + r.width), max(self.y + self.height, r.y + r.height)
        return GRectangle(x1, y1, x2 - x1, y2 - y1)

    def add(self, r):
        u = self.union(r)
        self.x, self.y, self.width, self.height = u.x, u.y, u.width, u.height

    def __eq__(self, o):
        return isinstance(o, GRectangle) and (o.x, o.y, o.width, o.height) == (self.x, self.y, self.width, self.height)

    def __repr__(self):
        return "[%s, %s, %sx%s]" % (self.x, self.y, self.width, self.height)


# ====================================================================== GObject
class GObject:
    _me = 0       # epoch / frame of the last change to this object or its subtree (see _touch)
    _mf = 0

    def __init__(self):
        self._parent = None
        self._color = None
        self._x = 0.0
        self._y = 0.0
        self._visible = True
        self._mf = PaintCache.frame   # new objects count as changing until they have been left alone a while

    # -- painting
    def paint(self, g):
        raise NotImplementedError

    def paint_object(self, g):
        if not self._visible:
            return
        c = self._color
        if c is not None:
            old = g.color
            g.color = c          # g.set_color(c), inlined: this runs for every object every frame
            g.paint = None
            self.paint(g)
            if old is not None:  # g.set_color(old)
                g.color = old
                g.paint = None
        else:
            self.paint(g)

    # -- location / size
    def set_location(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        x = float(x)
        y = float(y)
        if x != self._x or y != self._y:   # sprites re-set unchanged values every frame: only real changes count
            _touch(self)
        self._x = x
        self._y = y

    def get_location(self):
        return GPoint(self._x, self._y)

    def get_x(self):
        return self._x

    def get_y(self):
        return self._y

    def move(self, dx, dy):
        self.set_location(self._x + dx, self._y + dy)

    def move_polar(self, r, theta):
        a = math.radians(theta)
        self.move(r * math.cos(a), -r * math.sin(a))

    def get_bounds(self):
        raise NotImplementedError

    def get_size(self):
        b = self.get_bounds()
        return GDimension(b.width, b.height)

    def get_awt_bounds(self):
        """acm's protected getAWTBounds, kept fractional (no integer snapping) for Retina-quality output."""
        b = self.get_bounds()
        r = Rectangle.__new__(Rectangle)
        r.x, r.y, r.width, r.height = b.x, b.y, b.width, b.height
        return r

    def get_width(self):
        return self.get_bounds().width

    def get_height(self):
        return self.get_bounds().height

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        return self.get_bounds().contains(x, y)

    # -- z order
    def send_to_front(self):
        p = self._parent
        if p is not None:
            p._reorder(self, len(p._contents) - 1)

    def send_to_back(self):
        p = self._parent
        if p is not None:
            p._reorder(self, 0)

    def send_forward(self):
        p = self._parent
        if p is not None:
            i = p._index(self)
            p._reorder(self, min(len(p._contents) - 1, i + 1))

    def send_backward(self):
        p = self._parent
        if p is not None:
            i = p._index(self)
            p._reorder(self, max(0, i - 1))

    # -- colour / visibility
    def set_color(self, c):
        old = self._color
        self._color = c
        if c is not old and (c is None or old is None or c._argb != old._argb):
            _touch(self)

    def get_color(self):
        return self._color if self._color is not None else Color.BLACK

    def get_object_color(self):
        return self._color

    def set_visible(self, v):
        v = bool(v)
        if v != self._visible:
            self._visible = v
            _touch(self)

    def is_visible(self):
        return self._visible

    def get_parent(self):
        return self._parent

    def set_parent(self, p):
        self._parent = p

    def repaint(self):
        pass

    def add_mouse_listener(self, l):
        pass

    def add_mouse_motion_listener(self, l):
        pass

    def add_action_listener(self, l):
        pass

    def __repr__(self):
        return "%s(%s, %s)" % (type(self).__name__, self._x, self._y)


# ====================================================================== fillable shapes
class _Fillable(GObject):
    def __init__(self):
        GObject.__init__(self)
        self._filled = False
        self._fill_color = None

    def set_filled(self, f):
        self._filled = bool(f)
        _touch(self)

    def is_filled(self):
        return self._filled

    def set_fill_color(self, c):
        old = self._fill_color
        self._fill_color = c
        if c is not old and (c is None or old is None or c._argb != old._argb):
            _touch(self)

    def get_fill_color(self):
        return self._fill_color if self._fill_color is not None else self.get_color()


class GRect(_Fillable):
    def __init__(self, x, y=None, w=None, h=None):
        _Fillable.__init__(self)
        if y is None or w is None:   # (w, h)
            x, y, w, h = 0.0, 0.0, x, y
        self._x, self._y = float(x), float(y)
        self._w, self._h = float(w), float(h)

    def set_size(self, w, h=None):
        if h is None:
            w, h = w.width, w.height
        self._w, self._h = float(w), float(h)
        _touch(self)

    def set_bounds(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self.set_location(x, y)
        self.set_size(w, h)

    def get_bounds(self):
        return GRectangle(self._x, self._y, self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._w *= sx
        self._h *= sy
        _touch(self)

    def paint(self, g):
        if self._filled:
            lc = self._color if self._color is not None else Color.BLACK
            g._fill_draw_rect(self._x, self._y, self._w, self._h,
                              self._fill_color if self._fill_color is not None else lc, lc)
            return
        g.draw_rect(self._x, self._y, self._w, self._h)


class GRoundRect(GRect):
    def __init__(self, x, y=None, w=None, h=None, arc=10.0, arc_h=None):
        if w is None and h is None and y is not None and not isinstance(y, (int, float)):
            pass
        GRect.__init__(self, x, y, w, h)
        self._aw = float(arc)
        self._ah = float(arc if arc_h is None else arc_h)

    def paint(self, g):
        if self._filled:
            g.set_color(self.get_fill_color())
            g.fill_round_rect(self._x, self._y, self._w, self._h, self._aw, self._ah)
            g.set_color(self.get_color())
        g.draw_round_rect(self._x, self._y, self._w, self._h, self._aw, self._ah)


class G3DRect(GRect):
    def __init__(self, x, y=None, w=None, h=None, raised=False):
        GRect.__init__(self, x, y, w, h)
        self._raised = raised

    def set_raised(self, r):
        self._raised = r
        _touch(self)

    def is_raised(self):
        return self._raised


class GOval(_Fillable):
    def __init__(self, x, y=None, w=None, h=None):
        _Fillable.__init__(self)
        if w is None:
            x, y, w, h = 0.0, 0.0, x, y
        self._x, self._y = float(x), float(y)
        self._w, self._h = float(w), float(h)

    def set_size(self, w, h=None):
        if h is None:
            w, h = w.width, w.height
        self._w, self._h = float(w), float(h)
        _touch(self)

    def set_bounds(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self.set_location(x, y)
        self.set_size(w, h)

    def get_bounds(self):
        return GRectangle(self._x, self._y, self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._w *= sx
        self._h *= sy
        _touch(self)

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        rx, ry = self._w / 2.0, self._h / 2.0
        if rx <= 0 or ry <= 0:
            return False
        dx, dy = (x - self._x - rx) / rx, (y - self._y - ry) / ry
        return dx * dx + dy * dy <= 1.0

    def paint(self, g):
        if self._filled:
            lc = self._color if self._color is not None else Color.BLACK
            g._fill_draw_oval(self._x, self._y, self._w, self._h,
                              self._fill_color if self._fill_color is not None else lc, lc)
            return
        g.draw_oval(self._x, self._y, self._w, self._h)


class GArc(_Fillable):
    ARC_TOLERANCE = 2.5

    def __init__(self, a, b, c, d, e=None, f=None):
        _Fillable.__init__(self)
        if e is None:   # (width, height, start, sweep)
            x, y, w, h, start, sweep = 0.0, 0.0, a, b, c, d
        else:
            x, y, w, h, start, sweep = a, b, c, d, e, f
        self._x, self._y = float(x), float(y)
        self._fw, self._fh = float(w), float(h)
        self._start, self._sweep = float(start), float(sweep)

    def set_start_angle(self, a):
        self._start = float(a)
        _touch(self)

    def get_start_angle(self):
        return self._start

    def set_sweep_angle(self, a):
        self._sweep = float(a)
        _touch(self)

    def get_sweep_angle(self):
        return self._sweep

    def set_frame_rectangle(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self._x, self._y, self._fw, self._fh = float(x), float(y), float(w), float(h)
        _touch(self)

    def get_frame_rectangle(self):
        return GRectangle(self._x, self._y, self._fw, self._fh)

    def get_start_point(self):
        return self._arc_point(self._start)

    def get_end_point(self):
        return self._arc_point(self._start + self._sweep)

    def _arc_point(self, theta):
        rx, ry = self._fw / 2.0, self._fh / 2.0
        a = math.radians(theta)
        return GPoint(self._x + rx + rx * math.cos(a), self._y + ry - ry * math.sin(a))

    def get_bounds(self):
        return GRectangle(self._x, self._y, self._fw, self._fh)

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._fw *= sx
        self._fh *= sy
        _touch(self)

    def paint(self, g):
        if self._filled:
            g.set_color(self.get_fill_color())
            g.fill(Arc2DDouble(self._x, self._y, self._fw, self._fh, self._start, self._sweep, Arc2D.PIE))
            g.set_color(self.get_color())
            g.draw(Arc2DDouble(self._x, self._y, self._fw, self._fh, self._start, self._sweep, Arc2D.PIE))
        else:
            g.draw(Arc2DDouble(self._x, self._y, self._fw, self._fh, self._start, self._sweep, Arc2D.OPEN))


class GLine(GObject):
    LINE_TOLERANCE = 1.5

    def __init__(self, x0, y0, x1, y1):
        GObject.__init__(self)
        self._x, self._y = float(x0), float(y0)
        self._dx, self._dy = float(x1 - x0), float(y1 - y0)

    def set_start_point(self, x, y):
        ex, ey = self._x + self._dx, self._y + self._dy
        self._x, self._y = float(x), float(y)
        self._dx, self._dy = ex - self._x, ey - self._y
        _touch(self)

    def get_start_point(self):
        return GPoint(self._x, self._y)

    def set_end_point(self, x, y):
        self._dx, self._dy = float(x) - self._x, float(y) - self._y
        _touch(self)

    def get_end_point(self):
        return GPoint(self._x + self._dx, self._y + self._dy)

    def get_bounds(self):
        return GRectangle(min(self._x, self._x + self._dx), min(self._y, self._y + self._dy), abs(self._dx), abs(self._dy))

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._dx *= sx
        self._dy *= sy
        _touch(self)

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        x0, y0, x1, y1 = self._x, self._y, self._x + self._dx, self._y + self._dy
        t = self.LINE_TOLERANCE
        if math.hypot(x - x0, y - y0) < t or math.hypot(x - x1, y - y1) < t:
            return True
        if x < min(x0, x1) - t or x > max(x0, x1) + t or y < min(y0, y1) - t or y > max(y0, y1) + t:
            return False
        if abs(self._dx) + abs(self._dy) < 1e-12:
            return False
        u = ((x - x0) * self._dx + (y - y0) * self._dy) / (self._dx * self._dx + self._dy * self._dy)
        px, py = x0 + u * self._dx, y0 + u * self._dy
        return math.hypot(x - px, y - py) < t

    def paint(self, g):
        g.draw_line(self._x, self._y, self._x + self._dx, self._y + self._dy)


class GPolygon(_Fillable):
    """Vertices are kept relative to the location. The painted path and the Polygon handed to get_polygon()'s callers
    are cached and rebuilt only when a vertex or the location changes (every mutator resets _pc): sprites are made of
    thousands of polygons that rarely change, and rebuilding each one every frame was a large part of frame time."""

    def __init__(self, x=None, y=None):
        _Fillable.__init__(self)
        self._vx, self._vy = [], []
        self._cx = self._cy = 0.0
        self._pc = None   # (x, y, jawt Polygon with its cached path, PathShape) for the current vertices
        if isinstance(x, (list, tuple)):
            for p in x:
                self.add_vertex(p.x, p.y)
        elif x is not None:
            self._x, self._y = float(x), float(y)

    def add_vertex(self, x, y):
        self._cx, self._cy = float(x), float(y)
        self._vx.append(self._cx)
        self._vy.append(self._cy)
        self._pc = None
        _touch(self)

    def add_edge(self, dx, dy):
        self.add_vertex(self._cx + dx, self._cy + dy)

    def add_polar_edge(self, r, theta):
        a = math.radians(theta)
        self.add_edge(r * math.cos(a), -r * math.sin(a))

    def add_arc(self, w, h, start, sweep):
        rx, ry = w / 2.0, h / 2.0
        a0 = math.radians(start)
        cx, cy = self._cx - rx * math.cos(a0), self._cy + ry * math.sin(a0)
        n = max(2, int(abs(sweep) / 5) + 1)
        for i in range(1, n + 1):
            a = math.radians(start + sweep * i / n)
            self.add_vertex(cx + rx * math.cos(a), cy - ry * math.sin(a))

    def get_current_point(self):
        return GPoint(self._cx, self._cy)

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._vx = [v * sx for v in self._vx]
        self._vy = [v * sy for v in self._vy]
        self._cx *= sx
        self._cy *= sy
        self._pc = None
        _touch(self)

    def rotate(self, theta):
        a = math.radians(theta)
        c, s = math.cos(a), math.sin(a)
        vx, vy = self._vx, self._vy
        self._vx = [x * c + y * s for x, y in zip(vx, vy)]
        self._vy = [y * c - x * s for x, y in zip(vx, vy)]
        self._pc = None
        _touch(self)

    def recenter(self):
        if not self._vx:
            return
        cx = sum(self._vx) / len(self._vx)
        cy = sum(self._vy) / len(self._vy)
        self._vx = [v - cx for v in self._vx]
        self._vy = [v - cy for v in self._vy]
        self._pc = None
        _touch(self)

    def get_vertex_count(self):
        return len(self._vx)

    def _cached(self):
        pc = self._pc
        if pc is not None and pc[0] == self._x and pc[1] == self._y:
            return pc
        from lindefense.ui.jawt import PathShape, Polygon
        poly = Polygon()
        poly.xpoints = [self._x + v for v in self._vx]
        poly.ypoints = [self._y + v for v in self._vy]
        poly.npoints = len(self._vx)
        pc = self._pc = (self._x, self._y, poly, PathShape(poly.path()) if poly.npoints else None)
        return pc

    def get_polygon(self):
        """acm's protected getPolygon: the vertices offset by the location (kept fractional). The result is shared
        until the polygon changes, so callers must only read it (the sprite classes only paint it)."""
        return self._cached()[2]

    def get_bounds(self):
        if not self._vx:
            return GRectangle(self._x, self._y, 0, 0)
        x0, x1, y0, y1 = min(self._vx), max(self._vx), min(self._vy), max(self._vy)
        return GRectangle(self._x + x0, self._y + y0, x1 - x0, y1 - y0)

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        x -= self._x
        y -= self._y
        inside = False
        vx, vy = self._vx, self._vy
        n = len(vx)
        j = n - 1
        for i in range(n):
            if (vy[i] > y) != (vy[j] > y) and x < (vx[j] - vx[i]) * (y - vy[i]) / ((vy[j] - vy[i]) or 1e-12) + vx[i]:
                inside = not inside
            j = i
        return inside

    def paint(self, g):
        if not self._vx:
            return
        s = self._cached()[3]
        if self._filled:
            lc = self._color if self._color is not None else Color.BLACK
            g._fill_draw_path(s._p, self._fill_color if self._fill_color is not None else lc, lc)
            return
        g.draw(s)

    def mark_as_complete(self):
        pass


class GLabel(GObject):
    DEFAULT_FONT = Font("Dialog", 0, 12)

    def __init__(self, text="", x=0.0, y=0.0):
        GObject.__init__(self)
        self._label = "" if text is None else str(text)
        self._font = GLabel.DEFAULT_FONT
        self._x, self._y = float(x), float(y)

    def set_font(self, f):
        if isinstance(f, str):
            f = _decode_font(f)
        self._font = f
        _touch(self)

    def get_font(self):
        return self._font

    def set_label(self, s):
        self._label = "" if s is None else str(s)
        _touch(self)

    def get_label(self):
        return self._label

    def get_font_metrics(self):
        return font_metrics(self._font)

    def get_width(self):
        return float(font_metrics(self._font).string_width(self._label))

    def get_height(self):
        return float(font_metrics(self._font).get_height())

    def get_ascent(self):
        return float(font_metrics(self._font).ascent)

    def get_descent(self):
        return float(font_metrics(self._font).descent)

    def get_bounds(self):
        fm = font_metrics(self._font)
        return GRectangle(self._x, self._y - fm.ascent, fm.string_width(self._label), fm.get_height())

    def paint(self, g):
        g.set_font(self._font)
        g.draw_string(self._label, self._x, self._y)


def _decode_font(s):
    parts = s.split("-")
    name = parts[0] if parts else "Dialog"
    style = 0
    size = 12
    if len(parts) > 1:
        st = parts[1].upper()
        style = (1 if "BOLD" in st else 0) | (2 if "ITALIC" in st else 0)
    if len(parts) > 2:
        try:
            size = int(parts[2])
        except ValueError:
            pass
    return Font(name, style, size)


class GImage(GObject):
    def __init__(self, img, x=0.0, y=0.0):
        GObject.__init__(self)
        if isinstance(img, str):
            from lindefense.ui.jawt import ImageIO
            img = ImageIO.read(img)
        self._img = img
        self._x, self._y = float(x), float(y)
        self._w = float(img.get_width()) if img is not None else 0.0
        self._h = float(img.get_height()) if img is not None else 0.0

    def set_image(self, img):
        self._img = img
        if img is not None:
            self._w, self._h = float(img.get_width()), float(img.get_height())
        _touch(self)

    def get_image(self):
        return self._img

    def set_size(self, w, h=None):
        if h is None:
            w, h = w.width, w.height
        self._w, self._h = float(w), float(h)
        _touch(self)

    def set_bounds(self, x, y=None, w=None, h=None):
        if y is None:
            x, y, w, h = x.x, x.y, x.width, x.height
        self.set_location(x, y)
        self.set_size(w, h)

    def get_bounds(self):
        return GRectangle(self._x, self._y, self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self._w *= sx
        self._h *= sy
        _touch(self)

    def paint(self, g):
        if self._img is not None:
            g.draw_image(self._img, self._x, self._y, self._w, self._h, None)


# ====================================================================== containers
class GCompound(GObject):
    _run_cache = False   # True on sprite classes: record unchanged runs of children (see PaintCache)
    _runs = None         # id(first child) -> _Run, the runs replayed by the last paint
    _rec = None          # (epoch, frame, recordable) memo of _recordable

    def __init__(self):
        GObject.__init__(self)
        self._contents = []
        self._complete = False

    def add(self, obj, x=None, y=None):
        if x is not None:
            if y is None:
                x, y = x.x, x.y
            obj.set_location(x, y)
        old = obj._parent
        if old is not None and old is not self:
            old.remove(obj)
        if obj._parent is self:
            try:
                self._contents.remove(obj)
            except ValueError:
                pass
        obj._parent = self
        self._contents.append(obj)
        _touch(self)

    def remove(self, obj):
        try:
            self._contents.remove(obj)
        except ValueError:
            return
        obj._parent = None
        _touch(self)

    def remove_all(self):
        for o in self._contents:
            o._parent = None
        self._contents = []
        _touch(self)

    def get_element_count(self):
        return len(self._contents)

    def get_element(self, i):
        return self._contents[i]

    def get_element_at(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        lx, ly = x - self._x, y - self._y
        for o in reversed(self._contents):
            if o._visible and o.contains(lx, ly):
                return o
        return None

    def iterator(self, direction=0):
        return iter(list(self._contents))

    def __iter__(self):
        return iter(list(self._contents))

    def _index(self, obj):
        for i, o in enumerate(self._contents):
            if o is obj:
                return i
        return -1

    def _reorder(self, obj, idx):
        i = self._index(obj)
        if i < 0:
            return
        del self._contents[i]
        self._contents.insert(idx, obj)
        _touch(self)

    def paint(self, g):
        g2 = g.create()
        g2.translate(self._x, self._y)
        if self._run_cache and PaintCache.enabled:
            self._paint_runs(g2)
            return
        for o in self._contents:
            if o._visible:
                o.paint_object(g2)

    def _paint_runs(self, g2):
        """paint(), replaying recorded pictures for runs of children unchanged for PaintCache.STABLE_FRAMES frames."""
        f = PaintCache.frame - PaintCache.STABLE_FRAMES
        kind = _KIND.get
        kids = self._contents
        n = len(kids)
        old = self._runs
        new = None
        i = 0
        while i < n:
            c = kids[i]
            i += 1
            if not c._visible:
                continue
            k = kind(type(c))
            if c._mf > f or not (k == 1 or (k != 0 and _recordable(c))):
                c.paint_object(g2)
                continue
            run = [c]
            while i < n:
                d = kids[i]
                if d._visible:
                    k = kind(type(d))
                    if d._mf > f or not (k == 1 or (k != 0 and _recordable(d))):
                        break
                    run.append(d)
                i += 1
            if len(run) == 1 and type(c) not in _HEAVY and not isinstance(c, GCompound):
                c.paint_object(g2)   # a single shape: recording would not save anything
                continue
            r = old.get(id(c)) if old is not None else None
            if r is None or not r.valid(run, g2):
                r = _Run(run, g2)
            r.replay(g2)
            if new is None:
                new = {}
            new[id(c)] = r
        self._runs = new

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        for o in self._contents:
            o.set_location(o._x * sx, o._y * sy)
            if hasattr(o, "scale"):
                o.scale(sx, sy)

    def get_bounds(self):
        r = None
        for o in self._contents:
            if not o._visible:
                continue
            b = o.get_bounds()
            r = GRectangle(b) if r is None else r.union(b)
        if r is None:
            return GRectangle(self._x, self._y, 0, 0)
        r.translate(self._x, self._y)
        return r

    def contains(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        lx, ly = x - self._x, y - self._y
        for o in reversed(self._contents):
            if o._visible and o.contains(lx, ly):
                return True
        return False

    def get_canvas_point(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        c = self
        while isinstance(c, GObject):
            x += c._x
            y += c._y
            c = c._parent
        return GPoint(x, y)

    def get_local_point(self, x, y=None):
        if y is None:
            x, y = x.x, x.y
        c = self
        while isinstance(c, GObject):
            x -= c._x
            y -= c._y
            c = c._parent
        return GPoint(x, y)

    def mark_as_complete(self):
        self._complete = True


class GCanvas(GCompound):
    """The root container the app paints every frame (no own offset)."""

    def __init__(self):
        GCompound.__init__(self)
        self._native_arcs = True
        self._auto_repaint = False
        self._bg = Color.WHITE
        self._w = 0
        self._h = 0

    def set_auto_repaint_flag(self, f):
        self._auto_repaint = f

    def get_auto_repaint_flag(self):
        return self._auto_repaint

    def set_native_arc_flag(self, f):
        self._native_arcs = f

    def get_native_arc_flag(self):
        return self._native_arcs

    def set_background(self, c):
        self._bg = c

    def get_background(self):
        return self._bg

    def repaint(self):
        pass

    def set_size(self, w, h=None):
        if h is None:   # set_size(Dimension)
            w, h = w.width, w.height
        self._w, self._h = int(w), int(h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def paint(self, g):
        """JComponent.paint of an opaque GCanvas: its background, then the scene graph."""
        if self._w > 0 and self._h > 0:
            g.set_color(self._bg)
            g.fill_rect(0, 0, self._w, self._h)
        GCompound.paint(self, g)
        PaintCache.next_frame()


# the ACM shapes paint from their own mutator-set fields only (GImage is left out: its image can be drawn into)
for _c in (GRect, GRoundRect, GOval, GArc, GLine, GPolygon, GLabel):
    pure_paint(_c)


class GMath:
    @staticmethod
    def round(x):
        return int(math.floor(x + 0.5))

    @staticmethod
    def sin_degrees(a):
        return math.sin(math.radians(a))

    @staticmethod
    def cos_degrees(a):
        return math.cos(math.radians(a))

    @staticmethod
    def to_radians(a):
        return math.radians(a)

    @staticmethod
    def to_degrees(a):
        return math.degrees(a)

    @staticmethod
    def distance(x0, y0, x1=None, y1=None):
        if x1 is None:
            return math.hypot(x0, y0)
        return math.hypot(x1 - x0, y1 - y0)


# acm interfaces, for isinstance checks
GFillable = _Fillable
GResizable = (GRect, GOval, GImage)
GScalable = (GRect, GOval, GArc, GLine, GPolygon, GImage, GCompound)
GContainer = GCompound


# ====================================================================== acm.program.GraphicsProgram
class GraphicsProgram:
    """acm.program.GraphicsProgram on pygame + Skia, for the small developer tools (sprite / tower galleries).
    init() then run() as in ACM; pause(ms) paints, handles window events and sleeps; started javax.swing Timers fire
    from the same loop. Closing the window exits."""

    def __init__(self):
        self._root = GCompound()
        self._w, self._h = 754, 492
        self._title = type(self).__name__
        self._bg = Color.WHITE
        self._win = None
        self._surf = None
        self._closed = False

    # -- canvas-ish API
    def set_size(self, w, h):
        self._w, self._h = int(w), int(h)
        if self._win is not None:
            self._win.size = (self._w, self._h)

    def set_title(self, t):
        self._title = t
        if self._win is not None:
            self._win.title = t

    def set_background(self, c):
        self._bg = c

    def add(self, obj, x=None, y=None):
        self._root.add(obj, x, y)

    def remove(self, obj):
        self._root.remove(obj)

    def remove_all(self):
        self._root.remove_all()

    def get_element_at(self, x, y=None):
        return self._root.get_element_at(x, y)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def get_g_canvas(self):
        return self

    def repaint(self):
        pass

    def request_focus_in_window(self):
        pass

    def add_mouse_listeners(self):
        pass

    def add_key_listeners(self):
        pass

    def set_auto_repaint_flag(self, f):
        pass

    def set_native_arc_flag(self, f):
        pass

    def paint(self, g):
        g.set_color(self._bg)
        g.fill_rect(0, 0, self._w, self._h)
        self._root.paint(g)

    # -- lifecycle
    def init(self):
        pass

    def run(self):
        pass

    def start(self, args=None):
        import os
        import time
        import pygame
        self.init()
        if not os.environ.get("SDL_VIDEODRIVER") == "dummy":
            pygame.init()
            self._win = pygame.Window(self._title, (self._w, self._h), allow_high_dpi=True)
        self.run()
        if self._win is None:   # headless (screenshot tools): keep timers running for a while, then return
            end = time.perf_counter() + float(os.environ.get("LINDEFENSE_PROGRAM_SECONDS", "4"))
            while time.perf_counter() < end:
                self.pause(16)
            return
        while not self._closed:
            self.pause(16)

    def exit(self):
        import sys
        sys.exit(0)

    def pause(self, ms):
        import time
        from lindefense.ui.jawt import Timer
        end = time.perf_counter() + ms / 1000.0
        while True:
            self._frame()
            Timer.fire_due(time.perf_counter())
            left = end - time.perf_counter()
            if left <= 0:
                break
            time.sleep(min(left, 0.016))

    def _frame(self):
        if self._win is None:
            return
        import numpy as np  # noqa: F401
        import pygame
        import skia
        from lindefense.ui.jawt import Graphics2D, reset_canvas_state
        for ev in pygame.event.get():
            if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                self._closed = True
                import sys
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.MOUSEBUTTONDOWN and hasattr(self, "mouse_pressed"):
                self.mouse_pressed(ev)
        win = self._win.get_surface()
        pw, ph = win.get_size()
        if self._surf is None or self._surf.width() != pw or self._surf.height() != ph:
            self._surf = skia.Surface.MakeRasterN32Premul(pw, ph)
        cv = self._surf.getCanvas()
        reset_canvas_state(cv)
        g = Graphics2D(cv)
        g.scale(pw / float(self._w), ph / float(self._h))
        self.paint(g)
        reset_canvas_state(cv)
        img = self._surf.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType)
        win.blit(pygame.image.frombuffer(img.tobytes(), (pw, ph), "BGRA"), (0, 0))
        self._win.flip()
