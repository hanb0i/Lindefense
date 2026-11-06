"""Maps every TowerType to its (stateless, shared) behaviour."""
from lindefense.tower.tower_type import TowerType

_MAP = {}
_GENERIC = None


def _ensure():
    global _GENERIC
    if _MAP:
        return
    from lindefense.tower.behavior.base import GenericBehavior
    from lindefense.tower.behavior import heroes as h
    from lindefense.tower.behavior import primary as p
    from lindefense.tower.behavior import military_magic as mm
    from lindefense.tower.behavior import support_titans as st
    T = TowerType
    _GENERIC = GenericBehavior()
    _MAP.update({
        T.LOBBER_LUIS: h.LobberLuisBehavior(), T.SAGE_AARAV: h.SageAaravBehavior(), T.IRON_IMRAAN: h.IronImraanBehavior(),
        T.BOOM_SAM: h.BoomSamBehavior(), T.CHILLSTIN: h.ChillstinBehavior(), T.KAIJU_KAI: h.KaijuKaiBehavior(),
        T.ABHI_ACE: h.AbhiAceBehavior(), T.ZIPPY_MATT: h.ZippyMattBehavior(), T.SUNNY_JOE: h.SunnyJoeBehavior(),
        T.NIK_SCOPE: h.NikScopeBehavior(), T.CAMI_MINE: h.CamiMineBehavior(), T.JUSTIN_TIME: h.JustinTimeBehavior(),
        T.SPEAR_HANBO: h.SpearHanboBehavior(), T.THORN_TUHIN: h.ThornTuhinBehavior(), T.TRAPPER_CHE: h.TrapperCheBehavior(),
        T.BLITZ_ARNAV: h.BlitzArnavBehavior(), T.TANIMBUS: h.TanimbusBehavior(), T.MR_LINDEMANN: h.MrLindemannBehavior(),
        T.GEMINI: p.GeminiBehavior(), T.CLAUDE: p.ClaudeBehavior(), T.GPT: p.GptBehavior(), T.ZETHOS: p.ZethosBehavior(),
        T.DEEPSEEK: mm.DeepSeekBehavior(), T.COPILOT: mm.CopilotBehavior(),
        T.DALLE: mm.DalleBehavior(), T.SORA: mm.SoraBehavior(), T.SUNO: mm.SunoBehavior(),
        T.GROK: st.GrokBehavior(), T.PERPLEXITY: st.PerplexityBehavior(),
        T.QWEN: st.QwenBehavior(), T.LLAMA: st.LlamaBehavior(), T.MISTRAL: st.MistralBehavior(),
        T.COHERE: st.CohereBehavior(), T.GLM: st.GlmBehavior(), T.KIMI: st.KimiBehavior(), T.MINIMAX: st.MiniMaxBehavior(),
    })


def behavior_of(type_):
    _ensure()
    return _MAP.get(type_, _GENERIC)
