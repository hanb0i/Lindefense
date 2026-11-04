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
 * base + {@value #STANDARD_UPGRADES} upgrades; Zethos has {@value #ZETHOS_UPGRADES}. Only Zethos has an ability.
 */
public final class TowerCatalog {
    /** Upgrades of every standard shop tower. */
    public static final int STANDARD_UPGRADES = 3;
    /** Zethos's upgrade path (Quantum Acceleration .. Reality Engine). */
    public static final int ZETHOS_UPGRADES = 4;
    private static final Map<TowerType, TowerDef> DEFS = new EnumMap<>(TowerType.class);

    private TowerCatalog() { }

    public static TowerDef get(TowerType type) { return DEFS.get(type); }
    public static Map<TowerType, TowerDef> all() { return Collections.unmodifiableMap(DEFS); }

    /**
     * Whether a tower type keeps an active ability. Only Zethos (whose Reality Collapse is part of its
     * specification) has one; every other tower and hero is passive and progresses through purchasable upgrades.
     */
    public static boolean hasActiveAbility(TowerType type) { return type == TowerType.ZETHOS; }

    private static void register(Iterable<TowerDef> defs) {
        for (TowerDef d : defs) DEFS.put(d.type, hasActiveAbility(d.type) ? d : withoutAbility(d));
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
