package lindefense.enemy;

/**
 * The enemy roster and all per-type baseline numbers (centralised so values can be
 * tuned without touching game logic). HP values are the "layer" counts from the
 * design spec; bosses use large absolute pools.
 *
 * <p>Children (released when the outer body is destroyed) are assigned in the static
 * initialiser because enum constants cannot forward-reference each other.</p>
 */
public enum EnemyType {
    // ---------------- Standard data structures ----------------
    PRIMITIVE_VARIABLE("Primitive Variable", 1, 1.0, 2, 1, 9, Mechanic.NONE,
        "A small, simple data orb. The most basic enemy."),
    STATIC_ARRAY("Static Array", 2, 1.4, 3, 1, 12, Mechanic.NONE,
        "An orderly segmented container. Releases 1 Primitive Variable when destroyed."),
    DYNAMIC_ARRAY("Dynamic Array", 3, 1.8, 4, 1, 14, Mechanic.NONE,
        "An expandable container. Releases 1 Static Array when destroyed."),
    SINGLY_LINKED_LIST("Singly Linked List", 4, 3.2, 5, 2, 13, Mechanic.NONE,
        "Connected nodes with one-way links. Very fast."),
    DOUBLY_LINKED_LIST("Doubly Linked List", 5, 3.5, 6, 2, 14, Mechanic.ACCELERATE_ON_DAMAGE,
        "Two-way linked nodes. Accelerates every time it is damaged."),

    // ---------------- Sorting algorithms ----------------
    BUBBLE_SORT("Bubble Sort", 3, 0.9, 5, 2, 15, Mechanic.BUBBLE_SWAP,
        "A bubbly sorter that swaps positions with the enemy ahead of it."),
    SELECTION_SORT("Selection Sort", 4, 1.0, 6, 2, 15, Mechanic.SELECTION_FRONT,
        "Scans the group ahead and jumps to its front."),
    INSERTION_SORT("Insertion Sort", 4, 1.5, 6, 2, 14, Mechanic.INSERTION_LEAPFROG,
        "Slips between enemies, leapfrogging the one directly ahead."),
    SHELL_SORT("Shell Sort", 5, 2.0, 8, 3, 15, Mechanic.SHELL_GAP_JUMP,
        "Jumps forward by a shrinking gap sequence."),
    MERGE_SORT("Merge Sort", 6, 1.1, 8, 4, 17, Mechanic.NONE,
        "Divides into two 2-layer Merge Runs when destroyed."),
    MERGE_RUN("Merge Run", 2, 1.3, 3, 2, 11, Mechanic.NONE,
        "Half of a Merge Sort."),
    QUICK_SORT("Quick Sort", 7, 1.8, 10, 5, 17, Mechanic.NONE,
        "Partitions into two 3-layer Quick Partitions when destroyed."),
    QUICK_PARTITION("Quick Partition", 3, 1.6, 4, 3, 12, Mechanic.NONE,
        "One side of a Quick Sort partition."),
    HEAP_SORT("Heap Sort", 8, 1.2, 12, 5, 19, Mechanic.HEAP_SHIELD,
        "Armoured tree. Lead-type (Sharp cannot hurt it) and shields enemies behind it (50% damage)."),
    COUNTING_SORT("Counting Sort", 1, 1.3, 6, 4, 16, Mechanic.NONE,
        "A thin outer layer holding four counters. Releases 4 Primitive Variables."),
    RADIX_SORT("Radix Sort", 8, 1.5, 14, 6, 18, Mechanic.RADIX_PHASES,
        "Digit armour: its outer two layers are plain; once it drops to 6 layers or fewer its armoured phases are Lead-type."),
    BUCKET_SORT("Bucket Sort", 6, 1.4, 10, 5, 19, Mechanic.BUCKET_STORE,
        "Stores up to 6 nearby weaker enemies and releases them when destroyed."),
    TIMSORT("TimSort", 10, 1.6, 16, 8, 19, Mechanic.NONE,
        "Fast hybrid. Splits into a Merge Sort and an Insertion Sort."),

    // ---------------- Corporate bosses ----------------
    BELLARMINE_COLLEGE_PREP("Bellarmine College Prep", 1500, 0.7, 300, 30, 34, Mechanic.NONE,
        "MOAB-class. Heavy armour (25%), slow. Releases 4 Quick Sorts."),
    SW_RESOURCE_CONSULTANT("SW Resource Consultant", 7500, 0.5, 800, 60, 42, Mechanic.NONE,
        "BFB-class. Armour 40%; hits below 3 damage are halved. Releases 3 Bellarmine College Preps."),
    THREE_COM("3Com", 8000, 0.4, 2000, 100, 52, Mechanic.NONE,
        "ZOMG-class. Massive HP, armour 30%. Releases 3 SW Resource Consultants."),
    LOCKHEED_MARTIN("Lockheed Martin", 1000, 2.6, 700, 50, 30, Mechanic.NONE,
        "DDT-class. Camo, very fast, Lead-type, armour 40%. Releases 4 camo Quick Sorts."),
    PALANTIR("Palantir", 50000, 0.28, 10000, 100, 64, Mechanic.PALANTIR,
        "BAD-class final boss. Three defensive phases, each with a signature ability (Panopticon, Prompt Broadcast, System Takeover), and Predictive Surveillance."),

