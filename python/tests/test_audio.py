"""Audio system and volume sliders (port of AudioTests.java + VolumeTests.java). Nothing opens an audio device: managers
are built with open_device=False, and preference nodes live in a throw-away directory."""
import os

import pytest

from lindefense import prefs
from lindefense.audio import audio_settings as AS
from lindefense.audio.audio_manager import AudioManager, MUSIC_MIX, SFX_MIX, music_mix_gain, sound_mix_gain
from lindefense.audio.audio_settings import AudioSettings
from lindefense.audio.music_director import MusicDirector
from lindefense.audio.sfx import Sfx
from lindefense.audio.throttle import Throttle
from lindefense.audio.track import Track
from lindefense.ui.cyber import Cyber
from lindefense.ui.slider import Slider

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
_n = [0]


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


def _node():
    _n[0] += 1
    return prefs.node("test-audio-%d" % _n[0])


def _near(a, b):
    return abs(a - b) < 1e-6


# ---------------------------------------------------------------- AudioTests
def test_settings_round_trip(check):
    node = _node()
    a = AudioSettings(node)
    check(a.is_sound() and a.is_music(), "both switches default to on")
    a.set_sound(False)
    check(not a.is_sound() and a.is_music(), "switches are independent")
    a.set_music(False)
    a.set_sound(True)
    b = AudioSettings(node)
    check(b.is_sound() and not b.is_music(), "settings persist across instances")
    m = AudioManager(node, "no-such-dir", False)
    check(m.is_sound_enabled() and not m.is_music_enabled(), "manager reads persisted settings")
    m.toggle_music()
    m.toggle_sound()
    c = AudioSettings(node)
    check(c.is_music() and not c.is_sound(), "manager toggles persist")
    check(not m.play(Sfx.UI_CLICK), "no effects accepted while sound is off")


def test_throttle_caps(check):
    t = Throttle()
    pops = lasers = 0
    for i in range(1000):
        now = i * 1_000_000
        if t.allow(Sfx.ENEMY_POP, now):
            pops += 1
        if t.allow(Sfx.ATK_LASER, now):
            lasers += 1
    check(15 <= pops <= 21, "enemy pops capped near 20/s (got %d)" % pops)
    check(12 <= lasers <= 16, "attack family capped near 15/s (got %d)" % lasers)
    check(t.allow(Sfx.UI_CLICK, 0) and not t.allow(Sfx.UI_CLICK, 1_000_000), "same sound within its gap is rejected")
    check(t.allow(Sfx.UI_CLICK, 40_000_000), "same sound after its gap is accepted")
    m = AudioManager(_node(), "no-such-dir", False)
    accepted = sum(1 for _ in range(5000) if m.play(Sfx.ENEMY_POP))
    check(accepted <= 2, "burst of 5000 pops accepts at most 2 (got %d)" % accepted)
    check(m.get_accepted_count(Sfx.ENEMY_POP) == accepted, "accepted counter matches")


def test_no_device_is_graceful(check):
    m = AudioManager(_node(), "no-such-dir", False)
    m.init()
    check(not m.is_ready(), "manager without a device is never ready")
    threw = False
    try:
        m.play(Sfx.WAVE_START)
        m.set_music([Track.BATTLE])
        m.set_music_enabled(False)
        m.set_sound_enabled(False)
        m.set_music_enabled(True)
        AudioManager.sfx(Sfx.UI_CLICK)
        AudioManager.menu_music()
    except Exception:
        threw = True
    check(not threw, "all calls are safe without a device")


def test_missing_music(check, tmp_path):
    none = AudioManager(_node(), str(tmp_path), False)
    for t in Track:
        check(not none.has_track(t), "no track reported when music/ is missing: %s" % t)
    none.set_music([Track.BOSS, Track.BATTLE])
    check(none.get_desired_track() is None, "missing music resolves to silence")
    music = tmp_path / "music"
    music.mkdir()
    (music / "battle.wav").write_bytes(bytes([1, 2, 3]))
    some = AudioManager(_node(), str(tmp_path), False)
    check(some.has_track(Track.BATTLE) and not some.has_track(Track.BOSS), "only existing tracks are available")
    some.set_music([Track.BOSS, Track.BATTLE_LATE, Track.BATTLE])
    check(some.get_desired_track() is Track.BATTLE, "falls back along the preference list")
    some.set_music([Track.PALANTIR])
    check(some.get_desired_track() is None, "a missing track with no fallback plays nothing")


