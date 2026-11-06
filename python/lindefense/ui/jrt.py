"""Java runtime helpers for the transpiled UI: string conversion and formatting, integer arithmetic, collections,
functional objects for lambdas, and small java.lang / java.util shims."""
import functools
import math
import os
import re
import time as _time

from lindefense.javacompat import JavaRandom


# ====================================================================== numbers
def idiv(a, b):
    """Java integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def imod(a, b):
    """Java integer remainder (sign of the dividend)."""
    r = abs(a) % abs(b)
    return r if a >= 0 else -r


def fmod(a, b):
    """Java floating-point remainder (sign of the dividend)."""
    if b == 0:
        return float("nan")
    return math.fmod(a, b)


def i32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def i64(v):
    v &= 0xFFFFFFFFFFFFFFFF
    return v - (1 << 64) if v & 0x8000000000000000 else v


def to_int(x):
    """(int) cast: truncation toward zero, NaN -> 0, saturating."""
    if isinstance(x, int):
        return i32(x)
    if isinstance(x, str):
        return ord(x)
    if x != x:
        return 0
    if x >= 2147483647:
        return 2147483647
    if x <= -2147483648:
        return -2147483648
    return int(x)


def to_long(x):
    if isinstance(x, int):
        return i64(x)
    if isinstance(x, str):
        return ord(x)
    if x != x:
        return 0
    if x >= 9.223372036854776e18:
        return (1 << 63) - 1
    if x <= -9.223372036854776e18:
        return -(1 << 63)
    return int(x)


def to_char(x):
    return x if isinstance(x, str) else chr(int(x) & 0xFFFF)


def to_float(x):
    return float(ord(x)) if isinstance(x, str) else float(x)


def ushr(a, n):
    return (a & 0xFFFFFFFF) >> (n & 31)


def ushr64(a, n):
    return (a & 0xFFFFFFFFFFFFFFFF) >> (n & 63)


def shl(a, n):
    return i32(a << (n & 31))


def jround(x):
    """Math.round: floor(x + 0.5) as a long; NaN -> 0."""
    if x != x:
        return 0
    if x in (float("inf"), float("-inf")):
        return (1 << 63) - 1 if x > 0 else -(1 << 63)
    return int(math.floor(x + 0.5))


def signum(x):
    if x != x:
        return x
    return 1.0 if x > 0 else -1.0 if x < 0 else x * 1.0


def rint(x):
    return float(round(x))


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


MAX_INT = 2147483647
MIN_INT = -2147483648
MAX_LONG = (1 << 63) - 1
MIN_LONG = -(1 << 63)
MAX_DOUBLE = 1.7976931348623157e308
MIN_DOUBLE = 4.9e-324


def floor_div(a, b):
    return a // b


def floor_mod(a, b):
    return a % b


def hypot(a, b):
    return math.hypot(a, b)


def cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def compare(a, b):
    return -1 if a < b else (1 if a > b else 0)


def is_nan(x):
    return x != x


def is_infinite(x):
    return x in (float("inf"), float("-inf"))


def is_finite(x):
    return not (x != x or x in (float("inf"), float("-inf")))


def nano_time():
    return _time.perf_counter_ns()


def current_time_millis():
    return int(_time.time() * 1000)


# ====================================================================== strings
def jstr_double(d):
    """Double.toString."""
    if d != d:
        return "NaN"
    if d == float("inf"):
        return "Infinity"
    if d == float("-inf"):
        return "-Infinity"
    if d == 0:
        return "-0.0" if math.copysign(1, d) < 0 else "0.0"
    a = abs(d)
    if 1e-3 <= a < 1e7:
        r = repr(float(d))
        if "e" in r or "E" in r:
            r = "%.17g" % d
        if "." not in r:
            r += ".0"
        return r
    r = repr(float(d))
    mant, _, exp = r.partition("e")
    if not exp:
        # repr gave a plain number (e.g. 12345678.0): convert to scientific
        s = "%.16e" % d
        mant, _, exp = s.partition("e")
        mant = mant.rstrip("0")
    if "." not in mant:
        mant += ".0"
    if mant.endswith("."):
        mant += "0"
    return mant + "E" + str(int(exp))


def s(x):
    """String.valueOf / string concatenation conversion."""
    if isinstance(x, str):
        return x
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float):
        return jstr_double(x)
    if isinstance(x, int):
        return str(x)
    ts = getattr(x, "to_string", None)
    if ts is not None:
        return ts()
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(s(v) for v in x) + "]"
    return str(x)


def cat(*parts):
    return "".join(s(p) for p in parts)


def add(a, b):
    """'+' when neither operand's static type is known: concatenation if either is a String."""
    if isinstance(a, str) or isinstance(b, str):
        return s(a) + s(b)
    return a + b


