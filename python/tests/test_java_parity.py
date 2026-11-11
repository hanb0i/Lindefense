"""Bit-for-bit parity with the Java build in the places Python's own library behaves differently.

The expected values below were produced by the Java build (Math.hypot, String.format, AutoPlayer -Dbot.dump=true).
"""
import math
import struct

from kit import new_game
from lindefense.ai.defender_ai import DefenderAI, Options
from lindefense.ai.reverse_match import Outcome
from lindefense.enemy.types import Modifier
from lindefense.javacompat import jhypot
from lindefense.jenum import EnumSet
from lindefense.map import maps
from lindefense.sim.vec import Vec

# (x, y, Java Math.hypot(x, y)) where Python's math.hypot rounds the other way (from the maps' own track segments)
_JAVA_HYPOT_DIFFERS = [
    (56.87274840275927, 26.520198120529074, 62.75213477831388),
    (-19.990265356115515, -13.997334493164544, 24.403607969344332),
    (19.101299543362302, -108.32885283134283, 109.99999999999993),
    (23.572075192223338, -6.316118511681907, 24.403607969344243),
    (18.41680425036742, -39.49496416858284, 43.5778713738291),
    (35.69690242163472, -24.99524016636508, 43.577871373828955),
    (39.49496416858301, -18.416804250367505, 43.577871373829296),
    (0.1, 0.2, 0.22360679774997896),
]

# (x, y, Java Math.hypot) for every scaling branch of fdlibm's hypot
_JAVA_HYPOT_EDGES = [(float.fromhex(a), float.fromhex(b), float.fromhex(h)) for a, b, h in [
    ("0x0.0p0", "0x0.0p0", "0x0.0p0"),
    ("-0x1.8p1", "0x1.0p2", "0x1.4p2"),
    ("0x1.7e43c8800759cp996", "0x1.7e43c8800759cp996", "0x1.0e4d50f99b211p997"),
    ("0x1.7e43c8800759cp996", "0x1.cab7bd666f388p994", "0x1.8f189cf7aa555p996"),
    ("0x1.56e1fc2f8f359p-997", "0x1.56e1fc2f8f359p-997", "0x1.e4e8d12762225p-997"),
    ("0x0.012688b70e62bp-1022", "0x0.024d116e1cc56p-1022", "0x0.0292991fdae04p-1022"),
    ("0x0.0000000000001p-1022", "0x0.0p0", "0x0.0000000000001p-1022"),
    ("0x1.4e718d7d7625ap664", "0x1.87e92154ef7acp-665", "0x1.4e718d7d7625ap664"),
    ("0x0.00000000007e8p-1022", "0x1.56e1fc2f8f359p-997", "0x1.56e1fc2f8f359p-997"),
    ("0x1.c1e43171a4a11p-531", "0x1.0a55f036fd1bcp-533", "0x1.c6cab9f4940ffp-531"),
    ("0x1.8ebbb5516e5adp1022", "0x1.005419221015dp1023", "0x1.44bb94dbefe6ap1023"),
    ("0x1.0p0", "0x1.70ef54646d497p-57", "0x1.0p0"),
    ("0x1.2a05f2p33", "0x1.5798ee2308c3ap-27", "0x1.2a05f2p33"),
]]


# (x, y, Java Math.pow(x, y)) where Python's math.pow differs; 0.9 ** 4 is Zippy Matt's 4th chain hop
_JAVA_POW_DIFFERS = [
    (0.9, 4.0, 0.6561000000000001),
    (2.0, 0.75, 1.6817928305074292),
    (0.5, 0.25, 0.8408964152537146),
    (3.0, 0.999999999999, 2.999999999996704),
    (1.28, 0.75, 1.203392989787646),
    (0.25, 0.25, 0.7071067811865475),
    (0.25, 0.75, 0.35355339059327373),
]

# (y, x, Java Math.atan2(y, x)) where Python's math.atan2 differs (Palantir's Panopticon cone test)
_JAVA_ATAN2_DIFFERS = [
    (0.9, 1.0, 0.7328151017865066),
    (-1075.0, -1.0, -1.5717265590847163),
    (0.75, 2.0, 0.3587706702705722),
    (3.0, -2.0, 2.1587989303424644),
    (-3.0, -2.0, -2.1587989303424644),
    (1023.9, -2.0, 1.5727496400641394),
]