def test_music_director_rules(check):
    d = MusicDirector()
    check(d.choose(False, False, 5, False, False, False, 0)[0] is Track.BATTLE, "early waves use battle")
    late = d.choose(False, False, 60, False, False, False, 1)
    check(late[0] is Track.BATTLE_LATE and late[-1] is Track.BATTLE, "wave 60+ uses battle_late then battle")
    onn = d.choose(False, False, 10, True, False, False, 2)
    check(onn[0] is Track.BATTLE_ONN and onn[1] is Track.BATTLE_LATE and onn[2] is Track.BATTLE, "O(N^N) overrides battle tracks")
    boss = d.choose(False, False, 40, False, False, True, 3)
    check(boss[0] is Track.BOSS and boss[1] is Track.BATTLE, "boss theme falls back to the battle track")
    check(d.choose(False, False, 40, False, False, False, 4)[0] is Track.BOSS, "boss theme is held after the boss dies")
    check(d.choose(False, False, 40, False, False, False, 3 + MusicDirector.BOSS_HOLD_SECONDS + 0.1)[0] is Track.BATTLE, "returns after the hold")
    pal = d.choose(False, False, 100, False, True, True, 20)
    check(pal[0] is Track.PALANTIR and pal[1] is Track.BOSS, "Palantir overrides everything, falling back to boss")
    check(MusicDirector().choose(False, False, 100, False, False, False, 0)[0] is Track.PALANTIR, "wave 100 uses the Palantir theme")
    check(d.choose(True, False, 100, False, True, False, 30)[0] is Track.END, "victory uses the end-screen track")
    check(d.choose(False, True, 33, False, False, False, 31)[0] is Track.END, "defeat uses the end-screen track")
    check(Track.END.loop and Track.BATTLE.loop and Track.MENU.loop, "all tracks loop")


def test_shipped_audio_decodes(check, monkeypatch):
    """Every shipped effect and track decodes with pygame's mixer and is not silent (dummy audio driver)."""
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import numpy as np
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    try:
        for sub, lo, hi in (("sfx", 0.01, 10), ("music", 5, 400)):
            d = os.path.join(ASSETS, sub)
            names = sorted(f for f in os.listdir(d) if f.endswith(".wav")) if os.path.isdir(d) else []
            for f in names:
                try:
                    snd = pygame.mixer.Sound(os.path.join(d, f))
                except Exception as e:
                    check(False, "%s/%s failed to decode: %s" % (sub, f, e))
                    continue
                n = snd.get_length()
                check(lo <= n <= hi, "%s/%s duration is sensible (%.2f s)" % (sub, f, n))
                check(np.abs(pygame.sndarray.array(snd)).max() > 0, "%s/%s is not silent" % (sub, f))
        for s in Sfx:
            check(os.path.isfile(os.path.join(ASSETS, "sfx", s.file + ".wav")), "effect file for %s ships" % s)
    finally:
        pygame.mixer.quit()


# ---------------------------------------------------------------- VolumeTests
def test_taper_and_clamp(check):
    check(AS.gain(0) == 0 and AS.gain(100) == 1, "0 % is silence, 100 % unity")
    check(_near(AS.gain(50), 0.25) and _near(AS.gain(10), 0.01), "squared taper")
    check(all(AS.gain(p) > AS.gain(p - 1) for p in range(1, 101)), "gain rises strictly")
    check(AS.gain(-20) == 0 and AS.gain(250) == 1, "out-of-range volumes clamp before the taper")
    check(AS.clamp_volume(-1) == 0 and AS.clamp_volume(101) == 100 and AS.clamp_volume(37) == 37, "clamp_volume")
    check(AS.clamp_volume(-2 ** 31) == 0 and AS.clamp_volume(2 ** 31 - 1) == 100, "clamp_volume extremes")
    check(sound_mix_gain(100) == SFX_MIX and _near(SFX_MIX, 0.9), "effects at 100 % keep the tuned 0.9 mix gain")
    check(music_mix_gain(100) == MUSIC_MIX and _near(MUSIC_MIX, 0.6), "music at 100 % keeps the tuned 0.6 mix gain")
    check(_near(music_mix_gain(50), 0.6 * 0.25) and sound_mix_gain(0) == 0, "mix gain = tuned level x taper")


