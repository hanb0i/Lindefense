"""SETTINGS > DISPLAY > FPS COUNTER: a small frame-rate readout in the bottom-right corner of the logical layout, over
every screen (menu, map select, match). The app feeds it the real time between frames and paints it after the UI."""
from lindefense.ui.jawt import Color, Font


class FpsCounter:
    WINDOW = 0.5        # seconds of frames averaged per readout update
    MARGIN = 4.0        # logical px from the layout's right / bottom edge

    def __init__(self):
        self.frames = 0
        self.elapsed = 0.0
        self.fps = 0.0
        self.text = "-- FPS"
        self._font = None

    def tick(self, real_dt):
        """One presented frame, real_dt seconds after the previous one (uncapped)."""
        if real_dt <= 0:
            return
        self.frames += 1
        self.elapsed += real_dt
        if self.elapsed >= self.WINDOW:
            self.fps = self.frames / self.elapsed
            self.text = "%d FPS" % int(self.fps + 0.5)
            self.frames = 0
            self.elapsed = 0.0

    def paint(self, g, layer):
        """Draws the readout over everything, in the logical space of layer (the app's ScaledLayer)."""
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        if self._font is None:
            self._font = Cyber.mono(Font.BOLD, 11)
        g2 = g.create()
        try:
            g2.translate(layer.off_x, layer.off_y)
            g2.scale(layer.get_scale(), layer.get_scale())
            fm = g2.get_font_metrics(self._font)
            tw = fm.string_width(self.text)
            w, h = tw + 12, fm.get_ascent() + 6
            x, y = Ui.W - self.MARGIN - w, Ui.H - self.MARGIN - h
            g2.set_color(Color(4, 7, 18, 210))
            g2.fill_rect(x, y, w, h)
            g2.set_color(Cyber.alpha(Cyber.CYAN, 150))
            g2.draw_rect(x, y, w, h)
            g2.set_font(self._font)
            g2.set_color(Cyber.CYAN)
            g2.draw_string(self.text, x + 6, y + h - 4)
        finally:
            g2.dispose()
