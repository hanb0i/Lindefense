"""Exact emulations of the Java behaviours the simulation depends on.

Seeded runs must produce the same results as the Java build, so randomness, rounding, integer truncation and
string hashing follow the Java specification bit for bit.
"""
import math
import struct

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


_DD = struct.Struct("<dd")
_QQ = struct.Struct("<QQ")
_pack_dd, _unpack_dd = _DD.pack, _DD.unpack
_pack_qq, _unpack_qq = _QQ.pack, _QQ.unpack
_sqrt = math.sqrt
_INF = float("inf")
_HYPOT_A_BIG = float.fromhex("0x1.00000ffffffffp500")
_HYPOT_B_SMALL = float.fromhex("0x1.0p-500")
_MIN_NORMAL = float.fromhex("0x1.0p-1022")
_TWO_M600 = float.fromhex("0x1.0p-600")
_TWO_P600 = float.fromhex("0x1.0p600")
_TWO_P1022 = float.fromhex("0x1.0p1022")


def jhypot(x: float, y: float) -> float:
    """Java Math.hypot, bit for bit: fdlibm's e_hypot (java.lang.FdLibm.Hypot), which StrictMath and Math both use.

    Python's math.hypot rounds differently in about one call in eight (1 ulp), so route lengths, track positions and
    every distance check drifted from the Java build.
    """
    a = abs(x)
    b = abs(y)
    if not (a < _INF and b < _INF):   # infinite or NaN
        return _INF if (a == _INF or b == _INF) else a + b
    if b > a:
        a, b = b, a
    qa, qb = _unpack_qq(_pack_dd(a, b))
    ha = qa >> 32   # high words (a, b >= 0)
    hb = qb >> 32
    if ha - hb > 0x3c00000:
        return a + b   # a / b > 2**60
    k = 0
    if a > _HYPOT_A_BIG or b < _HYPOT_B_SMALL:
        if a > _HYPOT_A_BIG:   # a > ~2**500: scale a and b by 2**-600
            ha -= 0x25800000
            hb -= 0x25800000
            a *= _TWO_M600
            b *= _TWO_M600
            k = 600
        if b < _HYPOT_B_SMALL:   # b < 2**-500
            if b < _MIN_NORMAL:   # subnormal b or 0
                if b == 0.0:
                    return a
                b *= _TWO_P1022
                a *= _TWO_P1022
                k -= 1022
            else:   # scale a and b by 2**600
                ha += 0x25800000
                hb += 0x25800000
                a *= _TWO_P600
                b *= _TWO_P600
                k -= 600
    w = a - b
    if w > b:
        t1 = _unpack_dd(_pack_qq((ha & 0xFFFFFFFF) << 32, 0))[0]
        t2 = a - t1
        w = _sqrt(t1 * t1 - (b * (-b) - t2 * (a + t1)))
    else:
        a = a + a
        y1, t1 = _unpack_dd(_pack_qq((hb & 0xFFFFFFFF) << 32, ((ha + 0x00100000) & 0xFFFFFFFF) << 32))
        y2 = b - y1
        t2 = a - t1
        w = _sqrt(t1 * y1 - (w * (-w) - (t1 * y2 + t2 * b)))
    return math.ldexp(w, k) if k != 0 else w


# ---- fdlibm bit helpers (java.lang.FdLibm __HI / __LO): words as signed 32-bit ints
_D = struct.Struct("<d")
_Q = struct.Struct("<q")
_UQ = struct.Struct("<Q")


def _bits(x: float) -> int:
    return _Q.unpack(_D.pack(x))[0]


def _hi(x: float) -> int:
    return _bits(x) >> 32


def _lo(x: float) -> int:
    return wrap32(_bits(x))


def _with_hi(x: float, high: int) -> float:
    return _D.unpack(_UQ.pack((_bits(x) & 0xFFFFFFFF) | ((high & 0xFFFFFFFF) << 32)))[0]


def _clear_lo(x: float) -> float:
    return _D.unpack(_UQ.pack(_bits(x) & 0xFFFFFFFF00000000 & 0xFFFFFFFFFFFFFFFF))[0]


def _fx(s):
    return float.fromhex(s)


