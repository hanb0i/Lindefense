"""Enemy roster, modifiers, boss classes, mechanics and status effects (all per-type baseline numbers live here)."""
from lindefense.jenum import JEnum


class Mechanic(JEnum):
    NONE = ()
    ACCELERATE_ON_DAMAGE = ()   # Doubly Linked List: +15% speed per hit taken, up to +90%
    BUBBLE_SWAP = ()            # Bubble Sort: every 3 s swaps with the nearest enemy ahead within 45 px
    SELECTION_FRONT = ()        # Selection Sort: every 2.5 s jumps to the front of the group within 140 px ahead
    INSERTION_LEAPFROG = ()     # Insertion Sort: every 2 s leapfrogs the nearest enemy ahead within 70 px
    SHELL_GAP_JUMP = ()         # Shell Sort: every 3 s jumps forward by its current gap (140, 70, 35, then 18 px)
    HEAP_SHIELD = ()            # Heap Sort: enemies up to 90 px behind it on its route take 50% damage
    RADIX_PHASES = ()           # Radix Sort: defensive profile changes every two layers
    BUCKET_STORE = ()           # Bucket Sort: absorbs nearby weaker enemies and releases them on death
    PALANTIR = ()               # Palantir: multi-phase final boss with Predictive Surveillance


class Modifier(JEnum):
    """Flags applied to existing enemies, never separate species."""
    CAMO = ("Camo",)
    REGROW = ("Regrow",)
    FORTIFIED = ("Fortified",)
    INJECTION = ("Prompt Injection",)

    def _init(self, label):
        self.label = label


class BossClass(JEnum):
    MOAB = ("MOAB",)
    BFB = ("BFB",)
    ZOMG = ("ZOMG",)
    DDT = ("DDT",)
    BAD = ("BAD",)

    def _init(self, label):
        self.label = label


class StatusKind(JEnum):
    SLOW = ()          # magnitude = fraction of speed removed; strongest wins; bosses get 1/3
    STUN = ()          # cannot move; bosses immune unless overridden
    FREEZE = ()        # like STUN and takes x2 damage (Claude Time-Lock)
    DOT = ()           # burn: magnitude = dps (TRUE damage); refreshes
    ARMOR_CRACK = ()   # Lead immunity removed and Fortified bonus ignored
    MARKED = ()        # magnitude = extra damage taken fraction; strongest wins
    MARKED_FLAT = ()   # magnitude = flat extra damage per hit; strongest wins
    DISRUPTED = ()     # special mechanic disabled
    REVEALED = ()      # camo temporarily ignored


class StatusEffect:
    __slots__ = ("kind", "magnitude", "remaining")

    Kind = StatusKind

    def __init__(self, kind, magnitude: float, remaining: float):
        self.kind = kind
        self.magnitude = magnitude
        self.remaining = remaining


