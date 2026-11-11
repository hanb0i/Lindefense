"""In-world overlays for the corporate bosses' signature abilities (enemy/boss_abilities.py) and Palantir's Swarm
Uplink. Immediate mode like IntrusionFx, which calls it and lends it its stroke cache and drawing helpers: everything is
painted from the simulation state each frame, so nothing has to be created or removed when an ability starts or ends.

  CREST SHIELD (MOAB)   a pale-blue hex bubble whose rim fades with the shield's strength, a shield bar and a tag;
                        shards fly outward when it breaks.
  OUTSOURCING (BFB)     an orange charge arc that fills towards the next drop, and a burst ring when contractors land.
  NETWORK HUB (ZOMG)    the teal aura ring, link lines to every enemy it shields (each wears a small node ring) and
                        green repair sparks while it heals.
  AFTERBURNER (DDT)     a flame plume behind the jet and speed streaks while it burns, a flicker as it is about to.
  SWARM UPLINK (BAD)    pulsing tethers from each escort boss to Palantir and the damage cut it grants."""
import math

from lindefense.enemy.boss_abilities import Afterburner, CrestShield, NetworkHub, Outsourcing
from lindefense.ui import display_settings
from lindefense.ui import jrt as _j
from lindefense.ui.jawt import Color

SHIELD = Color(0x7fc8ff)
OUTSOURCE = Color(0xffb347)
HUB = Color(0x4fe0c8)
FLAME = Color(0xff7a3a)
FLAME_CORE = Color(0xffe08a)
UPLINK = Color(0xff5ab4)
MAX_LINKS = 24


def paint(fx, g, b):
    """Paints the overlay for one live corporate boss."""
    ab = b.get_ability()
    if isinstance(ab, CrestShield):
        _crest_shield(fx, g, b, ab)
    elif isinstance(ab, Outsourcing):
        _outsourcing(fx, g, b, ab)
    elif isinstance(ab, NetworkHub):
        _network_hub(fx, g, b, ab)
    elif isinstance(ab, Afterburner):
        _afterburner(fx, g, b, ab)


def _crest_shield(fx, g, b, ab):
    p = b.get_position()
    r = b.get_radius()
    age = ab.get_broken_age()
    if age < 0.7:
        k = age / 0.7
        for i in range(8):
            a = i * math.pi / 4 + 0.3
            d0 = r * (1.3 + 1.6 * k)
            fx.seg(g, p.x + math.cos(a) * d0, p.y + math.sin(a) * d0 * 0.8, p.x + math.cos(a) * (d0 + 9),
                   p.y + math.sin(a) * (d0 + 9) * 0.8, fx.col(SHIELD, 230 * (1 - k)), 3)
        fx.ring(g, p.x, p.y, r * (1.35 + k), fx.col(Color.WHITE, 160 * (1 - k)), 2)
    if not ab.is_up():
        return
    f = ab.get_shield_fraction()
    pulse = display_settings.calm(0.5 + 0.5 * math.sin(fx.time * 4 + b.get_id()), 0.5)   # reduced motion: steady
    R = r * 1.4
    fx.path.reset()
    spin = fx.time * 0.5
    for i in range(6):
        a = spin + i * math.pi / 3
        x = p.x + math.cos(a) * R
        y = p.y + math.sin(a) * R * 0.82
        if i == 0:
            fx.path.move_to(x, y)
        else:
            fx.path.line_to(x, y)
    fx.path.close_path()
    g.set_color(fx.col(SHIELD, 24 + 24 * pulse))
    g.fill(fx.path)
    g.set_stroke(fx.st(3.5))
    g.set_color(fx.col(fx.INK, 100))
    g.draw(fx.path)
    g.set_stroke(fx.st(1.8))
    g.set_color(fx.col(SHIELD, 120 + 135 * f))
    g.draw(fx.path)
    _bar(fx, g, p.x, p.y - R * 0.82 - 10, r * 1.6, f, SHIELD)
    fx.tag(g, p.x, p.y + R * 0.82 + 16, "CREST SHIELD " + str(int(round(100 * f))) + "%", SHIELD)


def _bar(fx, g, cx, y, w, f, c):
    fx.round.set_round_rect(cx - w / 2 - 1, y - 1, w + 2, 6, 4, 4)
    g.set_color(Color(6, 8, 18, 210))
    g.fill(fx.round)
    if f > 0:
        fx.round.set_round_rect(cx - w / 2, y, w * f, 4, 3, 3)
        g.set_color(c)
        g.fill(fx.round)


def _outsourcing(fx, g, b, ab):
    p = b.get_position()
    r = b.get_radius()
    since = ab.get_since()
    if since < 1.0:
        k = since
        fx.ring(g, p.x, p.y, r * (1.2 + 2.2 * k), fx.col(OUTSOURCE, 230 * (1 - k)), 4 - 3 * k)
        fx.oval(g, p.x, p.y, r * (1.2 + 2.2 * k), r * (1.2 + 2.2 * k), fx.col(OUTSOURCE, 36 * (1 - k)), None, 0)
        fx.tag(g, p.x, p.y - r * 1.35 - 6, "OUTSOURCED x" + str(Outsourcing.COUNT), OUTSOURCE)
    charge = 1.0 - ab.get_timer() / Outsourcing.INTERVAL
    R = r * 1.3
    fx.ring(g, p.x, p.y, R, fx.col(OUTSOURCE, 50), 2)
    if charge > 0:
        fx.arc.set_arc(p.x - R, p.y - R, R * 2, R * 2, 90, -360 * max(0.0, min(1.0, charge)), fx.ARC_OPEN)
        g.set_stroke(fx.st(3.2))
        g.set_color(fx.col(OUTSOURCE, 150 + 100 * charge))
        g.draw(fx.arc)
    if ab.get_timer() < 2.0:
        fx.tag(g, p.x, p.y + R + 16, "OUTSOURCING " + str(int(ab.get_timer() + 0.999)) + "s", OUTSOURCE)


