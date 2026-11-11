"""CAMPAIGN (main menu): the level path and each level's briefing.

A 4 x 4 grid of cards read as one winding path (left to right, then back right to left, ...): an optional BOOT CAMP card
(the tutorial) and the 15 campaign levels. Every level card shows its state (locked / available / completed), the best
stars, a map thumbnail, the wave count and the first-clear reward. Clicking an available or completed level opens its
briefing (map preview, waves, starting cash and integrity, threats, the towers available and the reward); START plays
it. Esc closes the briefing, then returns to the main menu; Enter starts the briefed level.

The screen takes the app's map-select slot (the same input routing: mouse_pressed / mouse_moved / key_pressed /
frame / is_typing). It is drawn flat with the shared helpers only (Cyber.Chamfer with one fill and one thin border,
UIButton, Ui labels; sentence-case headings), so the minimalist restyle of those helpers carries over."""
from lindefense.map import maps
from lindefense.map.game_map import HEIGHT as MAP_H, WIDTH as MAP_W
from lindefense.sim import campaign
from lindefense.sim.campaign import CampaignProgress
from lindefense.tower import catalog
from lindefense.ui import jrt as _j
from lindefense.ui.acm import GCompound, GLine
from lindefense.ui.jawt import Color, Font, KeyEvent

COLS = 4
ROWS = 4
GRID_X = 25.0
GRID_TOP = 122.0
GRID_BOTTOM = 976.0
GAP_X = 22.0
GAP_Y = 18.0
CARD_W = (1600 - 2 * GRID_X - (COLS - 1) * GAP_X) / COLS
CARD_H = (GRID_BOTTOM - GRID_TOP - (ROWS - 1) * GAP_Y) / ROWS
THUMB_W = 156.0
THUMB_H = THUMB_W * MAP_H / MAP_W

BRIEF_W = 1120.0
BRIEF_H = 840.0
BRIEF_X = (1600 - BRIEF_W) / 2
BRIEF_Y = (1000 - BRIEF_H) / 2
BRIEF_PAD = 34.0
BRIEF_ART_W = 560.0

CARD_FILL = Color(9, 14, 30)
CARD_FILL_LOCKED = Color(7, 10, 20)
BOOT_CAMP = "boot_camp"
DIFFICULTY_RGB = {"Beginner": 0x3bff8a, "Intermediate": 0xffe94a, "Advanced": 0xff8c3b, "Expert": 0xff2bd6}


def flat(x, y, w, h, cut, fill, border, lw=1.2):
    """A flat panel: one fill and one thin border."""
    from lindefense.ui.cyber import Cyber
    c = Cyber.Chamfer(x, y, w, h, cut).fill(fill).border(border).line_width(lw)
    if hasattr(c, "scan"):   # the pre-restyle Chamfer draws scanlines unless told not to (the restyle removed them)
        c.scan(False)
    return c


def difficulty_color(m):
    return Color(DIFFICULTY_RGB.get(m.get_difficulty(), 0xff2bd6))


def button(x, y, w, h, text, size, accent, action, primary=False):
    from lindefense.ui.cyber import Cyber
    from lindefense.ui.ui_button import UIButton
    b = UIButton(x, y, w, h, text, Cyber.display(Font.BOLD, size), action)
    b.set_accent(accent)
    b.set_primary(primary)
    return b


def slot_rect(i):
    """(x, y, w, h) of path position i (0 = BOOT CAMP, then level i) in the snake-ordered grid."""
    row, k = divmod(i, COLS)
    col = k if row % 2 == 0 else COLS - 1 - k
    return (GRID_X + col * (CARD_W + GAP_X), GRID_TOP + row * (CARD_H + GAP_Y), CARD_W, CARD_H)


def stars_row(into, x, cy, r, n, lit_col, dim_col, gap=6.0):
    """Three stars from x (left) on the line cy, the first n lit. Returns the right edge."""
    from lindefense.ui import run_report_view as RunReportView
    for i in range(3):
        cx = x + r + i * (2 * r + gap)
        into.add(RunReportView.star(cx, cy, r, lit_col if i < n else dim_col))
    return x + 3 * 2 * r + 2 * gap


