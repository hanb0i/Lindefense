"""Lindefense NeonButton (ported from src/lindefense/ui/NeonButton.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.ui_button import UIButton


class NeonButton(UIButton):
    """Menu button: the shared flat UIButton (same frame, sizes and states) with the menus' sounds, a hover tick and the
select sound on click. neon is its accent colour (hover border, selected fill)."""
    def __init__(self, x, y, w, h, label, font, neon, action):
        UIButton.__init__(self, x, y, w, h, label, font, action)
        self.neon = neon
        self.set_accent(neon)
        self.apply()
    def click(self):
        if not self.is_visible():
            return False
        self.press_t = 1.0
        AudioManager.sfx(Sfx.UI_SELECT)
        if self.action is not None:
            self.action()
        return True
    def set_hover(self, h):
        if h and (not self.hover):
            AudioManager.sfx(Sfx.UI_HOVER)
        self.hover = h


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402

NeonButton.serial_version_uid = 1
