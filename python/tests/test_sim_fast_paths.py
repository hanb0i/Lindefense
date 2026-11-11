"""The simulation's hot-path shortcuts against the straightforward code they replace, bit for bit.

Each fast path (Path.position_at's bisect, NodeHazard.links_within's prefilter, the spatial grid's candidate lists,
the cached aura sums...) must give exactly what the plain version gives, or seeded runs drift from the Java build.
"""
import math
import random

from kit import buildable_near, force_place, mods, new_game, spawn_at
from lindefense.effects.effects import NodeHazard
from lindefense.enemy.grid import CELL, COLS, ROWS, _FULL_SCAN_CELLS
from lindefense.enemy.types import EnemyType, Modifier
from lindefense.map import maps
from lindefense.map.path import Path
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import BuffStat, TowerType


def _bits(x):
    return math.copysign(1.0, x), x.hex() if x == x else "nan"


def _ref_position_at(r, dist):
    """Path.position_at before the bisect: the original binary search and Vec.lerp."""
    wp, cum = r.get_waypoints(), r._cumulative
    if dist <= 0:
        return wp[0]
    if dist >= r.get_total_length():
        return wp[-1]
    lo, hi = 0, len(wp) - 2
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if cum[mid] <= dist:
            lo = mid
        else:
            hi = mid - 1
    seg = max(0, min(lo, len(wp) - 2))
    seg_len = cum[seg + 1] - cum[seg]
    t = 0 if seg_len <= 0 else (dist - cum[seg]) / seg_len
    return Vec.lerp(wp[seg], wp[seg + 1], t)


def test_position_at_matches_the_binary_search(check):
    rnd = random.Random(5)
    bad = 0
    n = 0
    for m in range(maps.MAP_COUNT):
        for r in maps.create(m).get_routes():
            total = r.get_total_length()
            ds = [0.0, -1.0, total, total + 1, math.nextafter(total, 0), 1e-300, float("nan")]
            ds += list(r._cumulative) + [math.nextafter(c, 0) for c in r._cumulative] + [math.nextafter(c, 1e9) for c in r._cumulative]
            ds += [rnd.uniform(0, total) for _ in range(400)]
            for d in ds:
                a, b = r.position_at(d), _ref_position_at(r, d)
                n += 1
                if _bits(a.x) != _bits(b.x) or _bits(a.y) != _bits(b.y):
                    bad += 1
    check(bad == 0, "position_at differs from the binary search in %d of %d cases" % (bad, n))


def _ref_point_segment_distance(p, a, b):
    abx, aby = b.x - a.x, b.y - a.y
    len2 = abx * abx + aby * aby
    t = 0 if len2 <= 0 else max(0.0, min(1.0, ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2))
    return Vec.lerp(a, b, t).dist(p)


