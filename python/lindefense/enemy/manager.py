"""Owns every live enemy: spawning, movement, status upkeep, neighbour mechanics, leaks, deaths, rewards, splits."""
from operator import attrgetter

from lindefense.javacompat import jround
from lindefense.jenum import EnumSet
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.boss import Boss
from lindefense.enemy.enemy import Enemy
from lindefense.enemy.grid import EnemyGrid, EnemyList
from lindefense.enemy.types import EnemyType, Mechanic, Modifier

_BY_DISTANCE = attrgetter("_distance")   # Enemy.get_distance
_PASSIVE = (Mechanic.NONE, Mechanic.PALANTIR, Mechanic.ACCELERATE_ON_DAMAGE, Mechanic.RADIX_PHASES)


def _overrides(obj, name) -> bool:
    """Whether obj's method name is something other than GameMap's default."""
    from lindefense.map.game_map import GameMap
    return getattr(getattr(obj, name), "__func__", None) is not getattr(GameMap, name)


def _is_tower(o) -> bool:
    global _Tower
    if _Tower is None:
        from lindefense.tower.tower import Tower   # imported late (tower imports enemy modules)
        _Tower = Tower
    return isinstance(o, _Tower)


_Tower = None


class EnemyManager:
    def __init__(self, game):
        self._game = game
        self._enemies = EnemyList()
        self._grid = EnemyGrid(self._enemies)
        self._pending = []
        self._route_keys = []
        self._route_lists = []
        self._route_by_id = {}   # id(route) -> its list in _route_lists (routes are kept alive by _route_keys)
        self._routes_sorted = False
        self._scratch = []
        self._total_killed = 0
        self._total_leaked = 0
        self._total_spawned = 0

    def __setstate__(self, state):
        """Loading a saved run (savegame): _route_by_id is keyed by id(route), so re-key it for the new objects."""
        self.__dict__.update(state)
        slot = {id(l): i for i, l in enumerate(self._route_lists)}   # each value is one of _route_lists
        self._route_by_id = {id(self._route_keys[slot[id(l)]]): l for l in self._route_by_id.values()}

    def get_enemies(self):
        return self._enemies

    def get_grid(self):
        return self._grid

    def get_pending(self):
        return self._pending

    def get_total_killed(self):
        return self._total_killed

    def get_total_leaked(self):
        return self._total_leaked

    def get_total_spawned(self):
        return self._total_spawned

    def is_empty(self):
        return not self._enemies and not self._pending

    def get_alive_count(self):
        n = len(self._enemies) + len(self._pending)
        for e in self._enemies:
            n += len(e.get_stored_enemies())
        return n

    def spawn(self, type_, mods, route_index, distance):
        g = self._game
        return self.spawn_scaled(type_, mods, route_index, distance, g.get_wave_hp_scale(type_), g.get_wave_speed_scale())

    def spawn_scaled(self, type_, mods, route_index, distance, hp_scale, speed_scale):
        g = self._game
        routes = g.get_map().get_routes()
        idx = g.get_map().pick_route(g) if route_index < 0 or route_index >= len(routes) else route_index
        route = routes[idx]
        cls = Boss if type_.is_boss() else Enemy
        e = cls(type_, mods, route, idx, distance, hp_scale, speed_scale)
        e.set_spawn_time(g.get_time())
        self._pending.append(e)
        self._total_spawned += 1
        return e

    def clear(self):
        self._enemies.clear()
        self._pending.clear()
        for l in self._route_lists:
            l.clear()

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self._flush_pending()
        g = self._game
        now = g.get_time()
        enemies = self._enemies
        # the passes below iterate with `for e in enemies`: a list iterator re-reads the length every step, exactly
        # like `while i < len(enemies)` (the list never changes during them anyway: spawns wait in _pending)
        # 1. statuses, DOT, regrow, boss logic
        for e in enemies:
            dot = e.tick_statuses(dt)
            if dot > 0:
                dealt = e.take_damage(dot, now)
                ds = e.get_dot_source()
                if ds is not None and _is_tower(ds):
                    e.set_last_hit_by(ds)
                    ds.add_damage_dealt(dealt)
            if isinstance(e, Boss):
                e.update_boss(g, dt)
        # 2. movement + leaks
        gmap = g.get_map()
        gmul = g.get_global_enemy_speed_multiplier()
        # maps without a speed / moved hook use GameMap's (1.0 and a no-op): skip the per-enemy calls
        speed_hook = _overrides(gmap, "enemy_speed_multiplier")
        ext = 1.0 * gmul
        moved_hook = _overrides(gmap, "on_enemy_moved")
        for e in enemies:
            if not e._alive:
                continue
            if speed_hook:
                ext = gmap.enemy_speed_multiplier(e) * gmul
            if e.advance(dt, ext):
                self._leak(e)
            elif moved_hook:
                gmap.on_enemy_moved(g, e)
        # 2b. reversed enemies (Cohere Command Override) damage whatever they touch
        for e in enemies:
            if e._alive and e._reverse_remaining > 0 and not e._stored:
                self._reverse_contact(e, dt)
        # 3. neighbour-based mechanics (Accelerate and Radix are passive: _run_mechanic returns at once for them)
        self._rebuild_route_index()
        for e in enemies:
            if not e._alive or e._stored:
                continue
            if e._type.mechanic not in _PASSIVE:
                self._run_mechanic(e, dt)
        # 4. deaths
        for e in enemies:
            if e._alive and e._hp <= 0:
                self.kill(e)
        # 5. sweep (swap-remove from the back, as the Java build does, so list order matches)
        for i in range(len(enemies) - 1, -1, -1):
            e = enemies[i]
            if not e._alive or e._stored:
                last = len(enemies) - 1
                list.__setitem__(enemies, i, enemies[last])
                enemies.pop()
        self._flush_pending()

    def _reverse_contact(self, r, dt):
        dmg = r.get_reverse_dps() * dt
        if dmg <= 0:
            return
        src = r.get_reverse_source()
        rp = r.get_position()
        rad = r.get_radius()
        near = self._grid.near(rp.x, rp.y, rad, self._scratch)
        now = self._game.get_time()
        credit = src is not None and _is_tower(src)
        for o in near:
            if o is r or not o._alive or o._stored:
                continue
            rr = rad + o._radius
            q = o._cached_pos   # o.get_position().dist_sq(rp), inlined
            dx = q.x - rp.x
            dy = q.y - rp.y
            if dx * dx + dy * dy > rr * rr:
                continue
            dealt = o.take_damage(dmg, now)
            if credit:
                o.set_last_hit_by(src)
                src.add_damage_dealt(dealt)

    def _flush_pending(self):
        if self._pending:
            self._enemies.extend(self._pending)
            self._pending.clear()

    def _rebuild_route_index(self):
        for l in self._route_lists:
            l.clear()
        by_route = self._route_by_id
        for e in self._enemies:
            if not e._alive or e._stored:
                continue
            l = by_route.get(id(e._route))
            if l is None:
                l = self._route_list(e._route, True)
                by_route[id(e._route)] = l
            l.append(e)
        for l in self._route_lists:
            l.sort(key=_BY_DISTANCE)
        self._routes_sorted = True

    def _route_list(self, route, create):
        for i, k in enumerate(self._route_keys):
            if k is route:
                return self._route_lists[i]
        if not create:
            return None
        l = []
        self._route_keys.append(route)
        self._route_lists.append(l)
        return l

    def _route_mates(self, e):
        l = self._route_by_id.get(id(e.get_route()))   # _route_list(route, False)
        return () if l is None else l

    def _window_start(self, mates, from_distance):
        if not self._routes_sorted:
            return 0
        lo, hi = 0, len(mates)
        key = from_distance - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            if mates[mid]._distance < key:   # get_distance()
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _past_window(self, o, to_distance):
        return self._routes_sorted and o.get_distance() > to_distance + 1

    def _run_mechanic(self, e, dt):
        g = self._game
        m = e.get_type().mechanic
        if m is Mechanic.HEAP_SHIELD:
            if e.is_disrupted():
                return
            mates = self._route_mates(e)
            ed = e._distance
            i = self._window_start(mates, ed - 90)
            past = ed + 1   # _past_window(o, ed); shielding moves nobody, so ed and the limit stay fixed
            sorted_ = self._routes_sorted
            tick = g.get_tick()
            n = len(mates)
            while i < n:
                o = mates[i]
                i += 1
                od = o._distance
                if sorted_ and od > past:
                    break
                if o is e:
                    continue
                gap = ed - od
                if 0 < gap <= 90:
                    o.set_shielded_tick(tick)
            return
        if m is Mechanic.ACCELERATE_ON_DAMAGE or m is Mechanic.RADIX_PHASES:
            return
        e.set_mechanic_timer(e.get_mechanic_timer() + dt)
        if m is Mechanic.BUBBLE_SWAP:
            period = 3.0
        elif m is Mechanic.SELECTION_FRONT:
            period = 2.5
        elif m is Mechanic.INSERTION_LEAPFROG:
            period = 2.0
        elif m is Mechanic.SHELL_GAP_JUMP:
            period = 3.0
        else:
            period = 1.0
        if e.get_mechanic_timer() < period:
            return
        e.set_mechanic_timer(0.0)
        if e.is_disrupted() or e.is_stunned():
            return
        events = g.get_events()
        if m is Mechanic.BUBBLE_SWAP:
            ahead = self._nearest_ahead(e, 45)
            if ahead is not None:
                self._routes_sorted = False
                d = ahead.get_distance()
                ahead.set_distance(e.get_distance())
                e.set_distance(d)
                events.append(VisualEvent.split(e.get_position(), 14, 0x9be7ff))
        elif m is Mechanic.SELECTION_FRONT:
            best = -1.0
            mates = self._route_mates(e)
            i = self._window_start(mates, e.get_distance())
            while i < len(mates):
                o = mates[i]
                i += 1
                if self._past_window(o, e.get_distance() + 140):
                    break
                gap = o.get_distance() - e.get_distance()
                if o is not e and 0 < gap <= 140 and o.get_distance() > best:
                    best = o.get_distance()
            if best >= 0:
                self._routes_sorted = False
                e.set_distance(best + 6)
                events.append(VisualEvent.teleport(e.get_position()))
        elif m is Mechanic.INSERTION_LEAPFROG:
            ahead = self._nearest_ahead(e, 70)
            if ahead is not None:
                self._routes_sorted = False
                e.set_distance(ahead.get_distance() + 6)
                events.append(VisualEvent.split(e.get_position(), 10, 0xffe066))
        elif m is Mechanic.SHELL_GAP_JUMP:
            gap = e.current_shell_gap()
            frm = e.get_position()
            self._routes_sorted = False
            e.shift_distance(gap)
            e.set_shell_jump_index(e.get_shell_jump_index() + 1)
            events.append(VisualEvent.chain(frm, e.get_position(), 0xc2b280))
        elif m is Mechanic.BUCKET_STORE:
            stored = e.get_stored_enemies()
            if len(stored) >= 6:
                return
            mates = self._route_mates(e)
            i = self._window_start(mates, e.get_distance() - 30)
            while i < len(mates):
                o = mates[i]
                i += 1
                if self._past_window(o, e.get_distance() + 30):
                    break
                if o is e or not o.is_alive() or o.is_stored() or o.is_boss():
                    continue
                if o.get_type().base_hp > 5 or o.get_type().mechanic is Mechanic.BUCKET_STORE:
                    continue
                if abs(o.get_distance() - e.get_distance()) <= 30:
                    o.set_stored(True)
                    stored.append(o)
                    events.append(VisualEvent.split(o.get_position(), 12, 0x8ad8ff))
                    if len(stored) >= 6:
                        break

    def _nearest_ahead(self, e, max_gap):
        best = None
        best_gap = max_gap
        mates = self._route_mates(e)
        i = self._window_start(mates, e.get_distance())
        while i < len(mates):
            o = mates[i]
            i += 1
            if self._past_window(o, e.get_distance() + max_gap):
                break
            if o is e:
                continue
            gap = o.get_distance() - e.get_distance()
            if 0 < gap <= best_gap:
                best_gap = gap
                best = o
        return best

    # ------------------------------------------------------------------
    def _leak(self, e):
        if not e.is_alive():
            return
        if self._game.is_campaign_won() or e._type.is_hologram():
            # the final boss is down: whatever still reaches the exit during the victory sequence (a child of a late
            # kill, an outsourced contractor) leaves without costing lives or the run's leak-free record; so does a
            # Palantir hologram, a decoy that costs no lives
            for s in e.get_stored_enemies():
                s.mark_dead()
            e.mark_dead()
            return
        lives = e.get_type().lives
        for s in e.get_stored_enemies():
            lives += s.get_type().lives
            s.mark_leaked()
        e.mark_leaked()
        self._total_leaked += 1
        self._game.lose_lives(self._game.get_variance().leak_lives(lives), e)

    def kill(self, e):
        self._destroy(e, True)

    def destroy_without_children(self, e, credit):
        if e is None or not e.is_alive():
            return
        if credit is not None:
            e.set_last_hit_by(credit)
        self._destroy(e, False)

    def _destroy(self, e, children):
        if not e.is_alive():
            return
        g = self._game
        e.mark_dead()
        self._total_killed += 1
        src = e.get_last_hit_by()
        reward = float(jround(e.get_type().reward * g.get_reward_scale()))
        if reward > 0:
            g.add_cash(reward, e.get_position())
            g.add_pop_value(reward)
        g.on_enemy_killed(e)
        if src is not None and _is_tower(src):
            src.add_kill()
            src.get_behavior().on_kill(g, src, e)
        t = e.get_type()
        if t is EnemyType.PALANTIR:
            return
        inherited = EnumSet()
        if e.has(Modifier.CAMO):
            inherited.add(Modifier.CAMO)
        if e.has(Modifier.REGROW):
            inherited.add(Modifier.REGROW)
        if e.has(Modifier.FORTIFIED) and e.is_boss():
            inherited.add(Modifier.FORTIFIED)
        k = 0
        ct = t.get_child_types()
        cc = t.get_child_counts()
        if children:
            for i in range(len(ct)):
                for _ in range(cc[i]):
                    d = e.get_distance() - 6 * k
                    k += 1
                    child = self.spawn_scaled(ct[i], inherited, e.get_route_index(), max(0.0, d), e.get_hp_scale(), e.get_speed_scale())
                    child.set_drifted(e.has_drifted())
        if children and len(ct) > 0:
            g.get_events().append(VisualEvent.split(e.get_position(), e.get_radius() * 1.6, 0xffffff))
        else:
            g.get_events().append(VisualEvent.death(e.get_position(), e.get_radius(), 0xffffff))
        stored = e.get_stored_enemies()
        if stored:
            for i, s in enumerate(stored):
                s.set_stored(False)
                s.teleport_to(e.get_route(), e.get_route_index(), max(0.0, e.get_distance() - 8 * i))
                if not any(x is s for x in self._enemies):
                    self._pending.append(s)
            stored.clear()

    def count_of_type(self, t):
        n = 0
        for e in self._enemies:
            if e.get_type() is t:
                n += 1
            for s in e.get_stored_enemies():
                if s.get_type() is t:
                    n += 1
        for e in self._pending:
            if e.get_type() is t:
                n += 1
        return n
