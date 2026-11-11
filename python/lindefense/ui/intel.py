"""Read-only player intel for the HUD and the tower panel: the next wave's composition after difficulty and Patch Notes
shaping, threat warnings for it, the stat deltas of a tower's next upgrade, and compact numbers.

Nothing here draws a random number or changes game state. The wave is shaped by the same pure functions the
WaveManager calls when it starts the wave (Difficulty.shape seeds its own JavaRandom per wave and group,
RunVariance.shape_wave only reads the current knobs), so the preview lists exactly what will spawn. The one thing that
can still change a wave is its Breaking News, which is rolled when the wave before it ends: while that roll is still to
come (Patch Notes on, previous wave running) the preview is a forecast without it."""
from lindefense.combat.hit_spec import DamageType
from lindefense.enemy.types import Mechanic, Modifier
from lindefense.javacompat import jint, jround
from lindefense.tower import catalog
from lindefense.tower.tower_type import BuffStat, TowerType
from lindefense.variance.variance import Knob
from lindefense.wave import waves

MODIFIER_ORDER = (Modifier.CAMO, Modifier.FORTIFIED, Modifier.REGROW, Modifier.INJECTION)
MODIFIER_TAGS = {Modifier.CAMO: "CAMO", Modifier.FORTIFIED: "FORTIFIED", Modifier.REGROW: "REGROW",
                 Modifier.INJECTION: "PROMPT INJECTION"}
MODIFIER_SHORT = {Modifier.CAMO: "C", Modifier.FORTIFIED: "F", Modifier.REGROW: "R", Modifier.INJECTION: "I"}


