"""The minimal battlefield style: quiet map art whose only text is functional labels and diegetic neon signs / markings
(no floating HUD captions), a world view that never paints
the purely decorative sprite parts, flat overlays (HP bars, range rings, nameplates, IN / OUT markers), fewer
particles and smaller flashes, no projectile glow; COLOUR-BLIND SAFE and REDUCED MOTION keep working.
Everything is painted offscreen; nothing opens a window."""
import skia

from kit import buildable_near, force_place, new_game, spawn_at
from lindefense.enemy.types import EnemyType
from lindefense.map import maps
from lindefense.sim.vec import Vec
from lindefense.tower.tower_type import TowerType as T
from lindefense.ui.cyber import Cyber
from lindefense.ui.display_settings import DisplaySettings
from lindefense.ui.game_screen import GameScreen
from lindefense.ui.glow_layer import GlowLayer
from lindefense.ui.jawt import BufferedImage, Color, Graphics2D, Point2D, reset_canvas_state
from lindefense.ui.map_art import MapArt
from lindefense.ui.sprites.effect import Effect
from lindefense.ui.sprites.thick import Thick
from lindefense.ui.sprites.towers.art import Art
from lindefense.ui.sprites.towers.flat import Flat
from lindefense.ui.sprites.towers.tower_art_factory import TowerArtFactory
from lindefense.ui.sprites.towers.tower_icons import TowerIcons
from lindefense.ui.world_view import WorldView


def _settings(**on):
    s = DisplaySettings.in_memory()
    for k, v in on.items():
        setattr(s, k, v)
    DisplaySettings.set_instance(s)


def _paint(c, w=1600, h=1000):
    surf = skia.Surface.MakeRasterN32Premul(w, h)
    cv = surf.getCanvas()
    reset_canvas_state(cv)
    c.paint(Graphics2D(cv))
    reset_canvas_state(cv)


def _map_strings(idx, monkeypatch, scale=1.0):
    """The strings the map art draws, with their world positions, and the painter (its marks are the diegetic text)."""
    drawn = []
    orig = Graphics2D.draw_string

    def spy(self, s, x, y):
        q = self.get_transform().transform(Point2D.Double(x, y), None)
        drawn.append((s, q.get_x() / scale, q.get_y() / scale))
        return orig(self, s, x, y)
    monkeypatch.setattr(Graphics2D, "draw_string", spy)
    img = BufferedImage(int(1200 * scale), int(900 * scale), BufferedImage.TYPE_INT_RGB)
    g = img.create_graphics()
    g.scale(scale, scale)
    p = MapArt.render(g, maps.create(idx))
    g.dispose()
    monkeypatch.setattr(Graphics2D, "draw_string", orig)
    return drawn, p


