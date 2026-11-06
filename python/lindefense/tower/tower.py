"""A placed tower (position, tier, targeting, buff book, ability cooldown, per-tower memory) and its
prompt-injection state (Intrusion)."""
import sys

from lindefense.javacompat import jround, jint
from lindefense.tower.tower_type import AttackKind, BuffStat, Targeting, TowerType

_STAT_COUNT = len(BuffStat)
_TYPE_COUNT = len(TowerType)
_MAX = sys.float_info.max


class Intrusion:
    """Hijacked / disabled / blinded timers (towers have no health: cyber attacks take them offline)."""
    GRACE = 4.0

    def __init__(self):
        self._hijacked = 0.0
        self._disabled = 0.0
        self._blinded = 0.0
        self._grace = 0.0
        self._hijacker = None
        self._disabled_by = None
        self._zap_timer = 0.0
        self._zaps_left = 0
        self._firewalled = False
        self._last_victim = None
        self._last_zap_age = 99.0
        self._age = 99.0
        self._total = 0.0

    def is_hijacked(self):
        return self._hijacked > 0

    def is_disabled(self):
        return self._disabled > 0

    def is_blinded(self):
        return self._blinded > 0

    def is_offline(self):
        return self._hijacked > 0 or self._disabled > 0 or self._blinded > 0

    def is_patched(self):
        return self._grace > 0

    def can_be_compromised(self):
        return not self.is_offline() and self._grace <= 0

    def get_remaining(self):
        return max(self._hijacked, max(self._disabled, self._blinded))

    def get_grace_remaining(self):
        return self._grace

    def get_age(self):
        return self._age

    def get_hijacker(self):
        return self._hijacker if self.is_hijacked() else None

    def get_disabled_by(self):
        return self._disabled_by if self.is_disabled() else None

    def get_last_victim(self):
        return self._last_victim

    def get_last_zap_age(self):
        return self._last_zap_age

    def get_zaps_left(self):
        return self._zaps_left if self.is_hijacked() else 0

    def get_total_offline_time(self):
        return self._total

    def is_firewalled(self):
        return self._firewalled

    def hijack(self, seconds, source, first_zap, zaps) -> bool:
        if seconds <= 0 or not self.can_be_compromised():
            return False
        self._hijacked = seconds
        self._hijacker = source
        self._zap_timer = first_zap
        self._zaps_left = zaps
        self._last_victim = None
        self._last_zap_age = 99.0
        self._age = 0.0
        return True

    def disable(self, seconds, by) -> bool:
        if seconds <= 0 or not self.can_be_compromised():
            return False
        self._disabled = seconds
        self._disabled_by = by
        self._age = 0.0
        return True

    def blind(self, seconds) -> bool:
        if seconds <= 0 or not self.can_be_compromised():
            return False
        self._blinded = seconds
        self._age = 0.0
        return True

    def zap_due(self, dt) -> bool:
        if not self.is_hijacked() or self._zaps_left <= 0:
            return False
        self._zap_timer -= dt
        if self._zap_timer > 0:
            return False
        self._zaps_left -= 1
        self._zap_timer = _MAX
        return True

    def record_zap(self, victim, next_in):
        if victim is not None:
            self._last_victim = victim
            self._last_zap_age = 0.0
        self._zap_timer = next_in

    def clear(self):
        was = self.is_offline()
        self._hijacked = self._disabled = self._blinded = 0.0
        if was:
            self._grace = self.GRACE

    def set_firewalled(self, on):
        self._firewalled = on

    def tick(self, dt):
        self._age += dt
        self._last_zap_age += dt
        was = self.is_offline()
        if was:
            self._total += dt
        if self._hijacked > 0:
            self._hijacked = max(0.0, self._hijacked - dt)
        if self._disabled > 0:
            self._disabled = max(0.0, self._disabled - dt)
        if self._blinded > 0:
            self._blinded = max(0.0, self._blinded - dt)
        if self._grace > 0:
            self._grace = max(0.0, self._grace - dt)
        if was and not self.is_offline():
            self._grace = self.GRACE


class _TimedBuff:
    __slots__ = ("stat", "source", "value", "remaining")

    def __init__(self, stat, source, value, remaining):
        self.stat, self.source, self.value, self.remaining = stat, source, value, remaining


class _SelfBuff:
    __slots__ = ("key", "rate_mult", "projectile_speed_mult", "remaining")

    def __init__(self, key, r, p, t):
        self.key, self.rate_mult, self.projectile_speed_mult, self.remaining = key, r, p, t


