"""The unchanged-part paint cache (acm.PaintCache) must never change a pixel.

Tower sprites record the runs of parts that stayed unchanged for a few frames into Skia pictures and replay them.
These tests paint the same state with the cache on and off and compare pixels: a busy late-game board over many
frames (every tower type, tiers, aiming, firing, abilities, upgrades, sales), and every kind of change to a part that
is currently replayed from a recording (each mutator, level of detail, the Graphics state the run starts from).
"""
import random

import numpy as np
import skia

from lindefense.sim.difficulty import Difficulty
from lindefense.tools.perf_bench import PerfBench
from lindefense.ui import acm
from lindefense.ui.acm import GCompound, GOval, GPolygon, GRect, PaintCache
from lindefense.ui.jawt import AlphaComposite, BasicStroke, Color, Graphics2D, reset_canvas_state
from lindefense.ui.sprites.thick import Thick
from lindefense.ui.sprites.towers.flat import Flat
from lindefense.ui.sprites.towers.turret import Turret


def _paint(root, w, h, scale, prep=None):
    surf = skia.Surface(w, h)
    cv = surf.getCanvas()
    cv.clear(0xFF101820)
    reset_canvas_state(cv)
    g = Graphics2D(cv)
    g.scale(scale, scale)
    if prep is not None:
        prep(g)
    root.paint_object(g)
    reset_canvas_state(cv)
    return surf.makeImageSnapshot().toarray()


def _both(root, w, h, scale, prep=None):
    """(cached paint, uncached paint) of the same state; Python's random state is replayed for the second paint."""
    state = random.getstate()
    on = _paint(root, w, h, scale, prep)
    random.setstate(state)
    PaintCache.enabled = False
    try:
        off = _paint(root, w, h, scale, prep)
    finally:
        PaintCache.enabled = True
    return on, off


def _replayed():
    """Counts _Run replays while active (to prove the cache was actually exercised)."""
    n = [0]
    orig = acm._Run.replay

    def replay(self, g):
        n[0] += 1
        return orig(self, g)
    acm._Run.replay = replay
    return n, lambda: setattr(acm._Run, "replay", orig)


def test_busy_board_paints_identically_with_and_without_the_cache(check):
    random.seed(5)
    g = PerfBench.late_game(2, Difficulty.values()[1], 40, 30)
    rig = PerfBench.RenderRig(g, 800, 500)
    PerfBench.spawn_crowd(g, 120, 0)
    tm = g.get_tower_manager()
    n, restore = _replayed()
    try:
        for f in range(150):
            if f % 50 == 0:
                PerfBench.fire_abilities(g)
            if f == 70:   # an upgrade rebuilds a tower's art; a sale removes a sprite
                towers = [t for t in tm.get_player_towers() if t.get_tier() < t.get_max_tier()]
                if towers:
                    tm.upgrade(towers[0])
                sold = tm.get_player_towers()[-1]
                tm.sell(sold)
            rig.screen.frame(1 / 60.0)
            if f >= 5 and f % 12 == 0:
                on, off = _both(rig.canvas, 800, 500, 1.0)
                check(np.array_equal(on, off), "frame %d: cached paint differs in %d pixels"
                      % (f, int((on != off).any(axis=2).sum())))
            else:
                _paint(rig.canvas, 800, 500, 1.0)
    finally:
        restore()
    check(n[0] > 1000, "the cache replayed recorded runs (%d)" % n[0])


class _Box(GCompound):
    """A tower-like compound: records runs like TowerArt / TowerSprite."""
    _run_cache = True


