"""The simulation root: map, economy, lives, managers and the fixed-step update loop. It knows nothing about
graphics; the UI calls advance() and reads state / get_events() to render."""
from lindefense.audio import hooks as audio
from lindefense.audio.sfx import Sfx
from lindefense.combat.combat import Combat
from lindefense.combat.visual_event import VisualEvent
from lindefense.effects.effects import Effects
from lindefense.enemy.boss import Boss
from lindefense.enemy.manager import EnemyManager
from lindefense.enemy.types import EnemyType, StatusKind
from lindefense.javacompat import fmt1, jint, jround
from lindefense.jenum import JEnum
from lindefense.sim.challenges import Challenge, FRUGAL_PRICE, GLASS_CANNON_DAMAGE, GLASS_CANNON_LIVES, ONE_LIFE_LIVES
from lindefense.sim.challenges import ordered as _ordered_challenges
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.misc import HeroCollection, WindowLink
from lindefense.sim.prompt_injection import PromptInjection
from lindefense.sim.rng import Rng
from lindefense.tower import catalog
from lindefense.tower.manager import AbilityManager, TowerManager, MAX_HEROES_PER_GAME
from lindefense.variance.variance import RunVariance, seed_next
from lindefense.wave import waves
from lindefense.wave.waves import WaveManager


class State(JEnum):
    PLAYING = ()
    VICTORY = ()
    DEFEAT = ()


