"""Regression tests for reverse mode's attacker panel, the Patch Notes draft and late-game art, clicked / painted through
the real ported UI (offscreen, no window)."""
import pytest

from lindefense import prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai.units import AttackAbility, AttackUnit
from lindefense.enemy.types import Modifier
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.ui.attack_panel import AttackPanel
from lindefense.ui.cyber import Cyber
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.jawt import Font


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


def _click(s, b):
    s.mouse_pressed(b.get_x() + b.w / 2, b.get_y() + b.h / 2, False)


def test_attack_panel_buttons_act_on_their_own_item(check):
    """Every modifier / quantity / exploit button acts on its own item (the loop lambdas used to all bind the last one,
    and toggling a modifier raised KeyError from set.remove)."""
    g = ReverseMatch.create(0, 42, Difficulty.ON)
    r = g.get_reverse()
    r.set_unlimited_credits(True)
    s = GameScreen(None, g)
    s.frame(0.02)
    ap = s.attack
    r._elapsed = 400.0   # every modifier and exploit unlocked
    s.frame(0.02)
    for i in range(len(ap.qty_btns)):
        _click(s, ap.qty_btns[i])
        check(ap.qty_index == i, "quantity button %d selects x%d (got index %d)" % (i, AttackPanel.QUANTITIES[i], ap.qty_index))
    for i, m in enumerate(Modifier.values()):
        _click(s, ap.mod_btns[i])
        check(m in ap.mods and len(ap.mods) == i + 1, "modifier button %s turns %s on (%s)" % (m, m, sorted(x.name for x in ap.mods)))
    _click(s, ap.mod_btns[0])
    check(Modifier.values()[0] not in ap.mods and len(ap.mods) == len(Modifier.values()) - 1, "a second click turns it off")
    r.send(AttackUnit.BFB, None, 3, -1)   # bosses stay on the track while the exploits are clicked
    for _ in range(int(2 / Game.DT)):
        g.step(Game.DT)
    s.frame(0.02)
    check(len(g.get_enemy_manager().get_enemies()) > 0, "units on the track")
    for i, a in enumerate(AttackAbility.values()):
        before = {x: r.get_uses(x) for x in AttackAbility.values()}
        _click(s, ap.exploit_btns[i])
        used = [x for x in AttackAbility.values() if r.get_uses(x) > before[x]]
        check(used == [a], "exploit button %s fires %s (fired %s)" % (a, a, used))




def test_patch_notes_card_click_ships_that_card(check):
    for k in range(3):
        g = Game(maps.create(0), 7)
        g.get_variance().enable()
        s = GameScreen(None, g)
        s.frame(0.02)
        v = g.get_variance()
        offer = list(v.get_offer())
        check(v.is_draft_pending() and len(offer) == 3, "the launch draft offers three cards")
        cards = [b for b in s.overlay_buttons if "SHIP IT" in b.get_text()]
        check(len(cards) == 3, "three SHIP IT buttons (%d)" % len(cards))
        cards.sort(key=lambda b: b.get_x())
        _click(s, cards[k])
        check([p.title for p in v.get_active()] == [offer[k].title],
              "card %d ships %s (shipped %s)" % (k, offer[k].title, [p.title for p in v.get_active()]))


def test_small_display_fonts_keep_their_size(check):
    """Cyber.display with a small size is floored (Java: deriveFont((float) max(floor, ..))); an int floor used to hit
    Font.deriveFont(int style) and leave a 1-pt font (boss logo banners, shrink-to-fit titles vanished)."""
    for size in (6, 8, 10, 12, 13, 20):
        for f in (Cyber.display(Font.BOLD, size), Cyber.display(Font.BOLD | Font.ITALIC, size), Cyber.display_compact(Font.BOLD, size)):
            check(f.get_size2d() >= 9, "display font for size %d is %s" % (size, f))
    from lindefense.ui.sprites.logo import Logo
    for logo in (Logo.bellarmine(28), Logo.lockheed(30), Logo.swrc(30), Logo.three_com(30)):
        for o in logo._contents:
            if hasattr(o, "get_label"):
                check(o.get_font().get_size2d() >= 9 and o.get_width() > 4 * len(o.get_label()),
                      "logo text %r is readable (%s, %.1f px wide)" % (o.get_label(), o.get_font(), o.get_width()))


def test_snapshot_tools_import_their_test_kit(check):
    from lindefense.ui import injection_snapshots, ui_snapshots, variance_snapshots
    for m in (injection_snapshots, ui_snapshots, variance_snapshots):
        check(hasattr(m, "TestKit"), "%s has TestKit" % m.__name__)
    tk = injection_snapshots.TestKit
    g = Game(maps.create(0), 7)
    r = g.get_map().get_routes()[0]
    p = tk.buildable_near(g, r.position_at(400), 140)
    from lindefense.tower.tower_type import TowerType
    t = tk.force_place(g, TowerType.GPT, p, 2)
    check(t is not None and t.get_tier() == 2, "TestKit.force_place places and upgrades")


def test_world_fx_prunes_dead_entities(check):
    """WorldFx forgets entities that are gone (Java: born.keySet().removeIf(...)); the Python keySet view used to be a
    detached copy, so the map kept every zone / walker / drone / hazard of the match alive forever."""
    from lindefense.ui import jrt as _j
    from lindefense.ui.world_fx import WorldFx
    g = Game(maps.create(0), 7)
    fx = WorldFx(g)
    for _ in range(50):
        fx.born[object()] = 0.0   # not a live sim entity -> pruned
    fx.update(2.0)
    check(len(fx.born) == 0, "dead entries pruned (%d left)" % len(fx.born))
    m = _j.HashMap()
    m["a"], m["b"], m["c"] = 1, 2, 3
    check(_j._j_remove_if(_j.key_set(m), _j.Fn(lambda k: k != "b")) and dict(m) == {"b": 2}, "keySet().removeIf edits the map")
    m["a"], m["c"] = 1, 3
    check(_j._j_remove_if(_j.values_view(m), _j.Fn(lambda v: v == 3)) and dict(m) == {"a": 1, "b": 2},
          "values().removeIf edits the map")
