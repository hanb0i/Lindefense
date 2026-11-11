"""Lindefense QuickSortSprite (ported from src/lindefense/ui/sprites/QuickSortSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class QuickSortSprite(EnemySprite):
    """Quick Sort: a chunky crimson plate carrying seven bars with a golden pivot
in the middle (it has the eyes and a little marker above it) and a dashed
partition line through it. Shorter bars stand left of the pivot, taller
bars right; the outer bars keep shuffling heights as they are partitioned.
Bars vanish from the outside in as HP drops, leaving the pivot last."""
    def __init__(self, e):
        self.marker = None
        self.eye = None
        self.pivot_shine = None
        self.plate_y = 0.0
        EnemySprite.__init__(self, e)
        self.bars = ([None] * 7)
        self.base_h = ([0.0] * 7)
        self.shown = (-1)
        self.plate_y = (self.r * 0.72)
        self.body_rect(((-1.25) * self.r), self.plate_y, (2.5 * self.r), (0.42 * self.r), Art.shade(Art.QUICK, 0.25))
        bw = (self.r * 0.27)
        for i in range(7):
            k = (i - 3)
            self.base_h[i] = ((self.r * 1.0) if (k == 0) else ((self.r * (0.35 + (0.15 * (3 + k)))) if (k < 0) else (self.r * (1.05 + (0.15 * (k - 1))))))
            x = (((k * bw) * 1.25) - (bw / 2))
            self.bars[i] = self.part(Art.rect(x, (self.plate_y - self.base_h[i]), bw, self.base_h[i]), (Art.QUICK_PIVOT if (k == 0) else (Art.tint(Art.QUICK, 0.3) if (k < 0) else Art.QUICK)))
            if k != 0:
                self.thin(self.bars[i])
        self.thin(self.fixed_stroke(Art.line(0, (self.plate_y + (0.42 * self.r)), 0, (self.plate_y + (0.7 * self.r))), Art.tint(Art.QUICK_PIVOT, 0.4)))
        self.thin(self.fixed_stroke(Art.line(0, (self.plate_y - (1.35 * self.r)), 0, (self.plate_y - (1.1 * self.r))), Art.tint(Art.QUICK_PIVOT, 0.4)))
        self.marker = self.thin(self.fixed(Art.poly([((-0.17) * self.r), (((-1.6) * self.r) + self.plate_y), (0.17 * self.r), (((-1.6) * self.r) + self.plate_y), 0, (((-1.36) * self.r) + self.plate_y)]), Art.QUICK_PIVOT, Art.OUTLINE))
        self.pivot_shine = self.highlight(((-bw) * 0.15), (self.plate_y - (0.85 * self.r)), (bw * 0.45), (0.2 * self.r))
        self.eye = self.eyes(0, (self.plate_y - (0.55 * self.r)), (bw * 0.55), (bw * 0.4))
        self.gloss(((-0.5) * self.r), (self.plate_y + (0.1 * self.r)), (1.4 * self.r), (0.6 * self.r))
        self.finish_overlays()
    def update_body(self, e, t):
        step = _j.to_int(((t + (e.get_id() * 0.3)) * 2))
        for i in range(7):
            if i == 3:
                continue
            side = (0 if (i < 3) else 1)
            j = (_j.imod((step + i), 3) if (side == 0) else (4 + _j.imod((step + i), 3)))
            h = (self.base_h[j] * (0.92 + (0.08 * math.sin(((t * 6) + i)))))
            self.bars[i].set_bounds(self.bars[i].get_x(), (self.plate_y - h), self.bars[i].get_width(), h)
        self.marker.set_location(0, ((math.sin((t * 4)) * self.r) * 0.08))
        for i in range(2):
            Art.center(self.eye[((2 * i) + 1)], (((self.eye[(2 * i)].get_x() + (self.eye[(2 * i)].get_width() / 2)) + ((self.dir_x * 0.04) * self.r)) + (0.02 * self.r)), (((self.eye[(2 * i)].get_y() + (self.eye[(2 * i)].get_height() / 2)) + ((self.dir_y * 0.04) * self.r)) + (0.02 * self.r)))
        show = EnemySprite.layers_left(e, 7)
        if show != self.shown:
            self.shown = show
            order = [0, 6, 1, 5, 2, 4, 3]
            for i in range(7):
                self.bars[order[i]].set_visible((i >= (7 - show)))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