def equals(a, b):
    if a is b:
        return True
    if a is None or b is None:
        return False
    eq = getattr(a, "equals", None)
    if eq is not None and not isinstance(a, (str, int, float)):
        return eq(b)
    return a == b


def hash_code(x):
    if x is None:
        return 0
    if isinstance(x, str):
        h = 0
        for ch in x:
            h = (31 * h + ord(ch)) & 0xFFFFFFFF
        return i32(h)
    hc = getattr(x, "hash_code", None)
    if hc is not None:
        return hc()
    if isinstance(x, bool):
        return 1231 if x else 1237
    if isinstance(x, int):
        return i32(x)
    return hash(x) & 0x7FFFFFFF


def length(x):
    return len(x) if isinstance(x, (str, list, tuple)) else x.length()


def char_at(sv, i):
    return sv[i]


def substring(sv, a, b=None):
    return sv[a:] if b is None else sv[a:b]


def index_of(sv, x, start=0):
    if isinstance(sv, str):
        if isinstance(x, int):
            x = chr(x)
        return sv.find(x, start)
    try:
        return list(sv).index(x)
    except ValueError:
        return -1


def last_index_of(sv, x):
    if isinstance(sv, str):
        if isinstance(x, int):
            x = chr(x)
        return sv.rfind(x)
    lst = list(sv)
    for i in range(len(lst) - 1, -1, -1):
        if equals(lst[i], x):
            return i
    return -1


def split(sv, regex, limit=0):
    if len(regex) == 1 and regex not in ".$|()[{^?*+\\":
        parts = sv.split(regex)
    elif regex == "\\s+":
        parts = re.split(r"\s+", sv)
    else:
        parts = re.split(regex, sv)
    if limit == 0:
        while parts and parts[-1] == "":
            parts.pop()
    return parts


def replace_all(sv, regex, repl):
    return re.sub(regex, repl.replace("$", "\\"), sv)


def trim(sv):
    return sv.strip(" \t\n\r\x0b\f\x00")


def is_blank(sv):
    return sv.strip() == ""


def repeat(sv, n):
    return sv * n


def compare_to(a, b):
    if isinstance(a, str):
        return (a > b) - (a < b)
    ct = getattr(a, "compare_to", None)
    if ct is not None:
        return ct(b)
    return (a > b) - (a < b)


def compare_ignore_case(a, b):
    return compare_to(a.lower(), b.lower())


def to_char_array(sv):
    return list(sv)


def is_digit(c):
    return c.isdigit()


def is_letter(c):
    return c.isalpha()


def is_letter_or_digit(c):
    return c.isalnum()


def is_whitespace(c):
    return c.isspace()


def is_upper_case(c):
    return c.isupper()


def is_lower_case(c):
    return c.islower()


def to_upper_char(c):
    return c.upper()


def to_lower_char(c):
    return c.lower()


def parse_int(sv, radix=10):
    return int(sv.strip(), radix)


def parse_double(sv):
    return float(sv.strip())


def to_hex(v):
    return "%x" % (v & 0xFFFFFFFF)


# -------------------------------------------------------------- String.format
_FMT = re.compile(r"%(\d+\$)?([-#+ 0,(<]*)?(\d+)?(\.\d+)?([a-zA-Z%])")


def format(fmt, *args):
    """String.format with the conversions the UI uses (%d %s %f %e %x %c %b %n %%, flags , - 0 + width precision)."""
    if fmt is None or not isinstance(fmt, str):   # String.format(Locale, fmt, args...)
        fmt, args = args[0], args[1:]
    out = []
    pos = 0
    ai = 0
    for m in _FMT.finditer(fmt):
        out.append(fmt[pos:m.start()])
        pos = m.end()
        idx, flags, width, prec, conv = m.groups()
        flags = flags or ""
        if conv == "%":
            out.append("%")
            continue
        if conv == "n":
            out.append("\n")
            continue
        if idx:
            arg = args[int(idx[:-1]) - 1]
        else:
            arg = args[ai] if ai < len(args) else None
            ai += 1
        out.append(_fmt_one(arg, flags, width, prec, conv))
    out.append(fmt[pos:])
    return "".join(out)


