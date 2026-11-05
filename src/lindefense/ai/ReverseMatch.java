package lindefense.ai;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.List;
import lindefense.enemy.Enemy;
import lindefense.enemy.Modifier;
import lindefense.map.GameMap;
import lindefense.map.MapCatalog;
import lindefense.sim.Difficulty;
import lindefense.sim.Game;
import lindefense.tower.Tower;
import lindefense.tower.TowerType;

/**
 * Reverse mode, "Adversarial Training": the player is the attacker and a {@link DefenderAI} defends. One instance is
 * plugged into a {@link Game} ({@link Game#getReverse()}), which calls {@link #update} every fixed step while the
 * match is running and {@link #onLeak} whenever integrity is lost.
 *
 * <h3>Rules</h3>
 * <ul>
 *   <li><b>Training run</b>: {@value #EPOCHS} epochs of {@value #EPOCH_SECONDS} s ({@link #DURATION} = 15:00 of game time).
 *       When it ends the uplink closes: nothing more can be sent, units already queued or on the track get up to
 *       {@value #OVERTIME} s of overtime, then the defender wins if it still has integrity.</li>
 *   <li><b>Attacker wins</b> the moment the defender's integrity (lives) reaches 0 (the game's DEFEAT state).</li>
 *   <li><b>Compute credits</b>: {@value #START_CREDITS} to start, passive income {@link #incomeRate()} that grows over
 *       the match (12/s at 0:00, ~87/s at 5:00, ~192/s at 10:00, ~327/s at 15:00), +{@value #COMPUTE_STEP}/s per SCALE
 *       COMPUTE purchase (price {@value #COMPUTE_BASE_PRICE} x {@value #COMPUTE_PRICE_GROWTH}^n, at most
 *       {@value #COMPUTE_MAX}), and {@value #LEAK_BONUS_PER_LIFE} credits per integrity point a leak takes; all income is
 *       multiplied by the difficulty's {@link DefenderProfile#attackerIncome}.</li>
 *   <li><b>Difficulty</b> ({@link DefenderProfile}): besides the AI's play and funding, each mode sets the defender's
 *       tower damage and integrity and the attacker's unit health and income. Harder modes: harder-hitting towers, more
 *       integrity, frailer units, less income.</li>
 *   <li><b>Units</b> ({@link AttackUnit}) unlock over time; modifiers add a surcharge; bought units queue in the
 *       uplink and enter the track start one every {@value #SPAWN_GAP} s, on a chosen lane or a random one. Normal
 *       enemy rules apply (splitting, boss children, Palantir phases and surveillance); Palantir's death does not end
 *       the match.</li>
 *   <li><b>Exploits</b> ({@link AttackAbility}) cost credits and have cooldowns.</li>
 *   <li><b>Defender</b>: the normal starting cash (times {@link DefenderProfile#startCash}), the normal kill rewards,
 *       funding {@link #defenderFundingRate()} per second (times {@link DefenderProfile#income}) and its towers'
 *       per-round research income at every epoch end. It plays through the normal game actions, so every rule holds
 *       (hero cap, one copy per hero, Hero Store unlocks in an in-memory collection, $15,000 ability unlocks).</li>
 * </ul>
 *
 * <p>The Game itself runs with {@link Difficulty#O1} rules; the chosen Difficulty Growth mode selects the
 * {@link DefenderProfile}, whose tower-damage, integrity, unit-health and income multipliers apply on top.</p>
 */
