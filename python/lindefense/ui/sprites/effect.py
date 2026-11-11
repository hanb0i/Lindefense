"""Lindefense Effect (ported from src/lindefense/ui/sprites/Effect.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.animated import Animated


class Effect(GCompound, Animated):
    """A self-contained, one-shot visual effect. Everything is built in the
constructor; #step advances an internal clock and moves, resizes or
fades the pieces until #duration has passed.

Two building blocks cover most needs: #shards (flying particles
with gravity and fade) and #ring (an expanding, fading ring).
Effects can also be nested via #stage so bosses can chain several
bursts with delays."""
    class Particle:
        def __init__(self):
            self.g = None
            self.x0 = 0.0
            self.y0 = 0.0
            self.vx = 0.0
            self.vy = 0.0
            self.gravity = 0.0
            self.delay = 0.0
            self.life = 0.0
            self.spin = 0.0
            self.w = 0.0
            self.h = 0.0
            self.c = None
            self.shrink = False
            pass
    class Ring:
        def __init__(self):
            self.g = None
            self.r0 = 0.0
            self.r1 = 0.0
            self.delay = 0.0
            self.life = 0.0
            self.c = None
            self.filled = False
            pass
    def __init__(self, x, y, duration):
        self.duration = 0.0
        self.t = 0.0
        self.done = False
        GCompound.__init__(self)
        self.particles = _j.ArrayList()
        self.rings = _j.ArrayList()
        self.stages = _j.ArrayList()
        self.stage_delay = _j.ArrayList()
        self.stage_done = _j.ArrayList()
        self.duration = duration
        self.set_location(x, y)
    @staticmethod
    def rnd(seed):
        """Hashes a seed into a pseudo-random double in [0,1)."""
        seed = ((seed ^ 0x5DEECE66D) * 0x2545F4914F6CDD1D)
        seed = (seed ^ _j.ushr64(seed, 29))
        return (_j.ushr64(seed, 11) & 0xFFFFFFFF) / 4294967296.0
    def shards(self, n, cx, cy, size, speed, gravity, c, shape, delay, life, seed):
        """Adds n shards flying out from (cx,cy).

