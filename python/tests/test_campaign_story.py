"""The campaign story (sim/campaign_story.py, ui/story_view.py): every level's story beats and their consistency, the
seen-scene log (in memory and on disk), the prologue and pre-level dialogues (once, skippable), the STORY codex replays,
the briefing card, the radio chatter firing at its waves without touching the game (twin runs), the outcome rows on the
LEVEL COMPLETE / DEFEAT panels, the campaign ending replacing the classic epilogue only for campaign runs, Save &
Continue, and the layouts fitting the 1600 x 1000 logical screen. Every test uses temp folders and in-memory logs."""
import re

import pytest

from kit import DT, kill_outright
from lindefense import prefs, savegame
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim import campaign
from lindefense.sim import campaign_story as story
from lindefense.sim import records as R
from lindefense.sim.campaign import CampaignProgress, LEVELS
from lindefense.sim.campaign_story import StoryLog
from lindefense.sim.game import Game, State
from lindefense.sim.misc import HeroCollection
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.jawt import KeyEvent


@pytest.fixture(autouse=True)
def _temp_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("LINDEFENSE_PREFS_DIR", str(tmp_path / "prefs"))
    prefs._nodes.clear()
    shared = (CampaignProgress._shared, HeroCollection._shared, R.Records._shared, StoryLog._shared,
              DisplaySettings.instance)
    CampaignProgress._shared = HeroCollection._shared = R.Records._shared = StoryLog._shared = None
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    yield
    prefs._nodes.clear()
    (CampaignProgress._shared, HeroCollection._shared, R.Records._shared, StoryLog._shared,
     DisplaySettings.instance) = shared


class _App:
    def __init__(self):
        self.calls = []

    def show_menu(self):
        self.calls.append("menu")

    def start_tutorial(self):
        self.calls.append("tutorial")

    def start_campaign_level(self, lid):
        self.calls.append("start:" + lid)

    def show_campaign(self, briefing=None):
        self.calls.append("campaign" + ("" if briefing is None else ":" + briefing))

    def restart_level(self):
        self.calls.append("retry")

    def show_map_select(self):
        self.calls.append("map_select")


def _key(code):
    return KeyEvent(None, KeyEvent.KEY_PRESSED, 0, 0, code, KeyEvent.CHAR_UNDEFINED)


def _paint(c):
    from lindefense.ui.cyber import Cyber
    from lindefense.ui.jawt import BufferedImage
    img = BufferedImage(1600, 1000, BufferedImage.TYPE_INT_ARGB)
    g2 = img.create_graphics()
    Cyber.quality(g2)
    c.paint(g2)
    g2.dispose()
    return img


def _sentences(text):
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def _inside(r, box):
    x, y, w, h = r
    bx, by, bw, bh = box
    return bx - 0.5 <= x and by - 0.5 <= y and x + w <= bx + bw + 0.5 and y + h <= by + bh + 0.5


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# ====================================================================== the story data
def test_every_level_has_its_story_beats(check):
    check(sorted(story.STORY) == sorted(lv.id for lv in LEVELS), "a story for every level, and only for levels")
    acts = [story.story(lv).act for lv in LEVELS]
    check(acts == sorted(acts) and set(acts) == set(range(len(story.ACTS))), "the levels walk through every act in order")
    for lv in LEVELS:
        s = story.story(lv)
        name = lv.id
        check(s.briefing.text and s.briefing.speaker in story.SPEAKERS, "%s: a briefing line" % name)
        check(2 <= len(s.dialogue) <= 4, "%s: a 2-4 line dialogue (%d)" % (name, len(s.dialogue)))
        check(1 <= len(s.outcome) <= 2, "%s: a 1-2 line outcome" % name)
        sched = story.chatter_schedule(lv)
        check(len(sched) == len(s.chatter) and len(sched) >= 3, "%s: every radio line fires (%d of %d)"
              % (name, len(sched), len(s.chatter)))
        check(all(1 <= w <= lv.wave_count() for w, _i, _c in sched), "%s: on the level's own waves" % name)
        check([w for w, _i, _c in sched] == sorted(w for w, _i, _c in sched), "%s: in wave order" % name)
        check(set(s.unlock) == set(lv.reward) and all(story.SPEAKERS[s.unlock[t].speaker].ref is t for t in lv.reward),
              "%s: each new tower speaks its own first line" % name)
        for w, _i, c in sched:   # boss taunts come with the boss
            if isinstance(c.when, EnemyType):
                check(any(gr.type is c.when for gr in lv.waves()[w - 1].groups), "%s: %s taunts on its wave" % (name, c.when))
        check(story.defeat_line(lv).text, "%s: a retry line" % name)
    # each tower unlocked by a level says its first line on the radio or in the dialogue of the next level
    for a, b in zip(LEVELS, LEVELS[1:]):
        for t in a.reward:
            key = next(k for k, sp in story.SPEAKERS.items() if sp.ref is t)
            spoken = [l.speaker for l in story.story(b).dialogue] + [c.speaker for c in story.story(b).chatter]
            check(key in spoken, "%s speaks in %s, the level after it joins" % (t.display_name, b.id))