def _fmt_one(arg, flags, width, prec, conv):
    c = conv.lower()
    if c == "d":
        v = int(arg)
        body = "{:,}".format(abs(v)) if "," in flags else str(abs(v))
        sign = "-" if v < 0 else ("+" if "+" in flags else (" " if " " in flags else ""))
        txt = sign + body
        if "(" in flags and v < 0:
            txt = "(" + body + ")"
    elif c == "f":
        p = 6 if prec is None else int(prec[1:])
        v = float(arg)
        txt = _half_up(v, p)
        if "," in flags:
            ip, _, fp = txt.lstrip("-").partition(".")
            ip = "{:,}".format(int(ip))
            txt = ("-" if txt.startswith("-") else "") + ip + ("." + fp if fp else "")
        if "+" in flags and v >= 0:
            txt = "+" + txt
    elif c == "e":
        p = 6 if prec is None else int(prec[1:])
        txt = ("%." + str(p) + "e") % float(arg)
    elif c == "g":
        p = 6 if prec is None else int(prec[1:])
        txt = ("%." + str(p) + "g") % float(arg)
    elif c == "x":
        v = int(arg)
        txt = "%x" % ((v & 0xFFFFFFFF if v >= -(1 << 31) else v & 0xFFFFFFFFFFFFFFFF) if v < 0 else v)
    elif c == "o":
        txt = "%o" % int(arg)
    elif c == "c":
        txt = arg if isinstance(arg, str) else chr(int(arg))
    elif c == "b":
        txt = "false" if arg is None or arg is False else "true"
    else:   # s
        txt = s(arg)
        if prec is not None:
            txt = txt[:int(prec[1:])]
    if conv.isupper():
        txt = txt.upper()
    if width:
        w = int(width)
        if len(txt) < w:
            if "-" in flags:
                txt = txt.ljust(w)
            elif "0" in flags and c in "dfex":
                neg = txt.startswith("-") or txt.startswith("+")
                txt = (txt[0] + txt[1:].rjust(w - 1, "0")) if neg else txt.rjust(w, "0")
            else:
                txt = txt.rjust(w)
    return txt


def _half_up(v, p):
    from decimal import ROUND_HALF_UP, Decimal
    if v != v:
        return "NaN"
    if v in (float("inf"), float("-inf")):
        return "Infinity" if v > 0 else "-Infinity"
    q = Decimal(1).scaleb(-p)
    d = Decimal(repr(v)).quantize(q, rounding=ROUND_HALF_UP)
    txt = format_decimal(d, p)
    return txt


def format_decimal(d, p):
    txt = "{:f}".format(d)
    if p == 0:
        txt = txt.split(".")[0]
    if txt.startswith("-") and float(txt) == 0:
        txt = txt[1:] if not (1 / float("-0.0") < 0 and False) else txt
    return txt


class StringBuilder:
    __slots__ = ("_parts",)

    def __init__(self, init=None):
        self._parts = [] if init is None or isinstance(init, int) else [s(init)]

    def append(self, x, start=None, end=None):
        if start is not None:
            self._parts.append(s(x)[start:end])
        else:
            self._parts.append(s(x))
        return self

    def to_string(self):
        return "".join(self._parts)

    __str__ = to_string

    def length(self):
        return len(self.to_string())

    def set_length(self, n):
        t = self.to_string()
        self._parts = [t[:n] + "\0" * max(0, n - len(t))]

    def insert(self, i, x):
        t = self.to_string()
        self._parts = [t[:i] + s(x) + t[i:]]
        return self

    def reverse(self):
        self._parts = [self.to_string()[::-1]]
        return self

    def char_at(self, i):
        return self.to_string()[i]

    def delete_char_at(self, i):
        t = self.to_string()
        self._parts = [t[:i] + t[i + 1:]]
        return self

    def delete(self, a, b):
        t = self.to_string()
        self._parts = [t[:a] + t[b:]]
        return self

    def is_empty(self):
        return self.length() == 0


# ====================================================================== functional objects (lambdas, method refs)
class Fn:
    """A lambda or method reference: callable, and answers to any single-method interface name."""
    __slots__ = ("f",)

    def __init__(self, f):
        self.f = f

    def __call__(self, *a):
        return self.f(*a)

    def __getattr__(self, name):
        return self.f


def call(f, *a):
    return f(*a)


# ====================================================================== collections
def size(x):
    if isinstance(x, (list, tuple, dict, set, frozenset, str)):
        return len(x)
    sz = getattr(x, "size", None)
    return sz() if sz is not None else len(x)


def is_empty(x):
    if isinstance(x, (list, tuple, dict, set, frozenset, str)):
        return len(x) == 0
    ie = getattr(x, "is_empty", None)
    return ie() if ie is not None else len(x) == 0


