"""Lindefense MapSelectScreen (ported from src/lindefense/ui/MapSelectScreen.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai.units import DefenderProfile
from lindefense.map import maps
from lindefense.map.game_map import GameMap
from lindefense.sim import records
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.records import Records
from lindefense.sim.run_setup import DailyRun, RunOptions, RunSetup
from lindefense.ui.ui import Ui
import lindefense.ai.reverse_match as _m_reverse_match


class MapSelectScreen(GCompound):
    """Map selection: a 4-column grid of cards (as many rows as
MapCatalog#MAP_COUNT needs) with a miniature track preview, name,
colour-coded difficulty badge and lane count, styled to match the cyberpunk
title card. A card's DEPLOY button opens a mission briefing popup (large
preview, description, map mechanics, chosen Difficulty Growth mode) whose own
DEPLOY starts the match; BACK or Esc closes it. All geometry is in logical
coordinates so hit-testing stays correct at any window size."""
    def __init__(self, app):
        self.audio_toggles = None
        self.mark = None
        self.t = 0.0
        self.difficulty = None
        self.app = None
        self.maps = None
        self.briefing = None
        self.briefing_reverse = False
        self.briefing_daily = False
        self.run_setup = None
        self.daily = DailyRun.today()
        GCompound.__init__(self)
        self.buttons = _j.ArrayList()
        self.chips = _j.ArrayList()
        self.briefing_buttons = _j.ArrayList()
        self.briefing_map = (-1)
        self.records = Records.persistent()
        self.best_labels = []        # (label, map name, right edge, baseline) of each card's BEST readout
        self.medal_marks = {}        # map name -> its card's four medal frames (Difficulty order)
        self.app = app
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, MenuScreen.BG, MenuScreen.BG))
        self.add(Cyber.Grid(0, 0, Ui.W, Ui.H, 40, Ui.with_alpha(MenuScreen.CYAN, 6)))
        title = Ui.label('SELECT A MAP', 0, 0, MenuScreen.menu_font(Font.BOLD, 30), Cyber.TEXT)
        title.set_location((((Ui.W - title.get_width()) / 2) + 30), 64)
        self.add(title)
        self.mark = LogoEmblem(52)
        self.mark.set_location((((Ui.W - title.get_width()) / 2) - 18), 52)
        self.add(self.mark)
        small = LogoWordmark(22, Color(0xeafcff), None, True)
        small.set_location((Ui.W - 190), 46)
        self.add(small)
        self.maps = maps.create_all()
        n = len(self.maps)
        rows = max(1, _j.idiv(((n + MapSelectScreen.COLS) - 1), MapSelectScreen.COLS))
        self.difficulty = DifficultySelector(25, 104, (Ui.W - 50))
        self.add(self.difficulty)
        top = ((104 + DifficultySelector.HEIGHT) + 40)
        bottom = (Ui.H - 28)
        gap = 18.0
        card_w = (((Ui.W - 50) - (gap * (MapSelectScreen.COLS - 1))) / MapSelectScreen.COLS)
        card_h = _j.dmin((540 if (rows == 1) else 520), (((bottom - top) - (gap * (rows - 1))) / rows))
        top += _j.dmax(0, ((((((bottom - top) - (gap * (rows - 1))) / rows) - card_h) * 0.35) * rows))
        order = MapSelectScreen.display_order(self.maps)
        for pos in range(n):
            idx = order[pos]
            m = self.maps[idx]
            col = _j.imod(pos, MapSelectScreen.COLS)
            row = _j.idiv(pos, MapSelectScreen.COLS)
            self.build_card(app, m, idx, (25 + (col * (card_w + gap))), (top + (row * (card_h + gap))), card_w, card_h)
        if _j.imod(n, MapSelectScreen.COLS) != 0:   # the DAILY RUN card takes the free grid slot after the last map
            daily = RunSetupView.build_daily_card(self, self.daily, (25 + (_j.imod(n, MapSelectScreen.COLS) * (card_w + gap))), (top + (_j.idiv(n, MapSelectScreen.COLS) * (card_h + gap))), card_w, card_h)
        else:
            daily = NeonButton(420, 28, 170, 42, 'DAILY RUN', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN, _j.Fn(self.open_daily_briefing))
            self.add(daily)
        _j_add(self.buttons, daily)
        back = NeonButton(25, 28, 130, 42, 'BACK', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN, _j.Fn(lambda *, app=app: app.show_menu()))
        _j_add(self.buttons, back)
        self.add(back)
        self.audio_toggles = AudioToggle.pair(168, 28, 118, 42, 8, 'SOUND', 'MUSIC', self.chips)
        for c in self.chips:
            self.add(c)
    @staticmethod
    def deploy_center(idx):
        """Logical centre of a map card's DEPLOY button, for tools that click through the real UI (the demo driver). Mirrors the
