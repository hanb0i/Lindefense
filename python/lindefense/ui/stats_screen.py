"""RECORDS (main menu): career totals, the per-map records grid, achievements and the run history, as a pop-up panel
over the menu like the Catalog. Everything is read from sim.records; history rows have a REPLAY SEED button that
starts that map / difficulty / seed again."""
from lindefense.jenum import JEnum
from lindefense.map import maps
from lindefense.sim import records as rec
from lindefense.sim.challenges import Challenge
from lindefense.sim.difficulty import Difficulty
from lindefense.ui.acm import GCompound
from lindefense.ui.jawt import Color, Font, KeyEvent
from lindefense.ui.cyber import Cyber
from lindefense.ui.ui import Ui
from lindefense.ui.ui_button import UIButton
from lindefense.ui import run_report_view as RunReportView
from lindefense.variance.variance import PatchNote

X0 = 50.0
X1 = 1550.0
TOP = 170.0
BOTTOM = 930.0
HISTORY_ROWS = 15
RESULT_COLORS = {rec.VICTORY: Cyber.YELLOW, rec.DEFEAT: Cyber.RED, rec.ABANDONED: Cyber.MUTED}


class Tab(JEnum):
    CAREER = ("CAREER",)
    MAPS = ("MAPS",)
    ACHIEVEMENTS = ("ACHIEVEMENTS",)
    HISTORY = ("HISTORY",)

    def _init(self, label):
        self.label = label


def _diff_colors():
    from lindefense.ui.difficulty_selector import DifficultySelector
    return DifficultySelector.COLORS


def _short(text, f, max_w):
    return RunReportView._short(text, f, max_w)