def test_lines_are_short_and_the_cast_is_consistent(check):
    for l in story.all_lines():
        check(l.speaker in story.SPEAKERS, "known speaker %s" % l.speaker)
        check(_sentences(l.text) <= 3 and len(l.text) <= 175, "short: %r" % l.text)
    for lv in LEVELS:
        for c in story.story(lv).chatter:
            check(len(c.text) <= 125, "a radio line fits the bubble: %r" % c.text)
    # Palantir is the unknown sender until the consultant's invoice names it (level 7's outcome)
    reveal = campaign.level("outsourced")
    order = list(story.INTRO)
    for lv in LEVELS:
        s = story.story(lv)
        order += list(s.dialogue) + [story.Line(c.speaker, c.text) for c in s.chatter]
        if lv is reveal:
            named_at = len(order)
        order += list(s.outcome)
    speakers = [l.speaker for l in order]
    check("unknown" not in speakers[named_at:], "no unknown sender after the reveal")
    check("palantir" not in speakers[:named_at], "Palantir is not named before the reveal")
    check(any("PALANTIR" in l.text for l in story.story(reveal).outcome), "the reveal names it")
    check(all(story.SPEAKERS[k].kind == "intercept" for k in ("palantir", "unknown")),
          "Palantir only speaks through intercepted transmissions")
    for boss in ("bellarmine", "consultant", "threecom", "lockheed"):
        check(boss in speakers, "%s has its chapter" % boss)
    for t in campaign.TowerType.shop_towers():
        check(any(sp.ref is t for sp in story.SPEAKERS.values()), "%s has a voice" % t.display_name)
    check(story.CODE_LINE in story.ENDING and story.ENDING_TITLE, "the ending writes the last line of code")


# ====================================================================== the seen-scene log
def test_story_log_is_injectable_and_persists_in_its_own_node(check, tmp_path):
    mem = StoryLog.in_memory(["intro"])
    check(mem.is_seen("intro") and not mem.is_seen("ending"), "in-memory log seeded")
    check(mem.mark("ending") and not mem.mark("ending"), "mark() says whether the scene was new")
    check(mem._storage.saves == 1, "one save per new scene")
    p = StoryLog.persistent()
    check(StoryLog.persistent() is p and not p.seen(), "a shared persistent log, empty on a fresh install")
    p.mark("intro")
    p.mark(story.level_key("hello_world"))
    prefs._nodes.clear()
    StoryLog._shared = None
    q = StoryLog.persistent()
    check(q.seen() == {"intro", "level:hello_world"}, "read back from disk (%s)" % sorted(q.seen()))
    check((tmp_path / "prefs" / "lindefense_story.json").exists(), "in its own prefs node")
    check(not (tmp_path / "prefs" / "lindefense_campaign.json").exists(), "the campaign progress is untouched")
    prefs.node(story.NODE).put("seen", "garbage")
    check(not StoryLog(story._PrefsStorage()).seen(), "a damaged node reads as nothing seen")
    q.reset()
    check(not q.seen(), "reset")


