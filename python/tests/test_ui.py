"""UI-layer tests (ports of GraphicsTests, AssetTests, HeadlessTests.shopLayout, HeroStoreTests.uiText / tutorialScript /
catalogEntries, the ShopLayout part of zethosShop, and ReverseModeTests.uiRouting). Screens are built and painted offscreen;
nothing opens a window."""
import os

import pytest
import skia

from kit import buildable_near, new_game, run_seconds, spawn_at
from lindefense import assets, prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai.units import AttackUnit
from lindefense.audio.sfx import Sfx
from lindefense.audio.track import Track
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.misc import HeroCollection
from lindefense.sim.vec import Vec
from lindefense.tower import catalog
from lindefense.tower.tower_type import Faction, TowerType as T
from lindefense.ui.attack_panel import AttackPanel
from lindefense.ui.catalog_screen import CatalogScreen
from lindefense.ui.cyber import Cyber
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.graphics_settings import GraphicsSettings
from lindefense.ui.hero_stat_text import HeroStatText
from lindefense.ui.jawt import BufferedImage, KeyEvent, RenderingHints
from lindefense.ui.jrt import Preferences
from lindefense.ui.map_art import MapArt
from lindefense.ui.shop_layout import ShopLayout
from lindefense.ui.tutorial_script import TutorialScript
from lindefense.ui.ui import Ui

Q = GraphicsSettings.Quality


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


# ---------------------------------------------------------------- GraphicsTests
def test_graphics_presets(check):
    check(Q.HIGH.map_scale(1.0) == 1.0 and Q.MEDIUM.map_scale(1.0) == 1.0, "a 1:1 map bitmap at every preset")
    check(Q.HIGH.map_scale(3.2) == 3.25, "HIGH follows a 5K density (got %s)" % Q.HIGH.map_scale(3.2))
    check(Q.MEDIUM.map_scale(3.2) == 2.5 and Q.LOW.map_scale(3.2) == 1.5, "MEDIUM / LOW cap the map bitmap")
    check(Q.HIGH.map_scale(9) == 4.0, "HIGH caps at 4x")
    check(Q.HIGH.map_scale(0.01) == 0.125, "never below 1/8 scale")
    check(Q.HIGH.map_scale(2.0) == 2.0 and Q.HIGH.map_scale(2.01) == 2.125, "map scale rounds up to 1/8 steps")
    check(Q.HIGH.icon_scale(1.0) == 2 and Q.HIGH.icon_scale(3.1) == 4 and Q.MEDIUM.icon_scale(3.1) == 3 and Q.LOW.icon_scale(3.1) == 2,
          "icons supersample at the device density")
    check(Q.HIGH.interpolation() == RenderingHints.VALUE_INTERPOLATION_BILINEAR
          and Q.LOW.interpolation() == RenderingHints.VALUE_INTERPOLATION_BILINEAR, "bilinear scaling everywhere")
    check(Q.LOW.min_lod >= 1 and Q.MEDIUM.min_lod == 0 and Q.HIGH.min_lod == 0, "LOW always trims detail")
    check(Q.HIGH.vignette and Q.HIGH.screen_shake and Q.HIGH.glow and not Q.MEDIUM.glow and not Q.LOW.screen_shake, "extras are HIGH only")
    check(Q.LOW.next() is Q.MEDIUM and Q.HIGH.next() is Q.LOW, "presets cycle")
    check(Q.parse("high") is Q.HIGH and Q.parse(" Low ") is Q.LOW and Q.parse("ultra") is None, "preset names parse")


def test_graphics_settings(check):
    mem = GraphicsSettings.in_memory()
    check(mem.quality() is Q.HIGH and mem.get_max_fps() == 60, "defaults: HIGH, 60 fps")
    check(mem.frame_delay_ms() == 16, "60 fps = a 16 ms frame timer")
    mem.set_max_fps(100)
    check(mem.get_max_fps() == 120 and mem.frame_delay_ms() == 8, "a requested rate snaps (100 -> 120)")
    check(mem.next_fps() == 30, "frame-rate choices cycle")
    mem.set_quality(None)
    check(mem.quality() is Q.HIGH, "a null preset is ignored")
    node = Preferences.user_root().node("lindefense-test/graphics")
    a = GraphicsSettings(node)
    a.set_quality(Q.LOW)
    a.set_max_fps(120)
    b = GraphicsSettings(node)
    check(b.quality() is Q.LOW and b.get_max_fps() == 120, "quality and frame rate persist")