def test_defaults_and_persistence(check):
    node = _node()
    a = AudioSettings(node)
    check(a.get_sound_volume() == AS.DEFAULT_SOUND_VOLUME and a.get_music_volume() == AS.DEFAULT_MUSIC_VOLUME, "defaults")
    check(AS.DEFAULT_SOUND_VOLUME == 100 and AS.DEFAULT_MUSIC_VOLUME == 100, "defaults are 100 %")
    mem = AudioSettings(None)
    check(mem.get_sound_volume() == 100 and mem.get_music_volume() == 100 and mem.is_sound() and mem.is_music(), "in-memory defaults")
    a.set_sound_volume(35)
    a.set_music_volume(140)
    check(a.get_sound_volume() == 35 and a.get_music_volume() == 100, "setters clamp (140 -> 100)")
    a.set_music_volume(-9)
    check(a.get_music_volume() == 0, "setters clamp (-9 -> 0)")
    a.set_music_volume(62)
    a.flush()
    b = AudioSettings(node)
    check(b.get_sound_volume() == 35 and b.get_music_volume() == 62, "volumes round-trip")
    check(b.is_sound() and b.is_music(), "volume changes leave the switches alone")
    node.put(AS.KEY_SOUND_VOLUME, 999)
    node.put(AS.KEY_MUSIC_VOLUME, "loud")
    c = AudioSettings(node)
    check(c.get_sound_volume() == 100, "stored 999 reads back clamped")
    check(c.get_music_volume() == AS.DEFAULT_MUSIC_VOLUME, "unparsable stored volume falls back to the default")
    node.put(AS.KEY_SOUND_VOLUME, 20)
    node.put(AS.KEY_MUSIC_VOLUME, 45)
    m = AudioManager(node, "no-such-dir", False)
    check(m.get_sound_volume() == 20 and m.get_music_volume() == 45, "manager reads persisted volumes")
    m.set_sound_volume(75)
    m.set_music_volume(5)
    m.save_settings()
    d = AudioSettings(node)
    check(d.get_sound_volume() == 75 and d.get_music_volume() == 5, "manager volume changes persist")


def test_mute_is_independent(check):
    node = _node()
    m = AudioManager(node, "no-such-dir", False)
    m.set_music_volume(40)
    m.set_sound_volume(70)
    check(_near(m.get_effective_music_gain(), music_mix_gain(40)), "music heard at its volume while on")
    m.toggle_music()
    check(not m.is_music_enabled() and m.get_music_volume() == 40 and m.get_effective_music_gain() == 0, "muting keeps the volume")
    check(m.is_sound_enabled() and m.get_sound_volume() == 70, "muting music leaves sound alone")
    m.set_music_volume(90)
    check(not m.is_music_enabled() and m.get_music_volume() == 90, "a volume change while muted does not unmute")
    m.toggle_music()
    check(m.is_music_enabled() and _near(m.get_effective_music_gain(), music_mix_gain(90)), "unmuting restores the latest level")
    m.toggle_sound()
    check(not m.is_sound_enabled() and m.get_sound_volume() == 70 and m.get_effective_sound_gain() == 0, "muting sound keeps its volume")
    check(not m.play(Sfx.UI_CLICK), "no effects while sound is muted")
    m.toggle_sound()
    m.set_sound_volume(0)
    check(m.is_sound_enabled() and m.get_effective_sound_gain() == 0, "volume 0 is silent but not switched off")
    p = AudioSettings(node)
    check(p.is_music() and p.is_sound() and p.get_music_volume() == 90 and p.get_sound_volume() == 0, "switches and volumes persist")


def test_slider_mapping(check):
    va = Slider.value_at
    check(va(100, 100, 200) == 0 and va(300, 100, 200) == 100 and va(200, 100, 200) == 50, "track ends and middle")
    check(va(150, 100, 200) == 25 and va(250.9, 100, 200) == 75, "quarter points")
    check(va(-50, 100, 200) == 0 and va(9999, 100, 200) == 100, "off-track clamps")
    check(va(101, 100, 200) == 1 and va(100.9, 100, 200) == 0, "rounds to the nearest percent")
    check(va(5, 0, 0) == 0 and va(5, 0, -3) == 0 and va(float("nan"), 0, 100) == 0, "degenerate input gives 0")
    last, mono = -1, True
    x = 90.0
    while x <= 310:
        v = va(x, 100, 200)
        mono = mono and v >= last
        last = v
        x += 0.5
    check(mono, "value never decreases left to right")
    s = Slider(400, 300, 290, 46, "VOL", Cyber.CYAN)
    check(s.get_track_width() > 120 and s.get_track_left() > 400 and s.get_track_left() + s.get_track_width() < 690, "track inside the box")
    check(s.value_at_x(s.get_track_left()) == 0 and s.value_at_x(s.get_track_left() + s.get_track_width()) == 100, "absolute track mapping")
    for v in (0, 1, 33, 50, 99, 100):
        s.set_value(v)
        check(s.get_value() == v and s.value_at_x(s.get_knob_x()) == v, "knob maps back to its value (%d)" % v)
    s.set_value(-5)
    check(s.get_value() == 0, "set_value clamps low")
    s.set_value(300)
    check(s.get_value() == 100, "set_value clamps high")
    s.set_location(10, 900)
    check(s.value_at_x(s.get_track_left() + s.get_track_width() / 2) == 50, "mapping follows the logical position")
    check(Slider(0, 0, 290, 46, None, Cyber.MAGENTA).get_track_width() > s.get_track_width(), "no caption leaves a longer track")


