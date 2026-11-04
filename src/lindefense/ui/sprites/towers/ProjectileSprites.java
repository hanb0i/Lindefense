package lindefense.ui.sprites.towers;

import java.awt.Color;
import lindefense.combat.Projectile;
import lindefense.combat.VisualEvent;
import lindefense.tower.Tower;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.ui.sprites.Animated;
import lindefense.ui.sprites.towers.ProjectileSprite.Style;

/**
 * Factory for projectile sprites and attack effects. Every tower type gets a
 * distinct projectile family matching its attack concept (Claude lances, Llama
 * kinetic wads, MiniMax bouncing orbs, Suno notes, Kimi sniper rounds, Brad
 * command-energy spheres, Ronil meteors, Zethos quantum diamonds, ...) that scales up with tier.
 */
public final class ProjectileSprites {
    private ProjectileSprites() { }

    /**
     * Creates the sprite for a live projectile. Unknown or null sources fall
     * back to a plain glossy dot in the projectile's own colour.
     */
    public static ProjectileSprite create(Projectile p) {
        if (p == null) return new ProjectileSprite(Style.DOT, 0, 5, Color.WHITE, Color.WHITE);
        Tower src = p.getSource();
        TowerType type = src == null ? null : src.getType();
        int tier = src == null ? 0 : src.getTier();
        ProjectileSprite s = create(type, tier, p.getStats(), p.getSize(), p.getRgb());
        s.sync(p, 0);
        return s;
    }

    /**
     * Creates a projectile sprite from its parameters (also used by the gallery).
     *
     * @param type  source tower type, may be null
     * @param tier  source tier 0-4
     * @param stats stats of the shot (splash / pierce tune size), may be null
     * @param size  logical radius
     * @param rgb   the projectile's own colour, used for fallbacks and paint
     */
    public static ProjectileSprite create(TowerType type, int tier, TowerStats stats, double size, int rgb) {
        double sz = size;
        if (stats != null) {
            if (stats.splashRadius > 60) sz *= 1.2;
            if (stats.pierce >= 8) sz *= 1.1;
        }
        if (type == null) return new ProjectileSprite(Style.DOT, tier, sz, Art.rgb(rgb), Color.WHITE);
        Color pri = Art.rgb(type.primaryRgb), sec = Art.rgb(type.secondaryRgb);
        switch (type) {
            case CLAUDE: return new ProjectileSprite(Style.LANCE, tier, sz, pri, sec);
            case GPT: return new ProjectileSprite(Style.TOKEN, tier, sz, pri, sec);
            case GEMINI: return new ProjectileSprite(Style.SPARK, tier, sz, pri, sec);
            case DEEPSEEK: return new ProjectileSprite(Style.SLUG, tier, sz, pri, sec);
            case COPILOT: return new ProjectileSprite(Style.SNIPPET, tier, sz, pri, sec);
            case DALLE: return new ProjectileSprite(Style.PAINT, tier, sz, Art.rgb(rgb == 0 ? type.primaryRgb : rgb), sec);
            case DALLE_SPRITE: return new ProjectileSprite(Style.PAINT, 0, sz * 0.8, Art.rgb(0xff5fa2), sec);
            case SORA: return new ProjectileSprite(Style.PULSE, tier, sz, pri, sec);
            case SUNO: return new ProjectileSprite(Style.NOTE, tier, sz, pri, sec);
            case GROK: return new ProjectileSprite(Style.BOLT, tier, sz, pri, sec);
            case PERPLEXITY: return new ProjectileSprite(Style.PIN, tier, sz, pri, sec);
            case QWEN: return new ProjectileSprite(Style.BLADE, tier, sz, pri, sec);
            case LLAMA: return new ProjectileSprite(Style.WAD, tier, sz, pri, sec);
            case MISTRAL: return new ProjectileSprite(Style.GALE, tier, sz, pri, sec);
            case COHERE: return new ProjectileSprite(Style.SPARK, tier, sz, pri, sec);
            case GLM: return new ProjectileSprite(Style.PULSE, tier, sz, pri, sec);
            case KIMI: return new ProjectileSprite(Style.ROUND, tier, sz, pri, sec);
            case MINIMAX: return new ProjectileSprite(Style.ORB, tier, sz, pri, sec);
            case LOBBER_LUIS: return new ProjectileSprite(Style.METEOR, 2, sz, pri, sec);
            case BOOM_SAM: return new ProjectileSprite(Style.METEOR, 1, sz, pri, sec);
            case IRON_IMRAAN: return new ProjectileSprite(Style.COMMAND, 0, sz, pri, sec);
            case CHILLSTIN: return new ProjectileSprite(Style.CRYO, 1, sz, pri, sec);
            case KAIJU_KAI: return new ProjectileSprite(Style.COMMAND, 2, sz, pri, sec);
            case ABHI_ACE: return new ProjectileSprite(Style.DRONE, 1, sz, pri, sec);
            case NIK_SCOPE: return new ProjectileSprite(Style.VOLLEY, 2, sz, pri, sec);
            case BLITZ_ARNAV: return new ProjectileSprite(Style.VOLLEY, 0, sz, pri, sec);
            case SPEAR_HANBO: return new ProjectileSprite(Style.VOLLEY, 1, sz, pri, sec);
            case THORN_TUHIN: return new ProjectileSprite(Style.DATA, 1, sz, pri, sec);
            case JUSTIN_TIME: return new ProjectileSprite(Style.DATA, 0, sz, pri, sec);
            case CAMI_MINE: case TRAPPER_CHE: return new ProjectileSprite(Style.METEOR, 0, sz, pri, sec);
            case ZETHOS: return new ProjectileSprite(Style.QUANTUM, tier, sz, pri, sec);
            default: return new ProjectileSprite(Style.DOT, tier, sz, Art.rgb(rgb), Color.WHITE);
        }
    }

    /**
     * Builds a cartoon effect for a BEAM, CHAIN, HIT or EXPLOSION event.
     * Returns null for every other kind (the world view keeps its own handling
     * for text, banners, deaths and so on).
     */
    public static Animated createAttackEffect(VisualEvent ev) {
        if (ev == null || ev.kind == null) return null;
        switch (ev.kind) {
            case BEAM: return ev.a == null || ev.b == null ? null : new AttackEffects.Beam(ev);
            case CHAIN: return ev.a == null || ev.b == null ? null : new AttackEffects.Chain(ev);
            case HIT: return ev.a == null ? null : new AttackEffects.Hit(ev);
            case EXPLOSION: return ev.a == null ? null : new AttackEffects.Explosion(ev);
            default: return null;
        }
    }
}
