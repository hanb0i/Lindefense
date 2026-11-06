"""Hero Store hero behaviours (18 heroes) and their shared impact handlers / planting helpers."""
import math
import sys

from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.visual_event import VisualEvent
from lindefense.effects.effects import Barrage, Mine, TrackZone
from lindefense.enemy.types import StatusKind
from lindefense.javacompat import jint, jround
from lindefense.map.path import Path
from lindefense.sim.vec import Vec
from lindefense.tower.behavior.base import TowerBehavior, all_on_track
from lindefense.tower.tower_type import BuffStat

_MAX = sys.float_info.max


# ====================================================================== shared helpers
def straight_pierce(game, p, e):
    """Homes until the first hit, then flies straight, damaging each enemy once until pierce is spent."""
    game.get_combat().projectile_hit(p, e, 1)
    if p.consume_pierce():
        p.kill()
    else:
        p.retarget(None)


def plant(game, t, hit, spacing, kind):
    """Plants one device on a route's centre line inside the tower's range, clear of the existing ones."""
    rng = t.effective_range(game)
    tp = t.get_position()
    existing = game.get_effects().mines_of(t, kind)
    best = None
    best_score = -1.0
    for r in game.get_map().get_routes():
        d = 0.0
        ln = r.get_total_length()
        while d <= ln:
            q = r.position_at(d)
            d += 16
            if q.dist(tp) > rng:
                continue
            nearest = _MAX
            for m in existing:
                nearest = min(nearest, m.position.dist(q))
            if nearest < spacing:
                continue
            score = 1e6 if nearest == _MAX else nearest
            if score > best_score:
                best_score = score
                best = q
    if best is None:
        return None
    m = Mine(t, best, hit)
    m.kind = kind
    m.rgb = t.get_type().primary_rgb
    return m


# ====================================================================== 1. Lobber Luis
def _cluster_impact(game, p, e):
    sh = p.get_shot()
    s = sh.stats
    combat = game.get_combat()
    combat.area_hit_full(p.get_position(), sh.splash, sh.hit, sh.source, sh.damage_mult, sh.extra_damage,
                         sh.pierce if sh.pierce > 1 else 999, None, sh.detection, sh.buffed, p)
    combat.emit(VisualEvent.explosion(p.get_position(), sh.splash, sh.rgb))
    p.kill()
    bombs = s.pi("clusterBombs", 0)
    if bombs <= 0:
        return
    radius = s.p("clusterSplash")
    spread = sh.splash * 0.8
    sub = sh.hit.copy()
    sub.damage = s.p("clusterDamage")
    at = p.get_position()
    for i in range(bombs):
        ang = math.pi * 2 * i / bombs + 0.4
        spot = Vec(at.x + math.cos(ang) * spread, at.y + math.sin(ang) * spread)

        def land(spot=spot):
            game.get_combat().area_hit(spot, radius, sub, sh.source, game.get_global_damage_multiplier(), 9999, None)
            game.get_combat().emit(VisualEvent.explosion(spot, radius, sh.source.get_type().secondary_rgb))

        game.get_effects().schedule(0.12 + i * 0.05, land)


class LobberLuisBehavior(TowerBehavior):
    def modify_attack(self, game, t, c):
        s = t.get_stats()
        if s.pi("clusterBombs", 0) > 0:
            c.on_impact = _cluster_impact
        every = s.pi("orbitalEvery", 0)
        if every > 0 and (t.counter("shots") + 1) % every == 0:
            c.damage_mult *= s.p("orbitalMult")
            c.splash *= 1.35
            c.tag = "orbital"

    def on_fire(self, game, t, c):
        t.add_counter("shots", 1)
        if c.tag == "orbital" and c.primary is not None:
            game.get_combat().emit(VisualEvent.ability(c.primary.get_position(), t.get_stats().splash_radius * 1.6,
                                                       t.get_type().primary_rgb))