public final class ReverseMatch {
    /** Length of one epoch (the defender's research towers pay out at every epoch end). */
    public static final double EPOCH_SECONDS = 60;
    /** Epochs in a training run. */
    public static final int EPOCHS = 15;
    /** Length of the training run in game seconds (15:00). */
    public static final double DURATION = EPOCH_SECONDS * EPOCHS;
    /** Most seconds the match runs past {@link #DURATION} while sent units are still on the track. */
    public static final double OVERTIME = 60;
    /** The attacker's compute credits at 0:00. */
    public static final int START_CREDITS = 250;
    /** Credits the attacker earns per integrity point a leak takes. */
    public static final int LEAK_BONUS_PER_LIFE = 8;
    /** Setup phase: queued units start leaving the uplink only after this many seconds (the defender gets to build). */
    public static final double HANDSHAKE = 15;
    /** Seconds between two units leaving the uplink queue. */
    public static final double SPAWN_GAP = 0.15;
    /** Most units waiting in the uplink queue. */
    public static final int MAX_QUEUE = 150;
    /** Credits per second added by one SCALE COMPUTE purchase. */
    public static final int COMPUTE_STEP = 4;
    /** Price of the first SCALE COMPUTE purchase. */
    public static final int COMPUTE_BASE_PRICE = 300;
    /** Each SCALE COMPUTE purchase costs this much more than the previous one. */
    public static final double COMPUTE_PRICE_GROWTH = 1.45;
    /** Most SCALE COMPUTE purchases per match. */
    public static final int COMPUTE_MAX = 8;
    /** The defender is "under pressure" (stops greedy plays, adds cheap firepower) after 2+ lives lost in this window. */
    public static final double PRESSURE_WINDOW = 20;
    /** A camo unit seen this recently keeps a reactive AI's camo alarm on. */
    public static final double CAMO_MEMORY = 30;
    /** Feed lines kept. */
    public static final int FEED_SIZE = 40;

    /** One line of the activity feed: the AI's builds / upgrades / heroes / abilities and the match's own events. */
    public static final class FeedEntry {
        /** Match time of the entry (seconds). */
        public final double time;
        /** The line shown in the feed. */
        public final String text;
        /** Its colour (0xRRGGBB). */
        public final int rgb;
        /** The AI's action, or null for a match event (unlocks, epochs, exploits). */
        public final DefenderAI.Action action;
        /** Tower involved (for the icon), or null. */
        public final TowerType tower;
        FeedEntry(double time, String text, int rgb, DefenderAI.Action action, TowerType tower) {
            this.time = time; this.text = text; this.rgb = rgb; this.action = action; this.tower = tower;
        }
    }

    /** A bought unit waiting in the uplink. */
    private static final class Pending {
        final AttackUnit unit; final EnumSet<Modifier> mods; final int route;
        Pending(AttackUnit unit, EnumSet<Modifier> mods, int route) { this.unit = unit; this.mods = mods; this.route = route; }
    }

    private final Game game;
    private final DefenderProfile profile;
    private final DefenderAI ai;
    private double credits = START_CREDITS;
    private double creditsEarned = START_CREDITS, creditsSpent, defenderFunding, leakBonus;
    private int computeLevel;
    private final double trackBonus, trackSpeed;
    private double elapsed;
    private int epochsDone;
    private final ArrayDeque<Pending> queue = new ArrayDeque<>();
    private double spawnTimer;
    private final EnumMap<AttackAbility, Double> cooldowns = new EnumMap<>(AttackAbility.class);
    private final EnumMap<AttackAbility, Integer> uses = new EnumMap<>(AttackAbility.class);
    private double overclockLeft;
    private final List<FeedEntry> feed = new ArrayList<>();
    private FeedEntry lastAiAction;
    private int unitsBought, unitsSpawned, livesTaken, leaks, bossesSent;
    private double thinkTimer, camoScanTimer;
    private double lastCamoSeen = -1e9;
    private boolean unlimited;
    private boolean uplinkClosed;
    private final EnumSet<AttackUnit> announced = EnumSet.noneOf(AttackUnit.class);
    private final EnumSet<Modifier> announcedMods = EnumSet.noneOf(Modifier.class);
    private final EnumSet<AttackAbility> announcedAbilities = EnumSet.noneOf(AttackAbility.class);

    // ------------------------------------------------------------------ creation

