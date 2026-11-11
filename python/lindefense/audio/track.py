"""Lindefense Track (ported from src/lindefense/audio/Track.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.jenum import JEnum


class Track(JEnum):
    """The (all optional) music tracks, looked up as assets/music/<file>.wav."""
    MENU = ('menu', True, )
    BATTLE = ('battle', True, )
    BATTLE_LATE = ('battle_late', True, )
    BATTLE_ONN = ('battle_onn', True, )
    BOSS = ('boss', True, )
    PALANTIR = ('palantir', True, )
    END = ('incoming_data', True, )
    def _init(self, file, loop):
        self.file = None
        self.loop = False
        self.file = file
        self.loop = loop
        pass
