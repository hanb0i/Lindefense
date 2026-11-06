"""Facade for all game audio on pygame.mixer: sound effects (preloaded, 12-voice pool with priority stealing, per-sound
throttling, slight random pitch/volume variation), music with true crossfades on two reserved channels, the persisted
Sound / Music switches and volume levels (AudioSettings).

Switches and volumes are independent: a switched-off channel is silent but keeps its volume. Everything is best
effort: with no audio device, a headless run or missing files the manager stays silent and never throws into the
game. Game code calls the static hooks (sfx / event / menu_music), which are no-ops until install()."""
import os
import sys
import time

from lindefense.audio import audio_settings
from lindefense.audio import hooks
from lindefense.audio.audio_settings import AudioSettings
from lindefense.audio.sfx import Sfx
from lindefense.audio.sfx_families import SfxFamilies
from lindefense.audio.throttle import Throttle
from lindefense.audio.track import Track

CROSSFADE = 1.5
SFX_MIX = 0.9
MUSIC_MIX = 0.6
VOICES = 12
PITCH_VARIANTS = 5          # pre-resampled copies per varying effect, spread over 0.94 .. 1.06
_live = None


def _assets_dir():
    from lindefense.ui.jawt import ASSETS_DIR
    return ASSETS_DIR


def sound_mix_gain(percent):
    return SFX_MIX * audio_settings.gain(percent)


def music_mix_gain(percent):
    return MUSIC_MIX * audio_settings.gain(percent)


