"""Reusable simulation primitives spawned by tower behaviours: track zones, walkers, drones, node hazards, mines,
barrages and delayed tasks. Everything expires on its own or when its owner tower is sold."""
import math
import sys

from lindefense.combat import clusters
from lindefense.combat.projectile import AttackContext, HitContext
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import StatusKind
from lindefense.map.path import Path
from lindefense.sim.vec import Vec
from lindefense.tower.stats import TowerStats
from lindefense.tower.tower_type import AttackKind, Targeting

_MAX = sys.float_info.max


# ====================================================================== Mine
class Mine:
    """A one-shot proximity device (Cami-Mine mine, Trapper Che trap)."""

    def __init__(self, owner, position, hit):
        self.owner = owner
        self.position = position
        self.trigger_radius = 14.0
        self.blast_radius = 32.0
        self.hit = hit
        self.arm_time = 0.35
        self.hold_duration = 0.0
        self.tether_dps = 0.0
        self.secondary_chance = 0.0
        self.secondary_hit = None
        self.secondary_delay = 0.3
        self.secondary_radius = 32.0
        self.detection = owner is None or owner.can_see_camo()
        self.rgb = 0xff8a3b
        self.kind = "mine"
        self._age = 0.0
        self._dead = False
        self._triggered = False

    def is_alive(self):
        return not self._dead

    def kill(self):
        self._dead = True

    def is_armed(self):
        return self._age >= self.arm_time

    def has_triggered(self):
        return self._triggered

    def get_arm_fraction(self):
        return 1.0 if self.arm_time <= 0 else min(1.0, self._age / self.arm_time)

    def update(self, game, dt):
        if self._dead:
            return
        if self.owner is not None and not self.owner.is_alive():
            self._dead = True
            return
        self._age += dt
        if self._age < self.arm_time:
            return
        trigger = None
        p = self.position
        for e in game.get_enemy_manager().get_grid().near(p.x, p.y, self.trigger_radius, []):
            if not e.is_alive() or e.is_stored():
                continue
            if not self.detection and e.is_camo() and not e.is_revealed():
                continue
            if e.get_position().dist(p) <= self.trigger_radius + e.get_radius() * 0.5:
                trigger = e
                break
        if trigger is None:
            return
        self.detonate(game)

    def detonate(self, game):
        if self._triggered:
            return
        self._triggered = True
        self._dead = True
        combat = game.get_combat()
        hits = combat.area_hits(self.position, self.blast_radius, self.hit, self.owner, game.get_global_damage_multiplier(),
                                0.0, None, None, self.detection, False, None)
        if self.hold_duration > 0 or self.tether_dps > 0:
            held = set()
            for h in hits:
                e = h.target
                if e is None or not e.is_alive() or e.get_id() in held:
                    continue
                held.add(e.get_id())
                if self.hold_duration > 0 and not e.is_boss():
                    e.apply_status(StatusKind.STUN, 1, self.hold_duration)
                if self.tether_dps > 0:
                    e.apply_burn(self.tether_dps, self.hold_duration if self.hold_duration > 0 else 1.0, self.owner)
        if self.secondary_hit is not None and self.secondary_chance > 0 and game.get_rng().chance(self.secondary_chance):
            at, sec, rad, owner = self.position, self.secondary_hit, self.secondary_radius, self.owner
            game.get_effects().schedule(self.secondary_delay, lambda: game.get_combat().area_hit(
                at, rad, sec, owner, game.get_global_damage_multiplier(), 9999, None))
        combat.emit(VisualEvent.explosion(self.position, self.blast_radius, self.rgb))


