"""Lindefense ClaudeArt (ported from src/lindefense/ui/sprites/towers/ClaudeArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class ClaudeArt(TowerArt):
    """Claude, the Constitutional Lance: a calm cream-and-terracotta robot with a
single big amber eye that carries a long piercing thought-lance. Each tier
lengthens the lance (Haiku, Sonnet, Fable, Opus); the Mythos superclass
wields a golden double-railed lance ringed by halos with cream orbs circling."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        br = (self.r * (0.68 + (0.03 * self.tier)))
        self.disc(((-br) * 0.95), ((-self.r) * 0.05), (self.r * 0.2), self.pri)
        self.disc((br * 0.95), ((-self.r) * 0.05), (self.r * 0.2), self.pri)
        self.body(0, ((-self.r) * 0.08), br, self.sec)
        self.poly([((-br) * 0.7), (self.r * 0.15), (br * 0.7), (self.r * 0.15), (br * 0.55), ((br * 0.9) - (self.r * 0.08)), ((-br) * 0.55), ((br * 0.9) - (self.r * 0.08))], self.pri)
        if self.tier >= 2:
            self.antenna(((-br) * 0.55), ((-br) * 0.8), ((-br) * 1.35), self.pri_light)
            self.pulsing_glow(((-br) * 0.55), ((-br) * 1.35), (self.r * 0.25), self.pri_light, 80, 60, 1.2)
        if self.tier >= 4:
            self.orbiting_orb(0, ((-self.r) * 0.1), (self.r * 1.2), (self.r * 0.16), 0, 1.6, self.sec)
            self.orbiting_orb(0, ((-self.r) * 0.1), (self.r * 1.2), (self.r * 0.16), math.pi, 1.6, Art.GOLD_LIGHT)
        tu = self.turret()
        len_ = (self.r * (1.0 + (0.24 * self.tier)))
        hw = (self.r * (0.11 + (0.02 * self.tier)))
        shaft = (Art.GOLD if (self.tier >= 4) else self.pri)
        if self.tier >= 3:
            tu.poly(Art.rect(0, ((-hw) * 2.3), (len_ * 0.72), (hw * 0.7)), self.sec)
            tu.poly(Art.rect(0, (hw * 1.6), (len_ * 0.72), (hw * 0.7)), self.sec)
        tu.poly(Art.rect(((-self.r) * 0.25), (-hw), (len_ + (self.r * 0.25)), (2 * hw)), shaft)
        if self.tier >= 1:
            tu.poly([((-self.r) * 0.05), (-hw), (self.r * 0.3), (-hw), 0, ((-hw) * 2.8)], self.sec_dark)
            tu.poly([((-self.r) * 0.05), hw, (self.r * 0.3), hw, 0, (hw * 2.8)], self.sec_dark)
        tip_len = (self.r * (0.3 + (0.06 * self.tier)))
        tu.poly(([(len_ - (self.r * 0.1)), ((-hw) * 2.1), (len_ + tip_len), 0, (len_ - (self.r * 0.1)), (hw * 2.1), (len_ - (self.r * 0.3)), 0] if (self.tier >= 3) else Art.wedge((len_ - (self.r * 0.05)), (len_ + tip_len), (hw * 1.7), 0)), (Color.WHITE if (self.tier >= 4) else self.sec))
        tu.gloss((len_ * 0.35), ((-hw) * 0.35), (len_ * 0.3), (hw * 0.3))
        if self.tier >= 4:
            tu.ring_spinner((hw * 3.4), (hw * 2.4), 8, (len_ * 0.45), 0, Art.GOLD)
            tu.ring_spinner((hw * 3.0), (hw * 2.0), 8, (len_ * 0.8), 0, Art.GOLD_LIGHT)
            tu.set_spin_speed(140)
        tu.set_flash(tu.plain(Art.star(((len_ + tip_len) + (self.r * 0.15)), 0, (self.r * 0.32), (self.r * 0.12), 6, 0), Art.alpha(Color.WHITE, 230)))
        self.disc(0, 0, (self.r * 0.2), self.pri_dark)
        self.eye(0, ((-br) * 0.38), (self.r * 0.26), self.pri)
        if self.tier >= 4:
            self.crown(0, ((-br) * 1.08), (self.r * 0.28), 5)
        self.sparkle(((-br) * 0.75), ((-br) * 0.55), (self.r * 0.1))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

ClaudeArt.serial_version_uid = 1