    /**
     * A new reverse-mode game: base-rule {@link Game} on {@code map}, with this controller installed and the defender
     * profile chosen by {@code level}.
     */
    public static Game create(GameMap map, long seed, Difficulty level) {
        Game g = new Game(map, seed, Difficulty.O1);
        g.setReverse(new ReverseMatch(g, DefenderProfile.of(level == null ? Difficulty.O1 : level)));
        return g;
    }

    /** {@link #create(GameMap, long, Difficulty)} on the catalog map {@code mapIndex}. */
    public static Game create(int mapIndex, long seed, Difficulty level) { return create(MapCatalog.create(mapIndex), seed, level); }

    /** RESTART: a fresh reverse match on the same map and defender profile (unlimited credits carried over). */
    public static Game restart(Game old) {
        ReverseMatch r = old.getReverse();
        int idx = MapCatalog.indexOf(old.getMap());
        if (r == null || idx < 0) throw new IllegalArgumentException("not a reverse-mode catalog game");
        Game g = create(idx, System.nanoTime(), r.profile.level);
        g.getReverse().setUnlimitedCredits(r.unlimited);
        return g;
    }

    private ReverseMatch(Game game, DefenderProfile profile) {
        this.game = game;
        this.profile = profile;
        this.trackBonus = trackBonus(game.getMap());
        this.trackSpeed = trackSpeed(game.getMap());
        game.setStartingLives(profile.integrity);
        if (profile.startCash > 1) game.addCash(Game.START_CASH * (profile.startCash - 1), null);
        DefenderAI.Options o = new DefenderAI.Options();
        o.plan = DefenderAI.Plan.REVERSE;
        o.randomPlacement = profile.casual;
        o.unlockAbilities = profile.unlocksAbilities;
        o.unlockMinTowers = profile.unlockMinTowers;
        o.unlockTowersPer = profile.unlockTowersPer;
        o.waveSource = this::equivalentWave;
        o.camoAlarm = this::camoAlarm;
        o.pressureWindow = PRESSURE_WINDOW;
        ai = new DefenderAI(game, o);
        ai.setListener(this::onAiAction);
        for (AttackUnit u : AttackUnit.values()) if (u.unlockAt <= 0) announced.add(u);
    }

    // ------------------------------------------------------------------ accessors

    /** The game this controller runs. */
    public Game getGame() { return game; }
    /** The defender AI's profile (from the Difficulty Growth mode). */
    public DefenderProfile getProfile() { return profile; }
    /** The Difficulty Growth mode that picked the defender profile. */
    public Difficulty getLevel() { return profile.level; }
    /** The defender AI. */
    public DefenderAI getAI() { return ai; }
    /** Compute credits available now. */
    public double getCredits() { return unlimited ? lindefense.sim.Game.ADMIN_CASH : credits; }
    /** All compute credits the attacker has received (start, income, leaks). */
    public double getCreditsEarned() { return creditsEarned; }
    /** All compute credits the attacker has spent (units, compute, exploits). */
    public double getCreditsSpent() { return creditsSpent; }
    /** Credits earned from leaks so far. */
    public double getLeakBonus() { return leakBonus; }
    /** HP scale of a unit of {@code type} sent now (the game's scale x the difficulty's unit-health multiplier). */
    public double unitHpScale(lindefense.enemy.EnemyType type) { return game.getWaveHpScale(type) * profile.unitHp; }
    /** Total funding paid to the defender (not counting kill rewards). */
    public double getDefenderFunding() { return defenderFunding; }
    /** Game seconds since the match started. */
    public double getElapsed() { return elapsed; }
    /** Seconds left in the training run (0 once the uplink is closed). */
    public double getTimeLeft() { return Math.max(0, DURATION - elapsed); }
    /** Overtime seconds left once the uplink is closed. */
    public double getOvertimeLeft() { return uplinkClosed ? Math.max(0, DURATION + OVERTIME - elapsed) : OVERTIME; }
    /** Current epoch, 1-based ({@value #EPOCHS} at most). */
    public int getEpoch() { return Math.min(EPOCHS, epochsDone + 1); }
    /** Epochs completed so far. */
    public int getEpochsDone() { return epochsDone; }
    /** True once the training run is over: no more sends or exploits. */
    public boolean isUplinkClosed() { return uplinkClosed; }
    /** True when the admin "infinite money" cheat gave the attacker unlimited credits. */
    public boolean hasUnlimitedCredits() { return unlimited; }
    /** Admin "infinite money" in reverse mode: purchases never lower the attacker's credits. */
    public void setUnlimitedCredits(boolean u) { unlimited = u; }
    /** SCALE COMPUTE purchases so far. */
    public int getComputeLevel() { return computeLevel; }
    /** Units bought (queued or spawned). */
    public int getUnitsBought() { return unitsBought; }
    /** Units that have left the uplink onto the track. */
    public int getUnitsSpawned() { return unitsSpawned; }
    /** Bosses bought. */
    public int getBossesSent() { return bossesSent; }
    /** Integrity the attacker's leaks have taken. */
    public int getLivesTaken() { return livesTaken; }
    /** Leaks so far (each takes integrity). */
    public int getLeaks() { return leaks; }
    /** Units waiting in the uplink queue. */
    public int getQueued() { return queue.size(); }
    /** How often an exploit has been used. */
    public int getUses(AttackAbility a) { Integer n = uses.get(a); return n == null ? 0 : n; }
    /** Newest-last activity feed. */
    public List<FeedEntry> getFeed() { return java.util.Collections.unmodifiableList(feed); }
    /** The AI's most recent action (build, upgrade, hero, ability), or null. */
    public FeedEntry getLastAiAction() { return lastAiAction; }
    /** True if the match ended with the defender breached. */
    public boolean attackerWon() { return game.getState() == Game.State.DEFEAT; }
    /** True if the match ended with the defender holding. */
    public boolean defenderHeld() { return game.getState() == Game.State.VICTORY; }