# ====================================================================== TrackZone
class TrackZone:
    """A circular area acting on every enemy inside it (tick damage, slow / speed cap, armour crack)."""
    REFRESH = 0.25

    def __init__(self, center, radius, owner):
        self.center = center
        self.radius = float(radius)
        self.owner = owner
        self.duration = 1.0
        self.permanent = False
        self.bind_to_owner = True
        self.tick_interval = 0.0
        self.tick_hit = None
        self.slow = 0.0
        self.speed_cap = 0.0
        self.armor_crack = False
        self.crack_bosses = False
        self.affects_bosses = True
        self.bosses_only = False
        self.detection = True
        self.rgb = 0xffffff
        self.kind = "zone"
        self._tick_timer = 0.0
        self._dead = False

    def contains(self, e):
        return e.get_position().within_dist(self.center, self.radius)

    def is_alive(self):
        return not self._dead

    def kill(self):
        self._dead = True

    def get_remaining(self):
        return self.duration

    def update(self, game, dt):
        if self._dead:
            return
        if self.bind_to_owner and self.owner is not None and not self.owner.is_alive():
            self._dead = True
            return
        if not self.permanent:
            self.duration -= dt
            if self.duration <= 0:
                self._dead = True
                return
        tick = False
        if self.tick_interval > 0 and self.tick_hit is not None:
            self._tick_timer += dt
            if self._tick_timer >= self.tick_interval:
                self._tick_timer -= self.tick_interval
                tick = True
        eff_slow = max(self.slow, 1 - self.speed_cap if self.speed_cap > 0 else 0.0)
        combat = game.get_combat()
        scan = game.get_enemy_manager().get_grid().scan(self.center.x, self.center.y, self.radius)
        e = scan.next()
        while e is not None:
            if e.is_alive() and not e.is_stored() and self.contains(e) \
                    and not (e.is_boss() and not self.affects_bosses) and not (self.bosses_only and not e.is_boss()):
                if eff_slow > 0:
                    e.apply_status(StatusKind.SLOW, eff_slow, self.REFRESH)
                if self.armor_crack and (not e.is_boss() or self.crack_bosses):
                    e.apply_status(StatusKind.ARMOR_CRACK, 1, self.REFRESH)
                if tick:
                    h = HitContext(e, self.tick_hit, self.owner)
                    h.detection = self.detection
                    h.mult = game.get_global_damage_multiplier()
                    combat.apply_hit(h)
            e = scan.next()


# ====================================================================== TrackWalker
class TrackWalker:
    """A summon walking along a route between two distances, dealing contact damage."""

    def __init__(self, route, start_distance, end_distance, speed, owner, hit):
        self.route = route
        self.distance = float(start_distance)
        self.end_distance = float(end_distance)
        self.speed = float(speed)
        self.owner = owner
        self.hit = hit
        self.boss_hit = None
        self.radius = 14.0
        self.pierce = 1
        self.per_enemy_cooldown = 0.0
        self.lifetime = 0.0
        self.detection = False
        self.respect_camo = False
        self.damage_mult = 1.0
        self.rgb = 0xffffff
        self.kind = "walker"
        self._hit_once = set()
        self._last_hit = {}
        self._dead = False
        self._age = 0.0

    def get_position(self):
        return self.route.position_at(self.distance)

    def is_forward(self):
        return self.end_distance >= self.distance

    def is_alive(self):
        return not self._dead

    def get_distinct_hits(self):
        return len(self._hit_once)

    def kill(self):
        self._dead = True

    def update(self, game, dt):
        if self._dead:
            return
        self._age += dt
        if self.lifetime > 0 and self._age >= self.lifetime:
            self._dead = True
            return
        direction = 1 if self.end_distance >= self.distance else -1
        self.distance += direction * self.speed * dt
        finished = self.distance >= self.end_distance if direction > 0 else self.distance <= self.end_distance
        if finished:
            self.distance = self.end_distance
        pos = self.get_position()
        combat = game.get_combat()
        scan = game.get_enemy_manager().get_grid().scan(pos.x, pos.y, self.radius)
        e = scan.next()
        while e is not None and not self._dead:
            if e.is_alive() and not e.is_stored() and not (self.respect_camo and not self.detection and e.is_camo() and not e.is_revealed()):
                rr = self.radius + e.get_radius()
                if e.get_position().dist_sq(pos) <= rr * rr:
                    eid = e.get_id()
                    first = eid not in self._hit_once
                    skip = False
                    if not first:
                        if self.per_enemy_cooldown <= 0:
                            skip = True
                        else:
                            last = self._last_hit.get(eid)
                            if last is not None and game.get_time() - last < self.per_enemy_cooldown:
                                skip = True
                    elif len(self._hit_once) >= self.pierce:
                        skip = True
                    if not skip:
                        self._hit_once.add(eid)
                        self._last_hit[eid] = game.get_time()
                        h = HitContext(e, self.boss_hit if (e.is_boss() and self.boss_hit is not None) else self.hit, self.owner)
                        h.mult = self.damage_mult * game.get_global_damage_multiplier()
                        h.detection = self.detection
                        combat.apply_hit(h)
                        if len(self._hit_once) >= self.pierce and self.per_enemy_cooldown <= 0:
                            self._dead = True
            e = scan.next()
        if finished:
            self._dead = True


