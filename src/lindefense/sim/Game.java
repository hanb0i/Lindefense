package lindefense.sim;

import java.util.ArrayList;
import java.util.List;
import lindefense.audio.AudioManager;
import lindefense.audio.Sfx;
import lindefense.combat.Combat;
import lindefense.combat.VisualEvent;
import lindefense.effects.Effects;
import lindefense.enemy.Boss;
import lindefense.enemy.Enemy;
import lindefense.enemy.EnemyManager;
import lindefense.enemy.EnemyType;
import lindefense.map.GameMap;
import lindefense.tower.AbilityManager;
import lindefense.tower.Tower;
import lindefense.tower.TowerManager;
import lindefense.tower.TowerType;
import lindefense.wave.WaveData;
import lindefense.wave.WaveDef;
import lindefense.wave.WaveManager;

/**
 * The simulation root: owns the map, economy, lives, managers and the fixed-step
 * update loop. It knows nothing about ACM graphics; the UI drives it by calling
 * {@link #advance(double)} and reads state / {@link #getEvents()} to render.
 */
public final class Game {
    public enum State { PLAYING, VICTORY, DEFEAT }

    public static final int START_CASH = 650;
    public static final int START_LIVES = 100;
    /** Fixed simulation step in seconds. */
    public static final double DT = 1.0 / 60.0;
    /** Length of the Palantir defeat sequence before the victory screen. */
    public static final double VICTORY_SEQUENCE_TIME = 5.0;

    private final GameMap map;
    private final Rng rng;
    private final EnemyManager enemyManager;
    private final TowerManager towerManager;
    private final WaveManager waveManager;
    private final AbilityManager abilityManager;
    private final Combat combat;
    private final Effects effects;
    /** PROMPT INJECTION: injector enemies, hijacked towers and Palantir's decoys (see {@link PromptInjection}). */
    private final PromptInjection injection;
    /** Palantir's window grab: the only window number the simulation sees (see {@link WindowLink}). */
    private final WindowLink windowLink = new WindowLink();
    /** PATCH NOTES / BREAKING NEWS: run modifiers and per-wave events (off unless enabled; see RunVariance). */
    private final lindefense.variance.RunVariance variance;
    private final List<VisualEvent> events = new ArrayList<>();
    private final List<String> log = new ArrayList<>();

    private State state = State.PLAYING;
    private double cash = START_CASH;
    private int lives = START_LIVES;
    private final Difficulty difficulty;   // DIFFICULTY HOOK: chosen mode (see Difficulty)
    private final long seed;
    private double time;
    private int tick;
    private int speed = 1;
    private boolean paused;
    private double accumulator;

    private String banner;
    private int bannerRgb;
    private double bannerTime;
    private Boss palantir;
    private double victoryTimer = -1;
    private double defeatTimer = -1;
    private int lastCompletedWave;
    private double totalCashEarned;
    private double roundPopValue;
    private double globalEnemySpeedMultiplier = 1.0;
    private boolean invincible;
    /** Permanently unlocked heroes (Hero Store). In-memory by default; the windowed game installs the persistent one. */
    private HeroCollection heroes = HeroCollection.inMemory();
    /** Heroes already deployed this match (each hero may be placed once per match, even after being removed). */
    private final java.util.EnumSet<TowerType> deployedHeroes = java.util.EnumSet.noneOf(TowerType.class);

    public Game(GameMap map, long seed) { this(map, seed, Difficulty.defaultMode()); }

    public Game(GameMap map, long seed, Difficulty difficulty) {
        this.difficulty = difficulty;   // DIFFICULTY HOOK
        this.seed = seed;
        this.cash = difficulty.startCash(START_CASH);
        this.lives = difficulty.startLives(START_LIVES);
        this.map = map;
        this.rng = new Rng(seed);
        this.enemyManager = new EnemyManager(this);
        this.towerManager = new TowerManager(this);
        this.waveManager = new WaveManager(this);
        this.abilityManager = new AbilityManager(this);
        this.combat = new Combat(this);
        this.effects = new Effects(this);
        this.injection = new PromptInjection(this);
        this.variance = new lindefense.variance.RunVariance(this);
        map.reset();
    }