@param shape 0 = triangles, 1 = quads, 2 = circles, 3 = thin slivers"""
        for i in range(n):
            a = (((2 * math.pi) * (i + Effect.rnd((seed + (i * 7))))) / n)
            sp = (speed * (0.55 + (0.9 * Effect.rnd(((seed + (i * 13)) + 1)))))
            s = (size * (0.6 + (0.8 * Effect.rnd(((seed + (i * 17)) + 2)))))
            p = Effect.Particle()
            p.x0 = cx
            p.y0 = cy
            p.vx = (math.cos(a) * sp)
            p.vy = ((math.sin(a) * sp) - (speed * 0.2))
            p.gravity = gravity
            p.delay = delay
            p.life = (life * (0.75 + (0.5 * Effect.rnd(((seed + (i * 19)) + 3)))))
            p.c = c
            p.w = s
            p.h = s
            p.spin = ((Effect.rnd((seed + i)) - 0.5) * 720)
            p.shrink = (shape != 2)
            _sw1 = shape
            if _sw1 == 0:
                g = Art.poly([((-s) / 2), (s / 2), (s / 2), (s / 2), 0, ((-s) / 2)])
            elif _sw1 == 1:
                g = Art.poly([((-s) / 2), ((-s) / 2), (s / 2), ((-s) / 2), (s / 2), (s / 2), ((-s) / 2), (s / 2)])
            elif _sw1 == 3:
                g = Art.poly([(-s), ((-s) * 0.15), s, ((-s) * 0.15), s, (s * 0.15), (-s), (s * 0.15)])
            else:
                g = Art.oval_at(0, 0, s, s)
            g.set_filled(True)
            g.set_fill_color(c)
            g.set_color(Art.outline(c))
            g.set_visible(False)
            p.g = g
            self.add(g)
            _j_add(self.particles, p)
    def piece(self, g, cx, cy, vx, vy, gravity, c, delay, life, spin_deg_per_sec, shrink):
        """Adds a single drifting particle (used for halves and other bespoke pieces)."""
        p = Effect.Particle()
        p.g = g
        p.x0 = cx
        p.y0 = cy
        p.vx = vx
        p.vy = vy
        p.gravity = gravity
        p.delay = delay
        p.life = life
        p.c = c
        p.spin = spin_deg_per_sec
        p.shrink = shrink
        p.w = g.get_width()
        p.h = g.get_height()
        if isinstance(g, GFillable):
            g.set_filled(True)
            g.set_fill_color(c)
        g.set_color(Art.outline(c))
        g.set_visible(False)
        self.add(g)
        _j_add(self.particles, p)
        return g
    def ring(self, cx, cy, r0, r1, c, delay, life, filled):
        """Adds an expanding ring from radius r0 to r1 (filled = a flash disc, drawn at a fraction of its strength with
REDUCED MOTION on so death and boss explosions never flash the screen)."""
        if filled and display_settings.reduced_motion():
            c = Art.alpha(c, _j.to_int((c.get_alpha() * Effect.CALM_FLASH)))
        rg = Effect.Ring()
        rg.g = Art.oval_at(cx, cy, (r0 * 2), (r0 * 2))
        rg.g.set_filled(filled)
        rg.g.set_fill_color(c)
        rg.g.set_color(c)
        rg.g.set_visible(False)
        rg.r0 = r0
        rg.r1 = r1
        rg.c = c
        rg.delay = delay
        rg.life = life
        rg.filled = filled
        self.add(rg.g)
        _j_add(self.rings, rg)
    def stage(self, e, delay):
        """Nests another effect (positioned relative to this one) that starts after delay."""
        e.set_visible(False)
        self.add(e)
        _j_add(self.stages, e)
        _j_add(self.stage_delay, delay)
        _j_add(self.stage_done, False)
    def step(self, dt):
        if self.done:
            return False
        self.t += dt
        self.update(self.t)
        for p in self.particles:
            lt = (self.t - p.delay)
            if (lt < 0) or (lt > p.life):
                if p.g.is_visible():
                    p.g.set_visible(False)
                continue
            x = (p.x0 + (p.vx * lt))
            y = ((p.y0 + (p.vy * lt)) + (((0.5 * p.gravity) * lt) * lt))
            f = (1 - (lt / p.life))
            k = ((0.35 + (0.65 * f)) if p.shrink else 1)
            if isinstance(p.g, GPolygon):
                p.g.set_location(x, y)
                if p.spin != 0:
                    p.g.rotate((p.spin * dt))
            elif isinstance(p.g, GOval):
                p.g.set_bounds((x - ((p.w * k) / 2)), (y - ((p.h * k) / 2)), (p.w * k), (p.h * k))
            else:
                p.g.set_location((x - (p.w / 2)), (y - (p.h / 2)))
            a = _j.to_int((p.c.get_alpha() * _j.dmin(1, (f * 1.6))))
            if isinstance(p.g, GFillable):
                p.g.set_fill_color(Art.alpha(p.c, a))
            p.g.set_color(Art.alpha(Art.outline(p.c), a))
            p.g.set_visible(True)
        for rg in self.rings:
            lt = (self.t - rg.delay)
            if (lt < 0) or (lt > rg.life):
                if rg.g.is_visible():
                    rg.g.set_visible(False)
                continue
            f = (lt / rg.life)
            e = (1 - ((1 - f) * (1 - f)))
            rad = (rg.r0 + ((rg.r1 - rg.r0) * e))
            cx = (rg.g.get_x() + (rg.g.get_width() / 2))
            cy = (rg.g.get_y() + (rg.g.get_height() / 2))
            rg.g.set_bounds((cx - rad), (cy - rad), (rad * 2), (rad * 2))
            c = Art.alpha(rg.c, _j.to_int((rg.c.get_alpha() * (1 - f))))
            rg.g.set_color(c)
            if rg.filled:
                rg.g.set_fill_color(c)
            rg.g.set_visible(True)
        stages_alive = False
        for i in range(len(self.stages)):
            if self.stage_done[i]:
                continue
            if self.t < self.stage_delay[i]:
                stages_alive = True
                continue
            s = self.stages[i]
            s.set_visible(True)
            if not s.step(dt):
                _j_set(self.stage_done, i, True)
                s.set_visible(False)
            else:
                stages_alive = True
        if (self.t >= self.duration) and (not stages_alive):
            self.done = True
            self.set_visible(False)
            return False
        return True
    def update(self, t):
        """Hook for bespoke per-frame animation; default does nothing."""
        pass


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.sprites.art import Art  # noqa: E402

Effect.CALM_FLASH = 0.25
