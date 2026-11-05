package lindefense.tower;

import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;
import lindefense.combat.DamageType;
import lindefense.tower.data.HeroTowers;
import lindefense.tower.data.MagicTowers;
import lindefense.tower.data.MilitaryTowers;
import lindefense.tower.data.PrimaryTowers;
import lindefense.tower.data.SupportTowers;
import lindefense.tower.data.TitanTowers;
import lindefense.tower.data.TowerBuilder;

/**
 * Central tower registry. The numbers live in the per-faction data files in {@code tower/data}
 * ({@link HeroTowers}, {@link PrimaryTowers}, {@link MilitaryTowers}, {@link MagicTowers}, {@link SupportTowers},
 * {@link TitanTowers}), transcribed from the tower specification. Standard shop towers and Hero Store heroes are
 * base + {@value #STANDARD_UPGRADES} upgrades; Zethos has {@value #ZETHOS_UPGRADES}.
 *
 * <p>Abilities: every standard shop tower has an overpowered active ability that is locked until the tower is fully
 * upgraded and the player pays {@value #ABILITY_UNLOCK_COST} for it ({@link Tower#unlockAbility}). Zethos's Reality
 * Collapse is part of its own specification and is usable from placement. Heroes have no abilities.</p>
 */
public final class TowerCatalog {
    /** Upgrades of every standard shop tower. */
    public static final int STANDARD_UPGRADES = 3;
    /** Zethos's upgrade path (Quantum Acceleration .. Reality Engine). */
    public static final int ZETHOS_UPGRADES = 4;
    /** Price of unlocking a shop tower's ability, available once the tower has every upgrade. */
    public static final int ABILITY_UNLOCK_COST = 15_000;
    private static final Map<TowerType, TowerDef> DEFS = new EnumMap<>(TowerType.class);

    private TowerCatalog() { }

    public static TowerDef get(TowerType type) { return DEFS.get(type); }
    public static Map<TowerType, TowerDef> all() { return Collections.unmodifiableMap(DEFS); }

    /** Whether a tower type has an active ability at all (every shop tower and Zethos; heroes are passive). */
    public static boolean hasActiveAbility(TowerType type) { return !type.isHero() && get(type) != null && get(type).ability != null; }

    /** Whether a tower type's ability must be bought at max tier for {@link #ABILITY_UNLOCK_COST} (all but Zethos). */
    public static boolean abilityNeedsUnlock(TowerType type) { return type != TowerType.ZETHOS && !type.isHero(); }

    /**
     * Whether a tower type is immune to prompt injection (the {@link TowerStats#injectionImmune} flag set in its data
     * file): Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann. Immune towers are never hijacked and never
     * disabled by a hijacked neighbour; Copilot additionally shields the towers in its tether radius.
     */
    public static boolean isInjectionImmune(TowerType type) {
        TowerDef d = get(type);
        return d != null && d.baseStats.injectionImmune;
    }

    /** The one-line reason a tower type is immune to prompt injection, or null if it is not. */
    public static String injectionImmunityReason(TowerType type) {
        return isInjectionImmune(type) ? get(type).baseStats.injectionImmuneReason : null;
    }

    /** Whether a tower type's aura shields other towers from prompt injection (Copilot's firewall). */
    public static boolean grantsInjectionFirewall(TowerType type) {
        TowerDef d = get(type);
        return d != null && d.baseStats.auraInjectionImmunity;
    }

    private static void register(Iterable<TowerDef> defs) {
        for (TowerDef d : defs) DEFS.put(d.type, d.type.isHero() ? withoutAbility(d) : d);
    }

    /** The same definition with its active ability removed. */
    private static TowerDef withoutAbility(TowerDef d) {
        return new TowerDef(d.type, d.subtitle, d.description, d.baseCost, d.radius, d.baseStats, d.upgrades, null, d.tierLabels,
            d.unlockCost, d.defaultTargeting);
    }

    static {
        register(HeroTowers.all());
        register(PrimaryTowers.all());
        register(MilitaryTowers.all());
        register(MagicTowers.all());
        register(SupportTowers.all());
        register(TitanTowers.all());
        // Internal placeholder kept so tooling that iterates TowerType.values() keeps working; never purchasable.
        DEFS.put(TowerType.DALLE_SPRITE, TowerBuilder.of(TowerType.DALLE_SPRITE, "Illustrated creature", 0)
            .description("Internal. DALL-E creatures are track walkers now, not towers.")
            .tiers("Sprite", "Sprite", "Sprite", "Sprite")
            .attack(AttackKind.NONE, DamageType.MAGIC, 100, 1.0, 1, 1)
            .upgrade(0, null, "None.", s -> { })
            .upgrade(0, null, "None.", s -> { })
            .upgrade(0, null, "None.", s -> { })
            .build());
    }
}
