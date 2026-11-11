"""Run setup UI: the RUN SETUP band at the bottom of the mission briefing (SEED field, challenge toggles, PATCH NOTES
switch), the DAILY RUN card on the map-select screen and its briefing, and the rule chips shown in the in-game run
strip and on the end screen. The logic behind them is lindefense.sim.run_setup / lindefense.sim.challenges."""
import sys

from lindefense.sim.challenges import Challenge
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.run_setup import DailyRecords, DailyRun, RunOptions, RunSetup, parse_seed_entry
from lindefense.ui.acm import GCompound
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import Color, Font, KeyEvent
from lindefense.ui.ui import Ui
from lindefense.ui.ui_button import UIButton
from lindefense.variance.variance import seed_format


PASTE_KEY = "Cmd+V" if sys.platform == "darwin" else "Ctrl+V"


def clipboard_text():
    """The system clipboard's text (SDL, through pygame), or "" when there is none or no window."""
    try:
        import pygame
        if not pygame.display.get_init():
            return ""
        return pygame.scrap.get_text() or ""
    except Exception:
        return ""


def _audio(sfx_name):
    from lindefense.audio.audio_manager import AudioManager
    from lindefense.audio.sfx import Sfx
    AudioManager.sfx(getattr(Sfx, sfx_name))


# ====================================================================== SEED field
class SeedField(GCompound):
    """The briefing's SEED text box. Click it, then type or paste (Cmd+V / Ctrl+V) a run code; a blank field means a
    random seed. While it has focus every key goes to it (so M / N type letters instead of toggling audio); Enter
    deploys and Esc or a click elsewhere drops the focus. A locked field just shows a fixed seed (daily run)."""
    MAX = 20
    PAD = 74.0

    def __init__(self, x, y, w, h, on_change=None, locked=False, accent=None):
        GCompound.__init__(self)
        self.w = w
        self.h = h
        self.text = ""
        self.focused = False
        self.hover = False
        self.error = False
        self.locked = locked
        self.on_change = on_change
        self.accent = Cyber.CYAN if accent is None else accent
        self.t = 0.0
        self.hover_t = 0.0
        self.frame = Cyber.Chamfer(0, 0, w, h, 10).scan(False).fill(Color(4, 9, 22, 245)).line_width(1.5)
        self.add(self.frame)
        self.tag = Ui.label("SEED", 14, h / 2 + 4.5, Cyber.mono(Font.BOLD, 12), Cyber.alpha(self.accent, 225))
        self.add(self.tag)
        self.add(Ui.rect(60, 9, 1, h - 18, Cyber.alpha(self.accent, 90), Cyber.alpha(self.accent, 90)))
        self.value = Ui.label("", SeedField.PAD, h / 2 + 7, Cyber.mono(Font.BOLD, 19), Cyber.TEXT)
        self.add(self.value)
        self.caret = Ui.rect(SeedField.PAD, 9, 2, h - 18, self.accent, self.accent)
        self.add(self.caret)
        self.set_location(x, y)
        self.refresh()

    # ---- the clickable contract shared with UIButton / NeonButton (the screen keeps it in briefing_buttons)
    def get_w(self):
        return self.w

    def get_h(self):
        return self.h

    def hit(self, lx, ly):
        return (self.is_visible() and self.get_x() <= lx <= self.get_x() + self.w
                and self.get_y() <= ly <= self.get_y() + self.h)

    def click(self):
        if self.locked or not self.is_visible():
            return False
        if not self.focused:
            _audio("UI_CLICK")
        self.set_focus(True)
        return True

    def set_hover(self, h):
        self.hover = h

    def animate(self, dt):
        self.t += dt
        self.hover_t += ((1 if self.hover and not self.locked else 0) - self.hover_t) * min(1.0, dt * 14)
        on = self.focused and int(self.t * 2.2) % 2 == 0
        if self.caret.is_visible() != on:
            self.caret.set_visible(on)
        self.style()

    # ---- text
    def set_focus(self, on):
        if self.locked:
            on = False
        if on != self.focused:
            self.focused = on
            self.t = 0.0
            self.refresh()

    def set_text(self, s):
        s = (s or "")[:SeedField.MAX]
        if s != self.text:
            self.text = s
            self.refresh()
            if self.on_change is not None:
                self.on_change()

    def set_error(self, e):
        if e != self.error:
            self.error = e
            self.refresh()

    def paste(self, s):
        """Pastes the clipboard's first line (the parser strips spaces and a leading "SEED")."""
        line = (s or "").strip().splitlines()
        if line:
            self.set_text((self.text + line[0].strip())[:SeedField.MAX])

    def key_pressed(self, e):
        """A key while the field has focus: Backspace deletes, Cmd/Ctrl+V pastes, Cmd/Ctrl+Backspace clears,
        printable characters type. Every key is consumed."""
        if not self.focused:
            return False
        k = e.get_key_code()
        cmd = e.is_meta_down() or e.is_control_down()
        if cmd and k == KeyEvent.VK_V:
            self.paste(clipboard_text())
            return True
        if k == KeyEvent.VK_BACK_SPACE or k == KeyEvent.VK_DELETE:
            self.set_text("" if cmd else self.text[:-1])
            return True
        if cmd:
            return True
        typed = ""
        for ch in e.get_key_char() or "":
            cp = ord(ch)
            if ch != KeyEvent.CHAR_UNDEFINED and not (cp <= 0x20 or 0x7f <= cp <= 0x9f):
                typed += ch
        if typed:
            self.set_text(self.text + typed)
        return True

    def refresh(self):
        if not self.text and not self.focused:
            Cyber.set_text(self.value, "RANDOM")
            Cyber.set_color(self.value, Cyber.DIM)
        else:
            Cyber.set_text(self.value, self.text.upper())
            Cyber.set_color(self.value, Cyber.RED if self.error else (self.accent if self.locked else Cyber.TEXT))
        self.caret.set_location(SeedField.PAD + (self.value.get_width() + 3 if self.text else 0), 9)
        self.caret.set_visible(self.focused)
        self.style()

    def style(self):
        acc = Cyber.RED if self.error else self.accent
        if self.focused:
            self.frame.border(acc).glow(0.9).fill(Color(6, 14, 32, 250))
        else:
            self.frame.border(Cyber.lerp(Cyber.alpha(acc, 150), acc, self.hover_t)).glow(0.5 * self.hover_t) \
                .fill(Color(4, 9, 22, 245))