class ArrayList(list):
    """java.util.ArrayList / List (also used for LinkedList and the List views)."""

    def __init__(self, src=None):
        if src is None or isinstance(src, int):
            list.__init__(self)
        else:
            list.__init__(self, src)

    def add(self, a, b=None, *_):
        if b is None and not isinstance(a, int):
            self.append(a)
            return True
        if b is None:
            self.append(a)
            return True
        self.insert(a, b)
        return None

    def add_at(self, i, x):
        self.insert(i, x)

    def add_all(self, a, b=None):
        if b is None:
            self.extend(a)
        else:
            self[a:a] = list(b)
        return True

    def get(self, i):
        if i < 0:
            raise IndexError(i)
        return self[i]

    def set(self, i, x):
        old = self[i]
        self[i] = x
        return old

    def size(self):
        return len(self)

    def is_empty(self):
        return len(self) == 0

    def contains(self, x):
        for v in self:
            if v is x or equals(v, x):
                return True
        return False

    def index_of(self, x):
        for i, v in enumerate(self):
            if v is x or equals(v, x):
                return i
        return -1

    def last_index_of(self, x):
        for i in range(len(self) - 1, -1, -1):
            if self[i] is x or equals(self[i], x):
                return i
        return -1

    def remove(self, x):
        """remove(int index) returns the element; remove(Object) returns whether it was found."""
        if isinstance(x, int) and not isinstance(x, bool):
            return self.pop(x)
        for i, v in enumerate(self):
            if v is x or equals(v, x):
                del self[i]
                return True
        return False

    def remove_object(self, x):
        for i, v in enumerate(self):
            if v is x or equals(v, x):
                del self[i]
                return True
        return False

    def remove_if(self, pred):
        n = len(self)
        self[:] = [v for v in self if not pred(v)]
        return len(self) != n

    def remove_all(self, other):
        o = list(other)
        n = len(self)
        self[:] = [v for v in self if not any(v is w or equals(v, w) for w in o)]
        return len(self) != n

    def retain_all(self, other):
        o = list(other)
        n = len(self)
        self[:] = [v for v in self if any(v is w or equals(v, w) for w in o)]
        return len(self) != n

    def sort(self, cmp=None, **kw):
        if kw:
            list.sort(self, **kw)
        elif cmp is None:
            list.sort(self)
        else:
            list.sort(self, key=functools.cmp_to_key(cmp))

    def sub_list(self, a, b):
        return ArrayList(self[a:b])

    def iterator(self):
        return iter(list(self))

    def for_each(self, f):
        for v in list(self):
            f(v)

    def stream(self):
        return Stream(self)

    def to_array(self, *_):
        return list(self)

    def peek_first(self):
        return self[0] if self else None

    def get_first(self):
        return self[0]

    def get_last(self):
        return self[-1]

    def remove_first(self):
        return self.pop(0)

    def remove_last(self):
        return self.pop()

    def clear(self):
        del self[:]

    def to_string(self):
        return "[" + ", ".join(s(v) for v in self) + "]"

    def equals(self, o):
        return isinstance(o, list) and len(o) == len(self) and all(equals(a, b) for a, b in zip(self, o))

    def __eq__(self, o):
        return list.__eq__(self, o)

    __hash__ = None


LinkedList = ArrayList
List = ArrayList


class ArrayDeque(list):
    def __init__(self, src=None):
        list.__init__(self, [] if src is None or isinstance(src, int) else src)

    def add(self, x):
        self.append(x)
        return True

    add_last = offer = offer_last = add

    def add_first(self, x):
        self.insert(0, x)

    offer_first = push = add_first

    def poll(self):
        return self.pop(0) if self else None

    poll_first = poll

    def poll_last(self):
        return self.pop() if self else None

    def pop_first(self):
        return list.pop(self, 0)

    def remove_first(self):
        return list.pop(self, 0)

    def remove_last(self):
        return list.pop(self)

    def peek(self):
        return self[0] if self else None

    peek_first = peek

    def peek_last(self):
        return self[-1] if self else None

    def get_first(self):
        return self[0]

    def get_last(self):
        return self[-1]

    def size(self):
        return len(self)

    def is_empty(self):
        return not self

    def clear(self):
        del self[:]

    def contains(self, x):
        return any(v is x or equals(v, x) for v in self)

    def iterator(self):
        return iter(list(self))

    def remove(self, x=None):
        if x is None:
            return list.pop(self, 0)
        for i, v in enumerate(self):
            if v is x or equals(v, x):
                del self[i]
                return True
        return False

    def remove_if(self, pred):
        n = len(self)
        self[:] = [v for v in self if not pred(v)]
        return n != len(self)

    def descending_iterator(self):
        return iter(list(reversed(self)))

    __hash__ = None


