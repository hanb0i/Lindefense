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
    """Detailed, futuristic map art (background, set dressing, track) as one ACM GObject.

The art is hundreds of Java2D shapes, so it is painted once into a bitmap at the resolution the object is
actually shown at (canvas scale x HiDPI scale) and every frame only blits that bitmap. The bitmap is re-rendered when
the window is resized and shared through a small cache, so the map-select thumbnails and the playfield cost nothing
per frame. Everything is deterministic (seeded per map) and only reads the map's static geometry: routes, obstacles,
pads, nodes. Set dressing is placed only where it keeps clear of the track and obstacles so it never hides gameplay.

Pulses is the small live layer: glowing data packets streaming along each route."""
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
            self.grid(25, 100, self.accent, 12, 26)
            self.vignette(120)
            self.track(0.55, self.accent)
            self.hud_frame(self.accent, 'SECTOR')
            self.scanlines(10)
        def fill(self, s, c):
            self.g.set_color(c)
            self.g.fill(s)
        def draw(self, s, c, w):
            self.g.set_stroke(MapArt.round(w))
            self.g.set_color(c)
            self.g.draw(s)
        def glow(self, s, c, w, spread):
            """Stroke with a soft glow: a few wide translucent passes under the core line."""
            for i in range(3, 0, -1):
                self.draw(s, MapArt.alpha(c, _j.to_int((c.get_alpha() * (0.09 + (0.05 * (3 - i)))))), (w + (spread * i)))
            self.draw(s, c, w)
        def text(self, s, x, y, f, c):
            self.g.set_font(f)
            self.g.set_color(c)
            self.g.draw_string(s, x, y)
        def _tag_0(self, s, cx, cy, c):
            """A legible map label: bright display-font text on a dark, outlined plate, centred on (cx, cy) and kept inside the
world. Every functional label (building, pad, hub, portal, hazard) goes through this so it reads over any art."""
            self.tag(s, cx, cy, c, True)
        def _tag_1(self, s, cx, cy, c, centered):
            f = Cyber.display(Font.BOLD, 14)
            u = s.upper()
            tw = self.text_width(u, f)
            pw = (tw + 14)
            ph = 18.0
            x = ((cx - (pw / 2)) if centered else cx)
            x = _j.dmax(4, _j.dmin(((MapArt.W - pw) - 4), x))
            y = _j.dmax(4, _j.dmin(((MapArt.H - ph) - 4), (cy - (ph / 2))))
            plate = RoundRectangle2D.Double(x, y, pw, ph, 6, 6)
            self.fill(plate, Color(3, 6, 16, 225))
            self.draw(plate, MapArt.alpha(c, 190), 1)
            self.text(u, (x + 7), (((y + (ph / 2)) + (self.g.get_font_metrics().get_ascent() / 2.0)) - 1), f, Cyber.lerp(c, Color.WHITE, 0.35))
        def tag(self, *a):
            if len(a) == 4:
                return self._tag_0(*a)
            elif len(a) == 5:
                return self._tag_1(*a)
            raise TypeError('no overload for %d args' % len(a))
        def tag_right(self, s, rx, cy, c):
            """A tag whose right edge sits at rx (for labels that must stay clear of something to their right)."""
            self.tag(s, ((rx - self.text_width(s.upper(), Cyber.display(Font.BOLD, 14))) - 14), cy, c, False)
        def text_centered(self, s, cx, y, f, c):
            self.g.set_font(f)
            fm = self.g.get_font_metrics()
            self.text(s, (cx - (fm.string_width(s) / 2.0)), y, f, c)
        def text_width(self, s, f):
            self.g.set_font(f)
            return self.g.get_font_metrics().string_width(s)
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
        def grid(self, minor, major, c, a_minor, a_major):
            mi = Path2D.Double()
            ma = Path2D.Double()
            x = 0.0
            while x <= MapArt.W:
                (ma if (_j.fmod(x, major) == 0) else mi).append(Line2D.Double(x, 0, x, MapArt.H), False)
                x += minor
            y = 0.0
            while y <= MapArt.H:
                (ma if (_j.fmod(y, major) == 0) else mi).append(Line2D.Double(0, y, MapArt.W, y), False)
                y += minor
            self.draw(mi, MapArt.alpha(c, a_minor), 1)
            self.draw(ma, MapArt.alpha(c, a_major), 1)
            cross = Path2D.Double()
            x = major
            while x < MapArt.W:
                y = major
                while y < MapArt.H:
                    cross.append(Line2D.Double((x - 4), y, (x + 4), y), False)
                    cross.append(Line2D.Double(x, (y - 4), x, (y + 4)), False)
                    y += major
                x += major
            self.draw(cross, MapArt.alpha(c, (a_major * 2)), 1.2)
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
        def hex_grid(self, r, c, w):
            p = Path2D.Double()
            hx = (math.sqrt(3) * r)
            vy = (1.5 * r)
            row = 0
            y = 0.0
            while y < (MapArt.H + r):
                x = ((_j.imod(row, 2) * hx) / 2)
                while x < (MapArt.W + hx):
                    p.append(MapArt.hexagon(x, y, r, 30), False)
                    x += hx
                y += vy
                row += 1
            self.draw(p, c, w)
        def glow_blob(self, cx, cy, r, c):
            self.g.set_paint(RadialGradientPaint(Point2D.Double(cx, cy), r, [0.0, 1.0], [c, MapArt.alpha(c, 0)]))
            self.g.fill(Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r)))
        def vignette(self, a):
            self.g.set_paint(RadialGradientPaint(Point2D.Double((MapArt.W / 2), (MapArt.H / 2)), (math.hypot(MapArt.W, MapArt.H) / 2), [0.0, 0.55, 1.0], [Color(0, 0, 0, 0), Color(0, 0, 0, _j.idiv(a, 4)), Color(0, 0, 0, a)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
        def scanlines(self, a):
            p = Path2D.Double()
            y = 1.0
            while y < MapArt.H:
                p.append(Rectangle2D.Double(0, y, MapArt.W, 1), False)
                y += 3
            self.fill(p, Color(0, 0, 0, a))
        def stars(self, region, n, tint):
            old = self.g.get_clip()
            if region is not None:
                self.g.clip(region)
            b = (region.get_bounds2_d() if (region is not None) else Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            for i in range(n):
                x = (b.get_x() + (self.rnd.next_double() * b.get_width()))
                y = (b.get_y() + (self.rnd.next_double() * b.get_height()))
                r = (1.6 if (self.rnd.next_double() < 0.08) else (0.5 + (self.rnd.next_double() * 0.8)))
                c = Cyber.lerp(Color.WHITE, tint, (self.rnd.next_double() * 0.7))
                if r > 1.4:
                    self.glow_blob(x, y, 6, MapArt.alpha(c, 60))
                self.fill(Ellipse2D.Double((x - r), (y - r), (2 * r), (2 * r)), MapArt.alpha(c, (90 + self.rnd.next_int(150))))
            self.g.set_clip(old)
        def hud_frame(self, c, tag):
            """Corner brackets, ruler ticks and coordinate labels around the world edge."""
            br = Path2D.Double()
            m = 6.0
            L = 34.0
            corners = [[m, m, 1, 1], [(MapArt.W - m), m, (-1), 1], [m, (MapArt.H - m), 1, (-1)], [(MapArt.W - m), (MapArt.H - m), (-1), (-1)]]
            for k in corners:
                br.move_to((k[0] + (k[2] * L)), k[1])
                br.line_to(k[0], k[1])
                br.line_to(k[0], (k[1] + (k[3] * L)))
            self.glow(br, MapArt.alpha(c, 170), 2, 2)
            ticks = Path2D.Double()
            x = 50.0
            while x < MapArt.W:
                len_ = (7 if (_j.fmod(x, 100) == 0) else 3.5)
                ticks.append(Line2D.Double(x, 0, x, len_), False)
                ticks.append(Line2D.Double(x, MapArt.H, x, (MapArt.H - len_)), False)
                x += 50
            y = 50.0
            while y < MapArt.H:
                len_ = (7 if (_j.fmod(y, 100) == 0) else 3.5)
                ticks.append(Line2D.Double(0, y, len_, y), False)
                ticks.append(Line2D.Double(MapArt.W, y, (MapArt.W - len_), y), False)
                y += 50
            self.draw(ticks, MapArt.alpha(c, 90), 1)
            if tag is not None:
                self.tag(tag, 14, (MapArt.H - 20), c, False)
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
        def track(self, darken, glow_col):
            """The track as a lit conduit: outer glow and drop shadow, a dark body tinted with the track colour, cross ribs,
inner lane lines, a dashed centre line, direction chevrons and crisp neon edges. darken is how far the
body is pulled towards black (0 = pure track colour)."""
            body = self.track_area(MapArt.HW)
            for i in range(4, 0, -1):
                self.draw(body, MapArt.alpha(glow_col, (10 + ((4 - i) * 6))), (i * 5))
            self.g.translate(0, 3)
            self.draw(body, Color(0, 0, 0, 140), 5)
            self.g.translate(0, (-3))
            base = Cyber.lerp(self.f_track, Color.BLACK, darken)
            self.fill(body, base)
            old = self.g.get_clip()
            self.g.clip(body)
            self.fill(self.track_area((MapArt.HW - 7)), Cyber.lerp(base, self.f_track, 0.16))
            self.g.set_color(MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.2), 42))
            self.g.set_stroke(BasicStroke((2 * MapArt.HW), BasicStroke.CAP_BUTT, BasicStroke.JOIN_MITER, 10.0, [1.6, 9.0], 0.0))
            for r in self.map.get_routes():
                self.g.draw(self.route_path(r))
            self.draw(self.track_area((MapArt.HW - 6)), MapArt.alpha(self.f_track, 80), 1)
            self.g.set_color(MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.55), 95))
            self.g.set_stroke(BasicStroke(1.4, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [12.0, 9.0], 0.0))
            for r in self.map.get_routes():
                self.g.draw(self.route_path(r))
            chev = MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.45), 120)
            for r in self.map.get_routes():
                d = 55.0
                while d < (r.get_total_length() - 30):
                    p = r.position_at(d)
                    dir_ = r.direction_at(d)
                    n = Vec((-dir_.y), dir_.x)
                    cv = Path2D.Double()
                    for k in range(2):
                        o = ((k * 7) - 3)
                        cv.move_to(((p.x + (dir_.x * (o - 5))) + (n.x * 9)), ((p.y + (dir_.y * (o - 5))) + (n.y * 9)))
                        cv.line_to((p.x + (dir_.x * (o + 1))), (p.y + (dir_.y * (o + 1))))
                        cv.line_to(((p.x + (dir_.x * (o - 5))) - (n.x * 9)), ((p.y + (dir_.y * (o - 5))) - (n.y * 9)))
                    self.draw(cv, chev, 1.8)
                    d += 95
            self.g.set_clip(old)
            self.glow(body, MapArt.alpha(Cyber.lerp(self.f_track, Color.WHITE, 0.15), 235), 1.8, 2.2)
            for r in self.map.get_routes():
                w = r.get_waypoints()
                i = 1
                while (i + 1) < len(w):
                    a = w[(i - 1)]
                    b = w[i]
                    cc = w[(i + 1)]
                    d1 = b.sub(a).normalized()
                    d2 = cc.sub(b).normalized()
                    if abs(((d1.x * d2.y) - (d1.y * d2.x))) < 0.5:
                        i += 1
                        continue
                    out = d1.sub(d2).normalized()
                    sx = (b.x + (out.x * (MapArt.HW + 9)))
                    sy = (b.y + (out.y * (MapArt.HW + 9)))
                    self.fill(Ellipse2D.Double((sx - 3), (sy - 3), 6, 6), MapArt.alpha(self.f_track, 200))
                    self.draw(Ellipse2D.Double((sx - 6), (sy - 6), 12, 12), MapArt.alpha(self.f_track, 90), 1)
                    i += 1
        def circuit(self, count, line, shadow, via_ring, via_hole):
            """Random orthogonal / 45-degree circuit traces that keep clear of the track and obstacles, ending in vias."""
            made = 0
            tries = 0
            while (made < count) and (tries < (count * 40)):
                x = (_j.jround(((self.rnd.next_double() * MapArt.W) / 10)) * 10)
                y = (_j.jround(((self.rnd.next_double() * MapArt.H) / 10)) * 10)
                if not self.clear(x, y, 6):
                    tries += 1
                    continue
                tr = Path2D.Double()
                tr.move_to(x, y)
                cx = x
                cy = y
                total = 0.0
                dir_ = (self.rnd.next_int(4) * 2)
                segs = (2 + self.rnd.next_int(3))
                for k in range(segs):
                    dx = _j.jround(math.cos(((dir_ * math.pi) / 4)))
                    dy = _j.jround(math.sin(((dir_ * math.pi) / 4)))
                    want = (30 + (self.rnd.next_int(9) * 14))
                    run = 0.0
                    while (run < want) and self.clear((cx + (dx * 4)), (cy + (dy * 4)), 5):
                        cx += (dx * 4)
                        cy += (dy * 4)
                        run += 4
                    if run > 0:
                        tr.line_to(cx, cy)
                        total += run
                    if run < want:
                        break
                    dir_ = _j.imod((dir_ + (1 if self.rnd.next_boolean() else 7)), 8)
                if total < 40:
                    tries += 1
                    continue
                w = (3 if (self.rnd.next_double() < 0.2) else (2 if (self.rnd.next_double() < 0.5) else 1.2))
                if shadow is not None:
                    self.draw(tr, shadow, (w + 2))
                self.draw(tr, line, w)
                for v in [[x, y], [cx, cy]]:
                    self.fill(Ellipse2D.Double((v[0] - 3.4), (v[1] - 3.4), 6.8, 6.8), via_ring)
                    self.fill(Ellipse2D.Double((v[0] - 1.5), (v[1] - 1.5), 3, 3), via_hole)
                made += 1
                tries += 1
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
        def car(self, cx, cy, ang_deg, body):
            """Top-down little autonomous car."""
            old = self.g.get_transform()
            self.g.translate(cx, cy)
            self.g.rotate(math.radians(ang_deg))
            self.fill(RoundRectangle2D.Double((-11), (-6), 22, 12, 6, 6), Color(0, 0, 0, 110))
            self.fill(RoundRectangle2D.Double((-10), (-5.5), 20, 11, 6, 6), body)
            self.fill(RoundRectangle2D.Double((-4), (-4.2), 9, 8.4, 3, 3), Color(0x0c1626))
            self.fill(RoundRectangle2D.Double((-3), (-3.4), 4, 6.8, 2, 2), Color(120, 200, 255, 120))
            self.fill(Rectangle2D.Double(8.5, (-4.5), 1.6, 2.4), Color(0xeaffff))
            self.fill(Rectangle2D.Double(8.5, 2.1, 1.6, 2.4), Color(0xeaffff))
            self.fill(Rectangle2D.Double((-10), (-4.5), 1.4, 2.4), Cyber.RED)
            self.fill(Rectangle2D.Double((-10), 2.1, 1.4, 2.4), Cyber.RED)
            self.fill(Ellipse2D.Double((-1.5), (-1.5), 3, 3), Cyber.CYAN)
            self.g.set_transform(old)
        def holo(self, x, y, w0, h, c1, c2, l1, l2):
            """Floating holographic ad panel."""
            w = _j.dmax(w0, (self.text_width(l1.upper(), Cyber.display(Font.BOLD, 14)) + 22))
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (w * 0.8), MapArt.alpha(c1, 40))
            self.g.set_paint(GradientPaint(x, y, MapArt.alpha(c1, 110), (x + w), (y + h), MapArt.alpha(c2, 90)))
            self.g.fill(Rectangle2D.Double(x, y, w, h))
            lines = Path2D.Double()
            yy = (y + 2)
            while yy < (y + h):
                lines.append(Line2D.Double(x, yy, (x + w), yy), False)
                yy += 3
            self.draw(lines, Color(255, 255, 255, 22), 1)
            self.glow(Rectangle2D.Double(x, y, w, h), MapArt.alpha(c1, 220), 1.2, 2)
            self.text_centered(l1.upper(), (x + (w / 2)), ((y + (h / 2)) + 4), Cyber.display(Font.BOLD, 14), Color(255, 255, 255, 240))
            beam = Path2D.Double()
            beam.move_to((x + (w * 0.4)), (y + h))
            beam.line_to((x + (w * 0.6)), (y + h))
            beam.line_to(((x + (w / 2)) + 2), ((y + h) + 14))
            beam.line_to(((x + (w / 2)) - 2), ((y + h) + 14))
            beam.close_path()
            self.fill(beam, MapArt.alpha(c1, 60))
        def robot_arm(self, x, y, ang, accent_c):
            """Small robotic arm (top-down) at (x, y)."""
            self.fill(Ellipse2D.Double((x - 9), (y - 9), 18, 18), MapArt.c(0x2a3140))
            self.draw(Ellipse2D.Double((x - 9), (y - 9), 18, 18), MapArt.alpha(accent_c, 180), 1.2)
            a1 = math.radians(ang)
            a2 = (a1 + math.radians(70))
            ex = (x + (math.cos(a1) * 22))
            ey = (y + (math.sin(a1) * 22))
            hx = (ex + (math.cos(a2) * 17))
            hy = (ey + (math.sin(a2) * 17))
            self.draw(Line2D.Double(x, y, ex, ey), MapArt.c(0x0a0d12), 8)
            self.draw(Line2D.Double(x, y, ex, ey), MapArt.c(0xe08a2e), 5.5)
            self.draw(Line2D.Double(ex, ey, hx, hy), MapArt.c(0x0a0d12), 6)
            self.draw(Line2D.Double(ex, ey, hx, hy), MapArt.c(0xf0a040), 4)
            self.fill(Ellipse2D.Double((ex - 4), (ey - 4), 8, 8), MapArt.c(0x3a4250))
            self.fill(Ellipse2D.Double((x - 3.5), (y - 3.5), 7, 7), MapArt.alpha(accent_c, 230))
            ga = (a2 + (math.pi / 2))
            self.draw(Line2D.Double((hx + (math.cos(ga) * 5)), (hy + (math.sin(ga) * 5)), (hx - (math.cos(ga) * 5)), (hy - (math.sin(ga) * 5))), MapArt.c(0xc0c8d0), 2.4)
            self.glow_blob(hx, hy, 8, MapArt.alpha(accent_c, 90))
        def hud_tag(self, s, x, y, c):
            self.tag(s, x, (y + 9), c, False)
        def fan(self, cx, cy, r, c):
            self.fill(Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r)), Color(6, 8, 12))
            self.draw(Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r)), MapArt.alpha(c, 150), 1.6)
            blades = Path2D.Double()
            for i in range(7):
                a0 = (((i * math.pi) * 2) / 7)
                blades.move_to((cx + ((math.cos(a0) * r) * 0.28)), (cy + ((math.sin(a0) * r) * 0.28)))
                blades.quad_to((cx + ((math.cos((a0 + 0.5)) * r) * 0.75)), (cy + ((math.sin((a0 + 0.5)) * r) * 0.75)), (cx + ((math.cos((a0 + 0.95)) * r) * 0.86)), (cy + ((math.sin((a0 + 0.95)) * r) * 0.86)))
            self.draw(blades, MapArt.alpha(c, 110), 3.2)
            grill = Path2D.Double()
            rr = (r * 0.45)
            while rr < r:
                grill.append(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)), False)
                rr += (r * 0.18)
            grill.append(Line2D.Double((cx - r), cy, (cx + r), cy), False)
            grill.append(Line2D.Double(cx, (cy - r), cx, (cy + r)), False)
            self.draw(grill, MapArt.alpha(Color.WHITE, 40), 0.8)
            self.fill(Ellipse2D.Double((cx - (r * 0.26)), (cy - (r * 0.26)), (r * 0.52), (r * 0.52)), Color(0x2a3140))
            self.draw(Ellipse2D.Double((cx - (r * 0.26)), (cy - (r * 0.26)), (r * 0.52), (r * 0.52)), MapArt.alpha(c, 200), 1.2)
    class Silicon(Painter):
        def __init__(self, sc, g):
            self.sc = None
            MapArt.Painter.__init__(self, sc, g, MapArt.c(0x0d2c1a), MapArt.c(0x3bff8a), MapArt.c(0xd4a62a))
            self.gold = MapArt.c(0xd4a62a)
            self.mask = MapArt.c(0x2e6a45)
            self.silk = Color(220, 236, 226, 150)
            self.sc = sc
        def extra_clear(self, x, y, r):
            for p in self.sc.get_pads():
                if p.dist(Vec(x, y)) < (50 + r):
                    return False
            return True
        def _draw_0(self):
            self.g.set_paint(GradientPaint(0, 0, MapArt.c(0x123a23), MapArt.W, MapArt.H, MapArt.c(0x0a2214)))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.dot_grid(20, MapArt.alpha(MapArt.c(0x3bff8a), 16), 0.9)
            self.grid(50, 200, self.accent, 7, 16)
            self.glow_blob(600, 470, 520, Color(60, 255, 140, 18))
            self.traces()
            self.components()
            self.mounting_holes()
            self.silkscreen()
            self.vignette(130)
            for o in self.map.get_obstacles():
                self.chip(o)
            for p in self.sc.get_pads():
                self.pad(p)
            self.track(0.38, self.gold)
            self.hud_frame(self.accent, 'PCB // LX-MAINBOARD')
            self.scanlines(9)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Silicon, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def traces(self):
            """Random orthogonal / 45-degree copper traces under the solder mask, ending in vias."""
            made = 0
            tries = 0
            while (made < 110) and (tries < 4000):
                x = (_j.jround(((self.rnd.next_double() * MapArt.W) / 10)) * 10)
                y = (_j.jround(((self.rnd.next_double() * MapArt.H) / 10)) * 10)
                if not self.clear(x, y, 6):
                    tries += 1
                    continue
                tr = Path2D.Double()
                tr.move_to(x, y)
                cx = x
                cy = y
                total = 0.0
                dir_ = (self.rnd.next_int(4) * 2)
                segs = (2 + self.rnd.next_int(3))
                for s in range(segs):
                    dx = _j.jround(math.cos(((dir_ * math.pi) / 4)))
                    dy = _j.jround(math.sin(((dir_ * math.pi) / 4)))
                    want = (30 + (self.rnd.next_int(9) * 14))
                    run = 0.0
                    while (run < want) and self.clear((cx + (dx * 4)), (cy + (dy * 4)), 5):
                        cx += (dx * 4)
                        cy += (dy * 4)
                        run += 4
                    if run > 0:
                        tr.line_to(cx, cy)
                        total += run
                    if run < want:
                        break
                    dir_ = _j.imod((dir_ + (1 if self.rnd.next_boolean() else 7)), 8)
                if total < 40:
                    tries += 1
                    continue
                w = (3.4 if (self.rnd.next_double() < 0.2) else (2.2 if (self.rnd.next_double() < 0.5) else 1.4))
                self.draw(tr, MapArt.alpha(MapArt.c(0x081a10), 160), (w + 2))
                self.draw(tr, MapArt.alpha(Cyber.lerp(self.mask, self.accent, 0.15), 200), w)
                self.via(x, y)
                self.via(cx, cy)
                made += 1
                tries += 1
        def via(self, x, y):
            self.fill(Ellipse2D.Double((x - 3.6), (y - 3.6), 7.2, 7.2), MapArt.c(0xb89a4a))
            self.fill(Ellipse2D.Double((x - 1.6), (y - 1.6), 3.2, 3.2), MapArt.c(0x06120b))
        def components(self):
            pre = ['R', 'C', 'L', 'D', 'Q']
            made = 0
            tries = 0
            while (made < 46) and (tries < 3000):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                ic = (_j.imod(made, 6) == 5)
                vert = self.rnd.next_boolean()
                w = (24 if ic else 11)
                h = (14 if ic else 5)
                if vert:
                    t = w
                    w = h
                    h = t
                if not self.clear(x, y, ((_j.dmax(w, h) / 2) + 4)):
                    tries += 1
                    continue
                x0 = (x - (w / 2))
                y0 = (y - (h / 2))
                if ic:
                    pins = Path2D.Double()
                    n = 4
                    for i in range(n):
                        f = ((i + 0.5) / n)
                        if not vert:
                            pins.append(Rectangle2D.Double(((x0 + (f * w)) - 1), (y0 - 3), 2, 3), False)
                            pins.append(Rectangle2D.Double(((x0 + (f * w)) - 1), (y0 + h), 2, 3), False)
                        else:
                            pins.append(Rectangle2D.Double((x0 - 3), ((y0 + (f * h)) - 1), 3, 2), False)
                            pins.append(Rectangle2D.Double((x0 + w), ((y0 + (f * h)) - 1), 3, 2), False)
                    self.fill(pins, MapArt.c(0xc7ccd3))
                    self.fill(Rectangle2D.Double(x0, y0, w, h), MapArt.c(0x15181d))
                    self.draw(Rectangle2D.Double(x0, y0, w, h), MapArt.c(0x3a4250), 0.8)
                    self.fill(Ellipse2D.Double((x0 + 2), (y0 + 2), 2.4, 2.4), MapArt.c(0x606a78))
                else:
                    cap = self.rnd.next_boolean()
                    self.fill(Rectangle2D.Double(x0, y0, w, h), (MapArt.c(0x9c7a4c) if cap else MapArt.c(0x1a1a1c)))
                    cw = 2.4
                    end = MapArt.c(0xd8dce2)
                    if not vert:
                        self.fill(Rectangle2D.Double(x0, y0, cw, h), end)
                        self.fill(Rectangle2D.Double(((x0 + w) - cw), y0, cw, h), end)
                    else:
                        self.fill(Rectangle2D.Double(x0, y0, w, cw), end)
                        self.fill(Rectangle2D.Double(x0, ((y0 + h) - cw), w, cw), end)
                made += 1
                tries += 1
        def mounting_holes(self):
            holes = [[26, 26], [1174, 26], [26, 874], [1174, 874], [600, 26]]
            for h in holes:
                if not self.clear(h[0], h[1], 10):
                    continue
                self.fill(Ellipse2D.Double((h[0] - 11), (h[1] - 11), 22, 22), MapArt.c(0xb89a4a))
                self.fill(Ellipse2D.Double((h[0] - 6), (h[1] - 6), 12, 12), MapArt.c(0x050a07))
                self.draw(Ellipse2D.Double((h[0] - 14), (h[1] - 14), 28, 28), MapArt.alpha(self.silk, 90), 0.8)
        def silkscreen(self):
            self.tag('LX-MAINBOARD // REV 4B', 600, 470, Cyber.lerp(self.silk, MapArt.c(0x7fd8a8), 0.4))
            for r in self.map.get_routes():
                s = r.get_start()
                self.tag(r.get_name(), (s.x + 34), ((s.y - MapArt.HW) - 18), self.gold, False)
        def chip(self, o):
            l = ('' if (o.label is None) else o.label)
            if l == 'RAM':
                self.dimm(o)
                return
            if l == 'I/O':
                self.connector(o)
                return
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            in_ = 6.0
            pins = Path2D.Double()
            px = ((x + in_) + 3)
            while px < (((x + w) - in_) - 2):
                pins.append(Rectangle2D.Double(px, y, 3, in_), False)
                pins.append(Rectangle2D.Double(px, ((y + h) - in_), 3, in_), False)
                px += 7
            py = ((y + in_) + 3)
            while py < (((y + h) - in_) - 2):
                pins.append(Rectangle2D.Double(x, py, in_, 3), False)
                pins.append(Rectangle2D.Double(((x + w) - in_), py, in_, 3), False)
                py += 7
            self.fill(pins, MapArt.c(0xc9ced6))
            body = Rectangle2D.Double((x + in_), (y + in_), (w - (2 * in_)), (h - (2 * in_)))
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (w * 0.7), Color(0, 240, 255, 26))
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x2a2f37), x, (y + h), MapArt.c(0x0f1115)))
            self.g.fill(body)
            self.draw(body, MapArt.c(0x4c5562), 1)
            die = Rectangle2D.Double((x + 18), (y + 13), (w - 36), (h - 26))
            self.g.set_paint(GradientPaint(float(die.x), float(die.y), MapArt.c(0x1b2a3a), float(_j.add(die.x, die.width)), float(_j.add(die.y, die.height)), MapArt.c(0x0b1420)))
            self.g.fill(die)
            cells = Path2D.Double()
            cx = (die.x + 4)
            while cx < (_j.add(die.x, die.width) - 3):
                cells.append(Line2D.Double(cx, (die.y + 2), cx, (_j.add(die.y, die.height) - 2)), False)
                cx += 6
            self.draw(cells, Color(0, 240, 255, 26), 1)
            self.draw(die, Color(0, 240, 255, 150), 1)
            self.fill(Ellipse2D.Double(((x + in_) + 3), ((y + in_) + 3), 4, 4), MapArt.c(0x8a929a))
            self.text_centered(l, (x + (w / 2)), (_j.add(die.y, (die.height / 2)) + 2), Cyber.display(Font.BOLD, 15), MapArt.c(0xd9f6ff))
        def dimm(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            board = RoundRectangle2D.Double(x, y, w, h, 6, 6)
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x1b5c34), x, (y + h), MapArt.c(0x0f3a20)))
            self.g.fill(board)
            self.draw(board, MapArt.c(0x8a929a), 1)
            fingers = Path2D.Double()
            fx = (x + 6)
            while fx < ((x + w) - 6):
                if abs((fx - (x + (w * 0.42)))) < 4:
                    fx += 5
                    continue
                fingers.append(Rectangle2D.Double(fx, ((y + h) - 11), 3, 9), False)
                fx += 5
            self.fill(fingers, self.gold)
            self.fill(Rectangle2D.Double(((x + (w * 0.42)) - 2), ((y + h) - 12), 4, 12), MapArt.c(0x0b2616))
            for i in range(4):
                cx = ((x + 8) + ((i * (w - 16)) / 4.0))
                chip = Rectangle2D.Double((cx + 2), (y + 10), (((w - 16) / 4.0) - 4), (h - 30))
                self.fill(chip, MapArt.c(0x121418))
                self.draw(chip, MapArt.c(0x3a4250), 0.8)
                self.fill(Rectangle2D.Double((chip.x + 3), (chip.y + 3), (chip.width - 6), 2), Color(0, 240, 255, 60))
            self.text('RAM', (x + 8), ((y + h) - 15), Cyber.display(Font.BOLD, 14), MapArt.c(0xe6eef6))
        def connector(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            shell = RoundRectangle2D.Double(x, y, w, h, 10, 10)
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x9aa3ad), x, (y + h), MapArt.c(0x3a4048)))
            self.g.fill(shell)
            self.draw(shell, MapArt.c(0xd8dee6), 1)
            slot = RoundRectangle2D.Double((x + 10), (y + 12), (w - 20), (h - 24), 6, 6)
            self.fill(slot, MapArt.c(0x0a0c10))
            pins = Path2D.Double()
            for row in range(2):
                px = (x + 18)
                while px < ((x + w) - 16):
                    pins.append(Rectangle2D.Double(px, ((y + 18) + (row * 12)), 4, 5), False)
                    px += 9
            self.fill(pins, self.gold)
            for i in range(3):
                self.fill(Ellipse2D.Double((((x + w) - 14) - (i * 8)), (y + 4), 4, 4), (Cyber.GREEN if (i == 0) else Color(0x2a3a30)))
            self.text('I/O', (x + 10), (y + 10), Cyber.display(Font.BOLD, 14), MapArt.c(0x10141a))
        def pad(self, p):
            r = 42.0
            self.glow_blob(p.x, p.y, 70, Color(127, 216, 168, 34))
            self.g.set_paint(RadialGradientPaint(Point2D.Double((p.x - 10), (p.y - 12)), r, [0.0, 0.7, 1.0], [MapArt.c(0xc89a52), MapArt.c(0x8a5c2a), MapArt.c(0x4a3016)]))
            self.g.fill(Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r)))
            self.g.set_color(MapArt.c(0x0d2c1a))
            self.g.set_stroke(BasicStroke(6.0))
            for i in range(4):
                a = ((math.pi / 4) + ((i * math.pi) / 2))
                self.g.draw(Line2D.Double((p.x + (math.cos(a) * (r - 13))), (p.y + (math.sin(a) * (r - 13))), (p.x + (math.cos(a) * (r + 1))), (p.y + (math.sin(a) * (r + 1)))))
            self.fill(Ellipse2D.Double((p.x - 26), (p.y - 26), 52, 52), MapArt.c(0x1d4a32))
            self.draw(Ellipse2D.Double((p.x - 26), (p.y - 26), 52, 52), MapArt.alpha(MapArt.c(0x7fd8a8), 200), 1.2)
            self.draw(Ellipse2D.Double((p.x - 16), (p.y - 16), 32, 32), MapArt.alpha(MapArt.c(0x7fd8a8), 110), 1)
            ticks = Path2D.Double()
            for i in range(24):
                a = ((i * math.pi) / 12)
                r0 = (r + 4)
                r1 = (r + (10 if (_j.imod(i, 3) == 0) else 7))
                ticks.append(Line2D.Double((p.x + (math.cos(a) * r0)), (p.y + (math.sin(a) * r0)), (p.x + (math.cos(a) * r1)), (p.y + (math.sin(a) * r1))), False)
            self.draw(ticks, MapArt.alpha(MapArt.c(0x7fd8a8), 150), 1.2)
            self.glow(Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r)), MapArt.alpha(MapArt.c(0x7fd8a8), 220), 1.6, 2)
            plus = Path2D.Double()
            plus.append(Line2D.Double((p.x - 6), p.y, (p.x + 6), p.y), False)
            plus.append(Line2D.Double(p.x, (p.y - 6), p.x, (p.y + 6)), False)
            self.draw(plus, MapArt.alpha(MapArt.c(0x7fd8a8), 200), 2)
            self.tag('CAPACITOR PAD', p.x, ((p.y + r) + 24), MapArt.c(0x7fd8a8))
    class Monolith(Painter):
        def __init__(self, lm, g):
            self.lm = None
            MapArt.Painter.__init__(self, lm, g, MapArt.c(0x161a22), MapArt.c(0x5aa8ff), MapArt.c(0x4f6f8f))
            self.steel = MapArt.c(0x6f7a8c)
            self.amber = MapArt.c(0xffb43b)
            self.lm = lm
        def _draw_0(self):
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            floors = self.lm.get_floors()
            bands = _j.ArrayList()
            _j_add(bands, [0, floors[0][0]])
            for f in floors:
                _j_add(bands, f)
            _j_add(bands, [floors[(len(floors) - 1)][1], MapArt.H])
            for b in bands:
                self.g.set_paint(GradientPaint(0, b[0], MapArt.c(0x1d2330), 0, b[1], MapArt.c(0x10131a)))
                self.g.fill(Rectangle2D.Double(0, b[0], MapArt.W, (b[1] - b[0])))
            seams = Path2D.Double()
            x = 200.0
            while x < MapArt.W:
                seams.append(Line2D.Double(x, 0, x, MapArt.H), False)
                x += 200
            self.draw(seams, Color(0, 0, 0, 120), 2)
            self.g.translate(1.5, 0)
            self.draw(seams, Color(255, 255, 255, 14), 1)
            self.g.translate((-1.5), 0)
            self.perforation()
            self.glow_blob(600, 450, 600, Color(90, 168, 255, 16))
            self.rails()
            for f in floors:
                self.divider(f[0])
            self.divider(floors[(len(floors) - 1)][1])
            self.header()
            self.footer_vents()
            self.cables()
            fans = [[190, 258], [600, 258], [1010, 258], [190, 468], [600, 468], [1010, 468], [190, 678], [600, 678], [1010, 678], [600, 160]]
            for f in fans:
                if self.clear(f[0], f[1], 22):
                    self.fan(f[0], f[1], 22, self.accent)
            self.vignette(140)
            n = 0
            for o in self.map.get_obstacles():
                self.blade(o, ((n := n + 1) - 1))
            for i in range(len(floors)):
                self.tag_right(_j.cat('FLOOR ', (i + 1), ' // ', ('COLD AISLE' if (i < 2) else 'HOT AISLE')), 1086, (floors[i][0] + 15), (self.accent if (i < 2) else self.amber))
            self.track(0.45, self.accent)
            self.hud_frame(self.accent, 'RACK-07 // LEGACY CLUSTER')
            self.scanlines(12)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Monolith, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def perforation(self):
            holes = Path2D.Double()
            lit = Path2D.Double()
            row = 0
            y = 8.0
            while y < MapArt.H:
                x = ((_j.imod(row, 2) * 5.5) + 40)
                while x < (MapArt.W - 36):
                    if not self.clear(x, y, 2):
                        x += 11
                        continue
                    holes.append(Ellipse2D.Double((x - 1.6), (y - 1.6), 3.2, 3.2), False)
                    lit.append(Ellipse2D.Double((x - 1.6), (y + 0.4), 3.2, 1.6), False)
                    x += 11
                y += 11
                row += 1
            self.fill(holes, Color(0, 0, 0, 150))
            self.fill(lit, Color(120, 160, 220, 18))
        def rails(self):
            for x0 in [4, (MapArt.W - 30)]:
                rail = Rectangle2D.Double(x0, 0, 26, MapArt.H)
                self.g.set_paint(GradientPaint(x0, 0, MapArt.c(0x3a4250), (x0 + 26), 0, MapArt.c(0x1a1f28)))
                self.g.fill(rail)
                self.draw(Line2D.Double((x0 + 0.5), 0, (x0 + 0.5), MapArt.H), Color(255, 255, 255, 40), 1)
                sq = Path2D.Double()
                u = 1
                y = 12.0
                while y < (MapArt.H - 6):
                    sq.append(Rectangle2D.Double((x0 + 10), y, 6, 6), False)
                    y += 22
                    u += 1
                self.fill(sq, MapArt.c(0x07090d))
        def divider(self, y):
            band = Rectangle2D.Double(30, (y - 5), (MapArt.W - 60), 10)
            self.fill(band, MapArt.c(0x0c0e12))
            old = self.g.get_clip()
            self.g.clip(band)
            stripes = Path2D.Double()
            x = 20.0
            while x < MapArt.W:
                stripes.move_to(x, (y + 5))
                stripes.line_to((x + 8), (y - 5))
                stripes.line_to((x + 14), (y - 5))
                stripes.line_to((x + 6), (y + 5))
                stripes.close_path()
                x += 16
            self.fill(stripes, MapArt.alpha(MapArt.c(0xc9a227), 70))
            self.g.set_clip(old)
            self.draw(Line2D.Double(30, (y - 5), (MapArt.W - 30), (y - 5)), MapArt.alpha(self.accent, 80), 1)
            self.draw(Line2D.Double(30, (y + 5), (MapArt.W - 30), (y + 5)), Color(0, 0, 0, 160), 1)
        def header(self):
            self.tag('LEGACY MONOLITH // RACK 07 // 42U', 130, 30, self.accent, False)
            for i in range(18):
                x = (660 + (i * 12))
                led = (self.amber if (_j.imod(i, 7) == 3) else (Cyber.RED if (_j.imod(i, 5) == 0) else Cyber.GREEN))
                self.glow_blob((x + 2), 26, 6, MapArt.alpha(led, 60))
                self.fill(Rectangle2D.Double(x, 24, 5, 3), led)
            self.tag('PWR A+B OK', 900, 30, Cyber.GREEN, False)
        def footer_vents(self):
            slots = Path2D.Double()
            x = 140.0
            while x < (MapArt.W - 60):
                slots.append(RoundRectangle2D.Double(x, 864, 8, 24, 4, 4), False)
                x += 14
            self.fill(slots, MapArt.c(0x06070a))
            self.draw(slots, Color(255, 255, 255, 18), 0.8)
        def cables(self):
            ys = [160, 370, 580]
            cols = [MapArt.c(0x2b6cff), MapArt.c(0xff8a2b), MapArt.c(0x2bd67b), MapArt.c(0x8a5cff)]
            for y in ys:
                for k in range(4):
                    x0 = (110 + (k * 4))
                    x1 = (290 - (k * 3))
                    cab = Path2D.Double()
                    cab.move_to(x0, ((y - 8) + (k * 2)))
                    cab.curve_to((x0 + 50), ((y + 10) + (k * 3)), (x1 - 50), ((y + 10) + (k * 3)), x1, ((y - 6) + (k * 2)))
                    if ((not self.clear(x0, ((y - 8) + (k * 2)), 3)) or (not self.clear(x1, ((y - 6) + (k * 2)), 3))) or (not self.clear(((x0 + x1) / 2), ((y + 6) + (k * 2)), 3)):
                        continue
                    self.draw(cab, Color(0, 0, 0, 150), 4.2)
                    self.draw(cab, MapArt.alpha(cols[k], 150), 2.4)
        def blade(self, o, idx):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (w * 0.65), Color(90, 168, 255, 22))
            self.g.translate(0, 4)
            self.fill(RoundRectangle2D.Double(x, y, w, h, 6, 6), Color(0, 0, 0, 120))
            self.g.translate(0, (-4))
            body = RoundRectangle2D.Double(x, y, w, h, 6, 6)
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x3a4252), x, (y + h), MapArt.c(0x1c2029)))
            self.g.fill(body)
            self.draw(body, self.steel, 1.2)
            handle = RoundRectangle2D.Double((x + 6), (y + 8), 10, (h - 16), 4, 4)
            self.fill(handle, MapArt.c(0x0f1218))
            grip = Path2D.Double()
            gy = (y + 14)
            while gy < ((y + h) - 12):
                grip.append(Line2D.Double((x + 8), gy, (x + 14), gy), False)
                gy += 5
            self.draw(grip, MapArt.alpha(self.steel, 150), 1)
            r = _j.Random(((idx * 31) + 7))
            for i in range(6):
                bx = ((x + 24) + (i * 18))
                bay = RoundRectangle2D.Double(bx, (y + 9), 14, (h - 34), 2, 2)
                self.fill(bay, MapArt.c(0x12151c))
                self.draw(bay, MapArt.c(0x4a5466), 0.8)
                vent = Path2D.Double()
                vy = (y + 14)
                while vy < ((y + h) - 32):
                    vent.append(Line2D.Double((bx + 3), vy, (bx + 11), vy), False)
                    vy += 4
                self.draw(vent, Color(255, 255, 255, 22), 0.8)
                led = (self.amber if (r.next_double() < 0.18) else Cyber.GREEN)
                self.glow_blob((bx + 7), ((y + h) - 29), 5, MapArt.alpha(led, 90))
                self.fill(Ellipse2D.Double((bx + 5.5), ((y + h) - 30.5), 3, 3), led)
            lcd = RoundRectangle2D.Double((x + 136), (y + 10), 52, 22, 3, 3)
            self.fill(lcd, MapArt.c(0x061420))
            self.draw(lcd, MapArt.alpha(self.accent, 170), 1)
            load = (40 + r.next_int(58))
            self.text(_j.cat(load, '%'), (x + 142), (y + 24), Cyber.display(Font.BOLD, 14), (self.amber if (load > 85) else Cyber.CYAN))
            self.fill(Rectangle2D.Double((x + 140), (y + 27), ((44 * load) / 100.0), 3), MapArt.alpha((self.amber if (load > 85) else Cyber.CYAN), 190))
            old = self.g.get_clip()
            gr = Rectangle2D.Double((x + 136), (y + 36), 52, (h - 46))
            self.g.clip(gr)
            slots = Path2D.Double()
            sx = (gr.x - gr.height)
            while sx < _j.add(gr.x, gr.width):
                slots.append(Line2D.Double(sx, _j.add(gr.y, gr.height), (sx + gr.height), gr.y), False)
                sx += 5
            self.fill(gr, MapArt.c(0x0c0f14))
            self.draw(slots, MapArt.alpha(self.steel, 90), 1.4)
            self.g.set_clip(old)
            self.draw(gr, MapArt.alpha(self.steel, 140), 0.8)
            self.fill(Rectangle2D.Double((x + 24), ((y + h) - 18), 106, 2), MapArt.alpha(self.accent, 140))
            self.fill(Ellipse2D.Double(((x + w) - 22), ((y + 8) - 0.5), 8, 8), MapArt.c(0x5ce07a))
            self.glow_blob(((x + w) - 18), (y + 12), 8, Color(92, 224, 122, 90))
            self.text(o.label, (x + 24), ((y + h) - 5), Cyber.display(Font.BOLD, 14), MapArt.c(0xe2eaf6))
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
            self.g.set_paint(RadialGradientPaint(Point2D.Double(600, 450), 760.0, [0.0, 0.6, 1.0], [MapArt.c(0x2a1d4c), MapArt.c(0x1b1430), MapArt.c(0x0e0a1c)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.hex_grid(24, MapArt.alpha(self.violet, 16), 1)
            self.glow_blob(300, 200, 360, Color(255, 140, 240, 22))
            self.glow_blob(920, 720, 380, Color(120, 90, 255, 26))
            self.network()
            for o in self.map.get_obstacles():
                self.chasm(o)
            self.vignette(150)
            self.track(0.5, self.violet)
            for n in self.hc.get_nodes():
                self.node(n)
            self.hub(self.hc.get_center())
            self.hud_frame(self.violet, 'NEURAL FIELD // LAYER 12 OF 96')
            self.scanlines(10)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Canyon, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def network(self):
            ns = _j.ArrayList()
            tries = 0
            while (len(ns) < 60) and (tries < 3000):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if self.clear(x, y, 9):
                    _j_add(ns, Vec(x, y))
                tries += 1
            links = Path2D.Double()
            for i in range(len(ns)):
                a = ns[i]
                best1 = (-1)
                best2 = (-1)
                d1 = 1e9
                d2 = 1e9
                for j in range(len(ns)):
                    if j == i:
                        continue
                    d = a.dist(ns[j])
                    if d < d1:
                        d2 = d1
                        best2 = best1
                        d1 = d
                        best1 = j
                    elif d < d2:
                        d2 = d
                        best2 = j
                for b in [best1, best2]:
                    if (b < 0) or (a.dist(ns[b]) > 230):
                        continue
                    v = ns[b]
                    mx = (((a.x + v.x) / 2) + ((self.rnd.next_double() - 0.5) * 40))
                    my = (((a.y + v.y) / 2) + ((self.rnd.next_double() - 0.5) * 40))
                    links.move_to(a.x, a.y)
                    links.quad_to(mx, my, v.x, v.y)
            self.draw(links, MapArt.alpha(self.violet, 30), 3)
            self.draw(links, MapArt.alpha(self.pale, 55), 0.9)
            for n in ns:
                r = (2 + (self.rnd.next_double() * 2.5))
                c = (self.pink if (self.rnd.next_double() < 0.25) else self.violet)
                self.glow_blob(n.x, n.y, (r * 5), MapArt.alpha(c, 70))
                self.fill(Ellipse2D.Double((n.x - r), (n.y - r), (2 * r), (2 * r)), Cyber.lerp(c, Color.WHITE, 0.5))
                self.draw(Ellipse2D.Double(((n.x - r) - 3), ((n.y - r) - 3), ((2 * r) + 6), ((2 * r) + 6)), MapArt.alpha(c, 110), 0.8)
        def chasm(self, o):
            r = Rectangle2D.Double(o.x, o.y, o.w, o.h)
            jag = Path2D.Double()
            step = 12.0
            first = True
            edges = [[o.x, o.y, (o.x + o.w), o.y], [(o.x + o.w), o.y, (o.x + o.w), (o.y + o.h)], [(o.x + o.w), (o.y + o.h), o.x, (o.y + o.h)], [o.x, (o.y + o.h), o.x, o.y]]
            for e in edges:
                len_ = math.hypot((e[2] - e[0]), (e[3] - e[1]))
                nx = ((e[3] - e[1]) / len_)
                ny = ((-(e[2] - e[0])) / len_)
                t = 0.0
                while t < len_:
                    j = ((self.rnd.next_double() - 0.3) * 3.5)
                    px = ((e[0] + (((e[2] - e[0]) * t) / len_)) + (nx * j))
                    py = ((e[1] + (((e[3] - e[1]) * t) / len_)) + (ny * j))
                    if first:
                        jag.move_to(px, py)
                        first = False
                    else:
                        jag.line_to(px, py)
                    t += step
            jag.close_path()
            self.g.set_paint(RadialGradientPaint(Point2D.Double(r.get_center_x(), r.get_center_y()), (_j.dmax(o.w, o.h) * 0.7), [0.0, 1.0], [MapArt.c(0x020106), MapArt.c(0x0e0820)]))
            self.g.fill(jag)
            old = self.g.get_clip()
            self.g.clip(jag)
            self.stars(r, _j.to_int(((o.w * o.h) / 900)), self.violet)
            depth = Path2D.Double()
            cx = r.get_center_x()
            cy = r.get_center_y()
            for i in range(9):
                fx = (o.x + ((o.w * i) / 8.0))
                depth.append(Line2D.Double(fx, o.y, (cx + ((fx - cx) * 0.25)), cy), False)
                depth.append(Line2D.Double(fx, (o.y + o.h), (cx + ((fx - cx) * 0.25)), cy), False)
            k = 0.85
            while k > 0.3:
                depth.append(Rectangle2D.Double((cx - ((o.w * k) / 2)), (cy - ((o.h * k) / 2)), (o.w * k), (o.h * k)), False)
                k -= 0.18
            self.draw(depth, MapArt.alpha(self.violet, 26), 1)
            for i in range(6):
                self.draw(r, Color(0, 0, 0, (60 - (i * 9))), (4 + (i * 4)))
            self.g.set_clip(old)
            self.glow(jag, MapArt.alpha(self.pink, 200), 1.4, 2.4)
            self.draw(jag, MapArt.alpha(self.violet, 120), 4)
            for i in range(5):
                top = self.rnd.next_boolean()
                bw = (18 + (self.rnd.next_double() * 50))
                bx = (o.x + (self.rnd.next_double() * _j.dmax(1, (o.w - bw))))
                by = ((o.y if top else (o.y + o.h)) + ((self.rnd.next_double() - 0.5) * 8))
                self.fill(Rectangle2D.Double(bx, by, bw, (1.5 + (self.rnd.next_double() * 2))), MapArt.alpha((self.pink if self.rnd.next_boolean() else Cyber.CYAN), 110))
            self.tag(('VOID' if (o.w < 140) else 'NULL REGION'), (o.x + ((o.w / 2) if (o.w < 140) else 10)), (o.y + 18), self.pink, (o.w < 140))
        def node(self, n):
            p = n.pos
            self.fill(MapArt.hexagon(p.x, p.y, 31, 0), MapArt.alpha(self.violet, 34))
            self.glow(MapArt.hexagon(p.x, p.y, 31, 0), MapArt.alpha(self.violet, 230), 1.6, 2.4)
            self.draw(MapArt.hexagon(p.x, p.y, 36, 0), MapArt.alpha(self.pale, 70), 0.8)
            self.g.set_color(MapArt.alpha(self.pale, 150))
            self.g.set_stroke(BasicStroke(1.2, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [5.0, 4.0], 0.0))
            self.g.draw(Ellipse2D.Double((p.x - 19), (p.y - 19), 38, 38))
            for i in range(6):
                a = math.radians((i * 60))
                self.fill(Ellipse2D.Double(((p.x + (math.cos(a) * 31)) - 2.2), ((p.y + (math.sin(a) * 31)) - 2.2), 4.4, 4.4), self.pale)
        def hub(self, c):
            self.glow_blob(c.x, c.y, 120, Color(180, 140, 255, 60))
            self.fill(Ellipse2D.Double((c.x - 40), (c.y - 40), 80, 80), MapArt.alpha(MapArt.c(0x5a3fa0), 110))
            for i in range(3):
                r = (48 + (i * 11))
                self.g.set_color(MapArt.alpha((self.pink if (i == 1) else self.pale), (170 - (i * 40))))
                self.g.set_stroke(BasicStroke((2.0 if (i == 0) else 1.2), BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, ([22.0, 6.0] if (i == 0) else ([3.0, 5.0] if (i == 1) else [40.0, 12.0, 6.0, 12.0])), (i * 7.0)))
                self.g.draw(Ellipse2D.Double((c.x - r), (c.y - r), (2 * r), (2 * r)))
            spokes = Path2D.Double()
            for i in range(16):
                a = ((i * math.pi) / 8)
                spokes.append(Line2D.Double((c.x + (math.cos(a) * 42)), (c.y + (math.sin(a) * 42)), (c.x + (math.cos(a) * (54 if (_j.imod(i, 2) == 0) else 48))), (c.y + (math.sin(a) * (54 if (_j.imod(i, 2) == 0) else 48)))), False)
            self.draw(spokes, MapArt.alpha(self.pale, 170), 1.2)
            self.glow(Ellipse2D.Double((c.x - 40), (c.y - 40), 80, 80), MapArt.alpha(self.pale, 230), 1.6, 3)
            self.fill(MapArt.hexagon(c.x, c.y, 9, 30), MapArt.alpha(self.pale, 200))
            self.tag('ATTENTION HUB', c.x, (c.y - 84), self.pale)
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
            self.glow_blob(150, 140, 360, Color(255, 75, 216, 30))
            self.glow_blob(1080, 780, 380, Color(60, 120, 255, 30))
            self.glow_blob(1100, 120, 260, Color(140, 90, 255, 26))
            self.stars(None, 520, self.violet)
            arena = Ellipse2D.Double((c.x - self.R), (c.y - self.R), (2 * self.R), (2 * self.R))
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), self.R, [0.0, 0.18, 0.45, 0.9, 1.0], [MapArt.c(0x4a1f80), MapArt.c(0x22123f), MapArt.c(0x150c2b), MapArt.c(0x1a1030), MapArt.c(0x2a1850)], MultipleGradientPaint.CycleMethod.NO_CYCLE))
            self.g.fill(arena)
            old = self.g.get_clip()
            self.g.clip(arena)
            self.polar_grid(c)
            self.accretion_swirl(c)
            self.g.set_clip(old)
            self.rim(c)
            self.vignette(110)
            self.track(0.5, self.violet)
            for r in self.map.get_routes():
                self.portal(r.get_start(), r.get_name())
            self.horizon(c)
            self.hud_frame(self.violet, 'SINGULARITY CORE // GRAVITY WELL ACTIVE')
            self.scanlines(10)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Singularity, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def polar_grid(self, c):
            rings = Path2D.Double()
            spokes = Path2D.Double()
            major = Path2D.Double()
            r = 40.0
            while r < self.R:
                rings.append(Ellipse2D.Double((c.x - r), (c.y - r), (2 * r), (2 * r)), False)
                r += 40
            for i in range(48):
                a = ((i * math.pi) / 24)
                (major if (_j.imod(i, 6) == 0) else spokes).append(Line2D.Double((c.x + (math.cos(a) * 60)), (c.y + (math.sin(a) * 60)), (c.x + (math.cos(a) * self.R)), (c.y + (math.sin(a) * self.R))), False)
            self.draw(rings, MapArt.alpha(self.violet, 26), 1)
            self.draw(spokes, MapArt.alpha(self.violet, 14), 1)
            self.draw(major, MapArt.alpha(self.violet, 40), 1)
            f = Cyber.mono(Font.PLAIN, 7)
        def accretion_swirl(self, c):
            for arm in range(6):
                sp = Path2D.Double()
                a0 = ((arm * math.pi) / 3)
                first = True
                t = 0.0
                while t <= 1:
                    r = (60 + ((self.R - 70) * t))
                    a = (a0 + (t * 4.2))
                    x = (c.x + (math.cos(a) * r))
                    y = (c.y + (math.sin(a) * r))
                    if first:
                        sp.move_to(x, y)
                        first = False
                    else:
                        sp.line_to(x, y)
                    t += 0.01
                self.draw(sp, MapArt.alpha((self.magenta if (_j.imod(arm, 2) == 0) else self.violet), 22), 14)
                self.draw(sp, MapArt.alpha((self.magenta if (_j.imod(arm, 2) == 0) else self.violet), 45), 1.2)
            self.glow_blob(c.x, c.y, 200, Color(255, 196, 106, 40))
        def rim(self, c):
            outer = Ellipse2D.Double((c.x - self.R), (c.y - self.R), (2 * self.R), (2 * self.R))
            self.draw(outer, MapArt.c(0x1b1236), 18)
            self.g.set_color(MapArt.alpha(self.violet, 150))
            self.g.set_stroke(BasicStroke(6.0, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [30.0, 8.0, 4.0, 8.0], 0.0))
            self.g.draw(outer)
            ticks = Path2D.Double()
            for i in range(120):
                a = ((i * math.pi) / 60)
                r0 = (self.R + 10)
                r1 = (self.R + (20 if (_j.imod(i, 5) == 0) else 14))
                ticks.append(Line2D.Double((c.x + (math.cos(a) * r0)), (c.y + (math.sin(a) * r0)), (c.x + (math.cos(a) * r1)), (c.y + (math.sin(a) * r1))), False)
            self.draw(ticks, MapArt.alpha(self.violet, 120), 1)
            self.glow(Ellipse2D.Double(((c.x - self.R) - 9), ((c.y - self.R) - 9), ((2 * self.R) + 18), ((2 * self.R) + 18)), MapArt.alpha(self.violet, 200), 1.4, 2.5)
            self.glow(Ellipse2D.Double(((c.x - self.R) + 9), ((c.y - self.R) + 9), ((2 * self.R) - 18), ((2 * self.R) - 18)), MapArt.alpha(self.magenta, 120), 1, 2)
        def portal(self, p, name):
            self.glow_blob(p.x, p.y, 70, Color(176, 144, 255, 70))
            self.fill(MapArt.hexagon(p.x, p.y, 32, 0), MapArt.alpha(MapArt.c(0x4020a0), 90))
            self.glow(MapArt.hexagon(p.x, p.y, 32, 0), MapArt.alpha(MapArt.c(0xc0a0ff), 230), 2, 2.6)
            for i in range(3):
                arc = Arc2D.Double((p.x - 40), (p.y - 40), 80, 80, ((i * 120) + 15), 80, Arc2D.OPEN)
                self.glow(arc, MapArt.alpha(self.magenta, 200), 2, 2)
            ang = math.atan2((p.y - 450), (p.x - 600))
            lx = ((p.x + (math.cos(ang) * 0)) + (0 if (abs(math.cos(ang)) > 0.5) else 44))
            ly = (p.y + (((-48) if (math.cos(ang) > 0) else 56) if (abs(math.cos(ang)) > 0.5) else 4))
            self.tag(name, (lx + (0 if (abs(math.cos(ang)) > 0.5) else 30)), (ly - 4), MapArt.c(0xc0a0ff))
        def horizon(self, c):
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), 96.0, [0.0, 0.45, 0.55, 0.75, 1.0], [Color(0, 0, 0, 255), Color(0, 0, 0, 255), Color(255, 196, 106, 200), Color(255, 75, 216, 90), Color(120, 60, 255, 0)]))
            self.g.fill(Ellipse2D.Double((c.x - 96), (c.y - 96), 192, 192))
            self.glow(Ellipse2D.Double((c.x - 45), (c.y - 45), 90, 90), MapArt.alpha(MapArt.c(0xffe6c0), 230), 1.6, 3)
            self.g.set_color(MapArt.alpha(self.hot, 170))
            self.g.set_stroke(BasicStroke(3.0, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10.0, [26.0, 14.0], 0.0))
            self.g.draw(Ellipse2D.Double((c.x - 56), (c.y - 56), 112, 112))
            self.g.set_color(MapArt.alpha(self.magenta, 140))
            self.g.set_stroke(BasicStroke(1.4, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND, 10.0, [4.0, 6.0], 0.0))
            self.g.draw(Ellipse2D.Double((c.x - 70), (c.y - 70), 140, 140))
            self.fill(Ellipse2D.Double((c.x - 30), (c.y - 30), 60, 60), Color.BLACK)
            self.tag('EVENT HORIZON', c.x, (c.y + 94), self.hot)
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
            self.g.set_paint(GradientPaint(0, 0, MapArt.c(0x101d36), 0, MapArt.H, MapArt.c(0x070c18)))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.grid(20, 100, self.cyan, 9, 22)
            self.glow_blob(250, 650, 420, Color(255, 75, 216, 22))
            self.glow_blob(950, 300, 460, Color(95, 212, 255, 24))
            self.circuit(70, MapArt.alpha(self.cyan, 70), Color(0, 0, 0, 90), MapArt.alpha(self.cyan, 160), MapArt.c(0x07101e))
            self.plazas()
            self.planters()
            self.parked_cars()
            self.vignette(130)
            self.lamps()
            self.track(0.72, self.cyan)
            self.lane_marks()
            for o in self.map.get_obstacles():
                self.building(o)
            for b in self.sv.get_skybridges():
                self.skybridge(b)
            self.holos()
            self.arms()
            self.hud_frame(self.cyan, 'INNOVATION DISTRICT // CAMPUS 01')
            self.scanlines(9)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Valley, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def plazas(self):
            made = 0
            tries = 0
            while (made < 7) and (tries < 600):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                r = (34 + (self.rnd.next_double() * 16))
                if not self.clear(x, y, r):
                    tries += 1
                    continue
                self.fill(MapArt.hexagon(x, y, r, 30), Color(20, 40, 70, 120))
                self.draw(MapArt.hexagon(x, y, r, 30), MapArt.alpha(self.cyan, 70), 1)
                self.draw(MapArt.hexagon(x, y, (r * 0.62), 30), MapArt.alpha(self.cyan, 40), 1)
                self.fill(Ellipse2D.Double((x - 3), (y - 3), 6, 6), MapArt.alpha(self.cyan, 160))
                made += 1
                tries += 1
        def planters(self):
            made = 0
            tries = 0
            while (made < 18) and (tries < 900):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if not self.clear(x, y, 12):
                    tries += 1
                    continue
                self.fill(Ellipse2D.Double((x - 11), (y - 11), 22, 22), MapArt.c(0x0e1a24))
                self.draw(Ellipse2D.Double((x - 11), (y - 11), 22, 22), MapArt.alpha(self.lime, 150), 1.2)
                self.glow_blob(x, y, 16, Color(80, 255, 160, 40))
                for k in range(5):
                    a = ((self.rnd.next_double() * math.pi) * 2)
                    d = (self.rnd.next_double() * 4)
                    self.fill(Ellipse2D.Double(((x + (math.cos(a) * d)) - 5), ((y + (math.sin(a) * d)) - 5), 10, 10), MapArt.alpha(Cyber.lerp(MapArt.c(0x1f8a52), self.lime, (self.rnd.next_double() * 0.5)), 210))
                made += 1
                tries += 1
        def parked_cars(self):
            cols = [MapArt.c(0xe8eef6), MapArt.c(0x2b6cff), MapArt.c(0xff4bd8), MapArt.c(0x1d2230), MapArt.c(0xffd84a)]
            made = 0
            tries = 0
            while (made < 9) and (tries < 600):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if not self.clear(x, y, 13):
                    tries += 1
                    continue
                self.car(x, y, (self.rnd.next_int(4) * 90), cols[self.rnd.next_int(len(cols))])
                made += 1
                tries += 1
        def lamps(self):
            r = self.map.get_routes()[0]
            side = False
            d = 60.0
            while d < r.get_total_length():
                p = r.position_at(d)
                dir_ = r.direction_at(d)
                s = (1 if side else (-1))
                off = (MapArt.HW + 10)
                x = (p.x - ((dir_.y * off) * s))
                y = (p.y + ((dir_.x * off) * s))
                q = Vec(x, y)
                if ((((r.distance_to_point(q) < (MapArt.HW + 6)) or (x < 6)) or (y < 6)) or (x > (MapArt.W - 6))) or (y > (MapArt.H - 6)):
                    d += 110
                    side = (not side)
                    continue
                blocked = False
                for o in self.map.get_obstacles():
                    if o.contains(q, 2):
                        blocked = True
                if blocked:
                    d += 110
                    side = (not side)
                    continue
                self.glow_blob(x, y, 26, Color(160, 230, 255, 46))
                self.fill(Ellipse2D.Double((x - 3), (y - 3), 6, 6), MapArt.c(0x1a2436))
                self.fill(Ellipse2D.Double((x - 1.6), (y - 1.6), 3.2, 3.2), Color(0xeaffff))
                d += 110
                side = (not side)
        def lane_marks(self):
            r = self.map.get_routes()[0]
            for d in [140, (r.get_total_length() - 150)]:
                p = r.position_at(d)
                dir_ = r.direction_at(d)
                n = Vec((-dir_.y), dir_.x)
                z = Path2D.Double()
                for i in range((-3), 4):
                    ox = ((n.x * i) * 6)
                    oy = ((n.y * i) * 6)
                    z.append(Line2D.Double(((p.x + ox) - (dir_.x * 7)), ((p.y + oy) - (dir_.y * 7)), ((p.x + ox) + (dir_.x * 7)), ((p.y + oy) + (dir_.y * 7))), False)
                self.draw(z, Color(255, 255, 255, 70), 3)
        def building(self, o):
            l = ('' if (o.label is None) else o.label)
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            ex = 6.0
            ey = 8.0
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (_j.dmax(w, h) * 0.75), MapArt.alpha(self.cyan, 20))
            wall = Path2D.Double()
            wall.move_to(x, (y + h))
            wall.line_to((x + w), (y + h))
            wall.line_to((x + w), y)
            wall.line_to(((x + w) + ex), (y + ey))
            wall.line_to(((x + w) + ex), ((y + h) + ey))
            wall.line_to((x + ex), ((y + h) + ey))
            wall.close_path()
            self.fill(wall, MapArt.c(0x0c1424))
            win = Path2D.Double()
            wx = ((x + ex) + 3)
            while wx < (((x + w) + ex) - 3):
                if self.rnd.next_double() < 0.7:
                    win.append(Rectangle2D.Double(wx, ((y + h) + 2), 3, (ey - 4)), False)
                wx += 6
            wy = ((y + ey) + 3)
            while wy < (((y + h) + ey) - 3):
                if self.rnd.next_double() < 0.7:
                    win.append(Rectangle2D.Double(((x + w) + 2), wy, (ex - 3), 3), False)
                wy += 6
            self.fill(win, MapArt.alpha((self.cyan if self.rnd.next_boolean() else MapArt.c(0xffe6a8)), 150))
            roof = Rectangle2D.Double(x, y, w, h)
            r0 = MapArt.c(0x1c2a42)
            r1 = MapArt.c(0x111a2c)
            if 'HQ' in l:
                r0 = MapArt.c(0x24395c)
                r1 = MapArt.c(0x14223a)
            if ('SERVER' in l) or ('DATA' in l):
                r0 = MapArt.c(0x1a2230)
                r1 = MapArt.c(0x0f141e)
            self.g.set_paint(GradientPaint(x, y, r0, (x + w), (y + h), r1))
            self.g.fill(roof)
            old = self.g.get_clip()
            self.g.clip(roof)
            if 'HQ' in l:
                self.hq(x, y, w, h)
            elif ('SERVER' in l) or ('DATA' in l):
                self.server_roof(x, y, w, h)
            elif 'LAB' in l:
                self.lab(x, y, w, h, ('ROBOTICS' in l))
            elif ('DEPOT' in l) or ('CHARGING' in l):
                self.parking(x, y, w, h)
            elif 'HOLO' in l:
                self.billboard(x, y, w, h)
            self.g.set_clip(old)
            self.glow(roof, MapArt.alpha(self.cyan, 200), 1.4, 2)
            self.draw(Line2D.Double(x, y, (x + w), y), Color(255, 255, 255, 70), 1)
            if not ('HOLO' in l):
                self.tag(l, (x + 5), (y + 15), self.cyan, False)
        def hq(self, x, y, w, h):
            refl = Path2D.Double()
            k = (-h)
            while k < w:
                refl.append(Line2D.Double((x + k), (y + h), ((x + k) + h), y), False)
                k += 18
            self.draw(refl, Color(160, 220, 255, 22), 6)
            t1 = Rectangle2D.Double((x + 12), (y + 20), (w - 24), (h - 30))
            t2 = Rectangle2D.Double((x + 26), (y + 32), (w - 52), (h - 54))
            self.fill(t1, Color(40, 70, 110, 120))
            self.draw(t1, MapArt.alpha(self.glass, 120), 1)
            self.fill(t2, Color(60, 100, 150, 120))
            self.draw(t2, MapArt.alpha(self.glass, 160), 1)
            cx = (x + (w / 2))
            cy = ((y + 32) + ((h - 54) / 2))
            rr = (min(t2.width, t2.height) * 0.36)
            self.draw(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)), MapArt.alpha(Cyber.YELLOW, 200), 1.6)
            self.text_centered('H', cx, (cy + (rr * 0.42)), Cyber.display(Font.BOLD, _j.to_int(_j.dmax(8, (rr * 1.2)))), MapArt.alpha(Cyber.YELLOW, 220))
            self.glow_blob(((x + w) - 14), (y + 26), 10, MapArt.alpha(Cyber.RED, 160))
            self.fill(Ellipse2D.Double(((x + w) - 16), (y + 24), 4, 4), Cyber.RED)
        def server_roof(self, x, y, w, h):
            fx = (x + 22)
            while fx < ((x + w) - 14):
                fy = (y + 28)
                while fy < ((y + h) - 12):
                    self.fan(fx, fy, 12, self.cyan)
                    fy += 32
                fx += 32
            self.fill(Rectangle2D.Double(x, ((y + h) - 5), w, 3), MapArt.alpha(Cyber.GREEN, 140))
        def lab(self, x, y, w, h, robotics):
            solar = Path2D.Double()
            sx = (x + 6)
            while sx < (x + (w * 0.45)):
                solar.append(Rectangle2D.Double(sx, (y + 20), 9, (h - 28)), False)
                sx += 11
            self.fill(solar, MapArt.c(0x16264a))
            self.draw(solar, MapArt.alpha(self.glass, 90), 0.8)
            cx = (x + (w * 0.72))
            cy = (y + (h * 0.55))
            rr = _j.dmin((w * 0.24), (h * 0.36))
            self.g.set_paint(RadialGradientPaint(Point2D.Double((cx - (rr * 0.3)), (cy - (rr * 0.3))), rr, [0.0, 1.0], [Color(200, 240, 255, 200), Color(40, 110, 190, 150)]))
            self.g.fill(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)))
            ribs = Path2D.Double()
            for i in range(6):
                ribs.append(Line2D.Double(cx, cy, (cx + (math.cos(((i * math.pi) / 3)) * rr)), (cy + (math.sin(((i * math.pi) / 3)) * rr))), False)
            ribs.append(Ellipse2D.Double((cx - (rr * 0.55)), (cy - (rr * 0.55)), (rr * 1.1), (rr * 1.1)), False)
            self.draw(ribs, Color(255, 255, 255, 80), 1)
            self.draw(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)), MapArt.alpha(self.glass, 230), 1.4)
            if robotics:
                self.robot_arm((x + (w * 0.5)), (y + (h * 0.3)), 20, self.magenta)
        def parking(self, x, y, w, h):
            vert = (h > w)
            bays = Path2D.Double()
            cols = [MapArt.c(0xe8eef6), MapArt.c(0x2b6cff), MapArt.c(0xff4bd8), MapArt.c(0x3a3f4a), MapArt.c(0xffd84a)]
            if vert:
                by = (y + 20)
                while by < ((y + h) - 4):
                    bays.append(Line2D.Double((x + 4), by, ((x + w) - 4), by), False)
                    if self.rnd.next_double() < 0.75:
                        self.car((x + (w / 2)), (by + 13), 0, cols[self.rnd.next_int(len(cols))])
                    by += 26
            else:
                bx = (x + 6)
                while bx < ((x + w) - 4):
                    bays.append(Line2D.Double(bx, (y + 20), bx, ((y + h) - 4)), False)
                    if (self.rnd.next_double() < 0.7) and ((bx + 26) < (x + w)):
                        self.car((bx + 13), ((y + (h / 2)) + 8), 90, cols[self.rnd.next_int(len(cols))])
                    bx += 26
            self.draw(bays, Color(255, 255, 255, 90), 1)
            for i in range(3):
                px = ((x + 6) if vert else ((x + 16) + ((i * (w - 30)) / 2.0)))
                py = (((y + 32) + ((i * (h - 50)) / 2.0)) if vert else (y + 22))
                self.glow_blob(px, py, 7, Color(60, 255, 140, 120))
                self.fill(Rectangle2D.Double((px - 2), (py - 2), 4, 4), Cyber.GREEN)
        def billboard(self, x, y, w, h):
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x3a0f60), (x + w), y, MapArt.c(0x0f3a66)))
            self.g.fill(Rectangle2D.Double(x, y, w, h))
            lines = Path2D.Double()
            yy = (y + 2)
            while yy < (y + h):
                lines.append(Line2D.Double(x, yy, (x + w), yy), False)
                yy += 3
            self.draw(lines, Color(255, 255, 255, 20), 1)
            self.text_centered('SCALE IS', (x + (w / 2)), (y + (h * 0.36)), Cyber.display(Font.BOLD, 15), Color(255, 255, 255, 240))
            self.text_centered('ALL YOU NEED', (x + (w / 2)), (y + (h * 0.62)), Cyber.display(Font.BOLD, 15), Color(255, 255, 255, 240))
            self.text_centered('NOW SHIPPING', (x + (w / 2)), (y + (h * 0.88)), Cyber.mono(Font.BOLD, 11), Cyber.lerp(self.cyan, Color.WHITE, 0.4))
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (w * 0.5), MapArt.alpha(self.magenta, 40))
        def skybridge(self, b):
            x = b[0]
            y = b[1]
            w = b[2]
            h = b[3]
            self.g.translate(5, 7)
            self.fill(Rectangle2D.Double(x, y, w, h), Color(0, 0, 0, 70))
            self.g.translate((-5), (-7))
            glass_r = Rectangle2D.Double(x, y, w, h)
            self.g.set_paint(GradientPaint(x, y, Color(170, 225, 255, 70), x, (y + h), Color(80, 150, 220, 40)))
            self.g.fill(glass_r)
            mull = Path2D.Double()
            horiz = (w > h)
            if horiz:
                mx = (x + 10)
                while mx < (x + w):
                    mull.append(Line2D.Double(mx, y, mx, (y + h)), False)
                    mx += 10
            else:
                my = (y + 10)
                while my < (y + h):
                    mull.append(Line2D.Double(x, my, (x + w), my), False)
                    my += 10
            self.draw(mull, Color(200, 240, 255, 60), 1)
            self.draw(glass_r, MapArt.alpha(self.glass, 200), 1.6)
            self.draw((Line2D.Double(x, (y + 2), (x + w), (y + 2)) if horiz else Line2D.Double((x + 2), y, (x + 2), (y + h))), Color(255, 255, 255, 110), 1)
        def holos(self):
            ads = ['AGI SOON', '50% OFF', 'HIRE AN AI', 'GPU CLOUD']
            used = _j.ArrayList()
            made = 0
            tries = 0
            while (made < len(ads)) and (tries < 1500):
                w = _j.dmax(64, (self.text_width(ads[made], Cyber.display(Font.BOLD, 14)) + 22))
                h = 30.0
                x = (self.rnd.next_double() * (MapArt.W - w))
                y = (self.rnd.next_double() * ((MapArt.H - h) - 16))
                if not self.clear((x + (w / 2)), (y + (h / 2)), ((w / 2) + 8)):
                    tries += 1
                    continue
                box = Rectangle2D.Double((x - 24), (y - 24), (w + 48), (h + 56))
                hit = False
                for u in used:
                    if u.intersects(box):
                        hit = True
                        break
                if hit:
                    tries += 1
                    continue
                _j_add(used, box)
                self.holo(x, y, w, h, (self.magenta if (_j.imod(made, 2) == 0) else self.cyan), (self.cyan if (_j.imod(made, 2) == 0) else self.magenta), ads[made], None)
                made += 1
                tries += 1
        def arms(self):
            made = 0
            tries = 0
            while (made < 3) and (tries < 600):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if not self.clear(x, y, 34):
                    tries += 1
                    continue
                self.robot_arm(x, y, self.rnd.next_int(360), self.cyan)
                made += 1
                tries += 1
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
            self.g.set_paint(RadialGradientPaint(Point2D.Double(600, 450), 780.0, [0.0, 0.6, 1.0], [MapArt.c(0x0e1430), MapArt.c(0x070a1c), MapArt.c(0x020309)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            self.glow_blob(220, 450, 380, Color(56, 232, 255, 26))
            self.glow_blob(760, 200, 360, Color(255, 75, 216, 22))
            self.glow_blob(860, 760, 380, Color(138, 92, 255, 30))
            self.hex_grid(30, MapArt.alpha(self.violet, 14), 1)
            self.binary_rain()
            self.weights()
            self.platforms()
            self.fragments()
            self.vignette(150)
            self.track(0.58, self.cyan)
            i = 0
            while i < len(self.nn.get_neurons()):
                self.neuron(self.nn.get_neurons()[i], i)
                i += 1
            self.ports()
            self.hud_frame(self.cyan, 'INSIDE THE MACHINE // FORWARD PASS')
            self.scanlines(10)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Neural, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def binary_rain(self):
            f = Cyber.mono(Font.PLAIN, 10)
            self.g.set_font(f)
            x = 12.0
            while x < MapArt.W:
                if self.rnd.next_double() < 0.35:
                    x += 26
                    continue
                y0 = (self.rnd.next_double() * MapArt.H)
                len_ = (6 + self.rnd.next_int(16))
                for k in range(len_):
                    y = (y0 - (k * 12))
                    if y < 0:
                        break
                    a = _j.to_int((150 * (1 - (k / float(len_)))))
                    self.g.set_color((Color(220, 255, 255, 170) if (k == 0) else MapArt.alpha((self.magenta if (self.rnd.next_double() < 0.15) else self.cyan), max(14, _j.idiv(a, 2)))))
                    self.g.draw_string(('1' if self.rnd.next_boolean() else '0'), x, y)
                x += 26
        def weights(self):
            """Faint fully-connected weights between consecutive layers: the network diagram behind the pathways."""
            layers = [[NeuralNetwork.IN_A, NeuralNetwork.IN_B], [NeuralNetwork.J1, NeuralNetwork.J2], [NeuralNetwork.H1, NeuralNetwork.H2, NeuralNetwork.H3], [NeuralNetwork.H4, NeuralNetwork.H5], [NeuralNetwork.OUT]]
            li = 0
            while (li + 1) < len(layers):
                for a in layers[li]:
                    for b in layers[(li + 1)]:
                        self.g.set_paint(GradientPaint(a.x, a.y, MapArt.alpha(self.cyan, 40), b.x, b.y, MapArt.alpha(self.magenta, 40)))
                        self.g.set_stroke(MapArt.round(1.2))
                        self.g.draw(Line2D.Double(a.x, a.y, b.x, b.y))
                li += 1
            xs = [240, 480, 780, 990]
            for x in xs:
                for k in range(3):
                    y = (60 + (self.rnd.next_double() * 780))
                    if not self.clear(x, y, 10):
                        continue
                    self.glow_blob(x, y, 22, MapArt.alpha(self.violet, 70))
                    self.fill(Ellipse2D.Double((x - 6), (y - 6), 12, 12), MapArt.c(0x1a1440))
                    self.draw(Ellipse2D.Double((x - 6), (y - 6), 12, 12), MapArt.alpha(self.violet, 200), 1.2)
                    for v in self.nn.get_neurons():
                        if (abs((v.x - x)) < 1) or (abs((v.x - x)) > 320):
                            continue
                        self.draw(Line2D.Double(x, y, v.x, v.y), MapArt.alpha(self.violet, 18), 1)
        def platforms(self):
            made = 0
            tries = 0
            while (made < 12) and (tries < 1200):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                r = (22 + (self.rnd.next_double() * 10))
                if not self.clear(x, y, r):
                    tries += 1
                    continue
                self.g.translate(0, 5)
                self.fill(MapArt.hexagon(x, y, r, 30), Color(0, 0, 0, 120))
                self.g.translate(0, (-5))
                self.g.set_paint(GradientPaint(x, (y - r), Color(40, 50, 110, 200), x, (y + r), Color(18, 20, 50, 200)))
                self.g.fill(MapArt.hexagon(x, y, r, 30))
                self.glow(MapArt.hexagon(x, y, r, 30), MapArt.alpha((self.magenta if (_j.imod(made, 3) == 0) else self.cyan), 190), 1.2, 2)
                self.draw(MapArt.hexagon(x, y, (r * 0.6), 30), MapArt.alpha(self.cyan, 60), 1)
                spokes = Path2D.Double()
                for i in range(6):
                    a = math.radians((30 + (i * 60)))
                    spokes.append(Line2D.Double((x + ((math.cos(a) * r) * 0.6)), (y + ((math.sin(a) * r) * 0.6)), (x + (math.cos(a) * r)), (y + (math.sin(a) * r))), False)
                self.draw(spokes, MapArt.alpha(self.cyan, 50), 1)
                made += 1
                tries += 1
        def fragments(self):
            bits = ['[0.42]', 'w=1.7', 'relu', 'dL/dw', 'bias +0.3', '0x3F', 'softmax', '[ ]', 'epoch 812', 'lr 3e-4', 'grad', '{ }']
            f = Cyber.mono(Font.BOLD, 11)
            used = _j.ArrayList()
            made = 0
            tries = 0
            while (made < 20) and (tries < 1500):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                box = (self.rnd.next_double() < 0.4)
                s = bits[self.rnd.next_int(len(bits))]
                tw = (10 if box else self.text_width(s, f))
                if not self.clear((x + (tw / 2)), (y - 3), ((tw / 2) + 10)):
                    tries += 1
                    continue
                r = Rectangle2D.Double((x - 14), (y - 26), (tw + 28), 40)
                hit = False
                for u in used:
                    if u.intersects(r):
                        hit = True
                        break
                if hit:
                    tries += 1
                    continue
                _j_add(used, r)
                c = (self.cyan if self.rnd.next_boolean() else self.magenta)
                if box:
                    old = self.g.get_transform()
                    self.g.rotate((self.rnd.next_double() * math.pi), (x + 5), (y - 5))
                    self.draw(Rectangle2D.Double(x, (y - 10), 10, 10), MapArt.alpha(c, 140), 1.2)
                    self.fill(Rectangle2D.Double((x + 3), (y - 7), 4, 4), MapArt.alpha(c, 110))
                    self.g.set_transform(old)
                else:
                    self.fill(RoundRectangle2D.Double((x - 5), (y - 13), (tw + 10), 18, 5, 5), Color(3, 6, 16, 215))
                    self.draw(RoundRectangle2D.Double((x - 5), (y - 13), (tw + 10), 18, 5, 5), MapArt.alpha(c, 140), 1)
                    self.text(s, x, y, f, Cyber.lerp(c, Color.WHITE, 0.45))
                made += 1
                tries += 1
        def neuron(self, p, i):
            out = (p is NeuralNetwork.OUT)
            r = (44 if out else 36)
            core = (MapArt.c(0xffd84a) if out else self.magenta)
            self.glow_blob(p.x, p.y, (r * 2.6), MapArt.alpha(core, 60))
            den = Path2D.Double()
            for k in range(14):
                a = ((((k * math.pi) * 2) / 14) + i)
                r0 = (r + 2)
                r1 = ((r + 9) + (_j.imod(k, 3) * 5))
                den.move_to((p.x + (math.cos(a) * r0)), (p.y + (math.sin(a) * r0)))
                den.quad_to((p.x + ((math.cos((a + 0.12)) * (r0 + r1)) / 2)), (p.y + ((math.sin((a + 0.12)) * (r0 + r1)) / 2)), (p.x + (math.cos((a + 0.2)) * r1)), (p.y + (math.sin((a + 0.2)) * r1)))
            self.draw(den, MapArt.alpha(Cyber.lerp(core, Color.WHITE, 0.3), 150), 1.4)
            self.g.set_paint(RadialGradientPaint(Point2D.Double(p.x, p.y), r, [0.0, 0.35, 0.8, 1.0], [Color(255, 255, 255, 230), MapArt.alpha(core, 200), MapArt.alpha(Cyber.lerp(core, self.violet, 0.6), 120), MapArt.alpha(self.violet, 40)]))
            self.g.fill(Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r)))
            self.glow(Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r)), MapArt.alpha(self.cyan, 230), 1.8, 2.5)
            self.g.set_color(MapArt.alpha(Color.WHITE, 140))
            self.g.set_stroke(BasicStroke(1.2, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [6.0, 5.0], (i * 3.0)))
            self.g.draw(Ellipse2D.Double((p.x - (r * 0.68)), (p.y - (r * 0.68)), (r * 1.36), (r * 1.36)))
            names = ['J1', 'J2', 'H1', 'H2', 'H3', 'H4', 'H5', 'OUT']
            n = (names[i] if (i < len(names)) else 'N')
            self.tag(n, p.x, ((p.y - r) - 14), self.cyan)
        def ports(self):
            for p in [NeuralNetwork.IN_A, NeuralNetwork.IN_B, NeuralNetwork.EXIT]:
                in_ = (p.x < (MapArt.W / 2))
                c = (Cyber.GREEN if in_ else Cyber.RED)
                self.glow_blob(p.x, p.y, 70, MapArt.alpha(c, 50))
                self.g.set_color(MapArt.alpha(c, 200))
                self.g.set_stroke(MapArt.round(3))
                self.g.draw(Arc2D.Double((p.x - 40), (p.y - 40), 80, 80, ((-70) if in_ else 110), 140, Arc2D.OPEN))
                self.tag((('INPUT A' if (p.y < (MapArt.H / 2)) else 'INPUT B') if in_ else 'OUTPUT'), ((p.x + 62) if in_ else (p.x - 66)), (p.y - 52), c)
    class Graveyard(Painter):
        def __init__(self, dc, g):
            self.dc = None
            MapArt.Painter.__init__(self, dc, g, MapArt.c(0x0b0d10), MapArt.c(0xffb43b), MapArt.c(0x9aa4b0))
            self.amber = MapArt.c(0xffb43b)
            self.cold = MapArt.c(0x7fd6ff)
            self.dead = MapArt.c(0x2a2e33)
            self.lights = _j.ArrayList()
            self.dc = dc
        def _draw_0(self):
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            self.floor_tiles()
            self.cables()
            self.glow_blob(600, 120, 260, Color(127, 214, 255, 30))
            self.glow_blob(210, 470, 200, Color(255, 180, 59, 22))
            self.glow_blob(990, 450, 220, Color(127, 214, 255, 22))
            self.glow_blob(600, 820, 220, Color(255, 80, 60, 18))
            self.debris()
            self.vignette(175)
            self.track(0.62, self.amber)
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_marks(self.dc.get_hazards()[i], False)
                i += 1
            for o in self.map.get_obstacles():
                l = ('' if (o.label is None) else o.label)
                if l.startswith('COOLING'):
                    self.cooling_plant(o)
                elif l.startswith('UPS'):
                    self.ups(o)
                else:
                    self.rack(o)
            self.props()
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_marks(self.dc.get_hazards()[i], True)
                i += 1
            self.hud_frame(self.amber, 'SERVER GRAVEYARD // SECTOR 7 // POWER 12%')
            self.scanlines(14)
            _j_put(MapArt.FLICKER, self.map.get_name(), self.lights)
        def draw(self, *a):
            if len(a) == 0:
                return self._draw_0(*a)
            elif len(a) == 3:
                return super(MapArt.Graveyard, self).draw(*a)
            raise TypeError('no overload for %d args' % len(a))
        def floor_tiles(self):
            seams = Path2D.Double()
            x = 0.0
            while x <= MapArt.W:
                seams.append(Line2D.Double(x, 0, x, MapArt.H), False)
                x += 40
            y = 0.0
            while y <= MapArt.H:
                seams.append(Line2D.Double(0, y, MapArt.W, y), False)
                y += 40
            holes = Path2D.Double()
            tx = 0.0
            while tx < MapArt.W:
                ty = 0.0
                while ty < MapArt.H:
                    v = self.rnd.next_double()
                    if v < 0.12:
                        hx = (tx + 6)
                        while hx < (tx + 36):
                            hy = (ty + 6)
                            while hy < (ty + 36):
                                holes.append(Ellipse2D.Double((hx - 1.2), (hy - 1.2), 2.4, 2.4), False)
                                hy += 6
                            hx += 6
                    elif v < 0.3:
                        self.fill(Rectangle2D.Double((tx + 1), (ty + 1), 38, 38), Color(255, 255, 255, (6 + self.rnd.next_int(8))))
                    elif v < 0.36:
                        self.fill(Rectangle2D.Double((tx + 1), (ty + 1), 38, 38), Color(0, 0, 0, 60))
                    ty += 40
                tx += 40
            self.fill(holes, Color(0, 0, 0, 160))
            self.draw(seams, Color(0, 0, 0, 170), 2)
            self.g.translate(1, 1)
            self.draw(seams, Color(255, 255, 255, 10), 1)
            self.g.translate((-1), (-1))
            made = 0
            tries = 0
            while (made < 5) and (tries < 400):
                tx = (float(math.floor(((self.rnd.next_double() * MapArt.W) / 40))) * 40)
                ty = (float(math.floor(((self.rnd.next_double() * MapArt.H) / 40))) * 40)
                if not self.clear((tx + 20), (ty + 20), 22):
                    tries += 1
                    continue
                self.fill(Rectangle2D.Double((tx + 2), (ty + 2), 36, 36), MapArt.c(0x030405))
                for k in range(3):
                    self.draw(Line2D.Double((tx + 4), ((ty + 8) + (k * 11)), (tx + 36), ((ty + 12) + (k * 9))), [MapArt.c(0x5a1a1a), MapArt.c(0x1a3a5a), MapArt.c(0x5a5a1a)][k], 3)
                old = self.g.get_transform()
                self.g.rotate(math.radians((12 + self.rnd.next_int(20))), (tx + 40), (ty + 20))
                self.fill(Rectangle2D.Double((tx + 30), (ty + 6), 36, 36), MapArt.c(0x1c2025))
                self.draw(Rectangle2D.Double((tx + 30), (ty + 6), 36, 36), MapArt.c(0x3a3f46), 1)
                self.g.set_transform(old)
                made += 1
                tries += 1
        def cables(self):
            sheath = [MapArt.c(0x8a2a2a), MapArt.c(0x2a4a8a), MapArt.c(0x8a7a2a), MapArt.c(0x3a3f46), MapArt.c(0x2a6a3a)]
            for i in range(18):
                x0 = (self.rnd.next_double() * MapArt.W)
                y0 = (self.rnd.next_double() * MapArt.H)
                x1 = (x0 + ((self.rnd.next_double() - 0.5) * 360))
                y1 = (y0 + ((self.rnd.next_double() - 0.5) * 360))
                cab = Path2D.Double()
                cab.move_to(x0, y0)
                cab.curve_to((x0 + ((self.rnd.next_double() - 0.5) * 240)), (y0 + ((self.rnd.next_double() - 0.5) * 240)), (x1 + ((self.rnd.next_double() - 0.5) * 240)), (y1 + ((self.rnd.next_double() - 0.5) * 240)), x1, y1)
                w = (2.5 + (self.rnd.next_double() * 3))
                sc = sheath[self.rnd.next_int(len(sheath))]
                self.draw(cab, Color(0, 0, 0, 150), (w + 2.5))
                self.draw(cab, sc, w)
                self.draw(cab, MapArt.alpha(Cyber.lerp(sc, Color.WHITE, 0.4), 60), (w * 0.3))
                if (self.rnd.next_double() < 0.45) and self.clear(x1, y1, 6):
                    self.frayed(x1, y1)
        def frayed(self, x, y):
            wires = Path2D.Double()
            for k in range(5):
                a = ((self.rnd.next_double() * math.pi) * 2)
                wires.append(Line2D.Double(x, y, (x + (math.cos(a) * (5 + (self.rnd.next_double() * 5)))), (y + (math.sin(a) * (5 + (self.rnd.next_double() * 5))))), False)
            self.draw(wires, MapArt.c(0xd08a4a), 1.2)
            self.spark(x, y, 9)
        def spark(self, x, y, r):
            self.glow_blob(x, y, (r * 2.4), Color(255, 230, 140, 90))
            rays = Path2D.Double()
            for k in range(7):
                a = ((self.rnd.next_double() * math.pi) * 2)
                l = (r * (0.5 + (self.rnd.next_double() * 0.7)))
                rays.append(Line2D.Double(x, y, (x + (math.cos(a) * l)), (y + (math.sin(a) * l))), False)
            self.draw(rays, Color(255, 245, 200, 220), 1)
            self.fill(Ellipse2D.Double((x - 1.6), (y - 1.6), 3.2, 3.2), Color.WHITE)
            _j_add(self.lights, [x, y, 1, 0xffe08a])
        def debris(self):
            made = 0
            tries = 0
            while (made < 26) and (tries < 1500):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if not self.clear(x, y, 5):
                    tries += 1
                    continue
                old = self.g.get_transform()
                self.g.rotate((self.rnd.next_double() * math.pi), x, y)
                w = (4 + (self.rnd.next_double() * 9))
                h = (2 + (self.rnd.next_double() * 4))
                self.fill(Rectangle2D.Double((x - (w / 2)), (y - (h / 2)), w, h), (MapArt.c(0x3a3f46) if self.rnd.next_boolean() else MapArt.c(0x1e3a22)))
                self.g.set_transform(old)
                made += 1
                tries += 1
        def hazard_marks(self, hz, labels):
            """labels == false draws the striped zone under the props; true draws its warning tag on top of them."""
            r = self.map.get_routes()[0]
            zone = self.sub_path(r, hz.from_, hz.to)
            band = Area(BasicStroke(((2 * MapArt.HW) + 10), BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND).create_stroked_shape(zone))
            hc = MapArt.c(hz.rgb)
            if labels:
                self.hazard_label(hz, r, hc)
                return
            self.draw(band, Color(0, 0, 0, 200), 4)
            self.g.set_color(MapArt.alpha(Cyber.YELLOW, 220))
            self.g.set_stroke(BasicStroke(4.0, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [7.0, 7.0], 0.0))
            self.g.draw(band)
            old = self.g.get_clip()
            self.g.clip(self.track_area(MapArt.HW))
            self.fill(band, MapArt.alpha(hc, 22))
            self.g.set_clip(old)
        def hazard_label(self, hz, r, hc):
            mid = r.position_at(((hz.from_ + hz.to) / 2))
            dir_ = r.direction_at(((hz.from_ + hz.to) / 2))
            side = 1.0
            tag_at = Vec((mid.x - ((dir_.y * (MapArt.HW + 28)) * side)), (mid.y + ((dir_.x * (MapArt.HW + 28)) * side)))
            blocked = False
            for o in self.map.get_obstacles():
                if o.contains(tag_at, 14):
                    blocked = True
            if blocked:
                tag_at = Vec((mid.x + (dir_.y * (MapArt.HW + 28))), (mid.y - (dir_.x * (MapArt.HW + 28))))
            tri = Path2D.Double()
            tri.move_to(tag_at.x, (tag_at.y - 11))
            tri.line_to((tag_at.x + 11), (tag_at.y + 8))
            tri.line_to((tag_at.x - 11), (tag_at.y + 8))
            tri.close_path()
            self.fill(tri, MapArt.alpha(Cyber.YELLOW, 230))
            self.draw(tri, Color(0, 0, 0, 220), 1.4)
            self.text_centered('!', tag_at.x, (tag_at.y + 6), Cyber.mono(Font.BOLD, 12), Color.BLACK)
            self.tag(hz.kind, tag_at.x, (tag_at.y + 24), hc)
            _j_add(self.lights, [tag_at.x, (tag_at.y - 2), 2, (Cyber.YELLOW.get_rgb() & 0xffffff)])
        def rack(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            self.g.translate(4, 6)
            self.fill(Rectangle2D.Double(x, y, w, h), Color(0, 0, 0, 140))
            self.g.translate((-4), (-6))
            body = Rectangle2D.Double(x, y, w, h)
            self.g.set_paint(GradientPaint(x, y, MapArt.c(0x23272d), (x + w), y, MapArt.c(0x121417)))
            self.g.fill(body)
            self.draw(body, MapArt.c(0x4a5058), 1.4)
            units = Path2D.Double()
            uy = (y + 6)
            while uy < ((y + h) - 4):
                units.append(Line2D.Double((x + 5), uy, ((x + w) - 5), uy), False)
                uy += 9
            self.draw(units, Color(0, 0, 0, 180), 1.2)
            uy = (y + 8)
            while uy < ((y + h) - 6):
                v = self.rnd.next_double()
                led = (self.dead if (v < 0.62) else (Cyber.RED if (v < 0.78) else (self.amber if (v < 0.92) else Cyber.GREEN)))
                self.fill(Rectangle2D.Double(((x + w) - 10), uy, 3, 3), led)
                if led != self.dead:
                    self.glow_blob(((x + w) - 8.5), (uy + 1.5), 5, MapArt.alpha(led, 90))
                    if self.rnd.next_double() < 0.35:
                        _j_add(self.lights, [((x + w) - 8.5), (uy + 1.5), 0, (led.get_rgb() & 0xffffff)])
                uy += 9
            crack = Path2D.Double()
            cx = (x + (w * 0.3))
            cy = (y + (h * (0.3 + (self.rnd.next_double() * 0.4))))
            crack.move_to(cx, cy)
            crack.line_to((cx + 8), (cy + 6))
            crack.line_to((cx + 5), (cy + 14))
            crack.line_to((cx + 13), (cy + 20))
            self.draw(crack, Color(200, 210, 220, 90), 1)
            if self.rnd.next_boolean():
                old = self.g.get_transform()
                self.g.rotate(math.radians((-14)), x, (y + (h * 0.5)))
                self.fill(Rectangle2D.Double((x - 4), (y + (h * 0.5)), 6, (h * 0.42)), MapArt.c(0x2c3036))
                self.g.set_transform(old)
        def cooling_plant(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            self.glow_blob((x + (w / 2)), (y + (h / 2)), (w * 0.9), Color(127, 214, 255, 40))
            body = Rectangle2D.Double(x, y, w, h)
            self.fill(body, MapArt.c(0x1a1f25))
            old = self.g.get_clip()
            border = Area(body)
            border.subtract(Area(Rectangle2D.Double((x + 8), (y + 8), (w - 16), (h - 16))))
            self.g.clip(border)
            self.fill(body, Color(0x1a1a1a))
            stripes = Path2D.Double()
            k = (-h)
            while k < (w + h):
                stripes.move_to((x + k), y)
                stripes.line_to(((x + k) + 8), y)
                stripes.line_to((((x + k) + 8) - h), (y + h))
                stripes.line_to(((x + k) - h), (y + h))
                stripes.close_path()
                k += 16
            self.fill(stripes, MapArt.alpha(Cyber.YELLOW, 150))
            self.g.set_clip(old)
            pipe = MapArt.c(0x5a6a7a)
            for py in [(y + 30), ((y + h) - 30)]:
                self.draw(Line2D.Double((x + 12), py, ((x + w) - 12), py), Color(0, 0, 0, 160), 11)
                self.draw(Line2D.Double((x + 12), py, ((x + w) - 12), py), pipe, 8)
                self.draw(Line2D.Double((x + 12), (py - 2), ((x + w) - 12), (py - 2)), Color(255, 255, 255, 50), 2)
                jx = (x + 30)
                while jx < ((x + w) - 20):
                    self.fill(Rectangle2D.Double(jx, (py - 6), 5, 12), MapArt.c(0x3a4550))
                    jx += 44
            self.fan((x + (w / 2)), (y + (h * 0.36)), 44, self.cold)
            self.fan((x + (w / 2)), (y + (h * 0.7)), 30, self.cold)
            self.g.set_paint(RadialGradientPaint(Point2D.Double((x + 24), ((y + h) - 24)), (w * 0.5), [0.0, 1.0], [Color(200, 240, 255, 90), Color(200, 240, 255, 0)]))
            self.g.fill(body)
            self.draw(body, MapArt.c(0x5a6470), 1.6)
            self.fill(Rectangle2D.Double((x + 14), (y + 12), (w - 28), 14), Color(0, 0, 0, 200))
            self.tag('COOLING PLANT // OFFLINE', (x + (w / 2)), (y + 19), self.amber)
            _j_add(self.lights, [((x + w) - 16), (y + 19), 2, (self.amber.get_rgb() & 0xffffff)])
        def ups(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            self.fill(Rectangle2D.Double(x, y, w, h), MapArt.c(0x15181c))
            self.draw(Rectangle2D.Double(x, y, w, h), MapArt.c(0x4a5058), 1.4)
            for i in range(4):
                cx = ((x + 6) + ((i * (w - 12)) / 4.0))
                cw = (((w - 12) / 4.0) - 6)
                cab = RoundRectangle2D.Double(cx, (y + 8), cw, (h - 16), 4, 4)
                self.fill(cab, MapArt.c(0x23282e))
                self.draw(cab, MapArt.c(0x3a4048), 1)
                self.fill(Rectangle2D.Double((cx + 4), (y + 14), (cw - 8), 10), Color(20, 6, 6))
                self.text(('FAULT' if (i == 2) else 'LOW'), (cx + 5), (y + 23), Cyber.mono(Font.BOLD, 10), Cyber.RED)
                by = (y + 32)
                while by < ((y + h) - 14):
                    self.fill(Rectangle2D.Double((cx + 4), by, ((cw - 8) * (0.15 if (i == 2) else 0.3)), 3), MapArt.alpha(Cyber.RED, 160))
                    by += 6
                _j_add(self.lights, [(cx + (cw / 2)), (y + 19), 1, (Cyber.RED.get_rgb() & 0xffffff)])
            self.tag('UPS BANK', (x + 2), ((y + h) + 14), self.amber, False)
        def props(self):
            monitors = 0
            beacons = 0
            fans = 0
            chassis = 0
            tries = 0
            while (tries < 2500) and ((((monitors < 8) or (beacons < 7)) or (fans < 3)) or (chassis < 4)):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if (monitors < 8) and self.clear(x, y, 16):
                    self.monitor(x, y)
                    monitors += 1
                    tries += 1
                    continue
                if (beacons < 7) and self.clear(x, y, 8):
                    self.beacon(x, y)
                    beacons += 1
                    tries += 1
                    continue
                if (fans < 3) and self.clear(x, y, 26):
                    self.fan(x, y, 22, self.amber)
                    fans += 1
                    tries += 1
                    continue
                if (chassis < 4) and self.clear(x, y, 20):
                    self.toppled(x, y)
                    chassis += 1
                tries += 1
            sparks = 0
            tries = 0
            while (sparks < 6) and (tries < 800):
                x = (self.rnd.next_double() * MapArt.W)
                y = (self.rnd.next_double() * MapArt.H)
                if self.clear(x, y, 8):
                    self.spark(x, y, (8 + (self.rnd.next_double() * 5)))
                    sparks += 1
                tries += 1
        def monitor(self, x, y):
            old = self.g.get_transform()
            self.g.rotate(math.radians((self.rnd.next_int(50) - 25)), x, y)
            self.fill(RoundRectangle2D.Double((x - 14), (y - 10), 28, 20, 3, 3), MapArt.c(0x202428))
            self.draw(RoundRectangle2D.Double((x - 14), (y - 10), 28, 20, 3, 3), MapArt.c(0x4a5058), 1)
            on = (self.rnd.next_double() < 0.55)
            scr = (MapArt.c(0x3bff8a) if self.rnd.next_boolean() else self.cold)
            screen = Rectangle2D.Double((x - 11), (y - 7.5), 22, 14)
            self.fill(screen, (MapArt.alpha(scr, 70) if on else MapArt.c(0x0a0c0e)))
            if on:
                txt = Path2D.Double()
                for k in range(4):
                    txt.append(Line2D.Double((x - 9), ((y - 5) + (k * 3.4)), (((x - 9) + 6) + (self.rnd.next_double() * 12)), ((y - 5) + (k * 3.4))), False)
                self.draw(txt, MapArt.alpha(scr, 200), 1)
                _j_add(self.lights, [x, y, 0, (scr.get_rgb() & 0xffffff)])
            crack = Path2D.Double()
            crack.move_to((x + 2), (y - 7))
            crack.line_to((x - 2), (y - 1))
            crack.line_to((x + 4), (y + 2))
            crack.line_to((x + 1), (y + 7))
            crack.move_to((x - 2), (y - 1))
            crack.line_to((x - 9), (y + 1))
            self.draw(crack, Color(255, 255, 255, 140), 0.8)
            self.fill(Rectangle2D.Double((x - 4), (y + 10), 8, 3), MapArt.c(0x2a2e33))
            self.fill(RoundRectangle2D.Double((x - 12), (y + 15), 24, 6, 2, 2), MapArt.c(0x1a1d21))
            self.g.set_transform(old)
        def beacon(self, x, y):
            self.glow_blob(x, y, 22, MapArt.alpha(self.amber, 70))
            self.fill(Ellipse2D.Double((x - 5), (y - 5), 10, 10), MapArt.c(0x2a2420))
            self.fill(Ellipse2D.Double((x - 3.2), (y - 3.2), 6.4, 6.4), self.amber)
            self.fill(Ellipse2D.Double((x - 1.4), (y - 2.4), 2.4, 2), Color(255, 255, 255, 200))
            _j_add(self.lights, [x, y, 2, (self.amber.get_rgb() & 0xffffff)])
        def toppled(self, x, y):
            old = self.g.get_transform()
            self.g.rotate(math.radians(self.rnd.next_int(360)), x, y)
            self.fill(Rectangle2D.Double((x - 16), (y - 7), 32, 14), Color(0, 0, 0, 120))
            self.fill(Rectangle2D.Double((x - 17), (y - 9), 32, 14), MapArt.c(0x2a2f36))
            self.draw(Rectangle2D.Double((x - 17), (y - 9), 32, 14), MapArt.c(0x4a5058), 1)
            for k in range(4):
                self.fill(Rectangle2D.Double(((x - 14) + (k * 7)), (y - 6), 5, 8), MapArt.c(0x16191d))
            self.fill(Rectangle2D.Double((x + 10), (y - 6), 2, 2), (Cyber.RED if self.rnd.next_boolean() else self.dead))
            self.g.set_transform(old)
    class Pulses(GObject):
        """Glowing data packets streaming along every route (one cheap custom ACM object). Skipped when the world view is
painting at a reduced level of detail."""
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
            if Thick.level() >= Thick.DETAIL_DECOR:
                return
            g2 = g.create()
            try:
                g2.set_composite(AlphaComposite.SrcOver)
                g2.set_stroke(BasicStroke(3.0, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
                ri = 0
                for r in self.map.get_routes():
                    len_ = r.get_total_length()
                    n = max(3, _j.to_int((len_ / 420)))
                    for k in range(n):
                        d = _j.fmod((_j.fmod((((self.time * 150) + ((k * len_) / n)) + (ri * 97)), len_) + len_), len_)
                        if d < 24:
                            continue
                        p = r.position_at(d)
                        q = r.position_at((d - 26))
                        g2.set_paint(GradientPaint(q.x, q.y, MapArt.alpha(self.col, 0), p.x, p.y, MapArt.alpha(self.col, 170)))
                        g2.draw(Line2D.Double(q.x, q.y, p.x, p.y))
                        g2.set_color(MapArt.alpha(self.col, 70))
                        g2.fill(Ellipse2D.Double((p.x - 6), (p.y - 6), 12, 12))
                        g2.set_color(Color.WHITE)
                        g2.fill(Ellipse2D.Double((p.x - 2.2), (p.y - 2.2), 4.4, 4.4))
                    ri += 1
                if isinstance(self.map, NeuralNetwork):
                    self.neuron_pulse(g2)
                if isinstance(self.map, AbandonedDataCenter):
                    self.flicker(g2)
                    self.hazard_fx(g2, self.map)
            finally:
                g2.dispose()
        def neuron_pulse(self, g2):
            """Neurons breathe: an expanding ring and a brightening core, out of phase per neuron."""
            ns = self.map.get_neurons()
            for i in range(len(ns)):
                p = ns[i]
                ph = _j.fmod(((self.time * 0.8) + (i * 0.37)), 1.0)
                rr = (38 + (ph * 34))
                g2.set_stroke(BasicStroke(2.0))
                g2.set_color(MapArt.alpha(MapArt.c(0xff4bd8), _j.to_int((150 * (1 - ph)))))
                g2.draw(Ellipse2D.Double((p.x - rr), (p.y - rr), (2 * rr), (2 * rr)))
                a = _j.to_int((60 + (50 * math.sin(((self.time * 3) + i)))))
                g2.set_color(Color(255, 255, 255, max(0, a)))
                g2.fill(Ellipse2D.Double((p.x - 10), (p.y - 10), 20, 20))
        def flicker(self, g2):
            """Dying lights: monitors flicker, warning beacons blink, sparks crackle."""
            ls = MapArt.FLICKER.get(self.map.get_name())
            if ls is None:
                return
            for i in range(len(ls)):
                l = ls[i]
                kind = _j.to_int(l[2])
                n = (math.sin(((self.time * (7 + _j.imod(i, 5))) + (i * 1.7))) + math.sin(((self.time * 13.3) + i)))
                if kind == 2:
                    a = (120 if (_j.imod(_j.to_int(((self.time * 2) + (i * 0.3))), 2) == 0) else 0)
                elif kind == 1:
                    a = (200 if (n > 1.2) else 0)
                else:
                    a = (90 if (n > 0.6) else (40 if (n > (-1.4)) else 0))
                if a <= 0:
                    continue
                rr = (16 if (kind == 2) else (10 if (kind == 1) else 12))
                c = Color(_j.to_int(l[3]))
                g2.set_paint(RadialGradientPaint(Point2D.Double(l[0], l[1]), rr, [0.0, 1.0], [MapArt.alpha(c, a), MapArt.alpha(c, 0)]))
                g2.fill(Ellipse2D.Double((l[0] - rr), (l[1] - rr), (2 * rr), (2 * rr)))
        def hazard_fx(self, g2, dc):
            """Particles over the active hazard section: sparks, coolant mist or air streaks."""
            idx = dc.get_active_hazard()
            if idx < 0:
                return
            h = dc.get_hazards()[idx]
            r = self.map.get_routes()[0]
            c = Color(h.rgb)
            rr = _j.Random(_j.to_long((self.time * 20)))
            for k in range(22):
                d = (h.from_ + (rr.next_double() * (h.to - h.from_)))
                p = r.position_at(d)
                dir_ = r.direction_at(d)
                off = (((rr.next_double() - 0.5) * 2) * MapArt.HW)
                x = (p.x - (dir_.y * off))
                y = (p.y + (dir_.x * off))
                if h.kind == 'SPARKS':
                    a = ((rr.next_double() * math.pi) * 2)
                    l = (4 + (rr.next_double() * 8))
                    g2.set_color(MapArt.alpha(Color.WHITE, 220))
                    g2.set_stroke(BasicStroke(1.2))
                    g2.draw(Line2D.Double(x, y, (x + (math.cos(a) * l)), (y + (math.sin(a) * l))))
                    g2.set_color(MapArt.alpha(c, 120))
                    g2.fill(Ellipse2D.Double((x - 4), (y - 4), 8, 8))
                elif h.kind == 'COOLANT':
                    s = (6 + (rr.next_double() * 12))
                    g2.set_color(MapArt.alpha(c, 60))
                    g2.fill(Ellipse2D.Double((x - (s / 2)), (y - (s / 2)), s, s))
                    g2.set_color(MapArt.alpha(Color.WHITE, 120))
                    g2.fill(Ellipse2D.Double((x - 1), (y - 1), 2, 2))
                else:
                    l = (10 + (rr.next_double() * 14))
                    g2.set_color(MapArt.alpha(c, 130))
                    g2.set_stroke(BasicStroke(1.4, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND))
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
MapArt.Pulses.serial_version_uid = 1
