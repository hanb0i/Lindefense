"""Lindefense Slider (ported from src/lindefense/ui/Slider.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.cyber import Cyber


class Slider(GCompound):
    """Horizontal percentage slider (0-100 %) in the cyberpunk style: a chamfered dark-glass box like UIButton
holding an optional caption, a notched track filled with the accent colour up to the value, a draggable knob and a
percentage readout. Drag the knob, or click anywhere on the track to jump there and keep dragging. The box brightens
on hover and while dragging, and it can be shown #setInactive inactive (greyed, for example while its audio
channel is muted) without losing its value.

Like the buttons, a slider does no event handling of its own: the owning screen forwards mouse events in logical
coordinates to #press, #drag, #release and #setHover (or to the null-safe group
helpers such as #pressAny), so it works at any window size. Coordinates are absolute logical coordinates:
the slider's parent compound must sit at the origin, as the screens' overlays and panels do (the same contract as
UIButton#hit).

User changes reach the model through #setOnChange (every change while dragging) and #setOnRelease
(once, when the drag ends). #bind makes #sync() pull the shown value and the inactive state back from
the model once per frame, so changes made elsewhere (another screen, a hotkey) show up too."""
    def __init__(self, x, y, w, h, caption, accent):
        self.w = 0.0
        self.h = 0.0
        self.track_x = 0.0
        self.track_w = 0.0
        self.readout_right = 0.0
        self.accent = None
        self.frame = None
        self.track = None
        self.knob = None
        self.caption = None
        self.readout = None
        self.value = 0
        self.hover = False
        self.dragging = False
        self.inactive = False
        self.grab_offset = 0.0
        self.hover_t = 0.0
        self.drag_t = 0.0
        self.on_change = None
        self.on_release = None
        self.source = None
        self.inactive_source = None
        GCompound.__init__(self)
        self.w = w
        self.h = h
        self.accent = accent
        self.frame = Cyber.Chamfer(0, 0, w, h, _j.dmin(10, (h * 0.28))).scan(False)
        self.add(self.frame)
        left = Slider.PAD
        if caption is not None:
            self.caption = Cyber.Text(caption)
            self.caption.set_font(Slider.CAPTION_FONT)
            self.caption.set_location(Slider.PAD, (((h + self.caption.get_ascent()) / 2) - 2))
            self.add(self.caption)
            left += (self.caption.get_width() + 10)
        else:
            self.caption = None
        self.readout = Cyber.Text('100%')
        self.readout.set_font(Slider.READOUT_FONT)
        self.readout_right = (w - Slider.PAD)
        readout_w = self.readout.get_width()
        self.track_x = (left + (Slider.KNOB_W / 2))
        self.track_w = _j.dmax(1, ((((self.readout_right - readout_w) - 12) - (Slider.KNOB_W / 2)) - self.track_x))
        self.track = Cyber.Bar(self.track_x, ((h / 2) - 3), self.track_w, 6, 0).notches([0.25, 0.5, 0.75])
        self.add(self.track)
        kh = _j.dmax(10, _j.dmin(24, (h - 14)))
        self.knob = Cyber.Chamfer(0, ((h - kh) / 2), Slider.KNOB_W, kh, 3).scan(False).line_width(1.2)
        self.add(self.knob)
        self.add(self.readout)
        self.set_location(x, y)
        self.refresh()
        self.apply()
    @staticmethod
    def clamp(percent):
        """Clamps a percentage to 0-100."""
        return max(0, min(100, percent))
    @staticmethod
    def value_at(x, track_left, track_width):
        """The percentage at horizontal position x on a track that starts at trackLeft and is
trackWidth long: rounded to a whole percent and clamped to 0-100 (positions before the track give 0,
past it 100). A non-positive width gives 0."""
        if not (track_width > 0):
            return 0
        f = _j.dmax(0, _j.dmin(1, ((x - track_left) / track_width)))
        return Slider.clamp(_j.to_int(_j.jround((f * 100))))
    def value_at_x(self, lx):
        """The percentage at absolute logical x on this slider's track (see #valueAt(double, double, double))."""
        return Slider.value_at(lx, self.get_track_left(), self.track_w)
    def get_track_left(self):
        """Absolute logical x of the track's 0 % end."""
        return self.get_x() + self.track_x
    def get_track_width(self):
        """Track length in logical px (0 % to 100 %)."""
        return self.track_w
    def get_knob_x(self):
        """Absolute logical x of the knob's centre for the current value."""
        return self.get_track_left() + ((self.track_w * self.value) / 100.0)
    def get_center_y(self):
        """Absolute logical y of the slider's vertical centre (the track and knob centre line)."""
        return self.get_y() + (self.h / 2)
    def get_w(self):
        return self.w
    def get_h(self):
        return self.h
    def get_value(self):
        """The current value in percent (0-100)."""
        return self.value
    def set_value(self, percent):
        """Shows percent (clamped) without firing any callback, for syncing from the model."""
        v = Slider.clamp(percent)
        if v == self.value:
            return
        self.value = v
        self.refresh()
    def set_on_change(self, c):
        """Called with the new value whenever the user changes it (press on the track, drag)."""
        self.on_change = c
    def set_on_release(self, c):
        """Called once with the final value when a drag ends (#release())."""
        self.on_release = c
    def bind(self, value, inactive):
        """Binds the slider to a model: #sync() then shows value (except while the user is dragging) and,
if inactive is not null, greys the slider while it returns true. Returns this slider."""
        self.source = value
        self.inactive_source = inactive
        self.sync()
        return self
    def sync(self):
        """Pulls the value and inactive state from the bound model (see #bind); does nothing if unbound."""
        if self.inactive_source is not None:
            self.set_inactive(self.inactive_source())
        if (self.source is not None) and (not self.dragging):
            self.set_value(self.source())
    def set_inactive(self, on):
        """Greys the slider out (it keeps working and keeps its value), e.g. while its audio channel is muted."""
        if on == self.inactive:
            return
        self.inactive = on
        self.apply()
    def is_inactive(self):
        return self.inactive
    def is_dragging(self):
        """True between a #press on the track and the matching #release()."""
        return self.dragging
    def set_hover(self, on):
        """Sets the hover highlight (the owner passes hit(mouse))."""
        self.hover = on
    def hit(self, lx, ly):
        """True if logical point (lx, ly) lies inside the slider's box (absolute coordinates)."""
        return (((self.is_visible() and (lx >= self.get_x())) and (lx <= (self.get_x() + self.w))) and (ly >= self.get_y())) and (ly <= (self.get_y() + self.h))
    def press(self, lx, ly):
        """Mouse press at (lx, ly). On the track (or within a few px of its ends) it starts a drag: a press on the knob
grabs it where it is, a press elsewhere on the track jumps the value there. A press on the caption or readout
changes nothing. Returns true if the press was inside the box, so the owner should not pass it on."""
        if not self.hit(lx, ly):
            return False
        rel = (lx - self.get_track_left())
        if (rel < (((-Slider.KNOB_W) / 2) - Slider.SLOP)) or (rel > ((self.track_w + (Slider.KNOB_W / 2)) + Slider.SLOP)):
            return True
        kx = self.get_knob_x()
        self.grab_offset = ((lx - kx) if (abs((lx - kx)) <= ((Slider.KNOB_W / 2) + 2)) else 0)
        self.dragging = True
        self.user_set(self.value_at_x((lx - self.grab_offset)))
        return True
    def drag(self, lx, ly):
        """Mouse drag to (lx, ly): moves the knob while a drag is in progress (the pointer may leave the box)."""
        if self.dragging:
            self.user_set(self.value_at_x((lx - self.grab_offset)))
    def release(self):
        """Mouse release: ends a drag and fires the release callback. Returns true if a drag was in progress."""
        if not self.dragging:
            return False
        self.dragging = False
        if self.on_release is not None:
            self.on_release(self.value)
        return True
    def user_set(self, v):
        v = Slider.clamp(v)
        if v == self.value:
            return
        self.value = v
        self.refresh()
        if self.on_change is not None:
            self.on_change(v)
    def animate(self, dt):
        """Eases the hover / drag highlight (call once per frame)."""
        k = _j.dmin(1, (dt * 14))
        self.hover_t += (((1 if (self.hover or self.dragging) else 0) - self.hover_t) * k)
        self.drag_t += (((1 if self.dragging else 0) - self.drag_t) * k)
        self.apply()
    def refresh(self):
        """Positions the knob, track fill and readout for the current value."""
        self.track.set_value((self.value / 100.0))
        self.knob.set_location(((self.track_x + ((self.track_w * self.value) / 100.0)) - (Slider.KNOB_W / 2)), self.knob.get_y())
        self.readout.set_label(_j.cat(self.value, '%'))
        self.readout.set_location((self.readout_right - self.readout.get_width()), (((self.h + self.readout.get_ascent()) / 2) - 2))
    def apply(self):
        acc = (Slider.INACTIVE if self.inactive else self.accent)
        act = _j.dmax((self.hover_t * 0.55), self.drag_t)
        self.frame.fill(Cyber.lerp(Slider.FILL, Cyber.alpha(Cyber.lerp(Color(10, 18, 38), acc, 0.22), 235), _j.dmin(1, (act * 0.8)))).border(Cyber.lerp(Cyber.alpha(acc, 150), acc, _j.dmin(1, (0.45 + act)))).glow((0 if self.inactive else _j.dmin(1, ((self.hover_t * 0.75) + (self.drag_t * 0.4)))))
        self.track.colors(Cyber.lerp(acc, Color.WHITE, (0.2 * act)), Slider.TRACK_BACK, Cyber.alpha(acc, (90 if self.inactive else 120)))
        self.knob.fill(Cyber.lerp(acc, Color.WHITE, (0.35 + (0.45 * act)))).border(Cyber.lerp(acc, Color.WHITE, 0.75)).glow((0 if self.inactive else (0.35 + (0.65 * act))))
        Cyber.set_color(self.readout, (Cyber.MUTED if self.inactive else Cyber.lerp(Cyber.TEXT, Color.WHITE, self.hover_t)))
        if self.caption is not None:
            Cyber.set_color(self.caption, (Cyber.DIM if self.inactive else Cyber.alpha(acc, 220)))
    @staticmethod
    def press_any(lx, ly, group):
        """Offers a press to each slider of group (may be null); true if one of them took it."""
        if group is not None:
            for s in group:
                if (s is not None) and s.press(lx, ly):
                    return True
        return False
    @staticmethod
    def drag_all(lx, ly, group):
        """Forwards a drag to every slider of group (may be null); only one being dragged reacts."""
        if group is not None:
            for s in group:
                if s is not None:
                    s.drag(lx, ly)
    @staticmethod
    def release_all(group):
        """Ends any drag in group (may be null); true if one was being dragged."""
        any_ = False
        if group is not None:
            for s in group:
                if (s is not None) and s.release():
                    any_ = True
        return any_
    @staticmethod
    def hover_all(lx, ly, group):
        """Sets each slider's hover from the pointer position (may be null)."""
        if group is not None:
            for s in group:
                if s is not None:
                    s.set_hover(s.hit(lx, ly))
    @staticmethod
    def frame_all(dt, group):
        """Per-frame update for a group (may be null): #sync() then #animate(double)."""
        if group is not None:
            for s in group:
                if s is not None:
                    s.sync()
                    s.animate(dt)


Slider.serial_version_uid = 1
Slider.FILL = Color(10, 18, 38, 225)
Slider.TRACK_BACK = Color(2, 4, 12, 235)
Slider.INACTIVE = Color(0x4a5c78)
Slider.PAD = 14.0
Slider.KNOB_W = 12.0
Slider.SLOP = 10.0
Slider.READOUT_FONT = Cyber.mono(Font.BOLD, 13)
Slider.CAPTION_FONT = Cyber.mono(Font.BOLD, 11)
