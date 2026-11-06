"""Support (Grok, Perplexity) and Experimental Titan (Qwen, Llama, Mistral, Cohere, GLM, Kimi, MiniMax) behaviours."""
import math
import sys

from lindefense.combat import clusters
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.projectile import HitContext, Shot
from lindefense.combat.visual_event import VisualEvent
from lindefense.effects.effects import Barrage, Drone, NodeHazard, TrackWalker, TrackZone
from lindefense.enemy.boss import Boss
from lindefense.enemy.types import EnemyType, StatusKind
from lindefense.javacompat import jint, jround
from lindefense.map.game_map import WIDTH, HEIGHT
from lindefense.map.path import Path
from lindefense.sim.vec import Vec
from lindefense.tower.behavior.base import TowerBehavior, enemies_within
from lindefense.tower.tower_type import BuffStat

_MAX = sys.float_info.max
_INT_MAX = 2147483647


# ====================================================================== Grok
_TAG_CLUSTER, _TAG_FRAGMENT, _TAG_HEAVY = "cluster", "fragment", "heavy"


class GrokBehavior(TowerBehavior):
    """Burn spread (U1), Paradox Trap volleys + Densest Cluster (U2), Chaos Mode missile cycle (U3), Real-Time Override."""

    def allows_densest_cluster(self, t):
        return t.get_stats().has("allowDensest")

    def update(self, game, t, dt):
        s = t.get_stats()
        if s.has("volleyInterval") and t.periodic("volley", s.p("volleyInterval"), dt):
            self._volley(game, t, s)

    def _volley(self, game, t, s):
        sees = t.can_see_camo()
        in_range = [e for e in enemies_within(game, t.get_position(), t.effective_range(game)) if e.is_targetable_by(sees)]
        centre = clusters.densest(in_range, game.get_enemy_manager().get_enemies())
        if centre is None:
            return
        b = Barrage(t, HitSpec(s.p("volleyDamage"), s.hit.type), s.pi("volleyMissiles"), s.splash_radius)
        b.aim = Barrage.POINT
        b.point = centre.get_position()
        game.get_effects().fire(b)

    def modify_attack(self, game, t, c):
        s = t.get_stats()
        if not s.has("chaosCycle"):
            return
        kind = jint(t.add_counter("chaos", 1)) - 1
        kind %= s.pi("chaosCycle")
        if kind == 0:
            c.tag = "incendiary"
            return
        h = c.edit_hit()
        h.dot_dps = 0.0
        h.dot_duration = 0.0
        if kind == 1:
            c.tag = _TAG_CLUSTER
        else:
            c.tag = _TAG_HEAVY
            h.mult_vs_boss *= s.p("chaosHeavyMoabMult")

    def on_hit(self, game, t, c):
        if c.immune:
            return
        s = t.get_stats()
        if c.hit().dot_dps > 0 and s.has("burnSpreadRadius") and c.target.is_alive():
            self._spread_burn(game, t, c, s)
        p = c.projectile
        if p is not None and p.get_shot().tag == _TAG_CLUSTER and t.state().get("lastSplit") is not p:
            t.state()["lastSplit"] = p
            self._split(game, t, c, p, s)

    def _spread_burn(self, game, t, c, s):
        seen = {c.target.get_id()}
        frontier = [c.target]
        sees = t.can_see_camo()
        for _ in range(s.pi("burnSpreads")):
            nxt = []
            for frm in frontier:
                for e in enemies_within(game, frm.get_position(), s.p("burnSpreadRadius")):
                    if e.get_id() in seen:
                        continue
                    seen.add(e.get_id())
                    if not e.is_targetable_by(sees):
                        continue
                    e.apply_burn(c.hit().dot_dps, c.hit().dot_duration, t)
                    nxt.append(e)
            frontier = nxt

    def _split(self, game, t, c, p, s):
        at = p.get_position()
        splash = p.get_shot().splash
        blasted = set()
        for e in game.get_enemy_manager().get_grid().near(at.x, at.y, splash, []):
            if e.is_alive() and not e.is_stored() and e.get_position().dist(at) <= splash + e.get_radius():
                blasted.add(e.get_id())
        blasted.add(c.target.get_id())
        sees = t.can_see_camo()
        near = [e for e in enemies_within(game, at, s.p("chaosSplitRange"))
                if e.get_id() not in blasted and e.is_targetable_by(sees)]
        if not near:
            return
        near.sort(key=lambda e: e.get_position().dist_sq(at))
        for i in range(s.pi("chaosSplit")):
            f = Shot.of(game, t, at, near[i % len(near)])
            f.hit = p.get_hit()
            f.splash = 0.0
            f.pierce = 1
            f.tag = _TAG_FRAGMENT
            game.get_combat().fire(f).get_hit_ids().update(blasted)

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        for o in game.get_tower_manager().get_towers():
            if o.get_position().dist(t.get_position()) <= a.p("radius"):
                o.add_timed_buff(BuffStat.BOSS_DAMAGE_PCT, t.get_type(), a.p("bossDamagePct"), a.p("duration"))
        return True


