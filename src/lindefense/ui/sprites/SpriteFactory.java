package lindefense.ui.sprites;

import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyType;

/**
 * Creates the character model and one-shot effects for an enemy. Every
 * {@link EnemyType} constant maps to its own sprite class; unknown or future
 * constants fall back to {@link GenericSprite} rather than failing.
 */
public final class SpriteFactory {
    private SpriteFactory() { }

    /** Returns a freshly built sprite for the enemy, sized from {@link Enemy#getRadius()}. */
    public static EnemySprite create(Enemy e) {
        EnemyType t = e.getType();
        if (t == null) return new GenericSprite(e);
        switch (t) {
            case PRIMITIVE_VARIABLE: return new PrimitiveVariableSprite(e);
            case STATIC_ARRAY: return new StaticArraySprite(e);
            case DYNAMIC_ARRAY: return new DynamicArraySprite(e);
            case SINGLY_LINKED_LIST: return new SinglyLinkedListSprite(e);
            case DOUBLY_LINKED_LIST: return new DoublyLinkedListSprite(e);
            case BUBBLE_SORT: return new BubbleSortSprite(e);
            case SELECTION_SORT: return new SelectionSortSprite(e);
            case INSERTION_SORT: return new InsertionSortSprite(e);
            case SHELL_SORT: return new ShellSortSprite(e);
            case MERGE_SORT: return new MergeSortSprite(e);
            case MERGE_RUN: return new MergeRunSprite(e);
            case QUICK_SORT: return new QuickSortSprite(e);
            case QUICK_PARTITION: return new QuickPartitionSprite(e);
            case HEAP_SORT: return new HeapSortSprite(e);
            case COUNTING_SORT: return new CountingSortSprite(e);
            case RADIX_SORT: return new RadixSortSprite(e);
            case BUCKET_SORT: return new BucketSortSprite(e);
            case TIMSORT: return new TimSortSprite(e);
            case BELLARMINE_COLLEGE_PREP: return new BellarmineSprite(e);
            case SW_RESOURCE_CONSULTANT: return new SwResourceConsultantSprite(e);
            case THREE_COM: return new ThreeComSprite(e);
            case LOCKHEED_MARTIN: return new LockheedMartinSprite(e);
            case PALANTIR: return new PalantirSprite(e);
            case PALANTIR_HOLOGRAM: return new PalantirSprite(e);   // the decoy wears Palantir's hull; the world view adds the hologram flicker
            default: return new GenericSprite(e);
        }
    }

    /**
     * Death animation positioned at the enemy's location. Bosses get a
     * multi-stage explosion; Palantir gets its full defeat sequence.
     */
    public static Animated createDeathEffect(Enemy e) {
        if (e.getType() == EnemyType.PALANTIR) return new PalantirDefeatEffect(e);
        if (e.isBoss()) return new BossDeathEffect(e);
        return new DeathEffect(e);
    }

    /**
     * Split animation for a parent whose outer body was destroyed and is
     * releasing children. Bosses reuse their explosion.
     */
    public static Animated createSplitEffect(Enemy parent) {
        if (parent.getType() == EnemyType.PALANTIR) return new PalantirDefeatEffect(parent);
        if (parent.isBoss()) return new BossDeathEffect(parent);
        return new SplitEffect(parent);
    }
}
