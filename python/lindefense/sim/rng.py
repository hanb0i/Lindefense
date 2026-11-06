"""Seedable random source shared by the simulation so headless runs are reproducible (matches the Java build)."""
from lindefense.javacompat import JavaRandom, wrap64


class Rng:
    __slots__ = ("_random",)

    def __init__(self, seed: int):
        # scramble the seed: java.util.Random yields near-identical first values for sequential seeds
        self._random = JavaRandom(wrap64(wrap64((seed + 1) * 0x9E3779B97F4A7C15) ^ 0x5DEECE66D))
        for _ in range(4):
            self._random.next_double()

    def next(self) -> float:
        return self._random.next_double()

    def next_int(self, bound: int) -> int:
        return self._random.next_int(bound)

    def chance(self, p: float) -> bool:
        return self._random.next_double() < p

    def range(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self._random.next_double()
