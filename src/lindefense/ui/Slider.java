package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import java.awt.Color;
import java.awt.Font;
import java.util.function.BooleanSupplier;
import java.util.function.IntConsumer;
import java.util.function.IntSupplier;

/**
 * Horizontal percentage slider (0-100 %) in the cyberpunk style: a chamfered dark-glass box like {@link UIButton}
 * holding an optional caption, a notched track filled with the accent colour up to the value, a draggable knob and a
 * percentage readout. Drag the knob, or click anywhere on the track to jump there and keep dragging. The box brightens
 * on hover and while dragging, and it can be shown {@link #setInactive inactive} (greyed, for example while its audio
 * channel is muted) without losing its value.
 *
 * <p>Like the buttons, a slider does no event handling of its own: the owning screen forwards mouse events in logical
 * coordinates to {@link #press}, {@link #drag}, {@link #release} and {@link #setHover} (or to the null-safe group
 * helpers such as {@link #pressAny}), so it works at any window size. Coordinates are absolute logical coordinates:
 * the slider's parent compound must sit at the origin, as the screens' overlays and panels do (the same contract as
 * {@link UIButton#hit}).</p>
 *
 * <p>User changes reach the model through {@link #setOnChange} (every change while dragging) and {@link #setOnRelease}
 * (once, when the drag ends). {@link #bind} makes {@link #sync()} pull the shown value and the inactive state back from
 * the model once per frame, so changes made elsewhere (another screen, a hotkey) show up too.</p>
 */
public final class Slider extends GCompound {
    private static final long serialVersionUID = 1L;

    private static final Color FILL = new Color(10, 18, 38, 225);
    private static final Color TRACK_BACK = new Color(2, 4, 12, 235);
    private static final Color INACTIVE = new Color(0x4a5c78);
    private static final double PAD = 14;
    private static final double KNOB_W = 12;
    /** Extra horizontal reach (logical px) beyond the track ends that still counts as a track press. */
    private static final double SLOP = 10;
    private static final Font READOUT_FONT = Cyber.mono(Font.BOLD, 13);
    private static final Font CAPTION_FONT = Cyber.mono(Font.BOLD, 11);

    private final double w, h;
    /** Track start and length, relative to the slider's own location. */
    private final double trackX, trackW;
    private final double readoutRight;
    private final Color accent;
    private final Cyber.Chamfer frame;
    private final Cyber.Bar track;
    private final Cyber.Chamfer knob;
    private final GLabel caption;
    private final GLabel readout;
    private int value;
    private boolean hover, dragging, inactive;
    private double grabOffset;
    private double hoverT, dragT;
    private IntConsumer onChange, onRelease;
    private IntSupplier source;
    private BooleanSupplier inactiveSource;

    /**
     * Creates a slider showing 0 %.
     *
     * @param x       left edge (logical)
     * @param y       top edge (logical)
     * @param w       width of the whole box, caption and readout included
     * @param h       height of the box
     * @param caption short label at the left inside the box, or null for none
     * @param accent  neon colour of the frame, track fill and knob
     */
    public Slider(double x, double y, double w, double h, String caption, Color accent) {
        this.w = w; this.h = h; this.accent = accent;
        frame = new Cyber.Chamfer(0, 0, w, h, Math.min(10, h * 0.28)).scan(false);
        add(frame);
        double left = PAD;
        if (caption != null) {
            this.caption = new Cyber.Text(caption);
            this.caption.setFont(CAPTION_FONT);
            this.caption.setLocation(PAD, (h + this.caption.getAscent()) / 2 - 2);
            add(this.caption);
            left += this.caption.getWidth() + 10;
        } else {
            this.caption = null;
        }
        readout = new Cyber.Text("100%");
        readout.setFont(READOUT_FONT);
        readoutRight = w - PAD;
        double readoutW = readout.getWidth();
        trackX = left + KNOB_W / 2;
        trackW = Math.max(1, readoutRight - readoutW - 12 - KNOB_W / 2 - trackX);
        track = new Cyber.Bar(trackX, h / 2 - 3, trackW, 6, 0).notches(0.25, 0.5, 0.75);
        add(track);
        double kh = Math.max(10, Math.min(24, h - 14));
        knob = new Cyber.Chamfer(0, (h - kh) / 2, KNOB_W, kh, 3).scan(false).lineWidth(1.2);
        add(knob);
        add(readout);
        setLocation(x, y);
        refresh();
        apply();
    }

