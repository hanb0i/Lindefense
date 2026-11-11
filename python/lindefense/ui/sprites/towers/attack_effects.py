"""Lindefense AttackEffects (ported from src/lindefense/ui/sprites/towers/AttackEffects.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.animated import Animated


class AttackEffects:
    """Cartoon attack effects built from VisualEvents: a thick glowing
beam, a crackling chain arc, a hit spark ring and a chunky comic explosion.
Each is a GCompound placed in world coordinates whose
Animated#step fades and grows it, returning false when done."""
    class Beam(GCompound, Animated):
        """A thick beam from a to b with a muzzle flash and an impact star."""
        def __init__(self, ev):
            self.total = 0.0
            self.t = 0.0
            self.glow = None
            self.core = None
            self.flash = None
            self.burst = None
            self.c = None
            GCompound.__init__(self)
            self.burst_scale = 1.0
            self.total = AttackEffects.life(ev, 0.22)
            self.c = Art.rgb(ev.rgb)
            a = ev.a
            b = ev.b
            w = (_j.dmax(2.5, ev.radius) * 1.6)
            self.glow = Art.raw_poly(Art.bar(a.x, a.y, b.x, b.y, (w * 1.8)), Art.alpha(self.c, 110), Art.alpha(self.c, 0))
            self.add(self.glow)
            self.core = Art.raw_poly(Art.bar(a.x, a.y, b.x, b.y, (w * 0.7)), Art.alpha(Color.WHITE, 230), Art.alpha(self.c, 200))
            self.add(self.core)
            self.flash = Art.raw_poly(Art.star(0, 0, (w * 3.5), (w * 1.4), 6, 0), Art.alpha(Color.WHITE, 220), Art.alpha(self.c, 220))
            self.flash.set_location(a.x, a.y)
            self.add(self.flash)
            self.burst = Art.raw_poly(Art.star(0, 0, (w * 3), (w * 1.5), 8, 15), Art.alpha(Art.shade(self.c, 1.3), 230), Art.INK)
            self.burst.set_location(b.x, b.y)
            self.add(self.burst)
        def step(self, dt):
            self.t += dt
            f = _j.dmin(1, (self.t / self.total))
            a = _j.to_int((255 * (1 - f)))
            self.glow.set_fill_color(Art.alpha(self.c, _j.to_int((110 * (1 - f)))))
            self.core.set_fill_color(Art.alpha(Color.WHITE, a))
            self.core.set_color(Art.alpha(self.c, a))
            self.flash.set_fill_color(Art.alpha(Color.WHITE, a))
            self.flash.set_color(Art.alpha(self.c, a))
            self.burst.set_fill_color(Art.alpha(Art.shade(self.c, 1.3), a))
            self.burst.set_color(Art.alpha(Art.INK, a))
            want = (1 + (f * 0.8))
            self.burst.scale((want / self.burst_scale))
            self.burst_scale = want
            return self.t < self.total
    class Chain(GCompound, Animated):
        """A jagged lightning arc that re-crackles every few frames."""
        def __init__(self, ev):
            self.total = 0.0
            self.t = 0.0
            self.a = None
            self.b = None
            self.c = None
            self.spark = None
            GCompound.__init__(self)
            self.since_crackle = 1.0
            self.segs = _j.ArrayList(10)
            self.seed = 12345
            self.total = AttackEffects.life(ev, 0.22)
            self.a = ev.a
            self.b = ev.b
            self.c = Art.rgb(ev.rgb)
            self.spark = Art.glow(self, self.b.x, self.b.y, 6, Art.shade(self.c, 1.3), 220)
            self.crackle(1)
        def rnd(self):
            self.seed = ((self.seed * 6364136223846793005) + 1442695040888963407)
            return ((_j.ushr64(self.seed, 11) & 0xffffff) / float(0x1000000)) - 0.5
        def crackle(self, alpha):
            for p in self.segs:
                self.remove(p)
            self.segs.clear()
            n = 5
            dx = (self.b.x - self.a.x)
            dy = (self.b.y - self.a.y)
            len_ = math.hypot(dx, dy)
            nx = (0 if (len_ < 1e-6) else ((-dy) / len_))
            ny = (0 if (len_ < 1e-6) else (dx / len_))
            amp = _j.dmin(14, (len_ * 0.18))
            px = self.a.x
            py = self.a.y
            for i in range(1, n + 1):
                f = (i / float(n))
                off = (0 if (i == n) else ((self.rnd() * 2) * amp))
                qx = ((self.a.x + (dx * f)) + (nx * off))
                qy = ((self.a.y + (dy * f)) + (ny * off))
                outer = Art.raw_poly(Art.bar(px, py, qx, qy, 2.6), Art.alpha(self.c, _j.to_int((170 * alpha))), Art.alpha(self.c, 0))
                inner = Art.raw_poly(Art.bar(px, py, qx, qy, 1.0), Art.alpha(Color.WHITE, _j.to_int((240 * alpha))), Art.alpha(Color.WHITE, 0))
                self.add(outer)
                self.add(inner)
                _j_add(self.segs, outer)
                _j_add(self.segs, inner)
                px = qx
                py = qy
            self.spark.send_to_front()
        def step(self, dt):
            self.t += dt
            self.since_crackle += dt
            f = _j.dmin(1, (self.t / self.total))
            if self.since_crackle > 0.045:
                self.since_crackle = 0.0
                self.crackle((1 - f))
            rad = (6 * (1 + f))
            self.spark.set_bounds((self.b.x - rad), (self.b.y - rad), (2 * rad), (2 * rad))
            self.spark.set_fill_color(Art.alpha(Art.shade(self.c, 1.3), _j.to_int((220 * (1 - f)))))
            return self.t < self.total
    class Hit(GCompound, Animated):
        """A small expanding ring with four radiating sparks."""
        def __init__(self, ev):
            self.total = 0.0
            self.r0 = 0.0
            self.t = 0.0
            self.a = None
            self.c = None
            self.ring = None
            self.sparks = None
            GCompound.__init__(self)
            self.spark_scale = 1.0
            self.total = AttackEffects.life(ev, 0.18)
            self.a = ev.a
            self.c = Art.rgb(ev.rgb)
            self.r0 = _j.dmax(4, ev.radius)
            self.ring = Flat.Oval((self.a.x - self.r0), (self.a.y - self.r0), (2 * self.r0), (2 * self.r0))
            self.ring.set_color(Art.alpha(Color.WHITE, 230))
            self.add(self.ring)
            self.sparks = Art.raw_poly(Art.star(0, 0, (self.r0 * 2.2), (self.r0 * 0.5), 4, 0), Art.alpha(Art.shade(self.c, 1.2), 230), Art.alpha(Art.INK, 200))
            self.sparks.set_location(self.a.x, self.a.y)
            self.add(self.sparks)
        def step(self, dt):
            self.t += dt
            f = _j.dmin(1, (self.t / self.total))
            rad = (self.r0 * (1 + (1.6 * f)))
            self.ring.set_bounds((self.a.x - rad), (self.a.y - rad), (2 * rad), (2 * rad))
            self.ring.set_color(Art.alpha(Color.WHITE, _j.to_int((230 * (1 - f)))))
            want = (1 + (f * 0.9))
            self.sparks.scale((want / self.spark_scale))
            self.spark_scale = want
            self.sparks.set_fill_color(Art.alpha(Art.shade(self.c, 1.2), _j.to_int((230 * (1 - f)))))
            self.sparks.set_color(Art.alpha(Art.INK, _j.to_int((200 * (1 - f)))))
            return self.t < self.total
    class Explosion(GCompound, Animated):
        """A chunky comic explosion: dark rim, coloured fill, hot white core, spiky burst and flying debris."""
        def __init__(self, ev):
            self.total = 0.0
            self.radius = 0.0
            self.t = 0.0
            self.a = None
            self.c = None
            self.rim = None
            self.fill = None
            self.core = None
            self.burst = None
            GCompound.__init__(self)
            self.burst_scale = 1.0
            self.debris = ([None] * 4)
            self.total = AttackEffects.life(ev, 0.35)
            self.a = ev.a
            self.c = Art.rgb(ev.rgb)
            self.radius = _j.dmax(10, ev.radius)
            self.rim = Art.glow(self, self.a.x, self.a.y, 1, Art.INK, 200)
            self.fill = Art.glow(self, self.a.x, self.a.y, 1, self.c, 220)
            self.burst = Art.raw_poly(Art.star(0, 0, (self.radius * 0.9), (self.radius * 0.45), 9, 10), Art.alpha(Art.shade(self.c, 1.25), 240), Art.alpha(Art.INK, 230))
            self.burst.set_location(self.a.x, self.a.y)
            self.add(self.burst)
            self.core = Art.glow(self, self.a.x, self.a.y, 1, Art.rgb(0xfff4c2), 250)
            for i in range(len(self.debris)):
                self.debris[i] = Art.glow(self, self.a.x, self.a.y, (self.radius * 0.1), (Art.INK if (_j.imod(i, 2) == 0) else Art.shade(self.c, 0.8)), 230)
        def step(self, dt):
            self.t += dt
            f = _j.dmin(1, (self.t / self.total))
            grow = math.sin(((_j.dmin(1, (f * 1.4)) * math.pi) / 2))
            rr = (self.radius * (0.35 + (0.65 * grow)))
            a255 = _j.to_int((255 * (1 - (f * f))))
            self.rim.set_bounds((self.a.x - (rr * 1.08)), (self.a.y - (rr * 1.08)), (rr * 2.16), (rr * 2.16))
            self.rim.set_fill_color(Art.alpha(Art.INK, _j.to_int((200 * (1 - (f * f))))))
            self.fill.set_bounds((self.a.x - rr), (self.a.y - rr), (rr * 2), (rr * 2))
            self.fill.set_fill_color(Art.alpha(self.c, _j.to_int((220 * (1 - (f * f))))))
            cr = (rr * (0.55 - (0.3 * f)))
            self.core.set_bounds((self.a.x - cr), (self.a.y - cr), (cr * 2), (cr * 2))
            self.core.set_fill_color(Art.alpha(Art.rgb(0xfff4c2), _j.to_int((250 * (1 - f)))))
            want = (0.4 + (1.0 * grow))
            self.burst.scale((want / self.burst_scale))
            self.burst_scale = want
            self.burst.set_fill_color(Art.alpha(Art.shade(self.c, 1.25), a255))
            self.burst.set_color(Art.alpha(Art.INK, _j.to_int((230 * (1 - f)))))
            for i in range(len(self.debris)):
                ang = (((i * math.pi) / 2) + 0.6)
                d = (self.radius * (0.3 + (1.2 * f)))
                dr = ((self.radius * 0.1) * (1 - (f * 0.5)))
                self.debris[i].set_bounds(((self.a.x + (math.cos(ang) * d)) - dr), (((self.a.y + ((math.sin(ang) * d) * 0.8)) - dr) + (((self.radius * 0.6) * f) * f)), (dr * 2), (dr * 2))
                self.debris[i].set_fill_color(Art.alpha((Art.INK if (_j.imod(i, 2) == 0) else Art.shade(self.c, 0.8)), _j.to_int((230 * (1 - f)))))
            return self.t < self.total
    def __init__(self):
        pass
    @staticmethod
    def life(ev, min_):
        return _j.dmax(min_, ev.duration)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402
from lindefense.ui.sprites.towers.flat import Flat  # noqa: E402

AttackEffects.Beam.serial_version_uid = 1
AttackEffects.Chain.serial_version_uid = 1
AttackEffects.Hit.serial_version_uid = 1
AttackEffects.Explosion.serial_version_uid = 1
