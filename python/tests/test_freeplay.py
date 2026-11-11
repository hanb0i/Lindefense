"""Freeplay (endless generated waves after Palantir) and the victory epilogue / credits."""
import skia
import pytest

from kit import buildable_near, force_place, kill_outright, new_game, run_seconds, spawn_at
from lindefense import prefs
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.audio.music_director import MusicDirector
from lindefense.audio.track import Track
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game, State
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui.acm import GCompound, GLabel
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.jawt import Graphics2D, KeyEvent, reset_canvas_state
from lindefense.ui.ui import Ui
from lindefense.ui.victory_epilogue import VictoryEpilogue
from lindefense.variance.variance import BreakingNews, Picker, RunVariance
from lindefense.wave import waves
from lindefense.wave.freeplay import FreeplayWaves as F

W = waves.WAVE_COUNT


@pytest.fixture(autouse=True)
def _prefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path))
    prefs._nodes.clear()
    yield
    prefs._nodes.clear()


def won_game(seed=42, map_idx=0, variance=None, towers=0):
    """A game that has just beaten Palantir on wave 100 (waves 1-99 skipped, Palantir killed outright)."""
    g = new_game(map_idx, seed)
    if variance is not None:
        g.get_variance().enable(variance)
    spots = [Vec(380, 300), Vec(800, 600), Vec(600, 420), Vec(300, 650)]
    for i in range(towers):
        force_place(g, (T.GPT, T.GEMINI, T.PERPLEXITY, T.CLAUDE)[i % 4], buildable_near(g, spots[i % len(spots)], 150), 3)
    wm = g.get_wave_manager()
    for _ in range(W - 1):
        wm.start_next_wave()
        wm.end_wave()
    assert wm.start_next_wave() and g.get_wave() == W
    kill_outright(g, spawn_at(g, EnemyType.PALANTIR, None, 0, 60))
    run_seconds(g, Game.VICTORY_SEQUENCE_TIME + 0.2)
    assert g.get_state() is State.VICTORY
    return g


def skip_to(g, wave):
    wm = g.get_wave_manager()
    while g.get_wave() < wave:
        assert wm.start_next_wave(), "wave %d starts" % (g.get_wave() + 1)
        wm.end_wave()


def shape(w):
    return [(gr.type, gr.count, tuple(sorted(m.name for m in gr.modifiers)), gr.interval, gr.start_delay, gr.route)
            for gr in w.groups], w.note


def texts(node, out=None):
    """Every label text inside a scene-graph node."""
    out = [] if out is None else out
    if isinstance(node, GLabel):
        out.append(node.get_label())
    if isinstance(node, GCompound):
        for o in node:
            texts(o, out)
    return out


def paint(screen):
    surf = skia.Surface.MakeRasterN32Premul(800, 500)
    reset_canvas_state(surf.getCanvas())
    g = Graphics2D(surf.getCanvas())
    g.scale(0.5, 0.5)
    screen.paint(g)
    return surf.makeImageSnapshot().toarray()


def _key(code):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, code, KeyEvent.CHAR_UNDEFINED)


# ---------------------------------------------------------------- generator
def test_generated_waves_are_deterministic(check):
    for seed in (1, 42, 1234):
        for w in (101, 110, 117, 125, 150, 199):
            a = shape(F.generate(seed, w))
            F._cache.clear()
            b = shape(waves.get(w, seed))
            check(a == b, "seed %d wave %d generates the same wave every time" % (seed, w))
            check(waves.get(w, seed) is waves.get(w, seed), "cached")
    differ = sum(1 for w in range(101, 121) if shape(waves.get(w, 1)) != shape(waves.get(w, 2)))
    check(differ >= 15, "another seed gives other waves (%d of 20 differ)" % differ)
    check(all(waves.get(w, 999) is waves.get(w) for w in range(1, W + 1)), "waves 1-100 ignore the seed")
    a, b = new_game(0, 5), new_game(0, 5)
    for w in range(101, 140):
        F._cache.clear()
        waves.for_game(a, w)
    check(a.get_rng().next() == b.get_rng().next(), "generating waves never touches Game._rng")
    g = waves.for_game(a, 117)
    check(g.number == 117 and g.total_spawns() > 0 and g.note, "for_game uses the run seed")


