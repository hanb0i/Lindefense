"""The single definition of "densest cluster": an enemy's density is the number of other live, on-track enemies
within RADIUS px of it; ties go to the enemy furthest along the track."""
from lindefense.enemy.grid import EnemyList

RADIUS = 60.0
_R2 = RADIUS * RADIUS


def density(e, population) -> int:
    n = 0
    p = e.get_position()
    if isinstance(population, EnemyList) and population.grid is not None:
        scan = population.grid.scan(p.x, p.y, RADIUS)
        o = scan.next()
        while o is not None:
            if o is not e and o.is_alive() and not o.is_stored() and o.get_position().dist_sq(p) <= _R2:
                n += 1
            o = scan.next()
        return n
    for o in population:
        if o is e or not o.is_alive() or o.is_stored():
            continue
        if o.get_position().dist_sq(p) <= _R2:
            n += 1
    return n


def densest(candidates, population):
    best = None
    best_n = -1
    for c in candidates:
        if not c.is_alive() or c.is_stored():
            continue
        n = density(c, population)
        if n > best_n or (n == best_n and c.get_remaining_distance() < best.get_remaining_distance()):
            best = c
            best_n = n
    return best


def densest_point(enemies):
    e = densest(enemies, enemies)
    return None if e is None else e.get_position()