    /** A brand-new game on the same map and difficulty as {@code old} (used by RESTART): wave, cash, lives and all state reset. */
    public static Game freshCopy(Game old) { return freshCopy(old, lindefense.variance.RunSeed.next()); }

    /**
     * As {@link #freshCopy(Game)} but with the given seed ({@code old.getSeed()} replays the run: same patch-note offers,
     * news and spawns). Admin cheats and the variance switch carry over.
     */
    public static Game freshCopy(Game old, long seed) {
        int idx = lindefense.map.MapCatalog.indexOf(old.getMap());
        if (idx < 0) throw new IllegalArgumentException("map is not in the catalog: " + old.getMap().getName());
        Game g = new Game(lindefense.map.MapCatalog.create(idx), seed, old.getDifficulty());
        g.setHeroCollection(old.getHeroCollection());   // unlocks are permanent; deployments reset per match
        g.copyAdminFrom(old);
        if (old.variance.isEnabled()) g.variance.enable(old.variance.getPicker());   // PATCH NOTES: same switch and picker
        return g;
    }

    // ---------------- Hero Store ----------------
    public HeroCollection getHeroCollection() { return heroes; }
    public void setHeroCollection(HeroCollection c) { heroes = c == null ? HeroCollection.inMemory() : c; }
    public boolean isHeroUnlocked(TowerType type) { return (adminHeroes && type != null && type.isHero()) || heroes.isUnlocked(type); }

    // ---------------- admin mode ----------------
    /** Credits shown while infinite money is on (spending never lowers them). */
    public static final double ADMIN_CASH = 999_999_999;
    private boolean adminHeroes, adminMoney, adminHealth;

    /**
     * Applies the SETTINGS admin checklist to this match (see {@link AdminMode}). Each cheat is independent:
     * unlocking every hero, unlimited credits and unloseable integrity.
     */
    public void setAdmin(boolean heroes, boolean money, boolean health) {
        adminHeroes = heroes;
        adminMoney = money;
        adminHealth = health;
        if (money) cash = Math.max(cash, ADMIN_CASH);
        if (health) invincible = true;
    }

    /** Copies the admin cheats of another game (RESTART keeps them). */
    public void copyAdminFrom(Game other) { setAdmin(other.adminHeroes, other.adminMoney, other.adminHealth); }

    /** True if any admin cheat is active in this match. */
    public boolean isAdmin() { return adminHeroes || adminMoney || adminHealth; }
    public boolean hasAdminHeroes() { return adminHeroes; }
    public boolean hasAdminMoney() { return adminMoney; }
    public boolean hasAdminHealth() { return adminHealth; }
    private int heroLimit = lindefense.tower.TowerManager.MAX_HEROES_PER_GAME;
    /** Most different heroes this match allows (default {@code TowerManager.MAX_HEROES_PER_GAME}, 3). */
    public int getHeroLimit() { return heroLimit; }
    /** Changes the hero cap for this match; tests and tools that field the whole roster lift it. */
    public void setHeroLimit(int limit) { heroLimit = Math.max(0, limit); }
    /** True once this hero has been deployed in the current match (it stays true after the hero is removed). */
    public boolean isHeroDeployed(TowerType type) { return deployedHeroes.contains(type); }
    /** Called by the tower manager when a hero is placed. */
    public void markHeroDeployed(TowerType type) { deployedHeroes.add(type); }

    /**
     * Why the hero cannot be bought in the Hero Store right now ("Already unlocked", "Not enough cash", ...), or null
     * if {@link #purchaseHero} would succeed.
     */
    public String heroPurchaseProblem(TowerType type) {
        if (type == null || !type.isHero()) return "Not a hero";
        if (state != State.PLAYING) return "Game over";
        if (isHeroUnlocked(type)) return "Already unlocked";
        if (cash < lindefense.tower.TowerCatalog.get(type).unlockCost) return "Not enough cash";
        return null;
    }

