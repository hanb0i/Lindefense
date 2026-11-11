"""Lindefense CopilotArt (ported from src/lindefense/ui/sprites/towers/CopilotArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class CopilotArt(TowerArt):
    """Copilot, the Pair Programmer: a friendly monitor-headed bot wearing big blue
headphones whose screen scrolls code, firing snippets from a keyboard
launcher. Pro adds a second monitor, Microsoft 365 hex firewall shields,
GitHub Enterprise a triple snippet launcher and antenna headset, and the
Autopilot superclass sprouts aviator wings and a spinning gold propeller."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        w = (self.r * (1.25 + (0.05 * self.tier)))
        h = (self.r * 1.0)
        top = ((-self.r) * 0.65)
        if self.tier >= 4:
            self.poly([((-w) * 0.5), ((-self.r) * 0.1), (((-w) * 0.5) - (self.r * 0.9)), ((-self.r) * 0.45), (((-w) * 0.5) - (self.r * 0.95)), (self.r * 0.05), ((-w) * 0.5), (self.r * 0.3)], Art.GOLD)
            self.poly([(w * 0.5), ((-self.r) * 0.1), ((w * 0.5) + (self.r * 0.9)), ((-self.r) * 0.45), ((w * 0.5) + (self.r * 0.95)), (self.r * 0.05), (w * 0.5), (self.r * 0.3)], Art.GOLD)
            self.plain(Art.rect((((-w) * 0.5) - (self.r * 0.8)), ((-self.r) * 0.25), (self.r * 0.7), (self.r * 0.08)), Art.GOLD_LIGHT)
            self.plain(Art.rect(((w * 0.5) + (self.r * 0.1)), ((-self.r) * 0.25), (self.r * 0.7), (self.r * 0.08)), Art.GOLD_LIGHT)
        self.poly(Art.bar(((-w) * 0.5), (top + (self.r * 0.1)), (w * 0.5), (top + (self.r * 0.1)), (self.r * 0.1)), self.pri_dark)
        self.ellipse(((-w) * 0.52), ((-self.r) * 0.15), (self.r * 0.17), (self.r * 0.3), self.pri)
        self.ellipse((w * 0.52), ((-self.r) * 0.15), (self.r * 0.17), (self.r * 0.3), self.pri)
        self.body_box(((-w) / 2), top, w, h, self.sec)
        self.box(((-w) * 0.4), (top + (self.r * 0.12)), (w * 0.8), (h * 0.6), Art.rgb(0x16213a))
        code_colors = [self.pri, Art.rgb(0x7ee0a0), Art.rgb(0xffd166), Color.WHITE]
        for i in range(3):
            self.plain(Art.rect((((-w) * 0.33) + ((_j.imod(i, 2) * self.r) * 0.12)), ((top + (self.r * 0.22)) + ((i * self.r) * 0.17)), (w * (0.25 + (0.15 * _j.imod((i + 1), 3)))), (self.r * 0.07)), code_colors[i])
        self.plain(Art.rect(((-w) * 0.12), (top + (h * 0.8)), (w * 0.24), (self.r * 0.06)), self.pri)
        if self.tier >= 1:
            self.box((((-w) * 0.5) - (self.r * 0.45)), (top - (self.r * 0.05)), (self.r * 0.45), (self.r * 0.4), self.sec)
            self.plain(Art.rect((((-w) * 0.5) - (self.r * 0.38)), (top + (self.r * 0.03)), (self.r * 0.3), (self.r * 0.22)), Art.rgb(0x16213a))
            self.plain(Art.rect((((-w) * 0.5) - (self.r * 0.34)), (top + (self.r * 0.08)), (self.r * 0.2), (self.r * 0.05)), Art.rgb(0x7ee0a0))
        if self.tier >= 2:
            self.poly(Art.regular(((-w) * 0.62), (self.r * 0.5), (self.r * 0.22), 6, 0), (Art.GOLD if (self.tier >= 4) else self.pri))
            self.poly(Art.regular((w * 0.62), (self.r * 0.5), (self.r * 0.22), 6, 0), (Art.GOLD if (self.tier >= 4) else self.pri))
            self.plain(Art.regular(((-w) * 0.62), (self.r * 0.5), (self.r * 0.1), 6, 0), Color.WHITE)
            self.plain(Art.regular((w * 0.62), (self.r * 0.5), (self.r * 0.1), 6, 0), Color.WHITE)
        if self.tier >= 3:
            self.antenna((w * 0.5), (top + (self.r * 0.1)), (top - (self.r * 0.45)), Art.rgb(0x7ee0a0))
        if self.tier >= 4:
            self.antenna(0, top, (top - (self.r * 0.3)), Art.GOLD)
            self.spinning_poly(Art.star(0, 0, (self.r * 0.55), (self.r * 0.08), 3, 0), 0, (top - (self.r * 0.3)), Art.GOLD_LIGHT, 540)
        tu = self.turret()
        len_ = (self.r * (0.75 + (0.15 * self.tier)))
        hw = (self.r * 0.16)
        tubes = (3 if (self.tier >= 3) else 1)
        for i in range(tubes):
            off = (((i - ((tubes - 1) / 2.0)) * hw) * 1.9)
            tu.poly(Art.rect(((-self.r) * 0.1), (off - (hw * 0.8)), (len_ + (self.r * 0.1)), (hw * 1.6)), (Art.GOLD if (self.tier >= 4) else self.pri))
            tu.poly(Art.rect((len_ - (self.r * 0.1)), (off - hw), (self.r * 0.2), (hw * 2)), self.sec)
        for i in range(3):
            tu.plain(Art.rect(((self.r * 0.1) + ((i * self.r) * 0.2)), ((-hw) * 0.45), (self.r * 0.12), (hw * 0.9)), Art.alpha(Color.WHITE, 160))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.3)), 0, (self.r * 0.28), (self.r * 0.11), 4, 45), Art.alpha(Color.WHITE, 230)))
        self.disc(0, 0, (self.r * 0.18), Art.METAL_LIGHT)
        self.sparkle(((-w) * 0.3), (top + (self.r * 0.08)), (self.r * 0.09))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

CopilotArt.serial_version_uid = 1