class AudioManager:
    CROSSFADE = CROSSFADE
    SFX_MIX = SFX_MIX
    MUSIC_MIX = MUSIC_MIX
    sound_mix_gain = staticmethod(sound_mix_gain)
    music_mix_gain = staticmethod(music_mix_gain)

    def __init__(self, settings, assets_root, open_device):
        """settings: an AudioSettings, or a preference node (None = in memory) to read them from."""
        if not isinstance(settings, AudioSettings):
            settings = AudioSettings(settings)
        self._settings = settings
        self._sfx_dir = os.path.join(assets_root, "sfx")
        self._music_dir = os.path.join(assets_root, "music")
        self._open_device = open_device
        self._throttle = Throttle()
        self._accepted = [0] * len(Sfx.values())
        self._sounds = {}            # Sfx -> [pygame.mixer.Sound variants]
        self._available = set()
        self._bad = set()
        self._ready = False
        self._disabled = False
        self._logged = False
        self._desired = None
        self._playing = None
        self._music_ch = None        # [channel A, channel B]
        self._music_cur = 0
        self._music_cache = {}
        self._rng = 0x9E3779B97F4A7C15
        self._scan_music()

    # ---------------------------------------------------------------- global access
    @staticmethod
    def install():
        global _live
        if _live is None:
            headless = (os.environ.get("SDL_VIDEODRIVER") == "dummy" or bool(os.environ.get("LINDEFENSE_HEADLESS"))
                        or os.environ.get("LINDEFENSE_NOSOUND", "").lower() in ("1", "true"))
            settings = AudioSettings(None) if os.environ.get("LINDEFENSE_DEMO") else AudioSettings.persistent()
            m = AudioManager(settings, _assets_dir(), not headless)
            m.init()
            _live = m
            hooks.set_live(m)
        return _live

    @staticmethod
    def get():
        return _live

    @staticmethod
    def sfx(s):
        m = _live
        if m is not None:
            m.play(s)

    @staticmethod
    def menu_music():
        m = _live
        if m is not None:
            m.set_music([Track.MENU])

    @staticmethod
    def event(ev):
        m = _live
        if m is None or not m._ready:
            return
        s = SfxFamilies.for_event(ev)
        if s is not None:
            m.play(s)

    def on_event(self, ev):
        """Simulation hook (lindefense.audio.hooks.event)."""
        if not self._ready:
            return
        s = SfxFamilies.for_event(ev)
        if s is not None:
            self.play(s)

    # ---------------------------------------------------------------- lifecycle
    def init(self):
        if not self._open_device:
            return
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(VOICES + 2)
            pygame.mixer.set_reserved(2)
            self._music_ch = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self._load_sfx()
            self._ready = True
            self._apply_music(CROSSFADE)
        except Exception as e:
            self._fail("audio init failed: %s" % e)

    def _fail(self, why):
        self._disabled = True
        self._ready = False
        if not self._logged:
            self._logged = True
            print("[audio] disabled: " + why, file=sys.stderr)

    def _load_sfx(self):
        import pygame
        try:
            import numpy as np
        except Exception:
            np = None
        for s in Sfx.values():
            path = os.path.join(self._sfx_dir, s.file + ".wav")
            if not os.path.isfile(path):
                continue
            try:
                base = pygame.mixer.Sound(path)
            except Exception:
                continue
            variants = [base]
            if s.vary and np is not None:
                try:
                    arr = pygame.sndarray.array(base)
                    variants = []
                    for k in range(PITCH_VARIANTS):
                        pitch = 0.94 + 0.12 * k / (PITCH_VARIANTS - 1)
                        n = max(1, int(len(arr) / pitch))
                        idx = np.minimum((np.arange(n) * pitch).astype(np.int64), len(arr) - 1)
                        variants.append(pygame.sndarray.make_sound(np.ascontiguousarray(arr[idx])))
                except Exception:
                    variants = [base]
            self._sounds[s] = variants

    # ---------------------------------------------------------------- switches
    def is_sound_enabled(self):
        return self._settings.is_sound()

    def is_music_enabled(self):
        return self._settings.is_music()

    def is_ready(self):
        return self._ready

    def is_disabled(self):
        return self._disabled

    def set_sound_enabled(self, on):
        self._settings.set_sound(on)
        if not on and self._ready:
            import pygame
            for i in range(2, VOICES + 2):
                pygame.mixer.Channel(i).stop()

    def set_music_enabled(self, on):
        self._settings.set_music(on)
        self._apply_music(CROSSFADE)

    def toggle_sound(self):
        self.set_sound_enabled(not self._settings.is_sound())
        if self._settings.is_sound():
            self.play(Sfx.UI_CLICK)

    def toggle_music(self):
        self.set_music_enabled(not self._settings.is_music())

    # ---------------------------------------------------------------- volumes
    def get_sound_volume(self):
        return self._settings.get_sound_volume()

    def get_music_volume(self):
        return self._settings.get_music_volume()

    def set_sound_volume(self, percent):
        self._settings.set_sound_volume(percent)

    def set_music_volume(self, percent):
        self._settings.set_music_volume(percent)
        self._apply_music_volume()

    def save_settings(self):
        self._settings.flush()

    def get_effective_sound_gain(self):
        return sound_mix_gain(self._settings.get_sound_volume()) if self._settings.is_sound() else 0.0

    def get_effective_music_gain(self):
        return music_mix_gain(self._settings.get_music_volume()) if self._settings.is_music() else 0.0

    # ---------------------------------------------------------------- effects
    def play(self, s):
        if not self._settings.is_sound() or self._disabled:
            return False
        if not self._throttle.allow(s, time.perf_counter_ns()):
            return False
        self._accepted[s.ordinal] += 1
        if self._ready and self._settings.get_sound_volume() > 0:
            variants = self._sounds.get(s)
            if variants:
                g = s.gain
                snd = variants[0]
                if s.vary:
                    r = self._rng
                    r ^= (r << 13) & 0xFFFFFFFFFFFFFFFF
                    r ^= r >> 7
                    r ^= (r << 17) & 0xFFFFFFFFFFFFFFFF
                    self._rng = r
                    a = ((r >> 40) & 0xFFFF) / 65535.0
                    b = ((r >> 20) & 0xFFFF) / 65535.0
                    snd = variants[min(len(variants) - 1, int(a * len(variants)))]
                    g *= 0.85 + 0.15 * b
                self._play_voice(snd, min(1.0, g * sound_mix_gain(self._settings.get_sound_volume())), s.priority)
        return True

    def _play_voice(self, snd, vol, priority):
        import pygame
        ch = pygame.mixer.find_channel(False)
        if ch is None:
            # steal a voice: only from an equal or lower priority sound
            best = None
            for i in range(2, VOICES + 2):
                c = pygame.mixer.Channel(i)
                p = getattr(c, "_lp", 0)
                if best is None or p < best[0]:
                    best = (p, c)
            if best is None or best[0] > priority:
                return
            ch = best[1]
            ch.stop()
        try:
            ch._lp = priority
        except Exception:
            pass
        ch.set_volume(vol)
        ch.play(snd)

    def get_accepted_count(self, s):
        return self._accepted[s.ordinal]

    def get_loaded_sfx_count(self):
        return len(self._sounds)

    # ---------------------------------------------------------------- music
    def _scan_music(self):
        for t in Track.values():
            if os.path.isfile(os.path.join(self._music_dir, t.file + ".wav")):
                self._available.add(t)

    def has_track(self, t):
        return t in self._available

    def get_desired_track(self):
        return self._desired

    def set_music(self, prefs):
        pick = None
        for t in (prefs or ()):
            if t in self._available and t not in self._bad:
                pick = t
                break
        if pick is self._desired:
            return
        self._desired = pick
        self._apply_music(CROSSFADE)

    def _music_sound(self, t):
        import pygame
        snd = self._music_cache.get(t)
        if snd is None:
            snd = pygame.mixer.Sound(os.path.join(self._music_dir, t.file + ".wav"))
            self._music_cache[t] = snd
        return snd

    def _apply_music_volume(self):
        if self._ready and self._music_ch is not None:
            v = self.get_effective_music_gain()
            self._music_ch[self._music_cur].set_volume(v)

    def _apply_music(self, fade):
        if not self._ready:
            return
        want = self._desired if self._settings.is_music() else None
        if want is self._playing:
            return
        self._playing = want
        ms = int(fade * 1000)
        old = self._music_ch[self._music_cur]
        old.fadeout(ms)
        if want is None:
            return
        try:
            snd = self._music_sound(want)
        except Exception:
            self._bad.add(want)
            print("[audio] cannot play music/%s.wav (unsupported or unreadable); skipping" % want.file, file=sys.stderr)
            return
        self._music_cur ^= 1
        ch = self._music_ch[self._music_cur]
        ch.stop()
        ch.set_volume(self.get_effective_music_gain())
        ch.play(snd, loops=-1 if want.loop else 0, fade_ms=ms)
