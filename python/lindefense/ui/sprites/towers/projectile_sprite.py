"""Lindefense ProjectileSprite (ported from src/lindefense/ui/sprites/towers/ProjectileSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.jenum import JEnum
from lindefense.ui.sprites.animated import Animated


class ProjectileSprite(GCompound, Animated):
    """Cartoon projectile. Each sprite is one of a small set of Styles
(lance, token, shell, ...) built once from at most ~6 ACM objects; afterwards
#sync only moves and rotates it. Parts authored pointing +x turn
with the velocity; "spinner" parts tumble continuously; a glow may pulse."""
    class Style(JEnum):
        """Visual families; ProjectileSprites picks one per tower type."""
        LANCE = ()
        TOKEN = ()
        SLUG = ()
        SNIPPET = ()
        PAINT = ()
        NOTE = ()
        BOLT = ()
        PIN = ()
        BLADE = ()
        WAD = ()
        GALE = ()
        ORB = ()
        ROUND = ()
        BOOK = ()
        SHELL = ()
        SPARK = ()
        PULSE = ()
        DOT = ()
        COMMAND = ()
        VOLLEY = ()
        CRYO = ()
        METEOR = ()
        DATA = ()
        DRONE = ()
        QUANTUM = ()
        SINGULARITY = ()
    def __init__(self, style, tier, size, c, c2):
        self.pulse_ring = None
        self.flicker = None
        self.flicker_color = None
        self.spin_speed = 0.0
        self.heading = 0.0
        self.t = 0.0
        self.base_radius = 0.0
        GCompound.__init__(self)
        self.oriented = _j.ArrayList(4)
        self.spinners = _j.ArrayList(3)
        self.alive = True
        tier = max(0, min(4, tier))
        k = ((size / 6.0) * (1 + (0.12 * tier)))
        self.base_radius = (size * (1 + (0.12 * tier)))
        self.build(style, tier, k, c, c2)
    def part(self, xy, fill):
        ink = Art.raw_poly(Art.expand(xy, (Art.OUT * 0.8)), Art.INK, Art.INK)
        self.add(ink)
        _j_add(self.oriented, ink)
        p = Art.raw_poly(xy, fill, Art.shade(fill, 0.75))
        self.add(p)
        _j_add(self.oriented, p)
        return p
    def plain_part(self, xy, fill):
        p = Art.raw_poly(xy, fill, fill)
        self.add(p)
        _j_add(self.oriented, p)
        return p
    def spin_part(self, xy, fill, outline):
        if outline:
            ink = Art.raw_poly(Art.expand(xy, (Art.OUT * 0.8)), Art.INK, Art.INK)
            self.add(ink)
            _j_add(self.spinners, ink)
        p = Art.raw_poly(xy, fill, (Art.shade(fill, 0.75) if outline else fill))
        self.add(p)
        _j_add(self.spinners, p)
        return p
    def build(self, s, tier, k, c, c2):
        _sw1 = s
        if _sw1 is ProjectileSprite.Style.LANCE:
            len_ = (k * (16 + (4 * tier)))
            hw = (k * 1.7)
            self.plain_part(Art.wedge(((-len_) * 0.3), ((-len_) * 1.4), (hw * 1.6), 0), Art.alpha(c, 90))
            self.part([((-len_) / 2), (-hw), ((len_ / 2) - (hw * 2.5)), (-hw), ((len_ / 2) + hw), 0, ((len_ / 2) - (hw * 2.5)), hw, ((-len_) / 2), hw], (Art.GOLD if (tier >= 4) else c))
            self.plain_part(Art.rect(((-len_) * 0.4), ((-hw) * 0.35), (len_ * 0.75), (hw * 0.7)), (Color.WHITE if (tier >= 3) else c2))
            pass  # break
        elif _sw1 is ProjectileSprite.Style.TOKEN:
            rad = (k * 5.5)
            self.plain_part(Art.wedge(0, ((-rad) * 3), (rad * 0.8), 0), Art.alpha(c, 80))
            self.part((Art.star(0, 0, (rad * 1.2), (rad * 0.8), 8, 0) if (tier >= 3) else Art.circle(0, 0, rad, 14)), c)
            self.plain_part(Art.circle(0, 0, (rad * 0.45), 10), Color.WHITE)
            self.plain_part(Art.circle(((-rad) * 0.35), ((-rad) * 0.4), (rad * 0.22), 6), Art.alpha(Color.WHITE, 200))
            pass  # break
        elif _sw1 is ProjectileSprite.Style.SLUG:
            len_ = (k * 14)
            hw = (k * 2.2)
            self.plain_part(Art.wedge(((-len_) * 0.2), ((-len_) * 1.8), (hw * 1.3), 0), Art.alpha(c2, 100))
            self.part(Art.bar(((-len_) / 2), 0, (len_ / 2), 0, hw), c)
            self.plain_part(Art.rect(((-len_) * 0.35), ((-hw) * 0.3), (len_ * 0.7), (hw * 0.6)), (Color.WHITE if (tier >= 4) else c2))
            self.plain_part(Art.circle((len_ / 2), 0, (hw * 1.1), 8), Art.alpha(Color.WHITE, 220))
            pass  # break
        elif _sw1 is ProjectileSprite.Style.SNIPPET:
            w = (k * 11)
            h = (k * 7)
            self.part(Art.rect(((-w) / 2), ((-h) / 2), w, h), c2)
            self.plain_part(Art.rect(((-w) * 0.38), ((-h) * 0.3), (w * 0.12), (h * 0.6)), c)
            self.plain_part(Art.rect((w * 0.26), ((-h) * 0.3), (w * 0.12), (h * 0.6)), c)
            self.plain_part(Art.rect(((-w) * 0.18), ((-h) * 0.08), (w * 0.36), (h * 0.16)), (Art.GOLD if (tier >= 4) else c))
            self.spin_speed = 0.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.PAINT:
            rad = (k * 5.5)
            self.part(Art.circle(0, 0, rad, 14), c)
            self.plain_part(Art.circle(((-rad) * 0.3), ((-rad) * 0.35), (rad * 0.3), 8), Art.alpha(Color.WHITE, 200))
            self.spin_part(Art.circle((rad * 1.35), 0, (rad * 0.35), 8), Art.shade(c, 1.2), False)
            self.spin_part(Art.circle(((-rad) * 0.6), (rad * 1.25), (rad * 0.28), 8), c2, False)
            self.spin_speed = 400.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.NOTE:
            rad = (k * 4.5)
            self.spin_part(Art.bar((rad * 0.9), 0, (rad * 0.9), ((-rad) * 3.2), (rad * 0.3)), c, True)
            self.spin_part([(rad * 0.9), ((-rad) * 3.2), (rad * 2.4), ((-rad) * 2.2), (rad * 0.9), ((-rad) * 1.8)], c, True)
            self.spin_part(Art.regular(0, 0, rad, 10, 0), c, True)
            self.spin_part(Art.circle(((-rad) * 0.3), ((-rad) * 0.3), (rad * 0.3), 6), Art.alpha(Color.WHITE, 200), False)
            self.spin_speed = 240.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.BOLT:
            len_ = (k * 16)
            amp = (k * 4)
            self.flicker = self.part(Art.bolt(((-len_) / 2), (len_ / 2), amp, (k * 1.5)), c2)
            self.flicker_color = c2
            self.plain_part(Art.scaled(Art.bolt(((-len_) / 2), (len_ / 2), amp, (k * 1.5)), 0.5), Color.WHITE)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.PIN:
            len_ = (k * 13)
            hw = (k * 3)
            self.plain_part(Art.wedge(0, ((-len_) * 1.3), (hw * 0.6), 0), Art.alpha(c, 90))
            self.part(Art.wedge(((-len_) / 2), (len_ / 2), hw, 0), c)
            self.part(Art.circle(((-len_) * 0.3), 0, (hw * 0.7), 10), c2)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.BLADE:
            rad = (k * 7)
            self.spin_part(Art.star(0, 0, rad, (rad * 0.45), (3 + _j.idiv(tier, 2)), 0), c, True)
            self.spin_part(Art.circle(0, 0, (rad * 0.25), 8), c2, False)
            self.spin_speed = 900.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.WAD:
            rad = (k * 6)
            v = ([0.0] * 14)
            bumps = [1, 0.8, 1.05, 0.85, 1, 0.75, 0.95]
            for i in range(7):
                a = (((i * 2) * math.pi) / 7)
                v[(2 * i)] = ((math.cos(a) * rad) * bumps[i])
                v[((2 * i) + 1)] = ((math.sin(a) * rad) * bumps[i])
            self.spin_part(v, c, True)
            self.spin_part(Art.circle(((-rad) * 0.3), ((-rad) * 0.3), (rad * 0.3), 6), Art.alpha(Color.WHITE, 200), False)
            self.spin_speed = 360.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.GALE:
            rad = (k * 8)
            v = ([0.0] * 28)
            for i in range(7):
                a = (((-math.pi) * 0.45) + (((i * math.pi) * 0.9) / 6))
                v[(2 * i)] = (math.cos(a) * rad)
                v[((2 * i) + 1)] = (math.sin(a) * rad)
            for i in range(7):
                a = ((math.pi * 0.45) - (((i * math.pi) * 0.9) / 6))
                v[(14 + (2 * i))] = (((math.cos(a) * rad) * 0.55) + (rad * 0.25))
                v[((14 + (2 * i)) + 1)] = ((math.sin(a) * rad) * 0.55)
            self.spin_part(v, c2, True)
            self.spin_part(Art.scaled(v, 0.5), Art.alpha(Color.WHITE, 160), False)
            self.spin_speed = 720.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.ORB:
            rad = (k * 5.5)
            self.plain_part(Art.wedge(0, ((-rad) * 2.5), (rad * 0.7), 0), Art.alpha(c, 80))
            self.part(Art.circle(0, 0, rad, 14), c)
            self.plain_part(Art.circle(((-rad) * 0.3), ((-rad) * 0.35), (rad * 0.32), 8), Art.alpha(Color.WHITE, 210))
            if tier >= 2:
                self.spin_part(Art.circle((rad * 1.7), 0, (rad * 0.35), 8), c2, False)
                self.spin_part(Art.circle(((-rad) * 1.7), 0, (rad * 0.35), 8), c2, False)
                self.spin_speed = 500.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.ROUND:
            len_ = (k * 18)
            hw = (k * 1.3)
            self.plain_part(Art.rect(((-len_) * 1.6), ((-hw) * 0.6), (len_ * 1.3), (hw * 1.2)), Art.alpha(c2, 110))
            self.part(Art.bar(((-len_) / 2), 0, (len_ / 2), 0, hw), (Art.GOLD if (tier >= 4) else c))
            self.plain_part(Art.rect(((-len_) * 0.3), ((-hw) * 0.3), (len_ * 0.7), (hw * 0.6)), Color.WHITE)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.BOOK:
            w = (k * 10)
            h = (k * 7.5)
            self.spin_part(Art.rect(((-w) / 2), ((-h) / 2), w, h), c, True)
            self.spin_part(Art.rect(((-w) / 2), ((-h) / 2), (w * 0.2), h), Art.shade(c, 0.7), False)
            self.spin_part(Art.rect(((-w) * 0.15), ((-h) * 0.25), (w * 0.5), (h * 0.12)), Color.WHITE, False)
            self.spin_speed = 300.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.SHELL:
            len_ = (k * 15)
            hw = (k * 3.2)
            self.plain_part(Art.circle(((-len_) * 0.9), 0, (hw * 1.2), 8), Art.alpha(0xbbbbbb, 110))
            self.plain_part(Art.circle(((-len_) * 1.5), (hw * 0.3), (hw * 0.9), 8), Art.alpha(0xbbbbbb, 70))
            self.part([((-len_) / 2), (-hw), (len_ * 0.2), (-hw), (len_ / 2), 0, (len_ * 0.2), hw, ((-len_) / 2), hw], Art.rgb(0x2b2b33))
            self.plain_part(Art.rect(((-len_) * 0.2), ((-hw) * 0.9), (len_ * 0.18), (hw * 1.8)), Art.GOLD)
            self.plain_part([(len_ * 0.2), ((-hw) * 0.8), (len_ / 2), 0, (len_ * 0.2), (hw * 0.8)], (Art.GOLD if (tier >= 4) else Art.rgb(0xff7a00)))
            pass  # break
        elif _sw1 is ProjectileSprite.Style.PULSE:
            self.pulse_ring = Flat.Oval(((-k) * 6), ((-k) * 6), (k * 12), (k * 12))
            self.pulse_ring.set_color(Art.alpha(c, 200))
            self.add(self.pulse_ring)
            self.plain_part(Art.circle(0, 0, (k * 2.5), 8), Art.alpha(c, 200))
            pass  # break
        elif _sw1 is ProjectileSprite.Style.SPARK:
            rad = (k * 6)
            self.spin_part(Art.star(0, 0, rad, (rad * 0.4), 4, 0), c, True)
            self.spin_part(Art.circle(0, 0, (rad * 0.3), 8), Color.WHITE, False)
            self.spin_speed = 420.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.COMMAND:
            rad = (k * 8)
            self.plain_part(Art.wedge(0, ((-rad) * 2.6), (rad * 0.9), 0), Art.alpha(Art.rgb(0xfff3a0), 90))
            self.part(Art.circle(0, 0, rad, 16), c)
            self.plain_part(Art.circle(0, 0, (rad * 0.6), 12), Art.rgb(0xfff3a0))
            self.plain_part(Art.circle(0, 0, (rad * 0.3), 10), Color.WHITE)
            self.spin_part(Art.star(0, 0, (rad * 1.5), (rad * 0.9), 5, 0), Art.alpha(Art.rgb(0xfff3a0), 150), False)
            self.spin_speed = 380.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.VOLLEY:
            len_ = (k * 15)
            hw = (k * 1.2)
            self.plain_part(Art.rect(((-len_) * 1.5), ((-hw) * 0.5), (len_ * 1.2), hw), Art.alpha(c, 110))
            self.part([((-len_) / 2), (-hw), ((len_ / 2) - hw), (-hw), ((len_ / 2) + (hw * 2)), 0, ((len_ / 2) - hw), hw, ((-len_) / 2), hw], c)
            self.plain_part(Art.rect(((-len_) * 0.35), ((-hw) * 0.35), (len_ * 0.7), (hw * 0.7)), Color.WHITE)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.CRYO:
            rad = (k * 6.5)
            self.plain_part(Art.wedge(0, ((-rad) * 2.4), (rad * 0.7), 0), Art.alpha(Art.rgb(0x8fe6ff), 100))
            self.spin_part(Art.star(0, 0, rad, (rad * 0.45), 6, 0), Art.rgb(0x8fe6ff), True)
            self.spin_part(Art.star(0, 0, (rad * 0.55), (rad * 0.25), 6, 30), Color.WHITE, False)
            self.spin_speed = 260.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.METEOR:
            rad = (k * 7.5)
            self.plain_part(Art.wedge(0, ((-rad) * 3.2), (rad * 1.1), 0), Art.alpha(Art.rgb(0xff5a1f), 120))
            self.plain_part(Art.wedge(0, ((-rad) * 2.2), (rad * 0.7), 0), Art.alpha(Art.rgb(0xffd166), 160))
            v = ([0.0] * 16)
            bumps = [1, 0.82, 1.08, 0.9, 1, 0.78, 1.04, 0.86]
            for i in range(8):
                a = ((i * math.pi) / 4)
                v[(2 * i)] = ((math.cos(a) * rad) * bumps[i])
                v[((2 * i) + 1)] = ((math.sin(a) * rad) * bumps[i])
            self.spin_part(v, Art.rgb(0x4a3530), True)
            self.spin_part(Art.circle((rad * 0.2), (rad * 0.1), (rad * 0.35), 8), Art.rgb(0xffb02e), False)
            self.spin_part(Art.circle(((-rad) * 0.35), ((-rad) * 0.3), (rad * 0.2), 6), Art.rgb(0xff5a1f), False)
            self.spin_speed = 200.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.DATA:
            w = (k * 9)
            h = (k * 6)
            self.plain_part(Art.rect(((-w) * 1.6), ((-h) * 0.15), (w * 0.3), (h * 0.3)), Art.alpha(c, 160))
            self.plain_part(Art.rect(((-w) * 1.15), ((-h) * 0.15), (w * 0.3), (h * 0.3)), Art.alpha(c, 200))
            self.part(Art.regular(0, 0, (w * 0.6), 6, 0), c)
            self.plain_part(Art.rect(((-w) * 0.25), ((-h) * 0.25), (w * 0.15), (h * 0.5)), Color.WHITE)
            self.plain_part(Art.rect((w * 0.05), ((-h) * 0.25), (w * 0.15), (h * 0.5)), Color.WHITE)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.DRONE:
            len_ = (k * 10)
            hw = (k * 1.6)
            self.plain_part(Art.wedge(((-len_) * 0.3), ((-len_) * 1.4), hw, 0), Art.alpha(Art.rgb(0x5fd6ff), 120))
            self.part(Art.wedge(((-len_) / 2), (len_ / 2), (hw * 1.4), 0), Art.rgb(0x5fd6ff))
            self.plain_part(Art.circle((len_ * 0.1), 0, (hw * 0.6), 6), Color.WHITE)
            pass  # break
        elif _sw1 is ProjectileSprite.Style.QUANTUM:
            rad = (k * (5.5 + (0.6 * tier)))
            self.plain_part(Art.wedge(0, ((-rad) * (2.4 + (0.5 * tier))), (rad * 0.75), 0), Art.alpha(c2, (90 + (25 * tier))))
            self.part([(-rad), 0, 0, ((-rad) * 0.7), (rad * 1.3), 0, 0, (rad * 0.7)], c)
            self.plain_part([((-rad) * 0.4), 0, 0, ((-rad) * 0.3), (rad * 0.6), 0, 0, (rad * 0.3)], c2)
            self.plain_part(Art.circle(0, 0, (rad * 0.18), 6), Color.WHITE)
            if tier >= 2:
                self.spin_part(Art.circle((rad * 1.5), 0, (rad * 0.25), 8), c2, False)
                self.spin_part(Art.circle(((-rad) * 1.5), 0, (rad * 0.25), 8), (Art.GOLD if (tier >= 4) else c), False)
                self.spin_speed = 600.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.SINGULARITY:
            rad = (k * 7)
            self.plain_part(Art.ring(0, 0, (rad * 1.9), (rad * 1.25), 18), Art.alpha(c, 170))
            self.part(Art.circle(0, 0, rad, 14), Color(0x07040f))
            self.plain_part(Art.ring(0, 0, (rad * 1.25), (rad * 1.0), 16), Art.alpha(c2, 230))
            self.spin_part(Art.rect((rad * 2.0), ((-rad) * 0.18), (rad * 0.55), (rad * 0.36)), Color.WHITE, False)
            self.spin_part(Art.rect(((-rad) * 2.55), ((-rad) * 0.18), (rad * 0.55), (rad * 0.36)), c, False)
            self.spin_part(Art.rect(((-rad) * 0.18), (rad * 2.0), (rad * 0.36), (rad * 0.55)), c2, False)
            self.spin_speed = 420.0
            pass  # break
        elif _sw1 is ProjectileSprite.Style.DOT:
            rad = (k * 5.5)
            self.part(Art.circle(0, 0, rad, 12), c)
            self.plain_part(Art.circle(((-rad) * 0.3), ((-rad) * 0.35), (rad * 0.3), 8), Art.alpha(Color.WHITE, 200))
            pass  # break
    def sync(self, p, time_):
        """Positions the sprite on the projectile and turns it along its velocity."""
        if p is None:
            return
        self.alive = p.is_alive()
        pos = p.get_position()
        v = p.get_velocity()
        self.place(pos.x, pos.y, v.x, v.y, time_)
    def place(self, x, y, vx, vy, time_):
        """Manual placement (used by galleries and tests)."""
        self.set_location(x, y)
        if ((abs(vx) + abs(vy)) > 1e-6) and (not (len(self.oriented) == 0)):
            want = math.atan2(vy, vx)
            d = (want - self.heading)
            while d > math.pi:
                d -= (2 * math.pi)
            while d < (-math.pi):
                d += (2 * math.pi)
            if abs(d) > 1e-4:
                deg = (-math.degrees(d))
                for q in self.oriented:
                    q.rotate(deg)
                self.heading = want
    def step(self, dt):
        """Advances spin / pulse; returns false once the synced projectile has died."""
        self.t += dt
        if self.spin_speed != 0:
            deg = (self.spin_speed * dt)
            for q in self.spinners:
                q.rotate(deg)
        if self.pulse_ring is not None:
            ph = (_j.fmod(self.t, 0.5) / 0.5)
            rad = (self.base_radius * (0.6 + (1.4 * ph)))
            self.pulse_ring.set_bounds((-rad), (-rad), (2 * rad), (2 * rad))
            self.pulse_ring.set_color(Art.alpha(self.pulse_ring.get_color(), _j.to_int((220 * (1 - ph)))))
        if self.flicker is not None:
            self.flicker.set_fill_color((self.flicker_color if (_j.imod(_j.to_int((self.t * 30)), 2) == 0) else Art.shade(self.flicker_color, 1.4)))
        return self.alive
    def finish(self):
        """Marks the sprite finished so the next #step returns false."""
        self.alive = False


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402
from lindefense.ui.sprites.towers.flat import Flat  # noqa: E402

ProjectileSprite.serial_version_uid = 1
