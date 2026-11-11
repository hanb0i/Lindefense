"""Lindefense ShellSortSprite (ported from src/lindefense/ui/sprites/ShellSortSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.enemy import Enemy
from lindefense.ui.sprites.enemy_sprite import EnemySprite


class ShellSortSprite(EnemySprite):
    """Shell Sort: a chunky segmented nautilus shell (four nested, offset rings
with radiating ribs) with a little foot and two eyes on stalks peeking out
the front. Faint "gap" ghosts fade in ahead of it as the next gap-jump
approaches, spaced by the current gap from Enemy#getShellJumpIndex().
Rings are lost from the outside in as HP drops."""
    def __init__(self, e):
        self.foot = None
        self.eye = None
        EnemySprite.__init__(self, e)
        self.rings = ([None] * 4)
        self.ribs = ([None] * 3)
        self.stalks = ([None] * 2)
        self.ghosts = ([None] * 3)
        self.shown = (-1)
        for i in range(3):
            self.ghosts[i] = Art.oval_at(0, 0, (1.1 * self.r), (1.1 * self.r))
            self.ghosts[i].set_filled(True)
            self.ghosts[i].set_line_width(1.5)
            self.add(self.ghosts[i])
        self.foot = self.part(Art.oval_at((0.75 * self.r), (0.5 * self.r), (1.1 * self.r), (0.65 * self.r)), Art.SHELL_DARK)
        for i in range(2):
            self.stalks[i] = self.thin(self.stroke(Art.line(0, 0, 1, 1), Art.SHELL_DARK))
        for i in range(4):
            d = ((2.0 - (i * 0.46)) * self.r)
            self.rings[i] = self.part(Art.oval_at((((-0.05) * self.r) + ((i * 0.13) * self.r)), (((-0.05) * self.r) + ((i * 0.09) * self.r)), d, d), (Art.SHELL if (_j.imod(i, 2) == 0) else Art.shade(Art.SHELL, 0.25)))
            if i > 0:
                self.thin(self.rings[i])
        for i in range(3):
            a = math.radians((200 + (i * 45)))
            self.ribs[i] = self.thin(self.stroke(Art.line((0.3 * self.r), (0.2 * self.r), ((0.3 * self.r) + (math.cos(a) * self.r)), ((0.2 * self.r) + (math.sin(a) * self.r))), Art.shade(Art.SHELL_DARK, 0.35)))
        self.gloss(((-0.05) * self.r), ((-0.05) * self.r), (2.0 * self.r), (2.0 * self.r))
        self.eye = self.eyes((1.3 * self.r), ((-0.05) * self.r), (0.36 * self.r), (0.3 * self.r))
        self.finish_overlays()
    def update_body(self, e, t):
        layers = EnemySprite.layers_left(e, 5)
        show = (4 if (layers >= 5) else max(1, min(4, (layers - 1))))
        if show != self.shown:
            self.shown = show
            for i in range(4):
                self.rings[i].set_visible((i >= (4 - show)))
            for i in range(3):
                self.ribs[i].set_visible((show >= 3))
        creep = ((math.sin(((t * 6) + e.get_id())) * self.r) * 0.08)
        Art.center(self.foot, ((0.75 * self.r) + creep), (0.5 * self.r))
        for i in range(2):
            ex = (((1.25 * self.r) + creep) + (((-0.18) if (i == 0) else 0.18) * self.r))
            ey = (((-0.05) * self.r) + ((math.sin(((t * 5) + i)) * self.r) * 0.04))
            self.stalks[i].set_start_point(((1.1 * self.r) + creep), (0.35 * self.r))
            self.stalks[i].set_end_point(ex, (ey + (0.1 * self.r)))
            Art.center(self.eye[(2 * i)], ex, ey)
            Art.center(self.eye[((2 * i) + 1)], (ex + (0.04 * self.r)), (ey + (0.03 * self.r)))
        cyc = _j.fmod((t + (e.get_id() * 0.5)), 3.0)
        antic = _j.dmax(0, ((cyc - 1.8) / 1.2))
        gap = (_j.dmin(Enemy.SHELL_GAPS[min(e.get_shell_jump_index(), (len(Enemy.SHELL_GAPS) - 1))], 70) * 0.5)
        for i in range(3):
            d = (((gap * (i + 1)) / 3.0) + (self.r * 0.8))
            Art.center(self.ghosts[i], (self.dir_x * d), (self.dir_y * d))
            a = _j.to_int(((110 * antic) * (1 - (i * 0.25))))
            self.ghosts[i].set_fill_color(Art.alpha(Art.SHELL, _j.idiv(a, 2)))
            self.ghosts[i].set_color(Art.alpha(Art.OUTLINE, a))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
