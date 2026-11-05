package lindefense.ui;

import static lindefense.tower.TowerStats.toUnits;

import java.util.ArrayList;
import java.util.List;
import lindefense.sim.Game;
import lindefense.tower.AbilityDef;
import lindefense.tower.AttackKind;
import lindefense.tower.Tower;
import lindefense.tower.TowerCatalog;
import lindefense.tower.TowerDef;
import lindefense.tower.TowerStats;
import lindefense.tower.TowerType;
import lindefense.tower.behavior.KaijuKaiBehavior;
import lindefense.tower.behavior.TanimbusBehavior;
import lindefense.tower.behavior.ZethosBehavior;

/**
 * Text for the Hero Store cards and the info panel of the Hero Store heroes and Zethos. Every number is read from the
 * data table (never typed here), and distances are shown in the specification's map units.
 */
public final class HeroStatText {
    private HeroStatText() { }

    /** Whether a type's stats are specified in map units (heroes and Zethos). */
    public static boolean usesUnits(TowerType t) { return t.isHero() || t == TowerType.ZETHOS; }

    /** Range label: "220" px for standard towers, "55u" for heroes and Zethos. */
    public static String range(TowerType t, double px) {
        return usesUnits(t) ? Ui.fmt(toUnits(px)) + "u" : String.valueOf((int) px);
    }

    private static String u(double px) { return Ui.fmt(toUnits(px)); }

    /** Combat role line ("Explosive Artillery"). */
    public static String role(TowerType t) { return TowerCatalog.get(t).subtitle; }

    /** Name of the primary attack: a hero's base tier label is the name of what it does. */
    public static String attackName(TowerType t) {
        TowerDef d = TowerCatalog.get(t);
        return d == null || d.tierLabels.length == 0 ? "Attack" : d.tierLabels[0];
    }

    /** Statistics of a hero at one tier, two to three short lines. */
    public static List<String> attackLines(TowerType t) { return attackLines(t, 0); }

