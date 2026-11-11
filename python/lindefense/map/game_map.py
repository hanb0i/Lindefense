"""Map base class, obstacles and decorations. Maps own their routes, buildable-area rules and mechanic hooks."""
from lindefense.sim.vec import Vec

WIDTH = 1200
HEIGHT = 900
TRACK_HALF_WIDTH = 22.0


class Obstacle:
    """A rectangular non-buildable region; may block line of sight."""

    def __init__(self, x, y, w, h, blocks_line_of_sight: bool, label: str):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)
        self.blocks_line_of_sight = blocks_line_of_sight
        self.label = label
        self._c = (Vec(x, y), Vec(x + w, y), Vec(x + w, y + h), Vec(x, y + h))

    def contains(self, p: Vec, margin: float) -> bool:
        return (self.x - margin <= p.x <= self.x + self.w + margin
                and self.y - margin <= p.y <= self.y + self.h + margin)

    def intersects_segment(self, a: Vec, b: Vec) -> bool:
        if self.contains(a, 0) or self.contains(b, 0):
            return True
        c0, c1, c2, c3 = self._c
        return (_seg_hits(a, b, c0, c1) or _seg_hits(a, b, c1, c2)
                or _seg_hits(a, b, c2, c3) or _seg_hits(a, b, c3, c0))


def _cross(a, b, c):
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _seg_hits(p1, p2, p3, p4):
    d1, d2 = _cross(p3, p4, p1), _cross(p3, p4, p2)
    d3, d4 = _cross(p1, p2, p3), _cross(p1, p2, p4)
    return ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4))


class Decoration:
    """Simple decorative shape consumed by the renderer (thumbnails)."""
    RECT, OVAL, LABEL, LINE = "RECT", "OVAL", "LABEL", "LINE"

    def __init__(self, kind, x, y, w, h, rgb, text, filled):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h
        self.rgb, self.text, self.filled = rgb, text, filled

    @staticmethod
    def rect(x, y, w, h, rgb):
        return Decoration(Decoration.RECT, x, y, w, h, rgb, None, True)

    @staticmethod
    def frame(x, y, w, h, rgb):
        return Decoration(Decoration.RECT, x, y, w, h, rgb, None, False)

    @staticmethod
    def oval(x, y, w, h, rgb, filled):
        return Decoration(Decoration.OVAL, x, y, w, h, rgb, None, filled)

    @staticmethod
    def label(x, y, text, rgb):
        return Decoration(Decoration.LABEL, x, y, 0, 0, rgb, text, False)

    @staticmethod
    def line(x1, y1, x2, y2, rgb):
        return Decoration(Decoration.LINE, x1, y1, x2 - x1, y2 - y1, rgb, None, False)


class GameMap:
    WIDTH = WIDTH
    HEIGHT = HEIGHT
    TRACK_HALF_WIDTH = TRACK_HALF_WIDTH

    def __init__(self, name: str, difficulty: str, description: str):
        self.routes = []
        self.obstacles = []
        self.decorations = []
        self._name = name
        self._difficulty = difficulty
        self._description = description

    def get_name(self):
        return self._name

    def get_difficulty(self):
        return self._difficulty

    def get_description(self):
        return self._description

    def get_routes(self):
        return self.routes

    def get_obstacles(self):
        return self.obstacles

    def get_decorations(self):
        return self.decorations

    def get_background_rgb(self) -> int:
        raise NotImplementedError

    def get_track_rgb(self) -> int:
        raise NotImplementedError

    def get_mechanic_summary(self) -> str:
        raise NotImplementedError

    # ---- placement rules
    def min_track_clearance(self, tower_radius: float) -> float:
        return TRACK_HALF_WIDTH + tower_radius * 0.6

    def is_buildable(self, p: Vec, tower_radius: float) -> bool:
        if p.x < tower_radius or p.y < tower_radius or p.x > WIDTH - tower_radius or p.y > HEIGHT - tower_radius:
            return False
        clearance = self.min_track_clearance(tower_radius)
        for r in self.routes:
            if r.is_closer_than(p, clearance):
                return False
        for o in self.obstacles:
            if o.contains(p, tower_radius * 0.7):
                return False
        return self.is_inside_arena(p)

    def is_inside_arena(self, p: Vec) -> bool:
        return True

    def has_line_of_sight(self, frm: Vec, to: Vec) -> bool:
        for o in self.obstacles:
            if o.blocks_line_of_sight and o.intersects_segment(frm, to):
                return False
        return True

    def can_block_line_of_sight(self) -> bool:
        """False when has_line_of_sight is true for every segment (no sight-blocking obstacle), so callers may skip it."""
        return (type(self).has_line_of_sight is not GameMap.has_line_of_sight
                or any(o.blocks_line_of_sight for o in self.obstacles))

    # ---- mechanic hooks (default: none)
    def update(self, game, dt: float) -> None:
        pass

    def on_wave_start(self, game, wave: int) -> None:
        pass

    def on_enemy_moved(self, game, e) -> None:
        pass

    def enemy_speed_multiplier(self, e) -> float:
        return 1.0

    def tower_range_multiplier(self, game, t) -> float:
        return 1.0

    def tower_rate_multiplier(self, game, t) -> float:
        return 1.0

    def tower_damage_multiplier(self, game, t) -> float:
        return 1.0

    def get_event_text(self):
        return None

    def reset(self) -> None:
        pass

    def pick_route(self, game) -> int:
        """Random route index for spawning (a Server Outage closes one lane for the wave)."""
        closed = game.get_variance().closed_route(len(self.routes))
        if closed < 0:
            return game.get_rng().next_int(len(self.routes))
        r = game.get_rng().next_int(len(self.routes) - 1)
        return r + 1 if r >= closed else r

    def add_decoration(self, d: Decoration) -> None:
        self.decorations.append(d)

    # map subclasses rely on whether they override the per-enemy speed hook (skipped when not)
    def has_enemy_speed_hook(self) -> bool:
        return type(self).enemy_speed_multiplier is not GameMap.enemy_speed_multiplier
