"""Lindefense StaticArraySprite (ported from src/lindefense/ui/sprites/StaticArraySprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class StaticArraySprite(EnemySprite):
    """Static Array: a rigid, orderly container with three fixed cells and heavy
end-caps (its size never changes). Nothing moves; as HP drops the cells
empty from the right and the casing cracks."""
    def __init__(self, e):
        self.cracks = None
        EnemySprite.__init__(self, e)
        self.cells = ([None] * 3)
        self.shown_cells = (-1)
        w = (2.4 * self.r)
        h = (1.35 * self.r)
        self.body_rect(((-w) / 2), ((-h) / 2), w, h, Art.STATIC_ARRAY)
        self.thin(self.part(Art.rect(((-w) / 2), ((-h) / 2), (w * 0.12), h), Art.shade(Art.STATIC_ARRAY, 0.5)))
        self.thin(self.part(Art.rect(((w / 2) - (w * 0.12)), ((-h) / 2), (w * 0.12), h), Art.shade(Art.STATIC_ARRAY, 0.5)))
        inner = (w * 0.76)
        cw = (inner / 3)
        for i in range(3):
            cx = (((-inner) / 2) + (cw * (i + 0.5)))
            self.cells[i] = self.thin(self.part(Art.rect((cx - (cw * 0.32)), ((-h) * 0.28), (cw * 0.64), (h * 0.56)), Art.tint(Art.STATIC_ARRAY, 0.55)))
        self.thin(self.stroke(Art.line(((-inner) / 6), (((-h) / 2) + 2), ((-inner) / 6), ((h / 2) - 2)), Art.shade(Art.STATIC_ARRAY, 0.45)))
        self.thin(self.stroke(Art.line((inner / 6), (((-h) / 2) + 2), (inner / 6), ((h / 2) - 2)), Art.shade(Art.STATIC_ARRAY, 0.45)))
        self.gloss(0, ((-h) * 0.12), w, (h * 0.9))
        self.cracks = self.make_cracks(2, self.r)
        self.finish_overlays()
    def update_body(self, e, t):
        show = max(0, _j.to_int(float(math.ceil(((self.hp_frac * 3) - 1e-6)))))
        if show != self.shown_cells:
            self.shown_cells = show
            for i in range(3):
                self.cells[i].set_visible((i < show))
        EnemySprite.show_cracks(self.cracks, self.dmg)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