class HashMap(dict):
    """java.util.HashMap / LinkedHashMap / TreeMap / EnumMap / IdentityHashMap (insertion order; a LinkedHashMap
    built with accessOrder=true moves entries to the end on get, like Java's LRU mode)."""

    def __init__(self, src=None, load=None, access_order=False):
        self._lru = bool(access_order)
        if src is None or isinstance(src, (int, type)) or (isinstance(src, type(object)) and not isinstance(src, dict)):
            dict.__init__(self)
        elif isinstance(src, dict):
            dict.__init__(self, src)
        else:
            dict.__init__(self)

    def put(self, k, v):
        old = dict.get(self, k)
        self[k] = v
        return old

    def get(self, k, *d):
        if k in self:
            v = dict.__getitem__(self, k)
            if self._lru:
                dict.__delitem__(self, k)
                dict.__setitem__(self, k, v)
            return v
        return d[0] if d else None

    def get_or_default(self, k, d):
        return dict.get(self, k, d)

    def contains_key(self, k):
        return k in self

    def contains_value(self, v):
        return any(equals(x, v) for x in self.values())

    def remove(self, k):
        return self.pop(k, None)

    def size(self):
        return len(self)

    def is_empty(self):
        return not self

    def key_set(self):
        return ArrayList(list(self.keys()))

    def entry_set(self):
        return ArrayList([Entry(k, v) for k, v in self.items()])

    def values_list(self):
        return ArrayList(list(dict.values(self)))

    def put_if_absent(self, k, v):
        if k not in self:
            self[k] = v
            return None
        return self[k]

    def compute_if_absent(self, k, f):
        if k not in self or self[k] is None:
            v = f(k)
            if v is not None:
                self[k] = v
            return v
        return self[k]

    def merge(self, k, v, f):
        if k in self and self[k] is not None:
            nv = f(self[k], v)
        else:
            nv = v
        if nv is None:
            self.pop(k, None)
        else:
            self[k] = nv
        return nv

    def put_all(self, m):
        self.update(m)

    def for_each(self, f):
        for k, v in list(self.items()):
            f(k, v)

    def clear(self):
        dict.clear(self)

    __hash__ = None


LinkedHashMap = TreeMap = EnumMap = IdentityHashMap = HashMap


class Entry:
    __slots__ = ("k", "v")

    def __init__(self, k, v):
        self.k, self.v = k, v

    def get_key(self):
        return self.k

    def get_value(self):
        return self.v


class HashSet(list):
    """java.util.HashSet / LinkedHashSet / EnumSet-like set with insertion order (identity or equals)."""

    def __init__(self, src=None):
        list.__init__(self)
        if src is not None and not isinstance(src, int):
            for v in src:
                self.add(v)

    def add(self, x):
        if self.contains(x):
            return False
        self.append(x)
        return True

    def contains(self, x):
        for v in self:
            if v is x or equals(v, x):
                return True
        return False

    def remove(self, x):
        for i, v in enumerate(self):
            if v is x or equals(v, x):
                del self[i]
                return True
        return False

    def add_all(self, it):
        ch = False
        for v in it:
            ch = self.add(v) or ch
        return ch

    def size(self):
        return len(self)

    def is_empty(self):
        return not self

    def clear(self):
        del self[:]

    def iterator(self):
        return iter(list(self))

    def remove_if(self, pred):
        n = len(self)
        self[:] = [v for v in self if not pred(v)]
        return n != len(self)

    def retain_all(self, other):
        o = list(other)
        n = len(self)
        self[:] = [v for v in self if any(v is w or equals(v, w) for w in o)]
        return n != len(self)

    def stream(self):
        return Stream(self)

    __hash__ = None


LinkedHashSet = TreeSet = HashSet


class Stream:
    def __init__(self, it):
        self._it = list(it)

    def filter(self, p):
        return Stream(v for v in self._it if p(v))

    def map(self, f):
        return Stream(f(v) for v in self._it)

    map_to_int = map_to_double = map_to_obj = map

    def count(self):
        return len(self._it)

    def sum(self):
        return sum(self._it)

    def any_match(self, p):
        return any(p(v) for v in self._it)

    def all_match(self, p):
        return all(p(v) for v in self._it)

    def none_match(self, p):
        return not any(p(v) for v in self._it)

    def for_each(self, f):
        for v in self._it:
            f(v)

    def collect(self, c):
        return ArrayList(self._it)

    def to_list(self):
        return ArrayList(self._it)

    def sorted(self, cmp=None):
        lst = ArrayList(self._it)
        lst.sort(cmp)
        return Stream(lst)

    def max(self, cmp=None):
        if not self._it:
            return Optional(None)
        if cmp is None:
            return Optional(max(self._it))
        return Optional(max(self._it, key=functools.cmp_to_key(cmp)))

    def min(self, cmp=None):
        if not self._it:
            return Optional(None)
        if cmp is None:
            return Optional(min(self._it))
        return Optional(min(self._it, key=functools.cmp_to_key(cmp)))

    def find_first(self):
        return Optional(self._it[0] if self._it else None)


