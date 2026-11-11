"""Lindefense MiniMaxArt (ported from src/lindefense/ui/sprites/towers/MiniMaxArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class MiniMaxArt(TowerArt):
    """MiniMax, the Clone Bouncer: a big glossy cherry-red ball-bot with a goofy
grin, a pinball launcher, and little clone balls that multiply with each
tier (sitting, then orbiting). The Hydra superclass sprouts five clone heads
on necks around a gold-collared core."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        br = (self.r * (0.64 + (0.03 * self.tier)))
        cy = ((-self.r) * 0.1)
        if self.tier >= 4:
            for i in range(5):
                a = ((math.pi + ((i - 2) * 0.62)) + (math.pi / 2))
                hx = ((math.cos(a) * self.r) * 1.25)
                hy = (cy + ((math.sin(a) * self.r) * 1.0))
                self.poly(Art.bar(((math.cos(a) * br) * 0.6), (cy + ((math.sin(a) * br) * 0.6)), hx, hy, (self.r * 0.1)), self.pri_dark)
                self.body(hx, hy, (self.r * 0.24), self.pri)
                self.eye(hx, (hy - (self.r * 0.04)), (self.r * 0.08), Art.INK)
        else:
            clones = (1 + self.tier)
            for i in range(clones):
                a = ((math.pi * 0.75) + (i * ((math.pi * 1.5) / max(1, ((clones - 1) + (1 if (clones == 1) else 0))))))
                if self.tier >= 2:
                    self.orbiting_orb(0, cy, (self.r * 1.15), (self.r * 0.17), a, 1.8, self.pri)
                else:
                    cx = ((math.cos(a) * self.r) * 1.05)
                    cyy = (cy + ((math.sin(a) * self.r) * 0.75))
                    self.body(cx, cyy, (self.r * 0.18), self.pri)
        tu = self.turret()
        len_ = (self.r * (0.8 + (0.18 * self.tier)))
        hw = (self.r * 0.17)
        tu.poly(Art.rect(((-self.r) * 0.1), (-hw), (len_ + (self.r * 0.1)), (2 * hw)), (Art.GOLD if (self.tier >= 4) else self.sec))
        tu.poly(Art.rect((len_ - (self.r * 0.1)), ((-hw) * 1.3), (self.r * 0.2), (hw * 2.6)), self.pri_dark)
        for i in range(2 + min(self.tier, 2)):
            tu.plain(Art.circle(((self.r * 0.15) + ((i * self.r) * 0.22)), 0, (hw * 0.45), 8), Art.alpha(self.pri, 200))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.3)), 0, (self.r * 0.3), (self.r * 0.12), 5, 0), Art.alpha(Color.WHITE, 230)))
        self.body(0, cy, br, self.pri)
        if self.tier >= 4:
            self.ellipse(0, (cy + (br * 0.75)), (br * 0.8), (self.r * 0.16), Art.GOLD)
        self.eye(((-br) * 0.3), (cy - (br * 0.15)), (self.r * 0.17), Art.INK)
        self.eye((br * 0.3), (cy - (br * 0.15)), (self.r * 0.17), Art.INK)
        self.plain([((-br) * 0.4), (cy + (br * 0.3)), (br * 0.4), (cy + (br * 0.3)), (br * 0.2), (cy + (br * 0.55)), ((-br) * 0.2), (cy + (br * 0.55))], Art.INK)
        self.plain(Art.rect(((-br) * 0.15), (cy + (br * 0.32)), (br * 0.3), (br * 0.1)), Color.WHITE)
        if self.tier >= 3:
            self.poly(Art.rect(((-br) * 1.05), (cy - (self.r * 0.4)), (self.r * 0.22), (self.r * 0.5)), self.sec)
            self.poly(Art.rect(((br * 1.05) - (self.r * 0.22)), (cy - (self.r * 0.4)), (self.r * 0.22), (self.r * 0.5)), self.sec)
        if self.tier >= 4:
            self.crown(0, (cy - (br * 1.05)), (self.r * 0.24), 5)
        self.sparkle(((-br) * 0.6), (cy - (br * 0.6)), (self.r * 0.1))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

MiniMaxArt.serial_version_uid = 1