    /**
     * Passive compute income per second right now: {@link #baseIncome()} x {@link #getTrackBonus()} plus SCALE COMPUTE,
     * times the difficulty's {@link DefenderProfile#attackerIncome}.
     */
    public double incomeRate() { return (baseIncome() * trackBonus + COMPUTE_STEP * computeLevel) * profile.attackerIncome; }

    /**
     * Long-track compute bonus for the attacker: towers get more time on long routes, so on maps whose mean route is
     * longer than {@value #TRACK_REFERENCE} px the base income is multiplied by (length / {@value #TRACK_REFERENCE})^
     * {@value #TRACK_EXP} (1.0 on the short maps, x1.16 on Silicon Valley, x1.29 on The Legacy Monolith and Abandoned Data
     * Center). Units also move faster there: {@link #getTrackSpeed()}.
     */
    public double getTrackBonus() { return trackBonus; }

    /** Route length (px) that earns no track bonus. */
    public static final double TRACK_REFERENCE = 1800;
    /** Cap of the long-track bonuses. */
    public static final double TRACK_BONUS_MAX = 3.0;
    /** Exponent of the long-track compute bonus. */
    public static final double TRACK_EXP = 0.25;

    /** The track bonus for a map (see {@link #getTrackBonus()}). */
    public static double trackBonus(GameMap map) {
        return Math.max(1, Math.min(TRACK_BONUS_MAX, Math.pow(meanRoute(map) / TRACK_REFERENCE, TRACK_EXP)));
    }

    /**
     * Unit speed multiplier on long tracks: (mean route length / {@value #TRACK_REFERENCE})^{@value #SPEED_EXP}, clamped
     * to [1, {@value #TRACK_BONUS_MAX}] (x1.55 on Silicon Valley, x2.1 on The Legacy Monolith and Abandoned Data Center), so
     * crossing a long track takes about as long as a short one and map-wide towers do not get several times the work.
     */
    public static double trackSpeed(GameMap map) {
        return Math.max(1, Math.min(TRACK_BONUS_MAX, Math.pow(meanRoute(map) / TRACK_REFERENCE, SPEED_EXP)));
    }
    /** Exponent of the long-track unit speed-up. */
    public static final double SPEED_EXP = 0.75;