# ====================================================================== numbers
def compact(v):
    """Compact count for small readouts: 999, 12.3k, 456k, 4.5M, 1.2B (truncated, never rounded up)."""
    n = int(max(0.0, float(v)))
    if n < 1000:
        return str(n)
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if n >= div:
            if n < 100 * div:
                tenths = n * 10 // div
                return "%d.%d%s" % (tenths // 10, tenths % 10, suf)
            return "%d%s" % (n // div, suf)
    return str(n)


# ====================================================================== waves
def wave_def(n, game=None):
    """The base definition of wave n in this game (Freeplay waves past the campaign come from the run seed), or None
when there is no such wave."""
    if n < 1:
        return None
    if game is not None:
        return waves.for_game(game, n) if waves.exists(game, n) else None
    if n > waves.WAVE_COUNT:
        return None
    try:
        return waves.get(n)
    except (IndexError, KeyError, ValueError):
        return None


def is_lead_type(t):
    """Lead-type for at least part of its life: Heap Sort, Lockheed Martin, Radix Sort (armoured phases)."""
    return t.is_lead_body() or t.mechanic is Mechanic.RADIX_PHASES


class TypeGroup:
    """Every unit of one enemy type in a wave: how many, and how many of them carry each modifier."""
    __slots__ = ("type", "count", "mods", "order")

    def __init__(self, type_, order):
        self.type = type_
        self.count = 0
        self.mods = {}
        self.order = order

    def add(self, n, modifiers):
        self.count += n
        for m in modifiers:
            self.mods[m] = self.mods.get(m, 0) + n
        if self.type.has_innate_camo() and Modifier.CAMO not in modifiers:
            self.mods[Modifier.CAMO] = self.mods.get(Modifier.CAMO, 0) + n

    def modifiers(self):
        return [m for m in MODIFIER_ORDER if self.mods.get(m, 0) > 0]

    def key(self):
        return "%s:%d:%s" % (self.type.name, self.count, ",".join("%s%d" % (MODIFIER_SHORT[m], self.mods[m]) for m in self.modifiers()))


class WavePreview:
    """A wave as it will spawn, grouped by enemy type (bosses first, then the biggest groups)."""

    def __init__(self, number, d, forecast=False, news=None):
        self.number = number
        self.definition = d
        self.forecast = forecast
        self.news = news
        self.note = d.note
        by_type = {}
        for gr in d.groups:
            tg = by_type.get(gr.type)
            if tg is None:
                tg = by_type[gr.type] = TypeGroup(gr.type, len(by_type))
            tg.add(gr.count, gr.modifiers)
        # bosses first, highest class first (BAD, DDT, ZOMG, BFB, MOAB), then the biggest groups
        self.groups = sorted(by_type.values(), key=lambda g: (0, -g.type.get_boss_class().ordinal, g.order)
                             if g.type.is_boss() else (1, -g.count, g.order))
        self.total = d.total_spawns()
        self.modifiers = {}
        for m in MODIFIER_ORDER:
            c = sum(g.mods.get(m, 0) for g in self.groups)
            if c > 0:
                self.modifiers[m] = c
        self.bosses = [g for g in self.groups if g.type.is_boss()]
        self.lead = [g for g in self.groups if is_lead_type(g.type)]

    def count_of(self, t):
        return sum(g.count for g in self.groups if g.type is t)

    def modifier_count(self, m):
        return self.modifiers.get(m, 0)

    def lead_count(self):
        return sum(g.count for g in self.lead)

    def key(self):
        return "%d|%s|%s|%s" % (self.number, self.forecast, "" if self.news is None else self.news.name,
                                ";".join(g.key() for g in self.groups))


def _news_shapes_wave(news):
    m = news.mods()
    return m.has(Knob.ENEMY_COUNT) or m.has(Knob.ALL_CAMO)


def preview(game, n=None):
    """The next wave (or wave n) exactly as the WaveManager will spawn it, or None past the last wave. Read-only."""
    if n is None:
        n = game.get_wave_manager().get_current_wave() + 1
    base = wave_def(n, game)
    if base is None:
        return None
    v = game.get_variance()
    shaped = game.get_difficulty().shape(base, game.get_seed())
    forecast = v.news_pending(n)
    shaped = v.forecast_wave(shaped) if forecast else v.shape_wave(shaped)
    news = v.get_news()
    if forecast or news is None or v.get_news_wave() != n or not _news_shapes_wave(news):
        news = None
    return WavePreview(n, shaped, forecast, news)


# ====================================================================== threats
class Threat:
    BOSS = "boss"
    CAMO = "camo"
    LEAD = "lead"

    def __init__(self, kind, chip, detail):
        self.kind = kind
        self.chip = chip
        self.detail = detail

    def __repr__(self):
        return "Threat(%s, %r)" % (self.kind, self.chip)


def attack_towers(game):
    """The player's placed towers that attack (summons and pure support towers excluded)."""
    return [t for t in game.get_tower_manager().get_towers()
            if t.is_alive() and not t.is_temporary() and not t.get_stats().is_support_only()]


def can_hurt_lead(t):
    h = t.get_stats().hit
    return h.type is not DamageType.SHARP or h.ignores_resistance


def camo_covered(game):
    """True when at least one attacking tower can see camo (built in, gained by upgrade, or from a Perplexity)."""
    return any(t.can_see_camo() for t in attack_towers(game))


def lead_blocked(game):
    """True when the player has attacking towers and every one of them deals Sharp damage that Lead shrugs off."""
    ts = attack_towers(game)
    return bool(ts) and not any(can_hurt_lead(t) for t in ts)


_DETECTION_HINT = [None]


def detection_hint():
    """Which shop towers see camo, and from which tier (derived from the tower data)."""
    if _DETECTION_HINT[0] is None:
        by_tier = {}
        for ty in TowerType.shop_towers():
            d = catalog.get(ty)
            for k in range(len(d.upgrades) + 1):
                s = d.stats_for_tier(k)
                if s.sees_camo or s.aura_detection or s.has("revealAllCamo"):
                    by_tier.setdefault(k, []).append(ty.display_name)
                    break
        parts = []
        for k in sorted(by_tier):
            parts.append(", ".join(by_tier[k]) + (" (built in)" if k == 0 else " (tier %d)" % k))
        _DETECTION_HINT[0] = "; ".join(parts)
    return _DETECTION_HINT[0]


def _names(groups):
    return ", ".join("%s \u00d7%d" % (g.type.display_name, g.count) for g in groups)


def threats(game, pv):
    """Warnings for a previewed wave: a boss is coming; camo is coming and no tower can see it; Lead-type enemies are
    coming and all the player's damage is Sharp."""
    out = []
    if pv is None:
        return out
    if pv.bosses:
        top = pv.bosses[0]
        chip = "BOSS  " + top.type.display_name.upper() + (" \u00d7%d" % top.count if top.count > 1 else "")
        if len(pv.bosses) > 1:
            chip += "  +%d" % (len(pv.bosses) - 1)
        out.append(Threat(Threat.BOSS, chip, "Boss wave: " + _names(pv.bosses) + "."))
    camo = pv.modifier_count(Modifier.CAMO)
    if camo > 0 and not camo_covered(game):
        out.append(Threat(Threat.CAMO, "NO CAMO DETECTION",
                          "%d camo %s and none of your towers can see camo. Detection: %s; any tower near a "
                          "Perplexity." % (camo, "enemy" if camo == 1 else "enemies", detection_hint())))
    if pv.lead and lead_blocked(game):
        out.append(Threat(Threat.LEAD, "SHARP VS LEAD",
                          "%s: Lead-type, and all your damage is Sharp, which cannot hurt Lead. Any other damage type "
                          "can (Claude's final upgrade too)." % _names(pv.lead)))
    return out


# ====================================================================== upgrade deltas
class StatDelta:
    """One stat the next upgrade changes, in the units the tower panel shows. better: True / False / None."""
    __slots__ = ("label", "now", "next", "better", "now_value", "next_value")

    def __init__(self, label, now, next_, better, now_value=None, next_value=None):
        self.label = label
        self.now = now
        self.next = next_
        self.better = better
        self.now_value = now_value
        self.next_value = next_value

    def text(self):
        return "%s %s -> %s" % (self.label, self.now, self.next)

    def __repr__(self):
        return "StatDelta(%s)" % self.text()


def _effective_pierce(t, s):
    """Tower.effective_pierce for stats s (the tower's pierce buffs applied)."""
    flat = t.buff_total_uncapped(BuffStat.PIERCE_FLAT)
    pct = t.buff_total_uncapped(BuffStat.PIERCE_PCT)
    add = min(BuffStat.PIERCE_FLAT.cap, flat + jround(s.pierce * pct))
    return s.pierce + jint(add)


def next_stats(t):
    """The stat block of the tower's next tier (a fresh copy, the tower is untouched), or None at max tier."""
    return t.get_def().stats_for_tier(t.get_tier() + 1) if t.can_upgrade() else None


def next_range(game, t):
    """Effective range after the next upgrade (map, Patch Notes, aura and surveillance multipliers applied)."""
    nxt = next_stats(t)
    if nxt is None:
        return t.effective_range(game)
    flat = t.get_behavior().flat_range_bonus(t)
    base = t.get_stats().range + flat
    k = t.effective_range(game) / base if base > 0 else game.get_global_range_multiplier()
    return (nxt.range + flat) * k


def next_rate(game, t):
    """Attacks per second after the next upgrade (the tower's live rate multipliers applied)."""
    nxt = next_stats(t)
    if nxt is None:
        return t.effective_rate(game)
    return nxt.rate * t.rate_multiplier(game)


def next_sees_camo(t):
    nxt = next_stats(t)
    if nxt is None:
        return t.can_see_camo()
    return bool(nxt.sees_camo or nxt.has("revealAllCamo") or getattr(t, "_granted_detection", False))


def _split(text):
    return [p for p in text.split("  •  ") if p]


def upgrade_deltas(game, t):
    """(stat rows, gained effects) for the tower's next upgrade: only what changes, formatted like the tower panel."""
    from lindefense.ui.hero_stat_text import HeroStatText
    from lindefense.ui.side_panel import SidePanel
    from lindefense.ui.ui import Ui
    nxt = next_stats(t)
    if nxt is None:
        return [], []
    cur = t.get_stats()
    ty = t.get_type()
    rows = []

    def add(label, a, b, fmt, higher_is_better):
        if fmt(a) == fmt(b):
            return
        better = None if higher_is_better is None else ((b > a) == higher_is_better)
        rows.append(StatDelta(label, fmt(a), fmt(b), better, a, b))

    attacks = not (cur.is_support_only() and nxt.is_support_only())
    if attacks:
        dm = t.damage_multiplier(game)
        add("DMG", cur.hit.damage * dm, nxt.hit.damage * dm, Ui.fmt, True)
        add("INTERVAL", 1.0 / max(0.01, t.effective_rate(game)), 1.0 / max(0.01, next_rate(game, t)),
            lambda v: Ui.fmt(v) + "s", False)
    add("RANGE", t.effective_range(game), next_range(game, t), lambda v: HeroStatText.range(ty, v), True)
    if attacks:
        if SidePanel.mode_label(cur) == SidePanel.mode_label(nxt) == "PIERCE":
            add("PIERCE", t.effective_pierce(), _effective_pierce(t, nxt), str, True)
        elif SidePanel.mode_label(cur) != SidePanel.mode_label(nxt) or SidePanel.mode_text(cur) != SidePanel.mode_text(nxt):
            rows.append(StatDelta(SidePanel.mode_label(nxt), SidePanel.mode_text(cur), SidePanel.mode_text(nxt), None))
        add("TARGETS", cur.targets, nxt.targets, str, True)
        add("SHOTS", cur.projectiles_per_shot, nxt.projectiles_per_shot, str, True)
        if cur.splash_radius > 0 or nxt.splash_radius > 0:
            add("SPLASH", cur.splash_radius, nxt.splash_radius, lambda v: HeroStatText.range(ty, v), True)
        if cur.hit.type is not nxt.hit.type:
            rows.append(StatDelta("TYPE", cur.hit.type.label.upper(), nxt.hit.type.label.upper(), None))
    camo_now, camo_next = t.can_see_camo(), next_sees_camo(t)
    if camo_now != camo_next:
        rows.append(StatDelta("CAMO", "YES" if camo_now else "NO", "YES" if camo_next else "NO", camo_next, camo_now, camo_next))
    have = set(_split(SidePanel.effects_text(cur, False))) | set(_split(SidePanel.support_text(cur, False)))
    gained = [e for e in _split(SidePanel.effects_text(nxt, False)) + _split(SidePanel.support_text(nxt, False))
              if e not in have]
    return rows, gained
