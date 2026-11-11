"""Lindefense TowerGallery (ported from src/lindefense/ui/sprites/towers/TowerGallery.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.combat.visual_event import VisualEvent
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower import Tower
from lindefense.tower.tower_type import TowerType
from lindefense.ui.ui import Ui


class TowerGallery(GraphicsProgram):
    """Visual self-check for the tower art. Run with GALLERY_PAGE=towers
(default) for a grid of every tower at all five tiers drawn through real
TowerSprites, or GALLERY_PAGE=fx for an aiming / recoil
demo, every projectile in flight at tier 0 and tier 4, shop icons and
looping BEAM / CHAIN / HIT / EXPLOSION effects."""
    def __init__(self):
        self.fx_layer = None
        self.clock = 0.0
        self.last_fire = 0.0
        self.last_fx = 0.0
        self.fx_page = False
        self.shot_taken = False
        GraphicsProgram.__init__(self)
        self.sprites = _j.ArrayList()
        self.towers = _j.ArrayList()
        self.aimers = _j.ArrayList()
        self.shots = _j.ArrayList()
        self.shot_paths = _j.ArrayList()
        self.fx = _j.ArrayList()
        pass
    def init(self):
        self.fx_page = ('fx' == _j.get_property('gallery.page', 'towers'))
        self.set_size(1500, 1060)
        self.set_title(_j.cat('Lindefense tower gallery - ', ('projectiles & effects' if self.fx_page else 'towers x tiers')))
    def run(self):
        canvas = self.get_g_canvas()
        canvas.set_background(TowerGallery.BG)
        canvas.set_auto_repaint_flag(False)
        if self.fx_page:
            self.build_fx()
        else:
            self.build_towers()
        canvas.repaint()
        timer = Timer(33, _j.Fn(lambda e: self.tick(0.033)))
        timer.start()
    def label(self, s, x, y, f):
        l = GLabel(s, x, y)
        l.set_font(f)
        l.set_color(Color.WHITE)
        self.add(l)
    def build_towers(self):
        all_ = TowerType.values()
        rows = _j.idiv((len(all_) + 1), 2)
        cell_w = 112.0
        cell_h = 92.0
        label_w = 150.0
        top = 40.0
        for block in range(2):
            bx = (block * ((label_w + (5 * cell_w)) + 30))
            for t in range(5):
                self.label(_j.cat('Tier ', t), (((bx + label_w) + (t * cell_w)) + 30), 22, TowerGallery.F)
            for i in range(rows):
                idx = ((block * rows) + i)
                if idx >= len(all_):
                    break
                type_ = all_[idx]
                cy = ((top + (i * cell_h)) + (cell_h / 2))
                band = GRect(bx, (top + (i * cell_h)), (label_w + (5 * cell_w)), cell_h)
                band.set_filled(True)
                band.set_fill_color((TowerGallery.BG if (_j.imod(i, 2) == 0) else TowerGallery.BG2))
                band.set_color((TowerGallery.BG if (_j.imod(i, 2) == 0) else TowerGallery.BG2))
                self.add(band)
                self.label(type_.display_name, (bx + 8), (cy + 4), TowerGallery.F)
                def_ = catalog.get(type_)
                for t in range(5):
                    cx = (((bx + label_w) + (t * cell_w)) + (cell_w / 2))
                    tower = Tower(def_, Vec(cx, (cy - 6)), t, False, 0, None)
                    s = TowerSprite(tower)
                    self.add(s)
                    _j_add(self.sprites, s)
                    _j_add(self.towers, tower)
    def build_fx(self):
        self.label('Aim + recoil demo (TowerArt.aim / setFiring)', 20, 22, TowerGallery.F)
        demo = [TowerType.CLAUDE, TowerType.KAIJU_KAI, TowerType.DEEPSEEK, TowerType.KIMI, TowerType.COHERE, TowerType.GEMINI, TowerType.LLAMA, TowerType.ZETHOS]
        demo_tier = [2, 4, 3, 1, 4, 2, 3, 4]
        for i in range(len(demo)):
            a = TowerArtFactory.create(demo[i], demo_tier[i], 20)
            a.set_location((70 + (i * 110)), 85)
            self.add(a)
            _j_add(self.aimers, a)
        self.label('Projectiles: tier 0 row, tier 4 row (one per tower type)', 20, 160, TowerGallery.F)
        all_ = TowerType.values()
        for t in range(2):
            tier = (0 if (t == 0) else 4)
            for i in range(len(all_)):
                type_ = all_[i]
                def_ = catalog.get(type_)
                st = def_.stats_for_tier(tier)
                size = (8 if (st.splash_radius > 0) else (7 if (st.hit.damage >= 5) else 5))
                p = ProjectileSprites.create(type_, tier, st, size, type_.primary_rgb)
                self.add(p)
                _j_add(self.shots, p)
                _j_add(self.shot_paths, [(50 + (i * 66)), (200 + (t * 70)), (i * 0.4)])
                if t == 0:
                    l = GLabel((type_.display_name[0:9] if (len(type_.display_name) > 9) else type_.display_name), ((50 + (i * 66)) - 20), 330)
                    l.set_font(TowerGallery.FS)
                    l.set_color(Color.WHITE)
                    self.add(l)
        self.label('TowerIcons.create(type, tier, 56) for game tiers 0 and 3', 20, 370, TowerGallery.F)
        for t in range(2):
            for i in range(len(all_)):
                cx = (50 + (i * 66))
                cy = (410 + (t * 70))
                box = GRect((cx - 28), (cy - 28), 56, 56)
                box.set_color(Color(0xffffff))
                self.add(box)
                icon = TowerIcons.create(all_[i], (0 if (t == 0) else 3), 56)
                self.add(icon, cx, cy)
        self.label('Attack effects: BEAM, CHAIN, HIT, EXPLOSION (looping)', 20, 540, TowerGallery.F)
        self.fx_layer = GCompound()
        self.add(self.fx_layer)
    def spawn_fx(self):
        cols = [0xe88a4a, 0x4f7cff, 0x20b2aa, 0xffd700, 0xff5fa2, 0x19e6ff]
        c = cols[_j.imod(_j.to_int((self.clock * 7)), len(cols))]
        self.add_fx(VisualEvent.beam(Vec(60, 620), Vec(260, 580), c))
        self.add_fx(VisualEvent.chain(Vec(320, 620), Vec(470, 585), cols[_j.imod(_j.to_int((self.clock * 3)), len(cols))]))
        self.add_fx(VisualEvent.hit(Vec(560, 600), c))
        self.add_fx(VisualEvent.explosion(Vec(700, 600), 45, c))
        self.add_fx(VisualEvent.explosion(Vec(850, 600), 90, 0xffd700))
        self.add_fx(VisualEvent(VisualEvent.Kind.BEAM, Vec(960, 640), Vec(1200, 560), 4, 0x3d3fa8, None, 0.3))
    def add_fx(self, ev):
        a = ProjectileSprites.create_attack_effect(ev)
        if isinstance(a, GObject):
            self.fx_layer.add(a)
            _j_add(self.fx, a)
    def maybe_snapshot(self):
        """Writes the canvas to the PNG named by GALLERY_SHOT once the scene has settled."""
        path = _j.get_property('gallery.shot')
        if ((path is None) or self.shot_taken) or (self.clock < float(_j.get_property('gallery.shotAt', '2.5'))):
            return
        self.shot_taken = True
        try:
            canvas = self.get_g_canvas()
            img = BufferedImage(_j.dmax(1, canvas.get_width()), _j.dmax(1, canvas.get_height()), BufferedImage.TYPE_INT_RGB)
            g = img.create_graphics()
            g.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
            canvas.paint(g)
            g.dispose()
            ImageIO.write(img, 'png', _j.File(path))
            print(_j.s(_j.cat('snapshot written: ', path)))
        except Exception as ex:
            print(_j.s(_j.cat('snapshot failed: ', ex)))
    def tick(self, dt):
        self.clock += dt
        self.maybe_snapshot()
        if not self.fx_page:
            if (self.clock - self.last_fire) > 1.6:
                self.last_fire = self.clock
                for t in self.towers:
                    t.set_last_fire_time(self.clock)
            for s in self.sprites:
                s.sync(None, dt, False)
        else:
            ang = (self.clock * 1.3)
            since = (self.clock - self.last_fire)
            if since > 0.9:
                self.last_fire = self.clock
                since = 0.0
            for a in self.aimers:
                a.aim(ang)
                a.set_firing(since)
                a.animate(self.clock, dt)
            for i in range(len(self.shots)):
                p = self.shot_paths[i]
                a = ((self.clock * 1.5) + p[2])
                x = (p[0] + (math.cos(a) * 16))
                y = (p[1] + (math.sin(a) * 16))
                self.shots[i].place(x, y, (-math.sin(a)), math.cos(a), self.clock)
                self.shots[i].step(dt)
            if (self.clock - self.last_fx) > 0.75:
                self.last_fx = self.clock
                self.spawn_fx()
            for i in range((len(self.fx) - 1), -1, -1):
                if not self.fx[i].step(dt):
                    self.fx_layer.remove(self.fx[i])
                    self.fx.pop(i)
        self.get_g_canvas().repaint()
    @staticmethod
    def main(args):
        """Entry point."""
        TowerGallery().start(args)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.projectile_sprites import ProjectileSprites  # noqa: E402
from lindefense.ui.sprites.towers.tower_art_factory import TowerArtFactory  # noqa: E402
from lindefense.ui.sprites.towers.tower_icons import TowerIcons  # noqa: E402
from lindefense.ui.tower_sprite import TowerSprite  # noqa: E402

TowerGallery.serial_version_uid = 1
TowerGallery.BG = Color(0x3f8f4f)
TowerGallery.BG2 = Color(0x4a9c5a)
TowerGallery.F = Ui.body(Font.BOLD, 12)
TowerGallery.FS = Ui.body(Font.PLAIN, 10)


if __name__ == "__main__":
    import sys
    TowerGallery.main(sys.argv[1:])
