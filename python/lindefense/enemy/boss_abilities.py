"""Signature abilities of the four corporate bosses (Palantir's own live in boss.py's PalantirProtocols).

Every ability is deterministic (timers and HP thresholds only, no randomness) and announces itself: a floating text at
the boss each time it fires, a banner the first time per wave, a status line in the boss dock (status_text) and an
in-world overlay drawn by ui/boss_fx.py from the state exposed here.

  Bellarmine College Prep (MOAB)  CREST SHIELD   at 50% HP raises a shield worth 35% of its max HP, once.
  SW Resource Consultant (BFB)    OUTSOURCING    every 9 s hands the job to 3 Quick Sort contractors.
  3Com (ZOMG)                     NETWORK HUB    enemies within 200 px take half damage; 3Com self-repairs 0.6%/s.
  Lockheed Martin (DDT)           AFTERBURNER    every 7 s, 1.5x speed for 1 s.
"""
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.jenum import EnumSet

_take_damage = Enemy.take_damage


def _n(x):
    """3, 1.5, 0.6: a number as players read it."""
    return ("%.2f" % x).rstrip("0").rstrip(".")


def _pct(f):
    return _n(100 * f) + "%"


class BossAbility:
    NAME = ""
    RGB = 0xffffff

    def __init__(self):
        self._fired = 0

    def update(self, game, b, dt):
        pass

    def take_damage(self, b, amount, now):
        """Boss.take_damage routes here (amount > 0 and the boss alive); returns the damage dealt."""
        return _take_damage(b, amount, now)

    def speed_multiplier(self):
        return 1.0

    def status_text(self, b):
        """Short dock line ('' when there is nothing to say)."""
        return ""

    def get_fired(self):
        """How many times the ability has gone off."""
        return self._fired

    @classmethod
    def describe(cls):
        """One sentence for the catalog, the boss dock help and the design doc, built from the live numbers."""
        return ""

    def _announce(self, game, b, text, banner):
        self._fired += 1
        game.emit_text(b.get_position(), text, self.RGB)
        game.announce_boss_ability(b, banner, self.RGB)


class CrestShield(BossAbility):
    """MOAB: the school crest becomes a shield the first time the hull drops to TRIGGER of its max HP. The shield soaks
    every kind of damage (true and %-max-HP included) before the hull takes any; whatever is left of a hit that breaks
    it carries over."""
    NAME = "Crest Shield"
    RGB = 0x7fc8ff
    TRIGGER = 0.50
    SHIELD = 0.35

    def __init__(self):
        BossAbility.__init__(self)
        self._shield = 0.0
        self._shield_max = 0.0
        self._used = False
        self._announced = False   # take_damage has no game: the shield is announced on the next update
        self._break_pending = False
        self._broken_age = 99.0

    def take_damage(self, b, amount, now):
        dealt = 0.0
        if not self._used:
            floor = b.get_max_hp() * self.TRIGGER
            if b.get_hp() - amount > floor:
                return _take_damage(b, amount, now)
            pre = b.get_hp() - floor
            if pre > 0:
                dealt = _take_damage(b, pre, now)
                amount -= pre
            self._used = True
            self._shield = self._shield_max = b.get_max_hp() * self.SHIELD
        if self._shield > 0 and amount > 0:
            soak = min(self._shield, amount)
            self._shield -= soak
            amount -= soak
            dealt += soak
            if self._shield <= 1e-9:
                self._shield = 0.0
                self._break_pending = True
            b._times_hit += 1
            b._last_hit_time = now
        if amount > 0:
            dealt += _take_damage(b, amount, now)
        return dealt

    def update(self, game, b, dt):
        self._broken_age += dt
        if self._used and not self._announced:
            self._announced = True
            self._announce(game, b, "CREST SHIELD", b.get_type().display_name + " raises its CREST SHIELD (+"
                           + str(int(round(self._shield_max))) + " shield)")
        if self._break_pending:
            self._break_pending = False
            self._broken_age = 0.0
            game.emit_text(b.get_position(), "SHIELD BROKEN", 0xffffff)

    @classmethod
    def describe(cls):
        return ("CREST SHIELD: the first time it drops to " + _pct(cls.TRIGGER) + " health it raises a shield worth "
                + _pct(cls.SHIELD) + " of its max HP that soaks every kind of damage (%-max-HP strikes included); "
                "the hit that breaks it carries over.")

    def is_up(self):
        return self._shield > 0

    def is_used(self):
        return self._used

    def get_shield(self):
        return self._shield

    def get_shield_max(self):
        return self._shield_max

    def get_shield_fraction(self):
        return 0.0 if self._shield_max <= 0 else self._shield / self._shield_max

    def get_broken_age(self):
        return self._broken_age

    def status_text(self, b):
        if self._shield > 0:
            return "CREST SHIELD " + str(int(round(100 * self.get_shield_fraction()))) + "%"
        return "SHIELD BROKEN" if self._used else "CREST SHIELD AT 50%"


