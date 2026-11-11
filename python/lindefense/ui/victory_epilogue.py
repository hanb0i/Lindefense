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
    PROMPT = "CLICK OR ESC TO CONTINUE"
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
        frame = Cyber.Chamfer(px, y, pw, 100, 26).fill(Color(6, 10, 24, 242)).border(Cyber.YELLOW).glow(1.1).line_width(2).ticks(True)
        self.add(frame)
        stripe = Ui.rect(px + 24, 0, 140, 3, Cyber.MAGENTA, Cyber.MAGENTA)
        self.add(stripe)
        cx = x + w / 2
        t = 0.2
        yy = 44.0
        micro = self._centered(Cyber.spaced('// epilogue  -  palantir offline'), Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.YELLOW, 230), cx, yy, t)
        self.title = Cyber.GlitchText('THE LAST LINE HOLDS', Cyber.display(Font.BOLD, 54), Cyber.lerp(Cyber.YELLOW, Color.WHITE, 0.3))
        yy += 70
        self.title.set_location(cx - self.title.text_width() / 2, yy)
        self.add(self.title)
        self.items.append([self.title, None, t, yy])
        self.title.burst(0.6)
        self.glitch = 2.5
        yy += 50
        body = Cyber.body(Font.PLAIN, 18)
        for i, para in enumerate(VictoryEpilogue.STORY):
            t += VictoryEpilogue.LINE_DELAY
            last = i == len(VictoryEpilogue.STORY) - 1
            f = Cyber.display(Font.BOLD, 24) if last else body
            col = Cyber.lerp(Cyber.YELLOW, Color.WHITE, 0.45) if last else Cyber.TEXT
            if last:
                yy += 12
            for line in Ui.wrap(para, f, pw - 120):
                self._centered(line, f, col, cx, yy, t)
                yy += 26
            yy += 8
        t += VictoryEpilogue.LINE_DELAY
        yy += 14
        rule = GLine(px + 60, 0, px + pw - 60, 0)
        rule.set_color(Cyber.alpha(Cyber.CYAN, 0))
        self.add(rule)
        self.rule = rule
        self.rule_t = t
        rule_y = yy
        yy += 40
        self._centered(Cyber.spaced('// credits'), Cyber.mono(Font.BOLD, 11), Cyber.alpha(Cyber.CYAN, 220), cx, yy, t)
        yy += 36
        t += 0.4
        self._centered(VictoryEpilogue.BYLINE, Cyber.display(Font.BOLD, 26), Cyber.TEXT, cx, yy, t)
        yy += 32
        t += 0.4
        self._centered(VictoryEpilogue.THANKS, Cyber.body(Font.BOLD, 18), Cyber.lerp(Cyber.MAGENTA, Color.WHITE, 0.35), cx, yy, t)
        yy += 34
        small = Cyber.mono(Font.BOLD, 11)
        for para in VictoryEpilogue.ASSET_CREDITS:
            t += 0.4
            for line in Ui.wrap(para, small, pw - 60):
                self._centered(line, small, Cyber.MUTED, cx, yy, t)
                yy += 17
            yy += 4
        yy += 34
        self.prompt = self._centered(VictoryEpilogue.PROMPT, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.YELLOW, 220), cx, yy, t + VictoryEpilogue.LINE_DELAY)
        self.end_time = t + VictoryEpilogue.LINE_DELAY + VictoryEpilogue.FADE
        ph = yy + 30
        py = y + (h - ph) / 2
        frame.size(pw, ph)
        frame.set_location(px, py)
        stripe.set_location(px + 24, py + 12)
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
            if col is None:
                obj.set_alpha_factor(a)
            else:
                Cyber.set_color(obj, Cyber.alpha(col, _j.to_int(col.get_alpha() * a)))
            obj.set_location(obj.get_x(), y + (1 - a) * VictoryEpilogue.SLIDE)
        a = _j.dmax(0, _j.dmin(1, (self.time - self.rule_t) / VictoryEpilogue.FADE))
        Cyber.set_color(self.rule, Cyber.alpha(Cyber.CYAN, _j.to_int(90 * a)))
        self.title.animate(dt)
        self.glitch -= dt
        if self.glitch <= 0:
            self.title.burst(0.25)
            self.glitch = 3.0

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
            out.append(obj.main.get_label() if col is None else obj.get_label())
        return out


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ui import Ui  # noqa: E402