def _network_hub(fx, g, b, ab):
    p = b.get_position()
    r = b.get_radius()
    R = NetworkHub.RADIUS
    pulse = display_settings.calm(0.5 + 0.5 * math.sin(fx.time * 2.5), 0.5)
    fx.oval(g, p.x, p.y, R, R, fx.col(HUB, 14 + 10 * pulse), None, 0)
    g.set_stroke(fx.dashed(2, 10, 7, fx.time * 18))
    g.set_color(fx.col(HUB, 130 + 60 * pulse))
    fx.ell.set_frame(p.x - R, p.y - R, R * 2, R * 2)
    g.draw(fx.ell)
    links = ab.get_linked()
    n = 0
    for e in links:
        if n >= MAX_LINKS:
            break
        if not e.is_alive():
            continue
        n += 1
        q = e.get_position()
        g.set_stroke(fx.dashed(1.4, 5, 5, -fx.time * 30) if fx.lod < 1 else fx.st(1.2))
        g.set_color(fx.col(HUB, 120))
        fx.line.set_line(p.x, p.y, q.x, q.y)
        g.draw(fx.line)
        fx.ring(g, q.x, q.y, e.get_radius() + 4, fx.col(HUB, 170), 1.6)
    if b.get_hp() < b.get_max_hp():
        for i in range(3):
            ph = _j.fmod(fx.time * 0.8 + i / 3.0, 1.0)
            mx = p.x + math.sin(i * 2.4 + fx.time) * r * 0.6
            my = p.y + r * 0.3 - ph * r * 1.5
            fx.plus(g, mx, my, 4, fx.col(Color(0x7dffb0), 220 * (1 - ph)))
    fx.tag(g, p.x, p.y - r - 12, "NETWORK HUB  " + str(len(links)) + " linked", HUB)


def _afterburner(fx, g, b, ab):
    p = b.get_position()
    r = b.get_radius()
    d = b.get_route().direction_at(b.get_distance())
    bx, by = -d.x, -d.y
    nx, ny = -d.y, d.x
    if ab.is_burning():
        flick = display_settings.calm(0.75 + 0.25 * math.sin(fx.time * 40 + b.get_id()), 1.0)   # no flicker
        L = r * 3.2 * flick
        for k, (c, w, a) in enumerate(((FLAME, 0.55, 150), (FLAME_CORE, 0.3, 230))):
            fx.path.reset()
            fx.path.move_to(p.x + bx * r * 0.6 + nx * r * w, p.y + by * r * 0.6 + ny * r * w)
            fx.path.line_to(p.x + bx * (r * 0.6 + L * (1 - 0.3 * k)), p.y + by * (r * 0.6 + L * (1 - 0.3 * k)))
            fx.path.line_to(p.x + bx * r * 0.6 - nx * r * w, p.y + by * r * 0.6 - ny * r * w)
            fx.path.close_path()
            g.set_color(fx.col(c, a))
            g.fill(fx.path)
        for i in range(-1, 2):
            o = i * r * 0.7
            ph = _j.fmod(fx.time * 3 + i * 0.37, 1.0)
            x0 = p.x + nx * o + bx * r * (1.0 + 2.5 * ph)
            y0 = p.y + ny * o + by * r * (1.0 + 2.5 * ph)
            fx.seg(g, x0, y0, x0 + bx * r * 1.2, y0 + by * r * 1.2, fx.col(Color.WHITE, 170 * (1 - ph)), 1.6)
        fx.tag(g, p.x, p.y - r - 10, "AFTERBURNER", FLAME)
    elif ab.get_timer() < 0.8:
        a = display_settings.calm(120 if _j.imod(_j.to_int(fx.time * 12), 2) == 0 else 40, 120)   # a steady warning
        fx.oval(g, p.x + bx * r * 0.9, p.y + by * r * 0.9, r * 0.35, r * 0.35, fx.col(FLAME, a), None, 0)


def paint_uplinks(fx, g, pal):
    """Palantir's Swarm Uplink: tethers to the escort bosses that shield it and the damage cut they grant."""
    pr = pal.get_protocols()
    ups = pr.get_uplinks()
    if not ups:
        return
    o = pal.get_position()
    for e in ups:
        if not e.is_alive():
            continue
        q = e.get_position()
        g.set_stroke(fx.st(3.5))
        g.set_color(fx.col(fx.INK, 100))
        fx.line.set_line(q.x, q.y, o.x, o.y)
        g.draw(fx.line)
        g.set_stroke(fx.dashed(1.8, 9, 6, -fx.time * 45))
        g.set_color(fx.col(UPLINK, 220))
        g.draw(fx.line)
        fx.ring(g, q.x, q.y, e.get_radius() + 6, fx.col(UPLINK, 190), 1.6)
    fx.tag(g, o.x, o.y + pal.get_radius() + 34, "SWARM UPLINK  -" + str(int(round(100 * pr.uplink_reduction()))) + "% damage", UPLINK)
