"""Lindefense ScreenShake (ported from src/lindefense/ui/ScreenShake.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class ScreenShake:
    """HIGH-quality cosmetic camera shake (see GraphicsSettings.Quality#screenShake). Impacts add "trauma" (0-1)
that decays over time; the offset grows with trauma squared, so small kicks are subtle and big ones punchy, and it
follows smooth sine noise rather than random jumps. The offset is in logical px and only moves the drawing of the
battlefield, never the simulation or mouse picking. REDUCED MOTION (SETTINGS > ACCESSIBILITY) switches it off whatever the
preset."""
    def __init__(self):
        self.f_trauma = 0.0
        self.time = 0.0
        pass
    def kick(self, amount):
        """Adds trauma (clamped to 1); ignored unless the preset enables screen shake, and with reduced motion on."""
        if (amount <= 0) or (not GraphicsSettings.get().quality().screen_shake) or display_settings.reduced_motion():
            return
        self.f_trauma = _j.dmin(1, (self.f_trauma + amount))
    def update(self, dt):
        self.time += dt
        self.f_trauma = _j.dmax(0, (self.f_trauma - (ScreenShake.DECAY * dt)))
    def trauma(self):
        return self.f_trauma
    def offset_x(self):
        if display_settings.reduced_motion():
            return 0
        s = (self.f_trauma * self.f_trauma)
        return 0 if (s == 0) else (((ScreenShake.MAX_OFFSET * s) * math.sin((self.time * 47.0))) * math.cos((self.time * 13.0)))
    def offset_y(self):
        if display_settings.reduced_motion():
            return 0
        s = (self.f_trauma * self.f_trauma)
        return 0 if (s == 0) else ((ScreenShake.MAX_OFFSET * s) * math.sin(((self.time * 39.0) + 1.3)))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402

ScreenShake.MAX_OFFSET = 7.0
ScreenShake.DECAY = 1.8
