"""Regressions found while debugging the Python port (beyond the UI and simulation suites)."""
import os
import subprocess
import sys
import textwrap


from lindefense.app import _WindowAdapter
from lindefense.sim.misc import HeroCollection
from lindefense.tower.tower_type import TowerType

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_unlocked_heroes_iterate_in_declaration_order(check):
    """Java's EnumSet iterates in ordinal order; a Python set of enums iterates in string-hash order, which changes
    from run to run (PYTHONHASHSEED)."""
    heroes = [t for t in TowerType if t.is_hero()]
    h = HeroCollection.in_memory()
    for t in reversed(heroes):
        h.unlock(t)
    check(list(h.unlocked()) == heroes, "unlocked() iterates in TowerType order")
    code = textwrap.dedent("""
        from lindefense.sim.misc import HeroCollection
        from lindefense.tower.tower_type import TowerType
        h = HeroCollection.in_memory()
        for t in reversed([t for t in TowerType if t.is_hero()]):
            h.unlock(t)
        print(",".join(t.name for t in h.unlocked()))
    """)
    outs = set()
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        outs.add(subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout)
    check(len(outs) == 1, "the order is the same under every hash seed: %r" % outs)


class _FakeSdl:
    def __init__(self, flags):
        self.flags = flags

    def SDL_GetWindowFlags(self, ptr):
        return self.flags


class _FakeApp:
    def __init__(self, flags):
        self.sdl = _FakeSdl(flags)
        self.win_ptr = None


def test_window_grab_ignores_hidden_and_minimized_windows(check):
    """Palantir's window grab: a minimized window used to count as "maximized" (showing the "blocked: it is
    maximized" banner), and is_showing() was always true."""
    SHOWN, HIDDEN, MINIMIZED, MAXIMIZED, FULLSCREEN = 0x4, 0x8, 0x40, 0x80, 0x1
    cases = {
        "shown": (SHOWN, True, False),
        "hidden": (HIDDEN, False, False),
        "minimized": (SHOWN | MINIMIZED, False, False),
        "maximized": (SHOWN | MAXIMIZED, True, True),
        "fullscreen": (SHOWN | FULLSCREEN, True, True),
    }
    for name, (flags, showing, maxed) in cases.items():
        w = _WindowAdapter(_FakeApp(flags))
        check(w.is_showing() is showing, "%s window: is_showing() is %s" % (name, showing))
        check(w.is_maximized_or_full_screen() is maxed, "%s window: maximized/full screen is %s" % (name, maxed))
