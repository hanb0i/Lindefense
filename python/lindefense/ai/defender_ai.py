"""A scripted tower-defense player (the balance bot and reverse mode's defender). It plays only through the public
Game actions, so it is bound by exactly the rules a human player is."""
import sys

from lindefense.enemy.types import EnemyType, Modifier
from lindefense.jenum import JEnum
from lindefense.map.game_map import WIDTH, HEIGHT
from lindefense.sim.vec import Vec
from lindefense.tower import catalog, shop
from lindefense.tower.tower_type import Targeting, TowerType

_MAX = sys.float_info.max


class Step:
    def __init__(self, type_, copy, tier, min_wave):
        self.type, self.copy, self.tier, self.min_wave = type_, copy, tier, min_wave


class Plan(JEnum):
    EFFICIENT = ()
    MIXED = ()
    REVERSE = ()


class Action(JEnum):
    BUILD = ()
    UPGRADE = ()
    HERO_UNLOCK = ()
    HERO_DEPLOY = ()
    ABILITY_UNLOCK = ()
    ABILITY_CAST = ()


class Options:
    def __init__(self):
        self.plan = Plan.EFFICIENT
        self.opening = None
        self.max_towers = 999
        self.random_placement = False
        self.unlock_abilities = False
        self.unlock_min_towers = 8
        self.unlock_towers_per = 0
        self.wave_source = None   # callable -> int
        self.camo_alarm = None    # callable -> bool
        self.pressure_window = 0.0
        self.verbose = False


def _build_plans():
    T = TowerType
    GEM, CLA, GPT, DS, COP = T.GEMINI, T.CLAUDE, T.GPT, T.DEEPSEEK, T.COPILOT
    PER, COH, BRAD, ZET = T.PERPLEXITY, T.COHERE, T.LOBBER_LUIS, T.ZETHOS
    BRN, ROH, RON, SHA, OWN = T.BLITZ_ARNAV, T.CHILLSTIN, T.BOOM_SAM, T.SUNNY_JOE, T.NIK_SCOPE
    QWEN, KIMI, MM, SUNO, GLM = T.QWEN, T.KIMI, T.MINIMAX, T.SUNO, T.GLM
    GROK, SORA, MIS, LLA, DAL = T.GROK, T.SORA, T.MISTRAL, T.LLAMA, T.DALLE
    HANBO, LIND = T.SPEAR_HANBO, T.MR_LINDEMANN
    eff = [(GEM, 0, 0, 1), (CLA, 0, 0, 1), (GEM, 0, 1, 1), (CLA, 0, 1, 1), (PER, 0, 0, 1),
           (GPT, 0, 0, 1), (GPT, 0, 1, 1), (PER, 0, 1, 1), (DS, 0, 0, 1), (DS, 0, 1, 1),
           (COH, 0, 1, 1), (PER, 0, 2, 1), (PER, 0, 3, 1),
           (DS, 0, 2, 1), (DS, 0, 3, 1), (DS, 1, 0, 1), (DS, 1, 1, 1), (DS, 1, 2, 1), (DS, 1, 3, 1),
           (PER, 1, 3, 1), (DS, 2, 3, 1), (PER, 2, 3, 14), (QWEN, 0, 2, 1), (PER, 3, 3, 22),
           (BRAD, 0, 0, 28),
           (DS, 3, 3, 1), (QWEN, 0, 3, 1), (DS, 4, 3, 1), (COH, 0, 3, 1), (GEM, 0, 3, 1), (GPT, 0, 3, 1)]
    mixed = [(GEM, 0, 0, 1), (CLA, 0, 0, 1), (PER, 0, 0, 1),
             (GEM, 0, 1, 1), (CLA, 0, 1, 1), (GPT, 0, 0, 1), (PER, 0, 1, 1),
             (GPT, 0, 1, 1), (DS, 0, 0, 1), (DS, 0, 1, 1),
             (PER, 0, 2, 1), (PER, 0, 3, 1),
             (COH, 0, 1, 1), (GEM, 0, 2, 1), (CLA, 0, 2, 1),
             (COH, 0, 2, 1), (GPT, 0, 2, 1), (DS, 0, 2, 1),
             (COH, 0, 3, 1), (DS, 0, 3, 1), (GEM, 0, 3, 1),
             (ZET, 0, 2, 1), (CLA, 0, 3, 1), (GPT, 0, 3, 1), (ZET, 0, 4, 1),
             (BRAD, 0, 0, 1), (SHA, 0, 0, 1), (ROH, 0, 0, 1), (BRN, 0, 0, 1), (OWN, 0, 0, 1), (RON, 0, 0, 1),
             (QWEN, 0, 2, 1), (QWEN, 0, 3, 1),
             (KIMI, 0, 1, 1), (MM, 0, 1, 1), (SUNO, 0, 2, 1), (GLM, 0, 2, 1),
             (KIMI, 0, 3, 1), (MM, 0, 3, 1), (SUNO, 0, 3, 1), (GLM, 0, 3, 1),
             (GROK, 0, 3, 1), (SORA, 0, 3, 1), (MIS, 0, 3, 1), (LLA, 0, 3, 1), (DAL, 0, 3, 1), (COP, 0, 3, 1)]
    rev = [(GEM, 0, 0, 1), (CLA, 0, 0, 1), (GEM, 0, 1, 1), (CLA, 0, 1, 1), (GPT, 0, 0, 1), (GPT, 0, 1, 1),
           (DS, 0, 0, 1), (DS, 0, 1, 1), (HANBO, 0, 0, 1), (COH, 0, 1, 1), (DS, 0, 2, 1), (HANBO, 0, 1, 1), (DS, 0, 3, 1),
           (DS, 1, 0, 1), (DS, 1, 1, 1), (LIND, 0, 0, 1), (DS, 1, 2, 1), (DS, 1, 3, 1), (HANBO, 0, 2, 1), (LIND, 0, 1, 1),
           (QWEN, 0, 2, 1), (DS, 2, 3, 1), (LIND, 0, 2, 1), (BRAD, 0, 0, 1), (HANBO, 0, 3, 1),
           (DS, 3, 3, 1), (QWEN, 0, 3, 1), (BRAD, 0, 2, 1), (LIND, 0, 3, 1), (COH, 0, 3, 1), (DS, 4, 3, 1),
           (GEM, 0, 3, 1), (GPT, 0, 3, 1), (BRAD, 0, 3, 1)]
    mk = lambda lst: [Step(*x) for x in lst]
    return mk(eff), mk(mixed), mk(rev)


