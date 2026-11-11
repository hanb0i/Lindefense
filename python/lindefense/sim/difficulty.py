"""Difficulty Growth: four modes named after Big-O classes. Every knob is a relative multiplier on the base game;
O1 is an exact no-op. Elites are rolled deterministically from (game seed, wave, group index)."""
import math
import os

from lindefense.javacompat import JavaRandom, jround, string_hash, wrap64
from lindefense.jenum import EnumSet, JEnum
from lindefense.enemy.types import EnemyType, Modifier

PROPERTY = "LINDEFENSE_DIFFICULTY"


class Curve(JEnum):
    FLAT = ()
    LINEAR = ()
    QUADRATIC = ()


class Difficulty(JEnum):
    O1 = ("O1", "O(1)", "O(1)", "Constant (current)", "The original game, unchanged.",
          Curve.FLAT, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1.00)
    ON = ("ON", "O(N)", "O(N)", "Linear (Normal)", "Tougher enemies, more of them, weaker towers, leaner income.",
          Curve.LINEAR, 1.10, 1.50, 0.92, 0.80, 1.10, 1.40, 0, 0, 0, 0, 1, 1, 1.15)
    ON2 = ("ON2", "O(N²)", "O(N^2)", "Quadratic (Hard)",
           "Enemy health climbs to 1.85x with 1.6x the enemies, towers deal 90% damage, 72% income, and late waves bring some elites.",
           Curve.QUADRATIC, 1.10, 1.85, 0.90, 0.72, 1.10, 1.60, 0.02, 0.22, 1, 0.20, 1, 1, 1.30)
    ONN = ("ONN", "O(Nᴺ)", "O(N^N)", "Super-exponential (Impossible)",
           "Enemy health climbs to 3.1x with 2.4x the enemies, towers deal 84% damage, 56% income, and most late enemies are elites. Still beatable.",
           Curve.QUADRATIC, 1.25, 3.10, 0.84, 0.56, 1.25, 2.40, 0.03, 0.80, 2, 0.50, 1, 1, 2.00)

    def _init(self, id_, label, ascii_, subtitle, description, curve, hp_base, hp_final, tower_damage, income,
              count_base, count_final, elite_base, elite_final, elite_mods, promote_chance, cash, lives, palantir_hp):
        self.id = id_
        self.label = label
        self.ascii_label = ascii_
        self.subtitle = subtitle
        self.description = description
        self.curve = curve
        self.hp_base, self.hp_final = float(hp_base), float(hp_final)
        self.tower_damage = float(tower_damage)
        self.income = float(income)
        self.count_base, self.count_final = float(count_base), float(count_final)
        self.elite_base, self.elite_final = float(elite_base), float(elite_final)
        self.elite_mods = elite_mods
        self.promote_chance = float(promote_chance)
        self.start_cash_mult, self.start_lives_mult = float(cash), float(lives)
        self.palantir_hp_mult = float(palantir_hp)

    def is_base(self):
        return self is Difficulty.O1

    @staticmethod
    def parse(s):
        if s is None:
            return None
        k = s.strip().upper().replace("(", "").replace(")", "").replace("^", "").replace("²", "2").replace("ᴺ", "N")
        for d in Difficulty:
            if d.id == k:
                return d
        return None

    @staticmethod
    def default_mode():
        d = Difficulty.parse(os.environ.get(PROPERTY))
        return Difficulty.O1 if d is None else d

    @staticmethod
    def get_selected():
        return Difficulty.default_mode() if _selected[0] is None else _selected[0]

    @staticmethod
    def set_selected(d):
        _selected[0] = d

    # ---- curves
    def growth(self, wave):
        from lindefense.wave.waves import WAVE_COUNT
        x = max(0.0, min(1.0, wave / float(WAVE_COUNT)))
        if self.curve is Curve.LINEAR:
            return x
        if self.curve is Curve.QUADRATIC:
            return x * x
        return 0.0

    def palantir_hp(self):
        """Palantir's own HP multiplier for this mode. It replaces the ramped multiplier (which would put it at 1.5x-3.1x)
        but, unlike before, no longer cancels the weaker towers, so the final fight is harder in every mode."""
        return self.palantir_hp_mult

    def hp_multiplier(self, wave, type_=None):
        if type_ is EnemyType.PALANTIR:
            return self.palantir_hp()
        return _ramp(self.hp_base, self.hp_final, self.growth(wave))

    def count_multiplier(self, wave):
        return _ramp(self.count_base, self.count_final, self.growth(wave))

    def elite_chance(self, wave):
        return _ramp(self.elite_base, self.elite_final, self.growth(wave))

    def start_cash(self, base):
        return jround(base * self.start_cash_mult)

    def start_lives(self, base):
        return jround(base * self.start_lives_mult)

    # ---- wave shaping
    def shape(self, base, seed):
        if self.is_base():
            return base
        from lindefense.wave.waves import SpawnGroup, WaveDef
        wave = base.number
        cm = self.count_multiplier(wave)
        ec = self.elite_chance(wave)
        out = []
        gi = 0
        h = string_hash(self.id)
        for g in base.groups:
            r = JavaRandom(wrap64(wrap64(wrap64(seed * 1_000_003) + wave * 7919 + gi * 104_729) + h))
            gi += 1
            if g.type.is_boss():
                out.append(g)
                continue
            exact = g.count * cm
            n = int(math.floor(exact))
            if r.next_double() < exact - n:
                n += 1
            n = max(1, n)
            interval = g.interval / (1 + 0.5 * (cm - 1))
            plain = elite = promoted = 0
            for _ in range(n):
                if ec > 0 and r.next_double() < ec:
                    if r.next_double() < self.promote_chance and g.type in _PROMOTION:
                        promoted += 1
                    else:
                        elite += 1
                else:
                    plain += 1
            em = self._elite_modifiers(g.modifiers, r)
            if plain > 0:
                out.append(SpawnGroup(g.type, plain, g.modifiers, interval, g.start_delay, g.route))
            if elite > 0:
                out.append(SpawnGroup(g.type, elite, em, interval * n / elite, g.start_delay + interval * 0.5, g.route))
            if promoted > 0:
                out.append(SpawnGroup(_PROMOTION[g.type], promoted, em, interval * n / promoted, g.start_delay + interval * 0.25, g.route))
        return WaveDef(wave, base.note, out)

    def _elite_modifiers(self, have, r):
        m = have.copy()
        missing = list(EnumSet.complement_of(m, Modifier))
        if Modifier.INJECTION in missing:
            missing.remove(Modifier.INJECTION)
        for _ in range(self.elite_mods):
            if not missing:
                break
            m.add(missing.pop(r.next_int(len(missing))))
        return m


def _ramp(base, fin, g):
    return base + (fin - base) * g


_selected = [None]

_E = EnemyType
_PROMOTION = {
    _E.PRIMITIVE_VARIABLE: _E.STATIC_ARRAY,
    _E.STATIC_ARRAY: _E.DYNAMIC_ARRAY,
    _E.DYNAMIC_ARRAY: _E.DOUBLY_LINKED_LIST,
    _E.SINGLY_LINKED_LIST: _E.DOUBLY_LINKED_LIST,
    _E.BUBBLE_SORT: _E.MERGE_SORT,
    _E.SELECTION_SORT: _E.QUICK_SORT,
    _E.INSERTION_SORT: _E.QUICK_SORT,
    _E.SHELL_SORT: _E.QUICK_SORT,
    _E.MERGE_SORT: _E.QUICK_SORT,
    _E.QUICK_SORT: _E.HEAP_SORT,
    _E.HEAP_SORT: _E.RADIX_SORT,
    _E.COUNTING_SORT: _E.BUCKET_SORT,
    _E.RADIX_SORT: _E.TIMSORT,
    _E.BUCKET_SORT: _E.TIMSORT,
}