def test_generated_waves_escalate(check):
    for seed in (1, 42, 1234):
        decades = [sum(F.total_hp(waves.get(w, seed)) for w in range(s, s + 10)) for s in range(101, 201, 10)]
        check(all(b > a * 1.5 for a, b in zip(decades, decades[1:])),
              "seed %d: total HP grows every 10 waves (%s)" % (seed, [round(x) for x in decades]))
        first = F.total_hp(waves.get(101, seed))
        check(first > 0.3 * F.total_hp(waves.get(99)), "wave 101 is no step down from the late campaign (%.0f)" % first)
    check(all(F.hp_scale(w + 1) > F.hp_scale(w) for w in range(100, 400)), "per-enemy health grows forever")
    check(abs(waves.hp_scale(101) - waves.hp_scale(100) * F.HP_GROWTH) < 1e-9, "freeplay health continues from wave 100")
    check(F.hp_scale(200) > 500, "it becomes impossible (x%.0f health by wave 200)" % F.hp_scale(200))
    check(all(waves.speed_scale(w) <= F.SPEED_CAP for w in range(101, 400)), "speed is capped")
    check(waves.speed_scale(101) >= waves.speed_scale(100), "speed does not drop after wave 100")
    for w in range(1, W + 1):
        if waves.hp_scale(w) != waves._curve(waves.HP_CURVE, w):   # freeplay never touches waves 1-100
            check(False, "campaign health scale changed at wave %d" % w)
    seen = set()
    for w in range(101, 161):
        d = waves.get(w, 7)
        for gr in d.groups:
            seen.update(gr.modifiers)
            seen.add(gr.type)
        heads = [gr.type for gr in d.groups if gr.type in (EnemyType.PALANTIR, EnemyType.THREE_COM)]
        if F.is_palantir_wave(w):
            check(EnemyType.PALANTIR in heads and "PALANTIR" in d.note, "wave %d brings a rebuilt Palantir" % w)
        else:
            check(EnemyType.PALANTIR not in heads, "no Palantir on wave %d" % w)
        if F.is_boss_wave(w) and not F.is_palantir_wave(w):
            check(d.note.startswith("FREEPLAY BOSS"), "wave %d is a headline boss wave" % w)
        check(d.contains_boss(), "wave %d has MOAB-class escorts" % w)
    for m in (Modifier.CAMO, Modifier.FORTIFIED, Modifier.REGROW, Modifier.INJECTION):
        check(m in seen, "freeplay uses %s" % m.label)
    for t in (EnemyType.THREE_COM, EnemyType.SW_RESOURCE_CONSULTANT, EnemyType.LOCKHEED_MARTIN, EnemyType.BELLARMINE_COLLEGE_PREP, EnemyType.TIMSORT):
        check(t in seen, "freeplay sends %s" % t.display_name)
    check(F.is_boss_wave(110) and F.is_boss_wave(120) and not F.is_boss_wave(115) and F.is_palantir_wave(125)
          and F.is_palantir_wave(150) and not F.is_palantir_wave(100), "boss schedule")


