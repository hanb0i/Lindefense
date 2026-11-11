"""Lindefense HeroStatText (ported from src/lindefense/ui/HeroStatText.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.tower import catalog
from lindefense.tower.behavior.heroes import KaijuKaiBehavior
from lindefense.tower.behavior.heroes import MrLindemannBehavior
from lindefense.tower.behavior.heroes import TanimbusBehavior
from lindefense.tower.behavior.primary import ZethosBehavior
from lindefense.tower.tower_type import AttackKind
from lindefense.tower.tower_type import TowerType
import lindefense.tower.stats as _m_stats


class HeroStatText:
    """Text for the Hero Store cards and the info panel of the Hero Store heroes and Zethos. Every number is read from the
data table (never typed here), and distances are shown in the specification's map units."""
    def __init__(self):
        pass
    @staticmethod
    def uses_units(t):
        """Whether a type's stats are specified in map units (heroes and Zethos)."""
        return t.is_hero() or (t is TowerType.ZETHOS)
    @staticmethod
    def range(t, px):
        """Range label: "220" px for standard towers, "55u" for heroes and Zethos."""
        return _j.cat(Ui.fmt(_m_stats.to_units(px)), 'u') if HeroStatText.uses_units(t) else _j.s(_j.to_int(px))
    @staticmethod
    def u(px):
        return Ui.fmt(_m_stats.to_units(px))
    @staticmethod
    def role(t):
        """Combat role line ("Explosive Artillery")."""
        return catalog.get(t).subtitle
    @staticmethod
    def attack_name(t):
        """Name of the primary attack: a hero's base tier label is the name of what it does."""
        d = catalog.get(t)
        return 'Attack' if ((d is None) or (len(d.tier_labels) == 0)) else d.tier_labels[0]
    @staticmethod
    def _attack_lines_0(t):
        """Statistics of a hero at one tier, two to three short lines."""
        return HeroStatText.attack_lines(t, 0)
    @staticmethod
    def _attack_lines_1(t, tier):
        """Statistics at the given tier (0 = base), so the store can preview what an upgrade changes."""
        d = catalog.get(t)
        s = d.stats_for_tier(tier)
        l = _j.ArrayList()
        if s.p('healAmount', 0) > 0:
            _j_add(l, _j.cat('Restores ', _j.to_int(s.p('healAmount')), ' integrity  •  every ', Ui.fmt(s.p('healInterval')), 's'))
            _j_add(l, _j.cat('Aura ', HeroStatText.u(s.field_radius), 'u  •  never above your starting maximum'))
            if s.p('emergencyRestore', 0) > 0:
                _j_add(l, _j.cat('Once per match: +', HeroStatText.pct(s.p('emergencyRestore')), ' max integrity below ', HeroStatText.pct(s.p('emergencyThreshold'))))
            return l
        if s.p('income', 0) > 0:
            _j_add(l, _j.cat('$', _j.to_int(s.p('income')), '  •  every ', Ui.fmt(s.p('incomeInterval')), 's  •  never attacks'))
            _j_add(l, (_j.cat('Bonus $', _j.to_int(s.p('bonus')), ' every ', Ui.fmt(s.p('bonusInterval')), 's') if (s.p('bonus', 0) > 0) else _j.cat('Paid straight into your balance  •  $', _j.to_int((s.p('income') * 6)), ' per minute')))
            return l
        if t is TowerType.TANIMBUS:
            single = (s.p('singleTarget', 0) > 0)
            _j_add(l, _j.cat(('Strongest tower in ' if single else 'All towers in '), HeroStatText.u(s.aura_range), 'u  •  flying'))
            _j_add(l, _j.cat('+', HeroStatText.pct((s.p('buffRate') if single else s.aura_rate)), ' attack speed', (_j.cat('  •  +', HeroStatText.pct(s.aura_range_bonus), ' range') if (s.aura_range_bonus > 0) else '')))
            if s.p('rallyInterval', 0) > 0:
                _j_add(l, _j.cat('Every ', Ui.fmt(s.p('rallyInterval')), 's: +', HeroStatText.pct(s.p('rallyRate')), ' to every tower for ', Ui.fmt(s.p('rallyDuration')), 's'))
            return l
        if (s.p('maxMines', 0) > 0) or (s.p('maxTraps', 0) > 0):
            trap = (s.p('maxTraps', 0) > 0)
            max_ = (s.pi('maxTraps') if trap else s.pi('maxMines'))
            _j_add(l, _j.cat(max_, (' traps' if trap else ' mines'), ' x ', Ui.fmt(s.hit.damage), ' dmg  •  one every ', Ui.fmt(s.interval()), 's'))
            _j_add(l, _j.cat('Blast ', HeroStatText.u((s.p('trapRadius') if trap else s.p('mineRadius'))), 'u  •  range ', HeroStatText.u(s.range), 'u'))
            if trap:
                _j_add(l, _j.cat('Holds normals ', Ui.fmt(s.p('holdDuration')), 's  •  bosses take damage only', (_j.cat('  •  ', Ui.fmt(s.p('tetherDps')), '/s while held') if (s.p('tetherDps', 0) > 0) else '')))
            elif s.hit.slow_fraction > 0:
                _j_add(l, _j.cat('Slows ', HeroStatText.pct(s.hit.slow_fraction), ' for ', Ui.fmt(s.hit.slow_duration), 's', (_j.cat('  •  ', HeroStatText.pct(s.p('secondaryChance')), ' second blast') if (s.p('secondaryChance', 0) > 0) else '')))
            return l
        if s.p('beamDuration', 0) > 0:
            _j_add(l, _j.cat(Ui.fmt(s.p('beamDamage')), ' dmg per tick  •  beam ', Ui.fmt(s.p('beamDuration')), 's  •  range ', HeroStatText.u(s.range), 'u'))
            _j_add(l, _j.cat('Burns everything along its path  •  every ', Ui.fmt(s.interval()), 's'))
        else:
            core = _j.cat(Ui.fmt(s.hit.damage), ' dmg  •  every ', Ui.fmt(s.interval()), 's  •  range ', HeroStatText.u(s.range), 'u')
            _j_add(l, core)
            bits = _j.ArrayList()
            if s.splash_radius > 0:
                _j_add(bits, _j.cat('splash ', HeroStatText.u(s.splash_radius), 'u'))
            if s.pierce > 1:
                _j_add(bits, _j.cat('pierce ', s.pierce))
            if s.chain_hops > 0:
                _j_add(bits, _j.cat('chains ', (s.chain_hops + 1), ' targets'))
            if s.targets > 1:
                _j_add(bits, _j.cat(s.pi('bullets', s.targets), (' bullets' if (t is TowerType.BLITZ_ARNAV) else ' shots'), ' per attack'))
            if s.projectiles_per_shot > 1:
                _j_add(bits, _j.cat(s.projectiles_per_shot, ' spears'))
            if s.hit.knockback > 0:
                _j_add(bits, 'knockback')
            if s.sees_camo:
                _j_add(bits, 'sees camo')
            if s.ignores_los:
                _j_add(bits, 'flying')
            if not (len(bits) == 0):
                _j_add(l, HeroStatText.join(bits))
        extra = _j.ArrayList()
        if s.hit.slow_fraction > 0:
            _j_add(extra, _j.cat('slow ', HeroStatText.pct(s.hit.slow_fraction), ' for ', Ui.fmt(s.hit.slow_duration), 's'))
        if s.hit.dot_dps > 0:
            _j_add(extra, _j.cat('poison ', Ui.fmt(s.hit.dot_dps), '/s for ', Ui.fmt(s.hit.dot_duration), 's'))
        if s.p('critChance', 0) > 0:
            _j_add(extra, _j.cat(HeroStatText.pct(s.p('critChance')), ' crit x', Ui.fmt(s.p('critMult'))))
        if s.p('clusterBombs', 0) > 0:
            _j_add(extra, _j.cat(s.pi('clusterBombs'), ' bomblets x ', Ui.fmt(s.p('clusterDamage'))))
        if s.p('freezeChance', 0) > 0:
            _j_add(extra, _j.cat(HeroStatText.pct(s.p('freezeChance')), ' freeze every ', s.pi('freezeEvery')))
        if s.p('vineDps', 0) > 0:
            _j_add(extra, _j.cat('vines ', Ui.fmt(s.p('vineDps')), '/s every ', Ui.fmt(s.p('vineInterval')), 's'))
        if s.p('fieldSlow', 0) > 0:
            _j_add(extra, _j.cat('field ', HeroStatText.pct(s.p('fieldSlow')), ' every ', Ui.fmt(s.p('fieldInterval')), 's'))
        if s.p('blastDamage', 0) > 0:
            _j_add(extra, _j.cat('blast ', Ui.fmt(s.p('blastDamage')), ' every ', Ui.fmt(s.p('blastInterval')), 's'))
        if s.p('bombDamage', 0) > 0:
            _j_add(extra, _j.cat('bombing run ', Ui.fmt(s.p('bombDamage')), ' every ', Ui.fmt(s.p('bombInterval')), 's'))
        if s.p('nukeDamage', 0) > 0:
            _j_add(extra, _j.cat('nuke ', Ui.fmt(s.p('nukeDamage')), ' every ', s.pi('nukeEvery')))
        if s.p('smashDamage', 0) > 0:
            _j_add(extra, _j.cat('smash ', Ui.fmt(s.p('smashDamage')), ' every ', s.pi('smashEvery')))
        if s.p('rocketDamage', 0) > 0:
            _j_add(extra, _j.cat('rocket ', Ui.fmt(s.p('rocketDamage')), ' every ', s.pi('rocketEvery')))
        if s.p('returns', 0) > 0:
            _j_add(extra, 'returns through the line')
        if not (len(extra) == 0):
            _j_add(l, HeroStatText.join(extra))
        return l
    @staticmethod
    def attack_lines(*a):
        if len(a) == 1:
            return HeroStatText._attack_lines_0(*a)
        elif len(a) == 2:
            return HeroStatText._attack_lines_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    @staticmethod
    def join(parts):
        return '  •  '.join(parts)
    @staticmethod
    def pct(f):
        return _j.cat(_j.jround((f * 100)), '%')
    @staticmethod
    def live_line(game, t):
        """Live status line for a placed hero / Zethos (beams, planted devices, supported towers), or null if there is
nothing to say right now."""
        ty = t.get_type()
        s = t.get_stats()
        _sw1 = ty
        if _sw1 is TowerType.ZETHOS:
            a = t.get_ability()
            if (a is None) or (not ZethosBehavior.is_collapsing(t)):
                return None
            return _j.cat('REALITY COLLAPSE ', _j.jround(t.self_buff_remaining(ZethosBehavior.COLLAPSE)), 's: x', Ui.fmt(a.p('damageMult')), ' damage, x', Ui.fmt(a.p('rateMult')), ' speed, +', HeroStatText.u(a.p('rangeBonus')), 'u range, ', _j.to_int(a.p('bounces')), ' bounces')
        elif _sw1 is TowerType.KAIJU_KAI:
            return 'ATOMIC BREATH burning everything on the beam' if KaijuKaiBehavior.is_beaming(t) else None
        elif _sw1 is TowerType.CAMI_MINE:
            return _j.cat('Mines armed: ', len(game.get_effects().mines_of(t, 'mine')), ' / ', s.pi('maxMines'))
        elif _sw1 is TowerType.TRAPPER_CHE:
            return _j.cat('Traps set: ', len(game.get_effects().mines_of(t, 'trap')), ' / ', s.pi('maxTraps'))
        elif _sw1 is TowerType.THORN_TUHIN:
            vines = len(game.get_effects().zones_of(t, 'vines'))
            return _j.cat('Vines growing: ', vines, ' / ', s.pi('maxVines', 2)) if (vines > 0) else None
        elif _sw1 is TowerType.TANIMBUS:
            sup = TanimbusBehavior.supported(game, t)
            if sup is not None:
                return _j.cat('Boosting ', sup.get_type().display_name, ' (+', HeroStatText.pct(s.p('buffRate')), ' attack speed)')
            return 'No tower in range to boost' if (s.p('singleTarget', 0) > 0) else None
        elif _sw1 is TowerType.SAGE_AARAV:
            return _j.cat('Integrity ', game.get_lives(), ' / ', game.get_max_lives())
        elif _sw1 is TowerType.MR_LINDEMANN:
            left = MrLindemannBehavior.warp_remaining(t)
            holes = len(game.get_effects().zones_of(t, MrLindemannBehavior.HOLE))
            return _j.cat(('Space warp ready' if (left <= 0) else _j.cat('Space warp in ', _j.to_int(float(math.ceil(left))), 's')), '  •  singularities ', holes, ' / ', s.pi('maxHoles', 3))
        else:
            return None
    @staticmethod
    def is_support_hero(t):
        """True when the hero never attacks (the UI hides damage-style stats for these)."""
        d = catalog.get(t)
        return (d is not None) and (d.base_stats.kind is AttackKind.NONE)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.ui import Ui  # noqa: E402
