"""Lindefense GeminiArt (ported from src/lindefense/ui/sprites/towers/GeminiArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class GeminiArt(TowerArt):
    """Gemini, the Prism Chain: twin dome-headed bots, one blue and one violet,
flanking a tall crystal prism that aims at the chain's first link. Flash
tiers add arc antennae and orbiting shards; Argon crowns both twins; the
Ultra superclass raises a huge iridescent star crystal inside a gold ring."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        hx = (self.r * 0.5)
        hy = (self.r * 0.05)
        hr = (self.r * (0.36 + (0.02 * self.tier)))
        self.box((-hx), (hy - (self.r * 0.15)), (2 * hx), (self.r * 0.3), Art.METAL)
        self.body((-hx), hy, hr, self.pri)
        self.body(hx, hy, hr, self.sec)
        self.eye(((-hx) + (hr * 0.1)), (hy - (hr * 0.05)), (hr * 0.42), self.sec)
        self.eye((hx - (hr * 0.1)), (hy - (hr * 0.05)), (hr * 0.42), self.pri)
        if self.tier >= 1:
            self.antenna(((-hx) - (hr * 0.5)), (hy - (hr * 0.6)), (hy - (hr * 1.5)), self.sec)
            self.antenna((hx + (hr * 0.5)), (hy - (hr * 0.6)), (hy - (hr * 1.5)), self.pri)
        if self.tier >= 3:
            self.crown((-hx), (hy - (hr * 1.05)), (self.r * 0.2), 3)
            self.crown(hx, (hy - (hr * 1.05)), (self.r * 0.2), 3)
        shards = (6 if (self.tier >= 4) else (4 if (self.tier >= 3) else (2 if (self.tier >= 2) else 0)))
        for i in range(shards):
            self.orbiting_orb(0, ((-self.r) * 0.1), (self.r * (1.05 + (0.15 * (1 if (self.tier >= 4) else 0)))), (self.r * 0.13), (((i * 2) * math.pi) / shards), 1.4, (self.pri if (_j.imod(i, 2) == 0) else self.sec))
        tu = self.turret()
        len_ = (self.r * (0.9 + (0.2 * self.tier)))
        hw = (self.r * (0.22 + (0.03 * self.tier)))
        if self.tier >= 4:
            tu.ring_spinner((self.r * 0.95), (self.r * 0.78), 10, (self.r * 0.1), 0, Art.GOLD)
            tu.set_spin_speed(60)
            tu.poly(Art.star(0, 0, (len_ * 0.75), (hw * 1.1), 6, 90), Art.mix(self.pri, self.sec, 0.5))
            tu.poly([((-self.r) * 0.35), 0, 0, (-hw), len_, 0, 0, hw], self.pri)
            tu.poly([0, ((-hw) * 0.5), (len_ * 0.8), 0, 0, (hw * 0.5)], Art.shade(self.sec, 1.25))
            tu.gloss((len_ * 0.25), ((-hw) * 0.3), (len_ * 0.2), (hw * 0.25))
        else:
            tu.poly([((-self.r) * 0.35), 0, 0, (-hw), len_, 0, 0, hw], self.pri)
            tu.poly([((-self.r) * 0.35), 0, 0, hw, len_, 0], self.sec)
            tu.gloss((len_ * 0.2), ((-hw) * 0.35), (len_ * 0.2), (hw * 0.25))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.2)), 0, (self.r * 0.3), (self.r * 0.12), 4, 0), Art.alpha(Color.WHITE, 230)))
        self.disc(0, 0, (self.r * 0.18), (Art.GOLD if (self.tier >= 4) else Art.METAL_LIGHT))
        self.sparkle(((-hx) - (hr * 0.3)), (hy - (hr * 0.6)), (self.r * 0.09))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

GeminiArt.serial_version_uid = 1
