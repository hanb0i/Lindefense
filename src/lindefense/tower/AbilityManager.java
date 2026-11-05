package lindefense.tower;

import lindefense.combat.VisualEvent;
import lindefense.sim.Game;
import lindefense.sim.Vec;

/**
 * Enforces ability rules and delegates the effect to the tower's behaviour. Rules: a shop tower's ability is locked
 * until it is bought at max tier ({@link Tower#unlockAbility}) and is ready the moment it is bought; Zethos's ability
 * is usable from placement with its cooldown starting at 50%; cooldowns count down in game time (so they
 * speed up with fast-forward), Surveillance locks them, and abilities that need a location
 * ({@link AbilityDef#needsTarget}) are only activated through {@link #activate(Tower, Vec)}.
 */
public class AbilityManager {
    private final Game game;

    public AbilityManager(Game game) { this.game = game; }

    public boolean canActivate(Tower t) {
        return t != null && t.isAlive() && !t.isTemporary() && t.getAbility() != null && t.isAbilityReady();
    }

    /** Activates an ability that needs no location. Returns false for abilities that need one or are not ready. */
    public boolean activate(Tower t) {
        if (t != null && t.getAbility() != null && t.getAbility().needsTarget) return false;
        return activate(t, null);
    }

    /**
     * Activates the ability, passing the player-chosen map point (required if {@code needsTarget}, ignored
     * otherwise). The cooldown is spent only if the behaviour accepts the activation.
     */
    public boolean activate(Tower t, Vec target) {
        if (!canActivate(t)) return false;
        AbilityDef a = t.getAbility();
        if (a.needsTarget && target == null) return false;
        if (!t.getBehavior().activateAbility(game, t, a.needsTarget ? target : null)) return false;
        t.startAbilityCooldown();
        game.getEvents().add(VisualEvent.ability(t.getPosition(), Math.max(40, Math.min(300, t.effectiveRange(game))), t.getType().primaryRgb));
        game.getEvents().add(VisualEvent.text(t.getPosition(), a.name + "!", t.getType().primaryRgb));
        return true;
    }
}