    /**
     * Buys a hero in the Hero Store: deducts its unlock price from the match cash and permanently adds it to the
     * collection. Never places it. Returns false (and spends nothing) if unaffordable, already owned or not a hero.
     */
    public boolean purchaseHero(TowerType type) {
        if (heroPurchaseProblem(type) != null) { AudioManager.sfx(Sfx.INVALID); return false; }   // AUDIO HOOK
        int price = lindefense.tower.TowerCatalog.get(type).unlockCost;
        if (!spendCash(price)) return false;
        heroes.unlock(type);
        setBanner(type.displayName.toUpperCase() + " UNLOCKED", type.primaryRgb, 2.5);
        log("Hero unlocked: " + type.displayName + " for $" + price);
        AudioManager.sfx(Sfx.CASH);   // AUDIO HOOK
        return true;
    }

    // ---------------- reverse mode ("Adversarial Training") ----------------
    /** The attacker controller of a reverse-mode match (the player sends enemies, an AI defends), or null. */
    private lindefense.ai.ReverseMatch reverse;
    /** The reverse-mode controller, or null in the normal game. */
    public lindefense.ai.ReverseMatch getReverse() { return reverse; }
    /** True in reverse mode. */
    public boolean isReverse() { return reverse != null; }
    /** Installs the reverse-mode controller (see {@code ReverseMatch.create}); it is updated every step while playing. */
    public void setReverse(lindefense.ai.ReverseMatch r) { reverse = r; }

    /**
     * Ends the match at once with the defender holding the line (reverse mode: the training run ran out). Does nothing
     * if the match is already over or its defeat / victory sequence has started.
     */
    public void declareDefenderVictory(String bannerText) {
        if (state != State.PLAYING || defeatTimer >= 0 || victoryTimer >= 0) return;
        state = State.VICTORY;
        setBanner(bannerText, 0x7fd8a8, 4);
        log(bannerText);
    }

    // ---------------- accessors ----------------
    public GameMap getMap() { return map; }
    public Difficulty getDifficulty() { return difficulty; }   // DIFFICULTY HOOK
    public long getSeed() { return seed; }
    public Rng getRng() { return rng; }
    public EnemyManager getEnemyManager() { return enemyManager; }
    public TowerManager getTowerManager() { return towerManager; }
    public WaveManager getWaveManager() { return waveManager; }
    public AbilityManager getAbilityManager() { return abilityManager; }
    public Combat getCombat() { return combat; }
    /** Patch notes (run modifiers) and breaking news (per-wave events); disabled unless the windowed game enables it. */
    public lindefense.variance.RunVariance getVariance() { return variance; }
    /** Zones, walkers, drones, node hazards and scheduled tasks spawned by tower behaviours. */
    public Effects getEffects() { return effects; }
    public List<VisualEvent> getEvents() { return events; }
    /** Prompt injection: injector broadcasts, hijacked towers' zaps and Palantir's decoys. */
    public PromptInjection getInjection() { return injection; }
    /** Palantir's window grab link (grab requests out, window fraction in). */
    public WindowLink getWindowLink() { return windowLink; }
    /**
     * Reported by the windowed UI during Palantir's System Takeover: the window's size relative to its size before the
     * grab (1.0 = untouched, the default; headless runs never call this).
     */
    public void setWindowFraction(double f) { windowLink.setFraction(f); }
    /** The last window fraction the UI reported (1.0 unless Palantir's grab shrank the window). */
    public double getWindowFraction() { return windowLink.getFraction(); }
    public List<String> getLog() { return log; }
    public State getState() { return state; }
    public double getCash() { return cash; }
    public int getLives() { return lives; }
    public double getTime() { return time; }
    public int getTick() { return tick; }
    public int getSpeed() { return speed; }
    public boolean isPaused() { return paused; }
    public int getWave() { return waveManager.getCurrentWave(); }
    public int getLastCompletedWave() { return lastCompletedWave; }
    public double getTotalCashEarned() { return totalCashEarned; }
    /** Cash paid by enemy pops since the current wave started (Perplexity Deep Research Scrape). */
    public double getRoundPopValue() { return roundPopValue; }
    public void addPopValue(double v) { roundPopValue += v; }
    public Boss getPalantir() { return palantir; }
    public boolean isVictorySequenceActive() { return victoryTimer > 0; }
    public double getVictoryTimer() { return victoryTimer; }
    public String getBanner() { return bannerTime > 0 ? banner : null; }
    public int getBannerRgb() { return bannerRgb; }
    public double getGlobalRateMultiplier() { return variance.fireRate(); }   // PATCH NOTES hook (1 when off)
    /** Range multiplier from run modifiers / news for every tower (1 when variance is off). */
    public double getGlobalRangeMultiplier() { return variance.range(); }
    public double getGlobalDamageMultiplier() { return difficulty.towerDamage; }   // DIFFICULTY HOOK
    public double getGlobalEnemySpeedMultiplier() { return globalEnemySpeedMultiplier; }
    public void setGlobalEnemySpeedMultiplier(double m) { globalEnemySpeedMultiplier = m; }
    /** Test/debug only: leaks still subtract lives but never trigger defeat. */
    public void setInvincible(boolean v) { invincible = v; }
    public boolean isInvincible() { return invincible; }

