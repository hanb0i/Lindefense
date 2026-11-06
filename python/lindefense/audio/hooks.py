"""AUDIO HOOK entry points called by the simulation. No-ops until a live audio manager is installed, so headless
simulations and tests stay silent and pay nothing."""

_live = None


def set_live(manager) -> None:
    global _live
    _live = manager


def get_live():
    return _live


def sfx(s) -> None:
    m = _live
    if m is not None:
        m.play(s)


def event(ev) -> None:
    m = _live
    if m is not None:
        m.on_event(ev)
