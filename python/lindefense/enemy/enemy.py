"""A single enemy on the track: HP, modifiers, statuses and path progress (distance along a route)."""
from lindefense.javacompat import jround
from lindefense.jenum import EnumSet
from lindefense.enemy.types import Mechanic, Modifier, StatusEffect, StatusKind

_KIND_COUNT = len(StatusKind)
_SLOW = StatusKind.SLOW.ordinal
_STUN = StatusKind.STUN.ordinal
_FREEZE = StatusKind.FREEZE.ordinal
_DOT = StatusKind.DOT
_K_SLOW = StatusKind.SLOW
_K_STUN = StatusKind.STUN
_K_FREEZE = StatusKind.FREEZE
_K_MARKED = StatusKind.MARKED
_K_MARKED_FLAT = StatusKind.MARKED_FLAT
_CAMO = Modifier.CAMO
_REGROW = Modifier.REGROW
_DISRUPTED = StatusKind.DISRUPTED.ordinal
_REVEALED = StatusKind.REVEALED.ordinal
_ARMOR_CRACK = StatusKind.ARMOR_CRACK.ordinal
_MARKED = StatusKind.MARKED.ordinal
_MARKED_FLAT = StatusKind.MARKED_FLAT.ordinal


def max_magnitude(lst) -> float:
    """status_magnitude: the strongest entry of one status list (0 when there is none)."""
    m = 0.0
    if lst:
        for s in lst:
            if s.magnitude > m:
                m = s.magnitude
    return m


