"""Primary tower behaviours: Gemini, Claude, GPT and Zethos."""
import math

from lindefense.combat.combat import CRACKED_FORTIFIED_MULT
from lindefense.combat.hit_spec import DamageType, HitSpec
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import StatusKind
from lindefense.javacompat import jint
from lindefense.sim.vec import Vec
from lindefense.tower.behavior.base import TowerBehavior, enemies_within


class GeminiBehavior(TowerBehavior):
    """Argon Singularity: pull every enemy in the radius into a vortex, hold, then damage."""

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        caught = enemies_within(game, t.get_position(), a.p("radius"))
        if not caught:
            return False
        tp = t.get_position()
        centre = caught[0]
        for e in caught:
            if e.get_position().dist(tp) < centre.get_position().dist(tp):
                centre = e
        hold = a.p("holdTime")
        rgb = t.get_type().primary_rgb
        combat = game.get_combat()
        combat.emit(VisualEvent.ability(centre.get_position(), a.p("radius"), rgb))
        victims = list(caught)
        for e in victims:
            if not e.is_boss():
                e.hold(hold, centre.get_distance(), a.p("pullSpeed"))
            combat.emit(VisualEvent.beam(tp, e.get_position(), rgb))
        damage, boss_damage = a.p("damage"), a.p("bossDamage")

        def detonate():
            for e in victims:
                if not e.is_alive() or e.is_stored():
                    continue
                h = HitSpec(boss_damage if e.is_boss() else damage, DamageType.ENERGY)
                game.get_combat().apply_hit_simple(e, h, t, 1, 0)
                game.get_combat().emit(VisualEvent.explosion(e.get_position(), 30, rgb))

        game.get_effects().schedule(hold, detonate)
        return True


class ClaudeBehavior(TowerBehavior):
    """Opus Time-Lock: freeze non-bosses in the radius, slow bosses by the stated amount."""

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        rng = a.p("radius") if a.has("radius") else t.effective_range(game)
        for e in enemies_within(game, t.get_position(), rng):
            if e.is_boss():
                e.apply_exact_slow(a.p("bossSlow"), a.p("bossSlowTime"))
            else:
                e.apply_status(StatusKind.FREEZE, 1, a.p("freezeTime"))
        return True


_ANGLE, _BEAM_LEFT, _BEAM_ACC, _BEAM_TARGET, _MOON_CD = "moonAngle", "beamLeft", "beamAcc", "beamTarget", "moonCd"


class GptBehavior(TowerBehavior):
    """Two orbiting moons (U1) and the Astra Beam ability."""

    @staticmethod
    def moon_position(t, i):
        s = t.get_stats()
        if not s.has("moonCount"):
            return None
        ang = t.counter(_ANGLE) + math.pi * 2 * i / s.p("moonCount")
        return t.get_position().add(Vec(math.cos(ang), math.sin(ang)).scale(s.p("moonRadius")))

    @staticmethod
    def beam_active(t):
        return t.counter(_BEAM_LEFT) > 0

    def update(self, game, t, dt):
        self._update_moons(game, t, dt)
        self._update_beam(game, t, dt)

    def _update_moons(self, game, t, dt):
        s = t.get_stats()
        if not s.has("moonCount"):
            return
        t.add_counter(_ANGLE, s.p("moonOrbitSpeed") * dt)
        cd = t.state().setdefault(_MOON_CD, {})
        now = game.get_time()
        h = HitSpec(s.p("moonDamage"), DamageType.ENERGY)
        moons = s.pi("moonCount")
        size = s.p("moonSize")
        interval = s.p("moonInterval")
        sees = t.can_see_camo()
        combat = game.get_combat()
        grid = game.get_enemy_manager().get_grid()
        for i in range(moons):
            m = self.moon_position(t, i)
            scan = grid.scan(m.x, m.y, size)
            e = scan.next()
            while e is not None:
                if e.is_alive() and not e.is_stored() and e.is_targetable_by(sees) \
                        and e.get_position().within_dist(m, size + e.get_radius()):
                    key = i * 1_000_000 + e.get_id()
                    ready = cd.get(key)
                    if ready is None or ready <= now:
                        cd[key] = now + interval
                        combat.apply_hit_simple(e, h, t, 1, 0)
                        combat.emit(VisualEvent.hit(m, t.get_type().secondary_rgb))
                e = scan.next()
        for k in [k for k, r in cd.items() if r <= now]:
            del cd[k]

    def _update_beam(self, game, t, dt):
        if not self.beam_active(t):
            return
        a = t.get_ability()
        step = min(dt, t.counter(_BEAM_LEFT))
        t.add_counter(_BEAM_LEFT, -step)
        acc = t.add_counter(_BEAM_ACC, step)
        tick = a.p("tick")
        while acc >= tick - 1e-9:
            acc -= tick
            e = t.state().get(_BEAM_TARGET)
            if e is None or not e.is_alive() or e.is_stored():
                e = self._strongest(game, t)
            t.state()[_BEAM_TARGET] = e
            if e is None:
                break
            h = HitSpec(a.p("dps") * tick, DamageType.ENERGY)
            h.mult_vs_boss = a.p("bossMult")
            h.mult_vs_fortified = CRACKED_FORTIFIED_MULT
            game.get_combat().apply_hit_simple(e, h, t, 1, 0)
            game.get_combat().emit(VisualEvent.beam(t.get_position(), e.get_position(), t.get_type().primary_rgb))
        t.set_counter(_BEAM_ACC, acc)
        if t.counter(_BEAM_LEFT) <= 0:
            t.state().pop(_BEAM_TARGET, None)

    @staticmethod
    def _strongest(game, t):
        best = None
        sees = t.can_see_camo()
        for e in game.get_enemy_manager().get_enemies():
            if not e.is_targetable_by(sees):
                continue
            if (best is None or e.get_hp() > best.get_hp()
                    or (e.get_hp() == best.get_hp() and e.get_remaining_distance() < best.get_remaining_distance())):
                best = e
        return best

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        e = self._strongest(game, t)
        if e is None:
            return False
        t.set_counter(_BEAM_LEFT, a.p("duration"))
        t.set_counter(_BEAM_ACC, 0)
        t.state()[_BEAM_TARGET] = e
        game.get_combat().emit(VisualEvent.ability(t.get_position(), 40, t.get_type().primary_rgb))
        return True