# ====================================================================== 2. Sage Aarav
class SageAaravBehavior(TowerBehavior):
    def update(self, game, t, dt):
        s = t.get_stats()
        interval = s.p("healInterval")
        combat = game.get_combat()
        if interval > 0 and t.periodic("healTimer", interval, dt):
            healed = game.restore_lives(jint(s.p("healAmount")))
            if healed > 0:
                combat.emit(VisualEvent.text(t.get_position(), "+" + str(healed) + " integrity", t.get_type().primary_rgb))
                combat.emit(VisualEvent.ability(t.get_position(), s.field_radius, t.get_type().primary_rgb))
        threshold = s.p("emergencyThreshold", 0.0)
        if threshold > 0 and t.counter("emergencyUsed") == 0:
            mx = game.get_max_lives()
            if 0 < game.get_lives() < mx * threshold:
                t.set_counter("emergencyUsed", 1)
                healed = game.restore_lives(jint(math.ceil(mx * s.p("emergencyRestore"))))
                combat.emit(VisualEvent.text(t.get_position(), "DIVINE RESTORATION +" + str(healed), 0xffe9a8))
                combat.emit(VisualEvent.ability(t.get_position(), s.field_radius * 1.5, 0xffe9a8))


# ====================================================================== 3. Iron Imraan
class IronImraanBehavior(TowerBehavior):
    def on_fire(self, game, t, c):
        s = t.get_stats()
        every = s.pi("smashEvery", 0)
        if every <= 0:
            return
        if t.add_counter("punches", 1) % every != 0:
            return
        smash = HitSpec(s.p("smashDamage"), s.hit.type)
        smash.knockback = s.hit.knockback
        radius = s.p("smashRadius")
        hits = game.get_combat().area_hits(t.get_position(), radius, smash, t, game.get_global_damage_multiplier(), 0.0,
                                           None, None, t.can_see_camo(), False, None)
        stun = s.p("smashStun", 0.0)
        if stun > 0:
            for h in hits:
                e = h.target
                if e is not None and e.is_alive() and not e.is_boss():
                    e.apply_status(StatusKind.STUN, 1, stun)
        game.get_combat().emit(VisualEvent.explosion(t.get_position(), radius, t.get_type().primary_rgb))


# ====================================================================== 4. Boom Sam
class BoomSamBehavior(TowerBehavior):
    def on_fire(self, game, t, c):
        s = t.get_stats()
        every = s.pi("nukeEvery", 0)
        if every <= 0:
            return
        if t.add_counter("throws", 1) % every != 0:
            return
        at = c.primary.get_position() if c.primary is not None else t.get_position()
        nuke = HitSpec(s.p("nukeDamage"), s.hit.type)
        radius = s.p("nukeRadius")

        def boom():
            game.get_combat().area_hit(at, radius, nuke, t, game.get_global_damage_multiplier(), 9999, None)
            game.get_combat().emit(VisualEvent.explosion(at, radius, 0xffd34d))
            game.get_combat().emit(VisualEvent.ability(at, radius * 1.2, t.get_type().primary_rgb))

        game.get_effects().schedule(0.25, boom)


