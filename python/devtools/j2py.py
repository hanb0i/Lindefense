#!/usr/bin/env python3
"""Java -> Python transpiler for the Lindefense UI layer.

Parses every Java file under src/lindefense (sim + ui) with javalang to build a class table with declared types, then
emits one Python module per UI Java file. Expressions are typed from declarations so Java semantics survive:
integer division, string concatenation, char arithmetic, collection calls on Python lists/dicts, lambdas as callable
objects, overload dispatch, static initialisation order, inner classes.

Usage: j2py.py <java_src_root> <python_out_root> [File.java ...]
"""
import glob
import os
import re
import sys

import javalang
from javalang import tree as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ====================================================================== naming
PY_KEYWORDS = {"False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
               "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is",
               "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
               }
BUILTIN_LOCALS = {"len", "str", "int", "float", "max", "min", "abs", "round", "range", "list", "sum", "id", "map",
                  "filter", "next", "iter", "any", "all", "isinstance", "super", "object", "hash", "format", "open",
                  "input", "pow", "bool", "dict", "set", "tuple", "chr", "ord", "divmod", "zip", "sorted", "reversed",
                  "enumerate", "getattr", "setattr", "math", "self", "cls", "sys", "os", "re", "time", "skia", "vars",
                  "dir", "callable", "property", "staticmethod", "classmethod", "slice", "bytes", "complex", "help",
                  "type", "print", "exec", "match", "case",
                  "catalog", "shop", "waves", "maps", "variance", "version", "assets", "random"}


def snake(name):
    if re.fullmatch(r"[A-Z0-9_]+", name) and any(c.isalpha() for c in name):
        return name   # CONSTANT
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    s = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", s)
    return s.lower()


def local_name(n):
    s = snake(n)
    if s in PY_KEYWORDS or s in BUILTIN_LOCALS or s.startswith("_"):
        s = s + "_"
    return s


def attr_name(n):
    s = snake(n)
    if s in PY_KEYWORDS:
        s = s + "_"
    return s


def module_name(java_file_base):
    return snake(java_file_base)


# ====================================================================== types
PRIMS_INT = {"int", "long", "short", "byte"}
PRIMS_FLOAT = {"double", "float"}
NUMERIC = PRIMS_INT | PRIMS_FLOAT | {"char", "Integer", "Long", "Double", "Float", "Short", "Byte"}
INT_LIKE = PRIMS_INT | {"Integer", "Long", "Short", "Byte"}
FLOAT_LIKE = PRIMS_FLOAT | {"Double", "Float"}
LIST_TYPES = {"List", "ArrayList", "LinkedList", "Collection", "Iterable", "AbstractList", "CopyOnWriteArrayList", "Vector"}
SET_TYPES = {"Set", "HashSet", "LinkedHashSet", "TreeSet", "EnumSet", "SortedSet"}
MAP_TYPES = {"Map", "HashMap", "LinkedHashMap", "TreeMap", "EnumMap", "IdentityHashMap", "SortedMap", "ConcurrentHashMap"}
DEQUE_TYPES = {"Deque", "ArrayDeque", "Queue"}
FUNCTIONAL = {"Runnable", "Supplier", "Consumer", "BiConsumer", "Function", "BiFunction", "Predicate", "BiPredicate",
              "IntPredicate", "DoublePredicate", "UnaryOperator", "BinaryOperator", "IntFunction", "IntUnaryOperator",
              "DoubleUnaryOperator", "ToDoubleFunction", "ToIntFunction", "ToLongFunction", "DoubleSupplier",
              "IntSupplier", "BooleanSupplier", "LongSupplier", "IntConsumer", "DoubleConsumer", "ObjIntConsumer",
              "IntBinaryOperator", "DoubleBinaryOperator", "Callable", "ActionListener"}


class TypeRef:
    __slots__ = ("name", "dims", "args", "cls")

    def __init__(self, name, dims=0, args=None, cls=None):
        self.name, self.dims, self.args, self.cls = name, dims, args or [], cls

    def elem(self):
        if self.dims:
            return TypeRef(self.name, self.dims - 1, self.args, self.cls)
        if self.args:
            return self.args[-1] if self.name in MAP_TYPES else self.args[0]
        return None

    def is_int(self):
        return self.dims == 0 and self.name in INT_LIKE

    def is_float(self):
        return self.dims == 0 and self.name in FLOAT_LIKE

    def is_numeric(self):
        return self.dims == 0 and self.name in NUMERIC

    def is_char(self):
        return self.dims == 0 and self.name in ("char", "Character")

    def is_string(self):
        return self.dims == 0 and self.name == "String"

    def is_bool(self):
        return self.dims == 0 and self.name in ("boolean", "Boolean")

    def is_array(self):
        return self.dims > 0

    def __repr__(self):
        return self.name + "[]" * self.dims


T_INT, T_LONG, T_DOUBLE, T_FLOAT = TypeRef("int"), TypeRef("long"), TypeRef("double"), TypeRef("float")
T_BOOL, T_STRING, T_CHAR, T_VOID = TypeRef("boolean"), TypeRef("String"), TypeRef("char"), TypeRef("void")


# ====================================================================== class table
class FieldInfo:
    def __init__(self, name, type_, static, final, cls, init=None):
        self.name, self.type, self.static, self.final, self.cls, self.init = name, type_, static, final, cls, init
        self.py = attr_name(name)


class MethodInfo:
    def __init__(self, name, params, ret, static, varargs, cls, node, abstract=False):
        self.name, self.params, self.ret, self.static, self.varargs, self.cls, self.node = name, params, ret, static, varargs, cls, node
        self.abstract = abstract


class ClassInfo:
    def __init__(self, name, kind, outer, cu, node, pkg, path):
        self.name, self.kind, self.outer, self.cu, self.node, self.pkg, self.path = name, kind, outer, cu, node, pkg, path
        self.fields, self.methods, self.ctors, self.inner = {}, {}, [], {}
        self.extends, self.implements = None, []
        self.enum_consts = []
        self.static = outer is None or "static" in getattr(node, "modifiers", set()) or kind in ("interface", "enum") \
            or (outer is not None and outer.kind == "interface")
        self.is_ui = False
        self.module = None
        self.local = False

    @property
    def qual(self):
        return (self.outer.qual + "." if self.outer else (self.pkg + ".")) + self.name

    @property
    def pyname(self):
        """Python expression naming this class from module scope."""
        return (self.outer.pyname + "." if self.outer else "") + self.name

    def chain(self):
        c = self
        while c is not None:
            yield c
            c = c.sup()

    def sup(self):
        e = self.extends
        return e.cls if e is not None and e.cls is not None else None

    def all_supers(self):
        seen = []
        stack = [self]
        while stack:
            c = stack.pop(0)
            if c is None or c in seen:
                continue
            seen.append(c)
            if c.extends is not None and c.extends.cls is not None:
                stack.append(c.extends.cls)
            for i in c.implements:
                if i.cls is not None:
                    stack.append(i.cls)
        return seen

    def find_field(self, n):
        for c in self.all_supers():
            if n in c.fields:
                return c.fields[n]
        return None

    def find_methods(self, n):
        out = []
        for c in self.all_supers():
            out.extend(c.methods.get(n, []))
        return out

    def find_inner(self, n):
        for c in self.all_supers():
            if n in c.inner:
                return c.inner[n]
        return None

    def external_base(self):
        """Name of the first non-project superclass (e.g. GCompound), or None."""
        c = self
        while c is not None:
            if c.extends is not None and c.extends.cls is None:
                return c.extends.name
            c = c.sup()
        return None


class Table:
    def __init__(self):
        self.classes = {}       # qual -> ClassInfo
        self.by_simple = {}     # simple -> [ClassInfo] (top-level + nested)
        self.cus = {}           # path -> (cu, [top ClassInfo])

    def add(self, ci):
        self.classes[ci.qual] = ci
        self.by_simple.setdefault(ci.name, []).append(ci)


def parse_type(t, ctx):
    if t is None:
        return T_VOID
    if isinstance(t, T.BasicType):
        return TypeRef(t.name, len(t.dimensions or []))
    name = t.name
    sub = t.sub_type
    args = []
    for a in (t.arguments or []):
        if isinstance(a, T.TypeArgument) and a.type is not None:
            args.append(parse_type(a.type, ctx))
        else:
            args.append(TypeRef("Object"))
    dims = len(t.dimensions or [])
    full = name
    while sub is not None:
        full += "." + sub.name
        if sub.arguments:
            args = [parse_type(a.type, ctx) if isinstance(a, T.TypeArgument) and a.type is not None else TypeRef("Object") for a in sub.arguments]
        dims = len(sub.dimensions or []) or dims
        sub = sub.sub_type
    cls = ctx.resolve_class(full) if ctx is not None else None
    segs = full.split(".")
    while len(segs) > 1 and segs[0][:1].islower():
        segs = segs[1:]
    if len(segs) >= 2 and segs[-1] in ("Double", "Float"):
        simple = segs[-2]
    elif len(segs) >= 2 and segs[-1] == "Entry":
        simple = "Map.Entry"
    else:
        simple = segs[-1]
    return TypeRef(simple if cls is None else cls.name, dims, args, cls)


class Ctx:
    """Name-resolution context for a class inside a compilation unit."""

    def __init__(self, table, cu, cls):
        self.table, self.cu, self.cls = table, cu, cls
        self.pkg = cu.package.name if cu.package else ""

    def resolve_class(self, name):
        tbl = self.table
        parts = name.split(".")
        head = parts[0]
        c = None
        # nested / enclosing
        k = self.cls
        while k is not None and c is None:
            if k.name == head:
                c = k
            else:
                c = k.find_inner(head)
            k = k.outer
        if c is None:
            for imp in self.cu.imports:
                if imp.static or imp.wildcard:
                    continue
                if imp.path.split(".")[-1] == head:
                    c = tbl.classes.get(imp.path)
                    if c is None:
                        # import of a nested class: pkg.Outer.Inner
                        c = tbl.classes.get(imp.path)
                    if c is None:
                        return None
                    break
        if c is None:
            c = tbl.classes.get(self.pkg + "." + head)
        if c is None:
            for imp in self.cu.imports:
                if imp.wildcard and not imp.static:
                    c = tbl.classes.get(imp.path + "." + head)
                    if c is not None:
                        break
        if c is None and head in ("lindefense",):
            # fully qualified name
            for i in range(len(parts), 0, -1):
                cc = tbl.classes.get(".".join(parts[:i]))
                if cc is not None:
                    c = cc
                    parts = [c.name] + parts[i:]
                    break
            else:
                return None
            for p in parts[1:]:
                c = c.find_inner(p) if c is not None else None
            return c
        if c is None:
            return None
        for p in parts[1:]:
            c = c.find_inner(p)
            if c is None:
                return None
        return c


def collect(table, root):
    files = sorted(glob.glob(os.path.join(root, "**", "*.java"), recursive=True))
    for f in files:
        rel = os.path.relpath(f, root)
        if rel.startswith("test" + os.sep):
            continue
        src = open(f, encoding="utf-8").read()
        cu = javalang.parse.parse(src)
        pkg = cu.package.name if cu.package else ""
        tops = []

        def walk(node, outer):
            kind = {T.ClassDeclaration: "class", T.InterfaceDeclaration: "interface", T.EnumDeclaration: "enum"}.get(type(node))
            if kind is None:
                return None
            ci = ClassInfo(node.name, kind, outer, cu, node, pkg, f)
            ci.is_ui = pkg.startswith("lindefense.ui") or pkg.startswith("lindefense.audio") or pkg.startswith("lindefense.tools") \
                or (pkg == "lindefense" and node.name in ("Assets", "Main"))
            if outer is not None:
                outer.inner[node.name] = ci
            table.add(ci)
            body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
            for m in body or []:
                walk(m, ci)
            return ci

        for td in cu.types:
            tops.append(walk(td, None))
        table.cus[f] = (cu, tops)
    # second pass: members (types need the full class table)
    for f, (cu, tops) in table.cus.items():
        def members(ci):
            ctx = Ctx(table, cu, ci)
            node = ci.node
            if ci.kind == "class":
                ci.extends = parse_type(node.extends, ctx) if node.extends else None
                ci.implements = [parse_type(i, ctx) for i in (node.implements or [])]
            elif ci.kind == "interface":
                ci.implements = [parse_type(i, ctx) for i in (node.extends or [])]
            else:
                ci.implements = [parse_type(i, ctx) for i in (node.implements or [])]
                ci.enum_consts = [c.name for c in node.body.constants] if node.body else []
                for c in ci.enum_consts:
                    ci.fields[c] = FieldInfo(c, TypeRef(ci.name, cls=ci), True, True, ci)
            body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
            for m in body or []:
                if isinstance(m, T.FieldDeclaration) or isinstance(m, T.ConstantDeclaration):
                    ty = parse_type(m.type, ctx)
                    st = "static" in m.modifiers or ci.kind == "interface"
                    for d in m.declarators:
                        t2 = TypeRef(ty.name, ty.dims + len(d.dimensions or []), ty.args, ty.cls)
                        ci.fields[d.name] = FieldInfo(d.name, t2, st, "final" in m.modifiers, ci, d.initializer)
                elif isinstance(m, T.MethodDeclaration):
                    params = [parse_type(p.type, ctx) for p in m.parameters]
                    va = bool(m.parameters) and m.parameters[-1].varargs
                    abstract = "abstract" in m.modifiers or (ci.kind == "interface" and m.body is None)
                    ci.methods.setdefault(m.name, []).append(
                        MethodInfo(m.name, params, parse_type(m.return_type, ctx), "static" in m.modifiers, va, ci, m, abstract))
                elif isinstance(m, T.ConstructorDeclaration):
                    params = [parse_type(p.type, ctx) for p in m.parameters]
                    va = bool(m.parameters) and m.parameters[-1].varargs
                    ci.ctors.append(MethodInfo("<init>", params, None, False, va, ci, m))
            for i in ci.inner.values():
                members(i)

        for c in tops:
            members(c)


# ====================================================================== python sim API knowledge
SIM_MODULES = {}   # simple class name -> python module