# ---------------------------------------------------------------- game flow
def test_continue_freeplay_and_waves_past_100(check):
    g = won_game()
    wm = g.get_wave_manager()
    check(not wm.can_start_next_wave() and not g.start_next_wave(), "the campaign ends at wave 100")
    check(g.can_continue_freeplay() and not g.is_freeplay(), "a won campaign can continue")
    cash, towers = g.get_cash(), len(g.get_tower_manager().get_towers())
    check(g.continue_freeplay(), "continue")
    check(g.get_state() is State.PLAYING and g.is_freeplay() and not g.can_continue_freeplay(), "back in play, once")
    check(g.get_cash() == cash and len(g.get_tower_manager().get_towers()) == towers, "board and cash carry over")
    check(g.get_enemy_manager().get_alive_count() == 0 and g.get_last_completed_wave() == W, "the track is cleared")
    check(wm.can_start_next_wave(), "can_start_next_wave works past 100")
    skip_to(g, 160)
    check(g.get_wave() == 160 and wm.can_start_next_wave(), "freeplay never runs out of waves")
    check(not g.continue_freeplay(), "continue only works on the victory screen")
    # a rebuilt Palantir dying in freeplay does not end the run
    p = spawn_at(g, EnemyType.PALANTIR, None, 0, 60)
    kill_outright(g, p)
    run_seconds(g, 1)
    check(g.get_state() is State.PLAYING and not g.is_victory_sequence_active(), "a freeplay Palantir kill is not a second victory")
    # finishing a freeplay wave never triggers the wave-100 victory either
    g2 = won_game(seed=3)
    g2.continue_freeplay()
    g2.start_next_wave()
    run_seconds(g2, 0.5)
    for e in list(g2.get_enemy_manager().get_enemies()):
        e.mark_dead()
    g2.get_enemy_manager().clear()
    g2.get_wave_manager()._progress = [gr.count for gr in g2.get_wave_manager().get_current_def().groups]
    run_seconds(g2, 0.5)
    check(g2.get_last_completed_wave() == 101 and g2.get_state() is State.PLAYING, "wave 101 completes and play goes on")
    check(g2.get_wave_hp_scale() == pytest.approx(F.hp_scale(101)), "wave 101 spawns at freeplay health")


def test_freeplay_loss_is_a_victory(check):
    g = won_game()
    g.continue_freeplay()
    skip_to(g, 116)
    g.start_next_wave()
    run_seconds(g, 3)
    g.lose_lives(g.get_lives(), spawn_at(g, EnemyType.PRIMITIVE_VARIABLE, None, 0, 10))
    run_seconds(g, 2.5)
    check(g.get_state() is State.VICTORY and g.is_freeplay() and g.get_wave() == 117, "lives at zero end freeplay as a VICTORY")
    check(not g.can_continue_freeplay(), "no second freeplay")
    s = GameScreen(None, g)
    s.frame(0.02)
    t = texts(s.overlay)
    check(not s.is_epilogue_open(), "no epilogue after freeplay")
    check(any(x.startswith("VICTORY - reached wave 117 in freeplay") for x in t), "end screen: %s" % t)
    check(not any(b.get_text() == "CONTINUE - FREEPLAY" for b in s.overlay_buttons), "no CONTINUE after freeplay")
    check(s.overlay_title is not None and s.overlay_title.get_label() == "VICTORY", "titled VICTORY")


def test_seeded_freeplay_replays_identically(check):
    def play(seed):
        F._cache.clear()
        g = won_game(seed=seed, towers=4)
        g.continue_freeplay()
        g.set_invincible(True)   # 4 towers cannot hold freeplay; leaks just end each wave sooner
        g.get_wave_manager().set_auto_start(True)
        g.start_next_wave()
        out = []
        for _ in range(int(80 / Game.DT)):
            g.step(Game.DT)
            g.get_events().clear()
            if g.get_tick() % 600 == 0:
                em = g.get_enemy_manager()
                out.append((g.get_wave(), g.get_lives(), g.get_cash(), em.get_total_spawned(), em.get_total_killed(),
                            round(sum(e.get_hp() for e in em.get_enemies()), 6),
                            tuple(round(e.get_distance(), 6) for e in em.get_enemies())))
        return out
    a, b = play(11), play(11)
    check(a == b, "the same seed replays the same freeplay continuation")
    check(a[-1][0] >= 102 and a[-1][3] > 150 and a[-1][4] > 20, "it really played freeplay waves (%s)" % (a[-1][:5],))
    check(play(12) != a, "another seed plays differently")


