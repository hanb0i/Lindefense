"""Spatial hash grid over the live enemies for every "enemies near a point" query.

Queries return a superset of the exact answer in live-list order, so a caller that applies its exact test to the
candidates visits the same enemies in the same order as a full scan (results stay deterministic). The grid
rebuilds lazily when the list's membership changes and moves enemies between buckets as they move.
"""
import math

from lindefense.map.game_map import WIDTH, HEIGHT

CELL = 48
COLS = (WIDTH + CELL - 1) // CELL
ROWS = (HEIGHT + CELL - 1) // CELL
_FULL_SCAN_CELLS = 0.5 * COLS * ROWS


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
            p = e.get_position()
            c, r = _col(p.x), _row(p.y)
            e.grid = self
            e.grid_epoch = ep
            e.grid_index = i
            e.grid_col = c
            e.grid_row = r
            cells[c][r].append(e)
            rad = e.get_radius()
            if rad > mr:
                mr = rad
        self._max_radius = mr
        self._built_version = self._list.version

    def moved(self, e) -> None:
        if e.grid_epoch != self._epoch:
            return
        p = e.get_position()
        c, r = _col(p.x), _row(p.y)
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
        self._collect(x0, y0, x1, y1, 0, out)
        return out

    def _collect(self, x0, y0, x1, y1, from_index, out):
        lst = self._list
        n = len(lst)
        if from_index >= n:
            return
        m = self._max_radius
        c0, c1, r0, r1 = _col(x0 - m), _col(x1 + m), _row(y0 - m), _row(y1 + m)
        if (c1 - c0 + 1) * (r1 - r0 + 1) >= _FULL_SCAN_CELLS:
            out.extend(lst[from_index:])
            return
        idxs = []
        cells = self._cells
        for c in range(c0, c1 + 1):
            column = cells[c]
            for r in range(r0, r1 + 1):
                for e in column[r]:
                    gi = e.grid_index
                    if gi >= from_index:
                        idxs.append(gi)
        if not idxs:
            return
        idxs.sort()
        out.extend(lst[i] for i in idxs)

    def scan(self, cx, cy, reach):
        return Scan(self, cx - reach, cy - reach, cx + reach, cy + reach)

    def scan_box(self, x0, y0, x1, y1):
        return Scan(self, x0, y0, x1, y1)


class Scan:
    """Index-ordered walk over a box's candidates that stays exact while the loop body moves enemies."""

    __slots__ = ("_g", "_buf", "_x0", "_y0", "_x1", "_y1", "_pos", "_stamp", "_version", "_next_index")

    def __init__(self, g, x0, y0, x1, y1):
        self._g = g
        self._buf = []
        self._x0, self._y0, self._x1, self._y1 = x0, y0, x1, y1
        self._next_index = 0
        self._refill()

    def _refill(self):
        g = self._g
        self._buf.clear()
        self._pos = 0
        g._ensure()
        g._collect(self._x0, self._y0, self._x1, self._y1, self._next_index, self._buf)
        self._stamp = g.cell_stamp
        self._version = g._list.version

    def next(self):
        g = self._g
        if self._stamp != g.cell_stamp or self._version != g._list.version:
            self._refill()
        if self._pos >= len(self._buf):
            return None
        e = self._buf[self._pos]
        self._pos += 1
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
