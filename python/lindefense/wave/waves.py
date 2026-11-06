"""The 100-wave campaign (spawn groups, scaling, end-of-wave bonus), the Prompt Injection schedule and the
WaveManager that runs it."""
import math

from lindefense.javacompat import jround
from lindefense.jenum import EnumSet
from lindefense.enemy.types import EnemyType, Modifier

WAVE_COUNT = 100


class SpawnGroup:
    """count enemies of one type spawned every interval seconds, starting start_delay seconds into the wave."""

    def __init__(self, type_, count, modifiers, interval, start_delay, route):
        self.type = type_
        self.count = count
        self.modifiers = EnumSet() if modifiers is None else modifiers
        self.interval = float(interval)
        self.start_delay = float(start_delay)
        self.route = route

    def modifier_label(self):
        return "+".join(m.label for m in self.modifiers)

    def end_time(self):
        return self.start_delay + self.interval * max(0, self.count - 1)


class WaveDef:
    def __init__(self, number, note, *groups):
        self.number = number
        self.note = note
        self.groups = list(groups[0]) if len(groups) == 1 and isinstance(groups[0], list) else list(groups)

    def total_spawns(self):
        return sum(g.count for g in self.groups)

    def contains_boss(self):
        return any(g.type.is_boss() for g in self.groups)

    def contains(self, t):
        return any(g.type is t for g in self.groups)

    def count_of(self, t):
        return sum(g.count for g in self.groups if g.type is t)

    def duration(self):
        d = 0.0
        for g in self.groups:
            d = max(d, g.end_time())
        return d


# ---------------------------------------------------------------- scaling
def hp_scale(wave):
    if wave <= 60:
        return 1.0
    if wave <= 80:
        return 1.0 + (wave - 60) * 0.005
    return 1.1 + (wave - 80) * 0.01


def speed_scale(wave):
    return 1.0 if wave <= 80 else 1.0 + (wave - 80) * 0.015


def reward_scale(wave):
    if wave <= 60:
        return 3.0
    if wave <= 80:
        return 4.0
    return 1.6


def wave_bonus(wave):
    return jround(300 + 900 * max(0.0, 1 - wave / 40.0))


# ---------------------------------------------------------------- Prompt Injection schedule
INJECTION_FIRST_WAVE = 30
BOSS_DEBUTS = (40, 60, 80, 90)


def injectors(wave):
    if wave < INJECTION_FIRST_WAVE or wave >= WAVE_COUNT:
        return 0
    if wave in BOSS_DEBUTS:
        return 0
    if wave < 50:
        return 1 if (wave - INJECTION_FIRST_WAVE) % 4 == 0 else 0
    if wave < 70:
        return 1 if wave % 2 == 0 else 0
    return 2 if wave < 85 else 3


def _carrier_index(groups):
    best = -1
    for i, g in enumerate(groups):
        if g.type.is_boss() or g.count < 2 or Modifier.INJECTION in g.modifiers:
            continue
        if best < 0:
            best = i
            continue
        b = groups[best]
        if g.count > b.count or (g.count == b.count and g.type.base_hp > b.type.base_hp):
            best = i
    return best


def _apply_injection(w):
    want = injectors(w.number)
    ci = _carrier_index(w.groups)
    if want <= 0 or ci < 0:
        return w
    g = w.groups[ci]
    k = min(want, g.count - 1)
    mods = g.modifiers.copy()
    mods.add(Modifier.INJECTION)
    interval = g.interval * g.count / k
    out = list(w.groups)
    out[ci] = SpawnGroup(g.type, g.count - k, g.modifiers, g.interval, g.start_delay, g.route)
    out.append(SpawnGroup(g.type, k, mods, interval, g.start_delay + interval * 0.5, g.route))
    if w.number == INJECTION_FIRST_WAVE:
        note = ("" if w.note is None else w.note + " ") + ("Prompt Injection: an enemy holding an IGNORE PREVIOUS INSTRUCTIONS "
                "sign hijacks nearby towers (Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann are immune).")
    else:
        note = w.note
    return WaveDef(w.number, note, out)


# ---------------------------------------------------------------- DSL
def _mods(code):
    m = EnumSet()
    if code is None:
        return m
    if "C" in code:
        m.add(Modifier.CAMO)
    if "R" in code:
        m.add(Modifier.REGROW)
    if "F" in code:
        m.add(Modifier.FORTIFIED)
    if "I" in code:
        m.add(Modifier.INJECTION)
    return m