class PerplexityBehavior(TowerBehavior):
    """Radar pulse on Camo enemies (the CUSTOM attack) and Deep Research Scrape."""

    def attack(self, game, t):
        s = t.get_stats()
        rng = t.effective_range(game)
        camo = [e for e in enemies_within(game, t.get_position(), rng) if e.is_camo()]
        if not camo:
            return False
        h = HitSpec(s.p("pulseDamage"), s.hit.type)
        for e in camo:
            c = HitContext(e, h, t)
            c.from_attack = True
            game.get_combat().apply_hit(c)
        game.get_combat().emit(VisualEvent.ability(t.get_position(), rng, t.get_type().primary_rgb))
        t.on_attacked(game)
        return True

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        cash = min(a.p("maxCash"), math.floor(game.get_round_pop_value() * a.p("popValuePct")))
        if cash > 0:
            game.add_cash(cash, t.get_position())
        game.get_combat().emit(VisualEvent.text(t.get_position(), "+$" + str(jint(cash)), 0xffd166))
        return True


# ====================================================================== Qwen
_QWEN_DRONES, _QWEN_TIER = "qwenDrones", "qwenDroneTier"


def _qwen_drone_stats(t):
    ds = t.get_stats().copy()
    ds.set_interval(t.get_stats().p("droneInterval"))
    return ds


def _qwen_outside(r, frm, seg, t):
    return r.position_at(frm + seg / 2).dist(t.get_position()) > t.get_stats().range + seg / 2


def _qwen_count_segments(r, seg, t, outside_only):
    c = 0
    frm = 0.0
    while frm + seg <= r.get_total_length():
        if not outside_only or _qwen_outside(r, frm, seg, t):
            c += 1
        frm += seg
    return c