class Outsourcing(BossAbility):
    """BFB: every INTERVAL s (the first after FIRST s) it hands the job to COUNT contractors, Quick Sorts spawned on
    its own spot with its HP scale (and its Camo / Regrow). They pay their normal bounty."""
    NAME = "Outsourcing"
    RGB = 0xffb347
    FIRST = 4.0
    INTERVAL = 9.0
    COUNT = 3
    CONTRACTOR = EnemyType.QUICK_SORT
    SPACING = 9.0

    def __init__(self):
        BossAbility.__init__(self)
        self._timer = self.FIRST
        self._since = 99.0
        self._spawned = 0

    def update(self, game, b, dt):
        self._since += dt
        self._timer -= dt
        if self._timer > 0:
            return
        self._timer = self.INTERVAL
        self.outsource(game, b)

    def outsource(self, game, b):
        em = game.get_enemy_manager()
        for i in range(self.COUNT):
            mods = EnumSet()
            if b.has(Modifier.CAMO):
                mods.add(Modifier.CAMO)
            if b.has(Modifier.REGROW):
                mods.add(Modifier.REGROW)
            d = max(0.0, b.get_distance() - self.SPACING * i)
            c = em.spawn_scaled(self.CONTRACTOR, mods, b.get_route_index(), d, b.get_hp_scale(), b.get_speed_scale())
            c.set_drifted(b.has_drifted())
            self._spawned += 1
        self._since = 0.0
        game.get_events().append(VisualEvent.split(b.get_position(), b.get_radius() * 2.2, self.RGB))
        self._announce(game, b, "OUTSOURCED x" + str(self.COUNT), b.get_type().display_name + " is OUTSOURCING: "
                       + str(self.COUNT) + " " + self.CONTRACTOR.display_name + " contractors every " + str(int(self.INTERVAL)) + " s")

    @classmethod
    def describe(cls):
        return ("OUTSOURCING: " + _n(cls.FIRST) + " s after it appears and every " + _n(cls.INTERVAL) + " s after that it drops "
                + str(cls.COUNT) + " " + cls.CONTRACTOR.display_name + " contractors on its own spot (with its Camo and "
                "Regrow); they pay their normal bounty.")

    def get_timer(self):
        return max(0.0, self._timer)

    def get_since(self):
        return self._since

    def get_spawned(self):
        return self._spawned

    def status_text(self, b):
        return "OUTSOURCING IN " + str(int(self._timer + 0.999)) + "s"


