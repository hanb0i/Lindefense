package lindefense.wave;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import lindefense.enemy.EnemyType;
import lindefense.enemy.Modifier;

import static lindefense.enemy.EnemyType.*;

/**
 * The complete 100-wave campaign. Every wave is specified individually as a set
 * of concurrent {@link SpawnGroup}s. Counts are enemies initially spawned;
 * children released by splitting or boss destruction are extra.
 *
 * <p>Modifier codes: C = Camo, R = Regrow, F = Fortified, I = Prompt Injection (combinable, e.g. "CF"). Prompt
 * Injection enemies are placed by {@link InjectionSchedule} from wave 30 on.</p>
 *
 * <p>Scaling (also centralised here): {@link #hpScale(int)}, {@link #speedScale(int)}
 * and {@link #rewardScale(int)} are applied to every enemy spawned in a wave.</p>
 */
public final class WaveData {
    public static final int WAVE_COUNT = 100;
    private static final List<WaveDef> WAVES = new ArrayList<>();

    private WaveData() { }

    public static WaveDef get(int wave) { return WAVES.get(wave - 1); }
    public static List<WaveDef> all() { return Collections.unmodifiableList(WAVES); }

    /**
     * HP multiplier for every enemy (bosses included, so effective HP never decreases with the wave): flat to wave 60,
     * 1.1x at wave 80, then it climbs to 1.3x at wave 100. Boss base HPs are rebased to their debut waves in {@code EnemyType}.
     */
    public static double hpScale(int wave) {
        if (wave <= 60) return 1.0;
        if (wave <= 80) return 1.0 + (wave - 60) * 0.005;     // 1.10 at 80
        return 1.1 + (wave - 80) * 0.01;                      // 1.30 at 100
    }

    /** Enemy speed multiplier for a wave: flat to 80, +1.5% per wave after. */
    public static double speedScale(int wave) {
        return wave <= 80 ? 1.0 : 1.0 + (wave - 80) * 0.015;  // 1.30 at 100
    }

    /**
     * Cash reward multiplier per wave. The tower spec made towers several times more expensive than the original
     * roster, so kill rewards are tripled to wave 60 (the opening has to afford a real defence), 4x on waves 61-80 (the
     * boss waves that need the DeepSeek / Brad core) and 1.6x afterwards (late bosses pay big child cascades).
     */
    public static double rewardScale(int wave) {
        if (wave <= 60) return 3.0;
        if (wave <= 80) return 4.0;
        return 1.6;
    }

    /** End-of-wave bonus cash: $1,200 after wave 1, falling linearly to a flat $300 from wave 40 on (was 100 + wave). */
    public static int waveBonus(int wave) {
        return (int) Math.round(300 + 900 * Math.max(0, 1 - wave / 40.0));
    }

    // ---------------- DSL ----------------
    private static EnumSet<Modifier> mods(String code) {
        EnumSet<Modifier> m = EnumSet.noneOf(Modifier.class);
        if (code == null) return m;
        if (code.indexOf('C') >= 0) m.add(Modifier.CAMO);
        if (code.indexOf('R') >= 0) m.add(Modifier.REGROW);
        if (code.indexOf('F') >= 0) m.add(Modifier.FORTIFIED);
        if (code.indexOf('I') >= 0) m.add(Modifier.INJECTION);
        return m;
    }

    private static SpawnGroup g(EnemyType t, int count, double interval, double delay) {
        return new SpawnGroup(t, count, null, interval, delay, -1);
    }

    private static SpawnGroup g(EnemyType t, int count, String mods, double interval, double delay) {
        return new SpawnGroup(t, count, mods(mods), interval, delay, -1);
    }

    private static void w(int n, String note, SpawnGroup... groups) {
        if (WAVES.size() != n - 1) throw new IllegalStateException("Wave " + n + " defined out of order");
        WAVES.add(new WaveDef(n, note, groups));
    }

