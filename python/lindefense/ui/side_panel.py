"""Lindefense SidePanel (ported from src/lindefense/ui/SidePanel.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import Mechanic
from lindefense.tower import catalog
from lindefense.tower import shop
from lindefense.tower.behavior.support_titans import KimiBehavior
from lindefense.tower.tower_type import AttackKind
from lindefense.tower.tower_type import Faction
from lindefense.tower.tower_type import Targeting
from lindefense.tower.tower_type import TowerType
from lindefense.ui.cyber import Cyber
from lindefense.ui import intel


class SidePanel(GCompound):
    """Right-hand panel: the tower shop (faction tabs or an ALL view showing every buildable tower grouped by faction) and
the context info panel (selected tower with stat grid / upgrade path / targeting / ability / sell, shop tower preview,
enemy inspector). The info panel starts right below whichever card grid is shown, so faction view has no dead gap.
Shop cells show live affordability; a floating tooltip explains the hovered cell. The info section is rebuilt only when
the selection (or something that changes its buttons) changes; live numbers are refreshed by mutating labels.
Upgrade pips and labels are derived from TowerDef.upgrades / tierLabels, never hardcoded."""
    class Card:
        """One rendered shop cell."""
        def __init__(self, cell, button, price, name, icon):
            self.cell = None
            self.button = None
            self.price = None
            self.name = None
            self.icon = None
            self.badge = None
            self.cell = cell
            self.button = button
            self.price = price
            self.name = name
            self.icon = icon
    class ShopIcon(GCompound):
        """Tower art icon with a translucent overlay that dims it when the tower is unaffordable."""
        def __init__(self, t, size):
            self.dim = None
            GCompound.__init__(self)
            self.add(TowerIcons.create(t, 0, size), 0, 0)
            r = (size * 0.62)
            self.dim = Cyber.Ring((-r), (-r), (2 * r), (2 * r), Color(5, 9, 22, 170), None)
            self.dim.set_visible(False)
            self.add(self.dim)
        def set_dimmed(self, d):
            self.dim.set_visible(d)
    def __init__(self, screen):
        self.screen = None
        self.game = None
        self.all_button = None
        self.help_btn = None
        self.collapse_btn = None
        self.shop_collapsed = False
        self.compact_shop = False
        self.info_frame = None
        self.tip_frame = None
        self.tip_title = None
        self.tip_sub = None
        self.tip_status = None
        self.all_mode = False
        self.refresh = 0.0
        self.ability_bar = None
        self.ability_text = None
        self.enemy_bar = None
        self.upgrade_btn = None
        self.y = 0.0
        GCompound.__init__(self)
        self.tab_buttons = _j.ArrayList()
        self.cards = _j.ArrayList()
        self.info_buttons = _j.ArrayList()
        self.dyn = _j.ArrayList()
        self.card_layer = GCompound()
        self.info = GCompound()
        self.info_y = 320.0
        self.tip = GCompound()
        self.tab = Faction.PRIMARY
        self.built_key = ''
        self.shown_price_mult = 1.0
        self.x0 = (Ui.PANEL_X + 22)
        self.text_w = (Ui.PANEL_W - 44)
        self.screen = screen
        self.game = screen.get_game()
        self.add(Cyber.Chamfer(Ui.PANEL_X, (-2), (Ui.PANEL_W + 2), (Ui.H + 4), 0).fill(Color(5, 9, 22)).border(Cyber.alpha(Cyber.CYAN, 130)).line_width(2))
        self.add(Ui.rect((Ui.PANEL_X + 2), 0, 3, 90, Cyber.MAGENTA, Cyber.MAGENTA))
        self.add(Ui.label(Cyber.spaced('armory'), (Ui.PANEL_X + 18), 27, Cyber.display(Font.BOLD, 22), Cyber.TEXT))
        self.help_btn = UIButton((((Ui.PANEL_X + Ui.PANEL_W) - 8) - 92), 8, 92, 26, '? HELP  [H]', Cyber.mono(Font.BOLD, 11), _j.Fn(screen.toggle_help))
        self.help_btn.set_accent(Cyber.MAGENTA)
        self.add(self.help_btn)
        self.collapse_btn = UIButton(((self.help_btn.get_x() - 8) - 132), 8, 132, 26, 'COLLAPSE SHOP', Cyber.mono(Font.BOLD, 10), _j.Fn(self.toggle_shop_collapsed))
        self.collapse_btn.set_accent(Cyber.CYAN)
        self.add(self.collapse_btn)
        x = (Ui.PANEL_X + 8)
        tab_w = 60.0
        for f in ShopLayout.shop_factions():
            b = UIButton(x, 40, tab_w, 30, f.label.upper(), Cyber.display_compact(Font.BOLD, 12), _j.Fn(lambda f=f: self.set_tab(f)))   # bind per iteration (Java captures the loop variable)
            b.set_accent(Ui.c(f.rgb))
            _j_add(self.tab_buttons, b)
            self.add(b)
            x += (tab_w + 3)
        self.all_button = UIButton(x, 40, (((Ui.PANEL_X + Ui.PANEL_W) - 8) - x), 30, 'ALL', Cyber.display(Font.BOLD, 14), _j.Fn(self.toggle_all))
        self.all_button.set_accent(Cyber.YELLOW)
        self.add(self.all_button)
        self.add(self.card_layer)
        self.info_frame = Cyber.Chamfer((Ui.PANEL_X + 8), self.info_y, (Ui.PANEL_W - 16), ((Ui.H - self.info_y) - 8), 14).fill(Color(7, 12, 28, 235)).border(Cyber.alpha(Cyber.CYAN, 150)).glow(0.5).ticks(True)
        self.add(self.info_frame)
        self.add(self.info)
        self.tip_frame = Cyber.Chamfer(0, 0, 280, 78, 10).fill(Color(5, 9, 22, 245)).border(Cyber.CYAN).glow(0.8).scan(False)
        self.tip.add(self.tip_frame)
        self.tip_title = Ui.label('', 14, 28, Cyber.display(Font.BOLD, 20), Cyber.TEXT)
        self.tip_sub = Ui.label('', 14, 47, SidePanel.F_TXT, Cyber.MUTED)
        self.tip_status = Ui.label('', 14, 67, Cyber.mono(Font.BOLD, 11), Cyber.CYAN)
        self.tip.add(self.tip_title)
        self.tip.add(self.tip_sub)
        self.tip.add(self.tip_status)
        self.tip.set_visible(False)
        self.add(self.tip)
        self.set_tab(Faction.PRIMARY)
    def get_tab(self):
        return self.tab
    def is_all_mode(self):
        return self.all_mode
    def set_tab(self, f):
        """Shows one faction (exits ALL mode)."""
        self.tab = f
        self.all_mode = False
        self.rebuild_cards()
    def toggle_all(self):
        """Switches between the single-faction view and the all-towers view."""
        self.all_mode = (not self.all_mode)
        self.rebuild_cards()
    def is_shop_collapsed(self):
        """True while the shop's card grid is collapsed (tabs, ALL and the cards hidden; the info panel grows into the space)."""
        return self.shop_collapsed
    def toggle_shop_collapsed(self):
        """COLLAPSE SHOP / EXPAND SHOP: hides (or restores) the card grid without losing the current tab / ALL selection."""
        self.shop_collapsed = (not self.shop_collapsed)
        self.collapse_btn.set_text(('EXPAND SHOP' if self.shop_collapsed else 'COLLAPSE SHOP'))
        self.collapse_btn.set_selected(self.shop_collapsed)
        AudioManager.sfx(Sfx.UI_CLICK)
        self.rebuild_cards()
    def rebuild_cards(self):
        for i in range(len(self.tab_buttons)):
            b = self.tab_buttons[i]
            b.set_visible((not self.shop_collapsed))
            b.set_selected(((not self.all_mode) and (ShopLayout.shop_factions()[i] is self.tab)))
        self.all_button.set_visible((not self.shop_collapsed))
        self.all_button.set_selected(self.all_mode)
        self.card_layer.set_visible((not self.shop_collapsed))
        self.card_layer.remove_all()
        self.cards.clear()
        if self.shop_collapsed:
            self.info_y = ShopLayout.CARDS_Y
            self.refresh_affordability()
            self.built_key = ''
            return
        cells = self.layout_cells()
        for c in cells:
            t = c.type
            d = catalog.get(t)
            b = UIButton(c.x, c.y, c.w, c.h, '', _j.Fn(lambda t=t: self.screen.begin_placing(t)))   # bind per iteration
            b.set_accent(Cyber.lerp(Ui.c(t.primary_rgb), Cyber.CYAN, 0.35))
            self.card_layer.add(b)
            if self.all_mode:
                if c.first_of_faction:
                    self.card_layer.add(Ui.label(t.faction.label.upper(), (ShopLayout.CARDS_X + 5), ((c.y + (c.h / 2)) + 4), Cyber.mono(Font.BOLD, 9), Ui.c(t.faction.rgb)))
                    self.card_layer.add(Ui.rect(ShopLayout.CARDS_X, (c.y + 2), 2, (c.h - 4), Ui.c(t.faction.rgb), Ui.c(t.faction.rgb)))
                label = SidePanel.short_label(t)
                if c.h >= 64:
                    isz = _j.dmin((c.h - 40), 46)
                    icon = SidePanel.shop_icon(t, (c.x + ((c.w - isz) / 2)), (c.y + 6), isz)
                    nf = SidePanel.fit_font(label, Cyber.display(Font.BOLD, 17), (c.w - 10), 10)
                    name = Ui.label(label, 0, ((c.y + c.h) - 22), nf, Cyber.TEXT)
                    name.set_location((c.x + ((c.w - name.get_width()) / 2)), ((c.y + c.h) - 22))
                    price = Ui.label(Ui.money(shop.price_of(t, self.game)), 0, ((c.y + c.h) - 7), Cyber.mono(Font.BOLD, 14), Cyber.YELLOW)
                    price.set_location((c.x + ((c.w - price.get_width()) / 2)), ((c.y + c.h) - 7))
                else:
                    isz = (c.h - 14)
                    icon = SidePanel.shop_icon(t, (c.x + 6), (c.y + 7), isz)
                    tx = ((c.x + isz) + 12)
                    nf = SidePanel.fit_font(label, Cyber.display(Font.BOLD, 16), (((c.x + c.w) - 4) - tx), 9)
                    name = Ui.label(label, tx, ((c.y + (c.h / 2)) - 2), nf, Cyber.TEXT)
                    price = Ui.label(Ui.money(shop.price_of(t, self.game)), tx, ((c.y + c.h) - 8), Cyber.mono(Font.BOLD, 14), Cyber.YELLOW)
            else:
                isz = _j.dmin((c.h - 20), 76)
                icon = SidePanel.shop_icon(t, (c.x + 10), (c.y + ((c.h - isz) / 2)), isz)
                tx = ((c.x + isz) + 22)
                big = (c.h >= 100)
                ns = (22 if big else 19)
                ps = (19 if big else 16)
                block_h = ((((ns + 2) + 14) + ps) + 4)
                top = (c.y + ((c.h - block_h) / 2))
                nf = SidePanel.fit_font(t.display_name, Cyber.display(Font.BOLD, ns), (((c.x + c.w) - 6) - tx), 12)
                name = Ui.label(t.display_name, tx, (top + ns), nf, Cyber.TEXT)
                sf = SidePanel.fit_font(d.subtitle, Cyber.body(Font.PLAIN, 12), (((c.x + c.w) - 6) - tx), 9)
                self.card_layer.add(Ui.label(d.subtitle, tx, ((top + ns) + 16), sf, Cyber.MUTED))
                price = Ui.label(Ui.money(shop.price_of(t, self.game)), tx, ((top + block_h) - 2), Cyber.mono(Font.BOLD, ps), Cyber.YELLOW)
            self.card_layer.add(icon)
            self.card_layer.add(name)
            self.card_layer.add(price)
            card = SidePanel.Card(c, b, price, name, icon)
            if t.is_hero():
                badge = GCompound()
                bl = Ui.label('PLACED', 0, 0, Cyber.mono(Font.BOLD, 11), Cyber.YELLOW)
                bw = (bl.get_width() + 16)
                badge.add(Cyber.Chamfer(0, 0, bw, 18, 5).scan(False).fill(Color(20, 16, 4, 235)).border(Cyber.YELLOW))
                bl.set_location(8, 13)
                badge.add(bl)
                badge.set_location((((c.x + c.w) - bw) - 4), (c.y + 4))
                badge.set_visible(False)
                self.card_layer.add(badge)
                card.badge = badge
            _j_add(self.cards, card)
        self.info_y = (ShopLayout.bottom(cells) + 10)
        self.refresh_affordability()
        self.built_key = ''
    def layout_cells(self):
        """Cells for the current mode; the shop is larger when nothing is selected and compacts to leave room for the info panel."""
        avail = ((((Ui.H - 8) - SidePanel.BRIEF_H) - 12) - ShopLayout.CARDS_Y)
        if self.all_mode:
            h = ShopLayout.ALL_ROW_H
            if not self.compact_shop:
                h = _j.dmax(h, _j.dmin(84, (((avail - (4 * ShopLayout.ALL_GROUP_GAP)) / 7) - ShopLayout.ALL_ROW_GAP)))
            return ShopLayout.all_cells(h)
        h = ShopLayout.CARD_H
        if not self.compact_shop:
            n = 0
            for t in TowerType.shop_towers():
                if t.faction is self.tab:
                    n += 1
            rows = max(1, _j.idiv((n + 1), 2))
            h = _j.dmax(h, _j.dmin(140, (((avail - ShopLayout.CARD_GAP) / rows) - ShopLayout.CARD_GAP)))
        return ShopLayout.faction_cells(self.tab, h)
    @staticmethod
    def short_label(t):
        """Compact label for the dense ALL grid (full name is shown in the tooltip and info panel)."""
        return t.display_name
    @staticmethod
    def shop_icon(t, x, y, size):
        """Shop icon: the tower's tier-0 art in a size x size box with top-left (x, y)."""
        icon = SidePanel.ShopIcon(t, size)
        icon.set_location((x + (size / 2)), (y + (size / 2)))
        return icon
    @staticmethod
    def fit_font(text, f, max_width, min_size):
        """Shrinks a font (never truncates) until the text fits maxWidth, down to minSize."""
        probe = Cyber.Text(text)
        cur = f
        probe.set_font(cur)
        while (probe.get_width() > max_width) and (cur.get_size() > min_size):
            cur = cur.derive_font(float((cur.get_size() - 1)))
            probe.set_font(cur)
        return cur
    def get_buttons(self):
        all_ = _j.ArrayList(self.tab_buttons)
        _j_add(all_, self.all_button)
        _j_add(all_, self.help_btn)
        for c in self.cards:
            _j_add(all_, c.button)
        all_.extend(self.info_buttons)
        _j_add(all_, self.collapse_btn)
        return all_
    def request_rebuild(self):
        self.built_key = ''
    def refresh_affordability(self):
        cash = self.game.get_cash()
        for c in self.cards:
            placed = (c.cell.type.is_hero() and self.game.get_tower_manager().hero_placed(c.cell.type))
            ok = (ShopLayout.affordable(self.game, c.cell.type) and (not placed))
            if (c.badge is not None) and (c.badge.is_visible() != placed):
                c.badge.set_visible(placed)
            c.button.set_selected((self.screen.get_placing() is c.cell.type))
            c.button.set_enabled(ok)
            Cyber.set_color(c.price, (Cyber.YELLOW if ok else (Cyber.DIM if placed else Cyber.cant_afford())))
            Cyber.set_color(c.name, (Cyber.TEXT if ok else Color(0x6f819b)))
            if isinstance(c.icon, SidePanel.ShopIcon):
                c.icon.set_dimmed((not ok))
    def update(self, dt):
        self.refresh -= dt
        pm = self.game.get_variance().tower_cost_multiplier()
        if pm != self.shown_price_mult:
            self.shown_price_mult = pm
            self.rebuild_cards()
        self.refresh_affordability()
        want_compact = (((self.screen.get_selected_tower() is not None) or (self.screen.get_placing() is not None)) or (self.screen.get_selected_enemy() is not None))
        if want_compact != self.compact_shop:
            self.compact_shop = want_compact
            self.rebuild_cards()
        self.update_tooltip()
        key = self.selection_key()
        rebuilt = False
        if not (key == self.built_key):
            self.built_key = key
            self.rebuild_info()
            rebuilt = True
        if rebuilt:
            self.refresh = 0.25
            self.screen.refresh_hover()
        elif self.refresh <= 0:
            self.refresh = 0.25
            for r in self.dyn:
                r()
        t = self.screen.get_selected_tower()
        if ((self.ability_bar is not None) and (t is not None)) and (t.get_ability() is not None):
            self.ability_bar.set_value((1 - t.get_ability_cooldown_fraction()))
            ready = t.is_ability_ready()
            self.ability_bar.set_fill((Cyber.MAGENTA if ready else Cyber.lerp(Cyber.DIM, Cyber.MAGENTA, (1 - t.get_ability_cooldown_fraction()))))
            s = ('READY  [A]' if ready else ('OFFLINE' if t.is_surveilled() else _j.format('%.0fs / %ds', float(math.ceil(t.get_ability_cooldown_remaining())), _j.to_int(t.get_ability().cooldown))))
            Cyber.set_text(self.ability_text, s)
            self.ability_text.set_location((((Ui.PANEL_X + Ui.PANEL_W) - 22) - self.ability_text.get_width()), self.ability_text.get_y())
            Cyber.set_color(self.ability_text, (Cyber.MAGENTA if ready else Cyber.MUTED))
        if (self.enemy_bar is not None) and (self.screen.get_selected_enemy() is not None):
            self.enemy_bar.set_value(self.screen.get_selected_enemy().get_hp_fraction())
            self.enemy_bar.set_fill(Cyber.hp_color(self.screen.get_selected_enemy().get_hp_fraction()))
    def update_tooltip(self):
        m = self.screen.get_mouse_logical()
        hover = None
        for c in self.cards:
            if c.button.hit(m[0], m[1]):
                hover = c
                break
        if hover is None:
            self.tip.set_visible(False)
            return
        d = catalog.get(hover.cell.type)
        need = ShopLayout.shortfall(self.game, hover.cell.type)
        self.tip_title.set_label(_j.cat(hover.cell.type.display_name, '   ', Ui.money(shop.price_of(hover.cell.type, self.game))))
        Cyber.set_text(self.tip_sub, _j.cat(d.subtitle, '  //  ', hover.cell.type.faction.label))
        block = (shop.unavailable_reason(self.game, hover.cell.type) if (hover.cell.type.is_hero() and self.game.get_tower_manager().hero_placed(hover.cell.type)) else None)
        n = (self.cards.index(hover) + 1)
        Cyber.set_text(self.tip_status, (block.upper() if (block is not None) else (_j.cat('NEED ', Ui.money(need), ' MORE') if (need > 0) else (_j.cat('CLICK OR SHIFT+', n, ', THEN PLACE ON THE MAP') if (n <= 9) else 'CLICK, THEN PLACE ON THE MAP'))))
        accent = (Cyber.YELLOW if (block is not None) else (Cyber.cant_afford() if (need > 0) else Cyber.CYAN))
        Cyber.set_color(self.tip_status, accent)
        Cyber.set_color(self.tip_title, (Cyber.lerp(Cyber.TEXT, Cyber.cant_afford(), 0.15) if ((need > 0) and (block is None)) else Cyber.TEXT))
        w = _j.dmax(240, (_j.dmax(_j.dmax(self.tip_title.get_width(), self.tip_sub.get_width()), self.tip_status.get_width()) + 28))
        self.tip_frame.size(w, 78).border(accent)
        y = _j.dmax((Ui.WORLD_Y + 6), _j.dmin(((hover.cell.y + (hover.cell.h / 2)) - 39), (Ui.BOTTOM_Y - 90)))
        self.tip.set_location(((Ui.PANEL_X - w) - 8), y)
        self.tip.set_visible(True)
    def selection_key(self):
        t = self.screen.get_selected_tower()
        base = _j.cat('@', _j.to_int(self.info_y), self.compact_shop, ':')
        if t is not None:
            return _j.cat(base, 'T', t.get_id(), ':', t.get_tier(), ':', (self.game.get_cash() >= shop.upgrade_cost(t, self.game)), ':', t.get_targeting(), ':', t.is_ability_ready(), ':', t.is_surveilled(), ':', t.is_ability_locked(), ':', (self.game.get_cash() >= shop.ability_unlock_cost(self.game)), ':', shop.upgrade_cost(t, self.game), ':', shop.sell_value(t, self.game), ':', shop.ability_unlock_cost(self.game), ':', IntrusionText.state_key(t))
        if self.screen.get_placing() is not None:
            return _j.cat(base, 'P', self.screen.get_placing())
        if self.screen.get_selected_enemy() is not None:
            return _j.cat(base, 'E', self.screen.get_selected_enemy().get_id())
        return _j.cat(base, 'none')
    def put(self, s, x, baseline, f, c):
        l = Ui.label(s, x, baseline, f, c)
        self.info.add(l)
        return l
    def para(self, s, f, c, max_lines):
        lines = Ui.wrap(s, f, self.text_w)
        n = 0
        for l in lines:
            if (max_lines > 0) and (n >= max_lines):
                break
            self.y += (f.get_size() + 4)
            self.put(l, self.x0, self.y, f, c)
            n += 1
    def section(self, title):
        self.y += 12
        l = self.put(Cyber.spaced(_j.cat('// ', title)), self.x0, (self.y + 9), SidePanel.F_MICRO, Cyber.alpha(Cyber.CYAN, 230))
        ln = GLine(((self.x0 + l.get_width()) + 8), (self.y + 5.5), (self.x0 + self.text_w), (self.y + 5.5))
        ln.set_color(Cyber.alpha(Cyber.CYAN, 70))
        self.info.add(ln)
        self.y += 13
    def button(self, bx, by, w, h, text, r):
        b = UIButton(bx, by, w, h, text, Cyber.display(Font.BOLD, 15), r)
        self.info.add(b)
        _j_add(self.info_buttons, b)
        return b
    def stat_cell(self, cx, cy, label, val, vc):
        """Micro-label over a value; the value is refreshed from the supplier by #update(double)."""
        self.put(Cyber.spaced(label), cx, (cy + 9), SidePanel.F_MICRO, Cyber.alpha(Cyber.CYAN, 190))
        v = self.put(val(), cx, (cy + 27), SidePanel.F_VAL, vc)
        _j_add(self.dyn, _j.Fn(lambda : Cyber.set_text(v, val())))
    def rebuild_info(self):
        self.info.remove_all()
        self.info_buttons.clear()
        self.dyn.clear()
        self.ability_bar = None
        self.ability_text = None
        self.enemy_bar = None
        self.upgrade_btn = None
        brief = (not self.compact_shop)
        top = self.info_y
        self.info_frame.set_location((Ui.PANEL_X + 8), top)
        self.info_frame.size((Ui.PANEL_W - 16), (SidePanel.BRIEF_H if brief else ((Ui.H - 8) - top)))
        self.y = (top + 6)
        t = self.screen.get_selected_tower()
        if (t is not None) and t.is_alive():
            self.build_tower_info(t)
        elif self.screen.get_placing() is not None:
            self.build_shop_info(self.screen.get_placing())
        else:
            e = self.screen.get_selected_enemy()
            if e is not None:
                self.build_enemy_info(e)
            else:
                self.build_help()
    def build_help(self):
        """Compact 3-line briefing strip anchored at the bottom of the panel (full controls live in the Help overlay)."""
        self.put(Cyber.spaced('sector'), self.x0, (self.y + 16), SidePanel.F_MICRO, Cyber.alpha(Cyber.CYAN, 230))
        nm = self.put(self.game.get_map().get_name().upper(), (self.x0 + 62), (self.y + 18), Cyber.display(Font.BOLD, 18), Cyber.YELLOW)
        hint = self.put('[H] HELP', 0, (self.y + 16), SidePanel.F_MICRO, Cyber.DIM)
        hint.set_location(((self.x0 + self.text_w) - hint.get_width()), (self.y + 16))
        room = ((hint.get_x() - 8) - (self.x0 + 62))
        sz = 18
        while (nm.get_width() > room) and (sz > 8):
            nm.set_font(Cyber.display_compact(Font.BOLD, sz))
            sz -= 2
        self.y += 22
        lines = Ui.wrap(self.game.get_map().get_mechanic_summary(), SidePanel.F_TXT, self.text_w)
        for i in range(min(2, len(lines))):
            self.y += 16
            l = lines[i]
            if (i == 1) and (len(lines) > 2):
                l = SidePanel.fit_text(_j.cat(l, ' …'), SidePanel.F_TXT, self.text_w)
            self.put(l, self.x0, self.y, SidePanel.F_TXT, Cyber.MUTED)
        if nm.get_width() < 0:
            self.y += 0
    @staticmethod
    def fit_text(s, f, w):
        p = Cyber.Text(s)
        p.set_font(f)
        cur = s
        while (p.get_width() > w) and (len(cur) > 2):
            cur = _j.cat(cur[0:(len(cur) - 2)], '…')
            p.set_label(cur)
        return cur
    @staticmethod
    def effects_text(s, include_kind):
        """Wrapped, comma-joined list of a stat block's notable effects."""
        h = s.hit
        fx = _j.ArrayList()
        if include_kind and (s.kind is not AttackKind.NONE):
            _j_add(fx, ('pulse (all in range)' if (s.kind is AttackKind.PULSE) else (_j.cat('chain x', (s.chain_hops + 1)) if (s.kind is AttackKind.CHAIN) else ('beam' if (s.kind is AttackKind.INSTANT) else (_j.cat('splash ', _j.to_int(s.splash_radius), 'px') if (s.splash_radius > 0) else 'projectile')))))
            _j_add(fx, h.type.label.lower())
        if s.targets > 1:
            _j_add(fx, _j.cat(s.targets, ' targets'))
        if s.projectiles_per_shot > 1:
            _j_add(fx, _j.cat(s.projectiles_per_shot, ' shots'))
        if s.bounces > 0:
            _j_add(fx, _j.cat(s.bounces, ' bounces'))
        if h.slow_fraction > 0:
            _j_add(fx, _j.cat('slow ', _j.to_int((h.slow_fraction * 100)), '%'))
        if h.stun_duration > 0:
            _j_add(fx, _j.cat('stun ', Ui.fmt(h.stun_duration), 's'))
        if h.knockback > 0:
            _j_add(fx, _j.cat('knockback ', _j.to_int(h.knockback)))
        if h.armor_break > 0:
            _j_add(fx, _j.cat('armour break ', _j.to_int((h.armor_break * 100)), '%'))
        if h.armor_pierce > 0:
            _j_add(fx, _j.cat('armour pierce ', _j.to_int((h.armor_pierce * 100)), '%'))
        if h.ignores_resistance:
            _j_add(fx, 'ignores immunities')
        if h.mark_bonus > 0:
            _j_add(fx, _j.cat('mark +', _j.to_int((h.mark_bonus * 100)), '%'))
        if h.disrupt_duration > 0:
            _j_add(fx, _j.cat('disrupt ', Ui.fmt(h.disrupt_duration), 's'))
        if h.bonus_vs_boss > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_boss * 100)), '% vs bosses'))
        if h.bonus_vs_fortified > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_fortified * 100)), '% vs Fortified'))
        if h.bonus_vs_non_fortified > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_non_fortified * 100)), '% vs non-Fortified'))
        if h.bonus_vs_complex > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_complex * 100)), '% vs complex'))
        if h.bonus_vs_fast > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_fast * 100)), '% vs fast'))
        if h.bonus_vs_splitters > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.bonus_vs_splitters * 100)), '% vs splitters'))
        if h.strips_fortified:
            _j_add(fx, 'strips Fortified')
        if h.pct_max_hp > 0:
            _j_add(fx, _j.cat('+', _j.to_int((h.pct_max_hp * 100)), '% max HP'))
        if s.stack_cap > 0:
            _j_add(fx, _j.cat('stacks to +', _j.to_int((s.stack_cap * s.stack_step))))
        return '  •  '.join(fx)
    @staticmethod
    def support_text(s, sees):
        aura = _j.ArrayList()
        if sees:
            _j_add(aura, 'sees camo')
        if s.aura_detection:
            _j_add(aura, 'shares detection')
        if s.aura_rate > 0:
            _j_add(aura, _j.cat('aura +', _j.to_int((s.aura_rate * 100)), '% speed'))
        if s.aura_damage > 0:
            _j_add(aura, _j.cat('aura +', Ui.fmt(s.aura_damage), ' damage'))
        if s.aura_range_bonus > 0:
            _j_add(aura, _j.cat('aura +', _j.to_int((s.aura_range_bonus * 100)), '% range'))
        if s.aura_surveillance_immunity:
            _j_add(aura, 'blocks Surveillance')
        if s.aura_enemy_slow > 0:
            _j_add(aura, _j.cat('wind wall slow ', _j.to_int((s.aura_enemy_slow * 100)), '%'))
        if s.income_per_wave > 0:
            _j_add(aura, _j.cat('+$', _j.to_int(s.income_per_wave), ' per wave'))
        if s.summon_count > 0:
            _j_add(aura, _j.cat('summons ', s.summon_count, ' sprite(s) / ', _j.to_int(s.summon_interval), 's'))
        return '  •  '.join(aura)
    @staticmethod
    def mode_text(s):
        return 'PULSE' if (s.kind is AttackKind.PULSE) else (_j.cat('x', (s.chain_hops + 1)) if (s.kind is AttackKind.CHAIN) else _j.s(s.pierce))
    @staticmethod
    def mode_label(s):
        return 'MODE' if (s.kind is AttackKind.PULSE) else ('CHAIN' if (s.kind is AttackKind.CHAIN) else 'PIERCE')
    def header(self, name, name_color, badge, badge_color):
        self.y += 28
        n = self.put(name, self.x0, self.y, SidePanel.F_NAME, name_color)
        if badge is not None:
            b = Ui.label(badge, 0, 0, Cyber.mono(Font.BOLD, 11), badge_color)
            bw = (b.get_width() + 18)
            bx = ((self.x0 + self.text_w) - bw)
            if bx < ((self.x0 + n.get_width()) + 8):
                bx = ((self.x0 + n.get_width()) + 8)
            self.info.add(Cyber.Chamfer(bx, (self.y - 17), bw, 20, 5).scan(False).fill(Cyber.alpha(badge_color, 40)).border(badge_color))
            b.set_location((bx + 9), (self.y - 2.5))
            self.info.add(b)
    def build_shop_info(self, type_):
        d = catalog.get(type_)
        tc = Cyber.lerp(Ui.c(type_.primary_rgb), Color.WHITE, 0.3)
        self.header(type_.display_name, tc, (_j.cat('DEPLOY  ', Ui.money(shop.price_of(type_, self.game))) if type_.is_hero() else Ui.money(shop.price_of(type_, self.game))), Cyber.YELLOW)
        self.y += 4
        self.put(_j.cat(d.subtitle, '  //  ', type_.faction.label.upper()), self.x0, (self.y + 12), SidePanel.F_TXT, Ui.c(type_.faction.rgb))
        self.y += 14
        self.para(d.description, SidePanel.F_TXT, Cyber.TEXT, 0)
        self.section('stats')
        s = d.base_stats
        if s.kind is not AttackKind.NONE:
            yy = self.y
            self.stat_cell(self.x0, yy, 'damage', _j.Fn(lambda : Ui.fmt(s.hit.damage)), Cyber.TEXT)
            self.stat_cell((self.x0 + 180), yy, 'interval', _j.Fn(lambda : _j.cat(Ui.fmt(s.interval()), 's')), Cyber.TEXT)
            self.stat_cell(self.x0, (yy + 34), 'range', _j.Fn(lambda : HeroStatText.range(type_, s.range)), Cyber.TEXT)
            self.stat_cell((self.x0 + 180), (yy + 34), SidePanel.mode_label(s), _j.Fn(lambda : SidePanel.mode_text(s)), Cyber.TEXT)
            self.y += 68
            fx = SidePanel.effects_text(s, True)
            if not (len(fx) == 0):
                self.para(fx, SidePanel.F_TXT_S, Cyber.MUTED, 3)
        else:
            self.y += 4
            self.put('Support tower - no direct attack', self.x0, (self.y + 12), SidePanel.F_TXT, Cyber.TEXT)
            self.y += 14
        sup = SidePanel.support_text(s, s.sees_camo)
        if not (len(sup) == 0):
            self.para(sup, SidePanel.F_TXT_S, Cyber.CYAN, 3)
        inj = IntrusionText.type_line(type_)
        if inj is not None:
            self.para(inj, SidePanel.F_TXT_S, Cyber.GREEN, 3)
        if len(d.upgrades) > 0:
            self.section('upgrade path')
        for i in range(len(d.upgrades)):
            u = d.upgrades[i]
            self.y += 15
            self.put(_j.cat((i + 1), '  ', u.name), self.x0, self.y, Cyber.display(Font.BOLD, 14), Cyber.TEXT)
            pr = self.put(Ui.money(shop.upgrade_price(self.game, u)), 0, self.y, Cyber.mono(Font.BOLD, 12), Cyber.YELLOW)
            pr.set_location(((self.x0 + self.text_w) - pr.get_width()), self.y)
        if d.ability is not None:
            locked = catalog.ability_needs_unlock(type_)
            self.section(('ability  //  unlock at max tier' if locked else 'ability'))
            self.y += 16
            self.put(d.ability.name, self.x0, self.y, Cyber.display(Font.BOLD, 15), Cyber.MAGENTA)
            cd = (self.put(Ui.money(shop.ability_unlock_cost(self.game)), 0, self.y, Cyber.mono(Font.BOLD, 12), Cyber.YELLOW) if locked else self.put(_j.cat(_j.to_int(d.ability.cooldown), 's cooldown'), 0, self.y, Cyber.mono(Font.BOLD, 11), Cyber.MUTED))
            cd.set_location(((self.x0 + self.text_w) - cd.get_width()), self.y)
            self.para(_j.cat(d.ability.description, (_j.cat(' ', _j.to_int(d.ability.cooldown), 's cooldown.') if locked else '')), SidePanel.F_TXT_S, Cyber.MUTED, 3)
        self.y += 12
        self.para(('Click a free spot to deploy (once per match). Esc cancels.' if type_.is_hero() else 'Click a free spot on the map. Right-click or Esc to cancel.'), SidePanel.F_TXT_S, Cyber.CYAN, 1)
        self.button(self.x0, _j.dmin((self.y + 10), (Ui.H - 56)), 130, 34, 'CANCEL', _j.Fn(lambda : self.screen.begin_placing(None))).set_accent(Cyber.RED)
    def build_tower_info(self, t):
        d = t.get_def()
        ty = t.get_type()
        tc = Cyber.lerp(Ui.c(ty.primary_rgb), Color.WHITE, 0.3)
        maxed = (not t.can_upgrade())
        hero = ty.is_hero()
        badge = ('HERO' if hero else ('MAX' if maxed else _j.cat('TIER ', t.get_tier(), '/', t.get_max_tier())))
        self.header(ty.display_name, tc, badge, (Cyber.YELLOW if maxed else Cyber.CYAN))
        self.y += 4
        sub = self.put(_j.cat(d.subtitle, '  //  '), self.x0, (self.y + 12), SidePanel.F_TXT, Cyber.MUTED)
        self.put(t.get_tier_label(), (self.x0 + sub.get_width()), (self.y + 12), Cyber.body(Font.BOLD, 12), Cyber.CYAN)
        self.y += 14
        self.section('stats')
        base = t.get_stats()
        yy = self.y
        if not base.is_support_only():
            self.stat_cell(self.x0, yy, 'damage', _j.Fn(lambda : Ui.fmt((t.get_stats().hit.damage * t.damage_multiplier(self.game)))), Cyber.TEXT)
            self.stat_cell((self.x0 + 180), yy, 'interval', _j.Fn(lambda : _j.cat(Ui.fmt((1.0 / _j.dmax(0.01, t.effective_rate(self.game)))), 's')), Cyber.TEXT)
            self.stat_cell(self.x0, (yy + 34), 'range', _j.Fn(lambda : HeroStatText.range(t.get_type(), t.effective_range(self.game))), Cyber.TEXT)
            self.stat_cell((self.x0 + 180), (yy + 34), SidePanel.mode_label(base), _j.Fn(lambda : SidePanel.tower_mode_text(t)), Cyber.TEXT)
            self.stat_cell(self.x0, (yy + 68), 'kills', _j.Fn(lambda : Cyber.commas(t.get_kills())), Cyber.GREEN)
            self.stat_cell((self.x0 + 92), (yy + 68), 'dmg dealt', _j.Fn(lambda : intel.compact(t.get_damage_dealt())), Cyber.GREEN)
            if t.get_ability() is not None:
                self.stat_cell((self.x0 + 180), (yy + 68), 'ability', _j.Fn(lambda : ('READY' if t.is_ability_ready() else _j.cat(_j.to_int(float(math.ceil(t.get_ability_cooldown_remaining()))), 's'))), Cyber.MAGENTA)
            else:
                self.stat_cell((self.x0 + 180), (yy + 68), 'invested', _j.Fn(lambda : Ui.money(t.get_invested_cost())), Cyber.YELLOW)
            self.y += 102
        else:
            self.stat_cell(self.x0, yy, 'kills', _j.Fn(lambda : Cyber.commas(t.get_kills())), Cyber.GREEN)
            self.stat_cell((self.x0 + 92), yy, 'dmg dealt', _j.Fn(lambda : intel.compact(t.get_damage_dealt())), Cyber.GREEN)
            self.stat_cell((self.x0 + 180), yy, 'invested', _j.Fn(lambda : Ui.money(t.get_invested_cost())), Cyber.YELLOW)
            self.y += 34
        fx = SidePanel.effects_text(base, True)
        if (not (len(fx) == 0)) and (not base.is_support_only()):
            self.para(fx, SidePanel.F_TXT_S, Cyber.MUTED, 2)
        sup = SidePanel.support_text(base, t.can_see_camo())
        if not (len(sup) == 0):
            self.para(sup, SidePanel.F_TXT_S, Cyber.CYAN, 2)
        if (ty is TowerType.KIMI) and base.has('memoryPer'):
            self.y += 6
            my = self.y
            self.stat_cell(self.x0, my, 'memory', _j.Fn(lambda : _j.cat('+', KimiBehavior.memory_stacks(t), ' dmg  (', KimiBehavior.memory_stacks(t), ' / ', _j.to_int(t.get_stats().p('memoryCap')), ')')), Cyber.MAGENTA)
            self.stat_cell((self.x0 + 180), my, 'next stack', _j.Fn(lambda : ('MAX' if (KimiBehavior.memory_stacks(t) >= _j.to_int(t.get_stats().p('memoryCap'))) else _j.cat(_j.imod(t.get_kills(), _j.to_int(t.get_stats().p('memoryPer'))), ' / ', _j.to_int(t.get_stats().p('memoryPer')), ' pops'))), Cyber.TEXT)
            self.y += 34
        if (t.get_aura_rate_bonus() > 0) or (t.get_aura_damage_bonus() > 0):
            self.para(_j.cat('BUFFED ', (_j.cat('+', _j.to_int(_j.jround((t.get_aura_rate_bonus() * 100))), '% speed') if (t.get_aura_rate_bonus() > 0) else ''), (', ' if ((t.get_aura_rate_bonus() > 0) and (t.get_aura_damage_bonus() > 0)) else ''), (_j.cat('+', Ui.fmt(t.get_aura_damage_bonus()), ' damage') if (t.get_aura_damage_bonus() > 0) else '')), SidePanel.F_TXT_S, Cyber.good(), 1)
        if t.is_surveilled():
            self.y += 4
            self.put('SURVEILLED: -50% speed, -30% range', self.x0, (self.y + 12), Cyber.mono(Font.BOLD, 11), Cyber.bad())
            self.y += 12
        inj = IntrusionText.tower_line(t)
        if inj is not None:
            self.para(inj, SidePanel.F_TXT_S, (Cyber.bad() if IntrusionText.is_warning(t) else Cyber.good()), 2)
        extra = HeroStatText.live_line(self.game, t)
        if extra is not None:
            self.para(extra, SidePanel.F_TXT_S, Cyber.YELLOW, 2)
        n = len(d.upgrades)
        if n > 0:
            self.section('upgrade path')
        gap = 6.0
        pip_w = ((self.text_w - (gap * (n - 1))) / max(1, n))
        for i in range(n):
            owned = (i < t.get_tier())
            next_ = (i == t.get_tier())
            pc = (Cyber.CYAN if owned else (Cyber.YELLOW if next_ else Cyber.DIM))
            self.info.add(Cyber.Chamfer((self.x0 + (i * (pip_w + gap))), self.y, pip_w, 9, 3).scan(False).fill((Cyber.alpha(Cyber.CYAN, 200) if owned else (Cyber.alpha(Cyber.YELLOW, 45) if next_ else Color(10, 18, 38, 220)))).border((Cyber.CYAN if owned else (Cyber.YELLOW if next_ else Cyber.alpha(Cyber.DIM, 160)))).glow((0.6 if owned else 0)).line_width(1.2))
            label = d.tier_labels[min((i + 1), (len(d.tier_labels) - 1))]
            lf = SidePanel.fit_font(label, Cyber.body(Font.PLAIN, 11), pip_w, 8)
            self.put(label, (self.x0 + (i * (pip_w + gap))), (self.y + 23), lf, (Cyber.MUTED if owned else (Cyber.YELLOW if next_ else Cyber.DIM)))
        self.y += 30
        u = t.next_upgrade()
        if u is not None:
            can = (self.game.get_cash() >= shop.upgrade_price(self.game, u))
            ub = self.button(self.x0, self.y, self.text_w, 40, '', _j.Fn(lambda : self.screen.upgrade_selected()))
            ub.set_enabled(can)
            ub.set_accent(Cyber.CYAN)
            self.upgrade_btn = ub
            self.put(Cyber.spaced('upgrade [u]'), (self.x0 + 12), (self.y + 14), SidePanel.F_MICRO, (Cyber.alpha(Cyber.CYAN, 230) if can else Cyber.DIM))
            self.put(u.name, (self.x0 + 12), (self.y + 32), Cyber.display(Font.BOLD, 17), (Cyber.TEXT if can else Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.4)))
            pr = self.put(Ui.money(shop.upgrade_price(self.game, u)), 0, (self.y + 27), Cyber.mono(Font.BOLD, 16), (Cyber.YELLOW if can else Cyber.cant_afford()))
            pr.set_location((((self.x0 + self.text_w) - 12) - pr.get_width()), (self.y + 27))
            self.y += 40
            self.upgrade_deltas(t)
            locked = (t.get_ability_def() if t.is_ability_locked() else None)
            self.para_fit(u.description, SidePanel.F_TXT_S, Cyber.MUTED, max(1, min(3, self.room_lines(t, (locked is not None)))))
            if locked is not None:
                self.para(_j.cat('Max tier unlocks ', locked.name, ' (', Ui.money(shop.ability_unlock_cost(self.game)), ').'), SidePanel.F_TXT_S, Cyber.alpha(Cyber.MAGENTA, 220), 1)
        elif (not hero) and t.is_ability_locked():
            a = t.get_ability_def()
            price = shop.ability_unlock_cost(self.game)
            can = (self.game.has_admin_money() or (self.game.get_cash() >= price))
            ub = self.button(self.x0, self.y, self.text_w, 40, '', _j.Fn(lambda : self.screen.unlock_ability_selected()))
            ub.set_enabled(can)
            ub.set_accent(Cyber.MAGENTA)
            self.put(Cyber.spaced('unlock ability [u]'), (self.x0 + 12), (self.y + 14), SidePanel.F_MICRO, (Cyber.alpha(Cyber.MAGENTA, 235) if can else Cyber.DIM))
            nf = SidePanel.fit_font(a.name, Cyber.display(Font.BOLD, 17), (self.text_w - 120), 12)
            self.put(a.name, (self.x0 + 12), (self.y + 32), nf, (Cyber.TEXT if can else Cyber.lerp(Cyber.MUTED, Cyber.TEXT, 0.4)))
            pr = self.put(Ui.money(price), 0, (self.y + 27), Cyber.mono(Font.BOLD, 16), (Cyber.YELLOW if can else Cyber.cant_afford()))
            pr.set_location((((self.x0 + self.text_w) - 12) - pr.get_width()), (self.y + 27))
            self.y += 40
            self.para(_j.cat(a.description, ' ', _j.to_int(a.cooldown), 's cooldown.'), SidePanel.F_TXT_S, Cyber.MUTED, 3)
        elif not hero:
            self.y += 4
            self.put(_j.cat('MAX TIER  //  ', t.get_tier_label()), self.x0, (self.y + 14), Cyber.display(Font.BOLD, 16), Cyber.YELLOW)
            self.y += 16
        if not base.is_support_only():
            self.y += 12
            self.put(Cyber.spaced('target [t]'), self.x0, (self.y + 20), SidePanel.F_MICRO, Cyber.alpha(Cyber.CYAN, 230))
            self.button((self.x0 + 86), self.y, 34, 28, '<', _j.Fn(lambda : self.screen.cycle_targeting((-1)))).set_accent(Cyber.CYAN)
            tl = ('DENSEST CLUSTER' if (t.get_targeting() is Targeting.DENSEST_CLUSTER) else t.get_targeting().label.upper())
            cur = self.button((self.x0 + 124), self.y, 130, 28, tl, None)
            cur.set_selected(True)
            self.button((self.x0 + 258), self.y, 34, 28, '>', _j.Fn(lambda : self.screen.cycle_targeting(1))).set_accent(Cyber.CYAN)
            self.y += 28
        a = t.get_ability()
        if a is not None:
            self.y += 12
            ready = t.is_ability_ready()
            ab = self.button(self.x0, self.y, self.text_w, 36, a.name.upper(), _j.Fn(lambda : self.screen.ability_selected()))
            ab.set_accent(Cyber.MAGENTA)
            ab.set_enabled(ready)
            self.ability_text = self.put('', ((self.x0 + self.text_w) - 12), (self.y + 22), Cyber.mono(Font.BOLD, 11), Cyber.MAGENTA)
            self.ability_bar = Cyber.Bar((self.x0 + 6), ((self.y + 36) - 7), (self.text_w - 12), 3, 0).colors(Cyber.MAGENTA, Color(255, 255, 255, 28), None)
            self.info.add(self.ability_bar)
            self.y += 36
            self.para(a.description, SidePanel.F_TXT_S, Cyber.MUTED, 3)
        self.y += 12
        sell = self.button(self.x0, self.y, 210, 34, _j.cat(('DISMISS  +' if hero else 'SELL  +'), Ui.money(shop.sell_value(t, self.game))), _j.Fn(lambda : self.screen.sell_selected()))
        sell.set_accent(Cyber.RED)
        if self.game.is_selling_locked():   # No Selling challenge: the button says why it is off
            sell.set_text('NO SELLING RULE')
            sell.set_enabled(False)
        desel = self.button((self.x0 + 218), self.y, (self.text_w - 218), 34, 'DESELECT', _j.Fn(lambda : self.screen.select_tower(None)))
        desel.set_accent(Cyber.MUTED)
        if maxed:
            self.y += 0
    @staticmethod
    def tower_mode_text(t):
        """mode_text for a placed tower: its effective pierce (pierce buffs included), what its attacks really use."""
        s = t.get_stats()
        return _j.s(t.effective_pierce()) if (SidePanel.mode_label(s) == 'PIERCE') else SidePanel.mode_text(s)
    def upgrade_deltas(self, t):
        """What the next upgrade changes, in the panel's own numbers (DMG 40 -> 55, gained effects), flowed into lines
under the upgrade button. Refreshed with the live stats: a change in the tower's multipliers rebuilds the panel."""
        rows, gained = intel.upgrade_deltas(self.game, t)
        sig = _j.cat(t.get_id(), ':', t.get_tier(), ':', ' '.join(r.text() for r in rows))
        _j_add(self.dyn, _j.Fn(lambda : (self.request_rebuild() if (_j.cat(t.get_id(), ':', t.get_tier(), ':', ' '.join(r.text() for r in intel.upgrade_deltas(self.game, t)[0])) != sig) else None)))
        if len(rows) == 0 and len(gained) == 0:
            return
        vf = Cyber.mono(Font.BOLD, 12)
        x = self.x0
        base = (self.y + 17)
        for r in rows:
            parts = [(Cyber.spaced(r.label), SidePanel.F_MICRO, Cyber.alpha(Cyber.CYAN, 200), 5), (r.now, vf, Cyber.MUTED, 4), ('→', vf, Cyber.DIM, 4), (r.next, vf, (Cyber.YELLOW if (r.better is None) else (Cyber.good() if r.better else Cyber.bad())), 0)]
            labels = [Ui.label(p[0], 0, 0, p[1], p[2]) for p in parts]
            w = sum((l.get_width() + p[3]) for l, p in zip(labels, parts))
            if (x > self.x0) and ((x + w) > (self.x0 + self.text_w)):
                x = self.x0
                base += 17
            for l, p in zip(labels, parts):
                l.set_location(x, (base - (1 if (p[1] is SidePanel.F_MICRO) else 0)))
                self.info.add(l)
                x += (l.get_width() + p[3])
            x += 16
        if len(rows) > 0:
            self.y = (base + 2)
        if len(gained) > 0:
            self.y += 15
            self.put(SidePanel.fit_text(_j.cat('+ ', '  •  '.join(gained)), SidePanel.F_TXT_S, self.text_w), self.x0, self.y, SidePanel.F_TXT_S, Cyber.alpha(Cyber.good(), 225))
            self.y += 2
    def room_lines(self, t, locked):
        """Lines of small text that still fit between self.y and the rows below the upgrade description (ability note,
targeting, sell), so the upgrade preview never pushes the panel past the bottom of the screen."""
        need = (((15 if locked else 0) + (0 if t.get_stats().is_support_only() else 40)) + 46)
        return _j.to_int(float(math.floor(((((Ui.H - 8) - need) - self.y) / (SidePanel.F_TXT_S.get_size() + 4)))))
    def para_fit(self, s, f, c, max_lines):
        """para() limited to max_lines, the last shown line ending in an ellipsis when text was cut."""
        lines = Ui.wrap(s, f, self.text_w)
        if len(lines) > max_lines:
            lines = lines[0:max_lines]
            lines[(max_lines - 1)] = SidePanel.fit_text(_j.cat(lines[(max_lines - 1)], ' …'), f, self.text_w)
        for l in lines:
            self.y += (f.get_size() + 4)
            self.put(l, self.x0, self.y, f, c)
    def upgrade_hover_tower(self):
        """The selected tower while the mouse is over its UPGRADE button (the map then previews the next tier's range)."""
        b = self.upgrade_btn
        t = self.screen.get_selected_tower()
        if (b is None) or (t is None) or (not t.is_alive()) or (not t.can_upgrade()):
            return None
        m = self.screen.get_mouse_logical()
        return t if b.hit(m[0], m[1]) else None
    def build_enemy_info(self, e):
        nc = (Cyber.RED if e.is_boss() else Cyber.TEXT)
        self.header(e.get_type().display_name, nc, (_j.cat(e.get_type().get_boss_class().label, ' BOSS') if e.is_boss() else 'ENEMY'), (Cyber.RED if e.is_boss() else Cyber.MAGENTA))
        mods = _j.StringBuilder()
        for m in e.get_modifiers():
            if mods.length() > 0:
                mods.append(', ')
            mods.append(m.label)
        if mods.length() > 0:
            self.y += 4
            self.put(mods.to_string().upper(), self.x0, (self.y + 12), Cyber.mono(Font.BOLD, 11), Cyber.YELLOW)
            self.y += 14
        self.y += 8
        self.enemy_bar = Cyber.Bar(self.x0, self.y, self.text_w, 12, 4).colors(Cyber.GREEN, Color(0, 0, 0, 200), Cyber.alpha(Cyber.CYAN, 120))
        self.info.add(self.enemy_bar)
        self.y += 12
        hp = self.put('', self.x0, (self.y + 18), Cyber.mono(Font.BOLD, 13), Cyber.TEXT)
        _j_add(self.dyn, _j.Fn(lambda : Cyber.set_text(hp, _j.cat('HP ', Cyber.amount(e.get_hp()), ' / ', Cyber.amount(e.get_max_hp()), ('' if e.is_alive() else '  (destroyed)')))))
        Cyber.set_text(hp, _j.cat('HP ', Cyber.amount(e.get_hp()), ' / ', Cyber.amount(e.get_max_hp())))
        self.y += 20
        self.section('stats')
        yy = self.y
        self.stat_cell(self.x0, yy, 'speed', _j.Fn(lambda : _j.cat(Ui.fmt(e.get_type().speed), 'x')), Cyber.TEXT)
        self.stat_cell((self.x0 + 180), yy, 'reward', _j.Fn(lambda : _j.cat('$', e.get_type().reward)), Cyber.YELLOW)
        self.stat_cell(self.x0, (yy + 34), 'lives cost', _j.Fn(lambda : _j.s(e.get_type().lives)), Cyber.RED)
        self.stat_cell((self.x0 + 180), (yy + 34), 'armour', _j.Fn(lambda : _j.cat(_j.to_int((e.get_type().get_armor() * 100)), '%')), Cyber.TEXT)
        self.y += 68
        if e.is_lead_type():
            self.para('Lead-type: immune to Sharp damage', SidePanel.F_TXT, Cyber.YELLOW, 1)
        inj = IntrusionText.enemy_line(e)
        if inj is not None:
            self.para(inj, SidePanel.F_TXT, Cyber.RED, 1)
        if e.get_type().has_children():
            self.para(_j.cat('Releases ', e.get_type().total_children(), ' ', e.get_type().get_child_types()[0].display_name, (_j.cat(' + ', e.get_type().get_child_types()[1].display_name) if (len(e.get_type().get_child_types()) > 1) else '')), SidePanel.F_TXT, Cyber.TEXT, 2)
        self.y += 4
        self.para(e.get_type().description, SidePanel.F_TXT, Cyber.MUTED, 0)
        if e.get_type().mechanic is Mechanic.RADIX_PHASES:
            ph = ['plain (layers 8-7)', 'Lead-type: armoured phase 1 (layers 6-5)', 'Lead-type: armoured phase 2 (layers 4-3)', 'Lead-type: armoured phase 3 (layers 2-1)']
            self.para(_j.cat('Current phase: ', ph[e.radix_phase()]), SidePanel.F_TXT, Cyber.YELLOW, 1)
        if not (len(e.get_stored_enemies()) == 0):
            self.para(_j.cat('Storing ', len(e.get_stored_enemies()), ' enemies'), SidePanel.F_TXT, Cyber.YELLOW, 1)
        self.y += 14
        self.button(self.x0, self.y, 130, 32, 'DESELECT', _j.Fn(lambda : self.screen.select_enemy(None))).set_accent(Cyber.MUTED)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.audio.sfx import Sfx  # noqa: E402
from lindefense.ui.hero_stat_text import HeroStatText  # noqa: E402
from lindefense.ui.intrusion_text import IntrusionText  # noqa: E402
from lindefense.ui.shop_layout import ShopLayout  # noqa: E402
from lindefense.ui.sprites.towers.tower_icons import TowerIcons  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

SidePanel.serial_version_uid = 1
SidePanel.F_MICRO = Cyber.mono(Font.BOLD, 9)
SidePanel.F_VAL = Cyber.mono(Font.BOLD, 15)
SidePanel.F_NAME = Cyber.display(Font.BOLD, 26)
SidePanel.F_SEC = Cyber.display(Font.BOLD, 16)
SidePanel.F_TXT = Cyber.body(Font.PLAIN, 12)
SidePanel.F_TXT_S = Cyber.body(Font.PLAIN, 11)
SidePanel.BRIEF_H = 96.0
SidePanel.ShopIcon.serial_version_uid = 1
