"""Lindefense TutorialGuide (ported from src/lindefense/ui/TutorialGuide.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ui.ui import Ui


class TutorialGuide(GCompound):
    """The on-screen card of the guided tutorial: step counter, title, instructions and NEXT / SKIP / END buttons, drawn
in the top-left corner of the playfield. The steps and their completion rules live in TutorialScript."""
    def __init__(self, script):
        self.script = None
        self.shown_finished = False
        self.pulse = 0.0
        GCompound.__init__(self)
        self.buttons = _j.ArrayList()
        self.shown_index = (-1)
        self.h = 170.0
        self.script = script
        self.rebuild()
    def get_script(self):
        return self.script
    def get_buttons(self):
        return _j.ArrayList() if self.script.is_finished() else self.buttons
    def covers(self, lx, ly):
        """True if the point is on the card (clicks there never reach the map)."""
        return ((((not self.script.is_finished()) and (lx >= TutorialGuide.X)) and (lx <= (TutorialGuide.X + TutorialGuide.W))) and (ly >= TutorialGuide.Y)) and (ly <= (TutorialGuide.Y + self.h))
    def update(self, dt):
        self.pulse += dt
        self.script.update()
        if (self.script.index() != self.shown_index) or (self.script.is_finished() != self.shown_finished):
            self.rebuild()
        for b in self.buttons:
            b.animate(dt)
    def rebuild(self):
        self.remove_all()
        self.buttons.clear()
        self.shown_index = self.script.index()
        self.shown_finished = self.script.is_finished()
        if self.script.is_finished():
            self.set_visible(False)
            return
        self.set_visible(True)
        s = self.script.current()
        tf = Cyber.body(Font.PLAIN, 14)
        lines = Ui.wrap(s.text, tf, (TutorialGuide.W - 32))
        self.h = ((92 + (len(lines) * 19)) + 46)
        self.add(Cyber.Chamfer(TutorialGuide.X, TutorialGuide.Y, TutorialGuide.W, self.h, 14).fill(Color(6, 10, 24, 238)).border(Cyber.YELLOW).glow(0.9).line_width(1.8))
        self.add(Ui.rect((TutorialGuide.X + 18), (TutorialGuide.Y + 8), 110, 3, Cyber.MAGENTA, Cyber.MAGENTA))
        self.add(Ui.label(Cyber.spaced(_j.cat('tutorial  ', (self.script.index() + 1), ' / ', self.script.count())), (TutorialGuide.X + 18), (TutorialGuide.Y + 30), Cyber.mono(Font.BOLD, 11), Cyber.YELLOW))
        if s.action:
            goal = Ui.label('GOAL', 0, (TutorialGuide.Y + 30), Cyber.mono(Font.BOLD, 11), Cyber.GREEN)
            goal.set_location((((TutorialGuide.X + TutorialGuide.W) - 18) - goal.get_width()), (TutorialGuide.Y + 30))
            self.add(goal)
        self.add(Ui.label(s.title, (TutorialGuide.X + 18), (TutorialGuide.Y + 62), Cyber.display(Font.BOLD, 24), Cyber.TEXT))
        ly = (TutorialGuide.Y + 70)
        for l in lines:
            ly += 19
            self.add(Ui.label(l, (TutorialGuide.X + 18), ly, tf, Cyber.MUTED))
        by = ((TutorialGuide.Y + self.h) - 44)
        last = (self.script.index() == (self.script.count() - 1))
        main = UIButton((TutorialGuide.X + 18), by, 150, 32, ('FINISH' if last else ('SKIP STEP' if s.action else 'NEXT')), Cyber.display(Font.BOLD, 15), _j.Fn(self.script.next))
        if not s.action:
            main.set_primary(True)
        else:
            main.set_accent(Cyber.MUTED)
        self.add(main)
        _j_add(self.buttons, main)
        if not last:
            end = UIButton((((TutorialGuide.X + TutorialGuide.W) - 18) - 150), by, 150, 32, 'END TUTORIAL', Cyber.display(Font.BOLD, 15), _j.Fn(self.script.skip_all))
            end.set_accent(Cyber.RED)
            self.add(end)
            _j_add(self.buttons, end)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.ui_button import UIButton  # noqa: E402

TutorialGuide.serial_version_uid = 1
TutorialGuide.X = 12.0
TutorialGuide.Y = (Ui.WORLD_Y + 10)
TutorialGuide.W = 480.0