# ====================================================================== the prologue and the dialogues
def test_prologue_plays_on_the_first_visit_only_and_skips(check):
    from lindefense.ui.campaign_screen import CampaignScreen, slot_rect
    app = _App()
    log = StoryLog.in_memory()
    s = CampaignScreen(app, CampaignProgress.in_memory(), story=log)
    check(s.is_story_open() and log.is_seen("intro"), "the prologue opens (and counts as seen) on the first visit")
    v = s.story_overlay
    check(" ".join(v.texts()) == story.INTRO[0].text and v.index == 1, "one line at a time")
    x, y, w, h = slot_rect(1)
    s.mouse_pressed(x + w / 2, y + h / 2)
    check(not s.is_briefing_open() and v.index == 2, "a click advances the scene, never the path below")
    s.key_pressed(_key(KeyEvent.VK_ENTER))
    s.key_pressed(_key(KeyEvent.VK_SPACE))
    check(v.index == 4, "Enter and Space advance (%d)" % v.index)
    s.frame(0.05)
    _paint(s)
    s.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not s.is_story_open() and app.calls == [], "Esc skips the rest and stays on the path")
    check(not CampaignScreen(app, CampaignProgress.in_memory(), story=log).is_story_open(), "never again")
    t = CampaignScreen(app, CampaignProgress.in_memory(), story=StoryLog.in_memory())
    w = t.story_overlay
    while not w.is_done():
        w.advance()
    joined = " ".join(w.texts())
    check(not t.is_story_open() and all(l.text in joined for l in story.INTRO), "played to the end, every line shown")


def test_pre_level_dialogue_plays_once_before_the_level(check):
    from lindefense.ui.campaign_screen import CampaignScreen
    app = _App()
    log = StoryLog.in_memory(["intro"])
    p = CampaignProgress.in_memory({"hello_world": 3})
    s = CampaignScreen(app, p, story=log)
    s.open_briefing("garbage_collection")
    go = next(b for b in s.briefing_buttons if b.get_text() == "START")
    s.mouse_pressed(go.get_x() + 10, go.get_y() + 10)
    check(s.is_story_open() and app.calls == [], "START plays the dialogue first")
    v = s.story_overlay
    lines = story.story("garbage_collection").dialogue
    while v.index < len(lines):
        s.key_pressed(_key(KeyEvent.VK_ENTER))
    check(v.next_button.get_text() == "START LEVEL", "the last line offers START LEVEL")
    check(all(l.text in " ".join(v.texts()) for l in lines), "every line of the dialogue was shown")
    s.key_pressed(_key(KeyEvent.VK_ENTER))
    check(app.calls == ["start:garbage_collection"] and not s.is_story_open(), "then the level starts (%s)" % app.calls)
    check(log.is_seen("level:garbage_collection"), "and the dialogue counts as seen")
    s.start("garbage_collection")
    check(app.calls[-1] == "start:garbage_collection" and len(app.calls) == 2 and not s.is_story_open(),
          "a second START plays the level at once")
    # SKIP and Esc both skip straight to the level
    s2 = CampaignScreen(app, CampaignProgress.in_memory({lv.id: 3 for lv in LEVELS}), story=StoryLog.in_memory(["intro"]))
    s2.start("legacy_code")
    skip = s2.story_overlay.skip_button
    s2.mouse_pressed(skip.get_x() + 5, skip.get_y() + 5)
    check(app.calls[-1] == "start:legacy_code", "SKIP starts the level")
    s2.start("campus_tour")
    s2.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(app.calls[-1] == "start:campus_tour" and not s2.is_story_open(), "Esc too")


def test_reduced_motion_shows_each_line_at_once(check):
    from lindefense.ui import story_view as SV
    DisplaySettings.get().set_reduced_motion(True)
    v = SV.scene_view(story.INTRO_KEY)
    r = v.rows[0]
    check(r.opacity == 1.0 and abs(r.get_y() - r.base_y) < 1e-9, "no fade or slide with REDUCED MOTION")
    v.advance()
    check(v.index == 2, "a click goes straight to the next line")
    DisplaySettings.get().set_reduced_motion(False)
    w = SV.scene_view(story.INTRO_KEY)
    check(w.rows[0].opacity < 1.0, "normally the line fades in")
    w.advance()
    check(w.index == 2 and w.rows[0].opacity == 1.0, "a click snaps it into place and shows the next")


