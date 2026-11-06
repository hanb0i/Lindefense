"""The persisted audio settings: two independent switches (Sound = sound effects, Music), both on by default, and one
volume level per channel in percent (0-100). Muting is its own flag, so switching a channel off and on again keeps its
volume. A volume maps to a mix gain through gain(): a squared (perceptual) taper where 100 % is the tuned mix level.

Switch changes are saved at once; volume changes are cached while a slider is dragged and written by flush()."""
from lindefense import prefs

KEY_SOUND = "sound"
KEY_MUSIC = "music"
KEY_SOUND_VOLUME = "soundVolume"
KEY_MUSIC_VOLUME = "musicVolume"
DEFAULT_SOUND_VOLUME = 100
DEFAULT_MUSIC_VOLUME = 100


def clamp_volume(percent):
    return max(0, min(100, int(percent)))


def gain(percent):
    """Linear gain (0-1) for a volume percentage: (percent / 100)^2 after clamping."""
    f = clamp_volume(percent) / 100.0
    return f * f


class AudioSettings:
    KEY_SOUND_VOLUME = KEY_SOUND_VOLUME
    KEY_MUSIC_VOLUME = KEY_MUSIC_VOLUME
    DEFAULT_SOUND_VOLUME = DEFAULT_SOUND_VOLUME
    DEFAULT_MUSIC_VOLUME = DEFAULT_MUSIC_VOLUME
    clamp_volume = staticmethod(clamp_volume)
    gain = staticmethod(gain)

    def __init__(self, node=None):
        """node: a lindefense.prefs Node, or None for in-memory settings with defaults."""
        self._node = node
        s = m = True
        sv, mv = DEFAULT_SOUND_VOLUME, DEFAULT_MUSIC_VOLUME
        try:
            if node is not None:
                s = node.get_bool(KEY_SOUND, True)
                m = node.get_bool(KEY_MUSIC, True)
                sv = node.get_int(KEY_SOUND_VOLUME, DEFAULT_SOUND_VOLUME)
                mv = node.get_int(KEY_MUSIC_VOLUME, DEFAULT_MUSIC_VOLUME)
        except Exception:
            pass
        self._sound, self._music = s, m
        self._sound_volume, self._music_volume = clamp_volume(sv), clamp_volume(mv)

    @staticmethod
    def persistent():
        try:
            return AudioSettings(prefs.node("audio"))
        except Exception:
            return AudioSettings(None)

    def is_sound(self):
        return self._sound

    def is_music(self):
        return self._music

    def set_sound(self, on):
        self._sound = bool(on)
        self._save(KEY_SOUND, self._sound)

    def set_music(self, on):
        self._music = bool(on)
        self._save(KEY_MUSIC, self._music)

    def get_sound_volume(self):
        return self._sound_volume

    def get_music_volume(self):
        return self._music_volume

    def set_sound_volume(self, percent):
        self._sound_volume = clamp_volume(percent)
        self._put(KEY_SOUND_VOLUME, self._sound_volume)

    def set_music_volume(self, percent):
        self._music_volume = clamp_volume(percent)
        self._put(KEY_MUSIC_VOLUME, self._music_volume)

    def flush(self):
        if self._node is None:
            return
        try:
            self._node.flush()
        except Exception:
            pass

    def _save(self, key, v):
        if self._node is None:
            return
        try:
            self._node.put(key, v)
            self._node.flush()
        except Exception:
            pass

    def _put(self, key, v):
        if self._node is None:
            return
        try:
            self._node.put(key, v)
        except Exception:
            pass
