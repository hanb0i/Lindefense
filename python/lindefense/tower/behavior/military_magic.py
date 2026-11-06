"""Military (DeepSeek, Copilot) and Magic (DALL-E, Sora, Suno) tower behaviours."""
import sys

from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.projectile import HitContext
from lindefense.combat.visual_event import VisualEvent
from lindefense.effects.effects import Barrage, TrackWalker, TrackZone
from lindefense.enemy.types import EnemyType
from lindefense.javacompat import jint
from lindefense.tower.behavior.base import TowerBehavior, enemies_within
from lindefense.tower.tower_type import BuffStat, Faction, Targeting

_MAX = sys.float_info.max


class DeepSeekBehavior(TowerBehavior):
    """Recursive Lock (consecutive-hit bonus, default Strongest) and the R1 Deep Reasoning Strike."""

    def on_upgraded(self, game, t):
        if t.get_stats().has("defaultStrongest") and t.counter("strongestApplied") == 0:
            t.set_counter("strongestApplied", 1)
            t.set_targeting(Targeting.STRONGEST)

    def modify_attack(self, game, t, c):
        s = t.get_stats()
        if not s.has("streakMax") or c.primary is None:
            return
        streak = t.register_streak(c.primary.get_id())
        c.extra_damage += min(s.p("streakMax"), streak * s.p("streakStep"))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        count = jint(a.p("count", 1))
        pool, bosses = [], []
        for e in game.get_enemy_manager().get_enemies():
            if not e.is_alive() or e.is_stored():
                continue
            (bosses if e.is_boss() else pool).append(e)
        boss_pct = a.p("bossDamagePct", 0.0)
        if not pool and (boss_pct <= 0 or not bosses):
            return False
        pool.sort(key=lambda e: -e.get_hp())
        combat = game.get_combat()
        rgb = t.get_type().primary_rgb
        for e in pool[:min(count, len(pool))]:
            combat.emit(VisualEvent.beam(t.get_position(), e.get_position(), rgb))
            game.get_enemy_manager().destroy_without_children(e, t)
        if boss_pct > 0:
            for b in bosses:
                pct = a.p("palantirDamagePct", boss_pct) if b.get_type() is EnemyType.PALANTIR else boss_pct
                combat.emit(VisualEvent.beam(t.get_position(), b.get_position(), rgb))
                combat.apply_hit_simple(b, HitSpec(b.get_max_hp() * pct, DamageType.TRUE), t, 1, 0)
        return True


AUTO_REFACTOR = "autoRefactor"


class CopilotBehavior(TowerBehavior):
    """Map-wide MILITARY bonus (U3), Task Scheduler drone (U2) and Enterprise Auto-Refactor."""
    AUTO_REFACTOR = AUTO_REFACTOR

    def aura_contribution(self, game, src, dst):
        super().aura_contribution(game, src, dst)
        s = src.get_stats()
        if dst is not src and dst.get_type().faction is Faction.MILITARY and s.has("globalMilitaryRate"):
            dst.add_aura_buff(BuffStat.RATE, src.get_type(), s.p("globalMilitaryRate"))
            dst.add_aura_buff(BuffStat.DAMAGE_FLAT, src.get_type(), s.p("globalMilitaryDamage"))

    def update(self, game, t, dt):
        s = t.get_stats()
        if not s.has("droneInterval") or not t.periodic("drone", s.p("droneInterval"), dt):
            return
        h = HitSpec(s.p("droneDamage"), DamageType.EXPLOSIVE)
        b = Barrage(t, h, 1, s.p("droneSplash"))
        b.aim = Barrage.DENSEST
        b.rgb = t.get_type().primary_rgb
        game.get_effects().fire(b)

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        all_towers = a.p("allTowers", 0.0) > 0
        for o in game.get_tower_manager().get_towers():
            if not all_towers and o.get_type().faction is not Faction.MILITARY:
                continue
            if a.has("rateMult"):
                o.add_self_buff(AUTO_REFACTOR, a.p("rateMult"), 1, a.p("duration"))
            else:
                o.add_timed_buff(BuffStat.RATE, t.get_type(), a.p("rateBonus"), a.p("duration"))
        return True


# ====================================================================== DALL-E
SAMPLE_STEP = 8.0


class Spot:
    __slots__ = ("route", "dist", "pos")

    def __init__(self, route, dist, pos):
        self.route, self.dist, self.pos = route, dist, pos


