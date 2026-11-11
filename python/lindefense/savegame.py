"""Save & Continue: one autosave slot holding an exact snapshot of a running match.

The snapshot is the whole simulation object graph (the Game and everything it reaches: map and its mechanics,
towers with their tiers, targeting, counters and cooldowns, enemies, projectiles, effects and scheduled tasks, the
wave manager, Patch Notes, Breaking News, the RNG streams, ...), pickled. A field-by-field serializer would have to
name several hundred attributes across ~60 classes and be kept in step with every future change; one missed timer
and a continued run silently drifts from the uninterrupted one. Pickling the graph captures every attribute by
construction, so a run saved at wave N, loaded and played on is bit-identical to the same run played straight
through. What pickle cannot do on its own is handled here:

  * Shared static data (catalog TowerDefs and their stats / upgrades / abilities, the stateless tower behaviours,
    the campaign's WaveDefs, Mods.NONE, the persistent Hero Store collection) is written as a symbolic reference
    and resolved to the live singleton on load, so identity checks and the saved Hero Store keep working.
  * Functions that are not importable by name (the closures and lambdas Effects.schedule() holds for delayed
    explosions) are written as (module, qualified name, index, code hash) plus their defaults and closure cells;
    loading finds the same code object again and refuses if the code changed.
  * Strings made of identifier characters come back interned, as source constants are: the simulation compares
    some of them by identity (Drone.mode is Drone.PATROL, Barrage.aim is Barrage.POINT).
  * Process-global counters (Enemy / Tower ids) are saved with the graph and restored.
  * Classes whose state pickle cannot rebuild as is say so themselves: Vec (read-only slots) and EnemyList (counting
    list overrides) reduce explicitly; PromptInjection and EnemyManager re-key their id()-keyed dicts in __setstate__.
  * Pickle restores an object's fields as they were, whatever its class looks like now: a save from a build whose
    simulation classes differ would load and then fail (or drift) on the first step. The header therefore lists every
    class in the save with a fingerprint of its code (and its lindefense base classes'); a save whose classes changed
    since it was written is refused, like a changed closure.

Only simulation objects are ever reachable from a Game: the UI holds the Game, never the reverse (no listeners,
audio hooks or window handles to drop). Tutorial and reverse-mode matches are never saved (can_save).

File format (one file, FILE_NAME in the prefs folder, written atomically through a temp file + rename):
    MAGIC line, one JSON header line, zlib-compressed pickle payload.
The header carries the format number, game version (version.py), Python version, map, difficulty, wave, the class
fingerprints and a payload checksum; a save from another version / format / Python or with changed classes is refused.
The main menu decodes the save (a few ms) before offering CONTINUE, so a save that would not load is reported and
deleted up front. Unpickling is restricted to this
package's classes plus a few builtins. Nothing in a save depends on absolute paths or the hash seed.
"""
import hashlib
import importlib
import io
import json
import os
import pickle
import re
import sys
import time
import types
import zlib

from lindefense import prefs, version

FORMAT = 2   # 2: class fingerprints in the header (format 1 saves predate the boss-ability / challenge fields)
FILE_NAME = "run_save.bin"
MAGIC = b"LINDEFENSE-RUN-SAVE\n"
PROTOCOL = 5
LOAD_FAILED_TEXT = "Your saved run could not be loaded"


class SaveError(Exception):
    """A save could not be written or read (incompatible version, corrupt file, changed code, ...)."""


def game_version():
    return version.NUMBER + " " + version.STAGE


def python_version():
    return "%d.%d" % sys.version_info[:2]


# ====================================================================== what may be saved
def can_save(game, tutorial=False):
    """A normal match that is still being played: never tutorial or reverse-mode runs, never a finished match
    (a defeat or victory sequence that is already running counts as finished)."""
    from lindefense.sim.game import State
    return (game is not None and not tutorial and not game.is_reverse() and game.get_state() is State.PLAYING
            and game._victory_timer < 0 and game._defeat_timer < 0)


def has_progress(game):
    """False for a match nothing has happened in yet (no wave started, no tower built): leaving it saves nothing."""
    return game.get_wave() > 0 or bool(game.get_tower_manager().get_towers())