    /** HP scale for enemies spawned now (based on the current wave). */
    public double getWaveHpScale() { return WaveData.hpScale(Math.max(1, getWave())) * difficulty.hpMultiplier(Math.max(1, getWave())) * variance.enemyHp(); }   // DIFFICULTY HOOK, PATCH NOTES hook
    /** Type-aware HP scale used when spawning (DIFFICULTY HOOK: Palantir gets a reduced share of the mode's HP bonus). */
    public double getWaveHpScale(EnemyType type) {
        return WaveData.hpScale(Math.max(1, getWave())) * difficulty.hpMultiplier(Math.max(1, getWave()), type) * variance.enemyHp();   // PATCH NOTES hook
    }
    public double getWaveSpeedScale() { return WaveData.speedScale(Math.max(1, getWave())) * variance.enemySpeed(); }   // PATCH NOTES hook
    public double getRewardScale() {
        if (reverse != null) return reverse.killRewardScale();   // REVERSE HOOK: the defender AI's kill bounty
        return WaveData.rewardScale(Math.max(1, getWave())) * difficulty.income * variance.killIncome();   // DIFFICULTY HOOK, PATCH NOTES hook
    }

    public void setSpeed(int s) { speed = Math.max(1, Math.min(3, s)); }
    public void setPaused(boolean p) { paused = p; }
    public void togglePause() { paused = !paused; }

    /** All bosses currently alive (for health bars). */
    public List<Boss> getActiveBosses() {
        List<Boss> l = new ArrayList<>();
        for (Enemy e : enemyManager.getEnemies()) if (e instanceof Boss) l.add((Boss) e);
        return l;
    }

    // ---------------- economy & lives ----------------
    public void addCash(double amount, Vec where) {
        if (amount <= 0) return;
        cash += amount;
        totalCashEarned += amount;
    }

    public boolean spendCash(double amount) {
        if (adminMoney) return true;   // unlimited credits
        if (cash < amount) return false;
        cash -= amount;
        return true;
    }

    /**
     * Restores integrity (lives), never above the difficulty's starting maximum, and returns how many were actually
     * restored. The game has no per-tower health, so healing heroes (Sage Aarav) top the player's lives back up:
     * this is the survival resource leaks take away.
     */
    public int restoreLives(int n) {
        if (state != State.PLAYING || n <= 0) return 0;
        int max = difficulty.startLives(START_LIVES);
        int before = lives;
        lives = Math.max(lives, Math.min(max, lives + n));   // never lowers integrity above the maximum (Synthetic Data)
        return lives - before;
    }

