"""Lindefense TowerIcons (ported from src/lindefense/ui/sprites/towers/TowerIcons.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class TowerIcons:
    """Static tower icons for the shop and the info panel. An icon is the tower's
body art (including its tier-4 aura) fitted into a size x size
box centred on (0,0), facing straight up. Like the battlefield, icons paint in the minimal style: the purely
decorative parts (Thick#DETAIL_DECOR: shadow, gloss, sparkles, glows) are left out."""
    class Icon(GCompound):
        """The icon compound: paints its art at least at the decorative level of detail."""
        def paint(self, g):
            prev = Thick.set_level(max(Thick.level(), Thick.DETAIL_DECOR))
            try:
                GCompound.paint(self, g)
            finally:
                Thick.set_level(prev)
    def __init__(self):
        pass
    @staticmethod
    def create(type_, tier, size):
        """Creates an icon.

@param type tower type
@param tier game tier (clamped); drawn with TowerArtFactory#artStage(TowerType, int)
@param size box side in logical units
@return a compound whose content fits in the box centred at (0,0)"""
        t = TowerArtFactory.art_stage(type_, tier)
        extent = (TowerIcons.EXTENT if (t >= 4) else 1.45)
        r = (size / (2 * extent))
        art = TowerArtFactory.create(type_, t, r)
        art.animate(0, 0)
        g = TowerIcons.Icon()
        g.add(art, 0, 0)
        return g


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.thick import Thick  # noqa: E402
from lindefense.ui.sprites.towers.tower_art_factory import TowerArtFactory  # noqa: E402

TowerIcons.EXTENT = 1.9
