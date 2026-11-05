package lindefense.audio;

import java.io.File;
import java.util.EnumSet;
import java.util.Set;
import java.util.prefs.Preferences;
import lindefense.combat.VisualEvent;

/**
 * Facade for all game audio: sound effects (preloaded, 12-voice pool, per-sound throttling, slight random
 * pitch/volume variation), streamed music with crossfades, the persisted Sound / Music switches and the persisted
 * Sound / Music volume levels (see {@link AudioSettings}).
 *
 * <p>Switches and volumes are independent: a switched-off channel is silent but keeps its volume, and changing a volume
 * never switches a channel on or off. A volume scales its channel in the mixer by {@link #soundMixGain(int)} /
 * {@link #musicMixGain(int)}; 100 % is the level the mix was tuned at.</p>
 *
 * <p>Everything is best effort. With no audio device, a headless run, missing or unsupported files, the manager
 * logs one line (device failures only) and stays silent; nothing here ever throws into the game. Game code
 * calls the static {@link #sfx(Sfx)} / {@link #event(VisualEvent)} hooks, which are no-ops until
 * {@link #install()} has been called (so headless simulations and tests pay nothing).</p>
 */
public final class AudioManager {
    /** Seconds for music crossfades between contexts. */
    public static final float CROSSFADE = 1.5f;
    /** Mixer gain of the sound effects at 100 % volume (the level the effects were tuned at). */
    public static final float SFX_MIX = 0.9f;
    /** Mixer gain of the music at 100 % volume (the level the music was tuned at). */
    public static final float MUSIC_MIX = 0.6f;

    private static volatile AudioManager live;

    private final AudioSettings settings;
    private final File sfxDir, musicDir;
    private final boolean openDevice;
    private final Throttle throttle = new Throttle();
    private final SfxBank bank = new SfxBank();
    private final Mixer mixer = new Mixer();
    private final int[] accepted = new int[Sfx.values().length];
    private final Set<Track> available = EnumSet.noneOf(Track.class);
    private final Set<Track> reportedBad = EnumSet.noneOf(Track.class);
    private volatile boolean ready;
    private volatile boolean disabled;
    private boolean loggedFailure;
    private Track desired;
    private Track playing;
    private long rng = 0x9E3779B97F4A7C15L;

    /**
     * @param prefs      preference node for the switches (null = in-memory only)
     * @param assetsRoot directory containing {@code sfx/} and {@code music/}
     * @param openDevice false to never touch the audio device (tests, headless)
     */
    public AudioManager(Preferences prefs, File assetsRoot, boolean openDevice) {
        this.settings = new AudioSettings(prefs);
        this.sfxDir = new File(assetsRoot, "sfx");
        this.musicDir = new File(assetsRoot, "music");
        this.openDevice = openDevice;
        scanMusic();
    }

    // ------------------------------------------------------------------ global access
    /** Creates the game-wide manager (assets located by {@link lindefense.Assets}), starts loading in the background. */
    public static synchronized AudioManager install() {
        if (live == null) {
            File root = lindefense.Assets.file("assets");   // works from any working directory (see lindefense.Assets)
            boolean headless = java.awt.GraphicsEnvironment.isHeadless() || Boolean.getBoolean("lindefense.nosound");
            // scripted demo runs (DemoDriver) drag the volume sliders: they keep audio settings in memory, never in the player's prefs
            Preferences prefs = System.getProperty("lindefense.demo") != null ? null : Preferences.userRoot().node("lindefense/audio");
            AudioManager m = new AudioManager(prefs, root, !headless);
            m.init();
            live = m;
        }
        return live;
    }

    /** The installed manager, or null before {@link #install()}. */
    public static AudioManager get() { return live; }

    /** AUDIO HOOK entry: plays an effect if audio is installed. */
    public static void sfx(Sfx s) {
        AudioManager m = live;
        if (m != null) m.play(s);
    }

    /** AUDIO HOOK entry: title / how-to-play / map select music. */
    public static void menuMusic() {
        AudioManager m = live;
        if (m != null) m.setMusic(new Track[] { Track.MENU });
    }

    /** AUDIO HOOK entry: plays the effect that matches a simulation event. */
    public static void event(VisualEvent ev) {
        AudioManager m = live;
        if (m == null || !m.ready) return;
        Sfx s = SfxFamilies.forEvent(ev);
        if (s != null) m.play(s);
    }

    // ------------------------------------------------------------------ lifecycle
    /** Loads effects and opens the output on a background thread. Safe to call once; never throws. */
    public void init() {
        if (!openDevice) return;
        Thread t = new Thread(() -> {
            try {
                bank.load(sfxDir);
                if (!mixer.open()) { fail("no audio output device available"); return; }
                applySettings();
                ready = true;
                synchronized (this) { applyMusic(CROSSFADE); }
            } catch (Throwable e) {
                fail("audio init failed: " + e);
            }
        }, "lindefense-audio-init");
        t.setDaemon(true);
        t.start();
    }

    private synchronized void fail(String why) {
        disabled = true; ready = false;
        if (!loggedFailure) { loggedFailure = true; System.err.println("[audio] disabled: " + why); }
    }

    private void applySettings() { mixer.setVolumes(soundMixGain(settings.getSoundVolume()), musicMixGain(settings.getMusicVolume())); }

