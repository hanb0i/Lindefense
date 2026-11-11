"""Lindefense GlowLayer (ported from src/lindefense/ui/GlowLayer.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.map.game_map import GameMap


class GlowLayer(GObject):
    """HIGH-quality cosmetic layer (see GraphicsSettings.Quality#glow): a short, small and faint light flash on
explosions and big abilities (the minimal style keeps global glow to that; projectiles carry no halos). Drawn in world
coordinates by WorldView, under the projectile sprites.

It stays cheap by stamping one small pre-rendered radial-gradient sprite per colour (cached) instead of painting
gradients every frame, and by switching off as soon as big fights lower the level of detail."""
    class Flash:
        """One explosion / ability flash."""
        def __init__(self, x, y, radius, life, rgb):
            self.x = 0.0
            self.y = 0.0
            self.radius = 0.0
            self.life = 0.0
            self.rgb = 0
            self.age = 0.0
            self.x = x
            self.y = y
            self.radius = radius
            self.life = life
            self.rgb = rgb
    def __init__(self, game):
        self.game = None
        self.lod = 0
        GObject.__init__(self)
        self.flashes = _j.ArrayList()
        self.at = AffineTransform()
        self.game = game
    def set_lod(self, lod):
        """Level of detail from the world view: flashes up to level 1."""
        self.lod = lod
    def flash(self, at, radius, rgb):
        """Adds a light flash of the given world radius and colour (explosions, abilities); none with REDUCED MOTION on."""
        if (((at is None) or (not GraphicsSettings.get().quality().glow)) or (self.lod >= 2)) or (len(self.flashes) >= 40) or display_settings.reduced_motion():
            return
        _j_add(self.flashes, GlowLayer.Flash(at.x, at.y, _j.dmin(160, _j.dmax(18, (radius * GlowLayer.FLASH_SCALE))), 0.22, rgb))
    def update(self, dt):
        """Ages the flashes."""
        for i in range((len(self.flashes) - 1), -1, -1):
            f = self.flashes[i]
            f.age += dt
            if f.age >= f.life:
                self.flashes.pop(i)
    def flash_count(self):
        """Live flashes (tests)."""
        return len(self.flashes)
    def get_bounds(self):
        return GRectangle(0, 0, GameMap.WIDTH, GameMap.HEIGHT)
    def paint(self, g):
        if not GraphicsSettings.get().quality().glow:
            return
        g2 = g.create()
        try:
            for f in self.flashes:
                k = (1 - (f.age / f.life))
                self.stamp(g2, f.x, f.y, (f.radius * (0.7 + (0.3 * (1 - k)))), f.rgb, ((GlowLayer.FLASH_ALPHA * k) * k))
        finally:
            g2.dispose()
    def stamp(self, g2, x, y, r, rgb, alpha):
        if alpha <= 0.01:
            return
        g2.set_composite(AlphaComposite.SrcOver.derive(_j.dmin(1.0, alpha)))
        self.at.set_to_translation((x - r), (y - r))
        self.at.scale(((2 * r) / GlowLayer.SPRITE), ((2 * r) / GlowLayer.SPRITE))
        g2.draw_image(GlowLayer.sprite(rgb), self.at, None)
    @staticmethod
    def sprite(rgb):
        """The cached radial glow sprite for a colour: bright core fading to transparent."""
        key = (rgb & 0xffffff)
        b = GlowLayer.SPRITES.get(key)
        if b is not None:
            return b
        b = BufferedImage(GlowLayer.SPRITE, GlowLayer.SPRITE, BufferedImage.TYPE_INT_ARGB)
        g = b.create_graphics()
        try:
            c = Color(key)
            core = Color(min(255, (c.get_red() + 70)), min(255, (c.get_green() + 70)), min(255, (c.get_blue() + 70)), 200)
            g.set_paint(RadialGradientPaint((GlowLayer.SPRITE / 2.0), (GlowLayer.SPRITE / 2.0), (GlowLayer.SPRITE / 2.0), [0.0, 0.35, 1.0], [core, Color(c.get_red(), c.get_green(), c.get_blue(), 90), Color(c.get_red(), c.get_green(), c.get_blue(), 0)]))
            g.fill_rect(0, 0, GlowLayer.SPRITE, GlowLayer.SPRITE)
        finally:
            g.dispose()
        _j_put(GlowLayer.SPRITES, key, b)
        return b


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.graphics_settings import GraphicsSettings  # noqa: E402

GlowLayer.serial_version_uid = 1
GlowLayer.SPRITE = 64
GlowLayer.FLASH_SCALE = 0.9
GlowLayer.FLASH_ALPHA = 0.32
GlowLayer.SPRITES = _j.HashMap()
