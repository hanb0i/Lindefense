"""Lindefense SpriteGallery (ported from src/lindefense/ui/sprites/SpriteGallery.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.boss import Boss
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType
from lindefense.enemy.types import Modifier
from lindefense.enemy.types import StatusEffect
from lindefense.jenum import EnumSet
from lindefense.map.path import Path
import random
import sys


class SpriteGallery(GraphicsProgram):
    """Visual self-check for the sprite package. Lays out every ordinary enemy
type in a grid of states (base, camo, regrow, fortified, all three, two
damage levels and five status cues), loops the death and split effects
underneath, and shows the five bosses large with Palantir in each phase and
while telegraphing. Enemies crawl around small loops so facing is exercised.

Run with GALLERY_SHOTS=/some/dir to have the canvas rendered to
PNG files at a few points in time and then exit; otherwise it runs until the
window is closed. The telegraph state is driven through reflection on
Boss.telegraphRemaining because starting a real surveillance needs a
full Game."""
    class Cell:
        def __init__(self):
            self.e = None
            self.s = None
            self.hit_loop = False
            self.telegraph = None
            pass
    class FxSlot:
        def __init__(self):
            self.e = None
            self.fx = None
            self.g = None
            self.split = False
            self.restart = 0.0
            self.period = 0.0
            pass
    def __init__(self):
        self.t = 0.0
        GraphicsProgram.__init__(self)
        self.cells = _j.ArrayList()
        self.fx = _j.ArrayList()
        pass
    @staticmethod
    def main(args):
        """Entry point."""
        SpriteGallery().start(args)
    def init(self):
        self.set_size(SpriteGallery.W, SpriteGallery.H)
    @staticmethod
    def loop(cx, cy, hw, hh):
        return Path('loop', (cx - hw), (cy - hh), (cx + hw), (cy - hh), (cx + hw), (cy + hh), (cx - hw), (cy + hh), (cx - hw), (cy - hh))
    def place(self, type_, mods, cx, cy, hw, hh, speed_scale):
        p = SpriteGallery.loop(cx, cy, hw, hh)
        e = (Boss(type_, mods, p, 0, 0, 1.0, speed_scale) if type_.is_boss() else Enemy(type_, mods, p, 0, 0, 1.0, speed_scale))
        e.set_distance((random.random() * p.get_total_length()))
        c = SpriteGallery.Cell()
        c.e = e
        c.s = SpriteFactory.create(e)
        self.add(c.s)
        _j_add(self.cells, c)
        return c
    def label(self, text, x, y, size, c):
        l = GLabel(text, x, y)
        l.set_font(Ui.body(Font.PLAIN, size))
        l.set_color(c)
        self.add(l)
    def run(self):
        self.set_background(Color(78, 132, 70))
        canvas = self.get_g_canvas()
        canvas.set_background(Color(78, 132, 70))
        normal = _j.ArrayList()
        for et in EnemyType.values():
            if not et.is_boss():
                _j_add(normal, et)
        none = EnumSet.none_of()
        camo = EnumSet.of(Modifier.CAMO)
        regrow = EnumSet.of(Modifier.REGROW)
        fort = EnumSet.of(Modifier.FORTIFIED)
        all_ = EnumSet.all_of(Modifier)
        for row in range(len(SpriteGallery.ROWS)):
            self.label(SpriteGallery.ROWS[row], 4, ((SpriteGallery.Y0 + (row * SpriteGallery.ROW)) + 4), 10, Color.WHITE)
        for col in range(len(normal)):
            type_ = normal[col]
            n = type_.display_name.replace('Linked List', 'LL').replace(' Sort', '').replace(' Array', 'Arr').replace('Primitive Variable', 'Primitive').replace('Quick Partition', 'QPartition')
            self.label(n, ((SpriteGallery.X0 + (col * SpriteGallery.COL)) - 30), 14, 9, Color.WHITE)
            cx = (SpriteGallery.X0 + (col * SpriteGallery.COL))
            for row in range(len(SpriteGallery.ROWS)):
                cy = (SpriteGallery.Y0 + (row * SpriteGallery.ROW))
                mods = (camo if ((row == 1) or (row == 10)) else (regrow if (row == 2) else (fort if (row == 3) else (all_ if (row == 4) else none))))
                c = self.place(type_, mods, cx, cy, 10, 5, 0.18)
                e = c.e
                _sw1 = row
                if _sw1 == 5:
                    e.take_damage((e.get_max_hp() * 0.5), 0)
                    c.hit_loop = True
                    e.set_shell_jump_index(1)
                elif _sw1 == 6:
                    e.take_damage((e.get_max_hp() * 0.85), 0)
                    c.hit_loop = True
                    e.set_shell_jump_index(3)
                elif _sw1 == 7:
                    e.apply_status(StatusEffect.Kind.SLOW, 0.5, 1e9)
                elif _sw1 == 8:
                    e.apply_status(StatusEffect.Kind.STUN, 1, 1e9)
                elif _sw1 == 9:
                    e.apply_status(StatusEffect.Kind.MARKED, 0.25, 1e9)
                elif _sw1 == 10:
                    e.apply_status(StatusEffect.Kind.REVEALED, 1, 1e9)
                elif _sw1 == 11:
                    e.apply_status(StatusEffect.Kind.DISRUPTED, 1, 1e9)
                else:
                    pass
                if (type_ is EnemyType.BUCKET_SORT) and (row != 0):
                    n2 = min(6, row)
                    kinds = [EnemyType.PRIMITIVE_VARIABLE, EnemyType.BUBBLE_SORT, EnemyType.STATIC_ARRAY, EnemyType.SINGLY_LINKED_LIST, EnemyType.INSERTION_SORT, EnemyType.MERGE_RUN]
                    for k in range(n2):
                        _j_add(e.get_stored_enemies(), Enemy(kinds[k], none, e.get_route(), 0, 0, 1, 1))
                if ((type_ is EnemyType.DOUBLY_LINKED_LIST) and (row >= 5)) and (row <= 6):
                    k = 0
                    while k < (3 if (row == 5) else 6):
                        e.take_damage(0.001, 0)
                        e.heal(0.001)
                        k += 1
            fy = ((SpriteGallery.Y0 + (len(SpriteGallery.ROWS) * SpriteGallery.ROW)) + 12)
            self.label('death', 4, (fy + 4), 10, Color.WHITE)
            self.label('split', 4, (fy + 58), 10, Color.WHITE)
            d = SpriteGallery.FxSlot()
            d.e = Enemy(type_, none, SpriteGallery.loop(cx, fy, 1, 1), 0, 0, 1, 1)
            d.e.set_distance(1)
            d.period = 0.9
            d.restart = (col * 0.11)
            _j_add(self.fx, d)
            if type_.has_children():
                s = SpriteGallery.FxSlot()
                s.e = Enemy(type_, none, SpriteGallery.loop(cx, (fy + 54), 1, 1), 0, 0, 1, 1)
                s.e.set_distance(1)
                if type_ is EnemyType.BUCKET_SORT:
                    _j_add(s.e.get_stored_enemies(), Enemy(EnemyType.PRIMITIVE_VARIABLE, none, s.e.get_route(), 0, 0, 1, 1))
                    _j_add(s.e.get_stored_enemies(), Enemy(EnemyType.BUBBLE_SORT, none, s.e.get_route(), 0, 0, 1, 1))
                    _j_add(s.e.get_stored_enemies(), Enemy(EnemyType.QUICK_PARTITION, none, s.e.get_route(), 0, 0, 1, 1))
                s.split = True
                s.period = 1.0
                s.restart = (0.3 + (col * 0.11))
                _j_add(self.fx, s)
        sep = GLine(0, ((SpriteGallery.Y0 + (len(SpriteGallery.ROWS) * SpriteGallery.ROW)) + 92), SpriteGallery.W, ((SpriteGallery.Y0 + (len(SpriteGallery.ROWS) * SpriteGallery.ROW)) + 92))
        sep.set_color(Color(255, 255, 255, 120))
        self.add(sep)
        by = ((SpriteGallery.Y0 + (len(SpriteGallery.ROWS) * SpriteGallery.ROW)) + 205)
        self.label(_j.cat('bosses: Bellarmine (MOAB) | SW Resource Consultant (BFB) | 3Com (ZOMG) | Lockheed Martin (DDT, camo; below: revealed + 70% dmg) | ', 'Palantir phase 0 / phase 1 / phase 2 + telegraph | Bellarmine fortified 80% dmg | Lockheed death loop'), 4, (by - 110), 10, Color.WHITE)
        self.place(EnemyType.BELLARMINE_COLLEGE_PREP, none, 80, by, 20, 10, 0.5)
        self.place(EnemyType.SW_RESOURCE_CONSULTANT, none, 215, by, 20, 10, 0.5)
        self.place(EnemyType.THREE_COM, none, 380, by, 20, 10, 0.5)
        self.place(EnemyType.LOCKHEED_MARTIN, none, 540, (by - 55), 20, 8, 0.3)
        lr = self.place(EnemyType.LOCKHEED_MARTIN, none, 540, (by + 65), 20, 8, 0.3)
        lr.e.apply_status(StatusEffect.Kind.REVEALED, 1, 1e9)
        lr.e.take_damage((lr.e.get_max_hp() * 0.7), 0)
        lr.hit_loop = True
        self.place(EnemyType.PALANTIR, none, 730, by, 20, 8, 0.6)
        p1 = self.place(EnemyType.PALANTIR, none, 940, by, 20, 8, 0.6)
        p1.e.take_damage((p1.e.get_max_hp() * 0.5), 0)
        p1.e.update_phase()
        p2 = self.place(EnemyType.PALANTIR, none, 1150, by, 20, 8, 0.6)
        p2.e.take_damage((p2.e.get_max_hp() * 0.8), 0)
        p2.e.update_phase()
        p2.telegraph = p2.e
        bf = self.place(EnemyType.BELLARMINE_COLLEGE_PREP, fort, 1320, (by - 40), 20, 10, 0.5)
        bf.e.take_damage((bf.e.get_max_hp() * 0.8), 0)
        bf.hit_loop = True
        bd = SpriteGallery.FxSlot()
        bd.e = Boss(EnemyType.LOCKHEED_MARTIN, none, SpriteGallery.loop(1340, (by + 60), 1, 1), 0, 0, 1, 1)
        bd.e.set_distance(1)
        bd.period = 3.0
        bd.restart = 0.5
        _j_add(self.fx, bd)
        pd = SpriteGallery.FxSlot()
        pd.e = Boss(EnemyType.PALANTIR, none, SpriteGallery.loop(730, by, 1, 1), 0, 0, 1, 1)
        pd.e.set_distance(1)
        pd.period = 7.0
        pd.restart = 4.0
        _j_add(self.fx, pd)
        shots = _j.get_property('gallery.shots')
        shot_times = [1.2, 2.0, 2.6, 3.3, 5.3, 6.4, 8.2]
        shot = 0
        dt = (1.0 / 60)
        last = _j.nano_time()
        while True:
            self.t += dt
            for c in self.cells:
                e = c.e
                if e.advance(dt, 1.0):
                    e.set_distance(0)
                if c.hit_loop and (_j.to_int((self.t / 1.5)) != _j.to_int(((self.t - dt) / 1.5))):
                    e.take_damage(0.001, self.t)
                    e.heal(0.001)
                if c.telegraph is not None:
                    SpriteGallery.set_telegraph(c.telegraph, _j.dmax(0, (Boss.TELEGRAPH_TIME - _j.fmod(self.t, 4.2))))
                c.s.sync(e, self.t)
            for f in self.fx:
                if f.fx is not None:
                    if not f.fx.step(dt):
                        self.remove(f.g)
                        f.fx = None
                        f.restart = (self.t + f.period)
                elif self.t >= f.restart:
                    f.fx = (SpriteFactory.create_split_effect(f.e) if f.split else SpriteFactory.create_death_effect(f.e))
                    f.g = f.fx
                    self.add(f.g)
            if ((shots is not None) and (shot < len(shot_times))) and (self.t >= shot_times[shot]):
                SpriteGallery.capture(canvas, _j.File(shots, _j.cat('gallery-', shot, '.png')))
                shot += 1
                if shot == len(shot_times):
                    self.pause(400)
                    sys.exit(0)
            now = _j.nano_time()
            sleep = (16 - ((now - last) / 1e6))
            last = now
            self.pause(_j.dmax(1, sleep))
    @staticmethod
    def set_telegraph(b, remaining):
        try:
            f = Boss
            f.set_accessible(True)
            f.set_double(b, remaining)
        except Exception as ex:
            pass
    @staticmethod
    def capture(canvas, file):
        try:
            file.get_parent_file().mkdirs()
            img = BufferedImage(_j.dmax(1, (canvas.get_width() * 2)), _j.dmax(1, (canvas.get_height() * 2)), BufferedImage.TYPE_INT_RGB)
            g = img.create_graphics()
            g.set_rendering_hint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
            g.set_rendering_hint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON)
            g.scale(2, 2)
            canvas.paint(g)
            g.dispose()
            ImageIO.write(img, 'png', file)
            print(_j.s(_j.cat('wrote ', file.get_absolute_path())))
        except Exception as ex:
            print(_j.s(_j.cat('capture failed: ', ex)))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.sprite_factory import SpriteFactory  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402

SpriteGallery.W = 1440
SpriteGallery.H = 1000
SpriteGallery.X0 = 72
SpriteGallery.COL = 76
SpriteGallery.Y0 = 46
SpriteGallery.ROW = 54
SpriteGallery.ROWS = ['base', 'camo', 'regrow', 'fortified', 'all three', 'hp 50%', 'hp 15%', 'slowed', 'stunned', 'marked', 'revealed', 'disrupted']


if __name__ == "__main__":
    import sys
    SpriteGallery.main(sys.argv[1:])