# ====================================================================== 5. Chillstin
class ChillstinBehavior(TowerBehavior):
    def modify_attack(self, game, t, c):
        s = t.get_stats()
        shots = t.counter("shards") + 1
        freeze_every = s.pi("freezeEvery", 0)
        if freeze_every > 0 and shots % freeze_every == 0:
            c.tag = "freeze"
        burst_every = s.pi("burstEvery", 0)
        if burst_every > 0 and shots % burst_every == 0:
            c.tag = "burst"

    def on_hit(self, game, t, c):
        if c.tag != "freeze" or c.target is None or not c.target.is_alive():
            return
        s = t.get_stats()
        if c.target.is_boss():
            c.target.apply_status(StatusKind.SLOW, s.p("bossSlowPct"), s.hit.slow_duration)
        elif game.get_rng().chance(s.p("freezeChance")):
            c.target.apply_status(StatusKind.FREEZE, 1, s.p("freezeDuration"))
            game.get_combat().emit(VisualEvent.text(c.target.get_position(), "FROZEN", t.get_type().primary_rgb))

    def on_fire(self, game, t, c):
        t.add_counter("shards", 1)
        if c.tag != "burst" or c.primary is None:
            return
        s = t.get_stats()
        at = c.primary.get_position()
        radius = s.p("burstRadius")
        burst = HitSpec(s.hit.damage, s.hit.type)
        burst.slow_fraction = s.p("burstSlow")
        burst.slow_duration = s.p("burstSlowDuration")

        def go():
            hits = game.get_combat().area_hits(at, radius, burst, t, game.get_global_damage_multiplier(), 0.0,
                                               None, None, t.can_see_camo(), False, None)
            for h in hits:
                e = h.target
                if e is not None and e.is_alive() and e.is_boss():
                    e.apply_status(StatusKind.SLOW, s.p("bossSlowPct", 0.15), s.p("burstSlowDuration"))
            game.get_combat().emit(VisualEvent.explosion(at, radius, t.get_type().primary_rgb))

        game.get_effects().schedule(0.15, go)


# ====================================================================== 6. Kaiju Kai
_K_LEFT, _K_TICK, _K_BLAST, _K_DX, _K_DY = "beamLeft", "beamTick", "blastTimer", "beamDirX", "beamDirY"


class KaijuKaiBehavior(TowerBehavior):
    @staticmethod
    def _has_beam(s):
        return s.p("beamDuration", 0.0) > 0

    def attack(self, game, t):
        s = t.get_stats()
        if not self._has_beam(s):
            return game.get_combat().generic_attack(t)
        targets = game.get_combat().acquire_targets(t, 1)
        if not targets:
            return False
        d = targets[0].get_position().sub(t.get_position()).normalized()
        t.set_counter(_K_DX, d.x)
        t.set_counter(_K_DY, d.y)
        t.set_counter(_K_LEFT, s.p("beamDuration"))
        t.set_counter(_K_TICK, 0)
        t.set_last_target(targets[0])
        t.on_attacked(game)
        return True

    def update(self, game, t, dt):
        s = t.get_stats()
        left = t.counter(_K_LEFT)
        if left > 0:
            t.set_counter(_K_LEFT, max(0.0, left - dt))
            tick = s.p("beamTick", 0.25)
            if t.periodic(_K_TICK, tick, dt):
                self._burn(game, t, s)
        blast_interval = s.p("blastInterval", 0.0)
        if blast_interval > 0 and t.periodic(_K_BLAST, blast_interval, dt):
            blast = HitSpec(s.p("blastDamage"), s.hit.type)
            b = Barrage(t, blast, 1, s.p("blastRadius"))
            b.aim = Barrage.BOSS_ELSE_DENSEST
            b.rgb = t.get_type().primary_rgb
            at = game.get_effects().fire(b)
            if at is not None:
                game.get_combat().emit(VisualEvent.ability(at, s.p("blastRadius"), t.get_type().primary_rgb))

    @staticmethod
    def _burn(game, t, s):
        d = Vec(t.counter(_K_DX), t.counter(_K_DY))
        if d.length() < 0.5:
            return
        rng = t.effective_range(game)
        origin = t.get_position()
        end = origin.add(d.normalized().scale(rng))
        width = s.p("beamWidth", 24.0)
        hit = s.hit.copy()
        hit.damage = s.p("beamDamage")
        sees = t.can_see_camo()
        on_line = [e for e in game.get_enemy_manager().get_enemies()
                   if e.is_alive() and not e.is_stored() and e.is_targetable_by(sees)
                   and Path.point_segment_distance(e.get_position(), origin, end) <= width + e.get_radius()]
        mult = game.get_global_damage_multiplier()
        for e in on_line:
            game.get_combat().apply_hit_simple(e, hit, t, mult, 0)
        game.get_combat().emit(VisualEvent.beam(origin, end, t.get_type().primary_rgb))

    @staticmethod
    def is_beaming(t):
        return t.counter(_K_LEFT) > 0