_P_BP = (1.0, 1.5)
_P_DP_H = (0.0, _fx("0x1.2b8034p-1"))
_P_DP_L = (0.0, _fx("0x1.cfdeb43cfd006p-27"))
_P_L1, _P_L2, _P_L3 = _fx("0x1.3333333333303p-1"), _fx("0x1.b6db6db6fabffp-2"), _fx("0x1.55555518f264dp-2")
_P_L4, _P_L5, _P_L6 = _fx("0x1.17460a91d4101p-2"), _fx("0x1.d864a93c9db65p-3"), _fx("0x1.a7e284a454eefp-3")
_P_CP, _P_CP_H, _P_CP_L = _fx("0x1.ec709dc3a03fdp-1"), _fx("0x1.ec709ep-1"), -_fx("0x1.e2fe0145b01f5p-28")
_P_INV_LN2, _P_INV_LN2_H, _P_INV_LN2_L = _fx("0x1.71547652b82fep0"), _fx("0x1.715476p0"), _fx("0x1.4ae0bf85ddf44p-26")
_P_P1, _P_P2, _P_P3 = _fx("0x1.555555555553ep-3"), -_fx("0x1.6c16c16bebd93p-9"), _fx("0x1.1566aaf25de2cp-14")
_P_P4, _P_P5 = -_fx("0x1.bbd41c5d26bf1p-20"), _fx("0x1.6376972bea4d0p-25")
_P_LG2, _P_LG2_H, _P_LG2_L = _fx("0x1.62e42fefa39efp-1"), _fx("0x1.62e43p-1"), -_fx("0x1.05c610ca86c39p-29")
_P_OVT = 8.0085662595372944372e-0017
_MAX_DOUBLE = 1.7976931348623157e308


