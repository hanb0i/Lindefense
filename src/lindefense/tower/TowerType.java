package lindefense.tower;

/**
 * Identifiers for every playable unit: 17 Hero Store heroes and 18 standard towers (including Zethos, a Primary
 * tower), plus the internal DALL-E Sprite summon. Heroes are unlocked in the Hero Store, are never sold in the
 * regular tower shop, deploy free once per match and carry base + 3 purchasable upgrades like any other tower.
 * Display names are shown in the UI; descriptive nicknames are subtitles in the catalog.
 */
public enum TowerType {
    // Heroes (Hero Store only) -- base + 3 purchasable upgrades each
    LOBBER_LUIS("Lobber Luis", Faction.HERO, 0xffb02e, 0x3a2410),
    SAGE_AARAV("Sage Aarav", Faction.HERO, 0xffe9a8, 0xf3f6ff),
    IRON_IMRAAN("Iron Imraan", Faction.HERO, 0x9fb4cc, 0x2a3850),
    BOOM_SAM("Boom Sam", Faction.HERO, 0xff5a1f, 0x3a1206),
    CHILLSTIN("Chillstin", Faction.HERO, 0x8fe6ff, 0x1f5a7a),
    KAIJU_KAI("Kaiju Kai", Faction.HERO, 0x4ade80, 0x123a24),
    ABHI_ACE("Abhi-Ace", Faction.HERO, 0x5fd6ff, 0x1b3a66),
    ZIPPY_MATT("Zippy Matt", Faction.HERO, 0xffe94a, 0x3a3410),
    SUNNY_JOE("Sunny Joe", Faction.HERO, 0x46e08a, 0x0e2b1d),
    NIK_SCOPE("Nik-Scope", Faction.HERO, 0xff3b6e, 0x3a0f1e),
    CAMI_MINE("Cami-Mine", Faction.HERO, 0xff8a3b, 0x3a2010),
    JUSTIN_TIME("Justin Time", Faction.HERO, 0xb48cff, 0x2a1a50),
    SPEAR_HANBO("Spear Hanbo", Faction.HERO, 0xd8dee6, 0x33405a),
    THORN_TUHIN("Thorn Tuhin", Faction.HERO, 0x7dff8a, 0x14301a),
    TRAPPER_CHE("Trapper Che", Faction.HERO, 0x5fe0d0, 0x113a36),
    BLITZ_ARNAV("Blitz Arnav", Faction.HERO, 0x9dff3a, 0x16301a),
    TANIMBUS("Tanimbus", Faction.HERO, 0xff9ad5, 0x4a1f3a),
    MR_LINDEMANN("Mr. Lindemann", Faction.HERO, 0xf89820, 0x3a1d78),
    // Primary
    GEMINI("Gemini", Faction.PRIMARY, 0x4f7cff, 0x9b5cff),
    CLAUDE("Claude", Faction.PRIMARY, 0xe88a4a, 0xf3d9c4),
    GPT("GPT", Faction.PRIMARY, 0x10a37f, 0xffffff),
    ZETHOS("Zethos", Faction.PRIMARY, 0x9a6bff, 0x22e6ff),
    // Military
    DEEPSEEK("DeepSeek", Faction.MILITARY, 0x1f3b8f, 0x4d7cff),
    COPILOT("Copilot", Faction.MILITARY, 0x2f7fe0, 0xb8dcff),
    // Magic
    DALLE("DALL·E", Faction.MAGIC, 0xffb347, 0x5bc0eb),
    SORA("Sora", Faction.MAGIC, 0x8fd3ff, 0xffffff),
    SUNO("Suno", Faction.MAGIC, 0xff5fa2, 0xffd1e6),
    // Support
    GROK("Grok", Faction.SUPPORT, 0x151515, 0xff7a00),
    PERPLEXITY("Perplexity", Faction.SUPPORT, 0x20b2aa, 0xe0fffa),
    // Experimental Titans
    QWEN("Qwen", Faction.TITAN, 0x7b3fe4, 0xd9c6ff),
    LLAMA("Llama", Faction.TITAN, 0xf2c94c, 0x8a5a2b),
    MISTRAL("Mistral", Faction.TITAN, 0x2bb3a3, 0xd8fff6),
    COHERE("Cohere", Faction.TITAN, 0xff7f6e, 0xffe3de),
    GLM("GLM", Faction.TITAN, 0x19e6ff, 0x0a2a3a),
    KIMI("Kimi", Faction.TITAN, 0x3d3fa8, 0xc6c7ff),
    MINIMAX("MiniMax", Faction.TITAN, 0xe03131, 0xffd6d6),
    // Internal summon (not in shop)
    DALLE_SPRITE("Sprite", Faction.MAGIC, 0xffe08a, 0x5bc0eb);

    public final String displayName;
    public final Faction faction;
    public final int primaryRgb;
    public final int secondaryRgb;

    TowerType(String displayName, Faction faction, int primaryRgb, int secondaryRgb) {
        this.displayName = displayName; this.faction = faction;
        this.primaryRgb = primaryRgb; this.secondaryRgb = secondaryRgb;
    }

    public boolean isHero() { return faction == Faction.HERO; }
    public boolean isPurchasable() { return this != DALLE_SPRITE; }

    /** The Hero Store heroes in store order. */
    public static TowerType[] heroes() {
        java.util.List<TowerType> l = new java.util.ArrayList<>();
        for (TowerType t : values()) if (t.isHero()) l.add(t);
        return l.toArray(new TowerType[0]);
    }

    /** The regular tower shop's towers (everything purchasable except heroes) in shop order. */
    public static TowerType[] shopTowers() {
        java.util.List<TowerType> l = new java.util.ArrayList<>();
        for (TowerType t : values()) if (t.isPurchasable() && !t.isHero()) l.add(t);
        return l.toArray(new TowerType[0]);
    }

    /** Every placeable unit (heroes + shop towers) in catalog order. */
    public static TowerType[] purchasable() {
        TowerType[] all = values();
        TowerType[] out = new TowerType[all.length - 1];
        int i = 0;
        for (TowerType t : all) if (t.isPurchasable()) out[i++] = t;
        return out;
    }
}
