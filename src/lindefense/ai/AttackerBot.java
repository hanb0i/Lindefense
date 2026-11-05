package lindefense.ai;

import java.util.EnumSet;
import lindefense.enemy.Enemy;
import lindefense.enemy.Modifier;
import lindefense.sim.Game;

/**
 * A scripted reverse-mode attacker for tests, balance probes and the demo. Call {@link #tick(double)} once per fixed
 * step; it decides twice a game second.
 *
 * <ul>
 *   <li>{@link Style#PASSIVE}: never sends anything (the defender must win).</li>
 *   <li>{@link Style#SPAM}: only ever floods the cheapest unit, no modifiers, exploits or investment (a weak attacker).</li>
 *   <li>{@link Style#REASONABLE}: invests in SCALE COMPUTE early, then saves about 75 s of income and spends it in one
 *       push down the least-defended lane: the biggest affordable bosses first (up to 80%), then the strongest regular
 *       units (Camo while the AI has no detection, Regrow, later Fortified). Backs bosses with Overclock / Hotfix /
 *       Zero-Day and dumps everything in the last 40 s.</li>
 * </ul>
 */
public final class AttackerBot {
    /** Attacker behaviour. */
    public enum Style { PASSIVE, SPAM, REASONABLE }

    private final ReverseMatch match;
    private final Style style;
    private final double pushSeconds, bossShare;
    private double timer;

    /** A bot of the given style playing the attacker side of {@code match}, with the default push size and boss share. */
    public AttackerBot(ReverseMatch match, Style style) { this(match, style, DEFAULT_PUSH_SECONDS, DEFAULT_BOSS_SHARE); }

    /**
     * A bot whose {@link Style#REASONABLE} pushes save {@code pushSeconds} of income and spend up to {@code bossShare}
     * of each push on bosses.
     */
    public AttackerBot(ReverseMatch match, Style style, double pushSeconds, double bossShare) {
        this.match = match;
        this.style = style;
        this.pushSeconds = pushSeconds;
        this.bossShare = bossShare;
    }

    /** The bot's behaviour. */
    public Style getStyle() { return style; }

    /** Advances the bot by one step of {@code dt} game seconds (decides every 0.5 s). */
    public void tick(double dt) {
        timer -= dt;
        if (timer > 0) return;
        timer = 0.5;
        Game g = match.getGame();
        if (g.getState() != Game.State.PLAYING || g.getLives() <= 0 || match.isUplinkClosed()) return;
        switch (style) {
            case SPAM: match.send(AttackUnit.PRIMITIVE, null, 10, -1); break;
            case REASONABLE: reasonable(); break;
            default: break;
        }
    }

    private void reasonable() {
        double t = match.getElapsed();
        // 1. invest early: SCALE COMPUTE pays for itself in about 75-150 s
        if (t < 240 && match.getComputeLevel() < 4 && match.computeProblem() == null) { match.scaleCompute(); return; }
        exploits();
        // 2. save, then push: a push spends everything at once (concentration beats a trickle), down the weakest lane
        boolean lastCall = t > ReverseMatch.DURATION - 40;
        double threshold = Math.max(400, match.incomeRate() * pushSeconds);
        if (match.getCredits() < threshold && !lastCall) return;
        EnumSet<Modifier> mods = EnumSet.noneOf(Modifier.class);
        if (match.isUnlocked(Modifier.CAMO) && !match.getAI().hasDetection()) mods.add(Modifier.CAMO);
        if (match.isUnlocked(Modifier.REGROW)) mods.add(Modifier.REGROW);
        if (match.isUnlocked(Modifier.FORTIFIED) && t > 360) mods.add(Modifier.FORTIFIED);
        int lane = weakestLane();
        // bosses take up to 70% of the push: the biggest ones that fit, then smaller ones
        double bossBudget = match.getCredits() * bossShare;
        for (int i = AttackUnit.values().length - 1; i >= 0; i--) {
            AttackUnit u = AttackUnit.values()[i];
            if (!u.isBoss() || !match.isUnlocked(u)) continue;
            int p = match.price(u, mods, 1);
            int n = (int) (bossBudget / p);
            if (n > 0) bossBudget -= p * match.send(u, mods, n, lane);
        }
        // the rest: the strongest regular unit, then the next ones down, until the credits run out
        for (int i = AttackUnit.values().length - 1; i >= 0 && match.getQueued() < ReverseMatch.MAX_QUEUE; i--) {
            AttackUnit u = AttackUnit.values()[i];
            if (u.isBoss() || !match.isUnlocked(u)) continue;
            int n = (int) (match.getCredits() / match.price(u, mods, 1));
            if (n > 0) match.send(u, mods, Math.min(n, 30), lane);
        }
    }

    /** Default seconds of income saved before each push. */
    public static final double DEFAULT_PUSH_SECONDS = 75;
    /** Default share of a push spent on bosses. */
    public static final double DEFAULT_BOSS_SHARE = 0.8;