def scan_python(pyroot):
    for f in glob.glob(os.path.join(pyroot, "lindefense", "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, pyroot)
        if rel.startswith(os.path.join("lindefense", "ui")):
            continue
        mod = rel[:-3].replace(os.sep, ".")
        for m in re.finditer(r"^class (\w+)", open(f, encoding="utf-8").read(), re.M):
            SIM_MODULES.setdefault(m.group(1), mod)


# Java static utility classes that became Python modules: class -> (module, alias)
UTIL_MODULES = {
    "TowerCatalog": ("lindefense.tower.catalog", "catalog"),
    "Shop": ("lindefense.tower.shop", "shop"),
    "WaveData": ("lindefense.wave.waves", "waves"),
    "InjectionSchedule": ("lindefense.wave.waves", "waves"),
    "MapCatalog": ("lindefense.map.maps", "maps"),
    "RunSeed": ("lindefense.variance.variance", "variance"),
    "Version": ("lindefense.version", "version"),
    "Assets": ("lindefense.assets", "assets"),
}
# (Class, member) -> python template ({0},{1}.. args; {*} all args) for statics that changed shape
UTIL_CALLS = {
    ("Shop", "priceOf"): lambda a: "shop.price_of(%s)" % (a[0] if len(a) == 1 else "%s, %s" % (a[1], a[0])),
    ("Shop", "upgradeCost"): lambda a: "shop.upgrade_cost(%s)" % (a[0] if len(a) == 1 else "%s, %s" % (a[1], a[0])),
    ("Shop", "sellValue"): lambda a: "shop.sell_value(%s)" % (a[0] if len(a) == 1 else "%s, %s" % (a[1], a[0])),
    ("WaveData", "all"): lambda a: "waves.all_waves()",
    ("InjectionSchedule", "injectors"): lambda a: "waves.injectors(%s)" % a[0],
    ("RunSeed", "next"): lambda a: "variance.seed_next()",
    ("RunSeed", "format"): lambda a: "variance.seed_format(%s)" % a[0],
    ("RunSeed", "parse"): lambda a: "variance.seed_parse(%s)" % a[0],
    ("TowerCatalog", "all"): lambda a: "catalog.all_defs()",
}
UTIL_FIELDS = {
    ("InjectionSchedule", "FIRST_WAVE"): "waves.INJECTION_FIRST_WAVE",
    ("InjectionSchedule", "BOSS_DEBUTS"): "waves.BOSS_DEBUTS",
    ("RunSeed", "SPACE"): "variance.SEED_SPACE",
    ("RunSeed", "PROPERTY"): "variance.SEED_PROPERTY",
}

# known return types of external (JDK / ACM) methods
EXT_RET = {
    "length": T_INT, "size": T_INT, "indexOf": T_INT, "lastIndexOf": T_INT, "compareTo": T_INT, "hashCode": T_INT,
    "getRed": T_INT, "getGreen": T_INT, "getBlue": T_INT, "getAlpha": T_INT, "getRGB": T_INT, "ordinal": T_INT,
    "getSize": None, "charAt": T_CHAR, "toString": T_STRING, "substring": T_STRING, "toUpperCase": T_STRING,
    "toLowerCase": T_STRING, "trim": T_STRING, "name": T_STRING, "getLabel": T_STRING, "replace": T_STRING,
    "format": T_STRING, "valueOf": None, "getName": None, "isEmpty": T_BOOL, "contains": T_BOOL, "equals": T_BOOL,
    "startsWith": T_BOOL, "endsWith": T_BOOL, "isVisible": T_BOOL, "getX": T_DOUBLE, "getY": T_DOUBLE,
    "getWidth": T_DOUBLE, "getHeight": T_DOUBLE, "getAscent": T_DOUBLE, "getDescent": T_DOUBLE,
    "getCenterX": T_DOUBLE, "getCenterY": T_DOUBLE, "stringWidth": T_INT, "getStartAngle": T_DOUBLE,
    "getSweepAngle": T_DOUBLE, "getElementCount": T_INT, "nextInt": T_INT, "nextDouble": T_DOUBLE,
    "nextFloat": T_FLOAT, "nextBoolean": T_BOOL, "nextLong": T_LONG, "nanoTime": T_LONG,
    "currentTimeMillis": T_LONG, "getScale": T_DOUBLE, "getLineWidth": T_FLOAT, "getMinX": T_DOUBLE,
    "getMinY": T_DOUBLE, "getMaxX": T_DOUBLE, "getMaxY": T_DOUBLE, "canDisplayUpTo": T_INT, "getStyle": T_INT,
}
STRING_TYPES_EXT = {("Font", "getName"), ("Font", "getFamily"), ("Object", "toString")}

EXC_MAP = {"Exception": "Exception", "RuntimeException": "Exception", "Throwable": "BaseException", "Error": "Exception",
           "IOException": "OSError", "FileNotFoundException": "OSError", "UncheckedIOException": "OSError",
           "NumberFormatException": "ValueError", "IllegalArgumentException": "ValueError",
           "IllegalStateException": "RuntimeError", "UnsupportedOperationException": "NotImplementedError",
           "NullPointerException": "(AttributeError, TypeError)", "IndexOutOfBoundsException": "IndexError",
           "ArrayIndexOutOfBoundsException": "IndexError", "ClassCastException": "TypeError",
           "ArithmeticException": "ArithmeticError", "InterruptedException": "Exception",
           "SecurityException": "Exception", "LineUnavailableException": "Exception",
           "UnsupportedAudioFileException": "Exception", "LinkageError": "Exception", "NoClassDefFoundError": "Exception",
           "UnsatisfiedLinkError": "Exception", "HeadlessException": "Exception", "FontFormatException": "Exception",
           "ConcurrentModificationException": "RuntimeError", "BackingStoreException": "Exception",
           "InvocationTargetException": "Exception", "ReflectiveOperationException": "Exception",
           "URISyntaxException": "Exception", "AWTException": "Exception", "OutOfMemoryError": "MemoryError",
           "StackOverflowError": "RecursionError", "AssertionError": "AssertionError", "NoSuchElementException": "Exception"}

# external names provided by jawt / acm / jrt
JAWT_NAMES = {"Color", "Font", "FontMetrics", "BasicStroke", "Stroke", "AffineTransform", "Path2D", "GeneralPath",
              "Ellipse2D", "Rectangle2D", "RoundRectangle2D", "Line2D", "Arc2D", "QuadCurve2D", "CubicCurve2D",
              "Polygon", "Area", "Shape", "Point2D", "Rectangle", "Dimension", "Point", "Insets", "GradientPaint",
              "LinearGradientPaint", "RadialGradientPaint", "MultipleGradientPaint", "TexturePaint", "AlphaComposite",
              "Composite", "RenderingHints", "BufferedImage", "Image", "ImageIO", "Graphics", "Graphics2D",
              "GraphicsEnvironment", "PathShape"}
ACM_NAMES = {"GObject", "GRect", "GRoundRect", "G3DRect", "GOval", "GArc", "GLine", "GPolygon", "GLabel", "GImage",
             "GCompound", "GCanvas", "GPoint", "GDimension", "GRectangle"}
JRT_CLASSES = {"ArrayList": "_j.ArrayList", "LinkedList": "_j.ArrayList", "HashMap": "_j.HashMap",
               "LinkedHashMap": "_j.HashMap", "TreeMap": "_j.HashMap", "EnumMap": "_j.HashMap",
               "IdentityHashMap": "_j.HashMap", "HashSet": "_j.HashSet", "LinkedHashSet": "_j.HashSet",
               "TreeSet": "_j.HashSet", "ArrayDeque": "_j.ArrayDeque", "StringBuilder": "_j.StringBuilder",
               "StringBuffer": "_j.StringBuilder", "Random": "_j.Random", "File": "_j.File",
               "CopyOnWriteArrayList": "_j.ArrayList", "ConcurrentHashMap": "_j.HashMap"}


_PYMOD_CACHE = {}


def sim_static(cls_name, member_py):
    """For a ported sim class: (module, alias) if the static member lives at module level instead of on the class."""
    mod = SIM_MODULES.get(cls_name)
    if mod is None:
        return None
    try:
        import importlib
        m = _PYMOD_CACHE.get(mod) or importlib.import_module(mod)
        _PYMOD_CACHE[mod] = m
    except Exception:
        return None
    c = getattr(m, cls_name, None)
    if c is not None and hasattr(c, member_py):
        return None
    if hasattr(m, member_py):
        return mod
    return None


# ====================================================================== emitter
class Out:
    def __init__(self):
        self.lines = []

    def line(self, ind, s):
        self.lines.append("    " * ind + s)


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}   # java name -> (pyname, TypeRef)

    def lookup(self, n):
        s = self
        while s is not None:
            if n in s.vars:
                return s.vars[n]
            s = s.parent
        return None

    def declare(self, n, t):
        py = local_name(n)
        self.vars[n] = (py, t)
        return py


class Unsupported(Exception):
    pass


class FileGen:
    def __init__(self, gen, path, cu, tops):
        self.gen, self.path, self.cu, self.tops = gen, path, cu, tops
        self.table = gen.table
        self.imports_top = set()      # python import lines needed at module top
        self.imports_bottom = set()   # deferred (cycle-safe) imports
        self.lam = 0
        self.warnings = []
        self.static_ctx = False
        self.cls = None
        self.method_static = False
        self.in_ctor = False
        self.class_body_init = False   # translating static initialisers (module level, after the class)
        self.static_deps = set()       # UI modules needed while the module executes

    # ---------------------------------------------------------------- helpers
    def warn(self, msg, node=None):
        pos = getattr(node, "position", None)
        self.warnings.append("%s:%s: %s" % (os.path.basename(self.path), pos.line if pos else "?", msg))

    def ctx(self):
        return Ctx(self.table, self.cu, self.cls)

    def need_class(self, ci):
        """Makes a project class reachable by its simple top-level name; returns the Python expression."""
        top = ci
        while top.outer is not None:
            top = top.outer
        if top.path == self.path:
            return ci.pyname
        if ci.is_ui:
            mod = self.gen.ui_module_of(top)
            line = "from %s import %s" % (mod, top.name)
            if self.class_body_init:
                self.imports_top.add(line)
                self.static_deps.add(mod)
            else:
                self.imports_bottom.add(line)
            return ci.pyname
        # simulation class (already ported)
        if top.name in UTIL_MODULES:
            mod, alias = UTIL_MODULES[top.name]
            self.imports_top.add("from %s import %s" % (mod.rsplit(".", 1)[0], mod.rsplit(".", 1)[1]) if mod.count(".") else "import %s" % mod)
            return alias
        mod = SIM_MODULES.get(top.name)
        if mod is None:
            self.warn("no python module for sim class %s" % top.name)
            mod = "lindefense.UNKNOWN"
        self.imports_top.add("from %s import %s" % (mod, top.name))
        return ci.pyname

    def ext_class(self, name):
        if name in JAWT_NAMES or name in ACM_NAMES:
            return name
        if name in JRT_CLASSES:
            return JRT_CLASSES[name]
        if name in ("EnumSet",):
            self.imports_top.add("from lindefense.jenum import EnumSet")
            return "EnumSet"
        if name == "JEnum":
            return "JEnum"
        return None

    # ---------------------------------------------------------------- types
    def ptype(self, t):
        return parse_type(t, self.ctx())

    # ---------------------------------------------------------------- expression entry
    def expr(self, e, scope, want=None):
        code, t = self._expr(e, scope)
        return code, t

    def ex(self, e, scope):
        return self._expr(e, scope)[0]

    def _expr(self, e, scope):
        m = getattr(self, "e_" + type(e).__name__, None)
        if m is None:
            raise Unsupported("expression %s" % type(e).__name__)
        code, t = m(e, scope)
        return code, t

    # ---------------------------------------------------------------- literals
    def e_Literal(self, e, scope):
        v = e.value
        code, t = self.literal(v)
        return self.post(e, code, t, scope)

    def literal(self, v):
        if v == "true":
            return "True", T_BOOL
        if v == "false":
            return "False", T_BOOL
        if v == "null":
            return "None", TypeRef("null")
        if v.startswith('"'):
            return repr(decode_java_string(v[1:-1])), T_STRING
        if v.startswith("'"):
            return repr(decode_java_string(v[1:-1])), T_CHAR
        s = v.replace("_", "")
        low = s.lower()
        if low.startswith("0x"):
            body = s[2:].rstrip("lL")
            val = int(body, 16)
            if not s.lower().endswith("l") and val >= 0x80000000:
                val -= 1 << 32
            return str(val) if val < 0 else s.rstrip("lL"), (T_LONG if low.endswith("l") else T_INT)
        if low.startswith("0b"):
            return s.rstrip("lL"), T_INT
        if low.endswith("l"):
            return str(int(s[:-1])), T_LONG
        if low.endswith("f") or low.endswith("d") or "." in s or ("e" in low and not low.startswith("0x")):
            f = s.rstrip("fFdD")
            if f.startswith("."):
                f = "0" + f
            if f.endswith("."):
                f += "0"
            if "." not in f and "e" not in f.lower():
                f += ".0"
            return f, (T_FLOAT if low.endswith("f") else T_DOUBLE)
        if len(s) > 1 and s.startswith("0") and s.isdigit():
            return str(int(s, 8)), T_INT
        return s, T_INT

    # ---------------------------------------------------------------- names
    def e_MemberReference(self, e, scope):
        # [qualifier.]member with selectors
        if e.qualifier:
            base, bt, kind = self.resolve_qualifier(e.qualifier, scope, e)
            code, t = self.field_access(base, bt, kind, e.member, e)
        else:
            code, t = self.simple_name(e.member, scope, e)
        return self.post(e, code, t, scope)

    def simple_name(self, n, scope, node):
        v = scope.lookup(n)
        if v is not None:
            return v[0], v[1]
        f, owner_expr = self.find_field_in_scope(n)
        if f is not None:
            return owner_expr, f.type
        # static import
        for imp in self.cu.imports:
            if imp.static and (imp.path.endswith("." + n) or imp.wildcard):
                cname = imp.path if imp.wildcard else imp.path.rsplit(".", 1)[0]
                ci = self.table.classes.get(cname)
                if ci is not None and (n in ci.fields):
                    fi = ci.fields[n]
                    if not ci.is_ui and ci.kind != "enum":
                        mod = sim_static(ci.name, self.field_py(fi))
                        if mod is not None:
                            alias = "_m_" + mod.rsplit(".", 1)[1]
                            self.imports_top.add("import %s as %s" % (mod, alias))
                            return alias + "." + self.field_py(fi), fi.type
                    return self.need_class(ci) + "." + self.field_py(fi), fi.type
        ci = self.ctx().resolve_class(n)
        if ci is not None:
            return self.need_class(ci), TypeRef(ci.name, cls=ci)
        self.warn("unresolved name %s" % n, node)
        return local_name(n), None

    def field_py(self, fi):
        return self.gen.field_pyname(fi)

    def find_field_in_scope(self, n):
        """Field visible from the current class: returns (FieldInfo, python access expr)."""
        k = self.cls
        hops = 0
        inst_ok = not self.method_static
        while k is not None:
            f = k.find_field(n)
            if f is not None:
                if f.static or f.cls.kind == "interface":
                    return f, self.need_class(f.cls) + "." + self.field_py(f)
                if hops == 0:
                    return f, "self." + self.field_py(f)
                return f, self.outer_ref(hops) + "." + self.field_py(f)
            if not k.static and k.outer is not None:
                hops += 1
            elif k.outer is not None:
                hops = 99
            k = k.outer
        return None, None

    def outer_ref(self, hops):
        return "self" + "._outer" * hops

    def resolve_qualifier(self, q, scope, node):
        """Resolves a dotted qualifier: returns (code, TypeRef or None, kind) with kind 'value' | 'class' | 'util'."""
        parts = q.split(".")
        head = parts[0]
        code, t, kind = None, None, None
        v = scope.lookup(head)
        if v is not None:
            code, t, kind = v[0], v[1], "value"
        else:
            f, expr = self.find_field_in_scope(head)
            if f is not None:
                code, t, kind = expr, f.type, "value"
        rest = parts[1:]
        if code is None:
            # longest class name prefix
            ci = None
            for i in range(len(parts), 0, -1):
                ci = self.ctx().resolve_class(".".join(parts[:i]))
                if ci is not None:
                    rest = parts[i:]
                    break
            if ci is not None:
                if ci.name in UTIL_MODULES and ci.outer is None:
                    code, t, kind = self.need_class(ci), TypeRef(ci.name, cls=ci), "util"
                else:
                    code, t, kind = self.need_class(ci), TypeRef(ci.name, cls=ci), "class"
            else:
                # external class (java.*, acm.*) possibly fully qualified
                ext = [p for p in parts if p[:1].isupper()]
                if ext:
                    name = ext[0]
                    idx = parts.index(name)
                    rest = parts[idx + 1:]
                    # nested external: Path2D.Double, Map.Entry, Point2D.Double, Thick.Line (project handled above)
                    while rest and rest[0][:1].isupper() and rest[0] not in ("PI", "E") and not re.fullmatch(r"[A-Z0-9_]+", rest[0]):
                        name = name + "." + rest[0]
                        rest = rest[1:]
                    code, t, kind = name, TypeRef(name), "ext"
                else:
                    self.warn("unresolved qualifier %s" % q, node)
                    return local_name(head), None, "value"
        for p in rest:
            code, t = self.field_access(code, t, kind, p, node)
            kind = "value"
        return code, t, kind

    def field_access(self, base, bt, kind, member, node):
        if kind == "util":
            cls = bt.name
            if (cls, member) in UTIL_FIELDS:
                return UTIL_FIELDS[(cls, member)], self.util_field_type(bt, member)
            return base + "." + attr_name(member), self.util_field_type(bt, member)
        if kind == "ext":
            return self.ext_static_field(base, member, node)
        if member == "length" and (bt is None or bt.is_array()):
            return "len(%s)" % base, T_INT
        if bt is not None and bt.cls is not None:
            ci = bt.cls
            if bt.dims:
                return "%s.%s" % (base, attr_name(member)), None
            f = ci.find_field(member)
            if f is not None:
                if kind == "class" and f.static and not ci.is_ui and ci.kind != "enum":
                    mod = sim_static(ci.name, self.field_py(f))
                    if mod is not None:
                        alias = "_m_" + mod.rsplit(".", 1)[1]
                        self.imports_top.add("import %s as %s" % (mod, alias))
                        return "%s.%s" % (alias, self.field_py(f)), f.type
                return base + "." + self.field_py(f), f.type
            inner = ci.find_inner(member)
            if inner is not None:
                return self.need_class(inner), TypeRef(inner.name, cls=inner)
        if kind == "class" and bt is not None and bt.cls is not None and member in getattr(bt.cls, "enum_consts", []):
            return base + "." + member, TypeRef(bt.cls.name, cls=bt.cls)
        if bt is not None and bt.name in ("Rectangle", "Dimension", "Point", "Insets", "Point2D.Double", "GPoint"):
            return base + "." + member, T_INT if bt.name in ("Rectangle", "Dimension", "Point") else T_DOUBLE
        return base + "." + attr_name(member), None

    def util_field_type(self, bt, member):
        f = bt.cls.fields.get(member) if bt.cls else None
        return f.type if f else None

    def ext_static_field(self, cls, member, node):
        c = cls.split(".")[-1]
        if c == "Math":
            return {"PI": "math.pi", "E": "math.e"}[member], T_DOUBLE
        if c in ("Integer", "Long", "Short", "Byte", "Character"):
            v = {"MAX_VALUE": {"Integer": "_j.MAX_INT", "Long": "_j.MAX_LONG", "Short": "32767", "Byte": "127", "Character": "'\\uffff'"},
                 "MIN_VALUE": {"Integer": "_j.MIN_INT", "Long": "_j.MIN_LONG", "Short": "-32768", "Byte": "-128", "Character": "'\\x00'"}}
            return v[member][c], T_INT
        if c in ("Double", "Float"):
            v = {"MAX_VALUE": "_j.MAX_DOUBLE", "MIN_VALUE": "_j.MIN_DOUBLE", "POSITIVE_INFINITY": "float('inf')",
                 "NEGATIVE_INFINITY": "float('-inf')", "NaN": "float('nan')"}[member]
            return v, T_DOUBLE
        if c == "Boolean":
            return {"TRUE": "True", "FALSE": "False"}[member], T_BOOL
        if c == "System" and member in ("out", "err"):
            return "_j_sysout", TypeRef("PrintStream")
        if c == "Locale":
            return "None", TypeRef("Locale")
        if c in ("Color",):
            return "Color." + member, TypeRef("Color")
        if c == "Toolkit":
            return "None", None
        name = self.ext_class(c.split(".")[0])
        if name is None:
            self.warn("external static %s.%s" % (cls, member), node)
            name = cls
        else:
            name = name + cls[len(c.split(".")[0]):] if "." in cls else name
        return name + "." + member, None

    # ---------------------------------------------------------------- selectors & postfix/prefix
    def post(self, e, code, t, scope):
        for sel in (getattr(e, "selectors", None) or []):
            code, t = self.selector(code, t, sel, scope)
        for op in (getattr(e, "postfix_operators", None) or []):
            code, t = self.incdec(e, code, t, op, post=True)
        for op in reversed(getattr(e, "prefix_operators", None) or []):
            code, t = self.prefix(e, code, t, op, scope)
        return code, t

    def selector(self, code, t, sel, scope):
        if isinstance(sel, T.MemberReference):
            return self.field_access(code, t, "value", sel.member, sel)
        if isinstance(sel, T.MethodInvocation):
            return self.call(code, t, "value", sel.member, sel.arguments, scope, sel)
        if isinstance(sel, T.ArraySelector):
            idx = self.ex(sel.index, scope)
            if t is not None and t.dims == 0 and t.name in MAP_TYPES:
                return "%s[%s]" % (code, idx), t.elem()
            return "%s[%s]" % (code, idx), (t.elem() if t is not None else None)
        if isinstance(sel, T.SuperMethodInvocation):
            raise Unsupported("super selector")
        raise Unsupported("selector %s" % type(sel).__name__)

    def incdec(self, e, code, t, op, post):
        # used inside expressions: only simple locals via walrus, attributes via helper
        delta = "1" if op == "++" else "-1"
        if re.fullmatch(r"[a-z_][a-z0-9_]*", code):
            if post:
                return "((%s := %s + %s) - %s)" % (code, code, delta, delta), t
            return "(%s := %s + %s)" % (code, code, delta), t
        m = re.fullmatch(r"(.+)\.([a-z_][a-z0-9_]*)", code)
        if m:
            return "_j_%sinc(%s, %r, %s)" % ("post" if post else "pre", m.group(1), m.group(2), delta), t
        m = re.fullmatch(r"(.+)\[([^\[\]]+)\]", code)
        if m:
            return "_j_%sinc_idx(%s, %s, %s)" % ("post" if post else "pre", m.group(1), m.group(2), delta), t
        raise Unsupported("increment of %s" % code)

    def prefix(self, e, code, t, op, scope):
        if op == "!":
            return "(not %s)" % code, T_BOOL
        if op == "-":
            if t is not None and t.is_char():
                return "(-ord(%s))" % code, T_INT
            return "(-%s)" % code, t
        if op == "+":
            return code, t
        if op == "~":
            return "(~%s)" % code, t
        if op in ("++", "--"):
            return self.incdec(e, code, t, op, post=False)
        raise Unsupported("prefix " + op)

    # ---------------------------------------------------------------- this / super
    def e_This(self, e, scope):
        code, t = "self", TypeRef(self.cls.name, cls=self.cls)
        if e.qualifier:
            # Outer.this
            hops = 0
            k = self.cls
            while k is not None and k.name != e.qualifier:
                hops += 1
                k = k.outer
            code, t = self.outer_ref(hops), TypeRef(k.name, cls=k) if k else None
        sels = e.selectors or []
        if sels and isinstance(sels[0], T.MethodInvocation) and False:
            pass
        for sel in sels:
            code, t = self.selector(code, t, sel, scope)
        for op in (e.postfix_operators or []):
            code, t = self.incdec(e, code, t, op, post=True)
        for op in reversed(e.prefix_operators or []):
            code, t = self.prefix(e, code, t, op, scope)
        return code, t

    def e_SuperMethodInvocation(self, e, scope):
        args = [self.ex(a, scope) for a in e.arguments]
        k = self.cls
        sup = k.extends.cls if k.extends is not None else None
        ms = sup.find_methods(e.member) if sup is not None else []
        name = attr_name(e.member)
        code = "super(%s, self).%s(%s)" % (self.cls.pyname, name, ", ".join(args))
        t = ms[0].ret if ms else EXT_RET.get(e.member)
        return self.post(e, code, t, scope)

    def e_SuperMemberReference(self, e, scope):
        f = self.cls.sup().find_field(e.member) if self.cls.sup() else None
        return self.post(e, "self." + (self.field_py(f) if f else attr_name(e.member)), f.type if f else None, scope)

    # ---------------------------------------------------------------- method calls
    def e_MethodInvocation(self, e, scope):
        if e.qualifier:
            base, bt, kind = self.resolve_qualifier(e.qualifier, scope, e)
            code, t = self.call(base, bt, kind, e.member, e.arguments, scope, e)
        else:
            code, t = self.unqualified_call(e.member, e.arguments, scope, e)
        return self.post(e, code, t, scope)

    def args(self, args, scope, params=None, varargs=False, ui_callee=True):
        out = []
        types = []
        for a in args:
            c, t = self._expr(a, scope)
            out.append(c)
            types.append(t)
        if varargs and params is not None and not ui_callee:
            # ported sim API: Python *args convention
            if len(args) == len(params) and types[-1] is not None and types[-1].is_array():
                out[-1] = "*" + out[-1]
        elif varargs and params is not None:
            k = len(params) - 1
            passes_array = len(args) == len(params) and (types[-1] is None and out[-1] == "None" or (types[-1] is not None and (types[-1].is_array() or types[-1].name == "null")))
            if not passes_array:
                out = out[:k] + ["[%s]" % ", ".join(out[k:])]
                types = types[:k] + [None]
        # numeric widening to float params where the value is a char
        if params:
            for i, (p, t) in enumerate(zip(params, types)):
                if t is not None and t.is_char() and p is not None and (p.is_int() or p.is_float()):
                    out[i] = "ord(%s)" % out[i]
        return out, types

    def pick_method(self, ms, n):
        if not ms:
            return None
        for m in ms:
            if len(m.params) == n and not m.varargs:
                return m
        for m in ms:
            if m.varargs and n >= len(m.params) - 1:
                return m
        return ms[0]

    def unqualified_call(self, name, args, scope, node):
        if not args and name in ("ordinal", "name") and self.cls is not None and self.cls.kind == "enum" \
                and not self.cls.find_methods(name):
            return "self.%s" % name, (T_INT if name == "ordinal" else T_STRING)
        # method of this class / outer classes / static import
        k = self.cls
        hops = 0
        while k is not None:
            ms = k.find_methods(name)
            if ms:
                m = self.pick_method(ms, len(args))
                a, _ = self.args(args, scope, m.params, m.varargs, m.cls.is_ui)
                if m.static:
                    return "%s.%s(%s)" % (self.need_class(m.cls), attr_name(name), ", ".join(a)), m.ret
                target = "self" if hops == 0 else self.outer_ref(hops)
                return "%s.%s(%s)" % (target, attr_name(name), ", ".join(a)), m.ret
            if not k.static and k.outer is not None:
                hops += 1
            k = k.outer
        for imp in self.cu.imports:
            if imp.static and (imp.path.endswith("." + name) or imp.wildcard):
                cname = imp.path if imp.wildcard else imp.path.rsplit(".", 1)[0]
                ci = self.table.classes.get(cname)
                if ci is not None and name in ci.methods:
                    m = self.pick_method(ci.methods[name], len(args))
                    a, _ = self.args(args, scope, m.params, m.varargs, ci.is_ui)
                    if not ci.is_ui:
                        mod = sim_static(ci.name, attr_name(name))
                        if mod is not None:
                            alias = "_m_" + mod.rsplit(".", 1)[1]
                            self.imports_top.add("import %s as %s" % (mod, alias))
                            return "%s.%s(%s)" % (alias, attr_name(name), ", ".join(a)), m.ret
                    return "%s.%s(%s)" % (self.need_class(ci), attr_name(name), ", ".join(a)), m.ret
        # enum built-ins and calls from static context
        if self.cls is not None and self.cls.kind == "enum" and name in ("values", "valueOf"):
            a, _ = self.args(args, scope)
            return "%s.%s(%s)" % (self.cls.pyname, "values" if name == "values" else "value_of", ", ".join(a)), \
                (TypeRef(self.cls.name, 1, cls=self.cls) if name == "values" else TypeRef(self.cls.name, cls=self.cls))
        # inherited from an external base (ACM GCompound, GObject, ...)
        a, _ = self.args(args, scope)
        if self.method_static:
            return "%s.%s(%s)" % (self.cls.pyname, attr_name(name), ", ".join(a)), EXT_RET.get(name)
        target = "self"
        k = self.cls
        hops = 0
        while k is not None and k.external_base() is None and not k.static and k.outer is not None:
            k = k.outer
            hops += 1
        if hops:
            target = self.outer_ref(hops)
        return "%s.%s(%s)" % (target, attr_name(name), ", ".join(a)), EXT_RET.get(name)

    def call(self, base, bt, kind, name, args, scope, node):
        """base.name(args) with base of static type bt; kind 'value' | 'class' | 'ext' | 'util'."""
        if kind == "util":
            cls = bt.name
            a, _ = self.args(args, scope)
            if (cls, name) in UTIL_CALLS:
                return UTIL_CALLS[(cls, name)](a), self.util_ret(bt, name, len(args))
            return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), self.util_ret(bt, name, len(args))
        if kind == "ext":
            return self.ext_static_call(base, name, args, scope, node)
        if bt is not None and bt.cls is not None and bt.dims == 0:
            ci = bt.cls
            ms = ci.find_methods(name)
            if ms:
                m = self.pick_method(ms, len(args))
                a, _ = self.args(args, scope, m.params, m.varargs, m.cls.is_ui)
                if kind == "class" and m.static:
                    if not ci.is_ui:
                        mod = sim_static(ci.name, attr_name(name))
                        if mod is not None:
                            alias = "_m_" + mod.rsplit(".", 1)[1]
                            self.imports_top.add("import %s as %s" % (mod, alias))
                            return "%s.%s(%s)" % (alias, attr_name(name), ", ".join(a)), m.ret
                    return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), m.ret
                if ci.kind == "enum" and not ci.is_ui and False:
                    pass
                return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), m.ret
            # enum built-ins / Object methods on project types
            if name == "ordinal" and not args:
                return "%s.ordinal" % base, T_INT
            if name == "name" and not args:
                return "%s.name" % base, T_STRING
            if name == "values" and not args and kind == "class":
                return "%s.values()" % base, TypeRef(ci.name, 1, cls=ci)
            if name == "valueOf" and kind == "class":
                return "%s.value_of(%s)" % (base, self.ex(args[0], scope)), TypeRef(ci.name, cls=ci)
            if name == "compareTo":
                return "_j.compare(%s.ordinal, %s.ordinal)" % (base, self.ex(args[0], scope)), T_INT
            if name == "equals":
                other = self.ex(args[0], scope)
                if ci.kind == "enum":
                    return "(%s is %s)" % (base, other), T_BOOL
                return "_j.equals(%s, %s)" % (base, other), T_BOOL
            if name == "hashCode":
                return "_j.hash_code(%s)" % base, T_INT
            if name == "toString":
                return "_j.s(%s)" % base, T_STRING
            if name == "getClass":
                return "type(%s)" % base, TypeRef("Class")
            if name == "getDeclaringClass":
                return "type(%s)" % base, TypeRef("Class")
            # inherited from an external base class
            a, _ = self.args(args, scope)
            return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), EXT_RET.get(name)
        return self.ext_call(base, bt, name, args, scope, node)

    def util_ret(self, bt, name, n):
        ms = bt.cls.methods.get(name) if bt.cls else None
        if ms:
            m = self.pick_method(ms, n)
            return m.ret
        return None

    # ---------------------------------------------------------------- calls on external types
    def ext_call(self, base, bt, name, args, scope, node):
        a, at = self.args(args, scope)
        tn = bt.name if bt is not None else None
        n = len(a)
        if bt is not None and bt.dims > 0:
            if name == "clone":
                return "list(%s)" % base, bt
            if name == "length":
                return "len(%s)" % base, T_INT
        # ---- String
        if tn == "String" or (bt is None and name in ("charAt", "equalsIgnoreCase", "toUpperCase", "toLowerCase", "startsWith", "endsWith", "trim", "isBlank", "toCharArray", "matches", "replaceAll", "codePointAt")):
            r = self.string_call(base, name, a, at, node)
            if r is not None:
                return r
        if tn in ("StringBuilder", "StringBuffer"):
            if name == "toString":
                return "%s.to_string()" % base, T_STRING
            return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), (bt if name in ("append", "insert", "reverse", "delete", "deleteCharAt") else EXT_RET.get(name))
        # ---- functional interfaces
        if tn in FUNCTIONAL or (bt is not None and bt.cls is not None and False):
            return "%s(%s)" % (base, ", ".join(a)), (bt.args[-1] if bt.args and name in ("apply", "get", "call") else (T_BOOL if name == "test" else (T_DOUBLE if "Double" in name or name == "applyAsDouble" else None)))
        if tn == "Comparator":
            if name == "compare":
                return "%s(%s)" % (base, ", ".join(a)), T_INT
            if name == "reversed":
                return "_j.Fn(_j.reversed_cmp(%s))" % base, bt
            if name in ("thenComparing", "thenComparingDouble", "thenComparingInt"):
                other = a[0]
                if name != "thenComparing" or (at[0] is not None and at[0].name != "Comparator" and not other.startswith("_j.Fn(_j.")):
                    if name != "thenComparing":
                        other = "_j.comparing_double(%s)" % other
                return "_j.Fn(_j.then_comparing(%s, %s))" % (base, other), bt
        # ---- collections
        if tn in LIST_TYPES or tn in SET_TYPES or tn in DEQUE_TYPES or tn in MAP_TYPES or (bt is None and name in ("isEmpty", "size")):
            r = self.collection_call(base, bt, tn, name, a, at, node)
            if r is not None:
                return r
        if tn in ("Iterator", "ListIterator"):
            return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), (bt.args[0] if bt.args and name == "next" else (T_BOOL if name == "hasNext" else None))
        if tn in ("Map.Entry", "Entry"):
            if name == "getKey":
                return "%s[0]" % base, bt.args[0] if bt.args else None
            if name == "getValue":
                return "%s[1]" % base, bt.args[1] if len(bt.args) > 1 else None
        if tn in ("Optional", "OptionalDouble", "OptionalInt"):
            return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), None
        if tn == "PrintStream":
            if name in ("println", "print"):
                return "print(%s%s)" % (", ".join("_j.s(%s)" % x for x in a), "" if name == "println" else ", end=''"), T_VOID
            if name == "printf":
                return "print(_j.format(%s), end='')" % ", ".join(a), T_VOID
            if name == "flush":
                return "None", T_VOID
        if name == "printStackTrace" and n == 0:
            return "_j.print_stack_trace(%s)" % base, T_VOID
        if name in ("getMessage", "getLocalizedMessage") and n == 0 and (tn is None or tn.endswith("Exception") or tn.endswith("Error") or tn == "Throwable"):
            return "str(%s)" % base, T_STRING
        # ---- Object methods with unknown receiver
        if name == "equals" and n == 1:
            if tn == "Color":
                return "(%s == %s)" % (base, a[0]), T_BOOL
            return "_j.equals(%s, %s)" % (base, a[0]), T_BOOL
        if name == "hashCode" and n == 0:
            return "_j.hash_code(%s)" % base, T_INT
        if name == "toString" and n == 0:
            return "_j.s(%s)" % base, T_STRING
        if name == "getClass" and n == 0:
            return "type(%s)" % base, TypeRef("Class")
        if tn == "Class":
            if name in ("getSimpleName", "getName"):
                return "%s.__name__" % base, T_STRING
            if name == "isInstance":
                return "isinstance(%s, %s)" % (a[0], base), T_BOOL
            if name in ("getResourceAsStream", "getProtectionDomain", "getResource"):
                return "None", None
        if name == "ordinal" and n == 0:
            return "%s.ordinal" % base, T_INT
        if name == "name" and n == 0 and tn not in ("Font",):
            return "%s.name" % base, T_STRING
        if name == "compareTo" and n == 1:
            return "_j.compare_to(%s, %s)" % (base, a[0]), T_INT
        if name == "contains" and n == 1 and tn is None:
            return "(%s in %s)" % (a[0], base), T_BOOL
        if name == "length" and n == 0 and tn is None:
            return "_j.length(%s)" % base, T_INT
        if tn in ("Integer", "Double", "Long", "Float", "Boolean", "Character"):
            if name in ("intValue", "longValue", "shortValue", "byteValue"):
                return "int(%s)" % base, T_INT
            if name in ("doubleValue", "floatValue"):
                return "float(%s)" % base, T_DOUBLE
            if name in ("booleanValue", "charValue"):
                return base, bt
        ret = EXT_RET.get(name)
        if tn == "Color" and name in ("brighter", "darker"):
            ret = TypeRef("Color")
        if tn in ("Font",) and name == "deriveFont":
            ret = TypeRef("Font")
        if tn in ("GLabel", "Text", "GObject", "GRect", "GOval") and name in ("getWidth", "getHeight"):
            ret = T_DOUBLE
        if tn == "BufferedImage" and name in ("getWidth", "getHeight"):
            ret = T_INT
        if tn in ("FontMetrics",) and name in ("stringWidth", "getAscent", "getDescent", "getHeight", "charWidth", "getLeading"):
            ret = T_INT
        if tn in ("Font",) and name == "getSize":
            ret = T_INT
        if tn in ("Font",) and name == "getSize2D":
            ret = T_FLOAT
        if tn in ("Graphics", "Graphics2D") and name == "create":
            ret = TypeRef("Graphics2D")
        if tn in ("Graphics", "Graphics2D") and name == "getFontMetrics":
            ret = TypeRef("FontMetrics")
        if tn == "GCompound" and name == "getElement":
            ret = TypeRef("GObject")
        if tn in ("Random",) and name == "nextInt":
            ret = T_INT
        if tn in ("Rectangle",) and name in ("getWidth", "getHeight", "getX", "getY", "getCenterX", "getCenterY"):
            ret = T_DOUBLE
        if tn == "Dimension" and name in ("getWidth", "getHeight"):
            ret = T_DOUBLE
        return "%s.%s(%s)" % (base, attr_name(name), ", ".join(a)), ret

    def string_call(self, b, name, a, at, node):
        n = len(a)
        if name == "length":
            return "len(%s)" % b, T_INT
        if name == "charAt":
            return "%s[%s]" % (b, a[0]), T_CHAR
        if name == "equals":
            return "(%s == %s)" % (b, a[0]), T_BOOL
        if name == "equalsIgnoreCase":
            if re.fullmatch(r"'[^']*'|\"[^\"]*\"", b):
                return "(%s is not None and %s.lower() == %s.lower())" % (a[0], a[0], b), T_BOOL
            if re.fullmatch(r"'[^']*'|\"[^\"]*\"", a[0]):
                return "(%s is not None and %s.lower() == %s.lower())" % (b, b, a[0]), T_BOOL
            return "(%s is not None and %s.lower() == %s.lower())" % (a[0], b, a[0]), T_BOOL
        if name == "isEmpty":
            return "(len(%s) == 0)" % b, T_BOOL
        if name == "isBlank":
            return "_j.is_blank(%s)" % b, T_BOOL
        if name == "substring":
            return ("%s[%s:]" % (b, a[0]) if n == 1 else "%s[%s:%s]" % (b, a[0], a[1])), T_STRING
        if name == "indexOf":
            return "_j.index_of(%s, %s)" % (b, ", ".join(a)), T_INT
        if name == "lastIndexOf":
            return "_j.last_index_of(%s, %s)" % (b, a[0]), T_INT
        if name == "contains":
            return "(%s in %s)" % (a[0], b), T_BOOL
        if name == "startsWith":
            return "%s.startswith(%s)" % (b, a[0]), T_BOOL
        if name == "endsWith":
            return "%s.endswith(%s)" % (b, a[0]), T_BOOL
        if name == "toUpperCase":
            return "%s.upper()" % b, T_STRING
        if name == "toLowerCase":
            return "%s.lower()" % b, T_STRING
        if name in ("trim", "strip"):
            return "_j.trim(%s)" % b, T_STRING
        if name == "split":
            return "_j.split(%s, %s)" % (b, ", ".join(a)), TypeRef("String", 1)
        if name == "replace":
            x, y = a
            if at[0] is not None and at[0].is_char():
                pass
            return "%s.replace(%s, %s)" % (b, x, y), T_STRING
        if name == "replaceAll":
            return "_j.replace_all(%s, %s, %s)" % (b, a[0], a[1]), T_STRING
        if name == "matches":
            return "(re.fullmatch(%s, %s) is not None)" % (a[0], b), T_BOOL
        if name == "toCharArray":
            return "list(%s)" % b, TypeRef("char", 1)
        if name == "hashCode":
            return "_j.hash_code(%s)" % b, T_INT
        if name == "compareTo":
            return "_j.compare_to(%s, %s)" % (b, a[0]), T_INT
        if name == "compareToIgnoreCase":
            return "_j.compare_ignore_case(%s, %s)" % (b, a[0]), T_INT
        if name == "repeat":
            return "(%s * %s)" % (b, a[0]), T_STRING
        if name == "toString" or name == "intern":
            return b, T_STRING
        if name == "chars":
            return "[ord(c) for c in %s]" % b, None
        if name == "codePointAt":
            return "ord(%s[%s])" % (b, a[0]), T_INT
        if name == "concat":
            return "(%s + %s)" % (b, a[0]), T_STRING
        if name == "format" or name == "formatted":
            return "_j.format(%s, %s)" % (b, ", ".join(a)), T_STRING
        return None

    def collection_call(self, b, bt, tn, name, a, at, node):
        n = len(a)
        elem = bt.elem() if bt is not None else None
        is_map = tn in MAP_TYPES
        is_set = tn in SET_TYPES
        if name == "size":
            return "len(%s)" % b, T_INT
        if name == "isEmpty":
            return "(len(%s) == 0)" % b, T_BOOL
        if is_map:
            kt = bt.args[0] if bt and bt.args else None
            if name == "get":
                return "%s.get(%s)" % (b, a[0]), elem
            if name == "put":
                return "_j_put(%s, %s, %s)" % (b, a[0], a[1]), elem
            if name == "containsKey":
                return "(%s in %s)" % (a[0], b), T_BOOL
            if name == "getOrDefault":
                return "%s.get(%s, %s)" % (b, a[0], a[1]), elem
            if name == "remove":
                return "%s.pop(%s, None)" % (b, a[0]), elem
            if name == "keySet":
                return "_j.key_set(%s)" % b, TypeRef("Set", args=[kt] if kt else [])
            if name == "values":
                return "_j.values_view(%s)" % b, TypeRef("Collection", args=[elem] if elem else [])
            if name == "entrySet":
                return "_j.entry_set(%s)" % b, TypeRef("Set", args=[TypeRef("Map.Entry", args=list(bt.args))])
            if name == "clear":
                return "%s.clear()" % b, T_VOID
            if name == "containsValue":
                return "(%s in %s.values())" % (a[0], b), T_BOOL
            if name == "putIfAbsent":
                return "%s.setdefault(%s, %s)" % (b, a[0], a[1]), elem
            if name == "computeIfAbsent":
                return "_j_compute_if_absent(%s, %s, %s)" % (b, a[0], a[1]), elem
            if name == "merge":
                return "_j_merge(%s, %s, %s, %s)" % (b, a[0], a[1], a[2]), elem
            if name == "putAll":
                return "%s.update(%s)" % (b, a[0]), T_VOID
            if name == "forEach":
                return "_j_map_for_each(%s, %s)" % (b, a[0]), T_VOID
            return None
        if name == "get" and n == 1:
            return "%s[%s]" % (b, a[0]), elem
        if name == "add":
            if n == 2:
                return "%s.insert(%s, %s)" % (b, a[0], a[1]), T_VOID
            if is_set or tn in DEQUE_TYPES:
                return "%s.add(%s)" % (b, a[0]), T_BOOL
            return "_j_add(%s, %s)" % (b, a[0]), T_BOOL
        if name == "set" and n == 2:
            return "_j_set(%s, %s, %s)" % (b, a[0], a[1]), elem
        if name == "contains":
            return "(%s in %s)" % (a[0], b), T_BOOL
        if name == "clear":
            return "%s.clear()" % b, T_VOID
        if name == "remove" and n == 1:
            if is_set or tn in DEQUE_TYPES:
                return "%s.remove(%s)" % (b, a[0]), T_BOOL
            if at[0] is not None and at[0].is_int() and at[0].name != "Integer":
                return "%s.pop(%s)" % (b, a[0]), elem
            return "_j_remove(%s, %s)" % (b, a[0]), T_BOOL
        if name == "remove" and n == 0 and tn in DEQUE_TYPES:
            return "%s.pop(0)" % b, elem
        if name == "addAll":
            if is_set:
                return "%s.add_all(%s)" % (b, a[0]) if tn != "EnumSet" else "%s.update(%s)" % (b, a[0]), T_BOOL
            return "%s.extend(%s)" % (b, a[0]), T_BOOL
        if name == "indexOf":
            return "_j.index_of(%s, %s)" % (b, a[0]), T_INT
        if name == "sort":
            return "_j.sort(%s, %s)" % (b, a[0] if a else "None"), T_VOID
        if name == "subList":
            return "_j.ArrayList(%s[%s:%s])" % (b, a[0], a[1]), bt
        if name == "iterator":
            return "_j_iter(%s)" % b, TypeRef("Iterator", args=[elem] if elem else [])
        if name == "removeIf":
            return "_j_remove_if(%s, %s)" % (b, a[0]), T_BOOL
        if name == "forEach":
            return "_j_for_each(%s, %s)" % (b, a[0]), T_VOID
        if name == "stream":
            return "_j.Stream(%s)" % b, TypeRef("Stream", args=[elem] if elem else [])
        if name == "toArray":
            return "list(%s)" % b, TypeRef(elem.name if elem else "Object", 1)
        if name in ("getFirst", "peekFirst", "peek", "element"):
            return ("%s[0]" % b if name in ("getFirst", "element") else "(%s[0] if %s else None)" % (b, b)), elem
        if name in ("getLast", "peekLast"):
            return ("%s[-1]" % b if name == "getLast" else "(%s[-1] if %s else None)" % (b, b)), elem
        if name in ("removeFirst", "pollFirst", "poll", "pop"):
            return ("%s.pop(0)" % b if name in ("removeFirst", "pop") else "(%s.pop(0) if %s else None)" % (b, b)), elem
        if name in ("removeLast", "pollLast"):
            return ("%s.pop()" % b if name == "removeLast" else "(%s.pop() if %s else None)" % (b, b)), elem
        if name in ("addFirst", "offerFirst", "push"):
            return "%s.insert(0, %s)" % (b, a[0]), T_VOID
        if name in ("addLast", "offerLast", "offer"):
            return "%s.append(%s)" % (b, a[0]), T_VOID
        if name == "lastIndexOf":
            return "_j.last_index_of(%s, %s)" % (b, a[0]), T_INT
        if name == "containsAll":
            return "all(x in %s for x in %s)" % (b, a[0]), T_BOOL
        if name == "removeAll":
            return "_j_remove_all(%s, %s)" % (b, a[0]), T_BOOL
        if name == "retainAll":
            return "_j_retain_all(%s, %s)" % (b, a[0]), T_BOOL
        if name == "descendingIterator":
            return "iter(list(reversed(%s)))" % b, None
        return None

    def ext_static_call(self, cls, name, args, scope, node):
        a, at = self.args(args, scope)
        n = len(a)
        c = cls.split(".")[-1]
        if c == "Math" or c == "StrictMath":
            if name == "abs":
                return "abs(%s)" % a[0], at[0]
            if name in ("max", "min"):
                rt = T_DOUBLE if any(t is not None and t.is_float() for t in at) else (T_INT if all(t is not None and t.is_int() for t in at) else None)
                if any(t is not None and t.is_float() for t in at) and len(a) == 2:
                    return "_j.d%s(%s, %s)" % (name, a[0], a[1]), T_DOUBLE
                if rt is not None and rt.is_float() and not all(t is not None and t.is_float() for t in at):
                    return "float(%s(%s))" % (name, ", ".join(a)), rt
                return "%s(%s)" % (name, ", ".join(a)), rt
            if name in ("sqrt", "sin", "cos", "tan", "atan", "asin", "acos", "exp", "log", "log10", "sinh", "cosh", "tanh", "hypot", "atan2", "expm1", "log1p"):
                return "math.%s(%s)" % (name, ", ".join(a)), T_DOUBLE
            if name == "pow":
                return "math.pow(%s, %s)" % (a[0], a[1]), T_DOUBLE
            if name == "floor":
                return "float(math.floor(%s))" % a[0], T_DOUBLE
            if name == "ceil":
                return "float(math.ceil(%s))" % a[0], T_DOUBLE
            if name == "round":
                if at[0] is not None and at[0].name == "float":
                    return "_j.jround(%s)" % a[0], T_INT
                return "_j.jround(%s)" % a[0], T_LONG
            if name == "toRadians":
                return "math.radians(%s)" % a[0], T_DOUBLE
            if name == "toDegrees":
                return "math.degrees(%s)" % a[0], T_DOUBLE
            if name == "random":
                self.imports_top.add("import random")
                return "random.random()", T_DOUBLE
            if name == "signum":
                return "_j.signum(%s)" % a[0], T_DOUBLE
            if name == "floorMod":
                return "(%s %% %s)" % (a[0], a[1]), T_INT
            if name == "floorDiv":
                return "(%s // %s)" % (a[0], a[1]), T_INT
            if name == "cbrt":
                return "_j.cbrt(%s)" % a[0], T_DOUBLE
            if name == "rint":
                return "_j.rint(%s)" % a[0], T_DOUBLE
            if name == "clamp":
                return "_j.clamp(%s)" % ", ".join(a), at[0]
            if name == "copySign":
                return "math.copysign(%s, %s)" % (a[0], a[1]), T_DOUBLE
        if c in ("Integer", "Long", "Short", "Byte"):
            if name in ("parseInt", "parseLong", "valueOf") and at and at[0] is not None and at[0].is_string():
                return "int(%s)" % ", ".join(a), T_INT
            if name in ("valueOf",):
                return a[0], T_INT
            if name == "toString":
                return "str(%s)" % a[0], T_STRING
            if name == "compare":
                return "_j.compare(%s, %s)" % (a[0], a[1]), T_INT
            if name in ("max", "min"):
                return "%s(%s)" % (name, ", ".join(a)), T_INT
            if name == "toHexString":
                return "_j.to_hex(%s)" % a[0], T_STRING
            if name == "signum":
                return "_j.compare(%s, 0)" % a[0], T_INT
            if name == "getInteger":
                return "_j.get_integer(%s)" % ", ".join(a), T_INT
            if name == "getLong":
                return "_j.get_long(%s)" % ", ".join(a), T_LONG
            if name == "bitCount":
                return "bin(%s & 0xFFFFFFFF).count('1')" % a[0], T_INT
            if name == "hashCode":
                return "_j.hash_code(%s)" % a[0], T_INT
            if name == "sum":
                return "(%s + %s)" % (a[0], a[1]), T_INT
        if c in ("Double", "Float"):
            if name in ("parseDouble", "parseFloat", "valueOf"):
                return "float(%s)" % a[0], T_DOUBLE
            if name == "compare":
                return "_j.compare(%s, %s)" % (a[0], a[1]), T_INT
            if name == "isNaN":
                return "_j.is_nan(%s)" % a[0], T_BOOL
            if name == "isInfinite":
                return "_j.is_infinite(%s)" % a[0], T_BOOL
            if name == "isFinite":
                return "_j.is_finite(%s)" % a[0], T_BOOL
            if name == "toString":
                return "_j.s(float(%s))" % a[0], T_STRING
            if name in ("max", "min"):
                return "%s(%s)" % (name, ", ".join(a)), T_DOUBLE
            if name == "hashCode":
                return "hash(%s)" % a[0], T_INT
        if c == "Boolean":
            if name == "getBoolean":
                return "_j.get_boolean(%s)" % a[0], T_BOOL
            if name in ("parseBoolean", "valueOf"):
                return "(str(%s).lower() == 'true')" % a[0] if at[0] is not None and at[0].is_string() else a[0], T_BOOL
            if name == "compare":
                return "_j.compare(%s, %s)" % (a[0], a[1]), T_INT
            if name == "toString":
                return "_j.s(%s)" % a[0], T_STRING
        if c == "Character":
            m = {"isDigit": "_j.is_digit", "isLetter": "_j.is_letter", "isLetterOrDigit": "_j.is_letter_or_digit",
                 "isWhitespace": "_j.is_whitespace", "isUpperCase": "_j.is_upper_case", "isLowerCase": "_j.is_lower_case",
                 "toUpperCase": "_j.to_upper_char", "toLowerCase": "_j.to_lower_char"}.get(name)
            if m:
                return "%s(%s)" % (m, a[0]), (T_BOOL if name.startswith("is") else T_CHAR)
            if name == "toString" or name == "valueOf":
                return "_j.s(%s)" % a[0], T_STRING
            if name == "getNumericValue":
                return "int(%s)" % a[0], T_INT
        if c == "String":
            if name == "valueOf" or name == "copyValueOf":
                if at and at[0] is not None and at[0].dims == 1 and at[0].name == "char":
                    return "''.join(%s)" % a[0], T_STRING
                return "_j.s(%s)" % a[0], T_STRING
            if name == "format":
                if at and at[0] is not None and at[0].name == "Locale":
                    a = a[1:]
                return "_j.format(%s)" % ", ".join(a), T_STRING
            if name == "join":
                if n == 2 and at[1] is not None and (at[1].dims or at[1].name in LIST_TYPES or at[1].name in SET_TYPES):
                    return "%s.join(%s)" % (a[0], a[1]), T_STRING
                return "%s.join([%s])" % (a[0], ", ".join(a[1:])), T_STRING
        if c == "System":
            if name == "nanoTime":
                return "_j.nano_time()", T_LONG
            if name == "currentTimeMillis":
                return "_j.current_time_millis()", T_LONG
            if name == "getProperty":
                return "_j.get_property(%s)" % ", ".join(a), T_STRING
            if name == "setProperty":
                return "_j.set_property(%s)" % ", ".join(a), T_STRING
            if name == "clearProperty":
                return "_j.clear_property(%s)" % ", ".join(a), T_STRING
            if name == "getenv":
                return "_j.get_env(%s)" % a[0], T_STRING
            if name == "exit":
                self.imports_top.add("import sys")
                return "sys.exit(%s)" % a[0], T_VOID
            if name == "arraycopy":
                return "_j.array_copy(%s)" % ", ".join(a), T_VOID
            if name == "identityHashCode":
                return "_j.identity_hash(%s)" % a[0], T_INT
            if name == "gc":
                return "None", T_VOID
            if name == "lineSeparator":
                return "'\\n'", T_STRING
        if c == "Objects":
            if name == "equals":
                return "_j.equals(%s, %s)" % (a[0], a[1]), T_BOOL
            if name == "hash":
                return "hash((%s,))" % ", ".join(a), T_INT
            if name == "requireNonNull":
                return a[0], at[0]
            if name == "hashCode":
                return "_j.hash_code(%s)" % a[0], T_INT
            if name == "isNull":
                return "(%s is None)" % a[0], T_BOOL
            if name == "toString":
                return "_j.s(%s)" % a[0], T_STRING
        if c == "Collections":
            if name in ("unmodifiableList", "unmodifiableSet", "unmodifiableMap", "unmodifiableCollection", "synchronizedList", "synchronizedMap"):
                return a[0], at[0]
            if name in ("emptyList", "emptySet"):
                return "_j.ArrayList()", TypeRef("List")
            if name == "emptyMap":
                return "_j.HashMap()", TypeRef("Map")
            if name == "singletonList" or name == "singleton":
                return "_j.ArrayList([%s])" % a[0], TypeRef("List", args=[at[0]] if at[0] else [])
            if name == "sort":
                return "_j.sort(%s)" % ", ".join(a), T_VOID
            if name == "reverse":
                return "%s.reverse()" % a[0], T_VOID
            if name == "shuffle":
                return "_j.shuffle(%s)" % ", ".join(a), T_VOID
            if name == "max":
                return "max(%s)" % a[0], None
            if name == "min":
                return "min(%s)" % a[0], None
            if name == "nCopies":
                return "_j.ArrayList([%s] * %s)" % (a[1], a[0]), TypeRef("List", args=[at[1]] if at[1] else [])
            if name == "addAll":
                return "%s.extend([%s])" % (a[0], ", ".join(a[1:])), T_BOOL
            if name == "swap":
                return "_j_swap(%s)" % ", ".join(a), T_VOID
        if c == "Arrays":
            if name == "asList":
                return "_j.as_list(%s)" % ", ".join(a), TypeRef("List", args=[at[0]] if at and at[0] and not at[0].dims else [])
            if name == "fill":
                return "_j.array_fill(%s)" % ", ".join(a), T_VOID
            if name == "sort":
                if n == 2 and not (at[1] is not None and at[1].is_int()):
                    return "_j.sort(%s, %s)" % (a[0], a[1]), T_VOID
                return "_j.sort_range(%s)" % ", ".join(a), T_VOID
            if name == "copyOf":
                el = at[0].name if at[0] is not None and at[0].dims == 1 else None
                fill = {"int": "0", "long": "0", "short": "0", "byte": "0", "double": "0.0", "float": "0.0", "boolean": "False"}.get(el, "None")
                return "_j.copy_of(%s, %s, %s)" % (a[0], a[1], fill), at[0]
            if name == "copyOfRange":
                return "list(%s[%s:%s])" % (a[0], a[1], a[2]), at[0]
            if name == "toString":
                return "_j.arrays_to_string(%s)" % a[0], T_STRING
            if name == "equals":
                return "_j.arrays_equals(%s, %s)" % (a[0], a[1]), T_BOOL
            if name == "stream":
                return "_j.Stream(%s)" % a[0], TypeRef("Stream")
            if name == "hashCode":
                return "hash(tuple(%s))" % a[0], T_INT
        if c in ("List", "Set") and name == "of":
            return "_j.ArrayList([%s])" % ", ".join(a), TypeRef(c, args=[at[0]] if at and at[0] else [])
        if c == "Map" and name == "of":
            pairs = ", ".join("%s: %s" % (a[i], a[i + 1]) for i in range(0, n, 2))
            return "_j.HashMap({%s})" % pairs, TypeRef("Map")
        if c == "EnumSet":
            self.imports_top.add("from lindefense.jenum import EnumSet")
            if name == "of":
                return "EnumSet.of(%s)" % ", ".join(a), TypeRef("EnumSet", args=[at[0]] if at and at[0] else [])
            if name == "noneOf":
                return "EnumSet.none_of()", TypeRef("EnumSet", args=[at[0]] if at and at[0] else [])
            if name == "allOf":
                return "EnumSet.all_of(%s)" % a[0], TypeRef("EnumSet", args=[at[0]] if at and at[0] else [])
            if name == "copyOf":
                return "EnumSet(%s)" % a[0], TypeRef("EnumSet")
            if name == "complementOf":
                return "EnumSet.complement_of(%s, type(next(iter(%s))))" % (a[0], a[0]), TypeRef("EnumSet")
            if name == "range":
                return "EnumSet(m for m in type(%s) if %s.ordinal <= m.ordinal <= %s.ordinal)" % (a[0], a[0], a[1]), TypeRef("EnumSet")
        if c == "Comparator":
            if name in ("comparingDouble", "comparingInt", "comparingLong"):
                return "_j.Fn(_j.comparing_double(%s))" % a[0], TypeRef("Comparator")
            if name == "comparing":
                return "_j.Fn(_j.comparing(%s))" % ", ".join(a), TypeRef("Comparator")
            if name == "naturalOrder":
                return "_j.Fn(_j.compare_to)", TypeRef("Comparator")
            if name == "reverseOrder":
                return "_j.Fn(_j.reverse_order())", TypeRef("Comparator")
        if c == "Thread":
            if name == "sleep":
                return "_j.thread_sleep(%s)" % a[0], T_VOID
            if name == "currentThread":
                return "None", None
        if c == "Color" and name in ("getHSBColor", "HSBtoRGB", "RGBtoHSB", "decode"):
            return "Color.%s(%s)" % ({"getHSBColor": "get_hsb_color", "HSBtoRGB": "hsb_to_rgb", "RGBtoHSB": "rgb_to_hsb", "decode": "decode"}[name], ", ".join(a)), (TypeRef("Color") if name == "getHSBColor" else (T_INT if name == "HSBtoRGB" else None))
        if c == "Runtime" and name == "getRuntime":
            return "_j.Runtime.get_runtime()", TypeRef("Runtime")
        if c == "Locale":
            return "None", None
        if c in ("SwingUtilities", "EventQueue") and name in ("invokeLater", "invokeAndWait"):
            return "%s()" % a[0], T_VOID
        if c == "Optional":
            return "_j.Optional(%s)" % (a[0] if a else "None"), TypeRef("Optional")
        if c == "Stream":
            return "_j.Stream([%s])" % ", ".join(a), TypeRef("Stream")
        if c == "Files" or c == "Paths" or c == "Path":
            self.warn("java.nio %s.%s" % (c, name), node)
        name_py = self.ext_class(c.split(".")[0])
        if name_py is None:
            self.warn("external static call %s.%s" % (cls, name), node)
            name_py = cls
        else:
            name_py = name_py + cls[len(cls.split(".")[0]):]
        return "%s.%s(%s)" % (name_py, attr_name(name), ", ".join(a)), EXT_RET.get(name)

    # ---------------------------------------------------------------- object creation
    def e_ClassCreator(self, e, scope):
        t = self.ptype(e.type)
        a = None
        if e.body:
            code = self.anon_class(e, t, scope)
            return self.post(e, code, t, scope)
        if t.cls is not None:
            ci = t.cls
            ctor = self.pick_method(ci.ctors, len(e.arguments)) if ci.ctors else None
            a, _ = self.args(e.arguments, scope, ctor.params if ctor else None, ctor.varargs if ctor else False, ci.is_ui)
            ref = self.need_class(ci)
            if not ci.static and ci.outer is not None:
                # inner class: pass the enclosing instance
                hops = 0
                k = self.cls
                while k is not None and k is not ci.outer and ci.outer not in k.all_supers():
                    hops += 1
                    k = k.outer
                a = [self.outer_ref(hops) if not e.qualifier else local_name(e.qualifier)] + a
            code = "%s(%s)" % (ref, ", ".join(a))
            return self.post(e, code, t, scope)
        a, at = self.args(e.arguments, scope)
        name = t.name
        full = e.type.name
        sub = e.type.sub_type
        while sub is not None:
            full += "." + sub.name
            sub = sub.sub_type
        segs = full.split(".")
        while len(segs) > 1 and segs[0][:1].islower():
            segs = segs[1:]
        full = ".".join(segs)
        simple = full.split(".")[-1] if not full.startswith(("Path2D", "Ellipse2D", "Rectangle2D", "Line2D", "Arc2D", "RoundRectangle2D", "Point2D", "QuadCurve2D", "CubicCurve2D", "Map")) else full
        if simple in ("Integer", "Double", "Long", "Float", "Boolean"):
            return self.post(e, a[0], TypeRef(simple), scope)
        if simple in ("String",):
            if not a:
                return self.post(e, "''", T_STRING, scope)
            if at[0] is not None and at[0].dims:
                return self.post(e, "''.join(%s)" % a[0], T_STRING, scope)
            return self.post(e, "_j.s(%s)" % a[0], T_STRING, scope)
        if simple in JRT_CLASSES:
            return self.post(e, "%s(%s)" % (JRT_CLASSES[simple], ", ".join(a)), TypeRef(simple, args=t.args), scope)
        if simple in ("Object",):
            return self.post(e, "object()", TypeRef("Object"), scope)
        if simple in ("Font",) and a:
            pass
        if simple in EXC_MAP or simple.endswith("Exception") or simple.endswith("Error"):
            ex = EXC_MAP.get(simple, "Exception")
            if ex.startswith("("):
                ex = "Exception"
            return self.post(e, "%s(%s)" % (ex, ", ".join(a)), TypeRef(simple), scope)
        if simple in ("Timer",):
            self.warn("javax.swing.Timer", e)
        base = full.split(".")[0]
        py = self.ext_class(base)
        if py is None:
            self.warn("new external %s" % full, e)
            py = base
        code = "%s%s(%s)" % (py, full[len(base):], ", ".join(a))
        return self.post(e, code, TypeRef(full if "." in full and full.split(".")[0] in ("Path2D", "Ellipse2D", "Rectangle2D", "Line2D", "Arc2D", "RoundRectangle2D", "Point2D") else simple, args=t.args), scope)

    def anon_class(self, e, t, scope):
        """Anonymous class: hoisted as a local class definition."""
        self.lam += 1
        name = "_Anon%d" % self.lam
        base = None
        if t.cls is not None:
            base = self.need_class(t.cls)
        else:
            base = self.ext_class(t.name) or "object"
            if t.name in ("ComponentAdapter", "MouseAdapter", "KeyAdapter", "WindowAdapter", "TimerTask"):
                base = "object"
        ci = ClassInfo(name, "class", self.cls, self.cu, e, self.cls.pkg, self.path)
        ci.extends = t if t.cls is not None and t.cls.kind == "class" else None
        ci.implements = [t] if t.cls is not None and t.cls.kind == "interface" else []
        ci.static = False
        ci.local = True
        for m in e.body:
            if isinstance(m, T.MethodDeclaration):
                ci.methods.setdefault(m.name, []).append(MethodInfo(m.name, [self.ptype(p.type) for p in m.parameters], self.ptype(m.return_type), False, False, ci, m))
            elif isinstance(m, T.FieldDeclaration):
                for d in m.declarators:
                    ci.fields[d.name] = FieldInfo(d.name, self.ptype(m.type), False, False, ci, d.initializer)
        lines = Out()
        saved = (self.cls, self.method_static)
        self.cls = ci
        lines.line(0, "class %s(%s):" % (name, base))
        # constructor: pass args to base, capture outer self
        args, _ = self.args(e.arguments, scope)
        lines.line(1, "def __init__(self_, *a):")
        if base != "object":
            lines.line(2, "%s.__init__(self_, *a)" % base)
        lines.line(2, "self_._outer = _outer_self")
        self.emit_field_inits_inline(lines, 2, ci, "self_")
        for m in e.body:
            if isinstance(m, T.MethodDeclaration):
                self.emit_method(lines, 1, ci, m, anon=True)
        self.cls, self.method_static = saved
        self.pending_hoist.append(("_outer_self = self", lines.lines))
        return "%s(%s)" % (name, ", ".join(args))

    def emit_field_inits_inline(self, out, ind, ci, selfname):
        for f in ci.fields.values():
            if f.init is not None and not f.static:
                out.line(ind, "%s.%s = %s" % (selfname, self.field_py(f), self.ex(f.init, Scope())))

    def e_ArrayCreator(self, e, scope):
        t = self.ptype(e.type)
        if e.initializer is not None:
            return self.post(e, self.array_init(e.initializer, scope), TypeRef(t.name, len(e.dimensions), cls=t.cls), scope)
        dims = [self.ex(d, scope) for d in e.dimensions if d is not None]
        total = len(e.dimensions)
        init = {"int": "0", "long": "0", "short": "0", "byte": "0", "double": "0.0", "float": "0.0", "boolean": "False", "char": "'\\x00'"}.get(t.name, "None") if len(dims) == total else "None"
        if len(dims) == 1:
            code = "[%s] * %s" % (init, dims[0])
        else:
            code = "_j.new_array([%s], %s)" % (", ".join(dims), init)
        return self.post(e, "(%s)" % code, TypeRef(t.name, total, cls=t.cls), scope)

    def e_ArrayInitializer(self, e, scope):
        return self.array_init(e, scope), None

    def array_init(self, init, scope):
        items = []
        for x in init.initializers:
            if isinstance(x, T.ArrayInitializer):
                items.append(self.array_init(x, scope))
            else:
                items.append(self.ex(x, scope))
        return "[%s]" % ", ".join(items)

    def e_ClassReference(self, e, scope):
        t = self.ptype(e.type)
        if t.cls is not None:
            return self.need_class(t.cls), TypeRef("Class")
        return (self.ext_class(t.name) or t.name), TypeRef("Class")

    # ---------------------------------------------------------------- operators
    PREC = {"or": 1, "and": 2, "not": 3, "cmp": 4, "|": 5, "^": 6, "&": 7, "<<": 8, ">>": 8, "+": 9, "-": 9, "*": 10,
            "/": 10, "//": 10, "%": 10}

    def e_BinaryOperation(self, e, scope):
        op = e.operator
        if op == "instanceof":
            lc, lt = self._expr(e.operandl, scope)
            t = self.ptype(e.operandr)
            if t.cls is not None:
                ref = self.need_class(t.cls)
            else:
                ref = {"String": "str", "Integer": "int", "Double": "float", "Number": "(int, float)", "Boolean": "bool",
                       "List": "list", "Map": "dict", "Runnable": "_j.Fn"}.get(t.name) or self.ext_class(t.name) or t.name
            return self.post(e, "isinstance(%s, %s)" % (lc, ref), T_BOOL, scope)
        lc, lt = self._expr(e.operandl, scope)
        rc, rt = self._expr(e.operandr, scope)
        code, t = self.binop(op, lc, lt, rc, rt, e)
        return self.post(e, code, t, scope)

    def binop(self, op, lc, lt, rc, rt, node):
        if op == "&&":
            return "(%s and %s)" % (lc, rc), T_BOOL
        if op == "||":
            return "(%s or %s)" % (lc, rc), T_BOOL
        if op == "+" and ((lt is not None and lt.is_string()) or (rt is not None and rt.is_string())):
            return self.concat(lc, lt, rc, rt), T_STRING
        # char -> int in arithmetic / comparison with numbers
        lchar = lt is not None and lt.is_char()
        rchar = rt is not None and rt.is_char()
        if lchar != rchar or (lchar and rchar and op in ("+", "-", "*", "/", "%")):
            if lchar and not (rt is not None and rt.is_string()):
                if not (op in ("==", "!=") and rchar):
                    lc = "ord(%s)" % lc if not re.fullmatch(r"'.'|'\\.'", lc) else str(ord(eval(lc)))
                    lt = T_INT
            if rchar:
                if not (op in ("==", "!=") and lchar):
                    rc = "ord(%s)" % rc if not re.fullmatch(r"'.'|'\\.'", rc) else str(ord(eval(rc)))
                    rt = T_INT
        if op in ("==", "!="):
            pyop = op
            ident = (lc == "None" or rc == "None")
            refcmp = False
            for t in (lt, rt):
                if t is not None and t.cls is not None and t.dims == 0 and t.cls.kind in ("enum", "class", "interface"):
                    refcmp = True
                if t is not None and t.dims == 0 and t.name not in NUMERIC and t.name not in ("boolean", "Boolean", "String", "null", "Color") and t.cls is None:
                    refcmp = True
            if ident or refcmp:
                pyop = "is" if op == "==" else "is not"
            return "(%s %s %s)" % (lc, pyop, rc), T_BOOL
        if op in ("<", ">", "<=", ">="):
            return "(%s %s %s)" % (lc, op, rc), T_BOOL
        num_t = self.num_result(lt, rt)
        if op == "/":
            if lt is not None and rt is not None and lt.is_int() and rt.is_int():
                return "_j.idiv(%s, %s)" % (lc, rc), num_t
            return "(%s / %s)" % (lc, rc), (num_t if num_t is not None else None)
        if op == "%":
            if lt is not None and rt is not None and lt.is_int() and rt.is_int():
                return "_j.imod(%s, %s)" % (lc, rc), num_t
            return "_j.fmod(%s, %s)" % (lc, rc), num_t
        if op == "+":
            if lt is None and rt is None and not re.fullmatch(r"-?\d+(\.\d*)?", lc) and not re.fullmatch(r"-?\d+(\.\d*)?", rc):
                return "_j.add(%s, %s)" % (lc, rc), None
            return "(%s + %s)" % (lc, rc), num_t
        if op in ("-", "*"):
            return "(%s %s %s)" % (lc, op, rc), num_t
        if op in ("&", "|", "^"):
            if (lt is not None and lt.is_bool()) or (rt is not None and rt.is_bool()):
                pyop = {"&": "and", "|": "or", "^": "!="}[op]
                if op in ("&", "|"):
                    # non-short-circuit: both evaluated; bool() keeps the value boolean
                    return "(bool(%s) %s bool(%s))" % (lc, {"&": "&", "|": "|"}[op], rc), T_BOOL
                return "(%s != %s)" % (lc, rc), T_BOOL
            return "(%s %s %s)" % (lc, op, rc), num_t or T_INT
        if op == "<<":
            if lt is not None and lt.name == "long":
                return "_j.i64(%s << %s)" % (lc, rc), T_LONG
            return "_j.shl(%s, %s)" % (lc, rc), T_INT
        if op == ">>":
            return "(%s >> %s)" % (lc, rc), lt or T_INT
        if op == ">>>":
            if lt is not None and lt.name == "long":
                return "_j.ushr64(%s, %s)" % (lc, rc), T_LONG
            return "_j.ushr(%s, %s)" % (lc, rc), T_INT
        raise Unsupported("binary " + op)

    def num_result(self, lt, rt):
        if lt is None or rt is None:
            if lt is not None and lt.is_float():
                return T_DOUBLE
            if rt is not None and rt.is_float():
                return T_DOUBLE
            return None
        if lt.is_float() or rt.is_float():
            return T_DOUBLE
        if lt.is_int() and rt.is_int():
            return T_LONG if "long" in (lt.name, rt.name) or "Long" in (lt.name, rt.name) else T_INT
        if lt.is_numeric() and rt.is_numeric():
            return T_INT
        return None

    def concat(self, lc, lt, rc, rt):
        parts = []
        for c, t in ((lc, lt), (rc, rt)):
            if c.startswith("_j.cat(") and c.endswith(")") and self._balanced(c[7:-1]):
                parts.extend(self.split_args(c[7:-1]))
            elif t is not None and t.is_string() and not c.startswith("_j.cat("):
                parts.append(c)
            else:
                parts.append(c)
        return "_j.cat(%s)" % ", ".join(parts)

    def _balanced(self, s):
        depth = 0
        q = None
        i = 0
        while i < len(s):
            ch = s[i]
            if q:
                if ch == "\\":
                    i += 2
                    continue
                if ch == q:
                    q = None
            elif ch in "'\"":
                q = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth < 0:
                    return False
            i += 1
        return depth == 0

    def split_args(self, s):
        out, depth, q, cur = [], 0, None, []
        i = 0
        while i < len(s):
            ch = s[i]
            if q:
                cur.append(ch)
                if ch == "\\":
                    cur.append(s[i + 1])
                    i += 2
                    continue
                if ch == q:
                    q = None
            elif ch in "'\"":
                q = ch
                cur.append(ch)
            elif ch in "([{":
                depth += 1
                cur.append(ch)
            elif ch in ")]}":
                depth -= 1
                cur.append(ch)
            elif ch == "," and depth == 0:
                out.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
            i += 1
        if cur:
            out.append("".join(cur).strip())
        return out

    def e_TernaryExpression(self, e, scope):
        c = self.ex(e.condition, scope)
        a, at = self._expr(e.if_true, scope)
        b, bt = self._expr(e.if_false, scope)
        t = at if at is not None and at.name != "null" else bt
        if at is not None and bt is not None and at.is_numeric() and bt.is_numeric() and (at.is_float() or bt.is_float()):
            t = T_DOUBLE
        return self.post(e, "(%s if %s else %s)" % (a, c, b), t, scope)

    def e_Cast(self, e, scope):
        t = self.ptype(e.type)
        c, st = self._expr(e.expression, scope)
        if t.dims == 0 and t.name in ("int", "short", "byte"):
            if st is not None and st.is_int() and st.name != "long":
                code = c
            elif st is not None and st.is_char():
                code = "ord(%s)" % c
            else:
                code = "_j.to_int(%s)" % c
            return self.post(e, code, T_INT, scope)
        if t.dims == 0 and t.name == "long":
            if st is not None and st.is_int():
                code = c
            elif st is not None and st.is_char():
                code = "ord(%s)" % c
            else:
                code = "_j.to_long(%s)" % c
            return self.post(e, code, T_LONG, scope)
        if t.dims == 0 and t.name in ("double", "float"):
            if st is not None and st.is_float():
                code = c
            elif st is not None and st.is_char():
                code = "float(ord(%s))" % c
            else:
                code = "float(%s)" % c
            return self.post(e, code, t, scope)
        if t.dims == 0 and t.name == "char":
            if st is not None and st.is_char():
                return self.post(e, c, T_CHAR, scope)
            return self.post(e, "_j.to_char(%s)" % c, T_CHAR, scope)
        return self.post(e, c, t, scope)

    def e_Assignment(self, e, scope):
        raise Unsupported("assignment in expression")

    def e_LambdaExpression(self, e, scope):
        params = []
        inner = Scope(scope)
        for p in e.parameters:
            if isinstance(p, T.FormalParameter) or isinstance(p, T.InferredFormalParameter):
                ty = self.ptype(p.type) if getattr(p, "type", None) is not None else None
                params.append(inner.declare(p.name, ty))
            elif isinstance(p, T.MemberReference):
                params.append(inner.declare(p.member, None))
            else:
                params.append(inner.declare(getattr(p, "name", "x"), None))
        body = e.body
        if isinstance(body, list):
            # block lambda: hoist a def
            self.lam += 1
            fname = "_lam%d" % self.lam
            out = Out()
            out.line(0, "def %s(%s):" % (fname, ", ".join(params)))
            n0 = len(out.lines)
            self.block(out, 1, body, inner)
            if len(out.lines) == n0:
                out.line(1, "pass")
            self.pending_hoist.append((None, out.lines))
            return "_j.Fn(%s)" % fname, TypeRef("Lambda")
        if isinstance(body, T.StatementExpression) or (isinstance(body, T.Expression) and isinstance(body, T.Assignment)):
            raise Unsupported("lambda statement-expression body")
        code = self.ex(body, inner) if not isinstance(body, T.Assignment) else None
        return "_j.Fn(lambda %s: %s)" % (", ".join(params), code), TypeRef("Lambda")

    def e_MethodReference(self, e, scope):
        exp = e.expression
        meth = e.method.member if isinstance(e.method, T.MemberReference) else str(e.method)
        if isinstance(exp, T.This) or (isinstance(exp, T.MemberReference) and exp.member == "this"):
            return "_j.Fn(self.%s)" % attr_name(meth), TypeRef("Lambda")
        if isinstance(exp, T.MemberReference):
            name = (exp.qualifier + "." if exp.qualifier else "") + exp.member
            # Class::method or var::method
            v = scope.lookup(name)
            if v is not None:
                return "_j.Fn(%s.%s)" % (v[0], attr_name(meth)), TypeRef("Lambda")
            ci = self.ctx().resolve_class(name)
            if ci is not None:
                ref = self.need_class(ci)
                if meth == "new":
                    return "_j.Fn(%s)" % ref, TypeRef("Lambda")
                ms = ci.find_methods(meth)
                if ms and not ms[0].static:
                    return "_j.Fn(lambda o, *a: o.%s(*a))" % attr_name(meth), TypeRef("Lambda")
                if not ms and meth in ("ordinal", "name"):
                    return "_j.Fn(lambda o: o.%s)" % meth, TypeRef("Lambda")
                return "_j.Fn(%s.%s)" % (ref, attr_name(meth)), TypeRef("Lambda")
            if name in ("String", "Integer", "Double", "Object", "Objects", "Math"):
                special = {("String", "valueOf"): "_j.s", ("Objects", "nonNull"): "(lambda o: o is not None)",
                           ("Objects", "isNull"): "(lambda o: o is None)", ("Integer", "compare"): "_j.compare",
                           ("Double", "compare"): "_j.compare", ("Object", "toString"): "_j.s",
                           ("String", "length"): "len", ("Math", "abs"): "abs", ("Integer", "sum"): "(lambda a, b: a + b)",
                           ("Double", "sum"): "(lambda a, b: a + b)", ("Integer", "intValue"): "int",
                           ("Double", "doubleValue"): "float", ("Integer", "parseInt"): "int",
                           ("Integer", "max"): "max", ("Integer", "min"): "min", ("Math", "max"): "max",
                           ("Math", "min"): "min", ("Double", "max"): "_j.dmax", ("Double", "min"): "_j.dmin",
                           ("Long", "sum"): "(lambda a, b: a + b)", ("Boolean", "logicalOr"): "(lambda a, b: a or b)"}.get((name, meth))
                if special:
                    return "_j.Fn(%s)" % special, TypeRef("Lambda")
            f, expr = self.find_field_in_scope(name)
            if f is not None:
                return "_j.Fn(%s.%s)" % (expr, attr_name(meth)), TypeRef("Lambda")
            if name in JRT_CLASSES and meth == "new":
                return "_j.Fn(%s)" % JRT_CLASSES[name], TypeRef("Lambda")
            self.warn("method reference %s::%s" % (name, meth), e)
            return "_j.Fn(lambda o, *a: o.%s(*a))" % attr_name(meth), TypeRef("Lambda")
        c = self.ex(exp, scope)
        return "_j.Fn(%s.%s)" % (c, attr_name(meth)), TypeRef("Lambda")

    # ---------------------------------------------------------------- statements
    def block(self, out, ind, stmts, scope):
        for s in stmts:
            self.stmt(out, ind, s, scope)

    def flush_hoist(self, out, ind):
        hs = self.pending_hoist
        self.pending_hoist = []
        for pre, lines in hs:
            if pre:
                out.line(ind, pre)
            for ln in lines:
                out.line(ind, ln)

    def with_hoist(self, out, ind, fn):
        """Translates via fn() -> list of (ind, line); emits hoisted defs first."""
        saved = self.pending_hoist
        self.pending_hoist = []
        lines = fn()
        hs = self.pending_hoist
        self.pending_hoist = saved
        for pre, ls in hs:
            if pre:
                out.line(ind, pre)
            for ln in ls:
                out.line(ind, ln)
        for i, ln in lines:
            out.line(i, ln)

    def stmt(self, out, ind, s, scope):
        label = getattr(s, "label", None)
        if label and isinstance(s, (T.ForStatement, T.WhileStatement, T.DoStatement)):
            s.label = None
            out.line(ind, "try:")
            self.stmt(out, ind + 1, s, scope)
            out.line(ind, "except _j.Break as _brk:")
            out.line(ind + 1, "if _brk.label != %r:" % label)
            out.line(ind + 2, "raise")
            s.label = label
            return
        try:
            m = getattr(self, "s_" + type(s).__name__, None)
            if m is None:
                raise Unsupported("statement %s" % type(s).__name__)
            m(out, ind, s, scope)
        except Unsupported as ex:
            self.warn("UNSUPPORTED %s" % ex, s)
            out.line(ind, "raise NotImplementedError(%r)  # j2py: %s" % (str(ex), str(ex)))
        except Exception as ex:
            import traceback
            tb = traceback.extract_tb(ex.__traceback__)[-1]
            self.warn("CRASH %s: %s (j2py line %s)" % (type(ex).__name__, ex, tb.lineno), s)
            out.line(ind, "raise NotImplementedError('j2py crash')  # j2py: CRASH %s" % type(ex).__name__)

    def s_BlockStatement(self, out, ind, s, scope):
        inner = Scope(scope)
        n0 = len(out.lines)
        self.block(out, ind, s.statements, inner)
        if len(out.lines) == n0:
            out.line(ind, "pass")

    def s_LocalVariableDeclaration(self, out, ind, s, scope):
        base = self.ptype(s.type)
        for d in s.declarators:
            t = TypeRef(base.name, base.dims + len(d.dimensions or []), base.args, base.cls)
            if d.initializer is None:
                py = scope.declare(d.name, t)
                continue

            def go(d=d, t=t):
                if isinstance(d.initializer, T.ArrayInitializer):
                    code, it = self.array_init(d.initializer, scope), t
                else:
                    code, it = self._expr(d.initializer, scope)
                code = self.coerce(code, it, t)
                tt = t
                if t.name in ("Object",) and it is not None:
                    tt = it
                if (t.args == [] and it is not None and it.args and t.name == it.name):
                    tt = it
                py = scope.declare(d.name, tt)
                return [(ind, "%s = %s" % (py, code))]
            self.with_hoist(out, ind, go)

    s_VariableDeclaration = s_LocalVariableDeclaration

    def coerce(self, code, src, dst):
        """Implicit widening: int literal/expr assigned to double stays numerically equal (Python int is fine), but
        char assigned to int needs ord()."""
        if dst is not None and src is not None and dst.dims == 0:
            if (dst.is_int() or dst.is_float()) and src.is_char():
                return "ord(%s)" % code
            if dst.is_float() and src.is_int() and re.fullmatch(r"-?\d+", code):
                return code + ".0"
        return code

    def s_StatementExpression(self, out, ind, s, scope):
        e = s.expression

        def go():
            return [(ind, ln) for ln in self.stmt_expr(e, scope)]
        self.with_hoist(out, ind, go)

    def stmt_expr(self, e, scope):
        if isinstance(e, T.Assignment):
            return self.assignment(e, scope)
        if isinstance(e, (T.MemberReference, T.This, T.MethodInvocation, T.Primary)) and (getattr(e, "postfix_operators", None) or getattr(e, "prefix_operators", None)):
            ops = (e.postfix_operators or []) + (e.prefix_operators or [])
            if len(ops) == 1 and ops[0] in ("++", "--"):
                e2 = _strip_ops(e)
                tgt, tt = self._expr(e2, scope)
                return ["%s %s= 1" % (tgt, "+" if ops[0] == "++" else "-")]
        code, t = self._expr(e, scope)
        return [code]

    def assignment(self, e, scope):
        op = e.type
        val, vt = self._expr(e.value, scope) if not isinstance(e.value, T.Assignment) else (None, None)
        targets = []
        cur = e
        chain_vals = []
        if isinstance(e.value, T.Assignment):
            # a = b = expr
            lines = self.assignment(e.value, scope)
            inner_t, _ = self._expr(e.value.expressionl, scope)
            tgt, tt = self._expr(e.expressionl, scope)
            return lines + ["%s = %s" % (tgt, inner_t)]
        tgt, tt = self._lvalue(e.expressionl, scope)
        if op == "=":
            if isinstance(e.value, T.ArrayInitializer):
                val = self.array_init(e.value, scope)
            val = self.coerce(val, vt, tt)
            if tgt.startswith("_j_put_target:"):
                return [tgt[len("_j_put_target:"):] % val]
            return ["%s = %s" % (tgt, val)]
        bop = op[:-1]
        if bop == "+" and tt is not None and tt.is_string():
            return ["%s = _j.cat(%s, %s)" % (tgt, tgt, val)]
        cur_v, cur_t = tgt, tt
        if bop in ("+", "-", "*") and not (tt is not None and tt.is_char()) and not (vt is not None and vt.is_char()):
            if tt is not None and tt.is_int() and vt is not None and vt.is_float():
                return ["%s = _j.to_int(%s %s %s)" % (tgt, tgt, bop, val)]
            if tt is not None and tt.dims == 0 and tt.name == "long" and bop == "*":
                return ["%s = _j.i64(%s * %s)" % (tgt, tgt, val)]
            return ["%s %s= %s" % (tgt, bop, val)]
        code, rt = self.binop(bop, cur_v, cur_t, val, vt, e)
        if tt is not None and tt.is_int() and rt is not None and rt.is_float():
            code = "_j.to_int(%s)" % code
        if tt is not None and tt.is_char():
            code = "_j.to_char(%s)" % code
        return ["%s = %s" % (tgt, code)]

    def _lvalue(self, e, scope):
        code, t = self._expr(e, scope)
        return code, t

    def s_IfStatement(self, out, ind, s, scope):
        first = True
        cur = s
        while True:
            cond = []

            def go(cur=cur):
                c = self.ex(cur.condition, scope)
                return [(ind, ("if %s:" if first else "elif %s:") % strip_parens(c))]
            if first:
                self.with_hoist(out, ind, go)
            else:
                # hoisting inside elif chains: fall back to nested else/if
                saved = self.pending_hoist
                self.pending_hoist = []
                c = self.ex(cur.condition, scope)
                hs = self.pending_hoist
                self.pending_hoist = saved
                if hs:
                    out.line(ind, "else:")
                    self.if_chain_rest(out, ind + 1, cur, scope)
                    return
                out.line(ind, "elif %s:" % strip_parens(c))
            first = False
            self.body(out, ind + 1, cur.then_statement, scope)
            el = cur.else_statement
            if el is None:
                return
            if isinstance(el, T.IfStatement):
                cur = el
                continue
            out.line(ind, "else:")
            self.body(out, ind + 1, el, scope)
            return

    def if_chain_rest(self, out, ind, s, scope):
        self.s_IfStatement(out, ind, s, scope)

    def body(self, out, ind, s, scope):
        n0 = len(out.lines)
        if isinstance(s, T.BlockStatement):
            self.block(out, ind, s.statements, Scope(scope))
        elif s is not None:
            self.stmt(out, ind, s, Scope(scope))
        if len(out.lines) == n0:
            out.line(ind, "pass")

    def s_WhileStatement(self, out, ind, s, scope):
        saved = self.pending_hoist
        self.pending_hoist = []
        c = self.ex(s.condition, scope)
        hs = self.pending_hoist
        self.pending_hoist = saved
        if hs:
            for pre, ls in hs:
                for ln in ls:
                    out.line(ind, ln)
        out.line(ind, "while %s:" % strip_parens(c))
        self.loop_stack.append(None)
        self.body(out, ind + 1, s.body, scope)
        self.loop_stack.pop()

    def s_DoStatement(self, out, ind, s, scope):
        out.line(ind, "while True:")
        self.loop_stack.append(("do", s.condition, scope))
        self.body(out, ind + 1, s.body, scope)
        self.loop_stack.pop()
        c = self.ex(s.condition, scope)
        out.line(ind + 1, "if not %s:" % c)
        out.line(ind + 2, "break")

    def s_ForStatement(self, out, ind, s, scope):
        ctl = s.control
        inner = Scope(scope)
        if isinstance(ctl, T.EnhancedForControl):
            var = ctl.var
            vt = self.ptype(var.type)
            it, itt = self._expr(ctl.iterable, inner)
            name = var.declarators[0].name
            py = inner.declare(name, vt)
            if itt is not None and itt.dims == 0 and itt.name in MAP_TYPES:
                it = "list(%s.keys())" % it
            self.flush_hoist(out, ind)
            out.line(ind, "for %s in %s:" % (py, it))
            self.loop_stack.append(None)
            self.body(out, ind + 1, s.body, inner)
            self.loop_stack.pop()
            return
        r = self.try_range(ctl, s.body, inner)
        if r is not None:
            var, rng = r
            out.line(ind, "for %s in %s:" % (var, rng))
            self.loop_stack.append(None)
            self.body(out, ind + 1, s.body, inner)
            self.loop_stack.pop()
            return
        # general for -> while
        if ctl.init is not None:
            inits = ctl.init if isinstance(ctl.init, list) else [ctl.init]
            for i in inits:
                if isinstance(i, T.VariableDeclaration) or isinstance(i, T.LocalVariableDeclaration):
                    self.s_LocalVariableDeclaration(out, ind, i, inner)
                else:
                    for ln in self.stmt_expr(i, inner):
                        out.line(ind, ln)
        cond = self.ex(ctl.condition, inner) if ctl.condition is not None else "True"
        updates = []
        for u in (ctl.update or []):
            updates.extend(self.stmt_expr(u, inner))
        out.line(ind, "while %s:" % strip_parens(cond))
        self.loop_stack.append(("for", updates))
        n0 = len(out.lines)
        if isinstance(s.body, T.BlockStatement):
            self.block(out, ind + 1, s.body.statements, Scope(inner))
        else:
            self.stmt(out, ind + 1, s.body, Scope(inner))
        self.loop_stack.pop()
        body_stmts = s.body.statements if isinstance(s.body, T.BlockStatement) else [s.body]
        if not ends_with_jump(list(body_stmts or [])):
            for u in updates:
                out.line(ind + 1, u)
        if len(out.lines) == n0:
            out.line(ind + 1, "pass")

    def try_range(self, ctl, body, scope):
        init = ctl.init
        if init is None or ctl.condition is None or not ctl.update or len(ctl.update) != 1:
            return None
        if not isinstance(init, (T.VariableDeclaration, T.LocalVariableDeclaration)) or len(init.declarators) != 1:
            return None
        if init.type.name not in ("int", "long", "short") or (init.type.dimensions or []):
            return None
        d = init.declarators[0]
        var = d.name
        cond = ctl.condition
        if not isinstance(cond, T.BinaryOperation) or cond.operator not in ("<", "<=", ">", ">="):
            return None
        if not (isinstance(cond.operandl, T.MemberReference) and cond.operandl.member == var and not cond.operandl.qualifier
                and not cond.operandl.selectors and not cond.operandl.postfix_operators and not cond.operandl.prefix_operators):
            return None
        upd = ctl.update[0]
        step = None
        if isinstance(upd, T.MemberReference) and upd.member == var and not upd.qualifier:
            ops = (upd.postfix_operators or []) + (upd.prefix_operators or [])
            if ops == ["++"]:
                step = "1"
            elif ops == ["--"]:
                step = "-1"
        elif isinstance(upd, T.Assignment) and isinstance(upd.expressionl, T.MemberReference) and upd.expressionl.member == var \
                and upd.type in ("+=", "-=") and isinstance(upd.value, T.Literal):
            v = upd.value.value
            if not re.fullmatch(r"\d+", v):
                return None
            step = v if upd.type == "+=" else "-" + v
        if step is None:
            return None
        if step.startswith("-") and cond.operator in ("<", "<="):
            return None
        if not step.startswith("-") and cond.operator in (">", ">="):
            return None
        # loop var must not be assigned in the body; bound must be stable
        if assigns_var(body, var) or not stable_bound(cond.operandr, body):
            return None
        py = scope.declare(var, TypeRef(init.type.name))
        start = self.ex(d.initializer, scope)
        bound = self.ex(cond.operandr, scope)
        bt = None
        if cond.operator == "<=":
            bound = add_one(bound, 1)
        elif cond.operator == ">=":
            bound = add_one(bound, -1)
        if step == "1":
            if start == "0":
                return py, "range(%s)" % strip_parens(bound)
            return py, "range(%s, %s)" % (start, strip_parens(bound))
        return py, "range(%s, %s, %s)" % (start, strip_parens(bound), step)

    def s_ReturnStatement(self, out, ind, s, scope):
        if s.expression is None:
            out.line(ind, "return")
            return

        def go():
            code, t = self._expr(s.expression, scope) if not isinstance(s.expression, T.ArrayInitializer) else (self.array_init(s.expression, scope), None)
            if self.ret_type is not None and t is not None:
                code = self.coerce(code, t, self.ret_type)
            return [(ind, "return " + strip_parens(code))]
        self.with_hoist(out, ind, go)

    def s_BreakStatement(self, out, ind, s, scope):
        if s.goto:
            out.line(ind, "raise _j.Break(%r)" % s.goto)
            return
        if self.switch_depth and self.switch_depth[-1] == len(self.loop_stack):
            out.line(ind, "pass  # break")
            return
        out.line(ind, "break")

    def s_ContinueStatement(self, out, ind, s, scope):
        if s.goto:
            self.warn("labeled continue %s" % s.goto, s)
        top = self.loop_stack[-1] if self.loop_stack else None
        if top is not None and top[0] == "for":
            for u in top[1]:
                out.line(ind, u)
        elif top is not None and top[0] == "do":
            c = self.ex(top[1], top[2])
            out.line(ind, "if not %s:" % c)
            out.line(ind + 1, "break")
        out.line(ind, "continue")

    def s_ThrowStatement(self, out, ind, s, scope):
        out.line(ind, "raise " + self.ex(s.expression, scope))

    def s_Statement(self, out, ind, s, scope):
        out.line(ind, "pass")

    def s_AssertStatement(self, out, ind, s, scope):
        out.line(ind, "assert %s" % self.ex(s.condition, scope))

    def s_SynchronizedStatement(self, out, ind, s, scope):
        self.block(out, ind, s.block, Scope(scope))
        if not s.block:
            out.line(ind, "pass")

    def s_TryStatement(self, out, ind, s, scope):
        if s.resources:
            for r in s.resources:
                rt = self.ptype(r.type)
                code = self.ex(r.value, scope)
                py = scope.declare(r.name, rt)
                out.line(ind, "%s = %s" % (py, code))
        out.line(ind, "try:")
        self.body_block(out, ind + 1, s.block, scope)
        for c in (s.catches or []):
            names = c.parameter.types
            pys = []
            for n in names:
                e = EXC_MAP.get(n.split(".")[-1], "Exception")
                if e.startswith("("):
                    pys.extend(e[1:-1].split(", "))
                else:
                    pys.append(e)
            uniq = []
            for p in pys:
                if p not in uniq:
                    uniq.append(p)
            if "BaseException" in uniq:
                uniq = ["Exception"]
            if "Exception" in uniq:
                uniq = ["Exception"]
            ex_t = uniq[0] if len(uniq) == 1 else "(%s)" % ", ".join(uniq)
            inner = Scope(scope)
            py = inner.declare(c.parameter.name, TypeRef(names[0].split(".")[-1]))
            out.line(ind, "except %s as %s:" % (ex_t, py))
            self.body_block(out, ind + 1, c.block, inner)
        if s.finally_block is not None:
            out.line(ind, "finally:")
            self.body_block(out, ind + 1, s.finally_block, scope)
        if not s.catches and s.finally_block is None:
            out.line(ind, "finally:")
            out.line(ind + 1, "pass")

    def body_block(self, out, ind, stmts, scope):
        n0 = len(out.lines)
        self.block(out, ind, stmts or [], Scope(scope))
        if len(out.lines) == n0:
            out.line(ind, "pass")

    def s_SwitchStatement(self, out, ind, s, scope):
        sel, st = self._expr(s.expression, scope)
        self.flush_hoist(out, ind)
        self.sw += 1
        var = "_sw%d" % self.sw
        out.line(ind, "%s = %s" % (var, sel))
        groups = s.cases
        # fallthrough: merge bodies of groups without terminal jump
        bodies = []
        for i, g in enumerate(groups):
            stmts = list(g.statements)
            bodies.append(stmts)
        first = True
        self.switch_depth.append(len(self.loop_stack))
        for i, g in enumerate(groups):
            labels = g.case
            conds = []
            is_default = False
            for lab in labels:
                if lab == "default" or lab is None:
                    is_default = True
                    continue
                conds.append(self.case_cond(var, st, lab, scope))
            if not labels:
                is_default = True
            stmts = []
            j = i
            while True:
                stmts.extend(bodies[j])
                if bodies[j] and ends_with_jump(bodies[j]):
                    break
                if j + 1 >= len(groups):
                    break
                if not bodies[j]:
                    # empty group falls into the next one: handled by merging labels
                    j += 1
                    continue
                j += 1
            if not g.statements and i + 1 < len(groups):
                # empty case label: its conditions merge with the next group's
                groups[i + 1].case = list(labels) + list(groups[i + 1].case)
                continue
            if is_default and not conds:
                head = "else:" if not first else "if True:"
                default_block = (head, stmts)
                if first:
                    out.line(ind, "if True:")
                else:
                    out.line(ind, "else:")
            else:
                c = " or ".join(conds) if not is_default else "True"
                out.line(ind, ("if %s:" if first else "elif %s:") % c)
            first = False
            n0 = len(out.lines)
            body = list(stmts)
            if body and isinstance(body[-1], T.BreakStatement) and not body[-1].goto:
                body = body[:-1]
            self.block(out, ind + 1, body, Scope(scope))
            if len(out.lines) == n0:
                out.line(ind + 1, "pass")
        self.switch_depth.pop()

    def case_cond(self, var, st, lab, scope):
        if isinstance(lab, str):
            lab = T.MemberReference(member=lab, qualifier="", selectors=[], prefix_operators=[], postfix_operators=[])
        if isinstance(lab, T.MemberReference) and not lab.qualifier and st is not None and st.cls is not None and st.cls.kind == "enum":
            return "%s is %s.%s" % (var, self.need_class(st.cls), lab.member)
        if isinstance(lab, T.MemberReference) and not lab.qualifier and (st is None or st.cls is None) and lab.member[:1].isupper() \
                and scope.lookup(lab.member) is None and self.find_field_in_scope(lab.member)[0] is None:
            return "%s.name == %r" % (var, lab.member)
        c, t = self._expr(lab, scope)
        if st is not None and st.is_char() and t is not None and t.is_int():
            return "ord(%s) == %s" % (var, c)
        return "%s == %s" % (var, c)

    def s_LocalClassDeclaration(self, out, ind, s, scope):
        raise Unsupported("local class")

    def s_ClassDeclaration(self, out, ind, s, scope):
        raise Unsupported("local class declaration")

    # ---------------------------------------------------------------- classes
    def emit_class(self, out, ind, ci):
        self.cls = ci
        node = ci.node
        bases = []
        if ci.kind == "enum":
            self.imports_top.add("from lindefense.jenum import JEnum")
            bases.append("JEnum")
        elif ci.extends is not None:
            if ci.extends.cls is not None:
                bases.append(self.static_ref(ci.extends.cls))
            else:
                bases.append(self.ext_class(ci.extends.name) or ci.extends.name)
        for i in ci.implements:
            if i.cls is not None and ci.kind != "enum":
                bases.append(self.static_ref(i.cls))
        out.line(ind, "class %s%s:" % (ci.name, "(%s)" % ", ".join(bases) if bases else ""))
        doc = node.documentation
        if doc:
            d = clean_doc(doc)
            if d:
                out.line(ind + 1, '"""%s"""' % d.replace('"""', "'''").replace("\\", "\\\\"))
        n0 = len(out.lines)
        body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
        # enum constants
        if ci.kind == "enum":
            for c in node.body.constants:
                saved_static = self.method_static
                self.method_static = True
                self.class_body_init = True
                args = [self.ex(a, Scope()) for a in (c.arguments or [])]
                self.class_body_init = False
                self.method_static = saved_static
                if c.body:
                    self.warn("enum constant body %s" % c.name, c)
                out.line(ind + 1, "%s = (%s)" % (c.name, "".join(a + ", " for a in args)))
        # nested classes (non-enum) first so the class body can reference them; bases before subclasses
        if ci.kind != "enum":
            nested = [ci.inner[m.name] for m in body or [] if isinstance(m, (T.ClassDeclaration, T.InterfaceDeclaration, T.EnumDeclaration))]
            ordered = []

            def visit(n, stack=()):
                if n in ordered or n in stack:
                    return
                for b in ([n.extends] if n.extends is not None else []) + list(n.implements):
                    if b is not None and b.cls is not None and b.cls in nested:
                        visit(b.cls, stack + (n,))
                ordered.append(n)
            for n in nested:
                visit(n)
            self.body_owner.append(ci)
            for n in ordered:
                self.emit_class(out, ind + 1, n)
                self.cls = ci
            self.body_owner.pop()
        # constructor(s) + instance field initialisers
        self.emit_ctors(out, ind + 1, ci)
        # methods (overloads dispatched by arity)
        groups = {}
        for m in body or []:
            if isinstance(m, T.MethodDeclaration):
                groups.setdefault(m.name, []).append(m)
        for name, ms in groups.items():
            inherited = []
            if not all("static" in m.modifiers for m in ms):
                own = {(len(m.parameters), bool(m.parameters) and m.parameters[-1].varargs) for m in ms}
                for c in ci.all_supers()[1:]:
                    for mi in c.methods.get(name, []):
                        sig = (len(mi.params), mi.varargs)
                        if sig not in own and not mi.static and sig not in [(len(x.parameters), False) for x in inherited]:
                            inherited.append(mi.node)
            if len(ms) == 1 and not inherited:
                self.emit_method(out, ind + 1, ci, ms[0])
            else:
                self.emit_overloads(out, ind + 1, ci, name, ms, inherited)
        if "toString" in groups:
            out.line(ind + 1, "def __str__(self):")
            out.line(ind + 2, "return self.to_string()")
        if "equals" in groups and ci.kind != "enum":
            out.line(ind + 1, "def __eq__(self, o):")
            out.line(ind + 2, "return self.equals(o)")
            if "hashCode" in groups:
                out.line(ind + 1, "def __hash__(self):")
                out.line(ind + 2, "return self.hash_code()")
            else:
                out.line(ind + 1, "__hash__ = object.__hash__")
        if len(out.lines) == n0:
            out.line(ind + 1, "pass")
        if ci.kind == "enum":
            # nested classes of an enum go after it (an Enum body would turn them into members)
            for m in body or []:
                if isinstance(m, (T.ClassDeclaration, T.InterfaceDeclaration, T.EnumDeclaration)):
                    self.deferred_nested.append((ci, ci.inner[m.name]))
        self.cls = ci

    def static_ref(self, ci):
        owner = self.body_owner[-1] if self.body_owner else None
        if owner is not None and ci.outer is owner:
            return ci.name
        saved = self.class_body_init
        self.class_body_init = True
        r = self.need_class(ci)
        self.class_body_init = saved
        return r

    def emit_ctors(self, out, ind, ci):
        node = ci.node
        body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
        ctors = [m for m in body or [] if isinstance(m, T.ConstructorDeclaration)]
        inst_fields = []
        for m in body or []:
            if isinstance(m, T.FieldDeclaration) and "static" not in m.modifiers and ci.kind != "interface":
                for d in m.declarators:
                    inst_fields.append((m, d))
        init_blocks = [m for m in body or [] if isinstance(m, list) or (isinstance(m, T.BlockStatement) and not getattr(m, "static", False))]
        outer_param = not ci.static and ci.outer is not None
        if ci.kind == "enum":
            if not ctors and not inst_fields:
                return
            # JEnum: _init(*args)
            ctor = ctors[0] if ctors else None
            self.method_static = False
            scope = Scope()
            params = [scope.declare(p.name, self.ptype(p.type)) for p in (ctor.parameters if ctor else [])]
            out.line(ind, "def _init(self%s):" % "".join(", " + p for p in params))
            self.emit_field_defaults(out, ind + 1, ci, inst_fields)
            self.emit_field_inits(out, ind + 1, ci, inst_fields, scope)
            if ctor:
                self.ret_type = None
                self.block(out, ind + 1, ctor.body, scope)
            out.line(ind + 1, "pass")
            return
        if not ctors and not inst_fields and not outer_param and not init_blocks:
            return
        if not ctors:
            out.line(ind, "def __init__(self%s):" % (", _outer" if outer_param else ""))
            if outer_param:
                out.line(ind + 1, "self._outer = _outer")
            self.emit_field_defaults(out, ind + 1, ci, inst_fields)
            self.super_init_default(out, ind + 1, ci)
            self.emit_field_inits(out, ind + 1, ci, inst_fields, Scope())
            out.line(ind + 1, "pass")
            return
        if len(ctors) == 1:
            self.emit_ctor(out, ind, ci, ctors[0], "__init__", inst_fields, outer_param)
            return
        # overloaded constructors
        names = []
        for k, c in enumerate(ctors):
            nm = "_init_%d" % k
            names.append((nm, c))
            self.emit_ctor(out, ind, ci, c, nm, inst_fields, outer_param, sub=True)
        out.line(ind, "def __init__(self, *a):")
        self.emit_dispatch(out, ind + 1, ci, [(nm, c) for nm, c in names], "self.%s(*a)", outer_param)

    def super_init_default(self, out, ind, ci):
        if ci.extends is not None:
            base = self.need_class(ci.extends.cls) if ci.extends.cls is not None else (self.ext_class(ci.extends.name) or ci.extends.name)
            if ci.extends.cls is not None and not ci.extends.cls.static and ci.extends.cls.outer is not None:
                out.line(ind, "%s.__init__(self, self._outer)" % base)
            else:
                out.line(ind, "%s.__init__(self)" % base)

    def emit_ctor(self, out, ind, ci, c, name, inst_fields, outer_param, sub=False):
        self.method_static = False
        self.in_ctor = True
        self.ret_type = None
        scope = Scope()
        params = []
        for p in c.parameters:
            py = scope.declare(p.name, TypeRef(self.ptype(p.type).name, self.ptype(p.type).dims + (1 if p.varargs else 0), cls=self.ptype(p.type).cls))
            params.append(py)
        sig = ", ".join(["self"] + (["_outer"] if outer_param else []) + params)
        out.line(ind, "def %s(%s):" % (name, sig))
        doc = c.documentation
        if outer_param:
            out.line(ind + 1, "self._outer = _outer")
        self.emit_field_defaults(out, ind + 1, ci, inst_fields)
        stmts = list(c.body or [])
        first = stmts[0] if stmts else None
        explicit = None
        if isinstance(first, T.StatementExpression) and isinstance(first.expression, T.ExplicitConstructorInvocation):
            explicit = "this"
        elif isinstance(first, T.StatementExpression) and isinstance(first.expression, T.SuperConstructorInvocation):
            explicit = "super"
        if explicit == "this":
            inv = first.expression
            args, _ = self.args(inv.arguments, scope)
            self.flush_hoist(out, ind + 1)
            # call the matching sibling constructor
            ctors = [m for m in (ci.node.body or []) if isinstance(m, T.ConstructorDeclaration)]
            target = self.pick_ctor_index(ci, ctors, len(inv.arguments), inv.arguments, scope)
            out.line(ind + 1, "self._init_%d(%s)" % (target, ", ".join(([] if not outer_param else ["_outer"]) + args)))
            stmts = stmts[1:]
        else:
            if explicit == "super":
                inv = first.expression
                sup = ci.extends
                args, _ = self.args(inv.arguments, scope)
                self.flush_hoist(out, ind + 1)
                if sup is not None and sup.cls is not None:
                    base = self.need_class(sup.cls)
                    if not sup.cls.static and sup.cls.outer is not None:
                        args = ["self._outer"] + args
                else:
                    base = self.ext_class(sup.name) if sup is not None else "object"
                out.line(ind + 1, "%s.__init__(%s)" % (base, ", ".join(["self"] + args)))
                stmts = stmts[1:]
            else:
                self.super_init_default(out, ind + 1, ci)
            self.emit_field_inits(out, ind + 1, ci, inst_fields, Scope())
        self.block(out, ind + 1, stmts, scope)
        out.line(ind + 1, "pass") if not stmts and not inst_fields else None
        self.in_ctor = False

    def pick_ctor_index(self, ci, ctors, n, args, scope):
        cands = [i for i, c in enumerate(ctors) if len(c.parameters) == n]
        if len(cands) == 1:
            return cands[0]
        if not cands:
            return 0
        # same arity: choose by argument types
        _, ats = self.args(args, scope)
        best, score = cands[0], -1
        for i in cands:
            sc = 0
            for p, t in zip(ctors[i].parameters, ats):
                pt = self.ptype(p.type)
                if t is not None and (pt.name == t.name or (pt.is_float() and t.is_numeric()) or (pt.is_int() and t.is_int())):
                    sc += 1
            if sc > score:
                best, score = i, sc
        return best

    def emit_field_defaults(self, out, ind, ci, inst_fields):
        """Java zero-initialises every field before any constructor runs (a base constructor may call an
        overridden method that sets a subclass field): emitted before the super call."""
        for m, d in inst_fields:
            fi = ci.fields[d.name]
            if d.initializer is not None:
                continue
            ty = fi.type
            dflt = "None"
            if ty.dims == 0:
                if ty.is_int():
                    dflt = "0"
                elif ty.is_float():
                    dflt = "0.0"
                elif ty.is_bool():
                    dflt = "False"
                elif ty.is_char():
                    dflt = "'\\x00'"
            out.line(ind, "self.%s = %s" % (self.field_py(fi), dflt))

    def emit_field_inits(self, out, ind, ci, inst_fields, scope):
        for m, d in inst_fields:
            fi = ci.fields[d.name]
            if d.initializer is None:
                continue
            if d.initializer is None:
                ty = fi.type
                dflt = "None"
                if ty.dims == 0:
                    if ty.is_int():
                        dflt = "0"
                    elif ty.is_float():
                        dflt = "0.0"
                    elif ty.is_bool():
                        dflt = "False"
                    elif ty.is_char():
                        dflt = "'\\x00'"
                out.line(ind, "self.%s = %s" % (self.field_py(fi), dflt))
                continue

            def go(fi=fi, d=d):
                if isinstance(d.initializer, T.ArrayInitializer):
                    code = self.array_init(d.initializer, scope)
                else:
                    code, it = self._expr(d.initializer, scope)
                    code = self.coerce(code, it, fi.type)
                return [(ind, "self.%s = %s" % (self.field_py(fi), code))]
            self.with_hoist(out, ind, go)

    def emit_dispatch(self, out, ind, ci, items, call_fmt, outer_param, static=False, super_call=None):
        """items: [(pyname, MethodDeclaration|ConstructorDeclaration)]; dispatch by arity, then by types.
        pyname "__super__" dispatches to the inherited implementation (super_call)."""
        fmt = call_fmt

        def call_of(nm):
            return super_call if nm == "__super__" else fmt % nm
        by_n = {}
        for nm, m in items:
            va = bool(m.parameters) and m.parameters[-1].varargs
            by_n.setdefault(-1 if va else len(m.parameters), []).append((nm, m))
        off = 1 if outer_param else 0
        first = True
        for n, cands in sorted(by_n.items(), key=lambda kv: kv[0] if kv[0] >= 0 else 999):
            if n < 0:
                continue
            if len(cands) == 1:
                out.line(ind, "%s len(a) == %d:" % ("if" if first else "elif", n + off))
                out.line(ind + 1, "return " + call_of(cands[0][0]))
            else:
                out.line(ind, "%s len(a) == %d:" % ("if" if first else "elif", n + off))
                for k, (nm, m) in enumerate(cands):
                    cond = self.type_test(m, off)
                    if k == len(cands) - 1:
                        out.line(ind + 1, "return " + call_of(nm))
                    else:
                        out.line(ind + 1, "if %s:" % cond)
                        out.line(ind + 2, "return " + call_of(nm))
            first = False
        va = by_n.get(-1)
        if va:
            out.line(ind, "return " + call_of(va[0][0]))
        else:
            out.line(ind, "raise TypeError('no overload for %d args' % len(a))")

    def type_test(self, m, off):
        conds = []
        for i, p in enumerate(m.parameters):
            pt = self.ptype(p.type)
            x = "a[%d]" % (i + off)
            if pt.dims:
                conds.append("isinstance(%s, (list, tuple))" % x)
            elif pt.name in ("int", "long", "short", "byte"):
                conds.append("(isinstance(%s, int) and not isinstance(%s, bool))" % (x, x))
            elif pt.name in ("double", "float"):
                conds.append("isinstance(%s, (int, float))" % x)
            elif pt.name == "boolean":
                conds.append("isinstance(%s, bool)" % x)
            elif pt.name == "String":
                conds.append("isinstance(%s, str)" % x)
            elif pt.name == "char":
                conds.append("isinstance(%s, str)" % x)
            elif pt.cls is not None:
                conds.append("isinstance(%s, %s)" % (x, self.need_class(pt.cls)))
            elif pt.name in JAWT_NAMES or pt.name in ACM_NAMES:
                conds.append("isinstance(%s, %s)" % (x, pt.name))
        return " and ".join(conds) or "True"

    def emit_overloads(self, out, ind, ci, name, ms, inherited=()):
        py = attr_name(name)
        items = []
        static = all("static" in m.modifiers for m in ms)
        for k, m in enumerate(ms):
            nm = "_%s_%d" % (py, k)
            self.emit_method(out, ind, ci, m, pyname=nm)
            items.append((nm, m))
        for m in inherited:
            items.append(("__super__", m))
        if static:
            out.line(ind, "@staticmethod")
            out.line(ind, "def %s(*a):" % py)
            self.emit_dispatch(out, ind + 1, ci, items, ci.pyname + ".%s(*a)", False)
        else:
            out.line(ind, "def %s(self, *a):" % py)
            sup = "super(%s, self).%s(*a)" % (ci.pyname, py)
            self.emit_dispatch(out, ind + 1, ci, items, "self.%s(*a)", False, super_call=sup)

    def emit_method(self, out, ind, ci, m, pyname=None, anon=False):
        static = "static" in m.modifiers
        self.method_static = static
        self.ret_type = self.ptype(m.return_type)
        scope = Scope()
        params = []
        for p in m.parameters:
            pt = self.ptype(p.type)
            if p.varargs:
                pt = TypeRef(pt.name, pt.dims + 1, pt.args, pt.cls)
            py = scope.declare(p.name, pt)
            params.append(py)
        name = pyname or attr_name(m.name)
        if static:
            out.line(ind, "@staticmethod")
            out.line(ind, "def %s(%s):" % (name, ", ".join(params)))
        else:
            out.line(ind, "def %s(%s):" % (name, ", ".join([("self" if not anon else "self")] + params)))
        doc = m.documentation
        if doc:
            d = clean_doc(doc)
            if d:
                out.line(ind + 1, '"""%s"""' % d.replace('"""', "'''").replace("\\", "\\\\"))
        n0 = len(out.lines)
        if m.body is None:
            out.line(ind + 1, "raise NotImplementedError")
        else:
            self.block(out, ind + 1, m.body, scope)
        if len(out.lines) == n0:
            out.line(ind + 1, "pass")
        self.method_static = False

    # ---------------------------------------------------------------- static initialisation (after the classes)
    def emit_statics(self, out, ci):
        self.cls = ci
        self.method_static = True
        self.class_body_init = True
        node = ci.node
        body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
        for m in body or []:
            if isinstance(m, (T.FieldDeclaration, T.ConstantDeclaration)) and ("static" in m.modifiers or ci.kind == "interface"):
                for d in m.declarators:
                    fi = ci.fields[d.name]
                    if d.initializer is None:
                        dflt = "None"
                        if fi.type.dims == 0:
                            if fi.type.is_int():
                                dflt = "0"
                            elif fi.type.is_float():
                                dflt = "0.0"
                            elif fi.type.is_bool():
                                dflt = "False"
                        out.line(0, "%s.%s = %s" % (ci.pyname, self.field_py(fi), dflt))
                        continue

                    def go(fi=fi, d=d):
                        if isinstance(d.initializer, T.ArrayInitializer):
                            code = self.array_init(d.initializer, Scope())
                        else:
                            code, it = self._expr(d.initializer, Scope())
                            code = self.coerce(code, it, fi.type)
                        return [(0, "%s.%s = %s" % (ci.pyname, self.field_py(fi), code))]
                    self.with_hoist(out, 0, go)
            elif isinstance(m, list) or (isinstance(m, T.BlockStatement) and getattr(m, "static", False)):
                pass
        # static initializer blocks
        for m in _static_blocks(node):
            self.sinit += 1
            fname = "_static_init_%d" % self.sinit
            out.line(0, "def %s():" % fname)
            n0 = len(out.lines)
            self.block(out, 1, m, Scope())
            if len(out.lines) == n0:
                out.line(1, "pass")
            out.line(0, "%s()" % fname)
        self.class_body_init = False
        self.method_static = False
        for inner in ci.inner.values():
            self.emit_statics(out, inner)

    # ---------------------------------------------------------------- module
    def generate(self):
        out = Out()
        self.pending_hoist = []
        self.loop_stack = []
        self.switch_depth = []
        self.sw = 0
        self.sinit = 0
        self.ret_type = None
        self.deferred_nested = []
        self.body_owner = []
        body = Out()
        for ci in self.tops:
            self.emit_class(body, 0, ci)
            body.line(0, "")
            body.line(0, "")
        while self.deferred_nested:
            outer, inner = self.deferred_nested.pop(0)
            tmp = Out()
            self.emit_class(tmp, 0, inner)
            body.lines.extend(tmp.lines)
            body.line(0, "%s.%s = %s" % (outer.pyname, inner.name, inner.name))
            body.line(0, "")
        statics = Out()
        for ci in self.tops:
            self.emit_statics(statics, ci)
        rel = os.path.relpath(self.path, self.gen.java_root)
        out.line(0, '"""Lindefense %s (ported from src/lindefense/%s)."""' % (self.tops[0].name if self.tops else "", rel))
        out.line(0, "# Generated by j2py from the Java UI.")
        out.line(0, "# j2py-managed: regenerated from Java until this line is removed (remove it when editing by hand).")
        out.line(0, "import math")
        out.line(0, "import re")
        out.line(0, "")
        out.line(0, "from lindefense.ui import jrt as _j")
        out.line(0, "from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,")
        out.line(0, "                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,")
        out.line(0, "                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)")
        out.line(0, "from lindefense.ui.jawt import *  # noqa: F401,F403")
        out.line(0, "from lindefense.ui.acm import *  # noqa: F401,F403")
        for imp in sorted(self.imports_top):
            out.line(0, imp)
        out.line(0, "")
        out.line(0, "")
        out.lines.extend(body.lines)
        if self.imports_bottom - self.imports_top:
            out.line(0, "")
            out.line(0, "# deferred imports (after the class definitions, so import cycles resolve)")
            for imp in sorted(self.imports_bottom - self.imports_top):
                out.line(0, imp + "  # noqa: E402")
            out.line(0, "")
        out.lines.extend(statics.lines)
        for ci in self.tops:
            if any("static" in m.modifiers for m in ci.node.methods if m.name == "main") if hasattr(ci.node, "methods") else False:
                out.line(0, "")
                out.line(0, "")
                out.line(0, "if __name__ == \"__main__\":")
                out.line(1, "import sys")
                out.line(1, "%s.main(sys.argv[1:])" % ci.name)
                break
        text = "\n".join(out.lines).rstrip() + "\n"
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text


