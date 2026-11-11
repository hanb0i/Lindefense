"""Lindefense DeepSeekArt (ported from src/lindefense/ui/sprites/towers/DeepSeekArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class DeepSeekArt(TowerArt):
    """DeepSeek, the Deep Strike Railgun: a navy diving-bell bot with three glowing
portholes and a periscope, mounting a long electric-blue railgun. Flash
tiers add charge coils and a sonar dish, R1 twin rails, V4 Pro a triple
expert battery, and the Abyss superclass is a dark abyssal hulk with an
anglerfish lure and gold-ringed triple railguns."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        br = (self.r * (0.7 + (0.04 * self.tier)))
        hull = (Art.shade(self.pri, 0.6) if (self.tier >= 4) else self.pri)
        self.ellipse(((-br) * 0.95), (self.r * 0.05), (self.r * 0.22), (self.r * 0.38), Art.shade(hull, 0.85))
        self.ellipse((br * 0.95), (self.r * 0.05), (self.r * 0.22), (self.r * 0.38), Art.shade(hull, 0.85))
        self.body(0, ((-self.r) * 0.1), br, hull)
        self.plain(Art.rect(((-br) * 0.85), (self.r * 0.12), (br * 1.7), (self.r * 0.1)), Art.shade(hull, 0.65))
        for i in range((-1), 2):
            self.disc(((i * br) * 0.42), (self.r * 0.38), (self.r * 0.12), Art.METAL_LIGHT)
            self.plain(Art.circle(((i * br) * 0.42), (self.r * 0.38), (self.r * 0.07), 8), (Art.GOLD_LIGHT if (self.tier >= 4) else self.sec_light))
        if self.tier >= 4:
            self.antenna((br * 0.5), ((-br) * 0.8), ((-br) * 1.55), Art.GOLD_LIGHT)
            self.pulsing_glow((br * 0.5), ((-br) * 1.55), (self.r * 0.3), Art.GOLD_LIGHT, 90, 70, 2.0)
        else:
            self.poly(Art.bar((br * 0.5), ((-br) * 0.8), (br * 0.5), ((-br) * 1.25), (self.r * 0.06)), Art.METAL)
            self.poly(Art.rect(((br * 0.5) - (self.r * 0.05)), ((-br) * 1.35), (self.r * 0.28), (self.r * 0.14)), Art.METAL_LIGHT)
        if self.tier >= 2:
            self.poly([((-br) * 0.9), ((-br) * 0.9), ((-br) * 0.4), ((-br) * 0.9), ((-br) * 0.65), ((-br) * 0.55)], self.sec_light)
            self.poly(Art.bar(((-br) * 0.65), ((-br) * 0.55), ((-br) * 0.65), ((-br) * 0.3), (self.r * 0.05)), Art.METAL)
        tu = self.turret()
        len_ = (self.r * (1.15 + (0.25 * self.tier)))
        hw = (self.r * 0.12)
        barrels = (3 if (self.tier >= 3) else 1)
        rail = (Art.GOLD if (self.tier >= 4) else self.sec)
        for b in range(barrels):
            ang = (((b - 1) * 14) if (barrels == 3) else 0)
            bl = ((len_ * 0.8) if ((barrels == 3) and (b != 1)) else len_)
            tu.poly(Art.spin(Art.rect(((-self.r) * 0.2), (-hw), (bl + (self.r * 0.2)), (2 * hw)), ang), self.pri_dark)
            tu.poly(Art.spin(Art.rect((self.r * 0.05), ((-hw) * 1.5), (bl * 0.75), (hw * 0.55)), ang), rail)
            tu.poly(Art.spin(Art.rect((self.r * 0.05), (hw * 0.95), (bl * 0.75), (hw * 0.55)), ang), rail)
            tu.poly(Art.spin(Art.rect((bl - (self.r * 0.05)), ((-hw) * 1.3), (self.r * 0.25), (hw * 2.6)), ang), Art.METAL_LIGHT)
            if self.tier >= 1:
                c = 0
                while c < (2 + (1 if (self.tier >= 4) else 0)):
                    cx = (bl * (0.3 + (c * 0.2)))
                    tu.poly(Art.spin(Art.rect(cx, ((-hw) * 1.9), (self.r * 0.14), (hw * 3.8)), ang), (Art.GOLD_LIGHT if (self.tier >= 4) else self.sec_light))
                    c += 1
        tu.poly(Art.circle(0, 0, (self.r * 0.3), 14), (Art.GOLD if (self.tier >= 4) else Art.METAL))
        tu.gloss(((-self.r) * 0.08), ((-self.r) * 0.1), (self.r * 0.12), (self.r * 0.08))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.4)), 0, (self.r * 0.35), (self.r * 0.14), 4, 0), Art.alpha(self.sec_light, 240)))
        if self.tier >= 4:
            self.pulsing_glow(0, ((-self.r) * 0.1), (self.r * 0.95), self.sec, 30, 25, 1.5)
            self.crown(0, ((-br) * 1.1), (self.r * 0.25), 5)
        self.sparkle(((-br) * 0.6), ((-br) * 0.6), (self.r * 0.1))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

DeepSeekArt.serial_version_uid = 1