    /** Adds integrity with no cap (Synthetic Data: +1 per wave cleared may exceed the starting maximum). */
    public void addLives(int n) {
        if (state == State.PLAYING && n > 0) lives += n;
    }

    /** The difficulty's starting (maximum) lives, the cap for {@link #restoreLives}. */
    public int getMaxLives() { return difficulty.startLives(START_LIVES); }

    public void loseLives(int n, Enemy leaker) {
        if (state != State.PLAYING || n <= 0) return;
        lives = Math.max(0, lives - n);
        if (reverse != null) reverse.onLeak(n, leaker);   // REVERSE HOOK: leak bonus for the attacker
        AudioManager.sfx(Sfx.LIFE_LOST);   // AUDIO HOOK
        events.add(VisualEvent.text(leaker.getPosition(), "-" + n + " lives", 0xff5a5a));
        if (invincible) { lives = Math.max(lives, 1); return; }
        if (lives <= 0 && defeatTimer < 0 && victoryTimer < 0) {
            defeatTimer = 2.0;
            setBanner("DEFENSES BREACHED", 0xff5a5a, 3);
            log("Lives reached zero on wave " + getWave());
        }
    }

    // ---------------- player actions ----------------
    public boolean startNextWave() {
        if (state != State.PLAYING) return false;
        return waveManager.startNextWave();
    }

    public Tower placeTower(TowerType type, Vec p) {
        if (state != State.PLAYING) return null;
        Tower placed = towerManager.place(type, p);
        AudioManager.sfx(placed != null ? Sfx.TOWER_PLACE : Sfx.INVALID);   // AUDIO HOOK
        return placed;
    }

    /**
     * Why a tower cannot be placed at {@code p} ("Cannot build here", "Overlaps another tower",
     * "Unlock Brad Lindemann in the Hero Store", "Brad Lindemann already deployed this match", "Not enough cash"),
     * or null if it can.
     */
    public String placementProblem(TowerType type, Vec p) { return towerManager.placementProblem(type, p); }

    public boolean upgradeTower(Tower t) {
        boolean ok = state == State.PLAYING && towerManager.upgrade(t);
        AudioManager.sfx(ok ? Sfx.TOWER_UPGRADE : Sfx.INVALID);   // AUDIO HOOK
        return ok;
    }
    public int sellTower(Tower t) {
        int refund = state == State.PLAYING ? towerManager.sell(t) : 0;
        if (refund > 0) AudioManager.sfx(Sfx.TOWER_SELL);   // AUDIO HOOK
        return refund;
    }
    /**
     * Buys a fully upgraded shop tower's ability ({@code TowerCatalog.ABILITY_UNLOCK_COST}); it is ready at once.
     * Returns false if the tower is not maxed, has nothing to unlock, or the player cannot pay.
     */
    public boolean unlockAbility(Tower t) {
        boolean ok = state == State.PLAYING && towerManager.unlockAbility(t);
        AudioManager.sfx(ok ? Sfx.TOWER_UPGRADE : Sfx.INVALID);   // AUDIO HOOK
        return ok;
    }
    /** Activates an ability that needs no location (see {@link #activateAbility(Tower, Vec)} for targeted ones). */
    public boolean activateAbility(Tower t) {
        boolean ok = state == State.PLAYING && abilityManager.activate(t);
        AudioManager.sfx(ok ? Sfx.ABILITY : Sfx.INVALID);   // AUDIO HOOK
        return ok;
    }
    /** Activates an ability at a player-chosen map point (DALL-E Outpainting, Mistral Stratosphere Tempest). */
    public boolean activateAbility(Tower t, Vec targetPoint) {
        boolean ok = state == State.PLAYING && abilityManager.activate(t, targetPoint);
        AudioManager.sfx(ok ? Sfx.ABILITY : Sfx.INVALID);   // AUDIO HOOK
        return ok;
    }

