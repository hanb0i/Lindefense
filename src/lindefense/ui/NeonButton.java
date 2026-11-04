package lindefense.ui;

import acm.graphics.GCompound;
import acm.graphics.GLabel;
import java.awt.Color;
import java.awt.Font;

/**
 * Cyberpunk menu button: cut-corner neon outline with layered glow strokes that brighten
 * (with eased transitions) on hover. Same hit/click contract as {@link UIButton}.
 */
public final class NeonButton extends GCompound {
    private static final long serialVersionUID = 1L;
    private static final Color BASE = new Color(0x0b1024);

    private final double w, h;
    private final Cyber.Chamfer frame;
    private final GLabel text;
    private final Color neon;
    private final Runnable action;
    private boolean hover;
    private double hoverT, pressT, pulse;

    public NeonButton(double x, double y, double w, double h, String label, Font font, Color neon, Runnable action) {
        this.w = w; this.h = h; this.neon = neon; this.action = action;
        frame = new Cyber.Chamfer(0, 0, w, h, 14).fill(BASE).border(neon).scan(true).lineWidth(1.8).ticks(true);
        add(frame);
        text = new Cyber.Text(label);
        text.setFont(font);
        text.setColor(neon);
        text.setLocation((w - text.getWidth()) / 2, (h + text.getAscent()) / 2 - 3);
        add(text);
        setLocation(x, y);
    }

    /** Replaces the label (checklist toggles relabel themselves as they are ticked). */
    public void setText(String label) {
        text.setLabel(label);
        text.setLocation((w - text.getWidth()) / 2, (h + text.getAscent()) / 2 - 3);
    }

    /** Marks the button as currently "on": it is filled with its own neon instead of the dark base. */
    public void setSelected(boolean on) {
        frame.fill(on ? Cyber.alpha(neon, 46) : BASE);
    }

    public boolean hit(double lx, double ly) {
        return isVisible() && lx >= getX() && lx <= getX() + w && ly >= getY() && ly <= getY() + h;
    }

    public boolean click() {
        if (!isVisible()) return false;
        pressT = 1;
        lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_SELECT);   // AUDIO HOOK
        if (action != null) action.run();
        return true;
    }

    public void setHover(boolean h) {
        if (h && !hover) lindefense.audio.AudioManager.sfx(lindefense.audio.Sfx.UI_HOVER);   // AUDIO HOOK
        hover = h;
    }

    /** Animates glow and colour easing. */
    public void animate(double dt) {
        pulse += dt;
        hoverT += ((hover ? 1 : 0) - hoverT) * Math.min(1, dt * 14);
        pressT = Math.max(0, pressT - dt * 5);
        double base = 0.30 + 0.15 * Math.sin(pulse * 3);
        double glow = base + (1.1 - base) * hoverT;
        frame.glow(glow);
        frame.fill(Cyber.lerp(Cyber.lerp(BASE, neon, 0.28 * hoverT), Color.WHITE, pressT * 0.35));
        frame.border(Cyber.lerp(neon, Color.WHITE, 0.25 * hoverT));
        Cyber.setColor(text, Cyber.lerp(neon, Color.WHITE, hoverT));
    }
}
