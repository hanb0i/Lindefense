package lindefense.tools;

import lindefense.ai.AttackerBot;
import lindefense.ai.DefenderProfile;
import lindefense.map.MapCatalog;
import lindefense.sim.Difficulty;

/**
 * Headless balance probe for reverse mode ("Adversarial Training"): scripted attackers ({@link AttackerBot}) against
 * the defender AI on every map and Difficulty Growth level, one line per match.
 *
 * <p>Usage: {@code java -cp build:lib/acm.jar lindefense.tools.ReverseProbe [style] [level] [map]} with style
 * PASSIVE / SPAM / REASONABLE (default REASONABLE), level O1 / ON / ON2 / ONN or ALL (default ALL) and a map index or
 * -1 for every map (default -1); {@code -Dprobe.seeds=K} runs K seeds per combination from {@code -Dprobe.seed=N};
 * {@code -Dprobe.push=S} / {@code -Dprobe.boss=F} change the reasonable bot's push size (seconds of income) and boss
 * share; {@code -Dprobe.trace=true} prints the economy every 30 s.</p>
 */
public final class ReverseProbe {
    private ReverseProbe() { }

    public static void main(String[] args) {
        System.setProperty("lindefense.nosound", "true");
        AttackerBot.Style style = args.length > 0 ? AttackerBot.Style.valueOf(args[0].toUpperCase()) : AttackerBot.Style.REASONABLE;
        Difficulty only = args.length > 1 && !args[1].equalsIgnoreCase("ALL") ? Difficulty.parse(args[1]) : null;
        int map = args.length > 2 ? Integer.parseInt(args[2]) : -1;
        int seeds = Integer.getInteger("probe.seeds", 1);
        long seed0 = Long.getLong("probe.seed", 77L);
        double push = Double.parseDouble(System.getProperty("probe.push", String.valueOf(AttackerBot.DEFAULT_PUSH_SECONDS)));
        double boss = Double.parseDouble(System.getProperty("probe.boss", String.valueOf(AttackerBot.DEFAULT_BOSS_SHARE)));
        for (Difficulty d : Difficulty.values()) {
            if (only != null && d != only) continue;
            int wins = 0, n = 0;
            for (int m = 0; m < MapCatalog.MAP_COUNT; m++) {
                if (map >= 0 && m != map) continue;
                for (int k = 0; k < seeds; k++) {
                    long t0 = System.currentTimeMillis();
                    lindefense.sim.Game g = lindefense.ai.ReverseMatch.create(m, seed0 + k, d);
                    AttackerBot.Outcome o = AttackerBot.play(g, new AttackerBot(g.getReverse(), style, push, boss), Boolean.getBoolean("probe.trace"));
                    n++;
                    if (o.attackerWon) wins++;
                    System.out.printf("[%-6s %-17s] %-24s seed %-4d %s  (%.1fs)%n", d.asciiLabel, DefenderProfile.of(d).displayName,
                        MapCatalog.create(m).getName(), seed0 + k, o, (System.currentTimeMillis() - t0) / 1000.0);
                }
            }
            System.out.printf("== %s %s: attacker won %d of %d%n", style, d.asciiLabel, wins, n);
        }
    }
}