# ====================================================================== helpers
def _strip_ops(e):
    import copy
    e2 = copy.copy(e)
    e2.postfix_operators = []
    e2.prefix_operators = []
    return e2


def _static_blocks(node):
    out = []
    body = node.body if not isinstance(node, T.EnumDeclaration) else (node.body.declarations if node.body else [])
    for m in body or []:
        if isinstance(m, list):
            out.append(m)
    return out


def ends_with_jump(stmts):
    if not stmts:
        return False
    s = stmts[-1]
    if isinstance(s, (T.BreakStatement, T.ReturnStatement, T.ContinueStatement, T.ThrowStatement)):
        return True
    if isinstance(s, T.BlockStatement):
        return ends_with_jump(s.statements)
    return False


def assigns_var(node, var):
    for _, n in node.filter(T.Assignment) if hasattr(node, "filter") else []:
        if isinstance(n.expressionl, T.MemberReference) and n.expressionl.member == var and not n.expressionl.qualifier:
            return True
    for _, n in node.filter(T.MemberReference) if hasattr(node, "filter") else []:
        if n.member == var and not n.qualifier and (n.postfix_operators or (n.prefix_operators and any(o in ("++", "--") for o in n.prefix_operators))):
            return True
    return False


def stable_bound(e, body):
    """True if the loop bound is evaluated to the same value on every iteration (for range())."""
    if isinstance(e, T.Literal):
        return True
    if isinstance(e, T.MemberReference):
        if e.selectors:
            return False
        if e.qualifier and e.member == "length":
            return True
        if e.member[:1].isupper() or (e.qualifier and e.member.isupper()):
            return True
        if not e.qualifier and not assigns_var(body, e.member):
            return True
        return False
    if isinstance(e, T.BinaryOperation):
        return stable_bound(e.operandl, body) and stable_bound(e.operandr, body)
    if isinstance(e, T.MethodInvocation) and e.member == "size" and e.qualifier and not e.selectors:
        q = e.qualifier.split(".")[-1]
        for _, n in body.filter(T.MethodInvocation) if hasattr(body, "filter") else []:
            if n.qualifier and n.qualifier.split(".")[-1] == q and n.member in ("add", "remove", "clear", "addAll", "removeIf", "set", "removeAll", "retainAll", "poll", "pop", "push", "offer"):
                return False
        return True
    if isinstance(e, T.MethodInvocation) and e.member in ("min", "max") and e.qualifier == "Math":
        return all(stable_bound(a, body) for a in e.arguments)
    return False


