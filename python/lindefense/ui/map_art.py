"""Lindefense MapArt (ported from src/lindefense/ui/MapArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.map.game_map import GameMap
from lindefense.map.maps import AbandonedDataCenter
from lindefense.map.maps import HallucinationCanyon
from lindefense.map.maps import LegacyMonolith
from lindefense.map.maps import NeuralNetwork
from lindefense.map.maps import SiliconCircuit
from lindefense.map.maps import SiliconValley
from lindefense.map.maps import SingularityCore
from lindefense.sim.vec import Vec


class MapArt(GObject):
    """Map art (background, set dressing, track) as one ACM GObject, in a calm, minimal style: a quiet themed ground,
the few props that are gameplay (obstacles, pads, nodes, hazard sections, portals) drawn flat with thin outlines, and
a clean flat track with a subtle edge and sparse direction chevrons. Only functional labels are drawn (route names
that banners refer to, floor numbers, hazard kinds, capacitor pads).

The art is painted once into a bitmap at the resolution the object is actually shown at (canvas scale x HiDPI scale)
and every frame only blits that bitmap. The bitmap is re-rendered when the window is resized and shared through a
small cache, so the map-select thumbnails and the playfield cost nothing per frame. Everything is deterministic
(seeded per map) and only reads the map's static geometry: routes, obstacles, pads, nodes. Set dressing is placed only
where it keeps clear of the track and obstacles so it never hides gameplay.

Pulses is the small live layer: particles over an active malfunctioning section (Abandoned Data Center)."""
    class Painter:
        def __init__(self, map_, g, bg, accent, track):
            self.map = None
            self.g = None
            self.bg = None
            self.accent = None
            self.f_track = None
            self.rnd = None
            self.map = map_
            self.g = g
            self.bg = bg
            self.accent = accent
            self.f_track = track
            self.rnd = _j.Random(_j.hash_code(map_.get_name()))
        def draw_generic(self):
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            self.grid(100, self.accent, 10)
            self.track(0.55)
        # ------------------------------------------------------------------ drawing primitives
        def fill(self, s, c):
            self.g.set_color(c)
            self.g.fill(s)
        def draw(self, s, c, w):
            self.g.set_stroke(MapArt.round(w))
            self.g.set_color(c)
            self.g.draw(s)
        def text(self, s, x, y, f, c):
            self.g.set_font(f)
            self.g.set_color(c)
            self.g.draw_string(s, x, y)
        def text_width(self, s, f):
            self.g.set_font(f)
            return self.g.get_font_metrics().string_width(s)
        def label(self, s, cx, cy, c):
            """A functional map label: small, quiet capitals centred on (cx, cy) with a soft dark backing so it reads over
the ground. Only labels the player needs (names that banners refer to, hazard kinds, pads) are drawn."""
            self.label_at(s, cx, cy, c, True)
        def label_at(self, s, x, cy, c, centered):
            f = MapArt.LABEL_FONT
            u = s.upper()
            tw = self.text_width(u, f)
            pw = (tw + 10)
            ph = 15.0
            x0 = ((x - (pw / 2)) if centered else x)
            x0 = _j.dmax(4, _j.dmin(((MapArt.W - pw) - 4), x0))
            y0 = _j.dmax(4, _j.dmin(((MapArt.H - ph) - 4), (cy - (ph / 2))))
            self.fill(RoundRectangle2D.Double(x0, y0, pw, ph, 4, 4), Color(4, 7, 14, 150))
            self.text(u, (x0 + 5), (((y0 + (ph / 2)) + (self.g.get_font_metrics().get_ascent() / 2.0)) - 1), f, MapArt.alpha(Cyber.lerp(c, Color.WHITE, 0.25), 200))
        def label_right(self, s, rx, cy, c):
            """A label whose right edge sits at rx (kept clear of something to its right)."""
            self.label_at(s, ((rx - self.text_width(s.upper(), MapArt.LABEL_FONT)) - 10), cy, c, False)
        def clear(self, x, y, r):
            """True if a disc of radius r at (x, y) keeps clear of every track, obstacle and the world edge."""
            if (((x < (r + 4)) or (y < (r + 4))) or (x > ((MapArt.W - r) - 4))) or (y > ((MapArt.H - r) - 4)):
                return False
            p = Vec(x, y)
            for route in self.map.get_routes():
                if route.distance_to_point(p) < ((MapArt.HW + r) + 7):
                    return False
            for o in self.map.get_obstacles():
                if o.contains(p, (r + 6)):
                    return False
            return self.extra_clear(x, y, r)
        def extra_clear(self, x, y, r):
            """Per-map exclusions (pads, hubs, arena)."""
            return True
        def grid(self, step, c, a):
            """A single quiet grid of thin lines."""
            p = Path2D.Double()
            x = step
            while x < MapArt.W:
                p.append(Line2D.Double(x, 0, x, MapArt.H), False)
                x += step
            y = step
            while y < MapArt.H:
                p.append(Line2D.Double(0, y, MapArt.W, y), False)
                y += step
            self.draw(p, MapArt.alpha(c, a), 1)
        def dot_grid(self, step, c, r):
            p = Path2D.Double()
            y = (step / 2)
            while y < MapArt.H:
                x = (step / 2)
                while x < MapArt.W:
                    p.append(Ellipse2D.Double((x - r), (y - r), (2 * r), (2 * r)), False)
                    x += step
                y += step
            self.fill(p, c)
        def soft_light(self, cx, cy, r, c):
            """A very soft, wide radial light (at most one or two per map)."""
            self.g.set_paint(RadialGradientPaint(Point2D.Double(cx, cy), r, [0.0, 1.0], [c, MapArt.alpha(c, 0)]))
            self.g.fill(Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r)))
        def vignette(self, a):
            self.g.set_paint(RadialGradientPaint(Point2D.Double((MapArt.W / 2), (MapArt.H / 2)), (math.hypot(MapArt.W, MapArt.H) / 2), [0.0, 0.6, 1.0], [Color(0, 0, 0, 0), Color(0, 0, 0, _j.idiv(a, 5)), Color(0, 0, 0, a)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
        def stars(self, region, n, tint):
            old = self.g.get_clip()
            if region is not None:
                self.g.clip(region)
            b = (region.get_bounds2_d() if (region is not None) else Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            dots = Path2D.Double()
            for i in range(n):
                x = (b.get_x() + (self.rnd.next_double() * b.get_width()))
                y = (b.get_y() + (self.rnd.next_double() * b.get_height()))
                r = (0.5 + (self.rnd.next_double() * 0.7))
                dots.append(Ellipse2D.Double((x - r), (y - r), (2 * r), (2 * r)), False)
            self.fill(dots, MapArt.alpha(Cyber.lerp(Color.WHITE, tint, 0.4), 70))
            self.g.set_clip(old)
        def outlined(self, s, fill, line, w):
            """A flat shape with a thin outline (the prop style)."""
            self.fill(s, fill)
            self.draw(s, line, w)
        # ------------------------------------------------------------------ the track
        def route_path(self, r):
            p = Path2D.Double()
            w = r.get_waypoints()
            p.move_to(w[0].x, w[0].y)
            for i in range(1, len(w)):
                p.line_to(w[i].x, w[i].y)
            return p
        def track_area(self, half_width):
            st = BasicStroke((2 * half_width), BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
            a = Area()
            for r in self.map.get_routes():
                a.add(Area(st.create_stroked_shape(self.route_path(r))))
            return a
        def track(self, darken):
            """The track as a clean flat path: a solid body in the darkened track colour, a soft contact shadow, a thin