    // ---------------- simulation ----------------
    /**
     * Advances the simulation by real seconds, honouring speed and pause.
     * Runs whole fixed steps; the remainder is carried over.
     */
    public void advance(double realSeconds) {
        if (paused || state != State.PLAYING && victoryTimer <= 0 && defeatTimer <= 0) return;
        accumulator += realSeconds * speed;
        int steps = 0;
        while (accumulator >= DT && steps < 30) {
            step(DT);
            accumulator -= DT;
            steps++;
        }
        if (steps == 30) accumulator = 0;
    }

    /** Runs exactly one fixed simulation step. Public for headless tests. */
    public void step(double dt) {
        time += dt;
        tick++;
        if (bannerTime > 0) bannerTime -= dt;
        if (victoryTimer > 0) {
            victoryTimer -= dt;
            map.update(this, dt);
            enemyManager.update(dt);
            combat.updateProjectiles(dt);
            if (victoryTimer <= 0) { state = State.VICTORY; }
            return;
        }
        if (defeatTimer > 0) {
            defeatTimer -= dt;
            enemyManager.update(dt);
            combat.updateProjectiles(dt);
            if (defeatTimer <= 0) state = State.DEFEAT;
            return;
        }
        if (state != State.PLAYING) return;
        if (reverse != null) { reverse.update(dt); if (state != State.PLAYING) return; }   // REVERSE HOOK: attacker economy, uplink, AI
        waveManager.update(dt);
        map.update(this, dt);
        injection.update(dt);   // PROMPT INJECTION: broadcasts and zaps before the towers act
        towerManager.update(dt);
        effects.update(dt);
        combat.updateProjectiles(dt);
        enemyManager.update(dt);
    }

    /** Runs {@code n} fixed steps (headless helper). */
    public void run(int n) { for (int i = 0; i < n && !(state == State.DEFEAT); i++) step(DT); }

    /** Clears visual events (renderer calls this after drawing them). */
    public List<VisualEvent> drainEvents() {
        List<VisualEvent> copy = new ArrayList<>(events);
        events.clear();
        return copy;
    }

    // ---------------- hooks from subsystems ----------------
    public void onWaveStarted(int wave, WaveDef def) {
        roundPopValue = 0;
        variance.onWaveStarted(wave);   // PATCH NOTES: stale news dropped, wave-start news effects
        map.onWaveStart(this, wave);
        AudioManager.sfx(def.containsBoss() ? Sfx.BOSS_ALARM : Sfx.WAVE_START);   // AUDIO HOOK
        String msg = "Wave " + wave;
        if (def.containsBoss()) msg += "  -  BOSS INCOMING";
        setBanner(msg, def.containsBoss() ? 0xff8080 : 0xffffff, 2.5);
        log("Wave " + wave + " started" + (def.note != null ? ": " + def.note : ""));
    }

    public void onWaveCompleted(int wave, WaveDef def) {
        lastCompletedWave = wave;
        AudioManager.sfx(Sfx.WAVE_COMPLETE); AudioManager.sfx(Sfx.CASH);   // AUDIO HOOK
        int bonus = (int) Math.round(WaveData.waveBonus(wave) * difficulty.income * variance.waveBonus());   // DIFFICULTY HOOK, PATCH NOTES hook
        double income = 0;
        for (Tower t : new ArrayList<>(towerManager.getTowers())) income += t.getBehavior().onRoundEnd(this, t);
        addCash(bonus + income, null);
        setBanner("Wave " + wave + " complete  +$" + (int) (bonus + income), 0x7fd8a8, 2.5);
        log("Wave " + wave + " complete: +$" + bonus + (income > 0 ? " (+$" + (int) income + " research income)" : ""));
        variance.onWaveCompleted(wave);   // PATCH NOTES: integrity / interest, news expires, next draft and news
        if (wave >= WaveData.WAVE_COUNT && victoryTimer < 0 && state == State.PLAYING) {
            // Palantir already dead if we got here; treat as victory as a fallback.
            victoryTimer = 0.5;
        }
    }

