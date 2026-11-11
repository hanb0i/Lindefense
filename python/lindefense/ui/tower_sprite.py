"""Lindefense TowerSprite (ported from src/lindefense/ui/TowerSprite.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class TowerSprite(GCompound):
    """Visual model of a placed tower. The cartoon body is delegated to a
TowerArt from lindefense.ui.sprites.towers (one class per
tower type, four game tiers mapped to art stages 0, 2, 3, 4) and is rebuilt only when the tier changes.
This class owns the functional overlays: turret aiming at the last target,
firing recoil and muzzle flash, the radial ability cooldown ring (with a ready pulse),
the Palantir surveillance ring with its TARGETED / SURVEILLED label, the hero
badge and the three tier pips (no always-on name label; WorldView draws a
hover / selection nameplate). Between rebuilds only object state is mutated."""
    def __init__(self, t):
        self.tower = None
        self.art = None
        self.cd_ring = None
        self.surveil_ring = None
        self.mark = None
        self.pulse = 0.0
        self.clock = 0.0
        GCompound.__init__(self)
        self.built_tier = (-1)
        self.aim_angle = TowerArt.IDLE_ANGLE
        self.tower = t
        self.set_location(t.get_position().x, t.get_position().y)
        self.rebuild()
    def get_tower(self):
        """The tower this sprite draws."""
        return self.tower
    def rebuild(self):
        self.remove_all()
        self.built_tier = self.clamp_tier(self.tower.get_tier())
        type_ = self.tower.get_type()
        r = self.tower.get_radius()
        temp = self.tower.is_temporary()
        self.art = TowerArtFactory.create(type_, TowerArtFactory.art_stage(type_, self.built_tier), r)
        self.art.aim(self.aim_angle)
        self.add(self.art)
        pips = self.tower.get_max_tier()
        if (not temp) and (pips > 0):
            pw = (r * (0.32 if (pips > 3) else 0.4))
            ph = (r * 0.18)
            gap = (r * 0.12)
            x0 = ((-((pips * pw) + ((pips - 1) * gap))) / 2)
            for i in range(pips):
                fill = ((Art.GOLD if (self.built_tier >= pips) else Ui.GREEN) if (i < self.built_tier) else TowerSprite.PIP_OFF)
                self.add(Ui.rect((x0 + (i * (pw + gap))), (r * 1.22), pw, ph, fill, Art.INK))
        if type_.is_hero():
            star = GPolygon()
            for i in range(10):
                ang = (((-math.pi) / 2) + ((i * math.pi) / 5))
                rad = ((r * 0.38) if (_j.imod(i, 2) == 0) else (r * 0.16))
                star.add_vertex(((r * 1.0) + (math.cos(ang) * rad)), (((-r) * 1.0) + (math.sin(ang) * rad)))
            star.set_filled(True)
            star.set_fill_color(Art.GOLD)
            star.set_color(Art.GOLD_DARK)
            self.add(star)
        self.cd_ring = RadialCooldown((r * 1.32), 3)
        self.cd_ring.set_visible(False)
        self.add(self.cd_ring)
        self.surveil_ring = Ui.oval(((-r) * 1.7), ((-r) * 1.7), (r * 3.4), (r * 3.4), Ui.c(0xff2020, 50), Ui.c(0xff4040))
        self.surveil_ring.set_visible(False)
        self.add(self.surveil_ring)
        self.mark = Ui.label('!', (-4), ((-r) * 1.8), Ui.F_H2, Ui.RED)
        self.mark.set_visible(False)
        self.add(self.mark)
    def clamp_tier(self, t):
        return max(0, min(self.tower.get_max_tier(), t))
    @staticmethod
    def show(o, visible):
        """Sets visibility only when it changes (every ACM setter walks up to the canvas to request a repaint)."""
        if o.is_visible() != visible:
            o.set_visible(visible)
    def sync(self, game, dt, telegraphed):
        """Per-frame update.