def track_spots_in_range(game, t, rng):
    out = []
    tp = t.get_position()
    for r in game.get_map().get_routes():
        ln = r.get_total_length()
        d = 0.0
        while d <= ln:
            p = r.position_at(d)
            if p.dist(tp) <= rng:
                out.append(Spot(r, d, p))
            d += SAMPLE_STEP
    return out


class DalleBehavior(TowerBehavior):
    """Paint zones, Living Illustration creatures, Masterpiece downgrades and Outpainting Expansion."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if t.periodic("paint", s.p("zoneInterval"), dt):
            self._paint_zone(game, t, s)
        if s.has("creatureInterval") and t.periodic("creatures", s.p("creatureInterval"), dt):
            self._spawn_creatures(game, t, s)
        if s.has("zoneArmorCrack"):
            self._downgrade_armored(game, t)

    def _paint_zone(self, game, t, s):
        rng = t.effective_range(game)
        lead = None
        for e in enemies_within(game, t.get_position(), rng):
            if lead is None or e.get_remaining_distance() < lead.get_remaining_distance():
                lead = e
        at = None
        if lead is not None:
            at = lead.get_position()
        else:
            best = None
            for sp in track_spots_in_range(game, t, rng):
                if best is None or sp.route.get_total_length() - sp.dist < best.route.get_total_length() - best.dist:
                    best = sp
            if best is not None:
                at = best.pos
        if at is None:
            return
        z = TrackZone(at, s.p("zoneRadius"), t)
        z.duration = s.p("zoneDuration")
        z.tick_interval = s.p("zoneTick")
        z.tick_hit = HitSpec(s.p("zoneDamage"), s.hit.type)
        z.armor_crack = s.has("zoneArmorCrack")
        z.kind = "paint"
        z.rgb = t.get_type().primary_rgb
        game.get_effects().add_zone(z)
        game.get_combat().emit(VisualEvent.ability(at, z.radius, z.rgb))

    def _spawn_creatures(self, game, t, s):
        spots = track_spots_in_range(game, t, t.effective_range(game))
        if not spots:
            return
        starts = []
        for sp in spots:
            cur = None
            for o in starts:
                if o.route is sp.route:
                    cur = o
            if cur is None:
                starts.append(sp)
            elif sp.dist > cur.dist:
                starts[starts.index(cur)] = sp
        n = s.pi("creatureCount")
        hit = HitSpec(s.p("creatureDamage"), s.hit.type)
        for i in range(n):
            st = starts[i % len(starts)]
            start = min(st.route.get_total_length(), st.dist + (i // len(starts)) * s.p("creatureSpacing"))
            w = TrackWalker(st.route, start, 0, s.p("creatureSpeed"), t, hit)
            w.pierce = s.pi("creaturePierce")
            w.detection = t.can_see_camo()
            w.kind = "creature"
            w.rgb = t.get_type().primary_rgb
            game.get_effects().add_walker(w)
        game.get_combat().emit(VisualEvent.ability(starts[0].pos, t.get_radius(), t.get_type().primary_rgb))

    def _downgrade_armored(self, game, t):
        zones = game.get_effects().zones_of(t, "paint")
        if not zones:
            return
        pool = []
        for z in zones:
            if not z.armor_crack:
                continue
            game.get_enemy_manager().get_grid().near(z.center.x, z.center.y, z.radius, pool)
            for e in pool:
                if not e.is_alive() or e.is_stored() or e.is_boss() or not e.is_fortified() or not z.contains(e):
                    continue
                e.strip_fortified()
                game.get_combat().emit(VisualEvent.text(e.get_position(), "Downgraded", t.get_type().primary_rgb))

    def activate_ability(self, game, t, target):
        if target is None:
            return False
        a = t.get_ability()
        tp = game.get_effects().nearest_track_point(target)
        if tp is None:
            return False
        z = TrackZone(tp.position, a.p("radius"), t)
        z.duration = a.p("duration")
        z.speed_cap = a.p("speedCap")
        if a.has("damage"):
            z.tick_interval = a.p("tick")
            z.tick_hit = HitSpec(a.p("damage"), DamageType.MAGIC)
        z.kind = "outpaint"
        z.rgb = t.get_type().secondary_rgb
        game.get_effects().add_zone(z)
        game.get_combat().emit(VisualEvent.ability(tp.position, z.radius, z.rgb))
        return True


class SoraBehavior(TowerBehavior):
    """Scene Rewind (U2), Time Loop zones (U3) and Cinematic Rewind."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if s.has("rewindInterval") and t.periodic("rewind", s.p("rewindInterval"), dt):
            self._scene_rewind(game, t, s)
        if s.has("loopZones"):
            self._ensure_loop_zones(game, t, s)

    def _scene_rewind(self, game, t, s):
        rng = t.effective_range(game)
        any_hit = False
        for e in enemies_within(game, t.get_position(), rng):
            if e.is_boss():
                continue
            e.apply_knockback_uncapped(s.p("rewindKnockback"))
            any_hit = True
        if any_hit:
            game.get_combat().emit(VisualEvent.ability(t.get_position(), rng, t.get_type().secondary_rgb))

    def _ensure_loop_zones(self, game, t, s):
        want = s.pi("loopZones")
        have = game.get_effects().zones_of(t, "loop")
        if len(have) >= want:
            return
        spots = track_spots_in_range(game, t, t.effective_range(game))
        if not spots:
            return
        chosen = [z.center for z in have]
        tp = t.get_position()
        while len(chosen) < want:
            best = None
            best_score = -1.0
            for sp in spots:
                if not chosen:
                    score = -sp.pos.dist(tp) + 1e6
                else:
                    score = _MAX
                    for c in chosen:
                        score = min(score, c.dist(sp.pos))
                if score > best_score:
                    best_score = score
                    best = sp
            chosen.append(best.pos)
            z = TrackZone(best.pos, s.p("loopRadius"), t)
            z.permanent = True
            z.tick_interval = s.p("loopTick")
            z.tick_hit = HitSpec(s.p("loopTickDamage"), s.hit.type)
            z.slow = s.p("loopSlow")
            z.kind = "loop"
            z.rgb = t.get_type().secondary_rgb
            game.get_effects().add_zone(z)
            game.get_combat().emit(VisualEvent.ability(best.pos, z.radius, z.rgb))

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        for e in list(game.get_enemy_manager().get_enemies()):
            if not e.is_alive() or e.is_stored():
                continue
            e.rewind(a.p("bossRewindSeconds") if e.is_boss() else a.p("rewindSeconds"))
        return True


