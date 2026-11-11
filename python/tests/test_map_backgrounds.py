"""The map backgrounds (minimal, futuristic cyberpunk): on every map the track and the props that block placement stand
out from the ground, in thumbnails too; the low-resolution soft pass lines up with the crisp detail painted over it; the
vignette only darkens the far corners; the set dressing (the details: components, fans, debris, cars, trees...) is
there, stays off the track and the tower strips beside it, and is clearly quieter than the track; the live ambience
stays small, never moves along the track, and is off with REDUCED MOTION, on LOW quality and in the most crowded fights.
Everything is painted offscreen."""
import numpy as np
import pytest
import skia

from lindefense.map import maps
from lindefense.sim.vec import Vec
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.graphics_settings import GraphicsSettings
from lindefense.ui.jawt import BufferedImage, Graphics2D, reset_canvas_state
from lindefense.ui.map_art import MapArt
from lindefense.ui.sprites.thick import Thick


@pytest.fixture(autouse=True)
def _settings():
    ds, gs = DisplaySettings.get(), GraphicsSettings.get()
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    GraphicsSettings.set_instance(GraphicsSettings.in_memory())
    yield
    DisplaySettings.set_instance(ds)
    GraphicsSettings.set_instance(gs)
    Thick.set_level(0)


def _lum(argb):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch((argb >> 16) & 255) + 0.7152 * ch((argb >> 8) & 255) + 0.0722 * ch(argb & 255)


