"""Travelling projectiles (homing, pierce, splash, bounce, clones) and the contexts passed through a hit/attack."""
import math

from lindefense.sim.vec import Vec

_MAX = 1.7976931348623157e308


class Shot:
    """Mutable description of a shot; every field has a default derived from the tower's stats."""

    def __init__(self):
        self.source = None
        self.stats = None
        self.hit = None
        self.start = None
        self.target = None
        self.damage_mult = 1.0
        self.extra_damage = 0.0
        self.pierce = 1
        self.bounces = 0
        self.bounce_range = 90.0
        self.bounce_speed_gain = 0.0
        self.clones = 0
        self.splash = 0.0
        self.speed = 400.0
        self.detection = False
        self.rgb = 0
        self.tag = None
        self.buffed = True
        self.on_impact = None   # callable(game, projectile, enemy) or None

    @staticmethod
    def of(game, t, start, target) -> "Shot":
        s = Shot()
        st = t.get_stats()
        s.damage_mult = t.damage_multiplier(game)
        s.source = t
        s.stats = st
        s.hit = st.hit
        s.start = start
        s.target = target
        s.pierce = t.effective_pierce()
        s.bounces = st.bounces
        s.bounce_range = st.bounce_range
        s.bounce_speed_gain = st.p("bounceSpeedGain", 0.0)
        s.clones = st.clones
        s.splash = st.splash_radius
        s.speed = st.projectile_speed * t.projectile_speed_mult()
        s.detection = t.can_see_camo()
        s.rgb = t.get_type().primary_rgb
        return s

    def copy(self) -> "Shot":
        s = Shot.__new__(Shot)
        s.__dict__.update(self.__dict__)
        return s


class Projectile:
    Shot = Shot

    def __init__(self, shot: Shot):
        self._shot = shot
        self._pos = shot.start
        self._target = shot.target
        self._speed = shot.speed
        self._pierce_left = max(1, shot.pierce)
        self._bounces_left = shot.bounces
        self._can_clone = shot.clones > 1
        self._hit_ids = set()
        self._travelled = 0.0
        self._max_travel = shot.stats.range * 1.4 + 80
        self._alive = True
        self._stalled = 0.0
        self._size = 8.0 if shot.splash > 0 else (7.0 if shot.hit.damage >= 5 else 5.0)
        self._bounced = 0
        self.handler_mark = 0
        d = self._target.get_position().sub(self._pos).normalized()
        if d.length() < 0.5:
            d = Vec(1, 0)
        self._vel = d.scale(self._speed)

    def get_position(self):
        return self._pos

    def get_velocity(self):
        return self._vel

    def is_alive(self):
        return self._alive

    def get_source(self):
        return self._shot.source

    def get_stats(self):
        return self._shot.stats

    def get_shot(self):
        return self._shot

    def get_hit(self):
        return self._shot.hit

    def get_damage_mult(self):
        return self._shot.damage_mult

    def get_rgb(self):
        return self._shot.rgb

    def get_size(self):
        return self._size

    def get_hit_ids(self):
        return self._hit_ids

    def get_target(self):
        return self._target

    def get_bounces_left(self):
        return self._bounces_left

    def can_clone(self):
        return self._can_clone

    def consume_clone(self):
        self._can_clone = False

    def has_detection(self):
        return self._shot.detection

    def kill(self):
        self._alive = False

    def retarget(self, e):
        self._target = e
        if e is not None:
            self._vel = e.get_position().sub(self._pos).normalized().scale(self._speed)

    def reset_travel(self):
        self._travelled = 0.0

    def restore_pierce(self, n):
        self._pierce_left = max(1, n)

    def aim_towards(self, at):
        self._target = None
        d = at.sub(self._pos).normalized()
        if d.length() < 0.5:
            d = Vec(1, 0)
        self._vel = d.scale(self._speed)
        self._travelled = 0.0

    def get_bounced(self):
        return self._bounced

    def get_pierce_left(self):
        return self._pierce_left

    def consume_bounce(self):
        self._bounces_left -= 1
        self._bounced += 1
        self._speed *= 1 + self._shot.bounce_speed_gain

    def consume_pierce(self) -> bool:
        self._pierce_left -= 1
        return self._pierce_left <= 0

    def move(self, dt) -> bool:
        if not self._alive:
            return False
        tgt = self._target
        speed = self._speed
        if tgt is not None and tgt.is_alive() and not tgt.is_stored():
            tp = tgt.get_position()
            pos = self._pos
            wx, wy = tp.x - pos.x, tp.y - pos.y
            d = math.sqrt(wx * wx + wy * wy)
            if d > 1:
                s = speed / d
                dx, dy = wx * s, wy * s
                k = min(1.0, dt * 10)
                vel = self._vel
                nx = vel.x + (dx - vel.x) * k
                ny = vel.y + (dy - vel.y) * k
                ln = math.sqrt(nx * nx + ny * ny)
                self._vel = Vec(0 * speed, 0 * speed) if ln < 1e-9 else Vec(nx / ln * speed, ny / ln * speed)
        elif tgt is not None and not tgt.is_alive():
            self._target = None
        sx, sy = self._vel.x * dt, self._vel.y * dt
        self._pos = Vec(self._pos.x + sx, self._pos.y + sy)
        step_len = math.sqrt(sx * sx + sy * sy)
        self._travelled += step_len
        if self._travelled > self._max_travel:
            self._alive = False
        if step_len < 1e-6:
            self._stalled += dt
            if self._stalled > 1.0:
                self._alive = False
        return self._alive


class HitContext:
    """Everything the damage formula needs about one hit; behaviours may adjust it in before_hit / on_hit."""

    __slots__ = ("target", "source", "_hit", "_hit_owned", "extra", "mult", "from_attack", "detection",
                 "projectile", "tag", "final_mult", "final_flat", "dealt", "immune")

    def __init__(self, target, hit, source):
        self.target = target
        self.source = source
        self._hit = hit
        self._hit_owned = False
        self.extra = 0.0
        self.mult = 1.0
        self.from_attack = False
        self.detection = source is None or source.can_see_camo()
        self.projectile = None
        self.tag = None
        self.final_mult = 1.0
        self.final_flat = 0.0
        self.dealt = 0.0
        self.immune = False

    def hit(self):
        return self._hit

    def edit_hit(self):
        if not self._hit_owned:
            self._hit = self._hit.copy()
            self._hit_owned = True
        return self._hit


class AttackContext:
    """The parameters of one tower attack, adjustable by TowerBehavior.modify_attack before firing."""

    def __init__(self, tower, stats, targets):
        self.tower = tower
        self.stats = stats
        self.targets = targets
        self.primary = targets[0] if targets else None
        self._hit = stats.hit
        self._hit_owned = False
        self.damage_mult = 1.0
        self.extra_damage = 0.0
        self.pierce = 0
        self.bounces = 0
        self.clones = 0
        self.splash = 0.0
        self.speed = 0.0
        self.shots_per_target = max(1, stats.projectiles_per_shot)
        self.cancel = False
        self.tag = None
        self.on_impact = None

    def hit(self):
        return self._hit

    def edit_hit(self):
        if not self._hit_owned:
            self._hit = self._hit.copy()
            self._hit_owned = True
        return self._hit