class EnemyType(JEnum):
    # ---------------- Standard data structures ----------------
    PRIMITIVE_VARIABLE = ("Primitive Variable", 1, 1.0, 2, 1, 9, Mechanic.NONE,
                          "A small, simple data orb. The most basic enemy.")
    STATIC_ARRAY = ("Static Array", 2, 1.4, 3, 1, 12, Mechanic.NONE,
                    "An orderly segmented container. Releases 1 Primitive Variable when destroyed.")
    DYNAMIC_ARRAY = ("Dynamic Array", 3, 1.8, 4, 1, 14, Mechanic.NONE,
                     "An expandable container. Releases 1 Static Array when destroyed.")
    SINGLY_LINKED_LIST = ("Singly Linked List", 4, 3.2, 5, 2, 13, Mechanic.NONE,
                          "Connected nodes with one-way links. Very fast.")
    DOUBLY_LINKED_LIST = ("Doubly Linked List", 5, 3.5, 6, 2, 14, Mechanic.ACCELERATE_ON_DAMAGE,
                          "Two-way linked nodes. Accelerates every time it is damaged.")
    # ---------------- Sorting algorithms ----------------
    BUBBLE_SORT = ("Bubble Sort", 3, 0.9, 5, 2, 15, Mechanic.BUBBLE_SWAP,
                   "A bubbly sorter that swaps positions with the enemy ahead of it.")
    SELECTION_SORT = ("Selection Sort", 4, 1.0, 6, 2, 15, Mechanic.SELECTION_FRONT,
                      "Scans the group ahead and jumps to its front.")
    INSERTION_SORT = ("Insertion Sort", 4, 1.5, 6, 2, 14, Mechanic.INSERTION_LEAPFROG,
                      "Slips between enemies, leapfrogging the one directly ahead.")
    SHELL_SORT = ("Shell Sort", 5, 2.0, 8, 3, 15, Mechanic.SHELL_GAP_JUMP,
                  "Jumps forward by a shrinking gap sequence.")
    MERGE_SORT = ("Merge Sort", 6, 1.1, 8, 4, 17, Mechanic.NONE,
                  "Divides into two 2-layer Merge Runs when destroyed.")
    MERGE_RUN = ("Merge Run", 2, 1.3, 3, 2, 11, Mechanic.NONE,
                 "Half of a Merge Sort.")
    QUICK_SORT = ("Quick Sort", 7, 1.8, 10, 5, 17, Mechanic.NONE,
                  "Partitions into two 3-layer Quick Partitions when destroyed.")
    QUICK_PARTITION = ("Quick Partition", 3, 1.6, 4, 3, 12, Mechanic.NONE,
                       "One side of a Quick Sort partition.")
    HEAP_SORT = ("Heap Sort", 8, 1.2, 12, 5, 19, Mechanic.HEAP_SHIELD,
                 "Armoured tree. Lead-type (Sharp cannot hurt it) and shields enemies behind it (50% damage).")
    COUNTING_SORT = ("Counting Sort", 1, 1.3, 6, 4, 16, Mechanic.NONE,
                     "A thin outer layer holding four counters. Releases 4 Primitive Variables.")
    RADIX_SORT = ("Radix Sort", 8, 1.5, 14, 6, 18, Mechanic.RADIX_PHASES,
                  "Digit armour: its outer two layers are plain; once it drops to 6 layers or fewer its armoured phases are Lead-type.")
    BUCKET_SORT = ("Bucket Sort", 6, 1.4, 10, 5, 19, Mechanic.BUCKET_STORE,
                   "Stores up to 6 nearby weaker enemies and releases them when destroyed.")
    TIMSORT = ("TimSort", 10, 1.6, 16, 8, 19, Mechanic.NONE,
               "Fast hybrid. Splits into a Merge Sort and an Insertion Sort.")
    # ---------------- Corporate bosses ----------------
    BELLARMINE_COLLEGE_PREP = ("Bellarmine College Prep", 1500, 0.7, 300, 30, 34, Mechanic.NONE,
                               "MOAB-class. Heavy armour (25%), slow. Releases 4 Quick Sorts.")
    SW_RESOURCE_CONSULTANT = ("SW Resource Consultant", 7500, 0.5, 800, 60, 42, Mechanic.NONE,
                              "BFB-class. Armour 40%; hits below 3 damage are halved. Releases 3 Bellarmine College Preps.")
    THREE_COM = ("3Com", 8000, 0.4, 2000, 100, 52, Mechanic.NONE,
                 "ZOMG-class. Massive HP, armour 30%. Releases 3 SW Resource Consultants.")
    LOCKHEED_MARTIN = ("Lockheed Martin", 1000, 2.6, 700, 50, 30, Mechanic.NONE,
                       "DDT-class. Camo, very fast, Lead-type, armour 40%. Releases 4 camo Quick Sorts.")
    PALANTIR = ("Palantir", 50000, 0.28, 10000, 100, 64, Mechanic.PALANTIR,
                "BAD-class final boss. Three defensive phases, each with a signature ability (Panopticon, Prompt Broadcast, System Takeover), and Predictive Surveillance.")
    # ---------------- Summons (never in a wave) ----------------
    PALANTIR_HOLOGRAM = ("Palantir Hologram", 1000, 0.36, 0, 0, 64, Mechanic.NONE,
                         "A holographic decoy that Palantir projects in phase 2. Low HP, pays nothing and costs no lives, but towers target it first while it exists (the ones immune to prompt injection see through it).")

    def _init(self, display_name, base_hp, speed, reward, lives, radius, mechanic, description):
        self.display_name = display_name
        self.base_hp = base_hp
        self.speed = float(speed)
        self.reward = reward
        self.lives = lives
        self.radius = float(radius)
        self.mechanic = mechanic
        self.description = description
        self._child_types = ()
        self._child_counts = ()
        self._boss_class = None
        self._armor = 0.0
        self._weak_hit_threshold = 0
        self._lead_body = False
        self._ceramic_body = False
        self._innate_camo = False

    def _children(self, t, n):
        self._child_types = (t,)
        self._child_counts = (n,)

    def _boss(self, cls, armor, weak):
        self._boss_class = cls
        self._armor = armor
        self._weak_hit_threshold = weak

    def is_boss(self) -> bool:
        return self._boss_class is not None

    def get_boss_class(self):
        return self._boss_class

    def get_armor(self) -> float:
        return self._armor

    def get_weak_hit_threshold(self) -> int:
        return self._weak_hit_threshold

    def is_lead_body(self) -> bool:
        return self._lead_body

    def is_ceramic_body(self) -> bool:
        return self._ceramic_body

    def is_sorting_algorithm(self) -> bool:
        return EnemyType.BUBBLE_SORT.ordinal <= self.ordinal <= EnemyType.TIMSORT.ordinal

    def is_linked_list(self) -> bool:
        return self is EnemyType.SINGLY_LINKED_LIST or self is EnemyType.DOUBLY_LINKED_LIST

    def has_innate_camo(self) -> bool:
        return self._innate_camo

    def get_child_types(self):
        return self._child_types

    def get_child_counts(self):
        return self._child_counts

    def has_children(self) -> bool:
        return len(self._child_types) > 0

    def total_children(self) -> int:
        return sum(self._child_counts)

    def is_complex(self) -> bool:
        return self.base_hp >= 6 or self.is_boss()

    def is_fast(self) -> bool:
        return self.speed >= 1.8

    def is_spawnable_species(self) -> bool:
        return self not in (EnemyType.MERGE_RUN, EnemyType.QUICK_PARTITION, EnemyType.PALANTIR_HOLOGRAM)

    def is_hologram(self) -> bool:
        return self is EnemyType.PALANTIR_HOLOGRAM