def jpow(x: float, y: float) -> float:
    """Java Math.pow / StrictMath.pow, bit for bit (a port of java.lang.FdLibm.Pow, fdlibm's e_pow).

    HotSpot on Apple Silicon computes Math.pow with fdlibm too; Python's math.pow (the platform libm) differs by an
    ulp in roughly one call in ten.
    """
    x = float(x)
    y = float(y)
    if y == 0.0:
        return 1.0
    if x != x or y != y:
        return x + y
    y_abs = abs(y)
    x_abs = abs(x)
    if y == 2.0:
        return x * x
    elif y == 0.5:
        if x >= -_MAX_DOUBLE:
            return math.sqrt(x + 0.0) if x + 0.0 >= 0 else float("nan")
    elif y_abs == 1.0:
        return x if y == 1.0 else 1.0 / x if x != 0 else (math.copysign(_INF, x))
    elif y_abs == _INF:
        if x_abs == 1.0:
            return y - y
        elif x_abs > 1.0:
            return y if y >= 0 else 0.0
        else:
            return -y if y < 0 else 0.0
    hx = _hi(x)
    ix = hx & 0x7FFFFFFF
    y_is_int = 0
    if hx < 0:
        if y_abs >= 9007199254740992.0:
            y_is_int = 2
        elif y_abs >= 1.0:
            ya = int(y_abs)
            if float(ya) == y_abs:
                y_is_int = 2 - (ya & 1)
    if x_abs == 0.0 or x_abs == _INF or x_abs == 1.0:
        z = x_abs
        if y < 0.0:
            z = _INF if z == 0.0 else 1.0 / z
        if hx < 0:
            if ((ix - 0x3FF00000) | y_is_int) == 0:
                z = float("nan")
            elif y_is_int == 1:
                z = -1.0 * z
        return z
    n = (hx >> 31) + 1
    if (n | y_is_int) == 0:
        return float("nan")
    s = 1.0
    if (n | (y_is_int - 1)) == 0:
        s = -1.0
    if y_abs > _fx("0x1.00000ffffffffp31"):
        if x_abs < _fx("0x1.fffff00000000p-1"):
            return s * _INF if y < 0.0 else s * 0.0
        if x_abs > _fx("0x1.00000ffffffffp0"):
            return s * _INF if y > 0.0 else s * 0.0
        t = x_abs - 1.0
        w = (t * t) * (0.5 - t * (0.3333333333333333333333 - t * 0.25))
        u = _P_INV_LN2_H * t
        v = t * _P_INV_LN2_L - w * _P_INV_LN2
        t1 = u + v
        t1 = _clear_lo(t1)
        t2 = v - (t1 - u)
    else:
        n = 0
        if ix < 0x00100000:
            x_abs *= 9007199254740992.0
            n -= 53
            ix = _hi(x_abs)
        n += (ix >> 20) - 0x3FF
        j = ix & 0x000FFFFF
        ix = j | 0x3FF00000
        if j <= 0x3988E:
            k = 0
        elif j < 0xBB67A:
            k = 1
        else:
            k = 0
            n += 1
            ix -= 0x00100000
        x_abs = _with_hi(x_abs, ix)
        u = x_abs - _P_BP[k]
        v = 1.0 / (x_abs + _P_BP[k])
        ss = u * v
        s_h = _clear_lo(ss)
        t_h = _with_hi(0.0, ((ix >> 1) | 0x20000000) + 0x00080000 + (k << 18))
        t_l = x_abs - (t_h - _P_BP[k])
        s_l = v * ((u - s_h * t_h) - s_h * t_l)
        s2 = ss * ss
        r = s2 * s2 * (_P_L1 + s2 * (_P_L2 + s2 * (_P_L3 + s2 * (_P_L4 + s2 * (_P_L5 + s2 * _P_L6)))))
        r += s_l * (s_h + ss)
        s2 = s_h * s_h
        t_h = 3.0 + s2 + r
        t_h = _clear_lo(t_h)
        t_l = r - ((t_h - 3.0) - s2)
        u = s_h * t_h
        v = s_l * t_h + t_l * ss
        p_h = u + v
        p_h = _clear_lo(p_h)
        p_l = v - (p_h - u)
        z_h = _P_CP_H * p_h
        z_l = _P_CP_L * p_h + p_l * _P_CP + _P_DP_L[k]
        t = float(n)
        t1 = (((z_h + z_l) + _P_DP_H[k]) + t)
        t1 = _clear_lo(t1)
        t2 = z_l - (((t1 - t) - _P_DP_H[k]) - z_h)
    y1 = _clear_lo(y)
    p_l = (y - y1) * t1 + y * t2
    p_h = y1 * t1
    z = p_l + p_h
    j = _hi(z)
    i = _lo(z)
    if j >= 0x40900000:
        if ((j - 0x40900000) | i) != 0:
            return s * _INF
        elif p_l + _P_OVT > z - p_h:
            return s * _INF
    elif (j & 0x7FFFFFFF) >= 0x4090CC00:
        if ((j - wrap32(0xC090CC00)) | i) != 0:
            return s * 0.0
        elif p_l <= z - p_h:
            return s * 0.0
    i = j & 0x7FFFFFFF
    k = (i >> 20) - 0x3FF
    n = 0
    if i > 0x3FE00000:
        n = j + (0x00100000 >> (k + 1))
        k = ((n & 0x7FFFFFFF) >> 20) - 0x3FF
        t = _with_hi(0.0, n & ~(0x000FFFFF >> k))
        n = ((n & 0x000FFFFF) | 0x00100000) >> (20 - k)
        if j < 0:
            n = -n
        p_h -= t
    t = p_l + p_h
    t = _clear_lo(t)
    u = t * _P_LG2_H
    v = (p_l - (t - p_h)) * _P_LG2 + t * _P_LG2_L
    z = u + v
    w = v - (z - u)
    t = z * z
    t1 = z - t * (_P_P1 + t * (_P_P2 + t * (_P_P3 + t * (_P_P4 + t * _P_P5))))
    r = (z * t1) / (t1 - 2.0) - (w + z * w)
    z = 1.0 - (r - z)
    j = _hi(z)
    j += (n << 20)
    if (j >> 20) <= 0:
        z = math.ldexp(z, n)
    else:
        z = _with_hi(z, _hi(z) + (n << 20))
    return s * z


