"""Lindefense CatalogScreen (ported from src/lindefense/ui/CatalogScreen.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy import boss_abilities
from lindefense.enemy.boss import Boss, PalantirProtocols
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType
from lindefense.enemy.types import Modifier
from lindefense.jenum import EnumSet
from lindefense.jenum import JEnum
from lindefense.map.path import Path
from lindefense.tower import catalog
from lindefense.tower.tower_type import AttackKind
from lindefense.tower.tower_type import TowerType
from lindefense.sim.misc import HeroCollection


class CatalogScreen(GCompound):
    """The Catalog (main menu): every enemy, boss, tower and hero with its sprite and what it does. Four tabs, and a
full-width grid of name + sprite cards; clicking one pops the detail card (full stats, description, upgrade
path) up over the grid. Every number and description is read from the data tables (EnemyType,
TowerCatalog), so the catalog always matches the game."""
    class Tab(JEnum):
        """Catalog sections."""
        ENEMIES = ('ENEMIES', )
        BOSSES = ('BOSSES', )
        TOWERS = ('TOWERS', )
        HEROES = ('HEROES', )
        def _init(self, l):
            self.label = None
            self.label = l
            pass
    def __init__(self, on_close, heroes=None):
        self.heroes = heroes          # the saved Hero Store collection (owned / locked badges); persistent() if None
        self.on_close = None
        self.card_frame = None
        self.close_detail_btn = None
        self.selected = 0
        self.detail_open = False
        self.live_sprite = None
        self.live_enemy = None
        self.time = 0.0
        self.y = 0.0
        GCompound.__init__(self)
        self.chrome = _j.ArrayList()
        self.grid_buttons = _j.ArrayList()
        self.grid_layer = GCompound()
        self.card = GCompound()
        self.tabs = _j.ArrayList()
        self.tab = CatalogScreen.Tab.ENEMIES
        self.on_close = on_close
        self.add(Ui.rect(0, 0, Ui.W, Ui.H, Cyber.SCRIM, Ui.c(0x000000, 0)))
        self.add(Cyber.Chamfer(20, 20, (Ui.W - 40), (Ui.H - 40), 6).fill(Color(9, 14, 28, 250)))
        self.add(Ui.label('CATALOG', CatalogScreen.LIST_X, 94, Cyber.display(Font.BOLD, 40), Cyber.TEXT))
        def _lam1():
            if self.detail_open:
                self.close_detail()
            else:
                on_close()
        back = UIButton(((Ui.W - 50) - 180), 52, 180, 46, 'BACK  [ESC]', Cyber.display(Font.BOLD, 18), _j.Fn(_lam1))
        self.add(back)
        _j_add(self.chrome, back)
        tx = 330.0
        for t in CatalogScreen.Tab.values():
            b = UIButton(tx, 58, 150, 40, _j.cat(t.label, ' (', len(CatalogScreen.entries(t)), ')'), Cyber.display(Font.BOLD, 16), _j.Fn(lambda t=t: self.set_tab(t)))
            b.set_accent((Cyber.YELLOW if (t is CatalogScreen.Tab.HEROES) else (Cyber.RED if (t is CatalogScreen.Tab.BOSSES) else Cyber.CYAN)))
            b.set_flat(True)
            self.add(b)
            _j_add(self.chrome, b)
            _j_add(self.tabs, b)
            tx += 158
        self.add(self.grid_layer)
        self.card_frame = Cyber.Chamfer(CatalogScreen.CARD_X, CatalogScreen.CARD_Y, CatalogScreen.CARD_W, CatalogScreen.CARD_H, 6).fill(Color(11, 17, 33, 252)).border(Cyber.EDGE_HI)
        self.add(self.card_frame)
        self.add(self.card)
        self.close_detail_btn = UIButton(((CatalogScreen.CARD_X + CatalogScreen.CARD_W) - 46), (CatalogScreen.CARD_Y + 14), 32, 32, 'X', Cyber.display(Font.BOLD, 16), _j.Fn(self.close_detail))
        self.add(self.close_detail_btn)
        _j_add(self.chrome, self.close_detail_btn)
        self.set_tab(CatalogScreen.Tab.ENEMIES)
    @staticmethod
    def entries(t):
        """Entries of a tab, in game order."""
        l = _j.ArrayList()
        _sw1 = t
        if _sw1 is CatalogScreen.Tab.ENEMIES:
            for e in EnemyType.values():
                if not e.is_boss():
                    _j_add(l, e)
        elif _sw1 is CatalogScreen.Tab.BOSSES:
            for e in EnemyType.values():
                if e.is_boss():
                    _j_add(l, e)
        elif _sw1 is CatalogScreen.Tab.TOWERS:
            for ty in TowerType.shop_towers():
                _j_add(l, ty)
        elif _sw1 is CatalogScreen.Tab.HEROES:
            for ty in TowerType.heroes():
                _j_add(l, ty)
        else:
            pass
        return l
    def get_tab(self):
        return self.tab
    def hero_collection(self):
        if self.heroes is None:
            self.heroes = HeroCollection.persistent()
        return self.heroes
    def owned_heroes(self):
        """Heroes permanently unlocked in the Hero Store (real purchases)."""
        c = self.hero_collection()
        return [h for h in TowerType.heroes() if c.is_unlocked(h)]
    def set_tab(self, t):
        self.tab = t
        self.selected = 0
        for i in range(len(self.tabs)):
            self.tabs[i].set_selected((CatalogScreen.Tab.values()[i] is t))
        self.close_detail()
        self.rebuild_grid()
    def select(self, i):
        """Selects entry i and pops its detail card up over the grid."""
        self.selected = max(0, min((len(CatalogScreen.entries(self.tab)) - 1), i))
        self.detail_open = True
        self.rebuild_card()
        self.update_detail_visibility()
    def close_detail(self):
        """Dismisses the detail card, returning to the name + sprite grid."""
        self.detail_open = False
        self.update_detail_visibility()
    def update_detail_visibility(self):
        self.grid_layer.set_visible((not self.detail_open))
        self.card_frame.set_visible(self.detail_open)
        self.card.set_visible(self.detail_open)
        self.close_detail_btn.set_visible(self.detail_open)
    def rebuild_grid(self):
        self.grid_layer.remove_all()
        self.grid_buttons.clear()
        es = CatalogScreen.entries(self.tab)
        if len(es) == 0:
            return
        cols = max(1, min(_j.to_int(((CatalogScreen.GRID_W + CatalogScreen.CELL_GAP) / (CatalogScreen.CELL_W + CatalogScreen.CELL_GAP))), len(es)))
        row_w = ((cols * CatalogScreen.CELL_W) + ((cols - 1) * CatalogScreen.CELL_GAP))
        x0 = (CatalogScreen.GRID_X + ((CatalogScreen.GRID_W - row_w) / 2))
        heroes = (self.tab is CatalogScreen.Tab.HEROES)
        if heroes:
            owned = len(self.owned_heroes())
            hl = Ui.label(_j.cat(owned, ' / ', len(es), ' UNLOCKED'), x0, (CatalogScreen.GRID_Y - 22), Cyber.mono(Font.BOLD, 14), Cyber.YELLOW)
            self.grid_layer.add(hl)
            bx = ((x0 + hl.get_width()) + 16)
            self.grid_layer.add(Ui.rect(bx, (CatalogScreen.GRID_Y - 31), 220, 8, Cyber.alpha(Cyber.YELLOW, 40), Cyber.alpha(Cyber.YELLOW, 40)))
            self.grid_layer.add(Ui.rect(bx, (CatalogScreen.GRID_Y - 31), _j.dmax(2, ((220.0 * owned) / max(1, len(es)))), 8, Cyber.YELLOW, Cyber.YELLOW))
            self.grid_layer.add(Ui.label('Buy heroes in the Hero Store during a match (K); a purchase is permanent.', (bx + 236), (CatalogScreen.GRID_Y - 22), Cyber.body(Font.PLAIN, 14), Cyber.MUTED))
        for i in range(len(es)):
            idx = i
            col = _j.imod(i, cols)
            row = _j.idiv(i, cols)
            cx = (x0 + (col * (CatalogScreen.CELL_W + CatalogScreen.CELL_GAP)))
            cy = (CatalogScreen.GRID_Y + (row * (CatalogScreen.CELL_H + CatalogScreen.ROW_GAP)))
            o = es[i]
            name = (o.display_name if isinstance(o, EnemyType) else o.display_name)
            b = UIButton(cx, cy, CatalogScreen.CELL_W, CatalogScreen.CELL_H, '', _j.Fn(lambda idx=idx: self.select(idx)))
            if (not isinstance(o, TowerType)) and o.is_boss():
                b.set_accent(Cyber.RED)
            self.grid_layer.add(b)
            _j_add(self.grid_buttons, b)
            icon = (TowerIcons.create(o, 0, CatalogScreen.ICON_SIZE) if isinstance(o, TowerType) else CatalogScreen.build_enemy_icon(o, CatalogScreen.ICON_SIZE))
            icon.set_location((cx + (CatalogScreen.CELL_W / 2)), ((cy + 14) + (CatalogScreen.ICON_SIZE / 2)))
            self.grid_layer.add(icon)
            nf = CatalogScreen.fit_font(name, Cyber.display(Font.BOLD, 15), (CatalogScreen.CELL_W - 12), 9)
            nl = Ui.label(name, 0, ((cy + CatalogScreen.CELL_H) - 14), nf, Cyber.TEXT)
            nl.set_location((cx + ((CatalogScreen.CELL_W - nl.get_width()) / 2)), ((cy + CatalogScreen.CELL_H) - 14))
            self.grid_layer.add(nl)
            if heroes:
                self.hero_badge(o, cx, cy)
    def hero_badge(self, t, cx, cy):
        """OWNED / LOCKED tag in a hero card's top-right corner; locked cards are dimmed."""
        own = self.hero_collection().is_unlocked(t)
        if not own:
            self.grid_layer.add(Ui.rect((cx + 2), (cy + 2), (CatalogScreen.CELL_W - 4), (CatalogScreen.CELL_H - 4), Color(2, 4, 10, 120), Color(2, 4, 10, 0)))
        f = Cyber.mono(Font.BOLD, 9)
        tag = Ui.label(('OWNED' if own else 'LOCKED'), 0, 0, f, (Color(0x031219) if own else Cyber.MUTED))
        tw = (tag.get_width() + 12)
        tx = (((cx + CatalogScreen.CELL_W) - 8) - tw)
        if own:
            self.grid_layer.add(Ui.rect(tx, (cy + 8), tw, 16, Cyber.good(), Cyber.good()))
        else:
            self.grid_layer.add(Ui.rect(tx, (cy + 8), tw, 16, Color(255, 255, 255, 14), Color(255, 255, 255, 14)))
        tag.set_location((tx + 6), (cy + 20))
        self.grid_layer.add(tag)
    @staticmethod
    def build_enemy_icon(t, size):
        """A static, centred enemy/boss sprite fit roughly into a size x size box (matches TowerIcons#create's framing)."""
        p = Path('catalog', (-1), (-1), 1, (-1), 1, 1, (-1), 1, (-1), (-1))
        e = (Boss(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0) if t.is_boss() else Enemy(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0))
        sprite = SpriteFactory.create(e)
        sprite.sync(e, 0)
        scale = ((_j.dmin(1.1, (42.0 / _j.dmax(6, t.radius))) if t.is_boss() else _j.dmin(5.0, (95.0 / _j.dmax(6, t.radius)))) * (size / 200.0))
        g = GCompound()
        g.add(sprite)
        g.scale(scale)
        return g
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
    def line(self, s, f, c, x, w):
        for l in Ui.wrap(s, f, w):
            self.y += (f.get_size() + 5)
            self.card.add(Ui.label(l, x, self.y, f, c))
    def heading(self, s):
        self.y += 24
        self.card.add(Ui.label((s[0:1].upper() + s[1:]), CatalogScreen.TX, self.y, Cyber.body(Font.BOLD, 14), Cyber.MUTED))
        self.y += 2
    def rebuild_card(self):
        self.card.remove_all()
        self.live_sprite = None
        self.live_enemy = None
        es = CatalogScreen.entries(self.tab)
        if len(es) == 0:
            return
        o = es[self.selected]
        self.y = (CatalogScreen.CARD_Y + 40)
        if isinstance(o, EnemyType):
            self.enemy_card(o)
        else:
            self.tower_card(o)
    def enemy_card(self, t):
        p = Path('catalog', (-1), (-1), 1, (-1), 1, 1, (-1), 1, (-1), (-1))
        self.live_enemy = (Boss(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0) if t.is_boss() else Enemy(t, EnumSet.none_of(), p, 0, 0, 1.0, 1.0))
        self.live_sprite = SpriteFactory.create(self.live_enemy)
        holder = GCompound()
        holder.add(self.live_sprite)
        scale = (_j.dmin(1.1, (42 / _j.dmax(6, t.radius))) if t.is_boss() else _j.dmin(5.0, (95 / _j.dmax(6, t.radius))))
        holder.scale(scale)
        holder.set_location((CatalogScreen.CARD_X + 165), (CatalogScreen.CARD_Y + 230))
        self.card.add(holder)
        self.card.add(Ui.label(t.display_name, CatalogScreen.TX, (self.y + 10), Cyber.display(Font.BOLD, 40), (Cyber.RED if t.is_boss() else Cyber.TEXT)))
        self.y += 18
        cls_ = (_j.cat(t.get_boss_class().label, '-CLASS BOSS') if t.is_boss() else ('PALANTIR DECOY' if t.is_hologram() else ('SORTING ALGORITHM' if t.is_sorting_algorithm() else ('LINKED LIST' if t.is_linked_list() else 'DATA STRUCTURE'))))
        self.y += 16
        self.card.add(Ui.label(cls_, CatalogScreen.TX, self.y, Cyber.mono(Font.BOLD, 13), (Cyber.RED if t.is_boss() else Cyber.MAGENTA)))
        self.heading('stats')
        self.stat_grid([['health', _j.cat(Cyber.commas(t.base_hp), ('' if t.is_boss() else ' layers'))], ['speed', _j.cat(Ui.fmt(t.speed), 'x')], ['reward', _j.cat('$', t.reward)], ['lives cost', _j.s(t.lives)], ['armour', _j.cat(_j.to_int(_j.jround((t.get_armor() * 100))), '%')], [('class' if t.is_boss() else 'mechanic'), (t.get_boss_class().label if t.is_boss() else t.mechanic.name.replace('_', ' ').lower())]])
        self.heading('what it does')
        self.line(t.description, Cyber.body(Font.PLAIN, 16), Cyber.TEXT, CatalogScreen.TX, CatalogScreen.TW)
        traits = _j.ArrayList()
        if t.is_lead_body():
            _j_add(traits, 'Lead-type: Sharp damage cannot hurt it.')
        if t.is_ceramic_body():
            _j_add(traits, 'Ceramic outer layer: Blunt, Kinetic and Sonic damage deal x2.')
        if t.has_innate_camo():
            _j_add(traits, 'Always Camo: needs detection to be targeted.')
        if t.get_weak_hit_threshold() > 0:
            _j_add(traits, _j.cat('Weak hits (under ', t.get_weak_hit_threshold(), ' damage) are halved.'))
        if t.has_children():
            sb = _j.StringBuilder('Releases ')
            ch = t.get_child_types()
            n = t.get_child_counts()
            for i in range(len(ch)):
                if i > 0:
                    sb.append(' + ')
                sb.append(n[i]).append(' x ').append(ch[i].display_name)
            _j_add(traits, sb.append(' when destroyed.').to_string())
        if t.is_fast():
            _j_add(traits, 'Fast: a priority target for rapid-fire towers.')
        boss = CatalogScreen.boss_note(t)
        if boss is not None:
            _j_add(traits, boss)
        if t.is_boss():
            _j_add(traits, "Bosses take full damage from every attack; freezes and stuns do not work on them and slows are weaker. Rohan's slows still apply.")
        if not (len(traits) == 0):
            self.heading('traits')
            for s in traits:
                self.line(_j.cat('•  ', s), Cyber.body(Font.PLAIN, 15), Cyber.MUTED, CatalogScreen.TX, CatalogScreen.TW)
        self.heading('modifiers it can carry')
        self.line('Camo (needs detection)  •  Regrow (heals over time)  •  Fortified (double HP)  •  Prompt Injection (wave 30+: an IGNORE PREVIOUS INSTRUCTIONS sign that hijacks nearby towers)', Cyber.body(Font.PLAIN, 14), Cyber.MUTED, CatalogScreen.TX, CatalogScreen.TW)
    @staticmethod
    def boss_note(t):
        """Campaign notes for each boss (debut wave and special rules)."""
        _sw2 = t
        if _sw2 is EnemyType.BELLARMINE_COLLEGE_PREP:
            return _j.cat('Debuts on wave 40 as the first MOAB-class boss. ', boss_abilities.describe(t), ' Save your burst for after the shield.')
        elif _sw2 is EnemyType.SW_RESOURCE_CONSULTANT:
            return _j.cat('Debuts on wave 60. Low-damage towers struggle: bring heavy hitters (Ronil, Zethos, DeepSeek). ', boss_abilities.describe(t), ' Keep some towers on First to catch them.')
        elif _sw2 is EnemyType.THREE_COM:
            return _j.cat('Debuts on wave 80; the largest HP pool before the finale. ', boss_abilities.describe(t), ' Kill the hub first.')
        elif _sw2 is EnemyType.LOCKHEED_MARTIN:
            return _j.cat('Debuts on wave 90. Camo and very fast: you need detection (Perplexity, Grok, or Gemini / Llama after their second upgrade). ', boss_abilities.describe(t))
        elif _sw2 is EnemyType.PALANTIR:
            return PalantirProtocols.describe()
        elif _sw2 is EnemyType.PALANTIR_HOLOGRAM:
            return 'Projected by Palantir in phase 2. Towers immune to prompt injection (Claude, Copilot, DeepSeek, Perplexity, Mr. Lindemann) see through it.'
        else:
            return None
    def stat_grid(self, cells):
        x0 = CatalogScreen.TX
        cw = (CatalogScreen.TW / 3)
        for i in range(len(cells)):
            cx = (x0 + (_j.imod(i, 3) * cw))
            cy = ((self.y + 6) + (_j.idiv(i, 3) * 46))
            self.card.add(Ui.label((cells[i][0][0:1].upper() + cells[i][0][1:].lower()), cx, (cy + 12), Cyber.body(Font.PLAIN, 12), Cyber.MUTED))
            self.card.add(Ui.label(cells[i][1], cx, (cy + 34), Cyber.mono(Font.BOLD, 17), Cyber.TEXT))
        self.y += (6 + (_j.idiv((len(cells) + 2), 3) * 46))
    def tower_card(self, t):
        d = catalog.get(t)
        s = d.base_stats
        accent = Cyber.lerp(Ui.c(t.primary_rgb), Color.WHITE, 0.3)
        icon = TowerIcons.create(t, 0, 200)
        icon.set_location((CatalogScreen.CARD_X + 165), (CatalogScreen.CARD_Y + 170))
        self.card.add(icon)
        if len(d.upgrades) > 0:
            max_ = TowerIcons.create(t, len(d.upgrades), 150)
            max_.set_location((CatalogScreen.CARD_X + 165), (CatalogScreen.CARD_Y + 420))
            self.card.add(max_)
            self.card.add(Ui.label('BASE', (CatalogScreen.CARD_X + 145), (CatalogScreen.CARD_Y + 292), Cyber.mono(Font.BOLD, 12), Cyber.MUTED))
            ml = Ui.label(_j.cat('MAX: ', d.tier_labels[len(d.upgrades)]), 0, (CatalogScreen.CARD_Y + 520), Cyber.mono(Font.BOLD, 12), Cyber.YELLOW)
            ml.set_location(((CatalogScreen.CARD_X + 165) - (ml.get_width() / 2)), (CatalogScreen.CARD_Y + 520))
            self.card.add(ml)
        self.card.add(Ui.label(t.display_name, CatalogScreen.TX, (self.y + 10), Cyber.display(Font.BOLD, 40), accent))
        self.y += 18
        price = (_j.cat('HERO STORE  ', Ui.money(d.unlock_cost), '  //  ', Ui.money(d.base_cost), ' to deploy, once per match') if t.is_hero() else _j.cat(Ui.money(d.base_cost), '  //  ', t.faction.label.upper(), '  //  full path ', Ui.money(d.total_cost())))
        self.y += 16
        self.card.add(Ui.label(d.subtitle, CatalogScreen.TX, self.y, Cyber.body(Font.BOLD, 15), Cyber.MUTED))
        self.y += 20
        self.card.add(Ui.label(price, CatalogScreen.TX, self.y, Cyber.mono(Font.BOLD, 13), Cyber.YELLOW))
        if t.is_hero():
            own = self.hero_collection().is_unlocked(t)
            self.y += 20
            self.card.add(Ui.label(('OWNED  //  deploy it from the shop during any match' if own else 'LOCKED  //  unlock it in the Hero Store during a match (K)'), CatalogScreen.TX, self.y, Cyber.mono(Font.BOLD, 12), (Cyber.GREEN if own else Cyber.MUTED)))
        self.heading('what it does')
        self.line(d.description, Cyber.body(Font.PLAIN, 15), Cyber.TEXT, CatalogScreen.TX, CatalogScreen.TW)
        imm = IntrusionText.type_line(t)
        if imm is not None:
            self.line(imm, Cyber.mono(Font.BOLD, 13), Cyber.GREEN, CatalogScreen.TX, CatalogScreen.TW)
            fw = IntrusionText.firewall_line(t)
            if fw is not None:
                self.line(fw, Cyber.body(Font.PLAIN, 13), Cyber.GREEN, CatalogScreen.TX, CatalogScreen.TW)
        else:
            self.line(IntrusionText.vulnerable_line(), Cyber.body(Font.PLAIN, 13), Cyber.MUTED, CatalogScreen.TX, CatalogScreen.TW)
        self.heading((HeroStatText.attack_name(t).lower() if HeroStatText.uses_units(t) else 'base attack'))
        if HeroStatText.uses_units(t):
            for l in HeroStatText.attack_lines(t):
                self.line(l, Cyber.mono(Font.BOLD, 14), Cyber.TEXT, CatalogScreen.TX, CatalogScreen.TW)
        else:
            kind = ('pulse' if (s.kind is AttackKind.PULSE) else ('chain' if (s.kind is AttackKind.CHAIN) else ('beam' if (s.kind is AttackKind.INSTANT) else ('special' if (s.kind is AttackKind.CUSTOM) else ('support' if (s.kind is AttackKind.NONE) else 'projectile')))))
            self.line(_j.cat(Ui.fmt(s.hit.damage), ' ', s.hit.type.label.lower(), ' dmg  •  every ', Ui.fmt(s.interval()), 's  •  range ', ('whole map' if s.has_unlimited_range() else _j.s(_j.to_int(s.range))), '  •  pierce ', s.pierce, '  •  ', kind, (_j.cat('  •  splash ', _j.to_int(s.splash_radius)) if (s.splash_radius > 0) else ''), ('  •  camo detection' if s.sees_camo else '')), Cyber.mono(Font.BOLD, 14), Cyber.TEXT, CatalogScreen.TX, CatalogScreen.TW)
        if len(d.upgrades) > 0:
            self.heading('upgrade path')
            for i in range(len(d.upgrades)):
                u = d.upgrades[i]
                self.y += 4
                self.line(_j.cat((i + 1), '.  ', u.name, '   ', Ui.money(u.cost)), Cyber.display(Font.BOLD, 16), Cyber.YELLOW, CatalogScreen.TX, CatalogScreen.TW)
                self.line(u.description, Cyber.body(Font.PLAIN, 13), Cyber.MUTED, (CatalogScreen.TX + 22), (CatalogScreen.TW - 22))
        a = d.ability
        self.heading('active ability')
        if a is None:
            self.line('None: heroes are passive and grow through their upgrades.', Cyber.body(Font.PLAIN, 14), Cyber.MUTED, CatalogScreen.TX, CatalogScreen.TW)
        else:
            self.line(_j.cat(a.name, '   (', _j.to_int(a.cooldown), ' s cooldown)'), Cyber.display(Font.BOLD, 17), Cyber.MAGENTA, CatalogScreen.TX, CatalogScreen.TW)
            if catalog.ability_needs_unlock(d.type):
                self.line(_j.cat('Locked: buy it for ', Ui.money(catalog.ABILITY_UNLOCK_COST), ' once the tower has every upgrade.'), Cyber.mono(Font.BOLD, 13), Cyber.YELLOW, CatalogScreen.TX, CatalogScreen.TW)
            self.line(a.description, Cyber.body(Font.PLAIN, 14), Cyber.TEXT, CatalogScreen.TX, CatalogScreen.TW)
    def buttons(self):
        l = _j.ArrayList(self.chrome)
        if not self.detail_open:
            l.extend(self.grid_buttons)
        return l
    def mouse_pressed(self, lx, ly):
        for b in self.buttons():
            if b.hit(lx, ly) and b.click():
                return
    def mouse_moved(self, lx, ly):
        for b in self.buttons():
            b.set_hover(b.hit(lx, ly))
    def key_pressed(self, e):
        """Up / down step through the list, left / right switch tabs, Esc goes back."""
        _sw3 = e.get_key_code()
        if _sw3 == KeyEvent.VK_ESCAPE:
            if self.detail_open:
                self.close_detail()
            else:
                self.on_close()
        elif _sw3 == KeyEvent.VK_DOWN:
            self.select((self.selected + 1))
        elif _sw3 == KeyEvent.VK_UP:
            self.select((self.selected - 1))
        elif _sw3 == KeyEvent.VK_RIGHT:
            self.set_tab(CatalogScreen.Tab.values()[_j.imod((self.tab.ordinal + 1), len(CatalogScreen.Tab.values()))])
        elif _sw3 == KeyEvent.VK_LEFT:
            self.set_tab(CatalogScreen.Tab.values()[_j.imod(((self.tab.ordinal + len(CatalogScreen.Tab.values())) - 1), len(CatalogScreen.Tab.values()))])
        else:
            pass
    def frame(self, dt):
        self.time += dt
        for b in self.buttons():
            b.animate(dt)
        if (self.live_sprite is not None) and (self.live_enemy is not None):
            self.live_enemy.set_distance(_j.fmod((self.time * 0.3), 1.0))
            self.live_sprite.sync(self.live_enemy, self.time)
            self.live_sprite.set_location(0, 0)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.hero_stat_text import HeroStatText  # noqa: E402