# ====================================================================== 7. Abhi-Ace
class AbhiAceBehavior(TowerBehavior):
    def update(self, game, t, dt):
        s = t.get_stats()
        interval = s.p("bombInterval", 0.0)
        if interval <= 0 or not t.periodic("bombTimer", interval, dt):
            return
        bomb = HitSpec(s.p("bombDamage"), s.hit.type)
        b = Barrage(t, bomb, 1, s.p("bombRadius"))
        b.aim = Barrage.DENSEST
        b.rgb = t.get_type().primary_rgb
        at = game.get_effects().fire(b)
        if at is not None:
            game.get_combat().emit(VisualEvent.ability(at, s.p("bombRadius"), t.get_type().primary_rgb))


# ====================================================================== 8. Zippy Matt
class ZippyMattBehavior(TowerBehavior):
    def modify_attack(self, game, t, c):
        t.set_counter("hop", 0)
        every = t.get_stats().pi("burstEvery", 0)
        if every > 0 and (t.counter("arcs") + 1) % every == 0:
            c.tag = "burst"

    def before_hit(self, game, t, c):
        falloff = t.get_stats().p("chainFalloff", 1.0)
        if falloff >= 1.0 or not c.from_attack:
            return
        hop = jint(t.counter("hop"))
        c.final_mult *= math.pow(falloff, hop)
        t.set_counter("hop", hop + 1)

    def on_fire(self, game, t, c):
        t.add_counter("arcs", 1)
        if c.tag != "burst" or c.primary is None:
            return
        s = t.get_stats()
        at = c.primary.get_position()
        burst = HitSpec(s.p("burstDamage"), s.hit.type)
        radius = s.p("burstRadius")
        game.get_combat().area_hit(at, radius, burst, t, game.get_global_damage_multiplier(), 9999, None)
        game.get_combat().emit(VisualEvent.explosion(at, radius, t.get_type().primary_rgb))


# ====================================================================== 9. Sunny Joe
class SunnyJoeBehavior(TowerBehavior):
    def update(self, game, t, dt):
        s = t.get_stats()
        interval = s.p("incomeInterval")
        if interval > 0 and t.periodic("incomeTimer", interval, dt):
            game.add_cash(s.p("income"), t.get_position())
        bonus_interval = s.p("bonusInterval", 0.0)
        if bonus_interval > 0 and t.periodic("bonusTimer", bonus_interval, dt):
            game.add_cash(s.p("bonus"), t.get_position())


# ====================================================================== 10. Nik-Scope
class NikScopeBehavior(TowerBehavior):
    def before_hit(self, game, t, c):
        s = t.get_stats()
        chance = s.p("critChance", 0.0)
        if chance <= 0 or not c.from_attack:
            return
        if not game.get_rng().chance(chance):
            return
        c.final_mult *= s.p("critMult")
        c.tag = "crit"

    def on_hit(self, game, t, c):
        if c.tag == "crit" and c.target is not None:
            game.get_combat().emit(VisualEvent.text(c.target.get_position(), "CRIT", t.get_type().primary_rgb))


