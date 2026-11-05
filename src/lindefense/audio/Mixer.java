package lindefense.audio;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.LockSupport;
import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.SourceDataLine;

/**
 * Software mixer on one background daemon thread feeding a single {@link SourceDataLine} (44.1 kHz, 16-bit,
 * stereo). Holds a small voice pool for sound effects (at most {@link #MAX_VOICES} at once) and up to a few
 * crossfading music slots. The game thread only enqueues small commands; it never touches the line.
 * The thread sleeps (and the line is stopped) when nothing is playing.
 */
final class Mixer implements Runnable {
    static final int RATE = 44100;
    static final int MAX_VOICES = 12;
    private static final int BLOCK = 512;
    private static final int MAX_PENDING = 40;

    /** One playing effect. */
    private static final class Voice {
        final float[] data; final float gain; final double step; final int priority; double pos;
        Voice(float[] data, float gain, double step, int priority) { this.data = data; this.gain = gain; this.step = step; this.priority = priority; }
    }

    /** One music stream with its fade state. */
    private static final class Slot {
        final MusicStream stream; float gain; float target; float perFrame;
        Slot(MusicStream stream, float gain) { this.stream = stream; this.gain = gain; }
    }

    private final ConcurrentLinkedQueue<Object> commands = new ConcurrentLinkedQueue<>();
    private final AtomicInteger pending = new AtomicInteger();
    private final Voice[] voices = new Voice[MAX_VOICES];
    private final List<Slot> slots = new ArrayList<>();
    private final float[] accL = new float[BLOCK], accR = new float[BLOCK], tmp = new float[BLOCK * 2];
    private final byte[] out = new byte[BLOCK * 4];
    private SourceDataLine line;
    private Thread thread;
    private volatile boolean running;
    private volatile float sfxVolume = 0.9f, musicVolume = 0.6f;
    /** Volumes the last mixed block ended at (mixer thread only); each block ramps from these to the targets, so a dragged slider never clicks. */
    private float sfxNow = 0.9f, musicNow = 0.6f;

    /** Opens the output line and starts the thread. Returns false (never throws) if there is no usable device. */
    boolean open() {
        try {
            AudioFormat fmt = new AudioFormat(RATE, 16, 2, true, false);
            DataLine.Info info = new DataLine.Info(SourceDataLine.class, fmt);
            if (!AudioSystem.isLineSupported(info)) return false;
            line = (SourceDataLine) AudioSystem.getLine(info);
            line.open(fmt, 4096 * 4);
        } catch (Exception | LinkageError e) {
            line = null;
            return false;
        }
        running = true;
        thread = new Thread(this, "lindefense-audio-mixer");
        thread.setDaemon(true);
        thread.start();
        return true;
    }

    // ------------------------------------------------------------------ commands (any thread)
    /** Queues an effect. Dropped when the queue is backed up. */
    void play(float[] data, float gain, float pitch, int priority) {
        if (data == null || pending.get() >= MAX_PENDING) return;
        pending.incrementAndGet();
        commands.add(new Voice(data, gain, pitch, priority));
        LockSupport.unpark(thread);
    }

    /** Starts a new music stream, fading all current music out and the new one in over {@code fade} seconds. */
    void playMusic(MusicStream s, float fade) {
        commands.add(new Object[] { s, fade });
        LockSupport.unpark(thread);
    }

    /** Fades all music out. */
    void stopMusic(float fade) {
        commands.add(Float.valueOf(fade));
        LockSupport.unpark(thread);
    }

    /** Silences all sound effects immediately. */
    void clearVoices() {
        commands.add("clear");
        LockSupport.unpark(thread);
    }

    /** Sets the channel gains (any thread). Changes are ramped over one block (about 12 ms) so they never click. */
    void setVolumes(float sfx, float music) { sfxVolume = sfx; musicVolume = music; }

    // ------------------------------------------------------------------ mixer thread
    @Override public void run() {
        boolean started = false;
        try {
            while (running) {
                drainCommands();
                if (!active()) {
                    if (started) { line.stop(); line.flush(); started = false; }
                    sfxNow = sfxVolume; musicNow = musicVolume;   // nothing audible: jump straight to the current levels
                    LockSupport.parkNanos(25_000_000L);
                    continue;
                }
                if (!started) { line.start(); started = true; }
                mixBlock();
                line.write(out, 0, out.length);
            }
        } catch (Throwable t) {
            running = false;     // device died: give up quietly
        }
    }

