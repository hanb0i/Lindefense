"""Spatial hash grid over the live enemies for every "enemies near a point" query.

Queries return a superset of the exact answer in live-list order, so a caller that applies its exact test to the
candidates visits the same enemies in the same order as a full scan (results stay deterministic). The grid
rebuilds lazily when the list's membership changes and moves enemies between buckets as they move.
"""
import math
from operator import attrgetter

from lindefense.map.game_map import WIDTH, HEIGHT

CELL = 48
COLS = (WIDTH + CELL - 1) // CELL
ROWS = (HEIGHT + CELL - 1) // CELL
_FULL_SCAN_CELLS = 0.5 * COLS * ROWS
CENTER_MARGIN = 1.0   # box widening for centre-only tests: covers float rounding of the box edges, nothing else
_floor = math.floor
_by_index = attrgetter("grid_index")


class EnemyList(list):
    """The live enemy list; every structural change bumps a version so the grid knows to rebuild."""

    def __init__(self):
        super().__init__()
        self.version = 0
        self.grid = None

    def append(self, x):
        self.version += 1
        super().append(x)

    def extend(self, xs):
        self.version += 1
        super().extend(xs)

    def insert(self, i, x):
        self.version += 1
        super().insert(i, x)

    def remove(self, x):
        self.version += 1
        super().remove(x)

    def pop(self, *a):
        self.version += 1
        return super().pop(*a)

    def clear(self):
        self.version += 1
        super().clear()

    def sort(self, *a, **k):
        self.version += 1
        super().sort(*a, **k)

    def __delitem__(self, i):
        self.version += 1
        super().__delitem__(i)

    def __iadd__(self, other):
        self.version += 1
        return super().__iadd__(other)

    def __reduce_ex__(self, protocol):
        """Pickling (saved runs): the items travel in the state, so unpickling never calls the counting overrides
        on an instance whose attributes are not restored yet."""
        return EnemyList, (), (dict(self.__dict__), list(self))

    def __setstate__(self, state):
        attrs, items = state
        list.extend(self, items)
        self.__dict__.update(attrs)


def _col(x):
    if x != x:
        return 0
    c = int(math.floor(x / CELL))
    return 0 if c < 0 else (COLS - 1 if c >= COLS else c)


def _row(y):
    if y != y:
        return 0
    r = int(math.floor(y / CELL))
    return 0 if r < 0 else (ROWS - 1 if r >= ROWS else r)


