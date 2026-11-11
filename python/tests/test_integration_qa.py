"""Regressions found by the post-merge QA pass (restyle + tutorial + campaign + hero placement fix): where the merged
features meet. Each test names the interaction it covers."""
import pytest

from kit import spawn_at
from lindefense import prefs, savegame
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim import campaign
from lindefense.sim import records as R
from lindefense.sim.campaign import CampaignProgress
from lindefense.sim.game import Game
from lindefense.sim.misc import HeroCollection
from lindefense.tower.tower_type import TowerType as T


@pytest.fixture(autouse=True)
def _temp_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path / "prefs"))
    prefs._nodes.clear()
    shared = (CampaignProgress._shared, HeroCollection._shared, R.Records._shared)
    CampaignProgress._shared = HeroCollection._shared = R.Records._shared = None
    yield
    prefs._nodes.clear()
    CampaignProgress._shared, HeroCollection._shared, R.Records._shared = shared


def _real_app():
    from lindefense.app import LindefenseApp
    from lindefense.ui.scaled_layer import ScaledLayer
    app = LindefenseApp.__new__(LindefenseApp)
    app.root = ScaledLayer()
    app.menu = app.map_select = app.game_screen = None
    app.demo = app.window_grab = app.autosave = None
    app._errors = {}
    app.running = True
    app.px_w, app.px_h = 1600, 1000
    app._settle_heap = lambda: None
    return app


def test_heroes_button_reads_locked_before_the_hero_store_level(check):
    """Campaign x restyle: the HEROES button was dimmed through its accent only, which the flat restyle barely shows
    on a resting button (it looked exactly like MENU). Its label is greyed now; it stays clickable to say why."""
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.ui_button import UIButton
    early = GameScreen(None, campaign.new_game(1, 3))
    early.frame(0.02)
    b = early.hud.hero_btn
    check(b.text.get_color() == UIButton.DISABLED_TEXT, "level 1: HEROES reads locked (%s)" % b.text.get_color())
    check(b.text.get_color() != early.hud.menu_btn.text.get_color(), "and differs from MENU")
    check(b.is_enabled(), "a click still explains which level opens it")
    b.click()
    check(not early.is_hero_store_open() and "Hero Store opens after level" in early.abilities.hint, "it says so")
    for g in (campaign.new_game(campaign.heroes_level().index + 1, 3), Game(maps.create(0), 3)):
        s = GameScreen(None, g)
        s.frame(0.02)
        check(s.hud.hero_btn.text.get_color() != UIButton.DISABLED_TEXT, "open Hero Store: a normal HEROES button")


def test_shift_hotkey_on_a_locked_unaffordable_tower_names_its_unlock_level(check):
    """Campaign x Shift+1-9: a locked card the player cannot afford said 'needs $N more', as if cash would help."""
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.shop_layout import ShopLayout
    g = campaign.new_game(1, 3)
    s = GameScreen(None, g)
    s.frame(0.02)
    cells = ShopLayout.faction_cells(s.side.get_tab())
    idx = next(i for i, c in enumerate(cells) if g.tower_lock_problem(c.type) is not None)
    locked = cells[idx].type
    g.spend_cash(g.get_cash())
    s.pick_shop_card(idx)
    check(s.get_placing() is None, "nothing armed")
    check(s.abilities.hint == g.tower_lock_problem(locked), "the hint names the unlock level (%s)" % s.abilities.hint)
    free = next(i for i, c in enumerate(cells) if g.tower_lock_problem(c.type) is None)
    s.pick_shop_card(free)
    check("needs" in s.abilities.hint, "an unlocked card still asks for the missing cash (%s)" % s.abilities.hint)