lighter edge and small, sparse direction chevrons (one per stretch, never doubled where routes share a road).
darken is how far the body is pulled towards black (0 = pure track colour)."""
            body = self.track_area(MapArt.HW)
            self.g.translate(0, 2)
            self.draw(body, Color(0, 0, 0, 70), 4)
            self.g.translate(0, (-2))
            base = Cyber.lerp(self.f_track, Color.BLACK, darken)
            self.fill(body, base)
            self.draw(body, MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.15), 120), 1.2)
            self.chevrons(MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.35), 64))
        def chevrons(self, c):
            placed = _j.ArrayList()
            cv = Path2D.Double()
            for r in self.map.get_routes():
                d = 90.0
                while d < (r.get_total_length() - 60):
                    p = r.position_at(d)
                    near = False
                    for q in placed:
                        if q.dist(p) < 120:
                            near = True
                            break
                    if near:
                        d += 40
                        continue
                    _j_add(placed, p)
                    dir_ = r.direction_at(d)
                    n = Vec((-dir_.y), dir_.x)
                    cv.move_to(((p.x - (dir_.x * 4)) + (n.x * 6)), ((p.y - (dir_.y * 4)) + (n.y * 6)))
                    cv.line_to((p.x + (dir_.x * 3)), (p.y + (dir_.y * 3)))
                    cv.line_to(((p.x - (dir_.x * 4)) - (n.x * 6)), ((p.y - (dir_.y * 4)) - (n.y * 6)))
                    d += 210
            self.draw(cv, c, 2)
        def sub_path(self, r, from_, to):
            """The stretch of a route between two distances, sampled every 4 px."""
            p = Path2D.Double()
            a = r.position_at(from_)
            p.move_to(a.x, a.y)
            for w in r.get_waypoints():
                d = r.nearest_distance_along(w)
                if (d > (from_ + 0.5)) and (d < (to - 0.5)):
                    p.line_to(w.x, w.y)
            b = r.position_at(to)
            p.line_to(b.x, b.y)
            return p
        def traces(self, count, line, via):
            """Sparse orthogonal / 45-degree circuit traces that keep clear of the track and obstacles, ending in vias."""
            made = 0
            tries = 0
            tr = Path2D.Double()
            vias = Path2D.Double()
            while (made < count) and (tries < (count * 40)):
                x = (_j.jround(((self.rnd.next_double() * MapArt.W) / 10)) * 10)
                y = (_j.jround(((self.rnd.next_double() * MapArt.H) / 10)) * 10)
                if not self.clear(x, y, 6):
                    tries += 1
                    continue
                seg = Path2D.Double()
                seg.move_to(x, y)
                cx = x
                cy = y
                total = 0.0
                dir_ = (self.rnd.next_int(4) * 2)
                segs = (2 + self.rnd.next_int(2))
                for k in range(segs):
                    dx = _j.jround(math.cos(((dir_ * math.pi) / 4)))
                    dy = _j.jround(math.sin(((dir_ * math.pi) / 4)))
                    want = (40 + (self.rnd.next_int(8) * 14))
                    run = 0.0
                    while (run < want) and self.clear((cx + (dx * 4)), (cy + (dy * 4)), 5):
                        cx += (dx * 4)
                        cy += (dy * 4)
                        run += 4
                    if run > 0:
                        seg.line_to(cx, cy)
                        total += run
                    if run < want:
                        break
                    dir_ = _j.imod((dir_ + (1 if self.rnd.next_boolean() else 7)), 8)
                if total < 50:
                    tries += 1
                    continue
                tr.append(seg, False)
                for v in [[x, y], [cx, cy]]:
                    vias.append(Ellipse2D.Double((v[0] - 2.4), (v[1] - 2.4), 4.8, 4.8), False)
                made += 1
                tries += 1
            self.draw(tr, line, 1.4)
            self.fill(vias, via)
    class Silicon(Painter):
        def __init__(self, sc, g):
            self.sc = None
            MapArt.Painter.__init__(self, sc, g, MapArt.c(0x0d2c1a), MapArt.c(0x3bff8a), MapArt.c(0xd4a62a))
            self.gold = MapArt.c(0xd4a62a)
            self.mint = MapArt.c(0x7fd8a8)
            self.sc = sc
        def extra_clear(self, x, y, r):
            for p in self.sc.get_pads():
                if p.dist(Vec(x, y)) < (50 + r):
                    return False
            return True
        def _draw_0(self):
            self.g.set_paint(GradientPaint(0, 0, MapArt.c(0x10331f), MapArt.W, MapArt.H, MapArt.c(0x0a2315)))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.dot_grid(25, MapArt.alpha(self.accent, 12), 0.8)
            self.traces(34, MapArt.alpha(MapArt.c(0x3f8a5c), 110), MapArt.alpha(MapArt.c(0x8a7a44), 140))
            for o in self.map.get_obstacles():
                self.chip(o)
            for p in self.sc.get_pads():
                self.pad(p)
            self.track(0.42)
            for r in self.map.get_routes():
                s = r.get_start()
                self.label_at(r.get_name(), (s.x + 34), ((s.y - MapArt.HW) - 14), self.gold, False)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Silicon, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def chip(self, o):
            l = ('' if (o.label is None) else o.label)
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            if l == 'RAM':
                board = RoundRectangle2D.Double(x, y, w, h, 6, 6)
                self.outlined(board, MapArt.c(0x174a2c), MapArt.alpha(self.mint, 90), 1)
                for i in range(4):
                    cx = ((x + 8) + ((i * (w - 16)) / 4.0))
                    self.fill(Rectangle2D.Double((cx + 2), (y + 10), (((w - 16) / 4.0) - 4), (h - 30)), MapArt.c(0x10151a))
                self.fill(Rectangle2D.Double((x + 6), ((y + h) - 10), (w - 12), 5), MapArt.alpha(self.gold, 140))
                return
            if l == 'I/O':
                shell = RoundRectangle2D.Double(x, y, w, h, 10, 10)
                self.outlined(shell, MapArt.c(0x3a414a), MapArt.alpha(MapArt.c(0xb8c0ca), 120), 1)
                self.fill(RoundRectangle2D.Double((x + 10), (y + 12), (w - 20), (h - 24), 6, 6), MapArt.c(0x0b0e12))
                self.fill(Rectangle2D.Double((x + 18), ((y + (h / 2)) - 2), (w - 36), 4), MapArt.alpha(self.gold, 120))
                return
            in_ = 6.0
            pins = Path2D.Double()
            px = ((x + in_) + 3)
            while px < (((x + w) - in_) - 2):
                pins.append(Rectangle2D.Double(px, (y + 1), 2.5, (in_ - 1)), False)
                pins.append(Rectangle2D.Double(px, ((y + h) - in_), 2.5, (in_ - 1)), False)
                px += 8
            py = ((y + in_) + 3)
            while py < (((y + h) - in_) - 2):
                pins.append(Rectangle2D.Double((x + 1), py, (in_ - 1), 2.5), False)
                pins.append(Rectangle2D.Double(((x + w) - in_), py, (in_ - 1), 2.5), False)
                py += 8
            self.fill(pins, MapArt.alpha(MapArt.c(0xaab2bc), 120))
            body = RoundRectangle2D.Double((x + in_), (y + in_), (w - (2 * in_)), (h - (2 * in_)), 4, 4)
            self.outlined(body, MapArt.c(0x171b21), MapArt.alpha(MapArt.c(0x5a6472), 200), 1)
            die = Rectangle2D.Double((x + 18), (y + 13), (w - 36), (h - 26))
            self.draw(die, MapArt.alpha(MapArt.c(0x00f0ff), 60), 1)
        def pad(self, p):
            r = 40.0
            disc = Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r))
            self.outlined(disc, MapArt.c(0x5a4026), MapArt.alpha(self.mint, 150), 1.4)
            self.fill(Ellipse2D.Double((p.x - 26), (p.y - 26), 52, 52), MapArt.c(0x173e2a))
            plus = Path2D.Double()
            plus.append(Line2D.Double((p.x - 6), p.y, (p.x + 6), p.y), False)
            plus.append(Line2D.Double(p.x, (p.y - 6), p.x, (p.y + 6)), False)
            self.draw(plus, MapArt.alpha(self.mint, 170), 1.6)
            self.label('CAPACITOR PAD', p.x, ((p.y + r) + 14), self.mint)
    class Monolith(Painter):
        def __init__(self, lm, g):
            self.lm = None
            MapArt.Painter.__init__(self, lm, g, MapArt.c(0x161a22), MapArt.c(0x5aa8ff), MapArt.c(0x4f6f8f))
            self.steel = MapArt.c(0x6f7a8c)
            self.amber = MapArt.c(0xffb43b)
            self.lm = lm
        def _draw_0(self):
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), MapArt.c(0x12161d))
            floors = self.lm.get_floors()
            for f in floors:
                self.fill(Rectangle2D.Double(30, f[0], (MapArt.W - 60), (f[1] - f[0])), MapArt.c(0x171c25))
            seams = Path2D.Double()
            x = 200.0
            while x < MapArt.W:
                seams.append(Line2D.Double(x, 0, x, MapArt.H), False)
                x += 200
            self.draw(seams, Color(255, 255, 255, 8), 1)
            for x0 in [4, (MapArt.W - 30)]:
                self.outlined(Rectangle2D.Double(x0, 0, 26, MapArt.H), MapArt.c(0x1e242f), Color(255, 255, 255, 18), 1)
            dividers = Path2D.Double()
            for f in floors:
                dividers.append(Line2D.Double(30, f[0], (MapArt.W - 30), f[0]), False)
            dividers.append(Line2D.Double(30, floors[(len(floors) - 1)][1], (MapArt.W - 30), floors[(len(floors) - 1)][1]), False)
            self.g.set_color(MapArt.alpha(MapArt.c(0xc9a227), 40))
            self.g.set_stroke(BasicStroke(4.0, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [8.0, 8.0], 0.0))
            self.g.draw(dividers)
            n = 0
            for o in self.map.get_obstacles():
                self.blade(o, ((n := n + 1) - 1))
            self.track(0.5)
            for i in range(len(floors)):
                self.label_right(_j.cat('FLOOR ', (i + 1)), 1086, (floors[i][0] + 14), (self.accent if (i < 2) else self.amber))
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Monolith, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def blade(self, o, idx):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = RoundRectangle2D.Double(x, y, w, h, 6, 6)
            self.outlined(body, MapArt.c(0x232935), MapArt.alpha(self.steel, 170), 1)
            bays = Path2D.Double()
            for i in range(6):
                bx = ((x + 24) + (i * 18))
                bays.append(RoundRectangle2D.Double(bx, (y + 10), 12, (h - 30), 2, 2), False)
            self.fill(bays, MapArt.c(0x191e27))
            r = _j.Random(((idx * 31) + 7))
            leds = Path2D.Double()
            for i in range(6):
                if r.next_double() < 0.5:
                    leds.append(Rectangle2D.Double(((x + 28) + (i * 18)), ((y + h) - 15), 4, 2), False)
            self.fill(leds, MapArt.alpha(MapArt.c(0x5ce07a), 120))
            self.fill(RoundRectangle2D.Double((x + 136), (y + 10), 52, (h - 20), 3, 3), MapArt.c(0x191e27))
    class Canyon(Painter):
        def __init__(self, hc, g):
            self.hc = None
            MapArt.Painter.__init__(self, hc, g, MapArt.c(0x1b1430), MapArt.c(0xb48cff), MapArt.c(0x8f7fcf))
            self.violet = MapArt.c(0xb48cff)
            self.pink = MapArt.c(0xff8cf0)
            self.pale = MapArt.c(0xe0c8ff)
            self.hc = hc
        def extra_clear(self, x, y, r):
            p = Vec(x, y)
            if p.dist(self.hc.get_center()) < (70 + r):
                return False
            for n in self.hc.get_nodes():
                if p.dist(n.pos) < (40 + r):
                    return False
            return True
        def _draw_0(self):
            self.g.set_paint(RadialGradientPaint(Point2D.Double(600, 450), 760.0, [0.0, 1.0], [MapArt.c(0x221839), MapArt.c(0x140f24)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.network()
            for o in self.map.get_obstacles():
                self.chasm(o)
            self.track(0.55)
            for n in self.hc.get_nodes():
                self.node(n)
            self.hub(self.hc.get_center())
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Canyon, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def network(self):
            """A faint neural-net constellation: a few dots linked to their nearest neighbours."""
            ns = _j.ArrayList()
            tries = 0
            while (len(ns) < 26) and (tries < 3000):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if self.clear(x, y, 9):
                    _j_add(ns, Vec(x, y))
                tries += 1
            links = Path2D.Double()
            for i in range(len(ns)):
                a = ns[i]
                best = (-1)
                bd = 1e9
                for j in range(len(ns)):
                    if j == i:
                        continue
                    d = a.dist(ns[j])
                    if d < bd:
                        bd = d
                        best = j
                if (best >= 0) and (bd < 260):
                    links.move_to(a.x, a.y)
                    links.line_to(ns[best].x, ns[best].y)
            self.draw(links, MapArt.alpha(self.pale, 26), 1)
            dots = Path2D.Double()
            for n in ns:
                dots.append(Ellipse2D.Double((n.x - 2), (n.y - 2), 4, 4), False)
            self.fill(dots, MapArt.alpha(self.pale, 90))
        def chasm(self, o):
            jag = Path2D.Double()
            step = 16.0
            first = True
            edges = [[o.x, o.y, (o.x + o.w), o.y], [(o.x + o.w), o.y, (o.x + o.w), (o.y + o.h)], [(o.x + o.w), (o.y + o.h), o.x, (o.y + o.h)], [o.x, (o.y + o.h), o.x, o.y]]
            for e in edges:
                len_ = math.hypot((e[2] - e[0]), (e[3] - e[1]))
                nx = ((e[3] - e[1]) / len_)
                ny = ((-(e[2] - e[0])) / len_)
                t = 0.0
                while t < len_:
                    j = ((self.rnd.next_double() - 0.3) * 3.0)
                    px = ((e[0] + (((e[2] - e[0]) * t) / len_)) + (nx * j))
                    py = ((e[1] + (((e[3] - e[1]) * t) / len_)) + (ny * j))
                    if first:
                        jag.move_to(px, py)
                        first = False
                    else:
                        jag.line_to(px, py)
                    t += step
            jag.close_path()
            self.fill(jag, MapArt.c(0x0a0716))
            self.stars(jag, _j.to_int(((o.w * o.h) / 2600)), self.violet)
            self.draw(jag, MapArt.alpha(self.pink, 110), 1.2)
        def node(self, n):
            p = n.pos
            hexa = MapArt.hexagon(p.x, p.y, 30, 0)
            self.outlined(hexa, MapArt.alpha(MapArt.c(0x3a2a66), 200), MapArt.alpha(self.violet, 190), 1.4)
            self.fill(Ellipse2D.Double((p.x - 3), (p.y - 3), 6, 6), MapArt.alpha(self.pale, 160))
        def hub(self, c):
            self.soft_light(c.x, c.y, 110, Color(180, 140, 255, 34))
            disc = Ellipse2D.Double((c.x - 40), (c.y - 40), 80, 80)
            self.outlined(disc, MapArt.c(0x352560), MapArt.alpha(self.pale, 180), 1.6)
            self.draw(Ellipse2D.Double((c.x - 50), (c.y - 50), 100, 100), MapArt.alpha(self.pink, 70), 1)
            self.fill(MapArt.hexagon(c.x, c.y, 8, 30), MapArt.alpha(self.pale, 170))
    class Singularity(Painter):
        def __init__(self, sc, g):
            self.sc = None
            MapArt.Painter.__init__(self, sc, g, MapArt.c(0x07050e), MapArt.c(0x8a6cff), MapArt.c(0x7a5fe0))
            self.violet = MapArt.c(0xb090ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.hot = MapArt.c(0xffc46a)
            self.R = SingularityCore.ARENA_RADIUS
            self.sc = sc
        def extra_clear(self, x, y, r):
            d = Vec(x, y).dist(self.sc.get_center())
            return (d <= ((self.R - 24) - r)) and (d >= (76 + r))
        def _draw_0(self):
            c = self.sc.get_center()
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            self.stars(None, 160, self.violet)
            arena = Ellipse2D.Double((c.x - self.R), (c.y - self.R), (2 * self.R), (2 * self.R))
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), self.R, [0.0, 0.3, 1.0], [MapArt.c(0x2a1648), MapArt.c(0x170d2c), MapArt.c(0x140b26)], MultipleGradientPaint.CycleMethod.NO_CYCLE))
            self.g.fill(arena)
            rings = Path2D.Double()
            r = 80.0
            while r < self.R:
                rings.append(Ellipse2D.Double((c.x - r), (c.y - r), (2 * r), (2 * r)), False)
                r += 80
            self.draw(rings, MapArt.alpha(self.violet, 16), 1)
            self.draw(arena, MapArt.alpha(self.violet, 120), 1.6)
            self.track(0.55)
            for rt in self.map.get_routes():
                self.portal(rt.get_start())
            self.horizon(c)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Singularity, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def portal(self, p):
            hexa = MapArt.hexagon(p.x, p.y, 30, 0)
            self.outlined(hexa, MapArt.alpha(MapArt.c(0x3a1e8a), 170), MapArt.alpha(MapArt.c(0xc0a0ff), 200), 1.4)
        def horizon(self, c):
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), 80.0, [0.0, 0.55, 0.7, 1.0], [Color(0, 0, 0, 255), Color(0, 0, 0, 255), Color(255, 196, 106, 110), Color(255, 120, 200, 0)]))
            self.g.fill(Ellipse2D.Double((c.x - 80), (c.y - 80), 160, 160))
            self.draw(Ellipse2D.Double((c.x - 44), (c.y - 44), 88, 88), MapArt.alpha(self.hot, 170), 1.6)
    class Valley(Painter):
        def __init__(self, sv, g):
            self.sv = None
            MapArt.Painter.__init__(self, sv, g, MapArt.c(0x0b1424), MapArt.c(0x5fd4ff), MapArt.c(0x3fb8ff))
            self.cyan = MapArt.c(0x5fd4ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.glass = MapArt.c(0x9fdcff)
            self.lime = MapArt.c(0x7dffb0)
            self.sv = sv
        def _draw_0(self):
            self.g.set_paint(GradientPaint(0, 0, MapArt.c(0x0e1a30), 0, MapArt.H, MapArt.c(0x09111f)))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.grid(100, self.cyan, 10)
            self.trees()
            self.track(0.68)
            for o in self.map.get_obstacles():
                self.building(o)
            for b in self.sv.get_skybridges():
                self.skybridge(b)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Valley, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def trees(self):
            """A few quiet campus trees (soft green dots)."""
            made = 0
            tries = 0
            dots = Path2D.Double()
            while (made < 12) and (tries < 900):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if not self.clear(x, y, 12):
                    tries += 1
                    continue
                dots.append(Ellipse2D.Double((x - 8), (y - 8), 16, 16), False)
                made += 1
                tries += 1
            self.fill(dots, MapArt.alpha(MapArt.c(0x2f7a55), 90))
        def building(self, o):
            l = ('' if (o.label is None) else o.label)
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            ex = 5.0
            ey = 7.0
            wall = Path2D.Double()
            wall.move_to(x, (y + h))
            wall.line_to((x + w), (y + h))
            wall.line_to((x + w), y)
            wall.line_to(((x + w) + ex), (y + ey))
            wall.line_to(((x + w) + ex), ((y + h) + ey))
            wall.line_to((x + ex), ((y + h) + ey))
            wall.close_path()
            self.fill(wall, MapArt.c(0x08101c))
            roof = Rectangle2D.Double(x, y, w, h)
            tone = MapArt.c(0x172540)
            if 'HQ' in l:
                tone = MapArt.c(0x1b2d4c)
            elif ('SERVER' in l) or ('DATA' in l):
                tone = MapArt.c(0x141d2c)
            elif 'HOLO' in l:
                tone = MapArt.c(0x261a46)
            self.fill(roof, tone)
            if 'HQ' in l:
                self.draw(Rectangle2D.Double((x + 16), (y + 16), (w - 32), (h - 32)), MapArt.alpha(self.glass, 50), 1)
            elif ('SERVER' in l) or ('DATA' in l):
                vents = Path2D.Double()
                fx = (x + 14)
                while fx < ((x + w) - 20):
                    fy = (y + 14)
                    while fy < ((y + h) - 20):
                        vents.append(Ellipse2D.Double(fx, fy, 18, 18), False)
                        fy += 30
                    fx += 30
                self.draw(vents, MapArt.alpha(self.cyan, 36), 1)
            elif 'LAB' in l:
                rr = _j.dmin((w * 0.22), (h * 0.32))
                self.draw(Ellipse2D.Double(((x + (w * 0.7)) - rr), ((y + (h * 0.55)) - rr), (2 * rr), (2 * rr)), MapArt.alpha(self.glass, 70), 1)
            elif ('DEPOT' in l) or ('CHARGING' in l):
                bays = Path2D.Double()
                if h > w:
                    by = (y + 26)
                    while by < ((y + h) - 4):
                        bays.append(Line2D.Double((x + 6), by, ((x + w) - 6), by), False)
                        by += 26
                else:
                    bx = (x + 26)
                    while bx < ((x + w) - 4):
                        bays.append(Line2D.Double(bx, (y + 6), bx, ((y + h) - 6)), False)
                        bx += 26
                self.draw(bays, Color(255, 255, 255, 30), 1)
            elif 'HOLO' in l:
                self.draw(Rectangle2D.Double((x + 8), (y + 8), (w - 16), (h - 16)), MapArt.alpha(self.magenta, 60), 1)
            self.draw(roof, MapArt.alpha(self.cyan, 110), 1)
        def skybridge(self, b):
            r = Rectangle2D.Double(b[0], b[1], b[2], b[3])
            self.outlined(r, Color(150, 210, 255, 34), MapArt.alpha(self.glass, 90), 1)
    class Neural(Painter):
        def __init__(self, nn, g):
            self.nn = None
            MapArt.Painter.__init__(self, nn, g, MapArt.c(0x060818), MapArt.c(0x38e8ff), MapArt.c(0x38e8ff))
            self.cyan = MapArt.c(0x38e8ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.violet = MapArt.c(0x8a5cff)
            self.nn = nn
        def extra_clear(self, x, y, r):
            p = Vec(x, y)
            for v in self.nn.get_neurons():
                if p.dist(v) < (52 + r):
                    return False
            return True
        def _draw_0(self):
            self.g.set_paint(RadialGradientPaint(Point2D.Double(600, 450), 780.0, [0.0, 1.0], [MapArt.c(0x0c1129), MapArt.c(0x05070f)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.weights()
            self.track(0.66)
            i = 0
            while i < len(self.nn.get_neurons()):
                self.neuron(self.nn.get_neurons()[i])
                i += 1
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Neural, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def weights(self):
            """Faint fully-connected weights between consecutive layers: the network diagram behind the pathways."""
            layers = [[NeuralNetwork.IN_A, NeuralNetwork.IN_B], [NeuralNetwork.J1, NeuralNetwork.J2], [NeuralNetwork.H1, NeuralNetwork.H2, NeuralNetwork.H3], [NeuralNetwork.H4, NeuralNetwork.H5], [NeuralNetwork.OUT]]
            w = Path2D.Double()
            li = 0
            while (li + 1) < len(layers):
                for a in layers[li]:
                    for b in layers[(li + 1)]:
                        w.append(Line2D.Double(a.x, a.y, b.x, b.y), False)
                li += 1
            self.draw(w, MapArt.alpha(self.violet, 30), 1)
        def neuron(self, p):
            out = (p is NeuralNetwork.OUT)
            r = (40 if out else 32)
            core = (MapArt.c(0xffd84a) if out else self.magenta)
            disc = Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r))
            self.g.set_paint(RadialGradientPaint(Point2D.Double(p.x, p.y), r, [0.0, 0.3, 1.0], [MapArt.alpha(Cyber.lerp(core, Color.WHITE, 0.5), 220), MapArt.alpha(core, 110), MapArt.alpha(self.violet, 40)]))
            self.g.fill(disc)
            self.draw(disc, MapArt.alpha(self.cyan, 170), 1.4)
    class Graveyard(Painter):
        def __init__(self, dc, g):
            self.dc = None
            MapArt.Painter.__init__(self, dc, g, MapArt.c(0x0b0d10), MapArt.c(0xffb43b), MapArt.c(0x9aa4b0))
            self.amber = MapArt.c(0xffb43b)
            self.cold = MapArt.c(0x7fd6ff)
            self.dc = dc
        def _draw_0(self):
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), MapArt.c(0x0d0f13))
            self.grid(40, Color.WHITE, 7)
            self.cables()
            self.track(0.66)
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_zone(self.dc.get_hazards()[i])
                i += 1
            for o in self.map.get_obstacles():
                l = ('' if (o.label is None) else o.label)
                if l.startswith('COOLING'):
                    self.cooling_plant(o)
                elif l.startswith('UPS'):
                    self.ups(o)
                else:
                    self.rack(o)
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_label(self.dc.get_hazards()[i])
                i += 1
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Graveyard, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def cables(self):
            """A few loose cables on the floor, kept faint."""
            sheath = [MapArt.c(0x6a2a2a), MapArt.c(0x2a3f6a), MapArt.c(0x6a5f2a), MapArt.c(0x2a5a3a)]
            for i in range(7):
                x0 = (self.rnd.next_double() * MapArt.W)
                y0 = (self.rnd.next_double() * MapArt.H)
                x1 = (x0 + ((self.rnd.next_double() - 0.5) * 320))
                y1 = (y0 + ((self.rnd.next_double() - 0.5) * 320))
                cab = Path2D.Double()
                cab.move_to(x0, y0)
                cab.curve_to((x0 + ((self.rnd.next_double() - 0.5) * 220)), (y0 + ((self.rnd.next_double() - 0.5) * 220)), (x1 + ((self.rnd.next_double() - 0.5) * 220)), (y1 + ((self.rnd.next_double() - 0.5) * 220)), x1, y1)
                self.draw(cab, MapArt.alpha(sheath[_j.imod(i, len(sheath))], 120), 2.4)
        def hazard_zone(self, hz):
            """The marked track section: a faint tint inside the track and a thin dashed yellow border."""
            r = self.map.get_routes()[0]
            zone = self.sub_path(r, hz.from_, hz.to)
            band = Area(BasicStroke(((2 * MapArt.HW) + 8), BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND).create_stroked_shape(zone))
            old = self.g.get_clip()
            self.g.clip(self.track_area(MapArt.HW))
            self.fill(band, MapArt.alpha(MapArt.c(hz.rgb), 26))
            self.g.set_clip(old)
            self.g.set_color(MapArt.alpha(Cyber.YELLOW, 150))
            self.g.set_stroke(BasicStroke(1.6, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [6.0, 6.0], 0.0))
            self.g.draw(band)
        def hazard_label(self, hz):
            r = self.map.get_routes()[0]
            mid = r.position_at(((hz.from_ + hz.to) / 2))
            dir_ = r.direction_at(((hz.from_ + hz.to) / 2))
            tag_at = Vec((mid.x - (dir_.y * (MapArt.HW + 26))), (mid.y + (dir_.x * (MapArt.HW + 26))))
            blocked = False
            for o in self.map.get_obstacles():
                if o.contains(tag_at, 14):
                    blocked = True
            if blocked:
                tag_at = Vec((mid.x + (dir_.y * (MapArt.HW + 26))), (mid.y - (dir_.x * (MapArt.HW + 26))))
            tri = Path2D.Double()
            tri.move_to(tag_at.x, (tag_at.y - 8))
            tri.line_to((tag_at.x + 8), (tag_at.y + 6))
            tri.line_to((tag_at.x - 8), (tag_at.y + 6))
            tri.close_path()
            self.fill(tri, MapArt.alpha(Cyber.YELLOW, 200))
            self.text_centered_bold('!', tag_at.x, (tag_at.y + 5))
            self.label(hz.kind, tag_at.x, (tag_at.y + 18), MapArt.c(hz.rgb))
        def text_centered_bold(self, s, cx, y):
            f = Cyber.mono(Font.BOLD, 10)
            self.text(s, (cx - (self.text_width(s, f) / 2.0)), y, f, Color(10, 10, 10))
        def rack(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = Rectangle2D.Double(x, y, w, h)
            self.outlined(body, MapArt.c(0x1b1e23), MapArt.c(0x3c424a), 1)
            units = Path2D.Double()
            leds = Path2D.Double()
            uy = (y + 9)
            while uy < ((y + h) - 4):
                units.append(Line2D.Double((x + 5), uy, ((x + w) - 5), uy), False)
                if self.rnd.next_double() < 0.22:
                    leds.append(Rectangle2D.Double(((x + w) - 10), (uy + 2), 3, 3), False)
                uy += 9
            self.draw(units, Color(0, 0, 0, 120), 1)
            self.fill(leds, MapArt.alpha(self.amber, 130))
        def cooling_plant(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = Rectangle2D.Double(x, y, w, h)
            self.outlined(body, MapArt.c(0x181c22), MapArt.alpha(Cyber.YELLOW, 110), 1.4)
            self.fan((x + (w / 2)), (y + (h * 0.4)), 40)
            self.fan((x + (w / 2)), (y + (h * 0.76)), 26)
        def fan(self, cx, cy, r):
            disc = Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r))
            self.outlined(disc, MapArt.c(0x0e1115), MapArt.alpha(self.cold, 80), 1)
            blades = Path2D.Double()
            for i in range(3):
                a0 = (((i * math.pi) * 2) / 3)
                blades.move_to((cx + ((math.cos(a0) * r) * 0.25)), (cy + ((math.sin(a0) * r) * 0.25)))
                blades.quad_to((cx + ((math.cos((a0 + 0.5)) * r) * 0.7)), (cy + ((math.sin((a0 + 0.5)) * r) * 0.7)), (cx + ((math.cos((a0 + 0.9)) * r) * 0.82)), (cy + ((math.sin((a0 + 0.9)) * r) * 0.82)))
            self.draw(blades, MapArt.alpha(self.cold, 60), 2.4)
        def ups(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            self.outlined(Rectangle2D.Double(x, y, w, h), MapArt.c(0x15181c), MapArt.c(0x3c424a), 1)
            cabs = Path2D.Double()
            for i in range(4):
                cx = ((x + 6) + ((i * (w - 12)) / 4.0))
                cw = (((w - 12) / 4.0) - 6)
                cabs.append(RoundRectangle2D.Double(cx, (y + 8), cw, (h - 16), 4, 4), False)
            self.fill(cabs, MapArt.c(0x1d2127))
            self.fill(Rectangle2D.Double((x + 10), (y + 14), 4, 4), MapArt.alpha(Cyber.RED, 150))
    class Pulses(GObject):
        """The live part of the map art: particles over the active malfunctioning section of the Abandoned Data Center
