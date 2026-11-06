"""Immutable 2D vector / point used throughout the simulation (independent of any graphics library)."""
import math


class Vec:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float):
        object.__setattr__(self, "x", float(x))
        object.__setattr__(self, "y", float(y))

    def __setattr__(self, name, value):
        raise AttributeError("Vec is immutable")

    def add(self, o: "Vec") -> "Vec":
        return Vec(self.x + o.x, self.y + o.y)

    def sub(self, o: "Vec") -> "Vec":
        return Vec(self.x - o.x, self.y - o.y)

    def scale(self, s: float) -> "Vec":
        return Vec(self.x * s, self.y * s)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def dist(self, o: "Vec") -> float:
        return math.hypot(self.x - o.x, self.y - o.y)

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

    def normalized(self) -> "Vec":
        ln = self.length()
        return Vec(0, 0) if ln < 1e-9 else Vec(self.x / ln, self.y / ln)

    @staticmethod
    def lerp(a: "Vec", b: "Vec", t: float) -> "Vec":
        return Vec(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)

    def __repr__(self) -> str:
        return "(%.1f, %.1f)" % (self.x, self.y)
