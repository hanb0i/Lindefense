"""Victory epilogue and credits: shown over the playfield after the first Palantir victory of a run, before the victory
stats. The story lines and credits fade in one after another; a click or Esc skips it (GameScreen routes those)."""
from lindefense.ui import display_settings
from lindefense.ui import jrt as _j
from lindefense.ui.acm import GCompound, GLine
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import Color, Font


class VictoryEpilogue(GCompound):
    STORY = (
        "Wave 100. Palantir's final prediction returns null.",
        "Its core goes dark, and the surveillance network it wove through every server collapses, node by node, "
        "camera by camera.",
        "The sorters scatter, the boardrooms fall silent, and for the first time the grid is quiet.",
        "The last line of code holds.",
    )
    BYLINE = "Lindefense - a game by Hanbo Song and Austin"
    THANKS = "Special thanks: Mr. Lindemann"
    ASSET_CREDITS = (
        "Fonts: Rajdhani (Indian Type Foundry), Barlow (Jeremy Tribby), IBM Plex Mono (IBM Corp.)  -  SIL OFL 1.1",
        "Sound effects: Juhani Junkala and Kenney.nl (CC0)  -  interface sounds synthesised for Lindefense",
    )
    PROMPT = "Click or Esc to continue"
    LINE_DELAY = 0.85     # seconds between two items appearing
    FADE = 0.6            # seconds one item takes to fade in
    SLIDE = 8.0           # px an item rises while it fades in
    PW = 820.0

    def __init__(self, x, y, w, h):
        GCompound.__init__(self)
        self.time = 0.0
        self.items = []    # [object, base colour, appear time, final y]
        self.add(Ui.rect(x, y, w, h, Ui.c(0x02040a, 228), Ui.c(0x000000, 0)))
        pw = VictoryEpilogue.PW
        px = x + (w - pw) / 2
        frame = Cyber.Chamfer(px, y, pw, 100, 6)
        self.add(frame)
        cx = x + w / 2
        t = 0.2
        yy = 98.0
        self.title = self._centered('THE LAST LINE HOLDS', Cyber.display(Font.BOLD, 46), Cyber.lerp(Cyber.YELLOW, Color.WHITE, 0.2), cx, yy, t)
        yy += 52
        body = Cyber.body(Font.PLAIN, 18)
        for i, para in enumerate(VictoryEpilogue.STORY):
            t += VictoryEpilogue.LINE_DELAY
            last = i == len(VictoryEpilogue.STORY) - 1
            f = Cyber.display(Font.BOLD, 24) if last else body
            col = Cyber.lerp(Cyber.YELLOW, Color.WHITE, 0.45) if last else Cyber.lerp(Cyber.TEXT, Cyber.MUTED, 0.2)
            if last:
                yy += 12
            for line in Ui.wrap(para, f, pw - 120):
                self._centered(line, f, col, cx, yy, t)
                yy += 26
            yy += 8
        t += VictoryEpilogue.LINE_DELAY
        yy += 14
        rule = GLine(px + 60, 0, px + pw - 60, 0)
        rule.set_color(Cyber.alpha(Cyber.EDGE, 0))
        self.add(rule)
        self.rule = rule
        self.rule_t = t
        rule_y = yy
        yy += 40
        self._centered('Credits', Cyber.body(Font.BOLD, 14), Cyber.MUTED, cx, yy, t)
        yy += 36
        t += 0.4
        self._centered(VictoryEpilogue.BYLINE, Cyber.display(Font.BOLD, 26), Cyber.TEXT, cx, yy, t)
        yy += 32
        t += 0.4
        self._centered(VictoryEpilogue.THANKS, Cyber.body(Font.BOLD, 18), Cyber.lerp(Cyber.MAGENTA, Color.WHITE, 0.35), cx, yy, t)
        yy += 34
        small = Cyber.body(Font.PLAIN, 13)
        for para in VictoryEpilogue.ASSET_CREDITS:
            t += 0.4
            for line in Ui.wrap(para, small, pw - 60):
                self._centered(line, small, Cyber.MUTED, cx, yy, t)
                yy += 17
            yy += 4
        yy += 34
        self.prompt = self._centered(VictoryEpilogue.PROMPT, Cyber.body(Font.PLAIN, 14), Cyber.MUTED, cx, yy, t + VictoryEpilogue.LINE_DELAY)
        self.end_time = t + VictoryEpilogue.LINE_DELAY + VictoryEpilogue.FADE
        ph = yy + 30
        py = y + (h - ph) / 2
        frame.size(pw, ph)
        frame.set_location(px, py)
        rule.set_start_point(px + 60, py + rule_y)
        rule.set_end_point(px + pw - 60, py + rule_y)
        for it in self.items:
            it[3] += py
        self.top = py
        self.height = ph
        self.update(0)

    def _centered(self, text, font, col, cx, y, t):
        l = Ui.label(text, 0, y, font, col)
        l.set_location(cx - l.get_width() / 2, y)
        self.add(l)
        self.items.append([l, col, t, y])
        return l

    def update(self, dt):
        self.time += dt
        for obj, col, t0, y in self.items:
            a = _j.dmax(0, _j.dmin(1, (self.time - t0) / VictoryEpilogue.FADE))
            if obj is self.prompt and a >= 1:
                a = display_settings.calm(0.55 + 0.45 * abs(((self.time * 0.8) % 2.0) - 1.0), 1.0)   # no blinking
            Cyber.set_color(obj, Cyber.alpha(col, _j.to_int(col.get_alpha() * a)))
            obj.set_location(obj.get_x(), y + (0 if display_settings.reduced_motion() else (1 - a) * VictoryEpilogue.SLIDE))
        a = _j.dmax(0, _j.dmin(1, (self.time - self.rule_t) / VictoryEpilogue.FADE))
        Cyber.set_color(self.rule, Cyber.alpha(Cyber.EDGE, _j.to_int(255 * a)))

    def finish(self):
        """Shows everything at once."""
        if self.time < self.end_time:
            self.update(self.end_time - self.time)

    def is_finished(self):
        return self.time >= self.end_time

    def texts(self):
        """Every text line (tests)."""
        out = []
        for obj, col, t0, y in self.items:
            out.append(obj.get_label())
        return out


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ui import Ui  # noqa: E402
