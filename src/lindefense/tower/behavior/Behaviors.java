package lindefense.tower.behavior;

import java.util.EnumMap;
import java.util.Map;
import lindefense.tower.TowerType;

/** Registry mapping every {@link TowerType} to its (stateless, shared) {@link TowerBehavior}. */
public final class Behaviors {
    private static final Map<TowerType, TowerBehavior> MAP = new EnumMap<>(TowerType.class);

    private Behaviors() { }

    public static TowerBehavior of(TowerType type) {
        TowerBehavior b = MAP.get(type);
        return b == null ? GENERIC : b;
    }

    private static final TowerBehavior GENERIC = new GenericBehavior();

    static {
        // Hero Store heroes (base + 3 upgrades each)
        MAP.put(TowerType.LOBBER_LUIS, new LobberLuisBehavior());
        MAP.put(TowerType.SAGE_AARAV, new SageAaravBehavior());
        MAP.put(TowerType.IRON_IMRAAN, new IronImraanBehavior());
        MAP.put(TowerType.BOOM_SAM, new BoomSamBehavior());
        MAP.put(TowerType.CHILLSTIN, new ChillstinBehavior());
        MAP.put(TowerType.KAIJU_KAI, new KaijuKaiBehavior());
        MAP.put(TowerType.ABHI_ACE, new AbhiAceBehavior());
        MAP.put(TowerType.ZIPPY_MATT, new ZippyMattBehavior());
        MAP.put(TowerType.SUNNY_JOE, new SunnyJoeBehavior());
        MAP.put(TowerType.NIK_SCOPE, new NikScopeBehavior());
        MAP.put(TowerType.CAMI_MINE, new CamiMineBehavior());
        MAP.put(TowerType.JUSTIN_TIME, new JustinTimeBehavior());
        MAP.put(TowerType.SPEAR_HANBO, new SpearHanboBehavior());
        MAP.put(TowerType.THORN_TUHIN, new ThornTuhinBehavior());
        MAP.put(TowerType.TRAPPER_CHE, new TrapperCheBehavior());
        MAP.put(TowerType.BLITZ_ARNAV, new BlitzArnavBehavior());
        MAP.put(TowerType.TANIMBUS, new TanimbusBehavior());
        MAP.put(TowerType.MR_LINDEMANN, new MrLindemannBehavior());
        // Primary (B1)
        MAP.put(TowerType.GEMINI, new GeminiBehavior());
        MAP.put(TowerType.CLAUDE, new ClaudeBehavior());
        MAP.put(TowerType.GPT, new GptBehavior());
        MAP.put(TowerType.ZETHOS, new ZethosBehavior());
        // Military (B1)
        MAP.put(TowerType.DEEPSEEK, new DeepSeekBehavior());
        MAP.put(TowerType.COPILOT, new CopilotBehavior());
        // Magic (B2)
        MAP.put(TowerType.DALLE, new DalleBehavior());
        MAP.put(TowerType.SORA, new SoraBehavior());
        MAP.put(TowerType.SUNO, new SunoBehavior());
        // Support (B2)
        MAP.put(TowerType.GROK, new GrokBehavior());
        MAP.put(TowerType.PERPLEXITY, new PerplexityBehavior());
        // Titans (B3)
        MAP.put(TowerType.QWEN, new QwenBehavior());
        MAP.put(TowerType.LLAMA, new LlamaBehavior());
        MAP.put(TowerType.MISTRAL, new MistralBehavior());
        MAP.put(TowerType.COHERE, new CohereBehavior());
        MAP.put(TowerType.GLM, new GlmBehavior());
        MAP.put(TowerType.KIMI, new KimiBehavior());
        MAP.put(TowerType.MINIMAX, new MiniMaxBehavior());
    }
}