    // ------------------------------------------------------------------ switches
    public boolean isSoundEnabled() { return settings.isSound(); }
    public boolean isMusicEnabled() { return settings.isMusic(); }
    /** True if an output device is open and working. */
    public boolean isReady() { return ready; }
    public boolean isDisabled() { return disabled; }

    public void setSoundEnabled(boolean on) {
        settings.setSound(on);
        if (!on && ready) mixer.clearVoices();
    }

    public synchronized void setMusicEnabled(boolean on) {
        settings.setMusic(on);
        applyMusic(CROSSFADE);
    }

    public void toggleSound() { setSoundEnabled(!settings.isSound()); if (settings.isSound()) play(Sfx.UI_CLICK); }
    public void toggleMusic() { setMusicEnabled(!settings.isMusic()); }

    // ------------------------------------------------------------------ volumes
    /** Sound-effects volume in percent (0-100). Kept while the Sound switch is off. */
    public int getSoundVolume() { return settings.getSoundVolume(); }
    /** Music volume in percent (0-100). Kept while the Music switch is off. */
    public int getMusicVolume() { return settings.getMusicVolume(); }

    /**
     * Sets the sound-effects volume (clamped to 0-100) and applies it to the mix at once. Does not touch the Sound switch.
     * The value is cached for the preference store; call {@link #saveSettings()} when the slider is released.
     */
    public void setSoundVolume(int percent) { settings.setSoundVolume(percent); applySettings(); }

    /** Sets the music volume (clamped to 0-100) and applies it at once. Does not touch the Music switch; see {@link #setSoundVolume}. */
    public void setMusicVolume(int percent) { settings.setMusicVolume(percent); applySettings(); }

    /** Writes cached settings (the volume levels) to the preference store now. Best effort; never throws. */
    public void saveSettings() { settings.flush(); }

    /** Mixer gain of the sound effects at a volume: {@link #SFX_MIX} times {@link AudioSettings#gain(int)}. */
    public static float soundMixGain(int percent) { return SFX_MIX * AudioSettings.gain(percent); }
    /** Mixer gain of the music at a volume: {@link #MUSIC_MIX} times {@link AudioSettings#gain(int)}. */
    public static float musicMixGain(int percent) { return MUSIC_MIX * AudioSettings.gain(percent); }

    /** Gain the effects are heard at right now: 0 while Sound is off, otherwise {@link #soundMixGain(int)} of the volume. */
    public float getEffectiveSoundGain() { return settings.isSound() ? soundMixGain(settings.getSoundVolume()) : 0f; }
    /** Gain the music is heard at right now: 0 while Music is off, otherwise {@link #musicMixGain(int)} of the volume. */
    public float getEffectiveMusicGain() { return settings.isMusic() ? musicMixGain(settings.getMusicVolume()) : 0f; }

    // ------------------------------------------------------------------ effects
    /** Plays an effect. Returns true if it was accepted (sound on and not throttled). */
    public boolean play(Sfx s) {
        if (!settings.isSound() || disabled) return false;
        if (!throttle.allow(s, System.nanoTime())) return false;
        accepted[s.ordinal()]++;
        if (ready && settings.getSoundVolume() > 0) {   // at 0 % there is nothing to hear: skip the mixer
            float[] d = bank.get(s);
            if (d != null) {
                float gain = s.gain, pitch = 1f;
                if (s.vary) {
                    rng ^= rng << 13; rng ^= rng >>> 7; rng ^= rng << 17;
                    float a = ((rng >>> 40) & 0xffff) / 65535f, b = ((rng >>> 20) & 0xffff) / 65535f;
                    pitch = 0.94f + 0.12f * a;
                    gain *= 0.85f + 0.15f * b;
                }
                mixer.play(d, gain, pitch, s.priority);
            }
        }
        return true;
    }

    /** Number of plays of {@code s} that passed the throttle (for tests / diagnostics). */
    public int getAcceptedCount(Sfx s) { return accepted[s.ordinal()]; }

    /** Number of effect files that loaded. */
    public int getLoadedSfxCount() { return bank.loadedCount(); }

    // ------------------------------------------------------------------ music
    private void scanMusic() {
        for (Track t : Track.values()) if (new File(musicDir, t.file + ".wav").isFile()) available.add(t);
    }

    /** True if the track file was found at start-up. */
    public boolean hasTrack(Track t) { return available.contains(t); }

    /** The track currently requested (after fallbacks), or null for silence. */
    public synchronized Track getDesiredTrack() { return desired; }

    /**
     * Requests the first available track of {@code prefs} (null/empty or none available = silence).
     * Does nothing if that track is already the current one, so tracks are not restarted between waves.
     */
    public synchronized void setMusic(Track[] prefs) {
        Track pick = null;
        if (prefs != null) for (Track t : prefs) if (available.contains(t) && !reportedBad.contains(t)) { pick = t; break; }
        if (pick == desired) return;
        desired = pick;
        applyMusic(CROSSFADE);
    }

    private void applyMusic(float fade) {
        if (!ready) return;
        Track want = settings.isMusic() ? desired : null;
        if (want == playing) return;
        playing = want;
        if (want == null) { mixer.stopMusic(fade); return; }
        final Track t = want;
        mixer.playMusic(new MusicStream(new File(musicDir, t.file + ".wav"), t.loop, () -> badTrack(t)), fade);
    }

    private synchronized void badTrack(Track t) {
        if (reportedBad.add(t)) System.err.println("[audio] cannot play music/" + t.file + ".wav (unsupported or unreadable); skipping");
    }
}