def _setup():
    E = EnemyType
    E.STATIC_ARRAY._children(E.PRIMITIVE_VARIABLE, 1)
    E.DYNAMIC_ARRAY._children(E.STATIC_ARRAY, 1)
    E.MERGE_SORT._children(E.MERGE_RUN, 2)
    E.QUICK_SORT._children(E.QUICK_PARTITION, 2)
    E.COUNTING_SORT._children(E.PRIMITIVE_VARIABLE, 4)
    E.TIMSORT._child_types = (E.MERGE_SORT, E.INSERTION_SORT)
    E.TIMSORT._child_counts = (1, 1)
    E.HEAP_SORT._lead_body = True
    E.MERGE_SORT._ceramic_body = True
    E.QUICK_SORT._ceramic_body = True
    E.TIMSORT._ceramic_body = True
    E.BELLARMINE_COLLEGE_PREP._boss(BossClass.MOAB, 0.25, 0)
    E.BELLARMINE_COLLEGE_PREP._children(E.QUICK_SORT, 4)
    E.SW_RESOURCE_CONSULTANT._boss(BossClass.BFB, 0.40, 3)
    E.SW_RESOURCE_CONSULTANT._children(E.BELLARMINE_COLLEGE_PREP, 3)
    E.THREE_COM._boss(BossClass.ZOMG, 0.30, 0)
    E.THREE_COM._children(E.SW_RESOURCE_CONSULTANT, 3)
    E.LOCKHEED_MARTIN._boss(BossClass.DDT, 0.40, 0)
    E.LOCKHEED_MARTIN._children(E.QUICK_SORT, 4)
    E.LOCKHEED_MARTIN._lead_body = True
    E.LOCKHEED_MARTIN._innate_camo = True
    E.PALANTIR._boss(BossClass.BAD, 0.60, 0)


_setup()