def test_tutorial_from_boot_camp_quits_back_to_the_campaign(check):
    """Tutorial x campaign: the BOOT CAMP node's tutorial QUIT LEVEL (also after RESTART) landed on CLASSIC map select."""
    from lindefense.ui.campaign_screen import BOOT_CAMP, CampaignScreen
    from lindefense.ui.map_select_screen import MapSelectScreen
    app = _real_app()
    app.show_campaign()
    app.get_map_select().activate(BOOT_CAMP)
    check(app.get_game_screen() is not None and app.get_game_screen().get_tutorial() is not None, "BOOT CAMP: tutorial")
    app.restart_level()
    check(app.get_game_screen().get_tutorial() is not None, "RESTART keeps the tutorial")
    app.quit_level()
    check(isinstance(app.get_map_select(), CampaignScreen), "QUIT LEVEL returns to the campaign")
    app.show_menu()
    app.start_tutorial()
    app.quit_level()
    check(isinstance(app.get_map_select(), MapSelectScreen), "from the main menu it still returns to map select")
    app.start_campaign_level("hello_world")
    app.quit_level()
    check(isinstance(app.get_map_select(), CampaignScreen), "campaign levels return to the campaign")
    app.start_game(0)
    app.quit_level()
    check(isinstance(app.get_map_select(), MapSelectScreen), "classic runs return to map select")
    check(not savegame.slot().exists(), "nothing was played: nothing saved")


def test_classic_only_achievements_say_classic(check):
    """Campaign x records: the achievements a campaign level never earns said 'Win a campaign ...' (and 'Hello, World'
    shares its name with campaign level 1), so winning a campaign level looked like it should count."""
    from lindefense.ui.acm import GLabel
    from lindefense.ui.stats_screen import StatsScreen, Tab
    for a in R.achievements():
        if a.mode != "campaign":
            continue
        if a.group in R.CLASSIC_GROUPS:
            check("CLASSIC" in a.description and "campaign" not in a.description.lower(),
                  "%s: %s" % (a.id, a.description))
    wins = next(a for a in R.achievements() if a.id == "wins_10")
    check("campaign levels" in wins.description, "career wins count campaign levels and say so (%s)" % wins.description)
    rec = R.Records.in_memory()
    rec.record(R.RunSummary(map_name="The Silicon Circuit", map_index=0, difficulty="O1", seed=1, result=R.VICTORY,
                            wave=10, waves_cleared=10, campaign_level="hello_world", campaign_stars=3))
    check(not rec.is_unlocked("first_win") and rec.career()["victories"] == 1,
          "a campaign level win: no CLASSIC achievement, one career victory")

    def labels(c, out):
        for o in c:
            if isinstance(o, GLabel):
                out.append(o.get_label())
            elif hasattr(o, "get_element_count"):
                labels(o, out)
        return out
    st = StatsScreen(lambda: None, lambda *a: None, rec)
    career = labels(st, [])
    check("CLASSIC runs and campaign levels won" in career, "the CAREER victories caption says what counts")
    st.set_tab(Tab.HISTORY)
    check(any("CLASSIC run" in x for x in labels(st, [])), "the empty HISTORY says it lists CLASSIC runs")


def test_side_panel_boss_name_fits_beside_its_badge(check):
    """Restyle review: 'SW Resource Consultant' + its 'BFB BOSS' badge ran past the side panel's right edge."""
    from lindefense.ui.acm import GLabel
    from lindefense.ui.game_screen import GameScreen
    g = Game(maps.create(0), 3)
    s = GameScreen(None, g)
    g.start_next_wave()
    e = spawn_at(g, EnemyType.SW_RESOURCE_CONSULTANT, None, 0, 200)
    s.select_enemy(e)
    s.frame(0.02)
    side = s.side
    right = side.x0 + side.text_w
    labels = [o for o in side.info if isinstance(o, GLabel)]
    name = next(o for o in labels if o.get_label() == "SW Resource Consultant")
    badge = next(o for o in labels if o.get_label() == "BFB BOSS")
    check(badge.get_x() + badge.get_width() <= right + 9.5, "badge inside the panel (%.0f > %.0f)" % (
        badge.get_x() + badge.get_width(), right))
    check(name.get_x() + name.get_width() < badge.get_x(), "the name ends before its badge")
    short = GameScreen(None, Game(maps.create(0), 3))
    short.game.start_next_wave()
    short.select_enemy(spawn_at(short.game, EnemyType.PRIMITIVE_VARIABLE, None, 0, 200))
    short.frame(0.02)
    n2 = next(o for o in short.side.info if isinstance(o, GLabel) and o.get_label() == "Primitive Variable")
    from lindefense.ui.side_panel import SidePanel
    check(n2.get_font().get_size() == SidePanel.F_NAME.get_size(), "a name that fits keeps the full size (%s)" % (
        n2.get_font().get_size()))
    check(name.get_font().get_size() < SidePanel.F_NAME.get_size(), "the long one shrinks")


