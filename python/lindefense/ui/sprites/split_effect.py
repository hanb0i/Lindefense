"""Lindefense SplitEffect (ported from src/lindefense/ui/sprites/SplitEffect.java)."""
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


class SplitEffect(Effect):
    """Split animation for an enemy whose outer body has just been destroyed and
is releasing children. Identity-specific:

  Merge Sort: the hexagon visibly halves along its seam.
  Quick Sort: the partition line flashes and the two bar groups fly off
      to either side while the pivot pops upward.
  TimSort: its purple merge half and orange insertion half separate.
  Counting Sort: the four counters fly out diagonally through the ring.
  Static / Dynamic Array: the container walls fall away.
  Bucket Sort: the bucket tips and its stored contents spill out.
  Anything else: a ring and two puffs."""
    def __init__(self, parent):
        Effect.__init__(self, parent.get_position().x, parent.get_position().y, 0.8)
        r = _j.dmax(4, parent.get_radius())
        seed = parent.get_id()
        _sw1 = parent.get_type()
        if _sw1 is EnemyType.MERGE_SORT:
            R = (r * 0.95)
            l = Art.poly([0, ((-R) * 0.87), ((-R) * 0.5), ((-R) * 0.87), (-R), 0, ((-R) * 0.5), (R * 0.87), 0, (R * 0.87)])
            rt = Art.poly([0, ((-R) * 0.87), (R * 0.5), ((-R) * 0.87), R, 0, (R * 0.5), (R * 0.87), 0, (R * 0.87)])
            l.set_line_width(Thick.NORMAL)
            rt.set_line_width(Thick.NORMAL)
            self.piece(l, 0, 0, ((-r) * 2.2), ((-r) * 0.6), (r * 3), Art.MERGE, 0, 0.7, (-90), True)
            self.piece(rt, 0, 0, (r * 2.2), ((-r) * 0.6), (r * 3), Art.shade(Art.MERGE, 0.15), 0, 0.7, 90, True)
            self.ring(0, 0, (r * 0.1), (r * 1.6), Art.alpha(Art.tint(Art.MERGE, 0.5), 230), 0, 0.35, False)
            self.shards(6, 0, 0, (r * 0.25), (r * 3), (r * 6), Art.tint(Art.MERGE, 0.5), 1, 0, 0.5, seed)
            pass  # break
        elif _sw1 is EnemyType.QUICK_SORT:
            line = Art.poly([((-r) * 0.08), ((-r) * 1.4), (r * 0.08), ((-r) * 1.4), (r * 0.08), (r * 1.4), ((-r) * 0.08), (r * 1.4)])
            self.piece(line, 0, 0, 0, 0, 0, Art.tint(Art.QUICK_PIVOT, 0.5), 0, 0.3, 0, True)
            for i in range(3):
                h = (r * (0.4 + (0.2 * i)))
                b = Art.poly([((-r) * 0.12), ((-h) / 2), (r * 0.12), ((-h) / 2), (r * 0.12), (h / 2), ((-r) * 0.12), (h / 2)])
                self.piece(b, (((-r) * 0.3) - ((i * r) * 0.3)), (r * 0.2), ((-r) * (2.5 + (i * 0.6))), ((-r) * (1 + (i * 0.4))), (r * 6), Art.tint(Art.QUICK, 0.25), (0.03 * i), 0.6, (-120), True)
                b2 = Art.poly([((-r) * 0.12), ((-h) / 2), (r * 0.12), ((-h) / 2), (r * 0.12), (h / 2), ((-r) * 0.12), (h / 2)])
                self.piece(b2, ((r * 0.3) + ((i * r) * 0.3)), 0, (r * (2.5 + (i * 0.6))), ((-r) * (1 + (i * 0.4))), (r * 6), Art.QUICK, (0.03 * i), 0.6, 120, True)
            pivot = Art.poly([((-r) * 0.14), ((-r) * 0.5), (r * 0.14), ((-r) * 0.5), (r * 0.14), (r * 0.5), ((-r) * 0.14), (r * 0.5)])
            self.piece(pivot, 0, ((-r) * 0.2), 0, ((-r) * 3.5), (r * 9), Art.QUICK_PIVOT, 0, 0.7, 200, True)
            self.ring(0, 0, (r * 0.2), (r * 1.8), Art.alpha(Art.QUICK_PIVOT, 220), 0, 0.35, False)
            pass  # break
        elif _sw1 is EnemyType.TIMSORT:
            R = (r * 0.95)
            l = Art.poly([0, ((-R) * 0.87), ((-R) * 0.5), ((-R) * 0.87), (-R), 0, ((-R) * 0.5), (R * 0.87), 0, (R * 0.87)])
            rt = Art.poly([0, ((-R) * 0.87), (R * 0.5), ((-R) * 0.87), R, 0, (R * 0.5), (R * 0.87), 0, (R * 0.87)])
            l.set_line_width(Thick.NORMAL)
            rt.set_line_width(Thick.NORMAL)
            self.piece(l, 0, 0, ((-r) * 2.4), ((-r) * 0.8), (r * 3), Art.TIMSORT, 0, 0.7, (-60), True)
            self.piece(rt, 0, 0, (r * 2.4), ((-r) * 0.8), (r * 3), Art.INSERTION, 0, 0.7, 60, True)
            self.ring(0, 0, (r * 0.1), (r * 1.8), Art.alpha(Color.WHITE, 220), 0, 0.3, False)
            self.shards(4, 0, 0, (r * 0.25), (r * 3), (r * 6), Art.tint(Art.TIMSORT, 0.5), 1, 0, 0.5, seed)
            self.shards(4, 0, 0, (r * 0.25), (r * 3), (r * 6), Art.tint(Art.INSERTION, 0.5), 1, 0.02, 0.5, (seed + 1))
            pass  # break
        elif _sw1 is EnemyType.COUNTING_SORT:
            s = (r * 0.6)
            for i in range(4):
                sx = ((-1) if (_j.imod(i, 2) == 0) else 1)
                sy = ((-1) if (i < 2) else 1)
                box = Art.poly([((-s) / 2), ((-s) / 2), (s / 2), ((-s) / 2), (s / 2), (s / 2), ((-s) / 2), (s / 2)])
                box.set_line_width(Thick.DETAIL)
                self.piece(box, ((sx * r) * 0.4), ((sy * r) * 0.4), ((sx * r) * 3), (((sy * r) * 3) - r), (r * 6), Color(250, 250, 240), 0, 0.65, (sx * 150), False)
            self.ring(0, 0, (r * 0.9), (r * 2.0), Art.alpha(Art.COUNTING, 230), 0, 0.4, False)
            self.shards(8, 0, 0, (r * 0.3), (r * 5), (r * 10), Art.COUNTING, 0, 0, 0.5, seed)
            pass  # break
        elif _sw1 is EnemyType.STATIC_ARRAY or _sw1 is EnemyType.DYNAMIC_ARRAY:
            c = Art.color_of(parent.get_type())
            w = (2.2 * r)
            h = (1.25 * r)
            top_w = Art.poly([((-w) / 2), ((-h) / 2), (w / 2), ((-h) / 2), (w / 2), (((-h) / 2) + (r * 0.18)), ((-w) / 2), (((-h) / 2) + (r * 0.18))])
            bot_w = Art.poly([((-w) / 2), ((h / 2) - (r * 0.18)), (w / 2), ((h / 2) - (r * 0.18)), (w / 2), (h / 2), ((-w) / 2), (h / 2)])
            l_w = Art.poly([((-w) / 2), ((-h) / 2), (((-w) / 2) + (w * 0.1)), ((-h) / 2), (((-w) / 2) + (w * 0.1)), (h / 2), ((-w) / 2), (h / 2)])
            r_w = Art.poly([((w / 2) - (w * 0.1)), ((-h) / 2), (w / 2), ((-h) / 2), (w / 2), (h / 2), ((w / 2) - (w * 0.1)), (h / 2)])
            self.piece(top_w, 0, 0, 0, ((-r) * 3), (r * 6), Art.tint(c, 0.15), 0, 0.6, (-40), True)
            self.piece(bot_w, 0, 0, 0, (r * 1.5), (r * 6), Art.tint(c, 0.15), 0, 0.6, 40, True)
            self.piece(l_w, 0, 0, ((-r) * 3), (-r), (r * 6), Art.shade(c, 0.35), 0, 0.6, (-200), True)
            self.piece(r_w, 0, 0, (r * 3), (-r), (r * 6), Art.shade(c, 0.35), 0, 0.6, 200, True)
            self.ring(0, 0, (r * 0.3), (r * 1.6), Art.alpha(c, 200), 0, 0.35, False)
            pass  # break
        elif _sw1 is EnemyType.BUCKET_SORT:
            b = Art.poly([(-r), ((-0.75) * r), r, ((-0.75) * r), (0.72 * r), (0.95 * r), ((-0.72) * r), (0.95 * r)])
            b.set_line_width(Thick.NORMAL)
            self.piece(b, 0, 0, ((-r) * 0.8), ((-r) * 0.5), (r * 5), Art.BUCKET, 0, 0.75, 160, False)
            stored = parent.get_stored_enemies()
            n = max(3, min(6, len(stored)))
            for i in range(n):
                c = (Art.color_of(stored[i].get_type()) if (i < len(stored)) else Color(80, 140, 230))
                d = Art.oval_at(0, 0, (r * 0.3), (r * 0.3))
                d.set_line_width(Thick.DETAIL)
                self.piece(d, (r * 0.3), ((-r) * 0.3), (r * (0.8 + (0.5 * i))), ((-r) * (1.5 + (0.3 * _j.imod(i, 3)))), (r * 12), c, (0.04 * i), 0.7, 0, False)
            self.shards(6, 0, 0, (r * 0.25), (r * 3), (r * 10), Color(80, 140, 230, 200), 2, 0.05, 0.5, seed)
            pass  # break
        else:
            self.ring(0, 0, (r * 0.3), (r * 1.8), Art.alpha(Art.color_of(parent.get_type()), 200), 0, 0.4, False)
            self.shards(2, 0, 0, (r * 0.8), (r * 2), 0, Art.alpha(Color.WHITE, 160), 2, 0, 0.5, seed)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402
