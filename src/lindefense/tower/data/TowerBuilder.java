package lindefense.tower.data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import lindefense.combat.DamageType;
import lindefense.tower.AbilityDef;
import lindefense.tower.AttackKind;
import lindefense.tower.Targeting;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.UpgradeDef;

/**
 * Fluent builder used by the per-faction data files. A tower is: identity and cost, one tier label per state, base
 * attack stats, its upgrades (cost, mechanic name, description, stat mutation; three for standard towers, four for
 * Zethos, none for heroes) and one ability. Heroes also carry a Hero Store {@link #unlockCost}.
 * Upgrade names are the tier labels (model names / hero tier names), as the UI shows them.
 * <p>All numbers belong in the stat lambdas ({@code s.set("burnDps", 1)} for mechanic parameters) -- never in
 * behaviour code.</p>
 */
public final class TowerBuilder {
    private final TowerType type;
    private final String subtitle;
    private final int cost;
    private String description = "";
    private String[] tiers;
    private final TowerStats base = new TowerStats();
    private final List<UpgradeDef> upgrades = new ArrayList<>();
    private AbilityDef ability;
    private double radius = 20;
    private int unlockCost;
    private Targeting targeting = Targeting.FIRST;

    private TowerBuilder(TowerType type, String subtitle, int cost) { this.type = type; this.subtitle = subtitle; this.cost = cost; }

    /** Starts a tower: the spec's nickname is the subtitle, {@code cost} is the base purchase price. */
    public static TowerBuilder of(TowerType type, String subtitle, int cost) { return new TowerBuilder(type, subtitle, cost); }

    public TowerBuilder description(String d) { this.description = d; return this; }

    /** The tier labels: base, then one per upgrade in purchase order (heroes: just the base label). */
    public TowerBuilder tiers(String... labels) { this.tiers = labels.clone(); return this; }

    /** Hero Store price that permanently unlocks this hero. */
    public TowerBuilder unlockCost(int cost) { this.unlockCost = cost; return this; }

    /** Targeting priority a freshly placed copy starts with (default First). */
    public TowerBuilder targeting(Targeting t) { this.targeting = t; return this; }

    /** Core base attack: kind, damage type, range, interval (seconds), damage, pierce. */
    public TowerBuilder attack(AttackKind kind, DamageType dt, double range, double interval, double damage, int pierce) {
        base.kind = kind; base.hit.type = dt; base.range = range; base.interval(interval); base.hit.damage = damage; base.pierce = pierce;
        return this;
    }

    /** Further base-stat edits (projectile speed, splash, auras, parameters, ...). */
    public TowerBuilder base(Consumer<TowerStats> f) { f.accept(base); return this; }

    /** Adds the next upgrade (in purchase order; one per tier label after the base). {@code mechanic} is the spec's name for the effect, or null. */
    public TowerBuilder upgrade(int upCost, String mechanic, String desc, Consumer<TowerStats> f) {
        int i = upgrades.size();
        if (tiers == null) throw new IllegalStateException(type + ": call tiers() before upgrade()");
        if (i + 1 >= tiers.length) throw new IllegalStateException(type + ": more upgrades than tier labels");
        upgrades.add(new UpgradeDef(tiers[i + 1], upCost, mechanic == null || mechanic.isEmpty() ? desc : mechanic + ": " + desc, f));
        return this;
    }

    public TowerBuilder ability(AbilityBuilder a) { this.ability = a.build(); return this; }

    public TowerBuilder radius(double r) { this.radius = r; return this; }

    /**
     * Marks the tower as immune to prompt injection at every tier (it is never hijacked or disabled by a hijacked
     * neighbour). {@code why} is the one-line reason shown in the info panel and the catalog.
     */
    public TowerBuilder injectionImmune(String why) {
        base.injectionImmune = true;
        base.injectionImmuneReason = why;
        return this;
    }

    public TowerDef build() {
        return new TowerDef(type, subtitle, description, cost, radius, base, upgrades.toArray(new UpgradeDef[0]), ability, tiers,
            unlockCost, targeting);
    }

    /** Ability builder: name, cooldown (game seconds), description, optional target flag and named parameters. */
    public static final class AbilityBuilder {
        private final String name, desc;
        private final double cooldown;
        private boolean needsTarget;
        private final Map<String, Double> params = new LinkedHashMap<>();

        private AbilityBuilder(String name, double cooldown, String desc) { this.name = name; this.cooldown = cooldown; this.desc = desc; }

        public static AbilityBuilder of(String name, double cooldown, String desc) { return new AbilityBuilder(name, cooldown, desc); }
        /** The player must choose a map point. */
        public AbilityBuilder target() { needsTarget = true; return this; }
        public AbilityBuilder p(String key, double value) { params.put(key, value); return this; }
        AbilityDef build() { return new AbilityDef(name, desc, cooldown, needsTarget, params); }
    }
}
