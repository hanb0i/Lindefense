"""The combat engine: target acquisition, attack execution per AttackKind, projectile movement/collision and the
single damage formula (apply_hit) used by every hit in the game.

Comparators are expressed as sort keys; Python's sort is stable like Java's, so orderings match.
"""
from lindefense.combat import clusters
from lindefense.combat.hit_spec import DamageType
from lindefense.combat.projectile import AttackContext, HitContext, Projectile, Shot
from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import StatusKind
from lindefense.map.path import Path
from lindefense.tower.stats import UNLIMITED_RANGE
from lindefense.tower.tower_type import AttackKind, Targeting

MAX_EVENTS_PER_TICK = 400
SONIC_LEAD_KNOCKBACK = 20.0
CERAMIC_MULT = 2.0
FROZEN_MULT = 2.0
CRACKED_FORTIFIED_MULT = 2.0


def _first(e):
    return e.get_remaining_distance()


def _last(e):
    return -e.get_remaining_distance()


def _strongest(e):
    return (-e.get_hp(), e.get_remaining_distance())


def _weakest(e):
    return (e.get_hp(), e.get_remaining_distance())


def key_for(targeting, tower_pos):
    """Sort key for a targeting priority (DENSEST_CLUSTER falls back to First here)."""
    if targeting is Targeting.LAST:
        return _last
    if targeting is Targeting.STRONGEST:
        return _strongest
    if targeting is Targeting.WEAKEST:
        return _weakest
    if targeting is Targeting.CLOSEST:
        return lambda e: e.get_position().dist_sq(tower_pos)
    return _first


def then(first, second):
    """Java Comparator.thenComparing for sort keys."""
    return lambda e: (first(e), second(e))


