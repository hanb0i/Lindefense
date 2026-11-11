"""Lindefense Sfx (ported from src/lindefense/audio/Sfx.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.jenum import JEnum


class Sfx(JEnum):
    """Every one-shot sound effect in the game. Each entry names its WAV file under assets/sfx/,
the minimum gap between two plays (the per-sound throttle that keeps huge fights smooth), a base gain,
a priority used when the voice pool is full, and whether a little random pitch/volume variation is applied."""
    UI_CLICK = ('ui_click', 30, 0.70, 3, False, )
    UI_HOVER = ('ui_hover', 70, 0.50, 1, False, )
    UI_SELECT = ('ui_select', 60, 0.70, 3, False, )
    TOWER_PLACE = ('tower_place', 60, 0.75, 4, False, )
    TOWER_UPGRADE = ('tower_upgrade', 80, 0.75, 4, False, )
    TOWER_SELL = ('tower_sell', 80, 0.75, 4, False, )
    INVALID = ('invalid', 120, 0.75, 4, False, )
    ATK_LASER = ('atk_laser', 66, 0.35, 1, True, )
    ATK_PROJECTILE = ('atk_projectile', 66, 0.40, 1, True, )
    ATK_EXPLOSION = ('atk_explosion', 66, 0.50, 2, True, )
    ATK_SONIC = ('atk_sonic', 90, 0.35, 1, True, )
    ATK_MAGIC = ('atk_magic', 66, 0.35, 1, True, )
    ATK_KINETIC = ('atk_kinetic', 66, 0.45, 1, True, )
    ATK_GRAVITY = ('atk_gravity', 80, 0.35, 1, True, )
    ATK_CHAIN = ('atk_chain', 66, 0.35, 1, True, )
    ENEMY_POP = ('enemy_pop', 50, 0.40, 1, True, )
    ENEMY_HIT = ('enemy_hit', 60, 0.25, 0, True, )
    ENEMY_SPLIT = ('enemy_split', 80, 0.40, 1, True, )
    LIFE_LOST = ('life_lost', 100, 0.90, 6, False, )
    WAVE_START = ('wave_start', 300, 0.80, 5, False, )
    WAVE_COMPLETE = ('wave_complete', 300, 0.80, 5, False, )
    BOSS_ALARM = ('boss_alarm', 1500, 0.80, 7, False, )
    BOSS_DEATH = ('boss_death', 500, 1.00, 7, False, )
    PALANTIR_WARNING = ('palantir_warning', 1500, 0.90, 7, False, )
    ABILITY = ('ability', 120, 0.60, 3, True, )
    CASH = ('cash', 150, 0.60, 3, False, )
    VICTORY = ('victory', 1000, 0.90, 8, False, )
    DEFEAT = ('defeat', 1000, 0.90, 8, False, )
    def _init(self, file, min_gap_ms, gain, priority, vary):
        self.file = None
        self.min_gap_ms = 0
        self.gain = 0.0
        self.priority = 0
        self.vary = False
        self.file = file
        self.min_gap_ms = min_gap_ms
        self.gain = gain
        self.priority = priority
        self.vary = vary
        pass