    private boolean active() {
        if (!slots.isEmpty()) return true;
        for (Voice v : voices) if (v != null) return true;
        return false;
    }

    private void drainCommands() {
        Object c;
        while ((c = commands.poll()) != null) {
            if (c instanceof Voice) { pending.decrementAndGet(); addVoice((Voice) c); }
            else if (c instanceof Object[]) {
                Object[] a = (Object[]) c;
                fadeAll(((Float) a[1]));
                Slot s = new Slot((MusicStream) a[0], 0);
                s.target = 1;
                s.perFrame = 1f / Math.max(1, ((Float) a[1]) * RATE);
                slots.add(s);
            } else if (c instanceof Float) fadeAll((Float) c);
            else for (int i = 0; i < voices.length; i++) voices[i] = null;
        }
    }

    private void fadeAll(float fade) {
        for (Slot s : slots) { s.target = 0; s.perFrame = 1f / Math.max(1, fade * RATE); }
    }

    private void addVoice(Voice v) {
        int victim = -1;
        for (int i = 0; i < voices.length; i++) {
            if (voices[i] == null) { voices[i] = v; return; }
            if (voices[i].priority <= v.priority && (victim < 0 || voices[i].priority < voices[victim].priority
                    || voices[i].priority == voices[victim].priority && voices[i].pos > voices[victim].pos)) victim = i;
        }
        if (victim >= 0) voices[victim] = v;     // steal the lowest-priority (then furthest-along) voice
    }

    private void mixBlock() {
        java.util.Arrays.fill(accL, 0f);
        java.util.Arrays.fill(accR, 0f);
        // channel volumes ramp linearly across the block from where the last block ended to the current targets
        float sv0 = sfxNow, sv1 = sfxVolume, svStep = (sv1 - sv0) / BLOCK;
        float mv0 = musicNow, mv1 = musicVolume, mvStep = (mv1 - mv0) / BLOCK;
        for (int vi = 0; vi < voices.length; vi++) {
            Voice v = voices[vi];
            if (v == null) continue;
            float[] d = v.data;
            double pos = v.pos;
            float g = v.gain * sv0, gStep = v.gain * svStep;
            int i = 0;
            for (; i < BLOCK; i++) {
                int k = (int) pos;
                if (k >= d.length - 1) break;
                float fr = (float) (pos - k);
                float s = (d[k] + (d[k + 1] - d[k]) * fr) * g;
                accL[i] += s; accR[i] += s;
                pos += v.step;
                g += gStep;
            }
            v.pos = pos;
            if (i < BLOCK) voices[vi] = null;
        }
        for (int si = slots.size() - 1; si >= 0; si--) {
            Slot s = slots.get(si);
            if (s.stream.isFailed() || s.stream.isFinished()) { s.stream.close(); slots.remove(si); continue; }
            s.stream.read(tmp, BLOCK);
            float g = s.gain, mv = mv0;
            for (int i = 0; i < BLOCK; i++) {
                if (g < s.target) g = Math.min(s.target, g + s.perFrame);
                else if (g > s.target) g = Math.max(s.target, g - s.perFrame);
                accL[i] += tmp[i * 2] * g * mv;
                accR[i] += tmp[i * 2 + 1] * g * mv;
                mv += mvStep;
            }
            s.gain = g;
            if (g <= 0 && s.target <= 0) { s.stream.close(); slots.remove(si); }
        }
        sfxNow = sv1; musicNow = mv1;
        for (int i = 0; i < BLOCK; i++) {
            int l = (int) (soft(accL[i]) * 32767f), r = (int) (soft(accR[i]) * 32767f);
            out[i * 4] = (byte) l; out[i * 4 + 1] = (byte) (l >> 8);
            out[i * 4 + 2] = (byte) r; out[i * 4 + 3] = (byte) (r >> 8);
        }
    }

    /** Gentle limiter: linear below 0.8, smoothly saturating above, never beyond +-1. */
    private static float soft(float x) {
        float a = Math.abs(x);
        if (a <= 0.8f) return x;
        float y = 0.8f + 0.2f * (float) Math.tanh((a - 0.8f) / 0.2f);
        return x < 0 ? -y : y;
    }
}