def g(t, count, *rest):
    """g(type, count, interval, delay) or g(type, count, mods, interval, delay)."""
    if len(rest) == 2:
        return SpawnGroup(t, count, None, rest[0], rest[1], -1)
    return SpawnGroup(t, count, _mods(rest[0]), rest[1], rest[2], -1)


_WAVES = []


def w(n, note, *groups):
    if len(_WAVES) != n - 1:
        raise RuntimeError("Wave " + str(n) + " defined out of order")
    _WAVES.append(WaveDef(n, note, *groups))


def _define():
    globals().update({t.name: t for t in EnemyType})


def _define_waves():
    _define()
    w(1, "Primitive Variables only.", g(PRIMITIVE_VARIABLE, 10, 1.0, 0))
    w(2, None, g(PRIMITIVE_VARIABLE, 15, 0.8, 0))
    w(3, "Static Arrays appear (each releases a Primitive Variable).", g(PRIMITIVE_VARIABLE, 12, 0.7, 0), g(STATIC_ARRAY, 4, 1.5, 8))
    w(4, None, g(STATIC_ARRAY, 10, 1.0, 0))
    w(5, None, g(PRIMITIVE_VARIABLE, 20, 0.5, 0), g(STATIC_ARRAY, 6, 1.2, 5))
    w(6, "Dynamic Arrays appear (Dynamic -> Static -> Primitive).", g(DYNAMIC_ARRAY, 6, 1.5, 0), g(STATIC_ARRAY, 8, 1.0, 2))
    w(7, None, g(STATIC_ARRAY, 15, 0.7, 0), g(DYNAMIC_ARRAY, 6, 1.2, 6))
    w(8, "Singly Linked Lists: very fast.", g(PRIMITIVE_VARIABLE, 15, 0.4, 0), g(SINGLY_LINKED_LIST, 6, 1.2, 4))
    w(9, None, g(DYNAMIC_ARRAY, 12, 0.9, 0), g(SINGLY_LINKED_LIST, 5, 1.0, 10))
    w(10, "First mixed rush.", g(PRIMITIVE_VARIABLE, 30, 0.3, 0), g(STATIC_ARRAY, 12, 0.6, 4), g(DYNAMIC_ARRAY, 8, 1.0, 10), g(SINGLY_LINKED_LIST, 6, 0.8, 16))
    w(11, "Doubly Linked Lists accelerate when hit.", g(DOUBLY_LINKED_LIST, 5, 1.5, 0), g(DYNAMIC_ARRAY, 8, 1.0, 3))
    w(12, None, g(SINGLY_LINKED_LIST, 12, 0.6, 0), g(STATIC_ARRAY, 15, 0.5, 3))
    w(13, None, g(DYNAMIC_ARRAY, 18, 0.6, 0), g(DOUBLY_LINKED_LIST, 6, 1.0, 8))
    w(14, "Regrow introduced.", g(PRIMITIVE_VARIABLE, 20, "R", 0.4, 0), g(DYNAMIC_ARRAY, 10, 0.8, 6))
    w(15, None, g(DYNAMIC_ARRAY, 12, 0.6, 2), g(SINGLY_LINKED_LIST, 15, 0.5, 0), g(DOUBLY_LINKED_LIST, 8, 0.8, 6))
    w(16, "Dense array rush.", g(DYNAMIC_ARRAY, 25, 0.45, 0), g(STATIC_ARRAY, 20, 0.3, 2))
    w(17, None, g(DOUBLY_LINKED_LIST, 12, 0.7, 0), g(SINGLY_LINKED_LIST, 12, 0.5, 5))
    w(18, None, g(DYNAMIC_ARRAY, 20, "R", 0.5, 0), g(DOUBLY_LINKED_LIST, 8, 0.9, 4))
    w(19, "Final data-structure rush before the sorters arrive.", g(PRIMITIVE_VARIABLE, 30, 0.2, 0), g(SINGLY_LINKED_LIST, 20, 0.4, 0), g(DOUBLY_LINKED_LIST, 12, 0.6, 4), g(DYNAMIC_ARRAY, 16, 0.5, 8))

    # ---------------- Waves 20-39: sorting algorithms, Camo, Fortified ----------------
    w(20, "Bubble Sort introduction: they swap places with enemies ahead.", g(BUBBLE_SORT, 8, 2.0, 0), g(DYNAMIC_ARRAY, 12, 0.6, 6))
    w(21, None, g(BUBBLE_SORT, 12, 1.2, 0), g(STATIC_ARRAY, 20, 0.4, 0))
    w(22, "Selection Sort jumps to the front of groups.", g(SELECTION_SORT, 8, 1.5, 0), g(BUBBLE_SORT, 8, 1.2, 4), g(DYNAMIC_ARRAY, 10, 0.6, 8))
    w(23, "Insertion Sort leapfrogs.", g(INSERTION_SORT, 10, 1.0, 0), g(SINGLY_LINKED_LIST, 12, 0.5, 6))
    w(24, "Camo introduced: detection required.", g(PRIMITIVE_VARIABLE, 20, "C", 0.5, 0), g(STATIC_ARRAY, 12, "C", 0.8, 8))
    w(25, "Shell Sort gap-jumps.", g(SHELL_SORT, 8, 1.5, 0), g(BUBBLE_SORT, 10, 1.0, 4), g(SELECTION_SORT, 8, 1.0, 10), g(DYNAMIC_ARRAY, 12, "C", 0.6, 14))
    w(26, "Merge Sort splits in two.", g(MERGE_SORT, 6, 2.0, 0), g(INSERTION_SORT, 10, 0.8, 5))
    w(27, "Quick Sort partitions.", g(QUICK_SORT, 5, 2.5, 0), g(SINGLY_LINKED_LIST, 15, 0.4, 5))
    w(28, "Heap Sort (Lead-type, shields allies) and Fortified introduced.", g(HEAP_SORT, 4, 3.0, 0), g(BUBBLE_SORT, 12, "F", 1.0, 3))
    w(29, "Counting Sort releases four Primitives.", g(COUNTING_SORT, 10, 1.0, 0), g(DOUBLY_LINKED_LIST, 10, "C", 0.8, 6), g(SHELL_SORT, 8, 1.2, 10))
    w(30, "Splitter rush.", g(MERGE_SORT, 10, 1.2, 0), g(SELECTION_SORT, 10, 0.8, 4), g(QUICK_SORT, 6, 1.5, 8), g(BUBBLE_SORT, 10, "R", 1.0, 12))
    w(31, "Radix Sort: digit armour changes every two layers.", g(RADIX_SORT, 5, 2.5, 0), g(DYNAMIC_ARRAY, 20, 0.5, 2))
    w(32, "Bucket Sort stores weaker enemies.", g(BUCKET_SORT, 4, 3.0, 0), g(PRIMITIVE_VARIABLE, 30, 0.3, 2), g(STATIC_ARRAY, 15, 0.5, 5))
    w(33, "Camo sorters.", g(INSERTION_SORT, 15, "C", 0.7, 0), g(SHELL_SORT, 10, "C", 1.0, 5))
    w(34, "TimSort: fast hybrid splitter.", g(TIMSORT, 4, 3.0, 0), g(MERGE_SORT, 8, 1.2, 4))
    w(35, None, g(HEAP_SORT, 6, 2.0, 0), g(QUICK_SORT, 8, 1.5, 3), g(COUNTING_SORT, 12, 0.8, 8))
    w(36, "Speed test.", g(DOUBLY_LINKED_LIST, 20, 0.5, 0), g(SINGLY_LINKED_LIST, 20, "C", 0.4, 4), g(SHELL_SORT, 10, "F", 1.2, 8))
    w(37, None, g(RADIX_SORT, 8, 1.5, 0), g(BUCKET_SORT, 5, 2.0, 5), g(SELECTION_SORT, 12, 0.8, 8))
    w(38, None, g(QUICK_SORT, 10, "F", 1.5, 0), g(MERGE_SORT, 10, "R", 1.0, 4), g(INSERTION_SORT, 12, 0.8, 10))
    w(39, "Everything so far, at once.", g(TIMSORT, 6, 2.0, 0), g(HEAP_SORT, 6, "C", 2.0, 5), g(BUBBLE_SORT, 15, "R", 0.8, 2), g(DYNAMIC_ARRAY, 25, "C", 0.4, 8))

    # ---------------- Waves 40-59: first boss, advanced combinations ----------------
    w(40, "BOSS: Bellarmine College Prep (MOAB). Heavy armour; releases 4 Quick Sorts.", g(BELLARMINE_COLLEGE_PREP, 1, 1, 5), g(QUICK_SORT, 8, 1.5, 10), g(SHELL_SORT, 10, 1.0, 20))
    w(41, None, g(MERGE_SORT, 15, 0.8, 0), g(SELECTION_SORT, 12, "C", 0.8, 5), g(COUNTING_SORT, 15, 0.6, 10))
    w(42, "Fortified Heaps.", g(HEAP_SORT, 8, "F", 1.5, 0), g(INSERTION_SORT, 15, 0.6, 4))
    w(43, None, g(RADIX_SORT, 10, 1.2, 0), g(QUICK_SORT, 10, 1.2, 6), g(SINGLY_LINKED_LIST, 25, "C", 0.3, 10))
    w(44, "Bucket swarm.", g(BUCKET_SORT, 8, 1.5, 0), g(PRIMITIVE_VARIABLE, 40, 0.2, 2), g(STATIC_ARRAY, 30, 0.3, 4), g(DYNAMIC_ARRAY, 20, 0.4, 8))
    w(45, "Two MOABs.", g(BELLARMINE_COLLEGE_PREP, 2, 8.0, 5), g(TIMSORT, 6, 2.0, 15))
    w(46, "Camo splitters.", g(TIMSORT, 8, "C", 1.5, 0), g(MERGE_SORT, 12, "C", 1.0, 4))
    w(47, "Regrow rush.", g(QUICK_SORT, 15, "R", 1.0, 0), g(SHELL_SORT, 15, "R", 0.8, 5), g(DOUBLY_LINKED_LIST, 15, "R", 0.6, 10))
    w(48, None, g(HEAP_SORT, 10, 1.2, 0), g(RADIX_SORT, 8, "F", 1.5, 6), g(BUBBLE_SORT, 20, 0.6, 3))
    w(49, "Camo + Fortified Shells.", g(SELECTION_SORT, 20, "C", 0.6, 0), g(INSERTION_SORT, 20, "C", 0.6, 3), g(SHELL_SORT, 12, "CF", 1.0, 10))
    w(50, "Three MOABs. On The Singularity Core the Event Horizon collapses 15 s in.", g(BELLARMINE_COLLEGE_PREP, 3, 6.0, 3), g(QUICK_SORT, 12, "F", 1.2, 10), g(TIMSORT, 8, 1.5, 20))
    w(51, None, g(BUCKET_SORT, 10, "R", 1.2, 0), g(COUNTING_SORT, 20, 0.5, 3), g(DYNAMIC_ARRAY, 30, "R", 0.4, 6))
    w(52, None, g(TIMSORT, 12, 1.2, 0), g(MERGE_SORT, 15, "F", 0.8, 5))
    w(53, "Fortified MOABs.", g(BELLARMINE_COLLEGE_PREP, 2, "F", 8.0, 4), g(HEAP_SORT, 10, "C", 1.2, 10), g(RADIX_SORT, 10, 1.0, 14))
    w(54, "Camo speed rush.", g(SINGLY_LINKED_LIST, 40, "C", 0.25, 0), g(DOUBLY_LINKED_LIST, 25, "C", 0.4, 5), g(SHELL_SORT, 15, "C", 0.8, 10))
    w(55, None, g(QUICK_SORT, 20, 0.8, 0), g(BUCKET_SORT, 8, "F", 1.5, 6), g(SELECTION_SORT, 15, "R", 0.7, 12))
    w(56, "Camo MOABs: detection is mandatory.", g(BELLARMINE_COLLEGE_PREP, 3, "C", 6.0, 3), g(INSERTION_SORT, 20, "C", 0.5, 10), g(TIMSORT, 8, "C", 1.2, 16))
    w(57, None, g(RADIX_SORT, 15, 0.8, 0), g(HEAP_SORT, 12, "F", 1.0, 5), g(COUNTING_SORT, 25, 0.4, 10))
    w(58, "Regrow splitters.", g(TIMSORT, 15, "R", 1.0, 0), g(MERGE_SORT, 20, "R", 0.6, 4), g(QUICK_SORT, 15, "R", 0.8, 10))
    w(59, "Four Fortified MOABs.", g(BELLARMINE_COLLEGE_PREP, 4, "F", 5.0, 2), g(BUCKET_SORT, 10, 1.2, 10), g(SHELL_SORT, 20, "F", 0.6, 15), g(DOUBLY_LINKED_LIST, 20, 0.4, 20))

    # ---------------- Waves 60-79: BFB and late-game rushes ----------------
    w(60, "BOSS: SW Resource Consultant (BFB). Weak hits halved; releases 3 MOABs.", g(SW_RESOURCE_CONSULTANT, 1, 1, 5), g(QUICK_SORT, 10, 1.0, 15), g(HEAP_SORT, 8, 1.5, 25))
    w(61, None, g(TIMSORT, 15, 0.9, 0), g(RADIX_SORT, 12, "F", 1.0, 6))
    w(62, None, g(BELLARMINE_COLLEGE_PREP, 4, 4.0, 3), g(MERGE_SORT, 25, 0.5, 10), g(INSERTION_SORT, 25, "C", 0.4, 14))
    w(63, None, g(BUCKET_SORT, 12, "R", 1.0, 0), g(SELECTION_SORT, 25, "R", 0.5, 3), g(COUNTING_SORT, 30, 0.3, 8))
    w(64, "Camo heavy.", g(HEAP_SORT, 15, "C", 0.8, 0), g(QUICK_SORT, 20, "C", 0.7, 5), g(SINGLY_LINKED_LIST, 40, "C", 0.2, 12))
    w(65, None, g(BELLARMINE_COLLEGE_PREP, 4, "F", 4.0, 2), g(TIMSORT, 12, "F", 1.0, 12), g(SHELL_SORT, 25, 0.5, 20))
    w(66, None, g(RADIX_SORT, 20, 0.6, 0), g(BUCKET_SORT, 12, "F", 1.0, 8))
    w(67, "Camo Regrow speedsters.", g(DOUBLY_LINKED_LIST, 40, "CR", 0.3, 0), g(SHELL_SORT, 20, "CR", 0.6, 6), g(INSERTION_SORT, 20, "CR", 0.6, 12))
    w(68, "Fortified BFB.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 4), g(BELLARMINE_COLLEGE_PREP, 2, 6.0, 20), g(QUICK_SORT, 20, 0.7, 10))
    w(69, None, g(TIMSORT, 20, "C", 0.8, 0), g(MERGE_SORT, 30, "F", 0.5, 5), g(HEAP_SORT, 12, 1.0, 12))
    w(70, "Four MOABs.", g(BELLARMINE_COLLEGE_PREP, 4, 3.5, 2), g(BUCKET_SORT, 12, "C", 1.0, 10), g(COUNTING_SORT, 30, "R", 0.3, 14), g(RADIX_SORT, 12, "C", 0.8, 20))
    w(71, None, g(QUICK_SORT, 30, "R", 0.5, 0), g(SELECTION_SORT, 30, "C", 0.4, 4))
    w(72, "BFB with a TimSort escort.", g(SW_RESOURCE_CONSULTANT, 1, 12.0, 3), g(TIMSORT, 25, 0.8, 15))
    w(73, "Fortified armour wall.", g(HEAP_SORT, 20, "F", 0.7, 0), g(RADIX_SORT, 20, "F", 0.7, 5), g(SHELL_SORT, 25, "C", 0.5, 10))
    w(74, "Camo blitz.", g(SINGLY_LINKED_LIST, 60, "C", 0.15, 0), g(DOUBLY_LINKED_LIST, 40, "CR", 0.3, 6), g(INSERTION_SORT, 30, "C", 0.4, 12))
    w(75, None, g(BELLARMINE_COLLEGE_PREP, 4, "F", 3.5, 2), g(SW_RESOURCE_CONSULTANT, 1, 1, 25), g(TIMSORT, 20, "F", 0.8, 12))
    w(76, None, g(BUCKET_SORT, 15, "R", 0.8, 0), g(MERGE_SORT, 30, "CR", 0.4, 4), g(QUICK_SORT, 25, "C", 0.6, 10))
    w(77, None, g(RADIX_SORT, 25, 0.5, 0), g(HEAP_SORT, 20, "C", 0.7, 6), g(COUNTING_SORT, 40, 0.25, 12))
    w(78, "Fortified BFB with camo MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 10.0, 3), g(BELLARMINE_COLLEGE_PREP, 4, "C", 4.0, 20), g(SHELL_SORT, 30, "F", 0.5, 10))
    w(79, "Sorter flood.", g(TIMSORT, 30, 0.5, 0), g(QUICK_SORT, 30, "F", 0.5, 5), g(SELECTION_SORT, 30, "R", 0.4, 10), g(BUBBLE_SORT, 30, "R", 0.4, 15))

    # ---------------- Waves 80-89: ZOMG and escalating Fortified bosses ----------------
    w(80, "BOSS: 3Com (ZOMG). Releases 3 BFBs, each releasing 3 MOABs.", g(THREE_COM, 1, 1, 5), g(TIMSORT, 15, 1.0, 30))
    w(81, None, g(BELLARMINE_COLLEGE_PREP, 5, "F", 3.0, 2), g(QUICK_SORT, 30, "F", 0.5, 10))
    w(82, None, g(SW_RESOURCE_CONSULTANT, 1, "F", 8.0, 3), g(TIMSORT, 25, 0.6, 15))
    w(83, "Fortified TimSort flood.", g(TIMSORT, 40, "F", 0.4, 0), g(HEAP_SORT, 25, "F", 0.6, 6))
    w(84, None, g(BELLARMINE_COLLEGE_PREP, 5, "F", 2.5, 2), g(SW_RESOURCE_CONSULTANT, 1, 10.0, 15), g(RADIX_SORT, 25, "F", 0.6, 20))
    w(85, "Fortified Quick Sort swarm.", g(QUICK_SORT, 50, "F", 0.3, 0), g(MERGE_SORT, 40, "F", 0.4, 5), g(BUCKET_SORT, 15, "F", 0.8, 12))
    w(86, None, g(SW_RESOURCE_CONSULTANT, 1, "F", 7.0, 2), g(TIMSORT, 30, "F", 0.5, 10))
    w(87, None, g(BELLARMINE_COLLEGE_PREP, 5, "F", 2.0, 2), g(SHELL_SORT, 30, "CF", 0.4, 8), g(INSERTION_SORT, 30, "CF", 0.4, 12))
    w(88, "Fortified BFB with a MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 5), g(BELLARMINE_COLLEGE_PREP, 3, "F", 4.0, 20), g(QUICK_SORT, 30, "F", 0.4, 15))
    w(89, None, g(SW_RESOURCE_CONSULTANT, 1, "F", 6.0, 2), g(TIMSORT, 40, "F", 0.4, 10), g(HEAP_SORT, 30, "CF", 0.5, 14))

    # ---------------- Waves 90-99: DDTs and the road to Palantir ----------------
    w(90, "BOSS: Lockheed Martin (DDT). Camo, fast, Lead-type. Detection is required.", g(LOCKHEED_MARTIN, 2, 8.0, 5), g(BELLARMINE_COLLEGE_PREP, 4, 4.0, 15), g(SINGLY_LINKED_LIST, 40, "C", 0.2, 10))
    w(91, "DDT pack with Fortified BFBs.", g(LOCKHEED_MARTIN, 1, 5.0, 3), g(SW_RESOURCE_CONSULTANT, 1, "F", 8.0, 15), g(TIMSORT, 30, "CF", 0.5, 10))
    w(92, "BFB with a Fortified MOAB wall.", g(SW_RESOURCE_CONSULTANT, 1, 1, 3), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.5, 25), g(RADIX_SORT, 30, "CF", 0.5, 10))
    w(93, "Fortified DDTs and camo-fortified sorters.", g(LOCKHEED_MARTIN, 1, "F", 4.0, 2), g(QUICK_SORT, 50, "CF", 0.3, 10), g(SHELL_SORT, 40, "CF", 0.4, 15))
    w(94, None, g(SW_RESOURCE_CONSULTANT, 1, 6.0, 2), g(TIMSORT, 50, "F", 0.35, 10), g(BUCKET_SORT, 20, "F", 0.6, 20))
    w(95, "Fortified BFB with DDT escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 3), g(LOCKHEED_MARTIN, 1, 5.0, 25), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.0, 15))
    w(96, "Regrow DDTs and a camo-regrow blitz.", g(LOCKHEED_MARTIN, 2, "R", 3.0, 2), g(DOUBLY_LINKED_LIST, 60, "CR", 0.2, 10), g(INSERTION_SORT, 50, "CR", 0.3, 14))
    w(97, "BFB with a Fortified MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, 12.0, 2), g(BELLARMINE_COLLEGE_PREP, 2, "F", 3.0, 20), g(TIMSORT, 40, "CF", 0.4, 12))
    w(98, "DDT and MOAB flood under heavy armour.", g(LOCKHEED_MARTIN, 1, "F", 3.0, 2), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.0, 10), g(HEAP_SORT, 40, "CF", 0.4, 15), g(RADIX_SORT, 30, "CF", 0.4, 20))
    w(99, "Final rehearsal: BFB, MOAB and DDT classes together before the BAD.", g(SW_RESOURCE_CONSULTANT, 1, "F", 12.0, 2), g(BELLARMINE_COLLEGE_PREP, 3, "F", 6.0, 25), g(LOCKHEED_MARTIN, 1, 4.0, 40), g(TIMSORT, 50, "F", 0.3, 10))

    # ---------------- Wave 100: PALANTIR ----------------
    w(100, "FINAL BOSS: Palantir (BAD). Three phases, Predictive Surveillance. Victory when its body is destroyed.",
        g(PALANTIR, 1, 1, 8), g(LOCKHEED_MARTIN, 4, 6.0, 30), g(BELLARMINE_COLLEGE_PREP, 8, "F", 4.0, 45))


_define_waves()
if len(_WAVES) != WAVE_COUNT:
    raise RuntimeError("Expected 100 waves, got " + str(len(_WAVES)))
_WAVES[:] = [_apply_injection(x) for x in _WAVES]


def get(wave):
    return _WAVES[wave - 1]


def all_waves():
    return tuple(_WAVES)


class WaveManager:
    PREP_TIME = 8.0

    def __init__(self, game):
        self._game = game
        self._current_wave = 0
        self._wave_active = False
        self._wave_time = 0.0
        self._progress = []
        self._next_spawn_at = []
        self._current = None
        self._auto_start = False
        self._prep_timer = 0.0

    def get_current_wave(self):
        return self._current_wave

    def is_wave_active(self):
        return self._wave_active

    def get_current_def(self):
        return self._current

    def is_auto_start(self):
        return self._auto_start

    def set_auto_start(self, a):
        self._auto_start = a
        self._prep_timer = self.PREP_TIME

    def get_prep_timer(self):
        return self._prep_timer

    def get_wave_time(self):
        return self._wave_time

    def is_campaign_complete(self):
        return self._current_wave >= WAVE_COUNT and not self._wave_active

    def get_remaining_to_spawn(self):
        if not self._wave_active or self._current is None:
            return 0
        return sum(gr.count - self._progress[i] for i, gr in enumerate(self._current.groups))

    def can_start_next_wave(self):
        return (not self._wave_active and self._current_wave < WAVE_COUNT
                and self._game.get_variance().ready_for(self._current_wave + 1))

    def start_next_wave(self):
        if not self.can_start_next_wave():
            return False
        gm = self._game
        self._current_wave += 1
        self._current = gm.get_difficulty().shape(get(self._current_wave), gm.get_seed())
        self._current = gm.get_variance().shape_wave(self._current)
        self._wave_active = True
        self._wave_time = 0.0
        self._progress = [0] * len(self._current.groups)
        self._next_spawn_at = [gr.start_delay for gr in self._current.groups]
        gm.on_wave_started(self._current_wave, self._current)
        return True

    def update(self, dt):
        gm = self._game
        if not self._wave_active:
            if self._auto_start and self.can_start_next_wave() and self._current_wave > 0:
                self._prep_timer -= dt
                if self._prep_timer <= 0:
                    self._prep_timer = self.PREP_TIME
                    self.start_next_wave()
            return
        self._wave_time += dt
        all_spawned = True
        em = gm.get_enemy_manager()
        for i, gr in enumerate(self._current.groups):
            while self._progress[i] < gr.count and self._wave_time >= self._next_spawn_at[i]:
                e = em.spawn(gr.type, gr.modifiers, gr.route, 0)
                if e is not None:
                    self._progress[i] += 1
                self._next_spawn_at[i] += max(0.05, gr.interval)
            if self._progress[i] < gr.count:
                all_spawned = False
        if all_spawned and em.get_alive_count() == 0 and not gm.get_combat().get_projectiles():
            self._wave_active = False
            self._prep_timer = self.PREP_TIME
            gm.on_wave_completed(self._current_wave, self._current)

    def end_wave(self):
        self._wave_active = False