def test_slider_input(check):
    s = Slider(400, 300, 290, 46, "VOL", Cyber.CYAN)
    changes, releases = [], []
    s.set_on_change(changes.append)
    s.set_on_release(releases.append)
    cy, left, tw = s.get_center_y(), s.get_track_left(), s.get_track_width()
    check(not s.press(399, cy) and not s.press(500, 299) and not s.press(500, 347), "presses outside are not taken")
    check(not s.is_dragging() and not changes and not s.release() and not releases, "outside presses change nothing")
    check(s.press(left + tw * 0.25, cy) and s.is_dragging(), "press on the track starts a drag")
    check(s.get_value() == 25 and changes == [25], "track click jumps to the clicked value")
    s.drag(left + tw * 0.6, cy + 80)
    check(s.get_value() == 60 and changes[-1] == 60, "drag follows the pointer outside the box")
    s.drag(left - 500, cy)
    check(s.get_value() == 0, "clamps to 0")
    s.drag(left + tw + 500, cy)
    check(s.get_value() == 100, "clamps to 100")
    n = len(changes)
    s.drag(left + tw + 900, cy)
    check(len(changes) == n, "no callback when the value does not change")
    check(s.release() and not s.is_dragging() and releases == [100], "release reports the final value once")
    s.drag(left, cy)
    check(s.get_value() == 100, "drags after release are ignored")
    s.set_value(40)
    del changes[:]
    kx = s.get_knob_x()
    check(s.press(kx + 4, cy) and s.get_value() == 40 and not changes, "grabbing the knob keeps its value")
    s.drag(kx + 4 + tw * 0.1, cy)
    check(s.get_value() == 50, "knob moves by the drag distance (got %d)" % s.get_value())
    s.release()
    s.set_value(70)
    del changes[:]
    check(s.press(s.get_x() + 3, cy) and not s.is_dragging() and s.get_value() == 70 and not changes, "caption press is swallowed")
    check(s.press(s.get_x() + s.get_w() - 3, cy) and not s.is_dragging() and s.get_value() == 70, "readout press is swallowed")
    model, muted = [15], [True]
    s.bind(lambda: model[0], lambda: muted[0])
    check(s.get_value() == 15 and s.is_inactive(), "bind syncs value and inactive state")
    model[0], muted[0] = 80, False
    s.sync()
    check(s.get_value() == 80 and not s.is_inactive(), "sync follows the model")
    s.press(left + tw * 0.3, cy)
    model[0] = 5
    s.sync()
    check(s.get_value() == 30, "sync does not fight a drag")
    s.release()
    s.sync()
    check(s.get_value() == 5, "sync resumes after release")
    muted[0] = True
    s.sync()
    del changes[:]
    check(s.press(left + tw * 0.9, cy) and s.get_value() == 90 and len(changes) == 1, "an inactive slider still sets its value")
    s.release()
    other = Slider(400, 360, 290, 46, "VOL", Cyber.MAGENTA)
    check(not Slider.press_any(500, 320, None) and not Slider.release_all(None), "group helpers accept a null group")
    Slider.drag_all(0, 0, None)
    Slider.hover_all(0, 0, None)
    Slider.frame_all(0.016, None)
    check(Slider.press_any(other.get_track_left() + other.get_track_width() * 0.5, other.get_center_y(), [s, other])
          and other.is_dragging() and not s.is_dragging(), "press_any picks the slider under the pointer")
    Slider.drag_all(other.get_track_left() + other.get_track_width() * 0.2, 0, [s, other])
    check(other.get_value() == 20 and s.get_value() == 90, "drag_all moves only the grabbed slider")
    check(Slider.release_all([s, other]) and not other.is_dragging(), "release_all ends the drag")
    Slider.frame_all(0.016, [s, other])
    check(s.get_value() == 5, "frame_all syncs bound sliders (got %d)" % s.get_value())
