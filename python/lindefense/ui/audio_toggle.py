"""Lindefense AudioToggle (ported from src/lindefense/ui/AudioToggle.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class AudioToggle:
    """A Sound (speaker icon) or Music (note icon) on/off toggle built on UIButton. The owner calls
#sync() once per frame so the button always mirrors the persisted setting, including changes made
with the M / N hotkeys or on another screen. "Off" is shown dimmed with the icon struck through.

#soundVolume / #musicVolume build the matching volume Slider for a channel. Toggle and
slider are independent: the toggle mutes or unmutes without changing the level, and the slider sets the level without
switching the channel on or off (it is greyed out, keeping its value, while the channel is off)."""
    def __init__(self, music, x, y, w, h, label):
        self.button = None
        self.f_music = False
        self.label = None
        self.f_music = music
        self.label = label
        def _lam1(*, music=music):
            m = AudioManager.get()
            if m is None:
                return
            if music:
                m.toggle_music()
            else:
                m.toggle_sound()
        action = _j.Fn(_lam1)
        f = (Cyber.mono(Font.BOLD, 11) if (label is None) else Cyber.mono(Font.BOLD, 12))
        self.button = UIButton(x, y, w, h, ('' if (label is None) else label), f, action)
        self.button.set_icon((Cyber.Kind.NOTE if music else Cyber.Kind.SPEAKER))
        self.button.set_accent((Cyber.MAGENTA if music else Cyber.CYAN))
        self.sync()
    @staticmethod
    def sound(x, y, w, h, label):
        """Creates a Sound toggle; label may be null for an icon-only chip."""
        return AudioToggle(False, x, y, w, h, label)
    @staticmethod
    def music(x, y, w, h, label):
        """Creates a Music toggle; label may be null for an icon-only chip."""
        return AudioToggle(True, x, y, w, h, label)
    @staticmethod
    def pair(x, y, w, h, gap, sound_label, music_label, into):
        """Creates both toggles and adds their buttons to into (for hit testing / animation)."""
        s = AudioToggle.sound(x, y, w, h, sound_label)
        m = AudioToggle.music(((x + w) + gap), y, w, h, music_label)
        _j_add(into, s.button)
        _j_add(into, m.button)
        return [s, m]
    @staticmethod
    def sound_volume(x, y, w, h, caption):
        """Creates a sound-effects volume slider bound to the audio settings: dragging sets the level live, releasing saves
it and plays a click at the new level, and the slider greys out while Sound is off. Null-safe without audio."""
        return AudioToggle.volume_slider(False, x, y, w, h, caption)
    @staticmethod
    def music_volume(x, y, w, h, caption):
        """Creates a music volume slider bound to the audio settings: dragging sets the level live (the music follows at
once), releasing saves it, and the slider greys out while Music is off. Null-safe without audio."""
        return AudioToggle.volume_slider(True, x, y, w, h, caption)
    @staticmethod
    def volume_slider(music, x, y, w, h, caption):
        s = Slider(x, y, w, h, caption, (Cyber.MAGENTA if music else Cyber.CYAN))
        def _lam2(v, *, music=music):
            m = AudioManager.get()
            if m is None:
                return
            if music:
                m.set_music_volume(v)
            else:
                m.set_sound_volume(v)
        s.set_on_change(_j.Fn(_lam2))
        def _lam3(v, *, music=music):
            m = AudioManager.get()
            if m is None:
                return
            m.save_settings()
            if not music:
                m.play(Sfx.UI_CLICK)
        s.set_on_release(_j.Fn(_lam3))
        def _lam4(*, music=music):
            m = AudioManager.get()
            if m is None:
                return AudioSettings.DEFAULT_MUSIC_VOLUME if music else AudioSettings.DEFAULT_SOUND_VOLUME
            return m.get_music_volume() if music else m.get_sound_volume()
        def _lam5(*, music=music):
            m = AudioManager.get()
            return (m is not None) and (not (m.is_music_enabled() if music else m.is_sound_enabled()))
        return s.bind(_j.Fn(_lam4), _j.Fn(_lam5))
    def get_button(self):
        return self.button
    def sync(self):
        """Refreshes state visuals from the audio settings."""
        m = AudioManager.get()
        on = ((m is None) or (m.is_music_enabled() if self.f_music else m.is_sound_enabled()))
        self.button.set_selected(on)
        self.button.set_icon_struck((not on))
        self.button.set_text_color((None if on else Cyber.MUTED))
        if self.label is not None:
            self.button.set_text(_j.cat(self.label, (' ON' if on else ' OFF')))
        self.button.set_accent(((Cyber.MAGENTA if self.f_music else Cyber.CYAN) if on else Color(0x4a5c78)))
    @staticmethod
    def sync_all(t):
        """Syncs several toggles."""
        for a in t:
            a.sync()


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.audio_settings import AudioSettings  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.slider import Slider  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402
