"""Lindefense TowerArtFactory (ported from src/lindefense/ui/sprites/towers/TowerArtFactory.java)."""
import math
import re

from lindefense.ui import jrt as _j
from lindefense.ui.jrt import (_j_add, _j_compute_if_absent, _j_for_each, _j_iter, _j_map_for_each, _j_merge,
                               _j_postinc, _j_postinc_idx, _j_preinc, _j_preinc_idx, _j_put, _j_remove,
                               _j_remove_all, _j_remove_if, _j_retain_all, _j_set, _j_swap, _j_sysout)
from lindefense.ui.jawt import *  # noqa: F401,F403
from lindefense.ui.acm import *  # noqa: F401,F403
from lindefense.tower.tower_type import TowerType


class TowerArtFactory:
    """Maps each TowerType to its TowerArt class."""
    def __init__(self):
        pass
    @staticmethod
    def _art_stage_0(game_tier):
        """Maps a standard tower's game tier (0-3) to the art stage (0-4) that draws it."""
        return TowerArtFactory.STAGE_FOR_TIER[max(0, min(3, game_tier))]
    @staticmethod
    def _art_stage_1(type_, game_tier):
        """Art stage for a tower type: standard towers use #artStage(int); Zethos's five tiers (0-4) are five
stages; a hero's four tiers map straight through, so every upgrade visibly changes its gear."""
        if (type_ is not None) and type_.is_hero():
            return max(0, min(3, game_tier))
        if type_ is TowerType.ZETHOS:
            return max(0, min(4, game_tier))
        return TowerArtFactory.art_stage(game_tier)
    @staticmethod
    def art_stage(*a):
        if len(a) == 1:
            return TowerArtFactory._art_stage_0(*a)
        elif len(a) == 2:
            return TowerArtFactory._art_stage_1(*a)
        raise TypeError('no overload for %d args' % len(a))
    @staticmethod
    def create(type_, tier, r):
        """Builds the body art for a tower.

@param type tower type (null falls back to a generic bot)
@param tier art stage (0-4); use #artStage to convert a game tier
@param r    footprint radius in logical units"""
        if type_ is None:
            return GenericArt(TowerType.GPT, tier, r)
        if type_.is_hero():
            return HeroArt(type_, tier, r)
        _sw1 = type_
        if _sw1 is TowerType.CLAUDE:
            return ClaudeArt(type_, tier, r)
        elif _sw1 is TowerType.GPT:
            return GptArt(type_, tier, r)
        elif _sw1 is TowerType.GEMINI:
            return GeminiArt(type_, tier, r)
        elif _sw1 is TowerType.DEEPSEEK:
            return DeepSeekArt(type_, tier, r)
        elif _sw1 is TowerType.COPILOT:
            return CopilotArt(type_, tier, r)
        elif _sw1 is TowerType.DALLE:
            return DalleArt(type_, tier, r)
        elif _sw1 is TowerType.SORA:
            return SoraArt(type_, tier, r)
        elif _sw1 is TowerType.SUNO:
            return SunoArt(type_, tier, r)
        elif _sw1 is TowerType.GROK:
            return GrokArt(type_, tier, r)
        elif _sw1 is TowerType.PERPLEXITY:
            return PerplexityArt(type_, tier, r)
        elif _sw1 is TowerType.QWEN:
            return QwenArt(type_, tier, r)
        elif _sw1 is TowerType.LLAMA:
            return LlamaArt(type_, tier, r)
        elif _sw1 is TowerType.MISTRAL:
            return MistralArt(type_, tier, r)
        elif _sw1 is TowerType.COHERE:
            return CohereArt(type_, tier, r)
        elif _sw1 is TowerType.GLM:
            return GlmArt(type_, tier, r)
        elif _sw1 is TowerType.KIMI:
            return KimiArt(type_, tier, r)
        elif _sw1 is TowerType.MINIMAX:
            return MiniMaxArt(type_, tier, r)
        elif _sw1 is TowerType.ZETHOS:
            return ZethosArt(type_, tier, r)
        elif _sw1 is TowerType.DALLE_SPRITE:
            return SpriteArt(type_, tier, r)
        else:
            return GenericArt(type_, tier, r)


# deferred imports (after the class definitions, so import cycles resolve)
from lindefense.ui.sprites.towers.claude_art import ClaudeArt  # noqa: E402
from lindefense.ui.sprites.towers.cohere_art import CohereArt  # noqa: E402
from lindefense.ui.sprites.towers.copilot_art import CopilotArt  # noqa: E402
from lindefense.ui.sprites.towers.dalle_art import DalleArt  # noqa: E402
from lindefense.ui.sprites.towers.deep_seek_art import DeepSeekArt  # noqa: E402
from lindefense.ui.sprites.towers.gemini_art import GeminiArt  # noqa: E402
from lindefense.ui.sprites.towers.generic_art import GenericArt  # noqa: E402
from lindefense.ui.sprites.towers.glm_art import GlmArt  # noqa: E402
from lindefense.ui.sprites.towers.gpt_art import GptArt  # noqa: E402
from lindefense.ui.sprites.towers.grok_art import GrokArt  # noqa: E402
from lindefense.ui.sprites.towers.hero_art import HeroArt  # noqa: E402
from lindefense.ui.sprites.towers.kimi_art import KimiArt  # noqa: E402
from lindefense.ui.sprites.towers.llama_art import LlamaArt  # noqa: E402
from lindefense.ui.sprites.towers.mini_max_art import MiniMaxArt  # noqa: E402
from lindefense.ui.sprites.towers.mistral_art import MistralArt  # noqa: E402
from lindefense.ui.sprites.towers.perplexity_art import PerplexityArt  # noqa: E402
from lindefense.ui.sprites.towers.qwen_art import QwenArt  # noqa: E402
from lindefense.ui.sprites.towers.sora_art import SoraArt  # noqa: E402
from lindefense.ui.sprites.towers.sprite_art import SpriteArt  # noqa: E402
from lindefense.ui.sprites.towers.suno_art import SunoArt  # noqa: E402
from lindefense.ui.sprites.towers.zethos_art import ZethosArt  # noqa: E402

TowerArtFactory.STAGE_FOR_TIER = [0, 2, 3, 4]