def is_run_over(game):
    """True once the match is decided (victory or defeat, including their closing sequences)."""
    from lindefense.sim.game import State
    return game.get_state() is not State.PLAYING or game._victory_timer >= 0 or game._defeat_timer >= 0


def mid_wave_safe(game):
    """Whether the current mid-wave state can be saved as is. Everything in the simulation is captured, except
    the real window Palantir's System Takeover is holding (the window's size feeds back into the simulation every
    frame), so a takeover in progress keeps the last wave-boundary save instead."""
    link = game.get_window_link()
    return not link.is_takeover_active() and link.pending_grab_requests() == 0


# ====================================================================== shared static data
_SHARED = {}    # id(obj) -> key
_BY_KEY = {}    # key -> obj


def _shared_tables():
    if _SHARED:
        return _SHARED, _BY_KEY
    from lindefense.tower import catalog
    from lindefense.tower.behavior.registry import behavior_of
    from lindefense.tower.tower_type import TowerType
    from lindefense.variance.variance import Mods
    from lindefense.wave import waves

    def put(obj, key):
        if obj is not None and id(obj) not in _SHARED:
            _SHARED[id(obj)] = key
            _BY_KEY[key] = obj

    for t in TowerType:
        d = catalog.get(t)
        if d is not None:
            put(d, ("def", t.name))
            put(d.base_stats, ("def.base", t.name))
            put(d.ability, ("def.ability", t.name))
            for i, u in enumerate(d.upgrades):
                put(u, ("def.upgrade", t.name, i))
        put(behavior_of(t), ("behavior", t.name))
    for w in waves.all_waves():
        put(w, ("wave", w.number))
        for i, gr in enumerate(w.groups):
            put(gr, ("wave.group", w.number, i))
    put(Mods.NONE, ("mods.none",))
    return _SHARED, _BY_KEY


# ====================================================================== functions that are not importable by name
def _resolve(module, qualname):
    obj = module
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


def _importable(f):
    try:
        return _resolve(importlib.import_module(f.__module__), f.__qualname__) is f
    except Exception:
        return False


def _const_text(k):
    """A constant as text that does not depend on the hash seed (frozenset constants iterate in hash order)."""
    if isinstance(k, frozenset):
        return "frozenset(%s)" % sorted(_const_text(x) for x in k)
    if isinstance(k, tuple):
        return "(%s)" % ",".join(_const_text(x) for x in k)
    return repr(k)


def _code_hash(co):
    """Fingerprint of a code object and the code nested in it (bytecode, names, constants; not file or lines)."""
    h = hashlib.blake2b(digest_size=12)

    def feed(c):
        h.update(c.co_code)
        h.update(repr((c.co_qualname, c.co_names, c.co_varnames, c.co_freevars, c.co_cellvars,
                       c.co_argcount, c.co_kwonlyargcount, c.co_flags)).encode())
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                feed(k)
            else:
                h.update(_const_text(k).encode())
    feed(co)
    return h.hexdigest()


_CLASS_HASHES = {}


def _class_hash(cls):
    """Fingerprint of a class's code: every function, static / class method and property defined in it and in its
    lindefense base classes. Data attributes (constants, enum members) do not count."""
    h = _CLASS_HASHES.get(cls)
    if h is not None:
        return h
    d = hashlib.blake2b(digest_size=12)
    for c in cls.__mro__:
        if not c.__module__.startswith("lindefense"):
            continue
        d.update(("%s.%s|" % (c.__module__, c.__qualname__)).encode())
        for name in sorted(vars(c)):
            v = vars(c)[name]
            if isinstance(v, (staticmethod, classmethod)):
                v = v.__func__
            if isinstance(v, property):
                fs = (v.fget, v.fset, v.fdel)
            else:
                fs = (v,)
            for f in fs:
                if isinstance(f, types.FunctionType):
                    d.update(name.encode() + b"=" + _code_hash(f.__code__).encode())
    h = _CLASS_HASHES[cls] = d.hexdigest()
    return h