# ====================================================================== RUN SETUP band
class RunSetupBand:
    """The RUN SETUP band across the bottom of the mission briefing: the SEED field with its status, the PATCH NOTES
    switch (saved) and one toggle per challenge rule (kept for the session), with a line describing the hovered or
    active rules. For the daily run the same band shows the day's fixed seed and rule, locked."""
    FIELD_W = 330.0
    PATCH_W = 236.0

    def __init__(self, into, x, y, w, daily=None, options=None):
        self.into = into
        self.x = x
        self.y = y
        self.w = w
        self.daily = daily
        self.options = RunOptions.get() if options is None else options
        self.buttons = []
        self.toggles = []
        self.note = None
        acc = Cyber.MAGENTA if daily is not None else Cyber.CYAN
        head = Ui.label("// DAILY SETUP  -  THE SAME FOR EVERYONE TODAY" if daily is not None else "// RUN SETUP",
                        x, y, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.MAGENTA, 230))
        into.add(head)
        lx = x + head.get_width() + 14
        into.add(Ui.rect(lx, y - 5, x + w - lx, 1, Cyber.alpha(acc, 80), Cyber.alpha(acc, 80)))
        ry = y + 14
        self.field = SeedField(x, ry, RunSetupBand.FIELD_W, 40, self.refresh, daily is not None, acc)
        if daily is not None:
            self.field.text = daily.seed_text()
            self.field.refresh()
        into.add(self.field)
        self.buttons.append(self.field)
        sx = x + RunSetupBand.FIELD_W + 16
        self.status_head = Ui.label("", sx, ry + 15, Cyber.mono(Font.BOLD, 11), acc)
        self.status = Ui.label("", sx, ry + 34, Cyber.body(Font.PLAIN, 14), Cyber.MUTED)
        into.add(self.status_head)
        into.add(self.status)
        self.patch = UIButton(x + w - RunSetupBand.PATCH_W, ry, RunSetupBand.PATCH_W, 40, "PATCH NOTES: ON",
                              Cyber.display(Font.BOLD, 16), self.toggle_patch_notes)
        into.add(self.patch)
        self.buttons.append(self.patch)
        ty = y + 66
        gap = 10.0
        cs = list(Challenge)
        tw = (w - gap * (len(cs) - 1)) / len(cs)
        for i, c in enumerate(cs):
            b = UIButton(x + i * (tw + gap), ty, tw, 36, c.chip, Cyber.display(Font.BOLD, 15),
                         lambda c=c: self.toggle_challenge(c))
            into.add(b)
            self.buttons.append(b)
            self.toggles.append((c, b))
        self.desc_font = Cyber.body(Font.PLAIN, 15)
        self.desc = Ui.label("", x, y + 128, self.desc_font, Cyber.MUTED)
        into.add(self.desc)
        self.shown_desc = None
        self.refresh()

    # ---- state
    def is_daily(self):
        return self.daily is not None

    def challenges(self):
        return self.daily.challenges if self.daily is not None else self.options.challenges

    def patch_notes(self):
        return True if self.daily is not None else self.options.patch_notes_on()

    def is_typing(self):
        return self.field.focused

    def blur(self):
        self.field.set_focus(False)

    def mouse_pressed(self, lx, ly):
        """A click anywhere but the field takes the focus away from it."""
        if not self.field.hit(lx, ly):
            self.field.set_focus(False)

    def key_pressed(self, e):
        return self.field.key_pressed(e)

    def toggle_challenge(self, c):
        if self.daily is not None:
            self.note = (c.chip + " IS TODAY'S RULE", "The daily run's rule is fixed: everyone plays it today.")
        else:
            self.options.toggle_challenge(c)
            self.note = None
        self.refresh()

    def toggle_patch_notes(self):
        if self.daily is not None:
            self.note = ("PATCH NOTES ARE ON", "The daily run always drafts Patch Notes (the same offers for everyone).")
        else:
            self.options.toggle_patch_notes()
            self.note = None
        self.refresh()

    def setup(self, map_index, difficulty=None):
        """The RunSetup to deploy, or None (with the error shown) when the typed seed is not valid."""
        if self.daily is not None:
            return self.daily.setup()
        seed, err = parse_seed_entry(self.field.text)
        if err is not None:
            self.field.set_error(True)
            self.refresh()
            return None
        d = Difficulty.get_selected() if difficulty is None else difficulty
        return RunSetup(map_index, d, seed, self.options.challenges, self.options.patch_notes_on())

    # ---- view
    def refresh(self):
        seed, err = parse_seed_entry(self.field.text)
        self.field.set_error(err is not None and self.daily is None)
        if self.daily is not None:
            head, line, col = "DAILY SEED  " + self.daily.seed_text(), "Fixed for " + self.daily.label().title() + \
                ". Patch Notes on.", Cyber.MAGENTA
        elif err is not None:
            head, line, col = "INVALID SEED", err + ".", Cyber.RED
        elif seed is not None:
            head, line, col = "RUN CODE " + seed_format(seed), "Same drafts, news and elites as the run it came from.", \
                Cyber.GREEN
        else:
            head, line, col = "RANDOM SEED", "Type or paste a run code (" + PASTE_KEY + ") to replay a run.", Cyber.CYAN
        Cyber.set_text(self.status_head, head)
        Cyber.set_color(self.status_head, col)
        Cyber.set_text(self.status, line)
        Cyber.set_color(self.status, Cyber.RED if err is not None and self.daily is None else Cyber.MUTED)
        on = self.patch_notes()
        forced_off = self.daily is None and not RunOptions.env_allows_patch_notes()
        self.patch.set_text("PATCH NOTES: " + ("ON" if on else "OFF"))
        self.patch.set_selected(on)
        self.patch.set_accent(Cyber.CYAN if on else Cyber.DIM)
        self.patch.set_enabled(not forced_off)
        active = self.challenges()
        for c, b in self.toggles:
            sel = c in active
            b.set_primary(sel)   # a rule that is on is filled with its colour; off ones stay dark and muted
            b.set_accent(Color(c.rgb) if sel else Cyber.lerp(Color(c.rgb), Cyber.MUTED, 0.55))
            b.set_enabled(self.daily is None or sel)
        self.shown_desc = None
        self.update_desc()

    def frame(self, dt):
        self.update_desc()

    def update_desc(self):
        hovered = None
        for c, b in self.toggles:
            if b.hover:
                hovered = c
        if hovered is not None:
            text, col = hovered.title.upper() + ":  " + hovered.description, Cyber.lerp(Color(hovered.rgb), Cyber.TEXT, 0.35)
        elif self.patch.hover:
            text, col = ("PATCH NOTES:  draft a run modifier before waves 1, 20, 40, 60 and 80; Breaking News shakes up "
                         "single waves. Off = the plain game."), Cyber.lerp(Cyber.CYAN, Cyber.TEXT, 0.35)
        elif self.note is not None:
            text, col = self.note[0] + ":  " + self.note[1], Cyber.lerp(Cyber.MAGENTA, Cyber.TEXT, 0.35)
        else:
            active = self.challenges()
            if not active:
                text, col = "CHALLENGE RULES:  none, a standard run. Switch any on for a harder run.", Cyber.MUTED
            elif len(active) == 1:
                c = active[0]
                text, col = c.title.upper() + ":  " + c.description, Cyber.lerp(Color(c.rgb), Cyber.TEXT, 0.35)
            else:
                text, col = "RULES ON:  " + "  +  ".join(c.title for c in active) + ".  Hover a rule for details.", \
                    Cyber.TEXT
        if (text, col) != self.shown_desc:
            self.shown_desc = (text, col)
            Cyber.set_text(self.desc, _fit(text, self.desc_font, self.w))
            Cyber.set_color(self.desc, col)


