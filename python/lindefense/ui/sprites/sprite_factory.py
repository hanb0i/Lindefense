"""Lindefense SpriteFactory (ported from src/lindefense/ui/sprites/SpriteFactory.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.enemy.types import EnemyType


class SpriteFactory:
    """Creates the character model and one-shot effects for an enemy. Every
EnemyType constant maps to its own sprite class; unknown or future
constants fall back to GenericSprite rather than failing."""
    def __init__(self):
        pass
    @staticmethod
    def create(e):
        """Returns a freshly built sprite for the enemy, sized from Enemy#getRadius()."""
        t = e.get_type()
        if t is None:
            return GenericSprite(e)
        _sw1 = t
        if _sw1 is EnemyType.PRIMITIVE_VARIABLE:
            return PrimitiveVariableSprite(e)
        elif _sw1 is EnemyType.STATIC_ARRAY:
            return StaticArraySprite(e)
        elif _sw1 is EnemyType.DYNAMIC_ARRAY:
            return DynamicArraySprite(e)
        elif _sw1 is EnemyType.SINGLY_LINKED_LIST:
            return SinglyLinkedListSprite(e)
        elif _sw1 is EnemyType.DOUBLY_LINKED_LIST:
            return DoublyLinkedListSprite(e)
        elif _sw1 is EnemyType.BUBBLE_SORT:
            return BubbleSortSprite(e)
        elif _sw1 is EnemyType.SELECTION_SORT:
            return SelectionSortSprite(e)
        elif _sw1 is EnemyType.INSERTION_SORT:
            return InsertionSortSprite(e)
        elif _sw1 is EnemyType.SHELL_SORT:
            return ShellSortSprite(e)
        elif _sw1 is EnemyType.MERGE_SORT:
            return MergeSortSprite(e)
        elif _sw1 is EnemyType.MERGE_RUN:
            return MergeRunSprite(e)
        elif _sw1 is EnemyType.QUICK_SORT:
            return QuickSortSprite(e)
        elif _sw1 is EnemyType.QUICK_PARTITION:
            return QuickPartitionSprite(e)
        elif _sw1 is EnemyType.HEAP_SORT:
            return HeapSortSprite(e)
        elif _sw1 is EnemyType.COUNTING_SORT:
            return CountingSortSprite(e)
        elif _sw1 is EnemyType.RADIX_SORT:
            return RadixSortSprite(e)
        elif _sw1 is EnemyType.BUCKET_SORT:
            return BucketSortSprite(e)
        elif _sw1 is EnemyType.TIMSORT:
            return TimSortSprite(e)
        elif _sw1 is EnemyType.BELLARMINE_COLLEGE_PREP:
            return BellarmineSprite(e)
        elif _sw1 is EnemyType.SW_RESOURCE_CONSULTANT:
            return SwResourceConsultantSprite(e)
        elif _sw1 is EnemyType.THREE_COM:
            return ThreeComSprite(e)
        elif _sw1 is EnemyType.LOCKHEED_MARTIN:
            return LockheedMartinSprite(e)
        elif _sw1 is EnemyType.PALANTIR:
            return PalantirSprite(e)
        elif _sw1 is EnemyType.PALANTIR_HOLOGRAM:
            return PalantirSprite(e)
        else:
            return GenericSprite(e)
    @staticmethod
    def create_death_effect(e):
        """Death animation positioned at the enemy's location. Bosses get a
multi-stage explosion; Palantir gets its full defeat sequence."""
        if e.get_type() is EnemyType.PALANTIR:
            return PalantirDefeatEffect(e)
        if e.is_boss():
            return BossDeathEffect(e)
        return DeathEffect(e)
    @staticmethod
    def create_split_effect(parent):
        """Split animation for a parent whose outer body was destroyed and is
releasing children. Bosses reuse their explosion."""
        if parent.get_type() is EnemyType.PALANTIR:
            return PalantirDefeatEffect(parent)
        if parent.is_boss():
            return BossDeathEffect(parent)
        return SplitEffect(parent)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.bellarmine_sprite import BellarmineSprite  # noqa: E402
from lindefense.ui.sprites.boss_death_effect import BossDeathEffect  # noqa: E402
from lindefense.ui.sprites.bubble_sort_sprite import BubbleSortSprite  # noqa: E402
from lindefense.ui.sprites.bucket_sort_sprite import BucketSortSprite  # noqa: E402
from lindefense.ui.sprites.counting_sort_sprite import CountingSortSprite  # noqa: E402
from lindefense.ui.sprites.death_effect import DeathEffect  # noqa: E402
from lindefense.ui.sprites.doubly_linked_list_sprite import DoublyLinkedListSprite  # noqa: E402
from lindefense.ui.sprites.dynamic_array_sprite import DynamicArraySprite  # noqa: E402
from lindefense.ui.sprites.generic_sprite import GenericSprite  # noqa: E402
from lindefense.ui.sprites.heap_sort_sprite import HeapSortSprite  # noqa: E402
from lindefense.ui.sprites.insertion_sort_sprite import InsertionSortSprite  # noqa: E402
from lindefense.ui.sprites.lockheed_martin_sprite import LockheedMartinSprite  # noqa: E402
from lindefense.ui.sprites.merge_run_sprite import MergeRunSprite  # noqa: E402
from lindefense.ui.sprites.merge_sort_sprite import MergeSortSprite  # noqa: E402
from lindefense.ui.sprites.palantir_defeat_effect import PalantirDefeatEffect  # noqa: E402
from lindefense.ui.sprites.palantir_sprite import PalantirSprite  # noqa: E402
from lindefense.ui.sprites.primitive_variable_sprite import PrimitiveVariableSprite  # noqa: E402
from lindefense.ui.sprites.quick_partition_sprite import QuickPartitionSprite  # noqa: E402
from lindefense.ui.sprites.quick_sort_sprite import QuickSortSprite  # noqa: E402
from lindefense.ui.sprites.radix_sort_sprite import RadixSortSprite  # noqa: E402
from lindefense.ui.sprites.selection_sort_sprite import SelectionSortSprite  # noqa: E402
from lindefense.ui.sprites.shell_sort_sprite import ShellSortSprite  # noqa: E402
from lindefense.ui.sprites.singly_linked_list_sprite import SinglyLinkedListSprite  # noqa: E402
from lindefense.ui.sprites.split_effect import SplitEffect  # noqa: E402
from lindefense.ui.sprites.static_array_sprite import StaticArraySprite  # noqa: E402
from lindefense.ui.sprites.sw_resource_consultant_sprite import SwResourceConsultantSprite  # noqa: E402
from lindefense.ui.sprites.three_com_sprite import ThreeComSprite  # noqa: E402
from lindefense.ui.sprites.tim_sort_sprite import TimSortSprite  # noqa: E402