def _class_name(cls):
    return cls.__module__ + ":" + cls.__qualname__


def _check_classes(classes):
    """Refuses a save whose classes (header "classes": {module:qualname: fingerprint}) changed or are gone."""
    if not isinstance(classes, dict) or not classes:
        raise SaveError("save header lacks class fingerprints")
    for name, digest in classes.items():
        module, _, qualname = str(name).partition(":")
        if not (module == "lindefense" or module.startswith("lindefense.")):
            raise SaveError("unexpected type in save: " + str(name))
        try:
            cls = _resolve(importlib.import_module(module), qualname)
        except Exception:
            raise SaveError("the class " + str(name) + " no longer exists")
        if not isinstance(cls, type) or _class_hash(cls) != digest:
            raise SaveError("the code of " + str(name) + " changed since the run was saved")


def _nested_codes(root_code, qualname):
    """Code objects named qualname nested anywhere inside root_code, in a fixed (depth-first) order."""
    out = []

    def walk(c):
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                if k.co_qualname == qualname:
                    out.append(k)
                walk(k)
    walk(root_code)
    return out


def _outer_code(module, qualname):
    """The code of the importable function a nested qualname ("A.f.<locals>.g") is defined in."""
    head = qualname.split(".<locals>.")[0]
    outer = _resolve(module, head)
    outer = getattr(outer, "__func__", outer)   # staticmethod / classmethod
    if isinstance(outer, property):
        outer = outer.fget
    return outer.__code__


def _reduce_function(f):
    """Reduces a closure / lambda to a reference to its code plus its runtime state."""
    module = importlib.import_module(f.__module__)
    qualname = f.__qualname__
    if ".<locals>." in qualname:
        cands = _nested_codes(_outer_code(module, qualname), qualname)
        index = next((i for i, c in enumerate(cands) if c is f.__code__), -1)
        if index < 0:
            raise pickle.PicklingError("cannot locate the code of " + qualname)
        ref = ("nested", f.__module__, qualname, index, _code_hash(f.__code__))
    else:   # a lambda stored in a module or class attribute
        attr = next((k for k, v in vars(module).items() if v is f), None)
        if attr is None:
            raise pickle.PicklingError("cannot pickle function " + qualname)
        ref = ("attr", f.__module__, attr)
    return _make_function, (ref, f.__defaults__, f.__kwdefaults__, f.__closure__, f.__dict__ or None)


def _make_function(ref, defaults, kwdefaults, closure, fdict):
    module = importlib.import_module(ref[1])
    if ref[0] == "attr":
        return getattr(module, ref[2])
    _, _, qualname, index, digest = ref
    cands = _nested_codes(_outer_code(module, qualname), qualname)
    if index >= len(cands) or _code_hash(cands[index]) != digest:
        raise SaveError("the code of " + qualname + " changed since the run was saved")
    f = types.FunctionType(cands[index], vars(module), qualname.rsplit(".", 1)[-1], defaults, closure)
    f.__kwdefaults__ = kwdefaults
    f.__qualname__ = qualname
    if fdict:
        f.__dict__.update(fdict)
    return f


_EMPTY = "<empty cell>"


def _new_cell():
    return types.CellType()


def _fill_cell(cell, state):
    if state != (_EMPTY,):
        cell.cell_contents = state[0]


def _reduce_cell(c):
    try:
        state = (c.cell_contents,)
    except ValueError:
        state = (_EMPTY,)
    # contents go in as state (set after the cell is memoized), so a closure that refers to itself still pickles
    return _new_cell, (), state, None, None, _fill_cell


# ====================================================================== pickling
# Strings made only of ASCII letters, digits and '_' are interned by the compiler wherever they appear as source
# constants, and the simulation relies on that: Drone.mode is Drone.PATROL, Barrage.aim is Barrage.POINT, ... compare
# identity. Unpickled strings are fresh objects, so these travel as persistent ids and come back interned.
_NAME_LIKE = re.compile(r"[A-Za-z0-9_]+\Z").match