def _contrast(a, b):
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _median(v):
    v = sorted(v)
    return v[len(v) // 2]


def _pixels(img):
    return img.snapshot().toarray()   # rows x cols x RGBA


def _argb(px, x, y):
    r, g, b = (int(v) for v in px[int(y), int(x), :3])
    return (r << 16) | (g << 8) | b


def _ground_and_body(m, px, s):
    """Median luminance of the road body and of the buildable ground 70 px beside it."""
    body, ground = [], []
    for r in m.get_routes():
        d = 60.0
        while d < r.get_total_length() - 60:
            p, n = r.position_at(d), r.direction_at(d)
            body.append(_lum(_argb(px, (p.x + n.y * 11) * s, (p.y - n.x * 11) * s)))
            for side in (1, -1):
                q = Vec(p.x - n.y * 70 * side, p.y + n.x * 70 * side)
                if 0 < q.x < 1200 and 0 < q.y < 900 and m.is_buildable(q, 20):
                    ground.append(_lum(_argb(px, q.x * s, q.y * s)))
            d += 37
    return _median(body), _median(ground)


def test_track_and_blocking_props_stand_out(check):
    for s in (1.0, 0.25):
        for i in range(maps.MAP_COUNT):
            m = maps.create(i)
            px = _pixels(MapArt.bitmap(m, s, False))
            body, ground = _ground_and_body(m, px, s)
            check(_contrast(body, ground) >= 1.4, "%s @%.2f: the road body stands out from the ground (%.2f)"
                  % (m.get_name(), s, _contrast(body, ground)))
            if s < 1 or not m.get_obstacles():
                continue
            edges = []
            for o in m.get_obstacles():
                for k in range(1, 6):   # the brightest pixel within 3 px of the top and left edges: the neon outline
                    x, y = o.x + o.w * k / 6.0, o.y + o.h * k / 6.0
                    edges.append(max(_lum(_argb(px, x, o.y + dy)) for dy in range(-3, 4)))
                    edges.append(max(_lum(_argb(px, o.x + dx, y)) for dx in range(-3, 4)))
            check(_contrast(_median(edges), ground) >= 2.0, "%s: what blocks placement has a lit outline (%.2f)"
                  % (m.get_name(), _contrast(_median(edges), ground)))


def test_soft_pass_lines_up_with_the_crisp_detail(check, monkeypatch):
    """At HiDPI scales the ground, lights and big glows are painted at a lower resolution and scaled up; the result must
match painting everything at full resolution (no offset, no missing layer)."""
    def render(idx):
        img = BufferedImage(2400, 1800, BufferedImage.TYPE_INT_RGB)
        g = img.create_graphics()
        g.scale(2, 2)
        MapArt.render(g, maps.create(idx), True)
        g.dispose()
        small = BufferedImage(300, 225, BufferedImage.TYPE_INT_RGB)
        sg = small.create_graphics()
        sg.draw_image(img, 0, 0, 300, 225, None)
        sg.dispose()
        return _pixels(small).astype(int)
    for idx in (0, 3, 4):
        soft = render(idx)
        monkeypatch.setattr(MapArt.Painter, "begin_soft", lambda self: setattr(self, "soft", None))
        full = render(idx)
        monkeypatch.undo()
        diff = abs(soft[:, :, :3] - full[:, :, :3])
        check(diff.mean() < 1.0 and diff.max() < 32, "%s: soft pass matches a full-resolution paint (mean %.2f, max %d)"
              % (maps.create(idx).get_name(), diff.mean(), diff.max()))


def test_vignette_only_darkens_the_far_corners(check):
    m = maps.create(4)
    on, off = _pixels(MapArt.bitmap(m, 1.0, True)).astype(int), _pixels(MapArt.bitmap(m, 1.0, False)).astype(int)
    check(on[4, 4, :3].sum() < off[4, 4, :3].sum(), "a far corner is darker with the vignette")
    check(abs(on[450, 600, :3] - off[450, 600, :3]).max() <= 1, "the middle is untouched")


def _paint_live(p, t, surf):
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    p.set_time(t)
    p.paint(Graphics2D(cv))
    reset_canvas_state(cv)


def _lit(p, times):
    total = 0
    for t in times:
        surf = skia.Surface.MakeRasterN32Premul(1200, 900)
        surf.getCanvas().clear(0)
        _paint_live(p, t, surf)
        total += int((surf.makeImageSnapshot().toarray()[:, :, 3] > 0).sum())
    return total


def test_ambience_is_small_and_follows_the_settings(check):
    times = [k * 0.5 for k in range(40)]
    for i in range(maps.MAP_COUNT):
        m = maps.create(i)
        a = MapArt.ambience_for(m)
        check(1 <= a.count() <= 12, "%s: a few live items (%d)" % (m.get_name(), a.count()))
        check(_lit(MapArt.Pulses(m), times) > 0, "%s: the ambience shows on HIGH" % m.get_name())
    calm = DisplaySettings.in_memory()
    calm.reduced_motion = True
    DisplaySettings.set_instance(calm)
    check(all(_lit(MapArt.Pulses(maps.create(i)), times) == 0 for i in range(maps.MAP_COUNT)), "REDUCED MOTION: the map stays still")
    DisplaySettings.set_instance(DisplaySettings.in_memory())
    low = GraphicsSettings.in_memory()
    low.set_quality(GraphicsSettings.Quality.LOW)
    GraphicsSettings.set_instance(low)
    check(all(_lit(MapArt.Pulses(maps.create(i)), times) == 0 for i in range(maps.MAP_COUNT)), "LOW quality: no ambience")
    GraphicsSettings.set_instance(GraphicsSettings.in_memory())
    Thick.set_level(Thick.DETAIL_FINE)
    check(all(_lit(MapArt.Pulses(maps.create(i)), times) == 0 for i in range(maps.MAP_COUNT)), "crowded fights: no ambience")
    Thick.set_level(0)


def test_data_pulses_never_run_along_the_track(check):
    for i in range(maps.MAP_COUNT):
        m = maps.create(i)
        a = MapArt.ambience_for(m)
        if not a.lanes:
            continue
        lanes = MapArt.Ambience(m)
        lanes.lanes = a.lanes
        acc = skia.Surface.MakeRasterN32Premul(1200, 900)
        acc.getCanvas().clear(0)
        g = Graphics2D(acc.getCanvas())
        for k in range(160):
            lanes.paint(g, k * 0.25)
        mask = BufferedImage(1200, 900, BufferedImage.TYPE_INT_RGB)
        mg = mask.create_graphics()
        MapArt.Painter(m, mg, None, None, None).fill(MapArt.Painter(m, None, None, None, None).track_area(MapArt.HW - 3),
                                                     MapArt.c(0xffffff))
        mg.dispose()
        on_track = _pixels(mask)[:, :, 0] > 0
        lit = acc.makeImageSnapshot().toarray()[:, :, 3] > 0
        check(lit.any(), "%s: data pulses are painted" % m.get_name())
        check(not (lit & on_track).any(), "%s: no data pulse is ever drawn on the track (%d px)" % (m.get_name(), int((lit & on_track).sum())))


# ---------------------------------------------------------------------------------------------------- the set dressing
def _render(m, details, s=1.0):
    img = BufferedImage(int(1200 * s), int(900 * s), BufferedImage.TYPE_INT_RGB)
    g = img.create_graphics()
    g.scale(s, s)
    MapArt.render(g, m, False, details)
    g.dispose()
    return _pixels(img)[:, :, :3].astype(int)


def _track_distance(m, s=1.0):
    """Distance (world px) from every pixel centre to the nearest route centre line."""
    h, w = int(900 * s), int(1200 * s)
    Y, X = np.mgrid[0:h, 0:w].astype(float)
    X, Y = (X + 0.5) / s, (Y + 0.5) / s
    d = np.full(X.shape, 1e9)
    for r in m.get_routes():
        wp = r.get_waypoints()
        for a, b in zip(wp, wp[1:]):
            dx, dy = b.x - a.x, b.y - a.y
            l2 = dx * dx + dy * dy
            t = np.clip(((X - a.x) * dx + (Y - a.y) * dy) / l2, 0, 1) if l2 > 0 else 0
            np.minimum(d, np.hypot(X - (a.x + t * dx), Y - (a.y + t * dy)), out=d)
    return d


def _lum_array(px):
    c = px / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


_DRESSING = {}


def _dressing(i):
    """(map, picture with details, ground set-dressing mask, track distance): the ground mask is every pixel the
details change outside the obstacles (details painted on a prop belong to the prop)."""
    if i not in _DRESSING:
        m = maps.create(i)
        on, off = _render(m, True), _render(m, False)
        diff = abs(on - off).sum(axis=2) > 12
        props = np.zeros(diff.shape, bool)
        for o in m.get_obstacles():   # + the extruded facade below / right of a building
            props[max(0, int(o.y) - 3):int(o.y + o.h) + 12, max(0, int(o.x) - 3):int(o.x + o.w) + 9] = True
        _DRESSING[i] = (m, on, diff & ~props, _track_distance(m))
    return _DRESSING[i]


def test_every_map_has_set_dressing(check):
    for i in range(maps.MAP_COUNT):
        m, on, ground, d = _dressing(i)
        check(ground.sum() > 4000, "%s: the open ground is dressed (%d px of details)" % (m.get_name(), ground.sum()))
        lay = MapArt.layout_for(m)
        check(lay and any(len(v) if isinstance(v, (list, tuple)) else (v is not None) for v in lay.values()),
              "%s: the set dressing has its places" % m.get_name())


def test_set_dressing_stays_off_the_track_and_the_tower_strips(check):
    """Never on the track, and never in the strips beside it where towers usually stand: the ground details keep
STRIP px beyond the track edges (a couple of px of anti-aliasing aside)."""
    for i in range(maps.MAP_COUNT):
        m, on, ground, d = _dressing(i)
        near = float(d[ground].min()) if ground.any() else 1e9
        check(near >= MapArt.HW + MapArt.STRIP - 2.5, "%s: details keep out of the tower strips (closest %.1f px from the "
              "track centre, strip ends at %.0f)" % (m.get_name(), near, MapArt.HW + MapArt.STRIP))


def test_set_dressing_is_quieter_than_the_track(check):
    """Decoration is lower in brightness than what matters to play: almost all of it is under half the luminance of the
track's neon edges, and even its brightest points (LEDs, lamps) stay below them."""
    for i in range(maps.MAP_COUNT):
        m, on, ground, d = _dressing(i)
        lum = _lum_array(on)
        edge = np.sort(lum[(d > 21) & (d < 23.5)])
        edge = float(np.median(edge[-len(edge) // 3:]))
        deco = lum[ground]
        p99, p999 = float(np.percentile(deco, 99)), float(np.percentile(deco, 99.9))
        check(p99 <= 0.55 * edge, "%s: the details are quiet (p99 %.3f vs track edge %.3f)" % (m.get_name(), p99, edge))
        check(p999 <= 0.9 * edge, "%s: even the brightest details stay under the track edge (%.3f vs %.3f)"
              % (m.get_name(), p999, edge))


def test_thumbnails_keep_only_the_larger_details(check):
    """On thumbnail-sized bitmaps the finest details are left out, so the small pictures stay clean."""
    for i in range(maps.MAP_COUNT):
        m = maps.create(i)
        for s, fine in ((0.25, False), (1.0, True)):
            img = BufferedImage(int(1200 * s), int(900 * s), BufferedImage.TYPE_INT_RGB)
            g = img.create_graphics()
            g.scale(s, s)
            p = MapArt.render(g, m)
            g.dispose()
            check(p.fine == fine, "%s @%.2f: fine details %s" % (m.get_name(), s, "on" if fine else "off"))
        thumb = abs(_render(m, True, 0.25) - _render(m, False, 0.25)).sum(axis=2)
        check(thumb.mean() < 6, "%s: the thumbnail barely changes (mean %.2f)" % (m.get_name(), thumb.mean()))


def test_animated_details_stay_off_the_track(check):
    """Blinking LEDs, flickering signs and screens, glitches, spinning fans and moving cars: never drawn on the track or
in the tower strips (unless on a prop), and every kind is used somewhere."""
    kinds = {"blinks": 0, "flickers": 0, "glitches": 0, "spins": 0, "movers": 0}
    for i in range(maps.MAP_COUNT):
        m = maps.create(i)
        a = MapArt.ambience_for(m)
        live = MapArt.Ambience(m)
        for k in kinds:
            setattr(live, k, getattr(a, k))
            kinds[k] += len(getattr(a, k))
        if live.count() == 0:
            continue
        acc = skia.Surface.MakeRasterN32Premul(1200, 900)
        acc.getCanvas().clear(0)
        g = Graphics2D(acc.getCanvas())
        for k in range(400):
            live.paint(g, k * 0.137)
        lit = acc.makeImageSnapshot().toarray()[:, :, 3] > 0
        props = np.zeros(lit.shape, bool)
        for o in m.get_obstacles():
            props[max(0, int(o.y) - 2):int(o.y + o.h) + 3, max(0, int(o.x) - 2):int(o.x + o.w) + 3] = True
        strip = _dressing(i)[3] < MapArt.HW + MapArt.STRIP - 3
        check(lit.any(), "%s: the animated details are painted" % m.get_name())
        bad = int((lit & strip & ~props).sum())
        check(bad == 0, "%s: no animated detail on the track or in its strips (%d px)" % (m.get_name(), bad))
    for k, n in kinds.items():
        check(n > 0, "the ambience uses %s (%d)" % (k, n))