    // ---------------- Summons (never in a wave) ----------------
    PALANTIR_HOLOGRAM("Palantir Hologram", 1000, 0.36, 0, 0, 64, Mechanic.NONE,
        "A holographic decoy that Palantir projects in phase 2. Low HP, pays nothing and costs no lives, but towers target it first while it exists (the ones immune to prompt injection see through it).");

    public final String displayName;
    public final int baseHp;
    public final double speed;
    public final int reward;
    public final int lives;
    public final double radius;
    public final Mechanic mechanic;
    public final String description;

    private EnemyType[] childTypes = new EnemyType[0];
    private int[] childCounts = new int[0];
    private BossClass bossClass;
    private double armor;
    private int weakHitThreshold;
    private boolean leadBody;
    private boolean ceramicBody;
    private boolean innateCamo;

    EnemyType(String displayName, int baseHp, double speed, int reward, int lives, double radius,
              Mechanic mechanic, String description) {
        this.displayName = displayName;
        this.baseHp = baseHp;
        this.speed = speed;
        this.reward = reward;
        this.lives = lives;
        this.radius = radius;
        this.mechanic = mechanic;
        this.description = description;
    }

    static {
        STATIC_ARRAY.children(PRIMITIVE_VARIABLE, 1);
        DYNAMIC_ARRAY.children(STATIC_ARRAY, 1);
        MERGE_SORT.children(MERGE_RUN, 2);
        QUICK_SORT.children(QUICK_PARTITION, 2);
        COUNTING_SORT.children(PRIMITIVE_VARIABLE, 4);
        TIMSORT.childTypes = new EnemyType[] { MERGE_SORT, INSERTION_SORT };
        TIMSORT.childCounts = new int[] { 1, 1 };

        HEAP_SORT.leadBody = true;
        MERGE_SORT.ceramicBody = true;
        QUICK_SORT.ceramicBody = true;
        TIMSORT.ceramicBody = true;

        BELLARMINE_COLLEGE_PREP.boss(BossClass.MOAB, 0.25, 0);
        BELLARMINE_COLLEGE_PREP.children(QUICK_SORT, 4);
        SW_RESOURCE_CONSULTANT.boss(BossClass.BFB, 0.40, 3);
        SW_RESOURCE_CONSULTANT.children(BELLARMINE_COLLEGE_PREP, 3);
        THREE_COM.boss(BossClass.ZOMG, 0.30, 0);
        THREE_COM.children(SW_RESOURCE_CONSULTANT, 3);
        LOCKHEED_MARTIN.boss(BossClass.DDT, 0.40, 0);
        LOCKHEED_MARTIN.children(QUICK_SORT, 4);
        LOCKHEED_MARTIN.leadBody = true;
        LOCKHEED_MARTIN.innateCamo = true;
        PALANTIR.boss(BossClass.BAD, 0.60, 0); // armour is phase-driven, see Boss
    }

    private void children(EnemyType t, int n) {
        childTypes = new EnemyType[] { t };
        childCounts = new int[] { n };
    }

    private void boss(BossClass cls, double armor, int weakHitThreshold) {
        this.bossClass = cls;
        this.armor = armor;
        this.weakHitThreshold = weakHitThreshold;
    }

    public boolean isBoss() { return bossClass != null; }
    public BossClass getBossClass() { return bossClass; }
    public double getArmor() { return armor; }
    /** Hits with raw damage below this are halved (0 = disabled). */
    public int getWeakHitThreshold() { return weakHitThreshold; }
    /**
     * Lead-type for the whole body (Heap Sort, Lockheed Martin). Radix Sort is Lead-type only in its armoured
     * phases; see {@link Enemy#isLeadType()}.
     */
    public boolean isLeadBody() { return leadBody; }
    /**
     * Ceramic-type outer layer: the body that releases children when destroyed and is itself a sorting
     * layer (Merge Sort, Quick Sort, TimSort). Its children (Merge Run, Quick Partition) are not Ceramic.
     */
    public boolean isCeramicBody() { return ceramicBody; }
    /** True for every sorting-algorithm enemy including split-children (Merge Run, Quick Partition). */
    public boolean isSortingAlgorithm() { return ordinal() >= BUBBLE_SORT.ordinal() && ordinal() <= TIMSORT.ordinal(); }
    public boolean isLinkedList() { return this == SINGLY_LINKED_LIST || this == DOUBLY_LINKED_LIST; }
    public boolean hasInnateCamo() { return innateCamo; }
    public EnemyType[] getChildTypes() { return childTypes; }
    public int[] getChildCounts() { return childCounts; }
    public boolean hasChildren() { return childTypes.length > 0; }

    /** Total number of direct children released on death. */
    public int totalChildren() {
        int n = 0;
        for (int c : childCounts) n += c;
        return n;
    }

    /** "Complex" enemies are the targets of DeepSeek-style bonuses. */
    public boolean isComplex() { return baseHp >= 6 || isBoss(); }

    public boolean isFast() { return speed >= 1.8; }

    /** The 16 player-facing standard enemies plus bosses (no split-children, no Palantir holograms). */
    public boolean isSpawnableSpecies() { return this != MERGE_RUN && this != QUICK_PARTITION && this != PALANTIR_HOLOGRAM; }

    /** Palantir's holographic decoy (phase 2): spawned by the boss itself, targeted first by towers that fall for it. */
    public boolean isHologram() { return this == PALANTIR_HOLOGRAM; }
}