    /** Units' speed multiplier on this map (long tracks are crossed faster). */
    public double getTrackSpeed() { return trackSpeed; }

    private static double meanRoute(GameMap map) {
        double sum = 0;
        for (lindefense.map.Path p : map.getRoutes()) sum += p.getTotalLength();
        return sum / Math.max(1, map.getRoutes().size());
    }

    /** The base compute curve 12 + 10 m + 0.5 m^2 per second (m = minutes elapsed, capped at the end of the run). */
    public double baseIncome() {
        double m = Math.min(elapsed, DURATION) / 60.0;
        return 12 + 10 * m + 0.5 * m * m;
    }

    /** The defender's funding per second right now: {@link #baseIncome()} x {@link #FUND_RATIO} x the profile's multiplier. */
    public double defenderFundingRate() { return baseIncome() * FUND_RATIO * profile.income; }

    /** Defender funding as a share of the attacker's base compute income (before the profile multiplier). */
    public static final double FUND_RATIO = 1.0;
    /** Kill reward multiplier for the defender: the listed rewards (the campaign triples them; here the funding carries the AI). */
    public static final double KILL_REWARD_SCALE = 1.0;

    /** Multiplier on enemy kill rewards paid to the defender (the game's reward scale in reverse mode). */
    public double killRewardScale() { return KILL_REWARD_SCALE; }

    /** Campaign-equivalent wave for the AI's build plan: 1 at the start, 100 at the end of the run. */
    public int equivalentWave() { return 1 + (int) Math.min(99, elapsed / DURATION * 99); }