def test_map_cache_budget(check):
    saved = GraphicsSettings.get()
    GraphicsSettings.set_instance(GraphicsSettings.in_memory())
    try:
        target = BufferedImage(8, 8, BufferedImage.TYPE_INT_RGB)
        for m in range(4):
            g = target.create_graphics()
            g.scale(3.4, 3.4)
            MapArt(maps.create(m)).paint(g)
            check(MapArt.cached_pixels() <= MapArt.CACHE_PIXEL_BUDGET, "map cache within budget after map %d (%d px)" % (m, MapArt.cached_pixels()))
    finally:
        GraphicsSettings.set_instance(saved)


# ---------------------------------------------------------------- AssetTests
def test_assets_exact_case(check):
    root = assets.path("assets")
    check(os.path.isdir(root), "assets folder is found (%s)" % root)
    sfx = set(os.listdir(assets.path("assets/sfx")))
    check(bool(sfx), "assets/sfx lists files")
    for s in Sfx:
        check(s.file + ".wav" in sfx, "sfx file with exact case: %s.wav" % s.file)
    check("CREDITS.md" in sfx, "assets/sfx/CREDITS.md present")
    fonts = set(os.listdir(assets.path("assets/fonts")))
    for f in Cyber.FONT_FILES:
        if f != Cyber.VALORAX_FILE:
            check(f in fonts, "font file with exact case: %s" % f)
    music = set(os.listdir(assets.path("assets/music")))
    wanted = {t.file + ".wav" for t in Track}
    for m in music:
        for w in wanted:
            if m.lower() == w.lower():
                check(m == w, "music file name case: found %r, code expects %r" % (m, w))
    check(len(assets.roots()) >= 1, "Assets has at least one search root")


# ---------------------------------------------------------------- shop layout
def test_shop_layout(check):
    cells = ShopLayout.all_cells()
    check(len(cells) == 18, "ALL view lists the 18 shop towers, got %d" % len(cells))
    order = list(Faction)
    fi, grouped = 0, True
    for c in cells:
        while fi < len(order) and c.faction is not order[fi]:
            fi += 1
        if fi >= len(order):
            grouped = False
    check(grouped and cells[0].faction is Faction.PRIMARY and cells[17].faction is Faction.TITAN, "grouped in faction order")
    check(not any(c.type.is_hero() for c in cells), "heroes never appear in the tower shop")
    check(sum(1 for c in cells if c.first_of_faction) == 5, "five faction headers")
    inside, overlap = True, False
    for i, a in enumerate(cells):
        if a.x < Ui.PANEL_X or a.x + a.w > Ui.PANEL_X + Ui.PANEL_W or a.y < ShopLayout.CARDS_Y or a.y + a.h > ShopLayout.CARDS_BOTTOM:
            inside = False
        for b in cells[i + 1:]:
            if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h:
                overlap = True
    check(inside, "all cells fit inside the sidebar card area")
    check(not overlap, "no overlapping cells")
    for c in cells:
        check(ShopLayout.cell_at(cells, c.x + c.w / 2, c.y + c.h / 2) is c, "cell hit test %s" % c.type)
    check(len(ShopLayout.faction_cells(Faction.TITAN)) == 7, "Titans tab has 7 cards")
    check(ShopLayout.affordable(650, T.GPT) and not ShopLayout.affordable(650, T.COHERE), "affordability at $650")
    check(ShopLayout.shortfall(650, T.COHERE) == 150 and ShopLayout.shortfall(650, T.GPT) == 0, "shortfall amounts")
    check(sum(1 for c in cells if ShopLayout.affordable(Game.START_CASH, c.type)) == 13, "13 of 18 affordable at start")
    check(any(c.type is T.ZETHOS for c in ShopLayout.faction_cells(Faction.PRIMARY)), "Zethos sits in the PRIMARY shop tab")


