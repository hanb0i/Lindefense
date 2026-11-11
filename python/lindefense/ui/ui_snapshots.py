"""Lindefense UiSnapshots (ported from src/lindefense/ui/UiSnapshots.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType
import sys


class UiSnapshots:
    """Developer tool: paints real screens (Hero Store, hero / Zethos info panels and combat, tutorial, catalog) offscreen
into PNGs for visual review, without opening a window. .venv/bin/python -m lindefense.ui.ui_snapshots <dir>."""
    def __init__(self):
        pass
    @staticmethod
    def snap(c, dir_, name):
        img = BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB)
        g = img.create_graphics()
        Cyber.quality(g)
        c.paint(g)
        g.dispose()
        ImageIO.write(img, 'png', _j.File(dir_, _j.cat(name, '.png')))
    @staticmethod
    def main(args):
        _j.set_property('lindefense.nosound', 'true')
        dir_ = _j.File((args[0] if (len(args) > 0) else 'snapshots'))
        dir_.mkdirs()
        g = Game(maps.create(0), 7)
        g.set_hero_limit(_j.MAX_INT)
        g.add_cash(1600, None)
        s = GameScreen(None, g, True)
        s.frame(0.02)
        UiSnapshots.snap(s, dir_, '01_tutorial_start')
        s.toggle_hero_store()
        s.frame(0.02)
        UiSnapshots.snap(s, dir_, '02_hero_store_locked')
        s.buy_hero(TowerType.SUNNY_JOE)
        s.frame(0.02)
        UiSnapshots.snap(s, dir_, '03_hero_store_after_buy')
        s.toggle_hero_store()
        for h in TowerType.heroes():
            g.get_hero_collection().unlock(h)
        g.add_cash(50000, None)
        spots = [Vec(380, 300), Vec(700, 250), Vec(460, 520), Vec(560, 480), Vec(820, 660), Vec(300, 700), Vec(950, 420)]
        types = [TowerType.LOBBER_LUIS, TowerType.CHILLSTIN, TowerType.KAIJU_KAI, TowerType.NIK_SCOPE, TowerType.ZETHOS, TowerType.BLITZ_ARNAV, TowerType.SAGE_AARAV]
        zethos = None
        owen = None
        for i in range(len(types)):
            p = TestKit.buildable_near(g, spots[i], 200)
            t = g.place_tower(types[i], p)
            if t is None:
                print(_j.s(_j.cat('could not place ', types[i], ': ', g.placement_problem(types[i], p))))
                continue
            while g.upgrade_tower(t):
                pass
            if types[i] is TowerType.ZETHOS:
                zethos = t
            if types[i] is TowerType.NIK_SCOPE:
                owen = t
        for k in range(12):
            g.get_wave_manager().start_next_wave()
        for i in range(60 * 6):
            g.step(Game.DT)
            s.frame(Game.DT)
        for t in g.get_tower_manager().get_player_towers():
            t.reset_ability_cooldown()
            g.activate_ability(t)
        for i in range(40):
            g.step(Game.DT)
            s.frame(Game.DT)
        UiSnapshots.snap(s, dir_, '04_battle_abilities')
        for r in g.get_map().get_routes():
            d = 100.0
            while d < r.get_total_length():
                g.get_enemy_manager().spawn_scaled(EnemyType.QUICK_SORT, None, _j.index_of(g.get_map().get_routes(), r), d, 60, 1.0)
                d += 45
        g.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 700, 5, 1.0)
        for t in g.get_tower_manager().get_player_towers():
            t.reset_ability_cooldown()
            g.activate_ability(t)
        for i in range(50):
            g.step(Game.DT)
            s.frame(Game.DT)
        UiSnapshots.snap(s, dir_, '04b_battle_live')
        if zethos is not None:
            s.select_tower(zethos)
            s.frame(0.02)
            s.frame(0.02)
            UiSnapshots.snap(s, dir_, '05_zethos_selected')
        if owen is not None:
            s.select_tower(owen)
            s.frame(0.02)
            s.frame(0.02)
            UiSnapshots.snap(s, dir_, '06_owen_selected')
        s.select_tower(None)
        s.begin_placing(TowerType.ZETHOS)
        s.frame(0.02)
        s.frame(0.02)
        UiSnapshots.snap(s, dir_, '07_shop_zethos_preview')
        s.begin_placing(None)
        s.toggle_hero_store()
        s.frame(0.02)
        UiSnapshots.snap(s, dir_, '08_hero_store_deployed')
        c = CatalogScreen(None)
        c.frame(0.1)
        UiSnapshots.snap(c, dir_, '09_catalog_enemies')
        c.set_tab(CatalogScreen.Tab.BOSSES)
        c.select(4)
        c.frame(0.1)
        UiSnapshots.snap(c, dir_, '10_catalog_boss')
        c.set_tab(CatalogScreen.Tab.TOWERS)
        c.select(3)
        c.frame(0.1)
        UiSnapshots.snap(c, dir_, '11_catalog_zethos')
        c.set_tab(CatalogScreen.Tab.TOWERS)
        c.select(0)
        c.frame(0.1)
        UiSnapshots.snap(c, dir_, '12_catalog_gemini')
        c.set_tab(CatalogScreen.Tab.HEROES)
        c.select(0)
        c.frame(0.1)
        UiSnapshots.snap(c, dir_, '13_catalog_brad')
        print(_j.s(_j.cat('snapshots written to ', dir_.get_absolute_path())))
        sys.exit(0)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.tools.snapshots import TestKit  # noqa: E402  (Java: lindefense.test.TestKit)
from lindefense.ui.catalog_screen import CatalogScreen  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.game_screen import GameScreen  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402


if __name__ == "__main__":
    import sys
    UiSnapshots.main(sys.argv[1:])
