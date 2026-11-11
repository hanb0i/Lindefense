"""The tutorial's own seven short waves (WaveManager.set_wave_list), one idea each, on The Silicon Circuit.

Fixed lanes (no random route picks), small counts and gentle enemies: the whole tutorial plays in a few minutes and is
the same every time. Lane A is the upper trace, lane B the lower one (only wave 6 uses it, to teach the tactical pause).
The boss is a Bellarmine College Prep at a fraction of its campaign health (hp_scale on its spawn group), so a handful of
early towers can bring it down while it still shows its Crest Shield.
"""
from lindefense.enemy.types import EnemyType as E
from lindefense.wave.waves import SpawnGroup, WaveDef, _mods

MAP_INDEX = 0          # The Silicon Circuit
LANE_A = 0             # upper trace
LANE_B = 1             # lower trace
BOSS_HP_SCALE = 0.12   # the "small boss": 12% of a campaign Bellarmine College Prep (about 200 HP)


def _g(t, n, interval, delay, route=LANE_A, mods=None, hp_scale=None):
    g = SpawnGroup(t, n, _mods(mods), interval, delay, route)
    if hp_scale is not None:
        g.hp_scale = hp_scale
    return g


def create():
    """Fresh WaveDefs for one tutorial match (waves 1..7)."""
    return (
        WaveDef(1, "Primitive Variables: the simplest enemy.",
                _g(E.PRIMITIVE_VARIABLE, 8, 1.4, 1)),
        WaveDef(2, "A denser stream of Primitive Variables.",
                _g(E.PRIMITIVE_VARIABLE, 16, 0.6, 1)),
        WaveDef(3, "Splitters: Dynamic Arrays shed a Static Array, then a Primitive; Merge Sorts split in two.",
                _g(E.DYNAMIC_ARRAY, 6, 1.6, 1), _g(E.MERGE_SORT, 2, 3.0, 11)),
        WaveDef(4, "Heap Sorts are Lead-type: Sharp damage cannot hurt them.",
                _g(E.HEAP_SORT, 3, 4.0, 1), _g(E.STATIC_ARRAY, 6, 1.2, 3)),
        WaveDef(5, "Camo: only towers with detection can see these.",
                _g(E.PRIMITIVE_VARIABLE, 10, 1.0, 1, mods="C"), _g(E.STATIC_ARRAY, 4, 1.6, 6, mods="C")),
        WaveDef(6, "Both traces: the second group takes the lower trace.",
                _g(E.STATIC_ARRAY, 6, 1.2, 1), _g(E.STATIC_ARRAY, 10, 1.0, 6, LANE_B)),
        WaveDef(7, "BOSS: Bellarmine College Prep raises a CREST SHIELD at half health.",
                _g(E.PRIMITIVE_VARIABLE, 6, 0.8, 1), _g(E.BELLARMINE_COLLEGE_PREP, 1, 1, 7, hp_scale=BOSS_HP_SCALE)),
    )


COUNT = 7