def test_palantir_uses_the_colour_blind_warning_colour(check):
    from lindefense.ui import story_view as SV
    from lindefense.ui.cyber import Cyber
    check(SV.accent("palantir") == Cyber.RED, "red by default")
    DisplaySettings.get().set_colour_blind(True)
    check(SV.accent("palantir") == Cyber.CB_BAD and SV.accent("unknown") == Cyber.CB_BAD, "orange with COLOUR-BLIND SAFE")
    check(SV.accent("lindemann") == SV.accent("lindemann"), "the cast keeps its colours")


# ====================================================================== the codex
def test_codex_replays_the_unlocked_scenes(check):
    from lindefense.ui import story_view as SV
    from lindefense.ui.campaign_screen import CampaignScreen
    app = _App()
    log = StoryLog.in_memory(["intro", "level:hello_world", "level:garbage_collection", "level:legacy_code"])
    p = CampaignProgress.in_memory({"hello_world": 3, "garbage_collection": 2})
    s = CampaignScreen(app, p, story=log)
    btn = next(b for b in s.buttons if b.get_text() == "STORY")
    s.mouse_pressed(btn.get_x() + 5, btn.get_y() + 5)
    c = s.story_overlay
    check(isinstance(c, SV.StoryCodex), "STORY opens the codex")
    check(c.keys() == story.scene_keys(), "every scene, in story order")
    ok = {k: o for _r, k, _f, _b, o in c.cards}
    check(ok["intro"] and ok["level:hello_world"] and ok["level:legacy_code"], "seen or completed scenes are open")
    check(not ok["level:campus_tour"] and not ok["ending"], "the rest are locked")
    rects = [r for r, *_ in c.cards]
    check(all(_inside(r, (0, 0, 1600, 1000)) for r in rects) and _inside(c.rect, (0, 0, 1600, 1000)), "inside the screen")
    check(not [(a, b) for i, a in enumerate(rects) for b in rects[i + 1:] if _overlap(a, b)], "no overlaps")
    s.frame(0.05)
    _paint(s)
    locked = next(r for r, k, *_ in c.cards if k == "level:campus_tour")
    s.mouse_pressed(locked[0] + 20, locked[1] + 20)
    check(s.story_overlay is c, "a locked scene does not play")
    card = next(r for r, k, *_ in c.cards if k == "level:garbage_collection")
    s.mouse_pressed(card[0] + 20, card[1] + 20)
    v = s.story_overlay
    check(isinstance(v, SV.StoryView), "an open scene replays")
    while v.index < len(v.rows):
        v.advance()
    joined = " ".join(v.texts())
    gs = story.story("garbage_collection")
    check(gs.outcome[0].text in joined and gs.dialogue[0].text in joined, "the replay plays the dialogue and outcome")
    texts = [l.text for l in story.replay_lines("level:garbage_collection", p)]
    check(any(c.text == t for c in gs.chatter for t in texts) and gs.outcome[0] in story.replay_lines(
        "level:garbage_collection", p), "a completed level replays its radio log and outcome too")
    check(story.replay_lines("level:legacy_code", p) == list(story.story("legacy_code").dialogue),
          "a seen but unfinished level replays its dialogue only")
    check(v.next_button.get_text() == "BACK TO STORY", "the replay returns to the codex")
    v.advance()
    check(isinstance(s.story_overlay, SV.StoryCodex), "back in the codex")
    s.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(not s.is_story_open() and app.calls == [], "Esc closes it; nothing started")
    # the ending, once the campaign is finished
    done = CampaignScreen(app, CampaignProgress.in_memory({lv.id: 3 for lv in LEVELS}), story=StoryLog.in_memory(["intro"]))
    done.open_codex()
    end = next(r for r, k, *_ in done.story_overlay.cards if k == "ending")
    done.mouse_pressed(end[0] + 20, end[1] + 20)
    e = done.story_overlay
    check(isinstance(e, SV.EndingReplay) and story.ENDING_TITLE in e.texts() and story.CODE_LINE in e.texts(),
          "the ending replays from the codex")
    done.frame(0.5)
    _paint(done)
    done.key_pressed(_key(KeyEvent.VK_ESCAPE))
    check(isinstance(done.story_overlay, SV.StoryCodex), "and returns to it")


