"""Boss enemies, and Palantir's per-phase signature abilities (Panopticon, Prompt Broadcast, System Takeover, Swarm
Uplink). The corporate bosses' own abilities live in boss_abilities.py."""
import math

from lindefense.audio import hooks as audio
from lindefense.audio.sfx import Sfx
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy import boss_abilities
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.javacompat import jatan2
from lindefense.jenum import EnumSet


def _wrap(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class PalantirProtocols:
    ABILITY_NAMES = ("Panopticon", "Prompt Broadcast", "System Takeover")
    # Panopticon: one beam in phase 1, twin opposed beams sweeping faster in phase 3 (none in phase 2)
    PANOPTICON_RANGE = 380.0
    PANOPTICON_PERIODS = (10.0, 0.0, 8.0)   # seconds per turn by phase (0 = no beam)
    PANOPTICON_BEAMS = (1, 0, 2)
    PANOPTICON_PERIOD = PANOPTICON_PERIODS[0]
    PANOPTICON_HALF_WIDTH = math.radians(8)
    PANOPTICON_BLIND = 2.0
    PANOPTICON_DELAY = 3.0
    # phase 2: Prompt Broadcast
    BROADCAST_FIRST = 3.0
    BROADCAST_INTERVAL = 10.0
    BROADCAST_HIJACK = 4.0
    BROADCAST_TARGETS = 4
    BROADCAST_TOWERS_PER_EXTRA = 25
    BROADCAST_MAX_TARGETS = 8
    DECOYS = 3
    DECOY_HP_FRACTION = 0.04
    DECOY_SPACING = 90.0
    # phase 3: System Takeover
    KILL_SWITCH_WARNING = 0.42
    SEAL_DAMAGE_MULT = 0.3
    SEAL_REGEN_PER_SEC = 0.005
    SEAL_REGEN_CAP = 0.35
    REGRAB_INTERVAL = 30.0
    # escort squadron launched from the entrance of Palantir's route when a phase begins (phase index -> (type, count,
    # modifier code)); they fly the whole route to catch up with it. The Swarm Uplink: every escort boss within
    # UPLINK_RANGE of Palantir cuts the damage Palantir takes by UPLINK_PER, up to UPLINK_MAX
    ESCORTS = {1: ((EnemyType.BELLARMINE_COLLEGE_PREP, 3, "F"),),
               2: ((EnemyType.LOCKHEED_MARTIN, 1, ""), (EnemyType.SW_RESOURCE_CONSULTANT, 1, "F"))}
    ESCORT_SPACING = 45.0
    UPLINK_RANGE = 260.0
    UPLINK_PER = 0.12
    UPLINK_MAX = 0.36

    def __init__(self):
        self._clock = 0.0
        self._beam_angle = -math.pi / 2
        self._beam_clock = 0.0
        self._blinds = 0
        self._escorts = []
        self._uplinks = []
        self._scratch = []
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
            self._beam_clock = 0.0
        self._launch_escorts(game, b, phase)

    def update(self, game, b, dt: float) -> None:
        self._clock += dt
        self._beam_clock += dt
        self._last_broadcast_age += dt
        self._kill_switch_age += dt
        ph = b.get_phase()
        if ph == 0:
            self._panopticon(game, b, dt)
        elif ph == 1:
            self._prompt_broadcast(game, b, dt)
        else:
            self._system_takeover(game, b, dt)
            self._panopticon(game, b, dt)
        self._update_uplinks(game, b)

    # ---- Panopticon (phases 1 and 3)
    def beam_angles(self, b):
        """The angles of the beams sweeping right now (empty when none is)."""
        if not self.is_beam_active(b):
            return ()
        n = self.PANOPTICON_BEAMS[b.get_phase()]
        return tuple(_wrap(self._beam_angle + 2 * math.pi * k / n) for k in range(n))

    def _panopticon(self, game, b, dt):
        if not self.is_beam_active(b):
            return
        self._beam_angle = _wrap(self._beam_angle + 2 * math.pi / self.PANOPTICON_PERIODS[b.get_phase()] * dt)
        angles = self.beam_angles(b)
        o = b.get_position()
        for t in list(game.get_tower_manager().get_towers()):
            if not t.is_alive() or t.is_temporary() or t.is_surveillance_immune():
                continue
            if not t.get_intrusion().can_be_compromised() or not any(self.in_beam(o, a, t) for a in angles):
                continue
            if t.get_intrusion().blind(self.PANOPTICON_BLIND):
                self._blinds += 1

    # ---- escorts and the Swarm Uplink (phases 2 and 3)
    def _launch_escorts(self, game, b, phase):
        groups = self.ESCORTS.get(phase)
        if not groups or game.is_reverse():   # in Adversarial Training the player sends (and pays for) the escorts
            return
        em = game.get_enemy_manager()
        k = 0
        n = 0
        for type_, count, code in groups:
            for _ in range(count):
                k += 1
                mods = EnumSet()
                if "F" in code:
                    mods.add(Modifier.FORTIFIED)
                e = em.spawn(type_, mods, b.get_route_index(), self.ESCORT_SPACING * (k - 1))
                e._entrance_announced = True   # the phase banner speaks for the whole squadron
                self._escorts.append(e)
                game.get_events().append(VisualEvent.teleport(e.get_position()))
                n += 1
        game.get_events().append(VisualEvent.phase(b.get_route().position_at(0), "ESCORTS x" + str(n), 0xff9a5a))
        game.emit_text(b.get_position(), "ESCORTS INBOUND", 0xff9a5a)

    def _update_uplinks(self, game, b):
        up = self._uplinks
        up.clear()
        if b.get_phase() == 0:
            return
        p = b.get_position()
        r2 = self.UPLINK_RANGE * self.UPLINK_RANGE
        for e in game.get_enemy_manager().get_grid().near(p.x, p.y, self.UPLINK_RANGE, self._scratch):
            if e is b or not e._alive or e._stored or not e._is_boss or e.get_type() is EnemyType.PALANTIR:
                continue
            q = e._cached_pos
            dx = q.x - p.x
            dy = q.y - p.y
            if dx * dx + dy * dy <= r2:
                up.append(e)

    def get_uplinks(self):
        return self._uplinks

    def uplink_reduction(self):
        return min(self.UPLINK_MAX, self.UPLINK_PER * len(self._uplinks))

    def get_escorts(self):
        return self._escorts

    @staticmethod
    def escort_text(phase):
        """'3 Fortified Bellarmine College Preps' style list of the squadron a phase launches."""
        parts = []
        for type_, count, code in PalantirProtocols.ESCORTS.get(phase, ()):
            name = type_.display_name + ("s" if count > 1 else "")
            parts.append(str(count) + " " + ("Fortified " if "F" in code else "") + name)
        return " and ".join(parts)

    @staticmethod
    def describe():
        """The catalog / help text for Palantir's kit, built from the live numbers."""
        P, B = PalantirProtocols, Boss
        n = boss_abilities._n
        pct = boss_abilities._pct
        return ("Wave 100 final boss. Armour " + " / ".join(pct(a) for a in B.PALANTIR_ARMOR) + " across three phases (faster "
                "each phase); immune to slows, stuns and knockback in phases 1 and 2. Its HP grows with Difficulty Growth. "
                "Predictive Surveillance (first after " + n(B.SURVEILLANCE_FIRST) + " s, then every " + " / ".join(n(x) for x in B.SURVEILLANCE_INTERVAL)
                + " s by phase) marks your highest-investment towers for " + n(B.TELEGRAPH_TIME) + " s, then disrupts them for "
                + n(B.SURVEIL_DURATION) + " s (-50% speed, -30% range, abilities locked); towers near Perplexity U2 are immune. "
                "Phase 1 PANOPTICON: a rotating beam blinds the towers it sweeps (Perplexity U2 blocks it). "
                "Phase 2 PROMPT BROADCAST: every " + n(P.BROADCAST_INTERVAL) + " s it hijacks your priciest towers and keeps "
                + str(P.DECOYS) + " decoy holograms (" + pct(P.DECOY_HP_FRACTION) + " of its HP each) in the air. "
                "Phase 3 SYSTEM TAKEOVER: twin Panopticon beams, a kill switch that resets your ability cooldowns once, and a "
                "window grab: while the window stays shrunk Palantir is sealed (regenerates, takes 30% damage) until you drag it back. "
                "Each new phase launches an escort squadron from the entrance (" + P.escort_text(1) + ", then " + P.escort_text(2) + "); every escort "
                "boss within " + n(P.UPLINK_RANGE) + " px feeds the SWARM UPLINK, cutting Palantir's damage taken by "
                + pct(P.UPLINK_PER) + " each (up to " + pct(P.UPLINK_MAX) + "). Kill the escorts.")

    @staticmethod
    def in_beam(origin, angle: float, t) -> bool:
        dx = t.get_position().x - origin.x
        dy = t.get_position().y - origin.y
        d = math.sqrt(dx * dx + dy * dy)
        if d > PalantirProtocols.PANOPTICON_RANGE + t.get_radius():
            return False
        if d < 1:
            return True
        diff = abs(_wrap(jatan2(dy, dx) - angle))   # Java's (fdlibm) atan2, not the platform libm's
        return diff <= PalantirProtocols.PANOPTICON_HALF_WIDTH + jatan2(t.get_radius(), d)

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
        self._spawn_decoys(game, b)
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
        """Projects holograms up to DECOYS live ones (all of them on entering phase 2, then each broadcast restores
        the ones that were destroyed)."""
        self._decoys[:] = [d for d in self._decoys if d.is_alive()]
        if len(self._decoys) >= self.DECOYS:
            return
        hp = b.get_max_hp() * self.DECOY_HP_FRACTION
        hp_scale = hp / EnemyType.PALANTIR_HOLOGRAM.base_hp
        ln = b.get_route().get_total_length()
        for i in range(len(self._decoys), self.DECOYS):
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
        ph = b.get_phase()
        return self.PANOPTICON_BEAMS[ph] > 0 and (self._clock >= self.PANOPTICON_DELAY if ph == 0 else self._beam_clock >= self.PANOPTICON_DELAY)

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
    SURVEILLANCE_FIRST = 20.0
    SURVEILLANCE_INTERVAL = (24.0, 16.0, 11.0)
    SURVEILLANCE_TARGETS = (3, 4, 5)
    SURVEILLANCE_SHARE = (0.15, 0.20, 0.25)   # of all towers, when that is more than SURVEILLANCE_TARGETS
    PALANTIR_ARMOR = (0.60, 0.35, 0.10)
    PALANTIR_SPEED = (1.0, 1.3, 1.7)
    CONTROL_IMMUNE_PHASES = 2   # immune to slow / stun / hold / knockback in phases 1 and 2
    PALANTIR_PHASE_NAMES = ("Surveillance Shell", "Predictive Core", "Exposed Core")

    def __init__(self, type_, modifiers, route, route_index, distance, hp_scale, speed_scale):
        # protocols must exist before Enemy.__init__ (take_damage/is_control_immune may consult it)
        self._phase = 0
        self._shield_off_remaining = 0.0
        self._protocols = PalantirProtocols() if type_ is EnemyType.PALANTIR else None
        self._ability = boss_abilities.create(type_)
        super().__init__(type_, modifiers, route, route_index, distance, hp_scale, speed_scale)
        self._surveillance_timer = self.SURVEILLANCE_FIRST
        self._telegraph_remaining = 0.0
        self._marked_towers = []
        self._entrance_announced = False
        self._pending_phase_event = -1

    def get_protocols(self):
        return self._protocols

    def get_ability(self):
        """The corporate boss's signature ability (boss_abilities), None for Palantir."""
        return self._ability

    def get_ability_status(self):
        if self._ability is not None:
            return self._ability.status_text(self)
        pr = self._protocols
        if pr is not None and pr.get_uplinks():
            return "SWARM UPLINK -" + str(int(round(100 * pr.uplink_reduction()))) + "%"
        return ""

    def is_sealed(self):
        return self._protocols is not None and self._protocols.is_sealed()

    def take_damage(self, amount, now):
        pr = self._protocols
        if pr is not None:
            if pr.is_sealed():
                amount *= PalantirProtocols.SEAL_DAMAGE_MULT
            if pr._uplinks:
                amount *= 1 - pr.uplink_reduction()
        ab = self._ability
        if ab is not None and amount > 0 and self._alive:
            return ab.take_damage(self, amount, now)
        return super().take_damage(amount, now)

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
        return self.is_palantir() and self._phase < self.CONTROL_IMMUNE_PHASES and self._shield_off_remaining <= 0

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
        if self._ability is not None:
            return super().own_speed_multiplier() * self._ability.speed_multiplier()
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
            if self._ability is not None:
                self._ability.update(game, self, dt)
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
        scaled = int(math.ceil(len(candidates) * self.SURVEILLANCE_SHARE[self._phase]))
        n = min(max(self.SURVEILLANCE_TARGETS[self._phase], scaled), len(candidates))
        self._marked_towers.extend(candidates[:n])
        self._telegraph_remaining = self.TELEGRAPH_TIME
        game.on_surveillance_telegraph(self, self._marked_towers)

    def consume_phase_event(self) -> int:
        p = self._pending_phase_event
        self._pending_phase_event = -1
        return p
