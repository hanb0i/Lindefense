"""Lindefense BossDeathEffect (ported from src/lindefense/ui/sprites/BossDeathEffect.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import EnemyType
from lindefense.ui.sprites.effect import Effect


class BossDeathEffect(Effect):
    """Multi-stage explosion for the MOAB/BFB/ZOMG/DDT-class bosses: a chain of
four staggered bursts walking across the hull, hull plating and steel debris
raining down under gravity, rising smoke, and a final white flash with a
large shockwave ring in the boss's accent colour, followed by a rising smoke
column. Lockheed Martin opens with a decloak flash and sonic shockwave and
throws afterburner-coloured debris."""
    def __init__(self, e):
        Effect.__init__(self, e.get_position().x, e.get_position().y, 2.6)
        r = _j.dmax(10, e.get_radius())
        hull = Art.color_of(e.get_type())
        dark = Art.shade(hull, 0.45)
        seed = e.get_id()
        ddt = (e.get_type() is EnemyType.LOCKHEED_MARTIN)
        if ddt:
            pre = Effect(0, 0, 0.6)
            pre.ring(0, 0, (r * 0.3), (r * 1.6), Art.alpha(Color.WHITE, 230), 0, 0.2, True)
            pre.ring(0, 0, (r * 0.5), (r * 3.6), Art.alpha(Color.WHITE, 220), 0.05, 0.5, False)
            pre.ring(0, 0, (r * 0.5), (r * 3.0), Art.alpha(Art.LOCKHEED_GLOW, 220), 0.12, 0.5, False)
            self.stage(pre, 0)
            dark = Art.shade(Art.LOCKHEED, 0.2)
        at = [[(-0.5), (-0.2)], [0.3, 0.25], [(-0.1), (-0.35)], [0.55, (-0.1)]]
        for i in range(len(at)):
            s = Effect((at[i][0] * r), (at[i][1] * r), 0.7)
            s.ring(0, 0, (r * 0.1), (r * 0.55), Art.alpha(Color.WHITE, 230), 0, 0.15, True)
            s.ring(0, 0, (r * 0.15), (r * 0.8), Art.alpha(Color(255, 170, 60), 230), 0.02, 0.35, False)
            s.shards(7, 0, 0, (r * 0.14), (r * 2.5), (r * 1.5), Color(255, 190, 70), 0, 0, 0.4, (seed + (i * 31)))
            s.shards(5, 0, 0, (r * 0.22), (r * 2.2), ((-r) * 0.8), Color(90, 90, 100, 170), 2, 0.1, 0.6, (seed + (i * 17)))
            self.stage(s, (0.22 * i))
        fin = Effect(0, 0, 1.2)
        fin.ring(0, 0, (r * 0.2), (r * 1.3), Art.alpha(Color.WHITE, 240), 0, 0.22, True)
        fin.ring(0, 0, (r * 0.3), (r * 2.6), Art.alpha(hull, 230), 0.02, 0.6, False)
        fin.ring(0, 0, (r * 0.3), (r * 2.1), Art.alpha(Color(255, 200, 80), 200), 0.08, 0.5, False)
        fin.shards(14, 0, 0, (r * 0.26), (r * 3.2), (r * 4), dark, 1, 0, 0.9, (seed + 5))
        fin.shards(10, 0, 0, (r * 0.2), (r * 3.0), (r * 4), Art.STEEL, 1, 0.02, 0.8, (seed + 9))
        fin.shards(8, 0, 0, (r * 0.18), (r * 2.6), (r * 2), Color(255, 180, 60), 0, 0, 0.5, (seed + 13))
        fin.shards(8, 0, 0, (r * 0.4), (r * 1.2), ((-r) * 1.2), Color(80, 80, 90, 160), 2, 0.15, 1.0, (seed + 21))
        self.stage(fin, 0.9)
        if ddt:
            fin.shards(10, 0, 0, (r * 0.22), (r * 3.4), (r * 2.5), Color(255, 120, 40), 0, 0.03, 0.7, (seed + 41))
            fin.shards(6, 0, 0, (r * 0.3), (r * 1.6), (r * 3), Color(255, 60, 60), 1, 0.05, 0.9, (seed + 43))
        column = Effect(0, 0, 1.9)
        for i in range(9):
            puff = Art.oval_at(0, 0, (r * (0.35 + (0.05 * i))), (r * (0.35 + (0.05 * i))))
            puff.set_line_width(0)
            dx = (((Effect.rnd((seed + (i * 3))) - 0.5) * r) * 0.5)
            column.piece(puff, dx, (r * 0.1), (dx * 0.4), ((-r) * (1.2 + (0.15 * _j.imod(i, 3)))), ((-r) * 0.2), Color(70, 70, 80, 170), (0.1 * i), 1.1, 0, False)
        self.stage(column, 1.0)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