def add_one(code, k):
    m = re.fullmatch(r"(-?\d+)", code)
    if m:
        return str(int(code) + k)
    return "%s %s 1" % (code, "+" if k > 0 else "-")


def strip_parens(c):
    if c.startswith("(") and c.endswith(")"):
        inner = c[1:-1]
        depth = 0
        q = None
        for i, ch in enumerate(inner):
            if q:
                if ch == q and inner[i - 1] != "\\":
                    q = None
                continue
            if ch in "'\"":
                q = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    return c
        return inner
    return c


def clean_doc(doc):
    d = re.sub(r"^/\*\*|\*/$", "", doc.strip())
    lines = [re.sub(r"^\s*\* ?", "", ln) for ln in d.splitlines()]
    text = "\n".join(lines).strip()
    text = re.sub(r"\{@(?:link|code|linkplain|value) ([^}]*)\}", r"\1", text)
    text = re.sub(r"</?(p|h3|ul|li|b|i|em|pre|code)>", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def decode_java_string(s):
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u":
                j = i + 1
                while j < len(s) and s[j] == "u":
                    j += 1
                out.append(chr(int(s[j:j + 4], 16)))
                i = j + 4
                continue
            m = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "0": "\0", "'": "'", '"': '"', "\\": "\\", "s": " "}
            if n in "01234567" and n != "0" or (n == "0" and i + 2 < len(s) and s[i + 2] in "01234567"):
                j = i + 1
                k = j
                while k < len(s) and k < j + 3 and s[k] in "01234567":
                    k += 1
                out.append(chr(int(s[j:k], 8)))
                i = k
                continue
            out.append(m.get(n, n))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


