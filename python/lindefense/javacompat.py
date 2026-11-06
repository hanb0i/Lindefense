"""Exact emulations of the Java behaviours the simulation depends on.

Seeded runs must produce the same results as the Java build, so randomness, rounding, integer truncation and
string hashing follow the Java specification bit for bit.
"""
import math

_MASK48 = (1 << 48) - 1
_MULT = 0x5DEECE66D
_MASK64 = (1 << 64) - 1


def wrap64(v: int) -> int:
    """Two's-complement 64-bit overflow, like Java long arithmetic."""
    v &= _MASK64
    return v - (1 << 64) if v >= (1 << 63) else v


def wrap32(v: int) -> int:
    """Two's-complement 32-bit overflow, like Java int arithmetic."""
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= (1 << 31) else v


def jround(x: float) -> int:
    """Java Math.round(double): floor(x + 0.5) (halves round up, not to even)."""
    if x != x:
        return 0
    return int(math.floor(x + 0.5))


def jint(x: float) -> int:
    """Java (int) cast of a double: truncation toward zero, NaN -> 0, saturating."""
    if x != x:
        return 0
    if x >= 2147483647:
        return 2147483647
    if x <= -2147483648:
        return -2147483648
    return int(x)


def jdiv(a: int, b: int) -> int:
    """Java integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def string_hash(s: str) -> int:
    """Java String.hashCode() over UTF-16 code units."""
    h = 0
    data = s.encode("utf-16-be")
    for i in range(0, len(data), 2):
        h = (31 * h + ((data[i] << 8) | data[i + 1])) & 0xFFFFFFFF
    return wrap32(h)


class JavaRandom:
    """java.util.Random: the 48-bit linear congruential generator, identical output for identical seeds."""

    __slots__ = ("_seed", "_next_gaussian", "_have_gaussian")

    def __init__(self, seed: int = 0):
        self._seed = (wrap64(seed) ^ _MULT) & _MASK48
        self._have_gaussian = False
        self._next_gaussian = 0.0

    def set_seed(self, seed: int) -> None:
        self._seed = (wrap64(seed) ^ _MULT) & _MASK48
        self._have_gaussian = False

    def _next(self, bits: int) -> int:
        self._seed = (self._seed * _MULT + 0xB) & _MASK48
        r = self._seed >> (48 - bits)
        # interpret as a signed 32-bit int, as Java does
        return wrap32(r)

    def next_int(self, bound: int | None = None) -> int:
        if bound is None:
            return self._next(32)
        if bound <= 0:
            raise ValueError("bound must be positive")
        r = self._next(31)
        m = bound - 1
        if (bound & m) == 0:
            return wrap32((bound * r) >> 31)
        u = r
        while True:
            r = u % bound
            if u - r + m < (1 << 31):
                return r
            u = self._next(31)

    def next_long(self) -> int:
        return wrap64((self._next(32) << 32) + self._next(32))

    def next_boolean(self) -> bool:
        return self._next(1) != 0

    def next_float(self) -> float:
        return self._next(24) / float(1 << 24)

    def next_double(self) -> float:
        return ((self._next(26) << 27) + self._next(27)) * (1.0 / (1 << 53))

    def next_gaussian(self) -> float:
        if self._have_gaussian:
            self._have_gaussian = False
            return self._next_gaussian
        while True:
            v1 = 2 * self.next_double() - 1
            v2 = 2 * self.next_double() - 1
            s = v1 * v1 + v2 * v2
            if 0 < s < 1:
                break
        mul = math.sqrt(-2 * math.log(s) / s)
        self._next_gaussian = v2 * mul
        self._have_gaussian = True
        return v1 * mul


def shuffle(lst: list, rnd: JavaRandom) -> None:
    """java.util.Collections.shuffle(list, rnd)."""
    for i in range(len(lst) - 1, 0, -1):
        j = rnd.next_int(i + 1)
        lst[i], lst[j] = lst[j], lst[i]


def fmt1(x: float) -> str:
    """String.format("%.1f") (Java rounds HALF_UP on the decimal value)."""
    return _fmt_half_up(x, 1)


def fmt0(x: float) -> str:
    return _fmt_half_up(x, 0)


def _fmt_half_up(x: float, places: int) -> str:
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-places)
    return str(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))
