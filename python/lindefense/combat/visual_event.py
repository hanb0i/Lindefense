"""Transient visual notifications produced by the simulation; the renderer drains them each frame."""


class VisualEvent:
    BEAM, CHAIN, HIT, EXPLOSION, TEXT, DEATH, TELEPORT, ABILITY, BANNER, PHASE, SPLIT = (
        "BEAM", "CHAIN", "HIT", "EXPLOSION", "TEXT", "DEATH", "TELEPORT", "ABILITY", "BANNER", "PHASE", "SPLIT")

    def __init__(self, kind, a, b, radius, rgb, text, duration):
        self.kind, self.a, self.b, self.radius = kind, a, b, radius
        self.rgb, self.duration = rgb, duration
        self.__dict__["text"] = text   # instance field shadows the text() factory, as in Java

    @staticmethod
    def beam(a, b, rgb):
        return VisualEvent(VisualEvent.BEAM, a, b, 2, rgb, None, 0.12)

    @staticmethod
    def chain(a, b, rgb):
        return VisualEvent(VisualEvent.CHAIN, a, b, 2, rgb, None, 0.15)

    @staticmethod
    def hit(a, rgb):
        return VisualEvent(VisualEvent.HIT, a, None, 6, rgb, None, 0.15)

    @staticmethod
    def explosion(a, r, rgb):
        return VisualEvent(VisualEvent.EXPLOSION, a, None, r, rgb, None, 0.35)

    @staticmethod
    def text(a, t, rgb):
        return VisualEvent(VisualEvent.TEXT, a, None, 0, rgb, t, 1.2)

    @staticmethod
    def death(a, r, rgb):
        return VisualEvent(VisualEvent.DEATH, a, None, r, rgb, None, 0.4)

    @staticmethod
    def split(a, r, rgb):
        return VisualEvent(VisualEvent.SPLIT, a, None, r, rgb, None, 0.5)

    @staticmethod
    def teleport(a):
        return VisualEvent(VisualEvent.TELEPORT, a, None, 24, 0xd0b0ff, None, 0.5)

    @staticmethod
    def ability(a, r, rgb):
        return VisualEvent(VisualEvent.ABILITY, a, None, r, rgb, None, 0.6)

    @staticmethod
    def banner(t, rgb, dur):
        return VisualEvent(VisualEvent.BANNER, None, None, 0, rgb, t, dur)

    @staticmethod
    def phase(a, t, rgb):
        return VisualEvent(VisualEvent.PHASE, a, None, 120, rgb, t, 1.5)


class _Kind:
    """VisualEvent.Kind: the same constant objects, so `kind is VisualEvent.Kind.BEAM` holds."""


for _k in ("BEAM", "CHAIN", "HIT", "EXPLOSION", "TEXT", "DEATH", "TELEPORT", "ABILITY", "BANNER", "PHASE", "SPLIT"):
    setattr(_Kind, _k, getattr(VisualEvent, _k))
VisualEvent.Kind = _Kind