def _fit(text, f, w):
    """text, cut with an ellipsis to fit width w in font f."""
    if Ui.label(text, 0, 0, f, Color.WHITE).get_width() <= w:
        return text
    while text and Ui.label(text + "...", 0, 0, f, Color.WHITE).get_width() > w:
        text = text[:-1]
    return text.rstrip() + "..."


def reverse_band(into, x, y, w):
    """The band's place in the Adversarial Training briefing: says the run setup does not apply there."""
    head = Ui.label("// RUN SETUP", x, y, Cyber.mono(Font.BOLD, 12), Cyber.alpha(Cyber.CYAN, 200))
    into.add(head)
    lx = x + head.get_width() + 14
    into.add(Ui.rect(lx, y - 5, x + w - lx, 1, Cyber.alpha(Cyber.MAGENTA, 80), Cyber.alpha(Cyber.MAGENTA, 80)))
    f = Cyber.body(Font.PLAIN, 15)
    into.add(Ui.label("Seeds, challenge rules and Patch Notes are for defense runs. In Adversarial Training the defender AI",
                      x, y + 30, f, Cyber.MUTED))
    into.add(Ui.label("plays the standard rules on a fresh seed every match.", x, y + 52, f, Cyber.MUTED))


# ====================================================================== DAILY card + briefing
def best_text(best):
    return "TODAY'S BEST  //  WAVE " + str(best) if best > 0 else "NOT PLAYED TODAY"


