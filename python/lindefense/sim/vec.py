"""Immutable 2D vector / point used throughout the simulation (independent of any graphics library)."""
import math

from lindefense.javacompat import jhypot


class Vec:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float):
        _set_x(self, float(x))   # slot descriptors directly: object.__setattr__ by name is ~40% slower
        _set_y(self, float(y))

    def __setattr__(self, name, value):
        raise AttributeError("Vec is immutable")

    def __reduce__(self):   # pickling (saved runs): rebuild through the constructor, the slots are read-only
        return Vec, (self.x, self.y)

    def add(self, o: "Vec") -> "Vec":
        return Vec(self.x + o.x, self.y + o.y)

    def sub(self, o: "Vec") -> "Vec":
        return Vec(self.x - o.x, self.y - o.y)

    def scale(self, s: float) -> "Vec":
        return Vec(self.x * s, self.y * s)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def dist(self, o: "Vec") -> float:
        # Java's Math.hypot (fdlibm), not math.hypot: they differ by 1 ulp often enough to desync seeded runs
        return jhypot(self.x - o.x, self.y - o.y)

    def dist_sq(self, o: "Vec") -> float:
        dx = self.x - o.x
        dy = self.y - o.y
        return dx * dx + dy * dy

    def within_dist(self, o: "Vec", limit: float) -> bool:
        """Exactly dist(o) <= limit, via squared lengths except in the rounding-sensitive band."""
        if 1e-6 < limit < 1e100:
            dx = self.x - o.x
            dy = self.y - o.y
            d2 = dx * dx + dy * dy
            l2 = limit * limit
            if d2 < l2 * (1 - 1e-9):
                return True
            if d2 > l2 * (1 + 1e-9):
                return False
        return self.dist(o) <= limit

    def exceeds_dist(self, o: "Vec", limit: float) -> bool:
        """Exactly dist(o) > limit, with the same fast path as within_dist."""
        if 1e-6 < limit < 1e100:
            dx = self.x - o.x
            dy = self.y - o.y
            d2 = dx * dx + dy * dy
            l2 = limit * limit
            if d2 < l2 * (1 - 1e-9):
                return False
            if d2 > l2 * (1 + 1e-9):
                return True
        return self.dist(o) > limit

    def closer_than(self, o: "Vec", limit: float) -> bool:
        """Exactly dist(o) < limit, with the same fast path as within_dist."""
        if 1e-6 < limit < 1e100:
            dx = self.x - o.x
            dy = self.y - o.y
            d2 = dx * dx + dy * dy
            l2 = limit * limit
            if d2 < l2 * (1 - 1e-9):
                return True
            if d2 > l2 * (1 + 1e-9):
                return False
        return self.dist(o) < limit

    def normalized(self) -> "Vec":
        ln = self.length()
        return Vec(0, 0) if ln < 1e-9 else Vec(self.x / ln, self.y / ln)

    @staticmethod
    def lerp(a: "Vec", b: "Vec", t: float) -> "Vec":
        return Vec(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)

    def __repr__(self) -> str:
        return "(%.1f, %.1f)" % (self.x, self.y)


_set_x = Vec.x.__set__
_set_y = Vec.y.__set__
_new = object.__new__


def vec_xy(x: float, y: float) -> Vec:
    """Vec(x, y) for coordinates that are already floats (skips __init__ and its float() conversions); hot loops only."""
    v = _new(Vec)
    _set_x(v, x)
    _set_y(v, y)
    return v
