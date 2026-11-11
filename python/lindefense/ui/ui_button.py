"""Lindefense UIButton (ported from src/lindefense/ui/UIButton.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class UIButton(GCompound):
    """The shared flat button: a dark fill with one thin border tinted by its accent colour, an optional vector icon,
and eased hover / selected / press transitions (call #animate(double) once per frame). Hit testing is done in
logical coordinates by the owning screen (#hit(double, double)), so the button works at any window scale.
Styles: normal, primary (solid accent fill, dark text), flat (segmented controls, no frame until active)."""
    def _init_0(self, x, y, w, h, label, font, action):
        self.frame = None
        self.text = None
        self.icon = None
        self.w = 0.0
        self.h = 0.0
        self.action = None
        self.selected = False
        self.hover = False
        self.primary = False
        self.flat = False
        self.text_override = None
        self.hover_t = 0.0
        self.sel_t = 0.0
        self.press_t = 0.0
        self.has_icon = False
        GCompound.__init__(self)
        self.enabled = True
        self.accent = Cyber.CYAN
        self.text_color = Cyber.TEXT
        self.w = w
        self.h = h
        self.action = action
        self.frame = Cyber.Chamfer(0, 0, w, h, UIButton.CUT)
        self.add(self.frame)
        self.icon = Cyber.Icon(Cyber.Kind.PLAY, 14, Cyber.TEXT)
        self.icon.set_visible(False)
        self.add(self.icon)
        self.text = Cyber.Text(label)
        self.text.set_font(font)
        self.add(self.text)
        self.set_location(x, y)
        self.set_text(label)
        self.apply()
    def _init_1(self, x, y, w, h, label, action):
        self.frame = None
        self.text = None
        self.icon = None
        self.w = 0.0
        self.h = 0.0
        self.action = None
        self.selected = False
        self.hover = False
        self.primary = False
        self.flat = False
        self.text_override = None
        self.hover_t = 0.0
        self.sel_t = 0.0
        self.press_t = 0.0
        self.has_icon = False
        self._init_0(x, y, w, h, label, Cyber.display(Font.BOLD, 16), action)
    def __init__(self, *a):
        if len(a) == 6:
            return self._init_1(*a)
        elif len(a) == 7:
            return self._init_0(*a)
        raise TypeError('no overload for %d args' % len(a))
    def set_text(self, s):
        self.text.set_label(s)
        self.layout_content()
    def layout_content(self):
        tw = self.text.get_width()
        iw = (14 if self.has_icon else 0)
        gap = (7 if (self.has_icon and (tw > 0)) else 0)
        total = ((iw + gap) + tw)
        x0 = ((self.w - total) / 2)
        self.icon.set_location(x0, ((self.h - 14) / 2))
        self.text.set_location(((x0 + iw) + gap), (((self.h + self.text.get_ascent()) / 2) - 2))
    def get_text(self):
        return self.text.get_label()
    def set_action(self, r):
        self.action = r
    def set_enabled(self, e):
        self.enabled = e
    def is_enabled(self):
        return self.enabled
    def set_selected(self, s):
        self.selected = s
    def is_selected(self):
        return self.selected
    def set_hover(self, h):
        self.hover = h
    def set_accent(self, c):
        self.accent = c
    def set_primary(self, p):
        self.primary = p
    def set_flat(self, f):
        self.flat = f
        self.frame.size(self.w, self.h)
    def set_text_color(self, c):
        self.text_override = c
    def set_icon(self, k):
        self.has_icon = (k is not None)
        self.icon.set_visible(self.has_icon)
        if k is not None:
            self.icon.set_kind(k)
        self.layout_content()
    def set_icon_struck(self, s):
        """Strike the icon through (audio toggles use this for the "off" state)."""
        self.icon.set_struck(s)
    def set_colors(self, fill, text):
        """Legacy colour setter: the fill hue becomes the accent colour."""
        if (fill is not None) and (fill.get_alpha() > 0):
            self.accent = fill
        self.text_override = text
    def set_selected_color(self, c):
        self.accent = c
    def get_w(self):
        return self.w
    def get_h(self):
        return self.h
    def animate(self, dt):
        """Eases hover / selected / press blends and repaints the frame colours."""
        k = _j.dmin(1, (dt * 14))
        self.hover_t += (((1 if (self.hover and self.enabled) else 0) - self.hover_t) * k)
        self.sel_t += (((1 if self.selected else 0) - self.sel_t) * k)
        self.press_t = _j.dmax(0, (self.press_t - (dt * 5)))
        self.apply()
    def apply(self):
        acc = self.accent
        act = _j.dmax((self.hover_t * 0.5), self.sel_t)
        if not self.enabled:
            fill = (Cyber.alpha(UIButton.FILL, 0) if self.flat else UIButton.DISABLED_FILL)
            border = (None if self.flat else UIButton.DISABLED_LINE)
            tc = UIButton.DISABLED_TEXT
        elif self.primary:
            fill = Cyber.lerp(Cyber.lerp(Cyber.lerp(acc, UIButton.FILL, 0.1), Color.WHITE, (0.16 * self.hover_t)), Color.WHITE, (self.press_t * 0.35))
            border = None
            tc = (self.text_override if (self.text_override is not None) else UIButton.ON_ACCENT)
        elif self.flat:
            fill = Cyber.alpha(acc, _j.to_int(((52 * self.sel_t) + (22 * self.hover_t) + (40 * self.press_t))))
            border = None
            tc = (self.text_override if (self.text_override is not None) else Cyber.lerp(Cyber.MUTED, Color.WHITE, _j.dmax(self.sel_t, self.hover_t)))
        else:
            fill = Cyber.lerp(UIButton.FILL, Cyber.alpha(Cyber.lerp(UIButton.FILL, acc, 0.24), 240), _j.dmin(1, (act + (self.press_t * 0.6))))
            border = Cyber.lerp(Cyber.lerp(Cyber.EDGE_HI, acc, 0.28), acc, _j.dmin(1, act * 1.6))
            tc = (self.text_override if (self.text_override is not None) else Cyber.lerp(Cyber.TEXT, Color.WHITE, act))
        self.frame.fill(fill).border(border)
        Cyber.set_color(self.text, tc)
        self.icon.set_icon_color(tc)
    def hit(self, lx, ly):
        """True if logical point (lx, ly) lies inside the button (absolute coordinates)."""
        return (((self.is_visible() and (lx >= self.get_x())) and (lx <= (self.get_x() + self.w))) and (ly >= self.get_y())) and (ly <= (self.get_y() + self.h))
    def click(self):
        """Runs the action if enabled. Returns true if consumed."""
        if (not self.enabled) or (not self.is_visible()):
            return False
        self.press_t = 1.0
        AudioManager.sfx(Sfx.UI_CLICK)
        if self.action is not None:
            self.action()
        return True


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402

UIButton.serial_version_uid = 1
UIButton.FILL = Color(13, 20, 38, 238)
UIButton.DISABLED_FILL = Color(10, 15, 28, 200)
UIButton.DISABLED_TEXT = Color(0x5d7089)
UIButton.DISABLED_LINE = Color(0x1f2d42)
UIButton.ON_ACCENT = Color(0x06111a)   # text on a primary (accent-filled) button
UIButton.CUT = 4.0