def test_map_art_draws_functional_labels_and_diegetic_signs_only(check, monkeypatch):
    """Text on a map is either a functional label the player needs, or diegetic: a neon sign on a building, a marking
printed on a prop, a display. Never a floating HUD-style caption (a frame title, a region name, a "// " tag), and
diegetic text never sits on the track or in the tower strips beside it unless it is on a prop."""
    hud = ("NULL REGION", "VOID", "LX-MAINBOARD", "PCB", "NEURAL FIELD", "LAYER 12", "EVENT HORIZON", "PORTAL",
           "ATTENTION HUB", "INNOVATION DISTRICT", "CAMPUS", "SERVER GRAVEYARD", "SECTOR", "INSIDE THE MACHINE",
           "FORWARD PASS", "GRAVITY WELL", "LEGACY CLUSTER", "AISLE", "INPUT", "OUTPUT", "//")
    for idx in range(maps.MAP_COUNT):
        m = maps.create(idx)
        allowed = set()
        if idx == 0:
            allowed = {r.get_name().upper() for r in m.get_routes()} | {"CAPACITOR PAD"}
        elif idx == 1:
            allowed = {"FLOOR %d" % (i + 1) for i in range(len(m.get_floors()))}
        elif idx == 6:
            allowed = {h.kind.upper() for h in m.get_hazards()} | {"!"}
        drawn, p = _map_strings(idx, monkeypatch)
        strings = {s for s, _, _ in drawn}
        extra = sorted(strings - allowed - set(p.marks))
        check(not extra, "%s: every string is a functional label or diegetic (extra: %s)" % (m.get_name(), extra))
        check(not any(any(f in s for f in hud) for s in strings), "%s: no HUD-style captions" % m.get_name())
        check(allowed <= strings, "%s: the functional labels are still there (%s)" % (m.get_name(), sorted(allowed - strings)))
        loose = []
        for s, x, y in drawn:
            if s in allowed:
                continue
            on_prop = any(o.contains(Vec(x, y), 4) for o in m.get_obstacles())
            if not on_prop and MapArt.track_distance(m, x, y) < MapArt.HW + MapArt.STRIP - 8:
                loose.append(s)
        check(not loose, "%s: diegetic text stays on props or open ground (%s)" % (m.get_name(), loose[:5]))
        if idx in (2, 3):
            check(not strings, "%s: no text at all in the void" % m.get_name())
    _, valley = _map_strings(4, monkeypatch)
    signs = set(valley.marks)
    check({"AGI SOON", "50% OFF", "GPU CLOUD", "HIRE AN AI", "SCALE IS", "ALL YOU NEED"} <= signs,
          "Silicon Valley keeps its witty billboards (%s)" % sorted(signs))
    check({"SERVER FARM", "AI RESEARCH LAB", "GLASS HQ"} <= signs, "and its buildings carry their names")
    _, board = _map_strings(0, monkeypatch)
    check({"CPU", "RAM", "I/O"} <= set(board.marks), "the chips carry their markings")


def test_world_never_paints_decorative_sprite_parts(check, monkeypatch):
    _settings()
    g = new_game(0)
    force_place(g, T.GPT, buildable_near(g, Vec(400, 300), 160), 3)
    s = GameScreen(None, g, False)
    s.frame(0.02)
    levels = []
    orig = Thick.set_level

    def spy(lod):
        levels.append(lod)
        return orig(lod)
    monkeypatch.setattr(Thick, "set_level", staticmethod(spy))
    _paint(s)
    monkeypatch.setattr(Thick, "set_level", staticmethod(orig))
    check(levels and levels[0] >= Thick.DETAIL_DECOR, "the world paints at the decorative level or above (%s)" % levels[:1])
    check(Thick.level() == 0, "and restores the level afterwards")
    check(s.world.get_lod() == 0 and s.world.effect_cap() == WorldView.MAX_EFFECTS,
          "a quiet board keeps the full effect budget (lod %d)" % s.world.get_lod())
    check(s.world.fx.lod >= 1 and s.world.fx.cap() == s.world.fx.MAX_DRAWN, "world fx: no decorations, full entity cap")


def test_tower_icons_match_the_minimal_board(check, monkeypatch):
    levels = []
    orig = Thick.set_level

    def spy(lod):
        levels.append(lod)
        return orig(lod)
    icon = TowerIcons.create(T.CLAUDE, 3, 56)
    monkeypatch.setattr(Thick, "set_level", staticmethod(spy))
    _paint(icon, 64, 64)
    monkeypatch.setattr(Thick, "set_level", staticmethod(orig))
    check(levels and levels[0] == Thick.DETAIL_DECOR and Thick.level() == 0, "icons paint without decorative parts (%s)" % levels)


def test_superclass_keeps_a_plain_gold_ring(check):
    art = TowerArtFactory.create(T.GPT, 4, 20)
    rings = [o for o in art._contents if isinstance(o, Flat.Poly) and o.detail == 0
             and (o.get_fill_color().get_rgb() & 0xffffff) == (Art.GOLD.get_rgb() & 0xffffff) and 0 < o.get_fill_color().get_alpha() < 255]
    check(len(rings) == 1, "tier 4 shows one always-drawn gold ring (%d)" % len(rings))
    lower = TowerArtFactory.create(T.GPT, 3, 20)
    check(not any(isinstance(o, Flat.Poly) and o.detail == 0 and (o.get_fill_color().get_rgb() & 0xffffff) == (Art.GOLD.get_rgb() & 0xffffff)
                  and 0 < o.get_fill_color().get_alpha() < 255 for o in lower._contents), "lower tiers do not")


