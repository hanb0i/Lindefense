"""Lindefense DeathEffect (ported from src/lindefense/ui/sprites/DeathEffect.java)."""
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


class DeathEffect(Effect):
    """Death burst for an ordinary enemy: a brief flash disc, an expanding ring in
the enemy's signature colour and a spray of shards whose shape matches the
enemy family (bubbles pop into circles, arrays shatter into squares, sorting
algorithms into triangles, linked lists into beads and link slivers)."""
    def __init__(self, e):
        Effect.__init__(self, e.get_position().x, e.get_position().y, 0.7)
        r = _j.dmax(4, e.get_radius())
        t = e.get_type()
        c = Art.color_of(t)
        seed = e.get_id()
        self.ring(0, 0, (r * 0.4), (r * 2.2), Art.alpha(c, 220), 0, 0.45, False)
        self.ring(0, 0, (r * 0.2), (r * 1.3), Art.alpha(Color.WHITE, 200), 0, 0.18, True)
        _sw1 = t
        if _sw1 is EnemyType.BUBBLE_SORT:
            self.shards(7, 0, 0, (r * 0.5), (r * 5), (r * 2), Art.alpha(c, 200), 2, 0, 0.5, seed)
            self.ring((0.5 * r), ((-0.4) * r), (r * 0.2), (r * 0.9), Art.alpha(Art.tint(c, 0.4), 230), 0.08, 0.3, False)
            self.ring(((-0.6) * r), (0.5 * r), (r * 0.1), (r * 0.6), Art.alpha(Art.tint(c, 0.4), 230), 0.16, 0.3, False)
        elif _sw1 is EnemyType.STATIC_ARRAY or _sw1 is EnemyType.DYNAMIC_ARRAY or _sw1 is EnemyType.COUNTING_SORT or _sw1 is EnemyType.INSERTION_SORT or _sw1 is EnemyType.QUICK_SORT or _sw1 is EnemyType.QUICK_PARTITION:
            self.shards(8, 0, 0, (r * 0.45), (r * 7), (r * 14), c, 1, 0, 0.55, seed)
        elif _sw1 is EnemyType.SINGLY_LINKED_LIST or _sw1 is EnemyType.DOUBLY_LINKED_LIST:
            self.shards(5, 0, 0, (r * 0.5), (r * 6), (r * 12), c, 2, 0, 0.55, seed)
            self.shards(4, 0, 0, (r * 0.4), (r * 7), (r * 10), Art.shade(c, 0.35), 3, 0, 0.5, (seed + 99))
        elif _sw1 is EnemyType.HEAP_SORT:
            self.shards(6, 0, 0, (r * 0.5), (r * 6), (r * 14), Art.HEAP_ARMOR, 1, 0, 0.6, seed)
            self.shards(6, 0, 0, (r * 0.35), (r * 5), (r * 8), c, 2, 0.05, 0.5, (seed + 7))
        elif _sw1 is EnemyType.RADIX_SORT:
            self.shards(8, 0, 0, (r * 0.4), (r * 7), (r * 12), Art.RADIX, 1, 0, 0.6, seed)
            self.shards(4, 0, 0, (r * 0.3), (r * 4), (r * 8), Art.STEEL, 1, 0.04, 0.5, (seed + 3))
        elif _sw1 is EnemyType.SHELL_SORT:
            self.shards(6, 0, 0, (r * 0.5), (r * 6), (r * 14), Art.SHELL, 0, 0, 0.6, seed)
            self.shards(3, 0, 0, (r * 0.35), (r * 4), (r * 10), Art.SHELL_DARK, 0, 0.03, 0.5, (seed + 5))
        else:
            self.shards(8, 0, 0, (r * 0.45), (r * 7), (r * 12), c, 0, 0, 0.55, seed)
        if e.is_fortified():
            self.shards(5, 0, 0, (r * 0.35), (r * 8), (r * 16), Art.STEEL, 1, 0, 0.5, (seed + 11))
        if e.is_regrow():
            self.shards(5, 0, 0, (r * 0.3), (r * 3), ((-r) * 4), Art.REGROW, 2, 0.05, 0.6, (seed + 13))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