class Optional:
    def __init__(self, v):
        self.v = v

    def is_present(self):
        return self.v is not None

    def get(self):
        return self.v

    def or_else(self, d):
        return self.v if self.v is not None else d

    def get_as_double(self):
        return self.v

    get_as_int = get_as_double


class Collectors:
    @staticmethod
    def to_list():
        return None


def list_of(*a):
    return ArrayList(a)


def as_list(*a):
    if len(a) == 1 and isinstance(a[0], (list, tuple)):
        return ArrayList(a[0])
    return ArrayList(a)


def sort(lst, cmp=None):
    if cmp is None:
        lst.sort()
    else:
        list.sort(lst, key=functools.cmp_to_key(cmp))


def sort_range(arr, a=None, b=None):
    if a is None:
        arr.sort()
    else:
        arr[a:b] = sorted(arr[a:b])


def unmodifiable(x):
    return x


def array_fill(arr, a, b=None, v=None):
    if b is None:
        for i in range(len(arr)):
            arr[i] = a
    else:
        for i in range(a, b):
            arr[i] = v


def array_copy(src, sp, dst, dp, n):
    dst[dp:dp + n] = src[sp:sp + n]


def copy_of(arr, n, fill=None):
    out = list(arr[:n])
    if n > len(arr):
        if fill is None and arr:
            fill = 0.0 if isinstance(arr[0], float) else (0 if isinstance(arr[0], int) and not isinstance(arr[0], bool) else None)
        out.extend([fill] * (n - len(arr)))
    return out


def new_array(dims, init):
    if len(dims) == 1:
        return [init] * int(dims[0])
    return [new_array(dims[1:], init) for _ in range(int(dims[0]))]


def arrays_equals(a, b):
    return a is b or (a is not None and b is not None and len(a) == len(b) and all(equals(x, y) for x, y in zip(a, b)))


def arrays_to_string(a):
    return "null" if a is None else "[" + ", ".join(s(v) for v in a) + "]"


def reverse(lst):
    lst.reverse()


def shuffle(lst, rnd=None):
    from lindefense.javacompat import shuffle as jshuffle
    jshuffle(lst, rnd if rnd is not None else JavaRandom(_time.perf_counter_ns()))


def nCopies(n, v):
    return ArrayList([v] * n)


# -------------------------------------------------------------- comparators
def comparing(key, cmp=None):
    if cmp is None:
        return lambda a, b: compare_to(key(a), key(b))
    return lambda a, b: cmp(key(a), key(b))


def comparing_double(key):
    return lambda a, b: compare(key(a), key(b))


comparing_int = comparing_long = comparing_double


def then_comparing(c1, c2):
    def cmp(a, b):
        r = c1(a, b)
        return r if r != 0 else c2(a, b)
    return cmp


def reversed_cmp(c):
    return lambda a, b: c(b, a)


def natural_order():
    return compare_to


def reverse_order(c=None):
    if c is None:
        return lambda a, b: compare_to(b, a)
    return lambda a, b: c(b, a)


# ====================================================================== java.lang misc
def get_property(name, default=None):
    """System.getProperty: Java -Dlindefense.x=v properties map to LINDEFENSE_X environment variables."""
    env = name.upper().replace(".", "_")
    v = os.environ.get(env)
    if v is None:
        v = os.environ.get(name)
    return default if v is None else v


def get_boolean(name):
    v = get_property(name)
    return v is not None and v.lower() == "true"