def test_freeplay_variance_music_and_modes(check):
    check(RunVariance.draft_index(121) == 5 and RunVariance.draft_index(141) == 6 and RunVariance.draft_index(101) == -1
          and RunVariance.draft_index(120) == -1 and RunVariance.draft_index(80) == 4, "freeplay drafts every 20 waves from 121")
    check(BreakingNews.roll(1, W, False, 2) is None, "no news on the Palantir wave")
    check(any(BreakingNews.roll(s, 117, False, 2) is not None for s in range(40)), "news continues in freeplay")
    g = won_game(seed=8, variance=Picker.FIRST)
    v = g.get_variance()
    check(len(v.get_active()) == 5, "five campaign drafts")
    g.continue_freeplay()
    skip_to(g, 120)
    check(g.get_wave_manager().can_start_next_wave(), "wave 121 can start (draft auto-picked)")
    check(len(v.get_active()) == 6 and v.get_picked_before(5) == 121, "a freeplay draft before wave 121")
    skip_to(g, 141)
    check(len(v.get_active()) == 7, "and before wave 141")
    # music: battle_late in freeplay, the boss / Palantir themes only while those bosses are on the field
    md = MusicDirector()
    check(md.choose(False, False, 117, False, False, False, 0)[0] is Track.BATTLE_LATE, "freeplay plays battle_late")
    check(md.choose(False, False, 117, False, False, True, 10)[0] is Track.BOSS, "boss theme with a boss on the field")
    check(md.choose(False, False, 125, False, True, False, 20)[0] is Track.PALANTIR, "Palantir theme for a rebuilt Palantir")
    check(MusicDirector().choose(False, False, W, False, False, False, 0)[0] is Track.PALANTIR, "wave 100 still plays Palantir's theme")
    # reverse mode and the tutorial are untouched
    r = ReverseMatch.create(0, 42, Difficulty.ON)
    r.declare_defender_victory("CONTAINED")
    check(r.get_state() is State.VICTORY and not r.can_continue_freeplay() and not r.continue_freeplay(), "no freeplay in reverse mode")
    s = GameScreen(None, r)
    s.frame(0.02)
    check(not s.is_epilogue_open() and not any(b.get_text() == "CONTINUE - FREEPLAY" for b in s.overlay_buttons),
          "reverse end screen has no epilogue or freeplay")
    t = won_game(seed=9)
    ts = GameScreen(None, t, True)
    ts.frame(0.02)
    check(not ts.is_epilogue_open() and not ts.freeplay_offered(), "the tutorial never offers the epilogue or freeplay")


# ---------------------------------------------------------------- UI
def test_epilogue_renders_and_skips(check):
    g = won_game()
    s = GameScreen(None, g)
    s.frame(0.02)
    check(s.is_epilogue_open(), "the epilogue opens on the first victory")
    t = s.epilogue.texts()
    check(VictoryEpilogue.BYLINE in t and VictoryEpilogue.THANKS in t, "credits: %s" % t)
    check("The last line of code holds." in t and any("surveillance network" in x for x in t), "story lines")
    check(any("Rajdhani" in x for x in t) and any("Juhani Junkala" in x for x in t), "font and sound credits")
    ep = s.epilogue
    check(ep.top >= Ui.WORLD_Y and ep.top + ep.height <= Ui.BOTTOM_Y, "the epilogue fits the playfield (%s + %s)" % (ep.top, ep.height))
    check(not ep.is_finished(), "it fades in over time")
    for _ in range(40):
        s.frame(0.25)
    check(ep.is_finished(), "everything is shown after a few seconds")
    img = paint(s)
    check(img.std() > 5, "the epilogue paints")
    check(len(s.overlay_buttons) == 0, "nothing clickable behind it")
    s.key_pressed(_key(KeyEvent.VK_P))
    check(s.is_epilogue_open() and not g.is_paused(), "other keys do nothing")
    s.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not s.is_epilogue_open(), "Esc skips it")
    btn = [b for b in s.overlay_buttons if b.get_text() == "CONTINUE - FREEPLAY"]
    check(len(btn) == 1, "the victory screen offers CONTINUE - FREEPLAY")
    check(any(x.startswith("Palantir has fallen") for x in texts(s.overlay)), "victory stats follow")
    paint(s)
    for b in s.overlay_buttons:
        bx, by, bw, bh = b.get_x(), b.get_y(), b.get_w(), b.get_h()
        check(Ui.WORLD_X <= bx and bx + bw <= Ui.WORLD_X + Ui.WORLD_W and Ui.WORLD_Y <= by and by + bh <= Ui.BOTTOM_Y, "%s on screen" % b.get_text())
        for o in s.overlay_buttons:
            if o is not b:
                check(bx + bw <= o.get_x() or o.get_x() + o.get_w() <= bx or by + bh <= o.get_y() or o.get_y() + o.get_h() <= by,
                      "%s does not overlap %s" % (b.get_text(), o.get_text()))
    s.frame(0.02)
    check(not s.is_epilogue_open(), "the epilogue plays once")
    b = btn[0]
    s.mouse_pressed(b.get_x() + b.get_w() / 2, b.get_y() + b.get_h() / 2, False)
    check(g.is_freeplay() and g.get_state() is State.PLAYING, "CONTINUE - FREEPLAY resumes the run")
    s.frame(0.02)
    check(len(s.overlay_buttons) == 0 and not s.is_epilogue_open(), "the overlay closes")
    # a click skips it too
    h = won_game(seed=4)
    s2 = GameScreen(None, h)
    s2.frame(0.02)
    s2.mouse_pressed(600, 500, False)
    check(not s2.is_epilogue_open() and h.get_state() is State.VICTORY, "a click skips it (and clicks nothing else)")


