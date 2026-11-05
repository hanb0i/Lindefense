package lindefense.ui;

/**
 * HIGH-quality cosmetic camera shake (see {@link GraphicsSettings.Quality#screenShake}). Impacts add "trauma" (0-1)
 * that decays over time; the offset grows with trauma squared, so small kicks are subtle and big ones punchy, and it
 * follows smooth sine noise rather than random jumps. The offset is in logical px and only moves the drawing of the
 * battlefield, never the simulation or mouse picking.
 */
final class ScreenShake {
    /** Largest offset at full trauma, logical px. */
    static final double MAX_OFFSET = 7;
    /** Trauma lost per second. */
    static final double DECAY = 1.8;
    private double trauma, time;

    /** Adds trauma (clamped to 1); ignored unless the preset enables screen shake. */
    void kick(double amount) {
        if (amount <= 0 || !GraphicsSettings.get().quality().screenShake) return;
        trauma = Math.min(1, trauma + amount);
    }

    void update(double dt) {
        time += dt;
        trauma = Math.max(0, trauma - DECAY * dt);
    }

    double trauma() { return trauma; }
    double offsetX() { double s = trauma * trauma; return s == 0 ? 0 : MAX_OFFSET * s * Math.sin(time * 47.0) * Math.cos(time * 13.0); }
    double offsetY() { double s = trauma * trauma; return s == 0 ? 0 : MAX_OFFSET * s * Math.sin(time * 39.0 + 1.3); }
}