# ====================================================================== Drone
class Drone:
    """An orbiting, patrolling or stationary shooter with its own stats, credited to its owner tower."""
    ORBIT, PATROL, STATIC = "ORBIT", "PATROL", "STATIC"

    def __init__(self, owner, mode, stats, pos):
        self.owner = owner
        self.mode = mode
        self.stats = stats
        self.mirror_owner = False
        self.detection = False
        self.targeting = Targeting.FIRST
        self.lifetime = 0.0
        self.rgb = 0xffffff
        self.kind = "drone"
        self.range_from_owner = False
        self.inherit_owner_rate = False
        self.sticky_target = False
        self._current = None
        self.orbit_radius = 40.0
        self.orbit_speed = 2.0
        self._angle = 0.0
        self._route = None
        self._from = self._to = self._patrol_speed = self._patrol_pos = 0.0
        self._patrol_dir = 1
        self._pos = pos
        self._cooldown = 0.0
        self._age = 0.0
        self._dead = False

    @staticmethod
    def orbit(owner, stats, radius, start_angle):
        d = Drone(owner, Drone.ORBIT, stats, owner.get_position())
        d.orbit_radius = float(radius)
        d._angle = start_angle
        d._pos = owner.get_position().add(Vec(math.cos(start_angle) * radius, math.sin(start_angle) * radius))
        return d

    @staticmethod
    def patrol(owner, stats, route, frm, to, speed):
        d = Drone(owner, Drone.PATROL, stats, route.position_at(frm))
        d._route = route
        d._from = min(frm, to)
        d._to = max(frm, to)
        d._patrol_speed = speed
        d._patrol_pos = frm
        return d

    @staticmethod
    def fixed(owner, stats, at):
        return Drone(owner, Drone.STATIC, stats, at)

    @staticmethod
    def stats_for(kind, range_, interval, damage, type_, pierce, projectile_speed):
        s = TowerStats()
        s.kind = kind
        s.range = float(range_)
        s.set_interval(interval)
        s.hit.damage = float(damage)
        s.hit.type = type_
        s.pierce = pierce
        s.projectile_speed = float(projectile_speed)
        return s

    def get_position(self):
        return self._pos

    def is_alive(self):
        return not self._dead

    def kill(self):
        self._dead = True

    def get_age(self):
        return self._age

    def effective_stats(self):
        return self.owner.get_stats() if self.mirror_owner else self.stats

    def get_current_target(self):
        return self._current

    def update(self, game, dt):
        if self._dead:
            return
        if not self.owner.is_alive():
            self._dead = True
            return
        self._age += dt
        if self.lifetime > 0 and self._age >= self.lifetime:
            self._dead = True
            return
        if self.mode is Drone.ORBIT:
            self._angle += self.orbit_speed * dt
            self._pos = self.owner.get_position().add(Vec(math.cos(self._angle) * self.orbit_radius,
                                                          math.sin(self._angle) * self.orbit_radius))
        elif self.mode is Drone.PATROL:
            self._patrol_pos += self._patrol_dir * self._patrol_speed * dt
            if self._patrol_pos >= self._to:
                self._patrol_pos = self._to
                self._patrol_dir = -1
            if self._patrol_pos <= self._from:
                self._patrol_pos = self._from
                self._patrol_dir = 1
            self._pos = self._route.position_at(self._patrol_pos)
        self._cooldown -= dt
        if self._cooldown > 0:
            return
        s = self.effective_stats()
        want = max(s.targets, s.projectiles_per_shot if s.kind is AttackKind.INSTANT else 1)
        frm = self.owner.get_position() if self.range_from_owner else self._pos
        if self.sticky_target:
            t = self._sticky_pick(game, s, frm)
            targets = [t] if t is not None else []
        else:
            targets = game.get_combat().acquire_targets_from(frm, s.range, self.detection, True, self.targeting, max(1, want), None)
        if not targets:
            return
        c = AttackContext(self.owner, s, targets)
        c.damage_mult = self.owner.damage_multiplier(game)
        c.pierce = max(1, s.pierce)
        c.bounces = s.bounces
        c.clones = s.clones
        c.splash = s.splash_radius
        c.speed = s.projectile_speed
        game.get_combat().execute_attack(c, self._pos, self.detection, False)
        rate = s.rate * (self.owner.rate_multiplier(game) if self.inherit_owner_rate else 1)
        self._cooldown = 1.0 / max(0.05, rate)

    def _sticky_pick(self, game, s, frm):
        cur = self._current
        if (cur is not None and cur.is_alive() and not cur.is_stored() and cur.is_targetable_by(self.detection)
                and frm.within_dist(cur.get_position(), s.range + cur.get_radius())):
            return cur
        self._current = None
        cands = game.get_combat().acquire_targets_from(frm, s.range, self.detection, True, self.targeting, 12, None)
        if not cands:
            return None
        taken = set()
        for d in game.get_effects().get_drones():
            if d is not self and d.owner is self.owner and d.is_alive() and d._current is not None:
                taken.add(id(d._current))
        for e in cands:
            if id(e) not in taken:
                self._current = e
                return e
        self._current = cands[0]
        return self._current


