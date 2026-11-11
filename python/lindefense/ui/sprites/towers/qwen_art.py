"""Lindefense QwenArt (ported from src/lindefense/ui/sprites/towers/QwenArt.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.sprites.towers.tower_art import TowerArt


class QwenArt(TowerArt):
    """Qwen, the Layer Stripper: a stacked pagoda of violet and lilac discs with a
peeler-blade arm that shears layers off enemies. Each tier adds a storey to
the stack and sharper tooling (spinning sawblade, twin blades); the Omni
superclass is a tall rotating-ring pagoda capped in gold."""
    def __init__(self, type_, tier, r):
        TowerArt.__init__(self, type_, tier, r)
        pass
    def build(self):
        layers = (2 + self.tier)
        base = (self.r * 0.3)
        for i in range(layers):
            ly = (base - ((i * self.r) * 0.27))
            rx = (self.r * (0.78 - (i * 0.09)))
            ry = (rx * 0.45)
            c = (self.pri if (_j.imod(i, 2) == 0) else self.sec)
            if (self.tier >= 4) and (i == (layers - 1)):
                c = Art.GOLD
            self.ellipse(0, ly, rx, ry, c)
            self.plain(Art.rect(((-rx) * 0.9), (ly - (ry * 0.3)), (rx * 1.8), (ry * 0.3)), Art.alpha(Color.WHITE, 60))
            if (self.tier >= 4) and (_j.imod(i, 2) == 1):
                self.spinning_ring(0, ly, (rx * 1.2), (rx * 1.08), 12, Art.alpha(Art.GOLD, 200), (60 if (_j.imod(i, 4) == 1) else (-60)))
        top_y = (base - (((layers - 1) * self.r) * 0.27))
        self.eye(0, (top_y - (self.r * 0.02)), (self.r * 0.14), self.pri)
        tu = self.turret()
        len_ = (self.r * (0.9 + (0.2 * self.tier)))
        hw = (self.r * 0.09)
        arms = (2 if (self.tier >= 3) else 1)
        for a in range(arms):
            off = ((((-hw) * 3) if (a == 0) else (hw * 3)) if (arms == 2) else 0)
            tu.poly(Art.rect(((-self.r) * 0.15), (off - hw), (len_ + (self.r * 0.15)), (2 * hw)), Art.METAL)
            if self.tier >= 2:
                tu.spinner(Art.star(0, 0, (self.r * 0.3), (self.r * 0.2), 8, 0), len_, off, (Art.GOLD if (self.tier >= 4) else self.sec_light))
            else:
                tu.poly([(len_ - (self.r * 0.1)), (off - (hw * 2.2)), (len_ + (self.r * 0.3)), off, (len_ - (self.r * 0.1)), (off + (hw * 2.2))], self.sec_light)
        tu.set_spin_speed((900 if (self.tier >= 4) else 540))
        tu.set_flash(tu.plain(Art.star((len_ + (self.r * 0.4)), 0, (self.r * 0.28), (self.r * 0.11), 4, 0), Art.alpha(Color.WHITE, 230)))
        if self.tier >= 4:
            self.crown(0, (top_y - (self.r * 0.42)), (self.r * 0.24), 5)
        self.sparkle(((-self.r) * 0.45), (top_y + (self.r * 0.05)), (self.r * 0.09))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402

QwenArt.serial_version_uid = 1