class _Pickler(pickle.Pickler):
    def __init__(self, f):
        super().__init__(f, protocol=PROTOCOL)
        self._shared = _shared_tables()[0]
        self._names = {}
        self.classes = set()   # the package's classes with instances in the save (their fingerprints go in the header)
        from lindefense.sim.misc import HeroCollection
        self._heroes = HeroCollection

    def persistent_id(self, obj):
        if type(obj) is str:
            pid = self._names.get(obj)
            if pid is None and _NAME_LIKE(obj):
                pid = self._names[obj] = b"s" + obj.encode("ascii")   # bytes: never a persistent id itself
            return pid
        key = self._shared.get(id(obj))
        if key is not None:
            return key
        if obj is self._heroes._shared and obj is not None:
            return ("heroes.persistent",)
        return None

    def reducer_override(self, obj):
        t = type(obj)
        if t.__module__.startswith("lindefense"):
            self.classes.add(t)
        if t is types.FunctionType and not _importable(obj):
            return _reduce_function(obj)
        if t is types.CellType:
            return _reduce_cell(obj)
        return NotImplemented


# modules / names the payload may name besides this package's own
_ALLOWED = {("builtins", "set"), ("builtins", "frozenset"), ("builtins", "getattr"), ("builtins", "object"),
            ("copyreg", "_reconstructor"), ("collections", "OrderedDict"), ("collections", "deque"),
            ("collections", "defaultdict"), ("functools", "partial"), ("operator", "attrgetter"),
            ("operator", "itemgetter"), ("operator", "methodcaller")}


class _Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if not (module == "lindefense" or module.startswith("lindefense.") or (module, name) in _ALLOWED):
            raise SaveError("unexpected type in save: %s.%s" % (module, name))
        return super().find_class(module, name)

    def persistent_load(self, key):
        if type(key) is bytes:
            if key[:1] != b"s":
                raise SaveError("unknown reference in save")
            return sys.intern(key[1:].decode("ascii"))
        key = tuple(key)
        if key == ("heroes.persistent",):
            from lindefense.sim.misc import HeroCollection
            return HeroCollection.persistent()
        obj = _shared_tables()[1].get(key)
        if obj is None:
            raise SaveError("unknown shared reference in save: %r" % (key,))
        return obj


def dumps(game):
    """The match as payload bytes (uncompressed pickle)."""
    return _dump(game)[0]


def _dump(game):
    """(payload bytes, {class name: fingerprint} of every package class with an instance in the payload)."""
    from lindefense.enemy.enemy import Enemy
    from lindefense.tower.tower import Tower
    buf = io.BytesIO()
    p = _Pickler(buf)
    p.dump({"game": game, "enemy_next_id": Enemy._next_id, "tower_next_id": Tower._next_id})
    return buf.getvalue(), {_class_name(c): _class_hash(c) for c in sorted(p.classes, key=_class_name)}


def loads(payload):
    """Rebuilds a match from dumps() bytes and restores the global id counters. Raises SaveError."""
    from lindefense.enemy.enemy import Enemy
    from lindefense.sim.game import Game
    from lindefense.tower.tower import Tower
    try:
        d = _Unpickler(io.BytesIO(payload)).load()
    except SaveError:
        raise
    except Exception as e:   # corrupt data, a renamed class, ...
        raise SaveError("%s: %s" % (type(e).__name__, e)) from e
    if not isinstance(d, dict) or not isinstance(d.get("game"), Game):
        raise SaveError("not a saved run")
    Enemy._next_id = int(d["enemy_next_id"])
    Tower._next_id = int(d["tower_next_id"])
    return d["game"]


# ====================================================================== the slot
class SaveInfo:
    """What the main menu shows about the saved run (read from the header only)."""

    def __init__(self, header):
        self.header = header
        self.map_index = int(header["map"])
        self.map_name = str(header["map_name"])
        self.difficulty = str(header["difficulty"])
        self.wave = int(header["wave"])
        self.mid_wave = bool(header.get("mid_wave", False))

    def get_difficulty(self):
        """The run's Difficulty member, or None if this build has no such mode."""
        from lindefense.sim.difficulty import Difficulty
        return Difficulty.__members__.get(self.difficulty)

    def label(self, difficulty_text=None):
        """'The Silicon Circuit, O(N), wave 37' (difficulty_text: the mode as the caller's font can show it)."""
        d = self.get_difficulty()
        if difficulty_text is None:
            difficulty_text = d.ascii_label if d is not None else self.difficulty
        return "%s, %s, wave %d" % (self.map_name, difficulty_text, max(1, self.wave))