# ====================================================================== NodeHazard
class NodeHazard:
    """Nodes joined by damaging laser links, plus an optional slowing polygon (GLM)."""

    def __init__(self, owner):
        self.owner = owner
        self.nodes = []
        self.links = []
        self.line_hit = None
        self.cross_cooldown = 0.3
        self.link_width = 6.0
        self.region = None
        self.region_slow = 0.0
        self.duration = 0.0
        self.permanent = True
        self.detection = True
        self.rgb = 0xffffff
        self.kind = "nodes"
        self._last_hit = {}
        self._dead = False

    @staticmethod
    def line(owner, a, b, hit, cross_cooldown):
        h = NodeHazard(owner)
        h.nodes += [a, b]
        h.links.append((0, 1))
        h.line_hit = hit
        h.cross_cooldown = cross_cooldown
        return h

    @staticmethod
    def network(owner, pts, hit, cross_cooldown, slow):
        h = NodeHazard(owner)
        h.nodes += list(pts)
        n = len(pts)
        for i in range(n - 1):
            h.links.append((i, i + 1))
        if n > 2:
            h.links.append((n - 1, 0))
        h.line_hit = hit
        h.cross_cooldown = cross_cooldown
        if slow > 0 and n >= 3:
            h.region = list(pts)
            h.region_slow = slow
        return h

    def is_alive(self):
        return not self._dead

    def kill(self):
        self._dead = True

    def distance_to_links(self, p):
        best = _MAX
        for a, b in self.links:
            best = min(best, Path.point_segment_distance(p, self.nodes[a], self.nodes[b]))
        return best

    @staticmethod
    def polygon_contains(poly, p):
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            a, b = poly[i], poly[j]
            if (a.y > p.y) != (b.y > p.y) and p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x:
                inside = not inside
            j = i
        return inside

    def update(self, game, dt):
        if self._dead:
            return
        if self.owner is not None and not self.owner.is_alive():
            self._dead = True
            return
        if not self.permanent:
            self.duration -= dt
            if self.duration <= 0:
                self._dead = True
                return
        now = game.get_time()
        x0 = y0 = _MAX
        x1 = y1 = -_MAX
        for pts in (self.nodes, self.region):
            if pts is None:
                continue
            for v in pts:
                x0, y0, x1, y1 = min(x0, v.x), min(y0, v.y), max(x1, v.x), max(y1, v.y)
        if x0 > x1:
            return
        lw = self.link_width
        scan = game.get_enemy_manager().get_grid().scan_box(x0 - lw, y0 - lw, x1 + lw, y1 + lw)
        e = scan.next()
        while e is not None:
            if e.is_alive() and not e.is_stored():
                if self.region is not None and self.region_slow > 0 and self.polygon_contains(self.region, e.get_position()):
                    e.apply_status(StatusKind.SLOW, self.region_slow, TrackZone.REFRESH)
                if self.line_hit is not None and self.links and \
                        self.distance_to_links(e.get_position()) <= lw + e.get_radius() * 0.5:
                    last = self._last_hit.get(e.get_id())
                    if last is None or now - last >= self.cross_cooldown:
                        self._last_hit[e.get_id()] = now
                        h = HitContext(e, self.line_hit, self.owner)
                        h.detection = self.detection
                        h.mult = game.get_global_damage_multiplier()
                        game.get_combat().apply_hit(h)
            e = scan.next()
        if len(self._last_hit) > 400:
            self._last_hit.clear()


