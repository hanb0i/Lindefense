"""Hero collection (permanent Hero Store unlocks), admin mode cheats and Palantir's window link."""
from lindefense import prefs
from lindefense.jenum import EnumSet, JEnum


# ====================================================================== HeroCollection
class HeroCollection:
    """The player's permanently unlocked heroes. in_memory() never touches disk; persistent() is saved."""
    _shared = None

    def __init__(self, storage=None):
        self._unlocked = EnumSet()   # ordinal order, like Java's EnumSet (a plain set iterates in hash order)
        self._storage = storage
        if storage is not None:
            try:
                for t in storage.load():
                    if t.is_hero():
                        self._unlocked.add(t)
            except Exception:
                pass

    @staticmethod
    def in_memory():
        return HeroCollection(None)

    @staticmethod
    def with_storage(storage):
        return HeroCollection(storage)

    @staticmethod
    def persistent():
        if HeroCollection._shared is None:
            HeroCollection._shared = HeroCollection(_PrefsStorage())
        return HeroCollection._shared

    def is_unlocked(self, type_):
        return type_ in self._unlocked

    def unlocked(self):
        """Copy of the unlocked heroes, iterating in TowerType order."""
        return EnumSet(self._unlocked)

    def unlock(self, type_):
        if type_ is None or not type_.is_hero() or type_ in self._unlocked:
            return False
        self._unlocked.add(type_)
        if self._storage is not None:
            try:
                self._storage.save(set(self._unlocked))
            except Exception:
                pass
        return True


class _PrefsStorage:
    def load(self):
        from lindefense.tower.tower_type import TowerType
        out = set()
        raw = prefs.node("lindefense/heroes").get("unlocked", "")
        for s in str(raw).split(","):
            k = s.strip()
            if k and k in TowerType.__members__:
                out.add(TowerType[k])
        return out

    def save(self, s):
        names = ",".join(t.name for t in sorted(s, key=lambda t: t.ordinal))
        prefs.node("lindefense/heroes").put("unlocked", names)


# ====================================================================== AdminMode
class AdminOption(JEnum):
    UNLOCK_HEROES = ("Unlock all heroes", "Every Hero Store hero is available to deploy. Your real purchases are left untouched.")
    INFINITE_MONEY = ("Infinite money", "Credits never run out, so every tower, hero and upgrade is free.")
    INFINITE_HEALTH = ("Infinite health", "Leaks can never take your last integrity, so the run cannot be lost.")

    def _init(self, label, description):
        self.label = label
        self.description = description

    def key(self):
        return "opt." + self.name


class AdminMode:
    Option = AdminOption
    CODE = "lindeveloper"
    _unlocked = None
    _options = {}

    @staticmethod
    def _prefs():
        return prefs.node("lindefense/admin")

    @classmethod
    def is_unlocked(cls):
        if cls._unlocked is None:
            cls._unlocked = cls._prefs().get_bool("unlocked", False)
        return cls._unlocked

    @classmethod
    def matches(cls, code):
        return code is not None and code.strip().lower() == cls.CODE

    @classmethod
    def try_code(cls, code):
        if not cls.matches(code):
            return False
        cls._unlocked = True
        cls._prefs().put("unlocked", True)
        return True

    @classmethod
    def is_on(cls, o):
        if not cls.is_unlocked():
            return False
        v = cls._options.get(o)
        if v is None:
            v = cls._prefs().get_bool(o.key(), False)
            cls._options[o] = v
        return v

    @classmethod
    def set(cls, o, on):
        cls._options[o] = on
        cls._prefs().put(o.key(), on)

    @classmethod
    def toggle(cls, o):
        v = not cls.is_on(o)
        cls.set(o, v)
        return v

    @classmethod
    def any_on(cls):
        return any(cls.is_on(o) for o in AdminOption)

    @classmethod
    def disable_all(cls):
        for o in AdminOption:
            cls.set(o, False)
        cls._unlocked = False
        cls._prefs().put("unlocked", False)


# ====================================================================== WindowLink
class WindowLink:
    """The simulation's only view of the real window, for Palantir's System Takeover."""
    SEAL_THRESHOLD = 0.85

    def __init__(self):
        self._fraction = 1.0
        self._grab_requests = 0
        self._owner = None

    def set_fraction(self, f):
        if f != f:
            return
        self._fraction = max(0.05, min(4.0, f))

    def get_fraction(self):
        return self._fraction

    def request_grab(self, by):
        self._owner = by
        self._grab_requests += 1

    def consume_grab_requests(self):
        n = self._grab_requests
        self._grab_requests = 0
        return n

    def pending_grab_requests(self):
        return self._grab_requests

    def is_takeover_active(self):
        return self._owner is not None and self._owner.is_alive() and not self._owner.has_leaked()

    def is_sealing(self):
        return self.is_takeover_active() and self._fraction < self.SEAL_THRESHOLD