layout in the constructor. idx is the underlying catalog index (as passed to LindefenseProgram#startGame),
not the grid position: it is resolved through #displayOrder first, since cards are shown grouped by difficulty."""
        n = maps.MAP_COUNT
        rows = max(1, _j.idiv(((n + MapSelectScreen.COLS) - 1), MapSelectScreen.COLS))
        pos = MapSelectScreen.position_of(MapSelectScreen.display_order(maps.create_all()), idx)
        top = ((104 + DifficultySelector.HEIGHT) + 40)
        bottom = (Ui.H - 28)
        gap = 18.0
        card_w = (((Ui.W - 50) - (gap * (MapSelectScreen.COLS - 1))) / MapSelectScreen.COLS)
        full = (((bottom - top) - (gap * (rows - 1))) / rows)
        card_h = _j.dmin((540 if (rows == 1) else 520), full)
        top += _j.dmax(0, (((full - card_h) * 0.35) * rows))
        compact = (card_h < 520)
        y = (top + (_j.idiv(pos, MapSelectScreen.COLS) * (card_h + gap)))
        x = (25 + (_j.imod(pos, MapSelectScreen.COLS) * (card_w + gap)))
        by = ((y + card_h) - (54 if compact else 70))
        bh = (40 if compact else 50)
        return [(x + (card_w / 2)), (by + (bh / 2))]
    @staticmethod
    def display_order(maps_):
        """Beginner -> Intermediate -> Advanced -> Expert, ties kept in catalog order: maps a grid position to a catalog index."""
        idx = _j.ArrayList()
        for i in range(len(maps_)):
            _j_add(idx, i)
        _j.sort(idx, _j.Fn(lambda a, b, *, maps_=maps_: _j.compare(MapSelectScreen.tier_rank(maps_[a].get_difficulty()), MapSelectScreen.tier_rank(maps_[b].get_difficulty()))))
        order = ([0] * len(idx))
        for i in range(len(order)):
            order[i] = idx[i]
        return order
    @staticmethod
    def tier_rank(difficulty):
        _sw1 = difficulty
        if _sw1 == 'Beginner':
            return 0
        elif _sw1 == 'Intermediate':
            return 1
        elif _sw1 == 'Advanced':
            return 2
        elif _sw1 == 'Expert':
            return 3
        else:
            return 4
    @staticmethod
    def position_of(order, value):
        """Position of value in order (grid position of a catalog index), or 0 if absent."""
        for i in range(len(order)):
            if order[i] == value:
                return i
        return 0
    @staticmethod
    def difficulty_color(d):
        _sw2 = d
        if _sw2 == 'Beginner':
            return Color(0x3bff8a)
        elif _sw2 == 'Intermediate':
            return MenuScreen.YELLOW
        elif _sw2 == 'Advanced':
            return Color(0xff8c3b)
        else:
            return MenuScreen.MAGENTA
    def build_card(self, app, m, idx, x, y, w, h):
        dc = MapSelectScreen.difficulty_color(m.get_difficulty())
        self.add(Cyber.Chamfer(x, y, w, h, 6).fill(Cyber.SURFACE_2))
        compact = (h < 520)
        ph = (h - (123 if compact else 139))
        s = _j.dmin(((w - 24) / GameMap.WIDTH), (ph / GameMap.HEIGHT))
        pw = (GameMap.WIDTH * s)
        ph = (GameMap.HEIGHT * s)
        px = (x + ((w - pw) / 2))
        py = (y + 14)
        self.add(MapArt(m, px, py, pw, ph))
        self.add(Ui.rect(px, py, pw, ph, None, Cyber.EDGE))
        for r in m.get_routes():
            self.add(Ui.oval(((px + (r.get_start().x * s)) - 3), ((py + (r.get_start().y * s)) - 3), 6, 6, Ui.GREEN, Ui.GREEN))
            self.add(Ui.oval(((px + (r.get_end().x * s)) - 3), ((py + (r.get_end().y * s)) - 3), 6, 6, Ui.RED, Ui.RED))
        tx = (x + 16)
        ty = ((py + ph) + 24)
        name_f = MenuScreen.menu_font(Font.BOLD, (19 if compact else 24))
        self.add(Ui.label(m.get_name().upper(), tx, ty, name_f, Ui.TEXT))
        ty += (18 if compact else 24)
        self.add(MapSelectScreen.badge(m, tx, ty, (14 if compact else 15), dc))
        self.build_record_marks(m, (x + w - 16), (ty - (18 if compact else 24)), ty, compact)
        button_y = ((y + h) - (54 if compact else 70))
        button_h = (40 if compact else 50)
        play = NeonButton((x + 16), button_y, (w - 32), button_h, 'DEPLOY', MenuScreen.menu_font(Font.BOLD, (17 if compact else 20)), dc, _j.Fn(lambda *, idx=idx: self.open_briefing(idx)))
        _j_add(self.buttons, play)
        self.add(play)
    @staticmethod
    def badge(m, x, y, size, dc):
        """"Intermediate · 1 lane": the difficulty tier in its colour, the lane count muted (no box)."""
        g = GCompound()
        tier = Ui.label(m.get_difficulty(), x, y, Cyber.body(Font.BOLD, size), dc)
        g.add(tier)
        n = len(m.get_routes())
        g.add(Ui.label(_j.cat('·  ', n, (' lane' if (n == 1) else ' lanes')), ((x + tier.get_width()) + 8), y, Cyber.body(Font.PLAIN, size), Ui.MUTED))
        return g
    def build_record_marks(self, m, right, name_y, badge_y, compact):
        """A card's records: four difficulty medals (lit once the map is won on that mode) right-aligned on the badge
row, and the best wave on the selected mode right-aligned on the name row."""
        medals = self.records.medals(m.get_name())
        mw = (24.0 if compact else 28.0)
        mh = (18.0 if compact else 20.0)
        gap = 5.0
        ds = Difficulty.values()
        x0 = (right - ((len(ds) * mw) + ((len(ds) - 1) * gap)))
        self.medal_marks[m.get_name()] = [MapSelectScreen.medal(self, ds[i], medals.get(ds[i].id, False), (x0 + (i * (mw + gap))), (badge_y - mh + 4), mw, mh) for i in range(len(ds))]
        best = Ui.label('', 0, name_y, Cyber.mono(Font.BOLD, (12 if compact else 13)), Ui.TEXT)
        self.add(best)
        _j_add(self.best_labels, [best, m.get_name(), right, name_y])
        self.refresh_best(len(self.best_labels) - 1)
    @staticmethod
    def medal(into, d, won, x, y, w, h):
        """One difficulty medal: a small tag with the mode's growth term (1, N, N², Nᴺ); a won medal is outlined and tinted in
the mode's colour (its frame has a border only then)."""
        col = DifficultySelector.COLORS[d.ordinal]
        frame = Cyber.Chamfer(x, y, w, h, 2).fill((Cyber.alpha(col, 60) if won else Color(255, 255, 255, 10))).border((col if won else None))
        into.add(frame)
        tc = (Cyber.lerp(col, Color.WHITE, 0.55) if won else Cyber.alpha(Ui.MUTED, 120))
        term = {'O1': ['1', None], 'ON': ['N', None], 'ON2': ['N', '2'], 'ONN': ['N', 'N']}.get(d.id, [d.ascii_label, None])
        base = Ui.label(term[0], 0, 0, Cyber.display(Font.BOLD, (12 if h < 20 else 13)), tc)
        sup = (Ui.label(term[1], 0, 0, Cyber.display(Font.BOLD, 9), tc) if (term[1] is not None) else None)
        tw = (base.get_width() + ((sup.get_width() + 1) if (sup is not None) else 0))
        bx = (x + ((w - tw) / 2))
        by = ((y + (h / 2)) + 5)
        base.set_location(bx, by)
        into.add(base)
        if sup is not None:
            sup.set_location(((bx + base.get_width()) + 1), (by - 4))
            into.add(sup)
        return frame
    def refresh_best(self, i):
        e = self.best_labels[i]
        d = Difficulty.get_selected()
        w = self.records.best_wave(e[1], d)
        won = self.records.has_won(e[1], d)
        e[0].set_label((_j.cat('BEST W', w) if (w > 0) else 'BEST  --'))
        e[0].set_color((Cyber.YELLOW if won else (Ui.TEXT if (w > 0) else Cyber.DIM)))
        e[0].set_location((e[2] - e[0].get_width()), e[3])
    def refresh_records(self):
        """Re-reads the cards' BEST readouts for the selected Difficulty Growth mode."""
        for i in range(len(self.best_labels)):
            self.refresh_best(i)
    def briefing_records(self, m, rx, rw, ty):
        """YOUR RECORDS: best wave, victories, fastest win and most lives left on the selected mode, above the RUN SETUP band."""
        d = Difficulty.get_selected()
        r = self.records.map_record(m.get_name(), d)
        y = _j.dmax(ty, (MapSelectScreen.band_y() - 84))   # just above the RUN SETUP band
        col = DifficultySelector.COLORS[d.ordinal]
        self.briefing.add(Ui.label(_j.cat('Your records on ', DifficultySelector.display(d, Cyber.body(Font.BOLD, 14))), rx, y, Cyber.body(Font.BOLD, 14), Cyber.lerp(col, Ui.TEXT, 0.35)))
        runs = Ui.label(_j.cat(r['runs'], (' run' if (r['runs'] == 1) else ' runs'), '  ·  ', r['victories'], (' win' if (r['victories'] == 1) else ' wins')), 0, y, Cyber.body(Font.PLAIN, 13), Ui.MUTED)
        runs.set_location(((rx + rw) - runs.get_width()), y)
        self.briefing.add(runs)
        cells = [['Best wave', (_j.cat('W', _j.to_int(r['best_wave'])) if (r['best_wave'] > 0) else '-')], ['Victories', _j.s(_j.to_int(r['victories']))], ['Fastest win', (RunReportView.fmt_time(r['fastest']) if ('fastest' in r) else '-')], ['Most lives', (_j.s(_j.to_int(r['best_lives'])) if ('best_lives' in r) else '-')]]
        gap = 8.0
        cw = ((rw - (gap * 3)) / 4)
        cy = (y + 12)
        for i in range(4):
            cx = (rx + (i * (cw + gap)))
            self.briefing.add(Cyber.Chamfer(cx, cy, cw, 46, 4).fill(Cyber.SURFACE_2).border((Ui.with_alpha(col, 150) if (r['victories'] > 0) else Cyber.EDGE)))
            self.briefing.add(Ui.label(cells[i][0], (cx + 10), (cy + 17), Cyber.body(Font.PLAIN, 12), Ui.MUTED))
            self.briefing.add(Ui.label(cells[i][1], (cx + 10), (cy + 37), Cyber.mono(Font.BOLD, 16), Ui.TEXT))
    @staticmethod
    def briefing_deploy_center():
        """Logical centre of the briefing popup's DEPLOY button (for tools that click through the real UI)."""
        r = MapSelectScreen.briefing_deploy_rect()
        return [(r[0] + (r[2] / 2)), (r[1] + (r[3] / 2))]
    @staticmethod
    def briefing_deploy_rect():
        """{x, y, w, h} of the popup's DEPLOY button; BACK sits to its left."""
        rx = (((MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_PAD) + MapSelectScreen.BRIEF_ART_W) + 36)
        rw = (((MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_W) - MapSelectScreen.BRIEF_PAD) - rx)
        by = (((MapSelectScreen.BRIEF_Y + MapSelectScreen.BRIEF_H) - MapSelectScreen.BRIEF_PAD) - MapSelectScreen.BRIEF_BUTTON_H)
        return [(rx + 166), by, (rw - 166), MapSelectScreen.BRIEF_BUTTON_H]
    def is_briefing_open(self):
        """True while the mission briefing popup is showing."""
        return self.briefing is not None
    def get_briefing_map(self):
        """Index of the map in the open briefing, or -1."""
        return self.briefing_map
    def open_briefing(self, idx):
        """Opens the mission briefing for map idx (a card's DEPLOY button)."""
        self.close_briefing()
        m = self.maps[idx]
        dc = MapSelectScreen.difficulty_color(m.get_difficulty())
        self.briefing_map = idx
        self.briefing = GCompound()
        self.briefing.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.c(0x000000, 0)))
        px = MapSelectScreen.BRIEF_X
        py = MapSelectScreen.BRIEF_Y
        pw = MapSelectScreen.BRIEF_W
        ph = MapSelectScreen.BRIEF_H
        self.briefing.add(Cyber.Chamfer(px, py, pw, ph, 6))
        self.briefing.add(Ui.label(_j.cat('Map ', (idx + 1), ' of ', len(self.maps)), (px + MapSelectScreen.BRIEF_PAD), (py + 40), Cyber.body(Font.PLAIN, 14), Ui.MUTED))
        ax = (px + MapSelectScreen.BRIEF_PAD)
        ay = (py + 60)
        aw = MapSelectScreen.BRIEF_ART_W
        ah = ((aw * GameMap.HEIGHT) / GameMap.WIDTH)
        s = (aw / GameMap.WIDTH)
        self.briefing.add(MapArt(m, ax, ay, aw, ah))
        self.briefing.add(Ui.rect(ax, ay, aw, ah, None, Cyber.EDGE_HI))
        for r in m.get_routes():
            self.briefing.add(Ui.oval(((ax + (r.get_start().x * s)) - 5), ((ay + (r.get_start().y * s)) - 5), 10, 10, Ui.GREEN, Ui.GREEN))
            self.briefing.add(Ui.oval(((ax + (r.get_end().x * s)) - 5), ((ay + (r.get_end().y * s)) - 5), 10, 10, Ui.RED, Ui.RED))
        ly = ((ay + ah) + 30)
        legend_f = Cyber.body(Font.PLAIN, 14)
        self.briefing.add(Ui.oval(ax, (ly - 9), 10, 10, Ui.GREEN, Ui.GREEN))
        entry = Ui.label('Entry', (ax + 16), ly, legend_f, Ui.MUTED)
        self.briefing.add(entry)
        ex = (((ax + 16) + entry.get_width()) + 22)
        self.briefing.add(Ui.oval(ex, (ly - 9), 10, 10, Ui.RED, Ui.RED))
        self.briefing.add(Ui.label('Exit', (ex + 16), ly, legend_f, Ui.MUTED))
        rx = ((ax + aw) + 36)
        rw = (((px + pw) - MapSelectScreen.BRIEF_PAD) - rx)
        ty = (py + 92)
        name_f = MenuScreen.menu_font(Font.BOLD, 30)
        for line in Ui.wrap(m.get_name().upper(), name_f, rw):
            self.briefing.add(Ui.label(line, rx, ty, name_f, Ui.TEXT))
            ty += 34
        ty += 2
        self.briefing.add(MapSelectScreen.badge(m, rx, ty, 16, dc))
        ty += 40
        ty = self.briefing_section('Briefing', m.get_description(), MenuScreen.CYAN, rx, ty, rw)
        ty = self.briefing_section('Map mechanics', m.get_mechanic_summary(), MenuScreen.YELLOW, rx, ty, rw)
        d = Difficulty.get_selected()
        ty = self.briefing_section('Difficulty growth', _j.cat(DifficultySelector.display(d, Cyber.body(Font.PLAIN, 16)), '  -  ', d.subtitle), MenuScreen.MAGENTA, rx, ty, rw)
        self.briefing_records(m, rx, rw, ty)
        dep = MapSelectScreen.briefing_deploy_rect()
        back = NeonButton(rx, dep[1], 150, dep[3], 'BACK', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN, _j.Fn(self.close_briefing))
        go = NeonButton(dep[0], dep[1], dep[2], dep[3], 'DEPLOY', MenuScreen.menu_font(Font.BOLD, 22), dc, _j.Fn(lambda *, idx=idx: self.deploy(idx)))
        go.set_primary(True)
        _j_add(self.briefing_buttons, back)
        _j_add(self.briefing_buttons, go)
        self.briefing.add(back)
        self.briefing.add(go)
        self.add_mode_switch(idx, ax, aw, False)
        self.run_setup = RunSetupView.RunSetupBand(self.briefing, ax, MapSelectScreen.band_y(), (pw - (2 * MapSelectScreen.BRIEF_PAD)))
        for c in self.run_setup.buttons:
            _j_add(self.briefing_buttons, c)
        self.add(self.briefing)
    def is_reverse_briefing(self):
        """True while the reverse-mode (attacker) briefing is showing."""
        return (self.briefing is not None) and self.briefing_reverse
    @staticmethod
    def briefing_mode_center():
        """Logical centre of the briefing's ATTACK INSTEAD / DEFEND INSTEAD switch (for tools that click through the UI)."""
        dep = MapSelectScreen.briefing_deploy_rect()
        return [((MapSelectScreen.BRIEF_X + MapSelectScreen.BRIEF_PAD) + (MapSelectScreen.BRIEF_ART_W / 2)), (dep[1] + (dep[3] / 2))]
    def add_mode_switch(self, idx, ax, aw, reverse):
        """The switch between the normal and the reverse briefing, across the left column under the map legend."""
        dep = MapSelectScreen.briefing_deploy_rect()
        mode = (NeonButton(ax, dep[1], aw, dep[3], 'DEFEND INSTEAD  ·  NORMAL MODE', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN, _j.Fn(lambda *, idx=idx: self.open_briefing(idx))) if reverse else NeonButton(ax, dep[1], aw, dep[3], 'ATTACK INSTEAD  ·  ADVERSARIAL TRAINING', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.MAGENTA, _j.Fn(lambda *, idx=idx: self.open_reverse_briefing(idx))))
        _j_add(self.briefing_buttons, mode)
        self.briefing.add(mode)
    def open_reverse_briefing(self, idx):
        """The reverse-mode briefing for map idx: the same preview, then the rules of Adversarial Training (you send,
the AI defends), the defender AI the Difficulty Growth mode selects, and the map's lanes / long-track bonus. Its
ATTACK (or Enter) starts the reverse match; DEFEND INSTEAD goes back to the normal briefing."""
        self.close_briefing()
        m = self.maps[idx]
        dc = MenuScreen.MAGENTA
        self.briefing_map = idx
        self.briefing_reverse = True
        self.briefing = GCompound()
        self.briefing.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.c(0x000000, 0)))
        px = MapSelectScreen.BRIEF_X
        py = MapSelectScreen.BRIEF_Y
        pw = MapSelectScreen.BRIEF_W
        ph = MapSelectScreen.BRIEF_H
        self.briefing.add(Cyber.Chamfer(px, py, pw, ph, 6).fill(Color(14, 10, 28, 246)))
        self.briefing.add(Ui.label(_j.cat('Adversarial training  ·  map ', (idx + 1), ' of ', len(self.maps)), (px + MapSelectScreen.BRIEF_PAD), (py + 40), Cyber.body(Font.PLAIN, 14), Ui.MUTED))
        ax = (px + MapSelectScreen.BRIEF_PAD)
        ay = (py + 60)
        aw = MapSelectScreen.BRIEF_ART_W
        ah = ((aw * GameMap.HEIGHT) / GameMap.WIDTH)
        s = (aw / GameMap.WIDTH)
        self.briefing.add(MapArt(m, ax, ay, aw, ah))
        self.briefing.add(Ui.rect(ax, ay, aw, ah, None, Cyber.EDGE_HI))
        for r in m.get_routes():
            self.briefing.add(Ui.oval(((ax + (r.get_start().x * s)) - 5), ((ay + (r.get_start().y * s)) - 5), 10, 10, MenuScreen.MAGENTA, MenuScreen.MAGENTA))
            self.briefing.add(Ui.oval(((ax + (r.get_end().x * s)) - 5), ((ay + (r.get_end().y * s)) - 5), 10, 10, Ui.RED, Ui.RED))
        ly = ((ay + ah) + 30)
        legend_f = Cyber.body(Font.PLAIN, 14)
        self.briefing.add(Ui.oval(ax, (ly - 9), 10, 10, MenuScreen.MAGENTA, MenuScreen.MAGENTA))
        entry = Ui.label('Your uplink', (ax + 16), ly, legend_f, Ui.MUTED)
        self.briefing.add(entry)
        ex = (((ax + 16) + entry.get_width()) + 22)
        self.briefing.add(Ui.oval(ex, (ly - 9), 10, 10, Ui.RED, Ui.RED))
        self.briefing.add(Ui.label('Breach point', (ex + 16), ly, legend_f, Ui.MUTED))
        rx = ((ax + aw) + 36)
        rw = (((px + pw) - MapSelectScreen.BRIEF_PAD) - rx)
        ty = (py + 92)
        name_f = MenuScreen.menu_font(Font.BOLD, 30)
        for line in Ui.wrap(m.get_name().upper(), name_f, rw):
            self.briefing.add(Ui.label(line, rx, ty, name_f, Ui.TEXT))
            ty += 34
        ty += 2
        self.briefing.add(Ui.label('Reverse mode  ·  you attack', rx, ty, Cyber.body(Font.BOLD, 16), dc))
        ty += 40
        mins = _j.to_int((ReverseMatch.DURATION / 60))
        ty = self.briefing_section('Adversarial training', _j.cat('Roles reversed: you send the enemies, a defender AI builds and upgrades the towers. Spend compute credits on ', 'units, modifiers and exploits, and drop its integrity to 0 before the ', mins, ':00 training run ends.'), MenuScreen.MAGENTA, rx, ty, rw)
        d = Difficulty.get_selected()
        prof = DefenderProfile.of(d)
        ty = self.briefing_section(_j.cat('Defender AI: ', prof.display_name), _j.cat(DifficultySelector.display(d, Cyber.body(Font.PLAIN, 16)), '  -  ', prof.description), MenuScreen.YELLOW, rx, ty, rw)
        ty = self.briefing_section('Difficulty rules', prof.rules_line(), Ui.RED, rx, ty, rw)
        tb = _m_reverse_match.track_bonus(m)
        sp = _m_reverse_match.track_speed(m)
        lanes = len(m.get_routes())
        up = _j.cat(lanes, (' lane.' if (lanes == 1) else ' lanes: pick one per send or spread them.'), (_j.cat(' Long track: your units move x', Ui.fmt((_j.jround((sp * 100)) / 100.0)), ' faster and compute flows x', Ui.fmt((_j.jround((tb * 100)) / 100.0)), '.') if ((tb > 1) or (sp > 1)) else ' Standard track.'))
        self.briefing_section('Uplink', up, MenuScreen.CYAN, rx, ty, rw)
        dep = MapSelectScreen.briefing_deploy_rect()
        back = NeonButton(rx, dep[1], 150, dep[3], 'BACK', MenuScreen.menu_font(Font.BOLD, 18), MenuScreen.CYAN, _j.Fn(self.close_briefing))
        go = NeonButton(dep[0], dep[1], dep[2], dep[3], 'ATTACK', MenuScreen.menu_font(Font.BOLD, 22), dc, _j.Fn(lambda *, idx=idx: self.app.start_reverse(idx)))
        go.set_primary(True)
        _j_add(self.briefing_buttons, back)
        _j_add(self.briefing_buttons, go)
        self.briefing.add(back)
        self.briefing.add(go)
        self.add_mode_switch(idx, ax, aw, True)
        RunSetupView.reverse_band(self.briefing, ax, MapSelectScreen.band_y(), (pw - (2 * MapSelectScreen.BRIEF_PAD)))
        self.add(self.briefing)
    @staticmethod
    def band_y():
        """Baseline of the briefing's RUN SETUP heading: under the map legend, above the BACK / DEPLOY row."""
        return MapSelectScreen.BRIEF_Y + 572
    def is_typing(self):
        """True while the briefing's SEED field has the keyboard focus (keys go to it, not to the audio shortcuts)."""
        return (self.run_setup is not None) and self.run_setup.is_typing()
    def get_run_setup(self):
        """The open briefing's RUN SETUP band, or None."""
        return self.run_setup
    def deploy(self, idx):
        """DEPLOY / START DAILY / Enter: starts the run the briefing sets up (typed seed, challenge rules, Patch Notes,
or the daily run). A seed that does not parse is refused and its error stays on screen."""
        setup = (self.run_setup.setup(idx) if (self.run_setup is not None) else RunSetup(idx, Difficulty.get_selected(), None, (), RunOptions.get().patch_notes_on()))
        if setup is None:
            AudioManager.sfx(Sfx.INVALID)
            return
        self.app.start_run(setup)
    def is_daily_briefing(self):
        """True while the daily run's briefing is showing."""
        return (self.briefing is not None) and self.briefing_daily
    def open_daily_briefing(self):
        """PLAY DAILY: the briefing for today's daily run (fixed seed, map, difficulty and rule); START DAILY starts it."""
        self.close_briefing()
        self.daily = DailyRun.today()
        self.briefing_map = self.daily.map_index
        self.briefing_daily = True
        self.run_setup, buttons = RunSetupView.build_daily_briefing(self, self.daily)
        for c in (buttons + self.run_setup.buttons):
            _j_add(self.briefing_buttons, c)
        self.add(self.briefing)
    def briefing_section(self, heading, text, col, x, y, w):
        """One heading + wrapped paragraph in the briefing's right column; returns the y for the next section."""
        self.briefing.add(Ui.label(heading, x, y, Cyber.body(Font.BOLD, 14), Cyber.lerp(col, Ui.MUTED, 0.6)))
        y += 24
        f = Cyber.body(Font.PLAIN, 16)
        for line in Ui.wrap(text, f, w):
            self.briefing.add(Ui.label(line, x, y, f, Cyber.lerp(Ui.TEXT, Ui.MUTED, 0.2)))
            y += 22
        return y + 18
    def close_briefing(self):
        """Closes the mission briefing popup (BACK, Esc); does nothing if it is not open."""
        if self.briefing is None:
            return
        self.remove(self.briefing)
        self.briefing = None
        self.briefing_buttons.clear()
        self.briefing_map = (-1)
        self.briefing_reverse = False
        self.briefing_daily = False
        self.run_setup = None
    def key_pressed(self, e):
        """Esc closes the briefing popup, or goes back to the main menu; Enter deploys from an open briefing."""
        k = e.get_key_code()
        if self.is_typing() and (k != KeyEvent.VK_ENTER):
            if k == KeyEvent.VK_ESCAPE:
                self.run_setup.blur()
            else:
                self.run_setup.key_pressed(e)
            return
        if k == KeyEvent.VK_ESCAPE:
            if self.briefing is not None:
                AudioManager.sfx(Sfx.UI_CLICK)
                self.close_briefing()
            else:
                self.app.show_menu()
        elif (k == KeyEvent.VK_ENTER) and (self.briefing is not None):
            idx = self.briefing_map
            if self.briefing_reverse:
                self.app.start_reverse(idx)
                return
            AudioManager.sfx(Sfx.UI_SELECT)
            self.deploy(idx)
    def mouse_pressed(self, lx, ly):
        if self.briefing is not None:
            if self.run_setup is not None:
                self.run_setup.mouse_pressed(lx, ly)
            for b in _j.ArrayList(self.briefing_buttons):
                if b.hit(lx, ly):
                    b.click()
                    return
            return
        for c in self.chips:
            if c.hit(lx, ly):
                c.click()
                return
        if self.difficulty.mouse_pressed(lx, ly):
            AudioManager.sfx(Sfx.UI_CLICK)
            records.remember_difficulty(Difficulty.get_selected())
            self.refresh_records()
            return
        for b in self.buttons:
            if b.hit(lx, ly):
                b.click()
                return
    def mouse_moved(self, lx, ly):
        if self.briefing is not None:
            for b in self.briefing_buttons:
                b.set_hover(b.hit(lx, ly))
            for b in self.buttons:
                b.set_hover(False)
            for c in self.chips:
                c.set_hover(False)
            return
        self.difficulty.mouse_moved(lx, ly)
        for b in self.buttons:
            b.set_hover(b.hit(lx, ly))
        for c in self.chips:
            c.set_hover(c.hit(lx, ly))
    def frame(self, dt):
        self.t += dt
        for b in self.buttons:
            b.animate(dt)
        for b in self.briefing_buttons:
            b.animate(dt)
        if self.run_setup is not None:
            self.run_setup.frame(dt)
        AudioToggle.sync_all(self.audio_toggles)
        for c in self.chips:
            c.animate(dt)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.audio_toggle import AudioToggle  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.difficulty_selector import DifficultySelector  # noqa: E402
from lindefense.ui.logo_emblem import LogoEmblem  # noqa: E402
from lindefense.ui.logo_wordmark import LogoWordmark  # noqa: E402
from lindefense.ui.map_art import MapArt  # noqa: E402
from lindefense.ui.menu_screen import MenuScreen  # noqa: E402
from lindefense.ui.neon_button import NeonButton  # noqa: E402
from lindefense.ui import run_report_view as RunReportView  # noqa: E402
from lindefense.ui import run_setup_view as RunSetupView  # noqa: E402

MapSelectScreen.serial_version_uid = 1
MapSelectScreen.COLS = 4
MapSelectScreen.BRIEF_W = 1100.0
MapSelectScreen.BRIEF_H = 820.0
MapSelectScreen.BRIEF_X = ((Ui.W - MapSelectScreen.BRIEF_W) / 2)
MapSelectScreen.BRIEF_Y = ((Ui.H - MapSelectScreen.BRIEF_H) / 2)
MapSelectScreen.BRIEF_PAD = 34.0
MapSelectScreen.BRIEF_ART_W = 600.0
MapSelectScreen.BRIEF_BUTTON_H = 54.0