class SunoBehavior(TowerBehavior):
    """Bass Drop (U1), Chord Strike (U2), Uncontrolled Symphony (U3) and the Symphonic Bass Drop ability."""

    def update(self, game, t, dt):
        s = t.get_stats()
        if s.has("bassInterval") and t.periodic("bass", s.p("bassInterval"), dt):
            self._bass_drop(game, t, s)
        if s.has("symphonyInterval") and t.periodic("symphony", s.p("symphonyInterval"), dt):
            self._symphony(game, t, s)

    def _bass_drop(self, game, t, s):
        radius = s.p("bassRadius")
        hit = enemies_within(game, t.get_position(), radius)
        if not hit:
            return
        spec = HitSpec(s.p("bassDamage"), s.hit.type)
        mult = t.damage_multiplier(game)
        for e in hit:
            c = HitContext(e, spec, t)
            c.mult = mult
            game.get_combat().apply_hit(c)
        game.get_combat().emit(VisualEvent.ability(t.get_position(), radius, t.get_type().primary_rgb))

    def _symphony(self, game, t, s):
        sees = t.can_see_camo()
        pool = [e for e in enemies_within(game, t.get_position(), t.effective_range(game)) if e.is_targetable_by(sees)]
        if not pool:
            return
        spec = HitSpec(s.p("symphonyDamage"), s.hit.type)
        for _ in range(s.pi("symphonyCount")):
            target = pool[game.get_rng().next_int(len(pool))]
            b = Barrage(t, spec, 1, s.p("symphonyRadius"))
            b.aim = Barrage.POINT
            b.point = target.get_position()
            b.rgb = t.get_type().secondary_rgb
            game.get_effects().fire(b)

    def modify_attack(self, game, t, c):
        s = t.get_stats()
        if not s.has("chordEvery"):
            return
        if jint(t.add_counter("chord", 1)) % s.pi("chordEvery") != 0:
            return
        c.edit_hit().damage = s.p("chordDamage")
        c.pierce += s.pi("chordPierce") - s.pierce
        c.tag = "chord"

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        mult = t.damage_multiplier(game)
        for e in list(game.get_enemy_manager().get_enemies()):
            if not e.is_alive() or e.is_stored():
                continue
            dmg = a.p("baseDamage", 0.0) + a.p("damagePerSpeed") * e.speed_multiplier()
            if e.is_boss():
                dmg = min(dmg, a.p("bossCap"))
            c = HitContext(e, HitSpec(dmg, t.get_stats().hit.type), t)
            c.mult = mult
            game.get_combat().apply_hit(c)
        game.get_combat().emit(VisualEvent.ability(t.get_position(), t.get_radius(), t.get_type().primary_rgb))
        return True
