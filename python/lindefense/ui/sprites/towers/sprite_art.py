"""Lindefense SpriteArt (ported from src/lindefense/ui/sprites/towers/SpriteArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class SpriteArt(TowerArt):
    """The DALL·E Sprite summon: a tiny buttercup paint-blob familiar with sky-blue
wings, one big eye and a paintbrush tail. It has no base plate and bobs in
the air; tier is ignored."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def draws_plate(self):
        return False
    def build(self):
        br = (self.r * 0.7)
        cy = ((-self.r) * 0.2)
        self.poly([((-br) * 0.6), cy, ((-br) * 1.6), (cy - (br * 0.9)), ((-br) * 1.3), (cy + (br * 0.3))], self.sec)
        self.poly([(br * 0.6), cy, (br * 1.6), (cy - (br * 0.9)), (br * 1.3), (cy + (br * 0.3))], self.sec)
        self.poly(Art.bar(0, (cy + (br * 0.6)), 0, (cy + (br * 1.5)), (self.r * 0.08)), Art.rgb(0x8a5a2b))
        self.poly([((-self.r) * 0.14), (cy + (br * 1.45)), (self.r * 0.14), (cy + (br * 1.45)), 0, (cy + (br * 1.95))], Art.rgb(0xff5fa2))
        self.body(0, cy, br, self.pri)
        self.eye(0, (cy - (br * 0.05)), (br * 0.42), self.sec)
        self.plain(Art.circle(((-br) * 0.5), (cy + (br * 0.5)), (self.r * 0.1), 8), Art.rgb(0x7ee0a0))
        self.plain(Art.circle((br * 0.55), (cy + (br * 0.4)), (self.r * 0.08), 8), Art.rgb(0x9b5cff))
        tu = self.turret()
        tu.poly(Art.wedge((self.r * 0.2), (self.r * 0.9), (self.r * 0.1), 0), Art.rgb(0xff5fa2))
        tu.set_flash(tu.plain(Art.star((self.r * 1.05), 0, (self.r * 0.2), (self.r * 0.08), 4, 0), Art.alpha(Color.WHITE, 220)))
        self.sparkle(((-br) * 0.5), (cy - (br * 0.55)), (self.r * 0.1))
    def animate_extra(self, t, dt):
        self.set_location(self.get_x(), ((math.sin((t * 4)) * self.r) * 0.12))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

SpriteArt.serial_version_uid = 1