def build_daily_card(screen, daily, x, y, w, h):
    """The DAILY RUN card in the map-select grid (the free slot after the last map): today's date, the day's map,
    Difficulty Growth mode and rule, today's best wave and a PLAY DAILY button that opens the daily briefing. Returns
    the button."""
    from lindefense.ui.map_art import MapArt
    from lindefense.ui.map_select_screen import MapSelectScreen
    from lindefense.ui.menu_screen import MenuScreen
    from lindefense.ui.neon_button import NeonButton
    m = screen.maps[daily.map_index]
    acc = Cyber.MAGENTA
    rc = Color(daily.rule.rgb)
    frame = MapSelectScreen.cut(x, y, w, h, 16)
    frame.set_filled(True)
    frame.set_fill_color(Color(0x100a22))
    frame.set_color(Cyber.alpha(acc, 190))
    screen.add(frame)
    inner = MapSelectScreen.cut(x + 4, y + 4, w - 8, h - 8, 13)
    inner.set_color(Cyber.alpha(Cyber.YELLOW, 60))
    screen.add(inner)
    screen.add(Ui.rect(x + 24, y + 1, 110, 3, acc, acc))
    compact = h < 520
    screen.add(Ui.label("// DAILY RUN", x + 16, y + 28, Cyber.mono(Font.BOLD, 12), Cyber.alpha(acc, 235)))
    dl = Ui.label(daily.label(), 0, y + 28, Cyber.mono(Font.BOLD, 12), Cyber.TEXT)
    dl.set_location(x + w - 16 - dl.get_width(), y + 28)
    screen.add(dl)
    button_y = y + h - (54 if compact else 70)
    button_h = 40 if compact else 50
    ah = button_y - (y + 42) - (64 if compact else 80)
    aw = ah * 4.0 / 3.0
    if aw > w - 32:
        aw = w - 32
        ah = aw * 3.0 / 4.0
    ax = x + (w - aw) / 2
    ay = y + 40
    screen.add(MapArt(m, ax, ay, aw, ah))
    screen.add(Ui.rect(ax, ay, aw, ah, None, Cyber.alpha(acc, 120)))
    for side in (-1, 1):   # neon brackets either side of the thumbnail
        bx = ax - 12 if side < 0 else ax + aw + 10
        screen.add(Ui.rect(bx, ay, 2, ah, Cyber.alpha(acc, 140), Cyber.alpha(acc, 140)))
        screen.add(Ui.rect(bx + (0 if side < 0 else -6), ay, 8, 2, acc, acc))
        screen.add(Ui.rect(bx + (0 if side < 0 else -6), ay + ah - 2, 8, 2, acc, acc))
    tx = x + 16
    ty = ay + ah + (24 if compact else 30)
    name_f = MenuScreen.menu_font(Font.BOLD, 19 if compact else 24)
    screen.add(Ui.label(_fit(m.get_name().upper(), name_f, w - 32), tx, ty, name_f, Ui.TEXT))
    ty += 18 if compact else 24
    badge = daily.difficulty.label + "  /  " + daily.rule.chip
    bl = Ui.label(badge, tx + 8, ty, Cyber.display(Font.BOLD, 14 if compact else 16), rc)
    screen.add(Ui.rect(tx, ty - (13 if compact else 15), bl.get_width() + 16, 19 if compact else 22,
                       Cyber.alpha(rc, 35), Cyber.alpha(rc, 160)))
    screen.add(bl)
    best = DailyRecords.get().best(daily.date)
    bt = Ui.label(best_text(best), 0, ty, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW if best > 0 else Cyber.MUTED)
    bt.set_location(x + w - 16 - bt.get_width(), ty)
    screen.add(bt)
    play = NeonButton(x + 16, button_y, w - 32, button_h, "PLAY DAILY", MenuScreen.menu_font(Font.BOLD, 17 if compact else 20),
                      acc, screen.open_daily_briefing)
    screen.add(play)
    return play


