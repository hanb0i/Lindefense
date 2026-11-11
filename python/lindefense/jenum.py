"""Java-style enums: members carry an ordinal (declaration order) and constructor arguments as attributes."""
from enum import Enum


class JEnum(Enum):
    """Members are declared as tuples of constructor args; subclasses implement ``_init(self, *args)``."""

    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__)
        obj._args = args
        return obj

    def __init__(self, *args):
        init = getattr(self, "_init", None)
        if init is not None:
            init(*args)

    # Members are singletons compared by identity, so the identity hash is consistent with ==. Enum's own __hash__ is
    # a Python-level hash(self._name_), and enum members are hashed millions of times per match (modifier sets,
    # EnumMaps, status lookups). Neither order is meaningful: sets of enums are never iterated where order matters
    # (EnumSet iterates in ordinal order), and str hashes are randomised per process anyway.
    __hash__ = object.__hash__

    @property
    def ordinal(self) -> int:
        return self._value_

    def __lt__(self, other):
        return self._value_ < other._value_

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    @classmethod
    def values(cls):
        return list(cls)

    @classmethod
    def value_of(cls, name: str):
        try:
            return cls[name]
        except KeyError:
            raise ValueError("No enum constant " + cls.__name__ + "." + str(name)) from None


class EnumSet(set):
    """A set of enum members that iterates in ordinal order, like java.util.EnumSet."""

    def __iter__(self):
        return iter(sorted(set.__iter__(self), key=lambda m: m._value_))

    def __repr__(self) -> str:
        """AbstractCollection.toString: "[CAMO, REGROW]" in ordinal order (not "EnumSet({...})" in hash order)."""
        return "[" + ", ".join(str(m) for m in self) + "]"

    to_string = __repr__

    def copy(self) -> "EnumSet":
        return EnumSet(set.__iter__(self))

    @staticmethod
    def none_of() -> "EnumSet":
        return EnumSet()

    @staticmethod
    def of(*members) -> "EnumSet":
        return EnumSet(members)

    @staticmethod
    def all_of(cls) -> "EnumSet":
        return EnumSet(list(cls))

    @staticmethod
    def complement_of(s, cls) -> "EnumSet":
        return EnumSet(m for m in cls if m not in s)