# ---------------------------------------------------------------- hero store UI text, tutorial, catalog
def test_hero_ui_text(check):
    for h in T.heroes():
        check(bool(HeroStatText.role(h)), "%s has a role line" % h)
        check(HeroStatText.attack_name(h) == catalog.get(h).tier_labels[0], "%s names its base ability" % h)
        for tier in range(4):
            lines = HeroStatText.attack_lines(h, tier)
            check(len(lines) >= 2 and all(lines), "%s tier %d stat lines" % (h, tier))
        check(len(catalog.get(h).description) > 40, "%s has a store description" % h)
    check(HeroStatText.is_support_hero(T.SAGE_AARAV) and HeroStatText.is_support_hero(T.SUNNY_JOE)
          and HeroStatText.is_support_hero(T.TANIMBUS) and not HeroStatText.is_support_hero(T.NIK_SCOPE), "support heroes flagged")
    g = new_game(0)
    g.set_global_enemy_speed_multiplier(0)
    g.set_hero_limit(2 ** 31 - 1)
    g.add_cash(1_000_000, None)
    for h in T.heroes():
        g.get_hero_collection().unlock(h)
        t = g.place_tower(h, buildable_near(g, Vec(150 + (h.ordinal % 7) * 140, 200 + (h.ordinal // 7) * 250), 200))
        if t is not None:
            HeroStatText.live_line(g, t)


def test_tutorial_script(check):
    g = new_game(0)
    S = TutorialScript.Step
    ts = TutorialScript(g)
    check(ts.current() is S.WELCOME and not ts.current().action, "starts on the welcome card")
    ts.update()
    check(ts.index() == 0, "info cards wait for NEXT")
    ts.next()
    check(ts.current() is S.PLACE, "then: place a tower")
    ts.update()
    check(ts.index() == 1, "action steps wait")
    gpt = g.place_tower(T.GPT, buildable_near(g, Vec(380, 300), 150))
    check(gpt is not None, "player places GPT")
    ts.update()
    check(ts.current() is S.WAVE, "placing a tower advances")
    g.start_next_wave()
    ts.update()
    check(ts.current() is S.UPGRADE and ts.grant_paid(), "starting a wave advances; bonus paid")
    check(g.upgrade_tower(gpt), "bonus covers the upgrade")
    ts.update()
    check(ts.current() is S.TARGETING, "upgrading advances")
    ts.next()
    check(ts.current() is S.HERO_STORE and g.get_cash() >= 1000, "Hero Store step funds a hero")
    check(g.purchase_hero(T.SUNNY_JOE), "buy a hero")
    ts.update()
    check(ts.current() is S.DEPLOY, "buying advances")
    sj = g.place_tower(T.SUNNY_JOE, buildable_near(g, Vec(700, 300), 150))
    ts.update()
    check(sj is not None and ts.current() is S.HERO_UPGRADE, "deploying advances")
    check(g.upgrade_tower(sj), "the bonus covers the hero's first upgrade")
    ts.update()
    check(ts.current() is S.ZETHOS, "upgrading the hero advances")
    ts.next()
    check(ts.current() is S.DONE, "final card")
    ts.next()
    check(ts.is_finished(), "FINISH ends the tutorial")
    check(g.get_hero_collection() is not HeroCollection.persistent(), "not wired to the saved collection")
    skip = TutorialScript(new_game(0))
    skip.skip_all()
    check(skip.is_finished(), "END TUTORIAL works from any step")


def test_catalog_entries(check):
    tab = CatalogScreen.Tab
    enemies, bosses = len(CatalogScreen.entries(tab.ENEMIES)), len(CatalogScreen.entries(tab.BOSSES))
    towers, heroes = CatalogScreen.entries(tab.TOWERS), CatalogScreen.entries(tab.HEROES)
    check(enemies + bosses == len(list(EnemyType)) and bosses == 5, "catalog lists every enemy and all 5 bosses")
    check(len(towers) == 18 and T.ZETHOS in towers, "18 shop towers incl. Zethos")
    check(len(heroes) == 18 and T.ZETHOS not in heroes, "18 heroes (not Zethos)")


def test_catalog_grid_and_popup(check):
    """The catalog opens on a grid of name + sprite cards; the detail card only appears after a click."""
    c = CatalogScreen(None)
    c.frame(0.1)
    surf = skia.Surface.MakeRasterN32Premul(800, 500)
    from lindefense.ui.jawt import Graphics2D, reset_canvas_state
    reset_canvas_state(surf.getCanvas())
    g = Graphics2D(surf.getCanvas())
    g.scale(0.5, 0.5)
    c.paint(g)
    check(True, "catalog paints without errors")


# ---------------------------------------------------------------- reverse-mode screen routing (ReverseModeTests.uiRouting)
def _key(code):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, code, KeyEvent.CHAR_UNDEFINED)


def test_reverse_ui_routing(check):
    g = ReverseMatch.create(0, 42, Difficulty.ON)
    r = g.get_reverse()
    s = GameScreen(None, g)
    s.frame(0.02)
    c = AttackPanel.card_center(AttackUnit.PRIMITIVE.ordinal)
    s.mouse_pressed(c[0], c[1], False)
    check(r.get_queued() == 5 and r.get_units_bought() == 5, "clicking the Primitive card sends 5 (%d)" % r.get_queued())
    s.key_pressed(_key(KeyEvent.VK_SPACE))
    check(r.get_queued() == 10, "SPACE repeats the last send (%d)" % r.get_queued())
    s.key_pressed(_key(KeyEvent.VK_X))
    s.key_pressed(_key(KeyEvent.VK_SPACE))
    check(r.get_queued() == 20, "X switches to x10 (%d)" % r.get_queued())
    check(g.get_wave() == 0 and not g.get_wave_manager().is_wave_active(), "SPACE never starts a campaign wave")
    b = AttackPanel.card_center(AttackUnit.MOAB.ordinal)
    s.mouse_pressed(b[0], b[1], False)
    check(r.get_queued() == 20, "a locked card sends nothing")
    s.start_wave()
    s.toggle_auto()
    check(g.get_wave() == 0 and not g.get_wave_manager().is_auto_start(), "Start Wave and Auto are off")
    s.toggle_hero_store()
    check(not s.is_hero_store_open(), "the Hero Store stays closed")
    s.begin_placing(T.GPT)
    check(s.get_placing() is None, "the player cannot place towers")
    for _ in range(int(6 / Game.DT)):
        if g.get_state() is not State.PLAYING:
            break
        g.step(Game.DT)
        g.get_events().clear()
    t = g.get_tower_manager().get_player_towers()[0]
    s.mouse_pressed(t.get_position().x, t.get_position().y + Ui.WORLD_Y, False)
    check(s.get_selected_tower() is t, "an AI tower can be selected for inspection")
    tier, cash, tg = t.get_tier(), g.get_cash(), t.get_targeting()
    for k in (KeyEvent.VK_U, KeyEvent.VK_S, KeyEvent.VK_T, KeyEvent.VK_A):
        s.key_pressed(_key(k))
    s.upgrade_selected()
    s.sell_selected()
    s.unlock_ability_selected()
    s.cycle_targeting(1)
    check(t.is_alive() and t.get_tier() == tier and g.get_cash() == cash and t.get_targeting() is tg, "AI towers are read-only")
    s.frame(0.02)
    s.escape_pressed()
    check(s.is_menu_open() and g.is_paused(), "Esc opens the pause menu")
    s.key_pressed(_key(KeyEvent.VK_SPACE))
    check(r.get_queued() <= 20, "attacker keys are inactive while paused")
    s.escape_pressed()
    check(not s.is_menu_open() and not g.is_paused(), "Esc resumes")
    s.key_pressed(_key(KeyEvent.VK_3))
    check(g.get_speed() == 3, "speed keys still work")
    e = spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10)
    g.lose_lives(Game.START_LIVES, e)
    for _ in range(200):
        if g.get_state() is not State.PLAYING:
            break
        s.frame(Game.DT)
    s.frame(0.02)
    check(g.get_state() is State.DEFEAT and r.attacker_won(), "breached")