# ====================================================================== layouts
def test_story_layouts_fit_the_screen(check):
    from lindefense.ui import story_view as SV
    from lindefense.ui.ability_bar import AbilityBar
    from lindefense.ui.campaign_end_view import PANEL_W
    from lindefense.ui.campaign_screen import BRIEF_H, BRIEF_W, BRIEF_X, BRIEF_Y, CampaignScreen
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.ui import Ui
    screen = (0, 0, 1600, 1000)
    for key in story.scene_keys()[:-1]:
        for replay in (False, True):
            v = SV.scene_view(key, CampaignProgress.in_memory({lv.id: 3 for lv in LEVELS}), replay=replay)
            check(_inside(v.bounds(), screen), "%s fits the screen" % key)
            while v.index < len(v.rows):
                v.advance()
                shown = [r for r in v.rows if r.is_visible()]
                bottom = max(r.base_y + r.height() for r in shown)
                check(bottom <= v.py + v.ph - SV.StoryView.FOOT + 4, "%s: the lines stay above the buttons" % key)
                check(min(r.base_y for r in shown) >= v.py + SV.StoryView.HEAD - 2, "%s: and below the title" % key)
    app = _App()
    full = CampaignProgress.in_memory({lv.id: 3 for lv in LEVELS})
    for lv in LEVELS:
        s = CampaignScreen(app, full, lv.id, story=StoryLog.in_memory(story.scene_keys()))
        x, y, w, h = s.story_card
        check(_inside(s.story_card, (BRIEF_X, BRIEF_Y, BRIEF_W, BRIEF_H)), "%s: the story card is in the briefing" % lv.id)
        check(y + h <= BRIEF_Y + BRIEF_H - 18, "%s: above the briefing's edge" % lv.id)
        labels = [o for o in s.briefing if hasattr(o, "get_label") and o.get_x() < x + w and o.get_x() >= x - 1
                  and not (y <= o.get_y() <= y + h)]
        check(all(o.get_y() < y - 2 for o in labels), "%s: below everything else in its column" % lv.id)
        buttons = [(b.get_x(), b.get_y(), b.get_w(), b.get_h()) for b in s.briefing_buttons]
        check(not any(_overlap(s.story_card, r) for r in buttons), "%s: clear of the buttons" % lv.id)
        # the LEVEL COMPLETE panel with the story rows (a first clear: the outcome and the new towers' lines)
        g = campaign.new_game(lv, 5)
        gs = GameScreen(app, g)
        gs.story_log = StoryLog.in_memory(story.scene_keys())
        gs.epilogue_done = True
        g._state = State.VICTORY
        gs.frame(0.02)
        blk = gs.story_block
        bx, by = blk.get_x(), blk.get_y()
        bh = max(r.get_y() + r.height() for r in blk.rows) + 14
        world = (Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H)
        frame = next(o for o in gs.overlay if type(o).__name__ == "Chamfer" and o.get_w() == PANEL_W)
        panel = (frame.get_x(), frame.get_y(), frame.get_w(), frame.get_h())
        check(_inside(panel, world), "%s: the panel fits the playfield" % lv.id)
        check(_inside((bx, by, 716, bh), panel), "%s: the story rows sit in the panel" % lv.id)
        check(all(by + bh <= b.get_y() - 8 for b in gs.overlay_buttons), "%s: above the buttons" % lv.id)
    # the chatter bubble: lower left of the playfield, above the ability bar and clear of the pause banner
    g = campaign.new_game("last_line_of_code", 5)
    gs = GameScreen(app, g)
    gs.story_log = StoryLog.in_memory()
    for c in story.story("last_line_of_code").chatter:
        gs.chatter._build(story.Line(c.speaker, c.text))
        x, y, w, h = gs.chatter.get_rect()
        check(_inside((x, y, w, h), (Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H)), "the bubble is on the playfield")
        check(y + h <= AbilityBar.Y - 34 and x + w < Ui.WORLD_W / 2 - 200, "clear of the ability bar, hints and PAUSED")
        check(len(gs.chatter.texts()) <= 4, "at most four lines")


