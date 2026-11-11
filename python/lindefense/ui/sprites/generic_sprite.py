"""Lindefense GenericSprite (ported from src/lindefense/ui/sprites/GenericSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class GenericSprite(EnemySprite):
    """Fallback model for any lindefense.enemy.EnemType constant that has no
dedicated sprite yet: a glossy hexagon in the type's signature colour with
the first letter of its display name, so a newly added enemy still renders
sensibly instead of crashing the renderer."""
    def __init__(self, e):
        self.cracks = None
        EnemySprite.__init__(self, e)
        c = Art.color_of(e.get_type())
        self.body_poly(c, GenericSprite.hexagon((self.r * 0.95)))
        self.gloss(0, 0, (1.9 * self.r), (1.9 * self.r))
        l = GLabel(e.get_type().display_name[0:1])
        l.set_font(Ui.display(Font.BOLD, max(8, _j.to_int(_j.jround((self.r * 0.9))))))
        self.fixed_stroke(l, Color.WHITE)
        l.set_location(((-l.get_width()) / 2), (l.get_ascent() * 0.38))
        self.cracks = self.make_cracks(3, self.r)
        self.finish_overlays()
    @staticmethod
    def hexagon(R):
        xy = ([0.0] * 12)
        for i in range(6):
            xy[(2 * i)] = (R * math.cos(((i * math.pi) / 3)))
            xy[((2 * i) + 1)] = (R * math.sin(((i * math.pi) / 3)))
        return xy
    def update_body(self, e, t):
        EnemySprite.show_cracks(self.cracks, self.dmg)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