(sparks, coolant mist or air streaks, so the section's kind reads at a glance). Nothing on the other maps; skipped in
the most crowded fights."""
        def __init__(self, map_):
            self.map = None
            self.col = None
            self.time = 0.0
            GObject.__init__(self)
            self.map = map_
            self.col = Cyber.lerp(MapArt.c(map_.get_track_rgb()), Color.WHITE, 0.6)
        def set_time(self, t):
            self.time = t
        def get_bounds(self):
            return GRectangle(0, 0, MapArt.W, MapArt.H)
        def paint(self, g):
            if (not isinstance(self.map, AbandonedDataCenter)) or (Thick.level() >= Thick.DETAIL_FINE):
                return
            g2 = g.create()
            try:
                g2.set_composite(AlphaComposite.SrcOver)
                self.hazard_fx(g2, self.map)
            finally:
                g2.dispose()
        def hazard_fx(self, g2, dc):
            """Particles over the active hazard section: sparks, coolant mist or air streaks."""
            idx = dc.get_active_hazard()
            if idx < 0:
                return
            h = dc.get_hazards()[idx]
            r = self.map.get_routes()[0]
            c = Color(h.rgb)
            rr = _j.Random(_j.to_long(display_settings.calm((self.time * 12), 0)))   # REDUCED MOTION: a still pattern
            for k in range(10):
                d = (h.from_ + (rr.next_double() * (h.to - h.from_)))
                p = r.position_at(d)
                dir_ = r.direction_at(d)
                off = (((rr.next_double() - 0.5) * 2) * MapArt.HW)
                x = (p.x - (dir_.y * off))
                y = (p.y + (dir_.x * off))
                if h.kind == 'SPARKS':
                    a = ((rr.next_double() * math.pi) * 2)
                    l = (4 + (rr.next_double() * 6))
                    g2.set_color(MapArt.alpha(Cyber.lerp(c, Color.WHITE, 0.5), 200))
                    g2.set_stroke(BasicStroke(1.2))
                    g2.draw(Line2D.Double(x, y, (x + (math.cos(a) * l)), (y + (math.sin(a) * l))))
                elif h.kind == 'COOLANT':
                    s = (5 + (rr.next_double() * 8))
                    g2.set_color(MapArt.alpha(c, 55))
                    g2.fill(Ellipse2D.Double((x - (s / 2)), (y - (s / 2)), s, s))
                else:
                    l = (10 + (rr.next_double() * 12))
                    g2.set_color(MapArt.alpha(c, 120))
                    g2.set_stroke(BasicStroke(1.2, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                    g2.draw(Line2D.Double(x, y, (x - (dir_.x * l)), (y - (dir_.y * l))))
    def _init_0(self, map_):
        self.map = None
        self.dw = 0.0
        self.dh = 0.0
        self.img = None
        self.img_vignette = False
        self._init_1(map_, 0, 0, MapArt.W, MapArt.H)
    def _init_1(self, map_, x, y, dw, dh):
        self.map = None
        self.dw = 0.0
        self.dh = 0.0
        self.img = None
        self.img_vignette = False
        GObject.__init__(self)
        self.img_scale = (-1)
        self.map = map_
        self.dw = dw
        self.dh = dh
        self.set_location(x, y)
    def __init__(self, *a):
        if len(a) == 1:
            return self._init_0(*a)
        elif len(a) == 5:
            return self._init_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    def get_bounds(self):
        return GRectangle(self.get_x(), self.get_y(), self.dw, self.dh)
    def paint(self, g):
        g2 = g.create()
        try:
            t = g2.get_transform()
            q = GraphicsSettings.get().quality()
            s = q.map_scale(((math.sqrt(abs(t.get_determinant())) * self.dw) / MapArt.W))
            if ((self.img is None) or (s != self.img_scale)) or (q.vignette != self.img_vignette):
                self.img = MapArt.bitmap(self.map, s, q.vignette)
                self.img_scale = s
                self.img_vignette = q.vignette
            g2.set_rendering_hint(RenderingHints.KEY_INTERPOLATION, q.interpolation())
            at = AffineTransform()
            at.translate(self.get_x(), self.get_y())
            at.scale((self.dw / self.img.get_width()), (self.dh / self.img.get_height()))
            g2.draw_image(self.img, at, None)
        finally:
            g2.dispose()
    @staticmethod
    def bitmap(map_, s, vignette):
        key = _j.cat(map_.get_name(), '@', s, ('+v' if vignette else ''))
        b = MapArt.CACHE.get(key)
        if b is not None:
            return b
        b = BufferedImage(_j.to_int(float(math.ceil((MapArt.W * s)))), _j.to_int(float(math.ceil((MapArt.H * s)))), BufferedImage.TYPE_INT_RGB)
        g = b.create_graphics()
        try:
            Cyber.quality(g)
            g.scale(s, s)
            g.clip(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            MapArt.render(g, map_)
            if vignette:
                VignetteOverlay.paint(g, MapArt.W, MapArt.H)
        finally:
            g.dispose()
        _j_put(MapArt.CACHE, key, b)
        MapArt.trim_cache(key)
        return b
    @staticmethod
    def trim_cache(keep):
        """Drops least recently used bitmaps (never keep) until the cache fits its pixel budget."""
        total = 0
        for im in _j.values_view(MapArt.CACHE):
            total += (im.get_width() * im.get_height())
        it = _j_iter(_j.entry_set(MapArt.CACHE))
        while (total > MapArt.CACHE_PIXEL_BUDGET) and it.has_next():
            e = it.next()
            if e[0] == keep:
                continue
            total -= (e[1].get_width() * e[1].get_height())
            it.remove()
    @staticmethod
    def cached_pixels():
        """Pixels currently held by the bitmap cache (tests)."""
        total = 0
        for im in _j.values_view(MapArt.CACHE):
            total += (im.get_width() * im.get_height())
        return total
    @staticmethod
    def render(g, map_):
        """Paints the full map art in world coordinates."""
        if isinstance(map_, SiliconCircuit):
            MapArt.Silicon(map_, g).draw()
        elif isinstance(map_, LegacyMonolith):
            MapArt.Monolith(map_, g).draw()
        elif isinstance(map_, HallucinationCanyon):
            MapArt.Canyon(map_, g).draw()
        elif isinstance(map_, SingularityCore):
            MapArt.Singularity(map_, g).draw()
        elif isinstance(map_, SiliconValley):
            MapArt.Valley(map_, g).draw()
        elif isinstance(map_, NeuralNetwork):
            MapArt.Neural(map_, g).draw()
        elif isinstance(map_, AbandonedDataCenter):
            MapArt.Graveyard(map_, g).draw()
        else:
            MapArt.Painter(map_, g, MapArt.c(map_.get_background_rgb()), MapArt.c(0x00f0ff), MapArt.c(map_.get_track_rgb())).draw_generic()
    @staticmethod
    def c(rgb):
        return Color(rgb)
    @staticmethod
    def alpha(c, a):
        return Cyber.alpha(c, a)
    @staticmethod
    def round(w):
        return BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
    @staticmethod
    def hexagon(cx, cy, r, rot_deg):
        p = Path2D.Double()
        for i in range(6):
            a = math.radians((rot_deg + (i * 60)))
            if i == 0:
                p.move_to((cx + (math.cos(a) * r)), (cy + (math.sin(a) * r)))
            else:
                p.line_to((cx + (math.cos(a) * r)), (cy + (math.sin(a) * r)))
        p.close_path()
        return p


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402
from lindefense.ui.vignette_overlay import VignetteOverlay  # noqa: E402

MapArt.serial_version_uid = 1
MapArt.W = GameMap.WIDTH
MapArt.H = GameMap.HEIGHT
MapArt.HW = GameMap.TRACK_HALF_WIDTH
MapArt.CACHE_PIXEL_BUDGET = 48000000
MapArt.CACHE = _j.HashMap(8, 0.75, True)
MapArt.FLICKER = _j.HashMap()
MapArt.LABEL_FONT = Cyber.display(Font.BOLD, 11)
MapArt.Pulses.serial_version_uid = 1
