"""Waypoint routes. Positions are addressed by distance travelled, which keeps progress consistent when enemies are
slowed, knocked back or teleported."""
import math
import sys
from bisect import bisect_right

from lindefense.javacompat import jhypot
from lindefense.sim.vec import Vec

_new_vec = object.__new__
_set_x = Vec.x.__set__
_set_y = Vec.y.__set__


class Path:
    def __init__(self, name: str, *coords):
        """Path(name, x0, y0, x1, y1, ...) or Path(name, [Vec, ...])."""
        self._name = name
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)):
            self._waypoints = list(coords[0])
        else:
            self._waypoints = [Vec(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
        self._rebuild()

    def _rebuild(self):
        wp = self._waypoints
        n = len(wp)
        self._cumulative = [0.0] * n
        d = 0.0
        for i in range(1, n):
            d += wp[i].dist(wp[i - 1])
            self._cumulative[i] = d
        self._total_length = d
        self._segment_dir = [wp[i + 1].sub(wp[i]).normalized() for i in range(n - 1)]
        # per-segment start and delta (b.x - a.x, b.y - a.y) for position_at, the hottest call on a route
        self._seg_x = [wp[i].x for i in range(n - 1)]
        self._seg_y = [wp[i].y for i in range(n - 1)]
        self._seg_dx = [wp[i + 1].x - wp[i].x for i in range(n - 1)]
        self._seg_dy = [wp[i + 1].y - wp[i].y for i in range(n - 1)]

    def get_name(self) -> str:
        return self._name

    def get_total_length(self) -> float:
        return self._total_length

    def get_waypoints(self):
        return self._waypoints

    def get_start(self) -> Vec:
        return self._waypoints[0]

    def get_end(self) -> Vec:
        return self._waypoints[-1]

    def position_at(self, dist: float) -> Vec:
        if dist <= 0:
            return self._waypoints[0]
        if dist >= self._total_length:
            return self._waypoints[-1]
        cum = self._cumulative
        # _segment_index(dist): 0 < dist < total here, so the last segment starting at or before dist is
        # bisect_right - 1 (cum is non-decreasing); NaN compares false everywhere, which the search maps to 0
        seg = bisect_right(cum, dist) - 1 if dist == dist else 0
        seg_start = cum[seg]
        seg_len = cum[seg + 1] - seg_start
        t = 0 if seg_len <= 0 else (dist - seg_start) / seg_len
        # Vec.lerp(wp[seg], wp[seg + 1], t), built like vec_xy without the extra call
        v = _new_vec(Vec)
        _set_x(v, self._seg_x[seg] + self._seg_dx[seg] * t)
        _set_y(v, self._seg_y[seg] + self._seg_dy[seg] * t)
        return v

    def direction_at(self, dist: float) -> Vec:
        seg = self._segment_index(max(0.0, min(dist, self._total_length - 0.001)))
        return self._segment_dir[seg]

    def _segment_index(self, dist: float) -> int:
        cum = self._cumulative
        lo, hi = 0, len(self._waypoints) - 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if cum[mid] <= dist:
                lo = mid
            else:
                hi = mid - 1
        return max(0, min(lo, len(self._waypoints) - 2))

    def distance_to_point(self, p: Vec) -> float:
        best = sys.float_info.max
        wp = self._waypoints
        for i in range(len(wp) - 1):
            best = min(best, Path.point_segment_distance(p, wp[i], wp[i + 1]))
        return best

    def is_closer_than(self, p: Vec, limit: float) -> bool:
        """Exactly distance_to_point(p) < limit, without computing every segment distance in full."""
        wp = self._waypoints
        for i in range(len(wp) - 1):
            a, b = wp[i], wp[i + 1]
            abx, aby = b.x - a.x, b.y - a.y
            len2 = abx * abx + aby * aby
            t = 0 if len2 <= 0 else max(0.0, min(1.0, ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2))
            if Vec.lerp(a, b, t).closer_than(p, limit):
                return True
        return False

    def nearest_distance_along(self, p: Vec) -> float:
        best = sys.float_info.max
        best_d = 0.0
        wp = self._waypoints
        for i in range(len(wp) - 1):
            a, b = wp[i], wp[i + 1]
            abx, aby = b.x - a.x, b.y - a.y
            len2 = abx * abx + aby * aby
            t = 0 if len2 <= 0 else max(0.0, min(1.0, ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2))
            q = Vec.lerp(a, b, t)
            d = q.dist(p)
            if d < best:
                best = d
                best_d = self._cumulative[i] + t * math.sqrt(len2)
        return best_d

    @staticmethod
    def point_segment_distance(p: Vec, a: Vec, b: Vec) -> float:
        abx, aby = b.x - a.x, b.y - a.y
        len2 = abx * abx + aby * aby
        t = 0 if len2 <= 0 else max(0.0, min(1.0, ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2))
        # Vec.lerp(a, b, t).dist(p) without the temporary Vec
        return jhypot((a.x + abx * t) - p.x, (a.y + aby * t) - p.y)


def rounded(radius: float, *xy) -> list:
    """A polyline whose interior corners are rounded with quadratic fillets of up to ``radius`` px."""
    pts = [Vec(xy[i], xy[i + 1]) for i in range(0, len(xy) - 1, 2)]
    out = [pts[0]]

    def add(p):
        if not out or out[-1].dist(p) > 0.5:
            out.append(p)

    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        r = min(radius, min(a.dist(b), b.dist(c)) / 2)
        if r < 1:
            add(b)
            continue
        s = b.add(a.sub(b).normalized().scale(r))
        e = b.add(c.sub(b).normalized().scale(r))
        steps = max(3, int(math.ceil(r / 9)))
        for k in range(steps + 1):
            t = k / steps
            u = 1 - t
            add(Vec(u * u * s.x + 2 * u * t * b.x + t * t * e.x, u * u * s.y + 2 * u * t * b.y + t * t * e.y))
    add(pts[-1])
    return out