class QwenBehavior(TowerBehavior):
    """Drone Formation (U2) patrol drones and the Cosmic Sovereign Burst."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if not s.has("droneCount"):
            return
        n = s.pi("droneCount")
        ds = t.state().get(_QWEN_DRONES)
        if ds is None or len(ds) != n:
            bigger = [None] * n
            if ds is not None:
                bigger[:min(len(ds), n)] = ds[:min(len(ds), n)]
            ds = bigger
            t.state()[_QWEN_DRONES] = ds
        retier = t.counter(_QWEN_TIER) != t.get_tier() + 1
        dstats = None
        for i in range(n):
            d = ds[i]
            if d is None or not d.is_alive():
                ds[i] = self._spawn(game, t, i, n)
            elif retier:
                if dstats is None:
                    dstats = _qwen_drone_stats(t)
                d.stats = dstats
        if retier:
            t.set_counter(_QWEN_TIER, t.get_tier() + 1)

    @staticmethod
    def _spawn(game, t, index, count):
        s = t.get_stats()
        seg = s.p("droneSegment")
        routes = game.get_map().get_routes()
        for pss in range(2):
            outside_only = pss == 0
            total = sum(_qwen_count_segments(r, seg, t, outside_only) for r in routes)
            if total == 0:
                continue
            pick = min(total - 1, jint((index + 0.5) * total / count))
            for r in routes:
                c = _qwen_count_segments(r, seg, t, outside_only)
                if pick >= c:
                    pick -= c
                    continue
                frm = 0.0
                while frm + seg <= r.get_total_length():
                    if outside_only and not _qwen_outside(r, frm, seg, t):
                        frm += seg
                        continue
                    if pick > 0:
                        pick -= 1
                        frm += seg
                        continue
                    pick -= 1
                    d = Drone.patrol(t, _qwen_drone_stats(t), r, frm, frm + seg, s.p("droneSpeed"))
                    d.kind = "qwen"
                    d.rgb = t.get_type().primary_rgb
                    game.get_effects().add_drone(d)
                    return d
        r = routes[0]
        d = Drone.patrol(t, _qwen_drone_stats(t), r, 0, r.get_total_length(), s.p("droneSpeed"))
        d.kind = "qwen"
        d.rgb = t.get_type().primary_rgb
        game.get_effects().add_drone(d)
        return d

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        h = HitSpec(a.p("damage"), DamageType.ENERGY)
        for e in list(game.get_enemy_manager().get_enemies()):
            if not e.is_alive() or e.is_stored():
                continue
            if e.is_boss() and e.get_type() is not EnemyType.PALANTIR:
                e.strip_fortified()
            if isinstance(e, Boss) and e.get_type() is EnemyType.PALANTIR:
                e.disable_phase_shield(a.p("palantirShieldOff"))
            game.get_combat().apply_hit_simple(e, h, t, 1, 0)
        game.get_combat().emit(VisualEvent.banner("SOVEREIGN BURST", t.get_type().primary_rgb, 1.2))
        return True


# ====================================================================== Llama
class LlamaBehavior(TowerBehavior):
    """Charging llamas (CUSTOM attack), Mythical Stampede shockwave (U3) and Open Titan Stampede."""

    def attack(self, game, t):
        s = t.get_stats()
        targets = game.get_combat().acquire_targets(t, 1)
        if not targets:
            return False
        e = targets[0]
        half = s.p("chargeSegment") / 2
        centre = e.get_distance()
        n = s.pi("chargeCount")
        for i in range(n):
            start = min(e.get_route().get_total_length(), centre + half + i * 24)
            end = max(0.0, centre - half)
            w = TrackWalker(e.get_route(), start, end, s.p("chargeSpeed"), t, s.hit)
            w.pierce = t.effective_pierce()
            w.detection = t.can_see_camo()
            w.respect_camo = True
            w.kind = "llama"
            w.rgb = t.get_type().primary_rgb
            game.get_effects().add_walker(w)
        t.set_last_target(e)
        t.on_attacked(game)
        return True

    def update(self, game, t, dt):
        s = t.get_stats()
        if not s.has("shockInterval") or not t.periodic("shock", s.p("shockInterval"), dt):
            return
        h = HitSpec(s.p("shockDamage"), DamageType.KINETIC)
        h.knockback = s.p("shockKnockback")
        h.uncapped_knockback = True
        h.mult_vs_boss = s.p("shockBossMult")
        rng = t.effective_range(game)
        n = game.get_combat().area_hit(t.get_position(), rng, h, t, t.damage_multiplier(game), 9999, None)
        if n > 0:
            game.get_combat().emit(VisualEvent.ability(t.get_position(), rng, t.get_type().primary_rgb))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        h = HitSpec(a.p("damage"), DamageType.KINETIC)
        boss_hit = HitSpec(a.p("bossDamage"), DamageType.KINETIC)
        boss_hit.boss_knockback = a.p("bossKnockback")
        boss_hit.uncapped_knockback = True
        for r in game.get_map().get_routes():
            w = TrackWalker(r, r.get_total_length(), 0, a.p("herdSpeed"), t, h)
            w.boss_hit = boss_hit
            w.pierce = _INT_MAX
            w.detection = True
            w.kind = "herd"
            w.rgb = t.get_type().primary_rgb
            game.get_effects().add_walker(w)
        game.get_combat().emit(VisualEvent.banner("OPEN TITAN STAMPEDE", t.get_type().primary_rgb, 1.2))
        return True


# ====================================================================== Mistral
_VORTEX, _TEMPESTS = "vortex", "tempests"


class _Tempest:
    def __init__(self, zone, push):
        self.zone = zone
        self.push = push
        self.pushed = set()


def _push_bosses(game, tp):
    c = tp.zone.center
    scan = game.get_enemy_manager().get_grid().scan(c.x, c.y, tp.zone.radius)
    e = scan.next()
    while e is not None:
        if (e.is_boss() and e.is_alive() and not e.is_stored() and not e.is_control_immune()
                and tp.zone.contains(e) and e.get_id() not in tp.pushed):
            tp.pushed.add(e.get_id())
            e.apply_knockback_uncapped(tp.push)
        e = scan.next()


class MistralBehavior(TowerBehavior):
    """Gust (U1), Cyclone tornado (U2), Hurricane vortex (U3) and Stratosphere Tempest."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if s.has("gustInterval") and t.periodic("gust", s.p("gustInterval"), dt):
            self._gust(game, t, s)
        if s.has("tornadoInterval"):
            self._cyclone(game, t, s, dt)
        if s.has("vortexRadius"):
            self._vortex(game, t, s, dt)
        live = t.state().get(_TEMPESTS)
        if live is not None:
            for i in range(len(live) - 1, -1, -1):
                tp = live[i]
                if not tp.zone.is_alive():
                    del live[i]
                    continue
                _push_bosses(game, tp)

    @staticmethod
    def _gust(game, t, s):
        rng = t.effective_range(game)
        tp = t.get_position()
        fast, other = s.p("gustFast"), s.p("gustOther")
        n = 0
        scan = game.get_enemy_manager().get_grid().scan(tp.x, tp.y, rng)
        e = scan.next()
        while e is not None:
            if e.is_alive() and not e.is_stored() and not e.is_boss() and e.get_position().dist(tp) <= rng + e.get_radius():
                if e.apply_knockback_uncapped(fast if e.is_fast_for_knockback() else other) > 0:
                    n += 1
            e = scan.next()
        if n > 0:
            game.get_combat().emit(VisualEvent.ability(tp, rng, t.get_type().primary_rgb))

    @staticmethod
    def _cyclone(game, t, s, dt):
        interval = s.p("tornadoInterval")
        if t.add_counter("cyclone", dt) < interval:
            return
        first = game.get_combat().acquire_targets(t, 1)
        if not first:
            t.set_counter("cyclone", interval)
            return
        at = first[0].get_position()
        t.set_counter("cyclone", 0)
        z = TrackZone(at, s.p("tornadoRadius"), t)
        z.duration = s.p("tornadoDuration")
        z.tick_interval = s.p("tornadoTick")
        z.tick_hit = HitSpec(s.p("tornadoDamage"), DamageType.KINETIC)
        z.kind = "tornado"
        z.rgb = t.get_type().primary_rgb
        game.get_effects().add_zone(z)
        game.get_combat().emit(VisualEvent.text(at, "Cyclone", t.get_type().primary_rgb))

    @staticmethod
    def _vortex(game, t, s, dt):
        z = t.state().get(_VORTEX)
        if z is not None and z.is_alive():
            return
        if not t.periodic("vortexRetry", 0.5, dt):
            return
        bends = game.get_effects().bends_in_range(t.get_position(), t.effective_range(game))
        if not bends:
            return
        z = TrackZone(bends[0].position, s.p("vortexRadius"), t)
        z.permanent = True
        z.tick_interval = s.p("vortexTick")
        h = HitSpec(s.p("vortexDamage"), DamageType.KINETIC)
        h.mult_vs_boss = s.p("vortexBossMult")
        z.tick_hit = h
        z.slow = s.p("vortexSlow")
        z.kind = "vortex"
        z.rgb = t.get_type().primary_rgb
        game.get_effects().add_zone(z)
        t.state()[_VORTEX] = z

    def activate_ability(self, game, t, target):
        if target is None:
            return False
        a = t.get_ability()
        fx = game.get_effects()
        bends = fx.bends_in_range(target, a.p("snapRange"))
        if bends:
            at = bends[0].position
        else:
            p = fx.nearest_track_point(target)
            if p is None:
                return False
            at = p.position
        z = TrackZone(at, a.p("radius"), t)
        z.duration = a.p("duration")
        z.bosses_only = True
        z.tick_interval = a.p("tick")
        z.tick_hit = HitSpec(a.p("damage"), DamageType.KINETIC)
        z.kind = "tempest"
        z.rgb = t.get_type().primary_rgb
        fx.add_zone(z)
        live = t.state().setdefault(_TEMPESTS, [])
        tp = _Tempest(z, a.p("bossKnockback"))
        live.append(tp)
        _push_bosses(game, tp)
        game.get_combat().emit(VisualEvent.banner("STRATOSPHERE TEMPEST", t.get_type().primary_rgb, 1.2))
        return True


