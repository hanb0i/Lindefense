"""Lindefense Logo (ported from src/lindefense/ui/sprites/Logo.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class Logo:
    """Simplified, primitive-built renditions of each boss organisation's mark.
Every logo is a GCompound centred on its own origin so the boss
sprite can orbit it on the hull while it stays upright and
unmirrored whichever way the ship faces. Logos are deliberately not
registered with the tint system, so they stay fully opaque on cloaked
hulls.

Sources checked: Bellarmine College Preparatory's colours are blue,
light blue and white and its mascot is "Bellarmine the Bell" (shield +
bell + "B" + wordmark banner here). Lockheed Martin uses a blue bold-italic
wordmark beside a fragmented star with two full points. 3Com's final mark
is the "3Com" wordmark with two swoosh arcs at the upper right. Palantir's
mark is a filled circle over two angled strokes (a seeing-stone on a
stand). No real logo exists for "SW Resource Consultant", so its SWRC badge
is invented."""
    def __init__(self):
        pass
    @staticmethod
    def text(g, s, size, italic, c, cx, cy):
        l = GLabel(s)
        l.set_font(Ui.display((Font.BOLD | (Font.ITALIC if italic else 0)), max(6, _j.to_int(_j.jround(size)))))
        l.set_color(c)
        l.set_location((cx - (l.get_width() / 2)), (cy + (l.get_ascent() * 0.36)))
        g.add(l)
        return l
    @staticmethod
    def panel(g, cx, cy, w, h, fill, line, lw):
        p = Art.rect((cx - (w / 2)), (cy - (h / 2)), w, h)
        p.set_filled(True)
        p.set_fill_color(fill)
        p.set_color(line)
        p.set_line_width(lw)
        g.add(p)
        return p
    @staticmethod
    def bellarmine(r):
        """Bellarmine College Prep: white heater shield with a blue border, a
