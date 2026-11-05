package lindefense.ui;

import java.awt.Color;
import java.awt.Font;
import java.util.List;
import lindefense.audio.AudioManager;
import lindefense.audio.AudioSettings;

/**
 * A Sound (speaker icon) or Music (note icon) on/off toggle built on {@link UIButton}. The owner calls
 * {@link #sync()} once per frame so the button always mirrors the persisted setting, including changes made
 * with the M / N hotkeys or on another screen. "Off" is shown dimmed with the icon struck through.
 *
 * <p>{@link #soundVolume} / {@link #musicVolume} build the matching volume {@link Slider} for a channel. Toggle and
 * slider are independent: the toggle mutes or unmutes without changing the level, and the slider sets the level without
 * switching the channel on or off (it is greyed out, keeping its value, while the channel is off).</p>
 */
public final class AudioToggle {
    private final UIButton button;
    private final boolean music;
    private final String label;

    private AudioToggle(boolean music, double x, double y, double w, double h, String label) {
        this.music = music;
        this.label = label;
        Runnable action = () -> {
            AudioManager m = AudioManager.get();
            if (m == null) return;
            if (music) m.toggleMusic(); else m.toggleSound();
        };
        Font f = label == null ? Cyber.mono(Font.BOLD, 11) : Cyber.mono(Font.BOLD, 12);
        button = new UIButton(x, y, w, h, label == null ? "" : label, f, action);
        button.setIcon(music ? Cyber.Kind.NOTE : Cyber.Kind.SPEAKER);
        button.setAccent(music ? Cyber.MAGENTA : Cyber.CYAN);
        sync();
    }

    /** Creates a Sound toggle; {@code label} may be null for an icon-only chip. */
    public static AudioToggle sound(double x, double y, double w, double h, String label) { return new AudioToggle(false, x, y, w, h, label); }
    /** Creates a Music toggle; {@code label} may be null for an icon-only chip. */
    public static AudioToggle music(double x, double y, double w, double h, String label) { return new AudioToggle(true, x, y, w, h, label); }

    /** Creates both toggles and adds their buttons to {@code into} (for hit testing / animation). */
    public static AudioToggle[] pair(double x, double y, double w, double h, double gap, String soundLabel, String musicLabel, List<UIButton> into) {
        AudioToggle s = sound(x, y, w, h, soundLabel), m = music(x + w + gap, y, w, h, musicLabel);
        into.add(s.button); into.add(m.button);
        return new AudioToggle[] { s, m };
    }

    /**
     * Creates a sound-effects volume slider bound to the audio settings: dragging sets the level live, releasing saves
     * it and plays a click at the new level, and the slider greys out while Sound is off. Null-safe without audio.
     */
    public static Slider soundVolume(double x, double y, double w, double h, String caption) { return volumeSlider(false, x, y, w, h, caption); }

    /**
     * Creates a music volume slider bound to the audio settings: dragging sets the level live (the music follows at
     * once), releasing saves it, and the slider greys out while Music is off. Null-safe without audio.
     */
    public static Slider musicVolume(double x, double y, double w, double h, String caption) { return volumeSlider(true, x, y, w, h, caption); }

    private static Slider volumeSlider(boolean music, double x, double y, double w, double h, String caption) {
        Slider s = new Slider(x, y, w, h, caption, music ? Cyber.MAGENTA : Cyber.CYAN);
        s.setOnChange(v -> {
            AudioManager m = AudioManager.get();
            if (m == null) return;
            if (music) m.setMusicVolume(v); else m.setSoundVolume(v);
        });
        s.setOnRelease(v -> {
            AudioManager m = AudioManager.get();
            if (m == null) return;
            m.saveSettings();
            if (!music) m.play(lindefense.audio.Sfx.UI_CLICK);   // AUDIO HOOK: preview the new effects level
        });
        return s.bind(() -> {
            AudioManager m = AudioManager.get();
            if (m == null) return music ? AudioSettings.DEFAULT_MUSIC_VOLUME : AudioSettings.DEFAULT_SOUND_VOLUME;
            return music ? m.getMusicVolume() : m.getSoundVolume();
        }, () -> {
            AudioManager m = AudioManager.get();
            return m != null && !(music ? m.isMusicEnabled() : m.isSoundEnabled());
        });
    }

    public UIButton getButton() { return button; }

    /** Refreshes state visuals from the audio settings. */
    public void sync() {
        AudioManager m = AudioManager.get();
        boolean on = m == null || (music ? m.isMusicEnabled() : m.isSoundEnabled());
        button.setSelected(on);
        button.setIconStruck(!on);
        button.setTextColor(on ? null : Cyber.MUTED);
        if (label != null) button.setText(label + (on ? " ON" : " OFF"));
        button.setAccent(on ? (music ? Cyber.MAGENTA : Cyber.CYAN) : new Color(0x4a5c78));
    }

    /** Syncs several toggles. */
    public static void syncAll(AudioToggle... t) { for (AudioToggle a : t) a.sync(); }
}