    /** The lane the defence covers least (tower range x tier over track samples); -1 on single-lane maps. */
    private int weakestLane() {
        java.util.List<lindefense.map.Path> routes = match.getGame().getMap().getRoutes();
        if (routes.size() < 2) return -1;
        int best = -1; double bestCover = Double.MAX_VALUE;
        for (int r = 0; r < routes.size(); r++) {
            lindefense.map.Path p = routes.get(r);
            double cover = 0;
            for (double d = 0; d < p.getTotalLength(); d += 40) {
                lindefense.sim.Vec v = p.positionAt(d);
                for (lindefense.tower.Tower tw : match.getGame().getTowerManager().getPlayerTowers()) {
                    double range = tw.getStats().range;
                    if (range >= 1000 || tw.getPosition().distSq(v) <= range * range) cover += 1 + tw.getTier();
                }
            }
            cover /= Math.max(1, p.getTotalLength());
            if (cover < bestCover) { bestCover = cover; best = r; }
        }
        return best;
    }

    /** Overclock a boss past the first third of the track, Hotfix damaged bosses, Zero-Day while a boss is out. */
    private void exploits() {
        Enemy boss = null;
        for (Enemy e : match.getGame().getEnemyManager().getEnemies()) if (e.isBoss() && (boss == null || e.getMaxHp() > boss.getMaxHp())) boss = e;
        if (boss == null) return;
        double progress = boss.getDistance() / boss.getRoute().getTotalLength();
        if (progress > 0.3 && match.abilityProblem(AttackAbility.OVERCLOCK) == null) match.useAbility(AttackAbility.OVERCLOCK);
        if (boss.getHpFraction() < 0.5 && match.abilityProblem(AttackAbility.HOTFIX) == null) match.useAbility(AttackAbility.HOTFIX);
        if (progress > 0.15 && match.abilityProblem(AttackAbility.ZERO_DAY) == null) match.useAbility(AttackAbility.ZERO_DAY);
    }

    /** Result of a headless match. */
    public static final class Outcome {
        /** True if the defender's integrity reached 0. */
        public boolean attackerWon;
        /** Game seconds when the match ended. */
        public double time;
        /** The defender's integrity and tower counts at the end. */
        public int defenderLives, towers, maxed, heroes, abilityUnlocks;
        /** Credits the attacker spent and cash the defender earned. */
        public double creditsSpent, defenderEarned;
        /** Units the attacker bought. */
        public int unitsSent;
        @Override public String toString() {
            return String.format("%s at %s  lives %3d  towers %2d (maxed %2d, heroes %d, abilities %d)  spent %7.0f  AI earned %7.0f  units %5d",
                attackerWon ? "ATTACKER WINS" : "DEFENDER HOLDS", ReverseMatch.clock(time), defenderLives, towers, maxed, heroes, abilityUnlocks,
                creditsSpent, defenderEarned, unitsSent);
        }
    }

    /** Plays a whole reverse match headlessly with this attacker style and returns the outcome. */
    public static Outcome play(int mapIndex, long seed, lindefense.sim.Difficulty level, Style style) {
        Game g = ReverseMatch.create(mapIndex, seed, level);
        return play(g, new AttackerBot(g.getReverse(), style));
    }

    /** Plays {@code g} (a reverse-mode game) to the end with this attacker style. */
    public static Outcome play(Game g, Style style) { return play(g, new AttackerBot(g.getReverse(), style)); }

    /** Plays {@code g} to the end with {@code bot} as the attacker. */
    public static Outcome play(Game g, AttackerBot bot) { return play(g, bot, false); }

    /** As {@link #play(Game, AttackerBot)}; {@code trace} prints the economy every 30 game seconds. */
    public static Outcome play(Game g, AttackerBot bot, boolean trace) {
        ReverseMatch r = g.getReverse();
        int maxTicks = (int) ((ReverseMatch.DURATION + ReverseMatch.OVERTIME + 10) / Game.DT);
        for (int i = 0; i < maxTicks && g.getState() == Game.State.PLAYING; i++) {   // includes the 2 s defeat sequence
            bot.tick(Game.DT);
            g.step(Game.DT);
            g.getEvents().clear();
            if (trace && i % (30 * 60) == 0) System.out.printf("    %s credits %7.0f (+%3.0f/s)  AI cash %7.0f lives %3d towers %2d alive %3d queued %2d%n",
                ReverseMatch.clock(r.getElapsed()), r.getCredits(), r.incomeRate(), g.getCash(), g.getLives(),
                g.getTowerManager().getPlayerTowers().size(), g.getEnemyManager().getAliveCount(), r.getQueued());
        }
        Outcome o = new Outcome();
        o.attackerWon = r.attackerWon();
        o.time = r.getElapsed();
        o.defenderLives = g.getLives();
        for (lindefense.tower.Tower t : g.getTowerManager().getPlayerTowers()) {
            o.towers++;
            if (t.isMaxed()) o.maxed++;
            if (t.getType().isHero()) o.heroes++;
            if (lindefense.tower.TowerCatalog.abilityNeedsUnlock(t.getType()) && !t.isAbilityLocked()) o.abilityUnlocks++;
        }
        o.creditsSpent = r.getCreditsSpent();
        o.defenderEarned = g.getTotalCashEarned();
        o.unitsSent = r.getUnitsBought();
        return o;
    }
}
