"""Lindefense AttackPanel (ported from src/lindefense/ui/AttackPanel.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai.units import AttackAbility
from lindefense.ai.units import AttackUnit
from lindefense.ai.units import Role
from lindefense.enemy.boss import Boss
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType
from lindefense.enemy.types import Modifier
from lindefense.jenum import EnumSet
from lindefense.map.path import Path
from lindefense.sim.game import Game
from lindefense.tower import catalog
from lindefense.ui.cyber import Cyber
from lindefense.ui.ui import Ui
import lindefense.ai.reverse_match as _m_reverse_match


class AttackPanel(GCompound):
    """Reverse mode's right-hand panel (it replaces the tower shop while the player is the attacker): the doctrine, compute
credits with the SCALE COMPUTE investment, the round box (round, time left, the round track with the overtime slot and
this round's breach objective), the 21 unit cards (enemy art, price, unlock time, an EDGE / COUNTERED matchup tag;
click to send), modifier toggles, send quantity and lane (with the AI's lane coverage), the three exploits with
cooldowns, the uplink queue, and a context box that shows the hovered unit, a selected tower (read-only: the AI controls
it), a selected enemy, or else the defender AI's activity feed. Built once; per frame only colours, enabled states and
labels change, and the context box is rebuilt only when what it shows changes."""
    class Card:
        """One unit card."""
        def __init__(self, unit, button, name, price, veil, tag, tag_bg):
            self.unit = unit
            self.button = button
            self.name = name
            self.price = price
            self.veil = veil
            self.tag = tag         # EDGE / COUNTERED matchup label (third row)
            self.tag_bg = tag_bg
    def __init__(self, screen):
        self.screen = None
        self.game = None
        self.match = None
        self.help_btn = None
        self.compute_btn = None
        self.lane_btn = None
        self.credits = None
        self.income = None
        self.uplink = None
        self.hint = None
        self.queue_bar = None
        self.enemy_bar = None
        self.last_sent = None
        self.hovered = None
        self.refresh = 0.0
        self.hint_time = 0.0
        self.y = 0.0
        GCompound.__init__(self)
        self.buttons = _j.ArrayList()
        self.cards = _j.ArrayList()
        self.mod_btns = ([None] * len(Modifier.values()))
        self.qty_btns = ([None] * len(AttackPanel.QUANTITIES))
        self.exploit_btns = ([None] * len(AttackAbility.values()))
        self.exploit_bars = ([None] * len(AttackAbility.values()))
        self.exploit_meta = ([None] * len(AttackAbility.values()))
        self.info = GCompound()
        self.info_buttons = _j.ArrayList()
        self.dyn = _j.ArrayList()
        self.mods = EnumSet.none_of()
        self.qty_index = 1
        self.lane = (-1)
        self.built_key = ''
        self.tx = (AttackPanel.X0 + 22)
        self.tw = (Ui.PANEL_W - 44)
        self.screen = screen
        self.game = screen.get_game()
        self.match = self.game.get_reverse()
        self.add(Ui.rect(AttackPanel.X0, 0, Ui.PANEL_W, Ui.H, AttackPanel.BG, AttackPanel.BG))
        self.add(Ui.rect(AttackPanel.X0, 0, 1, Ui.H, Cyber.EDGE, Cyber.EDGE))
        title = Ui.label('UPLINK', (AttackPanel.X0 + 18), 28, Cyber.display(Font.BOLD, 20), Cyber.TEXT)
        self.add(title)
        doc = self.match.get_doctrine()
        dc = Ui.c(doc.rgb)
        dl = Ui.label(doc.display_name.upper() + ' DOCTRINE', 0, 0, Cyber.mono(Font.BOLD, 11), dc)
        dx = title.get_x() + title.get_width() + 14
        self.add(Cyber.Chamfer(dx, 11, dl.get_width() + 14, 20, 3).fill(Cyber.alpha(dc, 30)).border(None))
        dl.set_location(dx + 7, 25)
        self.add(dl)
        self.help_btn = self.button((((AttackPanel.X0 + Ui.PANEL_W) - 8) - 92), 8, 92, 26, '? HELP  [H]', Cyber.mono(Font.BOLD, 11), _j.Fn(screen.toggle_help))
        self.add(Cyber.Chamfer((AttackPanel.X0 + AttackPanel.PAD), 38, AttackPanel.INNER, 62, 4).fill(Cyber.SURFACE_2).border(None))
        self.add(Ui.label('Compute credits', (AttackPanel.X0 + 20), 53, AttackPanel.F_MICRO, Cyber.MUTED))
        self.credits = Ui.label('', (AttackPanel.X0 + 20), 79, Cyber.mono(Font.BOLD, 26), Cyber.YELLOW)
        self.add(self.credits)
        self.income = Ui.label('', 0, 79, Cyber.mono(Font.BOLD, 14), Cyber.GREEN)
        self.add(self.income)
        track = Ui.label(self.track_text(), (AttackPanel.X0 + 20), 94, AttackPanel.F_MICRO, Cyber.MUTED)
        self.add(track)
        self.compute_btn = self.button((AttackPanel.X0 + AttackPanel.PAD), 104, AttackPanel.INNER, 28, '', Cyber.display(Font.BOLD, 15), _j.Fn(self.scale_compute))
        self.compute_btn.set_accent(Cyber.YELLOW)
        self.build_round_box()
        units = AttackUnit.values()
        for i in range(len(units)):
            x = ((AttackPanel.X0 + AttackPanel.PAD) + (_j.imod(i, AttackPanel.COLS) * (AttackPanel.CARD_W + AttackPanel.GAP)))
            y = (AttackPanel.CARD_Y + (_j.idiv(i, AttackPanel.COLS) * (AttackPanel.CARD_H + AttackPanel.GAP)))
            _j_add(self.cards, self.card(units[i], x, y))
        ms = Modifier.values()
        mw = ((AttackPanel.INNER - AttackPanel.GAP) / 2)
        for i in range(len(ms)):
            m = ms[i]
            b = self.button(((AttackPanel.X0 + AttackPanel.PAD) + (_j.imod(i, 2) * (mw + AttackPanel.GAP))), (AttackPanel.MODS_Y + (_j.idiv(i, 2) * AttackPanel.MOD_ROW)), mw, AttackPanel.MOD_H, '', Cyber.display(Font.BOLD, 13), _j.Fn(lambda m=m: self.toggle_mod(m)))   # m=m: bind this iteration's value (Python closures are late-binding)
            b.set_accent((Cyber.lerp(Cyber.CYAN, Color.WHITE, 0.2) if (m is Modifier.CAMO) else (Cyber.GREEN if (m is Modifier.REGROW) else (Cyber.MAGENTA if (m is Modifier.INJECTION) else Cyber.YELLOW))))
            self.mod_btns[i] = b
        self.add(Ui.label('Send', (AttackPanel.X0 + 14), (AttackPanel.SEND_Y + 20), AttackPanel.F_MICRO, Cyber.MUTED))
        qx = (AttackPanel.X0 + 52)
        for i in range(len(AttackPanel.QUANTITIES)):
            k = i
            def _lam1(k=k):   # k=k: bind this iteration's index
                self.qty_index = k
            b = self.button((qx + (i * 44)), AttackPanel.SEND_Y, 42, AttackPanel.ROW_H, _j.cat('x', AttackPanel.QUANTITIES[i]), Cyber.mono(Font.BOLD, 13), _j.Fn(_lam1))
            b.set_flat(True)
            self.qty_btns[i] = b
        lx = ((qx + (len(AttackPanel.QUANTITIES) * 44)) + 8)
        self.lane_btn = self.button(lx, AttackPanel.SEND_Y, (((AttackPanel.X0 + AttackPanel.PAD) + AttackPanel.INNER) - lx), AttackPanel.ROW_H, '', Cyber.display(Font.BOLD, 13), _j.Fn(self.cycle_lane))
        self.lane_btn.set_accent(Cyber.CYAN)
        self.lane_btn.set_enabled((len(self.game.get_map().get_routes()) > 1))
        as_ = AttackAbility.values()
        ew = ((AttackPanel.INNER - (2 * AttackPanel.GAP)) / 3)
        for i in range(len(as_)):
            a = as_[i]
            ex = ((AttackPanel.X0 + AttackPanel.PAD) + (i * (ew + AttackPanel.GAP)))
            b = self.button(ex, AttackPanel.EXPLOIT_Y, ew, AttackPanel.EXPLOIT_H, a.display_name.upper(), Cyber.display(Font.BOLD, 15), _j.Fn(lambda a=a: self.use_exploit(a)))   # a=a: bind this iteration's exploit
            b.set_accent(Cyber.MAGENTA)
            self.exploit_btns[i] = b
            self.exploit_bars[i] = Cyber.Bar((ex + 2), ((AttackPanel.EXPLOIT_Y + AttackPanel.EXPLOIT_H) + 3), (ew - 4), 3, 0).colors(Cyber.MAGENTA, Color(255, 255, 255, 28), None)
            self.add(self.exploit_bars[i])
            self.exploit_meta[i] = Ui.label('', (ex + 2), ((AttackPanel.EXPLOIT_Y + AttackPanel.EXPLOIT_H) + 17), AttackPanel.F_MICRO, Cyber.MUTED)
            self.add(self.exploit_meta[i])
        self.uplink = Ui.label('', (AttackPanel.X0 + 14), (AttackPanel.UPLINK_Y + 8), AttackPanel.F_MICRO, Cyber.MUTED)
        self.add(self.uplink)
        self.queue_bar = Cyber.Bar((AttackPanel.X0 + 150), (AttackPanel.UPLINK_Y + 1), 110, 6, 0).colors(Cyber.CYAN, Color(255, 255, 255, 26), None)
        self.add(self.queue_bar)
        self.hint = Ui.label('', (AttackPanel.X0 + 270), (AttackPanel.UPLINK_Y + 8), AttackPanel.F_MICRO, Cyber.GREEN)
        self.add(self.hint)
        self.add(Cyber.Chamfer((AttackPanel.X0 + AttackPanel.PAD), AttackPanel.INFO_Y, AttackPanel.INNER, ((Ui.H - AttackPanel.INFO_Y) - 8), 4).fill(Cyber.SURFACE_2).border(None))
        self.add(self.info)
        self.refresh_static()
    def button(self, x, y, w, h, text, f, r):
        b = UIButton(x, y, w, h, text, f, r)
        self.add(b)
        _j_add(self.buttons, b)
        return b
    def track_text(self):
        b = self.match.get_track_bonus()
        s = self.match.get_track_speed()
        lanes = len(self.game.get_map().get_routes())
        l = _j.cat(lanes, (' LANE' if (lanes == 1) else ' LANES'))
        if (b <= 1) and (s <= 1):
            return _j.cat(l, '  ·  STANDARD TRACK')
        return _j.cat(l, '  ·  LONG TRACK: UNITS x', Ui.fmt((_j.jround((s * 100)) / 100.0)), ' SPEED, COMPUTE x', Ui.fmt((_j.jround((b * 100)) / 100.0)))
    def card(self, u, x, y):
        """A unit card: click target first, the enemy's own art, short name, price and matchup tag over it, a veil while
locked."""
        b = self.button(x, y, AttackPanel.CARD_W, AttackPanel.CARD_H, '', Cyber.mono(Font.BOLD, 1), _j.Fn(lambda : self.send(u)))
        b.set_accent((Cyber.RED if u.is_boss() else Cyber.CYAN))
        box = 42.0
        icon = AttackPanel.enemy_icon(u.type, box)
        icon.set_location((x + 3), (y + ((AttackPanel.CARD_H - box) / 2)))
        self.add(icon)
        label = AttackPanel.short_name(u.type)
        name = Ui.label(label, (x + 48), (y + 21), AttackPanel.fit(label, Cyber.display(Font.BOLD, 15), (AttackPanel.CARD_W - 52), 9), Cyber.TEXT)
        self.add(name)
        price = Ui.label('', (x + 48), (y + 37), AttackPanel.F_PRICE, Cyber.YELLOW)
        self.add(price)
        tag_bg = Cyber.Chamfer((x + 47), (y + 42), 10, 11, 2).fill(None).border(None)
        self.add(tag_bg)
        tag = Ui.label('', (x + 51), (y + 51), AttackPanel.F_TAG, Cyber.good())
        self.add(tag)
        veil = Cyber.Chamfer((x + 1), (y + 1), (AttackPanel.CARD_W - 2), (AttackPanel.CARD_H - 2), 4).fill(Color(6, 8, 18, 170)).border(None)
        self.add(veil)
        return AttackPanel.Card(u, b, name, price, veil, tag, tag_bg)
    def build_round_box(self):
        """The round box under SCALE COMPUTE: round and time left, the round track (one slot per round, lit by its breach
objective, the final round in red and the overtime slot after it), and this round's objective with its progress."""
        x0 = AttackPanel.X0 + AttackPanel.PAD
        y0 = AttackPanel.ROUND_Y
        self.add(Cyber.Chamfer(x0, y0, AttackPanel.INNER, AttackPanel.ROUND_H, 4).fill(Cyber.SURFACE_2).border(None))
        self.round_label = Ui.label('', x0 + 12, y0 + 17, Cyber.body(Font.BOLD, 13), Cyber.TEXT)
        self.add(self.round_label)
        self.round_clock = Ui.label('', 0, y0 + 17, Cyber.mono(Font.BOLD, 13), Cyber.TEXT)
        self.add(self.round_clock)
        n = ReverseMatch.ROUNDS
        tw = AttackPanel.INNER - 24
        ot_w = 34.0
        gap = 3.0
        sw = (tw - ot_w - gap - (n - 1) * gap) / n
        self.round_bars = []
        for i in range(n):
            back = Cyber.alpha(Cyber.RED, 46) if i == n - 1 else Color(255, 255, 255, 26)
            bar = Cyber.Bar(x0 + 12 + i * (sw + gap), y0 + 23, sw, 9, 0).colors(Cyber.MAGENTA, back, None)
            bar.set_value(0)
            self.add(bar)
            self.round_bars.append(bar)
        ox = x0 + 12 + n * (sw + gap)
        self.ot_bar = Cyber.Bar(ox, y0 + 23, ot_w, 9, 0).colors(Cyber.RED, Cyber.alpha(Cyber.RED, 22), None)
        self.ot_bar.set_value(0)
        self.add(self.ot_bar)
        self.ot_label = Ui.label('OT', 0, y0 + 17, Cyber.mono(Font.BOLD, 9), Cyber.alpha(Cyber.RED, 170))
        self.ot_label.set_location(ox + (ot_w - self.ot_label.get_width()) / 2, y0 + 31)
        self.add(self.ot_label)
        self.objective = Ui.label('', x0 + 12, y0 + 46, AttackPanel.F_OBJ, Cyber.MUTED)
        self.add(self.objective)
        self.objective_count = Ui.label('', 0, y0 + 46, Cyber.mono(Font.BOLD, 12), Cyber.TEXT)
        self.add(self.objective_count)
    def refresh_round_box(self):
        """Round, clocks, the track and the objective line (label / colour mutations only)."""
        r = self.match
        g = self.game
        x0 = AttackPanel.X0 + AttackPanel.PAD
        right = x0 + AttackPanel.INNER - 12
        n = ReverseMatch.ROUNDS
        cur = r.get_round_index()
        closed = r.is_uplink_closed()
        over = g.get_state() is not Game.State.PLAYING
        if over:
            head, head_c = ('Training over: breach' if r.attacker_won() else 'Training over: contained'), (Cyber.YELLOW if r.attacker_won() else Cyber.MUTED)
            clk = ReverseMatch.clock(r.get_elapsed())
        elif closed:
            head, head_c = 'Uplink closed', Cyber.YELLOW
            clk = ReverseMatch.clock(r.get_drain_left())
        elif r.is_overtime():
            head, head_c = 'Sudden-death overtime', Cyber.RED
            clk = ReverseMatch.clock(r.get_time_left())
        elif r.is_final_round():
            head, head_c = _j.cat('Final round  ', n, ' / ', n), Cyber.lerp(Cyber.RED, Color.WHITE, 0.25)
            clk = ReverseMatch.clock(r.round_time_left())
        else:
            head, head_c = _j.cat('Round ', cur + 1, ' / ', n), Cyber.TEXT
            clk = ReverseMatch.clock(r.round_time_left())
        Cyber.set_text(self.round_label, head)
        Cyber.set_color(self.round_label, head_c)
        Cyber.set_text(self.round_clock, clk)
        Cyber.set_color(self.round_clock, Cyber.MUTED if closed else Cyber.TEXT)
        self.round_clock.set_location(right - self.round_clock.get_width(), self.round_clock.get_y())
        for i in range(n):
            bar = self.round_bars[i]
            goal = r.round_goal(i)
            taken = r.round_taken(i)
            if r.objective_met(i):
                bar.set_fill(Cyber.good())
                bar.set_value(1)
            elif i < r.get_rounds_done() or (closed and i <= cur):
                bar.set_fill(Cyber.DIM)
                bar.set_value(taken / float(max(1, goal)))
            elif i == cur and not r.is_overtime():
                bar.set_fill(Cyber.MAGENTA)
                bar.set_value(taken / float(max(1, goal)))
            else:
                bar.set_value(0)
        self.ot_bar.set_value(1 if r.is_overtime() else 0)
        Cyber.set_color(self.ot_label, Cyber.TEXT if r.is_overtime() else Cyber.alpha(Cyber.RED, 170))
        if over:
            obj, oc, cnt = _j.cat(r.get_objectives_met(), ' of ', n, ' round objectives met'), Cyber.MUTED, ''
        elif closed:
            obj, oc, cnt = 'Units already sent are finishing their run', Cyber.MUTED, ''
        elif r.is_overtime():
            obj, oc, cnt = 'Break the AI before the uplink closes', Cyber.lerp(Cyber.RED, Color.WHITE, 0.3), _j.cat(g.get_lives(), ' LEFT')
        elif r.objective_met():
            obj, oc, cnt = 'Objective complete: round won', Cyber.good(), _j.cat(r.round_taken(), ' / ', r.round_goal())
        else:
            obj = _j.cat('Breach ', r.round_goal(), ' this round for +', Cyber.commas(r.objective_reward()))
            oc, cnt = Cyber.MUTED, _j.cat(r.round_taken(), ' / ', r.round_goal())
        Cyber.set_text(self.objective, obj)
        Cyber.set_color(self.objective, oc)
        Cyber.set_text(self.objective_count, cnt)
        Cyber.set_color(self.objective_count, Cyber.good() if r.objective_met() else Cyber.TEXT)
        self.objective_count.set_location(right - self.objective_count.get_width(), self.objective_count.get_y())
    @staticmethod
    def enemy_icon(t, box):
        """The enemy's own sprite, painted once into a clipped square image (2x supersampled): boss sprites carry name banners
wider than a card, so drawing them live would spill over the neighbouring cards and the playfield."""
        px = _j.to_int(_j.jround((box * 2)))
        img = BufferedImage(px, px, BufferedImage.TYPE_INT_ARGB)
        g2 = img.create_graphics()
        try:
            Cyber.quality(g2)
            p = Path('icon', (-1), 0, 1, 0)
            model = (Boss(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0) if t.is_boss() else Enemy(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0))
            sprite = SpriteFactory.create(model)
            sprite.sync(model, 0.4)
            scale = (2 * _j.dmin(1.6, (box / (t.radius * (2.0 if t.is_boss() else 2.2)))))
            g2.translate((px / 2.0), (px / 2.0))
            g2.scale(scale, scale)
            g2.translate(1, 0)
            sprite.paint(g2)
        finally:
            g2.dispose()
        gi = GImage(img)
        gi.set_size(box, box)
        return gi
    @staticmethod
    def short_name(t):
        """Card label: the display name, minus the trailing "Sort" family word where space is tight."""
        _sw1 = t
        if _sw1 is EnemyType.BELLARMINE_COLLEGE_PREP:
            return 'Bellarmine'
        elif _sw1 is EnemyType.SW_RESOURCE_CONSULTANT:
            return 'SW Consultant'
        elif _sw1 is EnemyType.LOCKHEED_MARTIN:
            return 'Lockheed'
        elif _sw1 is EnemyType.SINGLY_LINKED_LIST:
            return 'Singly List'
        elif _sw1 is EnemyType.DOUBLY_LINKED_LIST:
            return 'Doubly List'
        elif _sw1 is EnemyType.PRIMITIVE_VARIABLE:
            return 'Primitive'
        else:
            return t.display_name
    @staticmethod
    def fit(text, f, max_width, min_size):
        probe = Cyber.Text(text)
        cur = f
        probe.set_font(cur)
        while (probe.get_width() > max_width) and (cur.get_size() > min_size):
            cur = cur.derive_font(float((cur.get_size() - 1)))
            probe.set_font(cur)
        return cur
    @staticmethod
    def card_center(index):
        """Logical centre of the card of AttackUnit.values()[index] (for tools and tests that click through the UI)."""
        return [(((AttackPanel.X0 + AttackPanel.PAD) + (_j.imod(index, AttackPanel.COLS) * (AttackPanel.CARD_W + AttackPanel.GAP))) + (AttackPanel.CARD_W / 2)), ((AttackPanel.CARD_Y + (_j.idiv(index, AttackPanel.COLS) * (AttackPanel.CARD_H + AttackPanel.GAP))) + (AttackPanel.CARD_H / 2))]
    def get_buttons(self):
        """Every clickable button of the panel (for hit-testing and hover)."""
        all_ = _j.ArrayList(self.buttons)
        all_.extend(self.info_buttons)
        return all_
    def request_rebuild(self):
        """Forces the context box to rebuild on the next frame."""
        self.built_key = ''
    def quantity(self):
        return AttackPanel.QUANTITIES[self.qty_index]
    def send(self, u):
        """Buys #quantity() of the unit with the toggled modifiers on the chosen lane."""
        why = self.match.send_problem(u, self.mods, 1)
        if why is not None:
            self.show_hint(_j.cat(u.type.display_name, ': ', why.lower()), Cyber.bad())
            AudioManager.sfx(Sfx.INVALID)
            return
        n = self.match.send(u, self.mods, self.quantity(), self.lane)
        self.last_sent = u
        self.show_hint(_j.cat('SENT ', n, ' x ', AttackPanel.short_name(u.type).upper()), Cyber.good())
        AudioManager.sfx(Sfx.UI_SELECT)
    def scale_compute(self):
        why = self.match.compute_problem()
        if why is not None:
            self.show_hint(_j.cat('Compute: ', why.lower()), Cyber.bad())
            return
        self.match.scale_compute()
        self.show_hint(_j.cat('COMPUTE +', self.match.compute_step(), '/s'), Cyber.YELLOW)
        AudioManager.sfx(Sfx.CASH)
    def use_exploit(self, a):
        why = self.match.ability_problem(a)
        if why is not None:
            self.show_hint(_j.cat(a.display_name, ': ', why.lower()), Cyber.bad())
            AudioManager.sfx(Sfx.INVALID)
            return
        self.match.use_ability(a)
        self.show_hint(_j.cat(a.display_name.upper(), '!'), Cyber.MAGENTA)
        AudioManager.sfx(Sfx.ABILITY)
    def toggle_mod(self, m):
        if not self.match.is_unlocked(m):
            self.show_hint(_j.cat(m.label, ' unlocks at ', ReverseMatch.clock(self.match.unlock_at(m))), Cyber.RED)
            return
        if not _j_remove(self.mods, m):   # Java's Set.remove: false (no KeyError) when absent
            self.mods.add(m)
    def cycle_lane(self):
        n = len(self.game.get_map().get_routes())
        if n < 2:
            return
        self.lane = ((-1) if ((self.lane + 1) >= n) else (self.lane + 1))
    def show_hint(self, s, c):
        Cyber.set_text(self.hint, (_j.cat(s[0:33], '…') if (len(s) > 34) else s))
        Cyber.set_color(self.hint, c)
        self.hint_time = 2.5
    def key_pressed(self, e):
        """Reverse-mode hotkeys; returns true if the key was handled."""
        _sw2 = e.get_key_code()
        if _sw2 == KeyEvent.VK_SPACE:
            if self.last_sent is not None:
                self.send(self.last_sent)
            else:
                self.show_hint('Click a unit card first', Cyber.MUTED)
            return True
        elif _sw2 == KeyEvent.VK_X:
            self.qty_index = _j.imod((self.qty_index + 1), len(AttackPanel.QUANTITIES))
            return True
        elif _sw2 == KeyEvent.VK_L:
            self.cycle_lane()
            return True
        elif _sw2 == KeyEvent.VK_C:
            self.scale_compute()
            return True
        elif _sw2 == KeyEvent.VK_Q:
            self.use_exploit(AttackAbility.OVERCLOCK)
            return True
        elif _sw2 == KeyEvent.VK_W:
            self.use_exploit(AttackAbility.HOTFIX)
            return True
        elif _sw2 == KeyEvent.VK_E:
            self.use_exploit(AttackAbility.ZERO_DAY)
            return True
        else:
            return False
    def update(self, dt):
        """Per-frame update: hover, live labels, enabled states, and the context box when its subject changes."""
        self.refresh -= dt
        if self.hint_time > 0:
            self.hint_time -= dt
            if self.hint_time <= 0:
                Cyber.set_text(self.hint, '')
        m = self.screen.get_mouse_logical()
        hv = None
        for c in self.cards:
            if c.button.hit(m[0], m[1]):
                hv = c
                break
        if hv is not self.hovered:
            self.hovered = hv
            self.built_key = ''
        self.refresh_static()
        key = self.context_key()
        if not (key == self.built_key):
            self.built_key = key
            self.rebuild_info()
            self.refresh = 0.25
            self.screen.refresh_hover()
        elif self.refresh <= 0:
            self.refresh = 0.25
            for r in self.dyn:
                r()
        if (self.enemy_bar is not None) and (self.screen.get_selected_enemy() is not None):
            self.enemy_bar.set_value(self.screen.get_selected_enemy().get_hp_fraction())
            self.enemy_bar.set_fill(Cyber.hp_color(self.screen.get_selected_enemy().get_hp_fraction()))
    def refresh_static(self):
        """Credits, prices, locks, toggles, matchup tags, the round box and cooldowns: cheap label / colour mutations every
frame."""
        r = self.match
        cr = r.get_credits()
        Cyber.set_text(self.credits, ('ADMIN ∞' if r.has_unlimited_credits() else Ui.money(cr)))
        Cyber.set_text(self.income, _j.cat('+', _j.to_int(_j.jround(r.income_rate())), '/s'))
        Cyber.set_color(self.income, (Cyber.RED if (r.is_overtime() and not r.is_uplink_closed()) else Cyber.GREEN))
        self.income.set_location(((((AttackPanel.X0 + AttackPanel.PAD) + AttackPanel.INNER) - 12) - self.income.get_width()), 79)
        cp = r.compute_problem()
        AttackPanel.text(self.compute_btn, ('COMPUTE FULLY SCALED' if (r.get_compute_level() >= r.compute_max()) else _j.cat('SCALE COMPUTE  +', r.compute_step(), '/s   ', Ui.money(r.compute_price()), '   [C]')))
        self.compute_btn.set_enabled((cp is None))
        self.refresh_round_box()
        self.lane_btn.set_enabled(((len(self.game.get_map().get_routes()) > 1) and (self.game.get_state() is Game.State.PLAYING)))
        open_ = ((self.game.get_state() is Game.State.PLAYING) and (not r.is_uplink_closed()))
        for c in self.cards:
            unlocked = r.is_unlocked(c.unit)
            p = r.price(c.unit, self.mods, 1)
            ok = (unlocked and (r.send_problem(c.unit, self.mods, 1) is None))
            c.veil.set_visible((not unlocked))
            c.button.set_enabled((unlocked and open_))
            c.button.set_selected(((c.unit is self.last_sent) and unlocked))
            self.set_price(c, (_j.cat(Ui.money(p), (_j.cat(' x', self.quantity()) if (self.quantity() > 1) else '')) if unlocked else _j.cat('AT ', ReverseMatch.clock(r.unlock_at(c.unit)))))
            Cyber.set_color(c.price, (Cyber.MUTED if (not unlocked) else (Cyber.YELLOW if ok else Cyber.cant_afford())))
            Cyber.set_color(c.name, ((Cyber.lerp(Cyber.RED, Color.WHITE, 0.35) if c.unit.is_boss() else Cyber.TEXT) if unlocked else Cyber.DIM))
            st = r.unit_status(c.unit, self.mods) if (unlocked and open_) else None
            self.set_tag(c, st)
        ms = Modifier.values()
        blind = r.role_status(Role.CAMO) == 'edge'
        for i in range(len(ms)):
            un = r.is_unlocked(ms[i])
            self.mod_btns[i].set_enabled((un and open_))
            self.mod_btns[i].set_selected((un and (ms[i] in self.mods)))
            if not un:
                t = _j.cat(ms[i].label.upper(), '  ', ReverseMatch.clock(r.unlock_at(ms[i])))
            elif ms[i] is Modifier.CAMO and blind and open_:
                t = _j.cat('CAMO  x', Ui.fmt(AttackUnit.modifier_factor(ms[i])), '  · AI BLIND')
            else:
                t = _j.cat(ms[i].label.upper(), '  x', Ui.fmt(AttackUnit.modifier_factor(ms[i])))
            AttackPanel.text(self.mod_btns[i], t)
        for i in range(len(self.qty_btns)):
            self.qty_btns[i].set_selected((i == self.qty_index))
        AttackPanel.text(self.lane_btn, self.lane_text())
        as_ = AttackAbility.values()
        for i in range(len(as_)):
            a = as_[i]
            un = r.is_unlocked(a)
            cd = r.cooldown_left(a)
            why = r.ability_problem(a)
            self.exploit_btns[i].set_enabled(((un and (cd <= 0)) and open_))
            self.exploit_btns[i].set_selected(((a is AttackAbility.OVERCLOCK) and (r.get_overclock_left() > 0)))
            self.exploit_bars[i].set_value(((1 - (cd / r.ability_cooldown(a))) if un else 0))
            self.exploit_bars[i].set_fill((Cyber.MAGENTA if ((cd <= 0) and un) else Cyber.DIM))
            key = 'QWE'[i:(i + 1)]
            meta = ('OFFLINE' if (not open_) else (_j.cat('UNLOCKS ', ReverseMatch.clock(r.unlock_at(a))) if (not un) else (_j.cat('RECHARGING ', _j.to_int(float(math.ceil(cd))), 's') if (cd > 0) else _j.cat(Ui.money(r.ability_cost(a)), '  [', key, ']'))))
            Cyber.set_text(self.exploit_meta[i], meta)
            short = (why is not None) and (why == 'Not enough credits')
            Cyber.set_color(self.exploit_meta[i], (Cyber.DIM if (not un) else (Cyber.MUTED if (cd > 0) else (Cyber.cant_afford() if short else Cyber.YELLOW))))
        q = r.get_queued()
        Cyber.set_text(self.uplink, ('UPLINK CLOSED' if r.is_uplink_closed() else (_j.cat('HANDSHAKE ', ReverseMatch.clock((ReverseMatch.HANDSHAKE - r.get_elapsed()))) if (r.get_elapsed() < ReverseMatch.HANDSHAKE) else _j.cat('UPLINK  ', q, ' QUEUED'))))
        self.queue_bar.set_value((q / float(r.max_queue())))
    def set_price(self, c, txt):
        """The card's price line, in a smaller font when a big price and quantity would run past the card."""
        if txt == c.price.get_label():
            return
        Cyber.set_text(c.price, txt)
        f = AttackPanel.F_PRICE
        c.price.set_font(f)
        if c.price.get_width() > AttackPanel.CARD_W - 52:
            c.price.set_font(AttackPanel.fit(txt, f, AttackPanel.CARD_W - 52, 8))
    def set_tag(self, c, st):
        """The card's third row: EDGE (good colour) while the AI cannot answer the unit's role, COUNTERED (bad colour) after
it adapted against it, else nothing."""
        txt = 'EDGE' if st == 'edge' else ('COUNTERED' if st == 'countered' else '')
        col = Cyber.good() if st == 'edge' else Cyber.bad()
        if txt == c.tag.get_label() and (not txt or col == c.tag.get_color()):
            return
        Cyber.set_text(c.tag, txt)
        if not txt:
            c.tag_bg.set_visible(False)
            return
        Cyber.set_color(c.tag, col)
        c.tag_bg.fill(Cyber.alpha(col, 34)).size(c.tag.get_width() + 8, 12)
        c.tag_bg.set_visible(True)
    def lane_text(self):
        """The lane button: the chosen lane and how the AI covers it (OPEN / EVEN / HEAVY); on ALL, the open lane if any."""
        routes = len(self.game.get_map().get_routes())
        if routes < 2:
            return '1 LANE'
        if self.lane < 0:
            w = self.match.weakest_lane()
            if w >= 0 and self.match.lane_label(w) == 'OPEN':
                return _j.cat('ALL  ·  L', w + 1, ' OPEN')
            return 'ALL LANES  [L]'
        lbl = self.match.lane_label(self.lane)
        return _j.cat('LANE ', self.lane + 1, ('' if lbl is None else _j.cat('  ·  ', lbl)))
    @staticmethod
    def text(b, s):
        """Sets a button's text only when it changes (a set re-measures and repaints the label)."""
        if not (s == b.get_text()):
            b.set_text(s)
    def context_key(self):
        t = self.screen.get_selected_tower()
        if self.hovered is not None:
            return _j.cat('U', self.hovered.unit, self.mods, self.qty_index, self.match.is_unlocked(self.hovered.unit), self.match.unit_status(self.hovered.unit, self.mods))
        if (t is not None) and t.is_alive():
            return _j.cat('T', t.get_id(), ':', t.get_tier(), ':', t.is_ability_locked())
        if self.screen.get_selected_enemy() is not None:
            return _j.cat('E', self.screen.get_selected_enemy().get_id())
        n = len(self.match.get_feed())
        last = (None if (n == 0) else self.match.get_feed()[(n - 1)])
        return _j.cat('F', n, ':', (0 if (last is None) else _j.identity_hash(last)))
    def _put_0(self, s, x, baseline, f, c):
        l = Ui.label(s, x, baseline, f, c)
        self.info.add(l)
        return l
    def _put_1(self, s, f, c):
        self.put(s, self.tx, self.y, f, c)
    def put(self, *a):
        if len(a) == 3:
            return self._put_1(*a)
        elif len(a) == 5:
            return self._put_0(*a)
        raise TypeError('no overload for %d args' % len(a))
    def section(self, title, c):
        self.y += 10
        l = self.put((title[0:1].upper() + title[1:]), self.tx, (self.y + 9), Cyber.body(Font.BOLD, 12), Cyber.MUTED)
        ln = GLine(((self.tx + l.get_width()) + 10), (self.y + 5.5), (self.tx + self.tw), (self.y + 5.5))
        ln.set_color(Cyber.EDGE)
        self.info.add(ln)
        self.y += 13
    def para(self, s, f, c, max_lines):
        n = 0
        for l in Ui.wrap(s, f, self.tw):
            if (max_lines > 0) and (((n := n + 1) - 1) >= max_lines):
                break
            self.y += (f.get_size() + 4)
            self.put(l, self.tx, self.y, f, c)
    def stat_cell(self, cx, cy, label, val, vc):
        self.put((label[0:1].upper() + label[1:]), cx, (cy + 9), AttackPanel.F_MICRO, Cyber.MUTED)
        v = self.put(val(), cx, (cy + 26), AttackPanel.F_VAL, vc)
        _j_add(self.dyn, _j.Fn(lambda : Cyber.set_text(v, val())))
    def rebuild_info(self):
        self.info.remove_all()
        self.info_buttons.clear()
        self.dyn.clear()
        self.enemy_bar = None
        self.y = (AttackPanel.INFO_Y + 4)
        t = self.screen.get_selected_tower()
        if self.hovered is not None:
            self.build_unit_info(self.hovered.unit)
        elif (t is not None) and t.is_alive():
            self.build_tower_info(t)
        elif self.screen.get_selected_enemy() is not None:
            self.build_enemy_info(self.screen.get_selected_enemy())
        else:
            self.build_feed()
    def header(self, name, col, badge, badge_col):
        self.y += 26
        nf = AttackPanel.fit(name, Cyber.display(Font.BOLD, 22), (self.tw - 110), 12)
        self.put(name, self.tx, self.y, nf, col)
        if badge is not None:
            b = Ui.label(badge, 0, 0, Cyber.mono(Font.BOLD, 10), badge_col)
            bw = (b.get_width() + 14)
            bx = ((self.tx + self.tw) - bw)
            self.info.add(Cyber.Chamfer(bx, (self.y - 14), bw, 18, 3).fill(Cyber.alpha(badge_col, 32)).border(None))
            b.set_location((bx + 7), (self.y - 1))
            self.info.add(b)
    def build_unit_info(self, u):
        """The hovered unit card: what it is, its role and matchup, what it costs with the toggled modifiers, what the AI
earns if it dies and what a leak pays."""
        t = u.type
        r = self.match
        badge = (_j.cat(t.get_boss_class().label, '-CLASS') if u.is_boss() else u.role.label.upper())
        self.header(t.display_name, (Cyber.lerp(Cyber.RED, Color.WHITE, 0.3) if u.is_boss() else Cyber.TEXT), badge, (Cyber.RED if u.is_boss() else Cyber.MAGENTA))
        self.para(u.blurb, AttackPanel.F_TXT, Cyber.MUTED, 2)
        eff = r.effective_modifiers(u, self.mods)
        hp = (max(1, _j.jround((t.base_hp * r.unit_hp_scale(t)))) * (2 if (Modifier.FORTIFIED in eff) else 1))
        self.y += 4
        cw = (self.tw / 3)
        self.stat_cell(self.tx, self.y, 'health', _j.Fn(lambda : Cyber.commas(hp)), Cyber.TEXT)
        self.stat_cell((self.tx + cw), self.y, 'speed', _j.Fn(lambda : _j.cat(Ui.fmt((_j.jround(((t.speed * r.get_track_speed()) * 100)) / 100.0)), 'x')), Cyber.TEXT)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'integrity', _j.Fn(lambda : _j.s(t.lives)), Cyber.RED)
        self.y += 36
        self.stat_cell(self.tx, self.y, 'price', _j.Fn(lambda : Ui.money(r.price(u, self.mods, 1))), Cyber.YELLOW)
        self.stat_cell((self.tx + cw), self.y, 'AI bounty', _j.Fn(lambda : Ui.money((t.reward * _m_reverse_match.KILL_REWARD_SCALE))), Cyber.GREEN)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'leak pays', _j.Fn(lambda : _j.cat('+', _j.to_int(_j.jround(r.leak_pay(t.lives))))), Cyber.CYAN)
        self.y += 32
        why = r.edge_reason(u, self.mods)
        if not r.is_unlocked(u):
            self.para(_j.cat('Unlocks at ', ReverseMatch.clock(r.unlock_at(u)), ' (in ', ReverseMatch.clock(r.unlocks_in(u)), ')'), AttackPanel.F_TXT, Cyber.YELLOW, 1)
        elif why is not None:
            self.para(why, Cyber.body(Font.BOLD, 12), (Cyber.good() if why.startswith('EDGE') else Cyber.bad()), 1)
        m = (('No modifiers (toggle them below the cards).' if u.accepts_modifiers() else 'Carries no modifiers.') if (len(eff) == 0) else _j.cat('With ', AttackPanel.mods_text(eff), '.'))
        self.para(m, AttackPanel.F_TXT, Cyber.alpha(Cyber.CYAN, 230), 1)
        if t.has_children():
            sb = _j.StringBuilder('Releases ')
            ch = t.get_child_types()
            n = t.get_child_counts()
            for i in range(len(ch)):
                if i > 0:
                    sb.append(' + ')
                sb.append(n[i]).append(' x ').append(ch[i].display_name)
            self.para(sb.append(' when destroyed.').to_string(), AttackPanel.F_TXT, Cyber.MUTED, 1)
    @staticmethod
    def mods_text(m):
        l = _j.ArrayList()
        for x in m:
            _j_add(l, x.label)
        return ' + '.join(l)
    def build_tower_info(self, t):
        """A selected tower, read-only: the AI owns it."""
        d = t.get_def()
        self.header(t.get_type().display_name, Cyber.lerp(Ui.c(t.get_type().primary_rgb), Color.WHITE, 0.35), _j.cat('AI  T', t.get_tier(), '/', t.get_max_tier()), Cyber.CYAN)
        self.para(_j.cat(t.get_tier_label(), '  ·  ', d.subtitle), AttackPanel.F_TXT, Cyber.MUTED, 1)
        self.y += 6
        cw = (self.tw / 3)
        self.stat_cell(self.tx, self.y, 'kills', _j.Fn(lambda : Cyber.commas(t.get_kills())), Cyber.TEXT)
        self.stat_cell((self.tx + cw), self.y, 'damage', _j.Fn(lambda : Cyber.abbrev(t.get_damage_dealt())), Cyber.TEXT)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'invested', _j.Fn(lambda : Ui.money(t.get_invested_cost())), Cyber.YELLOW)
        self.y += 38
        self.stat_cell(self.tx, self.y, 'targeting', _j.Fn(lambda : t.get_targeting().label.upper()), Cyber.CYAN)
        self.stat_cell((self.tx + cw), self.y, 'range', _j.Fn(lambda : _j.s(_j.to_int(t.effective_range(self.game)))), Cyber.TEXT)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'status', _j.Fn(lambda : (_j.cat('JAMMED ', _j.to_int(float(math.ceil(t.get_surveilled_remaining()))), 's') if t.is_surveilled() else 'ONLINE')), (Cyber.bad() if t.is_surveilled() else Cyber.good()))
        self.y += 34
        if d.ability is None:
            ab = ('Hero: passive, no active ability.' if t.get_type().is_hero() else 'No ability.')
        elif t.is_ability_locked():
            ab = _j.cat('Ability ', d.ability.name, ': locked (the AI can buy it for ', Ui.money(catalog.ABILITY_UNLOCK_COST), ' at max tier).')
        else:
            ab = _j.cat('Ability ', d.ability.name, ': UNLOCKED. Jam the tower with Zero-Day to lock it.')
        self.para(ab, AttackPanel.F_TXT, (Cyber.MUTED if (t.is_ability_locked() or (d.ability is None)) else Cyber.MAGENTA), 3)
        self.y += 4
        self.para('Read-only: the defender AI controls this tower. Right-click to deselect.', Cyber.body(Font.PLAIN, 11), Cyber.DIM, 2)
    def build_enemy_info(self, e):
        self.header(e.get_type().display_name, (Cyber.RED if e.is_boss() else Cyber.TEXT), 'YOURS', Cyber.MAGENTA)
        self.y += 10
        self.enemy_bar = Cyber.Bar(self.tx, self.y, self.tw, 8, 2).colors(Cyber.hp_color(e.get_hp_fraction()), Color(255, 255, 255, 30), None)
        self.enemy_bar.set_value(e.get_hp_fraction())
        self.info.add(self.enemy_bar)
        self.y += 14
        cw = (self.tw / 3)
        self.stat_cell(self.tx, self.y, 'hp', _j.Fn(lambda : _j.cat(Cyber.commas(_j.to_long(float(math.ceil(_j.dmax(0, e.get_hp()))))), ' / ', Cyber.commas(_j.to_long(e.get_max_hp())))), Cyber.TEXT)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'integrity', _j.Fn(lambda : _j.s(e.get_type().lives)), Cyber.RED)
        self.y += 38
        self.stat_cell(self.tx, self.y, 'progress', _j.Fn(lambda : _j.cat(_j.to_int(_j.jround(((100 * e.get_distance()) / e.get_route().get_total_length()))), '%')), Cyber.CYAN)
        self.stat_cell((self.tx + cw), self.y, 'speed', _j.Fn(lambda : _j.cat(Ui.fmt((_j.jround((e.speed_multiplier() * 100)) / 100.0)), 'x')), Cyber.TEXT)
        self.stat_cell((self.tx + (2 * cw)), self.y, 'lane', _j.Fn(lambda : _j.s((e.get_route_index() + 1))), Cyber.TEXT)
        self.y += 34
        self.para(('No modifiers.' if (len(e.get_modifiers()) == 0) else _j.cat('Modifiers: ', AttackPanel.mods_text(e.get_modifiers()))), AttackPanel.F_TXT, Cyber.MUTED, 1)
        self.para(e.get_type().description, AttackPanel.F_TXT, Cyber.MUTED, 3)
    def build_feed(self):
        """The defender AI's latest actions and the match's events, newest first."""
        self.y += 6
        self.put(_j.cat('Defender AI: ', self.match.get_profile().display_name), self.tx, (self.y + 9), Cyber.body(Font.BOLD, 12), Cyber.MUTED)
        cash = self.put('', 0, (self.y + 9), AttackPanel.F_MICRO, Cyber.YELLOW)
        def _lam2():
            Cyber.set_text(cash, _j.cat('AI cash ', Ui.money(self.game.get_cash()), '   ·   towers ', len(self.game.get_tower_manager().get_player_towers())))
            cash.set_location(((self.tx + self.tw) - cash.get_width()), cash.get_y())
        _j_add(self.dyn, _j.Fn(_lam2))
        self.dyn[0]()
        self.y += 18
        f = self.match.get_feed()
        ff = Cyber.body(Font.PLAIN, 12)
        lines = 0
        i = (len(f) - 1)
        while (i >= 0) and (lines < AttackPanel.FEED_LINES):
            e = f[i]
            self.y += 17
            self.put(ReverseMatch.clock(e.time), self.tx, self.y, Cyber.mono(Font.BOLD, 10), Cyber.DIM)
            s = e.text
            l = self.put(s, (self.tx + 40), self.y, ff, Ui.c(e.rgb))
            while (l.get_width() > (self.tw - 40)) and (len(s) > 4):
                s = s[0:(len(s) - 2)]
                l.set_label(_j.cat(s, '…'))
            lines += 1
            i -= 1
        if len(f) == 0:
            self.y += 18
            self.put('The AI is setting up. Click a unit card to send it.', ff, Cyber.MUTED)
    @staticmethod
    def end_texts(g):
        """Title, subtitle and accent of the reverse-mode end screen ({title, sub, "win"|"loss"})."""
        r = g.get_reverse()
        map_ = g.get_map().get_name()
        ai = r.get_profile().display_name
        doc = r.get_doctrine().display_name
        if r.attacker_won():
            return ['BREACH', _j.cat('You broke the ', ai, ' defender AI on ', map_, ' in ', ReverseMatch.clock(r.get_elapsed()), (' in sudden-death overtime' if r.is_overtime() else ''), ' with the ', doc, ' doctrine.'), 'win']
        return ['CONTAINED', _j.cat('The ', ai, ' AI held the ', ReverseMatch.clock(ReverseMatch.DURATION), ' training run on ', map_, (', overtime included,' if r.is_overtime() else ''), ' with ', g.get_lives(), ' of ', g.get_max_lives(), ' integrity left.'), 'loss']
    @staticmethod
    def end_stats(g):
        """The four end-screen stat chips: {label, value, accent}."""
        r = g.get_reverse()
        taken = max(0, (g.get_max_lives() - g.get_lives()))
        return [['integrity taken', _j.cat(taken, ' / ', g.get_max_lives()), 'r'], ['objectives', _j.cat(r.get_objectives_met(), ' / ', ReverseMatch.ROUNDS), 'y'], ['units sent', Cyber.commas(r.get_units_bought()), ''], ['match time', ReverseMatch.clock(r.get_elapsed()), '']]
    @staticmethod
    def end_rounds(into, g, cx, y, w):
        """The end screen's round strip under the stat chips: one cell per round played (integrity taken, a bar toward the
round's objective, lit when it was met; the overtime last) and a caption with the doctrine and the AI's adaptations.
Draws from baseline y and returns the height used (END_ROUNDS_H)."""
        r = g.get_reverse()
        hist = r.get_round_history()
        n = ReverseMatch.ROUNDS + (1 if r.is_overtime() else 0)
        doc = r.get_doctrine()
        ad = len(r.get_adaptations())
        cap = Ui.label(_j.cat('Breach per round   ·   ', doc.display_name, ' doctrine   ·   the AI adapted ', ad, (' time' if ad == 1 else ' times'), '   ·   bonus compute ', Cyber.commas(_j.to_int(_j.jround(r.get_objective_bonus())))), 0, y, Cyber.body(Font.PLAIN, 13), Cyber.MUTED)
        cap.set_location(cx - cap.get_width() / 2, y)
        into.add(cap)
        gap = 6.0
        cw = (w - (n - 1) * gap) / n
        x0 = cx - w / 2
        top = y + 10
        for i in range(n):
            x = x0 + i * (cw + gap)
            played = i < len(hist)
            taken, goal, met = hist[i] if played else (0, r.round_goal(i), False)
            ot = i >= ReverseMatch.ROUNDS
            acc = Cyber.RED if ot else (Cyber.good() if met else Cyber.MAGENTA)
            into.add(Cyber.Chamfer(x, top, cw, 46, 3).fill(Cyber.alpha(acc, 26) if met else Cyber.SURFACE_2).border(Cyber.alpha(acc, 120) if (met or ot) else None))
            into.add(Ui.label('OT' if ot else _j.cat('R', i + 1), x + 8, top + 15, Cyber.mono(Font.BOLD, 10), Cyber.MUTED))
            v = Ui.label((_j.cat('-', taken) if (played and taken > 0) else ('0' if played else '-')), 0, top + 34, Cyber.mono(Font.BOLD, 16), (Cyber.TEXT if (played and taken > 0) else Cyber.DIM))
            v.set_location(x + cw - 8 - v.get_width(), top + 34)
            into.add(v)
            if not ot:
                bar = Cyber.Bar(x + 6, top + 39, cw - 12, 3, 0).colors((Cyber.good() if met else Cyber.alpha(Cyber.MAGENTA, 200)), Color(255, 255, 255, 22), None)
                bar.set_value(taken / float(max(1, goal)) if played else 0)
                into.add(bar)
        return AttackPanel.END_ROUNDS_H


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.sprites.sprite_factory import SpriteFactory  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