class Enemy:
    BASE_SPEED = 60.0
    BOSS_SLOW_DIVISOR = 3.0
    FAST_SPEED_MULT = 2.0
    REGROW_INTERVAL = 2.0
    SHELL_GAPS = (140.0, 70.0, 35.0, 18.0)
    KNOCKBACK_BUDGET = 0.40
    BOSS_KNOCKBACK_BUDGET = 0.25

    _next_id = 1

    def __init__(self, type_, modifiers, route, route_index: int, distance: float, hp_scale: float, speed_scale: float):
        self._id = Enemy._next_id
        Enemy._next_id += 1
        self._type = type_
        self._is_boss = type_.is_boss()   # the type never changes; read on every hit, status and zone check
        self._modifiers = EnumSet() if modifiers is None else EnumSet(set.__iter__(modifiers) if isinstance(modifiers, set) else modifiers)
        if type_.has_innate_camo():
            self._modifiers.add(Modifier.CAMO)
        self._hp_scale = hp_scale
        self._speed_scale = speed_scale
        base = float(max(1, jround(type_.base_hp * hp_scale)))
        self._max_hp = base * 2 if Modifier.FORTIFIED in self._modifiers else base
        self._hp = self._max_hp
        self._radius = self._compute_radius()   # read thousands of times a step; changes only in strip_fortified
        self._route = route
        self._route_index = route_index
        self._distance = max(0.0, distance)
        self._alive = True
        self._leaked = False
        self._stored = False
        self._statuses = [None] * _KIND_COUNT   # per StatusKind ordinal: None until first applied, then a list
        self._status_lists = []   # the lists created so far (what tick_statuses walks)
        self._dot_source = None
        self._reverse_remaining = 0.0
        self._reverse_dps = 0.0
        self._reverse_source = None
        self._hold_remaining = 0.0
        self._hold_distance = 0.0
        self._hold_pull = 0.0
        self._regrow_timer = 0.0
        self._mechanic_timer = 0.0
        self._shell_jump_index = 0
        self._accel_bonus = 0.0
        self._shielded_tick = -1000
        self._drifted = False
        self._times_hit = 0
        self._last_hit_time = -10.0
        self._spawn_time = 0.0
        self._last_hit_by = None
        self._kb_window_start = -1.0
        self._kb_used = 0.0
        self._stored_list = []
        self._cached_pos = route.position_at(self._distance)
        # spatial-grid bookkeeping, owned by EnemyGrid
        self.grid = None
        self.grid_epoch = -1
        self.grid_index = 0
        self.grid_col = 0
        self.grid_row = 0

    # ---------------- basic accessors
    def get_id(self):
        return self._id

    def get_type(self):
        return self._type

    def get_modifiers(self):
        return self._modifiers

    def has(self, m) -> bool:
        return m in self._modifiers

    def is_camo(self):
        return Modifier.CAMO in self._modifiers

    def is_fortified(self):
        return Modifier.FORTIFIED in self._modifiers

    def is_regrow(self):
        return Modifier.REGROW in self._modifiers

    def is_boss(self):
        return self._is_boss

    def get_max_hp(self):
        return self._max_hp

    def get_hp(self):
        return self._hp

    def get_hp_fraction(self):
        return 0.0 if self._max_hp <= 0 else self._hp / self._max_hp

    def get_route(self):
        return self._route

    def get_route_index(self):
        return self._route_index

    def get_distance(self):
        return self._distance

    def get_remaining_distance(self):
        return self._route.get_total_length() - self._distance

    def is_alive(self):
        return self._alive

    def has_leaked(self):
        return self._leaked

    def is_stored(self):
        return self._stored

    def get_hp_scale(self):
        return self._hp_scale

    def get_speed_scale(self):
        return self._speed_scale

    def get_position(self):
        return self._cached_pos

    def get_radius(self):
        return self._radius

    def _compute_radius(self):
        return self._type.radius * (1.0 if self.is_boss() else (1.15 if self.is_fortified() else 1.0))

    def get_stored_enemies(self):
        return self._stored_list

    def has_drifted(self):
        return self._drifted

    def set_drifted(self, d):
        self._drifted = d

    def get_times_hit(self):
        return self._times_hit

    def get_last_hit_time(self):
        return self._last_hit_time

    def get_spawn_time(self):
        return self._spawn_time

    def set_spawn_time(self, t):
        self._spawn_time = t

    def get_last_hit_by(self):
        return self._last_hit_by

    def set_last_hit_by(self, src):
        self._last_hit_by = src

    def get_mechanic_timer(self):
        return self._mechanic_timer

    def set_mechanic_timer(self, t):
        self._mechanic_timer = t

    def get_shell_jump_index(self):
        return self._shell_jump_index

    def set_shell_jump_index(self, i):
        self._shell_jump_index = i

    def get_accel_bonus(self):
        return self._accel_bonus

    def current_shell_gap(self):
        return self.SHELL_GAPS[min(self._shell_jump_index, len(self.SHELL_GAPS) - 1)]

    # ---------------- modifiers
    def strip_fortified(self) -> bool:
        if Modifier.FORTIFIED not in self._modifiers:
            return False
        self._modifiers.discard(Modifier.FORTIFIED)
        self._radius = self._compute_radius()
        import math
        self._max_hp = max(1.0, float(math.ceil(self._max_hp / 2)))
        self._hp = min(self._hp, self._max_hp)
        return True

    def strip_camo_regrow(self) -> bool:
        if self.is_boss():
            return False
        changed = Modifier.CAMO in self._modifiers or Modifier.REGROW in self._modifiers
        self._modifiers.discard(Modifier.CAMO)
        self._modifiers.discard(Modifier.REGROW)
        return changed

    # ---------------- statuses
    def apply_status(self, kind, magnitude: float, duration: float, boss_override: bool = False) -> bool:
        if duration <= 0 or not self._alive:
            return False
        if kind is _K_SLOW:
            if self.is_control_immune():
                return False
            if self._is_boss:
                magnitude /= self.BOSS_SLOW_DIVISOR
        elif kind is _K_STUN or kind is _K_FREEZE:
            if self.is_control_immune():
                return False
            if self._is_boss and not boss_override:
                return False
        lst = self._statuses[kind._value_]   # kind.ordinal
        if lst is None:
            lst = []
            self._statuses[kind._value_] = lst
            self._status_lists.append(lst)
        if kind is _K_SLOW or kind is _K_MARKED or kind is _K_MARKED_FLAT:   # several magnitudes may coexist
            for s in lst:
                if -1e-9 < s.magnitude - magnitude < 1e-9:   # abs(...) < 1e-9
                    if duration > s.remaining:   # s.remaining = max(s.remaining, duration)
                        s.remaining = duration
                    return True
            lst.append(StatusEffect(kind, magnitude, duration))
            return True
        if not lst:
            lst.append(StatusEffect(kind, magnitude, duration))
        else:
            s = lst[0]
            s.magnitude = max(s.magnitude, magnitude)
            s.remaining = duration if kind is _DOT else max(s.remaining, duration)
        return True

    def apply_exact_slow(self, magnitude: float, duration: float) -> bool:
        return self.apply_status(StatusKind.SLOW, magnitude * self.BOSS_SLOW_DIVISOR if self.is_boss() else magnitude, duration)

    def apply_burn(self, dps: float, duration: float, source) -> None:
        if self.apply_status(StatusKind.DOT, dps, duration) and source is not None:
            self._dot_source = source

    def get_dot_source(self):
        return self._dot_source

    def is_control_immune(self) -> bool:
        return False

    def has_status(self, kind) -> bool:
        lst = self._statuses[kind.ordinal]
        return bool(lst)

    def status_magnitude(self, kind) -> float:
        return max_magnitude(self._statuses[kind.ordinal])

    def clear_status(self, kind) -> None:
        lst = self._statuses[kind.ordinal]
        if lst is not None:
            lst.clear()

    def is_stunned(self) -> bool:
        st = self._statuses
        return bool(st[_STUN]) or bool(st[_FREEZE])

    def is_frozen(self) -> bool:
        return bool(self._statuses[_FREEZE])

    # the status queries below are has_status / status_magnitude with the kind's ordinal precomputed
    def is_disrupted(self) -> bool:
        return bool(self._statuses[_DISRUPTED])

    def is_revealed(self) -> bool:
        return bool(self._statuses[_REVEALED])

    def get_slow_fraction(self) -> float:
        return max_magnitude(self._statuses[_SLOW])

    def is_armor_cracked(self) -> bool:
        return bool(self._statuses[_ARMOR_CRACK])

    def get_marked_bonus(self) -> float:
        return max_magnitude(self._statuses[_MARKED])

    def get_marked_flat(self) -> float:
        return max_magnitude(self._statuses[_MARKED_FLAT])

    # ---------------- armour classes
    def is_lead_type(self) -> bool:
        return self._type.is_lead_body() or (self._type.mechanic is Mechanic.RADIX_PHASES and self.radix_phase() >= 1)

    def is_ceramic_type(self) -> bool:
        return self._type.is_ceramic_body()

    def is_moab_class(self) -> bool:
        return self.is_boss()

    def is_fast_for_knockback(self) -> bool:
        return self._type.is_linked_list() or self.speed_multiplier() >= self.FAST_SPEED_MULT

    def is_targetable_by(self, tower_sees_camo: bool) -> bool:
        if not self._alive or self._stored:
            return False
        return _CAMO not in self._modifiers or tower_sees_camo or self.is_revealed()

    # ---------------- shielding (Heap Sort)
    def set_shielded_tick(self, tick: int) -> None:
        self._shielded_tick = tick

    def is_shielded(self, current_tick: int) -> bool:
        return self._shielded_tick >= current_tick - 1

    # ---------------- Radix phases
    def radix_phase(self) -> int:
        if self._type.mechanic is not Mechanic.RADIX_PHASES:
            return 0
        layers = self._hp / self._hp_scale / (2 if self.is_fortified() else 1)
        if layers > 6:
            return 0
        if layers > 4:
            return 1
        if layers > 2:
            return 2
        return 3

    def effective_armor(self) -> float:
        return max(0.0, self.base_armor())

    def base_armor(self) -> float:
        return self._type.get_armor()

    def own_speed_multiplier(self) -> float:
        return 1.0 + self._accel_bonus

    # ---------------- damage
    def take_damage(self, amount: float, now: float) -> float:
        if not self._alive or amount <= 0:
            return 0.0
        before = self._hp
        hp = before - amount
        self._hp = hp if hp > 0.0 else 0.0   # max(0.0, hp)
        self._times_hit += 1
        self._last_hit_time = now
        if self._type.mechanic is Mechanic.ACCELERATE_ON_DAMAGE:
            self._accel_bonus = min(0.9, self._accel_bonus + 0.15)
        return before - self._hp

    def heal(self, amount: float) -> None:
        if not self._alive:
            return
        self._hp = min(self._max_hp, self._hp + amount)

    def mark_dead(self):
        self._alive = False

    def mark_leaked(self):
        self._leaked = True
        self._alive = False

    def set_stored(self, s: bool):
        self._stored = s

    # ---------------- movement
    def speed_multiplier(self) -> float:
        return self._type.speed * self._speed_scale * self.own_speed_multiplier()

    def nominal_speed(self) -> float:
        return self.speed_multiplier() * self.BASE_SPEED

    def _live_speed(self, external: float) -> float:
        return self.nominal_speed() * (1.0 - min(0.9, self.get_slow_fraction())) * external

    def advance(self, dt: float, external: float) -> bool:
        if not self._alive or self._stored:
            return False
        dist = self._distance
        if self._hold_remaining > 0:
            step = self._hold_pull * dt
            diff = self._hold_distance - dist
            dist += max(-step, min(step, diff))
        else:
            st = self._statuses
            if not (st[_STUN] or st[_FREEZE]):   # is_stunned()
                # _live_speed(external) * dt with the getters inlined (same operations, same order)
                slow = 0.0   # get_slow_fraction()
                slows = st[_SLOW]
                if slows:
                    for s in slows:
                        if s.magnitude > slow:
                            slow = s.magnitude
                # own_speed_multiplier(): only Boss overrides it (and returns the same for a non-boss type)
                osm = self.own_speed_multiplier() if self._is_boss else 1.0 + self._accel_bonus
                d = (self._type.speed * self._speed_scale * osm * self.BASE_SPEED
                     * (1.0 - (slow if slow < 0.9 else 0.9)) * external) * dt   # min(0.9, slow)
                if self._reverse_remaining > 0:
                    dist = max(0.0, dist - d)
                else:
                    dist += d
        dist = dist if dist > 0.0 else 0.0   # max(0.0, dist)
        self._distance = dist
        route = self._route
        self._cached_pos = route.position_at(dist)
        if self.grid is not None:
            self.grid.moved(self)
        return dist >= route._total_length

    def current_speed(self, external: float) -> float:
        if self.is_stunned() or self._hold_remaining > 0:
            return 0.0
        return self._live_speed(external)

    def apply_knockback(self, px: float, now: float) -> float:
        if px <= 0 or not self._alive or self.is_control_immune():
            return 0.0
        if now - self._kb_window_start >= 1.0:
            self._kb_window_start = now
            self._kb_used = 0.0
        cap = self._type.speed * self.BASE_SPEED * self._speed_scale * (
            self.BOSS_KNOCKBACK_BUDGET if self.is_boss() else self.KNOCKBACK_BUDGET)
        applied = min(px, max(0.0, cap - self._kb_used))
        if applied <= 0:
            return 0.0
        self._kb_used += applied
        self.shift_distance(-applied)
        return applied

    def apply_knockback_uncapped(self, px: float) -> float:
        if px <= 0 or not self._alive or self.is_control_immune():
            return 0.0
        before = self._distance
        self.shift_distance(-px)
        return before - self._distance

    def shift_distance(self, delta: float) -> None:
        self._distance = max(0.0, min(self._route.get_total_length() - 0.01, self._distance + delta))
        self._cached_pos = self._route.position_at(self._distance)
        if self.grid is not None:
            self.grid.moved(self)

    def set_distance(self, d: float) -> None:
        self._distance = max(0.0, min(self._route.get_total_length() - 0.01, d))
        self._cached_pos = self._route.position_at(self._distance)
        if self.grid is not None:
            self.grid.moved(self)

    def teleport_to(self, new_route, new_route_index: int, new_distance: float) -> None:
        self._route = new_route
        self._route_index = new_route_index
        self.set_distance(new_distance)

    # ---------------- enemy-level operations
    def rewind(self, seconds: float) -> float:
        before = self._distance
        self.shift_distance(-self.nominal_speed() * seconds)
        return before - self._distance

    def hold(self, duration: float, at_distance: float, pull_speed: float) -> bool:
        if duration <= 0 or not self._alive or self.is_control_immune():
            return False
        self._hold_remaining = max(self._hold_remaining, duration)
        self._hold_distance = at_distance
        self._hold_pull = pull_speed
        return True

    def is_held(self) -> bool:
        return self._hold_remaining > 0

    def start_reverse(self, duration: float, contact_dps: float, source) -> None:
        self._reverse_remaining = max(self._reverse_remaining, duration)
        self._reverse_dps = contact_dps
        self._reverse_source = source

    def is_reversed(self) -> bool:
        return self._reverse_remaining > 0

    def get_reverse_dps(self) -> float:
        return self._reverse_dps

    def get_reverse_source(self):
        return self._reverse_source

    # ---------------- per-tick upkeep
    def tick_statuses(self, dt: float) -> float:
        dot = 0.0
        # lists are independent and only DOT entries add to dot, so walking them in creation order (instead of
        # ordinal order, skipping kinds never applied) changes nothing
        for lst in self._status_lists:
            if not lst:
                continue
            if len(lst) == 1:   # the common case, without the index loop
                s = lst[0]
                s.remaining -= dt
                if s.kind is _DOT:
                    dot += s.magnitude * dt
                if s.remaining <= 0:
                    lst.clear()
                continue
            for i in range(len(lst) - 1, -1, -1):
                s = lst[i]
                s.remaining -= dt
                if s.kind is _DOT:
                    dot += s.magnitude * dt
                if s.remaining <= 0:
                    del lst[i]
        if self._hold_remaining > 0:
            self._hold_remaining = max(0.0, self._hold_remaining - dt)
        if self._reverse_remaining > 0:
            self._reverse_remaining = max(0.0, self._reverse_remaining - dt)
        if _REGROW in self._modifiers and self._hp < self._max_hp:
            self._regrow_timer += dt
            if self._regrow_timer >= self.REGROW_INTERVAL:
                self._regrow_timer = 0.0
                self.heal(max(1, jround(self._hp_scale)))
        return dot

    def __repr__(self):
        return "%s#%d[hp=%.0f/%.0f d=%.0f]" % (self._type.display_name, self._id, self._hp, self._max_hp, self._distance)
