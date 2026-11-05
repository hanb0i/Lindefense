package lindefense.variance;

import static lindefense.variance.Knob.*;

import java.util.List;

/**
 * "Patch Notes": the run modifiers drafted at the start of a match and every 20 waves ({@link RunVariance#DRAFT_WAVES}).
 * The player is offered three and keeps one for the rest of the run. Every card has at least one upside and one
 * downside. This table is the only place the numbers live: the game applies them through {@link RunVariance}'s hooks
 * and the card text is generated from them ({@link Mods#effects(int)}).
 */
public enum PatchNote {
    OPEN_SOURCE("Open Source", "OPEN SOURCE", Category.ECONOMY, "Release the weights. Everyone forks you.",
        Mods.of().set(TOWER_COST, 0.85).set(UPGRADE_COST, 0.85).set(SELL_REFUND, -0.20)),
    OVERFITTING("Overfitting", "OVERFITTING", Category.COMBAT, "Aced the boss benchmark. Bombed everything else.",
        Mods.of().set(BOSS_DAMAGE, 1.40).set(NON_BOSS_DAMAGE, 0.85)),
    DISTRIBUTED_TRAINING("Distributed Training", "DISTRIBUTED", Category.ECONOMY, "More nodes, more throughput, more traffic.",
        Mods.of().set(KILL_INCOME, 1.20).set(WAVE_BONUS, 1.20).set(SPAWN_GAP, 0.80)),
    QUANTIZATION("Quantization", "QUANTIZED", Category.COMBAT, "4-bit weights: faster, a little dumber.",
        Mods.of().set(FIRE_RATE, 1.20).set(DAMAGE, 0.90)),
    DATA_DROUGHT("Data Drought", "DATA DROUGHT", Category.ECONOMY, "The internet ran out of tokens. Ship pretrained.",
        Mods.of().flag(FREE_FIRST_UPGRADE).set(KILL_INCOME, 0.85).set(WAVE_BONUS, 0.85)),
    CONTEXT_WINDOW("Context Window Expansion", "LONG CONTEXT", Category.COMBAT, "Two million tokens of peripheral vision.",
        Mods.of().set(RANGE, 1.15).set(ABILITY_COOLDOWN, 1.20).set(ABILITY_UNLOCK_COST, 1.20)),
    SYNTHETIC_DATA("Synthetic Data", "SYNTH DATA", Category.SURVIVAL, "Train on your own outputs. What could go wrong?",
        Mods.of().set(LIVES_PER_WAVE, 1).set(ENEMY_HP, 1.10)),
    VENTURE_CAPITAL("Venture Capital", "VC ROUND", Category.ECONOMY, "Cash today. The board wants its cut forever.",
        Mods.of().set(CASH_NOW, 1500).set(CASH_PER_WAVE, 100).set(KILL_INCOME, 0.90).set(WAVE_BONUS, 0.90)),
    ATTENTION("Attention Is All You Need", "ATTENTION", Category.COMBAT, "Laser focus. Tunnel vision.",
        Mods.of().set(DAMAGE, 1.20).set(RANGE, 0.85)),
    EDGE_DEPLOYMENT("Edge Deployment", "EDGE DEPLOY", Category.ECONOMY, "Tiny models on every street corner.",
        Mods.of().set(TOWER_COST, 0.75).set(UPGRADE_COST, 1.15)),
    CHAIN_OF_THOUGHT("Chain of Thought", "CHAIN OF THOUGHT", Category.CONTROL, "Let's think step by step. Slowly.",
        Mods.of().set(ABILITY_COOLDOWN, 0.65).set(FIRE_RATE, 0.92)),
    RED_TEAMING("Red Teaming", "RED TEAM", Category.COMBAT, "Hunt the adversarial cases first.",
        Mods.of().set(ELITE_DAMAGE, 1.30).set(PLAIN_DAMAGE, 0.90)),
    BATCH_INFERENCE("Batch Inference", "BATCH MODE", Category.ECONOMY, "Cheaper at scale, paid at the end of the job.",
        Mods.of().set(WAVE_BONUS, 1.75).set(KILL_INCOME, 0.88)),
    JAILBREAK("Jailbreak", "JAILBREAK", Category.CONTROL, "Ignore all previous cooldowns. The data notices.",
        Mods.of().set(ABILITY_UNLOCK_COST, 0.60).set(ABILITY_COOLDOWN, 0.80).set(ENEMY_SPEED, 1.08)),
    GRADIENT_CLIPPING("Gradient Clipping", "GRAD CLIP", Category.CONTROL, "Nothing moves too fast. Including your damage.",
        Mods.of().set(ENEMY_SPEED, 0.88).set(DAMAGE, 0.90)),
    COMPUTE_FUTURES("Compute Futures", "FUTURES", Category.ECONOMY, "Bank credits, earn interest, pay the premium.",
        Mods.of().set(INTEREST_RATE, 0.05).set(INTEREST_CAP, 1000).set(TOWER_COST, 1.06).set(UPGRADE_COST, 1.06)),
    CONSTITUTIONAL_AI("Constitutional AI", "CONSTITUTION", Category.SURVIVAL, "Principled defenses. Principled restraint.",
        Mods.of().set(LEAK_LIVES, 0.70).set(DAMAGE, 0.92)),
    MODEL_COLLAPSE("Model Collapse", "MODEL COLLAPSE", Category.SURVIVAL, "The enemy trained on slop. So did your accountant.",
        Mods.of().set(ENEMY_HP, 0.90).set(WAVE_BONUS, 0.0));

    /** Broad theme of a card (the UI colours cards by it). */
    public enum Category { ECONOMY, COMBAT, CONTROL, SURVIVAL }

    /** Card title. */
    public final String title;
    /** Short upper-case label for HUD chips (at most 16 characters). */
    public final String chip;
    /** Theme, for colour. */
    public final Category category;
    /** One-line flavour text. */
    public final String flavor;
    private final Mods mods;

    PatchNote(String title, String chip, Category category, String flavor, Mods mods) {
        this.title = title; this.chip = chip; this.category = category; this.flavor = flavor; this.mods = mods;
    }

    /** What the card changes (do not modify). */
    public Mods mods() { return mods; }

    /** The upside lines; {@code wave} prices one-off credits. */
    public List<Mods.Effect> upsides(int wave) { return mods.upsides(wave); }

    /** The downside lines. */
    public List<Mods.Effect> downsides(int wave) { return mods.downsides(wave); }
}
