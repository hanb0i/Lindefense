"""Lindefense RunStrip (ported from src/lindefense/ui/RunStrip.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.cyber import Cyber


class RunStrip(GCompound):
    """Slim strip under the top HUD bar, shown while run variance is on or the run has rules (daily run, challenges):
the run's patch version and one chip per active patch note on the left (hover for the full card), then one chip per
run rule (hover for its description), the "Breaking News" ticker on the right (hover for details), or the run seed
when the feed is quiet. A new headline also flashes the HUD banner once the draft overlay is gone.
The playfield shrinks by #height() (like the boss dock) so the strip never covers the map."""
    class Ticker(GObject):
        """One line of text that scrolls right to left inside a clipped window (static when it fits)."""
        def __init__(self):
            self.w = 0.0
            self.h = 0.0
            self.offset = 0.0
            self.text_w = 0.0
            self.loop_w = 0.0
            GObject.__init__(self)
            self.text = ''
            self.color = Color.WHITE
            pass
        def set(self, x, y, nw, nh, t, c):
            self.set_location(x, y)
            self.w = _j.dmax(0, nw)
            self.h = nh
            self.color = c
            if not (t == self.text):
                self.text = t
                self.offset = 0.0
                self.text_w = RunStrip.TICK_FONT.get_string_bounds(self.text, RunStrip.Ticker.FRC).get_width()
                self.loop_w = RunStrip.TICK_FONT.get_string_bounds(_j.cat(self.text, RunStrip.Ticker.GAP), RunStrip.Ticker.FRC).get_width()
        def scroll(self, dt):
            if self.text_w > self.w:
                self.offset = _j.fmod((self.offset + (dt * 55)), _j.dmax(1, self.loop_w))
        def get_bounds(self):
            return GRectangle(self.get_x(), self.get_y(), self.w, self.h)
        def paint(self, g):
            if (self.w <= 0) or (len(self.text) == 0):
                return
            g2 = g.create()
            try:
                Cyber.quality(g2)
                g2.clip(Rectangle2D.Double(self.get_x(), self.get_y(), self.w, self.h))
                g2.set_font(RunStrip.TICK_FONT)
                g2.set_color(self.color)
                base = ((self.get_y() + (self.h / 2)) + (RunStrip.TICK_FONT.get_size() * 0.36))
                if self.text_w <= self.w:
                    g2.draw_string(self.text, self.get_x(), base)
                else:
                    x = (self.get_x() - self.offset)
                    g2.draw_string(_j.cat(self.text, RunStrip.Ticker.GAP), x, base)
                    g2.draw_string(_j.cat(self.text, RunStrip.Ticker.GAP), (x + self.loop_w), base)
            finally:
                g2.dispose()
    def __init__(self, screen):
        self.screen = None
        self.game = None
        self.version_label = None
        self.news_tag = None
        self.news_tag_label = None
        self.quiet_label = None
        self.shown_news = None
        self.shown_news_wave = 0
        self.flash = 0.0
        self.time = 0.0
        GCompound.__init__(self)
        self.chips = GCompound()
        self.ticker = RunStrip.Ticker()
        self.tip = GCompound()
        self.chip_boxes = _j.ArrayList()
        self.chips_key = ''
        self.tip_key = ''
        self.news_x = RunStrip.NEWS_MIN_X
        self.announce_wait = (-1)
        self.screen = screen
        self.game = screen.get_game()
        self.rules = RunSetupView.rule_chips(self.game)   # fixed for the whole run
        self.shown_rules = self.rules
        self.rule_boxes = []
        y = Ui.WORLD_Y
        self.add(Ui.rect(0, y, Ui.WORLD_W, RunStrip.H, Color(6, 10, 22, 245), Color(6, 10, 22, 245)))
        self.add(Ui.rect(0, ((y + RunStrip.H) - 1), Ui.WORLD_W, 1, Cyber.EDGE, Cyber.EDGE))
        self.version_label = Ui.label('', 0, (y + 17), RunStrip.LABEL_FONT, Cyber.MUTED)
        self.add(self.version_label)
        self.add(self.chips)
        self.news_tag = Cyber.Chamfer(0, (y + 4), RunStrip.NEWS_TAG_W, 18, 3).fill(Cyber.RED).border(None)
        self.news_tag_label = Ui.label('BREAKING', 0, (y + 17), RunStrip.CHIP_FONT, Color.WHITE)
        self.add(self.news_tag)
        self.add(self.news_tag_label)
        self.add(self.ticker)
        self.quiet_label = Ui.label('', 0, (y + 17), RunStrip.LABEL_FONT, Cyber.DIM)
        self.add(self.quiet_label)
        self.tip.set_visible(False)
        self.add(self.tip)
        self.set_visible(False)
    def height(self):
        """Height the playfield gives up for the strip (0 while variance is off and the run has no rules)."""
        return RunStrip.H if (self.game.get_variance().is_enabled() or self.rules) else 0
    def update(self, dt):
        v = self.game.get_variance()
        on = (v.is_enabled() or bool(self.rules))
        if self.is_visible() != on:
            self.set_visible(on)
        if not on:
            return
        self.time += dt
        key = _j.cat(v.get_version(), v.get_active())
        if not (key == self.chips_key):
            self.chips_key = key
            self.rebuild_chips(v)
        self.update_news(v, dt)
        self.update_tip(v)
    def rebuild_chips(self, v):
        self.chips.remove_all()
        self.chip_boxes.clear()
        y = Ui.WORLD_Y
        Cyber.set_text(self.version_label, (_j.cat('Patch ', v.get_version()) if v.is_enabled() else 'Run rules'))
        self.version_label.set_location(12, (y + 17))
        x = ((6 + RunStrip.TAG_W) + 8)
        if (len(v.get_active()) == 0) and v.is_enabled():
            self.chips.add(Ui.label('No patch notes yet', x, (y + 17), RunStrip.LABEL_FONT, Cyber.DIM))
            x += 130
        # Freeplay keeps drafting (a note every 20 waves): past what fits, the oldest-first row ends in "+N" instead of
        # running under the news feed and off the playfield (the pause menu and end screen list every note)
        notes = v.get_active()
        limit = (Ui.WORLD_W - RunStrip.QUIET_W) - (RunStrip.RULES_RESERVE if self.rules else 0) - RunStrip.MORE_W
        for i in range(len(notes)):
            w = PatchNotesView.chip_width(notes[i].chip, RunStrip.CHIP_FONT)
            if (x + w) > (limit + (RunStrip.MORE_W if (i == (len(notes) - 1)) else 0)):
                self.chips.add(Ui.label(_j.cat('+', (len(notes) - i)), (x + 2), (y + 17), RunStrip.CHIP_FONT, Cyber.CYAN))
                x += RunStrip.MORE_W
                break
            w = PatchNotesView.chip(self.chips, notes[i], x, (y + 4), 18, RunStrip.CHIP_FONT)
            _j_add(self.chip_boxes, [x, w])
            x += (w + 6)
        self.rule_boxes = []
        self.shown_rules = RunSetupView.fit_chips(self.rules, RunStrip.CHIP_FONT, ((Ui.WORLD_W - RunStrip.QUIET_W) - (x + 11)))
        if self.rules and v.is_enabled():
            self.chips.add(Ui.rect((x + 2), (y + 7), 1, 12, Cyber.EDGE_HI, Cyber.EDGE_HI))
            x += 11
        for r in self.shown_rules:
            w = RunSetupView.chip(self.chips, r, x, (y + 4), 18, RunStrip.CHIP_FONT)
            self.rule_boxes.append([x, w])
            x += (w + 6)
        self.news_x = _j.dmax(RunStrip.NEWS_MIN_X, (x + 14))
    def update_news(self, v, dt):
        n = v.get_news()
        nw = v.get_news_wave()
        if (n is not self.shown_news) or ((n is not None) and (nw != self.shown_news_wave)):
            self.shown_news = n
            self.shown_news_wave = nw
            if n is not None:
                self.announce_wait = 0.0
                self.flash = 1.5
        y = Ui.WORLD_Y
        right = (Ui.WORLD_W - 6)
        has = (n is not None)
        self.news_tag.set_visible(has)
        self.news_tag_label.set_visible(has)
        self.ticker.set_visible(has)
        self.quiet_label.set_visible((not has))
        if not has:
            Cyber.set_text(self.quiet_label, (_j.cat('News feed quiet   ·   ', PatchNotesView.seed_text(self.game)) if v.is_enabled() else PatchNotesView.seed_text(self.game)))
            self.quiet_label.set_location((right - self.quiet_label.get_width()), (y + 17))
            self.announce_wait = (-1)
            return
        live = (self.game.get_wave_manager().is_wave_active() and (self.game.get_wave() == nw))
        self.news_tag.set_location(self.news_x, (y + 4))
        self.news_tag_label.set_location((self.news_x + ((RunStrip.NEWS_TAG_W - self.news_tag_label.get_width()) / 2)), (y + 17))
        self.flash = _j.dmax(0, (self.flash - dt))
        pulse = display_settings.calm(((0.5 + (0.5 * math.sin((self.time * 18)))) if (self.flash > 0) else (0.5 + (0.5 * math.sin((self.time * 3))))), (1.0 if (self.flash > 0) else 0.5))
        self.news_tag.fill(Cyber.alpha(Cyber.RED, _j.to_int((150 + (105 * pulse)))))
        self.ticker.set(((self.news_x + RunStrip.NEWS_TAG_W) + 8), (y + 3), (right - ((self.news_x + RunStrip.NEWS_TAG_W) + 8)), (RunStrip.H - 6), _j.cat(n.headline(nw), '   ·   ', n.flavor, '   ·   ', (_j.cat('LIVE ON WAVE ', nw) if live else _j.cat('INCOMING: WAVE ', nw))), (Color.WHITE if (self.flash > 0) else Cyber.lerp(Cyber.RED, Color.WHITE, 0.55)))
        self.ticker.scroll(dt)
        if (self.announce_wait >= 0) and (not v.is_draft_pending()):
            self.announce_wait += dt
            if (self.game.get_banner() is None) or (self.announce_wait > 3.0):
                self.screen.flash_banner(_j.cat('BREAKING NEWS: ', n.title.upper()), Cyber.RED, 3.2)
                self.flash = 1.2
                self.announce_wait = (-1)
    def update_tip(self, v):
        m = self.screen.get_mouse_logical()
        y = Ui.WORLD_Y
        chip = (-1)
        news = False
        ax = 0.0
        rule = (-1)
        if (m[1] >= y) and (m[1] <= (y + RunStrip.H)):
            for i in range(len(self.chip_boxes)):
                b = self.chip_boxes[i]
                if (m[0] >= b[0]) and (m[0] <= (b[0] + b[1])):
                    chip = i
                    ax = b[0]
            for i in range(len(self.rule_boxes)):
                b = self.rule_boxes[i]
                if (m[0] >= b[0]) and (m[0] <= (b[0] + b[1])):
                    rule = i
                    ax = b[0]
            if (((chip < 0) and (rule < 0)) and (v.get_news() is not None)) and (m[0] >= self.news_x):
                news = True
                ax = self.news_x
        live = (self.game.get_wave_manager().is_wave_active() and (self.game.get_wave() == v.get_news_wave()))
        key = (_j.cat('C', chip, '|', self.chips_key) if (chip >= 0) else (_j.cat('R', rule, '|', self.chips_key) if (rule >= 0) else (_j.cat('N', v.get_news(), '|', v.get_news_wave(), '|', live) if news else '')))
        if key == self.tip_key:
            return
        self.tip_key = key
        self.tip.remove_all()
        if len(key) == 0:
            self.tip.set_visible(False)
            return
        card = (PatchNotesView.note_card(v.get_active()[chip], v.get_picked_before(chip)) if (chip >= 0) else (RunSetupView.hover_card(self.shown_rules[rule]) if (rule >= 0) else PatchNotesView.news_card(v.get_news(), v.get_news_wave(), live)))
        w = card.get_width()
        card.set_location(_j.dmax(6, _j.dmin(((Ui.WORLD_W - w) - 6), ax)), ((y + RunStrip.H) + 6))
        self.tip.add(card)
        self.tip.set_visible(True)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.patch_notes_view import PatchNotesView  # noqa: E402
from lindefense.ui import run_setup_view as RunSetupView  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402

RunStrip.serial_version_uid = 1
RunStrip.H = 26.0
RunStrip.CHIP_FONT = Cyber.mono(Font.BOLD, 10)
RunStrip.TICK_FONT = Cyber.mono(Font.BOLD, 12)
RunStrip.TAG_W = 92.0
RunStrip.LABEL_FONT = Cyber.body(Font.PLAIN, 12)
RunStrip.NEWS_TAG_W = 88.0
RunStrip.NEWS_MIN_X = 640.0
RunStrip.QUIET_W = 240.0
RunStrip.MORE_W = 34.0          # the "+N" after the patch-note chips that do not fit
RunStrip.RULES_RESERVE = 130.0  # room kept for the run-rule chips (one "RULES xN" chip when they do not fit)
RunStrip.Ticker.serial_version_uid = 1
RunStrip.Ticker.GAP = '      +      '
RunStrip.Ticker.FRC = FontRenderContext(None, True, True)
