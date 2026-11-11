"""Lindefense BossDockModel (ported from src/lindefense/ui/BossDockModel.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.boss import Boss


class BossDockModel:
    """Pure logic for the boss health dock: which bosses get a row, which one is
primary, and how many are hidden behind "+N more". Kept free of ACM so it
can be unit tested."""
    class Layout:
        """Result of laying out the dock."""
        def __init__(self, primary, compact, hidden):
            self.primary = None
            self.compact = None
            self.hidden = 0
            self.primary = primary
            self.compact = compact
            self.hidden = hidden
        def rows(self):
            return (0 if (self.primary is None) else 1) + len(self.compact)
    def __init__(self):
        pass
    @staticmethod
    def layout(bosses):
        """Orders bosses by importance (Palantir first, then biggest max HP, then
closest to the exit) and caps the dock at #MAX_ROWS rows."""
        sorted_ = _j.ArrayList(bosses)
        _j.sort(sorted_, _j.Fn(_j.then_comparing(_j.Fn(_j.then_comparing(_j.Fn(_j.comparing_double(_j.Fn(lambda b: (0 if b.is_palantir() else 1)))), _j.comparing_double(_j.Fn(lambda b: (-b.get_max_hp()))))), _j.comparing_double(_j.Fn(lambda o, *a: o.get_remaining_distance(*a))))))
        if len(sorted_) == 0:
            return BossDockModel.Layout(None, _j.ArrayList(), 0)
        primary = sorted_[0]
        compact = _j.ArrayList()
        i = 1
        while (i < len(sorted_)) and (len(compact) < (BossDockModel.MAX_ROWS - 1)):
            _j_add(compact, sorted_[i])
            i += 1
        hidden = ((len(sorted_) - 1) - len(compact))
        return BossDockModel.Layout(primary, compact, hidden)


BossDockModel.MAX_ROWS = 3