class EnemyGrid:
    CELL = CELL
    COLS = COLS
    ROWS = ROWS

    def __init__(self, lst: EnemyList):
        self._list = lst
        self._cells = [[[] for _ in range(ROWS)] for _ in range(COLS)]
        self._built_version = None
        self._epoch = 0
        self.cell_stamp = 0
        self._max_radius = 0.0
        lst.grid = self

    def _ensure(self):
        if self._built_version != self._list.version:
            self._rebuild()

    def _rebuild(self):
        for column in self._cells:
            for b in column:
                b.clear()
        self._epoch += 1
        self.cell_stamp += 1
        mr = 0.0
        ep = self._epoch
        cells = self._cells
        for i, e in enumerate(self._list):
            p = e._cached_pos   # get_position()
            # _col / _row inlined
            v = p.x
            c = 0 if v != v else _floor(v / CELL)
            c = 0 if c < 0 else (COLS - 1 if c >= COLS else c)
            v = p.y
            r = 0 if v != v else _floor(v / CELL)
            r = 0 if r < 0 else (ROWS - 1 if r >= ROWS else r)
            e.grid = self
            e.grid_epoch = ep
            e.grid_index = i
            e.grid_col = c
            e.grid_row = r
            cells[c][r].append(e)
            rad = e._radius   # get_radius()
            if rad > mr:
                mr = rad
        self._max_radius = mr
        self._built_version = self._list.version

    def moved(self, e) -> None:
        if e.grid_epoch != self._epoch:
            return
        p = e._cached_pos   # get_position()
        # _col / _row inlined (called after every enemy move)
        v = p.x
        c = 0 if v != v else _floor(v / CELL)
        c = 0 if c < 0 else (COLS - 1 if c >= COLS else c)
        v = p.y
        r = 0 if v != v else _floor(v / CELL)
        r = 0 if r < 0 else (ROWS - 1 if r >= ROWS else r)
        if c == e.grid_col and r == e.grid_row:
            return
        frm = self._cells[e.grid_col][e.grid_row]
        for i in range(len(frm) - 1, -1, -1):
            if frm[i] is e:
                frm[i] = frm[-1]
                frm.pop()
                break
        self._cells[c][r].append(e)
        e.grid_col = c
        e.grid_row = r
        self.cell_stamp += 1

    def max_radius(self) -> float:
        self._ensure()
        return self._max_radius

    def near(self, cx, cy, reach, out=None):
        return self.box(cx - reach, cy - reach, cx + reach, cy + reach, out)

    def box(self, x0, y0, x1, y1, out=None):
        if out is None:
            out = []
        else:
            out.clear()
        self._ensure()
        self._collect(x0, y0, x1, y1, 0, out, self._max_radius)
        return out

    def near_centers(self, cx, cy, reach, out=None):
        """Candidates for a test on the enemy's centre alone (centre within reach of (cx, cy), no radius term): the
        box is widened by CENTER_MARGIN (float rounding) instead of the largest radius, so fewer candidates.

        Only for loops that move no enemy: near()'s exact superset matters to a loop that knocks enemies about while
        re-testing a list gathered beforehand (Scan-style loops are exact with any such superset)."""
        if out is None:
            out = []
        else:
            out.clear()
        self._ensure()
        self._collect(cx - reach, cy - reach, cx + reach, cy + reach, 0, out, CENTER_MARGIN)
        return out

    def _collect(self, x0, y0, x1, y1, from_index, out, m):
        """Appends the enemies in the cells overlapping the box widened by m (index >= from_index), in list order."""
        lst = self._list
        if from_index >= len(lst):
            return
        # _col / _row inlined (this runs a few hundred times a step): floor(v / CELL) clamped to the grid, NaN -> 0
        v = x0 - m
        c0 = 0 if v != v else _floor(v / CELL)
        c0 = 0 if c0 < 0 else (COLS - 1 if c0 >= COLS else c0)
        v = x1 + m
        c1 = 0 if v != v else _floor(v / CELL)
        c1 = 0 if c1 < 0 else (COLS - 1 if c1 >= COLS else c1)
        v = y0 - m
        r0 = 0 if v != v else _floor(v / CELL)
        r0 = 0 if r0 < 0 else (ROWS - 1 if r0 >= ROWS else r0)
        v = y1 + m
        r1 = 0 if v != v else _floor(v / CELL)
        r1 = 0 if r1 < 0 else (ROWS - 1 if r1 >= ROWS else r1)
        if (c1 - c0 + 1) * (r1 - r0 + 1) >= _FULL_SCAN_CELLS:
            out.extend(lst[from_index:])
            return
        found = []
        for column in self._cells[c0:c1 + 1]:
            for b in column[r0:r1 + 1]:
                if b:
                    found += b
        if from_index:
            found = [e for e in found if e.grid_index >= from_index]
        # every enemy sits in exactly one bucket and grid_index is its position in the list (renumbered on every
        # membership change), so ordering by grid_index is list order
        if len(found) > 1:
            found.sort(key=_by_index)
        out += found

    def candidates(self, x0, y0, x1, y1, from_index, centers_only=False):
        """A new list of the box's candidates with list index >= from_index, in list order (what a Scan refills).

        For hot loops that inline a Scan: walk the list, and after any call that may move enemies or change the list
        (a hit: knockback, teleport, spawn), compare stamp() with the one taken here; if it changed, continue with
        candidates(..., index of the enemy just handled + 1, read before the call), exactly as Scan.next does.
        Such a walk equals a full index-ordered scan for any cell-based superset, so a loop whose test is on the
        enemy's centre alone (inside the box) may pass centers_only=True: CENTER_MARGIN instead of the largest radius."""
        self._ensure()
        out = []
        self._collect(x0, y0, x1, y1, from_index, out, CENTER_MARGIN if centers_only else self._max_radius)
        return out

    def stamp(self):
        """Changes whenever an enemy changes cell or the list's membership changes (see candidates)."""
        return self.cell_stamp, self._list.version

    def scan(self, cx, cy, reach):
        return Scan(self, cx - reach, cy - reach, cx + reach, cy + reach)

    def scan_box(self, x0, y0, x1, y1):
        return Scan(self, x0, y0, x1, y1)

    def scan_centers(self, cx, cy, reach):
        """A Scan for a test on the enemy's centre alone (centre within reach): box widened by CENTER_MARGIN only.
        A Scan matches a full index-ordered scan with any cell-based superset that holds every enemy passing the test."""
        return Scan(self, cx - reach, cy - reach, cx + reach, cy + reach, CENTER_MARGIN)


class Scan:
    """Index-ordered walk over a box's candidates that stays exact while the loop body moves enemies."""

    __slots__ = ("_g", "_buf", "_x0", "_y0", "_x1", "_y1", "_margin", "_pos", "_stamp", "_version", "_next_index")

    def __init__(self, g, x0, y0, x1, y1, margin=None):
        self._g = g
        self._buf = []
        self._x0, self._y0, self._x1, self._y1 = x0, y0, x1, y1
        self._margin = margin   # None: the grid's largest enemy radius
        self._next_index = 0
        self._refill()

    def _refill(self):
        g = self._g
        self._buf.clear()
        self._pos = 0
        g._ensure()
        m = g._max_radius if self._margin is None else self._margin
        g._collect(self._x0, self._y0, self._x1, self._y1, self._next_index, self._buf, m)
        self._stamp = g.cell_stamp
        self._version = g._list.version

    def next(self):
        g = self._g
        if self._stamp != g.cell_stamp or self._version != g._list.version:
            self._refill()
        pos = self._pos
        buf = self._buf
        if pos >= len(buf):
            return None
        e = buf[pos]
        self._pos = pos + 1
        self._next_index = e.grid_index + 1
        return e

    def __iter__(self):
        while True:
            e = self.next()
            if e is None:
                return
            yield e

    def close(self):
        pass