class Combat:
    SONIC_LEAD_KNOCKBACK = SONIC_LEAD_KNOCKBACK
    CERAMIC_MULT = CERAMIC_MULT
    FROZEN_MULT = FROZEN_MULT
    CRACKED_FORTIFIED_MULT = CRACKED_FORTIFIED_MULT

    def __init__(self, game):
        self._game = game
        self._projectiles = []
        self._new_projectiles = []
        self._near = []

    def get_projectiles(self):
        return self._projectiles

    # ------------------------------------------------------------------ targets
    def acquire_targets(self, t, n):
        g = self._game
        priority = t.get_behavior().priority_comparator(t)
        taunt = None if t.is_injection_immune() else g.get_injection().taunt_comparator()
        if taunt is not None:
            priority = taunt if priority is None else then(taunt, priority)
        return self.acquire_targets_from(t.get_position(), t.effective_range(g), t.can_see_camo(),
                                         t.get_stats().ignores_los, t.get_targeting(), n, priority)

    def acquire_targets_from(self, origin, rng, detection, ignore_los, targeting, n, priority):
        g = self._game
        gmap = g.get_map()
        candidates = []
        pool = g.get_enemy_manager().get_grid().near(origin.x, origin.y, rng, self._near)
        for e in pool:
            if not e.is_targetable_by(detection):
                continue
            if origin.exceeds_dist(e.get_position(), rng + e.get_radius()):
                continue
            if not ignore_los and not gmap.has_line_of_sight(origin, e.get_position()):
                continue
            candidates.append(e)
        if not candidates:
            return candidates
        if targeting is Targeting.DENSEST_CLUSTER:
            pop = g.get_enemy_manager().get_enemies()
            dens = {id(e): clusters.density(e, pop) for e in candidates}
            cmp = lambda e: (-dens[id(e)], e.get_remaining_distance())
        else:
            cmp = key_for(targeting, origin)
        if priority is not None:
            cmp = then(priority, cmp)
        if len(candidates) > 1:
            candidates.sort(key=cmp)
        if len(candidates) > n:
            del candidates[n:]
        return candidates

    @staticmethod
    def comparator_for(targeting, tower_pos):
        return key_for(targeting, tower_pos)

    # ------------------------------------------------------------------ attacks
    def attack(self, t) -> bool:
        return t.get_behavior().attack(self._game, t)

    def generic_attack(self, t) -> bool:
        s = t.get_stats()
        k = s.kind
        if k is AttackKind.PULSE:
            return self._pulse(t, s)
        if k not in (AttackKind.PROJECTILE, AttackKind.INSTANT, AttackKind.CHAIN):
            return False
        want = max(s.targets, s.projectiles_per_shot) if k is AttackKind.INSTANT else s.targets
        targets = self.acquire_targets(t, max(1, want))
        if not targets:
            return False
        c = self.new_attack_context(t, targets)
        t.get_behavior().modify_attack(self._game, t, c)
        if c.cancel or not c.targets:
            return False
        self.execute_attack(c, t.get_position(), t.can_see_camo(), True)
        t.set_last_target(c.targets[0])
        t.get_behavior().on_fire(self._game, t, c)
        t.on_attacked(self._game)
        return True

    def new_attack_context(self, t, targets):
        s = t.get_stats()
        c = AttackContext(t, s, targets)
        c.damage_mult = t.damage_multiplier(self._game)
        c.pierce = t.effective_pierce()
        c.bounces = s.bounces
        c.clones = s.clones
        c.splash = s.splash_radius
        c.speed = s.projectile_speed * t.projectile_speed_mult()
        return c

    def execute_attack(self, c, origin, detection, buffed):
        k = c.stats.kind
        if k is AttackKind.PROJECTILE:
            self._shoot(c, origin, detection, buffed)
        elif k is AttackKind.INSTANT or k is AttackKind.CHAIN:
            self._beam(c, origin, detection, buffed)

    def _shoot(self, c, origin, detection, buffed):
        shots = c.shots_per_target
        for target in c.targets:
            for i in range(shots):
                start = origin
                if shots > 1:
                    ang = (i - (shots - 1) / 2.0) * 0.35
                    d = target.get_position().sub(start).normalized()
                    from lindefense.sim.vec import Vec
                    perp = Vec(-d.y, d.x)
                    start = start.add(perp.scale(ang * 20))
                sh = Shot()
                sh.source = c.tower
                sh.stats = c.stats
                sh.hit = c.hit()
                sh.start = start
                sh.target = target
                sh.damage_mult = c.damage_mult
                sh.extra_damage = c.extra_damage
                sh.pierce = c.pierce
                sh.bounces = c.bounces
                sh.bounce_range = c.stats.bounce_range
                sh.bounce_speed_gain = c.stats.p("bounceSpeedGain", 0.0)
                sh.clones = c.clones
                sh.splash = c.splash
                sh.speed = c.speed
                sh.detection = detection
                sh.rgb = c.tower.get_type().primary_rgb
                sh.tag = c.tag
                sh.buffed = buffed
                sh.on_impact = c.on_impact
                self._new_projectiles.append(Projectile(sh))

    def _beam(self, c, origin, detection, buffed):
        g = self._game
        s = c.stats
        rgb = c.tower.get_type().primary_rgb
        chain_only = s.kind is AttackKind.CHAIN
        beams = 1 if chain_only else max(max(s.targets, c.shots_per_target), len(c.targets))
        hit_already = set()
        for b in range(beams):
            target = c.targets[b % len(c.targets)]
            if not target.is_alive():
                continue
            last = target
            if not chain_only and c.pierce > 1:
                direction = target.get_position().sub(origin).normalized()
                rng = UNLIMITED_RANGE if s.has_unlimited_range() else c.tower.effective_range(g)
                end = origin.add(direction.scale(rng))
                on_line = []
                pool = g.get_enemy_manager().get_grid().box(min(origin.x, end.x) - 4, min(origin.y, end.y) - 4,
                                                             max(origin.x, end.x) + 4, max(origin.y, end.y) + 4, self._near)
                for e in pool:
                    if not e.is_targetable_by(detection):
                        continue
                    if Path.point_segment_distance(e.get_position(), origin, end) <= e.get_radius() + 4:
                        on_line.append(e)
                on_line.sort(key=lambda e: e.get_position().dist_sq(origin))
                hits = 0
                for e in on_line:
                    if hits >= c.pierce:
                        break
                    hits += 1
                    self._beam_hit(c, e, buffed, detection)
                    hit_already.add(e.get_id())
                self.emit(VisualEvent.beam(origin, end, rgb))
            else:
                self._beam_hit(c, target, buffed, detection)
                hit_already.add(target.get_id())
                self.emit(VisualEvent.chain(origin, target.get_position(), rgb) if chain_only
                          else VisualEvent.beam(origin, target.get_position(), rgb))
            if s.chain_hops > 0:
                cur = last
                for _ in range(s.chain_hops):
                    nxt = self.nearest_enemy(cur.get_position(), s.chain_range, hit_already, detection)
                    if nxt is None:
                        break
                    self.emit(VisualEvent.chain(cur.get_position(), nxt.get_position(), c.tower.get_type().secondary_rgb))
                    self._beam_hit(c, nxt, buffed, detection)
                    hit_already.add(nxt.get_id())
                    cur = nxt

    def _beam_hit(self, c, e, buffed, detection):
        h = HitContext(e, c.hit(), c.tower)
        h.mult = c.damage_mult
        h.extra = c.extra_damage
        h.from_attack = buffed
        h.detection = detection
        h.tag = c.tag
        self.apply_hit(h)

    def _pulse(self, t, s):
        g = self._game
        rng = t.effective_range(g)
        tp = t.get_position()
        in_range = []
        sees = t.can_see_camo()
        pool = g.get_enemy_manager().get_grid().near(tp.x, tp.y, rng, self._near)
        for e in pool:
            if not e.is_targetable_by(sees):
                continue
            if tp.within_dist(e.get_position(), rng + e.get_radius()):
                in_range.append(e)
        if not in_range:
            return False
        in_range.sort(key=key_for(t.get_targeting(), tp))
        c = self.new_attack_context(t, in_range)
        t.get_behavior().modify_attack(g, t, c)
        if c.cancel:
            return False
        n = 0
        for e in c.targets:
            if n >= c.pierce:
                break
            n += 1
            self._beam_hit(c, e, True, sees)
        self.emit(VisualEvent.ability(tp, rng, t.get_type().primary_rgb))
        t.set_last_target(c.targets[0])
        t.get_behavior().on_fire(g, t, c)
        t.on_attacked(g)
        return True

    def nearest_enemy(self, p, radius, exclude, sees_camo):
        best = None
        best_d = radius * radius
        pool = self._game.get_enemy_manager().get_grid().near(p.x, p.y, radius, self._near)
        for e in pool:
            d = e.get_position().dist_sq(p)
            if not (d <= best_d):
                continue
            if not e.is_targetable_by(sees_camo):
                continue
            if exclude is not None and e.get_id() in exclude:
                continue
            best_d = d
            best = e
        return best

    # ------------------------------------------------------------------ projectiles
    def add_projectile(self, p):
        self._new_projectiles.append(p)

    def fire(self, shot):
        p = Projectile(shot)
        self._new_projectiles.append(p)
        return p

    def update_projectiles(self, dt):
        projectiles = self._projectiles
        if self._new_projectiles:
            projectiles.extend(self._new_projectiles)
            self._new_projectiles.clear()
        grid = self._game.get_enemy_manager().get_grid()
        i = 0
        while i < len(projectiles):
            p = projectiles[i]
            i += 1
            if not p.move(dt):
                continue
            sees = p.has_detection()
            pp = p.get_position()
            psize = p.get_size()
            hit_ids = p.get_hit_ids()
            scan = grid.scan(pp.x, pp.y, psize)
            e = scan.next()
            while e is not None and p.is_alive():
                r = e.get_radius() + psize
                if e.get_position().dist_sq(p.get_position()) <= r * r:
                    if e.is_targetable_by(sees) and e.get_id() not in hit_ids:
                        self._on_projectile_hit(p, e)
                e = scan.next()
        for i in range(len(projectiles) - 1, -1, -1):
            if not projectiles[i].is_alive():
                projectiles[i] = projectiles[-1]
                projectiles.pop()
        if self._new_projectiles:
            projectiles.extend(self._new_projectiles)
            self._new_projectiles.clear()

    def _on_projectile_hit(self, p, e):
        g = self._game
        sh = p.get_shot()
        t = sh.source
        p.get_hit_ids().add(e.get_id())
        if sh.on_impact is not None:
            sh.on_impact(g, p, e)
            return
        if sh.splash > 0:
            cap = sh.pierce if sh.pierce > 1 else 999
            self.area_hit_full(p.get_position(), sh.splash, sh.hit, t, sh.damage_mult, sh.extra_damage, cap, None,
                               sh.detection, sh.buffed, p)
            self.emit(VisualEvent.explosion(p.get_position(), sh.splash, t.get_type().primary_rgb))
            p.kill()
            return
        h = HitContext(e, sh.hit, t)
        h.mult = sh.damage_mult
        h.extra = sh.extra_damage
        h.from_attack = sh.buffed
        h.detection = sh.detection
        h.projectile = p
        h.tag = sh.tag
        self.apply_hit(h)
        self.emit(VisualEvent.hit(e.get_position(), t.get_type().primary_rgb))
        if p.can_clone():
            p.consume_clone()
            exclude = set(p.get_hit_ids())
            for _ in range(1, sh.clones):
                nt = self.nearest_enemy(e.get_position(), sh.bounce_range, exclude, sh.detection)
                if nt is None:
                    break
                exclude.add(nt.get_id())
                cs = sh.copy()
                cs.start = e.get_position()
                cs.target = nt
                cs.clones = 0
                cs.rgb = t.get_type().secondary_rgb
                clone = Projectile(cs)
                clone.get_hit_ids().add(e.get_id())
                self._new_projectiles.append(clone)
        if p.get_bounces_left() > 0:
            nxt = self.nearest_enemy(e.get_position(), sh.bounce_range, p.get_hit_ids(), sh.detection)
            if nxt is not None:
                p.consume_bounce()
                p.retarget(nxt)
                return
        if p.consume_pierce():
            p.kill()

    def projectile_hit(self, p, e, scale):
        sh = p.get_shot()
        h = HitContext(e, sh.hit, sh.source)
        h.mult = sh.damage_mult * scale
        h.extra = sh.extra_damage
        h.from_attack = sh.buffed
        h.detection = sh.detection
        h.projectile = p
        h.tag = sh.tag
        self.apply_hit(h)
        self.emit(VisualEvent.hit(e.get_position(), sh.rgb))
        return h

    def _in_area(self, center, radius, exclude):
        in_range = []
        pool = self._game.get_enemy_manager().get_grid().near(center.x, center.y, radius, self._near)
        for e in pool:
            if not e.is_alive() or e.is_stored():
                continue
            if not e.get_position().within_dist(center, radius + e.get_radius()):
                continue
            if exclude is not None and e.get_id() in exclude:
                continue
            in_range.append(e)
        in_range.sort(key=lambda e: e.get_position().dist_sq(center))
        return in_range

    def area_hits(self, center, radius, hit, source, mult, extra, exclude, record, detection, from_attack, via):
        out = []
        for e in self._in_area(center, radius, exclude):
            if record is not None:
                record.add(e.get_id())
            h = HitContext(e, hit, source)
            h.mult = mult
            h.extra = extra
            h.from_attack = from_attack
            h.detection = detection
            h.projectile = via
            self.apply_hit(h)
            out.append(h)
        return out

    def area_hit(self, center, radius, hit, source, mult, max_targets, exclude):
        """Ability-style area hit (no attack buffs); detection from the source tower."""
        return self.area_hit_full(center, radius, hit, source, mult, 0.0, max_targets, exclude,
                                  source is None or source.can_see_camo(), False, None)

    def area_hit_full(self, center, radius, hit, source, mult, extra, max_targets, exclude, detection, from_attack, via):
        n = 0
        for e in self._in_area(center, radius, exclude):
            if n >= max_targets:
                break
            h = HitContext(e, hit, source)
            h.mult = mult
            h.extra = extra
            h.from_attack = from_attack
            h.detection = detection
            h.projectile = via
            self.apply_hit(h)
            if not h.immune:
                n += 1
        return n

    # ------------------------------------------------------------------ damage formula
    def apply_hit_simple(self, e, hit, source, mult, extra):
        h = HitContext(e, hit, source)
        h.mult = mult
        h.extra = extra
        return self.apply_hit(h)

    def apply_hit(self, c) -> float:
        e = c.target
        if e is None or not e.is_alive() or e.is_stored():
            return 0.0
        g = self._game
        src = c.source
        if src is not None:
            src.get_behavior().before_hit(g, src, c)
        h = c.hit()
        type_ = h.type
        is_true = type_ is DamageType.TRUE
        cracked = e.is_armor_cracked()
        immune = False
        if not is_true:
            if type_ is DamageType.SHARP and e.is_lead_type() and not cracked and not h.ignores_resistance:
                immune = True
            if type_ is DamageType.EXPLOSIVE and e.is_camo() and not c.detection and not e.is_revealed():
                immune = True
        c.immune = immune
        dmg = 0.0
        if not immune:
            et = e.get_type()
            is_boss = e.is_boss()
            is_fort = e.is_fortified()
            is_lead = e.is_lead_type()
            is_cer = e.is_ceramic_type()
            base = h.damage + c.extra
            if c.from_attack and src is not None:
                base += src.flat_damage_buff()
            if is_boss:
                base += h.flat_vs_boss
            if is_fort:
                base += h.flat_vs_fortified
            if is_lead:
                base += h.flat_vs_lead
            if is_cer:
                base += h.flat_vs_ceramic
            bonus = 1.0
            if is_boss:
                bonus += h.bonus_vs_boss
            if is_fort:
                bonus += h.bonus_vs_fortified
            else:
                bonus += h.bonus_vs_non_fortified
            if et.is_complex():
                bonus += h.bonus_vs_complex
            if et.is_fast():
                bonus += h.bonus_vs_fast
            if et.has_children():
                bonus += h.bonus_vs_splitters
            m = max(0.1, bonus)
            if not is_true:
                if is_cer and (type_.is_blunt_like() or type_ is DamageType.SONIC):
                    m *= CERAMIC_MULT
                if is_cer:
                    m *= h.mult_vs_ceramic
                if is_lead:
                    m *= h.mult_vs_lead
                if is_fort:
                    m *= h.mult_vs_fortified
                    if cracked:
                        m *= CRACKED_FORTIFIED_MULT
                if is_boss:
                    m *= h.mult_vs_boss
                    if src is not None:
                        m *= 1 + src.boss_damage_buff()
                if et.is_sorting_algorithm() or et.is_linked_list():
                    m *= h.mult_vs_sorting_and_lists
                if et.base_hp >= 5:
                    m *= h.mult_vs_high_hp
                if e.is_frozen():
                    m *= FROZEN_MULT
            dmg = base * c.mult * m
            if not is_true:
                armor = e.effective_armor() * (1 - h.armor_pierce)
                dmg *= (1 - max(0.0, min(0.95, armor)))
                weak = et.get_weak_hit_threshold()
                if weak > 0 and h.damage < weak:
                    dmg *= 0.5
            if e.is_shielded(g.get_tick()):
                dmg *= 0.5
            if not is_true:
                dmg *= 1 + e.get_marked_bonus()
                if dmg > 0:
                    dmg += e.get_marked_flat()
            if h.pct_max_hp > 0:
                dmg += min(h.pct_cap, h.pct_max_hp * e.get_max_hp())
            dmg = dmg * c.final_mult + c.final_flat
            dmg *= g.get_variance().damage_against(e)
        dealt = 0.0
        if not immune and dmg > 0:
            dealt = e.take_damage(dmg, g.get_time())
            if src is not None:
                e.set_last_hit_by(src)
                src.add_damage_dealt(dealt)
        elif immune and src is not None and g.get_rng().chance(0.05):
            self.emit(VisualEvent.text(e.get_position(), "Immune", 0xaaaaaa))
        c.dealt = dealt
        if not immune:
            self._apply_effects(c, e, h, type_)
        if src is not None:
            src.get_behavior().on_hit(g, src, c)
        return dealt

    def _apply_effects(self, c, e, h, type_):
        g = self._game
        src = c.source
        if h.slow_fraction > 0:
            e.apply_status(StatusKind.SLOW, h.slow_fraction, h.slow_duration)
        is_boss = e.is_boss()
        stun = h.boss_stun_duration if is_boss else h.stun_duration
        if stun > 0:
            e.apply_status(StatusKind.STUN, 1, stun, True)
        kb = h.boss_knockback if is_boss else h.knockback
        if not is_boss:
            if h.knockback_vs_fast > 0 and e.is_fast_for_knockback():
                kb += h.knockback_vs_fast
            if e.is_lead_type():
                kb += h.knockback_vs_lead
                if type_ is DamageType.SONIC:
                    kb += SONIC_LEAD_KNOCKBACK
        if kb > 0:
            if h.uncapped_knockback:
                e.apply_knockback_uncapped(kb)
            else:
                e.apply_knockback(kb, g.get_time())
        if h.armor_break > 0 and h.armor_break_duration > 0:
            e.apply_status(StatusKind.ARMOR_CRACK, 1, h.armor_break_duration)
        if h.mark_bonus > 0:
            e.apply_status(StatusKind.MARKED, h.mark_bonus, h.mark_duration)
        if h.mark_flat > 0:
            e.apply_status(StatusKind.MARKED_FLAT, h.mark_flat, h.mark_duration)
        if h.disrupt_duration > 0:
            e.apply_status(StatusKind.DISRUPTED, 1, h.disrupt_duration)
        if h.dot_dps > 0:
            e.apply_burn(h.dot_dps, h.dot_duration, src)
        if h.strips_fortified and not is_boss and e.is_fortified():
            e.strip_fortified()
            self.emit(VisualEvent.text(e.get_position(), "Stripped!", 0xd9c6ff))
        if h.strips_camo_regrow and e.strip_camo_regrow():
            self.emit(VisualEvent.text(e.get_position(), "Revealed", 0xb9a8ff))

    def apply_map_damage(self, e, amount):
        if e is None or not e.is_alive() or e.is_stored():
            return 0.0
        dealt = e.take_damage(amount, self._game.get_time())
        e.set_last_hit_by(None)
        self.emit(VisualEvent.hit(e.get_position(), 0xffffff))
        return dealt

    def emit(self, ev):
        events = self._game.get_events()
        if len(events) < MAX_EVENTS_PER_TICK:
            events.append(ev)

    def clear(self):
        self._projectiles.clear()
        self._new_projectiles.clear()
