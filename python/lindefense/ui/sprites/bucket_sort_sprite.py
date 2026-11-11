"""Lindefense BucketSortSprite (ported from src/lindefense/ui/sprites/BucketSortSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class BucketSortSprite(EnemySprite):
    """Bucket Sort: a chunky tin bucket with a wooden rim, a swinging handle and a
pair of eyes on its front. Enemies it has absorbed show through as coloured
dots bobbing in a liquid whose level rises with
Enemy#getStoredEnemies(). Dents and a leaking drip appear as HP drops."""
    def __init__(self, e):
        self.liquid = None
        self.handle = None
        self.drip = None
        self.eye = None
        self.cracks = None
        self.top = 0.0
        self.bottom = 0.0
        EnemySprite.__init__(self, e)
        self.dots = ([None] * 6)
        self.shown_count = (-1)
        self.top = ((-0.75) * self.r)
        self.bottom = (1.0 * self.r)
        half_top = (1.0 * self.r)
        half_bot = (0.74 * self.r)
        self.body_poly(Art.BUCKET, [(-half_top), self.top, half_top, self.top, half_bot, self.bottom, (-half_bot), self.bottom])
        self.liquid = self.fixed(Art.rect(((-half_bot) * 0.95), (self.bottom - (0.1 * self.r)), (half_bot * 1.9), (0.1 * self.r)), Art.alpha(BucketSortSprite.WATER, 130), Art.alpha(BucketSortSprite.WATER, 0))
        self.liquid.set_line_width(0)
        for i in range(6):
            self.dots[i] = Art.oval_at(0, 0, (0.32 * self.r), (0.32 * self.r))
            self.dots[i].set_filled(True)
            self.dots[i].set_line_width(Thick.DETAIL)
            self.dots[i].set_visible(False)
            self.add(self.dots[i])
        self.thin(self.part(Art.rect(((-0.9) * self.r), (0.3 * self.r), (1.8 * self.r), (0.16 * self.r)), Art.shade(Art.BUCKET, 0.4)))
        self.part(Art.rect(((-half_top) - (0.1 * self.r)), (self.top - (0.2 * self.r)), ((2 * half_top) + (0.2 * self.r)), (0.34 * self.r)), Art.BUCKET_WOOD)
        self.handle = self.line_width(self.stroke(Art.arc(((-0.85) * self.r), ((-1.6) * self.r), (1.7 * self.r), (1.5 * self.r), 0, 180), Art.BUCKET_WOOD), 2.6)
        self.drip = self.fixed(Art.oval_at((0.5 * self.r), (self.bottom + (0.25 * self.r)), (0.2 * self.r), (0.32 * self.r)), BucketSortSprite.WATER, Art.OUTLINE)
        self.drip.set_line_width(Thick.DETAIL)
        self.drip.set_visible(False)
        self.gloss(0, (0.1 * self.r), (1.9 * self.r), (1.7 * self.r))
        self.eye = self.eyes(0, ((-0.2) * self.r), (0.6 * self.r), (0.36 * self.r))
        self.cracks = self.make_cracks(3, self.r)
        self.finish_overlays()
    def update_body(self, e, t):
        stored = e.get_stored_enemies()
        n = min(6, len(stored))
        level = ((0.1 + ((0.6 * n) / 6.0)) * (self.bottom - self.top))
        self.liquid.set_bounds(((-0.7) * self.r), (self.bottom - level), (1.4 * self.r), level)
        if n != self.shown_count:
            self.shown_count = n
            for i in range(6):
                self.dots[i].set_visible((i < n))
                if i < n:
                    c = Art.color_of(stored[i].get_type())
                    self.dots[i].set_fill_color(c)
                    self.dots[i].set_color(Art.OUTLINE)
        for i in range(n):
            x = (((-0.42) + (0.42 * _j.imod(i, 3))) * self.r)
            y = ((self.bottom - (level * (0.3 + (0.45 * _j.idiv(i, 3))))) + ((math.sin(((t * 3) + i)) * self.r) * 0.06))
            Art.center(self.dots[i], x, y)
        self.handle.set_location((((-0.85) * self.r) + ((math.sin(((t * 3) + e.get_id())) * self.r) * 0.08)), ((-1.6) * self.r))
        for i in range(2):
            Art.center(self.eye[((2 * i) + 1)], (((self.eye[(2 * i)].get_x() + (self.eye[(2 * i)].get_width() / 2)) + ((self.dir_x * 0.05) * self.r)) + (0.02 * self.r)), (((self.eye[(2 * i)].get_y() + (self.eye[(2 * i)].get_height() / 2)) + ((self.dir_y * 0.05) * self.r)) + (0.03 * self.r)))
        EnemySprite.show_cracks(self.cracks, self.dmg)
        leak = (self.dmg > 0.45)
        self.drip.set_visible(leak)
        if leak:
            Art.center(self.drip, (0.5 * self.r), ((self.bottom + (0.1 * self.r)) + ((_j.fmod((t * 1.5), 1.0) * self.r) * 0.6)))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402

BucketSortSprite.WATER = Color(70, 150, 240)
