package lindefense.test;

import static lindefense.test.TestKit.*;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.prefs.Preferences;
import lindefense.audio.AudioManager;
import lindefense.audio.AudioSettings;
import lindefense.audio.Sfx;
import lindefense.ui.Cyber;
import lindefense.ui.Slider;

/**
 * Volume sliders: the percentage-to-gain taper and clamping, defaults and persistence (on throw-away preference nodes
 * under {@code lindefense-test/}, never the player's {@code lindefense/audio} node), independence of the mute switches
 * and the volume levels, and the {@link Slider} component's position-to-value mapping and press / drag / release
 * contract. Nothing here opens an audio device or a window.
 */
public final class VolumeTests {
    private VolumeTests() { }

    public static void runAll() {
        run("volume.taperAndClamp", VolumeTests::taperAndClamp);
        run("volume.defaultsAndPersistence", VolumeTests::defaultsAndPersistence);
        run("volume.muteIsIndependent", VolumeTests::muteIsIndependent);
        run("volume.sliderMapping", VolumeTests::sliderMapping);
        run("volume.sliderInput", VolumeTests::sliderInput);
    }

    private static boolean near(double a, double b) { return Math.abs(a - b) < 1e-6; }

    /** A fresh, empty preference node for one test; remove it with {@link #drop}. */
    private static Preferences testNode() {
        return Preferences.userRoot().node("lindefense-test/volume-" + System.nanoTime());
    }

    private static void drop(Preferences node) {
        try { node.removeNode(); node.flush(); } catch (Exception ignored) { /* best effort cleanup */ }
    }

    private static void taperAndClamp() {
        check(AudioSettings.gain(0) == 0f, "0 % is silence");
        check(AudioSettings.gain(100) == 1f, "100 % is unity gain");
        check(near(AudioSettings.gain(50), 0.25), "50 % is a quarter of the amplitude (squared taper), got " + AudioSettings.gain(50));
        check(near(AudioSettings.gain(10), 0.01), "10 % is 1 % amplitude, got " + AudioSettings.gain(10));
        boolean rising = true;
        for (int p = 1; p <= 100; p++) if (!(AudioSettings.gain(p) > AudioSettings.gain(p - 1))) rising = false;
        check(rising, "gain rises strictly from 0 % to 100 %");
        check(AudioSettings.gain(-20) == 0f && AudioSettings.gain(250) == 1f, "out-of-range volumes clamp before the taper");
        check(AudioSettings.clampVolume(-1) == 0 && AudioSettings.clampVolume(101) == 100 && AudioSettings.clampVolume(37) == 37, "clampVolume");
        check(AudioSettings.clampVolume(Integer.MIN_VALUE) == 0 && AudioSettings.clampVolume(Integer.MAX_VALUE) == 100, "clampVolume extremes");
        // the mixer gains: 100 % is exactly the level the mix was tuned at before the sliders existed
        check(AudioManager.soundMixGain(100) == AudioManager.SFX_MIX && near(AudioManager.SFX_MIX, 0.9), "effects at 100 % keep the tuned 0.9 mix gain");
        check(AudioManager.musicMixGain(100) == AudioManager.MUSIC_MIX && near(AudioManager.MUSIC_MIX, 0.6), "music at 100 % keeps the tuned 0.6 mix gain");
        check(near(AudioManager.musicMixGain(50), 0.6 * 0.25) && AudioManager.soundMixGain(0) == 0f, "mix gain = tuned level x taper");
    }

