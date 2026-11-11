"""Lindefense AbilityBar (ported from src/lindefense/ui/AbilityBar.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.ui import Ui


class AbilityBar(GCompound):
    """Compact ability strip along the bottom of the playfield (above the status strip): one slot per placed tower that has
an ability, each with the tower icon, a radial cooldown ring and click-to-fire. Slots appear and disappear as towers are
placed and sold; when there are more than fit, the arrows page through them. Hovering a slot shows the ability name,
description and cooldown; targeted abilities are marked with a reticle glyph. A one-line hint above the bar shows
targeting prompts and refusal reasons. Rebuilt only when the set of towers (or the page) changes; per frame only the
rings and hint are mutated."""
    class Slot:
        def __init__(self, t, b, r):
            self.tower = None
            self.button = None
            self.ring = None
            self.tower = t
            self.button = b
            self.ring = r
    def __init__(self, screen):
        self.screen = None
        self.game = None
        self.page = 0
        self.hint_time = 0.0
        GCompound.__init__(self)
        self.body = GCompound()
        self.buttons = _j.ArrayList()
        self.slots = _j.ArrayList()
        self.tip = GCompound()
        self.tip_frame = Cyber.Chamfer(0, 0, 300, 90, 8).scan(False).fill(Color(5, 9, 22, 245)).glow(0.7)
        self.tip_title = Ui.label('', 12, 22, Cyber.display(Font.BOLD, 18), Cyber.TEXT)
        self.tip_meta = Ui.label('', 12, 40, Cyber.mono(Font.BOLD, 10), Cyber.MAGENTA)
        self.tip_lines = _j.ArrayList()
        self.hint_box = GCompound()
        self.hint_frame = Cyber.Chamfer(0, 0, 300, 26, 6).scan(False).fill(Color(5, 9, 22, 235))
        self.hint_label = Ui.label('', 12, 18, Cyber.mono(Font.BOLD, 12), Cyber.CYAN)
        self.key = ''
        self.capacity = 20
        self.hint = ''
        self.hint_color = Cyber.CYAN
        self.tip_shown = ''
        self.screen = screen
        self.game = screen.get_game()
        self.add(self.body)
        self.tip.add(self.tip_frame)
        self.tip.add(self.tip_title)
        self.tip.add(self.tip_meta)
        for i in range(3):
            l = Ui.label('', 12, (58 + (i * 15)), Cyber.body(Font.PLAIN, 12), Cyber.MUTED)
            _j_add(self.tip_lines, l)
            self.tip.add(l)
        self.tip.set_visible(False)
        self.hint_box.add(self.hint_frame)
        self.hint_box.add(self.hint_label)
        self.hint_box.set_visible(False)
        self.add(self.hint_box)
        self.add(self.tip)
    def get_buttons(self):
        return self.buttons
    def show_hint(self, text, color, seconds):
        """Shows a one-line message above the bar for seconds (targeting prompts, refusal reasons); 0 = until replaced."""
        self.hint = text
        self.hint_color = color
        self.hint_time = (1e9 if (seconds <= 0) else seconds)
    def clear_hint(self):
        self.hint = ''
        self.hint_time = 0.0
    def ability_towers(self):
        l = _j.ArrayList()
        for t in self.game.get_tower_manager().get_towers():
            if (t.is_alive() and (not t.is_temporary())) and (t.get_ability() is not None):
                _j_add(l, t)
        return l
    def rebuild(self, all_):
        self.body.remove_all()
        self.buttons.clear()
        self.slots.clear()
        n = len(all_)
        avail = (((Ui.WORLD_W - (2 * AbilityBar.LEFT)) - AbilityBar.LABEL_W) - 8)
        self.capacity = max(4, _j.to_int(float(math.floor((avail / AbilityBar.PITCH)))))
        paged = (n > self.capacity)
        if paged:
            self.capacity = max(3, _j.to_int(float(math.floor(((avail - (2 * AbilityBar.ARROW_W)) / AbilityBar.PITCH)))))
        pages = max(1, _j.idiv(((n + self.capacity) - 1), self.capacity))
        self.page = max(0, min((pages - 1), self.page))
        if n == 0:
            return
        from_ = (self.page * self.capacity)
        to = min(n, (from_ + self.capacity))
        w = (((AbilityBar.LABEL_W + ((to - from_) * AbilityBar.PITCH)) + (((2 * AbilityBar.ARROW_W) + 8) if paged else 0)) + 6)
        self.body.add(Cyber.Chamfer(AbilityBar.LEFT, AbilityBar.Y, w, AbilityBar.HEIGHT, 10).fill(Color(5, 9, 22, 214)).border(Cyber.alpha(Cyber.MAGENTA, 150)).scan(False))
        self.body.add(Ui.label('ABILITIES', (AbilityBar.LEFT + 10), (AbilityBar.Y + 22), Cyber.mono(Font.BOLD, 10), Cyber.alpha(Cyber.MAGENTA, 230)))
        self.body.add(Ui.label((_j.cat((self.page + 1), ' / ', pages) if paged else _j.cat(n, (' TOWER' if (n == 1) else ' TOWERS'))), (AbilityBar.LEFT + 10), (AbilityBar.Y + 38), Cyber.mono(Font.PLAIN, 10), Cyber.MUTED))
        x = (AbilityBar.LEFT + AbilityBar.LABEL_W)
        if paged:
            def _lam1():
                self.page = max(0, (self.page - 1))
                self.key = ''
            prev = UIButton(x, (AbilityBar.Y + 11), AbilityBar.ARROW_W, 32, '<', Cyber.display(Font.BOLD, 16), _j.Fn(_lam1))
            prev.set_accent(Cyber.MAGENTA)
            self.body.add(prev)
            _j_add(self.buttons, prev)
            x += (AbilityBar.ARROW_W + 4)
        for i in range(from_, to):
            t = all_[i]
            b = UIButton(x, (AbilityBar.Y + ((AbilityBar.HEIGHT - AbilityBar.SLOT) / 2)), AbilityBar.SLOT, AbilityBar.SLOT, '', _j.Fn(lambda t=t: self.screen.fire_ability(t)))   # bind per iteration
            b.set_accent(Ui.c(t.get_type().primary_rgb))
            self.body.add(b)
            _j_add(self.buttons, b)
            cx = (x + (AbilityBar.SLOT / 2))
            cy = (AbilityBar.Y + (AbilityBar.HEIGHT / 2))
            icon = IconImage(t.get_type(), t.get_tier(), 30)
            icon.set_location(cx, cy)
            self.body.add(icon)
            ring = RadialCooldown(((AbilityBar.SLOT / 2) - 3), 3)
            ring.set_location(cx, cy)
            self.body.add(ring)
            if t.get_ability().needs_target:
                self.body.add(Ui.label('+', ((x + AbilityBar.SLOT) - 11), (((AbilityBar.Y + (AbilityBar.HEIGHT / 2)) + (AbilityBar.SLOT / 2)) - 5), Cyber.mono(Font.BOLD, 13), Cyber.YELLOW))
            _j_add(self.slots, AbilityBar.Slot(t, b, ring))
            x += AbilityBar.PITCH
        if paged:
            def _lam2():
                self.page = min((pages - 1), (self.page + 1))
                self.key = ''
            next_ = UIButton((x + 2), (AbilityBar.Y + 11), AbilityBar.ARROW_W, 32, '>', Cyber.display(Font.BOLD, 16), _j.Fn(_lam2))
            next_.set_accent(Cyber.MAGENTA)
            self.body.add(next_)
            _j_add(self.buttons, next_)
        self.screen.refresh_hover()
    def update(self, dt):
        all_ = self.ability_towers()
        sb = _j.StringBuilder().append(self.page)
        for t in all_:
            sb.append(',').append(t.get_id()).append(':').append(t.get_tier())
        k = sb.to_string()
        if not (k == self.key):
            self.key = k
            self.rebuild(all_)
        sel = self.screen.get_selected_tower()
        arm = self.screen.get_targeting_tower()
        pulse = self.game.get_time()
        for s in self.slots:
            t = s.tower
            s.ring.set((1 - t.get_ability_cooldown_fraction()), t.is_ability_ready(), t.is_surveilled(), Ui.c(t.get_type().primary_rgb).brighter(), pulse)
            s.button.set_selected(((t is sel) or (t is arm)))
        self.update_hint(dt)
        self.update_tip()
    def update_hint(self, dt):
        self.hint_time -= dt
        h = (self.hint if (self.hint_time > 0) else '')
        arm = self.screen.get_targeting_tower()
        hc = self.hint_color
        if (len(h) == 0) and (arm is not None):
            h = _j.cat('TARGETING  ', arm.get_ability().name.upper(), '  -  click the track to cast  -  right-click / Esc cancels')
            hc = Cyber.YELLOW
        if len(h) == 0:
            self.hint_box.set_visible(False)
            return
        Cyber.set_text(self.hint_label, h)
        Cyber.set_color(self.hint_label, hc)
        w = (self.hint_label.get_width() + 24)
        self.hint_frame.size(w, 26).border(hc)
        self.hint_box.set_location(((Ui.WORLD_W / 2.0) - (w / 2)), (AbilityBar.Y - 34))
        self.hint_box.set_visible(True)
    def update_tip(self):
        m = self.screen.get_mouse_logical()
        hover = None
        for s in self.slots:
            if s.button.hit(m[0], m[1]):
                hover = s
                break
        if hover is None:
            self.tip.set_visible(False)
            return
        t = hover.tower
        a = t.get_ability()
        meta = _j.cat(('OFFLINE (SURVEILLED)' if t.is_surveilled() else ('READY' if t.is_ability_ready() else _j.format('%.0fs LEFT', float(math.ceil(t.get_ability_cooldown_remaining()))))), '  //  CD ', _j.to_int(a.cooldown), 's', ('  //  TARGETED' if a.needs_target else ''))
        id_ = _j.cat(t.get_id(), meta)
        if not (id_ == self.tip_shown):
            self.tip_shown = id_
            Cyber.set_text(self.tip_title, _j.cat(a.name, '   (', t.get_type().display_name, ')'))
            Cyber.set_text(self.tip_meta, meta)
            lines = Ui.wrap(a.description, Cyber.body(Font.PLAIN, 12), 330)
            for i in range(len(self.tip_lines)):
                Cyber.set_text(self.tip_lines[i], (lines[i] if (i < len(lines)) else ''))
            w = (_j.dmax(self.tip_title.get_width(), 340) + 24)
            self.tip_frame.size(w, ((62 + (min(3, len(lines)) * 15)) + 6)).border(Ui.c(t.get_type().primary_rgb))
        w = self.tip_frame.get_w()
        h = self.tip_frame.get_h()
        self.tip.set_location(_j.dmax(6, _j.dmin(((Ui.WORLD_W - w) - 6), ((hover.button.get_x() + (AbilityBar.SLOT / 2)) - (w / 2)))), ((AbilityBar.Y - h) - 8))
        self.tip.set_visible(True)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.icon_image import IconImage  # noqa: E402
from lindefense.ui.radial_cooldown import RadialCooldown  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

AbilityBar.serial_version_uid = 1
AbilityBar.HEIGHT = 54.0
AbilityBar.SLOT = 46.0
AbilityBar.PITCH = 50.0
AbilityBar.LEFT = 10.0
AbilityBar.LABEL_W = 78.0
AbilityBar.ARROW_W = 24.0
AbilityBar.Y = ((Ui.BOTTOM_Y - AbilityBar.HEIGHT) - 6)
