package lindefense.wave;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import lindefense.enemy.Modifier;

/**
 * Where Prompt Injection enemies ({@link Modifier#INJECTION}) appear in the base campaign. They debut on wave
 * {@value #FIRST_WAVE} and become more frequent and more numerous:
 * <ul>
 *   <li>waves 30-49: every fourth wave (30, 34, ...), 1 injector;</li>
 *   <li>waves 50-69: every even wave, 1 injector;</li>
 *   <li>waves 70-84: every wave, 2 injectors; waves 85-99: every wave, 3 injectors;</li>
 *   <li>never on a boss debut wave ({@link #BOSS_DEBUTS}: the first MOAB, BFB, ZOMG and DDT get the stage to
 *       themselves), and none on wave 100 (Palantir broadcasts its own injections).</li>
 * </ul>
 * Injectors are <b>converted</b>, not added: they are taken out of the wave's most numerous non-boss group (ties: the
 * tougher type) and spawn spread over that group's time window, so the wave's enemy total is unchanged. Higher
 * Difficulty Growth modes get more of them automatically, because {@code Difficulty.shape} multiplies the injector
 * group like any other group (up to x1.4 on O(N), x2.4 on O(N^2), x2.5 on O(N^N)); elites never gain the modifier at random.
 */
public final class InjectionSchedule {
    /** First wave with Prompt Injection enemies. */
    public static final int FIRST_WAVE = 30;
    /** Waves on which a boss class first appears (Bellarmine, SW Resource Consultant, 3Com, Lockheed Martin): no injectors. */
    public static final int[] BOSS_DEBUTS = { 40, 60, 80, 90 };

    private InjectionSchedule() { }

    /** Injectors in the base campaign on {@code wave} (0 = none). */
    public static int injectors(int wave) {
        if (wave < FIRST_WAVE || wave >= WaveData.WAVE_COUNT) return 0;
        for (int d : BOSS_DEBUTS) if (d == wave) return 0;
        if (wave < 50) return (wave - FIRST_WAVE) % 4 == 0 ? 1 : 0;
        if (wave < 70) return wave % 2 == 0 ? 1 : 0;
        return wave < 85 ? 2 : 3;
    }

    /**
     * Returns {@code w} with {@link #injectors(int)} enemies of its carrier group split off into a Prompt Injection
     * group (the same object if the wave has none or no suitable group). The debut wave's note introduces them.
     */
    static WaveDef apply(WaveDef w) {
        int want = injectors(w.number);
        int ci = carrierIndex(w.groups);
        if (want <= 0 || ci < 0) return w;
        SpawnGroup g = w.groups.get(ci);
        int k = Math.min(want, g.count - 1);
        EnumSet<Modifier> mods = EnumSet.copyOf(g.modifiers);
        mods.add(Modifier.INJECTION);
        double interval = g.interval * g.count / k;
        List<SpawnGroup> out = new ArrayList<>(w.groups);
        out.set(ci, new SpawnGroup(g.type, g.count - k, g.modifiers, g.interval, g.startDelay, g.route));
        out.add(new SpawnGroup(g.type, k, mods, interval, g.startDelay + interval * 0.5, g.route));
        String note = w.number == FIRST_WAVE
            ? (w.note == null ? "" : w.note + " ") + "Prompt Injection: an enemy holding an IGNORE PREVIOUS INSTRUCTIONS sign hijacks nearby towers (Claude, Copilot, DeepSeek, Perplexity and Mr. Lindemann are immune)."
            : w.note;
        return new WaveDef(w.number, note, out.toArray(new SpawnGroup[0]));
    }

    /** The group injectors are taken from: non-boss, at least 2 enemies, most enemies, then highest base HP; -1 if none. */
    static int carrierIndex(List<SpawnGroup> groups) {
        int best = -1;
        for (int i = 0; i < groups.size(); i++) {
            SpawnGroup g = groups.get(i);
            if (g.type.isBoss() || g.count < 2 || g.modifiers.contains(Modifier.INJECTION)) continue;
            if (best < 0) { best = i; continue; }
            SpawnGroup b = groups.get(best);
            if (g.count > b.count || g.count == b.count && g.type.baseHp > b.type.baseHp) best = i;
        }
        return best;
    }
}