def _bits(d):
    return struct.unpack("<q", struct.pack("<d", d))[0]


def test_pow_and_atan2_match_java(check):
    from lindefense.javacompat import jatan2, jpow
    for x, y, want in _JAVA_POW_DIFFERS:
        check(jpow(x, y) == want, "pow(%r, %r) = %r, Java %r" % (x, y, jpow(x, y), want))
    for y, x, want in _JAVA_ATAN2_DIFFERS:
        check(jatan2(y, x) == want, "atan2(%r, %r) = %r, Java %r" % (y, x, jatan2(y, x), want))
    inf, nan = float("inf"), float("nan")
    check(jpow(0.0, -1.0) == inf and jpow(-0.0, -1.0) == -inf and math.isnan(jpow(-8.0, 1.0 / 3)), "pow special cases")
    check(jpow(-2.0, 3.0) == -8.0 and jpow(2.0, 0.5) == math.sqrt(2.0) and math.isnan(jpow(nan, 1.5)), "pow special cases 2")
    check(jatan2(0.0, -1.0) == math.pi and jatan2(1.0, 0.0) == math.pi / 2 and jatan2(-inf, inf) == -math.pi / 4, "atan2 special cases")


def test_hypot_matches_java(check):
    for x, y, want in _JAVA_HYPOT_DIFFERS + _JAVA_HYPOT_EDGES:
        check(jhypot(x, y) == want, "hypot(%r, %r) = %r, Java %r" % (x, y, jhypot(x, y), want))
        check(Vec(x, y).dist(Vec(0, 0)) == want, "Vec.dist uses Java's hypot for (%r, %r)" % (x, y))
    check(jhypot(float("inf"), float("nan")) == float("inf"), "hypot(inf, NaN) is inf")
    check(math.isnan(jhypot(float("nan"), 1.0)), "hypot(NaN, 1) is NaN")


def test_neural_network_route_lengths_match_java(check):
    # Java: MapCatalog.create(5).getRoutes().get(i).getTotalLength() as raw long bits
    want = [4653497379100392312, 4653836378745552162, 4653869295236854971, 4653869295236854972,
            4653836378745552162, 4653497379100392313]
    got = [_bits(r.get_total_length()) for r in maps.create(5).get_routes()]
    check(got == want, "route lengths %r, Java %r" % (got, want))


def test_closer_than_is_exactly_dist_less_than(check):
    a = Vec(19.101299543362302, -108.32885283134283)
    o = Vec(0, 0)
    d = a.dist(o)
    for lim in (d, math.nextafter(d, 0), math.nextafter(d, 1e9), 50.0, 200.0):
        check(a.closer_than(o, lim) == (d < lim), "closer_than at %r" % lim)
        check(a.within_dist(o, lim) == (d <= lim), "within_dist at %r" % lim)
        check(a.exceeds_dist(o, lim) == (d > lim), "exceeds_dist at %r" % lim)


def test_enum_set_prints_like_java(check):
    check(str(EnumSet([Modifier.FORTIFIED, Modifier.CAMO])) == "[CAMO, FORTIFIED]", str(EnumSet([Modifier.FORTIFIED, Modifier.CAMO])))
    check(str(EnumSet()) == "[]", "empty set prints []")


def test_formatting_rounds_half_up_like_java(check):
    o = Outcome()
    o.credits_spent = 6408.5
    o.defender_earned = 4528.5
    s = str(o)
    check("spent    6409" in s and "AI earned    4529" in s, s)   # Java String.format("%7.0f") rounds half up
    g = new_game(0)
    g._time = 0.15
    g.set_banner("x", 0, 1)
    g._log_line("hello")
    check(g.get_log()[-1] == "[   0.2s] hello", g.get_log()[-1])


def test_defender_ai_verbose_reports_purchases(check, capsys):
    g = new_game(0)
    o = Options()
    o.verbose = True
    ai = DefenderAI(g, o)
    for _ in range(4):
        ai.manage()
    out = capsys.readouterr().out
    check("      buy w0 GEMINI cash 250" in out, "verbose purchase line missing: %r" % out)