# ====================================================================== Cohere
_LAST_SHELL = "fragShell"


class CohereBehavior(TowerBehavior):
    """Fragmentation shrapnel rays (U1) and Command Override."""

    def on_hit(self, game, t, c):
        s = t.get_stats()
        if c.projectile is None or not s.has("shrapnelCount"):
            return
        if t.state().get(_LAST_SHELL) is c.projectile:
            return
        t.state()[_LAST_SHELL] = c.projectile
        self._fragment(game, t, s, c.projectile.get_position(), c.target)

    @staticmethod
    def _fragment(game, t, s, impact, struck):
        n = s.pi("shrapnelCount")
        pierce = max(1, s.pi("shrapnelPierce"))
        rng = s.p("shrapnelRange")
        width = s.p("shrapnelWidth")
        h = HitSpec(s.p("shrapnelDamage"), s.hit.type)
        mult = t.damage_multiplier(game)
        sees = t.can_see_camo()
        rot = game.get_rng().range(0, math.pi * 2 / n)
        rgb = t.get_type().secondary_rgb
        lst = []
        combat = game.get_combat()
        grid = game.get_enemy_manager().get_grid()
        for k in range(n):
            ang = rot + k * math.pi * 2 / n
            end = Vec(impact.x + math.cos(ang) * rng, impact.y + math.sin(ang) * rng)
            done = []
            grid.box(min(impact.x, end.x) - width, min(impact.y, end.y) - width,
                     max(impact.x, end.x) + width, max(impact.y, end.y) + width, lst)
            for _ in range(pierce):
                best = None
                best_d = _MAX
                for e in lst:
                    if e is struck or not e.is_targetable_by(sees):
                        continue
                    if Path.point_segment_distance(e.get_position(), impact, end) > e.get_radius() + width:
                        continue
                    if any(x is e for x in done):
                        continue
                    d = e.get_position().dist_sq(impact)
                    if d < best_d:
                        best_d = d
                        best = e
                if best is None:
                    break
                done.append(best)
                combat.apply_hit_simple(best, h, t, mult, 0)
            combat.emit(VisualEvent.beam(impact, end, rgb))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        count = jint(a.p("count"))
        pick = [None] * count
        dist = [0.0] * count
        found = 0
        tp = t.get_position()
        for e in game.get_enemy_manager().get_enemies():
            if not e.is_alive() or e.is_stored():
                continue
            if e.is_boss() and e.get_type() is not EnemyType.BELLARMINE_COLLEGE_PREP:
                continue
            d = e.get_position().dist_sq(tp)
            if found >= count and d >= dist[count - 1]:
                continue
            if found < count:
                found += 1
            at = found - 1
            while at > 0 and dist[at - 1] > d:
                dist[at] = dist[at - 1]
                pick[at] = pick[at - 1]
                at -= 1
            dist[at] = d
            pick[at] = e
        if found == 0:
            return False
        for i in range(found):
            pick[i].start_reverse(a.p("duration"), a.p("contactDps"), t)
            game.get_combat().emit(VisualEvent.text(pick[i].get_position(), "Override", t.get_type().primary_rgb))
        return True