def get_integer(name, default=None):
    v = get_property(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def get_long(name, default=None):
    return get_integer(name, default)


def set_property(name, value):
    os.environ[name.upper().replace(".", "_")] = value


def clear_property(name):
    os.environ.pop(name.upper().replace(".", "_"), None)


def get_env(name):
    return os.environ.get(name)


class File:
    def __init__(self, a, b=None):
        if b is not None:
            a = os.path.join(a.path if isinstance(a, File) else a, b)
        self.path = a

    def exists(self):
        return os.path.exists(self.path)

    def is_file(self):
        return os.path.isfile(self.path)

    def is_directory(self):
        return os.path.isdir(self.path)

    def get_name(self):
        return os.path.basename(self.path)

    def get_path(self):
        return self.path

    def get_absolute_path(self):
        return os.path.abspath(self.path)

    def get_parent_file(self):
        p = os.path.dirname(self.path)
        return File(p) if p else None

    def mkdirs(self):
        os.makedirs(self.path, exist_ok=True)
        return True

    def list_files(self):
        if not os.path.isdir(self.path):
            return None
        return [File(os.path.join(self.path, n)) for n in sorted(os.listdir(self.path))]

    def length(self):
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def __str__(self):
        return self.path

    to_string = __str__


class Random(JavaRandom):
    def __init__(self, seed=None):
        JavaRandom.__init__(self, seed if seed is not None else _time.perf_counter_ns() ^ 0x5DEECE66D)


def thread_sleep(ms):
    _time.sleep(ms / 1000.0)


class Runtime:
    @staticmethod
    def get_runtime():
        return Runtime()

    def available_processors(self):
        return os.cpu_count() or 1

    def total_memory(self):
        return 0

    def free_memory(self):
        return 0

    def max_memory(self):
        return 0


def require_non_null(x, msg=None):
    if x is None:
        raise TypeError(msg or "null")
    return x


def identity_hash(x):
    return id(x) & 0x7FFFFFFF


# ====================================================================== helpers emitted by the transpiler
def _j_add(coll, v):
    if isinstance(coll, (set, HashSet)):
        coll.add(v)
    else:
        coll.append(v)
    return True


def _j_put(m, k, v):
    old = m.get(k) if isinstance(m, dict) else None
    m[k] = v
    return old


def _j_set(lst, i, v):
    old = lst[i]
    lst[i] = v
    return old


def _j_remove(coll, v):
    if isinstance(coll, (set, HashSet)):
        if v in coll:
            coll.remove(v)
            return True
        return False
    for i, x in enumerate(coll):
        if x is v or equals(x, v):
            del coll[i]
            return True
    return False


class _ListIter:
    __slots__ = ("_lst", "_i")

    def __init__(self, lst):
        self._lst = lst
        self._i = 0

    def has_next(self):
        return self._i < len(self._lst)

    def next(self):
        v = self._lst[self._i]
        self._i += 1
        return v

    def remove(self):
        self._i -= 1
        del self._lst[self._i]


class _SnapIter:
    """Iterator over a snapshot of a set or dict view; remove() deletes from the source."""
    __slots__ = ("_src", "_items", "_i")

    def __init__(self, src):
        self._src = src
        self._items = list(src)
        self._i = 0

    def has_next(self):
        return self._i < len(self._items)

    def next(self):
        v = self._items[self._i]
        self._i += 1
        return v

    def remove(self):
        v = self._items[self._i - 1]
        if isinstance(self._src, dict):
            self._src.pop(v, None)
        else:
            self._src.remove(v)


class _MapView(list):
    """keySet() / entrySet() / values() of a map: a snapshot list whose iterator.remove() deletes from the map."""

    def __init__(self, m, kind):
        self._map, self._kind = m, kind
        list.__init__(self, m.keys() if kind == "k" else (m.items() if kind == "e" else m.values()))


class _MapIter:
    __slots__ = ("_v", "_i")

    def __init__(self, view):
        self._v = view
        self._i = 0

    def has_next(self):
        return self._i < len(self._v)

    def next(self):
        x = self._v[self._i]
        self._i += 1
        return x

    def remove(self):
        x = self._v[self._i - 1]
        m = self._v._map
        if self._v._kind == "k":
            m.pop(x, None)
        elif self._v._kind == "e":
            m.pop(x[0], None)
        else:
            for k, v in list(m.items()):
                if v is x:
                    del m[k]
                    break


def key_set(m):
    return _MapView(m, "k")


def entry_set(m):
    return _MapView(m, "e")


def values_view(m):
    return _MapView(m, "v")


def _j_iter(coll):
    if isinstance(coll, _MapView):
        return _MapIter(coll)
    if isinstance(coll, list):
        return _ListIter(coll)
    return _SnapIter(coll)


def _j_remove_if(coll, pred):
    if isinstance(coll, list):
        n = len(coll)
        coll[:] = [v for v in coll if not pred(v)]
        return n != len(coll)
    gone = [v for v in coll if pred(v)]
    for v in gone:
        coll.remove(v)
    return bool(gone)


def _j_for_each(coll, f):
    for v in list(coll):
        f(v)


def _j_map_for_each(m, f):
    for k, v in list(m.items()):
        f(k, v)


def _j_compute_if_absent(m, k, f):
    v = m.get(k)
    if v is None:
        v = f(k)
        if v is not None:
            m[k] = v
    return v


def _j_merge(m, k, v, f):
    old = m.get(k)
    nv = v if old is None else f(old, v)
    if nv is None:
        m.pop(k, None)
    else:
        m[k] = nv
    return nv


def _j_remove_all(coll, other):
    o = list(other)
    n = len(coll)
    coll[:] = [v for v in coll if not any(v is w or equals(v, w) for w in o)]
    return n != len(coll)


def _j_retain_all(coll, other):
    o = list(other)
    n = len(coll)
    coll[:] = [v for v in coll if any(v is w or equals(v, w) for w in o)]
    return n != len(coll)


def _j_swap(lst, i, j):
    lst[i], lst[j] = lst[j], lst[i]


def _j_postinc(obj, attr, delta):
    old = getattr(obj, attr)
    setattr(obj, attr, old + delta)
    return old


def _j_preinc(obj, attr, delta):
    v = getattr(obj, attr) + delta
    setattr(obj, attr, v)
    return v


def _j_postinc_idx(arr, i, delta):
    old = arr[i]
    arr[i] = old + delta
    return old


def _j_preinc_idx(arr, i, delta):
    arr[i] = arr[i] + delta
    return arr[i]


class _SysOut:
    def println(self, *a):
        print(*(s(x) for x in a))

    def print(self, *a):
        print(*(s(x) for x in a), end="")

    def printf(self, fmt, *a):
        print(format(fmt, *a), end="")

    def flush(self):
        pass


_j_sysout = _SysOut()


# ====================================================================== java.util.prefs
class _PrefNode:
    """java.util.prefs.Preferences node backed by lindefense.prefs (JSON in the user's app-data folder)."""

    def __init__(self, path):
        from lindefense import prefs
        name = path[len("lindefense/"):] if path.startswith("lindefense/") else path
        self._n = prefs.node(name.strip("/") or "root")
        self._path = path

    def node(self, sub):
        return _PrefNode(self._path.rstrip("/") + "/" + sub if self._path else sub)

    def get(self, k, d=None):
        v = self._n.get(k, d)
        return d if v is None else (v if isinstance(v, str) else s(v))

    def get_boolean(self, k, d=False):
        return self._n.get_bool(k, d)

    def get_int(self, k, d=0):
        return self._n.get_int(k, d)

    get_long = get_int

    def get_double(self, k, d=0.0):
        v = self._n.get(k, d)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else d

    get_float = get_double

    def put(self, k, v):
        self._n.put(k, v)

    put_boolean = put_int = put_long = put_double = put_float = put

    def remove(self, k):
        self._n._data.pop(k, None)
        self._n.flush()

    def keys(self):
        return list(self._n._data.keys())

    def clear(self):
        self._n._data.clear()
        self._n.flush()

    def flush(self):
        self._n.flush()

    def sync(self):
        pass


class Preferences:
    @staticmethod
    def user_root():
        return _PrefNode("")

    @staticmethod
    def user_node_for_package(cls):
        return _PrefNode("lindefense")


def print_stack_trace(e):
    import traceback
    traceback.print_exception(type(e), e, e.__traceback__)


class Break(Exception):
    """Labeled break (Java `break label;`)."""

    def __init__(self, label):
        Exception.__init__(self, label)
        self.label = label


def dmin(a, b):
    """Math.min for doubles: NaN propagates."""
    if a != a:
        return a
    if b != b:
        return b
    return a if a <= b else b


def dmax(a, b):
    """Math.max for doubles: NaN propagates."""
    if a != a:
        return a
    if b != b:
        return b
    return a if a >= b else b


# ====================================================================== java.io writers
class StringWriter:
    def __init__(self, *a):
        self._parts = []

    def write(self, x, *a):
        self._parts.append(x if isinstance(x, str) else s(x))

    append = write

    def to_string(self):
        return "".join(self._parts)

    __str__ = to_string

    def flush(self):
        pass

    def close(self):
        pass


class FileWriter:
    def __init__(self, f, append=False, *a):
        path = f.path if isinstance(f, File) else str(f)
        self._fh = open(path, "a" if append is True else "w", encoding="utf-8", newline="")

    def write(self, x, *a):
        self._fh.write(x if isinstance(x, str) else s(x))

    append = write

    def flush(self):
        self._fh.flush()

    def close(self):
        self._fh.close()


BufferedWriter = FileWriter


class PrintWriter:
    """java.io.PrintWriter over a writer, a File or a path (println uses '\\n')."""

    def __init__(self, target, *a):
        if isinstance(target, (StringWriter, FileWriter, PrintWriter)):
            self._w = target
        elif target is _j_sysout or target is None:
            self._w = None
        else:
            self._w = FileWriter(target)

    def _out(self, txt):
        if self._w is None:
            print(txt, end="")
        else:
            self._w.write(txt)

    def write(self, x, *a):
        self._out(x if isinstance(x, str) else s(x))

    def print(self, x=""):
        self._out(s(x))

    def println(self, x=""):
        self._out(s(x) + "\n")

    def printf(self, fmt, *args):
        self._out(format(fmt, *args))
        return self

    format_ = printf

    def flush(self):
        if self._w is not None:
            self._w.flush()

    def close(self):
        if self._w is not None:
            self._w.close()