EFFICIENT_PLAN, MIXED_PLAN, REVERSE_PLAN = _build_plans()

_T = TowerType
OVERFLOW_EFFICIENT = (_T.DEEPSEEK, _T.QWEN, _T.COHERE, _T.GLM, _T.SORA, _T.GROK, _T.LLAMA)
OVERFLOW_MIXED = (_T.DEEPSEEK, _T.COHERE, _T.QWEN, _T.KIMI, _T.MINIMAX, _T.GEMINI, _T.GPT, _T.CLAUDE, _T.SUNO, _T.GLM,
                  _T.MISTRAL, _T.LLAMA, _T.GROK, _T.SORA)
UNLOCK_ORDER = (_T.DEEPSEEK, _T.QWEN, _T.COHERE, _T.GPT, _T.GEMINI, _T.CLAUDE, _T.SORA, _T.GLM, _T.GROK, _T.LLAMA, _T.KIMI,
                _T.MINIMAX, _T.SUNO, _T.MISTRAL, _T.DALLE, _T.COPILOT, _T.PERPLEXITY, _T.ZETHOS)


def _camo_wave(wave):
    from lindefense.wave import waves
    if wave < 1 or wave > waves.WAVE_COUNT:
        return False
    for gr in waves.get(wave).groups:
        if Modifier.CAMO in gr.modifiers or gr.type.has_innate_camo():
            return True
    return False


def _is_control_tool(t):
    return t in (TowerType.GLM, TowerType.SORA, TowerType.GROK, TowerType.LLAMA)