# ====================================================================== chatter
def _drive(g, gs, frames, last, kill_at=120.0):
    """Runs the screen like the app (8 steps a frame): starts waves up to `last`, kills what gets kill_at px in."""
    for _ in range(frames):
        if g.get_state() is not State.PLAYING:
            break
        if g.get_wave_manager().can_start_next_wave() and g.get_wave() < last:
            g.start_next_wave()
        for e in list(g.get_enemy_manager().get_enemies()):
            if e.is_alive() and e.get_distance() > kill_at:
                kill_outright(g, e)
        gs.frame(8 * DT)
        g.get_events().clear()


@pytest.fixture
def step_trace(monkeypatch):
    """Per-game digests of every Game.step (the simtrace fold, plus the RNG)."""
    from test_savegame import digest
    traces = {}
    step = Game.step

    def traced(self, dt):
        r = step(self, dt)
        traces.setdefault(id(self), []).append(digest(self))
        return r
    monkeypatch.setattr(Game, "step", traced)
    return traces


def test_chatter_fires_at_its_waves_and_never_changes_the_game(check, step_trace, monkeypatch):
    from lindefense.enemy.enemy import Enemy
    from lindefense.tower.tower import Tower
    from lindefense.ui.game_screen import GameScreen
    lv = campaign.level("hello_world")
    sched = story.chatter_schedule(lv)
    monkeypatch.setattr(Enemy, "_next_id", Enemy._next_id)   # restored afterwards
    monkeypatch.setattr(Tower, "_next_id", Tower._next_id)

    def run(log):
        """One run of the level through the game screen, from the same entity ids; returns its game and screen."""
        Enemy._next_id = Tower._next_id = 1
        g = campaign.new_game(lv, 11)
        gs = GameScreen(_App(), g)
        gs.story_log = log
        shown_at = {}
        for _ in range(2500):
            _drive(g, gs, 1, lv.wave_count())
            cur = gs.chatter.get_current()
            if cur is not None and cur not in shown_at:
                shown_at[cur] = g.get_wave()
            if g.get_state() is not State.PLAYING:
                break
        return g, gs, shown_at
    a, sa, shown_at = run(StoryLog.in_memory())
    b, sb, _ = run(StoryLog.in_memory(story.chatter_key(lv, i) for i in range(len(story.story(lv).chatter))))
    ta, tb = step_trace[id(a)], step_trace[id(b)]
    check(len(ta) > 1000 and ta == tb, "the twin runs are identical step by step, chatter shown or not (%d steps)"
          % len(ta))
    check(a.get_state() is State.VICTORY, "the level was played to the end (%s, wave %d)" % (a.get_state(), a.get_wave()))
    check([w for w, _i in sa.chatter.shown] == [w for w, _i, _c in sched], "every line fired at its wave (%s vs %s)"
          % (sa.chatter.shown, [w for w, _i, _c in sched]))
    check(all(shown_at.get(c) == w for w, _i, c in sched), "while that wave ran (%s)" % shown_at)
    check(not sb.chatter.shown, "lines already heard are not repeated")
    check(all(sa.story_log.is_seen(story.chatter_key(lv, i)) for _w, i, _c in sched), "each line is logged as heard")
    before = (Enemy._next_id, Tower._next_id)
    from lindefense.ui import story_view as SV
    for key in story.SPEAKERS:
        SV.portrait(key, 60)
    check((Enemy._next_id, Tower._next_id) == before, "drawing the cast takes no entity ids from the game")
    plain = GameScreen(_App(), Game(maps.create(0), 3))
    check(plain.chatter is None, "classic games have no radio chatter")