    // ------------------------------------------------------------------ value mapping
    /** Clamps a percentage to 0-100. */
    public static int clamp(int percent) { return Math.max(0, Math.min(100, percent)); }

    /**
     * The percentage at horizontal position {@code x} on a track that starts at {@code trackLeft} and is
     * {@code trackWidth} long: rounded to a whole percent and clamped to 0-100 (positions before the track give 0,
     * past it 100). A non-positive width gives 0.
     */
    public static int valueAt(double x, double trackLeft, double trackWidth) {
        if (!(trackWidth > 0)) return 0;
        double f = Math.max(0, Math.min(1, (x - trackLeft) / trackWidth));
        return clamp((int) Math.round(f * 100));
    }

    /** The percentage at absolute logical x on this slider's track (see {@link #valueAt(double, double, double)}). */
    public int valueAtX(double lx) { return valueAt(lx, getTrackLeft(), trackW); }

    /** Absolute logical x of the track's 0 % end. */
    public double getTrackLeft() { return getX() + trackX; }
    /** Track length in logical px (0 % to 100 %). */
    public double getTrackWidth() { return trackW; }
    /** Absolute logical x of the knob's centre for the current value. */
    public double getKnobX() { return getTrackLeft() + trackW * value / 100.0; }
    /** Absolute logical y of the slider's vertical centre (the track and knob centre line). */
    public double getCenterY() { return getY() + h / 2; }
    public double getW() { return w; }
    public double getH() { return h; }

    // ------------------------------------------------------------------ state
    /** The current value in percent (0-100). */
    public int getValue() { return value; }

    /** Shows {@code percent} (clamped) without firing any callback, for syncing from the model. */
    public void setValue(int percent) {
        int v = clamp(percent);
        if (v == value) return;
        value = v;
        refresh();
    }

    /** Called with the new value whenever the user changes it (press on the track, drag). */
    public void setOnChange(IntConsumer c) { onChange = c; }
    /** Called once with the final value when a drag ends ({@link #release()}). */
    public void setOnRelease(IntConsumer c) { onRelease = c; }

    /**
     * Binds the slider to a model: {@link #sync()} then shows {@code value} (except while the user is dragging) and,
     * if {@code inactive} is not null, greys the slider while it returns true. Returns this slider.
     */
    public Slider bind(IntSupplier value, BooleanSupplier inactive) {
        source = value;
        inactiveSource = inactive;
        sync();
        return this;
    }

    /** Pulls the value and inactive state from the bound model (see {@link #bind}); does nothing if unbound. */
    public void sync() {
        if (inactiveSource != null) setInactive(inactiveSource.getAsBoolean());
        if (source != null && !dragging) setValue(source.getAsInt());
    }

    /** Greys the slider out (it keeps working and keeps its value), e.g. while its audio channel is muted. */
    public void setInactive(boolean on) {
        if (on == inactive) return;
        inactive = on;
        apply();
    }

    public boolean isInactive() { return inactive; }
    /** True between a {@link #press} on the track and the matching {@link #release()}. */
    public boolean isDragging() { return dragging; }
    /** Sets the hover highlight (the owner passes {@code hit(mouse)}). */
    public void setHover(boolean on) { hover = on; }

    // ------------------------------------------------------------------ input (logical coordinates)
    /** True if logical point (lx, ly) lies inside the slider's box (absolute coordinates). */
    public boolean hit(double lx, double ly) {
        return isVisible() && lx >= getX() && lx <= getX() + w && ly >= getY() && ly <= getY() + h;
    }

    /**
     * Mouse press at (lx, ly). On the track (or within a few px of its ends) it starts a drag: a press on the knob
     * grabs it where it is, a press elsewhere on the track jumps the value there. A press on the caption or readout
     * changes nothing. Returns true if the press was inside the box, so the owner should not pass it on.
     */
    public boolean press(double lx, double ly) {
        if (!hit(lx, ly)) return false;
        double rel = lx - getTrackLeft();
        if (rel < -KNOB_W / 2 - SLOP || rel > trackW + KNOB_W / 2 + SLOP) return true;
        double kx = getKnobX();
        grabOffset = Math.abs(lx - kx) <= KNOB_W / 2 + 2 ? lx - kx : 0;
        dragging = true;
        userSet(valueAtX(lx - grabOffset));
        return true;
    }

