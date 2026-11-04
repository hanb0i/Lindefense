package lindefense.ui.sprites.towers;

import lindefense.tower.TowerType;

/** Maps each {@link TowerType} to its {@link TowerArt} class. */
public final class TowerArtFactory {
    private TowerArtFactory() { }

    /** Art stages used by the four game tiers 0-3: every upgrade is a visible jump and the last one is the dramatic stage 4. */
    private static final int[] STAGE_FOR_TIER = { 0, 2, 3, 4 };

    /** Maps a standard tower's game tier (0-3) to the art stage (0-4) that draws it. */
    public static int artStage(int gameTier) { return STAGE_FOR_TIER[Math.max(0, Math.min(3, gameTier))]; }

    /**
     * Art stage for a tower type: standard towers use {@link #artStage(int)}; Zethos's five tiers (0-4) are five
     * stages; a hero's four tiers map straight through, so every upgrade visibly changes its gear.
     */
    public static int artStage(TowerType type, int gameTier) {
        if (type != null && type.isHero()) return Math.max(0, Math.min(3, gameTier));   // heroes: one look per upgrade level
        if (type == TowerType.ZETHOS) return Math.max(0, Math.min(4, gameTier));
        return artStage(gameTier);
    }

    /**
     * Builds the body art for a tower.
     *
     * @param type tower type (null falls back to a generic bot)
     * @param tier art stage (0-4); use {@link #artStage} to convert a game tier
     * @param r    footprint radius in logical units
     */
    public static TowerArt create(TowerType type, int tier, double r) {
        if (type == null) return new GenericArt(TowerType.GPT, tier, r);
        if (type.isHero()) return new HeroArt(type, tier, r);
        switch (type) {
            case CLAUDE: return new ClaudeArt(type, tier, r);
            case GPT: return new GptArt(type, tier, r);
            case GEMINI: return new GeminiArt(type, tier, r);
            case DEEPSEEK: return new DeepSeekArt(type, tier, r);
            case COPILOT: return new CopilotArt(type, tier, r);
            case DALLE: return new DalleArt(type, tier, r);
            case SORA: return new SoraArt(type, tier, r);
            case SUNO: return new SunoArt(type, tier, r);
            case GROK: return new GrokArt(type, tier, r);
            case PERPLEXITY: return new PerplexityArt(type, tier, r);
            case QWEN: return new QwenArt(type, tier, r);
            case LLAMA: return new LlamaArt(type, tier, r);
            case MISTRAL: return new MistralArt(type, tier, r);
            case COHERE: return new CohereArt(type, tier, r);
            case GLM: return new GlmArt(type, tier, r);
            case KIMI: return new KimiArt(type, tier, r);
            case MINIMAX: return new MiniMaxArt(type, tier, r);
            case ZETHOS: return new ZethosArt(type, tier, r);
            case DALLE_SPRITE: return new SpriteArt(type, tier, r);
            default: return new GenericArt(type, tier, r);
        }
    }
}