def test_chatter_waits_behind_overlays_and_fades_under_the_pointer(check):
    from lindefense.ui.game_screen import GameScreen
    g = campaign.new_game("hello_world", 4)
    gs = GameScreen(_App(), g)
    gs.story_log = StoryLog.in_memory()
    gs.toggle_help()
    g.start_next_wave()
    gs.frame(DT)
    check(gs.chatter.get_current() is None and not gs.chatter.is_visible(), "nothing while HELP covers the map")
    gs.toggle_help()
    gs.frame(DT)
    check(gs.chatter.get_current() is not None and gs.chatter.is_visible(), "the line plays once the map is back")
    for _ in range(30):
        gs.frame(DT)
    check(gs.chatter.opacity > 0.9, "fully shown")
    x, y, w, h = gs.chatter.get_rect()
    gs.mouse_moved(x + w / 2, y + h / 2)
    gs.frame(DT)
    check(gs.chatter.opacity < 0.3, "see-through under the pointer")
    gs.mouse_moved(600, 300)
    for _ in range(600):
        gs.frame(DT)
    check(gs.chatter.get_current() is None and not gs.chatter.is_visible(), "and gone after a few seconds")


# ====================================================================== panels and the ending
def test_outcome_rows_on_the_level_end_panels(check):
    from lindefense.ui.game_screen import GameScreen
    lv = campaign.level("outsourced")
    g = campaign.new_game(lv, 5)
    gs = GameScreen(_App(), g)
    g._state = State.VICTORY
    gs.frame(0.02)
    rows = [" ".join(r.texts()) for r in gs.story_block.rows]
    want = list(story.story(lv).outcome) + story.unlock_lines(lv)
    check(len(rows) == len(want) and all(l.text.split(" ")[0] in r for l, r in zip(want, rows)),
          "a first clear: the outcome, then each new tower's first line (%s)" % rows)
    p = CampaignProgress.in_memory({lv.id: 1})
    h = campaign.new_game(lv, 5)
    hs = GameScreen(_App(), h)
    hs.set_run_session(R.RunSession(R.Records.in_memory(), h, False, p))
    h._state = State.VICTORY
    hs.frame(0.02)
    check(len(hs.story_block.rows) == len(story.story(lv).outcome), "a repeat clear: the outcome only")
    d = campaign.new_game(lv, 5)
    ds = GameScreen(_App(), d)
    d._lives = 0
    d._state = State.DEFEAT
    ds.frame(0.02)
    check([r.line for r in ds.story_block.rows] == [story.defeat_line(lv)], "a defeat: Mr. Lindemann's retry line")


def test_campaign_ending_replaces_the_epilogue_for_campaign_runs_only(check):
    from lindefense.ui import story_view as SV
    from lindefense.ui.game_screen import GameScreen
    from lindefense.ui.victory_epilogue import VictoryEpilogue
    log = StoryLog.in_memory()
    g = campaign.new_game(campaign.finale(), 5)
    gs = GameScreen(_App(), g)
    gs.story_log = log
    g._state = State.VICTORY
    gs.frame(0.02)
    check(isinstance(gs.epilogue, SV.CampaignEnding), "the finale plays the campaign's ending")
    texts = gs.epilogue.texts()
    check(story.ENDING_TITLE in texts and story.CODE_LINE in texts and VictoryEpilogue.BYLINE in texts,
          "its story, the last line of code and the credits")
    check(not any(t in texts for t in VictoryEpilogue.STORY), "instead of the classic story")
    check(log.is_seen(story.ENDING_KEY), "it counts as seen")
    gs.frame(0.5)
    check(gs.is_epilogue_open(), "and stays up until skipped")
    _paint(gs)
    gs.key_pressed(_key(KeyEvent.VK_ESCAPE))
    labels = [o.get_label() for o in gs.overlay if hasattr(o, "get_label")]
    check("CAMPAIGN COMPLETE" in labels, "then CAMPAIGN COMPLETE")
    check(story.story(campaign.finale()).outcome[0] == gs.story_block.rows[0].line, "with the finale's outcome")
    again = campaign.new_game(campaign.finale(), 6)
    gs2 = GameScreen(_App(), again)
    gs2.story_log = log
    again._state = State.VICTORY
    gs2.frame(0.02)
    check(not gs2.is_epilogue_open(), "a second finale win goes straight to the panel (the codex replays the ending)")
    classic = Game(maps.create(0), 5)
    cs = GameScreen(_App(), classic)
    cs.story_log = StoryLog.in_memory()
    classic._state = State.VICTORY
    cs.frame(0.02)
    check(type(cs.epilogue) is VictoryEpilogue, "a classic victory keeps the classic epilogue")
    ct = cs.epilogue.texts()
    check(VictoryEpilogue.TITLE in ct and VictoryEpilogue.STORY[-1] in ct and story.ENDING_TITLE not in ct,
          "with its own story")
    level = campaign.new_game("hello_world", 5)
    ls = GameScreen(_App(), level)
    level._state = State.VICTORY
    ls.frame(0.02)
    check(not ls.is_epilogue_open(), "other campaign levels have no epilogue")


