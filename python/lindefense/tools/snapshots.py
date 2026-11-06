"""Developer tool: paints real screens offscreen into PNGs for visual review (no window).

python -m lindefense.tools.snapshots [out_dir] [scale]
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("LINDEFENSE_NOSOUND", "1")

import skia  # noqa: E402

from lindefense.ui.jawt import Graphics2D, reset_canvas_state  # noqa: E402


def render(compound, path, scale=2.0, w=1600, h=1000):
    surf = skia.Surface.MakeRasterN32Premul(int(w * scale), int(h * scale))
    cv = surf.getCanvas()
    cv.clear(0xFF05070F)
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.scale(scale, scale)
    compound.paint(g)
    reset_canvas_state(cv)
    surf.makeImageSnapshot().save(path, skia.kPNG)


def buildable_near(g, target, radius):
    import math
    from lindefense.sim.vec import Vec
    best, best_d = None, float("inf")
    for dx in range(-int(radius), int(radius) + 1, 5):
        for dy in range(-int(radius), int(radius) + 1, 5):
            p = Vec(target.x + dx, target.y + dy)
            d = math.hypot(dx, dy)
            if d > radius or d >= best_d or not g.get_map().is_buildable(p, 20):
                continue
            ok = all(t.get_position().dist(p) >= t.get_radius() + 20 for t in g.get_tower_manager().get_towers())
            if ok:
                best, best_d = p, d
    return best if best is not None else target


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    out = args[0] if args else "snapshots"
    scale = float(args[1]) if len(args) > 1 else 2.0
    os.makedirs(out, exist_ok=True)
    from lindefense.map import maps
    from lindefense.sim.game import Game
    from lindefense.sim.vec import Vec
    from lindefense.tower.tower_type import TowerType
    from lindefense.enemy.types import EnemyType
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.catalog_screen import CatalogScreen

    g = Game(maps.create(0), 7)
    g.set_hero_limit(2 ** 31 - 1)
    g.add_cash(1600, None)
    s = GameScreen(None, g, True)
    s.frame(0.02)
    render(s, os.path.join(out, "01_tutorial_start.png"), scale)
    s.toggle_hero_store()
    s.frame(0.02)
    render(s, os.path.join(out, "02_hero_store_locked.png"), scale)
    s.buy_hero(TowerType.SUNNY_JOE)
    s.frame(0.02)
    render(s, os.path.join(out, "03_hero_store_after_buy.png"), scale)
    s.toggle_hero_store()
    for h in TowerType.heroes():
        g.get_hero_collection().unlock(h)
    g.add_cash(50000, None)
    spots = [Vec(380, 300), Vec(700, 250), Vec(460, 520), Vec(560, 480), Vec(820, 660), Vec(300, 700), Vec(950, 420)]
    types = [TowerType.LOBBER_LUIS, TowerType.CHILLSTIN, TowerType.KAIJU_KAI, TowerType.NIK_SCOPE, TowerType.ZETHOS,
             TowerType.BLITZ_ARNAV, TowerType.SAGE_AARAV]
    zethos = owen = None
    for p, t in zip(spots, types):
        q = buildable_near(g, p, 200)
        tw = g.place_tower(t, q)
        if tw is None:
            print("could not place", t, g.placement_problem(t, q))
            continue
        while g.upgrade_tower(tw):
            pass
        if t is TowerType.ZETHOS:
            zethos = tw
        if t is TowerType.NIK_SCOPE:
            owen = tw
    for _ in range(12):
        g.get_wave_manager().start_next_wave()
    for _ in range(60 * 6):
        g.step(Game.DT)
        s.frame(Game.DT)
    for t in g.get_tower_manager().get_player_towers():
        t.reset_ability_cooldown()
        g.activate_ability(t)
    for _ in range(40):
        g.step(Game.DT)
        s.frame(Game.DT)
    render(s, os.path.join(out, "04_battle_abilities.png"), scale)
    for ri, r in enumerate(g.get_map().get_routes()):
        d = 100.0
        while d < r.get_total_length():
            g.get_enemy_manager().spawn_scaled(EnemyType.QUICK_SORT, None, ri, d, 60, 1.0)
            d += 45
    g.get_enemy_manager().spawn_scaled(EnemyType.BELLARMINE_COLLEGE_PREP, None, 0, 700, 5, 1.0)
    for t in g.get_tower_manager().get_player_towers():
        t.reset_ability_cooldown()
        g.activate_ability(t)
    for _ in range(50):
        g.step(Game.DT)
        s.frame(Game.DT)
    render(s, os.path.join(out, "04b_battle_live.png"), scale)
    if zethos is not None:
        s.select_tower(zethos)
        s.frame(0.02)
        s.frame(0.02)
        render(s, os.path.join(out, "05_zethos_selected.png"), scale)
    if owen is not None:
        s.select_tower(owen)
        s.frame(0.02)
        s.frame(0.02)
        render(s, os.path.join(out, "06_owen_selected.png"), scale)
    s.select_tower(None)
    s.begin_placing(TowerType.ZETHOS)
    s.frame(0.02)
    s.frame(0.02)
    render(s, os.path.join(out, "07_shop_zethos_preview.png"), scale)
    s.begin_placing(None)
    s.toggle_hero_store()
    s.frame(0.02)
    render(s, os.path.join(out, "08_hero_store_deployed.png"), scale)
    c = CatalogScreen(None)
    c.frame(0.1)
    render(c, os.path.join(out, "09_catalog_enemies.png"), scale)
    c.set_tab(CatalogScreen.Tab.BOSSES)
    c.select(4)
    c.frame(0.1)
    render(c, os.path.join(out, "10_catalog_boss.png"), scale)
    c.set_tab(CatalogScreen.Tab.TOWERS)
    c.select(3)
    c.frame(0.1)
    render(c, os.path.join(out, "11_catalog_zethos.png"), scale)
    print("snapshots written to", os.path.abspath(out))


if __name__ == "__main__":
    main()