# ====================================================================== Barrage
class Barrage:
    """N explosions landing at a point or at the densest cluster, spread over a short time."""
    POINT, DENSEST, BOSS_ELSE_DENSEST = "POINT", "DENSEST", "BOSS_ELSE_DENSEST"

    def __init__(self, source, hit, count, splash):
        self.source = source
        self.aim = Barrage.DENSEST
        self.point = None
        self.count = count
        self.hit = hit
        self.splash = float(splash)
        self.scatter = 0.0
        self.stagger = 0.1
        self.detection = source is not None and source.can_see_camo()
        self.rgb = 0xff8844

    def resolve_aim(self, game):
        from lindefense.enemy.boss import Boss
        all_e = game.get_enemy_manager().get_enemies()
        if self.aim is Barrage.POINT:
            return self.point
        if self.aim is Barrage.BOSS_ELSE_DENSEST:
            boss = None
            for e in all_e:
                if isinstance(e, Boss) and e.is_alive() and not e.is_stored() and (
                        boss is None or e.get_remaining_distance() < boss.get_remaining_distance()):
                    boss = e
            if boss is not None:
                return boss.get_position()
        return clusters.densest_point(all_e)

    def land(self, game, p):
        at = p
        if self.scatter > 0:
            ang = game.get_rng().range(0, math.pi * 2)
            d = math.sqrt(game.get_rng().next()) * self.scatter
            at = p.add(Vec(math.cos(ang) * d, math.sin(ang) * d))
        mult = 1.0 if self.source is None else self.source.damage_multiplier(game)
        game.get_combat().area_hit_full(at, self.splash, self.hit, self.source, mult, 0.0, 999, None, self.detection, False, None)
        game.get_combat().emit(VisualEvent.explosion(at, self.splash, self.rgb))


