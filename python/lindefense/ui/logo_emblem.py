"""Lindefense LogoEmblem (ported from src/lindefense/ui/LogoEmblem.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403


class LogoEmblem(GCompound):
    """The Lindefense emblem: a hexagonal circuit shield around an angular "L"
monogram with a yellow AI core. Built once from ACM primitives (static). Origin = centre."""
    def __init__(self, size):
        self.size = 0.0
        self.core = None
        self.iris = None
        self.monogram = None
        GCompound.__init__(self)
        self.size = size
        r = (size / 2)
        shell = LogoEmblem.hex(r)
        shell.set_filled(True)
        shell.set_fill_color(LogoEmblem.NAVY)
        shell.set_color(LogoEmblem.CYAN)
        self.add(shell)
        inner = LogoEmblem.hex((r * 0.78))
        inner.set_color(Ui.with_alpha(LogoEmblem.MAGENTA, 160))
        self.add(inner)
        for k in range(6):
            a = math.radians(((60 * k) + 30))
            x1 = ((math.cos(a) * r) * 0.78)
            y1 = ((math.sin(a) * r) * 0.78)
            x2 = ((math.cos(a) * r) * 0.97)
            y2 = ((math.sin(a) * r) * 0.97)
            l = GLine(x1, y1, x2, y2)
            l.set_color(Ui.with_alpha(LogoEmblem.CYAN, 190))
            self.add(l)
            pad = GOval((x1 - (r * 0.045)), (y1 - (r * 0.045)), (r * 0.09), (r * 0.09))
            pad.set_filled(True)
            pad.set_fill_color((LogoEmblem.CYAN if (_j.imod(k, 2) == 0) else LogoEmblem.MAGENTA))
            pad.set_color(LogoEmblem.NAVY)
            self.add(pad)
        traces = [[(-0.55), (-0.1), (-0.55), (-0.45), (-0.3), (-0.45)], [0.55, 0.1, 0.55, 0.45, 0.3, 0.45], [0.2, (-0.55), 0.45, (-0.55), 0.45, (-0.3)]]
        for t in traces:
            a = GLine((t[0] * r), (t[1] * r), (t[2] * r), (t[3] * r))
            b = GLine((t[2] * r), (t[3] * r), (t[4] * r), (t[5] * r))
            a.set_color(Ui.with_alpha(LogoEmblem.CYAN, 120))
            b.set_color(Ui.with_alpha(LogoEmblem.CYAN, 120))
            self.add(a)
            self.add(b)
            dot = GOval(((t[4] * r) - (r * 0.03)), ((t[5] * r) - (r * 0.03)), (r * 0.06), (r * 0.06))
            dot.set_filled(True)
            dot.set_fill_color(Ui.with_alpha(LogoEmblem.CYAN, 170))
            dot.set_color(Ui.with_alpha(LogoEmblem.CYAN, 170))
            self.add(dot)
        self.monogram = GPolygon()
        u = (r * 0.085)
        pts = [[(-4), (-6)], [(-1.4), (-6)], [(-1.4), 3.2], [4.5, 3.2], [4.5, 5.8], [3.6, 6.6], [(-4), 6.6]]
        for p in pts:
            self.monogram.add_vertex(((p[0] + ((6.6 - p[1]) * 0.14)) * u), (p[1] * u))
        self.monogram.set_filled(True)
        self.monogram.set_fill_color(LogoEmblem.MAGENTA)
        self.monogram.set_color(Ui.with_alpha(Color.WHITE, 200))
        self.add(self.monogram)
        self.core = GOval((r * 0.16), ((-r) * 0.34), (r * 0.28), (r * 0.28))
        self.core.set_filled(True)
        self.core.set_fill_color(LogoEmblem.YELLOW)
        self.core.set_color(Color.WHITE)
        self.add(self.core)
        self.iris = GOval((r * 0.25), ((-r) * 0.25), (r * 0.10), (r * 0.10))
        self.iris.set_filled(True)
        self.iris.set_fill_color(LogoEmblem.NAVY)
        self.iris.set_color(LogoEmblem.NAVY)
        self.add(self.iris)
    @staticmethod
    def hex(r):
        p = GPolygon()
        for k in range(6):
            a = math.radians((60 * k))
            p.add_vertex((math.cos(a) * r), (math.sin(a) * r))
        return p
    def get_emblem_size(self):
        return self.size


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ui import Ui  # noqa: E402

LogoEmblem.serial_version_uid = 1
LogoEmblem.CYAN = Color(0x00f0ff)
LogoEmblem.MAGENTA = Color(0xff2bd6)
LogoEmblem.YELLOW = Color(0xf5ff3b)
LogoEmblem.NAVY = Color(0x070a16)