def build_daily_briefing(screen, daily):
    """The daily run's briefing: the usual frame, art and legend, then the day's date, rule, difficulty and best wave,
    the locked RUN SETUP band (seed, rule, Patch Notes) and START DAILY."""
    from lindefense.ui.map_art import MapArt
    from lindefense.ui.map_select_screen import MapSelectScreen as M
    from lindefense.ui.menu_screen import MenuScreen
    from lindefense.ui.neon_button import NeonButton
    from lindefense.map.game_map import GameMap
    idx = daily.map_index
    m = screen.maps[idx]
    dc = Cyber.MAGENTA
    rc = Color(daily.rule.rgb)
    b = GCompound()
    b.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.c(0x02040a, 205), Ui.c(0x000000, 0)))
    px, py, pw, ph = M.BRIEF_X, M.BRIEF_Y, M.BRIEF_W, M.BRIEF_H
    b.add(Cyber.Chamfer(px, py, pw, ph, 26).fill(Color(12, 6, 26, 244)).border(dc).glow(1.1).line_width(2).ticks(True))
    b.add(Ui.rect(px + 24, py + 12, 140, 3, Cyber.YELLOW, Cyber.YELLOW))
    b.add(Ui.label(Cyber.spaced("// daily run  -  " + daily.label()), px + M.BRIEF_PAD, py + 40, Cyber.mono(Font.BOLD, 12),
                   Cyber.alpha(dc, 230)))
    ax = px + M.BRIEF_PAD
    ay = py + 60
    aw = M.BRIEF_ART_W
    ah = aw * GameMap.HEIGHT / GameMap.WIDTH
    s = aw / GameMap.WIDTH
    b.add(MapArt(m, ax, ay, aw, ah))
    b.add(Ui.rect(ax, ay, aw, ah, None, Cyber.alpha(dc, 170)))
    for r in m.get_routes():
        b.add(Ui.oval(ax + r.get_start().x * s - 5, ay + r.get_start().y * s - 5, 10, 10, Ui.GREEN, Ui.GREEN))
        b.add(Ui.oval(ax + r.get_end().x * s - 5, ay + r.get_end().y * s - 5, 10, 10, Ui.RED, Ui.RED))
    ly = ay + ah + 30
    legend_f = Cyber.mono(Font.BOLD, 12)
    b.add(Ui.oval(ax, ly - 9, 10, 10, Ui.GREEN, Ui.GREEN))
    entry = Ui.label("ENTRY", ax + 16, ly, legend_f, Ui.TEXT)
    b.add(entry)
    ex = ax + 16 + entry.get_width() + 22
    b.add(Ui.oval(ex, ly - 9, 10, 10, Ui.RED, Ui.RED))
    b.add(Ui.label("EXIT", ex + 16, ly, legend_f, Ui.TEXT))
    screen.briefing = b
    rx = ax + aw + 36
    rw = px + pw - M.BRIEF_PAD - rx
    ty = py + 92
    name_f = MenuScreen.menu_font(Font.BOLD, 30)
    for line in Ui.wrap(m.get_name().upper(), name_f, rw):
        b.add(Ui.label(line, rx, ty, name_f, Ui.TEXT))
        ty += 34
    ty += 2
    badge = "DAILY RUN  /  " + m.get_difficulty().upper() + "  /  " + str(len(m.get_routes())) + \
        (" LANE" if len(m.get_routes()) == 1 else " LANES")
    bl = Ui.label(badge, rx + 8, ty, Cyber.display(Font.BOLD, 16), dc)
    b.add(Ui.rect(rx, ty - 15, bl.get_width() + 16, 22, Cyber.alpha(dc, 35), Cyber.alpha(dc, 160)))
    b.add(bl)
    ty += 40
    ty = screen.briefing_section("DAILY RUN", "One run a day, the same for everyone: today's seed, map, difficulty and "
                                 "rule are fixed. Push as far as you can; your best wave today is kept.", dc, rx, ty, rw)
    ty = screen.briefing_section("RULE OF THE DAY: " + daily.rule.chip, daily.rule.description, rc, rx, ty, rw)
    d = daily.difficulty
    ty = screen.briefing_section("DIFFICULTY GROWTH", d.label + "  -  " + d.subtitle, Cyber.YELLOW, rx, ty, rw)
    screen.briefing_section("MAP MECHANICS", m.get_mechanic_summary(), MenuScreen.CYAN, rx, ty, rw)
    band = RunSetupBand(b, ax, M.band_y(), pw - 2 * M.BRIEF_PAD, daily)
    dep = M.briefing_deploy_rect()
    best = DailyRecords.get().best(daily.date)
    b.add(Cyber.Chamfer(ax, dep[1], aw, dep[3], 14).scan(True).fill(Color(16, 10, 30, 235))
          .border(Cyber.alpha(Cyber.YELLOW if best > 0 else Cyber.DIM, 200)).line_width(1.6))
    bt = Ui.label(best_text(best), 0, 0, MenuScreen.menu_font(Font.BOLD, 18), Cyber.YELLOW if best > 0 else Cyber.MUTED)
    bt.set_location(ax + (aw - bt.get_width()) / 2, dep[1] + dep[3] / 2 + 7)
    b.add(bt)
    back = NeonButton(rx, dep[1], 150, dep[3], "BACK", MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN,
                      screen.close_briefing)
    go = NeonButton(dep[0], dep[1], dep[2], dep[3], "START DAILY", MenuScreen.menu_font(Font.BOLD, 22), dc,
                    lambda: screen.deploy(idx))
    b.add(back)
    b.add(go)
    return band, [back, go]