AttackPanel.serial_version_uid = 1
AttackPanel.X0 = Ui.PANEL_X
AttackPanel.PAD = 8.0
AttackPanel.INNER = (Ui.PANEL_W - (2 * AttackPanel.PAD))
AttackPanel.COLS = 3
AttackPanel.GAP = 5.0
AttackPanel.ROUND_Y = 137.0
AttackPanel.ROUND_H = 58.0
AttackPanel.CARD_Y = (AttackPanel.ROUND_Y + AttackPanel.ROUND_H + 6)
AttackPanel.CARD_H = 56.0
AttackPanel.CARD_W = ((AttackPanel.INNER - ((AttackPanel.COLS - 1) * AttackPanel.GAP)) / AttackPanel.COLS)
AttackPanel.MODS_Y = ((AttackPanel.CARD_Y + (7 * (AttackPanel.CARD_H + AttackPanel.GAP))) + 2)
AttackPanel.MOD_ROWS = _j.idiv((len(Modifier.values()) + 1), 2)
AttackPanel.MOD_H = 28.0
AttackPanel.MOD_ROW = (AttackPanel.MOD_H + 4)
AttackPanel.ROW_H = 30.0
AttackPanel.SEND_Y = ((AttackPanel.MODS_Y + (AttackPanel.MOD_ROWS * AttackPanel.MOD_ROW)) + 2)
AttackPanel.EXPLOIT_H = 32.0
AttackPanel.EXPLOIT_Y = (AttackPanel.SEND_Y + AttackPanel.ROW_H + 5)
AttackPanel.UPLINK_Y = (AttackPanel.EXPLOIT_Y + AttackPanel.EXPLOIT_H + 22)
AttackPanel.INFO_Y = (AttackPanel.UPLINK_Y + 17)
AttackPanel.END_ROUNDS_H = 76.0
AttackPanel.QUANTITIES = [1, 5, 10, 25]
AttackPanel.F_MICRO = Cyber.body(Font.PLAIN, 11)
AttackPanel.BG = Color(8, 9, 22)
AttackPanel.F_VAL = Cyber.mono(Font.BOLD, 14)
AttackPanel.F_TXT = Cyber.body(Font.PLAIN, 12)
AttackPanel.F_OBJ = Cyber.body(Font.PLAIN, 12)
AttackPanel.F_TAG = Cyber.mono(Font.BOLD, 9)
AttackPanel.F_PRICE = Cyber.mono(Font.BOLD, 12)
AttackPanel.FEED_LINES = 9
AttackPanel.HELP_KEYS = [['CLICK', 'send the unit on a card'], ['SPACE', 'repeat the last send'], ['X', 'cycle send quantity'], ['L', 'cycle lane (OPEN: the AI covers it least)'], ['C', 'scale compute (+5 credits/s)'], ['Q  W  E', 'Overclock / Hotfix / Zero-Day'], ['1  2  3', 'game speed'], ['P', 'pause / resume (you can still send)'], ['ESC', 'deselect, else pause menu'], ['M', 'music on / off'], ['N', 'sound on / off'], ['H', 'toggle this help']]
AttackPanel.HELP_NOTES = [['adversarial training', 'You send the enemies, an AI builds the towers. Break its integrity within 8 rounds of 1:00; each round\'s objective (breach that much integrity) pays bonus compute. AI at 25% or less at 8:00: one minute of sudden-death overtime.'], ['doctrine & compute', 'Your doctrine (Rush, Swarm or Heist, picked in the briefing) shapes the match. Income grows every second, SCALE COMPUTE adds more and leaks pay too.'], ['the ai adapts', 'It counters what you spend on most. EDGE on a card: the AI has no answer yet; COUNTERED: it just built one. Switch it up.'], ['modifiers & exploits', "Camo needs detection, Regrow heals, Fortified doubles HP. Overclock speeds your units up, Hotfix heals them, Zero-Day jams the AI's 3 priciest towers."]]