def _scene():
    root = _Box()
    shapes = []
    for i in range(4):
        r = GRect(10 + 30 * i, 10, 20, 14)
        r.set_filled(True)
        r.set_fill_color(Color(40 + 50 * i, 90, 160))
        r.set_color(Color(250, 250, 250))
        root.add(r)
        shapes.append(r)
    o = Thick.Oval(20, 40, 50, 30)
    o.set_filled(True)
    o.set_fill_color(Color(200, 80, 60))
    o.set_line_width(3)
    root.add(o)
    p = Flat.Poly()
    for x, y in ((90, 40), (140, 50), (120, 80), (95, 70)):
        p.add_vertex(x, y)
    p.set_filled(True)
    p.set_fill_color(Color(60, 200, 120))
    Flat.detail(p, Thick.DETAIL_DECOR)
    root.add(p)
    inner = GCompound()
    q = GOval(0, 0, 18, 18)
    q.set_filled(True)
    q.set_fill_color(Color(255, 220, 0, 160))
    inner.add(q)
    inner.set_location(150, 60)
    root.add(inner)
    t = Thick.Poly()
    for x, y in ((10, 90), (60, 95), (30, 115)):
        t.add_vertex(x, y)
    t.set_filled(True)
    t.set_fill_color(Color(120, 120, 240))
    t.set_line_width(2)
    root.add(t)
    return root, shapes, o, p, inner, q, t


def _settle(root):
    for _ in range(PaintCache.STABLE_FRAMES + 2):
        _paint(root, 200, 140, 1.3)
        PaintCache.next_frame()


def test_every_change_to_a_replayed_part_shows(check):
    root, shapes, o, p, inner, q, t = _scene()
    changes = [
        ("set_fill_color", lambda: shapes[1].set_fill_color(Color(255, 0, 0))),
        ("set_color", lambda: shapes[2].set_color(Color(0, 0, 0, 0))),
        ("set_location", lambda: shapes[0].set_location(14, 12)),
        ("set_size", lambda: shapes[3].set_size(26, 9)),
        ("set_visible off", lambda: shapes[2].set_visible(False)),
        ("set_visible on", lambda: shapes[2].set_visible(True)),
        ("set_filled", lambda: o.set_filled(False)),
        ("set_line_width", lambda: o.set_line_width(0.5)),
        ("Thick set_detail", lambda: t.set_detail(Thick.DETAIL_DECOR)),
        ("Flat set_detail", lambda: Flat.detail(p, 0)),
        ("Flat set_outline_detail", lambda: p.set_outline_detail(Thick.DETAIL_DECOR)),
        ("add_vertex", lambda: t.add_vertex(5, 100)),
        ("rotate", lambda: p.rotate(17)),
        ("scale", lambda: p.scale(1.2)),
        ("nested child moves", lambda: q.set_location(4, 3)),
        ("nested compound moves", lambda: inner.set_location(156, 64)),
        ("child added", lambda: inner.add(GRect(-30, -20, 8, 8))),
        ("child removed", lambda: root.remove(shapes[3])),
        ("z order", lambda: shapes[0].send_to_front()),
    ]
    n, restore = _replayed()
    try:
        for name, change in changes:
            _settle(root)
            before = n[0]
            on, off = _both(root, 200, 140, 1.3)
            check(n[0] > before, "%s: the settled scene is replayed from the cache" % name)
            check(np.array_equal(on, off), "%s: settled scene identical" % name)
            change()
            on, off = _both(root, 200, 140, 1.3)
            check(np.array_equal(on, off), "%s: the change shows at once (%d pixels differ)"
                  % (name, int((on != off).any(axis=2).sum())))
    finally:
        restore()


def test_state_left_by_a_replayed_run_reaches_later_siblings(check):
    """A shape without a colour of its own paints in, and leaves the Graphics at, black; a later sibling that is
    painted directly (it changes every frame) and has no colour either inherits that."""
    root = _Box()
    a = GRect(10, 10, 30, 20)
    a.set_filled(True)
    a.set_fill_color(Color(200, 40, 40))
    root.add(a)
    b = GRect(50, 10, 30, 20)
    b.set_filled(True)
    root.add(b)
    moving = GRect(100, 10, 30, 20)
    root.add(moving)
    n, restore = _replayed()
    green = lambda g: g.set_color(Color(10, 200, 30))
    try:
        for f in range(PaintCache.STABLE_FRAMES + 3):
            moving.set_location(100 + (f % 2) * 0.5, 10)
            _paint(root, 160, 50, 1.0, green)
            PaintCache.next_frame()
        before = n[0]
        on, off = _both(root, 160, 50, 1.0, green)
    finally:
        restore()
    check(n[0] > before, "the unchanged shapes are replayed")
    check(np.array_equal(on, off), "the moving outline gets the colour the replayed run left behind")


