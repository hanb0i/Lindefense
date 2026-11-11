"""Lindefense GptArt (ported from src/lindefense/ui/sprites/towers/GptArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class GptArt(TowerArt):
    """GPT, the Adaptive Generalist: a tidy white box-bot with a green visor band
and a hex-nut emblem that fires token bolts from a stubby green cannon.
Terra adds a context dish, Luna adaptive module chips, Sol twin cannons, and
the Cosmos superclass becomes a deep-green starfield sphere wearing a white
orbital halo and gold-tipped twin cannons."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        w = (self.r * (1.3 + (0.05 * self.tier)))
        h = (self.r * 1.15)
        if self.tier >= 4:
            self.body(0, ((-self.r) * 0.1), (self.r * 0.8), Art.shade(self.pri, 0.45))
            for i in range(7):
                a = ((i * 0.9) + 0.3)
                d = (self.r * (0.25 + (0.07 * _j.imod(i, 3))))
                self.plain(Art.star((math.cos(a) * d), (((-self.r) * 0.1) + (math.sin(a) * d)), (self.r * 0.07), (self.r * 0.025), 4, 0), Color.WHITE)
            self.visor(0, ((-self.r) * 0.3), (self.r * 1.0), (self.r * 0.22), self.pri)
            self.spinning_ring(0, ((-self.r) * 0.1), (self.r * 1.08), (self.r * 0.96), 16, Color.WHITE, 30)
        else:
            b = self.body_box(((-w) / 2), (((-h) / 2) - (self.r * 0.1)), w, h, Color.WHITE)
            b.set_fill_color(Art.shade(self.sec, 0.98))
            self.visor(0, ((-self.r) * 0.3), (w * 0.8), (self.r * 0.22), self.pri)
            self.poly(Art.regular(0, (self.r * 0.22), (self.r * 0.2), 6, 30), self.pri)
            self.plain(Art.regular(0, (self.r * 0.22), (self.r * 0.09), 6, 30), Color.WHITE)
        if self.tier >= 1:
            self.antenna(((-w) * 0.42), (((-h) * 0.5) - (self.r * 0.1)), (((-h) * 0.5) - (self.r * 0.55)), self.sec)
            self.poly([(((-w) * 0.42) - (self.r * 0.22)), (((-h) * 0.5) - (self.r * 0.55)), (((-w) * 0.42) + (self.r * 0.22)), (((-h) * 0.5) - (self.r * 0.55)), ((-w) * 0.42), (((-h) * 0.5) - (self.r * 0.3))], self.pri_light)
        if self.tier >= 2:
            chips = [self.pri, Art.rgb(0x2fd4b3), Art.rgb(0xffcf5a)]
            for i in range(3):
                self.box(((w * 0.5) - (self.r * 0.02)), (((-self.r) * 0.45) + ((i * self.r) * 0.3)), (self.r * 0.22), (self.r * 0.2), chips[i])
        tu = self.turret()
        len_ = (self.r * (0.85 + (0.15 * self.tier)))
        hw = (self.r * 0.14)
        barrel = (self.pri_dark if (self.tier >= 4) else self.pri)
        if self.tier >= 3:
            tu.poly(Art.rect(((-self.r) * 0.2), ((-hw) * 2.4), (len_ + (self.r * 0.2)), (hw * 1.6)), barrel)
            tu.poly(Art.rect(((-self.r) * 0.2), (hw * 0.8), (len_ + (self.r * 0.2)), (hw * 1.6)), barrel)
            tu.poly(Art.rect((len_ - (self.r * 0.12)), ((-hw) * 2.7), (self.r * 0.25), (hw * 2.2)), (Art.GOLD if (self.tier >= 4) else Color.WHITE))
            tu.poly(Art.rect((len_ - (self.r * 0.12)), (hw * 0.5), (self.r * 0.25), (hw * 2.2)), (Art.GOLD if (self.tier >= 4) else Color.WHITE))
            tu.poly(Art.rect(((-self.r) * 0.1), ((-hw) * 1.2), (self.r * 0.6), (hw * 2.4)), Art.METAL)
        else:
            tu.poly(Art.rect(((-self.r) * 0.2), (-hw), (len_ + (self.r * 0.2)), (2 * hw)), barrel)
            tu.poly(Art.rect((len_ - (self.r * 0.12)), ((-hw) * 1.5), (self.r * 0.25), (hw * 3)), Color.WHITE)
            tu.gloss((len_ * 0.3), ((-hw) * 0.3), (len_ * 0.25), (hw * 0.3))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.35)), 0, (self.r * 0.3), (self.r * 0.12), 5, 0), Art.alpha(Color.WHITE, 230)))
        self.disc(0, 0, (self.r * 0.22), (Art.GOLD if (self.tier >= 4) else Art.METAL_LIGHT))
        if self.tier >= 4:
            self.crown(0, ((-self.r) * 1.0), (self.r * 0.26), 5)
        self.sparkle(((-w) * 0.3), (((-h) * 0.45) - (self.r * 0.1)), (self.r * 0.1))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

GptArt.serial_version_uid = 1
