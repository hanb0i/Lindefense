"""The backdrop of the out-of-match screens (title, map select, campaign path and the pop-ups opened over them): a
minimal cyberpunk night scene. A deep blue-black sky with a soft magenta / cyan glow on the horizon, a distant city
drawn as two thin neon outlines, and a perspective floor grid that fades into the distance.

Everything static is painted ONCE into a bitmap at the resolution the backdrop is shown at (the MapArt pattern: the
canvas scale x HiDPI scale, in 1/8 steps, capped) and shared by every screen, so a frame costs one bitmap blit plus a
handful of live accents: a slow scan light gliding across the floor, an occasional data pulse along a grid line or the
horizon, a few drifting motes of light and softly pulsing beacons on the tallest spires (about 45 small draw calls at HIGH).
REDUCED MOTION holds the scene still (no scan light or pulses, motes and beacons steady); QUALITY LOW draws only the
bitmap. The live accents use their own seeded random numbers, never the game's.
"""
import math

from lindefense.ui import jrt as _j
from lindefense.ui.jawt import (AffineTransform, BasicStroke, BufferedImage, Color, Ellipse2D, Line2D,
                                LinearGradientPaint, Path2D, RadialGradientPaint, Rectangle2D)
from lindefense.ui.acm import GObject, GRectangle

W = 1600.0
H = 1000.0
HORIZON = 668.0               # y of the horizon line (the vanishing point is (W / 2, HORIZON))
MAX_SCALE = 2.0               # cap of the bitmap's pixel scale (memory: at most 3200 x 2000 px, about 25 MB)
SKY = [(0.0, 0x03040b), (0.42, 0x050817), (0.62, 0x0a0b22), (HORIZON / H, 0x150c2c)]
FLOOR = [(HORIZON / H, 0x0a0820), (0.80, 0x05060f), (1.0, 0x020308)]
CYAN = Color(0x00f0ff)
MAGENTA = Color(0xff2bd6)
VIOLET = Color(0x8a5cff)
SCAN_PERIOD = 9.0             # s for the scan light to cross the floor
GRID_STEP = 150.0             # spacing of the floor's vanishing lines at the bottom edge
GRID_ROWS = 11
MOTES = {"HIGH": 14, "MEDIUM": 8, "LOW": 0}
CLEAR = (548.0, 1052.0)        # the middle column no mote drifts through (x range)

_CACHE = {}                   # (pixel scale, seed) -> BufferedImage: one entry, shared by every screen