class DefenderAI:
    Step = Step
    Plan = Plan
    Action = Action
    Options = Options

    def __init__(self, game, options=None):
        self.g = game
        self.o = Options() if options is None else options
        o = self.o
        self._mixed = o.plan is Plan.MIXED
        if self._mixed:
            self._plan = MIXED_PLAN
        elif o.plan is Plan.REVERSE:
            self._plan = REVERSE_PLAN
        elif o.opening is not None:
            self._plan = list(o.opening) + list(EFFICIENT_PLAN)
        else:
            self._plan = EFFICIENT_PLAN
        self._lives_at_wave_start = self._lives_prev_wave = game.get_lives()
        self._tracked_wave = 0
        self._lives_history = []
        self._actions = 0
        self._listener = None
        gmap = game.get_map()
        self._samples = []
        for r in gmap.get_routes():
            d = 0.0
            while d < r.get_total_length():
                self._samples.append(r.position_at(d))
                d += 20
        self._spots = []
        for x in range(30, WIDTH, 15):
            for y in range(30, HEIGHT, 15):
                p = Vec(x, y)
                if gmap.is_buildable(p, 20):
                    self._spots.append(p)

    def set_listener(self, listener):
        self._listener = listener

    def get_options(self):
        return self.o

    def get_action_count(self):
        return self._actions

    def get_plan(self):
        return tuple(self._plan)

    # ------------------------------------------------------------------ decision pass
    def manage(self):
        from lindefense.sim.game import State
        g = self.g
        if g.get_state() is not State.PLAYING:
            return
        if g.get_wave() != self._tracked_wave:
            self._tracked_wave = g.get_wave()
            self._lives_prev_wave = self._lives_at_wave_start
            self._lives_at_wave_start = g.get_lives()
        if self.o.pressure_window > 0:
            self._lives_history.append((g.get_time(), g.get_lives()))
            while len(self._lives_history) > 1 and self._lives_history[1][0] <= g.get_time() - self.o.pressure_window:
                del self._lives_history[0]
        if not self.o.random_placement:
            self._use_abilities()
            self._set_targeting()
        self._purchase()

    def _wave(self):
        return self.o.wave_source() if self.o.wave_source is not None else self.g.get_wave()

    def _under_pressure(self):
        if self.o.pressure_window > 0:
            return bool(self._lives_history) and self._lives_history[0][1] - self.g.get_lives() >= 2
        return self._lives_prev_wave - self.g.get_lives() >= 2

    def _camo_expected(self, wave):
        if self.o.camo_alarm is not None:
            return self.o.camo_alarm()
        return any(_camo_wave(w) for w in range(wave, wave + 3))

    def _mine(self):
        return self.g.get_tower_manager().get_player_towers()

    def _nth(self, type_, copy):
        i = 0
        for t in self._mine():
            if t.get_type() is type_:
                if i == copy:
                    return t
                i += 1
        return None

    def _count(self, type_):
        return sum(1 for t in self._mine() if t.get_type() is type_)

    def has_detection(self):
        for t in self._mine():
            if t.get_type() is TowerType.PERPLEXITY and t.get_tier() >= 1:
                return True
            if t.get_type() is TowerType.GROK:
                return True
        return False

    def _purchase(self):
        g, o = self.g, self.o
        random = o.random_placement
        wave = max(1, self._wave())
        towers = len(self._mine())
        if (not random or o.camo_alarm is not None) and not self.has_detection() and self._camo_expected(wave):
            per = self._nth(TowerType.PERPLEXITY, 0)
            if per is None:
                if towers < o.max_towers and self._try_buy(TowerType.PERPLEXITY):
                    return
                if g.get_cash() < self._price(TowerType.PERPLEXITY):
                    return
            elif per.can_upgrade() and self._upgrade(per):
                return
            elif per.can_upgrade() and g.get_cash() < shop.upgrade_cost(per, g):
                return
        pressure = self._under_pressure()
        if pressure and self._attackers() < 5 + wave // 4 and towers < o.max_towers:
            pick = None
            best = 1 << 31
            for tt in (TowerType.GEMINI, TowerType.CLAUDE, TowerType.GPT, TowerType.COHERE):
                c = self._count(tt)
                if c < best:
                    best = c
                    pick = tt
            if g.get_cash() >= self._price(pick):
                if self._try_buy(pick):
                    return
        for st in self._plan:
            if st.min_wave > wave:
                continue
            if pressure and st.type is TowerType.PERPLEXITY and st.tier >= 2:
                continue
            if random and st.type is TowerType.PERPLEXITY:
                continue
            if o.max_towers < 40 and st.type is TowerType.PERPLEXITY and st.copy >= 1:
                continue
            t = self._nth(st.type, st.copy)
            if t is None:
                if st.type.is_hero() and (self._count(st.type) > 0 or g.is_hero_deployed(st.type)):
                    continue
                if st.type.is_hero() and g.get_tower_manager().hero_problem(st.type) is not None and g.is_hero_unlocked(st.type):
                    continue
                if st.copy > self._count(st.type):
                    continue
                if towers >= o.max_towers:
                    continue
                if not self._try_buy(st.type):
                    if g.get_cash() < self._price(st.type):
                        return
                    continue
                return
            if t.get_tier() >= st.tier:
                continue
            if self._upgrade(t):
                return
            return
        if o.unlock_abilities and not pressure and self._try_ability_unlock():
            return
        self._overflow()

    def _attackers(self):
        return sum(1 for t in self._mine() if t.get_type() is not TowerType.PERPLEXITY)

    def _price(self, t):
        g = self.g
        return catalog.get(t).unlock_cost if t.is_hero() and not g.is_hero_unlocked(t) else shop.price_of(t, g)

    def _upgrade(self, t):
        if not self.g.upgrade_tower(t):
            return False
        self._report(Action.UPGRADE, t, "upgraded " + t.get_type().display_name + " to " + t.get_tier_label())
        return True

    def _try_buy(self, type_):
        g = self.g
        if g.get_cash() < self._price(type_):
            return False
        if type_.is_hero() and g.is_hero_deployed(type_):
            return False
        if type_.is_hero() and not g.is_hero_unlocked(type_):
            if g.get_tower_manager().heroes_deployed_this_match() >= g.get_hero_limit():
                return False
            if not g.purchase_hero(type_):
                return False
            self._report(Action.HERO_UNLOCK, None, "unlocked hero " + type_.display_name + " in the Hero Store")
        p = self._best_spot(type_)
        if p is None:
            return False
        t = g.place_tower(type_, p)
        if t is not None:
            if type_.is_hero():
                self._report(Action.HERO_DEPLOY, t, "deployed hero " + type_.display_name)
            else:
                self._report(Action.BUILD, t, "built " + t.get_tier_label())
        return t is not None

    def _try_ability_unlock(self):
        g, o = self.g, self.o
        unlocked = sum(1 for t in self._mine() if catalog.ability_needs_unlock(t.get_type()) and not t.is_ability_locked())
        if len(self._mine()) < o.unlock_min_towers + o.unlock_towers_per * unlocked:
            return False
        pick = None
        for tt in UNLOCK_ORDER:
            for t in self._mine():
                if t.get_type() is tt and t.can_unlock_ability():
                    pick = t
                    break
            if pick is not None:
                break
        if pick is None:
            return False
        if g.get_cash() < catalog.ABILITY_UNLOCK_COST:
            return True
        if not g.unlock_ability(pick):
            return False
        self._report(Action.ABILITY_UNLOCK, pick, "unlocked " + pick.get_ability_def().name)
        return True

    def _overflow(self):
        g = self.g
        up = None
        for t in self._mine():
            if t.can_upgrade() and (up is None or shop.upgrade_cost(t, g) < shop.upgrade_cost(up, g)):
                up = t
        buy = None
        if len(self._mine()) < self.o.max_towers:
            best_ratio = _MAX
            for tt in (OVERFLOW_MIXED if self._mixed else OVERFLOW_EFFICIENT):
                if not self._mixed and _is_control_tool(tt) and len(self._mine()) < 30:
                    continue
                ratio = self._count(tt) / self._weight(tt)
                if ratio < best_ratio:
                    best_ratio = ratio
                    buy = tt
        if up is not None and (buy is None or shop.upgrade_cost(up, g) <= self._price(buy) * 2.2):
            self._upgrade(up)
            return
        if buy is not None:
            self._try_buy(buy)
        elif up is not None:
            self._upgrade(up)

    def _weight(self, t):
        if t is TowerType.DEEPSEEK:
            return 2.0 if self._mixed else 8.0
        if t is TowerType.QWEN:
            return 1.0 if self._mixed else 2.0
        return 1.0

    # ------------------------------------------------------------------ targeting & abilities
    def _set_targeting(self):
        boss = ddt = False
        for e in self.g.get_enemy_manager().get_enemies():
            if e.is_boss() and not e.is_stored():
                boss = True
            if e.get_type() is EnemyType.LOCKHEED_MARTIN:
                ddt = True
        for t in self._mine():
            want = Targeting.FIRST
            tt = t.get_type()
            if tt in (TowerType.DEEPSEEK, TowerType.COHERE, TowerType.NIK_SCOPE):
                want = Targeting.STRONGEST
            elif tt is TowerType.GROK:
                if t.can_use_densest_cluster():
                    want = Targeting.DENSEST_CLUSTER
            elif boss:
                want = Targeting.STRONGEST
            if ddt and want is not Targeting.DENSEST_CLUSTER:
                want = Targeting.FIRST
            if t.get_targeting() is not want:
                t.set_targeting(want)

    def _densest_spot(self, out_count):
        es = self.g.get_enemy_manager().get_enemies()
        best = None
        best_n = 0
        r2 = 110 * 110
        for a in es:
            if a.is_stored():
                continue
            n = 0
            ap = a.get_position()
            for b in es:
                if not b.is_stored() and ap.dist_sq(b.get_position()) <= r2:
                    n += 6 if b.is_boss() else 1
            if n > best_n:
                best_n = n
                best = ap
        if out_count is not None:
            out_count[0] = best_n
        return best

    def _use_abilities(self):
        g = self.g
        alive = 0
        boss = leak_risk = False
        lead_boss = None
        for e in g.get_enemy_manager().get_enemies():
            if e.is_stored():
                continue
            alive += 1
            if e.is_boss():
                boss = True
                lead_boss = e
            if e.get_remaining_distance() < 0.25 * e.get_route().get_total_length() and e.get_type().lives >= 2:
                leak_risk = True
        if alive == 0:
            return
        danger = boss or alive >= 18 or leak_risk
        for t in list(g.get_tower_manager().get_towers()):
            if t.is_temporary() or not t.is_ability_ready():
                continue
            tt = t.get_type()
            if tt is TowerType.PERPLEXITY:
                if g.get_round_pop_value() * t.get_ability().p("popValuePct") >= 800:
                    self._cast(t, None)
                continue
            if tt is TowerType.DEEPSEEK:
                if alive >= 6:
                    self._cast(t, None)
                continue
            if tt is TowerType.SORA:
                if leak_risk:
                    self._cast(t, None)
                continue
            if not danger:
                continue
            if t.get_ability().needs_target:
                n = [0]
                spot = lead_boss.get_position() if (lead_boss is not None and tt is TowerType.MISTRAL) else self._densest_spot(n)
                if spot is not None and (boss or n[0] >= 8):
                    self._cast(t, spot)
            elif self._in_reach(t):
                self._cast(t, None)

    def _in_reach(self, t):
        if t.get_type() is not TowerType.CLAUDE and t.get_type() is not TowerType.GEMINI:
            return True
        r = t.get_ability().p("radius")
        n = 0
        for e in self.g.get_enemy_manager().get_enemies():
            if e.is_stored() or e.get_position().dist(t.get_position()) > r:
                continue
            if e.is_boss():
                return True
            n += 1
            if n >= 5:
                return True
        return False

    def _cast(self, t, spot):
        name = t.get_ability().name
        ok = self.g.activate_ability(t) if spot is None else self.g.activate_ability(t, spot)
        if ok:
            self._report(Action.ABILITY_CAST, t, "cast " + name)

    def _report(self, a, t, text):
        self._actions += 1
        if self._listener is not None:
            self._listener(a, t, text)

    # ------------------------------------------------------------------ placement
    def _best_spot(self, type_):
        g = self.g
        tm = g.get_tower_manager()
        rng = catalog.get(type_).base_stats.range
        r2 = rng * rng
        if self.o.random_placement:
            for _ in range(200):
                p = self._spots[g.get_rng().next_int(len(self._spots))]
                if not tm.can_place(type_, p):
                    continue
                cover = 0
                for s in self._samples:
                    if s.dist_sq(p) <= r2:
                        cover += 1
                if cover >= 3:
                    return p
            return None
        map_wide = rng >= 1000
        aura = catalog.get(type_).base_stats.aura_range
        mine = self._mine()
        samples = self._samples
        weight = []
        for s in samples:
            cov = 0.0
            for t in mine:
                r = t.get_stats().range
                if r < 1000 and t.get_position().dist_sq(s) <= r * r:
                    cov += 1 + t.get_tier()
            weight.append(1.0 / (1.0 + 0.5 * cov))
        best = None
        best_score = float("-inf")
        spots = self._spots
        for i in range(0, len(spots), 2):
            p = spots[i]
            if not tm.can_place(type_, p):
                continue
            score = 0.0
            if map_wide:
                for s in samples:
                    if s.dist_sq(p) <= 170 * 170:
                        score -= 1
            else:
                px, py = p.x, p.y
                for k, s in enumerate(samples):
                    dx, dy = s.x - px, s.y - py
                    if dx * dx + dy * dy <= r2:
                        score += weight[k]
            if aura > 0 and not map_wide:
                for t in mine:
                    if t.get_position().dist(p) <= aura:
                        score += 15
            elif not map_wide:
                for t in mine:
                    if t.get_stats().aura_range > 0 and t.get_position().dist(p) <= t.get_stats().aura_range:
                        score += 10
            if score > best_score:
                best_score = score
                best = p
        return best