# ====================================================================== GLM
_NET, _NET_TIER = "net", "netTier"
_SCAN_STEP = 10.0


def _sides(r, d, spread):
    p = r.position_at(d)
    direction = r.direction_at(d)
    nrm = Vec(-direction.y, direction.x).scale(spread)
    return p.add(nrm), p.sub(nrm)


class GlmBehavior(TowerBehavior):
    """Node network on the track (U1-U3) rebuilt per tier, and Matrix Overload."""

    def on_placed(self, game, t):
        self._build(game, t)

    def on_upgraded(self, game, t):
        self._build(game, t)

    def update(self, game, t, dt):
        if not t.get_stats().has("nodes"):
            return
        cur = t.state().get(_NET)
        if cur is not None and cur.is_alive() and t.counter(_NET_TIER) == t.get_tier() + 1:
            return
        if t.periodic("netRetry", 0.25, dt):
            self._build(game, t)

    @staticmethod
    def _build(game, t):
        s = t.get_stats()
        old = t.state().pop(_NET, None)
        if old is not None:
            old.kill()
        t.set_counter(_NET_TIER, 0)
        if not s.has("nodes"):
            return
        rng = t.effective_range(game)
        c = game.get_effects().nearest_track_point(t.get_position())
        if c is None or c.position.dist(t.get_position()) > rng:
            return
        r = c.route
        tp = t.get_position()
        lo = hi = c.distance
        while lo - _SCAN_STEP >= 0 and r.position_at(lo - _SCAN_STEP).dist(tp) <= rng:
            lo -= _SCAN_STEP
        while hi + _SCAN_STEP <= r.get_total_length() and r.position_at(hi + _SCAN_STEP).dist(tp) <= rng:
            hi += _SCAN_STEP
        h = HitSpec(s.p("lineDamage"), DamageType.GRAVITY)
        h.mult_vs_fortified = s.p("lineFortifiedMult", 1.0)
        cd = s.p("lineCooldown")
        spread = s.p("nodeSpread")
        n = s.pi("nodes")
        if n <= 2:
            a, b = _sides(r, (lo + hi) / 2, spread)
            net = NodeHazard.line(t, a, b, h, cd)
        else:
            k = n // 2
            left, right = [], []
            for i in range(k):
                d = (lo + hi) / 2 if k == 1 else lo + (hi - lo) * i / (k - 1)
                a, b = _sides(r, d, spread)
                left.append(a)
                right.append(b)
            poly = list(left) + [right[i] for i in range(k - 1, -1, -1)]
            net = NodeHazard.network(t, poly, h, cd, s.p("gridSlow", 0.0))
            for i in range(1, k - 1):
                net.links.append((i, n - 1 - i))
        net.kind = "gravity grid"
        net.rgb = t.get_type().primary_rgb
        game.get_effects().add_hazard(net)
        t.state()[_NET] = net
        t.set_counter(_NET_TIER, t.get_tier() + 1)

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        for e in game.get_enemy_manager().get_enemies():
            if not e.is_alive() or e.is_stored():
                continue
            if e.is_boss():
                e.apply_status(StatusKind.STUN, 1, a.p("bossStun"), True)
            else:
                e.apply_status(StatusKind.STUN, 1, a.p("stun"), False)
        return True