# ====================================================================== 11. Cami-Mine
class CamiMineBehavior(TowerBehavior):
    SPACING = 46.0

    def attack(self, game, t):
        s = t.get_stats()
        if len(game.get_effects().mines_of(t, "mine")) >= s.pi("maxMines"):
            return False
        m = plant(game, t, s.hit.copy(), self.SPACING, "mine")
        if m is None:
            return False
        m.blast_radius = s.p("mineRadius")
        m.trigger_radius = s.p("mineTrigger")
        m.arm_time = s.p("mineArm")
        secondary = s.p("secondaryChance", 0.0)
        if secondary > 0:
            m.secondary_chance = secondary
            m.secondary_radius = m.blast_radius
            m.secondary_hit = HitSpec(s.p("secondaryDamage"), s.hit.type)
        game.get_effects().add_mine(m)
        game.get_combat().emit(VisualEvent.text(m.position, "mine set", t.get_type().primary_rgb))
        t.on_attacked(game)
        return True


# ====================================================================== 12. Justin Time
class JustinTimeBehavior(TowerBehavior):
    def update(self, game, t, dt):
        s = t.get_stats()
        field_interval = s.p("fieldInterval", 0.0)
        if field_interval > 0 and t.periodic("fieldTimer", field_interval, dt):
            slow, boss_slow, duration = s.p("fieldSlow"), s.p("fieldBossSlow"), s.p("fieldDuration")
            for e in all_on_track(game):
                e.apply_status(StatusKind.SLOW, boss_slow if e.is_boss() else slow, duration)
            game.get_combat().emit(VisualEvent.text(t.get_position(), "TEMPORAL FIELD", t.get_type().primary_rgb))
            game.get_combat().emit(VisualEvent.ability(t.get_position(), t.effective_range(game) * 1.4, t.get_type().primary_rgb))
        freeze_interval = s.p("freezeInterval", 0.0)
        if freeze_interval > 0 and t.periodic("freezeTimer", freeze_interval, dt):
            duration, boss_slow = s.p("freezeDuration"), s.p("freezeBossSlow")
            for e in all_on_track(game):
                if e.is_boss():
                    e.apply_status(StatusKind.SLOW, boss_slow, duration)
                else:
                    e.apply_status(StatusKind.FREEZE, 1, duration)
            game.get_combat().emit(VisualEvent.text(t.get_position(), "TIME FREEZE", 0xffffff))


# ====================================================================== 13. Spear Hanbo
_RETURNING = 1


class SpearHanboBehavior(TowerBehavior):
    def modify_attack(self, game, t, c):
        c.on_impact = straight_pierce

    def update(self, game, t, dt):
        if t.get_stats().p("returns", 0.0) <= 0:
            return
        rng = t.effective_range(game)
        live = game.get_combat().get_projectiles()
        for p in list(live):
            if p.get_source() is not t or p.handler_mark == _RETURNING or not p.is_alive():
                continue
            if p.get_position().dist(t.get_position()) < rng:
                continue
            p.handler_mark = _RETURNING
            p.restore_pierce(t.get_stats().pierce)
            p.get_hit_ids().clear()
            p.aim_towards(t.get_position())


# ====================================================================== 14. Thorn Tuhin
class ThornTuhinBehavior(TowerBehavior):
    def update(self, game, t, dt):
        s = t.get_stats()
        interval = s.p("vineInterval", 0.0)
        if interval <= 0 or not t.periodic("vineTimer", interval, dt):
            return
        if len(game.get_effects().zones_of(t, "vines")) >= s.pi("maxVines", 2):
            return
        tp = game.get_effects().nearest_track_point(t.get_position())
        if tp is None or tp.position.dist(t.get_position()) > t.effective_range(game):
            return
        bite = HitSpec(s.p("vineDps") * 0.5, s.hit.type)
        z = TrackZone(tp.position, s.p("vineRadius"), t)
        z.kind = "vines"
        z.duration = s.p("vineDuration")
        z.tick_interval = 0.5
        z.tick_hit = bite
        z.slow = s.p("vineSlow", 0.0)
        z.rgb = t.get_type().primary_rgb
        game.get_effects().add_zone(z)
        game.get_combat().emit(VisualEvent.text(tp.position, "overgrowth", t.get_type().primary_rgb))