light-blue bell and a bold blue "B", above a white "BELLARMINE" banner.
Overall about 1.8r wide and 1.15r tall."""
        g = GCompound()
        sh = (0.42 * r)
        shield = Art.poly([((-0.36) * r), (-sh), (0.36 * r), (-sh), (0.36 * r), (0.1 * r), 0, sh, ((-0.36) * r), (0.1 * r)])
        shield.set_filled(True)
        shield.set_fill_color(Color.WHITE)
        shield.set_color(Logo.BELL_BLUE)
        shield.set_line_width(_j.dmax(2, (r * 0.07)))
        g.add(shield)
        band = Art.rect(((-0.33) * r), ((-sh) + (0.02 * r)), (0.66 * r), (0.14 * r))
        band.set_filled(True)
        band.set_fill_color(Logo.BELL_BLUE)
        band.set_color(Logo.BELL_BLUE)
        band.set_line_width(0)
        g.add(band)
        bell = Art.poly([((-0.1) * r), (0.14 * r), ((-0.12) * r), (0.06 * r), ((-0.08) * r), ((-0.08) * r), ((-0.03) * r), ((-0.14) * r), (0.03 * r), ((-0.14) * r), (0.08 * r), ((-0.08) * r), (0.12 * r), (0.06 * r), (0.1 * r), (0.14 * r)])
        bell.set_filled(True)
        bell.set_fill_color(Logo.BELL_LIGHT)
        bell.set_color(Logo.BELL_BLUE)
        bell.set_line_width(_j.dmax(1.2, (r * 0.035)))
        bell.set_location((0.13 * r), (0.03 * r))
        g.add(bell)
        clapper = Art.oval_at((0.13 * r), (0.2 * r), (0.07 * r), (0.07 * r))
        clapper.set_filled(True)
        clapper.set_fill_color(Logo.BELL_BLUE)
        clapper.set_color(Logo.BELL_BLUE)
        clapper.set_line_width(0)
        g.add(clapper)
        Logo.text(g, 'B', (r * 0.42), False, Logo.BELL_BLUE, ((-0.14) * r), (0.06 * r))
        Logo.panel(g, 0, (0.62 * r), (1.8 * r), (0.3 * r), Color.WHITE, Logo.BELL_BLUE, _j.dmax(1.5, (r * 0.05)))
        Logo.text(g, 'BELLARMINE', (r * 0.25), False, Logo.BELL_BLUE, 0, (0.62 * r))
        return g
    @staticmethod
    def swrc(r):
        """SW Resource Consultant: invented SWRC monogram badge (orange disc, white ring and letters)."""
        g = GCompound()
        disc = Art.oval_at(0, 0, (0.95 * r), (0.95 * r))
        disc.set_filled(True)
        disc.set_fill_color(Art.SW_ACCENT)
        disc.set_color(Art.OUTLINE)
        disc.set_line_width(_j.dmax(2, (r * 0.06)))
        g.add(disc)
        ring = Art.oval_at(0, 0, (0.78 * r), (0.78 * r))
        ring.set_color(Color.WHITE)
        ring.set_line_width(_j.dmax(1.5, (r * 0.035)))
        g.add(ring)
        Logo.text(g, 'SWRC', (r * 0.26), False, Color.WHITE, 0, ((-0.04) * r))
        Logo.text(g, 'CONSULTING', (r * 0.11), False, Color.WHITE, 0, (0.2 * r))
        return g
    @staticmethod
    def three_com(r):
        """3Com: white rounded panel, blue "3Com" wordmark and the two swoosh arcs at the upper right."""
        g = GCompound()
        Logo.panel(g, 0, 0, (1.3 * r), (0.52 * r), Color.WHITE, Art.OUTLINE, _j.dmax(2, (r * 0.045)))
        Logo.text(g, '3Com', (r * 0.36), False, Logo.COM_BLUE, ((-0.08) * r), (0.02 * r))
        for i in range(2):
            sw = Art.arc(((0.22 * r) + ((i * 0.05) * r)), (((-0.26) * r) - ((i * 0.04) * r)), (0.5 * r), (0.36 * r), 20, 110)
            sw.set_color(Logo.COM_BLUE)
            sw.set_line_width(_j.dmax(1.5, (r * 0.035)))
            g.add(sw)
        return g
    @staticmethod
    def lockheed(r):
        """Lockheed Martin: white panel with the blue fragmented star (two full
points, two fading rays) beside a two-line bold-italic "LOCKHEED /
MARTIN" wordmark."""
        g = GCompound()
        Logo.panel(g, 0, 0, (1.8 * r), (0.7 * r), Color.WHITE, Art.OUTLINE, _j.dmax(2, (r * 0.05)))
        sx = ((-0.64) * r)
        sy = 0.0
        star = Art.poly([sx, (sy - (0.28 * r)), (sx + (0.06 * r)), (sy - (0.06 * r)), (sx + (0.34 * r)), sy, (sx + (0.06 * r)), (sy + (0.06 * r)), sx, (sy + (0.12 * r)), (sx - (0.05 * r)), (sy + (0.06 * r)), (sx - (0.14 * r)), sy, (sx - (0.05 * r)), (sy - (0.06 * r))])
        star.set_filled(True)
        star.set_fill_color(Logo.LM_BLUE)
        star.set_color(Logo.LM_BLUE)
        star.set_line_width(0)
        g.add(star)
        for i in range(2):
            ray = Art.line((sx - (0.06 * r)), ((sy + (0.07 * r)) + ((i * 0.06) * r)), (sx - (0.22 * r)), ((sy + (0.17 * r)) + ((i * 0.09) * r)))
            ray.set_color(Art.alpha(Logo.LM_BLUE, (150 - (i * 60))))
            ray.set_line_width(_j.dmax(1, (r * 0.03)))
            g.add(ray)
        Logo.text(g, 'LOCKHEED', (r * 0.27), True, Logo.LM_BLUE, (0.2 * r), ((-0.13) * r))
        Logo.text(g, 'MARTIN', (r * 0.27), True, Logo.LM_BLUE, (0.2 * r), (0.17 * r))
        return g
    @staticmethod
    def palantir(r):
        """Palantir: the seeing-stone mark (filled circle over two angled strokes) above a "PALANTIR" wordmark, in white."""
        g = GCompound()
        stone = Art.oval_at(0, ((-0.18) * r), (0.17 * r), (0.17 * r))
        stone.set_filled(True)
        stone.set_fill_color(Color.WHITE)
        stone.set_color(Color.WHITE)
        stone.set_line_width(0)
        g.add(stone)
        lw = _j.dmax(2, (r * 0.045))
        l1 = Art.line(((-0.02) * r), ((-0.08) * r), ((-0.14) * r), (0.06 * r))
        l2 = Art.line((0.02 * r), ((-0.08) * r), (0.14 * r), (0.06 * r))
        l1.set_color(Color.WHITE)
        l2.set_color(Color.WHITE)
        l1.set_line_width(lw)
        l2.set_line_width(lw)
        g.add(l1)
        g.add(l2)
        Logo.text(g, 'PALANTIR', (r * 0.17), False, Color.WHITE, 0, (0.2 * r))
        return g


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.art import Art  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402

Logo.BELL_BLUE = Color(20, 60, 160)
Logo.BELL_LIGHT = Color(120, 190, 250)
Logo.LM_BLUE = Color(0, 91, 173)
Logo.COM_BLUE = Color(0, 90, 175)