def test_freeplay_hud(check):
    g = won_game()
    g.continue_freeplay()
    skip_to(g, 117)
    s = GameScreen(None, g)
    s.frame(0.02)
    hud = s.hud
    chip = hud.wave_chip
    check(chip.value.get_label() == "W 117" and hud.freeplay_tag.get_label() == "FREEPLAY", "the chip reads FREEPLAY W 117")
    check(not chip.icon.is_visible(), "the icon makes room for the tag")
    tag_r = hud.freeplay_tag.get_x() + hud.freeplay_tag.get_width()
    check(tag_r < chip.value.get_x(), "tag and number do not overlap")
    check(chip.value.get_x() + chip.value.get_width() <= chip.width - 4, "the label fits the chip (%.1f of %.0f)"
          % (chip.value.get_x() + chip.value.get_width(), chip.width))
    check(hud.wave_bar.value == pytest.approx(0.7), "the bar fills toward the wave-120 boss (%s)" % hud.wave_bar.value)
    check(hud.start_btn.get_text() == "START WAVE 118", "start button: %s" % hud.start_btn.get_text())
    pv = hud.intel
    check(pv is not None and pv.number == 118 and sum(gr.count for gr in pv.groups) > 0 and "118" in hud.intel_label,
          "next-wave preview past 100 (%s)" % (None if pv is None else pv.number))
    g.start_next_wave()
    s.frame(0.02)
    check(hud.start_btn.get_text() == "WAVE 118 LIVE", "no FINAL WAVE in freeplay (%s)" % hud.start_btn.get_text())
    g.get_wave_manager().end_wave()
    skip_to(g, 1016)
    s.frame(0.02)
    check(chip.value.get_label() == "W 1016" and chip.value.get_x() + chip.value.get_width() <= chip.width - 4,
          "four-digit waves still fit")
    paint(s)
    n = new_game(0)
    ns = GameScreen(None, n)
    ns.frame(0.02)
    check(ns.hud.wave_chip.value.get_label() == "0 / 100" and ns.hud.freeplay_tag is None, "normal games keep w / 100")


def test_freeplay_continues_the_campaign_curve(check):
    """Wave 101 is never easier than wave 100: freeplay's health and speed start where the campaign curve ends."""
    from lindefense.wave import waves
    from lindefense.wave.freeplay import FreeplayWaves
    check(FreeplayWaves.HP_START == waves._curve(waves.HP_CURVE, 100), "health continues from wave 100")
    check(FreeplayWaves.SPEED_START == waves._curve(waves.SPEED_CURVE, 100), "speed continues from wave 100")
    check(waves.hp_scale(101) > waves.hp_scale(100) and waves.speed_scale(101) >= waves.speed_scale(100),
          "wave 101 is at least as tough as wave 100")