@param game        the simulation (may be null in galleries; an internal clock is used)
@param dt          seconds since the previous frame
@param telegraphed whether Palantir is about to target this tower"""
        if self.clamp_tier(self.tower.get_tier()) != self.built_tier:
            self.rebuild()
        self.pulse += dt
        self.clock += dt
        now = (game.get_time() if (game is not None) else self.clock)
        r = self.tower.get_radius()
        target = self.tower.get_last_target()
        since_fire = (now - self.tower.get_last_fire_time())
        if (((target is not None) and target.is_alive()) and (since_fire < 1.5)) and self.art.has_turret():
            d = target.get_position().sub(self.tower.get_position())
            if d.length() > 0.5:
                want = math.atan2(d.y, d.x)
                delta = (want - self.aim_angle)
                while delta > math.pi:
                    delta -= (2 * math.pi)
                while delta < (-math.pi):
                    delta += (2 * math.pi)
                max_step = (TowerSprite.SLEW_RATE * _j.dmax(dt, 1e-3))
                if abs(delta) > max_step:
                    delta = (_j.signum(delta) * max_step)
                self.aim_angle += delta
                while self.aim_angle > math.pi:
                    self.aim_angle -= (2 * math.pi)
                while self.aim_angle < (-math.pi):
                    self.aim_angle += (2 * math.pi)
                self.art.aim(self.aim_angle)
        self.art.set_firing(since_fire)
        self.art.animate(now, dt)
        has = ((self.tower.get_ability() is not None) and (not self.tower.is_temporary()))
        TowerSprite.show(self.cd_ring, has)
        if has:
            self.cd_ring.set((1 - self.tower.get_ability_cooldown_fraction()), self.tower.is_ability_ready(), self.tower.is_surveilled(), Ui.c(self.tower.get_type().primary_rgb).brighter(), self.pulse)
        surveilled = self.tower.is_surveilled()
        TowerSprite.show(self.surveil_ring, (surveilled or telegraphed))
        if surveilled or telegraphed:
            cb = display_settings.colour_blind()   # COLOUR-BLIND SAFE: orange (surveilled) / violet (targeted)
            base = ((Cyber.CB_BAD if cb else TowerSprite.SURVEIL_RGB) if surveilled else (Cyber.CB_MARK if cb else TowerSprite.TARGET_RGB))
            alpha = (display_settings.calm((60 + (50 * math.sin((self.pulse * 8)))), 90) if surveilled else display_settings.calm((40 + (60 * abs(math.sin((self.pulse * 10))))), 80))
            self.surveil_ring.set_fill_color(Cyber.alpha(base, _j.to_int(alpha)))
            self.surveil_ring.set_color((base if cb else TowerSprite.SURVEIL_LINE))
            self.mark.set_color((base if cb else Ui.RED))
        show_mark = (telegraphed or surveilled)
        if self.mark.is_visible() != show_mark:
            self.mark.set_visible(show_mark)
        if show_mark:
            want = ('SURVEILLED' if surveilled else 'TARGETED')
            if not (want == self.mark.get_label()):
                self.mark.set_label(want)
            self.mark.set_location(((-self.mark.get_width()) / 2), ((-r) * 1.85))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui import display_settings  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.radial_cooldown import RadialCooldown  # noqa: E402
from lindefense.ui.sprites.towers.art import Art  # noqa: E402
from lindefense.ui.sprites.towers.tower_art import TowerArt  # noqa: E402
from lindefense.ui.sprites.towers.tower_art_factory import TowerArtFactory  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402

TowerSprite.serial_version_uid = 1
TowerSprite.SLEW_RATE = 9.0
TowerSprite.PIP_OFF = Color(0x2a3140)
TowerSprite.SURVEIL_RGB = Color(0xff2020)
TowerSprite.TARGET_RGB = Color(0xff8000)
TowerSprite.SURVEIL_LINE = Color(0xff4040)
TowerSprite._run_cache = True