# ====================================================================== Save & Continue
def test_save_and_continue_keeps_the_story_state(check):
    from lindefense.ui.game_screen import GameScreen
    lv = campaign.level("outsourced")
    sched = story.chatter_schedule(lv)
    log = StoryLog.in_memory()
    g = campaign.new_game(lv, 9)
    gs = GameScreen(_App(), g)
    gs.story_log = log
    g.start_next_wave()
    for _ in range(30):
        gs.frame(DT)
    first = story.chatter_key(lv, sched[0][1])
    check(log.is_seen(first) and gs.chatter.shown == [(1, sched[0][1])], "wave 1's line played")
    mid = savegame.dumps(g)
    h = savegame.loads(mid)
    hs = GameScreen(_App(), h)
    hs.story_log = log
    for _ in range(30):
        hs.frame(DT)
    check(not hs.chatter.shown, "continued mid-wave: the line already heard is not replayed")
    fresh = StoryLog.in_memory()
    k = savegame.loads(mid)
    ks = GameScreen(_App(), k)
    ks.story_log = fresh
    for _ in range(30):
        ks.frame(DT)
    check(ks.chatter.shown == [(1, sched[0][1])], "a line not heard yet still plays for the wave being continued")
    # continued between waves 2 and 3: the earlier waves' lines stay in the past, later ones still come
    for _ in range(4000):
        if g.get_wave_manager().can_start_next_wave() and g.get_wave() < 2:
            g.start_next_wave()
        for e in list(g.get_enemy_manager().get_enemies()):
            if e.is_alive():
                kill_outright(g, e)
        g.step(DT)
        g.get_events().clear()
        if g.get_wave() >= 2 and not g.get_wave_manager().is_wave_active():
            break
    check(g.get_wave() == 2 and not g.get_wave_manager().is_wave_active(), "saved between waves")
    later = StoryLog.in_memory()
    m = savegame.loads(savegame.dumps(g))
    ms = GameScreen(_App(), m)
    ms.story_log = later
    ms.frame(DT)
    check(not ms.chatter.shown and not ms.chatter.queue, "nothing replays for waves already played")
    _drive(m, ms, 1500, sched[1][0])
    check((sched[1][0], sched[1][1]) in ms.chatter.shown, "the next scripted wave still brings its line (%s)"
          % ms.chatter.shown)
    check(not later.is_seen(first), "the skipped wave-1 line stays unheard for a later attempt")


def test_continue_from_the_menu_does_not_replay_the_dialogue(check):
    from test_campaign import _real_app
    from lindefense.ui.campaign_screen import CampaignScreen
    app = _real_app()
    app.show_campaign()
    cs = app.get_map_select()
    cs.story_overlay.skip()
    cs.open_briefing(1)
    cs.start(1)
    check(cs.is_story_open() and app.get_game() is None, "the first START plays level 1's dialogue")
    cs.story_overlay.skip()
    g = app.get_game()
    check(g is not None and g.get_campaign().level_id == "hello_world", "then the level")
    g.start_next_wave()
    app.frame(1 / 60.0)
    app.quit_level()
    check(isinstance(app.get_map_select(), CampaignScreen) and not app.get_map_select().is_story_open(),
          "QUIT LEVEL returns to the campaign with no scene")
    seen = StoryLog.persistent().seen()
    app.continue_run()
    check(app.get_game() is not None and app.get_game().get_wave() == 1, "CONTINUE restores the level directly")
    check(StoryLog.persistent().seen() == seen, "the story state is unchanged by the restore")
    app.quit_level()
    app.get_map_select().start(1)
    check(app.get_game() is not None, "a seen dialogue is not replayed on the next START")