    private static void defaultsAndPersistence() {
        Preferences node = testNode();
        try {
            AudioSettings a = new AudioSettings(node);
            check(a.getSoundVolume() == AudioSettings.DEFAULT_SOUND_VOLUME && a.getMusicVolume() == AudioSettings.DEFAULT_MUSIC_VOLUME,
                "fresh store uses the default volumes");
            check(AudioSettings.DEFAULT_SOUND_VOLUME == 100 && AudioSettings.DEFAULT_MUSIC_VOLUME == 100, "defaults are 100 % (today's loudness)");
            AudioSettings mem = new AudioSettings(null);
            check(mem.getSoundVolume() == 100 && mem.getMusicVolume() == 100 && mem.isSound() && mem.isMusic(), "in-memory settings use the defaults");

            a.setSoundVolume(35);
            a.setMusicVolume(140);
            check(a.getSoundVolume() == 35 && a.getMusicVolume() == 100, "setters clamp (140 -> 100)");
            a.setMusicVolume(-9);
            check(a.getMusicVolume() == 0, "setters clamp (-9 -> 0)");
            a.setMusicVolume(62);
            a.flush();
            AudioSettings b = new AudioSettings(node);
            check(b.getSoundVolume() == 35 && b.getMusicVolume() == 62, "volumes round-trip through the store (got " + b.getSoundVolume() + " / " + b.getMusicVolume() + ")");
            check(b.isSound() && b.isMusic(), "volume changes leave the switches alone");

            // garbage in the store: out-of-range ints clamp, unparsable values fall back to the default
            node.putInt(AudioSettings.KEY_SOUND_VOLUME, 999);
            node.put(AudioSettings.KEY_MUSIC_VOLUME, "loud");
            AudioSettings c = new AudioSettings(node);
            check(c.getSoundVolume() == 100, "stored 999 reads back clamped to 100");
            check(c.getMusicVolume() == AudioSettings.DEFAULT_MUSIC_VOLUME, "unparsable stored volume falls back to the default");

            // the manager reads and writes the same keys
            node.putInt(AudioSettings.KEY_SOUND_VOLUME, 20);
            node.putInt(AudioSettings.KEY_MUSIC_VOLUME, 45);
            AudioManager m = new AudioManager(node, new File("no-such-dir"), false);
            check(m.getSoundVolume() == 20 && m.getMusicVolume() == 45, "manager reads persisted volumes");
            m.setSoundVolume(75);
            m.setMusicVolume(5);
            m.saveSettings();
            AudioSettings d = new AudioSettings(node);
            check(d.getSoundVolume() == 75 && d.getMusicVolume() == 5, "manager volume changes persist");
        } finally {
            drop(node);
        }
    }

    private static void muteIsIndependent() {
        Preferences node = testNode();
        try {
            AudioManager m = new AudioManager(node, new File("no-such-dir"), false);
            m.setMusicVolume(40);
            m.setSoundVolume(70);
            check(near(m.getEffectiveMusicGain(), AudioManager.musicMixGain(40)), "music heard at its volume while on");

            m.toggleMusic();                       // mute (the M hotkey / MUSIC toggle path)
            check(!m.isMusicEnabled() && m.getMusicVolume() == 40, "muting music keeps its volume");
            check(m.getEffectiveMusicGain() == 0f, "muted music is silent");
            check(m.isSoundEnabled() && m.getSoundVolume() == 70, "muting music leaves sound alone");
            m.setMusicVolume(90);                  // drag the slider while muted: sets the level only
            check(!m.isMusicEnabled() && m.getMusicVolume() == 90, "a volume change while muted does not unmute");
            m.toggleMusic();                       // unmute
            check(m.isMusicEnabled() && m.getMusicVolume() == 90, "unmuting restores the (latest) level");
            check(near(m.getEffectiveMusicGain(), AudioManager.musicMixGain(90)), "music heard at the restored level");

            m.toggleSound();                       // the N hotkey / SOUND toggle path
            check(!m.isSoundEnabled() && m.getSoundVolume() == 70 && m.getEffectiveSoundGain() == 0f, "muting sound keeps its volume");
            check(!m.play(Sfx.UI_CLICK), "no effects while sound is muted, whatever the volume");
            m.toggleSound();
            check(m.isSoundEnabled() && m.getSoundVolume() == 70, "unmuting sound restores its level");
            m.setSoundVolume(0);
            check(m.isSoundEnabled(), "volume 0 is not the same as switching sound off");
            check(m.getEffectiveSoundGain() == 0f, "0 % is silent");

            AudioSettings persisted = new AudioSettings(node);
            check(persisted.isMusic() && persisted.isSound() && persisted.getMusicVolume() == 90 && persisted.getSoundVolume() == 0,
                "switches and volumes persist side by side");
        } finally {
            drop(node);
        }
    }

