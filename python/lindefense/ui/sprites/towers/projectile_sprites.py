"""Lindefense ProjectileSprites (ported from src/lindefense/ui/sprites/towers/ProjectileSprites.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.combat.visual_event import VisualEvent
from lindefense.tower.tower_type import TowerType


class ProjectileSprites:
    """Factory for projectile sprites and attack effects. Every tower type gets a
distinct projectile family matching its attack concept (Claude lances, Llama
kinetic wads, MiniMax bouncing orbs, Suno notes, Kimi sniper rounds, Brad
command-energy spheres, Ronil meteors, Zethos quantum diamonds, ...) that scales up with tier."""
    def __init__(self):
        pass
    @staticmethod
    def _create_0(p):
        """Creates the sprite for a live projectile. Unknown or null sources fall
back to a plain glossy dot in the projectile's own colour."""
        if p is None:
            return ProjectileSprite(ProjectileSprite.Style.DOT, 0, 5, Color.WHITE, Color.WHITE)
        src = p.get_source()
        type_ = (None if (src is None) else src.get_type())
        tier = (0 if (src is None) else src.get_tier())
        s = ProjectileSprites.create(type_, tier, p.get_stats(), p.get_size(), p.get_rgb())
        s.sync(p, 0)
        return s
    @staticmethod
    def _create_1(type_, tier, stats, size, rgb):
        """Creates a projectile sprite from its parameters (also used by the gallery).

@param type  source tower type, may be null
@param tier  source tier 0-4
@param stats stats of the shot (splash / pierce tune size), may be null
@param size  logical radius
@param rgb   the projectile's own colour, used for fallbacks and paint"""
        sz = size
        if stats is not None:
            if stats.splash_radius > 60:
                sz *= 1.2
            if stats.pierce >= 8:
                sz *= 1.1
        if type_ is None:
            return ProjectileSprite(ProjectileSprite.Style.DOT, tier, sz, Art.rgb(rgb), Color.WHITE)
        pri = Art.rgb(type_.primary_rgb)
        sec = Art.rgb(type_.secondary_rgb)
        _sw1 = type_
        if _sw1 is TowerType.CLAUDE:
            return ProjectileSprite(ProjectileSprite.Style.LANCE, tier, sz, pri, sec)
        elif _sw1 is TowerType.GPT:
            return ProjectileSprite(ProjectileSprite.Style.TOKEN, tier, sz, pri, sec)
        elif _sw1 is TowerType.GEMINI:
            return ProjectileSprite(ProjectileSprite.Style.SPARK, tier, sz, pri, sec)
        elif _sw1 is TowerType.DEEPSEEK:
            return ProjectileSprite(ProjectileSprite.Style.SLUG, tier, sz, pri, sec)
        elif _sw1 is TowerType.COPILOT:
            return ProjectileSprite(ProjectileSprite.Style.SNIPPET, tier, sz, pri, sec)
        elif _sw1 is TowerType.DALLE:
            return ProjectileSprite(ProjectileSprite.Style.PAINT, tier, sz, Art.rgb((type_.primary_rgb if (rgb == 0) else rgb)), sec)
        elif _sw1 is TowerType.DALLE_SPRITE:
            return ProjectileSprite(ProjectileSprite.Style.PAINT, 0, (sz * 0.8), Art.rgb(0xff5fa2), sec)
        elif _sw1 is TowerType.SORA:
            return ProjectileSprite(ProjectileSprite.Style.PULSE, tier, sz, pri, sec)
        elif _sw1 is TowerType.SUNO:
            return ProjectileSprite(ProjectileSprite.Style.NOTE, tier, sz, pri, sec)
        elif _sw1 is TowerType.GROK:
            return ProjectileSprite(ProjectileSprite.Style.BOLT, tier, sz, pri, sec)
        elif _sw1 is TowerType.PERPLEXITY:
            return ProjectileSprite(ProjectileSprite.Style.PIN, tier, sz, pri, sec)
        elif _sw1 is TowerType.QWEN:
            return ProjectileSprite(ProjectileSprite.Style.BLADE, tier, sz, pri, sec)
        elif _sw1 is TowerType.LLAMA:
            return ProjectileSprite(ProjectileSprite.Style.WAD, tier, sz, pri, sec)
        elif _sw1 is TowerType.MISTRAL:
            return ProjectileSprite(ProjectileSprite.Style.GALE, tier, sz, pri, sec)
        elif _sw1 is TowerType.COHERE:
            return ProjectileSprite(ProjectileSprite.Style.SPARK, tier, sz, pri, sec)
        elif _sw1 is TowerType.GLM:
            return ProjectileSprite(ProjectileSprite.Style.PULSE, tier, sz, pri, sec)
        elif _sw1 is TowerType.KIMI:
            return ProjectileSprite(ProjectileSprite.Style.ROUND, tier, sz, pri, sec)
        elif _sw1 is TowerType.MINIMAX:
            return ProjectileSprite(ProjectileSprite.Style.ORB, tier, sz, pri, sec)
        elif _sw1 is TowerType.LOBBER_LUIS:
            return ProjectileSprite(ProjectileSprite.Style.METEOR, 2, sz, pri, sec)
        elif _sw1 is TowerType.BOOM_SAM:
            return ProjectileSprite(ProjectileSprite.Style.METEOR, 1, sz, pri, sec)
        elif _sw1 is TowerType.IRON_IMRAAN:
            return ProjectileSprite(ProjectileSprite.Style.COMMAND, 0, sz, pri, sec)
        elif _sw1 is TowerType.CHILLSTIN:
            return ProjectileSprite(ProjectileSprite.Style.CRYO, 1, sz, pri, sec)
        elif _sw1 is TowerType.KAIJU_KAI:
            return ProjectileSprite(ProjectileSprite.Style.COMMAND, 2, sz, pri, sec)
        elif _sw1 is TowerType.ABHI_ACE:
            return ProjectileSprite(ProjectileSprite.Style.DRONE, 1, sz, pri, sec)
        elif _sw1 is TowerType.NIK_SCOPE:
            return ProjectileSprite(ProjectileSprite.Style.VOLLEY, 2, sz, pri, sec)
        elif _sw1 is TowerType.BLITZ_ARNAV:
            return ProjectileSprite(ProjectileSprite.Style.VOLLEY, 0, sz, pri, sec)
        elif _sw1 is TowerType.SPEAR_HANBO:
            return ProjectileSprite(ProjectileSprite.Style.VOLLEY, 1, sz, pri, sec)
        elif _sw1 is TowerType.THORN_TUHIN:
            return ProjectileSprite(ProjectileSprite.Style.DATA, 1, sz, pri, sec)
        elif _sw1 is TowerType.JUSTIN_TIME:
            return ProjectileSprite(ProjectileSprite.Style.DATA, 0, sz, pri, sec)
        elif _sw1 is TowerType.CAMI_MINE or _sw1 is TowerType.TRAPPER_CHE:
            return ProjectileSprite(ProjectileSprite.Style.METEOR, 0, sz, pri, sec)
        elif _sw1 is TowerType.ZETHOS:
            return ProjectileSprite(ProjectileSprite.Style.QUANTUM, tier, sz, pri, sec)
        elif _sw1 is TowerType.MR_LINDEMANN:
            return ProjectileSprite(ProjectileSprite.Style.SINGULARITY, tier, sz, pri, sec)
        else:
            return ProjectileSprite(ProjectileSprite.Style.DOT, tier, sz, Art.rgb(rgb), Color.WHITE)
    @staticmethod
    def create(*a):
        if len(a) == 1:
            return ProjectileSprites._create_0(*a)
        elif len(a) == 5:
            return ProjectileSprites._create_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    @staticmethod
    def create_attack_effect(ev):
        """Builds a cartoon effect for a BEAM, CHAIN, HIT or EXPLOSION event.
Returns null for every other kind (the world view keeps its own handling
for text, banners, deaths and so on)."""
        if (ev is None) or (ev.kind is None):
            return None
        _sw2 = ev.kind
        if _sw2 is VisualEvent.Kind.BEAM:
            return None if ((ev.a is None) or (ev.b is None)) else AttackEffects.Beam(ev)
        elif _sw2 is VisualEvent.Kind.CHAIN:
            return None if ((ev.a is None) or (ev.b is None)) else AttackEffects.Chain(ev)
        elif _sw2 is VisualEvent.Kind.HIT:
            return None if (ev.a is None) else AttackEffects.Hit(ev)
        elif _sw2 is VisualEvent.Kind.EXPLOSION:
            return None if (ev.a is None) else AttackEffects.Explosion(ev)
        else:
            return None


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.art import Art  # noqa: E402
from lindefense.ui.sprites.towers.attack_effects import AttackEffects  # noqa: E402
from lindefense.ui.sprites.towers.projectile_sprite import ProjectileSprite  # noqa: E402