    /** Statistics at the given tier (0 = base), so the store can preview what an upgrade changes. */
    public static List<String> attackLines(TowerType t, int tier) {
        TowerDef d = TowerCatalog.get(t);
        TowerStats s = d.statsForTier(tier);
        List<String> l = new ArrayList<>();
        // ---- support heroes describe what they give, not what they shoot
        if (s.p("healAmount", 0) > 0) {
            l.add("Restores " + (int) s.p("healAmount") + " integrity  •  every " + Ui.fmt(s.p("healInterval")) + "s");
            l.add("Aura " + u(s.fieldRadius) + "u  •  never above your starting maximum");
            if (s.p("emergencyRestore", 0) > 0) {
                l.add("Once per match: +" + pct(s.p("emergencyRestore")) + " max integrity below " + pct(s.p("emergencyThreshold")));
            }
            return l;
        }
        if (s.p("income", 0) > 0) {
            l.add("$" + (int) s.p("income") + "  •  every " + Ui.fmt(s.p("incomeInterval")) + "s  •  never attacks");
            l.add(s.p("bonus", 0) > 0
                ? "Bonus $" + (int) s.p("bonus") + " every " + Ui.fmt(s.p("bonusInterval")) + "s"
                : "Paid straight into your balance  •  $" + (int) (s.p("income") * 6) + " per minute");
            return l;
        }
        if (t == TowerType.TANIMBUS) {
            boolean single = s.p("singleTarget", 0) > 0;
            l.add((single ? "Strongest tower in " : "All towers in ") + u(s.auraRange) + "u  •  flying");
            l.add("+" + pct(single ? s.p("buffRate") : s.auraRate) + " attack speed"
                + (s.auraRangeBonus > 0 ? "  •  +" + pct(s.auraRangeBonus) + " range" : ""));
            if (s.p("rallyInterval", 0) > 0) {
                l.add("Every " + Ui.fmt(s.p("rallyInterval")) + "s: +" + pct(s.p("rallyRate")) + " to every tower for " + Ui.fmt(s.p("rallyDuration")) + "s");
            }
            return l;
        }
        if (s.p("maxMines", 0) > 0 || s.p("maxTraps", 0) > 0) {
            boolean trap = s.p("maxTraps", 0) > 0;
            int max = trap ? s.pi("maxTraps") : s.pi("maxMines");
            l.add(max + (trap ? " traps" : " mines") + " x " + Ui.fmt(s.hit.damage) + " dmg  •  one every " + Ui.fmt(s.interval()) + "s");
            l.add("Blast " + u(trap ? s.p("trapRadius") : s.p("mineRadius")) + "u  •  range " + u(s.range) + "u");
            if (trap) {
                l.add("Holds normals " + Ui.fmt(s.p("holdDuration")) + "s  •  bosses take damage only"
                    + (s.p("tetherDps", 0) > 0 ? "  •  " + Ui.fmt(s.p("tetherDps")) + "/s while held" : ""));
            } else if (s.hit.slowFraction > 0) {
                l.add("Slows " + pct(s.hit.slowFraction) + " for " + Ui.fmt(s.hit.slowDuration) + "s"
                    + (s.p("secondaryChance", 0) > 0 ? "  •  " + pct(s.p("secondaryChance")) + " second blast" : ""));
            }
            return l;
        }
        // ---- attackers: core line plus whatever is distinctive
        if (s.p("beamDuration", 0) > 0) {
            l.add(Ui.fmt(s.p("beamDamage")) + " dmg per tick  •  beam " + Ui.fmt(s.p("beamDuration")) + "s  •  range " + u(s.range) + "u");
            l.add("Burns everything along its path  •  every " + Ui.fmt(s.interval()) + "s");
        } else {
            String core = Ui.fmt(s.hit.damage) + " dmg  •  every " + Ui.fmt(s.interval()) + "s  •  range " + u(s.range) + "u";
            l.add(core);
            List<String> bits = new ArrayList<>();
            if (s.splashRadius > 0) bits.add("splash " + u(s.splashRadius) + "u");
            if (s.pierce > 1) bits.add("pierce " + s.pierce);
            if (s.chainHops > 0) bits.add("chains " + (s.chainHops + 1) + " targets");
            if (s.targets > 1) bits.add(s.pi("bullets", s.targets) + (t == TowerType.BLITZ_ARNAV ? " bullets" : " shots") + " per attack");
            if (s.projectilesPerShot > 1) bits.add(s.projectilesPerShot + " spears");
            if (s.hit.knockback > 0) bits.add("knockback");
            if (s.seesCamo) bits.add("sees camo");
            if (s.ignoresLos) bits.add("flying");
            if (!bits.isEmpty()) l.add(join(bits));
        }
        List<String> extra = new ArrayList<>();
        if (s.hit.slowFraction > 0) extra.add("slow " + pct(s.hit.slowFraction) + " for " + Ui.fmt(s.hit.slowDuration) + "s");
        if (s.hit.dotDps > 0) extra.add("poison " + Ui.fmt(s.hit.dotDps) + "/s for " + Ui.fmt(s.hit.dotDuration) + "s");
        if (s.p("critChance", 0) > 0) extra.add(pct(s.p("critChance")) + " crit x" + Ui.fmt(s.p("critMult")));
        if (s.p("clusterBombs", 0) > 0) extra.add(s.pi("clusterBombs") + " bomblets x " + Ui.fmt(s.p("clusterDamage")));
        if (s.p("freezeChance", 0) > 0) extra.add(pct(s.p("freezeChance")) + " freeze every " + s.pi("freezeEvery"));
        if (s.p("vineDps", 0) > 0) extra.add("vines " + Ui.fmt(s.p("vineDps")) + "/s every " + Ui.fmt(s.p("vineInterval")) + "s");
        if (s.p("fieldSlow", 0) > 0) extra.add("field " + pct(s.p("fieldSlow")) + " every " + Ui.fmt(s.p("fieldInterval")) + "s");
        if (s.p("blastDamage", 0) > 0) extra.add("blast " + Ui.fmt(s.p("blastDamage")) + " every " + Ui.fmt(s.p("blastInterval")) + "s");
        if (s.p("bombDamage", 0) > 0) extra.add("bombing run " + Ui.fmt(s.p("bombDamage")) + " every " + Ui.fmt(s.p("bombInterval")) + "s");
        if (s.p("nukeDamage", 0) > 0) extra.add("nuke " + Ui.fmt(s.p("nukeDamage")) + " every " + s.pi("nukeEvery"));
        if (s.p("smashDamage", 0) > 0) extra.add("smash " + Ui.fmt(s.p("smashDamage")) + " every " + s.pi("smashEvery"));
        if (s.p("rocketDamage", 0) > 0) extra.add("rocket " + Ui.fmt(s.p("rocketDamage")) + " every " + s.pi("rocketEvery"));
        if (s.p("returns", 0) > 0) extra.add("returns through the line");
        if (!extra.isEmpty()) l.add(join(extra));
        return l;
    }

