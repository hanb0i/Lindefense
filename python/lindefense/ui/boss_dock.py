"""Lindefense BossDock (ported from src/lindefense/ui/BossDock.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.ui import Ui


class BossDock(GCompound):
    """Boss health dock shown directly under the top HUD, in space reserved by shrinking the playfield (so it never covers the
track or towers). The primary boss gets a large bar (phase notches and phase name for Palantir), further bosses compact
rows (max 3 rows, then "+N more"). Bars carry a trailing "recent damage" chunk; numbers are abbreviated, monospaced and
right-anchored so they never jitter. The primary row also shows the boss's signature ability state (Crest Shield, Outsourcing
countdown, Network Hub links, Afterburner; Palantir's Swarm Uplink). Built when the boss set changes, only mutated per frame."""
    class Row:
        """One boss row."""
        def __init__(self, _outer, host, b, primary, y):
            self._outer = _outer
            self.boss = None
            self.primary = False
            self.bar = None
            self.numbers = None
            self.pct = None
            self.phase = None
            self.alert = None
            self.right_edge = 0.0
            self.last_nums = ''
            self.last_pct = ''
            self.last_phase = ''
            self.boss = b
            self.primary = primary
            accent = (Cyber.MAGENTA if b.is_palantir() else Cyber.RED)
            name_f = Cyber.display(Font.BOLD, (20 if primary else 14))
            num_f = Cyber.mono(Font.BOLD, (15 if primary else 12))
            base = ((y + 20) if primary else (y + 15))
            name = Ui.label(b.get_type().display_name.upper(), (BossDock.LEFT + 10), base, name_f, Cyber.TEXT)
            host.add(name)
            cls_ = b.get_type().get_boss_class().label
            badge_l = Ui.label(cls_, 0, 0, Cyber.mono(Font.BOLD, (11 if primary else 10)), accent)
            bw = (badge_l.get_width() + 14)
            bh = (17 if primary else 15)
            bx = ((name.get_x() + name.get_width()) + 10)
            badge = Cyber.Chamfer(bx, (base - (14 if primary else 12)), bw, bh, 4).scan(False).fill(Cyber.alpha(accent, 40)).border(accent)
            host.add(badge)
            badge_l.set_location((bx + 7), (((base - (14 if primary else 12)) + bh) - (4.5 if primary else 3.5)))
            host.add(badge_l)
            after_badge = ((bx + bw) + 12)
            self.phase = Ui.label('', after_badge, base, Cyber.mono(Font.BOLD, (12 if primary else 10)), Cyber.alpha(accent, 235))
            host.add(self.phase)
            self.alert = Ui.label('', 0, base, Cyber.mono(Font.BOLD, 12), Cyber.RED)
            host.add(self.alert)
            self.right_edge = (BossDock.RIGHT - 10)
            self.pct = Ui.label('100%', self.right_edge, base, num_f, Cyber.TEXT)
            self.pct.set_location((self.right_edge - self.pct.get_width()), base)
            self.numbers = Ui.label('', 0, base, num_f, Cyber.MUTED)
            host.add(self.pct)
            host.add(self.numbers)
            if primary:
                self.bar = Cyber.Bar((BossDock.LEFT + 10), (y + 28), ((BossDock.RIGHT - BossDock.LEFT) - 20), 18, 6)
                if b.is_palantir():
                    self.bar.notches([0.70, 0.35])
            else:
                bxs = 330.0
                self.bar = Cyber.Bar(bxs, (y + 5), ((self.right_edge - 170) - bxs), 11, 4)
            self.bar.colors((BossDock.PALANTIR_FILL if b.is_palantir() else Cyber.RED), Color(0, 0, 0, 205), Cyber.alpha(accent, 190)).trail(True, Color(255, 232, 196, 215))
            host.add(self.bar)
            self.update(0, True)
        def update(self, dt, force):
            f = self.boss.get_hp_fraction()
            self.bar.set_value(f)
            self.bar.step(dt)
            p = _j.cat(_j.to_int(float(math.ceil((f * 100)))), '%')
            if force or (not (p == self.last_pct)):
                self.last_pct = p
                self.pct.set_label(p)
                self.pct.set_location((self.right_edge - self.pct.get_width()), self.pct.get_y())
            n = _j.cat(Cyber.abbrev(self.boss.get_hp()), ' / ', Cyber.abbrev(self.boss.get_max_hp()))
            if force or (not (n == self.last_nums)):
                self.last_nums = n
                self.numbers.set_label(n)
                self.numbers.set_location(((self.pct.get_x() - 14) - self.numbers.get_width()), self.numbers.get_y())
            ph = ''
            if self.boss.is_palantir():
                ph = _j.cat('PHASE ', (self.boss.get_phase() + 1), '/3 // ', self.boss.get_phase_name().upper())
            else:
                if self.boss.is_fortified():
                    ph = _j.cat(ph, 'FORTIFIED ')
                if self.boss.is_camo():
                    ph = _j.cat(ph, 'CAMO')
            st = (self.boss.get_ability_status() if self.primary else '')
            if len(st) > 0:
                ph = (_j.cat(ph.strip(), ' // ', st) if (len(ph.strip()) > 0) else st)
            if force or (not (ph == self.last_phase)):
                self.last_phase = ph
                self.phase.set_label(ph)
            if (self.primary and self.boss.is_palantir()) and self.boss.is_telegraphing():
                t = _j.format('PREDICTIVE SURVEILLANCE %.1fs', self.boss.get_telegraph_remaining())
                Cyber.set_text(self.alert, t)
                self.alert.set_location(((self.numbers.get_x() - 24) - self.alert.get_width()), self.alert.get_y())
                flash = display_settings.calm((_j.fmod((self._outer.time * 8), 2) < 1), True)   # reduced motion: steady red
                Cyber.set_color(self.alert, (Cyber.RED if flash else Color.WHITE))
                self.bar.set_fill((BossDock.PALANTIR_FILL if flash else Color(0xffd0d8)))
            else:
                if not (len(self.alert.get_label()) == 0):
                    self.alert.set_label('')
                self.bar.set_fill((BossDock.PALANTIR_FILL if self.boss.is_palantir() else Cyber.RED))
    def __init__(self, game):
        self.game = None
        self.height = 0.0
        self.time = 0.0
        GCompound.__init__(self)
        self.shown = _j.ArrayList()
        self.rows = _j.ArrayList()
        self.content = GCompound()
        self.shown_hidden = (-1)
        self.game = game
        self.set_location(0, Ui.WORLD_Y)
        self.add(self.content)
    def get_height(self):
        """Pixel height the dock currently needs (0 when no boss is alive)."""
        return self.height
    def update(self, dt):
        self.time += dt
        lay = BossDockModel.layout(self.game.get_active_bosses())
        now = _j.ArrayList()
        if lay.primary is not None:
            _j_add(now, lay.primary)
        now.extend(lay.compact)
        if (not _j.equals(now, self.shown)) or (lay.hidden != self.shown_hidden):
            self.rebuild(lay, now)
        for r in self.rows:
            r.update(dt, False)
    def rebuild(self, lay, now):
        self.content.remove_all()
        self.rows.clear()
        self.shown.clear()
        self.shown.extend(now)
        self.shown_hidden = lay.hidden
        if lay.primary is None:
            self.height = 0.0
            return
        h = ((((BossDock.PAD_TOP + BossDock.PRIMARY_H) + (len(lay.compact) * BossDock.ROW_H)) + (BossDock.MORE_H if (lay.hidden > 0) else 0)) + BossDock.PAD_BOTTOM)
        pal = lay.primary.is_palantir()
        accent = (Cyber.MAGENTA if pal else Cyber.RED)
        back = Cyber.Chamfer((BossDock.LEFT - 2), BossDock.PAD_TOP, ((BossDock.RIGHT - BossDock.LEFT) + 4), ((h - BossDock.PAD_TOP) - 3), 12).fill(Color(8, 6, 16, 230)).border(Cyber.alpha(accent, 200)).glow(0.9).ticks(True)
        self.content.add(back)
        y = (BossDock.PAD_TOP + 4)
        _j_add(self.rows, BossDock.Row(self, self.content, lay.primary, True, y))
        y += (BossDock.PRIMARY_H - 4)
        for b in lay.compact:
            _j_add(self.rows, BossDock.Row(self, self.content, b, False, y))
            y += BossDock.ROW_H
        if lay.hidden > 0:
            more = Ui.label(_j.cat('+', lay.hidden, ' MORE'), 0, (y + 11), Cyber.mono(Font.BOLD, 11), Cyber.MUTED)
            more.set_location(((BossDock.RIGHT - 10) - more.get_width()), (y + 11))
            self.content.add(more)
        self.height = h


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.boss_dock_model import BossDockModel  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402

BossDock.serial_version_uid = 1
BossDock.PRIMARY_H = 58.0
BossDock.ROW_H = 24.0
BossDock.MORE_H = 16.0
BossDock.PAD_TOP = 3.0
BossDock.PAD_BOTTOM = 7.0
BossDock.LEFT = 12.0
BossDock.RIGHT = (Ui.WORLD_W - 12)
BossDock.PALANTIR_FILL = Color(0xff2b5c)