class StatsScreen(GCompound):
    Tab = Tab

    def __init__(self, on_close, on_replay=None, records=None):
        GCompound.__init__(self)
        self.on_close = on_close
        self.on_replay = on_replay
        self.records = records if records is not None else rec.Records.persistent()
        self.chrome = []
        self.content_buttons = []
        self.tabs = []
        self.tab = Tab.CAREER
        self.page = 0
        self.replay_buttons = []
        self.layer = GCompound()
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.c(0x000000, 0)))
        self.add(Cyber.Chamfer(20, 20, Ui.W - 40, Ui.H - 40, 6).fill(Color(9, 14, 28, 250)))
        self.add(Ui.label("RECORDS", X0, 94, Cyber.display(Font.BOLD, 40), Cyber.TEXT))
        back = UIButton(X1 - 180, 52, 180, 46, "BACK  [ESC]", Cyber.display(Font.BOLD, 18), self.close)
        self.add(back)
        self.chrome.append(back)
        n_ach = len(rec.achievements())
        labels = {Tab.CAREER: "CAREER", Tab.MAPS: "MAP RECORDS",
                  Tab.ACHIEVEMENTS: "ACHIEVEMENTS %d/%d" % (self.records.unlocked_count(), n_ach),
                  Tab.HISTORY: "HISTORY (%d)" % len(self.records.history())}
        widths = {Tab.CAREER: 130, Tab.MAPS: 160, Tab.ACHIEVEMENTS: 230, Tab.HISTORY: 160}
        tx = 330.0
        for t in Tab.values():
            b = UIButton(tx, 58, widths[t], 40, labels[t], Cyber.display(Font.BOLD, 16), lambda t=t: self.set_tab(t))
            b.set_accent(Cyber.YELLOW if t is Tab.ACHIEVEMENTS else Cyber.CYAN)
            b.set_flat(True)
            self.add(b)
            self.chrome.append(b)
            self.tabs.append(b)
            tx += widths[t] + 8
        self.add(self.layer)
        self.set_tab(Tab.CAREER)

    # ---------------------------------------------------------------- tabs
    def get_tab(self):
        return self.tab

    def set_tab(self, t):
        self.tab = t
        self.page = 0
        for i, b in enumerate(self.tabs):
            b.set_selected(Tab.values()[i] is t)
        self.rebuild()

    def close(self):
        if self.on_close is not None:
            self.on_close()

    def rebuild(self):
        self.layer.remove_all()
        self.content_buttons = []
        self.replay_buttons = []
        {Tab.CAREER: self.build_career, Tab.MAPS: self.build_maps, Tab.ACHIEVEMENTS: self.build_achievements,
         Tab.HISTORY: self.build_history}[self.tab]()

    def heading(self, text, x, y, col=None):
        """A section heading: small sentence-case text (the colour only when it means something)."""
        self.layer.add(Ui.label(text[0:1].upper() + text[1:], x, y, Cyber.body(Font.BOLD, 15), Cyber.MUTED if col is None else col))

    def tile(self, x, y, w, h, label, value, sub, accent):
        L = self.layer
        L.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.SURFACE_2))
        L.add(Ui.label(label[0:1].upper() + label[1:], x + 18, y + 34, Cyber.body(Font.PLAIN, 15), Cyber.MUTED))
        L.add(Ui.label(value, x + 18, y + 78, Cyber.mono(Font.BOLD, 34), Cyber.TEXT))
        if sub:
            L.add(Ui.label(sub, x + 16, y + h - 14, Cyber.body(Font.PLAIN, 14), Cyber.MUTED))

    # ---------------------------------------------------------------- career
    def build_career(self):
        r = self.records
        c = r.career()
        runs = int(c["runs"])
        wins = int(c["victories"])
        rate = (" (%d%%)" % round(100.0 * wins / runs)) if runs else ""
        n_ach = len(rec.achievements())
        got = r.unlocked_count()
        cells = [
            ("runs", Cyber.commas(runs), "%d won  /  %d lost  /  %d abandoned" % (wins, c["defeats"], c["abandoned"]), Cyber.CYAN),
            ("victories", Cyber.commas(wins) + rate, "CLASSIC runs and campaign levels won", Cyber.YELLOW),
            ("waves cleared", Cyber.commas(int(c["waves_cleared"])), "best wave reached: %d" % c["best_wave"], Cyber.CYAN),
            ("hostiles purged", Cyber.commas(int(c["enemies_killed"])), "%s leaked past the defenses" % Cyber.commas(int(c["leaks"])), Cyber.GREEN),
            ("bosses defeated", Cyber.commas(int(c["bosses_killed"])), "Palantir included", Cyber.RED),
            ("credits earned", Ui.money(c["cash_earned"]), "income only, sell refunds excluded", Cyber.YELLOW),
            ("time played", RunReportView.fmt_time(c["play_time"]), "across every recorded run", Cyber.MAGENTA),
            ("achievements", "%d / %d" % (got, n_ach), "see the ACHIEVEMENTS tab", Cyber.YELLOW),
        ]
        gap = 20.0
        w = (X1 - X0 - 3 * gap) / 4
        h = 132.0
        self.heading("career totals", X0, TOP + 2)
        for i, (lbl, val, sub, acc) in enumerate(cells):
            x = X0 + (i % 4) * (w + gap)
            y = TOP + 20 + (i // 4) * (h + gap)
            self.tile(x, y, w, h, lbl, val, sub, acc)
        # achievements progress bar in the last tile
        x = X0 + 3 * (w + gap)
        y = TOP + 20 + (h + gap)
        frac = got / float(n_ach) if n_ach else 0
        self.layer.add(Ui.rect(x + w - 150, y + 64, 130, 8, Cyber.alpha(Cyber.YELLOW, 40), Cyber.alpha(Cyber.YELLOW, 40)))
        self.layer.add(Ui.rect(x + w - 150, y + 64, max(2.0, 130 * frac), 8, Cyber.YELLOW, Cyber.YELLOW))
        # ---- medal cabinet: maps won per difficulty
        y0 = TOP + 20 + 2 * (h + gap) + 26
        self.heading("medal cabinet  -  maps won on each mode", X0, y0)
        names = self.map_names()
        cols = _diff_colors()
        from lindefense.ui.map_select_screen import MapSelectScreen
        row_h = 62.0
        for i, d in enumerate(Difficulty.values()):
            y = y0 + 18 + i * (row_h + 10)
            won = [r.has_won(n, d) for n in names]
            col = cols[d.ordinal]
            self.layer.add(Cyber.Chamfer(X0, y, X1 - X0, row_h, 4).fill(Cyber.SURFACE_2))
            self.layer.add(Ui.label(RunReportView.diff_text(d), X0 + 20, y + 30, Cyber.display(Font.BOLD, 22), col))
            self.layer.add(Ui.label(d.subtitle, X0 + 20, y + 50, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
            cnt = Ui.label("%d / %d" % (sum(won), len(names)), 0, y + 40, Cyber.mono(Font.BOLD, 22), Cyber.TEXT)
            cnt.set_location(X0 + 300 - cnt.get_width(), y + 40)
            self.layer.add(cnt)
            mx = X0 + 330
            step = (X1 - 16 - mx) / len(names)
            nf = Cyber.body(Font.BOLD, 12)
            for k, n in enumerate(names):
                MapSelectScreen.medal(self.layer, d, won[k], mx + k * step, y + 17, 26, 20)
                self.layer.add(Ui.label(_short(self.short_name(n), nf, step - 40), mx + k * step + 34, y + 33,
                                        nf, Cyber.TEXT if won[k] else Cyber.alpha(Cyber.MUTED, 170)))
                best = r.best_wave(n, d)
                self.layer.add(Ui.label(("BEST W%d" % best) if best else "-", mx + k * step + 34, y + 49,
                                        Cyber.mono(Font.BOLD, 10), Cyber.MUTED if best else Cyber.DIM))

    @staticmethod
    def short_name(n):
        return n[4:] if n.startswith("The ") else n

    @staticmethod
    def map_names():
        """Map names in map-select order (beginner first)."""
        from lindefense.ui.map_select_screen import MapSelectScreen
        ms = maps.create_all()
        return [ms[i].get_name() for i in MapSelectScreen.display_order(ms)]

    # ---------------------------------------------------------------- maps grid
    def build_maps(self):
        from lindefense.ui.difficulty_selector import DifficultySelector
        from lindefense.ui.map_select_screen import MapSelectScreen
        r = self.records
        ms = maps.create_all()
        order = MapSelectScreen.display_order(ms)
        cols = _diff_colors()
        name_w = 330.0
        gap = 10.0
        cw = (X1 - X0 - name_w - 4 * gap) / 4
        hy = TOP + 6
        self.heading("best wave, wins and fastest victory per map and mode", X0, hy)
        for j, d in enumerate(Difficulty.values()):
            x = X0 + name_w + gap + j * (cw + gap)
            lbl = DifficultySelector.math_label(d, Cyber.display(Font.BOLD, 20), Cyber.display(Font.BOLD, 12), cols[j])
            lbl.set_location(x + 14, hy + 36)
            self.layer.add(lbl)
            self.layer.add(Ui.label(d.subtitle.split(" (")[0], x + 100, hy + 36, Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
        row_h = 88.0
        for i, idx in enumerate(order):
            m = ms[idx]
            y = hy + 52 + i * (row_h + 8)
            dc = MapSelectScreen.difficulty_color(m.get_difficulty())
            self.layer.add(Cyber.Chamfer(X0, y, name_w, row_h, 4).fill(Cyber.SURFACE_2))
            nf = Cyber.display(Font.BOLD, 18)
            self.layer.add(Ui.label(_short(m.get_name().upper(), nf, name_w - 32), X0 + 16, y + 36, nf, Cyber.TEXT))
            self.layer.add(MapSelectScreen.badge(m, X0 + 16, y + 62, 13, dc))
            for j, d in enumerate(Difficulty.values()):
                x = X0 + name_w + gap + j * (cw + gap)
                self.map_cell(x, y, cw, row_h, r.map_record(m.get_name(), d), d, cols[j])

    def map_cell(self, x, y, w, h, mr, d, col):
        from lindefense.ui.map_select_screen import MapSelectScreen
        L = self.layer
        won = mr["victories"] > 0
        played = mr["runs"] > 0
        L.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.alpha(col, 22) if won else Cyber.SURFACE_2)
              .border(Cyber.alpha(col, 140) if won else (Cyber.EDGE if played else None)))
        MapSelectScreen.medal(L, d, won, x + 14, y + 14, 30, 22)
        if not played:
            L.add(Ui.label("NOT PLAYED", x + 56, y + 31, Cyber.mono(Font.BOLD, 12), Cyber.DIM))
            return
        L.add(Ui.label("BEST W%d" % mr["best_wave"], x + 56, y + 32, Cyber.mono(Font.BOLD, 17), Cyber.YELLOW if won else Cyber.TEXT))
        runs = Ui.label("%d/%d WON" % (mr["victories"], mr["runs"]), 0, y + 31, Cyber.mono(Font.BOLD, 11), Cyber.MUTED)
        runs.set_location(x + w - 14 - runs.get_width(), y + 31)
        L.add(runs)
        if won:
            L.add(Ui.label("FASTEST  " + RunReportView.fmt_time(mr.get("fastest", 0)), x + 14, y + 64, Cyber.mono(Font.BOLD, 12), Cyber.TEXT))
            lv = Ui.label("LIVES  %d" % mr.get("best_lives", 0), 0, y + 64, Cyber.mono(Font.BOLD, 12), Cyber.TEXT)
            lv.set_location(x + w - 14 - lv.get_width(), y + 64)
            L.add(lv)
        else:
            L.add(Ui.label("no victory yet", x + 14, y + 64, Cyber.body(Font.PLAIN, 13), Cyber.MUTED))

    # ---------------------------------------------------------------- achievements
    def build_achievements(self):
        r = self.records
        all_ = rec.achievements()
        got = r.unlocked()
        n = sum(1 for a in all_ if a.id in got)
        self.heading("%d of %d unlocked" % (n, len(all_)), X0, TOP + 2, Cyber.lerp(Cyber.YELLOW, Cyber.TEXT, 0.3))
        bx = X0 + 260
        self.layer.add(Ui.rect(bx, TOP - 6, 400, 8, Cyber.alpha(Cyber.YELLOW, 40), Cyber.alpha(Cyber.YELLOW, 40)))
        self.layer.add(Ui.rect(bx, TOP - 6, max(2.0, 400.0 * n / max(1, len(all_))), 8, Cyber.YELLOW, Cyber.YELLOW))
        cols = 4
        gap = 14.0
        w = (X1 - X0 - (cols - 1) * gap) / cols
        h = 84.0
        for i, a in enumerate(all_):
            x = X0 + (i % cols) * (w + gap)
            y = TOP + 18 + (i // cols) * (h + 10)
            self.achievement_card(a, got.get(a.id), x, y, w, h)

    def achievement_card(self, a, date, x, y, w, h):
        L = self.layer
        on = date is not None
        acc = Cyber.MAGENTA if a.mode == "reverse" else Cyber.YELLOW
        L.add(Cyber.Chamfer(x, y, w, h, 4).fill(Cyber.alpha(acc, 20) if on else Cyber.SURFACE_2)
              .border(Cyber.alpha(acc, 140) if on else None))
        cx, cy = x + 30, y + h / 2
        L.add(Ui.oval(cx - 17, cy - 17, 34, 34, Cyber.alpha(acc, 40) if on else Color(18, 26, 44), Cyber.alpha(acc, 40) if on else Color(18, 26, 44)))
        L.add(RunReportView.star(cx, cy + 1, 10, acc if on else Cyber.alpha(Cyber.DIM, 200)))
        tx = x + 60
        from lindefense.ui.catalog_screen import CatalogScreen
        room = w - 75 - (72 if on else 0)
        tf = CatalogScreen.fit_font(a.title.upper(), Cyber.display(Font.BOLD, 15), room, 12)
        L.add(Ui.label(_short(a.title.upper(), tf, room), tx, y + 28, tf, Cyber.TEXT if on else Cyber.alpha(Cyber.MUTED, 230)))
        if on:
            d = Ui.label(date.split(" ")[0], 0, y + 26, Cyber.mono(Font.BOLD, 10), Cyber.MUTED)
            d.set_location(x + w - 12 - d.get_width(), y + 26)
            L.add(d)
        f = Cyber.body(Font.PLAIN, 13)
        yy = y + 48
        for line in list(Ui.wrap(a.description, f, w - 75))[:2]:
            L.add(Ui.label(line, tx, yy, f, Cyber.MUTED if on else Cyber.alpha(Cyber.MUTED, 150)))
            yy += 17

    # ---------------------------------------------------------------- history
    def build_history(self):
        hist = self.records.history()
        pages = max(1, (len(hist) + HISTORY_ROWS - 1) // HISTORY_ROWS)
        self.page = max(0, min(self.page, pages - 1))
        self.heading("last %d runs  -  newest first" % rec.HISTORY_MAX, X0, TOP + 2)
        cols = [("DATE", 0), ("MAP", 150), ("MODE", 420), ("SEED", 500), ("RESULT", 640), ("WAVE", 760),
                ("TIME", 830), ("KILLS", 920), ("PATCH NOTES  /  TAGS", 1010)]
        hy = TOP + 34
        for name, dx in cols:
            self.layer.add(Ui.label(name, X0 + 12 + dx, hy, Cyber.mono(Font.BOLD, 10), Cyber.DIM))
        self.layer.add(Ui.rect(X0, hy + 8, X1 - X0, 1, Cyber.EDGE, Cyber.EDGE))
        if not hist:
            self.layer.add(Ui.label("No runs recorded yet. Finish or quit a CLASSIC run and it shows up here.", X0 + 12, hy + 60,
                                    Cyber.body(Font.PLAIN, 18), Cyber.MUTED))
            return
        names = [m.get_name() for m in maps.create_all()]
        row_h = 44.0
        f = Cyber.body(Font.PLAIN, 15)
        mono = Cyber.mono(Font.BOLD, 13)
        cols_d = _diff_colors()
        for i, h in enumerate(hist[self.page * HISTORY_ROWS:(self.page + 1) * HISTORY_ROWS]):
            y = hy + 18 + i * row_h
            if i % 2 == 0:
                self.layer.add(Ui.rect(X0, y, X1 - X0, row_h - 4, Color(14, 24, 48, 120), Color(14, 24, 48, 0)))
            base = y + 26
            x = X0 + 12
            self.layer.add(Ui.label(str(h.get("date", "")), x, base, mono, Cyber.MUTED))
            self.layer.add(Ui.label(_short(str(h.get("map", "?")), Cyber.body(Font.BOLD, 15), 255), x + 150, base, Cyber.body(Font.BOLD, 15), Cyber.TEXT))
            d = Difficulty.parse(str(h.get("difficulty", "")))
            self.layer.add(Ui.label(RunReportView.diff_text(d) if d else "?", x + 420, base, mono, cols_d[d.ordinal] if d else Cyber.MUTED))
            self.layer.add(Ui.label(str(h.get("seed_code", "")), x + 500, base, mono, Cyber.CYAN))
            res = str(h.get("result", ""))
            self.layer.add(Ui.label(res.upper(), x + 640, base, mono, RESULT_COLORS.get(res, Cyber.MUTED)))
            self.layer.add(Ui.label("W%d" % int(h.get("wave", 0)), x + 760, base, mono, Cyber.TEXT))
            self.layer.add(Ui.label(RunReportView.fmt_time(float(h.get("time", 0))), x + 830, base, mono, Cyber.TEXT))
            self.layer.add(Ui.label(Cyber.abbrev(float(h.get("kills", 0))), x + 920, base, mono, Cyber.TEXT))
            self.notes_cell(h, x + 1010, y + 9, 300)
            idx = h.get("map_index", -1)
            if h.get("map") in names:
                idx = names.index(h.get("map"))
            ok = d is not None and isinstance(idx, int) and 0 <= idx < maps.MAP_COUNT and self.on_replay is not None
            b = UIButton(X1 - 168, y + 4, 156, row_h - 12, "REPLAY SEED", Cyber.display(Font.BOLD, 14),
                         lambda h=h, idx=idx, d=d: self.replay(h, idx, d))
            b.set_accent(Cyber.CYAN)
            b.set_enabled(ok)
            self.layer.add(b)
            self.content_buttons.append(b)
            self.replay_buttons.append(b)
        if pages > 1:
            py = BOTTOM - 8
            prev = UIButton(X1 - 420, py - 30, 120, 36, "< NEWER", Cyber.display(Font.BOLD, 14), lambda: self.set_page(self.page - 1))
            nxt = UIButton(X1 - 120, py - 30, 120, 36, "OLDER >", Cyber.display(Font.BOLD, 14), lambda: self.set_page(self.page + 1))
            prev.set_enabled(self.page > 0)
            nxt.set_enabled(self.page < pages - 1)
            lbl = Ui.label("PAGE %d / %d" % (self.page + 1, pages), 0, py - 6, Cyber.mono(Font.BOLD, 13), Cyber.MUTED)
            lbl.set_location(X1 - 210 - lbl.get_width() / 2, py - 6)
            for b in (prev, nxt):
                self.layer.add(b)
                self.content_buttons.append(b)
            self.layer.add(lbl)

    def notes_cell(self, h, x, y, max_w):
        f = Cyber.mono(Font.BOLD, 10)
        cx = x
        items = [("tag", t) for t in h.get("tags", []) if isinstance(t, str)]
        for n in h.get("notes", []):
            p = PatchNote.__members__.get(n) if isinstance(n, str) else None
            items.append(("note", p.chip if p is not None else str(n)))
        if not items:
            self.layer.add(Ui.label("-", x, y + 17, f, Cyber.DIM))
            return
        for i, (kind, text) in enumerate(items):
            lbl = Ui.label(text.upper(), 0, 0, f, Cyber.TEXT)
            w = lbl.get_width() + 12
            if cx + w > x + max_w:
                more = Ui.label("+%d" % (len(items) - i), cx, y + 17, f, Cyber.MUTED)
                self.layer.add(more)
                break
            acc = Cyber.MAGENTA if kind == "tag" else Cyber.CYAN
            self.layer.add(Ui.rect(cx, y + 4, w, 18, Cyber.alpha(acc, 30), Cyber.alpha(acc, 30)))
            lbl.set_location(cx + 6, y + 17)
            lbl.set_color(acc if kind == "tag" else Cyber.TEXT)
            self.layer.add(lbl)
            cx += w + 5

    def set_page(self, p):
        self.page = p
        self.rebuild()

    def replay(self, h, idx, d):
        if self.on_replay is None or d is None:
            return
        try:
            seed = int(h.get("seed"))
        except (TypeError, ValueError):
            return
        rules = tuple(c for c in (Challenge.by_tag(t) for t in h.get("tags", []) if isinstance(t, str)) if c is not None)
        self.on_replay(idx, d, seed, bool(h.get("notes_on", True)), rules)

    # ---------------------------------------------------------------- input
    def buttons(self):
        return list(self.chrome) + list(self.content_buttons)

    def mouse_pressed(self, lx, ly):
        for b in self.buttons():
            if b.hit(lx, ly) and b.click():
                return

    def mouse_moved(self, lx, ly):
        for b in self.buttons():
            b.set_hover(b.hit(lx, ly))

    def key_pressed(self, e):
        """Esc goes back, left / right switch tabs, page up / down page through the history."""
        k = e.get_key_code()
        vals = Tab.values()
        if k == KeyEvent.VK_ESCAPE:
            self.close()
        elif k == KeyEvent.VK_RIGHT:
            self.set_tab(vals[(self.tab.ordinal + 1) % len(vals)])
        elif k == KeyEvent.VK_LEFT:
            self.set_tab(vals[(self.tab.ordinal - 1) % len(vals)])
        elif k in (KeyEvent.VK_PAGE_DOWN, KeyEvent.VK_DOWN) and self.tab is Tab.HISTORY:
            self.set_page(self.page + 1)
        elif k in (KeyEvent.VK_PAGE_UP, KeyEvent.VK_UP) and self.tab is Tab.HISTORY:
            self.set_page(max(0, self.page - 1))

    def frame(self, dt):
        for b in self.buttons():
            b.animate(dt)