# ====================================================================== rule chips (run strip, end screen)
class RuleChip:
    """One rule chip: text, accent colour, and the title / micro line / description of its hover card."""

    def __init__(self, text, color, title, micro, description):
        self.text = text
        self.color = color
        self.title = title
        self.micro = micro
        self.description = description


def rule_chips(game, with_best=False):
    """Chips for the run's rules: the daily run (with today's best wave on the end screen), then each challenge."""
    out = []
    date = game.get_daily_date()
    if date is not None:
        dr = DailyRun(date)
        text = "DAILY " + dr.label()[4:10]
        if with_best:
            text += "  //  BEST WAVE " + str(max(DailyRecords.get().best(date), game.get_last_completed_wave()))
        out.append(RuleChip(text, Cyber.MAGENTA, "DAILY RUN", Cyber.spaced("daily run  //  " + dr.label()),
                            "Today's seed, map, difficulty and rule are the same for everyone. Your best wave today is "
                            "kept."))
    for c in game.get_challenges():
        out.append(RuleChip(c.chip, Color(c.rgb), c.title.upper(), Cyber.spaced("challenge rule"), c.description))
    return out


def fit_chips(chips, f, max_w, gap=6.0):
    """chips as they are if they fit in max_w, else one "RULES x N" chip whose hover card lists them all."""
    if len(chips) < 2 or sum(chip_width(c.text, f) + gap for c in chips) <= max_w:
        return chips
    return [RuleChip("RULES x" + str(len(chips)), Cyber.MAGENTA, "RUN RULES", Cyber.spaced("this run"),
                     "  +  ".join(c.title.title() if c.title.isupper() else c.title for c in chips) + ".")]


