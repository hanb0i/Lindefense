"""Lindefense ReverseProbe (ported from src/lindefense/tools/ReverseProbe.java)."""
import os
import time

from lindefense.ui import jrt as _j
from lindefense.ai.reverse_match import AttackerBot
from lindefense.ai.reverse_match import ReverseMatch
from lindefense.ai.units import DefenderProfile, Doctrine
from lindefense.map import maps
from lindefense.sim.difficulty import Difficulty
import lindefense.ai.reverse_match as _m_reverse_match

MAX_JOBS = 6


def _match(args):
    """One probe match (a top-level function, so a process pool can run it): (line, won, match seconds)."""
    style_name, level_name, m, seed, doctrine_name, push, boss = args
    os.environ.setdefault("LINDEFENSE_NOSOUND", "1")
    d = Difficulty.value_of(level_name)
    doc = Doctrine.value_of(doctrine_name)
    t0 = time.time()
    g = ReverseMatch.create(m, seed, d, doc)
    o = AttackerBot.play(g, AttackerBot(g.get_reverse(), AttackerBot.Style.value_of(style_name), push, boss), _j.get_boolean('probe.trace'))
    line = _j.format('[%-6s %-17s %-5s] %-24s seed %-4d %s  (%.1fs)', d.ascii_label, DefenderProfile.of(d).display_name,
                     doc.display_name, maps.create(m).get_name(), seed, o, time.time() - t0)
    return line, o.attacker_won, o.time


class ReverseProbe:
    """Headless balance probe for reverse mode ("Adversarial Training"): scripted attackers (AttackerBot) against
the defender AI on every map and Difficulty Growth level, one line per match, then a summary per level (wins and the
average match length).

Usage: .venv/bin/python -m lindefense.tools.reverse_probe [style] [level] [map] [doctrine] with style
PASSIVE / SPAM / REASONABLE (default REASONABLE), level O1 / ON / ON2 / ONN or ALL (default ALL), a map index or
-1 for every map (default -1) and doctrine RUSH / SWARM / HEIST or ALL (default RUSH); PROBE_SEEDS=K runs K seeds per
combination from PROBE_SEED=N; PROBE_JOBS=J runs J matches in parallel (at most 6); PROBE_PUSH=S / PROBE_BOSS=F
change the reasonable bot's push size (seconds of income) and boss share; PROBE_TRACE=true prints the economy every
30 s."""
    def __init__(self):
        pass

    @staticmethod
    def main(args):
        _j.set_property('lindefense.nosound', 'true')
        style = (args[0].upper() if (len(args) > 0) else 'REASONABLE')
        AttackerBot.Style.value_of(style)
        only = (Difficulty.parse(args[1]) if ((len(args) > 1) and (args[1].lower() != 'all')) else None)
        map_ = (int(args[2]) if (len(args) > 2) else (-1))
        docs = ([d.name for d in Doctrine] if (len(args) > 3 and args[3].lower() == 'all')
                else [(args[3].upper() if len(args) > 3 else Doctrine.default().name)])
        seeds = _j.get_integer('probe.seeds', 1)
        seed0 = _j.get_long('probe.seed', 77)
        jobs = max(1, min(MAX_JOBS, _j.get_integer('probe.jobs', 1)))
        push = float(_j.get_property('probe.push', _j.s(_m_reverse_match.DEFAULT_PUSH_SECONDS)))
        boss = float(_j.get_property('probe.boss', _j.s(_m_reverse_match.DEFAULT_BOSS_SHARE)))
        pool = None
        if jobs > 1:
            from multiprocessing import Pool
            pool = Pool(jobs)
        try:
            for d in Difficulty.values():
                if (only is not None) and (d is not only):
                    continue
                for doc in docs:
                    work = [(style, d.name, m, seed0 + k, doc, push, boss) for m in range(maps.MAP_COUNT)
                            if map_ < 0 or m == map_ for k in range(seeds)]
                    results = pool.imap(_match, work) if pool is not None else map(_match, work)
                    wins = n = 0
                    total = 0.0
                    for line, won, t in results:
                        print(line, flush=True)
                        n += 1
                        wins += 1 if won else 0
                        total += t
                    avg = total / max(1, n)
                    print('== %s %s %s: attacker won %d of %d, average match %s' % (style, d.ascii_label, doc, wins, n,
                                                                                    ReverseMatch.clock(avg)), flush=True)
        finally:
            if pool is not None:
                pool.close()


if __name__ == "__main__":
    import sys
    ReverseProbe.main(sys.argv[1:])