def _random_points(rnd, n):
    pts = [Vec(rnd.uniform(-50, 1250), rnd.uniform(-50, 950)) for _ in range(n)]
    pts += [Vec(round(p.x), round(p.y)) for p in pts[:n // 4]]   # integer coordinates and repeats: degenerate links
    return pts


def test_point_segment_distance_unchanged(check):
    rnd = random.Random(6)
    pts = _random_points(rnd, 200)
    bad = 0
    for _ in range(4000):
        p, a, b = rnd.choice(pts), rnd.choice(pts), rnd.choice(pts)
        if _bits(Path.point_segment_distance(p, a, b)) != _bits(_ref_point_segment_distance(p, a, b)):
            bad += 1
    check(bad == 0, "point_segment_distance changed in %d cases" % bad)


def test_links_within_is_exactly_distance_to_links_le(check):
    rnd = random.Random(7)
    pts = _random_points(rnd, 120)
    bad = 0
    n = 0
    for _ in range(300):
        h = NodeHazard.network(None, [rnd.choice(pts) for _ in range(rnd.randint(2, 7))], None, 0.3, 0.0)
        if rnd.random() < 0.3:
            h.links.append((0, len(h.nodes) - 1))
        segs = h._link_segments()
        for _ in range(30):
            p = rnd.choice(pts) if rnd.random() < 0.2 else Vec(rnd.uniform(-50, 1250), rnd.uniform(-50, 950))
            d = h.distance_to_links(p)
            limits = [rnd.uniform(0, 60), 6.0 + rnd.choice((9, 13, 19)) * 0.5]
            if d < 1e300:
                limits += [d, math.nextafter(d, 0), math.nextafter(d, 1e9)]   # the rounding-sensitive band
            for lim in limits:
                n += 1
                want = d <= lim
                if h.links_within(p, lim) != want or h.links_within(p, lim, segs) != want:
                    bad += 1
    check(bad == 0, "links_within disagrees with distance_to_links <= limit in %d of %d cases" % (bad, n))


def test_polygon_edges_match_polygon_contains(check):
    rnd = random.Random(8)
    pts = _random_points(rnd, 60)
    bad = 0
    for _ in range(300):
        poly = [rnd.choice(pts) for _ in range(rnd.randint(3, 8))]
        edges = NodeHazard._polygon_edges(poly)
        for _ in range(40):
            p = rnd.choice(poly) if rnd.random() < 0.2 else Vec(rnd.uniform(-50, 1250), rnd.uniform(-50, 950))
            if NodeHazard._edges_contain(edges, p) != NodeHazard.polygon_contains(poly, p):
                bad += 1
    check(bad == 0, "edge-list polygon test differs in %d cases" % bad)


def _ref_collect(g, x0, y0, x1, y1, from_index, m):
    """The grid's original candidate gathering: cell range from floor(v / CELL), clamped; full list past half the grid."""
    def col(x):
        return 0 if x != x else max(0, min(COLS - 1, int(math.floor(x / CELL))))

    def row(y):
        return 0 if y != y else max(0, min(ROWS - 1, int(math.floor(y / CELL))))
    lst = g._list
    if from_index >= len(lst):
        return []
    c0, c1, r0, r1 = col(x0 - m), col(x1 + m), row(y0 - m), row(y1 + m)
    if (c1 - c0 + 1) * (r1 - r0 + 1) >= _FULL_SCAN_CELLS:
        return list(lst[from_index:])
    idxs = sorted(e.grid_index for c in range(c0, c1 + 1) for r in range(r0, r1 + 1) for e in g._cells[c][r]
                  if e.grid_index >= from_index)
    return [lst[i] for i in idxs]


def _crowded_game(seed):
    g = new_game(0, seed)
    rnd = random.Random(seed)
    routes = g.get_map().get_routes()
    kinds = [EnemyType.PRIMITIVE_VARIABLE, EnemyType.HEAP_SORT, EnemyType.TIMSORT, EnemyType.BELLARMINE_COLLEGE_PREP]
    for i in range(160):
        ri = rnd.randrange(len(routes))
        spawn_at(g, rnd.choice(kinds), mods(Modifier.FORTIFIED) if i % 5 == 0 else None, ri,
                 rnd.uniform(0, routes[ri].get_total_length()))
    for _ in range(20):   # move them so buckets are no longer in build order
        g.get_enemy_manager().update(g.DT * 3)
    return g, rnd


def test_grid_queries_keep_their_supersets(check):
    """near / box / Scan gather exactly what they used to; the centre-only queries hold every enemy whose centre
    passes, in list order; candidates() refills like a Scan."""
    g, rnd = _crowded_game(11)
    grid = g.get_enemy_manager().get_grid()
    enemies = g.get_enemy_manager().get_enemies()
    grid._ensure()
    bad = []
    for _ in range(300):
        cx, cy, reach = rnd.uniform(-60, 1260), rnd.uniform(-60, 960), rnd.choice((5.0, 8.0, 60.0, 90.0, 250.0, 700.0))
        x0, y0, x1, y1 = cx - reach, cy - reach, cx + reach, cy + reach
        ref = _ref_collect(grid, x0, y0, x1, y1, 0, grid._max_radius)
        if grid.near(cx, cy, reach, []) != ref or grid.box(x0, y0, x1, y1) != ref:
            bad.append("near/box at %r" % ((cx, cy, reach),))
        if grid.candidates(x0, y0, x1, y1, 0) != ref:
            bad.append("candidates at %r" % ((cx, cy, reach),))
        k = rnd.randrange(len(enemies) + 1)
        if grid.candidates(x0, y0, x1, y1, k) != _ref_collect(grid, x0, y0, x1, y1, k, grid._max_radius):
            bad.append("candidates from %d" % k)
        scan = grid.scan(cx, cy, reach)
        walked = list(iter(scan.next, None))
        if walked != ref:
            bad.append("scan at %r" % ((cx, cy, reach),))
        inside = [e for e in enemies if e.get_position().within_dist(Vec(cx, cy), reach)]
        for got in (grid.near_centers(cx, cy, reach, []), grid.candidates(x0, y0, x1, y1, 0, True),
                    list(iter(grid.scan_centers(cx, cy, reach).next, None))):
            if [e for e in got if e.get_position().within_dist(Vec(cx, cy), reach)] != inside:
                bad.append("centre query misses enemies at %r" % ((cx, cy, reach),))
            if [e.grid_index for e in got] != sorted(e.grid_index for e in got):
                bad.append("centre query out of list order")
    check(not bad, "; ".join(bad[:5]))


def test_aura_sum_cache_matches_a_fresh_sum(check):
    g = new_game(0)
    t = force_place(g, TowerType.GPT, buildable_near(g, Vec(300, 300), 300))
    rnd = random.Random(9)
    types = list(TowerType)
    bad = 0
    for i in range(400):
        stat = rnd.choice(list(BuffStat))
        if i % 97 == 0:
            t.reset_aura_bonuses()
        else:
            t.add_aura_buff(stat, rnd.choice(types), rnd.choice((0.05, 0.1, 0.15, 0.2, 0.25, 1 / 3.0, 0.7)))
        for st in BuffStat:
            row = t._aura_buffs[st.ordinal]
            s = 0.0
            for v in row:
                s += v
            if t.buff_total_uncapped(st) != s:
                bad += 1
    check(bad == 0, "cached aura sums differ from a left-to-right sum in %d cases" % bad)