def chip_width(text, f):
    return Ui.label(text, 0, 0, f, Color.WHITE).get_width() + 18


def chip(into, rc, x, y, h, f):
    """One rule chip (the patch-note chip's shape, filled with the rule's colour), top-left at (x, y); returns its
    width."""
    w = chip_width(rc.text, f)
    into.add(Cyber.Chamfer(x, y, w, h, 5).scan(False).fill(Cyber.alpha(rc.color, 40)).border(Cyber.alpha(rc.color, 220)))
    into.add(Ui.label(rc.text, x + 9, y + h / 2 + f.get_size() * 0.36, f, Cyber.lerp(rc.color, Color.WHITE, 0.5)))
    return w


def chip_rows(into, chips, cx, y, max_w, h=22.0, f=None):
    """Centred rows of rule chips wrapping at max_w; returns the y below the last row (y when there are none)."""
    if not chips:
        return y
    f = Cyber.mono(Font.BOLD, 11) if f is None else f
    gap = 8.0
    rows, row, rw = [], [], 0.0
    for c in chips:
        w = chip_width(c.text, f)
        if row and rw + gap + w > max_w:
            rows.append(row)
            row, rw = [], 0.0
        rw += (gap if row else 0) + w
        row.append(c)
    rows.append(row)
    for r in rows:
        total = sum(chip_width(c.text, f) for c in r) + gap * (len(r) - 1)
        x = cx - total / 2
        for c in r:
            x += chip(into, c, x, y, h, f) + gap
        y += h + 6
    return y


def end_rows_height(game, max_w=640.0):
    """Height the end screen gives the rule chips (0 without rules)."""
    probe = GCompound()
    return chip_rows(probe, rule_chips(game, True), 0, 0, max_w)


def hover_card(rc):
    from lindefense.ui.patch_notes_view import PatchNotesView
    return PatchNotesView.hover_card(rc.title, rc.micro, rc.description, [], rc.color)
