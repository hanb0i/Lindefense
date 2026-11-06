"""Owns placed towers: placement rules, purchase, upgrade, selling, summons, auras and the per-tick attack loop;
plus the AbilityManager that enforces ability rules."""
import sys

from lindefense.combat.visual_event import VisualEvent
from lindefense.enemy.types import StatusKind
from lindefense.jenum import EnumSet
from lindefense.tower import catalog, shop
from lindefense.tower.tower import Tower
from lindefense.tower.tower_type import TowerType

AURA_REFRESH_TICKS = 6
FIELD_REFRESH_TICKS = 3
FIELD_STATUS_TIME = 0.3
MAX_HEROES_PER_GAME = 3


class TowerManager:
    MAX_HEROES_PER_GAME = MAX_HEROES_PER_GAME

    def __init__(self, game):
        self._game = game
        self._towers = []
        self._pending = []
        self._near = []
        self._tick_counter = 0

    def get_towers(self):
        return self._towers

    def get_player_towers(self):
        return [t for t in self._towers if not t.is_temporary()]

    def clear(self):
        self._towers.clear()
        self._pending.clear()

    # ---- placement
    def placement_problem(self, type_, p):
        d = catalog.get(type_)
        hero = self.hero_problem(type_)
        if hero is not None:
            return hero
        if not self._game.get_map().is_buildable(p, d.radius):
            return "Cannot build here"
        for t in self._towers:
            if t.is_temporary():
                continue
            if t.get_position().dist(p) < t.get_radius() + d.radius:
                return "Overlaps another tower"
        if self._game.get_cash() < shop.price_of(type_, self._game):
            return "Not enough cash"
        return None

    def can_place(self, type_, p):
        return self.placement_problem(type_, p) is None

    def hero_problem(self, type_):
        if not type_.is_hero():
            return None
        g = self._game
        if not g.is_hero_unlocked(type_):
            return "Unlock " + type_.display_name + " in the Hero Store"
        if g.is_hero_deployed(type_) or self.hero_placed(type_):
            return type_.display_name + " already deployed this match"
        if self.heroes_deployed_this_match() >= g.get_hero_limit():
            return "Hero limit reached (" + str(g.get_hero_limit()) + " per game)"
        return None

    def heroes_deployed_this_match(self):
        seen = set()
        for t in self._towers:
            if t.get_type().is_hero() and not t.is_temporary():
                seen.add(t.get_type())
        for t in self._pending:
            if t.get_type().is_hero() and not t.is_temporary():
                seen.add(t.get_type())
        for h in TowerType.heroes():
            if self._game.is_hero_deployed(h):
                seen.add(h)
        return len(seen)

    def hero_placed(self, type_):
        for t in self._towers:
            if t.get_type() is type_ and not t.is_temporary():
                return True
        for t in self._pending:
            if t.get_type() is type_ and not t.is_temporary():
                return True
        return False

    def place(self, type_, p):
        if not self.can_place(type_, p):
            return None
        g = self._game
        d = catalog.get(type_)
        price = shop.price_of(type_, g)
        if not g.spend_cash(price):
            return None
        t = Tower(d, p)
        self._towers.append(t)
        if type_.is_hero():
            g.mark_hero_deployed(type_)
        g.get_events().append(VisualEvent.ability(p, d.radius * 2, type_.primary_rgb))
        self.recompute_auras()
        t.get_behavior().on_placed(g, t)
        g.get_variance().on_tower_placed(t, price)
        return t

    def add_temporary(self, type_, tier, p, lifetime, owner):
        t = Tower(catalog.get(type_), p, tier, True, lifetime, owner)
        self._pending.append(t)
        self._game.get_events().append(VisualEvent.ability(p, 30, type_.secondary_rgb))
        return t

    def can_upgrade(self, t):
        return (t is not None and t.is_alive() and not t.is_temporary() and t.can_upgrade()
                and self._game.get_cash() >= shop.upgrade_cost(t, self._game))

    def upgrade(self, t):
        if not self.can_upgrade(t):
            return False
        g = self._game
        lst = t.next_upgrade().cost
        cost = shop.upgrade_cost(t, g)
        if not g.spend_cash(cost):
            return False
        g.get_variance().on_purchase(t, lst, cost)
        t.apply_upgrade(g)
        t.clear_surveilled()
        t.get_intrusion().clear()
        g.get_events().append(VisualEvent.ability(t.get_position(), 50, t.get_type().secondary_rgb))
        self.recompute_auras()
        return True

    def unlock_ability(self, t):
        if t is None or not t.is_alive() or not t.can_unlock_ability():
            return False
        g = self._game
        cost = shop.ability_unlock_cost(g)
        if not g.spend_cash(cost):
            return False
        g.get_variance().on_purchase(t, catalog.ABILITY_UNLOCK_COST, cost)
        t.unlock_ability()
        g.get_events().append(VisualEvent.ability(t.get_position(), 90, t.get_type().primary_rgb))
        g.get_events().append(VisualEvent.text(t.get_position(), t.get_ability().name + " UNLOCKED", t.get_type().primary_rgb))
        return True

    def sell(self, t):
        if t is None or not t.is_alive() or t.is_temporary():
            return 0
        g = self._game
        refund = shop.sell_value(t, g)
        g.get_variance().on_tower_sold(t)
        t.mark_removed()
        self._towers.remove(t)
        t.get_behavior().on_removed(g, t)
        g.get_effects().remove_owned_by(t)
        g.add_cash(refund, t.get_position())
        txt = t.get_type().display_name + " dismissed" if t.get_type().is_hero() else "+$" + str(refund)
        g.get_events().append(VisualEvent.text(t.get_position(), txt, 0xffd166))
        self.recompute_auras()
        return refund

    def tower_at(self, p):
        best = None
        best_d = sys.float_info.max
        for t in self._towers:
            if t.is_temporary():
                continue
            d = t.get_position().dist(p)
            if d <= t.get_radius() + 2 and d < best_d:
                best_d = d
                best = t
        return best

    # ---- auras
    def recompute_auras(self):
        reveal_all = False
        towers = self._towers
        for t in towers:
            t.reset_aura_bonuses()
            if t.get_stats().has("revealAllCamo"):
                reveal_all = True
        g = self._game
        for src in towers:
            beh = src.get_behavior()
            for dst in towers:
                if dst is not src:
                    beh.aura_contribution(g, src, dst)
        if reveal_all:
            for t in towers:
                t.grant_detection()

    # ---- tick
    def update(self, dt):
        if self._pending:
            self._towers.extend(self._pending)
            self._pending.clear()
        self._tick_counter += 1
        if self._tick_counter % AURA_REFRESH_TICKS == 0:
            self.recompute_auras()
        g = self._game
        combat = g.get_combat()
        field_tick = self._tick_counter % FIELD_REFRESH_TICKS == 0
        towers = self._towers
        i = 0
        while i < len(towers):
            t = towers[i]
            i += 1
            wants_attack = t.tick_timers(g, dt)
            if not t.is_alive():
                continue
            if t.is_offline():
                t.idle()
                continue
            t.get_behavior().update(g, t, dt)
            if field_tick:
                self._apply_enemy_field(t)
            if wants_attack:
                if not combat.attack(t):
                    t.idle()
        for i in range(len(towers) - 1, -1, -1):
            if not towers[i].is_alive():
                del towers[i]
        if self._pending:
            self._towers.extend(self._pending)
            self._pending.clear()

    def _apply_enemy_field(self, t):
        s = t.get_stats()
        if s.aura_enemy_slow <= 0 and s.field_mark_flat <= 0 and s.field_mark_pct <= 0:
            return
        r = s.field_radius if s.field_radius > 0 else t.effective_range(self._game)
        tp = t.get_position()
        pool = self._game.get_enemy_manager().get_grid().near(tp.x, tp.y, r, self._near)
        for e in pool:
            if not e.is_alive() or e.is_stored():
                continue
            if e.is_boss() and not s.field_affects_bosses:
                continue
            if e.get_position().exceeds_dist(tp, r + e.get_radius()):
                continue
            if s.aura_enemy_slow > 0:
                e.apply_status(StatusKind.SLOW, s.aura_enemy_slow, FIELD_STATUS_TIME)
            if s.field_mark_flat > 0:
                e.apply_status(StatusKind.MARKED_FLAT, s.field_mark_flat, FIELD_STATUS_TIME)
            if s.field_mark_pct > 0:
                e.apply_status(StatusKind.MARKED, s.field_mark_pct, FIELD_STATUS_TIME)


class AbilityManager:
    def __init__(self, game):
        self._game = game

    def can_activate(self, t):
        return (t is not None and t.is_alive() and not t.is_temporary() and t.get_ability() is not None
                and t.is_ability_ready())

    def activate(self, t, target=None, _explicit=False):
        """activate(t) for abilities that need no location; activate(t, point) for targeted ones."""
        if target is None and not _explicit:
            if t is not None and t.get_ability() is not None and t.get_ability().needs_target:
                return False
        if not self.can_activate(t):
            return False
        g = self._game
        a = t.get_ability()
        if a.needs_target and target is None:
            return False
        if not t.get_behavior().activate_ability(g, t, target if a.needs_target else None):
            return False
        t.start_ability_cooldown()
        cd = g.get_variance().ability_cooldown()
        if cd != 1:
            t.reduce_ability_cooldown(1 - cd)
        g.get_events().append(VisualEvent.ability(t.get_position(), max(40.0, min(300.0, t.effective_range(g))), t.get_type().primary_rgb))
        g.get_events().append(VisualEvent.text(t.get_position(), a.name + "!", t.get_type().primary_rgb))
        return True