    /** Mouse drag to (lx, ly): moves the knob while a drag is in progress (the pointer may leave the box). */
    public void drag(double lx, double ly) {
        if (dragging) userSet(valueAtX(lx - grabOffset));
    }

    /** Mouse release: ends a drag and fires the release callback. Returns true if a drag was in progress. */
    public boolean release() {
        if (!dragging) return false;
        dragging = false;
        if (onRelease != null) onRelease.accept(value);
        return true;
    }

    private void userSet(int v) {
        v = clamp(v);
        if (v == value) return;
        value = v;
        refresh();
        if (onChange != null) onChange.accept(v);
    }

    // ------------------------------------------------------------------ drawing
    /** Eases the hover / drag highlight (call once per frame). */
    public void animate(double dt) {
        double k = Math.min(1, dt * 14);
        hoverT += ((hover || dragging ? 1 : 0) - hoverT) * k;
        dragT += ((dragging ? 1 : 0) - dragT) * k;
        apply();
    }

    /** Positions the knob, track fill and readout for the current value. */
    private void refresh() {
        track.setValue(value / 100.0);
        knob.setLocation(trackX + trackW * value / 100.0 - KNOB_W / 2, knob.getY());
        readout.setLabel(value + "%");
        readout.setLocation(readoutRight - readout.getWidth(), (h + readout.getAscent()) / 2 - 2);
    }

    private void apply() {
        Color acc = inactive ? INACTIVE : accent;
        double act = Math.max(hoverT * 0.55, dragT);
        frame.fill(Cyber.lerp(FILL, Cyber.alpha(Cyber.lerp(new Color(10, 18, 38), acc, 0.22), 235), Math.min(1, act * 0.8)))
            .border(Cyber.lerp(Cyber.alpha(acc, 150), acc, Math.min(1, 0.45 + act)))
            .glow(inactive ? 0 : Math.min(1, hoverT * 0.75 + dragT * 0.4));
        track.colors(Cyber.lerp(acc, Color.WHITE, 0.2 * act), TRACK_BACK, Cyber.alpha(acc, inactive ? 90 : 120));
        knob.fill(Cyber.lerp(acc, Color.WHITE, 0.35 + 0.45 * act)).border(Cyber.lerp(acc, Color.WHITE, 0.75))
            .glow(inactive ? 0 : 0.35 + 0.65 * act);
        Cyber.setColor(readout, inactive ? Cyber.MUTED : Cyber.lerp(Cyber.TEXT, Color.WHITE, hoverT));
        if (caption != null) Cyber.setColor(caption, inactive ? Cyber.DIM : Cyber.alpha(acc, 220));
    }

    // ------------------------------------------------------------------ group helpers (null-safe)
    /** Offers a press to each slider of {@code group} (may be null); true if one of them took it. */
    public static boolean pressAny(double lx, double ly, Slider... group) {
        if (group != null) for (Slider s : group) if (s != null && s.press(lx, ly)) return true;
        return false;
    }

    /** Forwards a drag to every slider of {@code group} (may be null); only one being dragged reacts. */
    public static void dragAll(double lx, double ly, Slider... group) {
        if (group != null) for (Slider s : group) if (s != null) s.drag(lx, ly);
    }

    /** Ends any drag in {@code group} (may be null); true if one was being dragged. */
    public static boolean releaseAll(Slider... group) {
        boolean any = false;
        if (group != null) for (Slider s : group) if (s != null && s.release()) any = true;
        return any;
    }

    /** Sets each slider's hover from the pointer position (may be null). */
    public static void hoverAll(double lx, double ly, Slider... group) {
        if (group != null) for (Slider s : group) if (s != null) s.setHover(s.hit(lx, ly));
    }

    /** Per-frame update for a group (may be null): {@link #sync()} then {@link #animate(double)}. */
    public static void frameAll(double dt, Slider... group) {
        if (group != null) for (Slider s : group) if (s != null) { s.sync(); s.animate(dt); }
    }
}
