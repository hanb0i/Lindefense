package lindefense.audio;

import java.util.prefs.Preferences;

/**
 * The persisted audio settings, stored with {@link Preferences}: two independent switches (Sound = sound effects,
 * Music), both on by default, and one volume level per channel in percent (0-100). Muting is its own flag, so
 * switching a channel off and on again keeps its volume. Persistence failures are ignored (the settings still work in
 * memory).
 *
 * <p>A volume maps to a mix gain through {@link #gain(int)}, a squared (perceptual) taper: 100 % is the level the game's
 * mix was tuned at, and the defaults are 100 %, so the game sounds exactly as it did before the volume sliders existed
 * until the player moves one.</p>
 *
 * <p>Switch changes are written to the backing store at once. Volume changes are only cached (they arrive many times a
 * second while a slider is dragged); call {@link #flush()} when the drag ends. The preference store also writes cached
 * changes by itself, periodically and at exit.</p>
 */
public final class AudioSettings {
    static final String KEY_SOUND = "sound";
    static final String KEY_MUSIC = "music";
    /** Preference key of the sound-effects volume (an int percentage). */
    public static final String KEY_SOUND_VOLUME = "soundVolume";
    /** Preference key of the music volume (an int percentage). */
    public static final String KEY_MUSIC_VOLUME = "musicVolume";
    /** Sound-effects volume in percent when nothing is saved yet (100 % = the tuned mix level). */
    public static final int DEFAULT_SOUND_VOLUME = 100;
    /** Music volume in percent when nothing is saved yet (100 % = the tuned mix level). */
    public static final int DEFAULT_MUSIC_VOLUME = 100;

    private final Preferences node;
    private volatile boolean sound;
    private volatile boolean music;
    private volatile int soundVolume;
    private volatile int musicVolume;

    /** Reads the settings from {@code node} (null = in memory only, all defaults). */
    public AudioSettings(Preferences node) {
        this.node = node;
        boolean s = true, m = true;
        int sv = DEFAULT_SOUND_VOLUME, mv = DEFAULT_MUSIC_VOLUME;
        try {
            if (node != null) {
                s = node.getBoolean(KEY_SOUND, true);
                m = node.getBoolean(KEY_MUSIC, true);
                sv = node.getInt(KEY_SOUND_VOLUME, DEFAULT_SOUND_VOLUME);
                mv = node.getInt(KEY_MUSIC_VOLUME, DEFAULT_MUSIC_VOLUME);
            }
        } catch (RuntimeException ignored) {
            // unreadable preference store: use defaults
        }
        sound = s; music = m;
        soundVolume = clampVolume(sv); musicVolume = clampVolume(mv);
    }

    public boolean isSound() { return sound; }
    public boolean isMusic() { return music; }

    public void setSound(boolean on) { sound = on; save(KEY_SOUND, on); }
    public void setMusic(boolean on) { music = on; save(KEY_MUSIC, on); }

    /** Sound-effects volume in percent (0-100), independent of the Sound switch. */
    public int getSoundVolume() { return soundVolume; }
    /** Music volume in percent (0-100), independent of the Music switch. */
    public int getMusicVolume() { return musicVolume; }

    /** Sets the sound-effects volume (clamped to 0-100); cached for the store, see {@link #flush()}. */
    public void setSoundVolume(int percent) { soundVolume = clampVolume(percent); put(KEY_SOUND_VOLUME, soundVolume); }
    /** Sets the music volume (clamped to 0-100); cached for the store, see {@link #flush()}. */
    public void setMusicVolume(int percent) { musicVolume = clampVolume(percent); put(KEY_MUSIC_VOLUME, musicVolume); }

    /** Writes cached changes (the volume levels) to the backing store now. Best effort; never throws. */
    public void flush() {
        if (node == null) return;
        try {
            node.flush();
        } catch (Exception ignored) {
            // read-only store; keep the in-memory values
        }
    }

    /** Clamps a volume percentage to 0-100. */
    public static int clampVolume(int percent) { return Math.max(0, Math.min(100, percent)); }

    /**
     * Linear gain factor (0-1) for a volume percentage: {@code (percent / 100)^2}, after clamping. The squared taper makes
     * equal slider steps sound like roughly equal loudness steps (50 % is about -12 dB, 10 % about -40 dB), where a
     * linear one would barely change until the bottom of the slider. 0 % is silence and 100 % is unity.
     */
    public static float gain(int percent) {
        float f = clampVolume(percent) / 100f;
        return f * f;
    }

    private void save(String key, boolean v) {
        if (node == null) return;
        try {
            node.putBoolean(key, v);
            node.flush();
        } catch (Exception ignored) {
            // read-only store; keep the in-memory value
        }
    }

    private void put(String key, int v) {
        if (node == null) return;
        try {
            node.putInt(key, v);
        } catch (Exception ignored) {
            // unusable store; keep the in-memory value
        }
    }
}