class _MapBuff:
    __slots__ = ("rate_mult", "dmg_mult", "range_mult", "remaining")

    def __init__(self, r, d, g, t):
        self.rate_mult, self.dmg_mult, self.range_mult, self.remaining = r, d, g, t


class Tower:
    _next_id = 1

    def __init__(self, def_, position, tier: int = 0, temporary: bool = False, lifetime: float = 0.0, owner=None):
        from lindefense.tower import catalog
        from lindefense.tower.behavior.registry import behavior_of
        self._id = Tower._next_id
        Tower._next_id += 1
        self._def = def_
        self._position = position
        self._tier = tier
        self._stats = def_.stats_for_tier(tier)
        self._temporary = temporary
        self._lifetime = lifetime
        self._owner = owner
        self._behavior = behavior_of(def_.type)
        self._targeting = def_.default_targeting
        self._alive = True
        self._attack_cooldown = 0.0
        usable = def_.ability is not None and not catalog.ability_needs_unlock(def_.type)
        self._ability_cooldown = def_.ability.cooldown * 0.5 if usable else 0.0
        self._ability_unlocked = False
        self._surveilled_remaining = 0.0
        self._intrusion = Intrusion()
        self._aura_buffs = [[0.0] * _TYPE_COUNT for _ in range(_STAT_COUNT)]
        self._timed_buffs = []
        self._self_buffs = []
        self._map_buffs = []
        self._granted_detection = False
        self._surveillance_immune = False
        self._counters = {}
        self._state = {}
        self._streak_target_id = -1
        self._streak_count = 0
        self._damage_dealt = 0.0
        self._kills = 0
        self._last_target = None
        self._last_fire_time = -10.0

    # ---------------- identity
    def get_id(self):
        return self._id

    def get_def(self):
        return self._def

    def get_type(self):
        return self._def.type

    def get_position(self):
        return self._position

    def get_tier(self):
        return self._tier

    def get_max_tier(self):
        return len(self._def.upgrades)

    def is_superclass(self):
        return self._tier >= len(self._def.upgrades)

    def is_maxed(self):
        return self._tier >= len(self._def.upgrades)

    def get_stats(self):
        return self._stats

    def get_behavior(self):
        return self._behavior

    def get_targeting(self):
        return self._targeting

    def set_targeting(self, t):
        if t is Targeting.DENSEST_CLUSTER and not self.can_use_densest_cluster():
            return
        self._targeting = t

    def can_use_densest_cluster(self):
        return self._behavior.allows_densest_cluster(self)

    def cycle_targeting(self, direction: int):
        allt = list(Targeting)
        t = self._targeting
        for _ in range(len(allt)):
            t = allt[(t.ordinal + (1 if direction >= 0 else len(allt) - 1)) % len(allt)]
            if t is not Targeting.DENSEST_CLUSTER or self.can_use_densest_cluster():
                self._targeting = t
                return

    def is_alive(self):
        return self._alive

    def mark_removed(self):
        self._alive = False

    def is_temporary(self):
        return self._temporary

    def get_lifetime(self):
        return self._lifetime

    def get_owner(self):
        return self._owner

    def get_tier_label(self):
        labels = self._def.tier_labels
        return labels[min(self._tier, len(labels) - 1)]

    def get_radius(self):
        return self._def.radius

    def get_damage_dealt(self):
        return self._damage_dealt

    def get_kills(self):
        return self._kills

    def add_damage_dealt(self, d):
        self._damage_dealt += d

    def add_kill(self):
        self._kills += 1

    def get_last_target(self):
        return self._last_target

    def set_last_target(self, e):
        self._last_target = e

    def get_last_fire_time(self):
        return self._last_fire_time

    def set_last_fire_time(self, t):
        self._last_fire_time = t

    # ---------------- economy
    def get_invested_cost(self) -> int:
        from lindefense.tower import catalog
        return self._def.total_cost_for_tier(self._tier) + (catalog.ABILITY_UNLOCK_COST if self._ability_unlocked else 0)

    def can_upgrade(self):
        return self._tier < len(self._def.upgrades)

    def next_upgrade(self):
        return self._def.upgrades[self._tier] if self.can_upgrade() else None

    def apply_upgrade(self, game):
        if not self.can_upgrade():
            return
        self._tier += 1
        self._stats = self._def.stats_for_tier(self._tier)
        self._behavior.on_upgraded(game, self)

    # ---------------- buff book
    def add_aura_buff(self, stat, source, value):
        row = self._aura_buffs[stat.ordinal]
        if value > row[source.ordinal]:
            row[source.ordinal] = value

    def add_timed_buff(self, stat, source, value, duration):
        for b in self._timed_buffs:
            if b.stat is stat and b.source is source and b.value == value:
                b.remaining = max(b.remaining, duration)
                return
        self._timed_buffs.append(_TimedBuff(stat, source, value, duration))

    def buff_total_uncapped(self, stat) -> float:
        row = self._aura_buffs[stat.ordinal]
        timed = [b for b in self._timed_buffs if b.stat is stat]
        if not timed:
            s = 0.0
            for v in row:
                s += v
            return s
        total = 0.0
        for ti in range(_TYPE_COUNT):
            best = row[ti]
            for b in timed:
                if b.source.ordinal == ti and b.value > best:
                    best = b.value
            total += best
        return total

    def buff_total(self, stat) -> float:
        return min(stat.cap, self.buff_total_uncapped(stat))

    def add_buff(self, rate_mult, dmg_mult, range_mult, duration):
        self._map_buffs.append(_MapBuff(rate_mult, dmg_mult, range_mult, duration))

    def _map_rate(self):
        m = 1.0
        for b in self._map_buffs:
            m *= b.rate_mult
        return m

    def _map_damage(self):
        m = 1.0
        for b in self._map_buffs:
            m *= b.dmg_mult
        return m

    def _map_range(self):
        m = 1.0
        for b in self._map_buffs:
            m *= b.range_mult
        return m

    def add_self_buff(self, key, rate_mult, projectile_speed_mult, duration):
        self._self_buffs = [b for b in self._self_buffs if b.key != key]
        self._self_buffs.append(_SelfBuff(key, rate_mult, projectile_speed_mult, duration))

    def has_self_buff(self, key):
        return any(b.key == key for b in self._self_buffs)

    def self_buff_remaining(self, key):
        for b in self._self_buffs:
            if b.key == key:
                return b.remaining
        return 0.0

    def timed_buff_remaining(self, source):
        best = 0.0
        for b in self._timed_buffs:
            if b.source is source:
                best = max(best, b.remaining)
        return best

    def self_rate_mult(self):
        m = 1.0
        for b in self._self_buffs:
            m *= b.rate_mult
        return m

    def projectile_speed_mult(self):
        m = 1.0
        for b in self._self_buffs:
            m *= b.projectile_speed_mult
        return m

    def effective_pierce(self) -> int:
        flat = self.buff_total_uncapped(BuffStat.PIERCE_FLAT)
        pct = self.buff_total_uncapped(BuffStat.PIERCE_PCT)
        add = min(BuffStat.PIERCE_FLAT.cap, flat + jround(self._stats.pierce * pct))
        return self._stats.pierce + jint(add)

    def flat_damage_buff(self):
        return self.buff_total(BuffStat.DAMAGE_FLAT)

    def boss_damage_buff(self):
        return self.buff_total(BuffStat.BOSS_DAMAGE_PCT)

    def reset_aura_bonuses(self):
        for row in self._aura_buffs:
            for i in range(len(row)):
                row[i] = 0.0
        self._granted_detection = False
        self._surveillance_immune = False
        self._intrusion.set_firewalled(False)

    def grant_detection(self):
        self._granted_detection = True

    def grant_surveillance_immunity(self):
        self._surveillance_immune = True

    def grant_injection_firewall(self):
        self._intrusion.set_firewalled(True)

    def is_surveillance_immune(self):
        return self._surveillance_immune or self._stats.aura_surveillance_immunity

    def can_see_camo(self):
        return self._stats.sees_camo or self._granted_detection

    def rate_multiplier(self, game):
        return 1.0 if self._stats.rate <= 0 else self.effective_rate(game) / self._stats.rate

    def get_aura_rate_bonus(self):
        return self.buff_total(BuffStat.RATE)

    def get_aura_damage_bonus(self):
        return self.flat_damage_buff()

    def set_surveilled(self, duration):
        self._surveilled_remaining = max(self._surveilled_remaining, duration)

    def clear_surveilled(self):
        self._surveilled_remaining = 0.0

    def is_surveilled(self):
        return self._surveilled_remaining > 0

    def get_surveilled_remaining(self):
        return self._surveilled_remaining

    # ---------------- prompt injection
    def get_intrusion(self):
        return self._intrusion

    def is_offline(self):
        return self._intrusion.is_offline()

    def is_hijacked(self):
        return self._intrusion.is_hijacked()

    def is_injection_immune(self):
        return self._stats.injection_immune or self._intrusion.is_firewalled()

    # ---------------- ability
    def get_ability(self):
        return None if self.is_ability_locked() else self._def.ability

    def get_ability_def(self):
        return self._def.ability

    def is_ability_locked(self):
        from lindefense.tower import catalog
        return self._def.ability is not None and catalog.ability_needs_unlock(self._def.type) and not self._ability_unlocked

    def can_unlock_ability(self):
        return self.is_ability_locked() and self.is_maxed() and not self._temporary

    def unlock_ability(self):
        if not self.is_ability_locked():
            return
        self._ability_unlocked = True
        self._ability_cooldown = 0.0

    def is_ability_unlocked(self):
        return self._ability_unlocked

    def is_ability_ready(self):
        return (self.get_ability() is not None and self._ability_cooldown <= 0
                and not self.is_surveilled() and not self._intrusion.is_offline())

    def get_ability_cooldown_remaining(self):
        return self._ability_cooldown

    def get_ability_cooldown_fraction(self):
        a = self.get_ability()
        return 0.0 if a is None else max(0.0, self._ability_cooldown / a.cooldown)

    def start_ability_cooldown(self):
        a = self.get_ability()
        if a is not None:
            self._ability_cooldown = a.cooldown

    def reset_ability_cooldown(self):
        self._ability_cooldown = 0.0

    def reduce_ability_cooldown(self, fraction):
        self._ability_cooldown *= (1 - fraction)

    # ---------------- per-tower memory
    def counter(self, key) -> float:
        return self._counters.get(key, 0.0)

    def set_counter(self, key, v):
        self._counters[key] = float(v)

    def add_counter(self, key, delta) -> float:
        v = self.counter(key) + delta
        self._counters[key] = v
        return v

    def counters(self):
        return self._counters

    def state(self):
        return self._state

    def periodic(self, key, interval, dt) -> bool:
        c = self.counter(key) + dt
        if c >= interval:
            self._counters[key] = c - interval
            return True
        self._counters[key] = c
        return False

    def register_streak(self, enemy_id) -> int:
        if enemy_id == self._streak_target_id:
            self._streak_count += 1
            return self._streak_count - 1
        self._streak_target_id = enemy_id
        self._streak_count = 1
        return 0

    def reset_streak(self):
        self._streak_target_id = -1
        self._streak_count = 0

    def get_streak_target_id(self):
        return self._streak_target_id

    # ---------------- effective numbers
    def effective_range(self, game) -> float:
        r = (self._stats.range + self._behavior.flat_range_bonus(self)) * (1 + self.buff_total(BuffStat.RANGE)) * self._map_range()
        if game is not None:
            r *= game.get_map().tower_range_multiplier(game, self) * game.get_global_range_multiplier()
        if self.is_surveilled():
            r *= 0.7
        return r

    def effective_rate(self, game) -> float:
        r = self._stats.rate * (1 + self.buff_total(BuffStat.RATE)) * self.self_rate_mult() * self._map_rate()
        if game is not None:
            r *= game.get_map().tower_rate_multiplier(game, self)
            r *= game.get_global_rate_multiplier()
        if self.is_surveilled():
            r *= 0.5
        return r

    def damage_multiplier(self, game) -> float:
        m = self._map_damage()
        if game is not None:
            m *= game.get_map().tower_damage_multiplier(game, self)
            m *= game.get_global_damage_multiplier()
        return m

    # ---------------- per tick
    def tick_timers(self, game, dt) -> bool:
        if self._temporary:
            self._lifetime -= dt
            if self._lifetime <= 0:
                self._alive = False
        for lst in (self._timed_buffs, self._map_buffs, self._self_buffs):
            for i in range(len(lst) - 1, -1, -1):
                b = lst[i]
                b.remaining -= dt
                if b.remaining <= 0:
                    del lst[i]
        if self._ability_cooldown > 0:
            self._ability_cooldown = max(0.0, self._ability_cooldown - dt)
        if self._surveilled_remaining > 0:
            self._surveilled_remaining = max(0.0, self._surveilled_remaining - dt)
        self._intrusion.tick(dt)
        if self._stats.kind is AttackKind.NONE:
            return False
        self._attack_cooldown -= dt
        return self._attack_cooldown <= 0

    def on_attacked(self, game):
        rate = max(0.05, self.effective_rate(game))
        self._attack_cooldown = max(self._attack_cooldown + 1.0 / rate, 1.0 / rate * 0.5)
        if self._attack_cooldown > 1.0 / rate:
            self._attack_cooldown = 1.0 / rate
        self._last_fire_time = game.get_time()

    def idle(self):
        self._attack_cooldown = max(self._attack_cooldown, 0.0)

    def __repr__(self):
        return "%s#%d(T%d)" % (self._def.type.display_name, self._id, self._tier)