# ====================================================================== 15. Trapper Che
class TrapperCheBehavior(TowerBehavior):
    SPACING = 52.0

    def attack(self, game, t):
        s = t.get_stats()
        if len(game.get_effects().mines_of(t, "trap")) >= s.pi("maxTraps"):
            return False
        m = plant(game, t, s.hit.copy(), self.SPACING, "trap")
        if m is None:
            return False
        m.blast_radius = s.p("trapRadius")
        m.trigger_radius = s.p("trapTrigger")
        m.hold_duration = s.p("holdDuration")
        m.tether_dps = s.p("tetherDps", 0.0)
        secondary = s.p("secondaryChance", 0.0)
        if secondary > 0:
            m.secondary_chance = secondary
            m.secondary_radius = m.blast_radius * 1.3
            m.secondary_hit = HitSpec(s.p("secondaryDamage"), s.hit.type)
        game.get_effects().add_mine(m)
        game.get_combat().emit(VisualEvent.text(m.position, "trap set", t.get_type().primary_rgb))
        t.on_attacked(game)
        return True


# ====================================================================== 16. Blitz Arnav
class BlitzArnavBehavior(TowerBehavior):
    def modify_attack(self, game, t, c):
        s = t.get_stats()
        nxt = t.counter("bursts") + 1
        bullets = s.pi("bullets", s.targets)
        if c.targets and bullets > len(c.targets):
            c.shots_per_target = max(1, bullets // len(c.targets))
        suppress = s.pi("suppressEvery", 0)
        if suppress > 0 and nxt % suppress == 0:
            c.tag = "suppress"
        rocket = s.pi("rocketEvery", 0)
        if rocket > 0 and nxt % rocket == 0:
            c.tag = "rocket"

    def on_hit(self, game, t, c):
        if c.tag != "suppress" or c.target is None or not c.target.is_alive():
            return
        s = t.get_stats()
        c.target.apply_status(StatusKind.SLOW, s.p("suppressSlow"), s.p("suppressDuration"))

    def on_fire(self, game, t, c):
        t.add_counter("bursts", 1)
        if c.tag != "rocket" or c.primary is None:
            return
        s = t.get_stats()
        at = c.primary.get_position()
        rocket = HitSpec(s.p("rocketDamage"), DamageType.EXPLOSIVE)
        radius = s.p("rocketRadius")

        def fire():
            game.get_combat().area_hit(at, radius, rocket, t, game.get_global_damage_multiplier(), 9999, None)
            game.get_combat().emit(VisualEvent.explosion(at, radius, t.get_type().primary_rgb))

        game.get_effects().schedule(0.2, fire)


# ====================================================================== 17. Tanimbus
class TanimbusBehavior(TowerBehavior):
    @staticmethod
    def supported(game, t):
        if t.get_stats().p("singleTarget", 0.0) <= 0:
            return None
        rng = t.get_stats().aura_range
        best = None
        best_score = -1.0
        for o in game.get_tower_manager().get_towers():
            if o is t or o.is_temporary() or not o.is_alive():
                continue
            if o.get_position().dist(t.get_position()) > rng:
                continue
            score = o.get_invested_cost()
            if score > best_score:
                best_score = score
                best = o
        return best

    def aura_contribution(self, game, src, dst):
        s = src.get_stats()
        if s.p("singleTarget", 0.0) <= 0:
            super().aura_contribution(game, src, dst)
            return
        if dst is not self.supported(game, src):
            return
        dst.add_aura_buff(BuffStat.RATE, src.get_type(), s.p("buffRate"))

    def update(self, game, t, dt):
        s = t.get_stats()
        interval = s.p("rallyInterval", 0.0)
        if interval <= 0 or not t.periodic("rallyTimer", interval, dt):
            return
        rate, duration = s.p("rallyRate"), s.p("rallyDuration")
        for o in game.get_tower_manager().get_towers():
            if not o.is_alive() or o.is_temporary():
                continue
            o.add_timed_buff(BuffStat.RATE, t.get_type(), rate, duration)
        game.get_combat().emit(VisualEvent.text(t.get_position(), "BATTLEFIELD COMMAND", t.get_type().primary_rgb))


# ====================================================================== 18. Mr. Lindemann
HOLE = "blackhole"
_WARP = "warpTimer"


def _open_singularity(game, t, at):
    s = t.get_stats()
    if len(game.get_effects().zones_of(t, HOLE)) >= s.pi("maxHoles", 3):
        return
    tp = game.get_effects().nearest_track_point(at)
    if tp is None or tp.position.dist(at) > s.p("holeRadius") * 2:
        return
    tick = 0.25
    z = TrackZone(tp.position, s.p("holeRadius"), t)
    z.kind = HOLE
    z.duration = s.p("holeDuration")
    z.tick_interval = tick
    z.tick_hit = HitSpec(s.p("holeDps") * tick, DamageType.GRAVITY)
    z.slow = s.p("holeSlow", 0.0)
    z.detection = t.can_see_camo()
    z.rgb = t.get_type().primary_rgb
    game.get_effects().add_zone(z)


def _singularity_impact(game, p, e):
    sh = p.get_shot()
    t = sh.source
    game.get_combat().area_hit_full(p.get_position(), sh.splash, sh.hit, t, sh.damage_mult, sh.extra_damage, 999, None,
                                    sh.detection, sh.buffed, p)
    game.get_combat().emit(VisualEvent.explosion(p.get_position(), sh.splash, t.get_type().secondary_rgb))
    p.kill()
    _open_singularity(game, t, p.get_position())


class MrLindemannBehavior(TowerBehavior):
    HOLE = HOLE

    def modify_attack(self, game, t, c):
        c.on_impact = _singularity_impact

    def update(self, game, t, dt):
        s = t.get_stats()
        gc = s.p("gcThreshold", 0.0)
        if gc > 0:
            self._garbage_collect(game, t, gc)
        interval = s.p("warpInterval", 0.0)
        if interval <= 0:
            return
        timer = min(interval, t.counter(_WARP) + dt)
        t.set_counter(_WARP, timer)
        if timer < interval:
            return
        all_e = all_on_track(game)
        if not all_e:
            return
        t.set_counter(_WARP, 0)
        self._warp(game, t, all_e, s.p("warpSeconds"))

    @staticmethod
    def warp_remaining(t):
        return max(0.0, t.get_stats().p("warpInterval", 0.0) - t.counter(_WARP))

    @staticmethod
    def _warp(game, t, all_e, seconds):
        for e in all_e:
            if not e.is_alive() or e.is_stored():
                continue
            e.rewind(seconds)
            game.get_combat().emit(VisualEvent.hit(e.get_position(), t.get_type().secondary_rgb))
        game.get_combat().emit(VisualEvent.ability(t.get_position(), 320, t.get_type().primary_rgb))
        game.get_combat().emit(VisualEvent.text(t.get_position(), "SPACE WARP  -" + str(jround(seconds)) + "s", t.get_type().primary_rgb))

    @staticmethod
    def _garbage_collect(game, t, threshold):
        holes = game.get_effects().zones_of(t, HOLE)
        grid = game.get_enemy_manager().get_grid()
        for z in holes:
            scan = grid.scan(z.center.x, z.center.y, z.radius)
            e = scan.next()
            while e is not None:
                if (e.is_alive() and not e.is_stored() and not e.is_boss() and z.contains(e)
                        and e.get_hp() <= e.get_max_hp() * threshold
                        and not (e.is_camo() and not e.is_revealed() and not t.can_see_camo())):
                    game.get_combat().emit(VisualEvent.text(e.get_position(), "null", t.get_type().primary_rgb))
                    game.get_enemy_manager().destroy_without_children(e, t)
                e = scan.next()