    static {
        // ---------------- Waves 1-19: standard data structures ----------------
        w(1, "Primitive Variables only.", g(PRIMITIVE_VARIABLE, 10, 1.0, 0));
        w(2, null, g(PRIMITIVE_VARIABLE, 15, 0.8, 0));
        w(3, "Static Arrays appear (each releases a Primitive Variable).", g(PRIMITIVE_VARIABLE, 12, 0.7, 0), g(STATIC_ARRAY, 4, 1.5, 8));
        w(4, null, g(STATIC_ARRAY, 10, 1.0, 0));
        w(5, null, g(PRIMITIVE_VARIABLE, 20, 0.5, 0), g(STATIC_ARRAY, 6, 1.2, 5));
        w(6, "Dynamic Arrays appear (Dynamic -> Static -> Primitive).", g(DYNAMIC_ARRAY, 6, 1.5, 0), g(STATIC_ARRAY, 8, 1.0, 2));
        w(7, null, g(STATIC_ARRAY, 15, 0.7, 0), g(DYNAMIC_ARRAY, 6, 1.2, 6));
        w(8, "Singly Linked Lists: very fast.", g(PRIMITIVE_VARIABLE, 15, 0.4, 0), g(SINGLY_LINKED_LIST, 6, 1.2, 4));
        w(9, null, g(DYNAMIC_ARRAY, 12, 0.9, 0), g(SINGLY_LINKED_LIST, 5, 1.0, 10));
        w(10, "First mixed rush.", g(PRIMITIVE_VARIABLE, 30, 0.3, 0), g(STATIC_ARRAY, 12, 0.6, 4), g(DYNAMIC_ARRAY, 8, 1.0, 10), g(SINGLY_LINKED_LIST, 6, 0.8, 16));
        w(11, "Doubly Linked Lists accelerate when hit.", g(DOUBLY_LINKED_LIST, 5, 1.5, 0), g(DYNAMIC_ARRAY, 8, 1.0, 3));
        w(12, null, g(SINGLY_LINKED_LIST, 12, 0.6, 0), g(STATIC_ARRAY, 15, 0.5, 3));
        w(13, null, g(DYNAMIC_ARRAY, 18, 0.6, 0), g(DOUBLY_LINKED_LIST, 6, 1.0, 8));
        w(14, "Regrow introduced.", g(PRIMITIVE_VARIABLE, 20, "R", 0.4, 0), g(DYNAMIC_ARRAY, 10, 0.8, 6));
        w(15, null, g(DYNAMIC_ARRAY, 12, 0.6, 2), g(SINGLY_LINKED_LIST, 15, 0.5, 0), g(DOUBLY_LINKED_LIST, 8, 0.8, 6));
        w(16, "Dense array rush.", g(DYNAMIC_ARRAY, 25, 0.45, 0), g(STATIC_ARRAY, 20, 0.3, 2));
        w(17, null, g(DOUBLY_LINKED_LIST, 12, 0.7, 0), g(SINGLY_LINKED_LIST, 12, 0.5, 5));
        w(18, null, g(DYNAMIC_ARRAY, 20, "R", 0.5, 0), g(DOUBLY_LINKED_LIST, 8, 0.9, 4));
        w(19, "Final data-structure rush before the sorters arrive.", g(PRIMITIVE_VARIABLE, 30, 0.2, 0), g(SINGLY_LINKED_LIST, 20, 0.4, 0), g(DOUBLY_LINKED_LIST, 12, 0.6, 4), g(DYNAMIC_ARRAY, 16, 0.5, 8));

        // ---------------- Waves 20-39: sorting algorithms, Camo, Fortified ----------------
        w(20, "Bubble Sort introduction: they swap places with enemies ahead.", g(BUBBLE_SORT, 8, 2.0, 0), g(DYNAMIC_ARRAY, 12, 0.6, 6));
        w(21, null, g(BUBBLE_SORT, 12, 1.2, 0), g(STATIC_ARRAY, 20, 0.4, 0));
        w(22, "Selection Sort jumps to the front of groups.", g(SELECTION_SORT, 8, 1.5, 0), g(BUBBLE_SORT, 8, 1.2, 4), g(DYNAMIC_ARRAY, 10, 0.6, 8));
        w(23, "Insertion Sort leapfrogs.", g(INSERTION_SORT, 10, 1.0, 0), g(SINGLY_LINKED_LIST, 12, 0.5, 6));
        w(24, "Camo introduced: detection required.", g(PRIMITIVE_VARIABLE, 20, "C", 0.5, 0), g(STATIC_ARRAY, 12, "C", 0.8, 8));
        w(25, "Shell Sort gap-jumps.", g(SHELL_SORT, 8, 1.5, 0), g(BUBBLE_SORT, 10, 1.0, 4), g(SELECTION_SORT, 8, 1.0, 10), g(DYNAMIC_ARRAY, 12, "C", 0.6, 14));
        w(26, "Merge Sort splits in two.", g(MERGE_SORT, 6, 2.0, 0), g(INSERTION_SORT, 10, 0.8, 5));
        w(27, "Quick Sort partitions.", g(QUICK_SORT, 5, 2.5, 0), g(SINGLY_LINKED_LIST, 15, 0.4, 5));
        w(28, "Heap Sort (Lead-type, shields allies) and Fortified introduced.", g(HEAP_SORT, 4, 3.0, 0), g(BUBBLE_SORT, 12, "F", 1.0, 3));
        w(29, "Counting Sort releases four Primitives.", g(COUNTING_SORT, 10, 1.0, 0), g(DOUBLY_LINKED_LIST, 10, "C", 0.8, 6), g(SHELL_SORT, 8, 1.2, 10));
        w(30, "Splitter rush.", g(MERGE_SORT, 10, 1.2, 0), g(SELECTION_SORT, 10, 0.8, 4), g(QUICK_SORT, 6, 1.5, 8), g(BUBBLE_SORT, 10, "R", 1.0, 12));
        w(31, "Radix Sort: digit armour changes every two layers.", g(RADIX_SORT, 5, 2.5, 0), g(DYNAMIC_ARRAY, 20, 0.5, 2));
        w(32, "Bucket Sort stores weaker enemies.", g(BUCKET_SORT, 4, 3.0, 0), g(PRIMITIVE_VARIABLE, 30, 0.3, 2), g(STATIC_ARRAY, 15, 0.5, 5));
        w(33, "Camo sorters.", g(INSERTION_SORT, 15, "C", 0.7, 0), g(SHELL_SORT, 10, "C", 1.0, 5));
        w(34, "TimSort: fast hybrid splitter.", g(TIMSORT, 4, 3.0, 0), g(MERGE_SORT, 8, 1.2, 4));
        w(35, null, g(HEAP_SORT, 6, 2.0, 0), g(QUICK_SORT, 8, 1.5, 3), g(COUNTING_SORT, 12, 0.8, 8));
        w(36, "Speed test.", g(DOUBLY_LINKED_LIST, 20, 0.5, 0), g(SINGLY_LINKED_LIST, 20, "C", 0.4, 4), g(SHELL_SORT, 10, "F", 1.2, 8));
        w(37, null, g(RADIX_SORT, 8, 1.5, 0), g(BUCKET_SORT, 5, 2.0, 5), g(SELECTION_SORT, 12, 0.8, 8));
        w(38, null, g(QUICK_SORT, 10, "F", 1.5, 0), g(MERGE_SORT, 10, "R", 1.0, 4), g(INSERTION_SORT, 12, 0.8, 10));
        w(39, "Everything so far, at once.", g(TIMSORT, 6, 2.0, 0), g(HEAP_SORT, 6, "C", 2.0, 5), g(BUBBLE_SORT, 15, "R", 0.8, 2), g(DYNAMIC_ARRAY, 25, "C", 0.4, 8));

        // ---------------- Waves 40-59: first boss, advanced combinations ----------------
        w(40, "BOSS: Bellarmine College Prep (MOAB). Heavy armour; releases 4 Quick Sorts.", g(BELLARMINE_COLLEGE_PREP, 1, 1, 5), g(QUICK_SORT, 8, 1.5, 10), g(SHELL_SORT, 10, 1.0, 20));
        w(41, null, g(MERGE_SORT, 15, 0.8, 0), g(SELECTION_SORT, 12, "C", 0.8, 5), g(COUNTING_SORT, 15, 0.6, 10));
        w(42, "Fortified Heaps.", g(HEAP_SORT, 8, "F", 1.5, 0), g(INSERTION_SORT, 15, 0.6, 4));
        w(43, null, g(RADIX_SORT, 10, 1.2, 0), g(QUICK_SORT, 10, 1.2, 6), g(SINGLY_LINKED_LIST, 25, "C", 0.3, 10));
        w(44, "Bucket swarm.", g(BUCKET_SORT, 8, 1.5, 0), g(PRIMITIVE_VARIABLE, 40, 0.2, 2), g(STATIC_ARRAY, 30, 0.3, 4), g(DYNAMIC_ARRAY, 20, 0.4, 8));
        w(45, "Two MOABs.", g(BELLARMINE_COLLEGE_PREP, 2, 8.0, 5), g(TIMSORT, 6, 2.0, 15));
        w(46, "Camo splitters.", g(TIMSORT, 8, "C", 1.5, 0), g(MERGE_SORT, 12, "C", 1.0, 4));
        w(47, "Regrow rush.", g(QUICK_SORT, 15, "R", 1.0, 0), g(SHELL_SORT, 15, "R", 0.8, 5), g(DOUBLY_LINKED_LIST, 15, "R", 0.6, 10));
        w(48, null, g(HEAP_SORT, 10, 1.2, 0), g(RADIX_SORT, 8, "F", 1.5, 6), g(BUBBLE_SORT, 20, 0.6, 3));
        w(49, "Camo + Fortified Shells.", g(SELECTION_SORT, 20, "C", 0.6, 0), g(INSERTION_SORT, 20, "C", 0.6, 3), g(SHELL_SORT, 12, "CF", 1.0, 10));
        w(50, "Three MOABs. On The Singularity Core the Event Horizon collapses 15 s in.", g(BELLARMINE_COLLEGE_PREP, 3, 6.0, 3), g(QUICK_SORT, 12, "F", 1.2, 10), g(TIMSORT, 8, 1.5, 20));
        w(51, null, g(BUCKET_SORT, 10, "R", 1.2, 0), g(COUNTING_SORT, 20, 0.5, 3), g(DYNAMIC_ARRAY, 30, "R", 0.4, 6));
        w(52, null, g(TIMSORT, 12, 1.2, 0), g(MERGE_SORT, 15, "F", 0.8, 5));
        w(53, "Fortified MOABs.", g(BELLARMINE_COLLEGE_PREP, 2, "F", 8.0, 4), g(HEAP_SORT, 10, "C", 1.2, 10), g(RADIX_SORT, 10, 1.0, 14));
        w(54, "Camo speed rush.", g(SINGLY_LINKED_LIST, 40, "C", 0.25, 0), g(DOUBLY_LINKED_LIST, 25, "C", 0.4, 5), g(SHELL_SORT, 15, "C", 0.8, 10));
        w(55, null, g(QUICK_SORT, 20, 0.8, 0), g(BUCKET_SORT, 8, "F", 1.5, 6), g(SELECTION_SORT, 15, "R", 0.7, 12));
        w(56, "Camo MOABs: detection is mandatory.", g(BELLARMINE_COLLEGE_PREP, 3, "C", 6.0, 3), g(INSERTION_SORT, 20, "C", 0.5, 10), g(TIMSORT, 8, "C", 1.2, 16));
        w(57, null, g(RADIX_SORT, 15, 0.8, 0), g(HEAP_SORT, 12, "F", 1.0, 5), g(COUNTING_SORT, 25, 0.4, 10));
        w(58, "Regrow splitters.", g(TIMSORT, 15, "R", 1.0, 0), g(MERGE_SORT, 20, "R", 0.6, 4), g(QUICK_SORT, 15, "R", 0.8, 10));
        w(59, "Four Fortified MOABs.", g(BELLARMINE_COLLEGE_PREP, 4, "F", 5.0, 2), g(BUCKET_SORT, 10, 1.2, 10), g(SHELL_SORT, 20, "F", 0.6, 15), g(DOUBLY_LINKED_LIST, 20, 0.4, 20));

        // ---------------- Waves 60-79: BFB and late-game rushes ----------------
        w(60, "BOSS: SW Resource Consultant (BFB). Weak hits halved; releases 3 MOABs.", g(SW_RESOURCE_CONSULTANT, 1, 1, 5), g(QUICK_SORT, 10, 1.0, 15), g(HEAP_SORT, 8, 1.5, 25));
        w(61, null, g(TIMSORT, 15, 0.9, 0), g(RADIX_SORT, 12, "F", 1.0, 6));
        w(62, null, g(BELLARMINE_COLLEGE_PREP, 4, 4.0, 3), g(MERGE_SORT, 25, 0.5, 10), g(INSERTION_SORT, 25, "C", 0.4, 14));
        w(63, null, g(BUCKET_SORT, 12, "R", 1.0, 0), g(SELECTION_SORT, 25, "R", 0.5, 3), g(COUNTING_SORT, 30, 0.3, 8));
        w(64, "Camo heavy.", g(HEAP_SORT, 15, "C", 0.8, 0), g(QUICK_SORT, 20, "C", 0.7, 5), g(SINGLY_LINKED_LIST, 40, "C", 0.2, 12));
        w(65, null, g(BELLARMINE_COLLEGE_PREP, 4, "F", 4.0, 2), g(TIMSORT, 12, "F", 1.0, 12), g(SHELL_SORT, 25, 0.5, 20));
        w(66, null, g(RADIX_SORT, 20, 0.6, 0), g(BUCKET_SORT, 12, "F", 1.0, 8));
        w(67, "Camo Regrow speedsters.", g(DOUBLY_LINKED_LIST, 40, "CR", 0.3, 0), g(SHELL_SORT, 20, "CR", 0.6, 6), g(INSERTION_SORT, 20, "CR", 0.6, 12));
        w(68, "Fortified BFB.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 4), g(BELLARMINE_COLLEGE_PREP, 2, 6.0, 20), g(QUICK_SORT, 20, 0.7, 10));
        w(69, null, g(TIMSORT, 20, "C", 0.8, 0), g(MERGE_SORT, 30, "F", 0.5, 5), g(HEAP_SORT, 12, 1.0, 12));
        w(70, "Four MOABs.", g(BELLARMINE_COLLEGE_PREP, 4, 3.5, 2), g(BUCKET_SORT, 12, "C", 1.0, 10), g(COUNTING_SORT, 30, "R", 0.3, 14), g(RADIX_SORT, 12, "C", 0.8, 20));
        w(71, null, g(QUICK_SORT, 30, "R", 0.5, 0), g(SELECTION_SORT, 30, "C", 0.4, 4));
        w(72, "BFB with a TimSort escort.", g(SW_RESOURCE_CONSULTANT, 1, 12.0, 3), g(TIMSORT, 25, 0.8, 15));
        w(73, "Fortified armour wall.", g(HEAP_SORT, 20, "F", 0.7, 0), g(RADIX_SORT, 20, "F", 0.7, 5), g(SHELL_SORT, 25, "C", 0.5, 10));
        w(74, "Camo blitz.", g(SINGLY_LINKED_LIST, 60, "C", 0.15, 0), g(DOUBLY_LINKED_LIST, 40, "CR", 0.3, 6), g(INSERTION_SORT, 30, "C", 0.4, 12));
        w(75, null, g(BELLARMINE_COLLEGE_PREP, 4, "F", 3.5, 2), g(SW_RESOURCE_CONSULTANT, 1, 1, 25), g(TIMSORT, 20, "F", 0.8, 12));
        w(76, null, g(BUCKET_SORT, 15, "R", 0.8, 0), g(MERGE_SORT, 30, "CR", 0.4, 4), g(QUICK_SORT, 25, "C", 0.6, 10));
        w(77, null, g(RADIX_SORT, 25, 0.5, 0), g(HEAP_SORT, 20, "C", 0.7, 6), g(COUNTING_SORT, 40, 0.25, 12));
        w(78, "Fortified BFB with camo MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 10.0, 3), g(BELLARMINE_COLLEGE_PREP, 4, "C", 4.0, 20), g(SHELL_SORT, 30, "F", 0.5, 10));
        w(79, "Sorter flood.", g(TIMSORT, 30, 0.5, 0), g(QUICK_SORT, 30, "F", 0.5, 5), g(SELECTION_SORT, 30, "R", 0.4, 10), g(BUBBLE_SORT, 30, "R", 0.4, 15));

        // ---------------- Waves 80-89: ZOMG and escalating Fortified bosses ----------------
        w(80, "BOSS: 3Com (ZOMG). Releases 3 BFBs, each releasing 3 MOABs.", g(THREE_COM, 1, 1, 5), g(TIMSORT, 15, 1.0, 30));
        w(81, null, g(BELLARMINE_COLLEGE_PREP, 5, "F", 3.0, 2), g(QUICK_SORT, 30, "F", 0.5, 10));
        w(82, null, g(SW_RESOURCE_CONSULTANT, 1, "F", 8.0, 3), g(TIMSORT, 25, 0.6, 15));
        w(83, "Fortified TimSort flood.", g(TIMSORT, 40, "F", 0.4, 0), g(HEAP_SORT, 25, "F", 0.6, 6));
        w(84, null, g(BELLARMINE_COLLEGE_PREP, 5, "F", 2.5, 2), g(SW_RESOURCE_CONSULTANT, 1, 10.0, 15), g(RADIX_SORT, 25, "F", 0.6, 20));
        w(85, "Fortified Quick Sort swarm.", g(QUICK_SORT, 50, "F", 0.3, 0), g(MERGE_SORT, 40, "F", 0.4, 5), g(BUCKET_SORT, 15, "F", 0.8, 12));
        w(86, null, g(SW_RESOURCE_CONSULTANT, 1, "F", 7.0, 2), g(TIMSORT, 30, "F", 0.5, 10));
        w(87, null, g(BELLARMINE_COLLEGE_PREP, 5, "F", 2.0, 2), g(SHELL_SORT, 30, "CF", 0.4, 8), g(INSERTION_SORT, 30, "CF", 0.4, 12));
        w(88, "Fortified BFB with a MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 5), g(BELLARMINE_COLLEGE_PREP, 3, "F", 4.0, 20), g(QUICK_SORT, 30, "F", 0.4, 15));
        w(89, null, g(SW_RESOURCE_CONSULTANT, 1, "F", 6.0, 2), g(TIMSORT, 40, "F", 0.4, 10), g(HEAP_SORT, 30, "CF", 0.5, 14));

        // ---------------- Waves 90-99: DDTs and the road to Palantir ----------------
        w(90, "BOSS: Lockheed Martin (DDT). Camo, fast, Lead-type. Detection is required.", g(LOCKHEED_MARTIN, 2, 8.0, 5), g(BELLARMINE_COLLEGE_PREP, 4, 4.0, 15), g(SINGLY_LINKED_LIST, 40, "C", 0.2, 10));
        w(91, "DDT pack with Fortified BFBs.", g(LOCKHEED_MARTIN, 1, 5.0, 3), g(SW_RESOURCE_CONSULTANT, 1, "F", 8.0, 15), g(TIMSORT, 30, "CF", 0.5, 10));
        w(92, "BFB with a Fortified MOAB wall.", g(SW_RESOURCE_CONSULTANT, 1, 1, 3), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.5, 25), g(RADIX_SORT, 30, "CF", 0.5, 10));
        w(93, "Fortified DDTs and camo-fortified sorters.", g(LOCKHEED_MARTIN, 1, "F", 4.0, 2), g(QUICK_SORT, 50, "CF", 0.3, 10), g(SHELL_SORT, 40, "CF", 0.4, 15));
        w(94, null, g(SW_RESOURCE_CONSULTANT, 1, 6.0, 2), g(TIMSORT, 50, "F", 0.35, 10), g(BUCKET_SORT, 20, "F", 0.6, 20));
        w(95, "Fortified BFB with DDT escort.", g(SW_RESOURCE_CONSULTANT, 1, "F", 1, 3), g(LOCKHEED_MARTIN, 1, 5.0, 25), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.0, 15));
        w(96, "Regrow DDTs and a camo-regrow blitz.", g(LOCKHEED_MARTIN, 2, "R", 3.0, 2), g(DOUBLY_LINKED_LIST, 60, "CR", 0.2, 10), g(INSERTION_SORT, 50, "CR", 0.3, 14));
        w(97, "BFB with a Fortified MOAB escort.", g(SW_RESOURCE_CONSULTANT, 1, 12.0, 2), g(BELLARMINE_COLLEGE_PREP, 2, "F", 3.0, 20), g(TIMSORT, 40, "CF", 0.4, 12));
        w(98, "DDT and MOAB flood under heavy armour.", g(LOCKHEED_MARTIN, 1, "F", 3.0, 2), g(BELLARMINE_COLLEGE_PREP, 3, "F", 2.0, 10), g(HEAP_SORT, 40, "CF", 0.4, 15), g(RADIX_SORT, 30, "CF", 0.4, 20));
        w(99, "Final rehearsal: BFB, MOAB and DDT classes together before the BAD.", g(SW_RESOURCE_CONSULTANT, 1, "F", 12.0, 2), g(BELLARMINE_COLLEGE_PREP, 3, "F", 6.0, 25), g(LOCKHEED_MARTIN, 1, 4.0, 40), g(TIMSORT, 50, "F", 0.3, 10));

        // ---------------- Wave 100: PALANTIR ----------------
        w(100, "FINAL BOSS: Palantir (BAD). Three phases, Predictive Surveillance. Victory when its body is destroyed.",
            g(PALANTIR, 1, 1, 8), g(LOCKHEED_MARTIN, 4, 6.0, 30), g(BELLARMINE_COLLEGE_PREP, 8, "F", 4.0, 45));

        if (WAVES.size() != WAVE_COUNT) throw new IllegalStateException("Expected 100 waves, got " + WAVES.size());
        for (int i = 0; i < WAVES.size(); i++) WAVES.set(i, InjectionSchedule.apply(WAVES.get(i)));   // PROMPT INJECTION from wave 30
    }
}
