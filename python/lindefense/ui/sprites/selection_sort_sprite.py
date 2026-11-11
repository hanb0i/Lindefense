"""Lindefense SelectionSortSprite (ported from src/lindefense/ui/sprites/SelectionSortSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class SelectionSortSprite(EnemySprite):
    """Selection Sort: a chunky slate hexagon with a single big amber "eye" at its
centre, wrapped in a targeting reticle whose sweep arm keeps scanning for
the front of the group. The eye darts about; the reticle ring breaks into a
shorter arc as HP drops."""
    def __init__(self, e):
        self.ring = None
        self.sweep = None
        self.iris = None
        self.pupil = None
        self.glint = None
        EnemySprite.__init__(self, e)
        self.ticks = ([None] * 4)
        self.shown_layers = (-1)
        R = (1.1 * self.r)
        self.sweep = self.fixed(Art.arc((-R), (-R), (2 * R), (2 * R), 0, 55), Art.alpha(Art.SELECTION, 80), Art.alpha(Art.SELECTION, 0))
        self.sweep.set_line_width(0)
        hex = ([0.0] * 12)
        for i in range(6):
            hex[(2 * i)] = ((0.82 * self.r) * math.cos(((i * math.pi) / 3)))
            hex[((2 * i) + 1)] = ((0.82 * self.r) * math.sin(((i * math.pi) / 3)))
        self.body_poly(Art.SELECTION_BODY, hex)
        self.gloss(0, 0, (1.6 * self.r), (1.4 * self.r))
        self.thin(self.part(Art.oval_at(0, 0, (0.9 * self.r), (0.9 * self.r)), Color.WHITE))
        self.iris = self.thin(self.part(Art.oval_at(0, 0, (0.6 * self.r), (0.6 * self.r)), Art.SELECTION))
        self.pupil = self.fixed(Art.oval_at(0, 0, (0.28 * self.r), (0.28 * self.r)), Art.OUTLINE, Art.OUTLINE)
        self.pupil.set_line_width(0)
        self.glint = self.highlight(((-0.1) * self.r), ((-0.12) * self.r), (0.16 * self.r), (0.12 * self.r))
        self.ring = self.line_width(self.stroke(Art.arc((-R), (-R), (2 * R), (2 * R), 90, 360), Art.SELECTION), 2.2)
        for i in range(4):
            a = math.radians((i * 90))
            self.ticks[i] = self.line_width(self.stroke(Art.line(((math.cos(a) * R) * 0.85), ((math.sin(a) * R) * 0.85), ((math.cos(a) * R) * 1.3), ((math.sin(a) * R) * 1.3)), Art.SELECTION), 2.2)
        self.finish_overlays()
    def update_body(self, e, t):
        self.sweep.set_start_angle(_j.fmod((((-t) * 160) + (e.get_id() * 40)), 360))
        pulse = (1.0 + (0.06 * math.sin((t * 5))))
        R = ((1.1 * self.r) * pulse)
        self.ring.set_frame_rectangle((-R), (-R), (2 * R), (2 * R))
        layers = EnemySprite.layers_left(e, 4)
        if layers != self.shown_layers:
            self.shown_layers = layers
            self.ring.set_sweep_angle((90.0 * max(1, layers)))
            for i in range(4):
                self.ticks[i].set_visible((i < layers))
        lx = (((math.cos((t * 2.3)) * self.r) * 0.1) + ((self.dir_x * 0.08) * self.r))
        ly = (((math.sin((t * 3.1)) * self.r) * 0.1) + ((self.dir_y * 0.08) * self.r))
        Art.center(self.iris, lx, ly)
        Art.center(self.pupil, (lx * 1.3), (ly * 1.3))
        Art.center(self.glint, (lx - (0.1 * self.r)), (ly - (0.12 * self.r)))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