def test_campaign_end_panel_names_the_achievements_it_unlocked(check):
    """Campaign x records: Fully Trained / State of the Art / Base Model unlock when the level is recorded, after the
    last live toast, and the level's end panel (unlike CLASSIC's) had no records line: they unlocked silently."""
    from kit import force_place
    from lindefense.sim.game import State
    from lindefense.sim.vec import Vec
    from lindefense.ui.game_screen import GameScreen
    p = CampaignProgress.in_memory({lv.id: 3 for lv in campaign.LEVELS[:-1]})
    rec = R.Records.in_memory()
    g = campaign.new_game(campaign.finale(), 5)
    s = GameScreen(None, g)
    s.set_run_session(R.RunSession(rec, g, False, p))
    t = force_place(g, T.GPT, Vec(380, 300) if g.get_map().is_buildable(Vec(380, 300), 30) else Vec(300, 200))
    g.get_tower_manager().sell(t)
    g._state = State.VICTORY
    s.epilogue_done = True
    s.frame(0.02)
    texts = [o.get_label() for o in s.overlay if hasattr(o, "get_label")]
    line = next((x for x in texts if "unlocked:" in x), "")
    check(rec.is_unlocked("campaign_done") and "Fully Trained" in line, "the panel names it (%s)" % line)
    check(line.index("Fully Trained") < line.index("State of the Art") if "State of the Art" in line else True, "order")
    labels = [b.get_text() for b in s.overlay_buttons]
    check(labels == ["CAMPAIGN", "RETRY", "MAIN MENU"], "buttons unchanged (%s)" % labels)
    ys = sorted(o.get_y() for o in s.overlay if hasattr(o, "get_label") and o.get_label() == line)
    by = min(b.get_y() for b in s.overlay_buttons)
    check(ys and ys[0] < by - 4, "the line sits above the buttons (%s vs %s)" % (ys, by))
    credits = next(x for x in texts if x.startswith("$"))
    check(credits == "$" + "{:,}".format(int(s.run_summary().cash_earned)), "credits earned are income, refunds excluded"
          " like the CLASSIC panel (%s)" % credits)
    plain = GameScreen(None, campaign.new_game(2, 5))
    plain.game._state = State.DEFEAT
    plain.frame(0.02)
    check(not [o for o in plain.overlay if hasattr(o, "get_label") and "unlocked:" in o.get_label()],
          "no line without unlocks")


def test_side_panel_ability_text_follows_the_campaign_lock(check):
    """Campaign x side panel: before the abilities level the shop card and the upgrade preview still promised 'Max
    tier unlocks <ability> ($15,000)'; they now say which level opens it (and CLASSIC is unchanged)."""
    from lindefense.ui.acm import GLabel
    from lindefense.ui.game_screen import GameScreen
    from kit import buildable_near
    from lindefense.sim.vec import Vec

    def texts(s):
        return [o.get_label() for o in s.side.info if isinstance(o, GLabel)]
    n = campaign.abilities_level().index
    for g, locked in ((campaign.new_game(1, 3), True), (campaign.new_game(n + 1, 3), False), (Game(maps.create(0), 3), False)):
        s = GameScreen(None, g)
        s.begin_placing(T.GPT)
        s.frame(0.02)
        shop = texts(s)
        check(("Ability, opens after level %d" % n in shop) == locked, "shop card (%s): %s" % (locked, shop[:12]))
        check(("Ability, unlocks at max tier" in shop) == (not locked), "or the usual line")
        s.begin_placing(None)
        g.add_cash(5000, None)
        t = g.get_tower_manager().place(T.GPT, buildable_near(g, Vec(380, 300), 200))
        s.select_tower(t)
        s.frame(0.02)
        sel = texts(s)
        check(any(x.startswith("Max tier unlocks") for x in sel) == (not locked), "tower panel (%s): %s" % (locked, sel))
        check(any("open after level %d" % n in x for x in sel) == locked, "names the level when locked")


def test_campaign_games_are_not_tutorial_games(check):
    """Campaign levels set a wave list too; only the tutorial match counts as a tutorial game."""
    from lindefense.sim import campaign
    from lindefense.ui.tutorial_script import is_tutorial_game
    g = campaign.new_game(campaign.LEVELS[0], seed=7)
    check(g.get_campaign() is not None and g.get_wave_manager().get_wave_list() is not None, "a campaign game with a wave list")
    check(not is_tutorial_game(g), "a campaign level is not a tutorial game")
