"""Lindefense WorldView (ported from src/lindefense/ui/WorldView.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.combat.visual_event import VisualEvent
from lindefense.map.game_map import GameMap
from lindefense.map.maps import AbandonedDataCenter
from lindefense.map.maps import HallucinationCanyon
from lindefense.map.maps import LegacyMonolith
from lindefense.map.maps import SiliconCircuit
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower import shop


class WorldView(GCompound):
    """Renders the playfield: map background and track, towers, enemies (via the
sprite package), projectiles, transient effects, boss health bars, Palantir's
surveillance telegraph and the placement ghost / range circle. All children
live in world coordinates (1200x900); the compound sits at the world origin
inside the scaled root.

Big fights

  Level of detail: the number of sprites on screen picks a level (see #LOD_DECOR_LOAD) that is
      applied while this view paints (Thick#setLevel): decorative and then fine sprite details are skipped,
      enemy HP bars are drawn simplified. The minimal style paints at least at #MIN_DETAIL, so the purely
      decorative parts are never drawn; the effect budget still follows the real level.
  Effect caps: at most #MAX_EFFECTS legacy and #MAX_EFFECTS animated effects at full
      detail, fewer at higher levels of detail (#effectCap()); extra visual events are dropped.
  Effect pool: the simple flash / ring / text effects are pooled. A finished one is hidden and stays in
      the effect layer for reuse, so a busy frame neither allocates new GObjects for them nor pays ACM's linear
      remove for each one that expires."""
    class Effect:
        """A transient effect built from a VisualEvent (pooled together with its GObject)."""
        def __init__(self):
            self.obj = None
            self.ev = None
            self.t = 0.0
            self.base = None
            pass
        def set(self, o, e, b):
            self.obj = o
            self.ev = e
            self.base = b
            self.t = 0.0
            return self
    def __init__(self, screen):
        self.lod = 0
        self.screen = None
        self.game = None
        self.map = None
        self.fx = None
        self.intrusion_fx = None
        self.range_circle = None
        self.next_range_circle = None
        self.ghost = None
        self.ghost_range = None
        self.ghost_x1 = None
        self.ghost_x2 = None
        self.reticle_radius = None
        self.reticle_dot = None
        self.reticle_h = None
        self.reticle_v = None
        self.reticle_link = None
        self.reticle_plate = None
        self.ghost_plate = None
        self.hover_plate = None
        self.select_plate = None
        self.view_dock = 0.0
        self.vent_rect = None
        self.storm_rect = None
        self.time = 0.0
        self.pulses = None
        self.glow = None
        GCompound.__init__(self)
        self.background = GCompound()
        self.map_fx = GCompound()
        self.tower_layer = GCompound()
        self.enemy_layer = GCompound()
        self.hp_layer = GCompound()
        self.projectile_layer = GCompound()
        self.effect_layer = GCompound()
        self.overlay = GCompound()
        self.tower_sprites = _j.HashMap()
        self.enemy_sprites = _j.HashMap()
        self.hp_bars = _j.HashMap()
        self.projectile_sprites = _j.HashMap()
        self.effects = _j.ArrayList()
        self.animated = _j.ArrayList()
        self.telegraph_lines = _j.ArrayList()
        self.view_scale = 1.0
        self.pad_fill = _j.ArrayList()
        self.short_fx = _j.ArrayList()
        self.shake = ScreenShake()
        self.last_lives = (-1)
        self.hazard_fx = _j.ArrayList()
        self.effect_pool = _j.ArrayDeque()
        self.oval_pool = _j.ArrayDeque()
        self.line_pool = _j.ArrayDeque()
        self.label_pool = _j.ArrayDeque()
        self.screen = screen
        self.game = screen.get_game()
        self.map = self.game.get_map()
        self.set_location(0, 0)
        self.fx = WorldFx(self.game)
        self.intrusion_fx = IntrusionFx(self.game)
        self.build_background()
        self.add(self.background)
        self.add(self.map_fx)
        self.add(self.fx.ground())
        self.add(self.tower_layer)
        self.add(self.enemy_layer)
        self.add(self.fx.top())
        self.add(self.hp_layer)
        self.glow = GlowLayer(self.game)
        self.add(self.glow)
        self.add(self.projectile_layer)
        self.add(self.effect_layer)
        self.add(self.intrusion_fx.layer())
        self.add(self.overlay)
        self.build_overlay()
    def build_background(self):
        self.background.add(MapArt(self.map))
        self.pulses = MapArt.Pulses(self.map)
        self.map_fx.add(self.pulses)
        for r in self.map.get_routes():
            w = r.get_waypoints()
            self.add_marker(r.get_start(), w[1].sub(w[0]).normalized(), Cyber.good(), 'IN')
            self.add_marker(r.get_end(), w[(len(w) - 1)].sub(w[(len(w) - 2)]).normalized(), Cyber.bad(), 'OUT')
        if isinstance(self.map, SiliconCircuit):
            for p in self.map.get_pads():
                f = Ui.oval((p.x - 36), (p.y - 36), 72, 72, Ui.c(0x7fd8a8, 40), Ui.c(0x7fd8a8, 0))
                _j_add(self.pad_fill, f)
                self.map_fx.add(f)
        if isinstance(self.map, LegacyMonolith):
            self.vent_rect = Ui.rect(0, 0, GameMap.WIDTH, 10, Ui.c(0xff6a00, 45), Ui.c(0xff6a00, 120))
            self.vent_rect.set_visible(False)
            self.map_fx.add(self.vent_rect)
        if isinstance(self.map, AbandonedDataCenter):
            r = self.map.get_routes()[0]
            for h in self.map.get_hazards():
                polys = _j.ArrayList()
                prev = r.position_at(h.from_)
                d = (h.from_ + 24)
                while True:
                    next_ = r.position_at(_j.dmin(d, h.to))
                    if next_.dist(prev) > 0.5:
                        p = self.segment(prev, next_, (GameMap.TRACK_HALF_WIDTH + 2), Ui.c(h.rgb, 0))
                        p.set_visible(False)
                        self.map_fx.add(p)
                        _j_add(polys, p)
                    prev = next_
                    if d >= h.to:
                        break
                    d += 24
                _j_add(self.hazard_fx, polys)
        if isinstance(self.map, HallucinationCanyon):
            self.storm_rect = Ui.rect(0, 0, GameMap.WIDTH, GameMap.HEIGHT, Ui.c(0xff8cf0, 35), Ui.c(0xff8cf0, 0))
            self.storm_rect.set_visible(False)
            self.map_fx.add(self.storm_rect)
    def add_marker(self, at, dir_, col, text):
        """Track entry / exit marker: a flat coloured disc with a dark direction chevron and a small IN / OUT caption,
inset from the world edge so it is never clipped."""
        m = 24.0
        px = _j.dmax(m, _j.dmin((GameMap.WIDTH - m), at.x))
        py = _j.dmax(m, _j.dmin((GameMap.HEIGHT - m), at.y))
        disc = Cyber.Ring((px - 11), (py - 11), 22, 22, Cyber.alpha(col, 225), WorldView.MARKER_INK)
        disc.set_line_width(1.2)
        self.background.add(disc)
        n = Vec((-dir_.y), dir_.x)
        chev = GPolygon()
        chev.add_vertex((px + (dir_.x * 5.5)), (py + (dir_.y * 5.5)))
        chev.add_vertex(((px - (dir_.x * 2.5)) + (n.x * 5.5)), ((py - (dir_.y * 2.5)) + (n.y * 5.5)))
        chev.add_vertex(((px - (dir_.x * 2.5)) + (n.x * 2.6)), ((py - (dir_.y * 2.5)) + (n.y * 2.6)))
        chev.add_vertex((px + (dir_.x * 1.5)), (py + (dir_.y * 1.5)))
        chev.add_vertex(((px - (dir_.x * 2.5)) - (n.x * 2.6)), ((py - (dir_.y * 2.5)) - (n.y * 2.6)))
        chev.add_vertex(((px - (dir_.x * 2.5)) - (n.x * 5.5)), ((py - (dir_.y * 2.5)) - (n.y * 5.5)))
        chev.set_filled(True)
        chev.set_fill_color(WorldView.MARKER_INK)
        chev.set_color(WorldView.MARKER_INK)
        self.background.add(chev)
        l = Ui.label(text, 0, 0, Cyber.mono(Font.BOLD, 10), Cyber.alpha(col, 220))
        ly = ((py + 26) if ((py + 26) < (GameMap.HEIGHT - 4)) else (py - 17))
        l.set_location((px - (l.get_width() / 2)), ly)
        self.background.add(l)
    def segment(self, a, b, hw, col):
        d = b.sub(a).normalized()
        n = Vec(((-d.y) * hw), (d.x * hw))
        p = GPolygon()
        p.add_vertex((a.x + n.x), (a.y + n.y))
        p.add_vertex((b.x + n.x), (b.y + n.y))
        p.add_vertex((b.x - n.x), (b.y - n.y))
        p.add_vertex((a.x - n.x), (a.y - n.y))
        p.set_filled(True)
        p.set_fill_color(col)
        p.set_color(col)
        return p
    def build_overlay(self):
        self.range_circle = Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.CYAN, 12), Cyber.alpha(Cyber.CYAN, 160))
        self.range_circle.set_line_width(1.2)
        self.range_circle.set_visible(False)
        self.overlay.add(self.range_circle)
        self.next_range_circle = Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.YELLOW, 8), Cyber.alpha(Cyber.YELLOW, 210))
        self.next_range_circle.set_line_width(1.4)
        self.next_range_circle.set_dashed(True)
        self.next_range_circle.set_visible(False)
        self.overlay.add(self.next_range_circle)
        self.ghost_range = Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.CYAN, 12), Cyber.alpha(Cyber.CYAN, 160))
        self.ghost_range.set_line_width(1.2)
        self.ghost_range.set_visible(False)
        self.overlay.add(self.ghost_range)
        self.ghost = Cyber.Ring(0, 0, 40, 40, Cyber.alpha(Cyber.CYAN, 70), Cyber.CYAN)
        self.ghost.set_line_width(1.5)
        self.ghost.set_visible(False)
        self.overlay.add(self.ghost)
        self.ghost_x1 = GLine(0, 0, 1, 1)
        self.ghost_x2 = GLine(0, 0, 1, 1)
        self.ghost_x1.set_color(Cyber.RED)
        self.ghost_x2.set_color(Cyber.RED)
        self.ghost_x1.set_visible(False)
        self.ghost_x2.set_visible(False)
        self.overlay.add(self.ghost_x1)
        self.overlay.add(self.ghost_x2)
        self.reticle_radius = Cyber.Ring(0, 0, 10, 10, Cyber.alpha(Cyber.YELLOW, 28), Cyber.alpha(Cyber.YELLOW, 235))
        self.reticle_radius.set_line_width(1.6)
        self.reticle_radius.set_dashed(True)
        self.reticle_radius.set_visible(False)
        self.reticle_dot = Cyber.Ring(0, 0, 10, 10, None, Cyber.YELLOW)
        self.reticle_dot.set_line_width(1.8)
        self.reticle_dot.set_visible(False)
        self.reticle_h = GLine(0, 0, 1, 1)
        self.reticle_v = GLine(0, 0, 1, 1)
        self.reticle_link = GLine(0, 0, 1, 1)
        self.reticle_h.set_color(Cyber.YELLOW)
        self.reticle_v.set_color(Cyber.YELLOW)
        self.reticle_link.set_color(Cyber.alpha(Cyber.YELLOW, 120))
        self.reticle_h.set_visible(False)
        self.reticle_v.set_visible(False)
        self.reticle_link.set_visible(False)
        self.reticle_plate = Nameplate()
        self.overlay.add(self.reticle_radius)
        self.overlay.add(self.reticle_link)
        self.overlay.add(self.reticle_dot)
        self.overlay.add(self.reticle_h)
        self.overlay.add(self.reticle_v)
        self.hover_plate = Nameplate()
        self.select_plate = Nameplate()
        self.ghost_plate = Nameplate()
        self.overlay.add(self.hover_plate)
        self.overlay.add(self.select_plate)
        self.overlay.add(self.ghost_plate)
        self.overlay.add(self.reticle_plate)
    def update(self, dt):
        self.time += dt
        self.sync_towers(dt)
        self.sync_enemies(dt)
        self.update_lod()
        self.fx.set_lod(self.lod)
        self.fx.update(dt)
        self.glow.set_lod(self.lod)
        self.glow.update(dt)
        self.shake.update(dt)
        lives = self.game.get_lives()
        if (self.last_lives >= 0) and (lives < self.last_lives):
            self.shake.kick(0.3)
        self.last_lives = lives
        self.intrusion_fx.set_lod(self.lod)
        self.intrusion_fx.update(dt)
        self.sync_projectiles()
        self.consume_events()
        self.step_effects(dt)
        self.sync_map_fx()
        self.sync_overlay()
    def sync_towers(self, dt):
        marked = None
        pal = self.game.get_palantir()
        if ((pal is not None) and pal.is_alive()) and pal.is_telegraphing():
            marked = pal.get_marked_towers()
        for t in self.game.get_tower_manager().get_towers():
            s = self.tower_sprites.get(t)
            if s is None:
                s = TowerSprite(t)
                _j_put(self.tower_sprites, t, s)
                self.tower_layer.add(s)
            s.sync(self.game, dt, ((marked is not None) and (t in marked)))
        it = _j_iter(_j.entry_set(self.tower_sprites))
        while it.has_next():
            en = it.next()
            if not en[0].is_alive():
                self.tower_layer.remove(en[1])
                it.remove()
        for o in self.telegraph_lines:
            self.overlay.remove(o)
        self.telegraph_lines.clear()
        if marked is not None:
            for t in marked:
                l = GLine(pal.get_position().x, pal.get_position().y, t.get_position().x, t.get_position().y)
                l.set_color(Cyber.alpha((Cyber.CB_MARK if display_settings.colour_blind() else WorldView.TELEGRAPH_RGB), _j.to_int(display_settings.calm((120 + (100 * abs(math.sin((self.time * 10))))), 220))))
                self.overlay.add(l)
                _j_add(self.telegraph_lines, l)
    def sync_enemies(self, dt):
        enemies = self.game.get_enemy_manager().get_enemies()
        for e in enemies:
            s = self.enemy_sprites.get(e)
            if s is None:
                s = SpriteFactory.create(e)
                _j_put(self.enemy_sprites, e, s)
                self.enemy_layer.add(s)
            s.sync(e, self.time)
            s.step(dt)
            self.sync_hp_bar(e)
        it = _j_iter(_j.entry_set(self.enemy_sprites))
        while it.has_next():
            en = it.next()
            e = en[0]
            if (not e.is_alive()) or e.is_stored():
                self.enemy_layer.remove(en[1])
                it.remove()
                bar = self.hp_bars.pop(e, None)
                if bar is not None:
                    self.hp_layer.remove(bar)
                if ((not e.is_alive()) and (not e.has_leaked())) and (len(self.animated) < self.effect_cap()):
                    fx = (SpriteFactory.create_split_effect(e) if e.get_type().has_children() else SpriteFactory.create_death_effect(e))
                    if isinstance(fx, GObject):
                        self.effect_layer.add(fx)
                        _j_add(self.animated, fx)
    def sync_hp_bar(self, e):
        """Compact flat HP bar (dark backing and value, no border) centred just above a damaged, non-boss enemy; created
lazily, mutated every frame."""
        show = (((not e.is_boss()) and e.is_alive()) and (e.get_hp() < (e.get_max_hp() - 1e-9)))
        bar = self.hp_bars.get(e)
        if not show:
            if bar is not None:
                bar.set_visible(False)
            return
        r = e.get_radius()
        w = _j.dmax(16, _j.dmin(48, ((r * 2.0) + 4)))
        h = (4 if (r > 14) else 3)
        if bar is None:
            bar = Cyber.Bar(0, 0, w, h, 0).colors(Cyber.GREEN, WorldView.HP_BACK, None).line_width(0)
            self.hp_layer.add(bar)
            _j_put(self.hp_bars, e, bar)
        f = e.get_hp_fraction()
        bar.set_size(w, h)
        bx = (e.get_position().x - (w / 2))
        by = (((e.get_position().y - r) - h) - 5)
        if (bx != bar.get_x()) or (by != bar.get_y()):
            bar.set_location(bx, by)
        if f != bar.get_value():
            bar.set_value(f)
            bar.set_fill(Cyber.hp_color(f))
        if not bar.is_visible():
            bar.set_visible(True)
    def sync_projectiles(self):
        now = self.game.get_time()
        for p in self.game.get_combat().get_projectiles():
            s = self.projectile_sprites.get(p)
            if s is None:
                s = ProjectileSprites.create(p)
                _j_put(self.projectile_sprites, p, s)
                self.projectile_layer.add(s)
            s.sync(p, now)
        it = _j_iter(_j.entry_set(self.projectile_sprites))
        while it.has_next():
            en = it.next()
            if not en[0].is_alive():
                self.projectile_layer.remove(en[1])
                it.remove()
    def update_lod(self):
        """Picks the level of detail for this frame from the number of sprites on screen (with hysteresis)."""
        if WorldView.LOD_FORCED >= 0:
            self.lod = WorldView.LOD_FORCED
            return
        load = (len(self.enemy_sprites) + _j.idiv(len(self.tower_sprites), 2))
        want = (2 if (load >= WorldView.LOD_FINE_LOAD) else (1 if (load >= WorldView.LOD_DECOR_LOAD) else 0))
        if want > self.lod:
            self.lod = want
        elif (self.lod == 2) and (load < (WorldView.LOD_FINE_LOAD * 0.8)):
            self.lod = (1 if (load >= WorldView.LOD_DECOR_LOAD) else 0)
        elif (self.lod == 1) and (load < (WorldView.LOD_DECOR_LOAD * 0.8)):
            self.lod = 0
        self.lod = max(self.lod, GraphicsSettings.get().quality().min_lod)
    def get_lod(self):
        """Current level of detail (0 = full detail)."""
        return self.lod
    def effect_cap(self):
        """Effect cap for the current level of detail (applies separately to legacy and animated effects)."""
        return WorldView.MAX_EFFECTS if (self.lod == 0) else (_j.idiv((WorldView.MAX_EFFECTS * 5), 8) if (self.lod == 1) else _j.idiv((WorldView.MAX_EFFECTS * 3), 8))
    def effect(self, o, ev, base):
        e = (WorldView.Effect() if (len(self.effect_pool) == 0) else self.effect_pool.pop(0))
        return e.set(o, ev, base)
    def pooled_oval(self, x, y, w, h, fill, outline):
        """A pooled (or new) oval in the effect layer, configured like Ui#oval."""
        o = (self.oval_pool.pop(0) if self.oval_pool else None)
        if o is None:
            o = Ui.oval(x, y, w, h, fill, outline)
            self.effect_layer.add(o)
            return o
        o.set_bounds(x, y, w, h)
        o.set_filled((fill is not None))
        if fill is not None:
            o.set_fill_color(fill)
        o.set_color((outline if (outline is not None) else (fill if (fill is not None) else Ui.TEXT)))
        o.set_visible(True)
        return o
    def pooled_line(self, a, b, col):
        l = (self.line_pool.pop(0) if self.line_pool else None)
        if l is None:
            l = GLine(a.x, a.y, b.x, b.y)
            self.effect_layer.add(l)
        else:
            l.set_start_point(a.x, a.y)
            l.set_end_point(b.x, b.y)
            l.set_visible(True)
        l.set_color(col)
        return l
    def pooled_label(self, text, f, col):
        l = (self.label_pool.pop(0) if self.label_pool else None)
        if l is None:
            l = Ui.label(text, 0, 0, f, col)
            self.effect_layer.add(l)
            return l
        l.set_label(text)
        l.set_font(f)
        l.set_color(col)
        l.set_visible(True)
        return l
    def recycle(self, e):
        """Hides a finished legacy effect and returns it and its object to the pools."""
        e.obj.set_visible(False)
        if isinstance(e.obj, GOval):
            self.oval_pool.insert(0, e.obj)
        elif isinstance(e.obj, GLine):
            self.line_pool.insert(0, e.obj)
        elif isinstance(e.obj, GLabel):
            self.label_pool.insert(0, e.obj)
        else:
            self.effect_layer.remove(e.obj)
        e.obj = None
        e.ev = None
        self.effect_pool.insert(0, e)
    def consume_events(self):
        cap = self.effect_cap()
        for ev in self.game.drain_events():
            AudioManager.event(ev)
            if (ev.kind is VisualEvent.Kind.EXPLOSION) or (ev.kind is VisualEvent.Kind.ABILITY):
                self.glow.flash(ev.a, ev.radius, ev.rgb)
                if ev.radius >= 70:
                    self.shake.kick((0.12 if (ev.kind is VisualEvent.Kind.EXPLOSION) else 0.08))
            elif ev.kind is VisualEvent.Kind.PHASE:
                self.shake.kick(0.5)
            if ((len(self.effects) >= cap) and (ev.kind is not VisualEvent.Kind.PHASE)) and (ev.kind is not VisualEvent.Kind.BANNER):
                continue
            if (((ev.kind is VisualEvent.Kind.BEAM) or (ev.kind is VisualEvent.Kind.CHAIN)) or (ev.kind is VisualEvent.Kind.HIT)) or (ev.kind is VisualEvent.Kind.EXPLOSION):
                if len(self.animated) >= cap:
                    continue
                fx = ProjectileSprites.create_attack_effect(ev)
                if fx is not None:
                    self.effect_layer.add(fx)
                    _j_add(self.animated, fx)
                    continue
            if ev.kind is VisualEvent.Kind.ABILITY:
                self.fx.on_ability_event(ev)
            col = Ui.c(ev.rgb)
            o = None
            _sw1 = ev.kind
            if _sw1 is VisualEvent.Kind.BEAM or _sw1 is VisualEvent.Kind.CHAIN:
                o = self.pooled_line(ev.a, ev.b, col)
            elif _sw1 is VisualEvent.Kind.HIT:
                o = self.pooled_oval((ev.a.x - ev.radius), (ev.a.y - ev.radius), (ev.radius * 2), (ev.radius * 2), Ui.with_alpha(col, 200), None)
            elif _sw1 is VisualEvent.Kind.EXPLOSION or _sw1 is VisualEvent.Kind.ABILITY or _sw1 is VisualEvent.Kind.TELEPORT or _sw1 is VisualEvent.Kind.DEATH or _sw1 is VisualEvent.Kind.SPLIT or _sw1 is VisualEvent.Kind.PHASE:
                o = self.pooled_oval((ev.a.x - 4), (ev.a.y - 4), 8, 8, (Ui.with_alpha(col, 90) if (ev.kind is VisualEvent.Kind.EXPLOSION) else None), col)
            elif _sw1 is VisualEvent.Kind.TEXT:
                l = self.pooled_label(ev.text, Cyber.mono(Font.BOLD, 13), col)
                l.set_location((ev.a.x - (l.get_width() / 2)), ev.a.y)
                o = l
                pass  # break
            elif _sw1 is VisualEvent.Kind.BANNER:
                self.screen.flash_banner(ev.text, col, ev.duration)
            else:
                pass
            if ev.kind is VisualEvent.Kind.PHASE:
                l = self.pooled_label(ev.text, Cyber.display(Font.BOLD, 36), col)
                l.set_location(_j.dmax(8, _j.dmin(((GameMap.WIDTH - l.get_width()) - 8), (ev.a.x - (l.get_width() / 2)))), _j.dmax((l.get_height() + 4), (ev.a.y - 60)))
                _j_add(self.effects, self.effect(l, VisualEvent.text(ev.a, ev.text, ev.rgb), col))
            if o is not None:
                _j_add(self.effects, self.effect(o, ev, col))
    def step_effects(self, dt):
        for i in range((len(self.effects) - 1), -1, -1):
            e = self.effects[i]
            e.t += dt
            f = _j.dmin(1, (e.t / e.ev.duration))
            if f >= 1:
                last = (len(self.effects) - 1)
                _j_set(self.effects, i, self.effects[last])
                self.effects.pop(last)
                self.recycle(e)
                continue
            alpha = _j.to_int((255 * (1 - f)))
            _sw2 = e.ev.kind
            if _sw2 is VisualEvent.Kind.EXPLOSION or _sw2 is VisualEvent.Kind.ABILITY or _sw2 is VisualEvent.Kind.TELEPORT or _sw2 is VisualEvent.Kind.DEATH or _sw2 is VisualEvent.Kind.SPLIT or _sw2 is VisualEvent.Kind.PHASE:
                r = (e.ev.radius * ((0.2 + (0.8 * f)) if (e.ev.kind is VisualEvent.Kind.ABILITY) else (0.3 + (0.7 * f))))
                ov = e.obj
                ov.set_bounds((e.ev.a.x - r), (e.ev.a.y - r), (2 * r), (2 * r))
                ov.set_color(Ui.with_alpha(e.base, alpha))
                if ov.is_filled():
                    ov.set_fill_color(Ui.with_alpha(e.base, _j.idiv(alpha, 3)))
                pass  # break
            elif _sw2 is VisualEvent.Kind.TEXT:
                e.obj.move(0, ((-30) * dt))
                e.obj.set_color(Ui.with_alpha(e.base, alpha))
            else:
                e.obj.set_color(Ui.with_alpha(e.base, alpha))
        for i in range((len(self.animated) - 1), -1, -1):
            a = self.animated[i]
            if not a.step(dt):
                self.effect_layer.remove(a)
                self.animated.pop(i)
    def sync_map_fx(self):
        self.pulses.set_time(self.time)
        if isinstance(self.map, SiliconCircuit):
            sc = self.map
            for i in range(len(self.pad_fill)):
                c = sc.get_pad_charge(i)
                self.pad_fill[i].set_fill_color(Ui.c(0x7fd8a8, _j.to_int((20 + (120 * c)))))
            lane = sc.get_shorted_lane()
            for o in self.short_fx:
                self.map_fx.remove(o)
            self.short_fx.clear()
            if lane >= 0:
                r = self.map.get_routes()[lane]
                w = r.get_waypoints()
                i = 0
                while (i + 1) < len(w):
                    p = self.segment(w[i], w[(i + 1)], GameMap.TRACK_HALF_WIDTH, Ui.c(0xffffff, _j.to_int(display_settings.calm((90 + (90 * abs(math.sin((self.time * 30))))), 150))))
                    self.map_fx.add(p)
                    _j_add(self.short_fx, p)
                    i += 1
        if self.vent_rect is not None:
            lm = self.map
            f = lm.get_vented_floor()
            self.vent_rect.set_visible((f >= 0))
            if f >= 0:
                band = lm.get_floors()[f]
                self.vent_rect.set_bounds(0, band[0], GameMap.WIDTH, (band[1] - band[0]))
                self.vent_rect.set_fill_color(Ui.c(0xff6a00, _j.to_int(display_settings.calm((35 + (25 * math.sin((self.time * 4)))), 45))))
        if not (len(self.hazard_fx) == 0):
            dc = self.map
            active = dc.get_active_hazard()
            warned = dc.get_warned_hazard()
            for i in range(len(self.hazard_fx)):
                on = ((i == active) or (i == warned))
                col = None
                if i == active:
                    col = Ui.c(dc.get_hazards()[i].rgb, _j.to_int(display_settings.calm((70 + (45 * math.sin((self.time * 9)))), 100)))
                elif i == warned:
                    col = Ui.c(0xffd23b, display_settings.calm((120 if (_j.imod(_j.to_int((self.time * 8)), 2) == 0) else 30), 90))
                for p in self.hazard_fx[i]:
                    p.set_visible(on)
                    if col is not None:
                        p.set_fill_color(col)
                        p.set_color(col)
        if self.storm_rect is not None:
            hc = self.map
            self.storm_rect.set_visible(hc.is_storm_active())
            if hc.is_storm_active():
                self.storm_rect.set_fill_color(Ui.c(0xff8cf0, _j.to_int(display_settings.calm((25 + (25 * abs(math.sin((self.time * 6))))), 35))))
    def sync_overlay(self):
        sel = self.screen.get_selected_tower()
        placing = self.screen.get_placing()
        mouse = self.screen.get_mouse_world()
        hover = None
        if ((placing is not None) and (mouse is not None)) and WorldView.inside_world(mouse):
            r = ((catalog.get(placing).stats_for_tier(0).range * self.map.tower_range_multiplier(self.game, None)) * self.game.get_global_range_multiplier())
            problem = self.game.get_tower_manager().placement_problem(placing, mouse)
            ok = (problem is None)
            col = (Cyber.CYAN if ok else Cyber.bad())
            self.ghost_range.set(mouse.x, mouse.y, r)
            self.ghost_range.set_fill(Cyber.alpha(col, (12 if ok else 22)))
            self.ghost_range.set_line(Cyber.alpha(col, (160 if ok else 220)))
            self.ghost_range.set_dashed((not ok))
            self.ghost_range.set_phase((self.time * 14))
            self.ghost_range.set_visible(True)
            tr = catalog.get(placing).radius
            self.ghost.set(mouse.x, mouse.y, tr)
            self.ghost.set_fill(Cyber.alpha(col, (70 if ok else 100)))
            self.ghost.set_line(col)
            self.ghost.set_visible(True)
            self.ghost_x1.set_visible((not ok))
            self.ghost_x2.set_visible((not ok))
            if not ok:
                self.ghost_x1.set_color(col)
                self.ghost_x2.set_color(col)
                k = (tr * 0.55)
                self.ghost_x1.set_start_point((mouse.x - k), (mouse.y - k))
                self.ghost_x1.set_end_point((mouse.x + k), (mouse.y + k))
                self.ghost_x2.set_start_point((mouse.x - k), (mouse.y + k))
                self.ghost_x2.set_end_point((mouse.x + k), (mouse.y - k))
            self.ghost_plate.set((placing.display_name if ok else problem), (Ui.money(shop.price_of(placing, self.game)) if ok else None), col)
            self.place_plate(self.ghost_plate, mouse, tr)
            self.ghost_plate.set_visible(True)
            self.range_circle.set_visible(False)
            self.next_range_circle.set_visible(False)
        else:
            self.ghost_range.set_visible(False)
            self.ghost.set_visible(False)
            self.ghost_plate.set_visible(False)
            self.ghost_x1.set_visible(False)
            self.ghost_x2.set_visible(False)
            if (sel is not None) and sel.is_alive():
                self.range_circle.set(sel.get_position().x, sel.get_position().y, sel.effective_range(self.game))
                self.range_circle.set_visible(True)
            else:
                self.range_circle.set_visible(False)
            self.sync_next_range(sel)
            if (mouse is not None) and WorldView.inside_world(mouse):
                hover = self.game.get_tower_manager().tower_at(mouse)
        self.sync_reticle(mouse)
        sel_show = (sel if (((sel is not None) and sel.is_alive()) and (placing is None)) else None)
        self.show_plate(self.select_plate, sel_show)
        self.show_plate(self.hover_plate, (hover if ((hover is not None) and (hover is not sel_show)) else None))
    def sync_next_range(self, sel):
        """While the UPGRADE button is hovered: the next tier's range as a dashed yellow ring beside the current one."""
        side = self.screen.get_side_panel()
        up = (side.upgrade_hover_tower() if ((side is not None) and (not self.game.is_reverse())) else None)
        on = ((up is not None) and (up is sel))
        self.next_range_circle.set_visible(on)
        if on:
            self.next_range_circle.set(sel.get_position().x, sel.get_position().y, intel.next_range(self.game, sel))
            self.next_range_circle.set_phase((self.time * 14))
    def sync_reticle(self, mouse):
        """Targeting-mode reticle: snaps to the spot the sim will use (the nearest track bend within the ability's snap range
if it has one, otherwise the nearest point on the track) and previews the effect radius."""
        caster = self.screen.get_targeting_tower()
        on = (((((caster is not None) and caster.is_alive()) and (caster.get_ability() is not None)) and (mouse is not None)) and WorldView.inside_world(mouse))
        self.reticle_radius.set_visible(on)
        self.reticle_dot.set_visible(on)
        self.reticle_h.set_visible(on)
        self.reticle_v.set_visible(on)
        self.reticle_link.set_visible(on)
        self.reticle_plate.set_visible(on)
        if not on:
            return
        a = caster.get_ability()
        at = None
        bend = False
        if a.has('snapRange'):
            bends = self.game.get_effects().bends_in_range(mouse, a.p('snapRange'))
            if not (len(bends) == 0):
                at = bends[0].position
                bend = True
        if at is None:
            tp = self.game.get_effects().nearest_track_point(mouse)
            if tp is not None:
                at = tp.position
        if at is None:
            self.reticle_radius.set_visible(False)
            self.reticle_dot.set_visible(False)
            self.reticle_h.set_visible(False)
            self.reticle_v.set_visible(False)
            self.reticle_link.set_visible(False)
            self.reticle_plate.set_visible(False)
            return
        col = Ui.c(caster.get_type().primary_rgb)
        col = Cyber.lerp(col, Cyber.YELLOW, 0.5)
        r = a.p('radius', 60)
        self.reticle_radius.set(at.x, at.y, r)
        self.reticle_radius.set_fill(Cyber.alpha(col, 20))
        self.reticle_radius.set_line(Cyber.alpha(col, 220))
        self.reticle_radius.set_phase((self.time * 18))
        pr = (11 + (2 * math.sin((self.time * 8))))
        self.reticle_dot.set(at.x, at.y, pr)
        self.reticle_dot.set_line(col)
        k = (pr + 8)
        self.reticle_h.set_start_point((at.x - k), at.y)
        self.reticle_h.set_end_point((at.x + k), at.y)
        self.reticle_v.set_start_point(at.x, (at.y - k))
        self.reticle_v.set_end_point(at.x, (at.y + k))
        self.reticle_h.set_color(col)
        self.reticle_v.set_color(col)
        self.reticle_link.set_start_point(mouse.x, mouse.y)
        self.reticle_link.set_end_point(at.x, at.y)
        self.reticle_plate.set(a.name, ('snaps to track bend' if bend else 'on the track'), col)
        self.place_plate(self.reticle_plate, at, _j.dmax(r, pr))
    def show_plate(self, p, t):
        if t is None:
            p.set_visible(False)
            return
        ty = t.get_type()
        p.set(ty.display_name, t.get_tier_label(), Cyber.lerp(Ui.c(ty.primary_rgb), Color.WHITE, 0.35))
        self.place_plate(p, t.get_position(), t.get_radius())
        p.set_visible(True)
    def place_plate(self, p, c, r):
        """Puts a plate above (or below, near the top edge) a circle, clamped inside the world."""
        w = p.get_plate_width()
        x = _j.dmax(4, _j.dmin(((GameMap.WIDTH - w) - 4), (c.x - (w / 2))))
        y = (((c.y - r) - Nameplate.HEIGHT) - 12)
        if y < 4:
            y = ((c.y + r) + 12)
        y = _j.dmin(y, ((GameMap.HEIGHT - Nameplate.HEIGHT) - 4))
        p.place(x, y)
    def set_dock(self, dock):
        """Reserves dock logical px under the HUD for the boss dock by shrinking the playfield uniformly."""
        self.view_dock = _j.dmax(0, _j.dmin(170, dock))
        self.view_scale = ((Ui.WORLD_H - self.view_dock) / Ui.WORLD_H)
    def to_logical(self, w):
        """Inverse of #toWorld: the logical point {x, y} where world point w is drawn (boss dock / strip aware)."""
        off_x = ((Ui.WORLD_W - (GameMap.WIDTH * self.view_scale)) / 2)
        return [((Ui.WORLD_X + off_x) + (w.x * self.view_scale)), ((Ui.WORLD_Y + self.view_dock) + (w.y * self.view_scale))]
    def to_world(self, lx, ly):
        """Maps a logical point (screen layout space) into world coordinates, or null outside the playfield."""
        off_x = ((Ui.WORLD_W - (GameMap.WIDTH * self.view_scale)) / 2)
        p = Vec((((lx - Ui.WORLD_X) - off_x) / self.view_scale), (((ly - Ui.WORLD_Y) - self.view_dock) / self.view_scale))
        return p if WorldView.inside_world(p) else None
    def paint(self, g):
        g2 = g.create()
        try:
            Cyber.quality(g2)
            off_x = ((Ui.WORLD_W - (GameMap.WIDTH * self.view_scale)) / 2)
            g2.translate((Ui.WORLD_X + off_x), (Ui.WORLD_Y + self.view_dock))
            g2.translate(self.shake.offset_x(), self.shake.offset_y())
            g2.scale(self.view_scale, self.view_scale)
            g2.clip_rect(0, 0, GameMap.WIDTH, GameMap.HEIGHT)
            prev_lod = Thick.set_level(max(self.lod, WorldView.MIN_DETAIL))
            try:
                super(WorldView, self).paint(g2)
            finally:
                Thick.set_level(prev_lod)
        finally:
            g2.dispose()
    @staticmethod
    def inside_world(p):
        return (((p.x >= 0) and (p.y >= 0)) and (p.x <= GameMap.WIDTH)) and (p.y <= GameMap.HEIGHT)
    def pick_enemy(self, p):
        """Enemy under a world point, or null."""
        best = None
        best_d = _j.MAX_DOUBLE
        for e in self.game.get_enemy_manager().get_enemies():
            d = e.get_position().dist(p)
            if (d <= (e.get_radius() + 6)) and (d < best_d):
                best_d = d
                best = e
        return best


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.audio.audio_manager import AudioManager  # noqa: E402
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.glow_layer import GlowLayer  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402
from lindefense.ui import intel  # noqa: E402
from lindefense.ui.intrusion_fx import IntrusionFx  # noqa: E402
from lindefense.ui.map_art import MapArt  # noqa: E402
from lindefense.ui.nameplate import Nameplate  # noqa: E402
from lindefense.ui.screen_shake import ScreenShake  # noqa: E402
from lindefense.ui.sprites.sprite_factory import SpriteFactory  # noqa: E402
from lindefense.ui.sprites.thick import Thick  # noqa: E402
from lindefense.ui.sprites.towers.projectile_sprites import ProjectileSprites  # noqa: E402
from lindefense.ui.tower_sprite import TowerSprite  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402
from lindefense.ui.world_fx import WorldFx  # noqa: E402

WorldView.serial_version_uid = 1
WorldView.MAX_EFFECTS = 160
WorldView.LOD_DECOR_LOAD = 60
WorldView.LOD_FINE_LOAD = 150
WorldView.LOD_FORCED = _j.get_integer('lindefense.lod', (-1))
WorldView.TELEGRAPH_RGB = Color(0xff3030)
WorldView.MARKER_INK = Color(0x0a0f1a)
WorldView.HP_BACK = Color(6, 8, 16, 200)
# Minimal style: the world always paints at least at the decorative level of detail, so the purely decorative sprite
# parts (shadows, gloss, sparkles, cracks, small status accents; see Thick#DETAIL_DECOR) are never drawn. Crowded
# fights still raise the level further (#lod).
WorldView.MIN_DETAIL = Thick.DETAIL_DECOR