    private static void sliderMapping() {
        check(Slider.valueAt(100, 100, 200) == 0 && Slider.valueAt(300, 100, 200) == 100 && Slider.valueAt(200, 100, 200) == 50, "track ends and middle");
        check(Slider.valueAt(150, 100, 200) == 25 && Slider.valueAt(250.9, 100, 200) == 75, "quarter points (rounded)");
        check(Slider.valueAt(-50, 100, 200) == 0 && Slider.valueAt(9999, 100, 200) == 100, "positions off the track clamp to 0 / 100");
        check(Slider.valueAt(101, 100, 200) == 1 && Slider.valueAt(100.9, 100, 200) == 0, "rounds to the nearest percent");
        check(Slider.valueAt(5, 0, 0) == 0 && Slider.valueAt(5, 0, -3) == 0 && Slider.valueAt(Double.NaN, 0, 100) == 0, "degenerate input gives 0");
        boolean monotone = true;
        int last = -1;
        for (double x = 90; x <= 310; x += 0.5) { int v = Slider.valueAt(x, 100, 200); if (v < last) monotone = false; last = v; }
        check(monotone, "value never decreases left to right");

        Slider s = new Slider(400, 300, 290, 46, "VOL", Cyber.CYAN);
        check(s.getTrackWidth() > 120 && s.getTrackLeft() > 400 && s.getTrackLeft() + s.getTrackWidth() < 400 + 290, "track sits inside the box (w " + s.getTrackWidth() + ")");
        check(s.valueAtX(s.getTrackLeft()) == 0 && s.valueAtX(s.getTrackLeft() + s.getTrackWidth()) == 100, "instance mapping uses the absolute track");
        for (int v : new int[] { 0, 1, 33, 50, 99, 100 }) {
            s.setValue(v);
            check(s.getValue() == v && s.valueAtX(s.getKnobX()) == v, "knob position maps back to its value (" + v + ")");
        }
        s.setValue(-5);
        check(s.getValue() == 0, "setValue clamps low");
        s.setValue(300);
        check(s.getValue() == 100, "setValue clamps high");
        // same slider moved elsewhere: the mapping follows its logical position (it never sees window pixels)
        s.setLocation(10, 900);
        check(s.valueAtX(s.getTrackLeft() + s.getTrackWidth() / 2) == 50, "mapping follows the slider's logical position");
        Slider bare = new Slider(0, 0, 290, 46, null, Cyber.MAGENTA);
        check(bare.getTrackWidth() > s.getTrackWidth(), "no caption leaves a longer track");
    }