def test_fewer_particles_and_smaller_flashes(check):
    _settings()
    e = Effect(0, 0, 1.0)
    e.shards(8, 0, 0, 4, 40, 10, Cyber.YELLOW, 0, 0, 0.5, 7)
    check(len(e.particles) == 4, "shards keep half the particles (%d)" % len(e.particles))
    e.shards(1, 0, 0, 4, 40, 10, Cyber.YELLOW, 0, 0, 0.5, 7)
    check(len(e.particles) == 5, "never fewer than one")
    e.ring(0, 0, 5, 50, Cyber.YELLOW, 0, 0.3, True)
    e.ring(0, 0, 5, 50, Cyber.YELLOW, 0, 0.3, False)
    check(e.rings[0].r1 < 50 and e.rings[1].r1 == 50, "flash discs are smaller, plain rings unchanged (%.1f)" % e.rings[0].r1)
    gl = GlowLayer(new_game(0))
    gl.flash(Vec(300, 300), 120, 0xff8800)
    check(gl.flash_count() == 1 and gl.flashes[0].radius < 120 * 1.4, "explosion light flashes are smaller")


def test_no_projectile_halos(check, monkeypatch):
    _settings()
    g = new_game(0)
    r = g.get_map().get_routes()[0]
    force_place(g, T.GPT, buildable_near(g, r.position_at(300).add(Vec(0, -70)), 120), 2)
    for k in range(6):
        spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 250 + 20 * k)
    s = GameScreen(None, g, False)
    n = 0
    while len(g.get_combat().get_projectiles()) == 0 and n < 300:
        s.frame(1 / 60.0)
        n += 1
    check(len(g.get_combat().get_projectiles()) > 0, "precondition: projectiles in flight")
    stamps = []
    monkeypatch.setattr(GlowLayer, "stamp", lambda self, *a: stamps.append(a))
    s.world.glow.flashes.clear()
    _paint(s)
    check(not stamps, "projectiles carry no glow halos (%d stamps)" % len(stamps))


def test_flat_overlays(check):
    _settings()
    g = new_game(0)
    t = force_place(g, T.GPT, buildable_near(g, Vec(400, 300), 160), 1)
    e = spawn_at(g, EnemyType.STATIC_ARRAY, None, 0, 200)
    e.take_damage(e.get_max_hp() * 0.5, 0)
    s = GameScreen(None, g, False)
    s.select_tower(t)
    s.frame(0.02)
    bar = s.world.hp_bars.get(e)
    check(bar is not None and bar.is_visible(), "a damaged enemy shows its HP bar")
    check(bar is not None and bar.outline is None and bar.h <= 4, "HP bars are flat: no border, slim")
    check(s.world.range_circle.is_visible() and s.world.range_circle.line_w <= 1.4, "the range ring is a thin line")
    check(not hasattr(s.world.select_plate.frame, "f_glow"), "nameplates have no glow (panels have no glow at all)")
    _paint(s)


def test_in_out_markers_follow_colour_blind_safe(check):
    for cb in (False, True):
        _settings(colour_blind=cb)
        s = GameScreen(None, new_game(0), False)
        fills = {o.fill.get_rgb() & 0xffffff for o in s.world.background._contents if isinstance(o, Cyber.Ring) and o.fill is not None}
        good = (Cyber.CB_GOOD if cb else Cyber.GREEN).get_rgb() & 0xffffff
        bad = (Cyber.CB_BAD if cb else Cyber.RED).get_rgb() & 0xffffff
        check(good in fills and bad in fills, "%s: IN / OUT markers use the %s palette" % ("colour-blind" if cb else "normal", "safe" if cb else "default"))
    _settings()