def _c(rgb, a=255):
    return Color((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, a)


def _a(c, a):
    return Color(c.get_red(), c.get_green(), c.get_blue(), max(0, min(255, int(a))))


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def sky_color(y):
    """The sky gradient's colour at logical y (glitch slices over the title blend into it)."""
    f = y / H
    for (f0, c0), (f1, c1) in zip(SKY, SKY[1:]):
        if f <= f1:
            k = 0.0 if f1 <= f0 else max(0.0, (f - f0) / (f1 - f0))
            return Color(*[int(round(((c0 >> s) & 255) + (((c1 >> s) & 255) - ((c0 >> s) & 255)) * k)) for s in (16, 8, 0)])
    return _c(SKY[-1][1])


def row_y(p):
    """Floor depth p (0 = horizon, 1 = bottom edge) -> y: rows bunch up towards the horizon."""
    return HORIZON + (H - HORIZON) * (p ** 2.2)


def _skyline(rnd, low, high, wmin, wmax, center_dip, spires, gaps):
    """One city layer: buildings left to right across the screen, low in the middle (the title and the button stack
    stand there) and taller towards the edges. Each building is (x0, x1, roof points left to right, spire tip or None);
    roofs are flat, set back into a crown, or cut at a slant; a spire always stands on the roof's top run."""
    out = []
    x = -10.0
    while x < W + 10:
        w = wmin + rnd.next_double() * (wmax - wmin)
        d = abs((x + w / 2) - W / 2) / (W / 2)
        reach = low + (high - low) * _smooth(center_dip[0], center_dip[1], d)
        top = HORIZON - reach * (0.4 + 0.6 * rnd.next_double())
        x1 = x + w
        kind = rnd.next_double()
        if kind < 0.22 and w > 30:        # set back: a narrower crown on a wider base
            i = w * (0.18 + 0.12 * rnd.next_double())
            st = 7 + rnd.next_double() * 12
            pts = [(x, top + st), (x + i, top + st), (x + i, top), (x1 - i, top), (x1 - i, top + st), (x1, top + st)]
        elif kind < 0.36:                 # a slanted cut on one corner
            c = min(w * 0.45, 8 + rnd.next_double() * 14)
            pts = [(x, top + c), (x + c, top), (x1, top)] if rnd.next_boolean() else [(x, top), (x1 - c, top), (x1, top + c)]
        else:
            pts = [(x, top), (x1, top)]
        tip = None
        if top < HORIZON - reach * 0.8 and rnd.next_double() < spires:
            tip = ((x + x1) / 2, top - (16 + rnd.next_double() * 24))
        out.append((x, x1, pts, tip))
        x = x1 + (4 + rnd.next_double() * 12 if rnd.next_double() < gaps else 0)
    return out


def _outline(blocks):
    """The skyline's top edge as one open path (walls, roofs, spires), left to right; gaps between buildings drop to
    the horizon."""
    p = Path2D.Double()
    p.move_to(-20, HORIZON)
    end = -20.0
    for x0, x1, pts, tip in blocks:
        if x0 > end + 0.5:
            p.line_to(end, HORIZON)
            p.line_to(x0, HORIZON)
        for k, (px, py) in enumerate(pts):
            p.line_to(px, py)
            if tip is not None and k + 1 < len(pts) and px < tip[0] <= pts[k + 1][0] and py == pts[k + 1][1]:
                tx, ty = tip
                p.line_to(tx - 2.5, py)
                p.line_to(tx - 0.7, py - (py - ty) * 0.3)
                p.line_to(tx - 0.7, ty)
                p.line_to(tx + 0.7, ty)
                p.line_to(tx + 0.7, py - (py - ty) * 0.3)
                p.line_to(tx + 2.5, py)
        end = x1
    p.line_to(end, HORIZON)
    p.line_to(W + 20, HORIZON)
    return p


class Backdrop(GObject):
    """The shared menu backdrop (see the module docstring). Add it first to a screen and call frame(dt) every frame."""

    def __init__(self, seed=11):
        GObject.__init__(self)
        self.t = 0.0
        self.seed = seed
        self.img = None
        self.img_scale = -1.0
        self.rnd = _j.Random(seed)
        r = _j.Random(seed * 31 + 5)
        self.near = _skyline(r, 30, 140, 26, 70, (0.18, 0.62), 0.0, 0.0)
        self.far = _skyline(r, 64, 270, 16, 44, (0.14, 0.72), 0.6, 0.25)
        self.beacons = sorted((tip for _x0, _x1, _pts, tip in self.far if tip is not None), key=lambda b: b[1])
        self.beacons = self.beacons[:5]
        self.motes = [self.new_mote(True) for _ in range(max(MOTES.values()))]
        self.pulse = None              # (kind, lane, age, life) of the data pulse in flight
        self.pulse_wait = 2.5
        self.set_location(0, 0)

    # ---------------------------------------------------------------- live accents
    def new_mote(self, anywhere):
        """A mote of light: [x, y, rise speed, radius, phase, twinkle period, magenta?]. Motes rise on either side of
        the screen, never through the middle column (the title's text and the button stack stand there)."""
        r = self.rnd
        y = 300 + r.next_double() * (H - 300) if anywhere else H + 10
        x = 40 + r.next_double() * (CLEAR[0] - 40)
        if r.next_boolean():
            x = W - x
        return [x, y, 5 + r.next_double() * 9, 1.0 + r.next_double() * 1.3,
                r.next_double() * 6.283, 2.5 + r.next_double() * 3.5, r.next_double() < 0.3]

    def frame(self, dt):
        """Advances the live accents; with REDUCED MOTION the scene holds still."""
        if display_settings.reduced_motion():
            return
        self.t += dt
        for m in self.motes:
            m[1] -= m[2] * dt
            if m[1] < 250:
                m[:] = self.new_mote(False)
        if self.pulse is None:
            self.pulse_wait -= dt
            if self.pulse_wait <= 0:
                kind = 0 if self.rnd.next_double() < 0.65 else 1
                lane = (3 + self.rnd.next_int(7)) * (1 if self.rnd.next_boolean() else -1)
                self.pulse = [kind, lane, 0.0, 2.2 if kind == 0 else 2.8]
        else:
            self.pulse[2] += dt
            if self.pulse[2] >= self.pulse[3]:
                self.pulse = None
                self.pulse_wait = 3.5 + self.rnd.next_double() * 4.0

    def live_count(self):
        """Live accents drawn per frame at the current settings (tests / cost checks)."""
        q = GraphicsSettings.get().quality()
        if q is GraphicsSettings.Quality.LOW:
            return 0
        calm = display_settings.reduced_motion()
        return MOTES[q.name] + len(self.beacons) + (0 if calm else 1 + (self.pulse is not None))

    # ---------------------------------------------------------------- painting
    def get_bounds(self):
        return GRectangle(self.get_x(), self.get_y(), W, H)

    def paint(self, g):
        g2 = g.create()
        try:
            t = g2.get_transform()
            q = GraphicsSettings.get().quality()
            s = min(MAX_SCALE, q.map_scale(math.sqrt(abs(t.get_determinant()))))
            if self.img is None or s != self.img_scale:
                self.img = self.bitmap(s)
                self.img_scale = s
            at = AffineTransform()
            at.translate(self.get_x(), self.get_y())
            at.scale(W / self.img.get_width(), H / self.img.get_height())
            g2.draw_image(self.img, at, None)
            if q is GraphicsSettings.Quality.LOW:
                return
            g2.translate(self.get_x(), self.get_y())
            calm = display_settings.reduced_motion()
            if not calm:
                self.paint_scan(g2)
                self.paint_pulse(g2)
            self.paint_beacons(g2, calm)
            self.paint_motes(g2, MOTES[q.name], calm)
        finally:
            g2.dispose()

    def paint_scan(self, g):
        """A soft light row gliding from the horizon to the bottom edge, brightest mid-floor."""
        p = (self.t / SCAN_PERIOD) % 1.0
        y = row_y(p)
        a = math.sin(math.pi * p) ** 1.5
        if a < 0.02:
            return
        fade = [0.0, 0.3, 0.5, 0.7, 1.0]
        g.set_paint(LinearGradientPaint(0, 0, W, 0, fade, [_a(CYAN, 0), _a(CYAN, 26 * a), _a(CYAN, 40 * a), _a(CYAN, 26 * a), _a(CYAN, 0)]))
        g.fill(Rectangle2D.Double(0, y - 4 - 6 * p, W, 8 + 12 * p))
        g.set_paint(LinearGradientPaint(0, 0, W, 0, fade, [_a(CYAN, 0), _a(CYAN, 110 * a), _a(CYAN, 170 * a), _a(CYAN, 110 * a), _a(CYAN, 0)]))
        g.fill(Rectangle2D.Double(0, y - 0.6, W, 1.2))

    def paint_pulse(self, g):
        """The data pulse: a short bright streak running down one of the floor's grid lines towards the viewer, or along
        the horizon from the middle outwards."""
        if self.pulse is None:
            return
        kind, lane, age, life = self.pulse
        p = age / life
        a = min(1.0, p * 6) * min(1.0, (1 - p) * 4)
        if kind == 0:
            d1 = p ** 1.6
            d0 = max(0.0, p - 0.14) ** 1.6
            tx, bx = W / 2 + lane * GRID_STEP * 0.02, W / 2 + lane * GRID_STEP
            x0, y0 = tx + (bx - tx) * d0, HORIZON + (H - HORIZON) * d0
            x1, y1 = tx + (bx - tx) * d1, HORIZON + (H - HORIZON) * d1
            col = MAGENTA
            w = 1.2 + 1.6 * d1
        else:
            side = 1 if lane > 0 else -1
            d1 = p ** 0.9
            d0 = max(0.0, d1 - 0.18)
            x0, y0 = W / 2 + side * (W / 2) * d0, HORIZON
            x1, y1 = W / 2 + side * (W / 2) * d1, HORIZON
            col = CYAN
            w = 1.6
        if abs(x1 - x0) + abs(y1 - y0) < 0.5:
            return
        g.set_stroke(BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
        g.set_paint(LinearGradientPaint(x0, y0, x1, y1, [0.0, 1.0], [_a(col, 0), _a(col, 230 * a)]))
        g.draw(Line2D.Double(x0, y0, x1, y1))
        g.set_paint(None)
        g.set_color(_a(Color(0xffffff), 200 * a))
        g.fill(Ellipse2D.Double(x1 - w, y1 - w, 2 * w, 2 * w))
        g.set_color(_a(col, 50 * a))
        g.fill(Ellipse2D.Double(x1 - 4 * w, y1 - 4 * w, 8 * w, 8 * w))

    def paint_beacons(self, g, calm):
        for i, (x, y) in enumerate(self.beacons):
            k = 0.55 if calm else 0.5 + 0.5 * math.sin(self.t * 1.3 + i * 1.9)
            g.set_paint(None)
            g.set_color(_a(MAGENTA, 30 + 60 * k))
            g.fill(Ellipse2D.Double(x - 5, y - 5, 10, 10))
            g.set_color(_a(Color(0xffb8f0), 120 + 135 * k))
            g.fill(Ellipse2D.Double(x - 1.6, y - 1.6, 3.2, 3.2))

    def paint_motes(self, g, n, calm):
        g.set_paint(None)
        for m in self.motes[:n]:
            x, y, _vy, r, ph, per, magenta = m
            tw = 0.6 if calm else 0.5 + 0.5 * math.sin(self.t * 6.283 / per + ph)
            x += 0 if calm else 6 * math.sin(self.t * 0.5 + ph)
            fade = _smooth(250, 420, y)
            a = (70 + 150 * tw) * fade
            col = MAGENTA if magenta else CYAN
            g.set_color(_a(col, a * 0.22))
            g.fill(Ellipse2D.Double(x - 3 * r, y - 3 * r, 6 * r, 6 * r))
            g.set_color(_a(Color(0xe8fbff) if not magenta else Color(0xffd6f4), a))
            g.fill(Ellipse2D.Double(x - r * 0.8, y - r * 0.8, r * 1.6, r * 1.6))

    # ---------------------------------------------------------------- the static bitmap
    def bitmap(self, s):
        """The static layers at pixel scale s, shared through a one-entry cache (every screen shows the same scene)."""
        key = (s, self.seed)
        b = _CACHE.get(key)
        if b is not None:
            return b
        b = BufferedImage(int(math.ceil(W * s)), int(math.ceil(H * s)), BufferedImage.TYPE_INT_RGB)
        g = b.create_graphics()
        try:
            Cyber.quality(g)
            g.scale(s, s)
            g.clip(Rectangle2D.Double(0, 0, W, H))
            Backdrop.paint_static(g, self)
        finally:
            g.dispose()
        _CACHE.clear()
        _CACHE[key] = b
        return b

    @staticmethod
    def paint_static(g, d):
        # sky and floor
        g.set_paint(LinearGradientPaint(0, 0, 0, H, [f for f, _ in SKY] + [1.0], [_c(c) for _, c in SKY] + [_c(SKY[-1][1])]))
        g.fill(Rectangle2D.Double(0, 0, W, HORIZON))
        g.set_paint(LinearGradientPaint(0, 0, 0, H, [f for f, _ in FLOOR], [_c(c) for _, c in FLOOR]))
        g.fill(Rectangle2D.Double(0, HORIZON, W, H - HORIZON))
        # the horizon glow: a wide cyan haze and a narrower magenta core, mirrored faintly on the floor
        Backdrop.glow(g, W / 2, HORIZON, 1100, 0.36, _a(CYAN, 30), 0, HORIZON)
        Backdrop.glow(g, W / 2, HORIZON, 700, 0.30, _a(MAGENTA, 84), 0, HORIZON)
        Backdrop.glow(g, W / 2, HORIZON, 820, 0.17, _a(MAGENTA, 54), HORIZON, H)
        # the distant city: two outline layers, the far one violet and taller, the near one cyan
        for blocks, col, fill, core in ((d.far, VIOLET, _c(0x0d0a24, 210), 100), (d.near, CYAN, _c(0x070819, 250), 110)):
            path = _outline(blocks)
            closed = Path2D.Double()
            closed.append(path, False)
            closed.line_to(W + 20, HORIZON + 2)
            closed.line_to(-20, HORIZON + 2)
            closed.close_path()
            g.set_paint(LinearGradientPaint(0, HORIZON - 300, 0, HORIZON, [0.0, 1.0], [fill, _a(fill, 255)]))
            g.fill(closed)
            edge = [0.0, 0.08, 0.5, 0.92, 1.0]
            for w, a in ((5.0, core * 0.16), (2.4, core * 0.32), (1.0, core)):
                g.set_stroke(BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                g.set_paint(LinearGradientPaint(0, 0, W, 0, edge, [_a(col, a * 0.25), _a(col, a), _a(col, a * 0.7), _a(col, a), _a(col, a * 0.25)]))
                g.draw(path)
        # mist on the city's feet: the glow rises over the bases of the buildings
        Backdrop.glow(g, W / 2, HORIZON, 900, 0.07, _a(MAGENTA, 46), 0, HORIZON)
        Backdrop.glow(g, W / 2, HORIZON, 1300, 0.05, _a(CYAN, 22), 0, HORIZON)
        g.set_paint(None)
        for x, y in d.beacons:
            g.set_color(_a(MAGENTA, 140))
            g.fill(Ellipse2D.Double(x - 1.4, y - 1.4, 2.8, 2.8))
        # the floor grid: lines to the vanishing point and rows bunching up towards the horizon, both fading out
        grid = Path2D.Double()
        k = -12
        while k <= 12:
            grid.move_to(W / 2 + k * GRID_STEP * 0.02, HORIZON)
            grid.line_to(W / 2 + k * GRID_STEP, H)
            k += 1
        g.set_stroke(BasicStroke(1.0))
        g.set_paint(LinearGradientPaint(0, HORIZON, 0, H, [0.0, 0.35, 1.0], [_a(VIOLET, 0), _a(VIOLET, 40), _a(MAGENTA, 70)]))
        g.draw(grid)
        rows = Path2D.Double()
        for i in range(1, GRID_ROWS + 1):
            y = row_y(i / float(GRID_ROWS))
            rows.move_to(0, y)
            rows.line_to(W, y)
        g.set_paint(LinearGradientPaint(0, HORIZON, 0, H, [0.0, 0.3, 1.0], [_a(CYAN, 0), _a(CYAN, 26), _a(CYAN, 52)]))
        g.draw(rows)
        # the horizon: a bright line fading out at both ends, with a soft bloom
        fade = [0.0, 0.2, 0.5, 0.8, 1.0]
        for h, a in ((14.0, 16), (5.0, 40), (1.2, 230)):
            g.set_paint(LinearGradientPaint(0, 0, W, 0, fade, [_a(CYAN, 0), _a(CYAN, a * 0.6), _a(Color(0x9ff8ff), a), _a(CYAN, a * 0.6), _a(CYAN, 0)]))
            g.fill(Rectangle2D.Double(0, HORIZON - h / 2, W, h))
        # the corners fall off into the dark (baked here, never blended per frame)
        g.set_paint(RadialGradientPaint(W / 2, H * 0.46, math.hypot(W / 2, H * 0.54), [0.0, 0.55, 1.0],
                                        [Color(0, 0, 0, 0), Color(1, 2, 6, 30), Color(1, 2, 6, 170)]))
        g.fill(Rectangle2D.Double(0, 0, W, H))
        g.set_paint(None)

    @staticmethod
    def glow(g, cx, cy, r, sy, color, y0, y1):
        """A soft elliptical pool of light (radial gradient stretched by sy) filling the band y0..y1."""
        g2 = g.create()
        try:
            g2.clip(Rectangle2D.Double(0, y0, W, y1 - y0))
            g2.translate(cx, cy)
            g2.scale(1.0, sy)
            g2.set_paint(RadialGradientPaint(0, 0, r, [0.0, 0.4, 1.0], [color, _a(color, color.get_alpha() * 0.35), _a(color, 0)]))
            g2.fill(Rectangle2D.Double(-cx, (y0 - cy) / sy, W, (y1 - y0) / sy))
        finally:
            g2.dispose()


class Scanlines(GObject):
    """CRT scanlines over a band (the title wordmark): 1 px dark lines every step px, one fill."""

    def __init__(self, x, y, w, h, step, color):
        GObject.__init__(self)
        self.w = w
        self.h = h
        self.color = color
        p = Path2D.Double()
        yy = 0.0
        while yy < h:
            p.append(Rectangle2D.Double(0, yy, w, 1), False)
            yy += step
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


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402