def test_level_of_detail_and_graphics_state_are_part_of_the_key(check):
    root, shapes, o, p, inner, q, t = _scene()
    _settle(root)
    for lod in (1, 2, 0):
        prev = Thick.set_level(lod)
        try:
            on, off = _both(root, 200, 140, 1.3)
        finally:
            Thick.set_level(prev)
        check(np.array_equal(on, off), "level of detail %d" % lod)
    states = {
        "translucent composite": lambda g: g.set_composite(AlphaComposite.get_instance(AlphaComposite.SRC_OVER, 0.4)),
        "inherited colour": lambda g: g.set_color(Color(255, 0, 255)),
        "inherited stroke": lambda g: g.set_stroke(BasicStroke(4.0)),
        "different scale": lambda g: g.scale(0.7, 1.1),
    }
    for name, prep in states.items():
        on, off = _both(root, 200, 140, 1.3, prep)
        check(np.array_equal(on, off), "Graphics state: %s" % name)
    on, off = _both(root, 200, 140, 1.3)
    check(np.array_equal(on, off), "back to the plain state")


def test_turret_paints_its_heading_as_a_rotation(check):
    """A turret no longer rotates its parts' vertices; paint() rotates them. The picture must match parts rotated
    the old way."""
    def build():
        tu = Turret()
        tu.poly([0, -4, 26, -3, 26, 3, 0, 4], Color(90, 160, 220))
        tu.plain([18, -2, 24, -2, 24, 2, 18, 2], Color(255, 230, 120))
        return tu
    for deg in (0, 33, 90, 181, -127):
        a = deg * np.pi / 180
        new = build()
        new.set_angle(a)
        new.set_location(40, 40)
        old = build()
        old.set_location(40, 40)
        for part in old.parts:   # what Turret.set_angle did before
            part.rotate(-np.degrees(a))
        img_new = _paint(new, 80, 80, 1.0)
        PaintCache.enabled = False
        try:
            img_old = _paint(_Plain(old), 80, 80, 1.0)
        finally:
            PaintCache.enabled = True
        # Skia strokes the outline before rotating it rather than after, so single edge pixels may differ by a few
        # dozen levels; the shapes themselves must coincide (a wrong angle or sign differs by ~200 after the blur)
        diff = np.abs(_blur(img_new) - _blur(img_old)).max()
        check(diff <= 40, "heading %d degrees: blurred pictures differ by %.0f levels" % (deg, diff))
        check(new.get_angle() == a, "heading %d degrees is kept" % deg)
    wrong = build()
    wrong.set_angle(-0.6)
    wrong.set_location(40, 40)
    right = build()
    right.set_location(40, 40)
    for part in right.parts:
        part.rotate(-np.degrees(0.6))
    PaintCache.enabled = False
    try:
        ref = _paint(_Plain(right), 80, 80, 1.0)
    finally:
        PaintCache.enabled = True
    check(np.abs(_blur(_paint(wrong, 80, 80, 1.0)) - _blur(ref)).max() > 100, "the comparison notices a wrong heading")


def _blur(img):
    """3x3 box blur (float), to compare shapes without single edge pixels."""
    img = img.astype(float)
    pad = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    out = np.zeros_like(img)
    for dy in range(3):
        for dx in range(3):
            out += pad[dy:dy + img.shape[0], dx:dx + img.shape[1]]
    return out / 9.0


class _Plain(GCompound):
    """Paints a turret's children without its rotation (the vertices were rotated instead)."""
    def __init__(self, tu):
        GCompound.__init__(self)
        self.tu = tu

    def paint(self, g):
        g2 = g.create()
        g2.translate(self.tu.get_x(), self.tu.get_y())
        for o in self.tu._contents:
            if o.is_visible():
                o.paint_object(g2)