# ====================================================================== Effects
class TrackPoint:
    def __init__(self, route, route_index, distance, position):
        self.route, self.route_index, self.distance, self.position = route, route_index, distance, position


class _Task:
    __slots__ = ("delay", "action")

    def __init__(self, delay, action):
        self.delay = delay
        self.action = action


class Effects:
    def __init__(self, game):
        self._game = game
        self._zones = []
        self._walkers = []
        self._drones = []
        self._hazards = []
        self._mines = []
        self._tasks = []

    def add_zone(self, z):
        self._zones.append(z)
        return z

    def add_walker(self, w):
        self._walkers.append(w)
        return w

    def add_drone(self, d):
        self._drones.append(d)
        return d

    def add_hazard(self, h):
        self._hazards.append(h)
        return h

    def add_mine(self, m):
        self._mines.append(m)
        return m

    def schedule(self, delay, action):
        self._tasks.append(_Task(delay, action))

    def fire(self, b):
        g = self._game
        aim = b.resolve_aim(g)
        if aim is None:
            return None
        for i in range(b.count):
            if i == 0 and b.stagger <= 0:
                b.land(g, aim)
                continue
            self.schedule(i * b.stagger, lambda b=b, aim=aim: b.land(g, aim))
        return aim

    def get_zones(self):
        return tuple(self._zones)

    def get_walkers(self):
        return tuple(self._walkers)

    def get_drones(self):
        return tuple(self._drones)

    def get_hazards(self):
        return tuple(self._hazards)

    def get_mines(self):
        return tuple(self._mines)

    def mines_of(self, owner, kind):
        return [m for m in self._mines if m.owner is owner and m.is_alive() and (kind is None or kind == m.kind)]

    def drones_of(self, owner, kind):
        return [d for d in self._drones if d.owner is owner and d.is_alive() and (kind is None or kind == d.kind)]

    def zones_of(self, owner, kind):
        return [z for z in self._zones if z.owner is owner and z.is_alive() and (kind is None or kind == z.kind)]

    def remove_owned_by(self, owner):
        for lst in (self._zones, self._walkers, self._drones, self._hazards, self._mines):
            for x in lst:
                if x.owner is owner:
                    x.kill()

    def clear(self):
        for lst in (self._zones, self._walkers, self._drones, self._hazards, self._mines, self._tasks):
            lst.clear()

    def nearest_track_point(self, p):
        best = None
        best_d = _MAX
        for i, r in enumerate(self._game.get_map().get_routes()):
            d = r.nearest_distance_along(p)
            q = r.position_at(d)
            dist = q.dist(p)
            if dist < best_d:
                best_d = dist
                best = TrackPoint(r, i, d, q)
        return best

    def bends_in_range(self, frm, rng):
        out = []
        for i, r in enumerate(self._game.get_map().get_routes()):
            wp = r.get_waypoints()
            for k in range(1, len(wp) - 1):
                if wp[k].dist(frm) <= rng:
                    out.append(TrackPoint(r, i, r.nearest_distance_along(wp[k]), wp[k]))
        out.sort(key=lambda a: a.position.dist_sq(frm))
        return out

    def update(self, dt):
        g = self._game
        tasks = self._tasks
        i = 0
        while i < len(tasks):
            t = tasks[i]
            t.delay -= dt
            if t.delay <= 0:
                del tasks[i]
                t.action()
            else:
                i += 1
        for lst in (self._zones, self._hazards, self._mines, self._walkers, self._drones):
            i = 0
            while i < len(lst):
                lst[i].update(g, dt)
                i += 1
        self._zones[:] = [z for z in self._zones if z.is_alive()]
        self._hazards[:] = [h for h in self._hazards if h.is_alive()]
        self._mines[:] = [m for m in self._mines if m.is_alive()]
        self._walkers[:] = [w for w in self._walkers if w.is_alive()]
        self._drones[:] = [d for d in self._drones if d.is_alive()]