class NetworkHub(BossAbility):
    """ZOMG: every other enemy within RADIUS takes half damage (the Heap Sort shield, refreshed every tick) and 3Com
    repairs REGEN of its max HP per second."""
    NAME = "Network Hub"
    RGB = 0x4fe0c8
    RADIUS = 200.0
    REGEN = 0.006

    def __init__(self):
        BossAbility.__init__(self)
        self._linked = []
        self._healed = 0.0
        self._scratch = []

    def update(self, game, b, dt):
        if self._fired == 0:
            self._announce(game, b, "NETWORK HUB", b.get_type().display_name + " is a NETWORK HUB: enemies near it take half damage")
        tick = game.get_tick()
        p = b.get_position()
        r2 = self.RADIUS * self.RADIUS
        linked = self._linked
        linked.clear()
        for o in game.get_enemy_manager().get_grid().near(p.x, p.y, self.RADIUS, self._scratch):
            if o is b or not o._alive or o._stored:
                continue
            q = o._cached_pos
            dx = q.x - p.x
            dy = q.y - p.y
            if dx * dx + dy * dy <= r2:
                o.set_shielded_tick(tick)
                linked.append(o)
        if b.get_hp() < b.get_max_hp():
            before = b.get_hp()
            b.heal(self.REGEN * b.get_max_hp() * dt)
            self._healed += b.get_hp() - before

    @classmethod
    def describe(cls):
        return ("NETWORK HUB: every other enemy within " + _n(cls.RADIUS) + " px takes half damage (like a Heap Sort's "
                "shield), and 3Com repairs " + _pct(cls.REGEN) + " of its max HP per second.")

    def get_linked(self):
        return self._linked

    def get_healed(self):
        return self._healed

    def status_text(self, b):
        return "NETWORK HUB  " + str(len(self._linked)) + " LINKED"


class Afterburner(BossAbility):
    """DDT: every INTERVAL s (the first after FIRST s) it lights its afterburner for DURATION s at BOOST x speed."""
    NAME = "Afterburner"
    RGB = 0xff7a3a
    FIRST = 5.0
    INTERVAL = 7.0
    DURATION = 1.0
    BOOST = 1.5

    def __init__(self):
        BossAbility.__init__(self)
        self._timer = self.FIRST
        self._burn = 0.0

    def update(self, game, b, dt):
        if self._burn > 0:
            self._burn = max(0.0, self._burn - dt)
        self._timer -= dt
        if self._timer > 0:
            return
        self._timer = self.INTERVAL
        self._burn = self.DURATION
        self._announce(game, b, "AFTERBURNER", b.get_type().display_name + " hits the AFTERBURNER: " + _n(self.BOOST) + "x speed for "
                       + _n(self.DURATION) + " s every " + _n(self.INTERVAL) + " s")

    @classmethod
    def describe(cls):
        return ("AFTERBURNER: " + _n(cls.FIRST) + " s after it appears and every " + _n(cls.INTERVAL) + " s after that it "
                "multiplies its speed by " + _n(cls.BOOST) + " for " + _n(cls.DURATION) + " s.")

    def is_burning(self):
        return self._burn > 0

    def get_burn_remaining(self):
        return self._burn

    def get_timer(self):
        return max(0.0, self._timer)

    def speed_multiplier(self):
        return self.BOOST if self._burn > 0 else 1.0

    def status_text(self, b):
        return "AFTERBURNER!" if self._burn > 0 else "AFTERBURNER IN " + str(int(self._timer + 0.999)) + "s"


_BY_TYPE = {
    EnemyType.BELLARMINE_COLLEGE_PREP: CrestShield,
    EnemyType.SW_RESOURCE_CONSULTANT: Outsourcing,
    EnemyType.THREE_COM: NetworkHub,
    EnemyType.LOCKHEED_MARTIN: Afterburner,
}


def create(type_):
    """A fresh ability for a boss of this type (None for Palantir, which has PalantirProtocols, and for non-bosses)."""
    cls = _BY_TYPE.get(type_)
    return None if cls is None else cls()


def ability_class(type_):
    return _BY_TYPE.get(type_)


def describe(type_):
    """The boss type's ability sentence ('' when it has none)."""
    cls = _BY_TYPE.get(type_)
    return "" if cls is None else cls.describe()