    /** "m:ss" for a number of seconds. */
    public static String clock(double seconds) {
        int s = (int) Math.ceil(Math.max(0, seconds));
        return (s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
    }

    // ------------------------------------------------------------------ unlocks

    /** True once the unit can be bought. */
    public boolean isUnlocked(AttackUnit u) { return elapsed >= u.unlockAt; }
    /** True once the modifier can be applied. */
    public boolean isUnlocked(Modifier m) { return elapsed >= AttackUnit.modifierUnlockAt(m); }
    /** True once the exploit can be used. */
    public boolean isUnlocked(AttackAbility a) { return elapsed >= a.unlockAt; }
    /** Seconds until the unit unlocks (0 if available). */
    public double unlocksIn(AttackUnit u) { return Math.max(0, u.unlockAt - elapsed); }

    /** The modifiers that actually apply to a unit (locked ones and Palantir's are dropped). */
    public EnumSet<Modifier> effectiveModifiers(AttackUnit u, EnumSet<Modifier> mods) {
        EnumSet<Modifier> m = EnumSet.noneOf(Modifier.class);
        if (mods == null || !u.acceptsModifiers()) return m;
        for (Modifier x : mods) if (isUnlocked(x)) m.add(x);
        return m;
    }

    /** Price of {@code count} units of {@code u} with the (effective) modifiers. */
    public int price(AttackUnit u, EnumSet<Modifier> mods, int count) { return u.priceWith(effectiveModifiers(u, mods)) * Math.max(1, count); }

    // ------------------------------------------------------------------ attacker actions

    /** Why {@link #send} would fail ("Unlocks at 4:00", "Not enough credits", ...), or null if it would succeed. */
    public String sendProblem(AttackUnit u, EnumSet<Modifier> mods, int count) {
        if (game.getState() != Game.State.PLAYING) return "Match over";
        if (uplinkClosed) return "Uplink closed";
        if (!isUnlocked(u)) return "Unlocks at " + clock(u.unlockAt);
        if (queue.size() >= MAX_QUEUE) return "Uplink queue full";
        if (!unlimited && credits < price(u, mods, 1)) return "Not enough credits";
        return null;
    }

    /**
     * Buys up to {@code count} units (as many as the credits and the queue allow) and queues them for the track start;
     * {@code route} &lt; 0 picks a random lane per unit. Locked modifiers are ignored. Returns how many were bought.
     */
    public int send(AttackUnit u, EnumSet<Modifier> mods, int count, int route) {
        if (sendProblem(u, mods, 1) != null) return 0;
        EnumSet<Modifier> m = effectiveModifiers(u, mods);
        int each = u.priceWith(m);
        int routes = game.getMap().getRoutes().size();
        int lane = route >= routes ? -1 : route;
        int n = 0;
        while (n < Math.max(1, count) && queue.size() < MAX_QUEUE && (unlimited || credits >= each)) {
            spend(each);
            queue.add(new Pending(u, EnumSet.copyOf(m), lane));
            n++;
        }
        unitsBought += n;
        if (u.isBoss()) bossesSent += n;
        return n;
    }

    /** Price of the next SCALE COMPUTE purchase. */
    public int computePrice() { return (int) Math.round(COMPUTE_BASE_PRICE * Math.pow(COMPUTE_PRICE_GROWTH, computeLevel)); }

    /** Why SCALE COMPUTE cannot be bought now, or null. */
    public String computeProblem() {
        if (game.getState() != Game.State.PLAYING) return "Match over";
        if (uplinkClosed) return "Uplink closed";
        if (computeLevel >= COMPUTE_MAX) return "Fully scaled";
        if (!unlimited && credits < computePrice()) return "Not enough credits";
        return null;
    }

    /** SCALE COMPUTE: +{@value #COMPUTE_STEP} credits per second for the rest of the match. */
    public boolean scaleCompute() {
        if (computeProblem() != null) return false;
        spend(computePrice());
        computeLevel++;
        feed("Compute scaled to +" + (COMPUTE_STEP * computeLevel) + "/s", 0xffd166, null, null);
        return true;
    }

    /** Remaining cooldown of an exploit (0 = ready). */
    public double cooldownLeft(AttackAbility a) { Double c = cooldowns.get(a); return c == null ? 0 : c; }

    /** Seconds left of the running Overclock (0 if none). */
    public double getOverclockLeft() { return overclockLeft; }

    /** Why the exploit cannot be used now, or null. */
    public String abilityProblem(AttackAbility a) {
        if (game.getState() != Game.State.PLAYING) return "Match over";
        if (uplinkClosed) return "Uplink closed";
        if (!isUnlocked(a)) return "Unlocks at " + clock(a.unlockAt);
        if (cooldownLeft(a) > 0) return "Recharging (" + (int) Math.ceil(cooldownLeft(a)) + "s)";
        if (!unlimited && credits < a.cost) return "Not enough credits";
        if (a != AttackAbility.ZERO_DAY && game.getEnemyManager().getEnemies().isEmpty()) return "No units on the track";
        if (a == AttackAbility.ZERO_DAY && game.getTowerManager().getPlayerTowers().isEmpty()) return "No towers to jam";
        return null;
    }

    /** Fires an exploit (see {@link AttackAbility}); returns false (and spends nothing) if {@link #abilityProblem} says no. */
    public boolean useAbility(AttackAbility a) {
        if (abilityProblem(a) != null) return false;
        spend(a.cost);
        cooldowns.put(a, a.cooldown);
        uses.put(a, getUses(a) + 1);
        switch (a) {
            case OVERCLOCK:
                if (overclockLeft <= 0) game.setGlobalEnemySpeedMultiplier(game.getGlobalEnemySpeedMultiplier() * AttackAbility.OVERCLOCK_SPEED);
                overclockLeft = a.duration;
                game.setBanner("OVERCLOCK: UNITS +50% SPEED", 0xff2bd6, 2);
                break;
            case HOTFIX: {
                int n = 0;
                for (Enemy e : game.getEnemyManager().getEnemies()) {
                    if (!e.isAlive() || e.getHp() >= e.getMaxHp()) continue;
                    e.heal(e.getMaxHp());
                    game.emitText(e.getPosition(), "+HP", 0x3bff8a);
                    n++;
                }
                game.setBanner("HOTFIX: " + n + " UNITS RESTORED", 0x3bff8a, 2);
                break;
            }
            case ZERO_DAY: {
                List<Tower> ts = new ArrayList<>(game.getTowerManager().getPlayerTowers());
                ts.sort((x, y) -> Integer.compare(y.getInvestedCost(), x.getInvestedCost()));
                int jammed = 0, tried = 0;
                for (Tower t : ts) {
                    if (tried >= AttackAbility.ZERO_DAY_TARGETS) break;
                    tried++;
                    if (t.isSurveillanceImmune()) { game.emitText(t.getPosition(), "PATCHED", 0x7fd8a8); continue; }
                    t.setSurveilled(a.duration);
                    game.emitText(t.getPosition(), "JAMMED", 0xff4d4d);
                    jammed++;
                }
                game.setBanner("ZERO-DAY: " + jammed + " TOWER" + (jammed == 1 ? "" : "S") + " JAMMED", 0xff4d4d, 2);
                break;
            }
            default: break;
        }
        feed("Exploit: " + a.displayName, 0xff2bd6, null, null);
        return true;
    }

    private void spend(double amount) {
        if (!unlimited) credits -= amount;
        creditsSpent += amount;
    }

    // ------------------------------------------------------------------ simulation hooks

    /** One fixed step of the match (called by {@link Game#step} while it is playing). */
    public void update(double dt) {
        if (game.getState() != Game.State.PLAYING) return;
        elapsed += dt;
        if (!uplinkClosed) {
            double inc = incomeRate() * dt;
            credits += inc;
            creditsEarned += inc;
            double fund = defenderFundingRate() * dt;
            game.addCash(fund, null);
            defenderFunding += fund;
        }
        while (epochsDone < EPOCHS && elapsed >= (epochsDone + 1) * EPOCH_SECONDS) endEpoch();
        announceUnlocks();
        // uplink: one unit every SPAWN_GAP seconds
        if (elapsed >= HANDSHAKE) spawnTimer -= dt;
        while (spawnTimer <= 0 && !queue.isEmpty() && elapsed >= HANDSHAKE) {
            Pending p = queue.poll();
            Enemy e = game.getEnemyManager().spawnScaled(p.unit.type, p.mods, p.route, 0, unitHpScale(p.unit.type), game.getWaveSpeedScale() * trackSpeed);
            if (e != null) unitsSpawned++;
            spawnTimer += SPAWN_GAP;
        }
        if (queue.isEmpty() && spawnTimer < 0) spawnTimer = 0;
        for (AttackAbility a : AttackAbility.values()) {
            double c = cooldownLeft(a);
            if (c > 0) cooldowns.put(a, Math.max(0, c - dt));
        }
        if (overclockLeft > 0) {
            overclockLeft -= dt;
            if (overclockLeft <= 0) { overclockLeft = 0; game.setGlobalEnemySpeedMultiplier(game.getGlobalEnemySpeedMultiplier() / AttackAbility.OVERCLOCK_SPEED); }
        }
        camoScanTimer -= dt;
        if (camoScanTimer <= 0) {
            camoScanTimer = 0.5;
            for (Enemy e : game.getEnemyManager().getEnemies()) if (e.isCamo()) { lastCamoSeen = elapsed; break; }
        }
        thinkTimer -= dt;
        if (thinkTimer <= 0) {
            thinkTimer += profile.thinkInterval;
            ai.manage();
        }
        if (!uplinkClosed && elapsed >= DURATION) {
            uplinkClosed = true;
            game.setBanner("TRAINING RUN OVER  -  UPLINK CLOSED", 0xffd166, 3);
            feed("Uplink closed: overtime for units already sent", 0xffd166, null, null);
        }
        if (uplinkClosed && game.getState() == Game.State.PLAYING
            && (queue.isEmpty() && game.getEnemyManager().isEmpty() || elapsed >= DURATION + OVERTIME)) {
            feed("Defender held with " + game.getLives() + " integrity", 0x7fd8a8, null, null);
            game.declareDefenderVictory("THE DEFENDER AI HELD THE LINE");
        }
    }

    /** Integrity was lost: the attacker earns {@value #LEAK_BONUS_PER_LIFE} credits per point (times the difficulty's income multiplier). */
    public void onLeak(int lives, Enemy leaker) {
        if (lives <= 0) return;
        leaks++;
        livesTaken += lives;
        double bonus = LEAK_BONUS_PER_LIFE * lives * profile.attackerIncome;
        credits += bonus;
        creditsEarned += bonus;
        leakBonus += bonus;
    }

    private void endEpoch() {
        epochsDone++;
        double research = 0;
        for (Tower t : new ArrayList<>(game.getTowerManager().getTowers())) research += t.getBehavior().onRoundEnd(game, t);
        if (research > 0) game.addCash(research, null);
        game.addPopValue(-game.getRoundPopValue());   // Perplexity's Deep Research Scrape counts pops per epoch
        feed("Epoch " + epochsDone + " / " + EPOCHS + " complete" + (research > 0 ? "  (AI research +$" + (int) research + ")" : ""), 0x9fb3c8, null, null);
    }

    /** Banner + feed line for units, modifiers and exploits that just became available. */
    private void announceUnlocks() {
        List<String> names = new ArrayList<>();
        for (AttackUnit u : AttackUnit.values()) {
            if (announced.contains(u) || !isUnlocked(u)) continue;
            announced.add(u);
            names.add(u.type.displayName);
        }
        for (Modifier m : Modifier.values()) {
            if (announcedMods.contains(m) || !isUnlocked(m)) continue;
            announcedMods.add(m);
            names.add(m.label + " modifier");
        }
        for (AttackAbility a : AttackAbility.values()) {
            if (announcedAbilities.contains(a) || !isUnlocked(a)) continue;
            announcedAbilities.add(a);
            names.add(a.displayName + " exploit");
        }
        if (names.isEmpty()) return;
        String head = names.size() > 3 ? String.join(", ", names.subList(0, 3)) + " +" + (names.size() - 3) : String.join(", ", names);
        game.setBanner("UNLOCKED: " + head.toUpperCase(), 0xff2bd6, 3);
        feed("Unlocked: " + String.join(", ", names), 0xff2bd6, null, null);
    }

    /** The AI's camo alarm: camo seen on the track recently, or (anticipating profiles) camo is available to the attacker. */
    private boolean camoAlarm() {
        if (elapsed - lastCamoSeen <= CAMO_MEMORY) return true;
        return profile.anticipatesCamo && (isUnlocked(Modifier.CAMO) || isUnlocked(AttackUnit.DDT));
    }

    private void onAiAction(DefenderAI.Action a, Tower t, String text) {
        int rgb;
        switch (a) {
            case BUILD: rgb = 0x00f0ff; break;
            case UPGRADE: rgb = 0x3bff8a; break;
            case HERO_UNLOCK: case HERO_DEPLOY: rgb = 0xffd166; break;
            case ABILITY_UNLOCK: rgb = 0xff2bd6; break;
            default: rgb = 0xb48cff; break;
        }
        FeedEntry e = feed("AI " + text, rgb, a, t != null ? t.getType() : null);
        if (a != DefenderAI.Action.ABILITY_CAST) lastAiAction = e;
        // the big moments get the banner (and replace the Hero Store's own "X UNLOCKED", which would read as yours)
        if (a == DefenderAI.Action.HERO_UNLOCK || a == DefenderAI.Action.HERO_DEPLOY || a == DefenderAI.Action.ABILITY_UNLOCK)
            game.setBanner(("DEFENDER AI " + text).toUpperCase(), rgb, 2.5);
    }

    private FeedEntry feed(String text, int rgb, DefenderAI.Action a, TowerType tower) {
        FeedEntry e = new FeedEntry(elapsed, text, rgb, a, tower);
        feed.add(e);
        if (feed.size() > FEED_SIZE) feed.remove(0);
        return e;
    }
}