def header_for(game, payload, classes):
    from lindefense.map import maps
    wm = game.get_wave_manager()
    return {
        "format": FORMAT,
        "classes": classes,
        "game_version": game_version(),
        "python": python_version(),
        "map": maps.index_of(game.get_map()),
        "map_name": game.get_map().get_name(),
        "difficulty": game.get_difficulty().name,
        "wave": game.get_wave(),   # the wave counter, as the HUD shows it
        "completed": game.get_last_completed_wave(),
        "mid_wave": wm.is_wave_active(),
        "lives": game.get_lives(),
        "cash": game.get_cash(),
        "sim_time": game.get_time(),
        "patch_notes": game.get_variance().is_enabled(),
        "saved_at": int(time.time()),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def encode(game):
    """The complete save file for a match, as bytes."""
    payload, classes = _dump(game)
    header = header_for(game, payload, classes)
    return MAGIC + json.dumps(header, sort_keys=True).encode("utf-8") + b"\n" + zlib.compress(payload, 6)


def _split(data):
    """(header dict, compressed payload). Raises SaveError for anything that is not a compatible save."""
    if not data.startswith(MAGIC):
        raise SaveError("not a Lindefense save")
    nl = data.find(b"\n", len(MAGIC))
    if nl < 0:
        raise SaveError("truncated save")
    try:
        header = json.loads(data[len(MAGIC):nl].decode("utf-8"))
    except ValueError as e:
        raise SaveError("bad save header") from e
    if not isinstance(header, dict):
        raise SaveError("bad save header")
    if header.get("format") != FORMAT:
        raise SaveError("save format %r (this build reads %d)" % (header.get("format"), FORMAT))
    if header.get("game_version") != game_version():
        raise SaveError("saved by version %r (this is %s)" % (header.get("game_version"), game_version()))
    if header.get("python") != python_version():
        raise SaveError("saved under Python %r" % header.get("python"))
    for k in ("map", "map_name", "difficulty", "wave", "sha256", "size"):
        if k not in header:
            raise SaveError("save header lacks " + k)
    _check_classes(header.get("classes"))
    return header, data[nl + 1:]


def _payload(header, body):
    try:
        payload = zlib.decompress(body)
    except zlib.error as e:
        raise SaveError("corrupt save data") from e
    if len(payload) != header["size"] or hashlib.sha256(payload).hexdigest() != header["sha256"]:
        raise SaveError("save checksum mismatch")
    return payload


def decode(data):
    """(header, Game) from save file bytes. Raises SaveError."""
    header, body = _split(data)
    return header, loads(_payload(header, body))


def validate(data):
    """SaveInfo for save file bytes if they hold a loadable run of this build (checksummed, not unpickled)."""
    header, body = _split(data)
    _payload(header, body)
    try:
        return SaveInfo(header)
    except (KeyError, TypeError, ValueError) as e:
        raise SaveError("bad save header") from e


class SaveSlot:
    """The one autosave slot: FILE_NAME in the prefs folder (LINDEFENSE_PREFS_DIR), or an explicit path."""

    def __init__(self, path=None):
        self._path = path

    def path(self):
        return self._path if self._path is not None else os.path.join(prefs._base_dir(), FILE_NAME)

    def exists(self):
        return os.path.isfile(self.path())

    def save(self, game):
        """Writes the match atomically (temp file + rename). Returns the file size; raises SaveError."""
        try:
            data = encode(game)
        except SaveError:
            raise
        except Exception as e:
            raise SaveError("could not snapshot the run: %s: %s" % (type(e).__name__, e)) from e
        path = self.path()
        tmp = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise SaveError("could not write the save: %s" % e) from e
        return len(data)

    def _read(self):
        try:
            with open(self.path(), "rb") as f:
                return f.read()
        except OSError as e:
            raise SaveError("could not read the save: %s" % e) from e

    def peek(self):
        """SaveInfo for a valid save, None when there is no save. Raises SaveError for an unusable one."""
        if not self.exists():
            return None
        try:
            return validate(self._read())
        except SaveError:
            raise
        except Exception as e:
            raise SaveError("%s: %s" % (type(e).__name__, e)) from e

    def check(self):
        """Like peek(), but also rebuilds the run (a few ms) so a save that would fail to load is caught now. The
        process-wide id counters are left as they were."""
        from lindefense.enemy.enemy import Enemy
        from lindefense.tower.tower import Tower
        if not self.exists():
            return None
        counters = (Enemy._next_id, Tower._next_id)
        try:
            header, _game = decode(self._read())
            return SaveInfo(header)
        except SaveError:
            raise
        except Exception as e:
            raise SaveError("%s: %s" % (type(e).__name__, e)) from e
        finally:
            Enemy._next_id, Tower._next_id = counters

    def load(self):
        """The saved match. Raises SaveError (the caller reports it and deletes the save)."""
        try:
            return decode(self._read())[1]
        except SaveError:
            raise
        except Exception as e:
            raise SaveError("%s: %s" % (type(e).__name__, e)) from e

    def delete(self):
        for p in (self.path(), self.path() + ".tmp"):
            try:
                os.remove(p)
            except OSError:
                pass


_default = SaveSlot()


def slot():
    """The game's save slot (follows LINDEFENSE_PREFS_DIR at call time)."""
    return _default


def _report(what, e):
    print("[save] %s: %s" % (what, e), file=sys.stderr)


def menu_entry(s=None):
    """(SaveInfo or None, notice or None) for the main menu's CONTINUE button. A save that cannot be used (another
    version, corrupt, unreadable, code changed) is deleted here and reported once through the notice."""
    s = _default if s is None else s
    try:
        return s.check(), None
    except Exception as e:
        _report("discarding the saved run", e)
        s.delete()
        return None, LOAD_FAILED_TEXT


# ====================================================================== the app's autosave policy
class Autosave:
    """Keeps the slot in step with one match while its game screen is showing (LindefenseApp owns one per match):

      * frame(): after every frame. Saves once each time a wave is cleared (the match is between waves then, and
        the snapshot is taken between two simulation steps); deletes the save as soon as the match is won or lost.
      * leave(): when the game screen goes away (main menu, map select, restart, closing the window). Saves the
        current state, which continues exactly, unless Palantir is holding the real window mid-takeover (then the
        last wave-boundary save stays); a finished match deletes the save instead.

    Tutorial and reverse-mode matches never touch the slot. Saving never raises: a failure is reported on stderr
    and the previous save is left in place."""

    def __init__(self, game, tutorial=False, s=None):
        self.game = game
        self.slot = _default if s is None else s
        self.enabled = can_save(game, tutorial)
        self.saved_wave = game.get_last_completed_wave()
        self.last_size = 0
        self.last_seconds = 0.0

    def _save(self):
        t0 = time.perf_counter()
        try:
            self.last_size = self.slot.save(self.game)
        except Exception as e:
            _report("autosave failed", e)
            return False
        self.last_seconds = time.perf_counter() - t0
        return True

    def frame(self):
        if not self.enabled:
            return
        g = self.game
        if is_run_over(g):
            self.slot.delete()
            self.enabled = False
            return
        done = g.get_last_completed_wave()
        if done != self.saved_wave and not g.get_wave_manager().is_wave_active():
            self.saved_wave = done
            self._save()

    def leave(self):
        """Returns True when this run is in the save slot afterwards (to be continued), else False."""
        if not self.enabled:
            return False
        self.enabled = False
        g = self.game
        if is_run_over(g):
            self.slot.delete()
            return False
        if not has_progress(g):
            return False   # nothing played yet: no run to continue
        if not g.get_wave_manager().is_wave_active() or mid_wave_safe(g):
            return self._save()
        return self.slot.exists()   # mid-takeover: the last wave-boundary save stays