AUDIO_LOGIC = {"Sfx.java", "Track.java", "Throttle.java", "MusicDirector.java", "SfxFamilies.java"}
SKIP_FILES = {"WindowEffects.java", "WindowGrab.java", "AutoPlayer.java", "Main.java", "Assets.java"}


class Gen:
    def __init__(self, java_root, py_root):
        self.java_root, self.py_root = java_root, py_root
        self.table = Table()
        collect(self.table, java_root)
        scan_python(py_root)
        self.field_renames = {}
        self._compute_field_renames()

    def ui_module_of(self, top):
        rel = os.path.relpath(top.path, self.java_root)
        parts = rel[:-5].split(os.sep)
        pkg = parts[:-1]
        if pkg and pkg[0] == "ui":
            return "lindefense." + ".".join(pkg + [module_name(parts[-1])])
        if pkg and pkg[0] in ("audio", "tools"):
            return "lindefense." + ".".join(pkg + [module_name(parts[-1])])
        return "lindefense." + module_name(parts[-1])

    def _compute_field_renames(self):
        """Instance fields that clash with a method name in the class hierarchy (Python shares one namespace)."""
        import importlib
        sys.path.insert(0, self.py_root)
        ext_methods = {}
        try:
            acm = importlib.import_module("lindefense.ui.acm")
            jawt = importlib.import_module("lindefense.ui.jawt")
            for mod in (acm, jawt):
                for n in dir(mod):
                    o = getattr(mod, n)
                    if isinstance(o, type):
                        ext_methods[n] = {a for a in dir(o) if not a.startswith("__")}
        except Exception as ex:
            print("warning: cannot import acm/jawt for field clash analysis:", ex)
        for ci in self.table.classes.values():
            if not ci.is_ui:
                continue
            names = set()
            for c in ci.all_supers():
                for mn in c.methods:
                    names.add(attr_name(mn))
            base = ci.external_base()
            if base:
                names |= ext_methods.get(base, set())
            for c in ci.all_supers():
                if c.kind == "enum":
                    names |= {"name", "value", "ordinal", "values", "value_of"}
            for f in ci.fields.values():
                py = attr_name(f.name)
                if py in names or (base and ("_" + py) in ext_methods.get(base, set())):
                    self.field_renames[(ci.qual, f.name)] = "f_" + py

    def field_pyname(self, fi):
        k = (fi.cls.qual, fi.name)
        if k in self.field_renames:
            return self.field_renames[k]
        if fi.cls.kind == "enum" and fi.name in fi.cls.enum_consts:
            return fi.name
        # sim classes: plain snake case (already ported)
        return attr_name(fi.name)

    def run(self, only=None):
        warnings = []
        for path, (cu, tops) in sorted(self.table.cus.items()):
            if not tops or not tops[0].is_ui:
                continue
            relp = os.path.relpath(path, self.java_root)
            if (relp.startswith("audio" + os.sep) and os.path.basename(path) not in AUDIO_LOGIC) or os.path.basename(path) in SKIP_FILES:
                continue
            base = os.path.basename(path)
            if only and base not in only:
                continue
            fg = FileGen(self, path, cu, tops)
            try:
                text = fg.generate()
            except Unsupported as ex:
                warnings.append("%s: FAILED %s" % (base, ex))
                continue
            mod = self.ui_module_of(tops[0])
            dst = os.path.join(self.py_root, *mod.split(".")) + ".py"
            if os.path.exists(dst):
                head = open(dst, encoding="utf-8").read(600)
                if "j2py-managed" not in head:
                    warnings.append("%s: kept hand-edited %s" % (base, dst))
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            for d in range(len(mod.split(".")) - 1):
                pkg = os.path.join(self.py_root, *mod.split(".")[:d + 1], "__init__.py")
                if not os.path.exists(pkg):
                    open(pkg, "w").close()
            import j2py_patches
            rel = os.path.relpath(dst, self.py_root).replace(os.sep, "/")
            text = j2py_patches.apply(rel, text, fg.warnings.append)
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(text)
            warnings.extend(fg.warnings)
        return warnings


if __name__ == "__main__":
    java_root, py_root = sys.argv[1], sys.argv[2]
    only = set(sys.argv[3:]) or None
    g = Gen(java_root, py_root)
    ws = g.run(only)
    for w in ws:
        print(w)
    print("%d warnings" % len(ws))
