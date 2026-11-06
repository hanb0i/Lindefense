"""Boss enemies, and Palantir's per-phase signature abilities (Panopticon, Prompt Broadcast, System Takeover)."""
import math

from lindefense.audio import hooks as audio
from lindefense.audio.sfx import Sfx
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType


def _wrap(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class PalantirProtocols:
    ABILITY_NAMES = ("Panopticon", "Prompt Broadcast", "System Takeover")
    # phase 1: Panopticon
    PANOPTICON_RANGE = 380.0
    PANOPTICON_PERIOD = 10.0
    PANOPTICON_HALF_WIDTH = math.radians(8)
    PANOPTICON_BLIND = 2.0
    PANOPTICON_DELAY = 3.0
    # phase 2: Prompt Broadcast
    BROADCAST_FIRST = 3.0
    BROADCAST_INTERVAL = 12.0
    BROADCAST_HIJACK = 3.0
    BROADCAST_TARGETS = 3
    BROADCAST_TOWERS_PER_EXTRA = 30
    BROADCAST_MAX_TARGETS = 6
    DECOYS = 2
    DECOY_HP_FRACTION = 0.02
    DECOY_SPACING = 90.0
    # phase 3: System Takeover
    KILL_SWITCH_WARNING = 0.42
    SEAL_DAMAGE_MULT = 0.3
    SEAL_REGEN_PER_SEC = 0.005
    SEAL_REGEN_CAP = 0.35
    REGRAB_INTERVAL = 30.0

    def __init__(self):
        self._clock = 0.0
        self._beam_angle = -math.pi / 2
        self._blinds = 0
        self._broadcast_timer = -1.0
        self._broadcasts = 0
        self._broadcast_hijacks = 0
        self._last_broadcast_age = 99.0
        self._last_broadcast_targets = []
        self._decoys = []
        self._kill_switch_warned = False
        self._kill_switch_used = False
        self._kill_switch_resets = 0
        self._kill_switch_age = 99.0
        self._regrab_timer = 0.0
        self._sealed = False
        self._sealed_time = 0.0
        self._healed_while_sealed = 0.0

    # ---- hooks from Boss
    def on_phase(self, game, b, phase: int) -> None:
        if phase == 1:
            self._broadcast_timer = self.BROADCAST_FIRST
            self._spawn_decoys(game, b)
        elif phase == 2:
            self._kill_switch(game, b)
            game.get_window_link().request_grab(b)
            self._regrab_timer = self.REGRAB_INTERVAL

    def update(self, game, b, dt: float) -> None:
        self._clock += dt
        self._last_broadcast_age += dt
        self._kill_switch_age += dt
        ph = b.get_phase()
        if ph == 0:
            self._panopticon(game, b, dt)
        elif ph == 1:
            self._prompt_broadcast(game, b, dt)
        else:
            self._system_takeover(game, b, dt)

    # ---- phase 1
    def _panopticon(self, game, b, dt):
        if self._clock < self.PANOPTICON_DELAY:
            return
        self._beam_angle = _wrap(self._beam_angle + 2 * math.pi / self.PANOPTICON_PERIOD * dt)
        o = b.get_position()
        for t in list(game.get_tower_manager().get_towers()):
            if not t.is_alive() or t.is_temporary() or t.is_surveillance_immune():
                continue
            if not t.get_intrusion().can_be_compromised() or not self.in_beam(o, self._beam_angle, t):
                continue
            if t.get_intrusion().blind(self.PANOPTICON_BLIND):
                self._blinds += 1

    @staticmethod
    def in_beam(origin, angle: float, t) -> bool:
        dx = t.get_position().x - origin.x
        dy = t.get_position().y - origin.y
        d = math.sqrt(dx * dx + dy * dy)
        if d > PalantirProtocols.PANOPTICON_RANGE + t.get_radius():
            return False
        if d < 1:
            return True
        diff = abs(_wrap(math.atan2(dy, dx) - angle))
        return diff <= PalantirProtocols.PANOPTICON_HALF_WIDTH + math.atan2(t.get_radius(), d)

    # ---- phase 2
    def _prompt_broadcast(self, game, b, dt):
        if not self._kill_switch_warned and b.get_hp_fraction() < self.KILL_SWITCH_WARNING:
            self._kill_switch_warned = True
            game.set_banner("KILL SWITCH ARMING: fire your abilities before Palantir drops to 35%", 0xffb020, 3.5)
        if self._broadcast_timer < 0:
            self._broadcast_timer = self.BROADCAST_FIRST
        self._broadcast_timer -= dt
        if self._broadcast_timer > 0:
            return
        self._broadcast_timer = self.BROADCAST_INTERVAL
        self.broadcast(game, b)

    def broadcast(self, game, b):
        from lindefense.sim.prompt_injection import PromptInjection
        n = self.broadcast_targets(game)
        hit = game.get_injection().hijack_strongest(b, n, self.BROADCAST_HIJACK)
        self._broadcasts += 1
        self._broadcast_hijacks += len(hit)
        self._last_broadcast_targets = hit
        self._last_broadcast_age = 0.0
        audio.sfx(Sfx.PALANTIR_WARNING)
        if not hit:
            game.set_banner("PROMPT BROADCAST blocked: your towers ignore it", 0x7fd8a8, 2.5)
        else:
            game.set_banner("PROMPT BROADCAST: \"" + PromptInjection.SIGN + "\"  -  " + str(len(hit)) + " tower(s) hijacked", 0xff4d4d, 3)
        return hit

    @staticmethod
    def broadcast_targets(game) -> int:
        towers = len(game.get_tower_manager().get_player_towers())
        P = PalantirProtocols
        return min(P.BROADCAST_MAX_TARGETS, P.BROADCAST_TARGETS + towers // P.BROADCAST_TOWERS_PER_EXTRA)

    def _spawn_decoys(self, game, b):
        hp = b.get_max_hp() * self.DECOY_HP_FRACTION
        hp_scale = hp / EnemyType.PALANTIR_HOLOGRAM.base_hp
        ln = b.get_route().get_total_length()
        for i in range(self.DECOYS):
            d = b.get_distance() + (self.DECOY_SPACING if i % 2 == 0 else -self.DECOY_SPACING) * (1 + i // 2)
            d = max(0.0, min(ln - 1, d))
            e = game.get_enemy_manager().spawn_scaled(EnemyType.PALANTIR_HOLOGRAM, None, b.get_route_index(), d, hp_scale, b.get_speed_scale())
            self._decoys.append(e)
            game.get_injection().register_decoy(e)
            game.get_events().append(VisualEvent.teleport(e.get_position()))
        game.get_events().append(VisualEvent.phase(b.get_position(), "HOLOGRAMS", 0x8ad8ff))

    # ---- phase 3
    def _kill_switch(self, game, b):
        if self._kill_switch_used:
            return
        self._kill_switch_used = True
        n = 0
        for t in game.get_tower_manager().get_towers():
            if not t.is_alive() or t.is_temporary() or t.get_ability() is None or t.is_injection_immune():
                continue
            t.start_ability_cooldown()
            n += 1
            game.get_events().append(VisualEvent.text(t.get_position(), "KILL SWITCH", 0xffb020))
        self._kill_switch_resets = n
        self._kill_switch_age = 0.0
        game.set_banner("SYSTEM TAKEOVER: kill switch reset " + str(n) + " abilit" + ("y" if n == 1 else "ies")
                        + "  -  Palantir reaches for your window", 0xff4d4d, 4)

    def _system_takeover(self, game, b, dt):
        link = game.get_window_link()
        self._regrab_timer -= dt
        if self._regrab_timer <= 0:
            self._regrab_timer = self.REGRAB_INTERVAL
            link.request_grab(b)
        now = link.is_sealing()
        if now != self._sealed:
            self._sealed = now
            if now:
                game.set_banner("PALANTIR IS SEALED: it regenerates and shrugs off damage  -  drag your window back", 0xff4d4d, 4)
            else:
                game.set_banner("SEAL BROKEN: window restored", 0x7fd8a8, 2.5)
        if not self._sealed:
            return
        self._sealed_time += dt
        cap = self.SEAL_REGEN_CAP * b.get_max_hp()
        if b.get_hp() < cap:
            heal = min(self.SEAL_REGEN_PER_SEC * b.get_max_hp() * dt, cap - b.get_hp())
            b.heal(heal)
            self._healed_while_sealed += heal

    # ---- state
    def is_sealed(self):
        return self._sealed

    def get_sealed_time(self):
        return self._sealed_time

    def get_healed_while_sealed(self):
        return self._healed_while_sealed

    def get_beam_angle(self):
        return self._beam_angle

    def is_beam_active(self, b):
        return b.get_phase() == 0 and self._clock >= self.PANOPTICON_DELAY

    def get_blinds(self):
        return self._blinds

    def get_broadcasts(self):
        return self._broadcasts

    def get_broadcast_hijacks(self):
        return self._broadcast_hijacks

    def get_last_broadcast_age(self):
        return self._last_broadcast_age

    def get_last_broadcast_targets(self):
        return self._last_broadcast_targets

    def get_broadcast_timer(self):
        return max(0.0, self._broadcast_timer)

    def get_decoys(self):
        return self._decoys

    def is_kill_switch_used(self):
        return self._kill_switch_used

    def get_kill_switch_resets(self):
        return self._kill_switch_resets

    def get_kill_switch_age(self):
        return self._kill_switch_age


class Boss(Enemy):
    TELEGRAPH_TIME = 3.0
    SURVEIL_DURATION = 8.0
    SURVEILLANCE_INTERVAL = (30.0, 20.0, 14.0)
    SURVEILLANCE_TARGETS = (2, 3, 4)
    PALANTIR_ARMOR = (0.60, 0.35, 0.10)
    PALANTIR_SPEED = (1.0, 1.3, 1.7)
    PALANTIR_PHASE_NAMES = ("Surveillance Shell", "Predictive Core", "Exposed Core")

    def __init__(self, type_, modifiers, route, route_index, distance, hp_scale, speed_scale):
        # protocols must exist before Enemy.__init__ (take_damage/is_control_immune may consult it)
        self._phase = 0
        self._shield_off_remaining = 0.0
        self._protocols = PalantirProtocols() if type_ is EnemyType.PALANTIR else None
        super().__init__(type_, modifiers, route, route_index, distance, hp_scale, speed_scale)
        self._surveillance_timer = self.SURVEILLANCE_INTERVAL[0]
        self._telegraph_remaining = 0.0
        self._marked_towers = []
        self._entrance_announced = False
        self._pending_phase_event = -1

    def get_protocols(self):
        return self._protocols

    def is_sealed(self):
        return self._protocols is not None and self._protocols.is_sealed()

    def take_damage(self, amount, now):
        return super().take_damage(amount * PalantirProtocols.SEAL_DAMAGE_MULT if self.is_sealed() else amount, now)

    def is_palantir(self):
        return self._type is EnemyType.PALANTIR

    def get_phase(self):
        return self._phase

    def get_phase_count(self):
        return 3 if self.is_palantir() else 1

    def get_phase_name(self):
        return self.PALANTIR_PHASE_NAMES[self._phase] if self.is_palantir() else self._type.get_boss_class().label

    def is_telegraphing(self):
        return self._telegraph_remaining > 0

    def get_telegraph_remaining(self):
        return self._telegraph_remaining

    def get_surveillance_timer(self):
        return self._surveillance_timer

    def get_marked_towers(self):
        return self._marked_towers

    def is_control_immune(self):
        return self.is_palantir() and self._phase == 0 and self._shield_off_remaining <= 0

    def disable_phase_shield(self, seconds):
        if self.is_palantir():
            self._shield_off_remaining = max(self._shield_off_remaining, seconds)

    def is_phase_shield_down(self):
        return self._shield_off_remaining > 0

    def get_phase_shield_off_remaining(self):
        return self._shield_off_remaining

    def base_armor(self):
        if not self.is_palantir():
            return super().base_armor()
        return 0.0 if self._shield_off_remaining > 0 else self.PALANTIR_ARMOR[self._phase]

    def own_speed_multiplier(self):
        return super().own_speed_multiplier() * (self.PALANTIR_SPEED[self._phase] if self.is_palantir() else 1.0)

    def update_phase(self) -> int:
        if not self.is_palantir():
            return -1
        f = self.get_hp_fraction()
        np_ = 0 if f > 0.70 else (1 if f > 0.35 else 2)
        if np_ > self._phase:
            self._phase = np_
            self._surveillance_timer = min(self._surveillance_timer, self.SURVEILLANCE_INTERVAL[self._phase] * 0.5)
            return self._phase
        return -1

    def update_boss(self, game, dt: float) -> None:
        if not self.is_alive() or self.get_hp() <= 0:
            return
        if self._shield_off_remaining > 0:
            self._shield_off_remaining = max(0.0, self._shield_off_remaining - dt)
        if not self._entrance_announced:
            self._entrance_announced = True
            game.announce_boss(self)
        new_phase = self.update_phase()
        if new_phase >= 0:
            self._pending_phase_event = new_phase
            game.on_palantir_phase(self, new_phase)
            if self._protocols is not None:
                self._protocols.on_phase(game, self, new_phase)
        if not self.is_palantir():
            return
        self._protocols.update(game, self, dt)
        if self._telegraph_remaining > 0:
            self._telegraph_remaining -= dt
            if self._telegraph_remaining <= 0:
                applied = 0
                for t in self._marked_towers:
                    if t.is_alive() and not t.is_surveillance_immune():
                        t.set_surveilled(self.SURVEIL_DURATION)
                        applied += 1
                game.on_surveillance_applied(self, applied, len(self._marked_towers))
                self._marked_towers.clear()
            return
        self._surveillance_timer -= dt
        if self._surveillance_timer <= 0:
            self._surveillance_timer = self.SURVEILLANCE_INTERVAL[self._phase]
            self.begin_surveillance(game)

    def begin_surveillance(self, game) -> None:
        self._marked_towers.clear()
        candidates = [t for t in game.get_tower_manager().get_towers() if not t.is_temporary()]
        candidates.sort(key=lambda t: -t.get_invested_cost())
        scaled = int(math.ceil(len(candidates) * (0.10 + 0.05 * self._phase)))
        n = min(max(self.SURVEILLANCE_TARGETS[self._phase], scaled), len(candidates))
        self._marked_towers.extend(candidates[:n])
        self._telegraph_remaining = self.TELEGRAPH_TIME
        game.on_surveillance_telegraph(self, self._marked_towers)

    def consume_phase_event(self) -> int:
        p = self._pending_phase_event
        self._pending_phase_event = -1
        return p
