"""The guided tutorial (TUTORIAL on the main menu, and the campaign's optional first node): seven short waves on The
Silicon Circuit, one idea each, learnt by doing.

  wave 1  BASICS          build a tower, start a wave
  wave 2  UPGRADES        select it, read the upgrade preview, upgrade, targeting
  wave 3  SPLITTERS       the next-wave preview; enemies that split
  wave 4  LEAD            Lead-type shrugs off Sharp damage: the preview warns, build another damage type
  wave 5  CAMO            camo needs detection: the preview warns, build a detector
  wave 6  TACTICAL PAUSE  part of the wave takes the lower trace: pause (P), build while paused, resume
  wave 7  HEROES & BOSS   buy and deploy a practice hero, spend before the boss, the boss dock, its telegraphed ability

TutorialScript is pure logic (no ACM), so it is tested headlessly. It decides the steps, what each one points at (a
symbolic target such as ("card", TowerType.CLAUDE) or ("start",) that TutorialGuide resolves to the real widget), when a
step is done, the cash it tops up so nobody can get stuck, whether the next wave may start yet, and the one-off
contextual tips (first leak, camo slipping by, credits piling up, the first boss ability, the first tower selected).
Steps advance on the player's action; info cards have NEXT; SKIP TUTORIAL works at any time and RESUME TUTORIAL brings it
back. The view state it reads (what is being placed, the selected tower, the Hero Store, the shop tab) comes from an
optional `ui` object, the GameScreen in the game; without one the script sees no selection and a closed store.

The match itself (create_game): map 0, O(1), no Patch Notes, a fixed seed (the tutorial is the same every time), its own
waves (wave/tutorial_waves.py) and the Game's default in-memory hero collection, so practice unlocks never reach the
saved Hero Store. The app never saves or records it (savegame.can_save and RunSummary see the tutorial flag).
"""
from lindefense.combat.hit_spec import DamageType
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import Faction, TowerType
from lindefense.ui import intel
from lindefense.wave import tutorial_waves

SEED = 20261110            # fixed: the tutorial plays the same every time
CHAPTERS = ("Basics", "Upgrades", "Splitters", "Lead", "Camo", "Tactical pause", "Heroes & boss")
CASH_TIP_AMOUNT = 1500     # credits piling up: at least this much ...
CASH_TIP_SECONDS = 12.0    # ... unspent for this long while a wave runs
HERO_GRANT_CAP = 4200      # the most the Hero Store step tops up to (the priciest unlock plus its deploy cost)


def create_game(seed=SEED):
    """A fresh tutorial match (TUTORIAL on the main menu, RESTART / RETRY in it)."""
    g = Game(maps.create(tutorial_waves.MAP_INDEX), seed, Difficulty.O1)
    g.get_wave_manager().set_wave_list(tutorial_waves.create())
    g.set_seed_fixed(True)   # RESTART replays the same tutorial
    return g


def is_tutorial_game(game):
    """A tutorial match: it has its own wave list and is not a campaign level (campaign levels have one too)."""
    return (game is not None and game.get_wave_manager().get_wave_list() is not None
            and getattr(game, "get_campaign", lambda: None)() is None)


class Step:
    """One tutorial step. kind: INFO (NEXT advances; done() may also end it), ACTION (ends when done()) or WATCH (ends
    when done(), no NEXT). text / title / target may be callables taking the script. fund tops the credits up to what
    the step needs, on entry and every frame (it never takes any away). wave: the wave this step lets the player
    start. store: the card stays up while the Hero Store is open. pause: the step pauses the game while it is read and
    NEXT resumes it."""
    INFO = "info"
    ACTION = "action"
    WATCH = "watch"

    def __init__(self, key, chapter, kind, title, text, target=None, done=None, fund=None, wave=0, store=False,
                 pause=False):
        self.key = key
        self.chapter = chapter
        self.kind = kind
        self.title = title
        self.text = text
        self.target = target
        self.done = done
        self.fund = fund
        self.wave = wave
        self.store = store
        self.pause = pause

    @property
    def action(self):
        return self.kind == Step.ACTION

    def __repr__(self):
        return "Step(%s)" % self.key


class Tip:
    """A contextual tip, shown once per tutorial. tone: 'bad', 'warn' or 'info' (the view picks the colour)."""

    def __init__(self, key, title, text, tone):
        self.key = key
        self.title = title
        self.text = text
        self.tone = tone

    def __repr__(self):
        return "Tip(%s)" % self.key