_ATANHI = (_fx("0x1.dac670561bb4fp-2"), _fx("0x1.921fb54442d18p-1"), _fx("0x1.f730bd281f69bp-1"), _fx("0x1.921fb54442d18p0"))
_ATANLO = (_fx("0x1.a2b7f222f65e2p-56"), _fx("0x1.1a62633145c07p-55"), _fx("0x1.007887af0cbbdp-56"), _fx("0x1.1a62633145c07p-54"))
_AT = (_fx("0x1.555555555550dp-2"), -_fx("0x1.999999998ebc4p-3"), _fx("0x1.24924920083ffp-3"), -_fx("0x1.c71c6fe231671p-4"),
       _fx("0x1.745cdc54c206ep-4"), -_fx("0x1.3b0f2af749a6dp-4"), _fx("0x1.10d66a0d03d51p-4"), -_fx("0x1.dde2d52defd9ap-5"),
       _fx("0x1.97b4b24760debp-5"), -_fx("0x1.2b4442c6a6c2fp-5"), _fx("0x1.0ad3ae322da11p-6"))
_PI = math.pi
_PI_O_4 = _fx("0x1.921fb54442d18p-1")
_PI_O_2 = _fx("0x1.921fb54442d18p0")
_PI_LO = _fx("0x1.1a62633145c07p-53")
_TINY = 1.0e-300


def jatan(x: float) -> float:
    """StrictMath.atan, bit for bit (java.lang.FdLibm.Atan)."""
    x = float(x)
    hx = _hi(x)
    ix = hx & 0x7FFFFFFF
    if ix >= 0x44100000:
        if x != x:
            return x + x
        return _ATANHI[3] + _ATANLO[3] if hx > 0 else -_ATANHI[3] - _ATANLO[3]
    if ix < 0x3FDC0000:
        if ix < 0x3E200000:
            return x
        idx = -1
    else:
        x = abs(x)
        if ix < 0x3FF30000:
            if ix < 0x3FE60000:
                idx = 0
                x = (2.0 * x - 1.0) / (2.0 + x)
            else:
                idx = 1
                x = (x - 1.0) / (x + 1.0)
        else:
            if ix < 0x40038000:
                idx = 2
                x = (x - 1.5) / (1.0 + 1.5 * x)
            else:
                idx = 3
                x = -1.0 / x
    z = x * x
    w = z * z
    aT = _AT
    s1 = z * (aT[0] + w * (aT[2] + w * (aT[4] + w * (aT[6] + w * (aT[8] + w * aT[10])))))
    s2 = w * (aT[1] + w * (aT[3] + w * (aT[5] + w * (aT[7] + w * aT[9]))))
    if idx < 0:
        return x - x * (s1 + s2)
    z = _ATANHI[idx] - ((x * (s1 + s2) - _ATANLO[idx]) - x)
    return -z if hx < 0 else z


def jatan2(y: float, x: float) -> float:
    """Java Math.atan2 / StrictMath.atan2, bit for bit (java.lang.FdLibm.Atan2; HotSpot on Apple Silicon uses it)."""
    x = float(x)
    y = float(y)
    hx = _hi(x)
    ix = hx & 0x7FFFFFFF
    lx = _lo(x)
    hy = _hi(y)
    iy = hy & 0x7FFFFFFF
    ly = _lo(y)
    if x != x or y != y:
        return x + y
    if ((hx - 0x3FF00000) | lx) == 0:
        return jatan(y)
    m = ((hy >> 31) & 1) | ((hx >> 30) & 2)
    if (iy | ly) == 0:
        if m <= 1:
            return y
        return _PI + _TINY if m == 2 else -_PI - _TINY
    if (ix | lx) == 0:
        return -_PI_O_2 - _TINY if hy < 0 else _PI_O_2 + _TINY
    if ix == 0x7FF00000:
        if iy == 0x7FF00000:
            return (_PI_O_4 + _TINY, -_PI_O_4 - _TINY, 3.0 * _PI_O_4 + _TINY, -3.0 * _PI_O_4 - _TINY)[m]
        return (0.0, -0.0, _PI + _TINY, -_PI - _TINY)[m]
    if iy == 0x7FF00000:
        return -_PI_O_2 - _TINY if hy < 0 else _PI_O_2 + _TINY
    k = (iy - ix) >> 20
    if k > 60:
        z = _PI_O_2 + 0.5 * _PI_LO
    elif hx < 0 and k < -60:
        z = 0.0
    else:
        z = jatan(abs(y / x))
    if m == 0:
        return z
    if m == 1:
        return -z
    if m == 2:
        return _PI - (z - _PI_LO)
    return (z - _PI_LO) - _PI


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