def tower_icon(t, x, y, size, dim=False):
    """A shop tower's tier-0 art in a size x size box with top-left (x, y); dim: veiled (a locked reward)."""
    from lindefense.ui.sprites.towers.tower_icons import TowerIcons
    from lindefense.ui.ui import Ui
    g = GCompound()
    g.add(TowerIcons.create(t, 0, size), size / 2, size / 2)
    if dim:
        g.add(Ui.oval(size * 0.12, size * 0.12, size * 0.76, size * 0.76, Color(5, 9, 22, 175), Color(5, 9, 22, 0)))
    g.set_location(x, y)
    return g


class CampaignScreen(GCompound):
    """The campaign path (see the module docstring). app: the LindefenseApp (show_menu, start_campaign_level,
    start_tutorial); progress: the CampaignProgress shown (default: the saved one); briefing: a level (id / index) whose
    briefing opens at once (NEXT LEVEL on the level-complete panel)."""

    def __init__(self, app, progress=None, briefing=None):
        from lindefense.ui.audio_toggle import AudioToggle
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.menu_screen import MenuScreen
        from lindefense.ui.ui import Ui
        GCompound.__init__(self)
        self.app = app
        self.progress = CampaignProgress.persistent() if progress is None else progress
        self.buttons = []
        self.chips = []
        self.cards = []            # (rect, level id or BOOT_CAMP, frame, base border colour, clickable)
        self.hover_id = None
        self.briefing = None
        self.briefing_level = None
        self.briefing_buttons = []
        self.t = 0.0
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, MenuScreen.BG, MenuScreen.BG))
        title = Ui.label("Campaign", 0, 0, Cyber.display(Font.BOLD, 34), Cyber.CYAN)
        title.set_location((Ui.W - title.get_width()) / 2, 64)
        self.add(title)
        p = self.progress
        sub = Ui.label("Levels %d / %d  \u00b7  Stars %d / %d  \u00b7  Towers %d / %d" % (
            p.completed_count(), len(campaign.LEVELS), p.total_stars(), 3 * len(campaign.LEVELS),
            len(p.unlocked_towers()), len(campaign.TowerType.shop_towers())), 0, 0, Cyber.body(Font.PLAIN, 15), Cyber.MUTED)
        sub.set_location((Ui.W - sub.get_width()) / 2, 92)
        self.add(sub)
        back = button(25, 28, 130, 42, "BACK", 18, Cyber.CYAN, lambda: self.app.show_menu())
        self.buttons.append(back)
        self.add(back)
        self.audio_toggles = AudioToggle.pair(Ui.W - 25 - 2 * 118 - 8, 28, 118, 42, 8, "SOUND", "MUSIC", self.chips)
        for c in self.chips:
            self.add(c)
        self.build_path()
        if briefing is not None:
            lv = campaign.level(briefing)
            if lv is not None and self.progress.state(lv) != "locked":
                self.open_briefing(lv)

    # ---------------------------------------------------------------- the path
    def build_path(self):
        from lindefense.ui.cyber import Cyber
        nodes = [BOOT_CAMP] + list(campaign.LEVELS)
        # connectors first, under the cards: lit once the level they lead to is playable
        for i in range(len(nodes) - 1):
            ax, ay, aw, ah = slot_rect(i)
            bx, by, bw, bh = slot_rect(i + 1)
            nxt = nodes[i + 1]
            lit = self.progress.state(nxt) != "locked"
            col = Cyber.alpha(Cyber.CYAN, 150) if lit else Cyber.alpha(Cyber.DIM, 110)
            if abs(ay - by) < 1:      # same row
                y = ay + ah / 2
                x0, x1 = (ax + aw, bx) if bx > ax else (bx + bw, ax)
                ln = GLine(x0, y, x1, y)
            else:                     # down to the next row, at the row's end
                x = ax + aw / 2
                ln = GLine(x, ay + ah, x, by)
            ln.set_color(col)
            self.add(ln)
        for i, node in enumerate(nodes):
            x, y, w, h = slot_rect(i)
            if node == BOOT_CAMP:
                self.build_boot_camp(x, y, w, h)
            else:
                self.build_card(node, x, y, w, h)

    def build_boot_camp(self, x, y, w, h):
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.map_art import MapArt
        from lindefense.ui.ui import Ui
        acc = Cyber.GREEN
        frame = flat(x, y, w, h, 12, CARD_FILL, Cyber.alpha(acc, 150))
        self.add(frame)
        tx, ty = x + 14, y + 14
        self.add(MapArt(maps.create(0), tx, ty, THUMB_W, THUMB_H))
        self.add(Ui.rect(tx, ty, THUMB_W, THUMB_H, None, Cyber.alpha(acc, 90)))
        rx = tx + THUMB_W + 16
        rw = x + w - 14 - rx
        self.add(Ui.label("Optional", rx, y + 30, Cyber.body(Font.BOLD, 13), Cyber.alpha(acc, 230)))
        self.add(Ui.label("Boot Camp", rx, y + 58, Cyber.display(Font.BOLD, 24), Cyber.TEXT))
        yy = y + 84
        for line in list(Ui.wrap("The guided tutorial: build, upgrade, target and start waves.", Cyber.body(Font.PLAIN, 13), rw))[:3]:
            self.add(Ui.label(line, rx, yy, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
            yy += 17
        done = self.progress.boot_camp_done()
        self.add(Ui.label("Done  \u00b7  play it again" if done else "Start the tutorial", x + 14, y + h - 16,
                          Cyber.body(Font.BOLD, 14), acc))
        self.cards.append(((x, y, w, h), BOOT_CAMP, frame, Cyber.alpha(acc, 150), True))

    def build_card(self, lv, x, y, w, h):
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.map_art import MapArt
        from lindefense.ui.ui import Ui
        state = self.progress.state(lv)
        locked = state == "locked"
        done = state == "completed"
        acc = Cyber.YELLOW if done else (Cyber.CYAN if not locked else Cyber.DIM)
        border = Cyber.alpha(acc, 170 if not locked else 110)
        frame = flat(x, y, w, h, 12, CARD_FILL_LOCKED if locked else CARD_FILL, border, 1.6 if state == "available" else 1.2)
        self.add(frame)
        m = maps.create(lv.map_index)
        tx, ty = x + 14, y + 14
        self.add(MapArt(m, tx, ty, THUMB_W, THUMB_H))
        if locked:
            self.add(Ui.rect(tx, ty, THUMB_W, THUMB_H, Color(5, 8, 18, 175), Cyber.alpha(Cyber.DIM, 120)))
        else:
            self.add(Ui.rect(tx, ty, THUMB_W, THUMB_H, None, Cyber.alpha(acc, 90)))
        dc = difficulty_color(m)
        from lindefense.ui.catalog_screen import CatalogScreen
        rx = tx + THUMB_W + 16
        rw = x + w - 14 - rx
        head = "Level %d" % lv.index + ("  \u00b7  Finale" if lv.is_finale() else "")
        self.add(Ui.label(head, rx, y + 30, Cyber.body(Font.BOLD, 13), Cyber.alpha(acc, 230)))
        tf = CatalogScreen.fit_font(lv.title, Cyber.display(Font.BOLD, 23), rw, 12)
        self.add(Ui.label(lv.title, rx, y + 55, tf, Cyber.TEXT if not locked else Cyber.MUTED))
        waves = "%d waves  \u00b7  %s" % (lv.wave_count(), lv.kind().capitalize())
        self.add(Ui.label(waves, rx, y + 77, Cyber.body(Font.BOLD, 13), Cyber.TEXT if not locked else Cyber.DIM))
        # the map: a difficulty-coloured mark and its name
        self.add(Ui.rect(rx, y + 89, 3, 11, dc if not locked else Cyber.DIM, dc if not locked else Cyber.DIM))
        nf = CatalogScreen.fit_font(m.get_name(), Cyber.body(Font.PLAIN, 13), rw - 9, 10)
        self.add(Ui.label(m.get_name(), rx + 9, y + 99, nf, Cyber.MUTED if not locked else Cyber.DIM))
        best = self.progress.best_stars(lv)
        stars_row(self, rx, y + 122, 10, best, Cyber.YELLOW, Cyber.alpha(Cyber.DIM, 150 if not locked else 90))
        tag = "Play" if state == "available" else ("Locked" if locked else "")
        if tag:
            tl = Ui.label(tag, 0, 0, Cyber.body(Font.BOLD, 14), Cyber.CYAN if not locked else Cyber.DIM)
            tl.set_location(x + w - 14 - tl.get_width(), y + 127)
            self.add(tl)
        # reward strip along the bottom
        ry = y + h - 44
        self.add(Ui.rect(x + 14, ry - 8, w - 28, 1, Cyber.alpha(acc, 60), Cyber.alpha(acc, 60)))
        if lv.is_finale():
            self.add(Ui.label("Defeat Palantir to finish the campaign", x + 14, ry + 22, Cyber.body(Font.BOLD, 13),
                              Cyber.alpha(Cyber.MAGENTA, 220) if not locked else Cyber.DIM))
        else:
            lab = "Unlocked" if done else "Reward"
            self.add(Ui.label(lab, x + 14, ry + 22, Cyber.body(Font.BOLD, 12), Cyber.alpha(acc, 200)))
            ix = x + 14 + 78
            for t in lv.reward:
                self.add(tower_icon(t, ix, ry + 2, 30, dim=locked))
                ix += 34
            extra = ", ".join(t.display_name for t in lv.reward)
            if lv.reward_heroes:
                extra += " + Hero Store"
            if lv.reward_abilities:
                extra += " + abilities"
            ef = CatalogScreen.fit_font(extra, Cyber.body(Font.BOLD, 13), x + w - 14 - ix - 4, 10)
            self.add(Ui.label(extra, ix + 4, ry + 22, ef, Cyber.TEXT if not locked else Cyber.DIM))
        self.cards.append(((x, y, w, h), lv.id, frame, border, not locked))

    # ---------------------------------------------------------------- briefing
    def is_briefing_open(self):
        return self.briefing is not None

    def get_briefing_level(self):
        return self.briefing_level

    def open_briefing(self, lv):
        """The level briefing popup: map preview, waves, starting cash and integrity, threats, towers, reward; START."""
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.map_art import MapArt
        from lindefense.ui.ui import Ui
        self.close_briefing()
        lv = campaign.level(lv)
        self.briefing_level = lv
        b = self.briefing = GCompound()
        m = maps.create(lv.map_index)
        dc = difficulty_color(m)
        b.add(Ui.rect(0, 0, Ui.W, Ui.H, Ui.c(0x02040a, 215), Ui.c(0x000000, 0)))
        px, py, pw, ph = BRIEF_X, BRIEF_Y, BRIEF_W, BRIEF_H
        b.add(flat(px, py, pw, ph, 20, Color(6, 10, 24, 250), Cyber.alpha(Cyber.CYAN, 190), 1.6))
        b.add(Ui.label("Level %d of %d  \u00b7  %s  \u00b7  war waves %d-%d" % (lv.index, len(campaign.LEVELS), lv.kind().capitalize(),
                                                                       lv.bases[0], lv.bases[-1]),
                       px + BRIEF_PAD, py + 42, Cyber.body(Font.BOLD, 14), Cyber.alpha(Cyber.MAGENTA, 230)))
        # left: the map
        ax, ay = px + BRIEF_PAD, py + 62
        aw = BRIEF_ART_W
        ah = aw * MAP_H / MAP_W
        s = aw / MAP_W
        b.add(MapArt(m, ax, ay, aw, ah))
        b.add(Ui.rect(ax, ay, aw, ah, None, Cyber.alpha(dc, 170)))
        for r in m.get_routes():
            b.add(Ui.oval(ax + r.get_start().x * s - 5, ay + r.get_start().y * s - 5, 10, 10, Ui.GREEN, Ui.GREEN))
            b.add(Ui.oval(ax + r.get_end().x * s - 5, ay + r.get_end().y * s - 5, 10, 10, Ui.RED, Ui.RED))
        ty = ay + ah + 30
        b.add(Ui.label(m.get_name(), ax, ty, Cyber.display(Font.BOLD, 21), Cyber.TEXT))
        badge = "%s  \u00b7  %d %s" % (m.get_difficulty(), len(m.get_routes()), "lane" if len(m.get_routes()) == 1 else "lanes")
        bl = Ui.label(badge, 0, ty, Cyber.body(Font.BOLD, 14), dc)
        bl.set_location(ax + aw - bl.get_width(), ty)
        b.add(bl)
        ty += 24
        for line in list(Ui.wrap(m.get_mechanic_summary(), Cyber.body(Font.PLAIN, 14), aw))[:3]:
            b.add(Ui.label(line, ax, ty, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
            ty += 19
        self._wave_strip(b, lv, ax, ty + 30, aw)
        # right column
        rx = ax + aw + 34
        rw = px + pw - BRIEF_PAD - rx
        y = py + 86
        b.add(Ui.label("Level %d" % lv.index, rx, y - 22, Cyber.body(Font.BOLD, 14), Cyber.CYAN))
        tf = Cyber.display(Font.BOLD, 36)
        for line in Ui.wrap(lv.title, tf, rw):
            b.add(Ui.label(line, rx, y + 10, tf, Cyber.TEXT))
            y += 38
        y += 12
        for line in Ui.wrap(lv.flavour, Cyber.body(Font.PLAIN, 16), rw):
            b.add(Ui.label(line, rx, y, Cyber.body(Font.PLAIN, 16), Cyber.TEXT))
            y += 21
        y += 14
        # numbers: waves, starting cash, integrity, the slice of the war it plays
        cells = (("Waves", "%d" % lv.wave_count(), Cyber.CYAN), ("Start cash", Ui.money(lv.start_cash), Cyber.YELLOW),
                 ("Integrity", "%d" % lv.start_lives, Cyber.RED),
                 ("Enemy health", lv.hp_text(), Cyber.MAGENTA))   # of their health at those waves in CLASSIC
        cw = (rw - 3 * 8) / 4
        for i, (lab, val, col) in enumerate(cells):
            cx = rx + i * (cw + 8)
            b.add(flat(cx, y, cw, 54, 7, Color(8, 14, 32, 235), Cyber.alpha(col, 150)))
            b.add(Ui.label(lab, cx + 9, y + 18, Cyber.body(Font.BOLD, 12), Cyber.alpha(col, 220)))
            vf = Cyber.mono(Font.BOLD, 18)
            from lindefense.ui.catalog_screen import CatalogScreen
            vf = CatalogScreen.fit_font(val, vf, cw - 16, 11)
            b.add(Ui.label(val, cx + 9, y + 42, vf, Cyber.TEXT))
        y += 78
        y = self._threat_line(b, lv, rx, y, rw)
        y = self._towers_block(b, lv, rx, y, rw)
        y = self._reward_block(b, lv, rx, y, rw)
        best = self.progress.best_stars(lv)
        if best > 0:
            b.add(Ui.label("Best", rx, py + ph - 100, Cyber.body(Font.BOLD, 13), Cyber.MUTED))
            stars_row(b, rx + 44, py + ph - 104, 9, best, Cyber.YELLOW, Cyber.alpha(Cyber.DIM, 150))
        back = button(rx, py + ph - 82, 150, 52, "BACK", 18, Cyber.CYAN, self.close_briefing)
        go = button(rx + 166, py + ph - 82, rw - 166, 52, "START", 22, Cyber.YELLOW, lambda: self.start(lv), True)
        self.briefing_buttons = [back, go]
        b.add(back)
        b.add(go)
        self.add(b)

    def _wave_strip(self, b, lv, x, y, w):
        """WAVE PLAN: one cell per wave, boss waves filled yellow; dots mark camo (magenta) and prompt injection (red)."""
        from lindefense.enemy.types import Modifier
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        y = self._section(b, "Wave plan", x, y, Cyber.CYAN) + 6
        n = lv.wave_count()
        gap = 3.0 if n <= 24 else 2.0
        cw = (w - (n - 1) * gap) / n
        for i, wv in enumerate(lv.waves()):
            cx = x + i * (cw + gap)
            boss = wv.contains_boss()
            fill = Cyber.alpha(Cyber.YELLOW, 200) if boss else Color(14, 24, 46)
            b.add(flat(cx, y, cw, 26, 0, fill, Cyber.alpha(Cyber.YELLOW if boss else Cyber.CYAN, 150), 1.0))
            camo = any(Modifier.CAMO in g.modifiers or g.type.has_innate_camo() for g in wv.groups)
            inj = any(Modifier.INJECTION in g.modifiers for g in wv.groups)
            d = min(6.0, cw / 3)
            if camo:
                b.add(Ui.oval(cx + cw / 2 - d - 1, y + 32, d, d, Cyber.MAGENTA, Cyber.MAGENTA))
            if inj:
                b.add(Ui.oval(cx + cw / 2 + 1, y + 32, d, d, Cyber.RED, Cyber.RED))
        y += 58
        lx = x
        for col, text in ((Cyber.YELLOW, "Boss"), (Cyber.MAGENTA, "Camo"), (Cyber.RED, "Prompt injection")):
            b.add(Ui.oval(lx, y - 9, 8, 8, col, col))
            lab = Ui.label(text, lx + 13, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
            b.add(lab)
            lx += 13 + lab.get_width() + 18
        lo, hi = lv.hp_range()
        if lo < 1 or hi < 1:
            text = ("Enemies have %s of their CLASSIC health at these war waves%s; your build grows with the level's "
                    "income." % (lv.hp_text(), ", rising wave by wave" if hi > lo else ""))
            y += 10
            for line in list(Ui.wrap(text, Cyber.body(Font.PLAIN, 13), w))[:2]:
                y += 18
                b.add(Ui.label(line, x, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
        return y

    def _section(self, b, text, x, y, col):
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        b.add(Ui.label(text, x, y, Cyber.body(Font.BOLD, 14), Cyber.alpha(col, 235)))
        return y + 14

    def _threat_line(self, b, lv, x, y, w):
        """THREATS: chips for camo / Lead / fortified / regrow / prompt injection, and the bosses with their waves."""
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        th = lv.threats()
        y = self._section(b, "Threats", x, y, Cyber.RED)
        chips = [(k.capitalize() if k != "injection" else "Prompt injection") for k in ("camo", "lead", "fortified", "regrow", "injection") if th[k] > 0]
        if not chips:
            chips = ["None: data structures only"]
        cx = x
        f = Cyber.body(Font.BOLD, 13)
        for c in chips:
            lab = Ui.label(c, 0, 0, f, Cyber.TEXT)
            cw = lab.get_width() + 16
            if cx + cw > x + w:
                cx = x
                y += 26
            b.add(flat(cx, y, cw, 20, 4, Cyber.alpha(Cyber.RED, 28), Cyber.alpha(Cyber.RED, 150), 1.0))
            lab.set_location(cx + 8, y + 14)
            b.add(lab)
            cx += cw + 6
        y += 40
        if th["bosses"]:
            seen = []
            for wn, t in th["bosses"]:
                if t not in [s for s, _ in seen]:
                    seen.append((t, wn))
            text = "Bosses: " + ", ".join("%s (wave %d)" % (t.display_name, wn) for t, wn in seen)
            for line in list(Ui.wrap(text, Cyber.body(Font.PLAIN, 14), w))[:2]:
                b.add(Ui.label(line, x, y, Cyber.body(Font.PLAIN, 14), Cyber.alpha(Cyber.YELLOW, 235)))
                y += 19
            y += 10
        return y

    def _towers_block(self, b, lv, x, y, w):
        """TOWERS AVAILABLE: the icons and names of the level's towers; heroes and abilities on one line."""
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        allowed = lv.towers()
        y = self._section(b, "Towers available  %d / %d" % (len(allowed), len(campaign.TowerType.shop_towers())), x, y, Cyber.CYAN)
        size = 38.0
        per_row = 9
        gap = (w - per_row * size) / (per_row - 1)
        for i, t in enumerate(allowed):
            r, c = divmod(i, per_row)
            ix, iy = x + c * (size + gap), y + 4 + r * (size + 6)
            b.add(flat(ix, iy, size, size, 5, Color(10, 18, 36), Cyber.alpha(Ui.c(t.faction.rgb), 120), 1.0))
            b.add(tower_icon(t, ix + 2, iy + 2, size - 4))
        rows = (len(allowed) + per_row - 1) // per_row
        y += 4 + rows * (size + 6) + 12
        names = ", ".join(t.display_name for t in allowed)
        for line in list(Ui.wrap(names, Cyber.body(Font.PLAIN, 13), w))[:3]:
            b.add(Ui.label(line, x, y, Cyber.body(Font.PLAIN, 13), Cyber.TEXT))
            y += 17
        y += 4
        heroes = "Hero Store open" if lv.heroes_allowed() else "Hero Store opens after level %d" % campaign.heroes_level().index
        abil = "$15,000 abilities on" if lv.abilities_allowed() else "abilities open after level %d" % campaign.abilities_level().index
        b.add(Ui.label(heroes + "  \u00b7  " + abil, x, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))
        return y + 26

    def _reward_block(self, b, lv, x, y, w):
        from lindefense.ui.cyber import Cyber
        from lindefense.ui.ui import Ui
        y = self._section(b, "First clear unlocks" if not lv.is_finale() else "The finale", x, y, Cyber.YELLOW)
        if lv.is_finale():
            for line in list(Ui.wrap("Defeat Palantir to finish the campaign. Every tower is yours.", Cyber.body(Font.PLAIN, 15), w))[:2]:
                b.add(Ui.label(line, x, y + 16, Cyber.body(Font.PLAIN, 15), Cyber.TEXT))
                y += 20
            return y + 20
        ix = x
        for t in lv.reward:
            b.add(tower_icon(t, ix, y + 2, 34))
            ix += 40
        txt = lv.reward_text()
        from lindefense.ui.catalog_screen import CatalogScreen
        f = CatalogScreen.fit_font(txt, Cyber.body(Font.BOLD, 15), x + w - ix - 6, 10)
        b.add(Ui.label(txt, ix + 6, y + 25, f, Cyber.TEXT))
        return y + 50

    def close_briefing(self):
        if self.briefing is None:
            return
        self.remove(self.briefing)
        self.briefing = None
        self.briefing_level = None
        self.briefing_buttons = []

    def start(self, lv):
        """START: plays the level (the app builds the game)."""
        if self.app is not None and hasattr(self.app, "start_campaign_level"):
            self.app.start_campaign_level(campaign.level(lv).id)

    def activate(self, node):
        """A click on a card: BOOT CAMP starts the tutorial, a playable level opens its briefing."""
        from lindefense.audio.audio_manager import AudioManager
        from lindefense.audio.sfx import Sfx
        if node == BOOT_CAMP:
            if self.app is not None:
                self.app.start_tutorial()
            return
        AudioManager.sfx(Sfx.UI_SELECT)
        self.open_briefing(node)

    # ---------------------------------------------------------------- input / frame
    def is_typing(self):
        return False

    def card_at(self, lx, ly):
        for (x, y, w, h), node, frame, border, ok in self.cards:
            if x <= lx <= x + w and y <= ly <= y + h:
                return node, ok
        return None, False

    def mouse_pressed(self, lx, ly):
        if self.briefing is not None:
            for b in list(self.briefing_buttons):
                if b.hit(lx, ly):
                    b.click()
                    return
            return
        for c in self.chips:
            if c.hit(lx, ly):
                c.click()
                return
        for b in self.buttons:
            if b.hit(lx, ly):
                b.click()
                return
        node, ok = self.card_at(lx, ly)
        if node is not None and ok:
            self.activate(node)
        elif node is not None:
            from lindefense.audio.audio_manager import AudioManager
            from lindefense.audio.sfx import Sfx
            AudioManager.sfx(Sfx.INVALID)

    def mouse_moved(self, lx, ly):
        from lindefense.ui.cyber import Cyber
        if self.briefing is not None:
            for b in self.briefing_buttons:
                b.set_hover(b.hit(lx, ly))
            for b in self.buttons:
                b.set_hover(False)
            return
        for b in self.buttons:
            b.set_hover(b.hit(lx, ly))
        for c in self.chips:
            c.set_hover(c.hit(lx, ly))
        node, ok = self.card_at(lx, ly)
        hover = node if ok else None
        if hover != self.hover_id:
            self.hover_id = hover
            for _r, n, frame, border, _ok in self.cards:
                frame.border(Cyber.lerp(border, Color.WHITE, 0.45) if n == hover else border)

    def mouse_dragged(self, lx, ly):
        pass

    def mouse_released(self):
        pass

    def key_pressed(self, e):
        k = e.get_key_code()
        if k == KeyEvent.VK_ESCAPE:
            if self.briefing is not None:
                self.close_briefing()
            elif self.app is not None:
                self.app.show_menu()
        elif k == KeyEvent.VK_ENTER:
            if self.briefing is not None:
                self.start(self.briefing_level)
            else:
                nxt = self.progress.next_level()
                if nxt is not None:
                    self.open_briefing(nxt)

    def frame(self, dt):
        from lindefense.ui.audio_toggle import AudioToggle
        self.t += dt
        for b in self.buttons + self.briefing_buttons:
            b.animate(dt)
        AudioToggle.sync_all(self.audio_toggles)
        for c in self.chips:
            c.animate(dt)