# ====================================================================== Kimi
class KimiBehavior(TowerBehavior):
    """Consecutive-hit bonus, Memory Storage, crystal bursts (U3) and Infinite Context Burst."""

    @staticmethod
    def memory_stacks(t):
        s = t.get_stats()
        if not s.has("memoryPer"):
            return 0
        return jint(min(s.p("memoryCap"), math.floor(t.get_kills() / s.p("memoryPer"))))

    def modify_attack(self, game, t, c):
        s = t.get_stats()
        if c.primary is None:
            return
        streak = jint(min(s.p("streakMax"), t.register_streak(c.primary.get_id()) * s.p("streakStep")))
        c.extra_damage += streak + self.memory_stacks(t)
        c.pierce += jint(streak * s.p("pierceBonusPerStack", 0.0))

    def on_fire(self, game, t, c):
        s = t.get_stats()
        if not s.has("burstEvery") or c.primary is None:
            return
        if t.add_counter("attacks", 1) < s.p("burstEvery"):
            return
        t.set_counter("attacks", 0)
        h = HitSpec(s.p("burstDamage"), DamageType.MAGIC)
        h.mult_vs_fortified = s.hit.mult_vs_fortified
        at = c.primary.get_position()
        radius = s.p("burstSplash")
        game.get_combat().area_hit(at, radius, h, t, t.damage_multiplier(game), 9999, None)
        game.get_combat().emit(VisualEvent.explosion(at, radius, t.get_type().secondary_rgb))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        stacks = self.memory_stacks(t)
        full = HitSpec(stacks * a.p("damagePerStack"), DamageType.TRUE)
        half = HitSpec(full.damage * a.p("bossFraction"), DamageType.TRUE)
        lst = game.get_enemy_manager().get_enemies()
        i = 0
        while i < len(lst):
            e = lst[i]
            i += 1
            if stacks == 0:
                break
            if not e.is_alive() or e.is_stored() or (e.is_fortified() and a.p("hitsFortified", 0.0) <= 0):
                continue
            p = e.get_position()
            if p.x < 0 or p.y < 0 or p.x > WIDTH or p.y > HEIGHT:
                continue
            game.get_combat().apply_hit_simple(e, half if e.is_boss() else full, t, 1, 0)
        game.get_combat().emit(VisualEvent.banner("INFINITE CONTEXT BURST", t.get_type().primary_rgb, 1.2))
        return True


