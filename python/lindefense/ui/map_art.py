"""Lindefense MapArt (ported from src/lindefense/ui/MapArt.java): the seven map backgrounds in a minimal, futuristic
cyberpunk style."""
import bisect
import math

import numpy as np
import skia

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.jawt import _runs
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


def _blur(g, s, c, sigma, width=0.0):
    """A Skia extra with no Java2D equivalent: paints shape s in colour c blurred by a Gaussian of sigma world px, filled
(width 0) or stroked width wide. It makes the soft neon glows and light falloff of the map art, which are baked into the
cached map bitmap and so cost nothing per frame. The blur follows the transform, so thumbnails, the playfield and HiDPI
bitmaps all look alike."""
    p = skia.Paint(AntiAlias=True, Color=skia.Color(c.get_red(), c.get_green(), c.get_blue(), c.get_alpha()),
                   MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
    if width > 0:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(width)
        p.setStrokeJoin(skia.Paint.kRound_Join)
        p.setStrokeCap(skia.Paint.kRound_Cap)
    cv = g._begin()
    path = s.path()
    m = cv.getTotalMatrix()
    k = int(min(6, (sigma * math.sqrt(abs(m.getScaleX() * m.getScaleY()))) / 2.0))
    if k < 2:
        cv.drawPath(path, p)
        return
    # A wide blur on a big bitmap is costly (the mask spans the whole shape): render it into a layer k times smaller
    # (the blur still spans >= 2 px there) and draw that layer back scaled up with bilinear filtering. Same look.
    pad = ((width / 2) + (3 * sigma))
    dev = m.mapRect(path.computeTightBounds().makeOutset(pad, pad))
    clip = skia.Rect.Make(cv.getDeviceClipBounds())
    if not dev.intersect(clip):
        return
    x0 = math.floor(dev.left())
    y0 = math.floor(dev.top())
    w = (int(math.ceil(((dev.right() - x0) / k))) + 1)
    h = (int(math.ceil(((dev.bottom() - y0) / k))) + 1)
    layer = skia.Surface.MakeRasterN32Premul(w, h)
    lc = layer.getCanvas()
    lc.scale((1.0 / k), (1.0 / k))
    lc.translate((-x0), (-y0))
    lc.concat(m)
    lc.drawPath(path, p)
    cv.save()
    cv.resetMatrix()
    cv.drawImageRect(layer.makeImageSnapshot(), skia.Rect.MakeWH(w, h), skia.Rect.MakeXYWH(x0, y0, (w * k), (h * k)),
                     skia.SamplingOptions(skia.FilterMode.kLinear), None)
    cv.restore()


class MapArt(GObject):
    """Map art (background, set dressing, track) as one ACM GObject, in a minimal, futuristic cyberpunk style: few elements
with a strong atmosphere. Every map is built from the same layers:

  ground: a dark, deep gradient with one or two very soft lights (light falloff);
  far layer: a faint grid, circuit traces, constellation or vortex at low contrast and without glow;
  near layer: the props that are gameplay (chips, chassis, chasms, portals, buildings, racks, pads, nodes, hazard
      sections) as dark solid shapes with crisp thin neon outlines and a soft glow, so what blocks placement or does
      something always reads as solid and lit, and never like the faint decoration behind it;
  the track: a dark road body tinted with the track colour between two crisp neon edge lines, with a soft glow and a
      wide faint light falloff along its edges, a faint inner rail and sparse direction chevrons.

  set dressing (the details): the world's small things, as quiet neon line art: components and solder points on the
      board, fans and cables in the server hall, debris and glitch shards in the canyon, planets and orbiting debris in
      space, cars, street lights, trees and robot arms on the campus, weight labels and activation glyphs in the
      network, monitors, cables and sparks in the dead data center. Thinner, dimmer and cooler than anything that
      matters to play, and placed only on open ground well away from the track: never on it nor in the strips beside it
      where towers stand (STRIP), so the buildable / blocked distinction stays obvious. Their places are computed once
      per map (layout_for), so the live ambience can animate a few of them.

Each map keeps one neon accent palette (from the game's magenta / cyan / violet / amber palette). Text is either a
functional label (route names that banners refer to, floor numbers, hazard kinds, capacitor pads) or diegetic: neon
signs on buildings and markings printed on props (chip markings, blade numbers, displays), recorded by mark(). There
are no floating HUD-style captions.

The art is painted once into a bitmap at the resolution the object is actually shown at (canvas scale x HiDPI scale)
and every frame only blits that bitmap. The bitmap is re-rendered when the window is resized and shared through a
small cache, so the map-select thumbnails and the playfield cost nothing per frame. Everything is deterministic
(seeded per map) and only reads the map's static geometry: routes, obstacles, pads, nodes. Set dressing is placed only
where it keeps clear of the track and obstacles so it never hides gameplay.

Pulses is the small live layer: particles over an active malfunctioning section (Abandoned Data Center) and the
optional ambience (Ambience: a data pulse along a trace now and then, a few slowly breathing lights, blinking LEDs, a
flickering sign, a slowly spinning fan, a car on a side street), which is off with REDUCED MOTION, on LOW quality and in
the most crowded fights."""
    class Painter:
        def __init__(self, map_, g, bg, accent, track):
            self.map = map_
            self.g = g
            self.bg = bg
            self.accent = accent
            self.f_track = track
            self.rnd = _j.Random(_j.hash_code(map_.get_name()))
            self.soft = None
            self.vignette = False
            self.detail = True      # paint the set dressing (tests turn it off to tell it apart)
            self.fine = True        # the smallest details too (off on thumbnail-sized bitmaps, where they'd be noise)
            self.marks = []         # the diegetic text painted (mark)
            self.lay = None         # the set dressing's places (layout_for)
            self.drnd = _j.Random(((_j.hash_code(map_.get_name()) * 7) + 3))
            self.taken = []         # discs (x, y, r) already used by the layout
        def layout(self):
            """The set dressing's places (a dict), from the map's static geometry only. Overridden per map."""
            return {}
        def paint_generic(self):
            self.begin_soft()
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            self.track_glow(80)
            self.end_soft()
            self.grid(100, self.accent, 10)
            self.track(0.6)
        # ------------------------------------------------------------------ the soft pass
        def begin_soft(self):
            """Starts the soft pass: the ground gradient, wide lights and big glows have no sharp detail, so on a large
(HiDPI) bitmap they are painted into an opaque layer at about 0.7 px per world px and drawn back scaled up with bilinear
filtering by end_soft. The same look for a fraction of the cost; the crisp detail is painted afterwards at full
resolution. Small bitmaps (thumbnails, 1:1) paint directly. The HIGH-quality vignette (VignetteOverlay) is part of
the soft pass too: it darkens the far corners of the ground under the crisp detail."""
            self.soft = None
            s = math.sqrt(abs(self.g.get_transform().get_determinant()))
            k = _j.to_int((s * 1.5))
            if k < 2:
                return
            r = (s / k)
            img = BufferedImage((_j.to_int(float(math.ceil((MapArt.W * r)))) + 2), (_j.to_int(float(math.ceil((MapArt.H * r)))) + 2), BufferedImage.TYPE_INT_RGB)
            gl = img.create_graphics()
            Cyber.quality(gl)
            gl.scale(r, r)
            self.soft = (self.g, img, r)
            self.g = gl
        def end_soft(self):
            if self.vignette:
                VignetteOverlay.paint(self.g, MapArt.W, MapArt.H)
            if self.soft is None:
                return
            main, img, r = self.soft
            self.g.dispose()
            self.g = main
            self.soft = None
            at = AffineTransform()
            at.scale((1.0 / r), (1.0 / r))
            main.set_rendering_hint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR)
            main.draw_image(img, at, None)
        # ------------------------------------------------------------------ drawing primitives
        def fill(self, s, c):
            self.g.set_color(c)
            self.g.fill(s)
        def draw(self, s, c, w):
            self.g.set_stroke(MapArt.round(w))
            self.g.set_color(c)
            self.g.draw(s)
        def dashed(self, s, c, w, on, off):
            self.g.set_color(c)
            self.g.set_stroke(BasicStroke(w, BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND, 10.0, [on, off], 0.0))
            self.g.draw(s)
        def blur(self, s, c, sigma, w=0.0):
            """A soft glow: s filled (w = 0) or stroked w wide in colour c, blurred by sigma world px."""
            _blur(self.g, s, c, sigma, w)
        def neon(self, s, c, w=1.2, glow=80, sigma=3.0, glow_c=None):
            """A crisp thin neon line with a soft glow around it (glow = the glow's alpha, 0 = none; glow_c its colour
when it differs from the line's)."""
            if glow > 0:
                self.blur(s, MapArt.alpha((c if (glow_c is None) else glow_c), glow), sigma, (w + 2.5))
            self.draw(s, c, w)
        def ground(self, c0, c1, x1, y1):
            """The deep base gradient, from c0 at the top-left corner towards c1 at (x1, y1)."""
            self.g.set_paint(GradientPaint(0, 0, c0, x1, y1, c1))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
        def text(self, s, x, y, f, c):
            self.g.set_font(f)
            self.g.set_color(c)
            self.g.draw_string(s, x, y)
        def text_width(self, s, f):
            self.g.set_font(f)
            return self.g.get_font_metrics().string_width(s)
        def label(self, s, cx, cy, c):
            """A functional map label: small, quiet capitals centred on (cx, cy) on a dark chip with a hairline border in
the label's colour. Only labels the player needs (names that banners refer to, hazard kinds, pads) are drawn."""
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
            chip = RoundRectangle2D.Double(x0, y0, pw, ph, 3, 3)
            self.fill(chip, Color(3, 5, 10, 190))
            self.draw(chip, MapArt.alpha(c, 70), 1)
            self.text(u, (x0 + 5), (((y0 + (ph / 2)) + (self.g.get_font_metrics().get_ascent() / 2.0)) - 1), f, MapArt.alpha(Cyber.lerp(c, Color.WHITE, 0.25), 215))
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
            """A very soft, wide radial light (a few per map at most)."""
            self.g.set_paint(RadialGradientPaint(Point2D.Double(cx, cy), r, [0.0, 1.0], [c, MapArt.alpha(c, 0)]))
            self.g.fill(Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r)))
        def stars(self, region, n, tint, a=70):
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
            self.fill(dots, MapArt.alpha(Cyber.lerp(Color.WHITE, tint, 0.4), a))
            self.g.set_clip(old)
        def constellation(self, n, link_c, dot_c, link_cap):
            """A faint far-layer net: n dots that keep clear of the gameplay, each linked to its nearest neighbour."""
            ns = _j.ArrayList()
            tries = 0
            while (len(ns) < n) and (tries < 3000):
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
                if (best >= 0) and (bd < link_cap):
                    links.move_to(a.x, a.y)
                    links.line_to(ns[best].x, ns[best].y)
            self.draw(links, link_c, 1)
            dots = Path2D.Double()
            for v in ns:
                dots.append(Ellipse2D.Double((v.x - 1.8), (v.y - 1.8), 3.6, 3.6), False)
            self.fill(dots, dot_c)
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
        def edge_colour(self):
            """The neon colour of the track's edges (default: the track colour lightened)."""
            return Cyber.lerp(self.f_track, Color.WHITE, 0.3)
        def track_glow(self, glow):
            """The light of the track (soft pass): a soft glow along both edges (alpha glow) and a wide faint falloff on
the ground around the road. The road body painted later covers the inner half, so it only lights the ground."""
            body = self.track_area(MapArt.HW)
            e = self.edge_colour()
            self.blur(body, MapArt.alpha(e, _j.idiv(glow, 4)), 18)
            self.blur(body, MapArt.alpha(e, glow), 3.5, 3.0)
        def track(self, darken, chevron=None):
            """The track: a dark flat road body (the track colour pulled towards black by darken) between two crisp neon
edge lines, a faint inner rail and small, sparse direction chevrons (one per stretch, never doubled where routes share a
road). Its light is track_glow, painted in the soft pass."""
            body = self.track_area(MapArt.HW)
            e = self.edge_colour()
            self.fill(body, Cyber.lerp(self.f_track, Color.BLACK, darken))
            self.draw(self.track_area((MapArt.HW - 5)), MapArt.alpha(e, 34), 1)
            self.draw(body, MapArt.alpha(e, 215), 1.3)
            self.chevrons((chevron if (chevron is not None) else MapArt.alpha(e, 90)))
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
        def circuit(self, count, salt, ok=None):
            """Sparse orthogonal / 45-degree circuit traces that keep clear of the track, obstacles and the map's own
exclusions (or pass ok(x, y, r)), as polylines [(x, y), ...]. Seeded by the map name and salt only, so the live data
pulses (Ambience) run along exactly the traces the bitmap shows."""
            clear = (self.clear if (ok is None) else ok)
            rnd = _j.Random(((_j.hash_code(self.map.get_name()) * 31) + salt))
            out = []
            tries = 0
            while (len(out) < count) and (tries < (count * 40)):
                tries += 1
                x = (_j.jround(((rnd.next_double() * MapArt.W) / 10)) * 10)
                y = (_j.jround(((rnd.next_double() * MapArt.H) / 10)) * 10)
                if not clear(x, y, 6):
                    continue
                pts = [(x, y)]
                cx = x
                cy = y
                total = 0.0
                dir_ = (rnd.next_int(4) * 2)
                segs = (2 + rnd.next_int(2))
                for k in range(segs):
                    dx = _j.jround(math.cos(((dir_ * math.pi) / 4)))
                    dy = _j.jround(math.sin(((dir_ * math.pi) / 4)))
                    want = (40 + (rnd.next_int(8) * 14))
                    run = 0.0
                    while (run < want) and clear((cx + (dx * 4)), (cy + (dy * 4)), 5):
                        cx += (dx * 4)
                        cy += (dy * 4)
                        run += 4
                    if run > 0:
                        pts.append((cx, cy))
                        total += run
                    if run < want:
                        break
                    dir_ = _j.imod((dir_ + (1 if rnd.next_boolean() else 7)), 8)
                if total < 50:
                    continue
                out.append(pts)
            return out
        # ------------------------------------------------------------------ set dressing helpers
        def deco_clear(self, x, y, r, props=True, others=True):
            """True if a detail of radius r at (x, y) keeps off the track and the tower strips beside it (STRIP px beyond
each edge), off obstacles (unless props is False: details mounted on a prop's rim), off the map's exclusions and the
world edge, and clear of the details already placed."""
            if (x < (r + 4)) or (y < (r + 4)) or (x > ((MapArt.W - r) - 4)) or (y > ((MapArt.H - r) - 4)):
                return False
            if MapArt.track_distance(self.map, x, y) < ((MapArt.HW + MapArt.STRIP) + r):
                return False
            if props:
                p = Vec(x, y)
                for o in self.map.get_obstacles():
                    if o.contains(p, (r + 8)):
                        return False
            if not self.deco_extra(x, y, r):
                return False
            if not others:
                return True
            for t in self.taken:
                if math.hypot((x - t[0]), (y - t[1])) < ((r + t[2]) + 6):
                    return False
            return True
        def box_clear(self, x0, y0, x1, y1, props=True):
            """deco_clear for a box-shaped detail: its outline, sampled every 6 px, keeps off the track and its strips,
the obstacles (props) and the exclusions, and its centre keeps clear of the details already placed."""
            cx = ((x0 + x1) / 2)
            cy = ((y0 + y1) / 2)
            if not self.deco_clear(cx, cy, (min((x1 - x0), (y1 - y0)) / 2), props):
                return False
            nx = max(1, _j.to_int(math.ceil(((x1 - x0) / 6.0))))
            ny = max(1, _j.to_int(math.ceil(((y1 - y0) / 6.0))))
            pts = []
            for i in range((nx + 1)):
                x = (x0 + (((x1 - x0) * i) / nx))
                pts.append((x, y0))
                pts.append((x, y1))
            for j in range((ny + 1)):
                y = (y0 + (((y1 - y0) * j) / ny))
                pts.append((x0, y))
                pts.append((x1, y))
            taken = self.taken
            self.taken = []
            try:
                return all(self.deco_clear(x, y, 0, props) for x, y in pts)
            finally:
                self.taken = taken
        def deco_extra(self, x, y, r):
            """Per-map exclusions for the set dressing (default: the map's own exclusions)."""
            return self.extra_clear(x, y, r)
        def spot(self, r, x0=0.0, y0=0.0, x1=None, y1=None, tries=300):
            """A free place for a detail of radius r inside the box (x0, y0)-(x1, y1), or None; the place is taken."""
            x1 = (MapArt.W if (x1 is None) else x1)
            y1 = (MapArt.H if (y1 is None) else y1)
            for _ in range(tries):
                x = (x0 + (self.drnd.next_double() * (x1 - x0)))
                y = (y0 + (self.drnd.next_double() * (y1 - y0)))
                if self.deco_clear(x, y, r):
                    self.taken.append((x, y, r))
                    return (x, y)
            return None
        def spots(self, n, r, tries=300):
            out = []
            for _ in range(n):
                p = self.spot(r, tries=tries)
                if p is not None:
                    out.append(p)
            return out
        def deco_area(self):
            """The open ground the set dressing may use (for clipping ground textures): the world minus the track and
its tower strips and minus the obstacles."""
            a = Area(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            a.subtract(self.track_area((MapArt.HW + MapArt.STRIP)))
            for o in self.map.get_obstacles():
                a.subtract(Area(Rectangle2D.Double((o.x - 8), (o.y - 8), (o.w + 16), (o.h + 16))))
            return a
        def mark(self, s, x, y, f, c):
            """Diegetic text (a neon sign, a chip marking, a display readout): painted like any text and recorded, so it
can be told from labels."""
            self.marks.append(s)
            self.text(s, x, y, f, c)
        def glow_text(self, s, x, y, f, c, sigma):
            """A soft glow under text (Skia blur mask; follows the transform like blur)."""
            cv = self.g._begin()
            p = skia.Paint(AntiAlias=True, Color=skia.Color(c.get_red(), c.get_green(), c.get_blue(), c.get_alpha()),
                           MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
            xx = float(x)
            for sf, t in _runs(f, s):
                cv.drawString(t, xx, float(y), sf, p)
                xx += sf.measureText(t)
        def neon_text(self, s, x, y, size, c, a=190, glow=70, mono=False):
            """Glowing neon tube letters, left edge at x, baseline at y (a sign's text)."""
            f = (Cyber.mono(Font.BOLD, size) if mono else MapArt.sign_font(size))
            if glow > 0:
                self.glow_text(s, x, y, f, MapArt.alpha(c, glow), (size * 0.28))
            self.mark(s, x, y, f, MapArt.alpha(Cyber.lerp(c, Color.WHITE, 0.25), a))
        def sign(self, lines, x, y, c, size=9, a=190, glow=70, frame=True, align='l', pad=4.0):
            """A diegetic neon sign mounted on a building or prop: lines of glowing letters on a dark backing panel with
a thin frame tube; MapArt.sign_rect gives the panel. Returns the panel as (x, y, w, h)."""
            f = MapArt.sign_font(size)
            x0, y0, pw, ph = MapArt.sign_rect(lines, x, y, size, align, pad)
            panel = RoundRectangle2D.Double(x0, y0, pw, ph, 3, 3)
            self.fill(panel, Color(3, 5, 10, 230))
            if frame:
                self.blur(panel, MapArt.alpha(c, 35), 2.5, 1)
                self.draw(panel, MapArt.alpha(c, 95), 0.9)
            lh = (size * 1.05)
            for i, s in enumerate(lines):
                sx = ((x0 + (pw / 2)) - (MapArt.measure(s, f) / 2))
                self.neon_text(s, sx, (((y0 + (pad / 2)) + (lh * (i + 1))) - (size * 0.18)), size, c, a, glow)
            return (x0, y0, pw, ph)
        def fan_art(self, cx, cy, r, c, a=90, blades=5, fill=None):
            """A cooling fan as line art: housing ring, curved blades (MapArt.fan_blades), hub and two grill bars."""
            disc = Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r))
            self.fill(disc, (MapArt.c(0x05070b) if (fill is None) else fill))
            self.draw(disc, MapArt.alpha(c, a), 1)
            self.draw(MapArt.fan_blades(cx, cy, r, 0.0, blades), MapArt.alpha(c, _j.idiv((a * 3), 4)), 1)
            grill = Path2D.Double()
            grill.append(Line2D.Double((cx - r), cy, (cx + r), cy), False)
            grill.append(Line2D.Double(cx, (cy - r), cx, (cy + r)), False)
            self.draw(grill, MapArt.alpha(c, _j.idiv(a, 4)), 0.8)
            self.draw(Ellipse2D.Double((cx - (r * 0.22)), (cy - (r * 0.22)), (r * 0.44), (r * 0.44)), MapArt.alpha(c, a), 1)
        def car_art(self, cx, cy, ang_deg, c, a=120, lights=True):
            """A top-down little car as neon line art (nose towards ang_deg): body, cabin, head and tail lights."""
            old = self.g.get_transform()
            self.g.translate(cx, cy)
            self.g.rotate(math.radians(ang_deg))
            MapArt.car_shape(self.g, c, a, lights)
            self.g.set_transform(old)
        def rotated(self, x, y, deg):
            """Rotates the painter about (x, y); returns the old transform for set_transform."""
            old = self.g.get_transform()
            self.g.rotate(math.radians(deg), x, y)
            return old
    class Silicon(Painter):
        """The Silicon Circuit: a deep green PCB at night. Far layer: solder-mask dots and faint traces; near layer: a few
mint traces with vias, the chips (CPU / RAM / I/O, which block placement) as dark packages with cyan / mint neon
outlines, the capacitor pads as glowing mint rings; the gold traces are the track. Set dressing: a populated board
(SMD parts, small ICs and clusters with silkscreen corners, extra traces ending in solder vias, mounting holes) and chip
markings (CPU, RAM, I/O, connector pins and status LEDs)."""
        def __init__(self, sc, g):
            MapArt.Painter.__init__(self, sc, g, MapArt.c(0x04130b), MapArt.c(0x3bff8a), MapArt.c(0xd4a62a))
            self.sc = sc
            self.gold = MapArt.c(0xd4a62a)
            self.mint = MapArt.c(0x7fd8a8)
            self.green = MapArt.c(0x3bff8a)
            self.cyan = MapArt.c(0x38e8ff)
            self.steel = MapArt.c(0x8fa3b0)
        def extra_clear(self, x, y, r):
            for p in self.sc.get_pads():
                if p.dist(Vec(x, y)) < (56 + r):
                    return False
            return True
        def edge_colour(self):
            return Cyber.lerp(self.gold, Color.WHITE, 0.25)
        def paint_map(self):
            far, near = MapArt.circuit_layers(self.map)
            np_ = Path2D.Double()
            for t in near:
                MapArt.polyline(t, np_)
            self.begin_soft()
            self.ground(MapArt.c(0x06200f), MapArt.c(0x010805), MapArt.W, MapArt.H)
            self.soft_light(600, 450, 640, Color(40, 140, 90, 20))
            for p in self.sc.get_pads():
                self.soft_light(p.x, p.y, 92, Color(127, 216, 168, 38))
            self.blur(np_, MapArt.alpha(self.green, 36), 3, 3.7)
            self.track_glow(90)
            self.end_soft()
            self.dot_grid(25, MapArt.alpha(self.mint, 12), 0.8)
            fp = Path2D.Double()
            for t in far:
                MapArt.polyline(t, fp)
            self.draw(fp, MapArt.alpha(MapArt.c(0x2f8a5c), 48), 1)
            vias = Path2D.Double()
            for t in near:
                for v in (t[0], t[(len(t) - 1)]):
                    vias.append(Ellipse2D.Double((v[0] - 2.8), (v[1] - 2.8), 5.6, 5.6), False)
            self.draw(np_, MapArt.alpha(self.green, 105), 1.2)
            self.fill(vias, self.bg)
            self.draw(vias, MapArt.alpha(self.green, 170), 1.1)
            if self.detail:
                self.board_details()
            for o in self.map.get_obstacles():
                self.chip(o)
            for p in self.sc.get_pads():
                self.pad(p)
            self.track(0.46)
            for r in self.map.get_routes():
                s = r.get_start()
                self.label_at(r.get_name(), (s.x + 34), ((s.y - MapArt.HW) - 14), self.gold, False)
        # ------------------------------------------------------------------ set dressing: a populated board
        def layout(self):
            lay = {'holes': [], 'parts': []}
            for x, y in ((26, 26), (1174, 26), (26, 874), (1174, 874)):
                if self.deco_clear(x, y, 14):
                    lay['holes'].append((x, y))
                    self.taken.append((x, y, 14))
            lay['groups'] = []
            for i in range(10):
                p = self.spot(26)
                if p is None:
                    continue
                x, y = p
                vert = self.drnd.next_boolean()
                kind = ('array', 'qfp', 'decap', 'soic')[(i % 4)]
                along = ((lambda k, d: (x, (y + (k * d)))) if vert else (lambda k, d: ((x + (k * d)), y)))
                if kind == 'array':
                    for k in range(5):
                        lay['parts'].append(('r',) + along((k - 2), 7) + ((not vert),))
                elif kind == 'decap':
                    for k in range(4):
                        lay['parts'].append(('c',) + along((k - 1.5), 9) + ((not vert),))
                    lay['parts'].append(('cap',) + along(3.6, 9) + (vert,))
                elif kind == 'qfp':
                    lay['parts'].append(('qfp', x, y, vert))
                    lay['parts'].append(('c', (x + 17), (y - 9), True))
                    lay['parts'].append(('c', (x - 17), (y + 9), True))
                else:
                    lay['parts'].append(('ic',) + along(0, 0) + (vert,))
                    lay['parts'].append(('r',) + along(1.9, 9) + (vert,))
                    lay['parts'].append(('r',) + along((-1.9), 9) + (vert,))
                lay['groups'].append((x, y))
            kinds = ['r', 'c', 'r', 'ic', 'r', 'cap', 'c', 'r', 'xtal', 'r', 'c', 'led', 'r', 'ic', 'tp', 'c', 'r', 'tp']
            size = {'r': 8, 'c': 7, 'ic': 15, 'cap': 10, 'xtal': 11, 'led': 6, 'tp': 5}
            for i in range(44):
                k = kinds[(i % len(kinds))]
                p = self.spot(size[k])
                if p is not None:
                    lay['parts'].append((k, p[0], p[1], self.drnd.next_boolean()))
            lay['traces'] = self.circuit(54, 3, lambda x, y, r: self.deco_clear(x, y, r))
            leds = [(p[1], p[2]) for p in lay['parts'] if p[0] == 'led']
            lay['blink'] = leds[:2]
            return lay
        def board_details(self):
            """The populated board between the traces: faint extra traces with solder vias, SMD resistors and capacitors,
small ICs, electrolytic caps, a crystal, status LEDs, test points and the mounting holes in the corners, all as thin, dim
line art."""
            lay = self.lay
            steel = MapArt.alpha(self.steel, 80)
            solder = MapArt.alpha(self.gold, 75)
            tr = Path2D.Double()
            ends = Path2D.Double()
            for t in lay['traces']:
                MapArt.polyline(t, tr)
                for v in (t[0], t[(len(t) - 1)]):
                    ends.append(Ellipse2D.Double((v[0] - 2.3), (v[1] - 2.3), 4.6, 4.6), False)
            self.draw(tr, MapArt.alpha(MapArt.c(0x2f8a5c), 58), 1)
            self.fill(ends, self.bg)
            self.draw(ends, solder, 0.9)
            for x, y in lay['holes']:
                self.draw(Ellipse2D.Double((x - 10), (y - 10), 20, 20), MapArt.alpha(self.gold, 70), 1.2)
                self.draw(Ellipse2D.Double((x - 5.5), (y - 5.5), 11, 11), MapArt.alpha(self.gold, 45), 1)
                self.dashed(Ellipse2D.Double((x - 14.5), (y - 14.5), 29, 29), MapArt.alpha(self.mint, 30), 0.8, 2, 4)
            if not self.fine:
                return
            bodies = Path2D.Double()
            pads = Path2D.Double()
            pins = Path2D.Double()
            lit = Path2D.Double()
            for k, x, y, vert in lay['parts']:
                if k in ('r', 'c'):
                    w = (10.0 if (k == 'r') else 8.0)
                    h = (4.4 if (k == 'r') else 4.0)
                    if vert:
                        w, h = h, w
                    bodies.append(Rectangle2D.Double((x - (w / 2)), (y - (h / 2)), w, h), False)
                    cw = 2.2
                    if not vert:
                        pads.append(Rectangle2D.Double((x - (w / 2)), (y - (h / 2)), cw, h), False)
                        pads.append(Rectangle2D.Double(((x + (w / 2)) - cw), (y - (h / 2)), cw, h), False)
                    else:
                        pads.append(Rectangle2D.Double((x - (w / 2)), (y - (h / 2)), w, cw), False)
                        pads.append(Rectangle2D.Double((x - (w / 2)), ((y + (h / 2)) - cw), w, cw), False)
                elif k == 'ic':
                    w, h = ((10.0, 18.0) if vert else (18.0, 10.0))
                    bodies.append(Rectangle2D.Double((x - (w / 2)), (y - (h / 2)), w, h), False)
                    for i in range(4):
                        f = ((i + 0.5) / 4)
                        if not vert:
                            px = ((x - (w / 2)) + (f * w))
                            pins.append(Line2D.Double(px, ((y - (h / 2)) - 3), px, (y - (h / 2))), False)
                            pins.append(Line2D.Double(px, (y + (h / 2)), px, ((y + (h / 2)) + 3)), False)
                        else:
                            py = ((y - (h / 2)) + (f * h))
                            pins.append(Line2D.Double(((x - (w / 2)) - 3), py, (x - (w / 2)), py), False)
                            pins.append(Line2D.Double((x + (w / 2)), py, ((x + (w / 2)) + 3), py), False)
                    pads.append(Ellipse2D.Double(((x - (w / 2)) + 1.6), ((y - (h / 2)) + 1.6), 2.2, 2.2), False)
                elif k == 'cap':
                    bodies.append(Ellipse2D.Double((x - 7), (y - 7), 14, 14), False)
                    bodies.append(Line2D.Double((x - 6.2), (y + 3), (x + 6.2), (y + 3)), False)
                    pads.append(Rectangle2D.Double((x - 1.5), (y - 5.5), 3, 1), False)
                    pads.append(Rectangle2D.Double((x - 0.5), (y - 6.5), 1, 3), False)
                elif k == 'xtal':
                    w, h = ((6.5, 16.0) if vert else (16.0, 6.5))
                    bodies.append(RoundRectangle2D.Double((x - (w / 2)), (y - (h / 2)), w, h, 6, 6), False)
                    bodies.append(RoundRectangle2D.Double(((x - (w / 2)) + 2), ((y - (h / 2)) + 2), (w - 4), (h - 4), 3, 3), False)
                elif k == 'qfp':
                    bodies.append(Rectangle2D.Double((x - 9), (y - 9), 18, 18), False)
                    for i in range(5):
                        o = ((i - 2) * 3.4)
                        pins.append(Line2D.Double((x + o), (y - 12), (x + o), (y - 9)), False)
                        pins.append(Line2D.Double((x + o), (y + 9), (x + o), (y + 12)), False)
                        pins.append(Line2D.Double((x - 12), (y + o), (x - 9), (y + o)), False)
                        pins.append(Line2D.Double((x + 9), (y + o), (x + 12), (y + o)), False)
                    pads.append(Ellipse2D.Double((x - 7), (y - 7), 2.4, 2.4), False)
                    bodies.append(Rectangle2D.Double((x - 4.5), (y - 4.5), 9, 9), False)
                elif k == 'led':
                    bodies.append(Ellipse2D.Double((x - 3.4), (y - 3.4), 6.8, 6.8), False)
                    lit.append(Ellipse2D.Double((x - 1.5), (y - 1.5), 3, 3), False)
                else:
                    pads.append(Ellipse2D.Double((x - 3), (y - 3), 6, 6), False)
            silk = Path2D.Double()
            for x, y in lay['groups']:
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    cx = (x + (sx * 27))
                    cy = (y + (sy * 27))
                    silk.move_to(cx, (cy - (sy * 6)))
                    silk.line_to(cx, cy)
                    silk.line_to((cx - (sx * 6)), cy)
            self.draw(silk, MapArt.alpha(self.mint, 40), 0.9)
            self.fill(bodies, MapArt.c(0x030a07))
            self.draw(bodies, steel, 0.9)
            self.fill(pads, solder)
            self.draw(pins, solder, 1)
            self.blur(lit, MapArt.alpha(self.green, 70), 2)
            self.fill(lit, MapArt.alpha(self.green, 150))
        def chip(self, o):
            l = ('' if (o.label is None) else o.label)
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            dark = MapArt.c(0x030a07)
            if l == 'RAM':
                board = RoundRectangle2D.Double(x, y, w, h, 6, 6)
                self.fill(board, dark)
                self.neon(board, MapArt.alpha(self.mint, 205), 1.2, 70)
                top = ((y + 17) if self.detail else (y + 10))
                mods = Path2D.Double()
                for i in range(4):
                    cx = ((x + 8) + ((i * (w - 16)) / 4.0))
                    mods.append(RoundRectangle2D.Double((cx + 2), top, (((w - 16) / 4.0) - 4), ((y + h) - 20) - top, 2, 2), False)
                self.draw(mods, MapArt.alpha(self.mint, 80), 1)
                notch = (x + (w * 0.42))
                pins = Path2D.Double()
                px = (x + 9)
                while px < ((x + w) - 8):
                    if not (self.detail and (abs((px - notch)) < 4)):
                        pins.append(Line2D.Double(px, ((y + h) - 13), px, ((y + h) - 7)), False)
                    px += 5
                self.draw(pins, MapArt.alpha(self.gold, 170), 1.4)
                if self.detail:
                    f = Cyber.mono(Font.BOLD, 9)
                    self.mark('RAM', (x + 10), (y + 13), f, MapArt.alpha(self.mint, 150))
                    self.mark('4x16G', (((x + w) - 10) - MapArt.measure('4x16G', f)), (y + 13), f, MapArt.alpha(self.mint, 85))
                    marks = Path2D.Double()
                    for i in range(4):
                        cx = ((x + 8) + ((i * (w - 16)) / 4.0))
                        marks.append(Line2D.Double((cx + 6), (top + 6), ((cx + ((w - 16) / 4.0)) - 6), (top + 6)), False)
                    self.draw(marks, MapArt.alpha(self.mint, 50), 1)
                return
            if l == 'I/O':
                shell = RoundRectangle2D.Double(x, y, w, h, 10, 10)
                self.fill(shell, dark)
                self.neon(shell, MapArt.alpha(self.cyan, 195), 1.2, 60)
                self.draw(RoundRectangle2D.Double((x + 12), (y + 14), (w - 24), (h - 28), 5, 5), MapArt.alpha(self.cyan, 90), 1)
                pins = Path2D.Double()
                rows = (((y + (h / 2)) - 7, (y + (h / 2)) + 1) if self.detail else ((y + (h / 2)) - 3,))
                for ry in rows:
                    px = (x + 22)
                    while px < ((x + w) - 20):
                        pins.append(Line2D.Double(px, ry, px, (ry + 6)), False)
                        px += 7
                self.draw(pins, MapArt.alpha(self.gold, 150), 1.2)
                if self.detail:
                    self.mark('I/O', (x + 12), (y + 11), Cyber.mono(Font.BOLD, 9), MapArt.alpha(self.cyan, 150))
                    for i in range(3):
                        led = Ellipse2D.Double((((x + w) - 18) - (i * 8)), (y + 5), 4, 4)
                        if i == 0:
                            self.blur(led, MapArt.alpha(self.green, 90), 2.5)
                            self.fill(led, MapArt.alpha(self.green, 220))
                        else:
                            self.draw(led, MapArt.alpha(self.steel, 90), 0.8)
                return
            in_ = 6.0
            pins = Path2D.Double()
            px = ((x + in_) + 4)
            while px < (((x + w) - in_) - 2):
                pins.append(Line2D.Double(px, (y + 1), px, (y + in_)), False)
                pins.append(Line2D.Double(px, ((y + h) - in_), px, ((y + h) - 1)), False)
                px += 8
            py = ((y + in_) + 4)
            while py < (((y + h) - in_) - 2):
                pins.append(Line2D.Double((x + 1), py, (x + in_), py), False)
                pins.append(Line2D.Double(((x + w) - in_), py, ((x + w) - 1), py), False)
                py += 8
            self.draw(pins, MapArt.alpha(self.steel, 120), 1.2)
            body = RoundRectangle2D.Double((x + in_), (y + in_), (w - (2 * in_)), (h - (2 * in_)), 4, 4)
            self.fill(body, dark)
            self.neon(body, MapArt.alpha(self.cyan, 200), 1.2, 70)
            die = Rectangle2D.Double(((x + (w / 2)) - 30), ((y + (h / 2)) - 11), 60, 22)
            self.blur(die, MapArt.alpha(self.cyan, 60), 8)
            if self.detail:
                cells = Path2D.Double()
                cx = ((x + (w / 2)) - 26)
                while cx < ((x + (w / 2)) + 27):
                    cells.append(Line2D.Double(cx, ((y + (h / 2)) - 9), cx, ((y + (h / 2)) + 9)), False)
                    cx += 6
                self.draw(cells, MapArt.alpha(self.cyan, 24), 1)
                f = Cyber.mono(Font.BOLD, 11)
                self.fill(Rectangle2D.Double(((x + (w / 2)) - 15), ((y + (h / 2)) - 7), 30, 14), dark)
                self.mark('CPU', ((x + (w / 2)) - (MapArt.measure('CPU', f) / 2)), ((y + (h / 2)) + 4), f, MapArt.alpha(self.cyan, 165))
                self.fill(Ellipse2D.Double(((x + in_) + 4), ((y + in_) + 4), 3.5, 3.5), MapArt.alpha(self.steel, 120))
            self.draw(die, MapArt.alpha(self.cyan, 150), 1)
        def pad(self, p):
            r = 40.0
            disc = Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r))
            self.fill(disc, MapArt.c(0x04140c))
            self.neon(disc, MapArt.alpha(self.mint, 225), 1.6, 100, 4)
            self.dashed(Ellipse2D.Double((p.x - 29), (p.y - 29), 58, 58), MapArt.alpha(self.mint, 80), 1, 3, 5)
            ticks = Path2D.Double()
            for k in range(4):
                a = ((k * math.pi) / 2)
                ticks.append(Line2D.Double((p.x + (math.cos(a) * (r + 3))), (p.y + (math.sin(a) * (r + 3))), (p.x + (math.cos(a) * (r + 9))), (p.y + (math.sin(a) * (r + 9)))), False)
            self.draw(ticks, MapArt.alpha(self.mint, 170), 1.4)
            plus = Path2D.Double()
            plus.append(Line2D.Double((p.x - 6), p.y, (p.x + 6), p.y), False)
            plus.append(Line2D.Double(p.x, (p.y - 6), p.x, (p.y + 6)), False)
            self.draw(plus, MapArt.alpha(self.mint, 170), 1.6)
            self.label('CAPACITOR PAD', p.x, ((p.y + r) + 16), self.mint)
    class Monolith(Painter):
        """The Legacy Monolith: a dark server hall in steel blue. Far layer: faint rack seams; the four floors (the venting
mechanic) are framed by neon divider lines and side-rail vent slots, cold cyan on floors 1-2 and amber on the hot floors
3-4; the chassis (which block line of sight) are dark blades with cyan neon outlines, outlined drive bays and a few
lit LEDs. Set dressing: full blade faceplates (handle, vented bays, activity LEDs, load display, grille, blade number),
the rack's header (name plate, LED strip, power readout), fans, cable runs, patch panels, grilles, floor vents and
perforated plates."""
        def __init__(self, lm, g):
            MapArt.Painter.__init__(self, lm, g, MapArt.c(0x080b12), MapArt.c(0x5aa8ff), MapArt.c(0x4f6f8f))
            self.lm = lm
            self.steel = MapArt.c(0x6f7a8c)
            self.cold = MapArt.c(0x5aa8ff)
            self.amber = MapArt.c(0xffb43b)
            self.led = MapArt.c(0x5ce07a)
        def heat(self, i):
            return (self.cold if (i < 2) else self.amber)
        def edge_colour(self):
            return Cyber.lerp(self.cold, Color.WHITE, 0.1)
        def paint_map(self):
            floors = self.lm.get_floors()
            ys = [f[0] for f in floors] + [floors[(len(floors) - 1)][1]]
            self.begin_soft()
            self.ground(MapArt.c(0x0b0f19), MapArt.c(0x05070b), 0, MapArt.H)
            self.soft_light(600, 450, 620, Color(90, 168, 255, 14))
            for i in range(len(floors)):
                f = floors[i]
                self.g.set_paint(GradientPaint(0, f[0], MapArt.alpha(self.heat(i), 13), 0, f[1], MapArt.alpha(self.heat(i), 0)))
                self.g.fill(Rectangle2D.Double(30, f[0], (MapArt.W - 60), (f[1] - f[0])))
            for x0 in [18, (MapArt.W - 18)]:
                self.blur(Line2D.Double(x0, 0, x0, MapArt.H), MapArt.alpha(self.steel, 20), 3, 3.5)
            for k in range(len(ys)):
                self.blur(Line2D.Double(30, ys[k], (MapArt.W - 30), ys[k]), MapArt.alpha((self.cold if (k < 2) else self.amber), 50), 3, 3.5)
            self.track_glow(75)
            self.end_soft()
            seams = Path2D.Double()
            x = 70.0
            while x < (MapArt.W - 30):
                seams.append(Line2D.Double(x, floors[0][0], x, floors[(len(floors) - 1)][1]), False)
                x += 40
            self.draw(seams, Color(255, 255, 255, 5), 1)
            rails = Path2D.Double()
            for x0 in [18, (MapArt.W - 18)]:
                rails.append(Line2D.Double(x0, 0, x0, MapArt.H), False)
            self.draw(rails, MapArt.alpha(self.steel, 80), 1)
            for i in range(len(floors)):
                f = floors[i]
                slots = Path2D.Double()
                yy = (f[0] + 14)
                while yy < (f[1] - 10):
                    slots.append(Line2D.Double(6, yy, 13, yy), False)
                    slots.append(Line2D.Double((MapArt.W - 13), yy, (MapArt.W - 6), yy), False)
                    yy += 9
                self.draw(slots, MapArt.alpha(self.heat(i), 70), 1.2)
            for k in range(len(ys)):
                col = (self.cold if (k < 2) else self.amber)
                self.draw(Line2D.Double(30, ys[k], (MapArt.W - 30), ys[k]), MapArt.alpha(col, 120), 1)
                ticks = Path2D.Double()
                tx = 100.0
                while tx < (MapArt.W - 30):
                    ticks.append(Line2D.Double(tx, (ys[k] - 3), tx, (ys[k] + 3)), False)
                    tx += 100
                self.draw(ticks, MapArt.alpha(col, 80), 1)
            if self.detail:
                self.hall_details()
            n = 0
            for o in self.map.get_obstacles():
                self.blade(o, n)
                n += 1
            self.track(0.5)
            for i in range(len(floors)):
                self.label_right(_j.cat('FLOOR ', (i + 1)), 1086, (floors[i][0] + 14), self.heat(i))
        # ------------------------------------------------------------------ set dressing: the server hall
        def layout(self):
            """Fans, cable runs, patch panels and vent grilles in the free pockets between the blades (above and below
each floor divider), the rack's header panel and the floor vents at the bottom."""
            lay = {'fans': [], 'cables': [], 'panels': [], 'grilles': []}
            floors = self.lm.get_floors()
            for i in range(3):
                mid = floors[(i + 1)][0]
                up = (mid - 24)
                down = (mid + 24)
                for x, y, kind in ((215, up, 'fan'), (600, up, 'cable'), (215, down, 'panel'), (985, down, 'fan'),
                                   (985, up, 'grille'), (600, down, 'grille')):
                    x += (((i % 2) * 2) - 1) * 18 if kind == 'fan' else 0
                    hw = {'fan': 13, 'cable': 16, 'panel': 42, 'grille': 40}[kind]
                    hh = {'fan': 13, 'cable': 16, 'panel': 7, 'grille': 8}[kind]
                    if (kind == 'cable') or self.box_clear((x - hw), (y - hh), (x + hw), (y + hh)):
                        self.taken.append((x, y, hh))
                        if kind == 'fan':
                            lay['fans'].append((x, y))
                        elif kind == 'cable':
                            lay['cables'].append((500, (mid - 32), 700, (mid - 32)))
                        elif kind == 'panel':
                            lay['panels'].append((x, y))
                        else:
                            lay['grilles'].append((x, y))
            lay['header'] = ((160, 10, 880, 28) if self.deco_clear(600, 24, 14) else None)
            lay['vents'] = (858 if self.deco_clear(600, 874, 14) else None)
            return lay
        def hall_details(self):
            """The hall's small things as dim line art: perforated floor plates, the rack header (a name plate, a strip of
status LEDs, a power readout), cable runs between the blades, fans, patch panels, vent grilles and floor vents."""
            lay = self.lay
            steel = self.steel
            if self.fine:
                old = self.g.get_clip()
                self.g.clip(self.deco_area())
                self.dot_grid(12, Color(170, 200, 255, 9), 1.0)
                self.g.set_clip(old)
            hd = lay['header']
            if hd is not None:
                x, y, w, h = hd
                plate = RoundRectangle2D.Double(x, y, w, h, 4, 4)
                self.fill(plate, MapArt.c(0x080b12))
                self.draw(plate, MapArt.alpha(steel, 70), 1)
                screws = Path2D.Double()
                for sx in ((x + 8), ((x + w) - 8)):
                    screws.append(Ellipse2D.Double((sx - 2.5), ((y + (h / 2)) - 2.5), 5, 5), False)
                self.draw(screws, MapArt.alpha(steel, 70), 0.9)
                f = Cyber.mono(Font.BOLD, 9)
                self.mark('RACK 07 \u00b7 42U', (x + 20), ((y + (h / 2)) + 3.5), f, MapArt.alpha(steel, 140))
                leds = {}
                for i in range(18):
                    c = (self.amber if ((i % 7) == 3) else (MapArt.c(0xff5a6a) if ((i % 11) == 5) else self.led))
                    leds.setdefault(c.get_rgb(), (c, Path2D.Double()))[1].append(Rectangle2D.Double(((x + 330) + (i * 12)), ((y + (h / 2)) - 1.5), 6, 3), False)
                for c, pth in leds.values():
                    self.blur(pth, MapArt.alpha(c, 50), 2)
                    self.fill(pth, MapArt.alpha(c, 115))
                lcd = RoundRectangle2D.Double(((x + w) - 128), (y + 5), 108, (h - 10), 3, 3)
                self.fill(lcd, MapArt.c(0x04100a))
                self.draw(lcd, MapArt.alpha(self.led, 60), 0.9)
                self.mark('PWR A+B OK', ((x + w) - 120), ((y + (h / 2)) + 3.5), f, MapArt.alpha(self.led, 120))
            if lay['vents'] is not None:
                slots = Path2D.Double()
                vx = 150.0
                while vx < 1050:
                    slots.append(RoundRectangle2D.Double(vx, lay['vents'], 6, 26, 3, 3), False)
                    vx += 13
                self.draw(slots, MapArt.alpha(steel, 45), 0.9)
            for x0, y0, x1, y1 in lay['cables']:
                cols = (MapArt.c(0x2b6cff), MapArt.c(0xff8a2b), MapArt.c(0x2bd67b), MapArt.c(0x8a5cff))
                for k in range(4):
                    cab = Path2D.Double()
                    cab.move_to(x0, (y0 + (k * 3)))
                    cab.curve_to((x0 + 60), ((y0 + 16) + (k * 2)), (x1 - 60), ((y0 + 16) + (k * 2)), x1, (y1 + (k * 3)))
                    self.draw(cab, MapArt.alpha(cols[k], 70), 1.1)
            for x, y in lay['fans']:
                self.fan_art(x, y, 13, self.cold, 80)
            for x, y in lay['panels']:
                body = RoundRectangle2D.Double((x - 42), (y - 7), 84, 14, 2, 2)
                self.fill(body, MapArt.c(0x070a11))
                self.draw(body, MapArt.alpha(steel, 75), 0.9)
                ports = Path2D.Double()
                for k in range(8):
                    ports.append(Rectangle2D.Double(((x - 36) + (k * 9.5)), (y - 3), 6, 5), False)
                self.draw(ports, MapArt.alpha(self.cold, 60), 0.8)
            for x, y in lay['grilles']:
                body = RoundRectangle2D.Double((x - 40), (y - 8), 80, 16, 3, 3)
                self.fill(body, MapArt.c(0x070a11))
                self.draw(body, MapArt.alpha(steel, 70), 0.9)
                old = self.g.get_clip()
                self.g.clip(body)
                slots = Path2D.Double()
                sx = (x - 56)
                while sx < (x + 40):
                    slots.append(Line2D.Double(sx, (y + 8), (sx + 16), (y - 8)), False)
                    sx += 6
                self.draw(slots, MapArt.alpha(steel, 45), 1)
                self.g.set_clip(old)
        def blade(self, o, idx):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = RoundRectangle2D.Double(x, y, w, h, 5, 5)
            self.fill(body, MapArt.c(0x070a11))
            self.neon(body, MapArt.alpha(self.cold, 195), 1.2, 60)
            if self.detail:
                self.blade_detail(o, idx)
                return
            bays = Path2D.Double()
            for i in range(6):
                bays.append(RoundRectangle2D.Double(((x + 18) + (i * 18)), (y + 12), 12, (h - 24), 2, 2), False)
            self.draw(bays, MapArt.alpha(self.steel, 70), 1)
            r = _j.Random(((idx * 31) + 7))
            leds = Path2D.Double()
            for i in range(6):
                if r.next_double() < 0.5:
                    leds.append(Rectangle2D.Double(((x + 21) + (i * 18)), ((y + h) - 17), 6, 2), False)
            self.blur(leds, MapArt.alpha(self.led, 130), 2.5)
            self.fill(leds, MapArt.alpha(self.led, 220))
            self.draw(RoundRectangle2D.Double((x + 134), (y + 12), 52, (h - 24), 3, 3), MapArt.alpha(self.steel, 80), 1)
            load = (0.3 + (0.6 * r.next_double()))
            self.fill(Rectangle2D.Double((x + 140), ((y + h) - 22), (40 * load), 3), MapArt.alpha(self.cold, 170))
        def blade_detail(self, o, idx):
            """A blade's faceplate in full: handle and grip, six drive bays with vents and activity LEDs, the load display
(a percentage and a bar), a vent grille, a status LED and the blade's number."""
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            steel = self.steel
            handle = RoundRectangle2D.Double((x + 5), (y + 10), 8, (h - 20), 3, 3)
            grip = Path2D.Double()
            gy = (y + 16)
            while gy < ((y + h) - 14):
                grip.append(Line2D.Double((x + 7), gy, (x + 11), gy), False)
                gy += 5
            self.draw(handle, MapArt.alpha(steel, 70), 0.9)
            self.draw(grip, MapArt.alpha(steel, 55), 0.9)
            bays = Path2D.Double()
            vents = Path2D.Double()
            for i in range(6):
                bx = ((x + 20) + (i * 18))
                bays.append(RoundRectangle2D.Double(bx, (y + 10), 12, (h - 32), 2, 2), False)
                vy = (y + 15)
                while vy < ((y + h) - 26):
                    vents.append(Line2D.Double((bx + 3), vy, (bx + 9), vy), False)
                    vy += 4
            self.draw(bays, MapArt.alpha(steel, 70), 1)
            self.draw(vents, MapArt.alpha(steel, 32), 0.8)
            r = _j.Random(((idx * 31) + 7))
            green = Path2D.Double()
            amber = Path2D.Double()
            for i in range(6):
                v = r.next_double()
                if v < 0.62:
                    (amber if (v < 0.12) else green).append(Rectangle2D.Double(((x + 23) + (i * 18)), ((y + h) - 19), 6, 2), False)
            self.blur(green, MapArt.alpha(self.led, 110), 2.2)
            self.fill(green, MapArt.alpha(self.led, 210))
            self.blur(amber, MapArt.alpha(self.amber, 110), 2.2)
            self.fill(amber, MapArt.alpha(self.amber, 210))
            load = (40 + r.next_int(58))
            hot = (load > 85)
            lc = (self.amber if hot else MapArt.c(0x7fd6ff))
            lcd = RoundRectangle2D.Double((x + 134), (y + 10), 54, 24, 3, 3)
            self.fill(lcd, MapArt.c(0x04101a))
            self.draw(lcd, MapArt.alpha(steel, 90), 1)
            self.mark(_j.cat(load, '%'), (x + 140), (y + 25), Cyber.mono(Font.BOLD, 11), MapArt.alpha(lc, 175))
            self.fill(Rectangle2D.Double((x + 140), (y + 28), ((42 * load) / 100.0), 2), MapArt.alpha(lc, 150))
            grille = RoundRectangle2D.Double((x + 134), (y + 39), 54, ((h - 39) - 10), 3, 3)
            self.draw(grille, MapArt.alpha(steel, 70), 0.9)
            old = self.g.get_clip()
            self.g.clip(grille)
            slots = Path2D.Double()
            sx = (x + 110)
            while sx < (x + 190):
                slots.append(Line2D.Double(sx, ((y + h) - 10), (sx + 30), (y + 39)), False)
                sx += 5
            self.draw(slots, MapArt.alpha(steel, 40), 1)
            self.g.set_clip(old)
            st = Ellipse2D.Double(((x + w) - 9), (y + 7), 4, 4)
            self.blur(st, MapArt.alpha(self.led, 110), 2.5)
            self.fill(st, MapArt.alpha(self.led, 220))
            self.mark(o.label, (x + 20), ((y + h) - 6), Cyber.mono(Font.BOLD, 9), MapArt.alpha(steel, 150))
    class Canyon(Painter):
        """The Hallucination Canyon: a violet void. Far layer: faint attention ripples around the hub and a faint
constellation; the chasms (which block placement) are black holes in the ground with a pink neon rim, light falling
into them and stars far below; the bridge nodes are neon hexagons and the attention hub a glowing ringed disc. Set
dressing: depth lines inside the chasms, glitch shards on their rims, cracks and rock debris near them, and floating
fragments of broken geometry (shards, open hexagons, wireframe cubes with a ghost) in the void."""
        def __init__(self, hc, g):
            MapArt.Painter.__init__(self, hc, g, MapArt.c(0x1b1430), MapArt.c(0xb48cff), MapArt.c(0x8f7fcf))
            self.hc = hc
            self.violet = MapArt.c(0xb48cff)
            self.pink = MapArt.c(0xff8cf0)
            self.pale = MapArt.c(0xe0c8ff)
        def extra_clear(self, x, y, r):
            p = Vec(x, y)
            if p.dist(self.hc.get_center()) < (70 + r):
                return False
            for n in self.hc.get_nodes():
                if p.dist(n.pos) < (40 + r):
                    return False
            return True
        def edge_colour(self):
            return Cyber.lerp(self.violet, Color.WHITE, 0.35)
        def paint_map(self):
            c = self.hc.get_center()
            self.begin_soft()
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), 780.0, [0.0, 1.0], [MapArt.c(0x1e1338), MapArt.c(0x06040d)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            for n in self.hc.get_nodes():
                self.soft_light(n.pos.x, n.pos.y, 70, Color(180, 140, 255, 36))
            self.soft_light(c.x, c.y, 170, Color(190, 140, 255, 50))
            self.track_glow(80)
            self.end_soft()
            ripples = Path2D.Double()
            for r in [150, 250, 360, 480, 610]:
                ripples.append(Ellipse2D.Double((c.x - r), (c.y - r), (2 * r), (2 * r)), False)
            self.dashed(ripples, MapArt.alpha(self.pale, 16), 1, 2, 9)
            self.constellation(26, MapArt.alpha(self.pale, 18), MapArt.alpha(self.pale, 70), 260)
            if self.detail:
                self.void_details()
            for o in self.map.get_obstacles():
                self.chasm(o)
            if self.detail:
                self.shards()
            self.track(0.55)
            for n in self.hc.get_nodes():
                self.node(n)
            self.hub(c)
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
            self.blur(jag, MapArt.alpha(self.pink, 110), 5, 3)
            self.fill(jag, MapArt.c(0x020106))
            old = self.g.get_clip()
            self.g.clip(jag)
            self.blur(jag, MapArt.alpha(self.violet, 120), 9, 8)
            if self.detail:
                cx = (o.x + (o.w / 2))
                cy = (o.y + (o.h / 2))
                depth = Path2D.Double()
                for i in range(1, 8):
                    fx = (o.x + ((o.w * i) / 8.0))
                    depth.append(Line2D.Double(fx, o.y, (cx + ((fx - cx) * 0.3)), (cy - (o.h * 0.15))), False)
                    depth.append(Line2D.Double(fx, (o.y + o.h), (cx + ((fx - cx) * 0.3)), (cy + (o.h * 0.15))), False)
                for k in (0.62, 0.38):
                    depth.append(Rectangle2D.Double((cx - ((o.w * k) / 2)), (cy - ((o.h * k) / 2)), (o.w * k), (o.h * k)), False)
                self.draw(depth, MapArt.alpha(self.violet, 22), 0.9)
            self.g.set_clip(old)
            self.stars(jag, _j.to_int(((o.w * o.h) / 2000)), self.violet, 120)
            self.draw(jag, MapArt.alpha(self.pink, 215), 1.3)
        # ------------------------------------------------------------------ set dressing: debris in the void
        def layout(self):
            """Cracks running from the chasm rims into the open ground, rock debris near the rims, glitch shards on the
rims and floating fragments of broken geometry in the void."""
            lay = {'cracks': [], 'debris': [], 'shards': [], 'frags': []}
            obs = self.map.get_obstacles()
            for o in obs:
                for k in range(_j.to_int((((o.w + o.h) / 120) + 2))):
                    top = self.drnd.next_boolean()
                    w = (14 + (self.drnd.next_double() * 34))
                    x = (o.x + (self.drnd.next_double() * max(1.0, (o.w - w))))
                    y = ((o.y - 5) if top else ((o.y + o.h) + 3))
                    y += ((self.drnd.next_double() - 0.5) * 6)
                    if self.box_clear(x, (y - 2), (x + w), (y + 3), False):
                        lay['shards'].append((x, y, w, (1.2 + (self.drnd.next_double() * 1.6)), self.drnd.next_boolean()))
            for i in range(12):
                o = obs[(i % len(obs))]
                side = self.drnd.next_int(4)
                t = self.drnd.next_double()
                x, y, dx, dy = ((o.x + (t * o.w), o.y, 0, -1), ((o.x + o.w), o.y + (t * o.h), 1, 0),
                                (o.x + (t * o.w), (o.y + o.h), 0, 1), (o.x, o.y + (t * o.h), -1, 0))[side]
                pts = [(x, y)]
                ln = (26 + (self.drnd.next_double() * 60))
                d = 0.0
                ok = True
                while d < ln:
                    d += 7
                    j = ((self.drnd.next_double() - 0.5) * 7)
                    q = ((x + (dx * d)) - (dy * j), (y + (dy * d)) + (dx * j))
                    if not self.deco_clear(q[0], q[1], 1, False):
                        ok = (d > 20)
                        break
                    pts.append(q)
                if ok and (len(pts) > 3):
                    lay['cracks'].append(pts)
                    for q in pts[2::3]:
                        self.taken.append((q[0], q[1], 3))
            for i in range(14):
                o = obs[(i % len(obs))]
                for _ in range(40):
                    x = ((o.x - 30) + (self.drnd.next_double() * (o.w + 60)))
                    y = ((o.y - 30) + (self.drnd.next_double() * (o.h + 60)))
                    r = (4 + (self.drnd.next_double() * 6))
                    if self.deco_clear(x, y, r):
                        self.taken.append((x, y, r))
                        lay['debris'].append((x, y, r, self.drnd.next_double() * 6.28))
                        break
            lay['cubes'] = []
            for i in range(6):
                p = self.spot(28)
                if p is not None:
                    lay['cubes'].append((p[0], p[1], (15 + (self.drnd.next_double() * 8)), self.drnd.next_int(9)))
            for i in range(24):
                p = self.spot(14)
                if p is not None:
                    lay['frags'].append((('sq', 'tri', 'hex', 'dash', 'sq', 'hex')[(i % 6)], p[0], p[1], (7 + (self.drnd.next_double() * 7)), (self.drnd.next_double() * 360)))
            return lay
        def void_details(self):
            lay = self.lay
            cr = Path2D.Double()
            for pts in lay['cracks']:
                MapArt.polyline(pts, cr)
            self.draw(cr, MapArt.alpha(self.pink, 42), 0.9)
            rocks = Path2D.Double()
            for x, y, r, a0 in lay['debris']:
                for k in range(5):
                    a = (a0 + ((k * math.pi * 2) / 5))
                    rr = (r * (0.65 + (0.35 * ((k * 7) % 3) / 2.0)))
                    (rocks.move_to if (k == 0) else rocks.line_to)((x + (math.cos(a) * rr)), (y + (math.sin(a) * rr)))
                rocks.close_path()
            self.fill(rocks, MapArt.c(0x0b0718))
            self.draw(rocks, MapArt.alpha(self.pale, 60), 0.9)
            if not self.fine:
                return
            frags = Path2D.Double()
            for kind, x, y, s, rot in lay['frags']:
                a0 = math.radians(rot)
                if kind == 'dash':
                    for k in (-1, 1):
                        ox = ((-math.sin(a0) * k) * 2.5)
                        oy = ((math.cos(a0) * k) * 2.5)
                        frags.append(Line2D.Double(((x + ox) - (math.cos(a0) * s)), ((y + oy) - (math.sin(a0) * s)), ((x + ox) + (math.cos(a0) * s * (0.4 if (k > 0) else 1))), ((y + oy) + (math.sin(a0) * s * (0.4 if (k > 0) else 1)))), False)
                    continue
                n, keep = {'sq': (4, 4), 'tri': (3, 3), 'hex': (6, 4)}[kind]
                for k in range((keep + 1)):
                    if (keep == n) and (k == keep):
                        break
                    a = (a0 + ((k * math.pi * 2) / n))
                    (frags.move_to if (k == 0) else frags.line_to)((x + (math.cos(a) * s)), (y + (math.sin(a) * s)))
                if keep == n:
                    frags.close_path()
            self.blur(frags, MapArt.alpha(self.violet, 40), 2.5, 1)
            self.draw(frags, MapArt.alpha(self.pale, 72), 0.9)
            cubes = Path2D.Double()
            ghost = Path2D.Double()
            for x, y, r, gap in lay['cubes']:
                # an isometric wireframe cube with one edge missing, and its faint offset ghost (a hallucination)
                c30 = (math.cos(math.radians(30)) * r)
                top = [(x, (y - r)), ((x + c30), (y - (r / 2))), (x, y), ((x - c30), (y - (r / 2)))]
                bot = [(px, (py + r)) for px, py in top]
                edges = ([(top[k], top[((k + 1) % 4)]) for k in range(4)] + [(bot[k], bot[((k + 1) % 4)]) for k in (1, 2)]
                         + [(top[k], bot[k]) for k in (1, 2, 3)])
                for k, (a, b) in enumerate(edges):
                    if k != gap:
                        cubes.append(Line2D.Double(a[0], a[1], b[0], b[1]), False)
                    if (k % 3) == 0:
                        ghost.append(Line2D.Double((a[0] + 5), (a[1] - 4), (b[0] + 5), (b[1] - 4)), False)
            self.blur(cubes, MapArt.alpha(self.violet, 34), 3, 1)
            self.draw(cubes, MapArt.alpha(self.pale, 58), 0.9)
            self.draw(ghost, MapArt.alpha(self.pink, 34), 0.8)
        def shards(self):
            """Glitch shards: thin offset bars flaking off the chasm rims, in pink and cyan."""
            pink = Path2D.Double()
            cyan = Path2D.Double()
            for x, y, w, h, p in self.lay['shards']:
                (pink if p else cyan).append(Rectangle2D.Double(x, y, w, h), False)
            self.fill(pink, MapArt.alpha(self.pink, 95))
            self.fill(cyan, MapArt.alpha(MapArt.c(0x5fe8ff), 80))
        def node(self, n):
            p = n.pos
            hexa = MapArt.hexagon(p.x, p.y, 30, 0)
            self.fill(hexa, MapArt.alpha(MapArt.c(0x160c2e), 235))
            self.neon(hexa, MapArt.alpha(self.violet, 225), 1.4, 90)
            self.draw(MapArt.hexagon(p.x, p.y, 19, 0), MapArt.alpha(self.violet, 80), 1)
            self.fill(Ellipse2D.Double((p.x - 3), (p.y - 3), 6, 6), MapArt.alpha(self.pale, 220))
        def hub(self, c):
            self.dashed(Ellipse2D.Double((c.x - 64), (c.y - 64), 128, 128), MapArt.alpha(self.pale, 70), 1, 3, 5)
            self.neon(Ellipse2D.Double((c.x - 50), (c.y - 50), 100, 100), MapArt.alpha(self.pink, 150), 1.2, 60)
            disc = Ellipse2D.Double((c.x - 40), (c.y - 40), 80, 80)
            self.fill(disc, MapArt.c(0x1b1037))
            self.neon(disc, MapArt.alpha(self.pale, 225), 1.6, 100)
            core = MapArt.hexagon(c.x, c.y, 9, 30)
            self.blur(core, MapArt.alpha(self.pink, 140), 5)
            self.fill(core, MapArt.alpha(self.pale, 225))
    class Singularity(Painter):
        """The Singularity Core: deep space. Far layer: two faint nebula lights, stars and the vortex (spiral arms and
dashed orbits, inside the arena); the arena has a neon rim with a dial of ticks, the four portals are magenta-lit neon
hexagons and the event horizon a black core in a hot accretion ring. Set dressing, all outside the arena: a denser
star field with a few glints, a ringed planet, a far spiral galaxy, a satellite, orbiting debris on a faint orbit and
energy arcs leaping off the rim."""
        def __init__(self, sc, g):
            MapArt.Painter.__init__(self, sc, g, MapArt.c(0x030208), MapArt.c(0x8a6cff), MapArt.c(0x7a5fe0))
            self.sc = sc
            self.violet = MapArt.c(0xb090ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.hot = MapArt.c(0xffc46a)
            self.R = SingularityCore.ARENA_RADIUS
        def extra_clear(self, x, y, r):
            d = Vec(x, y).dist(self.sc.get_center())
            return (d <= ((self.R - 24) - r)) and (d >= (76 + r))
        def edge_colour(self):
            return Cyber.lerp(self.f_track, Color.WHITE, 0.35)
        def paint_map(self):
            c = self.sc.get_center()
            R = self.R
            arena = Ellipse2D.Double((c.x - R), (c.y - R), (2 * R), (2 * R))
            self.begin_soft()
            self.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H), self.bg)
            self.soft_light(250, 170, 440, Color(255, 75, 216, 16))
            self.soft_light(990, 760, 480, Color(138, 108, 255, 22))
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), R, [0.0, 0.35, 1.0], [MapArt.c(0x26114a), MapArt.c(0x150a2c), MapArt.c(0x0a0517)], MultipleGradientPaint.CycleMethod.NO_CYCLE))
            self.g.fill(arena)
            self.blur(arena, MapArt.alpha(self.violet, 110), 5, 4.1)
            for rt in self.map.get_routes():
                s = rt.get_start()
                self.soft_light(s.x, s.y, 78, Color(255, 75, 216, 44))
            self.track_glow(80)
            self.end_soft()
            outside = Area(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            outside.subtract(Area(arena))
            self.stars(outside, 150, self.violet)
            if self.detail:
                self.space_details(c)
            old = self.g.get_clip()
            self.g.clip(arena)
            self.draw(self.spiral_arms(c), MapArt.alpha(self.violet, 22), 1.2)
            orbits = Path2D.Double()
            r = 90.0
            while r < R:
                orbits.append(Ellipse2D.Double((c.x - r), (c.y - r), (2 * r), (2 * r)), False)
                r += 90
            self.dashed(orbits, MapArt.alpha(self.violet, 16), 1, 2, 7)
            self.g.set_clip(old)
            self.draw(arena, MapArt.alpha(self.violet, 210), 1.6)
            self.draw(Ellipse2D.Double(((c.x - R) - 9), ((c.y - R) - 9), ((2 * R) + 18), ((2 * R) + 18)), MapArt.alpha(self.violet, 50), 1)
            ticks = Path2D.Double()
            for k in range(60):
                a = math.radians((k * 6))
                ticks.append(Line2D.Double((c.x + (math.cos(a) * (R + 3))), (c.y + (math.sin(a) * (R + 3))), (c.x + (math.cos(a) * (R + 8))), (c.y + (math.sin(a) * (R + 8)))), False)
            self.draw(ticks, MapArt.alpha(self.violet, 70), 1)
            self.track(0.55)
            for rt in self.map.get_routes():
                self.portal(rt.get_start())
            self.horizon(c)
        # ------------------------------------------------------------------ set dressing: deep space
        def deco_extra(self, x, y, r):
            """Space details stay outside the arena (which is all play area) and its dial."""
            return Vec(x, y).dist(self.sc.get_center()) >= ((self.R + 30) + r)
        def layout(self):
            """A ringed planet, a far spiral galaxy and a satellite in the corners, a field of orbiting debris on a faint
orbit around the core, and energy arcs leaping off the arena rim between the portals."""
            c = self.sc.get_center()
            lay = {'planet': None, 'galaxy': None, 'sat': None, 'rocks': [], 'arcs': [], 'stars': []}
            for key, x, y, r in (('planet', 100, 118, 78), ('galaxy', 1096, 790, 60), ('sat', 1105, 105, 26)):
                if self.deco_clear(x, y, r):
                    self.taken.append((x, y, r))
                    lay[key] = (x, y)
            for i in range(80):
                a = (self.drnd.next_double() * math.pi * 2)
                rr = (0.92 + (self.drnd.next_double() * 0.16))
                x = (c.x + (math.cos(a) * 650 * rr))
                y = (c.y + (math.sin(a) * 485 * rr))
                r = (2.5 + (self.drnd.next_double() * 4.5))
                if self.deco_clear(x, y, r):
                    self.taken.append((x, y, r))
                    lay['rocks'].append((x, y, r, (self.drnd.next_double() * 6.28)))
                if len(lay['rocks']) >= 22:
                    break
            for deg in (24, 62, 116, 154, 206, 244, 296, 334):
                a0 = math.radians((deg + ((self.drnd.next_double() - 0.5) * 8)))
                span = math.radians((7 + (self.drnd.next_double() * 7)))
                lift = (18 + (self.drnd.next_double() * 22))
                pts = []
                ok = True
                for k in range(17):
                    f = (k / 16.0)
                    a = (a0 + (span * f))
                    r = (((self.R + 10) + (lift * math.sin((math.pi * f)))) + (((self.drnd.next_double() - 0.5) * 2.4) if (0 < k < 16) else 0))
                    x = (c.x + (math.cos(a) * r))
                    y = (c.y + (math.sin(a) * r))
                    if MapArt.track_distance(self.map, x, y) < (MapArt.HW + MapArt.STRIP):
                        ok = False
                        break
                    pts.append((x, y))
                if ok:
                    lay['arcs'].append(pts)
            for i in range(240):
                x = (self.drnd.next_double() * MapArt.W)
                y = (self.drnd.next_double() * MapArt.H)
                if (Vec(x, y).dist(c) > (self.R + 22)) and (MapArt.track_distance(self.map, x, y) > ((MapArt.HW + MapArt.STRIP) + 2)):
                    lay['stars'].append((x, y, (0.4 + (self.drnd.next_double() * 0.6)), (self.drnd.next_double() < 0.04)))
            return lay
        def space_details(self, c):
            lay = self.lay
            pale = MapArt.c(0xc8b8ff)
            dots = Path2D.Double()
            glints = Path2D.Double()
            for x, y, r, glint in lay['stars']:
                dots.append(Ellipse2D.Double((x - r), (y - r), (2 * r), (2 * r)), False)
                if glint:
                    glints.append(Line2D.Double((x - 4), y, (x + 4), y), False)
                    glints.append(Line2D.Double(x, (y - 4), x, (y + 4)), False)
            self.fill(dots, MapArt.alpha(pale, 55))
            self.draw(glints, MapArt.alpha(pale, 60), 0.8)
            outside = Area(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            outside.subtract(Area(Ellipse2D.Double(((c.x - self.R) - 24), ((c.y - self.R) - 24), ((2 * self.R) + 48), ((2 * self.R) + 48))))
            outside.subtract(self.track_area((MapArt.HW + MapArt.STRIP)))
            old = self.g.get_clip()
            self.g.clip(outside)
            self.dashed(Ellipse2D.Double((c.x - 650), (c.y - 485), 1300, 970), MapArt.alpha(self.violet, 26), 1, 3, 9)
            self.g.set_clip(old)
            rocks = Path2D.Double()
            for x, y, r, a0 in lay['rocks']:
                for k in range(6):
                    a = (a0 + ((k * math.pi * 2) / 6))
                    rr = (r * (0.7 + (0.3 * (((k * 5) % 4) / 3.0))))
                    (rocks.move_to if (k == 0) else rocks.line_to)((x + (math.cos(a) * rr)), (y + (math.sin(a) * rr)))
                rocks.close_path()
            self.fill(rocks, MapArt.c(0x0b0718))
            self.draw(rocks, MapArt.alpha(pale, 70), 0.9)
            arcs = Path2D.Double()
            for pts in lay['arcs']:
                MapArt.polyline(pts, arcs)
            self.blur(arcs, MapArt.alpha(self.magenta, 40), 2.5, 1)
            self.draw(arcs, MapArt.alpha(Cyber.lerp(self.magenta, self.violet, 0.45), 70), 0.9)
            if lay['planet'] is not None:
                self.planet(*lay['planet'])
            if lay['galaxy'] is not None:
                self.galaxy(*lay['galaxy'])
            if lay['sat'] is not None:
                self.satellite(*lay['sat'])
        def planet(self, x, y):
            """A ringed planet in line art: the far half of the ring, the dark globe with faint bands, then the ring's
near half over it; a small moon."""
            r = 34.0
            pale = MapArt.c(0xc8b8ff)
            ring = Ellipse2D.Double((x - 66), (y - 14), 132, 28)
            rot = self.rotated(x, y, (-18))
            self.draw(ring, MapArt.alpha(self.violet, 60), 1)
            self.draw(Ellipse2D.Double((x - 56), (y - 10), 112, 20), MapArt.alpha(self.violet, 34), 0.9)
            self.g.set_transform(rot)
            globe = Ellipse2D.Double((x - r), (y - r), (2 * r), (2 * r))
            self.blur(globe, MapArt.alpha(self.magenta, 30), 8)
            self.fill(globe, MapArt.c(0x0d0820))
            old = self.g.get_clip()
            self.g.clip(globe)
            bands = Path2D.Double()
            for k in range((-3), 4):
                bands.append(Ellipse2D.Double((x - (r * 1.4)), ((y + (k * 9)) - 4), (r * 2.8), 8), False)
            self.draw(bands, MapArt.alpha(pale, 22), 0.9)
            self.fill(Ellipse2D.Double(((x - r) + 12), ((y - r) + 8), (2 * r), (2 * r)), Color(2, 1, 8, 150))
            self.g.set_clip(old)
            self.draw(globe, MapArt.alpha(pale, 85), 1.1)
            rot = self.rotated(x, y, (-18))
            old = self.g.get_clip()
            self.g.clip(Rectangle2D.Double((x - 80), y, 160, 30))
            self.draw(ring, MapArt.alpha(self.violet, 90), 1.1)
            self.g.set_clip(old)
            self.g.set_transform(rot)
            moon = Ellipse2D.Double((x + 48), (y - 52), 10, 10)
            self.fill(moon, MapArt.c(0x0d0820))
            self.draw(moon, MapArt.alpha(pale, 80), 0.9)
        def galaxy(self, x, y):
            """A far spiral galaxy, tilted: two dotted arms around a soft core."""
            rot = self.rotated(x, y, 24)
            arms = Path2D.Double()
            for arm in range(2):
                th = 0.0
                first = True
                while th < 4.4:
                    rr = (8.5 * math.exp((0.42 * th)))
                    a = ((arm * math.pi) + th)
                    px = (x + (math.cos(a) * rr))
                    py = (y + ((math.sin(a) * rr) * 0.5))
                    (arms.move_to if first else arms.line_to)(px, py)
                    first = False
                    th += 0.12
            core = Ellipse2D.Double((x - 9), (y - 4.5), 18, 9)
            self.blur(core, MapArt.alpha(MapArt.c(0xffc4e8), 55), 6)
            self.draw(arms, MapArt.alpha(MapArt.c(0xc8b8ff), 46), 1)
            self.fill(core, MapArt.alpha(MapArt.c(0xffe6f4), 75))
            self.g.set_transform(rot)
        def satellite(self, x, y):
            """A small satellite: body, two solar wings with cell lines, a dish and a beacon (it blinks)."""
            rot = self.rotated(x, y, (-30))
            steel = MapArt.c(0xb0a8d8)
            body = RoundRectangle2D.Double((x - 6), (y - 5), 12, 10, 2, 2)
            wings = Path2D.Double()
            cells = Path2D.Double()
            for sx in (-1, 1):
                x0 = ((x + 9) if (sx > 0) else (x - 25))
                wings.append(Rectangle2D.Double(x0, (y - 5), 16, 10), False)
                cells.append(Line2D.Double((x0 + 5.3), (y - 5), (x0 + 5.3), (y + 5)), False)
                cells.append(Line2D.Double((x0 + 10.6), (y - 5), (x0 + 10.6), (y + 5)), False)
                cells.append(Line2D.Double(x0, y, (x0 + 16), y), False)
                wings.append(Line2D.Double((x + (6 * sx)), y, (x + (9 * sx)), y), False)
            self.fill(body, MapArt.c(0x0d0820))
            self.draw(body, MapArt.alpha(steel, 110), 1)
            self.draw(wings, MapArt.alpha(steel, 90), 0.9)
            self.draw(cells, MapArt.alpha(steel, 40), 0.8)
            self.draw(Arc2D.Double((x - 4), (y - 13), 8, 6, 180, 180, Arc2D.OPEN), MapArt.alpha(steel, 90), 0.9)
            self.fill(Ellipse2D.Double((x - 1.3), (y - 11.3), 2.6, 2.6), MapArt.alpha(MapArt.c(0xff5a8a), 170))
            self.g.set_transform(rot)
        def spiral_arms(self, c):
            """Six faint logarithmic spiral arms that wind inward the way the track does."""
            p = Path2D.Double()
            k = 0.2
            for arm in range(6):
                a0 = ((arm * math.pi) / 3)
                th = 0.0
                first = True
                while True:
                    r = (70 * math.exp((k * th)))
                    if r > self.R:
                        break
                    x = (c.x + (r * math.cos((a0 - th))))
                    y = (c.y + (r * math.sin((a0 - th))))
                    if first:
                        p.move_to(x, y)
                        first = False
                    else:
                        p.line_to(x, y)
                    th += 0.06
            return p
        def portal(self, p):
            hexa = MapArt.hexagon(p.x, p.y, 30, 0)
            self.fill(hexa, MapArt.alpha(MapArt.c(0x12082a), 240))
            self.neon(hexa, MapArt.alpha(MapArt.c(0xc0a0ff), 230), 1.4, 110, 4, self.magenta)
            self.draw(Ellipse2D.Double((p.x - 17), (p.y - 17), 34, 34), MapArt.alpha(self.magenta, 110), 1)
        def horizon(self, c):
            self.blur(Ellipse2D.Double((c.x - 50), (c.y - 50), 100, 100), MapArt.alpha(self.hot, 170), 7, 6)
            self.g.set_paint(RadialGradientPaint(Point2D.Double(c.x, c.y), 80.0, [0.0, 0.52, 0.62, 1.0], [Color(0, 0, 0, 255), Color(0, 0, 0, 255), Color(255, 196, 106, 120), Color(255, 75, 216, 0)]))
            self.g.fill(Ellipse2D.Double((c.x - 80), (c.y - 80), 160, 160))
            self.draw(Ellipse2D.Double((c.x - 44), (c.y - 44), 88, 88), MapArt.alpha(self.hot, 220), 1.6)
            self.draw(Ellipse2D.Double((c.x - 62), (c.y - 62), 124, 124), MapArt.alpha(self.magenta, 70), 1)
    class Valley(Painter):
        """Silicon Valley: a tech campus at night. Far layer: a faint street grid; the buildings (which block placement)
are neon-outlined architecture: dark roofs with a crisp outline in the building's accent (cyan HQs, magenta labs and
holo board, violet server farms, lime depots), a dim extruded facade with sparse lit windows, and one or two roof
details; the skybridges are thin glass rails over Innovation Drive. Set dressing: every roof in detail (helipads,
glass tiers, solar arrays, domes, a robot arm, fan grids, parking bays with cars and chargers), neon signs with the
buildings' names and the ad billboards ("SCALE IS ALL YOU NEED", "AGI SOON", "GPU CLOUD", "HIRE AN AI", "50% OFF"), and
on the ground a side street with street lights and parked cars, a park with trees and a pond, plazas and trees."""
        def __init__(self, sv, g):
            MapArt.Painter.__init__(self, sv, g, MapArt.c(0x0b1424), MapArt.c(0x5fd4ff), MapArt.c(0x3fb8ff))
            self.sv = sv
            self.cyan = MapArt.c(0x5fd4ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.violet = MapArt.c(0x8a7bff)
            self.lime = MapArt.c(0x7dffb0)
            self.glass = MapArt.c(0x9fdcff)
            self.warm = MapArt.c(0xffc46a)
        @staticmethod
        def kind(l):
            if 'HQ' in l:
                return 'hq'
            if 'LAB' in l:
                return 'lab'
            if ('SERVER' in l) or ('DATA' in l):
                return 'srv'
            if ('DEPOT' in l) or ('CHARGING' in l):
                return 'bay'
            if 'HOLO' in l:
                return 'holo'
            return 'hq'
        def accent_of(self, k):
            return {'hq': self.cyan, 'lab': self.magenta, 'srv': self.violet, 'bay': self.lime, 'holo': self.magenta}[k]
        def edge_colour(self):
            return Cyber.lerp(self.cyan, Color.WHITE, 0.2)
        def paint_map(self):
            self.begin_soft()
            self.ground(MapArt.c(0x0a1428), MapArt.c(0x04070f), 0, MapArt.H)
            self.soft_light(600, 450, 680, Color(60, 150, 255, 16))
            for o in self.map.get_obstacles():
                if MapArt.Valley.kind(('' if (o.label is None) else o.label)) == 'holo':
                    self.blur(Rectangle2D.Double(o.x, o.y, o.w, o.h), MapArt.alpha(self.magenta, 60), 14)
            self.track_glow(85)
            self.end_soft()
            self.grid(50, self.cyan, 5)
            self.grid(200, self.cyan, 9)
            if self.detail:
                self.campus_details()
            self.track(0.68)
            for o in self.map.get_obstacles():
                self.building(o)
            for b in self.sv.get_skybridges():
                self.skybridge(b)
        def building(self, o):
            l = ('' if (o.label is None) else o.label)
            k = MapArt.Valley.kind(l)
            acc = self.accent_of(k)
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            roof = Rectangle2D.Double(x, y, w, h)
            ex = 6.0
            ey = 9.0
            side = Path2D.Double()
            side.move_to(x, (y + h))
            side.line_to((x + w), (y + h))
            side.line_to((x + w), y)
            side.line_to(((x + w) + ex), (y + ey))
            side.line_to(((x + w) + ex), ((y + h) + ey))
            side.line_to((x + ex), ((y + h) + ey))
            side.close_path()
            self.fill(side, MapArt.c(0x03060d))
            self.draw(side, MapArt.alpha(acc, 45), 1)
            r = _j.Random((_j.hash_code(l) + _j.to_int(((x * 7) + y))))
            cool = Path2D.Double()
            warm = Path2D.Double()
            wx = ((x + (ex / 2)) + 4)
            while wx < (((x + w) + (ex / 2)) - 6):
                if r.next_double() < 0.24:
                    (warm if r.next_boolean() else cool).append(Rectangle2D.Double(wx, (((y + h) + (ey / 2)) - 1.5), 3, 3), False)
                wx += 7
            wy = ((y + (ey / 2)) + 4)
            while wy < (((y + h) + (ey / 2)) - 6):
                if r.next_double() < 0.2:
                    (warm if r.next_boolean() else cool).append(Rectangle2D.Double((((x + w) + (ex / 2)) - 1.5), wy, 3, 3), False)
                wy += 8
            self.blur(warm, MapArt.alpha(self.warm, 120), 2)
            self.blur(cool, MapArt.alpha(self.glass, 110), 2)
            self.fill(warm, MapArt.alpha(self.warm, 220))
            self.fill(cool, MapArt.alpha(self.glass, 220))
            self.fill(roof, MapArt.c(0x0a1428))
            if self.detail:
                self.roof(o, k, acc)
            elif k == 'hq':
                self.draw(Rectangle2D.Double((x + 10), (y + 10), (w - 20), (h - 20)), MapArt.alpha(acc, 60), 1)
                rr = (_j.dmin(w, h) * 0.2)
                cx = (x + (w / 2))
                cy = (y + (h / 2))
                self.draw(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)), MapArt.alpha(acc, 110), 1.2)
                hh = Path2D.Double()
                hh.append(Line2D.Double((cx - (rr * 0.4)), (cy - (rr * 0.5)), (cx - (rr * 0.4)), (cy + (rr * 0.5))), False)
                hh.append(Line2D.Double((cx + (rr * 0.4)), (cy - (rr * 0.5)), (cx + (rr * 0.4)), (cy + (rr * 0.5))), False)
                hh.append(Line2D.Double((cx - (rr * 0.4)), cy, (cx + (rr * 0.4)), cy), False)
                self.draw(hh, MapArt.alpha(acc, 120), 1.2)
            elif k == 'lab':
                rr = _j.dmin((w * 0.22), (h * 0.32))
                dome = Ellipse2D.Double(((x + (w * 0.68)) - rr), ((y + (h * 0.52)) - rr), (2 * rr), (2 * rr))
                self.blur(dome, MapArt.alpha(acc, 50), 6)
                self.fill(dome, MapArt.c(0x0d1430))
                self.draw(dome, MapArt.alpha(acc, 170), 1.2)
                self.draw(Ellipse2D.Double(((x + (w * 0.68)) - (rr * 0.55)), ((y + (h * 0.52)) - (rr * 0.55)), (rr * 1.1), (rr * 1.1)), MapArt.alpha(acc, 60), 1)
            elif k == 'srv':
                rows = Path2D.Double()
                leds = Path2D.Double()
                ry = (y + 14)
                while ry < ((y + h) - 8):
                    rows.append(Line2D.Double((x + 10), ry, ((x + w) - 14), ry), False)
                    if r.next_double() < 0.35:
                        leds.append(Rectangle2D.Double(((x + w) - 11), (ry - 1), 3, 2), False)
                    ry += 14
                self.draw(rows, MapArt.alpha(acc, 42), 1)
                self.fill(leds, MapArt.alpha(self.cyan, 220))
            elif k == 'bay':
                bays = Path2D.Double()
                lit = Path2D.Double()
                if h > w:
                    by = (y + 26)
                    while by < ((y + h) - 4):
                        bays.append(Line2D.Double((x + 6), by, ((x + w) - 6), by), False)
                        if r.next_double() < 0.4:
                            lit.append(Ellipse2D.Double(((x + (w / 2)) - 2), (by - 15), 4, 4), False)
                        by += 26
                else:
                    bx = (x + 26)
                    while bx < ((x + w) - 4):
                        bays.append(Line2D.Double(bx, (y + 6), bx, ((y + h) - 6)), False)
                        if r.next_double() < 0.4:
                            lit.append(Ellipse2D.Double((bx - 15), ((y + (h / 2)) - 2), 4, 4), False)
                        bx += 26
                self.draw(bays, MapArt.alpha(acc, 60), 1)
                self.blur(lit, MapArt.alpha(acc, 140), 3)
                self.fill(lit, MapArt.alpha(acc, 230))
            elif k == 'holo':
                screen = Rectangle2D.Double((x + 8), (y + 8), (w - 16), (h - 16))
                self.g.set_paint(GradientPaint(x, y, MapArt.alpha(self.magenta, 70), (x + w), (y + h), MapArt.alpha(self.violet, 30)))
                self.g.fill(screen)
                lines = Path2D.Double()
                ly = (y + 18)
                while ly < ((y + h) - 12):
                    lines.append(Line2D.Double((x + 16), ly, ((x + w) - 16), ly), False)
                    ly += 12
                self.draw(lines, MapArt.alpha(self.magenta, 50), 1)
            self.neon(roof, MapArt.alpha(acc, 220), 1.3, 80)
            if self.detail:
                self.signage(o, k, acc)
        # ------------------------------------------------------------------ set dressing: the campus
        ADS = {'AI RESEARCH LAB': ('AGI SOON', 0xff4bd8), 'SERVER FARM': ('GPU CLOUD', 0x5fd4ff),
               'NEXUS HQ': ('HIRE AN AI', 0xb9a8ff), 'CHARGING HUB': ('50% OFF', 0xff4bd8)}
        @staticmethod
        def ad(o):
            """The ad billboard on a building's roof, as (text, colour, x, y, size, align) or None. Only the second server
farm carries one."""
            l = ('' if (o.label is None) else o.label)
            v = MapArt.Valley.ADS.get(l)
            if (v is None) or ((l == 'SERVER FARM') and (o.x < 500)):
                return None
            if l == 'CHARGING HUB':
                return (v[0], v[1], ((o.x + o.w) - 7), (o.y + 6), 11, 'r')
            if 'LAB' in l:
                return (v[0], v[1], (o.x + 8), ((o.y + o.h) - 25), 12, 'l')
            return (v[0], v[1], (o.x + (o.w / 2)), ((o.y + o.h) - 27), 13, 'c')
        def layout(self):
            """The side street along the bottom edge (street lights, cars parked at the kerb), the park, plazas and
trees; all on open ground away from Innovation Drive and its tower strips."""
            lay = {'street': None, 'lamps': [], 'parked': [], 'park': None, 'park_trees': [], 'plazas': [], 'trees': []}
            sy = 874.0
            if self.box_clear(20, (sy - 12), (MapArt.W - 20), (sy + 12)):
                lay['street'] = sy
                x = 12.0
                while x < MapArt.W:
                    self.taken.append((x, sy, 16))
                    x += 24
                x = 70.0
                while x < MapArt.W:
                    lay['lamps'].append((x, (sy - 15)))
                    x += 160
                for x in (300.0, 326.0, 640.0, 960.0):
                    if self.deco_clear(x, (sy - 21), 9, True, False):
                        lay['parked'].append((x, (sy - 21)))
            for box in ((478, 170, 728, 282), (470, 180, 700, 270), (470, 190, 640, 280)):
                if self.box_clear(*box):
                    lay['park'] = box
                    x0, y0, x1, y1 = box
                    gx = (x0 + 18)
                    while gx < x1:
                        gy = (y0 + 18)
                        while gy < y1:
                            self.taken.append((gx, gy, 16))
                            gy += 26
                        gx += 26
                    pond = (x0 + ((x1 - x0) * 0.68), y0 + ((y1 - y0) * 0.55))
                    lay['pond'] = pond
                    for i in range(40):
                        tx = ((x0 + 12) + (self.drnd.next_double() * ((x1 - x0) - 24)))
                        ty = ((y0 + 12) + (self.drnd.next_double() * ((y1 - y0) - 24)))
                        if math.hypot(((tx - pond[0]) / 1.6), (ty - pond[1])) < 30:
                            continue
                        if abs((ty - (y0 + ((y1 - y0) * 0.42)))) < 9:
                            continue
                        if all((math.hypot((tx - t[0]), (ty - t[1])) > 20) for t in lay['park_trees']):
                            lay['park_trees'].append((tx, ty, (7 + (self.drnd.next_double() * 4))))
                        if len(lay['park_trees']) >= 9:
                            break
                    break
            for i in range(3):
                p = self.spot(30)
                if p is not None:
                    lay['plazas'].append((p[0], p[1], 28.0))
            for i in range(14):
                p = self.spot(10)
                if p is not None:
                    lay['trees'].append((p[0], p[1], (6.5 + (self.drnd.next_double() * 3))))
            return lay
        def tree(self, path, x, y, r):
            """A tree from above (added to path): a cloud-shaped crown (a union of lobes) and a small inner lobe."""
            crown = Area(Ellipse2D.Double((x - (r * 0.62)), (y - (r * 0.62)), (r * 1.24), (r * 1.24)))
            a0 = (x * 0.37)
            for k in range(5):
                a = (a0 + (((k * math.pi) * 2) / 5))
                cx = (x + ((math.cos(a) * r) * 0.45))
                cy = (y + ((math.sin(a) * r) * 0.45))
                crown.add(Area(Ellipse2D.Double((cx - (r * 0.55)), (cy - (r * 0.55)), (r * 1.1), (r * 1.1))))
            path.append(crown, False)
            path.append(Ellipse2D.Double(((x - (r * 0.25)) - (r * 0.18)), ((y - (r * 0.25)) - (r * 0.18)), (r * 0.36), (r * 0.36)), False)
        def campus_details(self):
            """The campus between the buildings: a side street with street lights and parked cars along the bottom, a
park with trees and a pond, hexagonal plazas and trees, as quiet line art."""
            lay = self.lay
            sy = lay['street']
            lime = Cyber.lerp(self.lime, MapArt.c(0x4fbf8a), 0.4)
            if sy is not None:
                road = Path2D.Double()
                road.append(Line2D.Double(0, (sy - 11), MapArt.W, (sy - 11)), False)
                road.append(Line2D.Double(0, (sy + 11), MapArt.W, (sy + 11)), False)
                self.fill(Rectangle2D.Double(0, (sy - 11), MapArt.W, 22), Color(4, 8, 16, 120))
                self.draw(road, MapArt.alpha(self.cyan, 50), 1)
                self.dashed(Line2D.Double(0, sy, MapArt.W, sy), MapArt.alpha(self.cyan, 34), 1, 10, 12)
                pools = Path2D.Double()
                heads = Path2D.Double()
                posts = Path2D.Double()
                for x, y in lay['lamps']:
                    pools.append(Ellipse2D.Double((x - 15), (y - 6), 30, 22), False)
                    heads.append(Ellipse2D.Double((x - 1.8), (y - 1.8), 3.6, 3.6), False)
                    posts.append(Line2D.Double(x, (y - 7), x, (y + 1)), False)
                self.blur(pools, Color(200, 235, 255, 26), 5)
                self.draw(posts, MapArt.alpha(self.cyan, 50), 1)
                self.blur(heads, Color(220, 245, 255, 55), 2)
                self.fill(heads, Color(210, 236, 255, 105))
                if self.fine:
                    bays = Path2D.Double()
                    for i, (x, y) in enumerate(lay['parked']):
                        bays.append(Line2D.Double((x - 13), (y - 6), (x - 13), (y + 7)), False)
                        bays.append(Line2D.Double((x + 13), (y - 6), (x + 13), (y + 7)), False)
                    self.draw(bays, MapArt.alpha(self.cyan, 40), 0.9)
                    for i, (x, y) in enumerate(lay['parked']):
                        self.car_art(x, y, (90 if (i % 2) else 270), (self.glass if (i % 3) else self.magenta), 85, False)
            if lay['park'] is not None:
                x0, y0, x1, y1 = lay['park']
                lawn = RoundRectangle2D.Double(x0, y0, (x1 - x0), (y1 - y0), 18, 18)
                self.fill(lawn, Color(20, 60, 40, 40))
                self.draw(lawn, MapArt.alpha(lime, 45), 1)
                path = Path2D.Double()
                py = (y0 + ((y1 - y0) * 0.42))
                path.move_to(x0, py)
                path.curve_to((x0 + ((x1 - x0) * 0.3)), (py - 14), (x0 + ((x1 - x0) * 0.55)), (py + 16), x1, (py - 4))
                self.dashed(path, MapArt.alpha(lime, 40), 1, 3, 4)
                px, pq = lay['pond']
                pond = Ellipse2D.Double((px - 30), (pq - 16), 60, 32)
                self.fill(pond, Color(20, 60, 90, 70))
                self.draw(pond, MapArt.alpha(self.glass, 70), 1)
                self.draw(Ellipse2D.Double((px - 18), (pq - 8), 36, 16), MapArt.alpha(self.glass, 30), 0.8)
                trees = Path2D.Double()
                for x, y, r in lay['park_trees']:
                    self.tree(trees, x, y, r)
                self.fill(trees, Color(10, 30, 22, 120))
                self.draw(trees, MapArt.alpha(lime, 75), 0.9)
            for x, y, r in lay['plazas']:
                self.fill(MapArt.hexagon(x, y, r, 30), Color(20, 40, 70, 60))
                self.draw(MapArt.hexagon(x, y, r, 30), MapArt.alpha(self.cyan, 45), 1)
                self.draw(MapArt.hexagon(x, y, (r * 0.6), 30), MapArt.alpha(self.cyan, 28), 1)
                self.fill(Ellipse2D.Double((x - 2.5), (y - 2.5), 5, 5), MapArt.alpha(self.cyan, 110))
            trees = Path2D.Double()
            for x, y, r in lay['trees']:
                self.tree(trees, x, y, r)
            self.fill(trees, Color(10, 30, 22, 120))
            self.draw(trees, MapArt.alpha(lime, 75), 0.9)
        def roof(self, o, k, acc):
            """A building's roof in full detail: HQ glass tiers, helipad and beacon; lab solar arrays and glass dome (a
robot arm on the robotics lab); server-farm fan grids; parking bays with cars and chargers; the holo billboard."""
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            l = ('' if (o.label is None) else o.label)
            ad = MapArt.Valley.ad(o)
            bottom = (((y + h) - 32) if ((ad is not None) and (ad[5] != 'r')) else ((y + h) - 8))
            r = _j.Random((_j.hash_code(l) + _j.to_int(((x * 7) + y))))
            if k == 'hq':
                t1 = Rectangle2D.Double((x + 10), (y + 20), (w - 20), ((bottom - y) - 24))
                self.draw(t1, MapArt.alpha(acc, 55), 1)
                t2 = Rectangle2D.Double((x + 22), (y + 30), (w - 44), ((bottom - y) - 44))
                self.draw(t2, MapArt.alpha(acc, 30), 1)
                old = self.g.get_clip()
                self.g.clip(t1)
                refl = Path2D.Double()
                kx = (-h)
                while kx < w:
                    refl.append(Line2D.Double((x + kx), (y + h), ((x + kx) + h), y), False)
                    kx += 22
                self.draw(refl, Color(160, 220, 255, 14), 4)
                self.g.set_clip(old)
                rr = (min(t2.width, t2.height) * 0.36)
                cx = (x + (w / 2))
                cy = (t2.y + (t2.height / 2))
                self.draw(Ellipse2D.Double((cx - rr), (cy - rr), (2 * rr), (2 * rr)), MapArt.alpha(MapArt.c(0xffd84a), 120), 1.2)
                hh = Path2D.Double()
                hh.append(Line2D.Double((cx - (rr * 0.4)), (cy - (rr * 0.5)), (cx - (rr * 0.4)), (cy + (rr * 0.5))), False)
                hh.append(Line2D.Double((cx + (rr * 0.4)), (cy - (rr * 0.5)), (cx + (rr * 0.4)), (cy + (rr * 0.5))), False)
                hh.append(Line2D.Double((cx - (rr * 0.4)), cy, (cx + (rr * 0.4)), cy), False)
                self.draw(hh, MapArt.alpha(MapArt.c(0xffd84a), 130), 1.2)
                self.fill(Ellipse2D.Double(((x + w) - 9), (y + 5), 4, 4), MapArt.alpha(MapArt.c(0xff3b4e), 150))
            elif k == 'lab':
                robotics = ('ROBOTICS' in l)
                rr = _j.dmin((w * 0.22), (h * 0.32))
                dx = (x + (w * 0.7))
                dy = (y + (h * 0.55))
                if ad is not None:
                    rr = _j.dmin((w * 0.2), (h * 0.3))
                    dx = ((x + w) - rr) - 12
                    dy = (y + (h * 0.5))
                if not robotics:
                    panels = Path2D.Double()
                    cells = Path2D.Double()
                    sx = (x + 8)
                    while sx < (x + (w * 0.44)):
                        panels.append(Rectangle2D.Double(sx, (y + 22), 10, ((bottom - y) - 26)), False)
                        cy = (y + 30)
                        while cy < (bottom - 4):
                            cells.append(Line2D.Double(sx, cy, (sx + 10), cy), False)
                            cy += 8
                        sx += 13
                    self.fill(panels, Color(14, 26, 60, 160))
                    self.draw(panels, MapArt.alpha(self.glass, 60), 0.9)
                    self.draw(cells, MapArt.alpha(self.glass, 26), 0.8)
                else:
                    self.robot_arm((x + (w * 0.28)), (y + (h * 0.58)), 300, acc)
                dome = Ellipse2D.Double((dx - rr), (dy - rr), (2 * rr), (2 * rr))
                self.blur(dome, MapArt.alpha(acc, 50), 6)
                self.fill(dome, MapArt.c(0x0d1430))
                ribs = Path2D.Double()
                for i in range(6):
                    a = ((i * math.pi) / 3)
                    ribs.append(Line2D.Double(dx, dy, (dx + (math.cos(a) * rr)), (dy + (math.sin(a) * rr))), False)
                ribs.append(Ellipse2D.Double((dx - (rr * 0.55)), (dy - (rr * 0.55)), (rr * 1.1), (rr * 1.1)), False)
                self.draw(ribs, MapArt.alpha(acc, 45), 0.9)
                self.draw(dome, MapArt.alpha(acc, 170), 1.2)
            elif k == 'srv':
                fr = 9.0
                fx = (x + 18)
                while ((fx + fr) + 5) < (x + w):
                    fy = (y + 30)
                    while fy < (bottom - 6):
                        self.fan_art(fx, fy, fr, acc, 70)
                        fy += 25
                    fx += 25
                leds = Path2D.Double()
                ly = (y + 26)
                while ly < (bottom - 4):
                    if r.next_double() < 0.4:
                        leds.append(Rectangle2D.Double(((x + w) - 6), ly, 2.5, 2), False)
                    ly += 9
                self.fill(leds, MapArt.alpha(self.cyan, 200))
            elif k == 'bay':
                vert = (h > w)
                bays = Path2D.Double()
                chargers = Path2D.Double()
                cols = (self.glass, self.lime, self.magenta, self.glass, self.warm)
                if vert:
                    by = (y + 22)
                    while (by + 26) <= ((y + h) - 2):
                        bays.append(Line2D.Double((x + 6), by, ((x + w) - 6), by), False)
                        chargers.append(Ellipse2D.Double((x + 7), (by + 11), 4, 4), False)
                        if r.next_double() < 0.7:
                            self.car_art(((x + (w / 2)) + 6), (by + 13), 0, cols[r.next_int(len(cols))], 90)
                        by += 26
                else:
                    bx = (x + 8)
                    while (bx + 26) <= ((x + w) - 4):
                        bays.append(Line2D.Double(bx, (y + 26), bx, ((y + h) - 6)), False)
                        chargers.append(Ellipse2D.Double((bx + 11), (y + 28), 4, 4), False)
                        if r.next_double() < 0.7:
                            self.car_art((bx + 13), ((y + h) - 30), 90, cols[r.next_int(len(cols))], 90)
                        bx += 26
                self.draw(bays, MapArt.alpha(acc, 55), 1)
                self.blur(chargers, MapArt.alpha(acc, 90), 2.5)
                self.fill(chargers, MapArt.alpha(acc, 180))
            elif k == 'holo':
                screen = Rectangle2D.Double((x + 6), (y + 6), (w - 12), (h - 12))
                self.g.set_paint(GradientPaint(x, y, MapArt.alpha(self.magenta, 55), (x + w), (y + h), MapArt.alpha(self.violet, 25)))
                self.g.fill(screen)
                lines = Path2D.Double()
                ly = (y + 8)
                while ly < ((y + h) - 6):
                    lines.append(Line2D.Double((x + 7), ly, ((x + w) - 7), ly), False)
                    ly += 3
                self.draw(lines, Color(255, 255, 255, 10), 1)
        def robot_arm(self, x, y, ang, c):
            """A robot arm from above as line art: base ring, two links, a gripper."""
            a1 = math.radians(ang)
            a2 = (a1 + math.radians(70))
            ex = (x + (math.cos(a1) * 22))
            ey = (y + (math.sin(a1) * 22))
            hx = (ex + (math.cos(a2) * 16))
            hy = (ey + (math.sin(a2) * 16))
            base = Ellipse2D.Double((x - 8), (y - 8), 16, 16)
            self.fill(base, MapArt.c(0x0a1020))
            self.draw(base, MapArt.alpha(c, 110), 1)
            arm = Path2D.Double()
            arm.move_to(x, y)
            arm.line_to(ex, ey)
            arm.line_to(hx, hy)
            self.draw(arm, MapArt.alpha(self.warm, 50), 4.5)
            self.draw(arm, MapArt.alpha(self.warm, 140), 1.2)
            self.draw(Ellipse2D.Double((ex - 3), (ey - 3), 6, 6), MapArt.alpha(self.warm, 140), 1)
            ga = (a2 + (math.pi / 2))
            grip = Path2D.Double()
            for sgn in (-1, 1):
                gx = (hx + ((math.cos(ga) * 4) * sgn))
                gy = (hy + ((math.sin(ga) * 4) * sgn))
                grip.move_to(gx, gy)
                grip.line_to((gx + (math.cos(a2) * 5)), (gy + (math.sin(a2) * 5)))
            grip.append(Line2D.Double((hx + (math.cos(ga) * 4)), (hy + (math.sin(ga) * 4)), (hx - (math.cos(ga) * 4)), (hy - (math.sin(ga) * 4))), False)
            self.draw(grip, MapArt.alpha(self.glass, 130), 1)
            self.fill(Ellipse2D.Double((x - 2.5), (y - 2.5), 5, 5), MapArt.alpha(c, 200))
        def signage(self, o, k, acc):
            """The building's own neon sign (its name, top-left on the roof) and its ad billboard, if any; the holo
board shows its slogan."""
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            l = ('' if (o.label is None) else o.label)
            if k == 'holo':
                self.neon_text('SCALE IS', ((x + (w / 2)) - (MapArt.measure('SCALE IS', MapArt.sign_font(14)) / 2)), (y + 27), 14, MapArt.c(0xff8cf0), 175, 65)
                self.neon_text('ALL YOU NEED', ((x + (w / 2)) - (MapArt.measure('ALL YOU NEED', MapArt.sign_font(14)) / 2)), (y + 43), 14, MapArt.c(0xff8cf0), 175, 65)
                self.neon_text('NOW SHIPPING', ((x + (w / 2)) - (MapArt.measure('NOW SHIPPING', MapArt.sign_font(9)) / 2)), (y + 58), 9, self.cyan, 160, 50)
                return
            if self.fine or (w >= 120):
                self.neon_text(l, (x + 6), (y + 13), 9, acc, 135, 40)
            ad = MapArt.Valley.ad(o)
            if ad is not None:
                self.sign([ad[0]], ad[2], ad[3], MapArt.c(ad[1]), ad[4], 175, 60, True, ad[5])
        def skybridge(self, b):
            r = Rectangle2D.Double(b[0], b[1], b[2], b[3])
            self.fill(r, Color(150, 210, 255, 22))
            rails = Path2D.Double()
            if b[2] >= b[3]:
                rails.append(Line2D.Double(b[0], b[1], (b[0] + b[2]), b[1]), False)
                rails.append(Line2D.Double(b[0], (b[1] + b[3]), (b[0] + b[2]), (b[1] + b[3])), False)
            else:
                rails.append(Line2D.Double(b[0], b[1], b[0], (b[1] + b[3])), False)
                rails.append(Line2D.Double((b[0] + b[2]), b[1], (b[0] + b[2]), (b[1] + b[3])), False)
            self.neon(rails, MapArt.alpha(self.glass, 150), 1, 40)
    class Neural(Painter):
        """The Neural Network: inside the machine. Far layer: a faint ghost network and the fully-connected weights between
the layers; the neurons are glowing magenta rings (the output neuron gold) over the cyan synapse pathways. Set
dressing: weight labels on the weights, activation-function glyph tiles (relu, sigmoid, tanh, softmax...), faint
columns of bits and loose data packets."""
        def __init__(self, nn, g):
            MapArt.Painter.__init__(self, nn, g, MapArt.c(0x060818), MapArt.c(0x38e8ff), MapArt.c(0x38e8ff))
            self.nn = nn
            self.cyan = MapArt.c(0x38e8ff)
            self.magenta = MapArt.c(0xff4bd8)
            self.violet = MapArt.c(0x8a5cff)
            self.gold = MapArt.c(0xffd84a)
        def extra_clear(self, x, y, r):
            p = Vec(x, y)
            for v in self.nn.get_neurons():
                if p.dist(v) < (52 + r):
                    return False
            return True
        def edge_colour(self):
            return Cyber.lerp(self.cyan, Color.WHITE, 0.2)
        def paint_map(self):
            self.begin_soft()
            self.g.set_paint(RadialGradientPaint(Point2D.Double(560, 450), 820.0, [0.0, 1.0], [MapArt.c(0x0c1232), MapArt.c(0x020309)]))
            self.g.fill(Rectangle2D.Double(0, 0, MapArt.W, MapArt.H))
            for v in self.nn.get_neurons():
                r = (40 if (v is NeuralNetwork.OUT) else 32)
                self.soft_light(v.x, v.y, (r * 2.4), MapArt.alpha((self.gold if (v is NeuralNetwork.OUT) else self.magenta), 46))
            self.track_glow(85)
            self.end_soft()
            self.constellation(34, MapArt.alpha(self.violet, 22), MapArt.alpha(MapArt.c(0x9aa8ff), 50), 200)
            self.draw(MapArt.weights(), MapArt.alpha(self.violet, 36), 1)
            if self.detail:
                self.machine_details()
            self.track(0.64)
            for v in self.nn.get_neurons():
                self.neuron(v)
        # ------------------------------------------------------------------ set dressing: inside the machine
        GLYPHS = ('relu', 'sigmoid', 'tanh', 'softmax', 'gelu', 'step', 'loss')
        def layout(self):
            """Weight labels on the fully-connected weights, activation-function glyph tiles and loss curves floating in
the open, faint columns of bits, and a few loose data packets."""
            lay = {'weights': [], 'tiles': [], 'rain': [], 'packets': []}
            vals = ('0.42', '-1.7', 'w=.91', '0.08', '-0.3', '1.25', 'w=.07', '-2.1', '0.66', '3e-4')
            n = 0
            for a, b in MapArt.weight_pairs():
                for t in (0.5, 0.42, 0.58, 0.34, 0.66):
                    x = (a.x + ((b.x - a.x) * t))
                    y = (a.y + ((b.y - a.y) * t))
                    if self.deco_clear(x, y, 15):
                        self.taken.append((x, y, 15))
                        ang = math.degrees(math.atan2((b.y - a.y), (b.x - a.x)))
                        if ang > 90:
                            ang -= 180
                        elif ang < (-90):
                            ang += 180
                        lay['weights'].append((x, y, ang, vals[(n % len(vals))]))
                        n += 1
                        break
            for i in range(len(MapArt.Neural.GLYPHS)):
                p = self.spot(24)
                if p is not None:
                    lay['tiles'].append((p[0], p[1], MapArt.Neural.GLYPHS[i]))
            x = 14.0
            while x < MapArt.W:
                if self.drnd.next_double() < 0.45:
                    y0 = (40 + (self.drnd.next_double() * (MapArt.H - 80)))
                    lay['rain'].append((x, y0, (5 + self.drnd.next_int(9)), self.drnd.next_int(1 << 20)))
                x += 34
            for i in range(10):
                p = self.spot(8)
                if p is not None:
                    lay['packets'].append((p[0], p[1], (self.drnd.next_double() * 90)))
            return lay
        def glyph(self, kind, x, y, c):
            """An activation-function tile: a rounded frame with tiny axes, the function's curve and its name."""
            tile = RoundRectangle2D.Double((x - 17), (y - 17), 34, 38, 5, 5)
            self.fill(tile, Color(6, 9, 24, 200))
            self.draw(tile, MapArt.alpha(c, 70), 0.9)
            axes = Path2D.Double()
            axes.append(Line2D.Double((x - 12), (y + 4), (x + 12), (y + 4)), False)
            axes.append(Line2D.Double(x, (y - 12), x, (y + 8)), False)
            self.draw(axes, MapArt.alpha(c, 32), 0.8)
            cur = Path2D.Double()
            for k in range(25):
                u = ((k / 24.0) * 2) - 1
                if kind == 'relu':
                    v = max(0.0, u)
                elif kind == 'sigmoid':
                    v = (1 / (1 + math.exp((-u) * 5)))
                elif kind == 'tanh':
                    v = (0.5 + (0.5 * math.tanh((u * 3))))
                elif kind == 'gelu':
                    v = ((u * 0.5) * (1 + math.tanh((0.8 * (u * 2))))) + 0.08
                elif kind == 'step':
                    v = (1.0 if (u >= 0) else 0.0)
                elif kind == 'loss':
                    v = (0.05 + (0.9 * math.exp(((-(u + 1)) * 2.2))))
                else:
                    v = None
                if v is None:
                    break
                px = (x + (u * 12))
                py = ((y + 4) - (v * 14))
                (cur.move_to if (k == 0) else cur.line_to)(px, py)
            if kind == 'softmax':
                for i, hgt in enumerate((4, 13, 7)):
                    cur.append(Rectangle2D.Double(((x - 10) + (i * 8)), ((y + 4) - hgt), 5, hgt), False)
            self.draw(cur, MapArt.alpha(Cyber.lerp(c, Color.WHITE, 0.2), 120), 1.1)
            f = Cyber.mono(Font.BOLD, 7)
            self.mark(kind, (x - (MapArt.measure(kind, f) / 2)), (y + 17), f, MapArt.alpha(c, 110))
        def machine_details(self):
            lay = self.lay
            if self.fine:
                f = Cyber.mono(Font.BOLD, 9)
                old = self.g.get_clip()
                self.g.clip(self.deco_area())
                for x, y0, n, bits in lay['rain']:
                    for k in range(n):
                        y = (y0 - (k * 12))
                        if y < 8:
                            break
                        if not self.deco_clear((x + 3), (y - 3), 4, True, False):
                            continue
                        a = (60 if (k == 0) else max(12, _j.to_int((44 * (1 - (k / float(n)))))))
                        self.mark(('1' if ((bits >> (k % 20)) & 1) else '0'), x, y, f, MapArt.alpha(self.cyan, a))
                self.g.set_clip(old)
                f = Cyber.mono(Font.BOLD, 9)
                for x, y, ang, s in lay['weights']:
                    rot = self.rotated(x, y, ang)
                    tw = MapArt.measure(s, f)
                    self.fill(Rectangle2D.Double(((x - (tw / 2)) - 3), (y - 7), (tw + 6), 10), MapArt.c(0x070a1c))
                    self.mark(s, (x - (tw / 2)), (y + 0.5), f, MapArt.alpha(MapArt.c(0xb9a8ff), 120))
                    self.g.set_transform(rot)
            pk = Path2D.Double()
            for x, y, a in lay['packets']:
                rot = self.rotated(x, y, a)
                self.draw(Rectangle2D.Double((x - 5), (y - 5), 10, 10), MapArt.alpha(self.cyan, 60), 0.9)
                self.fill(Rectangle2D.Double((x - 2), (y - 2), 4, 4), MapArt.alpha(self.magenta, 70))
                self.g.set_transform(rot)
            for i, (x, y, kind) in enumerate(lay['tiles']):
                self.glyph(kind, x, y, (self.cyan if ((i % 2) == 0) else MapArt.c(0xd07bff)))
        def neuron(self, p):
            out = (p is NeuralNetwork.OUT)
            r = (40 if out else 32)
            core = (self.gold if out else self.magenta)
            disc = Ellipse2D.Double((p.x - r), (p.y - r), (2 * r), (2 * r))
            self.g.set_paint(RadialGradientPaint(Point2D.Double(p.x, p.y), r, [0.0, 0.35, 1.0], [MapArt.alpha(Cyber.lerp(core, Color.WHITE, 0.5), 210), MapArt.alpha(core, 90), MapArt.alpha(core, 22)]))
            self.g.fill(disc)
            self.neon(disc, MapArt.alpha(core, 225), 1.6, 100)
            self.draw(Ellipse2D.Double((p.x - (r * 0.62)), (p.y - (r * 0.62)), (r * 1.24), (r * 1.24)), MapArt.alpha(Cyber.lerp(core, Color.WHITE, 0.3), 80), 1)
    class Graveyard(Painter):
        """The Abandoned Data Center: a dark, dead hall lit only by emergency lights. Far layer: raised-floor tiles and a few
loose cables; the racks are dim and unlit apart from a few amber LEDs and a red fault strip here and there, the cooling
plant is framed in amber hazard neon; the four malfunctioning track sections keep their dashed yellow border, tint,
warning sign and kind label; the escape route's chevrons are amber. Set dressing: perforated and lifted floor tiles,
loose cables with sparking ends, debris, dead monitors (a few still flicker), toppled chassis, floor fans and warning
beacons on the floor; cracks, dead LEDs and DANGER placards on the racks, FAULT / LOW readouts and a high-voltage mark
on the UPS bank, pipes and an OFFLINE sign on the cooling plant."""
        def __init__(self, dc, g):
            MapArt.Painter.__init__(self, dc, g, MapArt.c(0x0b0d10), MapArt.c(0xffb43b), MapArt.c(0x9aa4b0))
            self.dc = dc
            self.amber = MapArt.c(0xffb43b)
            self.red = MapArt.c(0xff3b4e)
            self.cold = MapArt.c(0x7fd6ff)
            self.steel = MapArt.c(0x5a6472)
            self.steel_hi = MapArt.c(0x76808e)
        def edge_colour(self):
            return MapArt.c(0xb8c2cc)
        def paint_map(self):
            self.begin_soft()
            self.ground(MapArt.c(0x0c0e12), MapArt.c(0x050608), 0, MapArt.H)
            self.soft_light(600, 60, 260, Color(255, 180, 59, 30))
            self.soft_light(210, 900, 320, Color(255, 59, 78, 30))
            self.soft_light(990, 900, 300, Color(255, 59, 78, 24))
            self.soft_light(600, 420, 280, Color(127, 214, 255, 14))
            self.track_glow(45)
            self.end_soft()
            self.grid(40, Color.WHITE, 5)
            self.cables()
            if self.detail:
                self.ruin_details()
            self.track(0.64, MapArt.alpha(self.amber, 100))
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_zone(self.dc.get_hazards()[i])
                i += 1
            n = 0
            for o in self.map.get_obstacles():
                l = ('' if (o.label is None) else o.label)
                if l.startswith('COOLING'):
                    self.cooling_plant(o)
                elif l.startswith('UPS'):
                    self.ups(o)
                else:
                    self.rack(o, n)
                    n += 1
            i = 0
            while i < len(self.dc.get_hazards()):
                self.hazard_label(self.dc.get_hazards()[i])
                i += 1
        # ------------------------------------------------------------------ set dressing: the ruin
        def tag_pos(self, hz):
            """Where a hazard section's warning tag stands (beside the section, on the side clear of racks)."""
            r = self.map.get_routes()[0]
            mid = r.position_at(((hz.from_ + hz.to) / 2))
            dir_ = r.direction_at(((hz.from_ + hz.to) / 2))
            tag_at = Vec((mid.x - (dir_.y * (MapArt.HW + 26))), (mid.y + (dir_.x * (MapArt.HW + 26))))
            for o in self.map.get_obstacles():
                if o.contains(tag_at, 14):
                    return Vec((mid.x + (dir_.y * (MapArt.HW + 26))), (mid.y - (dir_.x * (MapArt.HW + 26))))
            return tag_at
        def deco_extra(self, x, y, r):
            for hz in self.dc.get_hazards():
                t = self.tag_pos(hz)
                if math.hypot((x - t.x), ((y - t.y) - 8)) < (46 + r):
                    return False
            return True
        def layout(self):
            """Broken floor tiles, loose cables with frayed ends, debris, dead monitors, toppled chassis, floor fans and
warning beacons, wherever the open floor allows."""
            lay = {'perf': [], 'holes': [], 'monitors': [], 'chassis': [], 'fans': [], 'beacons': [], 'debris': [],
                   'cables': [], 'sparks': []}
            for i in range(120):
                tx = (math.floor(((self.drnd.next_double() * MapArt.W) / 40)) * 40)
                ty = (math.floor(((self.drnd.next_double() * MapArt.H) / 40)) * 40)
                if any(((t[0] == tx) and (t[1] == ty)) for t in (lay['holes'] + lay['perf'])):
                    continue
                if self.box_clear((tx + 1), (ty + 1), (tx + 39), (ty + 39), True):
                    if (len(lay['holes']) < 3) and ((i % 3) == 0):
                        lay['holes'].append((tx, ty, (self.drnd.next_double() * 30)))
                        self.taken.append(((tx + 20), (ty + 20), 20))
                    elif len(lay['perf']) < 12:
                        lay['perf'].append((tx, ty, 0))
            for key, n, r in (('fans', 3, 18), ('monitors', 9, 17), ('chassis', 5, 19), ('beacons', 5, 7), ('debris', 32, 6)):
                for i in range(n):
                    p = self.spot(r)
                    if p is not None:
                        lay[key].append((p[0], p[1], (self.drnd.next_int(50) - 25), self.drnd.next_double()))
            for i in range(160):
                p = ((self.drnd.next_double() * MapArt.W), (self.drnd.next_double() * MapArt.H))
                if not self.deco_clear(p[0], p[1], 3, True, False):
                    continue
                pts = [p]
                a = (self.drnd.next_double() * math.pi * 2)
                for k in range(16):
                    a += ((self.drnd.next_double() - 0.5) * 0.9)
                    q = ((pts[-1][0] + (math.cos(a) * 9)), (pts[-1][1] + (math.sin(a) * 9)))
                    if not self.deco_clear(q[0], q[1], 2, True, False):
                        break
                    pts.append(q)
                if len(pts) >= 6:
                    lay['cables'].append((pts, (i % 4)))
                    if (len(lay['sparks']) < 4) and (self.drnd.next_double() < 0.5):
                        lay['sparks'].append(pts[-1])
                if len(lay['cables']) >= 13:
                    break
            return lay
        def ruin_details(self):
            lay = self.lay
            steel = self.steel_hi
            holes = Path2D.Double()
            for tx, ty, _ in lay['perf']:
                hx = (tx + 8)
                while hx < (tx + 36):
                    hy = (ty + 8)
                    while hy < (ty + 36):
                        holes.append(Ellipse2D.Double((hx - 1), (hy - 1), 2, 2), False)
                        hy += 6
                    hx += 6
            self.fill(holes, Color(0, 0, 0, 150))
            self.fill(holes, Color(255, 255, 255, 8))
            for tx, ty, rot in lay['holes']:
                self.fill(Rectangle2D.Double((tx + 2), (ty + 2), 36, 36), MapArt.c(0x030405))
                self.draw(Rectangle2D.Double((tx + 2), (ty + 2), 36, 36), MapArt.alpha(steel, 40), 0.8)
                old = self.rotated((tx + 34), (ty + 20), (12 + rot))
                tile = Rectangle2D.Double((tx + 22), (ty + 6), 30, 30)
                self.fill(tile, MapArt.c(0x111418))
                self.draw(tile, MapArt.alpha(steel, 70), 0.9)
                self.g.set_transform(old)
            sheath = (MapArt.c(0xb04a4a), MapArt.c(0x4a6ab0), MapArt.c(0xb0a04a), MapArt.c(0x4ab06a))
            for pts, k in lay['cables']:
                cab = Path2D.Double()
                cab.move_to(pts[0][0], pts[0][1])
                for i in range(1, (len(pts) - 1)):
                    cab.quad_to(pts[i][0], pts[i][1], ((pts[i][0] + pts[(i + 1)][0]) / 2), ((pts[i][1] + pts[(i + 1)][1]) / 2))
                cab.line_to(pts[-1][0], pts[-1][1])
                self.draw(cab, MapArt.alpha(sheath[k], 72), 1.4)
            if not self.fine:
                return
            sp = Path2D.Double()
            for x, y in lay['sparks']:
                for k in range(6):
                    a = (k * 1.047) + (x * 0.1)
                    l = (3 + ((k % 3) * 2))
                    sp.append(Line2D.Double(x, y, (x + (math.cos(a) * l)), (y + (math.sin(a) * l))), False)
            self.draw(sp, Color(255, 225, 150, 90), 0.8)
            deb = Path2D.Double()
            for x, y, rot, v in lay['debris']:
                at = AffineTransform()
                at.rotate(math.radians((rot * 4)), x, y)
                deb.append(at.create_transformed_shape(Rectangle2D.Double((x - 4), (y - 2), (5 + (v * 5)), (2.5 + (v * 2)))), False)
                deb.append(Rectangle2D.Double((x + 3), (y + 3), 2, 2), False)
            self.draw(deb, MapArt.alpha(steel, 55), 0.8)
            for x, y, rot, v in lay['chassis']:
                old = self.rotated(x, y, (rot * 3))
                body = Rectangle2D.Double((x - 17), (y - 8), 34, 16)
                self.fill(body, MapArt.c(0x0e1114))
                self.draw(body, MapArt.alpha(steel, 75), 0.9)
                bays = Path2D.Double()
                for k in range(4):
                    bays.append(Rectangle2D.Double(((x - 14) + (k * 7)), (y - 5), 5, 10), False)
                self.draw(bays, MapArt.alpha(steel, 40), 0.8)
                self.fill(Rectangle2D.Double((x + 11), (y - 5), 2.5, 2.5), MapArt.alpha(self.red, (150 if (v < 0.5) else 40)))
                self.g.set_transform(old)
            for x, y, rot, v in lay['monitors']:
                self.monitor(x, y, rot, (v < 0.45), (self.cold if (v < 0.25) else MapArt.c(0x5ce07a)))
            for x, y, rot, v in lay['fans']:
                self.fan_art(x, y, 16, self.amber, 70)
            for x, y, rot, v in lay['beacons']:
                ring = Ellipse2D.Double((x - 5), (y - 5), 10, 10)
                self.fill(ring, MapArt.c(0x14100a))
                self.draw(ring, MapArt.alpha(self.amber, 90), 0.9)
                dot = Ellipse2D.Double((x - 2), (y - 2), 4, 4)
                self.blur(dot, MapArt.alpha(self.amber, 60), 3)
                self.fill(dot, MapArt.alpha(self.amber, 130))
        def monitor(self, x, y, rot, on, scr):
            """A dead monitor on the floor, tilted: bezel, stand and a cracked screen (some still glow faintly)."""
            old = self.rotated(x, y, rot)
            bezel = RoundRectangle2D.Double((x - 14), (y - 10), 28, 19, 3, 3)
            self.fill(bezel, MapArt.c(0x0d1013))
            self.draw(bezel, MapArt.alpha(self.steel_hi, 85), 0.9)
            screen = Rectangle2D.Double((x - 11), (y - 7.5), 22, 13.5)
            if on:
                self.fill(screen, MapArt.alpha(scr, 34))
                txt = Path2D.Double()
                for k in range(3):
                    txt.append(Line2D.Double((x - 9), ((y - 4.5) + (k * 3.6)), ((x - 3) + (((k * 5) % 7) * 1.6)), ((y - 4.5) + (k * 3.6))), False)
                self.draw(txt, MapArt.alpha(scr, 120), 0.9)
            crack = Path2D.Double()
            crack.move_to((x + 2), (y - 7))
            crack.line_to((x - 1), (y - 1))
            crack.line_to((x + 4), (y + 2))
            crack.line_to((x + 1), (y + 6))
            crack.move_to((x - 1), (y - 1))
            crack.line_to((x - 9), (y + 1))
            self.draw(crack, Color(220, 230, 240, 70), 0.7)
            stand = Path2D.Double()
            stand.append(Line2D.Double(x, (y + 9), x, (y + 13)), False)
            stand.append(Line2D.Double((x - 8), (y + 13), (x + 8), (y + 13)), False)
            self.draw(stand, MapArt.alpha(self.steel_hi, 70), 1)
            self.g.set_transform(old)
        def cables(self):
            """A few loose cables on the floor, kept very faint."""
            sheath = [MapArt.c(0x6a2a2a), MapArt.c(0x2a3f6a), MapArt.c(0x6a5f2a), MapArt.c(0x2a5a3a)]
            for i in range(4):
                x0 = (self.rnd.next_double() * MapArt.W)
                y0 = (self.rnd.next_double() * MapArt.H)
                x1 = (x0 + ((self.rnd.next_double() - 0.5) * 320))
                y1 = (y0 + ((self.rnd.next_double() - 0.5) * 320))
                cab = Path2D.Double()
                cab.move_to(x0, y0)
                cab.curve_to((x0 + ((self.rnd.next_double() - 0.5) * 220)), (y0 + ((self.rnd.next_double() - 0.5) * 220)), (x1 + ((self.rnd.next_double() - 0.5) * 220)), (y1 + ((self.rnd.next_double() - 0.5) * 220)), x1, y1)
                self.draw(cab, MapArt.alpha(sheath[_j.imod(i, len(sheath))], 70), 1.6)
        def hazard_zone(self, hz):
            """The marked track section: a faint tint inside the track and a thin dashed yellow border."""
            r = self.map.get_routes()[0]
            zone = self.sub_path(r, hz.from_, hz.to)
            band = Area(BasicStroke(((2 * MapArt.HW) + 8), BasicStroke.CAP_BUTT, BasicStroke.JOIN_ROUND).create_stroked_shape(zone))
            old = self.g.get_clip()
            self.g.clip(self.track_area(MapArt.HW))
            self.fill(band, MapArt.alpha(MapArt.c(hz.rgb), 30))
            self.g.set_clip(old)
            self.blur(band, MapArt.alpha(Cyber.YELLOW, 40), 3, 2)
            self.g.set_color(MapArt.alpha(Cyber.YELLOW, 170))
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
            self.blur(tri, MapArt.alpha(Cyber.YELLOW, 90), 4)
            self.fill(tri, MapArt.alpha(Cyber.YELLOW, 215))
            self.text_centered_bold('!', tag_at.x, (tag_at.y + 5))
            self.label(hz.kind, tag_at.x, (tag_at.y + 18), MapArt.c(hz.rgb))
        def text_centered_bold(self, s, cx, y):
            f = Cyber.mono(Font.BOLD, 10)
            self.text(s, (cx - (self.text_width(s, f) / 2.0)), y, f, Color(10, 10, 10))
        def rack(self, o, idx):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = Rectangle2D.Double(x, y, w, h)
            self.fill(body, MapArt.c(0x121519))
            self.draw(body, MapArt.alpha(self.steel_hi, 210), 1)
            units = Path2D.Double()
            leds = Path2D.Double()
            uy = (y + 9)
            while uy < ((y + h) - 4):
                units.append(Line2D.Double((x + 5), uy, ((x + w) - 5), uy), False)
                if self.rnd.next_double() < 0.15:
                    leds.append(Rectangle2D.Double(((x + w) - 10), (uy + 2), 3, 3), False)
                uy += 9
            self.draw(units, MapArt.alpha(self.steel, 40), 1)
            self.blur(leds, MapArt.alpha(self.amber, 90), 2.5)
            self.fill(leds, MapArt.alpha(self.amber, 200))
            if _j.imod(idx, 2) == 0:
                strip = Line2D.Double((x + 2.5), (y + 6), (x + 2.5), ((y + h) - 6))
                self.neon(strip, MapArt.alpha(self.red, 170), 1.2, 70)
            if self.detail:
                crack = Path2D.Double()
                cx = (x + (w * 0.35))
                cy = (y + (h * (0.3 + (0.12 * (idx % 3)))))
                crack.move_to(cx, cy)
                crack.line_to((cx + 8), (cy + 6))
                crack.line_to((cx + 5), (cy + 14))
                crack.line_to((cx + 13), (cy + 21))
                crack.move_to((cx + 8), (cy + 6))
                crack.line_to((cx + 16), (cy + 4))
                self.draw(crack, Color(210, 220, 230, 60), 0.8)
                dead = Path2D.Double()
                uy = (y + 11)
                k = 0
                while uy < ((y + h) - 4):
                    if ((k + idx) % 4) == 1:
                        dead.append(Rectangle2D.Double(((x + w) - 10), uy, 3, 3), False)
                    uy += 9
                    k += 1
                self.draw(dead, MapArt.alpha(self.steel, 70), 0.7)
                if (idx % 3) == 1:
                    self.sign(['DANGER'], (x + (w / 2)), ((y + h) - 22), self.red, 8, 170, 40, True, 'c', 3)
        def cooling_plant(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = Rectangle2D.Double(x, y, w, h)
            self.fill(body, MapArt.c(0x07090b))
            self.neon(body, MapArt.alpha(self.amber, 190), 1.4, 60)
            corners = Path2D.Double()
            l = 14.0
            for (cx, cy, dx, dy) in ((x - 5, y - 5, 1, 1), ((x + w) + 5, y - 5, -1, 1), ((x + w) + 5, (y + h) + 5, -1, -1), (x - 5, (y + h) + 5, 1, -1)):
                corners.move_to(cx, (cy + (dy * l)))
                corners.line_to(cx, cy)
                corners.line_to((cx + (dx * l)), cy)
            self.draw(corners, MapArt.alpha(Cyber.YELLOW, 200), 1.4)
            self.fan((x + (w / 2)), (y + (h * 0.4)), 40)
            self.fan((x + (w / 2)), (y + (h * 0.76)), 26)
            if self.detail:
                pipes = Path2D.Double()
                for py in ((y + (h * 0.4)) - 52, (y + (h * 0.4)) + 50):
                    pipes.append(Line2D.Double((x + 12), py, ((x + w) - 12), py), False)
                    pipes.append(Line2D.Double((x + 12), (py + 5), ((x + w) - 12), (py + 5)), False)
                self.draw(pipes, MapArt.alpha(self.steel_hi, 70), 0.9)
                flanges = Path2D.Double()
                for py in ((y + (h * 0.4)) - 52, (y + (h * 0.4)) + 50):
                    fx = (x + 30)
                    while fx < ((x + w) - 20):
                        flanges.append(Line2D.Double(fx, (py - 2), fx, (py + 7)), False)
                        fx += 46
                self.draw(flanges, MapArt.alpha(self.steel_hi, 80), 1.2)
                self.sign(['OFFLINE'], (x + (w / 2)), ((y + h) - 22), self.amber, 10, 180, 60, True, 'c')
        def fan(self, cx, cy, r):
            disc = Ellipse2D.Double((cx - r), (cy - r), (2 * r), (2 * r))
            self.fill(disc, MapArt.c(0x0a0d11))
            self.draw(disc, MapArt.alpha(self.cold, 110), 1.2)
            blades = Path2D.Double()
            for i in range(3):
                a0 = (((i * math.pi) * 2) / 3)
                blades.move_to((cx + ((math.cos(a0) * r) * 0.25)), (cy + ((math.sin(a0) * r) * 0.25)))
                blades.quad_to((cx + ((math.cos((a0 + 0.5)) * r) * 0.7)), (cy + ((math.sin((a0 + 0.5)) * r) * 0.7)), (cx + ((math.cos((a0 + 0.9)) * r) * 0.82)), (cy + ((math.sin((a0 + 0.9)) * r) * 0.82)))
            self.draw(blades, MapArt.alpha(self.cold, 80), 1.6)
            self.fill(Ellipse2D.Double((cx - 3), (cy - 3), 6, 6), MapArt.alpha(self.cold, 120))
        def ups(self, o):
            x = o.x
            y = o.y
            w = o.w
            h = o.h
            body = Rectangle2D.Double(x, y, w, h)
            self.fill(body, MapArt.c(0x121519))
            self.draw(body, MapArt.alpha(self.steel_hi, 210), 1)
            cabs = Path2D.Double()
            for i in range(4):
                cx = ((x + 6) + ((i * (w - 12)) / 4.0))
                cw = (((w - 12) / 4.0) - 6)
                cabs.append(RoundRectangle2D.Double(cx, (y + 8), cw, (h - 16), 4, 4), False)
            self.draw(cabs, MapArt.alpha(self.steel, 70), 1)
            led = Rectangle2D.Double((x + 10), (y + 14), 4, 4)
            self.blur(led, MapArt.alpha(self.red, 140), 3)
            self.fill(led, MapArt.alpha(self.red, 220))
            if self.detail:
                f = Cyber.mono(Font.BOLD, 8)
                bars = Path2D.Double()
                for i in range(4):
                    cx = ((x + 6) + ((i * (w - 12)) / 4.0))
                    cw = (((w - 12) / 4.0) - 6)
                    lcd = Rectangle2D.Double((cx + 3), (y + 24), (cw - 6), 11)
                    self.fill(lcd, Color(20, 4, 6))
                    s = ('FAULT' if (i == 2) else 'LOW')
                    self.mark(s, ((cx + (cw / 2)) - (MapArt.measure(s, f) / 2)), (y + 32.5), f, MapArt.alpha(self.red, (190 if (i == 2) else 130)))
                    by = (y + 40)
                    while by < ((y + h) - 10):
                        bars.append(Rectangle2D.Double((cx + 4), by, ((cw - 8) * (0.15 if (i == 2) else 0.32)), 2), False)
                        by += 5
                self.fill(bars, MapArt.alpha(self.red, 110))
                bolt = Path2D.Double()
                bx = ((x + w) - 14)
                by = (y + 10)
                bolt.move_to((bx + 2), by)
                bolt.line_to((bx - 2), (by + 6))
                bolt.line_to((bx + 1), (by + 6))
                bolt.line_to((bx - 1.5), (by + 12))
                self.draw(MapArt.hexagon(bx, (by + 6), 8, 30), MapArt.alpha(self.amber, 80), 0.9)
                self.draw(bolt, MapArt.alpha(self.amber, 150), 1)
    class Ambience:
        """The optional live ambience of a map, built once per map (deterministic) and painted with a handful of draw
calls per frame: data pulses (a bright head with a short tail) that run along a background trace, divider or link now
and then; slowly breathing lights on a mechanic feature; a highlight sweeping around a ring; and a few animated details
of the set dressing: blinking LEDs, a neon sign or monitor that flickers now and then, a glitch shard that pops, a fan
that turns slowly, a car driving along a side street (never on the track)."""
        TAIL = 26.0
        def __init__(self, map_=None):
            self.map = map_
            self.lanes = []      # [points, cumulative lengths, total, colour, period, phase, speed, hidden stretches]
            self.breaths = []    # [x, y, r, colour, period, phase, alpha low, alpha high, stroke width (0 = filled)]
            self.sweeps = []     # [cx, cy, r, colour, degrees per second, span in degrees]
            self.blinks = []     # [x, y, r, colour, period, phase, duty (lit fraction of the period)]
            self.flickers = []   # [shape, cover colour, period, phase]: a sign or screen dims under the cover twice a period
            self.glitches = []   # [shape, colour, rate (slots per second), salt, stroke width (0 = filled)]: pops on in a few slots
            self.spins = []      # [cx, cy, r, colour, hub fill, radians per second, blades]
            self.movers = []     # [points, cumulative lengths, total, colour, speed, gap (px of empty street)]
            self.tail_stroke = BasicStroke(2.4, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
            self.strokes = {}
        def blink(self, x, y, r, col, period, phase, duty=0.5):
            self.blinks.append([x, y, r, col, period, phase, duty])
        def flicker(self, shape, cover, period, phase):
            self.flickers.append([shape, cover, period, phase])
        def glitch(self, shape, col, rate, salt, w=0.0):
            self.glitches.append([shape, col, rate, salt, w])
        def spin(self, cx, cy, r, col, hub, speed, blades=5):
            self.spins.append([cx, cy, r, col, hub, speed, blades])
        def mover(self, pts, col, speed, gap):
            cum = [0.0]
            for i in range(1, len(pts)):
                cum.append((cum[(i - 1)] + math.hypot((pts[i][0] - pts[(i - 1)][0]), (pts[i][1] - pts[(i - 1)][1]))))
            self.movers.append([pts, cum, cum[(len(cum) - 1)], col, speed, gap])
        def lane(self, pts, col, period, phase, speed=150.0):
            """A data pulse along the polyline pts every period seconds. Where the line crosses the track the pulse is
hidden, so nothing that moves along the track can be mistaken for an enemy or a shot."""
            cum = [0.0]
            for i in range(1, len(pts)):
                cum.append((cum[(i - 1)] + math.hypot((pts[i][0] - pts[(i - 1)][0]), (pts[i][1] - pts[(i - 1)][1]))))
            ln = [pts, cum, cum[(len(cum) - 1)], col, period, phase, speed, []]
            if self.map is not None:
                hidden = ln[7]
                d = 0.0
                start = (-1.0)
                while d <= (ln[2] + 4):
                    q = MapArt.Ambience.at(ln, min(d, ln[2]))
                    on = False
                    for r in self.map.get_routes():
                        if r.distance_to_point(Vec(q[0], q[1])) < (MapArt.HW + 8):
                            on = True
                            break
                    if on and (start < 0):
                        start = (d - 4)
                    elif (not on) and (start >= 0):
                        hidden.append((start, d))
                        start = (-1.0)
                    d += 4
                if start >= 0:
                    hidden.append((start, (ln[2] + MapArt.Ambience.TAIL)))
            self.lanes.append(ln)
        def breath(self, x, y, r, col, period, phase, lo, hi, w):
            self.breaths.append([x, y, r, col, period, phase, lo, hi, w])
        def sweep(self, cx, cy, r, col, speed, span):
            self.sweeps.append([cx, cy, r, col, speed, span])
        def count(self):
            """Number of live items (tests: the layer stays small)."""
            return (((((((len(self.lanes) + len(self.breaths)) + len(self.sweeps)) + len(self.blinks)) + len(self.flickers))
                     + len(self.glitches)) + len(self.spins)) + len(self.movers))
        @staticmethod
        def at(ln, d):
            pts = ln[0]
            cum = ln[1]
            i = max(1, min((len(cum) - 1), bisect.bisect_left(cum, d)))
            seg = (cum[i] - cum[(i - 1)])
            f = (0.0 if (seg <= 0) else ((d - cum[(i - 1)]) / seg))
            return ((pts[(i - 1)][0] + ((pts[i][0] - pts[(i - 1)][0]) * f)), (pts[(i - 1)][1] + ((pts[i][1] - pts[(i - 1)][1]) * f)))
        def stroke(self, w):
            s = self.strokes.get(w)
            if s is None:
                s = BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
                self.strokes[w] = s
            return s
        def paint(self, g2, t):
            S = MapArt.Ambience
            for ln in self.lanes:
                d = (math.fmod((t + ln[5]), ln[4]) * ln[6])
                if d > (ln[2] + S.TAIL):
                    continue
                a = max(0.0, (d - S.TAIL))
                b = min(d, ln[2])
                if any(((h0 <= b) and (h1 >= a)) for (h0, h1) in ln[7]):
                    continue
                p = Path2D.Double()
                q = S.at(ln, a)
                p.move_to(q[0], q[1])
                for i in range(1, (len(ln[1]) - 1)):
                    if a < ln[1][i] < b:
                        p.line_to(ln[0][i][0], ln[0][i][1])
                q = S.at(ln, b)
                p.line_to(q[0], q[1])
                g2.set_stroke(self.tail_stroke)
                g2.set_color(MapArt.alpha(ln[3], 120))
                g2.draw(p)
                if d <= ln[2]:
                    g2.set_color(MapArt.alpha(Cyber.lerp(ln[3], Color.WHITE, 0.6), 235))
                    g2.fill(Ellipse2D.Double((q[0] - 1.9), (q[1] - 1.9), 3.8, 3.8))
            for b in self.breaths:
                k = (0.5 - (0.5 * math.cos(((2 * math.pi) * ((t + b[5]) / b[4])))))
                a = _j.to_int((b[6] + ((b[7] - b[6]) * k)))
                if a <= 2:
                    continue
                g2.set_color(MapArt.alpha(b[3], a))
                e = Ellipse2D.Double((b[0] - b[2]), (b[1] - b[2]), (2 * b[2]), (2 * b[2]))
                if b[8] > 0:
                    g2.set_stroke(self.stroke(b[8]))
                    g2.draw(e)
                else:
                    g2.fill(e)
            for s in self.sweeps:
                a0 = math.radians(math.fmod((t * s[4]), 360.0))
                p = Path2D.Double()
                n = 12
                for i in range((n + 1)):
                    a = (a0 + ((math.radians(s[5]) * i) / n))
                    x = (s[0] + (math.cos(a) * s[2]))
                    y = (s[1] + (math.sin(a) * s[2]))
                    if i == 0:
                        p.move_to(x, y)
                    else:
                        p.line_to(x, y)
                g2.set_stroke(self.stroke(5.0))
                g2.set_color(MapArt.alpha(s[3], 40))
                g2.draw(p)
                g2.set_stroke(self.stroke(1.6))
                g2.set_color(MapArt.alpha(Cyber.lerp(s[3], Color.WHITE, 0.4), 170))
                g2.draw(p)
            for b in self.blinks:
                if (math.fmod((t + b[5]), b[4]) / b[4]) >= b[6]:
                    continue
                r = b[2]
                g2.set_color(MapArt.alpha(b[3], 55))
                g2.fill(Ellipse2D.Double((b[0] - (r * 2.6)), (b[1] - (r * 2.6)), (r * 5.2), (r * 5.2)))
                g2.set_color(MapArt.alpha(Cyber.lerp(b[3], Color.WHITE, 0.3), 235))
                g2.fill(Ellipse2D.Double((b[0] - r), (b[1] - r), (2 * r), (2 * r)))
            for f in self.flickers:
                u = (math.fmod((t + f[3]), f[2]) / f[2])
                if (u < 0.016) or (0.03 < u < 0.042):
                    g2.set_color(f[1])
                    g2.fill(f[0])
            for gl in self.glitches:
                k = _j.to_int(((t * gl[2]) + gl[3]))
                if (((k * 2654435761) & 0xffffffff) % 97) >= 4:
                    continue
                g2.set_color(gl[1])
                if gl[4] > 0:
                    g2.set_stroke(self.stroke(gl[4]))
                    g2.draw(gl[0])
                else:
                    g2.fill(gl[0])
            for s in self.spins:
                r = s[2]
                g2.set_color(s[4])
                g2.fill(Ellipse2D.Double((s[0] - (r * 0.9)), (s[1] - (r * 0.9)), (r * 1.8), (r * 1.8)))
                g2.set_stroke(MapArt.HAIR)
                g2.set_color(s[3])
                g2.draw(MapArt.fan_blades(s[0], s[1], r, (t * s[5]), s[6]))
            for m in self.movers:
                d = math.fmod((t * m[4]), (m[2] + m[5]))
                if d > m[2]:
                    continue
                q = S.at(m, d)
                n = S.at(m, min(m[2], (d + 2)))
                if (n[0] == q[0]) and (n[1] == q[1]):
                    n = S.at(m, max(0.0, (d - 2)))
                    n = ((2 * q[0]) - n[0], (2 * q[1]) - n[1])
                old = g2.get_transform()
                g2.translate(q[0], q[1])
                g2.rotate(math.atan2((n[1] - q[1]), (n[0] - q[0])))
                MapArt.car_shape(g2, m[3], 150)
                g2.set_color(Color(255, 244, 214, 26))
                g2.fill(MapArt.BEAM)
                g2.set_transform(old)
    class Pulses(GObject):
        """The live part of the map art: particles over the active malfunctioning section of the Abandoned Data Center
(sparks, coolant mist or air streaks, so the section's kind reads at a glance) and the map's optional ambience
(MapArt.Ambience). The ambience is off with REDUCED MOTION and on LOW quality; both are skipped in the most crowded
fights."""
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
            if Thick.level() >= Thick.DETAIL_FINE:
                return
            hazard = isinstance(self.map, AbandonedDataCenter)
            amb = MapArt.ambient()
            if not (hazard or amb):
                return
            g2 = g.create()
            try:
                g2.set_composite(AlphaComposite.SrcOver)
                if amb:
                    MapArt.ambience_for(self.map).paint(g2, self.time)
                if hazard:
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
            MapArt.render(g, map_, vignette)
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
    def painter(map_, g):
        """The map's painter (None for a map without its own art)."""
        if isinstance(map_, SiliconCircuit):
            return MapArt.Silicon(map_, g)
        if isinstance(map_, LegacyMonolith):
            return MapArt.Monolith(map_, g)
        if isinstance(map_, HallucinationCanyon):
            return MapArt.Canyon(map_, g)
        if isinstance(map_, SingularityCore):
            return MapArt.Singularity(map_, g)
        if isinstance(map_, SiliconValley):
            return MapArt.Valley(map_, g)
        if isinstance(map_, NeuralNetwork):
            return MapArt.Neural(map_, g)
        if isinstance(map_, AbandonedDataCenter):
            return MapArt.Graveyard(map_, g)
        return None
    @staticmethod
    def render(g, map_, vignette=False, details=True):
        """Paints the full map art in world coordinates (with the HIGH-quality vignette when vignette is set; without the
set dressing when details is False). Returns the painter (its marks list the diegetic text painted)."""
        p = MapArt.painter(map_, g)
        if p is None:
            p = MapArt.Painter(map_, g, MapArt.c(map_.get_background_rgb()), MapArt.c(0x00f0ff), MapArt.c(map_.get_track_rgb()))
            p.vignette = vignette
            p.paint_generic()
            return p
        p.vignette = vignette
        p.detail = details
        p.fine = (math.sqrt(abs(g.get_transform().get_determinant())) >= 0.45)
        p.lay = MapArt.layout_for(map_)
        p.paint_map()
        return p
    @staticmethod
    def layout_for(map_):
        """The map's set dressing places, computed once per map (the bitmap at every scale and the ambience share it)."""
        key = map_.get_name()
        v = MapArt.LAYOUTS.get(key)
        if v is None:
            p = MapArt.painter(map_, None)
            v = ({} if (p is None) else p.layout())
            MapArt.LAYOUTS[key] = v
        return v
    @staticmethod
    def track_field(map_):
        """Distance from every FIELD_STEP grid point to the nearest route centre line (numpy), once per map: placing the
set dressing asks it thousands of times."""
        key = map_.get_name()
        f = MapArt.FIELDS.get(key)
        if f is None:
            st = MapArt.FIELD_STEP
            X, Y = np.meshgrid(np.arange(0, (MapArt.W + st), st, dtype=float), np.arange(0, (MapArt.H + st), st, dtype=float))
            f = np.full(X.shape, 1e9)
            segs = set()
            for r in map_.get_routes():
                w = r.get_waypoints()
                for i in range((len(w) - 1)):
                    segs.add((w[i].x, w[i].y, w[(i + 1)].x, w[(i + 1)].y))
            for ax, ay, bx, by in segs:
                dx = (bx - ax)
                dy = (by - ay)
                l2 = ((dx * dx) + (dy * dy))
                t = (np.clip(((((X - ax) * dx) + ((Y - ay) * dy)) / l2), 0.0, 1.0) if (l2 > 0) else 0.0)
                np.minimum(f, np.hypot((X - (ax + (t * dx))), (Y - (ay + (t * dy)))), out=f)
            MapArt.FIELDS[key] = f
        return f
    @staticmethod
    def track_distance(map_, x, y):
        """A lower bound of the distance from (x, y) to the nearest route centre line (the field's grid error removed)."""
        f = MapArt.track_field(map_)
        st = MapArt.FIELD_STEP
        i = min((f.shape[0] - 1), max(0, _j.to_int(round((y / st)))))
        j = min((f.shape[1] - 1), max(0, _j.to_int(round((x / st)))))
        return float((f[(i, j)] - (st * 0.7072)))
    @staticmethod
    def measure(s, f):
        """The advance width of s in font f (no Graphics needed)."""
        return sum(sf.measureText(t) for sf, t in _runs(f, s))
    @staticmethod
    def sign_rect(lines, x, y, size, align='l', pad=4.0):
        """The backing panel (x, y, w, h) of a neon sign whose top-left ('l'), top centre ('c') or top-right ('r') is at
(x, y)."""
        f = MapArt.sign_font(size)
        tw = max(MapArt.measure(s, f) for s in lines)
        pw = (tw + (2 * pad))
        ph = (((size * 1.05) * len(lines)) + pad + 1)
        x0 = ((x - (pw / 2)) if (align == 'c') else ((x - pw) if (align == 'r') else x))
        return (x0, y, pw, ph)
    @staticmethod
    def sign_font(size):
        """The neon signs' face: Rajdhani Bold, a narrow techy sans that reads like bent tubes."""
        return Cyber.font('D', 'Rajdhani-Medium.ttf', 'Rajdhani-Bold.ttf', Font.SANS_SERIF, Font.BOLD, size)
    @staticmethod
    def fan_blades(cx, cy, r, a0, n):
        """n curved fan blades about (cx, cy), turned by a0 radians (the bitmap draws them still, the ambience turns
them)."""
        blades = Path2D.Double()
        for i in range(n):
            a = (a0 + (((i * math.pi) * 2) / n))
            blades.move_to((cx + ((math.cos(a) * r) * 0.26)), (cy + ((math.sin(a) * r) * 0.26)))
            blades.quad_to((cx + ((math.cos((a + 0.55)) * r) * 0.72)), (cy + ((math.sin((a + 0.55)) * r) * 0.72)), (cx + ((math.cos((a + 1.0)) * r) * 0.84)), (cy + ((math.sin((a + 1.0)) * r) * 0.84)))
        return blades
    @staticmethod
    def car_shape(g, c, a, lights=True):
        """A top-down car about the origin, nose towards +x, as neon line art (for the bitmap and the moving car)."""
        body = RoundRectangle2D.Double((-9), (-4.6), 18, 9.2, 5, 5)
        g.set_color(Color(3, 6, 12, 235))
        g.fill(body)
        g.set_stroke(MapArt.HAIR)
        g.set_color(MapArt.alpha(c, a))
        g.draw(body)
        g.set_color(MapArt.alpha(c, _j.idiv(a, 2)))
        g.draw(RoundRectangle2D.Double((-4.5), (-3.2), 8.5, 6.4, 3, 3))
        if lights:
            g.set_color(Color(255, 244, 214, min(255, (a + 70))))
            g.fill(Rectangle2D.Double(7.4, (-3.7), 1.5, 1.9))
            g.fill(Rectangle2D.Double(7.4, 1.8, 1.5, 1.9))
            g.set_color(Color(255, 70, 96, min(255, (a + 30))))
            g.fill(Rectangle2D.Double((-9), (-3.5), 1.2, 1.7))
            g.fill(Rectangle2D.Double((-9), 1.8, 1.2, 1.7))
    @staticmethod
    def circuit_layers(map_):
        """The Silicon Circuit's (far, near) circuit traces, computed once per map (the bitmap and the data pulses share
them)."""
        key = map_.get_name()
        v = MapArt.CIRCUITS.get(key)
        if v is None:
            p = MapArt.Silicon(map_, None)
            v = (p.circuit(26, 1), p.circuit(9, 2))
            MapArt.CIRCUITS[key] = v
        return v
    @staticmethod
    def weights():
        """The Neural Network's fully-connected weights between consecutive layers (the far network diagram)."""
        w = Path2D.Double()
        for a, b in MapArt.weight_pairs():
            w.append(Line2D.Double(a.x, a.y, b.x, b.y), False)
        return w
    @staticmethod
    def weight_pairs():
        C = NeuralNetwork
        layers = [[C.IN_A, C.IN_B], [C.J1, C.J2], [C.H1, C.H2, C.H3], [C.H4, C.H5], [C.OUT]]
        out = []
        for li in range((len(layers) - 1)):
            for a in layers[li]:
                for b in layers[(li + 1)]:
                    out.append((a, b))
        return out
    @staticmethod
    def hidden_weights(nn):
        """The weights that are not synapse roads (no route runs along them): the ones data pulses may fire along."""
        out = []
        for a, b in MapArt.weight_pairs():
            mid = Vec(((a.x + b.x) / 2), ((a.y + b.y) / 2))
            if all((r.distance_to_point(mid) > MapArt.HW) for r in nn.get_routes()):
                out.append((a, b))
        return out
    @staticmethod
    def ambient():
        """True when the live ambience runs: never with REDUCED MOTION (the map stays still) or on LOW quality."""
        return (not display_settings.reduced_motion()) and (GraphicsSettings.get().quality() is not GraphicsSettings.Quality.LOW)
    @staticmethod
    def ambience_for(map_):
        """The map's Ambience, built once per map: a few items, all on decoration or mechanic features, none on the track
(so nothing can be mistaken for an enemy or a shot)."""
        key = map_.get_name()
        a = MapArt.AMBIENCE.get(key)
        if a is not None:
            return a
        a = MapArt.Ambience(map_)
        rnd = _j.Random((_j.hash_code(key) + 99))
        if isinstance(map_, SiliconCircuit):
            near = sorted(MapArt.circuit_layers(map_)[1], key=lambda t: -MapArt.poly_length(t))
            for i, t in enumerate(near[:5]):
                a.lane(t, MapArt.c(0x7fffb8), (6.5 + (rnd.next_double() * 3)), (i * 1.7))
            for o in map_.get_obstacles():
                if o.label == 'I/O':
                    a.blink(((o.x + o.w) - 16), (o.y + 7), 2.0, MapArt.c(0x3bff8a), 1.4, 0, 0.45)
            for i, (x, y) in enumerate(MapArt.layout_for(map_)['blink']):
                a.blink(x, y, 1.5, MapArt.c(0x3bff8a), (2.2 + i), (i * 0.7), 0.3)
        elif isinstance(map_, LegacyMonolith):
            floors = map_.get_floors()
            ys = [f[0] for f in floors] + [floors[(len(floors) - 1)][1]]
            for k in range(len(ys)):
                pts = [(30.0, ys[k]), ((MapArt.W - 30.0), ys[k])]
                if _j.imod(k, 2) == 1:
                    pts.reverse()
                a.lane(pts, (MapArt.c(0x5aa8ff) if (k < 2) else MapArt.c(0xffb43b)), (13 + (rnd.next_double() * 5)), (k * 3.1), 280.0)
            lay = MapArt.layout_for(map_)
            if lay['header'] is not None:
                hx = (lay['header'][0] + 330)
                hy = (lay['header'][1] + (lay['header'][3] / 2))
                a.blink(((hx + (3 * 12)) + 3), hy, 1.6, MapArt.c(0xffb43b), 1.1, 0, 0.5)
                a.blink(((hx + (11 * 12)) + 3), hy, 1.6, MapArt.c(0x5ce07a), 0.7, 0.2, 0.4)
            obs = map_.get_obstacles()
            for i in (1, 4):
                if i < len(obs):
                    a.blink(((obs[i].x + obs[i].w) - 7), (obs[i].y + 9), 1.8, MapArt.c(0x5ce07a), (1.7 + (i * 0.3)), (i * 0.4), 0.5)
            if lay['fans']:
                fx, fy = lay['fans'][0]
                a.spin(fx, fy, 13, MapArt.alpha(MapArt.c(0x5aa8ff), 60), MapArt.c(0x05070b), 1.6)
        elif isinstance(map_, HallucinationCanyon):
            c = map_.get_center()
            a.breath(c.x, c.y, 50, MapArt.c(0xff8cf0), 4.2, 0, 10, 110, 3)
            for i, n in enumerate(map_.get_nodes()):
                a.breath(n.pos.x, n.pos.y, 36, MapArt.c(0xb48cff), 5.0, (i * 1.25), 0, 70, 2)
            sh = MapArt.layout_for(map_)['shards']
            for i, k in enumerate((1, (len(sh) // 2), (len(sh) - 2))):
                if 0 <= k < len(sh):
                    x, y, w, h, p = sh[k]
                    a.glitch(Rectangle2D.Double((x + 5), (y - 3), (w * 0.8), h), MapArt.alpha((MapArt.c(0x5fe8ff) if p else MapArt.c(0xff8cf0)), 170), 7.0, (i * 37))
        elif isinstance(map_, SingularityCore):
            c = map_.get_center()
            a.sweep(c.x, c.y, SingularityCore.ARENA_RADIUS, MapArt.c(0xd0a0ff), 9.0, 48)
            a.breath(c.x, c.y, 52, MapArt.c(0xffc46a), 3.6, 0, 30, 140, 3)
            lay = MapArt.layout_for(map_)
            if lay['sat'] is not None:
                sx, sy = lay['sat']
                a.blink((sx - 5.0), (sy - 8.7), 1.6, MapArt.c(0xff5a8a), 1.8, 0, 0.18)
            for i, pts in enumerate(lay['arcs'][:3:2]):
                a.glitch(MapArt.polyline(pts), MapArt.alpha(MapArt.c(0xff9af0), 200), 6.0, (i * 53), 1.3)
        elif isinstance(map_, SiliconValley):
            lay = MapArt.layout_for(map_)
            sy = lay['street']
            if sy is not None:
                a.mover([((-30.0), (sy + 5.5)), ((MapArt.W + 30.0), (sy + 5.5))], MapArt.c(0x9fdcff), 62.0, 520.0)
                a.mover([((MapArt.W + 30.0), (sy - 5.5)), ((-30.0), (sy - 5.5))], MapArt.c(0xff8cf0), 47.0, 900.0)
            for o in map_.get_obstacles():
                ad = MapArt.Valley.ad(o)
                if (ad is not None) and (ad[0] == 'AGI SOON'):
                    rx, ry, rw, rh = MapArt.sign_rect([ad[0]], ad[2], ad[3], ad[4], ad[5])
                    a.flicker(Rectangle2D.Double((rx + 1), (ry + 1), (rw - 2), (rh - 2)), Color(3, 5, 10, 175), 7.5, 2.0)
                if (o.label == 'SERVER FARM') and (o.x < 500):
                    a.spin((o.x + 18), (o.y + 30), 9.0, MapArt.alpha(MapArt.c(0x8a7bff), 52), MapArt.c(0x05070b), 2.2)
                if o.label == 'CHARGING HUB':
                    a.blink((o.x + 21), (o.y + 30), 1.8, MapArt.c(0x7dffb0), 1.3, 0, 0.5)
            for o in map_.get_obstacles():
                if o.label in ('GLASS HQ', 'NEXUS HQ'):
                    bx = ((o.x + o.w) - 7)
                    by = (o.y + 7)
                    ph = (rnd.next_double() * 2.8)
                    a.breath(bx, by, 7, MapArt.c(0xff3b4e), 2.8, ph, 0, 60, 0)
                    a.breath(bx, by, 2.2, MapArt.c(0xff6b7a), 2.8, ph, 20, 240, 0)
        elif isinstance(map_, NeuralNetwork):
            for i, (p, q) in enumerate(MapArt.hidden_weights(map_)):
                a.lane([(p.x, p.y), (q.x, q.y)], MapArt.c(0xc6a8ff), (5.5 + (rnd.next_double() * 3)), (i * 1.3))
            for x, y, kind in MapArt.layout_for(map_)['tiles']:
                if kind == 'loss':
                    a.blink((x + 12), (y + 3), 1.5, MapArt.c(0x38e8ff), 1.6, 0, 0.5)
        elif isinstance(map_, AbandonedDataCenter):
            for o in map_.get_obstacles():
                if (o.label or '').startswith('UPS'):
                    a.breath((o.x + 12), (o.y + 16), 12, MapArt.c(0xff3b4e), 3.2, 0, 0, 70, 0)
                    a.breath((o.x + 12), (o.y + 16), 3, MapArt.c(0xff6b7a), 3.2, 0, 60, 240, 0)
            lay = MapArt.layout_for(map_)
            on = [m for m in lay['monitors'] if m[3] < 0.45]
            for i, (x, y, rot, v) in enumerate(on[:2]):
                at = AffineTransform()
                at.rotate(math.radians(rot), x, y)
                a.flicker(at.create_transformed_shape(Rectangle2D.Double((x - 11), (y - 7.5), 22, 13.5)), Color(8, 10, 12, 200), (5.0 + (i * 2.3)), (i * 1.7))
            for i, (x, y, rot, v) in enumerate(lay['beacons'][:2]):
                a.blink(x, y, 2.2, MapArt.c(0xffb43b), (1.1 + (i * 0.25)), (i * 0.5), 0.5)
            if lay['fans']:
                x, y = lay['fans'][0][:2]
                a.spin(x, y, 16, MapArt.alpha(MapArt.c(0xffb43b), 52), MapArt.c(0x05070b), 0.9)
            if lay['sparks']:
                x, y = lay['sparks'][0]
                zap = Path2D.Double()
                for k in range(6):
                    ang = ((k * 1.047) + 0.5)
                    zap.append(Line2D.Double(x, y, (x + (math.cos(ang) * 7)), (y + (math.sin(ang) * 7))), False)
                a.glitch(zap, Color(255, 236, 170, 220), 11.0, 5, 1.0)
        MapArt.AMBIENCE[key] = a
        return a
    @staticmethod
    def polyline(pts, p=None):
        if p is None:
            p = Path2D.Double()
        p.move_to(pts[0][0], pts[0][1])
        for i in range(1, len(pts)):
            p.line_to(pts[i][0], pts[i][1])
        return p
    @staticmethod
    def poly_length(pts):
        return sum(math.hypot((pts[i][0] - pts[(i - 1)][0]), (pts[i][1] - pts[(i - 1)][1])) for i in range(1, len(pts)))
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
MapArt.CIRCUITS = {}
MapArt.AMBIENCE = {}
MapArt.LAYOUTS = {}
MapArt.FIELDS = {}
MapArt.FIELD_STEP = 5.0
MapArt.STRIP = 40.0     # the band beyond each track edge where towers usually stand: no set dressing there
MapArt.HAIR = BasicStroke(1.0, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
MapArt.BEAM = Path2D.Double()      # a moving car's faint headlight cone (car coordinates)
MapArt.BEAM.move_to(9, (-3.6))
MapArt.BEAM.line_to(34, (-10))
MapArt.BEAM.line_to(34, 10)
MapArt.BEAM.line_to(9, 3.6)
MapArt.BEAM.close_path()
MapArt.FLICKER = _j.HashMap()
MapArt.LABEL_FONT = Cyber.display(Font.BOLD, 11)
MapArt.Pulses.serial_version_uid = 1