from lindefense.ui.intrusion_text import IntrusionText  # noqa: E402
from lindefense.ui.sprites.sprite_factory import SpriteFactory  # noqa: E402
from lindefense.ui.sprites.towers.tower_icons import TowerIcons  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

CatalogScreen.serial_version_uid = 1
CatalogScreen.LIST_X = 50.0
CatalogScreen.LIST_Y = 168.0
CatalogScreen.CARD_X = 500.0
CatalogScreen.CARD_Y = 150.0
CatalogScreen.CARD_W = 1050.0
CatalogScreen.CARD_H = 800.0
CatalogScreen.GRID_X = CatalogScreen.LIST_X
CatalogScreen.GRID_W = ((CatalogScreen.CARD_X + CatalogScreen.CARD_W) - CatalogScreen.LIST_X)
CatalogScreen.GRID_Y = CatalogScreen.LIST_Y
CatalogScreen.CELL_W = 160.0
CatalogScreen.CELL_H = 148.0
CatalogScreen.CELL_GAP = 16.0
CatalogScreen.ROW_GAP = 16.0
CatalogScreen.ICON_SIZE = 92.0
CatalogScreen.TX = (CatalogScreen.CARD_X + 330)
CatalogScreen.TW = ((CatalogScreen.CARD_W - 330) - 40)