# ====================================================================== MiniMax
_CLONES, _SIG, _OVERCLOCK = "clones", "cloneSig", "overclock"


def _clone_stats(t, overclock):
    cs = t.get_stats().copy()
    if overclock:
        a = t.get_ability()
        cs.rate *= a.p("rateMult")
        cs.bounces = jint(jround(cs.bounces * a.p("bounceMult")))
    return cs


class MiniMaxBehavior(TowerBehavior):
    """Orbiting clones (U1/U3), synchronized barrages (U3) and Scale Factor Overclock."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if s.has("cloneCount"):
            self._maintain_clones(game, t, s)
        if s.has("barrageInterval") and t.add_counter("barrage", dt) >= s.p("barrageInterval"):
            self._barrage(game, t, s)

    @staticmethod
    def _maintain_clones(game, t, s):
        n = s.pi("cloneCount")
        ds = t.state().get(_CLONES)
        if ds is None or len(ds) != n:
            bigger = [None] * n
            if ds is not None:
                bigger[:min(len(ds), n)] = ds[:min(len(ds), n)]
            ds = bigger
            t.state()[_CLONES] = ds
        oc = t.has_self_buff(_OVERCLOCK)
        sig = t.get_tier() * 2 + (1 if oc else 0) + 1
        refresh = t.counter(_SIG) != sig
        cs = None
        for i in range(n):
            d = ds[i]
            if d is None or not d.is_alive():
                d = Drone.orbit(t, _clone_stats(t, oc), s.p("cloneOrbit"), math.pi * 2 * i / n)
                d.kind = "clone"
                d.rgb = t.get_type().secondary_rgb
                game.get_effects().add_drone(d)
                ds[i] = d
            elif refresh:
                if cs is None:
                    cs = _clone_stats(t, oc)
                d.stats = cs
        if refresh:
            t.set_counter(_SIG, sig)

    @staticmethod
    def _barrage(game, t, s):
        count = s.pi("barrageCount")
        targets = game.get_combat().acquire_targets(t, count)
        if not targets:
            t.set_counter("barrage", s.p("barrageInterval"))
            return
        t.set_counter("barrage", 0)
        oc = t.has_self_buff(_OVERCLOCK)
        bounce_mult = t.get_ability().p("bounceMult") if oc else 1.0
        for i in range(count):
            sh = Shot.of(game, t, t.get_position(), targets[i % len(targets)])
            sh.bounces = jint(jround(sh.bounces * bounce_mult))
            game.get_combat().fire(sh)
        game.get_combat().emit(VisualEvent.ability(t.get_position(), 60, t.get_type().primary_rgb))

    def modify_attack(self, game, t, c):
        if t.has_self_buff(_OVERCLOCK):
            c.bounces = jint(jround(c.bounces * t.get_ability().p("bounceMult")))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        t.add_self_buff(_OVERCLOCK, a.p("rateMult"), 1, a.p("duration"))
        game.get_combat().emit(VisualEvent.banner("SCALE FACTOR OVERCLOCK", t.get_type().primary_rgb, 1.2))
        return True
