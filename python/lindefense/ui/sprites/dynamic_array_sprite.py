"""Lindefense DynamicArraySprite (ported from src/lindefense/ui/sprites/DynamicArraySprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class DynamicArraySprite(EnemySprite):
    """Dynamic Array: a container with three filled cells and an open right end
where a translucent "capacity" cell keeps growing and shrinking, with a plus
sign inside it. A thin capacity bracket spans the whole thing."""
    def __init__(self, e):
        self.growth = None
        self.plus_h = None
        self.plus_v = None
        self.bracket = None
        self.cracks = None
        self.w = 0.0
        self.h = 0.0
        self.left = 0.0
        EnemySprite.__init__(self, e)
        self.cells = ([None] * 3)
        self.shown_cells = (-1)
        self.w = (2.1 * self.r)
        self.h = (1.35 * self.r)
        self.left = (((-self.w) / 2) - (0.3 * self.r))
        self.body_rect(self.left, ((-self.h) / 2), self.w, self.h, Art.DYNAMIC_ARRAY)
        self.thin(self.part(Art.rect(self.left, ((-self.h) / 2), (self.w * 0.12), self.h), Art.shade(Art.DYNAMIC_ARRAY, 0.5)))
        cw = ((self.w * 0.88) / 3)
        for i in range(3):
            cx = ((self.left + (self.w * 0.12)) + (cw * (i + 0.5)))
            self.cells[i] = self.thin(self.part(Art.rect((cx - (cw * 0.32)), ((-self.h) * 0.28), (cw * 0.64), (self.h * 0.56)), Art.tint(Art.DYNAMIC_ARRAY, 0.55)))
        self.growth = self.thin(self.fixed(Art.rect((self.left + self.w), ((-self.h) / 2), (0.6 * self.r), self.h), Art.alpha(Art.DYNAMIC_ARRAY, 90), Art.alpha(Art.outline(Art.DYNAMIC_ARRAY), 220)))
        self.plus_h = self.thin(self.fixed_stroke(Art.line(0, 0, 1, 0), Art.shade(Art.DYNAMIC_ARRAY, 0.5)))
        self.plus_v = self.thin(self.fixed_stroke(Art.line(0, 0, 0, 1), Art.shade(Art.DYNAMIC_ARRAY, 0.5)))
        self.bracket = self.thin(self.fixed_stroke(Art.line(self.left, (((-self.h) / 2) - (0.28 * self.r)), (self.left + self.w), (((-self.h) / 2) - (0.28 * self.r))), Art.shade(Art.DYNAMIC_ARRAY, 0.4)))
        self.gloss((self.left + (self.w / 2)), ((-self.h) * 0.12), self.w, (self.h * 0.9))
        self.cracks = self.make_cracks(3, self.r)
        self.finish_overlays()
    def update_body(self, e, t):
        gw = (self.r * (0.45 + (0.4 * (0.5 + (0.5 * math.sin(((t * 2.2) + e.get_id())))))))
        gx = (self.left + self.w)
        self.growth.set_bounds(gx, ((-self.h) / 2), gw, self.h)
        cx = (gx + (gw / 2))
        s = _j.dmin((gw * 0.3), (self.r * 0.25))
        self.plus_h.set_start_point((cx - s), 0)
        self.plus_h.set_end_point((cx + s), 0)
        self.plus_v.set_start_point(cx, (-s))
        self.plus_v.set_end_point(cx, s)
        self.bracket.set_end_point((gx + gw), (((-self.h) / 2) - (0.28 * self.r)))
        show = max(0, _j.to_int(float(math.ceil(((self.hp_frac * 3) - 1e-6)))))
        if show != self.shown_cells:
            self.shown_cells = show
            for i in range(3):
                self.cells[i].set_visible((i < show))
        EnemySprite.show_cracks(self.cracks, self.dmg)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
