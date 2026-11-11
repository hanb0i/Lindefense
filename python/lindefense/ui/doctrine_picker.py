"""The ATTACK DOCTRINE picker of the Adversarial Training briefing: three cards (Rush / Swarm / Heist) with their perks
and their cost, one of them selected. The pick is kept for the session (ai/units.select_doctrine) and the next reverse
match starts with it; keys 1 / 2 / 3 pick too."""
from lindefense.ai import units
from lindefense.ai.units import Doctrine
from lindefense.ui.acm import GCompound
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import Color, Font
from lindefense.ui.ui import Ui

CARD_H = 118.0
GAP = 12.0


class DoctrinePicker(GCompound):
    """Built at (x, y) = the band heading's baseline, w wide; buttons() are the three clickable cards."""

    def __init__(self, x, y, w):
        from lindefense.ui.neon_button import NeonButton
        GCompound.__init__(self)
        head = Ui.label("Attack doctrine", x, y, Cyber.body(Font.BOLD, 14), Cyber.MUTED)
        self.add(head)
        hint = Ui.label("click a card or press 1  2  3", 0, y, Cyber.body(Font.PLAIN, 13), Cyber.DIM)
        hint.set_location(x + w - hint.get_width(), y)
        self.add(hint)
        lx = x + head.get_width() + 14
        self.add(Ui.rect(lx, y - 5, hint.get_x() - 14 - lx, 1, Cyber.EDGE, Cyber.EDGE))
        cw = (w - 2 * GAP) / 3.0
        cy = y + 14
        self.cards = []
        for i, d in enumerate(Doctrine):
            cx = x + i * (cw + GAP)
            acc = Ui.c(d.rgb)
            b = NeonButton(cx, cy, cw, CARD_H, "", Cyber.mono(Font.BOLD, 1), acc, (lambda d=d: self.pick(d)))
            b.set_selected_color(Cyber.alpha(acc, 34))
            self.add(b)
            self.cards.append((d, b))
            name = Ui.label(d.display_name.upper(), cx + 16, cy + 28, Cyber.display(Font.BOLD, 20), Cyber.lerp(acc, Color.WHITE, 0.2))
            self.add(name)
            key = Ui.label("[" + str(i + 1) + "]", 0, cy + 27, Cyber.mono(Font.BOLD, 12), Cyber.MUTED)
            key.set_location(cx + cw - 14 - key.get_width(), cy + 27)
            self.add(key)
            tag = Ui.label(d.tagline, cx + 16 + name.get_width() + 10, cy + 27, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
            if tag.get_x() + tag.get_width() > key.get_x() - 8:
                tag.set_visible(False)
            self.add(tag)
            ly = cy + 52
            f = Cyber.body(Font.PLAIN, 14)
            for p in d.perks:
                self.add(Ui.label("+  " + p, cx + 16, ly, f, Cyber.TEXT))
                ly += 19
            self.drawback = Ui.label("-  " + d.drawback, cx + 16, ly + 2, f, Cyber.bad())
            self.add(self.drawback)
        self.refresh()

    def buttons(self):
        return [b for _, b in self.cards]

    def pick(self, d):
        units.select_doctrine(d)
        self.refresh()

    def pick_index(self, i):
        """Keys 1 / 2 / 3."""
        ds = list(Doctrine)
        if 0 <= i < len(ds):
            self.pick(ds[i])

    def refresh(self):
        sel = units.selected_doctrine()
        for d, b in self.cards:
            b.set_selected(d is sel)
