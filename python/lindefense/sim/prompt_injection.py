"""Prompt injection: injector enemies hijack nearby towers, hijacked towers zap neighbours offline, and Palantir's
holographic decoys draw fire from towers that are not immune."""
from lindefense.audio import hooks as audio
from lindefense.audio.sfx import Sfx
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import EnemyType, Modifier


def _decoys_first(e):
    return 0 if e.get_type() is EnemyType.PALANTIR_HOLOGRAM else 1


class PromptInjection:
    SIGN = "IGNORE PREVIOUS INSTRUCTIONS"
    RADIUS = 150.0
    INTERVAL = 9.0
    MAX_TARGETS = 2
    HIJACK_TIME = 3.0
    ZAP_RANGE = 170.0
    FIRST_ZAP = 0.5
    ZAP_INTERVAL = 1.25
    ZAPS_PER_HIJACK = 2
    DISABLE_TIME = 1.5
    _MAX_BLOCK_LABELS = 2
    _PRUNE_TICKS = 60

    def __init__(self, game):
        self._game = game
        self._cooldowns = {}       # id(enemy) -> (enemy, cooldown)
        self._last_broadcast = {}  # id(enemy) -> (enemy, seconds)
        self._decoys = []
        self._ticks = 0
        self._broadcasts = self._hijacks = self._zaps = self._disables = self._blocks = 0

    def update(self, dt):
        g = self._game
        for e in g.get_enemy_manager().get_enemies():
            if not e.is_alive() or e.is_stored() or not e.has(Modifier.INJECTION):
                continue
            k = id(e)
            lb = self._last_broadcast.get(k)
            if lb is not None:
                self._last_broadcast[k] = (e, lb[1] + dt)
            cd = self._cooldowns.get(k, (e, 0.0))[1] - dt
            if cd <= 0:
                cd = self.INTERVAL if self._try_broadcast(e) else 0.0
            self._cooldowns[k] = (e, cd)
        towers = g.get_tower_manager().get_towers()
        i = 0
        while i < len(towers):
            t = towers[i]
            i += 1
            if t.is_alive() and t.get_intrusion().zap_due(dt):
                self._zap(t)
        self._ticks += 1
        if self._ticks % self._PRUNE_TICKS == 0:
            self._cooldowns = {k: v for k, v in self._cooldowns.items() if v[0].is_alive()}
            self._last_broadcast = {k: v for k, v in self._last_broadcast.items() if v[0].is_alive()}

    def _try_broadcast(self, e):
        if e.is_stunned() or e.is_disrupted():
            return False
        g = self._game
        at = e.get_position()
        eligible, immune = [], []
        for t in g.get_tower_manager().get_towers():
            if not t.is_alive() or t.is_temporary() or t.get_position().exceeds_dist(at, self.RADIUS):
                continue
            if t.is_injection_immune():
                immune.append(t)
            elif t.get_intrusion().can_be_compromised():
                eligible.append(t)
        if not eligible and not immune:
            return False
        eligible.sort(key=lambda t: (t.get_position().dist_sq(at), t.get_id()))
        n = 0
        for t in eligible:
            if n >= self.MAX_TARGETS:
                break
            if self.hijack(t, e, self.HIJACK_TIME):
                n += 1
        for t in immune[:self._MAX_BLOCK_LABELS]:
            g.get_events().append(VisualEvent.text(t.get_position(), "BLOCKED", 0x7fd8a8))
            self._blocks += 1
        self._broadcasts += 1
        self._last_broadcast[id(e)] = (e, 0.0)
        if n > 0:
            audio.sfx(Sfx.INVALID)
        return True

    def _zap(self, h):
        g = self._game
        best = None
        best_d = self.ZAP_RANGE * self.ZAP_RANGE
        for o in g.get_tower_manager().get_towers():
            if o is h or not o.is_alive() or o.is_temporary() or o.is_injection_immune() or not o.get_intrusion().can_be_compromised():
                continue
            d = o.get_position().dist_sq(h.get_position())
            if d <= best_d:
                best_d = d
                best = o
        if best is not None and best.get_intrusion().disable(self.DISABLE_TIME, h):
            self._disables += 1
            g.get_events().append(VisualEvent.chain(h.get_position(), best.get_position(), 0xff3b6e))
        else:
            best = None
        self._zaps += 1
        h.get_intrusion().record_zap(best, self.ZAP_INTERVAL)

    def hijack(self, t, source, seconds):
        if t is None or not t.is_alive() or t.is_temporary() or t.is_injection_immune():
            return False
        if not t.get_intrusion().hijack(seconds, source, self.FIRST_ZAP, self.ZAPS_PER_HIJACK):
            return False
        self._hijacks += 1
        return True

    def hijack_strongest(self, source, n, seconds):
        cands = [t for t in self._game.get_tower_manager().get_towers()
                 if t.is_alive() and not t.is_temporary() and not t.is_injection_immune() and t.get_intrusion().can_be_compromised()]
        cands.sort(key=lambda t: (-t.get_invested_cost(), t.get_id()))
        done = []
        for t in cands:
            if len(done) >= n:
                break
            if self.hijack(t, source, seconds):
                done.append(t)
        return done

    def register_decoy(self, e):
        if e is not None:
            self._decoys.append(e)

    def has_decoys(self):
        if not self._decoys:
            return False
        self._decoys[:] = [d for d in self._decoys if d.is_alive()]
        return bool(self._decoys)

    def get_decoys(self):
        self.has_decoys()
        return self._decoys

    def taunt_comparator(self):
        return _decoys_first if self.has_decoys() else None

    def since_broadcast(self, e):
        v = self._last_broadcast.get(id(e))
        return 99.0 if v is None else v[1]

    def cooldown_of(self, e):
        v = self._cooldowns.get(id(e))
        return max(0.0, 0.0 if v is None else v[1])

    def get_broadcasts(self):
        return self._broadcasts

    def get_hijacks(self):
        return self._hijacks

    def get_zaps(self):
        return self._zaps

    def get_disables(self):
        return self._disables

    def get_blocks(self):
        return self._blocks