class TutorialScript:
    Step = Step
    Tip = Tip

    def __init__(self, game, ui=None):
        self.game = game
        self.ui = ui
        self.f_index = 0
        self.finished = False
        self.completed = False
        self.skipped = False
        self.granted = 0.0               # every credit the tutorial has topped up
        self.paused_by_step = False
        self.snap = {}                   # values remembered when the current step began
        self.tips_shown = set()
        self.tips_fired = []             # tips in the order they fired (tests, the view's queue)
        self.tip_queue = []
        self.lives_seen = game.get_lives()
        self.cash_time = 0.0
        self.spots = {}
        self.steps = self.build_steps()
        self.enter()

    # ------------------------------------------------------------------ state
    def set_ui(self, ui):
        self.ui = ui

    def current(self):
        return self.steps[min(self.f_index, len(self.steps) - 1)]

    def index(self):
        return self.f_index

    def count(self):
        return len(self.steps)

    def chapter(self):
        return self.current().chapter

    def chapter_count(self):
        return len(CHAPTERS)

    def chapter_name(self):
        return CHAPTERS[self.chapter() - 1]

    def is_finished(self):
        """True once the tutorial is over: completed, or skipped (RESUME TUTORIAL can bring a skipped one back)."""
        return self.finished

    def is_completed(self):
        return self.completed

    def is_skipped(self):
        return self.skipped

    def title(self):
        t = self.current().title
        return t(self) if callable(t) else t

    def text(self):
        t = self.current().text
        return t(self) if callable(t) else t

    def target(self):
        """Symbolic target of the current step (None: nothing to point at). See TutorialGuide.resolve."""
        if self.finished:
            return None
        t = self.current().target
        return t(self) if callable(t) else t

    def grant_paid(self):
        return self.granted > 0

    # ------------------------------------------------------------------ flow
    def next(self):
        """NEXT on an info card (it also moves on from any step, which the tests use)."""
        if self.finished:
            return
        self.leave()
        if self.f_index >= len(self.steps) - 1:
            self.finish(True)
            return
        self.f_index += 1
        self.enter()
        self.settle()

    def skip_all(self):
        """SKIP TUTORIAL: ends it early (the completion card offers what to do next, or RESUME TUTORIAL)."""
        if self.finished:
            return
        self.leave()
        self.skipped = True
        self.finished = True

    def resume(self):
        """RESUME TUTORIAL after a skip: back to the step it was on."""
        if not self.skipped:
            return
        self.skipped = False
        self.finished = False
        self.enter()
        self.settle()

    def finish(self, completed):
        self.finished = True
        self.completed = completed
        self.f_index = len(self.steps) - 1

    def enter(self):
        s = self.current()
        self.snap = {"tiers": self.tier_sum(), "towers": len(self.player_towers()),
                     "targeting": {t.get_id(): t.get_targeting() for t in self.player_towers()}}
        if s.fund is not None and not self.is_done(s):
            s.fund(self)
        if s.pause and not self.is_done(s) and not self.game.is_paused():
            self.game.set_paused(True)
            self.paused_by_step = True

    def leave(self):
        if self.current().key in TutorialScript.BUILD_STEPS and self.placing() is not None \
                and hasattr(self.ui, "begin_placing"):
            self.ui.begin_placing(None)   # one tower per step: drop the placement mode the game would keep armed
        if self.paused_by_step:
            self.paused_by_step = False
            if self.game.is_paused() and not self.menu_open():
                self.game.set_paused(False)

    def is_done(self, s):
        return s.done is not None and bool(s.done(self))

    def settle(self):
        """Moves past every step whose goal is already met (a few per call at most)."""
        for _ in range(len(self.steps)):
            if self.finished or not self.is_done(self.current()):
                return
            self.next_from_done()

    def next_from_done(self):
        self.leave()
        if self.f_index >= len(self.steps) - 1:
            self.finish(True)
            return
        self.f_index += 1
        self.enter()

    def update(self, dt=0.0):
        """Advances steps whose goal is met, keeps the Hero Store step funded and fires contextual tips. Every frame."""
        if self.finished:
            return
        self.settle()
        s = self.current()
        if not self.finished and s.fund is not None and not self.is_done(s):
            s.fund(self)
        self.watch_tips(dt)

    def allows_wave_start(self):
        """The next wave may start only on the step that asks for it (afterwards, or once skipped, always)."""
        if self.finished:
            return True
        return self.current().wave == self.game.get_wave() + 1

    def allows_auto(self):
        """AUTO stays off while the tutorial runs: waves wait for the player."""
        return self.finished

    def progress(self):
        """0..1 through the steps."""
        return 1.0 if self.finished else self.f_index / float(max(1, len(self.steps) - 1))

    # ------------------------------------------------------------------ game / view reads
    def player_towers(self):
        return [t for t in self.game.get_tower_manager().get_player_towers() if t.is_alive()]

    def attack_towers(self):
        return intel.attack_towers(self.game)

    def tier_sum(self):
        return sum(t.get_tier() for t in self.player_towers())

    def hero(self):
        return next((t for t in self.player_towers() if t.get_type().is_hero()), None)

    def first_tower(self):
        ts = [t for t in self.player_towers() if not t.get_type().is_hero()]
        return ts[0] if ts else (self.player_towers() or [None])[0]

    def placing(self):
        return None if self.ui is None else self.ui.get_placing()

    def selected(self):
        t = None if self.ui is None else self.ui.get_selected_tower()
        return t if t is not None and t.is_alive() else None

    def store_open(self):
        return self.ui is not None and self.ui.is_hero_store_open()

    def menu_open(self):
        return self.ui is not None and hasattr(self.ui, "is_menu_open") and self.ui.is_menu_open()

    def tactically_paused(self):
        if self.ui is not None and hasattr(self.ui, "is_tactically_paused"):
            return self.ui.is_tactically_paused()
        return self.game.is_paused()

    def wave_live(self):
        return self.game.get_wave_manager().is_wave_active()

    def bosses(self):
        return [b for b in self.game.get_active_bosses() if b.is_alive()]

    def ensure_cash(self, amount):
        """Tops the credits up to `amount` (never takes any away)."""
        need = amount - self.game.get_cash()
        if need > 0:
            self.game.add_cash(need, None)
            self.granted += need

    def fund_selected_hero(self):
        sel = getattr(self.ui, "hero_store_selection", None) if self.ui is not None else None
        h = sel if sel is not None and sel.is_hero() else TowerType.heroes()[0]
        if any(self.game.is_hero_unlocked(x) for x in TowerType.heroes()):
            return
        self.ensure_cash(min(HERO_GRANT_CAP, catalog.get(h).unlock_cost + shop.price_of(h, self.game)))

    # ------------------------------------------------------------------ spots on the map
    def suggest_spot(self, type_, lane):
        """A free spot beside `lane` from which a `type_` covers the most track (earliest such spot on ties), or None."""
        towers = len(self.game.get_tower_manager().get_towers())
        key = (type_, lane, towers)
        if key not in self.spots:
            self.spots[key] = self.find_spot(type_, lane)
        return self.spots[key]

    def find_spot(self, type_, lane):
        g = self.game
        routes = g.get_map().get_routes()
        r = routes[min(lane, len(routes) - 1)]
        d = catalog.get(type_)
        reach = max(60.0, d.base_stats.range * 0.85)
        off = g.get_map().min_track_clearance(d.radius) + 8
        length = r.get_total_length()
        samples = [r.position_at(x) for x in range(0, int(length), 25)]
        tm = g.get_tower_manager()
        best, best_score = None, -1
        dist = 30.0
        while dist < length - 30:
            a, b = r.position_at(dist - 2), r.position_at(dist + 2)
            dx, dy = b.x - a.x, b.y - a.y
            n = max(1e-9, (dx * dx + dy * dy) ** 0.5)
            for side in (1, -1):
                p = Vec(round(a.x + dx / 2 - side * dy / n * off), round(a.y + dy / 2 + side * dx / n * off))
                if tm.placement_problem(type_, p) not in (None, "Not enough cash"):
                    continue
                score = sum(1 for q in samples if q.dist(p) <= reach)
                if score > best_score:
                    best, best_score = p, score
            dist += 30.0
        return best

    def build_target(self, type_, lane, accept=None):
        """Pick `type_` in the shop (opening its tab or the collapsed shop first), then a spot by `lane`. While another
        tower that also meets the goal (accept) is being placed, the spot is for that one."""
        if self.placing_ok(accept):
            return ("spot", self.suggest_spot(self.placing(), lane))
        return self.shop_target(type_)

    def placing_ok(self, accept=None):
        p = self.placing()
        return p is not None and not p.is_hero() and (accept is None or accept(p))

    @staticmethod
    def hurts_lead(type_):
        h = catalog.get(type_).base_stats.hit
        return not catalog.get(type_).base_stats.is_support_only() and (h.type is not DamageType.SHARP or h.ignores_resistance)

    @staticmethod
    def sees_camo(type_):
        st = catalog.get(type_).base_stats
        return bool(st.sees_camo or st.aura_detection or st.has("revealAllCamo"))

    def shop_target(self, type_):
        side = None if self.ui is None else self.ui.get_side_panel()
        if side is None:
            return ("card", type_)
        if side.is_shop_collapsed():
            return ("expand",)
        if not side.is_all_mode() and side.get_tab() is not type_.faction:
            return ("tab", type_.faction)
        return ("card", type_)

    def shop_hint(self, type_):
        """What to click in the shop for `type_`, in words."""
        t = self.shop_target(type_)
        if t[0] == "expand":
            return "Press EXPAND SHOP, then pick " + type_.display_name.upper()
        if t[0] == "tab":
            return "Open the " + type_.faction.label.upper() + " tab, then pick " + type_.display_name.upper()
        return "Pick " + type_.display_name.upper() + " in the ARMORY"

    # ------------------------------------------------------------------ the steps
    def build_steps(self):
        S = Step
        T = TowerType
        A, B = tutorial_waves.LANE_A, tutorial_waves.LANE_B

        def start(n, title, body):
            def text(s):
                if s.wave_live():
                    return "Wave %d is still running. START WAVE %d unlocks once it is cleared." % (s.game.get_wave(), n)
                return body + " Press START WAVE (or SPACE)."
            return S("start%d" % n, n, S.ACTION, title, text, ("start",), lambda s: s.game.get_wave() >= n, wave=n)

        def build_text(type_, why, lane_words, accept=None):
            def text(s):
                if s.placing_ok(accept):
                    return ("Now click a free spot beside the " + lane_words + " (the highlighted one is a good pick); the "
                            "ring shows its reach. Right-click cancels.")
                return why + " " + s.shop_hint(type_) + "."
            return text

        def wave_done(n):
            return lambda s: s.game.get_last_completed_wave() >= n

        steps = [
            # ---- 1 BASICS
            S("welcome", 1, S.INFO, "Defend the exit",
              "Enemies follow the glowing track from IN to OUT. Each one that gets out costs integrity (lives); credits "
              "build towers. Seven short waves, one idea each.", ("chips",)),
            S("build", 1, S.ACTION, "Build your first tower",
              build_text(T.CLAUDE, "Towers fire on their own.", "upper trace"),
              lambda s: s.build_target(T.CLAUDE, A), lambda s: len(s.player_towers()) > 0,
              fund=lambda s: s.ensure_cash(shop.price_of(T.CLAUDE, s.game))),
            start(1, "Start the first wave", "Waves start only when you say so."),
            S("watch1", 1, S.INFO, "It fires by itself",
              "Every kill pays credits and each cleared wave pays a bonus. 1x / 2x / 3x (keys 1-3) set the game speed.",
              ("speed",), wave_done(1)),
            # ---- 2 UPGRADES
            S("select", 2, S.ACTION, "Select your tower", TutorialScript.select_text, TutorialScript.select_target,
              lambda s: s.selected() is not None,
              fund=lambda s: s.fund_first_upgrade()),
            S("upgrade", 2, S.ACTION, "Read the preview, then upgrade", TutorialScript.upgrade_text, TutorialScript.upgrade_target,
              lambda s: any(t.get_tier() >= 1 for t in s.player_towers()),
              fund=lambda s: s.fund_first_upgrade()),
            S("targeting", 2, S.INFO, "Choose its targets", TutorialScript.targeting_text, TutorialScript.targeting_target,
              lambda s: any(s.snap["targeting"].get(t.get_id(), t.get_targeting()) is not t.get_targeting()
                            for t in s.player_towers())),
            start(2, "Start wave 2", "A denser stream this time."),
            # ---- 3 SPLITTERS
            S("preview3", 3, S.INFO, "Read the next wave",
              "This strip previews the next wave. Wave 3 brings splitters: a Dynamic Array sheds a Static Array, then a "
              "Primitive; a Merge Sort splits in two. Hover it for the full list.", ("preview",)),
            start(3, "Start wave 3", "One enemy becomes several, so keep an eye on the count."),
            # ---- 4 LEAD
            S("lead", 4, S.INFO, "Lead-type armour", TutorialScript.lead_text, ("preview",)),
            S("lead_fix", 4, S.ACTION, "Add another damage type",
              build_text(T.GPT, "GPT's Energy shots hurt Lead.", "upper trace", TutorialScript.hurts_lead),
              lambda s: s.build_target(T.GPT, A, TutorialScript.hurts_lead), lambda s: not intel.lead_blocked(s.game),
              fund=lambda s: s.ensure_cash(shop.price_of(T.GPT, s.game)) if intel.lead_blocked(s.game) else None),
            start(4, "Start wave 4", "Three Heap Sorts lead a group of Static Arrays."),
            # ---- 5 CAMO
            S("camo", 5, S.INFO, "Camo needs detection", TutorialScript.camo_text, ("preview",)),
            S("camo_fix", 5, S.ACTION, "Build a detector",
              build_text(T.GROK, "Grok sees camo.", "upper trace", TutorialScript.sees_camo),
              lambda s: s.build_target(T.GROK, A, TutorialScript.sees_camo), lambda s: intel.camo_covered(s.game),
              fund=lambda s: s.ensure_cash(shop.price_of(T.GROK, s.game)) if not intel.camo_covered(s.game) else None),
            start(5, "Start wave 5", "Camo Primitives and Static Arrays."),
            # ---- 6 TACTICAL PAUSE
            start(6, "Two traces", "Part of wave 6 takes the LOWER trace, where you have no towers. Start it; you will pause it next."),
            S("pause", 6, S.ACTION, "Pause the action",
              "Press P (or the pause button). Unlike the menu, this tactical pause keeps the map usable.",
              ("pause",), lambda s: s.tactically_paused(),
              fund=lambda s: s.ensure_cash(shop.price_of(T.GPT, s.game))),
            S("pause_build", 6, S.ACTION, "Build while paused", TutorialScript.pause_build_text,
              lambda s: s.build_target(T.GPT, B), lambda s: len(s.player_towers()) > s.snap["towers"],
              fund=lambda s: s.ensure_cash(shop.price_of(T.GPT, s.game))),
            S("resume", 6, S.ACTION, "Resume",
              "Press P again. Everything you did while paused is already in place.", ("pause",),
              lambda s: not s.game.is_paused()),
            # ---- 7 HEROES & BOSS
            S("heroes", 7, S.ACTION, "Meet the heroes",
              "Heroes are strong units from the Hero Store. Open it with HEROES (or K).", ("heroes",),
              lambda s: s.store_open() or s.any_hero_unlocked(),
              fund=lambda s: s.fund_selected_hero()),
            S("buy_hero", 7, S.ACTION, "Unlock a hero", TutorialScript.buy_text, TutorialScript.buy_target,
              lambda s: s.any_hero_unlocked(), fund=lambda s: s.fund_selected_hero(), store=True),
            S("deploy_hero", 7, S.ACTION, "Deploy it", TutorialScript.deploy_text, TutorialScript.deploy_target,
              lambda s: s.hero() is not None, fund=lambda s: s.fund_deploy(), store=True),
            S("spend", 7, S.ACTION, "Spend before the boss", TutorialScript.spend_text, TutorialScript.spend_target,
              lambda s: s.tier_sum() > s.snap["tiers"] or not any(t.can_upgrade() for t in s.player_towers()),
              fund=lambda s: s.fund_cheapest_upgrade()),
            S("boss_preview", 7, S.INFO, "A boss is coming",
              "The preview flags it. Hover it to read the boss's ability: at half health Bellarmine College Prep "
              "raises a CREST SHIELD that soaks damage before its hull.", ("preview",)),
            start(7, "Start the boss wave", "A few Primitives first, then the boss."),
            S("boss_wait", 7, S.WATCH, "Boss incoming",
              "Bellarmine College Prep rolls in a few seconds into the wave.", None,
              lambda s: bool(s.bosses()) or s.game.get_last_completed_wave() >= 7),
            S("dock", 7, S.INFO, "The boss dock",
              "Under the top bar the dock tracks every boss: its health and what its ability does next. The game is "
              "paused while you read; NEXT resumes.", ("dock",), lambda s: not s.bosses(), pause=True),
            S("boss_fight", 7, S.WATCH, "Bring it down",
              "Watch for the CREST SHIELD at half health and keep firing. Upgrades still work mid-fight, and P "
              "pauses if you need a moment.", None, wave_done(7)),
        ]
        return steps

    # ------------------------------------------------------------------ step texts and targets
    def any_hero_unlocked(self):
        return any(self.game.is_hero_unlocked(h) for h in TowerType.heroes())

    def fund_first_upgrade(self):
        t = self.selected() or self.first_tower()
        if t is not None and t.can_upgrade():
            self.ensure_cash(shop.upgrade_cost(t, self.game))

    def fund_cheapest_upgrade(self):
        costs = [shop.upgrade_cost(t, self.game) for t in self.player_towers() if t.can_upgrade()]
        if costs:
            self.ensure_cash(min(costs))

    def fund_deploy(self):
        h = next((x for x in TowerType.heroes() if self.game.is_hero_unlocked(x) and not self.game.is_hero_deployed(x)), None)
        if h is not None:
            self.ensure_cash(shop.price_of(h, self.game))

    def select_text(self):
        if not self.player_towers():
            return "You have no towers left. " + self.shop_hint(TowerType.CLAUDE) + " and place it by the track."
        return "Click your tower on the map (or press TAB). Its panel opens on the right."

    def select_target(self):
        t = self.first_tower()
        return ("tower", t) if t is not None else self.build_target(TowerType.CLAUDE, tutorial_waves.LANE_A)

    def upgrade_text(self):
        t = self.selected()
        if t is None:
            return self.select_text() if not self.player_towers() else "Select your tower again: click it on the map."
        if not t.can_upgrade():
            return "This one is maxed out. Select another tower."
        return "The lines under UPGRADE show exactly what changes (DMG, interval, range...). Press UPGRADE or U."

    def upgrade_target(self):
        t = self.selected()
        if t is not None and t.can_upgrade():
            return ("upgrade",)
        return self.select_target()

    def targeting_text(self):
        t = self.selected()
        if t is None or t.get_stats().is_support_only():
            return "Select an attacking tower to see its targeting. Or press NEXT."
        return "TARGET < > (or T) picks who it shoots: First, Last, Strongest, Weakest and more. Try it, or press NEXT."

    def targeting_target(self):
        t = self.selected()
        if t is not None and not t.get_stats().is_support_only():
            return ("targeting",)
        return self.select_target()

    def lead_text(self):
        if intel.lead_blocked(self.game):
            return ("Heap Sorts are Lead-type: Sharp damage can't hurt them, and all your towers deal Sharp damage. "
                    "The preview warns you: ! SHARP VS LEAD.")
        names = sorted({t.get_type().display_name for t in self.attack_towers() if intel.can_hurt_lead(t)})
        if names:
            return ("Heap Sorts are Lead-type: Sharp damage can't hurt them. " + ", ".join(names)
                    + (" deals" if len(names) == 1 else " deal") + " another damage type, so you are covered. When you "
                    "are not, the preview warns: ! SHARP VS LEAD.")
        return "Heap Sorts are Lead-type: Sharp damage can't hurt them. When that matters, the preview warns: ! SHARP VS LEAD."

    def camo_text(self):
        if not intel.camo_covered(self.game):
            return "Wave 5 is Camo: most towers can't see it. The preview warns you: ! NO CAMO DETECTION."
        return ("Wave 5 is Camo. One of your towers sees camo, so you are covered. When you are not, the preview warns: "
                "! NO CAMO DETECTION.")

    def pause_build_text(self):
        if self.placing_ok():
            return "Click a free spot beside the LOWER trace. Paused or not, placing works the same."
        lead = "While paused, build a tower beside the LOWER trace." if self.game.is_paused() else \
            "Build a tower beside the LOWER trace (P pauses again)."
        return lead + " " + self.shop_hint(TowerType.GPT) + "."

    def buy_text(self):
        if not self.store_open():
            return "Open the Hero Store again: HEROES (or K)."
        return ("Pick any hero, then press BUY. Here it is a practice unlock; in a real run an unlock is permanent. "
                "The tutorial covers the price.")

    def buy_target(self):
        return ("buy",) if self.store_open() else ("heroes",)

    def deploy_text(self):
        p = self.placing()
        if p is not None and p.is_hero():
            return "Click a free spot beside the track. Each hero deploys once per match."
        if not self.store_open():
            return "Open the Hero Store (HEROES or K) and press DEPLOY."
        return "Press DEPLOY, then click a spot on the map. Each hero deploys once per match."

    def deploy_target(self):
        p = self.placing()
        if p is not None and p.is_hero():
            return ("spot", self.suggest_spot(p, tutorial_waves.LANE_A))
        return ("deploy",) if self.store_open() else ("heroes",)

    def spend_text(self):
        t = self.selected()
        if t is not None and t.can_upgrade():
            return "Credits in the bank defend nothing. Press UPGRADE (or U); heroes upgrade the same way."
        return "Credits in the bank defend nothing. Select a tower or your hero and upgrade it before the boss."

    def spend_target(self):
        t = self.selected()
        if t is not None and t.can_upgrade():
            return ("upgrade",)
        cands = [x for x in self.player_towers() if x.can_upgrade()]
        if not cands:
            return None
        return ("tower", min(cands, key=lambda x: shop.upgrade_cost(x, self.game)))

    # ------------------------------------------------------------------ contextual tips
    TIPS = {
        "leak": ("An enemy got through", "Each escape costs integrity. Build where the track is busiest, upgrade, or "
                 "press P to pause and fix it.", "bad"),
        "camo": ("Camo slipped past", "A camo enemy walked right past a tower that cannot see it. Only detection hits "
                 "camo: Grok and Perplexity have it built in; Gemini and Llama gain it with upgrades.", "warn"),
        "cash": ("Credits are piling up", "{cash} in the bank defends nothing: build another tower or upgrade one.",
                 "warn"),
        "boss": ("Boss ability!", "{name}: the shield soaks damage before the hull. Keep firing and it breaks; the boss "
                 "dock shows what is left.", "bad"),
        "selected": ("Tower selected", "The panel on the right shows its stats, upgrade preview, targeting and SELL. "
                     "Esc or right-click deselects.", "info"),
    }
    SPENDING_STEPS = ("build", "select", "upgrade", "lead_fix", "camo_fix", "pause", "pause_build", "heroes",
                      "buy_hero", "deploy_hero", "spend")
    SELECTION_STEPS = ("select", "upgrade", "targeting", "spend")
    BUILD_STEPS = ("build", "lead_fix", "camo_fix", "pause_build", "deploy_hero")

    def fire_tip(self, key, **fmt):
        if key in self.tips_shown:
            return
        self.tips_shown.add(key)
        title, text, tone = TutorialScript.TIPS[key]
        tip = Tip(key, title, text.format(**fmt) if fmt else text, tone)
        self.tips_fired.append(tip)
        self.tip_queue.append(tip)

    def pop_tip(self):
        return self.tip_queue.pop(0) if self.tip_queue else None

    def watch_tips(self, dt):
        g = self.game
        key = self.current().key
        lives = g.get_lives()
        if lives < self.lives_seen:
            self.fire_tip("leak")
        self.lives_seen = lives
        if "camo" not in self.tips_shown and self.camo_slipping():
            self.fire_tip("camo")
        if self.wave_live() and g.get_cash() >= CASH_TIP_AMOUNT and key not in TutorialScript.SPENDING_STEPS:
            self.cash_time += dt
            if self.cash_time >= CASH_TIP_SECONDS:
                from lindefense.ui.cyber import Cyber
                self.fire_tip("cash", cash=Cyber.money(g.get_cash()))
        else:
            self.cash_time = 0.0
        if "boss" not in self.tips_shown:
            for b in self.bosses():
                ab = b.get_ability()
                if ab is not None and ab.get_fired() > 0:
                    self.fire_tip("boss", name=(ab.NAME or "Its ability").upper())
                    break
        if "selected" not in self.tips_shown and self.selected() is not None:
            if key in TutorialScript.SELECTION_STEPS:
                self.tips_shown.add("selected")   # the step itself explains the panel
            else:
                self.fire_tip("selected")

    def camo_slipping(self):
        """A camo enemy is walking past a tower that cannot see it with no detector in reach (or one just got out)."""
        blind, seeing = [], []
        for t in self.attack_towers():
            (seeing if t.can_see_camo() else blind).append(t)
        for e in self.game.get_enemy_manager().get_enemies():
            if not e.is_camo() or e.is_revealed():
                continue
            if e.has_leaked():
                return True
            if not e.is_alive():
                continue
            p = e.get_position()

            def reach(t):
                return t.get_position().dist(p) <= t.effective_range(self.game)
            if any(reach(t) for t in blind) and not any(reach(t) for t in seeing):
                return True
        return False
