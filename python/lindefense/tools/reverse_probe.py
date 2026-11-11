"""Lindefense ReverseProbe (ported from src/lindefense/tools/ReverseProbe.java)."""
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
from lindefense.ai.units import DefenderProfile
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
import lindefense.ai.reverse_match as _m_reverse_match


class ReverseProbe:
    """Headless balance probe for reverse mode ("Adversarial Training"): scripted attackers (AttackerBot) against
the defender AI on every map and Difficulty Growth level, one line per match.

Usage: .venv/bin/python -m lindefense.tools.reverse_probe [style] [level] [map] with style
PASSIVE / SPAM / REASONABLE (default REASONABLE), level O1 / ON / ON2 / ONN or ALL (default ALL) and a map index or
-1 for every map (default -1); PROBE_SEEDS=K runs K seeds per combination from PROBE_SEED=N;
PROBE_PUSH=S / PROBE_BOSS=F change the reasonable bot's push size (seconds of income) and boss
share; PROBE_TRACE=true prints the economy every 30 s."""
    def __init__(self):
        pass
    @staticmethod
    def main(args):
        _j.set_property('lindefense.nosound', 'true')
        style = (AttackerBot.Style.value_of(args[0].upper()) if (len(args) > 0) else AttackerBot.Style.REASONABLE)
        only = (Difficulty.parse(args[1]) if ((len(args) > 1) and (not (args[1] is not None and args[1].lower() == 'ALL'.lower()))) else None)
        map_ = (int(args[2]) if (len(args) > 2) else (-1))
        seeds = _j.get_integer('probe.seeds', 1)
        seed0 = _j.get_long('probe.seed', 77)
        push = float(_j.get_property('probe.push', _j.s(_m_reverse_match.DEFAULT_PUSH_SECONDS)))
        boss = float(_j.get_property('probe.boss', _j.s(_m_reverse_match.DEFAULT_BOSS_SHARE)))
        for d in Difficulty.values():
            if (only is not None) and (d is not only):
                continue
            wins = 0
            n = 0
            for m in range(maps.MAP_COUNT):
                if (map_ >= 0) and (m != map_):
                    continue
                for k in range(seeds):
                    t0 = _j.current_time_millis()
                    g = ReverseMatch.create(m, (seed0 + k), d)
                    o = AttackerBot.play(g, AttackerBot(g.get_reverse(), style, push, boss), _j.get_boolean('probe.trace'))
                    n += 1
                    if o.attacker_won:
                        wins += 1
                    print(_j.format('[%-6s %-17s] %-24s seed %-4d %s  (%.1fs)%n', d.ascii_label, DefenderProfile.of(d).display_name, maps.create(m).get_name(), (seed0 + k), o, ((_j.current_time_millis() - t0) / 1000.0)), end='')
            print(_j.format('== %s %s: attacker won %d of %d%n', style, d.ascii_label, wins, n), end='')


if __name__ == "__main__":
    import sys
    ReverseProbe.main(sys.argv[1:])