    public void onEnemyKilled(Enemy e) {
        if (e.getType().isBoss()) AudioManager.sfx(Sfx.BOSS_DEATH);   // AUDIO HOOK
        if (e.getType() == EnemyType.PALANTIR && victoryTimer < 0 && reverse == null) {   // REVERSE HOOK: just a unit there
            victoryTimer = VICTORY_SEQUENCE_TIME;
            setBanner("PALANTIR DESTROYED", 0xffd166, VICTORY_SEQUENCE_TIME);
            events.add(VisualEvent.phase(e.getPosition(), "PALANTIR DESTROYED", 0xffd166));
            for (Enemy o : enemyManager.getEnemies()) if (o != e) o.applyStatus(lindefense.enemy.StatusEffect.Kind.STUN, 1, 99);
            waveManager.endWave();
            log("Palantir destroyed. Campaign complete.");
        }
    }

    public void announceBoss(Boss b) {
        AudioManager.sfx(Sfx.BOSS_ALARM);   // AUDIO HOOK
        if (b.isPalantir()) {
            palantir = b;
            setBanner("PALANTIR HAS ARRIVED  -  " + b.getPhaseName(), 0xff4d4d, 4);
            events.add(VisualEvent.phase(b.getPosition(), "PALANTIR", 0xff4d4d));
        } else {
            setBanner(b.getType().displayName + " (" + b.getType().getBossClass().label + ") has entered the track", 0xff9a5a, 3);
        }
        log("Boss entered: " + b.getType().displayName);
    }

    public void onPalantirPhase(Boss b, int phase) {
        setBanner("PALANTIR PHASE " + (phase + 1) + ": " + b.getPhaseName(), 0xff4d4d, 3);
        events.add(VisualEvent.phase(b.getPosition(), b.getPhaseName(), 0xff4d4d));
        if (phase == 2) {
            // Exposed Core: launches two Lockheed Martin escorts.
            for (int i = 0; i < 2; i++) {
                enemyManager.spawn(EnemyType.LOCKHEED_MARTIN, null, b.getRouteIndex(), Math.max(0, b.getDistance() - 40 * (i + 1)));
            }
        }
        log("Palantir entered phase " + (phase + 1) + " (" + b.getPhaseName() + ")");
    }

    public void onSurveillanceTelegraph(Boss b, List<Tower> marked) {
        AudioManager.sfx(Sfx.PALANTIR_WARNING);   // AUDIO HOOK
        setBanner("PREDICTIVE SURVEILLANCE: analysing " + marked.size() + " towers...", 0xff4d4d, Boss.TELEGRAPH_TIME);
        for (Tower t : marked) events.add(VisualEvent.text(t.getPosition(), "TARGETED", 0xff4d4d));
    }

    public void onSurveillanceApplied(Boss b, int applied, int attempted) {
        if (applied == 0 && attempted > 0) setBanner("Surveillance blocked!", 0x7fd8a8, 2);
        else setBanner("Surveillance disrupts " + applied + " tower(s) for " + (int) Boss.SURVEIL_DURATION + "s", 0xff4d4d, 2.5);
    }

    public void emitText(Vec where, String text, int rgb) { events.add(VisualEvent.text(where, text, rgb)); }
    public void emitTeleport(Vec where) { events.add(VisualEvent.teleport(where)); }

    public void setBanner(String text, int rgb, double seconds) {
        banner = text; bannerRgb = rgb; bannerTime = seconds;
    }

    private void log(String s) {
        log.add(String.format("[%6.1fs] %s", time, s));
        if (log.size() > 200) log.remove(0);
    }
}
