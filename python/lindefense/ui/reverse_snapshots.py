"""Lindefense ReverseSnapshots (ported from src/lindefense/ui/ReverseSnapshots.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.ai.reverse_match import AttackerBot
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai import units
from lindefense.ai.units import AttackUnit, Doctrine
from lindefense.sim.difficulty import Difficulty
from lindefense.sim.game import Game


class ReverseSnapshots:
    """Developer tool: paints the reverse-mode ("Adversarial Training") screens offscreen into PNGs for visual review,
without opening a window: the briefing switch and the attacker briefing with its doctrine cards, the in-match HUD and
spawn panel at several moments (driven by the scripted AttackerBot), a hovered unit card, a selected AI tower, the help
overlay, the pause menu, both end screens and a sudden-death overtime. .venv/bin/python -m lindefense.ui.reverse_snapshots <dir>."""
    def __init__(self):
        pass
    @staticmethod
    def snap(c, dir_, name):
        img = BufferedImage(Ui.W, Ui.H, BufferedImage.TYPE_INT_ARGB)
        g = img.create_graphics()
        Cyber.quality(g)
        c.paint(g)
        g.dispose()
        ImageIO.write(img, 'png', _j.File(dir_, _j.cat(name, '.png')))
        print(_j.s(_j.cat('wrote ', _j.File(dir_, _j.cat(name, '.png')).get_path())))
    @staticmethod
    def play(g, s, bot, seconds):
        """Runs the match headlessly with the bot for seconds, then a few rendered frames so the views catch up."""
        n = _j.to_int((seconds / Game.DT))
        i = 0
        while (i < n) and (g.get_state() is Game.State.PLAYING):
            bot.tick(Game.DT)
            g.step(Game.DT)
            if _j.imod(i, 30) == 0:
                s.frame(0)
            g.get_events().clear()
            i += 1
        for i in range(20):
            bot.tick(Game.DT)
            s.frame(Game.DT)
    @staticmethod
    def main(args):
        _j.set_property('lindefense.nosound', 'true')
        dir_ = _j.File((args[0] if (len(args) > 0) else 'snapshots-reverse'))
        dir_.mkdirs()
        Difficulty.set_selected(Difficulty.ON)
        ms = MapSelectScreen(None)
        ms.frame(0.02)
        ms.open_briefing(4)
        ms.frame(0.05)
        ReverseSnapshots.snap(ms, dir_, 'r01_briefing_with_attack_switch')
        units.select_doctrine(Doctrine.RUSH)
        ms.open_reverse_briefing(4)
        ms.frame(0.05)
        ReverseSnapshots.snap(ms, dir_, 'r02_reverse_briefing')
        ms.open_reverse_briefing(1)
        ms.doctrine_picker.pick(Doctrine.HEIST)
        b = ms.doctrine_picker.buttons()[2]
        ms.mouse_moved(b.get_x() + 40, b.get_y() + 40)
        ms.frame(0.05)
        ReverseSnapshots.snap(ms, dir_, 'r02b_reverse_briefing_heist_long_track')
        units.select_doctrine(Doctrine.RUSH)
        g = ReverseMatch.create(0, 11, Difficulty.ON2, Doctrine.SWARM)
        r = g.get_reverse()
        s = GameScreen(None, g)
        s.frame(0.02)
        ReverseSnapshots.snap(s, dir_, 'r03_match_start')
        bot = AttackerBot(r, AttackerBot.Style.REASONABLE)
        ReverseSnapshots.play(g, s, bot, 30)
        ReverseSnapshots.snap(s, dir_, 'r03b_match_0m30')
        ReverseSnapshots.play(g, s, bot, 45)
        r.send(AttackUnit.DYNAMIC, None, 6, (-1))
        ReverseSnapshots.play(g, s, bot, 10)
        ReverseSnapshots.snap(s, dir_, 'r04_match_1m25')
        ReverseSnapshots.play(g, s, bot, 80)
        card = AttackPanel.card_center(AttackUnit.MOAB.ordinal)
        s.mouse_moved(card[0], card[1])
        s.frame(Game.DT)
        s.frame(Game.DT)
        ReverseSnapshots.snap(s, dir_, 'r05_hover_unit_card')
        s.mouse_moved(600, 500)
        ReverseSnapshots.play(g, s, bot, 60)
        ReverseSnapshots.snap(s, dir_, 'r06_match_mid')
        best = None
        for t in g.get_tower_manager().get_player_towers():
            if (best is None) or (t.get_invested_cost() > best.get_invested_cost()):
                best = t
        if best is not None:
            s.select_tower(best)
            s.frame(Game.DT)
            s.frame(Game.DT)
            ReverseSnapshots.snap(s, dir_, 'r07_ai_tower_selected')
            s.select_tower(None)
        s.toggle_help()
        s.frame(Game.DT)
        ReverseSnapshots.snap(s, dir_, 'r08_help')
        s.toggle_help()
        s.open_menu()
        s.frame(Game.DT)
        ReverseSnapshots.snap(s, dir_, 'r09_pause_menu')
        s.escape_pressed()
        s.frame(Game.DT)
        ReverseSnapshots.play(g, s, bot, ReverseMatch.DURATION)
        i = 0
        while (i < 200) and (g.get_state() is Game.State.PLAYING):
            bot.tick(Game.DT)
            s.frame(Game.DT)
            i += 1
        ReverseSnapshots.snap(s, dir_, ('r10_end_breach' if (g.get_state() is Game.State.DEFEAT) else 'r10_end_contained'))
        h = ReverseMatch.create(5, 12, Difficulty.ONN)
        hs = GameScreen(None, h)
        ReverseSnapshots.play(h, hs, AttackerBot(h.get_reverse(), AttackerBot.Style.PASSIVE), (ReverseMatch.DURATION + 5))
        for i in range(10):
            hs.frame(Game.DT)
        ReverseSnapshots.snap(hs, dir_, ('r11_end_contained' if (h.get_state() is Game.State.VICTORY) else 'r11_end_other'))
        w = ReverseMatch.create(2, 13, Difficulty.O1, Doctrine.HEIST)
        ws = GameScreen(None, w)
        ReverseSnapshots.play(w, ws, AttackerBot(w.get_reverse(), AttackerBot.Style.REASONABLE), ReverseMatch.DURATION)
        i = 0
        while (i < 200) and (w.get_state() is Game.State.PLAYING):
            ws.frame(Game.DT)
            i += 1
        for i in range(10):
            ws.frame(Game.DT)
        ReverseSnapshots.snap(ws, dir_, ('r12_end_breach' if (w.get_state() is Game.State.DEFEAT) else 'r12_end_other'))
        # sudden-death overtime: an O(N^2) match where the attacker got the AI under the overtime line
        o = ReverseMatch.create(3, 77, Difficulty.ON2, Doctrine.HEIST)
        os_ = GameScreen(None, o)
        ob = AttackerBot(o.get_reverse(), AttackerBot.Style.REASONABLE)
        ReverseSnapshots.play(o, os_, ob, ReverseMatch.DURATION + 12)
        ReverseSnapshots.snap(os_, dir_, ('r13_overtime' if o.get_reverse().is_overtime() else 'r13_no_overtime'))


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.attack_panel import AttackPanel  # noqa: E402
from lindefense.ui.cyber import Cyber  # noqa: E402
from lindefense.ui.game_screen import GameScreen  # noqa: E402
from lindefense.ui.map_select_screen import MapSelectScreen  # noqa: E402
from lindefense.ui.ui import Ui  # noqa: E402


if __name__ == "__main__":
    import sys
    ReverseSnapshots.main(sys.argv[1:])
