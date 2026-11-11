"""Lindefense PalantirDefeatEffect (ported from src/lindefense/ui/sprites/PalantirDefeatEffect.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.effect import Effect


class PalantirDefeatEffect(Effect):
    """Palantir's defeat sequence, the most dramatic in the game (about 4.5 s):
<ol>
  the eye flickers and its scanning beams spin out of control while a
      chain of explosions walks across the hull,
  the eye flares white and shatters into cyan shards,
  three huge shockwave rings (white, cyan, violet) roll out,
  the hull breaks into dark debris that rains down through smoke,
  sparkles linger as the smoke clears.
</ol>"""
    def __init__(self, e):
        self.eye = None
        self.r = 0.0
        Effect.__init__(self, e.get_position().x, e.get_position().y, 4.5)
        self.beams = ([None] * 2)
        self.r = _j.dmax(10, e.get_radius())
        seed = e.get_id()
        for i in range(2):
            self.beams[i] = Art.poly([0, 0, (2.6 * self.r), ((-0.3) * self.r), (2.8 * self.r), 0, (2.6 * self.r), (0.3 * self.r)])
            self.beams[i].set_filled(True)
            self.beams[i].set_fill_color(Art.alpha(Art.PALANTIR_EYE0, 70))
            self.beams[i].set_color(Art.alpha(Art.PALANTIR_EYE0, 120))
            self.beams[i].rotate((i * 180))
            self.add(self.beams[i])
        self.eye = Art.oval_at(0, 0, (0.62 * self.r), (0.62 * self.r))
        self.eye.set_filled(True)
        self.eye.set_fill_color(Art.PALANTIR_EYE0)
        self.eye.set_color(Art.OUTLINE)
        self.eye.set_line_width(Thick.BOSS)
        self.add(self.eye)
        at = [[(-0.7), (-0.2)], [0.5, 0.3], [(-0.3), 0.35], [0.8, (-0.25)], [(-0.9), 0.1], [0.2, (-0.4)]]
        for i in range(len(at)):
            s = Effect((at[i][0] * self.r), (at[i][1] * self.r), 0.7)
            s.ring(0, 0, (self.r * 0.08), (self.r * 0.45), Art.alpha(Color.WHITE, 230), 0, 0.15, True)
            s.ring(0, 0, (self.r * 0.1), (self.r * 0.7), Art.alpha(Color(255, 170, 60), 230), 0.02, 0.35, False)
            s.shards(6, 0, 0, (self.r * 0.1), (self.r * 2.2), (self.r * 1.5), Color(255, 190, 70), 0, 0, 0.4, (seed + (i * 31)))
            s.shards(4, 0, 0, (self.r * 0.18), (self.r * 1.8), ((-self.r) * 0.6), Color(90, 90, 100, 170), 2, 0.1, 0.6, (seed + (i * 17)))
            self.stage(s, (0.18 * i))
        shatter = Effect(0, 0, 1.2)
        shatter.ring(0, 0, (self.r * 0.3), (self.r * 1.1), Art.alpha(Color.WHITE, 250), 0, 0.3, True)
        shatter.shards(14, 0, 0, (self.r * 0.22), (self.r * 3.5), (self.r * 3), Art.PALANTIR_EYE0, 0, 0.05, 0.9, (seed + 3))
        shatter.shards(8, 0, 0, (self.r * 0.16), (self.r * 2.5), (self.r * 3), Color.WHITE, 0, 0.08, 0.6, (seed + 4))
        self.stage(shatter, 1.35)
        waves_ = Effect(0, 0, 1.4)
        waves_.ring(0, 0, (self.r * 0.2), (self.r * 1.8), Art.alpha(Color.WHITE, 240), 0, 0.3, True)
        waves_.ring(0, 0, (self.r * 0.4), (self.r * 4.2), Art.alpha(Color.WHITE, 230), 0, 0.8, False)
        waves_.ring(0, 0, (self.r * 0.4), (self.r * 3.6), Art.alpha(Art.PALANTIR_EYE0, 230), 0.12, 0.8, False)
        waves_.ring(0, 0, (self.r * 0.4), (self.r * 3.0), Art.alpha(Art.PALANTIR_EYE1, 230), 0.24, 0.8, False)
        self.stage(waves_, 1.5)
        debris = Effect(0, 0, 2.0)
        debris.shards(22, 0, 0, (self.r * 0.3), (self.r * 3.0), (self.r * 3.5), Art.shade(Art.PALANTIR, 0.2), 1, 0, 1.3, (seed + 5))
        debris.shards(12, 0, 0, (self.r * 0.2), (self.r * 2.6), (self.r * 3.5), Color(70, 74, 92), 0, 0.03, 1.1, (seed + 6))
        debris.shards(8, 0, 0, (self.r * 0.25), (self.r * 2.2), (self.r * 2.5), Art.PALANTIR_EYE2, 0, 0.05, 0.9, (seed + 7))
        debris.shards(10, 0, 0, (self.r * 0.55), (self.r * 1.0), ((-self.r) * 1.0), Color(80, 80, 92, 150), 2, 0.1, 1.6, (seed + 8))
        self.stage(debris, 1.6)
        sparkle = Effect(0, 0, 2.0)
        for i in range(10):
            sp = Art.oval_at(0, 0, (self.r * 0.08), (self.r * 0.08))
            sp.set_line_width(0)
            a = ((Effect.rnd((seed + (i * 3))) * math.pi) * 2)
            d = (self.r * (0.4 + (1.4 * Effect.rnd((seed + (i * 5))))))
            sparkle.piece(sp, (math.cos(a) * d), (math.sin(a) * d), 0, ((-self.r) * 0.3), 0, Art.alpha(Color.WHITE, 240), (0.15 * i), 0.5, 0, True)
        self.stage(sparkle, 2.4)
    def update(self, t):
        if t < 1.4:
            spin = (140 + (500 * t))
            for b in self.beams:
                b.rotate((spin / 60.0))
            a = _j.to_int((70 * (1 - (t / 1.4))))
            for b in self.beams:
                b.set_fill_color(Art.alpha(Art.PALANTIR_EYE0, a))
                b.set_color(Art.alpha(Art.PALANTIR_EYE0, (a + 40)))
            on = (display_settings.reduced_motion() or (_j.imod(_j.to_int((t * (8 + (t * 20)))), 3) != 0))   # no strobe with reduced motion
            c = Art.mix(Art.PALANTIR_EYE0, Color.WHITE, _j.dmin(1, (t / 1.4)))
            self.eye.set_fill_color((c if on else Art.shade(c, 0.6)))
            s = (self.r * (0.62 + ((0.3 * t) / 1.4)))
            self.eye.set_bounds(((-s) / 2), ((-s) / 2), s, s)
        else:
            for b in self.beams:
                if b.is_visible():
                    b.set_visible(False)
            if self.eye.is_visible():
                self.eye.set_visible(False)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.sprites.art import Art  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402