    private static void sliderInput() {
        Slider s = new Slider(400, 300, 290, 46, "VOL", Cyber.CYAN);
        List<Integer> changes = new ArrayList<>(), releases = new ArrayList<>();
        s.setOnChange(changes::add);
        s.setOnRelease(releases::add);
        double cy = s.getCenterY(), left = s.getTrackLeft(), tw = s.getTrackWidth();

        check(!s.press(399, cy) && !s.press(500, 299) && !s.press(500, 347), "presses outside the box are not taken");
        check(!s.isDragging() && changes.isEmpty(), "outside presses change nothing");
        check(!s.release() && releases.isEmpty(), "release without a drag does nothing");

        // click on the track: jumps there and starts a drag
        check(s.press(left + tw * 0.25, cy) && s.isDragging(), "press on the track is taken and starts a drag");
        check(s.getValue() == 25 && changes.size() == 1 && changes.get(0) == 25, "track click jumps to the clicked value");
        s.drag(left + tw * 0.6, cy + 80);      // the pointer may leave the box while dragging
        check(s.getValue() == 60 && changes.get(changes.size() - 1) == 60, "drag follows the pointer, even outside the box");
        s.drag(left - 500, cy);
        check(s.getValue() == 0, "dragging past the left end clamps to 0");
        s.drag(left + tw + 500, cy);
        check(s.getValue() == 100, "dragging past the right end clamps to 100");
        int before = changes.size();
        s.drag(left + tw + 900, cy);
        check(changes.size() == before, "no change callback when the value does not change");
        check(s.release() && !s.isDragging() && releases.size() == 1 && releases.get(0) == 100, "release ends the drag and reports the final value once");
        s.drag(left, cy);
        check(s.getValue() == 100, "drags after release are ignored");

        // grabbing the knob off-centre does not make it jump
        s.setValue(40);
        changes.clear();
        double kx = s.getKnobX();
        check(s.press(kx + 4, cy) && s.getValue() == 40 && changes.isEmpty(), "grabbing the knob keeps its value");
        s.drag(kx + 4 + tw * 0.1, cy);
        check(s.getValue() == 50, "knob moves by the drag distance (got " + s.getValue() + ")");
        s.release();

        // caption / readout are inside the box but not the track: taken, no change
        s.setValue(70);
        changes.clear();
        check(s.press(s.getX() + 3, cy) && !s.isDragging() && s.getValue() == 70 && changes.isEmpty(), "press on the caption is swallowed without a change");
        check(s.press(s.getX() + s.getW() - 3, cy) && !s.isDragging() && s.getValue() == 70, "press on the readout is swallowed without a change");

        // binding: sync pulls the model, but never fights an active drag
        int[] model = { 15 };
        boolean[] muted = { true };
        s.bind(() -> model[0], () -> muted[0]);
        check(s.getValue() == 15 && s.isInactive(), "bind syncs value and inactive state at once");
        model[0] = 80; muted[0] = false;
        s.sync();
        check(s.getValue() == 80 && !s.isInactive(), "sync follows the model");
        s.press(left + tw * 0.3, cy);
        model[0] = 5;
        s.sync();
        check(s.getValue() == 30, "sync does not move the knob while it is being dragged");
        s.release();
        s.sync();
        check(s.getValue() == 5, "sync resumes after release");

        // inactive (muted) sliders still work: they set the level, the owner decides what that means
        muted[0] = true;
        s.sync();
        changes.clear();
        check(s.press(left + tw * 0.9, cy) && s.getValue() == 90 && changes.size() == 1, "an inactive slider still sets its value");
        s.release();

        // group helpers are null-safe and route to the right slider
        Slider other = new Slider(400, 360, 290, 46, "VOL", Cyber.MAGENTA);
        Slider[] none = null;
        check(!Slider.pressAny(500, 320, none) && !Slider.releaseAll(none), "group helpers accept a null group");
        Slider.dragAll(0, 0, none);
        Slider.hoverAll(0, 0, none);
        Slider.frameAll(0.016, none);
        check(Slider.pressAny(other.getTrackLeft() + other.getTrackWidth() * 0.5, other.getCenterY(), s, other) && other.isDragging() && !s.isDragging(), "pressAny picks the slider under the pointer");
        Slider.dragAll(other.getTrackLeft() + other.getTrackWidth() * 0.2, 0, s, other);
        check(other.getValue() == 20 && s.getValue() == 90, "dragAll moves only the grabbed slider");
        check(Slider.releaseAll(s, other) && !other.isDragging(), "releaseAll ends the drag");
        Slider.frameAll(0.016, s, other);
        check(s.getValue() == 5, "frameAll syncs bound sliders (got " + s.getValue() + ")");
    }
}