    private static String join(List<String> parts) { return String.join("  •  ", parts); }

    private static String pct(double f) { return Math.round(f * 100) + "%"; }

    /**
     * Live status line for a placed hero / Zethos (beams, planted devices, supported towers), or null if there is
     * nothing to say right now.
     */
    public static String liveLine(Game game, Tower t) {
        TowerType ty = t.getType();
        TowerStats s = t.getStats();
        switch (ty) {
            case ZETHOS: {
                AbilityDef a = t.getAbility();
                if (a == null || !ZethosBehavior.isCollapsing(t)) return null;
                return "REALITY COLLAPSE " + Math.round(t.selfBuffRemaining(ZethosBehavior.COLLAPSE)) + "s: x" + Ui.fmt(a.p("damageMult"))
                    + " damage, x" + Ui.fmt(a.p("rateMult")) + " speed, +" + u(a.p("rangeBonus")) + "u range, " + (int) a.p("bounces") + " bounces";
            }
            case KAIJU_KAI:
                return KaijuKaiBehavior.isBeaming(t) ? "ATOMIC BREATH burning everything on the beam" : null;
            case CAMI_MINE:
                return "Mines armed: " + game.getEffects().minesOf(t, "mine").size() + " / " + s.pi("maxMines");
            case TRAPPER_CHE:
                return "Traps set: " + game.getEffects().minesOf(t, "trap").size() + " / " + s.pi("maxTraps");
            case THORN_TUHIN: {
                int vines = game.getEffects().zonesOf(t, "vines").size();
                return vines > 0 ? "Vines growing: " + vines + " / " + s.pi("maxVines", 2) : null;
            }
            case TANIMBUS: {
                Tower sup = TanimbusBehavior.supported(game, t);
                if (sup != null) return "Boosting " + sup.getType().displayName + " (+" + pct(s.p("buffRate")) + " attack speed)";
                return s.p("singleTarget", 0) > 0 ? "No tower in range to boost" : null;
            }
            case SAGE_AARAV:
                return "Integrity " + game.getLives() + " / " + game.getMaxLives();
            case MR_LINDEMANN: {
                double left = lindefense.tower.behavior.MrLindemannBehavior.warpRemaining(t);
                int holes = game.getEffects().zonesOf(t, lindefense.tower.behavior.MrLindemannBehavior.HOLE).size();
                return (left <= 0 ? "Space warp ready" : "Space warp in " + (int) Math.ceil(left) + "s") + "  •  singularities " + holes + " / " + s.pi("maxHoles", 3);
            }
            default:
                return null;
        }
    }

    /** True when the hero never attacks (the UI hides damage-style stats for these). */
    public static boolean isSupportHero(TowerType t) {
        TowerDef d = TowerCatalog.get(t);
        return d != null && d.baseStats.kind == AttackKind.NONE;
    }
}