class Game:
    State = State
    START_CASH = 650
    START_LIVES = 100
    DT = 1.0 / 60.0
    VICTORY_SEQUENCE_TIME = 5.0
    ADMIN_CASH = 999_999_999.0

    def __init__(self, gmap, seed, difficulty=None):
        if difficulty is None:
            difficulty = Difficulty.default_mode()
        self._difficulty = difficulty
        self._seed = seed
        self._cash = float(difficulty.start_cash(self.START_CASH))
        self._lives = difficulty.start_lives(self.START_LIVES)
        self._max_lives = self._lives
        self._map = gmap
        self._rng = Rng(seed)
        self._events = []
        self._log = []
        self._state = State.PLAYING
        self._time = 0.0
        self._tick = 0
        self._speed = 1
        self._paused = False
        self._accumulator = 0.0
        self._banner = None
        self._banner_rgb = 0
        self._banner_time = 0.0
        self._palantir = None
        self._ability_banners = set()
        self._victory_timer = -1.0
        self._defeat_timer = -1.0
        self._last_completed_wave = 0
        self._total_cash_earned = 0.0
        self._round_pop_value = 0.0
        self._global_enemy_speed_multiplier = 1.0
        self._invincible = False
        self._heroes = HeroCollection.in_memory()
        self._deployed_heroes = set()
        self._boss_kills = []        # records: boss types killed this run (pure counters, read at run end)
        self._heroes_bought = []
        self._tags = []
        self._admin_heroes = self._admin_money = self._admin_health = False
        self._hero_limit = MAX_HEROES_PER_GAME
        self._challenges = ()            # challenge rules (set_challenges); all off by default
        self._selling_locked = False
        self._price_multiplier = 1.0
        self._challenge_damage = 1.0
        self._run_tags = []              # "daily:YYYY-MM-DD", "custom-seed" (see run_tags)
        self._seed_fixed = False         # True when the seed was chosen (typed, daily, replayed): RESTART keeps it
        self._reverse = None
        self._freeplay = False
        self._window_link = WindowLink()
        self._enemy_manager = EnemyManager(self)
        self._tower_manager = TowerManager(self)
        self._wave_manager = WaveManager(self)
        self._ability_manager = AbilityManager(self)
        self._combat = Combat(self)
        self._effects = Effects(self)
        self._injection = PromptInjection(self)
        self._variance = RunVariance(self)
        gmap.reset()

    @staticmethod
    def fresh_copy(old, seed=None, today=None):
        """A new match like `old` (RESTART / RETRY; with a seed: REPLAY SEED). A daily run stays the daily run only when
        it is restarted on its own date: replayed (or restarted another day) it becomes a chosen-seed run with the same
        rule, so it never updates that date's daily best. today: a date or "YYYY-MM-DD" (default: the local date)."""
        from lindefense.map import maps
        replay = seed is not None
        if seed is None:
            seed = old._seed if old._seed_fixed else seed_next()
        idx = maps.index_of(old.get_map())
        if idx < 0:
            raise ValueError("map is not in the catalog: " + old.get_map().get_name())
        g = Game(maps.create(idx), seed, old.get_difficulty())
        g.set_hero_collection(old.get_hero_collection())
        g.copy_admin_from(old)
        g.set_challenges(old._challenges)
        if not isinstance(today, str):
            import datetime
            from lindefense.sim.run_setup import date_key
            today = date_key(datetime.date.today() if today is None else today)
        for t in old._run_tags:
            g.add_run_tag("custom-seed" if t.startswith("daily:") and (replay or t[6:] != today) else t)
        g._seed_fixed = old._seed_fixed or replay
        if replay and not old._seed_fixed:
            g.add_run_tag("custom-seed")
        if old._variance.is_enabled():
            g._variance.enable(old._variance.get_picker())
        return g

    # ---------------- Hero Store
    def get_hero_collection(self):
        return self._heroes

    def set_hero_collection(self, c):
        self._heroes = HeroCollection.in_memory() if c is None else c

    def is_hero_unlocked(self, type_):
        return (self._admin_heroes and type_ is not None and type_.is_hero()) or self._heroes.is_unlocked(type_)

    # ---------------- admin mode
    def set_admin(self, heroes, money, health):
        self._admin_heroes = heroes
        self._admin_money = money
        self._admin_health = health
        if money:
            self._cash = max(self._cash, self.ADMIN_CASH)
        if health:
            self._invincible = True

    def copy_admin_from(self, other):
        self.set_admin(other._admin_heroes, other._admin_money, other._admin_health)

    def is_admin(self):
        return self._admin_heroes or self._admin_money or self._admin_health

    def has_admin_heroes(self):
        return self._admin_heroes

    def has_admin_money(self):
        return self._admin_money

    def has_admin_health(self):
        return self._admin_health

    def get_hero_limit(self):
        return self._hero_limit

    def set_hero_limit(self, limit):
        self._hero_limit = max(0, limit)

    # ---------------- challenge rules and run tags
    def set_challenges(self, challenges):
        """Switches on challenge rules (sim.challenges.Challenge) for a fresh match, before the first wave. With none (the
        default) nothing changes. Reverse matches never take challenges, so the defender AI is unaffected."""
        cs = _ordered_challenges(challenges)
        if self._reverse is not None or not cs:
            return
        self._challenges = cs
        if Challenge.NO_HEROES in cs:
            self.set_hero_limit(0)
        if Challenge.ONE_LIFE in cs:
            self.set_starting_lives(ONE_LIFE_LIVES)
        elif Challenge.GLASS_CANNON in cs:
            self.set_starting_lives(GLASS_CANNON_LIVES)
        self._selling_locked = Challenge.NO_SELLING in cs
        self._price_multiplier = FRUGAL_PRICE if Challenge.FRUGAL in cs else 1.0
        self._challenge_damage = GLASS_CANNON_DAMAGE if Challenge.GLASS_CANNON in cs else 1.0

    def get_challenges(self):
        return self._challenges

    def has_challenge(self, c):
        return c in self._challenges

    def is_selling_locked(self):
        """No Selling challenge: towers cannot be sold nor heroes dismissed."""
        return self._selling_locked

    def get_price_multiplier(self):
        """Frugal challenge: tower, hero and upgrade prices x1.5 (applied by tower.shop after Patch Notes)."""
        return self._price_multiplier

    def set_seed_fixed(self, fixed):
        self._seed_fixed = fixed

    def is_seed_fixed(self):
        """True when the player chose this run's seed (typed it, daily run, REPLAY SEED): RESTART keeps the seed."""
        return self._seed_fixed

    def add_run_tag(self, tag):
        if tag and tag not in self._run_tags:
            self._run_tags.append(tag)

    @property
    def run_tags(self):
        """Labels for career records / run history: "daily:2026-11-09" for a daily run, "custom-seed" for a chosen
        seed, one tag per challenge rule ("no-heroes", "one-life", "no-selling", "frugal", "glass-cannon") and
        "no-patch-notes" when Patch Notes are off. Empty for a standard run with Patch Notes on."""
        tags = list(self._run_tags)
        tags.extend(c.tag for c in self._challenges)
        if self._reverse is None and not self._variance.is_enabled():
            tags.append("no-patch-notes")
        return tuple(tags)

    def get_run_tags(self):
        return self.run_tags

    def get_daily_date(self):
        """The date ("YYYY-MM-DD") of a daily run, else None."""
        for t in self._run_tags:
            if t.startswith("daily:"):
                return t[6:]
        return None

    def is_hero_deployed(self, type_):
        return type_ in self._deployed_heroes

    def mark_hero_deployed(self, type_):
        self._deployed_heroes.add(type_)

    def hero_purchase_problem(self, type_):
        if type_ is None or not type_.is_hero():
            return "Not a hero"
        if self._state is not State.PLAYING:
            return "Game over"
        if self.is_hero_unlocked(type_):
            return "Already unlocked"
        if self._cash < catalog.get(type_).unlock_cost:
            return "Not enough cash"
        return None

    def purchase_hero(self, type_):
        if self.hero_purchase_problem(type_) is not None:
            audio.sfx(Sfx.INVALID)
            return False
        price = catalog.get(type_).unlock_cost
        if not self.spend_cash(price):
            return False
        self._heroes.unlock(type_)
        self._heroes_bought.append(type_)
        self.set_banner(type_.display_name.upper() + " UNLOCKED", type_.primary_rgb, 2.5)
        self._log_line("Hero unlocked: " + type_.display_name + " for $" + str(price))
        audio.sfx(Sfx.CASH)
        return True

    # ---------------- reverse mode
    def get_reverse(self):
        return self._reverse

    def is_reverse(self):
        return self._reverse is not None

    def set_reverse(self, r):
        self._reverse = r

    def declare_defender_victory(self, banner_text):
        if self._state is not State.PLAYING or self._defeat_timer >= 0 or self._victory_timer >= 0:
            return
        self._state = State.VICTORY
        self.set_banner(banner_text, 0x7fd8a8, 4)
        self._log_line(banner_text)

    # ---------------- freeplay (endless waves after Palantir)
    def is_freeplay(self):
        """True once the player chose CONTINUE - FREEPLAY on the victory screen (stays true after freeplay ends)."""
        return self._freeplay

    def can_continue_freeplay(self):
        return (self._state is State.VICTORY and not self._freeplay and self._reverse is None
                and self.get_wave() >= waves.WAVE_COUNT)

    def continue_freeplay(self):
        """Resumes a won campaign as Freeplay: the board, cash, lives and towers carry over, whatever was left on the
        track after Palantir fell is cleared, and wave 101 onwards are generated (wave/freeplay.py). Freeplay ends
        when lives reach zero; the run still ends in VICTORY."""
        if not self.can_continue_freeplay():
            return False
        self._freeplay = True
        self.add_tag("freeplay")
        self._state = State.PLAYING
        self._victory_timer = -1.0
        self._defeat_timer = -1.0
        self._paused = False
        self._accumulator = 0.0
        self._last_completed_wave = max(self._last_completed_wave, waves.WAVE_COUNT)
        for e in self._enemy_manager.get_enemies():
            e.mark_dead()
        for e in self._enemy_manager.get_pending():
            e.mark_dead()
        self._enemy_manager.clear()
        self._combat.clear()
        self._palantir = None
        self._wave_manager.end_wave()
        self.set_banner("FREEPLAY: ENDLESS WAVES", 0xffd166, 3)
        self._log_line("Freeplay started after wave " + str(self.get_wave()))
        return True

    # ---------------- accessors
    def get_map(self):
        return self._map

    def get_difficulty(self):
        return self._difficulty

    def get_seed(self):
        return self._seed

    def get_rng(self):
        return self._rng

    def get_enemy_manager(self):
        return self._enemy_manager

    def get_tower_manager(self):
        return self._tower_manager

    def get_wave_manager(self):
        return self._wave_manager

    def get_ability_manager(self):
        return self._ability_manager

    def get_combat(self):
        return self._combat

    def get_variance(self):
        return self._variance

    def get_effects(self):
        return self._effects

    def get_events(self):
        return self._events

    def get_injection(self):
        return self._injection

    def get_window_link(self):
        return self._window_link

    def set_window_fraction(self, f):
        self._window_link.set_fraction(f)

    def get_window_fraction(self):
        return self._window_link.get_fraction()

    def get_log(self):
        return self._log

    def get_state(self):
        return self._state

    def get_cash(self):
        return self._cash

    def get_lives(self):
        return self._lives

    def get_time(self):
        return self._time

    def get_tick(self):
        return self._tick

    def get_speed(self):
        return self._speed

    def is_paused(self):
        return self._paused

    def get_wave(self):
        return self._wave_manager.get_current_wave()

    def get_last_completed_wave(self):
        return self._last_completed_wave

    # ---------------- run records (read by sim/records.py at run end; never feed back into the simulation)
    def get_boss_kills(self):
        return self._boss_kills

    def get_heroes_bought(self):
        return self._heroes_bought

    def get_tags(self):
        """Run tags for the run history: free tags (add_tag, e.g. "freeplay") plus the run-setup tags (run_tags: daily
        run, chosen seed, challenge rules, Patch Notes off)."""
        return self._tags + [t for t in self.run_tags if t not in self._tags]

    def add_tag(self, tag):
        if tag and tag not in self._tags:
            self._tags.append(tag)

    def get_total_cash_earned(self):
        return self._total_cash_earned

    def get_round_pop_value(self):
        return self._round_pop_value

    def add_pop_value(self, v):
        self._round_pop_value += v

    def get_palantir(self):
        return self._palantir

    def is_victory_sequence_active(self):
        return self._victory_timer > 0

    def is_campaign_won(self):
        """True from the moment the campaign is won (Palantir destroyed or wave 100 cleared), through the victory
        sequence and screen, until Freeplay resumes play. (_victory_timer is exactly -1.0 until then; the sequence
        counts down from 0.5 / 5 s and stops at or just below 0.)"""
        return self._victory_timer != -1.0

    def get_victory_timer(self):
        return self._victory_timer

    def get_banner(self):
        return self._banner if self._banner_time > 0 else None

    def get_banner_rgb(self):
        return self._banner_rgb

    def get_global_rate_multiplier(self):
        return self._variance.fire_rate()

    def get_global_range_multiplier(self):
        return self._variance.range()

    def get_global_damage_multiplier(self):
        r = self._reverse
        m = self._difficulty.tower_damage * (r.get_profile().tower_damage if r is not None else 1)
        return m if self._challenge_damage == 1.0 else m * self._challenge_damage

    def get_global_enemy_speed_multiplier(self):
        return self._global_enemy_speed_multiplier

    def set_global_enemy_speed_multiplier(self, m):
        self._global_enemy_speed_multiplier = m

    def set_invincible(self, v):
        self._invincible = v

    def is_invincible(self):
        return self._invincible

    def get_wave_hp_scale(self, type_=None):
        w = max(1, self.get_wave())
        return waves.hp_scale(w) * self._difficulty.hp_multiplier(w, type_) * self._variance.enemy_hp()

    def get_wave_speed_scale(self):
        return waves.speed_scale(max(1, self.get_wave())) * self._variance.enemy_speed()

    def get_reward_scale(self):
        if self._reverse is not None:
            return self._reverse.kill_reward_scale()
        return waves.reward_scale(max(1, self.get_wave())) * self._difficulty.income * self._variance.kill_income()

    def set_speed(self, s):
        self._speed = max(1, min(3, s))

    def set_paused(self, p):
        self._paused = p

    def toggle_pause(self):
        self._paused = not self._paused

    def get_active_bosses(self):
        return [e for e in self._enemy_manager.get_enemies() if isinstance(e, Boss)]

    # ---------------- economy & lives
    def add_cash(self, amount, where=None):
        if amount <= 0:
            return
        self._cash += amount
        self._total_cash_earned += amount

    def spend_cash(self, amount):
        if self._admin_money:
            return True
        if self._cash < amount:
            return False
        self._cash -= amount
        return True

    def restore_lives(self, n):
        if self._state is not State.PLAYING or n <= 0:
            return 0
        before = self._lives
        self._lives = max(self._lives, min(self._max_lives, self._lives + n))
        return self._lives - before

    def add_lives(self, n):
        if self._state is State.PLAYING and n > 0 and not self.has_challenge(Challenge.ONE_LIFE):
            self._lives += n

    def get_max_lives(self):
        return self._max_lives

    def set_starting_lives(self, n):
        self._max_lives = max(1, n)
        self._lives = self._max_lives

    def lose_lives(self, n, leaker):
        if self._state is not State.PLAYING or n <= 0:
            return
        self._lives = max(0, self._lives - n)
        if self._reverse is not None:
            self._reverse.on_leak(n, leaker)
        audio.sfx(Sfx.LIFE_LOST)
        self._events.append(VisualEvent.text(leaker.get_position(), "-" + str(n) + " lives", 0xff5a5a))
        if self._invincible:
            self._lives = max(self._lives, 1)
            return
        if self._lives <= 0 and self._defeat_timer < 0 and self._victory_timer < 0:
            self._defeat_timer = 2.0
            self.set_banner("DEFENSES BREACHED", 0xff5a5a, 3)
            self._log_line("Lives reached zero on wave " + str(self.get_wave()))
            if self._freeplay:
                self.set_banner("FREEPLAY OVER  -  REACHED WAVE " + str(self.get_wave()), 0xffd166, 3)

    # ---------------- player actions
    def start_next_wave(self):
        if self._state is not State.PLAYING:
            return False
        return self._wave_manager.start_next_wave()

    def place_tower(self, type_, p):
        if self._state is not State.PLAYING:
            return None
        placed = self._tower_manager.place(type_, p)
        audio.sfx(Sfx.TOWER_PLACE if placed is not None else Sfx.INVALID)
        return placed

    def placement_problem(self, type_, p):
        return self._tower_manager.placement_problem(type_, p)

    def upgrade_tower(self, t):
        ok = self._state is State.PLAYING and self._tower_manager.upgrade(t)
        audio.sfx(Sfx.TOWER_UPGRADE if ok else Sfx.INVALID)
        return ok

    def sell_tower(self, t):
        refund = self._tower_manager.sell(t) if self._state is State.PLAYING else 0
        if refund > 0:
            audio.sfx(Sfx.TOWER_SELL)
        return refund

    def unlock_ability(self, t):
        ok = self._state is State.PLAYING and self._tower_manager.unlock_ability(t)
        audio.sfx(Sfx.TOWER_UPGRADE if ok else Sfx.INVALID)
        return ok

    def activate_ability(self, t, target_point=None):
        if target_point is None:
            ok = self._state is State.PLAYING and self._ability_manager.activate(t)
        else:
            ok = self._state is State.PLAYING and self._ability_manager.activate(t, target_point, True)
        audio.sfx(Sfx.ABILITY if ok else Sfx.INVALID)
        return ok

    # ---------------- simulation
    def advance(self, real_seconds):
        if self._paused or (self._state is not State.PLAYING and self._victory_timer <= 0 and self._defeat_timer <= 0):
            return
        self._accumulator += real_seconds * self._speed
        steps = 0
        while self._accumulator >= self.DT and steps < 30:
            self.step(self.DT)
            self._accumulator -= self.DT
            steps += 1
        if steps == 30:
            self._accumulator = 0.0

    def step(self, dt):
        self._time += dt
        self._tick += 1
        if self._banner_time > 0:
            self._banner_time -= dt
        if self._victory_timer > 0:
            self._victory_timer -= dt
            self._map.update(self, dt)
            self._enemy_manager.update(dt)
            self._combat.update_projectiles(dt)
            if self._victory_timer <= 0:
                self._state = State.VICTORY
            return
        if self._defeat_timer > 0:
            self._defeat_timer -= dt
            self._enemy_manager.update(dt)
            self._combat.update_projectiles(dt)
            if self._defeat_timer <= 0:
                self._state = State.VICTORY if self._freeplay else State.DEFEAT
            return
        if self._state is not State.PLAYING:
            return
        if self._reverse is not None:
            self._reverse.update(dt)
            if self._state is not State.PLAYING:
                return
        self._wave_manager.update(dt)
        self._map.update(self, dt)
        self._injection.update(dt)
        self._tower_manager.update(dt)
        self._effects.update(dt)
        self._combat.update_projectiles(dt)
        self._enemy_manager.update(dt)

    def run(self, n):
        i = 0
        while i < n and self._state is not State.DEFEAT:
            self.step(self.DT)
            i += 1

    def drain_events(self):
        copy = list(self._events)
        self._events.clear()
        return copy

    # ---------------- hooks from subsystems
    def on_wave_started(self, wave, d):
        self._round_pop_value = 0.0
        self._variance.on_wave_started(wave)
        self._map.on_wave_start(self, wave)
        audio.sfx(Sfx.BOSS_ALARM if d.contains_boss() else Sfx.WAVE_START)
        msg = "Wave " + str(wave)
        if d.contains_boss():
            msg += "  -  BOSS INCOMING"
        self.set_banner(msg, 0xff8080 if d.contains_boss() else 0xffffff, 2.5)
        self._log_line("Wave " + str(wave) + " started" + (": " + d.note if d.note is not None else ""))

    def on_wave_completed(self, wave, d):
        self._last_completed_wave = wave
        audio.sfx(Sfx.WAVE_COMPLETE)
        audio.sfx(Sfx.CASH)
        bonus = jround(waves.wave_bonus(wave) * self._difficulty.income * self._variance.wave_bonus())
        income = 0.0
        for t in list(self._tower_manager.get_towers()):
            income += t.get_behavior().on_round_end(self, t)
        self.add_cash(bonus + income, None)
        self.set_banner("Wave " + str(wave) + " complete  +$" + str(jint(bonus + income)), 0x7fd8a8, 2.5)
        self._log_line("Wave " + str(wave) + " complete: +$" + str(bonus)
                       + (" (+$" + str(jint(income)) + " research income)" if income > 0 else ""))
        self._variance.on_wave_completed(wave)
        if wave >= waves.WAVE_COUNT and self._victory_timer < 0 and self._state is State.PLAYING and not self._freeplay:
            self._victory_timer = 0.5

    def on_enemy_killed(self, e):
        if e.get_type().is_boss():
            audio.sfx(Sfx.BOSS_DEATH)
            self._boss_kills.append(e.get_type())
        if e.get_type() is EnemyType.PALANTIR and self._freeplay:
            self.set_banner("PALANTIR DESTROYED AGAIN", 0xffd166, 3)
            self._events.append(VisualEvent.phase(e.get_position(), "PALANTIR DESTROYED", 0xffd166))
            self._log_line("Freeplay Palantir destroyed on wave " + str(self.get_wave()))
        elif e.get_type() is EnemyType.PALANTIR and self._victory_timer < 0 and self._reverse is None:
            self._victory_timer = self.VICTORY_SEQUENCE_TIME
            # the final wave ends here (end_wave below, no completion): count it as cleared for the records, the
            # end screen and the daily best
            self._last_completed_wave = max(self._last_completed_wave, self.get_wave())
            self.set_banner("PALANTIR DESTROYED", 0xffd166, self.VICTORY_SEQUENCE_TIME)
            self._events.append(VisualEvent.phase(e.get_position(), "PALANTIR DESTROYED", 0xffd166))
            for o in self._enemy_manager.get_enemies():
                if o is not e:
                    o.apply_status(StatusKind.STUN, 1, 99, True)   # bosses too: Palantir's escorts freeze with the rest
            self._wave_manager.end_wave()
            self._log_line("Palantir destroyed. Campaign complete.")

    def announce_boss(self, b):
        audio.sfx(Sfx.BOSS_ALARM)
        if b.is_palantir():
            self._palantir = b
            self.set_banner("PALANTIR HAS ARRIVED  -  " + b.get_phase_name(), 0xff4d4d, 4)
            self._events.append(VisualEvent.phase(b.get_position(), "PALANTIR", 0xff4d4d))
        else:
            self.set_banner(b.get_type().display_name + " (" + b.get_type().get_boss_class().label + ") has entered the track", 0xff9a5a, 3)
        self._log_line("Boss entered: " + b.get_type().display_name)

    def on_palantir_phase(self, b, phase):
        self.set_banner("PALANTIR PHASE " + str(phase + 1) + ": " + b.get_phase_name(), 0xff4d4d, 3)
        self._events.append(VisualEvent.phase(b.get_position(), b.get_phase_name(), 0xff4d4d))
        self._log_line("Palantir entered phase " + str(phase + 1) + " (" + b.get_phase_name() + ")")

    def announce_boss_ability(self, b, text, rgb):
        """A corporate boss used its signature ability: banner the first use of each boss type per wave (never over
        Palantir's own banners: its escorts are announced by the phase change)."""
        key = (self.get_wave(), b.get_type())
        if key in self._ability_banners:
            return
        self._ability_banners.add(key)
        self._log_line(text)
        if self._palantir is None or not self._palantir.is_alive():
            self.set_banner(text, rgb, 3)

    def on_surveillance_telegraph(self, b, marked):
        audio.sfx(Sfx.PALANTIR_WARNING)
        self.set_banner("PREDICTIVE SURVEILLANCE: analysing " + str(len(marked)) + " towers...", 0xff4d4d, Boss.TELEGRAPH_TIME)
        for t in marked:
            self._events.append(VisualEvent.text(t.get_position(), "TARGETED", 0xff4d4d))

    def on_surveillance_applied(self, b, applied, attempted):
        if applied == 0 and attempted > 0:
            self.set_banner("Surveillance blocked!", 0x7fd8a8, 2)
        else:
            self.set_banner("Surveillance disrupts " + str(applied) + " tower(s) for " + str(jint(Boss.SURVEIL_DURATION)) + "s", 0xff4d4d, 2.5)

    def emit_text(self, where, text, rgb):
        self._events.append(VisualEvent.text(where, text, rgb))

    def emit_teleport(self, where):
        self._events.append(VisualEvent.teleport(where))

    def set_banner(self, text, rgb, seconds):
        self._banner = text
        self._banner_rgb = rgb
        self._banner_time = seconds

    def _log_line(self, s):
        self._log.append("[" + fmt1(self._time).rjust(6) + "s] " + s)   # String.format("%6.1f") rounds half up
        if len(self._log) > 200:
            del self._log[0]
