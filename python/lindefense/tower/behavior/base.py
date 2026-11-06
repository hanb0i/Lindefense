"""Per-tower-type behaviour: every hook is a no-op (or the data-driven default) so a subclass overrides only what its
tower's mechanics need. Behaviours are stateless singletons: per-tower memory lives in t.counter / t.state()."""
from lindefense.combat.visual_event import VisualEvent
from lindefense.tower.tower_type import BuffStat


class TowerBehavior:
    # ---- lifecycle
    def on_placed(self, game, t):
        pass

    def on_upgraded(self, game, t):
        pass

    def on_removed(self, game, t):
        pass

    def update(self, game, t, dt):
        pass

    # ---- attacking
    def attack(self, game, t):
        return game.get_combat().generic_attack(t)

    def modify_attack(self, game, t, c):
        pass

    def on_fire(self, game, t, c):
        pass

    def before_hit(self, game, t, c):
        pass

    def on_hit(self, game, t, c):
        pass

    def on_kill(self, game, t, e):
        pass

    def on_round_end(self, game, t):
        return t.get_stats().income_per_wave

    # ---- abilities
    def activate_ability(self, game, t, target):
        return False

    # ---- auras / targeting
    def aura_contribution(self, game, src, dst):
        s = src.get_stats()
        if s.aura_range <= 0 or dst is src:
            return
        if dst.get_position().dist(src.get_position()) > s.aura_range:
            return
        grant_aura(src, dst)

    def flat_range_bonus(self, t):
        return 0.0

    def allows_densest_cluster(self, t):
        return False

    def priority_comparator(self, t):
        """Optional sort key applied before the player's targeting priority (None = none)."""
        return None


def grant_aura(src, dst):
    s = src.get_stats()
    st = src.get_type()
    if s.aura_rate > 0:
        dst.add_aura_buff(BuffStat.RATE, st, s.aura_rate)
    if s.aura_damage > 0:
        dst.add_aura_buff(BuffStat.DAMAGE_FLAT, st, s.aura_damage)
    if s.aura_pierce > 0:
        dst.add_aura_buff(BuffStat.PIERCE_FLAT, st, s.aura_pierce)
    if s.aura_range_bonus > 0:
        dst.add_aura_buff(BuffStat.RANGE, st, s.aura_range_bonus)
    if s.aura_detection:
        dst.grant_detection()
    if s.aura_surveillance_immunity:
        dst.grant_surveillance_immunity()
    if s.aura_injection_immunity:
        dst.grant_injection_firewall()


def enemies_within(game, p, radius):
    """Alive, on-track enemies whose centre is within radius of p (any camo status), in list order."""
    out = []
    for e in game.get_enemy_manager().get_grid().near(p.x, p.y, radius, []):
        if e.is_alive() and not e.is_stored() and e.get_position().dist(p) <= radius:
            out.append(e)
    return out


def all_on_track(game):
    return [e for e in game.get_enemy_manager().get_enemies() if e.is_alive() and not e.is_stored()]


def stub_ability(game, t):
    game.get_combat().emit(VisualEvent.text(t.get_position(), t.get_ability().name + " (stub)", t.get_type().primary_rgb))
    return True


class GenericBehavior(TowerBehavior):
    pass
