"""Lindefense TimSortSprite (ported from src/lindefense/ui/sprites/TimSortSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class TimSortSprite(EnemySprite):
    """TimSort: the hybrid. A chunky hexagon split down the seam like Merge Sort,
but its left half is purple with sorted merge bars and its right half is
orange with Insertion Sort slabs (one of which keeps lifting and sliding
into place). One eye per half, and two swept speed fins trail behind it.
Elements are lost two per layer."""
    def __init__(self, e):
        self.left = None
        self.right = None
        self.shine_l = None
        self.shine_r = None
        self.eye = None
        self.cracks = None
        EnemySprite.__init__(self, e)
        self.bars = ([None] * 2)
        self.slabs = ([None] * 3)
        self.fins = ([None] * 2)
        self.shown = (-1)
        R = (self.r * 1.0)
        h = (R * 0.866)
        for i in range(2):
            side = ((-1) if (i == 0) else 1)
            self.fins[i] = self.rotating(Art.poly([((-0.4) * self.r), ((side * 0.35) * self.r), ((-1.5) * self.r), ((side * 0.95) * self.r), ((-0.75) * self.r), ((side * 0.25) * self.r)]))
            self.thin(self.part(self.fins[i], Art.shade((Art.TIMSORT if (i == 0) else Art.INSERTION), 0.3)))
        self.left = self.body_poly_parts(Art.TIMSORT, [0, (-h), ((-R) * 0.5), (-h), (-R), 0, ((-R) * 0.5), h, 0, h])
        self.right = self.body_poly_parts(Art.INSERTION, [0, (-h), (R * 0.5), (-h), R, 0, (R * 0.5), h, 0, h])
        for i in range(2):
            self.bars[i] = self.thin(self.part(Art.rect(0, 0, (self.r * 0.22), (self.r * (0.4 + (0.3 * i)))), Art.tint(Art.TIMSORT, (0.45 + (0.2 * i)))))
        for i in range(3):
            self.slabs[i] = self.thin(self.part(Art.rect(0, 0, (self.r * 0.2), (self.r * (0.35 + (0.2 * i)))), Art.tint(Art.INSERTION, (0.3 + (0.2 * i)))))
        for i in range(2):
            self.thin(self.fixed_stroke(Art.line(0, (((-0.7) * R) + ((i * 0.8) * R)), 0, ((((-0.7) * R) + ((i * 0.8) * R)) + (0.5 * R))), Art.tint(Art.TIMSORT, 0.6)))
        self.shine_l = self.highlight(((-0.5) * self.r), ((-0.5) * self.r), (0.42 * self.r), (0.26 * self.r))
        self.shine_r = self.highlight((0.3 * self.r), ((-0.55) * self.r), (0.22 * self.r), (0.14 * self.r))
        self.eye = self.eyes(0, ((-0.25) * self.r), (0.7 * self.r), (0.34 * self.r))
        self.cracks = self.make_cracks(3, self.r)
        self.finish_overlays()
    def update_body(self, e, t):
        self.set_facing(self.facing_deg)
        gap = (self.r * ((0.05 + (0.04 * math.sin(((t * 3.5) + e.get_id())))) + (0.3 * self.dmg)))
        self.left[0].set_location((-gap), 0)
        self.left[1].set_location((-gap), 0)
        self.right[0].set_location(gap, 0)
        self.right[1].set_location(gap, 0)
        Art.center(self.shine_l, ((-gap) - (0.5 * self.r)), ((-0.5) * self.r))
        Art.center(self.shine_r, (gap + (0.3 * self.r)), ((-0.55) * self.r))
        for i in range(2):
            self.bars[i].set_location((((-gap) - (0.72 * self.r)) + ((i * 0.3) * self.r)), ((0.48 * self.r) - self.bars[i].get_height()))
        cyc = _j.fmod(((t * 0.9) + (e.get_id() * 0.3)), 1.0)
        lift = ((cyc / 0.3) if (cyc < 0.3) else (1 if (cyc < 0.6) else _j.dmax(0, (1 - ((cyc - 0.6) / 0.2)))))
        slide = (0 if (cyc < 0.3) else (((cyc - 0.3) / 0.3) if (cyc < 0.6) else 1))
        for i in range(3):
            x = ((gap + (0.12 * self.r)) + ((i * 0.26) * self.r))
            y = ((0.48 * self.r) - self.slabs[i].get_height())
            if i == 2:
                x = ((gap + (0.12 * self.r)) + ((0.26 * self.r) * (2 - slide)))
                y -= ((lift * self.r) * 0.5)
            self.slabs[i].set_location(x, y)
        for i in range(2):
            ex = (((-gap) - (0.35 * self.r)) if (i == 0) else (gap + (0.35 * self.r)))
            ey = ((-0.25) * self.r)
            Art.center(self.eye[(2 * i)], ex, ey)
            Art.center(self.eye[((2 * i) + 1)], ((ex + ((self.dir_x * 0.06) * self.r)) + (0.03 * self.r)), ((ey + ((self.dir_y * 0.06) * self.r)) + (0.03 * self.r)))
        show = max(1, _j.to_int(float(math.ceil((EnemySprite.layers_left(e, 10) / 2.0)))))
        if show != self.shown:
            self.shown = show
            self.bars[1].set_visible((show >= 5))
            self.slabs[2].set_visible((show >= 4))
            self.bars[0].set_visible((show >= 3))
            self.slabs[1].set_visible((show >= 2))
        EnemySprite.show_cracks(self.cracks, self.dmg)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