COLLAPSE = "realityCollapse"


class ZethosBehavior(TowerBehavior):
    """Quantum projectiles: splash at every impact (T2+), bounces (T3+), never the same enemy twice; Reality Collapse."""
    COLLAPSE = COLLAPSE

    @staticmethod
    def is_collapsing(t):
        return t.has_self_buff(COLLAPSE)

    def flat_range_bonus(self, t):
        return t.get_ability().p("rangeBonus") if self.is_collapsing(t) else 0.0

    def modify_attack(self, game, t, c):
        s = t.get_stats()
        a = t.get_ability()
        splash = s.splash_radius
        splash_pct = s.p("splashPct", 0.0)
        bounce_pct = s.p("bouncePct", 0.0)
        bounces = s.bounces
        if self.is_collapsing(t):
            c.damage_mult *= a.p("damageMult")
            bounces = jint(a.p("bounces"))
            if splash <= 0 or splash_pct <= 0:
                splash = a.p("fallbackSplash")
                splash_pct = a.p("fallbackSplashPct")
            if bounce_pct <= 0:
                bounce_pct = a.p("fallbackBouncePct")
            c.tag = "collapse"
        c.bounces = bounces
        c.splash = splash
        c.on_impact = QuantumImpact(splash, splash_pct, bounce_pct)

    def activate_ability(self, game, t, target):
        a = t.get_ability()
        t.add_self_buff(COLLAPSE, a.p("rateMult"), 1, a.p("duration"))
        return True


class QuantumImpact:
    """Per-shot collision logic with the splash / bounce numbers frozen when the shot was fired."""

    def __init__(self, splash, splash_pct, bounce_pct):
        self.splash = splash
        self.splash_pct = splash_pct
        self.bounce_pct = bounce_pct

    def __call__(self, game, p, e):
        cb = game.get_combat()
        sh = p.get_shot()
        bounce_hit = p.handler_mark == 1
        p.handler_mark = 0
        scale = self.bounce_pct if bounce_hit else 1.0
        at = e.get_position()
        cb.projectile_hit(p, e, scale)
        if self.splash > 0 and self.splash_pct > 0:
            cb.area_hits(at, self.splash, sh.hit, sh.source, sh.damage_mult * scale * self.splash_pct, sh.extra_damage,
                         p.get_hit_ids(), p.get_hit_ids(), sh.detection, sh.buffed, p)
            cb.emit(VisualEvent.explosion(at, self.splash, sh.source.get_type().secondary_rgb))
        pierce_spent = p.get_pierce_left() <= 0 if bounce_hit else p.consume_pierce()
        if p.get_bounces_left() > 0:
            nxt = cb.nearest_enemy(at, sh.bounce_range, p.get_hit_ids(), sh.detection)
            if nxt is not None:
                p.consume_bounce()
                p.reset_travel()
                p.retarget(nxt)
                p.handler_mark = 1
                cb.emit(VisualEvent.chain(at, nxt.get_position(), sh.source.get_type().primary_rgb))
                return
        if not pierce_spent:
            p.retarget(None)
            return
        p.kill()
